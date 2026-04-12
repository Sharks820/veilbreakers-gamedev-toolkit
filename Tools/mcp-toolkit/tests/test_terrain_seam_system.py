"""Tests for the seam system: guards, node registry, stitcher, fault lines,
pipe erosion, and Poisson blending.

Each test must FAIL if the function body is replaced with pass/return None.
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_seam_guards import (
    apply_hero_delta_with_fade,
    compute_edge_fade_weights,
    compute_guard_band_mask,
    create_seam_guard_zones,
    is_in_guard_band,
)
from blender_addon.handlers.terrain_node_registry import (
    TerrainNodeInfo,
    TerrainNodeRegistry,
)
from blender_addon.handlers.terrain_seam_stitcher import (
    compute_adaptive_tolerance,
    compute_triplanar_continuity_weights,
    normalize_height_safe,
    repair_seam_heights,
    resize_heightmap_bilinear,
    resize_heightmap_bilinear_fast,
    safe_height_scale,
    snap_material_ids_at_seam,
    stitch_shared_edge,
    validate_protected_zone_seam_integrity,
    validate_stitched_export,
)
from blender_addon.handlers.terrain_fault_lines import (
    FaultLine,
    apply_fault_lines,
    compute_fault_displacement,
    generate_random_faults,
    signed_distance_to_fault,
)
from blender_addon.handlers.terrain_pipe_erosion import (
    pipe_model_erosion,
    poisson_blend,
    poisson_blend_patch,
)


# ===================================================================
# Seam guard tests
# ===================================================================


class TestGuardBandMask:
    def test_guard_band_covers_edges(self):
        mask = compute_guard_band_mask(16, guard_width=2)
        assert mask.shape == (17, 17)
        # Top edge cells should be guarded
        assert mask[0, 8]
        assert mask[1, 8]
        # Bottom edge cells should be guarded
        assert mask[16, 8]
        assert mask[15, 8]
        # Interior should NOT be guarded
        assert not mask[8, 8]

    def test_guard_band_zero_width_all_unguarded(self):
        mask = compute_guard_band_mask(16, guard_width=0)
        assert not np.any(mask)

    def test_guard_band_large_width_all_guarded(self):
        mask = compute_guard_band_mask(8, guard_width=10)
        assert np.all(mask)

    def test_guard_band_custom_shape(self):
        mask = compute_guard_band_mask(16, guard_width=3, shape=(20, 30))
        assert mask.shape == (20, 30)
        assert mask[0, 0]
        assert not mask[10, 15]


class TestEdgeFadeWeights:
    def test_fade_center_is_one(self):
        w = compute_edge_fade_weights(32, fade_width=8)
        assert w.shape == (33, 33)
        # Center should be 1.0
        assert w[16, 16] == pytest.approx(1.0)

    def test_fade_edge_is_zero(self):
        w = compute_edge_fade_weights(32, fade_width=8)
        # Corner should be 0.0
        assert w[0, 0] == pytest.approx(0.0)

    def test_fade_monotonic_increase(self):
        w = compute_edge_fade_weights(32, fade_width=8)
        # Moving from edge to center along a row, weights increase
        row_vals = w[16, :17]  # center row, left half
        for i in range(1, len(row_vals)):
            assert row_vals[i] >= row_vals[i - 1]


class TestHeroDeltaFade:
    def test_delta_zero_at_edges(self):
        base = np.ones((17, 17)) * 10.0
        delta = np.ones((17, 17)) * 5.0
        fade = compute_edge_fade_weights(16, fade_width=4)
        result = apply_hero_delta_with_fade(base, delta, fade)
        # At corner, fade=0, so result=base
        assert result[0, 0] == pytest.approx(10.0)
        # At center, fade=1, so result=base+delta=15
        assert result[8, 8] == pytest.approx(15.0)

    def test_delta_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="shape"):
            apply_hero_delta_with_fade(
                np.ones((5, 5)), np.ones((3, 3)), np.ones((5, 5))
            )


class TestIsInGuardBand:
    def test_corner_is_guarded(self):
        assert is_in_guard_band(0, 0, 16, guard_width=2)

    def test_center_is_not_guarded(self):
        assert not is_in_guard_band(8, 8, 16, guard_width=2)


class TestCreateSeamGuardZones:
    def test_creates_four_zones(self):
        zones = create_seam_guard_zones(
            tile_x=0, tile_y=0, tile_size=256,
            cell_size=1.0, world_origin_x=0.0, world_origin_y=0.0,
            guard_width=4,
        )
        assert len(zones) == 4
        kinds = {z.kind for z in zones}
        assert kinds == {"seam_guard"}

    def test_zones_forbid_erosion(self):
        zones = create_seam_guard_zones(
            tile_x=0, tile_y=0, tile_size=256,
            cell_size=1.0, world_origin_x=0.0, world_origin_y=0.0,
        )
        for z in zones:
            assert not z.permits("erosion")
            assert z.permits("macro_world")
            assert z.permits("structural_masks")


# ===================================================================
# Node registry tests
# ===================================================================


class TestTerrainNodeRegistry:
    def _make_node(self, tx=0, ty=0, tile_size=256, cell_size=1.0):
        return TerrainNodeInfo(
            tile_x=tx, tile_y=ty, tile_size=tile_size, cell_size=cell_size,
            world_origin_x=0.0, world_origin_y=0.0,
        )

    def test_register_and_get(self):
        reg = TerrainNodeRegistry(expected_tile_size=256, expected_cell_size=1.0)
        node = self._make_node(0, 0)
        reg.register(node)
        assert (0, 0) in reg
        assert reg.get(0, 0) is node
        assert len(reg) == 1

    def test_config_mismatch_raises(self):
        reg = TerrainNodeRegistry(expected_tile_size=256)
        bad_node = self._make_node(0, 0, tile_size=128)
        with pytest.raises(ValueError, match="tile_size"):
            reg.register(bad_node)

    def test_neighbor_lookup(self):
        reg = TerrainNodeRegistry(expected_tile_size=256, expected_cell_size=1.0)
        reg.register(self._make_node(0, 0))
        reg.register(self._make_node(1, 0))
        east = reg.get_neighbor(0, 0, "east")
        assert east is not None
        assert east.tile_x == 1
        west = reg.get_neighbor(0, 0, "west")
        assert west is None

    def test_shared_edge_pairs(self):
        reg = TerrainNodeRegistry(expected_tile_size=256, expected_cell_size=1.0)
        reg.register(self._make_node(0, 0))
        reg.register(self._make_node(1, 0))
        reg.register(self._make_node(0, 1))
        pairs = reg.get_shared_edge_pairs()
        assert len(pairs) == 2  # (0,0)->(1,0) east, (0,0)->(0,1) north

    def test_edge_height_validation(self):
        reg = TerrainNodeRegistry(expected_tile_size=4, expected_cell_size=1.0)
        reg.register(TerrainNodeInfo(
            tile_x=0, tile_y=0, tile_size=4, cell_size=1.0,
            world_origin_x=0.0, world_origin_y=0.0,
        ))
        reg.register(TerrainNodeInfo(
            tile_x=1, tile_y=0, tile_size=4, cell_size=1.0,
            world_origin_x=4.0, world_origin_y=0.0,
        ))
        # Create matching heightmaps
        h_a = np.ones((5, 5)) * 10.0
        h_b = np.ones((5, 5)) * 10.0
        reg.cache_edge_heights(0, 0, h_a)
        reg.cache_edge_heights(1, 0, h_b)
        result = reg.validate_edge_match(0, 0, "east")
        assert result["match"]
        assert result["max_delta"] == pytest.approx(0.0)

    def test_edge_height_mismatch_detected(self):
        reg = TerrainNodeRegistry(expected_tile_size=4, expected_cell_size=1.0)
        reg.register(TerrainNodeInfo(
            tile_x=0, tile_y=0, tile_size=4, cell_size=1.0,
            world_origin_x=0.0, world_origin_y=0.0,
        ))
        reg.register(TerrainNodeInfo(
            tile_x=1, tile_y=0, tile_size=4, cell_size=1.0,
            world_origin_x=4.0, world_origin_y=0.0,
        ))
        h_a = np.ones((5, 5)) * 10.0
        h_b = np.ones((5, 5)) * 20.0  # Different!
        reg.cache_edge_heights(0, 0, h_a)
        reg.cache_edge_heights(1, 0, h_b)
        result = reg.validate_edge_match(0, 0, "east")
        assert not result["match"]
        assert result["max_delta"] > 0

    def test_hero_node_tracking(self):
        reg = TerrainNodeRegistry(expected_tile_size=256, expected_cell_size=1.0)
        reg.register(self._make_node(0, 0))
        reg.register(self._make_node(1, 0))
        reg.mark_hero(0, 0, ("cliff_01",))
        heroes = reg.hero_nodes()
        assert len(heroes) == 1
        assert heroes[0].hero_feature_ids == ("cliff_01",)


# ===================================================================
# Stitcher tests
# ===================================================================


class TestStitchSharedEdge:
    def test_average_stitch(self):
        a = np.array([10.0, 20.0, 30.0])
        b = np.array([12.0, 18.0, 32.0])
        ra, rb = stitch_shared_edge(a, b)
        assert np.array_equal(ra, rb)
        assert ra[0] == pytest.approx(11.0)
        assert ra[1] == pytest.approx(19.0)

    def test_idempotent_f164(self):
        """F164: stitching twice produces same result as once."""
        a = np.array([10.0, 20.0])
        b = np.array([12.0, 22.0])
        r1a, r1b = stitch_shared_edge(a, b)
        r2a, r2b = stitch_shared_edge(r1a, r1b)
        np.testing.assert_array_equal(r1a, r2a)
        np.testing.assert_array_equal(r1b, r2b)

    def test_already_equal_returns_copies(self):
        a = np.array([5.0, 5.0])
        ra, rb = stitch_shared_edge(a, a.copy())
        np.testing.assert_array_equal(ra, rb)


class TestAdaptiveTolerance:
    def test_at_origin_returns_base(self):
        tol = compute_adaptive_tolerance((0.0, 0.0), (0.0, 0.0), base_tolerance=1e-6)
        assert tol == pytest.approx(1e-6)

    def test_scales_with_offset_f165(self):
        """F165: tolerance grows at large world offsets."""
        tol_near = compute_adaptive_tolerance((0.0, 0.0), (100.0, 0.0))
        tol_far = compute_adaptive_tolerance((0.0, 0.0), (10000.0, 0.0))
        assert tol_far > tol_near


class TestMaterialSnap:
    def test_identical_unchanged(self):
        a = np.array([1, 2, 3], dtype=np.int32)
        ra, rb = snap_material_ids_at_seam(a, a.copy())
        np.testing.assert_array_equal(ra, rb)

    def test_conflict_resolved_f166(self):
        """F166: material conflicts at seam resolved deterministically."""
        a = np.array([1, 2, 3], dtype=np.int32)
        b = np.array([1, 5, 3], dtype=np.int32)
        ra, rb = snap_material_ids_at_seam(a, b)
        np.testing.assert_array_equal(ra, rb)
        # A wins on conflict
        assert ra[1] == 2


class TestSafeHeightScale:
    def test_normal_range(self):
        s = safe_height_scale(0.0, 100.0)
        assert s == pytest.approx(0.01)

    def test_zero_range_no_crash_f167(self):
        """F167: flat terrain doesn't divide by zero."""
        s = safe_height_scale(50.0, 50.0)
        assert s > 0
        assert np.isfinite(s)

    def test_normalize_flat_returns_half(self):
        h = np.ones((5, 5)) * 42.0
        n = normalize_height_safe(h, 42.0, 42.0)
        assert np.allclose(n, 0.5)


