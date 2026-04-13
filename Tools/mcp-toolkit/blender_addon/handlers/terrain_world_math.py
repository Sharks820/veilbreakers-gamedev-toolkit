"""Pure-numpy world-space terrain math helpers.

Bundle A supplements per Addendum 2.A. Intentionally tiny and dependency-free
so every pass/test can import without dragging pipeline state in.

No bpy / bmesh imports. Safe in headless + subagent contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# Addendum 2.A.2 — fBm theoretical max amplitude
# ---------------------------------------------------------------------------


def theoretical_max_amplitude(persistence: float, octaves: int) -> float:
    """Deterministic fBm max amplitude — per-tile-invariant normalization.

    Per-tile ``(h - h.min()) / (h.max() - h.min())`` normalization breaks
    tiling because different tiles sample different local maxima. Using
    this theoretical upper bound as the global normalization constant makes
    height values identical across tiles for the same world coordinate.

    Formula:
        sum_{k=0..octaves-1} persistence**k
        = octaves                            if persistence == 1
        = (1 - persistence**octaves) / (1 - persistence)   otherwise
    """
    if octaves <= 0:
        return 0.0
    if abs(float(persistence) - 1.0) < 1e-10:
        return float(octaves)
    p = float(persistence)
    return (1.0 - p ** int(octaves)) / (1.0 - p)


# ---------------------------------------------------------------------------
# Addendum 2.B.2 — TileTransform contract (tile metadata single source of truth)
# ---------------------------------------------------------------------------


@dataclass
class TileTransform:
    """Canonical tile world-space transform.

    This is the single source of truth for "where is this tile in the
    world?" — replaces the old ``object_location`` / ``position`` pair
    (Bug #9) so downstream consumers cannot guess which is authoritative.
    """

    origin_world: Tuple[float, float, float]
    min_corner_world: Tuple[float, float, float]
    max_corner_world: Tuple[float, float, float]
    tile_coords: Tuple[int, int]
    tile_size_world: float
    convention: str = "object_origin_at_min_corner"

    def to_dict(self) -> Dict[str, Any]:
        """Return the Addendum 2.B.2 tile_transform contract dict."""
        return {
            "origin_world": [float(x) for x in self.origin_world],
            "min_corner_world": [float(x) for x in self.min_corner_world],
            "max_corner_world": [float(x) for x in self.max_corner_world],
            "tile_coords": [int(self.tile_coords[0]), int(self.tile_coords[1])],
            "tile_size_world": float(self.tile_size_world),
            "convention": str(self.convention),
        }


# ---------------------------------------------------------------------------
# Addendum 2.A.6 — Erosion math scaling direction
# ---------------------------------------------------------------------------


def compute_erosion_params_for_world_range(
    height_range: float,
    base_min_slope: float = 0.01,
    base_capacity: float = 4.0,
) -> Dict[str, float]:
    """Scale erosion params from `[0, 1]` defaults to world-unit domain.

    ``min_slope`` scales linearly by ``height_range`` — it was originally
    "1% of max height"; in world units it should be ``0.01 * height_range``.

    ``capacity`` is NOT scaled — sediment carrying scales automatically
    with the underlying height differences.
    """
    hr = float(height_range) if height_range else 0.0
    if hr <= 0.0:
        effective_min_slope = float(base_min_slope)
    else:
        effective_min_slope = float(base_min_slope) * hr
    return {
        "min_slope": effective_min_slope,
        "capacity": float(base_capacity),
        "height_range": hr,
    }


__all__ = [
    "theoretical_max_amplitude",
    "TileTransform",
    "compute_erosion_params_for_world_range",
]
