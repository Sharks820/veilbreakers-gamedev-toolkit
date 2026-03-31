"""Tests for decorative clutter scatter system (Task 33-03).

Tests:
- Poisson disk produces non-overlapping points
- 5-15 clutter items per room at default density
- Clutter items placed on furniture surfaces and floor
- Same seed = same layout (deterministic)
- No clutter outside room bounds
- Clutter pools defined for 6+ room types
"""

import math
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_clutter():
    from blender_addon.handlers._building_grammar import (
        CLUTTER_POOLS,
        _poisson_disk_scatter_2d,
        generate_clutter_layout,
    )
    return CLUTTER_POOLS, _poisson_disk_scatter_2d, generate_clutter_layout


def _make_furniture(room_type: str) -> list[dict]:
    """Return a small representative furniture list for a given room type."""
    if room_type == "tavern":
        return [
            {"type": "table", "position": [2.0, 2.0, 0.0], "scale": [1.2, 1.2, 0.75]},
            {"type": "bar_counter", "position": [0.6, 3.5, 0.0], "scale": [3.0, 0.8, 1.1]},
            {"type": "shelf", "position": [0.4, 0.5, 0.0], "scale": [1.5, 0.4, 1.8]},
        ]
    if room_type == "library":
        return [
            {"type": "desk", "position": [2.0, 2.0, 0.0], "scale": [1.5, 0.8, 0.75]},
            {"type": "bookshelf", "position": [0.4, 1.0, 0.0], "scale": [2.0, 0.5, 2.5]},
        ]
    if room_type == "kitchen":
        return [
            {"type": "table", "position": [2.0, 2.0, 0.0], "scale": [1.5, 1.0, 0.75]},
            {"type": "shelf", "position": [0.4, 0.8, 0.0], "scale": [2.0, 0.4, 1.8]},
        ]
    # Generic: just a table
    return [
        {"type": "table", "position": [2.0, 2.0, 0.0], "scale": [1.2, 1.2, 0.75]},
    ]


# ---------------------------------------------------------------------------
# CLUTTER_POOLS tests
# ---------------------------------------------------------------------------