class TestExportValidation:
    def test_matching_tiles_valid_f168(self):
        """F168: adjacent tiles with matching edges pass validation."""
        h = np.ones((5, 5)) * 10.0
        tiles = {(0, 0): h, (1, 0): h.copy()}
        result = validate_stitched_export(tiles)
        assert result["valid"]
        assert result["total_pairs"] == 1

    def test_mismatched_tiles_invalid(self):
        h_a = np.ones((5, 5)) * 10.0
        h_b = np.ones((5, 5)) * 20.0
        tiles = {(0, 0): h_a, (1, 0): h_b}
        result = validate_stitched_export(tiles)
        assert not result["valid"]
        assert len(result["failed_pairs"]) == 1


class TestResizeHeightmap:
    def test_bilinear_preserves_corners_f169(self):
        """F169: resize uses bilinear, not nearest-neighbor."""
        h = np.array([[0.0, 10.0], [20.0, 30.0]])
        resized = resize_heightmap_bilinear(h, 3)
        assert resized.shape == (3, 3)
        # Corners should be exact
        assert resized[0, 0] == pytest.approx(0.0)
        assert resized[0, 2] == pytest.approx(10.0)
        assert resized[2, 0] == pytest.approx(20.0)
        assert resized[2, 2] == pytest.approx(30.0)
        # Center should be interpolated average
        assert resized[1, 1] == pytest.approx(15.0)

    def test_fast_matches_reference(self):
        h = np.random.RandomState(42).rand(8, 8) * 100
        ref = resize_heightmap_bilinear(h, 16)
        fast = resize_heightmap_bilinear_fast(h, 16)
        np.testing.assert_allclose(ref, fast, atol=1e-10)

    def test_same_size_returns_copy(self):
        h = np.ones((5, 5)) * 42.0
        r = resize_heightmap_bilinear(h, 5)
        np.testing.assert_array_equal(h, r)
        # Must be a copy, not same object
        assert r is not h


