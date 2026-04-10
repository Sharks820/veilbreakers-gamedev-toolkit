"""Test erosion paint preserves world-unit scale -- Addendum 2 D.2 compliance."""
from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers._terrain_erosion import (
    apply_hydraulic_erosion_masks,
)


class TestErosionPaintPreservesScale:
    """Erosion must operate in world units, never clip to [0,1]."""

    def _make_heightmap(self, max_height: float = 47.3, size: int = 64) -> np.ndarray:
        rng = np.random.default_rng(42)
        base = rng.uniform(0.0, max_height, (size, size))
        ridge = np.linspace(0, max_height, size).reshape(1, -1)
        return (base * 0.3 + ridge * 0.7).astype(np.float64)

    def test_erosion_output_stays_in_world_units(self):
        """Result must NOT be clipped to [0,1]."""
        hmap = self._make_heightmap(max_height=47.3)
        result = apply_hydraulic_erosion_masks(hmap, iterations=50)
        eroded = result.height
        assert float(eroded.max()) > 1.0, (
            f"Eroded max {eroded.max():.3f} <= 1.0 -- output was normalized"
        )

    def test_erosion_does_not_exceed_original_max(self):
        """Erosion removes material; max should not increase significantly."""
        hmap = self._make_heightmap(max_height=47.3)
        original_max = float(hmap.max())
        result = apply_hydraulic_erosion_masks(hmap, iterations=50)
        eroded = result.height
        assert float(eroded.max()) <= original_max + 0.5, (
            f"Eroded max {eroded.max():.3f} > original {original_max:.3f}"
        )

    def test_erosion_result_has_sediment_accumulation(self):
        """ErosionMasks must include sediment_accumulation_at_base (Addendum 1 D.1)."""
        hmap = self._make_heightmap(max_height=20.0)
        result = apply_hydraulic_erosion_masks(hmap, iterations=50)
        assert hasattr(result, "sediment_accumulation_at_base"), (
            "ErosionMasks missing sediment_accumulation_at_base field"
        )

    def test_erosion_result_has_pool_deepening(self):
        """ErosionMasks must include pool_deepening_delta (Addendum 1 D.1)."""
        hmap = self._make_heightmap(max_height=20.0)
        result = apply_hydraulic_erosion_masks(hmap, iterations=50)
        assert hasattr(result, "pool_deepening_delta"), (
            "ErosionMasks missing pool_deepening_delta field"
        )
