"""Bundle K — terrain_multiscale_breakup.

Layers noise at 3 world-space scales (default 5 m / 20 m / 100 m) into
``roughness_variation`` to break up uniform PBR regions. This is the
"multi-scale breakup" trick used in Horizon Forbidden West / Ghost of
Tsushima terrain shaders: micro-detail + meso-detail + macro-detail,
each with decreasing amplitude.
"""

from __future__ import annotations

import math
import time
from typing import Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


def _rng_grid_bilinear(shape: Tuple[int, int], seed: int, scale_cells: float) -> np.ndarray:
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    h, w = shape
    gh = max(2, int(math.ceil(h / max(scale_cells, 1.0))) + 2)
    gw = max(2, int(math.ceil(w / max(scale_cells, 1.0))) + 2)
    grid = rng.uniform(-1.0, 1.0, size=(gh, gw)).astype(np.float64)
    ys = np.linspace(0.0, gh - 1.0, h)
    xs = np.linspace(0.0, gw - 1.0, w)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, gh - 1)
    x1 = np.clip(x0 + 1, 0, gw - 1)
    ty = (ys - y0).reshape(-1, 1)
    tx = (xs - x0).reshape(1, -1)
    a = grid[np.ix_(y0, x0)]
    b = grid[np.ix_(y0, x1)]
    c = grid[np.ix_(y1, x0)]
    d = grid[np.ix_(y1, x1)]
    top = a * (1 - tx) + b * tx
    bot = c * (1 - tx) + d * tx
    return top * (1 - ty) + bot * ty


def compute_multiscale_breakup(
    stack: TerrainMaskStack,
    scales_m: Tuple[float, ...] = (5.0, 20.0, 100.0),
    seed: int = 0,
) -> np.ndarray:
    """Return a (H, W) float32 breakup modulation in [-1, 1].

    Sum of N octaves each scaled by amplitude = 1/(i+1). Scales are
    world-meters, converted to cells via ``stack.cell_size``.
    """
    if stack.height is None:
        raise ValueError("compute_multiscale_breakup requires stack.height")
    if not scales_m:
        raise ValueError("scales_m must contain at least one scale")

    h = np.asarray(stack.height)
    shape = h.shape
    cell_m = float(stack.cell_size)

    total = np.zeros(shape, dtype=np.float64)
    weight_sum = 0.0
    for i, scale in enumerate(scales_m):
        if scale <= 0.0:
            raise ValueError(f"scale #{i} must be > 0, got {scale}")
        scale_cells = max(1.0, float(scale) / max(cell_m, 1e-6))
        amp = 1.0 / (i + 1)
        layer = _rng_grid_bilinear(shape, seed ^ (0x9E3779B1 * (i + 1)), scale_cells)
        total += layer * amp
        weight_sum += amp

    total /= max(weight_sum, 1e-6)
    return total.astype(np.float32)


def pass_multiscale_breakup(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle K pass: multi-scale breakup into roughness_variation.

    Consumes: height
    Produces: roughness_variation
    """
    from .terrain_pipeline import derive_pass_seed

    t0 = time.perf_counter()
    stack = state.mask_stack
    hints = state.intent.composition_hints if state.intent else {}
    scales = tuple(hints.get("breakup_scales_m", (5.0, 20.0, 100.0)))

    seed = derive_pass_seed(
        state.intent.seed if state.intent else 0,
        "multiscale_breakup",
        state.tile_x,
        state.tile_y,
        region,
    )
    breakup = compute_multiscale_breakup(stack, scales_m=scales, seed=seed)

    existing = stack.get("roughness_variation")
    if existing is None:
        rough = 0.5 + 0.25 * breakup
    else:
        rough = np.asarray(existing, dtype=np.float32) + 0.15 * breakup
    rough = np.clip(rough, 0.0, 1.0).astype(np.float32)
    stack.set("roughness_variation", rough, "multiscale_breakup")

    return PassResult(
        pass_name="multiscale_breakup",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("roughness_variation",),
        metrics={
            "scales_m": list(scales),
            "breakup_min": float(breakup.min()),
            "breakup_max": float(breakup.max()),
            "breakup_std": float(breakup.std()),
            "seed_used": int(seed),
        },
        issues=[],
        seed_used=int(seed),
    )


def register_bundle_k_multiscale_breakup_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="multiscale_breakup",
            func=pass_multiscale_breakup,
            requires_channels=("height",),
            produces_channels=("roughness_variation",),
            seed_namespace="multiscale_breakup",
            requires_scene_read=False,
            description="Bundle K: 3-scale noise breakup into roughness_variation",
        )
    )


__all__ = [
    "compute_multiscale_breakup",
    "pass_multiscale_breakup",
    "register_bundle_k_multiscale_breakup_pass",
]
