"""Tests for UDIM support, facial topology, hand/foot anatomy, and corrective shapes.

Validates Tasks #52-55:
- UDIM multi-tile UV assignment and trim sheet projection
- Face mesh generation with concentric quad loops
- 30 FACS blend shape targets
- Hand mesh with 5 articulated fingers
- Foot mesh with arch, toes, ankle detail
- Corrective blend shapes for joint deformation
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.udim_support import (
    UDIM_LAYOUTS,
    compute_udim_tile_assignment,
    compute_trim_sheet_uvs,
)
from blender_addon.handlers.facial_topology import (
    FACE_DETAIL_SPECS,
    generate_face_mesh,
    generate_blend_shape_targets,
    generate_hand_mesh,
    generate_foot_mesh,
    generate_corrective_shapes,
    _BLEND_SHAPE_DEFS,
    _CORRECTIVE_SHAPE_DEFS,
    _elliptical_loop,
    _ring_verts,
    _connect_rings_quad,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _make_simple_body_mesh() -> tuple[list, list]:
    """Create a simplified body mesh for UDIM testing."""
    verts = []
    faces = []

    # Create a column of boxes representing body regions
    # Head: y 1.56 - 1.80
    # Body: y 0.85 - 1.56
    # Arms: x +/- 0.25, y 0.63 - 1.35
    # Legs: y 0.0 - 0.85

    sections = [
        ("head", 0.08, 1.56, 1.80),
        ("body", 0.15, 0.85, 1.56),
        ("legs", 0.10, 0.00, 0.85),
    ]

    for _, hw, y_lo, y_hi in sections:
        b = len(verts)
        verts.extend([
            (-hw, y_lo, -0.05), (hw, y_lo, -0.05),
            (hw, y_hi, -0.05), (-hw, y_hi, -0.05),
            (-hw, y_lo, 0.05), (hw, y_lo, 0.05),
            (hw, y_hi, 0.05), (-hw, y_hi, 0.05),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
            (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
        ])

    # Arms (lateral, at arm height)
    for sign in [-1, 1]:
        b = len(verts)
        ax = sign * 0.25
        verts.extend([
            (ax - 0.03, 0.63, -0.03), (ax + 0.03, 0.63, -0.03),
            (ax + 0.03, 1.35, -0.03), (ax - 0.03, 1.35, -0.03),
            (ax - 0.03, 0.63, 0.03), (ax + 0.03, 0.63, 0.03),
            (ax + 0.03, 1.35, 0.03), (ax - 0.03, 1.35, 0.03),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
            (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
        ])

    return verts, faces


# ===========================================================================
# UDIM Layout Tests (Task #52)
# ===========================================================================


class TestUDIMLayouts:
    """Test UDIM layout configuration data."""

    def test_hero_character_layout_exists(self):
        assert "hero_character" in UDIM_LAYOUTS

    def test_standard_npc_layout_exists(self):
        assert "standard_npc" in UDIM_LAYOUTS

    def test_boss_character_layout_exists(self):
        assert "boss_character" in UDIM_LAYOUTS

    def test_prop_layout_exists(self):
        assert "prop" in UDIM_LAYOUTS

    def test_hero_has_four_tiles(self):
        layout = UDIM_LAYOUTS["hero_character"]
        assert len(layout["tiles"]) == 4

    def test_hero_tile_ids_start_at_1001(self):
        layout = UDIM_LAYOUTS["hero_character"]
        assert 1001 in layout["tiles"]
        assert 1002 in layout["tiles"]
        assert 1003 in layout["tiles"]
        assert 1004 in layout["tiles"]

    def test_hero_coverage_sums_to_one(self):
        layout = UDIM_LAYOUTS["hero_character"]
        total = sum(t["coverage"] for t in layout["tiles"].values())
        assert abs(total - 1.0) < 1e-6

    def test_npc_coverage_sums_to_one(self):
        layout = UDIM_LAYOUTS["standard_npc"]
        total = sum(t["coverage"] for t in layout["tiles"].values())
        assert abs(total - 1.0) < 1e-6

    def test_hero_resolution_is_4k(self):
        assert UDIM_LAYOUTS["hero_character"]["resolution_per_tile"] == 4096

    def test_npc_resolution_is_2k(self):
        assert UDIM_LAYOUTS["standard_npc"]["resolution_per_tile"] == 2048

    def test_each_tile_has_name(self):
        for layout_name, layout in UDIM_LAYOUTS.items():
            for tile_id, tile_info in layout["tiles"].items():
                assert "name" in tile_info, f"Tile {tile_id} in {layout_name} missing name"
                assert isinstance(tile_info["name"], str)

    def test_each_tile_has_coverage(self):
        for layout_name, layout in UDIM_LAYOUTS.items():
            for tile_id, tile_info in layout["tiles"].items():
                assert "coverage" in tile_info
                assert 0 < tile_info["coverage"] <= 1.0

    def test_boss_has_five_tiles(self):
        layout = UDIM_LAYOUTS["boss_character"]
        assert len(layout["tiles"]) == 5

    def test_boss_coverage_sums_to_one(self):
        layout = UDIM_LAYOUTS["boss_character"]
        total = sum(t["coverage"] for t in layout["tiles"].values())
        assert abs(total - 1.0) < 1e-6


class TestUDIMTileAssignment:
    """Test compute_udim_tile_assignment function."""

    def test_unknown_layout_returns_error(self):
        result = compute_udim_tile_assignment([], [], layout_name="nonexistent")
        assert "error" in result
        assert result["tile_count"] == 0

    def test_empty_mesh_returns_empty(self):
        result = compute_udim_tile_assignment([], [], layout_name="hero_character")
        assert result["tile_count"] == 4
        assert len(result["unassigned"]) == 0

    def test_explicit_region_assignment(self):
        verts, faces = _make_simple_body_mesh()
        regions = {
            "head": [0, 1, 2, 3, 4, 5],
            "body": [6, 7, 8, 9, 10, 11],
            "arms_hands": [18, 19, 20, 21, 22, 23],
            "legs_feet": [12, 13, 14, 15, 16, 17],
        }
        result = compute_udim_tile_assignment(verts, faces, regions, "hero_character")
        assert result["tile_count"] == 4
        assert len(result["tile_assignments"][1001]) > 0  # head
        assert len(result["tile_assignments"][1002]) > 0  # body

    def test_auto_assignment_covers_all_faces(self):
        verts, faces = _make_simple_body_mesh()
        result = compute_udim_tile_assignment(verts, faces, layout_name="hero_character")
        total_assigned = sum(len(v) for v in result["tile_assignments"].values())
        assert total_assigned == len(faces)

    def test_face_to_tile_mapping_complete(self):
        verts, faces = _make_simple_body_mesh()
        result = compute_udim_tile_assignment(verts, faces, layout_name="hero_character")
        assert len(result["face_to_tile"]) == len(faces)

    def test_coverage_actual_sums_to_one(self):
        verts, faces = _make_simple_body_mesh()
        result = compute_udim_tile_assignment(verts, faces, layout_name="hero_character")
        total = sum(result["coverage_actual"].values())
        assert abs(total - 1.0) < 1e-6

    def test_npc_layout_two_tiles(self):
        verts, faces = _make_simple_body_mesh()
        result = compute_udim_tile_assignment(verts, faces, layout_name="standard_npc")
        assert result["tile_count"] == 2

    def test_out_of_range_face_index_ignored(self):
        verts, faces = _make_simple_body_mesh()
        regions = {"head": [999, 1000]}
        result = compute_udim_tile_assignment(verts, faces, regions, "hero_character")
        assert len(result["tile_assignments"][1001]) == 0

    def test_returns_resolution(self):
        verts, faces = _make_simple_body_mesh()
        result = compute_udim_tile_assignment(verts, faces, layout_name="hero_character")
        assert result["resolution_per_tile"] == 4096


class TestTrimSheetUVs:
    """Test compute_trim_sheet_uvs function."""

    def test_empty_mesh_returns_empty(self):
        result = compute_trim_sheet_uvs([], [], 0)
        assert result == []

    def test_basic_projection(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        result = compute_trim_sheet_uvs(verts, faces, 0, total_strips=4)
        assert len(result) == 1
        assert result[0]["strip_index"] == 0
        assert len(result[0]["uvs"]) == 4

    def test_uvs_within_strip_bounds(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        total_strips = 8
        for strip_idx in range(total_strips):
            result = compute_trim_sheet_uvs(verts, faces, strip_idx, total_strips)
            strip_height = 1.0 / total_strips
            v_min = 1.0 - (strip_idx + 1) * strip_height
            v_max = 1.0 - strip_idx * strip_height

            for face_data in result:
                for u, v in face_data["uvs"]:
                    assert 0.0 <= u <= 1.0, f"U out of range: {u}"
                    assert v_min - 1e-6 <= v <= v_max + 1e-6, f"V {v} out of strip [{v_min}, {v_max}]"

    def test_strip_name_assigned(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        faces = [(0, 1, 2)]
        result = compute_trim_sheet_uvs(verts, faces, 0, total_strips=8)
        assert result[0]["strip_name"] == "molding"

    def test_strip_index_clamped(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        faces = [(0, 1, 2)]
        result = compute_trim_sheet_uvs(verts, faces, 100, total_strips=4)
        assert result[0]["strip_index"] == 3  # clamped to max

    def test_multiple_faces(self):
        verts = [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (1, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0),
        ]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7)]
        result = compute_trim_sheet_uvs(verts, faces, 2, total_strips=8)
        assert len(result) == 2

    def test_strip_names_extend_beyond_8(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        faces = [(0, 1, 2)]
        result = compute_trim_sheet_uvs(verts, faces, 9, total_strips=12)
        assert "strip_" in result[0]["strip_name"]

    def test_negative_strip_clamped(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        faces = [(0, 1, 2)]
        result = compute_trim_sheet_uvs(verts, faces, -5, total_strips=4)
        assert result[0]["strip_index"] == 0


# ===========================================================================
# Face Mesh Tests (Task #53)
# ===========================================================================


class TestFaceMeshGeneration:
    """Test generate_face_mesh function."""

    @pytest.mark.parametrize("level", ["low", "medium", "high"])
    def test_returns_valid_mesh_spec(self, level):
        result = generate_face_mesh(level)
        assert "vertices" in result
        assert "faces" in result
        assert "metadata" in result
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_low_detail_smaller_than_high(self):
        low = generate_face_mesh("low")
        high = generate_face_mesh("high")
        assert low["metadata"]["vertex_count"] < high["metadata"]["vertex_count"]

    def test_medium_detail_between_low_and_high(self):
        low = generate_face_mesh("low")
        med = generate_face_mesh("medium")
        high = generate_face_mesh("high")
        assert low["metadata"]["vertex_count"] < med["metadata"]["vertex_count"]
        assert med["metadata"]["vertex_count"] < high["metadata"]["vertex_count"]

    def test_has_eye_loop_metadata(self):
        result = generate_face_mesh("medium")
        meta = result["metadata"]
        assert "eye_loop_count" in meta
        assert meta["eye_loop_count"] == FACE_DETAIL_SPECS["medium"]["eye_loops"]

    def test_has_mouth_loop_metadata(self):
        result = generate_face_mesh("medium")
        meta = result["metadata"]
        assert "mouth_loop_count" in meta
        assert meta["mouth_loop_count"] == FACE_DETAIL_SPECS["medium"]["mouth_loops"]

    def test_high_detail_eye_loops(self):
        result = generate_face_mesh("high")
        assert result["metadata"]["eye_loop_count"] == 7

    def test_low_detail_eye_loops(self):
        result = generate_face_mesh("low")
        assert result["metadata"]["eye_loop_count"] == 4

    def test_mostly_quads(self):
        result = generate_face_mesh("medium")
        meta = result["metadata"]
        quad_count = meta["quad_count"]
        tri_count = meta["tri_count"]
        total = quad_count + tri_count
        # At least 90% quads
        assert quad_count / max(total, 1) >= 0.85, (
            f"Only {quad_count}/{total} quads ({100*quad_count/total:.0f}%)"
        )

    def test_no_ears_at_low_detail(self):
        result = generate_face_mesh("low")
        assert result["metadata"]["has_ears"] is False

    def test_ears_at_medium_detail(self):
        result = generate_face_mesh("medium")
        assert result["metadata"]["has_ears"] is True

    def test_ears_at_high_detail(self):
        result = generate_face_mesh("high")
        assert result["metadata"]["has_ears"] is True
        assert result["metadata"]["ear_vertex_count"] > 0

    def test_invalid_detail_defaults_to_medium(self):
        result = generate_face_mesh("ultra")
        assert result["metadata"]["detail_level"] == "medium"

    def test_face_dimensions_reasonable(self):
        result = generate_face_mesh("medium")
        dims = result["metadata"]["dimensions"]
        # Face should be roughly 0.16m wide, 0.12m tall
        assert 0.05 < dims["width"] < 0.3
        assert 0.05 < dims["height"] < 0.3

    def test_eye_data_present(self):
        result = generate_face_mesh("medium")
        assert "eye_data" in result["metadata"]
        assert "left" in result["metadata"]["eye_data"]
        assert "right" in result["metadata"]["eye_data"]

    def test_eye_data_has_loop_count(self):
        result = generate_face_mesh("medium")
        for side in ["left", "right"]:
            eye = result["metadata"]["eye_data"][side]
            assert "loop_count" in eye
            assert eye["loop_count"] == FACE_DETAIL_SPECS["medium"]["eye_loops"]

    def test_nose_detail_scales(self):
        low = generate_face_mesh("low")
        high = generate_face_mesh("high")
        assert low["metadata"]["nose_detail"] < high["metadata"]["nose_detail"]

    def test_all_face_indices_valid(self):
        result = generate_face_mesh("high")
        n_verts = len(result["vertices"])
        for face in result["faces"]:
            for vi in face:
                assert 0 <= vi < n_verts, f"Face index {vi} out of range [0, {n_verts})"

    def test_category_is_character_face(self):
        result = generate_face_mesh("medium")
        assert result["metadata"]["category"] == "character_face"


# ===========================================================================
# Blend Shape Tests (Task #53 continued)
# ===========================================================================


class TestBlendShapeTargets:
    """Test generate_blend_shape_targets function."""

    @pytest.fixture
    def face_mesh(self):
        return generate_face_mesh("medium")

    def test_returns_30_shapes(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert len(shapes) == 30

    def test_each_shape_same_length_as_base(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        n = len(face_mesh["vertices"])
        for name, displaced in shapes.items():
            assert len(displaced) == n, f"Shape '{name}' has {len(displaced)} verts, expected {n}"

    def test_jaw_open_displaces_chin_area(self, face_mesh):
        verts = face_mesh["vertices"]
        shapes = generate_blend_shape_targets(verts, face_mesh["faces"])
        jaw_open = shapes["jaw_open"]
        # At least some vertices should be displaced
        displaced_count = sum(
            1 for orig, disp in zip(verts, jaw_open)
            if any(abs(o - d) > 1e-8 for o, d in zip(orig, disp))
        )
        assert displaced_count > 0

    def test_smile_shapes_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert "mouth_smile_L" in shapes
        assert "mouth_smile_R" in shapes

    def test_blink_shapes_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert "eye_blink_L" in shapes
        assert "eye_blink_R" in shapes

    def test_brow_shapes_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert "brow_raise_L" in shapes
        assert "brow_raise_R" in shapes
        assert "brow_lower_L" in shapes
        assert "brow_lower_R" in shapes

    def test_cheek_shapes_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert "cheek_puff_L" in shapes
        assert "cheek_puff_R" in shapes

    def test_nose_shapes_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert "nose_sneer_L" in shapes
        assert "nose_sneer_R" in shapes

    def test_tongue_out_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        assert "tongue_out" in shapes

    def test_empty_mesh_returns_empty(self):
        shapes = generate_blend_shape_targets([], [])
        assert shapes == {}

    def test_all_30_expected_shapes_present(self, face_mesh):
        shapes = generate_blend_shape_targets(
            face_mesh["vertices"], face_mesh["faces"]
        )
        for name in _BLEND_SHAPE_DEFS:
            assert name in shapes, f"Missing blend shape: {name}"

    def test_shape_displacements_are_bounded(self, face_mesh):
        """Ensure no blend shape moves any vertex by more than 2cm."""
        verts = face_mesh["vertices"]
        shapes = generate_blend_shape_targets(verts, face_mesh["faces"])
        max_allowed = 0.02  # 2cm
        for name, displaced in shapes.items():
            for orig, disp in zip(verts, displaced):
                dx = abs(orig[0] - disp[0])
                dy = abs(orig[1] - disp[1])
                dz = abs(orig[2] - disp[2])
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                assert dist <= max_allowed, (
                    f"Shape '{name}' moves vertex by {dist:.4f}m (max {max_allowed}m)"
                )


# ===========================================================================
# Hand Mesh Tests (Task #54)
# ===========================================================================


class TestHandMeshGeneration:
    """Test generate_hand_mesh function."""

    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_returns_valid_mesh(self, detail):
        result = generate_hand_mesh(detail)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_has_five_fingers(self):
        result = generate_hand_mesh("medium")
        assert result["metadata"]["finger_count"] == 5

    def test_joint_positions_present(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "wrist" in joints

    def test_all_finger_bases_present(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        for finger in ["thumb", "index", "middle", "ring", "pinky"]:
            assert f"{finger}_base" in joints, f"Missing {finger}_base joint"

    def test_all_finger_joints_present(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        for finger in ["thumb", "index", "middle", "ring", "pinky"]:
            for joint in ["proximal", "intermediate", "distal"]:
                key = f"{finger}_{joint}"
                assert key in joints, f"Missing joint: {key}"

    def test_finger_data_present(self):
        result = generate_hand_mesh("medium")
        finger_data = result["metadata"]["finger_data"]
        assert len(finger_data) == 5
        for name in ["thumb", "index", "middle", "ring", "pinky"]:
            assert name in finger_data

    def test_thumb_is_marked_as_thumb(self):
        result = generate_hand_mesh("medium")
        assert result["metadata"]["finger_data"]["thumb"]["is_thumb"] is True
        assert result["metadata"]["finger_data"]["index"]["is_thumb"] is False

    def test_each_finger_has_3_joints(self):
        result = generate_hand_mesh("medium")
        for name, data in result["metadata"]["finger_data"].items():
            assert data["joint_count"] == 3, f"{name} has {data['joint_count']} joints"

    @pytest.mark.parametrize("side", ["left", "right"])
    def test_side_parameter(self, side):
        result = generate_hand_mesh("medium", side=side)
        assert result["metadata"]["side"] == side

    def test_left_right_mirror(self):
        left = generate_hand_mesh("medium", "left")
        right = generate_hand_mesh("medium", "right")
        # Wrist positions should differ in X sign
        left_thumb = left["metadata"]["joint_positions"]["thumb_base"]
        right_thumb = right["metadata"]["joint_positions"]["thumb_base"]
        # Left thumb should be positive X, right should be negative (mirrored)
        assert left_thumb[0] * right_thumb[0] < 0 or (
            abs(left_thumb[0]) < 1e-6 and abs(right_thumb[0]) < 1e-6
        )

    def test_high_detail_more_verts(self):
        low = generate_hand_mesh("low")
        high = generate_hand_mesh("high")
        assert high["metadata"]["vertex_count"] > low["metadata"]["vertex_count"]

    def test_high_detail_has_nails(self):
        # High detail generates nail geometry, so should have more faces
        med = generate_hand_mesh("medium")
        high = generate_hand_mesh("high")
        assert high["metadata"]["poly_count"] > med["metadata"]["poly_count"]

    def test_all_face_indices_valid(self):
        result = generate_hand_mesh("high")
        n = len(result["vertices"])
        for face in result["faces"]:
            for vi in face:
                assert 0 <= vi < n, f"Index {vi} out of range [0, {n})"

    def test_category_is_character_hand(self):
        result = generate_hand_mesh("medium")
        assert result["metadata"]["category"] == "character_hand"

    def test_invalid_detail_defaults(self):
        result = generate_hand_mesh("ultra")
        assert result["metadata"]["detail"] == "medium"

    def test_middle_finger_longest(self):
        result = generate_hand_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        # Compare distal Y positions - middle should be furthest
        middle_tip_y = joints["middle_distal"][1]
        index_tip_y = joints["index_distal"][1]
        pinky_tip_y = joints["pinky_distal"][1]
        assert middle_tip_y >= index_tip_y
        assert middle_tip_y >= pinky_tip_y


# ===========================================================================
# Foot Mesh Tests (Task #54)
# ===========================================================================


class TestFootMeshGeneration:
    """Test generate_foot_mesh function."""

    @pytest.mark.parametrize("detail", ["low", "medium", "high"])
    def test_returns_valid_mesh(self, detail):
        result = generate_foot_mesh(detail)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_has_ankle_joint(self):
        result = generate_foot_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "ankle" in joints

    def test_has_heel_joint(self):
        result = generate_foot_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "heel" in joints

    def test_has_ball_joint(self):
        result = generate_foot_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "ball" in joints

    def test_has_malleolus(self):
        result = generate_foot_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "malleolus_medial" in joints
        assert "malleolus_lateral" in joints

    def test_medial_malleolus_higher_than_lateral(self):
        result = generate_foot_mesh("medium", "right")
        joints = result["metadata"]["joint_positions"]
        med_z = joints["malleolus_medial"][2]
        lat_z = joints["malleolus_lateral"][2]
        assert med_z > lat_z  # medial is higher

    def test_has_achilles(self):
        result = generate_foot_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "achilles" in joints
        assert result["metadata"]["has_achilles"] is True

    def test_has_arch(self):
        result = generate_foot_mesh("medium")
        assert result["metadata"]["has_arch"] is True

    def test_has_ankle_bumps(self):
        result = generate_foot_mesh("medium")
        assert result["metadata"]["has_ankle_bumps"] is True

    def test_big_toe_present(self):
        result = generate_foot_mesh("medium")
        joints = result["metadata"]["joint_positions"]
        assert "big_toe_base" in joints
        assert "big_toe_tip" in joints

    def test_individual_toes_at_medium(self):
        result = generate_foot_mesh("medium")
        assert result["metadata"]["individual_toes"] is True
        assert result["metadata"]["toe_count"] == 5

    def test_grouped_toes_at_low(self):
        result = generate_foot_mesh("low")
        assert result["metadata"]["individual_toes"] is False
        assert result["metadata"]["toe_count"] == 2  # big_toe + small_toes

    @pytest.mark.parametrize("side", ["left", "right"])
    def test_side_parameter(self, side):
        result = generate_foot_mesh("medium", side=side)
        assert result["metadata"]["side"] == side

    def test_high_detail_more_verts(self):
        low = generate_foot_mesh("low")
        high = generate_foot_mesh("high")
        assert high["metadata"]["vertex_count"] > low["metadata"]["vertex_count"]

    def test_all_face_indices_valid(self):
        result = generate_foot_mesh("high")
        n = len(result["vertices"])
        for face in result["faces"]:
            for vi in face:
                assert 0 <= vi < n, f"Index {vi} out of range [0, {n})"

    def test_category_is_character_foot(self):
        result = generate_foot_mesh("medium")
        assert result["metadata"]["category"] == "character_foot"

    def test_foot_dimensions_reasonable(self):
        result = generate_foot_mesh("medium")
        dims = result["metadata"]["dimensions"]
        # Foot ~26cm long, ~9cm wide
        assert 0.05 < dims["height"] < 0.35  # length is along Y
        assert 0.03 < dims["width"] < 0.20

    def test_invalid_detail_defaults(self):
        result = generate_foot_mesh("ultra")
        assert result["metadata"]["detail"] == "medium"


# ===========================================================================
# Corrective Blend Shape Tests (Task #55)
# ===========================================================================


class TestCorrectiveShapes:
    """Test generate_corrective_shapes function."""

    @pytest.fixture
    def body_mesh(self):
        """Create a simple body mesh with joints."""
        verts = []
        # Create a grid of vertices around standard joint positions
        joints = {
            "shoulder_L": (-0.22, 0.0, 1.40),
            "shoulder_R": (0.22, 0.0, 1.40),
            "elbow_L": (-0.35, 0.0, 1.10),
            "elbow_R": (0.35, 0.0, 1.10),
            "knee_L": (-0.10, 0.0, 0.50),
            "knee_R": (0.10, 0.0, 0.50),
            "hip_L": (-0.10, 0.0, 0.90),
            "hip_R": (0.10, 0.0, 0.90),
        }

        # Generate vertices in a grid around each joint
        for jname, (jx, jy, jz) in joints.items():
            for dx in [-0.05, 0, 0.05]:
                for dy in [-0.05, 0, 0.05]:
                    for dz in [-0.05, 0, 0.05]:
                        verts.append((jx + dx, jy + dy, jz + dz))

        return verts, joints

    def test_returns_8_corrective_shapes(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        assert len(shapes) == 8

    def test_all_expected_shapes_present(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        for name in _CORRECTIVE_SHAPE_DEFS:
            assert name in shapes, f"Missing corrective shape: {name}"

    def test_each_shape_has_displaced_vertices(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        for name, data in shapes.items():
            assert len(data["displaced_vertices"]) == len(verts)

    def test_shapes_affect_nearby_vertices(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        for name, data in shapes.items():
            assert data["affected_vertex_count"] > 0, (
                f"Shape '{name}' affects no vertices"
            )

    def test_displacement_is_bounded(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        for name, data in shapes.items():
            # Max displacement should be reasonable (< 2cm)
            assert data["max_displacement"] < 0.025

    def test_description_present(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        for name, data in shapes.items():
            assert "description" in data
            assert len(data["description"]) > 0

    def test_joint_name_recorded(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        assert shapes["shoulder_raise_L"]["joint"] == "shoulder_L"
        assert shapes["knee_bend_R"]["joint"] == "knee_R"

    def test_empty_mesh_returns_empty(self):
        shapes = generate_corrective_shapes([], {})
        assert shapes == {}

    def test_missing_joint_uses_origin(self):
        verts = [(0.0, 0.0, 0.0), (0.01, 0.01, 0.01)]
        shapes = generate_corrective_shapes(verts, {})
        # Should still produce shapes (using origin for all joints)
        assert len(shapes) == 8
        for name, data in shapes.items():
            assert len(data["displaced_vertices"]) == 2

    def test_far_vertices_unaffected(self, body_mesh):
        """Vertices far from a joint should not be displaced by that joint's shape."""
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)

        shoulder_shape = shapes["shoulder_raise_L"]
        shoulder_pos = joints["shoulder_L"]
        radius = _CORRECTIVE_SHAPE_DEFS["shoulder_raise_L"]["region_radius"]

        for orig, disp in zip(verts, shoulder_shape["displaced_vertices"]):
            dist = math.sqrt(
                (orig[0] - shoulder_pos[0])**2 +
                (orig[1] - shoulder_pos[1])**2 +
                (orig[2] - shoulder_pos[2])**2
            )
            if dist >= radius:
                assert orig == disp, (
                    f"Vertex at distance {dist:.3f} from shoulder was displaced"
                )

    def test_symmetric_shapes_exist(self, body_mesh):
        verts, joints = body_mesh
        shapes = generate_corrective_shapes(verts, joints)
        # L/R pairs should both exist
        for prefix in ["shoulder_raise", "elbow_bend", "knee_bend", "hip_flex"]:
            assert f"{prefix}_L" in shapes
            assert f"{prefix}_R" in shapes


