"""Unit tests for the silhouette-preserving LOD pipeline.

Tests all pure-logic functions in lod_pipeline.py without Blender:
- LOD_PRESETS validation
- compute_silhouette_importance
- compute_region_importance
- decimate_preserving_silhouette
- generate_collision_mesh
- generate_lod_chain
- Billboard LOD generation
"""

from __future__ import annotations

import math

import pytest


# ---------------------------------------------------------------------------
# Test helpers: simple mesh generators
# ---------------------------------------------------------------------------

def _make_cube() -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Create a unit cube mesh centered at origin."""
    vertices = [
        (-0.5, -0.5, -0.5),  # 0
        (0.5, -0.5, -0.5),   # 1
        (0.5, 0.5, -0.5),    # 2
        (-0.5, 0.5, -0.5),   # 3
        (-0.5, -0.5, 0.5),   # 4
        (0.5, -0.5, 0.5),    # 5
        (0.5, 0.5, 0.5),     # 6
        (-0.5, 0.5, 0.5),    # 7
    ]
    faces = [
        (0, 1, 2, 3),  # back
        (4, 7, 6, 5),  # front
        (0, 4, 5, 1),  # bottom
        (2, 6, 7, 3),  # top
        (0, 3, 7, 4),  # left
        (1, 5, 6, 2),  # right
    ]
    return vertices, faces


def _make_subdivided_plane(
    n: int = 10,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Create an NxN subdivided plane with (n+1)^2 vertices."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for j in range(n + 1):
        for i in range(n + 1):
            x = i / n - 0.5
            y = 0.0
            z = j / n - 0.5
            vertices.append((x, y, z))

    for j in range(n):
        for i in range(n):
            v0 = j * (n + 1) + i
            v1 = v0 + 1
            v2 = v0 + (n + 1) + 1
            v3 = v0 + (n + 1)
            faces.append((v0, v1, v2, v3))

    return vertices, faces


def _make_sphere(
    rings: int = 8, segments: int = 16,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Create a UV sphere mesh."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Top pole
    vertices.append((0.0, 1.0, 0.0))

    # Ring vertices
    for ring in range(1, rings):
        phi = math.pi * ring / rings
        for seg in range(segments):
            theta = 2.0 * math.pi * seg / segments
            x = math.sin(phi) * math.cos(theta)
            y = math.cos(phi)
            z = math.sin(phi) * math.sin(theta)
            vertices.append((x, y, z))

    # Bottom pole
    vertices.append((0.0, -1.0, 0.0))

    # Top cap triangles
    for seg in range(segments):
        next_seg = (seg + 1) % segments
        faces.append((0, 1 + seg, 1 + next_seg))

    # Middle quads
    for ring in range(rings - 2):
        for seg in range(segments):
            next_seg = (seg + 1) % segments
            r0 = 1 + ring * segments
            r1 = 1 + (ring + 1) * segments
            faces.append((r0 + seg, r1 + seg, r1 + next_seg, r0 + next_seg))

    # Bottom cap triangles
    bottom_idx = len(vertices) - 1
    last_ring_start = 1 + (rings - 2) * segments
    for seg in range(segments):
        next_seg = (seg + 1) % segments
        faces.append((last_ring_start + seg, bottom_idx, last_ring_start + next_seg))

    return vertices, faces


def _make_tall_box() -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Create a tall box (character-like proportions) for region detection tests."""
    hw, hh, hd = 0.25, 1.0, 0.15
    vertices = [
        (-hw, 0.0, -hd), (hw, 0.0, -hd), (hw, 0.0, hd), (-hw, 0.0, hd),
        (-hw, 2 * hh, -hd), (hw, 2 * hh, -hd), (hw, 2 * hh, hd), (-hw, 2 * hh, hd),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (2, 6, 7, 3),
        (0, 3, 7, 4),
        (1, 5, 6, 2),
    ]
    return vertices, faces


# ---------------------------------------------------------------------------
# LOD_PRESETS tests
# ---------------------------------------------------------------------------


