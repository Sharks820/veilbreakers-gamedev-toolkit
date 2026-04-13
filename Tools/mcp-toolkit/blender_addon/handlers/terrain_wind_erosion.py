"""Bundle I — terrain_wind_erosion.

Aeolian processes: asymmetric smoothing along a prevailing wind vector
(produces yardangs / ventifacts) and procedural dune field generation.

Pure numpy. Returns height deltas — callers decide whether to apply.
"""

from __future__ import annotations

import math
import time
from typing import Optional

import numpy as np

from .terrain_pipeline import derive_pass_seed
from .terrain_semantics import (
    BBox,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# Wind erosion
# ---------------------------------------------------------------------------


def apply_wind_erosion(
    stack: TerrainMaskStack,
    prevailing_dir_rad: float,
    intensity: float,
) -> np.ndarray:
    """Return a height delta from asymmetric wind-direction smoothing.

    The algorithm samples the heightmap ahead and behind each cell along
    ``prevailing_dir_rad`` and blends them asymmetrically — this produces
    streamlined shapes (yardangs) aligned with wind.

    intensity : float in [0, 1], 1 = maximum smoothing
    """
    if stack.height is None:
        raise ValueError("apply_wind_erosion requires stack.height")
    if not (0.0 <= intensity <= 1.0):
        raise ValueError("intensity must be in [0, 1]")

    h = np.asarray(stack.height, dtype=np.float64)
    H, W = h.shape

    dx = math.cos(prevailing_dir_rad)
    dy = math.sin(prevailing_dir_rad)

    # Upwind / downwind shifts (1 cell)
    up = np.roll(h, shift=(-int(round(dy)), -int(round(dx))), axis=(0, 1))
    down = np.roll(h, shift=(int(round(dy)), int(round(dx))), axis=(0, 1))

    # Asymmetric blend: downwind side gets more of the upwind's mass
    blended = 0.5 * h + 0.3 * up + 0.2 * down
    delta = (blended - h) * intensity

    # Harder rocks resist
    if stack.rock_hardness is not None:
        hardness = np.asarray(stack.rock_hardness, dtype=np.float64)
        delta = delta * (1.0 - 0.7 * np.clip(hardness, 0.0, 1.0))

    return delta


# ---------------------------------------------------------------------------
# Dune generation
# ---------------------------------------------------------------------------


def generate_dunes(
    stack: TerrainMaskStack,
    wind_dir: float,
    seed: int,
) -> np.ndarray:
    """Generate a dune-field height delta aligned perpendicular to wind.

    Produces a sinusoidal ridge pattern whose crests run perpendicular
    to the wind vector, with amplitude modulated by low-frequency noise
    so the field isn't uniform.
    """
    if stack.height is None:
        raise ValueError("generate_dunes requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    H, W = h.shape

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)

    # Coordinate grid in cells
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float64)

    # Wind-aligned coordinate
    _u = xs * math.cos(wind_dir) + ys * math.sin(wind_dir)
    # Perpendicular (dune crest) coordinate
    v = -xs * math.sin(wind_dir) + ys * math.cos(wind_dir)

    # Dune wavelength ~10 cells. Crests perpendicular to wind → depend on v.
    wavelength = 10.0
    crest = np.sin(2.0 * math.pi * v / wavelength)
    # Asymmetric profile: steeper lee (downwind) side. Guard against
    # negative bases being raised to fractional powers by splitting on sign.
    pos = np.where(crest > 0, crest, 0.0)
    neg = np.where(crest < 0, -crest, 0.0)
    crest = np.power(pos, 0.7) - np.power(neg, 1.3)

    # Low-frequency amplitude modulation for natural variation
    lfmod_gh = max(4, H // 8)
    lfmod_gw = max(4, W // 8)
    lf = rng.uniform(0.3, 1.0, size=(lfmod_gh, lfmod_gw))
    # Bilinear upsample
    ys_i = np.linspace(0.0, lfmod_gh - 1.0, H)
    xs_i = np.linspace(0.0, lfmod_gw - 1.0, W)
    y0 = np.floor(ys_i).astype(np.int32)
    x0 = np.floor(xs_i).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, lfmod_gh - 1)
    x1 = np.clip(x0 + 1, 0, lfmod_gw - 1)
    ty = (ys_i - y0).reshape(-1, 1)
    tx = (xs_i - x0).reshape(1, -1)
    a = lf[np.ix_(y0, x0)]
    b = lf[np.ix_(y0, x1)]
    c = lf[np.ix_(y1, x0)]
    d = lf[np.ix_(y1, x1)]
    mod = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty

    amplitude = 2.0  # meters
    delta = crest * mod * amplitude
    return delta.astype(np.float64)


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


def pass_wind_erosion(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle I pass: apply wind erosion + optional dune generation.

    Consumes: height (+ optional rock_hardness)
    Produces: height (mutated) — also records wind_field if absent

    Does not produce new named channels; it mutates the height channel
    in place to integrate aeolian processes.
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    hints = dict(state.intent.composition_hints) if state.intent else {}
    wind_dir = float(hints.get("wind_direction_rad", 0.0))
    intensity = float(hints.get("wind_erosion_intensity", 0.3))
    dune_enabled = bool(hints.get("wind_dunes_enabled", False))

    seed = derive_pass_seed(
        state.intent.seed,
        "wind_erosion",
        state.tile_x,
        state.tile_y,
        region,
    )

    erosion_delta = apply_wind_erosion(stack, wind_dir, intensity)

    dune_delta_sum = 0.0
    total_delta = erosion_delta.copy()
    if dune_enabled:
        dunes = generate_dunes(stack, wind_dir, seed)
        total_delta = total_delta + dunes
        dune_delta_sum = float(np.abs(dunes).mean())

    stack.set("wind_erosion_delta", total_delta.astype(np.float32), "wind_erosion")

    return PassResult(
        pass_name="wind_erosion",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("wind_erosion_delta",),
        metrics={
            "wind_direction_rad": wind_dir,
            "intensity": intensity,
            "mean_erosion_delta_m": float(np.abs(erosion_delta).mean()),
            "mean_dune_delta_m": dune_delta_sum,
            "dunes_enabled": dune_enabled,
        },
        issues=[],
    )


__all__ = [
    "apply_wind_erosion",
    "generate_dunes",
    "pass_wind_erosion",
]
