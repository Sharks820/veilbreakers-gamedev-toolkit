"""Blender handlers for building generation, castles, ruins, interiors, modular kits.

Converts pure-logic BuildingSpec operations into Blender mesh geometry.
Provides 5 handler functions registered in COMMAND_HANDLERS.
"""

from __future__ import annotations

import math
from typing import Any

import bpy
import bmesh

from ._building_grammar import (
    evaluate_building_grammar,
    generate_castle_spec,
    generate_tower_spec,
    generate_bridge_spec,
    generate_fortress_spec,
    apply_ruins_damage,
    generate_interior_layout,
    generate_modular_pieces,
    BuildingSpec,
    STYLE_CONFIGS,
    MODULAR_CATALOG,
)


# ---------------------------------------------------------------------------
# Pure-logic: BuildingSpec -> mesh primitive specs (testable without Blender)
# ---------------------------------------------------------------------------


def _building_ops_to_mesh_spec(spec: BuildingSpec) -> list[dict]:
    """Convert BuildingSpec operations to mesh primitive specs.

    Returns list of dicts describing vertices, faces, and metadata for each
    primitive. This is a pure-logic function -- no bpy/bmesh calls.
    """
    result: list[dict] = []

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
            # Openings are marked for face construction (no boolean subtract)
            result.append({
                "type": "opening",
                "wall_index": op.get("wall_index", 0),
                "position": op.get("position", [0, 0]),
                "size": op.get("size", [1, 1]),
                "role": op.get("role", "opening"),
                "face_construction": True,
            })

    return result


# ---------------------------------------------------------------------------
# Pure-logic result builders (testable without Blender)
# ---------------------------------------------------------------------------


def _build_building_result(name: str, spec: BuildingSpec) -> dict:
    """Build handler return dict for a building from its spec."""
    mesh_specs = _building_ops_to_mesh_spec(spec)
    total_verts = sum(m.get("vertex_count", 0) for m in mesh_specs if m["type"] != "opening")
    total_faces = sum(m.get("face_count", 0) for m in mesh_specs if m["type"] != "opening")
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
    }


def _build_castle_result(name: str, spec: BuildingSpec) -> dict:
    """Build handler return dict for a castle from its spec."""
    roles = [op.get("role") for op in spec.operations]
    component_count = len(set(roles))
    return {
        "name": name,
        "component_count": component_count,
        "roles": list(set(roles)),
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
) -> dict:
    """Build handler return dict for interior layout."""
    return {
        "name": name,
        "room_type": room_type,
        "furniture_count": len(layout),
        "items": [item["type"] for item in layout],
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


# ---------------------------------------------------------------------------
# Blender geometry construction helpers
# ---------------------------------------------------------------------------


def _spec_to_bmesh(spec: BuildingSpec) -> bmesh.types.BMesh:
    """Convert a BuildingSpec into a single bmesh with all geometry."""
    bm = bmesh.new()
    mesh_specs = _building_ops_to_mesh_spec(spec)

    for ms in mesh_specs:
        if ms["type"] == "opening":
            continue  # openings handled separately

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
                pass  # skip degenerate faces

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
# Handler Functions
# ---------------------------------------------------------------------------


def handle_generate_building(params: dict) -> dict:
    """Generate a building from grammar rules.

    Params:
        name: object name (default "Building")
        width: building width (default 10)
        depth: building depth (default 8)
        floors: number of floors (default 2)
        style: style preset name (default "medieval")
        seed: random seed (default 0)
    """
    name = params.get("name", "Building")
    width = params.get("width", 10)
    depth = params.get("depth", 8)
    floors = params.get("floors", 2)
    style = params.get("style", "medieval")
    seed = params.get("seed", 0)

    if style not in STYLE_CONFIGS:
        raise ValueError(f"Unknown style '{style}'. Valid: {list(STYLE_CONFIGS.keys())}")

    spec = evaluate_building_grammar(width, depth, floors, style, seed)

    # Create Blender geometry
    bm = _spec_to_bmesh(spec)
    obj = _create_mesh_object(name, bm)

    result = _build_building_result(name, spec)
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
    name = params.get("name", "Castle")
    outer_size = params.get("outer_size", 40)
    keep_size = params.get("keep_size", 12)
    tower_count = params.get("tower_count", 4)
    seed = params.get("seed", 0)

    spec = generate_castle_spec(outer_size, keep_size, tower_count, seed)

    bm = _spec_to_bmesh(spec)
    obj = _create_mesh_object(name, bm)

    result = _build_castle_result(name, spec)
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
    name = params.get("name", "Interior")
    room_type = params.get("room_type", "tavern")
    width = params.get("width", 8)
    depth = params.get("depth", 6)
    height = params.get("height", 3.0)
    seed = params.get("seed", 0)

    layout = generate_interior_layout(room_type, width, depth, height, seed)

    # Create placeholder geometry for each furniture item
    # Create an empty as the room parent
    room_empty = bpy.data.objects.new(name, None)
    room_empty.empty_display_type = "CUBE"
    room_empty.empty_display_size = max(width, depth) / 2
    bpy.context.collection.objects.link(room_empty)

    for item in layout:
        item_name = f"{name}_{item['type']}"
        item_bm = bmesh.new()
        sx, sy, sz = item["scale"]
        bmesh.ops.create_cube(item_bm, size=1.0)
        # Scale the cube to furniture dimensions
        for v in item_bm.verts:
            v.co.x *= sx
            v.co.y *= sy
            v.co.z *= sz
            # Shift to sit on ground (cube center to bottom)
            v.co.z += sz / 2
        item_mesh = bpy.data.meshes.new(item_name)
        item_bm.to_mesh(item_mesh)
        item_bm.free()
        item_obj = bpy.data.objects.new(item_name, item_mesh)
        item_obj.location = tuple(item["position"])
        item_obj.rotation_euler = (0, 0, item["rotation"])
        item_obj.parent = room_empty
        bpy.context.collection.objects.link(item_obj)

    result = _build_interior_result(name, room_type, layout)
    return {"status": "success", "result": result}


def handle_generate_modular_kit(params: dict) -> dict:
    """Generate modular architecture kit pieces.

    Params:
        name_prefix: object name prefix (default "ModKit")
        cell_size: grid cell size in meters (default 2.0)
        pieces: list of piece names or null for all (default None)
    """
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
