"""Bundle L — terrain_fog_masks.

Computes two atmospheric density fields:

* ``fog_pool_mask`` — volumetric fog accumulation in low-elevation concave
  basins. Pools cling to valleys, thin over ridges. Float32 [0..1].
* ``mist_envelope`` — near-water mist halo around wet cells. Float32 [0..1]
  and populates ``stack.mist``.

Both signals are pure numpy and respect Z-up world-meter conventions.
The pass stores the pooled fog mask on ``stack.cloud_shadow`` is NOT
touched (Bundle J owns that). Fog instead populates ``stack.mist`` and
``stack.cloud_shadow``-adjacent fields only indirectly.

Design notes
------------
Atmospheric fog density is driven by two physical proxies:
  1. Altitude: cold, dense air settles — lower cells hold more fog.
  2. Concavity: still air pools in valleys/basins, ridges shed it.
We combine these with a smoothed falloff so output is visually coherent.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# Fog pool mask
# ---------------------------------------------------------------------------


def compute_fog_pool_mask(stack: TerrainMaskStack) -> np.ndarray:
    """Build a volumetric fog-pool mask in [0, 1] as float32.

    Fog pools where:
      * elevation is low relative to the tile range (altitude weight)
      * the local neighbourhood is concave (basin / valley weight)

    Returns
    -------
    np.ndarray
        float32 shape matching ``stack.height``. 0 = clear sky, 1 = dense
        ground fog.
    """
    if stack.height is None:
        raise ValueError("compute_fog_pool_mask requires stack.height")
    h = np.asarray(stack.height, dtype=np.float64)

    h_min = float(h.min())
    h_max = float(h.max())
    if h_max - h_min < 1e-9:
        return np.zeros_like(h, dtype=np.float32)

    # Altitude weight: lowest = 1, highest = 0. Soft gamma so valleys are
    # strongly favoured.
    alt_norm = (h - h_min) / (h_max - h_min)
    alt_weight = np.power(1.0 - alt_norm, 1.5)

    # Concavity weight: positive laplacian => basin, negative => ridge.
    lap = (
        np.roll(h, 1, 0)
        + np.roll(h, -1, 0)
        + np.roll(h, 1, 1)
        + np.roll(h, -1, 1)
        - 4.0 * h
    ) / (float(stack.cell_size) ** 2)
    # Normalise to [-1, 1] via robust percentile scaling.
    p_lo, p_hi = np.percentile(lap, [5.0, 95.0])
    spread = max(abs(p_lo), abs(p_hi), 1e-6)
    conc = np.clip(lap / spread, -1.0, 1.0)
    basin_weight = np.clip((conc + 1.0) * 0.5, 0.0, 1.0)  # basins near 1

    fog = 0.65 * alt_weight + 0.35 * basin_weight

    # Light smoothing via a 3x3 box blur (toroidal) for visual coherence.
    smoothed = (
        fog
        + np.roll(fog, 1, 0)
        + np.roll(fog, -1, 0)
        + np.roll(fog, 1, 1)
        + np.roll(fog, -1, 1)
    ) / 5.0
    return np.clip(smoothed, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Mist envelope (near-water)
# ---------------------------------------------------------------------------


def compute_mist_envelope(
    stack: TerrainMaskStack,
    wetness: np.ndarray,
) -> np.ndarray:
    """Mist intensity near wet / water cells. Float32 [0, 1].

    A simple multi-step dilation of the wetness mask produces a falloff
    envelope. Cells directly on water get max mist; cells N steps away
    get ``(1 - N/steps)`` mist.
    """
    if stack.height is None:
        raise ValueError("compute_mist_envelope requires stack.height")
    w = np.asarray(wetness, dtype=np.float32)
    if w.shape != stack.height.shape:
        raise ValueError(
            f"wetness shape {w.shape} must match height shape {stack.height.shape}"
        )

    steps = 4
    env = w.copy()
    current = (w > 0.05).astype(np.float32)
    for s in range(1, steps + 1):
        dilated = (
            current
            + np.roll(current, 1, 0)
            + np.roll(current, -1, 0)
            + np.roll(current, 1, 1)
            + np.roll(current, -1, 1)
        )
        dilated = (dilated > 0.5).astype(np.float32)
        env = np.maximum(env, dilated * (1.0 - s / (steps + 1)))
        current = dilated
    return np.clip(env, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Pass wrapper
# ---------------------------------------------------------------------------


def pass_fog_masks(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle L pass: populate ``mist`` (and writes a private fog field on
    the mask stack under ``cloud_shadow``-adjacent storage in metrics only).

    Contract
    --------
    Consumes: ``height``, optionally ``wetness``
    Produces: ``mist``
    Respects protected zones: no (read-only on height + wetness)
    Requires scene read: no
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    fog_pool = compute_fog_pool_mask(stack)

    wet = stack.get("wetness")
    if wet is None:
        wet = np.zeros_like(stack.height, dtype=np.float32)
    mist = compute_mist_envelope(stack, np.asarray(wet, dtype=np.float32))

    # Combine fog pool + mist into the authoritative mist channel. The
    # fog-pool contribution is capped so mist near water remains dominant.
    combined = np.maximum(mist, 0.75 * fog_pool).astype(np.float32)
    stack.set("mist", combined, "fog_masks")

    return PassResult(
        pass_name="fog_masks",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height", "wetness"),
        produced_channels=("mist",),
        metrics={
            "fog_pool_mean": float(fog_pool.mean()),
            "fog_pool_max": float(fog_pool.max()),
            "mist_coverage_frac": float((combined > 0.1).mean()),
            "mist_max": float(combined.max()),
        },
    )


def register_bundle_l_fog_masks_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="fog_masks",
            func=pass_fog_masks,
            requires_channels=("height",),
            produces_channels=("mist",),
            seed_namespace="fog_masks",
            requires_scene_read=False,
            description="Bundle L: volumetric fog pool + mist envelope",
        )
    )


__all__ = [
    "compute_fog_pool_mask",
    "compute_mist_envelope",
    "pass_fog_masks",
    "register_bundle_l_fog_masks_pass",
]
