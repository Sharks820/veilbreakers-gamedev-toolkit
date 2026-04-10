"""Dirty-region tracking for terrain iteration velocity (Bundle M).

Tracks which world-space bounding boxes and mask channels have been
mutated since the last "clean" snapshot so downstream iteration tooling
(sub-tile region exec, mask cache invalidation, live preview) can skip
unchanged work.

Pure Python + numpy. No bpy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Set

from .terrain_semantics import BBox, TerrainPipelineState


# ---------------------------------------------------------------------------
# DirtyRegion
# ---------------------------------------------------------------------------


@dataclass
class DirtyRegion:
    """A world-space region affected by one or more pass mutations."""

    bounds: BBox
    affected_channels: Set[str] = field(default_factory=set)
    timestamp: float = 0.0

    def touches_channel(self, channel: str) -> bool:
        return channel in self.affected_channels

    def merge(self, other: "DirtyRegion") -> "DirtyRegion":
        merged_bounds = BBox(
            min_x=min(self.bounds.min_x, other.bounds.min_x),
            min_y=min(self.bounds.min_y, other.bounds.min_y),
            max_x=max(self.bounds.max_x, other.bounds.max_x),
            max_y=max(self.bounds.max_y, other.bounds.max_y),
        )
        return DirtyRegion(
            bounds=merged_bounds,
            affected_channels=set(self.affected_channels) | set(other.affected_channels),
            timestamp=max(self.timestamp, other.timestamp),
        )


# ---------------------------------------------------------------------------
# DirtyTracker
# ---------------------------------------------------------------------------


class DirtyTracker:
    """Accumulates dirty regions across pass mutations.

    Usage
    -----
    >>> tracker = DirtyTracker(world_bounds=BBox(0,0,100,100))
    >>> tracker.mark_dirty("height", BBox(10,10,20,20))
    >>> regions = tracker.get_dirty_regions()
    >>> frac = tracker.dirty_fraction()
    """

    def __init__(self, world_bounds: Optional[BBox] = None) -> None:
        self._regions: List[DirtyRegion] = []
        self._world_bounds: Optional[BBox] = world_bounds

    @property
    def world_bounds(self) -> Optional[BBox]:
        return self._world_bounds

    def set_world_bounds(self, bounds: BBox) -> None:
        self._world_bounds = bounds

    def mark_dirty(self, channel: str, bbox: BBox) -> DirtyRegion:
        """Mark a region+channel as dirty. Returns the created DirtyRegion."""
        region = DirtyRegion(
            bounds=bbox,
            affected_channels={channel},
            timestamp=time.time(),
        )
        self._regions.append(region)
        return region

    def mark_many(self, channels: Iterable[str], bbox: BBox) -> DirtyRegion:
        region = DirtyRegion(
            bounds=bbox,
            affected_channels=set(channels),
            timestamp=time.time(),
        )
        self._regions.append(region)
        return region

    def get_dirty_regions(self) -> List[DirtyRegion]:
        return list(self._regions)

    def get_dirty_channels(self) -> Set[str]:
        out: Set[str] = set()
        for r in self._regions:
            out |= r.affected_channels
        return out

    def clear(self) -> None:
        self._regions.clear()

    def is_clean(self) -> bool:
        return not self._regions

    def dirty_area(self) -> float:
        """Approximate total dirty area in m^2 (sums regions, double-counts overlap)."""
        return sum(r.bounds.width * r.bounds.height for r in self._regions)

    def dirty_fraction(self) -> float:
        """Fraction of total world bounds that is dirty (0.0..1.0).

        If world_bounds is unset, returns 0.0. Clamped to 1.0 for overlap.
        """
        if self._world_bounds is None:
            return 0.0
        total = self._world_bounds.width * self._world_bounds.height
        if total <= 0.0:
            return 0.0
        return min(1.0, self.dirty_area() / total)

    def coalesce(self) -> Optional[DirtyRegion]:
        """Merge all dirty regions into a single bounding DirtyRegion."""
        if not self._regions:
            return None
        merged = self._regions[0]
        for r in self._regions[1:]:
            merged = merged.merge(r)
        return merged


# ---------------------------------------------------------------------------
# Attach helper
# ---------------------------------------------------------------------------


def attach_dirty_tracker(state: TerrainPipelineState) -> DirtyTracker:
    """Attach (or return existing) DirtyTracker on a pipeline state.

    The tracker is stored as an attribute on the state object; it is not
    part of the frozen dataclass contract — so we use setattr for a
    lightweight side-car.
    """
    existing = getattr(state, "_dirty_tracker", None)
    if isinstance(existing, DirtyTracker):
        return existing
    tracker = DirtyTracker(world_bounds=state.intent.region_bounds)
    setattr(state, "_dirty_tracker", tracker)
    return tracker


__all__ = [
    "DirtyRegion",
    "DirtyTracker",
    "attach_dirty_tracker",
]
