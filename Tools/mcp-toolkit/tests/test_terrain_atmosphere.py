"""Bundle L — atmosphere & horizon tests.

Covers:
    - terrain_horizon_lod: compute_horizon_lod, build_horizon_skybox_mask,
      pass_horizon_lod
    - terrain_fog_masks: compute_fog_pool_mask, compute_mist_envelope,
      pass_fog_masks
    - terrain_god_ray_hints: compute_god_ray_hints,
      export_god_ray_hints_json, pass_god_ray_hints
    - terrain_bundle_l: register_bundle_l_passes
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_stack(tile_size: int = 128, seed: int = 11):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    rng = np.random.default_rng(seed)
    n = tile_size + 1
    xs = np.linspace(-1.0, 1.0, n)
    ys = np.linspace(-1.0, 1.0, n)
    xv, yv = np.meshgrid(xs, ys)
    # Valley running along x=0; ridges on both sides; random perturbation.
    height = (
        200.0
        + 150.0 * xv * xv
        + 80.0 * np.sin(yv * 2.0)
        + 15.0 * rng.standard_normal((n, n))
    )
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=2.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.astype(np.float64),
    )
    return stack


def _build_state(tile_size: int = 128, seed: int = 11):
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainPipelineState,
    )

    stack = _make_stack(tile_size=tile_size, seed=seed)
    extent = float(tile_size * stack.cell_size)
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
# 1. terrain_horizon_lod
# ---------------------------------------------------------------------------


def test_compute_horizon_lod_enforces_1_over_64_ceiling(stack):
    from blender_addon.handlers.terrain_horizon_lod import compute_horizon_lod

    # Request a deliberately too-large target_res; function must clamp.
    lod = compute_horizon_lod(stack, target_res=9999)
    src_min = min(stack.height.shape)
    assert lod.shape[0] <= max(1, src_min // 64)
    assert lod.shape[0] == lod.shape[1]
    assert lod.dtype == np.float32


def test_compute_horizon_lod_preserves_peak_silhouette(stack):
    from blender_addon.handlers.terrain_horizon_lod import compute_horizon_lod

    lod = compute_horizon_lod(stack, target_res=2)
    # Max-pool must preserve global maximum within floating error.
    assert float(lod.max()) >= float(stack.height.max()) - 1e-3


def test_compute_horizon_lod_deterministic(stack):
    from blender_addon.handlers.terrain_horizon_lod import compute_horizon_lod

    a = compute_horizon_lod(stack, target_res=2)
    b = compute_horizon_lod(stack, target_res=2)
    assert np.array_equal(a, b)


def test_build_horizon_skybox_mask_shape_and_range(stack):
    from blender_addon.handlers.terrain_horizon_lod import build_horizon_skybox_mask

    vantage = (128.0, 128.0, 50.0)
    profile = build_horizon_skybox_mask(stack, vantage, ray_count=64)
    assert profile.shape == (64,)
    assert profile.dtype == np.float32
    # Elevation angles are in radians, must be within [-pi/2, pi/2].
    assert float(profile.max()) <= math.pi * 0.5 + 1e-6
    assert float(profile.min()) >= -math.pi * 0.5 - 1e-6


def test_build_horizon_skybox_mask_higher_vantage_lowers_horizon(stack):
    from blender_addon.handlers.terrain_horizon_lod import build_horizon_skybox_mask

    low = build_horizon_skybox_mask(stack, (128.0, 128.0, -500.0), ray_count=32)
    high = build_horizon_skybox_mask(stack, (128.0, 128.0, 5000.0), ray_count=32)
    # From a high vantage the visible horizon should be below the low one.
    assert float(high.mean()) < float(low.mean())


def test_pass_horizon_lod_populates_lod_bias(state):
    from blender_addon.handlers.terrain_horizon_lod import pass_horizon_lod

    res = pass_horizon_lod(state, None)
    assert res.status == "ok"
    assert "lod_bias" in res.produced_channels
    assert state.mask_stack.lod_bias is not None
    bias = np.asarray(state.mask_stack.lod_bias)
    assert bias.shape == state.mask_stack.height.shape
    assert bias.dtype == np.float32
    assert float(bias.min()) >= 0.0 and float(bias.max()) <= 1.0 + 1e-6
    assert res.metrics["target_res"] <= max(1, min(state.mask_stack.height.shape) // 64)


# ---------------------------------------------------------------------------
# 2. terrain_fog_masks
# ---------------------------------------------------------------------------


def test_compute_fog_pool_mask_shape_and_range(stack):
    from blender_addon.handlers.terrain_fog_masks import compute_fog_pool_mask

    fog = compute_fog_pool_mask(stack)
    assert fog.shape == stack.height.shape
    assert fog.dtype == np.float32
    assert float(fog.min()) >= 0.0
    assert float(fog.max()) <= 1.0 + 1e-6


def test_compute_fog_pool_mask_thicker_in_valleys(stack):
    from blender_addon.handlers.terrain_fog_masks import compute_fog_pool_mask

    fog = compute_fog_pool_mask(stack)
    h = np.asarray(stack.height)
    low_mask = h < np.percentile(h, 25)
    high_mask = h > np.percentile(h, 75)
    assert float(fog[low_mask].mean()) > float(fog[high_mask].mean())


def test_compute_mist_envelope_near_water(stack):
    from blender_addon.handlers.terrain_fog_masks import compute_mist_envelope

    wet = np.zeros_like(stack.height, dtype=np.float32)
    wet[60:65, 60:65] = 1.0
    env = compute_mist_envelope(stack, wet)
    assert env.shape == stack.height.shape
    assert env.dtype == np.float32
    # Center should have max, dilated cells slightly less.
    assert float(env[62, 62]) >= 0.99
    assert float(env[58, 62]) > 0.0
    # Far from water should be 0.
    assert float(env[0, 0]) == 0.0


def test_pass_fog_masks_populates_mist(state):
    from blender_addon.handlers.terrain_fog_masks import pass_fog_masks

    res = pass_fog_masks(state, None)
    assert res.status == "ok"
    assert "mist" in res.produced_channels
    assert state.mask_stack.mist is not None
    mist = np.asarray(state.mask_stack.mist)
    assert mist.shape == state.mask_stack.height.shape
    assert float(mist.min()) >= 0.0 and float(mist.max()) <= 1.0 + 1e-6


# ---------------------------------------------------------------------------
# 3. terrain_god_ray_hints
# ---------------------------------------------------------------------------


def test_compute_god_ray_hints_returns_list(stack):
    from blender_addon.handlers.terrain_god_ray_hints import compute_god_ray_hints

    cs = np.zeros_like(stack.height, dtype=np.float32)
    hints = compute_god_ray_hints(stack, (math.radians(90.0), math.radians(40.0)), cs)
    assert isinstance(hints, list)
    assert len(hints) <= 16
    for h in hints:
        assert len(h.source_pos) == 3
        assert 0.0 <= h.intensity


def test_compute_god_ray_hints_cave_bonus(stack):
    from blender_addon.handlers.terrain_god_ray_hints import compute_god_ray_hints

    cave = np.zeros_like(stack.height, dtype=np.float32)
    cave[40, 40] = 1.0
    stack.set("cave_candidate", cave, "test_fixture")
    cs = np.zeros_like(stack.height, dtype=np.float32)
    hints = compute_god_ray_hints(stack, (0.0, math.radians(30.0)), cs)
    assert any("cave_entrance" in h.source_feature_id for h in hints)


def test_export_god_ray_hints_json_roundtrip(stack):
    from blender_addon.handlers.terrain_god_ray_hints import (
        compute_god_ray_hints,
        export_god_ray_hints_json,
    )

    cs = np.zeros_like(stack.height, dtype=np.float32)
    hints = compute_god_ray_hints(stack, (1.0, 0.5), cs)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "hints.json"
        export_god_ray_hints_json(hints, out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["hint_count"] == len(hints)
        assert len(data["hints"]) == len(hints)
        if hints:
            assert "source_pos" in data["hints"][0]
            assert "direction_rad" in data["hints"][0]


def test_pass_god_ray_hints_runs_without_cave_or_cloud(state):
    from blender_addon.handlers.terrain_god_ray_hints import pass_god_ray_hints

    res = pass_god_ray_hints(state, None)
    assert res.status == "ok"
    assert "hint_count" in res.metrics
    assert res.metrics["hint_count"] >= 0


def test_pass_god_ray_hints_deterministic(state):
    from blender_addon.handlers.terrain_god_ray_hints import compute_god_ray_hints

    cs = np.zeros_like(state.mask_stack.height, dtype=np.float32)
    a = compute_god_ray_hints(state.mask_stack, (0.8, 0.4), cs)
    b = compute_god_ray_hints(state.mask_stack, (0.8, 0.4), cs)
    assert len(a) == len(b)
    for ha, hb in zip(a, b):
        assert ha.source_pos == hb.source_pos
        assert ha.source_feature_id == hb.source_feature_id


# ---------------------------------------------------------------------------
# 4. terrain_bundle_l registrar
# ---------------------------------------------------------------------------


def test_register_bundle_l_passes_registers_all_three():
    from blender_addon.handlers.terrain_bundle_l import (
        BUNDLE_L_PASSES,
        register_bundle_l_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_l_passes()
    for name in BUNDLE_L_PASSES:
        assert name in TerrainPassController.PASS_REGISTRY
        defn = TerrainPassController.PASS_REGISTRY[name]
        assert defn.name == name
        assert defn.func is not None


def test_bundle_l_passes_have_distinct_seed_namespaces():
    from blender_addon.handlers.terrain_bundle_l import (
        BUNDLE_L_PASSES,
        register_bundle_l_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_l_passes()
    namespaces = {
        TerrainPassController.PASS_REGISTRY[n].seed_namespace for n in BUNDLE_L_PASSES
    }
    assert len(namespaces) == len(BUNDLE_L_PASSES)
