"""Sub-tile region execution for terrain iteration velocity (Bundle M).

Runs a pass sequence scoped to a sub-tile region, with automatic
padding computation so droplet-based erosion etc. doesn't show seams
at the patch boundary.

Pure Python + numpy. No bpy.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from .terrain_pipeline import TerrainPassController
from .terrain_semantics import BBox, PassDefinition, PassResult


# Default radius (in world meters) passes get padded by. Erosion droplets
# can travel ~30 cells at 1m/cell worst case before losing all water.
_DEFAULT_PAD_RADIUS_M: float = 8.0


# Per-pass padding map — if a registered pass is known to need more
# slack than the default, override here. Conservative numbers.
_PASS_PAD_RADIUS: dict = {
    "erosion": 16.0,
    "macro_world": 0.0,  # global noise, padding is meaningless
    "structural_masks": 2.0,
    "validation_minimal": 0.0,
}


def _pass_pad_radius(pass_def: PassDefinition) -> float:
    return float(_PASS_PAD_RADIUS.get(pass_def.name, _DEFAULT_PAD_RADIUS_M))


def compute_minimum_padding(
    region: BBox,
    passes: Sequence[str],
    controller: Optional[TerrainPassController] = None,
    world_bounds: Optional[BBox] = None,
) -> BBox:
    """Expand a region outward by the maximum padding any pass needs.

    If a registry lookup fails for a pass name (e.g. the pass isn't
    registered yet) we fall back to the default radius. The returned
    BBox is clamped to ``world_bounds`` when provided.
    """
    pad = 0.0
    for name in passes:
        try:
            pdef = TerrainPassController.get_pass(name)
            pad = max(pad, _pass_pad_radius(pdef))
        except Exception:
            pad = max(pad, _DEFAULT_PAD_RADIUS_M)

    min_x = region.min_x - pad
    min_y = region.min_y - pad
    max_x = region.max_x + pad
    max_y = region.max_y + pad
    if world_bounds is not None:
        min_x = max(min_x, world_bounds.min_x)
        min_y = max(min_y, world_bounds.min_y)
        max_x = min(max_x, world_bounds.max_x)
        max_y = min(max_y, world_bounds.max_y)
        if max_x <= min_x:
            max_x = min_x + 1e-6
        if max_y <= min_y:
            max_y = min_y + 1e-6
    return BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def execute_region(
    controller: TerrainPassController,
    pass_sequence: Sequence[str],
    region: BBox,
    *,
    pad: bool = True,
    checkpoint: bool = False,
) -> List[PassResult]:
    """Run a pass sequence scoped to ``region`` (optionally padded).

    Stops on the first failed pass.
    """
    world = controller.state.intent.region_bounds
    target = (
        compute_minimum_padding(region, pass_sequence, controller, world)
        if pad
        else region
    )
    results: List[PassResult] = []
    for pass_name in pass_sequence:
        res = controller.run_pass(pass_name, region=target, checkpoint=checkpoint)
        results.append(res)
        if res.status == "failed":
            break
    return results


__all__ = [
    "execute_region",
    "compute_minimum_padding",
]
