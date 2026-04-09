"""Bundle Q — Footprint surface data for gameplay systems.

Samples the terrain mask stack at a set of world positions and returns
per-point surface data (position, normal, material id, wetness, cave
flag). Used by gameplay footprint VFX and audio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .terrain_semantics import TerrainMaskStack


@dataclass
class FootprintSurfacePoint:
    """Surface data sampled at a single world position."""

    world_pos: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    material_id: int
    wetness: float
    in_cave: bool


def _world_to_cell(
    stack: TerrainMaskStack, x: float, y: float
) -> Tuple[int, int]:
    col = int(round((x - stack.world_origin_x) / stack.cell_size))
    row = int(round((y - stack.world_origin_y) / stack.cell_size))
    h, w = stack.height.shape
    col = int(np.clip(col, 0, w - 1))
    row = int(np.clip(row, 0, h - 1))
    return row, col


def compute_footprint_surface_data(
    stack: TerrainMaskStack,
    world_positions: np.ndarray,
) -> List[FootprintSurfacePoint]:
    """Sample the stack at each ``(x, y)`` position.

    ``world_positions`` is an ``(N, 2)`` or ``(N, 3)`` array of world
    meters. Returns one ``FootprintSurfacePoint`` per row.
    """
    if stack.height is None:
        raise ValueError("stack.height is required for footprint sampling")
    arr = np.asarray(world_positions)
    if arr.ndim != 2 or arr.shape[1] not in (2, 3):
        raise ValueError(f"world_positions must be (N, 2|3), got {arr.shape}")

    h, w = stack.height.shape
    out: List[FootprintSurfacePoint] = []

    for pos in arr:
        x = float(pos[0])
        y = float(pos[1])
        r, c = _world_to_cell(stack, x, y)
        z = float(stack.height[r, c])

        # Simple finite-difference normal (Z-up)
        rm = max(0, r - 1)
        rp = min(h - 1, r + 1)
        cm = max(0, c - 1)
        cp = min(w - 1, c + 1)
        dzdx = (float(stack.height[r, cp]) - float(stack.height[r, cm])) / (
            2.0 * stack.cell_size
        )
        dzdy = (float(stack.height[rp, c]) - float(stack.height[rm, c])) / (
            2.0 * stack.cell_size
        )
        n = np.array([-dzdx, -dzdy, 1.0], dtype=np.float64)
        n = n / max(1e-9, np.linalg.norm(n))

        material_id = 0
        if stack.biome_id is not None:
            material_id = int(stack.biome_id[r, c])

        wetness = 0.0
        if stack.wetness is not None:
            wetness = float(stack.wetness[r, c])

        in_cave = False
        if stack.cave_candidate is not None:
            in_cave = bool(stack.cave_candidate[r, c] > 0.5)

        out.append(
            FootprintSurfacePoint(
                world_pos=(x, y, z),
                normal=(float(n[0]), float(n[1]), float(n[2])),
                material_id=material_id,
                wetness=wetness,
                in_cave=in_cave,
            )
        )
    return out


def export_footprint_data_json(
    points: List[FootprintSurfacePoint],
    output_path: Path,
) -> None:
    """Write a JSON file of all footprint points."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "1.0", "points": [asdict(p) for p in points]}
    output_path.write_text(json.dumps(payload, indent=2))
