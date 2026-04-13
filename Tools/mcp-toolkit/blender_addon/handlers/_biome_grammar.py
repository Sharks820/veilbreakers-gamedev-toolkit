"""Pure-logic biome world map composer.

NO bpy/bmesh imports. All functions operate on numpy arrays and return
numpy arrays or plain Python data structures. Fully testable without Blender.

Provides:
  - WorldMapSpec: Dataclass describing a full multi-biome world map.
  - generate_world_map_spec: Main entry point for multi-biome world generation.
  - resolve_biome_name: Alias resolution for biome names.
  - BIOME_CLIMATE_PARAMS: Per-biome temperature/moisture/elevation parameters.
  - BIOME_ALIASES: Maps non-palette biome names to closest BIOME_PALETTES keys.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------------------
# Biome alias table
# Maps success-criteria biome names -> BIOME_PALETTES keys
# ---------------------------------------------------------------------------

BIOME_ALIASES: dict[str, str] = {
    "volcanic_wastes": "desert",          # hot, barren -- closest palette
    "frozen_tundra":   "mountain_pass",   # cold, rocky -- closest palette
    "thornwood":       "thornwood_forest",
    "swamp":           "corrupted_swamp",
}


def resolve_biome_name(name: str) -> str:
    """Return canonical BIOME_PALETTES key for name, applying aliases.

    Args:
        name: Biome name (canonical or aliased).

    Returns:
        Canonical BIOME_PALETTES key.

    Raises:
        ValueError: If name is not a known biome or alias.
    """
    from .terrain_materials import BIOME_PALETTES
    if name in BIOME_PALETTES:
        return name
    alias = BIOME_ALIASES.get(name)
    if alias and alias in BIOME_PALETTES:
        return alias
    raise ValueError(f"Unknown biome: '{name}'. Known: {sorted(BIOME_PALETTES.keys())}")


# ---------------------------------------------------------------------------
# Per-biome climate parameter table
# temperature: 0=freezing, 1=scorching
# moisture: 0=arid, 1=saturated
# elevation: 0=sea level, 1=high mountain
# ---------------------------------------------------------------------------

BIOME_CLIMATE_PARAMS: dict[str, dict] = {
    "thornwood_forest":  {"temperature": 0.45, "moisture": 0.70, "elevation": 0.30},
    "corrupted_swamp":   {"temperature": 0.50, "moisture": 0.90, "elevation": 0.10},
    "mountain_pass":     {"temperature": 0.20, "moisture": 0.35, "elevation": 0.80},
    "desert":            {"temperature": 0.85, "moisture": 0.05, "elevation": 0.30},
    "grasslands":        {"temperature": 0.60, "moisture": 0.55, "elevation": 0.25},
    "deep_forest":       {"temperature": 0.50, "moisture": 0.80, "elevation": 0.40},
    "coastal":           {"temperature": 0.65, "moisture": 0.85, "elevation": 0.05},
    "cemetery":          {"temperature": 0.30, "moisture": 0.40, "elevation": 0.20},
    "battlefield":       {"temperature": 0.40, "moisture": 0.30, "elevation": 0.25},
    "ruined_fortress":   {"temperature": 0.35, "moisture": 0.25, "elevation": 0.55},
    "abandoned_village": {"temperature": 0.50, "moisture": 0.50, "elevation": 0.20},
    "veil_crack_zone":   {"temperature": 0.10, "moisture": 0.20, "elevation": 0.60},
    "mushroom_forest":   {"temperature": 0.55, "moisture": 0.85, "elevation": 0.30},
    "crystal_cavern":    {"temperature": 0.15, "moisture": 0.40, "elevation": 0.70},
}


# ---------------------------------------------------------------------------
# WorldMapSpec dataclass
# ---------------------------------------------------------------------------

@dataclass
class WorldMapSpec:
    """Full specification for a multi-biome world map.

    All fields are pure-logic (no bpy). Consumed by handle_generate_multi_biome_world.
    """

    width: int                           # grid cells (e.g. 256)
    height: int                          # grid cells (e.g. 256)
    world_size: float                    # meters (e.g. 512.0)
    seed: int
    biome_ids: np.ndarray                # (height, width) int32, values 0..biome_count-1
    biome_weights: np.ndarray            # (height, width, biome_count) float64, sum=1
    biome_names: list[str]               # length == biome_count, canonical BIOME_PALETTES keys
    corruption_map: np.ndarray           # (height, width) float64 in [0, 1]
    flatten_zones: list[dict]            # normalized coords, one per building_plot
    cell_params: list[dict]              # per-biome climate params (temperature, moisture, elevation)
    transition_width_m: float            # meters (e.g. 15.0)


# ---------------------------------------------------------------------------
# Default biome list (6 VeilBreakers presets)
# ---------------------------------------------------------------------------

_DEFAULT_BIOMES = [
    "thornwood_forest", "corrupted_swamp", "mountain_pass",
    "desert", "grasslands", "deep_forest",
]


# ---------------------------------------------------------------------------
# generate_world_map_spec: Main entry point
# ---------------------------------------------------------------------------

def generate_world_map_spec(
    width: int = 256,
    height: int = 256,
    world_size: float = 512.0,
    biome_count: int = 6,
    biomes: list[str] | None = None,
    seed: int = 42,
    corruption_level: float = 0.0,
    building_plots: list[dict] | None = None,
    transition_width_m: float = 15.0,
) -> WorldMapSpec:
    """Compose a WorldMapSpec for multi-biome world generation.

    Args:
        width: Grid resolution (cells).
        height: Grid resolution (cells).
        world_size: World extent in meters. Used to normalize flatten zones.
        biome_count: Number of Voronoi biome regions.
        biomes: List of biome names (canonical or alias). Defaults to 6 VB presets.
        seed: Master seed.
        corruption_level: Global corruption intensity [0, 1].
        building_plots: List of dicts with world-space keys: x, y, width, depth.
            Used to compute flatten zones. Coords in meters [0, world_size].
        transition_width_m: Blend zone width in meters.

    Returns:
        WorldMapSpec with all fields populated.

    Raises:
        ValueError: If biome names are invalid or count mismatch.
    """
    rng = random.Random(seed)

    # --- Resolve and validate biome names ---
    if biomes is None:
        chosen = list(_DEFAULT_BIOMES[:biome_count])
        if len(chosen) < biome_count:
            from .terrain_materials import BIOME_PALETTES
            extras = [b for b in BIOME_PALETTES if b not in chosen]
            chosen = chosen + extras[:biome_count - len(chosen)]
    else:
        chosen = [resolve_biome_name(b) for b in biomes]

    if len(chosen) != biome_count:
        raise ValueError(f"Expected {biome_count} biome names, got {len(chosen)}")

    # --- Normalized transition width ---
    transition_width_norm = transition_width_m / world_size

    # --- Voronoi distribution ---
    from ._terrain_noise import voronoi_biome_distribution
    biome_ids, biome_weights = voronoi_biome_distribution(
        width=width,
        height=height,
        biome_count=biome_count,
        transition_width=transition_width_norm,
        seed=seed,
        biome_names=chosen,
    )

    # --- Corruption map: fBm noise scaled by corruption_level ---
    # Use a separate seed offset so corruption pattern != biome distribution
    corruption_map = _generate_corruption_map(
        width, height, seed=seed + 7919, scale=corruption_level
    )

    # --- Flatten zones from building plots ---
    flatten_zones = []
    for plot in (building_plots or []):
        # Convert world-space to normalized [0, 1]
        cx = plot["x"] / world_size
        cy = plot["y"] / world_size
        # Radius = half of largest footprint dimension, with 20% padding
        max_dim = max(plot.get("width", 8.0), plot.get("depth", 8.0))
        radius = (max_dim / 2.0) / world_size * 1.2
        blend_width = radius * 0.5
        flatten_zones.append({
            "center_x": cx,
            "center_y": cy,
            "radius": radius,
            "blend_width": blend_width,
            "seed": rng.randint(0, 99999),
        })

    # --- Per-biome climate params ---
    cell_params = [
        BIOME_CLIMATE_PARAMS.get(
            name, {"temperature": 0.5, "moisture": 0.5, "elevation": 0.5}
        )
        for name in chosen
    ]

    return WorldMapSpec(
        width=width,
        height=height,
        world_size=world_size,
        seed=seed,
        biome_ids=biome_ids,
        biome_weights=biome_weights,
        biome_names=chosen,
        corruption_map=corruption_map,
        flatten_zones=flatten_zones,
        cell_params=cell_params,
        transition_width_m=transition_width_m,
    )


# ---------------------------------------------------------------------------
# _generate_corruption_map: fBm noise corruption intensity
# ---------------------------------------------------------------------------

def _generate_corruption_map(
    width: int,
    height: int,
    seed: int,
    scale: float,
    octaves: int = 4,
) -> np.ndarray:
    """Generate a per-cell corruption intensity map using fBm noise.

    Returns np.ndarray (height, width) in [0, 1]. Values scaled by `scale`
    so corruption_level=0.0 returns all-zeros, 1.0 returns full noise range.

    Args:
        width: Grid width in cells.
        height: Grid height in cells.
        seed: RNG seed for this corruption pattern.
        scale: Global multiplier [0, 1]. If 0, returns all-zeros.
        octaves: Number of fBm octaves.

    Returns:
        np.ndarray (height, width) float64 clipped to [0, 1].
    """
    if scale <= 0.0:
        return np.zeros((height, width), dtype=np.float64)

    from ._terrain_noise import _make_noise_generator
    gen = _make_noise_generator(seed)

    ys = np.arange(height, dtype=np.float64) / height
    xs = np.arange(width, dtype=np.float64) / width
    yy, xx = np.meshgrid(ys, xs, indexing="ij")

    # fBm noise
    noise = np.zeros((height, width), dtype=np.float64)
    amplitude = 1.0
    frequency = 3.0
    total_amp = 0.0
    for _ in range(octaves):
        noise += gen.noise2_array(xx * frequency, yy * frequency) * amplitude
        total_amp += amplitude
        amplitude *= 0.5
        frequency *= 2.0

    noise = noise / total_amp  # normalize to ~[-1, 1]
    noise = (noise + 1.0) / 2.0  # remap to [0, 1]
    return np.clip(noise * scale, 0.0, 1.0)


def _box_filter_2d(arr: np.ndarray, radius: int) -> np.ndarray:
    """Simple 2D box (mean) filter using cumulative sums. No scipy needed."""
    if radius <= 0:
        return arr.copy()
    h, w = arr.shape
    size = 2 * radius + 1
    # Pad with edge values
    padded = np.pad(arr, radius, mode="edge")
    # Cumulative sum approach for fast uniform filter
    cs = np.cumsum(np.cumsum(padded, axis=0), axis=1)
    # Compute box means using the integral image
    result = np.empty_like(arr)
    for y in range(h):
        for x in range(w):
            y2, x2 = y + size - 1, x + size - 1
            total = cs[y2, x2]
            if y > 0:
                total -= cs[y - 1, x2]
            if x > 0:
                total -= cs[y2, x - 1]
            if y > 0 and x > 0:
                total += cs[y - 1, x - 1]
            result[y, x] = total / (size * size)
    return result


def _distance_from_mask(mask: np.ndarray) -> np.ndarray:
    """Approximate Euclidean distance transform using iterative passes.

    For each True cell in *mask*, returns approximate distance to nearest
    False cell. Pure numpy, no scipy dependency.
    """
    h, w = mask.shape
    dist = np.full((h, w), h + w, dtype=np.float64)
    dist[~mask] = 0.0

    # Forward pass
    for y in range(h):
        for x in range(w):
            if y > 0:
                dist[y, x] = min(dist[y, x], dist[y - 1, x] + 1.0)
            if x > 0:
                dist[y, x] = min(dist[y, x], dist[y, x - 1] + 1.0)
    # Backward pass
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            if y < h - 1:
                dist[y, x] = min(dist[y, x], dist[y + 1, x] + 1.0)
            if x < w - 1:
                dist[y, x] = min(dist[y, x], dist[y, x + 1] + 1.0)
    return dist


# ===========================================================================
# Geology Feature Generators  (Clusters L-P gap fills)
#
# Each function is pure numpy — accepts a (H, W) heightmap + params,
# returns a modified heightmap or a feature mask. Deterministic given seed.
# ===========================================================================


def apply_periglacial_patterns(
    heightmap: np.ndarray,
    seed: int = 0,
    intensity: float = 0.5,
    frost_heave_scale: float = 0.02,
) -> np.ndarray:
    """Apply periglacial patterned-ground features to a heightmap.

    Simulates frost heave polygon patterns (sorted circles / stone stripes)
    using a Voronoi-cell displacement field.  Higher-elevation cells get
    stronger displacement, mimicking permafrost processes.

    Args:
        heightmap: (H, W) float64 terrain heights.
        seed: Deterministic RNG seed.
        intensity: Feature strength multiplier [0, 1].
        frost_heave_scale: Amplitude of frost-heave bumps (metres).

    Returns:
        Modified (H, W) heightmap with periglacial micro-relief.
    """
    if intensity <= 0.0:
        return heightmap.copy()
    h, w = heightmap.shape
    rng = np.random.RandomState(seed)

    # Voronoi cell centers — frost polygon seeds
    n_centers = max(4, int(h * w * 0.0004))
    cy = rng.randint(0, h, size=n_centers)
    cx = rng.randint(0, w, size=n_centers)

    # Distance-to-nearest-center field (cheap Voronoi)
    ys = np.arange(h, dtype=np.float64).reshape(-1, 1)
    xs = np.arange(w, dtype=np.float64).reshape(1, -1)
    min_dist = np.full((h, w), 1e9, dtype=np.float64)
    for i in range(n_centers):
        d = np.sqrt((ys - cy[i]) ** 2 + (xs - cx[i]) ** 2)
        np.minimum(min_dist, d, out=min_dist)

    # Normalize and invert — ridges at polygon boundaries
    max_d = min_dist.max()
    if max_d > 0:
        min_dist /= max_d
    heave = min_dist * frost_heave_scale * intensity

    # Scale by elevation — stronger at high points (permafrost zone)
    elev_mask = (heightmap - heightmap.min()) / max((heightmap.max() - heightmap.min()), 1e-6)
    elev_mask = np.clip(elev_mask * 2.0, 0.0, 1.0)  # top half gets full effect

    return heightmap + heave * elev_mask


def apply_desert_pavement(
    heightmap: np.ndarray,
    seed: int = 0,
    intensity: float = 0.5,
    smoothing_radius: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate desert pavement (reg) surface on low-slope areas.

    Returns the smoothed heightmap and a pavement_mask (H, W) float [0,1]
    indicating pavement coverage (1 = fully paved, 0 = no pavement).

    Low-slope, low-elevation areas are flattened slightly and marked as
    pavement.  The mask can drive a material shader downstream.

    Args:
        heightmap: (H, W) float64 terrain heights.
        seed: Deterministic RNG seed.
        intensity: Strength of flattening and mask coverage [0, 1].
        smoothing_radius: Kernel radius for slope-based smoothing.

    Returns:
        Tuple of (modified heightmap, pavement_mask).
    """
    h, w = heightmap.shape
    if intensity <= 0.0:
        return heightmap.copy(), np.zeros((h, w), dtype=np.float64)

    # Compute slope via gradient magnitude
    gy, gx = np.gradient(heightmap)
    slope = np.sqrt(gx ** 2 + gy ** 2)

    # Pavement forms on flat, low areas
    flat_mask = 1.0 - np.clip(slope / max(slope.max(), 1e-6) * 4.0, 0.0, 1.0)
    elev_norm = (heightmap - heightmap.min()) / max((heightmap.max() - heightmap.min()), 1e-6)
    low_mask = 1.0 - np.clip(elev_norm * 2.0, 0.0, 1.0)
    pavement_mask = np.clip(flat_mask * low_mask * intensity, 0.0, 1.0)

    # Smooth heightmap in pavement zones (wind-deflation flattening)
    # Pure-numpy box filter (no scipy dependency)
    smoothed = _box_filter_2d(heightmap.astype(np.float64), smoothing_radius)
    result = heightmap * (1.0 - pavement_mask) + smoothed * pavement_mask

    return result, pavement_mask


