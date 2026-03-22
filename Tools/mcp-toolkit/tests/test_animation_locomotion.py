"""Tests for extended locomotion animations. Pure-logic."""
import pytest
from blender_addon.handlers.animation_locomotion import (
    VALID_LOCOMOTION_TYPES, validate_locomotion_params, generate_locomotion_keyframes,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidation:
    @pytest.mark.parametrize("lt", sorted(VALID_LOCOMOTION_TYPES))
    def test_all_types(self, lt):
        r = validate_locomotion_params({"object_name": "X", "loco_type": lt})
        assert r["loco_type"] == lt

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_locomotion_params({"object_name": "X", "loco_type": "teleport"})


class TestDispatch:
    @pytest.mark.parametrize("lt", sorted(VALID_LOCOMOTION_TYPES))
    def test_all_dispatch(self, lt):
        params = {"loco_type": lt, "frame_count": 12, "intensity": 1.0}
        kfs = generate_locomotion_keyframes(params)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    @pytest.mark.parametrize("lt", sorted(VALID_LOCOMOTION_TYPES))
    def test_fc4_no_crash(self, lt):
        kfs = generate_locomotion_keyframes({"loco_type": lt, "frame_count": 4, "intensity": 1.0})
        assert len(kfs) > 0


class TestConstants:
    def test_count(self):
        assert len(VALID_LOCOMOTION_TYPES) == 33
