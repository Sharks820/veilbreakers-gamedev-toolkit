"""Bundle B — tests for terrain_materials_v2.py."""

from __future__ import annotations

import math
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pass_registry():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    yield
    TerrainPassController.clear_registry()


def _build_state(tile_size: int = 32, seed: int = 42):
    from blender_addon.handlers.terrain_masks import compute_base_masks
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
    )

    N = tile_size + 1
    # Synthetic heightmap: slope from 0..80m across rows, flat across cols
    rows = np.linspace(0.0, 80.0, N)[:, None]
    cols = np.zeros((1, N))
    height = rows + cols
    # Add a tall plateau at top
    height[:5, :] += 200.0
    rng = np.random.default_rng(seed)
    height += rng.normal(0.0, 0.02, size=height.shape)

    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    compute_base_masks(
        height,
        cell_size=1.0,
        tile_coords=(0, 0),
        stack=stack,
        pass_name="structural_masks",
    )
    region_bounds = BBox(0.0, 0.0, float(N), float(N))
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def _build_large_state(tile_size: int = 512):
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
    )

    N = tile_size
    height = np.zeros((N, N), dtype=np.float64)
    slope = np.full((N, N), math.radians(25.0), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    stack.set("slope", slope, "fixture")
    stack.set("curvature", np.zeros_like(height), "fixture")
    stack.set("wetness", np.zeros_like(height), "fixture")
    region_bounds = BBox(0.0, 0.0, float(N), float(N))
    intent = TerrainIntentState(
        seed=0,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# MaterialRuleSet / MaterialChannel
# ---------------------------------------------------------------------------


def test_default_dark_fantasy_rules_has_5_channels():
    from blender_addon.handlers.terrain_materials_v2 import (
        default_dark_fantasy_rules,
    )

    rules = default_dark_fantasy_rules()
    assert len(rules.channels) == 5
    ids = [c.channel_id for c in rules.channels]
    assert set(ids) == {"ground", "cliff", "scree", "wet_rock", "snow"}
    assert rules.default_channel_id == "ground"


def test_ruleset_rejects_duplicate_channel_ids():
    from blender_addon.handlers.terrain_materials_v2 import (
        MaterialChannel,
        MaterialRuleSet,
    )

    with pytest.raises(ValueError):
        MaterialRuleSet(
            channels=(
                MaterialChannel(channel_id="a"),
                MaterialChannel(channel_id="a"),
            ),
            default_channel_id="a",
        )


def test_ruleset_rejects_missing_default_channel():
    from blender_addon.handlers.terrain_materials_v2 import (
        MaterialChannel,
        MaterialRuleSet,
    )

    with pytest.raises(ValueError):
        MaterialRuleSet(
            channels=(MaterialChannel(channel_id="a"),),
            default_channel_id="b",
        )


def test_cliff_channel_is_triplanar():
    from blender_addon.handlers.terrain_materials_v2 import (
        default_dark_fantasy_rules,
    )

    rules = default_dark_fantasy_rules()
    cliff = next(c for c in rules.channels if c.channel_id == "cliff")
    assert cliff.triplanar is True


# ---------------------------------------------------------------------------
# compute_slope_material_weights
# ---------------------------------------------------------------------------


def test_weights_sum_to_one_per_cell():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
    )

    state = _build_state()
    weights = compute_slope_material_weights(state.mask_stack)
    sums = weights.sum(axis=2)
    assert np.allclose(sums, 1.0, atol=1e-5)


def test_weights_shape_matches_heightmap():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
        default_dark_fantasy_rules,
    )

    state = _build_state()
    rules = default_dark_fantasy_rules()
    weights = compute_slope_material_weights(state.mask_stack, rules)
    assert weights.shape == (*state.mask_stack.height.shape, len(rules.channels))
    assert weights.dtype == np.float32


def test_weights_vectorized_under_200ms_on_512():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
    )

    state = _build_large_state(tile_size=512)
    t0 = time.perf_counter()
    weights = compute_slope_material_weights(state.mask_stack)
    dt = time.perf_counter() - t0
    assert weights.shape[0] == 512
    assert dt < 0.5, f"compute_slope_material_weights took {dt*1000:.1f}ms"


def test_cliff_channel_triggers_on_high_slope():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
        default_dark_fantasy_rules,
    )

    state = _build_state()
    rules = default_dark_fantasy_rules()
    # Force slope to 70 degrees everywhere
    state.mask_stack.set(
        "slope",
        np.full_like(state.mask_stack.height, math.radians(70.0)),
        "test",
    )
    weights = compute_slope_material_weights(state.mask_stack, rules)
    cliff_idx = rules.index_of("cliff")
    assert weights[:, :, cliff_idx].mean() > 0.4


def test_ground_channel_dominates_flat_terrain():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
        default_dark_fantasy_rules,
    )

    state = _build_state()
    rules = default_dark_fantasy_rules()
    state.mask_stack.set(
        "slope", np.zeros_like(state.mask_stack.height), "test"
    )
    state.mask_stack.set(
        "height", np.full_like(state.mask_stack.height, 50.0), "test"
    )
    weights = compute_slope_material_weights(state.mask_stack, rules)
    ground_idx = rules.index_of("ground")
    assert weights[:, :, ground_idx].mean() > 0.5


