"""Bundle A supplements — 25+ regression tests for Addendum 1.B.1 / 2.A / 3.

Covers:
- theoretical_max_amplitude formula
- WorldHeightTransform round-trip for negative elevations
- ErosionStrategy enum
- SectorOrigin immutability
- TileTransform.to_dict schema
- TerrainMaskStack backward compat (tile_size=0) + new contract (>0)
- New mask channels (sediment_accumulation_at_base, pool_deepening_delta)
- compute_erosion_params_for_world_range
- 12-step world orchestrator
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blender_addon.handlers.terrain_semantics import (
    BBox,
    ErosionStrategy,
    SectorOrigin,
    TerrainIntentState,
    TerrainMaskStack,
    WorldHeightTransform,
)
from blender_addon.handlers.terrain_world_math import (
    TileTransform,
    compute_erosion_params_for_world_range,
    theoretical_max_amplitude,
)
from blender_addon.handlers.terrain_twelve_step import run_twelve_step_world_terrain


# ---------------------------------------------------------------------------
# theoretical_max_amplitude
# ---------------------------------------------------------------------------


def test_theoretical_max_amplitude_persistence_one():
    assert theoretical_max_amplitude(1.0, 8) == 8.0


def test_theoretical_max_amplitude_half_four_octaves():
    # Sum of 1 + 0.5 + 0.25 + 0.125 = 1.875; formula = (1-0.5^4)/(1-0.5) = 1.875
    assert math.isclose(theoretical_max_amplitude(0.5, 4), 1.875, rel_tol=1e-9)


def test_theoretical_max_amplitude_matches_naive_sum():
    for persistence in (0.3, 0.5, 0.7, 0.9):
        for octaves in (1, 2, 4, 6, 8):
            naive = sum(persistence ** k for k in range(octaves))
            assert math.isclose(
                theoretical_max_amplitude(persistence, octaves),
                naive,
                rel_tol=1e-9,
            ), f"mismatch at persistence={persistence}, octaves={octaves}"


def test_theoretical_max_amplitude_zero_octaves():
    assert theoretical_max_amplitude(0.5, 0) == 0.0


# ---------------------------------------------------------------------------
# WorldHeightTransform
# ---------------------------------------------------------------------------


def test_world_height_transform_roundtrip_negative_range():
    wht = WorldHeightTransform(world_min=-40.0, world_max=20.0)
    heights = np.array([-40.0, -30.0, -10.0, 0.0, 10.0, 20.0])
    normalized = wht.to_normalized(heights)
    assert normalized.min() >= 0.0
    assert normalized.max() <= 1.0
    restored = wht.from_normalized(normalized)
    np.testing.assert_allclose(restored, heights, atol=1e-9)


def test_world_height_transform_preserves_negatives():
    wht = WorldHeightTransform(world_min=-50.0, world_max=50.0)
    # A value at world_min = -50 should round trip to exactly -50
    restored = wht.from_normalized(wht.to_normalized(np.array([-50.0])))
    assert float(restored[0]) == -50.0


def test_world_height_transform_range_computed_from_min_max():
    wht = WorldHeightTransform(world_min=-40.0, world_max=20.0)
    assert wht.world_range == 60.0


def test_world_height_transform_degenerate_range_safe():
    # Zero range should not divide by zero; adapter stays usable
    wht = WorldHeightTransform(world_min=5.0, world_max=5.0)
    assert wht.world_range != 0.0
    result = wht.to_normalized(np.array([5.0]))
    assert np.all(np.isfinite(result))


# ---------------------------------------------------------------------------
# ErosionStrategy
# ---------------------------------------------------------------------------


def test_erosion_strategy_has_three_values():
    values = {e.value for e in ErosionStrategy}
    assert values == {"exact", "tiled_padded", "tiled_distributed_halo"}


def test_erosion_strategy_lookups():
    assert ErosionStrategy("exact") is ErosionStrategy.EXACT
    assert ErosionStrategy("tiled_padded") is ErosionStrategy.TILED_PADDED
    assert ErosionStrategy("tiled_distributed_halo") is ErosionStrategy.TILED_DISTRIBUTED_HALO


# ---------------------------------------------------------------------------
# SectorOrigin
# ---------------------------------------------------------------------------


def test_sector_origin_is_immutable():
    origin = SectorOrigin(name="sector_0_0", world_x_m=0.0, world_y_m=0.0)
    with pytest.raises((AttributeError, TypeError)):
        origin.world_x_m = 999.0  # type: ignore[misc]


def test_sector_origin_fields():
    origin = SectorOrigin(name="sector_1_0", world_x_m=1000.0, world_y_m=0.0)
    assert origin.name == "sector_1_0"
    assert origin.world_x_m == 1000.0
    assert origin.world_y_m == 0.0


# ---------------------------------------------------------------------------
# TileTransform
# ---------------------------------------------------------------------------


def test_tile_transform_to_dict_schema():
    tt = TileTransform(
        origin_world=(0.0, 0.0, -5.0),
        min_corner_world=(0.0, 0.0, -5.0),
        max_corner_world=(16.0, 16.0, 25.0),
        tile_coords=(0, 0),
        tile_size_world=16.0,
        convention="object_origin_at_min_corner",
    )
    d = tt.to_dict()
    assert set(d.keys()) == {
        "origin_world",
        "min_corner_world",
        "max_corner_world",
        "tile_coords",
        "tile_size_world",
        "convention",
    }
    assert d["tile_coords"] == [0, 0]
    assert d["tile_size_world"] == 16.0
    assert d["convention"] == "object_origin_at_min_corner"
    assert d["origin_world"] == [0.0, 0.0, -5.0]


def test_tile_transform_to_dict_values_are_plain_python():
    tt = TileTransform(
        origin_world=(np.float64(1.0), 2.0, 3.0),
        min_corner_world=(1.0, 2.0, 3.0),
        max_corner_world=(17.0, 18.0, 23.0),
        tile_coords=(1, 2),
        tile_size_world=16.0,
    )
    d = tt.to_dict()
    # All numerics should be plain floats/ints (no numpy types)
    for v in d["origin_world"]:
        assert isinstance(v, float)
    for v in d["tile_coords"]:
        assert isinstance(v, int)


# ---------------------------------------------------------------------------
# TerrainMaskStack backward compat + new contract
# ---------------------------------------------------------------------------


def test_mask_stack_tile_size_zero_still_constructs():
    # Legacy: tile_size=0 means "not a tile"; any shape allowed.
    height = np.zeros((10, 7), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=0,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    assert stack.height.shape == (10, 7)


def test_mask_stack_tile_size_positive_new_contract():
    ts = 32
    height = np.zeros((ts + 1, ts + 1), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    assert stack.height.shape == (ts + 1, ts + 1)


def test_mask_stack_tile_size_legacy_shape_still_accepted():
    # Legacy shape == (tile_size, tile_size). Backward compat path.
    ts = 16
    height = np.zeros((ts, ts), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    assert stack.height.shape == (ts, ts)


def test_mask_stack_tile_size_wrong_shape_rejected():
    ts = 32
    bad = np.zeros((10, 10), dtype=np.float64)
    with pytest.raises(ValueError, match="tile resolution contract"):
        TerrainMaskStack(
            tile_size=ts,
            cell_size=1.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            tile_x=0,
            tile_y=0,
            height=bad,
        )


def test_mask_stack_set_sediment_accumulation_at_base():
    ts = 32
    height = np.zeros((ts + 1, ts + 1), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    sediment = np.full_like(height, 0.25)
    stack.set("sediment_accumulation_at_base", sediment, pass_name="erosion_v2")
    out = stack.get("sediment_accumulation_at_base")
    assert out is not None
    np.testing.assert_array_equal(out, sediment)
    assert stack.populated_by_pass["sediment_accumulation_at_base"] == "erosion_v2"


def test_mask_stack_set_pool_deepening_delta():
    ts = 32
    height = np.zeros((ts + 1, ts + 1), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    delta = np.full_like(height, -0.1)
    stack.set("pool_deepening_delta", delta, pass_name="erosion_v2")
    out = stack.get("pool_deepening_delta")
    assert out is not None
    np.testing.assert_array_equal(out, delta)


def test_mask_stack_compute_hash_covers_new_channels():
    ts = 32
    height = np.zeros((ts + 1, ts + 1), dtype=np.float64)
    stack_a = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.copy(),
    )
    stack_b = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.copy(),
    )
    stack_b.set("sediment_accumulation_at_base", np.ones_like(height), "erosion_v2")
    assert stack_a.compute_hash() != stack_b.compute_hash()


def test_mask_stack_compute_hash_covers_pool_deepening_delta():
    ts = 32
    height = np.zeros((ts + 1, ts + 1), dtype=np.float64)
    stack_a = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.copy(),
    )
    stack_b = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.copy(),
    )
    stack_b.set("pool_deepening_delta", np.full_like(height, 0.7), "erosion_v2")
    assert stack_a.compute_hash() != stack_b.compute_hash()


# ---------------------------------------------------------------------------
# compute_erosion_params_for_world_range
# ---------------------------------------------------------------------------


def test_compute_erosion_params_scales_min_slope_linearly():
    params_20 = compute_erosion_params_for_world_range(20.0)
    params_40 = compute_erosion_params_for_world_range(40.0)
    assert math.isclose(params_20["min_slope"], 0.01 * 20.0)
    assert math.isclose(params_40["min_slope"], 0.01 * 40.0)


def test_compute_erosion_params_preserves_capacity():
    params = compute_erosion_params_for_world_range(100.0, base_capacity=4.0)
    assert params["capacity"] == 4.0


def test_compute_erosion_params_zero_range_safe():
    params = compute_erosion_params_for_world_range(0.0)
    assert params["min_slope"] == 0.01  # falls back to base_min_slope
    assert params["capacity"] == 4.0


# ---------------------------------------------------------------------------
# 12-step orchestration
# ---------------------------------------------------------------------------


def _make_intent(seed: int = 1234, tile_size: int = 16) -> TerrainIntentState:
    return TerrainIntentState(
        seed=seed,
        region_bounds=BBox(0.0, 0.0, 200.0, 200.0),
        tile_size=tile_size,
        cell_size=1.0,
    )


def test_twelve_step_returns_expected_keys():
    result = run_twelve_step_world_terrain(_make_intent(), tile_grid_x=2, tile_grid_y=2)
    required = {
        "tile_stacks",
        "tile_transforms",
        "world_heightmap",
        "world_flow_map",
        "cliff_candidates",
        "cave_candidates",
        "waterfall_lip_candidates",
        "seam_report",
        "sequence",
        "metadata",
    }
    assert required.issubset(set(result.keys()))


def test_twelve_step_produces_four_tiles():
    result = run_twelve_step_world_terrain(_make_intent(), tile_grid_x=2, tile_grid_y=2)
    assert set(result["tile_stacks"].keys()) == {(0, 0), (1, 0), (0, 1), (1, 1)}
    assert set(result["tile_transforms"].keys()) == {(0, 0), (1, 0), (0, 1), (1, 1)}


def test_twelve_step_sequence_exact_order():
    result = run_twelve_step_world_terrain(_make_intent(), tile_grid_x=2, tile_grid_y=2)
    seq = result["sequence"]
    # 12 steps; stubs still advance the sequence counter
    assert len(seq) == 12
    assert seq[0].startswith("1_")
    assert seq[-1].startswith("12_")
    # Erosion before any per-tile extract
    erode_idx = next(i for i, s in enumerate(seq) if "erode" in s)
    extract_idx = next(i for i, s in enumerate(seq) if "per_tile" in s)
    assert erode_idx < extract_idx


def test_twelve_step_per_tile_stacks_have_correct_coords():
    result = run_twelve_step_world_terrain(_make_intent(), tile_grid_x=2, tile_grid_y=2)
    for (tx, ty), stack in result["tile_stacks"].items():
        assert stack.tile_x == tx
        assert stack.tile_y == ty
        assert stack.height.shape == (16 + 1, 16 + 1)


def test_twelve_step_seam_report_passes():
    result = run_twelve_step_world_terrain(_make_intent(), tile_grid_x=2, tile_grid_y=2)
    seam = result["seam_report"]
    assert seam["seam_ok"] is True, f"seam report issues: {seam.get('issues')}"


def test_twelve_step_tile_transforms_non_overlapping():
    result = run_twelve_step_world_terrain(_make_intent(), tile_grid_x=2, tile_grid_y=2)
    t00 = result["tile_transforms"][(0, 0)]
    t10 = result["tile_transforms"][(1, 0)]
    # east neighbor's min x equals west neighbor's max x (shared edge)
    assert math.isclose(t00.max_corner_world[0], t10.min_corner_world[0])


def test_twelve_step_deterministic_same_seed():
    r1 = run_twelve_step_world_terrain(_make_intent(seed=42), tile_grid_x=2, tile_grid_y=2)
    r2 = run_twelve_step_world_terrain(_make_intent(seed=42), tile_grid_x=2, tile_grid_y=2)
    np.testing.assert_array_equal(r1["world_heightmap"], r2["world_heightmap"])


def test_twelve_step_rejects_zero_grid():
    with pytest.raises(ValueError):
        run_twelve_step_world_terrain(_make_intent(), tile_grid_x=0, tile_grid_y=1)
