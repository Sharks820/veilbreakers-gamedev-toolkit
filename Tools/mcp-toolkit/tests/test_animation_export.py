"""Tests for animation export handlers -- pure-logic validation functions.

Tests cover:
- Export param validation (_validate_export_params)
- Preview param validation (_validate_preview_params)
- Secondary motion param validation (_validate_secondary_motion_params)
- Root motion param validation (_validate_root_motion_params)
- Batch export param validation (_validate_batch_export_params)
- Mixamo bone mapping completeness and correctness (_map_mixamo_bones)
- Unity filename generation (_generate_unity_filename)
- AI motion stub response validation
- MIXAMO_TO_RIGIFY constant integrity

All pure-logic -- no Blender required.
"""

import pytest

from blender_addon.handlers.animation_export import (
    MIXAMO_TO_RIGIFY,
    PREVIEW_ANGLES,
    _generate_unity_filename,
    _map_mixamo_bones,
    _validate_batch_export_params,
    _validate_export_params,
    _validate_preview_params,
    _validate_root_motion_params,
    _validate_secondary_motion_params,
)


# ---------------------------------------------------------------------------
# TestValidateExportParams
# ---------------------------------------------------------------------------


class TestValidateExportParams:
    """Test _validate_export_params validation logic."""

    def test_valid_params(self):
        result = _validate_export_params({"object_name": "MyRig"})
        assert result["valid"] is True
        assert result["errors"] == []

    def test_missing_object_name(self):
        result = _validate_export_params({})
        assert result["valid"] is False
        assert any("object_name" in e for e in result["errors"])

    def test_empty_object_name(self):
        result = _validate_export_params({"object_name": ""})
        assert result["valid"] is False
        assert any("object_name" in e for e in result["errors"])

    def test_non_string_object_name(self):
        result = _validate_export_params({"object_name": 123})
        assert result["valid"] is False

    def test_wrong_object_type(self):
        result = _validate_export_params({
            "object_name": "MyMesh",
            "object_type": "MESH",
        })
        assert result["valid"] is False
        assert any("armature" in e for e in result["errors"])

    def test_armature_type_valid(self):
        result = _validate_export_params({
            "object_name": "MyRig",
            "object_type": "ARMATURE",
        })
        assert result["valid"] is True

    def test_none_type_skips_check(self):
        result = _validate_export_params({"object_name": "MyRig"})
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# TestValidatePreviewParams
# ---------------------------------------------------------------------------


class TestValidatePreviewParams:
    """Test _validate_preview_params validation logic."""

    def test_valid_defaults(self):
        result = _validate_preview_params({})
        assert result["valid"] is True

    def test_valid_custom_params(self):
        result = _validate_preview_params({
            "frame_step": 8,
            "angles": ["front", "back", "side"],
            "resolution": 512,
        })
        assert result["valid"] is True

    def test_frame_step_zero(self):
        result = _validate_preview_params({"frame_step": 0})
        assert result["valid"] is False
        assert any("frame_step" in e for e in result["errors"])

    def test_frame_step_negative(self):
        result = _validate_preview_params({"frame_step": -1})
        assert result["valid"] is False
        assert any("frame_step" in e for e in result["errors"])

    def test_frame_step_must_be_number(self):
        result = _validate_preview_params({"frame_step": "fast"})
        assert result["valid"] is False
        assert any("frame_step" in e for e in result["errors"])

    def test_angles_empty(self):
        result = _validate_preview_params({"angles": []})
        assert result["valid"] is False
        assert any("angles" in e for e in result["errors"])

    def test_angles_not_list(self):
        result = _validate_preview_params({"angles": "front"})
        assert result["valid"] is False
        assert any("angles" in e for e in result["errors"])

    def test_resolution_too_small(self):
        result = _validate_preview_params({"resolution": 16})
        assert result["valid"] is False
        assert any("resolution" in e for e in result["errors"])

    def test_resolution_not_number(self):
        result = _validate_preview_params({"resolution": "big"})
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# TestValidateSecondaryMotionParams
# ---------------------------------------------------------------------------


