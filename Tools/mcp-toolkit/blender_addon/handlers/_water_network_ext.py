"""Bundle C — WaterNetwork extension module.

Extension helpers for `_water_network.WaterNetwork` without editing that
file directly. Adds:
    - add_meander: sinusoidal perturbation of river paths
    - apply_bank_asymmetry: asymmetric bank erosion (left/right bias)
    - solve_outflow: pool → downstream outflow path solver
    - compute_wet_rock_mask: wetness proxy around water surfaces
    - compute_foam_mask / compute_mist_mask: shared foam/mist builders

Pure Python + numpy. No bpy/bmesh imports.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, List, Tuple

import numpy as np

from .terrain_semantics import TerrainMaskStack

if TYPE_CHECKING:  # pragma: no cover
    from .terrain_waterfalls import ImpactPool, WaterfallChain


# ---------------------------------------------------------------------------
# WaterNetwork upgrades
# ---------------------------------------------------------------------------


def add_meander(water_network: Any, amplitude: float) -> None:
    """Perturb each segment's waypoints sinusoidally to add meander.

    The perturbation is applied perpendicular to the segment direction.
    ``amplitude`` is in world-units. Safe to call on any WaterNetwork-like
    object exposing a ``segments`` dict mapping id → object with a
    ``waypoints`` list of (x, y, z) tuples.
    """
    if amplitude <= 0.0 or water_network is None:
        return
    segments = getattr(water_network, "segments", {})
    for seg in segments.values():
        waypoints = list(getattr(seg, "waypoints", []))
        n = len(waypoints)
        if n < 3:
            continue
        new_points: List[Tuple[float, float, float]] = []
        for i, (wx, wy, wz) in enumerate(waypoints):
            if i == 0 or i == n - 1:
                new_points.append((wx, wy, wz))
                continue
            prev = waypoints[i - 1]
            nxt = waypoints[i + 1]
            dx = nxt[0] - prev[0]
            dy = nxt[1] - prev[1]
            length = math.sqrt(dx * dx + dy * dy)
            if length < 1e-9:
                new_points.append((wx, wy, wz))
                continue
            # Perpendicular unit vector (rotate 90° CCW)
            px = -dy / length
            py = dx / length
            phase = (i / max(1, n - 1)) * math.pi * 4.0
            offset = math.sin(phase) * amplitude
            new_points.append((wx + px * offset, wy + py * offset, wz))
        seg.waypoints = new_points


def apply_bank_asymmetry(water_network: Any, bias: float) -> None:
    """Tag each segment with a bank-asymmetry bias.

    ``bias`` in [-1, 1]: negative = left bank wears faster, positive =
    right bank wears faster. Stored as ``segment.bank_asymmetry`` so
    downstream erosion passes can consume it.
    """
    bias = max(-1.0, min(1.0, float(bias)))
    if water_network is None:
        return
    segments = getattr(water_network, "segments", {})
    for seg in segments.values():
        try:
            setattr(seg, "bank_asymmetry", float(bias))
        except Exception:  # pragma: no cover
            pass


def solve_outflow(
    water_network: Any,
    pool: "ImpactPool",
) -> List[Tuple[float, float]]:
    """Solve a downstream outflow path from a pool.

    The solver walks in the pool's outflow direction in fixed steps for
    up to 16 nodes. If ``water_network`` exposes a heightmap we could
    refine this further; for now we emit a straight polyline that
    Bundle D's solver will later replace with a flow-aware trace.
    """
    path: List[Tuple[float, float]] = []
    cx, cy, _cz = pool.world_position
    dx = math.cos(pool.outflow_direction_rad)
    dy = math.sin(pool.outflow_direction_rad)
    step = max(1.0, pool.radius_m * 0.5)
    for i in range(1, 17):
        path.append((cx + dx * step * i, cy + dy * step * i))
    return path


# ---------------------------------------------------------------------------
# Mask builders (shared with terrain_waterfalls.py)
# ---------------------------------------------------------------------------


def _world_to_grid(
    stack: TerrainMaskStack, x: float, y: float,
) -> Tuple[int, int]:
    c = int((x - float(stack.world_origin_x)) / float(stack.cell_size))
    r = int((y - float(stack.world_origin_y)) / float(stack.cell_size))
    rows, cols = stack.height.shape
    r = max(0, min(rows - 1, r))
    c = max(0, min(cols - 1, c))
    return r, c


def compute_wet_rock_mask(
    stack: TerrainMaskStack,
    water_network: Any,
    radius_m: float = 3.0,
) -> np.ndarray:
    """Build a wet-rock mask around water surfaces.

    The mask is 1.0 at cells near a water surface (or existing
    ``water_surface`` / ``flow_accumulation`` cell) and falls off to 0 at
    ``radius_m``. If ``water_network`` is provided and exposes ``nodes``,
    each node also contributes a wet disc.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    wet = np.zeros((rows, cols), dtype=np.float32)
    cs = float(stack.cell_size)
    radius_cells = max(1, int(math.ceil(radius_m / cs)))

    # Seed from existing water_surface channel
    seeds: List[Tuple[int, int]] = []
    surface = stack.water_surface
    if surface is not None:
        surface_arr = np.asarray(surface)
        if surface_arr.shape == h.shape:
            ys, xs = np.where(surface_arr > 0.01)
            for r, c in zip(ys.tolist(), xs.tolist()):
                seeds.append((int(r), int(c)))

    # Seed from WaterNetwork nodes (if any)
    if water_network is not None:
        nodes = getattr(water_network, "nodes", {}) or {}
        for node in nodes.values():
            wx = getattr(node, "world_x", None)
            wy = getattr(node, "world_y", None)
            if wx is None or wy is None:
                continue
            r, c = _world_to_grid(stack, float(wx), float(wy))
            seeds.append((r, c))

    if not seeds:
        return wet

    # Stamp a radial falloff at every seed
    for (r, c) in seeds:
        r0 = max(0, r - radius_cells)
        r1 = min(rows, r + radius_cells + 1)
        c0 = max(0, c - radius_cells)
        c1 = min(cols, c + radius_cells + 1)
        for rr in range(r0, r1):
            for cc in range(c0, c1):
                dr = rr - r
                dc = cc - c
                dist = math.sqrt(dr * dr + dc * dc) * cs
                if dist > radius_m:
                    continue
                val = float(max(0.0, 1.0 - dist / max(radius_m, 1e-6)))
                if val > wet[rr, cc]:
                    wet[rr, cc] = val
    return wet


