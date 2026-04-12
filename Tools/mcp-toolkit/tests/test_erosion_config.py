"""Tests for ErosionConfig, AnalyticalErosionResult, and ErosionMasks.ridge_map."""

from __future__ import annotations

import numpy as np
import pytest


class TestErosionConfig:
    """ErosionConfig must have all 12 fields with sensible defaults."""

    def test_all_twelve_fields_exist(self):
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        cfg = ErosionConfig()
        fields = [
            "strength",
            "gully_weight",
            "detail",
            "rounding",
            "onset",
            "assumed_slope",
            "normalization",
            "fade_amplitude",
            "exit_slope_threshold",
            "cell_scale",
            "octave_count",
            "frequency",
        ]
        for f in fields:
            assert hasattr(cfg, f), f"ErosionConfig missing field: {f}"

    def test_default_values_sensible(self):
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        cfg = ErosionConfig()
        assert 0.0 < cfg.strength <= 1.0
        assert cfg.gully_weight > 0.0
        assert 0.0 <= cfg.detail <= 1.0
        assert cfg.normalization > 0.0
        assert cfg.fade_amplitude > 0.0
        assert cfg.exit_slope_threshold > 0.0
        assert cfg.cell_scale > 0.0
        assert cfg.octave_count >= 1
        assert cfg.frequency > 0.0

    def test_custom_values(self):
        from blender_addon.handlers._terrain_erosion import ErosionConfig

        cfg = ErosionConfig(strength=0.8, octave_count=6, frequency=2.0)
        assert cfg.strength == 0.8
        assert cfg.octave_count == 6
        assert cfg.frequency == 2.0


class TestAnalyticalErosionResult:
    """AnalyticalErosionResult must have height_delta, ridge_map, gradient_x, gradient_z."""

    def test_fields_exist(self):
        from blender_addon.handlers._terrain_erosion import AnalyticalErosionResult

        arr = np.zeros((4, 4))
        result = AnalyticalErosionResult(
            height_delta=arr,
            ridge_map=arr,
            gradient_x=arr,
            gradient_z=arr,
            metrics={},
        )
        assert result.height_delta is not None
        assert result.ridge_map is not None
        assert result.gradient_x is not None
        assert result.gradient_z is not None
        assert isinstance(result.metrics, dict)

    def test_arrays_are_numpy(self):
        from blender_addon.handlers._terrain_erosion import AnalyticalErosionResult

        arr = np.ones((8, 8))
        result = AnalyticalErosionResult(
            height_delta=arr * 0.1,
            ridge_map=arr * -0.5,
            gradient_x=arr * 0.3,
            gradient_z=arr * -0.2,
            metrics={"test": True},
        )
        assert isinstance(result.height_delta, np.ndarray)
        assert isinstance(result.ridge_map, np.ndarray)
        assert result.height_delta.shape == (8, 8)
        assert result.metrics["test"] is True


class TestErosionMasksRidgeMap:
    """ErosionMasks must have an optional ridge_map field."""

    def test_ridge_map_field_exists(self):
        from blender_addon.handlers._terrain_erosion import ErosionMasks

        arr = np.zeros((4, 4))
        masks = ErosionMasks(
            height=arr,
            erosion_amount=arr,
            deposition_amount=arr,
            wetness=arr,
            drainage=arr,
            bank_instability=arr,
        )
        # ridge_map should exist as a field (default None)
        assert hasattr(masks, "ridge_map")

    def test_ridge_map_accepts_array(self):
        from blender_addon.handlers._terrain_erosion import ErosionMasks

        arr = np.zeros((4, 4))
        ridge = np.random.randn(4, 4)
        masks = ErosionMasks(
            height=arr,
            erosion_amount=arr,
            deposition_amount=arr,
            wetness=arr,
            drainage=arr,
            bank_instability=arr,
            ridge_map=ridge,
        )
        np.testing.assert_array_equal(masks.ridge_map, ridge)