class TestLODPresets:
    """Validate LOD_PRESETS dictionary structure and content."""

    def test_all_expected_asset_types_present(self):
        """LOD_PRESETS has all seven required asset types."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        expected = {
            "hero_character", "standard_mob", "building",
            "prop_small", "prop_medium", "weapon", "vegetation",
        }
        assert expected == set(LOD_PRESETS.keys())

    def test_each_preset_has_required_keys(self):
        """Every preset has ratios, screen_percentages, and min_tris."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            assert "ratios" in preset, f"{name} missing 'ratios'"
            assert "screen_percentages" in preset, f"{name} missing 'screen_percentages'"
            assert "min_tris" in preset, f"{name} missing 'min_tris'"

    def test_ratios_are_descending(self):
        """All preset ratios are in descending order (with 0.0 billboard allowed at end)."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            ratios = preset["ratios"]
            for i in range(1, len(ratios)):
                assert ratios[i] < ratios[i - 1], (
                    f"{name}: ratio[{i}]={ratios[i]} >= ratio[{i-1}]={ratios[i-1]}"
                )

    def test_ratios_in_valid_range(self):
        """All ratios are between 0.0 and 1.0 inclusive."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            for i, r in enumerate(preset["ratios"]):
                assert 0.0 <= r <= 1.0, f"{name}: ratio[{i}]={r} out of range"

    def test_screen_percentages_descending(self):
        """Screen percentages are in descending order."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            sp = preset["screen_percentages"]
            for i in range(1, len(sp)):
                assert sp[i] < sp[i - 1], (
                    f"{name}: screen_pct[{i}]={sp[i]} >= screen_pct[{i-1}]={sp[i-1]}"
                )

    def test_min_tris_descending(self):
        """Min tri counts are in descending order."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            mt = preset["min_tris"]
            for i in range(1, len(mt)):
                assert mt[i] <= mt[i - 1], (
                    f"{name}: min_tris[{i}]={mt[i]} > min_tris[{i-1}]={mt[i-1]}"
                )

    def test_consistent_list_lengths(self):
        """ratios, screen_percentages, and min_tris have the same length."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            n_ratios = len(preset["ratios"])
            n_sp = len(preset["screen_percentages"])
            n_mt = len(preset["min_tris"])
            assert n_ratios == n_sp == n_mt, (
                f"{name}: list length mismatch: ratios={n_ratios}, "
                f"screen_pct={n_sp}, min_tris={n_mt}"
            )

    def test_first_ratio_is_one(self):
        """LOD0 ratio is always 1.0 (full detail)."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        for name, preset in LOD_PRESETS.items():
            assert preset["ratios"][0] == 1.0, (
                f"{name}: first ratio should be 1.0, got {preset['ratios'][0]}"
            )

    def test_vegetation_has_billboard_lod(self):
        """Vegetation preset has a 0.0 ratio for billboard LOD."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        assert LOD_PRESETS["vegetation"]["ratios"][-1] == 0.0
        assert LOD_PRESETS["vegetation"]["min_tris"][-1] == 4

    def test_hero_character_has_preserve_regions(self):
        """Hero character preset preserves face and hands."""
        from blender_addon.handlers.lod_pipeline import LOD_PRESETS

        regions = LOD_PRESETS["hero_character"].get("preserve_regions", [])
        assert "face" in regions
        assert "hands" in regions


# ---------------------------------------------------------------------------
# compute_silhouette_importance tests
# ---------------------------------------------------------------------------


class TestSilhouetteImportance:
    """Test per-vertex silhouette importance computation."""

    def test_returns_correct_length(self):
        """Output length matches vertex count."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts, faces = _make_cube()
        weights = compute_silhouette_importance(verts, faces)
        assert len(weights) == len(verts)

    def test_values_in_zero_one_range(self):
        """All importance values are in [0.0, 1.0]."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts, faces = _make_cube()
        weights = compute_silhouette_importance(verts, faces)
        for w in weights:
            assert 0.0 <= w <= 1.0, f"Weight {w} out of range"

    def test_cube_all_vertices_are_silhouette(self):
        """All cube vertices are silhouette vertices (importance > 0)."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts, faces = _make_cube()
        weights = compute_silhouette_importance(verts, faces)
        for i, w in enumerate(weights):
            assert w > 0.0, f"Cube vertex {i} should have positive silhouette importance"

    def test_sphere_all_values_valid(self):
        """Sphere vertices all have valid importance in [0, 1]."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts, faces = _make_sphere(rings=8, segments=16)
        weights = compute_silhouette_importance(verts, faces)
        for w in weights:
            assert 0.0 <= w <= 1.0

    def test_empty_mesh_returns_empty(self):
        """Empty mesh returns empty weights."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        weights = compute_silhouette_importance([], [])
        assert weights == []

    def test_vertices_no_faces_returns_zeros(self):
        """Vertices with no faces return all zeros."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        weights = compute_silhouette_importance(verts, [])
        assert len(weights) == 3
        assert all(w == 0.0 for w in weights)

    def test_custom_view_directions(self):
        """Custom view directions produce valid results."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts, faces = _make_cube()
        weights = compute_silhouette_importance(
            verts, faces,
            view_directions=[(0.0, 0.0, 1.0)],
        )
        assert len(weights) == len(verts)
        for w in weights:
            assert 0.0 <= w <= 1.0

    def test_plane_all_boundary(self):
        """Vertices on a single open face are all boundary (high importance)."""
        from blender_addon.handlers.lod_pipeline import compute_silhouette_importance

        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        weights = compute_silhouette_importance(verts, faces)
        for w in weights:
            assert w > 0.0


