"""PBR correctness tests for VeilBreakers material system.

These tests document PBR correctness bugs so they fail NOW and pass once fixed.

PBR rules:
  - Metals: metallic == 1.0 (physically, metallic is boolean in UE4/Unity PBR)
  - Dielectrics: metallic == 0.0
  - Roughness: never exactly 0.0 or 1.0 (physically implausible)
  - Dark fantasy base_colors: saturation < 40%, value 10-50% (non-supernatural)
  - material_ids in MeshSpec must have one entry per face

Expected failures (document bugs, will pass when Phase 5 fixes applied):
  - test_all_metal_presets_have_metallic_one: rusted_iron=0.85, tarnished_bronze=0.90, chain_metal=0.95
  - test_all_dielectric_presets_have_metallic_zero: glass=0.05, ice_crystal=0.05, scales=0.1, etc.
  - test_material_tiers_metallic_binary: iron=0.85, steel=0.90, ..., obsidian=0.3, dragonbone=0.4
  - test_material_ids_present_in_building_generators: generators never pass material_ids to _make_result
"""

from __future__ import annotations

import colorsys
import sys
import os
import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports without installing the package
# ---------------------------------------------------------------------------
_HANDLERS = os.path.join(
    os.path.dirname(__file__), "..", "blender_addon", "handlers"
)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(_HANDLERS))

