"""Per-biome vegetation quality system for VeilBreakers dark fantasy environments.

Provides biome-specific vegetation sets (trees, rocks, ground cover), Poisson
disk placement with slope/height filtering, wind vertex color computation for
Unity shader integration, and seasonal material variants.

All compute_* functions are pure-logic (no bpy/bmesh) for testability.
The handle_scatter_biome_vegetation handler wires everything together with
Blender scene creation.

Biomes:
  - thornwood_forest: Dead twisted trees, ancient oaks, giant mushrooms
  - corrupted_swamp: Sparse dead trees, mushroom clusters, scattered boulders
  - mountain_pass: Dark pines, heavy boulders, rare crystals
  - cemetery: Hanging willows, moss, gravestones
  - ashen_wastes: Charred stumps, obsidian rocks, ember plants
  - frozen_hollows: Ice-covered pines, frozen boulders, frost lichen
  - blighted_mire: Mangrove roots, toxic mushrooms, sludge rocks
  - ruined_citadel: Overgrown vines, crumbled stone, corrupted saplings
  - desert: Dead brush, cacti-shaped rocks, tumbleweeds
  - coastal: Sea grass, coastal scrub, driftwood
  - grasslands: Tall grass, wildflowers, lone trees
  - mushroom_forest: Giant mushrooms, bioluminescent ground cover, spore clusters
  - crystal_cavern: Crystal growths, mineral formations
  - deep_forest: Massive ancient trees, thick ferns, hanging moss
"""

from __future__ import annotations

import math
import random
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Per-biome vegetation configuration
# ---------------------------------------------------------------------------

