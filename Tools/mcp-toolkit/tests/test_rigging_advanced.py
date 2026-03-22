"""Unit tests for advanced rigging handler pure-logic functions and data structures.

Tests FACIAL_BONES, MONSTER_EXPRESSIONS, RAGDOLL_PRESETS, and all five
validation functions from rigging_advanced.py -- all pure-logic, no Blender required.

Separate file from test_rigging_handlers.py to avoid conflicts with Plan 02.
"""

import math

import pytest


# ---------------------------------------------------------------------------
# TestFacialRig
# ---------------------------------------------------------------------------


class TestFacialRig:
    """Test FACIAL_BONES data structure for facial rig bone definitions."""

    def test_facial_bones_has_at_least_15_bones(self):
        """FACIAL_BONES has at least 15 bone definitions."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert len(FACIAL_BONES) >= 15

    def test_facial_bones_has_jaw(self):
        """FACIAL_BONES contains jaw bone."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "jaw" in FACIAL_BONES

    def test_facial_bones_has_lip_upper(self):
        """FACIAL_BONES contains lip_upper bone."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "lip_upper" in FACIAL_BONES

    def test_facial_bones_has_lip_lower(self):
        """FACIAL_BONES contains lip_lower bone."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "lip_lower" in FACIAL_BONES

    def test_facial_bones_has_eyelid_bones(self):
        """FACIAL_BONES contains eyelid upper and lower bones."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "eyelid_upper.L" in FACIAL_BONES
        assert "eyelid_upper.R" in FACIAL_BONES
        assert "eyelid_lower.L" in FACIAL_BONES
        assert "eyelid_lower.R" in FACIAL_BONES

    def test_facial_bones_has_brow_bones(self):
        """FACIAL_BONES contains brow inner, mid, outer bones."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "brow_inner.L" in FACIAL_BONES
        assert "brow_inner.R" in FACIAL_BONES
        assert "brow_mid.L" in FACIAL_BONES
        assert "brow_mid.R" in FACIAL_BONES
        assert "brow_outer.L" in FACIAL_BONES
        assert "brow_outer.R" in FACIAL_BONES

    def test_facial_bones_has_cheek_bones(self):
        """FACIAL_BONES contains cheek bones."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "cheek.L" in FACIAL_BONES
        assert "cheek.R" in FACIAL_BONES

    def test_facial_bones_has_lip_corners(self):
        """FACIAL_BONES contains lip corner bones."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "lip_corner.L" in FACIAL_BONES
        assert "lip_corner.R" in FACIAL_BONES

    def test_all_bones_have_required_keys(self):
        """Every facial bone has head, tail, roll, parent keys."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        required = {"head", "tail", "roll", "parent"}
        for bone_name, bone_def in FACIAL_BONES.items():
            missing = required - set(bone_def.keys())
            assert not missing, (
                f"Bone '{bone_name}' missing keys: {missing}"
            )

    def test_bone_positions_are_3_tuples(self):
        """Bone head and tail are 3-element tuples of numbers."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        for bone_name, bone_def in FACIAL_BONES.items():
            for key in ("head", "tail"):
                pos = bone_def[key]
                assert len(pos) == 3, f"Bone '{bone_name}' {key} has {len(pos)} elements"
                for i, val in enumerate(pos):
                    assert isinstance(val, (int, float)), (
                        f"Bone '{bone_name}' {key}[{i}] is {type(val).__name__}"
                    )

    def test_bone_roll_is_numeric(self):
        """Bone roll is a numeric value."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        for bone_name, bone_def in FACIAL_BONES.items():
            assert isinstance(bone_def["roll"], (int, float)), (
                f"Bone '{bone_name}' roll is {type(bone_def['roll']).__name__}"
            )

    def test_lr_symmetry_for_paired_bones(self):
        """Bones with .L suffix have a .R counterpart and vice versa."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        for bone_name in FACIAL_BONES:
            if bone_name.endswith(".L"):
                mirror = bone_name[:-2] + ".R"
                assert mirror in FACIAL_BONES, (
                    f"Bone '{bone_name}' has no mirror '{mirror}'"
                )
            elif bone_name.endswith(".R"):
                mirror = bone_name[:-2] + ".L"
                assert mirror in FACIAL_BONES, (
                    f"Bone '{bone_name}' has no mirror '{mirror}'"
                )

    def test_lr_pairs_have_mirrored_x_positions(self):
        """L/R bone pairs have mirrored X positions (opposite sign)."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        for bone_name, bone_def in FACIAL_BONES.items():
            if not bone_name.endswith(".L"):
                continue
            mirror = bone_name[:-2] + ".R"
            mirror_def = FACIAL_BONES[mirror]
            # Head X should be negated
            assert abs(bone_def["head"][0] + mirror_def["head"][0]) < 0.001, (
                f"'{bone_name}' and '{mirror}' head X not mirrored"
            )
            # Tail X should be negated
            assert abs(bone_def["tail"][0] + mirror_def["tail"][0]) < 0.001, (
                f"'{bone_name}' and '{mirror}' tail X not mirrored"
            )

    def test_jaw_parent_is_head(self):
        """Jaw bone's parent is 'head'."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert FACIAL_BONES["jaw"]["parent"] == "head"

    def test_lip_lower_parent_is_jaw(self):
        """Lower lip parent is jaw (moves with jaw opening)."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert FACIAL_BONES["lip_lower"]["parent"] == "jaw"

    def test_lip_upper_parent_is_head(self):
        """Upper lip parent is head (stays fixed when jaw opens)."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert FACIAL_BONES["lip_upper"]["parent"] == "head"


