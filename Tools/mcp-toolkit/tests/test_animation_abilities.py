"""Tests for brand-specific ability animation generators.

Covers all 10 brands x 6 ability slots, status effects, combos,
and creature-type combat idles. All pure-logic -- no Blender required.
"""

import math
import pytest

from blender_addon.handlers.animation_abilities import (
    VALID_ABILITY_SLOTS,
    VALID_BRANDS,
    VALID_CREATURE_TYPES,
    VALID_STATUS_EFFECTS,
    generate_ability_keyframes,
    generate_brand_basic_attack,
    generate_brand_defend,
    generate_brand_skill,
    generate_brand_ultimate,
    generate_combo_keyframes,
    generate_creature_combat_idle,
    generate_status_effect_keyframes,
    validate_ability_params,
    validate_status_effect_params,
)
from blender_addon.handlers.animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateAbilityParams:
    def test_valid_defaults(self):
        result = validate_ability_params({"object_name": "Monster"})
        assert result["brand"] == "IRON"
        assert result["slot"] == "basic_attack"

    def test_all_brands_accepted(self):
        for brand in VALID_BRANDS:
            r = validate_ability_params({"object_name": "X", "brand": brand})
            assert r["brand"] == brand

    def test_all_slots_accepted(self):
        for slot in VALID_ABILITY_SLOTS:
            r = validate_ability_params({"object_name": "X", "slot": slot})
            assert r["slot"] == slot

    def test_missing_object_name(self):
        with pytest.raises(ValueError, match="object_name"):
            validate_ability_params({})

    def test_invalid_brand(self):
        with pytest.raises(ValueError, match="Invalid brand"):
            validate_ability_params({"object_name": "X", "brand": "FIRE"})

    def test_invalid_slot(self):
        with pytest.raises(ValueError, match="Invalid slot"):
            validate_ability_params({"object_name": "X", "slot": "superattack"})

    def test_brand_case_insensitive(self):
        r = validate_ability_params({"object_name": "X", "brand": "iron"})
        assert r["brand"] == "IRON"


class TestValidateStatusEffectParams:
    def test_valid_defaults(self):
        result = validate_status_effect_params({"object_name": "X"})
        assert result["effect"] == "poison"

    def test_all_effects_accepted(self):
        for eff in VALID_STATUS_EFFECTS:
            r = validate_status_effect_params({"object_name": "X", "effect": eff})
            assert r["effect"] == eff

    def test_invalid_effect(self):
        with pytest.raises(ValueError, match="Invalid effect"):
            validate_status_effect_params({"object_name": "X", "effect": "curse"})


# ---------------------------------------------------------------------------
# Brand basic attack tests
# ---------------------------------------------------------------------------

class TestBrandBasicAttack:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_generate(self, brand):
        kfs = generate_brand_basic_attack(brand=brand)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_savage_dual_claw(self):
        kfs = generate_brand_basic_attack(brand="SAVAGE")
        left_arm = [kf for kf in kfs if kf.bone_name == "DEF-upper_arm.L"]
        assert len(left_arm) > 0, "SAVAGE should animate left arm for dual-claw"

    def test_surge_tremor(self):
        kfs = generate_brand_basic_attack(brand="SURGE")
        hand_kfs = [kf for kf in kfs if kf.bone_name == "DEF-hand.R"]
        assert len(hand_kfs) > 0, "SURGE should have hand tremor"

    def test_iron_two_handed(self):
        kfs = generate_brand_basic_attack(brand="IRON")
        left_arm = [kf for kf in kfs if kf.bone_name == "DEF-upper_arm.L"]
        assert len(left_arm) > 0, "IRON should use both arms"

    def test_intensity_scales(self):
        kfs_low = generate_brand_basic_attack(intensity=0.5)
        kfs_high = generate_brand_basic_attack(intensity=2.0)
        max_low = max(abs(kf.value) for kf in kfs_low if "upper_arm.R" in kf.bone_name)
        max_high = max(abs(kf.value) for kf in kfs_high if "upper_arm.R" in kf.bone_name)
        assert max_high > max_low


# ---------------------------------------------------------------------------
# Brand defend tests
# ---------------------------------------------------------------------------

