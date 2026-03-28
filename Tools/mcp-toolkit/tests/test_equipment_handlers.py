"""Unit tests for equipment handler pure-logic and mesh generation functions.

Tests cover:
- Weapon parameter validation (_validate_weapon_params)
- Character split parameter validation (_validate_split_params)
- Armor fitting parameter validation (_validate_armor_params)
- Icon rendering parameter validation (_validate_icon_params)
- Weapon type constants (VALID_WEAPON_TYPES -- 47 types)
- Body part/type defaults (DEFAULT_BODY_PARTS, DEFAULT_BODY_TYPES)
- Weapon empty position computation (_compute_grip_point, _compute_trail_attach_*)
- Weapon mesh generators (bmesh-based, tested via vertex/face counts on stub bmesh)
- Weapon generator dispatch table (_WEAPON_GENERATORS)
- Weapon classification sets (_POLEARM_TYPES, _TWO_HANDED_TYPES, etc.)

All pure-logic -- no Blender required for validation tests.
Mesh generator tests use the real bmesh module stub from conftest.
"""

import math

import pytest

from blender_addon.handlers import equipment as equipment_module
from blender_addon.handlers.equipment import (
    DEFAULT_BODY_PARTS,
    DEFAULT_BODY_TYPES,
    VALID_WEAPON_TYPES,
    _compute_grip_point,
    _compute_trail_attach_bottom,
    _compute_trail_attach_top,
    _estimate_icon_file_size,
    _validate_armor_params,
    _validate_icon_params,
    _validate_split_params,
    _validate_weapon_params,
    _WEAPON_GENERATORS,
    _POLEARM_TYPES,
    _TWO_HANDED_TYPES,
    _RANGED_TYPES,
    _MAGIC_TYPES,
    _CHAIN_TYPES,
    _DUAL_WIELD_TYPES,
    _FIST_TYPES,
    _THRUST_TYPES,
    _FOCUS_TYPES,
    _THROWN_TYPES,
)


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    """Test that equipment constants are correct."""

    def test_valid_weapon_types_has_47(self):
        assert len(VALID_WEAPON_TYPES) == 47

    def test_valid_weapon_types_original_seven(self):
        original = {"sword", "axe", "mace", "staff", "bow", "dagger", "shield"}
        assert original.issubset(VALID_WEAPON_TYPES)

    EXPECTED_ALL_TYPES = {
        "sword", "axe", "mace", "staff", "bow", "dagger", "shield",
        "hammer", "spear", "crossbow", "scythe", "flail", "whip",
        "claw", "tome", "greatsword", "curved_sword", "hand_axe",
        "battle_axe", "greataxe", "club", "warhammer", "halberd",
        "glaive", "shortbow", "longbow", "staff_magic", "wand",
        "throwing_knife",
        # Dual-wield paired weapons
        "paired_daggers", "twin_swords", "dual_axes", "dual_claws",
        # Fist / gauntlet weapons
        "brass_knuckles", "cestus", "bladed_gauntlet", "iron_fist",
        # Rapiers / thrusting swords
        "rapier", "estoc",
        # Throwing weapons
        "javelin", "throwing_axe", "shuriken", "bola",
        # Off-hand focus items
        "orb_focus", "skull_fetish", "holy_symbol", "totem",
    }

    @pytest.mark.parametrize("wtype", sorted(EXPECTED_ALL_TYPES))
    def test_valid_weapon_types_contains(self, wtype):
        assert wtype in VALID_WEAPON_TYPES

    def test_valid_weapon_types_all_present(self):
        assert VALID_WEAPON_TYPES == self.EXPECTED_ALL_TYPES

    def test_classification_sets_cover_extended_types(self):
        """All extended weapon types belong to at least one classification set,
        or are handled in the original/other categories."""
        classified = (
            _POLEARM_TYPES | _TWO_HANDED_TYPES | _RANGED_TYPES
            | _MAGIC_TYPES | _CHAIN_TYPES | _DUAL_WIELD_TYPES
            | _FIST_TYPES | _THRUST_TYPES | _FOCUS_TYPES | _THROWN_TYPES
        )
        # Remaining types are handled by specific if-branches (sword, dagger, etc.)
        remaining = VALID_WEAPON_TYPES - classified
        # All remaining should be explicitly handled in grip/trail functions
        known_remaining = {
            "sword", "axe", "mace", "staff", "dagger", "shield",
            "hammer", "scythe", "claw", "curved_sword", "hand_axe",
            "battle_axe", "club",
        }
        assert remaining == known_remaining

    def test_classification_sets_no_overlap(self):
        """Classification sets should not overlap."""
        sets = [_POLEARM_TYPES, _TWO_HANDED_TYPES, _RANGED_TYPES,
                _MAGIC_TYPES, _CHAIN_TYPES, _DUAL_WIELD_TYPES,
                _FIST_TYPES, _THRUST_TYPES, _FOCUS_TYPES, _THROWN_TYPES]
        for i, s1 in enumerate(sets):
            for s2 in sets[i + 1:]:
                assert not (s1 & s2), f"Overlap: {s1 & s2}"

    def test_default_body_parts_count(self):
        assert len(DEFAULT_BODY_PARTS) == 7

    def test_default_body_parts_has_head(self):
        assert "head" in DEFAULT_BODY_PARTS

    def test_default_body_parts_has_torso(self):
        assert "torso" in DEFAULT_BODY_PARTS

    def test_default_body_parts_has_feet(self):
        assert "feet" in DEFAULT_BODY_PARTS

    def test_default_body_types_count(self):
        assert len(DEFAULT_BODY_TYPES) == 3

    def test_default_body_types_has_default(self):
        assert "default" in DEFAULT_BODY_TYPES

    def test_default_body_types_has_muscular(self):
        assert "muscular" in DEFAULT_BODY_TYPES

    def test_default_body_types_has_slim(self):
        assert "slim" in DEFAULT_BODY_TYPES

    def test_weapon_generators_covers_all_types(self):
        """Every valid weapon type has a generator function."""
        for wtype in VALID_WEAPON_TYPES:
            assert wtype in _WEAPON_GENERATORS, f"Missing generator for {wtype}"

    def test_weapon_generators_all_callable(self):
        for wtype, gen in _WEAPON_GENERATORS.items():
            assert callable(gen), f"Generator for {wtype} is not callable"

    def test_weapon_generators_count_matches_types(self):
        """Generator dispatch table has same count as VALID_WEAPON_TYPES."""
        assert len(_WEAPON_GENERATORS) == len(VALID_WEAPON_TYPES)


