"""Integration tests for Phase 52 delta conversion.

Verifies that the 4 converted passes (coastline, karst, wind_erosion, glacial)
produce delta channels instead of writing height directly, and that the
integrator composes them correctly.
"""

from __future__ import annotations

import ast
import os
import glob
from pathlib import Path

import numpy as np
import pytest

from blender_addon.handlers.terrain_semantics import (
    BBox,
    PassResult,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    TerrainSceneRead,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stack(size: int = 32, height_val: float = 100.0) -> TerrainMaskStack:
    """Create a populated stack for testing."""
    h = np.full((size, size), height_val, dtype=np.float64)
    # Add gradient so erosion/coastline passes have slope to work with
    for r in range(size):
        h[r, :] += r * 0.5
    stack = TerrainMaskStack(
        tile_size=size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )
    # rock_hardness needed by karst + wind_erosion
    rh = np.full((size, size), 0.45, dtype=np.float32)
    stack.set("rock_hardness", rh, "test_init")
    # slope for glacial snow_line
    slope = np.full((size, size), 0.3, dtype=np.float32)
    stack.set("slope", slope, "test_init")
    return stack


def _make_state(stack: TerrainMaskStack, hints: dict | None = None) -> TerrainPipelineState:
    """Create a minimal pipeline state wrapping the stack."""
    bounds = BBox(0.0, 0.0, float(stack.tile_size), float(stack.tile_size))
    scene_read = TerrainSceneRead(
        timestamp=0.0,
        major_landforms=("flat",),
        focal_point=(float(stack.tile_size) * 0.5, float(stack.tile_size) * 0.5, 0.0),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=(),
        protected_zones_in_region=(),
        edit_scope=bounds,
        success_criteria=("delta_test",),
        reviewer="pytest",
    )
    intent = TerrainIntentState(
        seed=42,
        region_bounds=bounds,
        tile_size=stack.tile_size,
        cell_size=1.0,
        scene_read=scene_read,
        composition_hints=hints or {},
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# Test: pass_coastline produces coastline_delta, not height
# ---------------------------------------------------------------------------

class TestCoastlineDelta:
    def test_produces_coastline_delta_channel(self):
        """pass_coastline with erosion enabled writes coastline_delta."""
        from blender_addon.handlers.coastline import pass_coastline

        stack = _make_stack()
        # Set height near sea level so coastal erosion has effect
        h = np.linspace(-2.0, 5.0, stack.height.size).reshape(stack.height.shape)
        stack.set("height", h.astype(np.float64), "setup")
        old_height = stack.height.copy()

        state = _make_state(stack, {"coastal_erosion_enabled": True, "sea_level_m": 0.0})
        result = pass_coastline(state, None)

        assert result.status == "ok"
        # Height must NOT have changed
        np.testing.assert_array_equal(stack.height, old_height)
        # coastline_delta channel must exist
        delta = stack.get("coastline_delta")
        assert delta is not None, "coastline_delta channel not produced"
        assert "coastline_delta" in result.produced_channels

    def test_no_delta_when_erosion_disabled(self):
        """Without coastal_erosion_enabled, no coastline_delta produced."""
        from blender_addon.handlers.coastline import pass_coastline

        stack = _make_stack()
        state = _make_state(stack, {"coastal_erosion_enabled": False})
        result = pass_coastline(state, None)
        assert "coastline_delta" not in result.produced_channels


# ---------------------------------------------------------------------------
# Test: pass_karst produces karst_delta, not height
# ---------------------------------------------------------------------------

class TestKarstDelta:
    def test_produces_karst_delta_channel(self):
        """pass_karst writes karst_delta when features found."""
        from blender_addon.handlers.terrain_karst import pass_karst

        stack = _make_stack()
        old_height = stack.height.copy()

        state = _make_state(stack, {"karst_enabled": True})
        result = pass_karst(state, None)

        assert result.status == "ok"
        # Height must NOT have changed
        np.testing.assert_array_equal(stack.height, old_height)
        # If features found, karst_delta exists
        delta = stack.get("karst_delta")
        if result.metrics.get("feature_count", 0) > 0:
            assert delta is not None
            assert "karst_delta" in result.produced_channels


# ---------------------------------------------------------------------------
# Test: pass_wind_erosion produces wind_erosion_delta, not height
# ---------------------------------------------------------------------------

class TestWindErosionDelta:
    def test_produces_wind_erosion_delta_channel(self):
        """pass_wind_erosion writes wind_erosion_delta."""
        from blender_addon.handlers.terrain_wind_erosion import pass_wind_erosion

        stack = _make_stack()
        old_height = stack.height.copy()

        state = _make_state(stack, {"wind_erosion_intensity": 0.5})
        result = pass_wind_erosion(state, None)

        assert result.status == "ok"
        # Height must NOT have changed
        np.testing.assert_array_equal(stack.height, old_height)
        # wind_erosion_delta must exist
        delta = stack.get("wind_erosion_delta")
        assert delta is not None, "wind_erosion_delta channel not produced"
        assert "wind_erosion_delta" in result.produced_channels
        # Delta should be non-zero with intensity > 0
        assert np.any(delta != 0.0)


# ---------------------------------------------------------------------------
# Test: pass_glacial produces glacial_delta, not height
# ---------------------------------------------------------------------------

class TestGlacialDelta:
    def test_produces_glacial_delta_with_paths(self):
        """pass_glacial with glacier_paths writes glacial_delta."""
        from blender_addon.handlers.terrain_glacial import pass_glacial

        stack = _make_stack(size=64, height_val=2500.0)
        old_height = stack.height.copy()

        glacier_paths = [
            {"path": [(10, 10), (50, 50)], "width_m": 20.0, "depth_m": 10.0}
        ]
        state = _make_state(stack, {"glacier_paths": glacier_paths, "snow_line_altitude_m": 2000.0})
        result = pass_glacial(state, None)

        assert result.status == "ok"
        # Height must NOT have changed
        np.testing.assert_array_equal(stack.height, old_height)
        # glacial_delta must exist
        delta = stack.get("glacial_delta")
        assert delta is not None, "glacial_delta channel not produced"
        assert "glacial_delta" in result.produced_channels

    def test_no_delta_without_paths(self):
        """Without glacier_paths, no glacial_delta produced."""
        from blender_addon.handlers.terrain_glacial import pass_glacial

        stack = _make_stack(size=32, height_val=2500.0)
        state = _make_state(stack, {"snow_line_altitude_m": 2000.0})
        result = pass_glacial(state, None)
        assert "glacial_delta" not in result.produced_channels


# ---------------------------------------------------------------------------
# Test: integrator composes all deltas correctly
# ---------------------------------------------------------------------------

class TestIntegratorComposition:
    def test_integrator_sums_all_deltas(self):
        """pass_integrate_deltas sums coastline + karst + wind + glacial deltas."""
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        original_height = stack.height.copy()

        # Simulate delta channels from the 4 passes
        d1 = np.full(stack.height.shape, -1.0, dtype=np.float32)
        d2 = np.full(stack.height.shape, -0.5, dtype=np.float32)
        d3 = np.full(stack.height.shape, 0.3, dtype=np.float32)
        d4 = np.full(stack.height.shape, -2.0, dtype=np.float32)
        stack.set("coastline_delta", d1, "coastline")
        stack.set("karst_delta", d2, "karst")
        stack.set("wind_erosion_delta", d3, "wind_erosion")
        stack.set("glacial_delta", d4, "glacial")

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        expected = original_height + (-1.0 + -0.5 + 0.3 + -2.0)
        np.testing.assert_allclose(stack.height, expected, atol=1e-6)
        assert result.metrics["cells_modified"] > 0
        applied = result.metrics["delta_channels_applied"]
        assert "coastline_delta" in applied
        assert "karst_delta" in applied
        assert "wind_erosion_delta" in applied
        assert "glacial_delta" in applied


# ---------------------------------------------------------------------------
# Test: No pass source writes stack.set("height",...) except integrator
# ---------------------------------------------------------------------------

class TestNoDirectHeightWrites:
    def test_no_height_set_outside_integrator(self):
        """AST scan: no handler file calls stack.set('height',...) except integrator."""
        handlers_dir = Path(__file__).parent.parent / "blender_addon" / "handlers"
        exempt = "terrain_delta_integrator.py"

        # Files that are out of scope for this phase (not Bundle I passes)
        # These will be converted in future phases
        known_exceptions = {
            "terrain_banded.py",
            "terrain_framing.py",
            "terrain_masks.py",
            "_terrain_world.py",
        }

        violations = []
        for pyfile in sorted(handlers_dir.glob("*.py")):
            if pyfile.name == exempt:
                continue
            if pyfile.name in known_exceptions:
                continue
            try:
                source = pyfile.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr != "set":
                    continue
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "height":
                    violations.append(f"{pyfile.name}:{node.lineno}")

        assert violations == [], (
            f"Direct stack.set('height',...) found outside integrator: {violations}"
        )
