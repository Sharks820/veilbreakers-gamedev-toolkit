"""Bundle J — terrain_gameplay_zones.

Classifies each cell into a GameplayZoneType based on stack signals and
authoring intent hints. Populates ``stack.gameplay_zone`` (int32), which
feeds Unity gameplay trigger volumes.
"""

from __future__ import annotations

import time
from enum import IntEnum
from typing import Any, Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


class GameplayZoneType(IntEnum):
    SAFE = 0
    COMBAT = 1
    STEALTH = 2
    EXPLORATION = 3
    BOSS_ARENA = 4
    NARRATIVE = 5
    PUZZLE = 6


def compute_gameplay_zones(
    stack: TerrainMaskStack,
    intent: Optional[Any] = None,
) -> np.ndarray:
    """Return an (H, W) int32 array of GameplayZoneType values.

    Heuristics (lowest priority first, highest last):
      - default EXPLORATION
      - SAFE: low slope, near water, basin/flat
      - COMBAT: moderate open terrain, traversable
      - STEALTH: high saliency / forest density / concave curvature
      - PUZZLE: cave_candidate regions
      - NARRATIVE: within hero feature footprint (from intent)
      - BOSS_ARENA: authored via intent.composition_hints['boss_arena_bbox']
    """
    if stack.height is None:
        raise ValueError("compute_gameplay_zones requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    shape = h.shape
    out = np.full(shape, GameplayZoneType.EXPLORATION.value, dtype=np.int32)

    slope = stack.slope
    if slope is None:
        gy, gx = np.gradient(h, float(stack.cell_size))
        slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(np.asarray(slope, dtype=np.float64))

    # SAFE: low slope + basin OR near water
    safe = slope_deg < 8.0
    if stack.basin is not None:
        safe &= np.asarray(stack.basin) > 0
    # COMBAT: moderately flat & open
    combat = (slope_deg < 20.0) & (slope_deg >= 8.0)

    # STEALTH: forest_dense proxy or concave curvature
    stealth = np.zeros(shape, dtype=bool)
    if stack.detail_density:
        total = np.zeros(shape, dtype=np.float64)
        for arr in stack.detail_density.values():
            total += np.asarray(arr, dtype=np.float64)
        stealth |= total > 0.5
    if stack.curvature is not None:
        stealth |= np.asarray(stack.curvature) < -0.1

    puzzle = (
        np.asarray(stack.cave_candidate) > 0.5
        if stack.cave_candidate is not None
        else np.zeros(shape, dtype=bool)
    )

    # Apply priority (later overrides earlier)
    out[safe] = GameplayZoneType.SAFE.value
    out[combat] = GameplayZoneType.COMBAT.value
    out[stealth] = GameplayZoneType.STEALTH.value
    out[puzzle] = GameplayZoneType.PUZZLE.value

    # NARRATIVE from hero features
    if intent is not None and getattr(intent, "hero_feature_specs", ()):
        for hero in intent.hero_feature_specs:
            bounds = getattr(hero, "bounds", None)
            if bounds is None:
                continue
            r_slice, c_slice = bounds.to_cell_slice(
                stack.world_origin_x,
                stack.world_origin_y,
                stack.cell_size,
                shape,
            )
            out[r_slice, c_slice] = GameplayZoneType.NARRATIVE.value

    # BOSS_ARENA from composition_hints
    if intent is not None:
        hint = getattr(intent, "composition_hints", {}).get("boss_arena_bbox")
        if hint is not None and isinstance(hint, BBox):
            r_slice, c_slice = hint.to_cell_slice(
                stack.world_origin_x,
                stack.world_origin_y,
                stack.cell_size,
                shape,
            )
            out[r_slice, c_slice] = GameplayZoneType.BOSS_ARENA.value

    return out


def pass_gameplay_zones(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: classify gameplay zones.

    Consumes: height, slope (optional), curvature (optional), basin (optional)
    Produces: gameplay_zone
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    zones = compute_gameplay_zones(stack, state.intent)
    stack.set("gameplay_zone", zones, "gameplay_zones")

    vals, counts = np.unique(zones, return_counts=True)
    issues: list[ValidationIssue] = []

    return PassResult(
        pass_name="gameplay_zones",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("gameplay_zone",),
        metrics={
            "zone_distribution": {
                int(v): int(c) for v, c in zip(vals.tolist(), counts.tolist())
            }
        },
        issues=issues,
    )


def register_bundle_j_gameplay_zones_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="gameplay_zones",
            func=pass_gameplay_zones,
            requires_channels=("height",),
            produces_channels=("gameplay_zone",),
            seed_namespace="gameplay_zones",
            requires_scene_read=False,
            description="Bundle J: classify gameplay zones from mask stack + intent",
        )
    )


__all__ = [
    "GameplayZoneType",
    "compute_gameplay_zones",
    "pass_gameplay_zones",
    "register_bundle_j_gameplay_zones_pass",
]
