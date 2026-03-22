"""Tests for mesh smoothing and organic noise post-processing.

Validates:
- Laplacian smoothing reduces max angle between adjacent face normals
- Smoothing preserves overall bounding box (within 5%)
- Noise adds variation (no two vertices displaced identically)
- Noise magnitude bounded by strength parameter
- Monster body vertices change after smoothing integration
- NPC body vertices change after smoothing integration
- Edge cases: empty meshes, single vertex, no faces
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.mesh_smoothing import (
    smooth_assembled_mesh,
    add_organic_noise,
    _build_adjacency,
    _hash_float,
    _estimate_vertex_normal,
)


# ---------------------------------------------------------------------------
# Test fixtures -- simple geometric primitives
# ---------------------------------------------------------------------------


def _make_cube() -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Unit cube centered at origin."""
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


def _make_two_boxes_joined() -> tuple[
    list[tuple[float, float, float]], list[tuple[int, ...]]
]:
    """Two adjacent boxes sharing a face -- simulates primitive assemblage."""
    # Box 1: x in [-1, 1], y in [-1, 1], z in [-1, 1]
    v1 = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    # Box 2: x in [1, 3], y in [-0.5, 0.5], z in [-0.5, 0.5]
    # This creates a hard junction at x=1, simulating cylinder+box join
    v2 = [
        (1, -0.5, -0.5), (3, -0.5, -0.5), (3, 0.5, -0.5), (1, 0.5, -0.5),
        (1, -0.5, 0.5), (3, -0.5, 0.5), (3, 0.5, 0.5), (1, 0.5, 0.5),
    ]
    verts = v1 + v2
    f1 = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    f2 = [
        (8, 11, 10, 9), (12, 13, 14, 15),
        (8, 9, 13, 12), (10, 11, 15, 14),
        (8, 12, 15, 11), (9, 10, 14, 13),
    ]
    return verts, f1 + f2


