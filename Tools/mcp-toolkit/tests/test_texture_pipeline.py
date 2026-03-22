"""Unit tests for texture pipeline handlers.

Tests cover the five new texture pipeline capabilities:
  - handle_bake_procedural_to_images: procedural-to-image baking
  - handle_bake_id_map: material ID map baking
  - handle_bake_thickness_map: SSS thickness map baking
  - handle_channel_pack: R/G/B channel packing
  - handle_ensure_flat_albedo: albedo de-lighting verification

Pure-logic tests run without Blender. Tests that require bpy are
tested via signature validation and configuration checks.
"""

import io
import os
import tempfile

import numpy as np
import pytest
from PIL import Image as PILImage


# ---------------------------------------------------------------------------
# Helper: create test images
# ---------------------------------------------------------------------------

def _make_gray_png(size: int, value: int) -> str:
    """Create a solid grayscale PNG in a temp file, return path."""
    img = PILImage.new("L", (size, size), value)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path, format="PNG")
    return path


def _make_rgb_png(size: int, color: tuple) -> str:
    """Create a solid RGB PNG in a temp file, return path."""
    img = PILImage.new("RGB", (size, size), color)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path, format="PNG")
    return path


# ---------------------------------------------------------------------------
# Test: _PROCEDURAL_BAKE_CHANNELS configuration
# ---------------------------------------------------------------------------

class TestProceduralBakeChannels:
    """Test that the bake channel configuration is correct."""

    def test_has_five_channels(self):
        """_PROCEDURAL_BAKE_CHANNELS has all 5 PBR channels."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        assert len(_PROCEDURAL_BAKE_CHANNELS) == 5
        expected = {"albedo", "normal", "roughness", "metallic", "ao"}
        assert set(_PROCEDURAL_BAKE_CHANNELS.keys()) == expected

    def test_albedo_uses_diffuse_bake(self):
        """Albedo channel uses DIFFUSE bake type with COLOR pass filter."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        bake_type, pass_filter, colorspace = _PROCEDURAL_BAKE_CHANNELS["albedo"]
        assert bake_type == "DIFFUSE"
        assert pass_filter == {"COLOR"}
        assert colorspace == "sRGB"

    def test_normal_uses_normal_bake(self):
        """Normal channel uses NORMAL bake type."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        bake_type, pass_filter, colorspace = _PROCEDURAL_BAKE_CHANNELS["normal"]
        assert bake_type == "NORMAL"
        assert pass_filter is None
        assert colorspace == "Non-Color"

    def test_roughness_uses_roughness_bake(self):
        """Roughness channel uses ROUGHNESS bake type."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        bake_type, pass_filter, colorspace = _PROCEDURAL_BAKE_CHANNELS["roughness"]
        assert bake_type == "ROUGHNESS"
        assert colorspace == "Non-Color"

    def test_metallic_uses_emit_trick(self):
        """Metallic channel uses EMIT bake type (emission trick)."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        bake_type, pass_filter, colorspace = _PROCEDURAL_BAKE_CHANNELS["metallic"]
        assert bake_type == "EMIT"
        assert colorspace == "Non-Color"

    def test_ao_uses_ao_bake(self):
        """AO channel uses AO bake type."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        bake_type, pass_filter, colorspace = _PROCEDURAL_BAKE_CHANNELS["ao"]
        assert bake_type == "AO"
        assert colorspace == "Non-Color"

    def test_all_non_albedo_are_non_color(self):
        """All channels except albedo use Non-Color colorspace."""
        from blender_addon.handlers.texture import _PROCEDURAL_BAKE_CHANNELS

        for name, (_, _, colorspace) in _PROCEDURAL_BAKE_CHANNELS.items():
            if name == "albedo":
                assert colorspace == "sRGB"
            else:
                assert colorspace == "Non-Color", f"{name} should be Non-Color"


# ---------------------------------------------------------------------------
# Test: _generate_id_colors (pure logic)
# ---------------------------------------------------------------------------

