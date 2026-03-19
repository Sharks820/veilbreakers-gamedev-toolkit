"""Unit tests for fal_client.py -- concept art generation and image analysis.

Tests cover:
- generate_concept_art without FAL_KEY returns unavailable status
- extract_color_palette on solid red image returns red as dominant
- extract_color_palette with num_colors=5 returns 5 entries
- Each palette color has rgb list and hex string
- extract_color_palette returns valid swatch_bytes PNG
- compose_style_board produces image wider than inputs
- silhouette test on centered dark shape returns readable=True
- silhouette test on solid gray returns readable=False
"""

import io

from PIL import Image as PILImage

from veilbreakers_mcp.shared.fal_client import (
    compose_style_board,
    extract_color_palette,
    generate_concept_art,
    test_silhouette_readability as silhouette_readability_fn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_png_bytes(img: PILImage.Image) -> bytes:
    """Convert a PIL image to PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _img_from_bytes(data: bytes) -> PILImage.Image:
    """Load a PIL image from PNG bytes."""
    return PILImage.open(io.BytesIO(data))


# ---------------------------------------------------------------------------
# generate_concept_art tests
# ---------------------------------------------------------------------------


class TestGenerateConceptArt:
    """Tests for AI concept art generation."""

    def test_without_fal_key_returns_unavailable(self):
        """generate_concept_art without FAL_KEY returns unavailable status."""
        result = generate_concept_art(
            prompt="a dark castle",
            fal_key=None,
        )
        assert result["status"] == "unavailable"
        assert "FAL_KEY" in result["message"] or "fal" in result["message"].lower()

    def test_with_empty_fal_key_returns_unavailable(self):
        """generate_concept_art with empty FAL_KEY returns unavailable status."""
        result = generate_concept_art(
            prompt="a dark castle",
            fal_key="",
        )
        assert result["status"] == "unavailable"


# ---------------------------------------------------------------------------
# extract_color_palette tests
# ---------------------------------------------------------------------------


class TestExtractColorPalette:
    """Tests for color palette extraction."""

    def test_solid_red_returns_red_dominant(self):
        """extract_color_palette on solid red image returns red as dominant."""
        img = PILImage.new("RGB", (64, 64), (255, 0, 0))
        img_bytes = _to_png_bytes(img)

        result = extract_color_palette(img_bytes, num_colors=4)

        assert "colors" in result
        assert len(result["colors"]) >= 1

        # Dominant color should be red
        dominant = result["colors"][0]
        assert dominant["rgb"][0] > 200, f"Expected red dominant, got {dominant['rgb']}"
        assert dominant["rgb"][1] < 50
        assert dominant["rgb"][2] < 50

    def test_num_colors_5_returns_5_entries(self):
        """extract_color_palette with num_colors=5 returns 5 entries."""
        # Create an image with multiple distinct colors
        img = PILImage.new("RGB", (100, 100), (0, 0, 0))
        for y in range(20):
            for x in range(100):
                img.putpixel((x, y), (255, 0, 0))
        for y in range(20, 40):
            for x in range(100):
                img.putpixel((x, y), (0, 255, 0))
        for y in range(40, 60):
            for x in range(100):
                img.putpixel((x, y), (0, 0, 255))
        for y in range(60, 80):
            for x in range(100):
                img.putpixel((x, y), (255, 255, 0))
        for y in range(80, 100):
            for x in range(100):
                img.putpixel((x, y), (255, 0, 255))
        img_bytes = _to_png_bytes(img)

        result = extract_color_palette(img_bytes, num_colors=5)

        assert len(result["colors"]) == 5

    def test_each_color_has_rgb_and_hex(self):
        """Each palette color has rgb list and hex string."""
        img = PILImage.new("RGB", (64, 64), (128, 64, 32))
        img_bytes = _to_png_bytes(img)

        result = extract_color_palette(img_bytes, num_colors=3)

        for color in result["colors"]:
            assert "rgb" in color, "Color entry must have 'rgb' key"
            assert isinstance(color["rgb"], list), "rgb must be a list"
            assert len(color["rgb"]) == 3, "rgb must have 3 elements"

            assert "hex" in color, "Color entry must have 'hex' key"
            assert isinstance(color["hex"], str), "hex must be a string"
            assert color["hex"].startswith("#"), "hex must start with #"
            assert len(color["hex"]) == 7, "hex must be 7 chars (#rrggbb)"

    def test_swatch_bytes_is_valid_png(self):
        """extract_color_palette returns valid swatch_bytes PNG."""
        img = PILImage.new("RGB", (64, 64), (0, 128, 255))
        img_bytes = _to_png_bytes(img)

        result = extract_color_palette(img_bytes, num_colors=4)

        assert "swatch_bytes" in result
        swatch_bytes = result["swatch_bytes"]
        assert len(swatch_bytes) > 0, "swatch_bytes should not be empty"

        # Verify it's a valid PNG by loading it
        swatch = _img_from_bytes(swatch_bytes)
        assert swatch.mode == "RGB"
        assert swatch.size[0] > 0
        assert swatch.size[1] > 0


# ---------------------------------------------------------------------------
# compose_style_board tests
# ---------------------------------------------------------------------------


class TestComposeStyleBoard:
    """Tests for style board composition."""

    def test_board_wider_than_inputs(self):
        """compose_style_board produces image wider than any single input."""
        # Create small input images
        img1 = PILImage.new("RGB", (200, 200), (255, 0, 0))
        img2 = PILImage.new("RGB", (200, 200), (0, 255, 0))

        board_bytes = compose_style_board(
            images=[_to_png_bytes(img1), _to_png_bytes(img2)],
            palette_colors=[{"rgb": [255, 0, 0]}, {"rgb": [0, 255, 0]}],
            title="Test Board",
            board_width=2048,
        )

        board = _img_from_bytes(board_bytes)
        assert board.width > 200, (
            f"Board width ({board.width}) should be wider than input images (200)"
        )
        assert board.width == 2048


# ---------------------------------------------------------------------------
# test_silhouette_readability tests
# ---------------------------------------------------------------------------


class TestSilhouetteReadability:
    """Tests for silhouette readability analysis."""

    def test_centered_dark_shape_is_readable(self):
        """Silhouette test on centered dark shape returns readable=True."""
        # White background with a large centered black circle
        img = PILImage.new("L", (256, 256), 255)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        # Draw a large dark ellipse in the center
        draw.ellipse([48, 48, 208, 208], fill=0)

        img_bytes = _to_png_bytes(img)

        result = silhouette_readability_fn(
            img_bytes,
            threshold=128,
            min_contrast_ratio=0.3,
            distances=[1.0, 0.5, 0.25],
        )

        assert result["readable"] is True
        assert result["silhouette_coverage"] > 0.1
        assert len(result["distances"]) == 3

    def test_solid_gray_is_not_readable(self):
        """Silhouette test on solid gray returns readable=False."""
        # Solid mid-gray: no foreground/background distinction at threshold=128
        # Use value 130 so all pixels are ABOVE threshold -> no foreground at all
        img = PILImage.new("L", (256, 256), 130)
        img_bytes = _to_png_bytes(img)

        result = silhouette_readability_fn(
            img_bytes,
            threshold=128,
            min_contrast_ratio=0.3,
            distances=[1.0, 0.5, 0.25],
        )

        assert result["readable"] is False
