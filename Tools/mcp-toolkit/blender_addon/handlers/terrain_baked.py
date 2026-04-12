"""BakedTerrain — the single artifact contract between DAG and mesh builder.

Phase 53-01: Every authoring path (compose_terrain_node, compose_map, etc.)
consumes this dataclass instead of re-running terrain generation or reading
raw mask stacks directly.

BakedTerrain is the frozen, post-pipeline snapshot of a terrain tile. It
carries the height grid, analytical gradients, ridge map, material masks,
and metadata needed by any downstream consumer (mesh builder, Unity exporter,
scatter system, LOD generator).

NO Blender imports. Pure Python + numpy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy scalars and arrays."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


@dataclass
class BakedTerrain:
    """Frozen post-pipeline terrain tile artifact.

    Fields
    ------
    height_grid : (H, W) float32 in world meters
    ridge_map   : (H, W) float32, -1 = crease, +1 = ridge
    gradient_x  : (H, W) float, dh/dx
    gradient_z  : (H, W) float, dh/dy (named gradient_z for legacy compat)
    material_masks : dict[str, (H, W) ndarray] — channel_name -> mask
    metadata : dict — seed, tile_x, tile_y, world_origin, cell_size, etc.
    """

    height_grid: np.ndarray
    ridge_map: np.ndarray
    gradient_x: np.ndarray
    gradient_z: np.ndarray
    material_masks: Dict[str, np.ndarray]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        h = np.asarray(self.height_grid)
        if not np.issubdtype(h.dtype, np.floating):
            h = h.astype(np.float64)
        if h.ndim != 2:
            raise ValueError(
                f"height_grid must be 2D (got ndim={h.ndim})"
            )
        self.height_grid = h
        shape = h.shape

        for name, arr in [
            ("ridge_map", self.ridge_map),
            ("gradient_x", self.gradient_x),
            ("gradient_z", self.gradient_z),
        ]:
            a = np.asarray(arr)
            if not np.issubdtype(a.dtype, np.floating):
                a = a.astype(np.float64)
            if a.shape != shape:
                raise ValueError(
                    f"{name} shape {a.shape} does not match "
                    f"height_grid shape {shape}"
                )
            setattr(self, name, a)

        for k, v in self.material_masks.items():
            a = np.asarray(v)
            if not np.issubdtype(a.dtype, np.floating):
                a = a.astype(np.float64)
            if a.shape != shape:
                raise ValueError(
                    f"material_mask '{k}' shape {a.shape} does not match "
                    f"height_grid shape {shape}"
                )
            self.material_masks[k] = a

    # ------------------------------------------------------------------
    # World-coordinate sampling
    # ------------------------------------------------------------------

    def _world_to_grid(self, x: float, y: float) -> Tuple[float, float]:
        """Convert world (x, y) to continuous grid (row, col) indices.

        Blender is Z-up, so the horizontal ground plane is X,Y.
        Rows map to the Y axis, columns to X — matching TerrainMaskStack.
        Legacy metadata key ``world_origin_z`` is accepted as a fallback
        for ``world_origin_y``.
        """
        cell_size = float(self.metadata.get("cell_size", 1.0))
        origin_x = float(self.metadata.get("world_origin_x", 0.0))
        origin_y = float(
            self.metadata.get(
                "world_origin_y",
                self.metadata.get("world_origin_z", 0.0),
            )
        )
        rows, cols = self.height_grid.shape
        col_f = (x - origin_x) / cell_size
        row_f = (y - origin_y) / cell_size
        # Clamp to valid range
        col_f = max(0.0, min(float(cols - 1), col_f))
        row_f = max(0.0, min(float(rows - 1), row_f))
        return row_f, col_f

    @staticmethod
    def _bilinear(grid: np.ndarray, row_f: float, col_f: float) -> float:
        """Bilinear interpolation on a 2D grid."""
        rows, cols = grid.shape
        r0 = max(0, min(int(row_f), rows - 2))
        c0 = max(0, min(int(col_f), cols - 2))
        r1, c1 = r0 + 1, c0 + 1
        rf = row_f - r0
        cf = col_f - c0
        return float(
            grid[r0, c0] * (1 - cf) * (1 - rf)
            + grid[r0, c1] * cf * (1 - rf)
            + grid[r1, c0] * (1 - cf) * rf
            + grid[r1, c1] * cf * rf
        )

    def sample_height(self, x: float, y: float) -> float:
        """Return interpolated height at world coordinates (x, y).

        In Blender's Z-up convention, x and y span the horizontal ground
        plane.  The returned value is the terrain height (Z).
        """
        row_f, col_f = self._world_to_grid(x, y)
        return self._bilinear(self.height_grid, row_f, col_f)

    def get_gradient(self, x: float, y: float) -> Tuple[float, float]:
        """Return (dh/dx, dh/dy) gradient vector at world (x, y)."""
        row_f, col_f = self._world_to_grid(x, y)
        gx = self._bilinear(self.gradient_x, row_f, col_f)
        gy = self._bilinear(self.gradient_z, row_f, col_f)
        return (gx, gy)

    def get_slope(self, x: float, y: float) -> float:
        """Return slope magnitude (>= 0) at world (x, y)."""
        gx, gy = self.get_gradient(x, y)
        return float(np.sqrt(gx * gx + gy * gy))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_npz(self, path: str) -> None:
        """Serialize to a compressed .npz file."""
        arrays: Dict[str, np.ndarray] = {
            "height_grid": self.height_grid,
            "ridge_map": self.ridge_map,
            "gradient_x": self.gradient_x,
            "gradient_z": self.gradient_z,
        }
        # Material masks with prefix
        for k, v in self.material_masks.items():
            arrays[f"mat_{k}"] = v

        # Metadata as JSON bytes
        meta_bytes = json.dumps(self.metadata, sort_keys=True, cls=_NumpyEncoder).encode("utf-8")
        arrays["_metadata_json"] = np.frombuffer(meta_bytes, dtype=np.uint8)

        np.savez_compressed(path, **arrays)

    @classmethod
    def from_npz(cls, path: str) -> "BakedTerrain":
        """Deserialize from a .npz file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"BakedTerrain npz not found: {path}")
        data = np.load(path, allow_pickle=False)

        height_grid = data["height_grid"]
        ridge_map = data["ridge_map"]
        gradient_x = data["gradient_x"]
        gradient_z = data["gradient_z"]

        # Reconstruct material masks
        material_masks: Dict[str, np.ndarray] = {}
        for key in data.files:
            if key.startswith("mat_"):
                channel_name = key[4:]  # strip "mat_" prefix
                material_masks[channel_name] = data[key]

        # Reconstruct metadata
        meta_bytes = data["_metadata_json"].tobytes()
        metadata = json.loads(meta_bytes.decode("utf-8"))

        return cls(
            height_grid=height_grid,
            ridge_map=ridge_map,
            gradient_x=gradient_x,
            gradient_z=gradient_z,
            material_masks=material_masks,
            metadata=metadata,
        )


__all__ = ["BakedTerrain"]