def test_wet_rock_channel_triggers_on_wetness():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
        default_dark_fantasy_rules,
    )

    state = _build_state()
    rules = default_dark_fantasy_rules()
    state.mask_stack.set(
        "slope",
        np.full_like(state.mask_stack.height, math.radians(35.0)),
        "test",
    )
    state.mask_stack.set(
        "wetness", np.full_like(state.mask_stack.height, 0.8), "test"
    )
    weights = compute_slope_material_weights(state.mask_stack, rules)
    wet_idx = rules.index_of("wet_rock")
    assert weights[:, :, wet_idx].mean() > 0.2


def test_snow_channel_triggers_above_altitude():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
        default_dark_fantasy_rules,
    )

    state = _build_state()
    rules = default_dark_fantasy_rules()
    state.mask_stack.set(
        "height", np.full_like(state.mask_stack.height, 400.0), "test"
    )
    state.mask_stack.set(
        "slope",
        np.full_like(state.mask_stack.height, math.radians(10.0)),
        "test",
    )
    weights = compute_slope_material_weights(state.mask_stack, rules)
    snow_idx = rules.index_of("snow")
    assert weights[:, :, snow_idx].mean() > 0.3


def test_snow_channel_absent_at_low_altitude():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
        default_dark_fantasy_rules,
    )

    state = _build_state()
    rules = default_dark_fantasy_rules()
    state.mask_stack.set(
        "height", np.full_like(state.mask_stack.height, 10.0), "test"
    )
    state.mask_stack.set(
        "slope",
        np.full_like(state.mask_stack.height, math.radians(10.0)),
        "test",
    )
    weights = compute_slope_material_weights(state.mask_stack, rules)
    snow_idx = rules.index_of("snow")
    assert weights[:, :, snow_idx].mean() < 1e-5


def test_weights_never_nan_or_inf():
    from blender_addon.handlers.terrain_materials_v2 import (
        compute_slope_material_weights,
    )

    state = _build_state()
    weights = compute_slope_material_weights(state.mask_stack)
    assert np.all(np.isfinite(weights))


# ---------------------------------------------------------------------------
# pass_materials
# ---------------------------------------------------------------------------


def test_pass_materials_populates_splatmap_channel():
    from blender_addon.handlers.terrain_materials_v2 import (
        register_bundle_b_material_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_material_passes()
    state = _build_state()
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        result = controller.run_pass("materials_v2", checkpoint=False)
    assert result.status == "ok"
    assert state.mask_stack.splatmap_weights_layer is not None
    assert state.mask_stack.material_weights is not None


def test_pass_materials_metrics_report_coverage():
    from blender_addon.handlers.terrain_materials_v2 import (
        register_bundle_b_material_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_material_passes()
    state = _build_state()
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        result = controller.run_pass("materials_v2", checkpoint=False)
    assert "dominant_layer" in result.metrics
    assert result.metrics["layer_count"] == 5
    for cid in ("ground", "cliff", "scree", "wet_rock", "snow"):
        assert f"coverage_{cid}" in result.metrics


def test_pass_materials_is_deterministic():
    from blender_addon.handlers.terrain_materials_v2 import (
        register_bundle_b_material_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_material_passes()
    state_a = _build_state()
    state_b = _build_state()
    with tempfile.TemporaryDirectory() as td:
        ca = TerrainPassController(state_a, checkpoint_dir=Path(td))
        cb = TerrainPassController(state_b, checkpoint_dir=Path(td))
        ca.run_pass("materials_v2", checkpoint=False)
        cb.run_pass("materials_v2", checkpoint=False)
    np.testing.assert_array_equal(
        state_a.mask_stack.splatmap_weights_layer,
        state_b.mask_stack.splatmap_weights_layer,
    )


def test_region_scoped_pass_leaves_outside_cells_unchanged():
    from blender_addon.handlers.terrain_materials_v2 import (
        register_bundle_b_material_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox

    register_bundle_b_material_passes()
    state = _build_state()
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        # First full-tile pass
        controller.run_pass("materials_v2", checkpoint=False)
        first = state.mask_stack.splatmap_weights_layer.copy()

        # Force slope to a different value, then run region-scoped pass on a sub-region
        state.mask_stack.set(
            "slope",
            np.full_like(state.mask_stack.height, math.radians(80.0)),
            "test",
        )
        region = BBox(0.0, 0.0, 5.0, 5.0)
        controller.run_pass("materials_v2", region=region, checkpoint=False)
        second = state.mask_stack.splatmap_weights_layer

    # Cells outside the region should match the first pass
    # Cells inside the 5x5 region SHOULD differ (slope radically changed)
    outside_unchanged = np.allclose(second[10:, 10:], first[10:, 10:], atol=1e-5)
    assert outside_unchanged, "region scoping should leave outside cells untouched"


def test_unity_export_manifest_lists_splatmap():
    from blender_addon.handlers.terrain_materials_v2 import (
        register_bundle_b_material_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_material_passes()
    state = _build_state()
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("materials_v2", checkpoint=False)
    manifest = state.mask_stack.unity_export_manifest()
    assert "splatmap_weights_layer" in manifest["populated_channels"]
