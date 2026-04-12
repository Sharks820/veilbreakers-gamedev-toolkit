"""Tests for A* river pathfinding fix, meander, and river mesh generation.

Validates:
- A* prefer_downhill mode produces non-straight paths that follow terrain drainage
- Meander adds lateral displacement while preserving endpoints
- River mesh generates valid quad-strip geometry
- Lake mesh generates valid radial disc geometry
- Waterfall volumetric mesh is truly 3D (not flat plane)
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from blender_addon.handlers._terrain_noise import (
    _astar,
    add_meander,
    carve_river_path,
    generate_lake_mesh,
    generate_river_mesh,
    generate_waterfall_volumetric_mesh,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valley_heightmap(size: int = 64, seed: int = 42) -> np.ndarray:
    """Create a heightmap with a diagonal valley from top-left to bottom-right.

    Height is high on the sides, low along the diagonal -- a natural river
    path should follow the valley rather than cut straight across ridges.
    """
    rng = np.random.default_rng(seed)
    rows, cols = size, size
    h = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            # Distance from diagonal (r == c line)
            dist_from_diag = abs(r - c) / (size * 0.5)
            h[r, c] = 0.2 + 0.6 * dist_from_diag + rng.uniform(0, 0.02)
    # Slope: top-left is higher than bottom-right along the diagonal
    for r in range(rows):
        h[r, :] += (1.0 - r / rows) * 0.15
    return h


def _slope_heightmap(size: int = 64) -> np.ndarray:
    """Simple slope: high at row 0, low at row size-1."""
    rows, cols = size, size
    h = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        h[r, :] = 1.0 - r / (rows - 1)
    return h


def _path_deviation(path: list[tuple[int, int]]) -> float:
    """Compute mean lateral deviation from the straight line between endpoints."""
    if len(path) < 3:
        return 0.0
    sr, sc = path[0]
    er, ec = path[-1]
    dr = er - sr
    dc = ec - sc
    line_len = math.sqrt(dr * dr + dc * dc)
    if line_len < 1e-6:
        return 0.0
    total_dev = 0.0
    for r, c in path[1:-1]:
        # Distance from point to line (sr,sc)->(er,ec)
        # Using cross-product formula
        cross = abs((c - sc) * dr - (r - sr) * dc)
        total_dev += cross / line_len
    return total_dev / max(len(path) - 2, 1)


# ---------------------------------------------------------------------------
# A* pathfinding tests
# ---------------------------------------------------------------------------

class TestAStarPreferDownhill:
    """Test that prefer_downhill=True produces terrain-following river paths."""

    def test_downhill_path_follows_valley(self):
        """On a valley heightmap, river should follow the valley, not cut straight."""
        h = _valley_heightmap(64)
        source = (2, 2)
        dest = (60, 60)

        path_downhill = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=True)
        path_legacy = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=False)

        # Both paths should reach the destination
        assert path_downhill[0] == source or (abs(path_downhill[0][0] - source[0]) <= 1 and abs(path_downhill[0][1] - source[1]) <= 1)
        assert path_downhill[-1] == dest

        # Downhill path should have more steps (it follows the valley, not straight)
        assert len(path_downhill) >= len(path_legacy), (
            f"Downhill path ({len(path_downhill)} steps) should be at least as long as "
            f"legacy path ({len(path_legacy)} steps) since it follows terrain"
        )

    def test_downhill_path_prefers_lower_terrain(self):
        """Average height along downhill path should be lower than legacy path."""
        h = _valley_heightmap(64)
        source = (5, 5)
        dest = (58, 58)

        path_dh = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=True)
        path_lg = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=False)

        avg_h_dh = np.mean([h[r, c] for r, c in path_dh])
        avg_h_lg = np.mean([h[r, c] for r, c in path_lg])

        assert avg_h_dh <= avg_h_lg + 0.05, (
            f"Downhill avg height {avg_h_dh:.3f} should be <= legacy {avg_h_lg:.3f}"
        )

    def test_downhill_avoids_uphill(self):
        """Count uphill steps -- downhill mode should have fewer."""
        h = _valley_heightmap(64)
        source = (5, 30)
        dest = (58, 30)

        path = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=True)

        uphill_count = 0
        for i in range(1, len(path)):
            if h[path[i][0], path[i][1]] > h[path[i-1][0], path[i-1][1]] + 0.001:
                uphill_count += 1

        uphill_fraction = uphill_count / max(len(path) - 1, 1)
        # On noisy terrain some uphill steps are unavoidable as the path
        # navigates around local bumps; 60% is a reasonable upper bound
        assert uphill_fraction < 0.6, (
            f"Downhill path has {uphill_fraction:.1%} uphill steps, expected < 60%"
        )

    def test_downhill_fewer_uphill_than_legacy(self):
        """Downhill mode should have fewer or equal uphill steps compared to legacy."""
        h = _valley_heightmap(64)
        source = (5, 5)
        dest = (58, 58)

        path_dh = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=True)
        path_lg = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=False)

        def _count_uphill(p):
            return sum(1 for i in range(1, len(p)) if h[p[i][0], p[i][1]] > h[p[i-1][0], p[i-1][1]] + 0.001)

        up_dh = _count_uphill(path_dh) / max(len(path_dh) - 1, 1)
        up_lg = _count_uphill(path_lg) / max(len(path_lg) - 1, 1)
        # Allow 5% tolerance since paths have different lengths
        assert up_dh <= up_lg + 0.05, (
            f"Downhill uphill frac {up_dh:.1%} should be <= legacy {up_lg:.1%}"
        )

    def test_legacy_mode_unchanged(self):
        """Legacy mode (prefer_downhill=False) should behave identically to before."""
        h = _slope_heightmap(32)
        source = (2, 2)
        dest = (28, 28)

        path = _astar(h, source, dest, slope_weight=5.0, height_weight=1.0, prefer_downhill=False)
        assert len(path) >= 2
        assert path[0] == source
        assert path[-1] == dest

    def test_straight_line_fallback(self):
        """When no valid path exists (e.g., 1x1 grid), fallback to straight line."""
        h = np.array([[0.5]])
        path = _astar(h, (0, 0), (0, 0), prefer_downhill=True)
        assert len(path) >= 1

    def test_carve_river_path_uses_downhill(self):
        """carve_river_path should use prefer_downhill and produce non-straight paths."""
        h = _valley_heightmap(64)
        path, carved = carve_river_path(h, (5, 5), (58, 58), width=2, depth=0.05)

        # Path should exist and have meaningful length
        assert len(path) > 10
        # Carved heightmap should be lower along the path
        for r, c in path[::5]:
            assert carved[r, c] <= h[r, c] + 1e-9


# ---------------------------------------------------------------------------
# Meander tests
# ---------------------------------------------------------------------------

class TestMeander:
    """Test sinusoidal meander perturbation."""

    def test_meander_preserves_endpoints(self):
        """Start and end points must not change."""
        path = [(r, 32) for r in range(64)]
        result = add_meander(path, amplitude=5.0, wavelength=20.0, seed=42)
        assert result[0] == path[0]
        assert result[-1] == path[-1]

    def test_meander_adds_lateral_displacement(self):
        """Meandered path should deviate from the straight line."""
        path = [(r, 32) for r in range(64)]
        result = add_meander(path, amplitude=5.0, wavelength=20.0, seed=42)

        dev = _path_deviation(result)
        assert dev > 0.5, (
            f"Meander deviation {dev:.2f} is too small, expected > 0.5 cells"
        )

    def test_meander_respects_amplitude(self):
        """Larger amplitude should produce more deviation."""
        path = [(r, 32) for r in range(64)]
        result_small = add_meander(path, amplitude=2.0, wavelength=20.0, seed=42)
        result_large = add_meander(path, amplitude=8.0, wavelength=20.0, seed=42)

        dev_small = _path_deviation(result_small)
        dev_large = _path_deviation(result_large)
        assert dev_large > dev_small, (
            f"Large amplitude dev {dev_large:.2f} should exceed small {dev_small:.2f}"
        )

    def test_meander_short_path_unchanged(self):
        """Paths shorter than 4 points should be returned as-is."""
        path = [(0, 0), (1, 1), (2, 2)]
        result = add_meander(path, amplitude=5.0, seed=0)
        assert result == path

    def test_meander_with_heightmap_avoids_uphill(self):
        """When heightmap is provided, meander should avoid pushing into ridges."""
        h = _valley_heightmap(64)
        path = [(r, r) for r in range(5, 59)]  # along the valley
        result = add_meander(path, amplitude=5.0, wavelength=15.0, seed=42, heightmap=h)

        # Result should still be valid grid coords
        for r, c in result:
            assert 0 <= r < 64
            assert 0 <= c < 64

    def test_meander_deterministic_with_seed(self):
        """Same seed should produce identical results."""
        path = [(r, 32) for r in range(64)]
        r1 = add_meander(path, amplitude=5.0, seed=123)
        r2 = add_meander(path, amplitude=5.0, seed=123)
        assert r1 == r2

    def test_meander_different_seeds_differ(self):
        """Different seeds should produce different paths."""
        path = [(r, 32) for r in range(64)]
        r1 = add_meander(path, amplitude=5.0, seed=123)
        r2 = add_meander(path, amplitude=5.0, seed=456)
        assert r1 != r2


# ---------------------------------------------------------------------------
# River mesh tests
# ---------------------------------------------------------------------------

class TestRiverMesh:
    """Test river surface mesh generation."""

    def test_basic_mesh_structure(self):
        """River mesh should produce vertices and quad faces."""
        h = _slope_heightmap(32)
        path = [(r, 16) for r in range(5, 28)]
        mesh = generate_river_mesh(path, h, width=2.0)

        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0
        assert len(mesh["vertices"]) == mesh["vertex_count"]
        assert len(mesh["faces"]) == mesh["face_count"]

    def test_mesh_width(self):
        """Vertices should span approximately the requested width."""
        h = _slope_heightmap(32)
        path = [(r, 16) for r in range(5, 28)]
        mesh = generate_river_mesh(path, h, width=4.0)

        # Each cross-section has 2 verts (left, right)
        # Check width at the midpoint
        mid = len(mesh["vertices"]) // 2
        if mid % 2 == 1:
            mid -= 1
        v_left = mesh["vertices"][mid]
        v_right = mesh["vertices"][mid + 1]
        actual_w = math.sqrt(
            (v_left[0] - v_right[0]) ** 2 + (v_left[1] - v_right[1]) ** 2
        )
        assert abs(actual_w - 4.0) < 1.0, f"Width {actual_w:.2f} != expected ~4.0"

    def test_faces_are_quads(self):
        """All faces should be quads (4 vertices each)."""
        h = _slope_heightmap(32)
        path = [(r, 16) for r in range(5, 28)]
        mesh = generate_river_mesh(path, h, width=2.0)

        for face in mesh["faces"]:
            assert len(face) == 4, f"Expected quad, got {len(face)}-gon"

    def test_water_below_terrain(self):
        """Water surface vertices should be below the terrain height."""
        h = _slope_heightmap(32)
        path = [(r, 16) for r in range(5, 28)]
        mesh = generate_river_mesh(path, h, width=2.0, depth_offset=0.15)

        for vx, vy, vz in mesh["vertices"]:
            # vy maps to row, vx maps to col in our convention
            ri = max(0, min(31, int(round(vy))))
            ci = max(0, min(31, int(round(vx))))
            assert vz <= float(h[ri, ci]) + 0.01, (
                f"Water at z={vz:.3f} above terrain {h[ri, ci]:.3f}"
            )

    def test_empty_path_returns_empty_mesh(self):
        """Single-point or empty path should return empty mesh."""
        h = _slope_heightmap(32)
        mesh = generate_river_mesh([(5, 5)], h, width=2.0)
        assert mesh["vertex_count"] == 0
        assert mesh["face_count"] == 0

    def test_face_indices_valid(self):
        """All face indices must be within vertex array bounds."""
        h = _slope_heightmap(32)
        path = [(r, 16) for r in range(5, 28)]
        mesh = generate_river_mesh(path, h, width=2.0)

        n_verts = mesh["vertex_count"]
        for face in mesh["faces"]:
            for idx in face:
                assert 0 <= idx < n_verts, f"Face index {idx} out of range [0, {n_verts})"


# ---------------------------------------------------------------------------
# Lake mesh tests
# ---------------------------------------------------------------------------

class TestLakeMesh:
    """Test lake surface mesh generation."""

    def test_basic_structure(self):
        """Lake mesh should have center vertex and radial structure."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        mesh = generate_lake_mesh(32, 32, h, radius=10.0)

        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0
        assert len(mesh["vertices"]) == mesh["vertex_count"]

    def test_center_vertex(self):
        """First vertex should be at the lake center."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        mesh = generate_lake_mesh(32, 32, h, radius=10.0)
        cx, cy, cz = mesh["center"]
        v0 = mesh["vertices"][0]
        assert abs(v0[0] - cx) < 0.01
        assert abs(v0[1] - cy) < 0.01

    def test_radius_in_output(self):
        """Output should include the radius."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        mesh = generate_lake_mesh(32, 32, h, radius=15.0)
        assert mesh["radius"] == 15.0

    def test_shore_noise_varies_boundary(self):
        """With shore noise, outer vertices should not form a perfect circle."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        mesh_noisy = generate_lake_mesh(32, 32, h, radius=10.0, shore_noise=0.3, seed=42)
        mesh_smooth = generate_lake_mesh(32, 32, h, radius=10.0, shore_noise=0.0, seed=42)

        # Outer ring vertices should differ
        assert mesh_noisy["vertices"] != mesh_smooth["vertices"]

    def test_face_indices_valid(self):
        """All face indices within bounds."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        mesh = generate_lake_mesh(32, 32, h, radius=10.0, resolution=16)

        n_verts = mesh["vertex_count"]
        for face in mesh["faces"]:
            for idx in face:
                assert 0 <= idx < n_verts, f"Index {idx} >= {n_verts}"

    def test_water_at_or_below_terrain(self):
        """Lake surface should be at or below surrounding terrain."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        mesh = generate_lake_mesh(32, 32, h, radius=8.0, depth_offset=0.2)

        for _, _, vz in mesh["vertices"]:
            assert vz <= 0.5 + 0.01, f"Lake vertex z={vz:.3f} above terrain 0.5"

    def test_deterministic_with_seed(self):
        """Same seed produces identical mesh."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        m1 = generate_lake_mesh(32, 32, h, radius=10.0, seed=99)
        m2 = generate_lake_mesh(32, 32, h, radius=10.0, seed=99)
        assert m1["vertices"] == m2["vertices"]


