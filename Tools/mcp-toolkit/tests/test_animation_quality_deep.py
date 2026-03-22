"""Deep animation quality validation — verifies output VALUES are physically correct.

Not just crash tests — these verify:
1. Seamless loops (frame 0 == frame N for every bone)
2. No extreme values (rotations < 3.5 rad, locations < 2.0)
3. Anti-phase biped walk (L/R legs opposite)
4. Attack phase timing (peak in strike phase, not edges)
5. All 10 defeat brands produce unique animations
6. Status effects are subtle enough for overlay
7. Door reaches target angle
8. Fire flicker actually oscillates
9. Combo alternates sides
10. Hover bob is sinusoidal (not flat)
"""
import math
import pytest

from blender_addon.handlers.animation_gaits import (
    generate_cycle_keyframes, generate_attack_keyframes,
    BIPED_WALK_CONFIG, BIPED_RUN_CONFIG, QUADRUPED_WALK_CONFIG,
    QUADRUPED_GALLOP_CONFIG, IDLE_CONFIG, FLY_HOVER_CONFIG,
    ARACHNID_WALK_CONFIG, SERPENT_WALK_CONFIG,
)
from blender_addon.handlers.animation_abilities import (
    generate_brand_basic_attack, generate_brand_ultimate,
    generate_status_effect_keyframes, generate_combo_keyframes,
)
from blender_addon.handlers.animation_combat import (
    generate_defeat_collapse_keyframes, generate_guard_keyframes,
)
from blender_addon.handlers.animation_hover import generate_hover_idle_keyframes
from blender_addon.handlers.animation_environment import (
    generate_door_open_keyframes, generate_fire_flicker_keyframes,
)


class TestSeamlessLoops:
    @pytest.mark.parametrize("name,config", [
        ("biped_walk", BIPED_WALK_CONFIG), ("biped_run", BIPED_RUN_CONFIG),
        ("quad_walk", QUADRUPED_WALK_CONFIG), ("quad_gallop", QUADRUPED_GALLOP_CONFIG),
        ("idle", IDLE_CONFIG), ("fly_hover", FLY_HOVER_CONFIG),
        ("arachnid_walk", ARACHNID_WALK_CONFIG), ("serpent_walk", SERPENT_WALK_CONFIG),
    ])
    def test_loop_seamless(self, name, config):
        kfs = generate_cycle_keyframes(config)
        fc = config["frame_count"]
        by_key = {}
        for kf in kfs:
            key = (kf.bone_name, kf.channel, kf.axis)
            by_key.setdefault(key, {})[kf.frame] = kf.value
        for key, frames in by_key.items():
            if 0 in frames and fc in frames:
                diff = abs(frames[0] - frames[fc])
                assert diff < 1e-6, f"Loop break in {name} {key}: diff={diff:.8f}"


class TestNoExtremeValues:
    @pytest.mark.parametrize("name,gen,kwargs", [
        ("IRON_attack", generate_brand_basic_attack, {"brand": "IRON"}),
        ("SAVAGE_attack", generate_brand_basic_attack, {"brand": "SAVAGE"}),
        ("SURGE_attack", generate_brand_basic_attack, {"brand": "SURGE"}),
        ("IRON_ultimate", generate_brand_ultimate, {"brand": "IRON"}),
        ("guard", generate_guard_keyframes, {}),
        ("hover", generate_hover_idle_keyframes, {}),
    ])
    def test_values_in_range(self, name, gen, kwargs):
        kfs = gen(**kwargs)
        for kf in kfs:
            if kf.channel == "rotation_euler":
                assert abs(kf.value) < 3.5, (
                    f"Extreme rotation in {name}: {kf.bone_name} f={kf.frame} val={kf.value:.3f}"
                )
            if kf.channel == "location":
                assert abs(kf.value) < 2.0, (
                    f"Extreme location in {name}: {kf.bone_name} f={kf.frame} val={kf.value:.3f}"
                )