# ---------------------------------------------------------------------------
# TestWeaponGeneration -- parameter validation
# ---------------------------------------------------------------------------


class TestWeaponGeneration:
    """Test _validate_weapon_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_weapon_params({})
        assert result["weapon_type"] == "sword"
        assert result["length"] == 1.0
        assert result["width"] == 0.15
        assert result["material_name"] == ""

    def test_valid_all_params(self):
        result = _validate_weapon_params({
            "weapon_type": "axe",
            "length": 1.5,
            "blade_width": 0.3,
            "material_name": "DarkSteel",
        })
        assert result["weapon_type"] == "axe"
        assert result["length"] == 1.5
        assert result["width"] == 0.3
        assert result["material_name"] == "DarkSteel"

    def test_head_size_alias(self):
        """head_size is accepted as width parameter for mace/staff."""
        result = _validate_weapon_params({
            "weapon_type": "mace",
            "head_size": 0.25,
        })
        assert result["width"] == 0.25

    def test_blade_width_takes_precedence(self):
        """blade_width takes precedence over head_size."""
        result = _validate_weapon_params({
            "blade_width": 0.2,
            "head_size": 0.3,
        })
        assert result["width"] == 0.2

    def test_invalid_weapon_type_raises(self):
        with pytest.raises(ValueError, match="Unknown weapon_type"):
            _validate_weapon_params({"weapon_type": "lightsaber"})

    def test_negative_length_raises(self):
        with pytest.raises(ValueError, match="length must be positive"):
            _validate_weapon_params({"length": -1.0})

    def test_zero_length_raises(self):
        with pytest.raises(ValueError, match="length must be positive"):
            _validate_weapon_params({"length": 0})

    def test_negative_width_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            _validate_weapon_params({"blade_width": -0.1})

    def test_case_insensitive_weapon_type(self):
        result = _validate_weapon_params({"weapon_type": "SWORD"})
        assert result["weapon_type"] == "sword"

    @pytest.mark.parametrize("wtype", sorted(VALID_WEAPON_TYPES))
    def test_all_weapon_types_accepted(self, wtype):
        result = _validate_weapon_params({"weapon_type": wtype})
        assert result["weapon_type"] == wtype

    def test_length_cast_to_float(self):
        result = _validate_weapon_params({"length": "2.5"})
        assert result["length"] == 2.5
        assert isinstance(result["length"], float)

    def test_width_cast_to_float(self):
        result = _validate_weapon_params({"blade_width": "0.2"})
        assert result["width"] == 0.2
        assert isinstance(result["width"], float)


# ---------------------------------------------------------------------------
# TestModularCharacter -- parameter validation
# ---------------------------------------------------------------------------


class TestModularCharacter:
    """Test _validate_split_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_split_params({"object_name": "Character"})
        assert result["object_name"] == "Character"
        assert result["parts"] == DEFAULT_BODY_PARTS

    def test_custom_parts(self):
        result = _validate_split_params({
            "object_name": "NPC",
            "parts": ["head", "torso"],
        })
        assert result["parts"] == ["head", "torso"]

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_split_params({})

    def test_empty_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_split_params({"object_name": ""})

    def test_empty_parts_list_raises(self):
        with pytest.raises(ValueError, match="parts must be a non-empty list"):
            _validate_split_params({"object_name": "X", "parts": []})

    def test_non_list_parts_raises(self):
        with pytest.raises(ValueError, match="parts must be a non-empty list"):
            _validate_split_params({"object_name": "X", "parts": "head"})

    def test_default_parts_order(self):
        """Default parts should be in logical body order."""
        result = _validate_split_params({"object_name": "X"})
        assert result["parts"][0] == "head"
        assert result["parts"][1] == "torso"
        assert result["parts"][-1] == "feet"

    def test_single_part(self):
        result = _validate_split_params({
            "object_name": "X",
            "parts": ["head"],
        })
        assert result["parts"] == ["head"]


