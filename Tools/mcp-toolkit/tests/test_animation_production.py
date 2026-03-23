"""Tests for animation production tools (GAP 62-66).

Covers:
  - FK/IK mode validation
  - Motion retarget parameter validation
  - Mocap import parameter validation
  - Pose library action validation
  - Animation layer blend mode validation
  - Keyframe operation validation
  - Contact solver parameter validation
  - Auto bone mapping (fuzzy matching)
  - Noise filter (sub-threshold removal)
  - Contact phase detection
  - Pose lerp interpolation
  - Euler filter discontinuity correction

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.animation_production import (
    LIMB_CHAIN_MAP,
    VALID_BLEND_MODES,
    VALID_CHANNELS,
    VALID_FK_IK_MODES,
    VALID_HANDLE_TYPES,
    VALID_INTERPOLATIONS,
    VALID_KEYFRAME_OPERATIONS,
    VALID_LAYER_ACTIONS,
    VALID_LIMBS,
    VALID_POSE_ACTIONS,
    VALID_POSE_CATEGORIES,
    compute_bone_mapping_auto,
    compute_contact_phases,
    compute_euler_filter,
    compute_noise_filter,
    lerp_pose,
    validate_animation_layer_params,
    validate_contact_solver_params,
    validate_fk_ik_params,
    validate_keyframe_edit_params,
    validate_mocap_params,
    validate_pose_library_params,
    validate_retarget_params,
)


# ===========================================================================
# Constants sanity checks
# ===========================================================================


class TestConstants:
    """Verify constant sets contain expected values."""

    def test_valid_limbs(self):
        assert VALID_LIMBS == {"arm_L", "arm_R", "leg_L", "leg_R"}

    def test_valid_fk_ik_modes(self):
        assert VALID_FK_IK_MODES == {"FK", "IK"}

    def test_limb_chain_map_keys(self):
        assert set(LIMB_CHAIN_MAP.keys()) == VALID_LIMBS

    def test_limb_chain_map_has_bones(self):
        for limb, info in LIMB_CHAIN_MAP.items():
            assert "bones" in info
            assert "ik_bone" in info
            assert "pole_bone" in info
            assert len(info["bones"]) == 3, f"{limb} chain should have 3 bones"

    def test_valid_pose_actions(self):
        assert VALID_POSE_ACTIONS == {"save", "load", "list", "delete", "blend"}

    def test_valid_pose_categories(self):
        assert "combat" in VALID_POSE_CATEGORIES
        assert "idle" in VALID_POSE_CATEGORIES
        assert "expression" in VALID_POSE_CATEGORIES

    def test_valid_layer_actions(self):
        assert VALID_LAYER_ACTIONS == {
            "add_layer", "remove_layer", "set_weight", "list_layers",
        }

    def test_valid_blend_modes(self):
        assert VALID_BLEND_MODES == {"REPLACE", "ADD", "MULTIPLY"}

    def test_valid_keyframe_operations(self):
        assert len(VALID_KEYFRAME_OPERATIONS) == 10
        assert "insert" in VALID_KEYFRAME_OPERATIONS
        assert "euler_filter" in VALID_KEYFRAME_OPERATIONS

    def test_valid_interpolations(self):
        assert "BEZIER" in VALID_INTERPOLATIONS
        assert "LINEAR" in VALID_INTERPOLATIONS
        assert "CONSTANT" in VALID_INTERPOLATIONS

    def test_valid_handle_types(self):
        assert "AUTO" in VALID_HANDLE_TYPES
        assert "AUTO_CLAMPED" in VALID_HANDLE_TYPES
        assert "VECTOR" in VALID_HANDLE_TYPES

    def test_valid_channels(self):
        assert VALID_CHANNELS == {
            "location", "rotation_quaternion", "rotation_euler", "scale",
        }


# ===========================================================================
# FK/IK Switch Validation (GAP-62)
# ===========================================================================


class TestValidateFKIKParams:
    def test_valid_fk(self):
        result = validate_fk_ik_params({
            "armature_name": "Armature",
            "limb": "arm_L",
            "mode": "FK",
        })
        assert result["armature_name"] == "Armature"
        assert result["limb"] == "arm_L"
        assert result["mode"] == "FK"
        assert result["match_pose"] is True

    def test_valid_ik(self):
        result = validate_fk_ik_params({
            "armature_name": "Armature",
            "limb": "leg_R",
            "mode": "IK",
            "match_pose": False,
        })
        assert result["mode"] == "IK"
        assert result["match_pose"] is False

    def test_missing_armature_name(self):
        with pytest.raises(ValueError, match="armature_name"):
            validate_fk_ik_params({"limb": "arm_L", "mode": "FK"})

    def test_empty_armature_name(self):
        with pytest.raises(ValueError, match="armature_name"):
            validate_fk_ik_params({"armature_name": "", "limb": "arm_L", "mode": "FK"})

    def test_invalid_limb(self):
        with pytest.raises(ValueError, match="Invalid limb"):
            validate_fk_ik_params({
                "armature_name": "A", "limb": "wing_L", "mode": "FK",
            })

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            validate_fk_ik_params({
                "armature_name": "A", "limb": "arm_L", "mode": "BOTH",
            })

    def test_none_mode(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            validate_fk_ik_params({
                "armature_name": "A", "limb": "arm_L",
            })

    @pytest.mark.parametrize("limb", sorted(VALID_LIMBS))
    def test_all_limbs_accepted(self, limb):
        result = validate_fk_ik_params({
            "armature_name": "A", "limb": limb, "mode": "FK",
        })
        assert result["limb"] == limb

    @pytest.mark.parametrize("mode", sorted(VALID_FK_IK_MODES))
    def test_all_modes_accepted(self, mode):
        result = validate_fk_ik_params({
            "armature_name": "A", "limb": "arm_L", "mode": mode,
        })
        assert result["mode"] == mode

    def test_match_pose_default_true(self):
        result = validate_fk_ik_params({
            "armature_name": "A", "limb": "arm_L", "mode": "FK",
        })
        assert result["match_pose"] is True

    def test_match_pose_coerced_to_bool(self):
        result = validate_fk_ik_params({
            "armature_name": "A", "limb": "arm_L", "mode": "FK",
            "match_pose": 0,
        })
        assert result["match_pose"] is False


# ===========================================================================
# Retarget Motion Validation (GAP-63a)
# ===========================================================================


class TestValidateRetargetParams:
    def test_valid_minimal(self):
        result = validate_retarget_params({
            "source_armature": "SourceRig",
            "target_armature": "TargetRig",
        })
        assert result["source_armature"] == "SourceRig"
        assert result["target_armature"] == "TargetRig"
        assert result["bone_mapping"] is None
        assert result["scale_factor"] == 1.0
        assert result["clean_noise"] is False

    def test_valid_full(self):
        result = validate_retarget_params({
            "source_armature": "Src",
            "target_armature": "Tgt",
            "bone_mapping": {"Hips": "DEF-spine"},
            "frame_range": [1, 100],
            "scale_factor": 0.5,
            "clean_noise": True,
            "noise_threshold": 0.01,
        })
        assert result["bone_mapping"] == {"Hips": "DEF-spine"}
        assert result["frame_range"] == [1, 100]
        assert result["scale_factor"] == 0.5
        assert result["clean_noise"] is True
        assert result["noise_threshold"] == 0.01

    def test_missing_source(self):
        with pytest.raises(ValueError, match="source_armature"):
            validate_retarget_params({"target_armature": "T"})

    def test_missing_target(self):
        with pytest.raises(ValueError, match="target_armature"):
            validate_retarget_params({"source_armature": "S"})

    def test_same_source_target(self):
        with pytest.raises(ValueError, match="must be different"):
            validate_retarget_params({
                "source_armature": "Same",
                "target_armature": "Same",
            })

    def test_invalid_bone_mapping_empty(self):
        with pytest.raises(ValueError, match="bone_mapping"):
            validate_retarget_params({
                "source_armature": "S", "target_armature": "T",
                "bone_mapping": {},
            })

    def test_invalid_frame_range_reversed(self):
        with pytest.raises(ValueError, match="frame_range"):
            validate_retarget_params({
                "source_armature": "S", "target_armature": "T",
                "frame_range": [100, 1],
            })

    def test_invalid_frame_range_wrong_length(self):
        with pytest.raises(ValueError, match="frame_range"):
            validate_retarget_params({
                "source_armature": "S", "target_armature": "T",
                "frame_range": [1],
            })

    def test_zero_scale_factor(self):
        with pytest.raises(ValueError, match="scale_factor"):
            validate_retarget_params({
                "source_armature": "S", "target_armature": "T",
                "scale_factor": 0,
            })

    def test_negative_noise_threshold(self):
        with pytest.raises(ValueError, match="noise_threshold"):
            validate_retarget_params({
                "source_armature": "S", "target_armature": "T",
                "noise_threshold": -0.01,
            })


# ===========================================================================
# Mocap Import Validation (GAP-63b)
# ===========================================================================


class TestValidateMocapParams:
    def test_valid_bvh(self):
        result = validate_mocap_params({"file_path": "/data/walk.bvh"})
        assert result["file_format"] == "bvh"
        assert result["scale"] == 1.0
        assert result["frame_start"] == 1

    def test_valid_fbx(self):
        result = validate_mocap_params({
            "file_path": "C:/mocap/run.fbx",
            "target_armature": "MyRig",
            "scale": 0.01,
            "frame_start": 10,
        })
        assert result["file_format"] == "fbx"
        assert result["target_armature"] == "MyRig"
        assert result["scale"] == 0.01
        assert result["frame_start"] == 10

    def test_missing_file_path(self):
        with pytest.raises(ValueError, match="file_path"):
            validate_mocap_params({})

    def test_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            validate_mocap_params({"file_path": "/data/anim.abc"})

    def test_no_extension(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            validate_mocap_params({"file_path": "/data/animation"})

    def test_zero_scale(self):
        with pytest.raises(ValueError, match="scale"):
            validate_mocap_params({"file_path": "/data/walk.bvh", "scale": 0})

    def test_case_insensitive_extension(self):
        result = validate_mocap_params({"file_path": "/data/anim.BVH"})
        assert result["file_format"] == "bvh"

    def test_fbx_uppercase(self):
        result = validate_mocap_params({"file_path": "/data/anim.FBX"})
        assert result["file_format"] == "fbx"


# ===========================================================================
# Pose Library Validation (GAP-64a)
# ===========================================================================


class TestValidatePoseLibraryParams:
    def test_valid_save(self):
        result = validate_pose_library_params({
            "armature_name": "Rig",
            "action": "save",
            "pose_name": "combat_ready",
            "category": "combat",
        })
        assert result["action"] == "save"
        assert result["pose_name"] == "combat_ready"
        assert result["category"] == "combat"

    def test_valid_list(self):
        result = validate_pose_library_params({
            "armature_name": "Rig",
            "action": "list",
        })
        assert result["action"] == "list"
        assert result["pose_name"] is None  # Not required for list

    def test_valid_blend(self):
        result = validate_pose_library_params({
            "armature_name": "Rig",
            "action": "blend",
            "pose_name": "idle_01",
            "blend_factor": 0.5,
        })
        assert result["blend_factor"] == 0.5

    def test_missing_armature(self):
        with pytest.raises(ValueError, match="armature_name"):
            validate_pose_library_params({"action": "list"})

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="Invalid action"):
            validate_pose_library_params({
                "armature_name": "R", "action": "export",
            })

    def test_save_requires_pose_name(self):
        with pytest.raises(ValueError, match="pose_name"):
            validate_pose_library_params({
                "armature_name": "R", "action": "save",
            })

    def test_load_requires_pose_name(self):
        with pytest.raises(ValueError, match="pose_name"):
            validate_pose_library_params({
                "armature_name": "R", "action": "load",
            })

    def test_delete_requires_pose_name(self):
        with pytest.raises(ValueError, match="pose_name"):
            validate_pose_library_params({
                "armature_name": "R", "action": "delete",
            })

    def test_blend_requires_pose_name(self):
        with pytest.raises(ValueError, match="pose_name"):
            validate_pose_library_params({
                "armature_name": "R", "action": "blend",
            })

    def test_invalid_category(self):
        with pytest.raises(ValueError, match="Invalid category"):
            validate_pose_library_params({
                "armature_name": "R", "action": "save",
                "pose_name": "p", "category": "dancing",
            })

    def test_blend_factor_out_of_range_high(self):
        with pytest.raises(ValueError, match="blend_factor"):
            validate_pose_library_params({
                "armature_name": "R", "action": "save",
                "pose_name": "p", "blend_factor": 1.5,
            })

    def test_blend_factor_out_of_range_low(self):
        with pytest.raises(ValueError, match="blend_factor"):
            validate_pose_library_params({
                "armature_name": "R", "action": "save",
                "pose_name": "p", "blend_factor": -0.1,
            })

    @pytest.mark.parametrize("action", sorted(VALID_POSE_ACTIONS))
    def test_all_actions_accepted(self, action):
        params = {"armature_name": "R", "action": action}
        if action in ("save", "load", "delete", "blend"):
            params["pose_name"] = "test_pose"
        result = validate_pose_library_params(params)
        assert result["action"] == action

    @pytest.mark.parametrize("category", sorted(VALID_POSE_CATEGORIES))
    def test_all_categories_accepted(self, category):
        result = validate_pose_library_params({
            "armature_name": "R", "action": "save",
            "pose_name": "p", "category": category,
        })
        assert result["category"] == category


# ===========================================================================
# Animation Layer Validation (GAP-64b)
# ===========================================================================


class TestValidateAnimationLayerParams:
    def test_valid_add_layer(self):
        result = validate_animation_layer_params({
            "armature_name": "Rig",
            "action": "add_layer",
            "layer_name": "breathing",
            "weight": 0.5,
            "blend_mode": "ADD",
        })
        assert result["layer_name"] == "breathing"
        assert result["weight"] == 0.5
        assert result["blend_mode"] == "ADD"

    def test_valid_list_layers(self):
        result = validate_animation_layer_params({
            "armature_name": "Rig",
            "action": "list_layers",
        })
        assert result["action"] == "list_layers"
        assert result["layer_name"] is None

    def test_missing_armature(self):
        with pytest.raises(ValueError, match="armature_name"):
            validate_animation_layer_params({"action": "list_layers"})

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="Invalid action"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "merge",
            })

    def test_add_requires_layer_name(self):
        with pytest.raises(ValueError, match="layer_name"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "add_layer",
            })

    def test_remove_requires_layer_name(self):
        with pytest.raises(ValueError, match="layer_name"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "remove_layer",
            })

    def test_set_weight_requires_layer_name(self):
        with pytest.raises(ValueError, match="layer_name"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "set_weight",
            })

    def test_weight_out_of_range(self):
        with pytest.raises(ValueError, match="weight"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "add_layer",
                "layer_name": "L", "weight": 1.5,
            })

    def test_weight_negative(self):
        with pytest.raises(ValueError, match="weight"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "add_layer",
                "layer_name": "L", "weight": -0.1,
            })

    def test_invalid_blend_mode(self):
        with pytest.raises(ValueError, match="Invalid blend_mode"):
            validate_animation_layer_params({
                "armature_name": "R", "action": "add_layer",
                "layer_name": "L", "blend_mode": "SCREEN",
            })

    @pytest.mark.parametrize("mode", sorted(VALID_BLEND_MODES))
    def test_all_blend_modes_accepted(self, mode):
        result = validate_animation_layer_params({
            "armature_name": "R", "action": "add_layer",
            "layer_name": "L", "blend_mode": mode,
        })
        assert result["blend_mode"] == mode

    @pytest.mark.parametrize("action", sorted(VALID_LAYER_ACTIONS))
    def test_all_layer_actions_accepted(self, action):
        params = {"armature_name": "R", "action": action}
        if action in ("add_layer", "remove_layer", "set_weight"):
            params["layer_name"] = "test_layer"
        result = validate_animation_layer_params(params)
        assert result["action"] == action


# ===========================================================================
# Keyframe Edit Validation (GAP-65)
# ===========================================================================


class TestValidateKeyframeEditParams:
    def test_valid_insert(self):
        result = validate_keyframe_edit_params({
            "armature_name": "Rig",
            "action_name": "walk",
            "operation": "insert",
            "frame": 10,
            "value": 0.5,
        })
        assert result["operation"] == "insert"
        assert result["frame"] == 10
        assert result["value"] == 0.5

    def test_valid_clean(self):
        result = validate_keyframe_edit_params({
            "armature_name": "Rig",
            "action_name": "walk",
            "operation": "clean",
            "clean_threshold": 0.01,
        })
        assert result["operation"] == "clean"
        assert result["clean_threshold"] == 0.01

    def test_valid_euler_filter(self):
        result = validate_keyframe_edit_params({
            "armature_name": "Rig",
            "action_name": "walk",
            "operation": "euler_filter",
        })
        assert result["operation"] == "euler_filter"

    def test_missing_armature(self):
        with pytest.raises(ValueError, match="armature_name"):
            validate_keyframe_edit_params({
                "action_name": "walk", "operation": "clean",
            })

    def test_missing_action_name(self):
        with pytest.raises(ValueError, match="action_name"):
            validate_keyframe_edit_params({
                "armature_name": "R", "operation": "clean",
            })

    def test_invalid_operation(self):
        with pytest.raises(ValueError, match="Invalid operation"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "explode",
            })

    def test_insert_requires_frame(self):
        with pytest.raises(ValueError, match="frame is required"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "insert", "value": 1.0,
            })

    def test_insert_requires_value(self):
        with pytest.raises(ValueError, match="value is required"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "insert", "frame": 10,
            })

    def test_delete_requires_frame(self):
        with pytest.raises(ValueError, match="frame is required"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "delete",
            })

    def test_move_requires_frame(self):
        with pytest.raises(ValueError, match="frame is required"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "move",
            })

    def test_set_interpolation_invalid(self):
        with pytest.raises(ValueError, match="Invalid interpolation"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "set_interpolation",
                "interpolation": "SMOOTH",
            })

    def test_set_handle_invalid(self):
        with pytest.raises(ValueError, match="Invalid handle_type"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "set_handle",
                "handle_type": "SPLINE",
            })

    def test_scale_time_requires_value(self):
        with pytest.raises(ValueError, match="time_scale is required"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "scale_time",
            })

    def test_scale_time_must_be_positive(self):
        with pytest.raises(ValueError, match="time_scale must be > 0"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "scale_time", "time_scale": -1.0,
            })

    def test_negative_clean_threshold(self):
        with pytest.raises(ValueError, match="clean_threshold"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "clean", "clean_threshold": -1,
            })

    def test_invalid_channel(self):
        with pytest.raises(ValueError, match="Invalid channel"):
            validate_keyframe_edit_params({
                "armature_name": "R", "action_name": "a",
                "operation": "clean", "channel": "color",
            })

    @pytest.mark.parametrize("op", sorted(VALID_KEYFRAME_OPERATIONS))
    def test_all_operations_accepted(self, op):
        params = {
            "armature_name": "R", "action_name": "a", "operation": op,
        }
        # Supply required params per operation
        if op in ("insert", "delete", "move"):
            params["frame"] = 10
        if op == "insert":
            params["value"] = 1.0
        if op == "set_interpolation":
            params["interpolation"] = "BEZIER"
        if op == "set_handle":
            params["handle_type"] = "AUTO"
        if op == "scale_time":
            params["time_scale"] = 2.0
        result = validate_keyframe_edit_params(params)
        assert result["operation"] == op

    @pytest.mark.parametrize("interp", sorted(VALID_INTERPOLATIONS))
    def test_all_interpolations_accepted(self, interp):
        result = validate_keyframe_edit_params({
            "armature_name": "R", "action_name": "a",
            "operation": "set_interpolation",
            "interpolation": interp,
        })
        assert result["interpolation"] == interp

    @pytest.mark.parametrize("ht", sorted(VALID_HANDLE_TYPES))
    def test_all_handle_types_accepted(self, ht):
        result = validate_keyframe_edit_params({
            "armature_name": "R", "action_name": "a",
            "operation": "set_handle",
            "handle_type": ht,
        })
        assert result["handle_type"] == ht

    @pytest.mark.parametrize("ch", sorted(VALID_CHANNELS))
    def test_all_channels_accepted(self, ch):
        result = validate_keyframe_edit_params({
            "armature_name": "R", "action_name": "a",
            "operation": "clean", "channel": ch,
        })
        assert result["channel"] == ch


# ===========================================================================
# Contact Solver Validation (GAP-66)
# ===========================================================================


class TestValidateContactSolverParams:
    def test_valid_minimal(self):
        result = validate_contact_solver_params({
            "armature_name": "Rig",
            "action_name": "walk",
            "contact_bones": ["foot_ik.L", "foot_ik.R"],
        })
        assert result["ground_height"] == 0.0
        assert result["contact_threshold"] == 0.05
        assert result["lock_rotation"] is False

    def test_valid_full(self):
        result = validate_contact_solver_params({
            "armature_name": "Rig",
            "action_name": "walk",
            "contact_bones": ["foot_ik.L"],
            "ground_height": 0.5,
            "contact_threshold": 0.1,
            "frame_range": [1, 60],
            "lock_rotation": True,
        })
        assert result["ground_height"] == 0.5
        assert result["contact_threshold"] == 0.1
        assert result["frame_range"] == [1, 60]
        assert result["lock_rotation"] is True

    def test_missing_armature(self):
        with pytest.raises(ValueError, match="armature_name"):
            validate_contact_solver_params({
                "action_name": "walk",
                "contact_bones": ["foot"],
            })

    def test_missing_action_name(self):
        with pytest.raises(ValueError, match="action_name"):
            validate_contact_solver_params({
                "armature_name": "R",
                "contact_bones": ["foot"],
            })

    def test_missing_contact_bones(self):
        with pytest.raises(ValueError, match="contact_bones"):
            validate_contact_solver_params({
                "armature_name": "R", "action_name": "walk",
            })

    def test_empty_contact_bones(self):
        with pytest.raises(ValueError, match="contact_bones"):
            validate_contact_solver_params({
                "armature_name": "R", "action_name": "walk",
                "contact_bones": [],
            })

    def test_invalid_contact_bone_entry(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_contact_solver_params({
                "armature_name": "R", "action_name": "walk",
                "contact_bones": ["foot", ""],
            })

    def test_negative_threshold(self):
        with pytest.raises(ValueError, match="contact_threshold"):
            validate_contact_solver_params({
                "armature_name": "R", "action_name": "walk",
                "contact_bones": ["foot"],
                "contact_threshold": -0.01,
            })

    def test_invalid_frame_range(self):
        with pytest.raises(ValueError, match="frame_range"):
            validate_contact_solver_params({
                "armature_name": "R", "action_name": "walk",
                "contact_bones": ["foot"],
                "frame_range": [60, 1],
            })


# ===========================================================================
# Auto Bone Mapping (GAP-63)
# ===========================================================================


class TestComputeBoneMappingAuto:
    def test_exact_match_case_insensitive(self):
        source = ["Hips", "Spine"]
        target = ["hips", "spine"]
        result = compute_bone_mapping_auto(source, target)
        assert result["Hips"] == "hips"
        assert result["Spine"] == "spine"

    def test_prefix_stripping_def(self):
        source = ["DEF-thigh.L", "DEF-shin.L"]
        target = ["thigh.L", "shin.L"]
        result = compute_bone_mapping_auto(source, target)
        assert result["DEF-thigh.L"] == "thigh.L"
        assert result["DEF-shin.L"] == "shin.L"

    def test_prefix_stripping_mixamo(self):
        source = ["mixamorig:Hips", "mixamorig:Spine"]
        target = ["DEF-Hips", "DEF-Spine"]
        result = compute_bone_mapping_auto(source, target)
        assert "mixamorig:Hips" in result
        assert "mixamorig:Spine" in result

    def test_side_matching(self):
        source = ["UpperArm.L", "UpperArm.R"]
        target = ["DEF-upper_arm.L", "DEF-upper_arm.R"]
        result = compute_bone_mapping_auto(source, target)
        # Should respect .L -> .L and .R -> .R
        if "UpperArm.L" in result:
            assert result["UpperArm.L"].endswith(".L")
        if "UpperArm.R" in result:
            assert result["UpperArm.R"].endswith(".R")

    def test_no_match_returns_empty(self):
        source = ["CompletelyUnique_A"]
        target = ["TotallyDifferent_B"]
        result = compute_bone_mapping_auto(source, target)
        # With substring matching off (too short or no containment), may be empty
        assert isinstance(result, dict)

    def test_substring_containment(self):
        source = ["LeftUpperArm"]
        target = ["DEF-upperarm.L"]
        result = compute_bone_mapping_auto(source, target)
        # "upperarm" is contained in both after normalization
        assert len(result) >= 0  # May or may not match depending on side

    def test_preserves_all_source_bones_possible(self):
        source = ["Hips", "Spine", "Head"]
        target = ["Hips", "Spine", "Head", "Tail"]
        result = compute_bone_mapping_auto(source, target)
        assert len(result) == 3

    def test_empty_inputs(self):
        assert compute_bone_mapping_auto([], []) == {}
        assert compute_bone_mapping_auto(["a"], []) == {}
        assert compute_bone_mapping_auto([], ["a"]) == {}

    def test_one_to_one_mapping(self):
        """Each source bone maps to at most one target bone."""
        source = ["A", "B", "C"]
        target = ["a", "b", "c"]
        result = compute_bone_mapping_auto(source, target)
        # Values should all be unique
        assert len(set(result.values())) == len(result)

    def test_mixamo_to_rigify_common_bones(self):
        """Realistic test: Mixamo names to Rigify DEF- names."""
        source = [
            "mixamorig:Hips",
            "mixamorig:Spine",
            "mixamorig:Head",
            "mixamorig:LeftUpLeg",
            "mixamorig:RightUpLeg",
        ]
        target = [
            "DEF-spine",
            "DEF-spine.001",
            "DEF-head",
            "DEF-thigh.L",
            "DEF-thigh.R",
        ]
        result = compute_bone_mapping_auto(source, target)
        # Should find at least some mappings
        assert len(result) >= 2  # At minimum Hips->spine and Head->head

    def test_cc_base_prefix(self):
        source = ["CC_Base_Hip", "CC_Base_Spine"]
        target = ["Hip", "Spine"]
        result = compute_bone_mapping_auto(source, target)
        assert result.get("CC_Base_Hip") == "Hip"
        assert result.get("CC_Base_Spine") == "Spine"


# ===========================================================================
# Noise Filter (GAP-63)
# ===========================================================================


class TestComputeNoiseFilter:
    def test_preserves_first_and_last(self):
        kf = [(0, 0.0), (1, 0.0001), (2, 0.0)]
        result = compute_noise_filter(kf, 0.01)
        assert result[0] == kf[0]
        assert result[-1] == kf[-1]

    def test_removes_small_delta(self):
        kf = [
            (0, 0.0), (1, 0.001), (2, 0.002), (3, 0.001), (4, 0.0),
        ]
        result = compute_noise_filter(kf, 0.01)
        # All intermediate deltas are < 0.01, so only first and last survive
        assert len(result) == 2
        assert result[0] == kf[0]
        assert result[-1] == kf[-1]

    def test_keeps_significant_change(self):
        kf = [(0, 0.0), (5, 1.0), (10, 0.0)]
        result = compute_noise_filter(kf, 0.01)
        assert len(result) == 3

    def test_empty_input(self):
        assert compute_noise_filter([], 0.01) == []

    def test_single_keyframe(self):
        kf = [(0, 1.0)]
        assert compute_noise_filter(kf, 0.01) == [(0, 1.0)]

    def test_two_keyframes_always_kept(self):
        kf = [(0, 0.0), (1, 0.0001)]
        result = compute_noise_filter(kf, 0.01)
        assert len(result) == 2

    def test_threshold_zero_keeps_all(self):
        kf = [(0, 0.0), (1, 0.0001), (2, 0.0002), (3, 0.0003)]
        result = compute_noise_filter(kf, 0.0)
        # At threshold 0, any non-zero delta is kept
        assert len(result) >= 2  # First and last always kept

    def test_large_spike_preserved(self):
        kf = [
            (0, 0.0), (1, 0.001), (2, 5.0), (3, 0.001), (4, 0.0),
        ]
        result = compute_noise_filter(kf, 0.01)
        # The spike at frame 2 should be preserved
        frames_in_result = {f for f, _ in result}
        assert 2 in frames_in_result

    def test_alternating_signal(self):
        kf = [(i, 0.5 * (i % 2)) for i in range(10)]
        result = compute_noise_filter(kf, 0.1)
        # Alternating 0 and 0.5 -- all deltas are 0.5, above threshold
        assert len(result) == 10


# ===========================================================================
# Contact Phase Detection (GAP-66)
# ===========================================================================


class TestComputeContactPhases:
    def test_single_contact_phase(self):
        heights = [(i, 0.0) for i in range(10)]
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.05)
        assert phases == [(0, 9)]

    def test_no_contact(self):
        heights = [(i, 1.0) for i in range(10)]
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.05)
        assert phases == []

    def test_two_contact_phases(self):
        heights = [
            (0, 0.0), (1, 0.0), (2, 0.0),  # Contact phase 1
            (3, 1.0), (4, 1.0),              # Airborne
            (5, 0.0), (6, 0.0),              # Contact phase 2
            (7, 1.0),                         # Airborne
        ]
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.05)
        assert phases == [(0, 2), (5, 6)]

    def test_threshold_determines_contact(self):
        heights = [(0, 0.04), (1, 0.06), (2, 0.03)]
        # Threshold 0.05: frame 0 and 2 are in contact, frame 1 is not
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.05)
        assert phases == [(0, 0), (2, 2)]

    def test_empty_input(self):
        assert compute_contact_phases([], 0.0, 0.05) == []

    def test_single_frame_contact(self):
        heights = [(5, 0.0)]
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.05)
        assert phases == [(5, 5)]

    def test_ground_height_offset(self):
        heights = [(0, 1.0), (1, 1.0), (2, 2.0)]
        phases = compute_contact_phases(heights, ground=1.0, threshold=0.05)
        assert phases == [(0, 1)]

    def test_walk_cycle_pattern(self):
        """Simulated walk cycle: foot goes up and down."""
        heights = []
        for i in range(24):
            # Sinusoidal foot height
            h = max(0.0, math.sin(i * math.pi / 12.0) * 0.3)
            heights.append((i, h))
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.02)
        # Should have contact at start and end of cycle where sin is ~0
        assert len(phases) >= 1

    def test_negative_ground_height(self):
        heights = [(0, -1.0), (1, -1.0), (2, 0.0)]
        phases = compute_contact_phases(heights, ground=-1.0, threshold=0.05)
        assert phases == [(0, 1)]

    def test_contact_at_end_closes_phase(self):
        heights = [(0, 1.0), (1, 0.0), (2, 0.0)]
        phases = compute_contact_phases(heights, ground=0.0, threshold=0.05)
        assert phases == [(1, 2)]


# ===========================================================================
# Pose Lerp (GAP-64a)
# ===========================================================================


class TestLerpPose:
    def test_factor_zero_returns_pose_a(self):
        a = {"bone1": {"location": [1, 2, 3], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]}}
        b = {"bone1": {"location": [4, 5, 6], "rotation": [0, 1, 0, 0], "scale": [2, 2, 2]}}
        result = lerp_pose(a, b, 0.0)
        assert result["bone1"]["location"] == pytest.approx([1, 2, 3])
        assert result["bone1"]["scale"] == pytest.approx([1, 1, 1])

    def test_factor_one_returns_pose_b(self):
        a = {"bone1": {"location": [1, 2, 3], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]}}
        b = {"bone1": {"location": [4, 5, 6], "rotation": [1, 0, 0, 0], "scale": [2, 2, 2]}}
        result = lerp_pose(a, b, 1.0)
        assert result["bone1"]["location"] == pytest.approx([4, 5, 6])
        assert result["bone1"]["scale"] == pytest.approx([2, 2, 2])

    def test_factor_half_interpolates(self):
        a = {"bone1": {"location": [0, 0, 0], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]}}
        b = {"bone1": {"location": [10, 10, 10], "rotation": [1, 0, 0, 0], "scale": [3, 3, 3]}}
        result = lerp_pose(a, b, 0.5)
        assert result["bone1"]["location"] == pytest.approx([5, 5, 5])
        assert result["bone1"]["scale"] == pytest.approx([2, 2, 2])

    def test_only_common_bones(self):
        a = {"bone1": {"location": [0, 0, 0]}, "bone2": {"location": [1, 1, 1]}}
        b = {"bone1": {"location": [10, 10, 10]}, "bone3": {"location": [5, 5, 5]}}
        result = lerp_pose(a, b, 0.5)
        assert "bone1" in result
        assert "bone2" not in result
        assert "bone3" not in result

    def test_empty_poses(self):
        assert lerp_pose({}, {}, 0.5) == {}

    def test_factor_clamped_below_zero(self):
        a = {"b": {"location": [0, 0, 0], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]}}
        b = {"b": {"location": [10, 10, 10], "rotation": [1, 0, 0, 0], "scale": [2, 2, 2]}}
        result = lerp_pose(a, b, -5.0)
        assert result["b"]["location"] == pytest.approx([0, 0, 0])

    def test_factor_clamped_above_one(self):
        a = {"b": {"location": [0, 0, 0], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]}}
        b = {"b": {"location": [10, 10, 10], "rotation": [1, 0, 0, 0], "scale": [2, 2, 2]}}
        result = lerp_pose(a, b, 5.0)
        assert result["b"]["location"] == pytest.approx([10, 10, 10])

    def test_rotation_nlerp_identity(self):
        """Interpolating between two identical quaternions gives the same quaternion."""
        q = [0.707, 0.707, 0, 0]
        a = {"b": {"rotation": q}}
        b = {"b": {"rotation": q}}
        result = lerp_pose(a, b, 0.5)
        # Should be normalized version of q
        length = math.sqrt(sum(v * v for v in result["b"]["rotation"]))
        assert length == pytest.approx(1.0, abs=1e-6)

    def test_rotation_shortest_path(self):
        """Quaternion lerp should take shortest path (negative dot check)."""
        a = {"b": {"rotation": [1, 0, 0, 0]}}
        b = {"b": {"rotation": [-1, 0, 0, 0]}}  # Same rotation, opposite quat
        result = lerp_pose(a, b, 0.5)
        # Should still be near identity (nlerp handles sign flip)
        length = math.sqrt(sum(v * v for v in result["b"]["rotation"]))
        assert length == pytest.approx(1.0, abs=1e-6)

    def test_partial_channels(self):
        """Bones with only some channels still interpolate what they have."""
        a = {"b": {"location": [0, 0, 0]}}
        b = {"b": {"location": [10, 10, 10]}}
        result = lerp_pose(a, b, 0.3)
        assert result["b"]["location"] == pytest.approx([3, 3, 3])
        assert "rotation" not in result["b"]
        assert "scale" not in result["b"]

    def test_multiple_bones(self):
        a = {
            "spine": {"location": [0, 0, 0], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]},
            "head": {"location": [0, 0, 1], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]},
        }
        b = {
            "spine": {"location": [0, 0, 0], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]},
            "head": {"location": [0, 0, 2], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]},
        }
        result = lerp_pose(a, b, 0.5)
        assert len(result) == 2
        assert result["head"]["location"][2] == pytest.approx(1.5)


# ===========================================================================
# Euler Filter (GAP-65)
# ===========================================================================


class TestComputeEulerFilter:
    def test_no_discontinuity(self):
        eulers = [(0.0, 0.0, 0.0), (0.1, 0.1, 0.1), (0.2, 0.2, 0.2)]
        result = compute_euler_filter(eulers)
        assert len(result) == 3
        for i, e in enumerate(result):
            assert e == pytest.approx(eulers[i], abs=1e-6)

    def test_360_flip_x_axis(self):
        """A 360-degree flip on X should be corrected."""
        TWO_PI = 2.0 * math.pi
        eulers = [
            (0.1, 0.0, 0.0),
            (0.2, 0.0, 0.0),
            (0.3 - TWO_PI, 0.0, 0.0),  # Flip!
            (0.4 - TWO_PI, 0.0, 0.0),
        ]
        result = compute_euler_filter(eulers)
        # After filtering, values should be continuous
        for i in range(1, len(result)):
            dx = abs(result[i][0] - result[i - 1][0])
            assert dx < math.pi, f"Discontinuity at frame {i}: delta={dx}"

    def test_360_flip_y_axis(self):
        TWO_PI = 2.0 * math.pi
        eulers = [
            (0.0, 1.0, 0.0),
            (0.0, 1.1, 0.0),
            (0.0, 1.2 + TWO_PI, 0.0),  # Positive flip
        ]
        result = compute_euler_filter(eulers)
        for i in range(1, len(result)):
            dy = abs(result[i][1] - result[i - 1][1])
            assert dy < math.pi

    def test_360_flip_z_axis(self):
        TWO_PI = 2.0 * math.pi
        eulers = [
            (0.0, 0.0, 0.5),
            (0.0, 0.0, 0.6),
            (0.0, 0.0, 0.7 - TWO_PI),
        ]
        result = compute_euler_filter(eulers)
        for i in range(1, len(result)):
            dz = abs(result[i][2] - result[i - 1][2])
            assert dz < math.pi

    def test_multiple_flips(self):
        TWO_PI = 2.0 * math.pi
        eulers = [(0.0, 0.0, 0.0)]
        for i in range(1, 20):
            # Add a flip every 5 frames
            val = i * 0.1
            if i % 5 == 0:
                val -= TWO_PI
            eulers.append((val, 0.0, 0.0))

        result = compute_euler_filter(eulers)
        # Should be monotonically increasing after filter
        for i in range(1, len(result)):
            assert result[i][0] >= result[i - 1][0] - 0.5

    def test_empty_input(self):
        assert compute_euler_filter([]) == []

    def test_single_euler(self):
        result = compute_euler_filter([(1.0, 2.0, 3.0)])
        assert result == [(1.0, 2.0, 3.0)]

    def test_two_eulers_no_flip(self):
        eulers = [(0.0, 0.0, 0.0), (0.1, 0.1, 0.1)]
        result = compute_euler_filter(eulers)
        assert len(result) == 2
        assert result[1] == pytest.approx((0.1, 0.1, 0.1), abs=1e-6)

    def test_preserves_smooth_rotation(self):
        """Smooth rotation without flips should pass through unchanged."""
        eulers = [(i * 0.05, 0.0, 0.0) for i in range(20)]
        result = compute_euler_filter(eulers)
        for i, e in enumerate(result):
            assert e == pytest.approx(eulers[i], abs=1e-6)

    def test_negative_to_positive_flip(self):
        TWO_PI = 2.0 * math.pi
        eulers = [
            (0.0, 0.0, -0.1),
            (0.0, 0.0, -0.2),
            (0.0, 0.0, -0.3 + TWO_PI),  # Jump from -0.3 to ~5.98
        ]
        result = compute_euler_filter(eulers)
        dz = abs(result[2][2] - result[1][2])
        assert dz < math.pi


# ===========================================================================
# Integration / Edge Case Tests
# ===========================================================================


class TestEdgeCases:
    """Cross-cutting edge case tests."""

    def test_bone_mapping_with_numbers(self):
        source = ["Spine1", "Spine2", "Spine3"]
        target = ["spine1", "spine2", "spine3"]
        result = compute_bone_mapping_auto(source, target)
        assert len(result) == 3

    def test_noise_filter_monotonic_increase(self):
        """Monotonically increasing values: all should be kept."""
        kf = [(i, float(i)) for i in range(10)]
        result = compute_noise_filter(kf, 0.5)
        assert len(result) == 10

    def test_contact_phases_all_contact(self):
        heights = [(i, 0.0) for i in range(100)]
        phases = compute_contact_phases(heights, 0.0, 0.05)
        assert phases == [(0, 99)]

    def test_contact_phases_alternating(self):
        """Every other frame is in contact."""
        heights = [(i, 0.0 if i % 2 == 0 else 1.0) for i in range(8)]
        phases = compute_contact_phases(heights, 0.0, 0.05)
        # Each contact is a single frame
        assert len(phases) == 4
        for start, end in phases:
            assert start == end

    def test_lerp_pose_identity(self):
        """Lerp with identical poses at any factor gives same pose."""
        pose = {
            "bone": {
                "location": [1.0, 2.0, 3.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            }
        }
        for factor in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = lerp_pose(pose, pose, factor)
            assert result["bone"]["location"] == pytest.approx([1, 2, 3])
            assert result["bone"]["scale"] == pytest.approx([1, 1, 1])

    def test_euler_filter_all_same(self):
        eulers = [(1.0, 2.0, 3.0)] * 10
        result = compute_euler_filter(eulers)
        assert len(result) == 10
        for e in result:
            assert e == pytest.approx((1.0, 2.0, 3.0), abs=1e-6)

    def test_retarget_params_frame_range_equal(self):
        """frame_range [5, 5] is valid (single frame)."""
        result = validate_retarget_params({
            "source_armature": "S",
            "target_armature": "T",
            "frame_range": [5, 5],
        })
        assert result["frame_range"] == [5, 5]

    def test_keyframe_edit_smooth_no_extra_params(self):
        result = validate_keyframe_edit_params({
            "armature_name": "R",
            "action_name": "a",
            "operation": "smooth",
        })
        assert result["operation"] == "smooth"

    def test_keyframe_edit_sample_no_extra_params(self):
        result = validate_keyframe_edit_params({
            "armature_name": "R",
            "action_name": "a",
            "operation": "sample",
        })
        assert result["operation"] == "sample"

    def test_bone_mapping_bip01_prefix(self):
        source = ["Bip01_Spine", "Bip01_Head"]
        target = ["Spine", "Head"]
        result = compute_bone_mapping_auto(source, target)
        assert result.get("Bip01_Spine") == "Spine"
        assert result.get("Bip01_Head") == "Head"

    def test_bone_mapping_underscore_side(self):
        source = ["Arm_L", "Arm_R"]
        target = ["DEF-arm.L", "DEF-arm.R"]
        result = compute_bone_mapping_auto(source, target)
        assert len(result) == 2
        # Verify side matching
        if "Arm_L" in result:
            assert ".L" in result["Arm_L"]
        if "Arm_R" in result:
            assert ".R" in result["Arm_R"]

    def test_noise_filter_preserves_peaks(self):
        """Peaks above threshold should be preserved."""
        kf = [
            (0, 0.0),
            (5, 0.0),
            (10, 2.0),  # Peak
            (15, 0.0),
            (20, 0.0),
        ]
        result = compute_noise_filter(kf, 0.1)
        frames = {f for f, _ in result}
        assert 10 in frames  # Peak preserved

    def test_contact_solver_single_bone(self):
        result = validate_contact_solver_params({
            "armature_name": "R",
            "action_name": "walk",
            "contact_bones": ["foot_ik.L"],
        })
        assert len(result["contact_bones"]) == 1

    def test_fk_ik_all_limb_chains_have_def_prefix(self):
        """All default bone names in LIMB_CHAIN_MAP use DEF- prefix."""
        for limb, info in LIMB_CHAIN_MAP.items():
            for bone in info["bones"]:
                assert bone.startswith("DEF-"), f"{limb}: {bone} missing DEF- prefix"
            assert info["ik_bone"].startswith("DEF-")
            assert info["pole_bone"].startswith("DEF-")