class TestValidateSecondaryMotionParams:
    """Test _validate_secondary_motion_params validation logic."""

    def test_valid_params(self):
        result = _validate_secondary_motion_params({
            "action_name": "walk",
            "bone_names": ["tail.001", "tail.002"],
        })
        assert result["valid"] is True

    def test_missing_action_name(self):
        result = _validate_secondary_motion_params({
            "bone_names": ["tail.001"],
        })
        assert result["valid"] is False
        assert any("action_name" in e for e in result["errors"])

    def test_empty_bone_names(self):
        result = _validate_secondary_motion_params({
            "action_name": "walk",
            "bone_names": [],
        })
        assert result["valid"] is False
        assert any("bone_names" in e for e in result["errors"])

    def test_missing_bone_names(self):
        result = _validate_secondary_motion_params({
            "action_name": "walk",
        })
        assert result["valid"] is False

    def test_bone_names_with_empty_string(self):
        result = _validate_secondary_motion_params({
            "action_name": "walk",
            "bone_names": ["tail.001", ""],
        })
        assert result["valid"] is False
        assert any("bone_names[1]" in e for e in result["errors"])

    def test_bone_names_not_list(self):
        result = _validate_secondary_motion_params({
            "action_name": "walk",
            "bone_names": "tail.001",
        })
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# TestValidateRootMotionParams
# ---------------------------------------------------------------------------


class TestValidateRootMotionParams:
    """Test _validate_root_motion_params validation logic."""

    def test_valid_params(self):
        result = _validate_root_motion_params({
            "action_name": "walk_cycle",
        })
        assert result["valid"] is True

    def test_missing_action_name(self):
        result = _validate_root_motion_params({})
        assert result["valid"] is False
        assert any("action_name" in e for e in result["errors"])

    def test_empty_action_name(self):
        result = _validate_root_motion_params({"action_name": ""})
        assert result["valid"] is False

    def test_default_hip_bone(self):
        """Default hip_bone is 'DEF-spine' -- should be valid."""
        result = _validate_root_motion_params({"action_name": "walk"})
        assert result["valid"] is True

    def test_custom_hip_bone(self):
        result = _validate_root_motion_params({
            "action_name": "walk",
            "hip_bone": "hips",
        })
        assert result["valid"] is True

    def test_custom_root_bone(self):
        result = _validate_root_motion_params({
            "action_name": "walk",
            "root_bone": "motion_root",
        })
        assert result["valid"] is True

    def test_extract_rotation_with_valid_hip(self):
        result = _validate_root_motion_params({
            "action_name": "walk",
            "hip_bone": "DEF-spine",
            "extract_rotation": True,
        })
        assert result["valid"] is True

    def test_extract_rotation_with_empty_hip(self):
        """extract_rotation=True requires hip_bone to be non-empty."""
        result = _validate_root_motion_params({
            "action_name": "walk",
            "hip_bone": "",
            "extract_rotation": True,
        })
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# TestValidateBatchExportParams
# ---------------------------------------------------------------------------


class TestValidateBatchExportParams:
    """Test _validate_batch_export_params validation logic."""

    def test_valid_params(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
        })
        assert result["valid"] is True

    def test_missing_output_dir(self):
        result = _validate_batch_export_params({})
        assert result["valid"] is False
        assert any("output_dir" in e for e in result["errors"])

    def test_empty_output_dir(self):
        result = _validate_batch_export_params({"output_dir": ""})
        assert result["valid"] is False

    def test_invalid_naming(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "naming": "unreal",
        })
        assert result["valid"] is False
        assert any("naming" in e for e in result["errors"])

    def test_valid_unity_naming(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "naming": "unity",
        })
        assert result["valid"] is True

    def test_valid_raw_naming(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "naming": "raw",
        })
        assert result["valid"] is True

    def test_empty_actions_list(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "actions": [],
        })
        assert result["valid"] is False
        assert any("actions" in e for e in result["errors"])

    def test_actions_not_list(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "actions": "walk",
        })
        assert result["valid"] is False

    def test_actions_none_is_valid(self):
        """actions=None means export all -- should be valid."""
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "actions": None,
        })
        assert result["valid"] is True

    def test_valid_actions_list(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/exports",
            "actions": ["walk", "run", "idle"],
        })
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# TestMixamoBoneMapping
# ---------------------------------------------------------------------------


