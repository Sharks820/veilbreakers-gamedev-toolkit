"""Tests for precision mesh editing tools (GAP-01 through GAP-05, GAP-09).

Tests pure-logic helpers that do NOT require bpy/Blender:
  - Position-based selection (box, sphere, plane)  [GAP-01]
  - Edit operation validation for new operations    [GAP-02/03/04/05]
  - Terrain sculpt brush math and falloff curves    [GAP-09]
"""

import math

import pytest


# ===========================================================================
# GAP-01: Position-Based Selection
# ===========================================================================


class TestSelectByBox:
    """Test bounding box vertex selection."""

    def test_all_inside(self):
        from blender_addon.handlers.mesh import _select_by_box

        verts = [(0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5)]
        result = _select_by_box(verts, (-1, -1, -1), (2, 2, 2))
        assert result == [0, 1, 2]

    def test_none_inside(self):
        from blender_addon.handlers.mesh import _select_by_box

        verts = [(5, 5, 5), (6, 6, 6)]
        result = _select_by_box(verts, (0, 0, 0), (1, 1, 1))
        assert result == []

    def test_partial_selection(self):
        from blender_addon.handlers.mesh import _select_by_box

        verts = [(0.5, 0.5, 0.5), (2, 2, 2), (0, 0, 0)]
        result = _select_by_box(verts, (0, 0, 0), (1, 1, 1))
        assert result == [0, 2]

    def test_on_boundary_included(self):
        """Vertices exactly on the box boundary should be included."""
        from blender_addon.handlers.mesh import _select_by_box

        verts = [(1, 1, 1), (0, 0, 0)]
        result = _select_by_box(verts, (0, 0, 0), (1, 1, 1))
        assert result == [0, 1]

    def test_empty_verts(self):
        from blender_addon.handlers.mesh import _select_by_box

        result = _select_by_box([], (0, 0, 0), (1, 1, 1))
        assert result == []

    def test_negative_coordinates(self):
        from blender_addon.handlers.mesh import _select_by_box

        verts = [(-0.5, -0.5, -0.5), (0, 0, 0), (-2, -2, -2)]
        result = _select_by_box(verts, (-1, -1, -1), (0, 0, 0))
        assert result == [0, 1]

    def test_flat_box_z(self):
        """A flat box (zero height) should still select vertices at that Z."""
        from blender_addon.handlers.mesh import _select_by_box

        verts = [(0, 0, 0), (0, 0, 1), (0, 0, -1)]
        result = _select_by_box(verts, (-1, -1, 0), (1, 1, 0))
        assert result == [0]


class TestSelectBySphere:
    """Test sphere-based vertex selection."""

    def test_all_inside(self):
        from blender_addon.handlers.mesh import _select_by_sphere

        verts = [(0, 0, 0), (0.1, 0.1, 0.1)]
        result = _select_by_sphere(verts, (0, 0, 0), 1.0)
        assert result == [0, 1]

    def test_none_inside(self):
        from blender_addon.handlers.mesh import _select_by_sphere

        verts = [(5, 5, 5)]
        result = _select_by_sphere(verts, (0, 0, 0), 1.0)
        assert result == []

    def test_on_boundary_included(self):
        """Vertex exactly on the sphere surface should be included."""
        from blender_addon.handlers.mesh import _select_by_sphere

        verts = [(1, 0, 0)]
        result = _select_by_sphere(verts, (0, 0, 0), 1.0)
        assert result == [0]

    def test_just_outside(self):
        from blender_addon.handlers.mesh import _select_by_sphere

        # sqrt(3) ~ 1.732, which is > 1.0
        verts = [(1, 1, 1)]
        result = _select_by_sphere(verts, (0, 0, 0), 1.0)
        assert result == []

    def test_offset_center(self):
        from blender_addon.handlers.mesh import _select_by_sphere

        verts = [(10, 10, 10), (10.5, 10, 10), (20, 20, 20)]
        result = _select_by_sphere(verts, (10, 10, 10), 1.0)
        assert result == [0, 1]

    def test_zero_radius(self):
        from blender_addon.handlers.mesh import _select_by_sphere

        # Only vertex at exact center should match
        verts = [(0, 0, 0), (0.001, 0, 0)]
        result = _select_by_sphere(verts, (0, 0, 0), 0.0)
        assert result == [0]

    def test_large_radius(self):
        from blender_addon.handlers.mesh import _select_by_sphere

        verts = [(i, 0, 0) for i in range(100)]
        result = _select_by_sphere(verts, (50, 0, 0), 1000.0)
        assert len(result) == 100


