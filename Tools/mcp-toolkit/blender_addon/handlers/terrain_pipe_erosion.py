"""Pipe-model hydraulic erosion for hero terrain nodes.

Implements the pipe-model (shallow water) erosion algorithm which is
better suited for hero nodes than the droplet-based approach. The pipe
model simulates water flow as flux through virtual pipes connecting
adjacent cells, producing more coherent drainage patterns.

Also provides Poisson blending for seamless compositing of hero terrain
patches into the surrounding base terrain.

NO bpy imports. Pure Python + numpy. Fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Pipe-model erosion
# ---------------------------------------------------------------------------


@dataclass
class PipeErosionResult:
    """Output of pipe-model erosion."""

    height: np.ndarray
    water_depth: np.ndarray
    sediment: np.ndarray
    velocity_x: np.ndarray
    velocity_y: np.ndarray
    erosion_amount: np.ndarray
    deposition_amount: np.ndarray
    metrics: Dict = field(default_factory=dict)


def pipe_model_erosion(
    heightmap: np.ndarray,
    iterations: int = 50,
    dt: float = 0.02,
    rain_rate: float = 0.01,
    evaporation_rate: float = 0.005,
    erosion_rate: float = 0.5,
    deposition_rate: float = 0.3,
    sediment_capacity: float = 1.0,
    gravity: float = 9.81,
    cell_size: float = 1.0,
    seed: int = 42,
    *,
    guard_mask: Optional[np.ndarray] = None,
    min_slope: float = 1e-4,
) -> PipeErosionResult:
    """Run pipe-model (shallow water) erosion on a heightmap.

    The algorithm simulates water flow using flux pipes between adjacent
    cells. Each iteration:
      1. Add rain
      2. Compute flux based on height + water differences
      3. Update water depth from flux divergence
      4. Compute velocity field from flux
      5. Erode/deposit based on capacity vs sediment load
      6. Transport sediment
      7. Evaporate water

    Args:
        heightmap: 2D terrain height array.
        iterations: Number of simulation steps.
        dt: Time step.
        rain_rate: Water added per cell per step.
        evaporation_rate: Fraction of water evaporated per step.
        erosion_rate: Erosion strength.
        deposition_rate: Deposition strength.
        sediment_capacity: Base sediment carrying capacity.
        gravity: Gravitational acceleration.
        cell_size: World-space cell size.
        seed: Random seed for rain distribution.
        guard_mask: Boolean mask; True cells are protected from erosion.
        min_slope: Minimum slope for capacity calculation.

    Returns:
        PipeErosionResult with eroded height and all intermediate channels.
    """
    h = np.asarray(heightmap, dtype=np.float64).copy()
    rows, cols = h.shape
    rng = np.random.RandomState(seed)

    # State arrays
    water = np.zeros_like(h)
    sediment = np.zeros_like(h)
    # Flux: left, right, top, bottom
    flux_l = np.zeros_like(h)
    flux_r = np.zeros_like(h)
    flux_t = np.zeros_like(h)
    flux_b = np.zeros_like(h)

    erosion_total = np.zeros_like(h)
    deposition_total = np.zeros_like(h)

    pipe_area = cell_size * cell_size
    pipe_length = cell_size

    if guard_mask is not None:
        gmask = np.asarray(guard_mask, dtype=bool)
        if gmask.shape != h.shape:
            raise ValueError(f"guard_mask shape {gmask.shape} != heightmap shape {h.shape}")
    else:
        gmask = None

    for iteration in range(iterations):
        # 1. Rain
        rain = rng.uniform(0.8, 1.2, size=h.shape) * rain_rate * dt
        water += rain

        # 2. Compute flux
        surface = h + water

        # Height differences to neighbors
        # Left: flux_l[r,c] = flow from (r,c) to (r,c-1)
        dh_l = np.zeros_like(h)
        dh_l[:, 1:] = surface[:, 1:] - surface[:, :-1]

        dh_r = np.zeros_like(h)
        dh_r[:, :-1] = surface[:, :-1] - surface[:, 1:]

        dh_t = np.zeros_like(h)
        dh_t[1:, :] = surface[1:, :] - surface[:-1, :]

        dh_b = np.zeros_like(h)
        dh_b[:-1, :] = surface[:-1, :] - surface[1:, :]

        # Update flux
        flux_factor = dt * gravity * pipe_area / pipe_length
        flux_l = np.maximum(0.0, flux_l + flux_factor * dh_l)
        flux_r = np.maximum(0.0, flux_r + flux_factor * dh_r)
        flux_t = np.maximum(0.0, flux_t + flux_factor * dh_t)
        flux_b = np.maximum(0.0, flux_b + flux_factor * dh_b)

        # Scale flux to not exceed available water
        total_flux = flux_l + flux_r + flux_t + flux_b
        available = water * pipe_area
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = np.where(
                total_flux > 0,
                np.minimum(1.0, available / (total_flux * dt + 1e-15)),
                0.0,
            )
        flux_l *= scale
        flux_r *= scale
        flux_t *= scale
        flux_b *= scale

        # 3. Update water from flux divergence
        # Inflow from neighbors
        inflow = np.zeros_like(h)
        inflow[:, 1:] += flux_r[:, :-1]    # right flux from left neighbor
        inflow[:, :-1] += flux_l[:, 1:]    # left flux from right neighbor
        inflow[1:, :] += flux_b[:-1, :]    # bottom flux from top neighbor
        inflow[:-1, :] += flux_t[1:, :]    # top flux from bottom neighbor

        outflow = flux_l + flux_r + flux_t + flux_b

        water += (inflow - outflow) * dt / pipe_area
        water = np.maximum(water, 0.0)

        # 4. Velocity field
        vel_x = np.zeros_like(h)
        vel_y = np.zeros_like(h)

        # X velocity from left/right flux difference
        vel_x[:, 1:-1] = (
            (flux_r[:, :-2] - flux_l[:, 1:-1] + flux_r[:, 1:-1] - flux_l[:, 2:])
            * 0.5
        )
        # Y velocity from top/bottom flux difference
        vel_y[1:-1, :] = (
            (flux_b[:-2, :] - flux_t[1:-1, :] + flux_b[1:-1, :] - flux_t[2:, :])
            * 0.5
        )

        with np.errstate(divide="ignore", invalid="ignore"):
            depth_factor = np.where(water > 1e-6, 1.0 / (water * cell_size), 0.0)
        vel_x *= depth_factor
        vel_y *= depth_factor

        velocity_mag = np.sqrt(vel_x ** 2 + vel_y ** 2)

        # 5. Erosion and deposition
        # Compute local slope
        padded = np.pad(h, 1, mode="edge")
        grad_x = (padded[1:-1, 2:] - padded[1:-1, :-2]) / (2.0 * cell_size)
        grad_y = (padded[2:, 1:-1] - padded[:-2, 1:-1]) / (2.0 * cell_size)
        slope = np.sqrt(grad_x ** 2 + grad_y ** 2)
        slope = np.maximum(slope, min_slope)

        # Sediment transport capacity
        capacity = sediment_capacity * slope * velocity_mag * water

        # Erode where capacity > sediment, deposit where sediment > capacity
        erode_mask = sediment < capacity
        deposit_mask = ~erode_mask

        erosion_step = np.zeros_like(h)
        deposition_step = np.zeros_like(h)

        erosion_step[erode_mask] = erosion_rate * dt * (
            capacity[erode_mask] - sediment[erode_mask]
        )
        deposition_step[deposit_mask] = deposition_rate * dt * (
            sediment[deposit_mask] - capacity[deposit_mask]
        )

        # Apply guard mask
        if gmask is not None:
            erosion_step[gmask] = 0.0
            deposition_step[gmask] = 0.0

        h -= erosion_step
        h += deposition_step
        sediment += erosion_step - deposition_step
        sediment = np.maximum(sediment, 0.0)

        erosion_total += erosion_step
        deposition_total += deposition_step

        # 6. Sediment transport (simple advection)
        # Shift sediment along velocity field using first-order upwind
        if velocity_mag.max() > 1e-6:
            shifted = sediment.copy()
            # Simple upwind advection
            shift_x = np.clip((vel_x * dt / cell_size).astype(int), -1, 1)
            shift_y = np.clip((vel_y * dt / cell_size).astype(int), -1, 1)
            # Apply shift (simplified -- full advection would use interpolation)
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    mask = (shift_x == dx) & (shift_y == dy)
                    if not np.any(mask):
                        continue
                    src_rows = slice(
                        max(0, -dy), min(rows, rows - dy)
                    )
                    src_cols = slice(
                        max(0, -dx), min(cols, cols - dx)
                    )
                    dst_rows = slice(
                        max(0, dy), min(rows, rows + dy)
                    )
                    dst_cols = slice(
                        max(0, dx), min(cols, cols + dx)
                    )
                    transfer = sediment[src_rows, src_cols] * mask[src_rows, src_cols] * 0.5
                    shifted[src_rows, src_cols] -= transfer
                    shifted[dst_rows, dst_cols] += transfer

            sediment = np.maximum(shifted, 0.0)

        # 7. Evaporation
        water *= (1.0 - evaporation_rate * dt)
        water = np.maximum(water, 0.0)

    return PipeErosionResult(
        height=h,
        water_depth=water,
        sediment=sediment,
        velocity_x=vel_x,
        velocity_y=vel_y,
        erosion_amount=erosion_total,
        deposition_amount=deposition_total,
        metrics={
            "iterations": iterations,
            "total_erosion": float(erosion_total.sum()),
            "total_deposition": float(deposition_total.sum()),
            "max_erosion": float(erosion_total.max()),
            "max_water_depth": float(water.max()),
            "mean_velocity": float(velocity_mag.mean()),
        },
    )


# ---------------------------------------------------------------------------
# Poisson blending
# ---------------------------------------------------------------------------


def poisson_blend(
    base: np.ndarray,
    patch: np.ndarray,
    mask: np.ndarray,
    *,
    iterations: int = 200,
    omega: float = 1.0,
) -> np.ndarray:
    """Poisson-blend a patch into a base heightmap using Gauss-Seidel SOR.

    Solves the Poisson equation to blend ``patch`` into ``base`` where
    ``mask`` is True, preserving the gradient field of ``patch`` while
    matching ``base`` at the boundary.

    This is the terrain equivalent of image Poisson blending -- it lets
    hero terrain patches merge seamlessly into surrounding terrain.

    Args:
        base: 2D base heightmap.
        patch: 2D patch heightmap (same shape as base).
        mask: Boolean mask; True = use patch gradients, False = use base.
        iterations: Number of Gauss-Seidel SOR iterations.
        omega: SOR relaxation factor (1.0 = Gauss-Seidel, >1.0 = SOR).

    Returns:
        Blended heightmap.
    """
    b = np.asarray(base, dtype=np.float64)
    p = np.asarray(patch, dtype=np.float64)
    m = np.asarray(mask, dtype=bool)

    if b.shape != p.shape or b.shape != m.shape:
        raise ValueError(
            f"Shape mismatch: base={b.shape} patch={p.shape} mask={m.shape}"
        )

    rows, cols = b.shape
    if rows < 3 or cols < 3:
        # Too small for Poisson blending
        return np.where(m, p, b)

    # Compute Laplacian of the patch (guidance field)
    lap_p = np.zeros_like(p)
    lap_p[1:-1, 1:-1] = (
        p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
        - 4.0 * p[1:-1, 1:-1]
    )

    # Initialize result with base heights
    result = b.copy()

    # Interior mask (exclude boundary cells which stay as base)
    interior = m.copy()
    interior[0, :] = False
    interior[-1, :] = False
    interior[:, 0] = False
    interior[:, -1] = False

    if not np.any(interior):
        return result

    # Gauss-Seidel SOR iterations
    for _ in range(iterations):
        # For each interior masked cell, solve:
        # result[r,c] = (sum of neighbors + lap_p[r,c]) / 4
        new_val = (
            result[:-2, 1:-1]   # top
            + result[2:, 1:-1]  # bottom
            + result[1:-1, :-2] # left
            + result[1:-1, 2:]  # right
            - lap_p[1:-1, 1:-1]
        ) / 4.0

        # Apply SOR update only where interior mask is True
        interior_core = interior[1:-1, 1:-1]
        old_val = result[1:-1, 1:-1]
        result[1:-1, 1:-1] = np.where(
            interior_core,
            old_val + omega * (new_val - old_val),
            old_val,
        )

    return result


def poisson_blend_patch(
    base_heightmap: np.ndarray,
    patch_heightmap: np.ndarray,
    patch_row: int,
    patch_col: int,
    *,
    fade_border: int = 4,
    iterations: int = 200,
) -> np.ndarray:
    """Blend a smaller patch into a larger base heightmap.

    Convenience wrapper that handles coordinate mapping and creates
    the blend mask with a fade border.

    Args:
        base_heightmap: Full tile heightmap.
        patch_heightmap: Smaller hero patch to blend in.
        patch_row: Row offset where patch is placed.
        patch_col: Column offset where patch is placed.
        fade_border: Border cells used for Poisson boundary conditions.
        iterations: Gauss-Seidel iterations.

    Returns:
        Modified base heightmap with patch blended in.
    """
    base = np.asarray(base_heightmap, dtype=np.float64).copy()
    patch = np.asarray(patch_heightmap, dtype=np.float64)

    pr, pc = patch.shape
    br, bc = base.shape

    # Clamp patch region to base bounds
    r0 = max(0, patch_row)
    c0 = max(0, patch_col)
    r1 = min(br, patch_row + pr)
    c1 = min(bc, patch_col + pc)

    if r1 <= r0 or c1 <= c0:
        return base  # No overlap

    # Extract overlapping regions
    pr0 = r0 - patch_row
    pc0 = c0 - patch_col
    pr1 = pr0 + (r1 - r0)
    pc1 = pc0 + (c1 - c0)

    region_h = r1 - r0
    region_w = c1 - c0

    # Create blend mask (True in interior, False at border)
    mask = np.zeros((region_h, region_w), dtype=bool)
    fb = min(fade_border, region_h // 2, region_w // 2)
    if fb > 0 and region_h > 2 * fb and region_w > 2 * fb:
        mask[fb:-fb, fb:-fb] = True
    elif region_h > 2 and region_w > 2:
        mask[1:-1, 1:-1] = True

    base_region = base[r0:r1, c0:c1].copy()
    patch_region = patch[pr0:pr1, pc0:pc1]

    blended = poisson_blend(base_region, patch_region, mask, iterations=iterations)
    base[r0:r1, c0:c1] = blended

    return base


__all__ = [
    "PipeErosionResult",
    "pipe_model_erosion",
    "poisson_blend",
    "poisson_blend_patch",
]
