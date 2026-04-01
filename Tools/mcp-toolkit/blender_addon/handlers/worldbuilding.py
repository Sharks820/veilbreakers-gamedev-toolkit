"""Blender handlers for building generation, castles, ruins, interiors, modular kits.

Converts pure-logic BuildingSpec operations into Blender mesh geometry.
Provides 5 handler functions registered in COMMAND_HANDLERS.

Includes VeilBreakers-specific building and dungeon presets for shrines,
ruined fortresses, abandoned villages, forges, and themed dungeons.
"""

from __future__ import annotations

import copy
import logging
import math
import random
from typing import Any

import bpy
import bmesh
from mathutils import Vector

from .procedural_materials import create_procedural_material
from ._context import get_3d_context_override
from ._settlement_grammar import (
    PROP_PROMPTS,
    CORRUPTION_DESCS,
    get_prop_prompt,
    generate_prop_manifest,
    ring_for_position,
    _road_segment_mesh_spec_with_curbs,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prop cache: (prop_type, corruption_band) -> glb_path
# Persists for the Blender session to avoid regenerating across towns.
# ---------------------------------------------------------------------------
_PROP_CACHE: dict[tuple[str, str], str] = {}


def clear_prop_cache() -> None:
    """Clear the session-level prop GLB cache.

    Callable externally for testing or to force regeneration.
    """
    _PROP_CACHE.clear()


def _get_or_generate_prop(
    prop_type: str,
    corruption_band: str,
    prompt: str,
    blender_connection: Any | None = None,
) -> str | None:
    """Return a cached GLB path for a prop type, generating via Tripo if needed.

    Parameters
    ----------
    prop_type : str
        Prop category key (e.g. "lantern_post").
    corruption_band : str
        Corruption tier (e.g. "pristine", "corrupted").
    prompt : str
        Fully-formatted Tripo AI prompt string.
    blender_connection : Any, optional
        Active Blender socket connection for dispatching asset_pipeline calls.
        When None (testing), generation is skipped and None is returned.

    Returns
    -------
    str or None
        Absolute path to the generated GLB file, or None if generation failed.
    """
    key = (prop_type, corruption_band)
    if key in _PROP_CACHE:
        return _PROP_CACHE[key]

    if blender_connection is None:
        logger.debug("No blender_connection — skipping Tripo generation for %s/%s", prop_type, corruption_band)
        return None

    try:
        result = blender_connection.send_command_sync(
            "asset_pipeline",
            {
                "action": "generate_3d",
                "prompt": prompt,
                "art_style": "dark_fantasy",
            },
        )
        glb_path = result.get("glb_path") if isinstance(result, dict) else None
        if glb_path:
            _PROP_CACHE[key] = glb_path
            # Non-fatal post-process pass (delight + validate)
            try:
                blender_connection.send_command_sync(
                    "asset_pipeline",
                    {"action": "post_process_model", "glb_path": glb_path},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Post-process failed for %s/%s: %s", prop_type, corruption_band, exc)
            return glb_path
        logger.warning("Tripo generation returned no glb_path for %s/%s", prop_type, corruption_band)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tripo generation failed for %s/%s: %s", prop_type, corruption_band, exc)
        return None


def prefetch_town_props(
    prop_manifest: list[dict],
    veil_pressure: float = 0.0,
    blender_connection: Any | None = None,
) -> dict[tuple[str, str], str | None]:
    """Pre-generate unique (prop_type, corruption_band) combos for a town.

    Separates slow Tripo calls from fast Blender object placement.

    Parameters
    ----------
    prop_manifest : list of dict
        Prop spec dicts from generate_prop_manifest() — each must have
        "cache_key": (prop_type, corruption_band).
    veil_pressure : float
        Veil pressure (used for logging context only).
    blender_connection : Any, optional
        Active Blender socket connection. None in test mode.

    Returns
    -------
    dict
        {(prop_type, corruption_band): glb_path_or_None}
    """
    unique_keys: set[tuple[str, str]] = set()
    for spec in prop_manifest:
        ck = spec.get("cache_key")
        if isinstance(ck, (tuple, list)) and len(ck) == 2:
            unique_keys.add((str(ck[0]), str(ck[1])))

    already_cached = sum(1 for k in unique_keys if k in _PROP_CACHE)
    logger.info(
        "Prefetching %d prop types (%d already cached) for pressure=%.2f",
        len(unique_keys),
        already_cached,
        veil_pressure,
    )

    resolved: dict[tuple[str, str], str | None] = {}
    for prop_type, corruption_band in unique_keys:
        if (prop_type, corruption_band) in _PROP_CACHE:
            resolved[(prop_type, corruption_band)] = _PROP_CACHE[(prop_type, corruption_band)]
            continue
        try:
            prompt = get_prop_prompt(prop_type, corruption_band)
        except KeyError:
            logger.warning("Unknown prop_type/corruption_band: %s/%s", prop_type, corruption_band)
            resolved[(prop_type, corruption_band)] = None
            continue
        glb_path = _get_or_generate_prop(prop_type, corruption_band, prompt, blender_connection)
        resolved[(prop_type, corruption_band)] = glb_path
        logger.info("Generated prop: %s (%s) -> %s", prop_type, corruption_band, glb_path)

    logger.info(
        "Prefetched %d prop types (%d from cache)",
        len(unique_keys),
        already_cached,
    )
    return resolved


def _assign_procedural_material(obj: Any, material_key: str) -> bool:
    """Assign a procedural material to a mesh-like object."""
    try:
        if obj is None or not hasattr(obj, "data") or not hasattr(obj.data, "materials"):
            return False
        mat_name = f"{obj.name}_{material_key}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = create_procedural_material(mat_name, material_key)
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        return True
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug("Material assignment failed for %s (%s): %s", getattr(obj, "name", "<unnamed>"), material_key, exc)
        return False


def _assign_procedural_material_recursive(obj: Any, material_key: str) -> int:
    """Assign a procedural material to an object and its mesh descendants."""
    if obj is None:
        return 0
    count = 1 if _assign_procedural_material(obj, material_key) else 0
    for child in getattr(obj, "children", []):
        count += _assign_procedural_material_recursive(child, material_key)
    return count


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
        "roof_style": "shed",
        "roof_material": "slate",
    },
    "inn": {
        "style": "medieval",
        "floors": 2,
        "width": 10.0, "depth": 8.0,
        "wall_height": 4.0,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "square"},
            {"type": "window", "wall": "left", "floor": 0, "style": "square"},
            {"type": "window", "wall": "right", "floor": 0, "style": "square"},
            {"type": "window", "wall": "left", "floor": 1, "style": "square"},
            {"type": "window", "wall": "right", "floor": 1, "style": "square"},
        ],
        "props": ["market_stall", "signpost", "barrel", "crate", "hay_bale"],
        "roof_style": "gable",
        "roof_material": "tile",
    },
    "warehouse": {
        "style": "medieval",
        "floors": 2,
        "width": 12.0, "depth": 9.0,
        "wall_height": 4.3,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "large_arch"},
            {"type": "window", "wall": "left", "floor": 0, "style": "square"},
            {"type": "window", "wall": "right", "floor": 0, "style": "square"},
        ],
        "props": ["crate", "barrel", "wagon_wheel", "signpost"],
        "roof_style": "shed",
        "roof_material": "slate",
    },
    "barracks": {
        "style": "fortress",
        "floors": 2,
        "width": 12.0, "depth": 8.5,
        "wall_height": 4.6,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "large_arch"},
            {"type": "window", "wall": "left", "floor": 0, "style": "arrow_slit"},
            {"type": "window", "wall": "right", "floor": 0, "style": "arrow_slit"},
            {"type": "window", "wall": "left", "floor": 1, "style": "arrow_slit"},
            {"type": "window", "wall": "right", "floor": 1, "style": "arrow_slit"},
        ],
        "props": ["weapon_rack", "bunk_bed", "barrel", "crate", "brazier"],
        "roof_style": "flat",
        "roof_material": "stone",
    },
    "gatehouse": {
        "style": "fortress",
        "floors": 2,
        "width": 8.0, "depth": 6.5,
        "wall_height": 5.2,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "large_arch"},
            {"type": "window", "wall": "left", "floor": 0, "style": "arrow_slit"},
            {"type": "window", "wall": "right", "floor": 0, "style": "arrow_slit"},
            {"type": "window", "wall": "left", "floor": 1, "style": "arrow_slit"},
            {"type": "window", "wall": "right", "floor": 1, "style": "arrow_slit"},
        ],
        "props": ["gate", "barrel", "crate", "signpost"],
        "roof_style": "flat",
        "roof_material": "stone",
    },
    "rowhouse": {
        "style": "medieval",
        "floors": 2,
        "width": 6.0, "depth": 5.0,
        "wall_height": 3.4,
        "has_roof": True,
        "openings": [
            {"type": "door", "wall": "front", "floor": 0, "style": "square"},
            {"type": "window", "wall": "left", "floor": 0, "style": "square"},
            {"type": "window", "wall": "right", "floor": 0, "style": "square"},
            {"type": "window", "wall": "front", "floor": 1, "style": "square"},
        ],
        "props": ["barrel", "crate", "signpost"],
        "roof_style": "gable",
        "roof_material": "tile",
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
    apply_ruins_damage,
    generate_interior_layout,
    generate_clutter_layout,
    generate_lighting_layout,
    generate_modular_pieces,
    generate_overrun_variant,
    add_storytelling_props,
    plan_modular_facade,
    BuildingSpec,
    STYLE_CONFIGS,
)
from ._dungeon_gen import generate_multi_floor_dungeon, generate_dungeon_prop_placements
from .building_quality import (
    generate_stone_wall,
    generate_gothic_window,
    generate_roof,
    generate_archway,
    generate_chimney,
)
from ._mesh_bridge import (
    mesh_from_spec,
    FURNITURE_GENERATOR_MAP,
    CASTLE_ELEMENT_MAP,
    DUNGEON_PROP_MAP,
    PROP_GENERATOR_MAP,
)
from .procedural_meshes import (
    generate_bridge_mesh,
    generate_buttress_mesh,
    generate_column_row_mesh,
    generate_fence_mesh,
    generate_staircase_mesh,
)
from .settlement_generator import generate_settlement
from .map_composer import compose_world_map
from .encounter_spaces import compute_encounter_layout, validate_encounter_layout
from .worldbuilding_layout import (
    generate_boss_arena_spec,
    generate_easter_egg_spec,
    generate_linked_interior_spec,
    generate_location_spec,
    generate_world_graph,
    _ops_to_mesh,
)


# ---------------------------------------------------------------------------
# Opening-aware building helpers
# ---------------------------------------------------------------------------

_WALL_NAME_TO_INDEX = {
    "front": 0,
    "back": 1,
    "left": 2,
    "right": 3,
}


def _building_opening_profile(
    opening_type: str,
    opening_style: str,
    *,
    wall_height: float,
    is_gothic: bool,
) -> dict[str, Any]:
    """Resolve opening dimensions and generator styles for a building opening."""
    kind = str(opening_type or "window").strip().lower()
    style_key = str(opening_style or "").strip().lower()

    if kind == "door":
        width = 1.2
        height = min(max(2.2, wall_height * 0.64), wall_height - 0.18)
        arch_style = "gothic_pointed" if is_gothic else "roman_round"
        if style_key in {"gothic_arch", "pointed_arch", "large_arch"}:
            arch_style = "gothic_pointed" if style_key != "large_arch" else "ogee"
            width = 1.55 if style_key != "large_arch" else 1.8
            height = min(max(2.45, wall_height * 0.72), wall_height - 0.12)
        elif style_key in {"square", "plank"}:
            arch_style = "flat_lintel"
            width = 1.1
        elif style_key == "iron_gate":
            arch_style = "flat_lintel"
            width = 1.55
            height = min(max(2.5, wall_height * 0.74), wall_height - 0.1)
        elif style_key in {"rounded", "round", "round_arch", "wooden_arched"}:
            arch_style = "roman_round"
        return {
            "kind": "door",
            "width": width,
            "height": height,
            "bottom": 0.0,
            "window_style": None,
            "door_arch_style": arch_style,
        }

    width = 0.9
    height = min(max(1.1, wall_height * 0.34), wall_height * 0.55)
    bottom = wall_height * 0.28
    mesh_style = "pointed_arch" if is_gothic else "rectangular"
    has_sill = True

    if style_key in {"pointed_arch", "lancet"}:
        width = 0.72 if style_key == "lancet" else 0.82
        height = min(max(1.5, wall_height * 0.46), wall_height * 0.68)
        bottom = wall_height * 0.24
        mesh_style = "lancet" if style_key == "lancet" else "pointed_arch"
    elif style_key in {"round", "round_arch"}:
        width = 0.86
        height = min(max(1.2, wall_height * 0.36), wall_height * 0.52)
        bottom = wall_height * 0.3
        mesh_style = "round_arch"
    elif style_key in {"square", "rectangular"}:
        width = 0.9
        height = min(max(0.95, wall_height * 0.32), wall_height * 0.42)
        bottom = wall_height * 0.3
        mesh_style = "rectangular"
    elif style_key == "large_rectangular":
        width = 1.3
        height = min(max(1.3, wall_height * 0.4), wall_height * 0.55)
        bottom = wall_height * 0.24
        mesh_style = "rectangular"
    elif style_key == "rose_window":
        width = min(max(1.15, wall_height * 0.28), 1.75)
        height = width
        bottom = wall_height * 0.48
        mesh_style = "rose_window"
        has_sill = False
    elif style_key == "arrow_slit":
        width = 0.24
        height = min(max(1.2, wall_height * 0.42), wall_height * 0.62)
        bottom = wall_height * 0.34
        mesh_style = "arrow_slit"
        has_sill = False

    return {
        "kind": "window",
        "width": width,
        "height": height,
        "bottom": bottom,
        "window_style": mesh_style,
        "door_arch_style": None,
        "has_sill": has_sill,
    }


def _place_openings_on_wall(
    requested: list[dict[str, Any]],
    *,
    wall_length: float,
    wall_height: float,
) -> list[dict[str, Any]]:
    """Assign horizontal centers to requested openings on a single wall/floor."""
    if wall_length <= 0.0 or not requested:
        return []

    resolved: list[dict[str, Any]] = []
    explicit_items: list[dict[str, Any]] = []
    auto_doors: list[dict[str, Any]] = []
    auto_windows: list[dict[str, Any]] = []

    for item in requested:
        center = item.get("center")
        if center is None and "position" in item and isinstance(item["position"], (list, tuple)) and item["position"]:
            center = float(item["position"][0])
        if center is not None:
            explicit_items.append({**item, "center": float(center)})
        elif item["kind"] == "door":
            auto_doors.append(item)
        else:
            auto_windows.append(item)

    edge_margin = max(
        0.5,
        max((float(item["width"]) * 0.55 for item in requested), default=0.5),
    )
    usable_start = edge_margin
    usable_end = max(usable_start, wall_length - edge_margin)

    if len(auto_doors) == 1:
        door = auto_doors[0]
        door_center = wall_length * 0.5
        resolved.append({**door, "center": door_center})

        if auto_windows:
            clearance = max(0.4, float(door["width"]) * 0.55)
            left_start = usable_start
            left_end = door_center - float(door["width"]) * 0.5 - clearance
            right_start = door_center + float(door["width"]) * 0.5 + clearance
            right_end = usable_end

            left_room = max(0.0, left_end - left_start)
            right_room = max(0.0, right_end - right_start)
            left_count = 0
            right_count = 0
            if left_room <= 0.0 and right_room <= 0.0:
                right_count = len(auto_windows)
                right_start = usable_start
                right_end = usable_end
            elif left_room <= 0.0:
                right_count = len(auto_windows)
            elif right_room <= 0.0:
                left_count = len(auto_windows)
            else:
                right_count = len(auto_windows) // 2
                left_count = len(auto_windows) - right_count
                if len(auto_windows) % 2 == 1 and right_room > left_room:
                    right_count += 1
                    left_count -= 1

            window_index = 0
            for side_count, start, end in (
                (left_count, left_start, left_end),
                (right_count, right_start, right_end),
            ):
                if side_count <= 0:
                    continue
                spacing = (end - start) / (side_count + 1) if end > start else 0.0
                for slot_idx in range(side_count):
                    center = start + spacing * (slot_idx + 1) if spacing > 0.0 else wall_length * 0.5
                    resolved.append({**auto_windows[window_index], "center": center})
                    window_index += 1
    else:
        ordered_auto = auto_doors + auto_windows
        auto_count = len(ordered_auto)
        if auto_count:
            spacing = (usable_end - usable_start) / (auto_count + 1) if usable_end > usable_start else 0.0
            for idx, item in enumerate(ordered_auto):
                center = usable_start + spacing * (idx + 1) if spacing > 0.0 else wall_length * 0.5
                resolved.append({**item, "center": center})

    resolved.extend(explicit_items)
    output: list[dict[str, Any]] = []
    for item in resolved:
        half_width = max(0.15, float(item["width"]) * 0.5)
        center_min = half_width + 0.08
        center_max = max(center_min, wall_length - half_width - 0.08)
        center = min(max(center_min, float(item["center"])), center_max)
        bottom = min(
            max(0.0, float(item["bottom"])),
            max(0.0, wall_height - float(item["height"]) - 0.06),
        )
        output.append({**item, "center": center, "bottom": bottom})

    output.sort(key=lambda item: (item["center"], 0 if item["kind"] == "door" else 1))
    return output


