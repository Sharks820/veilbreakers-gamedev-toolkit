"""Tests for Gap #15 (vertex paint), Gap #17 (autonomous loop), Gap #20 (terrain chunking).

All tests are pure Python — no Blender dependency. Tests cover:
  - Paint weight falloff computation (SMOOTH, LINEAR, SHARP, CONSTANT)
  - Color blending modes (MIX, ADD, SUBTRACT, MULTIPLY)
  - UV-space paint weights
  - Mesh quality evaluation (poly count, degenerate faces, normal consistency)
  - Fix action selection (decimate, subdivide, repair, remesh, etc.)
  - Terrain chunk coverage (no gaps, correct count)
  - Chunk overlap width
  - LOD downsample resolution and vertex count ordering
  - Streaming distance progression
  - Neighbor chunk references for edge and interior chunks
  - Metadata export to JSON
"""

from __future__ import annotations

import json
import math

import pytest


# ===========================================================================
# Gap #15: Vertex Paint — pure-logic helpers
# ===========================================================================


class TestComputePaintWeights:
    """Tests for compute_paint_weights (world-space brush)."""

    def test_center_vertex_weight_is_one(self):
        """A vertex exactly at the brush center has weight 1.0."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(0.0, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "SMOOTH")
        assert len(result) == 1
        assert result[0][0] == 0
        assert result[0][1] == pytest.approx(1.0)

    def test_vertex_at_radius_weight_is_zero_smooth(self):
        """SMOOTH falloff: weight at exactly the radius boundary = 0.0."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(1.0, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "SMOOTH")
        # At t=1.0, smoothstep = 1.0, weight = 1.0 - 1.0 = 0.0
        assert len(result) == 1
        assert result[0][1] == pytest.approx(0.0, abs=1e-9)

    def test_vertex_at_radius_weight_is_zero_linear(self):
        """LINEAR falloff: weight at radius boundary = 0.0."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(2.0, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 2.0, "LINEAR")
        assert len(result) == 1
        assert result[0][1] == pytest.approx(0.0, abs=1e-9)

    def test_linear_midpoint_is_half(self):
        """LINEAR falloff at half radius should give weight 0.5."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(0.5, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "LINEAR")
        assert len(result) == 1
        assert result[0][1] == pytest.approx(0.5)

    def test_constant_falloff_is_one_everywhere(self):
        """CONSTANT falloff: weight = 1.0 for all vertices within radius."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (0.99, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "CONSTANT")
        assert len(result) == 3
        for _, w in result:
            assert w == pytest.approx(1.0)

    def test_sharp_falloff_drops_faster_than_linear(self):
        """SHARP falloff at midpoint is less than LINEAR's 0.5."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(0.5, 0.0, 0.0)]
        sharp = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "SHARP")
        linear = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "LINEAR")
        assert sharp[0][1] < linear[0][1]

    def test_vertex_outside_radius_excluded(self):
        """Vertices beyond the brush radius are not in the result."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(5.0, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "SMOOTH")
        assert len(result) == 0

    def test_zero_radius_returns_empty(self):
        """Zero-radius brush affects no vertices."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [(0.0, 0.0, 0.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 0.0, "SMOOTH")
        assert len(result) == 0

    def test_multiple_vertices_mixed_inclusion(self):
        """Only vertices within radius are returned."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        verts = [
            (0.0, 0.0, 0.0),   # inside
            (0.3, 0.0, 0.0),   # inside
            (2.0, 0.0, 0.0),   # outside
            (0.0, 0.0, 10.0),  # outside
        ]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 1.0, "LINEAR")
        indices = [idx for idx, _ in result]
        assert 0 in indices
        assert 1 in indices
        assert 2 not in indices
        assert 3 not in indices

    def test_3d_distance_calculation(self):
        """Brush distance is true 3D Euclidean distance."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights

        # Vertex at (1,1,1), distance from origin = sqrt(3) ~ 1.732
        verts = [(1.0, 1.0, 1.0)]
        result = compute_paint_weights(verts, (0.0, 0.0, 0.0), 2.0, "LINEAR")
        assert len(result) == 1
        expected_t = math.sqrt(3.0) / 2.0
        expected_w = 1.0 - expected_t
        assert result[0][1] == pytest.approx(expected_w, abs=1e-6)


