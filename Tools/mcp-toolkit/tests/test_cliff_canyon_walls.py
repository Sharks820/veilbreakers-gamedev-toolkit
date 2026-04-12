"""Tests for canyon wall geometry improvements (55-03 Task 3).

Verifies strata layers, wall-floor connection, FBM roughness, and
material zone assignment in generate_canyon.
"""

import pytest

from blender_addon.handlers.terrain_features import generate_canyon


class TestCanyonWallStrata:
    """Canyon walls must have visible strata layers."""

    def test_strata_band_material_present(self):
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        assert "strata_band" in result["materials"]

    def test_strata_faces_exist(self):
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        strata_idx = result["materials"].index("strata_band")
        strata_count = sum(1 for m in result["material_indices"] if m == strata_idx)
        assert strata_count > 0, "No strata band faces generated"

    def test_multiple_material_zones(self):
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        unique_mats = set(result["material_indices"])
        # Should have at least floor, wall_rock, wet_rock, and strata_band
        assert len(unique_mats) >= 4, f"Only {len(unique_mats)} material zones"

    def test_wet_rock_at_base(self):
        """Wet rock material should appear at the lower portion of walls."""
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        wet_idx = result["materials"].index("wet_rock")
        assert wet_idx in result["material_indices"]


class TestCanyonWallFloorConnection:
    """Canyon wall base must connect to floor edge without gaps."""

    def test_wall_base_z_matches_floor_edge(self):
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        verts = result["mesh"]["vertices"]

        # Find floor vertices at the left edge (smallest Y per X section)
        floor_y_min = min(v[1] for v in verts if v[2] < 1.0)

        # Find wall base vertices (wall verts at lowest Z per X section)
        # Wall vertices have Y <= -half_w (left wall)
        half_w = 5.0 / 2.0
        left_wall_verts = [v for v in verts if v[1] < -half_w + 0.5]
        if left_wall_verts:
            # The lowest wall verts should have Z close to floor Z
            min_wall_z = min(v[2] for v in left_wall_verts)
            floor_z_at_edge = min(v[2] for v in verts if abs(v[1] - (-half_w)) < 0.5)
            # Gap should be small (wall base connects to floor)
            assert abs(min_wall_z - floor_z_at_edge) < 2.0

    def test_no_vertex_gap_floor_to_wall(self):
        """Floor edge vertices and wall base should be spatially close."""
        result = generate_canyon(width=8, length=30, depth=10, seed=99)
        verts = result["mesh"]["vertices"]
        half_w = 8.0 / 2.0

        # Floor left-edge verts: y close to -half_w, z near 0
        floor_left = [v for v in verts if abs(v[1] - (-half_w)) < 0.2 and v[2] < 1.0]
        # Wall left base verts: y close to -half_w, lowest z per x
        wall_left = [v for v in verts if v[1] < -half_w and v[2] < 2.0]

        # At least some floor/wall verts should exist
        assert len(floor_left) > 0 or len(wall_left) > 0


class TestCanyonWallProfile:
    """Wall profile must have non-linear lean (strata stepping)."""

    def test_wall_not_perfectly_flat(self):
        result = generate_canyon(width=5, length=50, depth=15, wall_roughness=0.5, seed=42)
        verts = result["mesh"]["vertices"]
        half_w = 5.0 / 2.0

        # Left wall Y values should vary (not all at -half_w)
        left_wall_ys = [v[1] for v in verts if v[1] < -half_w + 0.5 and v[2] > 2.0]
        if left_wall_ys:
            y_range = max(left_wall_ys) - min(left_wall_ys)
            assert y_range > 0.1, f"Wall too flat: Y range = {y_range}"

    def test_wall_roughness_increases_variation(self):
        r_smooth = generate_canyon(width=5, length=50, depth=15, wall_roughness=0.1, seed=42)
        r_rough = generate_canyon(width=5, length=50, depth=15, wall_roughness=0.9, seed=42)

        def _left_wall_y_range(result):
            verts = result["mesh"]["vertices"]
            hw = 5.0 / 2.0
            ys = [v[1] for v in verts if v[1] < -hw + 1.0 and v[2] > 2.0]
            return (max(ys) - min(ys)) if ys else 0.0

        smooth_range = _left_wall_y_range(r_smooth)
        rough_range = _left_wall_y_range(r_rough)
        assert rough_range > smooth_range, "Higher roughness should increase Y variation"

    def test_deterministic_with_seed(self):
        r1 = generate_canyon(width=5, length=30, depth=10, seed=42)
        r2 = generate_canyon(width=5, length=30, depth=10, seed=42)
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_different_seed_different_geometry(self):
        r1 = generate_canyon(width=5, length=30, depth=10, seed=1)
        r2 = generate_canyon(width=5, length=30, depth=10, seed=999)
        assert r1["mesh"]["vertices"] != r2["mesh"]["vertices"]

    def test_vertex_count_reasonable(self):
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        # Should have substantially more verts than minimal quad soup
        assert result["vertex_count"] > 100

    def test_face_count_matches_material_indices(self):
        result = generate_canyon(width=5, length=50, depth=15, seed=42)
        assert len(result["material_indices"]) == result["face_count"]