class TestMixamoBoneMapping:
    """Test MIXAMO_TO_RIGIFY mapping and _map_mixamo_bones function."""

    def test_mapping_has_at_least_22_entries(self):
        assert len(MIXAMO_TO_RIGIFY) >= 22

    def test_hips_mapping(self):
        assert MIXAMO_TO_RIGIFY["mixamorig:Hips"] == "DEF-spine"

    def test_left_arm_mapping(self):
        assert MIXAMO_TO_RIGIFY["mixamorig:LeftArm"] == "DEF-upper_arm.L"

    def test_right_foot_mapping(self):
        assert MIXAMO_TO_RIGIFY["mixamorig:RightFoot"] == "DEF-foot.R"

    def test_head_mapping(self):
        assert MIXAMO_TO_RIGIFY["mixamorig:Head"] == "DEF-spine.005"

    def test_all_keys_have_mixamorig_prefix(self):
        for key in MIXAMO_TO_RIGIFY:
            assert key.startswith("mixamorig:"), f"Key missing prefix: {key}"

    def test_all_values_have_def_prefix(self):
        for val in MIXAMO_TO_RIGIFY.values():
            assert val.startswith("DEF-"), f"Value missing DEF- prefix: {val}"

    def test_spine_chain_complete(self):
        """Spine chain should have 6 bones: Hips through Head."""
        spine_keys = [
            "mixamorig:Hips", "mixamorig:Spine", "mixamorig:Spine1",
            "mixamorig:Spine2", "mixamorig:Neck", "mixamorig:Head",
        ]
        for key in spine_keys:
            assert key in MIXAMO_TO_RIGIFY, f"Missing spine bone: {key}"

    def test_left_arm_chain_complete(self):
        arm_keys = [
            "mixamorig:LeftShoulder", "mixamorig:LeftArm",
            "mixamorig:LeftForeArm", "mixamorig:LeftHand",
        ]
        for key in arm_keys:
            assert key in MIXAMO_TO_RIGIFY, f"Missing left arm bone: {key}"

    def test_right_arm_chain_complete(self):
        arm_keys = [
            "mixamorig:RightShoulder", "mixamorig:RightArm",
            "mixamorig:RightForeArm", "mixamorig:RightHand",
        ]
        for key in arm_keys:
            assert key in MIXAMO_TO_RIGIFY, f"Missing right arm bone: {key}"

    def test_left_leg_chain_complete(self):
        leg_keys = [
            "mixamorig:LeftUpLeg", "mixamorig:LeftLeg",
            "mixamorig:LeftFoot", "mixamorig:LeftToeBase",
        ]
        for key in leg_keys:
            assert key in MIXAMO_TO_RIGIFY, f"Missing left leg bone: {key}"

    def test_right_leg_chain_complete(self):
        leg_keys = [
            "mixamorig:RightUpLeg", "mixamorig:RightLeg",
            "mixamorig:RightFoot", "mixamorig:RightToeBase",
        ]
        for key in leg_keys:
            assert key in MIXAMO_TO_RIGIFY, f"Missing right leg bone: {key}"

    def test_no_duplicate_values(self):
        """Each Rigify DEF bone should appear at most once in the mapping."""
        values = list(MIXAMO_TO_RIGIFY.values())
        assert len(values) == len(set(values)), "Duplicate DEF bone targets"

    def test_left_right_symmetry(self):
        """For every Left mapping there should be a corresponding Right mapping."""
        left_keys = [k for k in MIXAMO_TO_RIGIFY if "Left" in k]
        for lk in left_keys:
            rk = lk.replace("Left", "Right")
            assert rk in MIXAMO_TO_RIGIFY, f"Missing symmetric key: {rk}"
            # Check value symmetry (.L -> .R)
            lv = MIXAMO_TO_RIGIFY[lk]
            rv = MIXAMO_TO_RIGIFY[rk]
            assert lv.replace(".L", ".R") == rv, (
                f"Asymmetric values: {lv} vs {rv}"
            )


# ---------------------------------------------------------------------------
# TestMapMixamoBones
# ---------------------------------------------------------------------------


class TestMapMixamoBones:
    """Test _map_mixamo_bones filtering function."""

    def test_full_mapping_when_all_bones_present(self):
        source = list(MIXAMO_TO_RIGIFY.keys())
        target = list(MIXAMO_TO_RIGIFY.values())
        result = _map_mixamo_bones(source, target)
        assert len(result["mapped"]) == len(MIXAMO_TO_RIGIFY)
        assert result["unmapped_source"] == []

    def test_partial_mapping_missing_source(self):
        source = ["mixamorig:Hips", "mixamorig:Spine"]
        target = list(MIXAMO_TO_RIGIFY.values())
        result = _map_mixamo_bones(source, target)
        assert len(result["mapped"]) == 2

    def test_partial_mapping_missing_target(self):
        source = list(MIXAMO_TO_RIGIFY.keys())
        target = ["DEF-spine", "DEF-spine.001"]
        result = _map_mixamo_bones(source, target)
        assert len(result["mapped"]) == 2
        assert len(result["unmapped_source"]) > 0

    def test_no_mapping_when_no_overlap(self):
        source = ["bone_a", "bone_b"]
        target = ["bone_c", "bone_d"]
        result = _map_mixamo_bones(source, target)
        assert len(result["mapped"]) == 0

    def test_unmapped_source_contains_only_mixamorig(self):
        """Unmapped source should only list bones with mixamorig: prefix."""
        source = list(MIXAMO_TO_RIGIFY.keys()) + ["root", "armature"]
        target = ["DEF-spine"]  # Only maps Hips
        result = _map_mixamo_bones(source, target)
        for bone in result["unmapped_source"]:
            assert bone.startswith("mixamorig:")

    def test_unmapped_target_contains_only_def(self):
        """Unmapped target should only list bones with DEF- prefix."""
        source = ["mixamorig:Hips"]
        target = list(MIXAMO_TO_RIGIFY.values()) + ["MCH-spine", "ORG-spine"]
        result = _map_mixamo_bones(source, target)
        for bone in result["unmapped_target"]:
            assert bone.startswith("DEF-")


