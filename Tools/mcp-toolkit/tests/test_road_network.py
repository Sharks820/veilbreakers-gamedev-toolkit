"""Tests for road_network handler."""

import math

import pytest

from blender_addon.handlers.road_network import (
    compute_mst_edges,
    compute_road_network,
    _distance_3d,
    _distance_2d,
    _classify_road_type,
    _compute_slope_degrees,
    _generate_switchback_points,
    _segments_near,
    _classify_intersection,
    _detect_bridges,
    _road_segment_mesh_spec,
    _road_segment_mesh_spec_with_curbs,
    ROAD_TYPES,
)


# ---------------------------------------------------------------------------
# Distance helpers
# ---------------------------------------------------------------------------


class TestDistanceHelpers:
    def test_distance_3d_basic(self):
        assert _distance_3d((0, 0, 0), (3, 4, 0)) == 5.0

    def test_distance_3d_with_z(self):
        d = _distance_3d((0, 0, 0), (1, 2, 2))
        assert abs(d - 3.0) < 1e-6

    def test_distance_2d_ignores_z(self):
        assert _distance_2d((0, 0, 100), (3, 4, 200)) == 5.0

    def test_distance_same_point(self):
        assert _distance_3d((5, 5, 5), (5, 5, 5)) == 0.0


# ---------------------------------------------------------------------------
# MST computation
# ---------------------------------------------------------------------------


