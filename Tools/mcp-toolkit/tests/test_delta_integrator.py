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
    ProtectedZoneSpec,
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


def _make_state_with_protected_zones(
    stack: TerrainMaskStack,
    zones: tuple,
) -> TerrainPipelineState:
    """Build a pipeline state with protected zones on the intent."""
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
        protected_zones=zones,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


class TestDeltaIntegratorProtectedZones:
    """Protected zones from state.intent must zero out deltas."""

    def test_protected_zone_blocks_delta(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack(size=16, base_height=100.0)
        h_before = stack.height.copy()

        # Apply a uniform -5m delta everywhere
        delta = np.full_like(stack.height, -5.0, dtype=np.float32)
        stack.set("waterfall_pool_delta", delta, "waterfalls")

        # Protect cells covering world coords [2,6] x [2,6]
        # forbidden_mutations blocks integrate_deltas from touching this zone
        zone = ProtectedZoneSpec(
            zone_id="village",
            bounds=BBox(2.0, 2.0, 6.0, 6.0),
            kind="settlement",
            forbidden_mutations=frozenset({"integrate_deltas"}),
        )
        state = _make_state_with_protected_zones(stack, (zone,))
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        # Cells inside the protected zone should be unchanged
        # Cell centers are at (col+0.5)*cell_size, so cols 2-5, rows 2-5
        # are inside the zone [2,6]
        for r in range(2, 6):
            for c in range(2, 6):
                assert stack.height[r, c] == pytest.approx(h_before[r, c]), (
                    f"Protected cell ({r},{c}) was modified"
                )
        # Cells outside the zone must have the delta applied
        assert stack.height[0, 0] == pytest.approx(h_before[0, 0] - 5.0)
        assert stack.height[15, 15] == pytest.approx(h_before[15, 15] - 5.0)

    def test_allowed_mutation_permits_delta(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack(size=16, base_height=100.0)
        h_before = stack.height.copy()

        delta = np.full_like(stack.height, -2.0, dtype=np.float32)
        stack.set("cave_height_delta", delta, "caves")

        # Zone explicitly allows integrate_deltas
        zone = ProtectedZoneSpec(
            zone_id="quarry",
            bounds=BBox(0.0, 0.0, 16.0, 16.0),
            kind="quarry",
            allowed_mutations=frozenset({"integrate_deltas"}),
        )
        state = _make_state_with_protected_zones(stack, (zone,))
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        # All cells should have the delta applied since zone permits it
        np.testing.assert_array_almost_equal(
            stack.height, h_before - 2.0,
            err_msg="Allowed zone should not block deltas"
        )

    def test_hero_exclusion_combined_with_protected_zone(self):
        from blender_addon.handlers.terrain_delta_integrator import pass_integrate_deltas

        stack = _make_stack(size=16, base_height=100.0)
        h_before = stack.height.copy()

        delta = np.full_like(stack.height, -3.0, dtype=np.float32)
        stack.set("strat_erosion_delta", delta, "stratigraphy")

        # Hero exclusion protects row 0
        hero = np.zeros_like(stack.height, dtype=np.float32)
        hero[0, :] = 1.0
        stack.set("hero_exclusion", hero, "hero")

        # Protected zone protects bottom-right corner
        zone = ProtectedZoneSpec(
            zone_id="temple",
            bounds=BBox(12.0, 12.0, 16.0, 16.0),
            kind="sacred",
            forbidden_mutations=frozenset({"integrate_deltas"}),
        )
        state = _make_state_with_protected_zones(stack, (zone,))
        result = pass_integrate_deltas(state, None)

        assert result.status == "ok"
        # Row 0 protected by hero_exclusion
        np.testing.assert_array_almost_equal(
            stack.height[0, :], h_before[0, :],
            err_msg="Hero exclusion row should be unchanged"
        )
        # Bottom-right corner protected by zone
        for r in range(12, 16):
            for c in range(12, 16):
                assert stack.height[r, c] == pytest.approx(h_before[r, c]), (
                    f"Protected zone cell ({r},{c}) was modified"
                )
        # Middle cells should have delta applied
        assert stack.height[6, 6] == pytest.approx(h_before[6, 6] - 3.0)
