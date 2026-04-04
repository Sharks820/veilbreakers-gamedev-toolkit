"""Tests for _shared_utils.py -- smoothstep, interpolation, and placement utilities.

Pure-logic tests that run without Blender. Tests safe_place_object using
mocked _sample_scene_height to avoid bpy dependency.
"""
from __future__ import annotations

import math
from unittest.mock import patch, MagicMock

import pytest

from blender_addon.handlers._shared_utils import (
    smoothstep,
    inverse_smoothstep,
    lerp,
    smooth_lerp,
)


# ---------------------------------------------------------------------------
# smoothstep tests
# ---------------------------------------------------------------------------


class TestSmoothstep:
    """Test Hermite smoothstep: 3t^2 - 2t^3."""

    def test_zero(self):
        assert smoothstep(0.0) == 0.0

    def test_one(self):
        assert smoothstep(1.0) == 1.0

    def test_half(self):
        assert smoothstep(0.5) == 0.5

    def test_quarter(self):
        result = smoothstep(0.25)
        expected = 0.25 * 0.25 * (3.0 - 2.0 * 0.25)  # 0.15625
        assert abs(result - expected) < 1e-10

    def test_three_quarters(self):
        result = smoothstep(0.75)
        expected = 0.75 * 0.75 * (3.0 - 2.0 * 0.75)  # 0.84375
        assert abs(result - expected) < 1e-10

    def test_clamp_negative(self):
        assert smoothstep(-0.5) == 0.0
        assert smoothstep(-100.0) == 0.0

    def test_clamp_above_one(self):
        assert smoothstep(1.5) == 1.0
        assert smoothstep(100.0) == 1.0

    def test_monotonic(self):
        """Smoothstep must be monotonically increasing in [0, 1]."""
        prev = 0.0
        for i in range(1, 101):
            t = i / 100.0
            val = smoothstep(t)
            assert val >= prev, f"smoothstep({t}) = {val} < {prev}"
            prev = val

    def test_symmetry(self):
        """smoothstep(t) + smoothstep(1-t) == 1 for all t in [0,1]."""
        for i in range(101):
            t = i / 100.0
            assert abs(smoothstep(t) + smoothstep(1.0 - t) - 1.0) < 1e-10

    def test_derivative_zero_at_endpoints(self):
        """Derivative should be ~0 at t=0 and t=1 (smooth ease in/out).

        d/dt[3t^2 - 2t^3] = 6t - 6t^2 = 6t(1-t)
        At t=0: 0, at t=1: 0
        """
        epsilon = 1e-6
        # Near t=0
        deriv_0 = (smoothstep(epsilon) - smoothstep(0.0)) / epsilon
        assert abs(deriv_0) < 0.01

        # Near t=1
        deriv_1 = (smoothstep(1.0) - smoothstep(1.0 - epsilon)) / epsilon
        assert abs(deriv_1) < 0.01


class TestInverseSmoothstep:
    """Test inverse_smoothstep round-trip consistency."""

    def test_zero(self):
        assert inverse_smoothstep(0.0) == 0.0

    def test_one(self):
        assert inverse_smoothstep(1.0) == 1.0

    def test_clamp_negative(self):
        assert inverse_smoothstep(-1.0) == 0.0

    def test_clamp_above_one(self):
        assert inverse_smoothstep(2.0) == 1.0

    def test_round_trip(self):
        """smoothstep(inverse_smoothstep(y)) ~= y for y in [0, 1]."""
        for i in range(1, 100):  # skip endpoints (exact)
            y = i / 100.0
            t = inverse_smoothstep(y)
            recovered = smoothstep(t)
            assert abs(recovered - y) < 1e-6, f"round-trip failed for y={y}: got {recovered}"


# ---------------------------------------------------------------------------
# lerp / smooth_lerp tests
# ---------------------------------------------------------------------------


class TestLerp:
    def test_at_zero(self):
        assert lerp(10.0, 20.0, 0.0) == 10.0

    def test_at_one(self):
        assert lerp(10.0, 20.0, 1.0) == 20.0

    def test_at_half(self):
        assert lerp(0.0, 100.0, 0.5) == 50.0

    def test_clamp_below(self):
        assert lerp(0.0, 100.0, -1.0) == 0.0

    def test_clamp_above(self):
        assert lerp(0.0, 100.0, 2.0) == 100.0

    def test_negative_range(self):
        assert lerp(-10.0, 10.0, 0.5) == 0.0


class TestSmoothLerp:
    def test_at_zero(self):
        assert smooth_lerp(10.0, 20.0, 0.0) == 10.0

    def test_at_one(self):
        assert smooth_lerp(10.0, 20.0, 1.0) == 20.0

    def test_at_half(self):
        # smoothstep(0.5) == 0.5, so smooth_lerp(0, 100, 0.5) == 50
        assert smooth_lerp(0.0, 100.0, 0.5) == 50.0

    def test_ease_in_out_curve(self):
        """smooth_lerp at 0.25 should be closer to start than linear lerp."""
        linear = lerp(0.0, 100.0, 0.25)
        smooth = smooth_lerp(0.0, 100.0, 0.25)
        assert smooth < linear, "smooth_lerp should ease-in slower at 0.25"


# ---------------------------------------------------------------------------
# safe_place_object tests (mocked bpy)
# ---------------------------------------------------------------------------


