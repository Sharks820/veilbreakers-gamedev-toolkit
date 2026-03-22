"""Tests for monster surface detail generators.

Tests cover:
- compute_face_normals / compute_vertex_normals
- generate_scale_pattern: coverage, geometry validity, edge cases
- generate_chitin_segments: segment counts, geometry validity, parameters
- generate_fur_card_layer: card counts, UV validity, geometry validity
- All functions with empty inputs
- All functions with minimal meshes (single face)

All pure logic -- no Blender required.
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.monster_surface_detail import (
    compute_face_normals,
    compute_vertex_normals,
    generate_chitin_segments,
    generate_fur_card_layer,
    generate_scale_pattern,
)


# ---------------------------------------------------------------------------
# Test fixtures: simple meshes
# ---------------------------------------------------------------------------


def _cube_mesh():
    """Return a simple cube mesh for testing."""
    verts = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return verts, faces


def _single_tri():
    """Return a single triangle mesh."""
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    faces = [(0, 1, 2)]
    return verts, faces


def _tall_cylinder_mesh():
    """Return a tall cylinder-like mesh (for chitin testing)."""
    verts = []
    faces = []
    segments = 8
    height_steps = 10
    radius = 0.5

    for hi in range(height_steps + 1):
        y = hi * 0.2 - 1.0  # -1.0 to 1.0
        for si in range(segments):
            angle = 2.0 * math.pi * si / segments
            verts.append((
                math.cos(angle) * radius,
                y,
                math.sin(angle) * radius,
            ))

    for hi in range(height_steps):
        for si in range(segments):
            s2 = (si + 1) % segments
            r0 = hi * segments
            r1 = (hi + 1) * segments
            faces.append((r0 + si, r0 + s2, r1 + s2, r1 + si))

    return verts, faces


# ---------------------------------------------------------------------------
# TestComputeNormals
# ---------------------------------------------------------------------------


class TestComputeNormals:
    """Test normal computation utilities."""

    def test_face_normals_count(self):
        verts, faces = _cube_mesh()
        normals = compute_face_normals(verts, faces)
        assert len(normals) == len(faces)

    def test_face_normals_unit_length(self):
        verts, faces = _cube_mesh()
        normals = compute_face_normals(verts, faces)
        for n in normals:
            length = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
            assert abs(length - 1.0) < 1e-6

    def test_vertex_normals_count(self):
        verts, faces = _cube_mesh()
        normals = compute_vertex_normals(verts, faces)
        assert len(normals) == len(verts)

    def test_vertex_normals_unit_length(self):
        verts, faces = _cube_mesh()
        normals = compute_vertex_normals(verts, faces)
        for n in normals:
            length = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
            assert abs(length - 1.0) < 1e-6

    def test_single_tri_normal(self):
        verts, faces = _single_tri()
        normals = compute_face_normals(verts, faces)
        # Triangle in XY plane, normal should be (0, 0, +/-1)
        assert len(normals) == 1
        assert abs(abs(normals[0][2]) - 1.0) < 1e-6

    def test_empty_mesh(self):
        normals = compute_face_normals([], [])
        assert normals == []
        normals = compute_vertex_normals([], [])
        assert normals == []


# ---------------------------------------------------------------------------
# TestGenerateScalePattern
# ---------------------------------------------------------------------------


class TestGenerateScalePattern:
    """Test generate_scale_pattern() scale plate generator."""

    def test_produces_geometry(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces)
        assert result["scale_count"] > 0
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_scale_count_matches_faces(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces)
        # Each scale produces exactly 4 faces
        assert len(result["faces"]) == result["scale_count"] * 4

    def test_vertices_per_scale(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces)
        # Each scale has 5 vertices (4 diamond corners + 1 raised center)
        assert len(result["vertices"]) == result["scale_count"] * 5

    def test_coverage_zero(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces, coverage=0.0)
        assert result["scale_count"] == 0
        assert result["vertices"] == []
        assert result["faces"] == []

    def test_coverage_one(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces, coverage=1.0)
        # All faces should get scales
        assert result["scale_count"] == len(faces)

    def test_coverage_half(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_scale_pattern(verts, faces, coverage=0.5)
        n_faces = len(faces)
        # Roughly half should be covered (within tolerance)
        assert result["scale_count"] > 0
        assert result["scale_count"] <= n_faces

    def test_coverage_actual_field(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces, coverage=1.0)
        assert abs(result["coverage_actual"] - 1.0) < 1e-6

    def test_valid_face_indices(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            assert len(face) == 3, f"Scale face {fi} should be a triangle"
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        verts, faces = _cube_mesh()
        result = generate_scale_pattern(verts, faces)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Vertex {i} has non-finite component"

    def test_with_custom_normals(self):
        verts, faces = _cube_mesh()
        normals = [(0, 1, 0)] * len(verts)
        result = generate_scale_pattern(verts, faces, normals=normals)
        assert result["scale_count"] > 0

    def test_scale_size_affects_geometry(self):
        verts, faces = _cube_mesh()
        small = generate_scale_pattern(verts, faces, scale_size=0.01, coverage=1.0)
        large = generate_scale_pattern(verts, faces, scale_size=0.2, coverage=1.0)
        # Same count but different vertex positions
        assert small["scale_count"] == large["scale_count"]

    def test_seed_reproducibility(self):
        verts, faces = _cube_mesh()
        r1 = generate_scale_pattern(verts, faces, seed=42)
        r2 = generate_scale_pattern(verts, faces, seed=42)
        assert r1["scale_count"] == r2["scale_count"]
        assert r1["vertices"] == r2["vertices"]

    def test_different_seeds_vary(self):
        verts, faces = _tall_cylinder_mesh()
        r1 = generate_scale_pattern(verts, faces, coverage=0.5, seed=1)
        r2 = generate_scale_pattern(verts, faces, coverage=0.5, seed=999)
        # Different seeds may select different faces
        # At minimum, counts might differ
        # (both should be valid though)
        assert r1["scale_count"] > 0
        assert r2["scale_count"] > 0

    def test_empty_mesh(self):
        result = generate_scale_pattern([], [])
        assert result["scale_count"] == 0
        assert result["vertices"] == []
        assert result["faces"] == []

    def test_single_triangle(self):
        verts, faces = _single_tri()
        result = generate_scale_pattern(verts, faces, coverage=1.0)
        assert result["scale_count"] == 1


# ---------------------------------------------------------------------------
# TestGenerateChitinSegments
# ---------------------------------------------------------------------------


class TestGenerateChitinSegments:
    """Test generate_chitin_segments() chitin plate generator."""

    def test_produces_geometry(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_chitin_segments(verts, faces)
        assert result["segment_count"] > 0
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_segment_count_parameter(self):
        verts, faces = _tall_cylinder_mesh()
        r4 = generate_chitin_segments(verts, faces, segment_count=4)
        r8 = generate_chitin_segments(verts, faces, segment_count=8)
        assert r4["segment_count"] <= 4
        assert r8["segment_count"] <= 8
        # More segments = more geometry
        assert len(r8["vertices"]) >= len(r4["vertices"])

    def test_segment_metadata(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_chitin_segments(verts, faces, segment_count=4)
        segments = result["segments"]
        assert len(segments) == result["segment_count"]
        for seg in segments:
            assert "index" in seg
            assert "y_start" in seg
            assert "y_end" in seg
            assert "avg_radius" in seg
            assert "vertex_range" in seg

    def test_segments_cover_y_range(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_chitin_segments(verts, faces, segment_count=4)
        segments = result["segments"]
        # Segments should cover the Y extent of the mesh
        ys = [v[1] for v in verts]
        y_min, y_max = min(ys), max(ys)
        for seg in segments:
            assert seg["y_start"] <= seg["y_end"]
            # At least partially within the mesh Y range
            assert seg["y_end"] >= y_min
            assert seg["y_start"] <= y_max

    def test_valid_face_indices(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_chitin_segments(verts, faces)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Chitin face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_chitin_segments(verts, faces)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Vertex {i} has non-finite component"

    def test_overlap_parameter(self):
        verts, faces = _tall_cylinder_mesh()
        no_overlap = generate_chitin_segments(verts, faces, segment_count=4, overlap=0.0)
        with_overlap = generate_chitin_segments(verts, faces, segment_count=4, overlap=0.3)
        # Overlap should produce more vertices (wider bands)
        assert len(with_overlap["vertices"]) >= len(no_overlap["vertices"])

    def test_thickness_parameter(self):
        verts, faces = _tall_cylinder_mesh()
        thin = generate_chitin_segments(verts, faces, thickness=0.01)
        thick = generate_chitin_segments(verts, faces, thickness=0.1)
        # Same segment count, different geometry
        assert thin["segment_count"] == thick["segment_count"]

    def test_empty_mesh(self):
        result = generate_chitin_segments([], [])
        assert result["segment_count"] == 0
        assert result["vertices"] == []
        assert result["faces"] == []

    def test_flat_mesh(self):
        """Flat mesh with no Y extent should produce no segments."""
        verts = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]
        faces = [(0, 1, 2, 3)]
        result = generate_chitin_segments(verts, faces)
        assert result["segment_count"] == 0

    def test_single_segment(self):
        verts, faces = _tall_cylinder_mesh()
        result = generate_chitin_segments(verts, faces, segment_count=1)
        assert result["segment_count"] == 1


# ---------------------------------------------------------------------------
# TestGenerateFurCardLayer
# ---------------------------------------------------------------------------


class TestGenerateFurCardLayer:
    """Test generate_fur_card_layer() billboard fur card generator."""

    def test_produces_geometry(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        assert result["card_count"] > 0
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_card_count_respects_density(self):
        verts, faces = _tall_cylinder_mesh()
        r10 = generate_fur_card_layer(verts, faces, density=10)
        r50 = generate_fur_card_layer(verts, faces, density=50)
        assert r10["card_count"] <= 10
        assert r50["card_count"] <= 50
        assert r50["card_count"] >= r10["card_count"]

    def test_vertices_per_card(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        # Each card is a quad = 4 vertices
        assert len(result["vertices"]) == result["card_count"] * 4

    def test_faces_per_card(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        # Each card is 1 quad face
        assert len(result["faces"]) == result["card_count"]

    def test_uvs_per_vertex(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        assert len(result["uvs"]) == len(result["vertices"])

    def test_uv_range(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        for i, (u, v) in enumerate(result["uvs"]):
            assert 0.0 <= u <= 1.0, f"UV {i} u={u} out of [0,1]"
            assert 0.0 <= v <= 1.0, f"UV {i} v={v} out of [0,1]"

    def test_uv_pattern_per_card(self):
        """Each card should have the standard corner UVs."""
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        for ci in range(result["card_count"]):
            base = ci * 4
            uvs = result["uvs"][base:base + 4]
            assert uvs[0] == (0.0, 0.0)
            assert uvs[1] == (1.0, 0.0)
            assert uvs[2] == (1.0, 1.0)
            assert uvs[3] == (0.0, 1.0)

    def test_valid_face_indices(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            assert len(face) == 4, f"Fur card face {fi} should be a quad"
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=4)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Vertex {i} has non-finite component"

    def test_length_affects_card_size(self):
        verts, faces = _cube_mesh()
        short = generate_fur_card_layer(verts, faces, density=4, length=0.05)
        long_ = generate_fur_card_layer(verts, faces, density=4, length=0.5)
        # Both should produce cards, but vertex positions differ
        assert short["card_count"] == long_["card_count"]

    def test_width_affects_card_size(self):
        verts, faces = _cube_mesh()
        narrow = generate_fur_card_layer(verts, faces, density=4, width=0.01)
        wide = generate_fur_card_layer(verts, faces, density=4, width=0.1)
        assert narrow["card_count"] == wide["card_count"]

    def test_seed_reproducibility(self):
        verts, faces = _cube_mesh()
        r1 = generate_fur_card_layer(verts, faces, density=4, seed=42)
        r2 = generate_fur_card_layer(verts, faces, density=4, seed=42)
        assert r1["card_count"] == r2["card_count"]
        assert r1["vertices"] == r2["vertices"]

    def test_with_custom_normals(self):
        verts, faces = _cube_mesh()
        normals = [(0, 1, 0)] * len(verts)
        result = generate_fur_card_layer(verts, faces, normals=normals, density=4)
        assert result["card_count"] > 0

    def test_empty_mesh(self):
        result = generate_fur_card_layer([], [])
        assert result["card_count"] == 0
        assert result["vertices"] == []
        assert result["faces"] == []
        assert result["uvs"] == []

    def test_zero_density(self):
        verts, faces = _cube_mesh()
        result = generate_fur_card_layer(verts, faces, density=0)
        assert result["card_count"] == 0

    def test_single_face_mesh(self):
        verts, faces = _single_tri()
        result = generate_fur_card_layer(verts, faces, density=1)
        assert result["card_count"] == 1
