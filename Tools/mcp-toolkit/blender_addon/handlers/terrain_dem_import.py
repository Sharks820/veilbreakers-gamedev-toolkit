"""Bundle P — DEM (Digital Elevation Model) import.

Pure numpy. Loads a real DEM tile from a ``.npy`` file if present,
otherwise generates a deterministic synthetic DEM from the BBox coords
so tests remain reproducible without any real-world data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np

from .terrain_semantics import BBox


@dataclass
class DEMSource:
    """DEM provenance record.

    ``source_type`` is a free-form label (``"srtm"``, ``"usgs_3dep"``,
    ``"synthetic"``, ...). ``url_or_path`` may point to a local ``.npy``
    file on disk; if it exists it is loaded verbatim, otherwise a
    deterministic synthetic tile is returned.
    """

    source_type: str
    url_or_path: str
    resolution_m: float


def _synthetic_dem(world_bounds: BBox, shape: Tuple[int, int] = (64, 64)) -> np.ndarray:
    """Generate a deterministic DEM from BBox coordinates.

    Uses SHA-256 of the bounds as an RNG seed so repeated calls with the
    same BBox produce byte-identical output across processes.
    """
    key = f"{world_bounds.min_x}:{world_bounds.min_y}:{world_bounds.max_x}:{world_bounds.max_y}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:4], "big") & 0xFFFFFFFF
    rng = np.random.default_rng(seed)

    h, w = shape
    ys = np.linspace(0.0, 1.0, h).reshape(-1, 1)
    xs = np.linspace(0.0, 1.0, w).reshape(1, -1)

    # Smooth base gradient + low-frequency noise, all deterministic
    base = 100.0 + 50.0 * (xs + ys) + 20.0 * np.sin(xs * 6.28) * np.cos(ys * 6.28)
    noise = rng.standard_normal((h, w)) * 5.0
    return (base + noise).astype(np.float32)


def import_dem_tile(source: DEMSource, world_bounds: BBox) -> np.ndarray:
    """Load a DEM tile for the given world bounds.

    If ``source.url_or_path`` is an existing ``.npy`` file on disk, it is
    loaded. Otherwise a deterministic synthetic DEM is returned.
    """
    path = Path(source.url_or_path)
    if path.exists() and path.suffix == ".npy":
        arr = np.load(str(path))
        if arr.ndim != 2:
            raise ValueError(f"DEM {path} must be 2D, got shape {arr.shape}")
        return arr.astype(np.float32)
    return _synthetic_dem(world_bounds)


def resample_dem_to_tile_grid(
    dem: np.ndarray,
    target_tile_size: int,
    target_cell_size: float,
) -> np.ndarray:
    """Bilinear resample a DEM to ``(target_tile_size, target_tile_size)``.

    Numpy-only. ``target_cell_size`` is accepted for API symmetry but
    only the target shape matters for the resample — the caller is
    responsible for downstream world-unit consistency.
    """
    if dem.ndim != 2:
        raise ValueError(f"dem must be 2D, got shape {dem.shape}")
    if target_tile_size <= 0:
        raise ValueError("target_tile_size must be positive")
    _ = target_cell_size  # reserved for future use

    src_h, src_w = dem.shape
    dst = int(target_tile_size)

    ys = np.linspace(0.0, src_h - 1, dst)
    xs = np.linspace(0.0, src_w - 1, dst)

    y0 = np.floor(ys).astype(np.int64)
    x0 = np.floor(xs).astype(np.int64)
    y1 = np.clip(y0 + 1, 0, src_h - 1)
    x1 = np.clip(x0 + 1, 0, src_w - 1)
    fy = (ys - y0).reshape(-1, 1)
    fx = (xs - x0).reshape(1, -1)

    tl = dem[np.ix_(y0, x0)]
    tr = dem[np.ix_(y0, x1)]
    bl = dem[np.ix_(y1, x0)]
    br = dem[np.ix_(y1, x1)]

    top = tl * (1.0 - fx) + tr * fx
    bot = bl * (1.0 - fx) + br * fx
    out = top * (1.0 - fy) + bot * fy
    return out.astype(np.float32)


def normalize_dem_to_world_range(
    dem: np.ndarray,
    target_min_m: float,
    target_max_m: float,
) -> np.ndarray:
    """Linearly remap DEM to ``[target_min_m, target_max_m]``."""
    if target_max_m < target_min_m:
        raise ValueError("target_max_m must be >= target_min_m")
    lo = float(np.min(dem))
    hi = float(np.max(dem))
    if hi - lo < 1e-12:
        return np.full_like(dem, (target_min_m + target_max_m) * 0.5, dtype=np.float32)
    scale = (target_max_m - target_min_m) / (hi - lo)
    return ((dem - lo) * scale + target_min_m).astype(np.float32)