class TestComputePaintWeightsUV:
    """Tests for compute_paint_weights_uv (UV-space brush)."""

    def test_uv_center_weight_is_one(self):
        """UV vertex at brush center has weight 1.0."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights_uv

        uvs = [(0.5, 0.5)]
        result = compute_paint_weights_uv(uvs, (0.5, 0.5), 0.1, "SMOOTH")
        assert len(result) == 1
        assert result[0][1] == pytest.approx(1.0)

    def test_uv_vertex_outside_radius(self):
        """UV vertex far from brush center is excluded."""
        from blender_addon.handlers.vertex_paint_live import compute_paint_weights_uv

        uvs = [(0.0, 0.0)]
        result = compute_paint_weights_uv(uvs, (1.0, 1.0), 0.1, "SMOOTH")
        assert len(result) == 0


class TestBlendColors:
    """Tests for blend_colors RGBA blending."""

    def test_mix_strength_zero_returns_existing(self):
        """MIX at strength=0 returns the existing color unchanged."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.5, 0.3, 0.1, 1.0)
        new_col = (1.0, 0.0, 0.0, 1.0)
        result = blend_colors(existing, new_col, 0.0, "MIX")
        for i in range(4):
            assert result[i] == pytest.approx(existing[i])

    def test_mix_strength_one_returns_new(self):
        """MIX at strength=1 returns the new color."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.5, 0.3, 0.1, 1.0)
        new_col = (1.0, 0.0, 0.0, 1.0)
        result = blend_colors(existing, new_col, 1.0, "MIX")
        for i in range(4):
            assert result[i] == pytest.approx(new_col[i])

    def test_mix_half_strength(self):
        """MIX at strength=0.5 gives midpoint between existing and new."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.0, 0.0, 0.0, 0.0)
        new_col = (1.0, 1.0, 1.0, 1.0)
        result = blend_colors(existing, new_col, 0.5, "MIX")
        for i in range(4):
            assert result[i] == pytest.approx(0.5)

    def test_add_blend_mode(self):
        """ADD mode adds new * strength to existing."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.3, 0.3, 0.3, 0.3)
        new_col = (0.2, 0.2, 0.2, 0.2)
        result = blend_colors(existing, new_col, 1.0, "ADD")
        for i in range(4):
            assert result[i] == pytest.approx(0.5)

    def test_add_clamps_to_one(self):
        """ADD mode clamps values above 1.0."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.8, 0.8, 0.8, 0.8)
        new_col = (0.5, 0.5, 0.5, 0.5)
        result = blend_colors(existing, new_col, 1.0, "ADD")
        for i in range(4):
            assert result[i] == pytest.approx(1.0)

    def test_subtract_blend_mode(self):
        """SUBTRACT mode subtracts new * strength from existing."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.5, 0.5, 0.5, 0.5)
        new_col = (0.2, 0.2, 0.2, 0.2)
        result = blend_colors(existing, new_col, 1.0, "SUBTRACT")
        for i in range(4):
            assert result[i] == pytest.approx(0.3)

    def test_subtract_clamps_to_zero(self):
        """SUBTRACT mode clamps values below 0.0."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.1, 0.1, 0.1, 0.1)
        new_col = (0.5, 0.5, 0.5, 0.5)
        result = blend_colors(existing, new_col, 1.0, "SUBTRACT")
        for i in range(4):
            assert result[i] == pytest.approx(0.0)

    def test_multiply_blend_mode(self):
        """MULTIPLY mode: existing * lerp(1.0, new, strength)."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.8, 0.8, 0.8, 0.8)
        new_col = (0.5, 0.5, 0.5, 0.5)
        # factor = 1.0 + (0.5 - 1.0) * 1.0 = 0.5
        # result = 0.8 * 0.5 = 0.4
        result = blend_colors(existing, new_col, 1.0, "MULTIPLY")
        for i in range(4):
            assert result[i] == pytest.approx(0.4)

    def test_multiply_strength_zero_returns_existing(self):
        """MULTIPLY at strength=0: factor=1.0, so result=existing."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        existing = (0.7, 0.7, 0.7, 0.7)
        new_col = (0.1, 0.1, 0.1, 0.1)
        result = blend_colors(existing, new_col, 0.0, "MULTIPLY")
        for i in range(4):
            assert result[i] == pytest.approx(0.7)

    def test_blend_returns_four_components(self):
        """Blend always returns a 4-tuple."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        result = blend_colors((0.5, 0.5, 0.5, 0.5), (1.0, 1.0, 1.0, 1.0), 0.5, "MIX")
        assert len(result) == 4

    def test_all_values_clamped_0_1(self):
        """All blend results are clamped to [0, 1]."""
        from blender_addon.handlers.vertex_paint_live import blend_colors

        # ADD that would exceed 1.0
        result = blend_colors((1.0, 1.0, 1.0, 1.0), (1.0, 1.0, 1.0, 1.0), 1.0, "ADD")
        for v in result:
            assert 0.0 <= v <= 1.0

        # SUBTRACT that would go below 0.0
        result = blend_colors((0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0), 1.0, "SUBTRACT")
        for v in result:
            assert 0.0 <= v <= 1.0


# ===========================================================================
# Gap #17: Autonomous Loop — pure-logic helpers
# ===========================================================================


class TestEvaluateMeshQuality:
    """Tests for evaluate_mesh_quality pure-logic evaluator."""

    def _make_quad_plane(self):
        """4-vertex quad plane for basic tests."""
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
        faces = [(0, 1, 2, 3)]
        return verts, faces

    def _make_degenerate_mesh(self):
        """Mesh with a degenerate (zero-area) face."""
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            # Degenerate: three collinear vertices
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
        ]
        faces = [
            (0, 1, 2, 3),     # valid quad
            (4, 5, 6),         # degenerate triangle (collinear)
        ]
        return verts, faces

    def test_poly_count_correct(self):
        """Evaluator reports correct poly count."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_quad_plane()
        q = evaluate_mesh_quality(verts, faces)
        assert q["poly_count"] == 1
        assert q["face_count"] == 1
        assert q["vertex_count"] == 4

    def test_quad_detected(self):
        """Single quad face is counted as quad."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_quad_plane()
        q = evaluate_mesh_quality(verts, faces)
        assert q["quad_count"] == 1
        assert q["tri_count"] == 0
        assert q["ngon_count"] == 0

    def test_detects_degenerate_faces(self):
        """Evaluator detects degenerate (zero-area) faces."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_degenerate_mesh()
        q = evaluate_mesh_quality(verts, faces)
        assert q["has_degenerate_faces"] is True
        assert q["degenerate_face_count"] >= 1

    def test_clean_mesh_no_degenerate(self):
        """Clean quad plane has no degenerate faces."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_quad_plane()
        q = evaluate_mesh_quality(verts, faces)
        assert q["has_degenerate_faces"] is False

    def test_topology_grade_is_string(self):
        """Topology grade is a single character A-F."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_quad_plane()
        q = evaluate_mesh_quality(verts, faces)
        assert q["topology_grade"] in ("A", "B", "C", "D", "E", "F")

    def test_clean_quad_gets_expected_grade(self):
        """A single quad has boundary edges (non-manifold), so grade is D.

        This is correct: a lone quad's 4 edges are each shared by only 1
        face, which counts as non-manifold in the grading rubric.  A fully
        closed mesh (e.g., a cube) is needed for A/B grades.
        """
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_quad_plane()
        q = evaluate_mesh_quality(verts, faces)
        # Boundary edges -> non_manifold > 0 -> grade D
        assert q["topology_grade"] == "D"

    def test_closed_quad_mesh_gets_good_grade(self):
        """A closed box (all edges shared by 2 faces) gets A or B grade."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        # Unit cube: 8 vertices, 6 quad faces, all edges shared by 2 faces
        verts = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1,  1), (1, -1,  1), (1, 1,  1), (-1, 1,  1),
        ]
        faces = [
            (0, 1, 2, 3), (4, 7, 6, 5),
            (0, 3, 7, 4), (1, 5, 6, 2),
            (0, 4, 5, 1), (3, 2, 6, 7),
        ]
        q = evaluate_mesh_quality(verts, faces)
        assert q["topology_grade"] in ("A", "B")

    def test_normal_consistency_perfect_for_flat(self):
        """A flat plane has perfect normal consistency (1.0)."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        # Two coplanar quads sharing an edge
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (2.0, 1.0, 0.0),
        ]
        faces = [(0, 1, 4, 3), (1, 2, 5, 4)]
        q = evaluate_mesh_quality(verts, faces)
        assert q["normal_consistency"] == pytest.approx(1.0, abs=0.01)

    def test_uv_coverage_computed_when_provided(self):
        """UV coverage is computed when UV coords are provided."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        q = evaluate_mesh_quality(verts, faces, uvs=uvs)
        assert q["uv_coverage"] == pytest.approx(1.0)

    def test_uv_coverage_zero_without_uvs(self):
        """UV coverage is 0.0 when no UVs provided."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        verts, faces = self._make_quad_plane()
        q = evaluate_mesh_quality(verts, faces)
        assert q["uv_coverage"] == 0.0

    def test_non_manifold_detection(self):
        """Non-manifold edges (shared by 1 face only) are detected."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        # Single face = all boundary edges (each shared by 1 face = non-manifold)
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        q = evaluate_mesh_quality(verts, faces)
        # Boundary edges of a single face are shared by only 1 face
        assert q["has_non_manifold"] is True

    def test_empty_mesh(self):
        """Empty mesh returns zero counts."""
        from blender_addon.handlers.autonomous_loop import evaluate_mesh_quality

        q = evaluate_mesh_quality([], [])
        assert q["poly_count"] == 0
        assert q["vertex_count"] == 0
        assert q["face_count"] == 0


class TestSelectFixAction:
    """Tests for select_fix_action decision logic."""

    def test_decimate_when_over_poly_budget(self):
        """Selects 'decimate' when poly count exceeds max_poly_count."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 10000, "has_non_manifold": False,
                    "has_degenerate_faces": False, "topology_grade": "A",
                    "normal_consistency": 1.0, "uv_coverage": 1.0}
        targets = {"max_poly_count": 5000}
        actions = ["repair", "decimate", "subdivide"]
        assert select_fix_action(quality, targets, actions) == "decimate"

    def test_subdivide_when_under_poly_budget(self):
        """Selects 'subdivide' when poly count is below min_poly_count."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 100, "has_non_manifold": False,
                    "has_degenerate_faces": False, "topology_grade": "A",
                    "normal_consistency": 1.0, "uv_coverage": 1.0}
        targets = {"min_poly_count": 500}
        actions = ["repair", "decimate", "subdivide"]
        assert select_fix_action(quality, targets, actions) == "subdivide"

    def test_repair_when_non_manifold(self):
        """Selects 'repair' when non-manifold edges exist."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 1000, "has_non_manifold": True,
                    "has_degenerate_faces": False, "topology_grade": "D",
                    "normal_consistency": 0.8, "uv_coverage": 1.0}
        targets = {"no_non_manifold": True}
        actions = ["repair", "remesh", "decimate"]
        assert select_fix_action(quality, targets, actions) == "repair"

    def test_repair_when_degenerate_faces(self):
        """Selects 'repair' when degenerate faces exist."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 1000, "has_non_manifold": False,
                    "has_degenerate_faces": True, "topology_grade": "C",
                    "normal_consistency": 1.0, "uv_coverage": 1.0}
        targets = {"no_degenerate_faces": True}
        actions = ["repair", "remesh", "decimate"]
        assert select_fix_action(quality, targets, actions) == "repair"

    def test_remesh_when_bad_topology(self):
        """Selects 'remesh' when topology grade is worse than target."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 1000, "has_non_manifold": False,
                    "has_degenerate_faces": False, "topology_grade": "E",
                    "normal_consistency": 1.0, "uv_coverage": 1.0}
        targets = {"min_topology_grade": "B"}
        actions = ["repair", "remesh", "decimate"]
        assert select_fix_action(quality, targets, actions) == "remesh"

    def test_returns_none_when_all_targets_met(self):
        """Returns None when all targets are satisfied."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 1000, "has_non_manifold": False,
                    "has_degenerate_faces": False, "topology_grade": "A",
                    "normal_consistency": 1.0, "uv_coverage": 1.0}
        targets = {"max_poly_count": 5000, "min_topology_grade": "B",
                    "no_non_manifold": True, "no_degenerate_faces": True}
        actions = ["repair", "remesh", "decimate", "subdivide"]
        assert select_fix_action(quality, targets, actions) is None

    def test_returns_none_with_empty_actions(self):
        """Returns None when no actions are available."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 99999, "has_non_manifold": True}
        targets = {"max_poly_count": 100}
        assert select_fix_action(quality, targets, []) is None

    def test_skips_unavailable_action(self):
        """If the ideal action is not in available_actions, tries next."""
        from blender_addon.handlers.autonomous_loop import select_fix_action

        quality = {"poly_count": 10000, "has_non_manifold": True,
                    "has_degenerate_faces": False, "topology_grade": "A",
                    "normal_consistency": 1.0, "uv_coverage": 1.0}
        # 'repair' not in the list — should not select it even though
        # non-manifold is the highest priority; falls through to decimate
        targets = {"no_non_manifold": True, "max_poly_count": 5000}
        actions = ["decimate", "subdivide"]
        result = select_fix_action(quality, targets, actions)
        assert result == "decimate"


