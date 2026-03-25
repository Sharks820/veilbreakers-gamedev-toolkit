"""Building-interior spatial binding and configuration mapping.

Bridges the gap between building generation (exterior shells) and interior
composition (room layout + furniture). Provides:

1. Building-to-room-type mapping (building purpose -> suitable room types)
2. Spatial alignment (constrain room bounds to building footprint)
3. Style propagation (building style -> interior material palette)
4. Door metadata generation (scene names, transition types)
5. Interior spec generation from building presets

All functions are pure-logic (no bpy imports) for testability.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Building purpose -> room type mapping
# ---------------------------------------------------------------------------

BUILDING_ROOM_MAP: dict[str, list[dict[str, Any]]] = {
    "tavern": [
        {"type": "tavern_hall", "name": "main_hall", "floor": 0, "size_ratio": 0.6},
        {"type": "kitchen", "name": "kitchen", "floor": 0, "size_ratio": 0.25},
        {"type": "storage", "name": "cellar", "floor": -1, "size_ratio": 0.4},
        {"type": "bedroom", "name": "upstairs_room", "floor": 1, "size_ratio": 0.5},
    ],
    "house": [
        {"type": "bedroom", "name": "bedroom", "floor": 0, "size_ratio": 0.4},
        {"type": "kitchen", "name": "kitchen", "floor": 0, "size_ratio": 0.3},
        {"type": "storage", "name": "pantry", "floor": 0, "size_ratio": 0.2},
    ],
    "abandoned_house": [
        {"type": "bedroom", "name": "bedroom", "floor": 0, "size_ratio": 0.5},
        {"type": "kitchen", "name": "kitchen", "floor": 0, "size_ratio": 0.35},
    ],
    "castle": [
        {"type": "throne_room", "name": "throne_room", "floor": 0, "size_ratio": 0.5},
        {"type": "guard_barracks", "name": "barracks", "floor": 0, "size_ratio": 0.25},
        {"type": "dining_hall", "name": "great_hall", "floor": 1, "size_ratio": 0.5},
        {"type": "treasury", "name": "vault", "floor": -1, "size_ratio": 0.3},
        {"type": "war_room", "name": "war_room", "floor": 1, "size_ratio": 0.25},
    ],
    "cathedral": [
        {"type": "chapel", "name": "nave", "floor": 0, "size_ratio": 0.7},
        {"type": "library", "name": "scriptorium", "floor": 0, "size_ratio": 0.2},
        {"type": "crypt", "name": "crypt", "floor": -1, "size_ratio": 0.5},
    ],
    "tower": [
        {"type": "guard_barracks", "name": "ground_floor", "floor": 0, "size_ratio": 0.8},
        {"type": "library", "name": "study", "floor": 1, "size_ratio": 0.8},
        {"type": "alchemy_lab", "name": "laboratory", "floor": 2, "size_ratio": 0.8},
    ],
    "shop": [
        {"type": "tavern_hall", "name": "shop_floor", "floor": 0, "size_ratio": 0.6},
        {"type": "storage", "name": "stockroom", "floor": 0, "size_ratio": 0.3},
    ],
    "forge": [
        {"type": "blacksmith", "name": "smithy", "floor": 0, "size_ratio": 0.7},
        {"type": "storage", "name": "material_store", "floor": 0, "size_ratio": 0.2},
    ],
    "ruin": [
        {"type": "generic", "name": "main_chamber", "floor": 0, "size_ratio": 0.8},
    ],
    "gate": [],
    "bridge": [],
    "wall_section": [],
    "dungeon_entrance": [
        {"type": "guard_barracks", "name": "guard_post", "floor": 0, "size_ratio": 0.5},
        {"type": "torture_chamber", "name": "holding_cell", "floor": -1, "size_ratio": 0.4},
    ],
    "shrine": [
        {"type": "chapel", "name": "sanctum", "floor": 0, "size_ratio": 0.8},
    ],
}

# ---------------------------------------------------------------------------
# Building style -> interior material palette
# ---------------------------------------------------------------------------

STYLE_MATERIAL_MAP: dict[str, dict[str, str]] = {
    "dark_fantasy": {
        "wall": "dark_stone",
        "floor": "dark_wood_planks",
        "ceiling": "dark_wood_beams",
        "trim": "iron_dark",
        "accent": "blood_red",
    },
    "gothic": {
        "wall": "grey_stone_carved",
        "floor": "stone_tile",
        "ceiling": "stone_vault",
        "trim": "dark_wood",
        "accent": "gold_trim",
    },
    "medieval": {
        "wall": "rough_stone",
        "floor": "wood_planks",
        "ceiling": "wood_beams",
        "trim": "wood_dark",
        "accent": "iron",
    },
    "elven": {
        "wall": "white_stone_smooth",
        "floor": "marble_white",
        "ceiling": "crystal_lattice",
        "trim": "silver",
        "accent": "emerald",
    },
    "dwarven": {
        "wall": "carved_granite",
        "floor": "stone_slab",
        "ceiling": "stone_arch",
        "trim": "bronze",
        "accent": "gold",
    },
    "corrupted": {
        "wall": "corrupted_stone",
        "floor": "cracked_obsidian",
        "ceiling": "void_membrane",
        "trim": "bone",
        "accent": "void_purple",
    },
    "fortress": {
        "wall": "fortress_stone",
        "floor": "stone_flag",
        "ceiling": "stone_arch",
        "trim": "iron_reinforced",
        "accent": "iron_dark",
    },
}


def get_interior_materials(building_style: str) -> dict[str, str]:
    """Return material palette for interior surfaces based on building style."""
    return dict(STYLE_MATERIAL_MAP.get(building_style,
                                        STYLE_MATERIAL_MAP["medieval"]))


def get_room_types_for_building(building_type: str) -> list[dict[str, Any]]:
    """Return suitable room type configurations for a building type.

    Each room dict contains:
        type: Room type string (tavern_hall, bedroom, etc.)
        name: Default room name
        floor: Floor index (0 = ground, -1 = below, 1+ = upper)
        size_ratio: Fraction of building footprint this room occupies
    """
    return [dict(r) for r in BUILDING_ROOM_MAP.get(building_type, [])]


# ---------------------------------------------------------------------------
# Spatial alignment: constrain rooms to building footprint
# ---------------------------------------------------------------------------


def align_rooms_to_building(
    building_width: float,
    building_depth: float,
    building_position: tuple[float, float, float],
    rooms: list[dict[str, Any]],
    wall_thickness: float = 0.3,
) -> list[dict[str, Any]]:
    """Constrain and position room specs to fit inside a building footprint.

    Takes room definitions with size_ratio and returns rooms with:
    - Absolute world positions aligned to building location
    - Width/depth scaled to fit within building walls
    - Proper bounds for occlusion/trigger generation

    Args:
        building_width: Building exterior width.
        building_depth: Building exterior depth.
        building_position: World-space (x, y, z) of building origin.
        rooms: Room defs with type, name, size_ratio, floor.
        wall_thickness: Inset from exterior walls.

    Returns:
        Updated room dicts with position, width, depth, and bounds added.
    """
    bx, by, bz = building_position
    interior_w = building_width - wall_thickness * 2
    interior_d = building_depth - wall_thickness * 2

    if interior_w <= 0 or interior_d <= 0:
        return []

    # Group rooms by floor
    floors: dict[int, list[dict]] = {}
    for room in rooms:
        fl = room.get("floor", 0)
        floors.setdefault(fl, []).append(room)

    result: list[dict[str, Any]] = []

    for floor_idx, floor_rooms in sorted(floors.items()):
        # Calculate y offset for below-ground floors
        floor_y = bz + floor_idx * 3.5  # 3.5m per floor

        # Simple strip packing: divide interior space among rooms on this floor
        total_ratio = sum(r.get("size_ratio", 0.5) for r in floor_rooms)
        if total_ratio <= 0:
            total_ratio = 1.0

        current_x = bx + wall_thickness
        for room in floor_rooms:
            ratio = room.get("size_ratio", 0.5) / total_ratio
            room_w = interior_w * ratio
            room_d = interior_d  # Full depth minus walls

            aligned = dict(room)
            aligned["width"] = round(room_w, 2)
            aligned["depth"] = round(room_d, 2)
            aligned["height"] = room.get("height", 3.5)
            aligned["position"] = (
                round(current_x, 2),
                round(by + wall_thickness, 2),
                round(floor_y, 2),
            )
            aligned["bounds"] = {
                "min": (round(current_x, 2), round(by + wall_thickness, 2)),
                "max": (round(current_x + room_w, 2),
                        round(by + wall_thickness + room_d, 2)),
            }

            result.append(aligned)
            current_x += room_w

    return result


# ---------------------------------------------------------------------------
# Door metadata with interior scene linking
# ---------------------------------------------------------------------------


def generate_door_metadata(
    building_name: str,
    building_position: tuple[float, float, float],
    building_width: float,
    building_depth: float,
    openings: list[dict[str, Any]],
    wall_height: float = 3.5,
) -> list[dict[str, Any]]:
    """Generate door metadata with scene names and world positions.

    Converts building opening definitions (from VB_BUILDING_PRESETS) into
    door trigger data with interior scene references.

    Args:
        building_name: Building instance name.
        building_position: World-space (x, y, z).
        building_width: Exterior width.
        building_depth: Exterior depth.
        openings: List of opening defs from building preset.
        wall_height: Per-floor height.

    Returns:
        List of door metadata dicts with position, facing, scene name.
    """
    bx, by, bz = building_position
    doors: list[dict[str, Any]] = []

    for opening in openings:
        if opening.get("type") != "door":
            continue

        wall = opening.get("wall", "front")
        floor = opening.get("floor", 0)
        style = opening.get("style", "square")

        # Calculate world position based on wall
        if wall == "front":
            pos = (bx + building_width / 2, by, bz + floor * wall_height + 1.1)
            facing = "south"
        elif wall == "back":
            pos = (bx + building_width / 2, by + building_depth,
                   bz + floor * wall_height + 1.1)
            facing = "north"
        elif wall == "left":
            pos = (bx, by + building_depth / 2, bz + floor * wall_height + 1.1)
            facing = "east"
        elif wall == "right":
            pos = (bx + building_width, by + building_depth / 2,
                   bz + floor * wall_height + 1.1)
            facing = "west"
        else:
            continue

        doors.append({
            "position": tuple(round(c, 2) for c in pos),
            "facing": facing,
            "style": style,
            "floor": floor,
            "interior_scene_name": f"{building_name}_Interior",
            "transition_type": "door",
            "building_name": building_name,
        })

    return doors


# ---------------------------------------------------------------------------
# Full interior spec from building preset
# ---------------------------------------------------------------------------


def generate_interior_spec_from_building(
    building_name: str,
    building_type: str,
    building_style: str,
    building_width: float,
    building_depth: float,
    building_position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    openings: list[dict] | None = None,
    wall_height: float = 3.5,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a complete interior_spec from a building definition.

    This is the main integration function that bridges building generation
    with interior composition. Returns a spec that can be passed directly
    to ``compose_interior``.

    Args:
        building_name: Instance name (e.g., "Tavern_01").
        building_type: Building category (tavern, house, castle, etc.).
        building_style: Architectural style (medieval, gothic, etc.).
        building_width: Exterior width.
        building_depth: Exterior depth.
        building_position: World-space origin.
        openings: Door/window definitions from building preset.
        wall_height: Per-floor height.
        seed: Random seed for reproducibility.

    Returns:
        Dict compatible with compose_interior's interior_spec parameter.
    """
    # Get suitable room types for this building
    room_templates = get_room_types_for_building(building_type)
    if not room_templates:
        return {"name": building_name, "rooms": [], "doors": [], "style": building_style}

    # Align rooms to building footprint
    aligned_rooms = align_rooms_to_building(
        building_width, building_depth, building_position,
        room_templates, wall_thickness=0.3,
    )

    # Get interior material palette
    materials = get_interior_materials(building_style)

    # Build room specs for compose_interior
    rooms: list[dict[str, Any]] = []
    for room in aligned_rooms:
        rooms.append({
            "name": room["name"],
            "type": room["type"],
            "width": room["width"],
            "depth": room["depth"],
            "height": room["height"],
            "position": room.get("position"),
            "below_ground": room.get("floor", 0) < 0,
            "materials": materials,
        })

    # Generate door metadata
    door_meta = generate_door_metadata(
        building_name, building_position,
        building_width, building_depth,
        openings or [], wall_height,
    )

    # Build door specs for compose_interior
    doors: list[dict[str, Any]] = []
    for dm in door_meta:
        doors.append({
            "position": dm["position"],
            "facing": dm["facing"],
            "style": dm["style"],
            "interior_scene_name": dm["interior_scene_name"],
        })

    return {
        "name": f"{building_name}_Interior",
        "seed": seed,
        "style": building_style,
        "rooms": rooms,
        "doors": doors,
        "building_bounds": {
            "min": (building_position[0], building_position[1]),
            "max": (building_position[0] + building_width,
                    building_position[1] + building_depth),
        },
        "materials": materials,
        "storytelling_density": 0.5,
        "generate_props_with_tripo": False,
    }
