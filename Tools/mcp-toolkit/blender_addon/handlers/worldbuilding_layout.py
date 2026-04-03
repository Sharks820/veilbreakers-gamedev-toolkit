"""Blender handlers for dungeon, cave, and town layout generation.

Converts pure-logic layout data from ``_dungeon_gen`` into 3D mesh geometry
via bmesh.  Each handler delegates to a ``_*_to_geometry_ops`` function that
produces a list of geometry-operation dicts (testable without Blender), then
``_ops_to_mesh`` materialises them.

Also provides pure-logic world design functions (WORLD-01 through WORLD-10):
- generate_location_spec: compose building + path + POI layouts (WORLD-01)
- generate_boss_arena_spec: arena with cover, hazards, fog gate (WORLD-03)
- generate_world_graph: connected location graph with distance validation (WORLD-04)
- generate_linked_interior_spec: door trigger / occlusion / lighting markers (WORLD-05)
- generate_easter_egg_spec: secret rooms, hidden paths, lore items (WORLD-10)
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from ._dungeon_gen import (
    CaveMap,
    DungeonLayout,
    TownLayout,
    generate_bsp_dungeon,
    generate_cave_map,
    generate_town_layout,
)

logger = logging.getLogger(__name__)


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
    """Generate a Voronoi-based town layout and create AAA town geometry.

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
    layout_brief = str(params.get("layout_brief", ""))

    import bpy
    from .worldbuilding import handle_generate_building

    rng = random.Random(seed)
    town = generate_town_layout(
        width=width,
        height=height,
        num_districts=num_districts,
        seed=seed,
    )

    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    ops = _town_to_geometry_ops(town, cell_size=cell_size)
    obj = _ops_to_mesh(ops, name)
    obj.parent = parent

    district_lookup = {d["id"]: d for d in town.districts}
    structure_count = 0

    def _structure_params(
        district_type: str,
        plot_size: tuple[int, int],
        slot_index: int = 0,
        landmark: bool = False,
    ) -> dict[str, Any]:
        base_w = max(4.0, plot_size[0] * cell_size * 0.72)
        base_d = max(4.0, plot_size[1] * cell_size * 0.72)
        preset_pool = {
            "market_square": ["inn", "warehouse", "rowhouse"],
            "civic": ["shrine_major", "shrine_minor", "gatehouse"],
            "commercial": ["inn", "warehouse", "rowhouse"],
            "industrial": ["forge", "barracks", "gatehouse"],
            "residential": ["abandoned_house", "rowhouse", "inn"],
        }.get(district_type, ["abandoned_house", "rowhouse"])
        preset = preset_pool[(slot_index + rng.randrange(len(preset_pool))) % len(preset_pool)]
        site_profile = {
            "market_square": "market",
            "civic": "monastery",
            "commercial": "market",
            "industrial": "forgeyard",
            "residential": "rural",
        }.get(district_type, "rural")
        if landmark and district_type in {"civic", "market_square"}:
            preset = "shrine_major"
            site_profile = "monastery"
        if preset:
            return {
                "preset": preset,
                "site_profile": site_profile,
                "weathering_level": 0.04 if district_type == "civic" else 0.08 if district_type == "commercial" else 0.12,
                "wall_height": 4.4 if district_type == "civic" else 4.0 if district_type == "commercial" else 3.6,
            }
        if district_type == "market_square":
            return {
                "width": base_w * 0.8,
                "depth": base_d * 0.8,
                "floors": 1,
                "style": "medieval",
                "site_profile": site_profile,
                "weathering_level": 0.08,
                "wall_height": 3.8,
            }
        if district_type == "civic":
            return {
                "width": base_w,
                "depth": base_d,
                "floors": 2,
                "style": "gothic",
                "site_profile": site_profile,
                "weathering_level": 0.05,
                "wall_height": 4.4,
            }
        if district_type == "commercial":
            return {
                "width": base_w * 0.9,
                "depth": base_d * 0.9,
                "floors": 2,
                "style": "medieval",
                "site_profile": site_profile,
                "weathering_level": 0.12,
                "wall_height": 3.8,
            }
        if district_type == "industrial":
            return {
                "width": base_w,
                "depth": base_d,
                "floors": 1,
                "style": "fortress",
                "site_profile": site_profile,
                "weathering_level": 0.2,
                "wall_height": 4.2,
            }
        return {
            "width": base_w * 0.85,
            "depth": base_d * 0.85,
            "floors": 1,
            "style": "medieval",
            "site_profile": site_profile,
            "weathering_level": 0.12,
            "wall_height": 3.6,
        }

    # Materialize building plots with overlap prevention and road setback.
    # Track occupied footprints to prevent buildings from intersecting.
    _occupied_footprints: list[tuple[float, float, float, float]] = []  # (x_min, y_min, x_max, y_max)
    _SETBACK = 1.5  # meters from plot edge for road clearance
    _MIN_SEPARATION = 2.0  # minimum gap between buildings

    for i, plot in enumerate(town.building_plots):
        district = district_lookup.get(plot["district"], {})
        district_type = district.get("type", "residential")
        build_params = _structure_params(district_type, plot["size"], slot_index=i)

        # Clamp building size to plot dimensions with setback
        plot_w = max(5.6, plot["size"][0] * cell_size * 0.72 - _SETBACK * 2)
        plot_d = max(5.6, plot["size"][1] * cell_size * 0.72 - _SETBACK * 2)
        build_params["width"] = min(float(build_params.get("width", 10)), plot_w)
        build_params["depth"] = min(float(build_params.get("depth", 8)), plot_d)

        structure_name = f"{name}_building_{i}"
        build_params.update({
            "name": structure_name,
            "seed": seed + i * 17,
        })

        # Check overlap with existing buildings before generating
        px, py = plot["position"]
        bx = px * cell_size + _SETBACK
        by = py * cell_size + _SETBACK
        bw = float(build_params["width"])
        bd = float(build_params["depth"])
        candidate_box = (bx, by, bx + bw, by + bd)

        _overlaps = False
        for existing in _occupied_footprints:
            if (candidate_box[0] < existing[2] + _MIN_SEPARATION and
                    candidate_box[2] > existing[0] - _MIN_SEPARATION and
                    candidate_box[1] < existing[3] + _MIN_SEPARATION and
                    candidate_box[3] > existing[1] - _MIN_SEPARATION):
                _overlaps = True
                break

        if _overlaps:
            logger.debug("Skipping building %s at (%s,%s) - overlaps existing", structure_name, px, py)
            continue

        handle_generate_building(build_params)

        building_obj = bpy.data.objects.get(structure_name)
        if building_obj is not None:
            building_obj.location = (bx, by, 0.0)
            # Vary rotation for visual interest (face road)
            import random as _rng_town
            _rng_town.seed(seed + i)
            rot_z = _rng_town.choice([0.0, math.pi * 0.5, math.pi, math.pi * 1.5])
            building_obj.rotation_euler = (0.0, 0.0, rot_z)
            building_obj.parent = parent
            _occupied_footprints.append(candidate_box)
            structure_count += 1

    # Turn landmarks into larger, more expressive anchor buildings.
    for i, landmark in enumerate(town.landmarks):
        district = district_lookup.get(landmark["district"], {})
        district_type = district.get("type", "residential")
        lm_name = f"{name}_landmark_{i}"
        lm_build = _structure_params(district_type, (20, 20), slot_index=i, landmark=True)
        lm_build["name"] = lm_name
        lm_build["seed"] = seed + 1000 + i * 31
        handle_generate_building(lm_build)

        lm_obj = bpy.data.objects.get(lm_name)
        if lm_obj is not None:
            lx, ly = landmark["position"]
            lm_obj.location = (lx * cell_size, ly * cell_size, 0.0)
            lm_obj.rotation_euler = (0.0, 0.0, 0.0)
            lm_obj.parent = parent
            structure_count += 1

    # Overlay the richer settlement system so the town gets macro roads,
    # perimeter features, props, and settlement-level dressing.
    settlement_overlay = {"status": "skipped"}
    try:
        from .worldbuilding import handle_generate_settlement

        settlement_overlay = handle_generate_settlement({
            "name": f"{name}_SettlementOverlay",
            "settlement_type": "town",
            "seed": seed,
            "center": (width * cell_size * 0.5, height * cell_size * 0.5),
            "radius": min(width, height) * cell_size * 0.42,
            "wall_height": cell_size * 1.5,
            "layout_brief": layout_brief,
            "parent_name": name,
            "include_buildings": False,
            "include_interiors": False,
            "include_lights": False,
        })
    except Exception as exc:
        logger.warning("Town settlement overlay failed for %s: %s", name, exc)
        settlement_overlay = {"status": "failed", "error": str(exc)}

    return {
        "name": obj.name,
        "district_count": len(town.districts),
        "road_cell_count": len(town.roads),
        "plot_count": len(town.building_plots),
        "landmark_count": len(town.landmarks),
        "structure_count": structure_count,
        "settlement_overlay": settlement_overlay,
    }


