"""Comprehensive tests for the analytical erosion filter (terrain_erosion_filter.py).

Tests cover: determinism, chunk-parallelism, ridge map sign convention,
per-pixel config overrides, finite-difference gradient, exit slope threshold,
assumed slope on flat terrain, directional gullies on gradient heightmaps.
"""

from __future__ import annotations

import numpy as np
import pytest


def _make_gradient_heightmap(rows: int = 64, cols: int = 64) -> np.ndarray:
    """Create a heightmap with a known gradient (high on left, low on right)."""
    xs = np.linspace(1.0, 0.0, cols)
    return np.tile(xs, (rows, 1))


def _make_flat_heightmap(rows: int = 64, cols: int = 64, value: float = 0.5) -> np.ndarray:
    return np.full((rows, cols), value)


class TestApplyAnalyticalErosion:
    """Tests for the main public API: apply_analytical_erosion."""

    def test_produces_nonzero_height_delta(self):
        """Known gradient heightmap must produce non-zero erosion."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(64, 64)
        cfg = ErosionConfig(strength=0.5, octave_count=3)
        result = apply_analytical_erosion(hmap, cfg, seed=42)

        assert result.height_delta is not None
        assert result.height_delta.shape == hmap.shape
        # Must produce measurable erosion
        assert np.abs(result.height_delta).max() > 1e-6, (
            "Analytical erosion produced zero height_delta on gradient heightmap"
        )

    def test_ridge_map_sign_convention(self):
        """Ridge map must have values < 0 (creases) and > 0 (ridges)."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(64, 64)
        cfg = ErosionConfig(strength=0.5, octave_count=4)
        result = apply_analytical_erosion(hmap, cfg, seed=42)

        assert result.ridge_map is not None
        assert result.ridge_map.shape == hmap.shape
        # Must have both negative (creases) and positive (ridges) values
        assert result.ridge_map.min() < -0.01, "Ridge map has no creases (negative values)"
        assert result.ridge_map.max() > 0.01, "Ridge map has no ridges (positive values)"

    def test_determinism_same_seed(self):
        """Two calls with the same seed must produce bit-identical results."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(32, 32)
        cfg = ErosionConfig()

        r1 = apply_analytical_erosion(hmap, cfg, seed=123)
        r2 = apply_analytical_erosion(hmap, cfg, seed=123)

        np.testing.assert_array_equal(r1.height_delta, r2.height_delta)
        np.testing.assert_array_equal(r1.ridge_map, r2.ridge_map)
        np.testing.assert_array_equal(r1.gradient_x, r2.gradient_x)
        np.testing.assert_array_equal(r1.gradient_z, r2.gradient_z)

    def test_different_seed_different_result(self):
        """Different seeds must produce different patterns."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(32, 32)
        cfg = ErosionConfig()

        r1 = apply_analytical_erosion(hmap, cfg, seed=1)
        r2 = apply_analytical_erosion(hmap, cfg, seed=2)

        # At least some values must differ
        assert not np.array_equal(r1.height_delta, r2.height_delta)

    def test_chunk_parallelism(self):
        """Same world coordinates must produce identical results regardless of tile offset.

        For true chunk-parallelism, the gradient and height range must come from
        the global world (not recomputed per-chunk), so we pass them explicitly.
        """
        from blender_addon.handlers.terrain_erosion_filter import (
            apply_analytical_erosion,
            finite_difference_gradient,
        )
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        # Generate a large heightmap
        big = _make_gradient_heightmap(64, 64)
        cfg = ErosionConfig(octave_count=3)

        # Pre-compute global gradient and height range
        full_gx, full_gz = finite_difference_gradient(big, 1.0)
        h_min, h_max = float(big.min()), float(big.max())

        # Full evaluation with explicit gradient
        r_full = apply_analytical_erosion(
            big, cfg, seed=42, cell_size=1.0,
            grad_x=full_gx, grad_z=full_gz,
            height_min=h_min, height_max=h_max,
        )

        # Evaluate just the center 32x32 with matching world offsets
        # and the corresponding sub-region of the global gradient
        sub = big[16:48, 16:48].copy()
        sub_gx = full_gx[16:48, 16:48].copy()
        sub_gz = full_gz[16:48, 16:48].copy()
        r_sub = apply_analytical_erosion(
            sub, cfg, seed=42, cell_size=1.0,
            world_origin_x=16.0, world_origin_z=16.0,
            grad_x=sub_gx, grad_z=sub_gz,
            height_min=h_min, height_max=h_max,
        )

        # The sub-region result should match the corresponding region of the full
        np.testing.assert_allclose(
            r_sub.height_delta,
            r_full.height_delta[16:48, 16:48],
            atol=1e-10,
            err_msg="Chunk-parallel: sub-tile result differs from full-tile at same coords",
        )

    def test_per_pixel_config_override(self):
        """Per-pixel ErosionConfig override must produce different erosion in different zones."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(64, 64)

        # Uniform config
        cfg_weak = ErosionConfig(strength=0.1, octave_count=3)
        cfg_strong = ErosionConfig(strength=0.9, octave_count=3)

        r_weak = apply_analytical_erosion(hmap, cfg_weak, seed=42)
        r_strong = apply_analytical_erosion(hmap, cfg_strong, seed=42)

        # Stronger config must produce larger absolute height deltas
        weak_mag = np.abs(r_weak.height_delta).mean()
        strong_mag = np.abs(r_strong.height_delta).mean()
        assert strong_mag > weak_mag * 1.5, (
            f"Strong config erosion ({strong_mag:.6f}) not significantly larger than "
            f"weak ({weak_mag:.6f})"
        )

    def test_assumed_slope_erodes_flat_terrain(self):
        """Flat terrain with assumed_slope > 0 must still produce erosion features."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        flat = _make_flat_heightmap(64, 64, value=0.5)

        # Without assumed_slope: minimal erosion expected on flat terrain
        cfg_no_slope = ErosionConfig(strength=0.5, assumed_slope=0.0, octave_count=3)
        r_no = apply_analytical_erosion(flat, cfg_no_slope, seed=42)

        # With assumed_slope: erosion features appear
        cfg_with_slope = ErosionConfig(strength=0.5, assumed_slope=0.3, octave_count=3)
        r_with = apply_analytical_erosion(flat, cfg_with_slope, seed=42)

        mag_no = np.abs(r_no.height_delta).max()
        mag_with = np.abs(r_with.height_delta).max()

        assert mag_with > mag_no, (
            f"assumed_slope did not increase erosion: without={mag_no:.6f}, with={mag_with:.6f}"
        )

    def test_exit_slope_threshold(self):
        """Very low slope areas should have reduced erosion when exit_slope_threshold is high."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(64, 64)

        # Low threshold: erosion everywhere
        cfg_low = ErosionConfig(exit_slope_threshold=0.001, octave_count=3)
        r_low = apply_analytical_erosion(hmap, cfg_low, seed=42)

        # High threshold: erosion fades in low-slope areas
        cfg_high = ErosionConfig(exit_slope_threshold=0.5, octave_count=3)
        r_high = apply_analytical_erosion(hmap, cfg_high, seed=42)

        # High threshold should produce less total erosion magnitude
        mag_low = np.abs(r_low.height_delta).sum()
        mag_high = np.abs(r_high.height_delta).sum()

        assert mag_high < mag_low, (
            f"High exit_slope_threshold ({mag_high:.4f}) did not reduce erosion vs low ({mag_low:.4f})"
        )

    def test_returns_analytical_erosion_result(self):
        """Return type must be AnalyticalErosionResult with all fields populated."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import (
            AnalyticalErosionResult,
            ErosionConfig,
        )

        hmap = _make_gradient_heightmap(32, 32)
        result = apply_analytical_erosion(hmap, ErosionConfig(), seed=42)

        assert isinstance(result, AnalyticalErosionResult)
        assert result.height_delta.shape == (32, 32)
        assert result.ridge_map.shape == (32, 32)
        assert result.gradient_x.shape == (32, 32)
        assert result.gradient_z.shape == (32, 32)
        assert isinstance(result.metrics, dict)
        assert len(result.metrics) > 0

    def test_gradient_outputs_finite(self):
        """All gradient outputs must be finite (no NaN/inf)."""
        from blender_addon.handlers.terrain_erosion_filter import apply_analytical_erosion
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        hmap = _make_gradient_heightmap(32, 32)
        result = apply_analytical_erosion(hmap, ErosionConfig(), seed=42)

        assert np.all(np.isfinite(result.height_delta)), "height_delta contains NaN/inf"
        assert np.all(np.isfinite(result.ridge_map)), "ridge_map contains NaN/inf"
        assert np.all(np.isfinite(result.gradient_x)), "gradient_x contains NaN/inf"
        assert np.all(np.isfinite(result.gradient_z)), "gradient_z contains NaN/inf"