class TestGenerateIdColors:
    """Test ID color generation for material ID maps."""

    def test_generates_correct_count(self):
        """Generates the requested number of colors."""
        from blender_addon.handlers.texture import _generate_id_colors

        colors = _generate_id_colors(5)
        assert len(colors) == 5

    def test_single_color(self):
        """Generates at least one color for count=1."""
        from blender_addon.handlers.texture import _generate_id_colors

        colors = _generate_id_colors(1)
        assert len(colors) == 1
        assert len(colors[0]) == 3

    def test_zero_count_gives_one(self):
        """Generates at least one color even for count=0."""
        from blender_addon.handlers.texture import _generate_id_colors

        colors = _generate_id_colors(0)
        assert len(colors) >= 1

    def test_colors_are_rgb_float_triplets(self):
        """Each color is an [R, G, B] list of floats in 0-1 range."""
        from blender_addon.handlers.texture import _generate_id_colors

        colors = _generate_id_colors(8)
        for color in colors:
            assert len(color) == 3
            for c in color:
                assert 0.0 <= c <= 1.0, f"Color value {c} out of range"

    def test_colors_are_distinct(self):
        """Colors for different materials should be visually distinct."""
        from blender_addon.handlers.texture import _generate_id_colors

        colors = _generate_id_colors(6)
        # Check that no two colors are identical
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                diff = sum(abs(a - b) for a, b in zip(colors[i], colors[j]))
                assert diff > 0.01, f"Colors {i} and {j} are too similar"

    def test_high_saturation_and_value(self):
        """Colors should have high saturation (0.9) and value (0.95)."""
        import colorsys
        from blender_addon.handlers.texture import _generate_id_colors

        colors = _generate_id_colors(4)
        for color in colors:
            _, s, v = colorsys.rgb_to_hsv(*color)
            assert s > 0.8, f"Saturation {s} too low"
            assert v > 0.8, f"Value {v} too low"


# ---------------------------------------------------------------------------
# Test: handle_channel_pack (pure logic -- no bpy needed)
# ---------------------------------------------------------------------------

