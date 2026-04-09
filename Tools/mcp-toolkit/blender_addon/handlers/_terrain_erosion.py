"""Pure-logic hydraulic and thermal erosion on numpy heightmap arrays.

Bundle A refactor: the new ``*_masks`` entry points return rich
``ErosionMasks`` / ``ThermalErosionMasks`` dataclasses exposing every
intermediate signal (erosion_amount, deposition_amount, wetness, drainage,
bank_instability, talus). The legacy ``apply_hydraulic_erosion`` /
``apply_thermal_erosion`` functions remain as compat wrappers that return
only the eroded ``np.ndarray`` clamped to the source range (preserving
existing callers and tests).

NO bpy/bmesh imports. All functions accept numpy arrays and return numpy
arrays (or ErosionMasks containing numpy arrays) of the same shape.
Fully testable without Blender.

Provides:
  - apply_hydraulic_erosion      (legacy np.ndarray return)
  - apply_hydraulic_erosion_masks (new, returns ErosionMasks)
  - apply_thermal_erosion        (legacy np.ndarray return)
  - apply_thermal_erosion_masks  (new, returns ThermalErosionMasks)
  - ErosionMasks, ThermalErosionMasks dataclasses
"""

from __future__ import annotations

import math
import random as _random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ErosionMasks:
    """Complete output of droplet-based hydraulic erosion.

    All fields share the heightmap shape (H, W). ``height`` is NOT clipped
    to the input range — it holds the true world-unit eroded surface.
    """

    height: np.ndarray
    erosion_amount: np.ndarray      # per-cell net material removed (>= 0)
    deposition_amount: np.ndarray   # per-cell net material added (>= 0)
    wetness: np.ndarray             # accumulated droplet water-step contact
    drainage: np.ndarray            # log1p of droplet pass-through count
    bank_instability: np.ndarray    # curvature magnitude where wetness > 0
    metrics: dict = field(default_factory=dict)


@dataclass
class ThermalErosionMasks:
    """Complete output of talus-angle thermal erosion."""

    height: np.ndarray
    talus: np.ndarray               # accumulated material moved per cell
    metrics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Hydraulic erosion — new masks entry point
# ---------------------------------------------------------------------------


