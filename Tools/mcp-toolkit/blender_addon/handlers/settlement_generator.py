"""Settlement composition system for generating complete, unique locations.

Generates towns, camps, castles, villages, and outposts with:
- Unique building placement per seed
- Road networks connecting all structures
- Prop decoration (signs, crates, market stalls, etc.)
- Room function-based interior furnishing (multi-floor aware)
- Interior lighting placement per room type
- Terrain-aware foundation placement with heightmap support

Pure-logic data structures only -- NO bpy/bmesh imports.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable, Optional

from blender_addon.handlers._settlement_grammar import (
    assign_buildings_to_lots,
    generate_prop_manifest,
    generate_road_network_organic,
    ring_for_position,
    subdivide_block_to_lots,
)
from blender_addon.handlers._building_grammar import (
    generate_interior_layout,
    generate_clutter_layout,
    generate_lighting_layout,
)


# ---------------------------------------------------------------------------
# Settlement type configurations
# ---------------------------------------------------------------------------

SETTLEMENT_TYPES: dict[str, dict[str, Any]] = {
    "village": {
        "building_count": (4, 8),
        "has_walls": False,
        "has_market": False,
        "has_shrine": True,
        "road_style": "dirt_path",
        "building_types": [
            "abandoned_house", "abandoned_house", "forge", "shrine_minor",
        ],
        "prop_density": 0.3,
        "perimeter_props": ["fence", "signpost"],
        "layout_pattern": "organic",
    },
    "town": {
        "building_count": (8, 16),
        "has_walls": True,
        "has_market": True,
        "has_shrine": True,
        "road_style": "cobblestone",
        "building_types": [
            "abandoned_house", "forge", "shrine_major", "market_stall_cluster",
        ],
        "prop_density": 0.5,
        "perimeter_props": ["wall_segment", "gate", "watchtower"],
        "layout_pattern": "grid",
    },
    "bandit_camp": {
        "building_count": (3, 6),
        "has_walls": False,
        "has_market": False,
        "has_shrine": False,
        "road_style": "none",
        "building_types": ["tent", "lean_to", "campfire_area", "cage"],
        "prop_density": 0.6,
        "perimeter_props": ["barricade", "spike_fence", "lookout_post"],
        "layout_pattern": "circular",
    },
    "castle": {
        "building_count": (5, 10),
        "has_walls": True,
        "has_market": False,
        "has_shrine": True,
        "road_style": "stone",
        "building_types": [
            "ruined_fortress_tower", "shrine_minor", "forge", "barracks",
        ],
        "prop_density": 0.4,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
        "layout_pattern": "concentric",
    },
    "outpost": {
        "building_count": (2, 4),
        "has_walls": True,
        "has_market": False,
        "has_shrine": False,
        "road_style": "dirt_path",
        "building_types": ["watchtower", "barracks", "supply_tent"],
        "prop_density": 0.3,
        "perimeter_props": ["palisade", "gate"],
        "layout_pattern": "grid",
    },
    "traveler_camp": {
        "building_count": (2, 5),
        "has_walls": False,
        "has_market": False,
        "has_shrine": False,
        "road_style": "none",
        "building_types": ["tent", "lean_to", "campfire_area", "supply_tent"],
        "prop_density": 0.35,
        "perimeter_props": ["barricade", "lookout_post"],
        "layout_pattern": "circular",
    },
    "merchant_camp": {
        "building_count": (3, 7),
        "has_walls": False,
        "has_market": True,
        "has_shrine": False,
        "road_style": "dirt_path",
        "building_types": ["market_stall_cluster", "tent", "supply_tent", "watchtower"],
        "prop_density": 0.65,
        "perimeter_props": ["fence", "gate", "lookout_post"],
        "layout_pattern": "organic",
    },
    "wizard_fortress": {
        "building_count": (6, 12),
        "has_walls": True,
        "has_market": False,
        "has_shrine": True,
        "road_style": "stone",
        "building_types": [
            "wizard_fortress", "ruined_fortress_tower", "shrine_major", "barracks", "forge", "watchtower",
        ],
        "prop_density": 0.35,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
        "layout_pattern": "concentric",
    },
    "sorcery_school": {
        "building_count": (5, 10),
        "has_walls": True,
        "has_market": False,
        "has_shrine": True,
        "road_style": "stone",
        "building_types": [
            "sorcery_school", "shrine_major", "abandoned_house", "barracks", "watchtower", "market_stall_cluster",
        ],
        "prop_density": 0.45,
        "perimeter_props": ["wall_segment", "gate", "watchtower"],
        "layout_pattern": "grid",
    },
    "cliff_keep": {
        "building_count": (4, 8),
        "has_walls": True,
        "has_market": False,
        "has_shrine": True,
        "road_style": "stone",
        "building_types": [
            "ruined_fortress_tower", "barracks", "watchtower", "shrine_minor",
        ],
        "prop_density": 0.3,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
        "layout_pattern": "concentric",
    },
    "ruined_town": {
        "building_count": (5, 10),
        "has_walls": False,
        "has_market": False,
        "has_shrine": True,
        "road_style": "dirt_path",
        "building_types": [
            "abandoned_house", "abandoned_house", "forge", "shrine_minor", "ruined_fortress_tower",
        ],
        "prop_density": 0.55,
        "perimeter_props": ["fence", "signpost"],
        "layout_pattern": "organic",
    },
    "farmstead": {
        "building_count": (3, 6),
        "has_walls": False,
        "has_market": False,
        "has_shrine": False,
        "road_style": "dirt_path",
        "building_types": ["abandoned_house", "forge", "shrine_minor", "market_stall_cluster"],
        "prop_density": 0.5,
        "perimeter_props": ["fence", "signpost"],
        "layout_pattern": "organic",
    },
    "medieval_town": {
        "building_count": (40, 80),
        "has_walls": True,
        "has_market": True,
        "has_shrine": True,
        "road_style": "cobblestone",
        "building_types": [
            "abandoned_house", "forge", "shrine_major", "market_stall_cluster",
            "barracks", "watchtower", "abandoned_house", "abandoned_house",
            "tavern", "blacksmith", "guild_hall", "manor",
        ],
        "prop_density": 0.6,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
        "layout_pattern": "concentric_organic",
        "default_radius": 150.0,
    },
    "city": {
        "building_count": (20, 40),
        "has_walls": True,
        "has_market": True,
        "has_shrine": True,
        "road_style": "cobblestone",
        "building_types": [
            "abandoned_house", "forge", "shrine_major", "market_stall_cluster",
            "barracks", "watchtower", "abandoned_house", "abandoned_house",
        ],
        "prop_density": 0.5,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
        "layout_pattern": "district",
    },
    "hearthvale": {
        "building_count": (14, 14),  # Exact -- no randomization
        "has_walls": True,
        "has_market": True,
        "has_shrine": True,
        "road_style": "cobblestone",
        "building_types": [
            "tavern",          # The Ember Hearth
            "blacksmith",      # Forge
            "temple",          # Shrine to the Old Gods
            "town_hall",       # Civic center
            "general_store",   # Merchant provisions
            "apothecary",      # Potions and remedies
            "bakery",          # Daily bread
            "house", "house", "house", "house", "house",  # 5 houses
            "guard_barracks",  # Town watch
        ],
        "prop_density": 0.7,
        "perimeter_props": ["wall_segment", "portcullis_gate", "corner_tower"],
        "layout_pattern": "concentric_organic",
        "default_radius": 65.0,
    },
}


# ---------------------------------------------------------------------------
# District types for city-scale generation
# ---------------------------------------------------------------------------

DISTRICT_TYPES: dict[str, dict[str, Any]] = {
    "market_quarter": {
        "building_types": ["market_stall_cluster", "abandoned_house", "forge"],
        "prop_density": 0.7,
    },
    "noble_quarter": {
        "building_types": ["abandoned_house", "shrine_major", "abandoned_house"],
        "prop_density": 0.4,
    },
    "slums": {
        "building_types": ["tent", "lean_to", "abandoned_house"],
        "prop_density": 0.8,
    },
    "temple_district": {
        "building_types": ["shrine_major", "shrine_minor", "abandoned_house"],
        "prop_density": 0.3,
    },
    "military_quarter": {
        "building_types": ["barracks", "forge", "watchtower"],
        "prop_density": 0.5,
    },
    "port_district": {
        "building_types": ["market_stall_cluster", "abandoned_house", "abandoned_house"],
        "prop_density": 0.6,
    },
}


# ---------------------------------------------------------------------------
# Layout brief interpretation
# ---------------------------------------------------------------------------

_LAYOUT_BRIEF_KEYWORDS: dict[str, set[str]] = {
    "waterfront_edge": {"harbor", "harbour", "port", "river", "canal", "dock", "docks", "bay", "coast", "coastal", "waterfront"},
    "terraced": {"cliff", "cliffs", "terraced", "terrace", "hill", "hillside", "mountain", "ridge", "slope", "stepped"},
    "axial": {"capital", "imperial", "planned", "avenue", "boulevard", "ceremonial", "processional", "broad", "formal"},
    "radial_spokes": {"radial", "spokes", "hub", "star", "citadel", "keep", "fortified", "fortress"},
    "organic": {"organic", "winding", "maze", "medieval", "ancient", "crowded", "dense", "labyrinth"},
}

_DISTRICT_BRIEF_KEYWORDS: dict[str, set[str]] = {
    "market_quarter": {"market", "trade", "merchant", "bazaar", "guild", "shop", "commerce"},
    "noble_quarter": {"noble", "palace", "manor", "court", "upper", "wealthy", "aristocrat"},
    "slums": {"slum", "poor", "crowded", "dense", "refugee", "shanty", "underclass"},
    "temple_district": {"temple", "cathedral", "shrine", "abbey", "monastery", "sacred", "pilgrim"},
    "military_quarter": {"military", "garrison", "barracks", "fortified", "watch", "guard", "arsenal"},
    "port_district": {"harbor", "harbour", "port", "dock", "docks", "ship", "river", "canal", "fishing"},
}


def _stable_text_seed(text: str) -> int:
    """Return a deterministic integer fingerprint for freeform text."""
    acc = 0
    for idx, ch in enumerate(text):
        acc = (acc + (idx + 1) * ord(ch)) % 2147483647
    return acc


def _axis_vector(axis: str) -> tuple[float, float]:
    """Return a unit-ish vector for a named settlement spine axis."""
    return {
        "x": (1.0, 0.0),
        "y": (0.0, 1.0),
        "diag_pos": (math.sqrt(0.5), math.sqrt(0.5)),
        "diag_neg": (math.sqrt(0.5), -math.sqrt(0.5)),
    }.get(axis, (1.0, 0.0))


def _choose_edge(rng: random.Random) -> str:
    return rng.choice(["north", "south", "east", "west"])


def _derive_settlement_profile(
    settlement_type: str,
    layout_brief: str,
    seed: int,
) -> dict[str, Any]:
    """Interpret a layout brief into spatial rules for settlement generation."""
    base_config = SETTLEMENT_TYPES[settlement_type]
    normalized = " ".join(layout_brief.lower().split())
    tokens = set(normalized.replace(",", " ").replace(".", " ").split()) if normalized else set()
    profile_rng = random.Random(seed + _stable_text_seed(normalized))

    pattern_scores: dict[str, int] = {}
    for pattern_name, keywords in _LAYOUT_BRIEF_KEYWORDS.items():
        score = len(tokens & keywords)
        if score:
            pattern_scores[pattern_name] = score

    default_pattern = str(base_config.get("layout_pattern", "organic"))
    pattern_override = default_pattern
    if pattern_scores:
        pattern_override = max(
            pattern_scores.items(),
            key=lambda item: (item[1], item[0]),
        )[0]

    axis_hint = "x"
    if {"northsouth", "vertical"} & tokens:
        axis_hint = "y"
    elif {"diagonal", "angled"} & tokens:
        axis_hint = profile_rng.choice(["diag_pos", "diag_neg"])
    elif {"river", "canal", "waterfront", "harbor", "harbour"} & tokens:
        axis_hint = profile_rng.choice(["x", "y"])
    elif {"avenue", "boulevard", "processional"} & tokens:
        axis_hint = "x"
    elif {"cliff", "ridge", "terraced", "slope"} & tokens:
        axis_hint = "y"

    if pattern_override == "waterfront_edge" and axis_hint not in {"x", "y"}:
        axis_hint = "x"

    district_priority: list[tuple[int, str]] = []
    for district_name, keywords in _DISTRICT_BRIEF_KEYWORDS.items():
        score = len(tokens & keywords)
        if district_name == "port_district" and pattern_override == "waterfront_edge":
            score += 3
        if district_name == "military_quarter" and pattern_override in {"axial", "radial_spokes"}:
            score += 1
        if district_name == "temple_district" and {"temple", "cathedral", "abbey"} & tokens:
            score += 2
        district_priority.append((score, district_name))

    ordered_districts = [
        district_name for score, district_name in sorted(
            district_priority,
            key=lambda item: (-item[0], item[1]),
        )
        if score > 0
    ]
    for district_name in DISTRICT_TYPES:
        if district_name not in ordered_districts:
            ordered_districts.append(district_name)

    district_layouts = {
        "market_quarter": "organic" if pattern_override in {"organic", "waterfront_edge"} else "grid",
        "noble_quarter": "axial" if pattern_override in {"axial", "radial_spokes"} else "grid",
        "slums": "organic",
        "temple_district": "concentric" if pattern_override in {"radial_spokes", "terraced"} else "axial",
        "military_quarter": "axial" if pattern_override != "organic" else "grid",
        "port_district": "waterfront_edge" if pattern_override == "waterfront_edge" else "organic",
    }

    water_edge = _choose_edge(profile_rng) if pattern_override == "waterfront_edge" else None
    spoke_count = max(3, min(7, 3 + (seed + _stable_text_seed(normalized)) % 5))
    terrace_count = max(2, min(5, 2 + (_stable_text_seed(normalized) % 4)))

    return {
        "brief": layout_brief,
        "signature": f"{pattern_override}:{axis_hint}:{_stable_text_seed(normalized) % 997}",
        "pattern": pattern_override,
        "main_axis": axis_hint,
        "water_edge": water_edge,
        "spoke_count": spoke_count,
        "terrace_count": terrace_count,
        "district_types": ordered_districts,
        "district_layouts": district_layouts,
        "density_bias": 0.12 if {"dense", "crowded", "packed"} & tokens else -0.08 if {"spacious", "broad", "open"} & tokens else 0.0,
    }

# ---------------------------------------------------------------------------
# Room function -> furniture mapping
# ---------------------------------------------------------------------------

ROOM_FURNISHINGS: dict[str, list[str]] = {
    "bedroom": ["bed_frame", "chest", "candelabra", "rug"],
    "kitchen": ["table", "chair", "barrel", "shelf", "cauldron"],
    "smithy": ["anvil", "forge_fire", "bellows", "weapon_rack", "quench_trough"],
    "study": ["shelf", "table", "chair", "candelabra", "rug"],
    "great_hall": ["table", "chair", "banner", "candelabra", "rug", "chandelier"],
    "shrine_room": ["altar", "candelabra", "prayer_mat", "offering_bowl"],
    "storage": ["barrel", "crate", "sack", "shelf"],
    "tavern": ["table", "chair", "chair", "barrel", "candelabra", "banner"],
    "prison": ["shackle", "chain", "cell_door_broken", "skull_pile"],
    "throne_room": [
        "bone_throne", "banner", "candelabra", "rug", "chandelier",
    ],
    "barracks": ["bed_frame", "weapon_rack", "chest", "barrel"],
    "market": ["market_stall", "crate", "sack", "basket", "signpost"],
    "guard_post": ["weapon_rack", "chair", "lantern", "barrel"],
}

# Building type -> default room functions
_BUILDING_ROOMS: dict[str, list[str]] = {
    "abandoned_house": ["bedroom", "kitchen", "storage"],
    "forge": ["smithy", "storage"],
    "shrine_minor": ["shrine_room"],
    "shrine_major": ["shrine_room", "storage"],
    "market_stall_cluster": ["market"],
    "tent": ["bedroom"],
    "lean_to": ["storage"],
    "campfire_area": [],
    "cage": ["prison"],
    "ruined_fortress_tower": ["guard_post", "storage"],
    "wizard_fortress": ["great_hall", "study", "guard_post", "storage"],
    "sorcery_school": ["study", "great_hall", "shrine_room", "storage"],
    "barracks": ["barracks", "barracks", "storage"],
    "watchtower": ["guard_post"],
    "supply_tent": ["storage"],
    # Hearthvale building types (Phase 38 -- MESH-13)
    "tavern": ["tavern", "tavern", "bedroom", "bedroom", "storage"],
    "blacksmith": ["smithy", "smithy", "storage"],
    "temple": ["shrine_room", "shrine_room", "storage"],
    "town_hall": ["great_hall", "great_hall", "study", "storage"],
    "general_store": ["market", "storage", "storage"],
    "apothecary": ["study", "storage"],
    "bakery": ["kitchen", "kitchen", "storage"],
    "house": ["bedroom", "kitchen", "storage"],
    "guard_barracks": ["barracks", "barracks", "guard_post", "storage"],
    "manor": ["great_hall", "bedroom", "bedroom", "study", "storage", "kitchen"],
    "guild_hall": ["great_hall", "study", "storage", "armory"],
}

# Furniture bounding boxes (width, depth) for collision checks
_FURNITURE_SIZES: dict[str, tuple[float, float]] = {
    "bed_frame": (1.0, 2.0),
    "chest": (0.8, 0.5),
    "candelabra": (0.3, 0.3),
    "rug": (1.5, 2.0),
    "table": (1.2, 0.8),
    "chair": (0.5, 0.5),
    "barrel": (0.5, 0.5),
    "shelf": (1.0, 0.4),
    "cauldron": (0.6, 0.6),
    "anvil": (0.7, 0.5),
    "forge_fire": (1.0, 1.0),
    "bellows": (0.4, 0.6),
    "weapon_rack": (1.2, 0.3),
    "quench_trough": (0.8, 0.5),
    "altar": (1.0, 0.6),
    "prayer_mat": (0.8, 1.2),
    "offering_bowl": (0.3, 0.3),
    "crate": (0.6, 0.6),
    "sack": (0.4, 0.4),
    "banner": (0.3, 0.1),
    "market_stall": (2.0, 1.2),
    "basket": (0.4, 0.4),
    "signpost": (0.3, 0.3),
    "shackle": (0.3, 0.3),
    "chain": (0.2, 0.2),
    "cell_door_broken": (1.0, 0.2),
    "skull_pile": (0.5, 0.5),
    "bone_throne": (1.2, 1.0),
    "chandelier": (0.8, 0.8),
    "lantern": (0.3, 0.3),
}

# Furniture placement rules: "wall" = against wall, "center" = in open area
_FURNITURE_PLACEMENT: dict[str, str] = {
    "bed_frame": "wall",
    "chest": "wall",
    "candelabra": "wall",
    "rug": "center",
    "table": "center",
    "chair": "center",
    "barrel": "wall",
    "shelf": "wall",
    "cauldron": "center",
    "anvil": "center",
    "forge_fire": "center",
    "bellows": "wall",
    "weapon_rack": "wall",
    "quench_trough": "wall",
    "altar": "center",
    "prayer_mat": "center",
    "offering_bowl": "center",
    "crate": "wall",
    "sack": "wall",
    "banner": "wall",
    "market_stall": "center",
    "basket": "wall",
    "signpost": "center",
    "shackle": "wall",
    "chain": "wall",
    "cell_door_broken": "wall",
    "skull_pile": "wall",
    "bone_throne": "center",
    "chandelier": "center",
    "lantern": "wall",
}

# Road-side decoration props (placed at intervals along roads)
_ROAD_PROPS: dict[str, list[str]] = {
    "cobblestone": ["lantern_post", "bench", "planter"],
    "dirt_path": ["torch_post", "milestone"],
    "stone": ["brazier", "banner_stand", "statue_small"],
    "none": [],
}

# Open-area scatter props
_SCATTER_PROPS: list[str] = [
    "rock_small", "rock_medium", "debris_pile", "dead_bush",
    "fallen_log", "mushroom_cluster", "bone_scatter",
]

# ---------------------------------------------------------------------------
# Narrative prop clusters -- thematic groupings placed near matching buildings
# ---------------------------------------------------------------------------

_NARRATIVE_CLUSTERS: dict[str, dict[str, Any]] = {
    "merchant_stall": {
        "anchor": "market_stall",
        "satellites": ["crate", "sack", "basket", "signpost"],
        "radius": 3.0,
        "satellite_count": (2, 4),
    },
    "campfire_scene": {
        "anchor": "campfire",
        "satellites": ["log_seat", "bedroll", "sack", "lantern"],
        "radius": 4.0,
        "satellite_count": (2, 5),
    },
    "battle_aftermath": {
        "anchor": "broken_weapon",
        "satellites": ["shield_fragment", "bone_pile", "crater", "banner_torn"],
        "radius": 5.0,
        "satellite_count": (3, 6),
    },
    "tavern_entrance": {
        "anchor": "barrel",
        "satellites": ["crate", "barrel", "lantern", "signpost"],
        "radius": 2.5,
        "satellite_count": (2, 4),
    },
    "shrine_offering": {
        "anchor": "altar",
        "satellites": ["candelabra", "offering_bowl", "prayer_mat", "flower"],
        "radius": 2.0,
        "satellite_count": (2, 3),
    },
}

# Building type -> which narrative clusters can spawn nearby
_BUILDING_CLUSTER_MAP: dict[str, list[str]] = {
    "market_stall_cluster": ["merchant_stall"],
    "campfire_area": ["campfire_scene"],
    "ruined_fortress_tower": ["battle_aftermath"],
    "abandoned_house": ["tavern_entrance", "battle_aftermath"],
    "forge": ["tavern_entrance"],
    "shrine_minor": ["shrine_offering"],
    "shrine_major": ["shrine_offering"],
    "barracks": ["battle_aftermath", "tavern_entrance"],
    "tent": ["campfire_scene"],
    "lean_to": ["campfire_scene"],
    "cage": ["battle_aftermath"],
    "watchtower": ["battle_aftermath"],
    "supply_tent": ["merchant_stall"],
}

# Building footprint sizes (width, depth)
_BUILDING_FOOTPRINTS: dict[str, tuple[float, float]] = {
    "abandoned_house": (8.0, 6.0),
    "forge": (7.0, 7.0),
    "shrine_minor": (5.0, 5.0),
    "shrine_major": (8.0, 8.0),
    "market_stall_cluster": (10.0, 6.0),
    "tent": (4.0, 4.0),
    "lean_to": (3.0, 3.0),
    "campfire_area": (5.0, 5.0),
    "cage": (3.0, 3.0),
    "ruined_fortress_tower": (6.0, 6.0),
    "wizard_fortress": (14.0, 14.0),
    "sorcery_school": (16.0, 12.0),
    "barracks": (10.0, 8.0),
    "watchtower": (4.0, 4.0),
    "supply_tent": (5.0, 5.0),
    # Hearthvale building types (Phase 38 -- MESH-13)
    "tavern": (12.0, 10.0),
    "blacksmith": (10.0, 8.0),
    "temple": (14.0, 12.0),
    "town_hall": (16.0, 12.0),
    "general_store": (9.0, 7.0),
    "apothecary": (8.0, 7.0),
    "bakery": (8.0, 7.0),
    "house": (8.0, 6.0),
    "guard_barracks": (14.0, 10.0),
    "manor": (14.0, 10.0),
    "guild_hall": (12.0, 10.0),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dist2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _aabb_overlaps(
    pos_a: tuple[float, float],
    size_a: tuple[float, float],
    pos_b: tuple[float, float],
    size_b: tuple[float, float],
    margin: float = 1.0,
) -> bool:
    """Check AABB overlap with margin between two axis-aligned rectangles.

    Each rectangle is defined by its center ``pos`` and (width, depth).
    """
    hw_a, hd_a = size_a[0] / 2.0 + margin, size_a[1] / 2.0 + margin
    hw_b, hd_b = size_b[0] / 2.0, size_b[1] / 2.0

    return (
        abs(pos_a[0] - pos_b[0]) < hw_a + hw_b
        and abs(pos_a[1] - pos_b[1]) < hd_a + hd_b
    )


def _angle_to(
    from_pt: tuple[float, float], to_pt: tuple[float, float]
) -> float:
    """Angle in radians from ``from_pt`` to ``to_pt``."""
    return math.atan2(to_pt[1] - from_pt[1], to_pt[0] - from_pt[0])


def _nearest_road_angle(
    pos: tuple[float, float],
    roads: list[dict[str, Any]],
    fallback_target: tuple[float, float],
) -> float:
    """CITY-002: Return angle to face the nearest road segment.

    Finds the closest point on any road segment to ``pos`` and returns the
    perpendicular angle (i.e. the building faces the road).  Falls back to
    facing ``fallback_target`` when no roads are available yet.
    """
    if not roads:
        return _angle_to(pos, fallback_target)

    best_dist = float("inf")
    best_angle = _angle_to(pos, fallback_target)

    for road in roads:
        sx, sy = road["start"]
        ex, ey = road["end"]
        # Closest point on segment to pos
        dx, dy = ex - sx, ey - sy
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-9:
            cp = (sx, sy)
        else:
            t = max(0.0, min(1.0, ((pos[0] - sx) * dx + (pos[1] - sy) * dy) / seg_len_sq))
            cp = (sx + t * dx, sy + t * dy)
        d = _dist2d(pos, cp)
        if d < best_dist:
            best_dist = d
            # Face toward road (perpendicular to road direction) — just face the closest point
            best_angle = _angle_to(pos, cp)

    return best_angle


def _road_curve_controls(
    start: tuple[float, float],
    end: tuple[float, float],
    rng: random.Random,
    curviness: float = 0.25,
) -> list[tuple[float, float]]:
    """CITY-001: Generate cubic Bezier control points for a smooth road curve.

    Returns [start, cp1, cp2, end] as a list of 4 (x, y) tuples.
    The control points are offset perpendicular to the road axis by a
    fraction of the road length to produce gentle organic curves.
    """
    mx = (start[0] + end[0]) / 2.0
    my = (start[1] + end[1]) / 2.0
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy) or 1.0
    # Perpendicular unit vector
    px, py = -dy / length, dx / length
    offset = length * curviness * rng.uniform(-1.0, 1.0)
    cp1 = (
        round(start[0] + dx * 0.33 + px * offset * 0.5, 2),
        round(start[1] + dy * 0.33 + py * offset * 0.5, 2),
    )
    cp2 = (
        round(mx + px * offset, 2),
        round(my + py * offset, 2),
    )
    return [start, cp1, cp2, end]


# ---------------------------------------------------------------------------
# Building placement
# ---------------------------------------------------------------------------

def _place_buildings(
    rng: random.Random,
    config: dict[str, Any],
    center: tuple[float, float],
    radius: float,
) -> list[dict[str, Any]]:
    """Place buildings in a layout pattern, avoiding overlaps.

    Each building gets:
    - position: (x, y) world coordinate
    - rotation: facing road/center in radians
    - type: building type string
    - unique_seed: per-building seed for variation
    - room_functions: list of room type strings
    - footprint: (width, depth) tuple

    Placement rules:
    - Shrine placed at center (concentric/grid) or near edge (organic)
    - Market placed at the largest road intersection area
    - Other buildings distributed via layout pattern

    Parameters
    ----------
    rng : random.Random
        Seeded RNG instance.
    config : dict
        Settlement configuration from SETTLEMENT_TYPES.
    center : tuple
        Settlement center (x, y).
    radius : float
        Maximum settlement radius.

    Returns
    -------
    list of dict
        Placed building specifications.
    """
    min_count, max_count = config["building_count"]
    count = rng.randint(min_count, max_count)
    building_types = config["building_types"]
    pattern = config.get("layout_pattern", "organic")
    has_shrine = config.get("has_shrine", False)
    has_market = config.get("has_market", False)
    main_axis = str(config.get("main_axis", "x"))
    axis_vec = _axis_vector(main_axis)
    perp_vec = (-axis_vec[1], axis_vec[0])
    water_edge = str(config.get("water_edge", "south"))
    spoke_count = int(config.get("spoke_count", max(3, min(6, count // 2 or 3))))
    terrace_count = int(config.get("terrace_count", 3))

    # CITY-003: Per-district density variation — different layout patterns use
    # different minimum gaps between buildings.
    _PATTERN_GAP: dict[str, float] = {
        "grid": 1.5,           # dense urban grid
        "organic": 2.5,        # natural scatter — more breathing room
        "circular": 2.0,       # moderate camp spacing
        "district": 1.5,       # city district — tight urban
        "radial_spokes": 2.0,
        "concentric": 2.0,
        "terraced": 1.8,
        "waterfront_edge": 2.0,
        "axial": 1.5,
    }
    _gap_margin = _PATTERN_GAP.get(pattern, 2.0)

    buildings: list[dict[str, Any]] = []
    occupied: list[tuple[tuple[float, float], tuple[float, float]]] = []
    # Roads are not yet built at placement time, but we maintain a growing
    # list of provisional road stubs so late-placed buildings can orient to them.
    _provisional_roads: list[dict[str, Any]] = []

    def _try_place(
        btype: str, target_pos: tuple[float, float]
    ) -> dict[str, Any] | None:
        fp = _BUILDING_FOOTPRINTS.get(btype, (6.0, 6.0))
        # CITY-003: use per-district gap margin instead of fixed 2.0 m
        for opos, osize in occupied:
            if _aabb_overlaps(target_pos, fp, opos, osize, margin=_gap_margin):
                return None
        # CITY-002: face nearest already-placed provisional road; fall back to center
        rotation = _nearest_road_angle(target_pos, _provisional_roads, center)
        # Look up floor count from building preset defaults
        _BUILDING_FLOORS = {
            "shrine_minor": 1, "shrine_major": 2, "ruined_fortress_tower": 3,
            "abandoned_house": 1, "forge": 1, "tent": 1, "lean_to": 1,
            "campfire_area": 1, "cage": 1, "watchtower": 2, "barracks": 2,
            "supply_tent": 1, "market_stall_cluster": 1,
            "wizard_fortress": 3, "sorcery_school": 2,
            # Hearthvale types
            "tavern": 2, "inn": 2, "blacksmith": 1, "temple": 2,
            "town_hall": 2, "general_store": 1, "apothecary": 1,
            "bakery": 1, "house": 1, "guard_barracks": 2,
            "manor": 2, "guild_hall": 2, "warehouse": 2,
            "gatehouse": 2, "rowhouse": 2,
        }
        building = {
            "position": (round(target_pos[0], 2), round(target_pos[1], 2)),
            "rotation": round(rotation, 4),
            "type": btype,
            "unique_seed": rng.randint(0, 2**31),
            "room_functions": list(
                _BUILDING_ROOMS.get(btype, ["storage"])
            ),
            "footprint": fp,
            "floors": _BUILDING_FLOORS.get(btype, 1),
        }
        occupied.append((target_pos, fp))
        return building

    # --- Priority placements ---

    # 1. Shrine at center or near edge
    if has_shrine:
        shrine_types = [
            t for t in building_types if "shrine" in t
        ]
        shrine_type = shrine_types[0] if shrine_types else "shrine_minor"
        if pattern in ("concentric", "grid"):
            shrine_pos = (center[0], center[1])
        else:
            angle = rng.uniform(0, 2 * math.pi)
            shrine_pos = (
                center[0] + math.cos(angle) * radius * 0.7,
                center[1] + math.sin(angle) * radius * 0.7,
            )
        placed = _try_place(shrine_type, shrine_pos)
        if placed:
            buildings.append(placed)
            count -= 1

    # 2. Market near center (offset slightly for crossroads feel)
    if has_market:
        market_types = [
            t for t in building_types if "market" in t
        ]
        market_type = market_types[0] if market_types else "market_stall_cluster"
        market_offset = rng.uniform(3.0, radius * 0.3)
        market_angle = rng.uniform(0, 2 * math.pi)
        market_pos = (
            center[0] + math.cos(market_angle) * market_offset,
            center[1] + math.sin(market_angle) * market_offset,
        )
        placed = _try_place(market_type, market_pos)
        if placed:
            buildings.append(placed)
            count -= 1

    # --- Remaining buildings by layout pattern ---
    # Filter building types to exclude already-placed priority types
    remaining_types = [
        t for t in building_types
        if "shrine" not in t and "market" not in t
    ]
    if not remaining_types:
        remaining_types = list(building_types)

    for i in range(count):
        btype = remaining_types[i % len(remaining_types)]
        placed_building = None

        for attempt in range(80):
            if pattern == "circular":
                # Circular: buildings arranged in a ring
                angle = (2 * math.pi * i / max(count, 1)) + rng.uniform(
                    -0.3, 0.3
                )
                dist = rng.uniform(radius * 0.3, radius * 0.75)
                px = center[0] + math.cos(angle) * dist
                py = center[1] + math.sin(angle) * dist

            elif pattern == "grid":
                # Grid: rough grid with jitter
                cols = max(1, int(math.ceil(math.sqrt(count))))
                row = i // cols
                col = i % cols
                spacing = (radius * 1.4) / max(cols, 1)
                base_x = center[0] - radius * 0.7 + col * spacing + spacing * 0.5
                base_y = center[1] - radius * 0.7 + row * spacing + spacing * 0.5
                px = base_x + rng.uniform(-spacing * 0.2, spacing * 0.2)
                py = base_y + rng.uniform(-spacing * 0.2, spacing * 0.2)

            elif pattern == "concentric":
                # Concentric: inner ring is important, outer ring is common
                ring = 0 if i < max(count // 3, 1) else 1
                ring_radius = radius * (0.3 if ring == 0 else 0.65)
                ring_count = max(count // 3, 1) if ring == 0 else count
                angle = (2 * math.pi * i / max(ring_count, 1)) + rng.uniform(
                    -0.4, 0.4
                )
                px = center[0] + math.cos(angle) * ring_radius
                py = center[1] + math.sin(angle) * ring_radius

            elif pattern == "axial":
                stride = max(1, int(math.ceil(count / 3)))
                lane = (i % 3) - 1
                t = (i // 3) / max(1, stride - 1) if stride > 1 else 0.5
                axial = (t - 0.5) * radius * 1.35
                lateral = lane * radius * 0.22
                px = center[0] + axis_vec[0] * axial + perp_vec[0] * lateral
                py = center[1] + axis_vec[1] * axial + perp_vec[1] * lateral
                px += rng.uniform(-radius * 0.06, radius * 0.06)
                py += rng.uniform(-radius * 0.06, radius * 0.06)

            elif pattern == "radial_spokes":
                spoke_idx = i % max(spoke_count, 1)
                ring_idx = i // max(spoke_count, 1)
                angle = (2 * math.pi * spoke_idx / max(spoke_count, 1)) + rng.uniform(-0.14, 0.14)
                dist = radius * min(0.82, 0.24 + ring_idx * 0.17 + rng.uniform(-0.03, 0.04))
                px = center[0] + math.cos(angle) * dist
                py = center[1] + math.sin(angle) * dist

            elif pattern == "terraced":
                level_count = max(2, terrace_count)
                level_idx = i % level_count
                row_idx = i // level_count
                level_offset = (level_idx - (level_count - 1) / 2.0) * radius * 0.22
                row_t = row_idx / max(1, math.ceil(count / level_count) - 1) if count > level_count else 0.5
                row_offset = (row_t - 0.5) * radius * 1.25
                px = center[0] + axis_vec[0] * row_offset + perp_vec[0] * level_offset
                py = center[1] + axis_vec[1] * row_offset + perp_vec[1] * level_offset
                px += rng.uniform(-radius * 0.05, radius * 0.05)
                py += rng.uniform(-radius * 0.05, radius * 0.05)

            elif pattern == "waterfront_edge":
                bands = max(2, min(4, int(math.ceil(count / 4))))
                band_idx = i % bands
                row_idx = i // bands
                band_t = band_idx / max(1, bands - 1) if bands > 1 else 0.5
                row_t = row_idx / max(1, math.ceil(count / bands) - 1) if count > bands else 0.5
                long_offset = (row_t - 0.5) * radius * 1.35
                shore_depth = radius * (0.18 + band_t * 0.5)
                if water_edge == "north":
                    px = center[0] + long_offset
                    py = center[1] - radius * 0.52 + shore_depth
                elif water_edge == "south":
                    px = center[0] + long_offset
                    py = center[1] + radius * 0.52 - shore_depth
                elif water_edge == "east":
                    px = center[0] - radius * 0.52 + shore_depth
                    py = center[1] + long_offset
                else:
                    px = center[0] + radius * 0.52 - shore_depth
                    py = center[1] + long_offset
                px += rng.uniform(-radius * 0.05, radius * 0.05)
                py += rng.uniform(-radius * 0.05, radius * 0.05)

            else:  # organic
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(radius * 0.15, radius * 0.8)
                px = center[0] + math.cos(angle) * dist
                py = center[1] + math.sin(angle) * dist

            candidate_pos = (px, py)
            result = _try_place(btype, candidate_pos)
            if result is not None:
                placed_building = result
                break

        if placed_building is not None:
            buildings.append(placed_building)

    return buildings


# ---------------------------------------------------------------------------
# Road network generation (MST + main road)
# ---------------------------------------------------------------------------

def _generate_roads(
    buildings: list[dict[str, Any]],
    center: tuple[float, float],
    road_style: str,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Generate road segments connecting all buildings via MST + loop roads.

    CITY-001: Each segment includes ``control_points`` (4-point cubic Bezier)
    for smooth organic curves instead of straight Bresenham lines.

    CITY-006: After MST, add loop-closure edges so the network has redundant
    paths (prevents pure tree topology).

    Also adds a main road from the settlement edge to the center.

    Each road segment:
    - start: (x, y)
    - end: (x, y)
    - control_points: list of 4 (x, y) tuples (Bezier curve)
    - width: float
    - style: road style string

    Parameters
    ----------
    buildings : list of dict
        Placed buildings with ``position`` keys.
    center : tuple
        Settlement center.
    road_style : str
        Road surface type (cobblestone, dirt_path, stone, none).
    seed : int
        RNG seed for curve control points.

    Returns
    -------
    list of dict
        Road segment specifications.
    """
    if road_style == "none" or len(buildings) < 2:
        return []

    rng = random.Random(seed)
    roads: list[dict[str, Any]] = []
    n = len(buildings)
    positions = [b["position"] for b in buildings]

    # Build distance matrix
    dist_matrix = [
        [_dist2d(positions[i], positions[j]) for j in range(n)]
        for i in range(n)
    ]

    # Prim's MST
    in_tree = [False] * n
    in_tree[0] = True
    mst_edges: list[tuple[int, int]] = []
    edge_set: set[tuple[int, int]] = set()

    for _ in range(n - 1):
        best_i, best_j, best_d = -1, -1, float("inf")
        for i in range(n):
            if not in_tree[i]:
                continue
            for j in range(n):
                if in_tree[j]:
                    continue
                if dist_matrix[i][j] < best_d:
                    best_i, best_j, best_d = i, j, dist_matrix[i][j]
        if best_j == -1:
            break
        mst_edges.append((best_i, best_j))
        edge_set.add((min(best_i, best_j), max(best_i, best_j)))
        in_tree[best_j] = True

    # Width based on style
    width_map = {
        "cobblestone": 3.0,
        "dirt_path": 2.0,
        "stone": 3.5,
    }
    base_width = width_map.get(road_style, 2.0)

    # CITY-001: emit MST edges with Bezier control points for smooth curves
    for i, j in mst_edges:
        cps = _road_curve_controls(positions[i], positions[j], rng)
        roads.append({
            "start": positions[i],
            "end": positions[j],
            "control_points": cps,
            "width": base_width,
            "style": road_style,
        })

    # CITY-006: add loop-closure roads — connect pairs within 1.5× the MST
    # average edge length that don't already have a direct edge.  This turns
    # the pure tree into a looped street network.
    if len(mst_edges) > 0:
        avg_mst_dist = sum(dist_matrix[i][j] for i, j in mst_edges) / len(mst_edges)
        loop_threshold = avg_mst_dist * 1.5
        for i in range(n):
            for j in range(i + 1, n):
                key = (i, j)
                if key in edge_set:
                    continue
                if dist_matrix[i][j] <= loop_threshold:
                    # Add with ~30% probability to avoid too many cross-streets
                    if rng.random() < 0.30:
                        edge_set.add(key)
                        cps = _road_curve_controls(positions[i], positions[j], rng, curviness=0.15)
                        roads.append({
                            "start": positions[i],
                            "end": positions[j],
                            "control_points": cps,
                            "width": base_width * 0.8,  # slightly narrower side streets
                            "style": road_style,
                            "is_loop_road": True,
                        })

    # Main road: from settlement edge toward center (closest building)
    closest_idx = min(range(n), key=lambda k: _dist2d(positions[k], center))
    farthest_idx = max(range(n), key=lambda k: _dist2d(positions[k], center))
    far_pos = positions[farthest_idx]
    edge_angle = _angle_to(center, far_pos)
    farthest_dist = _dist2d(center, far_pos)
    edge_point = (
        center[0] + math.cos(edge_angle) * (farthest_dist + 10.0),
        center[1] + math.sin(edge_angle) * (farthest_dist + 10.0),
    )
    main_start = (round(edge_point[0], 2), round(edge_point[1], 2))
    main_end = positions[closest_idx]
    cps = _road_curve_controls(main_start, main_end, rng, curviness=0.1)
    roads.append({
        "start": main_start,
        "end": main_end,
        "control_points": cps,
        "width": base_width + 1.0,
        "style": road_style,
        "is_main_road": True,
    })

    return roads


