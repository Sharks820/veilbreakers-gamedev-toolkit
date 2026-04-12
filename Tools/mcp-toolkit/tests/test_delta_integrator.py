"""Tests for the delta integrator pass.

These tests verify that terrain height deltas (waterfall pools, cave carves,
stratigraphic erosion) are composed additively into stack.height via
pass_integrate_deltas. Each test FAILS if deltas are not applied.
"""

from __future__ import annotations

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


def _make_stack(size: int = 16, base_height: float = 100.0) -> TerrainMaskStack:
    """Build a minimal mask stack with flat terrain at base_height."""
    stack = TerrainMaskStack(
        tile_size=size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=np.full((size, size), base_height, dtype=np.float64),
    )
    return stack


def _make_state(stack: TerrainMaskStack) -> TerrainPipelineState:
    """Build a pipeline state with scene read attached."""
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
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


class TestDeltaIntegratorWaterfallDelta:
    """Waterfall pool delta must depress terrain height."""

    def test_waterfall_delta_applied_to_height(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        h_before = stack.height.copy()
        # Simulate waterfall carving a pool: negative delta at center
        delta = np.zeros_like(stack.height)
        delta[8, 8] = -5.0
        stack.set("waterfall_pool_delta", delta.astype(np.float32), "waterfalls")

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        # Height at (8,8) must be LOWER than before by the delta amount
        assert stack.height[8, 8] < h_before[8, 8], (
            f"Expected height at pool to decrease, got {stack.height[8, 8]} vs original {h_before[8, 8]}"
        )
        np.testing.assert_almost_equal(stack.height[8, 8], h_before[8, 8] - 5.0)


class TestDeltaIntegratorCaveDelta:
    """Cave height delta must carve terrain."""

    def test_cave_delta_applied_to_height(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        h_before = stack.height.copy()
        delta = np.zeros_like(stack.height)
        delta[4, 4] = -3.0
        delta[5, 5] = -2.0
        stack.set("cave_height_delta", delta.astype(np.float32), "caves")

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        assert stack.height[4, 4] < h_before[4, 4]
        assert stack.height[5, 5] < h_before[5, 5]
        np.testing.assert_almost_equal(stack.height[4, 4], h_before[4, 4] - 3.0)
        np.testing.assert_almost_equal(stack.height[5, 5], h_before[5, 5] - 2.0)


class TestDeltaIntegratorAdditiveComposition:
    """Multiple deltas must compose additively, not last-writer-wins."""

    def test_multiple_deltas_compose_additively(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        h_before = stack.height.copy()

        # Waterfall delta at (8,8)
        wf_delta = np.zeros_like(stack.height)
        wf_delta[8, 8] = -5.0
        stack.set("waterfall_pool_delta", wf_delta.astype(np.float32), "waterfalls")

        # Cave delta also at (8,8)
        cave_delta = np.zeros_like(stack.height)
        cave_delta[8, 8] = -3.0
        stack.set("cave_height_delta", cave_delta.astype(np.float32), "caves")

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        # Both deltas must be applied: -5 + -3 = -8
        expected = h_before[8, 8] - 8.0
        np.testing.assert_almost_equal(
            stack.height[8, 8], expected,
            err_msg=f"Expected additive composition: {expected}, got {stack.height[8, 8]}"
        )


class TestDeltaIntegratorNoDeltas:
    """When no deltas exist, height must be unchanged."""

    def test_no_deltas_height_unchanged(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        h_before = stack.height.copy()

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        np.testing.assert_array_equal(stack.height, h_before)


class TestDeltaIntegratorMetrics:
    """Integration pass must report metrics about applied deltas."""

    def test_metrics_report_delta_channels(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        delta = np.zeros_like(stack.height)
        delta[8, 8] = -5.0
        stack.set("waterfall_pool_delta", delta.astype(np.float32), "waterfalls")

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert "delta_channels_applied" in result.metrics
        assert "waterfall_pool_delta" in result.metrics["delta_channels_applied"]
        assert result.metrics["total_delta_sum"] < 0.0


class TestDeltaIntegratorStratErosionDelta:
    """Stratigraphic erosion delta must be applied."""

    def test_strat_erosion_delta_applied(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack()
        h_before = stack.height.copy()
        delta = np.full_like(stack.height, -0.5, dtype=np.float32)
        stack.set("strat_erosion_delta", delta, "stratigraphy")

        state = _make_state(stack)
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        # Every cell should be 0.5m lower
        np.testing.assert_array_almost_equal(
            stack.height, h_before - 0.5,
            err_msg="Stratigraphic erosion delta was not applied"
        )
