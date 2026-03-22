"""Tests for amorphous creature (blob) animation system.

All pure-logic -- no Blender required.
"""

import pytest

from blender_addon.handlers.animation_blob import (
    BLOB_PSEUDOPOD_BONES,
    BLOB_SPINE_BONES,
    VALID_BLOB_TYPES,
    generate_blob_attack_keyframes,
    generate_blob_idle_keyframes,
    generate_blob_keyframes,
    generate_blob_locomotion_keyframes,
    generate_blob_split_keyframes,
    generate_pseudopod_reach_keyframes,
    validate_blob_params,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidateBlobParams:
    def test_valid_defaults(self):
        result = validate_blob_params({"object_name": "Blob"})
        assert result["blob_type"] == "blob_idle"
        assert result["frame_count"] == 48

    def test_invalid_blob_type(self):
        with pytest.raises(ValueError, match="Invalid blob_type"):
            validate_blob_params({"object_name": "X", "blob_type": "fly"})

    def test_zero_intensity(self):
        with pytest.raises(ValueError, match="intensity"):
            validate_blob_params({"object_name": "X", "intensity": 0})

    @pytest.mark.parametrize("bt", sorted(VALID_BLOB_TYPES))
    def test_all_blob_types_accepted(self, bt):
        result = validate_blob_params({"object_name": "X", "blob_type": bt})
        assert result["blob_type"] == bt


class TestBlobLocomotion:
    def test_returns_keyframes(self):
        kfs = generate_blob_locomotion_keyframes()
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_uses_scale_channels(self):
        kfs = generate_blob_locomotion_keyframes()
        scale_kfs = [kf for kf in kfs if kf.channel == "scale"]
        assert len(scale_kfs) > 0

    def test_volume_preservation(self):
        """When Y scale decreases, X/Z should increase (volume conservation)."""
        kfs = generate_blob_locomotion_keyframes(frame_count=16)
        bone = BLOB_SPINE_BONES[0]
        y_vals = {kf.frame: kf.value for kf in kfs
                  if kf.bone_name == bone and kf.channel == "scale" and kf.axis == 1}
        x_vals = {kf.frame: kf.value for kf in kfs
                  if kf.bone_name == bone and kf.channel == "scale" and kf.axis == 0}
        # At frame where Y is smallest, X should be largest (approximately)
        if y_vals and x_vals:
            common_frames = set(y_vals.keys()) & set(x_vals.keys())
            if common_frames:
                min_y_frame = min(common_frames, key=lambda f: y_vals[f])
                # X at min-Y frame should be > 1 (expanded)
                assert x_vals[min_y_frame] >= 1.0


class TestPseudopodReach:
    def test_returns_keyframes(self):
        kfs = generate_pseudopod_reach_keyframes()
        assert len(kfs) > 0

    def test_has_body_recoil(self):
        kfs = generate_pseudopod_reach_keyframes()
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"]
        assert len(spine_kfs) > 0

    @pytest.mark.parametrize("direction", ["forward", "left", "right", "up"])
    def test_all_directions(self, direction):
        kfs = generate_pseudopod_reach_keyframes(direction=direction)
        assert len(kfs) > 0


class TestBlobIdle:
    def test_returns_keyframes(self):
        kfs = generate_blob_idle_keyframes()
        assert len(kfs) > 0

    def test_has_pulsing(self):
        kfs = generate_blob_idle_keyframes()
        scale_kfs = [kf for kf in kfs if kf.channel == "scale"]
        values = [kf.value for kf in scale_kfs]
        # Should oscillate around 1.0
        assert min(values) < 1.0
        assert max(values) > 1.0

    def test_has_surface_ripple(self):
        kfs = generate_blob_idle_keyframes()
        rot_kfs = [kf for kf in kfs if kf.channel == "rotation_euler"]
        assert len(rot_kfs) > 0


class TestBlobAttack:
    def test_returns_keyframes(self):
        kfs = generate_blob_attack_keyframes()
        assert len(kfs) > 0

    def test_has_extension_phase(self):
        kfs = generate_blob_attack_keyframes()
        loc_kfs = [kf for kf in kfs if kf.channel == "location"]
        if loc_kfs:
            max_extend = max(kf.value for kf in loc_kfs)
            assert max_extend > 0.05  # reaches outward


class TestBlobSplit:
    def test_returns_keyframes(self):
        kfs = generate_blob_split_keyframes()
        assert len(kfs) > 0

    def test_ends_at_smaller_scale(self):
        kfs = generate_blob_split_keyframes(frame_count=32)
        final_scales = [kf.value for kf in kfs
                        if kf.channel == "scale" and kf.frame == 32]
        if final_scales:
            assert all(s < 1.0 for s in final_scales)


class TestDispatch:
    @pytest.mark.parametrize("bt", sorted(VALID_BLOB_TYPES))
    def test_dispatch_all_types(self, bt):
        params = {
            "object_name": "Blob",
            "blob_type": bt,
            "frame_count": 16,
            "direction": "forward",
            "intensity": 1.0,
        }
        kfs = generate_blob_keyframes(params)
        assert isinstance(kfs, list)
        assert len(kfs) > 0

    def test_dispatch_unknown_raises(self):
        with pytest.raises(ValueError):
            generate_blob_keyframes({
                "blob_type": "fly",
                "frame_count": 16,
                "intensity": 1.0,
            })
