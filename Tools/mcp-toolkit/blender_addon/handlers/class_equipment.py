"""Path-exclusive equipment definitions for VeilBreakers hero paths.

Defines signature weapons, armor sets, brand affinities, material tiers,
and visual identity for each of the 4 hero paths:

  - IRONBOUND: Heavy tanks -- fortress shields, siege hammers, riveted plate
  - FANGBORN: Beast hunters -- fang daggers, antler staves, organic armor
  - VOIDTOUCHED: Arcane casters -- void staves, crystal wands, ethereal robes
  - UNCHAINED: Shadow rogues -- hidden blades, smoke bombs, sleek leather

Provides:
  - PATH_EQUIPMENT: Full path equipment definitions
  - VALID_PATHS: Set of recognised path names
  - get_path_equipment(): Look up full equipment data for a path
  - get_signature_weapons(): Weapons exclusive to a path
  - get_signature_armor_set(): Armor slot map for a path
  - get_brand_affinity(): Preferred brands for a path
  - get_visual_identity(): Visual identity tag for a path
  - validate_path_equipment(): Validate an equipment loadout against a path

All data is pure Python -- no ``bpy`` dependency -- for testability.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Valid equipment slots (matching armor_sets.py)
# ---------------------------------------------------------------------------

VALID_ARMOR_SLOTS = frozenset({
    "helmet", "chest", "gauntlet", "boot", "pauldron", "cape",
})

# ---------------------------------------------------------------------------
# Path equipment definitions
# ---------------------------------------------------------------------------

PATH_EQUIPMENT: dict[str, dict[str, Any]] = {
    "IRONBOUND": {
        "signature_weapons": [
            "fortress_shield", "chain_flail", "siege_hammer", "war_banner",
        ],
        "signature_armor": {
            "helmet": "fortress_helm",
            "chest": "siege_plate",
            "gauntlet": "chain_gauntlets",
            "boot": "iron_sabatons",
            "pauldron": "tower_pauldrons",
            "cape": "battle_standard",
        },
        "brand_affinity": ["IRON", "SAVAGE"],
        "material_tier": "steel",
        "visual_identity": "heavy_angular_riveted",
        "description": (
            "Ironbound warriors are the unbreakable vanguard. Their equipment "
            "prioritises mass, coverage, and intimidation through sheer weight "
            "of steel and chain."
        ),
    },
    "FANGBORN": {
        "signature_weapons": [
            "fang_daggers", "antler_staff", "claw_gauntlets", "thorn_whip",
        ],
        "signature_armor": {
            "helmet": "beastmaster_hood",
            "chest": "bark_armor",
            "gauntlet": "claw_wraps",
            "boot": "root_boots",
            "pauldron": "fur_mantle",
            "cape": "feather_cloak",
        },
        "brand_affinity": ["SAVAGE", "VENOM"],
        "material_tier": "monster_hide",
        "visual_identity": "organic_curved_natural",
        "description": (
            "Fangborn hunt the wild and wear what they kill. Their gear is "
            "grown, carved, and stitched from nature's deadliest materials."
        ),
    },
    "VOIDTOUCHED": {
        "signature_weapons": [
            "void_staff", "crystal_wand", "spell_blade", "grimoire",
        ],
        "signature_armor": {
            "helmet": "arcane_circlet",
            "chest": "archmage_robes",
            "gauntlet": "enchanted_bracers",
            "boot": "astral_sandals",
            "pauldron": "floating_crystals",
            "cape": "void_cloak",
        },
        "brand_affinity": ["VOID", "DREAD"],
        "material_tier": "enchanted_silk",
        "visual_identity": "flowing_ethereal_glowing",
        "description": (
            "Voidtouched channel forces beyond mortal comprehension. Their "
            "equipment shimmers with otherworldly energies and defies physics."
        ),
    },
    "UNCHAINED": {
        "signature_weapons": [
            "hidden_blade", "hand_crossbow", "smoke_bomb", "garrote",
        ],
        "signature_armor": {
            "helmet": "shadow_hood",
            "chest": "infiltrator_leather",
            "gauntlet": "tool_bracers",
            "boot": "silent_boots",
            "pauldron": "blade_shoulders",
            "cape": "shadow_cloak",
        },
        "brand_affinity": ["SURGE", "LEECH"],
        "material_tier": "hardened",
        "visual_identity": "sleek_dark_minimal",
        "description": (
            "Unchained strike from shadows and vanish before the body falls. "
            "Their equipment sacrifices protection for silence and speed."
        ),
    },
}


# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------

VALID_PATHS = frozenset(PATH_EQUIPMENT.keys())

# Collect every signature weapon across all paths for cross-reference
ALL_SIGNATURE_WEAPONS: frozenset[str] = frozenset(
    weapon
    for data in PATH_EQUIPMENT.values()
    for weapon in data["signature_weapons"]
)

# Collect every unique armor piece name across all paths
ALL_SIGNATURE_ARMOR_PIECES: frozenset[str] = frozenset(
    piece_name
    for data in PATH_EQUIPMENT.values()
    for piece_name in data["signature_armor"].values()
)


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------


def _normalise_path(path_name: str) -> str:
    """Normalise and validate a path name.

    Args:
        path_name: Path name (case-insensitive).

    Returns:
        Upper-cased path name.

    Raises:
        ValueError: If the path name is unknown.
    """
    upper = path_name.upper()
    if upper not in VALID_PATHS:
        raise ValueError(
            f"Unknown path '{path_name}'. Valid paths: {sorted(VALID_PATHS)}"
        )
    return upper


def get_path_equipment(path_name: str) -> dict[str, Any]:
    """Retrieve the full equipment definition for a hero path.

    Args:
        path_name: Path name (e.g. 'IRONBOUND'). Case-insensitive.

    Returns:
        Deep copy of the path's equipment definition dict.

    Raises:
        ValueError: If the path name is unknown.
    """
    key = _normalise_path(path_name)
    data = PATH_EQUIPMENT[key]
    # Return a copy to prevent mutation of the source data
    return {
        "signature_weapons": list(data["signature_weapons"]),
        "signature_armor": dict(data["signature_armor"]),
        "brand_affinity": list(data["brand_affinity"]),
        "material_tier": data["material_tier"],
        "visual_identity": data["visual_identity"],
        "description": data["description"],
    }


def get_signature_weapons(path_name: str) -> list[str]:
    """Get the list of signature weapons for a hero path.

    Args:
        path_name: Path name (e.g. 'FANGBORN'). Case-insensitive.

    Returns:
        List of weapon names exclusive to the path.

    Raises:
        ValueError: If the path name is unknown.
    """
    key = _normalise_path(path_name)
    return list(PATH_EQUIPMENT[key]["signature_weapons"])


def get_signature_armor_set(path_name: str) -> dict[str, str]:
    """Get the signature armor slot-to-piece mapping for a hero path.

    Args:
        path_name: Path name (e.g. 'VOIDTOUCHED'). Case-insensitive.

    Returns:
        Dict mapping armor slot names to signature piece names.

    Raises:
        ValueError: If the path name is unknown.
    """
    key = _normalise_path(path_name)
    return dict(PATH_EQUIPMENT[key]["signature_armor"])


def get_brand_affinity(path_name: str) -> list[str]:
    """Get the preferred brands for a hero path.

    Args:
        path_name: Path name (e.g. 'UNCHAINED'). Case-insensitive.

    Returns:
        List of brand names the path has affinity with.

    Raises:
        ValueError: If the path name is unknown.
    """
    key = _normalise_path(path_name)
    return list(PATH_EQUIPMENT[key]["brand_affinity"])


def get_visual_identity(path_name: str) -> str:
    """Get the visual identity tag for a hero path.

    Args:
        path_name: Path name (e.g. 'IRONBOUND'). Case-insensitive.

    Returns:
        Visual identity string describing the path's aesthetic.

    Raises:
        ValueError: If the path name is unknown.
    """
    key = _normalise_path(path_name)
    return PATH_EQUIPMENT[key]["visual_identity"]


def validate_path_equipment(
    path_name: str,
    weapon: str | None = None,
    armor_pieces: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate whether a weapon/armor loadout matches a path's signature gear.

    Args:
        path_name: Path to validate against.
        weapon: Optional weapon name to check.
        armor_pieces: Optional dict of {slot: piece_name} to check.

    Returns:
        Dict with:
          - valid: bool (True if all provided items match the path)
          - weapon_match: bool or None if not provided
          - armor_matches: dict[str, bool] per slot, or None
          - mismatched_slots: list of slots that don't match
          - path: normalised path name
    """
    key = _normalise_path(path_name)
    data = PATH_EQUIPMENT[key]

    result: dict[str, Any] = {"path": key, "valid": True}

    # Weapon check
    if weapon is not None:
        weapon_match = weapon in data["signature_weapons"]
        result["weapon_match"] = weapon_match
        if not weapon_match:
            result["valid"] = False
    else:
        result["weapon_match"] = None

    # Armor check
    if armor_pieces is not None:
        sig_armor = data["signature_armor"]
        armor_matches: dict[str, bool] = {}
        mismatched: list[str] = []
        for slot, piece in armor_pieces.items():
            match = sig_armor.get(slot) == piece
            armor_matches[slot] = match
            if not match:
                mismatched.append(slot)
        result["armor_matches"] = armor_matches
        result["mismatched_slots"] = mismatched
        if mismatched:
            result["valid"] = False
    else:
        result["armor_matches"] = None
        result["mismatched_slots"] = []

    return result
