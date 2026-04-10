"""Tests for collision_generator module.

Pure-logic tests only -- no bpy required.
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.collision_generator import (
    collision_mesh_name,
    compute_convex_hull_vertices,
    decimate_hull_faces,
)


class TestCollisionMeshGeneration:
    """Tests for pure-logic collision mesh functions."""

    def test_compute_convex_hull_pure(self):
        """Given 3D vertices, returns a reduced vertex set forming a convex hull."""
        # Cube vertices
        verts = [
            (0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0),
            (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1),
            (0.5, 0.5, 0.5),  # interior point -- should not be in hull
        ]
        hull_verts = compute_convex_hull_vertices(verts)
        # Interior point should be excluded (hull has 8 corner vertices)
        assert len(hull_verts) == 8
        # All hull verts should be from the original cube corners
        for v in hull_verts:
            assert v[0] in (0.0, 1.0) or abs(v[0]) < 0.001 or abs(v[0] - 1.0) < 0.001

    def test_collision_name_format(self):
        """Output mesh is named '{original_name}_COL'."""
        assert collision_mesh_name("Building_01") == "Building_01_COL"
        assert collision_mesh_name("Wall_Gate") == "Wall_Gate_COL"

    def test_face_count_limit(self):
        """After decimation, result has <= max_faces entries."""
        faces = list(range(200))
        result = decimate_hull_faces(faces, max_faces=128)
        assert len(result) <= 128

    def test_face_count_no_decimation_needed(self):
        """When face count is below limit, all faces returned."""
        faces = list(range(50))
        result = decimate_hull_faces(faces, max_faces=128)
        assert len(result) == 50

    def test_empty_input(self):
        """Raises ValueError for empty vertex list."""
        with pytest.raises(ValueError, match="empty"):
            compute_convex_hull_vertices([])

    def test_too_few_vertices(self):
        """Raises ValueError for fewer than 4 vertices."""
        with pytest.raises(ValueError, match="at least 4"):
            compute_convex_hull_vertices([(0, 0, 0), (1, 0, 0), (0, 1, 0)])

    def test_convex_hull_with_many_points(self):
        """Hull of many random-ish points has fewer vertices than input."""
        import random
        rng = random.Random(42)
        verts = [(rng.uniform(-10, 10), rng.uniform(-10, 10), rng.uniform(-10, 10)) for _ in range(100)]
        hull = compute_convex_hull_vertices(verts)
        assert len(hull) < 100
        assert len(hull) >= 4
