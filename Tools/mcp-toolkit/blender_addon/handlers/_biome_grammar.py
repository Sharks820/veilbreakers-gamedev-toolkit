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
from dataclasses import dataclass, field
from typing import Any

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