class TestRepairSeamHeights:
    def test_east_seam_repaired(self):
        a = np.ones((5, 5)) * 10.0
        b = np.ones((5, 5)) * 20.0
        ra, rb = repair_seam_heights(a, b, "east", blend_width=2)
        # Shared edge should match
        np.testing.assert_allclose(ra[:, -1], rb[:, 0])

    def test_north_seam_repaired(self):
        a = np.ones((5, 5)) * 10.0
        b = np.ones((5, 5)) * 20.0
        ra, rb = repair_seam_heights(a, b, "north", blend_width=2)
        np.testing.assert_allclose(ra[-1, :], rb[0, :])


class TestProtectedZoneSeamIntegrity:
    def test_intact_when_unchanged(self):
        h = np.ones((9, 9)) * 10.0
        mask = compute_guard_band_mask(8, guard_width=2)
        result = validate_protected_zone_seam_integrity(h, mask, h)
        assert result["intact"]

    def test_violation_detected(self):
        orig = np.ones((9, 9)) * 10.0
        modified = orig.copy()
        modified[0, 0] = 99.0  # Modify a guard cell
        mask = compute_guard_band_mask(8, guard_width=2)
        result = validate_protected_zone_seam_integrity(modified, mask, orig)
        assert not result["intact"]
        assert result["violated_count"] > 0


