"""Bundle J — terrain_navmesh_export.

Computes Unity NavMeshSurface area classification + traversability
gradient, and exports a JSON descriptor for Unity-side consumption.

Populates:
    stack.navmesh_area_id  — (H, W) int8
    stack.traversability   — (H, W) float32
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# Area IDs — keep stable, Unity side uses the same table.
NAVMESH_UNWALKABLE = 0
NAVMESH_WALKABLE = 1
NAVMESH_CLIMB = 2
NAVMESH_JUMP = 3
NAVMESH_SWIM = 4


def compute_navmesh_area_id(
    stack: TerrainMaskStack,
    max_walkable_slope_deg: float = 45.0,
) -> np.ndarray:
    """Classify each cell into a NavMesh area id.

    Priority (later wins):
        default UNWALKABLE
        slope < max_walkable_slope_deg -> WALKABLE
        cliff_candidate / very steep   -> CLIMB
        waterfall_lip_candidate         -> JUMP
        water_surface > 0              -> SWIM
    """
    if stack.height is None:
        raise ValueError("compute_navmesh_area_id requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    shape = h.shape

    slope = stack.slope
    if slope is None:
        gy, gx = np.gradient(h, float(stack.cell_size))
        slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(np.asarray(slope, dtype=np.float64))

    out = np.full(shape, NAVMESH_UNWALKABLE, dtype=np.int8)
    walkable = slope_deg < float(max_walkable_slope_deg)
    out[walkable] = NAVMESH_WALKABLE

    if stack.cliff_candidate is not None:
        climb = np.asarray(stack.cliff_candidate) > 0.5
        out[climb] = NAVMESH_CLIMB
    steep = slope_deg >= 65.0
    out[steep] = NAVMESH_CLIMB

    if stack.waterfall_lip_candidate is not None:
        jump = np.asarray(stack.waterfall_lip_candidate) > 0.5
        out[jump] = NAVMESH_JUMP

    if stack.water_surface is not None:
        swim = np.asarray(stack.water_surface) > 0.0
        out[swim] = NAVMESH_SWIM

    return out


def compute_traversability(stack: TerrainMaskStack) -> np.ndarray:
    """Return (H, W) float32 in [0, 1] — cost gradient for AI pathing.

    1.0 = easy to traverse, 0.0 = impassable.
    """
    if stack.height is None:
        raise ValueError("compute_traversability requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    _shape = h.shape

    slope = stack.slope
    if slope is None:
        gy, gx = np.gradient(h, float(stack.cell_size))
        slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(np.asarray(slope, dtype=np.float64))

    # Base: 1 - slope/90
    base = 1.0 - np.clip(slope_deg / 90.0, 0.0, 1.0)

    # Penalize water
    if stack.water_surface is not None:
        water = np.asarray(stack.water_surface) > 0.0
        base = np.where(water, base * 0.3, base)

    # Penalize bank_instability / talus
    if stack.bank_instability is not None:
        base = base * (1.0 - 0.5 * np.clip(np.asarray(stack.bank_instability), 0.0, 1.0))
    if stack.talus is not None:
        base = base * (1.0 - 0.3 * np.clip(np.asarray(stack.talus), 0.0, 1.0))

    # Hero exclusion is impassable
    if stack.hero_exclusion is not None:
        base = np.where(np.asarray(stack.hero_exclusion).astype(bool), 0.0, base)

    return np.clip(base, 0.0, 1.0).astype(np.float32)


def export_navmesh_json(stack: TerrainMaskStack, output_path: Path) -> Dict[str, Any]:
    """Write a Unity-consumable navmesh descriptor JSON and return the dict.

    Schema (conforms to plan §33 concept — navmesh descriptor):
        {
          "schema_version": "1.0",
          "tile_x": ..., "tile_y": ...,
          "tile_size": ..., "cell_size_m": ...,
          "world_origin": [x, y],
          "area_ids": { "unwalkable": 0, ..., "swim": 4 },
          "max_walkable_slope_deg": 45.0,
          "stats": {...},
        }
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    navmesh = stack.navmesh_area_id
    if navmesh is None:
        navmesh = compute_navmesh_area_id(stack)
        stack.set("navmesh_area_id", navmesh, "navmesh_export")

    navmesh_np = np.asarray(navmesh)
    vals, counts = np.unique(navmesh_np, return_counts=True)
    total = float(counts.sum())
    distribution = {int(v): int(c) for v, c in zip(vals.tolist(), counts.tolist())}

    descriptor: Dict[str, Any] = {
        "schema_version": "1.0",
        "tile_x": int(stack.tile_x),
        "tile_y": int(stack.tile_y),
        "tile_size": int(stack.tile_size),
        "cell_size_m": float(stack.cell_size),
        "world_origin": [float(stack.world_origin_x), float(stack.world_origin_y)],
        "unity_world_origin": [float(stack.world_origin_x), 0.0, float(stack.world_origin_y)],
        "coordinate_system": "y-up",
        "source_coordinate_system": stack.coordinate_system,
        "area_ids": {
            "unwalkable": NAVMESH_UNWALKABLE,
            "walkable": NAVMESH_WALKABLE,
            "climb": NAVMESH_CLIMB,
            "jump": NAVMESH_JUMP,
            "swim": NAVMESH_SWIM,
        },
        "max_walkable_slope_deg": 45.0,
        "stats": {
            "cell_counts": distribution,
            "walkable_fraction": float(distribution.get(NAVMESH_WALKABLE, 0)) / max(total, 1.0),
            "swim_fraction": float(distribution.get(NAVMESH_SWIM, 0)) / max(total, 1.0),
        },
    }
    output_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True))
    return descriptor


def pass_navmesh(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: compute navmesh area ids + traversability gradient."""
    t0 = time.perf_counter()
    stack = state.mask_stack

    hints = state.intent.composition_hints if state.intent else {}
    max_slope = float(hints.get("navmesh_max_walkable_slope_deg", 45.0))

    area = compute_navmesh_area_id(stack, max_walkable_slope_deg=max_slope)
    stack.set("navmesh_area_id", area, "navmesh")

    trav = compute_traversability(stack)
    stack.set("traversability", trav, "navmesh")

    vals, counts = np.unique(area, return_counts=True)

    return PassResult(
        pass_name="navmesh",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("navmesh_area_id", "traversability"),
        metrics={
            "area_distribution": {
                int(v): int(c) for v, c in zip(vals.tolist(), counts.tolist())
            },
            "walkable_fraction": float((area == NAVMESH_WALKABLE).mean()),
            "mean_traversability": float(trav.mean()),
            "max_walkable_slope_deg": max_slope,
        },
    )


def register_bundle_j_navmesh_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="navmesh",
            func=pass_navmesh,
            requires_channels=("height",),
            produces_channels=("navmesh_area_id", "traversability"),
            seed_namespace="navmesh",
            requires_scene_read=False,
            description="Bundle J: navmesh area classification + traversability gradient",
        )
    )


__all__ = [
    "NAVMESH_UNWALKABLE",
    "NAVMESH_WALKABLE",
    "NAVMESH_CLIMB",
    "NAVMESH_JUMP",
    "NAVMESH_SWIM",
    "compute_navmesh_area_id",
    "compute_traversability",
    "export_navmesh_json",
    "pass_navmesh",
    "register_bundle_j_navmesh_pass",
]
