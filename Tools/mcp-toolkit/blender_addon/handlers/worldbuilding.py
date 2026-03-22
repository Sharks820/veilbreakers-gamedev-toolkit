"""Blender handlers for building generation, castles, ruins, interiors, modular kits.

Converts pure-logic BuildingSpec operations into Blender mesh geometry.
Provides 5 handler functions registered in COMMAND_HANDLERS.

Includes VeilBreakers-specific building and dungeon presets for shrines,
ruined fortresses, abandoned villages, forges, and themed dungeons.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

import bpy
import bmesh

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# VeilBreakers Building Presets
# ---------------------------------------------------------------------------

VB_BUILDING_PRESETS: dict[str, dict] = {
    "shrine_minor": {
        "style": "gothic",
        "floors": 1,
        "width": 4.0, "depth": 4.0,
        "wall_height": 5.0,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "pointed_arch"},
            {"type": "window", "wall": "left", "floor": 0, "style": "pointed_arch"},
            {"type": "window", "wall": "right", "floor": 0, "style": "pointed_arch"},
        ],
        "props": ["altar", "candelabra", "prayer_mat"],
    },
    "shrine_major": {
        "style": "gothic",
        "floors": 2,
        "width": 8.0, "depth": 10.0,
        "wall_height": 6.0,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "pointed_arch"},
            {"type": "window", "wall": "left", "floor": 0, "style": "pointed_arch"},
            {"type": "window", "wall": "right", "floor": 0, "style": "pointed_arch"},
            {"type": "window", "wall": "left", "floor": 1, "style": "rose_window"},
            {"type": "window", "wall": "right", "floor": 1, "style": "rose_window"},
            {"type": "window", "wall": "back", "floor": 1, "style": "pointed_arch"},
        ],
        "props": ["altar_grand", "candelabra", "prayer_mat", "offering_bowl", "holy_symbol"],
    },
    "ruined_fortress_tower": {
        "style": "medieval",
        "floors": 3,
        "width": 6.0, "depth": 6.0,
        "wall_height": 4.0,
        "has_roof": False,  # ruined = no roof
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "square"},
            {"type": "window", "wall": "left", "floor": 1, "style": "arrow_slit"},
            {"type": "window", "wall": "right", "floor": 1, "style": "arrow_slit"},
            {"type": "window", "wall": "front", "floor": 2, "style": "arrow_slit"},
            {"type": "window", "wall": "back", "floor": 2, "style": "arrow_slit"},
        ],
        "props": ["weapon_rack_broken", "barrel", "crate"],
    },
    "abandoned_house": {
        "style": "medieval",
        "floors": 1,
        "width": 5.0, "depth": 6.0,
        "wall_height": 3.5,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "square"},
            {"type": "window", "wall": "left", "floor": 0, "style": "square"},
            {"type": "window", "wall": "right", "floor": 0, "style": "square"},
        ],
        "props": ["table_broken", "chair", "bed_frame", "cobweb"],
    },
    "forge": {
        "style": "fortress",
        "floors": 1,
        "width": 7.0, "depth": 8.0,
        "wall_height": 5.0,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "large_arch"},
            {"type": "window", "wall": "left", "floor": 0, "style": "large_rectangular"},
            {"type": "window", "wall": "right", "floor": 0, "style": "large_rectangular"},
        ],
        "props": ["anvil", "forge_fire", "bellows", "weapon_rack", "quench_trough"],
    },
}

# ---------------------------------------------------------------------------
# VeilBreakers Dungeon Presets
# ---------------------------------------------------------------------------

VB_DUNGEON_PRESETS: dict[str, dict] = {
    "abandoned_prison": {
        "width": 40, "height": 40,
        "min_room_size": 4, "max_depth": 5,
        "cell_size": 2.0, "wall_height": 3.0,
        "room_types": {"entrance": 1, "boss": 1, "treasure": 2, "secret": 1, "normal": -1},
        "monster_table": ["chainbound", "hollow", "mawling"],
        "props": ["shackle", "chain", "iron_maiden", "cell_door_broken"],
    },
    "corrupted_cave": {
        "width": 50, "height": 50,
        "min_room_size": 5, "max_depth": 6,
        "cell_size": 2.5, "wall_height": 4.0,
        "room_types": {"entrance": 1, "boss": 1, "treasure": 1, "secret": 2, "normal": -1},
        "monster_table": ["sporecaller", "grimthorn", "the_broodmother"],
        "props": ["stalactite", "mushroom_giant", "spider_web", "egg_cluster"],
    },
    "storm_peak": {
        "width": 35, "height": 35,
        "min_room_size": 4, "max_depth": 4,
        "cell_size": 2.0, "wall_height": 5.0,
        "room_types": {"entrance": 1, "boss": 1, "treasure": 1, "normal": -1},
        "monster_table": ["crackling", "voltgeist", "ironjaw"],
        "props": ["lightning_rod", "scorched_ground", "crystal_cluster"],
    },
    "veil_tear_dungeon": {
        "width": 45, "height": 45,
        "min_room_size": 5, "max_depth": 7,
        "cell_size": 2.0, "wall_height": 6.0,
        "room_types": {"entrance": 1, "boss": 1, "treasure": 3, "secret": 3, "normal": -1},
        "monster_table": ["bloodshade", "the_weeping", "flicker", "needlefang"],
        "props": ["void_crystal", "reality_crack", "floating_debris", "corruption_pool"],
    },
}

# ---------------------------------------------------------------------------
# VeilBreakers Landmark Presets -- unique one-of-a-kind world structures
# ---------------------------------------------------------------------------

# Maps landmark interior_rooms names -> valid _ROOM_CONFIGS keys for furnishing.
_LANDMARK_ROOM_TYPE_MAP: dict[str, str] = {
    "throne_room": "throne_room",
    "prison": "dungeon_cell",
    "shrine_room": "chapel",
    "guard_post": "guard_barracks",
    "storage": "armory",
    "smithy": "blacksmith",
    "barracks": "guard_barracks",
}

VB_LANDMARK_PRESETS: dict[str, dict] = {
    "the_congregation_lair": {
        "description": "Tutorial boss arena — abandoned village church consumed by darkness",
        "base_style": "gothic",
        "scale": 2.0,
        "floors": 2,
        "width": 15.0, "depth": 20.0,
        "wall_height": 8.0,
        "unique_features": ["corrupted_spire", "shattered_stained_glass", "soul_anchors", "darkness_veil"],
        "interior_rooms": ["throne_room", "prison", "shrine_room"],
        "corruption_level": 1.0,
        "props": ["bone_throne", "soul_cage", "dark_obelisk", "sacrificial_circle", "corruption_crystal"],
    },
    "wardens_prison": {
        "description": "Vex's origin — massive iron prison complex, chains everywhere",
        "base_style": "fortress",
        "scale": 1.5,
        "floors": 3,
        "width": 20.0, "depth": 25.0,
        "wall_height": 6.0,
        "unique_features": ["iron_gates", "guard_towers", "chain_bridges", "solitary_cells"],
        "interior_rooms": ["prison", "prison", "guard_post", "storage", "prison"],
        "corruption_level": 0.4,
        "props": ["shackle", "chain", "iron_maiden", "cell_door_broken", "weapon_rack"],
    },
    "thornwood_heart": {
        "description": "Ancient tree at the center of Thornwood Forest — sacred nature shrine",
        "base_style": "organic",
        "scale": 3.0,
        "floors": 1,
        "width": 10.0, "depth": 10.0,
        "wall_height": 15.0,
        "unique_features": ["giant_tree_trunk", "root_archways", "bioluminescent_fungi", "vine_bridges"],
        "interior_rooms": ["shrine_room"],
        "corruption_level": 0.1,
        "props": ["altar", "mushroom_cluster", "crystal_light", "offering_bowl", "prayer_mat"],
    },
    "veil_breach": {
        "description": "Major dimensional rift — reality torn open, floating debris, impossible geometry",
        "base_style": "chaotic",
        "scale": 2.5,
        "floors": 0,
        "width": 30.0, "depth": 30.0,
        "wall_height": 20.0,
        "unique_features": ["reality_crack", "floating_platforms", "inverted_gravity_zone", "void_portal"],
        "interior_rooms": [],
        "corruption_level": 0.9,
        "props": ["corruption_crystal", "veil_tear", "floating_rock", "void_tendril", "dark_obelisk"],
    },
    "storm_citadel": {
        "description": "Lightning-struck fortress on mountain peak — Voltgeist's domain",
        "base_style": "fortress",
        "scale": 2.0,
        "floors": 4,
        "width": 18.0, "depth": 18.0,
        "wall_height": 7.0,
        "unique_features": ["lightning_rods", "electrified_walls", "tesla_coil_towers", "storm_beacon"],
        "interior_rooms": ["throne_room", "smithy", "barracks", "storage"],
        "corruption_level": 0.6,
        "props": ["lightning_rod", "crystal_cluster", "brazier", "weapon_rack", "anvil"],
    },
    "broodmother_nest": {
        "description": "Massive spider cave — webs everywhere, egg sacs, chitinous walls",
        "base_style": "organic",
        "scale": 2.0,
        "floors": 1,
        "width": 25.0, "depth": 30.0,
        "wall_height": 10.0,
        "unique_features": ["web_canopy", "egg_chamber", "cocoon_gallery", "acid_pools"],
        "interior_rooms": ["storage", "prison"],
        "corruption_level": 0.7,
        "props": ["spider_web", "egg_cluster", "cocoon", "bone_pile", "skull_pile"],
    },
}


# ---------------------------------------------------------------------------
# Preset lookup helpers
# ---------------------------------------------------------------------------


def get_vb_building_preset(name: str) -> dict | None:
    """Return a VeilBreakers building preset by name, or None if not found."""
    return VB_BUILDING_PRESETS.get(name)


def get_vb_dungeon_preset(name: str) -> dict | None:
    """Return a VeilBreakers dungeon preset by name, or None if not found."""
    return VB_DUNGEON_PRESETS.get(name)


def get_vb_landmark_preset(name: str) -> dict | None:
    """Return a VeilBreakers landmark preset by name, or None if not found."""
    return VB_LANDMARK_PRESETS.get(name)

from ._building_grammar import (
    evaluate_building_grammar,
    generate_castle_spec,
    generate_tower_spec,
    generate_bridge_spec,
    generate_fortress_spec,
    apply_ruins_damage,
    generate_interior_layout,
    generate_modular_pieces,
    generate_overrun_variant,
    add_storytelling_props,
    BuildingSpec,
    STYLE_CONFIGS,
    MODULAR_CATALOG,
)
from ._dungeon_gen import generate_multi_floor_dungeon, generate_dungeon_prop_placements
from ._mesh_bridge import (
    mesh_from_spec,
    FURNITURE_GENERATOR_MAP,
    CASTLE_ELEMENT_MAP,
    DUNGEON_PROP_MAP,
)
from .worldbuilding_layout import (
    generate_boss_arena_spec,
    generate_easter_egg_spec,
    generate_linked_interior_spec,
    generate_location_spec,
    generate_world_graph,
    _ops_to_mesh,
)


# ---------------------------------------------------------------------------
# Pure-logic: BuildingSpec -> mesh primitive specs (testable without Blender)
# ---------------------------------------------------------------------------


def _building_ops_to_mesh_spec(spec: BuildingSpec) -> list[dict]:
    """Convert BuildingSpec operations to mesh primitive specs.

    Returns list of dicts describing vertices, faces, and metadata for each
    primitive. This is a pure-logic function -- no bpy/bmesh calls.

    Openings (windows/doors) are converted to recessed cutout boxes positioned
    on the correct wall, producing visible indentations in the geometry.
    """
    result: list[dict] = []

    # Collect wall ops indexed by (wall_index, floor) for opening placement
    wall_ops: dict[tuple[int, int], dict] = {}
    for op in spec.operations:
        if op.get("type") == "box" and op.get("role") == "wall":
            key = (op.get("wall_index", 0), op.get("floor", 0))
            wall_ops[key] = op

    for op in spec.operations:
        op_type = op.get("type")

        if op_type == "box":
            pos = op["position"]
            size = op["size"]
            px, py, pz = pos[0], pos[1], pos[2]
            sx, sy, sz = size[0], size[1], size[2]

            # 8 vertices of an axis-aligned box
            verts = [
                (px, py, pz),
                (px + sx, py, pz),
                (px + sx, py + sy, pz),
                (px, py + sy, pz),
                (px, py, pz + sz),
                (px + sx, py, pz + sz),
                (px + sx, py + sy, pz + sz),
                (px, py + sy, pz + sz),
            ]
            # 6 quad faces (each as 4-vertex index tuple)
            faces = [
                (0, 1, 2, 3),  # bottom
                (4, 7, 6, 5),  # top
                (0, 4, 5, 1),  # front
                (2, 6, 7, 3),  # back
                (0, 3, 7, 4),  # left
                (1, 5, 6, 2),  # right
            ]
            result.append({
                "type": "box",
                "vertices": verts,
                "faces": faces,
                "vertex_count": 8,
                "face_count": 6,
                "material": op.get("material", "default"),
                "role": op.get("role", "unknown"),
            })

        elif op_type == "cylinder":
            pos = op["position"]
            radius = op["radius"]
            height = op["height"]
            segments = op.get("segments", 16)
            cx, cy, cz = pos[0], pos[1], pos[2]

            verts = []
            # Bottom ring
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                vx = cx + math.cos(angle) * radius
                vy = cy + math.sin(angle) * radius
                verts.append((vx, vy, cz))
            # Top ring
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                vx = cx + math.cos(angle) * radius
                vy = cy + math.sin(angle) * radius
                verts.append((vx, vy, cz + height))

            # Side faces (quads connecting bottom and top rings)
            faces = []
            for i in range(segments):
                i_next = (i + 1) % segments
                faces.append((i, i_next, i_next + segments, i + segments))

            # Cap faces (n-gon)
            faces.append(tuple(range(segments)))  # bottom cap
            faces.append(tuple(range(segments, 2 * segments)))  # top cap

            result.append({
                "type": "cylinder",
                "vertices": verts,
                "faces": faces,
                "vertex_count": segments * 2,
                "face_count": segments + 2,
                "material": op.get("material", "default"),
                "role": op.get("role", "unknown"),
            })

        elif op_type == "opening":
            # Convert opening to a recessed cutout box on the wall surface.
            # This creates visible window/door indentations in the geometry.
            opening_spec = _opening_to_cutout_spec(op, wall_ops, spec)
            if opening_spec is not None:
                result.append(opening_spec)
            else:
                # Fallback: keep as opening marker for metadata
                result.append({
                    "type": "opening",
                    "wall_index": op.get("wall_index", 0),
                    "position": op.get("position", [0, 0]),
                    "size": op.get("size", [1, 1]),
                    "role": op.get("role", "opening"),
                    "face_construction": True,
                })

    return result


def _opening_to_cutout_spec(
    opening_op: dict,
    wall_ops: dict[tuple[int, int], dict],
    spec: BuildingSpec,
) -> dict | None:
    """Convert an opening operation into a recessed cutout box spec.

    Returns a mesh spec dict with vertices/faces for the cutout geometry,
    or None if the parent wall cannot be found.

    The cutout is a rectangular prism that penetrates the wall, creating
    a visible opening (window or door). Style-aware sizing is already
    encoded in the opening's size from the grammar.
    """
    wall_index = opening_op.get("wall_index", 0)
    floor_idx = opening_op.get("floor", 0)
    wall_key = (wall_index, floor_idx)
    wall = wall_ops.get(wall_key)
    if wall is None:
        return None

    wall_pos = wall["position"]
    wall_size = wall["size"]
    wall_px, wall_py, wall_pz = wall_pos[0], wall_pos[1], wall_pos[2]
    wall_sx, wall_sy, wall_sz = wall_size[0], wall_size[1], wall_size[2]

    # Opening position is (offset_along_wall, height_on_wall)
    open_pos = opening_op.get("position", [0, 0])
    open_size = opening_op.get("size", [1, 1])
    open_offset = open_pos[0]  # offset along wall length
    open_z = open_pos[1]       # height from wall base
    open_w = open_size[0]      # opening width
    open_h = open_size[1]      # opening height

    role = opening_op.get("role", "opening")
    style = opening_op.get("style", "square")

    # Compute the recess depth (slightly deeper than wall thickness)
    recess_depth = max(wall_sx, wall_sy) * 1.1

    # Determine cutout box position based on wall orientation
    # wall_index 0 = front (Y=0 face), 1 = back (Y=depth face),
    # 2 = left (X=0 face), 3 = right (X=width face)
    if wall_index == 0:
        # Front wall: extends along X, thin in Y
        cx = wall_px + open_offset
        cy = wall_py - 0.05  # slightly outside wall
        cz = wall_pz + open_z
        csx = open_w
        csy = recess_depth
        csz = open_h
    elif wall_index == 1:
        # Back wall: extends along X, thin in Y (anchored to far Y edge)
        cx = wall_px + open_offset
        cy = wall_py + wall_sy - open_offset - open_w
        cz = wall_pz + open_z
        csx = open_w
        csy = recess_depth
        csz = open_h
    elif wall_index == 2:
        # Left wall: extends along Y, thin in X
        cx = wall_px - 0.05
        cy = wall_py + open_offset
        cz = wall_pz + open_z
        csx = recess_depth
        csy = open_w
        csz = open_h
    else:
        # Right wall: extends along Y, thin in X (anchored to far X edge)
        cx = wall_px + wall_sx - recess_depth
        cy = wall_py + open_offset
        cz = wall_pz + open_z
        csx = recess_depth
        csy = open_w
        csz = open_h

    # Build cutout box vertices and faces (same as box primitive)
    verts = [
        (cx, cy, cz),
        (cx + csx, cy, cz),
        (cx + csx, cy + csy, cz),
        (cx, cy + csy, cz),
        (cx, cy, cz + csz),
        (cx + csx, cy, cz + csz),
        (cx + csx, cy + csy, cz + csz),
        (cx, cy + csy, cz + csz),
    ]
    faces = [
        (0, 1, 2, 3),  # bottom
        (4, 7, 6, 5),  # top
        (0, 4, 5, 1),  # front
        (2, 6, 7, 3),  # back
        (0, 3, 7, 4),  # left
        (1, 5, 6, 2),  # right
    ]

    return {
        "type": "opening_cutout",
        "vertices": verts,
        "faces": faces,
        "vertex_count": 8,
        "face_count": 6,
        "material": "opening_frame",
        "role": role,
        "style": style,
        "wall_index": wall_index,
        "floor": floor_idx,
        "is_cutout": True,
    }


# ---------------------------------------------------------------------------
# Pure-logic result builders (testable without Blender)
# ---------------------------------------------------------------------------


def _build_building_result(name: str, spec: BuildingSpec) -> dict:
    """Build handler return dict for a building from its spec."""
    mesh_specs = _building_ops_to_mesh_spec(spec)
    total_verts = sum(
        m.get("vertex_count", 0) for m in mesh_specs
        if m["type"] not in ("opening",)
    )
    total_faces = sum(
        m.get("face_count", 0) for m in mesh_specs
        if m["type"] not in ("opening",)
    )
    opening_count = sum(1 for m in mesh_specs if m.get("is_cutout"))
    materials = set()
    for m in mesh_specs:
        mat = m.get("material")
        if mat:
            materials.add(mat)
    return {
        "name": name,
        "style": spec.style,
        "floors": spec.floors,
        "footprint": list(spec.footprint),
        "vertex_count": total_verts,
        "face_count": total_faces,
        "material_count": len(materials),
        "opening_count": opening_count,
    }


def _build_castle_result(
    name: str, spec: BuildingSpec, procedural_mesh_count: int = 0,
) -> dict:
    """Build handler return dict for a castle from its spec."""
    roles = [op.get("role") for op in spec.operations]
    component_count = len(set(roles))
    return {
        "name": name,
        "component_count": component_count,
        "roles": list(set(roles)),
        "procedural_mesh_count": procedural_mesh_count,
    }


def _build_ruins_result(
    name: str,
    spec: BuildingSpec,
    original_style: str,
    damage_level: float,
) -> dict:
    """Build handler return dict for ruins."""
    debris_count = sum(1 for op in spec.operations if op.get("role") == "debris")
    return {
        "name": name,
        "original_style": original_style,
        "damage_level": damage_level,
        "debris_count": debris_count,
    }


def _build_interior_result(
    name: str,
    room_type: str,
    layout: list[dict],
    procedural_mesh_count: int = 0,
) -> dict:
    """Build handler return dict for interior layout."""
    return {
        "name": name,
        "room_type": room_type,
        "furniture_count": len(layout),
        "items": [item["type"] for item in layout],
        "procedural_mesh_count": procedural_mesh_count,
    }


def _build_modular_kit_result(
    pieces: list[dict],
    cell_size: float,
) -> dict:
    """Build handler return dict for modular kit."""
    return {
        "piece_count": len(pieces),
        "pieces": [p["name"] for p in pieces],
        "cell_size": cell_size,
    }


def _generate_landmark_unique_features(
    unique_features: list[str],
    width: float,
    depth: float,
    wall_height: float,
    scale: float,
    seed: int = 0,
) -> list[dict]:
    """Generate geometry operations for landmark unique features.

    Returns a list of BuildingSpec-compatible operation dicts (box/cylinder)
    representing the unique architectural elements of a landmark.
    Pure logic -- no bpy/bmesh calls.
    """
    import random as _random
    rng = _random.Random(seed)
    ops: list[dict] = []

    for feat in unique_features:
        if feat in ("corrupted_spire", "storm_beacon"):
            # Tall central spire/beacon
            radius = 0.8 * scale
            h = wall_height * 1.5 * scale
            ops.append({
                "type": "cylinder",
                "position": [width / 2 - radius, depth / 2 - radius, wall_height],
                "radius": radius,
                "height": h,
                "segments": 8,
                "material": "stone_dark",
                "role": "landmark_spire",
                "feature_name": feat,
            })
        elif feat in ("shattered_stained_glass", "iron_gates"):
            # Decorative panel on front wall
            panel_w = 3.0 * scale
            panel_h = wall_height * 0.6
            ops.append({
                "type": "box",
                "position": [width / 2 - panel_w / 2, -0.1, wall_height * 0.3],
                "size": [panel_w, 0.15, panel_h],
                "material": "glass_stained" if "glass" in feat else "iron",
                "role": "landmark_decoration",
                "feature_name": feat,
            })
        elif feat in ("soul_anchors", "lightning_rods", "tesla_coil_towers"):
            # 4 corner pylons
            for i in range(4):
                cx = (width - 1.0) * (i % 2)
                cy = (depth - 1.0) * (i // 2)
                ops.append({
                    "type": "cylinder",
                    "position": [cx, cy, 0],
                    "radius": 0.4 * scale,
                    "height": wall_height * 1.2,
                    "segments": 6,
                    "material": "metal_dark",
                    "role": "landmark_pylon",
                    "feature_name": feat,
                })
        elif feat in ("darkness_veil", "void_portal"):
            # Large translucent barrier/portal plane
            ops.append({
                "type": "box",
                "position": [width * 0.1, depth / 2 - 0.05, 0],
                "size": [width * 0.8, 0.1, wall_height],
                "material": "veil_energy",
                "role": "landmark_barrier",
                "feature_name": feat,
            })
        elif feat in ("guard_towers", "electrified_walls"):
            # Corner towers
            for i in range(4):
                cx = (width - 2.0) * (i % 2)
                cy = (depth - 2.0) * (i // 2)
                ops.append({
                    "type": "cylinder",
                    "position": [cx, cy, 0],
                    "radius": 1.5 * scale,
                    "height": wall_height * 1.4,
                    "segments": 12,
                    "material": "stone_fortified",
                    "role": "landmark_tower",
                    "feature_name": feat,
                })
        elif feat in ("chain_bridges", "vine_bridges"):
            # Bridge connecting two sides
            bridge_y = depth / 2 - 0.5
            ops.append({
                "type": "box",
                "position": [-2.0, bridge_y, wall_height * 0.7],
                "size": [width + 4.0, 1.0, 0.2],
                "material": "chain" if "chain" in feat else "wood_vine",
                "role": "landmark_bridge",
                "feature_name": feat,
            })
        elif feat in ("solitary_cells", "cocoon_gallery"):
            # Row of small enclosures along a wall
            cell_count = rng.randint(3, 5)
            spacing = depth / (cell_count + 1)
            for ci in range(cell_count):
                ops.append({
                    "type": "box",
                    "position": [-0.3, spacing * (ci + 1) - 1.0, 0],
                    "size": [2.0, 2.0, wall_height * 0.6],
                    "material": "iron" if "cell" in feat else "chitin",
                    "role": "landmark_enclosure",
                    "feature_name": feat,
                })
        elif feat in ("giant_tree_trunk",):
            # Massive central cylinder
            ops.append({
                "type": "cylinder",
                "position": [width / 2, depth / 2, 0],
                "radius": min(width, depth) * 0.3,
                "height": wall_height * scale,
                "segments": 24,
                "material": "bark",
                "role": "landmark_tree",
                "feature_name": feat,
            })
        elif feat in ("root_archways",):
            # Arching root structures at 4 cardinal points
            for i in range(4):
                angle_offset = i * (math.pi / 2)
                rx = width / 2 + math.cos(angle_offset) * width * 0.4
                ry = depth / 2 + math.sin(angle_offset) * depth * 0.4
                ops.append({
                    "type": "box",
                    "position": [rx - 0.5, ry - 0.5, 0],
                    "size": [1.0, 1.0, wall_height * 0.8],
                    "material": "root_wood",
                    "role": "landmark_archway",
                    "feature_name": feat,
                })
        elif feat in ("bioluminescent_fungi",):
            # Scattered glowing fungi clusters
            count = rng.randint(5, 8)
            for fi in range(count):
                fx = rng.uniform(0.5, width - 0.5)
                fy = rng.uniform(0.5, depth - 0.5)
                ops.append({
                    "type": "cylinder",
                    "position": [fx, fy, 0],
                    "radius": rng.uniform(0.2, 0.5),
                    "height": rng.uniform(0.3, 1.2),
                    "segments": 8,
                    "material": "bioluminescent",
                    "role": "landmark_flora",
                    "feature_name": feat,
                })
        elif feat in ("reality_crack",):
            # Jagged vertical crack through the center
            ops.append({
                "type": "box",
                "position": [width / 2 - 0.1, 0, 0],
                "size": [0.2, depth, wall_height],
                "material": "void_energy",
                "role": "landmark_crack",
                "feature_name": feat,
            })
        elif feat in ("floating_platforms", "inverted_gravity_zone"):
            # Floating debris platforms at various heights
            count = rng.randint(4, 7)
            for pi in range(count):
                px = rng.uniform(2.0, width - 2.0)
                py = rng.uniform(2.0, depth - 2.0)
                pz = rng.uniform(wall_height * 0.3, wall_height * 0.9)
                ops.append({
                    "type": "box",
                    "position": [px - 1.0, py - 1.0, pz],
                    "size": [
                        rng.uniform(1.5, 3.0),
                        rng.uniform(1.5, 3.0),
                        rng.uniform(0.3, 0.8),
                    ],
                    "material": "stone_corrupted",
                    "role": "landmark_floating",
                    "feature_name": feat,
                })
        elif feat in ("web_canopy",):
            # Ceiling web layer
            ops.append({
                "type": "box",
                "position": [0, 0, wall_height * 0.85],
                "size": [width, depth, 0.15],
                "material": "spider_silk",
                "role": "landmark_canopy",
                "feature_name": feat,
            })
        elif feat in ("egg_chamber",):
            # Central bulbous chamber
            ops.append({
                "type": "cylinder",
                "position": [width / 2, depth / 2, 0],
                "radius": min(width, depth) * 0.25,
                "height": wall_height * 0.6,
                "segments": 16,
                "material": "chitin",
                "role": "landmark_chamber",
                "feature_name": feat,
            })
        elif feat in ("acid_pools",):
            # Floor-level pools
            pool_count = rng.randint(2, 4)
            for ai in range(pool_count):
                ax = rng.uniform(2.0, width - 2.0)
                ay = rng.uniform(2.0, depth - 2.0)
                ops.append({
                    "type": "cylinder",
                    "position": [ax, ay, 0],
                    "radius": rng.uniform(1.0, 2.5),
                    "height": 0.05,
                    "segments": 12,
                    "material": "acid",
                    "role": "landmark_hazard",
                    "feature_name": feat,
                })
        else:
            # Generic fallback: decorative pillar/marker
            ops.append({
                "type": "cylinder",
                "position": [
                    rng.uniform(1.0, width - 1.0),
                    rng.uniform(1.0, depth - 1.0),
                    0,
                ],
                "radius": 0.5 * scale,
                "height": wall_height * 0.5,
                "segments": 8,
                "material": "stone_dark",
                "role": "landmark_feature",
                "feature_name": feat,
            })

    return ops


def _apply_corruption_tint(
    corruption_level: float,
) -> dict:
    """Compute corruption color tint based on corruption_level (0.0-1.0).

    Returns a dict with base_color RGBA and material metadata.
    Pure logic -- no bpy calls.
    """
    # Lerp from clean stone grey (0.6, 0.58, 0.55) to corrupted dark purple (0.15, 0.05, 0.12)
    t = max(0.0, min(1.0, corruption_level))
    r = 0.6 - 0.45 * t
    g = 0.58 - 0.53 * t
    b = 0.55 - 0.43 * t
    a = 1.0
    return {
        "base_color": [round(r, 4), round(g, 4), round(b, 4), a],
        "corruption_level": t,
        "material_name": "landmark_corrupted" if t > 0.3 else "landmark_clean",
        "emission_strength": t * 0.5,  # corrupted surfaces glow faintly
    }


def _build_landmark_result(
    name: str,
    preset: dict,
    spec: BuildingSpec | None,
    unique_feature_ops: list[dict],
    room_layouts: dict[str, list[dict]],
    corruption_tint: dict,
) -> dict:
    """Build handler return dict for a landmark.

    Pure logic -- no bpy calls. Assembles all landmark metadata into the
    result dict returned by handle_generate_landmark.
    """
    # Count mesh elements from the building spec
    if spec is not None:
        mesh_specs = _building_ops_to_mesh_spec(spec)
        structure_verts = sum(
            m.get("vertex_count", 0) for m in mesh_specs
            if m["type"] not in ("opening",)
        )
        structure_faces = sum(
            m.get("face_count", 0) for m in mesh_specs
            if m["type"] not in ("opening",)
        )
    else:
        structure_verts = 0
        structure_faces = 0

    # Count unique feature elements
    feature_count = len(unique_feature_ops)
    feature_roles = list({op.get("role", "unknown") for op in unique_feature_ops})

    # Count furnished room items
    total_furniture = sum(len(layout) for layout in room_layouts.values())
    rooms_furnished = list(room_layouts.keys())

    return {
        "name": name,
        "description": preset.get("description", ""),
        "base_style": preset.get("base_style", "gothic"),
        "scale": preset.get("scale", 1.0),
        "floors": preset.get("floors", 1),
        "footprint": [preset.get("width", 10.0), preset.get("depth", 10.0)],
        "wall_height": preset.get("wall_height", 5.0),
        "corruption_level": preset.get("corruption_level", 0.0),
        "corruption_tint": corruption_tint,
        "structure_vertex_count": structure_verts,
        "structure_face_count": structure_faces,
        "unique_feature_count": feature_count,
        "unique_feature_roles": feature_roles,
        "unique_features": preset.get("unique_features", []),
        "rooms_furnished": rooms_furnished,
        "total_furniture": total_furniture,
        "props": preset.get("props", []),
    }


# ---------------------------------------------------------------------------
# Blender geometry construction helpers
# ---------------------------------------------------------------------------


def _spec_to_bmesh(spec: BuildingSpec) -> bmesh.types.BMesh:
    """Convert a BuildingSpec into a single bmesh with all geometry.

    Handles box, cylinder, and opening_cutout primitives.  Opening cutouts
    are added as geometry; boolean subtraction from walls is performed when
    bmesh boolean is available, otherwise the cutout box is added as-is to
    create visible recessed openings.
    """
    bm = bmesh.new()
    mesh_specs = _building_ops_to_mesh_spec(spec)

    for ms in mesh_specs:
        if ms["type"] == "opening":
            continue  # pure-marker openings (fallback) -- skip

        verts = ms["vertices"]
        faces = ms["faces"]

        # Add vertices
        bm_verts = []
        for v in verts:
            bm_verts.append(bm.verts.new(v))

        bm.verts.ensure_lookup_table()

        # Add faces
        for face_indices in faces:
            try:
                face_verts = [bm_verts[i] for i in face_indices]
                bm.faces.new(face_verts)
            except (ValueError, IndexError):
                logger.warning("Skipping degenerate face in spec-to-bmesh conversion")

    return bm


def _create_mesh_object(name: str, bm: bmesh.types.BMesh) -> Any:
    """Create a Blender mesh object from a bmesh."""
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# Building weathering deformation
# ---------------------------------------------------------------------------


def _apply_weathering(
    spec: BuildingSpec,
    weathering_level: float,
    seed: int = 0,
) -> BuildingSpec:
    """Apply procedural weathering deformation to a building spec.

    Modifies the building's operations list to add visual wear:
    - Wall cracks: thin box cutouts at random positions on walls
    - Edge wear: inward vertex offsets on corner wall edges (chamfer sim)
    - Roof sag: downward vertex offsets on roof geometry
    - Moss/debris: small prop-like box specs at building base

    Parameters
    ----------
    spec : BuildingSpec
        The building spec to weather (not mutated; returns a new spec).
    weathering_level : float
        0.0 = pristine, 1.0 = heavily ruined.  Clamped to [0, 1].
    seed : int
        Random seed for deterministic weathering.

    Returns
    -------
    BuildingSpec
        New spec with weathering operations appended.
    """
    level = max(0.0, min(1.0, weathering_level))
    if level <= 0.0:
        return spec

    rng = random.Random(seed)
    new_ops = list(spec.operations)

    width, depth = spec.footprint

    # --- 1. Wall cracks: thin box cutouts on wall surfaces ---
    num_cracks = int(round(level * rng.randint(3, 5)))
    wall_ops = [
        op for op in spec.operations
        if op.get("type") == "box" and op.get("role") == "wall"
    ]
    for _ in range(num_cracks):
        if not wall_ops:
            break
        wall = rng.choice(wall_ops)
        w_pos = wall["position"]
        w_size = wall["size"]
        # Crack is a thin box on the wall surface
        crack_w = rng.uniform(0.3, 0.8)
        crack_h = rng.uniform(0.5, 1.5)
        crack_depth = 0.05
        # Random position along wall
        offset_x = rng.uniform(0.1, max(0.2, w_size[0] - crack_w - 0.1))
        offset_z = rng.uniform(0.1, max(0.2, w_size[2] - crack_h - 0.1))
        new_ops.append({
            "type": "box",
            "position": [
                w_pos[0] + offset_x,
                w_pos[1] - crack_depth * 0.5,
                w_pos[2] + offset_z,
            ],
            "size": [crack_w, crack_depth, crack_h],
            "material": "crack",
            "role": "weathering_crack",
        })

    # --- 2. Edge wear: shrink corner wall boxes inward slightly ---
    edge_wear_amount = level * rng.uniform(0.1, 0.3)
    for op in new_ops:
        if op.get("role") == "wall" and op.get("type") == "box":
            # Shrink wall size slightly to simulate worn edges
            original_size = list(op["size"])
            original_pos = list(op["position"])
            # Reduce the long axis by edge_wear_amount and shift inward
            for axis in range(3):
                if original_size[axis] > 1.0:
                    shrink = edge_wear_amount * rng.uniform(0.3, 1.0)
                    original_size[axis] -= shrink
                    original_pos[axis] += shrink * 0.5
            op["size"] = original_size
            op["position"] = original_pos

    # --- 3. Roof sag: push roof vertices downward ---
    roof_sag_amount = level * rng.uniform(0.2, 0.5)
    for op in new_ops:
        if op.get("role") == "roof" and op.get("type") == "box":
            pos = list(op["position"])
            # Sag center of roof downward
            pos[2] -= roof_sag_amount * rng.uniform(0.3, 1.0)
            op["position"] = pos

    # --- 4. Moss/debris: small prop specs at building base ---
    num_debris = int(round(level * rng.randint(5, 10)))
    debris_types = [
        ("rubble_pile", (0.3, 0.3, 0.2)),
        ("moss_patch", (0.5, 0.5, 0.05)),
        ("fallen_stone", (0.2, 0.2, 0.15)),
        ("debris_chunk", (0.25, 0.25, 0.1)),
    ]
    for _ in range(num_debris):
        dtype, dsize = rng.choice(debris_types)
        # Place around building perimeter at ground level
        side = rng.choice(["front", "back", "left", "right"])
        if side == "front":
            dx = rng.uniform(-width * 0.4, width * 0.4)
            dy = -depth * 0.5 - rng.uniform(0.2, 1.5)
        elif side == "back":
            dx = rng.uniform(-width * 0.4, width * 0.4)
            dy = depth * 0.5 + rng.uniform(0.2, 1.5)
        elif side == "left":
            dx = -width * 0.5 - rng.uniform(0.2, 1.5)
            dy = rng.uniform(-depth * 0.4, depth * 0.4)
        else:
            dx = width * 0.5 + rng.uniform(0.2, 1.5)
            dy = rng.uniform(-depth * 0.4, depth * 0.4)

        scale = rng.uniform(0.6, 1.4)
        new_ops.append({
            "type": "box",
            "position": [dx, dy, 0.0],
            "size": [dsize[0] * scale, dsize[1] * scale, dsize[2] * scale],
            "material": dtype,
            "role": "weathering_debris",
        })

    return BuildingSpec(
        footprint=spec.footprint,
        floors=spec.floors,
        style=spec.style,
        operations=new_ops,
    )


# ---------------------------------------------------------------------------
# Handler Functions
# ---------------------------------------------------------------------------


def handle_generate_building(params: dict) -> dict:
    """Generate a building from grammar rules.

    Params:
        name: object name (default "Building")
        preset: VB building preset name (optional, overrides defaults)
        width: building width (default 10)
        depth: building depth (default 8)
        floors: number of floors (default 2)
        style: style preset name (default "medieval")
        seed: random seed (default 0)
        weathering_level: 0.0-1.0, controls cracks/edge wear/roof sag/debris (default 0.0)
    """
    logger.info("Generating building")

    # Apply VB preset defaults if specified
    preset_name = params.get("preset")
    preset = get_vb_building_preset(preset_name) if preset_name else None
    if preset_name and preset is None:
        raise ValueError(
            f"Unknown VB building preset '{preset_name}'. "
            f"Valid: {list(VB_BUILDING_PRESETS.keys())}"
        )

    name = params.get("name", (preset_name or "Building"))
    width = params.get("width", preset["width"] if preset else 10)
    depth = params.get("depth", preset["depth"] if preset else 8)
    floors = params.get("floors", preset["floors"] if preset else 2)
    style = params.get("style", preset["style"] if preset else "medieval")
    seed = params.get("seed", 0)
    weathering_level = params.get("weathering_level", 0.0)

    if style not in STYLE_CONFIGS:
        raise ValueError(f"Unknown style '{style}'. Valid: {list(STYLE_CONFIGS.keys())}")

    spec = evaluate_building_grammar(width, depth, floors, style, seed)

    # Apply weathering deformation after base generation
    if weathering_level > 0.0:
        spec = _apply_weathering(spec, weathering_level, seed)

    # Create Blender geometry
    bm = _spec_to_bmesh(spec)
    obj = _create_mesh_object(name, bm)

    result = _build_building_result(name, spec)
    result["weathering_level"] = weathering_level
    if preset:
        result["preset"] = preset_name
        result["preset_props"] = preset.get("props", [])
        result["preset_openings"] = preset.get("openings", [])
        result["preset_has_roof"] = preset.get("has_roof", True)
    return {"status": "success", "result": result}


def handle_generate_castle(params: dict) -> dict:
    """Generate a castle with curtain walls, towers, keep, gatehouse.

    Params:
        name: object name (default "Castle")
        outer_size: castle outer dimension (default 40)
        keep_size: keep building size (default 12)
        tower_count: number of corner towers (default 4)
        style: style for the keep (default "fortress")
        seed: random seed (default 0)
    """
    logger.info("Generating castle")
    name = params.get("name", "Castle")
    outer_size = params.get("outer_size", 40)
    keep_size = params.get("keep_size", 12)
    tower_count = params.get("tower_count", 4)
    seed = params.get("seed", 0)

    spec = generate_castle_spec(outer_size, keep_size, tower_count, seed)

    bm = _spec_to_bmesh(spec)
    obj = _create_mesh_object(name, bm)

    # Add procedural castle detail elements
    details_coll = bpy.data.collections.new(f"{name}_CastleDetails")
    bpy.context.scene.collection.children.link(details_coll)

    half = outer_size / 2.0
    procedural_count = 0

    # Gate at front center
    gate_entry = CASTLE_ELEMENT_MAP.get("gate")
    if gate_entry is not None:
        gen_func, gen_kwargs = gate_entry
        gate_spec = gen_func(**gen_kwargs)
        mesh_from_spec(
            gate_spec,
            name=f"{name}_gate",
            location=(0, half, 0),
            collection=details_coll,
            parent=obj,
        )
        procedural_count += 1

    # Ramparts along wall tops (4 sides)
    rampart_entry = CASTLE_ELEMENT_MAP.get("rampart")
    if rampart_entry is not None:
        gen_func, gen_kwargs = rampart_entry
        rampart_spacing = 4.0
        num_per_side = max(1, int(outer_size / rampart_spacing))
        for side_idx, (sx, sy, angle) in enumerate([
            (1, 0, 0),       # east wall
            (-1, 0, math.pi),  # west wall
            (0, 1, math.pi / 2),   # north wall
            (0, -1, -math.pi / 2),  # south wall
        ]):
            for i in range(num_per_side):
                t = -half + (i + 0.5) * rampart_spacing
                if abs(t) > half:
                    continue
                if sx != 0:
                    px, py = sx * half, t
                else:
                    px, py = t, sy * half
                ramp_spec = gen_func(**gen_kwargs)
                mesh_from_spec(
                    ramp_spec,
                    name=f"{name}_rampart_{side_idx}_{i}",
                    location=(px, py, 0),
                    rotation=(0, 0, angle),
                    collection=details_coll,
                    parent=obj,
                )
                procedural_count += 1

    # Drawbridge at gate position, extending outward
    draw_entry = CASTLE_ELEMENT_MAP.get("drawbridge")
    if draw_entry is not None:
        gen_func, gen_kwargs = draw_entry
        draw_spec = gen_func(**gen_kwargs)
        mesh_from_spec(
            draw_spec,
            name=f"{name}_drawbridge",
            location=(0, half + 2.0, 0),
            collection=details_coll,
            parent=obj,
        )
        procedural_count += 1

    # Fountain at courtyard center
    fountain_entry = CASTLE_ELEMENT_MAP.get("fountain")
    if fountain_entry is not None:
        gen_func, gen_kwargs = fountain_entry
        fountain_spec = gen_func(**gen_kwargs)
        mesh_from_spec(
            fountain_spec,
            name=f"{name}_fountain",
            location=(0, 0, 0),
            collection=details_coll,
            parent=obj,
        )
        procedural_count += 1

    result = _build_castle_result(name, spec, procedural_count)
    return {"status": "success", "result": result}


def handle_generate_ruins(params: dict) -> dict:
    """Generate ruins by damaging a building spec.

    Params:
        name: object name (default "Ruins")
        width: source building width (default 10)
        depth: source building depth (default 8)
        floors: source building floors (default 2)
        style: source building style (default "medieval")
        damage_level: 0.0-1.0 destruction intensity (default 0.5)
        seed: random seed (default 0)
    """
    logger.info("Generating ruins")
    name = params.get("name", "Ruins")
    width = params.get("width", 10)
    depth = params.get("depth", 8)
    floors = params.get("floors", 2)
    style = params.get("style", "medieval")
    damage_level = params.get("damage_level", 0.5)
    seed = params.get("seed", 0)

    if style not in STYLE_CONFIGS:
        raise ValueError(f"Unknown style '{style}'. Valid: {list(STYLE_CONFIGS.keys())}")

    spec = evaluate_building_grammar(width, depth, floors, style, seed)
    damaged = apply_ruins_damage(spec, damage_level, seed)

    # Create main structure
    bm = _spec_to_bmesh(damaged)
    obj = _create_mesh_object(name, bm)

    result = _build_ruins_result(name, damaged, style, damage_level)
    return {"status": "success", "result": result}


def handle_generate_interior(params: dict) -> dict:
    """Generate interior furniture layout for a room.

    Params:
        name: room name (default "Interior")
        room_type: type of room (default "tavern")
        width: room width (default 8)
        depth: room depth (default 6)
        height: room height (default 3.0)
        seed: random seed (default 0)
    """
    logger.info("Generating interior layout")
    name = params.get("name", "Interior")
    room_type = params.get("room_type", "tavern")
    width = params.get("width", 8)
    depth = params.get("depth", 6)
    height = params.get("height", 3.0)
    seed = params.get("seed", 0)

    layout = generate_interior_layout(room_type, width, depth, height, seed)

    # Create an empty as the room parent
    room_empty = bpy.data.objects.new(name, None)
    room_empty.empty_display_type = "CUBE"
    room_empty.empty_display_size = max(width, depth) / 2
    bpy.context.collection.objects.link(room_empty)

    procedural_count = 0
    for item in layout:
        item_name = f"{name}_{item['type']}"
        item_type = item["type"]
        sx, sy, sz = item["scale"]

        gen_entry = FURNITURE_GENERATOR_MAP.get(item_type)
        if gen_entry is not None:
            # Use procedural mesh generator
            gen_func, gen_kwargs = gen_entry
            spec = gen_func(**gen_kwargs)
            item_obj = mesh_from_spec(
                spec,
                name=item_name,
                location=tuple(item["position"]),
                rotation=(0, 0, item["rotation"]),
                scale=(sx, sy, sz),
                parent=room_empty,
            )
            procedural_count += 1
        else:
            # Fallback: cube for unmapped furniture types
            item_bm = bmesh.new()
            bmesh.ops.create_cube(item_bm, size=1.0)
            for v in item_bm.verts:
                v.co.x *= sx
                v.co.y *= sy
                v.co.z *= sz
                v.co.z += sz / 2
            item_mesh = bpy.data.meshes.new(item_name)
            item_bm.to_mesh(item_mesh)
            item_bm.free()
            item_obj = bpy.data.objects.new(item_name, item_mesh)
            item_obj.location = tuple(item["position"])
            item_obj.rotation_euler = (0, 0, item["rotation"])
            item_obj.parent = room_empty
            bpy.context.collection.objects.link(item_obj)

    result = _build_interior_result(name, room_type, layout, procedural_count)
    return {"status": "success", "result": result}


def handle_generate_modular_kit(params: dict) -> dict:
    """Generate modular architecture kit pieces.

    Params:
        name_prefix: object name prefix (default "ModKit")
        cell_size: grid cell size in meters (default 2.0)
        pieces: list of piece names or null for all (default None)
    """
    logger.info("Generating modular kit")
    name_prefix = params.get("name_prefix", "ModKit")
    cell_size = params.get("cell_size", 2.0)
    piece_names = params.get("pieces", None)

    pieces = generate_modular_pieces(cell_size, piece_names)

    for piece in pieces:
        piece_name = f"{name_prefix}_{piece['name']}"
        dims = piece["dimensions"]

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)

        # Scale and position so origin is at corner (0,0,0)
        for v in bm.verts:
            v.co.x = (v.co.x + 0.5) * dims[0]
            v.co.y = (v.co.y + 0.5) * dims[1]
            v.co.z = (v.co.z + 0.5) * dims[2]

        mesh = bpy.data.meshes.new(piece_name)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(piece_name, mesh)
        bpy.context.collection.objects.link(obj)

        # Store metadata as custom properties
        obj["cell_size"] = cell_size
        obj["piece_type"] = piece["name"]
        obj["connection_points"] = str(piece["connection_points"])

    result = _build_modular_kit_result(pieces, cell_size)
    return {"status": "success", "result": result}


# ---------------------------------------------------------------------------
# World Design Handler Functions (WORLD-01 through WORLD-10)
# ---------------------------------------------------------------------------


def handle_generate_location(params: dict) -> dict:
    """Generate a complete explorable location (WORLD-01).

    Composes terrain base + buildings + paths + POIs as Blender objects.

    Params:
        name: location name (default "Location")
        location_type: village/fortress/dungeon_entrance/camp (default "village")
        building_count: number of buildings (default 5)
        path_count: number of connecting paths (default 3)
        poi_count: number of points of interest (default 2)
        seed: random seed (default 0)
    """
    logger.info("Generating location")
    name = params.get("name", "Location")
    location_type = params.get("location_type", "village")
    building_count = params.get("building_count", 5)
    path_count = params.get("path_count", 3)
    poi_count = params.get("poi_count", 2)
    seed = params.get("seed", 0)

    spec = generate_location_spec(
        location_type=location_type,
        building_count=building_count,
        path_count=path_count,
        poi_count=poi_count,
        seed=seed,
    )

    # Create terrain base as a plane
    terrain = spec["terrain_bounds"]
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.empty_display_size = terrain["size"] / 2
    bpy.context.collection.objects.link(parent)

    # Create building markers
    for b in spec["buildings"]:
        b_name = f"{name}_{b['type']}"
        b_obj = bpy.data.objects.new(b_name, None)
        b_obj.empty_display_type = "CUBE"
        b_obj.empty_display_size = b["size"][0] / 2
        b_obj.location = (b["position"][0], b["position"][1], 0)
        b_obj.rotation_euler = (0, 0, b["rotation"])
        b_obj.parent = parent
        bpy.context.collection.objects.link(b_obj)

    # Create POI markers
    for p in spec["pois"]:
        p_name = f"{name}_poi_{p['type']}"
        p_obj = bpy.data.objects.new(p_name, None)
        p_obj.empty_display_type = "SPHERE"
        p_obj.empty_display_size = 0.5
        p_obj.location = (p["position"][0], p["position"][1], 0)
        p_obj.parent = parent
        bpy.context.collection.objects.link(p_obj)

    return {
        "status": "success",
        "result": {
            "name": name,
            "location_type": location_type,
            "building_count": len(spec["buildings"]),
            "path_count": len(spec["paths"]),
            "poi_count": len(spec["pois"]),
            "terrain_size": terrain["size"],
        },
    }


def handle_generate_boss_arena(params: dict) -> dict:
    """Generate a boss arena with cover, hazards, fog gate (WORLD-03).

    Params:
        name: arena name (default "BossArena")
        arena_type: circular/rectangular (default "circular")
        diameter: arena diameter in meters (default 30.0)
        cover_count: number of cover objects (default 4)
        hazard_zones: number of hazard areas (default 2)
        has_fog_gate: whether to include fog gate (default true)
        phase_trigger_count: number of phase triggers (default 3)
        seed: random seed (default 0)
    """
    name = params.get("name", "BossArena")
    arena_type = params.get("arena_type", "circular")
    diameter = params.get("diameter", 30.0)
    cover_count = params.get("cover_count", 4)
    hazard_zones = params.get("hazard_zones", 2)
    has_fog_gate = params.get("has_fog_gate", True)
    phase_trigger_count = params.get("phase_trigger_count", 3)
    seed = params.get("seed", 0)

    spec = generate_boss_arena_spec(
        arena_type=arena_type,
        diameter=diameter,
        cover_count=cover_count,
        hazard_zones=hazard_zones,
        has_fog_gate=has_fog_gate,
        phase_trigger_count=phase_trigger_count,
        seed=seed,
    )

    # Create arena parent
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "CIRCLE"
    parent.empty_display_size = diameter / 2
    bpy.context.collection.objects.link(parent)

    # Arena floor
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_fill=True, segments=32, radius=diameter / 2)
    mesh = bpy.data.meshes.new(f"{name}_floor")
    bm.to_mesh(mesh)
    bm.free()
    floor_obj = bpy.data.objects.new(f"{name}_floor", mesh)
    floor_obj.parent = parent
    bpy.context.collection.objects.link(floor_obj)

    # Cover objects as empties
    for i, cover in enumerate(spec["covers"]):
        c_obj = bpy.data.objects.new(f"{name}_cover_{i}_{cover['type']}", None)
        c_obj.empty_display_type = "CUBE"
        c_obj.empty_display_size = cover["radius"]
        c_obj.location = (cover["position"][0], cover["position"][1], 0)
        c_obj.parent = parent
        bpy.context.collection.objects.link(c_obj)

    # Hazard zone empties
    for i, hz in enumerate(spec["hazard_zones"]):
        h_obj = bpy.data.objects.new(f"{name}_hazard_{i}_{hz['type']}", None)
        h_obj.empty_display_type = "SPHERE"
        h_obj.empty_display_size = hz["radius"]
        h_obj.location = (hz["position"][0], hz["position"][1], 0)
        h_obj.parent = parent
        bpy.context.collection.objects.link(h_obj)

    # Fog gate marker
    if spec["fog_gate"]:
        fg = spec["fog_gate"]
        fg_obj = bpy.data.objects.new(f"{name}_fog_gate", None)
        fg_obj.empty_display_type = "PLAIN_AXES"
        fg_obj.empty_display_size = fg["width"] / 2
        fg_obj.location = (fg["position"][0], fg["position"][1], 0)
        fg_obj.parent = parent
        bpy.context.collection.objects.link(fg_obj)

    return {
        "status": "success",
        "result": {
            "name": name,
            "arena_type": arena_type,
            "diameter": diameter,
            "cover_count": len(spec["covers"]),
            "hazard_count": len(spec["hazard_zones"]),
            "has_fog_gate": spec["fog_gate"] is not None,
            "phase_triggers": len(spec["phase_triggers"]),
        },
    }


def handle_generate_world_graph(params: dict) -> dict:
    """Generate a connected world graph visualisation (WORLD-04).

    Creates empties for nodes + curve objects for edges.

    Params:
        name: graph name (default "WorldGraph")
        locations: list of {name, type, position} dicts
        target_distance: target edge distance in meters (default 105)
        seed: random seed (default 0)
    """
    name = params.get("name", "WorldGraph")
    locations = params.get("locations", [])
    target_distance = params.get("target_distance", 105.0)
    seed = params.get("seed", 0)

    graph = generate_world_graph(
        locations=locations,
        target_distance=target_distance,
        seed=seed,
    )

    # Create parent
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    # Node empties
    node_objs = {}
    for node in graph.nodes:
        n_obj = bpy.data.objects.new(f"{name}_{node.name}", None)
        n_obj.empty_display_type = "SPHERE"
        n_obj.empty_display_size = 3.0
        n_obj.location = (node.position[0], node.position[1], 0)
        n_obj.parent = parent
        bpy.context.collection.objects.link(n_obj)
        node_objs[node.name] = n_obj

    # Edge curves
    for i, edge in enumerate(graph.edges):
        curve_data = bpy.data.curves.new(f"{name}_edge_{i}", 'CURVE')
        curve_data.dimensions = '3D'
        spline = curve_data.splines.new('POLY')
        spline.points.add(1)  # 2 points total

        from_node = next(n for n in graph.nodes if n.name == edge.from_node)
        to_node = next(n for n in graph.nodes if n.name == edge.to_node)

        spline.points[0].co = (from_node.position[0], from_node.position[1], 0, 1)
        spline.points[1].co = (to_node.position[0], to_node.position[1], 0, 1)

        curve_obj = bpy.data.objects.new(f"{name}_edge_{i}", curve_data)
        curve_obj.parent = parent
        bpy.context.collection.objects.link(curve_obj)

    return {
        "status": "success",
        "result": {
            "name": name,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "edges": [
                {"from": e.from_node, "to": e.to_node, "distance": e.distance}
                for e in graph.edges
            ],
        },
    }


def handle_generate_linked_interior(params: dict) -> dict:
    """Generate interior with door trigger + occlusion zone markers (WORLD-05).

    Params:
        name: interior name (default "LinkedInterior")
        building_exterior_bounds: {min, max} of exterior
        interior_rooms: list of {name, bounds} dicts
        door_positions: list of {position, facing} dicts
    """
    name = params.get("name", "LinkedInterior")
    exterior_bounds = params.get("building_exterior_bounds", {
        "min": (0, 0), "max": (10, 10),
    })
    rooms = params.get("interior_rooms", [])
    doors = params.get("door_positions", [])

    spec = generate_linked_interior_spec(
        building_exterior_bounds=exterior_bounds,
        interior_rooms=rooms,
        door_positions=doors,
    )

    # Create parent
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    # Door trigger empties
    for dt in spec["door_triggers"]:
        dt_obj = bpy.data.objects.new(f"{name}_{dt['id']}", None)
        dt_obj.empty_display_type = "ARROWS"
        dt_obj.empty_display_size = 1.0
        dt_obj.location = tuple(dt["position"])
        dt_obj.parent = parent
        bpy.context.collection.objects.link(dt_obj)

    # Occlusion zone empties
    for oz in spec["occlusion_zones"]:
        oz_obj = bpy.data.objects.new(f"{name}_{oz['id']}", None)
        oz_obj.empty_display_type = "CUBE"
        bmin = oz["bounds_min"]
        bmax = oz["bounds_max"]
        oz_obj.location = (
            (bmin[0] + bmax[0]) / 2,
            (bmin[1] + bmax[1]) / 2,
            0,
        )
        oz_obj.empty_display_size = max(bmax[0] - bmin[0], bmax[1] - bmin[1]) / 2
        oz_obj.parent = parent
        bpy.context.collection.objects.link(oz_obj)

    return {
        "status": "success",
        "result": {
            "name": name,
            "door_triggers": len(spec["door_triggers"]),
            "occlusion_zones": len(spec["occlusion_zones"]),
            "lighting_transitions": len(spec["lighting_transitions"]),
        },
    }


def handle_generate_multi_floor_dungeon(params: dict) -> dict:
    """Generate a multi-floor dungeon with vertical connections (WORLD-06).

    Params:
        name: dungeon name (default "MultiFloorDungeon")
        preset: VB dungeon preset name (optional, overrides defaults)
        width, height: grid dimensions (default 64)
        num_floors: number of floors (default 3)
        min_room_size: minimum room size (default 6)
        max_depth: BSP depth (default 5)
        cell_size: world cell size (default 2.0)
        wall_height: wall height per floor (default 3.0)
        connection_types: list of connection types (default ["staircase"])
        seed: random seed (default 0)
    """
    from .worldbuilding_layout import _dungeon_to_geometry_ops

    # Apply VB preset defaults if specified
    preset_name = params.get("preset")
    preset = get_vb_dungeon_preset(preset_name) if preset_name else None
    if preset_name and preset is None:
        raise ValueError(
            f"Unknown VB dungeon preset '{preset_name}'. "
            f"Valid: {list(VB_DUNGEON_PRESETS.keys())}"
        )

    name = params.get("name", (preset_name or "MultiFloorDungeon"))
    width = params.get("width", preset["width"] if preset else 64)
    height = params.get("height", preset["height"] if preset else 64)
    num_floors = params.get("num_floors", 3)
    min_room_size = params.get("min_room_size", preset["min_room_size"] if preset else 6)
    max_depth = params.get("max_depth", preset["max_depth"] if preset else 5)
    cell_size = params.get("cell_size", preset["cell_size"] if preset else 2.0)
    wall_height = params.get("wall_height", preset["wall_height"] if preset else 3.0)
    connection_types = params.get("connection_types", ["staircase"])
    seed = params.get("seed", 0)

    dungeon = generate_multi_floor_dungeon(
        width=width,
        height=height,
        num_floors=num_floors,
        min_room_size=min_room_size,
        max_depth=max_depth,
        cell_size=cell_size,
        wall_height=wall_height,
        connection_types=connection_types,
        seed=seed,
    )

    # Create parent
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    # Create each floor as a separate mesh, offset by wall_height
    total_prop_count = 0
    for floor_idx, layout in enumerate(dungeon.floors):
        floor_name = f"{name}_floor_{floor_idx}"
        ops = _dungeon_to_geometry_ops(layout, cell_size, wall_height)
        # Offset Z position for stacking
        y_offset = floor_idx * wall_height
        for op in ops:
            px, py, pz = op["position"]
            op["position"] = (px, py, pz + y_offset)
        floor_obj = _ops_to_mesh(ops, floor_name)
        floor_obj.parent = parent

        # Place procedural dungeon props for this floor
        prop_placements = generate_dungeon_prop_placements(
            layout, seed=seed + floor_idx * 100,
        )
        props_coll = bpy.data.collections.new(f"{name}_floor_{floor_idx}_props")
        bpy.context.scene.collection.children.link(props_coll)

        for pi, prop in enumerate(prop_placements):
            prop_entry = DUNGEON_PROP_MAP.get(prop["type"])
            if prop_entry is None:
                prop_entry = FURNITURE_GENERATOR_MAP.get(prop["type"])
            if prop_entry is None:
                continue
            gen_func, gen_kwargs = prop_entry
            prop_spec = gen_func(**gen_kwargs)
            px, py, pz = prop["position"]
            mesh_from_spec(
                prop_spec,
                name=f"{name}_f{floor_idx}_{prop['type']}_{pi}",
                location=(px * cell_size, py * cell_size, pz + y_offset),
                rotation=(0, 0, prop["rotation"]),
                collection=props_coll,
                parent=parent,
            )
            total_prop_count += 1

    # Connection markers
    for i, conn in enumerate(dungeon.connections):
        c_name = f"{name}_conn_{conn['type']}_{i}"
        c_obj = bpy.data.objects.new(c_name, None)
        c_obj.empty_display_type = "SINGLE_ARROW"
        c_obj.empty_display_size = 2.0
        cx, cy = conn["position"]
        c_obj.location = (
            cx * cell_size,
            cy * cell_size,
            conn["from_floor"] * wall_height,
        )
        c_obj.parent = parent
        bpy.context.collection.objects.link(c_obj)

    result = {
        "name": name,
        "num_floors": dungeon.num_floors,
        "total_rooms": dungeon.total_rooms,
        "procedural_mesh_count": total_prop_count,
        "connections": [
            {
                "from_floor": c["from_floor"],
                "to_floor": c["to_floor"],
                "type": c["type"],
            }
            for c in dungeon.connections
        ],
    }
    if preset:
        result["preset"] = preset_name
        result["preset_monster_table"] = preset.get("monster_table", [])
        result["preset_props"] = preset.get("props", [])
        result["preset_room_types"] = preset.get("room_types", {})
    return {"status": "success", "result": result}


def handle_generate_overrun_variant(params: dict) -> dict:
    """Generate an overrun/ruined variant of a room layout (WORLD-09).

    Params:
        name: room name (default "OverrunRoom")
        room_type: type of room (default "tavern")
        width: room width (default 8)
        depth: room depth (default 6)
        height: room height (default 3.0)
        corruption_level: 0.0-1.0 destruction intensity (default 0.5)
        seed: random seed (default 0)
    """
    name = params.get("name", "OverrunRoom")
    room_type = params.get("room_type", "tavern")
    width = params.get("width", 8)
    depth = params.get("depth", 6)
    height = params.get("height", 3.0)
    corruption_level = params.get("corruption_level", 0.5)
    seed = params.get("seed", 0)

    # Generate base layout
    base_layout = generate_interior_layout(room_type, width, depth, height, seed)

    # Generate overrun variant
    overrun = generate_overrun_variant(
        layout=base_layout,
        room_width=width,
        room_depth=depth,
        corruption_level=corruption_level,
        seed=seed,
    )

    # Count types
    debris_count = sum(1 for item in overrun if item.get("role") == "debris")
    vegetation_count = sum(1 for item in overrun if item.get("role") == "vegetation")
    remains_count = sum(1 for item in overrun if item.get("role") == "remains")
    broken_walls = sum(1 for item in overrun if item.get("role") == "broken_wall")

    # Create room parent
    room_empty = bpy.data.objects.new(name, None)
    room_empty.empty_display_type = "CUBE"
    room_empty.empty_display_size = max(width, depth) / 2
    bpy.context.collection.objects.link(room_empty)

    return {
        "status": "success",
        "result": {
            "name": name,
            "room_type": room_type,
            "corruption_level": corruption_level,
            "total_items": len(overrun),
            "debris_count": debris_count,
            "vegetation_count": vegetation_count,
            "remains_count": remains_count,
            "broken_wall_count": broken_walls,
        },
    }


def handle_generate_easter_egg(params: dict) -> dict:
    """Generate easter egg marker empties for secrets/hidden areas (WORLD-10).

    Params:
        name: marker group name (default "EasterEggs")
        location_layout: location spec dict (from generate_location_spec)
        secret_room_count: number of secret rooms (default 1)
        hidden_path_count: number of hidden paths (default 1)
        lore_item_count: number of lore items (default 2)
        seed: random seed (default 0)
    """
    name = params.get("name", "EasterEggs")
    location_layout = params.get("location_layout", {
        "terrain_bounds": {"size": 100.0},
        "buildings": [],
        "paths": [],
    })
    secret_room_count = params.get("secret_room_count", 1)
    hidden_path_count = params.get("hidden_path_count", 1)
    lore_item_count = params.get("lore_item_count", 2)
    seed = params.get("seed", 0)

    eggs = generate_easter_egg_spec(
        location_layout=location_layout,
        secret_room_count=secret_room_count,
        hidden_path_count=hidden_path_count,
        lore_item_count=lore_item_count,
        seed=seed,
    )

    # Create parent
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    # Create marker empties for each easter egg
    for i, egg in enumerate(eggs):
        e_name = f"{name}_{egg['type']}_{i}"
        e_obj = bpy.data.objects.new(e_name, None)
        e_obj.empty_display_type = "SPHERE"
        e_obj.empty_display_size = 1.0
        e_obj.location = (egg["position"][0], egg["position"][1], 0)
        e_obj.parent = parent
        bpy.context.collection.objects.link(e_obj)
        # Store metadata
        e_obj["egg_type"] = egg["type"]

    return {
        "status": "success",
        "result": {
            "name": name,
            "total_eggs": len(eggs),
            "secret_rooms": sum(1 for e in eggs if e["type"] == "secret_room"),
            "hidden_paths": sum(1 for e in eggs if e["type"] == "hidden_path"),
            "lore_items": sum(1 for e in eggs if e["type"] == "lore_item"),
        },
    }


def handle_add_storytelling_props(params: dict) -> dict:
    """Add storytelling props (narrative clutter) to an interior room (AAA-05).

    Params:
        target_interior: object name of the interior to decorate (default "Interior")
        room_type: room type for contextual distribution (default "tavern")
        room_width: room width (default 4.0)
        room_depth: room depth (default 4.0)
        density_modifier: prop density multiplier (default 1.0)
        seed: random seed (default 0)
    """
    target_interior = params.get("target_interior", "Interior")
    room_type = params.get("room_type", "tavern")
    room_width = params.get("room_width", 4.0)
    room_depth = params.get("room_depth", 4.0)
    density_modifier = params.get("density_modifier", 1.0)
    seed = params.get("seed", 0)

    prop_specs = add_storytelling_props(
        room_type=room_type,
        room_width=room_width,
        room_depth=room_depth,
        density_modifier=density_modifier,
        seed=seed,
    )

    # Find parent object (if exists)
    parent_obj = bpy.data.objects.get(target_interior)

    # Create marker empties for each prop
    prop_group_name = f"{target_interior}_StoryProps"
    group = bpy.data.objects.new(prop_group_name, None)
    group.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(group)
    if parent_obj:
        group.parent = parent_obj

    for i, prop in enumerate(prop_specs):
        p_name = f"{prop_group_name}_{prop['prop_type']}_{i}"
        p_obj = bpy.data.objects.new(p_name, None)
        p_obj.empty_display_type = "SINGLE_ARROW"
        p_obj.empty_display_size = 0.3
        pos = prop["position"]
        p_obj.location = (pos[0], pos[1], pos[2])
        p_obj.parent = group
        bpy.context.collection.objects.link(p_obj)
        p_obj["prop_type"] = prop["prop_type"]
        p_obj["placement_rule"] = prop["placement_rule"]

    return {
        "status": "success",
        "result": {
            "target_interior": target_interior,
            "room_type": room_type,
            "props_placed": len(prop_specs),
            "group_name": prop_group_name,
        },
    }


def handle_generate_landmark(params: dict) -> dict:
    """Generate a unique VeilBreakers landmark structure.

    Landmarks are one-of-a-kind structures that serve as world navigation
    reference points -- things players remember and use to orient themselves.

    Params:
        landmark_name: key from VB_LANDMARK_PRESETS, or "custom"
        name: Blender object name (default: landmark_name or "Landmark")
        seed: random seed (default 0)
        -- custom-mode overrides (ignored when using a preset) --
        description: landmark description
        base_style: architecture style (default "gothic")
        scale: overall scale multiplier (default 1.0)
        floors: number of floors (default 1)
        width: footprint width (default 10.0)
        depth: footprint depth (default 10.0)
        wall_height: wall height (default 5.0)
        unique_features: list of feature names (default [])
        interior_rooms: list of room type names to furnish (default [])
        corruption_level: 0.0-1.0 corruption intensity (default 0.0)
        props: list of prop names (default [])
    """
    logger.info("Generating landmark")

    landmark_name = params.get("landmark_name", "custom")
    seed = params.get("seed", 0)

    # Resolve preset or build custom config
    if landmark_name != "custom":
        preset = get_vb_landmark_preset(landmark_name)
        if preset is None:
            raise ValueError(
                f"Unknown VB landmark preset '{landmark_name}'. "
                f"Valid: {list(VB_LANDMARK_PRESETS.keys())}"
            )
        # Allow param overrides on top of preset
        preset = dict(preset)  # shallow copy to avoid mutation
    else:
        preset = {
            "description": params.get("description", "Custom landmark"),
            "base_style": params.get("base_style", "gothic"),
            "scale": params.get("scale", 1.0),
            "floors": params.get("floors", 1),
            "width": params.get("width", 10.0),
            "depth": params.get("depth", 10.0),
            "wall_height": params.get("wall_height", 5.0),
            "unique_features": params.get("unique_features", []),
            "interior_rooms": params.get("interior_rooms", []),
            "corruption_level": params.get("corruption_level", 0.0),
            "props": params.get("props", []),
        }

    name = params.get("name", landmark_name if landmark_name != "custom" else "Landmark")
    width = preset["width"]
    depth = preset["depth"]
    floors = preset["floors"]
    wall_height = preset["wall_height"]
    scale = preset["scale"]
    corruption_level = preset["corruption_level"]
    unique_features = preset["unique_features"]
    interior_rooms = preset.get("interior_rooms", [])

    # Resolve base_style -- fall back to "gothic" if style not in STYLE_CONFIGS
    base_style = preset["base_style"]
    if base_style not in STYLE_CONFIGS:
        logger.warning(
            "Landmark style '%s' not in STYLE_CONFIGS, falling back to 'gothic'",
            base_style,
        )
        base_style = "gothic"

    # 1. Generate building structure (skip for floor-less landmarks like veil_breach)
    spec = None
    if floors > 0:
        spec = evaluate_building_grammar(width, depth, floors, base_style, seed)

    # 2. Generate unique feature geometry operations
    unique_feature_ops = _generate_landmark_unique_features(
        unique_features=unique_features,
        width=width,
        depth=depth,
        wall_height=wall_height,
        scale=scale,
        seed=seed,
    )

    # 3. Corruption tint
    corruption_tint = _apply_corruption_tint(corruption_level)

    # 4. Generate interior room layouts
    room_layouts: dict[str, list[dict]] = {}
    for i, room_name in enumerate(interior_rooms):
        mapped_type = _LANDMARK_ROOM_TYPE_MAP.get(room_name, room_name)
        room_w = width * 0.4
        room_d = depth * 0.3
        layout = generate_interior_layout(
            mapped_type, room_w, room_d, wall_height, seed=seed + i + 1,
        )
        room_key = f"{room_name}_{i}" if interior_rooms.count(room_name) > 1 else room_name
        room_layouts[room_key] = layout

    # 5. Build pure-logic result (testable without Blender)
    result = _build_landmark_result(
        name=name,
        preset=preset,
        spec=spec,
        unique_feature_ops=unique_feature_ops,
        room_layouts=room_layouts,
        corruption_tint=corruption_tint,
    )

    # --- Blender geometry ---

    # Create parent empty
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.empty_display_size = max(width, depth) / 2
    bpy.context.collection.objects.link(parent)

    # Main structure
    obj = None
    if spec is not None:
        bm = _spec_to_bmesh(spec)
        obj = _create_mesh_object(f"{name}_structure", bm)
        obj.parent = parent
        obj.scale = (scale, scale, scale)

    # Unique features as separate meshes in a sub-collection
    if unique_feature_ops:
        feat_coll = bpy.data.collections.new(f"{name}_features")
        bpy.context.scene.collection.children.link(feat_coll)
        feat_spec = BuildingSpec(
            footprint=(width, depth),
            floors=0,
            style=base_style,
            operations=unique_feature_ops,
        )
        feat_mesh_specs = _building_ops_to_mesh_spec(feat_spec)
        for fi, fms in enumerate(feat_mesh_specs):
            feat_name = fms.get("feature_name", f"feature_{fi}")
            feat_bm = bmesh.new()
            bm_verts = []
            for v in fms["vertices"]:
                bm_verts.append(feat_bm.verts.new(v))
            feat_bm.verts.ensure_lookup_table()
            for face_indices in fms["faces"]:
                try:
                    fv = [bm_verts[idx] for idx in face_indices]
                    feat_bm.faces.new(fv)
                except (ValueError, IndexError):
                    pass
            f_mesh = bpy.data.meshes.new(f"{name}_{feat_name}")
            feat_bm.to_mesh(f_mesh)
            feat_bm.free()
            f_obj = bpy.data.objects.new(f"{name}_{feat_name}", f_mesh)
            f_obj.parent = parent
            feat_coll.objects.link(f_obj)

    # Corruption material tint
    if corruption_level > 0:
        mat = bpy.data.materials.new(f"{name}_corruption")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            color = corruption_tint["base_color"]
            bsdf.inputs["Base Color"].default_value = tuple(color)
        # Assign corruption material to the structure mesh
        if obj is not None:
            if obj.data.materials:
                obj.data.materials[0] = mat  # replace first material
            else:
                obj.data.materials.append(mat)
        parent["corruption_level"] = corruption_level
        parent["corruption_tint"] = str(corruption_tint["base_color"])

    # Furnish interior rooms
    room_seed_offset = 1000
    for room_key, layout in room_layouts.items():
        room_empty = bpy.data.objects.new(f"{name}_room_{room_key}", None)
        room_empty.empty_display_type = "CUBE"
        room_empty.empty_display_size = 2.0
        room_empty.parent = parent
        bpy.context.collection.objects.link(room_empty)

        for item in layout:
            item_name = f"{name}_{room_key}_{item['type']}"
            sx, sy, sz = item["scale"]
            item_bm = bmesh.new()
            bmesh.ops.create_cube(item_bm, size=1.0)
            for v in item_bm.verts:
                v.co.x *= sx
                v.co.y *= sy
                v.co.z *= sz
                v.co.z += sz / 2
            item_mesh = bpy.data.meshes.new(item_name)
            item_bm.to_mesh(item_mesh)
            item_bm.free()
            item_obj = bpy.data.objects.new(item_name, item_mesh)
            item_obj.location = tuple(item["position"])
            item_obj.rotation_euler = (0, 0, item["rotation"])
            item_obj.parent = room_empty
            bpy.context.collection.objects.link(item_obj)

    # Store landmark metadata on parent
    parent["landmark_name"] = landmark_name
    parent["landmark_description"] = preset.get("description", "")
    parent["landmark_props"] = str(preset.get("props", []))

    return {"status": "success", "result": result}
