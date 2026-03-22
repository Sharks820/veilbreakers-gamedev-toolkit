"""Comprehensive edge case stress tests for all T2 animation modules.

Tests every generator at minimum frame_count=4, every brand x slot combo,
seamless loop verification for multi-harmonic configs, and IK math.
"""
import math
import pytest

from blender_addon.handlers.animation_abilities import (
    VALID_ABILITY_SLOTS, VALID_BRANDS, VALID_STATUS_EFFECTS, VALID_CREATURE_TYPES,
    generate_ability_keyframes, generate_status_effect_keyframes,
    generate_combo_keyframes, generate_creature_combat_idle,
)
from blender_addon.handlers.animation_combat import (
    VALID_COMBAT_COMMANDS, generate_combat_command_keyframes,
)
from blender_addon.handlers.animation_hover import (
    VALID_HOVER_TYPES, generate_hover_keyframes,
)
from blender_addon.handlers.animation_blob import (
    VALID_BLOB_TYPES, generate_blob_keyframes,
)
from blender_addon.handlers.animation_spellcast import (
    generate_channel_keyframes, generate_release_keyframes, generate_sustain_keyframes,
)
from blender_addon.handlers.animation_ik import (
    compute_foot_correction, compute_hip_correction, smooth_corrections,
)
from blender_addon.handlers.animation_gaits import (
    Keyframe, generate_cycle_keyframes,
    BIPED_WALK_CONFIG, BIPED_RUN_CONFIG,
    QUADRUPED_WALK_CONFIG, QUADRUPED_TROT_CONFIG,
    QUADRUPED_CANTER_CONFIG, QUADRUPED_GALLOP_CONFIG,
    HEXAPOD_WALK_CONFIG, ARACHNID_WALK_CONFIG, SERPENT_WALK_CONFIG,
    FLY_HOVER_CONFIG, IDLE_CONFIG,
)
from blender_addon.handlers._combat_timing import (
    BRAND_TIMING_MODIFIERS, apply_brand_timing, configure_combat_timing,
)


class TestAbilityStress:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    @pytest.mark.parametrize("slot", sorted(VALID_ABILITY_SLOTS))
    def test_brand_slot_fc4(self, brand, slot):
        kfs = generate_ability_keyframes({"brand": brand, "slot": slot, "frame_count": 4, "intensity": 1.0})
        assert len(kfs) > 0

    @pytest.mark.parametrize("effect", sorted(VALID_STATUS_EFFECTS))
    def test_status_fc4(self, effect):
        kfs = generate_status_effect_keyframes(effect=effect, frame_count=4)
        assert len(kfs) > 0

    @pytest.mark.parametrize("ct", sorted(VALID_CREATURE_TYPES))
    def test_creature_idle_fc4(self, ct):
        kfs = generate_creature_combat_idle(creature_type=ct, frame_count=4)
        assert len(kfs) > 0

    @pytest.mark.parametrize("hits", [1, 2, 3, 4, 5, 6])
    def test_combo_fc4(self, hits):
        kfs = generate_combo_keyframes(hit_count=hits, frame_count=max(4, hits * 2))
        assert len(kfs) > 0


class TestCombatStress:
    @pytest.mark.parametrize("cmd", sorted(VALID_COMBAT_COMMANDS))
    def test_command_fc4(self, cmd):
        kfs = generate_combat_command_keyframes({"command": cmd, "brand": "IRON", "frame_count": 4, "stumble": False})
        assert len(kfs) > 0


class TestHoverStress:
    @pytest.mark.parametrize("ht", sorted(VALID_HOVER_TYPES))
    def test_hover_fc4(self, ht):
        kfs = generate_hover_keyframes({"hover_type": ht, "bob_amplitude": 0.05, "bob_frequency": 0.8,
                                         "bank_angle": 0.3, "drift_amount": 0.02, "frame_count": 4})
        assert len(kfs) > 0


class TestBlobStress:
    @pytest.mark.parametrize("bt", sorted(VALID_BLOB_TYPES))
    def test_blob_fc4(self, bt):
        kfs = generate_blob_keyframes({"blob_type": bt, "frame_count": 4, "direction": "forward", "intensity": 1.0})
        assert len(kfs) > 0


class TestSpellStress:
    @pytest.mark.parametrize("hand", ["left", "right", "both"])
    def test_channel_fc4(self, hand):
        assert len(generate_channel_keyframes(cast_hand=hand, frame_count=4)) > 0

    @pytest.mark.parametrize("hand", ["left", "right", "both"])
    def test_release_fc4(self, hand):
        assert len(generate_release_keyframes(cast_hand=hand, frame_count=4)) > 0

    @pytest.mark.parametrize("hand", ["left", "right", "both"])
    def test_sustain_fc4(self, hand):
        assert len(generate_sustain_keyframes(cast_hand=hand, frame_count=4)) > 0


class TestGaitLoopSeamless:
    """Verify frame 0 == frame N for all gait configs including multi-harmonic."""

    @pytest.mark.parametrize("name,config", [
        ("biped_walk", BIPED_WALK_CONFIG), ("biped_run", BIPED_RUN_CONFIG),
        ("quad_walk", QUADRUPED_WALK_CONFIG), ("quad_trot", QUADRUPED_TROT_CONFIG),
        ("quad_canter", QUADRUPED_CANTER_CONFIG), ("quad_gallop", QUADRUPED_GALLOP_CONFIG),
        ("hexapod_walk", HEXAPOD_WALK_CONFIG), ("arachnid_walk", ARACHNID_WALK_CONFIG),
        ("serpent_walk", SERPENT_WALK_CONFIG), ("fly_hover", FLY_HOVER_CONFIG),
        ("idle", IDLE_CONFIG),
    ])
    def test_seamless_loop(self, name, config):
        kfs = generate_cycle_keyframes(config)
        fc = config["frame_count"]
        by_key = {}
        for kf in kfs:
            key = (kf.bone_name, kf.channel, kf.axis)
            by_key.setdefault(key, {})[kf.frame] = kf.value
        for key, frames in by_key.items():
            if 0 in frames and fc in frames:
                assert frames[0] == pytest.approx(frames[fc], abs=1e-6), (
                    f"Loop break in {name} {key}: f0={frames[0]:.6f} fN={frames[fc]:.6f}"
                )


class TestBrandTimingStress:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    @pytest.mark.parametrize("attack", ["light_attack", "heavy_attack", "charged_attack"])
    def test_brand_timing_no_crash(self, brand, attack):
        timing = configure_combat_timing(attack)
        result = apply_brand_timing(timing, brand)
        assert result["frames"]["total"] > 0
        assert result["frames"]["anticipation"] >= 1
        assert result["frames"]["recovery"] >= 1


class TestIKStress:
    def test_flat_ground(self):
        r = compute_foot_correction(0.0, 0.0, (0, 0, 1))
        assert r["z_correction"] == pytest.approx(0.0)

    def test_steep_slope(self):
        r = compute_foot_correction(0.0, 0.0, (0, 0.99, 0.14))
        assert abs(r["ankle_pitch"]) <= 0.5  # clamped

    def test_hip_correction_multiple_feet(self):
        corrections = [{"z_correction": -0.3}, {"z_correction": 0.1}]
        r = compute_hip_correction(corrections)
        assert r < 0

    def test_smooth_single_frame(self):
        kfs = [Keyframe("A", "location", 0, 0, 1.0)]
        result = smooth_corrections(kfs, passes=3)
        assert len(result) == 1
