"""Unit tests for delight.py -- Albedo de-lighting algorithm (AAA-01).

Tests cover:
- Basic de-lighting operation and output format
- Luminance variance reduction
- Strength parameter effects (0.0, 0.75, 1.0)
- Custom blur radius
- Edge cases (small images, uniform images)
- Hue preservation during de-lighting
"""

import os

import numpy as np
import pytest
from PIL import Image

from veilbreakers_mcp.shared.delight import delight_albedo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_gradient_image(path: str, size: int = 64) -> str:
    """Create a test image with a diagonal gradient (simulates baked lighting)."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    for y in range(size):
        for x in range(size):
            brightness = int(((x + y) / (2 * size)) * 200 + 28)
            arr[y, x] = [brightness, brightness, brightness]
    img = Image.fromarray(arr, "RGB")
    img.save(path)
    return path


def _create_hotspot_image(path: str, size: int = 64) -> str:
    """Create image with bright center spot and dark corners."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    cx, cy = size // 2, size // 2
    for y in range(size):
        for x in range(size):
            dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            max_dist = np.sqrt(cx ** 2 + cy ** 2)
            brightness = int(255 * max(0, 1 - dist / max_dist))
            arr[y, x] = [brightness, brightness, brightness]
    img = Image.fromarray(arr, "RGB")
    img.save(path)
    return path


def _create_colored_image(path: str, r: int, g: int, b: int, size: int = 64) -> str:
    """Create a solid color test image."""
    img = Image.new("RGB", (size, size), (r, g, b))
    img.save(path)
    return path


def _luminance_variance(img_path: str) -> float:
    """Calculate luminance variance of an image."""
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    return float(np.var(lum))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDelightAlbedo:
    """Tests for the albedo de-lighting algorithm."""

    def test_delight_basic(self, tmp_path):
        """De-lighting produces output file and returns expected metadata keys."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_gradient_image(input_path)

        result = delight_albedo(input_path, output_path)

        assert os.path.exists(output_path)
        assert isinstance(result, dict)
        assert "input" in result
        assert "output" in result
        assert "blur_radius" in result
        assert "strength" in result
        assert "mean_luminance_before" in result
        assert "mean_luminance_after" in result
        assert "correction_applied" in result
        assert result["correction_applied"] is True

    def test_delight_reduces_luminance_variance(self, tmp_path):
        """De-lighting reduces luminance variance (flattens lighting)."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_hotspot_image(input_path, size=64)

        var_before = _luminance_variance(input_path)
        delight_albedo(input_path, output_path, strength=1.0)
        var_after = _luminance_variance(output_path)

        assert var_after < var_before, (
            f"Luminance variance should decrease: before={var_before:.6f}, after={var_after:.6f}"
        )

    def test_delight_strength_zero(self, tmp_path):
        """Strength=0.0 should produce output identical to input."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_gradient_image(input_path)

        result = delight_albedo(input_path, output_path, strength=0.0)

        # With strength=0.0, output should be very close to input
        input_img = np.array(Image.open(input_path))
        output_img = np.array(Image.open(output_path))
        # Allow small rounding differences from float conversion
        max_diff = np.max(np.abs(input_img.astype(int) - output_img.astype(int)))
        assert max_diff <= 1, f"Strength=0 should preserve input, max diff={max_diff}"

    def test_delight_strength_full(self, tmp_path):
        """Strength=1.0 applies maximum correction."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_hotspot_image(input_path, size=64)

        result = delight_albedo(input_path, output_path, strength=1.0)

        assert result["correction_applied"] is True
        assert result["strength"] == 1.0
        # Full strength should significantly reduce variance
        var_before = _luminance_variance(input_path)
        var_after = _luminance_variance(output_path)
        assert var_after < var_before * 0.8, "Full strength should significantly reduce variance"

    def test_delight_custom_blur_radius(self, tmp_path):
        """Custom blur_radius_pct is reflected in result metadata."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_gradient_image(input_path, size=100)

        result = delight_albedo(input_path, output_path, blur_radius_pct=0.25)

        # blur_radius should be 25% of max dimension (100) = 25
        assert result["blur_radius"] == 25

    def test_delight_output_format(self, tmp_path):
        """Output image has same dimensions as input."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_gradient_image(input_path, size=48)

        delight_albedo(input_path, output_path)

        input_img = Image.open(input_path)
        output_img = Image.open(output_path)
        assert input_img.size == output_img.size

    def test_delight_small_image(self, tmp_path):
        """Very small images (8x8) don't crash."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_gradient_image(input_path, size=8)

        result = delight_albedo(input_path, output_path)

        assert os.path.exists(output_path)
        assert result["blur_radius"] >= 1  # Minimum blur radius

    def test_delight_preserves_hue(self, tmp_path):
        """De-lighting preserves color hue (removes luminance, not chrominance)."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")

        # Create colored image with luminance variation
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        for y in range(64):
            for x in range(64):
                brightness = 0.3 + 0.5 * (x / 64.0)  # Varying luminance
                # Blue-ish color
                arr[y, x] = [
                    int(60 * brightness),
                    int(80 * brightness),
                    int(200 * brightness),
                ]
        img = Image.fromarray(arr, "RGB")
        img.save(input_path)

        delight_albedo(input_path, output_path, strength=0.75)

        # Check that average hue is similar
        import colorsys

        def mean_hue(path):
            im = Image.open(path).convert("RGB")
            a = np.array(im, dtype=np.float32) / 255.0
            # Sample center pixels
            center = a[20:44, 20:44].reshape(-1, 3)
            hues = []
            for px in center:
                h, s, v = colorsys.rgb_to_hsv(float(px[0]), float(px[1]), float(px[2]))
                if s > 0.05:  # Only chromatic pixels
                    hues.append(h)
            return np.mean(hues) if hues else 0.0

        hue_before = mean_hue(input_path)
        hue_after = mean_hue(output_path)

        # Hue should be similar (within ~10% of 1.0 hue range)
        hue_diff = abs(hue_after - hue_before)
        assert hue_diff < 0.1, f"Hue should be preserved: before={hue_before:.3f}, after={hue_after:.3f}"

    def test_delight_all_black_skips(self, tmp_path):
        """All-black image skips correction."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_colored_image(input_path, 0, 0, 0)

        result = delight_albedo(input_path, output_path)
        assert result["correction_applied"] is False

    def test_delight_all_white_skips(self, tmp_path):
        """All-white image skips correction."""
        input_path = str(tmp_path / "input.png")
        output_path = str(tmp_path / "output.png")
        _create_colored_image(input_path, 255, 255, 255)

        result = delight_albedo(input_path, output_path)
        assert result["correction_applied"] is False