def compute_spring_line_mask(
    heightmap: np.ndarray,
    geology_layers: int = 3,
    seed: int = 0,
) -> np.ndarray:
    """Identify spring line positions where water emerges at geological layer boundaries.

    Returns a (H, W) float mask [0, 1] where 1 marks likely spring locations.
    Spring lines form where an impermeable layer meets a permeable layer at
    the surface, approximated here by elevation contour bands.

    Args:
        heightmap: (H, W) float64 terrain heights.
        geology_layers: Number of geological strata to simulate.
        seed: Deterministic RNG seed (for layer offset noise).

    Returns:
        Spring-line mask (H, W) float64 in [0, 1].
    """
    h, w = heightmap.shape
    rng = np.random.RandomState(seed)

    elev_norm = (heightmap - heightmap.min()) / max((heightmap.max() - heightmap.min()), 1e-6)

    # Compute slope — springs emerge on slopes, not flats or cliffs
    gy, gx = np.gradient(heightmap)
    slope = np.sqrt(gx ** 2 + gy ** 2)
    slope_norm = slope / max(slope.max(), 1e-6)
    # Mid-range slope is ideal for springs
    slope_band = np.exp(-((slope_norm - 0.3) ** 2) / 0.02)

    # Layer boundaries: quantize elevation into strata, mark transitions
    layer_thickness = 1.0 / max(geology_layers, 1)
    offsets = rng.uniform(-0.02, 0.02, size=geology_layers)
    spring_mask = np.zeros((h, w), dtype=np.float64)
    for i in range(geology_layers):
        boundary = layer_thickness * (i + 1) + offsets[i]
        dist_to_boundary = np.abs(elev_norm - boundary)
        # Narrow band around each boundary
        spring_mask += np.exp(-(dist_to_boundary ** 2) / 0.001)

    spring_mask = np.clip(spring_mask, 0.0, 1.0) * slope_band
    return np.clip(spring_mask, 0.0, 1.0)


