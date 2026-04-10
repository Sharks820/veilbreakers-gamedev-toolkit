"""Test flatten preserves world-unit scale -- Addendum 2 D.2 compliance."""
from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_advanced import flatten_terrain_zone


class TestFlattenPreservesScale:
    """Flatten must work in world units, not clip to [0,1]."""

    def _make_heightmap(self, max_height: float = 30.0, size: int = 64) -> np.ndarray:
        rng = np.random.default_rng(99)
        return rng.uniform(5.0, max_height, (size, size)).astype(np.float64)

    def test_flatten_at_world_height(self):
        """Flattening to 15m should produce ~15m, not 0.5."""
        hmap = self._make_heightmap(max_height=30.0)
        # center_x/y are normalized [0,1]; radius is also normalized
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.2, target_height=15.0,
        )
        center_val = float(result[32, 32])
        assert abs(center_val - 15.0) < 2.0, (
            f"Flattened center is {center_val:.2f}, expected ~15 (normalized?)"
        )

    def test_flatten_preserves_surrounding_scale(self):
        """Terrain outside flatten zone should stay in world units."""
        hmap = self._make_heightmap(max_height=30.0)
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.1, target_height=10.0,
        )
        corner_val = float(result[0, 0])
        assert corner_val > 1.0, (
            f"Far corner is {corner_val:.3f} -- terrain was normalized to [0,1]"
        )

    def test_flatten_output_not_clipped(self):
        """Output must not be clipped to [0,1]."""
        hmap = self._make_heightmap(max_height=50.0)
        result = flatten_terrain_zone(
            hmap, center_x=0.5, center_y=0.5, radius=0.05, target_height=25.0,
        )
        assert float(result.max()) > 1.0, (
            f"Max {result.max():.3f} <= 1.0 -- output was clipped"
        )
