"""Tests for road_network, coastline, and terrain_features handlers.

All modules are pure logic (no bpy/bmesh). Tests verify mesh spec structure,
determinism, edge cases, and feature correctness.
"""

import math

import pytest


# ===================================================================
# Road Network Tests
# ===================================================================


class TestComputeMstEdges:
    """Test MST edge computation."""

    def test_two_waypoints_single_edge(self):
        from blender_addon.handlers.road_network import compute_mst_edges

        pts = [(0, 0, 0), (10, 0, 0)]
        edges = compute_mst_edges(pts)
        assert len(edges) == 1
        assert edges[0][0] == 0
        assert edges[0][1] == 1
        assert edges[0][2] == pytest.approx(10.0)

    def test_three_waypoints_two_edges(self):
        from blender_addon.handlers.road_network import compute_mst_edges

        pts = [(0, 0, 0), (10, 0, 0), (5, 5, 0)]
        edges = compute_mst_edges(pts)
        assert len(edges) == 2  # n-1 edges for MST

    def test_single_waypoint_no_edges(self):
        from blender_addon.handlers.road_network import compute_mst_edges

        edges = compute_mst_edges([(0, 0, 0)])
        assert len(edges) == 0

    def test_empty_waypoints(self):
        from blender_addon.handlers.road_network import compute_mst_edges

        edges = compute_mst_edges([])
        assert len(edges) == 0

    def test_five_waypoints_four_edges(self):
        from blender_addon.handlers.road_network import compute_mst_edges

        pts = [(0, 0, 0), (10, 0, 0), (20, 0, 0), (10, 10, 0), (10, -10, 0)]
        edges = compute_mst_edges(pts)
        assert len(edges) == 4  # n-1

    def test_collinear_points(self):
        from blender_addon.handlers.road_network import compute_mst_edges

        pts = [(0, 0, 0), (5, 0, 0), (10, 0, 0), (15, 0, 0)]
        edges = compute_mst_edges(pts)
        assert len(edges) == 3
        # MST on collinear points should connect nearest neighbors
        total_dist = sum(d for _, _, d in edges)
        assert total_dist == pytest.approx(15.0)


class TestRoadTypeClassification:
    """Test road segment classification by importance."""

    def test_short_distance_is_main(self):
        from blender_addon.handlers.road_network import _classify_road_type

        assert _classify_road_type(5.0, 100.0) == "main"

    def test_medium_distance_is_path(self):
        from blender_addon.handlers.road_network import _classify_road_type

        assert _classify_road_type(50.0, 100.0) == "path"

    def test_long_distance_is_trail(self):
        from blender_addon.handlers.road_network import _classify_road_type

        assert _classify_road_type(80.0, 100.0) == "trail"

    def test_zero_max_distance_is_main(self):
        from blender_addon.handlers.road_network import _classify_road_type

        assert _classify_road_type(10.0, 0.0) == "main"


class TestSlopeComputation:
    """Test slope angle computation."""

    def test_flat_slope_zero(self):
        from blender_addon.handlers.road_network import _compute_slope_degrees

        assert _compute_slope_degrees((0, 0, 0), (10, 0, 0)) == pytest.approx(0.0)

    def test_45_degree_slope(self):
        from blender_addon.handlers.road_network import _compute_slope_degrees

        slope = _compute_slope_degrees((0, 0, 0), (10, 0, 10))
        assert slope == pytest.approx(45.0)

    def test_vertical_slope_90(self):
        from blender_addon.handlers.road_network import _compute_slope_degrees

        slope = _compute_slope_degrees((0, 0, 0), (0, 0, 10))
        assert slope == pytest.approx(90.0)

    def test_same_point_zero(self):
        from blender_addon.handlers.road_network import _compute_slope_degrees

        slope = _compute_slope_degrees((5, 5, 5), (5, 5, 5))
        assert slope == pytest.approx(0.0)


