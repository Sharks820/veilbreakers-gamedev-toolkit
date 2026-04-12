"""Tests for terrain_unity_export bug fixes F050-F063.

F050: Z-up -> Y-up axis swap
F051: Little-endian byte order for .raw heightmap
F052: Resolution validation (power-of-2+1)
F053: FBX terrain mesh export metadata
F054-F058: LOD chain generation
F059-F063: Splatmap validation (sum-to-1, layer count, resolution)
+ Terrain size bridging (Blender -> Unity)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from blender_addon.handlers.terrain_unity_export import (
    VALID_UNITY_RESOLUTIONS,
    FBXExportConfig,
    TerrainSizeBridge,
    ensure_little_endian,
    export_heightmap_raw,
    export_lod_chain,
    export_unity_manifest,
    generate_fbx_export_metadata,
    generate_lod_heightmaps,
    is_valid_unity_resolution,
    normalize_splatmap,
    swap_z_up_to_y_up_heightmap,
    swap_z_up_to_y_up_positions,
    validate_heightmap_resolution,
    validate_splatmap,
)
from blender_addon.handlers.terrain_semantics import TerrainMaskStack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stack(size: int = 128, cell_size: float = 1.0) -> TerrainMaskStack:
    """Create a minimal TerrainMaskStack for testing."""
    rng = np.random.RandomState(42)
    height = rng.rand(size, size).astype(np.float32) * 100.0
    return TerrainMaskStack(
        tile_size=size,
        cell_size=cell_size,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )


def _make_unity_stack(size: int = 129) -> TerrainMaskStack:
    """Create a stack with Unity-compatible resolution (2^n+1)."""
    rng = np.random.RandomState(42)
    height = rng.rand(size, size).astype(np.float32) * 200.0
    return TerrainMaskStack(
        tile_size=size - 1,  # tile_size is the edge count, not vertex count
        cell_size=1.0,
        world_origin_x=10.0,
        world_origin_y=20.0,
        tile_x=1,
        tile_y=2,
        height=height,
    )


# ===========================================================================
# F050: Z-up -> Y-up axis swap
# ===========================================================================


class TestF050AxisSwapPositions:
    """F050: swap_z_up_to_y_up_positions transforms (X,Y,Z) Z-up -> Y-up."""

    def test_identity_axes(self):
        """X stays, Blender Z becomes Unity Y, Blender Y becomes Unity Z."""
        pts = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        result = swap_z_up_to_y_up_positions(pts)
        # Unity X = Blender X
        np.testing.assert_array_equal(result[:, 0], pts[:, 0])
        # Unity Y = Blender Z
        np.testing.assert_array_equal(result[:, 1], pts[:, 2])
        # Unity Z = Blender Y
        np.testing.assert_array_equal(result[:, 2], pts[:, 1])

    def test_single_point(self):
        pts = np.array([[10.0, 20.0, 30.0]])
        result = swap_z_up_to_y_up_positions(pts)
        assert result.shape == (1, 3)
        assert result[0, 0] == 10.0
        assert result[0, 1] == 30.0  # Z -> Y
        assert result[0, 2] == 20.0  # Y -> Z

    def test_rejects_wrong_shape(self):
        with pytest.raises(ValueError, match="must be.*N, 3"):
            swap_z_up_to_y_up_positions(np.zeros((5, 2)))

    def test_preserves_dtype(self):
        pts = np.array([[1, 2, 3]], dtype=np.float32)
        result = swap_z_up_to_y_up_positions(pts)
        assert result.dtype == np.float32


class TestF050AxisSwapHeightmap:
    """F050: swap_z_up_to_y_up_heightmap transposes the grid for axis change."""

    def test_transpose_applied(self):
        hm = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
        result = swap_z_up_to_y_up_heightmap(hm)
        np.testing.assert_array_equal(result, hm.T)

    def test_square_heightmap(self):
        hm = np.arange(9, dtype=np.float32).reshape(3, 3)
        result = swap_z_up_to_y_up_heightmap(hm)
        assert result.shape == (3, 3)
        np.testing.assert_array_equal(result, hm.T)

    def test_contiguous(self):
        hm = np.ones((4, 4), dtype=np.float32)
        result = swap_z_up_to_y_up_heightmap(hm)
        assert result.flags["C_CONTIGUOUS"]

    def test_rejects_3d(self):
        with pytest.raises(ValueError, match="must be 2D"):
            swap_z_up_to_y_up_heightmap(np.zeros((3, 3, 3)))


# ===========================================================================
# F051: Little-endian byte order
# ===========================================================================


class TestF051Endianness:
    """F051: ensure_little_endian forces LE byte order."""

    def test_native_to_little_endian(self):
        arr = np.array([1, 2, 3], dtype=np.uint16)
        result = ensure_little_endian(arr)
        assert result.dtype.byteorder in ("<", "=", "|")
        np.testing.assert_array_equal(result, arr)

    def test_big_endian_to_little(self):
        arr = np.array([1000, 2000, 3000], dtype=np.dtype(">u2"))
        assert arr.dtype.byteorder == ">"
        result = ensure_little_endian(arr)
        assert result.dtype.byteorder == "<"
        np.testing.assert_array_equal(result, [1000, 2000, 3000])

    def test_already_little_endian_noop(self):
        arr = np.array([1, 2], dtype=np.dtype("<u2"))
        result = ensure_little_endian(arr)
        np.testing.assert_array_equal(result, arr)

    def test_single_byte_passthrough(self):
        arr = np.array([1, 2, 3], dtype=np.uint8)
        result = ensure_little_endian(arr)
        np.testing.assert_array_equal(result, arr)


class TestF051ExportHeightmapRaw:
    """F051: export_heightmap_raw writes LE uint16 .raw file."""

    def test_writes_raw_file(self):
        hm = np.ones((33, 33), dtype=np.uint16) * 1000
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.raw"
            meta = export_heightmap_raw(hm, path, swap_axes=False)
            assert path.exists()
            assert meta["dtype"] == "uint16"
            assert meta["byte_order"] == "little"
            assert meta["resolution"] == 33
            # Size should be 33*33*2 bytes
            assert meta["size_bytes"] == 33 * 33 * 2

    def test_swap_axes_transposes(self):
        hm = np.arange(6, dtype=np.uint16).reshape(2, 3)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.raw"
            meta = export_heightmap_raw(hm, path, swap_axes=True)
            # After transpose: 3x2 -> resolution is 3
            assert meta["resolution"] == 3

    def test_raw_file_readable_as_uint16(self):
        hm = np.array([[100, 200], [300, 400]], dtype=np.uint16)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.raw"
            export_heightmap_raw(hm, path, swap_axes=False)
            loaded = np.fromfile(path, dtype=np.dtype("<u2")).reshape(2, 2)
            np.testing.assert_array_equal(loaded, hm)


# ===========================================================================
# F052: Resolution validation
# ===========================================================================


class TestF052ResolutionValidation:
    """F052: validate Unity terrain heightmap resolution requirements."""

    def test_valid_resolutions(self):
        for res in [33, 65, 129, 257, 513, 1025, 2049, 4097]:
            assert is_valid_unity_resolution(res), f"{res} should be valid"

    def test_invalid_resolutions(self):
        for res in [0, 1, 2, 32, 64, 100, 128, 256, 512, 1000, 1024]:
            assert not is_valid_unity_resolution(res), f"{res} should be invalid"

    def test_valid_unity_resolutions_tuple(self):
        assert len(VALID_UNITY_RESOLUTIONS) == 8
        assert VALID_UNITY_RESOLUTIONS[0] == 33
        assert VALID_UNITY_RESOLUTIONS[-1] == 4097

    def test_validate_good_shape(self):
        errors = validate_heightmap_resolution((513, 513))
        assert errors == []

    def test_validate_non_square(self):
        errors = validate_heightmap_resolution((513, 257))
        assert any("square" in e for e in errors)

    def test_validate_wrong_resolution(self):
        errors = validate_heightmap_resolution((512, 512))
        assert any("not a valid Unity resolution" in e for e in errors)

    def test_validate_not_2d(self):
        errors = validate_heightmap_resolution((512, 512, 3))
        assert any("must be 2D" in e for e in errors)


# ===========================================================================
# F053: FBX export metadata
# ===========================================================================


class TestF053FBXExport:
    """F053: FBX terrain mesh export metadata generation."""

    def test_default_config(self):
        stack = _make_stack(64)
        meta = generate_fbx_export_metadata(stack)
        assert meta["format"] == "FBX"
        assert meta["version"] == "7.4"
        assert meta["axis_conversion"]["source"] == "z-up"
        assert meta["axis_conversion"]["target"] == "y-up"
        assert meta["axis_conversion"]["applied"] is True

    def test_vertex_triangle_counts(self):
        stack = _make_stack(32)
        meta = generate_fbx_export_metadata(stack)
        assert meta["vertex_count"] == 32 * 32
        assert meta["triangle_count"] == 31 * 31 * 2

    def test_no_axis_conversion(self):
        config = FBXExportConfig(apply_axis_conversion=False)
        stack = _make_stack(16)
        meta = generate_fbx_export_metadata(stack, config)
        assert meta["axis_conversion"]["applied"] is False
        # Bounds should be in Z-up order
        bounds_min = meta["bounds"]["min"]
        assert bounds_min[2] == pytest.approx(stack.height_min_m or 0, abs=0.1)

    def test_axis_converted_bounds(self):
        config = FBXExportConfig(apply_axis_conversion=True)
        stack = _make_stack(16)
        meta = generate_fbx_export_metadata(stack, config)
        # With conversion: Y = height
        bounds_min = meta["bounds"]["min"]
        assert bounds_min[1] == pytest.approx(stack.height_min_m or 0, abs=0.1)

    def test_terrain_size(self):
        stack = _make_stack(64, cell_size=2.0)
        meta = generate_fbx_export_metadata(stack)
        assert meta["terrain_size"]["width_m"] == pytest.approx(128.0)
        assert meta["terrain_size"]["depth_m"] == pytest.approx(128.0)


# ===========================================================================
# F054-F058: LOD chain generation
# ===========================================================================


class TestF054LODGeneration:
    """F054-F058: LOD chain heightmap generation."""

    def test_lod_count(self):
        hm = np.random.rand(129, 129).astype(np.float32)
        lods = generate_lod_heightmaps(hm, lod_levels=4)
        assert len(lods) == 4

    def test_lod_resolutions_halve(self):
        hm = np.random.rand(129, 129).astype(np.float32)
        lods = generate_lod_heightmaps(hm, lod_levels=4)
        assert lods[0].shape == (129, 129)
        assert lods[1].shape == (65, 65)
        assert lods[2].shape == (33, 33)
        assert lods[3].shape == (17, 17)

    def test_lod0_is_original(self):
        hm = np.random.rand(33, 33).astype(np.float32)
        lods = generate_lod_heightmaps(hm, lod_levels=2)
        np.testing.assert_array_equal(lods[0], hm)

    def test_lod_preserves_corners(self):
        """Corner samples should be preserved through downsampling."""
        hm = np.random.rand(65, 65).astype(np.float32)
        lods = generate_lod_heightmaps(hm, lod_levels=2)
        # Corner (0,0) preserved
        assert lods[1][0, 0] == pytest.approx(hm[0, 0])
        # Corner (-1,-1) preserved
        assert lods[1][-1, -1] == pytest.approx(hm[-1, -1])

    def test_rejects_non_square(self):
        with pytest.raises(ValueError, match="must be square"):
            generate_lod_heightmaps(np.zeros((64, 128)))

    def test_stops_at_minimum_size(self):
        hm = np.random.rand(5, 5).astype(np.float32)
        lods = generate_lod_heightmaps(hm, lod_levels=10)
        # 5 -> 3 -> 2 -> stops (2 < 3 so no further downsampling)
        assert len(lods) == 3
        assert lods[-1].shape[0] < 5  # Actually downsampled


class TestF054LODExport:
    """F054-F058: LOD chain file export."""

    def test_export_creates_files(self):
        hm = np.random.rand(33, 33).astype(np.float32) * 100
        with tempfile.TemporaryDirectory() as td:
            results = export_lod_chain(hm, Path(td), lod_levels=3)
            assert len(results) == 3
            for r in results:
                assert Path(r["path"]).exists()
                assert r["dtype"] == "uint16"
                assert r["byte_order"] == "little"

    def test_lod_metadata_has_levels(self):
        hm = np.random.rand(65, 65).astype(np.float32) * 50
        with tempfile.TemporaryDirectory() as td:
            results = export_lod_chain(hm, Path(td), lod_levels=2)
            assert results[0]["lod_level"] == 0
            assert results[1]["lod_level"] == 1


# ===========================================================================
# F059-F063: Splatmap validation
# ===========================================================================


class TestF059SplatmapValidation:
    """F059-F063: splatmap weight validation for Unity terrain layers."""

    def test_valid_splatmap(self):
        splat = np.zeros((64, 64, 4), dtype=np.float32)
        splat[:, :, 0] = 1.0  # All weight on layer 0
        errors = validate_splatmap(splat)
        assert errors == []

    def test_too_many_layers(self):
        splat = np.zeros((32, 32, 20), dtype=np.float32)
        splat[:, :, 0] = 1.0
        errors = validate_splatmap(splat, max_layers=16)
        assert any("exceeds Unity max" in e for e in errors)

    def test_zero_layers(self):
        splat = np.zeros((32, 32, 0), dtype=np.float32)
        errors = validate_splatmap(splat)
        assert any("0 layers" in e for e in errors)

    def test_non_square(self):
        splat = np.zeros((64, 32, 4), dtype=np.float32)
        splat[:, :, 0] = 1.0
        errors = validate_splatmap(splat)
        assert any("square" in e for e in errors)

    def test_negative_weights(self):
        splat = np.zeros((32, 32, 4), dtype=np.float32)
        splat[:, :, 0] = 1.0
        splat[0, 0, 1] = -0.5
        splat[0, 0, 0] = 1.5  # Keep sum at 1
        errors = validate_splatmap(splat)
        assert any("negative" in e for e in errors)

    def test_weights_not_summing_to_one(self):
        splat = np.zeros((32, 32, 4), dtype=np.float32)
        splat[:, :, 0] = 0.5  # Only half
        errors = validate_splatmap(splat)
        assert any("sum to 1.0" in e for e in errors)

    def test_resolution_mismatch(self):
        splat = np.zeros((64, 64, 4), dtype=np.float32)
        splat[:, :, 0] = 1.0
        errors = validate_splatmap(splat, expected_resolution=128)
        assert any("does not match" in e for e in errors)

    def test_2d_rejected(self):
        splat = np.zeros((32, 32), dtype=np.float32)
        errors = validate_splatmap(splat)
        assert any("must be 3D" in e for e in errors)

    def test_tolerance_honored(self):
        splat = np.zeros((8, 8, 2), dtype=np.float32)
        splat[:, :, 0] = 0.505
        splat[:, :, 1] = 0.505  # Sum = 1.01
        errors_strict = validate_splatmap(splat, weight_tolerance=0.001)
        errors_loose = validate_splatmap(splat, weight_tolerance=0.05)
        assert len(errors_strict) > 0
        assert len(errors_loose) == 0


class TestF063NormalizeSplatmap:
    """F063: normalize_splatmap ensures weights sum to 1.0."""

    def test_normalizes_to_one(self):
        splat = np.zeros((4, 4, 3), dtype=np.float32)
        splat[:, :, 0] = 0.5
        splat[:, :, 1] = 0.3
        splat[:, :, 2] = 0.2
        result = normalize_splatmap(splat)
        sums = result.sum(axis=2)
        np.testing.assert_allclose(sums, 1.0, atol=1e-6)

    def test_handles_zero_weights(self):
        splat = np.zeros((4, 4, 3), dtype=np.float32)
        result = normalize_splatmap(splat)
        # Zero-weight pixels should get first layer = 1.0
        assert result[0, 0, 0] == pytest.approx(1.0)
        sums = result.sum(axis=2)
        np.testing.assert_allclose(sums, 1.0, atol=1e-6)

    def test_already_normalized(self):
        splat = np.zeros((4, 4, 2), dtype=np.float32)
        splat[:, :, 0] = 0.7
        splat[:, :, 1] = 0.3
        result = normalize_splatmap(splat)
        np.testing.assert_allclose(result, splat, atol=1e-6)

    def test_rejects_2d(self):
        with pytest.raises(ValueError, match="must be 3D"):
            normalize_splatmap(np.zeros((4, 4)))


# ===========================================================================
# Terrain size bridging
# ===========================================================================


class TestTerrainSizeBridge:
    """Blender -> Unity terrain size mapping."""

    def test_from_mask_stack(self):
        stack = _make_unity_stack(129)
        bridge = TerrainSizeBridge.from_mask_stack(stack)
        assert bridge.blender_width_m == pytest.approx(129.0)
        assert bridge.blender_depth_m == pytest.approx(129.0)
        assert bridge.unity_terrain_width == pytest.approx(129.0)
        assert bridge.unity_terrain_length == pytest.approx(129.0)
        assert bridge.unity_terrain_height > 0

    def test_y_up_position_mapping(self):
        """Unity position Y should be Blender height_min (Z-up -> Y-up)."""
        stack = _make_unity_stack(129)
        bridge = TerrainSizeBridge.from_mask_stack(stack)
        # Unity Y position = Blender Z min = height_min_m
        assert bridge.unity_position[1] == pytest.approx(
            stack.height_min_m, abs=0.1
        )
        # Unity Z position = Blender Y origin
        assert bridge.unity_position[2] == pytest.approx(
            stack.world_origin_y, abs=0.1
        )

    def test_heightmap_resolution_snapped(self):
        stack = _make_stack(128)
        bridge = TerrainSizeBridge.from_mask_stack(stack)
        assert is_valid_unity_resolution(bridge.heightmap_resolution)
        # 128 should snap up to 129
        assert bridge.heightmap_resolution == 129

    def test_to_unity_settings(self):
        stack = _make_unity_stack(129)
        bridge = TerrainSizeBridge.from_mask_stack(stack)
        settings = bridge.to_unity_settings()
        assert "terrainData.size" in settings
        assert "terrain.transform.position" in settings
        assert "terrainData.heightmapResolution" in settings
        assert settings["terrainData.heightmapResolution"] == 129

    def test_height_padding(self):
        stack = _make_unity_stack(129)
        bridge = TerrainSizeBridge.from_mask_stack(stack, height_padding_factor=1.5)
        h_range = (stack.height_max_m or 0) - (stack.height_min_m or 0)
        assert bridge.unity_terrain_height == pytest.approx(
            max(h_range, 1.0) * 1.5, abs=0.1
        )


# ===========================================================================
# Integration: export_unity_manifest with new features
# ===========================================================================


class TestExportManifestIntegration:
    """Integration tests for export_unity_manifest with F050-F063 fixes."""

    def test_manifest_has_y_up_coordinate_system(self):
        """F050: exported manifest should report y-up."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=False)
            assert manifest["coordinate_system"] == "y-up"
            assert manifest["source_coordinate_system"] == "z-up"

    def test_manifest_has_byte_order(self):
        """F051: manifest should declare little-endian."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=False)
            assert manifest["byte_order"] == "little-endian"

    def test_manifest_resolution_warnings(self):
        """F052: non-2^n+1 resolution produces validation warnings."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=True)
            assert manifest["validation_status"] == "warnings"
            assert len(manifest["validation_warnings"]) > 0

    def test_manifest_valid_resolution_passes(self):
        """F052: 2^n+1 resolution passes validation."""
        stack = _make_unity_stack(129)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=True)
            # May still have warnings if splatmap is missing, but no resolution errors
            res_warnings = [
                w for w in manifest.get("validation_warnings", [])
                if "resolution" in w.lower()
            ]
            assert len(res_warnings) == 0

    def test_manifest_raw_file_exported(self):
        """F051: .raw heightmap file is created."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(
                stack, Path(td), validate=False, export_raw=True
            )
            assert "heightmap.raw" in manifest["files"]
            raw_path = Path(td) / "heightmap.raw"
            assert raw_path.exists()

    def test_manifest_lod_chain(self):
        """F054-F058: LOD chain exported when enabled."""
        stack = _make_unity_stack(129)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(
                stack, Path(td), validate=False, export_lods=True, lod_levels=3
            )
            assert manifest["lod_levels"] == 3
            assert "terrain_lod0.raw" in manifest["files"]
            assert "terrain_lod1.raw" in manifest["files"]
            assert "terrain_lod2.raw" in manifest["files"]

    def test_manifest_splatmap_validation(self):
        """F059-F063: splatmap validation integrated into manifest."""
        stack = _make_stack(128)
        splat = np.zeros((128, 128, 4), dtype=np.float32)
        splat[:, :, 0] = 0.5  # Does not sum to 1
        stack.set("splatmap_weights_layer", splat, "test")
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=True)
            assert manifest["validation_status"] == "warnings"
            assert any("sum to 1.0" in w for w in manifest["validation_warnings"])

    def test_manifest_terrain_size_bridge(self):
        """F050: terrain_size_bridge.json is created."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=False)
            bridge_path = Path(td) / "terrain_size_bridge.json"
            assert bridge_path.exists()
            bridge_data = json.loads(bridge_path.read_text())
            assert "terrainData.size" in bridge_data

    def test_manifest_unity_terrain_settings(self):
        """Manifest includes inline Unity terrain settings."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=False)
            assert "unity_terrain_settings" in manifest
            settings = manifest["unity_terrain_settings"]
            assert "terrainData.size" in settings

    def test_generator_version_v2(self):
        """Generator version updated to v2.0."""
        stack = _make_stack(128)
        with tempfile.TemporaryDirectory() as td:
            manifest = export_unity_manifest(stack, Path(td), validate=False)
            assert manifest["generator_version"] == "bundle_j_v2.0"
