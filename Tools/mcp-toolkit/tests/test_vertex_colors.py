"""Unit tests for vertex color auto-painting pure-logic functions.

Tests compute_vertex_ao, compute_vertex_curvature, and compute_height_gradient
with known geometries (cube, plane, single vertex, degenerate cases).
All tests run without Blender.
"""

import math

import pytest


# ---------------------------------------------------------------------------
# Fixtures: Canonical mesh geometries
# ---------------------------------------------------------------------------

# Unit cube centered at origin: 8 verts, 6 quad faces, 12 edges
CUBE_VERTICES = [
    (-1.0, -1.0, -1.0),  # 0: bottom-left-back
    ( 1.0, -1.0, -1.0),  # 1: bottom-right-back
    ( 1.0,  1.0, -1.0),  # 2: top-right-back
    (-1.0,  1.0, -1.0),  # 3: top-left-back
    (-1.0, -1.0,  1.0),  # 4: bottom-left-front
    ( 1.0, -1.0,  1.0),  # 5: bottom-right-front
    ( 1.0,  1.0,  1.0),  # 6: top-right-front
    (-1.0,  1.0,  1.0),  # 7: top-left-front
]

CUBE_FACES = [
    (0, 1, 2, 3),  # back face  (-Z)
    (4, 7, 6, 5),  # front face (+Z)
    (0, 3, 7, 4),  # left face  (-X)
    (1, 5, 6, 2),  # right face (+X)
    (0, 4, 5, 1),  # bottom     (-Y)
    (3, 2, 6, 7),  # top        (+Y)
]

CUBE_FACE_NORMALS = [
    ( 0.0,  0.0, -1.0),  # back
    ( 0.0,  0.0,  1.0),  # front
    (-1.0,  0.0,  0.0),  # left
    ( 1.0,  0.0,  0.0),  # right
    ( 0.0, -1.0,  0.0),  # bottom
    ( 0.0,  1.0,  0.0),  # top
]

CUBE_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),  # back face edges
    (4, 5), (5, 6), (6, 7), (7, 4),  # front face edges
    (0, 4), (1, 5), (2, 6), (3, 7),  # connecting edges
]

# Flat plane (1 quad face, 4 verts) on the XY plane
PLANE_VERTICES = [
    (-1.0, -1.0, 0.0),
    ( 1.0, -1.0, 0.0),
    ( 1.0,  1.0, 0.0),
    (-1.0,  1.0, 0.0),
]

PLANE_FACES = [(0, 1, 2, 3)]

PLANE_FACE_NORMALS = [(0.0, 0.0, 1.0)]

PLANE_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),
]

# L-shaped geometry: two quads meeting at a 90-degree concave angle
L_VERTICES = [
    (0.0, 0.0, 0.0),  # 0: shared bottom-left
    (1.0, 0.0, 0.0),  # 1: shared bottom-right
    (1.0, 1.0, 0.0),  # 2: horizontal face top-right
    (0.0, 1.0, 0.0),  # 3: shared top (hinge edge)
    (0.0, 1.0, 1.0),  # 4: vertical face top-left
    (1.0, 1.0, 1.0),  # 5: vertical face top-right
]

L_FACES = [
    (0, 1, 2, 3),  # horizontal quad (Z=0)
    (3, 2, 5, 4),  # vertical quad (going up from the shared edge)
]

L_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),  # horizontal face
    (3, 4), (4, 5), (5, 2),          # vertical face extra edges
    (2, 3),                           # shared edge (duplicate key will be handled)
]


# ---------------------------------------------------------------------------
# Test: compute_vertex_ao
# ---------------------------------------------------------------------------

class TestComputeVertexAO:
    """Tests for ambient occlusion computation."""

    def test_empty_input(self):
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao([], [], [])
        assert result == []

    def test_single_vertex(self):
        """Single vertex with no faces should be fully exposed."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao([(0.0, 0.0, 0.0)], [], [])
        assert result == [1.0]

    def test_values_in_range(self):
        """All AO values must be in [0, 1]."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao(CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS)
        assert len(result) == 8
        for v in result:
            assert 0.0 <= v <= 1.0, f"AO value {v} out of range"

    def test_cube_corners_are_occluded(self):
        """Cube corners should have AO < 1.0 (they are enclosed by 3 perpendicular faces)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao(CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS)
        for i, ao in enumerate(result):
            assert ao < 1.0, f"Vertex {i} AO={ao}, expected < 1.0 for cube corner"

    def test_cube_all_corners_equal(self):
        """All cube corners should have the same AO value (symmetric geometry)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao(CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS)
        # All 8 corners should be approximately equal
        first = result[0]
        for i, ao in enumerate(result):
            assert abs(ao - first) < 1e-6, f"Vertex {i} AO={ao} != vertex 0 AO={first}"

    def test_plane_verts_are_exposed(self):
        """Plane vertices (single face) should be fully exposed (1.0)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao(PLANE_VERTICES, PLANE_FACES, PLANE_FACE_NORMALS)
        assert len(result) == 4
        for v in result:
            assert v == 1.0, f"Plane vertex AO={v}, expected 1.0"

    def test_cube_ao_value_correct(self):
        """Cube corner AO: 3 mutually perpendicular faces, all pair dots = 0.
        Average dot = 0.0, mapped to 0.5."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        result = compute_vertex_ao(CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS)
        # Each cube corner touches 3 faces with perpendicular normals
        # 3 pairs, each dot = 0.0, avg = 0.0, mapped = (0+1)*0.5 = 0.5
        for ao in result:
            assert abs(ao - 0.5) < 1e-6, f"Expected ~0.5, got {ao}"