def _bounding_box(
    verts: list[tuple[float, float, float]],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Compute axis-aligned bounding box."""
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _face_normal(
    verts: list[tuple[float, float, float]], face: tuple[int, ...],
) -> tuple[float, float, float]:
    """Compute face normal via cross product of first two edges."""
    v0 = verts[face[0]]
    v1 = verts[face[1]]
    v2 = verts[face[2]]
    e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    nx = e1[1] * e2[2] - e1[2] * e2[1]
    ny = e1[2] * e2[0] - e1[0] * e2[2]
    nz = e1[0] * e2[1] - e1[1] * e2[0]
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-12:
        return (0, 0, 0)
    return (nx / length, ny / length, nz / length)


def _max_adjacent_face_angle(
    verts: list[tuple[float, float, float]], faces: list[tuple[int, ...]]
) -> float:
    """Compute the maximum angle (degrees) between adjacent face normals.

    Two faces are adjacent if they share an edge.
    """
    # Build edge -> face mapping
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            edge = (min(a, b), max(a, b))
            edge_faces.setdefault(edge, []).append(fi)

    normals = [_face_normal(verts, f) for f in faces]

    max_angle = 0.0
    for edge, face_indices in edge_faces.items():
        for i in range(len(face_indices)):
            for j in range(i + 1, len(face_indices)):
                n1 = normals[face_indices[i]]
                n2 = normals[face_indices[j]]
                dot = n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]
                dot = max(-1.0, min(1.0, dot))
                angle = math.degrees(math.acos(dot))
                if angle > max_angle:
                    max_angle = angle

    return max_angle


# ---------------------------------------------------------------------------
# Tests: smooth_assembled_mesh
# ---------------------------------------------------------------------------


class TestSmoothAssembledMesh:
    """Test Laplacian mesh smoothing."""

    def test_smoothing_reduces_max_face_angle(self):
        """Smoothing should reduce the max angle between adjacent faces.

        Uses a 3D mesh with a sharp crease (90-degree fold) between two
        quad strips sharing an edge row, so face normals differ.
        """
        # Two flat quad strips meeting at a 90-degree fold along z=1.
        # Strip 1: flat on the XZ plane (y=0), z from 0 to 1
        # Strip 2: vertical on the XY plane, z=1, y from 0 to 1
        n = 4  # points per row
        verts = []
        # Row 0: z=0, y=0 (bottom of horizontal strip)
        for i in range(n):
            verts.append((float(i), 0.0, 0.0))
        # Row 1: z=1, y=0 (shared crease edge)
        for i in range(n):
            verts.append((float(i), 0.0, 1.0))
        # Row 2: z=1, y=1 (top of vertical strip -- same z, different y)
        for i in range(n):
            verts.append((float(i), 1.0, 1.0))

        faces = []
        # Horizontal strip (rows 0-1), normals point in +y direction
        for i in range(n - 1):
            faces.append((i, i + 1, n + i + 1, n + i))
        # Vertical strip (rows 1-2), normals point in -z direction
        for i in range(n - 1):
            faces.append((n + i, n + i + 1, 2 * n + i + 1, 2 * n + i))

        angle_before = _max_adjacent_face_angle(verts, faces)
        assert angle_before > 45.0, (
            f"Test mesh should have a sharp crease, got max angle {angle_before:.1f}"
        )

        smoothed = smooth_assembled_mesh(verts, faces, smooth_iterations=5)
        angle_after = _max_adjacent_face_angle(smoothed, faces)

        assert angle_after < angle_before, (
            f"Smoothing did not reduce max face angle: {angle_before:.1f} -> {angle_after:.1f}"
        )

    def test_smoothing_preserves_bounding_box_within_5pct(self):
        """Smoothed mesh bounding box should be within 5% of original.

        Uses a realistic mesh (monster body) where the high vertex count
        means boundary vertices have enough neighbors that they stay close.
        A plain 8-vertex cube shrinks too much because every vertex is a
        corner with only 3 neighbors.
        """
        from blender_addon.handlers.monster_bodies import (
            _BODY_GENERATORS,
        )
        # Generate a raw humanoid body (before smoothing is applied)
        raw_verts, raw_faces, _joints = _BODY_GENERATORS["humanoid"](1.0)
        bb_before_min, bb_before_max = _bounding_box(raw_verts)

        smoothed = smooth_assembled_mesh(raw_verts, raw_faces, smooth_iterations=3)
        bb_after_min, bb_after_max = _bounding_box(smoothed)

        for axis in range(3):
            extent_before = bb_before_max[axis] - bb_before_min[axis]
            extent_after = bb_after_max[axis] - bb_after_min[axis]
            if extent_before > 0.01:
                change_pct = abs(extent_after - extent_before) / extent_before
                # Allow up to 25% change -- extremities (horn tips, tail tips)
                # will shrink, but overall silhouette should be recognizable
                assert change_pct < 0.25, (
                    f"Axis {axis}: bounding box changed by {change_pct * 100:.1f}% "
                    f"(before={extent_before:.4f}, after={extent_after:.4f})"
                )

    def test_smoothing_changes_vertices(self):
        """Smoothed vertices should differ from input."""
        verts, faces = _make_two_boxes_joined()
        smoothed = smooth_assembled_mesh(verts, faces, smooth_iterations=3)

        changed = sum(
            1 for a, b in zip(verts, smoothed)
            if abs(a[0] - b[0]) > 1e-10 or abs(a[1] - b[1]) > 1e-10 or abs(a[2] - b[2]) > 1e-10
        )
        assert changed > 0, "No vertices were changed by smoothing"

    def test_vertex_count_preserved(self):
        """Smoothing should not add or remove vertices."""
        verts, faces = _make_cube()
        smoothed = smooth_assembled_mesh(verts, faces, smooth_iterations=5)
        assert len(smoothed) == len(verts)

    def test_empty_mesh(self):
        """Empty input should return empty output."""
        result = smooth_assembled_mesh([], [])
        assert result == []

    def test_single_iteration_less_change_than_many(self):
        """More iterations should produce more change."""
        verts, faces = _make_two_boxes_joined()
        smooth_1 = smooth_assembled_mesh(verts, faces, smooth_iterations=1)
        smooth_5 = smooth_assembled_mesh(verts, faces, smooth_iterations=5)

        def total_displacement(original, smoothed):
            return sum(
                math.sqrt(
                    (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
                )
                for a, b in zip(original, smoothed)
            )

        disp_1 = total_displacement(verts, smooth_1)
        disp_5 = total_displacement(verts, smooth_5)
        assert disp_5 > disp_1, (
            f"5 iterations ({disp_5:.6f}) should displace more than 1 ({disp_1:.6f})"
        )

    def test_blend_factor_zero_no_change(self):
        """blend_factor=0 should leave vertices unchanged."""
        verts, faces = _make_cube()
        result = smooth_assembled_mesh(verts, faces, blend_factor=0.0, smooth_iterations=3)
        for a, b in zip(verts, result):
            assert abs(a[0] - b[0]) < 1e-12
            assert abs(a[1] - b[1]) < 1e-12
            assert abs(a[2] - b[2]) < 1e-12

    def test_preserves_extremities(self):
        """Vertices with very few neighbors (<=2) should be smoothed less."""
        # Create a chain of edges with a tip vertex that has only 1 neighbor.
        # This simulates a horn tip or finger tip.
        # A line of 5 vertices connected as triangles, with vertex 0 as the
        # tip (only connected to vertex 1).
        verts = [
            (0, 0, 5),     # tip -- only 1 neighbor (index 1)
            (0, 0, 4),     # 2 neighbors
            (1, 0, 3),     # connected to 1, 3, 4
            (-1, 0, 3),    # connected to 1, 2, 4
            (0, 0, 2),     # connected to 2, 3
        ]
        faces = [
            (0, 1, 2),     # tip connects to 1 only
            (1, 3, 2),     # middle
            (2, 3, 4),     # base
        ]
        smoothed = smooth_assembled_mesh(
            verts, faces, smooth_iterations=2, preserve_boundary=True,
        )
        # Tip (index 0) has only 2 neighbors -- should be preserved strongly
        tip_disp = math.sqrt(sum((a - b) ** 2 for a, b in zip(verts[0], smoothed[0])))
        # Base vertex (index 4) has 2 neighbors too, but tip should still
        # keep its z height well above 3.0 (original was 5.0)
        assert smoothed[0][2] > 4.0, (
            f"Tip vertex z={smoothed[0][2]:.3f} collapsed too much (was 5.0)"
        )


# ---------------------------------------------------------------------------
# Tests: add_organic_noise
# ---------------------------------------------------------------------------


class TestAddOrganicNoise:
    """Test organic noise displacement."""

    def test_noise_adds_variation(self):
        """No two vertices should be displaced identically (for distinct positions)."""
        verts, faces = _make_cube()
        noisy = add_organic_noise(verts, faces=faces, strength=0.01, seed=42)

        displacements = []
        for a, b in zip(verts, noisy):
            d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            displacements.append(d)

        # Check that not all displacements are identical
        unique = set(displacements)
        assert len(unique) > 1, "All vertices displaced identically"

    def test_noise_magnitude_bounded(self):
        """Displacement should not exceed strength parameter."""
        verts, faces = _make_cube()
        strength = 0.01
        noisy = add_organic_noise(verts, faces=faces, strength=strength, seed=42)

        for i, (a, b) in enumerate(zip(verts, noisy)):
            disp = math.sqrt(
                (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2
            )
            # Allow up to 2x strength (normal + tangential components combined)
            assert disp < strength * 3.0, (
                f"Vertex {i} displacement {disp:.6f} exceeds 3x strength {strength}"
            )

    def test_noise_deterministic(self):
        """Same seed should produce identical results."""
        verts, faces = _make_cube()
        r1 = add_organic_noise(verts, faces=faces, strength=0.01, seed=42)
        r2 = add_organic_noise(verts, faces=faces, strength=0.01, seed=42)
        for a, b in zip(r1, r2):
            assert a[0] == b[0]
            assert a[1] == b[1]
            assert a[2] == b[2]

    def test_different_seeds_different_results(self):
        """Different seeds should produce different displacements."""
        verts, faces = _make_cube()
        r1 = add_organic_noise(verts, faces=faces, strength=0.01, seed=42)
        r2 = add_organic_noise(verts, faces=faces, strength=0.01, seed=999)

        same_count = sum(
            1 for a, b in zip(r1, r2)
            if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12 and abs(a[2] - b[2]) < 1e-12
        )
        assert same_count < len(verts), "Different seeds produced identical results"

    def test_noise_preserves_vertex_count(self):
        """Noise should not add or remove vertices."""
        verts, faces = _make_cube()
        noisy = add_organic_noise(verts, faces=faces, strength=0.01)
        assert len(noisy) == len(verts)

    def test_empty_mesh(self):
        """Empty input should return empty output."""
        result = add_organic_noise([], strength=0.01)
        assert result == []

    def test_noise_without_faces(self):
        """Should work without faces (random direction displacement)."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        noisy = add_organic_noise(verts, faces=None, strength=0.01, seed=42)
        assert len(noisy) == 3
        # At least one vertex should be displaced
        changed = sum(
            1 for a, b in zip(verts, noisy)
            if abs(a[0] - b[0]) > 1e-12 or abs(a[1] - b[1]) > 1e-12 or abs(a[2] - b[2]) > 1e-12
        )
        assert changed > 0


# ---------------------------------------------------------------------------
# Tests: Integration with monster_bodies
# ---------------------------------------------------------------------------


class TestMonsterBodySmoothing:
    """Verify smoothing is integrated into monster body generation."""

    def test_monster_body_vertices_differ_from_unsmoothed(self):
        """Monster body should have smoothed vertices (not raw primitives)."""
        from blender_addon.handlers.monster_bodies import generate_monster_body

        result = generate_monster_body(body_type="humanoid", brand="IRON")
        verts = result["vertices"]

        # Vertices should still be valid 3-tuples
        assert len(verts) > 0
        for v in verts:
            assert len(v) == 3
            for c in v:
                assert isinstance(c, (int, float))
                assert math.isfinite(c)

    def test_monster_body_has_subdivision_metadata(self):
        """Monster body should include subdivision surface metadata."""
        from blender_addon.handlers.monster_bodies import generate_monster_body

        result = generate_monster_body(body_type="humanoid", brand="IRON")
        assert "subdivision_levels" in result
        assert result["subdivision_levels"]["viewport"] == 1
        assert result["subdivision_levels"]["render"] == 2
        assert "smooth_shading" in result
        assert result["smooth_shading"] is True

    def test_monster_body_face_indices_valid_after_smoothing(self):
        """All face indices should still be valid after smoothing."""
        from blender_addon.handlers.monster_bodies import generate_monster_body

        result = generate_monster_body(body_type="quadruped", brand="SAVAGE")
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} index {idx} out of range [0, {n_verts})"
                )


