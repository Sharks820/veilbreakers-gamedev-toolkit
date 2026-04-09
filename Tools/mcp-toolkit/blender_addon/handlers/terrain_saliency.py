"""Vantage-aware saliency refinement for terrain composition (Bundle H).

Pure numpy. No bpy. Takes an existing ``saliency_macro`` channel and
refines it using camera-vantage ray-casts so the final composition mask
reflects what the player actually sees from hero camera positions —
the Witcher 3 / Horizon ZD "camera-aware" composition trick.

See docs/terrain_ultra_implementation_plan_2026-04-08.md §13 Bundle H.
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# World <-> grid helpers
# ---------------------------------------------------------------------------


def _world_to_cell(
    stack: TerrainMaskStack, x: float, y: float
) -> Tuple[int, int]:
    col = int(round((x - stack.world_origin_x) / stack.cell_size))
    row = int(round((y - stack.world_origin_y) / stack.cell_size))
    rows, cols = stack.height.shape
    col = max(0, min(cols - 1, col))
    row = max(0, min(rows - 1, row))
    return row, col


def _sample_height_bilinear(height: np.ndarray, rf: float, cf: float) -> float:
    rows, cols = height.shape
    rf = max(0.0, min(rows - 1.0001, rf))
    cf = max(0.0, min(cols - 1.0001, cf))
    r0 = int(np.floor(rf))
    c0 = int(np.floor(cf))
    dr = rf - r0
    dc = cf - c0
    h00 = height[r0, c0]
    h01 = height[r0, c0 + 1]
    h10 = height[r0 + 1, c0]
    h11 = height[r0 + 1, c0 + 1]
    return float(
        (1 - dr) * ((1 - dc) * h00 + dc * h01)
        + dr * ((1 - dc) * h10 + dc * h11)
    )


# ---------------------------------------------------------------------------
# Vantage silhouette rays
# ---------------------------------------------------------------------------


def compute_vantage_silhouettes(
    stack: TerrainMaskStack,
    vantage_points: Sequence[Tuple[float, float, float]],
    ray_count: int = 64,
) -> np.ndarray:
    """For each vantage, cast ``ray_count`` azimuthal rays across the heightmap.

    Returns an array of shape ``(V, ray_count)`` with the maximum silhouette
    elevation angle sampled along each ray. Elevation is in radians relative
    to the vantage eye-level; higher values mean the terrain occludes more of
    the horizon along that azimuth.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cell = float(stack.cell_size)
    tile_extent = float(max(rows, cols) * cell)
    max_dist = tile_extent * 1.5
    # Sample along ray at ~1 cell spacing, capped for huge tiles
    sample_step = max(cell, max_dist / 256.0)
    n_samples = max(4, int(max_dist / sample_step))

    V = len(vantage_points)
    out = np.zeros((V, ray_count), dtype=np.float64)
    if V == 0 or ray_count <= 0:
        return out

    angles = np.linspace(0.0, 2.0 * np.pi, ray_count, endpoint=False)
    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    for vi, (vx, vy, vz) in enumerate(vantage_points):
        for ri in range(ray_count):
            max_elev = 0.0
            for si in range(1, n_samples + 1):
                d = si * sample_step
                wx = vx + cos_a[ri] * d
                wy = vy + sin_a[ri] * d
                cf = (wx - stack.world_origin_x) / cell
                rf = (wy - stack.world_origin_y) / cell
                if rf < 0 or rf > rows - 1 or cf < 0 or cf > cols - 1:
                    break
                hz = _sample_height_bilinear(h, rf, cf)
                dz = hz - vz
                if dz <= 0.0:
                    continue
                elev = float(np.arctan2(dz, d))
                if elev > max_elev:
                    max_elev = elev
            out[vi, ri] = max_elev

    return out


# ---------------------------------------------------------------------------
# Auto-sculpt a feature to pop from a vantage silhouette
# ---------------------------------------------------------------------------


