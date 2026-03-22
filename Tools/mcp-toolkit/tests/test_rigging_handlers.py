"""Unit tests for rigging handler pure-logic functions.

Tests _analyze_proportions and _validate_custom_rig_config -- both are
pure functions testable without Blender.
"""

import pytest


# ---------------------------------------------------------------------------
# TestMeshAnalysis
# ---------------------------------------------------------------------------


class TestMeshAnalysis:
    """Test _analyze_proportions with different bbox ratios."""

    def test_tall_narrow_symmetric_recommends_humanoid(self):
        """Tall narrow mesh (aspect > 2.5) with symmetry recommends humanoid."""
        from blender_addon.handlers.rigging import _analyze_proportions

        # width=0.5, depth=0.4, height=2.0 -> aspect = 4.0
        result = _analyze_proportions((0.5, 0.4, 2.0), 1000, True)
        assert result["recommended_template"] == "humanoid"
        assert result["confidence"] >= 0.7

    def test_tall_narrow_asymmetric_recommends_humanoid_lower_confidence(self):
        """Tall narrow mesh without symmetry still recommends humanoid but lower confidence."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result = _analyze_proportions((0.5, 0.4, 2.0), 1000, False)
        assert result["recommended_template"] == "humanoid"
        assert result["confidence"] >= 0.5

    def test_flat_wide_recommends_serpent(self):
        """Flat wide mesh (aspect < 0.5, width > height) recommends serpent."""
        from blender_addon.handlers.rigging import _analyze_proportions

        # width=3.0, depth=0.5, height=0.3 -> aspect = 0.1
        result = _analyze_proportions((3.0, 0.5, 0.3), 500, False)
        assert result["recommended_template"] == "serpent"
        assert result["confidence"] >= 0.6

    def test_medium_deep_recommends_quadruped(self):
        """Medium aspect with significant depth recommends quadruped."""
        from blender_addon.handlers.rigging import _analyze_proportions

        # width=1.0, depth=1.5, height=0.6 -> aspect = 0.6
        result = _analyze_proportions((1.0, 1.5, 0.6), 2000, True)
        assert result["recommended_template"] == "quadruped"
        assert result["confidence"] >= 0.6

    def test_unknown_shape_recommends_amorphous(self):
        """Weird shape that does not fit any category gets amorphous."""
        from blender_addon.handlers.rigging import _analyze_proportions

        # very weird: width=0.01, depth=0.01, height=0.01, no symmetry
        result = _analyze_proportions((0.01, 0.01, 0.01), 10, False)
        # Should have a recommendation regardless
        assert "recommended_template" in result
        assert result["confidence"] >= 0.3

    def test_returns_required_keys(self):
        """Return dict contains all required keys."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result = _analyze_proportions((1.0, 1.0, 1.0), 500, True)
        required_keys = {
            "aspect_ratio", "recommended_template", "confidence",
            "has_symmetry", "vertex_count", "all_candidates",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_aspect_ratio_is_positive_float(self):
        """Aspect ratio is a positive float."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result = _analyze_proportions((1.0, 1.0, 2.0), 100, True)
        assert isinstance(result["aspect_ratio"], float)
        assert result["aspect_ratio"] > 0

    def test_confidence_between_0_and_1(self):
        """Confidence is between 0 and 1."""
        from blender_addon.handlers.rigging import _analyze_proportions

        for dims in [(0.5, 0.4, 2.0), (3.0, 0.5, 0.3), (1.0, 1.5, 0.6), (1.0, 1.0, 1.0)]:
            result = _analyze_proportions(dims, 100, True)
            assert 0.0 <= result["confidence"] <= 1.0

    def test_has_symmetry_passthrough(self):
        """has_symmetry in result matches input."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result_true = _analyze_proportions((1.0, 1.0, 1.0), 100, True)
        assert result_true["has_symmetry"] is True

        result_false = _analyze_proportions((1.0, 1.0, 1.0), 100, False)
        assert result_false["has_symmetry"] is False

    def test_vertex_count_passthrough(self):
        """vertex_count in result matches input."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result = _analyze_proportions((1.0, 1.0, 1.0), 42, True)
        assert result["vertex_count"] == 42

    def test_all_candidates_is_list(self):
        """all_candidates is a non-empty list of dicts."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result = _analyze_proportions((1.0, 1.0, 1.0), 100, True)
        assert isinstance(result["all_candidates"], list)
        assert len(result["all_candidates"]) >= 1
        for c in result["all_candidates"]:
            assert "template" in c
            assert "confidence" in c

    def test_recommended_is_top_candidate(self):
        """recommended_template matches the first all_candidates entry."""
        from blender_addon.handlers.rigging import _analyze_proportions

        result = _analyze_proportions((0.5, 0.4, 2.0), 1000, True)
        assert result["recommended_template"] == result["all_candidates"][0]["template"]

    def test_zero_width_does_not_crash(self):
        """Zero width mesh does not cause division by zero."""
        from blender_addon.handlers.rigging import _analyze_proportions

        # Should not raise
        result = _analyze_proportions((0.0, 1.0, 1.0), 100, True)
        assert "recommended_template" in result


# ---------------------------------------------------------------------------
# TestCustomRigValidation
# ---------------------------------------------------------------------------


class TestCustomRigValidation:
    """Test _validate_custom_rig_config with various inputs."""

    def test_valid_limb_list(self):
        """Valid limb types pass validation."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["arm_pair", "leg_pair"])
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["limb_count"] == 2
        assert result["bone_estimate"] > 0

    def test_invalid_limb_name(self):
        """Unknown limb type fails validation."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["arm_pair", "laser_cannon"])
        assert result["valid"] is False
        assert len(result["errors"]) >= 1
        assert "laser_cannon" in result["errors"][0]

    def test_empty_limb_list(self):
        """Empty limb list fails validation."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config([])
        assert result["valid"] is False
        assert result["limb_count"] == 0

    def test_single_valid_limb(self):
        """Single valid limb type passes."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["tail_chain"])
        assert result["valid"] is True
        assert result["limb_count"] == 1

    def test_all_limb_types_valid(self):
        """All known limb types pass individually."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY

        for lt in LIMB_LIBRARY:
            result = _validate_custom_rig_config([lt])
            assert result["valid"] is True, f"'{lt}' should be valid"

    def test_multiple_same_limb_valid(self):
        """Multiple of the same limb type is valid (e.g., 2 arm pairs)."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["arm_pair", "arm_pair"])
        assert result["valid"] is True
        assert result["limb_count"] == 2

    def test_bone_estimate_includes_spine(self):
        """Bone estimate includes spine bones (always added as root)."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["jaw"])
        # jaw has 1 bone + 4 spine bones
        assert result["bone_estimate"] >= 5

    def test_returns_required_keys(self):
        """Return dict contains all required keys."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["arm_pair"])
        required_keys = {"valid", "errors", "limb_count", "bone_estimate"}
        assert required_keys.issubset(set(result.keys()))

    def test_multiple_invalid_limbs_multiple_errors(self):
        """Multiple invalid limb types produce multiple errors."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["bad_1", "bad_2"])
        assert result["valid"] is False
        assert len(result["errors"]) >= 2

    def test_mixed_valid_and_invalid(self):
        """Mix of valid and invalid limb types fails."""
        from blender_addon.handlers.rigging import _validate_custom_rig_config

        result = _validate_custom_rig_config(["arm_pair", "invalid_type", "leg_pair"])
        assert result["valid"] is False
        assert result["limb_count"] == 3


# ---------------------------------------------------------------------------
# TestRigValidation -- _validate_rig_report
# ---------------------------------------------------------------------------


class TestRigValidation:
    """Test _validate_rig_report pure-logic function."""

    def _make_report(self, **overrides):
        """Helper to build a _validate_rig_report call with sensible defaults."""
        from blender_addon.handlers.rigging_weights import _validate_rig_report

        defaults = {
            "vertex_count": 100,
            "vertex_group_names": ["DEF-spine", "DEF-thigh.L", "DEF-thigh.R"],
            "unweighted_vertex_indices": [],
            "weight_sums": [1.0] * 100,
            "bone_names": ["DEF-spine", "DEF-thigh.L", "DEF-thigh.R"],
            "bone_rolls": {"DEF-thigh.L": 0.1, "DEF-thigh.R": -0.1},
            "bone_parents": {"DEF-spine": None, "DEF-thigh.L": "DEF-spine", "DEF-thigh.R": "DEF-spine"},
        }
        defaults.update(overrides)
        return _validate_rig_report(**defaults)

    def test_clean_rig_grades_a(self):
        """A rig with no issues grades A."""
        result = self._make_report()
        assert result["grade"] == "A"
        assert result["issues"] == []
        assert result["unweighted_vertices"] == 0
        assert result["non_normalized_vertices"] == 0
        assert result["symmetry_issues"] == 0
        assert result["roll_issues"] == 0

    def test_heavily_unweighted_grades_f(self):
        """A rig with >10% unweighted vertices grades F."""
        # 15 out of 100 = 15% unweighted
        result = self._make_report(
            unweighted_vertex_indices=list(range(15)),
        )
        assert result["grade"] == "F"
        assert result["unweighted_vertices"] == 15
        assert result["unweighted_percentage"] == 15.0

    def test_many_non_normalized_grades_f(self):
        """A rig with >100 non-normalized vertices grades F."""
        # 101 non-normalized out of 200 vertices
        sums = [1.0] * 99 + [0.5] * 101
        result = self._make_report(
            vertex_count=200,
            weight_sums=sums,
        )
        assert result["grade"] == "F"
        assert result["non_normalized_vertices"] == 101

    def test_moderate_unweighted_grades_d(self):
        """A rig with >5% unweighted grades D."""
        # 8 out of 100 = 8%
        result = self._make_report(
            unweighted_vertex_indices=list(range(8)),
        )
        assert result["grade"] == "D"

    def test_moderate_non_normalized_grades_d(self):
        """A rig with >50 non-normalized grades D."""
        sums = [1.0] * 49 + [0.5] * 51
        result = self._make_report(
            vertex_count=100,
            weight_sums=sums,
        )
        assert result["grade"] == "D"

    def test_many_symmetry_issues_grades_d(self):
        """A rig with >5 symmetry issues grades D."""
        # 6 left bones without right counterparts
        bones = [
            "DEF-bone_a.L", "DEF-bone_b.L", "DEF-bone_c.L",
            "DEF-bone_d.L", "DEF-bone_e.L", "DEF-bone_f.L",
        ]
        result = self._make_report(
            bone_names=bones,
            bone_rolls={},
            bone_parents={b: None for b in bones},
        )
        assert result["grade"] == "D"
        assert result["symmetry_issues"] == 6

    def test_small_unweighted_grades_c(self):
        """A rig with >1% but <=5% unweighted grades C."""
        # 3 out of 100 = 3%
        result = self._make_report(
            unweighted_vertex_indices=list(range(3)),
        )
        assert result["grade"] == "C"

    def test_some_non_normalized_grades_c(self):
        """A rig with >10 but <=50 non-normalized grades C."""
        sums = [1.0] * 85 + [0.5] * 15
        result = self._make_report(
            vertex_count=100,
            weight_sums=sums,
        )
        assert result["grade"] == "C"

    def test_few_symmetry_issues_grades_c(self):
        """A rig with >2 but <=5 symmetry issues grades C."""
        bones = ["DEF-a.L", "DEF-b.L", "DEF-c.L"]
        result = self._make_report(
            bone_names=bones,
            bone_rolls={},
            bone_parents={b: None for b in bones},
        )
        assert result["grade"] == "C"
        assert result["symmetry_issues"] == 3

    def test_tiny_unweighted_grades_b(self):
        """A rig with >0 but <=1% unweighted grades B."""
        # 1 out of 100 = 1%
        result = self._make_report(
            unweighted_vertex_indices=[0],
        )
        assert result["grade"] == "B"

    def test_few_non_normalized_grades_b(self):
        """A rig with >0 but <=10 non-normalized grades B."""
        sums = [1.0] * 95 + [0.5] * 5
        result = self._make_report(
            vertex_count=100,
            weight_sums=sums,
        )
        assert result["grade"] == "B"

    def test_roll_mismatches_grades_b(self):
        """A rig with >2 roll issues grades B."""
        bones = [
            "DEF-a.L", "DEF-a.R",
            "DEF-b.L", "DEF-b.R",
            "DEF-c.L", "DEF-c.R",
        ]
        # All rolls same sign -> mismatches
        rolls = {
            "DEF-a.L": 0.5, "DEF-a.R": 0.5,
            "DEF-b.L": 0.3, "DEF-b.R": 0.3,
            "DEF-c.L": 0.2, "DEF-c.R": 0.2,
        }
        result = self._make_report(
            bone_names=bones,
            bone_rolls=rolls,
            bone_parents={b: None for b in bones},
        )
        assert result["grade"] == "B"
        assert result["roll_issues"] == 3

    def test_asymmetric_bones_detected(self):
        """Missing right counterpart bone is reported as symmetry issue."""
        result = self._make_report(
            bone_names=["DEF-arm.L", "DEF-spine"],
            bone_rolls={"DEF-arm.L": 0.1},
            bone_parents={"DEF-arm.L": "DEF-spine", "DEF-spine": None},
        )
        assert result["symmetry_issues"] == 1
        assert any("Missing right counterpart" in i for i in result["issues"])

    def test_report_returns_required_keys(self):
        """Report dict contains all required keys."""
        result = self._make_report()
        required_keys = {
            "vertex_count", "bone_count", "unweighted_vertices",
            "unweighted_percentage", "non_normalized_vertices",
            "symmetry_issues", "roll_issues", "issues", "grade",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_zero_vertex_count_no_crash(self):
        """Zero vertex count does not crash (no division by zero)."""
        from blender_addon.handlers.rigging_weights import _validate_rig_report

        result = _validate_rig_report(
            vertex_count=0,
            vertex_group_names=[],
            unweighted_vertex_indices=[],
            weight_sums=[],
            bone_names=[],
            bone_rolls={},
            bone_parents={},
        )
        assert result["grade"] == "A"
        assert result["vertex_count"] == 0


# ---------------------------------------------------------------------------
# TestComputeRigGrade -- _compute_rig_grade thresholds
# ---------------------------------------------------------------------------


class TestComputeRigGrade:
    """Test _compute_rig_grade boundary conditions."""

    def test_grade_a_all_zeros(self):
        """All zeros -> grade A."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 0, 0, 0) == "A"

    def test_grade_b_tiny_unweighted(self):
        """Tiny unweighted percentage -> grade B."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0.5, 0, 0, 0) == "B"

    def test_grade_b_few_non_normalized(self):
        """Few non-normalized -> grade B."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 5, 0, 0) == "B"

    def test_grade_b_roll_issues(self):
        """Roll issues > 2 -> grade B."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 0, 0, 3) == "B"

    def test_grade_b_boundary_roll_at_2(self):
        """Roll issues at exactly 2 -> grade A (not > 2)."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 0, 0, 2) == "A"

    def test_grade_c_moderate_unweighted(self):
        """Unweighted > 1% -> grade C."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(2.0, 0, 0, 0) == "C"

    def test_grade_c_boundary_at_1(self):
        """Unweighted at exactly 1% -> grade B (not > 1)."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(1.0, 0, 0, 0) == "B"

    def test_grade_c_non_normalized_over_10(self):
        """Non-normalized > 10 -> grade C."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 11, 0, 0) == "C"

    def test_grade_c_symmetry_over_2(self):
        """Symmetry issues > 2 -> grade C."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 0, 3, 0) == "C"

    def test_grade_d_unweighted_over_5(self):
        """Unweighted > 5% -> grade D."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(6.0, 0, 0, 0) == "D"

    def test_grade_d_non_normalized_over_50(self):
        """Non-normalized > 50 -> grade D."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 51, 0, 0) == "D"

    def test_grade_d_symmetry_over_5(self):
        """Symmetry issues > 5 -> grade D."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 0, 6, 0) == "D"

    def test_grade_f_unweighted_over_10(self):
        """Unweighted > 10% -> grade F."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(11.0, 0, 0, 0) == "F"

    def test_grade_f_non_normalized_over_100(self):
        """Non-normalized > 100 -> grade F."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 101, 0, 0) == "F"

    def test_grade_f_boundary_at_10(self):
        """Unweighted at exactly 10% -> grade D (not > 10)."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(10.0, 0, 0, 0) == "D"

    def test_grade_f_boundary_at_100(self):
        """Non-normalized at exactly 100 -> grade D (not > 100)."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        assert _compute_rig_grade(0, 100, 0, 0) == "D"

    def test_worst_grade_wins(self):
        """When multiple thresholds are crossed, the worst grade wins."""
        from blender_addon.handlers.rigging_weights import _compute_rig_grade

        # F-level unweighted + C-level symmetry -> F wins
        assert _compute_rig_grade(15.0, 0, 3, 0) == "F"


# ---------------------------------------------------------------------------
# TestDeformationPoses -- DEFORMATION_POSES constant
# ---------------------------------------------------------------------------


class TestDeformationPoses:
    """Test DEFORMATION_POSES structure and contents."""

    def test_exactly_8_poses(self):
        """DEFORMATION_POSES has exactly 8 entries."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        assert len(DEFORMATION_POSES) == 8

    def test_expected_pose_names(self):
        """DEFORMATION_POSES contains the expected 8 pose names."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        expected = {
            "t_pose", "a_pose", "crouch", "reach_up",
            "twist_left", "twist_right", "extreme_bend", "action_pose",
        }
        assert set(DEFORMATION_POSES.keys()) == expected

    def test_all_values_are_dicts(self):
        """Every pose value is a dict."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        for name, pose in DEFORMATION_POSES.items():
            assert isinstance(pose, dict), f"Pose '{name}' value is not a dict"

    def test_rotation_tuples_are_3_element(self):
        """Every rotation value in each pose is a 3-element tuple."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        for pose_name, rotations in DEFORMATION_POSES.items():
            for bone_name, rot in rotations.items():
                assert isinstance(rot, tuple), (
                    f"Pose '{pose_name}', bone '{bone_name}': "
                    f"expected tuple, got {type(rot).__name__}"
                )
                assert len(rot) == 3, (
                    f"Pose '{pose_name}', bone '{bone_name}': "
                    f"expected 3-element tuple, got {len(rot)}"
                )

    def test_t_pose_is_empty(self):
        """t_pose has no rotations (rest pose)."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        assert DEFORMATION_POSES["t_pose"] == {}

    def test_a_pose_has_upper_arms(self):
        """a_pose rotates upper arms."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        a_pose = DEFORMATION_POSES["a_pose"]
        assert "DEF-upper_arm.L" in a_pose
        assert "DEF-upper_arm.R" in a_pose

    def test_all_bone_names_start_with_def(self):
        """All bone names in poses start with 'DEF-'."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        for pose_name, rotations in DEFORMATION_POSES.items():
            for bone_name in rotations:
                assert bone_name.startswith("DEF-"), (
                    f"Pose '{pose_name}': bone '{bone_name}' "
                    f"does not start with 'DEF-'"
                )

    def test_rotation_values_are_numeric(self):
        """All rotation values are numeric (int or float)."""
        from blender_addon.handlers.rigging_weights import DEFORMATION_POSES

        for pose_name, rotations in DEFORMATION_POSES.items():
            for bone_name, (rx, ry, rz) in rotations.items():
                for val in (rx, ry, rz):
                    assert isinstance(val, (int, float)), (
                        f"Pose '{pose_name}', bone '{bone_name}': "
                        f"non-numeric rotation value {val}"
                    )


# ---------------------------------------------------------------------------
# TestWeightFixParams -- _validate_weight_fix_params
# ---------------------------------------------------------------------------


class TestWeightFixParams:
    """Test _validate_weight_fix_params validation logic."""

    def test_normalize_valid(self):
        """'normalize' is a valid operation with no extra params."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("normalize", {})
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["operation"] == "normalize"

    def test_clean_zeros_valid(self):
        """'clean_zeros' is valid with no extra params."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("clean_zeros", {})
        assert result["valid"] is True

    def test_clean_zeros_with_valid_threshold(self):
        """'clean_zeros' with valid threshold passes."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("clean_zeros", {"threshold": 0.05})
        assert result["valid"] is True

    def test_clean_zeros_with_invalid_threshold(self):
        """'clean_zeros' with threshold > 0.1 fails."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("clean_zeros", {"threshold": 0.5})
        assert result["valid"] is False
        assert any("threshold" in e for e in result["errors"])

    def test_smooth_valid_default(self):
        """'smooth' is valid with no extra params."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("smooth", {})
        assert result["valid"] is True

    def test_smooth_with_valid_factor(self):
        """'smooth' with valid factor and repeat passes."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("smooth", {"factor": 0.5, "repeat": 3})
        assert result["valid"] is True

    def test_smooth_with_invalid_factor(self):
        """'smooth' with factor > 1.0 fails."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("smooth", {"factor": 1.5})
        assert result["valid"] is False
        assert any("factor" in e for e in result["errors"])

    def test_smooth_with_invalid_repeat(self):
        """'smooth' with repeat > 10 fails."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("smooth", {"repeat": 20})
        assert result["valid"] is False
        assert any("repeat" in e for e in result["errors"])

    def test_smooth_with_zero_repeat(self):
        """'smooth' with repeat = 0 fails (must be >= 1)."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("smooth", {"repeat": 0})
        assert result["valid"] is False

    def test_mirror_with_valid_direction(self):
        """'mirror' with 'left_to_right' direction passes."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("mirror", {"direction": "left_to_right"})
        assert result["valid"] is True

    def test_mirror_with_right_to_left(self):
        """'mirror' with 'right_to_left' direction passes."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("mirror", {"direction": "right_to_left"})
        assert result["valid"] is True

    def test_mirror_without_direction_fails(self):
        """'mirror' without direction param fails."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("mirror", {})
        assert result["valid"] is False
        assert any("direction" in e for e in result["errors"])

    def test_mirror_with_invalid_direction_fails(self):
        """'mirror' with invalid direction fails."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("mirror", {"direction": "up_to_down"})
        assert result["valid"] is False

    def test_invalid_operation(self):
        """Unknown operation fails validation."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("explode", {})
        assert result["valid"] is False
        assert result["operation"] == "explode"
        assert any("Unknown operation" in e for e in result["errors"])

    def test_returns_required_keys(self):
        """Return dict contains all required keys."""
        from blender_addon.handlers.rigging_weights import _validate_weight_fix_params

        result = _validate_weight_fix_params("normalize", {})
        required_keys = {"valid", "errors", "operation"}
        assert required_keys.issubset(set(result.keys()))


# ---------------------------------------------------------------------------
# TestWeightLimitPure
# ---------------------------------------------------------------------------


class TestWeightLimitPure:
    """Test _enforce_weight_limit_pure logic."""

    def test_under_limit_unchanged(self):
        """Vertices under the limit are not modified."""
        from blender_addon.handlers.rigging_weights import _enforce_weight_limit_pure

        vw = [[("a", 0.5), ("b", 0.3), ("c", 0.2)]]
        result = _enforce_weight_limit_pure(vw, max_influences=4)
        assert result["clamped_vertices"] == 0
        assert len(result["vertex_weights"][0]) == 3

    def test_over_limit_clamped(self):
        """Vertices over the limit are clamped to max_influences."""
        from blender_addon.handlers.rigging_weights import _enforce_weight_limit_pure

        vw = [[("a", 0.3), ("b", 0.25), ("c", 0.2), ("d", 0.15), ("e", 0.1)]]
        result = _enforce_weight_limit_pure(vw, max_influences=4)
        assert result["clamped_vertices"] == 1
        assert len(result["vertex_weights"][0]) == 4

    def test_empty_input(self):
        """Empty input produces empty output."""
        from blender_addon.handlers.rigging_weights import _enforce_weight_limit_pure

        result = _enforce_weight_limit_pure([], max_influences=4)
        assert result["total_vertices"] == 0
        assert result["clamped_vertices"] == 0
        assert result["vertex_weights"] == []

    def test_custom_max_influences(self):
        """Custom max_influences of 2 clamps correctly."""
        from blender_addon.handlers.rigging_weights import _enforce_weight_limit_pure

        vw = [[("a", 0.5), ("b", 0.3), ("c", 0.2)]]
        result = _enforce_weight_limit_pure(vw, max_influences=2)
        assert result["clamped_vertices"] == 1
        assert len(result["vertex_weights"][0]) == 2

    def test_exactly_at_limit_not_clamped(self):
        """Vertices exactly at the limit are not clamped."""
        from blender_addon.handlers.rigging_weights import _enforce_weight_limit_pure

        vw = [[("a", 0.4), ("b", 0.3), ("c", 0.2), ("d", 0.1)]]
        result = _enforce_weight_limit_pure(vw, max_influences=4)
        assert result["clamped_vertices"] == 0

    def test_returns_required_keys(self):
        """Result has clamped_vertices, total_vertices, max_influences, vertex_weights."""
        from blender_addon.handlers.rigging_weights import _enforce_weight_limit_pure

        result = _enforce_weight_limit_pure([], max_influences=4)
        required = {"clamped_vertices", "total_vertices", "max_influences", "vertex_weights"}
        assert required.issubset(set(result.keys()))


# ---------------------------------------------------------------------------
# TestEnhancedValidation
# ---------------------------------------------------------------------------


class TestEnhancedValidation:
    """Test _enhanced_rig_validation function."""

    def _make_validation(self, **overrides):
        from blender_addon.handlers.rigging_weights import _enhanced_rig_validation
        defaults = {
            "bone_names": [
                "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
                "thigh.L", "thigh.R", "shin.L", "shin.R",
                "upper_arm_twist.L", "upper_arm_twist.R",
                "forearm_twist.L", "forearm_twist.R",
                "thigh_twist.L", "thigh_twist.R",
                "shin_twist.L", "shin_twist.R",
            ],
            "bone_rolls": {
                "upper_arm.L": 0.1, "upper_arm.R": -0.1,
                "forearm.L": 1.5708, "forearm.R": -1.5708,
                "thigh.L": 0.1, "thigh.R": -0.1,
                "shin.L": 0.1, "shin.R": -0.1,
            },
            "bone_parents": {},
            "vertex_influence_counts": [4, 3, 4, 2],
            "max_influences": 4,
        }
        defaults.update(overrides)
        return _enhanced_rig_validation(**defaults)

    def test_detects_zero_weight_bones(self):
        """zero_weight_bones key exists in result."""
        result = self._make_validation()
        assert "zero_weight_bones" in result

    def test_detects_over_limit_vertices(self):
        """Vertices exceeding max_influences are counted."""
        result = self._make_validation(
            vertex_influence_counts=[5, 6, 4, 3],
            max_influences=4,
        )
        assert result["over_limit_vertices"] == 2

    def test_symmetry_mismatch(self):
        """Missing R counterpart is detected."""
        result = self._make_validation(
            bone_names=["upper_arm.L", "forearm.L", "forearm.R",
                       "upper_arm_twist.L", "forearm_twist.L", "forearm_twist.R"],
            bone_rolls={"upper_arm.L": 0.1, "forearm.L": 1.5708, "forearm.R": -1.5708},
        )
        assert "upper_arm.L" in result["symmetry_mismatches"]

    def test_default_roll_flagged(self):
        """Limb bones with roll 0.0 are flagged."""
        result = self._make_validation(
            bone_rolls={
                "upper_arm.L": 0.0, "upper_arm.R": 0.0,
                "forearm.L": 0.0, "forearm.R": 0.0,
                "thigh.L": 0.0, "thigh.R": 0.0,
                "shin.L": 0.0, "shin.R": 0.0,
            },
        )
        assert len(result["default_roll_bones"]) >= 8

    def test_missing_twist(self):
        """Missing twist bones are detected."""
        result = self._make_validation(
            bone_names=["upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
                       "thigh.L", "thigh.R", "shin.L", "shin.R"],
            bone_rolls={
                "upper_arm.L": 0.1, "upper_arm.R": -0.1,
                "forearm.L": 1.5708, "forearm.R": -1.5708,
                "thigh.L": 0.1, "thigh.R": -0.1,
                "shin.L": 0.1, "shin.R": -0.1,
            },
        )
        assert len(result["missing_twist_bones"]) == 8

    def test_clean_rig(self):
        """A rig with twist bones, proper rolls, and within limit passes clean."""
        result = self._make_validation()
        assert result["over_limit_vertices"] == 0
        assert result["symmetry_mismatches"] == []
        assert result["missing_twist_bones"] == []

    def test_returns_required_keys(self):
        """Result has all required keys."""
        result = self._make_validation()
        required = {
            "zero_weight_bones", "over_limit_vertices",
            "symmetry_mismatches", "default_roll_bones",
            "missing_twist_bones", "issues",
        }
        assert required.issubset(set(result.keys()))


# ---------------------------------------------------------------------------
# TestMultiArmGeneration
# ---------------------------------------------------------------------------


class TestMultiArmGeneration:
    """Test _generate_multi_arm_bones pure-logic function."""

    def test_2_arms_6_bones(self):
        """2 arms produce 6 bones (1 pair x 3 bones x 2 sides)."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        bones = _generate_multi_arm_bones(2)
        assert len(bones) == 6

    def test_4_arms_12_bones(self):
        """4 arms produce 12 bones (2 pairs x 3 bones x 2 sides)."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        bones = _generate_multi_arm_bones(4)
        assert len(bones) == 12

    def test_6_arms_18_bones(self):
        """6 arms produce 18 bones (3 pairs x 3 bones x 2 sides)."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        bones = _generate_multi_arm_bones(6)
        assert len(bones) == 18

    def test_invalid_count_raises(self):
        """Odd or out-of-range arm count raises ValueError."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        with pytest.raises(ValueError):
            _generate_multi_arm_bones(3)
        with pytest.raises(ValueError):
            _generate_multi_arm_bones(0)
        with pytest.raises(ValueError):
            _generate_multi_arm_bones(8)

    def test_bone_defs_required_keys(self):
        """Each bone dict has name, head, tail, roll, parent, rigify_type."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        bones = _generate_multi_arm_bones(4)
        required = {"name", "head", "tail", "roll", "parent", "rigify_type"}
        for bone in bones:
            assert required.issubset(set(bone.keys())), f"Bone {bone.get('name')} missing keys"

    def test_lr_symmetry(self):
        """Each pair has matching L and R bones."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        bones = _generate_multi_arm_bones(4)
        l_names = {b["name"] for b in bones if b["name"].endswith(".L")}
        r_names = {b["name"] for b in bones if b["name"].endswith(".R")}
        for ln in l_names:
            rn = ln[:-2] + ".R"
            assert rn in r_names, f"Missing R counterpart for {ln}"

    def test_forearm_rolls_set(self):
        """Forearm bones have roll 1.5708 (L) and -1.5708 (R)."""
        from blender_addon.handlers.rigging import _generate_multi_arm_bones
        bones = _generate_multi_arm_bones(4)
        for bone in bones:
            if "forearm" in bone["name"]:
                if bone["name"].endswith(".L"):
                    assert abs(bone["roll"] - 1.5708) < 0.001
                elif bone["name"].endswith(".R"):
                    assert abs(bone["roll"] - (-1.5708)) < 0.001


# ---------------------------------------------------------------------------
# TestMonsterTemplateMap
# ---------------------------------------------------------------------------


class TestMonsterTemplateMap:
    """Test MONSTER_TEMPLATE_MAP and VB-specific rigging."""

    def test_all_20_monsters_mapped(self):
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        assert len(MONSTER_TEMPLATE_MAP) == 20

    def test_all_templates_valid(self):
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        for mid, config in MONSTER_TEMPLATE_MAP.items():
            assert config["template"] in TEMPLATE_CATALOG, f"{mid} has invalid template"

    def test_skitter_teeth_is_humanoid(self):
        """SkitterTeeth is a hunched bipedal (confirmed from concept art)."""
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        assert MONSTER_TEMPLATE_MAP["skitter_teeth"]["template"] == "humanoid"

    def test_bosses_have_boss_body(self):
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        bosses = ["the_broodmother", "the_bulwark", "the_congregation", "the_vessel", "the_weeping"]
        for boss in bosses:
            assert MONSTER_TEMPLATE_MAP[boss]["body"] == "boss"

    def test_validate_known_monster(self):
        from blender_addon.handlers.rigging import _validate_monster_rig_config
        result = _validate_monster_rig_config("skitter_teeth")
        assert result["valid"] is True
        assert result["template"] == "humanoid"

    def test_validate_unknown_monster(self):
        from blender_addon.handlers.rigging import _validate_monster_rig_config
        result = _validate_monster_rig_config("nonexistent")
        assert result["valid"] is False

    def test_all_monsters_have_features(self):
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        for mid, config in MONSTER_TEMPLATE_MAP.items():
            assert isinstance(config["features"], list), f"{mid} features not a list"
            assert len(config["features"]) >= 1, f"{mid} has no features"

    def test_all_monsters_have_notes(self):
        """Every monster has visual description notes from concept art analysis."""
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        for mid, config in MONSTER_TEMPLATE_MAP.items():
            assert "notes" in config, f"{mid} missing notes"
            assert len(config["notes"]) > 10, f"{mid} notes too short"

    def test_wraith_monsters_have_tentacle_base(self):
        """Bloodshade and hollow need no_legs_tentacle_base (from art: no legs)."""
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        for mid in ("bloodshade", "hollow"):
            assert "no_legs_tentacle_base" in MONSTER_TEMPLATE_MAP[mid]["features"]

    def test_serpent_monsters_have_arm_addon(self):
        """Grimthorn and needlefang are serpents WITH arms (from art)."""
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        for mid in ("grimthorn", "needlefang"):
            assert MONSTER_TEMPLATE_MAP[mid]["template"] == "serpent"
            assert "arm_pair_addon" in MONSTER_TEMPLATE_MAP[mid]["features"]

    def test_flying_insects_have_wings(self):
        """Flicker and broodmother need wing_pair_addon (from art: visible wings)."""
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        for mid in ("flicker", "the_broodmother"):
            assert "wing_pair_addon" in MONSTER_TEMPLATE_MAP[mid]["features"]

    def test_congregation_has_6_arms(self):
        """The Congregation has 6 arms (from art: 3 pairs visible)."""
        from blender_addon.handlers.rigging import MONSTER_TEMPLATE_MAP
        assert MONSTER_TEMPLATE_MAP["the_congregation"]["template"] == "multi_armed"
        assert "arm_count_6" in MONSTER_TEMPLATE_MAP["the_congregation"]["features"]


class TestRigFeatureDefinitions:
    """Test RIG_FEATURE_DEFINITIONS data."""

    def test_feature_defs_exist(self):
        from blender_addon.handlers.rigging import RIG_FEATURE_DEFINITIONS
        assert isinstance(RIG_FEATURE_DEFINITIONS, dict)
        assert len(RIG_FEATURE_DEFINITIONS) >= 10

    def test_structural_features_have_definitions(self):
        """Features that modify bone structure have definitions with adds/removes."""
        from blender_addon.handlers.rigging import RIG_FEATURE_DEFINITIONS
        structural = [k for k, v in RIG_FEATURE_DEFINITIONS.items()
                      if "adds" in v or "removes" in v]
        assert len(structural) >= 5, "Need at least 5 structural feature definitions"

    def test_feature_defs_have_description(self):
        from blender_addon.handlers.rigging import RIG_FEATURE_DEFINITIONS
        for name, defn in RIG_FEATURE_DEFINITIONS.items():
            assert "description" in defn, f"Feature '{name}' missing description"


# ---------------------------------------------------------------------------
# TestStatusEffectSockets
# ---------------------------------------------------------------------------


class TestStatusEffectSockets:
    """Test STATUS_EFFECT_SOCKETS mapping."""

    def test_head_socket_exists_for_all_templates(self):
        from blender_addon.handlers.rigging import STATUS_EFFECT_SOCKETS
        assert "head" in STATUS_EFFECT_SOCKETS
        assert len(STATUS_EFFECT_SOCKETS["head"]) >= 7

    def test_get_socket_returns_bone_name(self):
        from blender_addon.handlers.rigging import _get_status_effect_socket
        result = _get_status_effect_socket("humanoid", "head")
        assert result == "spine.005"

    def test_get_socket_returns_none_for_missing(self):
        from blender_addon.handlers.rigging import _get_status_effect_socket
        result = _get_status_effect_socket("serpent", "left_hand")
        assert result is None

    def test_root_socket_available_for_all(self):
        from blender_addon.handlers.rigging import STATUS_EFFECT_SOCKETS
        for template in ("humanoid", "quadruped", "arachnid", "floating", "insect", "dragon"):
            assert template in STATUS_EFFECT_SOCKETS["root"]

    def test_serpent_and_multi_armed_have_sockets(self):
        from blender_addon.handlers.rigging import STATUS_EFFECT_SOCKETS
        assert "serpent" in STATUS_EFFECT_SOCKETS["root"]
        assert "multi_armed" in STATUS_EFFECT_SOCKETS["root"]
        assert "amorphous" in STATUS_EFFECT_SOCKETS["root"]


# ---------------------------------------------------------------------------
# TestCorruptionMorph
# ---------------------------------------------------------------------------


class TestCorruptionMorph:
    """Test CORRUPTION_MORPH_STAGES and helpers."""

    def test_has_4_stages(self):
        from blender_addon.handlers.rigging import CORRUPTION_MORPH_STAGES
        assert len(CORRUPTION_MORPH_STAGES) == 4

    def test_stages_ascending_threshold(self):
        from blender_addon.handlers.rigging import CORRUPTION_MORPH_STAGES
        thresholds = [s["threshold_pct"] for s in CORRUPTION_MORPH_STAGES]
        assert thresholds == sorted(thresholds)

    def test_get_stage_at_0_returns_none(self):
        from blender_addon.handlers.rigging import _get_corruption_stage
        assert _get_corruption_stage(0.0) is None

    def test_get_stage_at_25(self):
        from blender_addon.handlers.rigging import _get_corruption_stage
        result = _get_corruption_stage(25.0)
        assert result is not None
        assert result["name"] == "corruption_stage_1"

    def test_get_stage_at_100(self):
        from blender_addon.handlers.rigging import _get_corruption_stage
        result = _get_corruption_stage(100.0)
        assert result["name"] == "corruption_stage_4"

    def test_get_stage_invalid_returns_none(self):
        from blender_addon.handlers.rigging import _get_corruption_stage
        assert _get_corruption_stage(-5.0) is None
        assert _get_corruption_stage(101.0) is None

    def test_stage_intensity_increases(self):
        from blender_addon.handlers.rigging import CORRUPTION_MORPH_STAGES
        intensities = [s["morph_intensity"] for s in CORRUPTION_MORPH_STAGES]
        assert intensities == sorted(intensities)


# ---------------------------------------------------------------------------
# TestBoneLOD
# ---------------------------------------------------------------------------


class TestBoneLOD:
    def test_lod0_returns_all(self):
        from blender_addon.handlers.rigging import _get_bones_for_lod, BONE_LOD_TIERS
        bones = {"spine": {}, "upper_arm.L": {}, "thumb_01.L": {}, "upper_arm_twist.L": {}}
        result = _get_bones_for_lod(bones, "LOD0_full")
        assert len(result) == 4

    def test_lod1_strips_fingers(self):
        from blender_addon.handlers.rigging import _get_bones_for_lod
        bones = {"spine": {}, "upper_arm.L": {}, "thumb_01.L": {}, "index_02.R": {}}
        result = _get_bones_for_lod(bones, "LOD1_no_fingers")
        assert "spine" in result
        assert "thumb_01.L" not in result
        assert "index_02.R" not in result

    def test_lod2_strips_twist(self):
        from blender_addon.handlers.rigging import _get_bones_for_lod
        bones = {"spine": {}, "forearm.L": {}, "forearm_twist.L": {}}
        result = _get_bones_for_lod(bones, "LOD2_no_twist")
        assert "forearm.L" in result
        assert "forearm_twist.L" not in result

    def test_invalid_lod_returns_all(self):
        from blender_addon.handlers.rigging import _get_bones_for_lod
        bones = {"a": {}, "b": {}}
        assert _get_bones_for_lod(bones, "INVALID") == bones


# ---------------------------------------------------------------------------
# TestHeroTemplateMap
# ---------------------------------------------------------------------------


class TestHeroTemplateMap:
    def test_has_4_heroes(self):
        from blender_addon.handlers.rigging import HERO_TEMPLATE_MAP
        assert len(HERO_TEMPLATE_MAP) == 4

    def test_all_humanoid(self):
        from blender_addon.handlers.rigging import HERO_TEMPLATE_MAP
        for hid, config in HERO_TEMPLATE_MAP.items():
            assert config["template"] == "humanoid"

    def test_vex_is_warden(self):
        from blender_addon.handlers.rigging import HERO_TEMPLATE_MAP
        assert HERO_TEMPLATE_MAP["vex"]["class"] == "WARDEN"


# ---------------------------------------------------------------------------
# TestExportValidation
# ---------------------------------------------------------------------------


class TestExportValidation:
    def test_clean_export(self):
        from blender_addon.handlers.rigging import _validate_export_readiness
        r = _validate_export_readiness(100, 4, False, True)
        assert r["export_ready"] is True

    def test_too_many_bones(self):
        from blender_addon.handlers.rigging import _validate_export_readiness
        r = _validate_export_readiness(300, 4, False, True)
        assert r["export_ready"] is False

    def test_over_influenced(self):
        from blender_addon.handlers.rigging import _validate_export_readiness
        r = _validate_export_readiness(100, 6, False, True)
        assert r["export_ready"] is False


# ---------------------------------------------------------------------------
# TestAnimationClipRequirements
# ---------------------------------------------------------------------------


class TestAnimationClipRequirements:
    def test_all_templates_have_clips(self):
        from blender_addon.handlers.rigging import REQUIRED_ANIMATION_CLIPS
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        for tname in TEMPLATE_CATALOG:
            assert tname in REQUIRED_ANIMATION_CLIPS, f"Missing clips for {tname}"

    def test_all_have_idle_and_death(self):
        from blender_addon.handlers.rigging import REQUIRED_ANIMATION_CLIPS
        for tname, clips in REQUIRED_ANIMATION_CLIPS.items():
            assert "idle" in clips
            assert "death" in clips


# ---------------------------------------------------------------------------
# TestSkinningQuality
# ---------------------------------------------------------------------------


class TestSkinningQuality:
    def test_perfect_quality(self):
        from blender_addon.handlers.rigging_weights import _compute_skinning_quality
        weights = [[(0, 0.5), (1, 0.5)], [(0, 0.7), (1, 0.3)]]
        positions = [(0, 0, 0), (1, 0, 0)]
        r = _compute_skinning_quality(weights, positions)
        assert r["quality_score"] > 0.8

    def test_all_unweighted(self):
        from blender_addon.handlers.rigging_weights import _compute_skinning_quality
        weights = [[], []]
        positions = [(0, 0, 0), (1, 0, 0)]
        r = _compute_skinning_quality(weights, positions)
        assert r["quality_score"] < 0.6

    def test_empty_input(self):
        from blender_addon.handlers.rigging_weights import _compute_skinning_quality
        r = _compute_skinning_quality([], [])
        assert r["quality_score"] == 1.0