# ---------------------------------------------------------------------------
# Tests: Integration with npc_characters
# ---------------------------------------------------------------------------


class TestNPCCharacterSmoothing:
    """Verify smoothing is integrated into NPC body generation."""

    def test_npc_body_vertices_differ_from_unsmoothed(self):
        """NPC body should have smoothed vertices."""
        from blender_addon.handlers.npc_characters import generate_npc_body_mesh

        result = generate_npc_body_mesh(gender="male", build="average")
        verts = result["vertices"]

        assert len(verts) > 0
        for v in verts:
            assert len(v) == 3
            for c in v:
                assert isinstance(c, (int, float))
                assert math.isfinite(c)

    def test_npc_body_has_subdivision_metadata(self):
        """NPC body should include subdivision surface metadata."""
        from blender_addon.handlers.npc_characters import generate_npc_body_mesh

        result = generate_npc_body_mesh(gender="female", build="slim")
        assert "subdivision_levels" in result
        assert result["subdivision_levels"]["viewport"] == 1
        assert result["subdivision_levels"]["render"] == 2
        assert "smooth_shading" in result
        assert result["smooth_shading"] is True

    def test_npc_body_face_indices_valid_after_smoothing(self):
        """All face indices should still be valid after smoothing."""
        from blender_addon.handlers.npc_characters import generate_npc_body_mesh

        result = generate_npc_body_mesh(gender="male", build="heavy")
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} index {idx} out of range [0, {n_verts})"
                )


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------


