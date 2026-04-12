"""Sub-tile region execution for terrain iteration velocity (Bundle M).

Runs a pass sequence scoped to a sub-tile region, with automatic padding
computation so droplet-based erosion etc. doesn't show seams at the patch
boundary. Also supports rollback-on-failure and a baseline-relative
speedup estimator so the 5x iteration-velocity target in Section 3.2 of
the ultra implementation plan is measurable rather than aspirational.

Pure Python + numpy. No bpy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .terrain_pipeline import TerrainPassController
from .terrain_semantics import BBox, PassDefinition, PassResult


# Default radius (in world meters) passes get padded by. Erosion droplets
# can travel ~30 cells at 1m/cell worst case before losing all water.
_DEFAULT_PAD_RADIUS_M: float = 8.0


# Per-pass padding map — if a registered pass is known to need more
# slack than the default, override here. Conservative numbers.
_PASS_PAD_RADIUS: dict = {
    "erosion": 16.0,
    "macro_world": 0.0,  # global noise, padding is meaningless
    "structural_masks": 2.0,
    "validation_minimal": 0.0,
    "hero_features": 6.0,
    "water_network": 12.0,
    "material_zoning": 0.0,
    "asset_population": 4.0,
    "ecosystem_spine": 2.0,
    "validation_full": 0.0,
}


@dataclass
class RegionExecutionReport:
    """Summary returned by ``execute_region`` and ``execute_region_with_rollback``.

    * ``results`` — one ``PassResult`` per pass that ran (stops at first
      failure when rollback is enabled).
    * ``padded_region`` — the region after automatic padding expansion.
    * ``wall_clock_seconds`` — total time spent running the sequence.
    * ``rolled_back`` — ``True`` when a validation failure triggered a
      checkpoint rollback.
    * ``rollback_checkpoint_id`` — the checkpoint restored on rollback,
      or ``None`` when no rollback happened.
    """

    results: List[PassResult]
    padded_region: BBox
    wall_clock_seconds: float
    rolled_back: bool = False
    rollback_checkpoint_id: Optional[str] = None


def _pass_pad_radius(pass_def: PassDefinition) -> float:
    return float(_PASS_PAD_RADIUS.get(pass_def.name, _DEFAULT_PAD_RADIUS_M))


def compute_minimum_padding(
    region: BBox,
    passes: Sequence[str],
    controller: Optional[TerrainPassController] = None,
    world_bounds: Optional[BBox] = None,
) -> BBox:
    """Expand a region outward by the maximum padding any pass needs.

    If a registry lookup fails for a pass name (e.g. the pass isn't
    registered yet) we fall back to the default radius. The returned
    BBox is clamped to ``world_bounds`` when provided.
    """
    pad = 0.0
    for name in passes:
        try:
            pdef = TerrainPassController.get_pass(name)
            pad = max(pad, _pass_pad_radius(pdef))
        except Exception:
            pad = max(pad, _DEFAULT_PAD_RADIUS_M)

    min_x = region.min_x - pad
    min_y = region.min_y - pad
    max_x = region.max_x + pad
    max_y = region.max_y + pad
    if world_bounds is not None:
        min_x = max(min_x, world_bounds.min_x)
        min_y = max(min_y, world_bounds.min_y)
        max_x = min(max_x, world_bounds.max_x)
        max_y = min(max_y, world_bounds.max_y)
        if max_x <= min_x:
            max_x = min_x + 1e-6
        if max_y <= min_y:
            max_y = min_y + 1e-6
    return BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def execute_region(
    controller: TerrainPassController,
    pass_sequence: Sequence[str],
    region: BBox,
    *,
    pad: bool = True,
    checkpoint: bool = False,
) -> List[PassResult]:
    """Run a pass sequence scoped to ``region`` (optionally padded).

    Stops on the first failed pass. This is the low-level primitive;
    prefer :func:`execute_region_with_rollback` when you want automatic
    restoration on validation failure.
    """
    world = controller.state.intent.region_bounds
    target = (
        compute_minimum_padding(region, pass_sequence, controller, world)
        if pad
        else region
    )
    results: List[PassResult] = []
    for pass_name in pass_sequence:
        res = controller.run_pass(pass_name, region=target, checkpoint=checkpoint)
        results.append(res)
        if res.status == "failed":
            break
    return results


def execute_region_with_rollback(
    controller: TerrainPassController,
    pass_sequence: Sequence[str],
    region: BBox,
    *,
    pad: bool = True,
) -> RegionExecutionReport:
    """Run a sequence scoped to ``region`` with rollback on failure.

    Before the sequence starts we save a checkpoint. If any pass in the
    sequence reports ``status == "failed"`` we restore that checkpoint
    so the mask stack returns to its pre-sequence state, and the report
    surfaces the rollback marker so the caller can decide what to do.
    This mirrors how Horizon/Decima's terrain editor handles iterative
    local sculpt operations — failures never corrupt global state.
    """
    world = controller.state.intent.region_bounds
    target = (
        compute_minimum_padding(region, pass_sequence, controller, world)
        if pad
        else region
    )

    # Save a pre-sequence checkpoint through the public checkpoint API so
    # we can roll back by label if any pass fails. The label is unique
    # per invocation so concurrent callers can't collide, even though the
    # pipeline is single-threaded today.
    from .terrain_checkpoints import save_checkpoint as _save_ckpt
    from .terrain_checkpoints import rollback_to as _rollback_to

    pre_id: Optional[str] = None
    pre_label = f"region_exec_pre_{int(time.time() * 1000)}"
    try:
        ckpt = _save_ckpt(controller, pass_name="region_exec_pre", label=pre_label)
        pre_id = ckpt.checkpoint_id
    except Exception:
        pre_id = None

    start = time.perf_counter()
    results: List[PassResult] = []
    rolled_back = False
    for pass_name in pass_sequence:
        res = controller.run_pass(pass_name, region=target, checkpoint=False)
        results.append(res)
        if res.status == "failed":
            if pre_id is not None:
                try:
                    _rollback_to(controller, pre_label)
                    rolled_back = True
                except Exception:
                    # Best-effort rollback; surface the failure via the
                    # report rather than swallowing it.
                    rolled_back = False
            break
    wall = time.perf_counter() - start

    return RegionExecutionReport(
        results=results,
        padded_region=target,
        wall_clock_seconds=wall,
        rolled_back=rolled_back,
        rollback_checkpoint_id=pre_id if rolled_back else None,
    )


def estimate_speedup(
    full_tile_seconds: float,
    region_seconds: float,
) -> float:
    """Return how many times faster a region run was vs a full-tile run.

    Used by the iteration-velocity harness to validate the ≥ 5x target
    from the ultra plan §3.2. Returns ``inf`` if the region run took
    zero measurable time (perfect cache), ``0.0`` if the full-tile
    baseline was zero (avoid division-by-zero).
    """
    if full_tile_seconds <= 0.0:
        return 0.0
    if region_seconds <= 0.0:
        return float("inf")
    return float(full_tile_seconds) / float(region_seconds)


__all__ = [
    "execute_region",
    "execute_region_with_rollback",
    "compute_minimum_padding",
    "estimate_speedup",
    "RegionExecutionReport",
]