def apply_hydraulic_erosion_masks(
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
    height_range: Optional[float] = None,
    *,
    hero_exclusion: Optional[np.ndarray] = None,
) -> ErosionMasks:
    """Apply droplet-based hydraulic erosion and return the full mask set.

    Parameters mirror ``apply_hydraulic_erosion``. The extra
    ``hero_exclusion`` argument accepts a boolean mask of cells where
    droplets should not erode or deposit (protected hero regions).

    The returned ``height`` is NOT clipped — it reflects the true
    world-unit eroded surface including any out-of-source-range values.

    Returns
    -------
    ErosionMasks
        Contains height plus erosion_amount, deposition_amount, wetness,
        drainage, bank_instability, and a metrics dict.
    """
    h_in = np.asarray(heightmap, dtype=np.float64)
    result = h_in.copy()
    rows, cols = result.shape
    rng = _random.Random(seed)

    source_min = float(h_in.min()) if h_in.size else 0.0
    source_max = float(h_in.max()) if h_in.size else 0.0
    input_range = (
        float(height_range)
        if height_range is not None
        else max(source_max - source_min, 1e-12)
    )
    effective_min_slope = min_slope * max(input_range, 1e-12)

    erosion_amount = np.zeros_like(result, dtype=np.float64)
    deposition_amount = np.zeros_like(result, dtype=np.float64)
    wetness = np.zeros_like(result, dtype=np.float64)
    drainage_count = np.zeros_like(result, dtype=np.float64)

    if hero_exclusion is not None:
        hero_mask = np.asarray(hero_exclusion, dtype=bool)
        if hero_mask.shape != result.shape:
            raise ValueError(
                f"hero_exclusion shape {hero_mask.shape} does not match "
                f"heightmap shape {result.shape}"
            )
    else:
        hero_mask = None

    for _ in range(iterations):
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

            fx = px - ix
            fy = py - iy

            h00 = result[iy, ix]
            h10 = result[iy, ix + 1]
            h01 = result[iy + 1, ix]
            h11 = result[iy + 1, ix + 1]

            grad_x = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
            grad_y = (h01 - h00) * (1 - fx) + (h11 - h10) * fx

            dx_dir = dx_dir * inertia - grad_x * (1 - inertia)
            dy_dir = dy_dir * inertia - grad_y * (1 - inertia)

            length = math.sqrt(dx_dir * dx_dir + dy_dir * dy_dir)
            if length < 1e-10:
                angle = rng.random() * 2 * math.pi
                dx_dir = math.cos(angle)
                dy_dir = math.sin(angle)
            else:
                dx_dir /= length
                dy_dir /= length

            new_px = px + dx_dir
            new_py = py + dy_dir

            nix = int(new_px)
            niy = int(new_py)
            if nix < 0 or nix >= cols - 1 or niy < 0 or niy >= rows - 1:
                break

            new_fx = new_px - nix
            new_fy = new_py - niy
            new_h = (
                result[niy, nix] * (1 - new_fx) * (1 - new_fy)
                + result[niy, min(nix + 1, cols - 1)] * new_fx * (1 - new_fy)
                + result[min(niy + 1, rows - 1), nix] * (1 - new_fx) * new_fy
                + result[min(niy + 1, rows - 1), min(nix + 1, cols - 1)]
                * new_fx
                * new_fy
            )
            old_h = (
                h00 * (1 - fx) * (1 - fy)
                + h10 * fx * (1 - fy)
                + h01 * (1 - fx) * fy
                + h11 * fx * fy
            )
            h_diff = new_h - old_h

            c = max(-h_diff, effective_min_slope) * speed * water * capacity

            # Record wetness and drainage at current cell
            wetness[iy, ix] += water
            drainage_count[iy, ix] += 1.0

            skip_cell = hero_mask is not None and bool(hero_mask[iy, ix])

            if sediment > c or h_diff > 0:
                if h_diff > 0:
                    deposit_amount = min(sediment, h_diff)
                else:
                    deposit_amount = (sediment - c) * deposition
                if skip_cell:
                    deposit_amount = 0.0
                sediment -= deposit_amount
                if deposit_amount != 0.0:
                    _deposit(result, ix, iy, fx, fy, deposit_amount)
                    _deposit(deposition_amount, ix, iy, fx, fy, deposit_amount)
            else:
                erode_amount = min((c - sediment) * erosion_rate, -h_diff)
                erode_amount = max(erode_amount, 0.0)
                if skip_cell:
                    erode_amount = 0.0
                sediment += erode_amount
                if erode_amount != 0.0:
                    _erode_brush(result, ix, iy, erode_amount, radius, rows, cols)
                    _erode_brush(
                        erosion_amount,
                        ix,
                        iy,
                        -erode_amount,  # negate so erosion_amount accumulates positively
                        radius,
                        rows,
                        cols,
                    )

            normalized_h_diff = h_diff / max(input_range, 1e-12)
            speed = math.sqrt(max(speed * speed + normalized_h_diff, 0.01))
            water *= (1 - evaporation)

            px = new_px
            py = new_py

            if water < 0.001:
                break

    # drainage → log1p of droplet count
    drainage = np.log1p(drainage_count)

    # bank_instability: local curvature (Laplacian) where wetness > 0
    padded = np.pad(result, 1, mode="edge")
    d2dx2 = padded[1:-1, 2:] - 2.0 * result + padded[1:-1, :-2]
    d2dy2 = padded[2:, 1:-1] - 2.0 * result + padded[:-2, 1:-1]
    curvature = d2dx2 + d2dy2
    bank_instability = np.where(wetness > 0.0, np.abs(curvature), 0.0)

    # Normalize wetness to 0..1 (relative)
    max_wet = float(wetness.max()) if wetness.size else 0.0
    wetness_norm = wetness / max_wet if max_wet > 0.0 else wetness

    return ErosionMasks(
        height=result,
        erosion_amount=erosion_amount,
        deposition_amount=deposition_amount,
        wetness=wetness_norm,
        drainage=drainage,
        bank_instability=bank_instability,
        metrics={
            "iterations": int(iterations),
            "source_min": source_min,
            "source_max": source_max,
            "input_range": input_range,
            "max_wetness": max_wet,
            "total_erosion": float(erosion_amount.sum()),
            "total_deposition": float(deposition_amount.sum()),
        },
    )


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
    height_range: Optional[float] = None,
) -> np.ndarray:
    """Legacy compat wrapper — returns the eroded heightmap np.ndarray only.

    Clamps output to the source value range for behavior parity with
    pre-Bundle-A callers. New code should call ``apply_hydraulic_erosion_masks``.
    """
    h_in = np.asarray(heightmap, dtype=np.float64)
    source_min = float(h_in.min()) if h_in.size else 0.0
    source_max = float(h_in.max()) if h_in.size else 0.0
    masks = apply_hydraulic_erosion_masks(
        h_in,
        iterations=iterations,
        seed=seed,
        inertia=inertia,
        capacity=capacity,
        deposition=deposition,
        erosion_rate=erosion_rate,
        evaporation=evaporation,
        min_slope=min_slope,
        radius=radius,
        max_lifetime=max_lifetime,
        height_range=height_range,
    )
    return np.clip(masks.height, source_min, source_max)


