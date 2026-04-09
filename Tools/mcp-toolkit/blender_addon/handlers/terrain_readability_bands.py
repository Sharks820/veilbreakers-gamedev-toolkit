"""Bundle N — 5-band readability scoring.

Decomposes terrain visual readability into five orthogonal bands, each
scored 0..10, and aggregates a weighted overall score. Used as a
shippable AAA quality metric and for CI regression tracking.

Bands:
    1. silhouette — horizon profile variance (how "cut out" is the skyline?)
    2. volume     — 3D mass distribution (is there clear large / medium / small?)
    3. value      — light/dark contrast via slope (readable lighting)
    4. texture    — high-frequency detail variance (surface interest)
    5. color      — macro_color variance (palette spread)

Pure numpy — no bpy. See plan §19.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .terrain_semantics import TerrainMaskStack


BAND_IDS: Tuple[str, ...] = ("silhouette", "volume", "value", "texture", "color")

BAND_WEIGHTS: Dict[str, float] = {
    "silhouette": 0.25,
    "volume": 0.25,
    "value": 0.20,
    "texture": 0.15,
    "color": 0.15,
}


@dataclass
class BandScore:
    """One readability band result."""

    band_id: str
    name: str
    score: float  # 0..10
    details: Dict[str, Any] = field(default_factory=dict)

    def clamp(self) -> "BandScore":
        self.score = float(np.clip(self.score, 0.0, 10.0))
        return self


def _safe_std(arr: Optional[np.ndarray]) -> float:
    if arr is None:
        return 0.0
    a = np.asarray(arr, dtype=np.float64)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return 0.0
    return float(np.std(finite))


def _normalize_to_score(value: float, lo: float, hi: float) -> float:
    """Map ``value`` from [lo, hi] → [0, 10] and clamp."""
    if hi <= lo:
        return 0.0
    t = (value - lo) / (hi - lo)
    return float(np.clip(t * 10.0, 0.0, 10.0))


def _band_silhouette(stack: TerrainMaskStack) -> BandScore:
    h = np.asarray(stack.height, dtype=np.float64)
    if h.ndim != 2 or h.size == 0:
        return BandScore("silhouette", "silhouette", 0.0).clamp()
    # horizon = column-wise max (per-column skyline looking along +y)
    horizon_top = h.max(axis=0)
    horizon_right = h.max(axis=1)
    # Variance across both horizon profiles
    var = 0.5 * (float(np.var(horizon_top)) + float(np.var(horizon_right)))
    rng = float(h.max() - h.min()) or 1.0
    normalized = var / (rng * rng)  # unitless 0..~1
    score = _normalize_to_score(normalized, 0.0, 0.08)
    return BandScore(
        "silhouette",
        "silhouette",
        score,
        details={"horizon_var": var, "height_range": rng},
    ).clamp()


def _band_volume(stack: TerrainMaskStack) -> BandScore:
    h = np.asarray(stack.height, dtype=np.float64)
    if h.size == 0:
        return BandScore("volume", "volume", 0.0).clamp()
    # 3-bin "large/medium/small mass" histogram
    finite = h[np.isfinite(h)]
    if finite.size < 4:
        return BandScore("volume", "volume", 0.0).clamp()
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return BandScore("volume", "volume", 0.0).clamp()
    bins = np.linspace(lo, hi, 4)
    counts, _ = np.histogram(finite, bins=bins)
    fractions = counts.astype(np.float64) / float(finite.size)
    # Good distribution ~= entropy of the 3-bin histogram, max ≈ log(3)
    eps = 1e-12
    entropy = -float(np.sum(fractions * np.log(fractions + eps)))
    max_entropy = float(np.log(3.0))
    score = _normalize_to_score(entropy, 0.0, max_entropy)
    return BandScore(
        "volume",
        "volume",
        score,
        details={"fractions": fractions.tolist(), "entropy": entropy},
    ).clamp()


def _band_value(stack: TerrainMaskStack) -> BandScore:
    slope = stack.get("slope")
    if slope is None:
        # Fallback: compute a finite-difference slope from height
        h = np.asarray(stack.height, dtype=np.float64)
        if h.size == 0 or h.ndim != 2:
            return BandScore("value", "value", 0.0).clamp()
        gy, gx = np.gradient(h)
        slope = np.sqrt(gx * gx + gy * gy)
    s = np.asarray(slope, dtype=np.float64)
    finite = s[np.isfinite(s)]
    if finite.size == 0:
        return BandScore("value", "value", 0.0).clamp()
    std = float(np.std(finite))
    mean = float(np.mean(finite))
    # Contrast = std/mean ratio (coefficient of variation), capped
    denom = max(mean, 1e-6)
    contrast = std / denom
    score = _normalize_to_score(contrast, 0.1, 1.5)
    return BandScore(
        "value",
        "value",
        score,
        details={"slope_std": std, "slope_mean": mean, "contrast_cv": contrast},
    ).clamp()


def _band_texture(stack: TerrainMaskStack) -> BandScore:
    h = np.asarray(stack.height, dtype=np.float64)
    if h.ndim != 2 or h.shape[0] < 3 or h.shape[1] < 3:
        return BandScore("texture", "texture", 0.0).clamp()
    # High-frequency detail = local detail - smoothed local detail.
    # Approximate a blur via a 3x3 mean kernel via array slicing.
    kernel_sum = np.zeros_like(h)
    count = np.zeros_like(h)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            shifted = np.roll(np.roll(h, dr, axis=0), dc, axis=1)
            kernel_sum += shifted
            count += 1.0
    blurred = kernel_sum / count
    high_freq = h - blurred
    std = float(np.std(high_freq))
    # Target range: a "barely any detail" terrain has std ~ 0; rich has > 0.5m
    rng = float(h.max() - h.min()) or 1.0
    normalized = std / rng
    score = _normalize_to_score(normalized, 0.0, 0.05)
    return BandScore(
        "texture",
        "texture",
        score,
        details={"high_freq_std": std, "height_range": rng},
    ).clamp()


def _band_color(stack: TerrainMaskStack) -> BandScore:
    macro = stack.get("macro_color")
    if macro is None:
        return BandScore(
            "color",
            "color",
            0.0,
            details={"reason": "macro_color not populated"},
        ).clamp()
    arr = np.asarray(macro, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return BandScore("color", "color", 0.0).clamp()
    # Multi-channel: sum per-channel std
    if arr.ndim == 3:
        per_channel = [float(np.std(arr[..., c])) for c in range(arr.shape[-1])]
        total_var = float(np.mean(per_channel))
    else:
        total_var = float(np.std(finite))
    score = _normalize_to_score(total_var, 0.0, 0.25)
    return BandScore(
        "color",
        "color",
        score,
        details={"color_variance": total_var},
    ).clamp()


def compute_readability_bands(stack: TerrainMaskStack) -> List[BandScore]:
    """Compute all 5 readability bands for a mask stack."""
    return [
        _band_silhouette(stack),
        _band_volume(stack),
        _band_value(stack),
        _band_texture(stack),
        _band_color(stack),
    ]


def aggregate_readability_score(bands: List[BandScore]) -> float:
    """Weighted overall readability score (0..10)."""
    if not bands:
        return 0.0
    total = 0.0
    weight_sum = 0.0
    for band in bands:
        w = BAND_WEIGHTS.get(band.band_id, 0.0)
        total += band.score * w
        weight_sum += w
    if weight_sum <= 0.0:
        return 0.0
    return float(np.clip(total / weight_sum, 0.0, 10.0))


__all__ = [
    "BAND_IDS",
    "BAND_WEIGHTS",
    "BandScore",
    "compute_readability_bands",
    "aggregate_readability_score",
]