def apply_landslide_scars(
    heightmap: np.ndarray,
    seed: int = 0,
    num_slides: int = 3,
    scar_depth: float = 0.05,
    runout_factor: float = 2.5,
) -> np.ndarray:
    """Carve landslide scars and deposit runout fans into a heightmap.

    Each landslide originates from a steep slope, carves a concave scar
    uphill and deposits a convex fan at the toe.

    Args:
        heightmap: (H, W) float64 terrain heights.
        seed: Deterministic RNG seed.
        num_slides: Number of landslide features to generate.
        scar_depth: Maximum depth of the scar (metres, relative).
        runout_factor: Length of deposit fan relative to scar radius.

    Returns:
        Modified (H, W) heightmap with landslide features.
    """
    h, w = heightmap.shape
    result = heightmap.copy()
    rng = np.random.RandomState(seed)

    # Find steep areas as candidate origins
    gy, gx = np.gradient(heightmap)
    slope = np.sqrt(gx ** 2 + gy ** 2)

    ys = np.arange(h, dtype=np.float64).reshape(-1, 1)
    xs = np.arange(w, dtype=np.float64).reshape(1, -1)

    for _ in range(num_slides):
        # Sample origin weighted by slope steepness
        flat_slope = slope.ravel()
        prob = flat_slope / max(flat_slope.sum(), 1e-12)
        idx = rng.choice(len(prob), p=prob)
        oy, ox = divmod(idx, w)

        # Scar radius
        scar_r = rng.uniform(max(3, h * 0.03), max(5, h * 0.08))
        dist = np.sqrt((ys - oy) ** 2 + (xs - ox) ** 2)

        # Downhill direction from gradient
        dy_dir = -gy[oy, ox]
        dx_dir = -gx[oy, ox]
        norm = math.sqrt(dx_dir ** 2 + dy_dir ** 2) or 1.0
        dx_dir /= norm
        dy_dir /= norm

        # Scar: concave excavation around origin
        scar_mask = np.clip(1.0 - dist / scar_r, 0.0, 1.0) ** 2
        result -= scar_mask * scar_depth

        # Deposit fan: offset downhill, wider, shallower
        fan_cx = oy + dy_dir * scar_r * runout_factor
        fan_cy = ox + dx_dir * scar_r * runout_factor
        fan_r = scar_r * 1.5
        fan_dist = np.sqrt((ys - fan_cx) ** 2 + (xs - fan_cy) ** 2)
        fan_mask = np.clip(1.0 - fan_dist / fan_r, 0.0, 1.0)
        # Deposit is ~60% of excavated volume
        result += fan_mask * scar_depth * 0.6

    return result


