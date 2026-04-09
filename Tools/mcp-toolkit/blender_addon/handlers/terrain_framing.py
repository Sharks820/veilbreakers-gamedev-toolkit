"""Sightline framing for Bundle H — clears obstructions on vantage→target rays.

Pure numpy. No bpy. Z-up world meters.
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# enforce_sightline
# ---------------------------------------------------------------------------


def enforce_sightline(
    stack: TerrainMaskStack,
    vantage: Tuple[float, float, float],
    target: Tuple[float, float, float],
    clearance_m: float,
) -> np.ndarray:
    """Return a height delta that clears the line from ``vantage`` to ``target``.

    Samples the line-of-sight at ~1 cell intervals. Any cell whose height
    exceeds the linearly interpolated sightline height minus ``clearance_m``
    receives a negative delta bringing it to that limit. Cells away from the
    line are feathered with a radial falloff so the cut is not abrupt.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cell = float(stack.cell_size)
    delta = np.zeros_like(h, dtype=np.float64)

    vx, vy, vz = vantage
    tx, ty, tz = target
    dx = tx - vx
    dy = ty - vy
    planar = float(np.hypot(dx, dy))
    if planar < 1e-6:
        return delta

    n_samples = max(4, int(planar / cell))
    feather_cells = max(2.0, 4.0 / 1.0)  # 4 cells feather

    rr, cc = np.mgrid[0:rows, 0:cols].astype(np.float64)

    for si in range(n_samples + 1):
        t = si / float(n_samples)
        wx = vx + dx * t
        wy = vy + dy * t
        wz = vz + (tz - vz) * t
        limit_z = wz - float(clearance_m)

        cf = (wx - stack.world_origin_x) / cell
        rf = (wy - stack.world_origin_y) / cell

        d2 = (rr - rf) ** 2 + (cc - cf) ** 2
        local = d2 <= (feather_cells * feather_cells)
        if not np.any(local):
            continue

        weight = np.exp(-d2 / (2.0 * feather_cells * feather_cells))
        over = np.maximum(0.0, h - limit_z)
        this_delta = -over * weight
        # Keep the largest (most-negative) cut already collected
        delta = np.minimum(delta, this_delta)

    return delta


# ---------------------------------------------------------------------------
# pass_framing
# ---------------------------------------------------------------------------


def pass_framing(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Apply sightlines from composition_hints["vantages"] to every hero feature.

    Uses the default clearance from composition_hints.get("framing_clearance_m", 3.0).
    Writes into ``stack.height`` additively. Respects no-op if nothing to frame.
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    intent = state.intent

    vantages: List[Tuple[float, float, float]] = list(
        intent.composition_hints.get("vantages", ())
    )
    clearance = float(intent.composition_hints.get("framing_clearance_m", 3.0))

    if not vantages or not intent.hero_feature_specs:
        return PassResult(
            pass_name="framing",
            status="ok",
            duration_seconds=time.perf_counter() - t0,
            consumed_channels=("height",),
            produced_channels=("height",),
            metrics={
                "vantage_count": len(vantages),
                "feature_count": len(intent.hero_feature_specs),
                "noop": True,
            },
        )

    total_delta = np.zeros_like(stack.height, dtype=np.float64)
    sightlines_applied = 0
    for vantage in vantages:
        for feature in intent.hero_feature_specs:
            target = feature.world_position
            total_delta = np.minimum(
                total_delta,
                enforce_sightline(stack, vantage, target, clearance),
            )
            sightlines_applied += 1

    new_height = stack.height + total_delta
    stack.set("height", new_height, "framing")

    return PassResult(
        pass_name="framing",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("height",),
        metrics={
            "vantage_count": len(vantages),
            "feature_count": len(intent.hero_feature_specs),
            "sightlines_applied": sightlines_applied,
            "max_cut_m": float(-total_delta.min()),
            "mean_cut_m": float(-total_delta.mean()),
        },
    )


def register_framing_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="framing",
            func=pass_framing,
            requires_channels=("height",),
            produces_channels=("height",),
            seed_namespace="framing",
            may_modify_geometry=False,
            requires_scene_read=False,
            supports_region_scope=False,
            description="Clear vantage→hero sightlines by lowering obstructing cells.",
        )
    )


__all__ = [
    "enforce_sightline",
    "pass_framing",
    "register_framing_pass",
]
