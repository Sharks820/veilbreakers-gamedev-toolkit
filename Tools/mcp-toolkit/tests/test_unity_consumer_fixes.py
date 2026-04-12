"""Tests for F188-F203 C# consumer bug fixes in scene_templates.py.

Validates:
- Heightmap endianness: byte_order param controls decode expression in C#
- File size validation: generated C# validates heightmap/alphamap size before parsing
- Manifest output: generated C# writes terrain manifest JSON
- Alphamap validation: alphamap size check before parsing
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_terrain_setup_script,
    generate_tiled_terrain_setup_script,
)


# ---------------------------------------------------------------------------
# F188-F191: Heightmap endianness
# ---------------------------------------------------------------------------


class TestHeightmapEndianness:
    """byte_order param controls which endianness the C# reader uses."""

    def test_default_byte_order_is_little(self):
        result = generate_terrain_setup_script("Assets/hm.raw")
        # Little-endian: low byte first
        assert "rawBytes[byteIndex] | (rawBytes[byteIndex + 1] << 8)" in result

    def test_little_endian_explicit(self):
        result = generate_terrain_setup_script("Assets/hm.raw", byte_order="little")
        assert "rawBytes[byteIndex] | (rawBytes[byteIndex + 1] << 8)" in result

    def test_big_endian(self):
        result = generate_terrain_setup_script("Assets/hm.raw", byte_order="big")
        # Big-endian: high byte first
        assert "(rawBytes[byteIndex] << 8) | rawBytes[byteIndex + 1]" in result

    def test_big_endian_excludes_little(self):
        result = generate_terrain_setup_script("Assets/hm.raw", byte_order="big")
        # Should NOT contain the little-endian pattern
        assert "rawBytes[byteIndex] | (rawBytes[byteIndex + 1] << 8)" not in result

    def test_invalid_byte_order_raises(self):
        with pytest.raises(ValueError, match="byte_order must be"):
            generate_terrain_setup_script("Assets/hm.raw", byte_order="middle")

    def test_invalid_byte_order_raises_empty(self):
        with pytest.raises(ValueError, match="byte_order must be"):
            generate_terrain_setup_script("Assets/hm.raw", byte_order="")

    def test_byte_order_noted_in_comment(self):
        result = generate_terrain_setup_script("Assets/hm.raw", byte_order="big")
        assert "big-endian" in result

    def test_byte_order_in_manifest(self):
        result = generate_terrain_setup_script("Assets/hm.raw", byte_order="big")
        assert '\\"byte_order\\": \\"big\\"' in result


class TestTiledHeightmapEndianness:
    """byte_order param works for tiled terrain too."""

    TILES = [
        {"heightmap_path": "Assets/t0.raw", "grid_x": 0, "grid_y": 0},
        {"heightmap_path": "Assets/t1.raw", "grid_x": 1, "grid_y": 0},
    ]

    def test_tiled_default_little_endian(self):
        result = generate_tiled_terrain_setup_script(self.TILES)
        assert "rawBytes0[byteIndex0] | (rawBytes0[byteIndex0 + 1] << 8)" in result

    def test_tiled_big_endian(self):
        result = generate_tiled_terrain_setup_script(self.TILES, byte_order="big")
        assert "(rawBytes0[byteIndex0] << 8) | rawBytes0[byteIndex0 + 1]" in result

    def test_tiled_invalid_byte_order(self):
        with pytest.raises(ValueError, match="byte_order must be"):
            generate_tiled_terrain_setup_script(self.TILES, byte_order="mixed")

    def test_tiled_byte_order_in_manifest(self):
        result = generate_tiled_terrain_setup_script(self.TILES, byte_order="little")
        assert '\\"byte_order\\": \\"little\\"' in result


# ---------------------------------------------------------------------------
# F192-F195: File size validation
# ---------------------------------------------------------------------------


class TestHeightmapFileValidation:
    """Generated C# must validate heightmap file size before parsing."""

    def test_heightmap_size_check_present(self):
        result = generate_terrain_setup_script("Assets/hm.raw", resolution=513)
        assert "expectedBytes" in result
        assert "res * res * 2" in result

    def test_heightmap_size_mismatch_logs_error(self):
        result = generate_terrain_setup_script("Assets/hm.raw")
        assert "Heightmap file size mismatch" in result

    def test_heightmap_size_check_mentions_resolution(self):
        result = generate_terrain_setup_script("Assets/hm.raw", resolution=1025)
        assert "1025" in result
        assert "16-bit" in result

    def test_no_parsing_on_size_mismatch(self):
        """On size mismatch, SetHeights should be inside the else (valid) branch."""
        result = generate_terrain_setup_script("Assets/hm.raw")
        # SetHeights should come AFTER the size validation passes (inside else block)
        mismatch_idx = result.index("file size mismatch")
        setheights_idx = result.index("SetHeights")
        assert setheights_idx > mismatch_idx