def apply_hot_spring_features(
    heightmap: np.ndarray,
    seed: int = 0,
    num_springs: int = 2,
    pool_radius: float = 5.0,
    pool_depth: float = 0.03,
    terrace_rings: int = 4,
) -> tuple[np.ndarray, list[dict]]:
    """Create hot spring pools with travertine terraces.

    Returns the modified heightmap and a list of spring location dicts
    for downstream VFX placement (steam, mineral coloring).

    Args:
        heightmap: (H, W) float64 terrain heights.
        seed: Deterministic RNG seed.
        num_springs: Number of hot spring pools to place.
        pool_radius: Radius of the main pool (in grid cells).
        pool_depth: Depth of pool depression (metres, relative).
        terrace_rings: Number of travertine terrace steps.

    Returns:
        Tuple of (modified heightmap, list of spring info dicts).
    """
    h, w = heightmap.shape
    result = heightmap.copy()
    rng = np.random.RandomState(seed)
    springs: list[dict] = []

    ys = np.arange(h, dtype=np.float64).reshape(-1, 1)
    xs = np.arange(w, dtype=np.float64).reshape(1, -1)

    for _ in range(num_springs):
        # Place springs in mid-elevation zones
        elev_norm = (heightmap - heightmap.min()) / max((heightmap.max() - heightmap.min()), 1e-6)
        mid_mask = np.exp(-((elev_norm - 0.4) ** 2) / 0.05)
        flat_mask = mid_mask.ravel()
        prob = flat_mask / max(flat_mask.sum(), 1e-12)
        idx = rng.choice(len(prob), p=prob)
        sy, sx = divmod(idx, w)

        dist = np.sqrt((ys - sy) ** 2 + (xs - sx) ** 2)

        # Main pool depression
        pool_mask = np.clip(1.0 - dist / pool_radius, 0.0, 1.0) ** 2
        result -= pool_mask * pool_depth

        # Travertine terraces: concentric stepped rings
        for ring in range(1, terrace_rings + 1):
            ring_r = pool_radius + ring * pool_radius * 0.4
            ring_width = pool_radius * 0.15
            ring_dist = np.abs(dist - ring_r)
            terrace_mask = np.clip(1.0 - ring_dist / ring_width, 0.0, 1.0)
            step_h = pool_depth * 0.15 * (1.0 - ring / (terrace_rings + 1))
            result += terrace_mask * step_h

        springs.append({
            "grid_y": int(sy),
            "grid_x": int(sx),
            "pool_radius": float(pool_radius),
            "elevation": float(heightmap[sy, sx]),
        })

    return result, springs