class TestBipedAntiPhase:
    def test_thighs_opposite_at_quarter_cycle(self):
        kfs = generate_cycle_keyframes(BIPED_WALK_CONFIG)
        fc = BIPED_WALK_CONFIG["frame_count"]
        thigh_l = {kf.frame: kf.value for kf in kfs
                   if kf.bone_name == "DEF-thigh.L" and kf.channel == "rotation_euler" and kf.axis == 0}
        thigh_r = {kf.frame: kf.value for kf in kfs
                   if kf.bone_name == "DEF-thigh.R" and kf.channel == "rotation_euler" and kf.axis == 0}
        quarter = fc // 4
        assert quarter in thigh_l and quarter in thigh_r
        # At quarter cycle, L and R should have opposite signs
        assert thigh_l[quarter] * thigh_r[quarter] <= 0, (
            f"Not anti-phase: L={thigh_l[quarter]:.3f} R={thigh_r[quarter]:.3f}"
        )


class TestAttackPhaseTiming:
    @pytest.mark.parametrize("attack_type", ["melee_swing", "thrust", "slam", "claw"])
    def test_peak_in_strike_phase(self, attack_type):
        kfs = generate_attack_keyframes(attack_type, frame_count=24)
        arm_kfs = [kf for kf in kfs if "upper_arm" in kf.bone_name and kf.channel == "rotation_euler"]
        if arm_kfs:
            max_kf = max(arm_kfs, key=lambda k: abs(k.value))
            # Peak should be in middle of animation (not first or last 2 frames)
            assert 2 <= max_kf.frame <= 22, (
                f"{attack_type}: peak at frame {max_kf.frame}, expected 2-22"
            )


class TestDefeatBrandUniqueness:
    def test_all_10_brands_unique(self):
        fingerprints = {}
        for brand in ["IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                       "LEECH", "GRACE", "MEND", "RUIN", "VOID"]:
            kfs = generate_defeat_collapse_keyframes(brand=brand, frame_count=36)
            # Fingerprint: sum of absolute values at midpoint
            mid = sum(abs(kf.value) for kf in kfs if kf.frame == 18)
            fingerprints[brand] = round(mid, 2)

        unique = set(fingerprints.values())
        assert len(unique) == 10, (
            f"Only {len(unique)} unique defeat styles out of 10: {fingerprints}"
        )


class TestStatusEffectSubtlety:
    @pytest.mark.parametrize("effect", ["poison", "burn", "freeze", "bleed", "stun", "fear"])
    def test_overlay_not_too_strong(self, effect):
        kfs = generate_status_effect_keyframes(effect=effect, frame_count=48)
        max_val = max(abs(kf.value) for kf in kfs)
        assert max_val < 0.6, f"{effect} too strong for overlay: max={max_val:.3f}"


class TestDoorReachesTarget:
    def test_90_degree_open(self):
        kfs = generate_door_open_keyframes(frame_count=30, angle=90)
        final = [kf.value for kf in kfs if kf.frame == 30][0]
        target = math.radians(90)
        assert abs(final - target) < 0.15, (
            f"Door: {math.degrees(final):.1f} deg, expected ~90"
        )


class TestFireOscillates:
    def test_flame_scale_varies(self):
        kfs = generate_fire_flicker_keyframes()
        scales = [kf.value for kf in kfs if kf.channel == "scale" and kf.axis == 1]
        rng = max(scales) - min(scales)
        assert rng > 0.05, f"Fire flicker range too small: {rng:.3f}"


class TestComboAlternates:
    def test_3hit_uses_both_arms(self):
        kfs = generate_combo_keyframes(hit_count=3, frame_count=36)
        right = any(kf.bone_name == "DEF-upper_arm.R" for kf in kfs)
        left = any(kf.bone_name == "DEF-upper_arm.L" for kf in kfs)
        assert right and left, "Combo should alternate arms"


class TestHoverBobSinusoidal:
    def test_bob_has_positive_and_negative(self):
        kfs = generate_hover_idle_keyframes(bob_amplitude=0.1)
        z_vals = [kf.value for kf in kfs
                  if kf.bone_name == "DEF-spine" and kf.channel == "location" and kf.axis == 2]
        assert max(z_vals) > 0.05, "Hover should bob up"
        assert min(z_vals) < -0.05, "Hover should bob down"