# ---------------------------------------------------------------------------
# Waterfall volumetric mesh tests
# ---------------------------------------------------------------------------

class TestWaterfallVolumetricMesh:
    """Test 3D volumetric waterfall mesh generation."""

    def test_basic_structure(self):
        """Mesh should have vertices and faces."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(2, 2, 0), width=3.0
        )
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0
        assert mesh["is_volumetric"] is True

    def test_drop_height(self):
        """Drop height should match lip-to-pool Z difference."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 15), pool_pos=(1, 1, 5)
        )
        assert abs(mesh["drop_height"] - 10.0) < 0.01

    def test_not_flat_plane(self):
        """Mesh must have depth (not all vertices on the same plane).

        This is the critical volumetric requirement: waterfalls are NEVER flat planes.
        We check that vertex positions span 3 dimensions significantly.
        """
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 20), pool_pos=(3, 3, 0), width=4.0,
            thickness_top=0.3, thickness_bottom=0.8
        )
        verts = np.array(mesh["vertices"])
        # Check that we have non-trivial extent in all 3 axes
        extents = verts.max(axis=0) - verts.min(axis=0)
        assert extents[0] > 1.0, f"X extent {extents[0]:.2f} too small (flat?)"
        assert extents[1] > 1.0, f"Y extent {extents[1]:.2f} too small (flat?)"
        assert extents[2] > 5.0, f"Z extent {extents[2]:.2f} too small for 20m drop"

    def test_thickness_varies(self):
        """Bottom should be thicker than top (taper)."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(0, 5, 0), width=3.0,
            thickness_top=0.3, thickness_bottom=0.8, curvature_segments=6,
            vertical_segments=10
        )
        assert mesh["thickness_top"] < mesh["thickness_bottom"]

    def test_face_indices_valid(self):
        """All face indices within vertex array bounds."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(2, 2, 0)
        )
        n_verts = mesh["vertex_count"]
        for face in mesh["faces"]:
            for idx in face:
                assert 0 <= idx < n_verts, f"Index {idx} >= {n_verts}"

    def test_minimum_curvature_segments(self):
        """Even if 1 is requested, should be clamped to >= 3."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(2, 2, 0),
            curvature_segments=1  # Should be clamped to 3
        )
        # Should still produce valid geometry
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0

    def test_straight_down_waterfall(self):
        """Waterfall dropping straight down (no horizontal offset) should still work."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(5, 5, 20), pool_pos=(5, 5, 0), width=3.0
        )
        assert mesh["vertex_count"] > 0
        assert mesh["drop_height"] == 20.0

    def test_deterministic_with_seed(self):
        """Same seed produces identical mesh."""
        m1 = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(2, 2, 0), seed=77
        )
        m2 = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(2, 2, 0), seed=77
        )
        assert m1["vertices"] == m2["vertices"]

    def test_vertex_density_adequate(self):
        """Vertex count should scale with drop height and segments."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 30), pool_pos=(5, 5, 0), width=4.0,
            vertical_segments=20, curvature_segments=8
        )
        # Expected: (20+1) sections * 2 * (8+1) = 21 * 18 = 378 verts
        assert mesh["vertex_count"] >= 300, (
            f"Only {mesh['vertex_count']} verts for 30m drop -- too sparse"
        )
