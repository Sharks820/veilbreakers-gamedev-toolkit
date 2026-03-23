"""Material tier system for VeilBreakers equipment.

Defines metal, wood, leather, and cloth material tiers from common to legendary
with visual properties (base_color, metallic, roughness, emission, etc.).

All tier colours follow dark fantasy palette rules:
- Metal saturation <= 40%
- Metal value 10-50% for base, with reflective metals slightly higher
- Warm/desaturated tones for organic materials
- Supernatural materials may use emission for magical glow

This module is pure data -- no bpy imports -- and can be tested standalone.

Provides:
- METAL_TIERS: 10 metal material tiers (iron -> void_touched)
- WOOD_TIERS: 5 wood material tiers (pine -> living_wood)
- LEATHER_TIERS: 5 leather material tiers (rawhide -> dragon_leather)
- CLOTH_TIERS: 5 cloth material tiers (burlap -> void_woven)
- get_material_tier(category, tier_name): lookup single tier
- get_tier_names(category): list available tier names
- apply_material_tier_to_equipment(mesh_data, category, tier_name): return modified params
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Required keys for validation
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = {"base_color", "roughness", "description"}


# ---------------------------------------------------------------------------
# Metal tiers (10 tiers: common -> legendary)
# ---------------------------------------------------------------------------

METAL_TIERS: dict[str, dict[str, Any]] = {
    "iron": {
        "base_color": (0.56, 0.57, 0.58),
        "metallic": 0.85,
        "roughness": 0.60,
        "roughness_variation": 0.20,
        "rust_amount": 0.3,
        "description": "Common forged iron, prone to rust",
    },
    "steel": {
        "base_color": (0.63, 0.62, 0.64),
        "metallic": 0.90,
        "roughness": 0.25,
        "roughness_variation": 0.15,
        "description": "Refined steel, cleaner finish",
    },
    "silver": {
        "base_color": (0.95, 0.93, 0.88),
        "metallic": 0.95,
        "roughness": 0.20,
        "emission": 0.02,
        "description": "Bright silver, slight holy glow",
    },
    "gold": {
        "base_color": (1.0, 0.86, 0.57),
        "metallic": 0.95,
        "roughness": 0.20,
        "coat_weight": 0.3,
        "description": "Pure gold, ornate finish",
    },
    "mithril": {
        "base_color": (0.65, 0.70, 0.85),
        "metallic": 0.98,
        "roughness": 0.10,
        "emission": 0.05,
        "emission_color": (0.6, 0.7, 0.9),
        "description": "Elven mithril, blue-silver sheen",
    },
    "adamantine": {
        "base_color": (0.15, 0.15, 0.18),
        "metallic": 0.99,
        "roughness": 0.05,
        "description": "Indestructible dark metal",
    },
    "obsidian": {
        "base_color": (0.05, 0.05, 0.08),
        "metallic": 0.3,
        "roughness": 0.02,
        "coat_weight": 0.8,
        "description": "Volcanic glass, razor sharp",
    },
    "dragonbone": {
        "base_color": (0.85, 0.80, 0.90),
        "metallic": 0.4,
        "roughness": 0.55,
        "subsurface": 0.05,
        "description": "Ancient dragon bone, blue-white marbling",
    },
    "orichalcum": {
        "base_color": (0.73, 0.55, 0.36),
        "metallic": 0.92,
        "roughness": 0.35,
        "description": "Ancient bronze-red alloy",
    },
    "void_touched": {
        "base_color": (0.10, 0.05, 0.15),
        "metallic": 0.60,
        "roughness": 0.30,
        "emission": 0.15,
        "emission_color": (0.3, 0.1, 0.5),
        "description": "Reality-warped metal, purple distortion",
    },
}


# ---------------------------------------------------------------------------
# Wood tiers (5 tiers)
# ---------------------------------------------------------------------------

WOOD_TIERS: dict[str, dict[str, Any]] = {
    "pine": {
        "base_color": (0.65, 0.55, 0.35),
        "roughness": 0.80,
        "description": "Common softwood",
    },
    "oak": {
        "base_color": (0.45, 0.35, 0.20),
        "roughness": 0.70,
        "description": "Standard hardwood",
    },
    "darkwood": {
        "base_color": (0.15, 0.10, 0.08),
        "roughness": 0.60,
        "description": "Near-black premium wood",
    },
    "ironwood": {
        "base_color": (0.35, 0.30, 0.28),
        "roughness": 0.50,
        "metallic": 0.15,
        "description": "Metal-hard wood",
    },
    "living_wood": {
        "base_color": (0.20, 0.30, 0.15),
        "roughness": 0.65,
        "emission": 0.02,
        "description": "Still growing, green veins",
    },
}


# ---------------------------------------------------------------------------
# Leather tiers (5 tiers)
# ---------------------------------------------------------------------------

LEATHER_TIERS: dict[str, dict[str, Any]] = {
    "rawhide": {
        "base_color": (0.60, 0.50, 0.35),
        "roughness": 0.85,
        "description": "Untreated animal skin",
    },
    "cured": {
        "base_color": (0.45, 0.35, 0.22),
        "roughness": 0.70,
        "description": "Standard tanned leather",
    },
    "hardened": {
        "base_color": (0.30, 0.22, 0.15),
        "roughness": 0.55,
        "description": "Boiled and shaped",
    },
    "monster_hide": {
        "base_color": (0.25, 0.20, 0.18),
        "roughness": 0.60,
        "description": "Exotic creature leather",
    },
    "dragon_leather": {
        "base_color": (0.20, 0.15, 0.25),
        "roughness": 0.45,
        "metallic": 0.15,
        "description": "Scale-patterned dragon hide",
    },
}


# ---------------------------------------------------------------------------
# Cloth tiers (5 tiers)
# ---------------------------------------------------------------------------

CLOTH_TIERS: dict[str, dict[str, Any]] = {
    "burlap": {
        "base_color": (0.50, 0.45, 0.30),
        "roughness": 0.95,
        "description": "Rough cheap fabric",
    },
    "linen": {
        "base_color": (0.70, 0.65, 0.55),
        "roughness": 0.80,
        "description": "Common woven cloth",
    },
    "silk": {
        "base_color": (0.80, 0.75, 0.70),
        "roughness": 0.30,
        "coat_weight": 0.2,
        "description": "Smooth lustrous fabric",
    },
    "enchanted_silk": {
        "base_color": (0.75, 0.70, 0.85),
        "roughness": 0.25,
        "emission": 0.03,
        "description": "Magically woven, slight glow",
    },
    "void_woven": {
        "base_color": (0.10, 0.08, 0.15),
        "roughness": 0.40,
        "emission": 0.08,
        "emission_color": (0.3, 0.1, 0.5),
        "description": "Reality-shifted fabric",
    },
}


# ---------------------------------------------------------------------------
# Category registry
# ---------------------------------------------------------------------------

_ALL_CATEGORIES: dict[str, dict[str, dict[str, Any]]] = {
    "metal": METAL_TIERS,
    "wood": WOOD_TIERS,
    "leather": LEATHER_TIERS,
    "cloth": CLOTH_TIERS,
}

VALID_CATEGORIES = frozenset(_ALL_CATEGORIES.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_material_tier(category: str, tier_name: str) -> dict[str, Any]:
    """Return material properties for a given category and tier.

    Args:
        category: One of 'metal', 'wood', 'leather', 'cloth'.
        tier_name: Tier name within the category (e.g. 'iron', 'oak').

    Returns:
        Dict of material properties (base_color, roughness, etc.).

    Raises:
        ValueError: If category or tier_name is unknown.
    """
    category = category.lower()
    tier_name = tier_name.lower()

    if category not in _ALL_CATEGORIES:
        raise ValueError(
            f"Unknown material category: {category!r}. "
            f"Valid: {sorted(_ALL_CATEGORIES.keys())}"
        )

    tiers = _ALL_CATEGORIES[category]
    if tier_name not in tiers:
        raise ValueError(
            f"Unknown tier {tier_name!r} in category {category!r}. "
            f"Valid: {sorted(tiers.keys())}"
        )

    # Return a copy to prevent mutation of module data
    return dict(tiers[tier_name])


def get_tier_names(category: str) -> list[str]:
    """Return sorted list of available tier names for a category.

    Args:
        category: One of 'metal', 'wood', 'leather', 'cloth'.

    Returns:
        Sorted list of tier name strings.

    Raises:
        ValueError: If category is unknown.
    """
    category = category.lower()
    if category not in _ALL_CATEGORIES:
        raise ValueError(
            f"Unknown material category: {category!r}. "
            f"Valid: {sorted(_ALL_CATEGORIES.keys())}"
        )
    return sorted(_ALL_CATEGORIES[category].keys())


def apply_material_tier_to_equipment(
    mesh_data: dict[str, Any],
    category: str,
    tier_name: str,
) -> dict[str, Any]:
    """Build material parameters for equipment based on tier.

    Merges tier properties into a material parameter dict suitable for
    passing to Blender material creation functions. Does NOT call bpy.

    Args:
        mesh_data: Dict with at least 'object_name' key (the equipment mesh).
        category: Material category ('metal', 'wood', 'leather', 'cloth').
        tier_name: Tier name within the category.

    Returns:
        Dict with keys: object_name, material_name, base_color, metallic,
        roughness, and any extra tier properties (emission, coat_weight, etc.).
    """
    tier = get_material_tier(category, tier_name)
    object_name = mesh_data.get("object_name", "equipment")

    material_params: dict[str, Any] = {
        "object_name": object_name,
        "material_name": f"{object_name}_{category}_{tier_name}",
        "base_color": tier["base_color"],
        "metallic": tier.get("metallic", 0.0),
        "roughness": tier["roughness"],
    }

    # Forward optional properties
    for key in ("emission", "emission_color", "coat_weight", "subsurface",
                "roughness_variation", "rust_amount"):
        if key in tier:
            material_params[key] = tier[key]

    return material_params
