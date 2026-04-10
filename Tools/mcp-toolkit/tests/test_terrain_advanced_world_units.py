"""Test that world-unit heights pass through terrain_advanced.py helpers unchanged — Addendum 3 compliance.

Verifies that compute_erosion_brush and flatten_terrain_zone preserve
world-unit scale (heights > 1.0) and do not normalize or clip to [0, 1].
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_advanced import (
    compute_erosion_brush,
    flatten_terrain_zone,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _world_unit_heightmap(size: int = 32, max_h: float = 85.0, seed: int = 42) -> np.ndarray:
    """Create a heightmap with world-unit heights (well above 1.0)."""
    rng = np.random.RandomState(seed)
    base = rng.rand(size, size).astype(np.float64) * max_h * 0.8 + max_h * 0.1
    # Add a slope so erosion brush has material to move
    xs = np.linspace(0.0, 1.0, size)
    slope = np.outer(xs, np.ones(size)) * max_h * 0.2
    return base + slope


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeErosionBrushWorldUnits:
    """compute_erosion_brush must not clip heights to [0, 1]."""

    def test_output_max_stays_in_input_range(self):
        """Eroded heightmap max should stay within the input range, not clip to 1.0."""
        hmap = _world_unit_heightmap(size=32, max_h=85.0)
        assert hmap.max() > 1.0, "Precondition: input must have world-unit heights"

        result = compute_erosion_brush(
            hmap,
            brush_center=(50.0, 50.0),
            brush_radius=20.0,
            erosion_type="hydraulic",
            iterations=5,
            strength=0.5,
            terrain_size=(100.0, 100.0),
            terrain_origin=(0.0, 0.0),
            seed=42,
        )
        # Result must still be in world units, not clipped to [0, 1]
        assert result.max() > 1.0, (
            f"Result max = {result.max()}, expected > 1.0 (world units preserved)"
        )
        # Result should not exceed the input max (erosion removes material)
        assert result.max() <= hmap.max() + 1e-6

    def test_erosion_actually_modifies_heightmap(self):
        """Brush erosion must change at least some cells (not a no-op)."""
        hmap = _world_unit_heightmap(size=32, max_h=85.0)
        result = compute_erosion_brush(
            hmap,
            brush_center=(50.0, 50.0),
            brush_radius=20.0,
            erosion_type="hydraulic",
            iterations=10,
            strength=0.8,
            terrain_size=(100.0, 100.0),
            seed=42,
        )
        assert not np.array_equal(hmap, result), "Erosion brush was a no-op"

    def test_thermal_erosion_preserves_world_units(self):
        """Thermal erosion type also preserves world-unit scale."""
        hmap = _world_unit_heightmap(size=32, max_h=120.0)
        result = compute_erosion_brush(
            hmap,
            brush_center=(50.0, 50.0),
            brush_radius=25.0,
            erosion_type="thermal",
            iterations=5,
            strength=0.5,
            terrain_size=(100.0, 100.0),
            seed=7,
        )
        assert result.max() > 1.0, "Thermal erosion clipped to [0, 1]"
        assert result.min() >= 0.0 - 1e-6


class TestFlattenTerrainZoneWorldUnits:
    """flatten_terrain_zone must preserve world-unit scale."""

    def test_flatten_preserves_world_unit_scale(self):
        """Flattened region height should be in world units, not [0, 1]."""
        hmap = _world_unit_heightmap(size=64, max_h=50.0)
        target = 35.0  # world-unit target
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.15, target_height=target
        )
        # Inside the flattened zone, mean should be near 35.0, not near 0.35
        rows, cols = result.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        dist = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        inside = dist < 0.10  # well inside radius

        mean_inside = float(result[inside].mean())
        assert abs(mean_inside - target) < 1.0, (
            f"Flattened zone mean = {mean_inside}, expected ~{target}"
        )
        # The overall max should still be in world units
        assert result.max() > 1.0, "Flatten clipped output to [0, 1]"

    def test_flatten_auto_target_stays_in_world_units(self):
        """Auto target_height (None) should derive from world-unit area mean."""
        hmap = _world_unit_heightmap(size=64, max_h=40.0)
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.15
        )
        # Auto target should be ~mid-range of input (well above 1.0)
        rows, cols = result.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        dist = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        inside = dist < 0.10

        mean_inside = float(result[inside].mean())
        assert mean_inside > 1.0, (
            f"Auto-target flatten mean = {mean_inside}, world units lost"
        )
