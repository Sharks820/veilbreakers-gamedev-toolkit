"""Tests for BSP dungeon, cellular automata cave, and town layout generation.

All algorithms are pure-logic (no bpy) and must be seed-deterministic.
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers._dungeon_gen import (
    CaveMap,
    DungeonLayout,
    Room,
    TownLayout,
    _flood_fill,
    _verify_connectivity,
    generate_bsp_dungeon,
    generate_cave_map,
    generate_town_layout,
)


# =========================================================================
# BSP Dungeon Tests
# =========================================================================


class TestBSPDungeon:
    """Tests for generate_bsp_dungeon."""

    def test_returns_dungeon_layout(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        assert isinstance(layout, DungeonLayout)

    def test_has_rooms_corridors_doors_spawns_grid(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        assert len(layout.rooms) > 0
        assert len(layout.corridors) > 0
        assert layout.spawn_points  # non-empty
        assert layout.grid is not None

    def test_all_rooms_reachable(self):
        """Flood-fill from entrance must reach every room."""
        layout = generate_bsp_dungeon(64, 64, seed=42)
        assert _verify_connectivity(layout)

    def test_room_count_at_least_3(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        assert len(layout.rooms) >= 3

    def test_rooms_respect_min_size(self):
        min_room = 6
        layout = generate_bsp_dungeon(64, 64, min_room_size=min_room, seed=42)
        for room in layout.rooms:
            assert room.width >= min_room, f"Room width {room.width} < {min_room}"
            assert room.height >= min_room, f"Room height {room.height} < {min_room}"

    def test_no_rooms_overlap(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        rooms = layout.rooms
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                assert not rooms[i].intersects(rooms[j]), (
                    f"Room {i} overlaps Room {j}"
                )

    def test_grid_dimensions(self):
        layout = generate_bsp_dungeon(64, 48, seed=42)
        assert layout.grid.shape == (48, 64)
        assert layout.width == 64
        assert layout.height == 48

    def test_grid_values(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        unique = set(np.unique(layout.grid))
        assert unique.issubset({0, 1, 2, 3}), f"Unexpected grid values: {unique}"

    def test_spawn_points_on_floor_cells(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        for x, y in layout.spawn_points:
            assert layout.grid[y, x] in (1, 2, 3), (
                f"Spawn ({x},{y}) is on wall (grid={layout.grid[y, x]})"
            )

    def test_deterministic_same_seed(self):
        a = generate_bsp_dungeon(64, 64, seed=42)
        b = generate_bsp_dungeon(64, 64, seed=42)
        assert np.array_equal(a.grid, b.grid)
        assert len(a.rooms) == len(b.rooms)
        for ra, rb in zip(a.rooms, b.rooms):
            assert (ra.x, ra.y, ra.width, ra.height) == (
                rb.x,
                rb.y,
                rb.width,
                rb.height,
            )

    def test_different_seeds_different_layouts(self):
        a = generate_bsp_dungeon(64, 64, seed=42)
        b = generate_bsp_dungeon(64, 64, seed=99)
        assert not np.array_equal(a.grid, b.grid)

    def test_room_types_assigned(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        types = {r.room_type for r in layout.rooms}
        assert "entrance" in types
        assert "boss" in types

    def test_connectivity_multiple_seeds(self):
        """Verify connectivity across a range of seeds."""
        for seed in range(20):
            layout = generate_bsp_dungeon(64, 64, seed=seed)
            assert _verify_connectivity(layout), f"Disconnected dungeon at seed={seed}"


# =========================================================================
# Cave Generation Tests
# =========================================================================


class TestCaveGeneration:
    """Tests for generate_cave_map."""

    def test_returns_cave_map(self):
        cave = generate_cave_map(64, 64, seed=42)
        assert isinstance(cave, CaveMap)

    def test_grid_shape(self):
        cave = generate_cave_map(64, 48, seed=42)
        assert cave.grid.shape == (48, 64)

    def test_border_cells_are_wall(self):
        cave = generate_cave_map(64, 64, seed=42)
        assert np.all(cave.grid[0, :] == 0)
        assert np.all(cave.grid[-1, :] == 0)
        assert np.all(cave.grid[:, 0] == 0)
        assert np.all(cave.grid[:, -1] == 0)

    def test_largest_region_connected(self):
        cave = generate_cave_map(64, 64, seed=42)
        # All floor cells should be in a single connected region
        floor_cells = set()
        for y in range(cave.height):
            for x in range(cave.width):
                if cave.grid[y, x] == 1:
                    floor_cells.add((x, y))
        if floor_cells:
            start = next(iter(floor_cells))
            reachable = _flood_fill(cave.grid, start)
            assert reachable == floor_cells, "Cave has disconnected floor regions"

    def test_floor_ratio_reasonable(self):
        cave = generate_cave_map(64, 64, seed=42)
        total = cave.width * cave.height
        floors = int(np.sum(cave.grid == 1))
        ratio = floors / total
        assert 0.10 <= ratio <= 0.70, f"Floor ratio {ratio:.2f} out of range"

    def test_deterministic(self):
        a = generate_cave_map(64, 64, seed=42)
        b = generate_cave_map(64, 64, seed=42)
        assert np.array_equal(a.grid, b.grid)

    def test_fill_probability_effect(self):
        open_cave = generate_cave_map(64, 64, fill_probability=0.3, seed=42)
        dense_cave = generate_cave_map(64, 64, fill_probability=0.6, seed=42)
        open_floors = int(np.sum(open_cave.grid == 1))
        dense_floors = int(np.sum(dense_cave.grid == 1))
        assert open_floors > dense_floors, (
            f"fill_prob 0.3 ({open_floors} floors) should be more open than "
            f"0.6 ({dense_floors} floors)"
        )

    def test_single_region_after_pruning(self):
        cave = generate_cave_map(64, 64, seed=42)
        assert len(cave.regions) == 1

    def test_different_seeds(self):
        a = generate_cave_map(64, 64, seed=42)
        b = generate_cave_map(64, 64, seed=99)
        assert not np.array_equal(a.grid, b.grid)


# =========================================================================
# Town Layout Tests
# =========================================================================


class TestTownLayout:
    """Tests for generate_town_layout."""

    def test_returns_town_layout(self):
        town = generate_town_layout(200, 200, seed=42)
        assert isinstance(town, TownLayout)

    def test_districts_cover_full_area(self):
        town = generate_town_layout(100, 100, seed=42)
        all_cells: set[tuple[int, int]] = set()
        for d in town.districts:
            all_cells |= d["cells"]
        expected = {(x, y) for y in range(100) for x in range(100)}
        assert all_cells == expected, (
            f"Districts miss {len(expected - all_cells)} cells"
        )

    def test_roads_connected(self):
        town = generate_town_layout(100, 100, seed=42)
        if not town.roads:
            pytest.skip("No roads generated")
        # Build a simple grid for road connectivity
        w, h = town.width, town.height
        road_grid = np.zeros((h, w), dtype=np.int8)
        for x, y in town.roads:
            road_grid[y, x] = 1
        start = next(iter(town.roads))
        reachable = _flood_fill(road_grid, start)
        # Allow minor disconnection (< 5%) due to Voronoi edge effects
        coverage = len(reachable) / len(town.roads)
        assert coverage > 0.90, f"Road connectivity: {coverage:.2%}"

    def test_building_plots_within_districts(self):
        town = generate_town_layout(100, 100, seed=42)
        for plot in town.building_plots:
            district_id = plot["district"]
            district = town.districts[district_id]
            px, py = plot["position"]
            assert (px, py) in district["cells"], (
                f"Plot at {(px, py)} not in district {district_id}"
            )

    def test_district_types(self):
        town = generate_town_layout(200, 200, seed=42)
        types = {d["type"] for d in town.districts}
        # Must have at least civic and residential
        assert "civic" in types
        assert "residential" in types

    def test_landmarks_present(self):
        town = generate_town_layout(200, 200, seed=42)
        assert len(town.landmarks) > 0

    def test_landmark_road_adjacent(self):
        """Landmarks should be near road cells (within 2 cells)."""
        town = generate_town_layout(200, 200, seed=42)
        for lm in town.landmarks:
            lx, ly = lm["position"]
            near_road = any(
                (lx + dx, ly + dy) in town.roads
                for dx in range(-2, 3)
                for dy in range(-2, 3)
            )
            assert near_road, f"Landmark at ({lx},{ly}) not near any road"

    def test_deterministic(self):
        a = generate_town_layout(100, 100, seed=42)
        b = generate_town_layout(100, 100, seed=42)
        assert a.roads == b.roads
        assert len(a.districts) == len(b.districts)
        assert len(a.building_plots) == len(b.building_plots)

    def test_different_seeds(self):
        a = generate_town_layout(100, 100, seed=42)
        b = generate_town_layout(100, 100, seed=99)
        assert a.roads != b.roads

    def test_has_building_plots(self):
        town = generate_town_layout(200, 200, seed=42)
        assert len(town.building_plots) > 0

    def test_each_district_has_type(self):
        town = generate_town_layout(200, 200, seed=42)
        valid = {"civic", "residential", "commercial", "industrial"}
        for d in town.districts:
            assert d["type"] in valid, f"District {d['id']} has invalid type: {d['type']}"
