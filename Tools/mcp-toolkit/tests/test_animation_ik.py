"""Tests for IK foot placement ground-contact solver.

All pure-logic -- no Blender required.
"""

import math
import pytest

from blender_addon.handlers.animation_ik import (
    DEFAULT_FOOT_BONES,
    DEFAULT_HIP_BONE,
    VALID_TERRAIN_TYPES,
    compute_foot_correction,
    compute_hip_correction,
    generate_ik_corrected_keyframes,
    smooth_corrections,
    validate_ik_foot_params,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidateIKFootParams:
    def test_valid_defaults(self):
        result = validate_ik_foot_params({
            "object_name": "Character",
            "action_name": "walk",
        })
        assert result["foot_bones"] == DEFAULT_FOOT_BONES
        assert result["hip_bone"] == DEFAULT_HIP_BONE
        assert result["terrain_type"] == "auto"

    def test_missing_object_name(self):
        with pytest.raises(ValueError, match="object_name"):
            validate_ik_foot_params({"action_name": "walk"})

    def test_missing_action_name(self):
        with pytest.raises(ValueError, match="action_name"):
            validate_ik_foot_params({"object_name": "X"})

    def test_invalid_terrain_type(self):
        with pytest.raises(ValueError, match="Invalid terrain_type"):
            validate_ik_foot_params({
                "object_name": "X", "action_name": "walk",
                "terrain_type": "water",
            })

    def test_negative_raycast_distance(self):
        with pytest.raises(ValueError, match="raycast_distance"):
            validate_ik_foot_params({
                "object_name": "X", "action_name": "walk",
                "raycast_distance": -1,
            })

    def test_empty_foot_bones(self):
        with pytest.raises(ValueError, match="foot_bones"):
            validate_ik_foot_params({
                "object_name": "X", "action_name": "walk",
                "foot_bones": [],
            })

    @pytest.mark.parametrize("tt", sorted(VALID_TERRAIN_TYPES))
    def test_all_terrain_types_accepted(self, tt):
        result = validate_ik_foot_params({
            "object_name": "X", "action_name": "walk",
            "terrain_type": tt,
        })
        assert result["terrain_type"] == tt


class TestComputeFootCorrection:
    def test_flat_ground_no_correction(self):
        result = compute_foot_correction(
            foot_z=0.0, ground_z=0.0,
            ground_normal=(0, 0, 1),
        )
        assert result["z_correction"] == pytest.approx(0.0)
        assert result["ankle_pitch"] == pytest.approx(0.0)
        assert result["ankle_roll"] == pytest.approx(0.0)
        assert result["is_grounded"] is True

    def test_foot_above_ground(self):
        result = compute_foot_correction(
            foot_z=0.3, ground_z=0.0,
            ground_normal=(0, 0, 1),
        )
        assert result["z_correction"] == pytest.approx(-0.3)
        assert result["is_grounded"] is True

    def test_foot_below_ground(self):
        result = compute_foot_correction(
            foot_z=-0.1, ground_z=0.0,
            ground_normal=(0, 0, 1),
        )
        assert result["z_correction"] == pytest.approx(0.1)

    def test_sloped_ground_pitch(self):
        # Surface tilted forward (normal has Y component)
        result = compute_foot_correction(
            foot_z=0.0, ground_z=0.0,
            ground_normal=(0, 0.5, 0.866),  # ~30 degree slope
        )
        assert abs(result["ankle_pitch"]) > 0.1

    def test_sloped_ground_roll(self):
        # Surface tilted sideways (normal has X component)
        result = compute_foot_correction(
            foot_z=0.0, ground_z=0.0,
            ground_normal=(0.5, 0, 0.866),
        )
        assert abs(result["ankle_roll"]) > 0.1

    def test_ground_offset(self):
        result = compute_foot_correction(
            foot_z=0.0, ground_z=0.0,
            ground_normal=(0, 0, 1),
            ground_offset=0.05,
        )
        assert result["z_correction"] == pytest.approx(0.05)

    def test_pitch_clamped(self):
        result = compute_foot_correction(
            foot_z=0.0, ground_z=0.0,
            ground_normal=(0, 10, 0.1),  # extreme slope
        )
        assert abs(result["ankle_pitch"]) <= 0.5

    def test_not_grounded_when_too_far(self):
        result = compute_foot_correction(
            foot_z=2.0, ground_z=0.0,
            ground_normal=(0, 0, 1),
        )
        assert result["is_grounded"] is False


class TestComputeHipCorrection:
    def test_no_correction_on_flat(self):
        corrections = [
            {"z_correction": 0.0},
            {"z_correction": 0.0},
        ]
        result = compute_hip_correction(corrections)
        assert result == pytest.approx(0.0)

    def test_lowers_hip_when_foot_below(self):
        corrections = [
            {"z_correction": -0.2},
            {"z_correction": 0.0},
        ]
        result = compute_hip_correction(corrections)
        assert result < 0  # hip goes down

    def test_no_raise_when_feet_above(self):
        corrections = [
            {"z_correction": 0.1},
            {"z_correction": 0.2},
        ]
        result = compute_hip_correction(corrections)
        assert result == pytest.approx(0.0)  # don't raise hip

    def test_empty_corrections(self):
        result = compute_hip_correction([])
        assert result == pytest.approx(0.0)

    def test_80_percent_transfer(self):
        corrections = [{"z_correction": -1.0}]
        result = compute_hip_correction(corrections)
        assert result == pytest.approx(-0.8)


class TestGenerateIKCorrectedKeyframes:
    def test_generates_keyframes(self):
        foot_data = [
            {
                "frame": 0,
                "feet": [
                    {"bone_name": "DEF-foot.L", "z_correction": -0.1,
                     "ankle_pitch": 0.05, "ankle_roll": 0.0},
                ],
            },
            {
                "frame": 1,
                "feet": [
                    {"bone_name": "DEF-foot.L", "z_correction": -0.05,
                     "ankle_pitch": 0.02, "ankle_roll": 0.0},
                ],
            },
        ]
        kfs = generate_ik_corrected_keyframes(foot_data)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_includes_hip_correction(self):
        foot_data = [
            {
                "frame": 0,
                "feet": [
                    {"bone_name": "DEF-foot.L", "z_correction": -0.3,
                     "ankle_pitch": 0.0, "ankle_roll": 0.0},
                ],
            },
        ]
        kfs = generate_ik_corrected_keyframes(foot_data)
        hip_kfs = [kf for kf in kfs if kf.bone_name == DEFAULT_HIP_BONE]
        assert len(hip_kfs) > 0

    def test_skips_tiny_corrections(self):
        foot_data = [
            {
                "frame": 0,
                "feet": [
                    {"bone_name": "DEF-foot.L", "z_correction": 0.0,
                     "ankle_pitch": 0.0005, "ankle_roll": 0.0},
                ],
            },
        ]
        kfs = generate_ik_corrected_keyframes(foot_data)
        pitch_kfs = [kf for kf in kfs if kf.channel == "rotation_euler" and kf.axis == 0
                     and kf.bone_name == "DEF-foot.L"]
        assert len(pitch_kfs) == 0  # too small, skipped


class TestSmoothCorrections:
    def test_smooths_jitter(self):
        # Create noisy data
        noisy = [
            Keyframe("DEF-foot.L", "location", 2, 0, 0.0),
            Keyframe("DEF-foot.L", "location", 2, 1, 0.5),  # spike
            Keyframe("DEF-foot.L", "location", 2, 2, 0.0),
            Keyframe("DEF-foot.L", "location", 2, 3, 0.0),
        ]
        smoothed = smooth_corrections(noisy, passes=1)
        # The spike at frame 1 should be reduced
        frame1_val = [kf.value for kf in smoothed if kf.frame == 1][0]
        assert frame1_val < 0.5

    def test_preserves_endpoints(self):
        data = [
            Keyframe("DEF-foot.L", "location", 2, 0, 1.0),
            Keyframe("DEF-foot.L", "location", 2, 1, 0.5),
            Keyframe("DEF-foot.L", "location", 2, 2, 1.0),
        ]
        smoothed = smooth_corrections(data, passes=1)
        frame0_val = [kf.value for kf in smoothed if kf.frame == 0][0]
        frame2_val = [kf.value for kf in smoothed if kf.frame == 2][0]
        assert frame0_val == pytest.approx(1.0)
        assert frame2_val == pytest.approx(1.0)

    def test_empty_returns_empty(self):
        assert smooth_corrections([], passes=1) == []

    def test_too_short_returns_copy(self):
        data = [Keyframe("A", "location", 0, 0, 1.0)]
        result = smooth_corrections(data, passes=1)
        assert len(result) == 1

    def test_zero_passes_returns_copy(self):
        data = [
            Keyframe("A", "location", 0, 0, 1.0),
            Keyframe("A", "location", 0, 1, 2.0),
            Keyframe("A", "location", 0, 2, 3.0),
        ]
        result = smooth_corrections(data, passes=0)
        assert len(result) == 3