BIOME_VEGETATION_SETS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "thornwood_forest": {
        "trees": [
            {"type": "tree", "style": "dead_twisted", "density": 0.3, "scale_range": (0.8, 1.5)},
            {"type": "tree", "style": "ancient_oak", "density": 0.1, "scale_range": (1.5, 3.0)},
            {"type": "mushroom", "style": "giant_cap", "density": 0.05, "scale_range": (0.5, 1.2)},
        ],
        "ground_cover": [
            {"type": "fern", "density": 0.5, "scale_range": (0.2, 0.5)},
            {"type": "moss", "density": 0.4, "scale_range": (0.3, 0.6)},
        ],
        "rocks": [
            {"type": "rock", "style": "boulder", "density": 0.1, "scale_range": (0.3, 1.0)},
            {"type": "rock", "style": "standing_stone", "density": 0.02, "scale_range": (1.0, 2.0)},
        ],
    },
    "corrupted_swamp": {
        "trees": [
            {"type": "tree", "style": "dead_twisted", "density": 0.2, "scale_range": (0.6, 1.3)},
        ],
        "ground_cover": [
            {"type": "mushroom", "style": "cluster", "density": 0.3, "scale_range": (0.2, 0.6)},
        ],
        "rocks": [
            {"type": "rock", "style": "boulder", "density": 0.05, "scale_range": (0.3, 0.8)},
        ],
    },
    "mountain_pass": {
        "trees": [
            {"type": "tree", "style": "dark_pine", "density": 0.15, "scale_range": (1.0, 2.0)},
        ],
        "ground_cover": [],
        "rocks": [
            {"type": "rock", "style": "boulder", "density": 0.2, "scale_range": (0.5, 2.0)},
            {"type": "rock", "style": "crystal", "density": 0.03, "scale_range": (0.3, 0.8)},
        ],
    },
    "cemetery": {
        "trees": [
            {"type": "tree", "style": "willow_hanging", "density": 0.05, "scale_range": (1.2, 2.5)},
        ],
        "ground_cover": [
            {"type": "moss", "density": 0.3, "scale_range": (0.2, 0.4)},
        ],
        "rocks": [
            {"type": "gravestone", "style": "tombstone", "density": 0.15, "scale_range": (0.5, 1.0)},
        ],
    },
    "ashen_wastes": {
        "trees": [
            {"type": "tree", "style": "charred_stump", "density": 0.08, "scale_range": (0.4, 1.0)},
        ],
        "ground_cover": [
            {"type": "ember_plant", "density": 0.15, "scale_range": (0.1, 0.3)},
        ],
        "rocks": [
            {"type": "rock", "style": "obsidian", "density": 0.12, "scale_range": (0.3, 1.2)},
            {"type": "rock", "style": "volcanic", "density": 0.06, "scale_range": (0.5, 1.5)},
        ],
    },
    "frozen_hollows": {
        "trees": [
            {"type": "tree", "style": "ice_pine", "density": 0.12, "scale_range": (1.0, 2.2)},
        ],
        "ground_cover": [
            {"type": "frost_lichen", "density": 0.25, "scale_range": (0.1, 0.3)},
        ],
        "rocks": [
            {"type": "rock", "style": "frozen_boulder", "density": 0.15, "scale_range": (0.5, 1.8)},
            {"type": "rock", "style": "ice_crystal", "density": 0.04, "scale_range": (0.3, 0.7)},
        ],
    },
    "blighted_mire": {
        "trees": [
            {"type": "tree", "style": "mangrove_root", "density": 0.18, "scale_range": (0.7, 1.4)},
        ],
        "ground_cover": [
            {"type": "mushroom", "style": "toxic", "density": 0.2, "scale_range": (0.15, 0.4)},
        ],
        "rocks": [
            {"type": "rock", "style": "sludge_rock", "density": 0.08, "scale_range": (0.3, 0.9)},
        ],
    },
    "ruined_citadel": {
        "trees": [
            {"type": "tree", "style": "corrupted_sapling", "density": 0.06, "scale_range": (0.3, 0.8)},
        ],
        "ground_cover": [
            {"type": "vine", "density": 0.35, "scale_range": (0.3, 0.8)},
            {"type": "moss", "density": 0.2, "scale_range": (0.2, 0.5)},
        ],
        "rocks": [
            {"type": "rock", "style": "crumbled_stone", "density": 0.18, "scale_range": (0.3, 1.0)},
        ],
    },
    "desert": {
        "trees": [
            {"type": "bush", "style": "dead_brush", "density": 0.06, "scale_range": (0.3, 0.7)},
        ],
        "ground_cover": [
            {"type": "tumbleweed", "density": 0.04, "scale_range": (0.2, 0.5)},
        ],
        "rocks": [
            {"type": "rock", "style": "cactus_rock", "density": 0.08, "scale_range": (0.5, 1.5)},
            {"type": "rock", "style": "wind_eroded", "density": 0.05, "scale_range": (0.4, 1.2)},
        ],
    },
    "coastal": {
        "trees": [
            {"type": "bush", "style": "coastal_scrub", "density": 0.10, "scale_range": (0.3, 0.8)},
        ],
        "ground_cover": [
            {"type": "grass", "style": "sea_grass", "density": 0.25, "scale_range": (0.2, 0.5)},
        ],
        "rocks": [
            {"type": "rock", "style": "driftwood", "density": 0.08, "scale_range": (0.3, 1.0)},
            {"type": "rock", "style": "sea_worn", "density": 0.10, "scale_range": (0.3, 0.9)},
        ],
    },
    "grasslands": {
        "trees": [
            {"type": "tree", "style": "lone_windswept", "density": 0.03, "scale_range": (1.5, 3.0)},
        ],
        "ground_cover": [
            {"type": "grass", "style": "tall_grass", "density": 0.50, "scale_range": (0.3, 0.8)},
            {"type": "flower", "style": "wildflower", "density": 0.15, "scale_range": (0.1, 0.3)},
        ],
        "rocks": [
            {"type": "rock", "style": "field_stone", "density": 0.04, "scale_range": (0.3, 0.8)},
        ],
    },
    "mushroom_forest": {
        "trees": [
            {"type": "mushroom", "style": "giant_mushroom", "density": 0.12, "scale_range": (1.0, 3.0)},
            {"type": "mushroom", "style": "shelf_mushroom", "density": 0.08, "scale_range": (0.3, 0.8)},
        ],
        "ground_cover": [
            {"type": "moss", "style": "bioluminescent", "density": 0.30, "scale_range": (0.1, 0.3)},
            {"type": "mushroom", "style": "spore_cluster", "density": 0.20, "scale_range": (0.1, 0.4)},
        ],
        "rocks": [
            {"type": "rock", "style": "fungal_log", "density": 0.06, "scale_range": (0.4, 1.0)},
        ],
    },
    "crystal_cavern": {
        "trees": [],
        "ground_cover": [
            {"type": "crystal", "style": "small_growth", "density": 0.20, "scale_range": (0.2, 0.6)},
        ],
        "rocks": [
            {"type": "rock", "style": "crystal_cluster", "density": 0.15, "scale_range": (0.5, 2.0)},
            {"type": "rock", "style": "mineral_formation", "density": 0.10, "scale_range": (0.3, 1.2)},
        ],
    },
    "deep_forest": {
        "trees": [
            {"type": "tree", "style": "ancient_massive", "density": 0.08, "scale_range": (2.0, 5.0)},
            {"type": "tree", "style": "gnarled_elder", "density": 0.05, "scale_range": (1.5, 3.0)},
        ],
        "ground_cover": [
            {"type": "fern", "style": "thick_fern", "density": 0.40, "scale_range": (0.3, 0.7)},
            {"type": "moss", "style": "hanging_moss", "density": 0.30, "scale_range": (0.2, 0.6)},
        ],
        "rocks": [
            {"type": "rock", "style": "root_boulder", "density": 0.08, "scale_range": (0.5, 1.5)},
        ],
    },
}