class TestSwitchbackGeneration:
    """Test switchback point generation on steep slopes."""

    def test_no_switchback_on_flat(self):
        from blender_addon.handlers.road_network import _generate_switchback_points

        pts = _generate_switchback_points((0, 0, 0), (100, 0, 0))
        assert pts == []

    def test_switchback_on_steep_slope(self):
        from blender_addon.handlers.road_network import _generate_switchback_points

        pts = _generate_switchback_points((0, 0, 0), (10, 0, 20), max_slope=30.0)
        assert len(pts) > 0

    def test_switchback_points_are_between_start_end_z(self):
        from blender_addon.handlers.road_network import _generate_switchback_points

        start = (0, 0, 0)
        end = (10, 0, 30)
        pts = _generate_switchback_points(start, end, max_slope=30.0)
        for pt in pts:
            assert 0 <= pt[2] <= 30

    def test_switchback_deterministic(self):
        from blender_addon.handlers.road_network import _generate_switchback_points

        pts1 = _generate_switchback_points((0, 0, 0), (10, 0, 20), seed=42)
        pts2 = _generate_switchback_points((0, 0, 0), (10, 0, 20), seed=42)
        assert pts1 == pts2


class TestIntersectionDetection:
    """Test segment intersection detection."""

    def test_crossing_segments_detected(self):
        from blender_addon.handlers.road_network import _segments_near

        seg_a = ((0, -5, 0), (0, 5, 0))
        seg_b = ((-5, 0, 0), (5, 0, 0))
        pt = _segments_near(seg_a, seg_b, threshold=2.0)
        assert pt is not None
        assert abs(pt[0]) < 1.0
        assert abs(pt[1]) < 1.0

    def test_parallel_far_segments_not_detected(self):
        from blender_addon.handlers.road_network import _segments_near

        seg_a = ((0, 0, 0), (10, 0, 0))
        seg_b = ((0, 100, 0), (10, 100, 0))
        pt = _segments_near(seg_a, seg_b, threshold=2.0)
        assert pt is None

    def test_non_overlapping_segments(self):
        from blender_addon.handlers.road_network import _segments_near

        seg_a = ((0, 0, 0), (5, 0, 0))
        seg_b = ((10, 0, 0), (15, 0, 0))
        pt = _segments_near(seg_a, seg_b, threshold=2.0)
        assert pt is None


class TestIntersectionClassification:
    """Test intersection type classification."""

    def test_two_segments_T(self):
        from blender_addon.handlers.road_network import _classify_intersection

        pt = (0, 0, 0)
        segs = [((0, -5, 0), (0, 5, 0)), ((-5, 0, 0), (5, 0, 0))]
        itype = _classify_intersection(pt, segs)
        assert itype == "T"

    def test_four_segments_cross(self):
        from blender_addon.handlers.road_network import _classify_intersection

        pt = (0, 0, 0)
        segs = [
            ((0, -5, 0), (0, 5, 0)),
            ((-5, 0, 0), (5, 0, 0)),
            ((-3, -3, 0), (3, 3, 0)),
            ((-3, 3, 0), (3, -3, 0)),
        ]
        itype = _classify_intersection(pt, segs)
        assert itype == "cross"


class TestBridgeDetection:
    """Test bridge placement over water."""

    def test_no_bridges_above_water(self):
        from blender_addon.handlers.road_network import _detect_bridges

        segments = [((0, 0, 5), (10, 0, 5), 4.0, "main")]
        bridges = _detect_bridges(segments, water_level=0.0)
        assert len(bridges) == 0

    def test_bridge_below_water(self):
        from blender_addon.handlers.road_network import _detect_bridges

        # Segment dips below water
        segments = [((0, 0, -1), (10, 0, -1), 4.0, "main")]
        bridges = _detect_bridges(segments, water_level=0.0)
        assert len(bridges) > 0

    def test_bridge_has_correct_road_type(self):
        from blender_addon.handlers.road_network import _detect_bridges

        segments = [((0, 0, -2), (10, 0, -2), 2.0, "path")]
        bridges = _detect_bridges(segments, water_level=0.0)
        assert bridges[0]["road_type"] == "path"


