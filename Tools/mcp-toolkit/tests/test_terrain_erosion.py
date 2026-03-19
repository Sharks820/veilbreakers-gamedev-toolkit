"""Unit tests for terrain erosion algorithms.

Tests _terrain_erosion.py pure-logic functions: apply_hydraulic_erosion
and apply_thermal_erosion.
"""

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Hydraulic erosion tests
# ---------------------------------------------------------------------------


class TestApplyHydraulicErosion:
    """Test droplet-based hydraulic erosion on heightmaps."""

    def test_returns_same_shape(self):
        """Eroded heightmap has same shape as input."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        assert result.shape == hmap.shape

    def test_values_in_0_1_range(self):
        """All eroded values are clamped to [0, 1]."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_erosion_modifies_heightmap(self):
        """Eroded heightmap differs from input (erosion did something)."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_hydraulic_erosion(hmap, iterations=100, seed=42)
        assert not np.array_equal(hmap, result)

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical erosion results."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        r1 = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        r2 = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        np.testing.assert_array_equal(r1, r2)

    def test_different_seeds_differ(self):
        """Different seeds produce different erosion results."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        r1 = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        r2 = apply_hydraulic_erosion(hmap, iterations=50, seed=99)
        assert not np.array_equal(r1, r2)

    def test_flat_heightmap_minimal_change(self):
        """Erosion on a flat heightmap returns near-identical array."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.full((32, 32), 0.5)
        result = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        # Should be very close to original (minimal erosion on flat terrain)
        assert np.allclose(hmap, result, atol=0.05)

    def test_returns_ndarray(self):
        """Return type is numpy ndarray."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(16, 16)
        result = apply_hydraulic_erosion(hmap, iterations=10, seed=42)
        assert isinstance(result, np.ndarray)


# ---------------------------------------------------------------------------
# Thermal erosion tests
# ---------------------------------------------------------------------------


class TestApplyThermalErosion:
    """Test talus-based thermal erosion on heightmaps."""

    def test_returns_same_shape(self):
        """Eroded heightmap has same shape as input."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_thermal_erosion(hmap, iterations=10, talus_angle=45.0)
        assert result.shape == hmap.shape

    def test_values_in_0_1_range(self):
        """All eroded values are clamped to [0, 1]."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_thermal_erosion(hmap, iterations=10, talus_angle=45.0)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_erosion_reduces_max_slope(self):
        """Thermal erosion reduces the maximum slope (material redistributed)."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        # Create heightmap with steep slopes
        hmap = np.zeros((16, 16))
        hmap[8, 8] = 1.0  # Steep peak

        result = apply_thermal_erosion(hmap, iterations=20, talus_angle=30.0)

        # Max slope should be reduced
        orig_max_diff = 1.0  # peak vs neighbor
        new_max_diff = 0.0
        for r in range(1, 15):
            for c in range(1, 15):
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    diff = abs(result[r, c] - result[r + dr, c + dc])
                    new_max_diff = max(new_max_diff, diff)

        assert new_max_diff < orig_max_diff

    def test_flat_heightmap_no_change(self):
        """Erosion on a flat heightmap returns near-identical array."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.full((16, 16), 0.5)
        result = apply_thermal_erosion(hmap, iterations=10, talus_angle=45.0)
        np.testing.assert_allclose(hmap, result, atol=1e-10)

    def test_returns_ndarray(self):
        """Return type is numpy ndarray."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.random.RandomState(42).rand(16, 16)
        result = apply_thermal_erosion(hmap, iterations=5, talus_angle=45.0)
        assert isinstance(result, np.ndarray)

    def test_does_not_create_values_outside_bounds(self):
        """Edge case: heightmap with extremes doesn't break bounds."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.zeros((16, 16))
        hmap[::2, ::2] = 1.0  # Checkerboard pattern
        result = apply_thermal_erosion(hmap, iterations=10, talus_angle=20.0)
        assert result.min() >= 0.0
        assert result.max() <= 1.0