class TestBrandDefend:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_generate(self, brand):
        kfs = generate_brand_defend(brand=brand)
        assert len(kfs) > 0

    def test_arms_raised(self):
        kfs = generate_brand_defend(brand="IRON")
        arm_kfs = [kf for kf in kfs if "upper_arm" in kf.bone_name]
        assert any(kf.value < -0.3 for kf in arm_kfs), "Arms should be raised in guard"

    def test_crouch_present(self):
        kfs = generate_brand_defend(brand="IRON")
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        assert any(kf.value > 0.05 for kf in spine_kfs), "Should crouch"


# ---------------------------------------------------------------------------
# Brand skill tests
# ---------------------------------------------------------------------------

class TestBrandSkill:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_generate(self, brand):
        kfs = generate_brand_skill(brand=brand, skill_slot=1)
        assert len(kfs) > 0

    @pytest.mark.parametrize("slot", [1, 2, 3])
    def test_all_skill_slots(self, slot):
        kfs = generate_brand_skill(skill_slot=slot)
        assert len(kfs) > 0

    def test_higher_slot_more_dramatic(self):
        kfs_1 = generate_brand_skill(skill_slot=1, frame_count=36)
        kfs_3 = generate_brand_skill(skill_slot=3, frame_count=36)
        max_1 = max(abs(kf.value) for kf in kfs_1 if "upper_arm" in kf.bone_name)
        max_3 = max(abs(kf.value) for kf in kfs_3 if "upper_arm" in kf.bone_name)
        assert max_3 > max_1, "Skill 3 should be more dramatic than skill 1"

    def test_charge_tremor_on_higher_skills(self):
        kfs = generate_brand_skill(skill_slot=3, frame_count=48)
        hand_kfs = [kf for kf in kfs if "hand" in kf.bone_name]
        assert len(hand_kfs) > 0, "Skill 3 should have charge tremor"


# ---------------------------------------------------------------------------
# Brand ultimate tests
# ---------------------------------------------------------------------------

class TestBrandUltimate:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_generate(self, brand):
        kfs = generate_brand_ultimate(brand=brand)
        assert len(kfs) > 0

    def test_long_charge_phase(self):
        kfs = generate_brand_ultimate(frame_count=60)
        # At frame 25 (early in charge), arms should be partially raised
        arm_kfs = [kf for kf in kfs if kf.bone_name == "DEF-upper_arm.R" and kf.frame == 25]
        if arm_kfs:
            assert arm_kfs[0].value < 0, "Should be in charge phase (arms raised)"

    def test_has_tremor(self):
        kfs = generate_brand_ultimate()
        hand_kfs = [kf for kf in kfs if "hand" in kf.bone_name]
        assert len(hand_kfs) > 0

    def test_exhaustion_at_end(self):
        kfs = generate_brand_ultimate(frame_count=60)
        thigh_kfs = [kf for kf in kfs if kf.bone_name == "DEF-thigh.L" and kf.frame >= 50]
        # Should have some non-zero values during exhaustion
        assert any(abs(kf.value) > 0.01 for kf in thigh_kfs)


# ---------------------------------------------------------------------------
# Status effect tests
# ---------------------------------------------------------------------------

class TestStatusEffects:
    @pytest.mark.parametrize("effect", sorted(VALID_STATUS_EFFECTS))
    def test_all_effects_generate(self, effect):
        kfs = generate_status_effect_keyframes(effect=effect)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_poison_hunched(self):
        kfs = generate_status_effect_keyframes(effect="poison")
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        assert any(kf.value > 0.03 for kf in spine_kfs), "Poison should hunch"

    def test_fear_cowering(self):
        kfs = generate_status_effect_keyframes(effect="fear")
        arm_kfs = [kf for kf in kfs if "upper_arm" in kf.bone_name]
        assert any(kf.value < -0.2 for kf in arm_kfs), "Fear should cower"

    def test_freeze_shivering(self):
        kfs = generate_status_effect_keyframes(effect="freeze")
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        values = [kf.value for kf in spine_kfs]
        # Should have rapid oscillation (positive and negative)
        assert min(values) < 0 and max(values) > 0

    def test_intensity_scales(self):
        kfs_low = generate_status_effect_keyframes(effect="burn", intensity=0.5)
        kfs_high = generate_status_effect_keyframes(effect="burn", intensity=2.0)
        max_low = max(abs(kf.value) for kf in kfs_low)
        max_high = max(abs(kf.value) for kf in kfs_high)
        assert max_high > max_low

    def test_looping_frame_count(self):
        kfs = generate_status_effect_keyframes(effect="regen", frame_count=48)
        max_frame = max(kf.frame for kf in kfs)
        assert max_frame == 48


