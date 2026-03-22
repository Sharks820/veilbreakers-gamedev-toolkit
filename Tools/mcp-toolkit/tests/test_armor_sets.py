"""Unit tests for the armor set registration and bonus system.

Tests cover:
- ARMOR_SETS constant definitions (12 sets, 3 per path, 4 paths)
- get_armor_set() lookup and validation
- get_sets_for_path() path filtering and ordering
- compute_set_bonus_level() bonus tier activation
- get_active_bonuses() bonus name retrieval
- validate_set_pieces() piece slot validation
- Data integrity: piece slots, tiers, bonuses, colors

All pure-logic -- no Blender required.
"""

import pytest

from blender_addon.handlers.armor_sets import (
    ARMOR_SETS,
    VALID_PATHS,
    VALID_PIECE_SLOTS,
    compute_set_bonus_level,
    get_active_bonuses,
    get_armor_set,
    get_sets_for_path,
    validate_set_pieces,
)


# ---------------------------------------------------------------------------
# TestArmorSetsConstants
# ---------------------------------------------------------------------------

class TestArmorSetsConstants:
    """Test ARMOR_SETS constant definitions."""

    def test_has_twelve_sets(self):
        assert len(ARMOR_SETS) == 12

    def test_four_paths(self):
        assert VALID_PATHS == frozenset({"IRONBOUND", "SAVAGE", "SURGE", "VOID"})

    def test_three_sets_per_path(self):
        path_counts = {}
        for data in ARMOR_SETS.values():
            path = data["path"]
            path_counts[path] = path_counts.get(path, 0) + 1
        for path, count in path_counts.items():
            assert count == 3, f"Path '{path}' has {count} sets, expected 3"

    def test_valid_piece_slots(self):
        expected = {"helmet", "chest", "gauntlet", "boot", "pauldron", "cape",
                     "belt", "bracer", "ring", "amulet"}
        assert VALID_PIECE_SLOTS == frozenset(expected)

    def test_all_sets_have_required_keys(self):
        required = {"path", "tier", "display_name", "pieces", "set_bonuses",
                     "material_tier", "accent_color", "lore"}
        for name, data in ARMOR_SETS.items():
            for key in required:
                assert key in data, f"Set '{name}' missing key '{key}'"

    def test_all_piece_slots_valid(self):
        for name, data in ARMOR_SETS.items():
            for slot in data["pieces"]:
                assert slot in VALID_PIECE_SLOTS, (
                    f"Set '{name}' has invalid slot '{slot}'"
                )

    def test_tiers_are_valid(self):
        valid_tiers = {"rare", "epic", "legendary"}
        for name, data in ARMOR_SETS.items():
            assert data["tier"] in valid_tiers, (
                f"Set '{name}' has invalid tier '{data['tier']}'"
            )

    def test_each_path_has_all_three_tiers(self):
        for path in VALID_PATHS:
            sets = [d for d in ARMOR_SETS.values() if d["path"] == path]
            tiers = {s["tier"] for s in sets}
            assert tiers == {"rare", "epic", "legendary"}, (
                f"Path '{path}' missing tiers: {{'rare', 'epic', 'legendary'} - tiers}"
            )

    def test_set_bonuses_are_dict_with_int_keys(self):
        for name, data in ARMOR_SETS.items():
            bonuses = data["set_bonuses"]
            assert isinstance(bonuses, dict)
            for threshold, bonus_name in bonuses.items():
                assert isinstance(threshold, int), (
                    f"Set '{name}' bonus threshold '{threshold}' is not int"
                )
                assert isinstance(bonus_name, str), (
                    f"Set '{name}' bonus value '{bonus_name}' is not str"
                )

    def test_bonus_thresholds_are_even(self):
        for name, data in ARMOR_SETS.items():
            for threshold in data["set_bonuses"]:
                assert threshold % 2 == 0, (
                    f"Set '{name}' has odd bonus threshold {threshold}"
                )

    def test_accent_colors_are_rgb(self):
        for name, data in ARMOR_SETS.items():
            color = data["accent_color"]
            assert len(color) == 3
            for c in color:
                assert 0.0 <= c <= 1.0, (
                    f"Set '{name}' accent color channel {c} out of [0, 1]"
                )

    def test_rare_sets_have_six_pieces(self):
        for name, data in ARMOR_SETS.items():
            if data["tier"] == "rare":
                assert len(data["pieces"]) == 6, (
                    f"Rare set '{name}' has {len(data['pieces'])} pieces, expected 6"
                )

    def test_legendary_sets_have_ten_pieces(self):
        for name, data in ARMOR_SETS.items():
            if data["tier"] == "legendary":
                assert len(data["pieces"]) == 10, (
                    f"Legendary set '{name}' has {len(data['pieces'])} pieces, expected 10"
                )

    def test_all_sets_have_lore(self):
        for name, data in ARMOR_SETS.items():
            assert len(data["lore"]) > 20, (
                f"Set '{name}' has too short lore: '{data['lore']}'"
            )

    def test_display_names_unique(self):
        names = [d["display_name"] for d in ARMOR_SETS.values()]
        assert len(names) == len(set(names)), "Duplicate display names found"