def _resolve_building_openings(
    *,
    width: float,
    depth: float,
    floors: int,
    wall_height: float,
    wall_thickness: float,
    style: str,
    requested_openings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Resolve building openings into concrete wall placements and metadata."""
    is_gothic = style in {"gothic", "fortress"}
    side_wall_length = max(0.0, depth - 2.0 * wall_thickness)
    wall_lengths = {
        "front": width,
        "back": width,
        "left": side_wall_length,
        "right": side_wall_length,
    }

    requested = list(requested_openings or [])
    if not requested:
        default_window_style = "arrow_slit" if style == "fortress" else ("pointed_arch" if is_gothic else "rectangular")
        front_back_count = max(1, int(width / (4.5 if style == "fortress" else 3.6)))
        side_count = max(1, int(side_wall_length / (5.0 if style == "fortress" else 4.2))) if side_wall_length > 0.0 else 0
        requested.append({"type": "door", "wall": "front", "floor": 0, "style": "large_arch" if is_gothic else "rounded"})
        for floor_idx in range(max(1, floors)):
            if floor_idx > 0:
                for _ in range(front_back_count):
                    requested.append({"type": "window", "wall": "front", "floor": floor_idx, "style": default_window_style})
            for _ in range(front_back_count):
                requested.append({"type": "window", "wall": "back", "floor": floor_idx, "style": default_window_style})
            for wall_name in ("left", "right"):
                for _ in range(side_count):
                    requested.append({"type": "window", "wall": wall_name, "floor": floor_idx, "style": default_window_style})

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for raw in requested:
        wall_name = str(raw.get("wall", "front")).strip().lower()
        if wall_name not in wall_lengths:
            continue
        floor_idx = max(0, min(max(0, floors - 1), int(raw.get("floor", 0))))
        profile = _building_opening_profile(
            str(raw.get("type", "window")),
            str(raw.get("style", "")),
            wall_height=wall_height,
            is_gothic=is_gothic,
        )
        wall_length = wall_lengths[wall_name]
        max_width = max(0.35, wall_length - 0.28)
        profile["width"] = min(float(profile["width"]), max_width)
        if profile["kind"] == "door":
            profile["width"] = max(1.2, profile["width"])
            profile["height"] = max(2.2, float(profile["height"]))
        else:
            profile["width"] = max(0.9, profile["width"])
            profile["height"] = max(1.1, float(profile["height"]))
        if profile["width"] <= 0.3 or profile["height"] <= 0.3:
            continue
        grouped.setdefault((wall_name, floor_idx), []).append({
            **profile,
            "wall": wall_name,
            "wall_index": _WALL_NAME_TO_INDEX[wall_name],
            "floor": floor_idx,
            "floor_base_z": floor_idx * wall_height,
            "requested_style": str(raw.get("style", "")),
            "center": raw.get("center"),
            "position": raw.get("position"),
        })

    resolved: list[dict[str, Any]] = []
    for (wall_name, floor_idx), items in grouped.items():
        wall_length = wall_lengths[wall_name]
        placed = _place_openings_on_wall(
            items,
            wall_length=wall_length,
            wall_height=wall_height,
        )
        for item in placed:
            resolved.append({
                **item,
                "wall_length": wall_length,
                "world_bottom": item["floor_base_z"] + item["bottom"],
            })

    resolved.sort(key=lambda item: (item["wall_index"], item["floor"], item["center"]))
    return resolved


def _compute_wall_segments(
    wall_length: float,
    wall_height: float,
    openings: list[dict[str, Any]],
) -> tuple[list[dict[str, float]], list[dict[str, Any]]]:
    """Split a wall into non-overlapping solid rectangles around openings."""
    if wall_length <= 0.0 or wall_height <= 0.0:
        return [], []

    clamped: list[dict[str, Any]] = []
    for opening in openings:
        half_width = max(0.15, float(opening["width"]) * 0.5)
        u0 = max(0.0, float(opening["center"]) - half_width)
        u1 = min(wall_length, float(opening["center"]) + half_width)
        v0 = max(0.0, float(opening["bottom"]))
        v1 = min(wall_height, float(opening["bottom"]) + float(opening["height"]))
        if u1 - u0 < 0.05 or v1 - v0 < 0.05:
            continue
        clamped.append({**opening, "u0": u0, "u1": u1, "v0": v0, "v1": v1})

    if not clamped:
        return [{"u0": 0.0, "u1": wall_length, "v0": 0.0, "v1": wall_height}], []

    edges_u = sorted({0.0, wall_length, *(edge for op in clamped for edge in (op["u0"], op["u1"]))})
    segments: list[dict[str, float]] = []
    for idx in range(len(edges_u) - 1):
        u0 = edges_u[idx]
        u1 = edges_u[idx + 1]
        if u1 - u0 < 0.05:
            continue

        overlapping = [
            op for op in clamped
            if op["u0"] < u1 - 1e-4 and op["u1"] > u0 + 1e-4
        ]
        if not overlapping:
            segments.append({"u0": u0, "u1": u1, "v0": 0.0, "v1": wall_height})
            continue

        edges_v = sorted({0.0, wall_height, *(edge for op in overlapping for edge in (op["v0"], op["v1"]))})
        for v_idx in range(len(edges_v) - 1):
            v0 = edges_v[v_idx]
            v1 = edges_v[v_idx + 1]
            if v1 - v0 < 0.05:
                continue
            blocked = any(
                v0 >= op["v0"] - 1e-4 and v1 <= op["v1"] + 1e-4
                for op in overlapping
            )
            if not blocked:
                segments.append({"u0": u0, "u1": u1, "v0": v0, "v1": v1})

    return segments, clamped


# ---------------------------------------------------------------------------
# Pure-logic: BuildingSpec -> mesh primitive specs (testable without Blender)
# ---------------------------------------------------------------------------


def _collect_openings_by_wall(spec: BuildingSpec) -> dict[tuple[int, int], list[dict]]:
    """Group opening operations by (wall_index, floor).

    Returns dict mapping (wall_index, floor) -> list of opening ops sorted
    by horizontal offset so left-to-right splitting is deterministic.
    Pure-logic helper -- no bpy/bmesh.
    """
    openings: dict[tuple[int, int], list[dict]] = {}
    for op in spec.operations:
        if op.get("type") != "opening":
            continue
        key = (op.get("wall_index", 0), op.get("floor", 0))
        openings.setdefault(key, [])
        openings[key].append(op)
    # Sort each group by horizontal offset (position[0])
    for key in openings:
        openings[key].sort(key=lambda o: o.get("position", [0, 0])[0])
    return openings


def _wall_with_openings(
    px: float, py: float, pz: float,
    sx: float, sy: float, sz: float,
    wall_index: int,
    openings: list[dict],
    material: str,
    style: str = "medieval",
) -> list[dict]:
    """Build mesh specs for a wall segment with rectangular openings cut through.

    Walls 0,1 run along X (front/back); walls 2,3 run along Y (left/right).
    Each opening's position[0] = offset along the wall's length axis,
    position[1] = offset from the wall's base Z.

    The wall is subdivided into horizontal strips. For each opening we create:
      - Frame quads on both exterior faces (front/back of the wall)
      - Reveal quads through the wall thickness (top, bottom, sides of hole)
      - Optional pointed-arch top for gothic windows

    Returns a list of mesh-spec dicts (type="box" with custom verts/faces).
    """
    result: list[dict] = []

    # Determine wall-length axis and thickness axis
    # Walls 0,1: length along X (sx), thickness along Y (sy)
    # Walls 2,3: length along Y (sy), thickness along X (sx)
    is_xy = wall_index < 2  # wall runs along X
    wall_len = sx if is_xy else sy
    wall_thick = sy if is_xy else sx
    wall_height = sz

    # Clamp openings to wall bounds
    clamped = []
    for op in openings:
        o_off = op["position"][0]  # offset along wall length
        o_z = op["position"][1]    # height from wall base
        o_w = max(0.2, float(op["size"][0]))
        o_h = max(0.2, float(op["size"][1]))
        o_w = min(o_w, max(0.2, wall_len - 0.1))
        o_h = min(o_h, max(0.2, wall_height - 0.1))
        # Clamp to wall dimensions
        o_off = max(0.0, min(o_off, wall_len - o_w))
        o_z = max(0.0, min(o_z, wall_height - o_h))
        clamped.append({
            "off": o_off,
            "z": o_z,
            "w": o_w,
            "h": o_h,
            "role": op.get("role", "opening"),
            "style": op.get("style", ""),
        })

    # Build the wall face with holes by constructing individual quads.
    # We work in a local 2D coordinate system:
    #   u = along wall length [0..wall_len]
    #   v = along wall height [0..wall_height]
    # Then map (u, v) back to 3D.

    def _local_to_world(u: float, v: float, depth: float) -> tuple:
        """Map local (u=along wall, v=up, depth=into wall) to world coords."""
        if is_xy:
            return (px + u, py + depth, pz + v)
        else:
            return (px + depth, py + u, pz + v)

    def _make_quad(p0, p1, p2, p3, role: str, mat: str) -> dict:
        """Create a single-quad mesh spec from 4 world-space points."""
        verts = [p0, p1, p2, p3]
        faces = [(0, 1, 2, 3)]
        return {
            "type": "box",
            "vertices": verts,
            "faces": faces,
            "vertex_count": 4,
            "face_count": 1,
            "material": mat,
            "role": role,
        }

    # For each face layer (front face at depth=0, back face at depth=wall_thick),
    # build frame quads around each opening.

    # Strategy: for each opening, emit the 4 (or 3 for doors at floor) frame
    # strips on front and back faces, plus 4 reveal quads through the thickness.
    # The solid portions of the wall (regions with no opening) are emitted as
    # full-height quads spanning between openings.

    # Step 1: Build solid wall strips between/around openings (front + back)
    # Collect vertical "columns" separated by opening edges along u-axis
    edges_u = [0.0]
    for c in clamped:
        edges_u.append(c["off"])
        edges_u.append(c["off"] + c["w"])
    edges_u.append(wall_len)
    edges_u = sorted(set(edges_u))

    for i in range(len(edges_u) - 1):
        u0 = edges_u[i]
        u1 = edges_u[i + 1]
        if u1 - u0 < 1e-4:
            continue

        # Check which openings overlap this column
        col_openings = []
        for c in clamped:
            if c["off"] < u1 - 1e-4 and c["off"] + c["w"] > u0 + 1e-4:
                col_openings.append(c)

        if not col_openings:
            # Solid wall strip -- full height, front face
            p0 = _local_to_world(u0, 0.0, 0.0)
            p1 = _local_to_world(u1, 0.0, 0.0)
            p2 = _local_to_world(u1, wall_height, 0.0)
            p3 = _local_to_world(u0, wall_height, 0.0)
            result.append(_make_quad(p0, p1, p2, p3, "wall", material))
            # Back face
            p0b = _local_to_world(u0, 0.0, wall_thick)
            p1b = _local_to_world(u1, 0.0, wall_thick)
            p2b = _local_to_world(u1, wall_height, wall_thick)
            p3b = _local_to_world(u0, wall_height, wall_thick)
            result.append(_make_quad(p1b, p0b, p3b, p2b, "wall", material))
        else:
            # This column overlaps one or more openings.
            # Build horizontal strips: below opening, above opening, and between
            # stacked openings (rare but handled).
            v_edges = [0.0]
            for c in col_openings:
                v_edges.append(c["z"])
                v_edges.append(c["z"] + c["h"])
            v_edges.append(wall_height)
            v_edges = sorted(set(v_edges))

            for j in range(len(v_edges) - 1):
                v0 = v_edges[j]
                v1 = v_edges[j + 1]
                if v1 - v0 < 1e-4:
                    continue

                # Is this v-span inside an opening?
                is_opening = False
                opening_for_span = None
                for c in col_openings:
                    if v0 >= c["z"] - 1e-4 and v1 <= c["z"] + c["h"] + 1e-4:
                        is_opening = True
                        opening_for_span = c
                        break

                if not is_opening:
                    # Solid strip
                    p0 = _local_to_world(u0, v0, 0.0)
                    p1 = _local_to_world(u1, v0, 0.0)
                    p2 = _local_to_world(u1, v1, 0.0)
                    p3 = _local_to_world(u0, v1, 0.0)
                    result.append(_make_quad(p0, p1, p2, p3, "wall", material))
                    # Back face
                    p0b = _local_to_world(u0, v0, wall_thick)
                    p1b = _local_to_world(u1, v0, wall_thick)
                    p2b = _local_to_world(u1, v1, wall_thick)
                    p3b = _local_to_world(u0, v1, wall_thick)
                    result.append(_make_quad(p1b, p0b, p3b, p2b, "wall", material))
                # else: this is the opening hole -- no face here (walkable/visible)

    # Step 2: Reveal/jamb quads through wall thickness for each opening
    for c in clamped:
        o_u0 = c["off"]
        o_u1 = c["off"] + c["w"]
        o_v0 = c["z"]
        o_v1 = c["z"] + c["h"]

        # Top reveal (horizontal quad at top of opening, connecting front to back)
        t0 = _local_to_world(o_u0, o_v1, 0.0)
        t1 = _local_to_world(o_u1, o_v1, 0.0)
        t2 = _local_to_world(o_u1, o_v1, wall_thick)
        t3 = _local_to_world(o_u0, o_v1, wall_thick)
        result.append(_make_quad(t0, t1, t2, t3, "opening_reveal", material))

        # Bottom reveal (only for windows, not for doors at floor level)
        if o_v0 > 0.05:
            b0 = _local_to_world(o_u0, o_v0, 0.0)
            b1 = _local_to_world(o_u1, o_v0, 0.0)
            b2 = _local_to_world(o_u1, o_v0, wall_thick)
            b3 = _local_to_world(o_u0, o_v0, wall_thick)
            result.append(_make_quad(b1, b0, b3, b2, "opening_reveal", material))

            # Window sill (slightly protruding ledge for windows)
            if c["role"] == "window":
                sill_depth = 0.08
                sill_thick = 0.05
                s0 = _local_to_world(o_u0 - 0.02, o_v0 - sill_thick, -sill_depth)
                s1 = _local_to_world(o_u1 + 0.02, o_v0 - sill_thick, -sill_depth)
                s2 = _local_to_world(o_u1 + 0.02, o_v0, -sill_depth)
                s3 = _local_to_world(o_u0 - 0.02, o_v0, -sill_depth)
                result.append(_make_quad(s0, s1, s2, s3, "window_sill", material))
                # Sill top face
                s4 = _local_to_world(o_u0 - 0.02, o_v0, 0.0)
                s5 = _local_to_world(o_u1 + 0.02, o_v0, 0.0)
                result.append(_make_quad(s3, s2, s5, s4, "window_sill", material))

        # Left reveal (vertical quad on left side of opening)
        l0 = _local_to_world(o_u0, o_v0, 0.0)
        l1 = _local_to_world(o_u0, o_v1, 0.0)
        l2 = _local_to_world(o_u0, o_v1, wall_thick)
        l3 = _local_to_world(o_u0, o_v0, wall_thick)
        result.append(_make_quad(l1, l0, l3, l2, "opening_reveal", material))

        # Right reveal (vertical quad on right side of opening)
        r0 = _local_to_world(o_u1, o_v0, 0.0)
        r1 = _local_to_world(o_u1, o_v1, 0.0)
        r2 = _local_to_world(o_u1, o_v1, wall_thick)
        r3 = _local_to_world(o_u1, o_v0, wall_thick)
        result.append(_make_quad(r0, r1, r2, r3, "opening_reveal", material))

    # Step 3: Door/window frame geometry (thin border around opening)
    frame_thick = 0.06  # frame profile thickness
    frame_depth = 0.04  # how far frame protrudes from wall face
    for c in clamped:
        o_u0 = c["off"]
        o_u1 = c["off"] + c["w"]
        o_v0 = c["z"]
        o_v1 = c["z"] + c["h"]
        frame_role = "door_frame" if c["role"] == "door" else "window_frame"
        frame_mat = "wood_dark" if c["role"] == "door" else material

        # Frame is 4 strips (3 for doors: no bottom strip) on the front face
        # Left frame strip
        fl0 = _local_to_world(o_u0 - frame_thick, o_v0, -frame_depth)
        fl1 = _local_to_world(o_u0, o_v0, -frame_depth)
        fl2 = _local_to_world(o_u0, o_v1, -frame_depth)
        fl3 = _local_to_world(o_u0 - frame_thick, o_v1, -frame_depth)
        result.append(_make_quad(fl0, fl1, fl2, fl3, frame_role, frame_mat))

        # Right frame strip
        fr0 = _local_to_world(o_u1, o_v0, -frame_depth)
        fr1 = _local_to_world(o_u1 + frame_thick, o_v0, -frame_depth)
        fr2 = _local_to_world(o_u1 + frame_thick, o_v1, -frame_depth)
        fr3 = _local_to_world(o_u1, o_v1, -frame_depth)
        result.append(_make_quad(fr0, fr1, fr2, fr3, frame_role, frame_mat))

        # Top frame strip (lintel)
        # For gothic pointed-arch windows, add a triangular peak
        is_gothic = c.get("style", "") == "pointed_arch"
        if is_gothic:
            # Pointed arch: triangle peak above the rectangular top
            arch_rise = min(c["w"] * 0.4, 0.5)
            peak_u = (o_u0 + o_u1) / 2.0
            peak_v = o_v1 + arch_rise
            # Left arch slope
            al0 = _local_to_world(o_u0 - frame_thick, o_v1, -frame_depth)
            al1 = _local_to_world(peak_u, peak_v, -frame_depth)
            al2 = _local_to_world(peak_u, peak_v + frame_thick, -frame_depth)
            al3 = _local_to_world(o_u0 - frame_thick, o_v1 + frame_thick, -frame_depth)
            result.append(_make_quad(al0, al1, al2, al3, frame_role, frame_mat))
            # Right arch slope
            ar0 = _local_to_world(peak_u, peak_v, -frame_depth)
            ar1 = _local_to_world(o_u1 + frame_thick, o_v1, -frame_depth)
            ar2 = _local_to_world(o_u1 + frame_thick, o_v1 + frame_thick, -frame_depth)
            ar3 = _local_to_world(peak_u, peak_v + frame_thick, -frame_depth)
            result.append(_make_quad(ar0, ar1, ar2, ar3, frame_role, frame_mat))
        else:
            ft0 = _local_to_world(o_u0 - frame_thick, o_v1, -frame_depth)
            ft1 = _local_to_world(o_u1 + frame_thick, o_v1, -frame_depth)
            ft2 = _local_to_world(o_u1 + frame_thick, o_v1 + frame_thick, -frame_depth)
            ft3 = _local_to_world(o_u0 - frame_thick, o_v1 + frame_thick, -frame_depth)
            result.append(_make_quad(ft0, ft1, ft2, ft3, frame_role, frame_mat))

        # Bottom frame strip (only for windows with a sill, not doors)
        if c["role"] == "window" and o_v0 > 0.05:
            fb0 = _local_to_world(o_u0 - frame_thick, o_v0 - frame_thick, -frame_depth)
            fb1 = _local_to_world(o_u1 + frame_thick, o_v0 - frame_thick, -frame_depth)
            fb2 = _local_to_world(o_u1 + frame_thick, o_v0, -frame_depth)
            fb3 = _local_to_world(o_u0 - frame_thick, o_v0, -frame_depth)
            result.append(_make_quad(fb0, fb1, fb2, fb3, frame_role, frame_mat))

    # Step 4: Top and bottom caps of the wall (unchanged)
    # Bottom face
    p_b0 = _local_to_world(0.0, 0.0, 0.0)
    p_b1 = _local_to_world(wall_len, 0.0, 0.0)
    p_b2 = _local_to_world(wall_len, 0.0, wall_thick)
    p_b3 = _local_to_world(0.0, 0.0, wall_thick)
    result.append(_make_quad(p_b0, p_b1, p_b2, p_b3, "wall", material))
    # Top face
    p_t0 = _local_to_world(0.0, wall_height, 0.0)
    p_t1 = _local_to_world(wall_len, wall_height, 0.0)
    p_t2 = _local_to_world(wall_len, wall_height, wall_thick)
    p_t3 = _local_to_world(0.0, wall_height, wall_thick)
    result.append(_make_quad(p_t1, p_t0, p_t3, p_t2, "wall", material))

    # Left end cap (u=0)
    ec_l0 = _local_to_world(0.0, 0.0, 0.0)
    ec_l1 = _local_to_world(0.0, wall_height, 0.0)
    ec_l2 = _local_to_world(0.0, wall_height, wall_thick)
    ec_l3 = _local_to_world(0.0, 0.0, wall_thick)
    result.append(_make_quad(ec_l1, ec_l0, ec_l3, ec_l2, "wall", material))
    # Right end cap (u=wall_len)
    ec_r0 = _local_to_world(wall_len, 0.0, 0.0)
    ec_r1 = _local_to_world(wall_len, wall_height, 0.0)
    ec_r2 = _local_to_world(wall_len, wall_height, wall_thick)
    ec_r3 = _local_to_world(wall_len, 0.0, wall_thick)
    result.append(_make_quad(ec_r0, ec_r1, ec_r2, ec_r3, "wall", material))

    return result


def _wall_solid_box(
    px: float, py: float, pz: float,
    sx: float, sy: float, sz: float,
    material: str, role: str,
) -> dict:
    """Create a standard solid box mesh spec (no openings). Pure-logic."""
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
    faces = [
        (0, 1, 2, 3),  # bottom
        (4, 7, 6, 5),  # top
        (0, 4, 5, 1),  # front
        (2, 6, 7, 3),  # back
        (0, 3, 7, 4),  # left
        (1, 5, 6, 2),  # right
    ]
    return {
        "type": "box",
        "vertices": verts,
        "faces": faces,
        "vertex_count": 8,
        "face_count": 6,
        "material": material,
        "role": role,
    }


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

    # Collect openings indexed by (wall_index, floor)
    openings_map = _collect_openings_by_wall(spec)

    for op in spec.operations:
        op_type = op.get("type")

        if op_type == "box":
            pos = op["position"]
            size = op["size"]
            px, py, pz = pos[0], pos[1], pos[2]
            sx, sy, sz = size[0], size[1], size[2]

            # Check if this is a wall with openings
            if op.get("role") == "wall":
                wall_idx = op.get("wall_index", -1)
                floor_idx = op.get("floor", -1)
                key = (wall_idx, floor_idx)
                wall_openings = openings_map.get(key, [])

                if wall_openings:
                    # Generate wall with holes cut for openings
                    wall_specs = _wall_with_openings(
                        px, py, pz, sx, sy, sz,
                        wall_idx, wall_openings,
                        material=op.get("material", "default"),
                        style=spec.style,
                    )
                    result.extend(wall_specs)
                    continue

            # Standard solid box (non-wall, or wall without openings)
            result.append(_wall_solid_box(
                px, py, pz, sx, sy, sz,
                material=op.get("material", "default"),
                role=op.get("role", "unknown"),
            ))

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

        elif op_type == "tower":
            pos = op["position"]
            cx, cy, cz = pos[0], pos[1], pos[2]
            radius = float(op.get("radius", 3.0))
            height = float(op.get("height", 12.0))
            segments = max(6, int(op.get("segments", 8)))
            taper = max(0.55, min(1.0, float(op.get("taper", 0.9))))
            crown_height = max(0.6, min(height * 0.2, float(op.get("crown_height", max(0.9, height * 0.12)))))
            body_height = max(0.1, height - crown_height)
            top_radius = radius * taper
            crown_radius = radius * max(0.95, taper * 1.05)
            profile = str(op.get("profile", "fortress"))
            if profile == "fortress":
                base_profile = 0.34
                mid_profile = 0.24
                top_profile = 0.14
                crown_profile = 0.08
            elif profile == "keep":
                base_profile = 0.26
                mid_profile = 0.18
                top_profile = 0.10
                crown_profile = 0.06
            else:
                base_profile = 0.14
                mid_profile = 0.10
                top_profile = 0.06
                crown_profile = 0.04

            verts: list[tuple[float, float, float]] = []
            faces: list[tuple[int, ...]] = []

            def add_ring(z_offset: float, ring_radius: float, profile_strength: float = 0.0, phase: float = 0.0) -> int:
                ring_start = len(verts)
                for i in range(segments):
                    angle = 2.0 * math.pi * i / segments
                    if profile_strength > 0.0:
                        lobe = math.cos(angle * 4.0 + phase)
                        facet = math.cos(angle * 8.0 + phase * 0.5)
                        radial = 1.0 + profile_strength * (0.72 * lobe + 0.28 * facet)
                    else:
                        radial = 1.0
                    verts.append((
                        cx + math.cos(angle) * ring_radius * radial,
                        cy + math.sin(angle) * ring_radius * radial,
                        cz + z_offset,
                    ))
                return ring_start

            ring_specs = [
                (0.0, radius * 1.18, base_profile * 1.08, 0.0),
                (body_height * 0.15, radius * 1.12, base_profile * 0.82, math.pi / 14.0),
                (body_height * 0.42, max(radius * 0.96, (radius + top_radius) * 0.60), mid_profile * 1.10, math.pi / 8.0),
                (body_height * 0.70, max(radius * 0.82, top_radius * 1.04), top_profile * 1.05, math.pi / 4.0),
                (height, crown_radius * 0.98, crown_profile, math.pi / 6.0),
            ]
            ring_starts: list[int] = []
            for z_offset, ring_radius, profile_strength, phase in ring_specs:
                ring_starts.append(add_ring(z_offset, ring_radius, profile_strength, phase))

            for base, top in zip(ring_starts[:-1], ring_starts[1:]):
                for i in range(segments):
                    i_next = (i + 1) % segments
                    faces.append((base + i, base + i_next, top + i_next, top + i))

            faces.append(tuple(range(ring_starts[0] + segments - 1, ring_starts[0] - 1, -1)))
            faces.append(tuple(range(ring_starts[-1], ring_starts[-1] + segments)))

            # Battered base skirt and attached buttresses break the pure cylinder read.
            skirt_w = radius * 2.28
            skirt_h = max(0.32, height * 0.16)
            skirt_spec = _wall_solid_box(
                cx - skirt_w * 0.5,
                cy - skirt_w * 0.5,
                cz - skirt_h * 0.25,
                skirt_w,
                skirt_w,
                skirt_h,
                material=op.get("material", "default"),
                role=op.get("role", "tower"),
            )
            sv = skirt_spec["vertices"]
            sf = skirt_spec["faces"]
            offset = len(verts)
            verts.extend(sv)
            faces.extend(tuple(idx + offset for idx in face) for face in sf)

            buttress_w = max(0.34, radius * 0.30)
            buttress_h = max(0.85, height * 0.30)
            buttress_r = radius * 0.90
            buttress_offsets = (
                (buttress_r, 0.0, buttress_w * 0.6, buttress_h * 0.96),
                (-buttress_r, 0.0, buttress_w * 0.6, buttress_h * 0.96),
                (0.0, buttress_r, buttress_w * 0.72, buttress_h),
                (0.0, -buttress_r, buttress_w * 0.72, buttress_h),
                (buttress_r * 0.72, buttress_r * 0.72, buttress_w * 0.45, buttress_h * 0.58),
                (-buttress_r * 0.72, buttress_r * 0.72, buttress_w * 0.45, buttress_h * 0.58),
                (buttress_r * 0.72, -buttress_r * 0.72, buttress_w * 0.45, buttress_h * 0.58),
                (-buttress_r * 0.72, -buttress_r * 0.72, buttress_w * 0.45, buttress_h * 0.58),
            )
            for dx, dy, bw_scale, bh_scale in buttress_offsets:
                buttress_spec = _wall_solid_box(
                    cx + dx - bw_scale * 0.5,
                    cy + dy - bw_scale * 0.5,
                    cz + skirt_h * 0.1,
                    bw_scale,
                    bw_scale,
                    bh_scale,
                    material=op.get("material", "default"),
                    role=op.get("role", "tower"),
                )
                bv = buttress_spec["vertices"]
                bf = buttress_spec["faces"]
                offset = len(verts)
                verts.extend(bv)
                faces.extend(tuple(idx + offset for idx in face) for face in bf)

            entry_depth = max(0.9, radius * 0.68)
            entry_width = max(1.2, radius * 1.15)
            entry_height = max(2.0, height * 0.58)
            entry_spec = _wall_solid_box(
                cx - entry_width * 0.5,
                cy - radius - entry_depth * 0.14,
                cz + skirt_h * 0.12,
                entry_width,
                entry_depth,
                entry_height,
                material=op.get("material", "default"),
                role=op.get("role", "tower_entry"),
            )
            ev = entry_spec["vertices"]
            ef = entry_spec["faces"]
            offset = len(verts)
            verts.extend(ev)
            faces.extend(tuple(idx + offset for idx in face) for face in ef)

            stair_spec = _wall_solid_box(
                cx + radius * 0.92 - entry_width * 0.45,
                cy - entry_depth * 0.24,
                cz + skirt_h * 0.12,
                entry_width * 1.02,
                entry_depth * 1.08,
                max(entry_height * 0.98, height * 0.62),
                material=op.get("material", "default"),
                role=op.get("role", "tower_stair_turret"),
            )
            sv = stair_spec["vertices"]
            sf = stair_spec["faces"]
            offset = len(verts)
            verts.extend(sv)
            faces.extend(tuple(idx + offset for idx in face) for face in sf)

            rear_spec = _wall_solid_box(
                cx - radius * 1.30,
                cy + radius * 0.22 - entry_depth * 0.18,
                cz + skirt_h * 0.12,
                max(radius * 0.72, entry_width * 0.82),
                max(radius * 0.64, entry_depth * 0.90),
                max(height * 0.36, entry_height * 0.68),
                material=op.get("material", "default"),
                role=op.get("role", "tower_buttress"),
            )
            rv = rear_spec["vertices"]
            rf = rear_spec["faces"]
            offset = len(verts)
            verts.extend(rv)
            faces.extend(tuple(idx + offset for idx in face) for face in rf)

            flank_spec = _wall_solid_box(
                cx - radius * 0.18,
                cy + radius * 1.02,
                cz + skirt_h * 0.10,
                max(radius * 0.48, entry_width * 0.42),
                max(radius * 0.58, entry_depth * 0.56),
                max(height * 0.42, entry_height * 0.60),
                material=op.get("material", "default"),
                role=op.get("role", "tower_buttress"),
            )
            fv = flank_spec["vertices"]
            ff = flank_spec["faces"]
            offset = len(verts)
            verts.extend(fv)
            faces.extend(tuple(idx + offset for idx in face) for face in ff)

            merlon_count = segments
            merlon_w = max(0.22, radius * 0.18)
            merlon_d = max(0.22, radius * 0.18)
            merlon_h = max(0.55, crown_height * 0.55)
            merlon_base_z = cz + height - merlon_h
            merlon_ring = radius * 1.08
            for i in range(merlon_count):
                if i % 2 == 1:
                    continue
                angle = 2.0 * math.pi * i / merlon_count
                mx = cx + math.cos(angle) * merlon_ring
                my = cy + math.sin(angle) * merlon_ring
                merlon_spec = _wall_solid_box(
                    mx - merlon_w / 2.0,
                    my - merlon_d / 2.0,
                    merlon_base_z,
                    merlon_w,
                    merlon_d,
                    merlon_h,
                    material=op.get("material", "default"),
                    role=op.get("role", "tower"),
                )
                mv = merlon_spec["vertices"]
                mf = merlon_spec["faces"]
                offset = len(verts)
                verts.extend(mv)
                faces.extend(tuple(idx + offset for idx in face) for face in mf)

            result.append({
                "type": "tower",
                "vertices": verts,
                "faces": faces,
                "vertex_count": len(verts),
                "face_count": len(faces),
                "material": op.get("material", "default"),
                "role": op.get("role", "unknown"),
                "segments": segments,
                "taper": taper,
            })

        elif op_type == "mesh_spec":
            # Full vertex/face data from building_quality generators.
            # Already positioned in world space by _generate_detail_operations.
            mesh_verts = op.get("vertices", [])
            mesh_faces = op.get("faces", [])
            if mesh_verts and mesh_faces:
                result.append({
                    "type": "mesh_spec",
                    "vertices": mesh_verts,
                    "faces": mesh_faces,
                    "vertex_count": len(mesh_verts),
                    "face_count": len(mesh_faces),
                    "material": op.get("material", "default"),
                    "role": op.get("role", "detail"),
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
    open_w = max(0.2, float(open_size[0]))      # opening width
    open_h = max(0.2, float(open_size[1]))      # opening height

    wall_axis_width = wall_sx if wall_index < 2 else wall_sy
    wall_axis_height = wall_sz
    open_w = min(open_w, max(0.2, wall_axis_width - 0.1))
    open_h = min(open_h, max(0.2, wall_axis_height - 0.1))

    role = opening_op.get("role", "opening")
    style = opening_op.get("style", "square")

    # Compute the recess depth from wall THICKNESS (min dimension), not length
    recess_depth = max(0.05, min(wall_sx, wall_sy))

    # Determine cutout box position based on wall orientation
    # wall_index 0 = front (Y=0 face), 1 = back (Y=depth face),
    # 2 = left (X=0 face), 3 = right (X=width face)
    if wall_index == 0:
        # Front wall: extends along X, thin in Y
        cx = wall_px + open_offset
        cy = wall_py - recess_depth  # consistent with other walls
        cz = wall_pz + open_z
        csx = open_w
        csy = recess_depth
        csz = open_h
    elif wall_index == 1:
        # Back wall: extends along X, thin in Y (anchored to far Y edge)
        cx = wall_px + open_offset
        cy = wall_py + wall_sy - recess_depth  # start inside wall, extend outward
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
    opening_marker_count = sum(
        1 for m in mesh_specs
        if m.get("type") == "opening" and not m.get("is_cutout")
    )
    geometry_issues: list[str] = []
    if opening_marker_count > 0:
        geometry_issues.append("opening fallback markers present")
    if total_verts <= 0 or total_faces <= 0:
        geometry_issues.append("mesh spec produced no geometry")
    return {
        "name": name,
        "style": spec.style,
        "floors": spec.floors,
        "footprint": list(spec.footprint),
        "vertex_count": total_verts,
        "face_count": total_faces,
        "material_count": len(materials),
        "opening_count": opening_count,
        "opening_marker_count": opening_marker_count,
        "geometry_quality": "complete" if not geometry_issues else "partial",
        "geometry_issues": geometry_issues,
    }


def _summarize_live_building_quality(
    *,
    expected_openings: int,
    door_count: int,
    window_count: int,
    wall_segment_count: int,
    foundation_piece_count: int,
    roof_created: bool,
    component_count: int,
) -> dict[str, Any]:
    """Summarize whether a generated building is structurally complete."""
    issues: list[str] = []
    if wall_segment_count <= 0:
        issues.append("no wall segments were created")
    if foundation_piece_count <= 0:
        issues.append("foundation fitment produced no pieces")
    if not roof_created:
        issues.append("roof geometry failed to generate")
    if component_count <= 0:
        issues.append("no building components were generated")
    if expected_openings > 0 and (door_count + window_count) != expected_openings:
        issues.append(
            f"opening coverage mismatch: expected {expected_openings}, "
            f"generated {door_count + window_count}"
        )
    return {
        "geometry_quality": "complete" if not issues else "partial",
        "geometry_issues": issues,
    }


def _build_castle_result(
    name: str, spec: BuildingSpec, procedural_mesh_count: int = 0,
) -> dict:
    """Build handler return dict for a castle from its spec."""
    roles = [op.get("role") for op in spec.operations]
    component_count = len(set(roles))
    opening_count = sum(1 for op in spec.operations if op.get("type") == "opening")
    geometry_issues: list[str] = []
    if component_count <= 0:
        geometry_issues.append("no castle components were generated")
    if opening_count <= 0:
        geometry_issues.append("castle has no openings")
    return {
        "name": name,
        "component_count": component_count,
        "roles": list(set(roles)),
        "procedural_mesh_count": procedural_mesh_count,
        "opening_count": opening_count,
        "geometry_quality": "complete" if not geometry_issues else "partial",
        "geometry_issues": geometry_issues,
    }


def _summarize_shell_merge_quality(
    *,
    source_count: int,
    vertex_count: int,
    face_count: int,
    removed_source_count: int,
    cleanup_sources: bool,
    boundary_edge_count: int = 0,
    non_manifold_edge_count: int = 0,
    loose_vertex_count: int = 0,
) -> dict[str, Any]:
    """Summarize whether a structural shell merge produced clean output."""
    issues: list[str] = []
    if source_count <= 0:
        issues.append("no structural shell pieces were available to merge")
    if vertex_count <= 0 or face_count <= 0:
        issues.append("shell merge produced no geometry")
    if cleanup_sources and removed_source_count < source_count:
        issues.append(
            f"shell cleanup removed {removed_source_count}/{source_count} source pieces"
        )
    if boundary_edge_count > 0:
        issues.append(f"{boundary_edge_count} boundary edges remain")
    if non_manifold_edge_count > 0:
        issues.append(f"{non_manifold_edge_count} non-manifold edges remain")
    if loose_vertex_count > 0:
        issues.append(f"{loose_vertex_count} loose vertices remain")
    return {
        "geometry_quality": "complete" if not issues else "partial",
        "geometry_issues": issues,
        "watertight": boundary_edge_count == 0 and non_manifold_edge_count == 0 and loose_vertex_count == 0,
        "boundary_edge_count": boundary_edge_count,
        "non_manifold_edge_count": non_manifold_edge_count,
        "loose_vertex_count": loose_vertex_count,
    }


def _summarize_mesh_topology(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
) -> dict[str, Any]:
    """Summarize watertightness and topology cleanliness from raw mesh data."""
    used_vertices: set[int] = set()
    edge_face_count: dict[tuple[int, int], int] = {}
    degenerate_faces = 0

    for face in faces:
        if len(face) < 3:
            degenerate_faces += 1
            continue
        face_indices = tuple(int(i) for i in face)
        if len(set(face_indices)) < 3:
            degenerate_faces += 1
        for idx in face_indices:
            if 0 <= idx < len(vertices):
                used_vertices.add(idx)
        for i, start in enumerate(face_indices):
            end = face_indices[(i + 1) % len(face_indices)]
            edge = (start, end) if start < end else (end, start)
            edge_face_count[edge] = edge_face_count.get(edge, 0) + 1

    boundary_edge_count = sum(1 for count in edge_face_count.values() if count == 1)
    non_manifold_edge_count = sum(1 for count in edge_face_count.values() if count != 2)
    loose_vertex_count = max(0, len(vertices) - len(used_vertices))

    issues: list[str] = []
    if boundary_edge_count > 0:
        issues.append(f"{boundary_edge_count} boundary edges remain")
    if non_manifold_edge_count > 0:
        issues.append(f"{non_manifold_edge_count} non-manifold edges remain")
    if loose_vertex_count > 0:
        issues.append(f"{loose_vertex_count} loose vertices remain")
    if degenerate_faces > 0:
        issues.append(f"{degenerate_faces} degenerate faces remain")
    return {
        "watertight": not issues,
        "boundary_edge_count": boundary_edge_count,
        "non_manifold_edge_count": non_manifold_edge_count,
        "loose_vertex_count": loose_vertex_count,
        "degenerate_face_count": degenerate_faces,
        "geometry_quality": "complete" if not issues else "partial",
        "geometry_issues": issues,
    }


def _repair_bmesh_topology(
    bm: bmesh.types.BMesh,
    *,
    merge_distance: float = 0.0001,
    max_hole_sides: int = 8,
) -> dict[str, Any]:
    """Apply the mesh repair sequence used for game-ready cleanup."""
    report: dict[str, Any] = {}

    loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
    if loose_verts:
        bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
    report["removed_loose_verts"] = len(loose_verts)

    loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
    if loose_edges:
        bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
    report["removed_loose_edges"] = len(loose_edges)

    try:
        dissolved = bmesh.ops.dissolve_degenerate(
            bm,
            dist=merge_distance,
            edges=bm.edges[:],
        )
        report["dissolved_degenerate"] = len(dissolved.get("region", []))
    except (RuntimeError, TypeError, ValueError) as exc:
        report["dissolved_degenerate"] = 0
        report["dissolve_error"] = str(exc)

    try:
        merged = bmesh.ops.remove_doubles(
            bm,
            verts=bm.verts[:],
            dist=merge_distance,
        )
        report["merged_vertices"] = len(merged.get("targetmap", {}))
    except (RuntimeError, TypeError, ValueError) as exc:
        report["merged_vertices"] = 0
        report["merge_error"] = str(exc)

    try:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        report["normals_recalculated"] = True
    except (RuntimeError, TypeError, ValueError) as exc:
        report["normals_recalculated"] = False
        report["normal_error"] = str(exc)

    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if boundary_edges:
        try:
            filled = bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=max_hole_sides)
            report["holes_filled"] = len(filled.get("faces", []))
        except (RuntimeError, TypeError, ValueError) as exc:
            report["holes_filled"] = 0
            report["holes_fill_error"] = str(exc)
    else:
        report["holes_filled"] = 0

    return report


def _estimate_voxel_remesh_size(
    dimensions: tuple[float, float, float],
    target_face_count: int,
) -> float:
    """Estimate a voxel remesh size from object dimensions and target density."""
    max_dim = max(float(dimensions[0]), float(dimensions[1]), float(dimensions[2]), 0.1)
    target_polys = max(int(target_face_count), 1)
    voxel_size = max_dim / max(math.sqrt(target_polys / 6.0), 1.0)
    return max(voxel_size, 0.01)


def _apply_voxel_remesh_modifier(
    obj: Any,
    *,
    voxel_size: float,
    adaptivity: float = 0.0,
) -> dict[str, Any]:
    """Apply Blender's voxel remesh modifier to a mesh object."""
    if obj is None or getattr(obj, "type", "") != "MESH" or getattr(obj, "data", None) is None:
        return {
            "applied": False,
            "issues": ["mesh object unavailable for voxel remesh"],
        }

    before_vertex_count = len(obj.data.vertices)
    before_face_count = len(obj.data.polygons)
    mod = obj.modifiers.new(name="VB_VoxelRemesh", type="REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel_size
    if hasattr(mod, "adaptivity"):
        mod.adaptivity = adaptivity

    ctx = get_3d_context_override()
    if ctx is None:
        try:
            obj.modifiers.remove(mod)
        except (RuntimeError, ReferenceError, TypeError):
            pass
        return {
            "applied": False,
            "voxel_size": voxel_size,
            "adaptivity": adaptivity,
            "before_vertex_count": before_vertex_count,
            "before_face_count": before_face_count,
            "issues": ["no 3D viewport available for voxel remesh"],
        }

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    applied = False
    issues: list[str] = []
    try:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.modifier_apply(modifier=mod.name)
        applied = True
    except (RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        issues.append(str(exc))
    finally:
        if not applied:
            try:
                obj.modifiers.remove(mod)
            except (RuntimeError, ReferenceError, TypeError):
                pass

    return {
        "applied": applied,
        "voxel_size": voxel_size,
        "adaptivity": adaptivity,
        "before_vertex_count": before_vertex_count,
        "before_face_count": before_face_count,
        "after_vertex_count": len(obj.data.vertices) if applied else before_vertex_count,
        "after_face_count": len(obj.data.polygons) if applied else before_face_count,
        "issues": issues,
    }


def _apply_post_merge_remesh_fallback(
    obj: Any,
    *,
    merge_distance: float,
    target_face_count: int,
    label: str,
    adaptivity: float = 0.0,
) -> dict[str, Any]:
    """Apply a voxel remesh fallback and re-run mesh repair/topology checks."""
    if obj is None or getattr(obj, "type", "") != "MESH" or getattr(obj, "data", None) is None:
        return {
            "attempted": False,
            "applied": False,
            "watertight": False,
            "geometry_quality": "partial",
            "geometry_issues": ["mesh object unavailable for remesh fallback"],
            "remesh_issues": ["mesh object unavailable for remesh fallback"],
        }

    voxel_size = _estimate_voxel_remesh_size(
        tuple(float(v) for v in getattr(obj, "dimensions", (0.0, 0.0, 0.0))),
        target_face_count,
    )
    remesh_result = _apply_voxel_remesh_modifier(
        obj,
        voxel_size=voxel_size,
        adaptivity=adaptivity,
    )
    if not remesh_result["applied"]:
        return {
            "attempted": True,
            "applied": False,
            "voxel_size": voxel_size,
            "adaptivity": adaptivity,
            "before_vertex_count": int(remesh_result.get("before_vertex_count", 0)),
            "before_face_count": int(remesh_result.get("before_face_count", 0)),
            "after_vertex_count": int(remesh_result.get("after_vertex_count", 0)),
            "after_face_count": int(remesh_result.get("after_face_count", 0)),
            "watertight": False,
            "boundary_edge_count": 0,
            "non_manifold_edge_count": 0,
            "loose_vertex_count": 0,
            "degenerate_face_count": 0,
            "removed_loose_verts": 0,
            "removed_loose_edges": 0,
            "dissolved_degenerate": 0,
            "merged_vertices": 0,
            "holes_filled": 0,
            "geometry_quality": "partial",
            "geometry_issues": [f"{label}: " + "; ".join(remesh_result.get("issues", []))],
            "remesh_issues": list(remesh_result.get("issues", [])),
        }

    repaired = _weld_mesh_object(obj, merge_distance=merge_distance, remesh_fallback=False)
    return {
        "attempted": True,
        "applied": True,
        "voxel_size": voxel_size,
        "adaptivity": adaptivity,
        "before_vertex_count": int(remesh_result["before_vertex_count"]),
        "before_face_count": int(remesh_result["before_face_count"]),
        "after_vertex_count": int(remesh_result["after_vertex_count"]),
        "after_face_count": int(remesh_result["after_face_count"]),
        "watertight": bool(repaired["watertight"]),
        "boundary_edge_count": int(repaired["boundary_edge_count"]),
        "non_manifold_edge_count": int(repaired["non_manifold_edge_count"]),
        "loose_vertex_count": int(repaired["loose_vertex_count"]),
        "degenerate_face_count": int(repaired["degenerate_face_count"]),
        "removed_loose_verts": int(repaired.get("removed_loose_verts", 0)),
        "removed_loose_edges": int(repaired.get("removed_loose_edges", 0)),
        "dissolved_degenerate": int(repaired.get("dissolved_degenerate", 0)),
        "merged_vertices": int(repaired.get("merged_vertices", 0)),
        "holes_filled": int(repaired.get("holes_filled", 0)),
        "geometry_quality": repaired["geometry_quality"],
        "geometry_issues": list(repaired["geometry_issues"]),
        "remesh_issues": list(remesh_result.get("issues", [])),
    }


def _merge_structural_shell_objects(
    name: str,
    shell_objects: list[Any],
    parent: Any,
    *,
    cleanup_sources: bool = True,
    merge_distance: float = 0.0001,
    remesh_fallback: bool = True,
) -> dict[str, Any]:
    """Merge structural shell objects into a single welded shell mesh."""
    merged_sources = [
        obj for obj in shell_objects
        if obj is not None and getattr(obj, "type", "") == "MESH" and getattr(obj, "data", None) is not None
    ]
    if not merged_sources:
        return {
            "created": 0,
            "source_count": 0,
            "removed_source_count": 0,
            "object_name": None,
            "vertex_count": 0,
            "face_count": 0,
            "merge_distance": merge_distance,
            "remesh_attempted": False,
            "remesh_applied": False,
            "remesh_voxel_size": 0.0,
            "remesh_adaptivity": 0.0,
            "remesh_before_vertex_count": 0,
            "remesh_before_face_count": 0,
            "remesh_after_vertex_count": 0,
            "remesh_after_face_count": 0,
            "remesh_issues": ["no structural shell pieces were available to merge"],
            "geometry_quality": "partial",
            "geometry_issues": ["no structural shell pieces were available to merge"],
        }

    merged_mesh = bpy.data.meshes.new(name)
    merged_bm = bmesh.new()
    merged_materials: list[Any] = []
    material_lookup: dict[str, int] = {}
    source_count = 0
    removed_source_count = 0

    for obj in merged_sources:
        part_bm = bmesh.new()
        try:
            part_bm.from_mesh(obj.data)
            if not part_bm.verts:
                continue
            source_count += 1
            part_bm.verts.ensure_lookup_table()
            part_bm.faces.ensure_lookup_table()
            bmesh.ops.transform(part_bm, matrix=obj.matrix_world, verts=part_bm.verts[:])

            slot_map: dict[int, int] = {}
            for slot_index, material in enumerate(getattr(obj.data, "materials", []) or []):
                if material is None:
                    continue
                material_key = getattr(material, "name", f"material_{id(material)}")
                if material_key not in material_lookup:
                    material_lookup[material_key] = len(merged_materials)
                    merged_materials.append(material)
                slot_map[slot_index] = material_lookup[material_key]

            vert_map: dict[Any, Any] = {}
            for vert in part_bm.verts:
                vert_map[vert] = merged_bm.verts.new(vert.co)
            for face in part_bm.faces:
                try:
                    new_face = merged_bm.faces.new([vert_map[v] for v in face.verts])
                except ValueError:
                    continue
                new_face.smooth = face.smooth
                if face.material_index in slot_map:
                    new_face.material_index = slot_map[face.material_index]
        finally:
            part_bm.free()

    if not merged_bm.verts or not merged_bm.faces:
        merged_bm.free()
        return {
            "created": 0,
            "source_count": source_count,
            "removed_source_count": 0,
            "object_name": None,
            "vertex_count": 0,
            "face_count": 0,
            "merge_distance": merge_distance,
            "remesh_attempted": False,
            "remesh_applied": False,
            "remesh_voxel_size": 0.0,
            "remesh_adaptivity": 0.0,
            "remesh_before_vertex_count": 0,
            "remesh_before_face_count": 0,
            "remesh_after_vertex_count": 0,
            "remesh_after_face_count": 0,
            "remesh_issues": ["shell merge produced no geometry"],
            "geometry_quality": "partial",
            "geometry_issues": ["shell merge produced no geometry"],
        }

    repair_report = _repair_bmesh_topology(
        merged_bm,
        merge_distance=merge_distance,
        max_hole_sides=8,
    )
    if repair_report.get("holes_fill_error"):
        logger.debug("Shell holes_fill failed for %s: %s", name, repair_report["holes_fill_error"])
    if repair_report.get("merge_error"):
        logger.debug("Shell remove_doubles failed for %s: %s", name, repair_report["merge_error"])
    if repair_report.get("normal_error"):
        logger.debug("Shell normal recalculation failed for %s: %s", name, repair_report["normal_error"])

    merged_bm.verts.ensure_lookup_table()
    merged_bm.faces.ensure_lookup_table()
    topology_result = _summarize_mesh_topology(
        [tuple(v.co) for v in merged_bm.verts],
        [tuple(v.index for v in face.verts) for face in merged_bm.faces],
    )

    for material in merged_materials:
        merged_mesh.materials.append(material)
    merged_bm.to_mesh(merged_mesh)
    merged_bm.free()

    shell_obj = bpy.data.objects.new(name, merged_mesh)
    bpy.context.collection.objects.link(shell_obj)
    shell_obj.parent = parent
    shell_obj["vb_editable_role"] = "building_shell"
    shell_obj["vb_shell_source_count"] = source_count
    shell_obj["vb_shell_merge_distance"] = merge_distance
    for poly in shell_obj.data.polygons:
        poly.use_smooth = True

    remesh_result = {
        "attempted": False,
        "applied": False,
        "voxel_size": 0.0,
        "adaptivity": 0.0,
        "before_vertex_count": len(shell_obj.data.vertices),
        "before_face_count": len(shell_obj.data.polygons),
        "after_vertex_count": len(shell_obj.data.vertices),
        "after_face_count": len(shell_obj.data.polygons),
        "remesh_issues": [],
    }

    if remesh_fallback and not topology_result["watertight"]:
        remesh_result = _apply_post_merge_remesh_fallback(
            shell_obj,
            merge_distance=merge_distance,
            target_face_count=max(len(shell_obj.data.polygons), 1200),
            label=name,
        )
        if remesh_result["applied"]:
            topology_result = remesh_result
            repair_report = remesh_result

    cleanup_applied = bool(cleanup_sources and topology_result["watertight"])
    if cleanup_sources and not cleanup_applied:
        logger.warning(
            "Shell cleanup deferred for %s because merged topology is not watertight",
            name,
        )

    if cleanup_applied:
        for obj in merged_sources:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_source_count += 1
            except (RuntimeError, ReferenceError, TypeError) as exc:
                logger.debug("Failed to remove shell source %s: %s", getattr(obj, "name", "<unnamed>"), exc)

    quality = _summarize_shell_merge_quality(
        source_count=source_count,
        vertex_count=len(shell_obj.data.vertices),
        face_count=len(shell_obj.data.polygons),
        removed_source_count=removed_source_count,
        cleanup_sources=cleanup_applied,
        boundary_edge_count=int(topology_result["boundary_edge_count"]),
        non_manifold_edge_count=int(topology_result["non_manifold_edge_count"]),
        loose_vertex_count=int(topology_result["loose_vertex_count"]),
    )
    return {
        "created": 1,
        "source_count": source_count,
        "removed_source_count": removed_source_count,
        "object_name": shell_obj.name,
        "vertex_count": len(shell_obj.data.vertices),
        "face_count": len(shell_obj.data.polygons),
        "merge_distance": merge_distance,
        "cleanup_requested": bool(cleanup_sources),
        "cleanup_applied": cleanup_applied,
        "cleanup_deferred": bool(cleanup_sources and not cleanup_applied),
        "remesh_attempted": bool(remesh_result["attempted"]),
        "remesh_applied": bool(remesh_result["applied"]),
        "remesh_voxel_size": float(remesh_result["voxel_size"]),
        "remesh_adaptivity": float(remesh_result["adaptivity"]),
        "remesh_before_vertex_count": int(remesh_result["before_vertex_count"]),
        "remesh_before_face_count": int(remesh_result["before_face_count"]),
        "remesh_after_vertex_count": int(remesh_result["after_vertex_count"]),
        "remesh_after_face_count": int(remesh_result["after_face_count"]),
        "remesh_issues": list(remesh_result["remesh_issues"]),
        "watertight": bool(topology_result["watertight"]),
        "boundary_edge_count": int(topology_result["boundary_edge_count"]),
        "non_manifold_edge_count": int(topology_result["non_manifold_edge_count"]),
        "loose_vertex_count": int(topology_result["loose_vertex_count"]),
        "degenerate_face_count": int(topology_result["degenerate_face_count"]),
        "holes_filled": int(repair_report.get("holes_filled", 0)),
        "removed_loose_verts": int(repair_report.get("removed_loose_verts", 0)),
        "removed_loose_edges": int(repair_report.get("removed_loose_edges", 0)),
        "merged_vertices": int(repair_report.get("merged_vertices", 0)),
        **quality,
    }


def _weld_mesh_object(
    obj: Any,
    *,
    merge_distance: float = 0.0001,
    remesh_fallback: bool = True,
    remesh_target_face_count: int | None = None,
) -> dict[str, Any]:
    """Weld duplicate vertices and recalculate normals on a mesh object."""
    if obj is None or getattr(obj, "type", "") != "MESH" or getattr(obj, "data", None) is None:
        return {
            "vertex_count": 0,
            "face_count": 0,
            "geometry_quality": "partial",
            "geometry_issues": ["mesh object unavailable for welding"],
        }

    repair_report: dict[str, Any] = {}
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        repair_report = _repair_bmesh_topology(
            bm,
            merge_distance=merge_distance,
            max_hole_sides=8,
        )
        if repair_report.get("holes_fill_error"):
            logger.debug("Mesh holes_fill failed for %s: %s", getattr(obj, "name", "<unnamed>"), repair_report["holes_fill_error"])
        if repair_report.get("merge_error"):
            logger.debug("Mesh remove_doubles failed for %s: %s", getattr(obj, "name", "<unnamed>"), repair_report["merge_error"])
        if repair_report.get("normal_error"):
            logger.debug("Mesh normal recalculation failed for %s: %s", getattr(obj, "name", "<unnamed>"), repair_report["normal_error"])
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    topology_result = _summarize_mesh_topology(
        [tuple(v.co) for v in obj.data.vertices],
        [tuple(poly.vertices) for poly in obj.data.polygons],
    )
    remesh_result = {
        "attempted": False,
        "applied": False,
        "voxel_size": 0.0,
        "adaptivity": 0.0,
        "before_vertex_count": len(obj.data.vertices),
        "before_face_count": len(obj.data.polygons),
        "after_vertex_count": len(obj.data.vertices),
        "after_face_count": len(obj.data.polygons),
        "remesh_issues": [],
    }
    if remesh_fallback and not topology_result["watertight"]:
        remesh_result = _apply_post_merge_remesh_fallback(
            obj,
            merge_distance=merge_distance,
            target_face_count=remesh_target_face_count or max(len(obj.data.polygons), 1200),
            label=getattr(obj, "name", "<unnamed>"),
        )
        if remesh_result["applied"]:
            topology_result = remesh_result
            repair_report = remesh_result
    return {
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
        "remesh_attempted": bool(remesh_result["attempted"]),
        "remesh_applied": bool(remesh_result["applied"]),
        "remesh_voxel_size": float(remesh_result["voxel_size"]),
        "remesh_adaptivity": float(remesh_result["adaptivity"]),
        "remesh_before_vertex_count": int(remesh_result["before_vertex_count"]),
        "remesh_before_face_count": int(remesh_result["before_face_count"]),
        "remesh_after_vertex_count": int(remesh_result["after_vertex_count"]),
        "remesh_after_face_count": int(remesh_result["after_face_count"]),
        "remesh_issues": list(remesh_result["remesh_issues"]),
        "watertight": bool(topology_result["watertight"]),
        "boundary_edge_count": int(topology_result["boundary_edge_count"]),
        "non_manifold_edge_count": int(topology_result["non_manifold_edge_count"]),
        "loose_vertex_count": int(topology_result["loose_vertex_count"]),
        "degenerate_face_count": int(topology_result["degenerate_face_count"]),
        "geometry_quality": topology_result["geometry_quality"],
        "geometry_issues": topology_result["geometry_issues"],
        "holes_filled": int(repair_report.get("holes_filled", 0)),
        "removed_loose_verts": int(repair_report.get("removed_loose_verts", 0)),
        "removed_loose_edges": int(repair_report.get("removed_loose_edges", 0)),
        "merged_vertices": int(repair_report.get("merged_vertices", 0)),
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


def _terrain_type_for_location(location_type: str) -> str:
    """Map a location archetype to a terrain preset."""
    return {
        "village": "plains",
        "fortress": "hills",
        "dungeon_entrance": "mountains",
        "camp": "plains",
        "traveler_camp": "plains",
        "merchant_camp": "plains",
        "fishing_village": "plains",
        "mining_town": "mountains",
        "port_city": "plains",
        "monastery": "hills",
        "necropolis": "hills",
        "military_outpost": "hills",
        "crossroads_inn": "plains",
        "bandit_hideout": "hills",
        "wizard_fortress": "mountains",
        "sorcery_school": "hills",
        "cliff_keep": "mountains",
        "river_castle": "plains",
        "ruined_town": "plains",
        "farmstead": "plains",
    }.get(location_type, "plains")


def _sample_scene_height(x: float, y: float, terrain_name: str | None) -> float:
    """Raycast against the current scene to place objects on terrain."""
    try:
        from mathutils import Vector

        depsgraph = bpy.context.evaluated_depsgraph_get()
        origin = Vector((x, y, 10000.0))
        direction = Vector((0.0, 0.0, -1.0))
        hit, location, normal, face_index, hit_obj, matrix = bpy.context.scene.ray_cast(
            depsgraph,
            origin,
            direction,
        )
        if hit and location is not None:
            if terrain_name is None or hit_obj is None or hit_obj.name == terrain_name:
                return float(location.z)
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug(
            "Scene height sampling failed at (%.3f, %.3f) for %s: %s",
            x,
            y,
            terrain_name or "<any>",
            exc,
        )
    return 0.0


def _clear_material_slots(obj: Any, *, context: str) -> bool:
    """Clear material slots on an object while logging non-fatal failures."""
    if obj is None or not hasattr(obj, "data") or not hasattr(obj.data, "materials"):
        return False
    try:
        obj.data.materials.clear()
        return True
    except (AttributeError, RuntimeError, TypeError) as exc:
        logger.debug(
            "Failed to clear materials on %s during %s: %s",
            getattr(obj, "name", "<unnamed>"),
            context,
            exc,
        )
        return False


def _create_curve_path(
    name: str,
    points: list[tuple[float, float, float]],
    width: float,
    parent: Any | None = None,
) -> Any:
    """Create a visible 3D road/path curve with beveled width."""
    curve_data = bpy.data.curves.new(name, "CURVE")
    curve_data.dimensions = "3D"
    curve_data.fill_mode = "FULL"
    curve_data.bevel_depth = max(0.03, width * 0.18)
    curve_data.bevel_resolution = 2
    curve_data.resolution_u = 12
    curve_data.use_fill_caps = True

    spline = curve_data.splines.new("POLY")
    spline.points.add(max(0, len(points) - 1))
    for i, pt in enumerate(points):
        spline.points[i].co = (pt[0], pt[1], pt[2], 1.0)

    curve_obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(curve_obj)
    if parent is not None:
        curve_obj.parent = parent
    return curve_obj


def _create_road_with_curbs(
    road_segment: dict,
    terrain_name: str | None,
    parent: Any | None,
    base_name: str,
    index: int,
) -> Any | None:
    """Create a road mesh with raised curb geometry and cobblestone PBR material.

    Uses ``_road_segment_mesh_spec_with_curbs`` to generate vertex data, then
    materialises it into a Blender mesh object with terrain height snapping
    and a procedural cobblestone material.

    Parameters
    ----------
    road_segment : dict
        Road data with ``start``, ``end``, ``width`` keys.
    terrain_name : str or None
        Name of the terrain object for height sampling.  ``None`` skips
        terrain snapping and uses mesh-spec Z values as-is.
    parent : bpy.types.Object or None
        Parent object for parenting the road mesh.
    base_name : str
        Settlement name prefix for the object name.
    index : int
        Road index for unique naming.

    Returns
    -------
    bpy.types.Object or None
        The created road object, or ``None`` on failure.
    """
    start_2d = road_segment.get("start")
    end_2d = road_segment.get("end")
    if not start_2d or not end_2d:
        return None

    sx, sy = start_2d[0], start_2d[1]
    ex, ey = end_2d[0], end_2d[1]
    width = float(road_segment.get("width", 4.0))

    # Sample terrain height at endpoints (or use 0.0)
    sz = _sample_scene_height(sx, sy, terrain_name) + 0.02 if terrain_name else 0.02
    ez = _sample_scene_height(ex, ey, terrain_name) + 0.02 if terrain_name else 0.02

    # Generate curb mesh spec
    spec = _road_segment_mesh_spec_with_curbs(
        start=(sx, sy, sz),
        end=(ex, ey, ez),
        width=width,
    )

    vertices = spec.get("vertices", [])
    faces = spec.get("faces", [])
    if not vertices or not faces:
        logger.warning(
            "Road curb spec returned empty geometry for %s road %d", base_name, index
        )
        return None

    # Snap each vertex to terrain height if terrain is available
    if terrain_name:
        snapped_verts = []
        for vx, vy, vz in vertices:
            terrain_z = _sample_scene_height(vx, vy, terrain_name)
            # Preserve the relative Z offset (curb height) above the terrain
            base_z = _sample_scene_height(
                (sx + ex) / 2.0, (sy + ey) / 2.0, terrain_name
            )
            z_offset = vz - (sz + (ez - sz) * 0.5)  # offset from road midpoint Z
            snapped_z = terrain_z + 0.02 + max(0.0, vz - min(sz, ez))
            # Simpler approach: keep the curb height offsets, adjust base to terrain
            snapped_verts.append((vx, vy, terrain_z + 0.02 + (vz - sz)))
        vertices = snapped_verts

    # Create Blender mesh
    obj_name = f"{base_name}_road_curb_{index}"
    mesh = bpy.data.meshes.new(obj_name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    road_obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(road_obj)

    if parent is not None:
        road_obj.parent = parent

    # Apply cobblestone PBR material
    try:
        mat = create_procedural_material(obj_name, "cobblestone")
        if mat is not None:
            mesh.materials.append(mat)
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.warning(
            "Failed to apply cobblestone material to %s: %s", obj_name, exc
        )

    return road_obj


def _create_intersection_patch(
    position: tuple[float, float],
    size: float,
    terrain_name: str | None,
    parent: Any | None,
    base_name: str,
    index: int,
) -> Any | None:
    """Create a flat quad mesh at a road intersection with cobblestone material.

    Parameters
    ----------
    position : tuple[float, float]
        World-space (x, y) center of the intersection.
    size : float
        Side length of the square patch (typically ``max(widths) * 1.5``).
    terrain_name : str or None
        Name of the terrain object for height sampling.
    parent : bpy.types.Object or None
        Parent object.
    base_name : str
        Settlement name prefix.
    index : int
        Intersection index for unique naming.

    Returns
    -------
    bpy.types.Object or None
        The created intersection patch, or ``None`` on failure.
    """
    px, py = position[0], position[1]
    pz = _sample_scene_height(px, py, terrain_name) + 0.03 if terrain_name else 0.03

    half = size / 2.0
    vertices = [
        (px - half, py - half, pz),
        (px + half, py - half, pz),
        (px + half, py + half, pz),
        (px - half, py + half, pz),
    ]
    faces = [(0, 1, 2, 3)]

    # Snap corners to terrain if available
    if terrain_name:
        snapped = []
        for vx, vy, vz in vertices:
            tz = _sample_scene_height(vx, vy, terrain_name) + 0.03
            snapped.append((vx, vy, tz))
        vertices = snapped

    obj_name = f"{base_name}_intersection_{index}"
    mesh = bpy.data.meshes.new(obj_name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    patch_obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(patch_obj)

    if parent is not None:
        patch_obj.parent = parent

    # Apply cobblestone PBR material
    try:
        mat = create_procedural_material(obj_name, "cobblestone")
        if mat is not None:
            mesh.materials.append(mat)
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.warning(
            "Failed to apply cobblestone material to %s: %s", obj_name, exc
        )

    return patch_obj


def _create_bridge_span(
    name: str,
    center: tuple[float, float, float],
    span: float,
    bridge_width: float,
    parent: Any,
    style: str = "stone",
) -> Any | None:
    """Create a visible bridge mesh from the bridge catalog."""
    bridge_type = "bridge_stone" if style == "stone" else "rope_bridge"
    entry = _catalog_entry_for_type(bridge_type)
    if entry is None:
        return None

    gen_func, gen_kwargs = entry
    if bridge_type == "bridge_stone":
        bridge_spec = gen_func(style="flat", span=max(4.0, span), width=max(1.8, bridge_width), **gen_kwargs)
    else:
        bridge_spec = gen_func(style="sturdy", span=max(4.0, span), width=max(1.2, bridge_width), **gen_kwargs)

    obj = mesh_from_spec(
        bridge_spec,
        name=name,
        location=center,
        rotation=(math.pi / 2.0, 0.0, 0.0),
        parent=parent,
    )
    if isinstance(obj, dict):
        return None
    obj.scale = (1.0, 1.0, max(0.6, span / 10.0))
    return obj


def _generate_location_building(
    base_name: str,
    building: dict[str, Any],
    seed: int,
    index: int,
    terrain_name: str | None,
    parent: Any,
) -> bool:
    """Materialize a location building using the strongest available generator."""
    b_type = building["type"]
    px, py = building["position"]
    rotation = building.get("rotation", 0.0)
    size_x, size_y = building.get("size", (8.0, 8.0))
    area = max(size_x, size_y)
    structure_name = f"{base_name}_{b_type}_{index}"
    preset_name: str | None = None
    site_profile: str | None = None
    preexisting_object_names = {obj.name for obj in bpy.data.objects}
    requested_width = max(5.6, size_x * 0.9)
    requested_depth = max(5.6, size_y * 0.9)
    foundation_profile = building.get("foundation_profile") if isinstance(building.get("foundation_profile"), dict) else None
    platform_elevation = float(
        building.get("platform_elevation", _sample_scene_height(px, py, terrain_name))
    ) + 0.02

    if b_type in {"castle", "fortress", "keep"}:
        preset_name = "gatehouse"
    elif b_type in {"shrine", "temple", "chapel", "monastery"}:
        preset_name = "shrine_major" if area >= 8.0 else "shrine_minor"
    elif b_type in {"blacksmith", "forge", "smelter"}:
        preset_name = "forge"
    elif b_type in {"watchtower", "guard_tower", "ruined_tower"}:
        preset_name = "ruined_fortress_tower"
    elif b_type in {"house", "cottage", "abandoned_house"}:
        preset_name = "rowhouse" if area >= 10.0 else "abandoned_house"
    elif b_type in {"tavern", "inn"}:
        preset_name = "inn"
    elif b_type == "warehouse":
        preset_name = "warehouse"
    elif b_type in {"barracks", "armory"}:
        preset_name = "barracks"
    elif b_type == "gatehouse":
        preset_name = "gatehouse"
    elif b_type in {"mausoleum", "catacomb"}:
        preset_name = "shrine_minor"

    if b_type in {"castle", "fortress", "keep", "watchtower", "guard_tower", "ruined_tower"}:
        site_profile = "fortified"
    elif b_type in {"shrine", "temple", "chapel", "monastery", "mausoleum", "catacomb"}:
        site_profile = "monastery"
    elif b_type in {"blacksmith", "forge", "smelter"}:
        site_profile = "forgeyard"
    elif b_type in {"house", "cottage", "abandoned_house", "stable"}:
        site_profile = "rural"
    elif b_type in {"tavern", "inn", "general_store", "market_stall"}:
        site_profile = "market"
    elif b_type in {"warehouse", "dock", "boat_house", "harbor_dock"}:
        site_profile = "waterfront"
    elif b_type in {"mine_entrance", "command_tent", "lookout_post", "cave_entrance"}:
        site_profile = "cliffside"
    elif b_type in {"barracks", "armory", "gatehouse"}:
        site_profile = "fortified"

    if b_type in {"castle", "fortress", "keep"}:
        build_result = handle_generate_castle({
            "name": structure_name,
            "outer_size": max(24.0, area * 2.8),
            "keep_size": max(10.0, area * 0.85),
            "tower_count": 4 if area < 40.0 else 6,
            "seed": seed + index * 17,
        })
        quality = build_result.get("result", {}).get("geometry_quality")
        if quality and quality != "complete":
            logger.warning(
                "Location castle %s generated with partial geometry",
                structure_name,
            )
    elif b_type in {
        "house", "cottage", "abandoned_house", "tavern", "inn", "warehouse",
        "market_stall", "stable", "general_store", "dock", "boat_house",
        "harbor_dock", "lighthouse", "mine_entrance", "command_tent",
        "cave_entrance", "tent", "supply_tent", "lookout_post", "barracks", "armory",
        "mausoleum", "catacomb", "gatehouse",
    }:
        params: dict[str, Any] = {
            "name": structure_name,
            "width": requested_width,
            "depth": requested_depth,
            "floors": 2 if b_type in {"tavern", "inn", "barracks", "warehouse", "general_store", "house", "cottage"} else 1,
            "style": "fortress" if b_type in {"barracks", "armory", "gatehouse", "watchtower", "guard_tower"} else ("gothic" if b_type in {"mausoleum", "catacomb"} else "medieval"),
            "seed": seed + index * 17,
            "weathering_level": 0.12 if b_type in {"abandoned_house", "ruined_tower", "catacomb", "mausoleum"} else 0.04,
            "wall_height": 4.0 if b_type not in {"tent", "campfire", "supply_tent"} else 2.4,
        }
        if preset_name:
            params["preset"] = preset_name
        if site_profile:
            params["site_profile"] = site_profile
        if foundation_profile:
            params["foundation_profile"] = foundation_profile
        build_result = handle_generate_building(params)
        quality = build_result.get("result", {}).get("geometry_quality")
        if quality and quality != "complete":
            logger.warning(
                "Location building %s generated with partial geometry",
                structure_name,
            )
    else:
        build_params: dict[str, Any] = {
            "name": structure_name,
            "width": max(5.6, size_x * 0.85),
            "depth": max(5.6, size_y * 0.85),
            "floors": 1,
            "style": "medieval",
            "seed": seed + index * 17,
            "weathering_level": 0.08,
        }
        if site_profile:
            build_params["site_profile"] = site_profile
        if foundation_profile:
            build_params["foundation_profile"] = foundation_profile
        build_result = handle_generate_building(build_params)
        quality = build_result.get("result", {}).get("geometry_quality")
        if quality and quality != "complete":
            logger.warning(
                "Location building %s generated with partial geometry",
                structure_name,
            )

    building_obj = bpy.data.objects.get(structure_name)
    if building_obj is None:
        logger.warning("Location building %s was not created", structure_name)
        return False
    root_footprint = (
        float(requested_width if b_type not in {"castle", "fortress", "keep"} else max(24.0, area * 2.8)),
        float(requested_depth if b_type not in {"castle", "fortress", "keep"} else max(24.0, area * 2.8)),
    )
    origin_x, origin_y = _structure_origin_from_center((px, py), root_footprint, float(rotation))
    building_obj.location = (origin_x, origin_y, platform_elevation)
    building_obj.rotation_euler = (0.0, 0.0, rotation)
    building_obj.parent = parent
    if foundation_profile and b_type in {"castle", "fortress", "keep"}:
        _apply_foundation_fitment(
            structure_name,
            parent=building_obj,
            footprint=root_footprint,
            wall_thickness=0.8,
            foundation_profile=foundation_profile,
        )
    generated_objects = [
        obj for obj in bpy.data.objects
        if obj.name not in preexisting_object_names and obj.name.startswith(structure_name)
    ]
    if not generated_objects:
        generated_objects = [building_obj]
    if b_type in {"castle", "fortress", "keep", "watchtower", "guard_tower", "ruined_tower", "barracks", "armory", "gatehouse"}:
        for obj in generated_objects:
            _assign_procedural_material(obj, "rough_stone_wall")
    elif b_type in {"shrine", "temple", "chapel", "monastery", "mausoleum", "catacomb"}:
        for obj in generated_objects:
            _assign_procedural_material(obj, "smooth_stone")
    elif b_type in {"house", "cottage", "abandoned_house", "tavern", "inn", "warehouse", "market_stall", "stable", "general_store", "dock", "boat_house", "harbor_dock", "lighthouse", "tent", "supply_tent"}:
        for obj in generated_objects:
            _assign_procedural_material(obj, "rough_timber")
    elif b_type in {"mine_entrance", "command_tent", "lookout_post", "cave_entrance"}:
        for obj in generated_objects:
            _assign_procedural_material(obj, "cliff_rock")
    else:
        for obj in generated_objects:
            _assign_procedural_material(obj, "rough_stone_wall")
    return True


def _generate_location_poi(
    base_name: str,
    poi: dict[str, Any],
    seed: int,
    index: int,
    terrain_name: str | None,
    parent: Any,
) -> bool:
    """Materialize a location POI using the best available prop generator."""
    poi_type = poi["type"]
    px, py = poi["position"]
    height_z = _sample_scene_height(px, py, terrain_name) + 0.02
    poi_name = f"{base_name}_poi_{poi_type}_{index}"

    generator_entry = (
        PROP_GENERATOR_MAP.get(poi_type)
        or FURNITURE_GENERATOR_MAP.get(poi_type)
        or DUNGEON_PROP_MAP.get(poi_type)
    )

    if generator_entry is None:
        fallback_type = "pillar" if poi_type == "statue" else "signpost"
        generator_entry = (
            PROP_GENERATOR_MAP.get(fallback_type)
            or FURNITURE_GENERATOR_MAP.get(fallback_type)
            or DUNGEON_PROP_MAP.get(fallback_type)
        )

    if generator_entry is None:
        return False

    gen_func, gen_kwargs = generator_entry
    spec = gen_func(**gen_kwargs)
    mesh_obj = mesh_from_spec(spec, name=poi_name, location=(px, py, height_z), parent=parent)
    return not isinstance(mesh_obj, dict)


def _create_boss_arena_cover(
    base_name: str,
    cover: dict[str, Any],
    seed: int,
    index: int,
    parent: Any,
) -> bool:
    """Materialize boss arena cover with a strong visual silhouette."""
    cover_type = cover["type"]
    px, py = cover["position"]
    radius = float(cover.get("radius", 1.0))
    cover_name = f"{base_name}_cover_{index}_{cover_type}"

    if cover_type == "pillar":
        spec = (PROP_GENERATOR_MAP.get("pillar") or DUNGEON_PROP_MAP.get("pillar"))
        if spec is None:
            return False
        gen_func, gen_kwargs = spec
        mesh_spec = gen_func(**gen_kwargs)
        obj = mesh_from_spec(mesh_spec, name=cover_name, location=(px, py, 0.0), parent=parent)
        if isinstance(obj, dict):
            return False
        obj.scale = (radius * 1.2, radius * 1.2, max(1.6, radius * 2.0))
        return True

    if cover_type == "rock":
        spec = PROP_GENERATOR_MAP.get("rock")
        if spec is None:
            return False
        gen_func, gen_kwargs = spec
        mesh_spec = gen_func(**gen_kwargs)
        obj = mesh_from_spec(mesh_spec, name=cover_name, location=(px, py, 0.0), parent=parent)
        if isinstance(obj, dict):
            return False
        obj.scale = (radius * 1.4, radius * 1.0, radius * 1.1)
        return True

    if cover_type == "wall_fragment":
        mesh_spec = generate_stone_wall(
            width=max(2.5, radius * 4.0),
            height=max(1.5, radius * 2.2),
            thickness=max(0.25, radius * 0.6),
            block_style="ashlar",
            mortar_depth=0.008,
            block_variation=0.2,
            seed=seed + index * 13,
        )
        obj = mesh_from_spec(mesh_spec, name=cover_name, location=(px, py, 0.0), parent=parent)
        return not isinstance(obj, dict)

    if cover_type == "statue":
        spec = PROP_GENERATOR_MAP.get("pillar")
        if spec is None:
            return False
        gen_func, gen_kwargs = spec
        mesh_spec = gen_func(**gen_kwargs)
        obj = mesh_from_spec(mesh_spec, name=cover_name, location=(px, py, 0.0), parent=parent)
        if isinstance(obj, dict):
            return False
        obj.scale = (radius * 1.0, radius * 1.0, max(2.0, radius * 2.5))
        return True

    return False


def _create_hazard_disc(
    base_name: str,
    hazard: dict[str, Any],
    index: int,
    parent: Any,
) -> bool:
    """Create a visible hazard marker mesh for boss arenas."""
    px, py = hazard["position"]
    radius = float(hazard.get("radius", 2.0))
    hazard_type = hazard["type"]
    mesh = bpy.data.meshes.new(f"{base_name}_hazard_{index}_{hazard_type}")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_fill=True, segments=24, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"{base_name}_hazard_{index}_{hazard_type}", mesh)
    obj.location = (px, py, 0.02)
    obj.parent = parent
    bpy.context.collection.objects.link(obj)
    return True


def _create_fog_gate(
    base_name: str,
    fog_gate: dict[str, Any],
    arena_type: str,
    parent: Any,
) -> bool:
    """Create a visible fog gate archway for the arena entry."""
    px, py = fog_gate["position"]
    width = float(fog_gate.get("width", 4.0))
    height = float(fog_gate.get("height", 3.5))
    gate_name = f"{base_name}_fog_gate"
    arch = generate_archway(
        width=width * 1.2,
        height=height * 1.1,
        depth=0.75,
        arch_style="gothic_pointed" if arena_type != "circular" else "round",
        has_keystone=True,
        seed=42,
    )
    gate_obj = mesh_from_spec(arch, name=gate_name, location=(px, py, 0.0), parent=parent)
    return not isinstance(gate_obj, dict)


def _create_volume_cube(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    parent: Any,
) -> Any:
    """Create a simple editable cube volume."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vert in bm.verts:
        vert.co.x *= size[0] / 2.0
        vert.co.y *= size[1] / 2.0
        vert.co.z *= size[2] / 2.0
        vert.co.x += center[0]
        vert.co.y += center[1]
        vert.co.z += center[2]
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.parent = parent
    bpy.context.collection.objects.link(obj)
    return obj


def _facing_to_rotation(facing: str) -> float:
    """Convert a cardinal facing string into a Z rotation."""
    return {
        "north": 0.0,
        "east": -math.pi / 2.0,
        "south": math.pi,
        "west": math.pi / 2.0,
    }.get(facing, 0.0)


def _catalog_entry_for_type(item_type: str):
    """Resolve a prop/furniture/castle generator entry for a type."""
    return (
        CASTLE_ELEMENT_MAP.get(item_type)
        or DUNGEON_PROP_MAP.get(item_type)
        or FURNITURE_GENERATOR_MAP.get(item_type)
        or PROP_GENERATOR_MAP.get(item_type)
    )


def _normalize_scale(scale: Any) -> tuple[float, float, float]:
    """Coerce a scalar or short iterable into a full XYZ scale triple."""
    if isinstance(scale, (int, float)):
        s = float(scale)
        return (s, s, s)
    try:
        values = tuple(scale)
    except TypeError:
        s = float(scale)
        return (s, s, s)
    if len(values) == 0:
        return (1.0, 1.0, 1.0)
    if len(values) == 1:
        s = float(values[0])
        return (s, s, s)
    if len(values) == 2:
        return (float(values[0]), float(values[1]), 1.0)
    return (float(values[0]), float(values[1]), float(values[2]))


def _spawn_catalog_object(
    base_name: str,
    item_type: str,
    index: int,
    location: tuple[float, float, float],
    parent: Any,
    rotation: float = 0.0,
    scale: tuple[float, float, float] | None = None,
    collection: Any | None = None,
) -> Any | None:
    """Spawn a catalog-backed mesh or a simple fallback primitive."""
    entry = _catalog_entry_for_type(item_type)
    obj_name = f"{base_name}_{item_type}_{index}"

    if entry is not None:
        gen_func, gen_kwargs = entry
        spec = gen_func(**gen_kwargs)
        obj = mesh_from_spec(
            spec,
            name=obj_name,
            location=location,
            rotation=(0.0, 0.0, rotation),
            collection=collection,
            parent=parent,
        )
        if isinstance(obj, dict):
            return None
        if scale is not None:
            obj.scale = _normalize_scale(scale)
        return obj

    fallback = _create_volume_cube(
        obj_name,
        center=location,
        size=_normalize_scale(scale or (1.0, 1.0, 1.0)),
        parent=parent,
    )
    return fallback


def _create_settlement_light(
    base_name: str,
    light_spec: dict[str, Any],
    index: int,
    parent: Any,
) -> bool:
    """Create a real Blender light from a settlement light spec."""
    light_name = f"{base_name}_light_{index}_{light_spec.get('light_type', 'point')}"
    light_kind = str(light_spec.get("light_type", "point")).lower()
    blender_type = "AREA" if light_kind == "area" else "POINT"
    light_data = bpy.data.lights.new(light_name, type=blender_type)
    light_data.color = tuple(light_spec.get("color", (1.0, 0.9, 0.7)))
    light_data.energy = float(light_spec.get("intensity", 1.0)) * 100.0
    light_data.shadow_soft_size = max(0.05, float(light_spec.get("range", 4.0)) * 0.05)
    if blender_type == "AREA":
        light_data.shape = "RECTANGLE"
        light_data.size = max(0.35, float(light_spec.get("range", 4.0)) * 0.2)
        light_data.size_y = max(0.35, float(light_spec.get("range", 4.0)) * 0.15)
    light_obj = bpy.data.objects.new(light_name, light_data)
    light_obj.location = tuple(light_spec.get("position", (0.0, 0.0, 0.0)))
    light_obj.parent = parent
    bpy.context.collection.objects.link(light_obj)
    return True


def _create_settlement_prop_cluster(
    base_name: str,
    prop: dict[str, Any],
    index: int,
    parent: Any,
) -> int:
    """Spawn visually richer clusters for settlement prop archetypes."""
    prop_type = prop["type"]
    position = prop.get("position", (0.0, 0.0, 0.0))
    px = float(position[0]) if len(position) > 0 else 0.0
    py = float(position[1]) if len(position) > 1 else 0.0
    z = float(position[2]) if len(position) > 2 else 0.0
    rotation = float(prop.get("rotation", 0.0))
    scale = _normalize_scale(prop.get("scale", (1.0, 1.0, 1.0)))
    spawned = 0

    if prop_type == "market_stall_cluster":
        offsets = [
            (-1.4, 0.0, 0.0),
            (1.4, 0.0, 0.0),
            (0.0, 1.2, 0.0),
            (0.0, -1.2, 0.0),
        ]
        for stall_idx, (ox, oy, oz) in enumerate(offsets):
            stall = _spawn_catalog_object(
                base_name,
                "market_stall",
                index * 10 + stall_idx,
                (px + ox, py + oy, z + oz),
                parent,
                rotation=rotation + (stall_idx * math.pi / 2.0),
                scale=(1.0, 1.0, 1.0),
            )
            if stall is not None:
                spawned += 1
        for detail_idx, detail_type in enumerate(("crate", "sack", "basket", "signpost")):
            detail = _spawn_catalog_object(
                base_name,
                detail_type,
                index * 10 + 50 + detail_idx,
                (px + math.cos(rotation + detail_idx) * 1.8, py + math.sin(rotation + detail_idx) * 1.8, z),
                parent,
                rotation=rotation,
                scale=(0.65, 0.65, 0.65),
            )
            if detail is not None:
                spawned += 1
        return spawned

    if prop_type == "campfire_area":
        for detail_idx, detail_type in enumerate(("campfire", "log", "log", "rock", "rock")):
            detail = _spawn_catalog_object(
                base_name,
                detail_type,
                index * 10 + detail_idx,
                (
                    px + math.cos(rotation + detail_idx * 1.3) * (0.7 + detail_idx * 0.18),
                    py + math.sin(rotation + detail_idx * 1.3) * (0.7 + detail_idx * 0.18),
                    z,
                ),
                parent,
                rotation=rotation,
                scale=(0.8, 0.8, 0.8),
            )
            if detail is not None:
                spawned += 1
        return spawned

    if prop_type in {"tent", "lean_to", "supply_tent"}:
        # Small shelter-like forms should read as temporary structures, not houses.
        shelter = _spawn_catalog_object(
            base_name,
            "market_stall",
            index,
            (px, py, z),
            parent,
            rotation=rotation,
            scale=(scale[0] * 0.9, scale[1] * 0.9, max(0.65, scale[2] * 0.7)),
        )
        return 1 if shelter is not None else 0

    if prop_type == "cage":
        for detail_idx, detail_type in enumerate(("chain", "prison_door")):
            detail = _spawn_catalog_object(
                base_name,
                detail_type,
                index * 10 + detail_idx,
                (px, py, z + detail_idx * 0.15),
                parent,
                rotation=rotation,
                scale=(scale[0], scale[1], max(0.8, scale[2])),
            )
            if detail is not None:
                spawned += 1
        return spawned

    if prop_type == "farm_plot":
        # Dark-fantasy farm plot: fenced crop rows, hay bales, and work gear.
        plot_w = max(5.0, scale[0] * 6.0)
        plot_d = max(4.0, scale[1] * 4.5)
        fence_type = "fence" if scale[0] < 1.2 else "palisade"
        fence_slots = [
            (-plot_w / 2.0, -plot_d / 2.0, 0.0, 0.0, plot_w),
            (-plot_w / 2.0, plot_d / 2.0, 0.0, 0.0, plot_w),
            (-plot_w / 2.0, 0.0, 0.0, math.pi / 2.0, plot_d),
            (plot_w / 2.0, 0.0, 0.0, math.pi / 2.0, plot_d),
        ]
        for seg_idx, (ox, oy, oz, rot, seg_len) in enumerate(fence_slots):
            fence = _spawn_catalog_object(
                base_name,
                fence_type,
                index * 20 + seg_idx,
                (px + ox, py + oy, z + oz),
                parent,
                rotation=rotation + rot,
                scale=(max(0.8, seg_len / 4.0), 1.0, 1.0),
            )
            if fence is not None:
                spawned += 1
        row_offsets = [-plot_d * 0.28, -plot_d * 0.08, 0.12, 0.32]
        for row_idx, row_y in enumerate(row_offsets):
            row = _create_volume_cube(
                f"{base_name}_farm_row_{index}_{row_idx}",
                center=(px + math.cos(rotation) * 0.0, py + row_y, z + 0.04),
                size=(plot_w * 0.72, 0.12, 0.18),
                parent=parent,
            )
            if row is not None:
                spawned += 1
        for detail_idx, detail_type in enumerate(("hay_bale", "hay_bale", "cart", "barrel")):
            detail = _spawn_catalog_object(
                base_name,
                detail_type,
                index * 20 + 50 + detail_idx,
                (
                    px + math.cos(rotation + detail_idx) * (plot_w * 0.18 + detail_idx * 0.35),
                    py + math.sin(rotation + detail_idx) * (plot_d * 0.12 + detail_idx * 0.22),
                    z,
                ),
                parent,
                rotation=rotation,
                scale=(0.8, 0.8, 0.8),
            )
            if detail is not None:
                spawned += 1
        return spawned

    return 0


def _create_curve_from_points(
    name: str,
    points: list[tuple[float, float, float]],
    width: float,
    parent: Any,
) -> Any:
    """Create a visible path curve from point samples."""
    return _create_curve_path(name, points, width=width, parent=parent)


def _create_floor_plate(
    name: str,
    bounds: dict[str, Any],
    shape: str,
    parent: Any,
) -> Any:
    """Create a simple but editable floor plate for arenas and rooms."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    if shape == "circular" and "radius" in bounds:
        bmesh.ops.create_circle(
            bm,
            cap_fill=True,
            segments=48,
            radius=float(bounds["radius"]),
        )
    else:
        min_pt = bounds.get("min", (-5.0, -5.0, 0.0))
        max_pt = bounds.get("max", (5.0, 5.0, 0.0))
        width = float(max_pt[0] - min_pt[0])
        depth = float(max_pt[1] - min_pt[1])
        bmesh.ops.create_cube(bm, size=1.0)
        for vert in bm.verts:
            vert.co.x *= width / 2.0
            vert.co.y *= depth / 2.0
            vert.co.z *= 0.08
        for vert in bm.verts:
            vert.co.x += (min_pt[0] + max_pt[0]) / 2.0
            vert.co.y += (min_pt[1] + max_pt[1]) / 2.0
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.parent = parent
    bpy.context.collection.objects.link(obj)
    return obj


def _create_floor_segments(
    base_name: str,
    width: float,
    depth: float,
    parent: Any,
    opening_center: tuple[float, float] | None = None,
    opening_size: tuple[float, float] | None = None,
    thickness: float = 0.06,
) -> int:
    """Create an editable floor made of slabs, optionally with a hole.

    The hole is built from separate surrounding slabs instead of a boolean
    so the result stays editable for downstream agents.
    """
    created = 0

    def add_segment(segment_name: str, center: tuple[float, float], size_xy: tuple[float, float]) -> None:
        nonlocal created
        sx, sy = size_xy
        if sx <= 0.0 or sy <= 0.0:
            return
        _create_volume_cube(
            f"{base_name}_{segment_name}",
            center=(center[0], center[1], thickness / 2.0),
            size=(sx, sy, thickness),
            parent=parent,
        )
        created += 1

    if opening_center is None or opening_size is None:
        add_segment("full", (width / 2.0, depth / 2.0), (width, depth))
        return created

    margin = 0.35
    hole_w = min(max(0.8, float(opening_size[0])), max(0.8, width - 2.0 * margin))
    hole_d = min(max(0.8, float(opening_size[1])), max(0.8, depth - 2.0 * margin))
    hole_x = min(max(margin + hole_w / 2.0, float(opening_center[0])), width - margin - hole_w / 2.0)
    hole_y = min(max(margin + hole_d / 2.0, float(opening_center[1])), depth - margin - hole_d / 2.0)

    left_w = hole_x - hole_w / 2.0
    right_w = width - (hole_x + hole_w / 2.0)
    front_d = hole_y - hole_d / 2.0
    back_d = depth - (hole_y + hole_d / 2.0)

    add_segment("left", (left_w / 2.0, depth / 2.0), (left_w, depth))
    add_segment("right", (hole_x + hole_w / 2.0 + right_w / 2.0, depth / 2.0), (right_w, depth))
    add_segment("front", (hole_x, front_d / 2.0), (hole_w, front_d))
    add_segment("back", (hole_x, hole_y + hole_d / 2.0 + back_d / 2.0), (hole_w, back_d))
    return created


def _create_interior_shell(
    base_name: str,
    width: float,
    depth: float,
    height: float,
    parent: Any,
    room_type: str,
    origin: tuple[float, float] = (0.0, 0.0),
    seed: int = 0,
) -> int:
    """Create a lightweight but visually readable room shell.

    The shell remains split into separate editable pieces instead of a single
    fused volume, so downstream agents can still adjust wall layout, openings,
    and proportions.
    """
    rng = random.Random(seed + 211)
    style_map = {
        "chapel": "gothic",
        "shrine_room": "gothic",
        "throne_room": "gothic",
        "great_hall": "fortress",
        "study": "medieval",
        "library": "medieval",
        "alchemy_lab": "organic",
        "wizard_lab": "organic",
        "barracks": "fortress",
        "guard_post": "fortress",
        "storage": "rustic",
        "kitchen": "rustic",
        "tavern": "medieval",
        "bedroom": "medieval",
    }
    shell_style = style_map.get(room_type, "medieval")
    if shell_style in {"fortress", "gothic"}:
        floor_material_key = "cobblestone_floor"
        wall_material_key = "rough_stone_wall"
    elif shell_style == "rustic":
        floor_material_key = "plank_floor"
        wall_material_key = "rough_timber"
    elif shell_style == "organic":
        floor_material_key = "mud"
        wall_material_key = "smooth_stone"
    else:
        floor_material_key = "plank_floor"
        wall_material_key = "rough_stone_wall"
    shell_count = 0
    origin_x, origin_y = origin

    floor = _create_floor_plate(
        f"{base_name}_Floor",
        {"min": (origin_x, origin_y, 0.0), "max": (origin_x + width, origin_y + depth, 0.0)},
        "rectangular",
        parent,
    )
    if floor is not None:
        floor["vb_room_type"] = room_type
        floor["vb_editable_role"] = "room_floor"
        _assign_procedural_material(floor, floor_material_key)
        shell_count += 1

    ceiling_thickness = 0.12 if shell_style != "fortress" else 0.18
    ceiling = _create_volume_cube(
        f"{base_name}_Ceiling",
        center=(origin_x + width / 2.0, origin_y + depth / 2.0, height - ceiling_thickness / 2.0),
        size=(width, depth, ceiling_thickness),
        parent=parent,
    )
    if ceiling is not None:
        ceiling["vb_room_type"] = room_type
        ceiling["vb_editable_role"] = "room_ceiling"
        _assign_procedural_material(ceiling, wall_material_key)
        shell_count += 1

    wall_thickness = 0.18 if shell_style not in {"fortress", "gothic"} else 0.28
    wall_height = max(height, 2.4)
    opening_width = min(max(1.0, width * 0.22), width * 0.38)
    opening_height = min(max(2.0, wall_height * 0.72), wall_height - 0.2)
    opening_center_x = origin_x + width * 0.5 + rng.uniform(-0.15, 0.15)
    opening_center_y = origin_y + wall_thickness * 0.5

    front_left_w = max(0.0, (opening_center_x - origin_x) - opening_width * 0.5)
    front_right_w = max(0.0, (origin_x + width) - (opening_center_x + opening_width * 0.5))
    if front_left_w > 0.0:
        front_left = _create_volume_cube(
            f"{base_name}_Wall_Front_L",
            center=(origin_x + front_left_w / 2.0, origin_y + wall_thickness / 2.0, wall_height / 2.0),
            size=(front_left_w, wall_thickness, wall_height),
            parent=parent,
        )
        if front_left is not None:
            front_left["vb_room_type"] = room_type
            front_left["vb_editable_role"] = "room_wall"
            _assign_procedural_material(front_left, wall_material_key)
            shell_count += 1
    if front_right_w > 0.0:
        front_right = _create_volume_cube(
            f"{base_name}_Wall_Front_R",
            center=(opening_center_x + opening_width * 0.5 + front_right_w / 2.0, origin_y + wall_thickness / 2.0, wall_height / 2.0),
            size=(front_right_w, wall_thickness, wall_height),
            parent=parent,
        )
        if front_right is not None:
            front_right["vb_room_type"] = room_type
            front_right["vb_editable_role"] = "room_wall"
            _assign_procedural_material(front_right, wall_material_key)
            shell_count += 1

    back = _create_volume_cube(
        f"{base_name}_Wall_Back",
        center=(origin_x + width / 2.0, origin_y + depth - wall_thickness / 2.0, wall_height / 2.0),
        size=(width, wall_thickness, wall_height),
        parent=parent,
    )
    left = _create_volume_cube(
        f"{base_name}_Wall_Left",
        center=(origin_x + wall_thickness / 2.0, origin_y + depth / 2.0, wall_height / 2.0),
        size=(wall_thickness, depth, wall_height),
        parent=parent,
    )
    right = _create_volume_cube(
        f"{base_name}_Wall_Right",
        center=(origin_x + width - wall_thickness / 2.0, origin_y + depth / 2.0, wall_height / 2.0),
        size=(wall_thickness, depth, wall_height),
        parent=parent,
    )
    for wall_obj in (back, left, right):
        if wall_obj is not None:
            wall_obj["vb_room_type"] = room_type
            wall_obj["vb_editable_role"] = "room_wall"
            _assign_procedural_material(wall_obj, wall_material_key)
            shell_count += 1

    door = generate_archway(
        width=opening_width,
        height=opening_height,
        depth=max(0.18, wall_thickness * 0.75),
        arch_style="gothic_pointed" if shell_style in {"gothic", "fortress"} else "round",
        has_keystone=True,
        seed=seed,
    )
    door_obj = mesh_from_spec(
        door,
        name=f"{base_name}_Doorway",
        location=(opening_center_x, origin_y, 0.0),
        parent=parent,
    )
    if not isinstance(door_obj, dict):
        door_obj["vb_room_type"] = room_type
        door_obj["vb_editable_role"] = "room_entry"
        _assign_procedural_material(door_obj, wall_material_key)
        shell_count += 1

    # Only ceremonial spaces get visible internal columns; barracks and guard
    # posts stay cleaner so they do not read like random stacked blocks.
    if shell_style in {"gothic", "fortress"} and room_type in {"great_hall", "chapel", "shrine_room", "throne_room"}:
        pillar_height = wall_height * 0.95
        for suffix, px, py in (
            ("FL", origin_x + 0.4, origin_y + 0.35),
            ("FR", origin_x + width - 0.4, origin_y + 0.35),
            ("BL", origin_x + 0.4, origin_y + depth - 0.35),
            ("BR", origin_x + width - 0.4, origin_y + depth - 0.35),
        ):
            pillar = _spawn_catalog_object(
                base_name,
                "pillar",
                800 + shell_count,
                (px, py, 0.0),
                parent,
                rotation=0.0,
                scale=(0.7, 0.7, pillar_height / 4.0),
            )
            if pillar is not None:
                pillar["vb_room_type"] = room_type
                pillar["vb_editable_role"] = "room_support"
                _assign_procedural_material(pillar, wall_material_key)
                shell_count += 1

    return shell_count


_SITE_PROFILE_ROOM_MAP: dict[str, list[str]] = {
    "fortified": ["guard_post", "great_hall", "armory", "storage"],
    "cliffside": ["guard_post", "study", "great_hall", "storage"],
    "waterfront": ["tavern", "kitchen", "storage", "bedroom"],
    "riverfront": ["tavern", "kitchen", "storage", "bedroom"],
    "monastery": ["chapel", "shrine_room", "great_hall", "study"],
    "market": ["tavern", "great_hall", "storage", "bedroom"],
    "forgeyard": ["smithy", "storage", "guard_post", "kitchen"],
    "rural": ["kitchen", "bedroom", "storage", "study"],
    "wizard_lab": ["study", "alchemy_lab", "library", "storage"],
}


def _apply_site_profile_features(
    name: str,
    profile: str,
    width: float,
    depth: float,
    wall_height: float,
    parent: Any,
    seed: int,
) -> int:
    """Add context-specific exterior geometry for more distinct silhouettes."""
    profile_key = str(profile or "").strip().lower()
    if not profile_key:
        return 0

    rng = random.Random(seed + 7919)
    feature_count = 0

    def add_generated_mesh(
        mesh_spec: dict[str, Any],
        suffix: str,
        location: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> None:
        nonlocal feature_count
        obj = mesh_from_spec(
            mesh_spec,
            name=f"{name}_{suffix}_{feature_count}",
            location=location,
            rotation=rotation,
            scale=scale,
            parent=parent,
        )
        if not isinstance(obj, dict):
            feature_count += 1

    def add_catalog_feature(
        item_type: str,
        index: int,
        location: tuple[float, float, float],
        rotation: float = 0.0,
        scale: tuple[float, float, float] | None = None,
    ) -> None:
        nonlocal feature_count
        obj = _spawn_catalog_object(
            name,
            item_type,
            index,
            location,
            parent,
            rotation=rotation,
            scale=scale,
        )
        if obj is not None:
            feature_count += 1

    if profile_key in {"fortified", "cliffside", "wizard_lab"}:
        buttress_height = max(3.0, wall_height * 0.9)
        for idx, x_pos in enumerate((0.0, max(0.0, width - 0.9))):
            buttress_spec = generate_buttress_mesh(
                height=buttress_height,
                style="flying" if profile_key == "cliffside" else "standard",
            )
            add_generated_mesh(
                buttress_spec,
                "Buttress",
                (x_pos, depth * (0.25 + 0.45 * idx), 0.0),
                rotation=(0.0, 0.0, math.pi / 2.0 if idx == 0 else -math.pi / 2.0),
            )
        add_catalog_feature(
            "archway",
            0,
            (width * 0.5, -0.35, 0.0),
            rotation=0.0,
            scale=(1.0, 1.0, max(1.0, wall_height / 3.0)),
        )

    if profile_key == "cliffside":
        # Cliffside structures need actual cliff mass, not just a stone wall.
        for idx, (x_pos, y_pos, z_pos) in enumerate((
            (-0.9, depth * 0.16, -0.05),
            (width + 0.85, depth * 0.74, -0.05),
        )):
            add_catalog_feature(
                "cliff_rock",
                40 + idx,
                (x_pos, y_pos, z_pos),
                rotation=rng.uniform(-0.22, 0.22),
                scale=(1.55 + idx * 0.18, 1.0, 1.25),
            )

    if profile_key in {"waterfront", "riverfront"}:
        bridge_spec = generate_bridge_mesh(
            span=max(width * 0.95, 6.0),
            width=max(2.0, depth * 0.22),
            style="stone_arch",
        )
        add_generated_mesh(
            bridge_spec,
            "Bridgewalk",
            (width * 0.5, -max(2.5, depth * 0.28), 0.0),
            rotation=(math.pi / 2.0, 0.0, 0.0),
        )
        add_catalog_feature(
            "fence",
            1,
            (width * 0.5, depth + 0.45, 0.0),
            rotation=0.0,
            scale=(max(width * 0.85, 4.0), 1.0, 1.0),
        )

    if profile_key in {"monastery", "market", "rural", "forgeyard"}:
        fence_style = "wooden_picket" if profile_key in {"rural", "market"} else "iron_wrought"
        fence_spec = generate_fence_mesh(
            length=max(width, depth) * 0.95,
            posts=max(4, int(max(width, depth) / 1.8)),
            style=fence_style,
        )
        add_generated_mesh(
            fence_spec,
            "FrontYard",
            (width * 0.5, -0.8, 0.0),
            rotation=(0.0, 0.0, 0.0),
        )
        add_generated_mesh(
            fence_spec,
            "RearYard",
            (width * 0.5, depth + 0.8, 0.0),
            rotation=(0.0, 0.0, 0.0),
        )
        if profile_key in {"monastery", "forgeyard"}:
            colonnade_spec = generate_column_row_mesh(
                count=max(4, int(width / 2.5)),
                spacing=max(1.4, width / max(4, int(width / 2.5))),
                style="gothic" if profile_key == "monastery" else "doric",
            )
            add_generated_mesh(
                colonnade_spec,
                "Colonnade",
                (width * 0.5, depth + 1.3, 0.0),
                rotation=(0.0, 0.0, 0.0),
            )

    if profile_key == "rural":
        add_catalog_feature(
            "crate",
            2,
            (width + 1.4, depth * 0.55, 0.0),
            rotation=rng.uniform(0.0, math.pi / 4.0),
            scale=(1.2, 0.8, 0.9),
        )
        add_catalog_feature(
            "barrel",
            3,
            (-1.1, depth * 0.45, 0.0),
            rotation=rng.uniform(0.0, math.pi / 4.0),
            scale=(1.1, 1.1, 1.1),
        )

    if profile_key == "wizard_lab":
        add_catalog_feature(
            "map_display",
            4,
            (width * 0.18, depth + 0.25, 0.0),
            rotation=0.0,
            scale=(1.2, 1.0, 1.0),
        )
        add_catalog_feature(
            "candelabra",
            5,
            (width * 0.82, depth + 0.2, 0.0),
            rotation=0.0,
            scale=(1.0, 1.0, 1.0),
        )

    return feature_count


def _create_box_mesh_object(
    name: str,
    *,
    position: tuple[float, float, float],
    size: tuple[float, float, float],
    material: str,
    role: str,
    parent: Any,
) -> Any | None:
    """Create a simple mesh box object for facade and foundation detailing."""
    spec = _wall_solid_box(
        float(position[0]),
        float(position[1]),
        float(position[2]),
        float(size[0]),
        float(size[1]),
        float(size[2]),
        material,
        role,
    )
    obj = mesh_from_spec(spec, name=name)
    if isinstance(obj, dict):
        return None
    obj.parent = parent
    obj["vb_editable_role"] = role
    _assign_procedural_material(obj, material)
    return obj


def _structure_origin_from_center(
    center: tuple[float, float],
    footprint: tuple[float, float],
    rotation: float,
) -> tuple[float, float]:
    """Convert a center anchor into the corner origin used by generated shells."""
    offset_x = footprint[0] * 0.5
    offset_y = footprint[1] * 0.5
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    rotated_x = offset_x * cos_r - offset_y * sin_r
    rotated_y = offset_x * sin_r + offset_y * cos_r
    return (center[0] - rotated_x, center[1] - rotated_y)


def _apply_modular_facade(
    base_name: str,
    *,
    parent: Any,
    width: float,
    depth: float,
    floors: int,
    style: str,
    wall_height: float,
    wall_thickness: float,
    openings: list[dict[str, Any]],
    site_profile: str,
    seed: int,
) -> dict[str, Any]:
    """Materialize only non-placeholder facade modules as editable child meshes.

    Box-based bands/pilasters/frames remain in the facade plan metadata, but are
    not emitted as separate scene meshes because they currently degrade live
    building quality into obvious placeholder blocks.
    """
    facade_plan = plan_modular_facade(
        width=width,
        depth=depth,
        floors=floors,
        style=style,
        wall_height=wall_height,
        wall_thickness=wall_thickness,
        openings=openings,
        site_profile=site_profile,
        seed=seed,
    )

    created = 0
    chimney_count = 0
    buttress_count = 0
    suppressed_box_count = 0
    shell_objects: list[Any] = []
    for index, module in enumerate(facade_plan.get("modules", [])):
        module_type = str(module.get("type", "box"))
        role = str(module.get("role", "facade_module"))
        material = str(module.get("material", "smooth_stone"))
        if module_type == "chimney":
            chimney_spec = generate_chimney(
                height=float(module.get("height", 1.6)),
                chimney_width=float(module.get("width", 0.5)),
                chimney_depth=float(module.get("depth", 0.5)),
                style="stone" if style in {"gothic", "fortress"} else "brick",
            )
            obj = mesh_from_spec(
                chimney_spec,
                name=f"{base_name}_Facade_{index}",
                location=tuple(module["position"]),
                parent=parent,
            )
            if not isinstance(obj, dict):
                obj["vb_editable_role"] = role
                _assign_procedural_material(obj, material)
                created += 1
                chimney_count += 1
                shell_objects.append(obj)
            continue
        if module_type == "buttress":
            buttress_spec = generate_buttress_mesh(
                height=float(module.get("height", wall_height)),
                style="flying" if style == "gothic" else "standard",
            )
            obj = mesh_from_spec(
                buttress_spec,
                name=f"{base_name}_Facade_{index}",
                location=tuple(module["position"]),
                parent=parent,
            )
            if not isinstance(obj, dict):
                obj["vb_editable_role"] = role
                _assign_procedural_material(obj, material)
                created += 1
                buttress_count += 1
                shell_objects.append(obj)
            continue
        if module_type == "box":
            suppressed_box_count += 1
            continue

    return {
        "module_count": created,
        "chimney_count": chimney_count,
        "buttress_count": buttress_count,
        "suppressed_box_count": suppressed_box_count,
        "plan": facade_plan,
        "shell_objects": shell_objects,
    }


def _apply_foundation_fitment(
    base_name: str,
    *,
    parent: Any,
    footprint: tuple[float, float],
    wall_thickness: float,
    foundation_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Create plinth, retaining walls, and access steps for sloped sites."""
    profile = foundation_profile or {}
    foundation_height = float(profile.get("foundation_height", 0.0))
    if foundation_height <= 0.05:
        return {
            "created": 0,
            "retaining_wall_count": 0,
            "stair_count": 0,
            "shell_objects": [],
        }

    width, depth = float(footprint[0]), float(footprint[1])
    created = 0
    retaining_count = 0
    stair_count = 0
    shell_objects: list[Any] = []
    band = max(0.18, wall_thickness * 0.8)
    plinth = _create_box_mesh_object(
        f"{base_name}_Foundation",
        position=(-band, -band, -(foundation_height + 0.08)),
        size=(width + band * 2.0, depth + band * 2.0, foundation_height + 0.12),
        material="stone_dark",
        role="foundation_plinth",
        parent=parent,
    )
    if plinth is not None:
        created += 1
        shell_objects.append(plinth)

    side_heights = profile.get("side_heights", {}) if isinstance(profile, dict) else {}
    side_specs = [
        ("front", (-band * 1.2, -band * 1.35, -foundation_height), (width + band * 2.4, band * 0.7)),
        ("back", (-band * 1.2, depth + band * 0.65, -foundation_height), (width + band * 2.4, band * 0.7)),
        ("left", (-band * 1.35, -band * 1.2, -foundation_height), (band * 0.7, depth + band * 2.4)),
        ("right", (width + band * 0.65, -band * 1.2, -foundation_height), (band * 0.7, depth + band * 2.4)),
    ]
    retaining_sides = set(profile.get("retaining_sides", [])) if isinstance(profile, dict) else set()
    for wall_name, (px, py, pz), (sx, sy) in side_specs:
        drop = float(side_heights.get(wall_name, 0.0))
        if wall_name not in retaining_sides or drop <= 0.2:
            continue
        obj = _create_box_mesh_object(
            f"{base_name}_Retaining_{wall_name}",
            position=(px, py, pz),
            size=(sx, sy, max(0.28, drop)),
            material="stone_heavy",
            role="retaining_wall",
            parent=parent,
        )
        if obj is not None:
            created += 1
            retaining_count += 1
            shell_objects.append(obj)

    stair_wall = str(profile.get("stair_wall") or "")
    stair_steps = int(profile.get("stair_steps", 0))
    if stair_wall and stair_steps > 0:
        stair_spec = generate_staircase_mesh(
            steps=max(2, stair_steps),
            width=max(1.35, min(width * 0.24, 2.4)),
            direction="straight",
        )
        if stair_wall == "front":
            stair_loc = (width * 0.5, -max(1.0, stair_steps * 0.18), -foundation_height)
            stair_rot = (math.pi / 2.0, 0.0, math.pi)
        elif stair_wall == "back":
            stair_loc = (width * 0.5, depth + max(0.4, stair_steps * 0.18), -foundation_height)
            stair_rot = (math.pi / 2.0, 0.0, 0.0)
        elif stair_wall == "left":
            stair_loc = (-max(1.0, stair_steps * 0.18), depth * 0.5, -foundation_height)
            stair_rot = (math.pi / 2.0, 0.0, -math.pi / 2.0)
        else:
            stair_loc = (width + max(0.4, stair_steps * 0.18), depth * 0.5, -foundation_height)
            stair_rot = (math.pi / 2.0, 0.0, math.pi / 2.0)
        stairs_obj = mesh_from_spec(
            stair_spec,
            name=f"{base_name}_Foundation_Stairs",
            location=stair_loc,
            rotation=stair_rot,
            parent=parent,
        )
        if not isinstance(stairs_obj, dict):
            stairs_obj["vb_editable_role"] = "foundation_stairs"
            _assign_procedural_material(stairs_obj, "stone_dark")
            created += 1
            stair_count += 1

    return {
        "created": created,
        "retaining_wall_count": retaining_count,
        "stair_count": stair_count,
        "shell_objects": shell_objects,
    }


def _create_connection_geometry(
    base_name: str,
    conn: dict[str, Any],
    index: int,
    parent: Any,
    cell_size: float,
    wall_height: float,
) -> bool:
    """Create an editable vertical connection mesh for a dungeon."""
    px, py = conn["position"]
    conn_type = str(conn.get("type", "staircase")).lower()
    from_floor = int(conn.get("from_floor", 0))
    from_z = from_floor * wall_height
    location = (px * cell_size, py * cell_size, from_z)
    name = f"{base_name}_conn_{conn_type}_{index}"

    if conn_type == "ladder":
        obj = _spawn_catalog_object(
            base_name,
            "chain",
            index,
            location,
            parent,
            rotation=0.0,
            scale=(1.0, 1.0, max(1.8, wall_height * 1.2)),
        )
        return obj is not None

    if conn_type in {"pit_drop", "shaft"}:
        shaft = _create_volume_cube(
            name,
            center=(location[0], location[1], from_z + wall_height * 0.5),
            size=(cell_size * 1.0, cell_size * 1.0, wall_height),
            parent=parent,
        )
        return shaft is not None

    if conn_type == "elevator":
        shaft = _create_volume_cube(
            name,
            center=(location[0], location[1], from_z + wall_height * 0.5),
            size=(cell_size * 1.2, cell_size * 1.2, wall_height),
            parent=parent,
        )
        return shaft is not None

    steps = max(5, int(round(wall_height / 0.45)))
    step_height = wall_height / steps
    step_depth = max(cell_size * 0.85, 0.7)
    step_width = max(cell_size * 1.2, 1.8)
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for step_idx in range(steps):
        res = bmesh.ops.create_cube(bm, size=1.0)
        verts = res["verts"]
        current_depth = (step_idx + 1) * step_depth
        current_height = (step_idx + 1) * step_height
        for vert in verts:
            vert.co.x *= step_depth / 2.0
            vert.co.y *= step_width / 2.0
            vert.co.z *= step_height / 2.0
            vert.co.x += current_depth - step_depth / 2.0
            vert.co.z += current_height - step_height / 2.0
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.parent = parent
    bpy.context.collection.objects.link(obj)
    return True


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
    new_ops = [copy.deepcopy(op) for op in spec.operations]

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
    """Generate a building from AAA quality components.

    Composes stone walls, gothic windows, doorways, and a pitched roof
    into a complete building using the quality generators.

    Params:
        name: object name (default "Building")
        width: building width (default 10)
        depth: building depth (default 8)
        floors: number of floors (default 2)
        style: style preset name (default "medieval")
        seed: random seed (default 0)
        wall_height: height per floor (default 4.0)
    """
    logger.info("Generating AAA quality building")

    preset_name = params.get("preset")
    preset = get_vb_building_preset(preset_name) if preset_name else None
    if preset_name and preset is None:
        raise ValueError(
            f"Unknown VB building preset '{preset_name}'. "
            f"Valid: {list(VB_BUILDING_PRESETS.keys())}"
        )

    name = params.get("name", (preset_name or "Building"))
    width = max(5.6, float(params.get("width", preset["width"] if preset else 10)))
    depth_val = max(5.6, float(params.get("depth", preset["depth"] if preset else 8)))
    floors = int(max(1, params.get("floors", preset["floors"] if preset else 2)))
    style = params.get("style", preset["style"] if preset else "medieval")
    seed = params.get("seed", 0)
    wall_height = max(3.2, float(params.get("wall_height", 4.0)))
    weathering_level = params.get("weathering_level", 0.0)
    site_profile = str(params.get("site_profile", "")).strip().lower()
    foundation_profile = params.get("foundation_profile") if isinstance(params.get("foundation_profile"), dict) else None

    rng = random.Random(seed)
    total_height = wall_height * floors

    # Create parent empty to hold all building parts
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "CUBE"
    parent.empty_display_size = 0.5
    bpy.context.collection.objects.link(parent)

    component_count = 0
    total_verts = 0
    total_faces = 0
    structural_shell_objects: list[Any] = []

    # Wall thickness for stone walls
    wall_thick = 0.4

    # is_gothic must be defined before wall generation (fixes NameError from original code)
    is_gothic = style in ("gothic", "fortress")
    block_style = "ashlar" if is_gothic else "rubble"
    _wall_mat_key = "smooth_stone" if is_gothic else "rough_stone_wall"
    requested_openings = copy.deepcopy(
        params.get("openings", preset.get("openings", []) if preset else [])
    )
    resolved_openings = _resolve_building_openings(
        width=float(width),
        depth=float(depth_val),
        floors=int(max(1, floors)),
        wall_height=float(wall_height),
        wall_thickness=float(wall_thick),
        style=style,
        requested_openings=requested_openings,
    )
    for opening in resolved_openings:
        opening["width"] = max(1.05 if opening["kind"] == "window" else 1.3, float(opening["width"]))
        opening["height"] = max(1.25 if opening["kind"] == "window" else 2.3, float(opening["height"]))

    openings_by_wall: dict[str, list[dict[str, Any]]] = {wall_name: [] for wall_name in _WALL_NAME_TO_INDEX}
    for opening in resolved_openings:
        openings_by_wall[opening["wall"]].append(opening)

    wall_configs = {
        "front": {"origin_x": 0.0, "origin_y": 0.0, "rotation": 0.0, "length": width},
        "back": {"origin_x": 0.0, "origin_y": depth_val - wall_thick, "rotation": 0.0, "length": width},
        "left": {"origin_x": wall_thick, "origin_y": wall_thick, "rotation": math.pi / 2.0, "length": max(0.0, depth_val - 2.0 * wall_thick)},
        "right": {"origin_x": width, "origin_y": wall_thick, "rotation": math.pi / 2.0, "length": max(0.0, depth_val - 2.0 * wall_thick)},
    }

    wall_segment_count = 0
    wall_opening_metadata: list[dict[str, Any]] = []
    for wall_name, cfg in wall_configs.items():
        wall_segments, wall_openings = _compute_wall_segments(
            float(cfg["length"]),
            float(total_height),
            openings_by_wall.get(wall_name, []),
        )
        for opening in wall_openings:
            wall_opening_metadata.append({
                "wall": opening["wall"],
                "wall_index": opening["wall_index"],
                "kind": opening["kind"],
                "style": opening["requested_style"],
                "floor": opening["floor"],
                "center": round(float(opening["center"]), 4),
                "bottom": round(float(opening["world_bottom"]), 4),
                "width": round(float(opening["width"]), 4),
                "height": round(float(opening["height"]), 4),
            })
        for seg_idx, segment in enumerate(wall_segments):
            seg_width = float(segment["u1"] - segment["u0"])
            seg_height = float(segment["v1"] - segment["v0"])
            if seg_width < 0.08 or seg_height < 0.08:
                continue
            wall_spec = generate_stone_wall(
                width=seg_width,
                height=seg_height,
                thickness=wall_thick,
                block_style=block_style,
                mortar_depth=0.008,
                block_variation=rng.uniform(0.2, 0.4),
                seed=rng.randint(0, 99999),
            )
            wall_obj = mesh_from_spec(wall_spec, name=f"{name}_Wall_{wall_name}_{seg_idx}")
            if isinstance(wall_obj, dict):
                continue
            if wall_name in {"front", "back"}:
                wall_obj.location = (
                    float(cfg["origin_x"]) + float(segment["u0"]),
                    float(cfg["origin_y"]),
                    float(segment["v0"]),
                )
            else:
                wall_obj.location = (
                    float(cfg["origin_x"]),
                    float(cfg["origin_y"]) + float(segment["u0"]),
                    float(segment["v0"]),
                )
            wall_obj.rotation_euler = (0.0, 0.0, float(cfg["rotation"]))
            wall_obj.parent = parent
            wall_obj["vb_editable_role"] = "wall_segment"
            wall_obj["vb_wall_name"] = wall_name
            wall_obj["vb_wall_segment_index"] = seg_idx
            for poly in wall_obj.data.polygons:
                poly.use_smooth = True
            _assign_procedural_material(wall_obj, _wall_mat_key)
            component_count += 1
            wall_segment_count += 1
            structural_shell_objects.append(wall_obj)
            total_verts += len(wall_spec.get("vertices", []))
            total_faces += len(wall_spec.get("faces", []))

    def _opening_transform(opening: dict[str, Any]) -> tuple[tuple[float, float, float], float]:
        base_z = float(opening["world_bottom"])
        center = float(opening["center"])
        wall_name = opening["wall"]
        if wall_name == "front":
            return (center, 0.0, base_z), 0.0
        if wall_name == "back":
            return (center, depth_val, base_z), math.pi
        if wall_name == "left":
            return (0.0, wall_thick + center, base_z), -math.pi / 2.0
        return (width, wall_thick + center, base_z), math.pi / 2.0

    window_count = 0
    door_count = 0
    roof_created = False
    for opening_idx, opening in enumerate(resolved_openings):
        obj_location, obj_rotation_z = _opening_transform(opening)
        if opening["kind"] == "window":
            win_spec = generate_gothic_window(
                width=float(opening["width"]),
                height=float(opening["height"]),
                style=str(opening.get("window_style") or ("pointed_arch" if is_gothic else "rectangular")),
                tracery=is_gothic and opening["floor"] == floors - 1,
                has_sill=bool(opening.get("has_sill", True)),
                has_shutters=not is_gothic,
                frame_depth=max(0.12, wall_thick * 0.42),
                seed=rng.randint(0, 99999),
            )
            win_obj = mesh_from_spec(win_spec, name=f"{name}_Window_{opening['wall']}_{opening_idx}")
            if isinstance(win_obj, dict):
                continue
            win_obj.location = obj_location
            win_obj.rotation_euler = (0.0, 0.0, obj_rotation_z)
            win_obj.parent = parent
            win_obj["vb_editable_role"] = "window_frame"
            win_obj["vb_wall_name"] = opening["wall"]
            for poly in win_obj.data.polygons:
                poly.use_smooth = True
            _assign_procedural_material(win_obj, "smooth_stone" if is_gothic else "rough_stone_wall")
            window_count += 1
            component_count += 1
            total_verts += len(win_spec.get("vertices", []))
            total_faces += len(win_spec.get("faces", []))
            continue

        door_spec = generate_archway(
            width=float(opening["width"]),
            height=float(opening["height"]),
            depth=wall_thick + 0.08,
            arch_style=str(opening.get("door_arch_style") or ("gothic_pointed" if is_gothic else "roman_round")),
            has_keystone=is_gothic,
            seed=rng.randint(0, 99999),
        )
        door_obj = mesh_from_spec(door_spec, name=f"{name}_Door_{opening['wall']}_{opening_idx}")
        if isinstance(door_obj, dict):
            continue
        door_obj.location = obj_location
        door_obj.rotation_euler = (0.0, 0.0, obj_rotation_z)
        door_obj.parent = parent
        door_obj["vb_editable_role"] = "door_frame"
        door_obj["vb_wall_name"] = opening["wall"]
        for poly in door_obj.data.polygons:
            poly.use_smooth = True
        _assign_procedural_material(door_obj, "smooth_stone")
        door_count += 1
        component_count += 1
        total_verts += len(door_spec.get("vertices", []))
        total_faces += len(door_spec.get("faces", []))

    # === FLOOR SLABS: one per floor level so interiors have ground ===
    for floor_idx in range(floors):
        _fz = floor_idx * wall_height
        _fbm = bmesh.new()
        _ix0, _ix1 = wall_thick, width - wall_thick
        _iy0, _iy1 = wall_thick, depth_val - wall_thick
        _fv = [
            _fbm.verts.new((_ix0, _iy0, _fz)),
            _fbm.verts.new((_ix1, _iy0, _fz)),
            _fbm.verts.new((_ix1, _iy1, _fz)),
            _fbm.verts.new((_ix0, _iy1, _fz)),
            _fbm.verts.new((_ix0, _iy0, _fz + 0.08)),
            _fbm.verts.new((_ix1, _iy0, _fz + 0.08)),
            _fbm.verts.new((_ix1, _iy1, _fz + 0.08)),
            _fbm.verts.new((_ix0, _iy1, _fz + 0.08)),
        ]
        for _fi in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
            try:
                _fbm.faces.new([_fv[i] for i in _fi])
            except ValueError:
                pass
        _fmesh = bpy.data.meshes.new(f"{name}_Floor_{floor_idx}")
        _fbm.to_mesh(_fmesh)
        _fbm.free()
        _fobj = bpy.data.objects.new(f"{name}_Floor_{floor_idx}", _fmesh)
        bpy.context.collection.objects.link(_fobj)
        _fobj.parent = parent
        _assign_procedural_material(_fobj, "cobblestone_floor" if floor_idx == 0 else "plank_floor")
        component_count += 1
        structural_shell_objects.append(_fobj)

    # === ROOF: distinct material for visual differentiation from stone walls ===
    roof_style = preset.get("roof_style") if preset else None
    if not roof_style:
        roof_style = "gable" if style != "fortress" else "flat"
    roof_material = preset.get("roof_material") if preset else None
    if not roof_material:
        roof_material = "tile" if style != "fortress" else "stone"
    roof_spec = generate_roof(
        width=width + 0.6,
        depth=depth_val + 0.6,
        pitch=float(preset.get("roof_pitch", 50.0 if is_gothic else 40.0)) if preset else (50.0 if is_gothic else 40.0),
        style=roof_style,
        material=roof_material,
        overhang=float(preset.get("roof_overhang", 0.3)) if preset else 0.3,
        seed=rng.randint(0, 99999),
    )
    roof_obj = mesh_from_spec(roof_spec, name=f"{name}_Roof")
    if not isinstance(roof_obj, dict):
        # Y=-0.3 correctly centers roof with 0.6m overhang each side; Z=total_height sits on wall tops
        roof_obj.location = (width / 2.0, -0.3, total_height)
        roof_obj.parent = parent
        for poly in roof_obj.data.polygons:
            poly.use_smooth = True
        _roof_mat = "slate_tiles" if is_gothic else "thatch_roof"
        _assign_procedural_material(roof_obj, _roof_mat)
        component_count += 1
        structural_shell_objects.append(roof_obj)
        total_verts += len(roof_spec.get("vertices", []))
        total_faces += len(roof_spec.get("faces", []))
        roof_created = True

    facade_result = _apply_modular_facade(
        name,
        parent=parent,
        width=float(width),
        depth=float(depth_val),
        floors=int(floors),
        style=style,
        wall_height=float(wall_height),
        wall_thickness=float(wall_thick),
        openings=resolved_openings,
        site_profile=site_profile,
        seed=seed,
    )
    component_count += int(facade_result["module_count"])
    structural_shell_objects.extend(facade_result.get("shell_objects", []))

    # === EXTERIOR DRESSING ===
    exterior_props = list(preset.get("props", [])) if preset else []
    exterior_count = 0
    if exterior_props:
        slots = [
            (width * 0.5, -0.9, 0.0, 0.0),              # front center
            (width * 0.24, -0.8, 0.0, 0.0),             # front left
            (width * 0.76, -0.8, 0.0, 0.0),             # front right
            (-0.85, depth_val * 0.25, 0.0, math.pi / 2),  # left side
            (-0.85, depth_val * 0.75, 0.0, math.pi / 2),  # left side rear
            (width + 0.85, depth_val * 0.25, 0.0, -math.pi / 2),  # right side
            (width + 0.85, depth_val * 0.75, 0.0, -math.pi / 2),  # right side rear
            (width * 0.5, depth_val + 0.95, 0.0, math.pi),  # back center
        ]
        for pi, prop_type in enumerate(exterior_props):
            sx, sy, sz, rot = slots[pi % len(slots)]
            scale = 0.85 + 0.1 * ((pi * 13) % 3)
            obj = _spawn_catalog_object(
                name,
                prop_type,
                pi,
                (sx, sy, sz),
                parent,
                rotation=rot,
                scale=(scale, scale, scale),
            )
            if obj is not None:
                exterior_count += 1

    accent_count = 0
    if style in {"gothic", "fortress"}:
        accent_slots = [
            (-0.45, -0.25, 0.0, 0.0),
            (width + 0.45, -0.25, 0.0, 0.0),
            (-0.45, depth_val + 0.25, 0.0, math.pi),
            (width + 0.45, depth_val + 0.25, 0.0, math.pi),
        ]
        for ai, (ax, ay, az, rot) in enumerate(accent_slots):
            buttress = _spawn_catalog_object(
                name,
                "buttress",
                900 + ai,
                (ax, ay, az),
                parent,
                rotation=rot,
                scale=(0.95, 0.95, 1.05),
            )
            if buttress is not None:
                accent_count += 1
        for bi, (bx, by, bz, rot) in enumerate([
            (width * 0.18, -0.95, total_height * 0.38, 0.0),
            (width * 0.82, -0.95, total_height * 0.38, 0.0),
        ]):
            banner = _spawn_catalog_object(
                name,
                "banner",
                950 + bi,
                (bx, by, bz),
                parent,
                rotation=rot,
                scale=(0.85, 0.85, 0.85),
            )
            if banner is not None:
                accent_count += 1

    site_feature_count = _apply_site_profile_features(
        name,
        site_profile,
        width,
        depth_val,
        wall_height,
        parent,
        seed,
    )
    foundation_result = _apply_foundation_fitment(
        name,
        parent=parent,
        footprint=(float(width), float(depth_val)),
        wall_thickness=float(wall_thick),
        foundation_profile=foundation_profile,
    )
    component_count += int(foundation_result["created"])
    structural_shell_objects.extend(foundation_result.get("shell_objects", []))

    consolidate_shell = bool(params.get("consolidate_shell", True))
    remove_shell_sources = bool(params.get("remove_shell_sources", True))
    shell_merge_result = {
        "created": 0,
        "source_count": 0,
        "removed_source_count": 0,
        "object_name": None,
        "vertex_count": 0,
        "face_count": 0,
        "merge_distance": 0.0001,
        "cleanup_requested": bool(consolidate_shell),
        "cleanup_applied": False,
        "cleanup_deferred": bool(consolidate_shell),
        "watertight": False,
        "boundary_edge_count": 0,
        "non_manifold_edge_count": 0,
        "loose_vertex_count": 0,
        "degenerate_face_count": 0,
        "geometry_quality": "complete",
        "geometry_issues": [],
    }
    if consolidate_shell:
        shell_merge_result = _merge_structural_shell_objects(
            f"{name}_Shell",
            structural_shell_objects,
            parent,
            cleanup_sources=remove_shell_sources,
            merge_distance=max(0.00001, float(params.get("shell_merge_distance", 0.0001))),
        )
        if shell_merge_result["created"]:
            if remove_shell_sources:
                component_count = max(
                    0,
                    component_count - int(shell_merge_result["source_count"]) + int(shell_merge_result["created"]),
                )
            else:
                component_count += int(shell_merge_result["created"])
        if shell_merge_result["geometry_issues"]:
            logger.warning(
                "Building %s shell consolidation issues: %s",
                name,
                "; ".join(shell_merge_result["geometry_issues"]),
            )
    quality_result = _summarize_live_building_quality(
        expected_openings=len(resolved_openings),
        door_count=door_count,
        window_count=window_count,
        wall_segment_count=wall_segment_count,
        foundation_piece_count=int(foundation_result["created"]),
        roof_created=roof_created,
        component_count=component_count,
    )
    if shell_merge_result["geometry_issues"]:
        quality_result["geometry_issues"].extend(shell_merge_result["geometry_issues"])
        quality_result["geometry_quality"] = "partial"
    if quality_result["geometry_issues"]:
        logger.warning(
            "Building %s generated with geometry issues: %s",
            name,
            "; ".join(quality_result["geometry_issues"]),
        )

    # === INTERIORS ===
    interior_count = 0
    room_type_map = {
        "shrine_minor": ["shrine_room"],
        "shrine_major": ["shrine_room", "storage"],
        "forge": ["smithy", "storage"],
        "inn": ["tavern", "bedroom"],
        "warehouse": ["storage", "storage"],
        "barracks": ["barracks", "guard_post"],
        "gatehouse": ["guard_post", "storage"],
        "rowhouse": ["kitchen", "bedroom", "storage"],
        "abandoned_house": ["kitchen", "bedroom", "storage"],
        "ruined_fortress_tower": ["guard_post", "storage"],
    }
    site_room_map = _SITE_PROFILE_ROOM_MAP.get(site_profile, [])
    if site_room_map:
        interior_room_types = list(site_room_map)
    else:
        interior_room_types = room_type_map.get(preset_name or "", [])
    if not interior_room_types:
        if style in {"fortress", "gothic"}:
            interior_room_types = ["guard_post", "storage"]
        else:
            interior_room_types = ["bedroom", "kitchen", "storage"]

    usable_width = max(3.0, width - 1.2)
    usable_depth = max(3.0, depth_val - 1.2)
    usable_height = max(2.8, wall_height - 0.35)
    stair_anchor_map = {
        "tavern": (0.78, 0.22),
        "kitchen": (0.76, 0.24),
        "storage": (0.80, 0.20),
        "smithy": (0.80, 0.20),
        "barracks": (0.78, 0.22),
        "guard_post": (0.78, 0.20),
        "shrine_room": (0.18, 0.80),
        "chapel": (0.18, 0.80),
        "dining_hall": (0.18, 0.78),
        "bedroom": (0.76, 0.22),
    }
    stairs_steps = max(10, int(math.ceil(usable_height / 0.18)))
    stairs_direction = "straight" if usable_depth >= (stairs_steps * 0.28) + 1.0 else "spiral"
    stair_width = min(1.35, max(1.0, usable_width * 0.18))
    for floor_idx in range(max(1, floors)):
        room_type = interior_room_types[min(floor_idx, len(interior_room_types) - 1)]
        room_name = f"{name}_Interior_{floor_idx}"
        handle_generate_interior({
            "name": room_name,
            "room_type": room_type,
            "width": usable_width,
            "depth": usable_depth,
            "height": usable_height,
            "seed": rng.randint(0, 99999),
        })
        room_obj = bpy.data.objects.get(room_name)
        if room_obj is not None:
            room_obj.parent = parent
            room_obj.location = (0.6, 0.6, floor_idx * wall_height + 0.15)
            stair_anchor = stair_anchor_map.get(room_type, (0.78, 0.22))
            stair_center = (
                min(max(1.6, usable_width * stair_anchor[0]), usable_width - 1.6),
                min(max(1.8, usable_depth * stair_anchor[1]), usable_depth - 1.8),
            )
            opening_center = stair_center if floor_idx > 0 else None
            opening_size = (2.4, 2.4) if stairs_direction == "spiral" else (2.2, 2.2)
            _create_floor_segments(
                f"{room_name}_Floor",
                usable_width,
                usable_depth,
                room_obj,
                opening_center=opening_center,
                opening_size=opening_size if opening_center is not None else None,
            )
            if floor_idx < floors - 1:
                stairs_spec = generate_staircase_mesh(
                    steps=stairs_steps,
                    width=stair_width,
                    direction=stairs_direction,
                )
                stairs_obj = mesh_from_spec(
                    stairs_spec,
                    name=f"{room_name}_Staircase",
                    location=(stair_center[0], stair_center[1], 0.0),
                    parent=room_obj,
                )
                if not isinstance(stairs_obj, dict):
                    stairs_obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
                    stairs_obj["vb_room_type"] = room_type
                    stairs_obj["vb_editable_role"] = "stair_connection"
            interior_count += 1

    result = {
        "name": name,
        "style": style,
        "floors": floors,
        "footprint": [width, depth_val],
        "wall_height": wall_height,
        "vertex_count": total_verts,
        "face_count": total_faces,
        "component_count": component_count,
        "wall_segment_count": wall_segment_count,
        "door_count": door_count,
        "window_count": window_count,
        "opening_count": len(resolved_openings),
        "geometry_quality": quality_result["geometry_quality"],
        "geometry_issues": quality_result["geometry_issues"],
        "shell_consolidated": bool(shell_merge_result["created"]),
        "shell_object_name": shell_merge_result["object_name"],
        "shell_source_count": int(shell_merge_result["source_count"]),
        "shell_removed_source_count": int(shell_merge_result["removed_source_count"]),
        "shell_vertex_count": int(shell_merge_result["vertex_count"]),
        "shell_face_count": int(shell_merge_result["face_count"]),
        "shell_merge_distance": float(shell_merge_result["merge_distance"]),
        "shell_cleanup_requested": bool(shell_merge_result["cleanup_requested"]),
        "shell_cleanup_applied": bool(shell_merge_result["cleanup_applied"]),
        "shell_cleanup_deferred": bool(shell_merge_result["cleanup_deferred"]),
        "shell_watertight": bool(shell_merge_result["watertight"]),
        "shell_boundary_edge_count": int(shell_merge_result["boundary_edge_count"]),
        "shell_non_manifold_edge_count": int(shell_merge_result["non_manifold_edge_count"]),
        "shell_loose_vertex_count": int(shell_merge_result["loose_vertex_count"]),
        "shell_degenerate_face_count": int(shell_merge_result["degenerate_face_count"]),
        "shell_merge_quality": shell_merge_result["geometry_quality"],
        "shell_merge_issues": list(shell_merge_result["geometry_issues"]),
        "exterior_prop_count": exterior_count,
        "architectural_accent_count": accent_count,
        "site_feature_count": site_feature_count,
        "facade_module_count": int(facade_result["module_count"]),
        "facade_chimney_count": int(facade_result["chimney_count"]),
        "facade_buttress_count": int(facade_result["buttress_count"]),
        "foundation_piece_count": int(foundation_result["created"]),
        "foundation_retaining_wall_count": int(foundation_result["retaining_wall_count"]),
        "foundation_stair_count": int(foundation_result["stair_count"]),
        "interior_room_count": interior_count,
        "block_style": block_style,
        "roof_style": roof_style,
        "weathering_level": weathering_level,
        "openings": wall_opening_metadata,
    }
    if preset:
        result["preset"] = preset_name
    if site_profile:
        result["site_profile"] = site_profile
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
    shell_weld_result = _weld_mesh_object(obj)
    _assign_procedural_material(obj, "stone_fortified")

    # Add procedural castle detail elements
    details_coll = bpy.data.collections.new(f"{name}_CastleDetails")
    bpy.context.scene.collection.children.link(details_coll)

    def _material_for_castle_detail(role: str) -> str:
        if role in {"drawbridge"}:
            return "rough_timber"
        if role in {"fountain"}:
            return "smooth_stone"
        if role in {"gate"}:
            return "stone_dark"
        return "stone_fortified"

    half = outer_size / 2.0
    procedural_count = 0

    # Gate at front center
    gate_entry = CASTLE_ELEMENT_MAP.get("gate")
    if gate_entry is not None:
        gen_func, gen_kwargs = gate_entry
        gate_spec = gen_func(**gen_kwargs)
        gate_obj = mesh_from_spec(
            gate_spec,
            name=f"{name}_gate",
            location=(0, half, 0),
            collection=details_coll,
            parent=obj,
        )
        if gate_obj is not None and not isinstance(gate_obj, dict):
            _assign_procedural_material_recursive(gate_obj, _material_for_castle_detail("gate"))
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
                ramp_obj = mesh_from_spec(
                    ramp_spec,
                    name=f"{name}_rampart_{side_idx}_{i}",
                    location=(px, py, 0),
                    rotation=(0, 0, angle),
                    collection=details_coll,
                    parent=obj,
                )
                if ramp_obj is not None and not isinstance(ramp_obj, dict):
                    _assign_procedural_material_recursive(ramp_obj, _material_for_castle_detail("rampart"))
                procedural_count += 1

    # Drawbridge at gate position, extending outward
    draw_entry = CASTLE_ELEMENT_MAP.get("drawbridge")
    if draw_entry is not None:
        gen_func, gen_kwargs = draw_entry
        draw_spec = gen_func(**gen_kwargs)
        draw_obj = mesh_from_spec(
            draw_spec,
            name=f"{name}_drawbridge",
            location=(0, half + 2.0, 0),
            collection=details_coll,
            parent=obj,
        )
        if draw_obj is not None and not isinstance(draw_obj, dict):
            _assign_procedural_material_recursive(draw_obj, _material_for_castle_detail("drawbridge"))
        procedural_count += 1

    # Fountain at courtyard center
    fountain_entry = CASTLE_ELEMENT_MAP.get("fountain")
    if fountain_entry is not None:
        gen_func, gen_kwargs = fountain_entry
        fountain_spec = gen_func(**gen_kwargs)
        fountain_obj = mesh_from_spec(
            fountain_spec,
            name=f"{name}_fountain",
            location=(0, 0, 0),
            collection=details_coll,
            parent=obj,
        )
        if fountain_obj is not None and not isinstance(fountain_obj, dict):
            _assign_procedural_material_recursive(fountain_obj, _material_for_castle_detail("fountain"))
        procedural_count += 1

    result = _build_castle_result(name, spec, procedural_count)
    result["shell_weld_vertex_count"] = shell_weld_result["vertex_count"]
    result["shell_weld_face_count"] = shell_weld_result["face_count"]
    result["shell_weld_watertight"] = bool(shell_weld_result["watertight"])
    result["shell_weld_boundary_edge_count"] = int(shell_weld_result["boundary_edge_count"])
    result["shell_weld_non_manifold_edge_count"] = int(shell_weld_result["non_manifold_edge_count"])
    result["shell_weld_loose_vertex_count"] = int(shell_weld_result["loose_vertex_count"])
    result["shell_weld_degenerate_face_count"] = int(shell_weld_result["degenerate_face_count"])
    result["shell_weld_quality"] = shell_weld_result["geometry_quality"]
    result["shell_weld_issues"] = shell_weld_result["geometry_issues"]
    if shell_weld_result["geometry_issues"]:
        logger.warning(
            "Castle %s shell weld issues: %s",
            name,
            "; ".join(shell_weld_result["geometry_issues"]),
        )
    if result["geometry_issues"]:
        logger.warning(
            "Castle %s generated with geometry issues: %s",
            name,
            "; ".join(result["geometry_issues"]),
        )
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
    room_empty["vb_room_type"] = room_type
    room_empty["vb_editable_role"] = "interior_root"
    bpy.context.collection.objects.link(room_empty)

    shell_count = _create_interior_shell(
        name,
        width=float(width),
        depth=float(depth),
        height=float(height),
        parent=room_empty,
        room_type=room_type,
        seed=seed,
    )

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

        if not isinstance(item_obj, dict):
            item_obj["vb_room_type"] = room_type
            item_obj["vb_editable_role"] = "furniture"

    # ---- Clutter scatter (MESH-03) ----
    clutter_density = params.get("clutter_density", 0.5)
    clutter = generate_clutter_layout(
        room_type, width, depth, layout, seed, density=clutter_density,
    )
    clutter_count = 0
    for c_item in clutter:
        c_name = f"{name}_clutter_{c_item['type']}"
        c_type = c_item["type"]
        csx, csy, csz = c_item["scale"]

        gen_entry = FURNITURE_GENERATOR_MAP.get(c_type)
        if gen_entry is not None:
            gen_func, gen_kwargs = gen_entry
            spec = gen_func(**gen_kwargs)
            c_obj = mesh_from_spec(
                spec,
                name=c_name,
                location=tuple(c_item["position"]),
                rotation=(0, 0, c_item["rotation"]),
                scale=(csx, csy, csz),
                parent=room_empty,
            )
        else:
            # Small cube fallback for unmapped clutter types
            c_bm = bmesh.new()
            bmesh.ops.create_cube(c_bm, size=1.0)
            for v in c_bm.verts:
                v.co.x *= csx
                v.co.y *= csy
                v.co.z *= csz
                v.co.z += csz / 2
            c_mesh = bpy.data.meshes.new(c_name)
            c_bm.to_mesh(c_mesh)
            c_bm.free()
            c_obj = bpy.data.objects.new(c_name, c_mesh)
            c_obj.location = tuple(c_item["position"])
            c_obj.rotation_euler = (0, 0, c_item["rotation"])
            c_obj.parent = room_empty
            bpy.context.collection.objects.link(c_obj)

        if not isinstance(c_obj, dict):
            c_obj["vb_room_type"] = room_type
            c_obj["vb_editable_role"] = "clutter"
        clutter_count += 1

    # ---- Lighting placement (MESH-03) ----
    lights = generate_lighting_layout(
        room_type, width, depth, height, layout, seed=seed,
    )
    light_count = 0
    for light in lights:
        l_name = f"{name}_light_{light['light_type']}_{light_count}"
        lx, ly, lz = light["position"]

        # Create Blender point light
        light_data = bpy.data.lights.new(name=l_name, type="POINT")
        light_data.energy = light["intensity"] * 100  # Blender watts
        light_data.shadow_soft_size = light["radius"]
        # Convert color temperature to approximate RGB
        temp = light["color_temperature"]
        # Warm light approximation: 2700K=orange, 3500K=warm white
        t_norm = (temp - 2700) / 800.0  # 0.0=warmest, 1.0=coolest
        light_data.color = (
            1.0,
            0.75 + 0.15 * t_norm,
            0.45 + 0.35 * t_norm,
        )

        light_obj = bpy.data.objects.new(l_name, light_data)
        light_obj.location = (lx, ly, lz)
        light_obj.parent = room_empty
        light_obj["vb_room_type"] = room_type
        light_obj["vb_editable_role"] = "light"
        light_obj["vb_color_temperature"] = temp
        bpy.context.collection.objects.link(light_obj)
        light_count += 1

    result = _build_interior_result(name, room_type, layout, procedural_count)
    result["shell_count"] = shell_count
    result["clutter_count"] = clutter_count
    result["light_count"] = light_count
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

    Composes terrain base + buildings + roads + POIs as Blender objects.

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

    terrain = spec["terrain_bounds"]
    terrain_type = _terrain_type_for_location(location_type)
    terrain_name = f"{name}_Terrain"
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.empty_display_size = terrain["size"] / 2
    bpy.context.collection.objects.link(parent)

    # Terrain base first so later fitment can raycast against it.
    from .environment import handle_generate_terrain

    terrain_resolution = 257 if terrain["size"] <= 120 else 513
    terrain_result = handle_generate_terrain({
        "name": terrain_name,
        "terrain_type": terrain_type,
        "resolution": terrain_resolution,
        "scale": terrain["size"],
        "height_scale": 16.0 if location_type in {"fortress", "dungeon_entrance", "mountain_pass", "wizard_fortress", "cliff_keep"} else 8.0,
        "erosion": "both" if location_type in {"fortress", "dungeon_entrance", "monastery", "mining_town", "wizard_fortress", "cliff_keep", "sorcery_school"} else "hydraulic",
        "erosion_iterations": 1800 if location_type in {"fortress", "dungeon_entrance", "monastery", "wizard_fortress", "cliff_keep"} else 900,
        "seed": seed,
    })
    terrain_status = terrain_result.get("status") if isinstance(terrain_result, dict) else None
    if terrain_status not in (None, "success"):
        raise RuntimeError(
            f"Failed to generate location terrain: {terrain_result.get('error', 'unknown')}"
        )
    terrain_obj = bpy.data.objects.get(terrain_name)
    if terrain_obj is None:
        raise RuntimeError(f"Terrain object was not created: {terrain_name}")
    terrain_obj.parent = parent
    terrain_material_key = {
        "cliff_keep": "cliff_rock",
        "wizard_fortress": "cliff_rock",
        "fortress": "cliff_rock",
        "dungeon_entrance": "cliff_rock",
        "river_castle": "dirt",
        "farmstead": "grass",
        "village": "grass",
        "town": "dirt",
        "monastery": "grass",
        "sorcery_school": "grass",
    }.get(location_type, "grass" if terrain_type in {"plains", "hills"} else "dirt")
    _assign_procedural_material(terrain_obj, terrain_material_key)

    # Build roads as visible curves, fitted onto the generated terrain.
    road_count = 0
    road_seed_rng = random.Random(seed + 17)
    for i, path in enumerate(spec["paths"]):
        start = path["from"]
        end = path["to"]
        width = float(path.get("width", 2.0))
        mid_x = (start[0] + end[0]) / 2.0
        mid_y = (start[1] + end[1]) / 2.0
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx * dx + dy * dy) or 1.0
        ox = -dy / length
        oy = dx / length
        bend = min(terrain["size"] * 0.05, length * 0.12)
        mid_x += ox * road_seed_rng.uniform(-bend, bend)
        mid_y += oy * road_seed_rng.uniform(-bend, bend)
        road_points = [
            (start[0], start[1], _sample_scene_height(start[0], start[1], terrain_name) + 0.02),
            (mid_x, mid_y, _sample_scene_height(mid_x, mid_y, terrain_name) + 0.03),
            (end[0], end[1], _sample_scene_height(end[0], end[1], terrain_name) + 0.02),
        ]
        road_obj = _create_curve_path(f"{name}_road_{i}", road_points, width=width, parent=parent)
        _clear_material_slots(road_obj, context=f"location road {i}")
        road_count += 1

    # Materialize buildings as actual geometry, grounded to the terrain.
    structure_count = 0
    for i, building in enumerate(spec["buildings"]):
        if _generate_location_building(name, building, seed, i, terrain_name, parent):
            structure_count += 1

    # Materialize POIs using the strongest available prop generators.
    poi_count_actual = 0
    for i, poi in enumerate(spec["pois"]):
        if _generate_location_poi(name, poi, seed, i, terrain_name, parent):
            poi_count_actual += 1

    # Water accents for coastal location types.
    if location_type in {"fishing_village", "port_city", "river_castle"}:
        from .environment import handle_create_water

        water_size = terrain["size"] * 0.55
        water = handle_create_water({
            "name": f"{name}_Water",
            "water_level": 0.0,
            "width": water_size,
            "depth": water_size,
            "material_name": f"{name}_Water_Material",
        })
        water_obj = bpy.data.objects.get(f"{name}_Water")
        if water_obj is not None:
            water_obj.location = (terrain["size"] * 0.2, -terrain["size"] * 0.18, 0.0)
            water_obj.parent = parent

        bridge_center = (
            terrain["size"] * 0.2,
            -terrain["size"] * 0.18,
            0.18,
        )
        _create_bridge_span(
            f"{name}_Bridge",
            bridge_center,
            span=water_size * 0.52,
            bridge_width=3.2,
            parent=parent,
            style="stone",
        )

    # Location dressing for readability and AAA silhouette variety.
    dressing_idx = 0

    def add_scene_prop(item_type: str, location: tuple[float, float, float], rotation: float = 0.0, scale: tuple[float, float, float] | None = None) -> None:
        nonlocal dressing_idx
        if _spawn_catalog_object(name, item_type, dressing_idx, location, parent, rotation=rotation, scale=scale) is not None:
            dressing_idx += 1

    if location_type in {"village", "farmstead", "rural"}:
        farm_radius = terrain["size"] * 0.22
        for i in range(3):
            angle = (2.0 * math.pi * i / 3.0) + (0.12 * (i % 2))
            px = terrain["size"] * 0.5 + math.cos(angle) * farm_radius
            py = -terrain["size"] * 0.08 + math.sin(angle) * farm_radius * 0.55
            dressing_idx += _create_settlement_prop_cluster(
                name,
                {
                    "type": "farm_plot",
                    "position": (px, py, 0.0),
                    "rotation": angle,
                    "scale": (1.0, 1.0, 1.0),
                },
                dressing_idx + i,
                parent,
            )
        for i in range(2):
            add_scene_prop(
                "fence",
                (terrain["size"] * (0.24 + 0.48 * i), terrain["size"] * 0.28, 0.0),
                rotation=0.0,
                scale=(max(4.0, terrain["size"] * 0.16), 1.0, 1.0),
            )

    elif location_type == "traveler_camp":
        camp_radius = terrain["size"] * 0.08
        for i in range(4):
            angle = (2.0 * math.pi * i / 4.0) + 0.2
            px = terrain["size"] * 0.5 + math.cos(angle) * camp_radius
            py = terrain["size"] * 0.5 + math.sin(angle) * camp_radius
            add_scene_prop("tent", (px, py, 0.0), rotation=angle)
        dressing_idx += _create_settlement_prop_cluster(
            name,
            {
                "type": "campfire_area",
                "position": (terrain["size"] * 0.5, terrain["size"] * 0.5, 0.0),
                "rotation": 0.0,
                "scale": (1.0, 1.0, 1.0),
            },
            dressing_idx + 10,
            parent,
        )
        add_scene_prop("lookout_post", (terrain["size"] * 0.65, terrain["size"] * 0.52, 0.0), rotation=0.0)
        add_scene_prop("hitching_post", (terrain["size"] * 0.42, terrain["size"] * 0.48, 0.0), rotation=0.0)

    elif location_type == "merchant_camp":
        dressing_idx += _create_settlement_prop_cluster(
            name,
            {
                "type": "market_stall_cluster",
                "position": (terrain["size"] * 0.5, terrain["size"] * 0.5, 0.0),
                "rotation": 0.0,
                "scale": (1.0, 1.0, 1.0),
            },
            dressing_idx + 20,
            parent,
        )
        add_scene_prop("cart", (terrain["size"] * 0.64, terrain["size"] * 0.46, 0.0), rotation=0.2)
        add_scene_prop("hitching_post", (terrain["size"] * 0.38, terrain["size"] * 0.42, 0.0), rotation=0.0)
        add_scene_prop("lookout_post", (terrain["size"] * 0.59, terrain["size"] * 0.67, 0.0), rotation=0.0)

    elif location_type in {"wizard_fortress", "sorcery_school"}:
        add_scene_prop("holy_symbol", (terrain["size"] * 0.5, terrain["size"] * 0.7, 0.0), rotation=0.0, scale=(1.4, 1.4, 1.4))
        add_scene_prop("map_display", (terrain["size"] * 0.34, terrain["size"] * 0.64, 0.0), rotation=0.0, scale=(1.3, 1.0, 1.0))
        add_scene_prop("candelabra", (terrain["size"] * 0.66, terrain["size"] * 0.62, 0.0), rotation=0.0, scale=(1.1, 1.1, 1.1))
        add_scene_prop("pillar", (terrain["size"] * 0.5, terrain["size"] * 0.82, 0.0), rotation=0.0, scale=(1.2, 1.2, 2.0))

    elif location_type == "cliff_keep":
        _create_bridge_span(
            f"{name}_CliffBridge",
            (terrain["size"] * 0.52, -terrain["size"] * 0.22, 0.25),
            span=max(10.0, terrain["size"] * 0.34),
            bridge_width=3.5,
            parent=parent,
            style="stone",
        )
        add_scene_prop("fence", (terrain["size"] * 0.52, terrain["size"] * 0.74, 0.0), rotation=0.0, scale=(terrain["size"] * 0.18, 1.0, 1.0))

    elif location_type == "river_castle":
        _create_bridge_span(
            f"{name}_RiverSpan",
            (terrain["size"] * 0.34, -terrain["size"] * 0.12, 0.2),
            span=max(10.0, terrain["size"] * 0.28),
            bridge_width=3.2,
            parent=parent,
            style="stone",
        )
        add_scene_prop("fence", (terrain["size"] * 0.52, terrain["size"] * 0.78, 0.0), rotation=0.0, scale=(terrain["size"] * 0.16, 1.0, 1.0))

    elif location_type == "ruined_town":
        dressing_idx += _create_settlement_prop_cluster(
            name,
            {
                "type": "battle_aftermath",
                "position": (terrain["size"] * 0.48, terrain["size"] * 0.48, 0.0),
                "rotation": 0.0,
                "scale": (1.0, 1.0, 1.0),
            },
            dressing_idx + 30,
            parent,
        )
        add_scene_prop("gravestone", (terrain["size"] * 0.62, terrain["size"] * 0.41, 0.0), rotation=0.0)
        add_scene_prop("barricade", (terrain["size"] * 0.34, terrain["size"] * 0.36, 0.0), rotation=0.0)

    # A simple hierarchy-friendly marker object for agents.
    bpy.context.view_layer.objects.active = parent

    return {
        "status": "success",
        "result": {
            "name": name,
            "location_type": location_type,
            "building_count": structure_count,
            "path_count": road_count,
            "poi_count": poi_count_actual,
            "terrain_size": terrain["size"],
            "terrain_type": terrain_type,
            "terrain_object": terrain_name,
        },
    }


# ---------------------------------------------------------------------------
# Terrain-aligned prop materialization (Phase 36-02)
# ---------------------------------------------------------------------------


def _get_or_create_prop_collection(
    settlement_name: str,
    district: str,
) -> bpy.types.Collection:
    """Return (or create) a Blender collection for materialized props.

    Organises props under ``{settlement_name}_Props`` with per-district
    sub-collections such as ``{settlement_name}_Props_Market``.
    """
    root_name = f"{settlement_name}_Props"
    root_col = bpy.data.collections.get(root_name)
    if root_col is None:
        root_col = bpy.data.collections.new(root_name)
        bpy.context.scene.collection.children.link(root_col)

    # Friendly district suffix
    district_suffix = district.replace("_", " ").title().replace(" ", "")
    sub_name = f"{settlement_name}_Props_{district_suffix}"
    sub_col = bpy.data.collections.get(sub_name)
    if sub_col is None:
        sub_col = bpy.data.collections.new(sub_name)
        root_col.children.link(sub_col)

    return sub_col


def _materialize_prop(
    prop_spec: dict,
    glb_path: str,
    terrain_object: bpy.types.Object | None,
    parent: bpy.types.Object | None,
    settlement_name: str = "",
    center: tuple[float, float] = (0.0, 0.0),
    radius: float = 50.0,
) -> bpy.types.Object | None:
    """Import a GLB prop and snap it to the terrain surface with normal alignment.

    Parameters
    ----------
    prop_spec : dict
        Prop placement spec with ``position``, ``rotation_z``, ``prop_type``,
        ``corruption_band``, and ``cache_key``.
    glb_path : str
        Absolute path to the ``.glb`` file to import.
    terrain_object : bpy.types.Object or None
        The terrain mesh to raycast against. When *None*, the prop is placed
        at the raw ``position`` without surface snapping.
    parent : bpy.types.Object or None
        Empty that acts as the settlement root.
    settlement_name : str
        Used for collection naming.
    center : (x, y)
        Settlement center for district classification.
    radius : float
        Settlement radius.

    Returns
    -------
    bpy.types.Object or None
        The root imported object, or *None* on failure.
    """
    import os

    if not os.path.isfile(glb_path):
        logger.warning("GLB not found for prop %s: %s", prop_spec.get("prop_type"), glb_path)
        return None

    position = prop_spec.get("position", (0.0, 0.0, 0.0))
    rotation_z = float(prop_spec.get("rotation_z", 0.0))

    # --- Import GLB ---
    try:
        bpy.ops.import_scene.gltf(filepath=glb_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GLB import failed for %s: %s", glb_path, exc)
        return None

    imported = list(bpy.context.selected_objects)
    if not imported:
        logger.warning("GLB import produced no objects: %s", glb_path)
        return None

    # Pick root (prefer MESH, fallback to first)
    root = imported[0]
    for obj in imported:
        if obj.type == "MESH":
            root = obj
            break

    # --- Position & rotation ---
    pos = Vector((float(position[0]), float(position[1]), float(position[2]) if len(position) > 2 else 0.0))
    root.location = pos
    root.rotation_euler.z = rotation_z

    # --- Terrain snap & normal alignment ---
    if terrain_object is not None and terrain_object.type == "MESH":
        try:
            ray_origin = pos + Vector((0.0, 0.0, 50.0))
            ray_dir = Vector((0.0, 0.0, -1.0))
            # Raycast in terrain's local space
            inv_mat = terrain_object.matrix_world.inverted()
            local_origin = inv_mat @ ray_origin
            local_dir = (inv_mat.to_3x3() @ ray_dir).normalized()

            success, hit_loc, hit_normal, _ = terrain_object.ray_cast(local_origin, local_dir)

            if success and hit_loc is not None:
                world_hit = terrain_object.matrix_world @ hit_loc
                root.location.z = world_hit.z + 0.01

                # Align to surface normal
                world_normal = (terrain_object.matrix_world.to_3x3() @ hit_normal).normalized()
                up = Vector((0.0, 0.0, 1.0))
                if world_normal.dot(up) < 0.999:
                    rot_axis = up.cross(world_normal).normalized()
                    rot_angle = up.angle(world_normal)
                    from mathutils import Matrix
                    align_mat = Matrix.Rotation(rot_angle, 4, rot_axis)
                    root.rotation_euler = align_mat.to_euler()
                    # Re-apply the desired Z rotation on top
                    root.rotation_euler.z += rotation_z
        except Exception as exc:  # noqa: BLE001
            logger.warning("Terrain alignment failed for prop at %s: %s", pos, exc)

    # --- Parenting ---
    if parent is not None:
        root.parent = parent
        for obj in imported:
            if obj != root:
                obj.parent = root

    # --- Collection organisation ---
    if settlement_name:
        district = ring_for_position(
            (pos.x, pos.y), center, radius,
        )
        prop_col = _get_or_create_prop_collection(settlement_name, district)
        for obj in imported:
            # Link to prop collection, unlink from default scene collection
            if obj.name not in prop_col.objects:
                prop_col.objects.link(obj)
            for col in list(obj.users_collection):
                if col != prop_col:
                    col.objects.unlink(obj)

    logger.info(
        "Materialized prop %s at (%.1f, %.1f, %.1f)",
        prop_spec.get("prop_type", "unknown"),
        root.location.x,
        root.location.y,
        root.location.z,
    )
    return root


def handle_generate_settlement(params: dict) -> dict:
    """Generate a full settlement with geometry-rich roads, props, and lighting."""
    name = params.get("name", "Settlement")
    settlement_type = params.get("settlement_type", "town")
    seed = params.get("seed", 0)
    center = tuple(params.get("center", (0.0, 0.0)))
    radius = float(params.get("radius", 50.0))
    wall_height = float(params.get("wall_height", 3.0))
    terrain_name = params.get("terrain_name")
    include_buildings = params.get("include_buildings", True)
    include_roads = params.get("include_roads", True)
    include_props = params.get("include_props", True)
    include_perimeter = params.get("include_perimeter", True)
    include_interiors = params.get("include_interiors", True)
    include_lights = params.get("include_lights", True)
    parent_name = params.get("parent_name")
    layout_brief = str(params.get("layout_brief", ""))

    heightmap = None
    if terrain_name:
        heightmap = lambda x, y: _sample_scene_height(x, y, terrain_name)  # noqa: E731

    settlement = generate_settlement(
        settlement_type=settlement_type,
        seed=seed,
        center=center,
        radius=radius,
        heightmap=heightmap,
        wall_height=wall_height,
        layout_brief=layout_brief,
    )

    parent = bpy.data.objects.get(parent_name) if parent_name else None
    if parent is None:
        parent = bpy.data.objects.new(name, None)
        parent.empty_display_type = "PLAIN_AXES"
        parent.empty_display_size = max(radius, 1.0) * 0.25
        bpy.context.collection.objects.link(parent)

    building_lookup = {
        index: bld for index, bld in enumerate(settlement.get("buildings", []))
    }

    road_count = 0
    if include_roads:
        road_seed = random.Random(seed + 73)
        for i, road in enumerate(settlement.get("roads", [])):
            start = road.get("start")
            end = road.get("end")
            if not start or not end:
                continue
            road_width = float(road.get("width", 2.0))
            road_style = road.get("style", "")

            # Wide roads (cobblestone/stone, main roads, alleys >= 3m) get
            # mesh geometry with raised curbs.  Narrow trails keep the
            # lightweight curve-path representation.
            use_curbs = (
                road_style in ("cobblestone", "stone")
                or road.get("is_main_road")
                or road_width >= 3.0
            )

            if use_curbs:
                road_obj = _create_road_with_curbs(
                    road, terrain_name, parent, name, i,
                )
                if road_obj is not None:
                    road_count += 1
                    continue

            # Fallback: curve-path for narrow trails / dirt paths
            sx, sy = start
            ex, ey = end
            mid_x = (sx + ex) / 2.0
            mid_y = (sy + ey) / 2.0
            dx = ex - sx
            dy = ey - sy
            length = math.sqrt(dx * dx + dy * dy) or 1.0
            bend = min(radius * 0.12, length * 0.12)
            mid_x += road_seed.uniform(-bend, bend) * (-dy / length)
            mid_y += road_seed.uniform(-bend, bend) * (dx / length)
            road_z0 = _sample_scene_height(sx, sy, terrain_name) + 0.02
            road_z1 = _sample_scene_height(mid_x, mid_y, terrain_name) + 0.03
            road_z2 = _sample_scene_height(ex, ey, terrain_name) + 0.02
            road_obj = _create_curve_path(
                f"{name}_road_{i}",
                [
                    (sx, sy, road_z0),
                    (mid_x, mid_y, road_z1),
                    (ex, ey, road_z2),
                ],
                width=road_width,
                parent=parent,
            )
            _clear_material_slots(road_obj, context=f"settlement road {i}")
            road_count += 1

        # Create intersection patches where roads meet
        for j, isect in enumerate(settlement.get("intersections", [])):
            isect_pos = isect.get("position")
            if not isect_pos:
                continue
            # Size based on widest road width in settlement, fallback 4m
            all_widths = [
                float(r.get("width", 2.0)) for r in settlement.get("roads", [])
            ]
            isect_size = max(all_widths) * 1.5 if all_widths else 6.0
            _create_intersection_patch(
                position=isect_pos,
                size=isect_size,
                terrain_name=terrain_name,
                parent=parent,
                base_name=name,
                index=j,
            )

    building_count = 0
    if include_buildings:
        for i, building in enumerate(settlement.get("buildings", [])):
            b_type = building.get("type", "house")
            if b_type == "market_stall_cluster":
                spawned = _create_settlement_prop_cluster(name, building, i, parent)
                building_count += max(1, spawned)
                continue
            if b_type == "campfire_area":
                spawned = _create_settlement_prop_cluster(name, building, i, parent)
                building_count += max(1, spawned)
                continue
            if _generate_location_building(name, building, seed, i, terrain_name, parent):
                building_count += 1

    prop_count = 0
    if include_props:
        for i, prop in enumerate(settlement.get("props", [])):
            if _create_settlement_prop_cluster(name, prop, i, parent) > 0:
                prop_count += 1
                continue
            px, py = prop.get("position", (0.0, 0.0))[:2]
            pz = _sample_scene_height(px, py, terrain_name) + 0.02
            obj = _spawn_catalog_object(
                name,
                prop.get("type", "crate"),
                i,
                (px, py, pz),
                parent,
                rotation=float(prop.get("rotation", 0.0)),
                scale=_normalize_scale(prop.get("scale", (1.0, 1.0, 1.0))),
            )
            if obj is not None:
                prop_count += 1

    # --- Materialize Tripo AI props from manifest (Phase 36-02) ---
    prop_manifest = settlement.get("metadata", {}).get("prop_manifest", [])
    if prop_manifest and include_props:
        terrain_obj = bpy.data.objects.get(terrain_name) if terrain_name else None
        s_center = center if center else (0.0, 0.0)
        for prop_spec in prop_manifest:
            cache_key = prop_spec.get("cache_key")
            if isinstance(cache_key, (list, tuple)) and len(cache_key) == 2:
                cache_key = (str(cache_key[0]), str(cache_key[1]))
            else:
                continue
            glb_path = _PROP_CACHE.get(cache_key)
            if glb_path:
                result = _materialize_prop(
                    prop_spec,
                    glb_path,
                    terrain_obj,
                    parent,
                    settlement_name=name,
                    center=s_center,
                    radius=radius,
                )
                if result is not None:
                    prop_count += 1

    perimeter_count = 0
    if include_perimeter:
        for i, element in enumerate(settlement.get("perimeter", [])):
            px, py = element.get("position", (0.0, 0.0))[:2]
            pz = _sample_scene_height(px, py, terrain_name) + 0.02
            obj = _spawn_catalog_object(
                name,
                element.get("type", "wall_segment"),
                i,
                (px, py, pz),
                parent,
                rotation=float(element.get("rotation", 0.0)),
                scale=(1.0, 1.0, 1.0),
            )
            if obj is not None:
                perimeter_count += 1

    furniture_count = 0
    if include_interiors:
        for bld_index, furnishings in settlement.get("interiors", {}).items():
            building = building_lookup.get(int(bld_index))
            if building is None:
                continue
            base_z = float(building.get("elevation", 0.0))
            floor_height = float(building.get("floor_height", wall_height))
            for j, item in enumerate(furnishings):
                px, py = item.get("position", (0.0, 0.0))[:2]
                floor = int(item.get("floor", 0))
                pz = base_z + floor * floor_height + 0.05
                obj = _spawn_catalog_object(
                    name,
                    item.get("type", "crate"),
                    int(bld_index) * 1000 + j,
                    (px, py, pz),
                    parent,
                    rotation=float(item.get("rotation", 0.0)),
                    scale=(1.0, 1.0, 1.0),
                )
                if obj is not None:
                    furniture_count += 1

    light_count = 0
    if include_lights:
        for i, light_spec in enumerate(settlement.get("lights", [])):
            light_payload = dict(light_spec)
            light_count += 1 if _create_settlement_light(name, light_payload, i, parent) else 0

    parent["settlement_type"] = settlement_type
    parent["settlement_seed"] = seed
    parent["settlement_radius"] = radius

    return {
        "status": "success",
        "result": {
            "name": name,
            "settlement_type": settlement_type,
            "building_count": building_count,
            "road_count": road_count,
            "prop_count": prop_count,
            "perimeter_count": perimeter_count,
            "furniture_count": furniture_count,
            "light_count": light_count,
            "metadata": settlement.get("metadata", {}),
        },
    }


def handle_compose_world_map(params: dict) -> dict:
    """Compose a world map and materialize its road network and POIs."""
    name = params.get("name", "WorldMap")
    width = float(params.get("width", 2000.0))
    height = float(params.get("height", 2000.0))
    poi_list = params.get("poi_list", [])
    seed = params.get("seed", 0)
    shortcut_roads = params.get("shortcut_roads", 2)

    world_map = compose_world_map(
        width=width,
        height=height,
        poi_list=poi_list,
        seed=seed,
        shortcut_roads=shortcut_roads,
    )

    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.empty_display_size = max(width, height) * 0.05
    bpy.context.collection.objects.link(parent)

    road_count = 0
    for i, road in enumerate(world_map.get("roads", [])):
        waypoints = road.get("waypoints", [])
        if len(waypoints) < 2:
            continue
        points: list[tuple[float, float, float]] = []
        for pt in waypoints:
            if len(pt) >= 3:
                points.append((float(pt[0]), float(pt[1]), float(pt[2])))
            else:
                points.append((float(pt[0]), float(pt[1]), 0.02))
        _create_curve_path(
            f"{name}_road_{i}",
            points,
            width=3.2 if road.get("road_type") == "main" else 2.2 if road.get("road_type") == "shortcut" else 1.6,
            parent=parent,
        )
        road_obj = bpy.data.objects.get(f"{name}_road_{i}")
        if road_obj is not None:
            _assign_procedural_material(road_obj, "dirt")
        road_count += 1

    poi_count = 0
    for i, poi in enumerate(world_map.get("pois", [])):
        if _generate_location_poi(name, poi, seed, i, None, parent):
            poi_count += 1

    feature_count = 0
    feature_type_counts: dict[str, int] = {}
    for i, feature in enumerate(world_map.get("world_features", [])):
        feature_type = feature.get("type", "unknown")
        px, py = feature.get("position", (0.0, 0.0))[:2]
        pz = 0.0
        rotation = float(feature.get("rotation", 0.0))
        scale = feature.get("scale", (1.0, 1.0, 1.0))
        style = feature.get("style", "default")
        count = 0

        if feature_type == "farm_belt":
            count = _create_settlement_prop_cluster(
                name,
                {
                    "type": "farm_plot",
                    "position": (px, py, pz),
                    "rotation": rotation,
                    "scale": scale,
                },
                i,
                parent,
            )
        elif feature_type == "market_quarter":
            count = _create_settlement_prop_cluster(
                name,
                {
                    "type": "market_stall_cluster",
                    "position": (px, py, pz),
                    "rotation": rotation,
                    "scale": scale,
                },
                i,
                parent,
            )
        elif feature_type == "camp_perimeter":
            count = _create_settlement_prop_cluster(
                name,
                {
                    "type": "campfire_area",
                    "position": (px, py, pz),
                    "rotation": rotation,
                    "scale": scale,
                },
                i,
                parent,
            )
        elif feature_type == "bridge_crossing":
            bridge_obj = _create_bridge_span(
                f"{name}_feature_bridge_{i}",
                (px, py, pz + 0.15),
                span=max(8.0, float(scale[0]) * 8.0),
                bridge_width=max(2.0, float(scale[1]) * 2.0),
                parent=parent,
                style=style if style in {"stone", "rope"} else "stone",
            )
            if bridge_obj is not None:
                _assign_procedural_material(bridge_obj, "cliff_rock")
            count = 1
        elif feature_type == "fence_line":
            obj = _spawn_catalog_object(
                name,
                "fence",
                i,
                (px, py, pz),
                parent,
                rotation=rotation,
                scale=(max(3.0, float(scale[0]) * 6.0), 1.0, 1.0),
            )
            _assign_procedural_material(obj, "rough_timber")
            count = 1 if obj is not None else 0
        elif feature_type == "barricade_line":
            obj = _spawn_catalog_object(
                name,
                "barricade",
                i,
                (px, py, pz),
                parent,
                rotation=rotation,
                scale=(max(2.0, float(scale[0]) * 4.0), 1.0, 1.0),
            )
            _assign_procedural_material(obj, "charred_wood")
            count = 1 if obj is not None else 0
        elif feature_type == "lookout_post":
            obj = _spawn_catalog_object(
                name,
                "lookout_post",
                i,
                (px, py, pz),
                parent,
                rotation=rotation,
                scale=scale,
            )
            _assign_procedural_material(obj, "rough_timber")
            count = 1 if obj is not None else 0
        elif feature_type == "milestone":
            obj = _spawn_catalog_object(
                name,
                "milestone",
                i,
                (px, py, pz),
                parent,
                rotation=rotation,
                scale=(1.0, 1.0, 1.0),
            )
            _assign_procedural_material(obj, "smooth_stone")
            count = 1 if obj is not None else 0
        elif feature_type == "waystone":
            obj = _spawn_catalog_object(
                name,
                "waystone",
                i,
                (px, py, pz),
                parent,
                rotation=rotation,
                scale=scale,
            )
            _assign_procedural_material(obj, "smooth_stone")
            count = 1 if obj is not None else 0
        elif feature_type in {"sacrificial_circle", "corruption_crystal", "veil_tear", "dark_obelisk"}:
            obj = _spawn_catalog_object(
                name,
                feature_type,
                i,
                (px, py, pz),
                parent,
                rotation=rotation,
                scale=scale,
            )
            if feature_type == "sacrificial_circle":
                _assign_procedural_material(obj, "mossy_stone")
            elif feature_type == "corruption_crystal":
                _assign_procedural_material(obj, "ice_crystal")
            elif feature_type == "veil_tear":
                _assign_procedural_material(obj, "corruption_overlay")
            else:
                _assign_procedural_material(obj, "smooth_stone")
            count = 1 if obj is not None else 0

        if count > 0:
            feature_count += count
            feature_type_counts[feature_type] = feature_type_counts.get(feature_type, 0) + count

    parent["world_width"] = width
    parent["world_height"] = height
    parent["world_seed"] = seed

    return {
        "status": "success",
        "result": {
            "name": name,
            "road_count": road_count,
            "poi_count": poi_count,
            "feature_count": feature_count,
            "feature_type_counts": feature_type_counts,
            "metadata": world_map.get("metadata", {}),
        },
    }


def handle_generate_boss_arena(params: dict) -> dict:
    """Generate a boss arena with cover, hazards, and a fog gate (WORLD-03).

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

    cover_count_actual = 0
    for i, cover in enumerate(spec["covers"]):
        if _create_boss_arena_cover(name, cover, seed, i, parent):
            cover_count_actual += 1

    hazard_count_actual = 0
    for i, hz in enumerate(spec["hazard_zones"]):
        if _create_hazard_disc(name, hz, i, parent):
            hazard_count_actual += 1

    fog_gate_actual = False
    if spec["fog_gate"]:
        fog_gate_actual = _create_fog_gate(name, spec["fog_gate"], arena_type, parent)

    return {
        "status": "success",
        "result": {
            "name": name,
            "arena_type": arena_type,
            "diameter": diameter,
            "cover_count": cover_count_actual,
            "hazard_count": hazard_count_actual,
            "has_fog_gate": fog_gate_actual,
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
    """Generate interior with door trigger + occlusion zone geometry (WORLD-05).

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

    room_shell_count = 0
    for i, room in enumerate(rooms):
        bounds = room.get("bounds", {})
        r_min = bounds.get("min", (0.0, 0.0, 0.0))
        r_max = bounds.get("max", (4.0, 4.0, 3.0))
        origin = (float(r_min[0]), float(r_min[1]))
        shell_width = max(2.0, float(r_max[0] - r_min[0]))
        shell_depth = max(2.0, float(r_max[1] - r_min[1]))
        shell_height = max(2.8, float(r_max[2] - r_min[2]) if len(r_max) > 2 and len(r_min) > 2 else 3.0)
        room_name = room.get("name", f"room_{i}")
        room_shell_count += _create_interior_shell(
            f"{name}_{room_name}",
            shell_width,
            shell_depth,
            shell_height,
            parent,
            room.get("type", "tavern"),
            origin=origin,
            seed=42 + i,
        )

    door_geometry_count = 0
    for dt in spec["door_triggers"]:
        dt_obj = bpy.data.objects.new(f"{name}_{dt['id']}", None)
        dt_obj.empty_display_type = "ARROWS"
        dt_obj.empty_display_size = 1.0
        dt_obj.location = tuple(dt["position"])
        dt_obj.parent = parent
        bpy.context.collection.objects.link(dt_obj)

        door_width = dt.get("size", (1.2, 0.3, 2.2))[0]
        door_height = dt.get("size", (1.2, 0.3, 2.2))[2]
        facing = dt.get("facing", "south")
        door_mesh = generate_archway(
            width=door_width,
            height=door_height,
            depth=0.35,
            arch_style="gothic_pointed" if facing in {"north", "south"} else "round",
            has_keystone=True,
            seed=42,
        )
        door_geom = mesh_from_spec(
            door_mesh,
            name=f"{name}_{dt['id']}_frame",
            location=(dt["position"][0], dt["position"][1], dt["position"][2]),
            rotation=(0.0, 0.0, _facing_to_rotation(facing)),
            parent=parent,
        )
        if not isinstance(door_geom, dict):
            door_geometry_count += 1

    occlusion_geometry_count = 0
    for oz in spec["occlusion_zones"]:
        bmin = oz["bounds_min"]
        bmax = oz["bounds_max"]
        center = (
            (bmin[0] + bmax[0]) / 2,
            (bmin[1] + bmax[1]) / 2,
            0.0,
        )
        size = (
            max(0.5, bmax[0] - bmin[0]),
            max(0.5, bmax[1] - bmin[1]),
            2.4,
        )
        _create_volume_cube(f"{name}_{oz['id']}", center, size, parent)
        occlusion_geometry_count += 1

    lighting_transition_count = 0
    for lt in spec["lighting_transitions"]:
        lt_obj = bpy.data.objects.new(f"{name}_{lt['id']}", None)
        lt_obj.empty_display_type = "SPHERE"
        lt_obj.empty_display_size = 0.35
        lt_obj.location = tuple(lt["position"])
        lt_obj.parent = parent
        bpy.context.collection.objects.link(lt_obj)
        lighting_transition_count += 1

    return {
        "status": "success",
        "result": {
            "name": name,
            "room_shell_count": room_shell_count,
            "door_triggers": len(spec["door_triggers"]),
            "door_geometry_count": door_geometry_count,
            "occlusion_zones": len(spec["occlusion_zones"]),
            "occlusion_geometry_count": occlusion_geometry_count,
            "lighting_transitions": lighting_transition_count,
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

    # Connection geometry
    for i, conn in enumerate(dungeon.connections):
        if not _create_connection_geometry(name, conn, i, parent, cell_size, wall_height):
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


def handle_generate_encounter(params: dict) -> dict:
    """Generate an encounter space with validation-backed geometry."""
    name = params.get("name", "Encounter")
    template_name = params.get("template_name", params.get("template", "boss_chamber"))
    seed = params.get("seed", 42)
    enemy_count = params.get("enemy_count")
    if enemy_count is not None:
        enemy_count = int(enemy_count)

    layout = compute_encounter_layout(
        template_name=template_name,
        seed=seed,
        enemy_count=enemy_count,
    )
    validation = validate_encounter_layout(layout)
    if not validation.get("valid", False):
        raise ValueError(
            f"Encounter layout rejected for '{template_name}': "
            f"{validation.get('issues', [])}"
        )

    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(parent)

    floor = _create_floor_plate(
        f"{name}_floor",
        layout.get("bounds", {}),
        layout.get("shape", "square_room"),
        parent,
    )
    floor.location.z = float(layout.get("bounds", {}).get("min", (0.0, 0.0, 0.0))[2])

    cover_count = 0
    cover_palette = ["pillar", "rock", "barricade", "pillar"]
    for i, cover in enumerate(layout.get("cover", [])):
        px, py, pz = cover
        cover_type = cover_palette[i % len(cover_palette)]
        obj = _spawn_catalog_object(
            name,
            cover_type,
            i,
            (float(px), float(py), float(pz)),
            parent,
            rotation=0.0,
            scale=(1.0, 1.0, 1.0),
        )
        if obj is None:
            obj = _create_volume_cube(
                f"{name}_cover_{i}",
                center=(float(px), float(py), max(0.25, float(pz) + 0.25)),
                size=(1.2, 1.2, 1.2),
                parent=parent,
            )
        if obj is not None:
            cover_count += 1

    hazard_count = 0
    for i, hazard in enumerate(layout.get("hazards", [])):
        if _create_hazard_disc(name, hazard, i, parent):
            hazard_count += 1

    trigger_count = 0
    for i, trigger in enumerate(layout.get("triggers", [])):
        size = tuple(trigger.get("size", (3.0, 3.0, 3.0)))
        center = tuple(trigger.get("center", (0.0, 0.0, 0.0)))
        trigger_obj = _create_volume_cube(
            f"{name}_{trigger.get('type', 'trigger')}_{i}",
            center=center,
            size=size,
            parent=parent,
        )
        trigger_obj.display_type = "WIRE"
        trigger_count += 1

    prop_count = 0
    for i, prop in enumerate(layout.get("props", [])):
        prop_type = prop.get("type", "pillar")
        px, py, pz = prop.get("position", (0.0, 0.0, 0.0))
        size = prop.get("size", (1.0, 1.0, 1.0))
        rotation = float(prop.get("rotation", 0.0))

        if prop_type == "alcove":
            alcove = generate_archway(
                width=max(1.5, float(size[0])),
                height=max(1.8, float(size[2])),
                depth=max(0.8, float(size[1])),
                arch_style="gothic_pointed" if layout.get("shape") != "circular" else "round",
                has_keystone=True,
                seed=seed + i * 11,
            )
            obj = mesh_from_spec(
                alcove,
                name=f"{name}_alcove_{i}",
                location=(float(px), float(py), float(pz)),
                rotation=(0.0, 0.0, rotation),
                parent=parent,
            )
            if not isinstance(obj, dict):
                prop_count += 1
            continue

        if prop_type == "barricade":
            for detail_idx, detail_type in enumerate(("crate", "barrel", "crate")):
                detail = _spawn_catalog_object(
                    name,
                    detail_type,
                    i * 10 + detail_idx,
                    (
                        float(px) + math.cos(rotation + detail_idx) * 0.7,
                        float(py) + math.sin(rotation + detail_idx) * 0.7,
                        float(pz),
                    ),
                    parent,
                    rotation=rotation,
                    scale=(0.8, 0.8, 0.8),
                )
                if detail is not None:
                    prop_count += 1
            continue

        if prop_type == "archer_perch":
            perch = _create_volume_cube(
                f"{name}_archer_perch_{i}",
                center=(float(px), float(py), float(pz) + float(size[2]) * 0.5),
                size=(max(1.5, float(size[0])), max(1.5, float(size[1])), max(0.8, float(size[2]))),
                parent=parent,
            )
            perch.display_type = "BOUNDS"
            prop_count += 1
            continue

        obj = _spawn_catalog_object(
            name,
            prop_type,
            i,
            (float(px), float(py), float(pz)),
            parent,
            rotation=rotation,
            scale=tuple(size) if len(size) == 3 else (1.0, 1.0, 1.0),
        )
        if obj is not None:
            prop_count += 1

    enemy_count_actual = 0
    for i, enemy in enumerate(layout.get("enemies", [])):
        px, py, pz = enemy
        marker = _create_volume_cube(
            f"{name}_enemy_spawn_{i}",
            center=(float(px), float(py), float(pz) + 0.2),
            size=(0.5, 0.5, 0.5),
            parent=parent,
        )
        marker.display_type = "SPHERE"
        enemy_count_actual += 1

    entry = layout.get("entry")
    if entry:
        ex, ey, ez = entry
        entry_gate = generate_archway(
            width=max(2.5, float(layout.get("bounds", {}).get("radius", 4.0)) * 0.15),
            height=3.0,
            depth=0.9,
            arch_style="gothic_pointed" if layout.get("shape") != "circular" else "round",
            has_keystone=True,
            seed=seed + 100,
        )
        mesh_from_spec(
            entry_gate,
            name=f"{name}_entry_gate",
            location=(float(ex), float(ey), float(ez)),
            parent=parent,
        )

    exit_pt = layout.get("exit")
    if exit_pt:
        ex, ey, ez = exit_pt
        exit_gate = generate_archway(
            width=max(2.5, float(layout.get("bounds", {}).get("radius", 4.0)) * 0.15),
            height=3.0,
            depth=0.9,
            arch_style="gothic_pointed" if layout.get("shape") != "circular" else "round",
            has_keystone=True,
            seed=seed + 101,
        )
        mesh_from_spec(
            exit_gate,
            name=f"{name}_exit_gate",
            location=(float(ex), float(ey), float(ez)),
            parent=parent,
        )

    return {
        "status": "success",
        "result": {
            "name": name,
            "template": template_name,
            "validation": validation,
            "cover_count": cover_count,
            "hazard_count": hazard_count,
            "trigger_count": trigger_count,
            "prop_count": prop_count,
            "enemy_markers": enemy_count_actual,
        },
    }


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


# ---------------------------------------------------------------------------
# Prop prefetch handler (Phase 36-02, Task 2)
# ---------------------------------------------------------------------------


def handle_prefetch_settlement_props(params: dict) -> dict:
    """Pre-generate unique (prop_type, corruption_band) combinations via Tripo.

    Allows pre-warming the prop cache before a settlement generation session.
    Separates slow Tripo calls from fast Blender object placement.

    Params:
        prop_manifest : list of prop spec dicts (each has "cache_key": [type, band])
        veil_pressure : float 0.0-1.0 (default 0.0) -- used for logging context
        settlement_type : str (optional, for logging)

    Returns:
        {
            "prefetched": <total unique types>,
            "from_cache": <how many were already in cache>,
            "failed": <how many returned None>,
            "prop_types": [<list of "type/band" strings>],
        }
    """
    prop_manifest = params.get("prop_manifest", [])
    veil_pressure = float(params.get("veil_pressure", 0.0))

    resolved = prefetch_town_props(
        prop_manifest,
        veil_pressure=veil_pressure,
        blender_connection=None,  # Called from server context; Tripo uses its own session
    )

    failed = sum(1 for v in resolved.values() if v is None)
    from_cache = sum(1 for k in resolved if k in _PROP_CACHE and resolved[k] is not None)
    prop_types = [f"{t}/{b}" for t, b in resolved]

    return {
        "status": "success",
        "prefetched": len(resolved),
        "from_cache": from_cache,
        "failed": failed,
        "prop_types": prop_types,
    }