# ---------------------------------------------------------------------------
# TestMonsterExpressions
# ---------------------------------------------------------------------------


class TestMonsterExpressions:
    """Test MONSTER_EXPRESSIONS preset dict."""

    def test_has_snarl(self):
        """MONSTER_EXPRESSIONS contains 'snarl' preset."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        assert "snarl" in MONSTER_EXPRESSIONS

    def test_has_hiss(self):
        """MONSTER_EXPRESSIONS contains 'hiss' preset."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        assert "hiss" in MONSTER_EXPRESSIONS

    def test_has_roar(self):
        """MONSTER_EXPRESSIONS contains 'roar' preset."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        assert "roar" in MONSTER_EXPRESSIONS

    def test_snarl_has_bone_transforms(self):
        """Snarl expression has at least one bone transform."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        assert len(MONSTER_EXPRESSIONS["snarl"]) >= 1

    def test_hiss_has_bone_transforms(self):
        """Hiss expression has at least one bone transform."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        assert len(MONSTER_EXPRESSIONS["hiss"]) >= 1

    def test_roar_has_bone_transforms(self):
        """Roar expression has at least one bone transform."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        assert len(MONSTER_EXPRESSIONS["roar"]) >= 1

    def test_all_expression_bones_in_facial_bones(self):
        """All bones referenced in expressions exist in FACIAL_BONES."""
        from blender_addon.handlers.rigging_advanced import (
            FACIAL_BONES,
            MONSTER_EXPRESSIONS,
        )
        for expr_name, transforms in MONSTER_EXPRESSIONS.items():
            for bone_name in transforms:
                assert bone_name in FACIAL_BONES, (
                    f"Expression '{expr_name}' references bone '{bone_name}' "
                    "not in FACIAL_BONES"
                )

    def test_transforms_have_valid_format(self):
        """Each bone transform has 'location' or 'rotation' with 3-element tuples."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        for expr_name, transforms in MONSTER_EXPRESSIONS.items():
            for bone_name, transform in transforms.items():
                assert isinstance(transform, dict), (
                    f"Expression '{expr_name}', bone '{bone_name}': "
                    "transform must be a dict"
                )
                assert "location" in transform or "rotation" in transform, (
                    f"Expression '{expr_name}', bone '{bone_name}': "
                    "must have 'location' or 'rotation'"
                )
                for key in ("location", "rotation"):
                    if key in transform:
                        val = transform[key]
                        assert len(val) == 3, (
                            f"Expression '{expr_name}', bone '{bone_name}', "
                            f"'{key}' must have 3 elements"
                        )
                        for i, v in enumerate(val):
                            assert isinstance(v, (int, float)), (
                                f"Expression '{expr_name}', bone '{bone_name}', "
                                f"'{key}[{i}]' must be numeric"
                            )

    def test_roar_opens_jaw(self):
        """Roar expression includes jaw rotation (opens the mouth)."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        roar = MONSTER_EXPRESSIONS["roar"]
        assert "jaw" in roar
        assert "rotation" in roar["jaw"]
        # Negative X rotation opens the jaw
        assert roar["jaw"]["rotation"][0] < 0

    def test_hiss_opens_jaw(self):
        """Hiss expression includes jaw rotation."""
        from blender_addon.handlers.rigging_advanced import MONSTER_EXPRESSIONS
        hiss = MONSTER_EXPRESSIONS["hiss"]
        assert "jaw" in hiss
        assert "rotation" in hiss["jaw"]