# ---------------------------------------------------------------------------
# TestGetArmorSet
# ---------------------------------------------------------------------------

class TestGetArmorSet:
    """Test get_armor_set() lookup function."""

    def test_valid_sets(self):
        for name in ARMOR_SETS:
            result = get_armor_set(name)
            assert isinstance(result, dict)

    def test_returns_copy(self):
        result = get_armor_set("ironbound_sentinel")
        result["tier"] = "mythic"
        assert ARMOR_SETS["ironbound_sentinel"]["tier"] != "mythic"

    def test_invalid_set_raises(self):
        with pytest.raises(ValueError, match="Unknown armor set"):
            get_armor_set("nonexistent_set")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            get_armor_set("")


# ---------------------------------------------------------------------------
# TestGetSetsForPath
# ---------------------------------------------------------------------------

class TestGetSetsForPath:
    """Test get_sets_for_path() path filtering."""

    @pytest.mark.parametrize("path", list(VALID_PATHS))
    def test_returns_three_sets(self, path):
        sets = get_sets_for_path(path)
        assert len(sets) == 3

    def test_ordered_by_tier(self):
        sets = get_sets_for_path("IRONBOUND")
        tiers = [s["tier"] for s in sets]
        assert tiers == ["rare", "epic", "legendary"]

    def test_all_same_path(self):
        sets = get_sets_for_path("SAVAGE")
        for s in sets:
            assert s["path"] == "SAVAGE"

    def test_case_insensitive(self):
        sets = get_sets_for_path("surge")
        assert len(sets) == 3
        for s in sets:
            assert s["path"] == "SURGE"

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError, match="Unknown path"):
            get_sets_for_path("CHAOS")

    def test_returns_copies(self):
        sets = get_sets_for_path("VOID")
        sets[0]["tier"] = "mythic"
        original = get_sets_for_path("VOID")
        assert original[0]["tier"] != "mythic"


# ---------------------------------------------------------------------------
# TestComputeSetBonusLevel
# ---------------------------------------------------------------------------

class TestComputeSetBonusLevel:
    """Test compute_set_bonus_level() bonus tier calculation."""

    def test_no_pieces_zero_bonus(self):
        level = compute_set_bonus_level([], "ironbound_sentinel")
        assert level == 0

    def test_one_piece_zero_bonus(self):
        level = compute_set_bonus_level(["helmet"], "ironbound_sentinel")
        assert level == 0

    def test_two_pieces_one_bonus(self):
        level = compute_set_bonus_level(["helmet", "chest"], "ironbound_sentinel")
        assert level == 1

    def test_four_pieces_two_bonuses(self):
        level = compute_set_bonus_level(
            ["helmet", "chest", "gauntlet", "boot"],
            "ironbound_sentinel"
        )
        assert level == 2

    def test_full_rare_set_three_bonuses(self):
        pieces = list(ARMOR_SETS["ironbound_sentinel"]["pieces"].keys())
        level = compute_set_bonus_level(pieces, "ironbound_sentinel")
        assert level == 3  # 2-piece, 4-piece, 6-piece

    def test_non_matching_pieces_ignored(self):
        # Equip pieces not in this set
        level = compute_set_bonus_level(["ring", "amulet"], "ironbound_sentinel")
        # ring and amulet are not in sentinel set
        assert level == 0

    def test_invalid_set_raises(self):
        with pytest.raises(ValueError):
            compute_set_bonus_level(["helmet"], "nonexistent")

    def test_legendary_full_set(self):
        pieces = list(ARMOR_SETS["ironbound_bulwark"]["pieces"].keys())
        level = compute_set_bonus_level(pieces, "ironbound_bulwark")
        assert level == 5  # 2, 4, 6, 8, 10