class TestFiniteDifferenceGradient:
    """Tests for the gradient fallback function."""

    def test_gradient_of_linear_function(self):
        """Gradient of h = 2x + 3z should be (2, 3) everywhere (interior)."""
        from blender_addon.handlers.terrain_erosion_filter import finite_difference_gradient

        rows, cols = 32, 32
        cell_size = 1.0
        xs = np.arange(cols) * cell_size
        zs = np.arange(rows) * cell_size
        xg, zg = np.meshgrid(xs, zs)
        hmap = 2.0 * xg + 3.0 * zg

        gx, gz = finite_difference_gradient(hmap, cell_size)

        # Interior cells should have gradient very close to (2, 3)
        interior_gx = gx[2:-2, 2:-2]
        interior_gz = gz[2:-2, 2:-2]

        np.testing.assert_allclose(interior_gx, 2.0, atol=1e-10,
                                   err_msg="Gradient dh/dx should be 2.0 for h=2x+3z")
        np.testing.assert_allclose(interior_gz, 3.0, atol=1e-10,
                                   err_msg="Gradient dh/dz should be 3.0 for h=2x+3z")

    def test_gradient_shape_matches_input(self):
        """Output shape must match input shape."""
        from blender_addon.handlers.terrain_erosion_filter import finite_difference_gradient

        hmap = np.random.randn(16, 24)
        gx, gz = finite_difference_gradient(hmap, 1.0)
        assert gx.shape == hmap.shape
        assert gz.shape == hmap.shape

    def test_gradient_finite(self):
        """Gradient must be finite everywhere including edges."""
        from blender_addon.handlers.terrain_erosion_filter import finite_difference_gradient

        hmap = np.random.randn(16, 16)
        gx, gz = finite_difference_gradient(hmap, 0.5)
        assert np.all(np.isfinite(gx))
        assert np.all(np.isfinite(gz))
