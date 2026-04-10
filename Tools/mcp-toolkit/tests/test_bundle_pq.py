"""Bundle P + Bundle Q — regression tests.

Covers:
- terrain_dem_import (Bundle P)
- terrain_palette_extract (Bundle P)
- terrain_footprint_surface (Bundle Q)
- terrain_destructibility_patches (Bundle Q)
- terrain_weathering_timeline (Bundle Q)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from blender_addon.handlers.terrain_dem_import import (
    DEMSource,
    import_dem_tile,
    normalize_dem_to_world_range,
    resample_dem_to_tile_grid,
)
from blender_addon.handlers.terrain_palette_extract import (
    PaletteEntry,
    extract_palette_from_image,
    palette_to_biome_mapping,
)
from blender_addon.handlers.terrain_footprint_surface import (
    FootprintSurfacePoint,
    compute_footprint_surface_data,
    export_footprint_data_json,
)
from blender_addon.handlers.terrain_destructibility_patches import (
    DestructibilityPatch,
    detect_destructibility_patches,
    export_destructibility_json,
)
from blender_addon.handlers.terrain_weathering_timeline import (
    WeatheringEvent,
    apply_weathering_event,
    generate_weathering_timeline,
)
from blender_addon.handlers.terrain_semantics import BBox, TerrainMaskStack


def _tiny_stack(size: int = 8) -> TerrainMaskStack:
    h = np.linspace(0.0, 10.0, size * size, dtype=np.float32).reshape(size, size)
    return TerrainMaskStack(
        tile_size=0,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )


# ---------------------------------------------------------------------------
# Bundle P — DEM import
# ---------------------------------------------------------------------------


class TestDEMImport:
    def test_synthetic_dem_is_deterministic(self):
        src = DEMSource(source_type="synthetic", url_or_path="", resolution_m=30.0)
        bounds = BBox(0.0, 0.0, 1000.0, 1000.0)
        a = import_dem_tile(src, bounds)
        b = import_dem_tile(src, bounds)
        np.testing.assert_array_equal(a, b)

    def test_synthetic_dem_varies_with_bbox(self):
        src = DEMSource(source_type="synthetic", url_or_path="", resolution_m=30.0)
        a = import_dem_tile(src, BBox(0.0, 0.0, 1000.0, 1000.0))
        b = import_dem_tile(src, BBox(10.0, 10.0, 1010.0, 1010.0))
        assert not np.array_equal(a, b)

    def test_loads_real_npy(self, tmp_path: Path):
        arr = np.arange(64, dtype=np.float32).reshape(8, 8)
        p = tmp_path / "dem.npy"
        np.save(str(p), arr)
        src = DEMSource(source_type="local", url_or_path=str(p), resolution_m=1.0)
        out = import_dem_tile(src, BBox(0.0, 0.0, 8.0, 8.0))
        np.testing.assert_allclose(out, arr.astype(np.float32))

    def test_resample_shape(self):
        dem = np.arange(64, dtype=np.float32).reshape(8, 8)
        out = resample_dem_to_tile_grid(dem, target_tile_size=16, target_cell_size=0.5)
        assert out.shape == (16, 16)

    def test_resample_rejects_non_2d(self):
        with pytest.raises(ValueError):
            resample_dem_to_tile_grid(np.zeros((2, 2, 2)), 4, 1.0)

    def test_resample_rejects_nonpositive_target(self):
        with pytest.raises(ValueError):
            resample_dem_to_tile_grid(np.zeros((4, 4)), 0, 1.0)

    def test_normalize_world_range_min_max(self):
        dem = np.linspace(-100.0, 200.0, 64).reshape(8, 8).astype(np.float32)
        out = normalize_dem_to_world_range(dem, 0.0, 1.0)
        assert abs(float(out.min()) - 0.0) < 1e-5
        assert abs(float(out.max()) - 1.0) < 1e-5

    def test_normalize_world_range_rejects_inverted(self):
        with pytest.raises(ValueError):
            normalize_dem_to_world_range(np.zeros((4, 4)), 1.0, 0.0)

    def test_normalize_flat_dem(self):
        dem = np.full((4, 4), 7.0, dtype=np.float32)
        out = normalize_dem_to_world_range(dem, 10.0, 20.0)
        assert np.allclose(out, 15.0)


# ---------------------------------------------------------------------------
# Bundle P — palette extraction
# ---------------------------------------------------------------------------


class TestPaletteExtract:
    def test_extract_palette_returns_k_entries(self):
        rng = np.random.default_rng(0)
        img = rng.random((32, 32, 3)).astype(np.float32)
        palette = extract_palette_from_image(img, k=4)
        assert len(palette) == 4
        assert all(isinstance(e, PaletteEntry) for e in palette)

    def test_palette_weights_sum_to_one(self):
        rng = np.random.default_rng(1)
        img = rng.random((16, 16, 3)).astype(np.float32)
        palette = extract_palette_from_image(img, k=3)
        total = sum(e.weight for e in palette)
        assert abs(total - 1.0) < 1e-5

    def test_palette_sorted_descending(self):
        rng = np.random.default_rng(2)
        img = rng.random((16, 16, 3)).astype(np.float32)
        palette = extract_palette_from_image(img, k=5)
        weights = [e.weight for e in palette]
        assert weights == sorted(weights, reverse=True)

    def test_palette_handles_uint8(self):
        img = (np.ones((8, 8, 3)) * 128).astype(np.uint8)
        palette = extract_palette_from_image(img, k=2)
        assert palette[0].color_rgb[0] <= 1.0

    def test_palette_rgba_accepted(self):
        img = np.ones((8, 8, 4), dtype=np.float32) * 0.5
        palette = extract_palette_from_image(img, k=2)
        assert len(palette) >= 1

    def test_palette_to_biome_mapping(self):
        palette = [
            PaletteEntry(color_rgb=(0.0, 0.6, 0.0), weight=0.5, label="foliage"),
            PaletteEntry(color_rgb=(0.1, 0.1, 0.1), weight=0.3, label="dark"),
        ]
        mapping = palette_to_biome_mapping(palette)
        assert mapping["foliage"] == "forest"
        assert mapping["dark"] == "shadow"


# ---------------------------------------------------------------------------
# Bundle Q — footprint surface
# ---------------------------------------------------------------------------


class TestFootprintSurface:
    def test_single_point(self):
        stack = _tiny_stack(8)
        pts = compute_footprint_surface_data(stack, np.array([[2.0, 2.0]]))
        assert len(pts) == 1
        assert isinstance(pts[0], FootprintSurfacePoint)

    def test_multiple_points(self):
        stack = _tiny_stack(8)
        pts = compute_footprint_surface_data(
            stack, np.array([[1.0, 1.0], [2.0, 3.0], [4.0, 5.0]])
        )
        assert len(pts) == 3

    def test_normal_is_unit_length(self):
        stack = _tiny_stack(8)
        pts = compute_footprint_surface_data(stack, np.array([[3.0, 3.0]]))
        n = np.array(pts[0].normal)
        assert abs(np.linalg.norm(n) - 1.0) < 1e-5

    def test_export_json(self, tmp_path: Path):
        stack = _tiny_stack(8)
        pts = compute_footprint_surface_data(stack, np.array([[2.0, 2.0]]))
        out = tmp_path / "fp.json"
        export_footprint_data_json(pts, out)
        assert out.exists()
        payload = json.loads(out.read_text())
        assert "points" in payload

    def test_rejects_bad_shape(self):
        stack = _tiny_stack(8)
        with pytest.raises(ValueError):
            compute_footprint_surface_data(stack, np.zeros((3, 5)))


# ---------------------------------------------------------------------------
# Bundle Q — destructibility patches
# ---------------------------------------------------------------------------


class TestDestructibility:
    def test_no_rock_hardness_returns_empty(self):
        stack = _tiny_stack(8)
        assert detect_destructibility_patches(stack) == []

    def test_soft_rock_generates_patches(self):
        stack = _tiny_stack(16)
        stack.rock_hardness = np.full((16, 16), 0.2, dtype=np.float32)
        patches = detect_destructibility_patches(stack)
        assert len(patches) > 0
        assert all(isinstance(p, DestructibilityPatch) for p in patches)

    def test_hard_rock_generates_no_patches(self):
        stack = _tiny_stack(16)
        stack.rock_hardness = np.full((16, 16), 0.9, dtype=np.float32)
        patches = detect_destructibility_patches(stack)
        assert patches == []

    def test_wet_soft_rock_is_mud(self):
        stack = _tiny_stack(16)
        stack.rock_hardness = np.full((16, 16), 0.1, dtype=np.float32)
        stack.wetness = np.full((16, 16), 0.9, dtype=np.float32)
        patches = detect_destructibility_patches(stack)
        assert any(p.debris_type == "mud" for p in patches)

    def test_export_destructibility_json(self, tmp_path: Path):
        stack = _tiny_stack(16)
        stack.rock_hardness = np.full((16, 16), 0.2, dtype=np.float32)
        patches = detect_destructibility_patches(stack)
        out = tmp_path / "dest.json"
        export_destructibility_json(patches, out)
        assert out.exists()
        payload = json.loads(out.read_text())
        assert "patches" in payload


# ---------------------------------------------------------------------------
# Bundle Q — weathering timeline
# ---------------------------------------------------------------------------


class TestWeatheringTimeline:
    def test_timeline_deterministic(self):
        a = generate_weathering_timeline(24.0, seed=42)
        b = generate_weathering_timeline(24.0, seed=42)
        assert len(a) == len(b)
        for ea, eb in zip(a, b):
            assert ea.time_hours == eb.time_hours
            assert ea.kind == eb.kind

    def test_different_seeds_yield_different_timelines(self):
        a = generate_weathering_timeline(48.0, seed=1)
        b = generate_weathering_timeline(48.0, seed=2)
        assert a != b

    def test_zero_duration_empty(self):
        assert generate_weathering_timeline(0.0, seed=1) == []

    def test_apply_rain_increases_wetness(self):
        stack = _tiny_stack(8)
        stack.wetness = np.full((8, 8), 0.1, dtype=np.float32)
        before = stack.wetness.copy()
        apply_weathering_event(stack, WeatheringEvent(1.0, "rain", 0.3))
        assert (stack.wetness >= before).all()
        assert stack.wetness.max() > before.max()

    def test_apply_drought_decreases_wetness(self):
        stack = _tiny_stack(8)
        stack.wetness = np.full((8, 8), 0.5, dtype=np.float32)
        apply_weathering_event(stack, WeatheringEvent(1.0, "drought", 0.3))
        assert stack.wetness.max() < 0.5 + 1e-6

    def test_apply_freeze_is_noop(self):
        stack = _tiny_stack(8)
        stack.wetness = np.full((8, 8), 0.4, dtype=np.float32)
        before = stack.wetness.copy()
        apply_weathering_event(stack, WeatheringEvent(1.0, "freeze", 0.5))
        np.testing.assert_array_equal(stack.wetness, before)

    def test_apply_allocates_wetness_if_missing(self):
        stack = _tiny_stack(8)
        assert stack.wetness is None
        apply_weathering_event(stack, WeatheringEvent(1.0, "rain", 0.2))
        assert stack.wetness is not None
        assert stack.wetness.shape == stack.height.shape
