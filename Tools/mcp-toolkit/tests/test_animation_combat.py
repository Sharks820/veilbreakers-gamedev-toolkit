"""Tests for combat command flow animation generators.

All pure-logic -- no Blender required.
"""

import math
import pytest

from blender_addon.handlers.animation_combat import (
    VALID_BRANDS,
    VALID_COMBAT_COMMANDS,
    generate_combat_command_keyframes,
    generate_combat_idle_keyframes,
    generate_command_receive_keyframes,
    generate_approach_keyframes,
    generate_return_to_formation_keyframes,
    generate_guard_keyframes,
    generate_flee_keyframes,
    generate_target_switch_keyframes,
    generate_synergy_activation_keyframes,
    generate_ultimate_windup_keyframes,
    generate_victory_pose_keyframes,
    generate_defeat_collapse_keyframes,
    validate_combat_command_params,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidateCombatCommandParams:
    def test_valid_params(self):
        result = validate_combat_command_params({
            "object_name": "Enemy",
            "command": "combat_idle",
        })
        assert result["command"] == "combat_idle"
        assert result["brand"] == "IRON"

    def test_missing_object_name(self):
        with pytest.raises(ValueError, match="object_name"):
            validate_combat_command_params({"command": "guard"})

    def test_missing_command(self):
        with pytest.raises(ValueError, match="command"):
            validate_combat_command_params({"object_name": "X"})

    def test_invalid_command(self):
        with pytest.raises(ValueError, match="Invalid command"):
            validate_combat_command_params({"object_name": "X", "command": "dance"})

    def test_invalid_brand(self):
        with pytest.raises(ValueError, match="Invalid brand"):
            validate_combat_command_params({
                "object_name": "X", "command": "guard", "brand": "FIRE"
            })

    def test_brand_case_insensitive(self):
        result = validate_combat_command_params({
            "object_name": "X", "command": "guard", "brand": "iron"
        })
        assert result["brand"] == "IRON"

    @pytest.mark.parametrize("cmd", sorted(VALID_COMBAT_COMMANDS))
    def test_all_commands_accepted(self, cmd):
        result = validate_combat_command_params({
            "object_name": "X", "command": cmd,
        })
        assert result["command"] == cmd


class TestConstants:
    def test_valid_commands_count(self):
        assert len(VALID_COMBAT_COMMANDS) == 11

    def test_valid_brands_count(self):
        assert len(VALID_BRANDS) == 10

    def test_p0_commands_present(self):
        p0 = {"command_receive", "combat_idle", "approach", "return_to_formation", "guard"}
        assert p0.issubset(VALID_COMBAT_COMMANDS)

    def test_p1_commands_present(self):
        p1 = {"flee", "target_switch", "synergy_activation"}
        assert p1.issubset(VALID_COMBAT_COMMANDS)

    def test_p2_commands_present(self):
        p2 = {"ultimate_windup", "victory_pose", "defeat_collapse"}
        assert p2.issubset(VALID_COMBAT_COMMANDS)


class TestCommandReceive:
    def test_returns_keyframes(self):
        kfs = generate_command_receive_keyframes()
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_short_duration(self):
        kfs = generate_command_receive_keyframes(frame_count=12)
        max_frame = max(kf.frame for kf in kfs)
        assert max_frame == 12

    def test_has_head_nod(self):
        kfs = generate_command_receive_keyframes()
        head_kfs = [kf for kf in kfs if "spine.004" in kf.bone_name]
        assert len(head_kfs) > 0
        values = [kf.value for kf in head_kfs]
        assert max(values) > 0  # head nods forward


class TestCombatIdle:
    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_generate_keyframes(self, brand):
        kfs = generate_combat_idle_keyframes(brand=brand, frame_count=24)
        assert len(kfs) > 0

    def test_iron_wider_stance_than_grace(self):
        iron_kfs = generate_combat_idle_keyframes(brand="IRON")
        grace_kfs = generate_combat_idle_keyframes(brand="GRACE")
        iron_arms = [kf for kf in iron_kfs if "upper_arm" in kf.bone_name]
        grace_arms = [kf for kf in grace_kfs if "upper_arm" in kf.bone_name]
        iron_spread = max(abs(kf.value) for kf in iron_arms) if iron_arms else 0
        grace_spread = max(abs(kf.value) for kf in grace_arms) if grace_arms else 0
        assert iron_spread > grace_spread

    def test_dread_minimal_sway(self):
        kfs = generate_combat_idle_keyframes(brand="DREAD", frame_count=48)
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine" and kf.channel == "rotation_euler"]
        if spine_kfs:
            max_sway = max(abs(kf.value) for kf in spine_kfs)
            assert max_sway < 0.01  # DREAD is unnaturally still


class TestApproach:
    def test_returns_keyframes(self):
        kfs = generate_approach_keyframes()
        assert len(kfs) > 0

    def test_has_leg_motion(self):
        kfs = generate_approach_keyframes()
        leg_kfs = [kf for kf in kfs if "thigh" in kf.bone_name]
        assert len(leg_kfs) > 0

    def test_windup_in_last_quarter(self):
        fc = 32
        kfs = generate_approach_keyframes(frame_count=fc)
        # Check that right arm pulls back in last 25%
        late_arm_kfs = [kf for kf in kfs
                        if kf.bone_name == "DEF-upper_arm.R" and kf.frame > fc * 0.75]
        if late_arm_kfs:
            assert any(kf.value < -0.1 for kf in late_arm_kfs)


class TestGuard:
    def test_arms_raised(self):
        kfs = generate_guard_keyframes()
        arm_kfs = [kf for kf in kfs if "upper_arm" in kf.bone_name]
        values = [kf.value for kf in arm_kfs]
        assert min(values) < -0.5  # arms raised significantly


class TestFlee:
    def test_returns_keyframes(self):
        kfs = generate_flee_keyframes()
        assert len(kfs) > 0

    def test_stumble_variant(self):
        kfs_no_stumble = generate_flee_keyframes(stumble=False)
        kfs_stumble = generate_flee_keyframes(stumble=True)
        # Stumble variant has additional bone keyframes
        bones_no = {kf.bone_name for kf in kfs_no_stumble}
        bones_yes = {kf.bone_name for kf in kfs_stumble}
        # Stumble adds shin bone or spine pitch
        assert len(bones_yes) >= len(bones_no)

    def test_has_turn_phase(self):
        kfs = generate_flee_keyframes()
        spine_y = [kf for kf in kfs if kf.bone_name == "DEF-spine"
                    and kf.channel == "rotation_euler" and kf.axis == 1]
        if spine_y:
            max_rot = max(kf.value for kf in spine_y)
            assert max_rot >= math.pi * 0.9  # ~180 degree turn


class TestTargetSwitch:
    def test_head_leads_body(self):
        kfs = generate_target_switch_keyframes(frame_count=16)
        head_kfs = [kf for kf in kfs if "spine.004" in kf.bone_name]
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        if head_kfs and spine_kfs:
            # Head should start rotating before spine
            head_start = min(kf.frame for kf in head_kfs if abs(kf.value) > 0.01)
            spine_vals = [(kf.frame, kf.value) for kf in spine_kfs if abs(kf.value) > 0.01]
            if spine_vals:
                spine_start = min(f for f, v in spine_vals)
                assert head_start <= spine_start


class TestDefeatCollapse:
    @pytest.mark.parametrize("brand", ["IRON", "VOID"])
    def test_brand_specific_styles(self, brand):
        kfs = generate_defeat_collapse_keyframes(brand=brand)
        assert len(kfs) > 0

    def test_iron_forward_collapse(self):
        kfs = generate_defeat_collapse_keyframes(brand="IRON")
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"]
        final_values = [kf.value for kf in spine_kfs if kf.frame > 30]
        if final_values:
            assert max(final_values) > 0.5  # strong forward bend


class TestDispatch:
    @pytest.mark.parametrize("cmd", sorted(VALID_COMBAT_COMMANDS))
    def test_dispatch_all_commands(self, cmd):
        params = {
            "command": cmd,
            "brand": "IRON",
            "frame_count": 16,
            "stumble": False,
        }
        kfs = generate_combat_command_keyframes(params)
        assert isinstance(kfs, list)
        assert len(kfs) > 0

    def test_dispatch_unknown_raises(self):
        with pytest.raises(ValueError):
            generate_combat_command_keyframes({"command": "dance"})
