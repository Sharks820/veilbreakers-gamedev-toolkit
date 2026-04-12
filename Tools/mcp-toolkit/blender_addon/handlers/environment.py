"""Environment handlers for terrain generation, biome painting, water, and export.

Provides terrain/environment command handlers:
  - handle_generate_terrain: Heightmap -> bmesh grid terrain mesh
  - handle_generate_terrain_tile: World-space tiled terrain mesh
  - handle_generate_world_terrain: Multi-tile world region generation
  - handle_paint_terrain: Slope/altitude biome rules -> material slot assignment
  - handle_carve_river: River channel carving along A* path
  - handle_generate_road: A-to-B road with proper grading
  - handle_create_water: Lake/ocean/pond plane with shoreline
  - handle_export_heightmap: 16-bit Unity RAW export
"""

from __future__ import annotations

import logging
import math
import struct
import zlib
from pathlib import Path
from typing import Any, Optional

import numpy as np

import bpy
import bmesh

logger = logging.getLogger(__name__)

from ._terrain_noise import (
    generate_heightmap,
    compute_slope_map,
    compute_biome_assignments,
    carve_river_path,
    generate_road_path,
    _theoretical_max_amplitude,
    TERRAIN_PRESETS,
    BIOME_RULES,
)
from ._terrain_erosion import (
    apply_hydraulic_erosion,
    apply_thermal_erosion,
)
from ._terrain_world import (
    erode_world_heightmap,
    generate_world_heightmap,
)
# NOTE: extract_tile and world_region_dimensions were removed from this import
# because they are only used by the deprecated handle_generate_world_terrain.
# They remain available in _terrain_world for direct import if needed.
from .terrain_chunking import validate_tile_seams
from .terrain_materials import compute_world_splatmap_weights
from .terrain_features import generate_waterfall
from ._water_network import WaterNetwork


# ---------------------------------------------------------------------------
# Validation helpers (pure logic -- testable without Blender)
# ---------------------------------------------------------------------------

_VALID_TERRAIN_TYPES = frozenset(TERRAIN_PRESETS.keys())
_VALID_EROSION_MODES = frozenset({"none", "hydraulic", "thermal", "both"})
_MAX_RESOLUTION = 4096  # 8192 can OOM Blender; 4096 is practical AAA limit


