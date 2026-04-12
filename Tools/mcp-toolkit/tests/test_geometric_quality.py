"""Geometric quality tests for terrain meshes.

Tests manifold integrity, normal consistency, degenerate face detection,
and vertex-level mesh quality metrics on procedurally generated terrain.
Pure numpy -- no Blender required.
"""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers: build a simple grid mesh from a heightmap for geometric analysis
# ---------------------------------------------------------------------------

def _heightmap_to_mesh(
    heightmap: np.ndarray,
    cell_size: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert a 2D heightmap to vertices and triangle indices.

    Returns (vertices, faces) where:
      vertices: (N, 3) float array of (x, y, z)
      faces: (M, 3) int array of triangle vertex indices
    """
    rows, cols = heightmap.shape
    verts = np.zeros((rows * cols, 3), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            verts[idx] = (c * cell_size, r * cell_size, heightmap[r, c])

    faces_list: list[tuple[int, int, int]] = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            v00 = r * cols + c
            v01 = r * cols + c + 1
            v10 = (r + 1) * cols + c
            v11 = (r + 1) * cols + c + 1
            faces_list.append((v00, v01, v10))
            faces_list.append((v01, v11, v10))

    faces = np.array(faces_list, dtype=np.int64)
    return verts, faces


def _compute_face_normals(
    verts: np.ndarray,
    faces: np.ndarray,
) -> np.ndarray:
    """Compute per-face normals via cross product. Returns (M, 3) array."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    edge1 = v1 - v0
    edge2 = v2 - v0
    normals = np.cross(edge1, edge2)
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return normals / norms


def _compute_face_areas(
    verts: np.ndarray,
    faces: np.ndarray,
) -> np.ndarray:
    """Compute per-face area. Returns (M,) array."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return 0.5 * np.linalg.norm(cross, axis=1)


def _build_edge_face_map(
    faces: np.ndarray,
) -> dict[tuple[int, int], list[int]]:
    """Build mapping from sorted edge tuple to face indices."""
    edge_map: dict[tuple[int, int], list[int]] = {}
    for fi, (a, b, c) in enumerate(faces):
        for e in [(a, b), (b, c), (c, a)]:
            key = (min(e), max(e))
            edge_map.setdefault(key, []).append(fi)
    return edge_map


def _count_boundary_edges(edge_map: dict) -> int:
    """Count edges shared by exactly one face (boundary/non-manifold)."""
    return sum(1 for flist in edge_map.values() if len(flist) == 1)


def _count_non_manifold_edges(edge_map: dict) -> int:
    """Count edges shared by more than 2 faces (non-manifold)."""
    return sum(1 for flist in edge_map.values() if len(flist) > 2)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mountain_heightmap():
    """64x64 mountain terrain heightmap."""
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains")


@pytest.fixture
def plains_heightmap():
    """64x64 plains terrain heightmap."""
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="plains")


@pytest.fixture
def eroded_heightmap(mountain_heightmap):
    """Mountain heightmap after hydraulic erosion."""
    from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion
    return apply_hydraulic_erosion(mountain_heightmap, iterations=200, seed=42)


# ===========================================================================
# Test classes
# ===========================================================================


class TestManifoldIntegrity:
    """Terrain meshes must be manifold (watertight, no T-junctions)."""

    def test_grid_mesh_has_no_boundary_edges(self, mountain_heightmap):
        """A complete grid mesh should have boundary edges only on the perimeter."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        edge_map = _build_edge_face_map(faces)
        boundary = _count_boundary_edges(edge_map)
        rows, cols = mountain_heightmap.shape
        expected_boundary = 2 * ((rows - 1) + (cols - 1))
        assert boundary == expected_boundary, (
            f"Expected {expected_boundary} boundary edges (perimeter), got {boundary}"
        )

    def test_grid_mesh_has_no_non_manifold_edges(self, mountain_heightmap):
        """No edge should be shared by more than 2 faces."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        edge_map = _build_edge_face_map(faces)
        non_manifold = _count_non_manifold_edges(edge_map)
        assert non_manifold == 0, f"Found {non_manifold} non-manifold edges"

    def test_eroded_mesh_manifold(self, eroded_heightmap):
        """Erosion must not break manifold topology."""
        verts, faces = _heightmap_to_mesh(eroded_heightmap)
        edge_map = _build_edge_face_map(faces)
        non_manifold = _count_non_manifold_edges(edge_map)
        assert non_manifold == 0

    def test_vertex_count_matches_grid(self, mountain_heightmap):
        """Vertex count must equal rows * cols."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        rows, cols = mountain_heightmap.shape
        assert verts.shape[0] == rows * cols

    def test_face_count_matches_grid(self, mountain_heightmap):
        """Face count must be 2 * (rows-1) * (cols-1) for a triangulated grid."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        rows, cols = mountain_heightmap.shape
        expected = 2 * (rows - 1) * (cols - 1)
        assert faces.shape[0] == expected

    def test_all_face_indices_valid(self, mountain_heightmap):
        """All face vertex indices must reference valid vertices."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        assert faces.min() >= 0
        assert faces.max() < verts.shape[0]

    def test_each_interior_edge_shared_by_two_faces(self, mountain_heightmap):
        """Every interior edge must be shared by exactly 2 triangles."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        edge_map = _build_edge_face_map(faces)
        interior_bad = sum(
            1 for flist in edge_map.values()
            if len(flist) != 1 and len(flist) != 2
        )
        assert interior_bad == 0


class TestNormalConsistency:
    """Face normals must be consistently oriented (no flipped faces)."""

    def test_all_normals_point_upward(self, mountain_heightmap):
        """For terrain viewed from above, all face normals Z component must be > 0."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        normals = _compute_face_normals(verts, faces)
        min_z = normals[:, 2].min()
        assert min_z > 0.0, f"Found face normal with Z={min_z:.4f} (should be >0)"

    def test_eroded_normals_upward(self, eroded_heightmap):
        """Erosion must not create flipped normals."""
        verts, faces = _heightmap_to_mesh(eroded_heightmap)
        normals = _compute_face_normals(verts, faces)
        assert normals[:, 2].min() > 0.0

    def test_steep_terrain_normals_valid(self):
        """Even steep (cliff-type) terrain should not have flipped normals."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        hmap = generate_heightmap(64, 64, scale=30.0, seed=99, terrain_type="cliffs")
        verts, faces = _heightmap_to_mesh(hmap)
        normals = _compute_face_normals(verts, faces)
        assert normals[:, 2].min() > 0.0

    def test_normal_magnitudes_are_unit(self, mountain_heightmap):
        """All face normals should be unit length."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        normals = _compute_face_normals(verts, faces)
        lengths = np.linalg.norm(normals, axis=1)
        np.testing.assert_allclose(lengths, 1.0, atol=1e-6)

    def test_adjacent_normals_not_opposite(self, mountain_heightmap):
        """Adjacent faces should not have opposite normals (dot product > 0)."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        normals = _compute_face_normals(verts, faces)
        edge_map = _build_edge_face_map(faces)
        worst_dot = 1.0
        for edge, flist in edge_map.items():
            if len(flist) == 2:
                dot = np.dot(normals[flist[0]], normals[flist[1]])
                worst_dot = min(worst_dot, dot)
        assert worst_dot > -0.5, (
            f"Adjacent face normals nearly opposite: dot={worst_dot:.4f}"
        )


class TestDegenerateFaces:
    """No degenerate triangles (zero area, slivers, or collapsed edges)."""

    def test_no_zero_area_faces(self, mountain_heightmap):
        """No triangle should have zero (or near-zero) area."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        areas = _compute_face_areas(verts, faces)
        min_area = areas.min()
        assert min_area > 1e-10, f"Found degenerate face with area={min_area}"

    def test_no_sliver_triangles(self, mountain_heightmap):
        """Minimum angle in any triangle must be > 1 degree (no slivers)."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap, cell_size=1.0)
        min_angle_deg = 90.0  # will be lowered
        for tri in faces[:500]:  # sample first 500 for perf
            pts = verts[tri]
            edges = [
                pts[1] - pts[0],
                pts[2] - pts[1],
                pts[0] - pts[2],
            ]
            for i in range(3):
                a = -edges[(i - 1) % 3]
                b = edges[i]
                cos_a = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
                cos_a = np.clip(cos_a, -1.0, 1.0)
                angle = math.degrees(math.acos(cos_a))
                min_angle_deg = min(min_angle_deg, angle)
        assert min_angle_deg > 1.0, f"Sliver triangle found: min angle={min_angle_deg:.2f}deg"

    def test_no_collapsed_edges(self, mountain_heightmap):
        """No edge should have zero length (duplicate vertices)."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        for tri in faces[:500]:
            for i in range(3):
                j = (i + 1) % 3
                length = np.linalg.norm(verts[tri[i]] - verts[tri[j]])
                assert length > 1e-10, "Collapsed edge (zero-length) detected"

    def test_area_ratio_within_bounds(self, mountain_heightmap):
        """Max/min face area ratio should be reasonable (< 100x for terrain)."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        areas = _compute_face_areas(verts, faces)
        ratio = areas.max() / max(areas.min(), 1e-12)
        assert ratio < 100.0, f"Face area ratio {ratio:.1f} exceeds 100x limit"

    def test_eroded_no_degenerate_faces(self, eroded_heightmap):
        """Erosion must not introduce degenerate faces."""
        verts, faces = _heightmap_to_mesh(eroded_heightmap)
        areas = _compute_face_areas(verts, faces)
        assert areas.min() > 1e-10

    def test_plains_minimal_area_variance(self, plains_heightmap):
        """Plains terrain should have low face area variance (nearly uniform)."""
        verts, faces = _heightmap_to_mesh(plains_heightmap)
        areas = _compute_face_areas(verts, faces)
        cv = areas.std() / max(areas.mean(), 1e-12)
        assert cv < 0.5, f"Plains face area CV={cv:.3f} too high"


class TestMeshConnectivity:
    """Terrain meshes must be fully connected (single component)."""

    def test_single_connected_component(self, mountain_heightmap):
        """The mesh must form a single connected component."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        n_verts = verts.shape[0]

        # Build adjacency via union-find
        parent = list(range(n_verts))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for tri in faces:
            union(tri[0], tri[1])
            union(tri[1], tri[2])

        roots = set(find(i) for i in range(n_verts))
        assert len(roots) == 1, f"Mesh has {len(roots)} connected components"

    def test_no_isolated_vertices(self, mountain_heightmap):
        """Every vertex must belong to at least one face."""
        verts, faces = _heightmap_to_mesh(mountain_heightmap)
        used = set(faces.ravel())
        unused = set(range(verts.shape[0])) - used
        assert len(unused) == 0, f"{len(unused)} isolated vertices found"


class TestVertexDuplicates:
    """No duplicate vertices at the same position."""

    def test_no_coincident_vertices(self, mountain_heightmap):
        """Grid mesh should have no duplicate vertex positions."""
        verts, _ = _heightmap_to_mesh(mountain_heightmap)
        rounded = np.round(verts, 6)
        unique_count = len(set(map(tuple, rounded)))
        assert unique_count == verts.shape[0], (
            f"Found {verts.shape[0] - unique_count} duplicate vertices"
        )
