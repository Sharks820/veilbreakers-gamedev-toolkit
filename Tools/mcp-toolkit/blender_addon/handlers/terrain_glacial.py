"""Bundle I — terrain_glacial.

Glacial carving: U-shaped valleys, lateral/terminal moraines, and
altitude-driven snow-line computation. Unlike hydraulic V-valleys
these are wide, flat-floored, and carved along authored paths.

Pure numpy, no bpy. Z-up, world meters.
"""

from __future__ import annotations

import math
import time
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .terrain_pipeline import derive_pass_seed
from .terrain_semantics import (
    BBox,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# U-valley carving
# ---------------------------------------------------------------------------


def _path_to_cells(
    path: Sequence[Tuple[float, float]],
    stack: TerrainMaskStack,
) -> List[Tuple[int, int]]:
    """Convert world-space (x, y) path to (row, col) cells on the tile grid."""
    cells: List[Tuple[int, int]] = []
    H, W = stack.height.shape
    for (wx, wy) in path:
        c = int(round((wx - stack.world_origin_x) / stack.cell_size))
        r = int(round((wy - stack.world_origin_y) / stack.cell_size))
        if 0 <= r < H and 0 <= c < W:
            cells.append((r, c))
    return cells


def carve_u_valley(
    stack: TerrainMaskStack,
    path: Sequence[Tuple[float, float]],
    width_m: float,
    depth_m: float,
) -> np.ndarray:
    """Return a height delta carving a U-shaped valley along ``path``.

    The cross-section is ``-depth * max(0, 1 - (d/half_width)^2)^0.5``
    approximated with a smooth flat-bottom profile. Not applied in
    place — caller decides whether to write.
    """
    if stack.height is None:
        raise ValueError("carve_u_valley requires stack.height")
    if width_m <= 0 or depth_m <= 0:
        raise ValueError("width_m and depth_m must be positive")

    H, W = stack.height.shape
    delta = np.zeros((H, W), dtype=np.float64)
    if len(path) < 2:
        return delta

    cells = _path_to_cells(path, stack)
    if len(cells) < 2:
        return delta

    half_cells = max(1.0, 0.5 * width_m / stack.cell_size)

    # Rasterize a distance-to-path field by Bresenham-ish dense sampling
    dense: List[Tuple[float, float]] = []
    for i in range(len(cells) - 1):
        r0, c0 = cells[i]
        r1, c1 = cells[i + 1]
        n = max(2, int(math.hypot(r1 - r0, c1 - c0)) + 1)
        for t in np.linspace(0.0, 1.0, n):
            dense.append((r0 + (r1 - r0) * t, c0 + (c1 - c0) * t))

    dense_arr = np.array(dense)  # (N, 2)

    # For each cell within a bounding box of the path, find min distance.
    _rr = np.arange(H).reshape(-1, 1)
    _cc = np.arange(W).reshape(1, -1)

    rmin = max(0, int(dense_arr[:, 0].min() - half_cells - 2))
    rmax = min(H, int(dense_arr[:, 0].max() + half_cells + 3))
    cmin = max(0, int(dense_arr[:, 1].min() - half_cells - 2))
    cmax = min(W, int(dense_arr[:, 1].max() + half_cells + 3))

    for r in range(rmin, rmax):
        for c in range(cmin, cmax):
            dr = dense_arr[:, 0] - r
            dc = dense_arr[:, 1] - c
            d2 = dr * dr + dc * dc
            dmin = math.sqrt(float(d2.min()))
            if dmin >= half_cells:
                continue
            # U-profile: flat bottom (dmin < 0.3*half) then smooth wall
            frac = dmin / half_cells
            if frac < 0.3:
                carve = 1.0
            else:
                t = (frac - 0.3) / 0.7
                carve = math.sqrt(max(0.0, 1.0 - t * t))
            delta[r, c] = -depth_m * carve

    return delta


# ---------------------------------------------------------------------------
# Moraines
# ---------------------------------------------------------------------------


def scatter_moraines(
    stack: TerrainMaskStack,
    glacier_path: Sequence[Tuple[float, float]],
    seed: int,
) -> List[Tuple[float, float, float]]:
    """Return a list of (x, y, radius_m) moraine placements.

    Moraines are deposits of till at the lateral edges and terminus of a
    glacier. We scatter along the path with deterministic RNG.
    """
    if len(glacier_path) < 2:
        return []
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)

    moraines: List[Tuple[float, float, float]] = []
    path_arr = np.array(glacier_path, dtype=np.float64)

    # Lateral moraines: scatter along edges perpendicular to segments
    for i in range(len(path_arr) - 1):
        p0 = path_arr[i]
        p1 = path_arr[i + 1]
        seg = p1 - p0
        seg_len = float(np.linalg.norm(seg))
        if seg_len < 1e-6:
            continue
        nhat = np.array([-seg[1], seg[0]]) / seg_len
        # 2 lateral moraines per segment
        for _ in range(2):
            t = float(rng.uniform(0.1, 0.9))
            side = 1.0 if rng.random() > 0.5 else -1.0
            offset = side * float(rng.uniform(8.0, 20.0))
            pos = p0 + seg * t + nhat * offset
            radius = float(rng.uniform(3.0, 10.0))
            moraines.append((float(pos[0]), float(pos[1]), radius))

    # Terminal moraine at end of path
    end = path_arr[-1]
    moraines.append(
        (float(end[0]), float(end[1]), float(rng.uniform(10.0, 25.0)))
    )
    return moraines


