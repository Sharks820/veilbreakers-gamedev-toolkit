"""Bundle N — per-tile budget enforcement.

Guards tile authoring against AAA ship budgets: hero feature density,
triangle count, unique material count, scatter instance count, mask
archive size. Emits ``ValidationIssue`` entries when any budget is
exceeded so the controller can downgrade or roll back.

Pure numpy — no bpy. See plan §19.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .terrain_semantics import (
    TerrainIntentState,
    TerrainMaskStack,
    ValidationIssue,
)


@dataclass
class TerrainBudget:
    """Ship-grade per-tile authoring budgets."""

    max_hero_features_per_km2: float = 4.0
    max_tri_count: int = 1_500_000
    max_unique_materials: int = 12
    max_scatter_instances: int = 250_000
    max_npz_mb: float = 64.0
    # Soft-warn thresholds as a fraction of max (default 80%)
    warn_fraction: float = 0.80


def _km2_from_stack(stack: TerrainMaskStack) -> float:
    cs = float(stack.cell_size) if stack.cell_size else 1.0
    area_m2 = float(stack.tile_size) * cs * float(stack.tile_size) * cs
    return max(area_m2 / 1_000_000.0, 1e-9)


def _count_unique_materials(stack: TerrainMaskStack) -> int:
    weights = stack.get("splatmap_weights_layer")
    if weights is None:
        return 0
    arr = np.asarray(weights)
    if arr.ndim != 3:
        return 0
    # Layer is "present" if any cell has weight > 0.01
    present = int(np.sum(np.any(arr > 0.01, axis=(0, 1))))
    return present


def _count_scatter_instances(stack: TerrainMaskStack) -> int:
    tree = stack.get("tree_instance_points")
    total = 0
    if tree is not None:
        total += int(np.asarray(tree).shape[0])
    # detail_density dict: sum populated instance estimates
    detail = getattr(stack, "detail_density", None)
    if isinstance(detail, dict):
        for _k, v in detail.items():
            arr = np.asarray(v, dtype=np.float64)
            # Per-cell density is instances per cell; clamp to finite
            finite = arr[np.isfinite(arr)]
            if finite.size:
                total += int(max(0.0, float(np.sum(finite))))
    return total


def _estimate_tri_count(stack: TerrainMaskStack) -> int:
    """Heuristic: two triangles per heightmap cell."""
    h = stack.get("height")
    if h is None:
        return 0
    arr = np.asarray(h)
    if arr.ndim != 2:
        return 0
    rows, cols = arr.shape
    if rows < 2 or cols < 2:
        return 0
    return int(2 * (rows - 1) * (cols - 1))


def _estimate_npz_mb(stack: TerrainMaskStack) -> float:
    total_bytes = 0
    for name in stack._ARRAY_CHANNELS:
        val = getattr(stack, name, None)
        if val is None:
            continue
        arr = np.asarray(val)
        total_bytes += int(arr.nbytes)
    return float(total_bytes) / (1024.0 * 1024.0)


def compute_tile_budget_usage(
    stack: TerrainMaskStack,
    budget: Optional[TerrainBudget] = None,
    intent: Optional[TerrainIntentState] = None,
) -> Dict[str, Any]:
    """Compute current-vs-max usage for each budget axis."""
    b = budget or TerrainBudget()
    km2 = _km2_from_stack(stack)

    hero_count = 0
    if intent is not None:
        hero_count = len(intent.hero_feature_specs)
    hero_per_km2 = hero_count / km2 if km2 > 0 else 0.0

    tri_count = _estimate_tri_count(stack)
    unique_materials = _count_unique_materials(stack)
    scatter = _count_scatter_instances(stack)
    npz_mb = _estimate_npz_mb(stack)

    return {
        "tile_km2": km2,
        "hero_features": hero_count,
        "hero_per_km2": {
            "current": hero_per_km2,
            "max": b.max_hero_features_per_km2,
            "utilization": hero_per_km2 / max(b.max_hero_features_per_km2, 1e-9),
        },
        "tri_count": {
            "current": tri_count,
            "max": b.max_tri_count,
            "utilization": tri_count / max(b.max_tri_count, 1),
        },
        "unique_materials": {
            "current": unique_materials,
            "max": b.max_unique_materials,
            "utilization": unique_materials / max(b.max_unique_materials, 1),
        },
        "scatter_instances": {
            "current": scatter,
            "max": b.max_scatter_instances,
            "utilization": scatter / max(b.max_scatter_instances, 1),
        },
        "npz_mb": {
            "current": npz_mb,
            "max": b.max_npz_mb,
            "utilization": npz_mb / max(b.max_npz_mb, 1e-9),
        },
    }


def _issue_for(
    axis: str,
    current: float,
    max_: float,
    warn_fraction: float,
    code_hard: str,
    code_soft: str,
    unit: str,
) -> Optional[ValidationIssue]:
    if current > max_:
        return ValidationIssue(
            code=code_hard,
            severity="hard",
            message=(
                f"{axis}={current:.2f}{unit} exceeds budget {max_:.2f}{unit}"
            ),
            remediation=f"Reduce {axis} or raise the ship budget.",
        )
    if current > max_ * warn_fraction:
        return ValidationIssue(
            code=code_soft,
            severity="soft",
            message=(
                f"{axis}={current:.2f}{unit} approaching budget "
                f"{max_:.2f}{unit} ({(current / max_) * 100:.1f}% used)"
            ),
        )
    return None


def enforce_budget(
    stack: TerrainMaskStack,
    intent: TerrainIntentState,
    budget: TerrainBudget,
) -> List[ValidationIssue]:
    """Compare usage against budget, return all violations as ValidationIssue."""
    usage = compute_tile_budget_usage(stack, budget=budget, intent=intent)
    issues: List[ValidationIssue] = []

    checks = [
        ("hero_per_km2", "hero_per_km2", budget.max_hero_features_per_km2,
         "BUDGET_HERO_DENSITY_EXCEEDED", "BUDGET_HERO_DENSITY_NEAR", "/km2"),
        ("tri_count", "tri_count", float(budget.max_tri_count),
         "BUDGET_TRI_EXCEEDED", "BUDGET_TRI_NEAR", " tris"),
        ("unique_materials", "unique_materials", float(budget.max_unique_materials),
         "BUDGET_MATERIALS_EXCEEDED", "BUDGET_MATERIALS_NEAR", " mats"),
        ("scatter_instances", "scatter_instances", float(budget.max_scatter_instances),
         "BUDGET_SCATTER_EXCEEDED", "BUDGET_SCATTER_NEAR", " instances"),
        ("npz_mb", "npz_mb", float(budget.max_npz_mb),
         "BUDGET_NPZ_SIZE_EXCEEDED", "BUDGET_NPZ_SIZE_NEAR", " MB"),
    ]
    for axis, key, max_val, code_hard, code_soft, unit in checks:
        current = float(usage[key]["current"])
        issue = _issue_for(
            axis, current, max_val, budget.warn_fraction,
            code_hard, code_soft, unit,
        )
        if issue is not None:
            issues.append(issue)
    return issues


__all__ = [
    "TerrainBudget",
    "compute_tile_budget_usage",
    "enforce_budget",
]
