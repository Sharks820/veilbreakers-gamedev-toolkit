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
        """All eroded values stay within the input range."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_hydraulic_erosion(hmap, iterations=50, seed=42)
        assert result.min() >= hmap.min() - 1e-12
        assert result.max() <= hmap.max() + 1e-12

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
        """All eroded values stay within the input range."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.random.RandomState(42).rand(32, 32)
        result = apply_thermal_erosion(hmap, iterations=10, talus_angle=45.0)
        assert result.min() >= hmap.min() - 1e-12
        assert result.max() <= hmap.max() + 1e-12

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


# ---------------------------------------------------------------------------
# High-iteration erosion quality tests
# ---------------------------------------------------------------------------


class TestErosionHighIterationAndWorldUnits:
    """Stress tests for high-iteration erosion and world-unit inputs."""

    def test_erosion_50k_visible_channels(self):
        """50K droplet erosion on 64x64 heightmap carves channels > 0.05 depth."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion
        from blender_addon.handlers._terrain_noise import generate_heightmap

        # Generate a mountainous heightmap with real terrain features
        hmap = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        original = hmap.copy()

        # Run 50K droplets -- this is the AAA quality threshold
        eroded = apply_hydraulic_erosion(hmap, iterations=50000, seed=42)

        # Compute max channel depth (where erosion carved the most)
        depth_map = original - eroded
        max_channel_depth = float(depth_map.max())

        assert max_channel_depth > 0.05, (
            f"Max channel depth {max_channel_depth:.4f} is too shallow (< 0.05). "
            f"50K droplets should carve visible river channels."
        )

    def test_erosion_50k_stays_in_bounds(self):
        """50K droplet erosion keeps values within the input range."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        eroded = apply_hydraulic_erosion(hmap, iterations=50000, seed=42)
        assert eroded.min() >= hmap.min() - 1e-12
        assert eroded.max() <= hmap.max() + 1e-12

    def test_hydraulic_world_unit_height_range_is_supported(self):
        """Hydraulic erosion supports arbitrary world-unit height ranges."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        base = np.linspace(10.0, 30.0, 64 * 64, dtype=np.float64).reshape(64, 64)
        hmap = base + np.random.RandomState(42).rand(64, 64) * 0.5
        result = apply_hydraulic_erosion(
            hmap,
            iterations=200,
            seed=42,
            height_range=float(hmap.max() - hmap.min()),
        )
        assert result.shape == hmap.shape
        assert result.min() >= hmap.min() - 1e-12
        assert result.max() <= hmap.max() + 1e-12
        assert not np.array_equal(result, hmap)

    def test_thermal_world_unit_height_range_is_supported(self):
        """Thermal erosion supports arbitrary world-unit height ranges."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.linspace(-5.0, 17.0, 32 * 32, dtype=np.float64).reshape(32, 32)
        result = apply_thermal_erosion(hmap, iterations=12, talus_angle=35.0)
        assert result.shape == hmap.shape
        assert result.min() >= hmap.min() - 1e-12
        assert result.max() <= hmap.max() + 1e-12

    def test_thermal_cell_size_affects_world_space_threshold(self):
        """Larger sample spacing should reduce talus transfer for the same height delta."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.zeros((9, 9), dtype=np.float64)
        hmap[4, 4] = 1.0
        fine = apply_thermal_erosion(hmap, iterations=8, talus_angle=35.0, cell_size=1.0)
        coarse = apply_thermal_erosion(hmap, iterations=8, talus_angle=35.0, cell_size=4.0)
        assert coarse[4, 4] >= fine[4, 4]
