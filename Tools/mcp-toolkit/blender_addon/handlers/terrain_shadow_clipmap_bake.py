"""Bundle K — terrain_shadow_clipmap_bake.

Bakes a per-cell sun-shadow mask by ray-marching the heightmap along the
sun direction. Produces a float32 (clipmap_res, clipmap_res) mask in [0, 1]
(1 = fully lit, 0 = in shadow). Populates ``cloud_shadow`` channel when
sun occlusion is used as a multiplier on top of cloud shadows (both fold
into the shader AO path in Unity).

Pure numpy ray march — not production-fast, but deterministic and
dependency-free. For production bakes use a Houdini/Bake shader.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


def _resample_height(h: np.ndarray, target: int) -> np.ndarray:
    """Bilinear resample a heightmap to (target, target)."""
    rows, cols = h.shape
    if rows == target and cols == target:
        return h.astype(np.float64)
    ys = np.linspace(0.0, rows - 1.0, target)
    xs = np.linspace(0.0, cols - 1.0, target)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, rows - 1)
    x1 = np.clip(x0 + 1, 0, cols - 1)
    ty = (ys - y0).reshape(-1, 1)
    tx = (xs - x0).reshape(1, -1)
    a = h[np.ix_(y0, x0)]
    b = h[np.ix_(y0, x1)]
    c = h[np.ix_(y1, x0)]
    d = h[np.ix_(y1, x1)]
    top = a * (1 - tx) + b * tx
    bot = c * (1 - tx) + d * tx
    return (top * (1 - ty) + bot * ty).astype(np.float64)


def bake_shadow_clipmap(
    stack: TerrainMaskStack,
    sun_dir_rad: Tuple[float, float],
    clipmap_res: int = 512,
    num_steps: int = 24,
) -> np.ndarray:
    """Ray-march sun shadows across the heightmap.

    Parameters
    ----------
    sun_dir_rad : (azimuth, elevation) in radians. Azimuth is measured from
        world +X toward world +Y. Elevation is angle above horizon (>0).
    clipmap_res : output resolution. If different from height shape, we
        bilinearly resample the heightmap to match.
    num_steps : number of ray-march samples per cell.

    Returns
    -------
    (clipmap_res, clipmap_res) float32 in [0, 1]. 1 = lit, 0 = shadowed.
    """
    if stack.height is None:
        raise ValueError("bake_shadow_clipmap requires stack.height")
    if clipmap_res <= 0:
        raise ValueError(f"clipmap_res must be > 0, got {clipmap_res}")

    az, el = float(sun_dir_rad[0]), float(sun_dir_rad[1])
    if el <= 0.0:
        # Sun below horizon — everything shadowed
        return np.zeros((clipmap_res, clipmap_res), dtype=np.float32)

    h = _resample_height(np.asarray(stack.height, dtype=np.float64), clipmap_res)
    # World extent in meters
    tile_extent_m = float(stack.tile_size) * float(stack.cell_size)
    cell_m = tile_extent_m / max(clipmap_res, 1)

    # Horizontal ray direction in cell units
    dx = np.cos(az)
    dy = np.sin(az)
    # Per-step horizontal distance (in cell units). Cap to avoid aliasing.
    step_cells = max(1.0, (clipmap_res / max(num_steps, 1)) * 0.5)
    # Vertical per-step climb in world meters
    dz_per_step_m = step_cells * cell_m * np.tan(el)

    rows, cols = h.shape
    mask = np.ones((rows, cols), dtype=np.float64)

    # Precompute coordinate grid
    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float64)
    ray_h = h.copy()  # current "ray altitude" along the march

    for step in range(1, num_steps + 1):
        sx = xx + dx * step * step_cells
        sy = yy + dy * step * step_cells
        ray_h = h + dz_per_step_m * step

        # Out-of-bounds = assume unoccluded (open sky)
        in_bounds = (sx >= 0) & (sx < cols - 1) & (sy >= 0) & (sy < rows - 1)

        sxi = np.clip(sx.astype(np.int32), 0, cols - 1)
        syi = np.clip(sy.astype(np.int32), 0, rows - 1)
        terrain_h = h[syi, sxi]

        occluded = in_bounds & (terrain_h > ray_h)
        # Soft shadow: reduce mask by a factor each hit
        mask = np.where(occluded, mask * 0.55, mask)

    return mask.astype(np.float32)


def export_shadow_clipmap_exr(mask: np.ndarray, output_path: Path) -> None:
    """Write shadow clipmap to disk.

    Real EXR requires OpenEXR (not in deps). We write a float32 .npy with a
    sibling .json sidecar noting the intended format. Unity importer reads
    the .npy path and reconstructs the clipmap texture.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Force extension to .npy for honest round-trip
    if output_path.suffix.lower() != ".npy":
        output_path = output_path.with_suffix(".npy")

    arr = np.ascontiguousarray(mask, dtype=np.float32)
    np.save(output_path, arr)

    sidecar = output_path.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "schema": "veilbreakers.terrain.shadow_clipmap/v1",
                "format": "float32_npy",
                "intended_format": "exr_float32",
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "min": float(arr.min()),
                "max": float(arr.max()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def pass_shadow_clipmap(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle K pass: bake shadow clipmap.

    Consumes: height
    Produces: cloud_shadow (populated if not already present;
              otherwise multiplied in)
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    hints = state.intent.composition_hints if state.intent else {}
    sun_az = float(hints.get("sun_azimuth_rad", 0.6))
    sun_el = float(hints.get("sun_elevation_rad", 0.85))
    clipmap_res = int(hints.get("shadow_clipmap_res", max(32, stack.height.shape[0])))

    mask = bake_shadow_clipmap(
        stack,
        sun_dir_rad=(sun_az, sun_el),
        clipmap_res=clipmap_res,
        num_steps=int(hints.get("shadow_clipmap_steps", 18)),
    )

    # Resample back to heightmap shape to populate cloud_shadow channel
    rows, cols = np.asarray(stack.height).shape
    resampled = _resample_height(mask.astype(np.float64), max(rows, cols))
    # crop
    resampled = resampled[:rows, :cols].astype(np.float32)

    existing = stack.get("cloud_shadow")
    if existing is None:
        combined = resampled
    else:
        combined = (np.asarray(existing, dtype=np.float32) * resampled).astype(np.float32)
    stack.set("cloud_shadow", combined, "shadow_clipmap")

    return PassResult(
        pass_name="shadow_clipmap",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("cloud_shadow",),
        metrics={
            "sun_azimuth_rad": sun_az,
            "sun_elevation_rad": sun_el,
            "clipmap_res": int(clipmap_res),
            "lit_fraction": float((mask > 0.5).mean()),
            "shadow_min": float(mask.min()),
            "shadow_max": float(mask.max()),
        },
        issues=[],
    )


def register_bundle_k_shadow_clipmap_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="shadow_clipmap",
            func=pass_shadow_clipmap,
            requires_channels=("height",),
            produces_channels=("cloud_shadow",),
            seed_namespace="shadow_clipmap",
            requires_scene_read=False,
            description="Bundle K: ray-marched sun shadow clipmap bake",
        )
    )


__all__ = [
    "bake_shadow_clipmap",
    "export_shadow_clipmap_exr",
    "pass_shadow_clipmap",
    "register_bundle_k_shadow_clipmap_pass",
]
