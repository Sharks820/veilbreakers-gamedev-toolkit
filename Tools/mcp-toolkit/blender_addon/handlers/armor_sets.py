"""Armor set registration and bonus system for VeilBreakers equipment.

Defines 12 armor sets (3 per path x 4 paths), each with piece definitions,
set bonuses, material tiers, and accent colors. All data is pure Python
-- no ``bpy`` dependency -- for testability.

Paths:
  - IRONBOUND (tank/defense): Sentinel, Guardian, Bulwark
  - SAVAGE (damage/aggression): Marauder, Berserker, Warlord
  - SURGE (magic/elemental): Stormcaller, Arcanist, Tempest
  - VOID (dark/corruption): Shadowblade, Dreadlord, Abyssal

Provides:
  - ARMOR_SETS: full set definitions
  - get_armor_set(): look up a single set
  - get_sets_for_path(): all sets in a path
  - compute_set_bonus_level(): how many bonuses are active
  - get_active_bonuses(): list of active bonus names
  - validate_set_pieces(): check if piece names are valid for a set
  - VALID_PIECE_SLOTS: all recognized equipment slot names
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Valid piece slots
# ---------------------------------------------------------------------------

VALID_PIECE_SLOTS = frozenset({
    "helmet", "chest", "gauntlet", "boot", "pauldron", "cape",
    "belt", "bracer", "ring", "amulet",
})


# ---------------------------------------------------------------------------
# Armor set definitions: 12 sets, 3 per path x 4 paths
# ---------------------------------------------------------------------------

ARMOR_SETS: dict[str, dict[str, Any]] = {
    # === IRONBOUND PATH (tank/defense) ===
    "ironbound_sentinel": {
        "path": "IRONBOUND",
        "tier": "rare",
        "display_name": "Ironbound Sentinel",
        "pieces": {
            "helmet": "full_helm",
            "chest": "plate",
            "gauntlet": "plate",
            "boot": "plate",
            "pauldron": "plate",
            "cape": "half",
        },
        "set_bonuses": {2: "defense_up", 4: "iron_aura", 6: "fortress_mode"},
        "material_tier": "steel",
        "accent_color": (0.55, 0.35, 0.22),
        "lore": "Forged in the foundries of the Iron Citadel, each plate bears the mark of unyielding resolve.",
    },
    "ironbound_guardian": {
        "path": "IRONBOUND",
        "tier": "epic",
        "display_name": "Ironbound Guardian",
        "pieces": {
            "helmet": "full_helm",
            "chest": "plate",
            "gauntlet": "plate",
            "boot": "plate",
            "pauldron": "plate",
            "cape": "full",
            "belt": "chain",
            "bracer": "metal_vambrace",
        },
        "set_bonuses": {2: "shield_wall", 4: "iron_aura", 6: "guardian_oath", 8: "unbreakable"},
        "material_tier": "dark_steel",
        "accent_color": (0.45, 0.42, 0.38),
        "lore": "Guardians stand where others fall. Their armor is their oath made manifest.",
    },
    "ironbound_bulwark": {
        "path": "IRONBOUND",
        "tier": "legendary",
        "display_name": "Ironbound Bulwark",
        "pieces": {
            "helmet": "crown",
            "chest": "plate",
            "gauntlet": "plate",
            "boot": "plate",
            "pauldron": "plate",
            "cape": "full",
            "belt": "ornate",
            "bracer": "metal_vambrace",
            "ring": "signet",
            "amulet": "medallion",
        },
        "set_bonuses": {2: "iron_skin", 4: "iron_aura", 6: "fortress_mode", 8: "unbreakable", 10: "living_fortress"},
        "material_tier": "mythril",
        "accent_color": (0.60, 0.55, 0.45),
        "lore": "The Bulwark set was worn by the last Bastion King. It has never been breached.",
    },

    # === SAVAGE PATH (damage/aggression) ===
    "savage_marauder": {
        "path": "SAVAGE",
        "tier": "rare",
        "display_name": "Savage Marauder",
        "pieces": {
            "helmet": "skull_mask",
            "chest": "leather",
            "gauntlet": "leather",
            "boot": "leather",
            "pauldron": "bone",
            "cape": "tattered",
        },
        "set_bonuses": {2: "bloodlust", 4: "savage_fury", 6: "berserker_rage"},
        "material_tier": "hardened_leather",
        "accent_color": (0.71, 0.18, 0.18),
        "lore": "Stripped from fallen beasts, each piece reeks of blood and conquest.",
    },
    "savage_berserker": {
        "path": "SAVAGE",
        "tier": "epic",
        "display_name": "Savage Berserker",
        "pieces": {
            "helmet": "skull_mask",
            "chest": "chain",
            "gauntlet": "leather",
            "boot": "leather",
            "pauldron": "fur",
            "cape": "tattered",
            "belt": "leather",
            "bracer": "bone",
        },
        "set_bonuses": {2: "bloodlust", 4: "savage_fury", 6: "berserker_rage", 8: "undying_frenzy"},
        "material_tier": "beast_hide",
        "accent_color": (0.65, 0.15, 0.12),
        "lore": "The Berserker knows no retreat. Pain only sharpens the blade.",
    },
    "savage_warlord": {
        "path": "SAVAGE",
        "tier": "legendary",
        "display_name": "Savage Warlord",
        "pieces": {
            "helmet": "open_face",
            "chest": "chain",
            "gauntlet": "plate",
            "boot": "plate",
            "pauldron": "bone",
            "cape": "tattered",
            "belt": "leather",
            "bracer": "bone",
            "ring": "rune_etched",
            "amulet": "torc",
        },
        "set_bonuses": {2: "war_cry", 4: "savage_fury", 6: "berserker_rage", 8: "undying_frenzy", 10: "conquest"},
        "material_tier": "dragon_leather",
        "accent_color": (0.80, 0.20, 0.10),
        "lore": "Warlords carve their legacy in bone and blood. This set is a monument to domination.",
    },

    # === SURGE PATH (magic/elemental) ===
    "surge_stormcaller": {
        "path": "SURGE",
        "tier": "rare",
        "display_name": "Surge Stormcaller",
        "pieces": {
            "helmet": "hood",
            "chest": "robes",
            "gauntlet": "wraps",
            "boot": "sandals",
            "pauldron": "plate",
            "cape": "full",
        },
        "set_bonuses": {2: "mana_surge", 4: "storm_conduit", 6: "tempest_form"},
        "material_tier": "enchanted_silk",
        "accent_color": (0.24, 0.55, 0.86),
        "lore": "Woven with storm-thread, this garb channels the raw fury of the heavens.",
    },
    "surge_arcanist": {
        "path": "SURGE",
        "tier": "epic",
        "display_name": "Surge Arcanist",
        "pieces": {
            "helmet": "crown",
            "chest": "robes",
            "gauntlet": "wraps",
            "boot": "leather",
            "pauldron": "plate",
            "cape": "full",
            "belt": "ornate",
            "bracer": "enchanted",
        },
        "set_bonuses": {2: "mana_surge", 4: "arcane_focus", 6: "spell_echo", 8: "arcane_overload"},
        "material_tier": "astral_weave",
        "accent_color": (0.30, 0.50, 0.90),
        "lore": "Each rune sewn into the Arcanist robes holds a fragment of a forgotten spell.",
    },
    "surge_tempest": {
        "path": "SURGE",
        "tier": "legendary",
        "display_name": "Surge Tempest",
        "pieces": {
            "helmet": "crown",
            "chest": "robes",
            "gauntlet": "wraps",
            "boot": "leather",
            "pauldron": "plate",
            "cape": "full",
            "belt": "ornate",
            "bracer": "enchanted",
            "ring": "gem_set",
            "amulet": "pendant",
        },
        "set_bonuses": {2: "mana_surge", 4: "storm_conduit", 6: "spell_echo", 8: "arcane_overload", 10: "elemental_avatar"},
        "material_tier": "void_woven",
        "accent_color": (0.20, 0.40, 0.95),
        "lore": "The Tempest set bends reality itself. Its wearer becomes the storm.",
    },

    # === VOID PATH (dark/corruption) ===
    "void_shadowblade": {
        "path": "VOID",
        "tier": "rare",
        "display_name": "Void Shadowblade",
        "pieces": {
            "helmet": "hood",
            "chest": "leather",
            "gauntlet": "leather",
            "boot": "leather",
            "pauldron": "bone",
            "cape": "half",
        },
        "set_bonuses": {2: "shadow_step", 4: "void_strike", 6: "umbral_cloak"},
        "material_tier": "shadow_leather",
        "accent_color": (0.16, 0.08, 0.24),
        "lore": "Fashioned from the hides of void-touched beasts, it drinks in light and hope alike.",
    },
    "void_dreadlord": {
        "path": "VOID",
        "tier": "epic",
        "display_name": "Void Dreadlord",
        "pieces": {
            "helmet": "full_helm",
            "chest": "plate",
            "gauntlet": "plate",
            "boot": "plate",
            "pauldron": "plate",
            "cape": "full",
            "belt": "chain",
            "bracer": "metal_vambrace",
        },
        "set_bonuses": {2: "dread_aura", 4: "void_strike", 6: "soul_harvest", 8: "undeath_pact"},
        "material_tier": "corrupted_steel",
        "accent_color": (0.20, 0.10, 0.30),
        "lore": "The Dreadlord armor whispers to its wearer. Most go mad. Some become gods.",
    },
    "void_abyssal": {
        "path": "VOID",
        "tier": "legendary",
        "display_name": "Void Abyssal",
        "pieces": {
            "helmet": "skull_mask",
            "chest": "plate",
            "gauntlet": "plate",
            "boot": "plate",
            "pauldron": "bone",
            "cape": "full",
            "belt": "chain",
            "bracer": "bone",
            "ring": "twisted",
            "amulet": "holy_symbol",
        },
        "set_bonuses": {2: "void_step", 4: "soul_harvest", 6: "umbral_cloak", 8: "undeath_pact", 10: "abyssal_form"},
        "material_tier": "void_touched",
        "accent_color": (0.12, 0.05, 0.20),
        "lore": "To don the Abyssal set is to surrender your humanity. What replaces it is far more terrible.",
    },
}


# Path lookup index
_PATH_INDEX: dict[str, list[str]] = {}
for _set_name, _set_data in ARMOR_SETS.items():
    _path = _set_data["path"]
    _PATH_INDEX.setdefault(_path, []).append(_set_name)

# Valid paths
VALID_PATHS = frozenset(_PATH_INDEX.keys())


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def get_armor_set(set_name: str) -> dict[str, Any]:
    """Retrieve an armor set definition by name.

    Args:
        set_name: Internal set name (e.g. 'ironbound_sentinel').

    Returns:
        Copy of the armor set definition dict.

    Raises:
        ValueError: If the set name is unknown.
    """
    if set_name not in ARMOR_SETS:
        raise ValueError(
            f"Unknown armor set '{set_name}'. "
            f"Valid sets: {sorted(ARMOR_SETS.keys())}"
        )
    return dict(ARMOR_SETS[set_name])


def get_sets_for_path(path_name: str) -> list[dict[str, Any]]:
    """Get all armor sets belonging to a path.

    Args:
        path_name: Path name (e.g. 'IRONBOUND', 'SAVAGE', 'SURGE', 'VOID').

    Returns:
        List of armor set dicts for the path, ordered by tier.

    Raises:
        ValueError: If the path name is unknown.
    """
    path_upper = path_name.upper()
    if path_upper not in _PATH_INDEX:
        raise ValueError(
            f"Unknown path '{path_name}'. "
            f"Valid paths: {sorted(VALID_PATHS)}"
        )
    tier_order = {"rare": 0, "epic": 1, "legendary": 2}
    sets = [dict(ARMOR_SETS[name]) for name in _PATH_INDEX[path_upper]]
    sets.sort(key=lambda s: tier_order.get(s.get("tier", ""), 99))
    return sets


def compute_set_bonus_level(
    equipped_pieces: list[str],
    set_name: str,
) -> int:
    """Compute how many set bonus tiers are active.

    Args:
        equipped_pieces: List of equipped piece slot names
            (e.g. ['helmet', 'chest', 'gauntlet']).
        set_name: Armor set name to check against.

    Returns:
        Number of active bonus tiers (0 if fewer than minimum required).
    """
    armor_set = get_armor_set(set_name)
    set_pieces = armor_set["pieces"]
    bonuses = armor_set["set_bonuses"]

    # Count how many equipped pieces match the set
    matching = sum(1 for piece in equipped_pieces if piece in set_pieces)

    # Count active bonus tiers
    active_tiers = 0
    for threshold in sorted(bonuses.keys()):
        if matching >= threshold:
            active_tiers += 1
        else:
            break

    return active_tiers


def get_active_bonuses(
    equipped_pieces: list[str],
    set_name: str,
) -> list[str]:
    """Get list of active bonus names for equipped pieces.

    Args:
        equipped_pieces: List of equipped piece slot names.
        set_name: Armor set name to check against.

    Returns:
        List of active bonus names in activation order.
    """
    armor_set = get_armor_set(set_name)
    set_pieces = armor_set["pieces"]
    bonuses = armor_set["set_bonuses"]

    matching = sum(1 for piece in equipped_pieces if piece in set_pieces)

    active: list[str] = []
    for threshold in sorted(bonuses.keys()):
        if matching >= threshold:
            active.append(bonuses[threshold])
        else:
            break

    return active


def validate_set_pieces(
    piece_slots: list[str],
    set_name: str,
) -> dict[str, Any]:
    """Validate whether piece slot names are valid for a set.

    Args:
        piece_slots: List of piece slot names to validate.
        set_name: Armor set to validate against.

    Returns:
        Dict with 'valid' bool, 'matching' list, 'invalid' list,
        'missing' list of pieces not equipped.
    """
    armor_set = get_armor_set(set_name)
    set_pieces = set(armor_set["pieces"].keys())

    matching = [p for p in piece_slots if p in set_pieces]
    invalid = [p for p in piece_slots if p not in VALID_PIECE_SLOTS]
    not_in_set = [p for p in piece_slots if p in VALID_PIECE_SLOTS and p not in set_pieces]
    missing = [p for p in set_pieces if p not in piece_slots]

    return {
        "valid": len(invalid) == 0,
        "matching": matching,
        "invalid": invalid,
        "not_in_set": not_in_set,
        "missing": missing,
        "set_total_pieces": len(set_pieces),
        "equipped_matching": len(matching),
    }
