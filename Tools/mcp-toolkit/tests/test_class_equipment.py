"""Tests for path-exclusive equipment definitions.

Tests cover:
- PATH_EQUIPMENT constant definitions (4 paths, all fields present)
- get_path_equipment() lookup, copies, case insensitivity
- get_signature_weapons() weapon lists per path
- get_signature_armor_set() armor slot maps per path
- get_brand_affinity() brand affinity lists
- get_visual_identity() visual identity tags
- validate_path_equipment() loadout validation
- Data integrity: no cross-path duplicates, valid slots, valid brands
- Edge cases: invalid paths, empty inputs

All pure logic -- no Blender required.
"""

import pytest

from blender_addon.handlers.class_equipment import (
    ALL_SIGNATURE_ARMOR_PIECES,
    ALL_SIGNATURE_WEAPONS,
    PATH_EQUIPMENT,
    VALID_ARMOR_SLOTS,
    VALID_PATHS,
    get_brand_affinity,
    get_path_equipment,
    get_signature_armor_set,
    get_signature_weapons,
    get_visual_identity,
    validate_path_equipment,
)


# ---------------------------------------------------------------------------
# TestPathEquipmentConstants
# ---------------------------------------------------------------------------


class TestPathEquipmentConstants:
    """Test PATH_EQUIPMENT constant definitions."""

    def test_has_four_paths(self):
        assert len(PATH_EQUIPMENT) == 4

    def test_valid_paths_match(self):
        assert VALID_PATHS == frozenset({"IRONBOUND", "FANGBORN", "VOIDTOUCHED", "UNCHAINED"})

    def test_all_paths_have_required_keys(self):
        required = {
            "signature_weapons", "signature_armor", "brand_affinity",
            "material_tier", "visual_identity", "description",
        }
        for path, data in PATH_EQUIPMENT.items():
            for key in required:
                assert key in data, f"Path '{path}' missing key '{key}'"

    def test_all_paths_have_four_weapons(self):
        for path, data in PATH_EQUIPMENT.items():
            weapons = data["signature_weapons"]
            assert len(weapons) == 4, (
                f"Path '{path}' has {len(weapons)} weapons, expected 4"
            )

    def test_all_paths_have_six_armor_slots(self):
        for path, data in PATH_EQUIPMENT.items():
            armor = data["signature_armor"]
            assert len(armor) == 6, (
                f"Path '{path}' has {len(armor)} armor slots, expected 6"
            )

    def test_all_armor_slots_valid(self):
        for path, data in PATH_EQUIPMENT.items():
            for slot in data["signature_armor"]:
                assert slot in VALID_ARMOR_SLOTS, (
                    f"Path '{path}' has invalid armor slot '{slot}'"
                )

    def test_all_armor_slots_covered(self):
        """Every path should cover all 6 standard armor slots."""
        for path, data in PATH_EQUIPMENT.items():
            slots = set(data["signature_armor"].keys())
            assert slots == set(VALID_ARMOR_SLOTS), (
                f"Path '{path}' missing armor slots: {VALID_ARMOR_SLOTS - slots}"
            )

    def test_brand_affinities_are_lists(self):
        for path, data in PATH_EQUIPMENT.items():
            aff = data["brand_affinity"]
            assert isinstance(aff, list)
            assert len(aff) == 2, (
                f"Path '{path}' has {len(aff)} brand affinities, expected 2"
            )

    def test_brand_affinities_are_valid_brands(self):
        valid_brands = {"IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                        "LEECH", "GRACE", "MEND", "RUIN", "VOID"}
        for path, data in PATH_EQUIPMENT.items():
            for brand in data["brand_affinity"]:
                assert brand in valid_brands, (
                    f"Path '{path}' has invalid brand affinity '{brand}'"
                )

    def test_material_tiers_are_strings(self):
        for path, data in PATH_EQUIPMENT.items():
            assert isinstance(data["material_tier"], str)
            assert len(data["material_tier"]) > 0

    def test_visual_identities_are_strings(self):
        for path, data in PATH_EQUIPMENT.items():
            assert isinstance(data["visual_identity"], str)
            assert len(data["visual_identity"]) > 0

    def test_descriptions_are_substantial(self):
        for path, data in PATH_EQUIPMENT.items():
            assert len(data["description"]) > 30, (
                f"Path '{path}' has too short description"
            )

    def test_weapon_names_unique_across_paths(self):
        """No weapon should appear in more than one path."""
        all_weapons = []
        for data in PATH_EQUIPMENT.values():
            all_weapons.extend(data["signature_weapons"])
        assert len(all_weapons) == len(set(all_weapons)), (
            "Duplicate weapon names found across paths"
        )

    def test_armor_piece_names_unique_across_paths(self):
        """No armor piece name should appear in more than one path."""
        all_pieces = []
        for data in PATH_EQUIPMENT.values():
            all_pieces.extend(data["signature_armor"].values())
        assert len(all_pieces) == len(set(all_pieces)), (
            "Duplicate armor piece names found across paths"
        )

    def test_all_signature_weapons_set(self):
        assert len(ALL_SIGNATURE_WEAPONS) == 16  # 4 paths x 4 weapons

    def test_all_signature_armor_pieces_set(self):
        assert len(ALL_SIGNATURE_ARMOR_PIECES) == 24  # 4 paths x 6 pieces


# ---------------------------------------------------------------------------
# TestGetPathEquipment
# ---------------------------------------------------------------------------


class TestGetPathEquipment:
    """Test get_path_equipment() lookup function."""

    @pytest.mark.parametrize("path", list(VALID_PATHS))
    def test_valid_paths(self, path):
        result = get_path_equipment(path)
        assert isinstance(result, dict)
        assert "signature_weapons" in result
        assert "signature_armor" in result

    def test_returns_copy(self):
        result = get_path_equipment("IRONBOUND")
        result["material_tier"] = "adamantium"
        assert PATH_EQUIPMENT["IRONBOUND"]["material_tier"] != "adamantium"

    def test_weapons_list_is_copy(self):
        result = get_path_equipment("FANGBORN")
        result["signature_weapons"].append("extra_weapon")
        original = PATH_EQUIPMENT["FANGBORN"]["signature_weapons"]
        assert "extra_weapon" not in original

    def test_armor_dict_is_copy(self):
        result = get_path_equipment("VOIDTOUCHED")
        result["signature_armor"]["wings"] = "void_wings"
        original = PATH_EQUIPMENT["VOIDTOUCHED"]["signature_armor"]
        assert "wings" not in original

    def test_case_insensitive(self):
        result = get_path_equipment("ironbound")
        assert result["material_tier"] == "steel"

    def test_mixed_case(self):
        result = get_path_equipment("FangBorn")
        assert result["material_tier"] == "monster_hide"

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError, match="Unknown path"):
            get_path_equipment("CHAOS")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            get_path_equipment("")


