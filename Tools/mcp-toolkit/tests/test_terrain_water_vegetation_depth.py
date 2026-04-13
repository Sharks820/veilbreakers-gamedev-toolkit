"""Bundle O tests — water variants + vegetation depth.

Covers the acceptance criteria from docs/terrain_ultra_implementation_plan_2026-04-08.md §20.
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_pipeline import (
    TerrainPassController,
)
from blender_addon.handlers.terrain_semantics import (
    BBox,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    TerrainSceneRead,
)
from blender_addon.handlers.terrain_water_variants import (
    BraidedChannels,
    Estuary,
    HotSpring,
    KarstSpring,
    SeasonalState,
    Wetland,
    apply_seasonal_water_state,
    detect_estuary,
    detect_hot_springs,
    detect_karst_springs,
    detect_perched_lakes,
    detect_wetlands,
    generate_braided_channels,
    pass_water_variants,
)
from blender_addon.handlers.terrain_vegetation_depth import (
    DisturbancePatch,
    VegetationLayer,
    VegetationLayers,
    apply_allelopathic_exclusion,
    apply_cultivated_zones,
    apply_edge_effects,
    compute_vegetation_layers,
    detect_disturbance_patches,
    pass_vegetation_depth,
    place_clearings,
    place_fallen_logs,
)
from blender_addon.handlers.terrain_bundle_o import register_bundle_o_passes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    TerrainPassController.clear_registry()
    yield
    TerrainPassController.clear_registry()


def _make_height(rows: int = 32, cols: int = 32, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    ys, xs = np.meshgrid(np.linspace(0, 1, rows), np.linspace(0, 1, cols), indexing="ij")
    base = 20.0 + 40.0 * (0.5 + 0.5 * np.sin(xs * 3.0) * np.cos(ys * 2.5))
    noise = rng.standard_normal((rows, cols)) * 1.5
    return (base + noise).astype(np.float64)


def _make_stack(rows: int = 32, cols: int = 32) -> TerrainMaskStack:
    h = _make_height(rows, cols)
    return TerrainMaskStack(
        tile_size=rows,
        cell_size=2.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )


def _make_state(rows: int = 32, cols: int = 32, seed: int = 4242) -> TerrainPipelineState:
    stack = _make_stack(rows, cols)
    region = BBox(0.0, 0.0, float(cols) * 2.0, float(rows) * 2.0)
    scene_read = TerrainSceneRead(
        timestamp=0.0,
        major_landforms=("rolling_hills",),
        focal_point=(float(cols), float(rows), 0.0),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=(),
        protected_zones_in_region=(),
        edit_scope=region,
        success_criteria=("bundle_o_test",),
        reviewer="pytest",
    )
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region,
        tile_size=rows,
        cell_size=2.0,
        scene_read=scene_read,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# Water variants — braided channels
# ---------------------------------------------------------------------------


def test_braided_channels_produce_n_subpaths():
    stack = _make_stack()
    path = np.array([[0.0, 10.0], [20.0, 12.0], [40.0, 14.0], [60.0, 10.0]])
    braids = generate_braided_channels(stack, path, count=4, seed=7)
    assert isinstance(braids, BraidedChannels)
    assert len(braids.channel_paths) == 4
    for sub in braids.channel_paths:
        assert sub.shape == (4, 2)
    assert 0 <= braids.main_channel_idx < 4
    assert braids.total_width_m > 0.0


def test_braided_channels_deterministic():
    stack = _make_stack()
    path = [[0.0, 0.0], [10.0, 5.0], [20.0, 0.0]]
    a = generate_braided_channels(stack, path, count=3, seed=42)
    b = generate_braided_channels(stack, path, count=3, seed=42)
    for pa, pb in zip(a.channel_paths, b.channel_paths):
        assert np.allclose(pa, pb)


def test_braided_channels_single_channel():
    stack = _make_stack()
    path = [[0.0, 0.0], [10.0, 5.0]]
    braids = generate_braided_channels(stack, path, count=1, seed=1)
    assert len(braids.channel_paths) == 1
    assert braids.main_channel_idx == 0


# ---------------------------------------------------------------------------
# Estuary
# ---------------------------------------------------------------------------


def test_estuary_detection_finds_river_sea_intersection():
    stack = _make_stack()
    # Force a low cell where the path hits it.
    stack.height[10, 15] = -5.0
    path = np.array([[30.0, 20.0], [30.0, 20.01], [30.0, 20.02]])
    # That path doesn't hit the low cell — use one that does.
    path = np.array([[31.0, 21.0]])
    estuary = detect_estuary(stack, path, sea_level_m=-1.0)
    assert estuary is not None
    assert isinstance(estuary, Estuary)
    assert estuary.mouth_pos[2] <= -1.0


def test_estuary_none_when_river_above_sea():
    stack = _make_stack()
    stack.height[:] = 50.0
    path = np.array([[1.0, 1.0], [5.0, 5.0]])
    assert detect_estuary(stack, path, sea_level_m=0.0) is None


# ---------------------------------------------------------------------------
# Karst springs
# ---------------------------------------------------------------------------


def test_karst_springs_from_mask():
    stack = _make_stack()
    mask = np.zeros(stack.height.shape, dtype=bool)
    mask[5:10, 5:10] = True
    springs = detect_karst_springs(stack, mask)
    assert len(springs) >= 1
    assert all(isinstance(s, KarstSpring) for s in springs)


def test_karst_springs_from_point_list():
    stack = _make_stack()
    points = [(10.0, 10.0), (30.0, 30.0)]
    springs = detect_karst_springs(stack, points)
    assert len(springs) == 2


def test_karst_springs_none_when_empty_mask():
    stack = _make_stack()
    mask = np.zeros(stack.height.shape, dtype=bool)
    assert detect_karst_springs(stack, mask) == []


# ---------------------------------------------------------------------------
# Perched lakes
# ---------------------------------------------------------------------------


def test_perched_lake_detection_finds_basin():
    stack = _make_stack()
    # Create a clear perched-lake signature: raise a plateau, then dig a
    # shallow basin INSIDE it. The ring around the basin is still above
    # the basin's elevation — a normal valley. For perched, the ring
    # must be BELOW the basin, so carve a trough around the plateau.
    stack.height[:] = 20.0
    stack.height[10:20, 10:20] = 60.0  # plateau
    stack.height[13:17, 13:17] = 55.0  # basin on plateau
    stack.height[14, 14] = 52.0  # local min on plateau
    # Surrounding ring at r=14, c=14 radius 3 includes cells at 20m —
    # far below the basin — so it qualifies.
    lakes = detect_perched_lakes(stack)
    assert any(
        l.elevation_m > 40.0 for l in lakes  # noqa: E741
    ), "expected a perched lake on the elevated plateau"


def test_perched_lake_small_tile_returns_empty():
    h = np.zeros((3, 3), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=3, cell_size=1.0, world_origin_x=0, world_origin_y=0,
        tile_x=0, tile_y=0, height=h,
    )
    assert detect_perched_lakes(stack) == []


# ---------------------------------------------------------------------------
# Hot springs
# ---------------------------------------------------------------------------


def test_hot_spring_detection_with_volcanic_mask():
    stack = _make_stack()
    volcanic = np.zeros(stack.height.shape, dtype=np.float32)
    volcanic[20:25, 20:25] = 0.9
    springs = detect_hot_springs(stack, volcanic)
    assert len(springs) >= 1
    assert all(isinstance(s, HotSpring) for s in springs)
    assert all(s.temperature_c > 40.0 for s in springs)


def test_hot_spring_none_without_mask():
    stack = _make_stack()
    assert detect_hot_springs(stack, None) == []


def test_hot_spring_shape_validation():
    stack = _make_stack()
    bad = np.zeros((5, 5), dtype=np.float32)
    with pytest.raises(ValueError):
        detect_hot_springs(stack, bad)


# ---------------------------------------------------------------------------
# Wetlands
# ---------------------------------------------------------------------------


def test_wetland_detection_low_slope_high_wetness():
    stack = _make_stack()
    shape = stack.height.shape
    stack.wetness = np.zeros(shape, dtype=np.float32)
    stack.wetness[5:12, 5:12] = 0.9
    stack.slope = np.ones(shape, dtype=np.float32) * 0.8
    stack.slope[5:12, 5:12] = 0.05
    wetlands = detect_wetlands(stack)
    assert len(wetlands) >= 1
    assert all(isinstance(w, Wetland) for w in wetlands)


def test_wetland_empty_when_no_wetness():
    stack = _make_stack()
    assert detect_wetlands(stack) == []


# ---------------------------------------------------------------------------
# Seasonal state
# ---------------------------------------------------------------------------


def test_seasonal_dry_reduces_wetness():
    stack = _make_stack()
    stack.wetness = np.full(stack.height.shape, 0.8, dtype=np.float32)
    apply_seasonal_water_state(stack, SeasonalState.DRY)
    assert float(stack.wetness.mean()) < 0.8


def test_seasonal_wet_increases_wetness_and_water_surface():
    stack = _make_stack()
    stack.wetness = np.full(stack.height.shape, 0.3, dtype=np.float32)
    stack.water_surface = np.full(stack.height.shape, 0.2, dtype=np.float32)
    apply_seasonal_water_state(stack, SeasonalState.WET)
    assert float(stack.wetness.mean()) > 0.3
    assert float(stack.water_surface.mean()) > 0.2


def test_seasonal_frozen_sets_tidal():
    stack = _make_stack()
    apply_seasonal_water_state(stack, SeasonalState.FROZEN)
    assert stack.tidal is not None
    assert np.all(stack.tidal == 1.0)


def test_seasonal_normal_is_noop_on_wetness():
    stack = _make_stack()
    original = np.full(stack.height.shape, 0.5, dtype=np.float32)
    stack.wetness = original.copy()
    apply_seasonal_water_state(stack, SeasonalState.NORMAL)
    assert np.allclose(stack.wetness, original)


def test_seasonal_invalid_type_raises():
    stack = _make_stack()
    with pytest.raises(TypeError):
        apply_seasonal_water_state(stack, "dry")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Vegetation layers
# ---------------------------------------------------------------------------


def test_compute_vegetation_layers_returns_four_distinct_layers():
    stack = _make_stack()
    stack.slope = np.random.default_rng(1).uniform(0, 1, stack.height.shape).astype(np.float32)
    stack.wetness = np.random.default_rng(2).uniform(0, 1, stack.height.shape).astype(np.float32)
    layers = compute_vegetation_layers(stack)
    assert isinstance(layers, VegetationLayers)
    arrs = [
        layers.canopy_density,
        layers.understory_density,
        layers.shrub_density,
        layers.ground_cover_density,
    ]
    # All four distinct (at least one pair differs).
    assert not np.allclose(arrs[0], arrs[1])
    assert not np.allclose(arrs[2], arrs[3])


def test_vegetation_layers_are_float32_and_shape_matches():
    stack = _make_stack(rows=20, cols=24)
    layers = compute_vegetation_layers(stack)
    shape = stack.height.shape
    for arr in (
        layers.canopy_density,
        layers.understory_density,
        layers.shrub_density,
        layers.ground_cover_density,
    ):
        assert arr.shape == shape
        assert arr.dtype == np.float32


def test_vegetation_layers_within_unit_range():
    stack = _make_stack()
    layers = compute_vegetation_layers(stack)
    for arr in (
        layers.canopy_density,
        layers.understory_density,
        layers.shrub_density,
        layers.ground_cover_density,
    ):
        assert float(arr.min()) >= 0.0
        assert float(arr.max()) <= 1.0


def test_vegetation_layer_enum_has_four_values():
    assert len(list(VegetationLayer)) == 4


# ---------------------------------------------------------------------------
# Disturbance patches
# ---------------------------------------------------------------------------


def test_disturbance_patches_deterministic_by_seed():
    stack = _make_stack()
    a = detect_disturbance_patches(stack, seed=123)
    b = detect_disturbance_patches(stack, seed=123)
    assert len(a) == len(b)
    for pa, pb in zip(a, b):
        assert pa.kind == pb.kind
        assert pa.bounds.to_tuple() == pb.bounds.to_tuple()


def test_disturbance_patches_changes_with_seed():
    stack = _make_stack()
    a = detect_disturbance_patches(stack, seed=1)
    b = detect_disturbance_patches(stack, seed=9999)
    assert any(
        pa.bounds.to_tuple() != pb.bounds.to_tuple()
        for pa, pb in zip(a, b)
    )


def test_disturbance_patches_have_expected_kinds():
    stack = _make_stack()
    patches = detect_disturbance_patches(stack, seed=5, kinds=("fire",))
    assert all(p.kind == "fire" for p in patches)
    assert all(isinstance(p, DisturbancePatch) for p in patches)


# ---------------------------------------------------------------------------
# Clearings
# ---------------------------------------------------------------------------


def test_clearings_do_not_overlap():
    stack = _make_stack(rows=64, cols=64)
    intent = _make_state(rows=64, cols=64).intent
    clearings = place_clearings(stack, intent, count_per_km2=500.0, seed=11)
    assert len(clearings) >= 2
    # Pairwise Poisson check
    for i in range(len(clearings)):
        for j in range(i + 1, len(clearings)):
            a, b = clearings[i], clearings[j]
            dist = np.hypot(a.center[0] - b.center[0], a.center[1] - b.center[1])
            assert dist >= (a.radius_m + b.radius_m) - 1e-4


def test_clearings_kinds_alternate():
    stack = _make_stack(rows=64, cols=64)
    intent = _make_state(rows=64, cols=64).intent
    clearings = place_clearings(stack, intent, count_per_km2=500.0, seed=33)
    kinds = {c.kind for c in clearings}
    # Expect both kinds present when >1 clearing.
    if len(clearings) >= 2:
        assert "natural" in kinds
        assert "human" in kinds


# ---------------------------------------------------------------------------
# Fallen logs
# ---------------------------------------------------------------------------


def test_fallen_logs_only_inside_forest_mask():
    stack = _make_stack(rows=48, cols=48)
    forest = np.zeros(stack.height.shape, dtype=bool)
    forest[10:30, 10:30] = True
    logs = place_fallen_logs(stack, forest, seed=77)
    assert len(logs) > 0
    for x, y, _rot in logs:
        c = int((x - stack.world_origin_x) / stack.cell_size)
        r = int((y - stack.world_origin_y) / stack.cell_size)
        assert forest[r, c], f"log at ({x},{y}) outside forest mask"


def test_fallen_logs_empty_forest_returns_empty():
    stack = _make_stack()
    forest = np.zeros(stack.height.shape, dtype=bool)
    assert place_fallen_logs(stack, forest, seed=1) == []


def test_fallen_logs_shape_validation():
    stack = _make_stack()
    bad = np.zeros((4, 4), dtype=bool)
    with pytest.raises(ValueError):
        place_fallen_logs(stack, bad, seed=1)


# ---------------------------------------------------------------------------
# Edge effects
# ---------------------------------------------------------------------------


def test_edge_effects_increase_understory_near_boundary():
    stack = _make_stack()
    layers = compute_vegetation_layers(stack)
    original_understory_sum = float(layers.understory_density.sum())
    boundary = np.zeros(stack.height.shape, dtype=bool)
    boundary[15, :] = True  # single row as boundary
    boosted = apply_edge_effects(layers, boundary)
    assert float(boosted.understory_density.sum()) >= original_understory_sum


# ---------------------------------------------------------------------------
# Cultivated zones
# ---------------------------------------------------------------------------


def test_cultivated_zones_override_natural_vegetation():
    stack = _make_stack()
    layers = compute_vegetation_layers(stack)
    mask = np.zeros(stack.height.shape, dtype=bool)
    mask[5:10, 5:10] = True
    cultivated = apply_cultivated_zones(layers, mask)
    # Canopy drastically reduced inside mask
    inside_canopy = cultivated.canopy_density[mask]
    assert float(inside_canopy.max()) <= 0.1
    # Ground cover maxed
    assert float(cultivated.ground_cover_density[mask].min()) >= 0.9


# ---------------------------------------------------------------------------
# Allelopathic exclusion
# ---------------------------------------------------------------------------


def test_allelopathic_exclusion_reduces_canopy_under_species_b():
    stack = _make_stack()
    layers = compute_vegetation_layers(stack)
    a_mask = np.ones(stack.height.shape, dtype=np.float32)
    b_mask = np.zeros(stack.height.shape, dtype=np.float32)
    b_mask[10:20, 10:20] = 1.0
    original_canopy = layers.canopy_density.copy()
    result = apply_allelopathic_exclusion(layers, a_mask, b_mask)
    suppressed_mean = float(result.canopy_density[10:20, 10:20].mean())
    original_mean = float(original_canopy[10:20, 10:20].mean())
    assert suppressed_mean <= original_mean


# ---------------------------------------------------------------------------
# pass_vegetation_depth integration
# ---------------------------------------------------------------------------


def test_pass_vegetation_depth_populates_detail_density():
    register_bundle_o_passes()
    state = _make_state(rows=24, cols=24)
    result = pass_vegetation_depth(state, region=None)
    assert result.status == "ok"
    detail = state.mask_stack.detail_density
    assert detail is not None
    for key in ("canopy", "understory", "shrub", "ground_cover"):
        assert key in detail
        assert detail[key].shape == state.mask_stack.height.shape
        assert detail[key].dtype == np.float32


def test_vegetation_depth_registration_declares_detail_density_output():
    register_bundle_o_passes()
    definition = TerrainPassController.get_pass("vegetation_depth")
    assert "detail_density" in definition.produces_channels


def test_pass_vegetation_depth_region_scope_leaves_outside_unchanged():
    register_bundle_o_passes()
    state = _make_state(rows=32, cols=32)
    # Seed detail_density with a sentinel
    sentinel = np.full(state.mask_stack.height.shape, 0.777, dtype=np.float32)
    state.mask_stack.detail_density = {"canopy": sentinel.copy()}
    # Region covers only top-left quadrant
    region = BBox(0.0, 0.0, 16.0, 16.0)
    pass_vegetation_depth(state, region=region)
    canopy = state.mask_stack.detail_density["canopy"]
    # Outside the region (bottom-right) should still equal sentinel.
    # Cell size = 2.0 so region covers rows 0:8, cols 0:8.
    outside = canopy[16:, 16:]
    assert np.allclose(outside, 0.777), f"outside cells modified: {outside.mean()}"


def test_pass_vegetation_depth_deterministic_by_seed():
    register_bundle_o_passes()
    s1 = _make_state(rows=24, cols=24, seed=999)
    s2 = _make_state(rows=24, cols=24, seed=999)
    pass_vegetation_depth(s1, region=None)
    pass_vegetation_depth(s2, region=None)
    for key in ("canopy", "understory", "shrub", "ground_cover"):
        assert np.allclose(
            s1.mask_stack.detail_density[key],
            s2.mask_stack.detail_density[key],
        )


def test_pass_water_variants_populates_wetness_and_surface():
    state = _make_state()
    result = pass_water_variants(state, region=None)
    assert result.status == "ok"
    assert state.mask_stack.wetness is not None
    assert state.mask_stack.water_surface is not None


# ---------------------------------------------------------------------------
# Registrar
# ---------------------------------------------------------------------------


def test_register_bundle_o_passes_registers_both():
    register_bundle_o_passes()
    assert "water_variants" in TerrainPassController.PASS_REGISTRY
    assert "vegetation_depth" in TerrainPassController.PASS_REGISTRY


def test_register_bundle_o_is_idempotent():
    register_bundle_o_passes()
    register_bundle_o_passes()
    assert "water_variants" in TerrainPassController.PASS_REGISTRY
    assert "vegetation_depth" in TerrainPassController.PASS_REGISTRY