# ---------------------------------------------------------------------------
# TestIKParams
# ---------------------------------------------------------------------------


class TestIKParams:
    """Test _validate_ik_params validation function."""

    def test_valid_standard_ik(self):
        """Valid standard IK params pass validation."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "hand.L",
            "chain_length": 2,
            "constraint_type": "IK",
            "pole_angle": 0.0,
        })
        assert result["valid"] is True
        assert result["errors"] == []

    def test_valid_spline_ik(self):
        """Valid SPLINE_IK params pass validation."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "tail.003",
            "chain_length": 4,
            "constraint_type": "SPLINE_IK",
            "pole_angle": 0.0,
            "curve_points": 5,
        })
        assert result["valid"] is True
        assert result["errors"] == []

    def test_chain_length_zero_invalid(self):
        """chain_length of 0 is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "hand.L",
            "chain_length": 0,
            "constraint_type": "IK",
        })
        assert result["valid"] is False
        assert any("chain_length" in e for e in result["errors"])

    def test_chain_length_21_invalid(self):
        """chain_length of 21 is invalid (max 20)."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "hand.L",
            "chain_length": 21,
            "constraint_type": "IK",
        })
        assert result["valid"] is False
        assert any("chain_length" in e for e in result["errors"])

    def test_missing_bone_name(self):
        """Missing bone_name is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "chain_length": 2,
            "constraint_type": "IK",
        })
        assert result["valid"] is False
        assert any("bone_name" in e for e in result["errors"])

    def test_empty_bone_name(self):
        """Empty bone_name is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "",
            "chain_length": 2,
            "constraint_type": "IK",
        })
        assert result["valid"] is False
        assert any("bone_name" in e for e in result["errors"])

    def test_spline_ik_without_curve_points(self):
        """SPLINE_IK without curve_points is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "tail.003",
            "chain_length": 4,
            "constraint_type": "SPLINE_IK",
            "curve_points": 1,
        })
        assert result["valid"] is False
        assert any("curve_points" in e for e in result["errors"])

    def test_invalid_constraint_type(self):
        """Invalid constraint_type is rejected."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "hand.L",
            "chain_length": 2,
            "constraint_type": "FAKE_IK",
        })
        assert result["valid"] is False
        assert any("constraint_type" in e for e in result["errors"])

    def test_chain_length_1_valid(self):
        """chain_length of 1 is valid (minimum)."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "hand.L",
            "chain_length": 1,
            "constraint_type": "IK",
        })
        assert result["valid"] is True

    def test_chain_length_20_valid(self):
        """chain_length of 20 is valid (maximum)."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "spine.010",
            "chain_length": 20,
            "constraint_type": "IK",
        })
        assert result["valid"] is True

    def test_returns_required_keys(self):
        """Result has valid and errors keys."""
        from blender_addon.handlers.rigging_advanced import _validate_ik_params
        result = _validate_ik_params({
            "bone_name": "hand.L",
            "chain_length": 2,
            "constraint_type": "IK",
        })
        assert "valid" in result
        assert "errors" in result


# ---------------------------------------------------------------------------
# TestSpringParams
# ---------------------------------------------------------------------------


class TestSpringParams:
    """Test _validate_spring_params validation function."""

    def test_valid_params(self):
        """Valid spring params pass validation."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["tail.001", "tail.002", "tail.003"],
            stiffness=0.5,
            damping=0.3,
            gravity=1.0,
        )
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["bone_count"] == 3

    def test_empty_bone_names_invalid(self):
        """Empty bone_names list is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=[],
            stiffness=0.5,
            damping=0.3,
            gravity=1.0,
        )
        assert result["valid"] is False
        assert any("bone_names" in e for e in result["errors"])

    def test_stiffness_above_1_invalid(self):
        """stiffness > 1 is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["tail.001"],
            stiffness=1.5,
            damping=0.3,
            gravity=1.0,
        )
        assert result["valid"] is False
        assert any("stiffness" in e for e in result["errors"])

    def test_stiffness_below_0_invalid(self):
        """stiffness < 0 is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["tail.001"],
            stiffness=-0.1,
            damping=0.3,
            gravity=1.0,
        )
        assert result["valid"] is False
        assert any("stiffness" in e for e in result["errors"])

    def test_damping_above_1_invalid(self):
        """damping > 1 is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["tail.001"],
            stiffness=0.5,
            damping=1.5,
            gravity=1.0,
        )
        assert result["valid"] is False
        assert any("damping" in e for e in result["errors"])

    def test_negative_gravity_invalid(self):
        """Negative gravity is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["tail.001"],
            stiffness=0.5,
            damping=0.3,
            gravity=-1.0,
        )
        assert result["valid"] is False
        assert any("gravity" in e for e in result["errors"])

    def test_zero_gravity_valid(self):
        """Gravity of 0 is valid (zero-g environment)."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["hair.001"],
            stiffness=0.5,
            damping=0.3,
            gravity=0.0,
        )
        assert result["valid"] is True

    def test_boundary_stiffness_damping_valid(self):
        """Stiffness=1.0 and damping=1.0 are valid boundary values."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["cape.001"],
            stiffness=1.0,
            damping=1.0,
            gravity=0.5,
        )
        assert result["valid"] is True

    def test_bone_count_matches_input(self):
        """bone_count in result matches input list length."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["a", "b", "c", "d"],
            stiffness=0.5,
            damping=0.3,
            gravity=1.0,
        )
        assert result["bone_count"] == 4

    def test_returns_required_keys(self):
        """Result has valid, errors, bone_count keys."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_params
        result = _validate_spring_params(
            bone_names=["tail.001"],
            stiffness=0.5,
            damping=0.3,
            gravity=1.0,
        )
        assert "valid" in result
        assert "errors" in result
        assert "bone_count" in result