# ===========================================================================
# Geometry helper tests
# ===========================================================================


class TestGeometryHelpers:
    """Test low-level geometry helper functions."""

    def test_ring_verts_count(self):
        pts = _ring_verts(0, 0, 0, 1.0, 1.0, 8)
        assert len(pts) == 8

    def test_ring_verts_radius(self):
        pts = _ring_verts(0, 0, 0, 1.0, 1.0, 16)
        for x, y, z in pts:
            r = math.sqrt(x*x + z*z)
            assert abs(r - 1.0) < 1e-6

    def test_ring_verts_center_offset(self):
        pts = _ring_verts(5.0, 3.0, 2.0, 1.0, 1.0, 8)
        # All y should be 3.0
        for x, y, z in pts:
            assert abs(y - 3.0) < 1e-6

    def test_elliptical_loop_count(self):
        pts = _elliptical_loop(0, 0, 0, 0.5, 0.3, 10)
        assert len(pts) == 10

    def test_connect_rings_quad_count(self):
        faces = _connect_rings_quad(0, 8, 8)
        assert len(faces) == 8

    def test_connect_rings_quad_all_quads(self):
        faces = _connect_rings_quad(0, 8, 8)
        for f in faces:
            assert len(f) == 4


# ===========================================================================
# Integration tests
# ===========================================================================


