"""Bundle P — Palette extraction from reference imagery.

Pure numpy k-means on RGB pixels. No sklearn. Deterministic given a
seeded RNG (default seed=0).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass(frozen=True)
class PaletteEntry:
    """A single palette entry extracted from an image.

    ``color_rgb`` is in [0, 1] float. ``weight`` is the fraction of
    image pixels assigned to this cluster. ``label`` is a human-readable
    tag ("dark", "earth", "foliage", ...).
    """

    color_rgb: Tuple[float, float, float]
    weight: float
    label: str


def _labels_for(image: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    # image: (N, 3), centroids: (k, 3) -> (N,) int labels
    # ||p - c||^2 = |p|^2 - 2 p.c + |c|^2
    d = (
        (image ** 2).sum(axis=1, keepdims=True)
        - 2.0 * image @ centroids.T
        + (centroids ** 2).sum(axis=1, keepdims=True).T
    )
    return np.argmin(d, axis=1)


def extract_palette_from_image(
    image_array: np.ndarray,
    k: int = 8,
) -> List[PaletteEntry]:
    """Run deterministic numpy k-means on RGB pixels and return palette.

    Args:
        image_array: ``(H, W, 3)`` or ``(N, 3)`` float [0,1] or uint8.
        k: Number of clusters (default 8).
    """
    if k <= 0:
        raise ValueError("k must be positive")

    arr = np.asarray(image_array)
    if arr.ndim == 3:
        arr = arr.reshape(-1, arr.shape[-1])
    if arr.shape[-1] == 4:
        arr = arr[:, :3]
    if arr.shape[-1] != 3:
        raise ValueError(f"expected RGB image, got last-dim {arr.shape[-1]}")

    pixels = arr.astype(np.float64, copy=False)
    if pixels.max() > 1.5:
        pixels = pixels / 255.0

    n = pixels.shape[0]
    if n == 0:
        return []

    k = min(k, n)
    rng = np.random.default_rng(0)
    init_idx = rng.choice(n, size=k, replace=False)
    centroids = pixels[init_idx].copy()

    for _ in range(20):
        labels = _labels_for(pixels, centroids)
        new_centroids = np.zeros_like(centroids)
        for ci in range(k):
            mask = labels == ci
            if mask.any():
                new_centroids[ci] = pixels[mask].mean(axis=0)
            else:
                new_centroids[ci] = centroids[ci]
        if np.allclose(new_centroids, centroids, atol=1e-5):
            centroids = new_centroids
            break
        centroids = new_centroids

    labels = _labels_for(pixels, centroids)
    entries: List[PaletteEntry] = []
    for ci in range(k):
        weight = float((labels == ci).mean())
        r, g, b = centroids[ci]
        entries.append(
            PaletteEntry(
                color_rgb=(float(r), float(g), float(b)),
                weight=weight,
                label=_label_for_rgb(float(r), float(g), float(b)),
            )
        )
    entries.sort(key=lambda e: e.weight, reverse=True)
    return entries


def _label_for_rgb(r: float, g: float, b: float) -> str:
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum < 0.15:
        return "dark"
    if lum > 0.85:
        return "light"
    if g > r and g > b:
        return "foliage"
    if r > g and r > b:
        return "earth"
    if b > r and b > g:
        return "water"
    return "neutral"


def palette_to_biome_mapping(palette: List[PaletteEntry]) -> Dict[str, str]:
    """Map palette labels to biome names.

    Simple rule table: dark->shadow, earth->cliff, foliage->forest,
    water->wetland, light->alpine, neutral->plateau.
    """
    mapping: Dict[str, str] = {}
    rules = {
        "dark": "shadow",
        "earth": "cliff",
        "foliage": "forest",
        "water": "wetland",
        "light": "alpine",
        "neutral": "plateau",
    }
    for entry in palette:
        mapping[entry.label] = rules.get(entry.label, "plateau")
    return mapping
