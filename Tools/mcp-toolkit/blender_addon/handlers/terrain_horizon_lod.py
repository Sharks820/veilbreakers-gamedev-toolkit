"""Bundle L — terrain_horizon_lod.

Builds ultra-low-resolution horizon silhouette data from the tile's
heightfield, preserving peak silhouettes via max-pool downsampling to
below 1/64 of the source resolution. Also supports ray-cast horizon
profile sampling from a vantage position (for skybox mask generation).

This module is pure numpy — no bpy. All coordinates are Z-up, world
meters. The outputs are stored on ``stack.lod_bias`` (per-cell LOD
importance) as the Unity-consumable channel.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# Silhouette-preserving downsample
# ---------------------------------------------------------------------------


def compute_horizon_lod(
    stack: TerrainMaskStack,
    target_res: int,
) -> np.ndarray:
    """Downsample ``stack.height`` to ``target_res`` while preserving silhouette.

    The downsample factor is chosen so the output resolution is strictly
    less than ``1/64`` of the source tile resolution, with a ceiling of
    ``target_res``. Each output cell takes the **maximum** elevation of the
    corresponding source block — this preserves ridge silhouettes (the
    horizon profile) rather than averaging them away.

    Parameters
    ----------
    stack:
        Mask stack containing the source heightfield.
    target_res:
        Requested output side length, in cells. Clamped so the final
        resolution is always ``<= source_res // 64``.

    Returns
    -------
    np.ndarray
        2-D float32 silhouette-preserving LOD heightmap, shape
        ``(out_res, out_res)``.
    """
    if stack.height is None:
        raise ValueError("compute_horizon_lod requires stack.height")
    h = np.asarray(stack.height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"height must be 2D, got shape {h.shape}")

    src_h, src_w = h.shape
    src_min = min(src_h, src_w)
    # Hard ceiling: output < 1/64 of source.
    hard_cap = max(1, src_min // 64)
    out_res = max(1, min(int(target_res), hard_cap))

    # Block-pool: the step size in source cells per output cell.
    # Use ceil so every source row/col is covered.
    block_h = max(1, int(np.ceil(src_h / out_res)))
    block_w = max(1, int(np.ceil(src_w / out_res)))

    out = np.empty((out_res, out_res), dtype=np.float32)
    for i in range(out_res):
        r0 = i * block_h
        r1 = min(src_h, r0 + block_h)
        if r0 >= r1:
            r0 = max(0, src_h - 1)
            r1 = src_h
        for j in range(out_res):
            c0 = j * block_w
            c1 = min(src_w, c0 + block_w)
            if c0 >= c1:
                c0 = max(0, src_w - 1)
                c1 = src_w
            out[i, j] = float(h[r0:r1, c0:c1].max())
    return out


# ---------------------------------------------------------------------------
# Ray-cast horizon profile
# ---------------------------------------------------------------------------


def build_horizon_skybox_mask(
    stack: TerrainMaskStack,
    vantage_pos: Tuple[float, float, float],
    ray_count: int = 128,
) -> np.ndarray:
    """Ray-cast a horizon profile (max elevation angle) from ``vantage_pos``.

    Casts ``ray_count`` azimuth-distributed rays from the given world-space
    vantage point, returning for each ray the maximum elevation angle
    (radians, in [-pi/2, pi/2]) that any terrain cell subtends from that
    vantage. This is the skybox horizon profile — Unity consumers can use
    it to mask the lower portion of a cubemap cleanly against terrain.

    Parameters
    ----------
    stack:
        Source height stack.
    vantage_pos:
        (x, y, z) world-space meters (Z-up).
    ray_count:
        Number of azimuth bins (uniform around the full 2*pi).

    Returns
    -------
    np.ndarray
        float32 shape ``(ray_count,)`` — elevation angle per azimuth bin.
    """
    if stack.height is None:
        raise ValueError("build_horizon_skybox_mask requires stack.height")
    if ray_count < 3:
        raise ValueError(f"ray_count must be >= 3, got {ray_count}")

    vx, vy, vz = float(vantage_pos[0]), float(vantage_pos[1]), float(vantage_pos[2])
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cell = float(stack.cell_size)
    ox = float(stack.world_origin_x)
    oy = float(stack.world_origin_y)

    # World-space coordinates of every cell center.
    js = np.arange(cols, dtype=np.float64)
    is_ = np.arange(rows, dtype=np.float64)
    wx = ox + (js + 0.5) * cell
    wy = oy + (is_ + 0.5) * cell
    gx, gy = np.meshgrid(wx, wy)
    dx = gx - vx
    dy = gy - vy
    dz = h - vz
    dist = np.sqrt(dx * dx + dy * dy)
    # Avoid div-by-zero at vantage cell.
    safe_dist = np.where(dist < 1e-6, 1e-6, dist)
    elev = np.arctan2(dz, safe_dist)  # radians
    azimuth = np.arctan2(dy, dx)  # radians, [-pi, pi]

    profile = np.full((ray_count,), -np.pi * 0.5, dtype=np.float32)
    # Bin by azimuth into [0, ray_count).
    bins = ((azimuth + np.pi) / (2.0 * np.pi) * ray_count).astype(np.int32)
    bins = np.clip(bins, 0, ray_count - 1)
    flat_bins = bins.ravel()
    flat_elev = elev.ravel().astype(np.float32)
    # Per-bin max via np.maximum.at (unbuffered).
    np.maximum.at(profile, flat_bins, flat_elev)
    # Cells at the vantage itself (dist ~ 0) are nonsense; leave floor.
    return profile


# ---------------------------------------------------------------------------
# Pass wrapper
# ---------------------------------------------------------------------------


def pass_horizon_lod(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle L pass: build horizon LOD + set lod_bias channel.

    Contract
    --------
    Consumes: ``height``
    Produces: ``lod_bias``
    Respects protected zones: no (read-only on height; writes LOD metadata)
    Requires scene read: no
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    hints = state.intent.composition_hints if state.intent else {}

    src_shape = stack.height.shape
    src_min = min(src_shape)
    target_res = int(hints.get("horizon_lod_target_res", max(1, src_min // 64)))
    # Guard: always strictly <= 1/64 of source.
    target_res = max(1, min(target_res, max(1, src_min // 64)))

    lod_map = compute_horizon_lod(stack, target_res)

    # Build a per-cell lod_bias channel: cells at high elevation (ridge /
    # silhouette cells) get higher priority. We use the silhouette-preserving
    # max-pool to drive a 0..1 bias across the full-resolution grid via
    # nearest-neighbour upsample.
    out_res = lod_map.shape[0]
    row_idx = (np.arange(src_shape[0]) * out_res // max(1, src_shape[0])).clip(0, out_res - 1)
    col_idx = (np.arange(src_shape[1]) * out_res // max(1, src_shape[1])).clip(0, out_res - 1)
    upsampled = lod_map[np.ix_(row_idx, col_idx)]
    lo = float(upsampled.min())
    hi = float(upsampled.max())
    if hi - lo < 1e-9:
        bias = np.zeros_like(upsampled, dtype=np.float32)
    else:
        bias = ((upsampled - lo) / (hi - lo)).astype(np.float32)
    stack.set("lod_bias", bias, "horizon_lod")

    # Determinism-friendly ratio guard.
    ratio = float(out_res) / float(max(1, src_min))
    return PassResult(
        pass_name="horizon_lod",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("lod_bias",),
        metrics={
            "source_res": int(src_min),
            "target_res": int(out_res),
            "ratio_source_over_target": float(1.0 / ratio) if ratio > 0 else 0.0,
            "ratio_target_over_source": ratio,
            "silhouette_max_m": float(lod_map.max()),
            "silhouette_min_m": float(lod_map.min()),
        },
    )


def register_bundle_l_horizon_lod_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="horizon_lod",
            func=pass_horizon_lod,
            requires_channels=("height",),
            produces_channels=("lod_bias",),
            seed_namespace="horizon_lod",
            requires_scene_read=False,
            description="Bundle L: silhouette-preserving far-terrain LOD",
        )
    )


__all__ = [
    "compute_horizon_lod",
    "build_horizon_skybox_mask",
    "pass_horizon_lod",
    "register_bundle_l_horizon_lod_pass",
]