class TestSafePlaceObject:
    """Test safe_place_object with mocked terrain height sampling."""

    def _import_safe_place(self):
        """Import safe_place_object with mocked worldbuilding module."""
        from blender_addon.handlers._shared_utils import safe_place_object
        return safe_place_object

    def test_basic_placement(self):
        """Object placed at terrain height + offset."""
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 5.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(10.0, 20.0, "Terrain")
            assert result is not None
            assert result[0] == 10.0
            assert result[1] == 20.0
            assert abs(result[2] - 5.02) < 1e-10  # 5.0 + 0.02 offset

    def test_custom_offset(self):
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 3.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(0.0, 0.0, "Terrain", offset_z=0.1)
            assert result is not None
            assert abs(result[2] - 3.1) < 1e-10

    def test_water_exclusion(self):
        """Objects below water level are rejected."""
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 1.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(0.0, 0.0, "Terrain", water_level=2.0)
            assert result is None

    def test_water_level_above(self):
        """Objects above water level are accepted."""
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 5.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(0.0, 0.0, "Terrain", water_level=2.0)
            assert result is not None
            assert abs(result[2] - 5.02) < 1e-10

    def test_bounds_inside(self):
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 0.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(5.0, 5.0, None, bounds=(0.0, 0.0, 10.0, 10.0))
            assert result is not None

    def test_bounds_outside(self):
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 0.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(15.0, 5.0, None, bounds=(0.0, 0.0, 10.0, 10.0))
            assert result is None

    def test_bounds_edge(self):
        """Edge of bounds should be accepted (inclusive)."""
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 0.0,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(10.0, 10.0, None, bounds=(0.0, 0.0, 10.0, 10.0))
            assert result is not None

    def test_height_exception_returns_none(self):
        """If height sampling raises, safe_place returns None."""
        def _failing_sampler(x, y, t):
            raise RuntimeError("No scene")

        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=_failing_sampler,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(0.0, 0.0, "Terrain")
            assert result is None

    def test_no_terrain_name(self):
        """None terrain_name should still work."""
        with patch(
            "blender_addon.handlers._shared_utils._get_sample_scene_height",
            return_value=lambda x, y, t: 2.5,
        ):
            safe_place = self._import_safe_place()
            result = safe_place(0.0, 0.0, None)
            assert result is not None
            assert abs(result[2] - 2.52) < 1e-10


# ---------------------------------------------------------------------------
# Deprecated API static analysis tests
# ---------------------------------------------------------------------------


class TestNoDeprecatedAPI:
    """Verify no deprecated Blender API calls remain in handler files."""

    @staticmethod
    def _handler_source() -> str:
        """Read all handler .py files as a single string."""
        import pathlib
        handlers_dir = pathlib.Path(__file__).parent.parent / "blender_addon" / "handlers"
        sources = []
        for f in sorted(handlers_dir.glob("*.py")):
            sources.append(f.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(sources)

    def test_no_cap_fill(self):
        """cap_fill is not a valid bmesh parameter -- must use cap_ends."""
        source = self._handler_source()
        # Check each line for cap_fill= usage, excluding comments
        active_refs = []
        for line in source.split("\n"):
            stripped = line.strip()
            if "cap_fill" in stripped and "=" in stripped and not stripped.startswith("#"):
                active_refs.append(stripped)
        assert len(active_refs) == 0, f"Found {len(active_refs)} cap_fill= usages (should use cap_ends=): {active_refs}"

    def test_no_musgrave_node(self):
        """ShaderNodeTexMusgrave was removed in Blender 4.1."""
        source = self._handler_source()
        import re
        # Exclude comments
        lines = source.split("\n")
        active_refs = [
            line for line in lines
            if "ShaderNodeTexMusgrave" in line
            and not line.strip().startswith("#")
            and "removed" not in line.lower()
        ]
        assert len(active_refs) == 0, f"Found active ShaderNodeTexMusgrave references: {active_refs}"


# ---------------------------------------------------------------------------
# Dispatch routing tests
# ---------------------------------------------------------------------------


class TestDispatchRouting:
    """Verify pipeline dispatch maps are correctly configured."""

    def test_settlement_routes_to_settlement_handler(self):
        """_LOC_HANDLERS['settlement'] must NOT route to world_generate_town."""
        import re
        import pathlib
        server_path = (
            pathlib.Path(__file__).parent.parent
            / "src" / "veilbreakers_mcp" / "blender_server.py"
        )
        source = server_path.read_text(encoding="utf-8", errors="replace")
        # Find the _LOC_HANDLERS dict definition
        match = re.search(
            r'_LOC_HANDLERS\s*=\s*\{([^}]+)\}',
            source,
            re.DOTALL,
        )
        assert match, "_LOC_HANDLERS dict not found in blender_server.py"
        handlers_block = match.group(1)

        # Extract settlement mapping
        settlement_match = re.search(
            r'"settlement"\s*:\s*"([^"]+)"',
            handlers_block,
        )
        assert settlement_match, "'settlement' key not found in _LOC_HANDLERS"
        handler_name = settlement_match.group(1)
        assert handler_name == "world_generate_settlement", (
            f"settlement routes to '{handler_name}' instead of 'world_generate_settlement'"
        )

    def test_asset_pipeline_handler_routes_lods(self):
        """asset_pipeline COMMAND_HANDLERS entry must handle generate_lods."""
        import pathlib
        init_path = (
            pathlib.Path(__file__).parent.parent
            / "blender_addon" / "handlers" / "__init__.py"
        )
        source = init_path.read_text(encoding="utf-8", errors="replace")
        # Verify the handler references pipeline_generate_lods
        assert "pipeline_generate_lods" in source, (
            "asset_pipeline handler must reference pipeline_generate_lods"
        )
        # Verify it also handles generate_lod_chain
        assert "pipeline_generate_lod_chain" in source, (
            "asset_pipeline handler must reference pipeline_generate_lod_chain"
        )