# ---------------------------------------------------------------------------
# TestRagdollSpec
# ---------------------------------------------------------------------------


class TestRagdollSpec:
    """Test _validate_ragdoll_spec validation function."""

    def test_valid_capsule_spec(self):
        """Valid CAPSULE collider spec passes."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE",
                "radius": 0.1,
                "length": 0.3,
                "mass": 5.0,
            },
        })
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["collider_count"] == 1

    def test_valid_box_spec(self):
        """Valid BOX collider spec passes."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-head": {
                "shape": "BOX",
                "radius": 0.1,
                "length": 0.15,
                "mass": 3.0,
            },
        })
        assert result["valid"] is True

    def test_invalid_shape(self):
        """Invalid shape type is rejected."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "SPHERE",
                "radius": 0.1,
                "length": 0.3,
                "mass": 5.0,
            },
        })
        assert result["valid"] is False
        assert any("shape" in e for e in result["errors"])

    def test_mass_zero_invalid(self):
        """Mass of 0 is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE",
                "radius": 0.1,
                "length": 0.3,
                "mass": 0.0,
            },
        })
        assert result["valid"] is False
        assert any("mass" in e for e in result["errors"])

    def test_negative_mass_invalid(self):
        """Negative mass is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE",
                "radius": 0.1,
                "length": 0.3,
                "mass": -1.0,
            },
        })
        assert result["valid"] is False
        assert any("mass" in e for e in result["errors"])

    def test_missing_required_fields(self):
        """Missing required fields are reported."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE",
            },
        })
        assert result["valid"] is False
        assert any("missing" in e for e in result["errors"])

    def test_empty_map_invalid(self):
        """Empty bone_collider_map is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({})
        assert result["valid"] is False
        assert result["collider_count"] == 0

    def test_multiple_colliders_counted(self):
        """Multiple collider entries are counted correctly."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE", "radius": 0.1, "length": 0.3, "mass": 5.0,
            },
            "DEF-head": {
                "shape": "BOX", "radius": 0.1, "length": 0.15, "mass": 3.0,
            },
        })
        assert result["valid"] is True
        assert result["collider_count"] == 2

    def test_zero_radius_invalid(self):
        """Zero radius is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE",
                "radius": 0.0,
                "length": 0.3,
                "mass": 5.0,
            },
        })
        assert result["valid"] is False
        assert any("radius" in e for e in result["errors"])

    def test_valid_joint_angles(self):
        """Collider with valid joint angle limits passes."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE",
                "radius": 0.1,
                "length": 0.3,
                "mass": 5.0,
                "ang_x_min": -0.5,
                "ang_x_max": 0.5,
            },
        })
        assert result["valid"] is True

    def test_ragdoll_presets_humanoid_valid(self):
        """RAGDOLL_PRESETS humanoid preset passes validation."""
        from blender_addon.handlers.rigging_advanced import (
            RAGDOLL_PRESETS,
            _validate_ragdoll_spec,
        )
        result = _validate_ragdoll_spec(RAGDOLL_PRESETS["humanoid"])
        assert result["valid"] is True
        assert result["collider_count"] >= 5

    def test_returns_required_keys(self):
        """Result has valid, errors, collider_count keys."""
        from blender_addon.handlers.rigging_advanced import _validate_ragdoll_spec
        result = _validate_ragdoll_spec({
            "DEF-spine": {
                "shape": "CAPSULE", "radius": 0.1, "length": 0.3, "mass": 5.0,
            },
        })
        assert "valid" in result
        assert "errors" in result
        assert "collider_count" in result


