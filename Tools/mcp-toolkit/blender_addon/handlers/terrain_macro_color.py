"""Bundle K — terrain_macro_color.

Computes a (H, W, 3) float32 macro-color mask blending biome palette with
altitude and wetness modulations. Populates ``stack.macro_color`` for
Unity shader consumption (driven into a 2D lookup texture).

Dark-fantasy palette: desaturated earth tones, mossy greens, ashen peaks,
cold blue-grey waters.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# Biome id -> base RGB (float32 0..1). Dark-fantasy-tuned.
DARK_FANTASY_PALETTE: Dict[int, Tuple[float, float, float]] = {
    0: (0.32, 0.30, 0.24),   # lowland_earth: desaturated umber
    1: (0.22, 0.30, 0.18),   # forest: mossy green
    2: (0.45, 0.42, 0.32),   # grassland: dry olive
    3: (0.38, 0.34, 0.28),   # rocky_slope: weathered stone
    4: (0.50, 0.49, 0.47),   # highland_ash: ashen grey
    5: (0.82, 0.83, 0.88),   # snowcap: cold off-white
    6: (0.18, 0.22, 0.26),   # bog: dark blue-grey
    7: (0.28, 0.25, 0.20),   # scorched: burnt umber
}

DEFAULT_BIOME_ID = 0


def _resolve_palette(palette: Optional[Dict]) -> Dict[int, Tuple[float, float, float]]:
    if palette is None:
        return DARK_FANTASY_PALETTE
    out: Dict[int, Tuple[float, float, float]] = {}
    for k, v in palette.items():
        try:
            ki = int(k)
        except (TypeError, ValueError):
            continue
        arr = tuple(float(x) for x in v)
        if len(arr) != 3:
            continue
        out[ki] = arr  # type: ignore[assignment]
    if not out:
        return DARK_FANTASY_PALETTE
    return out


def compute_macro_color(
    stack: TerrainMaskStack,
    palette: Optional[Dict] = None,
) -> np.ndarray:
    """Return (H, W, 3) float32 macro-color map.

    Blend model:
        base = palette[biome_id]
        darken for wetness (wet ground darker)
        blue-shift for snow_line_factor (when altitude crosses snow line)
        altitude gradient: higher = slightly cooler/desaturated
    """
    if stack.height is None:
        raise ValueError("compute_macro_color requires stack.height")

    pal = _resolve_palette(palette)
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape

    hmin = float(stack.height_min_m) if stack.height_min_m is not None else float(h.min())
    hmax = float(stack.height_max_m) if stack.height_max_m is not None else float(h.max())
    hspan = max(hmax - hmin, 1e-6)
    h_norm = (h - hmin) / hspan  # 0..1

    # Base color: resolve per-cell biome id or default
    biome = stack.get("biome_id")
    color = np.zeros((rows, cols, 3), dtype=np.float64)
    default_rgb = np.array(pal.get(DEFAULT_BIOME_ID, (0.3, 0.3, 0.3)), dtype=np.float64)
    color[:] = default_rgb.reshape(1, 1, 3)
    if biome is not None:
        biome_arr = np.asarray(biome).astype(np.int32, copy=False)
        for bid, rgb in pal.items():
            mask = biome_arr == bid
            if np.any(mask):
                color[mask] = np.array(rgb, dtype=np.float64)

    # Wetness darkens
    wet = stack.get("wetness")
    if wet is not None:
        wet_arr = np.clip(np.asarray(wet, dtype=np.float64), 0.0, 1.0)
        # darken up to 35%
        color = color * (1.0 - 0.35 * wet_arr[..., None])

    # Altitude cool shift (Z-up): above 0.7 h_norm shift toward blue-grey
    alt_mix = np.clip((h_norm - 0.6) / 0.4, 0.0, 1.0)[..., None]
    cool_target = np.array([0.55, 0.58, 0.65], dtype=np.float64).reshape(1, 1, 3)
    color = color * (1.0 - alt_mix * 0.4) + cool_target * alt_mix * 0.4

    # Snow line overlay
    snow = stack.get("snow_line_factor")
    if snow is not None:
        snow_arr = np.clip(np.asarray(snow, dtype=np.float64), 0.0, 1.0)[..., None]
        snow_rgb = np.array([0.86, 0.88, 0.92], dtype=np.float64).reshape(1, 1, 3)
        color = color * (1.0 - snow_arr) + snow_rgb * snow_arr

    return np.clip(color, 0.0, 1.0).astype(np.float32)


def pass_macro_color(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle K pass: macro color mask.

    Consumes: height (+ optional biome_id, wetness, snow_line_factor)
    Produces: macro_color
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    hints = state.intent.composition_hints if state.intent else {}
    palette = hints.get("macro_color_palette")

    color = compute_macro_color(stack, palette=palette)
    stack.set("macro_color", color, "macro_color")

    return PassResult(
        pass_name="macro_color",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("macro_color",),
        metrics={
            "rgb_mean": [float(color[..., i].mean()) for i in range(3)],
            "rgb_std": [float(color[..., i].std()) for i in range(3)],
            "palette_size": len(_resolve_palette(palette)),
        },
        issues=[],
    )


def register_bundle_k_macro_color_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="macro_color",
            func=pass_macro_color,
            requires_channels=("height",),
            produces_channels=("macro_color",),
            seed_namespace="macro_color",
            requires_scene_read=False,
            description="Bundle K: macro color map from biome/wetness/altitude",
        )
    )


__all__ = [
    "DARK_FANTASY_PALETTE",
    "compute_macro_color",
    "pass_macro_color",
    "register_bundle_k_macro_color_pass",
]
