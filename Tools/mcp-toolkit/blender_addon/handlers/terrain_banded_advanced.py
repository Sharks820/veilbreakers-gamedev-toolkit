"""Bundle G supplements — banded noise advanced techniques (Addendum 1.B.7).

Pure numpy, headless. No bpy. Deterministic given fixed inputs.

Implements:
- compute_anisotropic_breakup — directional-scale noise that breaks up
  obvious Perlin/Voronoi artifacts along a chosen direction
- apply_anti_grain_smoothing — low-frequency Gaussian smoothing to kill
  "pixel grain" artifact from high-octave noise
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np


def compute_anisotropic_breakup(
    base: np.ndarray,
    direction: Tuple[float, float],
    strength: float,
) -> np.ndarray:
    """Directional noise modulation.

    Projects each cell position onto the ``direction`` vector, then
    modulates ``base`` with a sinusoidal + cosine combination sampled at
    that projection. The result is a deterministic directional breakup
    field of the same shape as ``base``.

    Args:
        base: (H, W) float heightmap.
        direction: (dx, dy) — direction of anisotropy. Zero-length allowed,
            returns ``base`` unchanged.
        strength: Magnitude of the breakup modulation in the same units
            as ``base``. Zero returns ``base`` unchanged.

    Returns:
        New (H, W) float array of the same shape and dtype as ``base``.
    """
    if base.ndim != 2:
        raise ValueError(f"base must be 2D, got shape {base.shape}")
    if strength == 0.0:
        return base.copy()

    dx, dy = float(direction[0]), float(direction[1])
    norm = math.sqrt(dx * dx + dy * dy)
    if norm < 1e-12:
        return base.copy()
    dx /= norm
    dy /= norm

    h, w = base.shape
    ys = np.arange(h, dtype=np.float64).reshape(-1, 1)
    xs = np.arange(w, dtype=np.float64).reshape(1, -1)
    # Normalize to unit-ish coords so strength is scale-invariant
    scale = max(h, w)
    proj = (xs * dx + ys * dy) / float(scale)

    # Two-frequency deterministic modulation — not random, fully reproducible
    mod = (
        np.sin(proj * (2.0 * math.pi * 3.0))
        + 0.5 * np.cos(proj * (2.0 * math.pi * 7.0))
    )
    # Scale to [-1, 1]-ish
    mod = mod / 1.5

    return (base + mod * float(strength)).astype(base.dtype, copy=False)


def _gaussian_kernel_1d(sigma: float) -> np.ndarray:
    """Build a 1D Gaussian kernel of radius ~3*sigma, normalized to sum 1."""
    radius = max(1, int(math.ceil(3.0 * sigma)))
    xs = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-(xs * xs) / (2.0 * sigma * sigma))
    s = k.sum()
    if s <= 0:
        return np.array([1.0], dtype=np.float64)
    return k / s


def _convolve_1d_axis(arr: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    """Convolve ``arr`` with ``kernel`` along ``axis`` using edge padding."""
    if kernel.size == 1:
        return arr.copy()
    radius = kernel.size // 2
    pad_width = [(0, 0), (0, 0)]
    pad_width[axis] = (radius, radius)
    padded = np.pad(arr, pad_width, mode="edge")
    out = np.zeros_like(arr, dtype=np.float64)
    for i, w in enumerate(kernel):
        if axis == 0:
            sl = padded[i : i + arr.shape[0], :]
        else:
            sl = padded[:, i : i + arr.shape[1]]
        out = out + w * sl
    return out


def apply_anti_grain_smoothing(
    heightmap: np.ndarray,
    sigma: float = 0.8,
) -> np.ndarray:
    """Low-frequency Gaussian smoothing via separable convolution.

    Uses a manually constructed 1D Gaussian kernel applied along each
    axis. Edge-padded to avoid ring artifacts. No scipy.

    Args:
        heightmap: (H, W) float array.
        sigma: Gaussian standard deviation. Must be > 0.

    Returns:
        Smoothed (H, W) array, same shape, float64 promoted then cast back.
    """
    if heightmap.ndim != 2:
        raise ValueError(f"heightmap must be 2D, got shape {heightmap.shape}")
    if sigma <= 0:
        return heightmap.copy()

    kernel = _gaussian_kernel_1d(float(sigma))
    work = heightmap.astype(np.float64, copy=True)
    work = _convolve_1d_axis(work, kernel, axis=0)
    work = _convolve_1d_axis(work, kernel, axis=1)
    return work.astype(heightmap.dtype, copy=False)