class TestComputeRoadNetwork:
    """Test the main road network API."""

    def test_basic_network(self):
        from blender_addon.handlers.road_network import compute_road_network

        waypoints = [(0, 0, 0), (20, 0, 0), (10, 15, 0)]
        result = compute_road_network(waypoints, seed=42)

        assert result["waypoint_count"] == 3
        assert len(result["segments"]) >= 2
        assert result["total_length"] > 0
        assert len(result["mesh_specs"]) == len(result["segments"])

    def test_single_waypoint(self):
        from blender_addon.handlers.road_network import compute_road_network

        result = compute_road_network([(0, 0, 0)], seed=42)
        assert result["segments"] == []
        assert result["total_length"] == 0.0

    def test_empty_waypoints(self):
        from blender_addon.handlers.road_network import compute_road_network

        result = compute_road_network([], seed=42)
        assert result["segments"] == []

    def test_deterministic(self):
        from blender_addon.handlers.road_network import compute_road_network

        wps = [(0, 0, 0), (20, 0, 0), (10, 15, 0), (30, 10, 0)]
        r1 = compute_road_network(wps, seed=42)
        r2 = compute_road_network(wps, seed=42)
        assert r1["total_length"] == r2["total_length"]
        assert len(r1["segments"]) == len(r2["segments"])

    def test_mesh_specs_have_vertices_and_faces(self):
        from blender_addon.handlers.road_network import compute_road_network

        result = compute_road_network(
            [(0, 0, 0), (20, 0, 0)], seed=42
        )
        for spec in result["mesh_specs"]:
            assert "vertices" in spec
            assert "faces" in spec
            assert len(spec["vertices"]) > 0
            assert len(spec["faces"]) > 0

    def test_segments_have_road_type(self):
        from blender_addon.handlers.road_network import compute_road_network

        result = compute_road_network(
            [(0, 0, 0), (20, 0, 0), (40, 0, 0)], seed=42
        )
        for start, end, width, road_type in result["segments"]:
            assert road_type in ("main", "path", "trail")
            assert width > 0

    def test_steep_terrain_generates_switchbacks(self):
        from blender_addon.handlers.road_network import compute_road_network

        # Two points with very steep slope
        wps = [(0, 0, 0), (5, 0, 50)]
        result = compute_road_network(wps, seed=42)
        assert len(result["switchbacks"]) > 0

    def test_water_level_generates_bridges(self):
        from blender_addon.handlers.road_network import compute_road_network

        # Road at negative Z, water at 0
        wps = [(0, 0, -5), (20, 0, -5)]
        result = compute_road_network(wps, water_level=0.0, seed=42)
        assert len(result["bridges"]) > 0


class TestRoadMeshSpec:
    """Test individual road segment mesh generation."""

    def test_mesh_spec_structure(self):
        from blender_addon.handlers.road_network import _road_segment_mesh_spec

        spec = _road_segment_mesh_spec((0, 0, 0), (10, 0, 0), width=4.0)
        assert "vertices" in spec
        assert "faces" in spec
        assert len(spec["vertices"]) > 0
        assert len(spec["faces"]) > 0

    def test_zero_length_segment(self):
        from blender_addon.handlers.road_network import _road_segment_mesh_spec

        spec = _road_segment_mesh_spec((5, 5, 5), (5, 5, 5), width=4.0)
        assert len(spec["vertices"]) == 0

    def test_vertices_respect_width(self):
        from blender_addon.handlers.road_network import _road_segment_mesh_spec

        spec = _road_segment_mesh_spec((0, 0, 0), (10, 0, 0), width=4.0)
        # First pair of vertices should be offset by width/2 in Y
        v0 = spec["vertices"][0]
        v1 = spec["vertices"][1]
        y_diff = abs(v0[1] - v1[1])
        assert y_diff == pytest.approx(4.0)


# ===================================================================
# Coastline Tests
# ===================================================================


class TestCoastlineStyles:
    """Test coastline style configuration."""

    def test_all_styles_defined(self):
        from blender_addon.handlers.coastline import COASTLINE_STYLES

        assert "rocky" in COASTLINE_STYLES
        assert "sandy" in COASTLINE_STYLES
        assert "cliffs" in COASTLINE_STYLES
        assert "harbor" in COASTLINE_STYLES

    def test_styles_have_required_keys(self):
        from blender_addon.handlers.coastline import COASTLINE_STYLES

        for name, config in COASTLINE_STYLES.items():
            assert "description" in config, f"{name} missing description"
            assert "features" in config, f"{name} missing features"
            assert "material_zones" in config, f"{name} missing material_zones"
            assert "shore_noise_amp" in config, f"{name} missing shore_noise_amp"


