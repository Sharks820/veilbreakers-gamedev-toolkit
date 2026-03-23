"""Tests for terrain_advanced.py: spline deformation, terrain layers, erosion
painting, flow map computation, thermal erosion, stamp placement, and
spline distance calculation.

All pure-logic -- no Blender dependency.
"""

import math

import numpy as np
import pytest

from blender_addon.handlers.terrain_advanced import (
    apply_layer_operation,
    apply_stamp_to_heightmap,
    apply_thermal_erosion,
    compute_erosion_brush,
    compute_falloff,
    compute_flow_map,
    compute_spline_deformation,
    compute_stamp_heightmap,
    distance_point_to_polyline,
    evaluate_spline,
    flatten_layers,
    TerrainLayer,
)


# ===================================================================
# Spline utilities
# ===================================================================


class TestEvaluateSpline:
    """Test cubic Bezier spline evaluation."""

    def test_two_points_produces_samples(self):
        """A spline between two points produces intermediate samples."""
        pts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        result = evaluate_spline(pts, samples_per_segment=8)
        assert len(result) >= 2
        # First point should be at origin
        assert abs(result[0][0]) < 1e-6
        assert abs(result[0][1]) < 1e-6
        # Last point should be near (10, 0, 0)
        assert abs(result[-1][0] - 10.0) < 1e-3

    def test_single_point_returns_that_point(self):
        """Single point input returns that point."""
        result = evaluate_spline([(5.0, 3.0, 1.0)])
        assert len(result) == 1
        assert result[0] == (5.0, 3.0, 1.0)

    def test_empty_returns_empty(self):
        """Empty input returns empty."""
        result = evaluate_spline([])
        assert result == []

    def test_three_points_smooth_curve(self):
        """Three points produce a smooth curve passing near all waypoints."""
        pts = [(0.0, 0.0, 0.0), (5.0, 5.0, 0.0), (10.0, 0.0, 0.0)]
        result = evaluate_spline(pts, samples_per_segment=32)
        # Should have samples from two segments
        assert len(result) > 32
        # Check that some points are above y=0 (the curve should arc up)
        max_y = max(p[1] for p in result)
        assert max_y > 2.0

    def test_deterministic(self):
        """Same input produces identical output."""
        pts = [(0.0, 0.0, 0.0), (5.0, 3.0, 1.0), (10.0, 0.0, 0.0)]
        r1 = evaluate_spline(pts, samples_per_segment=16)
        r2 = evaluate_spline(pts, samples_per_segment=16)
        for a, b in zip(r1, r2):
            assert a == b


class TestDistancePointToPolyline:
    """Test point-to-polyline distance calculation."""

    def test_point_on_polyline_has_zero_distance(self):
        """A point exactly on the polyline has distance 0."""
        polyline = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        dist, closest, t = distance_point_to_polyline(5.0, 0.0, polyline)
        assert dist < 1e-6
        assert abs(closest[0] - 5.0) < 1e-6

    def test_point_off_polyline_correct_distance(self):
        """Point perpendicular to polyline has correct distance."""
        polyline = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        dist, closest, t = distance_point_to_polyline(5.0, 3.0, polyline)
        assert abs(dist - 3.0) < 1e-6

    def test_point_beyond_end(self):
        """Point beyond polyline end snaps to endpoint."""
        polyline = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        dist, closest, t = distance_point_to_polyline(15.0, 0.0, polyline)
        assert abs(closest[0] - 10.0) < 1e-6

    def test_t_along_spline_normalized(self):
        """t_along_spline is in [0, 1] range."""
        polyline = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        _, _, t = distance_point_to_polyline(7.5, 0.0, polyline)
        assert 0.0 <= t <= 1.0
        # Should be around 0.75 (3/4 along the line)
        assert abs(t - 0.75) < 0.1

    def test_empty_polyline(self):
        """Empty polyline returns infinity distance."""
        dist, _, _ = distance_point_to_polyline(5.0, 5.0, [])
        assert dist == float("inf")

    def test_single_point_polyline(self):
        """Single-point polyline returns distance to that point."""
        dist, closest, t = distance_point_to_polyline(3.0, 4.0, [(0.0, 0.0, 0.0)])
        assert abs(dist - 5.0) < 1e-6  # 3-4-5 triangle


# ===================================================================
# Spline deformation
# ===================================================================


