"""Bundle J — terrain_audio_zones.

Derives per-cell audio reverb classification from the TerrainMaskStack.
Populates ``stack.audio_reverb_class`` (int8) consumed by Unity reverb
zone proxies (see terrain_semantics.UNITY_EXPORT_CHANNELS).

Pure numpy. No bpy imports. Deterministic given the stack state.
"""

from __future__ import annotations

import time
from enum import IntEnum
from typing import Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


class AudioReverbClass(IntEnum):
    """Encodes audio_reverb_class values stored on the mask stack.

    Maps to Unity AudioReverbZone presets on the consumer side.
    """

    OPEN_FIELD = 0
    FOREST_DENSE = 1
    FOREST_SPARSE = 2
    CAVE = 3
    CANYON = 4
    WATER_NEAR = 5
    MOUNTAIN_HIGH = 6
    INTERIOR = 7


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_audio_reverb_zones(stack: TerrainMaskStack) -> np.ndarray:
    """Return an (H, W) int8 array of AudioReverbClass values.

    Classification priority (highest wins):
        INTERIOR > CAVE > CANYON > WATER_NEAR > MOUNTAIN_HIGH >
        FOREST_DENSE > FOREST_SPARSE > OPEN_FIELD

    Uses these mask signals if present:
        - cave_candidate  -> CAVE
        - physics_collider_mask == 2 (interior)  -> INTERIOR
        - water_surface / wetness high            -> WATER_NEAR
        - curvature strongly concave + high slope -> CANYON
        - height near height_max_m, slope high    -> MOUNTAIN_HIGH
        - biome dense foliage proxies (detail_density sum) -> FOREST_DENSE/SPARSE
        - else OPEN_FIELD
    """
    if stack.height is None:
        raise ValueError("compute_audio_reverb_zones requires stack.height")

    h = np.asarray(stack.height)
    shape = h.shape
    out = np.full(shape, AudioReverbClass.OPEN_FIELD.value, dtype=np.int8)

    # Slope can be derived or present. Fallback: gradient magnitude in radians.
    slope = stack.slope
    if slope is None:
        gy, gx = np.gradient(h.astype(np.float64), float(stack.cell_size))
        slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope = np.asarray(slope, dtype=np.float64)

    # Height min/max
    hmin = float(stack.height_min_m) if stack.height_min_m is not None else float(h.min())
    hmax = float(stack.height_max_m) if stack.height_max_m is not None else float(h.max())
    hspan = max(hmax - hmin, 1e-6)
    h_norm = (h - hmin) / hspan

    # Forest density proxy — sum of detail_density layers if present.
    forest_dense = np.zeros(shape, dtype=bool)
    forest_sparse = np.zeros(shape, dtype=bool)
    if stack.detail_density:
        total = np.zeros(shape, dtype=np.float64)
        for _k, arr in stack.detail_density.items():
            total += np.asarray(arr, dtype=np.float64)
        forest_dense = total > 0.6
        forest_sparse = (total > 0.2) & (~forest_dense)

    # Mountain: high altitude + high slope
    mountain = (h_norm > 0.75) & (slope > np.radians(30.0))

    # Canyon: strong concavity + high slope
    canyon = np.zeros(shape, dtype=bool)
    curv = stack.curvature
    if curv is not None:
        curv_np = np.asarray(curv, dtype=np.float64)
        canyon = (curv_np < -0.15) & (slope > np.radians(25.0))

    # Water-near: water_surface > 0 OR wetness high
    water_near = np.zeros(shape, dtype=bool)
    if stack.water_surface is not None:
        water_near |= np.asarray(stack.water_surface) > 0.0
    if stack.wetness is not None:
        water_near |= np.asarray(stack.wetness) > 0.6

    # Cave candidate
    cave = np.zeros(shape, dtype=bool)
    if stack.cave_candidate is not None:
        cave = np.asarray(stack.cave_candidate) > 0.5

    # Interior (via physics collider mask == 2)
    interior = np.zeros(shape, dtype=bool)
    if stack.physics_collider_mask is not None:
        interior = np.asarray(stack.physics_collider_mask) == 2

    # Apply in priority order (lowest priority first, highest last).
    out[forest_sparse] = AudioReverbClass.FOREST_SPARSE.value
    out[forest_dense] = AudioReverbClass.FOREST_DENSE.value
    out[mountain] = AudioReverbClass.MOUNTAIN_HIGH.value
    out[canyon] = AudioReverbClass.CANYON.value
    out[water_near] = AudioReverbClass.WATER_NEAR.value
    out[cave] = AudioReverbClass.CAVE.value
    out[interior] = AudioReverbClass.INTERIOR.value

    return out


# ---------------------------------------------------------------------------
# Pass wrapper
# ---------------------------------------------------------------------------


def pass_audio_zones(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: populate stack.audio_reverb_class.

    Consumes: height (+ optional slope/curvature/water/cave/detail_density)
    Produces: audio_reverb_class
    Requires scene read: no
    Respects protected zones: yes (read-only, no geometry mutation)
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: list[ValidationIssue] = []

    reverb = compute_audio_reverb_zones(stack)
    stack.set("audio_reverb_class", reverb, "audio_zones")

    # Quick sanity: zones should not be 100% a single class on a varied tile.
    vals, counts = np.unique(reverb, return_counts=True)
    dominant_frac = float(counts.max() / counts.sum())
    if dominant_frac > 0.999 and vals.size == 1 and vals[0] == AudioReverbClass.OPEN_FIELD.value:
        issues.append(
            ValidationIssue(
                code="AUDIO_ZONES_TRIVIAL",
                severity="soft",
                message="all cells classified OPEN_FIELD — upstream masks may be empty",
            )
        )

    return PassResult(
        pass_name="audio_zones",
        status="ok" if not any(i.is_hard() for i in issues) else "failed",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("audio_reverb_class",),
        metrics={
            "class_distribution": {
                int(v): int(c) for v, c in zip(vals.tolist(), counts.tolist())
            },
            "dominant_fraction": dominant_frac,
        },
        issues=issues,
    )


def register_bundle_j_audio_zones_pass() -> None:
    """Register the audio_zones pass on TerrainPassController."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="audio_zones",
            func=pass_audio_zones,
            requires_channels=("height",),
            produces_channels=("audio_reverb_class",),
            seed_namespace="audio_zones",
            requires_scene_read=False,
            may_modify_geometry=False,
            description="Bundle J: classify audio reverb zones from mask stack",
        )
    )


__all__ = [
    "AudioReverbClass",
    "compute_audio_reverb_zones",
    "pass_audio_zones",
    "register_bundle_j_audio_zones_pass",
]
