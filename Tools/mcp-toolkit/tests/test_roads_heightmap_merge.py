"""Tests for road_network heightmap wiring and mesh merging (55-03 Task 1)."""

import math
import pytest

from blender_addon.handlers.road_network import (
    sample_heightmap_z,
    _road_segment_mesh_spec,
    _road_segment_mesh_spec_with_curbs,
    compute_road_network,
    merge_road_mesh_specs,
)


# ---------------------------------------------------------------------------
# sample_heightmap_z
# ---------------------------------------------------------------------------


class TestSampleHeightmapZ:
    """Bilinear heightmap sampling must return interpolated terrain height."""

    def test_corner_exact(self):
        hm = [[0.0, 10.0], [20.0, 30.0]]
        assert sample_heightmap_z(hm, 0.0, 0.0) == 0.0
        assert sample_heightmap_z(hm, 1.0, 0.0) == 10.0
        assert sample_heightmap_z(hm, 0.0, 1.0) == 20.0
        assert sample_heightmap_z(hm, 1.0, 1.0) == 30.0

    def test_midpoint_interpolation(self):
        hm = [[0.0, 10.0], [20.0, 30.0]]
        # Centre of 4 cells: average = 15.0
        z = sample_heightmap_z(hm, 0.5, 0.5)
        assert abs(z - 15.0) < 1e-6

    def test_custom_origin_and_cell_size(self):
        hm = [[100.0, 200.0], [300.0, 400.0]]
        # With origin at (10, 20) and cell_size=5, cell (0,1) is at x=15, y=20
        z = sample_heightmap_z(hm, 15.0, 20.0, origin_x=10.0, origin_y=20.0, cell_size=5.0)
        assert abs(z - 200.0) < 1e-6

    def test_out_of_bounds_clamps(self):
        hm = [[5.0, 10.0], [15.0, 20.0]]
        # Far negative should clamp to corner
        z = sample_heightmap_z(hm, -999.0, -999.0)
        assert abs(z - 5.0) < 1e-6

    def test_empty_heightmap_returns_zero(self):
        assert sample_heightmap_z([], 0.0, 0.0) == 0.0
        assert sample_heightmap_z([[]], 0.0, 0.0) == 0.0

    def test_single_cell(self):
        hm = [[42.0]]
        z = sample_heightmap_z(hm, 0.0, 0.0)
        assert abs(z - 42.0) < 1e-6


# ---------------------------------------------------------------------------
# Road mesh spec with heightmap
# ---------------------------------------------------------------------------


class TestRoadMeshSpecHeightmap:
    """Road mesh specs must sample terrain height when heightmap provided."""

    @staticmethod
    def _flat_heightmap(val: float = 5.0, size: int = 20):
        return [[val] * size for _ in range(size)]

    def test_flat_strip_follows_heightmap(self):
        hm = self._flat_heightmap(5.0)
        spec = _road_segment_mesh_spec(
            (0, 0, 0), (10, 0, 0), width=2.0,
            heightmap=hm, heightmap_origin=(0.0, 0.0), heightmap_cell_size=1.0,
        )
        # All vertex Z values should be heightmap value + 0.05 offset
        for v in spec["vertices"]:
            assert abs(v[2] - 5.05) < 1e-6, f"Expected ~5.05 got {v[2]}"

    def test_curb_strip_follows_heightmap(self):
        hm = self._flat_heightmap(3.0)
        spec = _road_segment_mesh_spec_with_curbs(
            (0, 0, 0), (10, 0, 0), width=4.0,
            heightmap=hm, heightmap_origin=(0.0, 0.0), heightmap_cell_size=1.0,
        )
        # Road surface columns (col 2, 3) should be at 3.05 + 0.0 = 3.05
        # Curb columns (col 1, 4) should be at 3.05 + curb_height
        assert len(spec["vertices"]) > 0
        # Check at least some vertices are near terrain height
        zs = [v[2] for v in spec["vertices"]]
        min_z = min(zs)
        assert min_z >= 3.0, f"Min Z {min_z} below terrain"

    def test_without_heightmap_uses_linear_interpolation(self):
        spec = _road_segment_mesh_spec(
            (0, 0, 0), (10, 0, 10), width=2.0,
        )
        # Without heightmap, Z interpolates 0..10
        zs = sorted(set(v[2] for v in spec["vertices"]))
        assert abs(zs[0] - 0.0) < 1e-6
        assert abs(zs[-1] - 10.0) < 1e-6


# ---------------------------------------------------------------------------
# compute_road_network heightmap wiring
# ---------------------------------------------------------------------------


