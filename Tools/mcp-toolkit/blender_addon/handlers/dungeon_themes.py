"""Dungeon theme configuration and application system.

Provides 10 themed dungeon variants with material, floor, prop, and lighting
definitions. Each theme can be applied to an existing dungeon layout to
customise its visual identity.

Pure-logic module -- no bpy/bmesh imports. Fully testable outside Blender.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

DUNGEON_THEMES: dict[str, dict[str, Any]] = {
    "prison": {
        "wall_material": "iron_bars",
        "floor": "cold_stone",
        "props": ["shackle", "cage", "stocks"],
        "lighting": "dim_torch",
        "ambient_color": (0.15, 0.12, 0.1),
        "fog_density": 0.3,
    },
    "tomb": {
        "wall_material": "carved_stone",
        "floor": "burial_slab",
        "props": ["sarcophagus", "coffin", "urn"],
        "lighting": "none",
        "ambient_color": (0.05, 0.05, 0.07),
        "fog_density": 0.1,
    },
    "natural_cave": {
        "wall_material": "raw_rock",
        "floor": "cave_floor",
        "props": ["stalactite", "stalagmite", "crystal_light"],
        "lighting": "bioluminescent",
        "ambient_color": (0.08, 0.15, 0.12),
        "fog_density": 0.4,
    },
    "mine": {
        "wall_material": "timber_supported",
        "floor": "track_rails",
        "props": ["cart", "barrel", "lantern"],
        "lighting": "lantern",
        "ambient_color": (0.2, 0.15, 0.08),
        "fog_density": 0.5,
    },
    "sewer": {
        "wall_material": "wet_brick",
        "floor": "water_channel",
        "props": ["barrel", "rat_nest", "skull_pile"],
        "lighting": "dim",
        "ambient_color": (0.1, 0.12, 0.08),
        "fog_density": 0.6,
    },
    "library": {
        "wall_material": "bookshelf_walls",
        "floor": "wood_polish",
        "props": ["bookshelf", "table", "candelabra"],
        "lighting": "chandelier",
        "ambient_color": (0.2, 0.18, 0.12),
        "fog_density": 0.1,
    },
    "laboratory": {
        "wall_material": "stained_stone",
        "floor": "tile",
        "props": ["cauldron", "workbench", "potion_bottle"],
        "lighting": "bright",
        "ambient_color": (0.2, 0.22, 0.18),
        "fog_density": 0.2,
    },
    "arena": {
        "wall_material": "arena_wall",
        "floor": "sand",
        "props": ["pillar", "shelf", "gate"],
        "lighting": "open_sky",
        "ambient_color": (0.3, 0.28, 0.2),
        "fog_density": 0.05,
    },
    "temple": {
        "wall_material": "sanctified_stone",
        "floor": "mosaic",
        "props": ["altar", "brazier", "banner"],
        "lighting": "candle",
        "ambient_color": (0.18, 0.15, 0.1),
        "fog_density": 0.15,
    },
    "hive": {
        "wall_material": "organic_resin",
        "floor": "membrane",
        "props": ["spider_egg_sac", "cobweb", "skull_pile"],
        "lighting": "bioluminescent",
        "ambient_color": (0.1, 0.08, 0.02),
        "fog_density": 0.7,
    },
}

# ---------------------------------------------------------------------------
# All valid theme names (useful for validation)
# ---------------------------------------------------------------------------

THEME_NAMES: list[str] = sorted(DUNGEON_THEMES.keys())


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_dungeon_theme(theme_name: str) -> dict[str, Any]:
    """Return theme configuration for dungeon generation.

    Args:
        theme_name: One of the keys in DUNGEON_THEMES.

    Returns:
        Dict with wall_material, floor, props, lighting, ambient_color,
        fog_density.

    Raises:
        ValueError: If theme_name is not a recognised theme.
    """
    theme = DUNGEON_THEMES.get(theme_name)
    if theme is None:
        raise ValueError(
            f"Unknown dungeon theme '{theme_name}'. "
            f"Valid themes: {', '.join(THEME_NAMES)}"
        )
    # Return a copy to prevent mutation of module-level data
    return dict(theme)


def list_themes() -> list[str]:
    """Return sorted list of all available dungeon theme names."""
    return list(THEME_NAMES)


# ---------------------------------------------------------------------------
# Theme application
# ---------------------------------------------------------------------------


def apply_theme_to_dungeon(
    dungeon_layout: dict[str, Any],
    theme_name: str,
) -> dict[str, Any]:
    """Apply theme materials, props, and lighting to an existing dungeon layout.

    Takes a dungeon layout dict (as returned by generate_location_spec or
    _dungeon_to_geometry_ops) and augments it with theme-specific data:
    - Replaces/tags wall and floor materials
    - Adds themed prop placements to rooms
    - Sets lighting parameters

    Args:
        dungeon_layout: Dict with at minimum a "rooms" or "ops" key
            describing the dungeon structure.
        theme_name: Name of the theme to apply.

    Returns:
        A new dict combining the original layout with theme overlays.
        Original dict is not mutated.
    """
    theme = get_dungeon_theme(theme_name)
    result = dict(dungeon_layout)

    # Apply theme metadata
    result["theme"] = theme_name
    result["theme_config"] = theme

    # Tag operations with theme materials if ops list exists
    if "ops" in result:
        themed_ops = []
        for op in result["ops"]:
            new_op = dict(op)
            op_type = new_op.get("type", "")
            if op_type == "wall":
                new_op["material"] = theme["wall_material"]
            elif op_type in ("floor", "corridor"):
                new_op["material"] = theme["floor"]
            themed_ops.append(new_op)
        result["ops"] = themed_ops

    # Generate themed prop placements for rooms if rooms list exists
    if "rooms" in result:
        import random
        rng = random.Random(hash(theme_name))  # deterministic per theme
        themed_props: list[dict[str, Any]] = []
        rooms = result["rooms"]
        props_list = theme["props"]

        for room in rooms:
            # Place 1-3 theme-specific props per room
            n_props = rng.randint(1, min(3, len(props_list)))
            room_center = room.get("center")
            if room_center is None:
                # Try to compute center from position + dimensions
                pos = room.get("position", (0, 0))
                size = room.get("size", (4, 4))
                room_center = (
                    pos[0] + size[0] / 2 if isinstance(pos, (list, tuple)) else 0,
                    pos[1] + size[1] / 2 if isinstance(pos, (list, tuple)) else 0,
                )

            for _ in range(n_props):
                prop_type = rng.choice(props_list)
                offset_x = rng.uniform(-1.5, 1.5)
                offset_y = rng.uniform(-1.5, 1.5)
                themed_props.append({
                    "type": prop_type,
                    "position": (
                        room_center[0] + offset_x,
                        room_center[1] + offset_y,
                        0,
                    ),
                    "rotation": rng.uniform(0, 6.283),
                    "theme": theme_name,
                })

        result["themed_props"] = themed_props

    # Apply lighting config
    result["lighting"] = {
        "type": theme["lighting"],
        "ambient_color": theme["ambient_color"],
        "fog_density": theme["fog_density"],
    }

    return result


def get_theme_props(theme_name: str) -> list[str]:
    """Return the list of prop types for a given theme.

    Args:
        theme_name: One of the keys in DUNGEON_THEMES.

    Returns:
        List of prop type strings appropriate for the theme.

    Raises:
        ValueError: If theme_name is not recognised.
    """
    theme = get_dungeon_theme(theme_name)
    return list(theme["props"])


def get_theme_material(theme_name: str, surface: str = "wall") -> str:
    """Return the material name for a given theme and surface type.

    Args:
        theme_name: One of the keys in DUNGEON_THEMES.
        surface: "wall" or "floor".

    Returns:
        Material name string.

    Raises:
        ValueError: If theme_name is not recognised or surface is invalid.
    """
    theme = get_dungeon_theme(theme_name)
    if surface == "wall":
        return theme["wall_material"]
    elif surface == "floor":
        return theme["floor"]
    else:
        raise ValueError(f"Unknown surface type '{surface}'. Use 'wall' or 'floor'.")
