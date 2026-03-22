"""Tests for spell-cast animation generators.

All pure-logic -- no Blender required.
"""

import math
import pytest

from blender_addon.handlers.animation_spellcast import (
    SPELL_CAST_TIMING,
    VALID_CAST_HANDS,
    VALID_CAST_TYPES,
    generate_channel_keyframes,
    generate_release_keyframes,
    generate_sustain_keyframes,
    get_spellcast_timing,
    validate_spellcast_params,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidateSpellcastParams:
    def test_valid_defaults(self):
        result = validate_spellcast_params({"object_name": "Mage"})
        assert result["cast_type"] == "channel"
        assert result["cast_hand"] == "both"
        assert result["frame_count"] == 48

    def test_valid_all_params(self):
        result = validate_spellcast_params({
            "object_name": "Mage",
            "cast_type": "release",
            "cast_hand": "left",
            "frame_count": 24,
            "intensity": 1.5,
        })
        assert result["cast_type"] == "release"
        assert result["cast_hand"] == "left"

    def test_missing_object_name(self):
        with pytest.raises(ValueError, match="object_name"):
            validate_spellcast_params({})

    def test_invalid_cast_type(self):
        with pytest.raises(ValueError, match="Invalid cast_type"):
            validate_spellcast_params({"object_name": "X", "cast_type": "fireball"})

    def test_invalid_cast_hand(self):
        with pytest.raises(ValueError, match="Invalid cast_hand"):
            validate_spellcast_params({"object_name": "X", "cast_hand": "foot"})

    def test_frame_count_too_small(self):
        with pytest.raises(ValueError, match="frame_count"):
            validate_spellcast_params({"object_name": "X", "frame_count": 2})

    def test_intensity_zero(self):
        with pytest.raises(ValueError, match="intensity"):
            validate_spellcast_params({"object_name": "X", "intensity": 0})

    @pytest.mark.parametrize("ct", sorted(VALID_CAST_TYPES))
    def test_all_cast_types_accepted(self, ct):
        result = validate_spellcast_params({"object_name": "X", "cast_type": ct})
        assert result["cast_type"] == ct

    @pytest.mark.parametrize("ch", sorted(VALID_CAST_HANDS))
    def test_all_cast_hands_accepted(self, ch):
        result = validate_spellcast_params({"object_name": "X", "cast_hand": ch})
        assert result["cast_hand"] == ch


class TestChannelKeyframes:
    def test_returns_keyframes(self):
        kfs = generate_channel_keyframes()
        assert isinstance(kfs, list)
        assert all(isinstance(kf, Keyframe) for kf in kfs)
        assert len(kfs) > 0

    def test_has_upper_arm_bones(self):
        kfs = generate_channel_keyframes(cast_hand="both")
        bones = {kf.bone_name for kf in kfs}
        assert "DEF-upper_arm.L" in bones
        assert "DEF-upper_arm.R" in bones

    def test_left_hand_only(self):
        kfs = generate_channel_keyframes(cast_hand="left")
        arm_bones = {kf.bone_name for kf in kfs if "upper_arm" in kf.bone_name}
        assert "DEF-upper_arm.L" in arm_bones
        assert "DEF-upper_arm.R" not in arm_bones

    def test_right_hand_only(self):
        kfs = generate_channel_keyframes(cast_hand="right")
        arm_bones = {kf.bone_name for kf in kfs if "upper_arm" in kf.bone_name}
        assert "DEF-upper_arm.R" in arm_bones
        assert "DEF-upper_arm.L" not in arm_bones

    def test_has_spine_motion(self):
        kfs = generate_channel_keyframes()
        spine_kfs = [kf for kf in kfs if "spine" in kf.bone_name]
        assert len(spine_kfs) > 0

    def test_intensity_scales_values(self):
        kfs_1 = generate_channel_keyframes(intensity=1.0)
        kfs_2 = generate_channel_keyframes(intensity=2.0)
        # Higher intensity should produce larger absolute values at same frame
        val_1 = max(abs(kf.value) for kf in kfs_1 if kf.bone_name == "DEF-upper_arm.L")
        val_2 = max(abs(kf.value) for kf in kfs_2 if kf.bone_name == "DEF-upper_arm.L")
        assert val_2 > val_1


class TestReleaseKeyframes:
    def test_returns_keyframes(self):
        kfs = generate_release_keyframes()
        assert len(kfs) > 0

    def test_has_thrust_motion(self):
        kfs = generate_release_keyframes(cast_hand="right")
        arm_kfs = [kf for kf in kfs if kf.bone_name == "DEF-upper_arm.R"]
        values = [kf.value for kf in arm_kfs]
        # Should have both negative (pull back) and positive (thrust) values
        assert min(values) < 0
        assert max(values) > 0


class TestSustainKeyframes:
    def test_returns_keyframes(self):
        kfs = generate_sustain_keyframes()
        assert len(kfs) > 0

    def test_has_rhythmic_pulse(self):
        kfs = generate_sustain_keyframes(frame_count=48)
        hand_kfs = [kf for kf in kfs if kf.bone_name == "DEF-hand.L"]
        if hand_kfs:
            values = [kf.value for kf in hand_kfs]
            # Should vary (not all same value)
            assert max(values) != min(values)


class TestSpellCastTiming:
    def test_all_cast_types_have_timing(self):
        for ct in VALID_CAST_TYPES:
            assert ct in SPELL_CAST_TIMING

    def test_timing_has_required_fields(self):
        required = {"anticipation_frames", "active_frames", "recovery_frames",
                     "cancel_window_start", "cancel_window_end", "vfx_frame"}
        for ct, timing in SPELL_CAST_TIMING.items():
            for field in required:
                assert field in timing, f"{ct} missing {field}"

    def test_channel_active_is_looping(self):
        assert SPELL_CAST_TIMING["channel"]["active_frames"] == -1

    def test_release_active_is_finite(self):
        assert SPELL_CAST_TIMING["release"]["active_frames"] > 0

    def test_sustain_active_is_looping(self):
        assert SPELL_CAST_TIMING["sustain"]["active_frames"] == -1

    def test_get_timing_valid(self):
        timing = get_spellcast_timing("release")
        assert timing["anticipation_frames"] == 8
        assert timing["active_frames"] == 4

    def test_get_timing_invalid_raises(self):
        with pytest.raises(ValueError):
            get_spellcast_timing("fireball")

    def test_get_timing_returns_copy(self):
        t1 = get_spellcast_timing("channel")
        t2 = get_spellcast_timing("channel")
        t1["anticipation_frames"] = 999
        assert t2["anticipation_frames"] != 999


class TestConstants:
    def test_valid_cast_types(self):
        assert VALID_CAST_TYPES == {"channel", "release", "sustain"}

    def test_valid_cast_hands(self):
        assert VALID_CAST_HANDS == {"left", "right", "both"}
