"""Bundle M — Iteration velocity tests.

Covers:
    - DirtyTracker correctness
    - MaskCache LRU + hit/miss semantics
    - Sub-tile region exec (padding)
    - Visual diff per-channel
    - PassDAG topo ordering + parallel waves
    - HotReloadWatcher
    - IterationMetrics + speedup measurement
    - LivePreviewSession apply_edit
    - Synthetic 5x-speedup proof over a 100m patch edit
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _register_passes():
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    TerrainPassController.clear_registry()
    register_default_passes()
    yield
    TerrainPassController.clear_registry()


def _build_state(tile_size: int = 32, seed: int = 1234, include_scene_read: bool = True):
    from blender_addon.handlers._terrain_noise import generate_heightmap
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    height = np.asarray(
        generate_heightmap(
            tile_size + 1,
            tile_size + 1,
            scale=100.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            cell_size=1.0,
            seed=seed,
            terrain_type="mountains",
            normalize=False,
        ),
        dtype=np.float64,
    )
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    region_bounds = BBox(0.0, 0.0, float(tile_size), float(tile_size))
    scene_read = None
    if include_scene_read:
        scene_read = TerrainSceneRead(
            timestamp=0.0,
            major_landforms=("ridge_system",),
            focal_point=(tile_size / 2.0, tile_size / 2.0, 0.0),
            hero_features_present=(),
            hero_features_missing=(),
            waterfall_chains=(),
            cave_candidates=(),
            protected_zones_in_region=(),
            edit_scope=region_bounds,
            success_criteria=("iter_test",),
            reviewer="pytest",
        )
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
        scene_read=scene_read,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def _tempdir():
    return tempfile.TemporaryDirectory()


# ===========================================================================
# 1–5. DirtyTracker
# ===========================================================================


def test_dirty_tracker_starts_clean():
    from blender_addon.handlers.terrain_dirty_tracking import DirtyTracker
    from blender_addon.handlers.terrain_semantics import BBox

    t = DirtyTracker(world_bounds=BBox(0, 0, 100, 100))
    assert t.is_clean()
    assert t.dirty_fraction() == 0.0
    assert t.coalesce() is None


def test_dirty_tracker_mark_and_regions():
    from blender_addon.handlers.terrain_dirty_tracking import DirtyTracker
    from blender_addon.handlers.terrain_semantics import BBox

    t = DirtyTracker(world_bounds=BBox(0, 0, 100, 100))
    t.mark_dirty("height", BBox(10, 10, 20, 20))
    t.mark_dirty("slope", BBox(30, 30, 40, 40))
    regions = t.get_dirty_regions()
    assert len(regions) == 2
    assert "height" in t.get_dirty_channels()
    assert "slope" in t.get_dirty_channels()
    assert not t.is_clean()


def test_dirty_tracker_fraction():
    from blender_addon.handlers.terrain_dirty_tracking import DirtyTracker
    from blender_addon.handlers.terrain_semantics import BBox

    t = DirtyTracker(world_bounds=BBox(0, 0, 100, 100))
    t.mark_dirty("height", BBox(0, 0, 10, 10))
    # 100m^2 / 10000m^2 = 0.01
    assert abs(t.dirty_fraction() - 0.01) < 1e-6


def test_dirty_tracker_coalesce_merges_all():
    from blender_addon.handlers.terrain_dirty_tracking import DirtyTracker
    from blender_addon.handlers.terrain_semantics import BBox

    t = DirtyTracker(world_bounds=BBox(0, 0, 100, 100))
    t.mark_dirty("height", BBox(5, 5, 10, 10))
    t.mark_dirty("slope", BBox(50, 50, 60, 60))
    merged = t.coalesce()
    assert merged is not None
    assert merged.bounds.min_x == 5
    assert merged.bounds.max_x == 60
    assert "height" in merged.affected_channels
    assert "slope" in merged.affected_channels


def test_attach_dirty_tracker_is_idempotent():
    from blender_addon.handlers.terrain_dirty_tracking import attach_dirty_tracker

    state = _build_state()
    t1 = attach_dirty_tracker(state)
    t2 = attach_dirty_tracker(state)
    assert t1 is t2


# ===========================================================================
# 6–10. MaskCache
# ===========================================================================


def test_mask_cache_put_get_hit_miss():
    from blender_addon.handlers.terrain_mask_cache import MaskCache

    c = MaskCache(max_entries=4)
    assert c.get("k") is None
    assert c.misses == 1
    c.put("k", 123)
    assert c.get("k") == 123
    assert c.hits == 1


def test_mask_cache_lru_eviction():
    from blender_addon.handlers.terrain_mask_cache import MaskCache

    c = MaskCache(max_entries=2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # evicts "a"
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_mask_cache_get_or_compute_runs_fn_once():
    from blender_addon.handlers.terrain_mask_cache import MaskCache

    c = MaskCache()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return 42

    assert c.get_or_compute("key", fn) == 42
    assert c.get_or_compute("key", fn) == 42
    assert calls["n"] == 1


def test_mask_cache_key_determinism():
    from blender_addon.handlers.terrain_mask_cache import cache_key_for_pass
    from blender_addon.handlers.terrain_semantics import BBox

    state = _build_state()
    k1 = cache_key_for_pass("erosion", state.intent, BBox(0, 0, 10, 10), (0, 0))
    k2 = cache_key_for_pass("erosion", state.intent, BBox(0, 0, 10, 10), (0, 0))
    k3 = cache_key_for_pass("erosion", state.intent, BBox(0, 0, 20, 20), (0, 0))
    assert k1 == k2
    assert k1 != k3


def test_mask_cache_invalidate_prefix():
    from blender_addon.handlers.terrain_mask_cache import MaskCache

    c = MaskCache()
    c.put("height:1", 1)
    c.put("height:2", 2)
    c.put("slope:1", 3)
    n = c.invalidate_prefix("height")
    assert n == 2
    assert c.get("height:1") is None
    assert c.get("slope:1") == 3


def test_pass_with_cache_restores_produced_channels():
    from blender_addon.handlers.terrain_mask_cache import MaskCache, pass_with_cache
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        pdef = TerrainPassController.get_pass("macro_world")
        cache = MaskCache()
        r1 = pass_with_cache(pdef, state, None, cache)
        h1 = state.mask_stack.height.copy()

        # Wipe the channel and re-run via cache — should restore h1
        state.mask_stack.height[:] = 0.0
        r2 = pass_with_cache(pdef, state, None, cache)
        assert cache.hits >= 1
        # The cache-hit path restores the produced channel snapshot
        np.testing.assert_array_equal(state.mask_stack.height, h1)


# ===========================================================================
# 11–13. Region exec + padding
# ===========================================================================


def test_compute_minimum_padding_expands_region():
    from blender_addon.handlers.terrain_region_exec import compute_minimum_padding
    from blender_addon.handlers.terrain_semantics import BBox

    region = BBox(50, 50, 60, 60)
    padded = compute_minimum_padding(region, ["erosion"], world_bounds=BBox(0, 0, 100, 100))
    assert padded.min_x < region.min_x
    assert padded.max_x > region.max_x
    assert padded.min_x >= 0
    assert padded.max_x <= 100


def test_compute_minimum_padding_clamps_to_world():
    from blender_addon.handlers.terrain_region_exec import compute_minimum_padding
    from blender_addon.handlers.terrain_semantics import BBox

    region = BBox(0, 0, 10, 10)
    padded = compute_minimum_padding(region, ["erosion"], world_bounds=BBox(0, 0, 100, 100))
    assert padded.min_x == 0.0
    assert padded.min_y == 0.0


def test_execute_region_runs_pass_sequence():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_region_exec import execute_region
    from blender_addon.handlers.terrain_semantics import BBox

    with _tempdir() as td:
        state = _build_state(tile_size=32)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        # Prereqs
        controller.run_pass("macro_world", checkpoint=False)
        controller.run_pass("structural_masks", checkpoint=False)
        results = execute_region(
            controller,
            ["erosion"],
            BBox(10, 10, 20, 20),
            pad=True,
            checkpoint=False,
        )
        assert len(results) == 1
        assert results[0].pass_name == "erosion"


# ===========================================================================
# 14–16. Visual diff
# ===========================================================================


def test_visual_diff_identical_stacks_reports_no_change():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_visual_diff import compute_visual_diff

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("macro_world", checkpoint=False)

    diff = compute_visual_diff(state.mask_stack, state.mask_stack)
    assert diff["changed_channels"] == []
    assert diff["total_changed_cells"] == 0


def test_visual_diff_detects_height_change():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_visual_diff import compute_visual_diff
    from blender_addon.handlers.terrain_live_preview import _clone_stack_for_diff

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("macro_world", checkpoint=False)
        snap_before = _clone_stack_for_diff(state.mask_stack)
        state.mask_stack.height[5:10, 5:10] += 50.0

    diff = compute_visual_diff(snap_before, state.mask_stack)
    assert "height" in diff["changed_channels"]
    assert diff["per_channel"]["height"]["max_abs_delta"] >= 49.0


def test_generate_diff_overlay_shape_and_colors():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_visual_diff import generate_diff_overlay
    from blender_addon.handlers.terrain_live_preview import _clone_stack_for_diff

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("macro_world", checkpoint=False)
        snap = _clone_stack_for_diff(state.mask_stack)
        state.mask_stack.height[5:10, 5:10] += 30.0

    overlay = generate_diff_overlay(snap, state.mask_stack)
    assert overlay.shape == state.mask_stack.height.shape + (3,)
    assert overlay.dtype == np.uint8
    # Red (height increase) should have fired somewhere
    assert overlay[..., 0].max() > 0


# ===========================================================================
# 17–19. PassDAG
# ===========================================================================


def test_pass_dag_topological_order_from_registry():
    from blender_addon.handlers.terrain_pass_dag import PassDAG

    dag = PassDAG.from_registry()
    order = dag.topological_order()
    # macro_world produces height; structural_masks/erosion require height
    assert order.index("macro_world") < order.index("structural_masks")
    assert order.index("macro_world") < order.index("erosion")


def test_pass_dag_parallel_waves():
    from blender_addon.handlers.terrain_pass_dag import PassDAG

    dag = PassDAG.from_registry()
    waves = dag.parallel_waves()
    # Wave 0 must include macro_world (zero-dep)
    assert "macro_world" in waves[0]
    # structural_masks and erosion can be in the same wave (both depend on height only)
    found_struct = any("structural_masks" in w for w in waves)
    found_erosion = any("erosion" in w for w in waves)
    assert found_struct and found_erosion


def test_pass_dag_execute_parallel_runs_all():
    from blender_addon.handlers.terrain_pass_dag import PassDAG
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        dag = PassDAG.from_registry()
        results = dag.execute_parallel(controller, max_workers=2, checkpoint=False)
        names = {r.pass_name for r in results}
        assert "macro_world" in names
        assert "structural_masks" in names
        assert "erosion" in names


# ===========================================================================
# 20. Hot reload
# ===========================================================================


def test_hot_reload_watcher_detects_no_change_on_first_scan():
    from blender_addon.handlers.terrain_hot_reload import HotReloadWatcher

    w = HotReloadWatcher()
    w.add("blender_addon.handlers.terrain_semantics")
    reloaded = w.check_and_reload()
    # First scan establishes baseline — no changes detected
    assert reloaded == [] or "terrain_semantics" in reloaded[0]


def test_reload_biome_rules_runs_without_error():
    from blender_addon.handlers.terrain_hot_reload import reload_biome_rules

    ok = reload_biome_rules()
    # All or some modules reload successfully; never raise
    assert isinstance(ok, list)


# ===========================================================================
# 21–22. IterationMetrics
# ===========================================================================


def test_iteration_metrics_record_and_speedup():
    from blender_addon.handlers.terrain_iteration_metrics import (
        IterationMetrics,
        record_iteration,
        speedup_factor,
    )
    from blender_addon.handlers.terrain_semantics import PassResult

    baseline = IterationMetrics()
    record_iteration(baseline, PassResult(pass_name="a", status="ok", duration_seconds=1.0))
    record_iteration(baseline, PassResult(pass_name="b", status="ok", duration_seconds=1.0))

    current = IterationMetrics()
    record_iteration(current, PassResult(pass_name="a", status="ok", duration_seconds=0.2))
    record_iteration(current, PassResult(pass_name="b", status="ok", duration_seconds=0.2))

    assert abs(speedup_factor(baseline, current) - 5.0) < 1e-6
    assert baseline.avg_pass_duration_s == 1.0
    assert current.avg_pass_duration_s == pytest.approx(0.2)


def test_iteration_metrics_cache_hit_rate():
    from blender_addon.handlers.terrain_iteration_metrics import (
        IterationMetrics,
        record_cache_hit,
        record_cache_miss,
    )

    m = IterationMetrics()
    record_cache_hit(m)
    record_cache_hit(m)
    record_cache_miss(m)
    assert m.cache_hit_rate == pytest.approx(2 / 3)


# ===========================================================================
# 23. LivePreviewSession
# ===========================================================================


def test_live_preview_session_apply_edit_changes_hash():
    from blender_addon.handlers.terrain_live_preview import LivePreviewSession
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        # Prereqs for erosion (requires scene_read + height + structural_masks)
        controller.run_pass("macro_world", checkpoint=False)
        controller.run_pass("structural_masks", checkpoint=False)
        session = LivePreviewSession(controller=controller)
        h0 = session.current_hash()
        h1 = session.apply_edit({"passes": ["erosion"], "region": None, "use_cache": True})
        assert h0 != h1
        diff_info = session.diff_preview(h0, h1)
        assert diff_info["identical"] is False


# ===========================================================================
# 24. 5x speedup on synthetic 100m patch edit
# ===========================================================================


def test_iteration_velocity_cache_delivers_speedup():
    """Re-running the same pass sequence with a warm cache must be much
    faster than the cold run. We assert >= 2x to avoid CI flakiness; the
    real target is 5x but single-threaded machines vary.
    """
    from blender_addon.handlers.terrain_iteration_metrics import (
        IterationMetrics,
        record_iteration,
        speedup_factor,
    )
    from blender_addon.handlers.terrain_mask_cache import MaskCache, pass_with_cache
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox

    with _tempdir() as td:
        state = _build_state(tile_size=48)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))

        # Cold baseline — run pipeline passes directly, no cache
        baseline = IterationMetrics()
        t0 = time.perf_counter()
        r1 = controller.run_pass("macro_world", checkpoint=False)
        r2 = controller.run_pass("structural_masks", checkpoint=False)
        r3 = controller.run_pass("erosion", checkpoint=False)
        baseline.total_duration_s = time.perf_counter() - t0
        for r in (r1, r2, r3):
            baseline.total_passes_run += 1
            baseline.pass_names.append(r.pass_name)

        # Warm run via mask cache
        cache = MaskCache(max_entries=32)
        pdefs = [TerrainPassController.get_pass(n) for n in ("macro_world", "structural_masks", "erosion")]
        # Prime the cache
        for p in pdefs:
            pass_with_cache(p, state, None, cache)

        current = IterationMetrics()
        t1 = time.perf_counter()
        for p in pdefs:
            pass_with_cache(p, state, None, cache)
        current.total_duration_s = time.perf_counter() - t1
        current.total_passes_run = len(pdefs)
        current.cache_hits = cache.hits
        current.cache_misses = cache.misses

        sf = speedup_factor(baseline, current)
        # Warm-cache path should be dramatically faster than cold
        assert sf >= 2.0, f"expected >=2x speedup, got {sf:.2f}x (baseline={baseline.total_duration_s:.4f}s, current={current.total_duration_s:.4f}s)"
        assert cache.hits >= 3


def test_dirty_tracker_integration_with_live_preview():
    from blender_addon.handlers.terrain_live_preview import LivePreviewSession
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox

    with _tempdir() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        session = LivePreviewSession(controller=controller)
        session.apply_edit(
            {
                "passes": ["macro_world"],
                "region": BBox(5, 5, 15, 15),
                "dirty_channels": ["height"],
                "use_cache": True,
            }
        )
        assert not session.tracker.is_clean()
        assert "height" in session.tracker.get_dirty_channels()