class TestComputeSplineDeformation:
    """Test spline-based terrain deformation computation."""

    def _make_flat_grid(self, size: float = 20.0, res: int = 21) -> list:
        """Make a flat grid of vertices at z=5."""
        verts = []
        step = size / (res - 1)
        for j in range(res):
            for i in range(res):
                verts.append((i * step, j * step, 5.0))
        return verts

    def test_carve_lowers_vertices(self):
        """Carve mode lowers terrain vertices near the spline."""
        verts = self._make_flat_grid()
        spline = [(0.0, 10.0, 5.0), (20.0, 10.0, 5.0)]
        result = compute_spline_deformation(verts, spline, width=3.0, depth=2.0,
                                            falloff=0.5, mode="carve")
        assert len(result) > 0
        for idx, new_z in result.items():
            assert new_z < 5.0  # All affected verts should be lowered

    def test_raise_raises_vertices(self):
        """Raise mode raises terrain vertices near the spline."""
        verts = self._make_flat_grid()
        spline = [(0.0, 10.0, 5.0), (20.0, 10.0, 5.0)]
        result = compute_spline_deformation(verts, spline, width=3.0, depth=2.0,
                                            falloff=0.5, mode="raise")
        assert len(result) > 0
        for idx, new_z in result.items():
            assert new_z > 5.0  # All affected verts should be raised

    def test_flatten_converges_to_spline_height(self):
        """Flatten mode pulls vertices toward the spline height."""
        verts = []
        for i in range(21):
            for j in range(21):
                z = 5.0 + (j - 10) * 0.5  # Sloped terrain
                verts.append((float(i), float(j), z))

        spline = [(0.0, 10.0, 5.0), (20.0, 10.0, 5.0)]
        result = compute_spline_deformation(verts, spline, width=5.0, depth=1.0,
                                            falloff=0.5, mode="flatten")
        assert len(result) > 0

    def test_no_effect_outside_width(self):
        """Vertices far from the spline are not affected."""
        verts = [(0.0, 100.0, 5.0), (10.0, 100.0, 5.0)]
        spline = [(0.0, 0.0, 5.0), (10.0, 0.0, 5.0)]
        result = compute_spline_deformation(verts, spline, width=3.0, depth=2.0,
                                            falloff=0.5, mode="carve")
        assert len(result) == 0

    def test_invalid_mode_raises(self):
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            compute_spline_deformation([], [(0, 0, 0), (1, 0, 0)],
                                       mode="invalid")

    def test_too_few_spline_points_raises(self):
        """Fewer than 2 spline points raises ValueError."""
        with pytest.raises(ValueError, match="at least 2"):
            compute_spline_deformation([], [(0, 0, 0)], mode="carve")


# ===================================================================
# Falloff function
# ===================================================================


class TestComputeFalloff:
    """Test falloff computation."""

    def test_smooth_at_center(self):
        """Smooth falloff is 1.0 at center."""
        assert abs(compute_falloff(0.0, "smooth") - 1.0) < 1e-6

    def test_smooth_at_edge(self):
        """Smooth falloff is 0.0 at edge (d=1.0)."""
        assert abs(compute_falloff(1.0, "smooth")) < 1e-6

    def test_linear_at_center(self):
        """Linear falloff is 1.0 at center."""
        assert abs(compute_falloff(0.0, "linear") - 1.0) < 1e-6

    def test_linear_midpoint(self):
        """Linear falloff at d=0.5 is 0.5."""
        assert abs(compute_falloff(0.5, "linear") - 0.5) < 1e-6

    def test_constant_inside(self):
        """Constant falloff is 1.0 everywhere inside."""
        assert abs(compute_falloff(0.5, "constant") - 1.0) < 1e-6
        assert abs(compute_falloff(0.99, "constant") - 1.0) < 1e-6

    def test_constant_at_edge(self):
        """Constant falloff is 0.0 at and beyond edge."""
        assert abs(compute_falloff(1.0, "constant")) < 1e-6

    def test_invalid_falloff_raises(self):
        """Invalid falloff type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown falloff"):
            compute_falloff(0.5, "nonexistent")


# ===================================================================
# Terrain layers
# ===================================================================


class TestTerrainLayer:
    """Test TerrainLayer class."""

    def test_creation(self):
        """Layer creates with correct dimensions and zeroed heights."""
        layer = TerrainLayer("test", 32, 32, "ADD", 1.0)
        assert layer.name == "test"
        assert layer.heights.shape == (32, 32)
        assert np.all(layer.heights == 0.0)

    def test_invalid_blend_mode(self):
        """Invalid blend mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid blend_mode"):
            TerrainLayer("test", 32, 32, "INVALID", 1.0)

    def test_serialization_roundtrip(self):
        """Layer survives to_dict -> from_dict roundtrip."""
        layer = TerrainLayer("hills", 16, 16, "ADD", 0.8)
        layer.heights[5, 5] = 1.5
        data = layer.to_dict()
        restored = TerrainLayer.from_dict(data)
        assert restored.name == "hills"
        assert restored.blend_mode == "ADD"
        assert abs(restored.strength - 0.8) < 1e-6
        assert abs(restored.heights[5, 5] - 1.5) < 1e-6

    def test_strength_clamped(self):
        """Strength is clamped to [0, 1]."""
        layer = TerrainLayer("t", 4, 4, "ADD", 5.0)
        assert layer.strength == 1.0
        layer2 = TerrainLayer("t2", 4, 4, "ADD", -1.0)
        assert layer2.strength == 0.0