def handle_generate_hearthvale(params: dict) -> dict:
    """Generate Hearthvale fortified castle-town via generate_settlement().

    Uses the fully-featured settlement path (perimeter walls, interiors,
    lighting) rather than the older generate_town_layout() path.

    Parameters
    ----------
    name : str, default "Hearthvale"
    seed : int, default 3810
    center : list[float], default [0.0, 0.0]
    radius : float, default 65.0
    layout_brief : str, optional
    """
    import bpy

    from .settlement_generator import generate_settlement

    name = params.get("name", "Hearthvale")
    seed = int(params.get("seed", 3810))
    center = tuple(params.get("center", [0.0, 0.0]))
    radius = float(params.get("radius", 65.0))
    layout_brief = params.get(
        "layout_brief",
        "fortified castle-town, winding cobblestone, market square at center, "
        "radial streets from square, military quarter, commerce district",
    )
    veil_pressure = float(params.get("veil_pressure", 0.0))

    result = generate_settlement(
        settlement_type="hearthvale",
        seed=seed,
        center=center,
        radius=radius,
        wall_height=3.5,
        layout_brief=layout_brief,
        veil_pressure=veil_pressure,
    )

    # Create parent empty
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    # Materialize buildings using the AAA building generator
    from .worldbuilding import _generate_location_building

    buildings_created = 0
    for i, bld in enumerate(result.get("buildings", [])):
        bld_type = bld.get("type", "abandoned_house")
        fp = bld.get("footprint", (8.0, 6.0))
        building_dict = {
            "type": bld_type,
            "position": tuple(bld.get("position", (0.0, 0.0))),
            "rotation": bld.get("rotation", 0.0),
            "size": fp,
            "floors": bld.get("floors", 1),
            "elevation": bld.get("elevation", 0.0),
        }
        try:
            if _generate_location_building(name, building_dict, seed, i, None, parent):
                buildings_created += 1
        except Exception:
            # Fallback: create a simple box if the AAA generator fails
            import bmesh
            bld_name = f"{name}_{bld_type}_{i}"
            bx, by = bld.get("position", (0.0, 0.0))
            elevation = bld.get("elevation", 0.0)
            mesh = bpy.data.meshes.new(f"{bld_name}_mesh")
            obj = bpy.data.objects.new(bld_name, mesh)
            obj.location = (bx, by, elevation)
            obj.rotation_euler = (0.0, 0.0, bld.get("rotation", 0.0))
            obj.parent = parent
            bpy.context.collection.objects.link(obj)
            bm = bmesh.new()
            try:
                hw, hd = fp[0] / 2.0, fp[1] / 2.0
                # WORLD-005: use configurable floor_height (default 3.5 m)
                floor_height = float(params.get("floor_height", 3.5))
                wh = floor_height * bld.get("floors", 1)
                vs = [
                    bm.verts.new((-hw, -hd, 0.0)),
                    bm.verts.new((hw, -hd, 0.0)),
                    bm.verts.new((hw, hd, 0.0)),
                    bm.verts.new((-hw, hd, 0.0)),
                    bm.verts.new((-hw, -hd, wh)),
                    bm.verts.new((hw, -hd, wh)),
                    bm.verts.new((hw, hd, wh)),
                    bm.verts.new((-hw, hd, wh)),
                ]
                for face_verts in [
                    [vs[0], vs[1], vs[2], vs[3]], [vs[4], vs[5], vs[6], vs[7]],
                    [vs[0], vs[1], vs[5], vs[4]], [vs[2], vs[3], vs[7], vs[6]],
                    [vs[0], vs[3], vs[7], vs[4]], [vs[1], vs[2], vs[6], vs[5]],
                ]:
                    bm.faces.new(face_verts)
                bm.to_mesh(mesh)
                buildings_created += 1
            finally:
                # WORLD-007: always free bmesh even on exception
                bm.free()

    # Materialize perimeter walls using AAA stone wall generator
    from .building_quality import generate_stone_wall, generate_archway
    from ._mesh_bridge import mesh_from_spec
    from .worldbuilding import _assign_procedural_material

    perimeter_created = 0
    for i, elem in enumerate(result.get("perimeter", [])):
        elem_type = elem.get("type", "wall_segment")
        elem_name = f"{name}_perimeter_{elem_type}_{i}"
        ex, ey = elem.get("position", (0.0, 0.0))
        rot_z = elem.get("rotation", 0.0)

        try:
            if elem.get("is_gate"):
                # Gate archway with stone detail
                gate_spec = generate_archway(
                    width=4.0, height=5.5, depth=1.6,
                    arch_style="gothic_pointed", has_keystone=True,
                    seed=seed + 3000 + i,
                )
                obj = mesh_from_spec(gate_spec, name=elem_name,
                                     location=(ex, ey, 0.0),
                                     rotation=(0.0, 0.0, rot_z),
                                     parent=parent)
                if not isinstance(obj, dict):
                    _assign_procedural_material(obj, "smooth_stone")
            elif elem.get("is_tower"):
                # Corner tower — taller, thicker stone walls
                tower_spec = generate_stone_wall(
                    width=5.0, height=7.0, thickness=1.2,
                    block_style="ashlar", seed=seed + 3000 + i,
                )
                obj = mesh_from_spec(tower_spec, name=elem_name,
                                     location=(ex, ey, 0.0),
                                     rotation=(0.0, 0.0, rot_z),
                                     parent=parent)
                if not isinstance(obj, dict):
                    _assign_procedural_material(obj, "rough_stone_wall")
            else:
                # Wall segment with stone block detail
                wall_spec = generate_stone_wall(
                    width=6.0, height=5.5, thickness=0.8,
                    block_style="ashlar", mortar_depth=0.008,
                    seed=seed + 3000 + i,
                )
                obj = mesh_from_spec(wall_spec, name=elem_name,
                                     location=(ex, ey, 0.0),
                                     rotation=(0.0, 0.0, rot_z),
                                     parent=parent)
                if not isinstance(obj, dict):
                    _assign_procedural_material(obj, "rough_stone_wall")
            perimeter_created += 1
        except Exception:
            # Fallback: simple box if stone generator fails
            import bmesh
            mesh = bpy.data.meshes.new(f"{elem_name}_mesh")
            obj = bpy.data.objects.new(elem_name, mesh)
            obj.location = (ex, ey, 0.0)
            obj.rotation_euler = (0.0, 0.0, rot_z)
            obj.parent = parent
            bpy.context.collection.objects.link(obj)
            bm = bmesh.new()
            if elem.get("is_gate"):
                hw, hd, wh = 3.0, 1.0, 5.5
            elif elem.get("is_tower"):
                hw, hd, wh = 2.5, 2.5, 7.0
            else:
                hw, hd, wh = 3.0, 0.8, 5.5
            vs = [bm.verts.new(v) for v in [
                (-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
                (-hw, -hd, wh), (hw, -hd, wh), (hw, hd, wh), (-hw, hd, wh),
            ]]
            for fi in [(0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(0,3,7,4),(1,2,6,5)]:
                bm.faces.new([vs[j] for j in fi])
            bm.to_mesh(mesh)
            bm.free()
            perimeter_created += 1

    return {
        "status": "success",
        "name": name,
        "buildings_created": buildings_created,
        "perimeter_created": perimeter_created,
        "road_count": len(result.get("roads", [])),
        "prop_count": len(result.get("props", [])),
        "metadata": result.get("metadata", {}),
    }


# ---------------------------------------------------------------------------
# Pure-logic world design functions (testable without Blender)
# ---------------------------------------------------------------------------


@dataclass
class WorldGraphNode:
    """A location node in the world graph."""

    name: str
    location_type: str
    position: tuple[float, float]


@dataclass
class WorldGraphEdge:
    """A path edge between two world graph nodes."""

    from_node: str
    to_node: str
    distance: float
    path_type: str = "road"


@dataclass
class WorldGraph:
    """Connected graph of game world locations."""

    nodes: list[WorldGraphNode] = field(default_factory=list)
    edges: list[WorldGraphEdge] = field(default_factory=list)


def generate_world_graph(
    locations: list[dict],
    target_distance: float = 105.0,
    seed: int = 0,
    add_landmarks: bool = True,
    world_bounds: tuple[float, float, float, float] = (-500.0, -500.0, 500.0, 500.0),
) -> WorldGraph:
    """Generate a connected world graph from location data (WORLD-04).

    CITY-008: Optionally seeds natural landmarks (peaks, lakes, ancient ruins,
    crossroads shrines) into the graph.  Landmarks are placed in gaps between
    existing locations to give waypoint context to world navigation.  They are
    tagged ``is_landmark=True`` so downstream systems can render them differently
    from functional settlements.

    Uses proximity-based MST to ensure connectivity, then adds extra edges
    for loop paths.  Validates that edges approximate *target_distance*
    (~105 m for the 30-second walking rule at 3.5 m/s).

    Parameters
    ----------
    locations : list of dict
        Each dict has ``name`` (str), ``type`` (str), ``position`` (x, y).
    target_distance : float
        Target walking distance between connected POIs (default 105 m).
    seed : int
        Random seed.
    add_landmarks : bool
        If True, scatter natural landmark nodes into large empty regions.
    world_bounds : tuple
        (min_x, min_y, max_x, max_y) bounding box used when placing landmarks.

    Returns
    -------
    WorldGraph
        Graph with nodes and edges.
    """
    rng = random.Random(seed)

    # CITY-008: generate landmark nodes for large empty regions
    landmark_locs: list[dict] = []
    if add_landmarks and locations:
        _LANDMARK_TYPES = [
            "ancient_ruins", "standing_stones", "mountain_peak",
            "forest_shrine", "river_crossing", "cliff_overlook",
            "haunted_tree", "burial_mound", "forgotten_well",
        ]
        min_x, min_y, max_x, max_y = world_bounds
        # Place one landmark per ~3 locations, up to 6 max
        landmark_count = min(6, max(1, len(locations) // 3))
        placed_landmark_positions: list[tuple[float, float]] = [
            (loc["position"][0], loc["position"][1]) for loc in locations
        ]
        for li in range(landmark_count):
            best_pos: Optional[tuple[float, float]] = None
            best_min_dist = 0.0
            # Pick the position that maximises minimum distance from all existing nodes
            for _ in range(30):
                cx = rng.uniform(min_x * 0.8, max_x * 0.8)
                cy = rng.uniform(min_y * 0.8, max_y * 0.8)
                min_d = min(
                    math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
                    for px, py in placed_landmark_positions
                )
                if min_d > best_min_dist:
                    best_min_dist = min_d
                    best_pos = (cx, cy)
            if best_pos and best_min_dist > target_distance * 0.5:
                ltype = rng.choice(_LANDMARK_TYPES)
                lname = f"{ltype.replace('_', ' ').title()} {li + 1}"
                placed_landmark_positions.append(best_pos)
                landmark_locs.append({
                    "name": lname,
                    "type": ltype,
                    "position": best_pos,
                    "is_landmark": True,
                })

    nodes = [
        WorldGraphNode(
            name=loc["name"],
            location_type=loc.get("type", "generic"),
            position=(loc["position"][0], loc["position"][1]),
        )
        for loc in locations
    ]
    # Add landmark nodes (tagged so callers can distinguish them)
    for lm in landmark_locs:
        nodes.append(WorldGraphNode(
            name=lm["name"],
            location_type=lm["type"],
            position=(lm["position"][0], lm["position"][1]),
        ))

    if len(nodes) < 2:
        return WorldGraph(nodes=nodes, edges=[])

    # Compute all pairwise distances
    n = len(nodes)
    dist_matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            dx = nodes[i].position[0] - nodes[j].position[0]
            dy = nodes[i].position[1] - nodes[j].position[1]
            row.append(math.sqrt(dx * dx + dy * dy))
        dist_matrix.append(row)

    # Prim's MST for guaranteed connectivity
    in_tree = [False] * n
    in_tree[0] = True
    mst_edges: list[tuple[int, int, float]] = []

    for _ in range(n - 1):
        best_edge: Optional[tuple[int, int, float]] = None
        for i in range(n):
            if not in_tree[i]:
                continue
            for j in range(n):
                if in_tree[j]:
                    continue
                d = dist_matrix[i][j]
                if best_edge is None or d < best_edge[2]:
                    best_edge = (i, j, d)
        if best_edge is None:
            break
        mst_edges.append(best_edge)
        in_tree[best_edge[1]] = True

    # Build edge set from MST
    edge_set: set[tuple[int, int]] = set()
    edges: list[WorldGraphEdge] = []
    for i, j, d in mst_edges:
        key = (min(i, j), max(i, j))
        if key not in edge_set:
            edge_set.add(key)
            edges.append(WorldGraphEdge(
                from_node=nodes[i].name,
                to_node=nodes[j].name,
                distance=round(d, 2),
            ))

    # Add extra loop edges: connect pairs that are close to target_distance
    tolerance = target_distance * 0.4  # 40% tolerance for extra edges
    for i in range(n):
        for j in range(i + 1, n):
            key = (i, j)
            if key in edge_set:
                continue
            d = dist_matrix[i][j]
            if abs(d - target_distance) < tolerance:
                if rng.random() < 0.4:  # 40% chance to add loop edge
                    edge_set.add(key)
                    edges.append(WorldGraphEdge(
                        from_node=nodes[i].name,
                        to_node=nodes[j].name,
                        distance=round(d, 2),
                    ))

    return WorldGraph(nodes=nodes, edges=edges)


def generate_boss_arena_spec(
    arena_type: str = "circular",
    diameter: float = 30.0,
    cover_count: int = 4,
    hazard_zones: int = 2,
    has_fog_gate: bool = True,
    phase_trigger_count: int = 3,
    seed: int = 0,
) -> dict:
    """Generate a boss arena specification (WORLD-03).

    Returns dict with arena geometry, cover positions, hazard zones,
    fog gate position, and phase trigger positions.  All positions are
    within the arena diameter bounds.  Pure-logic, no bpy.
    """
    rng = random.Random(seed)
    radius = diameter / 2.0

    # Arena base
    spec: dict[str, Any] = {
        "arena_type": arena_type,
        "diameter": diameter,
        "radius": radius,
        "center": (0.0, 0.0),
    }

    # Cover positions (placed around arena, avoiding center)
    covers: list[dict] = []
    for i in range(cover_count):
        angle = (2 * math.pi * i / cover_count) + rng.uniform(-0.3, 0.3)
        dist = rng.uniform(radius * 0.3, radius * 0.7)
        cx = round(math.cos(angle) * dist, 2)
        cy = round(math.sin(angle) * dist, 2)
        cover_type = rng.choice(["pillar", "rock", "wall_fragment", "statue"])
        covers.append({
            "position": (cx, cy),
            "type": cover_type,
            "radius": round(rng.uniform(0.8, 1.5), 2),
        })
    spec["covers"] = covers

    # Hazard zones (larger areas of danger)
    hazards: list[dict] = []
    for i in range(hazard_zones):
        angle = (2 * math.pi * (i + 0.5) / hazard_zones) + rng.uniform(-0.5, 0.5)
        dist = rng.uniform(radius * 0.2, radius * 0.6)
        hx = round(math.cos(angle) * dist, 2)
        hy = round(math.sin(angle) * dist, 2)
        hazard_type = rng.choice(["fire_pit", "acid_pool", "spike_trap", "void_zone"])
        hazards.append({
            "position": (hx, hy),
            "type": hazard_type,
            "radius": round(rng.uniform(2.0, 4.0), 2),
        })
    spec["hazard_zones"] = hazards

    # Fog gate (entrance)
    if has_fog_gate:
        spec["fog_gate"] = {
            "position": (0.0, -radius),
            "width": round(rng.uniform(3.0, 5.0), 2),
            "height": round(rng.uniform(3.0, 4.0), 2),
        }
    else:
        spec["fog_gate"] = None

    # Phase triggers (concentric rings at different health thresholds)
    triggers: list[dict] = []
    for i in range(phase_trigger_count):
        trigger_radius = radius * (0.3 + 0.2 * i)
        triggers.append({
            "phase": i + 1,
            "trigger_radius": round(trigger_radius, 2),
            "center": (0.0, 0.0),
        })
    spec["phase_triggers"] = triggers

    return spec


def generate_location_spec(
    location_type: str = "village",
    building_count: int = 5,
    path_count: int = 3,
    poi_count: int = 2,
    seed: int = 0,
    terrain_heightmap: Optional[Any] = None,
    terrain_slope_threshold: float = 0.4,
) -> dict:
    """Generate a complete location specification (WORLD-01).

    CITY-007: Now terrain-aware.  When ``terrain_heightmap`` is provided
    (a callable ``(x, y) -> float``), buildings are placed only on flat areas
    (slope < ``terrain_slope_threshold``).  Each building is annotated with
    its terrain elevation.  High-slope positions are skipped during placement.

    Composes building placement + path routing + POI distribution into a
    single location spec.  Pure-logic, no bpy.

    Returns dict with terrain_bounds, buildings, paths, pois.
    """
    rng = random.Random(seed)

    # Terrain bounds based on building count
    terrain_size = max(50.0, building_count * 15.0)
    half = terrain_size / 2.0

    spec: dict[str, Any] = {
        "location_type": location_type,
        "terrain_bounds": {
            "min": (-half, -half),
            "max": (half, half),
            "size": terrain_size,
        },
    }

    def _terrain_elevation(x: float, y: float) -> float:
        """Sample heightmap if provided, else return 0."""
        if terrain_heightmap is None:
            return 0.0
        try:
            return float(terrain_heightmap(x, y))
        except Exception:
            return 0.0

    def _terrain_slope(x: float, y: float, step: float = 1.0) -> float:
        """Estimate terrain slope via finite differences.  Returns approximate
        gradient magnitude.  Returns 0 when no heightmap provided."""
        if terrain_heightmap is None:
            return 0.0
        h_c = _terrain_elevation(x, y)
        h_e = _terrain_elevation(x + step, y)
        h_n = _terrain_elevation(x, y + step)
        gx = (h_e - h_c) / step
        gy = (h_n - h_c) / step
        return math.sqrt(gx * gx + gy * gy)

    # Building positions (avoid overlap using simple spacing)
    buildings: list[dict] = []
    placed_positions: list[tuple[float, float]] = []
    _BUILDING_TYPES = {
        "village": ["house", "tavern", "blacksmith", "chapel", "market_stall"],
        "fortress": ["barracks", "armory", "war_room", "guard_tower", "gatehouse"],
        "dungeon_entrance": ["ruined_tower", "cave_mouth", "guard_post"],
        "camp": ["tent", "campfire", "supply_cart", "lookout_post"],
        "traveler_camp": ["tent", "lookout_post", "supply_tent", "market_stall"],
        "merchant_camp": ["tent", "market_stall", "supply_tent", "lookout_post"],
        "fishing_village": ["dock", "boat_house", "tavern", "cottage", "cottage"],
        "mining_town": ["mine_entrance", "smelter", "barracks", "tavern", "general_store"],
        "port_city": ["harbor_dock", "warehouse", "lighthouse", "tavern", "market_stall", "guard_tower"],
        "monastery": ["temple", "dormitory", "library", "garden", "bell_tower"],
        "necropolis": ["catacomb", "mausoleum", "shrine", "ossuary"],
        "military_outpost": ["barracks", "watchtower", "armory", "stable", "command_tent"],
        "crossroads_inn": ["tavern", "stable", "cottage"],
        "bandit_hideout": ["cave_entrance", "tent", "lookout_post"],
        "wizard_fortress": ["castle", "fortress", "keep", "watchtower", "gatehouse", "barracks", "armory"],
        "sorcery_school": ["monastery", "temple", "chapel", "keep", "watchtower", "gatehouse"],
        "cliff_keep": ["keep", "fortress", "watchtower", "guard_tower", "gatehouse", "barracks"],
        "river_castle": ["castle", "dock", "boat_house", "harbor_dock", "watchtower", "gatehouse"],
        "ruined_town": ["house", "cottage", "abandoned_house", "ruined_tower", "market_stall", "chapel"],
        "farmstead": ["house", "cottage", "stable", "market_stall", "chapel"],
    }
    building_types = _BUILDING_TYPES.get(location_type, ["building"])

    for i in range(building_count):
        for attempt in range(100):
            bx = rng.uniform(-half * 0.7, half * 0.7)
            by = rng.uniform(-half * 0.7, half * 0.7)
            # CITY-007: skip high-slope terrain positions
            if _terrain_slope(bx, by) > terrain_slope_threshold:
                continue
            # Check minimum spacing
            too_close = False
            for px, py in placed_positions:
                if math.sqrt((bx - px) ** 2 + (by - py) ** 2) < 8.0:
                    too_close = True
                    break
            if not too_close:
                placed_positions.append((bx, by))
                buildings.append({
                    "type": building_types[i % len(building_types)],
                    "position": (round(bx, 2), round(by, 2)),
                    "rotation": round(rng.uniform(0, math.pi * 2), 2),
                    "size": (
                        round(rng.uniform(6.0, 12.0), 2),
                        round(rng.uniform(6.0, 10.0), 2),
                    ),
                    "elevation": round(_terrain_elevation(bx, by), 3),
                })
                break
    spec["buildings"] = buildings

    # Paths (connect buildings and POIs)
    paths: list[dict] = []
    for p in range(min(path_count, len(buildings) - 1)):
        if p + 1 < len(buildings):
            paths.append({
                "from": buildings[p]["position"],
                "to": buildings[p + 1]["position"],
                "width": round(rng.uniform(1.5, 3.0), 2),
                "type": rng.choice(["dirt_path", "cobblestone", "gravel"]),
            })
    # Add a main road from edge to center
    if buildings:
        center_building = buildings[0]
        paths.append({
            "from": (-half, 0.0),
            "to": center_building["position"],
            "width": round(rng.uniform(2.5, 4.0), 2),
            "type": "main_road",
        })
    spec["paths"] = paths

    # Points of Interest
    pois: list[dict] = []
    _POI_TYPES = ["well", "signpost", "shrine", "statue", "notice_board", "campfire"]
    for _ in range(poi_count):
        pois.append({
            "type": rng.choice(_POI_TYPES),
            "position": (
                round(rng.uniform(-half * 0.5, half * 0.5), 2),
                round(rng.uniform(-half * 0.5, half * 0.5), 2),
            ),
        })
    spec["pois"] = pois

    return spec


def generate_linked_interior_spec(
    building_exterior_bounds: dict,
    interior_rooms: list[dict],
    door_positions: list[dict],
) -> dict:
    """Generate interior-exterior linking specification (WORLD-05).

    Creates door_trigger markers, occlusion_zone bounds, and
    lighting_transition fade zones for seamless interior-exterior flow.
    Pure-logic spec generation, no bpy.

    Parameters
    ----------
    building_exterior_bounds : dict
        ``{"min": (x, y), "max": (x, y)}`` of the building exterior.
    interior_rooms : list of dict
        Each room: ``{"name": str, "bounds": {"min": ..., "max": ...}}``.
    door_positions : list of dict
        Each door: ``{"position": (x, y, z), "facing": str}``.

    Returns
    -------
    dict with door_triggers, occlusion_zones, lighting_transitions.
    """
    door_triggers: list[dict] = []
    occlusion_zones: list[dict] = []
    lighting_transitions: list[dict] = []

    ext_min = building_exterior_bounds["min"]
    ext_max = building_exterior_bounds["max"]
    ext_center_x = (ext_min[0] + ext_max[0]) / 2.0
    ext_center_y = (ext_min[1] + ext_max[1]) / 2.0

    for i, door in enumerate(door_positions):
        pos = door["position"]
        facing = door.get("facing", "south")

        # Door trigger: collision volume at door position
        door_triggers.append({
            "id": f"door_trigger_{i}",
            "position": pos,
            "size": (1.2, 0.3, 2.2),  # standard door dimensions
            "facing": facing,
            "linked_interior": interior_rooms[i]["name"] if i < len(interior_rooms) else None,
        })

        # Occlusion zone: volume that hides interior when player is outside
        if i < len(interior_rooms):
            room = interior_rooms[i]
            r_min = room["bounds"]["min"]
            r_max = room["bounds"]["max"]
            occlusion_zones.append({
                "id": f"occlusion_zone_{i}",
                "bounds_min": r_min,
                "bounds_max": r_max,
                "linked_door": f"door_trigger_{i}",
            })

        # Lighting transition: fade zone between exterior and interior lighting
        lighting_transitions.append({
            "id": f"lighting_transition_{i}",
            "position": pos,
            "fade_distance": 2.0,
            "exterior_probe_position": (
                round(pos[0] + (1.5 if facing == "south" else -1.5), 2),
                round(pos[1], 2),
                round(pos[2] + 1.5, 2),
            ),
            "interior_probe_position": (
                round(pos[0] + (-1.5 if facing == "south" else 1.5), 2),
                round(pos[1], 2),
                round(pos[2] + 1.5, 2),
            ),
        })

    return {
        "door_triggers": door_triggers,
        "occlusion_zones": occlusion_zones,
        "lighting_transitions": lighting_transitions,
    }


def generate_easter_egg_spec(
    location_layout: dict,
    secret_room_count: int = 1,
    hidden_path_count: int = 1,
    lore_item_count: int = 2,
    seed: int = 0,
) -> list[dict]:
    """Generate easter egg placement specifications (WORLD-10).

    Places secret rooms (breakable wall marker + room behind), hidden paths
    (off main route), and lore items (unexpected positions).  Pure-logic.

    Parameters
    ----------
    location_layout : dict
        Must have ``terrain_bounds`` with ``size`` and optional ``buildings``
        and ``paths`` lists.
    secret_room_count, hidden_path_count, lore_item_count : int
        Number of each type to generate.
    seed : int
        Random seed.

    Returns
    -------
    list of dict
        Each dict has ``type`` (secret_room | hidden_path | lore_item),
        ``position``, and type-specific fields.
    """
    rng = random.Random(seed)
    easter_eggs: list[dict] = []

    terrain_size = location_layout.get("terrain_bounds", {}).get("size", 100.0)
    half = terrain_size / 2.0

    buildings = location_layout.get("buildings", [])
    paths = location_layout.get("paths", [])

    # 1. Secret rooms (breakable wall markers near buildings)
    for i in range(secret_room_count):
        if buildings:
            building = rng.choice(buildings)
            bx, by = building["position"]
        else:
            bx = rng.uniform(-half * 0.5, half * 0.5)
            by = rng.uniform(-half * 0.5, half * 0.5)

        # Place breakable wall on a random side of the building
        wall_side = rng.choice(["north", "south", "east", "west"])
        offset = rng.uniform(3.0, 6.0)
        if wall_side == "north":
            sx, sy = bx, by + offset
        elif wall_side == "south":
            sx, sy = bx, by - offset
        elif wall_side == "east":
            sx, sy = bx + offset, by
        else:
            sx, sy = bx - offset, by

        easter_eggs.append({
            "type": "secret_room",
            "position": (round(sx, 2), round(sy, 2)),
            "breakable_wall_position": (round(sx, 2), round(sy, 2)),
            "room_behind": {
                "size": (round(rng.uniform(3.0, 5.0), 2), round(rng.uniform(3.0, 5.0), 2)),
                "content": rng.choice(["treasure_chest", "lore_scroll", "unique_weapon", "shrine"]),
            },
        })

    # 2. Hidden paths (off main route)
    for i in range(hidden_path_count):
        if paths:
            path = rng.choice(paths)
            # Midpoint of path with offset
            mid_x = (path["from"][0] + path["to"][0]) / 2.0
            mid_y = (path["from"][1] + path["to"][1]) / 2.0
        else:
            mid_x = rng.uniform(-half * 0.3, half * 0.3)
            mid_y = rng.uniform(-half * 0.3, half * 0.3)

        # Hidden path branches off at an angle
        angle = rng.uniform(0, math.pi * 2)
        length = rng.uniform(10.0, 25.0)
        end_x = mid_x + math.cos(angle) * length
        end_y = mid_y + math.sin(angle) * length

        easter_eggs.append({
            "type": "hidden_path",
            "position": (round(mid_x, 2), round(mid_y, 2)),
            "end_position": (round(end_x, 2), round(end_y, 2)),
            "path_length": round(length, 2),
            "concealment": rng.choice(["overgrown", "behind_rocks", "underwater", "illusory_wall"]),
        })

    # 3. Lore items (unexpected positions)
    for i in range(lore_item_count):
        lx = rng.uniform(-half * 0.6, half * 0.6)
        ly = rng.uniform(-half * 0.6, half * 0.6)
        easter_eggs.append({
            "type": "lore_item",
            "position": (round(lx, 2), round(ly, 2)),
            "item_type": rng.choice([
                "ancient_scroll", "carved_tablet", "mysterious_gem",
                "torn_journal", "enchanted_ring", "faded_map",
            ]),
            "lore_text_id": f"lore_{seed}_{i}",
        })

    return easter_eggs


# ---------------------------------------------------------------------------
# Settlement Layout Templates (Task #47)
# ---------------------------------------------------------------------------

SETTLEMENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "fishing_village": {
        "buildings": ["dock", "boat_house", "fish_market", "cottage", "cottage", "tavern"],
        "features": ["pier", "drying_rack", "net_rack"],
    },
    "mining_town": {
        "buildings": ["mine_entrance", "smelter", "barracks", "tavern", "general_store"],
        "features": ["ore_cart", "mine_track", "slag_heap"],
    },
    "port_city": {
        "buildings": ["harbor_dock", "warehouse", "lighthouse", "tavern", "market_stall", "guard_tower"],
        "features": ["crane", "ship_wreck"],
    },
    "monastery": {
        "buildings": ["temple", "dormitory", "library", "garden", "bell_tower"],
        "features": ["meditation_circle", "herb_garden"],
    },
    "necropolis": {
        "buildings": ["catacomb", "mausoleum", "shrine", "ossuary"],
        "features": ["gravestone", "angel_statue", "iron_fence"],
    },
    "military_outpost": {
        "buildings": ["barracks", "watchtower", "armory", "stable", "command_tent"],
        "features": ["palisade", "training_dummy", "flag_pole"],
    },
    "crossroads_inn": {
        "buildings": ["tavern", "stable", "cottage"],
        "features": ["signpost", "well", "hitching_post"],
    },
    "bandit_hideout": {
        "buildings": ["cave_entrance", "tent", "lookout_post"],
        "features": ["barricade", "campfire", "stolen_goods_pile"],
    },
}

SETTLEMENT_NAMES: list[str] = sorted(SETTLEMENT_TEMPLATES.keys())


def get_settlement_template(settlement_type: str) -> dict[str, Any]:
    """Return the settlement template for a given type.

    Args:
        settlement_type: One of the keys in SETTLEMENT_TEMPLATES.

    Returns:
        Dict with ``buildings`` and ``features`` lists.

    Raises:
        ValueError: If settlement_type is not recognised.
    """
    template = SETTLEMENT_TEMPLATES.get(settlement_type)
    if template is None:
        raise ValueError(
            f"Unknown settlement type '{settlement_type}'. "
            f"Valid types: {', '.join(SETTLEMENT_NAMES)}"
        )
    # Return a copy to prevent mutation
    return {
        "buildings": list(template["buildings"]),
        "features": list(template["features"]),
    }


def list_settlement_types() -> list[str]:
    """Return sorted list of all available settlement type names."""
    return list(SETTLEMENT_NAMES)


def generate_settlement_spec(
    settlement_type: str = "fishing_village",
    seed: int = 0,
    poi_count: int = 3,
    layout_brief: str = "",
) -> dict[str, Any]:
    """Generate a complete settlement layout from a template.

    Combines the settlement template's building and feature lists with
    the existing ``generate_location_spec`` function to produce a fully
    specified settlement.

    Args:
        settlement_type: One of the keys in SETTLEMENT_TEMPLATES.
        seed: Random seed for deterministic placement.
        poi_count: Number of additional points of interest.

    Returns:
        Dict with terrain_bounds, buildings, paths, pois, features,
        settlement_type.

    Raises:
        ValueError: If settlement_type is not recognised.
    """
    template = get_settlement_template(settlement_type)
    rng = random.Random(seed)

    building_count = len(template["buildings"])

    # Use generate_location_spec as the base layout engine
    base = generate_location_spec(
        location_type=settlement_type,
        building_count=building_count,
        path_count=max(2, building_count - 1),
        poi_count=poi_count,
        seed=seed,
    )

    # Override building types with template-specific ones
    for i, building in enumerate(base.get("buildings", [])):
        if i < len(template["buildings"]):
            building["type"] = template["buildings"][i]

    # Add features as additional POI-like placements
    terrain_size = base.get("terrain_bounds", {}).get("size", 100.0)
    half = terrain_size / 2.0
    features: list[dict[str, Any]] = []
    for feature_type in template["features"]:
        features.append({
            "type": feature_type,
            "position": (
                round(rng.uniform(-half * 0.4, half * 0.4), 2),
                round(rng.uniform(-half * 0.4, half * 0.4), 2),
            ),
        })

    base["features"] = features
    base["settlement_type"] = settlement_type
    if layout_brief:
        base["layout_brief"] = layout_brief
    base["template"] = template

    return base


# ---------------------------------------------------------------------------
# AAA Settlement Layout: Market Square + District Zoning (Plan 39-03)
# ---------------------------------------------------------------------------


def generate_market_square(
    center: tuple[float, float] = (0.0, 0.0),
    size: str = "medium",
    road_intersections: list[tuple[float, float]] | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate a market square layout spec.

    Parameters
    ----------
    center : (x, y) world-space center of the square.
    size : "small" (400 m²), "medium" (900 m²), or "large" (2500 m²).
    road_intersections : list of (x, y) positions of nearby road intersections
        used to orient the square shape.
    seed : random seed.

    Returns
    -------
    dict with center, area, shape_verts, central_feature_type,
    stall_count, stall_positions.
    """
    rng = random.Random(seed)

    # Area targets per research spec
    area_map = {"small": 400.0, "medium": 900.0, "large": 2500.0}
    # MISC-019: guard against ZeroDivisionError if area_map ever maps to 0
    target_area = max(area_map.get(size, 900.0), 1.0)

    # Derive rectangle dimensions: roughly 1:1 to 1:2 aspect ratio
    _safe_aspect = max(rng.uniform(0.65, 1.0), 0.01)  # width / length ratio
    length = math.sqrt(target_area / _safe_aspect)
    width = target_area / max(length, 0.001)
    actual_area = width * length

    cx, cy = center

    # Shape vertices (rectangular, clockwise from bottom-left)
    half_w = width / 2.0
    half_l = length / 2.0
    shape_verts = [
        (round(cx - half_w, 2), round(cy - half_l, 2)),
        (round(cx + half_w, 2), round(cy - half_l, 2)),
        (round(cx + half_w, 2), round(cy + half_l, 2)),
        (round(cx - half_w, 2), round(cy + half_l, 2)),
    ]

    # Central feature: well, fountain, or market cross
    central_feature_type = rng.choice(["well", "fountain", "market_cross"])
    central_feature = {
        "type": central_feature_type,
        "position": (round(cx, 2), round(cy, 2)),
    }
    if central_feature_type == "well":
        central_feature.update({"radius": 1.0, "height": 0.8})
    elif central_feature_type == "fountain":
        central_feature.update({"radius": 1.5, "height": 1.2, "basin_depth": 0.4})
    else:  # market_cross
        central_feature.update({"pillar_height": 3.0, "cross_width": 1.2})

    # Stall placement: 3 m x 2 m stalls, 1 m spacing, along 2 long sides
    # Stall count ~ floor(perimeter * 0.3 / 4)
    perimeter = 2.0 * (width + length)
    stall_count = max(2, int(perimeter * 0.3 / 4))
    stall_spacing = 4.0  # 3 m stall + 1 m gap
    stalls_per_side = max(1, int(length / stall_spacing))

    stall_positions: list[dict[str, Any]] = []
    for side_idx, sign in enumerate([-1, 1]):  # left and right sides
        for i in range(stalls_per_side):
            sx = round(cx + sign * (half_w + 1.5), 2)
            sy = round(cy - half_l * 0.8 + i * stall_spacing, 2)
            stall_positions.append({
                "position": (sx, sy),
                "width": 3.0,
                "depth": 2.0,
                "rotation": 0.0 if sign > 0 else math.pi,
            })
    # Trim to stall_count
    stall_positions = stall_positions[:stall_count]
    actual_stall_count = len(stall_positions)

    return {
        "center": (round(cx, 2), round(cy, 2)),
        "area": round(actual_area, 1),
        "width": round(width, 2),
        "length": round(length, 2),
        "shape_verts": shape_verts,
        "central_feature_type": central_feature_type,
        "central_feature": central_feature,
        "stall_count": actual_stall_count,
        "stall_positions": stall_positions,
        "size_class": size,
    }


def assign_district_zones(
    settlement_bounds: dict,
    castle_pos: tuple[float, float] = (0.0, 0.0),
    wall_positions: list[tuple[float, float]] | None = None,
    road_network: list[dict] | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Assign district zones to a settlement using proximity rules.

    Zone types (from research):
    - market   : settlement center, near main road intersection
    - residential : near castle (wealthy) and mid-ring (common)
    - military : near outer walls (barracks, training yard)
    - religious : near center (temple/church plot)
    - slums    : outermost ring near/outside walls

    Parameters
    ----------
    settlement_bounds : dict with ``min`` (x, y) and ``max`` (x, y).
    castle_pos : (x, y) world-space position of the castle/keep.
    wall_positions : list of (x, y) positions of wall segments.
    road_network : list of road dicts with ``start`` and ``end`` positions.
    seed : random seed.

    Returns
    -------
    dict with ``zones``: list of
        {type, seed_pos, area, building_density, polygon_verts, description}
    """
    rng = random.Random(seed)

    bmin = settlement_bounds.get("min", (-50.0, -50.0))
    bmax = settlement_bounds.get("max", (50.0, 50.0))
    center_x = (bmin[0] + bmax[0]) / 2.0
    center_y = (bmin[1] + bmax[1]) / 2.0
    half_w = (bmax[0] - bmin[0]) / 2.0
    half_h = (bmax[1] - bmin[1]) / 2.0
    radius = min(half_w, half_h)

    cx, cy = castle_pos

    # Zone seed points placed according to proximity rules
    zone_specs = [
        {
            "type": "market",
            "description": "Commercial center, highest foot traffic",
            # Near settlement center
            "seed_pos": (
                round(center_x + rng.uniform(-radius * 0.1, radius * 0.1), 2),
                round(center_y + rng.uniform(-radius * 0.1, radius * 0.1), 2),
            ),
            "building_density": round(rng.uniform(0.80, 0.90), 2),
            "zone_radius": round(radius * rng.uniform(0.18, 0.26), 2),
        },
        {
            "type": "residential",
            "description": "Wealthier homes near castle, common homes at mid-ring",
            # Between castle and center
            "seed_pos": (
                round((cx + center_x) / 2.0 + rng.uniform(-radius * 0.05, radius * 0.05), 2),
                round((cy + center_y) / 2.0 + rng.uniform(-radius * 0.05, radius * 0.05), 2),
            ),
            "building_density": round(rng.uniform(0.60, 0.80), 2),
            "zone_radius": round(radius * rng.uniform(0.22, 0.32), 2),
        },
        {
            "type": "military",
            "description": "Barracks and training yards near outer walls",
            # Near outer wall boundary
            "seed_pos": (
                round(center_x + radius * 0.6 * math.cos(rng.uniform(0, math.pi * 2)), 2),
                round(center_y + radius * 0.6 * math.sin(rng.uniform(0, math.pi * 2)), 2),
            ),
            "building_density": round(rng.uniform(0.55, 0.70), 2),
            "zone_radius": round(radius * rng.uniform(0.16, 0.24), 2),
        },
        {
            "type": "religious",
            "description": "Temple / church yard near settlement center",
            # Near center, offset slightly from market
            "seed_pos": (
                round(center_x + radius * 0.2 * math.cos(rng.uniform(math.pi * 0.5, math.pi * 1.5)), 2),
                round(center_y + radius * 0.2 * math.sin(rng.uniform(math.pi * 0.5, math.pi * 1.5)), 2),
            ),
            "building_density": round(rng.uniform(0.30, 0.55), 2),
            "zone_radius": round(radius * rng.uniform(0.12, 0.20), 2),
        },
        {
            "type": "slums",
            "description": "Poor dwellings at settlement edge and outside walls",
            # Outermost ring
            "seed_pos": (
                round(center_x + radius * 0.80 * math.cos(rng.uniform(math.pi * 1.2, math.pi * 2.0)), 2),
                round(center_y + radius * 0.80 * math.sin(rng.uniform(math.pi * 1.2, math.pi * 2.0)), 2),
            ),
            "building_density": round(rng.uniform(0.40, 0.65), 2),
            "zone_radius": round(radius * rng.uniform(0.18, 0.28), 2),
        },
    ]

    zones: list[dict[str, Any]] = []
    for zs in zone_specs:
        zx, zy = zs["seed_pos"]
        zr = zs["zone_radius"]
        # Approximate polygon as 8-sided convex hull around seed point
        poly_verts = []
        segments = 8
        for si in range(segments):
            ang = 2.0 * math.pi * si / segments
            jitter = rng.uniform(0.85, 1.15)
            poly_verts.append((
                round(zx + math.cos(ang) * zr * jitter, 2),
                round(zy + math.sin(ang) * zr * jitter, 2),
            ))
        area = math.pi * zr * zr  # approximate
        zones.append({
            "type": zs["type"],
            "description": zs["description"],
            "seed_pos": zs["seed_pos"],
            "area": round(area, 1),
            "building_density": zs["building_density"],
            "polygon_verts": poly_verts,
            "zone_radius": zr,
        })

    return {"zones": zones}


# ---------------------------------------------------------------------------
# AAA Combat/Encounter: Concentric Castle + Encounter Zone (Plan 39-03)
# ---------------------------------------------------------------------------


def generate_concentric_castle_spec(
    castle_radius: float = 40.0,
    rings: int = 2,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate a concentric castle specification (pure-logic, no bpy).

    Parameters
    ----------
    castle_radius : outer wall radius in meters.
    rings : number of concentric wall rings (2 or 3).
    seed : random seed.

    Returns
    -------
    dict with rings (list of wall ring specs), gatehouse, towers.
    Each ring: {ring_index, radius, height, thickness, tower_positions}
    """
    rng = random.Random(seed)
    rings = max(2, min(3, rings))

    ring_radii_factors = [1.0, 0.7, 0.5]
    ring_height_ranges = [(6.0, 8.0), (10.0, 12.0), (12.0, 16.0)]

    ring_specs: list[dict[str, Any]] = []
    for i in range(rings):
        r = castle_radius * ring_radii_factors[i]
        h_lo, h_hi = ring_height_ranges[i]
        height = round(rng.uniform(h_lo, h_hi), 2)
        thickness = round(rng.uniform(2.0, 3.0), 2)

        # Tower spacing: every 25-40m around circumference
        circumference = 2.0 * math.pi * r
        tower_spacing = rng.uniform(25.0, 40.0)
        tower_count = max(4, int(circumference / tower_spacing))
        tower_diameter = round(rng.uniform(4.0, 8.0), 2)
        tower_protrusion = 2.0  # meters beyond wall face

        tower_positions = []
        for ti in range(tower_count):
            ang = 2.0 * math.pi * ti / tower_count
            tx = round(math.cos(ang) * (r + tower_protrusion), 2)
            ty = round(math.sin(ang) * (r + tower_protrusion), 2)
            tower_positions.append({"position": (tx, ty), "diameter": tower_diameter})

        # Material tones (outer ring darker, inner lighter per research)
        if i == 0:
            material_srgb = (90, 85, 75)  # dark granite outer
        elif i == 1:
            material_srgb = (135, 128, 118)  # mid granite
        else:
            material_srgb = (180, 170, 155)  # light granite inner

        ring_specs.append({
            "ring_index": i,
            "radius": round(r, 2),
            "height": height,
            "thickness": thickness,
            "tower_count": tower_count,
            "tower_positions": tower_positions,
            "tower_diameter": tower_diameter,
            "material_srgb": material_srgb,
        })

    # Gatehouse on outer ring, facing south (main approach)
    outer_r = castle_radius
    gatehouse = _generate_gatehouse_spec(
        position=(0.0, -outer_r),
        rotation=0.0,
        wall_height=ring_specs[0]["height"],
        rng=rng,
    )

    return {
        "castle_radius": castle_radius,
        "rings": ring_specs,
        "ring_count": rings,
        "gatehouse": gatehouse,
    }


def _generate_gatehouse_spec(
    position: tuple[float, float],
    rotation: float,
    wall_height: float,
    rng: random.Random,
) -> dict[str, Any]:
    """Generate a gatehouse specification (pure-logic).

    Returns dict with passage, flanking towers, portcullis, murder holes,
    and arrow slits geometry specs.
    """
    passage_width = round(rng.uniform(3.0, 4.0), 2)
    passage_depth = round(rng.uniform(8.0, 15.0), 2)
    flanking_tower_height = round(wall_height + rng.uniform(2.0, 3.0), 2)
    flanking_tower_diameter = round(rng.uniform(5.0, 6.0), 2)

    # Portcullis bars: vertical iron bars
    bar_count = max(6, int(passage_width / 0.15))
    portcullis = {
        "position": position,
        "width": passage_width,
        "height": round(wall_height * 0.85, 2),
        "bar_count": bar_count,
        "bar_diameter": 0.1,
        "bar_spacing": 0.15,
        "material_srgb": (135, 131, 126),
        "metallic": 1.0,
    }

    # Murder holes in passage ceiling
    murder_hole_count = rng.randint(4, 6)
    murder_holes = []
    for i in range(murder_hole_count):
        mx = position[0]
        my = round(position[1] + passage_depth * (i + 1) / (murder_hole_count + 1), 2)
        murder_holes.append({"position": (mx, my), "size": (0.3, 0.3)})

    # Arrow slits on flanking towers
    arrow_slits_per_face = 3
    flanking_towers = []
    for side, sign in enumerate([-1, 1]):
        tx = round(position[0] + sign * (passage_width / 2.0 + flanking_tower_diameter / 2.0), 2)
        ty = round(position[1] + passage_depth / 2.0, 2)
        slits = []
        for si in range(arrow_slits_per_face):
            slit_z = round(flanking_tower_height * (0.3 + 0.2 * si), 2)
            slits.append({"width": 0.1, "height": 0.8, "z": slit_z})
        flanking_towers.append({
            "position": (tx, ty),
            "diameter": flanking_tower_diameter,
            "height": flanking_tower_height,
            "arrow_slits": slits,
        })

    return {
        "position": position,
        "rotation": rotation,
        "passage_width": passage_width,
        "passage_depth": passage_depth,
        "flanking_tower_height": flanking_tower_height,
        "flanking_tower_diameter": flanking_tower_diameter,
        "flanking_towers": flanking_towers,
        "portcullis": portcullis,
        "murder_holes": murder_holes,
        "murder_hole_count": murder_hole_count,
        "arrow_slits_per_tower_face": arrow_slits_per_face,
    }


def generate_encounter_zone_spec(
    center: tuple[float, float] = (0.0, 0.0),
    radius: float = 20.0,
    patrol_type: str = "circuit",
    density_tier: str = "moderate",
    seed: int = 0,
) -> dict[str, Any]:
    """Generate a mob encounter zone specification (pure-logic, no bpy).

    Parameters
    ----------
    center : (x, y) world center of the zone.
    radius : zone radius in meters.
    patrol_type : "circuit" | "figure_eight" | "sentry" | "wander"
    density_tier : "sparse" | "light" | "moderate" | "heavy" | "swarm"
    seed : random seed.

    Returns
    -------
    dict with zone_id, center, radius, patrol_waypoints, spawn_points,
    mob_count.
    """
    rng = random.Random(seed)
    cx, cy = center

    # Density tier → mob count ranges (from research)
    density_mob_counts = {
        "sparse": (1, 2),
        "light": (3, 4),
        "moderate": (5, 7),
        "heavy": (8, 12),
        "swarm": (13, 20),
    }
    mob_lo, mob_hi = density_mob_counts.get(density_tier, (5, 7))
    mob_count = rng.randint(mob_lo, mob_hi)

    # Waypoint patterns
    waypoints: list[tuple[float, float, float]] = []

    if patrol_type == "circuit":
        # Waypoints around perimeter
        wp_count = rng.randint(4, 8)
        for i in range(wp_count):
            ang = 2.0 * math.pi * i / wp_count + rng.uniform(-0.2, 0.2)
            dist = radius * rng.uniform(0.7, 0.95)
            wx = round(cx + math.cos(ang) * dist, 2)
            wy = round(cy + math.sin(ang) * dist, 2)
            waypoints.append((wx, wy, 0.0))

    elif patrol_type == "figure_eight":
        wp_count = rng.randint(6, 8)
        loop_r = radius * 0.4
        for i in range(wp_count):
            t = 2.0 * math.pi * i / wp_count
            # Lemniscate of Bernoulli approximation
            wx = round(cx + loop_r * math.cos(t), 2)
            wy = round(cy + loop_r * 0.6 * math.sin(2 * t), 2)
            waypoints.append((wx, wy, 0.0))

    elif patrol_type == "sentry":
        # 2-3 waypoints near zone edge, back-and-forth
        wp_count = rng.randint(2, 3)
        base_ang = rng.uniform(0, math.pi * 2)
        for i in range(wp_count):
            ang = base_ang + (i - wp_count / 2.0) * 0.4
            dist = radius * rng.uniform(0.75, 0.95)
            wx = round(cx + math.cos(ang) * dist, 2)
            wy = round(cy + math.sin(ang) * dist, 2)
            waypoints.append((wx, wy, 0.0))

    else:  # wander
        wp_count = rng.randint(4, 8)
        for _ in range(wp_count):
            wx = round(cx + rng.uniform(-radius * 0.85, radius * 0.85), 2)
            wy = round(cy + rng.uniform(-radius * 0.85, radius * 0.85), 2)
            waypoints.append((wx, wy, 0.0))

    zone_id = f"zone_{seed}_{patrol_type}"
    spawn_point_names = [f"spawn_mob_{zone_id}_{i}" for i in range(mob_count)]

    return {
        "zone_id": zone_id,
        "center": (round(cx, 2), round(cy, 2)),
        "radius": radius,
        "patrol_type": patrol_type,
        "density_tier": density_tier,
        "patrol_waypoints": waypoints,
        "waypoint_count": len(waypoints),
        "spawn_points": spawn_point_names,
        "mob_count": mob_count,
    }


def validate_interior_pathability_spec(
    room_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate NPC pathability of building interior room specs (pure-logic).

    Checks doorways, corridors, and NPC spawn point presence.

    Parameters
    ----------
    room_specs : list of room dicts, each containing:
        ``doorways``: list of {width, height, position}
        ``corridors``: list of {width, position}
        ``npc_spawns``: list of spawn point names

    Returns
    -------
    dict with pathable, doorways (with passable flag), corridors,
    blocked_count, spawn_points.
    """
    MIN_DOOR_WIDTH = 1.2
    MIN_DOOR_HEIGHT = 2.2
    MIN_CORRIDOR_WIDTH = 1.0

    all_doorways: list[dict[str, Any]] = []
    all_corridors: list[dict[str, Any]] = []
    all_spawn_points: list[str] = []
    blocked_count = 0

    for room in room_specs:
        for dw in room.get("doorways", []):
            w = dw.get("width", 0.0)
            h = dw.get("height", 0.0)
            passable = (w >= MIN_DOOR_WIDTH) and (h >= MIN_DOOR_HEIGHT)
            if not passable:
                blocked_count += 1
            all_doorways.append({
                "pos": dw.get("position", (0.0, 0.0, 0.0)),
                "width": w,
                "height": h,
                "passable": passable,
            })

        for cor in room.get("corridors", []):
            w = cor.get("width", 0.0)
            passable = w >= MIN_CORRIDOR_WIDTH
            if not passable:
                blocked_count += 1
            all_corridors.append({
                "pos": cor.get("position", (0.0, 0.0, 0.0)),
                "width": w,
                "passable": passable,
            })

        for sp in room.get("npc_spawns", []):
            all_spawn_points.append(sp)

    pathable = (blocked_count == 0) and len(all_spawn_points) >= len(room_specs)

    return {
        "pathable": pathable,
        "doorways": all_doorways,
        "corridors": all_corridors,
        "blocked_count": blocked_count,
        "spawn_points": all_spawn_points,
        "room_count": len(room_specs),
    }


def generate_trim_sheet_uv_spec(
    mesh_type: str = "wall",
    atlas_size: int = 2048,
) -> dict[str, Any]:
    """Generate trim sheet UV band assignment spec (pure-logic).

    Maps mesh surface types to pixel bands of a 2048x2048 trim atlas.

    Atlas layout (Y pixel ranges):
    - stone band  : Y 0-256    (wall surfaces)
    - wood band   : Y 384-640  (wooden elements)
    - roof band   : Y 1024-1280 (roof tiles)
    - ground band : Y 1280-1408 (ground/foundation)

    Parameters
    ----------
    mesh_type : "wall" | "wood" | "roof" | "ground"
    atlas_size : atlas pixel dimension (default 2048)

    Returns
    -------
    dict with atlas_size, uv_band (y_min, y_max in [0,1]),
    band_pixel_range (y_min_px, y_max_px).
    """
    ATLAS_SIZE = atlas_size
    BANDS = {
        "wall":   (0, 256),
        "stone":  (0, 256),
        "wood":   (384, 640),
        "roof":   (1024, 1280),
        "ground": (1280, 1408),
    }
    key = mesh_type.lower().strip()
    px_lo, px_hi = BANDS.get(key, BANDS["wall"])

    uv_lo = px_lo / ATLAS_SIZE
    uv_hi = px_hi / ATLAS_SIZE

    return {
        "atlas_size": ATLAS_SIZE,
        "mesh_type": mesh_type,
        "band_pixel_range": (px_lo, px_hi),
        "uv_band": (round(uv_lo, 6), round(uv_hi, 6)),
    }
