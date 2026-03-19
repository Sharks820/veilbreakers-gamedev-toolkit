"""Blender handlers for dungeon, cave, and town layout generation.

Converts pure-logic layout data from ``_dungeon_gen`` into 3D mesh geometry
via bmesh.  Each handler delegates to a ``_*_to_geometry_ops`` function that
produces a list of geometry-operation dicts (testable without Blender), then
``_ops_to_mesh`` materialises them.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ._dungeon_gen import (
    CaveMap,
    DungeonLayout,
    TownLayout,
    generate_bsp_dungeon,
    generate_cave_map,
    generate_town_layout,
)


# ---------------------------------------------------------------------------
# Pure-logic geometry-op converters (fully testable without Blender)
# ---------------------------------------------------------------------------

def _dungeon_to_geometry_ops(
    layout: DungeonLayout,
    cell_size: float = 2.0,
    wall_height: float = 3.0,
) -> list[dict[str, Any]]:
    """Convert a :class:`DungeonLayout` grid into geometry operation dicts.

    Each operation is one of:
    * ``{"type": "floor", "position": (x, y, z), "size": (sx, sy, sz)}``
    * ``{"type": "wall", "position": ..., "size": ...}``
    * ``{"type": "corridor", "position": ..., "size": ...}``
    * ``{"type": "door", "position": ..., "size": ...}``
    """
    ops: list[dict[str, Any]] = []
    h, w = layout.grid.shape

    for gy in range(h):
        for gx in range(w):
            val = int(layout.grid[gy, gx])
            wx = gx * cell_size
            wy = gy * cell_size

            if val == 1:  # floor
                ops.append({
                    "type": "floor",
                    "position": (wx, wy, 0.0),
                    "size": (cell_size, cell_size, 0.1),
                })
            elif val == 2:  # corridor
                ops.append({
                    "type": "corridor",
                    "position": (wx, wy, 0.0),
                    "size": (cell_size, cell_size, 0.1),
                })
            elif val == 3:  # door
                ops.append({
                    "type": "door",
                    "position": (wx, wy, 0.0),
                    "size": (cell_size, cell_size, wall_height * 0.7),
                })
            elif val == 0:  # wall -- only emit if adjacent to a walkable cell
                if _has_walkable_neighbor(layout.grid, gx, gy, h, w):
                    ops.append({
                        "type": "wall",
                        "position": (wx, wy, 0.0),
                        "size": (cell_size, cell_size, wall_height),
                    })

    return ops


def _has_walkable_neighbor(
    grid: np.ndarray, x: int, y: int, h: int, w: int
) -> bool:
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and grid[ny, nx] > 0:
            return True
    return False


def _cave_to_geometry_ops(
    cave: CaveMap,
    cell_size: float = 2.0,
    wall_height: float = 4.0,
) -> list[dict[str, Any]]:
    """Convert a :class:`CaveMap` grid into geometry operation dicts.

    Floor cells become flat quads; wall cells at the cave boundary become
    extruded wall columns.
    """
    ops: list[dict[str, Any]] = []
    h, w = cave.grid.shape

    for gy in range(h):
        for gx in range(w):
            val = int(cave.grid[gy, gx])
            wx = gx * cell_size
            wy = gy * cell_size

            if val == 1:  # floor
                ops.append({
                    "type": "floor",
                    "position": (wx, wy, 0.0),
                    "size": (cell_size, cell_size, 0.1),
                })
            elif val == 0:
                if _has_walkable_neighbor(cave.grid, gx, gy, h, w):
                    ops.append({
                        "type": "wall",
                        "position": (wx, wy, 0.0),
                        "size": (cell_size, cell_size, wall_height),
                    })

    return ops


def _town_to_geometry_ops(
    town: TownLayout,
    cell_size: float = 2.0,
) -> list[dict[str, Any]]:
    """Convert a :class:`TownLayout` into geometry operation dicts.

    Roads become flat quads, building plot origins become marker boxes,
    and landmarks become taller marker columns.
    """
    ops: list[dict[str, Any]] = []

    # Road cells
    for rx, ry in town.roads:
        ops.append({
            "type": "road",
            "position": (rx * cell_size, ry * cell_size, 0.0),
            "size": (cell_size, cell_size, 0.05),
        })

    # Building plot markers
    for plot in town.building_plots:
        px, py = plot["position"]
        sw, sh = plot["size"]
        ops.append({
            "type": "plot_marker",
            "position": (px * cell_size, py * cell_size, 0.0),
            "size": (sw * cell_size, sh * cell_size, 0.2),
            "district": plot["district"],
        })

    # Landmark markers
    for lm in town.landmarks:
        lx, ly = lm["position"]
        ops.append({
            "type": "landmark",
            "position": (lx * cell_size, ly * cell_size, 0.0),
            "size": (cell_size * 2, cell_size * 2, 3.0),
            "district_type": lm["district_type"],
        })

    return ops


# ---------------------------------------------------------------------------
# bmesh geometry builder (Blender-only)
# ---------------------------------------------------------------------------

def _ops_to_mesh(ops: list[dict[str, Any]], name: str) -> Any:
    """Materialise geometry operations into a Blender mesh object.

    Each operation becomes a box (bmesh cube) at the given position/size.
    Returns the created ``bpy.types.Object``.
    """
    import bpy
    import bmesh

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    for op in ops:
        px, py, pz = op["position"]
        sx, sy, sz = op["size"]

        # Create a unit cube and scale/position it
        result = bmesh.ops.create_cube(bm, size=1.0)
        verts = result["verts"] if "verts" in result else result.get("geom", [])
        if hasattr(verts, "__iter__"):
            vert_list = [v for v in verts if hasattr(v, "co")]
        else:
            vert_list = []

        for v in vert_list:
            v.co.x = v.co.x * sx + px + sx / 2
            v.co.y = v.co.y * sy + py + sy / 2
            v.co.z = v.co.z * sz + pz + sz / 2

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# Blender handlers
# ---------------------------------------------------------------------------

def handle_generate_dungeon(params: dict) -> dict:
    """Generate a BSP dungeon and create 3D mesh geometry.

    Parameters
    ----------
    name : str, default "Dungeon"
    width, height : int, default 64
    min_room_size : int, default 6
    max_depth : int, default 5
    seed : int, default 0
    cell_size : float, default 2.0
    wall_height : float, default 3.0
    """
    name = params.get("name", "Dungeon")
    width = params.get("width", 64)
    height = params.get("height", 64)
    min_room_size = params.get("min_room_size", 6)
    max_depth = params.get("max_depth", 5)
    seed = params.get("seed", 0)
    cell_size = params.get("cell_size", 2.0)
    wall_height = params.get("wall_height", 3.0)

    layout = generate_bsp_dungeon(
        width=width,
        height=height,
        min_room_size=min_room_size,
        max_depth=max_depth,
        seed=seed,
    )

    ops = _dungeon_to_geometry_ops(layout, cell_size=cell_size, wall_height=wall_height)
    obj = _ops_to_mesh(ops, name)

    # Convert spawn/loot points to world-space
    spawn_ws = [
        (x * cell_size, y * cell_size, 0.0) for x, y in layout.spawn_points
    ]
    loot_ws = [
        (x * cell_size, y * cell_size, 0.0) for x, y in layout.loot_points
    ]

    return {
        "name": obj.name,
        "room_count": len(layout.rooms),
        "corridor_count": len(layout.corridors),
        "door_count": len(layout.doors),
        "spawn_points": spawn_ws,
        "loot_points": loot_ws,
    }


def handle_generate_cave(params: dict) -> dict:
    """Generate a cellular-automata cave and create 3D mesh geometry.

    Parameters
    ----------
    name : str, default "Cave"
    width, height : int, default 64
    fill_probability : float, default 0.45
    iterations : int, default 5
    seed : int, default 0
    cell_size : float, default 2.0
    wall_height : float, default 4.0
    """
    name = params.get("name", "Cave")
    width = params.get("width", 64)
    height = params.get("height", 64)
    fill_probability = params.get("fill_probability", 0.45)
    iterations = params.get("iterations", 5)
    seed = params.get("seed", 0)
    cell_size = params.get("cell_size", 2.0)
    wall_height = params.get("wall_height", 4.0)

    cave = generate_cave_map(
        width=width,
        height=height,
        fill_probability=fill_probability,
        iterations=iterations,
        seed=seed,
    )

    ops = _cave_to_geometry_ops(cave, cell_size=cell_size, wall_height=wall_height)
    obj = _ops_to_mesh(ops, name)

    floor_area = int(np.sum(cave.grid == 1))

    return {
        "name": obj.name,
        "floor_area": floor_area,
        "region_count": len(cave.regions),
        "wall_height": wall_height,
    }


def handle_generate_town(params: dict) -> dict:
    """Generate a Voronoi-based town layout and create 3D geometry.

    Parameters
    ----------
    name : str, default "Town"
    width, height : int, default 200
    num_districts : int, default 6
    seed : int, default 0
    cell_size : float, default 2.0
    """
    name = params.get("name", "Town")
    width = params.get("width", 200)
    height = params.get("height", 200)
    num_districts = params.get("num_districts", 6)
    seed = params.get("seed", 0)
    cell_size = params.get("cell_size", 2.0)

    town = generate_town_layout(
        width=width,
        height=height,
        num_districts=num_districts,
        seed=seed,
    )

    ops = _town_to_geometry_ops(town, cell_size=cell_size)
    obj = _ops_to_mesh(ops, name)

    return {
        "name": obj.name,
        "district_count": len(town.districts),
        "road_cell_count": len(town.roads),
        "plot_count": len(town.building_plots),
        "landmark_count": len(town.landmarks),
    }