# ===========================================================================
# Gap #20: Terrain Chunking
# ===========================================================================


def _make_heightmap(rows: int, cols: int, value: float = 0.5) -> list[list[float]]:
    """Create a flat heightmap for testing."""
    return [[value for _ in range(cols)] for _ in range(rows)]


def _make_gradient_heightmap(rows: int, cols: int) -> list[list[float]]:
    """Create a diagonal gradient heightmap."""
    return [
        [float(r + c) / float(rows + cols - 2) if (rows + cols - 2) > 0 else 0.0
         for c in range(cols)]
        for r in range(rows)
    ]


class TestComputeTerrainChunks:
    """Tests for compute_terrain_chunks main pipeline."""

    def test_1024_with_chunk64_produces_256_chunks(self):
        """1024x1024 heightmap with chunk_size=64 produces 16x16=256 chunks."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(1024, 1024)
        result = compute_terrain_chunks(hmap, chunk_size=64, overlap=1, lod_levels=4)
        assert result["metadata"]["total_chunks"] == 256
        assert result["metadata"]["grid_size"] == (16, 16)

    def test_chunks_cover_entire_heightmap(self):
        """All grid positions from (0,0) to (max_x, max_y) are present."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=32, overlap=1, lod_levels=2)
        grid_cols, grid_rows = result["metadata"]["grid_size"]
        assert grid_cols == 4
        assert grid_rows == 4

        # Verify all grid positions exist
        positions = {(c["grid_x"], c["grid_y"]) for c in result["chunks"]}
        expected = {(gx, gy) for gy in range(grid_rows) for gx in range(grid_cols)}
        assert positions == expected

    def test_chunk_overlap_width(self):
        """Chunk sub-heightmap includes overlap border samples."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(128, 128)
        overlap = 2
        chunk_size = 32
        result = compute_terrain_chunks(
            hmap, chunk_size=chunk_size, overlap=overlap, lod_levels=1
        )

        # Interior chunk should have chunk_size + 2*overlap samples
        # (overlap on both sides)
        interior_chunk = None
        for c in result["chunks"]:
            if c["grid_x"] > 0 and c["grid_y"] > 0:
                interior_chunk = c
                break

        assert interior_chunk is not None
        sub_hmap = interior_chunk["heightmap"]
        expected_size = chunk_size + 2 * overlap
        assert len(sub_hmap) == expected_size
        assert len(sub_hmap[0]) == expected_size

    def test_edge_chunk_overlap_clamped(self):
        """Edge chunks clamp overlap at heightmap boundaries."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=32, overlap=2, lod_levels=1)

        # Corner chunk at (0, 0) — no overlap on top/left edges
        corner = [c for c in result["chunks"] if c["grid_x"] == 0 and c["grid_y"] == 0][0]
        sub_hmap = corner["heightmap"]
        # Top-left: only overlap on right and bottom
        assert len(sub_hmap) == 32 + 2  # chunk_size + overlap (bottom only, clamped at top)
        assert len(sub_hmap[0]) == 32 + 2  # chunk_size + overlap (right only, clamped at left)

    def test_neighbor_references_interior(self):
        """Interior chunks have all 4 neighbors."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(192, 192)
        result = compute_terrain_chunks(hmap, chunk_size=64, overlap=1, lod_levels=2)

        # Chunk at (1, 1) should have all 4 neighbors
        center = [c for c in result["chunks"] if c["grid_x"] == 1 and c["grid_y"] == 1][0]
        neighbors = center["neighbor_chunks"]
        assert neighbors["north"] == (1, 0)
        assert neighbors["south"] == (1, 2)
        assert neighbors["west"] == (0, 1)
        assert neighbors["east"] == (2, 1)

    def test_neighbor_references_corner(self):
        """Corner chunks have None for out-of-bounds neighbors."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=64, overlap=1, lod_levels=2)

        # Chunk at (0, 0) — top-left corner
        corner = [c for c in result["chunks"] if c["grid_x"] == 0 and c["grid_y"] == 0][0]
        neighbors = corner["neighbor_chunks"]
        assert neighbors["north"] is None
        assert neighbors["west"] is None
        assert neighbors["south"] is not None
        assert neighbors["east"] is not None

    def test_lod_count_matches_requested(self):
        """Each chunk has the requested number of LOD levels."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(128, 128)
        lod_levels = 4
        result = compute_terrain_chunks(hmap, chunk_size=32, overlap=0, lod_levels=lod_levels)

        for chunk in result["chunks"]:
            assert len(chunk["lods"]) == lod_levels

    def test_lod0_more_vertices_than_lod3(self):
        """LOD0 has more vertices than LOD3 (higher detail)."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=64, overlap=0, lod_levels=4)

        chunk = result["chunks"][0]
        lod0_verts = chunk["lods"][0]["vertex_count"]
        lod3_verts = chunk["lods"][3]["vertex_count"]
        assert lod0_verts > lod3_verts

    def test_empty_heightmap(self):
        """Empty heightmap produces no chunks."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        result = compute_terrain_chunks([], chunk_size=64)
        assert result["metadata"]["total_chunks"] == 0
        assert len(result["chunks"]) == 0

    def test_metadata_has_required_keys(self):
        """Metadata dict contains all required keys."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks

        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=32)
        meta = result["metadata"]
        assert "total_chunks" in meta
        assert "grid_size" in meta
        assert "chunk_world_size" in meta
        assert "total_vertices_lod0" in meta
        assert "streaming_distance_lod" in meta