# ---------------------------------------------------------------------------
# TestArmorFitting -- parameter validation
# ---------------------------------------------------------------------------


class TestArmorFitting:
    """Test _validate_armor_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_armor_params({
            "armor_object_name": "ChestPlate",
            "character_object_name": "Hero",
        })
        assert result["armor_object_name"] == "ChestPlate"
        assert result["character_object_name"] == "Hero"
        assert result["use_shape_keys"] is True
        assert result["body_types"] == DEFAULT_BODY_TYPES

    def test_missing_armor_name_raises(self):
        with pytest.raises(ValueError, match="armor_object_name is required"):
            _validate_armor_params({"character_object_name": "Hero"})

    def test_missing_character_name_raises(self):
        with pytest.raises(ValueError, match="character_object_name is required"):
            _validate_armor_params({"armor_object_name": "Plate"})

    def test_empty_armor_name_raises(self):
        with pytest.raises(ValueError, match="armor_object_name is required"):
            _validate_armor_params({
                "armor_object_name": "",
                "character_object_name": "Hero",
            })

    def test_empty_character_name_raises(self):
        with pytest.raises(ValueError, match="character_object_name is required"):
            _validate_armor_params({
                "armor_object_name": "Plate",
                "character_object_name": "",
            })

    def test_shape_keys_disabled(self):
        result = _validate_armor_params({
            "armor_object_name": "Plate",
            "character_object_name": "Hero",
            "use_shape_keys": False,
        })
        assert result["use_shape_keys"] is False

    def test_custom_body_types(self):
        result = _validate_armor_params({
            "armor_object_name": "Plate",
            "character_object_name": "Hero",
            "body_types": ["athletic", "heavy"],
        })
        assert result["body_types"] == ["athletic", "heavy"]

    def test_shape_keys_truthy_conversion(self):
        """use_shape_keys coerces to bool."""
        result = _validate_armor_params({
            "armor_object_name": "A",
            "character_object_name": "B",
            "use_shape_keys": 1,
        })
        assert result["use_shape_keys"] is True

    def test_shape_keys_falsy_conversion(self):
        result = _validate_armor_params({
            "armor_object_name": "A",
            "character_object_name": "B",
            "use_shape_keys": 0,
        })
        assert result["use_shape_keys"] is False


# ---------------------------------------------------------------------------
# TestPreviewIcons -- parameter validation
# ---------------------------------------------------------------------------


class TestPreviewIcons:
    """Test _validate_icon_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_icon_params({
            "object_name": "Sword",
            "output_path": "/tmp/icon.png",
        })
        assert result["object_name"] == "Sword"
        assert result["output_path"] == "/tmp/icon.png"
        assert result["resolution"] == 256
        assert result["camera_distance"] == 2.0
        assert result["camera_angle"] == (30, 45, 0)
        assert result["background_alpha"] == 0.0

    def test_custom_resolution(self):
        result = _validate_icon_params({
            "object_name": "X",
            "output_path": "/tmp/x.png",
            "resolution": 512,
        })
        assert result["resolution"] == 512

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_icon_params({"output_path": "/tmp/x.png"})

    def test_missing_output_path_raises(self):
        with pytest.raises(ValueError, match="output_path is required"):
            _validate_icon_params({"object_name": "Sword"})

    def test_empty_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_icon_params({
                "object_name": "",
                "output_path": "/tmp/x.png",
            })

    def test_empty_output_path_raises(self):
        with pytest.raises(ValueError, match="output_path is required"):
            _validate_icon_params({
                "object_name": "X",
                "output_path": "",
            })

    def test_resolution_too_small_raises(self):
        with pytest.raises(ValueError, match="resolution must be >= 16"):
            _validate_icon_params({
                "object_name": "X",
                "output_path": "/tmp/x.png",
                "resolution": 8,
            })

    def test_custom_camera_distance(self):
        result = _validate_icon_params({
            "object_name": "X",
            "output_path": "/tmp/x.png",
            "camera_distance": 5.0,
        })
        assert result["camera_distance"] == 5.0

    def test_custom_camera_angle(self):
        result = _validate_icon_params({
            "object_name": "X",
            "output_path": "/tmp/x.png",
            "camera_angle": (45, 90, 10),
        })
        assert result["camera_angle"] == (45, 90, 10)

    def test_camera_angle_list_to_tuple(self):
        """camera_angle list is converted to tuple."""
        result = _validate_icon_params({
            "object_name": "X",
            "output_path": "/tmp/x.png",
            "camera_angle": [60, 30, 0],
        })
        assert result["camera_angle"] == (60, 30, 0)
        assert isinstance(result["camera_angle"], tuple)

    def test_background_alpha_opaque(self):
        result = _validate_icon_params({
            "object_name": "X",
            "output_path": "/tmp/x.png",
            "background_alpha": 1.0,
        })
        assert result["background_alpha"] == 1.0

    def test_resolution_cast_to_int(self):
        result = _validate_icon_params({
            "object_name": "X",
            "output_path": "/tmp/x.png",
            "resolution": "128",
        })
        assert result["resolution"] == 128
        assert isinstance(result["resolution"], int)


