"""Per-channel visual diff between two TerrainMaskStack snapshots.

Bundle M — Iteration velocity. Used by live preview + regression
harness to quickly answer "what changed between these two stacks?".

Pure numpy. No bpy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .terrain_semantics import BBox, TerrainMaskStack


def _bbox_of_mask(
    mask: np.ndarray,
    stack: TerrainMaskStack,
) -> Optional[BBox]:
    """Return a world-space BBox covering all True cells in ``mask``."""
    if mask.dtype != bool:
        mask = mask.astype(bool)
    if not mask.any():
        return None
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    r0, r1 = int(np.argmax(rows)), int(len(rows) - 1 - np.argmax(rows[::-1]))
    c0, c1 = int(np.argmax(cols)), int(len(cols) - 1 - np.argmax(cols[::-1]))
    cs = float(stack.cell_size)
    return BBox(
        min_x=float(stack.world_origin_x) + c0 * cs,
        min_y=float(stack.world_origin_y) + r0 * cs,
        max_x=float(stack.world_origin_x) + (c1 + 1) * cs,
        max_y=float(stack.world_origin_y) + (r1 + 1) * cs,
    )


def compute_visual_diff(
    stack_before: TerrainMaskStack,
    stack_after: TerrainMaskStack,
    *,
    eps: float = 1e-9,
) -> Dict[str, Any]:
    """Compute per-channel max-delta + affected bbox.

    Returns a dict:
        {
            "changed_channels": [names...],
            "per_channel": {
                channel: {"max_abs_delta": float, "mean_abs_delta": float,
                          "changed_cells": int, "bbox": BBox or None},
                ...
            },
            "total_changed_cells": int,
        }
    """
    changed: List[str] = []
    per_channel: Dict[str, Any] = {}
    total_cells = 0

    for name in stack_before._ARRAY_CHANNELS:
        before = getattr(stack_before, name, None)
        after = getattr(stack_after, name, None)
        if before is None and after is None:
            continue
        if (before is None) != (after is None):
            per_channel[name] = {
                "max_abs_delta": float("inf"),
                "mean_abs_delta": float("inf"),
                "changed_cells": -1,
                "bbox": None,
                "newly_populated": before is None,
                "newly_removed": after is None,
            }
            changed.append(name)
            continue

        ba = np.asarray(before, dtype=np.float64)
        aa = np.asarray(after, dtype=np.float64)
        if ba.shape != aa.shape:
            per_channel[name] = {
                "max_abs_delta": float("inf"),
                "mean_abs_delta": float("inf"),
                "changed_cells": -1,
                "bbox": None,
                "shape_mismatch": (ba.shape, aa.shape),
            }
            changed.append(name)
            continue

        delta = np.abs(aa - ba)
        max_d = float(delta.max()) if delta.size else 0.0
        if max_d <= eps:
            continue
        mask = delta > eps
        # Collapse higher-dim masks down to 2D for bbox extraction
        mask2 = mask
        while mask2.ndim > 2:
            mask2 = np.any(mask2, axis=-1)
        bbox = _bbox_of_mask(mask2, stack_after) if mask2.ndim == 2 else None
        cells_changed = int(mask2.sum()) if mask2.ndim == 2 else int(mask.sum())
        per_channel[name] = {
            "max_abs_delta": max_d,
            "mean_abs_delta": float(delta.mean()),
            "changed_cells": cells_changed,
            "bbox": bbox,
        }
        changed.append(name)
        total_cells += cells_changed

    return {
        "changed_channels": changed,
        "per_channel": per_channel,
        "total_changed_cells": total_cells,
    }


def generate_diff_overlay(
    stack_before: TerrainMaskStack,
    stack_after: TerrainMaskStack,
) -> np.ndarray:
    """Produce a color-coded RGB delta image (H, W, 3) uint8.

    Red channel: height increase. Blue: height decrease. Green: any
    non-height channel changed. Unchanged cells are 0.
    """
    h_before = np.asarray(stack_before.height, dtype=np.float64)
    h_after = np.asarray(stack_after.height, dtype=np.float64)
    if h_before.shape != h_after.shape:
        raise ValueError(
            f"height shape mismatch {h_before.shape} vs {h_after.shape}"
        )
    H, W = h_before.shape
    overlay = np.zeros((H, W, 3), dtype=np.uint8)

    dh = h_after - h_before
    max_abs = float(np.abs(dh).max())
    if max_abs > 0.0:
        pos = np.clip(dh / max_abs, 0.0, 1.0)
        neg = np.clip(-dh / max_abs, 0.0, 1.0)
        overlay[..., 0] = (pos * 255).astype(np.uint8)
        overlay[..., 2] = (neg * 255).astype(np.uint8)

    # Green: any other channel changed
    for name in stack_before._ARRAY_CHANNELS:
        if name == "height":
            continue
        before = getattr(stack_before, name, None)
        after = getattr(stack_after, name, None)
        if before is None or after is None:
            continue
        ba = np.asarray(before)
        aa = np.asarray(after)
        if ba.shape != aa.shape:
            continue
        if ba.ndim < 2:
            continue
        mask = np.abs(aa.astype(np.float64) - ba.astype(np.float64)) > 1e-9
        while mask.ndim > 2:
            mask = np.any(mask, axis=-1)
        if mask.shape == (H, W):
            overlay[..., 1] = np.maximum(overlay[..., 1], (mask * 255).astype(np.uint8))

    return overlay


__all__ = [
    "compute_visual_diff",
    "generate_diff_overlay",
]
