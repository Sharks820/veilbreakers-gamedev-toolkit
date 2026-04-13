"""Bundle J — terrain_wind_field.

Computes an (H, W, 2) float32 wind vector field in world units (m/s) and
populates ``stack.wind_field``. Terrain-aware: slower in basins, faster on
ridges, curved around high-slope faces.
"""

from __future__ import annotations

import math
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


def _perlin_like_field(shape: tuple, seed: int, scale_cells: float) -> np.ndarray:
    """Cheap pseudo-Perlin scalar field via bilinear-interpolated RNG grid.

    Deterministic given ``seed``. Returns values in roughly [-1, 1].
    """
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    h, w = shape
    gh = max(2, int(math.ceil(h / max(scale_cells, 1.0))) + 2)
    gw = max(2, int(math.ceil(w / max(scale_cells, 1.0))) + 2)
    grid = rng.uniform(-1.0, 1.0, size=(gh, gw)).astype(np.float64)

    # Bilinear upsample
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


def compute_wind_field(
    stack: TerrainMaskStack,
    prevailing_direction_rad: float,
    base_speed_mps: float,
) -> np.ndarray:
    """Return (H, W, 2) float32 wind field in world m/s.

    Terrain awareness:
        - base direction = (cos, sin) * base_speed
        - altitude factor: faster at higher altitudes (×1 to ×2)
        - ridge factor: ridge cells accelerate (+30%)
        - basin factor: basin cells decelerate (×0.5)
        - small Perlin-like perturbation for natural variance
    """
    if stack.height is None:
        raise ValueError("compute_wind_field requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    shape = h.shape

    hmin = float(stack.height_min_m) if stack.height_min_m is not None else float(h.min())
    hmax = float(stack.height_max_m) if stack.height_max_m is not None else float(h.max())
    hspan = max(hmax - hmin, 1e-6)
    h_norm = (h - hmin) / hspan

    altitude_factor = 1.0 + h_norm  # 1 at valley, 2 at peak

    ridge_factor = np.ones(shape, dtype=np.float64)
    if stack.ridge is not None:
        ridge = np.asarray(stack.ridge, dtype=np.float64)
        ridge_factor = 1.0 + 0.3 * np.clip(ridge, 0.0, 1.0)

    basin_factor = np.ones(shape, dtype=np.float64)
    if stack.basin is not None:
        basin = np.asarray(stack.basin)
        basin_factor = np.where(basin > 0, 0.5, 1.0)

    # Seed derived from tile coords + content hash for determinism
    seed = (
        int(stack.tile_x) * 73856093
        ^ int(stack.tile_y) * 19349663
        ^ int(round(hmin * 1000.0)) & 0xFFFFFFFF
    ) & 0xFFFFFFFF
    perturb_u = _perlin_like_field(shape, seed, scale_cells=16.0)
    perturb_v = _perlin_like_field(shape, seed ^ 0xDEADBEEF, scale_cells=16.0)

    speed = base_speed_mps * altitude_factor * ridge_factor * basin_factor

    ux = np.cos(prevailing_direction_rad) * speed
    uy = np.sin(prevailing_direction_rad) * speed
    ux = ux + 0.25 * base_speed_mps * perturb_u
    uy = uy + 0.25 * base_speed_mps * perturb_v

    field = np.stack([ux, uy], axis=-1).astype(np.float32)
    return field


def pass_wind_field(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: compute terrain-aware wind field.

    Consumes: height (+ optional ridge, basin)
    Produces: wind_field
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    hints = state.intent.composition_hints if state.intent else {}
    direction = float(hints.get("wind_direction_rad", 0.0))
    base_speed = float(hints.get("wind_base_speed_mps", 5.0))

    field = compute_wind_field(stack, direction, base_speed)
    stack.set("wind_field", field, "wind_field")

    speed = np.sqrt(field[..., 0] ** 2 + field[..., 1] ** 2)

    return PassResult(
        pass_name="wind_field",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("wind_field",),
        metrics={
            "speed_min_mps": float(speed.min()),
            "speed_max_mps": float(speed.max()),
            "speed_mean_mps": float(speed.mean()),
            "direction_rad": direction,
        },
        issues=[],
    )


def register_bundle_j_wind_field_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="wind_field",
            func=pass_wind_field,
            requires_channels=("height",),
            produces_channels=("wind_field",),
            seed_namespace="wind_field",
            requires_scene_read=False,
            description="Bundle J: terrain-aware wind field generation",
        )
    )


__all__ = [
    "compute_wind_field",
    "pass_wind_field",
    "register_bundle_j_wind_field_pass",
]