class TestComputeChunkLod:
    """Tests for compute_chunk_lod downsampling."""

    def test_downsample_halves_resolution(self):
        """Downsampling a 64x64 chunk to 32 produces 32x32."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        chunk = _make_heightmap(64, 64, value=0.5)
        result = compute_chunk_lod(chunk, 32)
        assert len(result) == 32
        assert len(result[0]) == 32

    def test_downsample_preserves_flat_value(self):
        """Flat heightmap keeps its value after downsampling."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        chunk = _make_heightmap(64, 64, value=0.7)
        result = compute_chunk_lod(chunk, 16)
        for row in result:
            for val in row:
                assert val == pytest.approx(0.7, abs=1e-6)

    def test_downsample_corners_match(self):
        """Corner values are preserved exactly after downsampling."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        chunk = _make_gradient_heightmap(64, 64)
        result = compute_chunk_lod(chunk, 8)
        # Top-left corner
        assert result[0][0] == pytest.approx(chunk[0][0], abs=1e-6)
        # Bottom-right corner
        assert result[-1][-1] == pytest.approx(chunk[-1][-1], abs=1e-6)

    def test_no_downsample_if_already_small(self):
        """If input is already <= target, return copy unchanged."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        chunk = _make_heightmap(4, 4, value=0.3)
        result = compute_chunk_lod(chunk, 8)
        assert len(result) == 4
        assert len(result[0]) == 4

    def test_empty_chunk(self):
        """Empty chunk returns empty."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        result = compute_chunk_lod([], 8)
        assert result == []

    def test_target_zero_returns_empty(self):
        """Target resolution of 0 returns empty."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        chunk = _make_heightmap(8, 8)
        result = compute_chunk_lod(chunk, 0)
        assert result == []