# ---------------------------------------------------------------------------
# TestRetargetMapping
# ---------------------------------------------------------------------------


class TestRetargetMapping:
    """Test _validate_retarget_mapping validation function."""

    def test_valid_mapping(self):
        """Valid mapping with all bones existing passes."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["spine", "head", "arm.L", "arm.R"],
            target_bones=["Spine", "Head", "LeftArm", "RightArm"],
            mapping={
                "spine": "Spine",
                "head": "Head",
                "arm.L": "LeftArm",
                "arm.R": "RightArm",
            },
        )
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["mapped_count"] == 4
        assert result["unmapped_source"] == []
        assert result["unmapped_target"] == []

    def test_source_bone_not_in_list(self):
        """Source bone referenced in mapping but not in source_bones is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["spine", "head"],
            target_bones=["Spine", "Head", "LeftArm"],
            mapping={
                "spine": "Spine",
                "arm.L": "LeftArm",  # arm.L not in source_bones
            },
        )
        assert result["valid"] is False
        assert any("arm.L" in e for e in result["errors"])

    def test_target_bone_not_in_list(self):
        """Target bone referenced in mapping but not in target_bones is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["spine", "head", "arm.L"],
            target_bones=["Spine", "Head"],
            mapping={
                "spine": "Spine",
                "arm.L": "LeftArm",  # LeftArm not in target_bones
            },
        )
        assert result["valid"] is False
        assert any("LeftArm" in e for e in result["errors"])

    def test_empty_mapping_invalid(self):
        """Empty mapping dict is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["spine", "head"],
            target_bones=["Spine", "Head"],
            mapping={},
        )
        assert result["valid"] is False
        assert result["mapped_count"] == 0

    def test_partial_mapping_reports_unmapped(self):
        """Partial mapping reports unmapped source and target bones."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["spine", "head", "arm.L", "arm.R"],
            target_bones=["Spine", "Head", "LeftArm", "RightArm"],
            mapping={
                "spine": "Spine",
                "head": "Head",
            },
        )
        assert result["valid"] is True
        assert result["mapped_count"] == 2
        assert "arm.L" in result["unmapped_source"]
        assert "arm.R" in result["unmapped_source"]
        assert "LeftArm" in result["unmapped_target"]
        assert "RightArm" in result["unmapped_target"]

    def test_returns_required_keys(self):
        """Result has valid, errors, mapped_count, unmapped_source, unmapped_target."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["a"],
            target_bones=["b"],
            mapping={"a": "b"},
        )
        required = {"valid", "errors", "mapped_count", "unmapped_source", "unmapped_target"}
        assert required.issubset(set(result.keys()))

    def test_mapped_count_correct(self):
        """mapped_count reflects number of entries in mapping."""
        from blender_addon.handlers.rigging_advanced import _validate_retarget_mapping
        result = _validate_retarget_mapping(
            source_bones=["a", "b", "c"],
            target_bones=["x", "y", "z"],
            mapping={"a": "x", "b": "y"},
        )
        assert result["mapped_count"] == 2


# ---------------------------------------------------------------------------
# TestShapeKeyParams
# ---------------------------------------------------------------------------


