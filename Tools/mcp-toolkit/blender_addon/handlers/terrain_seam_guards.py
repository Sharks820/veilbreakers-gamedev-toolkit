"""Seam guard zones for terrain tile boundaries.

Creates per-cell boolean guard masks that block erosion, waterfalls, and
material mutations within a configurable band of cells from tile edges.
Hero deltas must fade to zero at tile edges; seam guard zones enforce this.

NO bpy imports. Pure Python + numpy. Fully unit-testable.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Guard band computation
# ---------------------------------------------------------------------------


def compute_guard_band_mask(
    tile_size: int,
    guard_width: int = 4,
    *,
    shape: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    """Return a boolean mask where True = guard band (mutations blocked).

    The guard band is ``guard_width`` cells wide along all four tile edges.
    Interior cells are False (mutations allowed).

    Args:
        tile_size: Logical tile resolution. If ``shape`` is None, the
            heightmap shape is inferred as ``(tile_size+1, tile_size+1)``
            (Unity shared-edge contract).
        guard_width: Number of cells from each edge that are protected.
        shape: Override heightmap shape (rows, cols) if non-standard.

    Returns:
        Boolean ndarray of shape ``(rows, cols)``.
    """
    if shape is not None:
        rows, cols = shape
    else:
        rows = tile_size + 1
        cols = tile_size + 1

    if guard_width <= 0:
        return np.zeros((rows, cols), dtype=bool)

    mask = np.ones((rows, cols), dtype=bool)
    if guard_width < rows and guard_width < cols:
        mask[guard_width:-guard_width, guard_width:-guard_width] = False
    # If guard_width >= half the tile, everything is guarded
    return mask


def compute_edge_fade_weights(
    tile_size: int,
    fade_width: int = 8,
    *,
    shape: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    """Return a float32 weight mask that fades from 1.0 (interior) to 0.0 (edge).

    Hero deltas should be multiplied by this mask so they naturally decay
    to zero at tile boundaries, ensuring seamless stitching.

    Args:
        tile_size: Logical tile resolution.
        fade_width: Number of cells over which the fade occurs from each edge.
        shape: Override heightmap shape (rows, cols) if non-standard.

    Returns:
        Float32 ndarray of shape ``(rows, cols)`` in [0, 1].
    """
    if shape is not None:
        rows, cols = shape
    else:
        rows = tile_size + 1
        cols = tile_size + 1

    if fade_width <= 0:
        return np.ones((rows, cols), dtype=np.float32)

    # Compute distance from each edge, clamped to fade_width
    row_dist = np.minimum(
        np.arange(rows, dtype=np.float32),
        np.arange(rows - 1, -1, -1, dtype=np.float32),
    )
    col_dist = np.minimum(
        np.arange(cols, dtype=np.float32),
        np.arange(cols - 1, -1, -1, dtype=np.float32),
    )
    # 2D distance = min(row_distance, col_distance)
    dist_2d = np.minimum(
        row_dist[:, np.newaxis],
        col_dist[np.newaxis, :],
    )
    # Normalize to [0, 1] over fade_width
    weights = np.clip(dist_2d / float(fade_width), 0.0, 1.0)
    return weights.astype(np.float32)


def apply_hero_delta_with_fade(
    base_height: np.ndarray,
    hero_delta: np.ndarray,
    fade_weights: np.ndarray,
) -> np.ndarray:
    """Apply a hero delta to a base heightmap with edge-fade blending.

    The hero delta is multiplied by ``fade_weights`` so it decays to zero
    at tile edges, then added to ``base_height``.

    Args:
        base_height: Base terrain heightmap (2D float).
        hero_delta: Additive height displacement from hero features (2D float).
        fade_weights: Edge-fade mask from ``compute_edge_fade_weights``.

    Returns:
        Combined heightmap as float64 ndarray.
    """
    base = np.asarray(base_height, dtype=np.float64)
    delta = np.asarray(hero_delta, dtype=np.float64)
    weights = np.asarray(fade_weights, dtype=np.float64)

    if base.shape != delta.shape:
        raise ValueError(
            f"base_height shape {base.shape} != hero_delta shape {delta.shape}"
        )
    if base.shape != weights.shape:
        raise ValueError(
            f"base_height shape {base.shape} != fade_weights shape {weights.shape}"
        )

    return base + delta * weights


def is_in_guard_band(
    row: int,
    col: int,
    tile_size: int,
    guard_width: int = 4,
    *,
    shape: Optional[Tuple[int, int]] = None,
) -> bool:
    """Check if a single cell is within the guard band.

    More efficient than computing the full mask for point queries.
    """
    if shape is not None:
        rows, cols = shape
    else:
        rows = tile_size + 1
        cols = tile_size + 1

    if row < guard_width or row >= rows - guard_width:
        return True
    if col < guard_width or col >= cols - guard_width:
        return True
    return False


# ---------------------------------------------------------------------------
# Protected zone factory for seam guards
# ---------------------------------------------------------------------------


def create_seam_guard_zones(
    tile_x: int,
    tile_y: int,
    tile_size: int,
    cell_size: float,
    world_origin_x: float,
    world_origin_y: float,
    guard_width: int = 4,
) -> list:
    """Create ProtectedZoneSpec instances for all four tile edges.

    Returns a list of ProtectedZoneSpec (imported lazily to avoid circular
    deps) that cover the guard band on each edge.

    These zones forbid erosion, waterfall, and material passes in the
    guard band. Only 'macro_world' and 'structural_masks' are permitted.
    """
    from .terrain_semantics import BBox, ProtectedZoneSpec

    tile_world_extent = tile_size * cell_size
    tx0 = world_origin_x + tile_x * tile_world_extent
    ty0 = world_origin_y + tile_y * tile_world_extent
    tx1 = tx0 + tile_world_extent
    ty1 = ty0 + tile_world_extent

    guard_m = guard_width * cell_size
    allowed = frozenset({"macro_world", "structural_masks", "validation_minimal"})

    zones = []

    # South edge (bottom)
    zones.append(
        ProtectedZoneSpec(
            zone_id=f"seam_guard_south_{tile_x}_{tile_y}",
            bounds=BBox(min_x=tx0, min_y=ty0, max_x=tx1, max_y=ty0 + guard_m),
            kind="seam_guard",
            allowed_mutations=allowed,
            description=f"Seam guard band: south edge of tile ({tile_x},{tile_y})",
        )
    )
    # North edge (top)
    zones.append(
        ProtectedZoneSpec(
            zone_id=f"seam_guard_north_{tile_x}_{tile_y}",
            bounds=BBox(min_x=tx0, min_y=ty1 - guard_m, max_x=tx1, max_y=ty1),
            kind="seam_guard",
            allowed_mutations=allowed,
            description=f"Seam guard band: north edge of tile ({tile_x},{tile_y})",
        )
    )
    # West edge (left)
    zones.append(
        ProtectedZoneSpec(
            zone_id=f"seam_guard_west_{tile_x}_{tile_y}",
            bounds=BBox(min_x=tx0, min_y=ty0, max_x=tx0 + guard_m, max_y=ty1),
            kind="seam_guard",
            allowed_mutations=allowed,
            description=f"Seam guard band: west edge of tile ({tile_x},{tile_y})",
        )
    )
    # East edge (right)
    zones.append(
        ProtectedZoneSpec(
            zone_id=f"seam_guard_east_{tile_x}_{tile_y}",
            bounds=BBox(min_x=tx1 - guard_m, min_y=ty0, max_x=tx1, max_y=ty1),
            kind="seam_guard",
            allowed_mutations=allowed,
            description=f"Seam guard band: east edge of tile ({tile_x},{tile_y})",
        )
    )

    return zones


__all__ = [
    "compute_guard_band_mask",
    "compute_edge_fade_weights",
    "apply_hero_delta_with_fade",
    "is_in_guard_band",
    "create_seam_guard_zones",
]