class TestTiledHeightmapFileValidation:
    """Tiled terrain also validates heightmap sizes."""

    TILES = [{"heightmap_path": "Assets/t0.raw", "grid_x": 0, "grid_y": 0}]

    def test_tiled_heightmap_size_check(self):
        result = generate_tiled_terrain_setup_script(self.TILES)
        assert "expectedBytes0" in result
        assert "res0 * res0 * 2" in result

    def test_tiled_heightmap_mismatch_logs_error(self):
        result = generate_tiled_terrain_setup_script(self.TILES)
        assert "heightmap size mismatch" in result


# ---------------------------------------------------------------------------
# F196-F199: Alphamap validation
# ---------------------------------------------------------------------------


class TestAlphamapValidation:
    """Alphamap reader validates file size before parsing."""

    LAYERS_4 = [
        {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
        {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
        {"texture_path": "Assets/Textures/dirt.png", "tiling": 8.0},
        {"texture_path": "Assets/Textures/snow.png", "tiling": 12.0},
    ]

    def test_alphamap_size_check_present(self):
        result = generate_terrain_setup_script(
            "Assets/hm.raw",
            splatmap_layers=self.LAYERS_4,
            alphamap_path="Assets/alpha.raw",
        )
        assert "expectedAlphaBytes" in result

    def test_alphamap_size_mismatch_logs_error(self):
        result = generate_terrain_setup_script(
            "Assets/hm.raw",
            splatmap_layers=self.LAYERS_4,
            alphamap_path="Assets/alpha.raw",
        )
        assert "Alphamap file size mismatch" in result

    def test_alphamap_no_parsing_on_mismatch(self):
        """SetAlphamaps should only happen after size validation passes."""
        result = generate_terrain_setup_script(
            "Assets/hm.raw",
            splatmap_layers=self.LAYERS_4,
            alphamap_path="Assets/alpha.raw",
        )
        mismatch_idx = result.index("Alphamap file size mismatch")
        setalpha_idx = result.index("SetAlphamaps")
        assert setalpha_idx > mismatch_idx


class TestTiledAlphamapValidation:
    """Tiled terrain alphamap reader validates file size."""

    LAYERS_4 = [
        {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
        {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
        {"texture_path": "Assets/Textures/dirt.png", "tiling": 8.0},
        {"texture_path": "Assets/Textures/snow.png", "tiling": 12.0},
    ]

    def test_tiled_alphamap_size_check(self):
        tiles = [{"heightmap_path": "Assets/t0.raw", "grid_x": 0, "grid_y": 0,
                  "alphamap_path": "Assets/alpha0.raw"}]
        result = generate_tiled_terrain_setup_script(
            tiles, splatmap_layers=self.LAYERS_4,
        )
        assert "ExpectedAlpha" in result

    def test_tiled_alphamap_mismatch_logs_error(self):
        tiles = [{"heightmap_path": "Assets/t0.raw", "grid_x": 0, "grid_y": 0,
                  "alphamap_path": "Assets/alpha0.raw"}]
        result = generate_tiled_terrain_setup_script(
            tiles, splatmap_layers=self.LAYERS_4,
        )
        assert "alphamap size mismatch" in result


# ---------------------------------------------------------------------------
# F200-F203: Manifest output
# ---------------------------------------------------------------------------


class TestTerrainManifest:
    """Generated C# writes a terrain manifest file."""

    def test_manifest_file_written(self):
        result = generate_terrain_setup_script("Assets/hm.raw")
        assert "vb_terrain_manifest.json" in result

    def test_manifest_contains_heightmap_path(self):
        result = generate_terrain_setup_script("Assets/Terrain/my_hm.raw")
        assert "my_hm.raw" in result
        assert '\\"heightmap\\"' in result

    def test_manifest_contains_byte_order(self):
        result = generate_terrain_setup_script("Assets/hm.raw", byte_order="big")
        assert '\\"byte_order\\": \\"big\\"' in result

    def test_manifest_contains_splatmap_count(self):
        layers = [
            {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
            {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
        ]
        result = generate_terrain_setup_script(
            "Assets/hm.raw", splatmap_layers=layers,
        )
        assert '\\"splatmap_layers\\": 2' in result

    def test_manifest_zero_splatmaps_when_none(self):
        result = generate_terrain_setup_script("Assets/hm.raw")
        assert '\\"splatmap_layers\\": 0' in result

    def test_manifest_contains_resolution(self):
        result = generate_terrain_setup_script("Assets/hm.raw", resolution=1025)
        assert '\\"resolution\\": 1025' in result


class TestTiledTerrainManifest:
    """Tiled terrain also writes manifest."""

    TILES = [{"heightmap_path": "Assets/t0.raw", "grid_x": 0, "grid_y": 0}]

    def test_tiled_manifest_file_written(self):
        result = generate_tiled_terrain_setup_script(self.TILES)
        assert "vb_terrain_manifest.json" in result

    def test_tiled_manifest_tile_count(self):
        result = generate_tiled_terrain_setup_script(self.TILES)
        assert '\\"tile_count\\": 1' in result

    def test_tiled_manifest_byte_order(self):
        result = generate_tiled_terrain_setup_script(self.TILES, byte_order="big")
        assert '\\"byte_order\\": \\"big\\"' in result
