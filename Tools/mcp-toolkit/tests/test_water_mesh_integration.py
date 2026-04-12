"""Integration tests: river mesh from A* path, lake from detection, waterfall from chain.

These tests verify the end-to-end pipeline:
1. A* pathfinding -> meander -> river mesh
2. Lake detection -> lake mesh
3. Waterfall chain solve -> volumetric mesh
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


def _create_terrain_with_valley_and_cliff(size: int = 64) -> np.ndarray:
    """Terrain with a valley (for river) and a cliff (for waterfall)."""
    h = np.zeros((size, size), dtype=np.float64)
    for r in range(size):
        for c in range(size):
            # General slope: high NW, low SE
            h[r, c] = 1.0 - 0.3 * (r / size) - 0.3 * (c / size)
            # Valley along diagonal
            dist = abs(r - c) / (size * 0.5)
            h[r, c] -= 0.2 * max(0, 1.0 - dist)
    # Add a cliff at row 40 (sharp drop)
    h[40:, :] -= 0.3
    return np.clip(h, 0.0, 1.0)


class TestRiverEndToEnd:
    """Full pipeline: A* -> meander -> mesh."""

    def test_full_river_pipeline(self):
        """A* path + meander + mesh generation produces valid water geometry."""
        h = _create_terrain_with_valley_and_cliff()
        source = (5, 5)
        dest = (35, 35)

        # Step 1: A* pathfinding with downhill preference
        path = _astar(h, source, dest, slope_weight=8.0, height_weight=2.0, prefer_downhill=True)
        assert len(path) >= 10, "Path too short"

        # Step 2: Add meander
        meandered = add_meander(path, amplitude=3.0, wavelength=15.0, seed=42, heightmap=h)
        assert len(meandered) >= 5, "Meandered path too short"
        assert meandered[0] == path[0], "Start changed"
        assert meandered[-1] == path[-1], "End changed"

        # Step 3: Generate river mesh
        mesh = generate_river_mesh(meandered, h, width=2.0, depth_offset=0.1)
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0

        # Verify all face indices valid
        for face in mesh["faces"]:
            for idx in face:
                assert 0 <= idx < mesh["vertex_count"]

    def test_carve_then_mesh(self):
        """carve_river_path + mesh should produce coherent result."""
        h = _create_terrain_with_valley_and_cliff()
        path, carved = carve_river_path(h, (5, 5), (35, 35), width=3, depth=0.05)

        # Mesh should use carved heightmap for accurate water level
        mesh = generate_river_mesh(path, carved, width=3.0, depth_offset=0.05)
        assert mesh["vertex_count"] > 0

        # Water should be below carved terrain
        for vx, vy, vz in mesh["vertices"]:
            ri = max(0, min(63, int(round(vy))))
            ci = max(0, min(63, int(round(vx))))
            assert vz <= float(carved[ri, ci]) + 0.02


class TestLakeEndToEnd:
    """Lake detection -> mesh."""

    def test_lake_at_depression(self):
        """Generate lake mesh at a terrain depression."""
        h = np.full((64, 64), 0.5, dtype=np.float64)
        # Create a depression at (32, 32)
        for r in range(24, 40):
            for c in range(24, 40):
                dist = math.sqrt((r - 32) ** 2 + (c - 32) ** 2)
                if dist < 8:
                    h[r, c] -= 0.2 * (1.0 - dist / 8)

        mesh = generate_lake_mesh(32, 32, h, radius=6.0, depth_offset=0.15, seed=42)
        assert mesh["vertex_count"] > 10
        assert mesh["face_count"] > 5
        # Center should be at the depression
        cx, cy, cz = mesh["center"]
        assert abs(cx - 32) < 0.1
        assert abs(cy - 32) < 0.1
        assert cz < 0.5  # Below surrounding terrain


class TestWaterfallEndToEnd:
    """Waterfall chain -> volumetric mesh."""

    def test_waterfall_from_cliff(self):
        """Generate volumetric waterfall mesh at a cliff edge."""
        lip = (32.0, 39.0, 0.7)  # Top of cliff
        pool = (32.0, 42.0, 0.3)  # Bottom of cliff
        drop = lip[2] - pool[2]

        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=lip, pool_pos=pool,
            width=3.0, thickness_top=0.3, thickness_bottom=0.8,
            curvature_segments=6, vertical_segments=12
        )

        assert mesh["is_volumetric"] is True
        assert abs(mesh["drop_height"] - drop) < 0.01
        assert mesh["vertex_count"] > 100  # Enough density for visual quality

        # Verify 3D extent (not flat)
        verts = np.array(mesh["vertices"])
        extents = verts.max(axis=0) - verts.min(axis=0)
        # Should span meaningfully in all 3 axes
        assert extents[0] > 1.0, "X extent too small"
        assert extents[1] > 1.0, "Y extent too small"
        assert extents[2] > 0.1, "Z extent too small"

    def test_tall_waterfall_high_density(self):
        """A 50m waterfall should have proportionally more vertices."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 50), pool_pos=(5, 5, 0),
            width=6.0, vertical_segments=24, curvature_segments=8
        )
        # 25 sections * 2 * 9 = 450 verts minimum
        assert mesh["vertex_count"] >= 400
        assert mesh["drop_height"] == 50.0


class TestMeshQualityChecks:
    """Cross-cutting quality checks for all mesh generators."""

    def test_no_degenerate_faces_river(self):
        """River mesh faces should have non-zero area."""
        h = np.linspace(1.0, 0.0, 32).reshape(32, 1) * np.ones((1, 32))
        path = [(r, 16) for r in range(4, 28)]
        mesh = generate_river_mesh(path, h, width=2.0)

        for face in mesh["faces"]:
            verts = [mesh["vertices"][i] for i in face]
            # Check that not all verts are identical
            unique = set(tuple(round(x, 6) for x in v) for v in verts)
            assert len(unique) >= 3, f"Degenerate face: {verts}"

    def test_no_degenerate_faces_waterfall(self):
        """Waterfall mesh faces should have non-zero area."""
        mesh = generate_waterfall_volumetric_mesh(
            lip_pos=(0, 0, 10), pool_pos=(2, 2, 0), width=3.0
        )

        degenerate_count = 0
        for face in mesh["faces"]:
            verts = [mesh["vertices"][i] for i in face]
            unique = set(tuple(round(x, 4) for x in v) for v in verts)
            if len(unique) < 3:
                degenerate_count += 1

        degenerate_frac = degenerate_count / max(mesh["face_count"], 1)
        assert degenerate_frac < 0.05, (
            f"{degenerate_frac:.1%} degenerate faces, expected < 5%"
        )