# ---------------------------------------------------------------------------
# Seasonal material variant configuration
# ---------------------------------------------------------------------------

_SEASONAL_VARIANTS: dict[str, dict[str, Any]] = {
    "summer": {
        "color_tint": (0.0, 0.0, 0.0),
        "saturation_mult": 1.0,
        "leaf_density": 1.0,
        "roughness_offset": 0.0,
        "description": "Full foliage, standard colors",
    },
    "autumn": {
        "color_tint": (0.3, 0.15, -0.1),
        "saturation_mult": 1.2,
        "leaf_density": 0.7,
        "roughness_offset": 0.05,
        "description": "Orange/red tint, reduced foliage",
    },
    "winter": {
        "color_tint": (0.1, 0.1, 0.15),
        "saturation_mult": 0.5,
        "leaf_density": 0.1,
        "roughness_offset": -0.1,
        "description": "Desaturated, bare branches, frost",
    },
    "corrupted": {
        "color_tint": (0.15, -0.1, 0.2),
        "saturation_mult": 0.8,
        "leaf_density": 0.4,
        "roughness_offset": 0.1,
        "description": "Purple tint, withered foliage",
    },
}


# ---------------------------------------------------------------------------
# Slope / height constraints
# ---------------------------------------------------------------------------

_MAX_TREE_SLOPE_DEGREES = 45.0
_MAX_GROUND_COVER_SLOPE_DEGREES = 55.0
_MAX_ROCK_SLOPE_DEGREES = 75.0
_DEFAULT_WATER_LEVEL = 0.05  # Normalized height below which nothing grows


def _max_slope_for_category(category: str) -> float:
    """Return the maximum slope in degrees for a vegetation category."""
    if category == "trees":
        return _MAX_TREE_SLOPE_DEGREES
    elif category == "ground_cover":
        return _MAX_GROUND_COVER_SLOPE_DEGREES
    elif category == "rocks":
        return _MAX_ROCK_SLOPE_DEGREES
    return _MAX_GROUND_COVER_SLOPE_DEGREES


# ---------------------------------------------------------------------------
# Pure-logic compute functions
# ---------------------------------------------------------------------------