class TestSelectByPlane:
    """Test plane-based vertex selection."""

    def test_above_z_plane(self):
        from blender_addon.handlers.mesh import _select_by_plane

        verts = [(0, 0, 1), (0, 0, -1), (0, 0, 0)]
        result = _select_by_plane(verts, (0, 0, 0), (0, 0, 1), "above")
        # z=1 and z=0 are >= 0 (on or above plane)
        assert 0 in result  # z=1
        assert 2 in result  # z=0 (on plane)
        assert 1 not in result  # z=-1

    def test_below_z_plane(self):
        from blender_addon.handlers.mesh import _select_by_plane

        verts = [(0, 0, 1), (0, 0, -1), (0, 0, 0)]
        result = _select_by_plane(verts, (0, 0, 0), (0, 0, 1), "below")
        assert result == [1]  # only z=-1

    def test_diagonal_plane(self):
        from blender_addon.handlers.mesh import _select_by_plane

        # Plane through origin with normal (1, 1, 0)
        verts = [(1, 1, 0), (-1, -1, 0), (0, 0, 0)]
        result = _select_by_plane(verts, (0, 0, 0), (1, 1, 0), "above")
        assert 0 in result  # dot > 0
        assert 2 in result  # dot == 0

    def test_offset_plane(self):
        from blender_addon.handlers.mesh import _select_by_plane

        # Plane at z=5 with normal pointing up
        verts = [(0, 0, 6), (0, 0, 4), (0, 0, 5)]
        result = _select_by_plane(verts, (0, 0, 5), (0, 0, 1), "above")
        assert 0 in result  # z=6
        assert 2 in result  # z=5 (on plane)
        assert 1 not in result  # z=4

    def test_zero_normal_returns_empty(self):
        from blender_addon.handlers.mesh import _select_by_plane

        verts = [(0, 0, 0)]
        result = _select_by_plane(verts, (0, 0, 0), (0, 0, 0), "above")
        assert result == []

    def test_unnormalized_normal(self):
        """Non-unit normal should still work (gets normalized internally)."""
        from blender_addon.handlers.mesh import _select_by_plane

        verts = [(0, 0, 10), (0, 0, -10)]
        # Normal (0, 0, 100) should behave same as (0, 0, 1)
        result = _select_by_plane(verts, (0, 0, 0), (0, 0, 100), "above")
        assert 0 in result
        assert 1 not in result


class TestSelectionCriteriaWithPositions:
    """Test that position criteria are recognized by _parse_selection_criteria."""

    def test_position_box_criteria(self):
        from blender_addon.handlers.mesh import _parse_selection_criteria

        box = {"min": [0, 0, 0], "max": [1, 1, 1]}
        criteria = _parse_selection_criteria({"position_box": box})
        assert criteria["position_box"] == box

    def test_position_sphere_criteria(self):
        from blender_addon.handlers.mesh import _parse_selection_criteria

        sphere = {"center": [0, 0, 0], "radius": 5.0}
        criteria = _parse_selection_criteria({"position_sphere": sphere})
        assert criteria["position_sphere"] == sphere

    def test_position_plane_criteria(self):
        from blender_addon.handlers.mesh import _parse_selection_criteria

        plane = {"point": [0, 0, 0], "normal": [0, 0, 1]}
        criteria = _parse_selection_criteria({"position_plane": plane})
        assert criteria["position_plane"] == plane

    def test_mixed_criteria(self):
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({
            "material_index": 2,
            "position_box": {"min": [0, 0, 0], "max": [1, 1, 1]},
        })
        assert "material_index" in criteria
        assert "position_box" in criteria


