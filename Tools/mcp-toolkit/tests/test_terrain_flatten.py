"""Tests for terrain flatten zone pure-logic functions.

Validates:
  - flatten_terrain_zone produces flat area inside radius (std < 0.01)
  - Smooth blend with no step discontinuity at transition boundary
  - target_height=None uses area average height
  - Terrain outside radius+blend_width is preserved unchanged
  - flatten_multiple_zones applies all zones sequentially
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_advanced import (
    flatten_terrain_zone,
    flatten_multiple_zones,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_noisy_heightmap(size: int = 64, seed: int = 42) -> np.ndarray:
    """Create a deterministic noisy heightmap for testing."""
    rng = np.random.RandomState(seed)
    return rng.rand(size, size).astype(np.float64) * 0.6 + 0.2  # range [0.2, 0.8]


# ---------------------------------------------------------------------------
# Tests: flatten_terrain_zone
# ---------------------------------------------------------------------------


class TestFlattenTerrainZone:
    """Tests for the flatten_terrain_zone pure-logic function."""

    def test_flatten_creates_flat_area(self):
        """64x64 heightmap, flatten at (0.5, 0.5) r=0.15 -> std < 0.01 inside."""
        hmap = _make_noisy_heightmap(64)
        result = flatten_terrain_zone(hmap, center_x=0.5, center_y=0.5, radius=0.15)

        rows, cols = result.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        dist = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        inside = dist < 0.15

        assert inside.any(), "No cells inside radius"
        std_inside = result[inside].std()
        assert std_inside < 0.01, f"std inside radius = {std_inside}, expected < 0.01"

    def test_flatten_smooth_blend(self):
        """Smooth blend: radial profile is monotonic with no sharp step.

        Uses a smooth (gradient) heightmap to isolate the blend behavior
        from underlying noise. Verifies that the transition from flat zone
        to surrounding terrain is C0-continuous (no step discontinuity).
        """
        # Create a smooth gradient heightmap so the blend is the only feature
        size = 128
        ys = np.arange(size, dtype=np.float64) / size
        xs = np.arange(size, dtype=np.float64) / size
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        hmap = 0.3 + 0.4 * xx  # smooth left-to-right gradient [0.3, 0.7]

        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.15, blend_width=0.15
        )

        # Sample a radial profile from center outward along X axis (y=0.5)
        mid_row = size // 2
        profile = result[mid_row, :]

        # Check no adjacent-cell step exceeds a reasonable threshold
        # For a 128-cell grid with smooth input, steps should be tiny
        diffs = np.abs(np.diff(profile))
        max_step = diffs.max()
        assert max_step < 0.05, (
            f"Max step in radial profile = {max_step}, expected < 0.05"
        )

    def test_flatten_target_height_auto(self):
        """With target_height=None, flattened area height equals area average."""
        hmap = _make_noisy_heightmap(64)
        rows, cols = hmap.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        dist = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        inside = dist < 0.15

        expected_height = float(hmap[inside].mean())
        result = flatten_terrain_zone(hmap, center_x=0.5, center_y=0.5, radius=0.15)

        mean_inside = float(result[inside].mean())
        assert abs(mean_inside - expected_height) < 0.02, (
            f"mean inside = {mean_inside}, expected ~{expected_height}"
        )

    def test_flatten_preserves_outside(self):
        """Cells beyond radius+blend_width are unchanged."""
        hmap = _make_noisy_heightmap(64)
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.1, blend_width=0.05
        )

        rows, cols = result.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        dist = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        outside = dist > 0.15 + 0.02  # small margin beyond blend

        assert outside.any(), "No cells outside the blend zone"
        assert np.allclose(result[outside], hmap[outside]), (
            "Terrain outside radius+blend_width was modified"
        )

    def test_flatten_explicit_target_height(self):
        """Explicit target_height should be used instead of auto-average."""
        hmap = _make_noisy_heightmap(64)
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.15, target_height=0.3
        )

        rows, cols = result.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")
        dist = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        inside = dist < 0.10  # well inside

        mean_inside = float(result[inside].mean())
        assert abs(mean_inside - 0.3) < 0.02, (
            f"mean inside = {mean_inside}, expected ~0.3"
        )

    def test_flatten_output_clipped(self):
        """Output should be clipped to [0, 1]."""
        hmap = _make_noisy_heightmap(64)
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.15, target_height=0.99
        )
        assert result.min() >= 0.0, f"min = {result.min()}"
        assert result.max() <= 1.0, f"max = {result.max()}"

    def test_flatten_returns_copy(self):
        """flatten_terrain_zone should not mutate the input."""
        hmap = _make_noisy_heightmap(64)
        original = hmap.copy()
        flatten_terrain_zone(hmap, center_x=0.5, center_y=0.5, radius=0.15)
        assert np.array_equal(hmap, original), "Input heightmap was mutated"


class TestFlattenMultipleZones:
    """Tests for flatten_multiple_zones."""

    def test_flatten_multiple_zones(self):
        """Apply 3 zones, verify all 3 areas are flat."""
        hmap = _make_noisy_heightmap(128)
        zones = [
            {"center_x": 0.25, "center_y": 0.25, "radius": 0.08},
            {"center_x": 0.75, "center_y": 0.25, "radius": 0.08},
            {"center_x": 0.5, "center_y": 0.75, "radius": 0.08},
        ]
        result = flatten_multiple_zones(hmap, zones)

        rows, cols = result.shape
        ys = np.arange(rows) / rows
        xs = np.arange(cols) / cols
        yy, xx = np.meshgrid(ys, xs, indexing="ij")

        for zone in zones:
            dist = np.sqrt(
                (xx - zone["center_x"]) ** 2 + (yy - zone["center_y"]) ** 2
            )
            inside = dist < zone["radius"]
            assert inside.any(), f"No cells inside zone at {zone['center_x']},{zone['center_y']}"
            std_inside = result[inside].std()
            assert std_inside < 0.01, (
                f"Zone ({zone['center_x']}, {zone['center_y']}): "
                f"std = {std_inside}, expected < 0.01"
            )

    def test_empty_zones_returns_original(self):
        """No zones means the heightmap is unchanged."""
        hmap = _make_noisy_heightmap(32)
        result = flatten_multiple_zones(hmap, [])
        assert np.array_equal(result, hmap)
