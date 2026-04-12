"""Bundle I — terrain_geology_validator.

Validation helpers for geology plausibility. Also owns the
``register_bundle_i_passes()`` registrar for all Bundle I passes.

Pure numpy, no bpy.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from .terrain_semantics import (
    TerrainMaskStack,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_strata_consistency(
    stack: TerrainMaskStack,
    tol_deg: float = 5.0,
) -> List[ValidationIssue]:
    """Strata orientation must vary smoothly over the tile.

    We check that the angular difference between each cell's bedding
    normal and its 4-neighbor average is under ``tol_deg`` degrees.
    Returns a soft issue if more than 5% of cells exceed the tolerance.
    """
    issues: List[ValidationIssue] = []
    orient = stack.strata_orientation
    if orient is None:
        issues.append(
            ValidationIssue(
                code="STRATA_MISSING",
                severity="soft",
                message="strata_orientation channel not populated",
            )
        )
        return issues

    arr = np.asarray(orient, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[-1] != 3:
        issues.append(
            ValidationIssue(
                code="STRATA_BAD_SHAPE",
                severity="hard",
                message=f"strata_orientation must be (H,W,3), got {arr.shape}",
            )
        )
        return issues

    # Smoothed orientation (4-neighbor mean, not including self)
    up = np.roll(arr, shift=1, axis=0)
    down = np.roll(arr, shift=-1, axis=0)
    left = np.roll(arr, shift=1, axis=1)
    right = np.roll(arr, shift=-1, axis=1)
    avg = (up + down + left + right) / 4.0

    # Normalize both
    def _norm(v: np.ndarray) -> np.ndarray:
        n = np.sqrt((v * v).sum(axis=-1, keepdims=True))
        return v / np.where(n < 1e-9, 1.0, n)

    a = _norm(arr)
    b = _norm(avg)
    dot = np.clip((a * b).sum(axis=-1), -1.0, 1.0)
    angle_deg = np.degrees(np.arccos(dot))

    # Strip edges (roll introduces wrap artifacts)
    inner = angle_deg[1:-1, 1:-1]
    if inner.size == 0:
        return issues

    violation_frac = float((inner > tol_deg).mean())
    if violation_frac > 0.05:
        issues.append(
            ValidationIssue(
                code="STRATA_INCONSISTENT",
                severity="soft",
                message=(
                    f"{violation_frac*100:.1f}% of cells exceed "
                    f"{tol_deg}° strata-orientation tolerance"
                ),
                remediation="reduce dip variance or increase smoothing",
            )
        )
    return issues


def validate_strahler_ordering(
    water_network: Optional[Any],
) -> List[ValidationIssue]:
    """Check Strahler stream-ordering hierarchy for plausibility.

    Accepts a ``water_network`` with attribute ``streams`` (iterable of
    objects with ``order``, ``parent_order``) OR a dict with key
    ``streams`` containing similar entries. Returns a soft issue for any
    stream whose order exceeds its parent's order + 1 (geologically
    implausible tributary).
    """
    issues: List[ValidationIssue] = []
    if water_network is None:
        return issues

    streams: Optional[Iterable[Any]] = None
    if hasattr(water_network, "streams"):
        streams = getattr(water_network, "streams")
    elif isinstance(water_network, dict) and "streams" in water_network:
        streams = water_network["streams"]

    if streams is None:
        return issues

    def _get(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    for idx, s in enumerate(streams):
        order = _get(s, "order")
        parent_order = _get(s, "parent_order")
        if order is None or parent_order is None:
            continue
        if int(order) > int(parent_order) + 1:
            issues.append(
                ValidationIssue(
                    code="STRAHLER_JUMP",
                    severity="soft",
                    affected_feature=f"stream_{idx}",
                    message=(
                        f"stream order {order} exceeds parent order "
                        f"{parent_order} + 1 — implausible tributary"
                    ),
                )
            )
    return issues


def validate_glacial_plausibility(
    stack: TerrainMaskStack,
    glacier_paths: Sequence[Dict[str, Any]],
    tree_line_altitude_m: float = 1800.0,
) -> List[ValidationIssue]:
    """U-valleys should be carved only above the tree line.

    For every point in every glacier path, verify the underlying
    ``stack.height`` is at or above ``tree_line_altitude_m``. Reports a
    hard issue per path that dips too low.
    """
    issues: List[ValidationIssue] = []
    if stack.height is None:
        return issues
    h = np.asarray(stack.height, dtype=np.float64)
    H, W = h.shape

    for i, gp in enumerate(glacier_paths):
        path = gp.get("path", []) if isinstance(gp, dict) else []
        if not path:
            continue
        too_low_count = 0
        for (wx, wy) in path:
            c = int(round((wx - stack.world_origin_x) / stack.cell_size))
            r = int(round((wy - stack.world_origin_y) / stack.cell_size))
            if not (0 <= r < H and 0 <= c < W):
                continue
            if h[r, c] < tree_line_altitude_m:
                too_low_count += 1
        if too_low_count > 0:
            issues.append(
                ValidationIssue(
                    code="GLACIER_BELOW_TREELINE",
                    severity="hard",
                    affected_feature=f"glacier_{i}",
                    message=(
                        f"{too_low_count} points of glacier_{i} lie below "
                        f"tree line {tree_line_altitude_m} m"
                    ),
                    remediation="raise glacier path or lower tree line",
                )
            )
    return issues


def validate_karst_plausibility(
    stack: TerrainMaskStack,
    karst_features: Sequence[Any],
    min_hardness: float = 0.35,
    max_hardness: float = 0.75,
) -> List[ValidationIssue]:
    """Karst should only form in soluble rock (limestone-like hardness).

    Reports a hard issue for any feature whose local ``rock_hardness``
    falls outside [min_hardness, max_hardness].
    """
    issues: List[ValidationIssue] = []
    if stack.rock_hardness is None:
        return issues
    hardness = np.asarray(stack.rock_hardness, dtype=np.float64)
    H, W = hardness.shape

    for f in karst_features:
        pos = getattr(f, "world_pos", None) or (
            f.get("world_pos") if isinstance(f, dict) else None
        )
        fid = getattr(f, "feature_id", None) or (
            f.get("feature_id") if isinstance(f, dict) else "unknown"
        )
        if pos is None:
            continue
        c = int(round((pos[0] - stack.world_origin_x) / stack.cell_size))
        r = int(round((pos[1] - stack.world_origin_y) / stack.cell_size))
        if not (0 <= r < H and 0 <= c < W):
            continue
        local = float(hardness[r, c])
        if not (min_hardness <= local <= max_hardness):
            issues.append(
                ValidationIssue(
                    code="KARST_WRONG_ROCK",
                    severity="hard",
                    affected_feature=fid,
                    message=(
                        f"karst feature {fid} at hardness={local:.2f} "
                        f"outside soluble band [{min_hardness},{max_hardness}]"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Bundle registrar
# ---------------------------------------------------------------------------


BUNDLE_I_PASSES = (
    "stratigraphy",
    "glacial",
    "wind_erosion",
    "coastline",
    "karst",
)


def register_bundle_i_passes() -> None:
    """Register every Bundle I pass on the TerrainPassController.

    Does NOT modify ``register_default_passes``. Call this explicitly
    (same pattern as Bundle J).
    """
    from .terrain_pipeline import TerrainPassController
    from .terrain_semantics import PassDefinition

    from . import (
        coastline as _coastline,
        terrain_glacial as _glacial,
        terrain_karst as _karst,
        terrain_stratigraphy as _strat,
        terrain_wind_erosion as _wind,
    )

    TerrainPassController.register_pass(
        PassDefinition(
            name="stratigraphy",
            func=_strat.pass_stratigraphy,
            requires_channels=("height",),
            produces_channels=("rock_hardness", "strata_orientation"),
            seed_namespace="stratigraphy",
            requires_scene_read=False,
            description="Bundle I: rock hardness + strata orientation",
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="differential_erosion",
            func=_strat.pass_differential_erosion,
            requires_channels=("height", "rock_hardness"),
            produces_channels=("strat_erosion_delta",),
            seed_namespace="differential_erosion",
            requires_scene_read=False,
            description="Bundle I: differential erosion delta from rock hardness",
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="glacial",
            func=_glacial.pass_glacial,
            requires_channels=("height",),
            produces_channels=("snow_line_factor",),
            seed_namespace="glacial",
            requires_scene_read=False,
            description="Bundle I: glacial carving + snow line",
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="wind_erosion",
            func=_wind.pass_wind_erosion,
            requires_channels=("height",),
            produces_channels=("height",),
            seed_namespace="wind_erosion",
            requires_scene_read=False,
            description="Bundle I: aeolian erosion + dune generation",
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="coastline",
            func=_coastline.pass_coastline,
            requires_channels=("height",),
            produces_channels=("tidal",),
            seed_namespace="coastline",
            requires_scene_read=False,
            description="Bundle I: wave energy + tidal zones + cliff retreat",
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="karst",
            func=_karst.pass_karst,
            requires_channels=("height",),
            produces_channels=("height",),
            seed_namespace="karst",
            requires_scene_read=False,
            description="Bundle I: karst feature detection + carving",
        )
    )


__all__ = [
    "validate_strata_consistency",
    "validate_strahler_ordering",
    "validate_glacial_plausibility",
    "validate_karst_plausibility",
    "register_bundle_i_passes",
    "BUNDLE_I_PASSES",
]
