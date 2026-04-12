"""Analytical erosion filter — pure numpy port of runevision/lpmitchell algorithm.

This module implements the PhacelleNoise + ErosionFilter approach from
``lpmitchell/AdvancedTerrainErosion`` (MIT+MPL-2.0). Every point on the
heightfield is evaluated in isolation from (x, z) plus the base height
function's analytical gradient. No droplet loops, no grid iterations,
no history.

Properties:
  - **Chunk-parallel**: same world coordinates produce identical results
  - **Deterministic**: same seed = bit-identical output
  - **Composable**: applies on top of any base height
  - **Pure numpy**: zero bpy dependency, fully unit-testable

Outputs per point:
  - height_delta: additive height offset from erosion
  - ridge_map: -1 on creases (rivers), +1 on ridges
  - gradient_x, gradient_z: analytical partial derivatives

Public API:
  - apply_analytical_erosion(height_grid, config, seed, ...)
  - finite_difference_gradient(height_grid, cell_size)
  - phacelle_noise(px, pz, slope_x, slope_z, cell_scale, seed)
  - erosion_filter(height_grid, grad_x, grad_z, config, seed, ...)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ._terrain_erosion import AnalyticalErosionResult, ErosionConfig


# ---------------------------------------------------------------------------
# Utility: seed-based hash (deterministic, no global state)
# ---------------------------------------------------------------------------


def _hash2(ix: np.ndarray, iz: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic 2D hash returning two float arrays in [-1, 1].

    Uses the irrational-number hash from the reference C# implementation.
    Vectorized over all grid cells simultaneously.
    """
    # Use large primes + irrationals for mixing (same approach as reference)
    s = np.float64(seed)
    a = ix.astype(np.float64) * 127.1 + iz.astype(np.float64) * 311.7 + s * 53.0
    b = ix.astype(np.float64) * 269.5 + iz.astype(np.float64) * 183.3 + s * 97.0

    # fract(sin(x) * 43758.5453) style hash
    ha = np.sin(a) * 43758.5453123
    hb = np.sin(b) * 43758.5453123
    ha = ha - np.floor(ha)
    hb = hb - np.floor(hb)

    # Map from [0,1] to [-1,1]
    return ha * 2.0 - 1.0, hb * 2.0 - 1.0


def _pow_inv(x: np.ndarray, p: float) -> np.ndarray:
    """PowInv: 1 - (1-x)^(1/(1-p)) for p in [0,1).

    Sharpens the combi-mask so higher detail values let more octave
    detail through. Handles edge cases for p near 1.
    """
    p = np.clip(p, 0.0, 0.999)
    exponent = 1.0 / (1.0 - p + 1e-12)
    return 1.0 - np.power(np.clip(1.0 - x, 0.0, 1.0), exponent)


# ---------------------------------------------------------------------------
# Finite-difference gradient (CONFLICT-003 fallback for imported heightmaps)
# ---------------------------------------------------------------------------


