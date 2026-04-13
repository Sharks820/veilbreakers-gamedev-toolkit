"""Bundle Q — Destructibility patch detection.

Seeds destructible patches from ``rock_hardness`` and ``wetness``. Low
hardness + high wetness => soft patches that break quickly; high
hardness => durable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

from .terrain_semantics import BBox, TerrainMaskStack


@dataclass
class DestructibilityPatch:
    """A single destructible terrain patch."""

    bounds: BBox
    hp: float
    material_id: int
    debris_type: str


def detect_destructibility_patches(stack: TerrainMaskStack) -> List[DestructibilityPatch]:
    """Detect destructible patches from rock_hardness and wetness.

    The detector scans the stack in coarse cells of at most 8x8 and
    emits one patch per cell whose average hardness falls below 0.6.
    When ``rock_hardness`` is unavailable the detector returns an empty
    list (nothing to destroy).
    """
    if stack.rock_hardness is None or stack.height is None:
        return []

    hardness = stack.rock_hardness
    wetness = stack.wetness if stack.wetness is not None else np.zeros_like(hardness)

    h, w = hardness.shape
    cell = max(1, min(8, min(h, w) // 4))

    patches: List[DestructibilityPatch] = []
    for r0 in range(0, h, cell):
        for c0 in range(0, w, cell):
            r1 = min(h, r0 + cell)
            c1 = min(w, c0 + cell)
            block_h = hardness[r0:r1, c0:c1]
            if block_h.size == 0:
                continue
            avg_h = float(block_h.mean())
            if avg_h >= 0.6:
                continue
            avg_w = float(wetness[r0:r1, c0:c1].mean())
            # hp in [10, 200] — softer blocks get less hp
            hp = 10.0 + 190.0 * max(0.0, avg_h)
            # wetness accelerates decay
            hp *= max(0.3, 1.0 - avg_w * 0.5)

            min_x = stack.world_origin_x + c0 * stack.cell_size
            min_y = stack.world_origin_y + r0 * stack.cell_size
            max_x = stack.world_origin_x + c1 * stack.cell_size
            max_y = stack.world_origin_y + r1 * stack.cell_size

            if avg_w > 0.5:
                debris = "mud"
            elif avg_h < 0.3:
                debris = "gravel"
            else:
                debris = "rock_chunk"

            material_id = 0
            if stack.biome_id is not None:
                material_id = int(
                    stack.biome_id[r0:r1, c0:c1].reshape(-1)[0]
                )

            patches.append(
                DestructibilityPatch(
                    bounds=BBox(min_x, min_y, max_x, max_y),
                    hp=float(hp),
                    material_id=material_id,
                    debris_type=debris,
                )
            )
    return patches


def export_destructibility_json(
    patches: List[DestructibilityPatch],
    output_path: Path,
) -> None:
    """Write destructibility patches to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "patches": [
            {
                "bounds": list(p.bounds.to_tuple()),
                "hp": p.hp,
                "material_id": p.material_id,
                "debris_type": p.debris_type,
            }
            for p in patches
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2))
