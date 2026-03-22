"""World map generator with Voronoi-based region partitioning, biome assignment,
road connections, POI distribution, landmark system, and environmental
storytelling patterns.

NO bpy/bmesh imports. Fully testable without Blender.

Provides:
  - generate_world_map: Voronoi world map with regions, roads, and 300+ POIs
  - BIOME_TYPES: 10 biome definitions with terrain/vegetation/danger metadata
  - POI_TYPES: 12 POI category definitions with spawn rules
  - LANDMARK_TYPES: 5 landmark definitions with visibility/height metadata
  - STORYTELLING_PATTERNS: 4 environmental storytelling prop patterns
  - place_landmarks: Distribute landmarks across regions with spacing constraints
  - generate_storytelling_scene: Compute prop placements for a storytelling pattern
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Biome Definitions -- 10 biomes
# ---------------------------------------------------------------------------

BIOME_TYPES: dict[str, dict[str, Any]] = {
    "dark_forest": {
        "color": (0.1, 0.25, 0.08),
        "vegetation_density": 0.8,
        "danger_level": 3,
        "terrain_roughness": 0.3,
        "ambient": "fog",
    },
    "corrupted_swamp": {
        "color": (0.2, 0.15, 0.3),
        "vegetation_density": 0.6,
        "danger_level": 5,
        "terrain_roughness": 0.1,
        "ambient": "toxic_fog",
    },
    "volcanic_wastes": {
        "color": (0.4, 0.15, 0.05),
        "vegetation_density": 0.05,
        "danger_level": 7,
        "terrain_roughness": 0.7,
        "ambient": "smoke",
    },
    "frozen_peaks": {
        "color": (0.8, 0.85, 0.9),
        "vegetation_density": 0.1,
        "danger_level": 4,
        "terrain_roughness": 0.8,
        "ambient": "blizzard",
    },
    "ancient_ruins": {
        "color": (0.5, 0.45, 0.35),
        "vegetation_density": 0.3,
        "danger_level": 6,
        "terrain_roughness": 0.4,
        "ambient": "dust",
    },
    "haunted_moor": {
        "color": (0.25, 0.2, 0.25),
        "vegetation_density": 0.4,
        "danger_level": 5,
        "terrain_roughness": 0.2,
        "ambient": "spectral_fog",
    },
    "enchanted_glade": {
        "color": (0.15, 0.4, 0.2),
        "vegetation_density": 0.9,
        "danger_level": 1,
        "terrain_roughness": 0.15,
        "ambient": "fireflies",
    },
    "bone_desert": {
        "color": (0.7, 0.65, 0.5),
        "vegetation_density": 0.02,
        "danger_level": 6,
        "terrain_roughness": 0.5,
        "ambient": "heat_haze",
    },
    "crystal_caverns": {
        "color": (0.3, 0.5, 0.7),
        "vegetation_density": 0.15,
        "danger_level": 4,
        "terrain_roughness": 0.6,
        "ambient": "crystal_glow",
    },
    "blood_marsh": {
        "color": (0.35, 0.1, 0.1),
        "vegetation_density": 0.5,
        "danger_level": 8,
        "terrain_roughness": 0.15,
        "ambient": "blood_mist",
    },
}


# ---------------------------------------------------------------------------
# POI Type Definitions -- 12 types
# ---------------------------------------------------------------------------

POI_TYPES: dict[str, dict[str, Any]] = {
    "camp": {
        "frequency": 0.25,
        "min_spacing": 80.0,
        "danger_bias": -1,
        "props": ["tent", "campfire", "bedroll", "supply_crate"],
    },
    "ruins": {
        "frequency": 0.15,
        "min_spacing": 100.0,
        "danger_bias": 1,
        "props": ["broken_pillar", "crumbled_wall", "rubble_pile", "ancient_statue"],
    },
    "shrine": {
        "frequency": 0.10,
        "min_spacing": 150.0,
        "danger_bias": 0,
        "props": ["altar", "offering_bowl", "prayer_rug", "incense_burner"],
    },
    "boss_arena": {
        "frequency": 0.03,
        "min_spacing": 300.0,
        "danger_bias": 3,
        "props": ["fog_gate", "arena_marker", "bone_pile", "boss_throne"],
    },
    "treasure": {
        "frequency": 0.12,
        "min_spacing": 60.0,
        "danger_bias": 0,
        "props": ["chest", "hidden_cache", "gem_deposit", "coin_pile"],
    },
    "merchant": {
        "frequency": 0.05,
        "min_spacing": 200.0,
        "danger_bias": -2,
        "props": ["cart", "tent_large", "display_rack", "lantern_post"],
    },
    "dungeon_entrance": {
        "frequency": 0.04,
        "min_spacing": 250.0,
        "danger_bias": 2,
        "props": ["stone_doorway", "descending_stairs", "rusted_gate", "warning_sign"],
    },
    "watchtower": {
        "frequency": 0.06,
        "min_spacing": 180.0,
        "danger_bias": 0,
        "props": ["tower_base", "lookout_platform", "signal_fire", "banner_pole"],
    },
    "resource_node": {
        "frequency": 0.18,
        "min_spacing": 50.0,
        "danger_bias": 0,
        "props": ["ore_vein", "herb_cluster", "mushroom_patch", "crystal_node"],
    },
    "waystone": {
        "frequency": 0.04,
        "min_spacing": 250.0,
        "danger_bias": -1,
        "props": ["waystone_pillar", "teleport_circle", "rune_stone"],
    },
    "ambush_site": {
        "frequency": 0.08,
        "min_spacing": 120.0,
        "danger_bias": 2,
        "props": ["overturned_cart", "dead_horse", "scattered_loot"],
    },
    "graveyard": {
        "frequency": 0.06,
        "min_spacing": 150.0,
        "danger_bias": 2,
        "props": ["tombstone", "open_grave", "mausoleum_door", "wilted_flowers"],
    },
}


# ---------------------------------------------------------------------------
# Landmark Definitions -- 5 types
# ---------------------------------------------------------------------------

LANDMARK_TYPES: dict[str, dict[str, Any]] = {
    "giant_skeleton": {
        "min_height": 15.0,
        "visibility_range": 200.0,
        "props": ["rib_cage", "skull", "scattered_bones"],
    },
    "ancient_tree": {
        "min_height": 20.0,
        "visibility_range": 300.0,
        "props": ["hollow_trunk", "hanging_lanterns", "root_cave"],
    },
    "ruined_tower": {
        "min_height": 12.0,
        "visibility_range": 150.0,
        "props": ["broken_stairs", "collapsed_roof", "overgrown_wall"],
    },
    "glowing_crystal": {
        "min_height": 8.0,
        "visibility_range": 100.0,
        "emission": True,
        "props": ["crystal_cluster", "energy_field", "mineral_deposit"],
    },
    "smoke_column": {
        "min_height": 30.0,
        "visibility_range": 500.0,
        "props": ["burning_ruin", "volcanic_vent", "signal_fire_large"],
    },
}


# ---------------------------------------------------------------------------
# Environmental Storytelling Patterns -- 4 patterns
# ---------------------------------------------------------------------------

STORYTELLING_PATTERNS: dict[str, list[str]] = {
    "battlefield_aftermath": [
        "broken_weapons",
        "skeleton_scatter",
        "scorched_ground",
        "damaged_banner",
    ],
    "abandoned_camp": [
        "cold_campfire",
        "scattered_supplies",
        "torn_tent",
        "footprints_away",
    ],
    "blood_trail": [
        "blood_splatter",
        "drag_marks",
        "dropped_item",
        "final_bloodpool",
    ],
    "corruption_spread": [
        "corruption_crystal",
        "withered_vegetation",
        "dead_animals",
        "purple_fog",
    ],
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Region:
    """A Voronoi region in the world map."""

    name: str
    center: tuple[float, float]
    biome: str
    bounds: tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)
    area: float = 0.0


@dataclass
class RoadConnection:
    """A road connecting two regions."""

    from_region: str
    to_region: str
    waypoints: list[tuple[float, float]]
    distance: float
    road_type: str = "main"


@dataclass
class POIPlacement:
    """A placed point of interest."""

    poi_type: str
    position: tuple[float, float]
    region: str
    props: list[str]


@dataclass
class LandmarkPlacement:
    """A placed landmark in the world."""

    landmark_type: str
    position: tuple[float, float]
    height: float
    visibility_range: float
    region: str
    props: list[str]


@dataclass
class StorytellingScene:
    """A placed environmental storytelling scene."""

    pattern: str
    center: tuple[float, float]
    radius: float
    prop_placements: list[dict[str, Any]]
    region: str


@dataclass
class WorldMap:
    """Complete world map with regions, roads, and POIs."""

    regions: list[Region] = field(default_factory=list)
    connections: list[RoadConnection] = field(default_factory=list)
    poi_positions: list[POIPlacement] = field(default_factory=list)
    landmarks: list[LandmarkPlacement] = field(default_factory=list)
    storytelling_scenes: list[StorytellingScene] = field(default_factory=list)
    seed: int = 42
    map_size: float = 2000.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _distance_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _assign_to_nearest_center(
    x: float,
    y: float,
    centers: list[tuple[float, float]],
) -> int:
    """Return index of the nearest center to point (x, y)."""
    best_idx = 0
    best_dist = float("inf")
    for i, c in enumerate(centers):
        d = (x - c[0]) ** 2 + (y - c[1]) ** 2
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


def _compute_voronoi_regions(
    centers: list[tuple[float, float]],
    map_size: float,
    resolution: int = 100,
) -> list[tuple[float, float, float, float]]:
    """Compute approximate Voronoi region bounds via grid sampling.

    Returns list of (min_x, min_y, max_x, max_y) per center.
    """
    n = len(centers)
    bounds = [
        (float("inf"), float("inf"), float("-inf"), float("-inf"))
        for _ in range(n)
    ]
    step = map_size / resolution

    for gy in range(resolution):
        y = gy * step + step * 0.5
        for gx in range(resolution):
            x = gx * step + step * 0.5
            idx = _assign_to_nearest_center(x, y, centers)
            bmin_x, bmin_y, bmax_x, bmax_y = bounds[idx]
            bounds[idx] = (
                min(bmin_x, x - step * 0.5),
                min(bmin_y, y - step * 0.5),
                max(bmax_x, x + step * 0.5),
                max(bmax_y, y + step * 0.5),
            )

    return bounds


def _compute_region_adjacency(
    centers: list[tuple[float, float]],
    map_size: float,
    resolution: int = 100,
) -> set[tuple[int, int]]:
    """Find adjacent Voronoi regions via grid-neighbor test."""
    n = len(centers)
    step = map_size / resolution
    grid: list[list[int]] = []

    for gy in range(resolution):
        row: list[int] = []
        y = gy * step + step * 0.5
        for gx in range(resolution):
            x = gx * step + step * 0.5
            row.append(_assign_to_nearest_center(x, y, centers))
        grid.append(row)

    adjacency: set[tuple[int, int]] = set()
    for gy in range(resolution):
        for gx in range(resolution):
            cell = grid[gy][gx]
            for dy, dx in [(0, 1), (1, 0)]:
                ny, nx = gy + dy, gx + dx
                if 0 <= ny < resolution and 0 <= nx < resolution:
                    neighbor = grid[ny][nx]
                    if neighbor != cell:
                        key = (min(cell, neighbor), max(cell, neighbor))
                        adjacency.add(key)

    return adjacency


def _poisson_disk_2d(
    width: float,
    height: float,
    min_distance: float,
    rng: random.Random,
    max_attempts: int = 30,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> list[tuple[float, float]]:
    """Bridson's Poisson disk sampling for 2D blue-noise distribution."""
    cell_size = min_distance / math.sqrt(2)
    grid_w = max(1, int(math.ceil(width / cell_size)))
    grid_h = max(1, int(math.ceil(height / cell_size)))

    grid: list[int] = [-1] * (grid_w * grid_h)
    points: list[tuple[float, float]] = []
    active: list[int] = []

    def _grid_idx(x: float, y: float) -> int:
        gx = max(0, min(int(x / cell_size), grid_w - 1))
        gy = max(0, min(int(y / cell_size), grid_h - 1))
        return gy * grid_w + gx

    def _is_valid(x: float, y: float) -> bool:
        if x < 0 or x >= width or y < 0 or y >= height:
            return False
        gx = int(x / cell_size)
        gy = int(y / cell_size)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < grid_w and 0 <= ny < grid_h:
                    idx = grid[ny * grid_w + nx]
                    if idx != -1:
                        px, py = points[idx]
                        if (x - px) ** 2 + (y - py) ** 2 < min_distance ** 2:
                            return False
        return True

    x0 = rng.uniform(0, width)
    y0 = rng.uniform(0, height)
    points.append((x0, y0))
    grid[_grid_idx(x0, y0)] = 0
    active.append(0)

    while active:
        active_idx = rng.randint(0, len(active) - 1)
        point_idx = active[active_idx]
        px, py = points[point_idx]

        found = False
        for _ in range(max_attempts):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(min_distance, 2 * min_distance)
            nx = px + math.cos(angle) * dist
            ny = py + math.sin(angle) * dist
            if _is_valid(nx, ny):
                new_idx = len(points)
                points.append((nx, ny))
                grid[_grid_idx(nx, ny)] = new_idx
                active.append(new_idx)
                found = True
                break

        if not found:
            active.pop(active_idx)

    # Apply offset
    return [(x + offset_x, y + offset_y) for x, y in points]


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

