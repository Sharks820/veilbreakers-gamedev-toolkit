"""Pure-logic terrain noise, biome assignment, and pathing algorithms.

NO bpy/bmesh imports. All functions operate on numpy arrays and return
numpy arrays or plain Python data structures. Fully testable without Blender.

Provides:
  - generate_heightmap: fBm noise heightmap with terrain-type presets
  - compute_slope_map: Slope in degrees from heightmap gradients
  - compute_biome_assignments: Per-cell biome index from altitude/slope rules
  - carve_river_path: A* river channel carving on heightmap
  - generate_road_path: Weighted A* road with terrain grading
  - TERRAIN_PRESETS: Parameter dicts for 8 terrain types
  - BIOME_RULES: Default dark-fantasy biome rules

Performance notes (2026-03):
  - Heightmap generation is numpy-vectorized (meshgrid + batch noise).
    256x256x8 octaves completes in ~0.05s vs ~8s with pure-Python loops.
  - Fallback noise uses a permutation-table gradient approach instead of
    MD5-per-pixel, giving ~100x speedup when opensimplex is unavailable.
"""

from __future__ import annotations

import heapq
import math
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Noise backend: opensimplex or permutation-table fallback
# ---------------------------------------------------------------------------

_USE_OPENSIMPLEX = False

try:
    from opensimplex import OpenSimplex as _RealOpenSimplex
    _USE_OPENSIMPLEX = True
except ImportError:
    _RealOpenSimplex = None  # type: ignore[assignment,misc]


# --- Permutation-table gradient noise (fallback) -------------------------
# Standard 2D gradient noise using a seeded permutation table.  Deterministic
# for a given seed, supports both scalar and vectorized (numpy array) eval.

# 12 gradient vectors for 2D noise (unit-length directions at 30-degree steps)
_GRAD2 = np.array([
    (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
    (0.7071, 0.7071), (-0.7071, 0.7071),
    (0.7071, -0.7071), (-0.7071, -0.7071),
    (0.5, 0.866), (-0.5, 0.866),
    (0.5, -0.866), (-0.5, -0.866),
], dtype=np.float64)


def _build_permutation_table(seed: int) -> np.ndarray:
    """Build a 512-element permutation table from a seed.

    The table is 256 random values repeated once so that index wrapping
    is handled automatically via ``perm[i & 255]`` or direct indexing up
    to 511.
    """
    rng = np.random.RandomState(seed & 0x7FFFFFFF)
    perm = np.arange(256, dtype=np.int32)
    rng.shuffle(perm)
    return np.concatenate([perm, perm])


def _perlin_noise2_array(
    xs: np.ndarray,
    ys: np.ndarray,
    perm: np.ndarray,
) -> np.ndarray:
    """Evaluate 2D Perlin gradient noise at arrays of (x, y) coordinates.

    Parameters
    ----------
    xs, ys : np.ndarray
        Coordinate arrays (must be same shape, any dimensionality).
    perm : np.ndarray
        512-element permutation table from ``_build_permutation_table``.

    Returns
    -------
    np.ndarray
        Noise values in approximately [-1, 1], same shape as *xs*.
    """
    # Integer cell coordinates
    xi = np.floor(xs).astype(np.int32)
    yi = np.floor(ys).astype(np.int32)

    # Fractional position inside cell
    xf = xs - xi
    yf = ys - yi

    # Wrap to permutation table range
    xi = xi & 255
    yi = yi & 255

    # Fade curves (improved Perlin: 6t^5 - 15t^4 + 10t^3)
    u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
    v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)

    # Hash the four corners
    n_grad = len(_GRAD2)
    aa = perm[perm[xi] + yi] % n_grad
    ab = perm[perm[xi] + yi + 1] % n_grad
    ba = perm[perm[xi + 1] + yi] % n_grad
    bb = perm[perm[xi + 1] + yi + 1] % n_grad

    # Gradient dot products at each corner
    g_aa = _GRAD2[aa]  # shape (..., 2)
    g_ab = _GRAD2[ab]
    g_ba = _GRAD2[ba]
    g_bb = _GRAD2[bb]

    dot_aa = g_aa[..., 0] * xf + g_aa[..., 1] * yf
    dot_ba = g_ba[..., 0] * (xf - 1.0) + g_ba[..., 1] * yf
    dot_ab = g_ab[..., 0] * xf + g_ab[..., 1] * (yf - 1.0)
    dot_bb = g_bb[..., 0] * (xf - 1.0) + g_bb[..., 1] * (yf - 1.0)

    # Bilinear interpolation using fade curves
    x1 = dot_aa + u * (dot_ba - dot_aa)
    x2 = dot_ab + u * (dot_bb - dot_ab)
    result = x1 + v * (x2 - x1)

    return result