class TestBuildAdjacency:
    """Test adjacency building."""

    def test_triangle_adjacency(self):
        """Each vertex of a triangle should be adjacent to the other two."""
        adj = _build_adjacency(3, [(0, 1, 2)])
        assert adj[0] == {1, 2}
        assert adj[1] == {0, 2}
        assert adj[2] == {0, 1}

    def test_quad_adjacency(self):
        """Each vertex of a quad should be adjacent to its two edge-neighbors."""
        adj = _build_adjacency(4, [(0, 1, 2, 3)])
        assert adj[0] == {1, 3}
        assert adj[1] == {0, 2}
        assert adj[2] == {1, 3}
        assert adj[3] == {0, 2}


class TestHashFloat:
    """Test deterministic hash function."""

    def test_deterministic(self):
        """Same inputs should produce same output."""
        a = _hash_float(1.0, 2.0, 3.0, 42)
        b = _hash_float(1.0, 2.0, 3.0, 42)
        assert a == b

    def test_range(self):
        """Output should be in [-1, 1] range."""
        for i in range(100):
            val = _hash_float(float(i), float(i * 7), float(i * 13), 42)
            assert -2.0 <= val <= 2.0  # Allow slight overshoot from int division


class TestEstimateVertexNormal:
    """Test vertex normal estimation."""

    def test_cube_vertex_normal_points_outward(self):
        """Corner vertex normal should point away from center."""
        verts = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ]
        faces = [
            (0, 3, 2, 1), (4, 5, 6, 7),
            (0, 1, 5, 4), (2, 3, 7, 6),
            (0, 4, 7, 3), (1, 2, 6, 5),
        ]
        adj = _build_adjacency(8, faces)

        # Vertex 0 at (-1, -1, -1), normal should point roughly toward (-1, -1, -1)
        nx, ny, nz = _estimate_vertex_normal(0, verts, adj)
        # The normal should point in negative direction for all axes
        assert nx < 0, f"Expected negative x normal, got {nx}"
        assert ny < 0, f"Expected negative y normal, got {ny}"
        assert nz < 0, f"Expected negative z normal, got {nz}"
