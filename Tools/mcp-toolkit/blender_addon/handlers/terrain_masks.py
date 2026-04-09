"""Structural mask computation functions for the terrain pipeline.

Bundle A — Foundation. Takes raw heightmaps and produces slope, curvature,
concavity, convexity, ridge, basin, and macro saliency masks. Populates
a ``TerrainMaskStack`` in place.

All operations are numpy-vectorized. No Blender imports.

References:
- docs/terrain_ultra_implementation_plan_2026-04-08.md §5.1, §6.2, §6.4
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .terrain_semantics import TerrainMaskStack


# ---------------------------------------------------------------------------
# Slope (radians)
# ---------------------------------------------------------------------------


def compute_slope(height: np.ndarray, cell_size: float) -> np.ndarray:
    """Return per-cell slope angle in radians.

    Uses central differences on interior cells and forward/backward
    differences on edges via np.gradient. Cell spacing is in world meters.
    """
    h = np.asarray(height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"compute_slope requires 2D heightmap (got {h.shape})")
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    dzdy, dzdx = np.gradient(h, cell_size)
    magnitude = np.sqrt(dzdx * dzdx + dzdy * dzdy)
    return np.arctan(magnitude)


# ---------------------------------------------------------------------------
# Curvature (signed, Laplacian-based)
# ---------------------------------------------------------------------------


def compute_curvature(height: np.ndarray, cell_size: float) -> np.ndarray:
    """Return signed Laplacian curvature of the heightmap.

    Positive values → convex (ridges, peaks).
    Negative values → concave (valleys, basins).
    Discrete Laplacian in world units: ∂²h/∂x² + ∂²h/∂y².
    """
    h = np.asarray(height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"compute_curvature requires 2D heightmap (got {h.shape})")
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    padded = np.pad(h, 1, mode="edge")
    d2dx2 = (padded[1:-1, 2:] - 2.0 * h + padded[1:-1, :-2]) / (cell_size * cell_size)
    d2dy2 = (padded[2:, 1:-1] - 2.0 * h + padded[:-2, 1:-1]) / (cell_size * cell_size)
    return d2dx2 + d2dy2


# ---------------------------------------------------------------------------
# Concavity / convexity (0..1)
# ---------------------------------------------------------------------------


def compute_concavity(curvature: np.ndarray) -> np.ndarray:
    """Normalized concavity mask 0..1 from signed curvature.

    Takes the negative lobe of curvature (concave regions) and normalizes
    to the 0..1 range by robust percentile scaling so outliers do not
    dominate.
    """
    curv = np.asarray(curvature, dtype=np.float64)
    neg = np.where(curv < 0.0, -curv, 0.0)
    if not np.any(neg > 0.0):
        return np.zeros_like(neg, dtype=np.float64)
    denom = float(np.percentile(neg, 99.0))
    if denom <= 0.0:
        return np.zeros_like(neg, dtype=np.float64)
    return np.clip(neg / denom, 0.0, 1.0)


def compute_convexity(curvature: np.ndarray) -> np.ndarray:
    """Normalized convexity mask 0..1 from signed curvature."""
    curv = np.asarray(curvature, dtype=np.float64)
    pos = np.where(curv > 0.0, curv, 0.0)
    if not np.any(pos > 0.0):
        return np.zeros_like(pos, dtype=np.float64)
    denom = float(np.percentile(pos, 99.0))
    if denom <= 0.0:
        return np.zeros_like(pos, dtype=np.float64)
    return np.clip(pos / denom, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Ridge extraction
# ---------------------------------------------------------------------------


def extract_ridge_mask(height: np.ndarray, cell_size: float) -> np.ndarray:
    """Boolean ridge mask: cells that are local maxima along at least one axis.

    Uses signed curvature: ridges are cells whose second derivative in one
    axis is strongly negative while the other axis is not more negative
    (i.e. a ridge line rather than a peak).
    """
    h = np.asarray(height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"extract_ridge_mask requires 2D heightmap (got {h.shape})")
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    padded = np.pad(h, 1, mode="edge")
    d2dx2 = (padded[1:-1, 2:] - 2.0 * h + padded[1:-1, :-2]) / (cell_size * cell_size)
    d2dy2 = (padded[2:, 1:-1] - 2.0 * h + padded[:-2, 1:-1]) / (cell_size * cell_size)

    # Ridge along y axis: row is a local max → d2dy2 strongly negative
    # Ridge along x axis: col is a local max → d2dx2 strongly negative
    all_curv = np.concatenate([d2dx2.ravel(), d2dy2.ravel()])
    if all_curv.size == 0:
        return np.zeros_like(h, dtype=bool)
    # Threshold at the 5th percentile of concave values (strongly negative)
    neg_vals = all_curv[all_curv < 0.0]
    if neg_vals.size == 0:
        return np.zeros_like(h, dtype=bool)
    threshold = float(np.percentile(neg_vals, 5.0))

    ridge_x = d2dx2 < threshold
    ridge_y = d2dy2 < threshold
    return ridge_x | ridge_y


# ---------------------------------------------------------------------------
# Basin detection (connected components of local minima)
# ---------------------------------------------------------------------------


def detect_basins(height: np.ndarray, min_area: int = 50) -> np.ndarray:
    """Label basins: cells that drain to the same local minimum.

    Pads with `+inf` so border cells are NOT trivially marked as minima
    (fixes Bundle A round-1 border-bug). Uses `np.argsort(kind='stable')`
    so tie-break order is reproducible across numpy builds.

    Returns an int32 array of basin IDs (0 = unassigned).
    Basins smaller than ``min_area`` cells are cleared back to 0.
    """
    h = np.asarray(height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"detect_basins requires 2D heightmap (got {h.shape})")
    rows, cols = h.shape
    if rows < 3 or cols < 3:
        return np.zeros_like(h, dtype=np.int32)

    # Pad with +inf so border cells cannot be spuriously marked as minima.
    padded = np.pad(h, 1, mode="constant", constant_values=np.inf)
    is_min = np.ones_like(h, dtype=bool)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            neighbor = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
            is_min &= h <= neighbor

    labels = np.zeros_like(h, dtype=np.int32)
    if not np.any(is_min):
        return labels

    # Connected-component label the seed minima (8-connected BFS)
    next_id = 1
    min_rows, min_cols = np.where(is_min)
    visited = np.zeros_like(h, dtype=bool)

    for r0, c0 in zip(min_rows.tolist(), min_cols.tolist()):
        if visited[r0, c0]:
            continue
        bfs_stack = [(r0, c0)]
        seed_id = next_id
        next_id += 1
        while bfs_stack:
            r, c = bfs_stack.pop()
            if r < 0 or r >= rows or c < 0 or c >= cols:
                continue
            if visited[r, c] or not is_min[r, c]:
                continue
            visited[r, c] = True
            labels[r, c] = seed_id
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    bfs_stack.append((r + dr, c + dc))

    # Iterative dilation: assign each unlabeled cell (in ascending-height
    # order) the label of its lowest-height already-labeled neighbor.
    # kind="stable" makes tie-break order deterministic across builds.
    order = np.argsort(h, axis=None, kind="stable")
    for _ in range(2):  # two passes handles edge cases where no labeled neighbor exists first time
        any_changed = False
        for flat_idx in order:
            r = int(flat_idx // cols)
            c = int(flat_idx % cols)
            if labels[r, c] != 0:
                continue
            best_label = 0
            best_h = np.inf
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = r + dr
                    nc = c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if labels[nr, nc] != 0 and h[nr, nc] < best_h:
                            best_h = float(h[nr, nc])
                            best_label = int(labels[nr, nc])
            if best_label != 0:
                labels[r, c] = best_label
                any_changed = True
        if not any_changed:
            break

    # Enforce min_area — vectorized via np.isin (no Python per-label mask writes)
    if min_area > 1:
        unique, counts = np.unique(labels, return_counts=True)
        small = unique[(counts < min_area) & (unique != 0)]
        if small.size:
            labels = np.where(np.isin(labels, small), 0, labels).astype(np.int32)

    return labels


# ---------------------------------------------------------------------------
# Macro saliency (relative importance for composition / framing)
# ---------------------------------------------------------------------------


def compute_macro_saliency(
    height: np.ndarray,
    curvature: np.ndarray,
    ridge: np.ndarray,
) -> np.ndarray:
    """Composite saliency mask 0..1 blending height prominence, curvature, and ridges.

    Used by Bundle H (composition) to decide where the "hero gaze"
    concentrates. Bundle A only needs to produce *a* saliency channel;
    Bundle H will refine with camera vantages.
    """
    h = np.asarray(height, dtype=np.float64)
    curv = np.asarray(curvature, dtype=np.float64)
    rid = np.asarray(ridge, dtype=bool)

    h_range = float(h.max() - h.min())
    if h_range > 0.0:
        h_norm = (h - h.min()) / h_range
    else:
        h_norm = np.zeros_like(h)

    curv_abs = np.abs(curv)
    curv_peak = float(np.percentile(curv_abs, 99.0)) if curv_abs.size else 0.0
    curv_norm = np.clip(curv_abs / curv_peak, 0.0, 1.0) if curv_peak > 0.0 else np.zeros_like(curv)

    ridge_norm = rid.astype(np.float64)

    saliency = 0.5 * h_norm + 0.3 * curv_norm + 0.2 * ridge_norm
    return np.clip(saliency, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Compound mask population
# ---------------------------------------------------------------------------


def compute_base_masks(
    height: np.ndarray,
    cell_size: float,
    tile_coords: Tuple[int, int],
    *,
    stack: Optional[TerrainMaskStack] = None,
    pass_name: str = "structural_masks",
    world_origin_x: float = 0.0,
    world_origin_y: float = 0.0,
) -> TerrainMaskStack:
    """Compute all structural masks and populate a ``TerrainMaskStack``.

    If ``stack`` is provided, it is updated in place (the given ``height``
    must match its existing shape). Otherwise a fresh stack is created.
    """
    h = np.asarray(height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"compute_base_masks requires 2D height (got {h.shape})")

    tile_size = max(h.shape) - 1

    if stack is None:
        stack = TerrainMaskStack(
            tile_size=tile_size,
            cell_size=float(cell_size),
            world_origin_x=float(world_origin_x),
            world_origin_y=float(world_origin_y),
            tile_x=int(tile_coords[0]),
            tile_y=int(tile_coords[1]),
            height=h.copy(),
        )
    else:
        if stack.height is None or stack.height.shape != h.shape:
            stack.set("height", h.copy(), pass_name)

    slope = compute_slope(h, cell_size)
    curvature = compute_curvature(h, cell_size)
    concavity = compute_concavity(curvature)
    convexity = compute_convexity(curvature)
    ridge = extract_ridge_mask(h, cell_size)
    basin = detect_basins(h)
    saliency = compute_macro_saliency(h, curvature, ridge)

    stack.set("slope", slope, pass_name)
    stack.set("curvature", curvature, pass_name)
    stack.set("concavity", concavity, pass_name)
    stack.set("convexity", convexity, pass_name)
    stack.set("ridge", ridge, pass_name)
    stack.set("basin", basin, pass_name)
    stack.set("saliency_macro", saliency, pass_name)

    return stack


__all__ = [
    "compute_slope",
    "compute_curvature",
    "compute_concavity",
    "compute_convexity",
    "extract_ridge_mask",
    "detect_basins",
    "compute_macro_saliency",
    "compute_base_masks",
]