def _parse_bool(value: Any) -> bool:
    """Parse a boolean value correctly, handling string 'false'/'true'.

    F152: bool("false") == True in Python -- this helper fixes that.
    Accepts bool, int, and common string representations.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _detect_grid_dims(bm) -> tuple[int, int]:
    """WORLD-004: Detect actual (rows, cols) of a terrain grid mesh.

    Counts unique rounded X and Y coordinate positions to infer actual
    grid width and height.  This is robust for non-square terrain meshes
    (e.g. 256×512) where ``int(math.sqrt(vert_count))`` would give wrong
    dimensions and cause reshape crashes.

    Falls back to sqrt-based square assumption only when coordinate
    detection produces an inconsistent vertex count.

    Returns:
        (rows, cols) tuple suitable for ``array.reshape(rows, cols)``.
    """
    xs = set(round(v.co.x, 3) for v in bm.verts)
    ys = set(round(v.co.y, 3) for v in bm.verts)
    cols, rows = len(xs), len(ys)
    if cols * rows == len(bm.verts):
        return rows, cols
    # Fallback: assume square
    side = max(2, int(math.sqrt(len(bm.verts))))
    return side, side


# ---------------------------------------------------------------------------
# VeilBreakers biome presets
# ---------------------------------------------------------------------------

# Erosion iteration policy: any preset with erosion enabled MUST use at least
# 5000 iterations.  Values below 5000 produce no visible erosion channels and
# defeat the purpose of the simulation pass.  Mountain/extreme biomes may use
# higher values (e.g. 8000-10000) for deeper carving.
VB_BIOME_PRESETS: dict[str, dict] = {
    "thornwood_forest": {
        "terrain_type": "hills",
        "resolution": 512,
        "height_scale": 15.0,
        "erosion": True,
        "erosion_iterations": 5000,
        "seed": None,  # random
        "scatter_rules": [
            {"asset": "tree_healthy", "density": 0.24, "min_distance": 4.5, "scale_range": [1.0, 1.9]},
            {"asset": "tree_boundary", "density": 0.14, "min_distance": 4.0, "scale_range": [0.9, 1.8]},
            {"asset": "tree_blighted", "density": 0.05, "min_distance": 5.5, "scale_range": [0.8, 1.4]},
            {"asset": "shrub", "density": 0.24, "min_distance": 2.0, "scale_range": [0.7, 1.2]},
            {"asset": "grass", "density": 0.35, "min_distance": 1.2, "scale_range": [0.6, 1.0]},
            {"asset": "rock_mossy", "density": 0.10, "min_distance": 3.0, "scale_range": [0.7, 1.3]},
            {"asset": "root", "density": 0.07, "min_distance": 2.6, "scale_range": [0.7, 1.1]},
            {"asset": "mushroom_cluster", "density": 0.05, "min_distance": 1.8, "scale_range": [0.45, 0.9]},
            {"asset": "fallen_log", "density": 0.02, "min_distance": 8.0, "scale_range": [0.8, 1.2]},
        ],
    },
    "corrupted_swamp": {
        "terrain_type": "flat",
        "resolution": 512,
        "height_scale": 5.0,
        "erosion": True,
        "erosion_iterations": 5000,
        "seed": None,
        "scatter_rules": [
            {"asset": "dead_tree", "density": 0.2, "min_distance": 4.0, "scale_range": [0.6, 1.0]},
            {"asset": "poison_pool", "density": 0.1, "min_distance": 8.0, "scale_range": [1.0, 2.0]},
            {"asset": "vine_cluster", "density": 0.3, "min_distance": 2.0, "scale_range": [0.5, 1.5]},
            {"asset": "spore_pod", "density": 0.15, "min_distance": 3.0, "scale_range": [0.3, 0.8]},
        ],
    },
    "mountain_pass": {
        "terrain_type": "mountains",
        "resolution": 512,
        "height_scale": 40.0,
        "erosion": True,
        "erosion_iterations": 5000,
        "seed": None,
        "default_season": "winter",
        "scatter_rules": [
            {"asset": "boulder", "density": 0.18, "min_distance": 5.0, "scale_range": [0.9, 2.8]},
            {"asset": "rock_mossy", "density": 0.16, "min_distance": 3.4, "scale_range": [0.8, 1.8]},
            {"asset": "pine_tree", "density": 0.11, "min_distance": 7.5, "scale_range": [0.9, 1.4]},
            {"asset": "tree_boundary", "density": 0.04, "min_distance": 8.0, "scale_range": [0.85, 1.25]},
            {"asset": "shrub", "density": 0.18, "min_distance": 2.1, "scale_range": [0.7, 1.1]},
            {"asset": "grass", "density": 0.14, "min_distance": 1.4, "scale_range": [0.5, 0.9]},
            {"asset": "fallen_log", "density": 0.03, "min_distance": 9.0, "scale_range": [0.85, 1.15]},
        ],
        "season_profiles": {
            "summer": {
                "scatter_rules": [
                    {"asset": "boulder", "density": 0.20, "min_distance": 5.0, "scale_range": [0.9, 3.0]},
                    {"asset": "rock_mossy", "density": 0.18, "min_distance": 3.4, "scale_range": [0.8, 1.9]},
                    {"asset": "pine_tree", "density": 0.11, "min_distance": 7.5, "scale_range": [0.9, 1.5]},
                    {"asset": "tree_boundary", "density": 0.05, "min_distance": 8.0, "scale_range": [0.85, 1.3]},
                    {"asset": "shrub", "density": 0.26, "min_distance": 2.0, "scale_range": [0.7, 1.2]},
                    {"asset": "grass", "density": 0.24, "min_distance": 1.3, "scale_range": [0.55, 1.0]},
                    {"asset": "fallen_log", "density": 0.04, "min_distance": 9.0, "scale_range": [0.85, 1.2]},
                ],
            },
            "winter": {
                "scatter_rules": [
                    {"asset": "boulder", "density": 0.18, "min_distance": 5.0, "scale_range": [0.9, 3.0]},
                    {"asset": "rock_mossy", "density": 0.14, "min_distance": 3.8, "scale_range": [0.8, 1.8]},
                    {"asset": "pine_tree", "density": 0.10, "min_distance": 8.0, "scale_range": [0.95, 1.45]},
                    {"asset": "tree_boundary", "density": 0.04, "min_distance": 8.5, "scale_range": [0.85, 1.25]},
                    {"asset": "shrub", "density": 0.10, "min_distance": 2.5, "scale_range": [0.7, 1.0]},
                    {"asset": "grass", "density": 0.06, "min_distance": 1.7, "scale_range": [0.5, 0.85]},
                    {"asset": "fallen_log", "density": 0.03, "min_distance": 9.5, "scale_range": [0.85, 1.2]},
                    {"asset": "snow_patch", "density": 0.18, "min_distance": 5.5, "scale_range": [1.1, 2.8]},
                ],
            },
        },
    },
    "ruined_fortress": {
        "terrain_type": "hills",
        "resolution": 257,
        "height_scale": 12.0,
        "erosion": True,
        "erosion_iterations": 5000,
        "seed": None,
        "scatter_rules": [
            {"asset": "rubble_pile", "density": 0.35, "min_distance": 2.0, "scale_range": [0.5, 1.5]},
            {"asset": "broken_pillar", "density": 0.1, "min_distance": 5.0, "scale_range": [0.8, 1.5]},
            {"asset": "wall_fragment", "density": 0.15, "min_distance": 4.0, "scale_range": [0.6, 1.2]},
            {"asset": "dead_tree", "density": 0.08, "min_distance": 6.0, "scale_range": [0.8, 1.2]},
            {"asset": "iron_fence", "density": 0.05, "min_distance": 7.0, "scale_range": [1.0, 1.0]},
        ],
    },
    "abandoned_village": {
        "terrain_type": "plains",
        "resolution": 257,
        "height_scale": 6.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "collapsed_roof", "density": 0.15, "min_distance": 6.0, "scale_range": [0.8, 1.2]},
            {"asset": "broken_cart", "density": 0.08, "min_distance": 8.0, "scale_range": [0.8, 1.0]},
            {"asset": "barrel", "density": 0.2, "min_distance": 3.0, "scale_range": [0.6, 1.0]},
            {"asset": "crate", "density": 0.2, "min_distance": 3.0, "scale_range": [0.5, 0.9]},
            {"asset": "weed_patch", "density": 0.3, "min_distance": 2.0, "scale_range": [0.4, 1.0]},
        ],
    },
    "veil_crack_zone": {
        "terrain_type": "chaotic",
        "resolution": 257,
        "height_scale": 20.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "crystal_shard", "density": 0.3, "min_distance": 2.0, "scale_range": [0.3, 2.0]},
            {"asset": "void_tendril", "density": 0.1, "min_distance": 5.0, "scale_range": [0.5, 1.5]},
            {"asset": "floating_rock", "density": 0.15, "min_distance": 4.0, "scale_range": [0.5, 3.0]},
            {"asset": "corruption_pool", "density": 0.08, "min_distance": 8.0, "scale_range": [1.0, 2.0]},
        ],
    },
    "underground_dungeon": {
        "terrain_type": "flat",
        "resolution": 257,
        "height_scale": 2.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "stalagmite", "density": 0.15, "min_distance": 3.0, "scale_range": [0.5, 1.5]},
            {"asset": "bone_pile", "density": 0.1, "min_distance": 4.0, "scale_range": [0.3, 0.8]},
            {"asset": "cobweb", "density": 0.2, "min_distance": 2.0, "scale_range": [0.5, 1.0]},
            {"asset": "torch_sconce", "density": 0.05, "min_distance": 8.0, "scale_range": [1.0, 1.0]},
        ],
    },
    "sacred_shrine": {
        "terrain_type": "plains",
        "resolution": 257,
        "height_scale": 4.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "stone_lantern", "density": 0.1, "min_distance": 5.0, "scale_range": [0.8, 1.2]},
            {"asset": "offering_bowl", "density": 0.08, "min_distance": 6.0, "scale_range": [0.6, 1.0]},
            {"asset": "prayer_flag", "density": 0.12, "min_distance": 4.0, "scale_range": [0.8, 1.0]},
            {"asset": "moss_patch", "density": 0.25, "min_distance": 2.0, "scale_range": [0.5, 1.5]},
            {"asset": "cherry_blossom", "density": 0.06, "min_distance": 7.0, "scale_range": [1.0, 1.8]},
        ],
    },
    "battlefield": {
        "terrain_type": "hills",
        "resolution": 257,
        "height_scale": 8.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "broken_weapon", "density": 0.3, "min_distance": 2.0, "scale_range": [0.5, 1.0]},
            {"asset": "shield_fragment", "density": 0.2, "min_distance": 2.5, "scale_range": [0.4, 0.8]},
            {"asset": "bone_pile", "density": 0.15, "min_distance": 3.0, "scale_range": [0.5, 1.2]},
            {"asset": "banner_torn", "density": 0.05, "min_distance": 8.0, "scale_range": [1.0, 1.5]},
            {"asset": "crater", "density": 0.08, "min_distance": 6.0, "scale_range": [1.0, 2.0]},
        ],
    },
    "cemetery": {
        "terrain_type": "flat",
        "resolution": 257,
        "height_scale": 3.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "gravestone", "density": 0.5, "min_distance": 2.0, "scale_range": [0.8, 1.2]},
            {"asset": "dead_tree", "density": 0.08, "min_distance": 8.0, "scale_range": [1.0, 2.0]},
            {"asset": "iron_fence", "density": 0.1, "min_distance": 3.0, "scale_range": [1.0, 1.0]},
            {"asset": "fog_emitter", "density": 0.05, "min_distance": 10.0, "scale_range": [1.0, 1.0]},
        ],
    },
}


_TRIPO_ENVIRONMENT_PROMPTS: dict[str, dict[str, Any]] = {
    "boulder": {
        "prompt": "low poly alpine boulder, grassy summer cliff biome, weathered stone, subtle moss, game ready environment prop",
        "asset_class": "rock_large",
        "suggested_max_vertices": 1800,
    },
    "rock_mossy": {
        "prompt": "low poly mossy cliff rock, alpine summer environment, broken stone slab, game ready scatter prop",
        "asset_class": "rock_medium",
        "suggested_max_vertices": 1200,
    },
    "pine_tree": {
        "prompt": "low poly alpine pine tree, summer mountain pass, readable silhouette, optimized for mass placement",
        "asset_class": "tree_conifer",
        "suggested_max_vertices": 2500,
    },
    "tree_boundary": {
        "prompt": "low poly windswept mountain tree, sparse summer foliage, alpine cliff edge biome, optimized for distance placement",
        "asset_class": "tree_boundary",
        "suggested_max_vertices": 2200,
    },
    "shrub": {
        "prompt": "low poly alpine shrub clump, grassy cliff biome in july, dark green leaves, game ready ground scatter",
        "asset_class": "shrub",
        "suggested_max_vertices": 700,
    },
    "grass": {
        "prompt": "low poly alpine grass tuft cluster, july mountain pass, damp green blades, optimized ground cover",
        "asset_class": "ground_cover",
        "suggested_max_vertices": 240,
    },
    "fallen_log": {
        "prompt": "low poly fallen mountain log, weathered bark, grassy cliff biome, game ready environment scatter prop",
        "asset_class": "deadwood",
        "suggested_max_vertices": 900,
    },
}


def _build_tripo_environment_manifest(
    biome_name: str,
    scatter_rules: list[dict[str, Any]],
    *,
    season: str | None = None,
) -> list[dict[str, Any]]:
    """Build a Tripo-oriented asset manifest from biome scatter rules.

    The manifest gives downstream generators a stable prompt set and an
    explicit per-asset vertex budget, so environment dressing can use
    imported Tripo assets instead of procedural placeholders.
    """
    manifest: list[dict[str, Any]] = []
    for rule in scatter_rules:
        asset_name = str(rule.get("asset", "")).strip()
        prompt_info = _TRIPO_ENVIRONMENT_PROMPTS.get(asset_name)
        if prompt_info is None:
            continue
        manifest.append({
            "asset": asset_name,
            "asset_class": prompt_info["asset_class"],
            "preferred_source": "tripo",
            "prompt": prompt_info["prompt"],
            "biome": biome_name,
            "season": season or "summer",
            "suggested_max_vertices": int(prompt_info["suggested_max_vertices"]),
            "scatter_density": float(rule.get("density", 0.0)),
            "min_distance": float(rule.get("min_distance", 0.0)),
            "scale_range": list(rule.get("scale_range", [1.0, 1.0])),
        })
    return manifest


def _apply_biome_season_profile(
    preset: dict[str, Any],
    season: str | None,
) -> dict[str, Any]:
    """Overlay season-specific biome data when a profile exists."""
    profiles = preset.get("season_profiles")
    if not isinstance(profiles, dict):
        if season:
            preset["season"] = season
        return preset

    resolved_season = season or preset.get("default_season")
    if resolved_season and resolved_season in profiles:
        override = profiles[resolved_season]
        for key, value in override.items():
            preset[key] = value
        preset["season"] = resolved_season
    elif resolved_season:
        preset["season"] = resolved_season
    return preset


def get_vb_biome_preset(
    biome_name: str,
    season: str | None = None,
) -> dict | None:
    """Return a copy of the VB biome preset for *biome_name*, or None.

    The returned dict contains terrain generation parameters (terrain_type,
    resolution, height_scale, erosion, erosion_iterations, seed) and
    scatter_rules for post-terrain vegetation/prop placement.

    Pure logic -- no bpy dependency.
    """
    preset = VB_BIOME_PRESETS.get(biome_name)
    if preset is None:
        return None
    # Return a deep-ish copy so callers can mutate without affecting the preset
    import copy
    resolved = copy.deepcopy(preset)
    resolved = _apply_biome_season_profile(resolved, season)
    if (
        "scatter_rules" in resolved
        and "tripo_asset_manifest" not in resolved
    ):
        resolved["tripo_asset_manifest"] = _build_tripo_environment_manifest(
            biome_name,
            resolved.get("scatter_rules", []),
            season=resolved.get("season") or season,
        )
    return resolved


def _validate_terrain_params(params: dict) -> dict:
    """Validate and normalize terrain generation parameters.

    Raises ValueError for invalid parameters. Returns normalized dict.
    Pure logic -- no bpy dependency.
    """
    resolution = params.get("resolution", 257)
    terrain_type = params.get("terrain_type", "mountains")
    erosion = params.get("erosion", "none")

    if resolution > _MAX_RESOLUTION:
        raise ValueError(
            f"Resolution {resolution} exceeds maximum {_MAX_RESOLUTION}. "
            f"Use resolution <= {_MAX_RESOLUTION} to avoid memory issues."
        )
    if resolution < 3:
        raise ValueError(
            f"Resolution {resolution} is too small. Minimum is 3."
        )

    if terrain_type not in _VALID_TERRAIN_TYPES:
        raise ValueError(
            f"Unknown terrain_type '{terrain_type}'. "
            f"Valid types: {sorted(_VALID_TERRAIN_TYPES)}"
        )

    if erosion not in _VALID_EROSION_MODES:
        raise ValueError(
            f"Unknown erosion mode '{erosion}'. "
            f"Valid modes: {sorted(_VALID_EROSION_MODES)}"
        )

    return {
        "name": params.get("name", "Terrain"),
        "resolution": resolution,
        "terrain_type": terrain_type,
        "scale": params.get("scale", 100.0),
        "height_scale": params.get("height_scale", 20.0),
        "seed": params.get("seed", 0),
        "octaves": params.get("octaves"),
        "persistence": params.get("persistence"),
        "lacunarity": params.get("lacunarity"),
        "erosion": erosion,
        "erosion_iterations": params.get("erosion_iterations", 5000),
    }


def _resolve_terrain_tile_params(params: dict) -> dict[str, Any]:
    """Validate and normalize tiled terrain generation parameters."""
    tile_x = int(params.get("tile_x", 0))
    tile_y = int(params.get("tile_y", 0))
    cell_size = float(params.get("cell_size", 1.0))
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")

    tile_size = params.get("tile_size")
    resolution = params.get("resolution")
    if tile_size is None and resolution is None:
        tile_size = 256
        resolution = tile_size + 1
    elif tile_size is None:
        resolution = int(resolution)
        tile_size = resolution - 1
    elif resolution is None:
        tile_size = int(tile_size)
        resolution = tile_size + 1
    else:
        tile_size = int(tile_size)
        resolution = int(resolution)
        if resolution != tile_size + 1:
            raise ValueError(
                "resolution must equal tile_size + 1 for tiled terrain generation"
            )

    if tile_size < 1:
        raise ValueError("tile_size must be positive")
    if resolution < 2:
        raise ValueError("resolution must be at least 2")

    terrain_size = float(tile_size * cell_size)
    world_origin_x = float(
        params.get("world_origin_x", tile_x * terrain_size)
    )
    world_origin_y = float(
        params.get("world_origin_y", tile_y * terrain_size)
    )

    name = params.get("name", f"Terrain_{tile_x}_{tile_y}")
    return {
        "name": name,
        "tile_x": tile_x,
        "tile_y": tile_y,
        "tile_size": tile_size,
        "resolution": resolution,
        "cell_size": cell_size,
        "world_origin_x": world_origin_x,
        "world_origin_y": world_origin_y,
        "terrain_size": terrain_size,
        "object_location": (
            world_origin_x + terrain_size / 2.0,
            world_origin_y + terrain_size / 2.0,
            0.0,
        ),
    }


def _export_heightmap_raw(
    heightmap: np.ndarray,
    flip_vertical: bool = True,
    value_range: tuple[float, float] | None = None,
) -> bytes:
    """Convert a heightmap to 16-bit little-endian RAW bytes.

    Pure logic -- no file I/O. Returns raw bytes suitable for writing
    to a .raw file for Unity Terrain import.

    Parameters
    ----------
    heightmap : np.ndarray
        2D array of height values.
    flip_vertical : bool
        Flip rows for Unity coordinate system compatibility.
    value_range : tuple[float, float] | None
        Optional shared export range ``(min, max)`` used to normalize heights.
        When omitted, the input array's local min/max are used.

    Returns
    -------
    bytes
        16-bit unsigned little-endian binary data.
    """
    hmap = heightmap.astype(np.float64).copy()

    # Normalize to [0, 1]
    if value_range is not None:
        hmin, hmax = float(value_range[0]), float(value_range[1])
    else:
        hmin, hmax = float(hmap.min()), float(hmap.max())
    if hmax - hmin > 1e-10:
        hmap = np.clip((hmap - hmin) / (hmax - hmin), 0.0, 1.0)
    else:
        hmap = np.zeros_like(hmap)

    if flip_vertical:
        hmap = np.flipud(hmap)

    # Convert to uint16 (0-65535)
    hmap_u16 = (hmap * 65535).astype(np.uint16)

    return hmap_u16.tobytes()


def _export_splatmap_raw(
    splatmap: np.ndarray,
    flip_vertical: bool = True,
) -> bytes:
    """Convert a 4-channel splatmap to 8-bit RGBA RAW bytes."""
    weights = np.asarray(splatmap, dtype=np.float64).copy()
    if weights.ndim != 3 or weights.shape[2] < 4:
        raise ValueError("splatmap must be a 3D array with at least 4 channels")

    rgba = weights[:, :, :4]
    totals = rgba.sum(axis=2, keepdims=True)
    rgba = np.divide(rgba, np.where(totals > 1e-9, totals, 1.0))
    rgba = np.clip(rgba, 0.0, 1.0)

    if flip_vertical:
        rgba = np.flipud(rgba)

    rgba_u8 = (rgba * 255).astype(np.uint8)
    return rgba_u8.tobytes()


def _export_world_tile_artifacts(
    *,
    export_dir: str | Path,
    tile_name: str,
    heightmap: np.ndarray,
    splatmap: np.ndarray | None = None,
    flip_vertical: bool = True,
    height_range: tuple[float, float] | None = None,
) -> dict[str, str]:
    """Write world-tile RAW artifacts and return their file paths."""
    output_dir = Path(export_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, str] = {}
    heightmap_path = output_dir / f"{tile_name}_heightmap.raw"
    heightmap_path.write_bytes(
        _export_heightmap_raw(
            heightmap,
            flip_vertical=flip_vertical,
            value_range=height_range,
        )
    )
    result["heightmap_path"] = str(heightmap_path)

    if splatmap is not None:
        alphamap_path = output_dir / f"{tile_name}_alphamap.raw"
        alphamap_path.write_bytes(_export_splatmap_raw(splatmap, flip_vertical=flip_vertical))
        result["alphamap_path"] = str(alphamap_path)

    return result


def _resolve_height_range(
    params: dict,
    heightmap: np.ndarray,
    *,
    allow_local_fallback: bool = True,
) -> tuple[float, float] | None:
    """Resolve a consistent height range for splatmap normalization.

    Returns ``None`` when the caller did not provide an explicit range
    and ``allow_local_fallback=False``. This is critical for tiled-world
    exports: if every tile were allowed to fall back to its own local
    min/max, each tile would normalize independently and produce visible
    seams in Unity. Tiled exports must either supply an explicit world
    range via ``height_range`` / ``height_range_min/max`` or accept that
    this function will return ``None`` and force the caller to handle
    the missing range deliberately.

    Callers that want the legacy behavior (local min/max fallback) pass
    ``allow_local_fallback=True`` (the default).
    """
    height_range = params.get("height_range")
    if height_range is not None:
        if isinstance(height_range, (list, tuple)) and len(height_range) >= 2:
            return float(height_range[0]), float(height_range[1])
        raise ValueError("height_range must be a 2-item sequence when provided")

    height_range_min = params.get("height_range_min")
    height_range_max = params.get("height_range_max")
    if height_range_min is not None and height_range_max is not None:
        return float(height_range_min), float(height_range_max)

    if not allow_local_fallback:
        return None

    hmap = np.asarray(heightmap, dtype=np.float64)
    if hmap.size == 0:
        return 0.0, 1.0
    return float(hmap.min()), float(hmap.max())


def _resolve_export_height_range(
    params: dict,
    heightmap: np.ndarray,
) -> tuple[float, float] | None:
    """Resolve an optional shared export range for heightmap RAW output.

    Tiled worlds demand a SHARED range across all tiles so the exported
    16-bit RAW heightmaps line up at Unity's tile boundaries. If the
    caller set ``tiled_world`` / ``use_global_height_range`` without an
    explicit range, we must NOT fall back to this tile's local min/max
    — that is the root cause of the per-tile seam bug flagged by the
    Gemini + GPT-5.4 consensus review.
    """
    if params.get("tiled_world") or params.get("use_global_height_range"):
        resolved = _resolve_height_range(
            params, heightmap, allow_local_fallback=False
        )
        if resolved is None:
            raise ValueError(
                "tiled_world / use_global_height_range requires an explicit "
                "'height_range' (or 'height_range_min' + 'height_range_max') "
                "parameter. Falling back to per-tile min/max would normalize "
                "each tile independently and create visible seams in Unity."
            )
        return resolved

    # Non-tiled export path — only return an explicit range when one is
    # present; otherwise the caller may skip height-range metadata.
    return _resolve_height_range(params, heightmap, allow_local_fallback=False)


def _terrain_grid_to_world_xy(
    row: int,
    col: int,
    *,
    rows: int,
    cols: int,
    terrain_size: float | None = None,
    terrain_width: float | None = None,
    terrain_height: float | None = None,
    terrain_origin_x: float,
    terrain_origin_y: float,
) -> tuple[float, float]:
    """Convert a terrain grid cell to a world-space XY position.

    ``terrain_origin_*`` is the terrain object's world-space center.
    """
    if rows < 2 or cols < 2:
        return terrain_origin_x, terrain_origin_y

    width = float(terrain_width if terrain_width is not None else terrain_size if terrain_size is not None else 0.0)
    height = float(terrain_height if terrain_height is not None else terrain_size if terrain_size is not None else 0.0)
    width = max(width, 1e-9)
    height = max(height, 1e-9)

    x = terrain_origin_x + (col / max(cols - 1, 1)) * width - width * 0.5
    y = terrain_origin_y + (row / max(rows - 1, 1)) * height - height * 0.5
    return x, y


def _resolve_water_path_points(
    *,
    path_points_raw: Any,
    terrain_origin_x: float,
    terrain_origin_y: float,
    fallback_depth: float,
    water_level: float,
) -> list[tuple[float, float, float]]:
    """Resolve explicit or fallback water spline points in world space.

    Every returned point is a guaranteed 3-tuple (x, y, z). Explicit
    ``path_points_raw`` entries may be supplied as 2D (x, y) pairs —
    in which case Z is filled from ``water_level`` — or 3D (x, y, z)
    triples. Any other arity raises ``ValueError`` so callers fail fast
    rather than sending half-initialized tuples into downstream mesh
    generation (Gemini consensus finding).
    """
    if path_points_raw and len(path_points_raw) >= 2:
        result: list[tuple[float, float, float]] = []
        for i, pt in enumerate(path_points_raw):
            try:
                pt_seq = list(pt)
            except TypeError as exc:
                raise ValueError(
                    f"path_points[{i}] is not iterable: {pt!r}"
                ) from exc
            if len(pt_seq) == 2:
                x_val, y_val = float(pt_seq[0]), float(pt_seq[1])
                z_val = float(water_level)
            elif len(pt_seq) >= 3:
                x_val = float(pt_seq[0])
                y_val = float(pt_seq[1])
                z_val = float(pt_seq[2])
            else:
                raise ValueError(
                    f"path_points[{i}] must have 2 (x,y) or 3 (x,y,z) "
                    f"components, got {len(pt_seq)}: {pt!r}"
                )
            result.append((x_val, y_val, z_val))
        return result

    return [
        (terrain_origin_x, terrain_origin_y - fallback_depth / 2.0, water_level),
        (terrain_origin_x, terrain_origin_y + fallback_depth / 2.0, water_level),
    ]


def _estimate_tile_height_range(
    terrain_type: str,
    *,
    octaves: int | None = None,
    persistence: float | None = None,
) -> tuple[float, float]:
    """Estimate a deterministic height range for standalone tile exports."""
    preset = TERRAIN_PRESETS.get(terrain_type, TERRAIN_PRESETS["mountains"])
    octaves = int(octaves if octaves is not None else preset["octaves"])
    persistence = float(
        persistence if persistence is not None else preset["persistence"]
    )
    amplitude = _theoretical_max_amplitude(octaves, persistence)
    amplitude *= float(preset.get("amplitude_scale", 1.0))
    post = str(preset.get("post_process", "none"))

    if post in ("power", "step"):
        return (0.0, 1.0)
    if post == "crater":
        crater_depth = float(preset.get("crater_depth", 0.4))
        return (-0.3 * amplitude - crater_depth, 0.7 + 0.3 * amplitude)
    if post == "canyon":
        ridge_strength = float(preset.get("ridge_strength", 0.7))
        return (-amplitude * (1.0 - ridge_strength), 1.0)
    return (-amplitude, amplitude)


def _create_terrain_mesh_from_heightmap(
    *,
    name: str,
    heightmap: np.ndarray,
    terrain_size: float,
    height_scale: float,
    seed: int,
    terrain_type: str,
    object_location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    cliff_overlays_enabled: bool = True,
    cliff_threshold_deg: float = 60.0,
) -> dict[str, Any]:
    """Create a terrain mesh object from a heightmap and optional cliff overlays."""
    rows, cols = heightmap.shape

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Create UV layer BEFORE create_grid so calc_uvs has somewhere to write.
    # Without this, calc_uvs=True silently produces nothing (verified bug).
    uv_layer = bm.loops.layers.uv.new("UVMap")

    bmesh.ops.create_grid(
        bm,
        x_segments=cols - 1,
        y_segments=rows - 1,
        size=terrain_size / 2.0,
        calc_uvs=True,
    )

    bm.verts.ensure_lookup_table()

    # Set vertex Z from heightmap using bilinear interpolation for smooth terrain
    for vert in bm.verts:
        u = (vert.co.x + terrain_size / 2.0) / terrain_size
        v = (vert.co.y + terrain_size / 2.0) / terrain_size
        col_f = u * (cols - 1)
        row_f = v * (rows - 1)
        c0 = max(0, min(int(col_f), cols - 2))
        r0 = max(0, min(int(row_f), rows - 2))
        c1 = c0 + 1
        r1 = r0 + 1
        cf = col_f - c0
        rf = row_f - r0
        h00 = float(heightmap[r0, c0])
        h10 = float(heightmap[r0, c1])
        h01 = float(heightmap[r1, c0])
        h11 = float(heightmap[r1, c1])
        h = (
            h00 * (1 - cf) * (1 - rf)
            + h10 * cf * (1 - rf)
            + h01 * (1 - cf) * rf
            + h11 * cf * rf
        )
        vert.co.z = h * height_scale

    bm.to_mesh(mesh)
    vertex_count = len(bm.verts)
    bm.free()

    if hasattr(mesh, "polygons"):
        for poly in mesh.polygons:
            poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    obj.location = object_location
    bpy.context.collection.objects.link(obj)

    cliff_placements: list[dict[str, Any]] = []
    if cliff_overlays_enabled:
        from ._terrain_depth import detect_cliff_edges, generate_cliff_face_mesh

        cliff_placements = detect_cliff_edges(
            heightmap,
            slope_threshold_deg=cliff_threshold_deg,
            min_cluster_size=4,
            terrain_size=terrain_size,
            height_scale=height_scale,
        )
        for i, cp in enumerate(cliff_placements):
            cliff_mesh_spec = generate_cliff_face_mesh(
                width=cp["width"],
                height=cp["height"],
                seed=seed + i + 1000,
            )
            cliff_mesh = bpy.data.meshes.new(f"{name}_Cliff_{i}")
            cliff_bm = bmesh.new()
            for vert_data in cliff_mesh_spec["vertices"]:
                cliff_bm.verts.new(vert_data)
            cliff_bm.verts.ensure_lookup_table()
            for face_data in cliff_mesh_spec["faces"]:
                try:
                    cliff_bm.faces.new([cliff_bm.verts[vi] for vi in face_data])
                except (ValueError, IndexError):
                    pass
            cliff_bm.to_mesh(cliff_mesh)
            cliff_bm.free()

            cliff_obj = bpy.data.objects.new(f"{name}_Cliff_{i}", cliff_mesh)
            bpy.context.collection.objects.link(cliff_obj)
            # --- Parent first, THEN set transform ---
            # The legacy order (location → parent) silently offset cliffs
            # on non-origin tiles: Blender's Python parent assignment
            # does not auto-adjust matrix_parent_inverse, so a world-space
            # location set before parenting was reinterpreted as local
            # after parenting and the visual world position drifted by
            # whatever the parent's world offset was. The fix is to
            # establish the parent relationship first with
            # ``matrix_parent_inverse`` forced to identity, then write the
            # transform — which is now unambiguously terrain-local. The
            # positions returned by ``detect_cliff_edges`` are already
            # in terrain-local coordinates (grid-center mapped to
            # [-tw/2, +tw/2]) and Z is already multiplied by
            # ``height_scale`` inside ``detect_cliff_edges`` — no further
            # scaling here.
            cliff_obj.parent = obj
            mpi = getattr(cliff_obj, "matrix_parent_inverse", None)
            if mpi is not None and hasattr(mpi, "identity"):
                mpi.identity()
            cliff_obj.location = (
                cp["position"][0],
                cp["position"][1],
                cp["position"][2],
            )
            cliff_obj.rotation_euler = tuple(cp["rotation"])

    return {
        "object": obj,
        "name": obj.name,
        "vertex_count": vertex_count,
        "cliff_overlays": len(cliff_placements),
        "terrain_size": terrain_size,
        "object_location": tuple(obj.location),
        "terrain_type": terrain_type,
    }


# ---------------------------------------------------------------------------
# Handler: generate_terrain
# ---------------------------------------------------------------------------

def handle_generate_terrain(params: dict) -> dict:
    """Generate a terrain mesh from noise heightmap with optional erosion.

    Params:
        name (str, default "Terrain"): Object name.
        resolution (int, default 257): Grid resolution (vertices per side).
        terrain_type (str, default "mountains"): One of 8 terrain presets,
            or a VeilBreakers biome name (e.g. "thornwood_forest").
            When a biome name is given, its preset parameters are applied
            as defaults, overrideable by explicit params.
        scale (float, default 100.0): Noise sampling scale.
        height_scale (float, default 20.0): Vertical scale multiplier.
        seed (int, default 0): Random seed.
        octaves, persistence, lacunarity: Override preset values.
        erosion (str, default "none"): none|hydraulic|thermal|both.
        erosion_iterations (int, default 5000): Erosion iteration count.

    Returns dict with: name, vertex_count, terrain_type, resolution,
        height_scale, erosion_applied, and optionally biome_preset
        and scatter_rules when a VB biome preset was used.
    """
    # Check if terrain_type is a VB biome preset name
    biome_preset = get_vb_biome_preset(
        params.get("terrain_type", ""),
        season=params.get("season"),
    )
    if biome_preset is not None:
        biome_name = params["terrain_type"]
        # Build effective params: preset defaults, overridden by explicit params
        effective = {}
        effective["terrain_type"] = biome_preset["terrain_type"]
        effective["resolution"] = biome_preset["resolution"]
        effective["height_scale"] = biome_preset["height_scale"]
        if biome_preset.get("erosion"):
            effective["erosion"] = "hydraulic"
            effective["erosion_iterations"] = biome_preset.get("erosion_iterations", 5000)
        else:
            effective["erosion"] = "none"
        # Explicit params override preset defaults (except terrain_type which
        # was the biome name -- we already resolved the real terrain_type).
        # Note: preset seed is intentionally NOT applied -- caller's seed
        # (or downstream default) always takes precedence.
        for key in ("name", "resolution", "height_scale", "scale", "seed",
                     "octaves", "persistence", "lacunarity", "erosion",
                     "erosion_iterations"):
            if key in params and key != "terrain_type":
                effective[key] = params[key]
        # Keep the original terrain_type param out so validation uses the
        # resolved terrain_type from the biome preset
        params = effective

    logger.info("Generating terrain (type=%s)", params.get("terrain_type", "mountains"))
    validated = _validate_terrain_params(params)

    name = validated["name"]
    resolution = validated["resolution"]
    terrain_type = validated["terrain_type"]
    scale = validated["scale"]
    height_scale = validated["height_scale"]
    seed = validated["seed"]
    erosion = validated["erosion"]
    erosion_iters = validated["erosion_iterations"]

    # Auto-scale erosion: minimum 150K droplets for AAA-quality river channels
    # and natural-looking drainage (Skyrim/Valhalla uses 150K+ for visible features)
    if erosion in ("hydraulic", "both") and erosion_iters < 150000:
        erosion_iters = max(150000, resolution * resolution // 2)

    # Domain warp params (organic terrain features)
    warp_strength = params.get("warp_strength", 0.4)  # default organic
    warp_scale = params.get("warp_scale", 0.5)

    # Generate heightmap
    heightmap = generate_heightmap(
        width=resolution,
        height=resolution,
        scale=scale,
        octaves=validated["octaves"],
        persistence=validated["persistence"],
        lacunarity=validated["lacunarity"],
        seed=seed,
        terrain_type=terrain_type,
        warp_strength=warp_strength,
        warp_scale=warp_scale,
    )

    # Apply erosion
    erosion_applied = False
    if erosion in ("hydraulic", "both") or erosion in ("thermal", "both"):
        erosion_result = erode_world_heightmap(
            heightmap,
            hydraulic_iterations=erosion_iters if erosion in ("hydraulic", "both") else 0,
            thermal_iterations=max(erosion_iters // 50, 5) if erosion in ("thermal", "both") else 0,
            seed=seed,
        )
        heightmap = erosion_result["heightmap"]
        erosion_applied = True

    # Apply flatten zones for building foundations (MESH-05)
    flatten_zones = params.get("flatten_zones", None)
    if flatten_zones:
        from .terrain_advanced import flatten_multiple_zones
        heightmap = flatten_multiple_zones(heightmap, flatten_zones)

    # Compute moisture map from flow accumulation (for splatmap painting)
    moisture_map = None
    if erosion_applied:
        from .terrain_advanced import compute_flow_map
        flow_result = compute_flow_map(heightmap)
        flow_acc = np.asarray(flow_result["flow_accumulation"], dtype=np.float64)
        # Normalize flow accumulation to [0, 1] using log scale
        log_flow = np.log1p(flow_acc)
        fa_max = log_flow.max()
        if fa_max > 0:
            moisture_map = log_flow / fa_max
        else:
            moisture_map = np.zeros_like(heightmap)

    terrain_size = scale
    terrain_result = _create_terrain_mesh_from_heightmap(
        name=name,
        heightmap=heightmap,
        terrain_size=terrain_size,
        height_scale=height_scale,
        seed=seed,
        terrain_type=terrain_type,
        object_location=(0.0, 0.0, 0.0),
        cliff_overlays_enabled=_parse_bool(params.get("cliff_overlays", True)),
        cliff_threshold_deg=params.get("cliff_threshold_deg", 60.0),
    )

    result = {
        "name": terrain_result["name"],
        "vertex_count": terrain_result["vertex_count"],
        "terrain_type": terrain_type,
        "resolution": resolution,
        "height_scale": height_scale,
        "erosion_applied": erosion_applied,
        "cliff_overlays": terrain_result["cliff_overlays"],
        "flatten_zones_applied": len(flatten_zones) if flatten_zones else 0,
        "has_moisture_map": moisture_map is not None,
    }
    if biome_preset is not None:
        result["biome_preset"] = biome_name
        result["scatter_rules"] = biome_preset.get("scatter_rules", [])
    return result


# ---------------------------------------------------------------------------
# Handler: generate_terrain_tile
# ---------------------------------------------------------------------------

def handle_generate_terrain_tile(params: dict) -> dict:
    """Generate a single world-space terrain tile."""
    logger.info("Generating tiled terrain")

    resolved = _resolve_terrain_tile_params(params)
    name = resolved["name"]
    tile_x = resolved["tile_x"]
    tile_y = resolved["tile_y"]
    tile_size = resolved["tile_size"]
    resolution = resolved["resolution"]
    cell_size = resolved["cell_size"]
    world_origin_x = resolved["world_origin_x"]
    world_origin_y = resolved["world_origin_y"]
    terrain_size = resolved["terrain_size"]
    object_location = resolved["object_location"]

    terrain_type = params.get("terrain_type", "mountains")
    scale = float(params.get("scale", 100.0))
    height_scale = float(params.get("height_scale", 20.0))
    seed = int(params.get("seed", 0))
    octaves = params.get("octaves")
    persistence = params.get("persistence")
    lacunarity = params.get("lacunarity")
    erosion = params.get("erosion", "none")
    erosion_iters = int(params.get("erosion_iterations", 5000))
    warp_strength = float(params.get("warp_strength", 0.4))
    warp_scale = float(params.get("warp_scale", 0.5))
    world_center_x = params.get("world_center_x")
    world_center_y = params.get("world_center_y")
    cliff_overlays_enabled = _parse_bool(params.get("cliff_overlays", True))
    cliff_threshold = float(params.get("cliff_threshold_deg", 60.0))
    erosion_margin = max(0, int(params.get("erosion_margin", 0)))
    biome_name = params.get("biome_name", params.get("terrain_type", "thornwood_forest"))
    export_splatmaps = _parse_bool(params.get("export_splatmaps", True))
    export_root = Path(
        params.get("export_dir")
        or params.get("output_dir")
        or Path("Temp") / "VB_TerrainExports" / name
    )

    world_width = tile_size + 1 + (2 * erosion_margin)
    world_height = tile_size + 1 + (2 * erosion_margin)
    padded_origin_x = world_origin_x - erosion_margin * cell_size
    padded_origin_y = world_origin_y - erosion_margin * cell_size

    heightmap = generate_world_heightmap(
        width=world_width,
        height=world_height,
        scale=scale,
        world_origin_x=padded_origin_x,
        world_origin_y=padded_origin_y,
        cell_size=cell_size,
        seed=seed,
        terrain_type=terrain_type,
        normalize=False,
        warp_strength=warp_strength,
        warp_scale=warp_scale,
        octaves=octaves,
        persistence=persistence,
        lacunarity=lacunarity,
        world_center_x=world_center_x,
        world_center_y=world_center_y,
    )

    erosion_applied = False
    if erosion in ("hydraulic", "both"):
        heightmap = erode_world_heightmap(
            heightmap,
            hydraulic_iterations=erosion_iters,
            thermal_iterations=0,
            seed=seed,
        )["heightmap"]
        erosion_applied = True
    if erosion in ("thermal", "both"):
        heightmap = erode_world_heightmap(
            heightmap,
            hydraulic_iterations=0,
            thermal_iterations=max(erosion_iters // 50, 5),
            seed=seed,
        )["heightmap"]
        erosion_applied = True

    if erosion_margin > 0:
        heightmap = heightmap[
            erosion_margin : erosion_margin + tile_size + 1,
            erosion_margin : erosion_margin + tile_size + 1,
        ]

    flatten_zones = params.get("flatten_zones", None)
    if flatten_zones:
        from .terrain_advanced import flatten_multiple_zones
        heightmap = flatten_multiple_zones(heightmap, flatten_zones)

    # Ask _resolve_height_range without local fallback; fall back to the
    # per-terrain-type estimator only when no explicit range was supplied.
    # This is clean "single source of truth" for range resolution and fixes
    # the duplicate key-presence check (Gemini consensus finding).
    height_range = _resolve_height_range(
        params, heightmap, allow_local_fallback=False
    )
    if height_range is None:
        height_range = _estimate_tile_height_range(
            terrain_type,
            octaves=octaves,
            persistence=persistence,
        )

    moisture_map = None
    splatmap = None
    if export_splatmaps:
        from .terrain_advanced import compute_flow_map

        flow_result = compute_flow_map(heightmap)
        flow_acc = np.asarray(flow_result["flow_accumulation"], dtype=np.float64)
        log_flow = np.log1p(flow_acc)
        fa_max = float(log_flow.max())
        if fa_max > 0:
            moisture_map = log_flow / fa_max
        else:
            moisture_map = np.zeros_like(heightmap)

        splatmap = compute_world_splatmap_weights(
            heightmap,
            biome_name=biome_name,
            cell_size=cell_size,
            moisture_map=moisture_map,
            height_range=height_range,
        )

    terrain_result = _create_terrain_mesh_from_heightmap(
        name=name,
        heightmap=heightmap,
        terrain_size=terrain_size,
        height_scale=height_scale,
        seed=seed,
        terrain_type=terrain_type,
        object_location=object_location,
        cliff_overlays_enabled=cliff_overlays_enabled,
        cliff_threshold_deg=cliff_threshold,
    )

    result = {
        "name": terrain_result["name"],
        "tile_x": tile_x,
        "tile_y": tile_y,
        "tile_size": tile_size,
        "resolution": resolution,
        "cell_size": cell_size,
        "world_origin_x": world_origin_x,
        "world_origin_y": world_origin_y,
        "terrain_type": terrain_type,
        "height_scale": height_scale,
        "vertex_count": terrain_result["vertex_count"],
        "cliff_overlays": terrain_result["cliff_overlays"],
        "erosion_applied": erosion_applied,
        "erosion_margin": erosion_margin,
        "flatten_zones_applied": len(flatten_zones) if flatten_zones else 0,
        "object_location": terrain_result["object_location"],
        "terrain_size": terrain_size,
        "grid_x": tile_x,
        "grid_y": tile_y,
        "position": [world_origin_x, 0.0, world_origin_y],
        "size": [terrain_size, height_scale, terrain_size],
        "height_range": [height_range[0], height_range[1]],
        "export_dir": str(export_root),
    }
    if export_splatmaps:
        result.update(
            _export_world_tile_artifacts(
                export_dir=export_root,
                tile_name=name,
                heightmap=heightmap,
                splatmap=splatmap,
                height_range=height_range,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Handler: generate_world_terrain
# ---------------------------------------------------------------------------

def handle_generate_world_terrain(params: dict) -> dict:
    """Compatibility wrapper over tile generation for legacy world-terrain callers."""
    base_name = str(params.get("name", "WorldTerrain"))
    start_tile_x = int(params.get("tile_x", params.get("start_tile_x", 0)))
    start_tile_y = int(params.get("tile_y", params.get("start_tile_y", 0)))
    tiles_x = max(1, int(params.get("tiles_x", params.get("world_tiles_x", 1))))
    tiles_y = max(1, int(params.get("tiles_y", params.get("world_tiles_y", 1))))

    tile_results: list[dict[str, Any]] = []
    for offset_y in range(tiles_y):
        for offset_x in range(tiles_x):
            tile_x = start_tile_x + offset_x
            tile_y = start_tile_y + offset_y
            tile_params = dict(params)
            tile_params["tile_x"] = tile_x
            tile_params["tile_y"] = tile_y
            if tiles_x > 1 or tiles_y > 1:
                tile_params["name"] = f"{base_name}_{tile_x}_{tile_y}"
            else:
                tile_params["name"] = base_name
            tile_results.append(handle_generate_terrain_tile(tile_params))

    if len(tile_results) == 1:
        result = dict(tile_results[0])
        result["compatibility_mode"] = "world_to_tile_wrapper"
        result["deprecated_command"] = True
        return result

    return {
        "name": base_name,
        "deprecated_command": True,
        "compatibility_mode": "world_to_tile_wrapper",
        "tile_count": len(tile_results),
        "tiles_x": tiles_x,
        "tiles_y": tiles_y,
        "tiles": tile_results,
    }


# ---------------------------------------------------------------------------
# Bundle A handler: run_terrain_pass
# ---------------------------------------------------------------------------


def handle_run_terrain_pass(params: dict) -> dict:
    """Run a registered terrain pass via ``TerrainPassController``.

    Required params:
        pass_name (str)  — name of a registered pass (e.g. "macro_world")
        tile_size (int)  — cells per tile edge
        cell_size (float)
        seed (int)

    Optional params:
        tile_x (int=0), tile_y (int=0)
        world_origin_x (float=0.0), world_origin_y (float=0.0)
        region_bounds (dict|list) — BBox for the intent region
        region (dict|list) — BBox for scoped execution
        protected_zones (list[dict])
        scene_read (dict)  — presence signals that scene-read requirement is met
        height (list[list[float]]|np.ndarray) — optional pre-built heightmap
        terrain_type (str), scale (float) — for generating initial height
        erosion_profile (str)
        pipeline (list[str]) — pass sequence
        pass_name=... with pipeline=None runs a single pass

    Default behavior:
        - with ``scene_read``: ``macro_world -> structural_masks -> erosion -> validation_minimal``
        - without ``scene_read``: ``macro_world -> structural_masks -> validation_minimal``

    Returns:
        dict with ``ok``, ``results`` (list of PassResult dicts),
        ``content_hash``, ``populated_channels``.
    """
    # Local imports to avoid circular dependency at module load.
    from . import _terrain_world as _tw
    from .terrain_master_registrar import register_all_terrain_passes
    from .terrain_pipeline import TerrainPassController
    from .terrain_semantics import (
        BBox,
        ProtectedZoneSpec,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    requested_pipeline = params.get("pipeline")
    requested_passes = list(requested_pipeline) if requested_pipeline is not None else []
    if not requested_passes:
        requested_passes = [str(params.get("pass_name", "macro_world"))]

    # Ensure all requested passes are registered even for direct callers
    # importing this module without the handlers package side effects.
    missing_passes = [
        pass_name for pass_name in requested_passes
        if pass_name not in TerrainPassController.PASS_REGISTRY
    ]
    if missing_passes or not TerrainPassController.PASS_REGISTRY:
        register_all_terrain_passes(strict=False)

    tile_size = int(params.get("tile_size", 64))
    cell_size = float(params.get("cell_size", 1.0))
    seed = int(params.get("seed", 0))
    tile_x = int(params.get("tile_x", 0))
    tile_y = int(params.get("tile_y", 0))
    world_origin_x = float(params.get("world_origin_x", 0.0))
    world_origin_y = float(params.get("world_origin_y", 0.0))

    # Resolve region bounds
    def _to_bbox(value: Any) -> Optional[BBox]:
        if value is None:
            return None
        if isinstance(value, BBox):
            return value
        if isinstance(value, dict):
            return BBox(
                min_x=float(value["min_x"]),
                min_y=float(value["min_y"]),
                max_x=float(value["max_x"]),
                max_y=float(value["max_y"]),
            )
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return BBox(
                min_x=float(value[0]),
                min_y=float(value[1]),
                max_x=float(value[2]),
                max_y=float(value[3]),
            )
        raise ValueError(f"region bounds must be dict|list[4]|BBox, got {type(value)}")

    region_bounds = _to_bbox(params.get("region_bounds")) or BBox(
        min_x=world_origin_x,
        min_y=world_origin_y,
        max_x=world_origin_x + tile_size * cell_size,
        max_y=world_origin_y + tile_size * cell_size,
    )
    region = _to_bbox(params.get("region"))

    # Protected zones — reject malformed entries early with a clear error.
    protected_zones: list[ProtectedZoneSpec] = []
    for i, pz in enumerate(params.get("protected_zones", []) or []):
        bounds_raw = pz.get("bounds")
        if bounds_raw is None:
            raise ValueError(
                f"protected_zones[{i}]: 'bounds' is required (dict|list[4]|BBox)"
            )
        bounds = _to_bbox(bounds_raw)
        if bounds is None:
            raise ValueError(
                f"protected_zones[{i}]: 'bounds' must resolve to a BBox, got {bounds_raw!r}"
            )
        protected_zones.append(
            ProtectedZoneSpec(
                zone_id=str(pz.get("zone_id", f"zone_{i}")),
                bounds=bounds,
                kind=str(pz.get("kind", "generic")),
                allowed_mutations=frozenset(pz.get("allowed_mutations", []) or []),
                forbidden_mutations=frozenset(pz.get("forbidden_mutations", []) or []),
                description=str(pz.get("description", "")),
            )
        )

    # Scene read (accept any non-None value as satisfying the requirement)
    scene_read_raw = params.get("scene_read")
    scene_read: Optional[TerrainSceneRead] = None
    if scene_read_raw is not None:
        scene_read = TerrainSceneRead(
            timestamp=float(scene_read_raw.get("timestamp", 0.0)),
            major_landforms=tuple(scene_read_raw.get("major_landforms", ()) or ()),
            focal_point=tuple(scene_read_raw.get("focal_point", (0.0, 0.0, 0.0))),
            hero_features_present=tuple(),
            hero_features_missing=tuple(scene_read_raw.get("hero_features_missing", ()) or ()),
            waterfall_chains=tuple(),
            cave_candidates=tuple(),
            protected_zones_in_region=tuple(z.zone_id for z in protected_zones),
            edit_scope=region or region_bounds,
            success_criteria=tuple(scene_read_raw.get("success_criteria", ()) or ()),
            reviewer=str(scene_read_raw.get("reviewer", "unknown")),
        )

    # Build or accept heightmap
    height_raw = params.get("height")
    if height_raw is not None:
        height = np.asarray(height_raw, dtype=np.float64)
    else:
        from ._terrain_noise import generate_heightmap

        height = np.asarray(
            generate_heightmap(
                tile_size + 1,
                tile_size + 1,
                scale=float(params.get("scale", 100.0)),
                world_origin_x=world_origin_x,
                world_origin_y=world_origin_y,
                cell_size=cell_size,
                seed=seed,
                terrain_type=str(params.get("terrain_type", "mountains")),
                normalize=False,
            ),
            dtype=np.float64,
        )

    mask_stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=cell_size,
        world_origin_x=world_origin_x,
        world_origin_y=world_origin_y,
        tile_x=tile_x,
        tile_y=tile_y,
        height=height,
    )

    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=cell_size,
        protected_zones=tuple(protected_zones),
        erosion_profile=str(params.get("erosion_profile", "temperate")),
        scene_read=scene_read,
    )

    state = TerrainPipelineState(intent=intent, mask_stack=mask_stack)

    # --- Protocol enforcement (Bundle R, Addendum 1.A.2) -------------------
    # Every production mutation handler MUST route through ProtocolGate.
    # Callers that cannot attach a full scene/vantage (unit tests, CLI dev
    # runs) opt out via ``enforce_protocol=False`` in params.
    if _parse_bool(params.get("enforce_protocol", False)):
        from .terrain_protocol import ProtocolGate, ProtocolViolation

        try:
            ProtocolGate.rule_1_observe_before_calculate(state)
            ProtocolGate.rule_2_sync_to_user_viewport(
                state,
                out_of_view_ok=_parse_bool(params.get("out_of_view_ok", True)),
            )
            ProtocolGate.rule_3_lock_reference_empties(state)
            ProtocolGate.rule_4_real_geometry_not_vertex_tricks(params)
            ProtocolGate.rule_5_smallest_diff_per_iteration(
                state,
                cells_affected=int(params.get("cells_affected", 0)),
                objects_affected=int(params.get("objects_affected", 0)),
                bulk_edit=_parse_bool(params.get("bulk_edit", True)),
            )
            ProtocolGate.rule_6_surface_vs_interior_classification(params)
            ProtocolGate.rule_7_plugin_usage(params)
        except ProtocolViolation as exc:
            return {
                "ok": False,
                "error": "protocol_violation",
                "message": str(exc),
            }

    controller = TerrainPassController(state)

    pass_name = params.get("pass_name")
    pipeline = params.get("pipeline")

    composition_hints = params.get("composition_hints") or {}
    unity_export_opt_out = _parse_bool(composition_hints.get("unity_export_opt_out", False))

    if pipeline is None and pass_name is None:
        pipeline = ["macro_world", "structural_masks", "validation_minimal"]
        if scene_read is not None:
            pipeline.insert(2, "erosion")

    if pipeline is not None:
        pipeline = list(pipeline)
        if (
            "validation_full" in pipeline
            and not unity_export_opt_out
            and "prepare_heightmap_raw_u16" not in pipeline
        ):
            insert_at = pipeline.index("validation_full")
            pipeline.insert(insert_at, "prepare_heightmap_raw_u16")

    # F150: try/finally ensures cleanup of leaked bpy meshes/objects on exception
    _leaked_meshes = []
    _leaked_objects = []
    try:
        # Snapshot meshes/objects before pass execution for cleanup tracking
        try:
            _pre_meshes = set(bpy.data.meshes[:])
            _pre_objects = set(bpy.data.objects[:])
        except Exception:
            _pre_meshes = set()
            _pre_objects = set()

        if pipeline is not None:
            results = controller.run_pipeline(
                pass_sequence=pipeline,
                region=region,
                checkpoint=_parse_bool(params.get("checkpoint", False)),
            )
        else:
            results = [
                controller.run_pass(
                    str(pass_name),
                    region=region,
                    checkpoint=_parse_bool(params.get("checkpoint", False)),
                )
            ]
    except Exception:
        # Clean up any meshes/objects created during the failed pass
        try:
            for obj in set(bpy.data.objects[:]) - _pre_objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            for mesh in set(bpy.data.meshes[:]) - _pre_meshes:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass  # best-effort cleanup in exception handler
        raise

    def _serialize(pr) -> dict:
        return {
            "pass_name": pr.pass_name,
            "status": pr.status,
            "duration_seconds": pr.duration_seconds,
            "produced_channels": list(pr.produced_channels),
            "consumed_channels": list(pr.consumed_channels),
            "metrics": pr.metrics,
            "seed_used": pr.seed_used,
            "content_hash_before": pr.content_hash_before,
            "content_hash_after": pr.content_hash_after,
            "issues": [
                {"code": i.code, "severity": i.severity, "message": i.message}
                for i in pr.issues
            ],
        }

    return {
        "ok": all(r.status == "ok" for r in results),
        "results": [_serialize(r) for r in results],
        "content_hash": mask_stack.compute_hash(),
        "populated_channels": sorted(mask_stack.populated_by_pass.keys()),
        "tile_x": tile_x,
        "tile_y": tile_y,
    }


def handle_generate_waterfall(params: dict) -> dict:
    """Generate a waterfall from water-network context when available.

    The legacy terrain-feature mesh generator remains as a compatibility
    fallback, but public terrain-water authoring should supply a heightmap so
    the waterfall is derived from hydrologic context.
    """
    heightmap_raw = params.get("heightmap")
    if heightmap_raw is not None:
        heightmap = np.asarray(heightmap_raw, dtype=np.float64)
        if heightmap.ndim != 2:
            raise ValueError("heightmap must be a 2D array")

        tile_size = int(params.get("tile_size", max(min(heightmap.shape) - 1, 1)))
        cell_size = float(params.get("cell_size", 1.0))
        tile_x = int(params.get("tile_x", 0))
        tile_y = int(params.get("tile_y", 0))
        network = WaterNetwork.from_heightmap(
            heightmap,
            cell_size=cell_size,
            world_origin_x=float(params.get("world_origin_x", 0.0)),
            world_origin_y=float(params.get("world_origin_y", 0.0)),
            tile_size=tile_size,
            min_drainage_area=float(params.get("min_drainage_area", 500.0)),
            river_threshold=float(params.get("river_threshold", 2000.0)),
            lake_min_area=float(params.get("lake_min_area", 100.0)),
            seed=int(params.get("seed", 42)),
        )
        features = network.get_tile_water_features(
            tile_x,
            tile_y,
            tile_size=tile_size,
            cell_size=cell_size,
        )
        waterfalls = features.get("waterfalls", [])
        if not waterfalls:
            raise ValueError("No waterfall candidates were detected in the supplied tile")

        chosen = waterfalls[0]
        fallback = generate_waterfall(
            height=max(float(chosen["drop"]), 1.0),
            width=max(float(chosen["width"]), 1.0),
            pool_radius=max(float(params.get("pool_radius", chosen["width"] * 1.5)), 1.0),
            num_steps=int(params.get("num_steps", 3)),
            has_cave_behind=_parse_bool(params.get("has_cave_behind", True)),
            seed=int(params.get("seed", 42)),
        )
        fallback["authoring_path"] = "water_network_derived"
        fallback["waterfall_feature"] = chosen
        fallback["waterfall_candidates"] = len(waterfalls)
        return fallback

    legacy = generate_waterfall(
        height=params.get("height", 10.0),
        width=params.get("width", 3.0),
        pool_radius=params.get("pool_radius", 4.0),
        num_steps=params.get("num_steps", 3),
        has_cave_behind=params.get("has_cave_behind", True),
        seed=params.get("seed", 42),
    )
    legacy["authoring_path"] = "legacy_geometry_fallback"
    legacy["warning"] = (
        "env_generate_waterfall should be driven from heightmap/water-network "
        "context; this call used legacy geometry fallback."
    )
    return legacy


def handle_stitch_terrain_edges(params: dict) -> dict:
    """Fallback seam stitcher for adjacent Blender terrain meshes."""
    terrain_a_name = params.get("terrain_a") or params.get("terrain_name_a")
    terrain_b_name = params.get("terrain_b") or params.get("terrain_name_b")
    if not terrain_a_name or not terrain_b_name:
        raise ValueError("'terrain_a' and 'terrain_b' are required")

    direction = params.get("direction", "east")
    tolerance = float(params.get("tolerance", 1e-4))

    obj_a = bpy.data.objects.get(terrain_a_name)
    obj_b = bpy.data.objects.get(terrain_b_name)
    if obj_a is None:
        raise ValueError(f"Object not found: {terrain_a_name}")
    if obj_b is None:
        raise ValueError(f"Object not found: {terrain_b_name}")
    if obj_a.type != "MESH" or obj_b.type != "MESH":
        raise ValueError("terrain stitcher requires mesh objects")

    def _edge_vertices(obj, edge: str) -> list[tuple[float, int]]:
        mesh = obj.data
        mesh.calc_loop_triangles()
        xs = [v.co.x for v in mesh.vertices]
        ys = [v.co.y for v in mesh.vertices]
        if not xs or not ys:
            return []
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if edge in ("east", "right"):
            axis_vals = [(v.co.y, idx) for idx, v in enumerate(mesh.vertices) if abs(v.co.x - max_x) <= tolerance]
        elif edge in ("west", "left"):
            axis_vals = [(v.co.y, idx) for idx, v in enumerate(mesh.vertices) if abs(v.co.x - min_x) <= tolerance]
        elif edge in ("north", "top"):
            axis_vals = [(v.co.x, idx) for idx, v in enumerate(mesh.vertices) if abs(v.co.y - max_y) <= tolerance]
        elif edge in ("south", "bottom"):
            axis_vals = [(v.co.x, idx) for idx, v in enumerate(mesh.vertices) if abs(v.co.y - min_y) <= tolerance]
        else:
            raise ValueError("direction must be east, west, north, or south")
        return sorted(axis_vals, key=lambda item: item[0])

    if direction in ("east", "west"):
        edge_a = "east" if direction == "east" else "west"
        edge_b = "west" if direction == "east" else "east"
    else:
        edge_a = "north" if direction == "north" else "south"
        edge_b = "south" if direction == "north" else "north"

    verts_a = _edge_vertices(obj_a, edge_a)
    verts_b = _edge_vertices(obj_b, edge_b)
    if len(verts_a) != len(verts_b):
        raise ValueError("terrain edge vertex counts do not match")
    if not verts_a:
        return {
            "status": "error",
            "message": "no seam vertices found",
            "direction": direction,
        }

    mesh_a = obj_a.data
    mesh_b = obj_b.data
    matched = 0
    max_delta = 0.0
    for (_, idx_a), (_, idx_b) in zip(verts_a, verts_b):
        za = mesh_a.vertices[idx_a].co.z
        zb = mesh_b.vertices[idx_b].co.z
        delta = abs(za - zb)
        max_delta = max(max_delta, delta)
        avg = (za + zb) * 0.5
        mesh_a.vertices[idx_a].co.z = avg
        mesh_b.vertices[idx_b].co.z = avg
        matched += 1

    mesh_a.update()
    mesh_b.update()
    return {
        "status": "success",
        "terrain_a": terrain_a_name,
        "terrain_b": terrain_b_name,
        "direction": direction,
        "matched_vertices": matched,
        "max_delta": max_delta,
    }


# ---------------------------------------------------------------------------
# Handler: paint_terrain
# ---------------------------------------------------------------------------

def handle_paint_terrain(params: dict) -> dict:
    """Auto-paint terrain with biome materials based on slope/altitude rules.

    Params:
        name (str): Existing terrain object name.
        biome_rules (list of dict, optional): Biome rules with name, material,
            min_alt, max_alt, min_slope, max_slope. Defaults to BIOME_RULES.
        height_scale (float, default 20.0): Used to normalize altitude.

    Returns dict with: name, material_count, biome_rules_applied.
    """
    logger.info("Painting terrain biomes")
    name = params.get("name")
    if not name:
        raise ValueError("'name' is required")

    biome_rules = params.get("biome_rules") or BIOME_RULES
    height_scale = params.get("height_scale", 20.0)

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is type '{obj.type}', expected 'MESH'")

    mesh = obj.data

    # Create material slots with proper Base Color from biome rules
    for rule in biome_rules:
        mat_name = rule.get("material", rule["name"])
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            # Apply base_color and roughness from rule if present
            if mat.node_tree:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    base_color = rule.get("base_color")
                    if base_color:
                        bc = list(base_color)
                        while len(bc) < 4:
                            bc.append(1.0)
                        bsdf.inputs["Base Color"].default_value = tuple(bc[:4])
                    roughness = rule.get("roughness")
                    if roughness is not None:
                        bsdf.inputs["Roughness"].default_value = roughness
        mesh.materials.append(mat)

    # Assign faces using bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    for face in bm.faces:
        center = face.calc_center_median()
        altitude = center.z / height_scale if height_scale > 0 else 0.0
        altitude = max(0.0, min(1.0, altitude))

        # Slope from face normal
        slope_rad = math.acos(max(-1.0, min(1.0, face.normal.z)))
        slope_deg = math.degrees(slope_rad)

        # First matching rule wins
        for idx, rule in enumerate(biome_rules):
            min_alt = rule.get("min_alt", 0.0)
            max_alt = rule.get("max_alt", 1.0)
            min_slope = rule.get("min_slope", 0.0)
            max_slope = rule.get("max_slope", 90.0)

            if (min_alt <= altitude <= max_alt
                    and min_slope <= slope_deg <= max_slope):
                face.material_index = idx
                break

    bm.to_mesh(mesh)
    bm.free()

    return {
        "name": obj.name,
        "material_count": len(mesh.materials),
        "biome_rules_applied": len(biome_rules),
    }


# ---------------------------------------------------------------------------
# Handler: carve_river
# ---------------------------------------------------------------------------

def handle_carve_river(params: dict) -> dict:
    """Carve a river channel on an existing terrain mesh.

    Params:
        terrain_name (str): Existing terrain object name.
        source (list of 2 ints): Start grid coordinate [row, col].
        destination (list of 2 ints): End grid coordinate [row, col].
        width (int, default 2): Channel width in cells.
        depth (float, default 0.05): Channel depth.
        seed (int, default 0): Random seed.

    Returns dict with: name, path_length, depth.
    """
    logger.info("Carving river on terrain")
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    source = tuple(params.get("source", [0, 0]))
    destination = tuple(params.get("destination", [0, 0]))
    width = params.get("width", 2)
    depth = params.get("depth", 0.05)
    seed = params.get("seed", 0)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    # Extract heightmap from mesh vertex Z
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # WORLD-004: Detect actual grid dimensions (robust to non-square terrain)
    rows, cols = _detect_grid_dims(bm)

    # Extract heights
    heights = np.array([v.co.z for v in bm.verts])
    height_scale = heights.max() if heights.max() > 0 else 1.0
    heightmap = (heights / height_scale).reshape(rows, cols)

    # Carve river
    path, carved = carve_river_path(
        heightmap, source=source, dest=destination,
        width=width, depth=depth, seed=seed,
    )

    # Apply back to mesh
    carved_flat = carved.flatten()
    for i, vert in enumerate(bm.verts):
        if i < len(carved_flat):
            vert.co.z = float(carved_flat[i]) * height_scale

    bm.to_mesh(mesh)
    bm.free()

    return {
        "name": terrain_name,
        "path_length": len(path),
        "depth": depth,
    }


# ---------------------------------------------------------------------------
# Handler: generate_road
# ---------------------------------------------------------------------------

def handle_generate_road(params: dict) -> dict:
    """Generate a road between waypoints on terrain with grading.

    Params:
        terrain_name (str): Existing terrain object name.
        waypoints (list of [row, col]): Ordered waypoints.
        width (int, default 3): Road width in cells.
        grade_strength (float, default 0.8): Flattening intensity.
        seed (int, default 0): Random seed.

    Returns dict with: name, path_length, width.
    """
    logger.info("Generating road on terrain")
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    waypoints = [(int(wp[0]), int(wp[1])) for wp in params.get("waypoints", [(0, 0), (0, 0)])]
    width = int(params.get("width", 3))
    grade_strength = params.get("grade_strength", 0.8)
    seed = params.get("seed", 0)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # WORLD-004: Detect actual grid dimensions (robust to non-square terrain)
    rows, cols = _detect_grid_dims(bm)

    heights = np.array([v.co.z for v in bm.verts])
    height_scale = heights.max() if heights.max() > 0 else 1.0
    heightmap = (heights / height_scale).reshape(rows, cols)

    # Convert width from meters to grid cells if it looks like meters
    terrain_width = obj.dimensions.x if obj.dimensions.x > 0 else 100.0
    terrain_height = obj.dimensions.y if obj.dimensions.y > 0 else terrain_width
    cell_size_x = terrain_width / max(cols - 1, 1)
    cell_size_y = terrain_height / max(rows - 1, 1)
    cell_size = (cell_size_x + cell_size_y) * 0.5
    if width > 10:  # likely specified in meters, not cells
        width = max(1, int(width / cell_size))

    path, graded = generate_road_path(
        heightmap, waypoints=waypoints,
        width=width, grade_strength=grade_strength, seed=seed,
    )

    graded_flat = graded.flatten()
    for i, vert in enumerate(bm.verts):
        if i < len(graded_flat):
            vert.co.z = float(graded_flat[i]) * height_scale

    bm.to_mesh(mesh)
    bm.free()

    # Generate visible road surface mesh with cobblestone material
    road_mesh_name = f"{terrain_name}_Road"
    terrain_obj = bpy.data.objects.get(terrain_name)
    terrain_width = terrain_obj.dimensions.x if terrain_obj and terrain_obj.dimensions.x > 0 else 100.0
    terrain_height = terrain_obj.dimensions.y if terrain_obj and terrain_obj.dimensions.y > 0 else terrain_width
    cell_size_x = terrain_width / max(cols - 1, 1)
    cell_size_y = terrain_height / max(rows - 1, 1)
    cell_size = (cell_size_x + cell_size_y) * 0.5
    terrain_origin_x = terrain_obj.location.x if terrain_obj else 0.0
    terrain_origin_y = terrain_obj.location.y if terrain_obj else 0.0

    road_bm = bmesh.new()
    road_uv = road_bm.loops.layers.uv.new("UVMap")
    road_half_width = width * cell_size * 0.5

    # Build road mesh as series of connected quads along the path
    if len(path) >= 2:
        prev_left = prev_right = None
        for pi in range(len(path) - 1):
            r0, c0 = path[pi]
            r1, c1 = path[pi + 1]
            # Convert grid coords to world coords
            x0, y0 = _terrain_grid_to_world_xy(
                r0,
                c0,
                rows=rows,
                cols=cols,
                terrain_width=terrain_width,
                terrain_height=terrain_height,
                terrain_origin_x=terrain_origin_x,
                terrain_origin_y=terrain_origin_y,
            )
            x1, y1 = _terrain_grid_to_world_xy(
                r1,
                c1,
                rows=rows,
                cols=cols,
                terrain_width=terrain_width,
                terrain_height=terrain_height,
                terrain_origin_x=terrain_origin_x,
                terrain_origin_y=terrain_origin_y,
            )
            z0 = float(graded_flat[r0 * cols + c0]) * height_scale + 0.03
            z1 = float(graded_flat[r1 * cols + c1]) * height_scale + 0.03

            # Perpendicular direction for road width
            dx, dy = x1 - x0, y1 - y0
            length = max(math.sqrt(dx * dx + dy * dy), 0.01)
            nx, ny = -dy / length * road_half_width, dx / length * road_half_width

            v0 = road_bm.verts.new((x0 + nx, y0 + ny, z0))
            v1 = road_bm.verts.new((x0 - nx, y0 - ny, z0))
            v2 = road_bm.verts.new((x1 - nx, y1 - ny, z1))
            v3 = road_bm.verts.new((x1 + nx, y1 + ny, z1))

            if prev_left is not None and prev_right is not None:
                # Connect to previous segment for continuous road
                try:
                    road_bm.faces.new([prev_left, prev_right, v1, v0])
                except ValueError:
                    pass

            try:
                face = road_bm.faces.new([v0, v1, v2, v3])
                face.smooth = True
            except ValueError:
                pass
            prev_left = v3
            prev_right = v2

    # Remove doubles and recalc normals
    if road_bm.verts:
        bmesh.ops.remove_doubles(road_bm, verts=road_bm.verts[:], dist=0.01)
        bmesh.ops.recalc_face_normals(road_bm, faces=road_bm.faces[:])

    road_mesh_data = bpy.data.meshes.new(road_mesh_name)
    road_bm.to_mesh(road_mesh_data)
    road_bm.free()
    for poly in road_mesh_data.polygons:
        poly.use_smooth = True

    road_obj = bpy.data.objects.new(road_mesh_name, road_mesh_data)
    bpy.context.collection.objects.link(road_obj)

    # Apply cobblestone material
    from .procedural_materials import create_procedural_material
    try:
        road_mat = create_procedural_material(road_mesh_name, "cobblestone_floor")
        if road_mat:
            road_mesh_data.materials.append(road_mat)
    except Exception:
        # Fallback: basic grey stone material
        road_mat = bpy.data.materials.new(name="Road_Cobblestone")
        road_mat.use_nodes = True
        if road_mat.node_tree:
            bsdf = road_mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bc = bsdf.inputs.get("Base Color")
                if bc:
                    bc.default_value = (0.25, 0.22, 0.18, 1.0)
                rgh = bsdf.inputs.get("Roughness")
                if rgh:
                    rgh.default_value = 0.85
        road_mesh_data.materials.append(road_mat)

    return {
        "name": terrain_name,
        "road_mesh_name": road_obj.name,
        "path_length": len(path),
        "width": width,
        "road_vertex_count": len(road_mesh_data.vertices),
    }


# ---------------------------------------------------------------------------
# Handler: create_water
# ---------------------------------------------------------------------------

def handle_create_water(params: dict) -> dict:
    """Create a water body -- spline-based surface mesh with AAA flow data.

    AAA upgrade (39-02): replaces flat disc placeholder with a spline-following
    mesh that encodes flow speed, direction, and foam as vertex colors.  A simple
    grid fallback is used when no path_points are provided.

    Params:
        name (str, default "Water"): Water object name.
        water_level (float, default 0.3): Water plane height (world Z).
        terrain_name (str, optional): Reference terrain for sizing.
        width (float, default 8.0): Cross-section width (river default 8m).
        depth (float, default 100.0): Along-flow length for grid mode.
        material_name (str, default "Water_Material"): Material name.
        path_points (list of [x,y,z], optional): Spline control points for the
            river/lake centre-line.  When provided the mesh follows the path.
        cross_sections (int, default 12): Subdivisions perpendicular to flow.

    Vertex color layer "flow_vc" RGBA convention:
        R = flow speed  (0=still, 1=fast; narrower channel = faster)
        G = flow dir X  (normalised, remapped to 0-1)
        B = flow dir Z  (normalised, remapped to 0-1)
        A = foam        (1.0 where depth<0.2m or speed>0.8, else 0.0)

    Returns dict with: name, water_level, area, tri_count, vertex_count,
                       has_flow_vertex_colors, has_shore_alpha.
    """
    logger.info("Creating water body (AAA spline mesh)")
    name = params.get("name", "Water")
    water_level = params.get("water_level", 0.3)
    terrain_name = params.get("terrain_name")
    width_raw = params.get("width")
    width = float(width_raw) if width_raw is not None else 8.0
    fallback_depth = float(params.get("depth", 100.0))
    material_name = params.get("material_name", "Water_Material")
    path_points_raw = params.get("path_points")
    cross_sections = max(8, min(16, int(params.get("cross_sections", 12))))
    preview_fast = _parse_bool(params.get("preview_fast", True))

    # If terrain specified, use its Z for water level snapping
    terrain_origin_x = 0.0
    terrain_origin_y = 0.0
    if terrain_name:
        terrain_obj = bpy.data.objects.get(terrain_name)
        if terrain_obj is not None and path_points_raw is None:
            terrain_origin_x = terrain_obj.location.x
            terrain_origin_y = terrain_obj.location.y
            dims = terrain_obj.dimensions
            fallback_depth = max(dims.y, fallback_depth)
            if width_raw is None:
                width = max(4.0, min(dims.x * 0.035, 12.0))

    # -----------------------------------------------------------------------
    # Build spline path
    # -----------------------------------------------------------------------
    path = _resolve_water_path_points(
        path_points_raw=path_points_raw,
        terrain_origin_x=terrain_origin_x,
        terrain_origin_y=terrain_origin_y,
        fallback_depth=fallback_depth,
        water_level=water_level,
    )
    if preview_fast and len(path) > 6:
        cross_sections = min(cross_sections, 3)

    # -----------------------------------------------------------------------
    # Build cross-section mesh following the spline
    # -----------------------------------------------------------------------
    existing_obj = bpy.data.objects.get(name)
    if existing_obj is not None:
        existing_mesh = existing_obj.data
        bpy.data.objects.remove(existing_obj, do_unlink=True)
        if existing_mesh is not None and getattr(existing_mesh, "users", 0) == 0:
            bpy.data.meshes.remove(existing_mesh)

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # UV layer (must exist before faces are created so loops can write to it).
    # Without this the water has no UV map and any tiled material is broken.
    uv_layer = bm.loops.layers.uv.new("UVMap")

    # Vertex color layer for flow data
    flow_layer = bm.loops.layers.float_color.new("flow_vc")

    half_w = width / 2.0
    num_segs = len(path) - 1

    # Estimate total path length for speed calculation
    total_length = 0.0
    for i in range(num_segs):
        p0 = path[i]
        p1 = path[i + 1]
        seg_len = math.sqrt(
            (p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 + (p1[2] - p0[2]) ** 2
        )
        total_length += max(seg_len, 0.001)

    # Track cumulative arc length per ring for v-axis UV (along flow).
    # u runs across the cross-section [0..1], v runs along the path [0..total_length / TILE].
    UV_TILE = 4.0  # 1 UV unit = 4 world units (tunable; controls texture density)
    cumulative_length = [0.0]
    for i in range(num_segs):
        p0 = path[i]
        p1 = path[i + 1]
        seg_len = math.sqrt(
            (p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 + (p1[2] - p0[2]) ** 2
        )
        cumulative_length.append(cumulative_length[-1] + seg_len)

    # Ring of vertices per path point
    rings: list[list] = []
    for pi, pt in enumerate(path):
        px, py, pz = pt

        # Tangent direction
        if pi == 0:
            nxt = path[1]
            tx = nxt[0] - px
            ty = nxt[1] - py
        elif pi == len(path) - 1:
            prv = path[-2]
            tx = px - prv[0]
            ty = py - prv[1]
        else:
            prv = path[pi - 1]
            nxt = path[pi + 1]
            tx = nxt[0] - prv[0]
            ty = nxt[1] - prv[1]

        tlen = math.sqrt(tx * tx + ty * ty) or 1.0
        tx /= tlen
        ty /= tlen

        # Perpendicular (cross-section direction)
        perp_x = -ty
        perp_y = tx

        # Normalised flow direction components (remapped 0-1)
        flow_dir_x = (tx + 1.0) * 0.5
        flow_dir_z = (ty + 1.0) * 0.5

        # Flow speed: terrain-aware based on channel slope
        if pi > 0:
            prev_pt = path[pi - 1]
            dz = abs(pz - prev_pt[2])
            dx_dist = math.sqrt((px - prev_pt[0]) ** 2 + (py - prev_pt[1]) ** 2)
            slope = dz / max(dx_dist, 0.1)
            flow_speed = min(1.0, 0.2 + slope * 3.0)
        else:
            flow_speed = 0.3

        # v coordinate for this ring (along flow direction)
        ring_v = cumulative_length[pi] / UV_TILE

        ring_verts = []
        for ci in range(cross_sections + 1):
            t = ci / cross_sections  # 0 = left shore, 1 = right shore
            offset = (t - 0.5) * 2.0  # -1 to +1
            vx = px + perp_x * offset * half_w
            vy = py + perp_y * offset * half_w
            vz = pz

            # Shore depth proxy: 0 at edges, 1 at center
            shore_t = 1.0 - abs(offset)  # 0.0 at shore, 1.0 at centre

            # u coordinate across cross-section [0..1]
            ring_u = t

            v = bm.verts.new((vx, vy, vz))
            ring_verts.append((v, shore_t, flow_speed, flow_dir_x, flow_dir_z, ring_u, ring_v))
        rings.append(ring_verts)

    # Connect rings into quads
    for ri in range(len(rings) - 1):
        ring_a = rings[ri]
        ring_b = rings[ri + 1]
        for ci in range(cross_sections):
            va, sha, spa, fdxa, fdza, ua, va_uv = ring_a[ci]
            vb, shb, spb, fdxb, fdzb, ub, vb_uv = ring_a[ci + 1]
            vc, shc, spc, fdxc, fdzc, uc, vc_uv = ring_b[ci + 1]
            vd, shd, spd, fdxd, fdzd, ud, vd_uv = ring_b[ci]
            try:
                face = bm.faces.new([va, vb, vc, vd])
                # Paint flow vertex colors AND UVs per loop
                loop_data = [
                    (sha, spa, fdxa, fdza, ua, va_uv),
                    (shb, spb, fdxb, fdzb, ub, vb_uv),
                    (shc, spc, fdxc, fdzc, uc, vc_uv),
                    (shd, spd, fdxd, fdzd, ud, vd_uv),
                ]
                for loop, (sh, sp, fdx, fdz, uv_u, uv_v) in zip(face.loops, loop_data):
                    # Foam: shallow shore (depth<0.2 proxy = shore_t<0.2) or fast flow
                    foam = 1.0 if (sh < 0.2 or sp > 0.8) else 0.0
                    loop[flow_layer] = (sp, fdx, fdz, foam)
                    loop[uv_layer].uv = (uv_u, uv_v)
            except ValueError:
                pass

    bm.to_mesh(mesh)
    tri_count = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
    # Count quads as 2 tris each for budget check
    total_tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    # The spline vertices already encode world-space XY and water Z.
    # Keep the object origin at world zero so the surface is not lifted twice.
    obj.location = (0.0, 0.0, 0.0)
    bpy.context.collection.objects.link(obj)

    # -----------------------------------------------------------------------
    # AAA water material: sRGB(40,60,50), roughness 0.05, alpha 0.6, IOR 1.33
    # -----------------------------------------------------------------------
    mat = bpy.data.materials.get(material_name)
    if mat is None:
        mat = bpy.data.materials.new(name=material_name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    if hasattr(mat, "blend_method"):
        mat.blend_method = "OPAQUE" if preview_fast else "BLEND"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    if mat.node_tree:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (360, 0)
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (120, 0)
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        base_color = bsdf.inputs.get("Base Color")
        if base_color:
            base_color.default_value = (0.019, 0.055, 0.043, 1.0)
        rough = bsdf.inputs.get("Roughness")
        if rough:
            rough.default_value = 0.16 if preview_fast else 0.06
        ior = bsdf.inputs.get("IOR")
        if ior:
            ior.default_value = 1.333
        alpha = bsdf.inputs.get("Alpha")
        if alpha:
            alpha.default_value = 1.0 if preview_fast else 0.68
        trans = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
        if trans:
            trans.default_value = 0.0 if preview_fast else 0.2
        spec = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
        if spec:
            spec.default_value = 0.5

        if not preview_fast:
            noise_tex = nodes.new("ShaderNodeTexNoise")
            noise_tex.location = (-320, 40)
            noise_tex.inputs["Scale"].default_value = 18.0
            noise_tex.inputs["Detail"].default_value = 4.0
            noise_tex.inputs["Roughness"].default_value = 0.4
            bump_node = nodes.new("ShaderNodeBump")
            bump_node.location = (-80, -120)
            bump_node.inputs["Strength"].default_value = 0.04
            bump_node.inputs["Distance"].default_value = 0.01
            links.new(noise_tex.outputs["Fac"], bump_node.inputs["Height"])
            normal_input = bsdf.inputs.get("Normal")
            if normal_input:
                links.new(bump_node.outputs["Normal"], normal_input)

    mesh.materials.append(mat)

    area = total_length * width if total_length > 0 else width * fallback_depth

    return {
        "name": obj.name,
        "water_level": water_level,
        "area": area,
        "tri_count": total_tris,
        "vertex_count": len(mesh.vertices),
        "has_flow_vertex_colors": True,
        "has_shore_alpha": True,
        "cross_sections": cross_sections,
        "path_point_count": len(path),
        "preview_fast": preview_fast,
    }


# ---------------------------------------------------------------------------
# Handler: export_heightmap
# ---------------------------------------------------------------------------

def handle_export_heightmap(params: dict) -> dict:
    """Export terrain heightmap as 16-bit little-endian RAW for Unity.

    Params:
        terrain_name (str): Terrain object name.
        filepath (str): Output file path (.raw).
        flip_vertical (bool, default True): Flip for Unity coordinate system.
        unity_compat (bool, default False): Resize to power-of-two+1.

    Returns dict with: filepath, width, height, bit_depth, byte_order.
    """
    logger.info("Exporting heightmap")
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    filepath = params.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required")

    flip_vertical = params.get("flip_vertical", True)
    unity_compat = params.get("unity_compat", False)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # WORLD-004: Detect actual grid dimensions (robust to non-square terrain)
    rows, cols = _detect_grid_dims(bm)

    heights = np.array([v.co.z for v in bm.verts])
    bm.free()

    heightmap = heights.reshape(rows, cols)
    export_height_range = _resolve_export_height_range(params, heightmap)

    # Unity compat: resize to nearest power-of-two + 1 (use cols as ref dimension)
    if unity_compat:
        target = _nearest_pot_plus_1(cols)
        if target != cols:
            # Simple nearest-neighbor resize
            x_indices = np.round(np.linspace(0, cols - 1, target)).astype(int)
            y_indices = np.round(np.linspace(0, rows - 1, target)).astype(int)
            heightmap = heightmap[np.ix_(y_indices, x_indices)]

    # Export
    raw_bytes = _export_heightmap_raw(
        heightmap,
        flip_vertical=flip_vertical,
        value_range=export_height_range,
    )

    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(raw_bytes)

    rows, cols = heightmap.shape

    return {
        "filepath": str(out_path),
        "width": cols,
        "height": rows,
        "bit_depth": 16,
        "byte_order": "little-endian",
    }


def _nearest_pot_plus_1(n: int) -> int:
    """Find nearest power-of-two + 1 >= n."""
    pot = 1
    while pot + 1 < n:
        pot *= 2
    return pot + 1


# ---------------------------------------------------------------------------
# Handler: generate_multi_biome_world
# ---------------------------------------------------------------------------

def handle_generate_multi_biome_world(params: dict) -> dict:
    """Generate a complete multi-biome world map in Blender.

    Orchestrates: WorldMapSpec -> terrain mesh -> biome vertex colors ->
    biome material -> vegetation scatter.  Requires bpy (runs inside Blender).

    Params:
        name (str): Base name for terrain object. Default "MultibiomeTerrain".
        width (int): Grid resolution. Default 256.
        height (int): Grid resolution. Default 256.
        world_size (float): Terrain size in meters. Default 512.0.
        height_scale (float): Vertical exaggeration. Default 80.0.
        biome_count (int): Number of Voronoi regions. Default 6.
        biomes (list[str]): Biome names. Default 6 VB presets.
        seed (int): Master seed. Default 42.
        corruption_level (float): Global corruption intensity 0-1. Default 0.3.
        building_plots (list[dict]): Pre-placed footprints for foundation flatten.
        erosion (str): "hydraulic"|"thermal"|"both"|"none". Default "hydraulic".
        erosion_iterations (int): Default 5000.
        scatter_vegetation (bool): Whether to scatter per-biome vegetation. Default True.
        min_veg_distance (float): Min spacing between vegetation instances. Default 4.0.
        max_veg_instances (int): Cap per biome. Default 2000.
        transition_width_m (float): Blend zone width in meters. Default 15.0.

    Returns dict with:
        name, biome_count, biome_names, corruption_level, corruption_zones,
        vegetation_count, flatten_zones_applied, vertex_count, world_size_m.
    """
    from ._biome_grammar import generate_world_map_spec
    from .terrain_materials import BIOME_PALETTES_V2

    # --- 1. Build world spec (pure logic, no bpy) ---
    name = params.get("name", "MultibiomeTerrain")
    seed = params.get("seed", 42)
    world_size = params.get("world_size", 512.0)
    width = params.get("width", 256)
    height = params.get("height", 256)
    biome_count = params.get("biome_count", 6)
    biomes = params.get("biomes")
    corruption_level = params.get("corruption_level", 0.3)
    building_plots = params.get("building_plots", [])
    scatter_veg = params.get("scatter_vegetation", True)

    spec = generate_world_map_spec(
        width=width,
        height=height,
        world_size=world_size,
        biome_count=biome_count,
        biomes=biomes,
        seed=seed,
        corruption_level=corruption_level,
        building_plots=building_plots,
        transition_width_m=params.get("transition_width_m", 15.0),
    )

    # --- 2. Generate base terrain mesh ---
    # Determine terrain type from dominant biome instead of hardcoding "mountain"
    dominant_biome = biomes[0] if biomes else (spec.biome_names[0] if spec.biome_names else "hills")
    biome_preset = get_vb_biome_preset(
        dominant_biome,
        season=params.get("season"),
    )
    base_terrain_type = biome_preset["terrain_type"] if biome_preset else "hills"
    terrain_params = {
        "name": name,
        "terrain_type": base_terrain_type,
        "resolution": width,
        "height_scale": params.get("height_scale", 80.0),
        "scale": world_size,
        "seed": seed,
        "erosion": params.get("erosion", "hydraulic"),
        "erosion_iterations": params.get("erosion_iterations", 5000),
        "flatten_zones": spec.flatten_zones,
    }
    terrain_result = handle_generate_terrain(terrain_params)

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError(f"Terrain object '{name}' not found after generation")

    # --- 3. Assign biome vertex colors per-vertex ---
    vertex_colors = _compute_vertex_colors_for_biome_map(
        obj, spec, world_size
    )

    mesh = obj.data
    if mesh.color_attributes.get("BiomeColor"):
        mesh.color_attributes.remove(mesh.color_attributes["BiomeColor"])
    col_attr = mesh.color_attributes.new(
        name="BiomeColor", type="FLOAT_COLOR", domain="POINT"
    )
    for i, rgba in enumerate(vertex_colors):
        col_attr.data[i].color = rgba

    # --- 4. Apply biome material for primary biome ---
    # Primary biome = dominant biome at terrain center (simple heuristic)
    cx_cell = int(spec.biome_ids[height // 2, width // 2])
    primary_biome = spec.biome_names[cx_cell]
    if primary_biome in BIOME_PALETTES_V2:
        from .terrain_materials import handle_create_biome_terrain
        try:
            handle_create_biome_terrain({
                "name": name,
                "biome_name": primary_biome,
                "season": params.get("season"),
            })
        except Exception:
            pass  # Non-fatal: material assignment is best-effort

    # --- 5. Scatter vegetation per biome (if enabled) ---
    vegetation_total = 0
    if scatter_veg:
        from .vegetation_system import scatter_biome_vegetation
        for biome_name in spec.biome_names:
            try:
                veg_result = scatter_biome_vegetation({
                    "terrain_name": name,
                    "biome_name": biome_name,
                    "min_distance": params.get("min_veg_distance", 4.0),
                    "seed": seed + _stable_seed_offset(biome_name),
                    "max_instances": params.get("max_veg_instances", 2000),
                    "season": "corrupted" if corruption_level > 0.5 else None,
                    "bake_wind_colors": True,
                    "water_level": 0.05,
                })
                vegetation_total += veg_result.get("instance_count", 0)
            except Exception:
                pass  # Biome may not have vegetation set -- skip silently

    # --- 6. Count corruption zones ---
    corruption_zones = int((spec.corruption_map > 0.3).sum())

    return {
        "name": name,
        "biome_count": biome_count,
        "biome_names": spec.biome_names,
        "corruption_level": corruption_level,
        "corruption_zones": corruption_zones,
        "vegetation_count": vegetation_total,
        "flatten_zones_applied": len(spec.flatten_zones),
        "vertex_count": terrain_result.get("vertex_count", 0),
        "world_size_m": world_size,
    }


def _compute_vertex_colors_for_biome_map(
    obj,            # Blender object
    spec,           # WorldMapSpec
    world_size: float,
) -> list:
    """Sample per-vertex biome color from WorldMapSpec corruption map + biome palette.

    Returns list of (R, G, B, A) tuples, one per vertex.
    """
    from .terrain_materials import apply_corruption_tint, BIOME_PALETTES, _get_material_def

    mesh = obj.data
    rows, cols = spec.biome_ids.shape

    result_colors = []
    for v in mesh.vertices:
        vx, vy = v.co.x, v.co.y

        # Map world position to biome grid cell
        nx = max(0, min(cols - 1, int((vx / world_size + 0.5) * cols)))
        ny = max(0, min(rows - 1, int((vy / world_size + 0.5) * rows)))
        biome_idx = int(spec.biome_ids[ny, nx])
        corruption = float(spec.corruption_map[ny, nx])

        # Base color from biome palette
        base_color = (0.15, 0.12, 0.10, 1.0)
        try:
            biome_name = spec.biome_names[biome_idx]
            palette = BIOME_PALETTES.get(biome_name, {})
            ground_mats = palette.get("ground", [])
            if ground_mats:
                mat_def = _get_material_def(ground_mats[0])
                if mat_def and "base_color" in mat_def:
                    base_color = tuple(mat_def["base_color"])
                    if len(base_color) == 3:
                        base_color = base_color + (1.0,)
        except Exception:
            pass

        tinted = apply_corruption_tint([base_color], corruption)
        result_colors.append(tinted[0])

    return result_colors
def _stable_seed_offset(label: str) -> int:
    """Return a deterministic, cross-process seed offset for string labels."""
    return zlib.crc32(label.encode("utf-8")) & 0xFFFF