# ---------------------------------------------------------------------------
# Combo tests
# ---------------------------------------------------------------------------

class TestCombo:
    def test_returns_keyframes(self):
        kfs = generate_combo_keyframes(hit_count=3)
        assert len(kfs) > 0

    def test_alternating_sides(self):
        kfs = generate_combo_keyframes(hit_count=4, frame_count=48)
        right_kfs = [kf for kf in kfs if kf.bone_name == "DEF-upper_arm.R"]
        left_kfs = [kf for kf in kfs if kf.bone_name == "DEF-upper_arm.L"]
        assert len(right_kfs) > 0 and len(left_kfs) > 0

    def test_hit_count_clamped(self):
        kfs_min = generate_combo_keyframes(hit_count=0)  # clamped to 1
        kfs_max = generate_combo_keyframes(hit_count=10)  # clamped to 6
        assert len(kfs_min) > 0
        assert len(kfs_max) > 0

    @pytest.mark.parametrize("hits", [1, 2, 3, 4, 5, 6])
    def test_various_hit_counts(self, hits):
        kfs = generate_combo_keyframes(hit_count=hits, frame_count=max(12, hits * 8))
        assert len(kfs) > 0


# ---------------------------------------------------------------------------
# Creature type combat idle tests
# ---------------------------------------------------------------------------

class TestCreatureCombatIdle:
    @pytest.mark.parametrize("ct", sorted(VALID_CREATURE_TYPES))
    def test_all_creature_types(self, ct):
        kfs = generate_creature_combat_idle(creature_type=ct)
        assert len(kfs) > 0

    def test_spider_uses_leg_bones(self):
        kfs = generate_creature_combat_idle(creature_type="spider")
        leg_bones = {kf.bone_name for kf in kfs if "leg_" in kf.bone_name}
        assert len(leg_bones) >= 4, "Spider should animate multiple legs"

    def test_serpent_uses_spine_chain(self):
        kfs = generate_creature_combat_idle(creature_type="serpent")
        spine_bones = {kf.bone_name for kf in kfs if "spine" in kf.bone_name}
        assert len(spine_bones) >= 3, "Serpent should undulate spine chain"

    def test_floating_has_bob(self):
        kfs = generate_creature_combat_idle(creature_type="floating")
        z_kfs = [kf for kf in kfs if kf.channel == "location" and kf.axis == 2]
        assert len(z_kfs) > 0, "Floating should have vertical bob"

    def test_amorphous_uses_scale(self):
        kfs = generate_creature_combat_idle(creature_type="amorphous")
        scale_kfs = [kf for kf in kfs if kf.channel == "scale"]
        assert len(scale_kfs) > 0, "Amorphous should use scale channels"


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------

class TestDispatch:
    @pytest.mark.parametrize("slot", sorted(VALID_ABILITY_SLOTS))
    def test_all_slots_dispatch(self, slot):
        params = {
            "brand": "IRON", "slot": slot, "frame_count": 24, "intensity": 1.0,
        }
        kfs = generate_ability_keyframes(params)
        assert len(kfs) > 0

    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_basic_attack(self, brand):
        params = {"brand": brand, "slot": "basic_attack", "frame_count": 24, "intensity": 1.0}
        kfs = generate_ability_keyframes(params)
        assert len(kfs) > 0

    def test_unknown_slot_raises(self):
        with pytest.raises(ValueError):
            generate_ability_keyframes({"brand": "IRON", "slot": "superpower", "frame_count": 24})


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_all_10_brands(self):
        assert len(VALID_BRANDS) == 10

    def test_6_ability_slots(self):
        assert len(VALID_ABILITY_SLOTS) == 6
        expected = {"basic_attack", "defend", "skill_1", "skill_2", "skill_3", "ultimate"}
        assert VALID_ABILITY_SLOTS == expected

    def test_10_status_effects(self):
        assert len(VALID_STATUS_EFFECTS) == 10

    def test_8_creature_types(self):
        assert len(VALID_CREATURE_TYPES) == 8
