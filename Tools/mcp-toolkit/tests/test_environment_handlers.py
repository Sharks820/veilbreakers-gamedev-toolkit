"""Unit tests for environment handler pure-logic functions.

Tests _validate_terrain_params, _export_heightmap_raw, and validates
handler return dict structure via pure-logic extraction.
"""

import struct

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# _validate_terrain_params tests
# ---------------------------------------------------------------------------


class TestValidateTerrainParams:
    """Test terrain parameter validation (pure logic, no Blender)."""

    def test_valid_defaults(self):
        """Default parameters pass validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({})
        assert result["name"] == "Terrain"
        assert result["resolution"] == 129
        assert result["terrain_type"] == "mountains"
        assert result["erosion"] == "none"

    def test_raises_resolution_too_large(self):
        """Resolution > 8192 raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="Resolution"):
            _validate_terrain_params({"resolution": 8193})

    def test_raises_resolution_too_small(self):
        """Resolution < 3 raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="Resolution"):
            _validate_terrain_params({"resolution": 2})

    def test_raises_unknown_terrain_type(self):
        """Unknown terrain_type raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="terrain_type"):
            _validate_terrain_params({"terrain_type": "swamp"})

    def test_raises_unknown_erosion_mode(self):
        """Unknown erosion mode raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="erosion"):
            _validate_terrain_params({"erosion": "wind"})

    def test_max_resolution_8192_passes(self):
        """Resolution 8192 (maximum) passes validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"resolution": 8192})
        assert result["resolution"] == 8192

    def test_resolution_4096_passes(self):
        """Resolution 4096 passes validation (4096+ support)."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"resolution": 4096})
        assert result["resolution"] == 4096

    def test_default_erosion_iterations_5000(self):
        """Default erosion_iterations is 5000."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({})
        assert result["erosion_iterations"] == 5000

    def test_all_terrain_types_valid(self):
        """All 6 terrain types pass validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        for ttype in ["mountains", "hills", "plains", "volcanic", "canyon", "cliffs"]:
            result = _validate_terrain_params({"terrain_type": ttype})
            assert result["terrain_type"] == ttype

    def test_all_erosion_modes_valid(self):
        """All erosion modes pass validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        for mode in ["none", "hydraulic", "thermal", "both"]:
            result = _validate_terrain_params({"erosion": mode})
            assert result["erosion"] == mode

    def test_custom_name_preserved(self):
        """Custom name parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"name": "MyTerrain"})
        assert result["name"] == "MyTerrain"

    def test_custom_scale_preserved(self):
        """Custom scale parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"scale": 200.0})
        assert result["scale"] == 200.0

    def test_custom_height_scale_preserved(self):
        """Custom height_scale parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"height_scale": 50.0})
        assert result["height_scale"] == 50.0

    def test_custom_seed_preserved(self):
        """Custom seed parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"seed": 42})
        assert result["seed"] == 42

    def test_returns_dict(self):
        """Validated result is a dict."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _export_heightmap_raw tests
# ---------------------------------------------------------------------------


class TestExportHeightmapRaw:
    """Test 16-bit RAW heightmap export (pure logic, no file I/O)."""

    def test_returns_bytes(self):
        """Export returns bytes object."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 0.5], [0.5, 1.0]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        assert isinstance(raw, bytes)

    def test_correct_byte_length(self):
        """Output length is width * height * 2 bytes (16-bit)."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 0.5], [0.5, 1.0]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        assert len(raw) == 2 * 2 * 2  # 2x2 grid, 2 bytes per pixel

    def test_known_2x2_values(self):
        """Known 2x2 heightmap produces correct uint16 values."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 1.0], [0.5, 0.5]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        # Unpack as 4 uint16 little-endian values
        values = struct.unpack("<4H", raw)
        # [0.0 -> 0, 1.0 -> 65535, 0.5 -> ~32767, 0.5 -> ~32767]
        assert values[0] == 0
        assert values[1] == 65535
        # 0.5 * 65535 = 32767.5, cast to uint16 = 32767 or 32768
        assert 32766 <= values[2] <= 32768
        assert 32766 <= values[3] <= 32768

    def test_flip_vertical_reverses_rows(self):
        """flip_vertical=True reverses row order."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 0.0], [1.0, 1.0]])
        raw_no_flip = _export_heightmap_raw(hmap, flip_vertical=False)
        raw_flipped = _export_heightmap_raw(hmap, flip_vertical=True)
        # No flip: row 0 = [0, 0], row 1 = [65535, 65535]
        # Flipped: row 0 = [65535, 65535], row 1 = [0, 0]
        vals_no_flip = struct.unpack("<4H", raw_no_flip)
        vals_flipped = struct.unpack("<4H", raw_flipped)
        # First row of no_flip should be last row of flipped
        assert vals_no_flip[0] == vals_flipped[2]
        assert vals_no_flip[1] == vals_flipped[3]
        assert vals_no_flip[2] == vals_flipped[0]
        assert vals_no_flip[3] == vals_flipped[1]

    def test_flat_heightmap_all_same(self):
        """Flat heightmap (all same value) exports as all zeros."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.full((4, 4), 0.5)
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        values = struct.unpack(f"<{4*4}H", raw)
        # All same value -> normalized to 0 (since max == min)
        assert all(v == 0 for v in values)

    def test_values_in_uint16_range(self):
        """All exported values are in [0, 65535]."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.random.RandomState(42).rand(8, 8)
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        values = struct.unpack(f"<{8*8}H", raw)
        assert all(0 <= v <= 65535 for v in values)

    def test_little_endian_byte_order(self):
        """Output uses little-endian byte order."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        # Create a heightmap where we know the exact uint16 value
        hmap = np.array([[0.0, 1.0]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        # Value 65535 in little-endian is 0xFF 0xFF
        # Value 0 in little-endian is 0x00 0x00
        assert raw[0:2] == b"\x00\x00"  # 0
        assert raw[2:4] == b"\xff\xff"  # 65535

    def test_larger_heightmap(self):
        """Correctly handles larger heightmaps."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.random.RandomState(42).rand(64, 64)
        raw = _export_heightmap_raw(hmap, flip_vertical=True)
        assert len(raw) == 64 * 64 * 2


# ---------------------------------------------------------------------------
# Handler return dict structure tests
# ---------------------------------------------------------------------------


class TestHandlerReturnDictKeys:
    """Verify expected keys in handler return dicts (via pure-logic validation)."""

    def test_generate_terrain_expected_keys(self):
        """handle_generate_terrain returns dict with required keys."""
        # We can't call the handler without Blender, but we can verify
        # the validation function returns the right structure
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({
            "name": "TestTerrain",
            "resolution": 65,
            "terrain_type": "hills",
            "erosion": "hydraulic",
        })
        # Validated params should contain all the keys the handler uses
        assert "name" in result
        assert "resolution" in result
        assert "terrain_type" in result
        assert "erosion" in result
        assert "height_scale" in result
        assert "seed" in result

    def test_export_raw_produces_correct_format(self):
        """_export_heightmap_raw produces Unity-compatible 16-bit little-endian."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.random.RandomState(42).rand(33, 33)
        raw = _export_heightmap_raw(hmap, flip_vertical=True)
        # Should be 33 * 33 * 2 bytes
        assert len(raw) == 33 * 33 * 2
        # Should be parseable as uint16 array
        arr = np.frombuffer(raw, dtype=np.uint16)
        assert arr.shape == (33 * 33,)
        assert arr.min() >= 0
        assert arr.max() <= 65535


# ---------------------------------------------------------------------------
# _nearest_pot_plus_1 tests
# ---------------------------------------------------------------------------


class TestNearestPotPlus1:
    """Test power-of-two + 1 calculation for Unity compatibility."""

    def test_129_stays_129(self):
        """129 is already a POT+1 (128+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(129) == 129

    def test_100_becomes_129(self):
        """100 rounds up to 129 (128+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(100) == 129

    def test_257_stays_257(self):
        """257 is already a POT+1 (256+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(257) == 257

    def test_513_stays_513(self):
        """513 is already a POT+1 (512+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(513) == 513

    def test_3_becomes_3(self):
        """3 is already a POT+1 (2+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(3) == 3

    def test_65_becomes_65(self):
        """65 is already a POT+1 (64+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(65) == 65

    def test_50_becomes_65(self):
        """50 rounds up to 65 (64+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(50) == 65