class TestGenerateCoastline:
    """Test the main coastline generation API."""

    def test_rocky_coastline(self):
        from blender_addon.handlers.coastline import generate_coastline

        result = generate_coastline(length=100, style="rocky", seed=42, resolution=16)
        assert result["style"] == "rocky"
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["features"]) > 0
        assert len(result["material_zones"]) == result["face_count"]

    def test_sandy_coastline(self):
        from blender_addon.handlers.coastline import generate_coastline

        result = generate_coastline(length=100, style="sandy", seed=42, resolution=16)
        assert result["style"] == "sandy"
        assert result["vertex_count"] > 0

    def test_cliffs_coastline(self):
        from blender_addon.handlers.coastline import generate_coastline

        result = generate_coastline(length=100, style="cliffs", seed=42, resolution=16)
        assert result["style"] == "cliffs"
        assert result["vertex_count"] > 0

    def test_harbor_coastline(self):
        from blender_addon.handlers.coastline import generate_coastline

        result = generate_coastline(length=100, style="harbor", seed=42, resolution=16)
        assert result["style"] == "harbor"
        assert result["vertex_count"] > 0

    def test_invalid_style_raises(self):
        from blender_addon.handlers.coastline import generate_coastline

        with pytest.raises(ValueError, match="Unknown coastline style"):
            generate_coastline(style="tropical")

    def test_zero_length_raises(self):
        from blender_addon.handlers.coastline import generate_coastline

        with pytest.raises(ValueError, match="length must be positive"):
            generate_coastline(length=0)

    def test_negative_width_raises(self):
        from blender_addon.handlers.coastline import generate_coastline

        with pytest.raises(ValueError, match="width must be positive"):
            generate_coastline(width=-10)

    def test_low_resolution_raises(self):
        from blender_addon.handlers.coastline import generate_coastline

        with pytest.raises(ValueError, match="resolution must be >= 4"):
            generate_coastline(resolution=2)

    def test_deterministic(self):
        from blender_addon.handlers.coastline import generate_coastline

        r1 = generate_coastline(length=50, style="rocky", seed=42, resolution=16)
        r2 = generate_coastline(length=50, style="rocky", seed=42, resolution=16)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_different_seeds_differ(self):
        from blender_addon.handlers.coastline import generate_coastline

        r1 = generate_coastline(length=50, style="rocky", seed=42, resolution=16)
        r2 = generate_coastline(length=50, style="rocky", seed=99, resolution=16)
        # Features will differ
        assert r1["features"] != r2["features"]

    def test_mesh_has_correct_resolution(self):
        from blender_addon.handlers.coastline import generate_coastline

        res = 32
        result = generate_coastline(resolution=res, seed=42)
        res_across = max(4, res // 2)
        expected_verts = res * res_across
        expected_faces = (res - 1) * (res_across - 1)
        assert result["vertex_count"] == expected_verts
        assert result["face_count"] == expected_faces

    def test_material_names_present(self):
        from blender_addon.handlers.coastline import generate_coastline

        result = generate_coastline(style="rocky", seed=42, resolution=16)
        assert "material_names" in result
        assert len(result["material_names"]) > 0

    def test_shoreline_profile_length(self):
        from blender_addon.handlers.coastline import generate_coastline

        res = 32
        result = generate_coastline(resolution=res, seed=42)
        assert len(result["shoreline_profile"]) == res

    def test_features_have_type_and_position(self):
        from blender_addon.handlers.coastline import generate_coastline

        result = generate_coastline(length=200, style="rocky", seed=42, resolution=32)
        for feat in result["features"]:
            assert "type" in feat
            assert "position" in feat
            assert len(feat["position"]) == 3


class TestCoastlineNoise:
    """Test noise utilities used by coastline."""

    def test_hash_noise_range(self):
        from blender_addon.handlers.coastline import _hash_noise

        for i in range(100):
            val = _hash_noise(i * 0.1, i * 0.2, 42)
            assert -1.0 <= val <= 1.0

    def test_fbm_noise_deterministic(self):
        from blender_addon.handlers.coastline import _fbm_noise

        v1 = _fbm_noise(1.5, 2.3, 42)
        v2 = _fbm_noise(1.5, 2.3, 42)
        assert v1 == v2


# ===================================================================
# Terrain Features: Canyon Tests
# ===================================================================


class TestGenerateCanyon:
    """Test canyon terrain generation."""

    def test_basic_canyon(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["floor_path"]) > 0
        assert len(result["materials"]) == 4

    def test_canyon_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(width=10, length=100, depth=20, seed=42)
        assert result["dimensions"]["width"] == 10
        assert result["dimensions"]["length"] == 100
        assert result["dimensions"]["depth"] == 20

    def test_canyon_side_caves(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(num_side_caves=5, seed=42)
        assert len(result["side_caves"]) == 5
        for cave in result["side_caves"]:
            assert "position" in cave
            assert "side" in cave
            assert cave["side"] in ("left", "right")
            assert cave["width"] > 0
            assert cave["height"] > 0
            assert cave["depth"] > 0

    def test_canyon_zero_caves(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(num_side_caves=0, seed=42)
        assert len(result["side_caves"]) == 0

    def test_canyon_floor_path_spans_length(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(length=50, seed=42)
        path = result["floor_path"]
        assert path[0][0] == pytest.approx(0.0)
        assert path[-1][0] == pytest.approx(50.0)

    def test_canyon_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_canyon_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        r1 = generate_canyon(seed=42)
        r2 = generate_canyon(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_canyon_mesh_structure(self):
        from blender_addon.handlers.terrain_features import generate_canyon

        result = generate_canyon(seed=42)
        mesh = result["mesh"]
        assert "vertices" in mesh
        assert "faces" in mesh
        # All face indices valid
        num_verts = len(mesh["vertices"])
        for face in mesh["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts


# ===================================================================
# Terrain Features: Waterfall Tests
# ===================================================================


class TestGenerateWaterfall:
    """Test waterfall terrain generation."""

    def test_basic_waterfall(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(height=10, width=3, pool_radius=4, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["steps"]) > 0
        assert result["pool"]["radius"] == 4

    def test_waterfall_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(height=15, width=5, pool_radius=6, seed=42)
        assert result["dimensions"]["height"] == 15
        assert result["dimensions"]["width"] == 5
        assert result["dimensions"]["pool_radius"] == 6

    def test_waterfall_step_count(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(num_steps=5, seed=42)
        assert len(result["steps"]) == 5

    def test_waterfall_single_step(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(num_steps=1, seed=42)
        assert len(result["steps"]) == 1

    def test_waterfall_cave_behind(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(has_cave_behind=True, seed=42)
        assert result["cave"] is not None
        assert "position" in result["cave"]
        assert "width" in result["cave"]
        assert "height" in result["cave"]

    def test_waterfall_no_cave(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(has_cave_behind=False, seed=42)
        assert result["cave"] is None

    def test_waterfall_splash_zone(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(pool_radius=4, seed=42)
        splash = result["splash_zone"]
        assert splash["radius"] > 4  # Splash zone is larger than pool

    def test_waterfall_pool_has_depth(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(seed=42)
        assert result["pool"]["depth"] > 0

    def test_waterfall_materials(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(seed=42)
        assert "cliff_rock" in result["materials"]
        assert "wet_rock" in result["materials"]
        assert "pool_bottom" in result["materials"]

    def test_waterfall_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        result = generate_waterfall(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_waterfall_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_waterfall

        r1 = generate_waterfall(seed=42)
        r2 = generate_waterfall(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]


# ===================================================================
# Terrain Features: Cliff Face Tests
# ===================================================================


class TestGenerateCliffFace:
    """Test cliff face terrain generation."""

    def test_basic_cliff(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(width=20, height=15, overhang=3, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert result["dimensions"]["width"] == 20
        assert result["dimensions"]["height"] == 15
        assert result["dimensions"]["overhang"] == 3

    def test_cliff_cave_entrances(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(num_cave_entrances=4, seed=42)
        assert len(result["cave_entrances"]) == 4
        for cave in result["cave_entrances"]:
            assert "position" in cave
            assert cave["width"] > 0
            assert cave["height"] > 0

    def test_cliff_zero_caves(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(num_cave_entrances=0, seed=42)
        assert len(result["cave_entrances"]) == 0

    def test_cliff_ledge_path(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(has_ledge_path=True, seed=42)
        assert len(result["ledge_path"]) > 0
        # Path should span the width
        xs = [p[0] for p in result["ledge_path"]]
        assert min(xs) < 0  # Left side
        assert max(xs) > 0  # Right side

    def test_cliff_no_ledge_path(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(has_ledge_path=False, seed=42)
        assert len(result["ledge_path"]) == 0

    def test_cliff_overhang_zone(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(overhang=5, seed=42)
        assert result["overhang_zone"]["extent"] == 5
        assert len(result["overhang_zone"]["vertices"]) > 0

    def test_cliff_materials(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(seed=42)
        assert "cliff_rock" in result["materials"]
        assert "moss_rock" in result["materials"]
        assert "ledge_stone" in result["materials"]

    def test_cliff_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_cliff_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        r1 = generate_cliff_face(seed=42)
        r2 = generate_cliff_face(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]

    def test_cliff_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_cliff_face

        result = generate_cliff_face(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts


# ===================================================================
# Terrain Features: Swamp Tests
# ===================================================================


class TestGenerateSwampTerrain:
    """Test swamp terrain generation."""

    def test_basic_swamp(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(size=50, water_level=0.3, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert result["dimensions"]["size"] == 50
        assert result["dimensions"]["water_level"] == 0.3

    def test_swamp_hummocks(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(hummock_count=10, seed=42)
        assert len(result["hummocks"]) == 10
        for h in result["hummocks"]:
            assert "position" in h
            assert h["radius"] > 0
            assert h["height"] > 0

    def test_swamp_islands(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(island_count=6, seed=42)
        assert len(result["islands"]) == 6
        for isle in result["islands"]:
            assert "position" in isle
            assert isle["radius"] > 0

    def test_swamp_water_coverage(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(water_level=0.3, seed=42)
        assert 0.0 <= result["water_coverage"] <= 1.0

    def test_swamp_high_water_level_more_coverage(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        low_water = generate_swamp_terrain(water_level=0.1, seed=42)
        high_water = generate_swamp_terrain(water_level=0.9, seed=42)
        assert high_water["water_coverage"] >= low_water["water_coverage"]

    def test_swamp_water_zones(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(water_level=0.3, seed=42)
        for zone in result["water_zones"]:
            assert "bounds" in zone
            assert "cell_count" in zone
            assert zone["cell_count"] > 0

    def test_swamp_materials(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(seed=42)
        assert "swamp_mud" in result["materials"]
        assert "shallow_water" in result["materials"]
        assert "deep_water" in result["materials"]

    def test_swamp_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_swamp_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        r1 = generate_swamp_terrain(seed=42)
        r2 = generate_swamp_terrain(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["water_coverage"] == r2["water_coverage"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_swamp_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_swamp_zero_features(self):
        from blender_addon.handlers.terrain_features import generate_swamp_terrain

        result = generate_swamp_terrain(
            hummock_count=0, island_count=0, seed=42
        )
        assert len(result["hummocks"]) == 0
        assert len(result["islands"]) == 0
        assert result["vertex_count"] > 0  # Still has base terrain


# ===================================================================
# Handler Registration Tests
# ===================================================================


class TestHandlerRegistration:
    """Test that all new handlers are registered in COMMAND_HANDLERS."""

    def test_road_network_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_compute_road_network" in COMMAND_HANDLERS

    def test_coastline_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_generate_coastline" in COMMAND_HANDLERS

    def test_canyon_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_generate_canyon" in COMMAND_HANDLERS

    def test_waterfall_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_generate_waterfall" in COMMAND_HANDLERS

    def test_cliff_face_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_generate_cliff_face" in COMMAND_HANDLERS

    def test_swamp_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_generate_swamp_terrain" in COMMAND_HANDLERS


class TestHandlerInvocation:
    """Test invoking handlers through COMMAND_HANDLERS dict."""

    def test_invoke_road_network(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_compute_road_network"]({
            "waypoints": [(0, 0, 0), (20, 0, 0), (10, 15, 0)],
            "seed": 42,
        })
        assert result["waypoint_count"] == 3
        assert len(result["segments"]) >= 2

    def test_invoke_coastline(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_generate_coastline"]({
            "style": "sandy",
            "length": 100,
            "resolution": 16,
            "seed": 42,
        })
        assert result["style"] == "sandy"
        assert result["vertex_count"] > 0

    def test_invoke_canyon(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_generate_canyon"]({
            "width": 8,
            "length": 40,
            "depth": 12,
            "seed": 42,
        })
        assert result["dimensions"]["width"] == 8
        assert result["vertex_count"] > 0

    def test_invoke_waterfall(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_generate_waterfall"]({
            "height": 12,
            "width": 4,
            "pool_radius": 5,
            "seed": 42,
        })
        assert result["dimensions"]["height"] == 12
        assert result["vertex_count"] > 0

    def test_invoke_cliff_face(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_generate_cliff_face"]({
            "width": 25,
            "height": 20,
            "overhang": 4,
            "seed": 42,
        })
        assert result["dimensions"]["width"] == 25
        assert result["vertex_count"] > 0

    def test_invoke_swamp(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_generate_swamp_terrain"]({
            "size": 30,
            "water_level": 0.4,
            "seed": 42,
        })
        assert result["dimensions"]["size"] == 30
        assert result["vertex_count"] > 0