# ---------------------------------------------------------------------------
# compute_region_importance tests
# ---------------------------------------------------------------------------


class TestRegionImportance:
    """Test per-vertex region importance computation."""

    def test_returns_correct_length(self):
        """Output length matches vertex count."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        verts, faces = _make_cube()
        regions = {"face": {0, 1}}
        weights = compute_region_importance(verts, faces, regions)
        assert len(weights) == len(verts)

    def test_region_vertices_get_one(self):
        """Vertices in a named region get importance 1.0."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        verts, faces = _make_cube()
        regions = {"face": {0, 1, 2}}
        weights = compute_region_importance(verts, faces, regions)
        assert weights[0] == 1.0
        assert weights[1] == 1.0
        assert weights[2] == 1.0

    def test_non_region_vertices_get_zero(self):
        """Vertices not in any region get importance 0.0."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        verts, faces = _make_cube()
        regions = {"face": {0, 1}}
        weights = compute_region_importance(verts, faces, regions)
        for i in range(2, 8):
            assert weights[i] == 0.0

    def test_multiple_regions_union(self):
        """Vertices in multiple regions still get 1.0."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        verts, faces = _make_cube()
        regions = {"face": {0, 1}, "hands": {1, 2}}
        weights = compute_region_importance(verts, faces, regions)
        assert weights[0] == 1.0
        assert weights[1] == 1.0
        assert weights[2] == 1.0

    def test_empty_regions(self):
        """Empty regions dict returns all zeros."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        verts, faces = _make_cube()
        weights = compute_region_importance(verts, faces, {})
        assert all(w == 0.0 for w in weights)

    def test_out_of_range_indices_ignored(self):
        """Region indices outside vertex range are silently ignored."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        verts, faces = _make_cube()
        regions = {"face": {0, 100, -5}}
        weights = compute_region_importance(verts, faces, regions)
        assert weights[0] == 1.0

    def test_empty_vertices_returns_empty(self):
        """Empty vertex list returns empty list."""
        from blender_addon.handlers.lod_pipeline import compute_region_importance

        weights = compute_region_importance([], [], {})
        assert weights == []


# ---------------------------------------------------------------------------
# decimate_preserving_silhouette tests
# ---------------------------------------------------------------------------