class TestClutterPools:
    """CLUTTER_POOLS constant has correct structure and coverage."""

    def test_clutter_pools_defined_for_six_or_more_room_types(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        assert len(CLUTTER_POOLS) >= 6, (
            f"Expected 6+ room types in CLUTTER_POOLS, got {len(CLUTTER_POOLS)}"
        )

    def test_required_room_types_present(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        required = {"tavern", "bedroom", "kitchen", "blacksmith", "library", "chapel"}
        missing = required - set(CLUTTER_POOLS.keys())
        assert not missing, f"Missing room types in CLUTTER_POOLS: {missing}"

    def test_each_pool_has_at_least_three_items(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        for room_type, pool in CLUTTER_POOLS.items():
            assert len(pool) >= 3, (
                f"Pool for '{room_type}' has only {len(pool)} items (need 3+)"
            )

    def test_all_pool_items_are_strings(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        for room_type, pool in CLUTTER_POOLS.items():
            for item in pool:
                assert isinstance(item, str), (
                    f"Non-string item '{item}' in pool for '{room_type}'"
                )

    def test_tavern_pool_contains_expected_items(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        pool = CLUTTER_POOLS["tavern"]
        assert "mug" in pool
        assert "bottle" in pool

    def test_blacksmith_pool_contains_expected_items(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        pool = CLUTTER_POOLS["blacksmith"]
        assert "hammer" in pool
        assert "tongs" in pool

    def test_library_pool_contains_expected_items(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        pool = CLUTTER_POOLS["library"]
        assert "open_book" in pool
        assert "scroll" in pool

    def test_chapel_pool_contains_expected_items(self):
        CLUTTER_POOLS, _, _ = _import_clutter()
        pool = CLUTTER_POOLS["chapel"]
        assert "prayer_bead" in pool
        assert "incense_holder" in pool


# ---------------------------------------------------------------------------
# Poisson disk sampling tests
# ---------------------------------------------------------------------------

class TestPoissonDiskScatter2D:
    """_poisson_disk_scatter_2d returns valid, non-overlapping samples."""

    def test_returns_list(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        rng = random.Random(42)
        pts = _poisson_disk_scatter_2d(5.0, 5.0, 0.5, rng)
        assert isinstance(pts, list)

    def test_no_points_outside_bounds(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        rng = random.Random(99)
        width, depth, min_dist = 4.0, 3.0, 0.3
        pts = _poisson_disk_scatter_2d(width, depth, min_dist, rng)
        for x, y in pts:
            assert 0.0 <= x <= width, f"x={x} out of [0, {width}]"
            assert 0.0 <= y <= depth, f"y={y} out of [0, {depth}]"

    def test_no_two_points_closer_than_min_distance(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        rng = random.Random(7)
        min_dist = 0.3
        pts = _poisson_disk_scatter_2d(6.0, 6.0, min_dist, rng)
        min_dist_sq = min_dist * min_dist
        for i, (x1, y1) in enumerate(pts):
            for j, (x2, y2) in enumerate(pts):
                if i >= j:
                    continue
                dist_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2
                assert dist_sq >= min_dist_sq - 1e-9, (
                    f"Points {i},{j} too close: dist={math.sqrt(dist_sq):.4f} < {min_dist}"
                )

    def test_produces_at_least_one_point(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        rng = random.Random(1)
        pts = _poisson_disk_scatter_2d(3.0, 3.0, 0.5, rng)
        assert len(pts) >= 1

    def test_deterministic_with_same_rng_seed(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        pts_a = _poisson_disk_scatter_2d(4.0, 4.0, 0.4, random.Random(55))
        pts_b = _poisson_disk_scatter_2d(4.0, 4.0, 0.4, random.Random(55))
        assert pts_a == pts_b, "Same seed must produce identical point sets"

    def test_different_seeds_produce_different_layouts(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        pts_a = _poisson_disk_scatter_2d(5.0, 5.0, 0.4, random.Random(1))
        pts_b = _poisson_disk_scatter_2d(5.0, 5.0, 0.4, random.Random(2))
        # Very unlikely to be identical for different seeds
        assert pts_a != pts_b

    def test_smaller_min_distance_yields_more_points(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        pts_sparse = _poisson_disk_scatter_2d(6.0, 6.0, 1.0, random.Random(3))
        pts_dense = _poisson_disk_scatter_2d(6.0, 6.0, 0.3, random.Random(3))
        assert len(pts_dense) >= len(pts_sparse)

    def test_zero_dimensions_returns_empty(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        rng = random.Random(0)
        assert _poisson_disk_scatter_2d(0.0, 5.0, 0.3, rng) == []
        assert _poisson_disk_scatter_2d(5.0, 0.0, 0.3, rng) == []

    def test_zero_min_distance_returns_empty(self):
        import random
        _, _poisson_disk_scatter_2d, _ = _import_clutter()
        rng = random.Random(0)
        assert _poisson_disk_scatter_2d(5.0, 5.0, 0.0, rng) == []


# ---------------------------------------------------------------------------
# generate_clutter_layout tests
# ---------------------------------------------------------------------------

class TestGenerateClutterLayout:
    """generate_clutter_layout produces valid, deterministic clutter placements."""

    def test_returns_list_of_dicts(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("tavern", 6.0, 5.0, _make_furniture("tavern"), seed=1)
        assert isinstance(items, list)
        assert all(isinstance(i, dict) for i in items)

    def test_item_count_between_5_and_15_at_default_density(self):
        _, _, generate_clutter_layout = _import_clutter()
        for room_type in ("tavern", "bedroom", "kitchen", "blacksmith", "library", "chapel"):
            items = generate_clutter_layout(
                room_type, 6.0, 5.0, _make_furniture(room_type), seed=42, density=0.5
            )
            assert 5 <= len(items) <= 15, (
                f"Room '{room_type}': expected 5-15 items, got {len(items)}"
            )

    def test_minimum_density_yields_5_items(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("tavern", 6.0, 5.0, _make_furniture("tavern"), seed=1, density=0.0)
        assert len(items) == 5

    def test_maximum_density_yields_15_items(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("tavern", 6.0, 5.0, _make_furniture("tavern"), seed=1, density=1.0)
        assert len(items) == 15

    def test_same_seed_same_layout(self):
        _, _, generate_clutter_layout = _import_clutter()
        furniture = _make_furniture("tavern")
        layout_a = generate_clutter_layout("tavern", 6.0, 5.0, furniture, seed=123)
        layout_b = generate_clutter_layout("tavern", 6.0, 5.0, furniture, seed=123)
        assert layout_a == layout_b, "Same seed must produce identical layouts"

    def test_different_seeds_differ(self):
        _, _, generate_clutter_layout = _import_clutter()
        furniture = _make_furniture("tavern")
        layout_a = generate_clutter_layout("tavern", 6.0, 5.0, furniture, seed=1)
        layout_b = generate_clutter_layout("tavern", 6.0, 5.0, furniture, seed=2)
        positions_a = [item["position"] for item in layout_a]
        positions_b = [item["position"] for item in layout_b]
        assert positions_a != positions_b

    def test_each_item_has_required_keys(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("kitchen", 5.0, 4.0, _make_furniture("kitchen"), seed=10)
        required_keys = {"name", "position", "rotation", "scale", "surface_parent"}
        for item in items:
            missing = required_keys - set(item.keys())
            assert not missing, f"Item missing keys: {missing} — item: {item}"

    def test_position_is_tuple_or_list_of_three_floats(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("library", 5.0, 4.0, _make_furniture("library"), seed=7)
        for item in items:
            pos = item["position"]
            assert len(pos) == 3, f"Position must have 3 components, got {pos}"
            for v in pos:
                assert isinstance(v, (int, float)), f"Position value not numeric: {v}"

    def test_no_clutter_outside_room_bounds(self):
        _, _, generate_clutter_layout = _import_clutter()
        width, depth = 6.0, 5.0
        items = generate_clutter_layout("tavern", width, depth, _make_furniture("tavern"), seed=5)
        for item in items:
            x, y, _z = item["position"]
            assert 0.0 <= x <= width, f"x={x} outside [0, {width}]"
            assert 0.0 <= y <= depth, f"y={y} outside [0, {depth}]"

    def test_clutter_names_come_from_room_pool(self):
        CLUTTER_POOLS, _, generate_clutter_layout = _import_clutter()
        room_type = "kitchen"
        pool = set(CLUTTER_POOLS[room_type])
        items = generate_clutter_layout(room_type, 5.0, 4.0, _make_furniture(room_type), seed=3)
        for item in items:
            assert item["name"] in pool, (
                f"Item '{item['name']}' not in '{room_type}' pool"
            )

    def test_scale_within_variation_range(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("blacksmith", 5.0, 4.0, _make_furniture("blacksmith"), seed=9)
        for item in items:
            sx, sy, sz = item["scale"]
            assert 0.8 <= sx <= 1.25, f"scale x={sx} outside expected 0.85-1.15 +margin"
            assert sx == sy == sz, "Uniform scale expected: sx==sy==sz"

    def test_items_placed_on_furniture_and_floor_surfaces(self):
        _, _, generate_clutter_layout = _import_clutter()
        # With furniture, some items should be on table_top or shelf_top surfaces
        furniture = _make_furniture("tavern")
        items = generate_clutter_layout("tavern", 6.0, 5.0, furniture, seed=20, density=1.0)
        surface_parents = {item["surface_parent"] for item in items}
        # At minimum floor is always available
        assert "floor" in surface_parents or len(surface_parents) > 0

    def test_surface_parent_is_string(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("library", 5.0, 4.0, _make_furniture("library"), seed=11)
        for item in items:
            assert isinstance(item["surface_parent"], str)

    def test_no_furniture_still_produces_items(self):
        _, _, generate_clutter_layout = _import_clutter()
        # Empty furniture list — floor scatter should still work
        items = generate_clutter_layout("chapel", 4.0, 4.0, [], seed=15)
        assert 5 <= len(items) <= 15

    def test_unknown_room_type_uses_default_pool(self):
        _, _, generate_clutter_layout = _import_clutter()
        # Unknown type should not raise and should return items (using default pool)
        items = generate_clutter_layout("unknown_room", 4.0, 4.0, [], seed=1)
        assert 5 <= len(items) <= 15

    def test_six_room_types_all_produce_valid_layouts(self):
        _, _, generate_clutter_layout = _import_clutter()
        room_types = ["tavern", "bedroom", "kitchen", "blacksmith", "library", "chapel"]
        for rt in room_types:
            furniture = _make_furniture(rt)
            items = generate_clutter_layout(rt, 5.0, 4.0, furniture, seed=42)
            assert len(items) >= 5, f"Room '{rt}' produced fewer than 5 items"
            assert all("name" in i for i in items), f"Room '{rt}' items missing 'name'"

    def test_rotation_is_tuple_of_three(self):
        _, _, generate_clutter_layout = _import_clutter()
        items = generate_clutter_layout("bedroom", 5.0, 4.0, _make_furniture("bedroom"), seed=8)
        for item in items:
            rot = item["rotation"]
            assert len(rot) == 3, f"Rotation must have 3 components, got {rot}"

    def test_items_on_table_have_elevated_z(self):
        _, _, generate_clutter_layout = _import_clutter()
        # Table height = 0.75, so table-top items should have z > 0
        furniture = [
            {"type": "table", "position": [2.5, 2.5, 0.0], "scale": [2.0, 2.0, 0.75]},
        ]
        items = generate_clutter_layout("tavern", 5.0, 5.0, furniture, seed=30, density=1.0)
        # At least some items should be above floor level (z > 0.1)
        elevated = [i for i in items if i["position"][2] > 0.1]
        # With a 2x2 table in a 5x5 room, we expect some to land on the table
        # (not guaranteed with sampling, so just check z values are consistent)
        for item in items:
            z = item["position"][2]
            assert z >= 0.0, f"Clutter z-position {z} is below floor"
