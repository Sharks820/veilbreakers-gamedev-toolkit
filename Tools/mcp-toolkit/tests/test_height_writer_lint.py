"""Tests for L2-HEIGHT-WRITER AST lint rule.

Verifies that stack.set("height", ...) is flagged outside
terrain_delta_integrator.py, and NOT flagged inside it or for
non-height channels.
"""

from __future__ import annotations

import textwrap
import tempfile
import os
import sys

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from quality_lint import scan_file


def _write_tmp(code: str, filename: str = "terrain_test.py") -> str:
    """Write code to a temp file and return its path."""
    d = tempfile.mkdtemp()
    path = os.path.join(d, filename)
    with open(path, "w") as f:
        f.write(textwrap.dedent(code))
    return path


class TestHeightWriterLint:
    """L2-HEIGHT-WRITER rule tests."""

    def test_flags_height_set_in_normal_file(self):
        """stack.set('height', ...) in a non-integrator file -> finding."""
        path = _write_tmp("""
            def pass_foo(state, region):
                stack = state.mask_stack
                stack.set("height", new_h, "foo")
        """, "terrain_foo.py")
        findings = scan_file(path)
        hw = [f for f in findings if f.pattern_id == "L2-07"]
        assert len(hw) >= 1, f"Expected HEIGHT-WRITER finding, got {findings}"

    def test_no_flag_in_integrator(self):
        """stack.set('height', ...) in terrain_delta_integrator.py -> NO finding."""
        path = _write_tmp("""
            def pass_integrate_deltas(state, region):
                stack = state.mask_stack
                stack.set("height", new_h, "integrate_deltas")
        """, "terrain_delta_integrator.py")
        findings = scan_file(path)
        hw = [f for f in findings if f.pattern_id == "L2-07"]
        assert len(hw) == 0, f"Integrator should be exempt, got {hw}"

    def test_no_flag_for_delta_channel(self):
        """stack.set('coastline_delta', ...) -> NO finding."""
        path = _write_tmp("""
            def pass_coastline(state, region):
                stack = state.mask_stack
                stack.set("coastline_delta", delta, "coastline")
        """, "coastline.py")
        findings = scan_file(path)
        hw = [f for f in findings if f.pattern_id == "L2-07"]
        assert len(hw) == 0, f"Delta channels should not trigger, got {hw}"

    def test_flags_height_with_single_quotes(self):
        """stack.set('height', ...) with single quotes also flagged."""
        path = _write_tmp("""
            def pass_bar(state, region):
                stack.set('height', h, 'bar')
        """, "terrain_bar.py")
        findings = scan_file(path)
        hw = [f for f in findings if f.pattern_id == "L2-07"]
        assert len(hw) >= 1