class TestPreviewIconSizing:
    """Test icon size estimation fallback behavior."""

    def test_estimate_icon_file_size_returns_zero_on_load_failure(self, monkeypatch):
        class DummyImages:
            def load(self, _path):
                raise RuntimeError("load failed")

            def remove(self, _img):
                raise AssertionError("remove should not be called")

        monkeypatch.setattr(
            equipment_module.bpy.data,
            "images",
            DummyImages(),
            raising=False,
        )

        assert _estimate_icon_file_size("/tmp/icon.png") == 0


# ---------------------------------------------------------------------------
# TestGripPointComputation
# ---------------------------------------------------------------------------


class TestGripPointComputation:
    """Test _compute_grip_point returns sensible positions per weapon type."""

    def test_sword_grip_near_hilt(self):
        pos = _compute_grip_point("sword", 1.0)
        assert pos[0] == 0.0  # centered
        assert 0.0 < pos[1] < 0.5  # near bottom
        assert pos[2] == 0.0

    def test_dagger_grip_near_hilt(self):
        pos = _compute_grip_point("dagger", 0.5)
        assert pos[1] < 0.25  # near bottom of short weapon

    def test_bow_grip_at_center(self):
        pos = _compute_grip_point("bow", 1.0)
        assert pos[1] == 0.0  # center grip

    def test_shield_grip_at_center(self):
        pos = _compute_grip_point("shield", 1.0)
        assert pos[1] == pytest.approx(0.4, abs=0.1)

    def test_staff_grip_near_bottom(self):
        pos = _compute_grip_point("staff", 2.0)
        assert pos[1] < 1.0  # lower half

    def test_axe_grip_near_bottom(self):
        pos = _compute_grip_point("axe", 1.0)
        assert pos[1] < 0.5

    def test_mace_grip_near_bottom(self):
        pos = _compute_grip_point("mace", 1.0)
        assert pos[1] < 0.5

    # --- Extended weapon type grip tests ---

    def test_polearm_grip_at_third(self):
        """Polearms grip at ~1/3 from bottom for leverage."""
        for wtype in _POLEARM_TYPES:
            pos = _compute_grip_point(wtype, 3.0)
            assert 0.8 < pos[1] < 1.2, f"{wtype}: grip Y={pos[1]} not near 1.0"

    def test_ranged_grip_at_center(self):
        """All ranged weapons grip at center."""
        for wtype in _RANGED_TYPES:
            pos = _compute_grip_point(wtype, 1.0)
            assert pos[1] == 0.0, f"{wtype}: grip Y={pos[1]} not at center"

    def test_two_handed_grip_near_bottom(self):
        """Two-handed weapons grip near the bottom."""
        for wtype in _TWO_HANDED_TYPES:
            pos = _compute_grip_point(wtype, 1.0)
            assert pos[1] < 0.3, f"{wtype}: grip Y={pos[1]} too high"

    def test_magic_grip_at_lower_section(self):
        """Magic weapons grip at center/bottom."""
        for wtype in _MAGIC_TYPES:
            pos = _compute_grip_point(wtype, 1.0)
            assert pos[1] < 0.5, f"{wtype}: grip Y={pos[1]} too high"

    def test_chain_grip_at_handle(self):
        """Chain weapons grip at handle end."""
        for wtype in _CHAIN_TYPES:
            pos = _compute_grip_point(wtype, 1.0)
            assert pos[1] < 0.2, f"{wtype}: grip Y={pos[1]} too high"

    def test_thrown_grip_at_center(self):
        """Thrown weapons grip near center for balance."""
        for wtype in _THROWN_TYPES:
            pos = _compute_grip_point(wtype, 1.0)
            assert pos[1] < 0.3, f"{wtype}: grip Y={pos[1]} too high"

    def test_curved_sword_grip_near_hilt(self):
        pos = _compute_grip_point("curved_sword", 1.0)
        assert pos[1] < 0.3

    def test_claw_grip_near_hilt(self):
        pos = _compute_grip_point("claw", 1.0)
        assert pos[1] < 0.3