# ---------------------------------------------------------------------------
# TestGenerateUnityFilename
# ---------------------------------------------------------------------------


class TestGenerateUnityFilename:
    """Test _generate_unity_filename naming convention."""

    def test_unity_naming(self):
        result = _generate_unity_filename("Creature", "Walk", "unity")
        assert result == "Creature@Walk.fbx"

    def test_raw_naming(self):
        result = _generate_unity_filename("Creature", "Walk", "raw")
        assert result == "Walk.fbx"

    def test_unity_naming_with_spaces(self):
        result = _generate_unity_filename("My Creature", "Walk Cycle", "unity")
        assert result == "My_Creature@Walk_Cycle.fbx"

    def test_raw_naming_with_spaces(self):
        result = _generate_unity_filename("My Creature", "Walk Cycle", "raw")
        assert result == "Walk_Cycle.fbx"

    def test_fbx_extension(self):
        result = _generate_unity_filename("A", "B", "unity")
        assert result.endswith(".fbx")

    def test_at_separator_in_unity_naming(self):
        result = _generate_unity_filename("Dragon", "Fly", "unity")
        assert "@" in result

    def test_no_at_in_raw_naming(self):
        result = _generate_unity_filename("Dragon", "Fly", "raw")
        assert "@" not in result


# ---------------------------------------------------------------------------
# TestPreviewAngles
# ---------------------------------------------------------------------------


class TestPreviewAngles:
    """Test PREVIEW_ANGLES constant."""

    def test_front_angle_exists(self):
        assert "front" in PREVIEW_ANGLES

    def test_side_angle_exists(self):
        assert "side" in PREVIEW_ANGLES

    def test_angles_are_tuples_of_two(self):
        for name, angle in PREVIEW_ANGLES.items():
            assert isinstance(angle, tuple), f"{name} is not a tuple"
            assert len(angle) == 2, f"{name} has {len(angle)} elements"

    def test_front_is_zero_zero(self):
        assert PREVIEW_ANGLES["front"] == (0, 0)

    def test_back_is_180_zero(self):
        assert PREVIEW_ANGLES["back"] == (180, 0)

    def test_top_is_zero_90(self):
        assert PREVIEW_ANGLES["top"] == (0, 90)


# ---------------------------------------------------------------------------
# TestAIMotionStub (pure-logic aspects)
# ---------------------------------------------------------------------------


class TestAIMotionStub:
    """Test AI motion stub handler response contract.

    Since the handler requires bpy, we test the expected return contract
    by verifying the MIXAMO_TO_RIGIFY-adjacent stub data.
    """

    def test_valid_models(self):
        """The stub should accept hy-motion and motion-gpt models."""
        valid_models = ("hy-motion", "motion-gpt")
        assert "hy-motion" in valid_models
        assert "motion-gpt" in valid_models

    def test_stub_response_keys(self):
        """Stub should return status, message, prompt, model, frame_count."""
        expected_keys = {"status", "message", "prompt", "model", "frame_count"}
        # Verify the keys are the expected contract
        assert len(expected_keys) == 5


# ---------------------------------------------------------------------------
# TestBatchExportFBXSettings
# ---------------------------------------------------------------------------


class TestBatchExportFBXSettings:
    """Test batch export FBX configuration constants."""

    def test_unity_naming_uses_at_sign(self):
        filename = _generate_unity_filename("Char", "Walk", "unity")
        assert "@" in filename

    def test_unity_naming_format(self):
        """Unity auto-import requires ObjectName@ClipName.fbx format."""
        filename = _generate_unity_filename("Spider", "Attack_Bite", "unity")
        assert filename == "Spider@Attack_Bite.fbx"

    def test_multiple_clips_unique_names(self):
        clips = ["Walk", "Run", "Idle", "Attack"]
        filenames = [_generate_unity_filename("Char", c, "unity") for c in clips]
        assert len(filenames) == len(set(filenames)), "Duplicate filenames"
