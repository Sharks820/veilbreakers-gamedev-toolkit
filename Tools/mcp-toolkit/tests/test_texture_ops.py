"""Unit tests for texture_ops.py -- Pillow-based texture editing operations.

Tests cover:
- UV mask generation with feathered (Gaussian) edges
- HSV color adjustment with mask-based alpha blending
- Seam blending across UV island boundaries
- Tileable texture generation
- Wear map rendering from curvature data
- Inpainting stub behavior
"""

import io
import math

import numpy as np
from PIL import Image as PILImage

from veilbreakers_mcp.shared.texture_ops import (
    apply_hsv_adjustment,
    blend_seams,
    generate_uv_mask,
    generate_uv_mask_image,
    inpaint_texture,
    make_tileable,
    render_wear_map,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _img_from_bytes(data: bytes) -> PILImage.Image:
    """Load a PIL image from PNG bytes."""
    return PILImage.open(io.BytesIO(data))


def _to_png_bytes(img: PILImage.Image) -> bytes:
    """Convert a PIL image to PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# generate_uv_mask tests
# ---------------------------------------------------------------------------

class TestGenerateUVMask:
    """Tests for UV mask generation with feathered edges."""

    def test_single_square_polygon_interior(self):
        """A single square polygon produces 255 inside and 0 outside."""
        # Polygon in UV space: a square from (0.25, 0.25) to (0.75, 0.75)
        polygons = [[(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]]
        mask_bytes = generate_uv_mask(polygons, texture_size=64, feather_radius=0)
        mask = _img_from_bytes(mask_bytes)

        assert mask.mode == "L"
        assert mask.size == (64, 64)

        # Center pixel should be white (inside polygon)
        center = mask.getpixel((32, 32))
        assert center == 255

        # Corner pixel should be black (outside polygon)
        corner = mask.getpixel((0, 0))
        assert corner == 0

    def test_feathered_edges_have_gradient(self):
        """Feathered mask edges produce gradient pixels, not hard 0/255."""
        polygons = [[(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]]
        mask_bytes = generate_uv_mask(polygons, texture_size=128, feather_radius=5)
        mask = _img_from_bytes(mask_bytes)
        arr = np.array(mask)

        # There should be pixels with values strictly between 0 and 255
        gradient_pixels = arr[(arr > 0) & (arr < 255)]
        assert len(gradient_pixels) > 0, "Feathered mask should have gradient pixels"

    def test_feathered_edge_values_within_radius(self):
        """Edge pixels within feather_radius have values between 1 and 254."""
        polygons = [[(0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7)]]
        mask_bytes = generate_uv_mask(polygons, texture_size=128, feather_radius=8)
        mask = _img_from_bytes(mask_bytes)
        arr = np.array(mask)

        # Check that gradient region exists near edges
        # The polygon edge in pixel space is around x=38 (0.3*128)
        # Check a strip near the edge for gradient values
        edge_col = int(0.3 * 128)  # ~38
        edge_strip = arr[:, max(0, edge_col - 10):edge_col + 10]
        gradient_in_strip = edge_strip[(edge_strip > 0) & (edge_strip < 255)]
        assert len(gradient_in_strip) > 0, "Edge strip should contain gradient values"

    def test_generate_uv_mask_image_returns_pil(self):
        """generate_uv_mask_image returns a PIL Image for chaining."""
        polygons = [[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]]
        mask_img = generate_uv_mask_image(polygons, texture_size=64, feather_radius=3)
        assert isinstance(mask_img, PILImage.Image)
        assert mask_img.mode == "L"
        assert mask_img.size == (64, 64)


# ---------------------------------------------------------------------------
# apply_hsv_adjustment tests
# ---------------------------------------------------------------------------

class TestApplyHSVAdjustment:
    """Tests for HSV color adjustment with mask-based blending."""

    def test_full_mask_shifts_hue(self):
        """Full mask (all 255) shifts hue of entire image."""
        # Create a solid red image
        img = PILImage.new("RGB", (64, 64), (255, 0, 0))
        img_bytes = _to_png_bytes(img)

        # Full white mask
        mask = PILImage.new("L", (64, 64), 255)
        mask_bytes = _to_png_bytes(mask)

        result_bytes = apply_hsv_adjustment(img_bytes, mask_bytes, hue_shift=0.33)
        result = _img_from_bytes(result_bytes)

        # Hue shifted by 0.33 from red (0.0) should be roughly green-ish
        center_pixel = result.getpixel((32, 32))
        # Red channel should decrease, green should increase
        assert center_pixel[0] < 100, f"Red should decrease, got {center_pixel[0]}"
        assert center_pixel[1] > 100, f"Green should increase, got {center_pixel[1]}"

    def test_half_mask_preserves_unmasked(self):
        """Half mask modifies only masked pixels; unmasked are bit-identical."""
        img = PILImage.new("RGB", (64, 64), (200, 100, 50))
        img_bytes = _to_png_bytes(img)

        # Left half white, right half black
        mask = PILImage.new("L", (64, 64), 0)
        for y in range(64):
            for x in range(32):
                mask.putpixel((x, y), 255)
        mask_bytes = _to_png_bytes(mask)

        result_bytes = apply_hsv_adjustment(img_bytes, mask_bytes, hue_shift=0.5)
        result = _img_from_bytes(result_bytes)
        original = _img_from_bytes(img_bytes)

        # Right half (unmasked) should be identical to original
        for y in range(0, 64, 8):
            for x in range(33, 64, 8):
                assert result.getpixel((x, y)) == original.getpixel((x, y)), \
                    f"Unmasked pixel ({x},{y}) should be identical to original"

        # Left half (masked) should be different
        left_pixel = result.getpixel((16, 32))
        orig_pixel = original.getpixel((16, 32))
        assert left_pixel != orig_pixel, "Masked pixel should be modified"

    def test_hue_shift_red_to_cyan(self):
        """hue_shift=0.5 rotates red to cyan."""
        img = PILImage.new("RGB", (64, 64), (255, 0, 0))
        img_bytes = _to_png_bytes(img)

        mask = PILImage.new("L", (64, 64), 255)
        mask_bytes = _to_png_bytes(mask)

        result_bytes = apply_hsv_adjustment(img_bytes, mask_bytes, hue_shift=0.5)
        result = _img_from_bytes(result_bytes)

        pixel = result.getpixel((32, 32))
        # Red (h=0.0) + 0.5 = cyan (h=0.5) = (0, 255, 255)
        assert pixel[0] < 10, f"Expected near-zero red, got {pixel[0]}"
        assert pixel[1] > 240, f"Expected near-max green, got {pixel[1]}"
        assert pixel[2] > 240, f"Expected near-max blue, got {pixel[2]}"

    def test_partial_mask_blends_smoothly(self):
        """Partially masked pixels (alpha < 255) blend between original and adjusted."""
        img = PILImage.new("RGB", (64, 64), (255, 0, 0))
        img_bytes = _to_png_bytes(img)

        # Gradient mask: left edge = 0, right edge = 255
        mask = PILImage.new("L", (64, 64), 0)
        for y in range(64):
            for x in range(64):
                mask.putpixel((x, y), int(x * 255 / 63))
        mask_bytes = _to_png_bytes(mask)

        result_bytes = apply_hsv_adjustment(img_bytes, mask_bytes, hue_shift=0.5)
        result = _img_from_bytes(result_bytes)

        # Left edge (mask ~0) should be close to original red
        left = result.getpixel((0, 32))
        assert left[0] > 200, f"Left edge should stay red, got R={left[0]}"

        # Right edge (mask ~255) should be close to cyan
        right = result.getpixel((63, 32))
        assert right[0] < 30, f"Right edge should be cyan, got R={right[0]}"

        # Middle (mask ~128) should be a blend
        mid = result.getpixel((32, 32))
        assert 30 < mid[0] < 220, f"Middle should be blended, got R={mid[0]}"


# ---------------------------------------------------------------------------
# blend_seams tests
# ---------------------------------------------------------------------------

class TestBlendSeams:
    """Tests for seam blending across UV island boundaries."""

    def test_hard_boundary_becomes_smooth(self):
        """A hard color boundary at midline becomes smooth after blending."""
        # Create image: left half red, right half blue
        img = PILImage.new("RGB", (128, 128), (0, 0, 0))
        for y in range(128):
            for x in range(64):
                img.putpixel((x, y), (255, 0, 0))
            for x in range(64, 128):
                img.putpixel((x, y), (0, 0, 255))
        img_bytes = _to_png_bytes(img)

        # Seam pixels along the midline
        seam_pixels = [(64, y) for y in range(128)]

        result_bytes = blend_seams(img_bytes, seam_pixels, blend_radius=8)
        result = _img_from_bytes(result_bytes)

        # At seam (x=64), pixel should now be a blend of red and blue
        seam_pixel = result.getpixel((64, 64))
        # It should have both red and blue components (not pure red or pure blue)
        assert seam_pixel[0] > 20, f"Seam should have some red, got {seam_pixel[0]}"
        assert seam_pixel[2] > 20, f"Seam should have some blue, got {seam_pixel[2]}"

    def test_monotonic_transition(self):
        """Pixel values monotonically transition across the seam region."""
        # Left half white, right half black
        img = PILImage.new("RGB", (128, 64), (0, 0, 0))
        for y in range(64):
            for x in range(64):
                img.putpixel((x, y), (255, 255, 255))
        img_bytes = _to_png_bytes(img)

        seam_pixels = [(64, y) for y in range(64)]
        result_bytes = blend_seams(img_bytes, seam_pixels, blend_radius=10)
        result = _img_from_bytes(result_bytes)

        # Sample the red channel along row 32 from x=54 to x=74
        # Values should generally decrease (white -> black) without spikes
        values = [result.getpixel((x, 32))[0] for x in range(54, 75)]
        # Check that no value increases by more than a small amount
        # (allows small non-monotonicity from discrete pixel blending)
        for i in range(1, len(values)):
            increase = values[i] - values[i - 1]
            assert increase < 30, (
                f"Non-monotonic spike at x={54+i}: "
                f"values[{i-1}]={values[i-1]}, values[{i}]={values[i]}"
            )


# ---------------------------------------------------------------------------
# make_tileable tests
# ---------------------------------------------------------------------------

class TestMakeTileable:
    """Tests for tileable texture generation."""

    def test_edges_match(self):
        """Left column matches right column and top row matches bottom row."""
        # Create a random-ish test image with color variation
        np.random.seed(42)
        arr = np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)
        img = PILImage.fromarray(arr, "RGB")
        img_bytes = _to_png_bytes(img)

        result_bytes = make_tileable(img_bytes, overlap_pct=0.15)
        result = _img_from_bytes(result_bytes)
        result_arr = np.array(result)

        # Left column vs right column
        left_col = result_arr[:, 0, :].astype(int)
        right_col = result_arr[:, -1, :].astype(int)
        lr_diff = np.abs(left_col - right_col)
        assert lr_diff.max() <= 15, (
            f"Left-right edge diff too large: max={lr_diff.max()}"
        )

        # Top row vs bottom row
        top_row = result_arr[0, :, :].astype(int)
        bottom_row = result_arr[-1, :, :].astype(int)
        tb_diff = np.abs(top_row - bottom_row)
        assert tb_diff.max() <= 15, (
            f"Top-bottom edge diff too large: max={tb_diff.max()}"
        )

    def test_2x2_tiling_no_seam(self):
        """Tiling 2x2 shows no visible seam at edges (pixel diff < threshold)."""
        np.random.seed(99)
        arr = np.random.randint(50, 200, (64, 64, 3), dtype=np.uint8)
        img = PILImage.fromarray(arr, "RGB")
        img_bytes = _to_png_bytes(img)

        result_bytes = make_tileable(img_bytes, overlap_pct=0.15)
        result = _img_from_bytes(result_bytes)
        w, h = result.size

        # Create a 2x2 tiled image
        tiled = PILImage.new("RGB", (w * 2, h * 2))
        tiled.paste(result, (0, 0))
        tiled.paste(result, (w, 0))
        tiled.paste(result, (0, h))
        tiled.paste(result, (w, h))

        tiled_arr = np.array(tiled)

        # Check vertical seam at x=w (between left and right tiles)
        left_of_seam = tiled_arr[:, w - 1, :].astype(int)
        right_of_seam = tiled_arr[:, w, :].astype(int)
        v_diff = np.abs(left_of_seam - right_of_seam)
        assert v_diff.mean() < 10, (
            f"Vertical seam mean diff too large: {v_diff.mean():.1f}"
        )

        # Check horizontal seam at y=h
        above_seam = tiled_arr[h - 1, :, :].astype(int)
        below_seam = tiled_arr[h, :, :].astype(int)
        h_diff = np.abs(above_seam - below_seam)
        assert h_diff.mean() < 10, (
            f"Horizontal seam mean diff too large: {h_diff.mean():.1f}"
        )


# ---------------------------------------------------------------------------
# render_wear_map tests
# ---------------------------------------------------------------------------

class TestRenderWearMap:
    """Tests for wear/damage map rendering from curvature data."""

    def test_curvature_to_brightness(self):
        """High curvature vertices produce bright pixels, zero curvature dark."""
        # Simple curvature data for 4 vertices
        curvature_data = {0: 1.0, 1: 0.5, 2: 0.0, 3: -1.0}

        # UV data: single quad covering most of the texture
        # Each face is a list of (vertex_index, u, v)
        uv_data = [
            [(0, 0.1, 0.1), (1, 0.9, 0.1), (2, 0.9, 0.9), (3, 0.1, 0.9)],
        ]

        result_bytes = render_wear_map(curvature_data, texture_size=64, uv_data=uv_data)
        result = _img_from_bytes(result_bytes)

        assert result.mode == "L"
        assert result.size == (64, 64)

        # Vertex 0 (curvature=1.0) at UV (0.1, 0.1) -> pixel near (6, 57)
        # In UV: x = int(0.1*64) = 6, y = int((1-0.1)*64) = 57
        bright_pixel = result.getpixel((6, 57))
        # Vertex 3 (curvature=-1.0) at UV (0.1, 0.9) -> pixel near (6, 6)
        dark_pixel = result.getpixel((6, 6))

        assert bright_pixel > dark_pixel, (
            f"High curvature should be brighter: bright={bright_pixel}, dark={dark_pixel}"
        )

    def test_wear_map_without_uv(self):
        """Wear map without UV data still returns a valid image."""
        curvature_data = {0: 0.5, 1: -0.5, 2: 1.0}
        result_bytes = render_wear_map(curvature_data, texture_size=64, uv_data=None)
        result = _img_from_bytes(result_bytes)
        assert result.mode == "L"
        assert result.size == (64, 64)


# ---------------------------------------------------------------------------
# inpaint_texture tests
# ---------------------------------------------------------------------------

class TestInpaintTexture:
    """Tests for AI inpainting stub."""

    def test_stub_without_api_key(self):
        """Returns stub status when no AI backend configured."""
        img = PILImage.new("RGB", (64, 64), (128, 128, 128))
        mask = PILImage.new("L", (64, 64), 255)

        result = inpaint_texture(
            _to_png_bytes(img),
            _to_png_bytes(mask),
            prompt="rusty metal texture",
            fal_key=None,
        )

        assert isinstance(result, dict)
        assert result["status"] == "stub"
        assert "not configured" in result["message"].lower() or "fal" in result["message"].lower()

    def test_stub_with_empty_key(self):
        """Returns stub status when key is empty string."""
        img = PILImage.new("RGB", (64, 64), (128, 128, 128))
        mask = PILImage.new("L", (64, 64), 255)

        result = inpaint_texture(
            _to_png_bytes(img),
            _to_png_bytes(mask),
            prompt="worn leather",
            fal_key="",
        )

        assert result["status"] == "stub"
