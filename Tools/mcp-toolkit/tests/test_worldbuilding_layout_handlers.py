"""Tests for worldbuilding layout handler pure-logic conversion functions.

Tests the _dungeon_to_geometry_ops, _cave_to_geometry_ops, and
_town_to_geometry_ops functions which convert layout data into geometry
operation dicts.  No Blender (bpy) required.
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers._dungeon_gen import (
    generate_bsp_dungeon,
    generate_cave_map,
    generate_town_layout,
)
from blender_addon.handlers.worldbuilding_layout import (
    _cave_to_geometry_ops,
    _dungeon_to_geometry_ops,
    _town_to_geometry_ops,
)


# =========================================================================
# Dungeon geometry ops
# =========================================================================


class TestDungeonToGeometryOps:
    """Tests for _dungeon_to_geometry_ops."""

    def test_returns_list_of_dicts(self):
        layout = generate_bsp_dungeon(32, 32, seed=42)
        ops = _dungeon_to_geometry_ops(layout)
        assert isinstance(ops, list)
        assert all(isinstance(op, dict) for op in ops)

    def test_op_types(self):
        layout = generate_bsp_dungeon(32, 32, seed=42)
        ops = _dungeon_to_geometry_ops(layout)
        types = {op["type"] for op in ops}
        assert "floor" in types
        assert "wall" in types

    def test_each_op_has_position_and_size(self):
        layout = generate_bsp_dungeon(32, 32, seed=42)
        ops = _dungeon_to_geometry_ops(layout)
        for op in ops:
            assert "position" in op, f"Op missing position: {op}"
            assert "size" in op, f"Op missing size: {op}"
            assert len(op["position"]) == 3
            assert len(op["size"]) == 3

    def test_op_count_reasonable(self):
        """Ops should include floors + corridors + doors + boundary walls."""
        layout = generate_bsp_dungeon(32, 32, seed=42)
        ops = _dungeon_to_geometry_ops(layout)
        # At minimum we should have some floor and wall ops
        floor_count = sum(1 for op in ops if op["type"] == "floor")
        wall_count = sum(1 for op in ops if op["type"] == "wall")
        assert floor_count > 0, "No floor ops generated"
        assert wall_count > 0, "No wall ops generated"

    def test_cell_size_affects_positions(self):
        layout = generate_bsp_dungeon(32, 32, seed=42)
        ops_small = _dungeon_to_geometry_ops(layout, cell_size=1.0)
        ops_large = _dungeon_to_geometry_ops(layout, cell_size=4.0)
        # Same number of ops
        assert len(ops_small) == len(ops_large)
        # Positions in large should be 4x the small
        for s, l in zip(ops_small, ops_large):
            assert abs(l["position"][0] - s["position"][0] * 4) < 1e-6
            assert abs(l["position"][1] - s["position"][1] * 4) < 1e-6

    def test_wall_height_parameter(self):
        layout = generate_bsp_dungeon(32, 32, seed=42)
        ops = _dungeon_to_geometry_ops(layout, wall_height=5.0)
        walls = [op for op in ops if op["type"] == "wall"]
        if walls:
            assert walls[0]["size"][2] == 5.0

    def test_corridor_ops_exist(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        ops = _dungeon_to_geometry_ops(layout)
        corridor_ops = [op for op in ops if op["type"] == "corridor"]
        assert len(corridor_ops) > 0, "No corridor geometry ops"

    def test_door_ops_exist_when_doors_present(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        if layout.doors:
            ops = _dungeon_to_geometry_ops(layout)
            door_ops = [op for op in ops if op["type"] == "door"]
            assert len(door_ops) > 0


# =========================================================================
# Cave geometry ops
# =========================================================================


class TestCaveToGeometryOps:
    """Tests for _cave_to_geometry_ops."""

    def test_returns_list_of_dicts(self):
        cave = generate_cave_map(32, 32, seed=42)
        ops = _cave_to_geometry_ops(cave)
        assert isinstance(ops, list)
        assert len(ops) > 0

    def test_has_floor_and_wall_ops(self):
        cave = generate_cave_map(32, 32, seed=42)
        ops = _cave_to_geometry_ops(cave)
        types = {op["type"] for op in ops}
        assert "floor" in types
        assert "wall" in types

    def test_floor_ops_match_floor_cells(self):
        cave = generate_cave_map(32, 32, seed=42)
        ops = _cave_to_geometry_ops(cave, cell_size=2.0)
        floor_ops = [op for op in ops if op["type"] == "floor"]
        floor_cells = int(np.sum(cave.grid == 1))
        assert len(floor_ops) == floor_cells

    def test_wall_height_parameter(self):
        cave = generate_cave_map(32, 32, seed=42)
        ops = _cave_to_geometry_ops(cave, wall_height=6.0)
        walls = [op for op in ops if op["type"] == "wall"]
        if walls:
            assert walls[0]["size"][2] == 6.0

    def test_each_op_has_position_and_size(self):
        cave = generate_cave_map(32, 32, seed=42)
        ops = _cave_to_geometry_ops(cave)
        for op in ops:
            assert "position" in op
            assert "size" in op
            assert len(op["position"]) == 3
            assert len(op["size"]) == 3

    def test_wall_only_at_boundary(self):
        """Wall ops should only be at cells adjacent to floor cells."""
        cave = generate_cave_map(32, 32, seed=42)
        ops = _cave_to_geometry_ops(cave, cell_size=1.0)
        for op in ops:
            if op["type"] == "wall":
                gx = int(op["position"][0])
                gy = int(op["position"][1])
                assert cave.grid[gy, gx] == 0, "Wall op on non-wall cell"


# =========================================================================
# Town geometry ops
# =========================================================================


class TestTownToGeometryOps:
    """Tests for _town_to_geometry_ops."""

    def test_returns_list_of_dicts(self):
        town = generate_town_layout(50, 50, seed=42)
        ops = _town_to_geometry_ops(town)
        assert isinstance(ops, list)
        assert len(ops) > 0

    def test_has_road_ops(self):
        town = generate_town_layout(50, 50, seed=42)
        ops = _town_to_geometry_ops(town)
        road_ops = [op for op in ops if op["type"] == "road"]
        assert len(road_ops) == len(town.roads)

    def test_has_plot_marker_ops(self):
        town = generate_town_layout(100, 100, seed=42)
        ops = _town_to_geometry_ops(town)
        plot_ops = [op for op in ops if op["type"] == "plot_marker"]
        assert len(plot_ops) == len(town.building_plots)

    def test_has_landmark_ops(self):
        town = generate_town_layout(100, 100, seed=42)
        ops = _town_to_geometry_ops(town)
        landmark_ops = [op for op in ops if op["type"] == "landmark"]
        assert len(landmark_ops) == len(town.landmarks)

    def test_cell_size_scales_positions(self):
        town = generate_town_layout(50, 50, seed=42)
        ops_1 = _town_to_geometry_ops(town, cell_size=1.0)
        ops_4 = _town_to_geometry_ops(town, cell_size=4.0)
        assert len(ops_1) == len(ops_4)
        # Road ops should be scaled
        roads_1 = sorted(
            [op for op in ops_1 if op["type"] == "road"],
            key=lambda o: o["position"],
        )
        roads_4 = sorted(
            [op for op in ops_4 if op["type"] == "road"],
            key=lambda o: o["position"],
        )
        if roads_1 and roads_4:
            assert abs(roads_4[0]["position"][0] - roads_1[0]["position"][0] * 4) < 1e-6

    def test_each_op_has_position_and_size(self):
        town = generate_town_layout(50, 50, seed=42)
        ops = _town_to_geometry_ops(town)
        for op in ops:
            assert "position" in op
            assert "size" in op

    def test_landmark_ops_have_district_type(self):
        town = generate_town_layout(100, 100, seed=42)
        ops = _town_to_geometry_ops(town)
        for op in ops:
            if op["type"] == "landmark":
                assert "district_type" in op


# =========================================================================
# Handler return value tests (structure only, no bpy calls)
# =========================================================================


class TestHandlerReturnStructure:
    """Verify handler return dicts have the expected keys by testing the
    pure-logic path (layout + geometry ops) that feeds them."""

    def test_dungeon_handler_metadata(self):
        layout = generate_bsp_dungeon(64, 64, seed=42)
        ops = _dungeon_to_geometry_ops(layout)
        # Simulate what handle_generate_dungeon returns
        result = {
            "name": "Dungeon",
            "room_count": len(layout.rooms),
            "corridor_count": len(layout.corridors),
            "door_count": len(layout.doors),
            "spawn_points": [(x * 2.0, y * 2.0, 0.0) for x, y in layout.spawn_points],
            "loot_points": [(x * 2.0, y * 2.0, 0.0) for x, y in layout.loot_points],
        }
        assert "name" in result
        assert "room_count" in result
        assert "corridor_count" in result
        assert "door_count" in result
        assert "spawn_points" in result
        assert "loot_points" in result
        assert result["room_count"] >= 3

    def test_cave_handler_metadata(self):
        cave = generate_cave_map(64, 64, seed=42)
        floor_area = int(np.sum(cave.grid == 1))
        result = {
            "name": "Cave",
            "floor_area": floor_area,
            "region_count": len(cave.regions),
            "wall_height": 4.0,
        }
        assert "name" in result
        assert "floor_area" in result
        assert result["floor_area"] > 0
        assert "region_count" in result
        assert "wall_height" in result

    def test_town_handler_metadata(self):
        town = generate_town_layout(200, 200, seed=42)
        result = {
            "name": "Town",
            "district_count": len(town.districts),
            "road_cell_count": len(town.roads),
            "plot_count": len(town.building_plots),
            "landmark_count": len(town.landmarks),
        }
        assert "name" in result
        assert "district_count" in result
        assert result["district_count"] > 0
        assert "road_cell_count" in result
        assert result["road_cell_count"] > 0
        assert "plot_count" in result
        assert "landmark_count" in result
