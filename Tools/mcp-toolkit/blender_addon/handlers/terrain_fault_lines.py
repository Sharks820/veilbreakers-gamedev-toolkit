"""Terrain fault line displacement system.

Generates geological fault lines that create visible height displacement
across the terrain. Fault lines interact with rock_hardness from the
stratigraphy system -- harder rock resists displacement, softer rock
deforms more.

Fault lines are defined as line segments in world space. Each fault
displaces terrain height on one side (the "hanging wall") relative to
the other side (the "footwall"), creating realistic geological features
like scarps, rifts, and thrust faults.

NO bpy imports. Pure Python + numpy. Fully unit-testable.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Fault definition
# ---------------------------------------------------------------------------


@dataclass
class FaultLine:
    """A geological fault line segment in world space."""

    fault_id: str
    start: Tuple[float, float]  # (x, y) world coordinates
    end: Tuple[float, float]    # (x, y) world coordinates
    displacement: float = 5.0   # vertical displacement in meters
    fault_type: str = "normal"  # normal, reverse, strike_slip
    width: float = 20.0         # transition zone width in meters
    roughness: float = 0.3      # 0-1, adds noise to the fault trace
    seed: int = 42

    @property
    def direction(self) -> Tuple[float, float]:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            return (1.0, 0.0)
        return (dx / length, dy / length)

    @property
    def normal(self) -> Tuple[float, float]:
        """Normal vector (perpendicular to fault direction, points to hanging wall)."""
        dx, dy = self.direction
        return (-dy, dx)

    @property
    def length(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# Fault displacement computation
# ---------------------------------------------------------------------------


def signed_distance_to_fault(
    x: np.ndarray,
    y: np.ndarray,
    fault: FaultLine,
) -> np.ndarray:
    """Compute signed distance from each (x,y) point to the fault line.

    Positive = hanging wall side, negative = footwall side.
    Points beyond the fault segment endpoints are handled by capping
    the projection to the segment length.

    Args:
        x: 2D array of x coordinates.
        y: 2D array of y coordinates.
        fault: FaultLine definition.

    Returns:
        2D array of signed distances.
    """
    sx, sy = fault.start
    dx, dy = fault.direction
    nx, ny = fault.normal

    # Vector from fault start to each point
    px = x - sx
    py = y - sy

    # Project onto fault direction (along-fault distance)
    along = px * dx + py * dy

    # Clamp to segment length for distance calculation
    fault_len = fault.length
    along_clamped = np.clip(along, 0.0, fault_len)

    # Closest point on fault segment
    closest_x = sx + along_clamped * dx
    closest_y = sy + along_clamped * dy

    # Vector from closest point to actual point
    to_point_x = x - closest_x
    to_point_y = y - closest_y

    # Signed distance (positive on normal side = hanging wall)
    signed_dist = to_point_x * nx + to_point_y * ny

    # For points beyond segment endpoints, use actual distance (unsigned-like fade)
    beyond_start = along < 0.0
    beyond_end = along > fault_len
    beyond = beyond_start | beyond_end

    # For beyond-segment points, compute actual distance and preserve sign
    actual_dist = np.sqrt(to_point_x ** 2 + to_point_y ** 2)
    # Preserve the sign from the normal-projected distance
    sign = np.sign(signed_dist)
    sign = np.where(sign == 0.0, 1.0, sign)

    result = np.where(beyond, sign * actual_dist, signed_dist)
    return result


def compute_fault_displacement(
    heightmap: np.ndarray,
    fault: FaultLine,
    cell_size: float,
    world_origin_x: float,
    world_origin_y: float,
    *,
    rock_hardness: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Compute the displacement delta from a single fault line.

    The displacement follows a smoothstep profile across the fault width,
    modulated by rock_hardness if provided. Harder rock (values near 1.0)
    resists displacement; softer rock (values near 0.0) deforms fully.

    Args:
        heightmap: 2D heightmap array (used for shape only).
        fault: FaultLine definition.
        cell_size: World-space size of each cell.
        world_origin_x: World X coordinate of tile origin.
        world_origin_y: World Y coordinate of tile origin.
        rock_hardness: Optional 2D array [0,1] where 1=hard, 0=soft.

    Returns:
        2D displacement delta array (add to heightmap).
    """
    rows, cols = heightmap.shape

    # Build world-space coordinate grids
    col_coords = world_origin_x + np.arange(cols, dtype=np.float64) * cell_size
    row_coords = world_origin_y + np.arange(rows, dtype=np.float64) * cell_size
    x_grid, y_grid = np.meshgrid(col_coords, row_coords)

    # Signed distance to fault
    dist = signed_distance_to_fault(x_grid, y_grid, fault)

    # Smoothstep displacement profile
    half_width = max(fault.width * 0.5, 1e-6)
    t = np.clip(dist / half_width, -1.0, 1.0)

    # Smoothstep: maps [-1, 1] to [0, 1]
    s = (t + 1.0) * 0.5  # map to [0, 1]
    s = s * s * (3.0 - 2.0 * s)  # smoothstep

    # Apply displacement based on fault type
    if fault.fault_type == "normal":
        # Normal fault: hanging wall drops
        delta = (s - 0.5) * fault.displacement
    elif fault.fault_type == "reverse":
        # Reverse fault: hanging wall rises
        delta = (0.5 - s) * fault.displacement
    elif fault.fault_type == "strike_slip":
        # Strike-slip: lateral offset simulated as micro-displacement
        # with alternating sign along the fault
        along_fault = (x_grid - fault.start[0]) * fault.direction[0] + \
                      (y_grid - fault.start[1]) * fault.direction[1]
        lateral_phase = np.sin(along_fault * 0.1)
        delta = (s - 0.5) * fault.displacement * 0.3 * lateral_phase
    else:
        delta = (s - 0.5) * fault.displacement

    # Add roughness noise along the fault trace
    if fault.roughness > 0.0:
        rng = np.random.RandomState(fault.seed)
        noise = rng.randn(*delta.shape) * fault.roughness * fault.displacement * 0.1
        # Fade noise away from fault
        noise_fade = np.exp(-np.abs(dist) / max(half_width * 2.0, 1e-6))
        delta += noise * noise_fade

    # Modulate by rock hardness (soft rock deforms more)
    if rock_hardness is not None:
        rh = np.asarray(rock_hardness, dtype=np.float64)
        if rh.shape != delta.shape:
            raise ValueError(
                f"rock_hardness shape {rh.shape} != heightmap shape {delta.shape}"
            )
        # Hardness 1.0 = 20% displacement, hardness 0.0 = 100% displacement
        hardness_factor = 1.0 - 0.8 * np.clip(rh, 0.0, 1.0)
        delta *= hardness_factor

    return delta


