"""Wave-merged terrain pipeline integration test.

Single end-to-end exercise that proves the wiring fix (bundles A–O
loaded via register_all_terrain_passes + handle_run_terrain_pass
routed through the COMMAND_HANDLERS dispatch) actually reaches code.
Runs without Blender — mask stack, intent, passes, validators, and
terrain_region_exec all operate on numpy directly.

This is intentionally a *smoke* test: it asserts the pipeline runs
without exceptions, every default pass produces its declared output
channels, and the new Tier 0 fixes (range preservation in
terrain_advanced, path_points 3D validation, Strahler ordering,
vectorized splatmap, direction-aware waterfall) behave correctly.
"""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_controller():
    """Create a fresh TerrainPassController with all bundles loaded.

    The intent carries a minimal :class:`TerrainSceneRead` so mutating
    passes (erosion, etc.) that declare ``requires_scene_read=True`` do
    not trip the orchestrator's protocol gate.
    """
    from blender_addon.handlers.terrain_master_registrar import (
        register_all_terrain_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    TerrainPassController.clear_registry()
    register_all_terrain_passes(strict=False)

    tile_size = 32
    cell_size = 2.0
    # Deterministic synthetic heightmap — gentle dome + noise
    ys = np.arange(tile_size + 1)
    xs = np.arange(tile_size + 1)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    centre = tile_size / 2.0
    dome = 20.0 * np.exp(-((xx - centre) ** 2 + (yy - centre) ** 2) / (2 * 6 ** 2))
    # world-unit heights (metres), not normalized to [0,1]
    height = (dome + 5.0 * np.sin(xx * 0.3) * np.cos(yy * 0.3)).astype(np.float64)

    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=cell_size,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    region_bounds = BBox(
        min_x=0.0,
        min_y=0.0,
        max_x=tile_size * cell_size,
        max_y=tile_size * cell_size,
    )
    scene_read = TerrainSceneRead(
        timestamp=0.0,
        major_landforms=("dome",),
        focal_point=(centre * cell_size, centre * cell_size, 0.0),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=(),
        protected_zones_in_region=(),
        edit_scope=region_bounds,
        success_criteria=("smoke_test",),
        reviewer="test_harness",
    )
    intent = TerrainIntentState(
        seed=1234,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=cell_size,
        scene_read=scene_read,
    )
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    return TerrainPassController(state)


# ---------------------------------------------------------------------------
# Fix #1 — wiring: every bundle's registrar runs
# ---------------------------------------------------------------------------


def test_wiring_bundle_a_default_pipeline_runs():
    controller = _fresh_controller()
    results = controller.run_pipeline(
        pass_sequence=[
            "macro_world",
            "structural_masks",
            "erosion",
            "validation_minimal",
        ],
        checkpoint=False,
    )
    # Cleanup the global registry for other tests
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    TerrainPassController.clear_registry()

    assert len(results) == 4
    for r in results:
        assert r.status in ("ok", "warnings"), f"{r.pass_name}: {r.status} {r.issues}"

    stack = controller.state.mask_stack
    # structural_masks populates these
    assert stack.slope is not None
    assert stack.curvature is not None
    # erosion populates these
    assert stack.erosion_amount is not None
    assert stack.deposition_amount is not None


def test_wiring_handle_run_terrain_pass_matches_direct_controller():
    """The MCP-facing handler should return the same shape as direct controller calls."""
    from blender_addon.handlers.environment import handle_run_terrain_pass
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    result = handle_run_terrain_pass(
        {
            "tile_size": 16,
            "cell_size": 2.0,
            "seed": 42,
            "terrain_type": "hills",
            "scale": 60.0,
            "pipeline": ["macro_world", "structural_masks"],
        }
    )
    TerrainPassController.clear_registry()

    assert result["ok"] is True
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 2
    assert "macro_world" in {r["pass_name"] for r in result["results"]}


# ---------------------------------------------------------------------------
# Fix #2 — terrain_advanced no longer crushes world-unit heights
# ---------------------------------------------------------------------------


def test_compute_erosion_brush_preserves_world_unit_range():
    from blender_addon.handlers.terrain_advanced import compute_erosion_brush

    # World-unit heightmap with values well above 1.0 (metres)
    hm = np.full((32, 32), 50.0, dtype=np.float64)
    hm[10:20, 10:20] = 80.0  # a raised plateau

    eroded = compute_erosion_brush(
        heightmap=hm,
        brush_center=(16.0, 16.0),
        brush_radius=5.0,
        erosion_type="hydraulic",
        iterations=2,
        strength=0.5,
        terrain_size=(32.0, 32.0),
        terrain_origin=(0.0, 0.0),
        seed=0,
    )

    # The legacy bug clamped everything to [0, 1] — any surviving pixel
    # at >1 proves the fix landed.
    assert float(eroded.max()) > 1.0, "erosion output was crushed to [0,1] — fix regressed"
    assert float(eroded.max()) <= 80.0 + 1e-6  # should not exceed source max
    assert float(eroded.min()) >= 50.0 - 1e-6  # should not collapse below source min


def test_flatten_terrain_zone_preserves_world_unit_range():
    from blender_addon.handlers.terrain_advanced import flatten_terrain_zone

    hm = np.linspace(40.0, 120.0, 32 * 32).reshape(32, 32)
    flat = flatten_terrain_zone(
        heightmap=hm,
        center_x=0.5,
        center_y=0.5,
        radius=0.25,
        target_height=75.0,
    )
    assert flat.max() > 1.0  # not crushed
    assert flat.max() <= 120.0 + 1e-6
    assert abs(float(flat[16, 16]) - 75.0) < 2.0  # near the target in the middle


# ---------------------------------------------------------------------------
# Fix #3 — splatmap is vectorized and produces valid weights
# ---------------------------------------------------------------------------


def test_compute_world_splatmap_weights_is_vectorized_and_normalized():
    import time

    from blender_addon.handlers.terrain_materials import compute_world_splatmap_weights

    rng = np.random.default_rng(0)
    hm = rng.random((128, 128)).astype(np.float64) * 30.0
    start = time.perf_counter()
    splat = compute_world_splatmap_weights(hm, cell_size=1.0)
    elapsed = time.perf_counter() - start

    # Shape contract preserved
    assert splat.shape == (128, 128, 4)
    # Every cell's channels must sum to ~1 so Unity's alphamap is valid
    totals = splat.sum(axis=-1)
    assert np.allclose(totals, 1.0, atol=1e-5)
    # Vectorized path must beat the legacy ~2s loop on this grid. We
    # give a very generous budget to avoid flakiness on slow CI.
    assert elapsed < 2.0, f"vectorized splatmap took {elapsed:.3f}s on 128²"


# ---------------------------------------------------------------------------
# Fix #4 — generate_waterfall is direction-aware
# ---------------------------------------------------------------------------


def test_generate_waterfall_direction_aware_rotation():
    from blender_addon.handlers.terrain_features import generate_waterfall

    base = generate_waterfall(height=8.0, width=3.0, num_steps=2, seed=1)
    rotated = generate_waterfall(
        height=8.0, width=3.0, num_steps=2, seed=1,
        facing_direction=(1.0, 0.0),  # flow along +X instead of -Y
    )
    assert base["vertex_count"] == rotated["vertex_count"]
    assert base["face_count"] == rotated["face_count"]

    # The pool centre in the default frame sits at negative Y. After a
    # 90° rotation to +X flow, the same centre should be at positive X,
    # Y close to zero.
    bx, by, bz = base["pool"]["center"]
    rx, ry, rz = rotated["pool"]["center"]
    assert bz == pytest.approx(rz)
    assert by < 0.0  # default: pool is behind in -Y
    assert rx > 0.0  # rotated: pool is now in +X
    assert abs(ry) < 1e-6
    # Total radial distance preserved through rotation
    assert math.isclose(math.hypot(bx, by), math.hypot(rx, ry), rel_tol=1e-9)


def test_generate_waterfall_default_matches_legacy_frame():
    """Default facing_direction=(0,-1) must be a pure identity."""
    from blender_addon.handlers.terrain_features import generate_waterfall

    result = generate_waterfall(height=5.0, num_steps=1, seed=7)
    assert result["facing_direction"] == (0.0, -1.0)
    assert result["pool"]["center"][0] == pytest.approx(0.0)
    assert result["pool"]["center"][1] < 0.0


# ---------------------------------------------------------------------------
# Fix #5 — Strahler stream ordering
# ---------------------------------------------------------------------------


def test_strahler_ordering_basic_y_shape():
    """Two order-1 tributaries merging should produce an order-2 trunk."""
    from blender_addon.handlers._water_network import (
        WaterNetwork,
        WaterNode,
        WaterSegment,
    )

    net = WaterNetwork()
    # Three nodes: two sources + one confluence + one drain
    net.nodes = {
        0: WaterNode(0, 0.0, 0.0, 100.0, "source", 1.0, 0.5),
        1: WaterNode(1, 10.0, 0.0, 100.0, "source", 1.0, 0.5),
        2: WaterNode(2, 5.0, 10.0, 80.0, "confluence", 2.0, 0.5),
        3: WaterNode(3, 5.0, 20.0, 60.0, "drain", 2.0, 0.8),
    }
    # Two tributary segments end at node 2, one trunk segment continues
    net.segments = {
        10: WaterSegment(10, 0, 2, 0, [], 1.0, 0.5, "stream"),
        11: WaterSegment(11, 1, 2, 0, [], 1.0, 0.5, "stream"),
        12: WaterSegment(12, 2, 3, 0, [], 2.0, 0.5, "river"),
    }
    orders = net.compute_strahler_orders()
    assert orders[10] == 1
    assert orders[11] == 1
    assert orders[12] == 2

    # assign_strahler_orders persists on the dataclass instance
    net.assign_strahler_orders()
    assert getattr(net.segments[12], "strahler_order") == 2

    # get_trunk_segments filters by order
    trunks = net.get_trunk_segments(min_order=2)
    assert trunks == [12]


# ---------------------------------------------------------------------------
# Fix #6 — path_points_raw validation
# ---------------------------------------------------------------------------


def test_resolve_water_path_points_pads_2d_to_3d():
    from blender_addon.handlers.environment import _resolve_water_path_points

    pts = _resolve_water_path_points(
        path_points_raw=[(0.0, 0.0), (10.0, 5.0)],
        terrain_origin_x=0.0,
        terrain_origin_y=0.0,
        fallback_depth=100.0,
        water_level=1.5,
    )
    assert len(pts) == 2
    for pt in pts:
        assert len(pt) == 3
        assert pt[2] == pytest.approx(1.5)


def test_resolve_water_path_points_rejects_1d():
    from blender_addon.handlers.environment import _resolve_water_path_points

    with pytest.raises(ValueError, match="2 .* or 3"):
        _resolve_water_path_points(
            path_points_raw=[(0.0,), (1.0,)],
            terrain_origin_x=0.0,
            terrain_origin_y=0.0,
            fallback_depth=100.0,
            water_level=0.0,
        )


# ---------------------------------------------------------------------------
# Fix #7 — height range tiled-world bug
# ---------------------------------------------------------------------------


def test_resolve_export_height_range_rejects_tiled_without_explicit_range():
    from blender_addon.handlers.environment import _resolve_export_height_range

    hm = np.zeros((8, 8), dtype=np.float64)
    with pytest.raises(ValueError, match="tiled_world"):
        _resolve_export_height_range({"tiled_world": True}, hm)


def test_resolve_export_height_range_accepts_explicit_range():
    from blender_addon.handlers.environment import _resolve_export_height_range

    hm = np.zeros((8, 8), dtype=np.float64)
    result = _resolve_export_height_range(
        {"tiled_world": True, "height_range": [-50.0, 250.0]}, hm
    )
    assert result == (-50.0, 250.0)


def test_resolve_height_range_returns_none_when_no_explicit_keys():
    from blender_addon.handlers.environment import _resolve_height_range

    hm = np.zeros((8, 8), dtype=np.float64)
    assert (
        _resolve_height_range({}, hm, allow_local_fallback=False) is None
    )


# ---------------------------------------------------------------------------
# Fix #8 — negative space validators (Bundle H)
# ---------------------------------------------------------------------------


def test_negative_space_feature_density_validator_trips():
    from blender_addon.handlers.terrain_negative_space import (
        compute_feature_density,
        validate_negative_space,
    )
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    # Half the tile above busy threshold → density absolutely blows the cap
    sal = np.zeros((64, 64), dtype=np.float64)
    sal[:32, :] = 0.9
    stack = TerrainMaskStack(
        tile_size=64,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=np.zeros((65, 65)),
        saliency_macro=sal,
    )
    density = compute_feature_density(stack)
    assert density > 1.25  # must trip the default cap
    issues = validate_negative_space(stack, min_ratio=0.1)
    codes = [i.code for i in issues]
    assert "negative_space.feature_density_too_high" in codes


# ---------------------------------------------------------------------------
# Fix #9 — region_exec speedup reporting
# ---------------------------------------------------------------------------


def test_region_exec_speedup_estimate():
    from blender_addon.handlers.terrain_region_exec import estimate_speedup

    assert estimate_speedup(10.0, 2.0) == pytest.approx(5.0)
    assert estimate_speedup(0.0, 1.0) == 0.0
    assert estimate_speedup(1.0, 0.0) == float("inf")


def test_iteration_metrics_percentiles_and_summary():
    from blender_addon.handlers.terrain_iteration_metrics import (
        IterationMetrics,
        meets_speedup_target,
        record_iteration,
    )
    from blender_addon.handlers.terrain_semantics import PassResult

    metrics = IterationMetrics()
    for i, dur in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
        record_iteration(
            metrics,
            PassResult(
                pass_name=f"p{i}",
                status="ok",
                duration_seconds=dur,
                produced_channels=(),
                consumed_channels=(),
                metrics={},
                seed_used=0,
                content_hash_before=None,
                content_hash_after=None,
                issues=(),
            ),
        )
    assert metrics.total_passes_run == 5
    assert metrics.p50_duration_s == pytest.approx(0.3)
    assert metrics.p95_duration_s == pytest.approx(0.48)  # linear interpolation
    summary = metrics.summary_report()
    assert summary["total_passes_run"] == 5
    assert "per_pass_totals_s" in summary

    baseline = IterationMetrics(total_duration_s=10.0)
    fast = IterationMetrics(total_duration_s=1.5)
    assert meets_speedup_target(baseline, fast, target=5.0) is True

    slow = IterationMetrics(total_duration_s=3.0)
    assert meets_speedup_target(baseline, slow, target=5.0) is False


# ---------------------------------------------------------------------------
# Fix #10 — cliff height scaling is physical, not dimensional nonsense
# ---------------------------------------------------------------------------


def test_detect_cliff_edges_height_scale_applies_to_z_and_height():
    """height_scale multiplies both position[2] and cliff height.

    The cluster raw Z range must be large enough that both the
    ``height_scale=1.0`` baseline and the scaled variant clear the
    2 m minimum floor — otherwise the floor hides the scaling ratio.
    """
    from blender_addon.handlers._terrain_depth import detect_cliff_edges

    # Synthetic cliff with a 3.0-unit drop so the 2 m floor is never
    # the dominant factor at either scale under test.
    hm = np.full((32, 32), 3.0, dtype=np.float64)
    hm[:, 16:] = 0.0

    base = detect_cliff_edges(
        hm,
        slope_threshold_deg=5.0,
        min_cluster_size=2,
        terrain_size=100.0,
        height_scale=1.0,
    )
    scaled = detect_cliff_edges(
        hm,
        slope_threshold_deg=5.0,
        min_cluster_size=2,
        terrain_size=100.0,
        height_scale=20.0,
    )
    assert len(base) >= 1
    assert len(scaled) == len(base)

    for b, s in zip(base, scaled):
        # Both position Z and cliff height scale linearly with height_scale.
        assert s["position"][2] == pytest.approx(b["position"][2] * 20.0)
        assert s["height"] == pytest.approx(b["height"] * 20.0)
        # XY placement is independent of height_scale.
        assert s["position"][0] == pytest.approx(b["position"][0])
        assert s["position"][1] == pytest.approx(b["position"][1])


def test_detect_cliff_edges_height_independent_of_terrain_footprint():
    """The legacy formula scaled cliff height with terrain_width * 0.1.

    That made a 5 m physical rock face become a 100 m cliff on a 200 m
    terrain and a 50 m cliff on a 100 m terrain — pure dimensional
    nonsense. The replacement uses the actual cluster Z range times
    height_scale, so the reported cliff height must not change when the
    horizontal footprint changes.

    At a larger terrain footprint the cell spacing widens, so we must
    compensate with a steeper raw drop to keep the slope angle above
    the cliff threshold under the new spacing. We use a drop that is
    large enough to keep both calls tripping the threshold.
    """
    from blender_addon.handlers._terrain_depth import detect_cliff_edges

    # Drop of 30 units over the cliff column — enough to produce a
    # steep slope at both 100 m and 800 m terrain footprints.
    hm = np.full((32, 32), 30.0, dtype=np.float64)
    hm[:, 16:] = 0.0

    small = detect_cliff_edges(
        hm,
        slope_threshold_deg=5.0,
        min_cluster_size=2,
        terrain_size=100.0,
        height_scale=10.0,
    )
    big = detect_cliff_edges(
        hm,
        slope_threshold_deg=5.0,
        min_cluster_size=2,
        terrain_size=800.0,
        height_scale=10.0,
    )
    assert small and big
    # The cluster Z span is identical in both calls (same heightmap,
    # same height_scale); only the terrain footprint differs. Cliff
    # height must therefore be identical up to the 2 m floor.
    for s, b in zip(small, big):
        assert s["height"] == pytest.approx(b["height"])


def test_detect_cliff_edges_height_has_2m_floor():
    """Very shallow clusters still get a sensible minimum height."""
    from blender_addon.handlers._terrain_depth import detect_cliff_edges

    hm = np.full((32, 32), 0.5, dtype=np.float64)
    # Tiny 0.02 drop across a 3-cell column — realistic for erosion noise
    hm[:, 16:19] = 0.48

    placements = detect_cliff_edges(
        hm,
        slope_threshold_deg=1.0,
        min_cluster_size=2,
        terrain_size=100.0,
        height_scale=1.0,
    )
    for p in placements:
        assert p["height"] >= 2.0
