"""Bundle E — Scatter Intelligence tests.

Covers:
    - compute_viability filters by slope / altitude / required_masks
    - place_assets_by_zone is deterministic and respects viability
    - cluster_rocks_for_* concentrate around hero candidate cells
    - validate_asset_density_and_overlap flags over-dense scatter
    - pass_scatter_intelligent populates tree_instance_points (N, 5)
      and detail_density
    - Region scoping + protected zones zero out placements there
    - Poisson disk respects cluster_radius_m
    - AssetRole round-trip via classify_asset_role
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from blender_addon.handlers.terrain_assets import (
    AssetContextRule,
    AssetRole,
    build_asset_context_rules,
    classify_asset_role,
    cluster_rocks_for_cliffs,
    cluster_rocks_for_waterfalls,
    compute_viability,
    place_assets_by_zone,
    register_bundle_e_passes,
    scatter_debris_for_caves,
    validate_asset_density_and_overlap,
)
from blender_addon.handlers.terrain_pipeline import TerrainPassController
from blender_addon.handlers.terrain_semantics import (
    BBox,
    ProtectedZoneSpec,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    TerrainSceneRead,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_stack(tile_size: int = 32, seed: int = 0) -> TerrainMaskStack:
    rng = np.random.default_rng(seed)
    height = (rng.random((tile_size + 1, tile_size + 1)).astype(np.float64) * 100.0)
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    # Populate baseline masks so viability logic has signals
    h = stack.height.shape
    stack.set("slope", np.full(h, math.radians(10.0), dtype=np.float32), "test_fixture")
    stack.set("wetness", np.full(h, 0.5, dtype=np.float32), "test_fixture")
    return stack


def _make_intent(stack: TerrainMaskStack, seed: int = 1234, protected_zones=()):
    region_bounds = BBox(
        0.0, 0.0,
        float(stack.tile_size) * stack.cell_size,
        float(stack.tile_size) * stack.cell_size,
    )
    scene_read = TerrainSceneRead(
        timestamp=0.0,
        major_landforms=("flatland",),
        focal_point=(0.0, 0.0, 0.0),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=(),
        protected_zones_in_region=tuple(z.zone_id for z in protected_zones),
        edit_scope=region_bounds,
        success_criteria=("scatter_test",),
        reviewer="pytest",
    )
    return TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=stack.tile_size,
        cell_size=stack.cell_size,
        protected_zones=tuple(protected_zones),
        scene_read=scene_read,
    )


@pytest.fixture
def stack():
    return _make_stack()


@pytest.fixture
def intent(stack):
    return _make_intent(stack)


@pytest.fixture(autouse=True)
def _register():
    TerrainPassController.clear_registry()
    register_bundle_e_passes()
    yield
    TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# compute_viability
# ---------------------------------------------------------------------------


def test_compute_viability_zeros_wrong_slope(stack):
    # All cells have slope = 10 deg; require 30..60 deg => zero
    rule = AssetContextRule(
        asset_id="cliff_only",
        role=AssetRole.ROCK_CLIFF_BASE,
        min_slope_rad=math.radians(30.0),
        max_slope_rad=math.radians(60.0),
    )
    viab = compute_viability(rule, stack)
    assert viab.shape == stack.height.shape
    assert np.all(viab == 0.0)


def test_compute_viability_zeros_wrong_altitude(stack):
    # Stack altitudes are [0, 100]; require 1000..2000 => zero
    rule = AssetContextRule(
        asset_id="highland",
        role=AssetRole.VEGETATION_LARGE,
        min_altitude_m=1000.0,
        max_altitude_m=2000.0,
    )
    viab = compute_viability(rule, stack)
    assert np.all(viab == 0.0)


def test_compute_viability_respects_required_masks(stack):
    # No cliff_candidate channel set at all → viability must be zero
    rule = AssetContextRule(
        asset_id="cliff_boulder",
        role=AssetRole.ROCK_CLIFF_BASE,
        required_masks=("cliff_candidate",),
    )
    viab = compute_viability(rule, stack)
    assert np.all(viab == 0.0)

    # Populate half of the map with cliff_candidate => that half viable
    h, w = stack.height.shape
    cliff = np.zeros((h, w), dtype=np.float32)
    cliff[:, w // 2 :] = 1.0
    stack.set("cliff_candidate", cliff, "test")
    viab2 = compute_viability(rule, stack)
    assert np.all(viab2[:, : w // 2] == 0.0)
    assert np.any(viab2[:, w // 2 :] > 0.0)


def test_compute_viability_respects_forbidden_masks(stack):
    h, w = stack.height.shape
    hero_excl = np.zeros((h, w), dtype=np.float32)
    hero_excl[: h // 2, :] = 1.0
    stack.set("hero_exclusion", hero_excl, "test")
    rule = AssetContextRule(
        asset_id="grass_clump",
        role=AssetRole.GROUND_COVER,
        max_slope_rad=math.radians(25.0),
        forbidden_masks=("hero_exclusion",),
    )
    viab = compute_viability(rule, stack)
    assert np.all(viab[: h // 2, :] == 0.0)
    assert np.any(viab[h // 2 :, :] > 0.0)


# ---------------------------------------------------------------------------
# place_assets_by_zone
# ---------------------------------------------------------------------------


def test_place_assets_by_zone_deterministic(stack, intent):
    rules = [
        AssetContextRule(
            asset_id="grass_clump",
            role=AssetRole.GROUND_COVER,
            max_slope_rad=math.radians(25.0),
            cluster_radius_m=1.5,
        )
    ]
    a = place_assets_by_zone(stack, intent, rules)
    b = place_assets_by_zone(stack, intent, rules)
    assert a == b
    assert len(a["grass_clump"]) > 0


def test_place_assets_by_zone_only_viable_cells(stack, intent):
    # Restrict by altitude window: only cells with height in [40, 60]
    rule = AssetContextRule(
        asset_id="bush",
        role=AssetRole.VEGETATION_SMALL,
        min_altitude_m=40.0,
        max_altitude_m=60.0,
        max_slope_rad=math.radians(30.0),
        cluster_radius_m=1.2,
    )
    placements = place_assets_by_zone(stack, intent, [rule])
    for (x, y, z) in placements["bush"]:
        assert 40.0 <= z <= 60.0


def test_place_assets_uses_height_channel_for_z(stack, intent):
    """Z value MUST come from stack.height — not a re-sampled scene function."""
    # Overwrite height with a constant 42m to prove z reads from channel.
    stack.height[:] = 42.0
    rule = AssetContextRule(
        asset_id="grass_clump",
        role=AssetRole.GROUND_COVER,
        max_slope_rad=math.radians(25.0),
        cluster_radius_m=1.5,
    )
    placements = place_assets_by_zone(stack, intent, [rule])
    assert len(placements["grass_clump"]) > 0
    for (_x, _y, z) in placements["grass_clump"]:
        assert z == pytest.approx(42.0)


def test_poisson_disk_honors_cluster_radius(stack, intent):
    rule = AssetContextRule(
        asset_id="oak_tree",
        role=AssetRole.VEGETATION_LARGE,
        max_slope_rad=math.radians(35.0),
        cluster_radius_m=3.5,
    )
    placements = place_assets_by_zone(stack, intent, [rule])
    pts = placements["oak_tree"]
    assert len(pts) >= 2
    arr = np.array([(p[0], p[1]) for p in pts])
    diffs = arr[:, None, :] - arr[None, :, :]
    dist_sq = (diffs ** 2).sum(-1)
    np.fill_diagonal(dist_sq, np.inf)
    # All pair distances >= cluster_radius_m (with tiny epsilon for fp)
    assert dist_sq.min() >= (3.5 ** 2) - 1e-6


def test_region_scoped_scatter_leaves_outside_empty(stack, intent):
    rule = AssetContextRule(
        asset_id="grass_clump",
        role=AssetRole.GROUND_COVER,
        max_slope_rad=math.radians(25.0),
        cluster_radius_m=1.0,
    )
    region = BBox(5.0, 5.0, 12.0, 12.0)
    placements = place_assets_by_zone(stack, intent, [rule], region=region)
    for (x, y, _z) in placements["grass_clump"]:
        assert 5.0 <= x <= 12.0
        assert 5.0 <= y <= 12.0
    assert len(placements["grass_clump"]) > 0


def test_protected_zones_zero_placements(stack):
    # Protect the whole region — no placements should occur.
    full_bounds = BBox(
        0.0, 0.0,
        stack.tile_size * stack.cell_size,
        stack.tile_size * stack.cell_size,
    )
    zone = ProtectedZoneSpec(
        zone_id="noscatter",
        bounds=full_bounds,
        kind="hero_mesh",
        forbidden_mutations=frozenset({"scatter_intelligent"}),
    )
    intent = _make_intent(stack, protected_zones=(zone,))
    rules = build_asset_context_rules()
    h, w = stack.height.shape
    protected = np.ones((h, w), dtype=bool)
    placements = place_assets_by_zone(stack, intent, rules, protected=protected)
    total = sum(len(v) for v in placements.values())
    assert total == 0


# ---------------------------------------------------------------------------
# Cluster helpers
# ---------------------------------------------------------------------------


def test_cluster_rocks_for_cliffs_concentrates_near_cliff_cells(stack, intent):
    h, w = stack.height.shape
    cliff = np.zeros((h, w), dtype=np.float32)
    cliff[h // 2, w // 2] = 1.0
    points = cluster_rocks_for_cliffs(stack, cliff, intent)
    assert len(points) >= 3
    cx = stack.world_origin_x + (w // 2 + 0.5) * stack.cell_size
    cy = stack.world_origin_y + (h // 2 + 0.5) * stack.cell_size
    for (x, y, _z) in points:
        assert abs(x - cx) <= 5.0
        assert abs(y - cy) <= 5.0


def test_cluster_rocks_for_waterfalls_concentrates_near_lip(stack, intent):
    h, w = stack.height.shape
    lip = np.zeros((h, w), dtype=np.float32)
    lip[8, 8] = 1.0
    points = cluster_rocks_for_waterfalls(stack, lip, intent)
    assert len(points) >= 3
    cx = stack.world_origin_x + 8.5 * stack.cell_size
    cy = stack.world_origin_y + 8.5 * stack.cell_size
    for (x, y, _z) in points:
        assert math.hypot(x - cx, y - cy) <= 5.0


def test_scatter_debris_for_caves_clusters_near_mouth(stack, intent):
    h, w = stack.height.shape
    cave = np.zeros((h, w), dtype=np.float32)
    cave[4, 4] = 1.0
    points = scatter_debris_for_caves(stack, cave, intent)
    assert len(points) >= 3


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_flags_overdense(stack):
    # Dense cluster of 100 grass points in a 1m^2 area.
    pts = [(float(i) * 0.05, 0.0, 0.0) for i in range(100)]
    placements = {"grass_clump": pts}
    rules = [
        AssetContextRule(
            asset_id="grass_clump",
            role=AssetRole.GROUND_COVER,
            cluster_radius_m=0.5,
        )
    ]
    issues = validate_asset_density_and_overlap(
        placements, rules, max_density_per_m2=1.0, area_m2=10.0,
    )
    codes = {i.code for i in issues}
    assert "SCATTER_OVERDENSE" in codes or "SCATTER_OVERLAP" in codes


# ---------------------------------------------------------------------------
# classify_asset_role
# ---------------------------------------------------------------------------


def test_asset_role_roundtrip():
    assert classify_asset_role("oak_tree") == AssetRole.VEGETATION_LARGE
    assert classify_asset_role("grass_clump") == AssetRole.GROUND_COVER
    assert classify_asset_role("cliff_boulder") == AssetRole.ROCK_CLIFF_BASE
    assert classify_asset_role("cave_rubble") == AssetRole.ROCK_CAVE_DEBRIS
    assert classify_asset_role("ambient_wind") == AssetRole.AUDIO_SOURCE
    # Unknown → heuristic: "mystery_tree" matches "tree"
    assert classify_asset_role("mystery_tree") == AssetRole.VEGETATION_LARGE
    # Override mapping
    override = {"oak_tree": AssetRole.HERO_PROP}
    assert classify_asset_role("oak_tree", overrides=override) == AssetRole.HERO_PROP


# ---------------------------------------------------------------------------
# pass_scatter_intelligent
# ---------------------------------------------------------------------------


def test_pass_populates_tree_instance_points(stack, intent):
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        result = controller.run_pass("scatter_intelligent", checkpoint=False)
    assert result.status in ("ok", "warning")
    tp = state.mask_stack.tree_instance_points
    assert tp is not None
    assert tp.ndim == 2
    assert tp.shape[1] == 5  # Unity contract: (x, y, z, rot, prototype_id)
    assert tp.shape[0] > 0


def test_pass_populates_detail_density(stack, intent):
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("scatter_intelligent", checkpoint=False)
    detail = state.mask_stack.detail_density
    assert detail is not None
    assert isinstance(detail, dict)
    assert len(detail) >= 1
    for name, arr in detail.items():
        assert arr.shape == state.mask_stack.height.shape
        assert arr.dtype == np.float32


def test_pass_preserves_existing_detail_density(stack, intent):
    sentinel = np.full(stack.height.shape, 0.5, dtype=np.float32)
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    state.mask_stack.detail_density = {"canopy": sentinel.copy()}
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("scatter_intelligent", checkpoint=False)
    detail = state.mask_stack.detail_density
    assert detail is not None
    np.testing.assert_array_equal(detail["canopy"], sentinel)


def test_scatter_registration_declares_detail_density_output():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    definition = TerrainPassController.get_pass("scatter_intelligent")
    assert "detail_density" in definition.produces_channels


def test_pass_unity_ready_shape(stack, intent):
    """Explicit Unity contract check: tree_instance_points is (N, 5)."""
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("scatter_intelligent", checkpoint=False)
    tp = state.mask_stack.tree_instance_points
    assert tp.shape[1] == 5
    # All rotations in valid range
    assert np.all(tp[:, 3] >= 0.0)
    assert np.all(tp[:, 3] <= 2.0 * math.pi + 1e-6)
    # Prototype IDs are non-negative integers-as-float
    assert np.all(tp[:, 4] >= 0.0)