def generate_world_map(
    num_regions: int = 6,
    map_size: float = 2000.0,
    seed: int = 42,
    min_pois: int = 300,
) -> WorldMap:
    """Generate a world map with distinct regions and POI distribution.

    Uses Voronoi-based region partitioning, biome assignment per region,
    road connections between adjacent regions, and POI distribution
    (300+ points: camps, ruins, shrines, boss arenas, treasure, merchants).

    Parameters
    ----------
    num_regions : int
        Number of Voronoi regions (default 6).
    map_size : float
        Square map edge length in world units (default 2000.0).
    seed : int
        Random seed for deterministic generation.
    min_pois : int
        Minimum number of POIs to distribute (default 300).

    Returns
    -------
    WorldMap
        Complete world map with regions, connections, poi_positions.
    """
    rng = random.Random(seed)
    num_regions = max(2, num_regions)

    # Generate Voronoi centers with minimum spacing
    margin = map_size * 0.1
    min_center_dist = map_size / (num_regions * 0.8)
    centers: list[tuple[float, float]] = []
    attempts = 0
    while len(centers) < num_regions and attempts < num_regions * 200:
        cx = rng.uniform(margin, map_size - margin)
        cy = rng.uniform(margin, map_size - margin)
        too_close = False
        for existing in centers:
            if _distance_2d((cx, cy), existing) < min_center_dist:
                too_close = True
                break
        if not too_close:
            centers.append((cx, cy))
        attempts += 1

    # Fallback: if we couldn't place enough, just add random
    while len(centers) < num_regions:
        cx = rng.uniform(margin, map_size - margin)
        cy = rng.uniform(margin, map_size - margin)
        centers.append((cx, cy))

    # Assign biomes
    biome_names = list(BIOME_TYPES.keys())
    rng.shuffle(biome_names)
    assigned_biomes = [
        biome_names[i % len(biome_names)] for i in range(num_regions)
    ]

    # Compute Voronoi bounds
    voronoi_bounds = _compute_voronoi_regions(centers, map_size)

    # Build Region objects
    regions: list[Region] = []
    for i, (center, biome, bounds) in enumerate(
        zip(centers, assigned_biomes, voronoi_bounds)
    ):
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        regions.append(Region(
            name=f"region_{i}_{biome}",
            center=center,
            biome=biome,
            bounds=bounds,
            area=round(w * h, 2),
        ))

    # Find adjacent regions and create road connections
    adjacency = _compute_region_adjacency(centers, map_size)
    connections: list[RoadConnection] = []
    for i, j in sorted(adjacency):
        c1 = centers[i]
        c2 = centers[j]
        mid = ((c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2)
        # Slightly curved road via midpoint offset
        offset_x = rng.uniform(-map_size * 0.02, map_size * 0.02)
        offset_y = rng.uniform(-map_size * 0.02, map_size * 0.02)
        mid_offset = (mid[0] + offset_x, mid[1] + offset_y)

        waypoints = [c1, mid_offset, c2]
        dist = _distance_2d(c1, mid_offset) + _distance_2d(mid_offset, c2)

        connections.append(RoadConnection(
            from_region=regions[i].name,
            to_region=regions[j].name,
            waypoints=waypoints,
            distance=round(dist, 2),
            road_type="main" if dist < map_size * 0.3 else "path",
        ))

    # Distribute POIs across regions using Poisson disk per region
    poi_positions: list[POIPlacement] = []
    poi_type_list = list(POI_TYPES.keys())

    for region in regions:
        biome_info = BIOME_TYPES[region.biome]
        danger = biome_info["danger_level"]

        # Compute region POI budget based on area proportion
        total_area = map_size * map_size
        region_fraction = max(0.01, region.area / total_area)
        region_poi_target = max(10, int(min_pois * region_fraction * 1.5))

        # Determine spacing based on region size
        rw = region.bounds[2] - region.bounds[0]
        rh = region.bounds[3] - region.bounds[1]
        spacing = max(15.0, min(rw, rh) / math.sqrt(region_poi_target))

        # Sample points
        points = _poisson_disk_2d(
            rw, rh, spacing, rng,
            offset_x=region.bounds[0],
            offset_y=region.bounds[1],
        )

        for px, py in points:
            # Verify point is actually in this region (Voronoi check)
            nearest = _assign_to_nearest_center(px, py, centers)
            if regions[nearest].name != region.name:
                continue

            # Pick POI type weighted by danger affinity
            chosen_type = _select_poi_type(poi_type_list, danger, rng)
            type_info = POI_TYPES[chosen_type]

            # Check minimum spacing against existing POIs of same type
            too_close = False
            for existing in poi_positions:
                if existing.poi_type == chosen_type:
                    if _distance_2d((px, py), existing.position) < type_info["min_spacing"]:
                        too_close = True
                        break
            if too_close:
                continue

            poi_positions.append(POIPlacement(
                poi_type=chosen_type,
                position=(round(px, 2), round(py, 2)),
                region=region.name,
                props=list(type_info["props"]),
            ))

    # Ensure we meet minimum POI count by adding more in sparse regions
    safety = 0
    while len(poi_positions) < min_pois and safety < min_pois * 2:
        safety += 1
        region = rng.choice(regions)
        rw = region.bounds[2] - region.bounds[0]
        rh = region.bounds[3] - region.bounds[1]
        px = rng.uniform(region.bounds[0], region.bounds[2])
        py = rng.uniform(region.bounds[1], region.bounds[3])

        nearest = _assign_to_nearest_center(px, py, centers)
        if regions[nearest].name != region.name:
            continue

        chosen_type = rng.choice(poi_type_list)
        type_info = POI_TYPES[chosen_type]

        too_close = False
        for existing in poi_positions:
            if existing.poi_type == chosen_type:
                if _distance_2d((px, py), existing.position) < type_info["min_spacing"] * 0.5:
                    too_close = True
                    break
        if too_close:
            continue

        poi_positions.append(POIPlacement(
            poi_type=chosen_type,
            position=(round(px, 2), round(py, 2)),
            region=region.name,
            props=list(type_info["props"]),
        ))

    return WorldMap(
        regions=regions,
        connections=connections,
        poi_positions=poi_positions,
        seed=seed,
        map_size=map_size,
    )


def _select_poi_type(
    poi_types: list[str],
    danger_level: int,
    rng: random.Random,
) -> str:
    """Select a POI type weighted by danger affinity."""
    weights: list[float] = []
    for pt in poi_types:
        info = POI_TYPES[pt]
        freq = info["frequency"]
        # Danger bias: positive = prefers dangerous, negative = prefers safe
        bias = info["danger_bias"]
        # Weight: frequency * danger alignment
        alignment = 1.0 + 0.1 * bias * danger_level
        weights.append(max(0.01, freq * alignment))

    total = sum(weights)
    r = rng.uniform(0, total)
    cumulative = 0.0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return poi_types[i]
    return poi_types[-1]


# ---------------------------------------------------------------------------
# Landmark placement
# ---------------------------------------------------------------------------

def place_landmarks(
    world_map: WorldMap,
    landmarks_per_region: int = 1,
    seed: int | None = None,
) -> list[LandmarkPlacement]:
    """Distribute landmarks across world map regions with spacing constraints.

    Parameters
    ----------
    world_map : WorldMap
        The generated world map.
    landmarks_per_region : int
        Target landmarks per region (default 1).
    seed : int or None
        Random seed (defaults to world_map.seed).

    Returns
    -------
    list of LandmarkPlacement
        Placed landmarks with positions and metadata.
    """
    rng = random.Random(seed if seed is not None else world_map.seed + 1000)
    landmark_types_list = list(LANDMARK_TYPES.keys())
    placements: list[LandmarkPlacement] = []

    for region in world_map.regions:
        for _ in range(landmarks_per_region):
            # Pick landmark type
            lm_type = rng.choice(landmark_types_list)
            lm_info = LANDMARK_TYPES[lm_type]

            # Position near region center with some offset
            rw = region.bounds[2] - region.bounds[0]
            rh = region.bounds[3] - region.bounds[1]
            px = region.center[0] + rng.uniform(-rw * 0.3, rw * 0.3)
            py = region.center[1] + rng.uniform(-rh * 0.3, rh * 0.3)

            # Clamp to region bounds
            px = max(region.bounds[0], min(px, region.bounds[2]))
            py = max(region.bounds[1], min(py, region.bounds[3]))

            # Check spacing against existing landmarks
            vis_range = lm_info["visibility_range"]
            too_close = False
            for existing in placements:
                if _distance_2d((px, py), existing.position) < vis_range * 0.5:
                    too_close = True
                    break
            if too_close:
                continue

            height = lm_info["min_height"] + rng.uniform(0, lm_info["min_height"] * 0.5)

            placements.append(LandmarkPlacement(
                landmark_type=lm_type,
                position=(round(px, 2), round(py, 2)),
                height=round(height, 2),
                visibility_range=vis_range,
                region=region.name,
                props=list(lm_info["props"]),
            ))

    return placements


# ---------------------------------------------------------------------------
# Environmental storytelling scene generation
# ---------------------------------------------------------------------------

def generate_storytelling_scene(
    pattern_name: str,
    center: tuple[float, float],
    radius: float = 10.0,
    region_name: str = "",
    seed: int = 42,
) -> StorytellingScene:
    """Compute prop placements for an environmental storytelling pattern.

    Parameters
    ----------
    pattern_name : str
        One of the keys in STORYTELLING_PATTERNS.
    center : tuple
        (x, y) world position for the scene center.
    radius : float
        Scatter radius for props (default 10.0).
    region_name : str
        Name of the region this scene belongs to.
    seed : int
        Random seed.

    Returns
    -------
    StorytellingScene
        Scene with prop placements.

    Raises
    ------
    ValueError
        If pattern_name is not in STORYTELLING_PATTERNS.
    """
    if pattern_name not in STORYTELLING_PATTERNS:
        raise ValueError(
            f"Unknown storytelling pattern '{pattern_name}'. "
            f"Valid patterns: {sorted(STORYTELLING_PATTERNS.keys())}"
        )

    rng = random.Random(seed)
    props = STORYTELLING_PATTERNS[pattern_name]
    prop_placements: list[dict[str, Any]] = []

    for i, prop_type in enumerate(props):
        # Distribute props in a roughly sequential path for trail patterns
        if pattern_name == "blood_trail":
            # Linear distribution along a direction
            angle = rng.uniform(0, 2 * math.pi)
            t = (i + 1) / len(props)
            dist = radius * t
            px = center[0] + math.cos(angle) * dist
            py = center[1] + math.sin(angle) * dist
        else:
            # Circular scatter
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(0, radius)
            px = center[0] + math.cos(angle) * dist
            py = center[1] + math.sin(angle) * dist

        rotation = rng.uniform(0, 360)
        scale = rng.uniform(0.8, 1.2)

        prop_placements.append({
            "type": prop_type,
            "position": (round(px, 2), round(py, 2)),
            "rotation": round(rotation, 2),
            "scale": round(scale, 2),
        })

    return StorytellingScene(
        pattern=pattern_name,
        center=center,
        radius=radius,
        prop_placements=prop_placements,
        region=region_name,
    )


# ---------------------------------------------------------------------------
# Serialization helpers (for handler integration)
# ---------------------------------------------------------------------------

def world_map_to_dict(world_map: WorldMap) -> dict[str, Any]:
    """Convert a WorldMap to a JSON-serializable dict."""
    return {
        "seed": world_map.seed,
        "map_size": world_map.map_size,
        "num_regions": len(world_map.regions),
        "num_connections": len(world_map.connections),
        "num_pois": len(world_map.poi_positions),
        "num_landmarks": len(world_map.landmarks),
        "num_storytelling_scenes": len(world_map.storytelling_scenes),
        "regions": [
            {
                "name": r.name,
                "center": r.center,
                "biome": r.biome,
                "bounds": r.bounds,
                "area": r.area,
            }
            for r in world_map.regions
        ],
        "connections": [
            {
                "from_region": c.from_region,
                "to_region": c.to_region,
                "waypoints": c.waypoints,
                "distance": c.distance,
                "road_type": c.road_type,
            }
            for c in world_map.connections
        ],
        "poi_positions": [
            {
                "poi_type": p.poi_type,
                "position": p.position,
                "region": p.region,
                "props": p.props,
            }
            for p in world_map.poi_positions
        ],
        "landmarks": [
            {
                "landmark_type": lm.landmark_type,
                "position": lm.position,
                "height": lm.height,
                "visibility_range": lm.visibility_range,
                "region": lm.region,
                "props": lm.props,
            }
            for lm in world_map.landmarks
        ],
        "storytelling_scenes": [
            {
                "pattern": s.pattern,
                "center": s.center,
                "radius": s.radius,
                "prop_placements": s.prop_placements,
                "region": s.region,
            }
            for s in world_map.storytelling_scenes
        ],
    }
