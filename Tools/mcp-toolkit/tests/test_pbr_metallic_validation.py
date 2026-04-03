"""PBR Metallic Binary Validation Tests.

Verifies that all material definition files follow PBR binary rules:
  - Metals MUST have metallic=1.0 (conductors absorb light differently)
  - Dielectrics MUST have metallic=0.0
  - Any value strictly between 0.0 and 1.0 is a PBR violation (renders incorrectly)

Files scanned:
  - blender_addon/handlers/material_tiers.py
  - blender_addon/handlers/procedural_materials.py
  - blender_addon/handlers/texture_quality.py
  - blender_addon/handlers/terrain_materials.py

Background: In physically-based rendering, metallic is a binary property.
Real-world materials are either conductors (metals, metallic=1.0) or dielectrics
(everything else, metallic=0.0). Intermediate values (0.1-0.9) produce physically
incorrect results — blended specular/diffuse that doesn't exist in nature.
Non-binary metallic values are a common AAA quality violation.

VIOLATION TRACKING STRATEGY:
  - Known violations are tracked in _*_VIOLATIONS_EXPECTED sets/dicts.
  - Parametrized tests use xfail for entries that are currently wrong.
  - "no_unknown_violations" guard tests catch NEW regressions not in the known set.
  - When violations are fixed, remove them from both the tracking set and xfail.
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.material_tiers import (
    METAL_TIERS,
    WOOD_TIERS,
    LEATHER_TIERS,
    CLOTH_TIERS,
)
from blender_addon.handlers.procedural_materials import MATERIAL_LIBRARY
from blender_addon.handlers.texture_quality import (
    SMART_MATERIAL_PRESETS,
    TRIM_ELEMENT_PBR,
)
from blender_addon.handlers.terrain_materials import TERRAIN_MATERIALS, BIOME_PALETTES_V2


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _is_binary(value: float) -> bool:
    """Return True if value is exactly 0.0 or 1.0 (within float epsilon)."""
    return abs(value - 0.0) < 1e-9 or abs(value - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# material_tiers.py -- METAL_TIERS
# ---------------------------------------------------------------------------

# These are the canonical metal names from METAL_TIERS.
# Per PBR rules, all conductors must have metallic=1.0.
_METAL_TIER_NAMES = [
    "iron",
    "steel",
    "silver",
    "gold",
    "mithril",
    "adamantine",
    "orichalcum",
]

# Known conductor violations: these should be 1.0 but aren't yet fixed.
# Remove entries from this dict when the source values are corrected.
_CONDUCTOR_VIOLATIONS = {
    "iron":       0.85,   # BUG: should be 1.0 — rust/weathering is roughness, not metallic drop
    "steel":      0.90,   # BUG: should be 1.0
    "silver":     0.95,   # BUG: should be 1.0
    "gold":       0.95,   # BUG: should be 1.0
    "mithril":    0.98,   # BUG: should be 1.0
    "adamantine": 0.99,   # BUG: should be 1.0
    "orichalcum": 0.92,   # BUG: should be 1.0
}

# These are labeled as metals in METAL_TIERS but are actually dielectrics
# by their physical material type (volcanic glass, bone). They should be
# metallic=0.0 per PBR rules regardless of which dict they live in.
_METAL_TIERS_DIELECTRIC_NAMES = [
    "obsidian",    # volcanic glass -- dielectric
    "dragonbone",  # bone material -- dielectric
]

# Known dielectric violations in METAL_TIERS.
_METAL_TIERS_DIELECTRIC_VIOLATIONS = {
    "obsidian":   0.3,   # BUG: volcanic glass is dielectric, should be 0.0
    "dragonbone": 0.4,   # BUG: bone is dielectric, should be 0.0
}

# Void-touched is a supernatural special-case: the current value (0.60)
# is a PBR violation regardless of lore justification. It should be 1.0
# (metal distorted by void) or 0.0 (non-metallic warped by magic), not 0.60.
_METAL_TIERS_VIOLATIONS_EXPECTED = {
    "void_touched",   # metallic=0.60 -- physically invalid blend
    # All conductor violations are also known:
    *_CONDUCTOR_VIOLATIONS.keys(),
    # Dielectric violations are also known:
    *_METAL_TIERS_DIELECTRIC_VIOLATIONS.keys(),
}


@pytest.mark.parametrize("tier_name", _METAL_TIER_NAMES)
def test_metal_tiers_conductors_have_metallic_1(tier_name: str) -> None:
    """Real metal tiers (iron, steel, silver, etc.) must be metallic=1.0."""
    tier = METAL_TIERS[tier_name]
    metallic = tier.get("metallic", 0.0)
    if tier_name in _CONDUCTOR_VIOLATIONS:
        pytest.xfail(
            f"Known violation: METAL_TIERS[{tier_name!r}] metallic={metallic} "
            f"(expected 1.0 for conductor — fix: set metallic=1.0, encode "
            f"weathering via roughness instead)"
        )
    assert abs(metallic - 1.0) < 1e-9, (
        f"METAL_TIERS[{tier_name!r}]: metallic={metallic} — "
        f"expected 1.0 for conductor. PBR violation."
    )


@pytest.mark.parametrize("tier_name", _METAL_TIERS_DIELECTRIC_NAMES)
def test_metal_tiers_dielectrics_have_metallic_0(tier_name: str) -> None:
    """Dielectric materials in METAL_TIERS (obsidian=glass, dragonbone=bone)
    must be metallic=0.0, not a partial metallic value."""
    tier = METAL_TIERS[tier_name]
    metallic = tier.get("metallic", 0.0)
    if tier_name in _METAL_TIERS_DIELECTRIC_VIOLATIONS:
        pytest.xfail(
            f"Known violation: METAL_TIERS[{tier_name!r}] metallic={metallic} "
            f"(expected 0.0 for dielectric)"
        )
    assert abs(metallic - 0.0) < 1e-9, (
        f"METAL_TIERS[{tier_name!r}]: metallic={metallic} — "
        f"expected 0.0 for dielectric. PBR violation."
    )


def test_metal_tiers_no_unknown_violations() -> None:
    """Every entry in METAL_TIERS must have a binary metallic value.

    Known PBR violations are listed in _METAL_TIERS_VIOLATIONS_EXPECTED.
    Any new non-binary value that is NOT in that set is a new regression.
    """
    new_violations = []
    for name, tier in METAL_TIERS.items():
        metallic = tier.get("metallic", 0.0)
        if not _is_binary(metallic) and name not in _METAL_TIERS_VIOLATIONS_EXPECTED:
            new_violations.append((name, metallic))

    assert not new_violations, (
        "New PBR violations found in METAL_TIERS (metallic not 0.0 or 1.0):\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in new_violations)
    )


# ---------------------------------------------------------------------------
# material_tiers.py -- WOOD_TIERS, LEATHER_TIERS, CLOTH_TIERS (all dielectrics)
# ---------------------------------------------------------------------------

# Known violations in wood/leather/cloth tiers.
_WOOD_LEATHER_CLOTH_VIOLATIONS_EXPECTED = {
    "ironwood",       # metallic=0.15 -- wood is a dielectric
    "dragon_leather", # metallic=0.15 -- leather is a dielectric
}


@pytest.mark.parametrize("tier_name,tier_data", list(WOOD_TIERS.items()))
def test_wood_tiers_are_dielectric(tier_name: str, tier_data: dict) -> None:
    """Wood is a dielectric -- metallic must be 0.0."""
    metallic = tier_data.get("metallic", 0.0)
    if tier_name in _WOOD_LEATHER_CLOTH_VIOLATIONS_EXPECTED:
        pytest.xfail(
            f"Known violation: WOOD_TIERS[{tier_name!r}] metallic={metallic}"
        )
    assert abs(metallic - 0.0) < 1e-9, (
        f"WOOD_TIERS[{tier_name!r}]: metallic={metallic} — "
        f"wood is a dielectric, expected metallic=0.0. PBR violation."
    )


@pytest.mark.parametrize("tier_name,tier_data", list(LEATHER_TIERS.items()))
def test_leather_tiers_are_dielectric(tier_name: str, tier_data: dict) -> None:
    """Leather is a dielectric -- metallic must be 0.0."""
    metallic = tier_data.get("metallic", 0.0)
    if tier_name in _WOOD_LEATHER_CLOTH_VIOLATIONS_EXPECTED:
        pytest.xfail(
            f"Known violation: LEATHER_TIERS[{tier_name!r}] metallic={metallic}"
        )
    assert abs(metallic - 0.0) < 1e-9, (
        f"LEATHER_TIERS[{tier_name!r}]: metallic={metallic} — "
        f"leather is a dielectric, expected metallic=0.0. PBR violation."
    )


@pytest.mark.parametrize("tier_name,tier_data", list(CLOTH_TIERS.items()))
def test_cloth_tiers_are_dielectric(tier_name: str, tier_data: dict) -> None:
    """Cloth is a dielectric -- metallic must be 0.0."""
    metallic = tier_data.get("metallic", 0.0)
    assert abs(metallic - 0.0) < 1e-9, (
        f"CLOTH_TIERS[{tier_name!r}]: metallic={metallic} — "
        f"cloth is a dielectric, expected metallic=0.0. PBR violation."
    )


# ---------------------------------------------------------------------------
# procedural_materials.py -- MATERIAL_LIBRARY
# ---------------------------------------------------------------------------

# Metal entries in MATERIAL_LIBRARY that must be metallic=1.0.
_PROC_METAL_NAMES = [
    "polished_steel",
    "gold_ornament",
]

# Known violations in MATERIAL_LIBRARY metals (non-binary values that are
# currently in the codebase and tracked as tech debt).
_PROC_MATERIAL_VIOLATIONS_EXPECTED = {
    "rusted_iron":       0.85,   # should be 1.0 (rust affects roughness, not metallicity)
    "tarnished_bronze":  0.90,   # should be 1.0
    "chain_metal":       0.95,   # should be 1.0
    "scales":            0.1,    # creature scales are dielectric
    "chitin_carapace":   0.15,   # chitin is dielectric
    "corruption_overlay": 0.1,   # supernatural overlay -- should be 0.0
    "ice_crystal":       0.05,   # ice is dielectric -- should be 0.0
    "glass":             0.05,   # glass is dielectric -- should be 0.0
}


@pytest.mark.parametrize("mat_name", _PROC_METAL_NAMES)
def test_proc_library_pure_metals_are_metallic_1(mat_name: str) -> None:
    """Pure metal presets in MATERIAL_LIBRARY must have metallic=1.0."""
    mat = MATERIAL_LIBRARY[mat_name]
    metallic = mat.get("metallic", 0.0)
    assert abs(metallic - 1.0) < 1e-9, (
        f"MATERIAL_LIBRARY[{mat_name!r}]: metallic={metallic} — "
        f"expected 1.0 for pure metal. PBR violation."
    )


def test_proc_library_no_unknown_violations() -> None:
    """All MATERIAL_LIBRARY entries must have binary metallic values.

    Known violations are in _PROC_MATERIAL_VIOLATIONS_EXPECTED.
    New non-binary metallic values are regressions.
    """
    new_violations = []
    for name, mat in MATERIAL_LIBRARY.items():
        metallic = mat.get("metallic", 0.0)
        if not _is_binary(metallic) and name not in _PROC_MATERIAL_VIOLATIONS_EXPECTED:
            new_violations.append((name, metallic))

    assert not new_violations, (
        "New PBR violations in MATERIAL_LIBRARY (metallic not 0.0 or 1.0):\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in new_violations)
    )


def test_proc_library_stone_dielectrics() -> None:
    """Stone materials must be metallic=0.0."""
    stone_names = [k for k, v in MATERIAL_LIBRARY.items()
                   if v.get("node_recipe") == "stone"]
    violations = [
        (n, MATERIAL_LIBRARY[n]["metallic"])
        for n in stone_names
        if not abs(MATERIAL_LIBRARY[n].get("metallic", 0.0)) < 1e-9
        and n not in _PROC_MATERIAL_VIOLATIONS_EXPECTED
    ]
    assert not violations, (
        "Stone materials in MATERIAL_LIBRARY with metallic != 0.0 (new violations):\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in violations)
    )


def test_proc_library_wood_dielectrics() -> None:
    """Wood materials must be metallic=0.0."""
    wood_names = [k for k, v in MATERIAL_LIBRARY.items()
                  if v.get("node_recipe") == "wood"]
    violations = [
        (n, MATERIAL_LIBRARY[n]["metallic"])
        for n in wood_names
        if not abs(MATERIAL_LIBRARY[n].get("metallic", 0.0)) < 1e-9
        and n not in _PROC_MATERIAL_VIOLATIONS_EXPECTED
    ]
    assert not violations, (
        "Wood materials in MATERIAL_LIBRARY with metallic != 0.0 (new violations):\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in violations)
    )


# ---------------------------------------------------------------------------
# texture_quality.py -- SMART_MATERIAL_PRESETS
# ---------------------------------------------------------------------------

# Metal smart material presets that must be metallic=1.0.
_SMART_PURE_METALS = [
    "polished_steel",
]

# Known violations in SMART_MATERIAL_PRESETS.
_SMART_VIOLATIONS_EXPECTED = {
    "rusted_armor":   0.95,  # should be 1.0 (rust = roughness increase, not metallic drop)
    "tarnished_gold": 0.95,  # should be 1.0
    "aged_bronze":    0.90,  # should be 1.0
    "rusted_iron":    0.85,  # should be 1.0
    "obsidian":       0.05,  # volcanic glass is dielectric, should be 0.0
    "chitin":         0.12,  # chitin is dielectric, should be 0.0
    "ice":            0.02,  # ice is dielectric, should be 0.0
    "crystal":        0.05,  # crystal is dielectric, should be 0.0
}


@pytest.mark.parametrize("mat_name", _SMART_PURE_METALS)
def test_smart_presets_pure_metals_are_metallic_1(mat_name: str) -> None:
    """Pure metal smart material presets must have metallic=1.0."""
    mat = SMART_MATERIAL_PRESETS[mat_name]
    metallic = mat.get("metallic", 0.0)
    assert abs(metallic - 1.0) < 1e-9, (
        f"SMART_MATERIAL_PRESETS[{mat_name!r}]: metallic={metallic} — "
        f"expected 1.0. PBR violation."
    )


def test_smart_presets_stone_and_wood_are_dielectric() -> None:
    """Stone and wood smart material presets must have metallic=0.0."""
    violations = []
    for name, mat in SMART_MATERIAL_PRESETS.items():
        if mat.get("category") in ("stone", "wood"):
            metallic = mat.get("metallic", 0.0)
            if not abs(metallic - 0.0) < 1e-9:
                if name not in _SMART_VIOLATIONS_EXPECTED:
                    violations.append((name, metallic))
    assert not violations, (
        "Stone/wood smart presets with metallic != 0.0 (new violations):\n"
        + "\n".join(f"  {n!r} (stone/wood): metallic={v}" for n, v in violations)
    )


def test_smart_presets_no_unknown_violations() -> None:
    """All SMART_MATERIAL_PRESETS must have binary metallic values.

    Known violations are tracked in _SMART_VIOLATIONS_EXPECTED.
    """
    new_violations = []
    for name, mat in SMART_MATERIAL_PRESETS.items():
        metallic = mat.get("metallic", 0.0)
        if not _is_binary(metallic) and name not in _SMART_VIOLATIONS_EXPECTED:
            new_violations.append((name, metallic))

    assert not new_violations, (
        "New PBR violations in SMART_MATERIAL_PRESETS (metallic not 0.0 or 1.0):\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in new_violations)
    )


# Known TRIM_ELEMENT_PBR violations (metal trim elements using non-binary values).
_TRIM_VIOLATIONS_EXPECTED = {
    "metal_strap":    0.90,   # BUG: conductor should be 1.0
    "metal_nail_row": 0.85,   # BUG: conductor should be 1.0
    "chain_link":     0.92,   # BUG: conductor should be 1.0
}


def test_trim_element_metals_are_binary() -> None:
    """Trim sheet PBR metal entries (metal_strap, metal_nail_row, chain_link)
    must have binary metallic values. Known violations are tracked; this test
    catches NEW violations introduced by future edits."""
    new_violations = []
    for name, pbr in TRIM_ELEMENT_PBR.items():
        metallic = pbr.get("metallic", 0.0)
        if not _is_binary(metallic) and name not in _TRIM_VIOLATIONS_EXPECTED:
            new_violations.append((name, metallic))
    assert not new_violations, (
        "New non-binary metallic values in TRIM_ELEMENT_PBR:\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in new_violations)
    )


def test_trim_element_known_violations_documented() -> None:
    """Verify that known TRIM_ELEMENT_PBR violations still exist as expected.

    If a known violation is fixed, remove it from _TRIM_VIOLATIONS_EXPECTED.
    This test ensures the tracking set stays accurate.
    """
    for name, expected_value in _TRIM_VIOLATIONS_EXPECTED.items():
        if name not in TRIM_ELEMENT_PBR:
            continue  # entry was removed entirely — ok
        actual = TRIM_ELEMENT_PBR[name].get("metallic", 0.0)
        if _is_binary(actual):
            pytest.fail(
                f"TRIM_ELEMENT_PBR[{name!r}] was fixed (metallic={actual}) — "
                f"remove it from _TRIM_VIOLATIONS_EXPECTED"
            )


# ---------------------------------------------------------------------------
# terrain_materials.py -- TERRAIN_MATERIAL_LIBRARY
# ---------------------------------------------------------------------------

# Known non-binary metallic values in TERRAIN_MATERIALS.
# These are special-effect terrain zones (crystal, void, ice, geode) where
# partial metallic is used as a visual shortcut. All are tracked violations.
_TERRAIN_VIOLATIONS_EXPECTED = {
    "ice",
    "fractured_earth_glow",
    "void_touched_stone",
    "crystal_surface",
    "reality_torn_rock",
    "void_energy_pool",
    "bioluminescent_stone",
    "geode_floor",
    "crystal_dust",
    "prismatic_rock",
    "crystal_wall",
    "mineral_pool",
}

# Known BIOME_PALETTES_V2 layer violations (biome.layer format).
_BIOME_VIOLATIONS_EXPECTED = {
    "ruined_fortress.special",
    "veil_crack_zone.slope",
    "veil_crack_zone.special",
    "mushroom_forest.cliff",
    "crystal_cavern.ground",
    "crystal_cavern.slope",
    "crystal_cavern.cliff",
    "crystal_cavern.special",
}


def test_terrain_materials_no_unknown_violations() -> None:
    """All TERRAIN_MATERIALS entries must have binary metallic values.

    Terrain materials are all dielectrics (stone, soil, vegetation, water).
    Fractional metallic on terrain materials causes incorrect specular response
    at grazing angles and makes terrain look like polished plastic.

    Known special-effect zones are listed in _TERRAIN_VIOLATIONS_EXPECTED.
    This test catches NEW violations introduced by future edits.
    """
    new_violations = []
    for name, mat in TERRAIN_MATERIALS.items():
        if not isinstance(mat, dict):
            continue
        metallic = mat.get("metallic", 0.0)
        if not _is_binary(metallic) and name not in _TERRAIN_VIOLATIONS_EXPECTED:
            new_violations.append((name, metallic))

    assert not new_violations, (
        "New TERRAIN_MATERIALS entries with non-binary metallic values "
        "(all terrain is dielectric):\n"
        + "\n".join(f"  {n!r}: metallic={v}" for n, v in new_violations)
    )


def test_biome_palettes_v2_no_unknown_violations() -> None:
    """All BIOME_PALETTES_V2 layer entries must have binary metallic values.

    The V2 per-layer palette system covers all biomes. Every layer
    (ground/slope/cliff/special) is a dielectric terrain surface.

    Known violations are in _BIOME_VIOLATIONS_EXPECTED. This test catches
    new violations in future biome additions.
    """
    new_violations = []
    for biome_name, layers in BIOME_PALETTES_V2.items():
        for layer_name, mat in layers.items():
            if not isinstance(mat, dict):
                continue
            metallic = mat.get("metallic", 0.0)
            loc = f"{biome_name}.{layer_name}"
            if not _is_binary(metallic) and loc not in _BIOME_VIOLATIONS_EXPECTED:
                new_violations.append((loc, metallic))

    assert not new_violations, (
        "New BIOME_PALETTES_V2 layers with non-binary metallic values:\n"
        + "\n".join(f"  {loc!r}: metallic={v}" for loc, v in new_violations)
    )