class TestComputeStreamingDistances:
    """Tests for compute_streaming_distances."""

    def test_distances_increase_with_lod(self):
        """Each LOD level has a larger streaming distance than the previous."""
        from blender_addon.handlers.terrain_chunking import compute_streaming_distances

        distances = compute_streaming_distances(64.0, 4)
        for i in range(1, 4):
            assert distances[i] > distances[i - 1]

    def test_lod0_distance_is_double_chunk_size(self):
        """LOD0 max distance = chunk_world_size * 2."""
        from blender_addon.handlers.terrain_chunking import compute_streaming_distances

        distances = compute_streaming_distances(100.0, 4)
        assert distances[0] == pytest.approx(200.0)

    def test_lod3_distance_is_sixteen_times_chunk_size(self):
        """LOD3 max distance = chunk_world_size * 16."""
        from blender_addon.handlers.terrain_chunking import compute_streaming_distances

        distances = compute_streaming_distances(100.0, 4)
        assert distances[3] == pytest.approx(1600.0)

    def test_correct_count(self):
        """Number of distance entries matches lod_levels."""
        from blender_addon.handlers.terrain_chunking import compute_streaming_distances

        distances = compute_streaming_distances(50.0, 6)
        assert len(distances) == 6

    def test_single_lod_level(self):
        """Single LOD level still works."""
        from blender_addon.handlers.terrain_chunking import compute_streaming_distances

        distances = compute_streaming_distances(32.0, 1)
        assert len(distances) == 1
        assert distances[0] == pytest.approx(64.0)


