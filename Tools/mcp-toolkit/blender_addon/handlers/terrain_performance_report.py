"""Addendum 3.B.4 — real TerrainPerformanceReport collector.

CRITICAL: never returns fake ``ok``. If inputs are missing, returns
``not_available``. The previous ``lambda params: {"status": "ok", ...}``
stub false-passed the performance gate and is now dead code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np

from .terrain_semantics import TerrainMaskStack


DEFAULT_BUDGETS: Dict[str, int] = {
    "terrain": 500_000,
    "water": 50_000,
    "foliage": 200_000,
    "rock": 100_000,
    "cliff": 150_000,
}


@dataclass
class TerrainPerformanceReport:
    """Scene-wide performance rollup.

    All counts are actual measurements — the collector never emits a
    fake ``ok`` status when inputs are missing.
    """

    triangle_count: Dict[str, int] = field(default_factory=dict)
    instance_count: Dict[str, int] = field(default_factory=dict)
    material_count: int = 0
    draw_call_proxy: int = 0
    texture_memory_mb: float = 0.0
    within_budget: Dict[str, bool] = field(default_factory=dict)
    status: str = "not_available"


def _channel_bytes(arr: Optional[np.ndarray]) -> int:
    if arr is None:
        return 0
    return int(arr.size) * int(arr.dtype.itemsize)


def collect_performance_report(
    stack: TerrainMaskStack,
    *,
    budgets: Optional[Dict[str, int]] = None,
) -> TerrainPerformanceReport:
    """Compute a real TerrainPerformanceReport from a mask stack.

    - Triangle estimate: two triangles per cell -> ``tile_size**2 * 2``.
      Split across categories as: terrain=full grid, water = wetness>0
      cells * 2, foliage = detail_density total * 2, rock = rock_hardness
      populated cells * 2, cliff = cliff_candidate cells * 2.
    - Instance count: ``tree_instance_points`` row count for "trees" +
      sums of ``detail_density`` dict for "detail_<type>".
    - Material count: ``splatmap_weights_layer.shape[2]`` if present, else 0.
    - Draw-call proxy: ``material_count + nonzero_channel_count``.
    - Texture memory: sum of ``_ARRAY_CHANNELS`` bytes / 1e6.
    - Status: ``ok`` iff every budget True; ``over_budget`` if any False;
      ``not_available`` if height is missing/empty.
    """
    budgets = dict(budgets) if budgets is not None else dict(DEFAULT_BUDGETS)

    report = TerrainPerformanceReport()

    # Bail out if critical inputs are missing — never fake ok.
    if stack is None or stack.height is None or stack.height.size == 0:
        report.status = "not_available"
        return report

    h, w = stack.height.shape
    base_tris = int(h * w * 2)

    # Per-category triangle estimate
    tri = {"terrain": base_tris, "water": 0, "foliage": 0, "rock": 0, "cliff": 0}

    if stack.wetness is not None:
        wet_cells = int((stack.wetness > 0.0).sum())
        tri["water"] = wet_cells * 2

    if stack.detail_density:
        foliage_cells = 0
        for v in stack.detail_density.values():
            if v is not None:
                foliage_cells += int((v > 0.0).sum())
        tri["foliage"] = foliage_cells * 2

    if stack.rock_hardness is not None:
        rock_cells = int((stack.rock_hardness > 0.0).sum())
        tri["rock"] = rock_cells * 2

    if stack.cliff_candidate is not None:
        cliff_cells = int((stack.cliff_candidate > 0.5).sum())
        tri["cliff"] = cliff_cells * 2

    report.triangle_count = tri

    # Instance counts
    instances: Dict[str, int] = {}
    if stack.tree_instance_points is not None and stack.tree_instance_points.ndim == 2:
        instances["trees"] = int(stack.tree_instance_points.shape[0])
    else:
        instances["trees"] = 0
    if stack.detail_density:
        for k, v in stack.detail_density.items():
            instances[f"detail_{k}"] = int(
                np.sum(v) if v is not None else 0
            )
    report.instance_count = instances

    # Material count (Unity Terrain Layer count)
    if (
        stack.splatmap_weights_layer is not None
        and stack.splatmap_weights_layer.ndim == 3
    ):
        report.material_count = int(stack.splatmap_weights_layer.shape[2])
    else:
        report.material_count = 0

    # Draw-call proxy
    nonzero_channels = 0
    for name in (
        "height",
        "slope",
        "wetness",
        "cliff_candidate",
        "flow_accumulation",
        "biome_id",
        "macro_color",
        "splatmap_weights_layer",
        "rock_hardness",
    ):
        arr = getattr(stack, name, None)
        if arr is not None and getattr(arr, "size", 0) > 0:
            nonzero_channels += 1
    report.draw_call_proxy = report.material_count + nonzero_channels

    # Texture memory (MB)
    bytes_total = 0
    for name in (
        "height",
        "slope",
        "curvature",
        "wetness",
        "flow_accumulation",
        "cliff_candidate",
        "biome_id",
        "macro_color",
        "splatmap_weights_layer",
        "rock_hardness",
        "heightmap_raw_u16",
        "ambient_occlusion_bake",
    ):
        bytes_total += _channel_bytes(getattr(stack, name, None))
    if stack.detail_density:
        for v in stack.detail_density.values():
            bytes_total += _channel_bytes(v)
    report.texture_memory_mb = bytes_total / 1e6

    # Budget rollup
    within: Dict[str, bool] = {}
    for cat, budget in budgets.items():
        count = tri.get(cat, 0)
        within[cat] = count <= budget
    report.within_budget = within

    report.status = "ok" if all(within.values()) else "over_budget"
    return report


def serialize_performance_report(report: TerrainPerformanceReport) -> Dict[str, Any]:
    return {
        "triangle_count": dict(report.triangle_count),
        "instance_count": dict(report.instance_count),
        "material_count": int(report.material_count),
        "draw_call_proxy": int(report.draw_call_proxy),
        "texture_memory_mb": float(report.texture_memory_mb),
        "within_budget": dict(report.within_budget),
        "status": str(report.status),
    }
