"""Pure-logic hydraulic and thermal erosion on numpy heightmap arrays.

NO bpy/bmesh imports. All functions accept numpy arrays and return numpy
arrays of the same shape. Fully testable without Blender.

Provides:
  - apply_hydraulic_erosion: Droplet-based hydraulic erosion simulation
  - apply_thermal_erosion: Talus-angle thermal weathering simulation
"""

from __future__ import annotations

import math
import random as _random

import numpy as np


# ---------------------------------------------------------------------------
# Hydraulic erosion (droplet-based)
# ---------------------------------------------------------------------------

def apply_hydraulic_erosion(
    heightmap: np.ndarray,
    iterations: int = 1000,
    seed: int = 0,
    inertia: float = 0.05,
    capacity: float = 4.0,
    deposition: float = 0.3,
    erosion_rate: float = 0.3,
    evaporation: float = 0.01,
    min_slope: float = 0.01,
    radius: int = 3,
    max_lifetime: int = 30,
    height_range: float | None = None,
) -> np.ndarray:
    """Apply droplet-based hydraulic erosion to a heightmap.

    Simulates water droplets flowing downhill, eroding sediment from steep
    areas and depositing it in flat areas or when slowing down.

    Parameters
    ----------
    heightmap : np.ndarray
        2D heightmap with arbitrary numeric values.
    iterations : int
        Number of droplets to simulate.
    seed : int
        Random seed for deterministic results.
    inertia : float
        Droplet direction inertia (0=follow gradient, 1=keep direction).
    capacity : float
        Sediment capacity multiplier.
    deposition : float
        Fraction of excess sediment deposited per step.
    erosion_rate : float
        Fraction of capacity deficit eroded per step.
    evaporation : float
        Water evaporation rate per step.
    min_slope : float
        Minimum slope for capacity calculation.
    radius : int
        Erosion/deposition brush radius.
    max_lifetime : int
        Maximum steps per droplet before evaporation.
    height_range : float | None
        Optional world-height range for scaling ``min_slope``. When omitted,
        the range is inferred from the input heightmap.

    Returns
    -------
    np.ndarray
        Eroded heightmap, same shape, clamped to the input value range.
    """
    result = heightmap.astype(np.float64).copy()
    rows, cols = result.shape
    rng = _random.Random(seed)
    source_min = float(result.min()) if result.size else 0.0
    source_max = float(result.max()) if result.size else 0.0
    input_range = float(height_range) if height_range is not None else max(source_max - source_min, 1e-12)
    effective_min_slope = min_slope * max(input_range, 1e-12)

    for _ in range(iterations):
        # Spawn droplet at random position
        px = rng.random() * (cols - 2) + 0.5
        py = rng.random() * (rows - 2) + 0.5
        dx_dir = 0.0
        dy_dir = 0.0
        speed = 1.0
        water = 1.0
        sediment = 0.0

        for _step in range(max_lifetime):
            ix = int(px)
            iy = int(py)

            if ix < 1 or ix >= cols - 2 or iy < 1 or iy >= rows - 2:
                break

            # Compute gradient using bilinear interpolation
            fx = px - ix
            fy = py - iy

            h00 = result[iy, ix]
            h10 = result[iy, ix + 1]
            h01 = result[iy + 1, ix]
            h11 = result[iy + 1, ix + 1]

            # Gradient
            grad_x = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
            grad_y = (h01 - h00) * (1 - fx) + (h11 - h10) * fx

            # Update direction with inertia
            dx_dir = dx_dir * inertia - grad_x * (1 - inertia)
            dy_dir = dy_dir * inertia - grad_y * (1 - inertia)

            # Normalize direction
            length = math.sqrt(dx_dir * dx_dir + dy_dir * dy_dir)
            if length < 1e-10:
                # Random direction if stuck
                angle = rng.random() * 2 * math.pi
                dx_dir = math.cos(angle)
                dy_dir = math.sin(angle)
            else:
                dx_dir /= length
                dy_dir /= length

            # Move droplet
            new_px = px + dx_dir
            new_py = py + dy_dir

            nix = int(new_px)
            niy = int(new_py)
            if nix < 0 or nix >= cols - 1 or niy < 0 or niy >= rows - 1:
                break

            # Height difference
            new_fx = new_px - nix
            new_fy = new_py - niy
            new_h = (
                result[niy, nix] * (1 - new_fx) * (1 - new_fy)
                + result[niy, min(nix + 1, cols - 1)] * new_fx * (1 - new_fy)
                + result[min(niy + 1, rows - 1), nix] * (1 - new_fx) * new_fy
                + result[min(niy + 1, rows - 1), min(nix + 1, cols - 1)] * new_fx * new_fy
            )
            old_h = (
                h00 * (1 - fx) * (1 - fy)
                + h10 * fx * (1 - fy)
                + h01 * (1 - fx) * fy
                + h11 * fx * fy
            )
            h_diff = new_h - old_h

            # Sediment capacity
            c = max(-h_diff, effective_min_slope) * speed * water * capacity

            if sediment > c or h_diff > 0:
                # Deposit sediment
                if h_diff > 0:
                    deposit_amount = min(sediment, h_diff)
                else:
                    deposit_amount = (sediment - c) * deposition
                sediment -= deposit_amount
                # Deposit at current position
                _deposit(result, ix, iy, fx, fy, deposit_amount)
            else:
                # Erode
                erode_amount = min((c - sediment) * erosion_rate, -h_diff)
                erode_amount = max(erode_amount, 0.0)
                sediment += erode_amount
                # Erode at current position using brush
                _erode_brush(result, ix, iy, erode_amount, radius, rows, cols)

            # Update speed and water
            speed = math.sqrt(max(speed * speed + h_diff, 0.01))
            water *= (1 - evaporation)

            px = new_px
            py = new_py

            if water < 0.001:
                break

    return np.clip(result, source_min, source_max)


