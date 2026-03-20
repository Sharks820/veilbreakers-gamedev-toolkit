"""Unit tests for palette_validator.py -- Dark fantasy palette validation (AAA-03).

Tests cover:
- Dark fantasy palette passing validation
- Oversaturated images failing
- Value range enforcement (too bright, too dark)
- Color temperature bias detection
- Custom rules override
- PALETTE_RULES constant structure
- ASSET_TYPE_BUDGETS constant values
- Roughness map variation detection
"""

import numpy as np
import pytest
from PIL import Image

from veilbreakers_mcp.shared.palette_validator import (
    ASSET_TYPE_BUDGETS,
    PALETTE_RULES,
    validate_palette,
    validate_roughness_map,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_solid_color(path: str, r: int, g: int, b: int, size: int = 64) -> str:
    """Create and save a solid color image."""
    img = Image.new("RGB", (size, size), (r, g, b))
    img.save(path)
    return path


def _save_array_image(path: str, arr: np.ndarray) -> str:
    """Save a numpy array as an RGB image."""
    img = Image.fromarray(arr.astype(np.uint8), "RGB")
    img.save(path)
    return path


def _save_grayscale(path: str, arr: np.ndarray) -> str:
    """Save a numpy array as a grayscale image."""
    img = Image.fromarray(arr.astype(np.uint8), "L")
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# TestPaletteValidator
# ---------------------------------------------------------------------------


class TestPaletteValidator:
    """Tests for albedo palette validation against dark fantasy rules."""

    def test_validate_dark_palette_passes(self, tmp_path):
        """Desaturated, cool-toned image passes validation."""
        # Create desaturated blue-gray image (typical dark fantasy)
        arr = np.full((64, 64, 3), [60, 70, 90], dtype=np.uint8)
        # Add some variation
        arr[0:32, :, :] = [50, 60, 80]
        path = _save_array_image(str(tmp_path / "dark_fantasy.png"), arr)

        result = validate_palette(path)

        assert result["passed"] is True
        assert len([i for i in result["issues"] if i["severity"] == "error"]) == 0

    def test_validate_oversaturated_fails(self, tmp_path):
        """Highly saturated neon image fails saturation cap."""
        # Bright saturated magenta
        path = _save_solid_color(str(tmp_path / "neon.png"), 255, 0, 255)

        result = validate_palette(path)

        assert result["passed"] is False
        sat_issues = [i for i in result["issues"] if i["rule"] == "saturation_cap"]
        assert len(sat_issues) > 0

    def test_validate_too_bright_fails(self, tmp_path):
        """Very bright white image reports brightness issue."""
        path = _save_solid_color(str(tmp_path / "bright.png"), 240, 240, 240)

        result = validate_palette(path)

        bright_issues = [i for i in result["issues"] if i["rule"] == "value_too_bright"]
        assert len(bright_issues) > 0

    def test_validate_too_dark_fails(self, tmp_path):
        """Near-black image reports darkness issue."""
        path = _save_solid_color(str(tmp_path / "dark.png"), 10, 10, 10)

        result = validate_palette(path)

        dark_issues = [i for i in result["issues"] if i["rule"] == "value_too_dark"]
        assert len(dark_issues) > 0

    def test_validate_warm_bias_warns(self, tmp_path):
        """Warm-toned red/orange image triggers temperature warning."""
        # Create warm red-orange image
        arr = np.full((64, 64, 3), [180, 80, 40], dtype=np.uint8)
        path = _save_array_image(str(tmp_path / "warm.png"), arr)

        result = validate_palette(path)

        warm_issues = [i for i in result["issues"] if i["rule"] == "warm_temperature_bias"]
        assert len(warm_issues) > 0
        assert warm_issues[0]["severity"] == "warning"

    def test_validate_custom_rules(self, tmp_path):
        """Custom rules override allows previously-failing image to pass."""
        # Moderately saturated image that fails default 0.55 cap
        arr = np.full((64, 64, 3), [80, 140, 200], dtype=np.uint8)
        path = _save_array_image(str(tmp_path / "moderate_sat.png"), arr)

        # Check with default rules
        default_result = validate_palette(path)

        # Check with custom lenient rules
        custom_rules = {
            "saturation_cap": 0.95,
            "value_range": (0.0, 1.0),
            "cool_bias_target": 0.0,
        }
        custom_result = validate_palette(path, rules=custom_rules)

        # Custom rules should have fewer or no errors
        default_errors = len([i for i in default_result["issues"] if i["severity"] == "error"])
        custom_errors = len([i for i in custom_result["issues"] if i["severity"] == "error"])
        assert custom_errors <= default_errors

    def test_palette_rules_constants(self):
        """PALETTE_RULES has all expected keys with correct types."""
        assert "saturation_cap" in PALETTE_RULES
        assert "value_range" in PALETTE_RULES
        assert "warm_temp_threshold" in PALETTE_RULES
        assert "cool_bias_target" in PALETTE_RULES
        assert "roughness_min_variance" in PALETTE_RULES
        assert "metallic_max_mean" in PALETTE_RULES

        assert isinstance(PALETTE_RULES["saturation_cap"], float)
        assert isinstance(PALETTE_RULES["value_range"], tuple)
        assert len(PALETTE_RULES["value_range"]) == 2
        assert PALETTE_RULES["saturation_cap"] == 0.55

    def test_asset_type_budgets(self):
        """ASSET_TYPE_BUDGETS has correct per-type min/max values."""
        assert "hero" in ASSET_TYPE_BUDGETS
        assert "mob" in ASSET_TYPE_BUDGETS
        assert "weapon" in ASSET_TYPE_BUDGETS
        assert "prop" in ASSET_TYPE_BUDGETS
        assert "building" in ASSET_TYPE_BUDGETS

        assert ASSET_TYPE_BUDGETS["hero"]["min"] == 30000
        assert ASSET_TYPE_BUDGETS["hero"]["max"] == 50000
        assert ASSET_TYPE_BUDGETS["mob"]["min"] == 8000
        assert ASSET_TYPE_BUDGETS["mob"]["max"] == 15000
        assert ASSET_TYPE_BUDGETS["weapon"]["min"] == 3000
        assert ASSET_TYPE_BUDGETS["weapon"]["max"] == 8000
        assert ASSET_TYPE_BUDGETS["prop"]["min"] == 500
        assert ASSET_TYPE_BUDGETS["prop"]["max"] == 6000
        assert ASSET_TYPE_BUDGETS["building"]["min"] == 5000
        assert ASSET_TYPE_BUDGETS["building"]["max"] == 15000

    def test_validate_returns_stats(self, tmp_path):
        """Result includes comprehensive stats dict."""
        arr = np.full((32, 32, 3), [100, 100, 120], dtype=np.uint8)
        path = _save_array_image(str(tmp_path / "stats.png"), arr)

        result = validate_palette(path)

        stats = result["stats"]
        assert "mean_saturation" in stats
        assert "mean_value" in stats
        assert "cool_ratio" in stats
        assert "warm_ratio" in stats
        assert "value_below_min_pct" in stats
        assert "value_above_max_pct" in stats
        assert "total_sampled" in stats

    def test_validate_sample_count(self, tmp_path):
        """Small images use all pixels when under sample_pixels threshold."""
        arr = np.full((8, 8, 3), [80, 80, 100], dtype=np.uint8)
        path = _save_array_image(str(tmp_path / "small.png"), arr)

        result = validate_palette(path, sample_pixels=10000)
        assert result["stats"]["total_sampled"] == 64  # 8 * 8


# ---------------------------------------------------------------------------
# TestRoughnessMap
# ---------------------------------------------------------------------------


class TestRoughnessMap:
    """Tests for roughness map variation validation."""

    def test_roughness_varied_passes(self, tmp_path):
        """Image with sufficient pixel variance passes."""
        # Create image with noise (high variance, full 0-255 range)
        np.random.seed(42)
        arr = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        path = _save_grayscale(str(tmp_path / "varied.png"), arr)

        result = validate_roughness_map(path)

        assert result["passed"] is True
        assert result["variance"] > 0.05

    def test_roughness_flat_fails(self, tmp_path):
        """Solid gray image fails (flat roughness)."""
        arr = np.full((64, 64), 128, dtype=np.uint8)
        path = _save_grayscale(str(tmp_path / "flat.png"), arr)

        result = validate_roughness_map(path)

        assert result["passed"] is False
        assert result["severity"] == "error"
        assert result["variance"] < 0.05

    def test_roughness_custom_threshold(self, tmp_path):
        """Custom min_variance threshold adjusts pass criteria."""
        # Create moderately varied image (half black, half white = ~0.25 variance)
        arr = np.full((64, 64), 60, dtype=np.uint8)
        arr[0:32, :] = 200  # Moderate variation
        path = _save_grayscale(str(tmp_path / "moderate.png"), arr)

        # With very low threshold, should pass
        result = validate_roughness_map(path, min_variance=0.01)
        assert result["passed"] is True

        # With very high threshold, should fail
        result_strict = validate_roughness_map(path, min_variance=0.5)
        assert result_strict["passed"] is False

    def test_roughness_result_structure(self, tmp_path):
        """Result dict has all expected keys."""
        np.random.seed(99)
        arr = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
        path = _save_grayscale(str(tmp_path / "structure.png"), arr)

        result = validate_roughness_map(path)

        assert "passed" in result
        assert "variance" in result
        assert "min_variance" in result
        assert "severity" in result
