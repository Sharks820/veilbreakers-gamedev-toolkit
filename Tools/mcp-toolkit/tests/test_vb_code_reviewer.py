from __future__ import annotations

from pathlib import Path

from veilbreakers_mcp._context_engine import ContextEngine
from veilbreakers_mcp import vb_code_reviewer as reviewer
from veilbreakers_mcp._tool_runner import ToolFinding, _map_ruff_severity
from veilbreakers_mcp._types import Category


def test_reexport_import_is_not_flagged_unused(tmp_path):
    init_path = tmp_path / "src" / "veilbreakers_mcp" / "__init__.py"
    init_path.parent.mkdir(parents=True)
    init_path.write_text("from .demo import Demo as Demo\n", encoding="utf-8")

    issues = reviewer.scan_python_file(str(init_path), None, review_scope="strict")

    assert not any(issue.rule_id == "PY-STY-07" for issue in issues)


def test_private_rule_module_skips_main_guard_and_all_export_noise(tmp_path):
    rules_path = tmp_path / "src" / "veilbreakers_mcp" / "_rules_demo.py"
    rules_path.parent.mkdir(parents=True)
    rules_path.write_text(
        "RULES = []\nRULES.append('demo')\ndef public_name():\n    return 1\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_python_file(str(rules_path), None, review_scope="strict")

    rule_ids = {issue.rule_id for issue in issues}
    assert "PY-STY-05" not in rule_ids
    assert "PY-STY-06" not in rule_ids


def test_csharp_line_classifier_tracks_nested_braces_in_hot_method():
    lines = [
        "void Update() {",
        "    if (x) {",
        "        Foo();",
        "    }",
        "    Bar();",
        "}",
    ]

    classifier = reviewer.CSharpLineClassifier()
    result = classifier.classify(lines)

    assert result == ["HotPath", "HotPath", "HotPath", "HotPath", "HotPath", "HotPath"]
    assert classifier.method_boundaries == [(0, 5, "Update")]


def test_context_engine_tracks_variable_states(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file_path = src_dir / "demo.py"
    file_path.write_text(
        "def demo(x=None):\n"
        "    value = x\n"
        "    if value is None:\n"
        "        return 0\n"
        "    return value\n",
        encoding="utf-8",
    )

    engine = ContextEngine(src_dir)
    engine.build_context()

    assert "value" in engine.variable_states
    assert engine.variable_states["value"].null_checks


def test_bug55_only_fires_in_teardown_methods(tmp_path):
    csharp_path = tmp_path / "Teardown.cs"
    csharp_path.write_text(
        "using System.Threading.Tasks;\n"
        "class Demo {\n"
        "    async Task Work() { await Task.Delay(1); }\n"
        "    async void OnDestroy() { await Task.Delay(1); }\n"
        "}\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_csharp_file(str(csharp_path), None, review_scope="strict")
    bug55_lines = [issue.line for issue in issues if issue.rule_id == "BUG-55"]

    assert bug55_lines == [4]


def test_game05_only_targets_particle_system_play_calls(tmp_path):
    csharp_path = tmp_path / "Effects.cs"
    csharp_path.write_text(
        "class ParticleSystem { public bool isPlaying; public void Play() {} }\n"
        "class AudioSource { public void Play() {} }\n"
        "class Demo {\n"
        "    ParticleSystem particles;\n"
        "    AudioSource audio;\n"
        "    void Update() {\n"
        "        particles.Play();\n"
        "        audio.Play();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_csharp_file(str(csharp_path), None, review_scope="strict")
    game05_lines = [issue.line for issue in issues if issue.rule_id == "GAME-05"]

    assert game05_lines == [7]


def test_strengthening_noise_curation_keeps_bug_signal():
    issues = [
        {
            "rule_id": "PY-STY-07",
            "file": "a.py",
            "line": 1,
            "layer": "heuristic",
            "finding_type": "STRENGTHENING",
            "confidence": 82,
            "priority": 50,
            "severity": "LOW",
        },
        {
            "rule_id": "PY-STY-07",
            "file": "a.py",
            "line": 2,
            "layer": "heuristic",
            "finding_type": "STRENGTHENING",
            "confidence": 82,
            "priority": 50,
            "severity": "LOW",
        },
        {
            "rule_id": "PY-STY-07",
            "file": "a.py",
            "line": 3,
            "layer": "heuristic",
            "finding_type": "STRENGTHENING",
            "confidence": 82,
            "priority": 50,
            "severity": "LOW",
        },
        {
            "rule_id": "PY-COR-12",
            "file": "a.py",
            "line": 4,
            "layer": "semantic",
            "finding_type": "BUG",
            "confidence": 75,
            "priority": 50,
            "severity": "MEDIUM",
        },
    ]

    curated = reviewer._curate_strengthening_noise(issues)

    assert sum(1 for issue in curated if issue["rule_id"] == "PY-STY-07") == 1
    assert any(issue["rule_id"] == "PY-COR-12" for issue in curated)


def test_map_ruff_severity_demotes_style_noise_but_keeps_real_bugs():
    assert _map_ruff_severity("F401") == "LOW"
    assert _map_ruff_severity("E402") == "LOW"
    assert _map_ruff_severity("F821") == "HIGH"
    assert _map_ruff_severity("S603") == "HIGH"


def test_production_scan_hides_style_only_ruff_findings(monkeypatch, tmp_path):
    src_dir = tmp_path / "src" / "veilbreakers_mcp"
    src_dir.mkdir(parents=True)
    file_path = src_dir / "demo.py"
    file_path.write_text("import os\n", encoding="utf-8")

    from veilbreakers_mcp import _tool_runner as tool_runner

    monkeypatch.setattr(
        tool_runner,
        "available_tools",
        lambda: {"ruff": True, "opengrep": False, "mypy": False, "dotnet": False, "ast-grep": False},
    )
    monkeypatch.setattr(
        tool_runner,
        "run_ruff",
        lambda files: [
            ToolFinding(
                tool="ruff",
                rule_id="RUFF-F401",
                file=str(file_path.resolve()),
                line=1,
                description="unused import",
                severity="LOW",
            )
        ],
    )

    report = reviewer.scan_project([str(src_dir)], lang="py", review_scope="production", build_context=False)

    assert report["total_issues"] == 0


def test_production_scan_keeps_real_ruff_correctness_findings(monkeypatch, tmp_path):
    src_dir = tmp_path / "src" / "veilbreakers_mcp"
    src_dir.mkdir(parents=True)
    file_path = src_dir / "demo.py"
    file_path.write_text("value = missing_name\n", encoding="utf-8")

    from veilbreakers_mcp import _tool_runner as tool_runner

    monkeypatch.setattr(
        tool_runner,
        "available_tools",
        lambda: {"ruff": True, "opengrep": False, "mypy": False, "dotnet": False, "ast-grep": False},
    )
    monkeypatch.setattr(
        tool_runner,
        "run_ruff",
        lambda files: [
            ToolFinding(
                tool="ruff",
                rule_id="RUFF-F821",
                file=str(file_path.resolve()),
                line=1,
                description="undefined name `missing_name`",
                severity="HIGH",
            )
        ],
    )

    report = reviewer.scan_project([str(src_dir)], lang="py", review_scope="production", build_context=False)

    assert report["total_issues"] == 1
    assert report["issues"][0]["rule_id"] == "RUFF-F821"


def test_general_profile_treats_non_vb_python_files_as_production(tmp_path):
    src_dir = tmp_path / "arbitrary_app"
    src_dir.mkdir()
    file_path = src_dir / "demo.py"
    file_path.write_text("result = eval(user_input)\n", encoding="utf-8")

    report = reviewer.scan_project(
        [str(src_dir)],
        lang="py",
        review_scope="production",
        profile="general",
        build_context=False,
    )

    assert any("PY-SEC-01" in issue["rule_id"] for issue in report["issues"])


def test_general_profile_excludes_unity_only_csharp_rules(tmp_path):
    csharp_path = tmp_path / "Runtime.cs"
    csharp_path.write_text(
        "using UnityEditor;\n"
        "public class Demo { }\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_csharp_file(
        str(csharp_path), None, review_scope="production", profile="general"
    )

    assert not any(issue.rule_id == "BUILD-01" for issue in issues)


def test_unity_profile_includes_unity_only_csharp_rules(tmp_path):
    csharp_path = tmp_path / "Runtime.cs"
    csharp_path.write_text(
        "using UnityEditor;\n"
        "public class Demo { }\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_csharp_file(
        str(csharp_path), None, review_scope="production", profile="unity"
    )

    assert any(issue.rule_id == "BUILD-01" for issue in issues)


def test_blender_profile_retains_blender_python_rules(tmp_path):
    python_path = tmp_path / "build_mesh.py"
    python_path.write_text(
        "def build_mesh(name):\n"
        "    mesh = bpy.data.meshes.new(name)\n"
        "    obj = bpy.data.objects.new(name, mesh)\n"
        "    bpy.context.collection.objects.link(obj)\n"
        "    return obj\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_python_file(
        str(python_path), None, review_scope="strict", profile="blender"
    )

    assert any(issue.rule_id == "BLE-02" for issue in issues)


def test_review_ignore_alias_suppresses_python_rule(tmp_path):
    file_path = tmp_path / "demo.py"
    file_path.write_text(
        "# REVIEW-IGNORE: PY-SEC-01\n"
        "result = eval(user_input)\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_python_file(str(file_path), None, review_scope="production")

    assert not any(issue.rule_id == "PY-SEC-01" for issue in issues)


def test_review_ignore_alias_suppresses_csharp_rule(tmp_path):
    file_path = tmp_path / "demo.cs"
    file_path.write_text(
        "using UnityEditor; // REVIEW-IGNORE\n"
        "public class Demo { }\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_csharp_file(
        str(file_path), None, review_scope="production", profile="unity"
    )

    assert not any(issue.rule_id == "BUILD-01" for issue in issues)


def test_framework_category_name_replaces_unity_name():
    assert Category.Framework.name == "Framework"


def test_display_path_uses_scan_root_relative_path(tmp_path):
    root = tmp_path / "repo"
    target = root / "src" / "module" / "demo.py"
    target.parent.mkdir(parents=True)
    target.write_text("pass\n", encoding="utf-8")

    display = reviewer._display_path(str(target), [str(root)])

    assert display == "src/module/demo.py"


def test_parse_unified_diff_extracts_added_line_ranges(tmp_path):
    diff_text = (
        "diff --git a/src/demo.py b/src/demo.py\n"
        "--- a/src/demo.py\n"
        "+++ b/src/demo.py\n"
        "@@ -1,1 +4,2 @@\n"
        "+result = eval(user_input)\n"
        "+print(result)\n"
    )

    changed = reviewer._parse_unified_diff(diff_text, base_dir=str(tmp_path))

    expected = str((tmp_path / "src" / "demo.py").resolve()).replace("\\", "/")
    assert changed == {expected: [(4, 5)]}


def test_changed_ranges_filter_out_unchanged_findings(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file_path = src_dir / "demo.py"
    file_path.write_text(
        "result = eval(user_input)\n"
        "print('safe')\n"
        "exec(code_string)\n",
        encoding="utf-8",
    )

    changed = {str(file_path.resolve()).replace("\\", "/"): [(1, 1)]}
    report = reviewer.scan_project(
        [str(src_dir)],
        lang="py",
        review_scope="production",
        profile="general",
        changed_ranges=changed,
        build_context=False,
    )

    assert report["total_issues"] == 1
    assert "PY-SEC-01" in report["issues"][0]["rule_id"]


def test_embedded_csharp_template_is_classified_as_csharp():
    lines = [
        'script = f"""',
        "using UnityEngine;",
        "public class Demo { void Run() { } }",
        '"""',
    ]

    classified = reviewer._classify_embedded_language(lines)

    assert classified == ["csharp", "csharp", "csharp", "csharp"]


def test_embedded_csharp_template_does_not_trigger_python_rules(tmp_path):
    file_path = tmp_path / "template.py"
    file_path.write_text(
        'script = f"""\n'
        "using System;\n"
        "public class Demo { void Run() { eval(code); } }\n"
        '"""\n',
        encoding="utf-8",
    )

    issues = reviewer.scan_python_file(
        str(file_path), None, review_scope="production", profile="general"
    )

    assert not issues


def test_scan_stdin_content_python():
    report = reviewer._scan_stdin_content(
        "result = eval(user_input)\n",
        lang="py",
        review_scope="production",
        profile="general",
    )

    assert report["total_issues"] == 1
    assert report["issues"][0]["file"] == "<stdin>"
    assert "PY-SEC-01" in report["issues"][0]["rule_id"]


def test_scan_stdin_content_csharp():
    report = reviewer._scan_stdin_content(
        "using System.Threading.Tasks;\n"
        "public class Bad {\n"
        "    public void Run(Task<int> work) {\n"
        "        var value = work.Result;\n"
        "    }\n"
        "}\n",
        lang="cs",
        review_scope="production",
        profile="general",
    )

    assert any("CS-COR-06" in issue["rule_id"] for issue in report["issues"])