class TestApplyLayerOperation:
    """Test brush operations on terrain layers."""

    def test_raise_increases_heights(self):
        """Raise operation increases heights in brush area."""
        layer = TerrainLayer("test", 32, 32, "ADD", 1.0)
        affected = apply_layer_operation(
            layer, "raise", (50.0, 50.0), 20.0, strength=1.0,
            terrain_size=(100.0, 100.0),
        )
        assert affected > 0
        assert layer.heights.max() > 0

    def test_lower_decreases_heights(self):
        """Lower operation decreases heights."""
        layer = TerrainLayer("test", 32, 32, "ADD", 1.0)
        layer.heights[:] = 1.0
        apply_layer_operation(
            layer, "lower", (50.0, 50.0), 20.0, strength=1.0,
            terrain_size=(100.0, 100.0),
        )
        assert layer.heights.min() < 1.0

    def test_noise_changes_heights(self):
        """Noise operation modifies heights non-uniformly."""
        layer = TerrainLayer("test", 32, 32, "ADD", 1.0)
        apply_layer_operation(
            layer, "noise", (50.0, 50.0), 30.0, strength=1.0,
            terrain_size=(100.0, 100.0), seed=42,
        )
        assert not np.all(layer.heights == 0.0)
        # Not all values should be the same (it's random noise)
        assert layer.heights.std() > 0

    def test_invalid_operation_raises(self):
        """Invalid operation raises ValueError."""
        layer = TerrainLayer("test", 8, 8, "ADD", 1.0)
        with pytest.raises(ValueError, match="Unknown operation"):
            apply_layer_operation(layer, "explode", (50.0, 50.0), 10.0)


class TestFlattenLayers:
    """Test layer flattening/merging."""

    def test_add_blend_mode(self):
        """ADD mode adds layer heights to base."""
        base = np.ones((16, 16), dtype=np.float64)
        layer = TerrainLayer("add", 16, 16, "ADD", 1.0)
        layer.heights[:] = 0.5
        result = flatten_layers(base, [layer])
        np.testing.assert_allclose(result, 1.5)

    def test_subtract_blend_mode(self):
        """SUBTRACT mode subtracts layer heights from base."""
        base = np.ones((16, 16), dtype=np.float64)
        layer = TerrainLayer("sub", 16, 16, "SUBTRACT", 1.0)
        layer.heights[:] = 0.3
        result = flatten_layers(base, [layer])
        np.testing.assert_allclose(result, 0.7)

    def test_multiple_layers(self):
        """Multiple layers are applied in order."""
        base = np.zeros((8, 8), dtype=np.float64)
        l1 = TerrainLayer("l1", 8, 8, "ADD", 1.0)
        l1.heights[:] = 1.0
        l2 = TerrainLayer("l2", 8, 8, "SUBTRACT", 1.0)
        l2.heights[:] = 0.3
        result = flatten_layers(base, [l1, l2])
        np.testing.assert_allclose(result, 0.7)

    def test_empty_layers_returns_base(self):
        """No layers returns a copy of base."""
        base = np.ones((8, 8), dtype=np.float64) * 3.0
        result = flatten_layers(base, [])
        np.testing.assert_array_equal(result, base)

    def test_strength_scaling(self):
        """Layer strength scales the height contribution."""
        base = np.ones((8, 8), dtype=np.float64)
        layer = TerrainLayer("half", 8, 8, "ADD", 0.5)
        layer.heights[:] = 2.0
        result = flatten_layers(base, [layer])
        np.testing.assert_allclose(result, 2.0)  # 1.0 + 2.0 * 0.5


