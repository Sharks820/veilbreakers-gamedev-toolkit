"""Unit tests for texture handler pure-logic functions.

Tests BSDF_INPUT_MAP, _build_channel_config, _validate_texture_metadata,
and _validate_bake_params -- all pure functions testable without Blender.
"""

import pytest


# ---------------------------------------------------------------------------
# BSDF_INPUT_MAP tests
# ---------------------------------------------------------------------------


class TestBsdfInputMap:
    """Test that BSDF_INPUT_MAP covers all required PBR channel mappings."""

    def test_has_base_color(self):
        """BSDF_INPUT_MAP includes base_color -> 'Base Color'."""
        from blender_addon.handlers.texture import BSDF_INPUT_MAP

        assert "base_color" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["base_color"] == "Base Color"

    def test_has_metallic(self):
        """BSDF_INPUT_MAP includes metallic -> 'Metallic'."""
        from blender_addon.handlers.texture import BSDF_INPUT_MAP

        assert "metallic" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["metallic"] == "Metallic"

    def test_has_roughness(self):
        """BSDF_INPUT_MAP includes roughness -> 'Roughness'."""
        from blender_addon.handlers.texture import BSDF_INPUT_MAP

        assert "roughness" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["roughness"] == "Roughness"

    def test_has_normal(self):
        """BSDF_INPUT_MAP includes normal -> 'Normal'."""
        from blender_addon.handlers.texture import BSDF_INPUT_MAP

        assert "normal" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["normal"] == "Normal"

    def test_has_all_five_pbr_channels(self):
        """BSDF_INPUT_MAP has at least the 5 core PBR channels."""
        from blender_addon.handlers.texture import BSDF_INPUT_MAP

        required = {"base_color", "metallic", "roughness", "normal", "alpha"}
        assert required.issubset(set(BSDF_INPUT_MAP.keys()))

    def test_has_blender_4_renames(self):
        """BSDF_INPUT_MAP includes Blender 4.0+ renamed sockets."""
        from blender_addon.handlers.texture import BSDF_INPUT_MAP

        assert "subsurface" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["subsurface"] == "Subsurface Weight"
        assert "specular" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["specular"] == "Specular IOR Level"
        assert "transmission" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["transmission"] == "Transmission Weight"
        assert "coat" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["coat"] == "Coat Weight"
        assert "sheen" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["sheen"] == "Sheen Weight"
        assert "emission" in BSDF_INPUT_MAP
        assert BSDF_INPUT_MAP["emission"] == "Emission Color"


# ---------------------------------------------------------------------------
# _build_channel_config tests
# ---------------------------------------------------------------------------