def compute_vegetation_placement(
    terrain_vertices: list[tuple[float, float, float]],
    terrain_faces: list[tuple[int, ...]],
    terrain_normals: list[tuple[float, float, float]],
    biome_name: str,
    area_bounds: tuple[float, float, float, float],
    seed: int = 42,
    min_distance: float = 3.0,
    water_level: float = _DEFAULT_WATER_LEVEL,
) -> list[dict[str, Any]]:
    """Compute vegetation placements for a biome on terrain geometry.

    Pure-logic function -- no Blender dependency.

    Parameters
    ----------
    terrain_vertices : list of (x, y, z) tuples
        Terrain mesh vertex positions.
    terrain_faces : list of index tuples
        Face index lists (unused in current implementation, reserved for
        future triangle-based sampling).
    terrain_normals : list of (nx, ny, nz) tuples
        Per-vertex normals for slope calculation.
    biome_name : str
        Key into BIOME_VEGETATION_SETS.
    area_bounds : (min_x, min_y, max_x, max_y)
        World-space scatter rectangle.
    seed : int
        Random seed for deterministic generation.
    min_distance : float
        Minimum distance between placed vegetation instances.
    water_level : float
        Normalized height below which no vegetation is placed (0-1 range
        relative to terrain height range).

    Returns
    -------
    list of dict
        Each dict has: position (x, y, z), type, style, scale, rotation.
    """
    if biome_name not in BIOME_VEGETATION_SETS:
        raise ValueError(
            f"Unknown biome '{biome_name}'. "
            f"Valid biomes: {sorted(BIOME_VEGETATION_SETS.keys())}"
        )

    biome = BIOME_VEGETATION_SETS[biome_name]
    rng = random.Random(seed)

    min_x, min_y, max_x, max_y = area_bounds
    width = max_x - min_x
    depth = max_y - min_y

    if width <= 0 or depth <= 0:
        return []

    # Build spatial lookup from terrain vertices
    if not terrain_vertices:
        return []

    # Compute height range for normalization
    heights = [v[2] for v in terrain_vertices]
    min_h = min(heights)
    max_h = max(heights)
    has_height_variation = max_h > min_h
    height_range = max_h - min_h if has_height_variation else 1.0

    # Build a grid index for fast vertex lookup
    grid_res = max(1, int(math.sqrt(len(terrain_vertices))))
    cell_w = width / grid_res if grid_res > 0 else width
    cell_d = depth / grid_res if grid_res > 0 else depth

    # Map vertices into grid
    vertex_grid: dict[tuple[int, int], list[int]] = {}
    for i, (vx, vy, _vz) in enumerate(terrain_vertices):
        gi = int((vx - min_x) / cell_w) if cell_w > 0 else 0
        gj = int((vy - min_y) / cell_d) if cell_d > 0 else 0
        gi = max(0, min(gi, grid_res - 1))
        gj = max(0, min(gj, grid_res - 1))
        vertex_grid.setdefault((gi, gj), []).append(i)

    def _sample_terrain(px: float, py: float) -> tuple[float, float]:
        """Sample height and slope at a world position.

        Returns (normalized_height, slope_degrees).
        """
        gi = int((px - min_x) / cell_w) if cell_w > 0 else 0
        gj = int((py - min_y) / cell_d) if cell_d > 0 else 0
        gi = max(0, min(gi, grid_res - 1))
        gj = max(0, min(gj, grid_res - 1))

        # Find nearest vertex in cell and neighbors
        best_idx = -1
        best_dist_sq = float("inf")
        for di in range(-1, 2):
            for dj in range(-1, 2):
                ni, nj = gi + di, gj + dj
                for vi in vertex_grid.get((ni, nj), []):
                    vx, vy, _vz = terrain_vertices[vi]
                    dsq = (px - vx) ** 2 + (py - vy) ** 2
                    if dsq < best_dist_sq:
                        best_dist_sq = dsq
                        best_idx = vi

        if best_idx < 0:
            return 0.5, 0.0  # Default: mid-height, flat

        _vx, _vy, vz = terrain_vertices[best_idx]
        norm_height = (vz - min_h) / height_range

        # Compute slope from normal
        nx, ny, nz = terrain_normals[best_idx]
        normal_len = math.sqrt(nx * nx + ny * ny + nz * nz)
        if normal_len > 0:
            nz_norm = abs(nz) / normal_len
            nz_norm = max(0.0, min(1.0, nz_norm))
            slope_deg = math.degrees(math.acos(nz_norm))
        else:
            slope_deg = 0.0

        return norm_height, slope_deg

    # Poisson disk sampling within bounds
    from ._scatter_engine import poisson_disk_sample

    raw_points = poisson_disk_sample(width, depth, min_distance, seed=seed)

    # Build weighted category list for random selection
    all_entries: list[tuple[str, dict[str, Any]]] = []
    for category in ("trees", "ground_cover", "rocks"):
        for entry in biome.get(category, []):
            all_entries.append((category, entry))

    if not all_entries:
        return []

    # Compute total density for weighted selection
    total_density = sum(e["density"] for _, e in all_entries)

    placements: list[dict[str, Any]] = []

    for rx, ry in raw_points:
        # Offset to world space
        wx = rx + min_x
        wy = ry + min_y

        # Sample terrain at this position
        norm_h, slope_deg = _sample_terrain(wx, wy)

        # Water level filter: only applies when terrain has height variation
        # (flat terrain has all vertices at norm_h=0 which is a false positive)
        if has_height_variation and norm_h < water_level:
            continue

        # Select vegetation type based on density weights
        roll = rng.uniform(0.0, total_density)
        cumulative = 0.0
        selected_cat = None
        selected_entry = None

        for cat, entry in all_entries:
            cumulative += entry["density"]
            if roll <= cumulative:
                selected_cat = cat
                selected_entry = entry
                break

        if selected_entry is None:
            selected_cat, selected_entry = all_entries[-1]

        # Slope filter by category
        max_slope = _max_slope_for_category(selected_cat)
        if slope_deg > max_slope:
            continue

        # Density probability check (higher density = more likely to place)
        if rng.random() > selected_entry["density"]:
            continue

        # Compute scale and rotation
        scale_range = selected_entry.get("scale_range", (0.8, 1.2))
        scale = rng.uniform(scale_range[0], scale_range[1])
        rotation = rng.uniform(0.0, 360.0)

        # Sample terrain height for z position
        sample_h, _ = _sample_terrain(wx, wy)
        wz = min_h + sample_h * height_range

        placements.append({
            "position": (wx, wy, wz),
            "type": selected_entry["type"],
            "style": selected_entry.get("style", "default"),
            "scale": scale,
            "rotation": rotation,
        })

    return placements


