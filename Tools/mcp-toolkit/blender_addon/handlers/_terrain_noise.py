"""Pure-logic terrain noise, biome assignment, and pathing algorithms.

NO bpy/bmesh imports. All functions operate on numpy arrays and return
numpy arrays or plain Python data structures. Fully testable without Blender.

Provides:
  - generate_heightmap: fBm noise heightmap with terrain-type presets
  - compute_slope_map: Slope in degrees from heightmap gradients
  - compute_biome_assignments: Per-cell biome index from altitude/slope rules
  - carve_river_path: A* river channel carving on heightmap
  - generate_road_path: Weighted A* road with terrain grading
  - TERRAIN_PRESETS: Parameter dicts for 6 terrain types
  - BIOME_RULES: Default dark-fantasy biome rules
"""

from __future__ import annotations

import heapq
import math
from typing import Any

import numpy as np

try:
    from opensimplex import OpenSimplex
except ImportError:
    # Fallback: use a simple hash-based noise when opensimplex isn't installed
    # (e.g. Blender's bundled Python may not have it)
    class OpenSimplex:  # type: ignore[no-redef]
        """Minimal noise fallback using hash-based value noise."""
        def __init__(self, seed: int = 0) -> None:
            self._seed = seed
        def noise2(self, x: float, y: float) -> float:
            # Deterministic pseudo-noise via hash mixing
            import hashlib
            h = hashlib.md5(f"{self._seed}:{x:.6f}:{y:.6f}".encode()).digest()
            return (int.from_bytes(h[:4], "little") / 2147483647.0) - 1.0

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
) -> np.ndarray:
    """Generate a 2D heightmap using fBm (fractal Brownian motion) noise.

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

    gen = OpenSimplex(seed=seed)

    # Vectorized fBm: build 1D coordinate arrays and evaluate noise
    # per-octave using the batch API for 4096+ performance.
    x_1d = np.arange(width, dtype=np.float64) / scale
    y_1d = np.arange(height, dtype=np.float64) / scale

    hmap = np.zeros((height, width), dtype=np.float64)
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0

    # Use noise2array (1D x, 1D y -> 2D result) if available,
    # otherwise fall back to np.vectorize wrapping the scalar noise2.
    _noise2_array = getattr(gen, 'noise2array', None)

    for _octave in range(oct_):
        freq_x = x_1d * frequency
        freq_y = y_1d * frequency
        if _noise2_array is not None:
            # noise2array(x_1d, y_1d) returns shape (len(y), len(x))
            octave_noise = _noise2_array(freq_x, freq_y)
        else:
            # Fallback: build 2D grids and vectorize the scalar noise2
            yy, xx = np.meshgrid(freq_y, freq_x, indexing='ij')
            _vfunc = np.vectorize(gen.noise2, otypes=[np.float64])
            octave_noise = _vfunc(xx, yy)
        hmap += octave_noise * amplitude
        max_val += amplitude
        amplitude *= pers_
        frequency *= lac_

    if max_val > 0:
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