class TestBuildChannelConfig:
    """Test PBR channel configuration tuples."""

    def test_returns_dict_with_five_channels(self):
        """_build_channel_config returns a dict with 5 PBR channel entries."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        assert isinstance(config, dict)
        assert len(config) == 5
        assert set(config.keys()) == {"albedo", "metallic", "roughness", "normal", "ao"}

    def test_albedo_channel(self):
        """Albedo has suffix '_albedo', input 'Base Color', sRGB, no normal node."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        suffix, input_name, colorspace, needs_normal_node = config["albedo"]
        assert suffix == "_albedo"
        assert input_name == "Base Color"
        assert colorspace == "sRGB"
        assert needs_normal_node is False

    def test_metallic_channel(self):
        """Metallic has suffix '_metallic', input 'Metallic', Non-Color."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        suffix, input_name, colorspace, needs_normal_node = config["metallic"]
        assert suffix == "_metallic"
        assert input_name == "Metallic"
        assert colorspace == "Non-Color"
        assert needs_normal_node is False

    def test_roughness_channel(self):
        """Roughness has suffix '_roughness', input 'Roughness', Non-Color."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        suffix, input_name, colorspace, needs_normal_node = config["roughness"]
        assert suffix == "_roughness"
        assert input_name == "Roughness"
        assert colorspace == "Non-Color"
        assert needs_normal_node is False

    def test_normal_channel(self):
        """Normal has suffix '_normal', input 'Normal', Non-Color, needs normal node."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        suffix, input_name, colorspace, needs_normal_node = config["normal"]
        assert suffix == "_normal"
        assert input_name == "Normal"
        assert colorspace == "Non-Color"
        assert needs_normal_node is True

    def test_ao_channel(self):
        """AO has suffix '_ao', None input (mixed via MixRGB), Non-Color."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        suffix, input_name, colorspace, needs_normal_node = config["ao"]
        assert suffix == "_ao"
        assert input_name is None
        assert colorspace == "Non-Color"
        assert needs_normal_node is False

    def test_normal_is_only_channel_needing_normal_node(self):
        """Only the normal channel should have needs_normal_node=True."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        for name, (_, _, _, needs_normal) in config.items():
            if name == "normal":
                assert needs_normal is True
            else:
                assert needs_normal is False, f"{name} should not need normal node"

    def test_all_non_albedo_channels_are_non_color(self):
        """All channels except albedo should use Non-Color colorspace."""
        from blender_addon.handlers.texture import _build_channel_config

        config = _build_channel_config()
        for name, (_, _, colorspace, _) in config.items():
            if name == "albedo":
                assert colorspace == "sRGB"
            else:
                assert colorspace == "Non-Color", f"{name} should be Non-Color"


# ---------------------------------------------------------------------------
# _validate_texture_metadata tests
# ---------------------------------------------------------------------------


class TestValidateTextureMetadata:
    """Test texture validation logic for resolution, format, etc."""

    def test_detects_non_power_of_two_width(self):
        """Non-power-of-two resolution (e.g., 1000x1000) is flagged."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1000, 1000, "PNG", "sRGB")
        assert not result["is_power_of_two"]
        assert any("power" in issue.lower() for issue in result["issues"])

    def test_detects_non_power_of_two_height(self):
        """Non-power-of-two height (e.g., 1024x999) is flagged."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1024, 999, "PNG", "sRGB")
        assert not result["is_power_of_two"]

    def test_passes_power_of_two_512(self):
        """512x512 passes power-of-two check."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(512, 512, "PNG", "sRGB")
        assert result["is_power_of_two"]

    def test_passes_power_of_two_1024(self):
        """1024x1024 passes power-of-two check."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1024, 1024, "PNG", "sRGB")
        assert result["is_power_of_two"]
        assert not any("power" in issue.lower() for issue in result["issues"])

    def test_passes_power_of_two_2048(self):
        """2048x2048 passes power-of-two check."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(2048, 2048, "PNG", "sRGB")
        assert result["is_power_of_two"]

    def test_passes_power_of_two_4096(self):
        """4096x4096 passes power-of-two check."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(4096, 4096, "PNG", "sRGB")
        assert result["is_power_of_two"]

    def test_flags_small_resolution_below_256(self):
        """Images smaller than 256x256 flagged as low resolution."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(128, 128, "PNG", "sRGB")
        assert any("low" in issue.lower() or "small" in issue.lower()
                    for issue in result["issues"])

    def test_flags_oversized_above_8192(self):
        """Images larger than 8192x8192 flagged as oversized."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(16384, 16384, "PNG", "sRGB")
        assert any("oversize" in issue.lower() or "large" in issue.lower()
                    for issue in result["issues"])

    def test_8192_not_oversized(self):
        """8192x8192 is the max valid size, should not be flagged."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(8192, 8192, "PNG", "sRGB")
        assert not any("oversize" in issue.lower() or "large" in issue.lower()
                        for issue in result["issues"])

    def test_256_not_low_resolution(self):
        """256x256 is the minimum valid size, should not be flagged."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(256, 256, "PNG", "sRGB")
        assert not any("low" in issue.lower() or "small" in issue.lower()
                        for issue in result["issues"])

    def test_reports_format_png(self):
        """PNG format is reported correctly in result."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1024, 1024, "PNG", "sRGB")
        assert result["format"] == "PNG"

    def test_reports_format_jpeg(self):
        """JPEG format is reported correctly in result."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1024, 1024, "JPEG", "sRGB")
        assert result["format"] == "JPEG"

    def test_reports_colorspace(self):
        """Colorspace is included in result."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1024, 1024, "PNG", "Non-Color")
        assert result["colorspace"] == "Non-Color"

    def test_reports_dimensions(self):
        """Width and height are included in result."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(2048, 1024, "PNG", "sRGB")
        assert result["width"] == 2048
        assert result["height"] == 1024

    def test_valid_texture_has_no_issues(self):
        """A well-formed 1024x1024 PNG has no issues."""
        from blender_addon.handlers.texture import _validate_texture_metadata

        result = _validate_texture_metadata(1024, 1024, "PNG", "sRGB")
        assert result["issues"] == []
        assert result["is_power_of_two"] is True


# ---------------------------------------------------------------------------
# _validate_bake_params tests
# ---------------------------------------------------------------------------


class TestValidateBakeParams:
    """Test bake parameter validation."""

    def test_raises_on_invalid_bake_type(self):
        """Invalid bake_type raises ValueError."""
        from blender_addon.handlers.texture import _validate_bake_params

        with pytest.raises(ValueError, match="bake_type"):
            _validate_bake_params("INVALID_TYPE")

    def test_raises_on_empty_bake_type(self):
        """Empty bake_type raises ValueError."""
        from blender_addon.handlers.texture import _validate_bake_params

        with pytest.raises(ValueError, match="bake_type"):
            _validate_bake_params("")

    def test_allows_normal(self):
        """NORMAL is a valid bake type."""
        from blender_addon.handlers.texture import _validate_bake_params

        _validate_bake_params("NORMAL")  # should not raise

    def test_allows_ao(self):
        """AO is a valid bake type."""
        from blender_addon.handlers.texture import _validate_bake_params

        _validate_bake_params("AO")  # should not raise

    def test_allows_combined(self):
        """COMBINED is a valid bake type."""
        from blender_addon.handlers.texture import _validate_bake_params

        _validate_bake_params("COMBINED")  # should not raise

    def test_allows_roughness(self):
        """ROUGHNESS is a valid bake type."""
        from blender_addon.handlers.texture import _validate_bake_params

        _validate_bake_params("ROUGHNESS")  # should not raise

    def test_allows_emit(self):
        """EMIT is a valid bake type."""
        from blender_addon.handlers.texture import _validate_bake_params

        _validate_bake_params("EMIT")  # should not raise

    def test_allows_diffuse(self):
        """DIFFUSE is a valid bake type."""
        from blender_addon.handlers.texture import _validate_bake_params

        _validate_bake_params("DIFFUSE")  # should not raise

    def test_case_sensitive(self):
        """Bake type validation is case-sensitive (lowercase should fail)."""
        from blender_addon.handlers.texture import _validate_bake_params

        with pytest.raises(ValueError):
            _validate_bake_params("normal")