class TestComputeRoadNetworkHeightmap:
    """compute_road_network must pass heightmap to mesh spec generation."""

    @staticmethod
    def _sloped_heightmap(size: int = 50):
        """Heightmap that slopes from Z=0 at row/col 0 to Z=50 at row/col 49."""
        return [[float(r + c) / 2.0 for c in range(size)] for r in range(size)]

    def test_merged_mesh_present(self):
        waypoints = [(5, 5, 0), (15, 5, 0), (10, 15, 0)]
        result = compute_road_network(waypoints)
        assert "merged_mesh" in result
        merged = result["merged_mesh"]
        assert "vertices" in merged
        assert "faces" in merged
        assert "material_indices" in merged
        assert merged["segment_count"] >= 2

    def test_heightmap_wiring_changes_z(self):
        hm = [[10.0] * 30 for _ in range(30)]
        waypoints = [(5, 5, 0), (20, 5, 0)]
        result_no_hm = compute_road_network(waypoints)
        result_hm = compute_road_network(
            waypoints, terrain_heightmap=hm,
            heightmap_origin=(0.0, 0.0), heightmap_cell_size=1.0,
        )
        # Without heightmap, Z comes from waypoints (0)
        zs_no = [v[2] for spec in result_no_hm["mesh_specs"] for v in spec.get("vertices", [])]
        # With heightmap, Z should be ~10.05
        zs_hm = [v[2] for spec in result_hm["mesh_specs"] for v in spec.get("vertices", [])]
        if zs_no and zs_hm:
            assert max(zs_no) < 1.0  # near zero from waypoints
            assert min(zs_hm) > 9.0  # near 10 from heightmap

    def test_merged_mesh_face_indices_valid(self):
        waypoints = [(0, 0, 0), (10, 0, 0), (5, 10, 0), (15, 5, 0)]
        result = compute_road_network(waypoints)
        merged = result["merged_mesh"]
        num_verts = len(merged["vertices"])
        for face in merged["faces"]:
            for idx in face:
                assert 0 <= idx < num_verts, f"Invalid index {idx} with {num_verts} verts"


# ---------------------------------------------------------------------------
# merge_road_mesh_specs
# ---------------------------------------------------------------------------


class TestMergeRoadMeshSpecs:
    """Mesh merging must combine segments with offset indices."""

    def test_empty_input(self):
        merged = merge_road_mesh_specs([])
        assert merged["vertices"] == []
        assert merged["faces"] == []
        assert merged["segment_count"] == 0

    def test_single_spec(self):
        spec = {
            "vertices": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
            "faces": [(0, 1, 2, 3)],
            "road_type": "main",
        }
        merged = merge_road_mesh_specs([spec])
        assert len(merged["vertices"]) == 4
        assert len(merged["faces"]) == 1
        assert merged["material_indices"] == [0]

    def test_two_specs_offset_indices(self):
        spec_a = {
            "vertices": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
            "faces": [(0, 1, 2, 3)],
            "road_type": "main",
        }
        spec_b = {
            "vertices": [(5, 0, 0), (6, 0, 0), (6, 1, 0), (5, 1, 0)],
            "faces": [(0, 1, 2, 3)],
            "road_type": "trail",
        }
        merged = merge_road_mesh_specs([spec_a, spec_b])
        assert len(merged["vertices"]) == 8
        assert len(merged["faces"]) == 2
        # Second face indices should be offset by 4
        assert merged["faces"][1] == (4, 5, 6, 7)
        # Material indices: main=0, trail=2
        assert merged["material_indices"] == [0, 2]

    def test_skips_empty_specs(self):
        spec_empty = {"vertices": [], "faces": [], "road_type": "main"}
        spec_ok = {
            "vertices": [(0, 0, 0), (1, 0, 0), (1, 1, 0)],
            "faces": [(0, 1, 2)],
            "road_type": "path",
        }
        merged = merge_road_mesh_specs([spec_empty, spec_ok])
        assert len(merged["vertices"]) == 3
        assert merged["material_indices"] == [1]

    def test_segment_count_includes_all(self):
        specs = [
            {"vertices": [(0, 0, 0)], "faces": [(0,)], "road_type": "main"},
            {"vertices": [], "faces": [], "road_type": "trail"},
            {"vertices": [(1, 1, 1)], "faces": [(0,)], "road_type": "path"},
        ]
        merged = merge_road_mesh_specs(specs)
        assert merged["segment_count"] == 3  # counts all, even empty
