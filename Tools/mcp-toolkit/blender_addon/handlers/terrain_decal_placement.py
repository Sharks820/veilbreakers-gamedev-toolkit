"""Bundle J — terrain_decal_placement.

Mask-driven decal density computation. Populates ``stack.decal_density``
(dict[str, (H, W) float32]) — one layer per DecalKind.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Dict, Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


class DecalKind(str, Enum):
    BLOOD_STAIN = "blood_stain"
    MOSS_PATCH = "moss_patch"
    WATER_STAIN = "water_stain"
    CRACK = "crack"
    SCORCH = "scorch"
    FOOTPRINT_TRAIL = "footprint_trail"


def compute_decal_density(stack: TerrainMaskStack, kind: DecalKind) -> np.ndarray:
    """Return (H, W) float32 density in [0, 1] for the given decal kind.

    Each kind uses a different combination of mask signals:
      - MOSS_PATCH: wetness + curvature concave + low slope
      - WATER_STAIN: wetness + basin
      - CRACK: erosion_amount + convex curvature
      - SCORCH: high ridge, high altitude, dry (inverse wetness)
      - BLOOD_STAIN: gameplay_zone == COMBAT + low slope
      - FOOTPRINT_TRAIL: traversability near water
    """
    if stack.height is None:
        raise ValueError("compute_decal_density requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    shape = h.shape

    slope = stack.slope
    if slope is None:
        gy, gx = np.gradient(h, float(stack.cell_size))
        slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_np = np.asarray(slope, dtype=np.float64)

    wetness = (
        np.asarray(stack.wetness, dtype=np.float64)
        if stack.wetness is not None
        else np.zeros(shape, dtype=np.float64)
    )
    curv = (
        np.asarray(stack.curvature, dtype=np.float64)
        if stack.curvature is not None
        else np.zeros(shape, dtype=np.float64)
    )
    erosion = (
        np.asarray(stack.erosion_amount, dtype=np.float64)
        if stack.erosion_amount is not None
        else np.zeros(shape, dtype=np.float64)
    )
    basin = (
        np.asarray(stack.basin, dtype=np.float64)
        if stack.basin is not None
        else np.zeros(shape, dtype=np.float64)
    )
    ridge = (
        np.asarray(stack.ridge, dtype=np.float64)
        if stack.ridge is not None
        else np.zeros(shape, dtype=np.float64)
    )
    gameplay = stack.gameplay_zone
    trav = stack.traversability

    def norm(a: np.ndarray) -> np.ndarray:
        lo, hi = float(a.min()), float(a.max())
        if hi - lo < 1e-9:
            return np.zeros_like(a, dtype=np.float64)
        return (a - lo) / (hi - lo)

    if kind == DecalKind.MOSS_PATCH:
        density = wetness * np.clip(-curv, 0.0, 1.0) * (1.0 - np.clip(slope_np / np.radians(60.0), 0.0, 1.0))
    elif kind == DecalKind.WATER_STAIN:
        density = 0.5 * wetness + 0.5 * (basin > 0).astype(np.float64)
    elif kind == DecalKind.CRACK:
        density = norm(erosion) * np.clip(curv, 0.0, 1.0)
    elif kind == DecalKind.SCORCH:
        hmin = float(stack.height_min_m) if stack.height_min_m is not None else float(h.min())
        hmax = float(stack.height_max_m) if stack.height_max_m is not None else float(h.max())
        h_norm = (h - hmin) / max(hmax - hmin, 1e-6)
        density = np.clip(ridge, 0.0, 1.0) * h_norm * (1.0 - wetness)
    elif kind == DecalKind.BLOOD_STAIN:
        combat_mask = np.zeros(shape, dtype=np.float64)
        if gameplay is not None:
            # COMBAT = 1 from GameplayZoneType
            combat_mask = (np.asarray(gameplay) == 1).astype(np.float64)
        density = combat_mask * (1.0 - np.clip(slope_np / np.radians(30.0), 0.0, 1.0))
    elif kind == DecalKind.FOOTPRINT_TRAIL:
        trav_np = (
            np.asarray(trav, dtype=np.float64)
            if trav is not None
            else np.ones(shape, dtype=np.float64) * 0.5
        )
        water_near = wetness > 0.5
        density = trav_np * water_near.astype(np.float64)
    else:
        density = np.zeros(shape, dtype=np.float64)

    return np.clip(density, 0.0, 1.0).astype(np.float32)


def pass_decals(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: compute per-kind decal density layers."""
    t0 = time.perf_counter()
    stack = state.mask_stack

    layers: Dict[str, np.ndarray] = {}
    for kind in DecalKind:
        layers[kind.value] = compute_decal_density(stack, kind)

    if stack.decal_density is None:
        stack.decal_density = {}
    stack.decal_density.update(layers)
    stack.populated_by_pass["decal_density"] = "decals"

    metrics = {
        name: {
            "peak": float(arr.max()),
            "mean": float(arr.mean()),
            "coverage_frac": float((arr > 0.1).mean()),
        }
        for name, arr in layers.items()
    }

    return PassResult(
        pass_name="decals",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=(),
        metrics=metrics,
    )


def register_bundle_j_decals_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="decals",
            func=pass_decals,
            requires_channels=("height",),
            produces_channels=(),
            seed_namespace="decals",
            requires_scene_read=False,
            description="Bundle J: mask-driven decal density layers",
        )
    )


__all__ = [
    "DecalKind",
    "compute_decal_density",
    "pass_decals",
    "register_bundle_j_decals_pass",
]