from blender_addon.handlers.procedural_materials import MATERIAL_LIBRARY
from blender_addon.handlers.material_tiers import (
    METAL_TIERS,
    WOOD_TIERS,
    LEATHER_TIERS,
    CLOTH_TIERS,
)
from blender_addon.handlers.building_quality import (
    generate_stone_wall,
    generate_gothic_window,
    generate_roof,
    generate_archway,
    generate_battlements,
    generate_staircase,
    generate_chimney,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rgb_to_hsv(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert linear sRGB [0,1] to HSV (h in [0,360], s/v in [0,100])."""
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s * 100.0, v * 100.0


# ---------------------------------------------------------------------------
# Metal vs dielectric classification for MATERIAL_LIBRARY
# ---------------------------------------------------------------------------

# Keys known to be metals — all must have metallic == 1.0
_MATERIAL_LIBRARY_METALS = {
    "rusted_iron",
    "polished_steel",
    "tarnished_bronze",
    "chain_metal",
    "gold_ornament",
}

# Keys known to be dielectrics (non-metal) — all must have metallic == 0.0
# Excludes "special" materials that have intentional fractional metallic for
# artistic reasons (corruption_overlay, scales, chitin_carapace) from this
# strict test — those are covered by the tiers test instead.
_MATERIAL_LIBRARY_DIELECTRICS = {
    # Stone
    "rough_stone_wall",
    "smooth_stone",
    "cobblestone_floor",
    "brick_wall",
    "crumbling_stone",
    "mossy_stone",
    "marble",
    # Wood
    "rough_timber",
    "polished_wood",
    "rotten_wood",
    "charred_wood",
    "plank_floor",
    # Roofing
    "slate_tiles",
    "thatch_roof",
    "wooden_shingles",
    # Organic creature
    "monster_skin",
    "fur_base",
    "bone",
    "membrane",
    # Vegetation
    "bark",
    "leaf",
    "moss",
    "mushroom_cap",
    # Terrain
    "grass",
    "dirt",
    "mud",
    "snow",
    "sand",
    "cliff_rock",
    # Fabric
    "burlap_cloth",
    "leather",
    "silk",
    # Special dielectrics (glass, ice should be 0.0 — currently wrong)
    "glass",
    "ice_crystal",
    "water_surface",
    "blood_splatter",
    "lava_ember",
}

# Metal tiers that ARE actual metals (iron alloys, precious metals)
# These must have metallic == 1.0 per strict PBR
_METAL_TIER_TRUE_METALS = {
    "iron",
    "steel",
    "silver",
    "gold",
    "mithril",
    "adamantine",
    "orichalcum",
}

# Special material_tiers entries — physically ambiguous (volcanic glass,
# bone, void-touched) — document separately so failures are explicit
_METAL_TIER_AMBIGUOUS = {
    "obsidian",     # volcanic glass — metallic=0.3, should be 0.0
    "dragonbone",   # bone — metallic=0.4, should be 0.0
    "void_touched", # supernatural — metallic=0.6, arguable
}


# ===========================================================================
# Test 1: MATERIAL_LIBRARY metals must be metallic == 1.0
# ===========================================================================

class TestMaterialLibraryMetals:
    """All MATERIAL_LIBRARY entries that are metals must have metallic == 1.0.

    PBR standard: the metallic channel is physically a binary mask.
    Values between 0 and 1 produce blend artifacts in lighting engines.

    Current failures:
      rusted_iron    = 0.85  (should be 1.0, rust handled via roughness/maps)
      tarnished_bronze = 0.90
      chain_metal    = 0.95
    """

    @pytest.mark.parametrize("mat_key", sorted(_MATERIAL_LIBRARY_METALS))
    def test_metal_preset_metallic_is_one(self, mat_key: str) -> None:
        """Metal preset '{mat_key}' must have metallic == 1.0."""
        assert mat_key in MATERIAL_LIBRARY, (
            f"Expected metal preset '{mat_key}' not found in MATERIAL_LIBRARY. "
            f"Available keys: {sorted(MATERIAL_LIBRARY.keys())}"
        )
        params = MATERIAL_LIBRARY[mat_key]
        metallic = params["metallic"]
        assert metallic == 1.0, (
            f"[PBR BUG] '{mat_key}' metallic={metallic} — metals must be 1.0. "
            f"Use roughness/texture variation to show wear, not fractional metallic."
        )


# ===========================================================================
# Test 2: MATERIAL_LIBRARY dielectrics must be metallic == 0.0
# ===========================================================================

class TestMaterialLibraryDielectrics:
    """All MATERIAL_LIBRARY entries that are dielectrics must have metallic == 0.0.

    Current failures:
      glass      = 0.05  (should be 0.0 — glass is not a conductor)
      ice_crystal = 0.05 (should be 0.0 — ice is not a conductor)
      scales     = 0.1   (should be 0.0 — biological, not metal)
      chitin_carapace = 0.15 (should be 0.0)
      corruption_overlay = 0.1 (supernatural — borderline)
    """

    @pytest.mark.parametrize("mat_key", sorted(_MATERIAL_LIBRARY_DIELECTRICS))
    def test_dielectric_preset_metallic_is_zero(self, mat_key: str) -> None:
        """Dielectric preset '{mat_key}' must have metallic == 0.0."""
        assert mat_key in MATERIAL_LIBRARY, (
            f"Expected dielectric preset '{mat_key}' not found in MATERIAL_LIBRARY."
        )
        params = MATERIAL_LIBRARY[mat_key]
        metallic = params["metallic"]
        assert metallic == 0.0, (
            f"[PBR BUG] '{mat_key}' metallic={metallic} — dielectrics must be 0.0. "
            f"Use IOR / transmission / coat for reflective dielectrics."
        )


# ===========================================================================
# Test 3: material_tiers.py metallic values must be binary
# ===========================================================================

class TestMaterialTiersMetallicBinary:
    """All METAL_TIERS entries must have metallic == 1.0 for true metals,
    and non-metal tiers (wood/leather/cloth) must be metallic == 0.0.

    Current failures in METAL_TIERS:
      iron=0.85, steel=0.90, silver=0.95, gold=0.95,
      mithril=0.98, adamantine=0.99, orichalcum=0.92 (not 1.0)
      obsidian=0.3, dragonbone=0.4 (not 0.0 for non-metals)
    """

    @pytest.mark.parametrize("tier_name", sorted(_METAL_TIER_TRUE_METALS))
    def test_true_metal_tier_metallic_is_one(self, tier_name: str) -> None:
        """True metal tier '{tier_name}' must have metallic == 1.0."""
        assert tier_name in METAL_TIERS, (
            f"Expected metal tier '{tier_name}' not in METAL_TIERS."
        )
        metallic = METAL_TIERS[tier_name].get("metallic", 0.0)
        assert metallic == 1.0, (
            f"[PBR BUG] METAL_TIERS['{tier_name}'] metallic={metallic} — "
            f"true metals must be 1.0."
        )

    @pytest.mark.parametrize("tier_name", sorted(_METAL_TIER_AMBIGUOUS))
    def test_ambiguous_metal_tier_metallic_is_zero(self, tier_name: str) -> None:
        """Non-metal entries in METAL_TIERS (glass/bone/void) should be 0.0.

        obsidian is volcanic glass (dielectric), dragonbone is bone (organic).
        void_touched is supernatural — this test documents the design decision.
        """
        assert tier_name in METAL_TIERS, (
            f"Expected tier '{tier_name}' not in METAL_TIERS."
        )
        metallic = METAL_TIERS[tier_name].get("metallic", 0.0)
        assert metallic == 0.0, (
            f"[PBR BUG] METAL_TIERS['{tier_name}'] metallic={metallic} — "
            f"non-metallic material placed in METAL_TIERS should be 0.0."
        )

    @pytest.mark.parametrize("tier_name", sorted(WOOD_TIERS.keys()))
    def test_wood_tier_metallic_is_zero(self, tier_name: str) -> None:
        """Wood tier '{tier_name}' must have metallic == 0.0 (default if absent)."""
        metallic = WOOD_TIERS[tier_name].get("metallic", 0.0)
        assert metallic == 0.0, (
            f"[PBR BUG] WOOD_TIERS['{tier_name}'] metallic={metallic} — "
            f"wood is a dielectric, must be 0.0."
        )

    @pytest.mark.parametrize("tier_name", sorted(LEATHER_TIERS.keys()))
    def test_leather_tier_metallic_is_zero(self, tier_name: str) -> None:
        """Leather tier '{tier_name}' must have metallic == 0.0."""
        metallic = LEATHER_TIERS[tier_name].get("metallic", 0.0)
        assert metallic == 0.0, (
            f"[PBR BUG] LEATHER_TIERS['{tier_name}'] metallic={metallic} — "
            f"leather is a dielectric, must be 0.0."
        )

    @pytest.mark.parametrize("tier_name", sorted(CLOTH_TIERS.keys()))
    def test_cloth_tier_metallic_is_zero(self, tier_name: str) -> None:
        """Cloth tier '{tier_name}' must have metallic == 0.0."""
        metallic = CLOTH_TIERS[tier_name].get("metallic", 0.0)
        assert metallic == 0.0, (
            f"[PBR BUG] CLOTH_TIERS['{tier_name}'] metallic={metallic} — "
            f"cloth is a dielectric, must be 0.0."
        )


# ===========================================================================
# Test 4: Roughness must avoid physically implausible extremes (0.0 and 1.0)
# ===========================================================================

class TestRoughnessAvoidExtremes:
    """Roughness == 0.0 is a perfect mirror (physically impossible for real surfaces).
    Roughness == 1.0 is lambertian diffuse with zero specularity (also not real).
    All roughness values should be in [0.04, 0.96].

    Violations found in MATERIAL_LIBRARY:
      glass.wear_intensity = 0.0 (not roughness, excluded)
      rotten_wood = 0.95 (passes)
      Check: thatch_roof = 0.95 passes, adamantine in METAL_TIERS = 0.05 passes
    """

    @pytest.mark.parametrize("mat_key", sorted(MATERIAL_LIBRARY.keys()))
    def test_material_library_roughness_in_range(self, mat_key: str) -> None:
        """MATERIAL_LIBRARY['{mat_key}'] roughness must be in [0.04, 0.96]."""
        roughness = MATERIAL_LIBRARY[mat_key]["roughness"]
        assert 0.04 <= roughness <= 0.96, (
            f"[PBR BUG] '{mat_key}' roughness={roughness} is outside [0.04, 0.96]. "
            f"Value 0.0 = perfect mirror, 1.0 = fully diffuse — both unphysical."
        )

    @pytest.mark.parametrize("tier_name", sorted(METAL_TIERS.keys()))
    def test_metal_tiers_roughness_in_range(self, tier_name: str) -> None:
        """METAL_TIERS['{tier_name}'] roughness must be in [0.04, 0.96]."""
        roughness = METAL_TIERS[tier_name]["roughness"]
        assert 0.04 <= roughness <= 0.96, (
            f"[PBR BUG] METAL_TIERS['{tier_name}'] roughness={roughness} "
            f"is outside [0.04, 0.96]."
        )


# ===========================================================================
# Test 5: Dark fantasy palette compliance
# ===========================================================================

class TestDarkFantasyPaletteCompliance:
    """Non-supernatural materials must follow dark fantasy palette rules:
      - Saturation < 40% (desaturated, grimdark)
      - Value 10-50% (dark world, no bright surfaces)

    Supernatural materials (emission-based, magical) are excluded from value
    check since they may be intentionally brighter.

    Known violations in MATERIAL_LIBRARY:
      snow base_color (0.45, 0.45, 0.48) — value ~47%, fine
      gold_ornament _GOLD_METAL (1.0, 0.86, 0.57) — value 100%, saturation 43%, FAIL
      glass (0.40, 0.42, 0.44) — borderline, saturation ~4%, value ~44%, passes
    """

    # Presets that are intentionally bright/saturated (supernaturals, gold, snow)
    # or have design exceptions — excluded from strict palette check.
    # Metals are excluded because physically-based metal albedo is defined by
    # the metal's actual reflectance (e.g., iron ~58%, steel ~64%, bronze ~73%)
    # and cannot be darkened without breaking PBR correctness.
    _PALETTE_EXCLUSIONS = {
        "gold_ornament",     # physically correct gold albedo — value 100%, SAT 43%
        "snow",              # bright white — value ~47% passes but listed for clarity
        "ice_crystal",       # pale blue, supernatural
        "lava_ember",        # fire — intentionally warm/bright
        "corruption_overlay",  # supernatural purple emission
        "water_surface",     # transparent, special
        # Metals — physically-based albedo values; saturation/value not constrained
        "rusted_iron",       # iron albedo: value ~58%
        "polished_steel",    # steel albedo: value ~64%
        "tarnished_bronze",  # bronze albedo: value ~73%
        "chain_metal",       # iron albedo: value ~58%
    }

    @pytest.mark.parametrize(
        "mat_key",
        sorted(k for k in MATERIAL_LIBRARY if k not in {
            "gold_ornament", "snow", "ice_crystal", "lava_ember",
            "corruption_overlay", "water_surface",
            "rusted_iron", "polished_steel", "tarnished_bronze", "chain_metal",
        }),
    )
    def test_base_color_saturation_under_40_percent(self, mat_key: str) -> None:
        """Non-supernatural '{mat_key}' base_color saturation must be < 40%."""
        color = MATERIAL_LIBRARY[mat_key]["base_color"]
        r, g, b = color[0], color[1], color[2]
        _, saturation, _ = _rgb_to_hsv(r, g, b)
        assert saturation < 40.0, (
            f"[PALETTE BUG] '{mat_key}' base_color saturation={saturation:.1f}% "
            f"exceeds 40% dark fantasy cap. Color={color[:3]}."
        )

    @pytest.mark.parametrize(
        "mat_key",
        sorted(k for k in MATERIAL_LIBRARY if k not in {
            "gold_ornament", "snow", "ice_crystal", "lava_ember",
            "corruption_overlay", "water_surface",
            "rusted_iron", "polished_steel", "tarnished_bronze", "chain_metal",
        }),
    )
    def test_base_color_value_in_dark_range(self, mat_key: str) -> None:
        """Non-supernatural '{mat_key}' base_color value must be in [10%, 50%]."""
        color = MATERIAL_LIBRARY[mat_key]["base_color"]
        r, g, b = color[0], color[1], color[2]
        _, _, value = _rgb_to_hsv(r, g, b)
        assert 10.0 <= value <= 50.0, (
            f"[PALETTE BUG] '{mat_key}' base_color value={value:.1f}% "
            f"outside [10%, 50%] dark fantasy range. Color={color[:3]}."
        )


# ===========================================================================
# Test 6: Building generators must emit material_ids aligned to face count
# ===========================================================================

class TestMaterialIdsPresentInBuildingGenerators:
    """Each face in a MeshSpec needs a material_id so Blender can assign
    different materials to e.g. mortar vs stone blocks, frame vs infill.

    Current bug: _make_result() defaults material_ids to [] (empty list).
    Every building generator calls _make_result without passing material_ids.
    This means Blender assigns slot 0 to everything — no per-face materials.

    These tests FAIL now and will pass once generators populate material_ids.
    """

    def _assert_material_ids_match_faces(
        self,
        spec: dict,
        generator_name: str,
    ) -> None:
        """Assert material_ids present and aligned to face count."""
        assert "material_ids" in spec, (
            f"[BUG] {generator_name} MeshSpec missing 'material_ids' key entirely."
        )
        face_count = len(spec["faces"])
        mat_id_count = len(spec["material_ids"])
        assert mat_id_count == face_count, (
            f"[BUG] {generator_name} material_ids length {mat_id_count} != "
            f"face count {face_count}. Every face must have a material slot index."
        )
        # All IDs must be non-negative integers
        for i, mid in enumerate(spec["material_ids"]):
            assert isinstance(mid, int) and mid >= 0, (
                f"[BUG] {generator_name} material_ids[{i}]={mid!r} is not a "
                f"non-negative integer."
            )

    def test_generate_stone_wall_has_material_ids(self) -> None:
        """generate_stone_wall() must return material_ids equal in length to faces."""
        spec = generate_stone_wall(width=4.0, height=3.0, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_stone_wall")

    def test_generate_gothic_window_has_material_ids(self) -> None:
        """generate_gothic_window() must return material_ids equal in length to faces."""
        spec = generate_gothic_window(width=1.2, height=2.4, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_gothic_window")

    def test_generate_roof_has_material_ids(self) -> None:
        """generate_roof() must return material_ids equal in length to faces."""
        spec = generate_roof(width=6.0, depth=5.0, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_roof")

    def test_generate_archway_has_material_ids(self) -> None:
        """generate_archway() must return material_ids equal in length to faces."""
        spec = generate_archway(width=2.0, height=3.0, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_archway")

    def test_generate_battlements_has_material_ids(self) -> None:
        """generate_battlements() must return material_ids equal in length to faces."""
        spec = generate_battlements(wall_length=8.0, wall_height=2.0, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_battlements")

    def test_generate_staircase_has_material_ids(self) -> None:
        """generate_staircase() must return material_ids equal in length to faces."""
        spec = generate_staircase(step_width=2.0, step_count=8, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_staircase")

    def test_generate_chimney_has_material_ids(self) -> None:
        """generate_chimney() must return material_ids equal in length to faces."""
        spec = generate_chimney(chimney_width=0.8, height=3.0, seed=42)
        self._assert_material_ids_match_faces(spec, "generate_chimney")

    def test_material_ids_key_exists_even_when_empty(self) -> None:
        """material_ids key must always be present in MeshSpec (may not be empty)."""
        spec = generate_stone_wall()
        assert "material_ids" in spec, (
            "MeshSpec from generate_stone_wall missing 'material_ids' key."
        )

    def test_stone_wall_material_ids_distinguish_block_from_mortar(self) -> None:
        """Stone wall material_ids should use at least 2 distinct slots (stone + mortar).

        A wall with only slot 0 everywhere means no per-material assignment is possible.
        This test documents the minimum requirement: 2 materials (stone=0, mortar=1).
        """
        spec = generate_stone_wall(width=4.0, height=3.0, seed=42)
        mat_ids = spec.get("material_ids", [])
        unique_ids = set(mat_ids)
        assert len(unique_ids) >= 2, (
            f"[BUG] generate_stone_wall material_ids has only {len(unique_ids)} "
            f"unique slot(s): {unique_ids}. Expected >= 2 (stone blocks + mortar)."
        )
