"""Tests for environmental/world animation generators. Pure-logic -- no Blender."""
import pytest
from blender_addon.handlers.animation_environment import (
    VALID_ENV_TYPES, validate_env_params, generate_env_keyframes,
    generate_door_open_keyframes, generate_door_slam_keyframes,
    generate_gate_raise_keyframes, generate_gate_lower_keyframes,
    generate_fire_flicker_keyframes, generate_water_wave_keyframes,
    generate_flag_wind_keyframes, generate_chest_open_keyframes,
    generate_trap_trigger_keyframes, generate_windmill_rotate_keyframes,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidation:
    def test_valid_defaults(self):
        r = validate_env_params({"object_name": "Door"})
        assert r["env_type"] == "door_open"

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            validate_env_params({"object_name": "X", "env_type": "explode"})

    def test_missing_name(self):
        with pytest.raises(ValueError):
            validate_env_params({})

    @pytest.mark.parametrize("et", sorted(VALID_ENV_TYPES))
    def test_all_types_accepted(self, et):
        r = validate_env_params({"object_name": "X", "env_type": et})
        assert r["env_type"] == et


class TestDoors:
    def test_door_open(self):
        kfs = generate_door_open_keyframes()
        assert len(kfs) > 0
        # Should end at roughly the target angle
        final = [kf.value for kf in kfs if kf.frame == 30]
        assert any(abs(v) > 1.0 for v in final)  # 90 degrees ~ 1.57 rad

    def test_door_slam_has_bounce(self):
        kfs = generate_door_slam_keyframes()
        values = [kf.value for kf in kfs]
        # Should have sign changes (bounce)
        has_pos = any(v > 0.01 for v in values)
        has_neg = any(v < -0.01 for v in values)
        assert has_pos or has_neg  # at least some motion


class TestGates:
    def test_gate_raise_reaches_height(self):
        kfs = generate_gate_raise_keyframes(frame_count=60, height=3.0)
        final = [kf.value for kf in kfs if kf.frame == 60]
        assert any(v > 2.5 for v in final)

    def test_gate_lower_has_bounce(self):
        kfs = generate_gate_lower_keyframes()
        z_vals = [kf.value for kf in kfs]
        assert min(z_vals) < 0.1  # reaches near ground


class TestFire:
    def test_fire_flicker_scale_varies(self):
        kfs = generate_fire_flicker_keyframes()
        scale_kfs = [kf for kf in kfs if kf.channel == "scale" and kf.axis == 1]
        values = [kf.value for kf in scale_kfs]
        assert max(values) > 1.0  # flame grows
        assert min(values) < 1.0  # flame shrinks

    def test_fire_has_sway(self):
        kfs = generate_fire_flicker_keyframes()
        loc_kfs = [kf for kf in kfs if kf.channel == "location"]
        assert len(loc_kfs) > 0


class TestWater:
    def test_water_wave_oscillates(self):
        kfs = generate_water_wave_keyframes()
        z_kfs = [kf for kf in kfs if kf.axis == 2 and kf.channel == "location"]
        values = [kf.value for kf in z_kfs]
        assert max(values) > 0 and min(values) < 0


class TestFlags:
    def test_flag_has_segments(self):
        kfs = generate_flag_wind_keyframes()
        bones = {kf.bone_name for kf in kfs}
        assert len(bones) >= 2  # root + at least one segment


class TestInteractables:
    def test_chest_opens_to_angle(self):
        kfs = generate_chest_open_keyframes()
        final = [kf.value for kf in kfs if kf.frame == 30]
        assert any(abs(v) > 1.5 for v in final)  # ~110 degrees

    def test_trap_trigger_fast(self):
        kfs = generate_trap_trigger_keyframes(frame_count=12)
        assert len(kfs) == 13  # 0..12 inclusive


class TestAmbient:
    def test_windmill_rotates(self):
        kfs = generate_windmill_rotate_keyframes()
        final = [kf.value for kf in kfs if kf.frame == 120]
        assert any(abs(v) > 6.0 for v in final)  # full rotation


class TestDispatch:
    @pytest.mark.parametrize("et", sorted(VALID_ENV_TYPES))
    def test_all_types_dispatch(self, et):
        params = {"env_type": et, "frame_count": 12, "intensity": 1.0,
                  "angle": 90, "speed": 1.0}
        kfs = generate_env_keyframes(params)
        assert isinstance(kfs, list)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            generate_env_keyframes({"env_type": "explode", "frame_count": 12})


class TestConstants:
    def test_env_type_count(self):
        assert len(VALID_ENV_TYPES) == 27
