"""Tests for BakedTerrain dataclass — the single contract between DAG and mesh builder.

Phase 53-01 Task 1: BakedTerrain with height_grid, ridge_map, gradient,
material_masks, metadata, sampling, serialization.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest


def _make_baked(size: int = 8) -> "BakedTerrain":
    """Create a minimal BakedTerrain for testing."""
    from blender_addon.handlers.terrain_baked import BakedTerrain

    height = np.linspace(0.0, 10.0, size * size, dtype=np.float32).reshape(size, size)
    ridge = np.random.default_rng(42).uniform(-1, 1, (size, size)).astype(np.float32)
    # Gradient: dh/dx and dh/dz from numpy gradient
    gz, gx = np.gradient(height)
    material_masks = {
        "rock": np.ones((size, size), dtype=np.float32) * 0.5,
        "grass": np.ones((size, size), dtype=np.float32) * 0.3,
    }
    metadata = {
        "seed": 42,
        "tile_x": 0,
        "tile_y": 0,
        "world_origin_x": 0.0,
        "world_origin_y": 0.0,
        "cell_size": 1.0,
    }
    return BakedTerrain(
        height_grid=height,
        ridge_map=ridge,
        gradient_x=gx.astype(np.float32),
        gradient_z=gz.astype(np.float32),
        material_masks=material_masks,
        metadata=metadata,
    )


class TestBakedTerrainConstruction:
    """BakedTerrain can be constructed with all required fields."""

    def test_construct_with_all_fields(self):
        bt = _make_baked()
        assert bt.height_grid.shape == (8, 8)
        assert bt.ridge_map.shape == (8, 8)
        assert bt.gradient_x.shape == (8, 8)
        assert bt.gradient_z.shape == (8, 8)
        assert "rock" in bt.material_masks
        assert "grass" in bt.material_masks
        assert bt.metadata["seed"] == 42

    def test_rejects_mismatched_shapes(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        height = np.zeros((8, 8), dtype=np.float32)
        ridge = np.zeros((4, 4), dtype=np.float32)  # wrong shape
        gx = np.zeros((8, 8), dtype=np.float32)
        gz = np.zeros((8, 8), dtype=np.float32)
        with pytest.raises(ValueError, match="shape"):
            BakedTerrain(
                height_grid=height,
                ridge_map=ridge,
                gradient_x=gx,
                gradient_z=gz,
                material_masks={},
                metadata={},
            )

    def test_rejects_non_2d_height(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        with pytest.raises(ValueError, match="2D"):
            BakedTerrain(
                height_grid=np.zeros(64, dtype=np.float32),
                ridge_map=np.zeros((8, 8), dtype=np.float32),
                gradient_x=np.zeros((8, 8), dtype=np.float32),
                gradient_z=np.zeros((8, 8), dtype=np.float32),
                material_masks={},
                metadata={},
            )


class TestBakedTerrainSampling:
    """BakedTerrain.sample_height, get_gradient, get_slope."""

    def test_sample_height_at_grid_center(self):
        bt = _make_baked(size=8)
        # Cell size is 1.0, world origin is (0,0), so grid covers [0..7]
        h = bt.sample_height(3.0, 3.0)
        assert isinstance(h, float)
        # Height at (3,3) in a linear 0..10 grid should be deterministic
        assert 0.0 <= h <= 10.0

    def test_sample_height_interpolates(self):
        bt = _make_baked(size=8)
        h_a = bt.sample_height(2.0, 2.0)
        h_b = bt.sample_height(3.0, 3.0)
        h_mid = bt.sample_height(2.5, 2.5)
        # Bilinear interpolation: midpoint should be between the two
        assert min(h_a, h_b) - 0.1 <= h_mid <= max(h_a, h_b) + 0.1

    def test_sample_height_clamps_out_of_bounds(self):
        bt = _make_baked(size=8)
        # Should not raise, should clamp to edge
        h = bt.sample_height(-100.0, -100.0)
        assert isinstance(h, float)
        h2 = bt.sample_height(1000.0, 1000.0)
        assert isinstance(h2, float)

    def test_get_gradient_returns_tuple(self):
        bt = _make_baked(size=8)
        gx, gz = bt.get_gradient(3.0, 3.0)
        assert isinstance(gx, float)
        assert isinstance(gz, float)

    def test_get_slope_returns_nonneg(self):
        bt = _make_baked(size=8)
        s = bt.get_slope(3.0, 3.0)
        assert isinstance(s, float)
        assert s >= 0.0


class TestBakedTerrainSerialization:
    """BakedTerrain round-trips through npz."""

    def test_to_npz_creates_file(self):
        bt = _make_baked()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.npz"
            bt.to_npz(str(path))
            assert path.exists()
            assert path.stat().st_size > 0

    def test_round_trip(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        bt = _make_baked()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.npz"
            bt.to_npz(str(path))
            bt2 = BakedTerrain.from_npz(str(path))
            np.testing.assert_array_almost_equal(bt2.height_grid, bt.height_grid)
            np.testing.assert_array_almost_equal(bt2.ridge_map, bt.ridge_map)
            np.testing.assert_array_almost_equal(bt2.gradient_x, bt.gradient_x)
            np.testing.assert_array_almost_equal(bt2.gradient_z, bt.gradient_z)
            assert set(bt2.material_masks.keys()) == set(bt.material_masks.keys())
            for k in bt.material_masks:
                np.testing.assert_array_almost_equal(
                    bt2.material_masks[k], bt.material_masks[k]
                )
            assert bt2.metadata["seed"] == bt.metadata["seed"]

    def test_from_npz_rejects_missing_file(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        with pytest.raises((FileNotFoundError, OSError)):
            BakedTerrain.from_npz("/nonexistent/path.npz")


class TestBakedTerrainFloat64Preservation:
    """Float64 inputs must not be silently downcast to float32."""

    def test_float64_height_preserved(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        size = 4
        height = np.linspace(0.0, 10.0, size * size, dtype=np.float64).reshape(size, size)
        ridge = np.zeros((size, size), dtype=np.float64)
        gx = np.zeros((size, size), dtype=np.float64)
        gz = np.zeros((size, size), dtype=np.float64)
        bt = BakedTerrain(
            height_grid=height,
            ridge_map=ridge,
            gradient_x=gx,
            gradient_z=gz,
            material_masks={},
            metadata={},
        )
        assert bt.height_grid.dtype == np.float64, (
            f"Expected float64, got {bt.height_grid.dtype}"
        )
        assert bt.ridge_map.dtype == np.float64
        assert bt.gradient_x.dtype == np.float64
        assert bt.gradient_z.dtype == np.float64

    def test_float32_still_accepted(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        size = 4
        height = np.zeros((size, size), dtype=np.float32)
        bt = BakedTerrain(
            height_grid=height,
            ridge_map=np.zeros((size, size), dtype=np.float32),
            gradient_x=np.zeros((size, size), dtype=np.float32),
            gradient_z=np.zeros((size, size), dtype=np.float32),
            material_masks={},
            metadata={},
        )
        assert bt.height_grid.dtype == np.float32


class TestBakedTerrainNumpyJsonEncoder:
    """Metadata with numpy scalars must serialize to JSON without crashing."""

    def test_numpy_scalars_in_metadata(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        size = 4
        height = np.zeros((size, size), dtype=np.float32)
        metadata = {
            "np_float": np.float64(3.14),
            "np_int": np.int64(42),
            "np_array": np.array([1, 2, 3]),
            "seed": 1,
        }
        bt = BakedTerrain(
            height_grid=height,
            ridge_map=np.zeros((size, size), dtype=np.float32),
            gradient_x=np.zeros((size, size), dtype=np.float32),
            gradient_z=np.zeros((size, size), dtype=np.float32),
            material_masks={},
            metadata=metadata,
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.npz"
            bt.to_npz(str(path))  # must not raise
            bt2 = BakedTerrain.from_npz(str(path))
            assert bt2.metadata["np_float"] == pytest.approx(3.14)
            assert bt2.metadata["np_int"] == 42
            assert bt2.metadata["np_array"] == [1, 2, 3]


class TestBakedTerrainLegacyOriginZ:
    """BakedTerrain with legacy world_origin_z metadata should still work."""

    def test_legacy_origin_z_fallback(self):
        from blender_addon.handlers.terrain_baked import BakedTerrain

        size = 4
        height = np.arange(16, dtype=np.float32).reshape(4, 4)
        metadata = {
            "world_origin_x": 0.0,
            "world_origin_z": 0.0,  # legacy key
            "cell_size": 1.0,
        }
        bt = BakedTerrain(
            height_grid=height,
            ridge_map=np.zeros((size, size), dtype=np.float32),
            gradient_x=np.zeros((size, size), dtype=np.float32),
            gradient_z=np.zeros((size, size), dtype=np.float32),
            material_masks={},
            metadata=metadata,
        )
        # Should use world_origin_z as fallback for world_origin_y
        h = bt.sample_height(0.0, 0.0)
        assert isinstance(h, float)