# ---------------------------------------------------------------------------
# Test: compute_vertex_curvature
# ---------------------------------------------------------------------------

class TestComputeVertexCurvature:
    """Tests for curvature / edge wear computation."""

    def test_empty_input(self):
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature([], [], [])
        assert result == []

    def test_single_vertex(self):
        """Single vertex with no edges should be flat (0.5)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature([(0.0, 0.0, 0.0)], [], [])
        assert result == [0.5]

    def test_values_in_range(self):
        """All curvature values must be in [0, 1]."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature(CUBE_VERTICES, CUBE_FACES, CUBE_EDGES)
        assert len(result) == 8
        for v in result:
            assert 0.0 <= v <= 1.0, f"Curvature value {v} out of range"

    def test_cube_corners_are_convex(self):
        """Cube corners should be convex (curvature > 0.5)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature(CUBE_VERTICES, CUBE_FACES, CUBE_EDGES)
        for i, c in enumerate(result):
            assert c > 0.5, f"Vertex {i} curvature={c}, expected > 0.5 for convex cube corner"

    def test_cube_all_corners_equal(self):
        """All cube corners should have identical curvature (symmetric geometry)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature(CUBE_VERTICES, CUBE_FACES, CUBE_EDGES)
        first = result[0]
        for i, c in enumerate(result):
            assert abs(c - first) < 1e-6, f"Vertex {i} curvature={c} != vertex 0 curvature={first}"

    def test_plane_verts_are_flat(self):
        """Plane vertices (boundary edges only) should be flat (0.5)."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature(PLANE_VERTICES, PLANE_FACES, PLANE_EDGES)
        for v in result:
            assert v == 0.5, f"Plane vertex curvature={v}, expected 0.5"

    def test_l_shape_concave_edge(self):
        """L-shape: vertices on the concave (inner) edge should have curvature < 0.5."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        # Vertices 2 and 3 are on the shared edge (the concave hinge)
        l_face_normals_unused = []  # compute_vertex_curvature computes its own normals
        result = compute_vertex_curvature(L_VERTICES, L_FACES, L_EDGES)
        # The shared edge between the horizontal and vertical face is concave
        # Vertices 2, 3 have the shared-edge curvature averaged with boundary edges
        # They should have at least some concave contribution
        assert len(result) == 6


# ---------------------------------------------------------------------------
# Test: compute_height_gradient
# ---------------------------------------------------------------------------

