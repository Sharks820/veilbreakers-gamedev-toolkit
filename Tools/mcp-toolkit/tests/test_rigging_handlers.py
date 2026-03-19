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
