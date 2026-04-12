"""Negative space / quiet zone enforcement for Bundle H.

Ensures a minimum fraction of the tile remains "quiet" so busy features
have somewhere to breathe. AAA composition rule: at least 40% of the
tile should read as low-saliency negative space.

This module now also validates:

1. **Quiet-zone ratio** — fraction of the tile below the saliency
   threshold. Enforces the "breathing room" constraint.
2. **Feature-rhythm spacing** — minimum distance between peaks in the
   saliency map so features don't cluster into a wall-of-detail.
3. **Feature-density budget** — rejects tiles where the high-saliency
   pixel count exceeds a configurable cap per unit area.

Pure numpy. No bpy.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .terrain_semantics import TerrainMaskStack, ValidationIssue


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


QUIET_THRESHOLD = 0.3
BUSY_THRESHOLD = 0.65  # cells with saliency >= BUSY_THRESHOLD count as "hero"
DEFAULT_MIN_PEAK_SPACING_M = 12.0  # min metres between high-saliency centroids


def compute_quiet_zone_ratio(stack: TerrainMaskStack) -> float:
    """Return fraction of the tile with saliency_macro < QUIET_THRESHOLD."""
    if stack.saliency_macro is None:
        return 0.0
    sal = np.asarray(stack.saliency_macro, dtype=np.float64)
    if sal.size == 0:
        return 0.0
    return float((sal < QUIET_THRESHOLD).sum() / sal.size)


def compute_busy_ratio(stack: TerrainMaskStack) -> float:
    """Return fraction of the tile with saliency_macro >= BUSY_THRESHOLD."""
    if stack.saliency_macro is None:
        return 0.0
    sal = np.asarray(stack.saliency_macro, dtype=np.float64)
    if sal.size == 0:
        return 0.0
    return float((sal >= BUSY_THRESHOLD).sum() / sal.size)


def find_saliency_peaks(
    stack: TerrainMaskStack,
    *,
    peak_threshold: float = BUSY_THRESHOLD,
    min_separation_cells: int = 4,
) -> List[Tuple[int, int]]:
    """Return grid-space (row, col) centres of the dominant saliency peaks.

    Performs a simple non-maximum suppression over the saliency map: a
    cell is a peak if it sits above ``peak_threshold`` AND is the max
    inside a square window of radius ``min_separation_cells``. This is
    intentionally cheap — Bundle H's full hierarchy pass uses a more
    sophisticated segmentation; this helper exists for the rhythm /
    spacing validator to avoid importing it.
    """
    if stack.saliency_macro is None:
        return []
    sal = np.asarray(stack.saliency_macro, dtype=np.float64)
    if sal.size == 0:
        return []

    rows, cols = sal.shape
    sep = max(int(min_separation_cells), 1)
    peaks: List[Tuple[int, int]] = []
    # Sort candidate cells descending by saliency so we claim the
    # strongest peaks first and suppress weaker ones nearby.
    candidates = np.argwhere(sal >= peak_threshold)
    if candidates.size == 0:
        return []
    values = sal[candidates[:, 0], candidates[:, 1]]
    order = np.argsort(-values)
    claimed = np.zeros_like(sal, dtype=bool)
    for idx in order:
        r, c = int(candidates[idx, 0]), int(candidates[idx, 1])
        if claimed[r, c]:
            continue
        peaks.append((r, c))
        r0 = max(0, r - sep)
        r1 = min(rows, r + sep + 1)
        c0 = max(0, c - sep)
        c1 = min(cols, c + sep + 1)
        claimed[r0:r1, c0:c1] = True
    return peaks


def compute_min_peak_spacing(
    stack: TerrainMaskStack,
    *,
    peak_threshold: float = BUSY_THRESHOLD,
    min_separation_cells: int = 4,
) -> float:
    """Return the smallest pairwise distance between saliency peaks (metres).

    Returns ``float('inf')`` whenever fewer than two peaks are present.
    Zero peaks means the constraint is trivially satisfied — a quiet
    tile with no hero features cannot violate a "peaks too close"
    rule. One peak means there is no pair to measure. Only two or more
    peaks produce a real distance.
    """
    peaks = find_saliency_peaks(
        stack,
        peak_threshold=peak_threshold,
        min_separation_cells=min_separation_cells,
    )
    if len(peaks) < 2:
        return float("inf")
    cell_size = float(stack.cell_size) if stack.cell_size else 1.0
    coords = np.asarray(peaks, dtype=np.float64) * cell_size
    diffs = coords[:, None, :] - coords[None, :, :]
    dists = np.sqrt((diffs * diffs).sum(axis=-1))
    # Set self-distances to +inf so min() returns the real neighbour distance.
    np.fill_diagonal(dists, np.inf)
    return float(dists.min())


def compute_feature_density(stack: TerrainMaskStack) -> float:
    """Return high-saliency cells per 1000 square metres.

    The budget enforcer in Bundle N uses this to trip when a tile
    exceeds the configured "hero density" cap.
    """
    if stack.saliency_macro is None:
        return 0.0
    sal = np.asarray(stack.saliency_macro, dtype=np.float64)
    if sal.size == 0:
        return 0.0
    busy_count = int((sal >= BUSY_THRESHOLD).sum())
    cell_size = float(stack.cell_size) if stack.cell_size else 1.0
    area_m2 = sal.size * cell_size * cell_size
    if area_m2 <= 0.0:
        return 0.0
    return busy_count / (area_m2 / 1000.0)


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
    *,
    max_feature_density_per_1000m2: float = 1.25,
    min_peak_spacing_m: float = DEFAULT_MIN_PEAK_SPACING_M,
) -> List[ValidationIssue]:
    """Validate that the tile has room to breathe, even after hero placement.

    Three independent checks are performed; they each contribute their
    own ``ValidationIssue`` on failure so downstream consumers can
    surface them individually.

    * ``negative_space.insufficient`` — quiet-zone ratio below floor.
    * ``negative_space.feature_density_too_high`` — too many hero
      cells per 1000 m² (the Bundle N budget enforcer uses this as
      one of its inputs).
    * ``negative_space.peaks_too_close`` — shortest pair of hero
      centroids is closer than the AAA minimum spacing, producing a
      wall-of-features read.
    """
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

    density = compute_feature_density(stack)
    if density > max_feature_density_per_1000m2:
        issues.append(
            ValidationIssue(
                code="negative_space.feature_density_too_high",
                severity="soft",
                message=(
                    f"Hero feature density {density:.3f} per 1000 m² exceeds "
                    f"budget {max_feature_density_per_1000m2:.3f}. Tile reads "
                    "as a wall of detail."
                ),
                remediation=(
                    "Reduce hero feature count or raise the BUSY_THRESHOLD "
                    "cutoff before re-running saliency."
                ),
            )
        )

    spacing = compute_min_peak_spacing(stack)
    if spacing < float(min_peak_spacing_m):
        issues.append(
            ValidationIssue(
                code="negative_space.peaks_too_close",
                severity="soft",
                message=(
                    f"Closest pair of saliency peaks is {spacing:.2f} m "
                    f"apart, below the {min_peak_spacing_m:.2f} m minimum. "
                    "Camera cannot separate the features."
                ),
                remediation=(
                    "Move one of the conflicting hero features or merge "
                    "them into a single composite landmark."
                ),
            )
        )

    return issues


def register_bundle_h_negative_space() -> None:
    """No-op registrar — negative_space is a validator module, not a pipeline pass.

    Called by ``terrain_master_registrar`` to verify the module is importable
    and its symbols are reachable at startup.
    """


__all__ = [
    "QUIET_THRESHOLD",
    "BUSY_THRESHOLD",
    "DEFAULT_MIN_PEAK_SPACING_M",
    "compute_quiet_zone_ratio",
    "compute_busy_ratio",
    "compute_feature_density",
    "compute_min_peak_spacing",
    "find_saliency_peaks",
    "enforce_quiet_zone",
    "validate_negative_space",
    "register_bundle_h_negative_space",
]