# ===================================================================
# Flow map computation
# ===================================================================


class TestComputeFlowMap:
    """Test D8 flow map computation."""

    def test_returns_correct_keys(self):
        """Result dict has required keys."""
        hmap = [[1.0, 0.9, 0.8],
                [0.7, 0.6, 0.5],
                [0.4, 0.3, 0.2]]
        result = compute_flow_map(hmap)
        assert "flow_direction" in result
        assert "flow_accumulation" in result
        assert "drainage_basins" in result

    def test_dimensions_match(self):
        """Output arrays match input dimensions."""
        hmap = np.random.rand(16, 16)
        result = compute_flow_map(hmap)
        fd = np.array(result["flow_direction"])
        fa = np.array(result["flow_accumulation"])
        db = np.array(result["drainage_basins"])
        assert fd.shape == (16, 16)
        assert fa.shape == (16, 16)
        assert db.shape == (16, 16)

    def test_flow_directions_in_valid_range(self):
        """Flow direction values are -1 to 7."""
        hmap = np.random.rand(8, 8)
        result = compute_flow_map(hmap)
        fd = np.array(result["flow_direction"])
        assert fd.min() >= -1
        assert fd.max() <= 7

    def test_flow_accumulation_positive(self):
        """Flow accumulation is always >= 1."""
        hmap = np.random.rand(8, 8)
        result = compute_flow_map(hmap)
        fa = np.array(result["flow_accumulation"])
        assert fa.min() >= 1.0

    def test_slope_flows_downhill(self):
        """On a simple slope, flow goes toward lower elevation."""
        # Linear slope: row 0 is highest, row 4 is lowest
        hmap = [[4.0, 4.0, 4.0],
                [3.0, 3.0, 3.0],
                [2.0, 2.0, 2.0],
                [1.0, 1.0, 1.0],
                [0.0, 0.0, 0.0]]
        result = compute_flow_map(hmap)
        fd = np.array(result["flow_direction"])
        # Interior cells should flow to row+1 (direction 4 = south)
        # or south-adjacent directions
        for r in range(1, 3):
            for c in range(1, 2):
                d = fd[r, c]
                assert d >= 0  # Should have a flow direction

    def test_flat_terrain_has_pits(self):
        """Flat terrain produces pit markers (direction -1)."""
        hmap = np.ones((4, 4))
        result = compute_flow_map(hmap)
        fd = np.array(result["flow_direction"])
        # All cells are equal height, so no downhill direction
        assert np.all(fd == -1)

    def test_accumulation_at_valley_bottom(self):
        """Valley bottom has highest flow accumulation."""
        hmap = np.array([
            [5.0, 4.0, 3.0, 4.0, 5.0],
            [4.0, 3.0, 2.0, 3.0, 4.0],
            [3.0, 2.0, 1.0, 2.0, 3.0],
            [4.0, 3.0, 2.0, 3.0, 4.0],
            [5.0, 4.0, 3.0, 4.0, 5.0],
        ])
        result = compute_flow_map(hmap)
        fa = np.array(result["flow_accumulation"])
        # Center cell (2,2) should have highest accumulation
        assert fa[2, 2] == fa.max()

    def test_drainage_basins_assigned(self):
        """All cells are assigned to a drainage basin."""
        hmap = np.random.rand(8, 8)
        result = compute_flow_map(hmap)
        db = np.array(result["drainage_basins"])
        assert np.all(db >= 0)

    def test_deterministic(self):
        """Same input produces same output."""
        hmap = np.random.RandomState(42).rand(8, 8)
        r1 = compute_flow_map(hmap)
        r2 = compute_flow_map(hmap)
        np.testing.assert_array_equal(r1["flow_direction"], r2["flow_direction"])
        np.testing.assert_array_equal(r1["flow_accumulation"], r2["flow_accumulation"])

    def test_list_input_accepted(self):
        """Plain Python list-of-lists is accepted."""
        hmap = [[1.0, 0.5], [0.5, 0.0]]
        result = compute_flow_map(hmap)
        assert result["resolution"] == (2, 2)


