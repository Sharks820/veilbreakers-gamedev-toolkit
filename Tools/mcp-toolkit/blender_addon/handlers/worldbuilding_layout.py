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

    # Materialize building plots as actual buildings instead of marker cubes.
    for i, plot in enumerate(town.building_plots):
        district = district_lookup.get(plot["district"], {})
        district_type = district.get("type", "residential")
        build_params = _structure_params(district_type, plot["size"], slot_index=i)
        structure_name = f"{name}_building_{i}"
        build_params.update({
            "name": structure_name,
            "seed": seed + i * 17,
        })
        handle_generate_building(build_params)

        building_obj = bpy.data.objects.get(structure_name)
        if building_obj is not None:
            px, py = plot["position"]
            building_obj.location = (px * cell_size, py * cell_size, 0.0)
            building_obj.rotation_euler = (0.0, 0.0, 0.0)
            building_obj.parent = parent
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
) -> WorldGraph:
    """Generate a connected world graph from location data (WORLD-04).

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

    Returns
    -------
    WorldGraph
        Graph with nodes and edges.
    """
    rng = random.Random(seed)

    nodes = [
        WorldGraphNode(
            name=loc["name"],
            location_type=loc.get("type", "generic"),
            position=(loc["position"][0], loc["position"][1]),
        )
        for loc in locations
    ]

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
) -> dict:
    """Generate a complete location specification (WORLD-01).

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
        for attempt in range(50):
            bx = rng.uniform(-half * 0.7, half * 0.7)
            by = rng.uniform(-half * 0.7, half * 0.7)
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