def apply_fault_lines(
    heightmap: np.ndarray,
    faults: List[FaultLine],
    cell_size: float,
    world_origin_x: float,
    world_origin_y: float,
    *,
    rock_hardness: Optional[np.ndarray] = None,
    guard_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Dict]:
    """Apply multiple fault lines to a heightmap.

    Args:
        heightmap: 2D heightmap to modify.
        faults: List of FaultLine definitions.
        cell_size: Cell size in world units.
        world_origin_x, world_origin_y: Tile world origin.
        rock_hardness: Optional hardness channel from stratigraphy.
        guard_mask: Optional boolean mask; True cells are not modified.

    Returns:
        Tuple of (modified_heightmap, metrics_dict).
    """
    h = np.asarray(heightmap, dtype=np.float64).copy()
    total_displacement = np.zeros_like(h)

    for fault in faults:
        delta = compute_fault_displacement(
            h, fault, cell_size, world_origin_x, world_origin_y,
            rock_hardness=rock_hardness,
        )
        total_displacement += delta

    # Apply guard mask: zero out displacement in guarded cells
    if guard_mask is not None:
        gm = np.asarray(guard_mask, dtype=bool)
        if gm.shape == total_displacement.shape:
            total_displacement[gm] = 0.0

    h += total_displacement

    metrics = {
        "fault_count": len(faults),
        "max_displacement": float(np.abs(total_displacement).max()),
        "mean_displacement": float(np.abs(total_displacement).mean()),
        "total_affected_cells": int(np.sum(np.abs(total_displacement) > 1e-6)),
    }

    return h, metrics


# ---------------------------------------------------------------------------
# Fault line generation helpers
# ---------------------------------------------------------------------------


def generate_random_faults(
    region_min_x: float,
    region_min_y: float,
    region_max_x: float,
    region_max_y: float,
    count: int = 3,
    seed: int = 42,
    *,
    displacement_range: Tuple[float, float] = (2.0, 10.0),
    width_range: Tuple[float, float] = (10.0, 40.0),
) -> List[FaultLine]:
    """Generate random fault lines within a region.

    Args:
        region_min_x, region_min_y, region_max_x, region_max_y: Bounds.
        count: Number of faults to generate.
        seed: Random seed for reproducibility.
        displacement_range: (min, max) displacement in meters.
        width_range: (min, max) fault width in meters.

    Returns:
        List of FaultLine instances.
    """
    rng = np.random.RandomState(seed)
    faults = []

    rx = region_max_x - region_min_x
    ry = region_max_y - region_min_y

    for i in range(count):
        # Random start and end points
        sx = region_min_x + rng.random() * rx
        sy = region_min_y + rng.random() * ry
        ex = region_min_x + rng.random() * rx
        ey = region_min_y + rng.random() * ry

        # Ensure minimum length
        dx = ex - sx
        dy = ey - sy
        length = math.sqrt(dx * dx + dy * dy)
        if length < min(rx, ry) * 0.2:
            angle = rng.random() * 2 * math.pi
            half_len = min(rx, ry) * 0.3
            ex = sx + math.cos(angle) * half_len
            ey = sy + math.sin(angle) * half_len

        disp = displacement_range[0] + rng.random() * (displacement_range[1] - displacement_range[0])
        width = width_range[0] + rng.random() * (width_range[1] - width_range[0])

        fault_types = ["normal", "reverse", "strike_slip"]
        ft = fault_types[rng.randint(0, len(fault_types))]

        # Derive per-fault seed deterministically
        fault_seed_payload = json.dumps([seed, i]).encode()
        fault_seed = int.from_bytes(
            hashlib.sha256(fault_seed_payload).digest()[:4], "big"
        ) & 0xFFFFFFFF

        faults.append(FaultLine(
            fault_id=f"fault_{seed}_{i}",
            start=(sx, sy),
            end=(ex, ey),
            displacement=disp,
            fault_type=ft,
            width=width,
            roughness=0.2 + rng.random() * 0.3,
            seed=fault_seed,
        ))

    return faults


__all__ = [
    "FaultLine",
    "signed_distance_to_fault",
    "compute_fault_displacement",
    "apply_fault_lines",
    "generate_random_faults",
]