class TestChannelPack:
    """Test channel packing utility."""

    def test_packs_three_channels(self):
        """Packs R, G, B channels from separate files into one RGB image."""
        from blender_addon.handlers.texture import handle_channel_pack

        red_path = _make_gray_png(64, 200)    # metallic
        green_path = _make_gray_png(64, 128)  # roughness
        blue_path = _make_gray_png(64, 255)   # AO

        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        try:
            result = handle_channel_pack({
                "red_path": red_path,
                "green_path": green_path,
                "blue_path": blue_path,
                "output_path": out_path,
            })

            assert result["output_path"] == out_path
            assert result["resolution"] == 64

            # Verify the packed image
            packed = PILImage.open(out_path)
            assert packed.mode == "RGB"
            assert packed.size == (64, 64)

            # Check center pixel
            r, g, b = packed.getpixel((32, 32))
            assert r == 200, f"Red channel should be 200, got {r}"
            assert g == 128, f"Green channel should be 128, got {g}"
            assert b == 255, f"Blue channel should be 255, got {b}"

        finally:
            for p in (red_path, green_path, blue_path, out_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_missing_channels_default_to_black(self):
        """Missing channel files produce black (0) in that channel."""
        from blender_addon.handlers.texture import handle_channel_pack

        green_path = _make_gray_png(64, 180)

        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        try:
            result = handle_channel_pack({
                "red_path": None,
                "green_path": green_path,
                "blue_path": None,
                "output_path": out_path,
                "resolution": 64,
            })

            packed = PILImage.open(out_path)
            r, g, b = packed.getpixel((32, 32))
            assert r == 0, f"Missing red should be 0, got {r}"
            assert g == 180, f"Green should be 180, got {g}"
            assert b == 0, f"Missing blue should be 0, got {b}"

        finally:
            os.unlink(green_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_resizes_to_target_resolution(self):
        """When resolution is specified, channels are resized."""
        from blender_addon.handlers.texture import handle_channel_pack

        red_path = _make_gray_png(128, 100)
        green_path = _make_gray_png(256, 150)

        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        try:
            result = handle_channel_pack({
                "red_path": red_path,
                "green_path": green_path,
                "blue_path": None,
                "output_path": out_path,
                "resolution": 64,
            })

            assert result["resolution"] == 64
            packed = PILImage.open(out_path)
            assert packed.size == (64, 64)
            packed.close()

        finally:
            for p in (red_path, green_path, out_path):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except PermissionError:
                    pass  # Windows file lock on temp cleanup

    def test_default_resolution_from_first_image(self):
        """Without explicit resolution, uses first available image's size."""
        from blender_addon.handlers.texture import handle_channel_pack

        red_path = _make_gray_png(512, 100)

        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        try:
            result = handle_channel_pack({
                "red_path": red_path,
                "green_path": None,
                "blue_path": None,
                "output_path": out_path,
            })

            assert result["resolution"] == 512

        finally:
            os.unlink(red_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_requires_output_path(self):
        """Raises ValueError when output_path is missing."""
        from blender_addon.handlers.texture import handle_channel_pack

        with pytest.raises(ValueError, match="output_path"):
            handle_channel_pack({"red_path": "foo.png"})

    def test_output_is_rgb_numpy_shape(self):
        """Packed output has correct numpy array shape (H, W, 3)."""
        from blender_addon.handlers.texture import handle_channel_pack

        red_path = _make_gray_png(32, 100)
        green_path = _make_gray_png(32, 200)
        blue_path = _make_gray_png(32, 50)

        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        try:
            handle_channel_pack({
                "red_path": red_path,
                "green_path": green_path,
                "blue_path": blue_path,
                "output_path": out_path,
            })

            packed = PILImage.open(out_path)
            arr = np.array(packed)
            assert arr.shape == (32, 32, 3)

        finally:
            for p in (red_path, green_path, blue_path, out_path):
                if os.path.exists(p):
                    os.unlink(p)


# ---------------------------------------------------------------------------
# Test: handle_ensure_flat_albedo (pure logic -- no bpy needed)
# ---------------------------------------------------------------------------

class TestEnsureFlatAlbedo:
    """Test albedo de-lighting verification."""

    def test_flat_color_is_flat(self):
        """A solid-color albedo is detected as flat."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        path = _make_rgb_png(128, (128, 100, 80))

        try:
            result = handle_ensure_flat_albedo({"image_path": path})

            assert result["is_flat"] is True
            assert len(result["issues"]) == 0
            assert "contrast_stats" in result
            assert result["contrast_stats"]["global_contrast"] < 0.01

        finally:
            os.unlink(path)

    def test_high_contrast_is_not_flat(self):
        """An image with strong shadows is detected as not flat."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        # Create image with strong local contrast (half bright, half dark)
        img = PILImage.new("RGB", (128, 128))
        for y in range(128):
            for x in range(128):
                if (x // 16 + y // 16) % 2 == 0:
                    img.putpixel((x, y), (220, 200, 180))
                else:
                    img.putpixel((x, y), (20, 15, 10))

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(path, format="PNG")

        try:
            result = handle_ensure_flat_albedo({"image_path": path})

            assert result["is_flat"] is False
            assert len(result["issues"]) > 0
            assert "delight" in result["recommendation"].lower()

        finally:
            os.unlink(path)

    def test_gradient_is_detected(self):
        """A strong gradient (simulating directional light) is flagged."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        # Create gradient from very dark to very bright
        img = PILImage.new("RGB", (256, 256))
        for y in range(256):
            for x in range(256):
                v = int(x * 255 / 255)
                img.putpixel((x, y), (v, v, v))

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(path, format="PNG")

        try:
            result = handle_ensure_flat_albedo({"image_path": path})

            assert result["contrast_stats"]["global_contrast"] > 0.7
            assert result["is_flat"] is False

        finally:
            os.unlink(path)

    def test_requires_image_path(self):
        """Raises ValueError when image_path is missing."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        with pytest.raises(ValueError, match="image_path"):
            handle_ensure_flat_albedo({})

    def test_invalid_path_raises(self):
        """Raises ValueError when image file doesn't exist."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        with pytest.raises(ValueError, match="not found"):
            handle_ensure_flat_albedo({"image_path": "/nonexistent/foo.png"})

    def test_returns_contrast_stats(self):
        """Result includes all expected contrast_stats fields."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        path = _make_rgb_png(64, (100, 100, 100))

        try:
            result = handle_ensure_flat_albedo({"image_path": path})
            stats = result["contrast_stats"]

            assert "global_contrast" in stats
            assert "avg_local_contrast" in stats
            assert "high_contrast_cells_pct" in stats
            assert "global_min_luminance" in stats
            assert "global_max_luminance" in stats

        finally:
            os.unlink(path)

    def test_custom_threshold(self):
        """Custom shadow_threshold affects detection sensitivity."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        # Create moderate contrast image
        img = PILImage.new("RGB", (128, 128))
        for y in range(128):
            for x in range(128):
                if x < 64:
                    img.putpixel((x, y), (150, 130, 110))
                else:
                    img.putpixel((x, y), (90, 75, 60))

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(path, format="PNG")

        try:
            # With strict threshold
            strict = handle_ensure_flat_albedo({
                "image_path": path,
                "shadow_threshold": 0.10,
            })

            # With permissive threshold
            permissive = handle_ensure_flat_albedo({
                "image_path": path,
                "shadow_threshold": 0.90,
            })

            # Strict should catch more issues than permissive
            assert len(strict["issues"]) >= len(permissive["issues"])

        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Test: handler function signatures accept correct params
# ---------------------------------------------------------------------------

class TestHandlerSignatures:
    """Test that all new handlers accept the expected params dict."""

    def test_bake_procedural_accepts_params(self):
        """handle_bake_procedural_to_images is callable with dict."""
        from blender_addon.handlers.texture import handle_bake_procedural_to_images

        assert callable(handle_bake_procedural_to_images)
        # Should raise ValueError for missing object_name, not TypeError
        with pytest.raises(ValueError, match="object_name"):
            handle_bake_procedural_to_images({})

    def test_bake_id_map_accepts_params(self):
        """handle_bake_id_map is callable with dict."""
        from blender_addon.handlers.texture import handle_bake_id_map

        assert callable(handle_bake_id_map)
        with pytest.raises(ValueError, match="object_name"):
            handle_bake_id_map({})

    def test_bake_thickness_accepts_params(self):
        """handle_bake_thickness_map is callable with dict."""
        from blender_addon.handlers.texture import handle_bake_thickness_map

        assert callable(handle_bake_thickness_map)
        with pytest.raises(ValueError, match="object_name"):
            handle_bake_thickness_map({})

    def test_channel_pack_accepts_params(self):
        """handle_channel_pack is callable with dict."""
        from blender_addon.handlers.texture import handle_channel_pack

        assert callable(handle_channel_pack)
        with pytest.raises(ValueError, match="output_path"):
            handle_channel_pack({})

    def test_ensure_flat_albedo_accepts_params(self):
        """handle_ensure_flat_albedo is callable with dict."""
        from blender_addon.handlers.texture import handle_ensure_flat_albedo

        assert callable(handle_ensure_flat_albedo)
        with pytest.raises(ValueError, match="image_path"):
            handle_ensure_flat_albedo({})


# ---------------------------------------------------------------------------
# Test: new handlers are registered in COMMAND_HANDLERS
# ---------------------------------------------------------------------------

class TestHandlerRegistration:
    """Test that new handlers are registered in the command handler dict."""

    def test_bake_procedural_registered(self):
        """texture_bake_procedural is in COMMAND_HANDLERS."""
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "texture_bake_procedural" in COMMAND_HANDLERS

    def test_bake_id_map_registered(self):
        """texture_bake_id_map is in COMMAND_HANDLERS."""
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "texture_bake_id_map" in COMMAND_HANDLERS

    def test_bake_thickness_registered(self):
        """texture_bake_thickness is in COMMAND_HANDLERS."""
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "texture_bake_thickness" in COMMAND_HANDLERS

    def test_channel_pack_registered(self):
        """texture_channel_pack is in COMMAND_HANDLERS."""
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "texture_channel_pack" in COMMAND_HANDLERS

    def test_ensure_flat_albedo_registered(self):
        """texture_ensure_flat_albedo is in COMMAND_HANDLERS."""
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "texture_ensure_flat_albedo" in COMMAND_HANDLERS

    def test_registered_handlers_are_callable(self):
        """All new registered handlers are callable functions."""
        from blender_addon.handlers import COMMAND_HANDLERS

        new_commands = [
            "texture_bake_procedural",
            "texture_bake_id_map",
            "texture_bake_thickness",
            "texture_channel_pack",
            "texture_ensure_flat_albedo",
        ]
        for cmd in new_commands:
            assert callable(COMMAND_HANDLERS[cmd]), f"{cmd} handler not callable"


# ---------------------------------------------------------------------------
# Test: existing handlers still work (regression)
# ---------------------------------------------------------------------------

class TestExistingHandlersNotBroken:
    """Verify existing texture handlers are still registered."""

    def test_existing_texture_handlers_present(self):
        """All pre-existing texture handlers remain registered."""
        from blender_addon.handlers import COMMAND_HANDLERS

        existing = [
            "texture_create_pbr",
            "texture_bake",
            "texture_validate",
            "texture_generate_wear",
            "texture_get_uv_region",
            "texture_get_seam_pixels",
        ]
        for cmd in existing:
            assert cmd in COMMAND_HANDLERS, f"Existing handler {cmd} missing"