class TestTriplanarContinuity:
    def test_center_is_one(self):
        w = compute_triplanar_continuity_weights(32, blend_width=8)
        assert w[16, 16] == pytest.approx(1.0)

    def test_edge_is_half(self):
        w = compute_triplanar_continuity_weights(32, blend_width=8)
        assert w[0, 16] == pytest.approx(0.5)


# ===================================================================
# Fault line tests
# ===================================================================


class TestFaultLines:
    def test_signed_distance_positive_negative(self):
        fault = FaultLine(
            fault_id="f1", start=(0.0, 5.0), end=(10.0, 5.0),
            displacement=5.0,
        )
        x = np.array([[5.0], [5.0]])
        y = np.array([[3.0], [7.0]])
        dist = signed_distance_to_fault(x, y, fault)
        # One side positive, other negative
        assert dist[0, 0] * dist[1, 0] < 0

    def test_displacement_produces_visible_offset(self):
        h = np.ones((33, 33)) * 50.0
        fault = FaultLine(
            fault_id="f1", start=(0.0, 16.0), end=(32.0, 16.0),
            displacement=10.0, width=8.0, fault_type="normal",
            roughness=0.0,
        )
        delta = compute_fault_displacement(
            h, fault, cell_size=1.0, world_origin_x=0.0, world_origin_y=0.0,
        )
        # Displacement should be non-trivial
        assert np.abs(delta).max() > 1.0
        # Opposite sides of fault should have opposite displacement signs
        assert delta[0, 16] * delta[32, 16] < 0

    def test_rock_hardness_modulates_displacement(self):
        h = np.ones((17, 17)) * 50.0
        fault = FaultLine(
            fault_id="f1", start=(0.0, 8.0), end=(16.0, 8.0),
            displacement=10.0, width=4.0, roughness=0.0,
        )
        delta_soft = compute_fault_displacement(
            h, fault, 1.0, 0.0, 0.0,
            rock_hardness=np.zeros_like(h),  # soft rock
        )
        delta_hard = compute_fault_displacement(
            h, fault, 1.0, 0.0, 0.0,
            rock_hardness=np.ones_like(h),   # hard rock
        )
        # Soft rock should have MORE displacement
        assert np.abs(delta_soft).max() > np.abs(delta_hard).max()

    def test_apply_fault_lines_respects_guard_mask(self):
        h = np.ones((17, 17)) * 50.0
        fault = FaultLine(
            fault_id="f1", start=(0.0, 8.0), end=(16.0, 8.0),
            displacement=10.0, width=4.0, roughness=0.0,
        )
        guard = compute_guard_band_mask(16, guard_width=2)
        result, metrics = apply_fault_lines(
            h, [fault], 1.0, 0.0, 0.0, guard_mask=guard,
        )
        # Guard-band cells should be unchanged
        np.testing.assert_array_equal(result[guard], h[guard])

    def test_generate_random_faults(self):
        faults = generate_random_faults(0.0, 0.0, 100.0, 100.0, count=5, seed=42)
        assert len(faults) == 5
        for f in faults:
            assert f.length > 0
            assert f.displacement > 0