def apply_reef_platform(
    heightmap: np.ndarray,
    sea_level: float = 0.0,
    seed: int = 0,
    reef_width: float = 8.0,
    reef_height: float = 0.01,
) -> np.ndarray:
    """Build fringing reef platforms at the coastline.

    Reefs form a raised platform just below sea level along the coast.
    The reef crest sits at sea_level and the platform extends seaward.

    Args:
        heightmap: (H, W) float64 terrain heights.
        sea_level: Water surface elevation.
        seed: Deterministic RNG seed for roughness noise.
        reef_width: Width of reef platform in grid cells.
        reef_height: Height of reef crest above surrounding seabed.

    Returns:
        Modified (H, W) heightmap with reef features.
    """
    h, w = heightmap.shape
    result = heightmap.copy()
    rng = np.random.RandomState(seed)

    # Coast mask: cells just below sea level
    underwater = heightmap < sea_level
    above = ~underwater

    if not underwater.any() or not above.any():
        return result  # no coastline

    # Distance from shore (for underwater cells only) — pure numpy
    shore_dist = _distance_from_mask(underwater)

    # Reef band: narrow strip near coast
    reef_mask = np.clip(1.0 - np.abs(shore_dist - reef_width * 0.5) / (reef_width * 0.5), 0.0, 1.0)
    reef_mask *= underwater.astype(np.float64)

    # Add reef height with some roughness
    roughness = rng.uniform(0.7, 1.3, size=(h, w))
    result += reef_mask * reef_height * roughness

    # Clamp reef crest to not exceed sea level
    np.minimum(result, sea_level, out=result, where=underwater)

    return result