# ---------------------------------------------------------------------------
# TestGetSignatureWeapons
# ---------------------------------------------------------------------------


class TestGetSignatureWeapons:
    """Test get_signature_weapons() weapon list retrieval."""

    def test_ironbound_weapons(self):
        weapons = get_signature_weapons("IRONBOUND")
        assert weapons == ["fortress_shield", "chain_flail", "siege_hammer", "war_banner"]

    def test_fangborn_weapons(self):
        weapons = get_signature_weapons("FANGBORN")
        assert weapons == ["fang_daggers", "antler_staff", "claw_gauntlets", "thorn_whip"]

    def test_voidtouched_weapons(self):
        weapons = get_signature_weapons("VOIDTOUCHED")
        assert weapons == ["void_staff", "crystal_wand", "spell_blade", "grimoire"]

    def test_unchained_weapons(self):
        weapons = get_signature_weapons("UNCHAINED")
        assert weapons == ["hidden_blade", "hand_crossbow", "smoke_bomb", "garrote"]

    def test_returns_copy(self):
        weapons = get_signature_weapons("IRONBOUND")
        weapons.append("extra")
        assert "extra" not in get_signature_weapons("IRONBOUND")

    def test_case_insensitive(self):
        weapons = get_signature_weapons("unchained")
        assert len(weapons) == 4

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            get_signature_weapons("DRAGON_KNIGHT")


# ---------------------------------------------------------------------------
# TestGetSignatureArmorSet
# ---------------------------------------------------------------------------


class TestGetSignatureArmorSet:
    """Test get_signature_armor_set() armor slot map retrieval."""

    @pytest.mark.parametrize("path", list(VALID_PATHS))
    def test_all_paths_return_six_slots(self, path):
        armor = get_signature_armor_set(path)
        assert len(armor) == 6

    def test_ironbound_armor(self):
        armor = get_signature_armor_set("IRONBOUND")
        assert armor["helmet"] == "fortress_helm"
        assert armor["chest"] == "siege_plate"
        assert armor["cape"] == "battle_standard"

    def test_fangborn_armor(self):
        armor = get_signature_armor_set("FANGBORN")
        assert armor["helmet"] == "beastmaster_hood"
        assert armor["boot"] == "root_boots"

    def test_returns_copy(self):
        armor = get_signature_armor_set("VOIDTOUCHED")
        armor["wings"] = "void_wings"
        original = get_signature_armor_set("VOIDTOUCHED")
        assert "wings" not in original

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            get_signature_armor_set("BERSERKER")