def compute_wind_vertex_colors(
    vertices: list[tuple[float, float, float]],
    trunk_center: tuple[float, float] | None = None,
    ground_level: float | None = None,
) -> list[tuple[float, float, float]]:
    """Compute per-vertex wind sway colors for Unity wind shader integration.

    Pure-logic function -- no Blender dependency.

    Channel mapping:
      R = distance from trunk center normalized [0, 1] -- sway amount
      G = height from ground normalized [0, 1] -- sway amplitude
      B = estimated branch level [0, 1] -- sway frequency variation

    Parameters
    ----------
    vertices : list of (x, y, z)
        Mesh vertex positions.
    trunk_center : (x, y) or None
        XY center of the trunk. If None, computed as centroid of
        lowest-height vertices.
    ground_level : float or None
        Z height of the ground. If None, uses minimum vertex Z.

    Returns
    -------
    list of (r, g, b)
        Per-vertex color tuples with values clamped to [0, 1].
    """
    if not vertices:
        return []

    # Determine ground level
    z_values = [v[2] for v in vertices]
    min_z = min(z_values)
    max_z = max(z_values)
    height_range = max_z - min_z if max_z > min_z else 1.0

    if ground_level is None:
        ground_level = min_z

    # Determine trunk center from bottom vertices
    if trunk_center is None:
        threshold = min_z + height_range * 0.1
        bottom_verts = [(v[0], v[1]) for v in vertices if v[2] <= threshold]
        if bottom_verts:
            cx = sum(v[0] for v in bottom_verts) / len(bottom_verts)
            cy = sum(v[1] for v in bottom_verts) / len(bottom_verts)
            trunk_center = (cx, cy)
        else:
            cx = sum(v[0] for v in vertices) / len(vertices)
            cy = sum(v[1] for v in vertices) / len(vertices)
            trunk_center = (cx, cy)

    # Compute maximum XY distance for normalization
    max_dist = 0.0
    for vx, vy, _vz in vertices:
        d = math.sqrt((vx - trunk_center[0]) ** 2 + (vy - trunk_center[1]) ** 2)
        if d > max_dist:
            max_dist = d
    if max_dist <= 0:
        max_dist = 1.0

    colors: list[tuple[float, float, float]] = []

    for vx, vy, vz in vertices:
        # R: distance from trunk center (sway amount)
        dist = math.sqrt((vx - trunk_center[0]) ** 2 + (vy - trunk_center[1]) ** 2)
        r = min(1.0, max(0.0, dist / max_dist))

        # G: height from ground (sway amplitude)
        g = min(1.0, max(0.0, (vz - ground_level) / height_range))

        # B: branch level estimation
        # Higher vertices further from trunk = outer branches (higher frequency)
        # Low vertices near trunk = trunk (low frequency)
        branch_level = (r * 0.5 + g * 0.5)
        b = min(1.0, max(0.0, branch_level))

        colors.append((r, g, b))

    return colors