def apply_tafoni_weathering(
    heightmap: np.ndarray,
    seed: int = 0,
    intensity: float = 0.5,
    cavity_scale: float = 0.01,
    num_cavities: int = 50,
) -> np.ndarray:
    """Apply tafoni (honeycomb weathering) erosion pits to rock surfaces.

    Creates small concave cavities on steep rock faces, simulating
    salt-crystal or differential weathering.

    Args:
        heightmap: (H, W) float64 terrain heights.
        seed: Deterministic RNG seed.
        intensity: Weathering strength [0, 1].
        cavity_scale: Depth of individual cavities (metres, relative).
        num_cavities: Number of tafoni cavities to generate.

    Returns:
        Modified (H, W) heightmap with tafoni pits.
    """
    h, w = heightmap.shape
    if intensity <= 0.0:
        return heightmap.copy()
    result = heightmap.copy()
    rng = np.random.RandomState(seed)

    # Tafoni form on steep, exposed rock
    gy, gx = np.gradient(heightmap)
    slope = np.sqrt(gx ** 2 + gy ** 2)
    steep_mask = np.clip(slope / max(slope.max(), 1e-6) * 3.0, 0.0, 1.0)

    ys = np.arange(h, dtype=np.float64).reshape(-1, 1)
    xs = np.arange(w, dtype=np.float64).reshape(1, -1)

    for _ in range(num_cavities):
        # Place cavity weighted by steepness
        prob = steep_mask.ravel()
        prob_sum = prob.sum()
        if prob_sum < 1e-12:
            break
        prob = prob / prob_sum
        idx = rng.choice(len(prob), p=prob)
        cy, cx = divmod(idx, w)

        # Small elliptical cavity
        rx = rng.uniform(1.5, 4.0)
        ry = rng.uniform(1.5, 4.0)
        dist = np.sqrt(((ys - cy) / ry) ** 2 + ((xs - cx) / rx) ** 2)
        cavity = np.clip(1.0 - dist, 0.0, 1.0) ** 2
        result -= cavity * cavity_scale * intensity

    return result