# ===================================================================
# Pipe erosion tests
# ===================================================================


class TestPipeModelErosion:
    def test_produces_erosion_and_deposition(self):
        rng = np.random.RandomState(42)
        h = rng.rand(33, 33) * 100.0
        result = pipe_model_erosion(h, iterations=10, seed=42)
        assert result.height.shape == h.shape
        assert result.erosion_amount.shape == h.shape
        assert result.deposition_amount.shape == h.shape
        assert result.metrics["total_erosion"] > 0

    def test_respects_guard_mask(self):
        rng = np.random.RandomState(42)
        h = rng.rand(17, 17) * 100.0
        guard = compute_guard_band_mask(16, guard_width=3)
        result = pipe_model_erosion(h, iterations=10, guard_mask=guard, seed=42)
        # Guard cells should have zero erosion
        np.testing.assert_array_equal(result.erosion_amount[guard], 0.0)

    def test_water_depth_non_negative(self):
        h = np.random.RandomState(42).rand(17, 17) * 50.0
        result = pipe_model_erosion(h, iterations=20, seed=42)
        assert np.all(result.water_depth >= 0.0)


# ===================================================================
# Poisson blending tests
# ===================================================================


class TestPoissonBlend:
    def test_preserves_base_outside_mask(self):
        base = np.ones((17, 17)) * 10.0
        patch = np.ones((17, 17)) * 50.0
        mask = np.zeros((17, 17), dtype=bool)
        mask[4:13, 4:13] = True
        result = poisson_blend(base, patch, mask, iterations=100)
        # Outside mask: should be base
        assert result[0, 0] == pytest.approx(10.0)

    def test_interior_shifts_toward_patch(self):
        # Use a non-constant patch so the Laplacian guidance field is non-zero
        base = np.zeros((17, 17))
        rng = np.random.RandomState(99)
        patch = 50.0 + rng.rand(17, 17) * 50.0  # Non-constant, 50-100 range
        mask = np.zeros((17, 17), dtype=bool)
        mask[4:13, 4:13] = True
        result = poisson_blend(base, patch, mask, iterations=300)
        # Interior should be shifted significantly above base (which is 0)
        assert result[8, 8] > 5.0

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="Shape"):
            poisson_blend(np.ones((5, 5)), np.ones((3, 3)), np.ones((5, 5), dtype=bool))


class TestPoissonBlendPatch:
    def test_blends_patch_into_base(self):
        base = np.ones((33, 33)) * 10.0
        # Non-constant patch so Laplacian guidance is non-zero
        rng = np.random.RandomState(77)
        patch = 40.0 + rng.rand(9, 9) * 20.0
        result = poisson_blend_patch(base, patch, 12, 12, iterations=200)
        # Center of patch region should differ from base
        assert result[16, 16] != pytest.approx(10.0)
        # Far from patch should be base
        assert result[0, 0] == pytest.approx(10.0)


# ===================================================================
# Integration: adjacent tile edge matching
# ===================================================================


