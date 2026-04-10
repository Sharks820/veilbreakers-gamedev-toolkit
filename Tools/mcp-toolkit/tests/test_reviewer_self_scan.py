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
