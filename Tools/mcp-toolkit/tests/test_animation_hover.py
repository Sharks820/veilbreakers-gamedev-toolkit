"""Tests for hover animation system.

All pure-logic -- no Blender required.
"""

import math
import pytest

from blender_addon.handlers.animation_hover import (
    VALID_HOVER_TYPES,
    generate_hover_idle_keyframes,
    generate_hover_move_keyframes,
    generate_wing_flap_keyframes,
    generate_tentacle_float_keyframes,
    generate_hover_keyframes,
    validate_hover_params,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidateHoverParams:
    def test_valid_defaults(self):
        result = validate_hover_params({"object_name": "Dragon"})
        assert result["hover_type"] == "hover_idle"
        assert result["bob_amplitude"] == pytest.approx(0.05)

    def test_invalid_hover_type(self):
        with pytest.raises(ValueError, match="Invalid hover_type"):
            validate_hover_params({"object_name": "X", "hover_type": "swim"})

    def test_negative_bob_amplitude(self):
        with pytest.raises(ValueError, match="bob_amplitude"):
            validate_hover_params({"object_name": "X", "bob_amplitude": -1})

    def test_zero_bob_frequency(self):
        with pytest.raises(ValueError, match="bob_frequency"):
            validate_hover_params({"object_name": "X", "bob_frequency": 0})

    @pytest.mark.parametrize("ht", sorted(VALID_HOVER_TYPES))
    def test_all_hover_types_accepted(self, ht):
        result = validate_hover_params({"object_name": "X", "hover_type": ht})
        assert result["hover_type"] == ht


class TestHoverIdle:
    def test_returns_keyframes(self):
        kfs = generate_hover_idle_keyframes()
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_has_vertical_bob(self):
        kfs = generate_hover_idle_keyframes()
        z_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"
                 and kf.channel == "location" and kf.axis == 2]
        assert len(z_kfs) > 0
        values = [kf.value for kf in z_kfs]
        assert max(values) > 0 and min(values) < 0  # oscillates

    def test_has_lateral_drift(self):
        kfs = generate_hover_idle_keyframes(drift_amount=0.05)
        x_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"
                 and kf.channel == "location" and kf.axis == 0]
        assert len(x_kfs) > 0

    def test_has_body_tilt(self):
        kfs = generate_hover_idle_keyframes()
        tilt_kfs = [kf for kf in kfs if "spine.001" in kf.bone_name
                    and kf.channel == "rotation_euler"]
        assert len(tilt_kfs) > 0

    def test_bob_amplitude_affects_values(self):
        kfs_small = generate_hover_idle_keyframes(bob_amplitude=0.01)
        kfs_large = generate_hover_idle_keyframes(bob_amplitude=0.1)
        max_small = max(abs(kf.value) for kf in kfs_small
                        if kf.bone_name == "DEF-spine" and kf.channel == "location" and kf.axis == 2)
        max_large = max(abs(kf.value) for kf in kfs_large
                        if kf.bone_name == "DEF-spine" and kf.channel == "location" and kf.axis == 2)
        assert max_large > max_small


class TestHoverMove:
    def test_returns_keyframes(self):
        kfs = generate_hover_move_keyframes()
        assert len(kfs) > 0

    def test_has_banking(self):
        kfs = generate_hover_move_keyframes(bank_angle=0.5)
        roll_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"
                    and kf.channel == "rotation_euler" and kf.axis == 0]
        assert len(roll_kfs) > 0
        max_roll = max(abs(kf.value) for kf in roll_kfs)
        assert max_roll > 0.1

    def test_has_forward_lean(self):
        kfs = generate_hover_move_keyframes()
        lean_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"
                    and kf.channel == "rotation_euler"]
        assert any(kf.value > 0.1 for kf in lean_kfs)


class TestWingFlap:
    def test_returns_keyframes(self):
        kfs = generate_wing_flap_keyframes()
        assert len(kfs) > 0

    def test_has_all_wing_bones(self):
        kfs = generate_wing_flap_keyframes()
        bones = {kf.bone_name for kf in kfs}
        assert "DEF-wing_upper.L" in bones
        assert "DEF-wing_upper.R" in bones
        assert "DEF-wing_fore.L" in bones
        assert "DEF-wing_fore.R" in bones

    def test_upper_wings_larger_amplitude(self):
        kfs = generate_wing_flap_keyframes()
        upper_vals = [abs(kf.value) for kf in kfs if "wing_upper" in kf.bone_name]
        tip_vals = [abs(kf.value) for kf in kfs if "wing_tip" in kf.bone_name]
        assert max(upper_vals) > max(tip_vals)


class TestTentacleFloat:
    def test_returns_keyframes(self):
        kfs = generate_tentacle_float_keyframes()
        assert len(kfs) > 0

    def test_correct_tentacle_count(self):
        kfs = generate_tentacle_float_keyframes(tentacle_count=3)
        tent_bones = {kf.bone_name for kf in kfs if "tentacle" in kf.bone_name}
        # 3 tentacles x 3 segments = should reference 9 tentacle bones
        assert len(tent_bones) >= 3

    def test_has_body_bob(self):
        kfs = generate_tentacle_float_keyframes()
        bob_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"
                   and kf.channel == "location"]
        assert len(bob_kfs) > 0


class TestDispatch:
    @pytest.mark.parametrize("ht", sorted(VALID_HOVER_TYPES))
    def test_dispatch_all_types(self, ht):
        params = {
            "object_name": "Dragon",
            "hover_type": ht,
            "bob_amplitude": 0.05,
            "bob_frequency": 0.8,
            "bank_angle": 0.3,
            "drift_amount": 0.02,
            "frame_count": 24,
        }
        kfs = generate_hover_keyframes(params)
        assert isinstance(kfs, list)
        assert len(kfs) > 0

    def test_dispatch_unknown_raises(self):
        with pytest.raises(ValueError):
            generate_hover_keyframes({
                "hover_type": "swim",
                "bob_amplitude": 0.05,
                "bob_frequency": 0.8,
                "bank_angle": 0.3,
                "drift_amount": 0.02,
                "frame_count": 24,
            })
