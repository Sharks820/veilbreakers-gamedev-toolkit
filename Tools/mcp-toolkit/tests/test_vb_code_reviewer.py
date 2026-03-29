from __future__ import annotations

from pathlib import Path

from veilbreakers_mcp._context_engine import ContextEngine
from veilbreakers_mcp import vb_code_reviewer as reviewer


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
