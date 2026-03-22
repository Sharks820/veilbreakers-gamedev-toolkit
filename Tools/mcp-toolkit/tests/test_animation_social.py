"""Tests for social/emote animations. Pure-logic."""
import pytest
from blender_addon.handlers.animation_social import (
    VALID_SOCIAL_TYPES, validate_social_params, generate_social_keyframes,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidation:
    @pytest.mark.parametrize("st", sorted(VALID_SOCIAL_TYPES))
    def test_all_types(self, st):
        r = validate_social_params({"object_name": "X", "social_type": st})
        assert r["social_type"] == st

class TestDispatch:
    @pytest.mark.parametrize("st", sorted(VALID_SOCIAL_TYPES))
    def test_all_dispatch(self, st):
        kfs = generate_social_keyframes({"social_type": st, "frame_count": 12, "intensity": 1.0})
        assert len(kfs) > 0 and all(isinstance(kf, Keyframe) for kf in kfs)

    @pytest.mark.parametrize("st", sorted(VALID_SOCIAL_TYPES))
    def test_fc4(self, st):
        kfs = generate_social_keyframes({"social_type": st, "frame_count": 4, "intensity": 1.0})
        assert len(kfs) > 0

class TestConstants:
    def test_count(self):
        assert len(VALID_SOCIAL_TYPES) == 7
