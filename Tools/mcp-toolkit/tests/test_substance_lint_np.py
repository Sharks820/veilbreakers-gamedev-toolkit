"""Tests for np.testing.assert_* recognition in test_substance_lint.

Validates that test_substance_lint correctly classifies tests containing
np.testing assertion calls as REAL (not SHALLOW), fixing F842.
"""

import ast
import sys
import textwrap
from pathlib import Path

import pytest

# Ensure scripts/ is importable
_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from test_substance_lint import (
    ASSERT_METHODS,
    TestClass,
    classify_test,
    scan_file,
    _collect_real_assertion_helpers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_synthetic(source: str) -> str:
    """Parse a synthetic test function and classify it."""
    tree = ast.parse(textwrap.dedent(source))
    helpers = _collect_real_assertion_helpers(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                classification, _ = classify_test(node, helpers)
                return classification
    raise ValueError("No test function found in source")


# ---------------------------------------------------------------------------
# Tests: np.testing assertions recognized as REAL
# ---------------------------------------------------------------------------

class TestNpTestingRecognition:
    """np.testing.assert_* must be classified as REAL assertions."""

    def test_assert_array_equal_is_real(self):
        source = """
        def test_foo():
            import numpy as np
            a = np.array([1, 2, 3])
            b = np.array([1, 2, 3])
            np.testing.assert_array_equal(a, b)
        """
        assert _classify_synthetic(source) == TestClass.REAL

    def test_assert_allclose_is_real(self):
        source = """
        def test_foo():
            import numpy as np
            a = np.array([1.0, 2.0])
            b = np.array([1.0, 2.0])
            np.testing.assert_allclose(a, b, atol=1e-6)
        """
        assert _classify_synthetic(source) == TestClass.REAL

    def test_assert_array_almost_equal_is_real(self):
        source = """
        def test_foo():
            import numpy as np
            a = np.array([1.0, 2.0])
            b = np.array([1.0, 2.0])
            np.testing.assert_array_almost_equal(a, b)
        """
        assert _classify_synthetic(source) == TestClass.REAL

    def test_assert_array_less_is_real(self):
        source = """
        def test_foo():
            import numpy as np
            a = np.array([1, 2])
            b = np.array([3, 4])
            np.testing.assert_array_less(a, b)
        """
        assert _classify_synthetic(source) == TestClass.REAL

    def test_assert_equal_np_is_real(self):
        source = """
        def test_foo():
            import numpy as np
            np.testing.assert_equal(42, 42)
        """
        assert _classify_synthetic(source) == TestClass.REAL

    def test_assert_raises_np_is_real(self):
        source = """
        def test_foo():
            import numpy as np
            np.testing.assert_raises(ValueError, int, "not_a_number")
        """
        assert _classify_synthetic(source) == TestClass.REAL


class TestNpTestingInAssertMethods:
    """Verify the ASSERT_METHODS set contains np.testing names."""

    def test_assert_array_equal_in_set(self):
        assert "assert_array_equal" in ASSERT_METHODS

    def test_assert_allclose_in_set(self):
        assert "assert_allclose" in ASSERT_METHODS

    def test_assert_array_almost_equal_in_set(self):
        assert "assert_array_almost_equal" in ASSERT_METHODS

    def test_assert_array_less_in_set(self):
        assert "assert_array_less" in ASSERT_METHODS

    def test_assert_string_equal_in_set(self):
        assert "assert_string_equal" in ASSERT_METHODS

    def test_assert_warns_in_set(self):
        assert "assert_warns" in ASSERT_METHODS


class TestNpTestingTautological:
    """np.testing.assert_array_equal(x, x) with same var should be tautological."""

    def test_same_name_is_tautological(self):
        source = """
        def test_foo():
            import numpy as np
            x = np.array([1, 2, 3])
            np.testing.assert_array_equal(x, x)
        """
        # This test verifies tautological detection for call-based assertions
        # where both args are the same Name node
        result = _classify_synthetic(source)
        assert result == TestClass.TAUTOLOGICAL
