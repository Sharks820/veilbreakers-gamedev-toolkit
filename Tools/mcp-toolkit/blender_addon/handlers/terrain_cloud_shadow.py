"""Bundle J — terrain_cloud_shadow.

Procedural cloud shadow mask (H, W) float32 in [0, 1], populating
``stack.cloud_shadow``. Unity consumes this as a directional shadow
cookie.
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


def _value_noise(shape: tuple, seed: int, scale_cells: float) -> np.ndarray:
    """Smooth value-noise scalar field in [0, 1]."""
    import math

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    h, w = shape
    gh = max(2, int(math.ceil(h / max(scale_cells, 1.0))) + 2)
    gw = max(2, int(math.ceil(w / max(scale_cells, 1.0))) + 2)
    grid = rng.uniform(0.0, 1.0, size=(gh, gw)).astype(np.float64)

    ys = np.linspace(0.0, gh - 1.0, h)
    xs = np.linspace(0.0, gw - 1.0, w)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, gh - 1)
    x1 = np.clip(x0 + 1, 0, gw - 1)
    ty = (ys - y0).reshape(-1, 1)
    tx = (xs - x0).reshape(1, -1)
    # Smoothstep
    ty = ty * ty * (3 - 2 * ty)
    tx = tx * tx * (3 - 2 * tx)

    a = grid[np.ix_(y0, x0)]
    b = grid[np.ix_(y0, x1)]
    c = grid[np.ix_(y1, x0)]
    d = grid[np.ix_(y1, x1)]
    top = a * (1 - tx) + b * tx
    bot = c * (1 - tx) + d * tx
    return top * (1 - ty) + bot * ty


def compute_cloud_shadow_mask(
    stack: TerrainMaskStack,
    seed: int,
    cloud_density: float = 0.4,
    cloud_scale_m: float = 500.0,
) -> np.ndarray:
    """Generate a smooth cloud shadow mask in [0, 1].

    Higher density => more shaded cells. 0 = full sun, 1 = full shadow.
    """
    if stack.height is None:
        raise ValueError("compute_cloud_shadow_mask requires stack.height")

    shape = stack.height.shape
    scale_cells = max(cloud_scale_m / max(stack.cell_size, 1e-6), 4.0)

    # Two octaves of value noise
    n1 = _value_noise(shape, seed, scale_cells)
    n2 = _value_noise(shape, seed ^ 0x9E3779B1, scale_cells * 0.5)
    combined = 0.65 * n1 + 0.35 * n2

    # Threshold-based shadow formation — remap so that `cloud_density` of
    # cells are > 0.5 shaded.
    density = float(np.clip(cloud_density, 0.0, 1.0))
    threshold = 1.0 - density
    shadow = np.clip((combined - threshold) / max(density, 1e-3), 0.0, 1.0)
    return shadow.astype(np.float32)


def pass_cloud_shadow(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: procedural cloud shadow mask."""
    t0 = time.perf_counter()
    stack = state.mask_stack

    hints = state.intent.composition_hints if state.intent else {}
    density = float(hints.get("cloud_density", 0.4))
    scale_m = float(hints.get("cloud_scale_m", 500.0))

    # Use intent.seed blended with tile coords for per-tile determinism.
    seed = (
        (int(state.intent.seed) if state.intent else 0)
        ^ (int(stack.tile_x) * 374761393)
        ^ (int(stack.tile_y) * 668265263)
    ) & 0xFFFFFFFF

    mask = compute_cloud_shadow_mask(stack, seed, density, scale_m)
    stack.set("cloud_shadow", mask, "cloud_shadow")

    return PassResult(
        pass_name="cloud_shadow",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("cloud_shadow",),
        metrics={
            "coverage_frac": float((mask > 0.5).mean()),
            "mean": float(mask.mean()),
            "density_param": density,
            "scale_m": scale_m,
        },
    )


def register_bundle_j_cloud_shadow_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="cloud_shadow",
            func=pass_cloud_shadow,
            requires_channels=("height",),
            produces_channels=("cloud_shadow",),
            seed_namespace="cloud_shadow",
            requires_scene_read=False,
            description="Bundle J: procedural cloud shadow mask",
        )
    )


__all__ = [
    "compute_cloud_shadow_mask",
    "pass_cloud_shadow",
    "register_bundle_j_cloud_shadow_pass",
]