def _generate_alleys(
    buildings: list[dict[str, Any]],
    roads: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """CITY-004: Generate narrow alley segments between adjacent building plots.

    Alleys are placed between pairs of buildings that are close together but
    do not already have a road connecting them.  Each alley is narrower than
    a standard road and is flagged ``is_alley=True``.

    Returns
    -------
    list of dict
        Alley segment specifications (same schema as road segments).
    """
    alleys: list[dict[str, Any]] = []
    if len(buildings) < 2:
        return alleys

    # Build a set of already-connected building pairs (from roads)
    positions = [b["position"] for b in buildings]
    connected: set[tuple[int, int]] = set()
    for road in roads:
        s, e = road["start"], road["end"]
        for i, pi in enumerate(positions):
            if _dist2d(pi, s) < 0.5:
                for j, pj in enumerate(positions):
                    if i != j and _dist2d(pj, e) < 0.5:
                        connected.add((min(i, j), max(i, j)))

    # Alley gap threshold: buildings within 6 m of each other get an alley
    alley_threshold = 6.0
    for i in range(len(buildings)):
        for j in range(i + 1, len(buildings)):
            key = (i, j)
            if key in connected:
                continue
            d = _dist2d(positions[i], positions[j])
            if d <= alley_threshold:
                mid = (
                    (positions[i][0] + positions[j][0]) / 2.0,
                    (positions[i][1] + positions[j][1]) / 2.0,
                )
                cps = _road_curve_controls(positions[i], positions[j], rng, curviness=0.05)
                alleys.append({
                    "start": positions[i],
                    "end": positions[j],
                    "control_points": cps,
                    "width": 1.0,
                    "style": "dirt_path",
                    "is_alley": True,
                })

    return alleys


def _enforce_road_frontage(
    buildings: list[dict[str, Any]],
    roads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """CITY-005: Tag buildings with their nearest road and frontage distance.

    For each building, find the closest road segment and annotate the building
    dict with ``nearest_road_dist`` (metres) and ``has_road_frontage`` (bool,
    True when within 8 m of a road).  Buildings without frontage are flagged
    so the caller can reposition or warn.

    Returns the annotated buildings list (mutates in place and returns it).
    """
    for building in buildings:
        pos = building["position"]
        min_dist = float("inf")

        for road in roads:
            sx, sy = road["start"]
            ex, ey = road["end"]
            dx, dy = ex - sx, ey - sy
            seg_len_sq = dx * dx + dy * dy
            if seg_len_sq < 1e-9:
                cp = (sx, sy)
            else:
                t = max(0.0, min(1.0, ((pos[0] - sx) * dx + (pos[1] - sy) * dy) / seg_len_sq))
                cp = (sx + t * dx, sy + t * dy)
            d = _dist2d(pos, cp)
            if d < min_dist:
                min_dist = d

        building["nearest_road_dist"] = round(min_dist, 2)
        building["has_road_frontage"] = min_dist <= 8.0

    return buildings


# ---------------------------------------------------------------------------
# Prop scatter
# ---------------------------------------------------------------------------

def _scatter_settlement_props(
    rng: random.Random,
    buildings: list[dict[str, Any]],
    roads: list[dict[str, Any]],
    config: dict[str, Any],
    radius: float,
    center: tuple[float, float] = (0.0, 0.0),
) -> list[dict[str, Any]]:
    """Scatter decoration props throughout the settlement.

    Placement rules:
    - Road-side: lanterns/torches at regular intervals along roads
    - Building-adjacent: crates, barrels, signs near building doors
    - Open-area: random scatter of rocks, debris in remaining space

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    buildings : list of dict
        Placed buildings.
    roads : list of dict
        Road segments.
    config : dict
        Settlement configuration.
    radius : float
        Settlement radius.
    center : tuple
        Settlement center.

    Returns
    -------
    list of dict
        Prop placement specs with position, rotation, type, scale.
    """
    props: list[dict[str, Any]] = []
    prop_density = config.get("prop_density", 0.3)
    road_style = config.get("road_style", "none")

    # 1. Road-side props: place at regular intervals along each road
    road_prop_types = _ROAD_PROPS.get(road_style, [])
    if road_prop_types:
        interval = max(4.0, 8.0 * (1.0 - prop_density))
        for road in roads:
            sx, sy = road["start"]
            ex, ey = road["end"]
            length = _dist2d((sx, sy), (ex, ey))
            if length < 0.01:
                continue
            dx = (ex - sx) / length
            dy = (ey - sy) / length
            # Perpendicular offset for placing props beside the road
            perp_x, perp_y = -dy, dx
            offset_dist = road["width"] * 0.6

            num_props = max(1, int(length / interval))
            for k in range(num_props):
                t = (k + 0.5) / max(num_props, 1)
                px = sx + dx * length * t
                py = sy + dy * length * t
                # Alternate sides
                side = 1.0 if k % 2 == 0 else -1.0
                px += perp_x * offset_dist * side
                py += perp_y * offset_dist * side
                props.append({
                    "type": rng.choice(road_prop_types),
                    "position": (round(px, 2), round(py, 2)),
                    "rotation": round(
                        math.atan2(dy, dx) + math.pi / 2, 4
                    ),
                    "scale": round(rng.uniform(0.85, 1.15), 2),
                    "source": "road",
                })

    # 2. Narrative cluster props near matching buildings
    #    Each building type can trigger thematic clusters (anchor + satellites)
    #    placed near the building entrance.  Falls back to generic adjacent
    #    props when no cluster mapping exists.
    generic_building_props = ["crate", "barrel", "sack", "firewood_stack"]
    for bld in buildings:
        bx, by = bld["position"]
        rot = bld["rotation"]
        fp = bld.get("footprint", (6.0, 6.0))
        btype = bld.get("type", "")

        cluster_names = _BUILDING_CLUSTER_MAP.get(btype)
        if cluster_names:
            cluster_key = rng.choice(cluster_names)
            cluster_def = _NARRATIVE_CLUSTERS[cluster_key]

            # Place anchor prop in front of building
            anchor_out = fp[1] * 0.5 + rng.uniform(1.0, 2.5)
            anchor_px = bx + math.cos(rot) * anchor_out
            anchor_py = by + math.sin(rot) * anchor_out
            props.append({
                "type": cluster_def["anchor"],
                "position": (round(anchor_px, 2), round(anchor_py, 2)),
                "rotation": round(rot + math.pi, 4),
                "scale": round(rng.uniform(0.9, 1.1), 2),
                "source": "narrative_cluster",
                "cluster": cluster_key,
                "cluster_role": "anchor",
            })

            # Place satellite props around the anchor
            sat_min, sat_max = cluster_def["satellite_count"]
            num_satellites = rng.randint(sat_min, sat_max)
            cluster_radius = cluster_def["radius"]
            for _s in range(num_satellites):
                sat_angle = rng.uniform(0, 2 * math.pi)
                sat_dist = rng.uniform(cluster_radius * 0.3, cluster_radius)
                sat_px = anchor_px + math.cos(sat_angle) * sat_dist
                sat_py = anchor_py + math.sin(sat_angle) * sat_dist
                sat_type = rng.choice(cluster_def["satellites"])
                props.append({
                    "type": sat_type,
                    "position": (round(sat_px, 2), round(sat_py, 2)),
                    "rotation": round(rng.uniform(0, 2 * math.pi), 4),
                    "scale": round(rng.uniform(0.8, 1.2), 2),
                    "source": "narrative_cluster",
                    "cluster": cluster_key,
                    "cluster_role": "satellite",
                })
        else:
            # Fallback: generic building-adjacent props
            num_adj = rng.randint(1, max(1, int(3 * prop_density + 0.5)))
            for _j in range(num_adj):
                offset_along = rng.uniform(-fp[0] * 0.3, fp[0] * 0.3)
                offset_out = fp[1] * 0.5 + rng.uniform(0.5, 2.0)
                px = bx + math.cos(rot) * offset_out + math.sin(rot) * offset_along
                py = by + math.sin(rot) * offset_out - math.cos(rot) * offset_along
                props.append({
                    "type": rng.choice(generic_building_props),
                    "position": (round(px, 2), round(py, 2)),
                    "rotation": round(rng.uniform(0, 2 * math.pi), 4),
                    "scale": round(rng.uniform(0.8, 1.2), 2),
                    "source": "building_adjacent",
                })

    # 3. Open-area scatter: random debris/rocks in settlement area
    num_scatter = max(
        2, int(prop_density * radius * 0.8)
    )
    for _ in range(num_scatter):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(radius * 0.1, radius * 0.9)
        px = center[0] + math.cos(angle) * dist
        py = center[1] + math.sin(angle) * dist

        # Skip if too close to a building
        too_close = False
        for bld in buildings:
            if _dist2d((px, py), bld["position"]) < 4.0:
                too_close = True
                break
        if too_close:
            continue

        props.append({
            "type": rng.choice(_SCATTER_PROPS),
            "position": (round(px, 2), round(py, 2)),
            "rotation": round(rng.uniform(0, 2 * math.pi), 4),
            "scale": round(rng.uniform(0.6, 1.4), 2),
            "source": "scatter",
        })

    # 4. Farm-scape dressing: crop plots, fences, hay, and carts around the outskirts.
    if road_style in {"dirt_path", "cobblestone"} and config.get("layout_pattern") in {"organic", "grid"}:
        farm_count = 2 if road_style == "dirt_path" else 3
        for i in range(farm_count):
            angle = (2 * math.pi * i / max(farm_count, 1)) + rng.uniform(-0.35, 0.35)
            dist = rng.uniform(radius * 0.68, radius * 0.9)
            px = center[0] + math.cos(angle) * dist
            py = center[1] + math.sin(angle) * dist
            props.append({
                "type": "farm_plot",
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(angle + math.pi / 2.0, 4),
                "scale": round(rng.uniform(0.9, 1.4), 2),
                "source": "farmscape",
            })

    return props


# ---------------------------------------------------------------------------
# Interior furnishing
# ---------------------------------------------------------------------------

def _furnish_interior(
    rng: random.Random,
    room_type: str,
    room_bounds: dict[str, Any],
) -> list[dict[str, Any]]:
    """Place furniture in a room based on its function.

    Wall-aligned items are placed against the room perimeter;
    center items are placed in the open area.  Collision checks
    prevent overlapping furniture.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    room_type : str
        Room function key (bedroom, kitchen, smithy, ...).
    room_bounds : dict
        ``{"min": (x, y), "max": (x, y)}`` of the room.

    Returns
    -------
    list of dict
        Furniture placements with type, position, rotation.
    """
    furnishing_list = ROOM_FURNISHINGS.get(room_type, ["crate"])
    rx_min, ry_min = room_bounds["min"]
    rx_max, ry_max = room_bounds["max"]
    room_w = rx_max - rx_min
    room_d = ry_max - ry_min

    if room_w < 1.0 or room_d < 1.0:
        return []

    placed: list[dict[str, Any]] = []
    placed_positions: list[tuple[tuple[float, float], tuple[float, float]]] = []

    # Compute wall and center zones
    wall_margin = 0.5
    center_margin = room_w * 0.25

    for item_type in furnishing_list:
        item_size = _FURNITURE_SIZES.get(item_type, (0.5, 0.5))
        placement_rule = _FURNITURE_PLACEMENT.get(item_type, "wall")

        placed_item = None
        for attempt in range(30):
            if placement_rule == "wall":
                # Pick a random wall (N/S/E/W) and place along it
                wall = rng.choice(["north", "south", "east", "west"])
                if wall == "north":
                    px = rng.uniform(
                        rx_min + wall_margin + item_size[0] / 2,
                        rx_max - wall_margin - item_size[0] / 2,
                    )
                    py = ry_max - wall_margin - item_size[1] / 2
                    rot = 0.0
                elif wall == "south":
                    px = rng.uniform(
                        rx_min + wall_margin + item_size[0] / 2,
                        rx_max - wall_margin - item_size[0] / 2,
                    )
                    py = ry_min + wall_margin + item_size[1] / 2
                    rot = math.pi
                elif wall == "east":
                    px = rx_max - wall_margin - item_size[1] / 2
                    py = rng.uniform(
                        ry_min + wall_margin + item_size[0] / 2,
                        ry_max - wall_margin - item_size[0] / 2,
                    )
                    rot = math.pi / 2
                else:  # west
                    px = rx_min + wall_margin + item_size[1] / 2
                    py = rng.uniform(
                        ry_min + wall_margin + item_size[0] / 2,
                        ry_max - wall_margin - item_size[0] / 2,
                    )
                    rot = -math.pi / 2
            else:
                # Center placement — INT-004: face toward room center with variation
                px = rng.uniform(
                    rx_min + center_margin + item_size[0] / 2,
                    rx_max - center_margin - item_size[0] / 2,
                )
                py = rng.uniform(
                    ry_min + center_margin + item_size[1] / 2,
                    ry_max - center_margin - item_size[1] / 2,
                )
                cx = (rx_min + rx_max) / 2.0
                cy = (ry_min + ry_max) / 2.0
                rot = math.atan2(px - cx, py - cy) + rng.uniform(-0.3, 0.3)

            # Collision check
            overlaps = False
            for opos, osize in placed_positions:
                if _aabb_overlaps(
                    (px, py), item_size, opos, osize, margin=0.2
                ):
                    overlaps = True
                    break

            if not overlaps:
                placed_item = {
                    "type": item_type,
                    "position": (round(px, 2), round(py, 2)),
                    "rotation": round(rot, 4),
                }
                placed_positions.append(((px, py), item_size))
                break

        if placed_item is not None:
            placed.append(placed_item)

    return placed


# ---------------------------------------------------------------------------
# Interior lighting
# ---------------------------------------------------------------------------

# Room type -> light source definitions
# Each entry: list of (light_type_name, color_rgb, intensity, range, light_kind)
_ROOM_LIGHTS: dict[str, list[tuple[str, tuple[float, float, float], float, float, str]]] = {
    "bedroom": [
        ("candelabra_light", (1.0, 0.85, 0.6), 0.6, 5.0, "point"),
    ],
    "kitchen": [
        ("fireplace_light", (1.0, 0.6, 0.3), 1.2, 8.0, "point"),
        ("candle_light", (1.0, 0.9, 0.7), 0.3, 3.0, "point"),
    ],
    "smithy": [
        ("forge_light", (1.0, 0.5, 0.2), 2.0, 10.0, "point"),
    ],
    "shrine_room": [
        ("shrine_candle_1", (1.0, 0.9, 0.7), 0.3, 3.0, "point"),
        ("shrine_candle_2", (1.0, 0.9, 0.7), 0.3, 3.0, "point"),
        ("shrine_candle_3", (1.0, 0.85, 0.65), 0.25, 2.5, "point"),
        ("shrine_candle_4", (1.0, 0.85, 0.65), 0.25, 2.5, "point"),
    ],
    "storage": [
        ("lantern_light", (1.0, 0.9, 0.7), 0.4, 4.0, "point"),
    ],
    "tavern": [
        ("tavern_candelabra_1", (1.0, 0.85, 0.6), 0.8, 6.0, "point"),
        ("tavern_candelabra_2", (1.0, 0.85, 0.6), 0.8, 6.0, "point"),
    ],
    "prison": [
        ("torch_light", (1.0, 0.55, 0.2), 0.7, 5.0, "point"),
    ],
    "throne_room": [
        ("chandelier_light", (1.0, 0.85, 0.6), 1.5, 10.0, "point"),
        ("throne_candle_1", (1.0, 0.9, 0.7), 0.4, 4.0, "point"),
    ],
    "barracks": [
        ("barracks_lantern", (1.0, 0.9, 0.7), 0.5, 5.0, "point"),
    ],
    "market": [
        ("market_lantern", (1.0, 0.9, 0.7), 0.6, 6.0, "point"),
    ],
    "guard_post": [
        ("guard_torch", (1.0, 0.55, 0.2), 0.6, 5.0, "point"),
    ],
    "study": [
        ("desk_candle", (1.0, 0.9, 0.7), 0.6, 4.0, "point"),
        ("wall_sconce", (1.0, 0.55, 0.2), 0.4, 3.5, "point"),
    ],
    "great_hall": [
        ("chandelier_light", (1.0, 0.85, 0.6), 1.2, 10.0, "point"),
        ("wall_torch_1", (1.0, 0.55, 0.2), 0.5, 5.0, "point"),
        ("wall_torch_2", (1.0, 0.55, 0.2), 0.5, 5.0, "point"),
        ("fireplace_glow", (1.0, 0.4, 0.1), 0.8, 6.0, "point"),
    ],
    "manor": [
        ("chandelier_light", (1.0, 0.85, 0.6), 1.0, 8.0, "point"),
        ("wall_sconce", (1.0, 0.55, 0.2), 0.4, 4.0, "point"),
    ],
}


def _place_interior_lights(
    rng: random.Random,
    room_type: str,
    room_bounds: dict[str, Any],
    floor_index: int = 0,
    wall_height: float = 3.0,
) -> list[dict[str, Any]]:
    """Place light sources in a room based on its function.

    Each light has position (x, y, z), color, intensity, range, and type.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    room_type : str
        Room function key (bedroom, kitchen, smithy, ...).
    room_bounds : dict
        ``{"min": (x, y), "max": (x, y)}`` of the room.
    floor_index : int
        Floor number (0 = ground). Used to calculate Z height.
    wall_height : float
        Height of each floor/storey.

    Returns
    -------
    list of dict
        Light placements with type, position (x, y, z), color, intensity,
        range, light_type (point/spot).
    """
    light_defs = _ROOM_LIGHTS.get(room_type, [])
    if not light_defs:
        return []

    rx_min, ry_min = room_bounds["min"]
    rx_max, ry_max = room_bounds["max"]
    room_w = rx_max - rx_min
    room_d = ry_max - ry_min

    if room_w < 1.0 or room_d < 1.0:
        return []

    lights: list[dict[str, Any]] = []
    base_z = floor_index * wall_height
    # Place lights at ~80% of wall height (near ceiling)
    light_z = base_z + wall_height * 0.8

    cx = (rx_min + rx_max) / 2.0
    cy = (ry_min + ry_max) / 2.0

    for i, (name, color, intensity, light_range, light_kind) in enumerate(light_defs):
        # Distribute lights within the room
        if len(light_defs) == 1:
            px, py = cx, cy
        elif len(light_defs) == 2:
            # Two lights: offset from center along the longer axis
            offset = min(room_w, room_d) * 0.25
            px = cx + (offset if i == 0 else -offset)
            py = cy + (offset if i == 1 else -offset)
        else:
            # Multiple lights: distribute in a ring around center
            angle = (2.0 * math.pi * i) / len(light_defs)
            radius = min(room_w, room_d) * 0.3
            px = cx + math.cos(angle) * radius
            py = cy + math.sin(angle) * radius

        # Add slight randomization
        px += rng.uniform(-0.3, 0.3)
        py += rng.uniform(-0.3, 0.3)

        # Clamp to room bounds
        px = max(rx_min + 0.3, min(px, rx_max - 0.3))
        py = max(ry_min + 0.3, min(py, ry_max - 0.3))

        lights.append({
            "type": name,
            "position": (round(px, 2), round(py, 2), round(light_z, 2)),
            "color": color,
            "intensity": round(intensity, 2),
            "range": round(light_range, 2),
            "light_type": light_kind,
            "floor": floor_index,
        })

    return lights


# ---------------------------------------------------------------------------
# Heightmap sampling
# ---------------------------------------------------------------------------

def _sample_heightmap(
    heightmap: Optional[Callable[[float, float], float]],
    x: float,
    y: float,
) -> float:
    """Sample a heightmap function at (x, y), returning 0.0 if no heightmap.

    Parameters
    ----------
    heightmap : callable or None
        Function (x, y) -> z elevation. None means flat terrain.
    x, y : float
        World-space coordinates.

    Returns
    -------
    float
        Elevation at (x, y).
    """
    if heightmap is None:
        return 0.0
    return heightmap(x, y)


def _compute_foundation_height(
    heightmap: Optional[Callable[[float, float], float]],
    position: tuple[float, float],
    footprint: tuple[float, float],
) -> float:
    """Compute foundation height needed to level a building on sloped terrain.

    Samples the heightmap at the four corners of the footprint and returns
    the height difference between the lowest and highest corner.

    Parameters
    ----------
    heightmap : callable or None
        Heightmap function.
    position : tuple
        Building center (x, y).
    footprint : tuple
        Building (width, depth).

    Returns
    -------
    float
        Foundation height needed (0.0 on flat terrain).
    """
    if heightmap is None:
        return 0.0
    bx, by = position
    hw, hd = footprint[0] / 2.0, footprint[1] / 2.0
    corners = [
        (bx - hw, by - hd),
        (bx + hw, by - hd),
        (bx - hw, by + hd),
        (bx + hw, by + hd),
    ]
    elevations = [heightmap(cx, cy) for cx, cy in corners]
    return max(elevations) - min(elevations)


def _rotate_point_2d(x: float, y: float, angle: float) -> tuple[float, float]:
    """Rotate a local-space 2D point around the origin."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _compute_foundation_profile(
    heightmap: Optional[Callable[[float, float], float]],
    position: tuple[float, float],
    footprint: tuple[float, float],
    *,
    rotation: float = 0.0,
    entrance_wall: str = "front",
) -> dict[str, Any]:
    """Compute a terrain fitment plan for a building footprint.

    The platform elevation is derived from the highest sampled point so the
    shell does not clip into sloped terrain. The returned profile is intended
    for downstream geometry generation: plinths, retaining walls, terraces,
    and entry steps.
    """
    bx, by = position
    width = max(0.1, float(footprint[0]))
    depth = max(0.1, float(footprint[1]))
    half_w = width * 0.5
    half_d = depth * 0.5

    if heightmap is None:
        zero_sides = {"front": 0.0, "back": 0.0, "left": 0.0, "right": 0.0}
        return {
            "platform_elevation": 0.0,
            "min_elevation": 0.0,
            "max_elevation": 0.0,
            "center_elevation": 0.0,
            "foundation_height": 0.0,
            "terrace_count": 1,
            "retaining_sides": [],
            "side_heights": zero_sides,
            "stair_wall": None,
            "stair_steps": 0,
            "dominant_slope_axis": "flat",
        }

    sample_offsets = {
        "front": (0.0, -half_d),
        "back": (0.0, half_d),
        "left": (-half_w, 0.0),
        "right": (half_w, 0.0),
        "front_left": (-half_w, -half_d),
        "front_right": (half_w, -half_d),
        "back_left": (-half_w, half_d),
        "back_right": (half_w, half_d),
        "center": (0.0, 0.0),
    }
    sampled: dict[str, float] = {}
    for key, (lx, ly) in sample_offsets.items():
        rx, ry = _rotate_point_2d(lx, ly, rotation)
        sampled[key] = float(heightmap(bx + rx, by + ry))

    min_elevation = min(sampled.values())
    max_elevation = max(sampled.values())
    center_elevation = sampled["center"]
    platform_elevation = max_elevation
    foundation_height = max(0.0, platform_elevation - min_elevation)

    edge_elevations = {
        "front": sampled["front"],
        "back": sampled["back"],
        "left": sampled["left"],
        "right": sampled["right"],
    }
    side_heights = {
        wall: round(max(0.0, platform_elevation - edge_height), 3)
        for wall, edge_height in edge_elevations.items()
    }
    retaining_sides = [
        wall for wall, drop in side_heights.items()
        if drop >= 0.45
    ]
    terrace_count = max(1, min(4, 1 + int(foundation_height / 1.2)))
    stair_drop = side_heights.get(entrance_wall, 0.0)
    stair_steps = int(math.ceil(stair_drop / 0.18)) if stair_drop >= 0.14 else 0

    slope_x = ((sampled["right"] + sampled["front_right"] + sampled["back_right"]) / 3.0) - (
        (sampled["left"] + sampled["front_left"] + sampled["back_left"]) / 3.0
    )
    slope_y = ((sampled["back"] + sampled["back_left"] + sampled["back_right"]) / 3.0) - (
        (sampled["front"] + sampled["front_left"] + sampled["front_right"]) / 3.0
    )
    if abs(slope_x) < 0.08 and abs(slope_y) < 0.08:
        dominant_axis = "flat"
    else:
        dominant_axis = "x" if abs(slope_x) >= abs(slope_y) else "y"

    return {
        "platform_elevation": round(platform_elevation, 3),
        "min_elevation": round(min_elevation, 3),
        "max_elevation": round(max_elevation, 3),
        "center_elevation": round(center_elevation, 3),
        "foundation_height": round(foundation_height, 3),
        "terrace_count": terrace_count,
        "retaining_sides": retaining_sides,
        "side_heights": side_heights,
        "stair_wall": entrance_wall if stair_steps > 0 else None,
        "stair_steps": stair_steps,
        "dominant_slope_axis": dominant_axis,
    }


# ---------------------------------------------------------------------------
# Building variation
# ---------------------------------------------------------------------------

def _apply_building_variation(
    rng: random.Random,
    building: dict[str, Any],
) -> dict[str, Any]:
    """Apply per-instance visual variation to a building.

    Randomizes:
    - wall_damage: 0-30% of wall surface showing damage
    - roof_condition: intact / damaged / missing
    - window_count: 0-4 windows
    - prop_additions: list of small detail props on/near the building
    - door_condition: intact / broken / missing

    Parameters
    ----------
    rng : random.Random
        Seeded with the building's unique_seed.
    building : dict
        Building spec to augment (not mutated; returns new dict).

    Returns
    -------
    dict
        Building spec with added ``variation`` key.
    """
    variation: dict[str, Any] = {}

    # Wall damage (0-30%)
    variation["wall_damage"] = round(rng.uniform(0.0, 0.3), 2)

    # Roof condition
    roof_roll = rng.random()
    if roof_roll < 0.5:
        variation["roof_condition"] = "intact"
    elif roof_roll < 0.8:
        variation["roof_condition"] = "damaged"
    else:
        variation["roof_condition"] = "missing"

    # Window count
    variation["window_count"] = rng.randint(0, 4)

    # Door condition
    door_roll = rng.random()
    if door_roll < 0.6:
        variation["door_condition"] = "intact"
    elif door_roll < 0.85:
        variation["door_condition"] = "broken"
    else:
        variation["door_condition"] = "missing"

    # Small detail props on the building
    detail_candidates = [
        "hanging_sign", "flower_box", "skull_mount",
        "lantern_hook", "ivy_patch", "cobweb", "moss_patch",
    ]
    num_details = rng.randint(0, 3)
    variation["prop_additions"] = rng.sample(
        detail_candidates, min(num_details, len(detail_candidates))
    )

    result = dict(building)
    result["variation"] = variation
    return result


# ---------------------------------------------------------------------------
# Perimeter walls / gates
# ---------------------------------------------------------------------------

def _generate_perimeter(
    rng: random.Random,
    config: dict[str, Any],
    center: tuple[float, float],
    radius: float,
) -> list[dict[str, Any]]:
    """Generate perimeter wall segments and gates.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    config : dict
        Settlement config.
    center : tuple
        Settlement center.
    radius : float
        Settlement radius.

    Returns
    -------
    list of dict
        Perimeter element specs (wall_segment, gate, tower, etc.).
    """
    if not config.get("has_walls", False):
        return []

    perimeter_types = config.get("perimeter_props", ["wall_segment", "gate"])
    elements: list[dict[str, Any]] = []

    # Wall segments around the circumference
    wall_radius = radius * 0.9
    segment_length = 6.0
    circumference = 2 * math.pi * wall_radius
    num_segments = max(4, int(circumference / segment_length))

    # Decide gate positions (1-2 gates)
    num_gates = rng.randint(1, 2)
    gate_indices: set[int] = set()
    gate_angle_step = num_segments / max(num_gates, 1)
    for g in range(num_gates):
        gate_indices.add(int(g * gate_angle_step) % num_segments)

    gate_types = [t for t in perimeter_types if "gate" in t]
    gate_type = gate_types[0] if gate_types else "gate"
    wall_types = [t for t in perimeter_types if "wall" in t]
    wall_type = wall_types[0] if wall_types else "wall_segment"
    tower_types = [t for t in perimeter_types if "tower" in t]
    tower_type = tower_types[0] if tower_types else None

    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        px = center[0] + math.cos(angle) * wall_radius
        py = center[1] + math.sin(angle) * wall_radius
        facing = angle + math.pi  # face inward

        if i in gate_indices:
            elements.append({
                "type": gate_type,
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_gate": True,
            })
        else:
            elements.append({
                "type": wall_type,
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_gate": False,
            })

        # Add towers at corners (every quarter)
        if tower_type and i % max(1, num_segments // 4) == 0 and i not in gate_indices:
            elements.append({
                "type": tower_type,
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_tower": True,
            })

    return elements


# ---------------------------------------------------------------------------
# City district generation (Voronoi-like subdivision)
# ---------------------------------------------------------------------------

def _voronoi_assign(
    px: float,
    py: float,
    seeds: list[tuple[float, float]],
) -> int:
    """Return the index of the nearest seed point (Voronoi cell assignment)."""
    best_idx = 0
    best_d2 = float("inf")
    for i, (sx, sy) in enumerate(seeds):
        d2 = (px - sx) ** 2 + (py - sy) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_idx = i
    return best_idx


def generate_city_districts(
    city_width: float,
    city_depth: float,
    num_districts: int = 4,
    seed: int = 42,
    city_profile: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Generate a city layout partitioned into districts via Voronoi subdivision.

    Each district receives its own building placements, a local road grid,
    and connects to a central main thoroughfare that runs through the city.
    City walls with gates are placed at main road entry points.

    Parameters
    ----------
    city_width : float
        Total width of the city area.
    city_depth : float
        Total depth of the city area.
    num_districts : int
        Number of districts to generate (clamped to 2-8).
    seed : int
        Random seed for deterministic generation.

    Returns
    -------
    dict
        ``{"districts": [...], "main_road": dict, "walls": [...],
        "gates": [...], "metadata": {...}}``

        Each district: ``{"district_type": str, "bounds": dict,
        "center": (x, y), "buildings": [...], "roads": [...],
        "prop_density": float}``
    """
    rng = random.Random(seed)
    num_districts = max(2, min(num_districts, 8))
    city_profile = city_profile or {}

    district_type_names = list(city_profile.get("district_types") or DISTRICT_TYPES.keys())
    half_w = city_width / 2.0
    half_d = city_depth / 2.0
    margin = min(city_width, city_depth) * 0.1
    main_axis = str(city_profile.get("main_axis", "x"))
    water_edge = city_profile.get("water_edge")

    # --- Generate Voronoi seed points within the city bounds ---
    district_seeds: list[tuple[float, float]] = []
    assigned_types_preview: list[str] = []
    for i in range(num_districts):
        assigned_types_preview.append(district_type_names[i % len(district_type_names)])
    rng.shuffle(assigned_types_preview)

    for i in range(num_districts):
        dtype = assigned_types_preview[i]
        sx = rng.uniform(-half_w + margin, half_w - margin)
        sy = rng.uniform(-half_d + margin, half_d - margin)
        if dtype == "port_district" and water_edge:
            if water_edge == "north":
                sy = -half_d + margin * 1.25
            elif water_edge == "south":
                sy = half_d - margin * 1.25
            elif water_edge == "east":
                sx = half_w - margin * 1.25
            else:
                sx = -half_w + margin * 1.25
        elif dtype == "temple_district":
            sx *= 0.35
            sy *= 0.35
        elif dtype == "military_quarter":
            axis = _axis_vector(main_axis)
            sx = axis[0] * (half_w - margin * 1.1) * 0.55 + rng.uniform(-margin, margin)
            sy = axis[1] * (half_d - margin * 1.1) * 0.55 + rng.uniform(-margin, margin)
        elif dtype == "slums":
            sx *= 0.85
            sy *= 0.85
        district_seeds.append((sx, sy))

    # --- Assign district types (seeded random) ---
    assigned_types = assigned_types_preview

    # --- Compute district bounds via grid sampling ---
    # Sample a grid and assign each cell to its nearest district seed.
    # Then compute the AABB of each district from its cells.
    grid_res = 40  # resolution of the sampling grid
    cell_w = city_width / grid_res
    cell_d = city_depth / grid_res

    # Track cells per district for bounds computation
    district_cells: list[list[tuple[float, float]]] = [[] for _ in range(num_districts)]

    for gx in range(grid_res):
        for gy in range(grid_res):
            cx = -half_w + (gx + 0.5) * cell_w
            cy = -half_d + (gy + 0.5) * cell_d
            owner = _voronoi_assign(cx, cy, district_seeds)
            district_cells[owner].append((cx, cy))

    # --- Build district specs ---
    districts: list[dict[str, Any]] = []
    all_district_buildings: list[dict[str, Any]] = []
    all_district_roads: list[dict[str, Any]] = []

    for di in range(num_districts):
        cells = district_cells[di]
        if not cells:
            continue

        dtype = assigned_types[di]
        dconfig = DISTRICT_TYPES[dtype]

        # Compute AABB from owned cells
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        bounds_min = (min(xs), min(ys))
        bounds_max = (max(xs), max(ys))
        d_center = district_seeds[di]

        d_width = bounds_max[0] - bounds_min[0]
        d_depth = bounds_max[1] - bounds_min[1]
        d_radius = min(d_width, d_depth) / 2.0 * 0.85

        # Determine building count proportional to district area
        total_area = city_width * city_depth
        district_area = d_width * d_depth
        area_ratio = district_area / max(total_area, 1.0)
        # City has 20-40 buildings; distribute proportionally
        base_count = max(2, int(area_ratio * 30 + 0.5))

        # Place buildings within the district
        district_config = {
            "building_count": (base_count, base_count),
            "has_walls": False,
            "has_market": dtype == "market_quarter",
            "has_shrine": dtype == "temple_district",
            "road_style": "cobblestone",
            "building_types": dconfig["building_types"],
            "prop_density": dconfig["prop_density"],
            "perimeter_props": [],
            "layout_pattern": city_profile.get("district_layouts", {}).get(dtype, "grid"),
            "main_axis": main_axis,
            "water_edge": water_edge,
            "spoke_count": int(city_profile.get("spoke_count", 4)),
            "terrace_count": int(city_profile.get("terrace_count", 3)),
        }

        district_rng = random.Random(seed + di * 7919)
        buildings = _place_buildings(
            district_rng, district_config, d_center, d_radius,
        )

        # Generate local road grid within the district
        roads = _generate_roads(
            buildings, d_center, district_config["road_style"],
            seed=seed + di * 7919,
        )
        # CITY-004: add alleys between tightly-packed plots
        alleys = _generate_alleys(buildings, roads, district_rng)
        roads = roads + alleys
        # CITY-005: annotate buildings with road frontage info
        _enforce_road_frontage(buildings, roads)

        district_spec = {
            "district_type": dtype,
            "bounds": {"min": bounds_min, "max": bounds_max},
            "center": (round(d_center[0], 2), round(d_center[1], 2)),
            "buildings": buildings,
            "roads": roads,
            "building_count": len(buildings),
            "prop_density": dconfig["prop_density"],
        }
        districts.append(district_spec)
        all_district_buildings.extend(buildings)
        all_district_roads.extend(roads)

    # --- Main thoroughfare: a road running through the city center ---
    # Connects the leftmost and rightmost district centers
    if main_axis == "y":
        sorted_by_axis = sorted(districts, key=lambda d: d["center"][1])
        main_road_start = (
            sorted_by_axis[0]["center"][0],
            sorted_by_axis[0]["center"][1] - margin,
        )
        main_road_end = (
            sorted_by_axis[-1]["center"][0],
            sorted_by_axis[-1]["center"][1] + margin,
        )
    elif main_axis == "diag_pos":
        sorted_by_axis = sorted(districts, key=lambda d: d["center"][0] + d["center"][1])
        main_road_start = (
            sorted_by_axis[0]["center"][0] - margin * 0.7,
            sorted_by_axis[0]["center"][1] - margin * 0.7,
        )
        main_road_end = (
            sorted_by_axis[-1]["center"][0] + margin * 0.7,
            sorted_by_axis[-1]["center"][1] + margin * 0.7,
        )
    elif main_axis == "diag_neg":
        sorted_by_axis = sorted(districts, key=lambda d: d["center"][0] - d["center"][1])
        main_road_start = (
            sorted_by_axis[0]["center"][0] - margin * 0.7,
            sorted_by_axis[0]["center"][1] + margin * 0.7,
        )
        main_road_end = (
            sorted_by_axis[-1]["center"][0] + margin * 0.7,
            sorted_by_axis[-1]["center"][1] - margin * 0.7,
        )
    else:
        sorted_by_axis = sorted(districts, key=lambda d: d["center"][0])
        main_road_start = (
            sorted_by_axis[0]["center"][0] - margin,
            sorted_by_axis[0]["center"][1],
        )
        main_road_end = (
            sorted_by_axis[-1]["center"][0] + margin,
            sorted_by_axis[-1]["center"][1],
        )
    main_road = {
        "start": (round(main_road_start[0], 2), round(main_road_start[1], 2)),
        "end": (round(main_road_end[0], 2), round(main_road_end[1], 2)),
        "width": 5.0,
        "style": "cobblestone",
        "is_main_road": True,
        "axis": main_axis,
    }

    # Connect each district center to the main thoroughfare
    connector_roads: list[dict[str, Any]] = []
    line_dx = main_road_end[0] - main_road_start[0]
    line_dy = main_road_end[1] - main_road_start[1]
    line_len_sq = max(line_dx * line_dx + line_dy * line_dy, 1.0)
    for dist in districts:
        dcx, dcy = dist["center"]
        # Project district center onto the main road line segment.
        t = (
            ((dcx - main_road_start[0]) * line_dx) + ((dcy - main_road_start[1]) * line_dy)
        ) / line_len_sq
        t = max(0.0, min(1.0, t))
        mx = main_road_start[0] + line_dx * t
        my = main_road_start[1] + line_dy * t
        connector_roads.append({
            "start": (round(dcx, 2), round(dcy, 2)),
            "end": (round(mx, 2), round(my, 2)),
            "width": 3.5,
            "style": "cobblestone",
            "is_connector": True,
        })

    # --- City walls with gates at main road entry points ---
    wall_radius = max(city_width, city_depth) / 2.0 * 0.95
    city_center = (0.0, 0.0)
    segment_length = 6.0
    circumference = 2 * math.pi * wall_radius
    num_segments = max(8, int(circumference / segment_length))

    # Gate positions: where the main road exits the city
    gate_angles: list[float] = []
    for pt in [main_road_start, main_road_end]:
        gate_angles.append(math.atan2(pt[1] - city_center[1], pt[0] - city_center[0]))

    walls: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []

    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        px = city_center[0] + math.cos(angle) * wall_radius
        py = city_center[1] + math.sin(angle) * wall_radius
        facing = angle + math.pi

        # Check if this segment is near a gate angle
        is_gate = False
        for ga in gate_angles:
            angle_diff = abs(((angle - ga + math.pi) % (2 * math.pi)) - math.pi)
            if angle_diff < (2 * math.pi / num_segments) * 1.2:
                is_gate = True
                break

        if is_gate:
            gates.append({
                "type": "gate_large",
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_gate": True,
            })
        else:
            walls.append({
                "type": "wall_segment",
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_gate": False,
            })

        # Corner towers every quarter
        if i % max(1, num_segments // 4) == 0 and not is_gate:
            walls.append({
                "type": "corner_tower",
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_tower": True,
            })

    total_buildings = sum(d["building_count"] for d in districts)
    total_roads = len(all_district_roads) + len(connector_roads) + 1  # +1 for main road

    return {
        "districts": districts,
        "main_road": main_road,
        "connector_roads": connector_roads,
        "walls": walls,
        "gates": gates,
        "metadata": {
            "city_size": (city_width, city_depth),
            "num_districts": len(districts),
            "total_buildings": total_buildings,
            "total_roads": total_roads,
            "wall_segments": len(walls),
            "gate_count": len(gates),
            "seed": seed,
            "main_axis": main_axis,
            "layout_signature": city_profile.get("signature"),
        },
    }


# ---------------------------------------------------------------------------
# Concentric-organic district layout (medieval_town)
# ---------------------------------------------------------------------------

def generate_concentric_districts(
    center: tuple[float, float],
    radius: float,
    seed: int,
    veil_pressure: float = 0.0,
    heightmap: Callable[[float, float], float] | None = None,
    wall_height: float = 3.5,
) -> dict[str, Any]:
    """Generate a medieval town using concentric ring zoning + OBB lot subdivision.

    Uses pure-logic grammar functions from _settlement_grammar.py:
      - ring_for_position → district assignment
      - generate_road_network_organic → winding medieval streets
      - subdivide_block_to_lots → OBB recursive lot split per road block
      - assign_buildings_to_lots → district-weighted building types
      - generate_prop_manifest → corruption-scaled prop placement specs

    Returns a dict compatible with generate_settlement() output structure so
    the same Blender wiring layer can consume it without modification.
    """
    rng = random.Random(seed)

    # --- Step 1: Generate organic road network ---
    # Seed settlement anchor points radially so roads radiate from center
    num_anchors = rng.randint(8, 14)
    anchor_points: list[tuple[float, float, float]] = [center + (0.0,)]  # type: ignore[operator]
    for i in range(num_anchors):
        angle = (i / num_anchors) * 2.0 * math.pi + rng.uniform(-0.3, 0.3)
        dist = rng.uniform(radius * 0.25, radius * 0.85)
        ax = center[0] + math.cos(angle) * dist
        ay = center[1] + math.sin(angle) * dist
        az = _sample_heightmap(heightmap, ax, ay)
        anchor_points.append((ax, ay, az))

    raw_roads = generate_road_network_organic(
        center=center,
        radius=radius,
        seed=seed,
        waypoint_count=num_anchors,
    )

    # Convert grammar road dicts to settlement_generator format
    roads: list[dict[str, Any]] = []
    for seg in raw_roads:
        pts = seg["points"]
        if len(pts) < 2:
            continue
        for pi in range(len(pts) - 1):
            roads.append({
                "start": (pts[pi][0], pts[pi][1]),
                "end": (pts[pi + 1][0], pts[pi + 1][1]),
                "width": seg["width"],
                "style": seg["style"],
            })

    # --- Step 2: Build road-bounded block polygons (simple rectangular blocks) ---
    # For each pair of adjacent anchor points + center, form a triangular block polygon
    # that the lot subdivider can recurse into.
    blocks: list[list[tuple[float, float]]] = []
    num_ap = len(anchor_points) - 1  # exclude center at index 0
    for i in range(num_ap):
        a1 = anchor_points[1 + i]
        a2 = anchor_points[1 + (i + 1) % num_ap]
        block_poly = [
            (center[0], center[1]),
            (a1[0], a1[1]),
            (a2[0], a2[1]),
        ]
        blocks.append(block_poly)

    # --- Step 3: Subdivide blocks into lots, assign buildings ---
    all_lots: list[dict[str, Any]] = []
    all_buildings: list[dict[str, Any]] = []

    for block_poly in blocks:
        # Determine district for block centroid
        cx = sum(p[0] for p in block_poly) / len(block_poly)
        cy = sum(p[1] for p in block_poly) / len(block_poly)
        district = ring_for_position((cx, cy), center, radius)

        lots = subdivide_block_to_lots(
            block_polygon=block_poly,
            district=district,
            seed=rng.randint(0, 2**31),
        )
        all_lots.extend(lots)

    # Assign building types to lots
    assigned = assign_buildings_to_lots(
        lots=all_lots,
        center=center,
        radius=radius,
        veil_pressure=veil_pressure,
        seed=seed,
    )

    # Convert grammar building assignments to settlement_generator building format
    for idx, lot in enumerate(assigned):
        lot_cx = sum(p[0] for p in lot["polygon"]) / len(lot["polygon"])
        lot_cy = sum(p[1] for p in lot["polygon"]) / len(lot["polygon"])
        lot_area = lot.get("area", 25.0)
        fp_side = max(3.0, min(12.0, math.sqrt(lot_area) * 0.6))
        elevation = _sample_heightmap(heightmap, lot_cx, lot_cy)
        foundation_profile = _compute_foundation_profile(
            heightmap,
            (lot_cx, lot_cy),
            (fp_side, fp_side),
            rotation=0.0,
        )
        btype = lot.get("building_type", "abandoned_house")
        variation_rng = random.Random(seed ^ idx)
        bld = {
            "type": btype,
            "position": (round(lot_cx, 2), round(lot_cy, 2)),
            "footprint": (fp_side, fp_side),
            "rotation": variation_rng.uniform(0.0, math.pi * 2.0),
            "floors": variation_rng.randint(1, 2),
            "district": lot["district"],
            "unique_seed": seed ^ idx,
            "elevation": round(elevation, 3),
            "foundation_height": foundation_profile["foundation_height"],
            "platform_elevation": foundation_profile["platform_elevation"],
            "foundation_profile": foundation_profile,
            "orientation_edge": lot.get("orientation_edge"),
            "room_functions": _BUILDING_ROOMS.get(btype, []),
        }
        variation_rng2 = random.Random(seed ^ idx ^ 0xBEEF)
        bld = _apply_building_variation(variation_rng2, bld)
        all_buildings.append(bld)

    # --- Step 4: Generate prop manifest ---
    prop_manifest = generate_prop_manifest(
        road_segments=raw_roads,
        center=center,
        radius=radius,
        veil_pressure=veil_pressure,
        seed=seed,
    )

    # Convert prop manifest to settlement prop format
    props: list[dict[str, Any]] = []
    for pm in prop_manifest:
        pos = pm["position"]
        px, py = pos[0], pos[1]
        props.append({
            "type": pm["prop_type"],
            "position": (round(px, 2), round(py, 2)),
            "rotation": pm["rotation_z"],
            "corruption_band": pm["corruption_band"],
            "cache_key": pm["cache_key"],
            "source": "tripo_manifest",
        })

    # --- Step 5: Perimeter walls ---
    perimeter_config = {
        "has_walls": True,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
    }
    perimeter = _generate_perimeter(rng, perimeter_config, center, radius)

    # --- Step 6: Furnish interiors + lights ---
    interiors: dict[int, list[dict[str, Any]]] = {}
    all_lights: list[dict[str, Any]] = []
    for idx, bld in enumerate(all_buildings):
        rooms = bld.get("room_functions", [])
        if not rooms:
            continue
        bx, by = bld["position"]
        fp = bld.get("footprint", (6.0, 6.0))
        num_floors = bld.get("floors", 1)
        room_furnishings: list[dict[str, Any]] = []
        building_lights: list[dict[str, Any]] = []
        # Distribute rooms across floors instead of duplicating all on every floor
        rooms_per_floor: dict[int, list[tuple[int, str]]] = {}
        for ri, room_type in enumerate(rooms):
            floor_idx = ri % max(1, num_floors)
            rooms_per_floor.setdefault(floor_idx, []).append((ri, room_type))
        for floor in range(max(1, num_floors)):
            floor_rooms = rooms_per_floor.get(floor, [(0, rooms[0])] if rooms else [])
            floor_room_count = max(len(floor_rooms), 1)
            floor_room_height = fp[1] / floor_room_count
            for local_ri, (ri, room_type) in enumerate(floor_rooms):
                room_bounds = {
                    "min": (bx - fp[0] / 2, by - fp[1] / 2 + local_ri * floor_room_height),
                    "max": (bx + fp[0] / 2, by - fp[1] / 2 + (local_ri + 1) * floor_room_height),
                }
                room_rng = random.Random(bld["unique_seed"] + ri + floor * 1000)
                room_seed = room_rng.randint(0, 2**31)
                room_w = room_bounds["max"][0] - room_bounds["min"][0]
                room_d = room_bounds["max"][1] - room_bounds["min"][1]
                furnishings = generate_interior_layout(room_type, room_w, room_d, seed=room_seed)
                for item in furnishings:
                    item["position"][0] += room_bounds["min"][0]
                    item["position"][1] += room_bounds["min"][1]
                    item["floor"] = floor
                clutter = generate_clutter_layout(room_type, room_w, room_d, furnishings, seed=room_seed + 1)
                for item in clutter:
                    item["position"][0] += room_bounds["min"][0]
                    item["position"][1] += room_bounds["min"][1]
                    item["floor"] = floor
                furnishings.extend(clutter)
                room_furnishings.extend(furnishings)
                base_z = floor * wall_height
                room_lights = generate_lighting_layout(
                    room_type, room_w, room_d, height=wall_height,
                    furniture_items=furnishings, seed=room_seed + 2,
                )
                for lt in room_lights:
                    px, py, pz = lt["position"]
                    lt["position"] = (
                        round(px + room_bounds["min"][0], 4),
                        round(py + room_bounds["min"][1], 4),
                        round(pz + base_z, 4),
                    )
                    lt["floor"] = floor
                    lt["building_index"] = idx
                building_lights.extend(room_lights)
            # Add staircase between floors (except top floor)
            if floor < num_floors - 1:
                stair_item = {
                    "type": "stairs",
                    "position": [fp[0] * 0.8, fp[1] * 0.5, 0.0],
                    "rotation": 0.0,
                    "scale": [1.0, 1.0, 1.0],
                    "floor": floor,
                }
                room_furnishings.append(stair_item)
        if room_furnishings:
            interiors[idx] = room_furnishings
        all_lights.extend(building_lights)

    metadata = {
        "building_count": len(all_buildings),
        "road_count": len(roads),
        "prop_count": len(props),
        "lot_count": len(all_lots),
        "perimeter_element_count": len(perimeter),
        "furnished_building_count": len(interiors),
        "total_furniture_pieces": sum(len(v) for v in interiors.values()),
        "light_count": len(all_lights),
        "veil_pressure": veil_pressure,
        "layout_pattern": "concentric_organic",
        "prop_manifest": prop_manifest,
    }

    return {
        "buildings": all_buildings,
        "roads": roads,
        "props": props,
        "perimeter": perimeter,
        "interiors": interiors,
        "lights": all_lights,
        "metadata": metadata,
        "districts": [],  # district info embedded per-building
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_settlement(
    settlement_type: str,
    seed: int | None = None,
    center: tuple[float, float] = (0.0, 0.0),
    radius: float = 50.0,
    heightmap: Optional[Callable[[float, float], float]] = None,
    wall_height: float = 3.0,
    layout_brief: str = "",
    veil_pressure: float = 0.0,
) -> dict[str, Any]:
    """Generate a complete settlement layout.

    Composes building placement, road network, prop scattering,
    perimeter walls, interior furnishing (multi-floor), interior lighting,
    and per-building variation into a single data structure.

    Parameters
    ----------
    settlement_type : str
        One of: village, town, bandit_camp, castle, outpost.
    seed : int or None
        Random seed for deterministic generation.  None uses system
        randomness.
    center : tuple
        World-space (x, y) center of the settlement.
    radius : float
        Approximate radius of the settlement area.
    heightmap : callable or None
        Optional function ``(x, y) -> z`` for terrain-aware placement.
        When provided, each building gets ``elevation`` and
        ``foundation_height`` fields based on the terrain at its position.
    wall_height : float
        Height of a single storey/floor (default 3.0 units).

    Returns
    -------
    dict with:
        - settlement_type: str
        - seed: int
        - center: tuple
        - radius: float
        - buildings: list of placed building specs with variation
        - roads: list of road segments
        - props: list of decoration placements
        - perimeter: list of wall/gate elements
        - interiors: dict mapping building index to furniture list
        - lights: list of all interior light placements
        - metadata: summary statistics

    Raises
    ------
    ValueError
        If ``settlement_type`` is not recognized.
    """
    if settlement_type not in SETTLEMENT_TYPES:
        raise ValueError(
            f"Unknown settlement type '{settlement_type}'. "
            f"Valid types: {sorted(SETTLEMENT_TYPES.keys())}"
        )

    config = SETTLEMENT_TYPES[settlement_type]

    if seed is None:
        seed = random.Random().randint(0, 2**31)  # fresh OS-entropy instance; not global RNG
    rng = random.Random(seed)
    layout_profile = _derive_settlement_profile(settlement_type, layout_brief, seed)

    # --- Concentric-organic medieval town generation ---
    if config.get("layout_pattern") == "concentric_organic":
        effective_radius = radius if radius > 0 else config.get("default_radius", 150.0)
        town_data = generate_concentric_districts(
            center=center,
            radius=effective_radius,
            seed=seed,
            veil_pressure=veil_pressure,
            heightmap=heightmap,
            wall_height=wall_height,
        )
        return {
            "settlement_type": settlement_type,
            "seed": seed,
            "center": center,
            "radius": effective_radius,
            "buildings": town_data["buildings"],
            "roads": town_data["roads"],
            "props": town_data["props"],
            "perimeter": town_data["perimeter"],
            "interiors": town_data["interiors"],
            "lights": town_data["lights"],
            "districts": town_data["districts"],
            "metadata": {
                **town_data["metadata"],
                "has_walls": config["has_walls"],
                "layout_pattern": "concentric_organic",
                "layout_brief": layout_brief,
                "layout_profile": layout_profile,
            },
        }

    # --- District-based city generation ---
    if config.get("layout_pattern") == "district":
        city_data = generate_city_districts(
            city_width=radius * 2.0,
            city_depth=radius * 2.0,
            num_districts=max(3, min(6, rng.randint(3, 6))),
            seed=seed,
            city_profile=layout_profile,
        )

        # Offset all positions by the requested center
        def _offset_pos(pos: tuple[float, float]) -> tuple[float, float]:
            return (round(pos[0] + center[0], 2), round(pos[1] + center[1], 2))

        # Collect all buildings from districts, apply variation + heightmap
        all_buildings: list[dict[str, Any]] = []
        for dist in city_data["districts"]:
            for bld in dist["buildings"]:
                bld["position"] = _offset_pos(bld["position"])
                variation_rng = random.Random(bld["unique_seed"])
                varied = _apply_building_variation(variation_rng, bld)
                bx, by = varied["position"]
                foundation_profile = _compute_foundation_profile(
                    heightmap,
                    (bx, by),
                    varied.get("footprint", (6.0, 6.0)),
                    rotation=float(varied.get("rotation", 0.0)),
                )
                varied["elevation"] = round(_sample_heightmap(heightmap, bx, by), 3)
                varied["foundation_height"] = foundation_profile["foundation_height"]
                varied["platform_elevation"] = foundation_profile["platform_elevation"]
                varied["foundation_profile"] = foundation_profile
                varied["district"] = dist["district_type"]
                all_buildings.append(varied)

        # Collect all roads, offset positions
        all_roads: list[dict[str, Any]] = []
        for dist in city_data["districts"]:
            for road in dist["roads"]:
                road["start"] = _offset_pos(road["start"])
                road["end"] = _offset_pos(road["end"])
                all_roads.append(road)
        # Main road + connectors
        main_road = city_data["main_road"]
        main_road["start"] = _offset_pos(main_road["start"])
        main_road["end"] = _offset_pos(main_road["end"])
        all_roads.append(main_road)
        for cr in city_data["connector_roads"]:
            cr["start"] = _offset_pos(cr["start"])
            cr["end"] = _offset_pos(cr["end"])
            all_roads.append(cr)

        # Scatter props
        props = _scatter_settlement_props(
            rng, all_buildings, all_roads, config, radius, center
        )

        # Walls and gates, offset positions
        perimeter: list[dict[str, Any]] = []
        for w in city_data["walls"] + city_data["gates"]:
            w["position"] = _offset_pos(w["position"])
            perimeter.append(w)

        # Furnish interiors + lights
        interiors: dict[int, list[dict[str, Any]]] = {}
        all_lights: list[dict[str, Any]] = []
        for idx, bld in enumerate(all_buildings):
            rooms = bld.get("room_functions", [])
            if not rooms:
                continue
            bx, by = bld["position"]
            fp = bld.get("footprint", (6.0, 6.0))
            num_floors = bld.get("floors", 1)
            room_height = fp[1] / max(len(rooms), 1)
            room_furnishings: list[dict[str, Any]] = []
            building_lights: list[dict[str, Any]] = []
            for floor in range(max(1, num_floors)):
                for ri, room_type in enumerate(rooms):
                    room_bounds = {
                        "min": (bx - fp[0] / 2, by - fp[1] / 2 + ri * room_height),
                        "max": (bx + fp[0] / 2, by - fp[1] / 2 + (ri + 1) * room_height),
                    }
                    room_rng = random.Random(bld["unique_seed"] + ri + floor * 1000)
                    room_seed = room_rng.randint(0, 2**31)
                    room_w = room_bounds["max"][0] - room_bounds["min"][0]
                    room_d = room_bounds["max"][1] - room_bounds["min"][1]
                    furnishings = generate_interior_layout(room_type, room_w, room_d, seed=room_seed)
                    for item in furnishings:
                        item["position"][0] += room_bounds["min"][0]
                        item["position"][1] += room_bounds["min"][1]
                        item["floor"] = floor
                    clutter = generate_clutter_layout(room_type, room_w, room_d, furnishings, seed=room_seed + 1)
                    for item in clutter:
                        item["position"][0] += room_bounds["min"][0]
                        item["position"][1] += room_bounds["min"][1]
                        item["floor"] = floor
                    furnishings.extend(clutter)
                    room_furnishings.extend(furnishings)
                    base_z = floor * wall_height
                    room_lights = generate_lighting_layout(
                        room_type, room_w, room_d, height=wall_height,
                        furniture_items=furnishings, seed=room_seed + 2,
                    )
                    for lt in room_lights:
                        px, py, pz = lt["position"]
                        lt["position"] = (
                            round(px + room_bounds["min"][0], 4),
                            round(py + room_bounds["min"][1], 4),
                            round(pz + base_z, 4),
                        )
                        lt["floor"] = floor
                        lt["building_index"] = idx
                    building_lights.extend(room_lights)
            if room_furnishings:
                interiors[idx] = room_furnishings
            all_lights.extend(building_lights)

        metadata = {
            "building_count": len(all_buildings),
            "road_count": len(all_roads),
            "prop_count": len(props),
            "perimeter_element_count": len(perimeter),
            "furnished_building_count": len(interiors),
            "total_furniture_pieces": sum(len(v) for v in interiors.values()),
            "light_count": len(all_lights),
            "has_walls": config["has_walls"],
            "layout_pattern": "district",
            "district_count": len(city_data["districts"]),
            "district_types": [d["district_type"] for d in city_data["districts"]],
            "layout_brief": layout_brief,
            "layout_profile": layout_profile,
            "main_axis": city_data["metadata"].get("main_axis", layout_profile.get("main_axis")),
        }

        return {
            "settlement_type": settlement_type,
            "seed": seed,
            "center": center,
            "radius": radius,
            "buildings": all_buildings,
            "roads": all_roads,
            "props": props,
            "perimeter": perimeter,
            "interiors": interiors,
            "lights": all_lights,
            "districts": city_data["districts"],
            "metadata": metadata,
        }

    # 1. Place buildings (non-district layout patterns)
    effective_config = dict(config)
    effective_config["layout_pattern"] = layout_profile.get(
        "pattern", effective_config.get("layout_pattern", "organic"),
    )
    effective_config["main_axis"] = layout_profile.get("main_axis", "x")
    effective_config["water_edge"] = layout_profile.get("water_edge")
    effective_config["spoke_count"] = int(layout_profile.get("spoke_count", 4))
    effective_config["terrace_count"] = int(layout_profile.get("terrace_count", 3))
    density_bias = float(layout_profile.get("density_bias", 0.0))
    base_lo, base_hi = effective_config["building_count"]
    effective_config["building_count"] = (
        max(1, int(round(base_lo * (1.0 + density_bias)))),
        max(1, int(round(base_hi * (1.0 + density_bias)))),
    )

    buildings = _place_buildings(rng, effective_config, center, radius)

    # 2. Apply per-building variation + heightmap elevation
    varied_buildings: list[dict[str, Any]] = []
    for bld in buildings:
        variation_rng = random.Random(bld["unique_seed"])
        varied = _apply_building_variation(variation_rng, bld)
        # Terrain-aware Z placement
        bx, by = varied["position"]
        foundation_profile = _compute_foundation_profile(
            heightmap,
            (bx, by),
            varied.get("footprint", (6.0, 6.0)),
            rotation=float(varied.get("rotation", 0.0)),
        )
        varied["elevation"] = round(_sample_heightmap(heightmap, bx, by), 3)
        varied["foundation_height"] = foundation_profile["foundation_height"]
        varied["platform_elevation"] = foundation_profile["platform_elevation"]
        varied["foundation_profile"] = foundation_profile
        varied_buildings.append(varied)

    # 3. Generate roads
    roads = _generate_roads(varied_buildings, center, effective_config["road_style"], seed=seed)
    # CITY-004: add alleys between tightly-packed plots
    alleys = _generate_alleys(varied_buildings, roads, rng)
    roads = roads + alleys
    # CITY-005: annotate buildings with road frontage info
    _enforce_road_frontage(varied_buildings, roads)

    # 4. Scatter props
    props = _scatter_settlement_props(
        rng, varied_buildings, roads, effective_config, radius, center
    )

    # 5. Perimeter walls
    perimeter = _generate_perimeter(rng, effective_config, center, radius)

    # 6. Furnish interiors (multi-floor aware) + place lights
    interiors: dict[int, list[dict[str, Any]]] = {}
    all_lights: list[dict[str, Any]] = []
    for idx, bld in enumerate(varied_buildings):
        rooms = bld.get("room_functions", [])
        if not rooms:
            continue
        bx, by = bld["position"]
        fp = bld.get("footprint", (6.0, 6.0))
        num_floors = bld.get("floors", 1)

        # Divide building footprint into rooms (stacked vertically within footprint)
        room_height = fp[1] / max(len(rooms), 1)
        room_furnishings: list[dict[str, Any]] = []
        building_lights: list[dict[str, Any]] = []

        for floor in range(max(1, num_floors)):
            for ri, room_type in enumerate(rooms):
                # Offset room bounds Y by floor * wall_height for
                # multi-floor buildings (furniture Y remains in footprint
                # space; floor index is stored for 3D placement)
                room_bounds = {
                    "min": (
                        bx - fp[0] / 2,
                        by - fp[1] / 2 + ri * room_height,
                    ),
                    "max": (
                        bx + fp[0] / 2,
                        by - fp[1] / 2 + (ri + 1) * room_height,
                    ),
                }
                room_rng = random.Random(
                    bld["unique_seed"] + ri + floor * 1000
                )
                room_seed = room_rng.randint(0, 2**31)
                room_w = room_bounds["max"][0] - room_bounds["min"][0]
                room_d = room_bounds["max"][1] - room_bounds["min"][1]
                furnishings = generate_interior_layout(room_type, room_w, room_d, seed=room_seed)
                for item in furnishings:
                    item["position"][0] += room_bounds["min"][0]
                    item["position"][1] += room_bounds["min"][1]
                    item["floor"] = floor
                clutter = generate_clutter_layout(room_type, room_w, room_d, furnishings, seed=room_seed + 1)
                for item in clutter:
                    item["position"][0] += room_bounds["min"][0]
                    item["position"][1] += room_bounds["min"][1]
                    item["floor"] = floor
                furnishings.extend(clutter)
                # Tag each furniture item with its floor
                room_furnishings.extend(furnishings)

                # Place lights for this room on this floor
                base_z = floor * wall_height
                room_lights = generate_lighting_layout(
                    room_type, room_w, room_d, height=wall_height,
                    furniture_items=furnishings, seed=room_seed + 2,
                )
                for lt in room_lights:
                    px, py, pz = lt["position"]
                    lt["position"] = (
                        round(px + room_bounds["min"][0], 4),
                        round(py + room_bounds["min"][1], 4),
                        round(pz + base_z, 4),
                    )
                    lt["floor"] = floor
                    lt["building_index"] = idx
                building_lights.extend(room_lights)

        if room_furnishings:
            interiors[idx] = room_furnishings
        all_lights.extend(building_lights)

    # 7. Metadata
    metadata = {
        "building_count": len(varied_buildings),
        "road_count": len(roads),
        "prop_count": len(props),
        "perimeter_element_count": len(perimeter),
        "furnished_building_count": len(interiors),
        "total_furniture_pieces": sum(
            len(v) for v in interiors.values()
        ),
        "light_count": len(all_lights),
        "has_walls": effective_config["has_walls"],
        "layout_pattern": effective_config.get("layout_pattern", "organic"),
        "layout_brief": layout_brief,
        "layout_profile": layout_profile,
    }

    return {
        "settlement_type": settlement_type,
        "seed": seed,
        "center": center,
        "radius": radius,
        "buildings": varied_buildings,
        "roads": roads,
        "props": props,
        "perimeter": perimeter,
        "interiors": interiors,
        "lights": all_lights,
        "metadata": metadata,
    }
