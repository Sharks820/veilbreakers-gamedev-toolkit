from __future__ import annotations

from pathlib import Path

from veilbreakers_mcp import vb_python_reviewer
from veilbreakers_mcp.shared.unity_templates.code_review_templates import (
    WEAK_CSHARP_REGEX_RULE_IDS,
    generate_code_reviewer_script,
    generate_python_reviewer_script,
)


def test_generate_python_reviewer_script_uses_canonical_source():
    result = generate_python_reviewer_script()

    assert result["review_scope_default"] == "production"
    assert result["script_content"] == Path(vb_python_reviewer.__file__).read_text(encoding="utf-8")


def test_generate_code_reviewer_script_exports_semantic_tier_metadata():
    result = generate_code_reviewer_script()

    assert result["semantic_tier_rule_ids"] == list(WEAK_CSHARP_REGEX_RULE_IDS)
    assert "semantic_tier_plan" in result
    assert "Roslyn symbols" in result["semantic_tier_plan"]["priority_1"][0]


def test_generated_code_reviewer_uses_safer_python_scan_defaults():
    script = generate_code_reviewer_script()["script_content"]

    assert 'normalized.Contains("/tests/")' in script
    assert 'normalized.Contains("/fixtures/")' in script
    assert 'scanErrors.Add($"{f}: {ex.Message}")' in script


def test_generated_code_reviewer_demotes_weak_bug_rules():
    script = generate_code_reviewer_script()["script_content"]

    assert 'new ReviewRule("BUG-31", Severity.LOW, Category.Quality, Language.CSharp,' in script
    assert 'new ReviewRule("BUG-15", Severity.LOW, Category.Quality, Language.CSharp,' in script
    assert 'new ReviewRule("BUG-19", Severity.LOW, Category.Performance, Language.CSharp,' in script