def apply_geological_folds(
    heightmap: np.ndarray,
    seed: int = 0,
    num_folds: int = 3,
    amplitude: float = 0.05,
    wavelength_cells: float = 30.0,
    fold_type: str = "syncline",
) -> np.ndarray:
    """Apply geological fold deformation (anticline/syncline) to terrain.

    Simulates tectonic folding by adding sinusoidal undulations along a
    random strike direction. ``fold_type`` controls the fold geometry:
    - "anticline": upward arch (positive center displacement)
    - "syncline": downward trough (negative center displacement)
    - "chevron": angular V-shaped folds

    Args:
        heightmap: (H, W) float64 terrain heights.
        seed: Deterministic RNG seed.
        num_folds: Number of fold axes.
        amplitude: Peak fold displacement (metres, relative).
        wavelength_cells: Wavelength of fold in grid cells.
        fold_type: "anticline", "syncline", or "chevron".

    Returns:
        Modified (H, W) heightmap with fold deformation.
    """
    h, w = heightmap.shape
    result = heightmap.copy()
    rng = np.random.RandomState(seed)

    ys = np.arange(h, dtype=np.float64).reshape(-1, 1)
    xs = np.arange(w, dtype=np.float64).reshape(1, -1)

    sign = -1.0 if fold_type == "syncline" else 1.0

    for _ in range(num_folds):
        # Random strike direction
        angle = rng.uniform(0, math.pi)
        dx = math.cos(angle)
        dy = math.sin(angle)

        # Project coordinates onto perpendicular direction
        proj = xs * (-dy) + ys * dx

        # Phase offset
        phase = rng.uniform(0, 2 * math.pi)

        if fold_type == "chevron":
            # Triangular wave for angular folds
            t = (proj / wavelength_cells + phase / (2 * math.pi)) % 1.0
            wave = 2.0 * np.abs(2.0 * (t - np.floor(t + 0.5))) - 1.0
        else:
            wave = np.sin(2.0 * math.pi * proj / wavelength_cells + phase)

        result += wave * amplitude * sign

    return result