def auto_sculpt_around_feature(
    stack: TerrainMaskStack,
    feature_pos: Tuple[float, float, float],
    feature_kind: str,
    intensity: float,
) -> np.ndarray:
    """Return a height delta that emphasizes a feature's silhouette.

    The delta is a radial Gaussian bump/dip centered on the feature projected
    to the XY plane. ``feature_kind`` selects sign and width:
        * "cliff", "pinnacle", "ridge", "peak", "spire" → positive bump
        * "canyon", "basin", "pool", "cave_entrance"   → negative dip
        * anything else                                → shallow positive bump

    This is a cheap authoring nudge. It does NOT replace real sculpting —
    it simply raises the saliency signature of the feature along the ray
    a vantage would see.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cell = float(stack.cell_size)
    delta = np.zeros_like(h)
    if intensity == 0.0:
        return delta

    fx, fy, _fz = feature_pos
    # Center in grid coords (float)
    cf = (fx - stack.world_origin_x) / cell
    rf = (fy - stack.world_origin_y) / cell

    positive_kinds = {
        "cliff",
        "pinnacle",
        "ridge",
        "peak",
        "spire",
        "arch",
        "mesa",
        "tower",
        "spur",
    }
    negative_kinds = {
        "canyon",
        "basin",
        "pool",
        "cave_entrance",
        "cave",
        "sinkhole",
        "gorge",
        "valley",
    }
    kind = feature_kind.lower()
    if kind in positive_kinds:
        sign = 1.0
        radius_cells = max(3.0, min(rows, cols) * 0.12)
    elif kind in negative_kinds:
        sign = -1.0
        radius_cells = max(3.0, min(rows, cols) * 0.10)
    else:
        sign = 1.0
        radius_cells = max(3.0, min(rows, cols) * 0.08)

    rr, cc = np.mgrid[0:rows, 0:cols]
    d2 = (rr - rf) ** 2 + (cc - cf) ** 2
    sigma2 = radius_cells * radius_cells
    gauss = np.exp(-d2 / (2.0 * sigma2))
    delta = sign * float(intensity) * gauss
    return delta


# ---------------------------------------------------------------------------
# pass_saliency_refine
# ---------------------------------------------------------------------------


def _rasterize_vantage_silhouettes_onto_grid(
    stack: TerrainMaskStack,
    vantage_points: Sequence[Tuple[float, float, float]],
    silhouettes: np.ndarray,
) -> np.ndarray:
    """Project each vantage's ray silhouette array onto the heightmap grid.

    Each cell receives a weight equal to the max silhouette elevation of
    the ray that best matches its azimuth from the nearest vantage.
    Cells closer to the vantage get a closer match; cells the vantage
    cannot see cleanly (occluded or outside) get zero.
    """
    h = stack.height
    rows, cols = h.shape
    out = np.zeros_like(h, dtype=np.float64)
    if silhouettes.size == 0 or len(vantage_points) == 0:
        return out

    ray_count = silhouettes.shape[1]
    cell = float(stack.cell_size)

    rr, cc = np.mgrid[0:rows, 0:cols]
    wx = cc.astype(np.float64) * cell + stack.world_origin_x
    wy = rr.astype(np.float64) * cell + stack.world_origin_y

    best = np.zeros_like(h, dtype=np.float64)
    for vi, (vx, vy, _vz) in enumerate(vantage_points):
        dx = wx - vx
        dy = wy - vy
        theta = np.arctan2(dy, dx)
        theta_pos = np.where(theta < 0, theta + 2.0 * np.pi, theta)
        ray_idx = (theta_pos / (2.0 * np.pi) * ray_count).astype(np.int32) % ray_count
        ray_vals = silhouettes[vi][ray_idx]
        # Distance falloff: close cells get the value more strongly
        dist = np.sqrt(dx * dx + dy * dy)
        max_dist = float(max(rows, cols) * cell)
        falloff = np.clip(1.0 - (dist / (max_dist + 1e-9)), 0.0, 1.0)
        best = np.maximum(best, ray_vals * falloff)

    # Normalize to 0..1 relative to the max elevation seen
    peak = float(best.max()) if best.size else 0.0
    if peak > 0.0:
        out = np.clip(best / peak, 0.0, 1.0)
    return out


def pass_saliency_refine(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Refine ``saliency_macro`` using vantage silhouettes.

    Reads ``intent.composition_hints["vantages"]`` (list of (x,y,z)).
    Blends 60% existing saliency + 40% vantage silhouette mask.
    If no vantages are specified, the pass is a no-op that keeps the
    existing saliency and reports an info metric.
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    intent = state.intent

    if stack.saliency_macro is None:
        return PassResult(
            pass_name="saliency_refine",
            status="failed",
            duration_seconds=time.perf_counter() - t0,
            metrics={"error": "saliency_macro not populated"},
        )

    vantages = tuple(intent.composition_hints.get("vantages", ()))
    if not vantages:
        return PassResult(
            pass_name="saliency_refine",
            status="ok",
            duration_seconds=time.perf_counter() - t0,
            consumed_channels=("saliency_macro",),
            produced_channels=("saliency_macro",),
            metrics={"vantage_count": 0, "noop": True},
        )

    silhouettes = compute_vantage_silhouettes(stack, vantages, ray_count=64)
    vantage_mask = _rasterize_vantage_silhouettes_onto_grid(
        stack, vantages, silhouettes
    )
    base = np.asarray(stack.saliency_macro, dtype=np.float64)
    refined = np.clip(0.6 * base + 0.4 * vantage_mask, 0.0, 1.0)

    stack.set("saliency_macro", refined, "saliency_refine")

    return PassResult(
        pass_name="saliency_refine",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("saliency_macro", "height"),
        produced_channels=("saliency_macro",),
        metrics={
            "vantage_count": len(vantages),
            "max_silhouette_rad": float(silhouettes.max()),
            "mean_refined": float(refined.mean()),
        },
    )


def register_saliency_pass() -> None:
    """Register the saliency refinement pass on TerrainPassController."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="saliency_refine",
            func=pass_saliency_refine,
            requires_channels=("height", "saliency_macro"),
            produces_channels=("saliency_macro",),
            seed_namespace="saliency_refine",
            may_modify_geometry=False,
            requires_scene_read=False,
            supports_region_scope=False,
            description="Refine saliency_macro with camera vantage silhouettes.",
        )
    )


__all__ = [
    "compute_vantage_silhouettes",
    "auto_sculpt_around_feature",
    "pass_saliency_refine",
    "register_saliency_pass",
]
