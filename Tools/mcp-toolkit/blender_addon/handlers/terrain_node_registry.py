"""TerrainNodeRegistry -- tile config consistency and neighbor tracking.

Central registry for terrain tiles (nodes). Ensures all tiles in a world
share consistent configuration (tile_size, cell_size, coordinate_system)
and tracks neighbor relationships for seam stitching.

NO bpy imports. Pure Python + numpy. Fully unit-testable.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Node descriptor
# ---------------------------------------------------------------------------


@dataclass
class TerrainNodeInfo:
    """Metadata for a single terrain tile in the registry."""

    tile_x: int
    tile_y: int
    tile_size: int
    cell_size: float
    world_origin_x: float
    world_origin_y: float
    height_min_m: float = 0.0
    height_max_m: float = 100.0
    coordinate_system: str = "z-up"
    is_hero: bool = False
    hero_feature_ids: Tuple[str, ...] = ()
    edge_heights: Optional[Dict[str, np.ndarray]] = None
    """Cached edge height arrays: keys are 'north','south','east','west'."""

    @property
    def node_key(self) -> Tuple[int, int]:
        return (self.tile_x, self.tile_y)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TerrainNodeRegistry:
    """Tracks all terrain tiles and their neighbor relationships.

    Validates that tiles share consistent configuration and provides
    fast neighbor lookups for seam stitching.
    """

    def __init__(
        self,
        *,
        expected_tile_size: int = 256,
        expected_cell_size: float = 1.0,
        expected_coordinate_system: str = "z-up",
    ) -> None:
        self._expected_tile_size = expected_tile_size
        self._expected_cell_size = expected_cell_size
        self._expected_coordinate_system = expected_coordinate_system
        self._nodes: Dict[Tuple[int, int], TerrainNodeInfo] = {}

    # -- registration -------------------------------------------------------

    def register(self, node: TerrainNodeInfo) -> None:
        """Register a tile node. Validates config consistency."""
        if node.tile_size != self._expected_tile_size:
            raise ValueError(
                f"Tile ({node.tile_x},{node.tile_y}) tile_size={node.tile_size} "
                f"does not match registry expected_tile_size={self._expected_tile_size}"
            )
        if abs(node.cell_size - self._expected_cell_size) > 1e-9:
            raise ValueError(
                f"Tile ({node.tile_x},{node.tile_y}) cell_size={node.cell_size} "
                f"does not match registry expected_cell_size={self._expected_cell_size}"
            )
        if node.coordinate_system != self._expected_coordinate_system:
            raise ValueError(
                f"Tile ({node.tile_x},{node.tile_y}) coordinate_system="
                f"'{node.coordinate_system}' does not match registry "
                f"expected='{self._expected_coordinate_system}'"
            )
        self._nodes[node.node_key] = node

    def unregister(self, tile_x: int, tile_y: int) -> None:
        """Remove a tile from the registry."""
        key = (tile_x, tile_y)
        self._nodes.pop(key, None)

    def get(self, tile_x: int, tile_y: int) -> Optional[TerrainNodeInfo]:
        """Retrieve node info, or None if not registered."""
        return self._nodes.get((tile_x, tile_y))

    def __contains__(self, key: Tuple[int, int]) -> bool:
        return key in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def all_nodes(self) -> List[TerrainNodeInfo]:
        return list(self._nodes.values())

    @property
    def all_keys(self) -> Set[Tuple[int, int]]:
        return set(self._nodes.keys())

    # -- neighbor lookups ---------------------------------------------------

    def get_neighbor(
        self, tile_x: int, tile_y: int, direction: str
    ) -> Optional[TerrainNodeInfo]:
        """Get the neighbor of tile (tile_x, tile_y) in the given direction."""
        offsets = {
            "north": (0, 1),
            "south": (0, -1),
            "east": (1, 0),
            "west": (-1, 0),
        }
        if direction not in offsets:
            raise ValueError(f"Unknown direction: {direction}. Use north/south/east/west.")
        dx, dy = offsets[direction]
        return self._nodes.get((tile_x + dx, tile_y + dy))

    def get_all_neighbors(
        self, tile_x: int, tile_y: int
    ) -> Dict[str, Optional[TerrainNodeInfo]]:
        """Return dict of direction -> neighbor (or None) for all 4 directions."""
        return {
            d: self.get_neighbor(tile_x, tile_y, d)
            for d in ("north", "south", "east", "west")
        }

    def get_shared_edge_pairs(self) -> List[Tuple[TerrainNodeInfo, TerrainNodeInfo, str]]:
        """Return all pairs of adjacent tiles with their shared edge direction.

        Each pair is yielded once: (node_a, node_b, direction_of_b_from_a).
        Only 'east' and 'north' are yielded to avoid duplicates.
        """
        pairs = []
        for key, node in self._nodes.items():
            tx, ty = key
            # East neighbor
            east = self._nodes.get((tx + 1, ty))
            if east is not None:
                pairs.append((node, east, "east"))
            # North neighbor
            north = self._nodes.get((tx, ty + 1))
            if north is not None:
                pairs.append((node, north, "north"))
        return pairs

    # -- edge height caching ------------------------------------------------

    def cache_edge_heights(
        self, tile_x: int, tile_y: int, heightmap: np.ndarray
    ) -> None:
        """Cache the four edge height arrays from a heightmap.

        Args:
            tile_x, tile_y: Tile coordinates.
            heightmap: 2D heightmap array for this tile.
        """
        node = self._nodes.get((tile_x, tile_y))
        if node is None:
            raise KeyError(f"Tile ({tile_x},{tile_y}) not registered")
        h = np.asarray(heightmap, dtype=np.float64)
        if h.ndim != 2:
            raise ValueError(f"heightmap must be 2D, got shape {h.shape}")
        node.edge_heights = {
            "north": h[-1, :].copy(),
            "south": h[0, :].copy(),
            "west": h[:, 0].copy(),
            "east": h[:, -1].copy(),
        }

    def validate_edge_match(
        self,
        tile_x: int,
        tile_y: int,
        direction: str,
        *,
        atol: float = 1e-12,
    ) -> Dict:
        """Validate that two adjacent tiles match at their shared edge.

        Returns a dict with 'match' (bool), 'max_delta', 'mean_delta', etc.
        """
        node = self._nodes.get((tile_x, tile_y))
        neighbor = self.get_neighbor(tile_x, tile_y, direction)

        if node is None:
            return {"match": False, "error": f"Tile ({tile_x},{tile_y}) not registered"}
        if neighbor is None:
            return {"match": False, "error": f"No neighbor in direction {direction}"}

        if node.edge_heights is None:
            return {"match": False, "error": f"Tile ({tile_x},{tile_y}) has no cached edge heights"}
        if neighbor.edge_heights is None:
            return {
                "match": False,
                "error": f"Neighbor ({neighbor.tile_x},{neighbor.tile_y}) has no cached edge heights",
            }

        # Map direction to edge names
        edge_map = {
            "east": ("east", "west"),
            "west": ("west", "east"),
            "north": ("north", "south"),
            "south": ("south", "north"),
        }
        edge_a_name, edge_b_name = edge_map[direction]
        edge_a = node.edge_heights.get(edge_a_name)
        edge_b = neighbor.edge_heights.get(edge_b_name)

        if edge_a is None or edge_b is None:
            return {"match": False, "error": "Edge heights missing for comparison"}
        if edge_a.shape != edge_b.shape:
            return {
                "match": False,
                "error": f"Edge shape mismatch: {edge_a.shape} vs {edge_b.shape}",
            }

        delta = np.abs(edge_a - edge_b)
        max_delta = float(delta.max())
        mean_delta = float(delta.mean())

        return {
            "match": max_delta <= atol,
            "direction": direction,
            "tile_a": (tile_x, tile_y),
            "tile_b": (neighbor.tile_x, neighbor.tile_y),
            "sample_count": len(edge_a),
            "max_delta": max_delta,
            "mean_delta": mean_delta,
            "atol": atol,
        }

    def validate_all_edges(self, *, atol: float = 1e-12) -> List[Dict]:
        """Validate all shared edges in the registry."""
        results = []
        for node_a, node_b, direction in self.get_shared_edge_pairs():
            result = self.validate_edge_match(
                node_a.tile_x, node_a.tile_y, direction, atol=atol
            )
            results.append(result)
        return results

    # -- hero node tracking -------------------------------------------------

    def hero_nodes(self) -> List[TerrainNodeInfo]:
        """Return all tiles flagged as hero nodes."""
        return [n for n in self._nodes.values() if n.is_hero]

    def mark_hero(
        self, tile_x: int, tile_y: int, feature_ids: Tuple[str, ...] = ()
    ) -> None:
        """Mark a tile as a hero node with optional feature IDs."""
        node = self._nodes.get((tile_x, tile_y))
        if node is None:
            raise KeyError(f"Tile ({tile_x},{tile_y}) not registered")
        node.is_hero = True
        node.hero_feature_ids = feature_ids

    # -- grid extent --------------------------------------------------------

    def grid_extent(self) -> Tuple[int, int, int, int]:
        """Return (min_x, min_y, max_x, max_y) of tile coordinates."""
        if not self._nodes:
            return (0, 0, 0, 0)
        xs = [k[0] for k in self._nodes]
        ys = [k[1] for k in self._nodes]
        return (min(xs), min(ys), max(xs), max(ys))

    def clear(self) -> None:
        """Remove all nodes."""
        self._nodes.clear()


__all__ = [
    "TerrainNodeInfo",
    "TerrainNodeRegistry",
]
