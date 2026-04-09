"""Negative space / quiet zone enforcement for Bundle H.

Ensures a minimum fraction of the tile remains "quiet" so busy features
have somewhere to breathe. AAA composition rule: at least 40% of the
tile should read as low-saliency negative space.

Pure numpy. No bpy.
"""

from __future__ import annotations

from typing import List

import numpy as np

from .terrain_semantics import TerrainMaskStack, ValidationIssue


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


QUIET_THRESHOLD = 0.3


def compute_quiet_zone_ratio(stack: TerrainMaskStack) -> float:
    """Return fraction of the tile with saliency_macro < QUIET_THRESHOLD."""
    if stack.saliency_macro is None:
        return 0.0
    sal = np.asarray(stack.saliency_macro, dtype=np.float64)
    if sal.size == 0:
        return 0.0
    return float((sal < QUIET_THRESHOLD).sum() / sal.size)


# ---------------------------------------------------------------------------
# Enforcement — produces a "calm zone" mask
# ---------------------------------------------------------------------------


def enforce_quiet_zone(
    stack: TerrainMaskStack,
    min_ratio: float = 0.4,
) -> np.ndarray:
    """Return a boolean mask of cells designated as the quiet zone.

    If the current tile already has >= ``min_ratio`` of below-threshold
    cells, the mask is simply those cells. Otherwise, the lowest-saliency
    cells are chosen until ``min_ratio`` of the tile is covered, and those
    cells are marked as the protected calm zone.

    The returned mask is intended to be consulted (not enforced) by later
    passes — they should avoid adding new saliency in these cells.
    """
    if stack.saliency_macro is None:
        rows, cols = stack.height.shape
        return np.zeros((rows, cols), dtype=bool)

    sal = np.asarray(stack.saliency_macro, dtype=np.float64)
    total = sal.size
    required = int(np.ceil(min_ratio * total))

    mask = sal < QUIET_THRESHOLD
    if int(mask.sum()) >= required:
        return mask

    # Not enough natural quiet — pick the lowest saliency cells
    flat = sal.ravel()
    if required >= total:
        return np.ones_like(sal, dtype=bool)
    # argpartition for efficient k-smallest selection
    idx = np.argpartition(flat, required - 1)[:required]
    picked = np.zeros_like(flat, dtype=bool)
    picked[idx] = True
    return picked.reshape(sal.shape)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_negative_space(
    stack: TerrainMaskStack,
    min_ratio: float = 0.4,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if stack.saliency_macro is None:
        issues.append(
            ValidationIssue(
                code="negative_space.missing_saliency",
                severity="hard",
                message="saliency_macro channel not populated; cannot validate negative space.",
                remediation="Run structural_masks pass first.",
            )
        )
        return issues

    ratio = compute_quiet_zone_ratio(stack)
    if ratio < min_ratio:
        issues.append(
            ValidationIssue(
                code="negative_space.insufficient",
                severity="soft",
                message=(
                    f"Quiet-zone ratio {ratio:.2f} below required {min_ratio:.2f}. "
                    "Scene is visually too busy — consider enforce_quiet_zone."
                ),
                remediation="Call enforce_quiet_zone and have downstream passes respect the mask.",
            )
        )
    return issues


__all__ = [
    "QUIET_THRESHOLD",
    "compute_quiet_zone_ratio",
    "enforce_quiet_zone",
    "validate_negative_space",
]
