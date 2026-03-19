"""Tests for screenshot comparison and visual regression detection.

Uses Pillow to create test images programmatically, then validates:
- Identical images return 0% diff and match=True
- Completely different images return high diff and match=False
- Threshold parameter controls match sensitivity
- Diff image generation creates output file
"""

import os
import tempfile

import pytest
from PIL import Image

from veilbreakers_mcp.shared.screenshot_diff import (
    compare_screenshots,
    generate_diff_image,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test images."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _save_solid_image(path: str, color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> str:
    """Create and save a solid-color image."""
    img = Image.new("RGB", size, color)
    img.save(path)
    img.close()
    return path


# ---------------------------------------------------------------------------
# Identical images
# ---------------------------------------------------------------------------


class TestIdenticalImages:
    """Tests that identical images return 0% diff."""

    def test_identical_images_match(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (128, 64, 32))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (128, 64, 32))
        result = compare_screenshots(ref, cur)
        assert result["match"] is True
        assert result["diff_percentage"] == 0.0

    def test_identical_images_no_diff_image(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (0, 0, 0))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (0, 0, 0))
        result = compare_screenshots(ref, cur)
        assert result["diff_image_path"] is None


# ---------------------------------------------------------------------------
# Different images
# ---------------------------------------------------------------------------


class TestDifferentImages:
    """Tests that different images are detected."""

    def test_solid_red_vs_blue_high_diff(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (255, 0, 0))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (0, 0, 255))
        result = compare_screenshots(ref, cur)
        assert result["match"] is False
        # All pixels should be different
        assert result["diff_percentage"] > 0.99

    def test_white_vs_black_high_diff(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (255, 255, 255))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (0, 0, 0))
        result = compare_screenshots(ref, cur)
        assert result["match"] is False
        assert result["diff_percentage"] == 1.0

    def test_small_change_detected(self, temp_dir):
        """A single pixel change should be detected."""
        ref_path = os.path.join(temp_dir, "ref.png")
        cur_path = os.path.join(temp_dir, "cur.png")

        img = Image.new("RGB", (100, 100), (128, 128, 128))
        img.save(ref_path)

        # Change one pixel significantly
        img.putpixel((50, 50), (255, 0, 0))
        img.save(cur_path)
        img.close()

        result = compare_screenshots(ref_path, cur_path)
        # 1 pixel out of 10000 = 0.0001 = 0.01%
        assert result["diff_percentage"] > 0.0
        assert result["diff_percentage"] < 0.01  # Less than 1%


# ---------------------------------------------------------------------------
# Threshold behavior
# ---------------------------------------------------------------------------


class TestThresholdBehavior:
    """Tests that the threshold parameter works correctly."""

    def test_high_threshold_matches_small_diff(self, temp_dir):
        ref_path = os.path.join(temp_dir, "ref.png")
        cur_path = os.path.join(temp_dir, "cur.png")

        img = Image.new("RGB", (10, 10), (100, 100, 100))
        img.save(ref_path)
        # Change 1 pixel out of 100 = 1% diff
        img.putpixel((5, 5), (255, 0, 0))
        img.save(cur_path)
        img.close()

        # With 5% threshold, 1% diff should match
        result = compare_screenshots(ref_path, cur_path, threshold=0.05)
        assert result["match"] is True

    def test_zero_threshold_strict(self, temp_dir):
        ref_path = os.path.join(temp_dir, "ref.png")
        cur_path = os.path.join(temp_dir, "cur.png")

        img = Image.new("RGB", (10, 10), (100, 100, 100))
        img.save(ref_path)
        img.putpixel((5, 5), (255, 0, 0))
        img.save(cur_path)
        img.close()

        # With 0% threshold, any diff should fail
        result = compare_screenshots(ref_path, cur_path, threshold=0.0)
        assert result["match"] is False


# ---------------------------------------------------------------------------
# Diff image generation
# ---------------------------------------------------------------------------


class TestDiffImageGeneration:
    """Tests for generate_diff_image()."""

    def test_creates_output_file(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (255, 0, 0))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (0, 0, 255))
        output = os.path.join(temp_dir, "diff.png")

        result_path = generate_diff_image(ref, cur, output)
        assert result_path == output
        assert os.path.exists(output)

    def test_diff_image_is_valid(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (255, 0, 0))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (0, 255, 0))
        output = os.path.join(temp_dir, "diff.png")

        generate_diff_image(ref, cur, output)
        # Should be openable as an image
        img = Image.open(output)
        assert img.size == (100, 100)
        img.close()

    def test_diff_image_contains_red_for_changes(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (0, 0, 0))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (255, 255, 255))
        output = os.path.join(temp_dir, "diff.png")

        generate_diff_image(ref, cur, output)
        img = Image.open(output)
        # The diff overlay should contain red pixels
        img_bytes = img.convert("RGB").tobytes()
        red_channel_values = [img_bytes[i] for i in range(0, len(img_bytes), 3)]
        assert max(red_channel_values) > 100  # Red overlay present
        img.close()

    def test_compare_screenshots_generates_diff_on_mismatch(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (255, 0, 0))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (0, 0, 255))

        result = compare_screenshots(ref, cur)
        assert result["diff_image_path"] is not None
        assert os.path.exists(result["diff_image_path"])


# ---------------------------------------------------------------------------
# Size handling
# ---------------------------------------------------------------------------


class TestSizeHandling:
    """Tests for images with different sizes."""

    def test_different_sizes_resized(self, temp_dir):
        ref = _save_solid_image(os.path.join(temp_dir, "ref.png"), (128, 128, 128), size=(200, 200))
        cur = _save_solid_image(os.path.join(temp_dir, "cur.png"), (128, 128, 128), size=(100, 100))
        result = compare_screenshots(ref, cur)
        # Should succeed (current is resized to match reference)
        assert "match" in result
        assert result["reference_size"] == (200, 200)
        assert result["current_size"] == (100, 100)