class TestExportChunksMetadata:
    """Tests for export_chunks_metadata JSON export."""

    def test_valid_json_output(self):
        """Export produces valid JSON."""
        from blender_addon.handlers.terrain_chunking import (
            compute_terrain_chunks, export_chunks_metadata,
        )

        hmap = _make_heightmap(64, 64)
        chunks_result = compute_terrain_chunks(hmap, chunk_size=32, lod_levels=2)
        json_str = export_chunks_metadata(chunks_result)
        parsed = json.loads(json_str)
        assert "terrain_metadata" in parsed
        assert "chunks" in parsed

    def test_no_heightmap_data_in_export(self):
        """Exported JSON does not contain raw heightmap arrays."""
        from blender_addon.handlers.terrain_chunking import (
            compute_terrain_chunks, export_chunks_metadata,
        )

        hmap = _make_heightmap(64, 64)
        chunks_result = compute_terrain_chunks(hmap, chunk_size=32, lod_levels=2)
        json_str = export_chunks_metadata(chunks_result)
        parsed = json.loads(json_str)
        for chunk in parsed["chunks"]:
            assert "heightmap" not in chunk

    def test_chunk_count_in_metadata(self):
        """Exported metadata reports correct total_chunks."""
        from blender_addon.handlers.terrain_chunking import (
            compute_terrain_chunks, export_chunks_metadata,
        )

        hmap = _make_heightmap(128, 128)
        chunks_result = compute_terrain_chunks(hmap, chunk_size=64, lod_levels=2)
        json_str = export_chunks_metadata(chunks_result)
        parsed = json.loads(json_str)
        assert parsed["terrain_metadata"]["total_chunks"] == 4
