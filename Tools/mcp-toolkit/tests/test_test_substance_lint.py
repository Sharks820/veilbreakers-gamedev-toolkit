from __future__ import annotations

from textwrap import dedent

from scripts import test_substance_lint as lint


def _scan_snippet(tmp_path, source: str):
    path = tmp_path / "test_sample.py"
    path.write_text(dedent(source), encoding="utf-8")
    return {result.name: result for result in lint.scan_file(str(path))}


def test_scan_file_treats_pytest_raises_as_real(tmp_path):
    results = _scan_snippet(
        tmp_path,
        """
        import pytest

        def test_value_error_is_checked():
            with pytest.raises(ValueError, match="bad input"):
                raise ValueError("bad input")
        """,
    )

    assert results["test_value_error_is_checked"].classification == lint.TestClass.REAL


def test_scan_file_treats_real_assert_helpers_as_real(tmp_path):
    results = _scan_snippet(
        tmp_path,
        """
        def validate_shape(result):
            assert result["value"] == 3
            assert result["kind"] == "shape"

        def test_helper_backed_assertions():
            validate_shape({"value": 3, "kind": "shape"})
        """,
    )

    result = results["test_helper_backed_assertions"]
    assert result.classification == lint.TestClass.REAL
    assert "real assertions" in result.reason


def test_scan_file_follows_nested_assert_helpers(tmp_path):
    results = _scan_snippet(
        tmp_path,
        """
        def assert_inner(value):
            assert value == 7

        def assert_outer(value):
            assert_inner(value)

        def test_nested_helper_assertions():
            assert_outer(7)
        """,
    )

    assert results["test_nested_helper_assertions"].classification == lint.TestClass.REAL


def test_scan_file_keeps_shallow_isinstance_checks_shallow(tmp_path):
    results = _scan_snippet(
        tmp_path,
        """
        def test_only_type_check():
            result = {"ok": True}
            assert isinstance(result, dict)
        """,
    )

    assert results["test_only_type_check"].classification == lint.TestClass.SHALLOW


def test_scan_file_keeps_tautologies_tautological(tmp_path):
    results = _scan_snippet(
        tmp_path,
        """
        def test_always_true():
            assert True
        """,
    )

    assert results["test_always_true"].classification == lint.TestClass.TAUTOLOGICAL