def _deposit(
    hmap: np.ndarray, ix: int, iy: int, fx: float, fy: float, amount: float
) -> None:
    """Deposit material at (ix, iy) using bilinear weights."""
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
    """Apply a weighted brush-shaped delta at (cx, cy).

    When called on ``result`` with a positive ``amount`` the brush removes
    material (matches legacy behavior where erode_amount was positive
    but subtracted below). When called on ``erosion_amount`` with a
    negative amount the brush accumulates the absolute removed values
    (so erosion_amount remains non-negative after negation).
    """
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
# Thermal erosion — new masks entry point
# ---------------------------------------------------------------------------


def apply_thermal_erosion_masks(
    heightmap: np.ndarray,
    iterations: int = 10,
    talus_angle: float = 40.0,
    cell_size: float = 1.0,
) -> ThermalErosionMasks:
    """Apply talus-angle thermal erosion and return ThermalErosionMasks.

    Accumulates the ``talus`` channel from the absolute magnitude of
    material moved per cell across all iterations. The returned
    ``height`` is NOT clipped — legacy wrapper does that.
    """
    h_in = np.asarray(heightmap, dtype=np.float64)
    result = h_in.copy()
    rows, cols = result.shape

    sample_spacing = max(float(cell_size), 1e-9)
    talus_threshold = math.tan(math.radians(talus_angle))

    offsets = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            dist = math.sqrt(dr * dr + dc * dc)
            offsets.append((dr, dc, dist))

    talus_accumulated = np.zeros_like(result, dtype=np.float64)

    for _iteration in range(iterations):
        delta = np.zeros_like(result)
        padded = np.pad(result, 1, mode="edge")

        accumulated_total_diff = np.zeros_like(result)
        accumulated_max_diff = np.zeros_like(result)
        neighbor_excess: list[tuple[int, int, np.ndarray]] = []

        for dr, dc, dist in offsets:
            shifted = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
            slope = (result - shifted) / (dist * sample_spacing)
            excess = np.maximum(slope - talus_threshold, 0.0)
            accumulated_total_diff += excess
            accumulated_max_diff = np.maximum(accumulated_max_diff, excess)
            neighbor_excess.append((dr, dc, excess))

        has_transfer = accumulated_total_diff > 0
        transfer = accumulated_max_diff * 0.5

        iteration_moved = np.zeros_like(result)

        for dr, dc, excess in neighbor_excess:
            with np.errstate(divide="ignore", invalid="ignore"):
                fraction = np.where(
                    has_transfer, excess / accumulated_total_diff, 0.0
                )
            amount = transfer * fraction * has_transfer

            delta -= amount
            iteration_moved += amount

            r_src_start = max(0, -dr)
            r_src_end = min(rows, rows - dr)
            c_src_start = max(0, -dc)
            c_src_end = min(cols, cols - dc)
            r_dst_start = max(0, dr)
            c_dst_start = max(0, dc)
            r_dst_end = r_dst_start + (r_src_end - r_src_start)
            c_dst_end = c_dst_start + (c_src_end - c_src_start)
            delta[r_dst_start:r_dst_end, c_dst_start:c_dst_end] += amount[
                r_src_start:r_src_end, c_src_start:c_src_end
            ]

        result += delta
        talus_accumulated += iteration_moved

    return ThermalErosionMasks(
        height=result,
        talus=talus_accumulated,
        metrics={
            "iterations": int(iterations),
            "talus_angle": float(talus_angle),
            "cell_size": float(cell_size),
            "total_talus_moved": float(talus_accumulated.sum()),
        },
    )


def apply_thermal_erosion(
    heightmap: np.ndarray,
    iterations: int = 10,
    talus_angle: float = 40.0,
    cell_size: float = 1.0,
) -> np.ndarray:
    """Legacy compat wrapper — returns eroded heightmap only, clamped to source range."""
    h_in = np.asarray(heightmap, dtype=np.float64)
    source_min = float(h_in.min()) if h_in.size else 0.0
    source_max = float(h_in.max()) if h_in.size else 0.0
    masks = apply_thermal_erosion_masks(
        h_in,
        iterations=iterations,
        talus_angle=talus_angle,
        cell_size=cell_size,
    )
    return np.clip(masks.height, source_min, source_max)


__all__ = [
    "ErosionMasks",
    "ThermalErosionMasks",
    "apply_hydraulic_erosion",
    "apply_hydraulic_erosion_masks",
    "apply_thermal_erosion",
    "apply_thermal_erosion_masks",
]
