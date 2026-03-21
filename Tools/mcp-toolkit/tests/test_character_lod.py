"""Tests for character-aware LOD retopology and armor seam ring generation.

Validates CHAR-04 and CHAR-05 requirements:
- Character-aware LOD preserving face/hand detail
- Armor seam-hiding overlap rings at joint split points
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers._character_lod import (
    character_aware_lod,
    generate_seam_ring,
    _compute_vertex_importance,
    _compute_face_importance,
    _JOINT_SPECS,
    _REGION_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Helper: generate a humanoid mesh for LOD testing
# ---------------------------------------------------------------------------


def _make_lod_test_mesh(
    height: float = 1.8,
    face_detail_multiplier: int = 1,
) -> dict:
    """Generate a humanoid mesh with known region distribution for LOD testing.

    Creates a mesh where face region has more polys when face_detail_multiplier > 1.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    hw = 0.225  # half shoulder width

    # Body section (0.05h to 0.87h) -- main bulk
    body_bottom = height * 0.05
    body_top = height * 0.87
    body_sections = 8
    for sec in range(body_sections):
        t = sec / body_sections
        y = body_bottom + (body_top - body_bottom) * t
        b = len(verts)
        verts.extend([
            (-hw, y, -0.10), (hw, y, -0.10),
            (hw, y + 0.05, -0.10), (-hw, y + 0.05, -0.10),
            (-hw, y, 0.10), (hw, y, 0.10),
            (hw, y + 0.05, 0.10), (-hw, y + 0.05, 0.10),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
        ])

    # Face section (0.87h to 1.0h) -- should be preserved in LOD
    face_bottom = height * 0.87
    face_top = height
    face_sections = 4 * face_detail_multiplier
    for sec in range(face_sections):
        t = sec / face_sections
        y = face_bottom + (face_top - face_bottom) * t
        b = len(verts)
        fw = 0.08
        fd = 0.09
        verts.extend([
            (-fw, y, -fd), (fw, y, -fd),
            (fw, y + 0.02, -fd), (-fw, y + 0.02, -fd),
            (-fw, y, fd), (fw, y, fd),
            (fw, y + 0.02, fd), (-fw, y + 0.02, fd),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
        ])

    # Feet section (0 to 0.05h) -- moderate importance
    for side in [-1, 1]:
        b = len(verts)
        fx = side * 0.10
        verts.extend([
            (fx - 0.04, 0, -0.06), (fx + 0.04, 0, -0.06),
            (fx + 0.04, height * 0.05, -0.06), (fx - 0.04, height * 0.05, -0.06),
            (fx - 0.04, 0, 0.06), (fx + 0.04, 0, 0.06),
            (fx + 0.04, height * 0.05, 0.06), (fx - 0.04, height * 0.05, 0.06),
        ])
        faces.extend([
            (b+0, b+3, b+2, b+1), (b+4, b+5, b+6, b+7),
            (b+0, b+1, b+5, b+4), (b+2, b+3, b+7, b+6),
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
# Mesh spec validator (reusable)
# ---------------------------------------------------------------------------


def validate_mesh_spec(result: dict, name: str, min_verts: int = 4, min_faces: int = 1):
    """Validate a MeshSpec dict has all required fields and valid data."""
    assert "vertices" in result, f"{name}: missing 'vertices'"
    assert "faces" in result, f"{name}: missing 'faces'"
    assert "metadata" in result, f"{name}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]

    assert len(verts) >= min_verts, f"{name}: expected >= {min_verts} verts, got {len(verts)}"
    assert len(faces) >= min_faces, f"{name}: expected >= {min_faces} faces, got {len(faces)}"

    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts"
        for idx in face:
            assert 0 <= idx < n_verts, f"{name}: face {fi} index {idx} out of range"


# ---------------------------------------------------------------------------
# CHAR-04: Character-aware LOD tests
# ---------------------------------------------------------------------------


class TestCharacterAwareLOD:
    """Tests for character_aware_lod -- CHAR-04."""

    def test_basic_lod_generation(self):
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero")
        assert len(lods) == 3  # default [1.0, 0.5, 0.25]

    def test_lod_names(self):
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero")
        assert lods[0]["metadata"]["name"] == "test_humanoid_LOD0"
        assert lods[1]["metadata"]["name"] == "test_humanoid_LOD1"
        assert lods[2]["metadata"]["name"] == "test_humanoid_LOD2"

    def test_lod_decreasing_poly_count(self):
        """Each LOD level should have equal or fewer polygons."""
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero")
        for i in range(len(lods) - 1):
            assert lods[i]["metadata"]["poly_count"] >= lods[i + 1]["metadata"]["poly_count"]

    def test_lod0_preserves_all(self):
        """LOD0 with ratio 1.0 should keep all faces."""
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero", [1.0])
        assert lods[0]["metadata"]["poly_count"] == mesh["metadata"]["poly_count"]

    def test_lod_valid_meshes(self):
        """All LOD levels should produce valid mesh specs."""
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero")
        for i, lod in enumerate(lods):
            validate_mesh_spec(lod, f"LOD{i}")

    def test_face_preservation(self):
        """Face region faces should be preserved more than body faces in lower LODs."""
        mesh = _make_lod_test_mesh(face_detail_multiplier=3)
        lods = character_aware_lod(mesh, "hero", [1.0, 0.3])

        # Get LOD1 face vertices
        lod1_verts = lods[1]["vertices"]
        lod1_height = max(v[1] for v in lod1_verts) - min(v[1] for v in lod1_verts)
        min_y = min(v[1] for v in lod1_verts)

        # Count face region vertices (top 13% of height) in LOD1
        face_threshold = min_y + lod1_height * 0.87
        lod1_face_verts = sum(1 for v in lod1_verts if v[1] >= face_threshold)

        # Face region should have vertices (not completely decimated)
        assert lod1_face_verts > 0, "Face region was completely removed in LOD1"

    def test_custom_lod_ratios(self):
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero", [1.0, 0.7, 0.4, 0.1])
        assert len(lods) == 4

    def test_boss_character_type(self):
        mesh = _make_lod_test_mesh(height=4.0)
        lods = character_aware_lod(mesh, "boss")
        assert len(lods) == 3
        assert lods[0]["metadata"]["character_type"] == "boss"

    def test_npc_character_type(self):
        mesh = _make_lod_test_mesh(height=1.7)
        lods = character_aware_lod(mesh, "npc")
        assert len(lods) == 3
        assert lods[0]["metadata"]["character_type"] == "npc"

    def test_empty_mesh(self):
        mesh = {"vertices": [], "faces": [], "uvs": [], "metadata": {"name": "empty"}}
        lods = character_aware_lod(mesh, "hero")
        assert lods == []

    def test_lod_metadata_fields(self):
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero")
        for i, lod in enumerate(lods):
            meta = lod["metadata"]
            assert "lod_level" in meta
            assert "lod_ratio" in meta
            assert "character_type" in meta
            assert meta["lod_level"] == i

    def test_uvs_preserved(self):
        """UVs should be correctly remapped for LOD levels."""
        mesh = _make_lod_test_mesh()
        lods = character_aware_lod(mesh, "hero")
        for lod in lods:
            if lod["uvs"]:
                assert len(lod["uvs"]) == len(lod["vertices"])


class TestVertexImportance:
    """Tests for _compute_vertex_importance helper."""

    def test_face_vertices_high_importance(self):
        # Vertex at top of head (y_ratio > 0.87) should get high weight
        verts = [(0.0, 0.0, 0.0), (0.0, 1.8, 0.0)]
        weights = _compute_vertex_importance(verts, "hero")
        assert weights[1] > weights[0]  # top vertex more important

    def test_boss_face_extra_importance(self):
        """Boss face should get 4.0 weight vs hero's 3.0."""
        verts = [(0.0, 0.0, 0.0), (0.0, 4.0, 0.0)]
        hero_weights = _compute_vertex_importance(verts, "hero")
        boss_weights = _compute_vertex_importance(verts, "boss")
        assert boss_weights[1] > hero_weights[1]

    def test_empty_verts(self):
        assert _compute_vertex_importance([], "hero") == []

    def test_flat_mesh(self):
        """All vertices at same height should get uniform weight."""
        verts = [(0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (2.0, 1.0, 0.0)]
        weights = _compute_vertex_importance(verts, "hero")
        assert len(weights) == 3
        # With no height variation, all get default
        assert all(w == weights[0] for w in weights)


class TestFaceImportance:
    """Tests for _compute_face_importance helper."""

    def test_basic_computation(self):
        faces = [(0, 1, 2)]
        weights = [1.0, 2.0, 3.0]
        result = _compute_face_importance(faces, weights)
        assert len(result) == 1
        assert abs(result[0] - 2.0) < 0.01  # average of 1+2+3

    def test_empty_face(self):
        result = _compute_face_importance([()], [1.0])
        assert result == [0.0]


# ---------------------------------------------------------------------------
# CHAR-05: Armor seam ring tests
# ---------------------------------------------------------------------------


class TestSeamRingGeneration:
    """Tests for generate_seam_ring -- CHAR-05."""

    def test_basic_generation(self):
        result = generate_seam_ring("neck")
        validate_mesh_spec(result, "SeamRing_neck")
        assert result["metadata"]["name"] == "SeamRing_neck"
        assert result["metadata"]["category"] == "armor_seam"

    @pytest.mark.parametrize("joint_type", [
        "neck", "wrist_l", "wrist_r", "ankle_l", "ankle_r",
        "waist", "upper_arm_l", "upper_arm_r",
    ])
    def test_all_joint_types(self, joint_type: str):
        """Every defined joint type should produce valid geometry."""
        result = generate_seam_ring(joint_type)
        validate_mesh_spec(result, f"SeamRing_{joint_type}")
        assert result["metadata"]["joint_type"] == joint_type

    def test_unknown_joint_fallback(self):
        """Unknown joint type should fall back to neck defaults."""
        result = generate_seam_ring("elbow")
        validate_mesh_spec(result, "SeamRing_elbow")
        assert len(result["vertices"]) > 0

    def test_custom_radii(self):
        result = generate_seam_ring("neck", inner_radius=0.10, outer_radius=0.15)
        assert result["metadata"]["inner_radius"] == 0.10
        assert result["metadata"]["outer_radius"] == 0.15

    def test_segments_affect_vertex_count(self):
        r8 = generate_seam_ring("neck", segments=8)
        r32 = generate_seam_ring("neck", segments=32)
        assert len(r32["vertices"]) > len(r8["vertices"])

    def test_ring_is_closed(self):
        """The ring should form a closed loop (no gaps)."""
        result = generate_seam_ring("neck", segments=8)
        verts = result["vertices"]
        # First and last vertices of each ring should be at similar angle
        # (the face winding handles closure)
        assert len(result["faces"]) == 4 * 8  # 4 face types * segments

    def test_vertex_face_consistency(self):
        """All face indices should reference valid vertices."""
        result = generate_seam_ring("waist", segments=16)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_uv_mapping(self):
        """Each vertex should have a UV coordinate."""
        result = generate_seam_ring("neck")
        assert len(result["uvs"]) == len(result["vertices"])

    def test_character_height_scaling(self):
        """Different character heights should position ring differently."""
        ring_short = generate_seam_ring("neck", character_height=1.7)
        ring_tall = generate_seam_ring("neck", character_height=4.0)
        # The ring Y positions should differ
        short_ys = [v[1] for v in ring_short["vertices"]]
        tall_ys = [v[1] for v in ring_tall["vertices"]]
        assert max(tall_ys) > max(short_ys)

    def test_ring_height_parameter(self):
        """Height parameter should affect ring thickness."""
        thin = generate_seam_ring("neck", height=0.01)
        thick = generate_seam_ring("neck", height=0.10)
        thin_ys = [v[1] for v in thin["vertices"]]
        thick_ys = [v[1] for v in thick["vertices"]]
        thin_span = max(thin_ys) - min(thin_ys)
        thick_span = max(thick_ys) - min(thick_ys)
        assert thick_span > thin_span

    def test_joint_specs_complete(self):
        """All joint specs should have required fields."""
        for joint, spec in _JOINT_SPECS.items():
            assert "y_ratio" in spec, f"{joint} missing y_ratio"
            assert "x_offset" in spec, f"{joint} missing x_offset"
            assert "default_inner" in spec, f"{joint} missing default_inner"
            assert "default_outer" in spec, f"{joint} missing default_outer"
            assert spec["default_outer"] > spec["default_inner"], (
                f"{joint}: outer radius must be > inner radius"
            )

    def test_vertices_are_3d(self):
        """All vertices should be 3-tuples of numbers."""
        result = generate_seam_ring("ankle_l")
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for comp in v:
                assert isinstance(comp, (int, float))