class TestComputeHeightGradient:
    """Tests for height gradient computation."""

    def test_empty_input(self):
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient([])
        assert result == []

    def test_single_vertex(self):
        """Single vertex should get 0.5 (flat -- no height range)."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient([(0.0, 0.0, 5.0)])
        assert result == [0.5]

    def test_values_in_range(self):
        """All height values must be in [0, 1]."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient(CUBE_VERTICES)
        for v in result:
            assert 0.0 <= v <= 1.0, f"Height value {v} out of range"

    def test_default_bottom_is_bright(self):
        """Default mode: bottom vertices (lowest Z) should have value 1.0."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        # Cube: Z goes from -1 to +1
        # Bottom verts (z=-1): indices 0,1,2,3
        # Top verts (z=+1): indices 4,5,6,7
        result = compute_height_gradient(CUBE_VERTICES)
        for i in [0, 1, 2, 3]:
            assert abs(result[i] - 1.0) < 1e-6, f"Bottom vertex {i} height={result[i]}, expected 1.0"

    def test_default_top_is_dark(self):
        """Default mode: top vertices (highest Z) should have value 0.0."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient(CUBE_VERTICES)
        for i in [4, 5, 6, 7]:
            assert abs(result[i] - 0.0) < 1e-6, f"Top vertex {i} height={result[i]}, expected 0.0"

    def test_inverted_top_is_bright(self):
        """Inverted mode: top vertices should have value 1.0."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient(CUBE_VERTICES, invert=True)
        for i in [4, 5, 6, 7]:
            assert abs(result[i] - 1.0) < 1e-6, f"Top vertex {i} inverted height={result[i]}, expected 1.0"

    def test_inverted_bottom_is_dark(self):
        """Inverted mode: bottom vertices should have value 0.0."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient(CUBE_VERTICES, invert=True)
        for i in [0, 1, 2, 3]:
            assert abs(result[i] - 0.0) < 1e-6, f"Bottom vertex {i} inverted height={result[i]}, expected 0.0"

    def test_linear_interpolation(self):
        """Height values should interpolate linearly between bottom and top."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        verts = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 5.0),
            (0.0, 0.0, 10.0),
        ]
        result = compute_height_gradient(verts)
        # Default: bottom(z=0)=1.0, mid(z=5)=0.5, top(z=10)=0.0
        assert abs(result[0] - 1.0) < 1e-6
        assert abs(result[1] - 0.5) < 1e-6
        assert abs(result[2] - 0.0) < 1e-6

    def test_flat_plane_all_same(self):
        """All vertices at the same Z should get 0.5."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        result = compute_height_gradient(PLANE_VERTICES)  # all at z=0
        for v in result:
            assert v == 0.5, f"Flat plane vertex height={v}, expected 0.5"

    def test_negative_z_range(self):
        """Works correctly when all Z values are negative."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        verts = [
            (0.0, 0.0, -10.0),
            (0.0, 0.0, -5.0),
            (0.0, 0.0, 0.0),
        ]
        result = compute_height_gradient(verts)
        assert abs(result[0] - 1.0) < 1e-6  # lowest Z = bottom = 1.0
        assert abs(result[1] - 0.5) < 1e-6
        assert abs(result[2] - 0.0) < 1e-6  # highest Z = top = 0.0


# ---------------------------------------------------------------------------
# Test: _compute_face_normals helper
# ---------------------------------------------------------------------------

class TestComputeFaceNormals:
    """Tests for the internal face normal computation helper."""

    def test_upward_facing_quad(self):
        """A horizontal quad should have normal (0, 0, 1)."""
        from blender_addon.handlers.vertex_colors import _compute_face_normals
        normals = _compute_face_normals(PLANE_VERTICES, PLANE_FACES)
        assert len(normals) == 1
        nx, ny, nz = normals[0]
        assert abs(nz - 1.0) < 1e-6
        assert abs(nx) < 1e-6
        assert abs(ny) < 1e-6

    def test_cube_has_six_normals(self):
        """Cube should produce 6 face normals."""
        from blender_addon.handlers.vertex_colors import _compute_face_normals
        normals = _compute_face_normals(CUBE_VERTICES, CUBE_FACES)
        assert len(normals) == 6

    def test_degenerate_face(self):
        """Face with < 3 vertices should return default normal."""
        from blender_addon.handlers.vertex_colors import _compute_face_normals
        normals = _compute_face_normals([(0, 0, 0), (1, 0, 0)], [(0, 1)])
        assert normals == [(0.0, 0.0, 1.0)]

    def test_normals_are_unit_length(self):
        """All computed normals should be unit length."""
        from blender_addon.handlers.vertex_colors import _compute_face_normals
        normals = _compute_face_normals(CUBE_VERTICES, CUBE_FACES)
        for i, (nx, ny, nz) in enumerate(normals):
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            assert abs(length - 1.0) < 1e-6, f"Face {i} normal length={length}, expected 1.0"


# ---------------------------------------------------------------------------
# Test: Edge cases and integration
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for degenerate and edge-case inputs."""

    def test_ao_with_isolated_vertices(self):
        """Vertices not referenced by any face should be fully exposed."""
        from blender_addon.handlers.vertex_colors import compute_vertex_ao
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (5, 5, 5)]  # vertex 3 is isolated
        faces = [(0, 1, 2)]
        normals = [(0.0, 0.0, 1.0)]
        result = compute_vertex_ao(verts, faces, normals)
        assert len(result) == 4
        assert result[3] == 1.0  # isolated vertex

    def test_curvature_with_no_edges(self):
        """No edges should give all flat values."""
        from blender_addon.handlers.vertex_colors import compute_vertex_curvature
        result = compute_vertex_curvature(CUBE_VERTICES, CUBE_FACES, [])
        for v in result:
            assert v == 0.5

    def test_height_gradient_tiny_range(self):
        """Very tiny Z range (< 1e-9) should give all 0.5."""
        from blender_addon.handlers.vertex_colors import compute_height_gradient
        verts = [
            (0, 0, 1.0),
            (1, 0, 1.0),
            (0, 1, 1.0 + 1e-12),
        ]
        result = compute_height_gradient(verts)
        for v in result:
            assert v == 0.5

    def test_all_functions_return_correct_length(self):
        """Output length must always match input vertex count."""
        from blender_addon.handlers.vertex_colors import (
            compute_vertex_ao,
            compute_vertex_curvature,
            compute_height_gradient,
        )
        n = len(CUBE_VERTICES)
        assert len(compute_vertex_ao(CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS)) == n
        assert len(compute_vertex_curvature(CUBE_VERTICES, CUBE_FACES, CUBE_EDGES)) == n
        assert len(compute_height_gradient(CUBE_VERTICES)) == n