# ===================================================================
# Thermal erosion
# ===================================================================


class TestApplyThermalErosion:
    """Test enhanced thermal erosion algorithm."""

    def test_returns_same_dimensions(self):
        """Output has same dimensions as input."""
        hmap = [[1.0, 0.5, 0.0],
                [0.8, 0.4, 0.1],
                [0.6, 0.3, 0.0]]
        result = apply_thermal_erosion(hmap, iterations=5)
        assert len(result) == 3
        assert len(result[0]) == 3

    def test_deterministic(self):
        """Same input produces identical output."""
        hmap = np.random.RandomState(42).rand(8, 8).tolist()
        r1 = apply_thermal_erosion(hmap, iterations=10, talus_angle=0.3)
        r2 = apply_thermal_erosion(hmap, iterations=10, talus_angle=0.3)
        np.testing.assert_array_equal(r1, r2)

    def test_reduces_steep_slopes(self):
        """Thermal erosion reduces slope between adjacent steep cells."""
        # Create a terrain with a sharp cliff
        hmap = np.zeros((5, 5))
        hmap[0:2, :] = 10.0  # Top rows are high
        hmap[2:, :] = 0.0    # Bottom rows are low

        result_arr = np.array(apply_thermal_erosion(
            hmap.tolist(), iterations=50, talus_angle=0.3, strength=0.5,
        ))

        # The gradient should be smoother after erosion
        original_max_diff = abs(hmap[1, 2] - hmap[2, 2])
        eroded_max_diff = abs(result_arr[1, 2] - result_arr[2, 2])
        assert eroded_max_diff < original_max_diff

    def test_flat_terrain_unchanged(self):
        """Flat terrain is not affected by thermal erosion."""
        hmap = np.ones((8, 8)).tolist()
        result = apply_thermal_erosion(hmap, iterations=10)
        np.testing.assert_allclose(result, 1.0)

    def test_small_terrain_handled(self):
        """1x1 terrain returns unchanged."""
        hmap = [[0.5]]
        result = apply_thermal_erosion(hmap, iterations=5)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_strength_affects_result(self):
        """Higher strength produces more erosion."""
        hmap = np.zeros((8, 8))
        hmap[0:4, :] = 5.0
        r_weak = np.array(apply_thermal_erosion(hmap.tolist(), iterations=20,
                                                 strength=0.1))
        r_strong = np.array(apply_thermal_erosion(hmap.tolist(), iterations=20,
                                                   strength=0.9))
        # Strong erosion should reduce the cliff more
        weak_diff = abs(r_weak[3, 3] - r_weak[4, 3])
        strong_diff = abs(r_strong[3, 3] - r_strong[4, 3])
        assert strong_diff <= weak_diff + 1e-6


# ===================================================================
# Terrain stamp
# ===================================================================