# ---------------------------------------------------------------------------
# TestGetActiveBonuses
# ---------------------------------------------------------------------------

class TestGetActiveBonuses:
    """Test get_active_bonuses() bonus name retrieval."""

    def test_no_pieces_empty(self):
        bonuses = get_active_bonuses([], "ironbound_sentinel")
        assert bonuses == []

    def test_two_pieces_first_bonus(self):
        bonuses = get_active_bonuses(["helmet", "chest"], "ironbound_sentinel")
        assert bonuses == ["defense_up"]

    def test_four_pieces_two_bonuses(self):
        bonuses = get_active_bonuses(
            ["helmet", "chest", "gauntlet", "boot"],
            "ironbound_sentinel"
        )
        assert bonuses == ["defense_up", "iron_aura"]

    def test_full_rare_set(self):
        pieces = list(ARMOR_SETS["savage_marauder"]["pieces"].keys())
        bonuses = get_active_bonuses(pieces, "savage_marauder")
        assert bonuses == ["bloodlust", "savage_fury", "berserker_rage"]

    def test_full_legendary_set(self):
        pieces = list(ARMOR_SETS["void_abyssal"]["pieces"].keys())
        bonuses = get_active_bonuses(pieces, "void_abyssal")
        assert len(bonuses) == 5
        assert bonuses[0] == "void_step"
        assert bonuses[-1] == "abyssal_form"

    def test_partial_only_first(self):
        bonuses = get_active_bonuses(["helmet", "chest", "gauntlet"], "ironbound_sentinel")
        # 3 matching pieces: only 2-piece threshold met
        assert bonuses == ["defense_up"]


# ---------------------------------------------------------------------------
# TestValidateSetPieces
# ---------------------------------------------------------------------------

class TestValidateSetPieces:
    """Test validate_set_pieces() piece validation."""

    def test_valid_matching_pieces(self):
        result = validate_set_pieces(
            ["helmet", "chest"],
            "ironbound_sentinel"
        )
        assert result["valid"] is True
        assert result["matching"] == ["helmet", "chest"]
        assert result["invalid"] == []

    def test_invalid_slot_name(self):
        result = validate_set_pieces(
            ["helmet", "wings"],
            "ironbound_sentinel"
        )
        assert result["valid"] is False
        assert "wings" in result["invalid"]

    def test_not_in_set(self):
        result = validate_set_pieces(
            ["ring"],
            "ironbound_sentinel"
        )
        # ring is valid slot but not in sentinel set
        assert result["valid"] is True
        assert "ring" in result["not_in_set"]

    def test_missing_pieces(self):
        result = validate_set_pieces(
            ["helmet"],
            "ironbound_sentinel"
        )
        assert "chest" in result["missing"]
        assert "helmet" not in result["missing"]

    def test_set_total_pieces(self):
        result = validate_set_pieces([], "ironbound_sentinel")
        assert result["set_total_pieces"] == 6

    def test_equipped_matching_count(self):
        result = validate_set_pieces(
            ["helmet", "chest", "gauntlet"],
            "ironbound_sentinel"
        )
        assert result["equipped_matching"] == 3

    def test_empty_pieces(self):
        result = validate_set_pieces([], "ironbound_sentinel")
        assert result["valid"] is True
        assert result["matching"] == []
        assert result["equipped_matching"] == 0

    def test_invalid_set_raises(self):
        with pytest.raises(ValueError):
            validate_set_pieces(["helmet"], "nonexistent")