def compute_foam_mask(
    chain: "WaterfallChain",
    stack: TerrainMaskStack,
) -> np.ndarray:
    """Shared foam-mask builder — delegates to terrain_waterfalls for the math.

    Kept here so downstream modules can depend on ``_water_network_ext``
    without importing ``terrain_waterfalls`` (which imports this module
    for ``compute_wet_rock_mask``). Breaks a potential import cycle by
    doing the computation inline.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    foam = np.zeros_like(h, dtype=np.float32)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    pool_r, pool_c = _world_to_grid(
        stack, chain.pool.world_position[0], chain.pool.world_position[1]
    )
    radius_cells = max(1, int(math.ceil(chain.pool.radius_m / cs)))
    r0 = max(0, pool_r - radius_cells)
    r1 = min(rows, pool_r + radius_cells + 1)
    c0 = max(0, pool_c - radius_cells)
    c1 = min(cols, pool_c + radius_cells + 1)
    for rr in range(r0, r1):
        for cc in range(c0, c1):
            dr = rr - pool_r
            dc = cc - pool_c
            dist = math.sqrt(dr * dr + dc * dc) * cs
            if dist > chain.pool.radius_m:
                continue
            norm = dist / max(chain.pool.radius_m, 1e-6)
            val = float(chain.foam_intensity * max(0.0, 1.0 - norm))
            if val > foam[rr, cc]:
                foam[rr, cc] = val
    return foam


def compute_mist_mask(
    chain: "WaterfallChain",
    stack: TerrainMaskStack,
) -> np.ndarray:
    """Shared mist-mask builder — radial falloff around pool center."""
    h = np.asarray(stack.height, dtype=np.float64)
    mist = np.zeros_like(h, dtype=np.float32)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    pool_r, pool_c = _world_to_grid(
        stack, chain.pool.world_position[0], chain.pool.world_position[1]
    )
    radius_cells = max(1, int(math.ceil(chain.mist_radius_m / cs)))
    r0 = max(0, pool_r - radius_cells)
    r1 = min(rows, pool_r + radius_cells + 1)
    c0 = max(0, pool_c - radius_cells)
    c1 = min(cols, pool_c + radius_cells + 1)
    for rr in range(r0, r1):
        for cc in range(c0, c1):
            dr = rr - pool_r
            dc = cc - pool_c
            dist = math.sqrt(dr * dr + dc * dc) * cs
            if dist > chain.mist_radius_m:
                continue
            norm = dist / max(chain.mist_radius_m, 1e-6)
            val = float(max(0.0, 1.0 - norm))
            if val > mist[rr, cc]:
                mist[rr, cc] = val
    return mist


__all__ = [
    "add_meander",
    "apply_bank_asymmetry",
    "solve_outflow",
    "compute_wet_rock_mask",
    "compute_foam_mask",
    "compute_mist_mask",
]