class TestAdjacentTileEdgeMatching:
    """Integration test: verify seam system produces matching tile boundaries."""

    def test_stitched_tiles_match_at_boundary(self):
        """Adjacent tiles have identical height at shared boundary (atol=1e-12)."""
        # Create two tiles with different heights
        tile_a = np.random.RandomState(1).rand(17, 17) * 100.0
        tile_b = np.random.RandomState(2).rand(17, 17) * 100.0

        # Stitch their shared east-west edge
        edge_a = tile_a[:, -1].copy()
        edge_b = tile_b[:, 0].copy()
        new_a, new_b = stitch_shared_edge(edge_a, edge_b)

        tile_a[:, -1] = new_a
        tile_b[:, 0] = new_b

        # Verify exact match
        np.testing.assert_allclose(tile_a[:, -1], tile_b[:, 0], atol=1e-12)

    def test_hero_deltas_fade_to_zero_at_edges(self):
        """Hero deltas produce zero displacement at tile boundaries."""
        tile_size = 32
        base = np.ones((tile_size + 1, tile_size + 1)) * 50.0
        hero_delta = np.ones((tile_size + 1, tile_size + 1)) * 20.0
        fade = compute_edge_fade_weights(tile_size, fade_width=8)
        result = apply_hero_delta_with_fade(base, hero_delta, fade)

        # All edge cells should equal base (delta * 0 = 0)
        np.testing.assert_allclose(result[0, :], base[0, :], atol=1e-12)
        np.testing.assert_allclose(result[-1, :], base[-1, :], atol=1e-12)
        np.testing.assert_allclose(result[:, 0], base[:, 0], atol=1e-12)
        np.testing.assert_allclose(result[:, -1], base[:, -1], atol=1e-12)

    def test_full_pipeline_edge_match(self):
        """Full pipeline: create tiles, apply faults+erosion with guards, stitch, verify."""
        tile_size = 16
        shape = (tile_size + 1, tile_size + 1)

        # Create two adjacent tiles
        rng = np.random.RandomState(42)
        tile_a = rng.rand(*shape) * 100.0
        tile_b = rng.rand(*shape) * 100.0

        # Apply fault line with guard masks
        guard_a = compute_guard_band_mask(tile_size, guard_width=3)
        guard_b = compute_guard_band_mask(tile_size, guard_width=3)

        fault = FaultLine(
            fault_id="test", start=(0.0, 8.0), end=(32.0, 8.0),
            displacement=5.0, width=6.0, roughness=0.0,
        )
        tile_a, _ = apply_fault_lines(
            tile_a, [fault], 1.0, 0.0, 0.0, guard_mask=guard_a,
        )
        tile_b, _ = apply_fault_lines(
            tile_b, [fault], 1.0, float(tile_size), 0.0, guard_mask=guard_b,
        )

        # Stitch shared edge
        new_a, new_b = stitch_shared_edge(tile_a[:, -1], tile_b[:, 0])
        tile_a[:, -1] = new_a
        tile_b[:, 0] = new_b

        # Validate
        result = validate_stitched_export(
            {(0, 0): tile_a, (1, 0): tile_b}, atol=1e-12
        )
        assert result["valid"], f"Edge validation failed: {result}"

    def test_registry_validates_all_edges(self):
        """Registry validates all shared edges after stitching."""
        reg = TerrainNodeRegistry(expected_tile_size=8, expected_cell_size=1.0)

        # 1x2 row of tiles (avoids 4-way corner ambiguity)
        tiles = {}
        for tx in range(2):
            node = TerrainNodeInfo(
                tile_x=tx, tile_y=0, tile_size=8, cell_size=1.0,
                world_origin_x=tx * 8.0, world_origin_y=0.0,
            )
            reg.register(node)
            h = np.ones((9, 9)) * (tx * 10.0 + 5.0)
            tiles[(tx, 0)] = h

        # Stitch shared east edge
        for node_a, node_b, direction in reg.get_shared_edge_pairs():
            ka = node_a.node_key
            kb = node_b.node_key
            if direction == "east":
                ea, eb = stitch_shared_edge(tiles[ka][:, -1], tiles[kb][:, 0])
                tiles[ka][:, -1] = ea
                tiles[kb][:, 0] = eb
            elif direction == "north":
                ea, eb = stitch_shared_edge(tiles[ka][-1, :], tiles[kb][0, :])
                tiles[ka][-1, :] = ea
                tiles[kb][0, :] = eb

        # Cache edge heights and validate
        for (tx, ty), h in tiles.items():
            reg.cache_edge_heights(tx, ty, h)

        results = reg.validate_all_edges(atol=1e-12)
        for r in results:
            assert r["match"], f"Edge mismatch: {r}"