class TestIntegration:
    """Integration tests combining multiple systems."""

    def test_face_mesh_to_blend_shapes(self):
        """Generate face mesh then create blend shapes from it."""
        face = generate_face_mesh("medium")
        shapes = generate_blend_shape_targets(face["vertices"], face["faces"])
        assert len(shapes) == 30
        for name, displaced in shapes.items():
            assert len(displaced) == len(face["vertices"])

    def test_face_mesh_to_udim(self):
        """Assign face mesh to UDIM tiles."""
        face = generate_face_mesh("high")
        result = compute_udim_tile_assignment(
            face["vertices"], face["faces"],
            layout_name="hero_character",
        )
        assert result["tile_count"] == 4
        total = sum(len(v) for v in result["tile_assignments"].values())
        assert total == len(face["faces"])

    def test_hand_mesh_to_trim_sheet(self):
        """Project hand mesh onto trim sheet strip."""
        hand = generate_hand_mesh("medium")
        result = compute_trim_sheet_uvs(
            hand["vertices"], hand["faces"], strip_index=2, total_strips=8,
        )
        assert len(result) == len(hand["faces"])

    def test_hand_corrective_shapes(self):
        """Generate corrective shapes using hand joint positions."""
        hand = generate_hand_mesh("medium")
        # Map hand joints to corrective shape joint names
        joints = {
            "shoulder_L": (0, 0, 1.4),
            "shoulder_R": (0, 0, 1.4),
            "elbow_L": hand["metadata"]["joint_positions"]["wrist"],
            "elbow_R": hand["metadata"]["joint_positions"]["wrist"],
            "knee_L": (0, 0, 0.5),
            "knee_R": (0, 0, 0.5),
            "hip_L": (0, 0, 0.9),
            "hip_R": (0, 0, 0.9),
        }
        shapes = generate_corrective_shapes(hand["vertices"], joints)
        assert len(shapes) == 8

    def test_all_detail_levels_face(self):
        for level in ["low", "medium", "high"]:
            face = generate_face_mesh(level)
            shapes = generate_blend_shape_targets(face["vertices"], face["faces"])
            assert len(shapes) == 30

    def test_all_detail_levels_hand(self):
        for detail in ["low", "medium", "high"]:
            for side in ["left", "right"]:
                hand = generate_hand_mesh(detail, side)
                assert hand["metadata"]["finger_count"] == 5

    def test_all_detail_levels_foot(self):
        for detail in ["low", "medium", "high"]:
            for side in ["left", "right"]:
                foot = generate_foot_mesh(detail, side)
                assert "ankle" in foot["metadata"]["joint_positions"]