# ---------------------------------------------------------------------------
# TestGetBrandAffinity
# ---------------------------------------------------------------------------


class TestGetBrandAffinity:
    """Test get_brand_affinity() brand affinity retrieval."""

    def test_ironbound_brands(self):
        brands = get_brand_affinity("IRONBOUND")
        assert brands == ["IRON", "SAVAGE"]

    def test_fangborn_brands(self):
        brands = get_brand_affinity("FANGBORN")
        assert brands == ["SAVAGE", "VENOM"]

    def test_voidtouched_brands(self):
        brands = get_brand_affinity("VOIDTOUCHED")
        assert brands == ["VOID", "DREAD"]

    def test_unchained_brands(self):
        brands = get_brand_affinity("UNCHAINED")
        assert brands == ["SURGE", "LEECH"]

    def test_returns_copy(self):
        brands = get_brand_affinity("IRONBOUND")
        brands.append("VOID")
        assert "VOID" not in get_brand_affinity("IRONBOUND")

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            get_brand_affinity("CHAOS")


# ---------------------------------------------------------------------------
# TestGetVisualIdentity
# ---------------------------------------------------------------------------


class TestGetVisualIdentity:
    """Test get_visual_identity() visual identity retrieval."""

    def test_ironbound_identity(self):
        assert get_visual_identity("IRONBOUND") == "heavy_angular_riveted"

    def test_fangborn_identity(self):
        assert get_visual_identity("FANGBORN") == "organic_curved_natural"

    def test_voidtouched_identity(self):
        assert get_visual_identity("VOIDTOUCHED") == "flowing_ethereal_glowing"

    def test_unchained_identity(self):
        assert get_visual_identity("UNCHAINED") == "sleek_dark_minimal"

    def test_case_insensitive(self):
        assert get_visual_identity("ironbound") == "heavy_angular_riveted"

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            get_visual_identity("NEUTRAL")


# ---------------------------------------------------------------------------
# TestValidatePathEquipment
# ---------------------------------------------------------------------------


class TestValidatePathEquipment:
    """Test validate_path_equipment() loadout validation."""

    def test_matching_weapon(self):
        result = validate_path_equipment("IRONBOUND", weapon="fortress_shield")
        assert result["valid"] is True
        assert result["weapon_match"] is True

    def test_non_matching_weapon(self):
        result = validate_path_equipment("IRONBOUND", weapon="void_staff")
        assert result["valid"] is False
        assert result["weapon_match"] is False

    def test_no_weapon_provided(self):
        result = validate_path_equipment("IRONBOUND")
        assert result["valid"] is True
        assert result["weapon_match"] is None

    def test_matching_armor(self):
        result = validate_path_equipment(
            "FANGBORN",
            armor_pieces={"helmet": "beastmaster_hood", "chest": "bark_armor"},
        )
        assert result["valid"] is True
        assert result["armor_matches"]["helmet"] is True
        assert result["armor_matches"]["chest"] is True
        assert result["mismatched_slots"] == []

    def test_non_matching_armor(self):
        result = validate_path_equipment(
            "FANGBORN",
            armor_pieces={"helmet": "fortress_helm"},
        )
        assert result["valid"] is False
        assert result["armor_matches"]["helmet"] is False
        assert "helmet" in result["mismatched_slots"]

    def test_no_armor_provided(self):
        result = validate_path_equipment("FANGBORN")
        assert result["armor_matches"] is None
        assert result["mismatched_slots"] == []

    def test_combined_weapon_and_armor(self):
        result = validate_path_equipment(
            "UNCHAINED",
            weapon="hidden_blade",
            armor_pieces={"helmet": "shadow_hood", "boot": "silent_boots"},
        )
        assert result["valid"] is True
        assert result["weapon_match"] is True
        assert all(result["armor_matches"].values())

    def test_mixed_valid_invalid(self):
        result = validate_path_equipment(
            "VOIDTOUCHED",
            weapon="void_staff",
            armor_pieces={"helmet": "fortress_helm", "chest": "archmage_robes"},
        )
        assert result["valid"] is False
        assert result["weapon_match"] is True
        assert result["armor_matches"]["helmet"] is False
        assert result["armor_matches"]["chest"] is True
        assert "helmet" in result["mismatched_slots"]

    def test_path_normalised_in_result(self):
        result = validate_path_equipment("ironbound")
        assert result["path"] == "IRONBOUND"

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            validate_path_equipment("CHAOS", weapon="sword")

    def test_empty_armor_dict(self):
        result = validate_path_equipment("IRONBOUND", armor_pieces={})
        assert result["valid"] is True
        assert result["armor_matches"] == {}
        assert result["mismatched_slots"] == []