def get_seasonal_variant(
    vegetation_type: str,
    season: str,
) -> dict[str, Any]:
    """Get modified material parameters for a seasonal variant.

    Pure-logic function -- no Blender dependency.

    Parameters
    ----------
    vegetation_type : str
        Type of vegetation (tree, mushroom, fern, moss, rock, etc.)
    season : str
        One of: summer, autumn, winter, corrupted.

    Returns
    -------
    dict with:
        color_tint: (r, g, b) additive color offset
        saturation_mult: float saturation multiplier
        leaf_density: float [0, 1] leaf coverage
        roughness_offset: float additive roughness change
        description: str human-readable description
        affects_leaves: bool whether foliage is affected
        affects_bark: bool whether bark/trunk is affected
    """
    if season not in _SEASONAL_VARIANTS:
        raise ValueError(
            f"Unknown season '{season}'. "
            f"Valid seasons: {sorted(_SEASONAL_VARIANTS.keys())}"
        )

    base = dict(_SEASONAL_VARIANTS[season])

    # Vegetation-type-specific adjustments
    is_foliage = vegetation_type in ("tree", "fern", "vine", "moss", "bush")
    is_fungi = vegetation_type in ("mushroom",)
    is_mineral = vegetation_type in ("rock", "gravestone", "crystal")

    base["affects_leaves"] = is_foliage
    base["affects_bark"] = vegetation_type == "tree"

    if is_mineral:
        # Rocks and stones are less affected by seasons
        base["color_tint"] = (
            base["color_tint"][0] * 0.3,
            base["color_tint"][1] * 0.3,
            base["color_tint"][2] * 0.3,
        )
        base["saturation_mult"] = 1.0 + (base["saturation_mult"] - 1.0) * 0.2
        base["leaf_density"] = 1.0  # Rocks don't lose leaves
        base["affects_leaves"] = False

    if is_fungi:
        # Mushrooms are less affected by seasons but react to corruption
        if season == "corrupted":
            base["color_tint"] = (0.2, -0.15, 0.3)  # Stronger purple
            base["saturation_mult"] = 1.3
        else:
            base["color_tint"] = (
                base["color_tint"][0] * 0.5,
                base["color_tint"][1] * 0.5,
                base["color_tint"][2] * 0.5,
            )
            base["leaf_density"] = 1.0  # Mushrooms don't lose caps

    if season == "winter" and is_foliage:
        # Extra frost effect on foliage
        base["roughness_offset"] = -0.15  # Smoother ice/frost surface

    return base


