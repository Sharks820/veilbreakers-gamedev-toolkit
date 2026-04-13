"""Meta-test tracking test count baseline -- Addendum 2 D.1."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path



# Baseline from current verified run
_TEST_BASELINE = 20868
_TOLERANCE = 50  # allow small fluctuation from new/removed tests
_TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
_TESTS_ROOT = _TOOLKIT_ROOT / "tests"


class TestRegressionZero:
    """Prevent silent test deletion by tracking total test count."""

    def test_count_above_baseline(self):
        """Total passing test count must not drop significantly below baseline."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(_TESTS_ROOT), "-q", "--co", "--no-header"],
            cwd=_TOOLKIT_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        # --co lists collected tests, one per line
        lines = [
            line for line in result.stdout.strip().splitlines()
            if "::" in line  # test lines have :: separator
        ]
        collected = len(lines)
        assert collected >= _TEST_BASELINE - _TOLERANCE, (
            f"Collected {collected} tests, baseline is {_TEST_BASELINE} "
            f"(tolerance {_TOLERANCE}). Tests may have been silently deleted."
        )