class TestMSTComputation:
    def test_empty_waypoints(self):
        assert compute_mst_edges([]) == []

    def test_single_waypoint(self):
        assert compute_mst_edges([(0, 0, 0)]) == []

    def test_two_waypoints(self):
        edges = compute_mst_edges([(0, 0, 0), (3, 4, 0)])
        assert len(edges) == 1
        assert edges[0][0] == 0
        assert edges[0][1] == 1
        assert abs(edges[0][2] - 5.0) < 1e-6

    def test_three_waypoints_connected(self):
        waypoints = [(0, 0, 0), (10, 0, 0), (5, 5, 0)]
        edges = compute_mst_edges(waypoints)
        assert len(edges) == 2  # N-1 edges for MST
        # All waypoints should be reachable
        connected = set()
        for a, b, _ in edges:
            connected.add(a)
            connected.add(b)
        assert connected == {0, 1, 2}

    def test_mst_picks_shortest_edges(self):
        # Triangle: 3 waypoints, MST should use 2 shortest edges
        waypoints = [(0, 0, 0), (1, 0, 0), (100, 0, 0)]
        edges = compute_mst_edges(waypoints)
        # Edge from 0->1 (dist=1) and 1->2 (dist=99) should be chosen
        distances = sorted(e[2] for e in edges)
        assert abs(distances[0] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Road type classification
# ---------------------------------------------------------------------------


class TestRoadClassification:
    def test_short_distance_is_main(self):
        assert _classify_road_type(1.0, 10.0) == "main"

    def test_medium_distance_is_path(self):
        assert _classify_road_type(5.0, 10.0) == "path"

    def test_long_distance_is_trail(self):
        assert _classify_road_type(8.0, 10.0) == "trail"

    def test_zero_max_distance(self):
        assert _classify_road_type(5.0, 0.0) == "main"

    def test_all_road_types_have_width(self):
        for name, cfg in ROAD_TYPES.items():
            assert "width" in cfg
            assert cfg["width"] > 0


# ---------------------------------------------------------------------------
# Slope and switchbacks
# ---------------------------------------------------------------------------


class TestSlopeComputation:
    def test_flat_slope(self):
        assert _compute_slope_degrees((0, 0, 0), (10, 0, 0)) == 0.0

    def test_steep_slope(self):
        slope = _compute_slope_degrees((0, 0, 0), (10, 0, 10))
        assert abs(slope - 45.0) < 1e-6

    def test_vertical(self):
        slope = _compute_slope_degrees((0, 0, 0), (0, 0, 10))
        assert slope == 90.0


class TestSwitchbacks:
    def test_no_switchback_on_flat(self):
        result = _generate_switchback_points((0, 0, 0), (10, 0, 0))
        assert result == []

    def test_switchback_on_steep(self):
        result = _generate_switchback_points((0, 0, 0), (10, 0, 20))
        assert len(result) > 0
        for pt in result:
            assert len(pt) == 3

    def test_switchback_deterministic(self):
        r1 = _generate_switchback_points((0, 0, 0), (10, 0, 20), seed=42)
        r2 = _generate_switchback_points((0, 0, 0), (10, 0, 20), seed=42)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Intersection detection
# ---------------------------------------------------------------------------


class TestIntersections:
    def test_crossing_segments(self):
        seg_a = ((0, 0, 0), (10, 10, 0))
        seg_b = ((10, 0, 0), (0, 10, 0))
        result = _segments_near(seg_a, seg_b, threshold=2.0)
        assert result is not None
        assert len(result) == 3

    def test_parallel_distant_segments(self):
        seg_a = ((0, 0, 0), (10, 0, 0))
        seg_b = ((0, 100, 0), (10, 100, 0))
        result = _segments_near(seg_a, seg_b, threshold=2.0)
        assert result is None

    def test_classify_t_junction(self):
        pt = (5, 5, 0)
        segs = [((0, 5, 0), (10, 5, 0)), ((5, 0, 0), (5, 5, 0))]
        result = _classify_intersection(pt, segs)
        assert result == "T"


# ---------------------------------------------------------------------------
# Bridge detection
# ---------------------------------------------------------------------------


class TestBridges:
    def test_no_bridge_above_water(self):
        segments = [((0, 0, 5), (10, 0, 5), 4.0, "main")]
        bridges = _detect_bridges(segments, water_level=0.0)
        assert len(bridges) == 0

    def test_bridge_below_water(self):
        segments = [((0, 0, -2), (10, 0, -2), 4.0, "main")]
        bridges = _detect_bridges(segments, water_level=0.0)
        assert len(bridges) > 0
        assert bridges[0]["road_type"] == "main"
        assert bridges[0]["width"] == 4.0


# ---------------------------------------------------------------------------
# Road mesh spec
# ---------------------------------------------------------------------------


class TestRoadMeshSpec:
    def test_basic_road_strip(self):
        spec = _road_segment_mesh_spec((0, 0, 0), (10, 0, 0), width=4.0)
        assert len(spec["vertices"]) > 0
        assert len(spec["faces"]) > 0
        assert spec["type"] == "road_strip"
        # Vertices should be 3D tuples
        for v in spec["vertices"]:
            assert len(v) == 3

    def test_zero_length_segment(self):
        spec = _road_segment_mesh_spec((5, 5, 0), (5, 5, 0), width=4.0)
        assert spec["vertices"] == []
        assert spec["faces"] == []

    def test_face_indices_valid(self):
        spec = _road_segment_mesh_spec((0, 0, 0), (10, 0, 0), width=2.0)
        num_verts = len(spec["vertices"])
        for face in spec["faces"]:
            for idx in face:
                assert 0 <= idx < num_verts

    def test_road_with_curbs(self):
        spec = _road_segment_mesh_spec_with_curbs(
            (0, 0, 0), (10, 0, 0), width=4.0
        )
        assert len(spec["vertices"]) > 0
        assert "uv_layers" in spec
        assert "road_surface" in spec["uv_layers"]
        assert "curb" in spec["uv_layers"]
        assert spec["type"] == "road_strip_with_curbs"

    def test_curb_mesh_has_more_verts_than_flat(self):
        flat = _road_segment_mesh_spec((0, 0, 0), (10, 0, 0), width=4.0)
        curb = _road_segment_mesh_spec_with_curbs((0, 0, 0), (10, 0, 0), width=4.0)
        assert len(curb["vertices"]) > len(flat["vertices"])


# ---------------------------------------------------------------------------
# Main API: compute_road_network
# ---------------------------------------------------------------------------


class TestComputeRoadNetwork:
    def test_empty_waypoints(self):
        result = compute_road_network([])
        assert result["segments"] == []
        assert result["waypoint_count"] == 0
        assert result["total_length"] == 0.0

    def test_single_waypoint(self):
        result = compute_road_network([(0, 0, 0)])
        assert result["segments"] == []
        assert result["waypoint_count"] == 1

    def test_two_waypoints(self):
        result = compute_road_network([(0, 0, 0), (10, 0, 0)])
        assert len(result["segments"]) >= 1
        assert result["waypoint_count"] == 2
        assert result["total_length"] > 0

    def test_network_has_all_keys(self):
        waypoints = [(0, 0, 0), (10, 0, 0), (5, 10, 0)]
        result = compute_road_network(waypoints)
        for key in ("segments", "intersections", "bridges", "switchbacks",
                     "mesh_specs", "waypoint_count", "total_length"):
            assert key in result

    def test_mesh_specs_match_segments(self):
        waypoints = [(0, 0, 0), (10, 0, 0), (20, 0, 0)]
        result = compute_road_network(waypoints)
        assert len(result["mesh_specs"]) == len(result["segments"])

    def test_mesh_specs_have_valid_geometry(self):
        waypoints = [(0, 0, 0), (10, 0, 0), (5, 10, 0)]
        result = compute_road_network(waypoints)
        for spec in result["mesh_specs"]:
            if spec["vertices"]:
                for v in spec["vertices"]:
                    assert len(v) == 3

    def test_road_width_consistent(self):
        waypoints = [(0, 0, 0), (10, 0, 0)]
        result = compute_road_network(waypoints)
        for seg in result["segments"]:
            road_type = seg[3]
            expected_width = ROAD_TYPES[road_type]["width"]
            assert seg[2] == expected_width

    def test_waypoints_connected(self):
        """All waypoints should be reachable via road segments."""
        waypoints = [(0, 0, 0), (10, 0, 0), (5, 10, 0), (15, 5, 0)]
        result = compute_road_network(waypoints)
        # With MST, we need at least N-1 segment groups
        assert len(result["segments"]) >= len(waypoints) - 1

    def test_deterministic_with_seed(self):
        waypoints = [(0, 0, 0), (10, 0, 20), (5, 10, 0)]
        r1 = compute_road_network(waypoints, seed=42)
        r2 = compute_road_network(waypoints, seed=42)
        assert r1["segments"] == r2["segments"]
        assert r1["switchbacks"] == r2["switchbacks"]