# ---------------------------------------------------------------------------
# Snow line
# ---------------------------------------------------------------------------


def compute_snow_line(
    stack: TerrainMaskStack,
    snow_line_altitude_m: float,
) -> np.ndarray:
    """Populate ``stack.snow_line_factor`` (H, W) in [0, 1].

    0 below the snow line, smoothly ramping to 1 above it with a
    50-meter transition band. Slope also reduces snow accumulation
    (steep cliff faces shed snow).
    """
    if stack.height is None:
        raise ValueError("compute_snow_line requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)
    band = 50.0
    raw = (h - snow_line_altitude_m) / band
    factor = np.clip(raw, 0.0, 1.0)

    if stack.slope is not None:
        slope = np.asarray(stack.slope, dtype=np.float64)
        # Reduce by up to 50% on very steep terrain
        slope_penalty = np.clip(slope / (math.pi / 2.0), 0.0, 1.0) * 0.5
        factor = factor * (1.0 - slope_penalty)

    factor = factor.astype(np.float32)
    stack.set("snow_line_factor", factor, "glacial")
    return factor


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


def pass_glacial(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle I pass: compute snow line + optional U-valley carving.

    Consumes: height (+ optional slope)
    Produces: snow_line_factor
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    hints = dict(state.intent.composition_hints) if state.intent else {}
    snow_alt = float(hints.get("snow_line_altitude_m", 2000.0))

    factor = compute_snow_line(stack, snow_alt)

    # Optional U-valley carving from hints
    carved = False
    H, W = stack.height.shape
    total_delta = np.zeros((H, W), dtype=np.float64)
    glacier_paths = hints.get("glacier_paths", [])
    if glacier_paths:
        _seed = derive_pass_seed(
            state.intent.seed,
            "glacial",
            state.tile_x,
            state.tile_y,
            region,
        )
        for gp in glacier_paths:
            path = gp.get("path", [])
            width = float(gp.get("width_m", 60.0))
            depth = float(gp.get("depth_m", 30.0))
            if len(path) >= 2:
                delta = carve_u_valley(stack, path, width, depth)
                total_delta += delta
                carved = True

    produced = ("snow_line_factor",)
    if carved:
        stack.set("glacial_delta", total_delta.astype(np.float32), "glacial")
        produced = ("snow_line_factor", "glacial_delta")

    return PassResult(
        pass_name="glacial",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=produced,
        metrics={
            "snow_line_altitude_m": snow_alt,
            "snow_coverage_fraction": float((factor > 0.5).mean()),
            "u_valleys_carved": int(len(glacier_paths)) if carved else 0,
        },
        issues=[],
    )


def get_ice_formation_specs(
    stack: TerrainMaskStack,
    *,
    max_formations: int = 5,
    seed: int = 42,
) -> list:
    """Return MeshSpec dicts for ice formations at high-altitude glacial sites.

    Scans the snow_line_factor channel for cells with high snow coverage
    and calls ``generate_ice_formation`` from terrain_features to produce
    standalone meshes suitable for Blender placement.

    Returns a list of dicts, each with keys ``mesh_spec`` and ``world_pos``.
    """
    from .terrain_features import generate_ice_formation

    factor = stack.get("snow_line_factor")
    if factor is None:
        return []

    rng = np.random.default_rng(seed)
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape

    # Find candidate cells with strong snow coverage
    candidates = np.argwhere(np.asarray(factor) > 0.7)
    if len(candidates) == 0:
        return []

    # Subsample to avoid excessive geometry
    indices = rng.choice(len(candidates), size=min(max_formations, len(candidates)), replace=False)
    results = []
    for idx in indices:
        r, c = int(candidates[idx][0]), int(candidates[idx][1])
        wx = stack.world_origin_x + c * stack.cell_size
        wy = stack.world_origin_y + r * stack.cell_size
        wz = float(h[r, c])
        spec = generate_ice_formation(
            width=rng.uniform(3.0, 8.0),
            height=rng.uniform(2.0, 6.0),
            depth=rng.uniform(2.0, 5.0),
            stalactite_count=int(rng.integers(4, 12)),
            ice_wall=bool(rng.random() > 0.5),
            seed=int(rng.integers(0, 2**31)),
        )
        results.append({"mesh_spec": spec, "world_pos": (wx, wy, wz)})
    return results


__all__ = [
    "carve_u_valley",
    "scatter_moraines",
    "compute_snow_line",
    "pass_glacial",
    "get_ice_formation_specs",
]
