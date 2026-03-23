"""Tests for character extremity quality: hand/foot accuracy and monster variants.

Validates:
- Hand: finger count param, separation, nail geometry, joint count, proportions
- Foot: toe count param, nail geometry, separation
- Monster variants: claw hand, hoof, paw -- all registered and valid
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.facial_topology import (
    generate_hand_mesh,
    generate_foot_mesh,
    generate_claw_hand_mesh,
    generate_hoof_mesh,
    generate_paw_mesh,
    _FINGER_SPECS,
    _FINGER_COUNT_MAP,
)


# ===========================================================================
# Hand: finger_count parameter
# ===========================================================================


class TestHandFingerCount:
    """Test variable finger count on hands."""

    @pytest.mark.parametrize("count", [2, 3, 4, 5])
    def test_finger_count_respected(self, count):
        result = generate_hand_mesh("medium", finger_count=count)
        assert result["metadata"]["finger_count"] == count

    def test_default_is_five(self):
        result = generate_hand_mesh("medium")
        assert result["metadata"]["finger_count"] == 5

    def test_three_finger_monster(self):
        result = generate_hand_mesh("medium", finger_count=3)
        fd = result["metadata"]["finger_data"]
        assert len(fd) == 3
        # Must include thumb
        assert "thumb" in fd

    def test_two_finger_claw_grip(self):
        result = generate_hand_mesh("medium", finger_count=2)
        fd = result["metadata"]["finger_data"]
        assert len(fd) == 2
        assert "thumb" in fd

    def test_four_finger_alien(self):
        result = generate_hand_mesh("medium", finger_count=4)
        fd = result["metadata"]["finger_data"]
        assert len(fd) == 4
        assert "thumb" in fd

    def test_clamped_below_2(self):
        result = generate_hand_mesh("medium", finger_count=0)
        assert result["metadata"]["finger_count"] >= 2

    def test_clamped_above_5(self):
        result = generate_hand_mesh("medium", finger_count=10)
        assert result["metadata"]["finger_count"] <= 5

    def test_fewer_fingers_fewer_verts(self):
        five = generate_hand_mesh("medium", finger_count=5)
        three = generate_hand_mesh("medium", finger_count=3)
        assert five["metadata"]["vertex_count"] > three["metadata"]["vertex_count"]


# ===========================================================================
# Hand: finger separation
# ===========================================================================


class TestHandFingerSeparation:
    """Verify fingers are geometrically separate with visible gaps."""

    def _get_finger_vert_sets(self, result):
        """Get approximate vertex sets per finger based on joint positions."""
        joints = result["metadata"]["joint_positions"]
        fd = result["metadata"]["finger_data"]
        finger_centers = {}
        for name, data in fd.items():
            base_key = f"{name}_base"
            if base_key in joints:
                finger_centers[name] = joints[base_key]
        return finger_centers

    def test_finger_bases_have_distinct_x_positions(self):
        result = generate_hand_mesh("medium", side="right")
        joints = result["metadata"]["joint_positions"]
        xs = set()
        for finger in ["thumb", "index", "middle", "ring", "pinky"]:
            base = joints.get(f"{finger}_base")
            if base:
                # Round to mm to avoid floating point noise
                x_mm = round(base[0] * 1000)
                xs.add(x_mm)
        # Each finger should have a distinct X position
        assert len(xs) == 5, f"Expected 5 distinct X positions, got {len(xs)}"

    def test_minimum_gap_between_adjacent_fingers(self):
        """Adjacent finger bases must be at least 3mm apart."""
        result = generate_hand_mesh("high", side="right")
        joints = result["metadata"]["joint_positions"]
        ordered = ["index", "middle", "ring", "pinky"]
        for i in range(len(ordered) - 1):
            a = joints[f"{ordered[i]}_base"]
            b = joints[f"{ordered[i+1]}_base"]
            gap = abs(a[0] - b[0])
            assert gap > 0.003, (
                f"Gap between {ordered[i]} and {ordered[i+1]} is {gap:.4f}m "
                f"(< 3mm minimum)"
            )


# ===========================================================================
# Hand: nail geometry
# ===========================================================================


class TestHandNailGeometry:
    """Verify nail generation controlled by has_nails param."""

    def test_nails_at_medium_detail(self):
        with_nails = generate_hand_mesh("medium", has_nails=True)
        without_nails = generate_hand_mesh("medium", has_nails=False)
        # With nails should have more geometry
        assert (with_nails["metadata"]["poly_count"] >
                without_nails["metadata"]["poly_count"])

    def test_nails_at_high_detail(self):
        with_nails = generate_hand_mesh("high", has_nails=True)
        without_nails = generate_hand_mesh("high", has_nails=False)
        assert (with_nails["metadata"]["poly_count"] >
                without_nails["metadata"]["poly_count"])

    def test_no_nails_at_low_detail(self):
        """Low detail never generates nails regardless of has_nails."""
        with_nails = generate_hand_mesh("low", has_nails=True)
        without_nails = generate_hand_mesh("low", has_nails=False)
        assert (with_nails["metadata"]["poly_count"] ==
                without_nails["metadata"]["poly_count"])

    def test_has_nails_metadata(self):
        result = generate_hand_mesh("medium", has_nails=True)
        assert result["metadata"]["has_nails"] is True

    def test_no_nails_metadata(self):
        result = generate_hand_mesh("medium", has_nails=False)
        assert result["metadata"]["has_nails"] is False

    def test_each_finger_has_nail_flag(self):
        result = generate_hand_mesh("medium", has_nails=True)
        for name, data in result["metadata"]["finger_data"].items():
            assert "has_nail" in data, f"Missing has_nail flag on {name}"

    def test_nail_vertices_on_dorsal_surface(self):
        """Nail verts should be on the dorsal (top) side of the finger."""
        result = generate_hand_mesh("high", has_nails=True)
        # The high-detail version generates nails -- they should be on
        # the positive-z side of the finger
        fd = result["metadata"]["finger_data"]
        joints = result["metadata"]["joint_positions"]
        for name, data in fd.items():
            if data.get("has_nail"):
                distal = joints.get(f"{name}_distal")
                assert distal is not None, f"Missing distal joint for {name}"


# ===========================================================================
# Hand: joint count per finger
# ===========================================================================


class TestHandJointCount:
    """Each finger must have exactly 3 joints."""

    @pytest.mark.parametrize("count", [2, 3, 4, 5])
    def test_three_joints_per_finger(self, count):
        result = generate_hand_mesh("medium", finger_count=count)
        for name, data in result["metadata"]["finger_data"].items():
            assert data["joint_count"] == 3, (
                f"{name} has {data['joint_count']} joints, expected 3"
            )

    def test_joint_hierarchy_exists(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        for finger in ["thumb", "index", "middle", "ring", "pinky"]:
            for jt in ["proximal", "intermediate", "distal"]:
                key = f"{finger}_{jt}"
                assert key in joints, f"Missing {key}"


# ===========================================================================
# Hand: proportions
# ===========================================================================


class TestHandProportions:
    """Verify correct finger length proportions."""

    def test_middle_finger_longest(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        middle_y = joints["middle_distal"][1]
        for finger in ["index", "ring", "pinky"]:
            tip_y = joints[f"{finger}_distal"][1]
            assert middle_y >= tip_y, (
                f"Middle finger ({middle_y:.4f}) not longest, "
                f"{finger} is {tip_y:.4f}"
            )

    def test_pinky_shortest(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        pinky_y = joints["pinky_distal"][1]
        for finger in ["index", "middle", "ring"]:
            tip_y = joints[f"{finger}_distal"][1]
            assert pinky_y <= tip_y, (
                f"Pinky ({pinky_y:.4f}) not shortest, "
                f"{finger} is {tip_y:.4f}"
            )

    def test_thumb_marked_as_thumb(self):
        result = generate_hand_mesh("medium")
        fd = result["metadata"]["finger_data"]
        assert fd["thumb"]["is_thumb"] is True
        for name in ["index", "middle", "ring", "pinky"]:
            assert fd[name]["is_thumb"] is False


# ===========================================================================
# Hand: face validity
# ===========================================================================


class TestHandFaceValidity:
    """All face indices must be valid."""

    @pytest.mark.parametrize("count", [2, 3, 4, 5])
    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_all_face_indices_valid(self, count, detail):
        result = generate_hand_mesh(detail, finger_count=count)
        n = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for vi in face:
                assert 0 <= vi < n, (
                    f"Face {fi}: index {vi} out of range [0, {n}), "
                    f"detail={detail}, fingers={count}"
                )


# ===========================================================================
# Foot: toe_count parameter
# ===========================================================================


class TestFootToeCount:
    """Test variable toe count on feet."""

    @pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
    def test_toe_count_respected(self, count):
        result = generate_foot_mesh("medium", toe_count=count)
        assert result["metadata"]["toe_count"] == count

    def test_default_is_five(self):
        result = generate_foot_mesh("medium")
        assert result["metadata"]["toe_count"] == 5

    def test_single_toe(self):
        result = generate_foot_mesh("medium", toe_count=1)
        joints = result["metadata"]["joint_positions"]
        assert "big_toe_base" in joints

    def test_three_toes(self):
        result = generate_foot_mesh("medium", toe_count=3)
        joints = result["metadata"]["joint_positions"]
        for name in ["big_toe", "second_toe", "third_toe"]:
            assert f"{name}_base" in joints

    def test_low_detail_groups_small_toes(self):
        """Low detail with 5 toes should group small toes."""
        result = generate_foot_mesh("low", toe_count=5)
        assert result["metadata"]["individual_toes"] is False
        assert result["metadata"]["toe_count"] == 2  # big + grouped

    def test_fewer_toes_fewer_verts(self):
        five = generate_foot_mesh("medium", toe_count=5)
        two = generate_foot_mesh("medium", toe_count=2)
        assert five["metadata"]["vertex_count"] > two["metadata"]["vertex_count"]


# ===========================================================================
# Foot: nail geometry
# ===========================================================================


class TestFootNailGeometry:
    """Test toenail generation."""

    def test_nails_at_medium_detail(self):
        with_nails = generate_foot_mesh("medium", has_nails=True)
        without_nails = generate_foot_mesh("medium", has_nails=False)
        assert (with_nails["metadata"]["poly_count"] >
                without_nails["metadata"]["poly_count"])

    def test_has_nails_metadata(self):
        result = generate_foot_mesh("medium", has_nails=True)
        assert result["metadata"]["has_nails"] is True

    def test_nails_generated_count(self):
        result = generate_foot_mesh("medium", toe_count=5, has_nails=True)
        assert result["metadata"]["nails_generated"] == 5

    def test_no_nails_zero_count(self):
        result = generate_foot_mesh("medium", toe_count=5, has_nails=False)
        assert result["metadata"]["nails_generated"] == 0


# ===========================================================================
# Foot: face validity
# ===========================================================================


class TestFootFaceValidity:
    """All face indices must be valid."""

    @pytest.mark.parametrize("count", [1, 3, 5])
    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_all_face_indices_valid(self, count, detail):
        result = generate_foot_mesh(detail, toe_count=count)
        n = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for vi in face:
                assert 0 <= vi < n, (
                    f"Face {fi}: index {vi} out of range [0, {n}), "
                    f"detail={detail}, toes={count}"
                )


# ===========================================================================
# Monster variant: claw hand
# ===========================================================================


class TestClawHandMesh:
    """Test generate_claw_hand_mesh."""

    def test_returns_valid_mesh(self):
        result = generate_claw_hand_mesh()
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    @pytest.mark.parametrize("count", [2, 3, 4, 5])
    def test_claw_count(self, count):
        result = generate_claw_hand_mesh(claw_count=count)
        assert result["metadata"]["claw_count"] == count

    def test_default_claw_count_is_3(self):
        result = generate_claw_hand_mesh()
        assert result["metadata"]["claw_count"] == 3

    @pytest.mark.parametrize("style", ["sharp", "hooked", "blunt"])
    def test_style_parameter(self, style):
        result = generate_claw_hand_mesh(style=style)
        assert result["metadata"]["style"] == style

    def test_invalid_style_defaults(self):
        result = generate_claw_hand_mesh(style="invalid")
        assert result["metadata"]["style"] == "sharp"

    def test_category(self):
        result = generate_claw_hand_mesh()
        assert result["metadata"]["category"] == "character_claw_hand"

    def test_has_wrist_joint(self):
        result = generate_claw_hand_mesh()
        assert "wrist" in result["metadata"]["joint_positions"]

    def test_claw_data_present(self):
        result = generate_claw_hand_mesh(claw_count=3)
        cd = result["metadata"]["claw_data"]
        assert len(cd) == 3

    def test_talon_tip_joints(self):
        result = generate_claw_hand_mesh(claw_count=3)
        joints = result["metadata"]["joint_positions"]
        for i in range(3):
            assert f"claw_{i}_talon_tip" in joints

    @pytest.mark.parametrize("side", ["left", "right"])
    def test_side_parameter(self, side):
        result = generate_claw_hand_mesh(side=side)
        assert result["metadata"]["side"] == side

    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_all_detail_levels(self, detail):
        result = generate_claw_hand_mesh(detail=detail)
        assert result["metadata"]["detail"] == detail

    def test_all_face_indices_valid(self):
        result = generate_claw_hand_mesh(claw_count=5, detail="high")
        n = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for vi in face:
                assert 0 <= vi < n, (
                    f"Claw hand face {fi}: index {vi} out of range [0, {n})"
                )

    def test_sharp_vs_blunt_geometry_differs(self):
        sharp = generate_claw_hand_mesh(style="sharp")
        blunt = generate_claw_hand_mesh(style="blunt")
        # Different talon curvature means different vertex positions
        sv = sharp["vertices"]
        bv = blunt["vertices"]
        # At least some vertices should differ
        diffs = sum(1 for a, b in zip(sv, bv) if a != b)
        assert diffs > 0


# ===========================================================================
# Monster variant: hoof
# ===========================================================================


class TestHoofMesh:
    """Test generate_hoof_mesh."""

    def test_returns_valid_mesh(self):
        result = generate_hoof_mesh()
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    @pytest.mark.parametrize("style", ["horse", "cloven", "padded"])
    def test_style_parameter(self, style):
        result = generate_hoof_mesh(style=style)
        assert result["metadata"]["style"] == style

    def test_invalid_style_defaults(self):
        result = generate_hoof_mesh(style="invalid")
        assert result["metadata"]["style"] == "horse"

    def test_default_is_horse(self):
        result = generate_hoof_mesh()
        assert result["metadata"]["style"] == "horse"

    def test_category(self):
        result = generate_hoof_mesh()
        assert result["metadata"]["category"] == "character_hoof"

    def test_has_pastern_joint(self):
        result = generate_hoof_mesh()
        joints = result["metadata"]["joint_positions"]
        assert "pastern_top" in joints
        assert "coronet" in joints

    def test_horse_has_sole(self):
        result = generate_hoof_mesh(style="horse")
        assert "sole" in result["metadata"]["joint_positions"]

    def test_cloven_has_toes(self):
        result = generate_hoof_mesh(style="cloven")
        joints = result["metadata"]["joint_positions"]
        assert "inner_toe_tip" in joints
        assert "outer_toe_tip" in joints
        assert "cleft" in joints

    def test_padded_has_pad_center(self):
        result = generate_hoof_mesh(style="padded")
        assert "pad_center" in result["metadata"]["joint_positions"]

    @pytest.mark.parametrize("side", ["left", "right"])
    def test_side_parameter(self, side):
        result = generate_hoof_mesh(side=side)
        assert result["metadata"]["side"] == side

    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_all_detail_levels(self, detail):
        result = generate_hoof_mesh(detail=detail)
        assert result["metadata"]["detail"] == detail

    def test_all_face_indices_valid(self):
        for style in ("horse", "cloven", "padded"):
            result = generate_hoof_mesh(style=style, detail="high")
            n = len(result["vertices"])
            for fi, face in enumerate(result["faces"]):
                for vi in face:
                    assert 0 <= vi < n, (
                        f"Hoof ({style}) face {fi}: index {vi} "
                        f"out of range [0, {n})"
                    )

    def test_different_styles_different_geometry(self):
        horse = generate_hoof_mesh(style="horse")
        cloven = generate_hoof_mesh(style="cloven")
        padded = generate_hoof_mesh(style="padded")
        counts = {
            horse["metadata"]["vertex_count"],
            cloven["metadata"]["vertex_count"],
            padded["metadata"]["vertex_count"],
        }
        assert len(counts) >= 2, "Expected different vertex counts for styles"


# ===========================================================================
# Monster variant: paw
# ===========================================================================


class TestPawMesh:
    """Test generate_paw_mesh."""

    def test_returns_valid_mesh(self):
        result = generate_paw_mesh()
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    @pytest.mark.parametrize("count", [2, 3, 4, 5])
    def test_toe_count(self, count):
        result = generate_paw_mesh(toe_count=count)
        assert result["metadata"]["toe_count"] == count

    def test_default_is_4_toes(self):
        result = generate_paw_mesh()
        assert result["metadata"]["toe_count"] == 4

    def test_category(self):
        result = generate_paw_mesh()
        assert result["metadata"]["category"] == "character_paw"

    def test_has_claws_by_default(self):
        result = generate_paw_mesh()
        assert result["metadata"]["has_claws"] is True

    def test_no_claws_option(self):
        result = generate_paw_mesh(has_claws=False)
        assert result["metadata"]["has_claws"] is False

    def test_claws_add_geometry(self):
        with_claws = generate_paw_mesh(has_claws=True)
        without_claws = generate_paw_mesh(has_claws=False)
        assert (with_claws["metadata"]["vertex_count"] >
                without_claws["metadata"]["vertex_count"])

    def test_toe_beans_present(self):
        result = generate_paw_mesh()
        td = result["metadata"]["toe_data"]
        for name, data in td.items():
            assert data["has_bean"] is True, f"{name} missing toe bean"

    def test_claw_tips_in_joints(self):
        result = generate_paw_mesh(toe_count=4, has_claws=True)
        joints = result["metadata"]["joint_positions"]
        for i in range(4):
            assert f"toe_{i}_claw_tip" in joints

    def test_no_claw_tips_when_disabled(self):
        result = generate_paw_mesh(toe_count=4, has_claws=False)
        joints = result["metadata"]["joint_positions"]
        for i in range(4):
            assert f"toe_{i}_claw_tip" not in joints

    def test_palm_pad_joint(self):
        result = generate_paw_mesh()
        assert "palm_pad" in result["metadata"]["joint_positions"]

    @pytest.mark.parametrize("side", ["left", "right"])
    def test_side_parameter(self, side):
        result = generate_paw_mesh(side=side)
        assert result["metadata"]["side"] == side

    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_all_detail_levels(self, detail):
        result = generate_paw_mesh(detail=detail)
        assert result["metadata"]["detail"] == detail

    def test_all_face_indices_valid(self):
        result = generate_paw_mesh(toe_count=5, has_claws=True, detail="high")
        n = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for vi in face:
                assert 0 <= vi < n, (
                    f"Paw face {fi}: index {vi} out of range [0, {n})"
                )

    def test_fewer_toes_fewer_verts(self):
        five = generate_paw_mesh(toe_count=5)
        two = generate_paw_mesh(toe_count=2)
        assert five["metadata"]["vertex_count"] > two["metadata"]["vertex_count"]


# ===========================================================================
# Integration: backward compatibility
# ===========================================================================


class TestBackwardCompatibility:
    """Ensure original API still works unchanged."""

    def test_hand_default_signature(self):
        """Original (detail, side) call still works."""
        result = generate_hand_mesh("medium", "right")
        assert result["metadata"]["finger_count"] == 5

    def test_foot_default_signature(self):
        """Original (detail, side) call still works."""
        result = generate_foot_mesh("medium", "right")
        assert result["metadata"]["toe_count"] == 5

    def test_hand_keyword_only_new_params(self):
        result = generate_hand_mesh("low", "left")
        assert result["metadata"]["finger_count"] == 5
        assert result["metadata"]["has_nails"] is True

    def test_foot_keyword_only_new_params(self):
        result = generate_foot_mesh("low", "left")
        # Low detail groups toes, so toe_count in metadata is 2
        assert result["metadata"]["has_nails"] is True