class TestShapeKeyParams:
    """Test _validate_shape_key_params validation function."""

    def test_valid_params(self):
        """Valid name and vertex offsets pass."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="snarl_expression",
            vertex_offsets={
                0: (0.01, 0.0, 0.005),
                5: (0.0, 0.02, 0.0),
                12: (-0.005, 0.0, 0.01),
            },
        )
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["vertex_count"] == 3

    def test_empty_name_invalid(self):
        """Empty name is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="",
            vertex_offsets={0: (0.01, 0.0, 0.0)},
        )
        assert result["valid"] is False
        assert any("name" in e for e in result["errors"])

    def test_name_with_special_chars_invalid(self):
        """Name with special characters (other than _ and -) is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="snarl expression!",
            vertex_offsets={0: (0.01, 0.0, 0.0)},
        )
        assert result["valid"] is False
        assert any("name" in e for e in result["errors"])

    def test_name_with_underscore_hyphen_valid(self):
        """Name with underscores and hyphens is valid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="snarl_expression-v2",
            vertex_offsets={0: (0.01, 0.0, 0.0)},
        )
        assert result["valid"] is True

    def test_negative_vertex_index_invalid(self):
        """Negative vertex index is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={-1: (0.01, 0.0, 0.0)},
        )
        assert result["valid"] is False
        assert any("vertex index" in e for e in result["errors"])

    def test_wrong_tuple_length_invalid(self):
        """Vertex offset with wrong number of elements is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={0: (0.01, 0.0)},  # Only 2 elements
        )
        assert result["valid"] is False
        assert any("3 elements" in e for e in result["errors"])

    def test_non_numeric_offset_invalid(self):
        """Non-numeric offset value is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={0: ("a", 0.0, 0.0)},
        )
        assert result["valid"] is False
        assert any("number" in e for e in result["errors"])

    def test_empty_offsets_invalid(self):
        """Empty vertex_offsets dict is invalid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={},
        )
        assert result["valid"] is False
        assert any("empty" in e for e in result["errors"])

    def test_vertex_count_matches_valid_indices(self):
        """vertex_count counts only valid non-negative int indices."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={
                0: (0.01, 0.0, 0.0),
                5: (0.0, 0.02, 0.0),
            },
        )
        assert result["vertex_count"] == 2

    def test_list_offset_valid(self):
        """Vertex offset as a list (not just tuple) is valid."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={0: [0.01, 0.0, 0.0]},
        )
        assert result["valid"] is True

    def test_returns_required_keys(self):
        """Result has valid, errors, vertex_count keys."""
        from blender_addon.handlers.rigging_advanced import _validate_shape_key_params
        result = _validate_shape_key_params(
            name="test",
            vertex_offsets={0: (0.01, 0.0, 0.0)},
        )
        assert "valid" in result
        assert "errors" in result
        assert "vertex_count" in result


# ---------------------------------------------------------------------------
# TestFACSActionUnits
# ---------------------------------------------------------------------------


class TestFACSActionUnits:
    """Test FACS_ACTION_UNITS data structure."""

    def test_has_17_units(self):
        """FACS_ACTION_UNITS has exactly 17 entries."""
        from blender_addon.handlers.rigging_advanced import FACS_ACTION_UNITS
        assert len(FACS_ACTION_UNITS) == 17

    def test_all_bones_in_facial(self):
        """All bones referenced in FACS units exist in FACIAL_BONES."""
        from blender_addon.handlers.rigging_advanced import FACS_ACTION_UNITS, FACIAL_BONES
        for au_code, au_def in FACS_ACTION_UNITS.items():
            for bone in au_def["bones"]:
                assert bone in FACIAL_BONES, (
                    f"FACS {au_code} references bone '{bone}' not in FACIAL_BONES"
                )

    def test_valid_format(self):
        """Each entry has 'name' (str) and 'bones' (list)."""
        from blender_addon.handlers.rigging_advanced import FACS_ACTION_UNITS
        for au_code, au_def in FACS_ACTION_UNITS.items():
            assert isinstance(au_def["name"], str), f"{au_code} name not str"
            assert isinstance(au_def["bones"], list), f"{au_code} bones not list"


# ---------------------------------------------------------------------------
# TestVisemeShapes
# ---------------------------------------------------------------------------


class TestVisemeShapes:
    """Test VISEME_SHAPES data structure."""

    def test_has_15_visemes(self):
        """VISEME_SHAPES has exactly 15 entries."""
        from blender_addon.handlers.rigging_advanced import VISEME_SHAPES
        assert len(VISEME_SHAPES) == 15

    def test_expected_names(self):
        """VISEME_SHAPES contains expected phoneme codes."""
        from blender_addon.handlers.rigging_advanced import VISEME_SHAPES
        expected = {"sil", "PP", "FF", "TH", "DD", "kk", "CH", "SS", "nn", "RR", "aa", "E", "I", "O", "U"}
        assert set(VISEME_SHAPES.keys()) == expected

    def test_sil_empty(self):
        """Silence viseme has empty bones list."""
        from blender_addon.handlers.rigging_advanced import VISEME_SHAPES
        assert VISEME_SHAPES["sil"]["bones"] == []


# ---------------------------------------------------------------------------
# TestEyeTracking
# ---------------------------------------------------------------------------


class TestEyeTracking:
    """Test eye tracking bones in FACIAL_BONES."""

    def test_has_eye_bones(self):
        """FACIAL_BONES has eye.L and eye.R."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "eye.L" in FACIAL_BONES
        assert "eye.R" in FACIAL_BONES

    def test_has_eye_target(self):
        """FACIAL_BONES has eye_target bone."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert "eye_target" in FACIAL_BONES

    def test_eye_target_parent(self):
        """eye_target parent is head."""
        from blender_addon.handlers.rigging_advanced import FACIAL_BONES
        assert FACIAL_BONES["eye_target"]["parent"] == "head"


