from __future__ import annotations

from pathlib import Path

from veilbreakers_mcp import vb_code_reviewer as reviewer


def _parse_truth_label(path: Path) -> str | None:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    if "TRUTH:" not in first_line:
        return None
    return first_line.split("TRUTH:", 1)[1].strip().split()[0]


def _score_python_truth_set() -> tuple[int, int, int]:
    root = Path(__file__).resolve().parent / "truth_set" / "python"
    tp = fp = fn = 0
    for path in root.glob("*.py"):
        truth = _parse_truth_label(path)
        issues = reviewer.scan_python_file(
            str(path), None, review_scope="production", profile="general"
        )
        actual = {issue.rule_id for issue in issues}
        if truth:
            if truth in actual:
                tp += 1
            else:
                fn += 1
            fp += max(0, len(actual - {truth}))
        else:
            fp += len(actual)
    return tp, fp, fn


def _score_csharp_truth_set() -> tuple[int, int, int]:
    root = Path(__file__).resolve().parent / "truth_set" / "csharp"
    tp = fp = fn = 0
    for path in root.glob("*.cs"):
        truth = _parse_truth_label(path)
        issues = reviewer.scan_csharp_file(
            str(path), None, review_scope="production", profile="general"
        )
        actual = {issue.rule_id for issue in issues}
        if truth:
            if truth in actual:
                tp += 1
            else:
                fn += 1
            fp += max(0, len(actual - {truth}))
        else:
            fp += len(actual)
    return tp, fp, fn


def test_python_truth_set_precision_floor():
    tp, fp, fn = _score_python_truth_set()
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    assert precision >= 0.95
    assert recall >= 0.95


def test_csharp_truth_set_precision_floor():
    tp, fp, fn = _score_csharp_truth_set()
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    assert precision >= 0.95
    assert recall >= 0.95