def finite_difference_gradient(
    height_grid: np.ndarray,
    cell_size: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute gradient via central differences, forward/backward at edges.

    Parameters
    ----------
    height_grid : (H, W) float array
    cell_size : world-space distance between cells

    Returns
    -------
    (gradient_x, gradient_z) : tuple of (H, W) arrays
        gradient_x = dh/dx (column direction)
        gradient_z = dh/dz (row direction)
    """
    h = np.asarray(height_grid, dtype=np.float64)
    rows, cols = h.shape
    inv_2dx = 1.0 / (2.0 * cell_size)

    # Central differences for interior
    gx = np.empty_like(h)
    gz = np.empty_like(h)

    # Interior: central differences
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * inv_2dx
    gz[1:-1, :] = (h[2:, :] - h[:-2, :]) * inv_2dx

    # Edges: forward/backward differences
    inv_dx = 1.0 / cell_size
    gx[:, 0] = (h[:, 1] - h[:, 0]) * inv_dx
    gx[:, -1] = (h[:, -1] - h[:, -2]) * inv_dx
    gz[0, :] = (h[1, :] - h[0, :]) * inv_dx
    gz[-1, :] = (h[-1, :] - h[-2, :]) * inv_dx

    return gx, gz


# ---------------------------------------------------------------------------
# PhacelleNoise — vectorized 4x4 cell grid evaluation
# ---------------------------------------------------------------------------


def phacelle_noise(
    px: np.ndarray,
    pz: np.ndarray,
    slope_x: np.ndarray,
    slope_z: np.ndarray,
    cell_scale: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate PhacelleNoise at world positions (px, pz).

    For each query point, examines a 4x4 cell grid. Each cell has a random
    pivot; cosine/sine stripe pairs are oriented along the slope direction
    and blended with bell-curve weights exp(-dist^2 * 2).

    Parameters
    ----------
    px, pz : (H, W) world-space x/z coordinates
    slope_x, slope_z : (H, W) normalized slope direction
    cell_scale : cell size multiplier
    seed : deterministic seed

    Returns
    -------
    (gully_value, d_cos, d_sin) : tuple of (H, W) arrays
        gully_value: combined cosine component (gully depth)
        d_cos: cosine derivative contribution
        d_sin: sine derivative contribution
    """
    shape = px.shape
    inv_cs = 1.0 / max(cell_scale, 1e-12)

    # Scale to cell space
    cx = px * inv_cs
    cz = pz * inv_cs

    # Integer cell of the query point
    ix0 = np.floor(cx).astype(np.int64)
    iz0 = np.floor(cz).astype(np.int64)

    # Fractional position within the cell
    fx = cx - ix0.astype(np.float64)
    fz = cz - iz0.astype(np.float64)

    # Accumulators
    total_cos = np.zeros(shape, dtype=np.float64)
    total_sin = np.zeros(shape, dtype=np.float64)
    total_d_cos = np.zeros(shape, dtype=np.float64)
    total_d_sin = np.zeros(shape, dtype=np.float64)
    total_weight = np.zeros(shape, dtype=np.float64)

    # Iterate over 4x4 cell neighborhood
    for di in range(-1, 3):
        for dj in range(-1, 3):
            # Cell index
            ci = ix0 + di
            cj = iz0 + dj

            # Random pivot within cell via hash
            hx, hz = _hash2(ci, cj, seed)
            # Pivot position in cell space: cell center + random offset * 0.4
            pivot_x = ci.astype(np.float64) + 0.5 + hx * 0.4
            pivot_z = cj.astype(np.float64) + 0.5 + hz * 0.4

            # Vector from pivot to query point
            dx = cx - pivot_x
            dz = cz - pivot_z

            # Distance squared
            dist_sq = dx * dx + dz * dz

            # Bell-curve weight: exp(-dist^2 * 2)
            weight = np.exp(-dist_sq * 2.0)

            # Project displacement onto slope direction
            # dot(displacement, slope_direction)
            proj = dx * slope_x + dz * slope_z

            # Cosine/sine stripe pair
            phase = proj * (2.0 * np.pi)
            cos_val = np.cos(phase)
            sin_val = np.sin(phase)

            # Accumulate with bell-curve weight
            total_cos += cos_val * weight
            total_sin += sin_val * weight
            # Derivatives: d/d(pos) cos(phase) = -sin(phase) * 2π,
            #              d/d(pos) sin(phase) =  cos(phase) * 2π
            total_d_cos += -sin_val * (2.0 * np.pi) * weight
            total_d_sin += cos_val * (2.0 * np.pi) * weight
            total_weight += weight

    # Normalize by total weight
    inv_weight = np.where(total_weight > 1e-12, 1.0 / total_weight, 0.0)
    gully_value = total_cos * inv_weight
    d_cos = total_d_cos * inv_weight
    d_sin = total_d_sin * inv_weight

    return gully_value, d_cos, d_sin


# ---------------------------------------------------------------------------
# ErosionFilter — multi-octave with combi-mask gating
# ---------------------------------------------------------------------------


def erosion_filter(
    height_grid: np.ndarray,
    grad_x: np.ndarray,
    grad_z: np.ndarray,
    config: ErosionConfig,
    seed: int,
    *,
    world_origin_x: float = 0.0,
    world_origin_z: float = 0.0,
    cell_size: float = 1.0,
    height_min: Optional[float] = None,
    height_max: Optional[float] = None,
) -> AnalyticalErosionResult:
    """Apply multi-octave analytical erosion filter.

    Implements the core loop from the reference:
    - For each octave, call PhacelleNoise at increasing frequency
    - Triangle-wave trick: sign(sine) * derivatives for straight gullies
    - Combi-mask gating: each octave's contribution faded by previous ridges
    - Ridge map accumulation via parallel pass without gully-weight

    Parameters
    ----------
    height_grid : (H, W) base heights
    grad_x, grad_z : (H, W) analytical gradient of base heights
    config : ErosionConfig with 12 parameters
    seed : deterministic seed
    world_origin_x, world_origin_z : world-space origin for chunk-parallelism
    cell_size : world-space distance between grid cells

    Returns
    -------
    AnalyticalErosionResult
    """
    h = np.asarray(height_grid, dtype=np.float64)
    rows, cols = h.shape

    # Build world-space coordinate grids
    xs = world_origin_x + np.arange(cols, dtype=np.float64) * cell_size
    zs = world_origin_z + np.arange(rows, dtype=np.float64) * cell_size
    px, pz = np.meshgrid(xs, zs)

    # Working gradient (updated each octave)
    gx = np.array(grad_x, dtype=np.float64)
    gz = np.array(grad_z, dtype=np.float64)

    # Add assumed_slope contribution (enables erosion on flat terrain)
    if config.assumed_slope > 0.0:
        # Hash-based random slope direction per-point for variety
        hx, hz = _hash2(
            np.floor(px).astype(np.int64),
            np.floor(pz).astype(np.int64),
            seed + 9999,
        )
        slope_mag = np.sqrt(gx * gx + gz * gz)
        assumed_mask = slope_mag < config.assumed_slope
        gx = np.where(assumed_mask, gx + hx * config.assumed_slope, gx)
        gz = np.where(assumed_mask, gz + hz * config.assumed_slope, gz)

    # Compute fade target from height range
    # When height_min/height_max are provided (chunk-parallel mode),
    # use them for consistent fade_target across tiles.
    h_min = float(height_min) if height_min is not None else float(h.min())
    h_max = float(height_max) if height_max is not None else float(h.max())
    h_range = max(h_max - h_min, 1e-12)
    fade_target = np.clip((h - h_min) / h_range * config.fade_amplitude, -1.0, 1.0)

    # Initialize accumulators
    height_delta = np.zeros_like(h)
    combi_mask = np.ones_like(h)
    ridge_map = np.zeros_like(h)
    ridge_combi_mask = np.ones_like(h)

    # Slope magnitude for exit-slope gating
    slope_mag = np.sqrt(gx * gx + gz * gz)

    # Exit-slope mask: suppress erosion where slope is below threshold
    exit_mask = np.where(
        slope_mag > config.exit_slope_threshold, 1.0,
        slope_mag / max(config.exit_slope_threshold, 1e-12)
    )

    freq = config.frequency
    for octave in range(config.octave_count):
        octave_seed = seed + octave * 1337

        # Normalize slope direction
        slope_len = np.sqrt(gx * gx + gz * gz)
        with np.errstate(divide="ignore", invalid="ignore"):
            inv_len = np.where(slope_len > 1e-12, 1.0 / slope_len, 0.0)
        slope_dir_x = gx * inv_len
        slope_dir_z = gz * inv_len

        # PhacelleNoise at current frequency
        gully, d_cos, d_sin = phacelle_noise(
            px * freq, pz * freq,
            slope_dir_x, slope_dir_z,
            config.cell_scale,
            octave_seed,
        )

        # Triangle-wave trick: use sign(sine) for straight-slope gullies
        # that branch cleanly
        sign_sin = np.sign(d_sin)
        gx += sign_sin * d_cos * config.strength * config.gully_weight * 0.1
        gz += sign_sin * d_sin * config.strength * config.gully_weight * 0.1

        # Faded gullies: lerp(fade_target, gullies * gully_weight, combi_mask)
        weighted_gully = gully * config.gully_weight
        faded_gullies = fade_target * (1.0 - combi_mask) + weighted_gully * combi_mask

        # Rounding: soften gully bottoms
        if config.rounding > 0.0:
            faded_gullies = faded_gullies * (1.0 - config.rounding) + \
                np.abs(faded_gullies) * config.rounding

        # Apply strength and exit-slope gating
        octave_delta = faded_gullies * config.strength * exit_mask

        # Onset: suppress small values
        if config.onset > 0.0:
            octave_delta = np.where(
                np.abs(octave_delta) > config.onset,
                octave_delta,
                octave_delta * 0.1,
            )

        # Accumulate
        height_delta += octave_delta * config.normalization

        # Update combi-mask: PowInv(combi_mask, detail) * new_mask
        new_mask = np.clip(0.5 + 0.5 * gully, 0.0, 1.0)
        combi_mask = _pow_inv(combi_mask, config.detail) * new_mask

        # Ridge map: parallel pass with no gully-weight for pure ridge detection
        ridge_gully = gully  # unweighted for ridge detection
        ridge_map_fade = ridge_map * (1.0 - ridge_combi_mask) + ridge_gully * ridge_combi_mask
        ridge_map = ridge_map_fade
        ridge_combi_mask = _pow_inv(ridge_combi_mask, config.detail) * new_mask

        # Increase frequency for next octave
        freq *= 2.0

    # Normalize ridge_map to [-1, 1]
    ridge_range = max(float(np.abs(ridge_map).max()), 1e-12)
    ridge_map = np.clip(ridge_map / ridge_range, -1.0, 1.0)

    # Final gradient (updated by octave loop)
    return AnalyticalErosionResult(
        height_delta=height_delta,
        ridge_map=ridge_map,
        gradient_x=gx,
        gradient_z=gz,
        metrics={
            "octave_count": config.octave_count,
            "height_delta_min": float(height_delta.min()),
            "height_delta_max": float(height_delta.max()),
            "height_delta_mean": float(height_delta.mean()),
            "ridge_map_min": float(ridge_map.min()),
            "ridge_map_max": float(ridge_map.max()),
            "seed": seed,
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_analytical_erosion(
    height_grid: np.ndarray,
    config: ErosionConfig,
    seed: int,
    cell_size: float = 1.0,
    *,
    world_origin_x: float = 0.0,
    world_origin_z: float = 0.0,
    grad_x: Optional[np.ndarray] = None,
    grad_z: Optional[np.ndarray] = None,
    height_min: Optional[float] = None,
    height_max: Optional[float] = None,
) -> AnalyticalErosionResult:
    """Apply analytical erosion filter to a heightmap.

    This is the main public API. Computes the gradient via finite differences
    unless pre-computed gradients are supplied (for chunk-parallel evaluation
    where the gradient should come from the full world heightmap).

    Parameters
    ----------
    height_grid : (H, W) base height values
    config : ErosionConfig with 12 fields
    seed : deterministic seed
    cell_size : world-space cell spacing (default 1.0)
    world_origin_x, world_origin_z : world-space origin for chunk-parallelism
    grad_x, grad_z : optional pre-computed gradients (for chunk-parallel mode)
    height_min, height_max : optional global height range (for chunk-parallel mode)

    Returns
    -------
    AnalyticalErosionResult with height_delta, ridge_map, gradient_x, gradient_z
    """
    h = np.asarray(height_grid, dtype=np.float64)

    # Compute gradient via finite differences (fallback for imported heightmaps)
    if grad_x is None or grad_z is None:
        grad_x, grad_z = finite_difference_gradient(h, cell_size)

    return erosion_filter(
        h, grad_x, grad_z,
        config=config,
        seed=seed,
        world_origin_x=world_origin_x,
        world_origin_z=world_origin_z,
        cell_size=cell_size,
        height_min=height_min,
        height_max=height_max,
    )


__all__ = [
    "apply_analytical_erosion",
    "erosion_filter",
    "finite_difference_gradient",
    "phacelle_noise",
]
