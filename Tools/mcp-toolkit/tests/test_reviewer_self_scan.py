from __future__ import annotations

from pathlib import Path

from veilbreakers_mcp import vb_code_reviewer as reviewer


def test_reviewer_does_not_flag_itself():
    src_dir = Path(__file__).resolve().parent.parent / "src" / "veilbreakers_mcp"

    report = reviewer.scan_project(
        [str(src_dir)],
        lang="py",
        review_scope="production",
        profile="general",
        build_context=False,
    )

    serious = [
        issue
        for issue in report["issues"]
        if issue["severity"] in ("CRITICAL", "HIGH")
    ]
    assert not serious, f"Reviewer flags itself: {serious}"


def test_reviewer_strict_self_scan_has_no_serious_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(reviewer, "CACHE_DIR", str(tmp_path / "cache"))

    src_root = Path(__file__).resolve().parent.parent / "src" / "veilbreakers_mcp"
    reviewer_files = [
        src_root / "vb_code_reviewer.py",
        src_root / "_rules_python.py",
        src_root / "_rules_csharp.py",
        src_root / "_rules_csharp_core.py",
        src_root / "_rules_csharp_unity.py",
        src_root / "_context_engine.py",
        src_root / "_tool_runner.py",
        src_root / "review_server.py",
        src_root / "vb_python_reviewer.py",
    ]

    report = reviewer.scan_project(
        [str(path) for path in reviewer_files],
        lang="auto",
        review_scope="strict",
        profile="all",
        build_context=False,
    )

    serious = [
        issue
        for issue in report["issues"]
        if issue["severity"] in ("CRITICAL", "HIGH")
    ]
    assert not serious, f"Strict reviewer self-scan still has serious findings: {serious}"
