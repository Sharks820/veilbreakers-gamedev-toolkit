"""Bundle K — material ceiling tests.

Covers all six sub-modules plus the central ``register_bundle_k_passes``
entrypoint. Every test runs against a synthetic mask stack and never
touches bpy.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_stack(tile_size: int = 24, seed: int = 7):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    rng = np.random.default_rng(seed)
    xs = np.linspace(0.0, 1.0, tile_size + 1)
    ys = np.linspace(0.0, 1.0, tile_size + 1)
    xv, yv = np.meshgrid(xs, ys)
    height = (
        60.0
        + 350.0 * (xv ** 2 + yv ** 2)
        + 25.0 * rng.standard_normal((tile_size + 1, tile_size + 1))
    )
    return TerrainMaskStack(
        tile_size=tile_size,
        cell_size=2.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.astype(np.float64),
    )


def _build_state(tile_size: int = 24, seed: int = 7):
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainPipelineState,
    )

    stack = _make_stack(tile_size=tile_size, seed=seed)
    extent = float(tile_size) * float(stack.cell_size)
    region = BBox(0.0, 0.0, extent, extent)
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region,
        tile_size=tile_size,
        cell_size=stack.cell_size,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


@pytest.fixture
def state():
    return _build_state()


@pytest.fixture
def stack(state):
    return state.mask_stack


# ---------------------------------------------------------------------------
# 1. terrain_stochastic_shader
# ---------------------------------------------------------------------------


def test_stochastic_sampling_mask_shape_and_dtype(stack):
    from blender_addon.handlers.terrain_stochastic_shader import (
        build_stochastic_sampling_mask,
    )

    mask = build_stochastic_sampling_mask(stack, tile_size_m=4.0, seed=42)
    rows, cols = stack.height.shape
    assert mask.shape == (rows, cols, 2)
    assert mask.dtype == np.float32
    assert np.all(np.abs(mask) <= 0.5 + 1e-5)


def test_stochastic_sampling_mask_is_deterministic(stack):
    from blender_addon.handlers.terrain_stochastic_shader import (
        build_stochastic_sampling_mask,
    )

    a = build_stochastic_sampling_mask(stack, tile_size_m=4.0, seed=99)
    b = build_stochastic_sampling_mask(stack, tile_size_m=4.0, seed=99)
    np.testing.assert_array_equal(a, b)


def test_stochastic_sampling_different_seeds_differ(stack):
    from blender_addon.handlers.terrain_stochastic_shader import (
        build_stochastic_sampling_mask,
    )

    a = build_stochastic_sampling_mask(stack, tile_size_m=4.0, seed=1)
    b = build_stochastic_sampling_mask(stack, tile_size_m=4.0, seed=2)
    assert not np.allclose(a, b)


def test_stochastic_sampling_rejects_bad_tile_size(stack):
    from blender_addon.handlers.terrain_stochastic_shader import (
        build_stochastic_sampling_mask,
    )

    with pytest.raises(ValueError):
        build_stochastic_sampling_mask(stack, tile_size_m=0.0, seed=1)


def test_export_unity_shader_template_writes_json():
    from blender_addon.handlers.terrain_stochastic_shader import (
        StochasticShaderTemplate,
        export_unity_shader_template,
    )

    tpl = StochasticShaderTemplate(
        template_id="rock_01",
        tile_size_m=3.5,
        randomness_strength=0.8,
        layer_index=2,
    )
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "rock_01.json"
        payload = export_unity_shader_template(tpl, out)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["schema"].startswith("veilbreakers.terrain.stochastic_shader")
        assert data["template"]["template_id"] == "rock_01"
        assert data["template"]["layer_index"] == 2
        assert payload == data


def test_pass_stochastic_shader_populates_roughness(state):
    from blender_addon.handlers.terrain_stochastic_shader import pass_stochastic_shader

    result = pass_stochastic_shader(state, None)
    assert result.status == "ok"
    assert state.mask_stack.get("roughness_variation") is not None
    assert state.mask_stack.get("roughness_variation").dtype == np.float32


# ---------------------------------------------------------------------------
# 2. terrain_macro_color
# ---------------------------------------------------------------------------


def test_macro_color_shape_and_dtype(stack):
    from blender_addon.handlers.terrain_macro_color import compute_macro_color

    color = compute_macro_color(stack)
    rows, cols = stack.height.shape
    assert color.shape == (rows, cols, 3)
    assert color.dtype == np.float32
    assert color.min() >= 0.0 and color.max() <= 1.0


def test_macro_color_respects_biome_id(stack):
    from blender_addon.handlers.terrain_macro_color import (
        DARK_FANTASY_PALETTE,
        compute_macro_color,
    )

    biome = np.zeros_like(stack.height, dtype=np.int32)
    biome[5:10, 5:10] = 5  # snowcap
    stack.set("biome_id", biome, "test")
    color = compute_macro_color(stack)
    np.array(DARK_FANTASY_PALETTE[5], dtype=np.float32)
    # Snow region should be brighter than surrounding by a meaningful margin
    region_mean = color[5:10, 5:10].mean(axis=(0, 1))
    assert region_mean.mean() > 0.6


def test_macro_color_wet_darkens(stack):
    from blender_addon.handlers.terrain_macro_color import compute_macro_color

    dry = compute_macro_color(stack)
    wet = np.ones_like(stack.height, dtype=np.float64) * 0.9
    stack.set("wetness", wet, "test")
    wet_color = compute_macro_color(stack)
    assert wet_color.mean() < dry.mean()


def test_macro_color_custom_palette(stack):
    from blender_addon.handlers.terrain_macro_color import compute_macro_color

    biome = np.zeros_like(stack.height, dtype=np.int32)
    stack.set("biome_id", biome, "test")
    color = compute_macro_color(stack, palette={0: (1.0, 0.0, 0.0)})
    # Red channel dominant (before altitude cool-shift applies)
    assert color[..., 0].mean() > color[..., 2].mean()


def test_pass_macro_color_populates_channel(state):
    from blender_addon.handlers.terrain_macro_color import pass_macro_color

    result = pass_macro_color(state, None)
    assert result.status == "ok"
    assert state.mask_stack.get("macro_color") is not None
    assert state.mask_stack.get("macro_color").shape[-1] == 3


# ---------------------------------------------------------------------------
# 3. terrain_multiscale_breakup
# ---------------------------------------------------------------------------


def test_multiscale_breakup_shape_and_dtype(stack):
    from blender_addon.handlers.terrain_multiscale_breakup import (
        compute_multiscale_breakup,
    )

    br = compute_multiscale_breakup(stack, scales_m=(5.0, 20.0, 100.0), seed=11)
    assert br.shape == stack.height.shape
    assert br.dtype == np.float32


def test_multiscale_breakup_deterministic(stack):
    from blender_addon.handlers.terrain_multiscale_breakup import (
        compute_multiscale_breakup,
    )

    a = compute_multiscale_breakup(stack, scales_m=(5.0, 20.0), seed=11)
    b = compute_multiscale_breakup(stack, scales_m=(5.0, 20.0), seed=11)
    np.testing.assert_array_equal(a, b)


def test_multiscale_breakup_rejects_empty_scales(stack):
    from blender_addon.handlers.terrain_multiscale_breakup import (
        compute_multiscale_breakup,
    )

    with pytest.raises(ValueError):
        compute_multiscale_breakup(stack, scales_m=(), seed=1)


def test_pass_multiscale_breakup_sets_roughness(state):
    from blender_addon.handlers.terrain_multiscale_breakup import pass_multiscale_breakup

    result = pass_multiscale_breakup(state, None)
    assert result.status == "ok"
    rough = state.mask_stack.get("roughness_variation")
    assert rough is not None
    assert rough.min() >= 0.0 and rough.max() <= 1.0


# ---------------------------------------------------------------------------
# 4. terrain_shadow_clipmap_bake
# ---------------------------------------------------------------------------


def test_bake_shadow_clipmap_shape_and_range(stack):
    from blender_addon.handlers.terrain_shadow_clipmap_bake import bake_shadow_clipmap

    mask = bake_shadow_clipmap(stack, sun_dir_rad=(0.5, 0.8), clipmap_res=64)
    assert mask.shape == (64, 64)
    assert mask.dtype == np.float32
    assert mask.min() >= 0.0 and mask.max() <= 1.0


def test_bake_shadow_clipmap_sun_below_horizon(stack):
    from blender_addon.handlers.terrain_shadow_clipmap_bake import bake_shadow_clipmap

    mask = bake_shadow_clipmap(stack, sun_dir_rad=(0.0, -0.1), clipmap_res=32)
    assert np.all(mask == 0.0)


def test_export_shadow_clipmap_npy_and_sidecar(stack):
    from blender_addon.handlers.terrain_shadow_clipmap_bake import (
        bake_shadow_clipmap,
        export_shadow_clipmap_exr,
    )

    mask = bake_shadow_clipmap(stack, sun_dir_rad=(0.5, 0.9), clipmap_res=32)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "shadow.exr"  # we intentionally pass exr; writer converts
        export_shadow_clipmap_exr(mask, path)
        npy_path = path.with_suffix(".npy")
        assert npy_path.exists()
        sidecar = npy_path.with_suffix(".json")
        assert sidecar.exists()
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        assert meta["format"] == "float32_npy"
        loaded = np.load(npy_path)
        assert loaded.shape == mask.shape


def test_pass_shadow_clipmap_populates_cloud_shadow(state):
    from blender_addon.handlers.terrain_shadow_clipmap_bake import pass_shadow_clipmap

    result = pass_shadow_clipmap(state, None)
    assert result.status == "ok"
    cs = state.mask_stack.get("cloud_shadow")
    assert cs is not None
    assert cs.shape == state.mask_stack.height.shape


# ---------------------------------------------------------------------------
# 5. terrain_roughness_driver
# ---------------------------------------------------------------------------


def test_roughness_driver_default_baseline(stack):
    from blender_addon.handlers.terrain_roughness_driver import (
        compute_roughness_from_wetness_wear,
    )

    r = compute_roughness_from_wetness_wear(stack)
    assert r.shape == stack.height.shape
    assert r.dtype == np.float32
    # Baseline ~0.55 with no wet/erosion signals
    assert 0.4 < r.mean() < 0.7


def test_roughness_driver_wet_reduces_roughness(stack):
    from blender_addon.handlers.terrain_roughness_driver import (
        compute_roughness_from_wetness_wear,
    )

    baseline = compute_roughness_from_wetness_wear(stack)
    wet = np.ones_like(stack.height, dtype=np.float64)
    stack.set("wetness", wet, "test")
    wet_r = compute_roughness_from_wetness_wear(stack)
    assert wet_r.mean() < baseline.mean()


def test_roughness_driver_erosion_increases_roughness(stack):
    from blender_addon.handlers.terrain_roughness_driver import (
        compute_roughness_from_wetness_wear,
    )

    baseline = compute_roughness_from_wetness_wear(stack)
    er = np.ones_like(stack.height, dtype=np.float64) * 5.0
    stack.set("erosion_amount", er, "test")
    eroded = compute_roughness_from_wetness_wear(stack)
    assert eroded.mean() > baseline.mean()


def test_pass_roughness_driver(state):
    from blender_addon.handlers.terrain_roughness_driver import pass_roughness_driver

    result = pass_roughness_driver(state, None)
    assert result.status == "ok"
    rough = state.mask_stack.get("roughness_variation")
    assert rough is not None
    assert rough.dtype == np.float32


# ---------------------------------------------------------------------------
# 6. terrain_quixel_ingest
# ---------------------------------------------------------------------------


def _make_fake_quixel_asset(root: Path, asset_id: str = "rock_mossy_01") -> Path:
    asset_dir = root / asset_id
    asset_dir.mkdir(parents=True)
    (asset_dir / f"{asset_id}_Albedo.png").write_bytes(b"fake")
    (asset_dir / f"{asset_id}_Normal_LOD0.png").write_bytes(b"fake")
    (asset_dir / f"{asset_id}_Roughness.png").write_bytes(b"fake")
    (asset_dir / f"{asset_id}_AO.png").write_bytes(b"fake")
    (asset_dir / f"{asset_id}.json").write_text(
        json.dumps({"displayName": asset_id, "category": "Rock"}),
        encoding="utf-8",
    )
    return asset_dir


def test_ingest_quixel_asset_parses_channels():
    from blender_addon.handlers.terrain_quixel_ingest import ingest_quixel_asset

    with tempfile.TemporaryDirectory() as td:
        asset_dir = _make_fake_quixel_asset(Path(td))
        asset = ingest_quixel_asset(asset_dir)
        assert asset.asset_id == "rock_mossy_01"
        assert asset.has_channel("albedo")
        assert asset.has_channel("normal")
        assert asset.has_channel("roughness")
        assert asset.has_channel("ao")
        assert asset.metadata.get("displayName") == "rock_mossy_01"


def test_ingest_quixel_asset_missing_folder_raises():
    from blender_addon.handlers.terrain_quixel_ingest import ingest_quixel_asset

    with pytest.raises(FileNotFoundError):
        ingest_quixel_asset(Path("/nonexistent/quixel/asset"))


def test_apply_quixel_to_layer_creates_splatmap(stack):
    from blender_addon.handlers.terrain_quixel_ingest import (
        QuixelAsset,
        apply_quixel_to_layer,
    )

    asset = QuixelAsset(asset_id="rock_01", textures={"albedo": Path("fake.png")})
    assert stack.splatmap_weights_layer is None
    apply_quixel_to_layer(stack, "rock_layer", asset)
    assert stack.splatmap_weights_layer is not None
    assert stack.splatmap_weights_layer.shape[-1] == 1
    assert "quixel_layer[rock_layer]" in stack.populated_by_pass


def test_pass_quixel_ingest_with_assets_param(state):
    from blender_addon.handlers.terrain_quixel_ingest import (
        QuixelAsset,
        pass_quixel_ingest,
    )

    asset = QuixelAsset(asset_id="mud_01", textures={"albedo": Path("fake.png")})
    result = pass_quixel_ingest(state, None, assets=[asset])
    assert result.status == "ok"
    assert result.metrics["asset_count"] == 1


def test_pass_quixel_ingest_handles_missing_paths(state):
    from blender_addon.handlers.terrain_quixel_ingest import pass_quixel_ingest

    state.intent.composition_hints["quixel_assets"] = [
        {"asset_path": "/definitely/not/here", "layer_id": "bad"}
    ]
    result = pass_quixel_ingest(state, None)
    # soft failure -> still ok (no hard issues)
    assert result.status == "ok"
    assert any(i.code == "quixel_ingest_failure" for i in result.issues)


# ---------------------------------------------------------------------------
# 7. Bundle K registrar
# ---------------------------------------------------------------------------


def test_register_bundle_k_passes():
    from blender_addon.handlers.terrain_bundle_k import (
        BUNDLE_K_PASSES,
        register_bundle_k_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    # Preserve registry
    original = dict(TerrainPassController.PASS_REGISTRY)
    try:
        TerrainPassController.clear_registry()
        register_bundle_k_passes()
        for name in BUNDLE_K_PASSES:
            assert name in TerrainPassController.PASS_REGISTRY
    finally:
        TerrainPassController.clear_registry()
        for k, v in original.items():
            TerrainPassController.PASS_REGISTRY[k] = v


def test_bundle_k_passes_produce_unity_channels():
    """Ensure Bundle K passes collectively produce macro_color +
    roughness_variation + (implicit via cloud_shadow) for Unity export."""
    from blender_addon.handlers.terrain_bundle_k import register_bundle_k_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    original = dict(TerrainPassController.PASS_REGISTRY)
    try:
        TerrainPassController.clear_registry()
        register_bundle_k_passes()
        produced = set()
        for name in ("macro_color", "multiscale_breakup", "shadow_clipmap",
                     "roughness_driver", "stochastic_shader", "quixel_ingest"):
            produced.update(TerrainPassController.PASS_REGISTRY[name].produces_channels)
        assert "macro_color" in produced
        assert "roughness_variation" in produced
        assert "cloud_shadow" in produced
        assert "splatmap_weights_layer" in produced
    finally:
        TerrainPassController.clear_registry()
        for k, v in original.items():
            TerrainPassController.PASS_REGISTRY[k] = v