# ===========================================================================
# GAP-02/03/04/05: Extended Edit Operations Validation
# ===========================================================================


class TestExtendedEditOperations:
    """Test that new edit operations are accepted by validation."""

    def test_move_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("move")

    def test_rotate_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("rotate")

    def test_scale_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("scale")

    def test_loop_cut_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("loop_cut")

    def test_bevel_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("bevel")

    def test_merge_vertices_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("merge_vertices")

    def test_dissolve_edges_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("dissolve_edges")

    def test_dissolve_faces_accepted(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        _validate_edit_operation("dissolve_faces")

    def test_original_operations_still_work(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        for op in ("extrude", "inset", "mirror", "separate", "join"):
            _validate_edit_operation(op)

    def test_invalid_still_rejected(self):
        from blender_addon.handlers.mesh import _validate_edit_operation

        with pytest.raises(ValueError, match="Unknown edit operation"):
            _validate_edit_operation("twist")


# ===========================================================================
# GAP-09: Terrain Sculpting Pure Logic
# ===========================================================================


class TestFalloffFunctions:
    """Test terrain brush falloff curves."""

    def test_smooth_at_center(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        # At center (distance=0), smooth falloff should be 1.0
        assert get_falloff_value(0.0, "smooth") == pytest.approx(1.0)

    def test_smooth_at_edge(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        # At edge (distance=1), smooth falloff should be 0.0
        assert get_falloff_value(1.0, "smooth") == pytest.approx(0.0)

    def test_smooth_at_midpoint(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        # At midpoint, smooth should be 0.5
        val = get_falloff_value(0.5, "smooth")
        assert val == pytest.approx(0.5, abs=0.01)

    def test_sharp_at_center(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(0.0, "sharp") == pytest.approx(1.0)

    def test_sharp_at_edge(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(1.0, "sharp") == pytest.approx(0.0)

    def test_linear_at_center(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(0.0, "linear") == pytest.approx(1.0)

    def test_linear_at_edge(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(1.0, "linear") == pytest.approx(0.0)

    def test_linear_at_midpoint(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(0.5, "linear") == pytest.approx(0.5)

    def test_constant_inside(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(0.0, "constant") == 1.0
        assert get_falloff_value(0.5, "constant") == 1.0
        assert get_falloff_value(0.99, "constant") == 1.0

    def test_constant_at_edge(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        assert get_falloff_value(1.0, "constant") == 0.0

    def test_outside_brush(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        for falloff in ("smooth", "sharp", "linear", "constant"):
            assert get_falloff_value(1.5, falloff) == 0.0

    def test_unknown_falloff_raises(self):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        with pytest.raises(ValueError, match="Unknown falloff"):
            get_falloff_value(0.5, "quadratic")


class TestComputeBrushWeights:
    """Test brush weight computation for terrain sculpting."""

    def test_center_vertex_gets_full_weight(self):
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        verts = [(0, 0)]
        result = compute_brush_weights(verts, (0, 0), 5.0, "constant")
        assert len(result) == 1
        assert result[0] == (0, 1.0)

    def test_outside_radius_excluded(self):
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        verts = [(100, 100)]
        result = compute_brush_weights(verts, (0, 0), 5.0, "smooth")
        assert result == []

    def test_zero_radius_empty(self):
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        verts = [(0, 0)]
        result = compute_brush_weights(verts, (0, 0), 0.0, "smooth")
        assert result == []

    def test_multiple_verts_distances(self):
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        verts = [(0, 0), (5, 0), (10, 0)]
        result = compute_brush_weights(verts, (0, 0), 6.0, "linear")
        # Vertex 0 at distance 0 -> weight 1.0
        # Vertex 1 at distance 5 -> weight ~0.167
        # Vertex 2 at distance 10 -> outside
        assert len(result) == 2
        assert result[0][0] == 0
        assert result[0][1] == pytest.approx(1.0)
        assert result[1][0] == 1
        assert result[1][1] == pytest.approx(1.0 - 5.0 / 6.0, abs=0.01)

    def test_offset_center(self):
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        verts = [(10, 10), (10, 11)]
        result = compute_brush_weights(verts, (10, 10), 5.0, "constant")
        assert len(result) == 2

    def test_xy_only(self):
        """Z is not part of 2D distance calculation."""
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        # Only XY coords matter
        verts = [(0, 0), (100, 0)]
        result = compute_brush_weights(verts, (0, 0), 1.0, "constant")
        assert len(result) == 1


class TestRaiseDisplacements:
    """Test the raise operation displacement calculation."""

    def test_basic_raise(self):
        from blender_addon.handlers.terrain_sculpt import compute_raise_displacements

        heights = [0.0, 0.0, 0.0]
        weights = [(0, 1.0), (1, 0.5)]
        result = compute_raise_displacements(heights, weights, 2.0)
        assert result[0] == pytest.approx(2.0)
        assert result[1] == pytest.approx(1.0)
        assert 2 not in result

    def test_raise_from_nonzero(self):
        from blender_addon.handlers.terrain_sculpt import compute_raise_displacements

        heights = [5.0]
        weights = [(0, 1.0)]
        result = compute_raise_displacements(heights, weights, 3.0)
        assert result[0] == pytest.approx(8.0)

    def test_empty_weights(self):
        from blender_addon.handlers.terrain_sculpt import compute_raise_displacements

        result = compute_raise_displacements([0.0], [], 1.0)
        assert result == {}


class TestLowerDisplacements:
    """Test the lower operation displacement calculation."""

    def test_basic_lower(self):
        from blender_addon.handlers.terrain_sculpt import compute_lower_displacements

        heights = [10.0, 10.0]
        weights = [(0, 1.0), (1, 0.5)]
        result = compute_lower_displacements(heights, weights, 2.0)
        assert result[0] == pytest.approx(8.0)
        assert result[1] == pytest.approx(9.0)

    def test_lower_below_zero(self):
        from blender_addon.handlers.terrain_sculpt import compute_lower_displacements

        heights = [1.0]
        weights = [(0, 1.0)]
        result = compute_lower_displacements(heights, weights, 5.0)
        assert result[0] == pytest.approx(-4.0)


class TestSmoothDisplacements:
    """Test the smooth operation (Laplacian Z-only)."""

    def test_smooth_spike(self):
        """A vertex higher than its neighbors should move toward their average."""
        from blender_addon.handlers.terrain_sculpt import compute_smooth_displacements

        positions = [
            (0, 0, 10),   # spike at center
            (1, 0, 0),    # neighbor
            (-1, 0, 0),   # neighbor
            (0, 1, 0),    # neighbor
            (0, -1, 0),   # neighbor
        ]
        adjacency = {0: [1, 2, 3, 4]}
        weights = [(0, 1.0)]
        result = compute_smooth_displacements(positions, adjacency, weights)
        # Average of neighbors = 0.0, weight = 1.0
        # new_z = 10 + (0 - 10) * 1.0 = 0.0
        assert result[0] == pytest.approx(0.0)

    def test_smooth_partial_weight(self):
        from blender_addon.handlers.terrain_sculpt import compute_smooth_displacements

        positions = [(0, 0, 10), (1, 0, 0), (-1, 0, 0)]
        adjacency = {0: [1, 2]}
        weights = [(0, 0.5)]
        result = compute_smooth_displacements(positions, adjacency, weights)
        # avg_z = 0.0, w = 0.5
        # new_z = 10 + (0 - 10) * 0.5 = 5.0
        assert result[0] == pytest.approx(5.0)

    def test_smooth_no_neighbors(self):
        from blender_addon.handlers.terrain_sculpt import compute_smooth_displacements

        positions = [(0, 0, 10)]
        adjacency = {0: []}
        weights = [(0, 1.0)]
        result = compute_smooth_displacements(positions, adjacency, weights)
        assert result == {}


class TestFlattenDisplacements:
    """Test the flatten operation."""

    def test_flatten_to_average(self):
        from blender_addon.handlers.terrain_sculpt import compute_flatten_displacements

        heights = [0.0, 4.0, 8.0]
        weights = [(0, 1.0), (1, 1.0), (2, 1.0)]
        result = compute_flatten_displacements(heights, weights)
        # Average = 4.0, all weights = 1.0
        for idx in [0, 1, 2]:
            assert result[idx] == pytest.approx(4.0)

    def test_flatten_partial_weight(self):
        from blender_addon.handlers.terrain_sculpt import compute_flatten_displacements

        heights = [0.0, 10.0]
        weights = [(0, 0.5), (1, 0.5)]
        result = compute_flatten_displacements(heights, weights)
        # Average = 5.0, weight = 0.5
        # idx 0: 0 + (5 - 0) * 0.5 = 2.5
        # idx 1: 10 + (5 - 10) * 0.5 = 7.5
        assert result[0] == pytest.approx(2.5)
        assert result[1] == pytest.approx(7.5)

    def test_flatten_empty(self):
        from blender_addon.handlers.terrain_sculpt import compute_flatten_displacements

        result = compute_flatten_displacements([0.0], [])
        assert result == {}


class TestStampDisplacements:
    """Test the stamp operation with heightmap."""

    def test_basic_stamp(self):
        from blender_addon.handlers.terrain_sculpt import compute_stamp_displacements

        positions_2d = [(0, 0)]
        heights = [0.0]
        weights = [(0, 1.0)]
        # 3x3 heightmap with center = 0.5
        heightmap = [
            [0.0, 0.0, 0.0],
            [0.0, 0.5, 0.0],
            [0.0, 0.0, 0.0],
        ]
        result = compute_stamp_displacements(
            positions_2d, heights, weights, (0, 0), 1.0, heightmap, 2.0
        )
        # Vertex at center -> u=0.5, v=0.5 -> maps to center of heightmap (0.5)
        # new_z = 0 + 0.5 * 2.0 * 1.0 = 1.0
        assert result[0] == pytest.approx(1.0)

    def test_stamp_empty_heightmap(self):
        from blender_addon.handlers.terrain_sculpt import compute_stamp_displacements

        result = compute_stamp_displacements(
            [(0, 0)], [0.0], [(0, 1.0)], (0, 0), 1.0, [], 1.0
        )
        assert result == {}

    def test_stamp_empty_weights(self):
        from blender_addon.handlers.terrain_sculpt import compute_stamp_displacements

        result = compute_stamp_displacements(
            [(0, 0)], [0.0], [], (0, 0), 1.0, [[0.5]], 1.0
        )
        assert result == {}

    def test_stamp_preserves_existing_height(self):
        from blender_addon.handlers.terrain_sculpt import compute_stamp_displacements

        positions_2d = [(0, 0)]
        heights = [5.0]
        weights = [(0, 1.0)]
        heightmap = [[1.0]]
        result = compute_stamp_displacements(
            positions_2d, heights, weights, (0, 0), 1.0, heightmap, 3.0
        )
        # new_z = 5.0 + 1.0 * 3.0 * 1.0 = 8.0
        assert result[0] == pytest.approx(8.0)


class TestFalloffMonotonicity:
    """Verify that all falloff functions decrease as distance increases."""

    @pytest.mark.parametrize("falloff", ["smooth", "sharp", "linear"])
    def test_monotonic_decrease(self, falloff):
        from blender_addon.handlers.terrain_sculpt import get_falloff_value

        prev = get_falloff_value(0.0, falloff)
        for i in range(1, 11):
            d = i / 10.0
            val = get_falloff_value(d, falloff)
            assert val <= prev + 1e-9, (
                f"{falloff} falloff not monotonically decreasing at d={d}"
            )
            prev = val


class TestBrushWeightsSymmetry:
    """Verify that equidistant vertices get equal brush weights."""

    def test_equidistant_vertices(self):
        from blender_addon.handlers.terrain_sculpt import compute_brush_weights

        # 4 vertices at equal distance from center
        d = 3.0
        verts = [(d, 0), (-d, 0), (0, d), (0, -d)]
        result = compute_brush_weights(verts, (0, 0), 5.0, "smooth")
        assert len(result) == 4
        weights = [w for _, w in result]
        assert all(abs(w - weights[0]) < 1e-9 for w in weights)