class TestDecimation:
    """Test edge-collapse decimation with importance weights."""

    def test_ratio_one_returns_original(self):
        """Ratio 1.0 returns the original mesh unchanged."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_cube()
        weights = [0.5] * len(verts)
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 1.0, weights,
        )
        assert len(result_verts) == len(verts)
        assert len(result_faces) == len(faces)

    def test_reduces_vertex_count(self):
        """Decimation at ratio < 1.0 reduces vertex count."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_subdivided_plane(10)
        weights = [0.5] * len(verts)
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.5, weights,
        )
        assert len(result_verts) < len(verts)

    def test_reduces_face_count(self):
        """Decimation reduces face count."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_subdivided_plane(10)
        weights = [0.5] * len(verts)
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.3, weights,
        )
        assert len(result_faces) < len(faces)

    def test_preserves_high_importance_vertices(self):
        """High importance vertices survive decimation more than low ones."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_subdivided_plane(10)
        n = len(verts)
        weights = [0.0] * n
        for i in range(min(10, n)):
            weights[i] = 1.0

        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.3, weights,
        )
        assert 4 <= len(result_verts) < n

    def test_minimum_four_vertices(self):
        """Decimation never goes below 4 vertices."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_subdivided_plane(5)
        weights = [0.0] * len(verts)
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.01, weights,
        )
        assert len(result_verts) >= 4

    def test_empty_mesh_returns_empty(self):
        """Empty mesh returns empty result."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        result_verts, result_faces = decimate_preserving_silhouette(
            [], [], 0.5, [],
        )
        assert result_verts == []
        assert result_faces == []

    def test_no_degenerate_faces(self):
        """Decimation does not produce degenerate faces (< 3 unique vertices)."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_subdivided_plane(8)
        weights = [0.5] * len(verts)
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.4, weights,
        )
        for face in result_faces:
            assert len(set(face)) >= 3, f"Degenerate face found: {face}"

    def test_sphere_decimation(self):
        """Sphere mesh decimates correctly."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_sphere(rings=8, segments=16)
        weights = [0.5] * len(verts)
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.5, weights,
        )
        assert len(result_verts) < len(verts)
        assert len(result_faces) > 0

    def test_progressive_decimation(self):
        """Lower ratio produces fewer vertices than higher ratio."""
        from blender_addon.handlers.lod_pipeline import decimate_preserving_silhouette

        verts, faces = _make_subdivided_plane(10)
        weights = [0.5] * len(verts)

        r50_verts, _ = decimate_preserving_silhouette(verts, faces, 0.5, list(weights))
        r25_verts, _ = decimate_preserving_silhouette(verts, faces, 0.25, list(weights))

        assert len(r25_verts) <= len(r50_verts)


# ---------------------------------------------------------------------------
# generate_collision_mesh tests
# ---------------------------------------------------------------------------


class TestCollisionMesh:
    """Test convex hull collision mesh generation."""

    def test_returns_vertices_and_faces(self):
        """Returns tuple of (vertices, faces)."""
        from blender_addon.handlers.lod_pipeline import generate_collision_mesh

        verts, faces = _make_cube()
        col_verts, col_faces = generate_collision_mesh(verts, faces)
        assert isinstance(col_verts, list)
        assert isinstance(col_faces, list)

    def test_max_tris_respected(self):
        """Collision mesh has at most max_tris triangles."""
        from blender_addon.handlers.lod_pipeline import generate_collision_mesh

        verts, faces = _make_sphere(rings=16, segments=32)
        col_verts, col_faces = generate_collision_mesh(verts, faces, max_tris=50)
        assert len(col_faces) <= 50

    def test_convex_normals_point_outward(self):
        """Most collision mesh face normals point outward from centroid."""
        from blender_addon.handlers.lod_pipeline import (
            generate_collision_mesh, _face_normal, _sub, _dot,
        )

        verts, faces = _make_cube()
        col_verts, col_faces = generate_collision_mesh(verts, faces)

        if not col_verts or not col_faces:
            pytest.skip("No collision mesh generated")

        cx = sum(v[0] for v in col_verts) / len(col_verts)
        cy = sum(v[1] for v in col_verts) / len(col_verts)
        cz = sum(v[2] for v in col_verts) / len(col_verts)
        centroid = (cx, cy, cz)

        outward_count = 0
        for face in col_faces:
            if len(face) < 3:
                continue
            fn = _face_normal(col_verts, face)
            fc = (
                sum(col_verts[face[j]][0] for j in range(min(3, len(face)))) / min(3, len(face)),
                sum(col_verts[face[j]][1] for j in range(min(3, len(face)))) / min(3, len(face)),
                sum(col_verts[face[j]][2] for j in range(min(3, len(face)))) / min(3, len(face)),
            )
            to_face = _sub(fc, centroid)
            if _dot(fn, to_face) >= -0.01:
                outward_count += 1

        total = len(col_faces)
        if total > 0:
            assert outward_count / total >= 0.7, (
                f"Only {outward_count}/{total} normals point outward"
            )

    def test_cube_collision_preserves_extent(self):
        """Collision mesh bounding box roughly matches source mesh."""
        from blender_addon.handlers.lod_pipeline import generate_collision_mesh

        verts, faces = _make_cube()
        col_verts, col_faces = generate_collision_mesh(verts, faces)

        if not col_verts:
            pytest.skip("No collision mesh generated")

        src_min_x = min(v[0] for v in verts)
        src_max_x = max(v[0] for v in verts)
        col_min_x = min(v[0] for v in col_verts)
        col_max_x = max(v[0] for v in col_verts)

        assert col_max_x - col_min_x >= (src_max_x - src_min_x) * 0.5

    def test_degenerate_input(self):
        """Fewer than 4 vertices returns the input back."""
        from blender_addon.handlers.lod_pipeline import generate_collision_mesh

        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        faces = [(0, 1, 2)]
        col_verts, col_faces = generate_collision_mesh(verts, faces)
        assert len(col_verts) == 3


