from __future__ import annotations

from pathlib import Path

from veilbreakers_mcp import vb_python_reviewer as reviewer


def test_scan_directory_defaults_to_production_scope(tmp_path):
    production_file = tmp_path / "src" / "veilbreakers_mcp" / "demo.py"
    test_file = tmp_path / "tests" / "test_demo.py"
    temp_file = tmp_path / "src" / "veilbreakers_mcp" / "_tmp_demo.py"

    production_file.parent.mkdir(parents=True)
    test_file.parent.mkdir(parents=True)

    production_file.write_text("value = score == 1.0\n", encoding="utf-8")
    test_file.write_text("assert score == 1.0\n", encoding="utf-8")
    temp_file.write_text("value = score == 1.0\n", encoding="utf-8")

    issues = reviewer.scan_directory(str(tmp_path))

    assert {Path(issue.file).name for issue in issues} == {"demo.py"}


def test_scan_directory_strict_can_include_tests_and_temp(tmp_path):
    production_file = tmp_path / "src" / "veilbreakers_mcp" / "demo.py"
    test_file = tmp_path / "tests" / "test_demo.py"
    temp_file = tmp_path / "src" / "veilbreakers_mcp" / "_tmp_demo.py"

    production_file.parent.mkdir(parents=True)
    test_file.parent.mkdir(parents=True)

    production_file.write_text("value = score == 1.0\n", encoding="utf-8")
    test_file.write_text("value = score == 1.0\n", encoding="utf-8")
    temp_file.write_text("value = score == 1.0\n", encoding="utf-8")

    issues = reviewer.scan_directory(
        str(tmp_path),
        review_scope="strict",
        include_tests=True,
        include_temp=True,
    )

    assert {Path(issue.file).name for issue in issues} == {
        "demo.py",
        "test_demo.py",
        "_tmp_demo.py",
    }


def test_strict_lazy_import_rule_ignores_stdlib_imports(tmp_path):
    file_path = tmp_path / "src" / "veilbreakers_mcp" / "demo.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text(
        "def build():\n"
        "    import random\n"
        "    return random.randint(1, 2)\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_file(str(file_path), review_scope="strict")

    assert not any(issue.rule_id == "PY-COR-13" for issue in issues)


def test_strict_lazy_import_rule_only_flags_local_project_imports(tmp_path):
    file_path = tmp_path / "src" / "veilbreakers_mcp" / "demo.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text(
        "def build():\n"
        "    import random\n"
        "    from veilbreakers_mcp.shared import config\n"
        "    return random, config\n",
        encoding="utf-8",
    )

    issues = reviewer.scan_file(str(file_path), review_scope="strict")

    assert any(issue.rule_id == "PY-COR-13" for issue in issues)
    assert not any(
        issue.rule_id == "PY-COR-13" and "random" in issue.description
        for issue in issues
    )


def test_init_module_reexports_do_not_trigger_unused_import_rule(tmp_path):
    init_path = tmp_path / "src" / "veilbreakers_mcp" / "__init__.py"
    init_path.parent.mkdir(parents=True)
    init_path.write_text("from .demo import DemoThing\n", encoding="utf-8")

    issues = reviewer.scan_file(str(init_path), review_scope="strict")

    assert not any(issue.rule_id == "PY-STY-07" for issue in issues)


def test_float_assertions_in_tests_are_suppressed(tmp_path):
    test_path = tmp_path / "tests" / "test_values.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("assert score == 1.0\n", encoding="utf-8")

    issues = reviewer.scan_file(str(test_path), review_scope="strict")

    assert not any(issue.rule_id == "PY-COR-10" for issue in issues)
