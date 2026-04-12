"""Delta Integrator Pass — composes all terrain height deltas additively.

Phase 51 — fixes the dead-delta epidemic (F820-F825). Passes like waterfalls,
caves, and stratigraphy compute height deltas but previously discarded them.
This pass reads all ``*_delta`` channels from the mask stack and sums them
into ``stack.height``.

Pipeline placement: AFTER waterfalls / caves / stratigraphy, BEFORE materials.

Rules honored:
    - Z-up, world-meter heights
    - All signals read from / written to TerrainMaskStack
    - Protected zones respected (zero delta in protected cells)
    - No bpy / bmesh imports
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    ProtectedZoneSpec,
    TerrainMaskStack,
    TerrainPipelineState,
)

# ---------------------------------------------------------------------------
# Known delta channels — order matters for deterministic composition
# ---------------------------------------------------------------------------

_DELTA_CHANNELS: Tuple[str, ...] = (
    "waterfall_pool_delta",
    "cave_height_delta",
    "strat_erosion_delta",
    "pool_deepening_delta",
    # Phase 52 — Bundle I delta conversion
    "coastline_delta",
    "karst_delta",
    "wind_erosion_delta",
    "glacial_delta",
)


# ---------------------------------------------------------------------------
# Core integrator
# ---------------------------------------------------------------------------


def _collect_deltas(stack: TerrainMaskStack) -> List[Tuple[str, np.ndarray]]:
    """Return all populated delta channels as (name, array) pairs."""
    found: List[Tuple[str, np.ndarray]] = []
    for ch_name in _DELTA_CHANNELS:
        arr = stack.get(ch_name)
        if arr is not None:
            arr = np.asarray(arr, dtype=np.float64)
            if np.any(arr != 0.0):
                found.append((ch_name, arr))
    return found


def pass_integrate_deltas(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Sum all ``*_delta`` channels additively into ``stack.height``.

    Contract
    --------
    Consumes : height (plus any populated delta channels)
    Produces : height (modified in place with deltas applied)
    Respects protected zones : yes
    Requires scene read : no (deltas are already computed)
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    height = np.asarray(stack.height, dtype=np.float64)

    deltas = _collect_deltas(stack)

    if not deltas:
        return PassResult(
            pass_name="integrate_deltas",
            status="ok",
            duration_seconds=time.perf_counter() - t0,
            consumed_channels=("height",),
            produced_channels=("height",),
            metrics={
                "delta_channels_applied": [],
                "total_delta_sum": 0.0,
                "cells_modified": 0,
            },
        )

    # Sum all deltas
    total_delta = np.zeros_like(height, dtype=np.float64)
    applied_names: List[str] = []
    for name, arr in deltas:
        total_delta += arr
        applied_names.append(name)

    # Apply protected zone mask: zero out delta in protected cells
    # 1. Hero exclusion channel
    protected = stack.get("hero_exclusion")
    prot_bool = np.zeros_like(total_delta, dtype=bool)
    if protected is not None:
        prot_bool |= np.asarray(protected, dtype=np.float64) > 0.0

    # 2. Intent protected zones (replicates _terrain_world._protected_mask)
    if state.intent.protected_zones:
        rows, cols = total_delta.shape
        ys = stack.world_origin_y + (np.arange(rows) + 0.5) * stack.cell_size
        xs = stack.world_origin_x + (np.arange(cols) + 0.5) * stack.cell_size
        xg, yg = np.meshgrid(xs, ys)
        for zone in state.intent.protected_zones:
            if zone.permits("integrate_deltas"):
                continue
            inside = (
                (xg >= zone.bounds.min_x)
                & (xg <= zone.bounds.max_x)
                & (yg >= zone.bounds.min_y)
                & (yg <= zone.bounds.max_y)
            )
            prot_bool |= inside

    total_delta = np.where(prot_bool, 0.0, total_delta)

    # Region scope: only apply within region bounds
    if region is not None:
        r_slice, c_slice = region.to_cell_slice(
            world_origin_x=stack.world_origin_x,
            world_origin_y=stack.world_origin_y,
            cell_size=stack.cell_size,
            grid_shape=height.shape,
        )
        mask = np.zeros_like(total_delta, dtype=bool)
        mask[r_slice, c_slice] = True
        total_delta = np.where(mask, total_delta, 0.0)

    # Apply to height
    new_height = height + total_delta
    stack.set("height", new_height, "integrate_deltas")

    cells_modified = int(np.count_nonzero(total_delta))

    return PassResult(
        pass_name="integrate_deltas",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("height",),
        metrics={
            "delta_channels_applied": applied_names,
            "total_delta_sum": float(total_delta.sum()),
            "cells_modified": cells_modified,
            "max_delta": float(total_delta.min()),  # most negative = deepest carve
        },
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_integrator_pass() -> None:
    """Register the delta integrator pass on TerrainPassController."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="integrate_deltas",
            func=pass_integrate_deltas,
            requires_channels=("height",),
            produces_channels=("height",),
            seed_namespace="integrate_deltas",
            requires_scene_read=False,
            may_modify_geometry=False,
            respects_protected_zones=True,
            description="Phase 51 — compose all terrain height deltas additively into height.",
        )
    )


__all__ = [
    "pass_integrate_deltas",
    "register_integrator_pass",
]