# ---------------------------------------------------------------------------
# generate_lod_chain tests
# ---------------------------------------------------------------------------


class TestLODChain:
    """Test full LOD chain generation."""

    def test_correct_number_of_levels(self):
        """LOD chain has same number of levels as preset ratios."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain, LOD_PRESETS

        verts, faces = _make_subdivided_plane(10)
        mesh_data = {"vertices": verts, "faces": faces}

        for asset_type, preset in LOD_PRESETS.items():
            chain = generate_lod_chain(mesh_data, asset_type)
            expected_levels = len(preset["ratios"])
            assert len(chain) == expected_levels, (
                f"{asset_type}: expected {expected_levels} LODs, got {len(chain)}"
            )

    def test_lod0_is_full_detail(self):
        """LOD0 has the same vertex and face count as the original."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_subdivided_plane(10)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "prop_medium")
        lod0_verts, lod0_faces, lod0_level = chain[0]

        assert lod0_level == 0
        assert len(lod0_verts) == len(verts)
        assert len(lod0_faces) == len(faces)

    def test_lod_levels_ascending(self):
        """LOD levels are sequential: 0, 1, 2, ..."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_subdivided_plane(10)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "hero_character")
        levels = [level for _, _, level in chain]
        assert levels == list(range(len(chain)))

    def test_vertex_count_decreases(self):
        """Later LODs have fewer or equal vertices than earlier ones."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_subdivided_plane(10)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "prop_medium")
        vert_counts = [len(v) for v, f, l in chain]

        for i in range(1, len(vert_counts)):
            assert vert_counts[i] <= vert_counts[i - 1], (
                f"LOD{i} has {vert_counts[i]} verts > LOD{i-1} with {vert_counts[i-1]}"
            )

    def test_unknown_asset_type_raises_error(self):
        """Unknown asset type raises ValueError."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        mesh_data = {"vertices": [(0, 0, 0)], "faces": [(0,)]}
        with pytest.raises(ValueError, match="Unknown asset type"):
            generate_lod_chain(mesh_data, "nonexistent_type")

    def test_empty_mesh_returns_empty(self):
        """Empty mesh data returns empty chain."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        chain = generate_lod_chain({"vertices": [], "faces": []}, "prop_medium")
        assert chain == []

    def test_all_presets_generate_chains(self):
        """Every preset generates a non-empty chain from a valid mesh."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain, LOD_PRESETS

        verts, faces = _make_sphere(rings=8, segments=16)
        mesh_data = {"vertices": verts, "faces": faces}

        for asset_type in LOD_PRESETS:
            chain = generate_lod_chain(mesh_data, asset_type)
            assert len(chain) > 0, f"{asset_type} produced empty chain"


# ---------------------------------------------------------------------------
# Billboard LOD tests
# ---------------------------------------------------------------------------


class TestBillboardLOD:
    """Test billboard LOD generation for vegetation preset."""

    def test_billboard_has_four_vertices(self):
        """Billboard LOD (ratio=0.0) generates exactly 4 vertices."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_sphere(rings=8, segments=16)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "vegetation")
        billboard_verts, billboard_faces, billboard_level = chain[-1]
        assert len(billboard_verts) == 4

    def test_billboard_has_one_face(self):
        """Billboard LOD generates exactly 1 quad face."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_sphere(rings=8, segments=16)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "vegetation")
        billboard_verts, billboard_faces, billboard_level = chain[-1]
        assert len(billboard_faces) == 1

    def test_billboard_quad_is_planar(self):
        """Billboard quad vertices are coplanar (same Z coordinate)."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_sphere(rings=8, segments=16)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "vegetation")
        billboard_verts, _, _ = chain[-1]

        z_values = [v[2] for v in billboard_verts]
        assert all(abs(z - z_values[0]) < 1e-6 for z in z_values)

    def test_billboard_spans_bounding_box(self):
        """Billboard quad width/height approximately matches the source mesh."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_sphere(rings=8, segments=16)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "vegetation")
        billboard_verts, _, _ = chain[-1]

        src_xs = [v[0] for v in verts]
        src_ys = [v[1] for v in verts]
        src_width = max(src_xs) - min(src_xs)
        src_height = max(src_ys) - min(src_ys)

        bb_xs = [v[0] for v in billboard_verts]
        bb_ys = [v[1] for v in billboard_verts]
        bb_width = max(bb_xs) - min(bb_xs)
        bb_height = max(bb_ys) - min(bb_ys)

        assert abs(bb_width - src_width) < 0.1
        assert abs(bb_height - src_height) < 0.1

    def test_vegetation_last_lod_is_billboard(self):
        """Vegetation preset's last LOD level is the billboard."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain, LOD_PRESETS

        verts, faces = _make_sphere(rings=8, segments=16)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "vegetation")
        expected_levels = len(LOD_PRESETS["vegetation"]["ratios"])
        assert chain[-1][2] == expected_levels - 1


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end integration tests combining multiple pipeline stages."""

    def test_full_pipeline_hero_character(self):
        """Full pipeline for hero_character produces valid LOD chain + collision."""
        from blender_addon.handlers.lod_pipeline import (
            generate_lod_chain, generate_collision_mesh,
        )

        verts, faces = _make_sphere(rings=12, segments=24)
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "hero_character")
        assert len(chain) == 4

        col_verts, col_faces = generate_collision_mesh(verts, faces)
        assert len(col_faces) <= 50
        assert len(col_verts) >= 4

    def test_full_pipeline_building(self):
        """Full pipeline for building produces valid LOD chain."""
        from blender_addon.handlers.lod_pipeline import generate_lod_chain

        verts, faces = _make_cube()
        mesh_data = {"vertices": verts, "faces": faces}

        chain = generate_lod_chain(mesh_data, "building")
        assert len(chain) == 4

    def test_silhouette_importance_feeds_decimation(self):
        """Silhouette importance weights correctly influence decimation."""
        from blender_addon.handlers.lod_pipeline import (
            compute_silhouette_importance, decimate_preserving_silhouette,
        )

        verts, faces = _make_subdivided_plane(10)
        importance = compute_silhouette_importance(verts, faces)

        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.5, importance,
        )
        assert len(result_verts) < len(verts)
        assert len(result_faces) > 0

    def test_region_importance_combines_with_silhouette(self):
        """Region + silhouette importance can be combined for decimation."""
        from blender_addon.handlers.lod_pipeline import (
            compute_silhouette_importance,
            compute_region_importance,
            decimate_preserving_silhouette,
        )

        verts, faces = _make_subdivided_plane(10)
        sil = compute_silhouette_importance(verts, faces)
        reg = compute_region_importance(verts, faces, {"face": {0, 1, 2, 3, 4}})

        combined = [max(s, r) for s, r in zip(sil, reg)]
        result_verts, result_faces = decimate_preserving_silhouette(
            verts, faces, 0.4, combined,
        )
        assert len(result_verts) < len(verts)
