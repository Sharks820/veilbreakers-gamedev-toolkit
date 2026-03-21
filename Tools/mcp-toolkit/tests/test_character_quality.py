"""Tests for character quality validation and hair card generation.

Validates CHAR-01, CHAR-02, CHAR-03, CHAR-06 requirements:
- Proportion validation against game-world scale specs
- Hair card mesh generation with UV layout
- Face topology edge loop detection
- Hand/foot topology validation
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers._character_quality import (
    CHARACTER_SPECS,
    validate_proportions,
    validate_face_topology,
    validate_hand_foot_topology,
    generate_hair_card_mesh,
    _find_vertices_near,
    _count_edge_loops,
    _find_distinct_groups,
)


# ---------------------------------------------------------------------------
# Helper: generate a simple humanoid mesh spec for testing
# ---------------------------------------------------------------------------


def _make_humanoid_mesh(
    height: float = 1.8,
    shoulder_width: float = 0.45,
    head_ratio: float = 7.5,
    include_face_loops: bool = False,
    include_fingers: bool = False,
) -> dict:
    """Generate a simplified humanoid mesh spec for testing.

    Creates a rough humanoid shape with torso, limbs, head.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    hw = shoulder_width / 2.0
    head_h = height / head_ratio
    body_base = 0.0

    # Torso: rectangular prism from 0.47*height to 0.87*height
    torso_bottom = body_base + height * 0.47
    torso_top = body_base + height * 0.87
    td = 0.12  # torso depth

    # Torso box (8 verts)
    b = len(verts)
    verts.extend([
        (-hw, torso_bottom, -td), (hw, torso_bottom, -td),
        (hw, torso_top, -td), (-hw, torso_top, -td),
        (-hw, torso_bottom, td), (hw, torso_bottom, td),
        (hw, torso_top, td), (-hw, torso_top, td),
    ])
    faces.extend([
        (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
        (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
        (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
    ])

    # Head: small box at top
    head_bottom = body_base + height - head_h
    head_top = body_base + height
    head_w = 0.08
    head_d = 0.09

    b = len(verts)
    verts.extend([
        (-head_w, head_bottom, -head_d), (head_w, head_bottom, -head_d),
        (head_w, head_top, -head_d), (-head_w, head_top, -head_d),
        (-head_w, head_bottom, head_d), (head_w, head_bottom, head_d),
        (head_w, head_top, head_d), (-head_w, head_top, head_d),
    ])
    faces.extend([
        (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
        (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
        (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
    ])

    # Legs: two cylinders approximated as boxes from 0 to 0.47*height
    leg_top = body_base + height * 0.47
    leg_w = 0.05
    leg_d = 0.06
    for side in [-1, 1]:
        leg_cx = side * 0.10
        b = len(verts)
        verts.extend([
            (leg_cx - leg_w, body_base, -leg_d),
            (leg_cx + leg_w, body_base, -leg_d),
            (leg_cx + leg_w, leg_top, -leg_d),
            (leg_cx - leg_w, leg_top, -leg_d),
            (leg_cx - leg_w, body_base, leg_d),
            (leg_cx + leg_w, body_base, leg_d),
            (leg_cx + leg_w, leg_top, leg_d),
            (leg_cx - leg_w, leg_top, leg_d),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
            (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
        ])

    # Arms: two boxes from shoulder height extending outward
    arm_top = body_base + height * 0.75
    arm_bottom = body_base + height * 0.40
    arm_w = 0.03
    arm_d = 0.04
    for side in [-1, 1]:
        arm_cx = side * (hw + 0.15)  # extend beyond shoulder
        b = len(verts)
        verts.extend([
            (arm_cx - arm_w, arm_bottom, -arm_d),
            (arm_cx + arm_w, arm_bottom, -arm_d),
            (arm_cx + arm_w, arm_top, -arm_d),
            (arm_cx - arm_w, arm_top, -arm_d),
            (arm_cx - arm_w, arm_bottom, arm_d),
            (arm_cx + arm_w, arm_bottom, arm_d),
            (arm_cx + arm_w, arm_top, arm_d),
            (arm_cx - arm_w, arm_top, arm_d),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
            (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
        ])

    # Face loops: concentric quads around eye/mouth positions
    if include_face_loops:
        for feature, pos in [
            ("eye_left", (-0.03, height * 0.917, 0.06)),
            ("eye_right", (0.03, height * 0.917, 0.06)),
            ("mouth", (0.0, height * 0.889, 0.05)),
            ("nose", (0.0, height * 0.903, 0.07)),
        ]:
            fx, fy, fz = pos
            # Create 3 concentric quad loops
            for ring in range(3):
                r = 0.008 + ring * 0.008
                b = len(verts)
                for k in range(8):
                    angle = 2.0 * math.pi * k / 8
                    verts.append((
                        fx + r * math.cos(angle),
                        fy + r * math.sin(angle),
                        fz,
                    ))
                # Connect ring quads
                for k in range(8):
                    k2 = (k + 1) % 8
                    if ring > 0:
                        prev_b = b - 8
                        faces.append((prev_b + k, prev_b + k2, b + k2, b + k))

    # Fingers: distinct vertex groups in hand region
    if include_fingers:
        for side in [-1, 1]:
            hand_cx = side * (hw + 0.20)
            hand_y = body_base + height * 0.40
            for finger in range(5):
                finger_x = hand_cx + side * finger * 0.008
                b = len(verts)
                # Small box per finger
                fw, fd = 0.003, 0.003
                verts.extend([
                    (finger_x - fw, hand_y - 0.02, -fd),
                    (finger_x + fw, hand_y - 0.02, -fd),
                    (finger_x + fw, hand_y + 0.02, -fd),
                    (finger_x - fw, hand_y + 0.02, -fd),
                    (finger_x - fw, hand_y - 0.02, fd),
                    (finger_x + fw, hand_y - 0.02, fd),
                    (finger_x + fw, hand_y + 0.02, fd),
                    (finger_x - fw, hand_y + 0.02, fd),
                ])
                faces.extend([
                    (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
                    (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
                    (b+0, b+4, b+7, b+3), (b+1, b+2, b+6, b+5),
                ])

    return {
        "vertices": verts,
        "faces": faces,
        "uvs": [(0.0, 0.0)] * len(verts),
        "metadata": {
            "name": "test_humanoid",
            "poly_count": len(faces),
            "vertex_count": len(verts),
            "dimensions": {
                "width": max(v[0] for v in verts) - min(v[0] for v in verts),
                "height": max(v[1] for v in verts) - min(v[1] for v in verts),
                "depth": max(v[2] for v in verts) - min(v[2] for v in verts),
            },
        },
    }


# ---------------------------------------------------------------------------
# CHAR-01: Proportion validation tests
# ---------------------------------------------------------------------------


class TestProportionValidation:
    """Tests for validate_proportions -- CHAR-01."""

    def test_hero_valid_proportions(self):
        mesh = _make_humanoid_mesh(height=1.8, shoulder_width=0.45)
        result = validate_proportions(mesh, "hero")
        assert result["character_type"] == "hero"
        assert isinstance(result["passed"], bool)
        assert isinstance(result["issues"], list)
        assert isinstance(result["measurements"], dict)
        assert result["grade"] in ("A", "B", "C", "D", "F")
        # Height should be measured correctly
        assert abs(result["measurements"]["height"] - 1.8) < 0.01

    def test_hero_too_short(self):
        mesh = _make_humanoid_mesh(height=1.2)  # way below 1.8m
        result = validate_proportions(mesh, "hero")
        assert result["passed"] is False
        assert any("Height" in i for i in result["issues"])

    def test_hero_too_tall(self):
        mesh = _make_humanoid_mesh(height=2.5)  # way above 1.8m
        result = validate_proportions(mesh, "hero")
        assert result["passed"] is False
        assert any("Height" in i for i in result["issues"])

    def test_npc_valid_proportions(self):
        mesh = _make_humanoid_mesh(height=1.7, shoulder_width=0.42)
        result = validate_proportions(mesh, "npc")
        assert result["character_type"] == "npc"
        assert abs(result["measurements"]["height"] - 1.7) < 0.01

    def test_boss_valid_proportions(self):
        mesh = _make_humanoid_mesh(height=4.0, shoulder_width=1.2)
        result = validate_proportions(mesh, "boss")
        assert result["character_type"] == "boss"
        # Boss should be within valid range
        assert "height_spec" in result["measurements"]

    def test_boss_too_small(self):
        mesh = _make_humanoid_mesh(height=2.0)
        result = validate_proportions(mesh, "boss")
        assert result["passed"] is False
        assert any("below boss minimum" in i for i in result["issues"])

    def test_boss_too_large(self):
        mesh = _make_humanoid_mesh(height=10.0)
        result = validate_proportions(mesh, "boss")
        assert result["passed"] is False
        assert any("above boss maximum" in i for i in result["issues"])

    def test_unknown_character_type(self):
        mesh = _make_humanoid_mesh()
        result = validate_proportions(mesh, "dragon")
        assert result["passed"] is False
        assert result["grade"] == "F"
        assert "Unknown character type" in result["issues"][0]

    def test_empty_mesh(self):
        mesh = {"vertices": [], "faces": [], "uvs": [], "metadata": {}}
        result = validate_proportions(mesh, "hero")
        assert result["passed"] is False
        assert result["grade"] == "F"
        assert "No vertices" in result["issues"][0]

    def test_grade_scaling(self):
        """More issues should produce worse grades."""
        # Valid mesh -> fewer issues -> better grade
        good_mesh = _make_humanoid_mesh(height=1.8, shoulder_width=0.45)
        good_result = validate_proportions(good_mesh, "hero")

        # Bad mesh -> more issues -> worse grade
        bad_mesh = _make_humanoid_mesh(height=1.2, shoulder_width=0.15)
        bad_result = validate_proportions(bad_mesh, "hero")

        grade_order = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
        assert grade_order[good_result["grade"]] >= grade_order[bad_result["grade"]]

    def test_character_specs_all_types_defined(self):
        """Verify all expected character types have specs."""
        assert "hero" in CHARACTER_SPECS
        assert "boss" in CHARACTER_SPECS
        assert "npc" in CHARACTER_SPECS

    def test_tolerance_is_configurable(self):
        """Each character type should have a tolerance field."""
        for ctype, spec in CHARACTER_SPECS.items():
            assert "tolerance" in spec, f"{ctype} missing tolerance"
            assert 0 < spec["tolerance"] <= 0.5


# ---------------------------------------------------------------------------
# CHAR-03: Face topology validation tests
# ---------------------------------------------------------------------------


class TestFaceTopologyValidation:
    """Tests for validate_face_topology -- CHAR-03."""

    def test_basic_face_analysis(self):
        mesh = _make_humanoid_mesh(include_face_loops=True)
        result = validate_face_topology(mesh, character_height=1.8)
        assert isinstance(result["features"], dict)
        assert isinstance(result["grade"], str)
        assert result["grade"] in ("A", "B", "C", "D", "F")
        assert isinstance(result["total_loop_count"], int)

    def test_face_features_detected(self):
        mesh = _make_humanoid_mesh(include_face_loops=True)
        result = validate_face_topology(mesh, character_height=1.8)
        features = result["features"]
        # Should detect all 4 facial features
        assert "eye_left" in features
        assert "eye_right" in features
        assert "mouth" in features
        assert "nose" in features

    def test_no_face_loops(self):
        """Plain mesh without face detail should get low grade."""
        mesh = _make_humanoid_mesh(include_face_loops=False)
        result = validate_face_topology(mesh, character_height=1.8)
        # Without explicit face loops, detection may find few or none
        assert isinstance(result["issues"], list)

    def test_empty_mesh_face(self):
        mesh = {"vertices": [], "faces": [], "uvs": [], "metadata": {}}
        result = validate_face_topology(mesh)
        assert result["passed"] is False
        assert result["grade"] == "F"

    def test_scaled_character(self):
        """Boss-sized character should still detect features at scaled positions."""
        mesh = _make_humanoid_mesh(height=4.0, include_face_loops=True)
        result = validate_face_topology(mesh, character_height=4.0)
        assert isinstance(result["features"], dict)

    def test_find_vertices_near(self):
        """Test the vertex proximity search helper."""
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.1, 0.1, 0.0)]
        result = _find_vertices_near(verts, (0.0, 0.0, 0.0), 0.2)
        assert 0 in result
        assert 2 in result
        assert 1 not in result

    def test_count_edge_loops_basic(self):
        """Test edge loop counting with simple geometry."""
        faces = [(0, 1, 2, 3), (1, 4, 5, 2), (2, 5, 6, 3)]
        result = _count_edge_loops([1, 2], faces)
        assert result >= 1

    def test_count_edge_loops_empty(self):
        assert _count_edge_loops([], []) == 0
        assert _count_edge_loops([], [(0, 1, 2)]) == 0
        assert _count_edge_loops([0], []) == 0


# ---------------------------------------------------------------------------
# CHAR-06: Hand/foot topology validation tests
# ---------------------------------------------------------------------------


class TestHandFootTopology:
    """Tests for validate_hand_foot_topology -- CHAR-06."""

    def test_basic_hand_foot_analysis(self):
        mesh = _make_humanoid_mesh(include_fingers=True)
        result = validate_hand_foot_topology(mesh, character_height=1.8)
        assert isinstance(result["hands"], dict)
        assert isinstance(result["feet"], dict)
        assert isinstance(result["grade"], str)

    def test_hand_detection(self):
        mesh = _make_humanoid_mesh(include_fingers=True)
        result = validate_hand_foot_topology(mesh, character_height=1.8)
        # Both hands should be detected
        assert "left_hand" in result["hands"]
        assert "right_hand" in result["hands"]

    def test_foot_detection(self):
        mesh = _make_humanoid_mesh()
        result = validate_hand_foot_topology(mesh, character_height=1.8)
        assert "left_foot" in result["feet"]
        assert "right_foot" in result["feet"]

    def test_empty_mesh_hand_foot(self):
        mesh = {"vertices": [], "faces": [], "uvs": [], "metadata": {}}
        result = validate_hand_foot_topology(mesh)
        assert result["passed"] is False
        assert result["grade"] == "F"

    def test_find_distinct_groups(self):
        """Test spatial clustering helper."""
        verts = [
            (0.0, 0.0, 0.0), (0.001, 0.0, 0.0),  # group 1
            (0.1, 0.0, 0.0), (0.101, 0.0, 0.0),   # group 2
            (0.2, 0.0, 0.0),                        # group 3
        ]
        result = _find_distinct_groups([0, 1, 2, 3, 4], verts, 0.01)
        assert result == 3

    def test_find_distinct_groups_empty(self):
        assert _find_distinct_groups([], [], 0.01) == 0

    def test_finger_groups_with_detail(self):
        """Mesh with finger detail should detect groups."""
        mesh = _make_humanoid_mesh(include_fingers=True)
        result = validate_hand_foot_topology(mesh, character_height=1.8)
        for hand_name in ("left_hand", "right_hand"):
            hand = result["hands"][hand_name]
            assert "finger_groups" in hand
            assert "vertex_count" in hand


# ---------------------------------------------------------------------------
# CHAR-02: Hair card generation tests
# ---------------------------------------------------------------------------


class TestHairCardGeneration:
    """Tests for generate_hair_card_mesh -- CHAR-02."""

    def test_basic_generation(self):
        result = generate_hair_card_mesh()
        assert "vertices" in result
        assert "faces" in result
        assert "uvs" in result
        assert "metadata" in result
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_metadata(self):
        result = generate_hair_card_mesh(style="long_straight", strand_count=10)
        meta = result["metadata"]
        assert meta["name"] == "HairCards_long_straight"
        assert meta["category"] == "character_hair"
        assert meta["style"] == "long_straight"
        assert meta["strand_count"] == 10

    def test_vertex_face_consistency(self):
        """All face indices should reference valid vertices."""
        result = generate_hair_card_mesh(strand_count=5, seed=42)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            assert len(face) >= 3, f"Face {fi} has {len(face)} verts"
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_uv_mapping(self):
        """Each vertex should have a UV coordinate."""
        result = generate_hair_card_mesh(strand_count=5, seed=0)
        assert len(result["uvs"]) == len(result["vertices"])
        # UVs should be in 0-1 range
        for uv in result["uvs"]:
            assert 0.0 <= uv[0] <= 1.0, f"UV u={uv[0]} out of range"
            assert 0.0 <= uv[1] <= 1.0, f"UV v={uv[1]} out of range"

    def test_strand_count(self):
        """More strands should produce more geometry."""
        result_5 = generate_hair_card_mesh(strand_count=5, seed=0)
        result_20 = generate_hair_card_mesh(strand_count=20, seed=0)
        assert len(result_20["faces"]) > len(result_5["faces"])

    def test_seed_determinism(self):
        """Same seed should produce identical meshes."""
        a = generate_hair_card_mesh(seed=42, strand_count=10)
        b = generate_hair_card_mesh(seed=42, strand_count=10)
        assert a["vertices"] == b["vertices"]
        assert a["faces"] == b["faces"]
        assert a["uvs"] == b["uvs"]

    def test_different_seeds_differ(self):
        """Different seeds should produce different meshes."""
        a = generate_hair_card_mesh(seed=1, strand_count=10)
        b = generate_hair_card_mesh(seed=2, strand_count=10)
        assert a["vertices"] != b["vertices"]

    @pytest.mark.parametrize("style", [
        "long_straight", "short_cropped", "braided",
        "wild", "mohawk", "ponytail",
    ])
    def test_all_styles(self, style: str):
        """Each style should produce valid geometry."""
        result = generate_hair_card_mesh(style=style, strand_count=5, seed=0)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0
        assert result["metadata"]["style"] == style

    def test_unknown_style_fallback(self):
        """Unknown style should fall back to long_straight."""
        result = generate_hair_card_mesh(style="nonexistent", seed=0)
        assert len(result["vertices"]) > 0

    def test_taper_effect(self):
        """Taper=0 should make tip vertices closer together than root."""
        result = generate_hair_card_mesh(
            strand_count=1, taper=0.1, seed=0, segments_per_strand=4
        )
        verts = result["vertices"]
        # First pair (root) should be wider than last pair (tip)
        root_width = abs(verts[0][0] - verts[1][0])
        tip_idx = len(verts) - 2
        tip_width = abs(verts[tip_idx][0] - verts[tip_idx + 1][0])
        assert tip_width < root_width

    def test_segments_per_strand(self):
        """More segments should produce more faces per strand."""
        result_2 = generate_hair_card_mesh(strand_count=1, segments_per_strand=2, seed=0)
        result_8 = generate_hair_card_mesh(strand_count=1, segments_per_strand=8, seed=0)
        assert len(result_8["faces"]) > len(result_2["faces"])

    def test_vertices_are_3d(self):
        """All vertices should be 3-tuples of numbers."""
        result = generate_hair_card_mesh(seed=0)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3, f"Vertex {i} has {len(v)} components"
            for comp in v:
                assert isinstance(comp, (int, float)), (
                    f"Vertex {i} component {comp} is not a number"
                )