# ---------------------------------------------------------------------------
# TestFacialRigValidation
# ---------------------------------------------------------------------------


class TestFacialRigValidation:
    """Test _validate_facial_rig_params."""

    def test_valid_params(self):
        """Valid expressions, FACS units, and visemes pass."""
        from blender_addon.handlers.rigging_advanced import _validate_facial_rig_params
        result = _validate_facial_rig_params({
            "expressions": ["roar", "snarl"],
            "facs_units": ["AU01", "AU26"],
            "visemes": ["aa", "O"],
        })
        assert result["valid"] is True
        assert result["errors"] == []

    def test_invalid_expression(self):
        """Unknown expression name fails."""
        from blender_addon.handlers.rigging_advanced import _validate_facial_rig_params
        result = _validate_facial_rig_params({
            "expressions": ["nonexistent_expr"],
        })
        assert result["valid"] is False
        assert any("nonexistent_expr" in e for e in result["errors"])

    def test_invalid_facs(self):
        """Unknown FACS unit fails."""
        from blender_addon.handlers.rigging_advanced import _validate_facial_rig_params
        result = _validate_facial_rig_params({
            "facs_units": ["AU99"],
        })
        assert result["valid"] is False
        assert any("AU99" in e for e in result["errors"])

    def test_invalid_viseme(self):
        """Unknown viseme fails."""
        from blender_addon.handlers.rigging_advanced import _validate_facial_rig_params
        result = _validate_facial_rig_params({
            "visemes": ["ZZ"],
        })
        assert result["valid"] is False
        assert any("ZZ" in e for e in result["errors"])

    def test_returns_keys(self):
        """Result has valid and errors keys."""
        from blender_addon.handlers.rigging_advanced import _validate_facial_rig_params
        result = _validate_facial_rig_params({})
        assert "valid" in result
        assert "errors" in result


# ---------------------------------------------------------------------------
# TestSpringDynamics
# ---------------------------------------------------------------------------