def _deposit(
    hmap: np.ndarray, ix: int, iy: int, fx: float, fy: float, amount: float
) -> None:
    """Deposit sediment using bilinear weights."""
    rows, cols = hmap.shape
    if iy < 0 or iy >= rows - 1 or ix < 0 or ix >= cols - 1:
        return
    hmap[iy, ix] += amount * (1 - fx) * (1 - fy)
    hmap[iy, ix + 1] += amount * fx * (1 - fy)
    hmap[iy + 1, ix] += amount * (1 - fx) * fy
    hmap[iy + 1, ix + 1] += amount * fx * fy


def _erode_brush(
    hmap: np.ndarray,
    cx: int,
    cy: int,
    amount: float,
    radius: int,
    rows: int,
    cols: int,
) -> None:
    """Erode heightmap using a weighted brush kernel."""
    total_weight = 0.0
    weights: list[tuple[int, int, float]] = []

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ny = cy + dy
            nx = cx + dx
            if 0 <= ny < rows and 0 <= nx < cols:
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= radius:
                    w = max(0.0, radius - dist)
                    weights.append((ny, nx, w))
                    total_weight += w

    if total_weight > 0:
        for ny, nx, w in weights:
            hmap[ny, nx] -= amount * (w / total_weight)


# ---------------------------------------------------------------------------
# Thermal erosion (talus-based)
# ---------------------------------------------------------------------------

def apply_thermal_erosion(
    heightmap: np.ndarray,
    iterations: int = 10,
    talus_angle: float = 40.0,
    cell_size: float = 1.0,
) -> np.ndarray:
    """Apply thermal (talus) erosion to a heightmap.

    For each cell, if the slope to any neighbor exceeds the talus angle,
    material is transferred downhill to reduce the slope.

    Parameters
    ----------
    heightmap : np.ndarray
        2D heightmap with arbitrary numeric values.
    iterations : int
        Number of erosion passes.
    talus_angle : float
        Maximum stable slope angle in degrees. Slopes steeper than this
        will shed material.
    cell_size : float
        World-space spacing between adjacent samples. Larger cells need a
        proportionally larger height delta before talus transfer should occur.

    Returns
    -------
    np.ndarray
        Eroded heightmap, same shape, clamped to the input value range.
    """
    result = heightmap.astype(np.float64).copy()
    rows, cols = result.shape
    source_min = float(result.min()) if result.size else 0.0
    source_max = float(result.max()) if result.size else 0.0
    sample_spacing = max(float(cell_size), 1e-9)

    # Convert talus angle to height difference threshold
    # For adjacent cells at distance 1, tan(angle) = height_diff / 1
    talus_threshold = math.tan(math.radians(talus_angle))

    # 8-connected neighbor offsets with distances
    offsets = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            dist = math.sqrt(dr * dr + dc * dc)
            offsets.append((dr, dc, dist))

    for _iteration in range(iterations):
        delta = np.zeros_like(result)

        # Vectorized: process all 8 neighbors via padded array shifts
        padded = np.pad(result, 1, mode='edge')

        accumulated_max_diff = np.zeros_like(result)
        accumulated_total_diff = np.zeros_like(result)
        neighbor_excess: list[tuple[int, int, np.ndarray]] = []

        for dr, dc, dist in offsets:
            shifted = padded[1 + dr:1 + dr + rows, 1 + dc:1 + dc + cols]
            slope = (result - shifted) / (dist * sample_spacing)
            excess = np.maximum(slope - talus_threshold, 0.0)
            accumulated_total_diff += excess
            accumulated_max_diff = np.maximum(accumulated_max_diff, excess)
            neighbor_excess.append((dr, dc, excess))

        has_transfer = accumulated_total_diff > 0
        transfer = accumulated_max_diff * 0.5

        for dr, dc, excess in neighbor_excess:
            with np.errstate(divide='ignore', invalid='ignore'):
                fraction = np.where(has_transfer, excess / accumulated_total_diff, 0.0)
            amount = transfer * fraction * has_transfer

            delta -= amount
            # Shift amount into neighbor position
            r_src_start = max(0, -dr)
            r_src_end = min(rows, rows - dr)
            c_src_start = max(0, -dc)
            c_src_end = min(cols, cols - dc)
            r_dst_start = max(0, dr)
            c_dst_start = max(0, dc)
            r_dst_end = r_dst_start + (r_src_end - r_src_start)
            c_dst_end = c_dst_start + (c_src_end - c_src_start)
            delta[r_dst_start:r_dst_end, c_dst_start:c_dst_end] += \
                amount[r_src_start:r_src_end, c_src_start:c_src_end]

        result += delta
        result = np.clip(result, source_min, source_max)

    return result