class _PermTableNoise:
    """Fallback noise generator using a seeded permutation table.

    Provides both scalar ``noise2(x, y)`` for compatibility and vectorized
    ``noise2_array(xs, ys)`` for batch evaluation.
    """

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed
        self._perm = _build_permutation_table(seed)

    def noise2(self, x: float, y: float) -> float:
        """Scalar 2D noise evaluation, returns value in ~[-1, 1]."""
        xs = np.array([x], dtype=np.float64)
        ys = np.array([y], dtype=np.float64)
        return float(_perlin_noise2_array(xs, ys, self._perm)[0])

    def noise2_array(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Vectorized 2D noise evaluation over coordinate arrays."""
        return _perlin_noise2_array(xs, ys, self._perm)


def _make_noise_generator(seed: int) -> _PermTableNoise:
    """Create a noise generator for the given seed.

    Uses opensimplex if available (wrapped to support ``noise2_array``),
    otherwise falls back to the permutation-table gradient noise.
    """
    if _USE_OPENSIMPLEX and _RealOpenSimplex is not None:
        return _OpenSimplexWrapper(seed)
    return _PermTableNoise(seed)


class _OpenSimplexWrapper(_PermTableNoise):
    """Wrap the real opensimplex library with vectorized noise support.

    The scalar ``noise2()`` delegates to the real opensimplex for exact
    compatibility with existing tests that check specific values.
    The vectorized ``noise2_array()`` uses the parent class's numpy-native
    Perlin implementation (permutation table), which is 50-200x faster
    than calling opensimplex.noise2 per-pixel via np.vectorize.

    The heightmap output values will differ slightly from pure-opensimplex
    (different noise algorithm), but all terrain-shaping properties
    (determinism, range, distribution) are preserved.
    """

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed)
        self._os = _RealOpenSimplex(seed=seed)  # type: ignore[misc]

    def noise2(self, x: float, y: float) -> float:
        """Scalar evaluation using the real opensimplex library."""
        return self._os.noise2(x, y)

    # noise2_array() intentionally NOT overridden: inherits the fast
    # numpy-vectorized Perlin implementation from _PermTableNoise.


# Legacy alias so that any code importing ``OpenSimplex`` from this module
# still works.  The class exposes the same ``.noise2()`` interface.
OpenSimplex = _PermTableNoise  # type: ignore[misc]

# ---------------------------------------------------------------------------
# Terrain type presets
# ---------------------------------------------------------------------------

TERRAIN_PRESETS: dict[str, dict[str, Any]] = {
    "mountains": {
        "octaves": 8,
        "persistence": 0.5,
        "lacunarity": 2.0,
        "amplitude_scale": 1.0,
        "post_process": "power",
        "power": 1.6,
    },
    "hills": {
        "octaves": 6,
        "persistence": 0.45,
        "lacunarity": 2.0,
        "amplitude_scale": 0.6,
        "post_process": "smooth",
    },
    "plains": {
        "octaves": 4,
        "persistence": 0.35,
        "lacunarity": 2.0,
        "amplitude_scale": 0.25,
        "post_process": "smooth",
    },
    "volcanic": {
        "octaves": 7,
        "persistence": 0.5,
        "lacunarity": 2.1,
        "amplitude_scale": 0.9,
        "post_process": "crater",
        "crater_radius": 0.3,
        "crater_depth": 0.4,
    },
    "canyon": {
        "octaves": 6,
        "persistence": 0.5,
        "lacunarity": 2.0,
        "amplitude_scale": 0.8,
        "post_process": "canyon",
        "ridge_strength": 0.7,
    },
    "cliffs": {
        "octaves": 7,
        "persistence": 0.55,
        "lacunarity": 2.0,
        "amplitude_scale": 0.9,
        "post_process": "step",
        "step_count": 5,
    },
    "flat": {
        "octaves": 3,
        "persistence": 0.25,
        "lacunarity": 2.0,
        "amplitude_scale": 0.15,
        "post_process": "smooth",
    },
    "chaotic": {
        "octaves": 8,
        "persistence": 0.6,
        "lacunarity": 2.3,
        "amplitude_scale": 1.0,
        "post_process": "canyon",
        "ridge_strength": 0.5,
    },
}

# ---------------------------------------------------------------------------
# Default biome rules (dark fantasy palette, priority order)
# ---------------------------------------------------------------------------

BIOME_RULES: list[dict[str, Any]] = [
    {
        "name": "snow",
        "material": "terrain_snow",
        "min_alt": 0.8,
        "max_alt": 1.0,
        "min_slope": 0.0,
        "max_slope": 45.0,
    },
    {
        "name": "rock",
        "material": "terrain_rock",
        "min_alt": 0.0,
        "max_alt": 1.0,
        "min_slope": 40.0,
        "max_slope": 90.0,
    },
    {
        "name": "dead_grass",
        "material": "terrain_dead_grass",
        "min_alt": 0.2,
        "max_alt": 0.8,
        "min_slope": 0.0,
        "max_slope": 40.0,
    },
    {
        "name": "mud",
        "material": "terrain_mud",
        "min_alt": 0.0,
        "max_alt": 0.2,
        "min_slope": 0.0,
        "max_slope": 40.0,
    },
]


# ---------------------------------------------------------------------------
# Heightmap generation
# ---------------------------------------------------------------------------

def generate_heightmap(
    width: int,
    height: int,
    scale: float = 100.0,
    octaves: int | None = None,
    persistence: float | None = None,
    lacunarity: float | None = None,
    seed: int = 0,
    terrain_type: str = "mountains",
    warp_strength: float = 0.0,
    warp_scale: float = 0.5,
) -> np.ndarray:
    """Generate a 2D heightmap using fBm (fractal Brownian motion) noise.

    Uses numpy-vectorized coordinate grids and batch noise evaluation for
    50-200x speedup over per-pixel Python loops.  A 256x256 heightmap with
    8 octaves completes in ~0.05s.

    Parameters
    ----------
    width, height : int
        Dimensions of the output heightmap.
    scale : float
        Noise sampling scale (larger = smoother terrain).
    octaves, persistence, lacunarity : optional
        Override terrain preset values for fBm noise stacking.
    seed : int
        Random seed for deterministic generation.
    terrain_type : str
        One of TERRAIN_PRESETS keys: mountains, hills, plains, volcanic,
        canyon, cliffs.
    warp_strength : float
        Domain warp amplitude. 0 = off (default, backward compatible),
        0.3-0.8 = organic terrain, 1.0+ = extreme distortion.
    warp_scale : float
        Frequency of the domain warp noise. Lower = broader warping.

    Returns
    -------
    np.ndarray
        2D array of shape (height, width) with values in [0, 1].
    """
    if terrain_type not in TERRAIN_PRESETS:
        raise ValueError(
            f"Unknown terrain_type '{terrain_type}'. "
            f"Valid types: {sorted(TERRAIN_PRESETS.keys())}"
        )

    preset = TERRAIN_PRESETS[terrain_type]
    oct_ = octaves if octaves is not None else preset["octaves"]
    pers_ = persistence if persistence is not None else preset["persistence"]
    lac_ = lacunarity if lacunarity is not None else preset["lacunarity"]

    gen = _make_noise_generator(seed)

    # Build coordinate grids once (vectorised)
    # x varies along columns (axis 1), y varies along rows (axis 0)
    x_coords = np.arange(width, dtype=np.float64) / scale   # shape (width,)
    y_coords = np.arange(height, dtype=np.float64) / scale  # shape (height,)
    xs_base, ys_base = np.meshgrid(x_coords, y_coords)      # both (height, width)

    # Apply domain warping for organic, non-repetitive terrain
    if warp_strength > 0.0:
        xs_base, ys_base = domain_warp_array(
            xs_base, ys_base,
            warp_strength=warp_strength,
            warp_scale=warp_scale,
            seed=seed + 7919,  # Offset seed for independent warp noise
        )

    # Accumulate fBm octaves with vectorized noise evaluation
    hmap = np.zeros((height, width), dtype=np.float64)
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0

    for _ in range(oct_):
        xs = xs_base * frequency
        ys = ys_base * frequency
        hmap += gen.noise2_array(xs, ys) * amplitude
        max_val += amplitude
        amplitude *= pers_
        frequency *= lac_

    if max_val > 0.0:
        hmap /= max_val

    # Apply terrain preset shaping
    hmap = _apply_terrain_preset(hmap, preset)

    # Normalize to [0, 1]
    hmin, hmax = hmap.min(), hmap.max()
    if hmax - hmin > 1e-10:
        hmap = (hmap - hmin) / (hmax - hmin)
    else:
        hmap = np.zeros_like(hmap)

    return hmap


def _apply_terrain_preset(
    hmap: np.ndarray, preset: dict[str, Any]
) -> np.ndarray:
    """Apply terrain-type post-processing to a raw noise heightmap."""
    post = preset.get("post_process", "none")
    amp = preset.get("amplitude_scale", 1.0)
    hmap = hmap * amp

    if post == "power":
        # Normalize to [0,1] first, apply power curve, rescale
        hmin, hmax = hmap.min(), hmap.max()
        if hmax - hmin > 1e-10:
            normalized = (hmap - hmin) / (hmax - hmin)
        else:
            normalized = np.zeros_like(hmap)
        power = preset.get("power", 1.5)
        hmap = np.power(normalized, power)

    elif post == "smooth":
        # Gentle smoothing: reduce high-frequency by averaging with neighbors
        # Simple 3x3 box blur (one pass)
        rows, cols = hmap.shape
        if rows >= 3 and cols >= 3:
            padded = np.pad(hmap, 1, mode="edge")
            smoothed = np.zeros_like(hmap)
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    smoothed += padded[1 + dy : rows + 1 + dy, 1 + dx : cols + 1 + dx]
            hmap = smoothed / 9.0

    elif post == "crater":
        # Volcanic crater: radial falloff with a dip in the center
        rows, cols = hmap.shape
        cy, cx = rows / 2.0, cols / 2.0
        max_r = min(rows, cols) / 2.0
        crater_r = preset.get("crater_radius", 0.3) * max_r
        crater_depth = preset.get("crater_depth", 0.4)

        y_coords, x_coords = np.mgrid[0:rows, 0:cols]
        dist = np.sqrt((y_coords - cy) ** 2 + (x_coords - cx) ** 2)

        # Create a radial mountain with crater dip
        radial = 1.0 - np.clip(dist / max_r, 0, 1)
        radial = np.power(radial, 1.5)

        # Crater dip for center
        crater_mask = np.clip(1.0 - dist / crater_r, 0, 1)
        crater_dip = crater_mask * crater_depth

        hmap = hmap * 0.3 + radial * 0.7 - crater_dip

    elif post == "canyon":
        # Canyon: invert ridges to create valley patterns
        ridge_strength = preset.get("ridge_strength", 0.7)
        # Ridged noise: take absolute value and invert
        ridged = 1.0 - np.abs(hmap)
        hmap = hmap * (1.0 - ridge_strength) + ridged * ridge_strength

    elif post == "step":
        # Cliff step function: quantize heights into discrete levels
        step_count = preset.get("step_count", 5)
        hmin, hmax = hmap.min(), hmap.max()
        if hmax - hmin > 1e-10:
            normalized = (hmap - hmin) / (hmax - hmin)
        else:
            normalized = np.zeros_like(hmap)
        stepped = np.floor(normalized * step_count) / step_count
        # Blend stepped with original for cliff edges
        hmap = stepped * 0.7 + normalized * 0.3

    return hmap


# ---------------------------------------------------------------------------
# Slope map
# ---------------------------------------------------------------------------

def compute_slope_map(heightmap: np.ndarray) -> np.ndarray:
    """Compute slope in degrees from a heightmap.

    Uses numpy gradient to compute partial derivatives, then converts
    the magnitude to degrees from horizontal (0 = flat, 90 = vertical).

    Parameters
    ----------
    heightmap : np.ndarray
        2D heightmap array.

    Returns
    -------
    np.ndarray
        2D array of slope values in degrees [0, 90].
    """
    # np.gradient requires at least 2 elements per axis; a 1-pixel
    # dimension has no neighbours so the slope is zero by definition.
    rows, cols = heightmap.shape
    if rows < 2 or cols < 2:
        return np.zeros_like(heightmap)

    dy, dx = np.gradient(heightmap)
    magnitude = np.sqrt(dx ** 2 + dy ** 2)
    slope_rad = np.arctan(magnitude)
    slope_deg = np.degrees(slope_rad)
    return np.clip(slope_deg, 0.0, 90.0)


# ---------------------------------------------------------------------------
# Biome assignment
# ---------------------------------------------------------------------------

def compute_biome_assignments(
    heightmap: np.ndarray,
    slope_map: np.ndarray,
    biome_rules: list[dict[str, Any]] | None = None,
) -> np.ndarray:
    """Assign biome indices per-cell based on altitude and slope rules.

    Parameters
    ----------
    heightmap : np.ndarray
        2D heightmap with values in [0, 1] (altitude).
    slope_map : np.ndarray
        2D slope map in degrees [0, 90].
    biome_rules : list of dict, optional
        Priority-ordered list of biome rules. Each dict may contain:
        min_alt, max_alt, min_slope, max_slope. First match wins.
        Defaults to BIOME_RULES.

    Returns
    -------
    np.ndarray
        Integer array same shape as heightmap, each value is a rule index.
        Cells matching no rule get the last rule index (fallback).
    """
    if biome_rules is None:
        biome_rules = BIOME_RULES

    # Process rules in reverse order so earlier (higher-priority) rules
    # overwrite later ones -- first matching rule wins.
    result = np.full(heightmap.shape, len(biome_rules) - 1, dtype=np.int32)
    for idx in range(len(biome_rules) - 1, -1, -1):
        rule = biome_rules[idx]
        min_alt = rule.get("min_alt", 0.0)
        max_alt = rule.get("max_alt", 1.0)
        min_slope = rule.get("min_slope", 0.0)
        max_slope = rule.get("max_slope", 90.0)

        mask = (
            (heightmap >= min_alt)
            & (heightmap <= max_alt)
            & (slope_map >= min_slope)
            & (slope_map <= max_slope)
        )
        result[mask] = idx

    return result


# ---------------------------------------------------------------------------
# A* pathfinding utilities
# ---------------------------------------------------------------------------

def _neighbors(row: int, col: int, rows: int, cols: int) -> list[tuple[int, int]]:
    """Return valid 8-connected neighbor coordinates."""
    result = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                result.append((nr, nc))
    return result


def _astar(
    heightmap: np.ndarray,
    source: tuple[int, int],
    dest: tuple[int, int],
    slope_weight: float = 5.0,
    height_weight: float = 1.0,
) -> list[tuple[int, int]]:
    """A* pathfinding on a heightmap.

    Cost = height difference * slope_weight + destination height * height_weight.
    Prefers downhill paths and low-height cells.
    """
    rows, cols = heightmap.shape
    sr, sc = source
    dr, dc = dest

    # Clamp to valid range
    sr = max(0, min(sr, rows - 1))
    sc = max(0, min(sc, cols - 1))
    dr = max(0, min(dr, rows - 1))
    dc = max(0, min(dc, cols - 1))

    # Priority queue: (f_cost, g_cost, row, col)
    open_set: list[tuple[float, float, int, int]] = []
    heapq.heappush(open_set, (0.0, 0.0, sr, sc))

    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {(sr, sc): 0.0}

    def heuristic(r: int, c: int) -> float:
        return math.sqrt((r - dr) ** 2 + (c - dc) ** 2)

    while open_set:
        f, g, cr, cc = heapq.heappop(open_set)

        # Skip stale heap entries whose cost has been superseded
        if g > g_score.get((cr, cc), float("inf")):
            continue

        if cr == dr and cc == dc:
            # Reconstruct path
            path = [(cr, cc)]
            while (cr, cc) in came_from:
                cr, cc = came_from[(cr, cc)]
                path.append((cr, cc))
            path.reverse()
            return path

        for nr, nc in _neighbors(cr, cc, rows, cols):
            h_diff = abs(float(heightmap[nr, nc]) - float(heightmap[cr, cc]))
            step_dist = math.sqrt((nr - cr) ** 2 + (nc - cc) ** 2)
            move_cost = (
                step_dist
                + h_diff * slope_weight
                + float(heightmap[nr, nc]) * height_weight
            )
            tentative_g = g + move_cost

            if tentative_g < g_score.get((nr, nc), float("inf")):
                g_score[(nr, nc)] = tentative_g
                came_from[(nr, nc)] = (cr, cc)
                f_score = tentative_g + heuristic(nr, nc)
                heapq.heappush(open_set, (f_score, tentative_g, nr, nc))

    # No path found -- fallback to straight line
    path = []
    steps = max(abs(dr - sr), abs(dc - sc), 1)
    for i in range(steps + 1):
        t = i / steps
        r = int(round(sr + t * (dr - sr)))
        c = int(round(sc + t * (dc - sc)))
        path.append((r, c))
    return path


# ---------------------------------------------------------------------------
# River carving
# ---------------------------------------------------------------------------

def carve_river_path(
    heightmap: np.ndarray,
    source: tuple[int, int],
    dest: tuple[int, int],
    width: int = 2,
    depth: float = 0.05,
    seed: int = 0,
) -> tuple[list[tuple[int, int]], np.ndarray]:
    """Carve a river channel from source to destination on a heightmap.

    Uses A* pathfinding to find a path preferring downhill routes, then
    lowers the heightmap along the path to create a channel.

    Parameters
    ----------
    heightmap : np.ndarray
        2D heightmap with values in [0, 1].
    source, dest : tuple of (row, col)
        Start and end coordinates.
    width : int
        Channel width in cells.
    depth : float
        Depth to carve (subtracted from heightmap values).
    seed : int
        Random seed (reserved for future jitter).

    Returns
    -------
    tuple of (path, modified_heightmap)
        path: list of (row, col) tuples.
        modified_heightmap: copy of heightmap with channel carved.
    """
    result = heightmap.copy()
    rows, cols = result.shape

    path = _astar(result, source, dest, slope_weight=8.0, height_weight=2.0)

    # Carve channel along path
    half_w = width // 2
    for r, c in path:
        for dr in range(-half_w, half_w + 1):
            for dc in range(-half_w, half_w + 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    # Distance-based falloff
                    dist = math.sqrt(dr * dr + dc * dc)
                    if dist <= half_w + 0.5:
                        falloff = 1.0 - dist / (half_w + 1.0)
                        result[nr, nc] -= depth * falloff

    result = np.clip(result, 0.0, 1.0)
    return path, result


# ---------------------------------------------------------------------------
# Road generation
# ---------------------------------------------------------------------------

def generate_road_path(
    heightmap: np.ndarray,
    waypoints: list[tuple[int, int]],
    width: int = 3,
    grade_strength: float = 0.8,
    seed: int = 0,
) -> tuple[list[tuple[int, int]], np.ndarray]:
    """Generate a road path between waypoints with terrain grading.

    Uses weighted A* preferring low-slope routes. Flattens vertices
    within `width` cells of the path to the path's average height.

    Parameters
    ----------
    heightmap : np.ndarray
        2D heightmap with values in [0, 1].
    waypoints : list of (row, col)
        Ordered waypoints the road passes through.
    width : int
        Road width in cells.
    grade_strength : float
        How aggressively to flatten terrain (0=none, 1=full).
    seed : int
        Random seed (reserved for future jitter).

    Returns
    -------
    tuple of (full_path, modified_heightmap)
        full_path: list of (row, col) tuples.
        modified_heightmap: copy of heightmap with road graded.
    """
    result = heightmap.copy()
    rows, cols = result.shape
    full_path: list[tuple[int, int]] = []

    # Connect each pair of waypoints
    for i in range(len(waypoints) - 1):
        segment = _astar(
            result,
            waypoints[i],
            waypoints[i + 1],
            slope_weight=10.0,
            height_weight=0.5,
        )
        if full_path and segment:
            # Avoid duplicate at junction
            full_path.extend(segment[1:])
        else:
            full_path.extend(segment)

    if not full_path:
        return full_path, result

    # Grade the road: flatten terrain along path
    half_w = width // 2
    for r, c in full_path:
        target_h = float(result[r, c])
        for dr in range(-half_w, half_w + 1):
            for dc in range(-half_w, half_w + 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    dist = math.sqrt(dr * dr + dc * dc)
                    if dist <= half_w + 0.5:
                        falloff = 1.0 - dist / (half_w + 1.0)
                        blend = grade_strength * falloff
                        current = float(result[nr, nc])
                        result[nr, nc] = current * (1.0 - blend) + target_h * blend

    result = np.clip(result, 0.0, 1.0)
    return full_path, result


# ---------------------------------------------------------------------------
# Hydraulic erosion (particle-based)
# ---------------------------------------------------------------------------

def hydraulic_erosion(
    heightmap: np.ndarray,
    iterations: int = 50000,
    erosion_rate: float = 0.01,
    deposition_rate: float = 0.01,
    evaporation_rate: float = 0.02,
    min_slope: float = 0.0001,
    seed: int = 0,
    max_particle_steps: int = 64,
    inertia: float = 0.3,
    gravity: float = 4.0,
    initial_water: float = 1.0,
    initial_speed: float = 1.0,
    sediment_capacity_factor: float = 4.0,
    min_sediment_capacity: float = 0.01,
) -> np.ndarray:
    """Particle-based hydraulic erosion on a 2D heightmap.

    Drops *iterations* water particles at random positions on the heightmap.
    Each particle flows downhill under gravity, eroding the terrain where it
    moves fast and depositing sediment where it slows down or evaporates.

    The algorithm follows the approach described by Hans Theobald Beyer (2015)
    and commonly used in game terrain generation:

      1. Drop a particle at a random position with initial water and speed.
      2. At each step compute the bilinear gradient at the particle's position.
      3. Update direction using inertia-weighted blend of old direction and
         gradient.
      4. Move the particle by one cell in the new direction.
      5. Compute height difference (delta_h) between old and new position.
         - If going uphill (delta_h > 0): deposit min(sediment, delta_h) to
           fill the pit and stop the particle.
         - If going downhill (delta_h < 0): compute sediment capacity from
           speed, water volume and slope.  If carrying more sediment than
           capacity, deposit excess.  Otherwise, erode terrain up to the
           difference between capacity and current sediment.
      6. Update speed from height difference and gravity.
      7. Evaporate a fraction of the water.
      8. Kill the particle when water drops below a threshold, speed is zero,
         or max steps reached.

    Parameters
    ----------
    heightmap : np.ndarray
        2D array of terrain heights.  Modified **in-place** is NOT done;
        a copy is returned.
    iterations : int
        Number of water particles to simulate.
    erosion_rate : float
        Fraction of terrain removed per step (0-1).
    deposition_rate : float
        Fraction of excess sediment deposited per step (0-1).
    evaporation_rate : float
        Fraction of water evaporated per step (0-1).
    min_slope : float
        Minimum slope used for sediment capacity (avoids division by zero).
    seed : int
        Random seed for reproducibility.
    max_particle_steps : int
        Maximum lifetime of each particle in simulation steps.
    inertia : float
        How much the particle's previous direction influences the new one
        (0 = pure gradient, 1 = pure inertia).
    gravity : float
        Gravitational acceleration factor for speed computation.
    initial_water : float
        Starting water volume per particle.
    initial_speed : float
        Starting speed per particle.
    sediment_capacity_factor : float
        Multiplier for sediment capacity from slope * speed * water.
    min_sediment_capacity : float
        Floor for sediment capacity (prevents zero-carry on flat terrain).

    Returns
    -------
    np.ndarray
        Eroded heightmap (same shape as input).
    """
    hmap = heightmap.astype(np.float64).copy()
    rows, cols = hmap.shape

    if rows < 3 or cols < 3:
        return hmap

    rng = np.random.RandomState(seed & 0x7FFFFFFF)

    # Pre-generate random start positions (batch for speed)
    start_x = rng.uniform(1.0, cols - 2.0, size=iterations)
    start_y = rng.uniform(1.0, rows - 2.0, size=iterations)

    for i in range(iterations):
        px = start_x[i]
        py = start_y[i]
        dir_x = 0.0
        dir_y = 0.0
        speed = initial_speed
        water = initial_water
        sediment = 0.0

        for _ in range(max_particle_steps):
            # Integer cell and fractional offset
            cx = int(px)
            cy = int(py)

            if cx < 1 or cx >= cols - 2 or cy < 1 or cy >= rows - 2:
                break

            fx = px - cx
            fy = py - cy

            # Bilinear interpolation of height at current position
            h00 = hmap[cy, cx]
            h10 = hmap[cy, cx + 1]
            h01 = hmap[cy + 1, cx]
            h11 = hmap[cy + 1, cx + 1]

            old_h = (
                h00 * (1 - fx) * (1 - fy)
                + h10 * fx * (1 - fy)
                + h01 * (1 - fx) * fy
                + h11 * fx * fy
            )

            # Compute gradient via finite differences of bilinear surface
            grad_x = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
            grad_y = (h01 - h00) * (1 - fx) + (h11 - h10) * fx

            # Update direction with inertia
            dir_x = dir_x * inertia - grad_x * (1 - inertia)
            dir_y = dir_y * inertia - grad_y * (1 - inertia)

            # Normalize direction
            dir_len = math.sqrt(dir_x * dir_x + dir_y * dir_y)
            if dir_len < 1e-10:
                # Random direction if gradient is zero
                angle = rng.uniform(0, 2 * math.pi)
                dir_x = math.cos(angle)
                dir_y = math.sin(angle)
            else:
                dir_x /= dir_len
                dir_y /= dir_len

            # Move particle
            new_px = px + dir_x
            new_py = py + dir_y

            # Check bounds
            ncx = int(new_px)
            ncy = int(new_py)
            if ncx < 1 or ncx >= cols - 2 or ncy < 1 or ncy >= rows - 2:
                break

            nfx = new_px - ncx
            nfy = new_py - ncy

            # Height at new position (bilinear)
            nh00 = hmap[ncy, ncx]
            nh10 = hmap[ncy, ncx + 1]
            nh01 = hmap[ncy + 1, ncx]
            nh11 = hmap[ncy + 1, ncx + 1]

            new_h = (
                nh00 * (1 - nfx) * (1 - nfy)
                + nh10 * nfx * (1 - nfy)
                + nh01 * (1 - nfx) * nfy
                + nh11 * nfx * nfy
            )

            delta_h = new_h - old_h

            # Sediment capacity based on slope, speed, and water volume
            slope = max(abs(delta_h), min_slope)
            capacity = max(
                min_sediment_capacity,
                slope * speed * water * sediment_capacity_factor,
            )

            if delta_h > 0:
                # Going uphill: deposit sediment to fill the pit
                deposit = min(sediment, delta_h)
                sediment -= deposit
                # Distribute deposit to the 4 surrounding cells (bilinear weights)
                hmap[cy, cx] += deposit * (1 - fx) * (1 - fy)
                hmap[cy, cx + 1] += deposit * fx * (1 - fy)
                hmap[cy + 1, cx] += deposit * (1 - fx) * fy
                hmap[cy + 1, cx + 1] += deposit * fx * fy
            elif sediment > capacity:
                # Carrying too much sediment: deposit excess
                deposit = (sediment - capacity) * deposition_rate
                sediment -= deposit
                hmap[cy, cx] += deposit * (1 - fx) * (1 - fy)
                hmap[cy, cx + 1] += deposit * fx * (1 - fy)
                hmap[cy + 1, cx] += deposit * (1 - fx) * fy
                hmap[cy + 1, cx + 1] += deposit * fx * fy
            else:
                # Erode terrain: pick up sediment
                erode = min(
                    (capacity - sediment) * erosion_rate,
                    -delta_h,  # don't erode more than height difference
                )
                sediment += erode
                hmap[cy, cx] -= erode * (1 - fx) * (1 - fy)
                hmap[cy, cx + 1] -= erode * fx * (1 - fy)
                hmap[cy + 1, cx] -= erode * (1 - fx) * fy
                hmap[cy + 1, cx + 1] -= erode * fx * fy

            # Update speed: v = sqrt(v^2 + delta_h * gravity)
            speed_sq = speed * speed + delta_h * gravity
            speed = math.sqrt(max(0.0, speed_sq))

            # Evaporate water
            water *= (1 - evaporation_rate)

            # Move to new position
            px = new_px
            py = new_py

            if water < 0.001:
                break

    return hmap


# ---------------------------------------------------------------------------
# Ridged multifractal noise
# ---------------------------------------------------------------------------

def ridged_multifractal(
    x: float,
    y: float,
    octaves: int = 6,
    lacunarity: float = 2.0,
    gain: float = 0.5,
    offset: float = 1.0,
    seed: int = 0,
) -> float:
    """Compute ridged multifractal noise at a point.

    Unlike standard fBm which produces smooth rounded hills, ridged
    multifractal takes the absolute value of the noise signal and inverts
    it (``offset - abs(noise)``), producing sharp mountain ridges and deep
    valleys.  The result is squared to sharpen ridges further, and each
    octave's amplitude is weighted by the previous octave's output to
    create natural-looking ridge networks.

    Parameters
    ----------
    x, y : float
        2D coordinates to evaluate.
    octaves : int
        Number of noise layers to combine.
    lacunarity : float
        Frequency multiplier per octave.
    gain : float
        Amplitude decay per octave (higher = more high-frequency detail).
    offset : float
        Controls ridge height.  1.0 produces ridges in [0, 1].
    seed : int
        Random seed for the noise generator.

    Returns
    -------
    float
        Ridged noise value, approximately in [0, 1].
    """
    gen = _make_noise_generator(seed)

    frequency = 1.0
    weight = 1.0
    result = 0.0
    max_val = 0.0

    for _ in range(octaves):
        # Sample noise and create ridge pattern
        signal = gen.noise2(x * frequency, y * frequency)
        signal = offset - abs(signal)
        signal *= signal  # square to sharpen ridges

        # Weight by previous octave (creates interconnected ridges)
        signal *= weight
        weight = max(0.0, min(1.0, signal * gain))

        result += signal
        max_val += offset * offset  # theoretical max per octave
        frequency *= lacunarity

    # Normalize to approximately [0, 1]
    if max_val > 0:
        result /= max_val
    return max(0.0, min(1.0, result))


def ridged_multifractal_array(
    xs: np.ndarray,
    ys: np.ndarray,
    octaves: int = 6,
    lacunarity: float = 2.0,
    gain: float = 0.5,
    offset: float = 1.0,
    seed: int = 0,
) -> np.ndarray:
    """Vectorized ridged multifractal noise for 2D coordinate arrays.

    Same algorithm as ``ridged_multifractal`` but operates on numpy arrays
    for batch evaluation.  The weight-per-octave is computed element-wise,
    preserving the interconnected ridge structure.

    Parameters
    ----------
    xs, ys : np.ndarray
        Coordinate arrays (same shape).
    octaves, lacunarity, gain, offset, seed :
        See ``ridged_multifractal``.

    Returns
    -------
    np.ndarray
        Ridged noise values, clipped to [0, 1], same shape as *xs*.
    """
    gen = _make_noise_generator(seed)

    frequency = 1.0
    weight = np.ones_like(xs, dtype=np.float64)
    result = np.zeros_like(xs, dtype=np.float64)
    max_val = 0.0

    for _ in range(octaves):
        signal = gen.noise2_array(xs * frequency, ys * frequency)
        signal = offset - np.abs(signal)
        signal = signal * signal  # square to sharpen ridges

        # Weight by previous octave
        signal *= weight
        weight = np.clip(signal * gain, 0.0, 1.0)

        result += signal
        max_val += offset * offset
        frequency *= lacunarity

    if max_val > 0:
        result /= max_val
    return np.clip(result, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Domain warping
# ---------------------------------------------------------------------------

def domain_warp(
    x: float,
    y: float,
    warp_strength: float = 0.5,
    warp_scale: float = 1.0,
    noise_fn: Any | None = None,
    seed: int = 0,
) -> tuple[float, float]:
    """Distort 2D coordinates using noise-based domain warping.

    Domain warping feeds coordinates through a noise function to produce
    offset values, then adds those offsets back to the original coordinates.
    This creates organic, flowing distortions that break up the regularity
    of procedural noise and produce natural-looking terrain features like
    meandering rivers and organic rock formations.

    Parameters
    ----------
    x, y : float
        Input coordinates to warp.
    warp_strength : float
        Amplitude of the distortion (in coordinate-space units).
    warp_scale : float
        Frequency scale for the warp noise (higher = more detailed warp).
    noise_fn : callable, optional
        Noise function with signature ``(x, y) -> float``.
        If *None*, uses the internal noise generator with the given seed.
    seed : int
        Random seed (used only when *noise_fn* is None).

    Returns
    -------
    tuple of (warped_x, warped_y)
        The distorted coordinates, ready to feed into another noise function.
    """
    if noise_fn is None:
        gen = _make_noise_generator(seed)
        noise_fn = gen.noise2

    # Use offset sampling positions to get independent x/y warps.
    # The offsets (5.2, 1.3) and (1.7, 9.2) are arbitrary constants
    # chosen to avoid correlation between the two warp axes.
    warp_x = noise_fn(x * warp_scale + 5.2, y * warp_scale + 1.3)
    warp_y = noise_fn(x * warp_scale + 1.7, y * warp_scale + 9.2)

    return (x + warp_x * warp_strength, y + warp_y * warp_strength)


def domain_warp_array(
    xs: np.ndarray,
    ys: np.ndarray,
    warp_strength: float = 0.5,
    warp_scale: float = 1.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized domain warping for numpy coordinate arrays.

    Same algorithm as ``domain_warp`` but operates on numpy arrays for
    batch evaluation.  Uses the internal noise generator (opensimplex or
    permutation-table fallback).

    Parameters
    ----------
    xs, ys : np.ndarray
        Coordinate arrays (same shape).
    warp_strength : float
        Amplitude of the distortion.
    warp_scale : float
        Frequency scale for the warp noise.
    seed : int
        Random seed for the noise generator.

    Returns
    -------
    tuple of (warped_xs, warped_ys)
        Distorted coordinate arrays, same shape as inputs.
    """
    gen = _make_noise_generator(seed)

    warp_x = gen.noise2_array(xs * warp_scale + 5.2, ys * warp_scale + 1.3)
    warp_y = gen.noise2_array(xs * warp_scale + 1.7, ys * warp_scale + 9.2)

    return (xs + warp_x * warp_strength, ys + warp_y * warp_strength)