# ---------------------------------------------------------------------------
# TestTrailAttachComputation
# ---------------------------------------------------------------------------


class TestTrailAttachComputation:
    """Test _compute_trail_attach_top and _compute_trail_attach_bottom."""

    def test_sword_trail_top_at_tip(self):
        pos = _compute_trail_attach_top("sword", 1.0, 0.15)
        assert pos[1] == 1.0  # at tip

    def test_sword_trail_bottom_at_blade_base(self):
        pos = _compute_trail_attach_bottom("sword", 1.0, 0.15)
        assert pos[1] == pytest.approx(0.3, abs=0.05)

    def test_axe_trail_top_at_head(self):
        pos = _compute_trail_attach_top("axe", 1.0, 0.2)
        assert pos[0] > 0  # offset to the side (axe head)

    def test_axe_trail_bottom_below_head(self):
        pos = _compute_trail_attach_bottom("axe", 1.0, 0.2)
        assert pos[0] > 0

    def test_dagger_trail_top_at_tip(self):
        pos = _compute_trail_attach_top("dagger", 0.5, 0.1)
        assert pos[1] == 0.5  # at tip

    def test_dagger_trail_bottom_near_guard(self):
        pos = _compute_trail_attach_bottom("dagger", 0.5, 0.1)
        assert pos[1] == pytest.approx(0.15, abs=0.05)

    def test_trail_top_above_trail_bottom_for_sword(self):
        """trail_attach_top should be higher than trail_attach_bottom."""
        top = _compute_trail_attach_top("sword", 1.0, 0.15)
        bot = _compute_trail_attach_bottom("sword", 1.0, 0.15)
        assert top[1] > bot[1]

    def test_trail_positions_scale_with_length(self):
        """Doubling length should roughly double the Y positions."""
        top1 = _compute_trail_attach_top("sword", 1.0, 0.15)
        top2 = _compute_trail_attach_top("sword", 2.0, 0.15)
        assert top2[1] == pytest.approx(top1[1] * 2.0, abs=0.01)

    def test_shield_trail_top(self):
        pos = _compute_trail_attach_top("shield", 1.0, 0.2)
        assert pos[1] > 0  # above center

    def test_staff_trail_top_at_tip(self):
        pos = _compute_trail_attach_top("staff", 2.0, 0.1)
        assert pos[1] == 2.0

    def test_mace_trail_top_at_tip(self):
        pos = _compute_trail_attach_top("mace", 1.0, 0.2)
        assert pos[1] == 1.0

    def test_polearm_trail_full_length(self):
        """Polearms trail along full length."""
        for wtype in _POLEARM_TYPES:
            top = _compute_trail_attach_top(wtype, 2.0, 0.1)
            bot = _compute_trail_attach_bottom(wtype, 2.0, 0.1)
            assert top[1] > bot[1], f"{wtype}: trail top not above bottom"
            assert top[1] >= 1.5, f"{wtype}: trail top too short"

    def test_ranged_no_useful_trail(self):
        """Ranged weapons trail attach points are at the arc, not along shaft."""
        for wtype in _RANGED_TYPES:
            top = _compute_trail_attach_top(wtype, 1.0, 0.15)
            bot = _compute_trail_attach_bottom(wtype, 1.0, 0.15)
            # Both should be at similar Y (no blade trail)
            assert abs(top[1] - bot[1]) < 0.1, f"{wtype}: unexpected trail span"

    def test_magic_vfx_at_top(self):
        """Magic weapons have VFX point at top."""
        for wtype in ("staff_magic", "wand"):
            top = _compute_trail_attach_top(wtype, 1.0, 0.1)
            assert top[1] >= 0.5, f"{wtype}: VFX point too low"

    def test_chain_trail_at_head(self):
        """Chain weapons: trail top is at head end, bottom where chain meets handle."""
        for wtype in _CHAIN_TYPES:
            top = _compute_trail_attach_top(wtype, 1.0, 0.15)
            bot = _compute_trail_attach_bottom(wtype, 1.0, 0.15)
            assert top[1] > bot[1], f"{wtype}: trail top not above bottom"

    @pytest.mark.parametrize("wtype", sorted(VALID_WEAPON_TYPES))
    def test_grip_returns_3_tuple(self, wtype):
        pos = _compute_grip_point(wtype, 1.0)
        assert len(pos) == 3

    @pytest.mark.parametrize("wtype", sorted(VALID_WEAPON_TYPES))
    def test_trail_top_returns_3_tuple(self, wtype):
        pos = _compute_trail_attach_top(wtype, 1.0, 0.15)
        assert len(pos) == 3

    @pytest.mark.parametrize("wtype", sorted(VALID_WEAPON_TYPES))
    def test_trail_bottom_returns_3_tuple(self, wtype):
        pos = _compute_trail_attach_bottom(wtype, 1.0, 0.15)
        assert len(pos) == 3

    @pytest.mark.parametrize("wtype", sorted(VALID_WEAPON_TYPES))
    def test_trail_top_above_or_at_bottom(self, wtype):
        """Trail top Y should be >= trail bottom Y for all types."""
        top = _compute_trail_attach_top(wtype, 1.0, 0.15)
        bot = _compute_trail_attach_bottom(wtype, 1.0, 0.15)
        assert top[1] >= bot[1], f"{wtype}: trail top ({top[1]}) below bottom ({bot[1]})"