class TestSpringDynamics:
    """Test _compute_spring_chain_forces and _validate_spring_dynamics_params."""

    def test_root_unchanged(self):
        """Root bone position is never modified."""
        from blender_addon.handlers.rigging_advanced import _compute_spring_chain_forces
        positions = [(0, 0, 1), (0, 0, 0.8), (0, 0, 0.6)]
        velocities = [(0, 0, 0), (0, 0, 0), (0, 0, 0)]
        result = _compute_spring_chain_forces(positions, velocities, 0.5, 0.3, 1.0)
        assert result[0] == (0, 0, 1)

    def test_gravity_pulls_down(self):
        """Non-root bones move downward under gravity."""
        from blender_addon.handlers.rigging_advanced import _compute_spring_chain_forces
        positions = [(0, 0, 1), (0, 0, 0.8)]
        velocities = [(0, 0, 0), (0, 0, 0)]
        result = _compute_spring_chain_forces(positions, velocities, 0.0, 0.0, 9.8)
        # With gravity and no stiffness, z should decrease
        assert result[1][2] < 0.8

    def test_correct_count(self):
        """Output has same count as input."""
        from blender_addon.handlers.rigging_advanced import _compute_spring_chain_forces
        positions = [(0, 0, 1), (0, 0, 0.8), (0, 0, 0.6), (0, 0, 0.4)]
        velocities = [(0, 0, 0)] * 4
        result = _compute_spring_chain_forces(positions, velocities, 0.5, 0.3, 1.0)
        assert len(result) == 4

    def test_valid_params(self):
        """Valid spring dynamics params pass."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_dynamics_params
        result = _validate_spring_dynamics_params(mass=1.0, stiffness=10.0, damping=0.5)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_invalid_mass(self):
        """Mass <= 0 fails."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_dynamics_params
        result = _validate_spring_dynamics_params(mass=0.0, stiffness=10.0, damping=0.5)
        assert result["valid"] is False
        assert any("mass" in e for e in result["errors"])

    def test_invalid_stiffness(self):
        """Stiffness <= 0 or > 100 fails."""
        from blender_addon.handlers.rigging_advanced import _validate_spring_dynamics_params
        result = _validate_spring_dynamics_params(mass=1.0, stiffness=0.0, damping=0.5)
        assert result["valid"] is False
        assert any("stiffness" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# TestCorrectiveShapes
# ---------------------------------------------------------------------------


class TestCorrectiveShapes:
    """Test CORRECTIVE_SHAPE_DEFS and _validate_corrective_shape_config."""

    def test_has_5_defs(self):
        """CORRECTIVE_SHAPE_DEFS has 5 entries."""
        from blender_addon.handlers.rigging_advanced import CORRECTIVE_SHAPE_DEFS
        assert len(CORRECTIVE_SHAPE_DEFS) == 5

    def test_valid_config(self):
        """Valid corrective shape config passes."""
        from blender_addon.handlers.rigging_advanced import _validate_corrective_shape_config
        result = _validate_corrective_shape_config({
            "joint": "shoulder",
            "axis": "x",
            "threshold": 45.0,
            "strength": 1.0,
        })
        assert result["valid"] is True
        assert result["errors"] == []

    def test_invalid_joint(self):
        """Unknown joint fails."""
        from blender_addon.handlers.rigging_advanced import _validate_corrective_shape_config
        result = _validate_corrective_shape_config({
            "joint": "ankle",
            "axis": "x",
            "threshold": 45.0,
            "strength": 1.0,
        })
        assert result["valid"] is False
        assert any("joint" in e for e in result["errors"])

    def test_invalid_axis(self):
        """Unknown axis fails."""
        from blender_addon.handlers.rigging_advanced import _validate_corrective_shape_config
        result = _validate_corrective_shape_config({
            "joint": "shoulder",
            "axis": "w",
            "threshold": 45.0,
            "strength": 1.0,
        })
        assert result["valid"] is False
        assert any("axis" in e for e in result["errors"])

    def test_invalid_threshold(self):
        """Threshold outside [0, 180] fails."""
        from blender_addon.handlers.rigging_advanced import _validate_corrective_shape_config
        result = _validate_corrective_shape_config({
            "joint": "shoulder",
            "axis": "x",
            "threshold": 200.0,
            "strength": 1.0,
        })
        assert result["valid"] is False
        assert any("threshold" in e for e in result["errors"])

    def test_invalid_strength(self):
        """Strength outside [0, 2] fails."""
        from blender_addon.handlers.rigging_advanced import _validate_corrective_shape_config
        result = _validate_corrective_shape_config({
            "joint": "shoulder",
            "axis": "x",
            "threshold": 45.0,
            "strength": 3.0,
        })
        assert result["valid"] is False
        assert any("strength" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# TestPoseSpaceDeformations
# ---------------------------------------------------------------------------


class TestPoseSpaceDeformations:
    def test_has_5_psds(self):
        from blender_addon.handlers.rigging_advanced import POSE_SPACE_DEFORMATIONS
        assert len(POSE_SPACE_DEFORMATIONS) == 5

    def test_valid_config(self):
        from blender_addon.handlers.rigging_advanced import _validate_psd_config
        r = _validate_psd_config(["upper_arm.L"], ["Z"], [60.0])
        assert r["valid"] is True

    def test_mismatched_lengths(self):
        from blender_addon.handlers.rigging_advanced import _validate_psd_config
        r = _validate_psd_config(["a", "b"], ["X"], [60.0])
        assert r["valid"] is False

    def test_invalid_axis(self):
        from blender_addon.handlers.rigging_advanced import _validate_psd_config
        r = _validate_psd_config(["a"], ["W"], [60.0])
        assert r["valid"] is False

    def test_invalid_threshold(self):
        from blender_addon.handlers.rigging_advanced import _validate_psd_config
        r = _validate_psd_config(["a"], ["X"], [0.0])
        assert r["valid"] is False

    def test_threshold_above_180(self):
        from blender_addon.handlers.rigging_advanced import _validate_psd_config
        r = _validate_psd_config(["a"], ["X"], [200.0])
        assert r["valid"] is False


# ---------------------------------------------------------------------------
# TestARKitMapping
# ---------------------------------------------------------------------------


class TestARKitMapping:
    def test_has_52_blendshapes(self):
        from blender_addon.handlers.rigging_advanced import ARKIT_BLENDSHAPE_MAP
        assert len(ARKIT_BLENDSHAPE_MAP) == 52

    def test_all_bones_in_facial(self):
        from blender_addon.handlers.rigging_advanced import ARKIT_BLENDSHAPE_MAP, FACIAL_BONES
        for shape, bones in ARKIT_BLENDSHAPE_MAP.items():
            for bone in bones:
                assert bone in FACIAL_BONES, f"ARKit '{shape}' references '{bone}' not in FACIAL_BONES"