# ---------------------------------------------------------------------------
# Handler: scatter_biome_vegetation
# ---------------------------------------------------------------------------

def handle_scatter_biome_vegetation(params: dict) -> dict:
    """Scatter per-biome vegetation on terrain using quality placement.

    Combines biome vegetation sets with Poisson disk sampling, slope/height
    filtering, and optional wind vertex color baking.

    Params:
        terrain_name (str): Existing terrain object name.
        biome_name (str): Key into BIOME_VEGETATION_SETS.
        min_distance (float, default 3.0): Minimum distance between instances.
        seed (int, default 42): Random seed.
        max_instances (int, default 5000): Cap on total instances.
        season (str, optional): Season variant (summer/autumn/winter/corrupted).
        bake_wind_colors (bool, default False): Whether to compute wind vertex
            colors on tree instances.
        water_level (float, default 0.05): Normalized height below which nothing
            is placed.

    Returns dict with: name, instance_count, vegetation_types, biome, season.
    """
    # Import bpy only inside handler (not at module level for testability)
    try:
        import bpy
        import bmesh
    except ImportError as exc:
        raise RuntimeError("handle_scatter_biome_vegetation requires Blender") from exc

    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    biome_name = params.get("biome_name")
    if not biome_name:
        raise ValueError("'biome_name' is required")

    min_distance = params.get("min_distance", 3.0)
    seed = params.get("seed", 42)
    max_instances = params.get("max_instances", 5000)
    season = params.get("season")
    bake_wind_colors = params.get("bake_wind_colors", False)
    water_level = params.get("water_level", _DEFAULT_WATER_LEVEL)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    # Extract terrain geometry
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Recalculate normals for accurate slope
    bm.normal_update()

    terrain_vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
    terrain_normals = [(v.normal.x, v.normal.y, v.normal.z) for v in bm.verts]
    terrain_faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()

    # Compute area bounds from terrain dimensions
    dims = obj.dimensions
    loc = obj.location
    half_x = dims.x / 2.0
    half_y = dims.y / 2.0
    area_bounds = (
        loc.x - half_x,
        loc.y - half_y,
        loc.x + half_x,
        loc.y + half_y,
    )

    # Compute placements
    placements = compute_vegetation_placement(
        terrain_vertices,
        terrain_faces,
        terrain_normals,
        biome_name,
        area_bounds,
        seed=seed,
        min_distance=min_distance,
        water_level=water_level,
    )

    # Cap instances
    if len(placements) > max_instances:
        placements = placements[:max_instances]

    # Create scatter collection
    scatter_coll_name = f"{terrain_name}_{biome_name}_vegetation"
    scatter_coll = bpy.data.collections.new(scatter_coll_name)
    bpy.context.scene.collection.children.link(scatter_coll)

    veg_counts: dict[str, int] = {}

    for p in placements:
        veg_key = f"{p['type']}_{p['style']}"
        veg_counts[veg_key] = veg_counts.get(veg_key, 0) + 1

        # Create simple placeholder mesh (real meshes come from procedural generators)
        placeholder_mesh = bpy.data.meshes.new(f"_veg_{veg_key}_{veg_counts[veg_key]:04d}")
        instance_bm = bmesh.new()
        bmesh.ops.create_cube(instance_bm, size=0.5)
        instance_bm.to_mesh(placeholder_mesh)
        instance_bm.free()

        instance = bpy.data.objects.new(
            f"{veg_key}_{veg_counts[veg_key]:04d}", placeholder_mesh,
        )
        instance.location = p["position"]
        s = p["scale"]
        instance.scale = (s, s, s)
        instance.rotation_euler = (0, 0, math.radians(p["rotation"]))

        scatter_coll.objects.link(instance)

    total_instances = sum(veg_counts.values())

    result: dict[str, Any] = {
        "name": scatter_coll_name,
        "instance_count": total_instances,
        "vegetation_types": veg_counts,
        "biome": biome_name,
    }

    if season:
        result["season"] = season

    return result
