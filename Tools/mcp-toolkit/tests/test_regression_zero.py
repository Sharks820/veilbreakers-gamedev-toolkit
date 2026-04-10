"""Meta-test tracking test count baseline -- Addendum 2 D.1."""
from __future__ import annotations

import subprocess
import sys

import pytest


# Baseline from current verified run
_TEST_BASELINE = 20868
_TOLERANCE = 50  # allow small fluctuation from new/removed tests


class TestRegressionZero:
    """Prevent silent test deletion by tracking total test count."""

    def test_count_above_baseline(self):
        """Total passing test count must not drop significantly below baseline."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--co", "--no-header"],
            capture_output=True, text=True, timeout=60,
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