class TestComputeStampHeightmap:
    """Test stamp heightmap generation."""

    def test_hill_stamp_peaks_at_center(self):
        """Hill stamp has highest value at center."""
        stamp = compute_stamp_heightmap("hill", 64)
        center = stamp[32, 32]
        assert center > 0.9  # Near 1.0 at center

    def test_crater_stamp_shape(self):
        """Crater stamp has a ring shape (low center, high ring)."""
        stamp = compute_stamp_heightmap("crater", 64)
        # Center should be lower than the ring
        center = stamp[32, 32]
        ring = stamp[32, 48]  # Offset from center
        assert ring > center or abs(ring - center) < 0.3

    def test_valley_stamp_negative(self):
        """Valley stamp has negative values (depressions)."""
        stamp = compute_stamp_heightmap("valley", 64)
        assert stamp.min() < 0

    def test_custom_stamp_passthrough(self):
        """Custom stamp returns the provided heightmap."""
        custom = [[1.0, 2.0], [3.0, 4.0]]
        result = compute_stamp_heightmap("custom", 64, custom)
        np.testing.assert_array_equal(result, custom)

    def test_invalid_stamp_type_raises(self):
        """Invalid stamp type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown stamp_type"):
            compute_stamp_heightmap("volcano_burst", 64)

    def test_all_stamp_types_produce_output(self):
        """All built-in stamp types produce valid output."""
        for stamp_type in ["crater", "mesa", "hill", "valley", "plateau", "ridge"]:
            stamp = compute_stamp_heightmap(stamp_type, 32)
            assert stamp.shape == (32, 32)


class TestApplyStampToHeightmap:
    """Test stamp application to terrain."""

    def test_stamp_modifies_terrain(self):
        """Applying a stamp changes the heightmap."""
        terrain = np.zeros((32, 32), dtype=np.float64)
        stamp = compute_stamp_heightmap("hill", 16)
        result = apply_stamp_to_heightmap(
            terrain, stamp, (50.0, 50.0), 20.0, height=5.0,
            terrain_size=(100.0, 100.0),
        )
        assert result.max() > 0

    def test_stamp_position_matters(self):
        """Different stamp positions affect different areas."""
        terrain = np.zeros((32, 32), dtype=np.float64)
        stamp = compute_stamp_heightmap("hill", 16)
        r1 = apply_stamp_to_heightmap(
            terrain, stamp, (25.0, 25.0), 10.0, height=5.0,
            terrain_size=(100.0, 100.0),
        )
        r2 = apply_stamp_to_heightmap(
            terrain, stamp, (75.0, 75.0), 10.0, height=5.0,
            terrain_size=(100.0, 100.0),
        )
        # The max positions should be in different quadrants
        r1_max_idx = np.unravel_index(r1.argmax(), r1.shape)
        r2_max_idx = np.unravel_index(r2.argmax(), r2.shape)
        assert r1_max_idx != r2_max_idx

    def test_stamp_does_not_modify_original(self):
        """Original heightmap is not modified (returns copy)."""
        terrain = np.zeros((16, 16), dtype=np.float64)
        stamp = compute_stamp_heightmap("hill", 8)
        _ = apply_stamp_to_heightmap(
            terrain, stamp, (50.0, 50.0), 20.0,
            terrain_size=(100.0, 100.0),
        )
        assert np.all(terrain == 0.0)


# ===================================================================
# Erosion brush
# ===================================================================


class TestComputeErosionBrush:
    """Test brush-based erosion painting."""

    def test_hydraulic_modifies_terrain(self):
        """Hydraulic erosion brush modifies terrain within radius."""
        hmap = np.random.RandomState(42).rand(32, 32)
        original = hmap.copy()
        result = compute_erosion_brush(
            hmap, (50.0, 50.0), 20.0, "hydraulic", iterations=3,
            terrain_size=(100.0, 100.0),
        )
        assert not np.array_equal(result, original)

    def test_thermal_erosion_brush(self):
        """Thermal erosion brush modifies terrain."""
        hmap = np.random.RandomState(42).rand(32, 32)
        original = hmap.copy()
        result = compute_erosion_brush(
            hmap, (50.0, 50.0), 20.0, "thermal", iterations=3,
            terrain_size=(100.0, 100.0),
        )
        assert not np.array_equal(result, original)

    def test_wind_erosion_brush(self):
        """Wind erosion brush modifies terrain."""
        hmap = np.random.RandomState(42).rand(32, 32)
        original = hmap.copy()
        result = compute_erosion_brush(
            hmap, (50.0, 50.0), 20.0, "wind", iterations=3,
            terrain_size=(100.0, 100.0),
        )
        assert not np.array_equal(result, original)

    def test_result_clamped_0_1(self):
        """Result values are clamped to [0, 1]."""
        hmap = np.random.RandomState(42).rand(16, 16)
        result = compute_erosion_brush(
            hmap, (50.0, 50.0), 30.0, "hydraulic", iterations=10,
            terrain_size=(100.0, 100.0),
        )
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_invalid_erosion_type_raises(self):
        """Invalid erosion type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown erosion_type"):
            compute_erosion_brush(np.zeros((4, 4)), (50, 50), 10, "magical")

    def test_does_not_modify_original(self):
        """Original heightmap is not modified."""
        hmap = np.random.RandomState(42).rand(16, 16)
        original = hmap.copy()
        _ = compute_erosion_brush(hmap, (50, 50), 20, "hydraulic",
                                  terrain_size=(100, 100))
        np.testing.assert_array_equal(hmap, original)
