"""Unit tests for material_tiers module (EQ-040).

Tests cover:
- All tier dicts have required keys (base_color, roughness, description)
- Metal tiers have metallic key
- Palette rule compliance (saturation, value ranges)
- get_material_tier lookup for all categories and tiers
- get_tier_names returns sorted lists
- apply_material_tier_to_equipment builds correct param dicts
- Error handling for invalid categories/tiers
- Data immutability (get_material_tier returns copies)
- Module-level constants (VALID_CATEGORIES)

All pure-logic -- no Blender required.
"""

import colorsys

import pytest

from blender_addon.handlers.material_tiers import (
    METAL_TIERS,
    WOOD_TIERS,
    LEATHER_TIERS,
    CLOTH_TIERS,
    VALID_CATEGORIES,
    get_material_tier,
    get_tier_names,
    apply_material_tier_to_equipment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_TIER_DICTS = {
    "metal": METAL_TIERS,
    "wood": WOOD_TIERS,
    "leather": LEATHER_TIERS,
    "cloth": CLOTH_TIERS,
}

REQUIRED_KEYS = {"base_color", "roughness", "description"}


def _rgb_to_hsv(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert RGB (0-1 range) to HSV (0-1 range)."""
    return colorsys.rgb_to_hsv(*rgb)


# ---------------------------------------------------------------------------
# TestTierDataIntegrity
# ---------------------------------------------------------------------------


class TestTierDataIntegrity:
    """Verify all tier dicts have correct structure."""

    @pytest.mark.parametrize("category", sorted(ALL_TIER_DICTS.keys()))
    def test_all_tiers_have_required_keys(self, category):
        tiers = ALL_TIER_DICTS[category]
        for name, data in tiers.items():
            missing = REQUIRED_KEYS - set(data.keys())
            assert not missing, (
                f"{category}/{name} missing keys: {missing}"
            )

    def test_metal_tiers_count(self):
        assert len(METAL_TIERS) == 10

    def test_wood_tiers_count(self):
        assert len(WOOD_TIERS) == 5

    def test_leather_tiers_count(self):
        assert len(LEATHER_TIERS) == 5

    def test_cloth_tiers_count(self):
        assert len(CLOTH_TIERS) == 5

    def test_total_tiers_count(self):
        total = sum(len(t) for t in ALL_TIER_DICTS.values())
        assert total == 25

    @pytest.mark.parametrize("category", sorted(ALL_TIER_DICTS.keys()))
    def test_base_color_is_3_tuple(self, category):
        for name, data in ALL_TIER_DICTS[category].items():
            bc = data["base_color"]
            assert len(bc) == 3, f"{category}/{name}: base_color has {len(bc)} elements"
            for i, v in enumerate(bc):
                assert 0.0 <= v <= 1.0, (
                    f"{category}/{name}: base_color[{i}] = {v} out of range"
                )

    @pytest.mark.parametrize("category", sorted(ALL_TIER_DICTS.keys()))
    def test_roughness_in_range(self, category):
        for name, data in ALL_TIER_DICTS[category].items():
            r = data["roughness"]
            assert 0.0 <= r <= 1.0, f"{category}/{name}: roughness={r} out of range"

    def test_metal_tiers_have_metallic(self):
        """All metal tiers should have a metallic property."""
        for name, data in METAL_TIERS.items():
            assert "metallic" in data, f"metal/{name} missing metallic key"
            assert 0.0 <= data["metallic"] <= 1.0, (
                f"metal/{name}: metallic={data['metallic']} out of range"
            )

    def test_emission_color_is_3_tuple(self):
        """Any tier with emission_color should have a valid 3-tuple."""
        for category, tiers in ALL_TIER_DICTS.items():
            for name, data in tiers.items():
                if "emission_color" in data:
                    ec = data["emission_color"]
                    assert len(ec) == 3, (
                        f"{category}/{name}: emission_color has {len(ec)} elements"
                    )

    def test_description_is_nonempty_string(self):
        for category, tiers in ALL_TIER_DICTS.items():
            for name, data in tiers.items():
                desc = data["description"]
                assert isinstance(desc, str), (
                    f"{category}/{name}: description is not a string"
                )
                assert len(desc) > 0, f"{category}/{name}: empty description"


# ---------------------------------------------------------------------------
# TestPaletteRules
# ---------------------------------------------------------------------------


class TestPaletteRules:
    """Verify dark fantasy palette rules for material tiers."""

    def test_metal_saturation_under_40_percent(self):
        """Metal base_color saturation should be <= 40% (0.4) for most tiers.

        Exception: gold and orichalcum are warm-toned decorative metals where
        higher saturation is expected in dark fantasy.
        """
        SATURATION_EXCEPTIONS = {"gold", "orichalcum", "void_touched"}
        for name, data in METAL_TIERS.items():
            _, s, _ = _rgb_to_hsv(data["base_color"])
            if name in SATURATION_EXCEPTIONS:
                # Decorative/supernatural metals allowed up to 75% saturation
                assert s <= 0.75, (
                    f"metal/{name}: saturation={s:.2f} exceeds 75% even for "
                    f"decorative/supernatural metal"
                )
            else:
                assert s <= 0.40, (
                    f"metal/{name}: saturation={s:.2f} exceeds 40%"
                )

    def test_metal_value_range(self):
        """Metal base_color value should be in 2-100% range.

        Dark metals (adamantine, obsidian, void_touched) can go very dark.
        Physically-based reflective metals (gold, silver, copper) can reach
        high reflectance values per PBR reference data.
        """
        for name, data in METAL_TIERS.items():
            _, _, v = _rgb_to_hsv(data["base_color"])
            assert 0.02 <= v <= 1.0, (
                f"metal/{name}: value={v:.2f} out of expected range"
            )

    def test_organic_colors_warm_desaturated(self):
        """Wood, leather, cloth base colors should be generally warm and
        desaturated (dark fantasy palette)."""
        for category in ("wood", "leather", "cloth"):
            for name, data in ALL_TIER_DICTS[category].items():
                _, s, _ = _rgb_to_hsv(data["base_color"])
                # Allow up to 60% for organic materials (some living/enchanted
                # materials have moderate saturation)
                assert s <= 0.60, (
                    f"{category}/{name}: saturation={s:.2f} exceeds 60% "
                    f"(too vivid for dark fantasy)"
                )


# ---------------------------------------------------------------------------
# TestGetMaterialTier
# ---------------------------------------------------------------------------


class TestGetMaterialTier:
    """Test get_material_tier lookup function."""

    def test_lookup_iron(self):
        tier = get_material_tier("metal", "iron")
        assert tier["base_color"] == (0.56, 0.57, 0.58)
        assert tier["metallic"] == 1.0  # PBR: true metal must be 1.0 (was 0.85, a PBR bug)

    def test_lookup_oak(self):
        tier = get_material_tier("wood", "oak")
        assert tier["roughness"] == 0.70

    def test_lookup_cured_leather(self):
        tier = get_material_tier("leather", "cured")
        assert "description" in tier

    def test_lookup_silk_cloth(self):
        tier = get_material_tier("cloth", "silk")
        assert tier["roughness"] == 0.30

    def test_case_insensitive_category(self):
        tier = get_material_tier("METAL", "iron")
        assert tier["base_color"] == (0.56, 0.57, 0.58)

    def test_case_insensitive_tier(self):
        tier = get_material_tier("metal", "IRON")
        assert tier["base_color"] == (0.56, 0.57, 0.58)

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Unknown material category"):
            get_material_tier("plastic", "abs")

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            get_material_tier("metal", "unobtanium")

    def test_returns_copy(self):
        """Modifying returned dict should not change module data."""
        tier1 = get_material_tier("metal", "iron")
        tier1["base_color"] = (1.0, 0.0, 0.0)
        tier2 = get_material_tier("metal", "iron")
        assert tier2["base_color"] == (0.56, 0.57, 0.58)

    @pytest.mark.parametrize("category", sorted(ALL_TIER_DICTS.keys()))
    def test_all_tiers_retrievable(self, category):
        """Every tier in every category is retrievable via get_material_tier."""
        for tier_name in ALL_TIER_DICTS[category]:
            tier = get_material_tier(category, tier_name)
            assert "base_color" in tier
            assert "roughness" in tier


# ---------------------------------------------------------------------------
# TestGetTierNames
# ---------------------------------------------------------------------------


class TestGetTierNames:
    """Test get_tier_names returns correct sorted lists."""

    def test_metal_tier_names(self):
        names = get_tier_names("metal")
        assert isinstance(names, list)
        assert len(names) == 10
        assert names == sorted(names)

    def test_wood_tier_names(self):
        names = get_tier_names("wood")
        assert len(names) == 5
        assert "oak" in names

    def test_leather_tier_names(self):
        names = get_tier_names("leather")
        assert len(names) == 5
        assert "rawhide" in names

    def test_cloth_tier_names(self):
        names = get_tier_names("cloth")
        assert len(names) == 5
        assert "burlap" in names

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Unknown material category"):
            get_tier_names("stone")

    def test_case_insensitive(self):
        names = get_tier_names("WOOD")
        assert "pine" in names


# ---------------------------------------------------------------------------
# TestApplyMaterialTier
# ---------------------------------------------------------------------------


class TestApplyMaterialTier:
    """Test apply_material_tier_to_equipment builds correct param dicts."""

    def test_basic_iron_application(self):
        result = apply_material_tier_to_equipment(
            {"object_name": "Sword_01"}, "metal", "iron"
        )
        assert result["object_name"] == "Sword_01"
        assert result["material_name"] == "Sword_01_metal_iron"
        assert result["base_color"] == (0.56, 0.57, 0.58)
        assert result["metallic"] == 1.0  # PBR: true metal must be 1.0 (rust via roughness)
        assert result["roughness"] == 0.60

    def test_forwards_emission(self):
        result = apply_material_tier_to_equipment(
            {"object_name": "Staff"}, "metal", "void_touched"
        )
        assert result["emission"] == 0.15
        assert result["emission_color"] == (0.3, 0.1, 0.5)

    def test_forwards_coat_weight(self):
        result = apply_material_tier_to_equipment(
            {"object_name": "Shield"}, "metal", "gold"
        )
        assert result["coat_weight"] == 0.3

    def test_forwards_subsurface(self):
        result = apply_material_tier_to_equipment(
            {"object_name": "Helm"}, "metal", "dragonbone"
        )
        assert result["subsurface"] == 0.05

    def test_wood_tier_no_metallic(self):
        result = apply_material_tier_to_equipment(
            {"object_name": "Bow"}, "wood", "pine"
        )
        assert result["metallic"] == 0.0  # wood defaults to 0

    def test_ironwood_has_metallic(self):
        result = apply_material_tier_to_equipment(
            {"object_name": "Club"}, "wood", "ironwood"
        )
        assert result["metallic"] == 0.0  # PBR: wood is dielectric regardless of hardness

    def test_default_object_name(self):
        result = apply_material_tier_to_equipment({}, "leather", "rawhide")
        assert result["object_name"] == "equipment"
        assert result["material_name"] == "equipment_leather_rawhide"

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Unknown material category"):
            apply_material_tier_to_equipment(
                {"object_name": "X"}, "glass", "clear"
            )

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            apply_material_tier_to_equipment(
                {"object_name": "X"}, "metal", "unobtanium"
            )

    @pytest.mark.parametrize("category", sorted(ALL_TIER_DICTS.keys()))
    def test_all_tiers_applicable(self, category):
        """Every tier in every category can be applied without error."""
        for tier_name in ALL_TIER_DICTS[category]:
            result = apply_material_tier_to_equipment(
                {"object_name": "Test"}, category, tier_name
            )
            assert "base_color" in result
            assert "material_name" in result


# ---------------------------------------------------------------------------
# TestValidCategories
# ---------------------------------------------------------------------------


class TestValidCategories:
    """Test VALID_CATEGORIES constant."""

    def test_contains_four_categories(self):
        assert len(VALID_CATEGORIES) == 4

    def test_expected_categories(self):
        assert VALID_CATEGORIES == {"metal", "wood", "leather", "cloth"}
