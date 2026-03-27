"""World map composition system for generating complete game worlds.

Places settlements, dungeons, landmarks, and POIs on terrain with:
- Biome-aware placement (towns in flat areas, dungeons in mountains)
- Minimum distance between settlements (no clustering)
- Road network connecting settlements
- Point-of-interest density control
- Terrain-aware height placement

Inspired by: Houdini scatter + No Man's Sky biome placement + Skyrim world design.

NO bpy/bmesh imports. Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# VeilBreakers biome types
# ---------------------------------------------------------------------------

VB_BIOMES = [
    "thornwood_forest",
    "corrupted_swamp",
    "mountain_pass",
    "ruined_fortress",
    "abandoned_village",
    "veil_crack_zone",
    "underground_dungeon",
    "sacred_shrine",
    "battlefield",
    "cemetery",
    "desert_wastes",
    "jungle_overgrowth",
    "mushroom_forest",
    "crystal_cavern",
    "coastal_cliffs",
    "rolling_plains",
    "ancient_deep_forest",
    "underwater_ruins",
    "floating_islands",
    "void_wasteland",
    "volcanic_caldera",
]

VEIL_PRESSURE_BANDS: dict[str, tuple[float, float]] = {
    "safehold": (0.0, 0.24),
    "frontier": (0.24, 0.5),
    "contested": (0.5, 0.76),
    "veil_belt": (0.76, 1.01),
}

# ---------------------------------------------------------------------------
# POI placement rules
# ---------------------------------------------------------------------------

POI_PLACEMENT_RULES: dict[str, dict[str, Any]] = {
    "village": {
        "preferred_biomes": ["thornwood_forest", "corrupted_swamp"],
        "min_slope": 0,
        "max_slope": 15,
        "min_distance_from_others": 80.0,
        "near_water": True,
        "elevation_range": (0.1, 0.4),
        "preferred_pressure_range": (0.0, 0.42),
    },
    "town": {
        "preferred_biomes": ["thornwood_forest"],
        "min_slope": 0,
        "max_slope": 10,
        "min_distance_from_others": 120.0,
        "near_water": True,
        "elevation_range": (0.1, 0.3),
        "preferred_pressure_range": (0.1, 0.5),
    },
    "bandit_camp": {
        "preferred_biomes": ["corrupted_swamp", "thornwood_forest", "battlefield"],
        "min_slope": 0,
        "max_slope": 25,
        "min_distance_from_others": 40.0,
        "near_water": False,
        "elevation_range": (0.2, 0.6),
        "preferred_pressure_range": (0.25, 0.78),
    },
    "dungeon_entrance": {
        "preferred_biomes": ["mountain_pass", "ruined_fortress", "underground_dungeon"],
        "min_slope": 10,
        "max_slope": 45,
        "min_distance_from_others": 60.0,
        "near_water": False,
        "elevation_range": (0.3, 0.8),
        "preferred_pressure_range": (0.45, 1.0),
    },
    "shrine": {
        "preferred_biomes": ["sacred_shrine", "thornwood_forest"],
        "min_slope": 0,
        "max_slope": 20,
        "min_distance_from_others": 30.0,
        "near_water": False,
        "elevation_range": (0.2, 0.7),
        "preferred_pressure_range": (0.05, 0.7),
    },
    "veil_crack": {
        "preferred_biomes": ["veil_crack_zone"],
        "min_slope": 0,
        "max_slope": 60,
        "min_distance_from_others": 50.0,
        "near_water": False,
        "elevation_range": (0.4, 0.9),
        "preferred_pressure_range": (0.78, 1.0),
    },
    "castle": {
        "preferred_biomes": ["mountain_pass", "ruined_fortress"],
        "min_slope": 0,
        "max_slope": 20,
        "min_distance_from_others": 150.0,
        "near_water": False,
        "elevation_range": (0.5, 0.8),
        "preferred_pressure_range": (0.18, 0.72),
    },
    "desert_outpost": {
        "preferred_biomes": ["desert_wastes"],
        "min_slope": 0,
        "max_slope": 15,
        "min_distance_from_others": 90.0,
        "near_water": False,
        "elevation_range": (0.1, 0.4),
        "preferred_pressure_range": (0.1, 0.6),
    },
    "jungle_shrine": {
        "preferred_biomes": ["jungle_overgrowth"],
        "min_slope": 0,
        "max_slope": 25,
        "min_distance_from_others": 40.0,
        "near_water": True,
        "elevation_range": (0.1, 0.5),
        "preferred_pressure_range": (0.2, 0.7),
    },
    "mushroom_grove": {
        "preferred_biomes": ["mushroom_forest"],
        "min_slope": 0,
        "max_slope": 20,
        "min_distance_from_others": 35.0,
        "near_water": False,
        "elevation_range": (0.2, 0.6),
        "preferred_pressure_range": (0.3, 0.8),
    },
    "crystal_node": {
        "preferred_biomes": ["crystal_cavern"],
        "min_slope": 5,
        "max_slope": 40,
        "min_distance_from_others": 45.0,
        "near_water": False,
        "elevation_range": (0.3, 0.7),
        "preferred_pressure_range": (0.5, 1.0),
    },
    "coastal_watchtower": {
        "preferred_biomes": ["coastal_cliffs"],
        "min_slope": 5,
        "max_slope": 35,
        "min_distance_from_others": 70.0,
        "near_water": True,
        "elevation_range": (0.3, 0.7),
        "preferred_pressure_range": (0.1, 0.5),
    },
    "plains_camp": {
        "preferred_biomes": ["rolling_plains"],
        "min_slope": 0,
        "max_slope": 10,
        "min_distance_from_others": 60.0,
        "near_water": False,
        "elevation_range": (0.1, 0.3),
        "preferred_pressure_range": (0.0, 0.4),
    },
    "ancient_tree_hollow": {
        "preferred_biomes": ["ancient_deep_forest"],
        "min_slope": 0,
        "max_slope": 20,
        "min_distance_from_others": 50.0,
        "near_water": False,
        "elevation_range": (0.2, 0.5),
        "preferred_pressure_range": (0.15, 0.65),
    },
    "sunken_altar": {
        "preferred_biomes": ["underwater_ruins"],
        "min_slope": 0,
        "max_slope": 15,
        "min_distance_from_others": 55.0,
        "near_water": True,
        "elevation_range": (0.0, 0.2),
        "preferred_pressure_range": (0.4, 0.9),
    },
    "sky_fragment": {
        "preferred_biomes": ["floating_islands"],
        "min_slope": 0,
        "max_slope": 50,
        "min_distance_from_others": 80.0,
        "near_water": False,
        "elevation_range": (0.7, 1.0),
        "preferred_pressure_range": (0.5, 1.0),
    },
    "void_rift": {
        "preferred_biomes": ["void_wasteland"],
        "min_slope": 0,
        "max_slope": 60,
        "min_distance_from_others": 65.0,
        "near_water": False,
        "elevation_range": (0.3, 0.9),
        "preferred_pressure_range": (0.78, 1.0),
    },
    "volcanic_vent": {
        "preferred_biomes": ["volcanic_caldera"],
        "min_slope": 10,
        "max_slope": 50,
        "min_distance_from_others": 55.0,
        "near_water": False,
        "elevation_range": (0.4, 0.9),
        "preferred_pressure_range": (0.6, 1.0),
    },
}

# Settlement types that get road connections
_SETTLEMENT_TYPES = {"village", "town", "castle"}

# Max rejection-sampling attempts per POI
_MAX_PLACEMENT_ATTEMPTS = 500


# ---------------------------------------------------------------------------
# Biome assignment from position + noise
# ---------------------------------------------------------------------------

def _get_biome_at(
    x: float,
    y: float,
    width: float,
    height: float,
    seed: int = 0,
) -> str:
    """Determine biome at world position using layered noise.

    Uses a simple hash-based noise approach (no external dependencies)
    to assign biomes based on position.  The world is loosely partitioned
    into biome zones by combining normalised coordinates with a noise
    value, then mapping the result to the VB biome list.

    Parameters
    ----------
    x, y : float
        World position.
    width, height : float
        Total world dimensions for normalisation.
    seed : int
        Seed mixed into the hash for determinism.

    Returns
    -------
    str
        One of the VeilBreakers biome names from :data:`VB_BIOMES`.
    """
    # Normalise to [0, 1]
    nx = x / max(width, 1.0)
    ny = y / max(height, 1.0)

    # Hash-based pseudo-noise for deterministic biome variation
    raw = _hash_noise_2d(nx * 4.0, ny * 4.0, seed)  # [-1, 1]
    # Combine position gradient with noise
    combined = (nx * 0.3 + ny * 0.3 + raw * 0.4 + 1.0) / 2.0  # [0, 1]
    idx = int(combined * len(VB_BIOMES)) % len(VB_BIOMES)
    return VB_BIOMES[idx]


def _veil_pressure_at(
    x: float,
    y: float,
    width: float,
    height: float,
    seed: int = 0,
) -> float:
    """Compute pressure from the Veil, normalized to [0, 1]."""
    nx = x / max(width, 1.0)
    ny = y / max(height, 1.0)
    directional = nx * 0.82 + abs(ny - 0.5) * 0.08
    noise = (_hash_noise_2d(nx * 4.0, ny * 4.0, seed) + 1.0) * 0.5
    pressure = directional * 0.8 + noise * 0.2
    return max(0.0, min(1.0, pressure))


def _pressure_band(pressure: float) -> str:
    for band, (lo, hi) in VEIL_PRESSURE_BANDS.items():
        if lo <= pressure < hi:
            return band
    return "veil_belt"


def _corruption_variant_for_pressure(biome: str, pressure: float, rng: random.Random) -> str:
    if pressure < 0.24:
        return "healthy"
    if pressure < 0.5:
        return rng.choice(["weathered", "strained"])
    if pressure < 0.76:
        return rng.choice(["corrupted", "blighted"])
    return rng.choice(["veil-touched", "void-stained", "blighted"])


def _hash_noise_2d(x: float, y: float, seed: int = 0) -> float:
    """Deterministic pseudo-noise via integer hashing.  Returns [-1, 1].

    Uses a custom integer hash instead of Python's hash() which is
    non-deterministic across processes (PYTHONHASHSEED randomization).
    """
    # Custom deterministic hash — Robert Jenkins' 32-bit integer hash
    ix = int(round(x, 4) * 10000) & 0xFFFFFFFF
    iy = int(round(y, 4) * 10000) & 0xFFFFFFFF
    h = (ix * 73856093) ^ (iy * 19349669) ^ (seed * 83492791)
    h = ((h >> 16) ^ h) * 0x45D9F3B
    h = ((h >> 16) ^ h) * 0x45D9F3B
    h = (h >> 16) ^ h
    # Map to [-1, 1] (divide by 0xFFFFFFFF to stay within bounds)
    return ((h & 0xFFFFFFFF) / 0xFFFFFFFF) * 2.0 - 1.0


# ---------------------------------------------------------------------------
# Heightmap utilities
# ---------------------------------------------------------------------------

def _sample_heightmap(
    heightmap: list[list[float]] | None,
    x: float,
    y: float,
    width: float,
    height: float,
) -> float:
    """Sample the heightmap at world coordinates.  Returns 0-1."""
    if heightmap is None or len(heightmap) == 0 or len(heightmap[0]) == 0:
        return 0.25  # default flat-ish elevation

    rows = len(heightmap)
    cols = len(heightmap[0])

    # Map world coords to grid indices
    gx = (x / max(width, 1.0)) * (cols - 1)
    gy = (y / max(height, 1.0)) * (rows - 1)

    # Bilinear interpolation
    gx0 = max(0, min(int(math.floor(gx)), cols - 1))
    gx1 = max(0, min(gx0 + 1, cols - 1))
    gy0 = max(0, min(int(math.floor(gy)), rows - 1))
    gy1 = max(0, min(gy0 + 1, rows - 1))

    fx = gx - gx0
    fy = gy - gy0

    v00 = heightmap[gy0][gx0]
    v10 = heightmap[gy0][gx1]
    v01 = heightmap[gy1][gx0]
    v11 = heightmap[gy1][gx1]

    return v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy) + v01 * (1 - fx) * fy + v11 * fx * fy


def _calculate_slope(
    heightmap: list[list[float]] | None,
    x: float,
    y: float,
    width: float,
    height: float,
) -> float:
    """Estimate terrain slope (in degrees) at world position from heightmap gradient.

    Computes the central-difference gradient at the nearest grid cell
    and converts the magnitude to degrees from horizontal.

    Parameters
    ----------
    heightmap : list[list[float]] | None
        2D grid of elevation values in [0, 1].
    x, y : float
        World position.
    width, height : float
        World dimensions.

    Returns
    -------
    float
        Slope in degrees [0, 90].  Returns 0 if no heightmap.
    """
    if heightmap is None or len(heightmap) < 2 or len(heightmap[0]) < 2:
        return 0.0

    rows = len(heightmap)
    cols = len(heightmap[0])

    # Map to grid indices
    gx = int((x / max(width, 1.0)) * (cols - 1))
    gy = int((y / max(height, 1.0)) * (rows - 1))
    gx = max(1, min(gx, cols - 2))
    gy = max(1, min(gy, rows - 2))

    # Central differences
    dx = (heightmap[gy][gx + 1] - heightmap[gy][gx - 1]) / 2.0
    dy = (heightmap[gy + 1][gx] - heightmap[gy - 1][gx]) / 2.0

    # Scale by grid cell size in world units
    cell_w = width / max(cols - 1, 1)
    cell_h = height / max(rows - 1, 1)
    dx /= max(cell_w, 1e-9)
    dy /= max(cell_h, 1e-9)

    magnitude = math.sqrt(dx * dx + dy * dy)
    slope_deg = math.degrees(math.atan(magnitude))
    return max(0.0, min(slope_deg, 90.0))


# ---------------------------------------------------------------------------
# POI placement via rejection sampling
# ---------------------------------------------------------------------------

def _distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx * dx + dy * dy)


def _find_valid_position(
    rng: random.Random,
    poi_type: str,
    existing_pois: list[dict[str, Any]],
    width: float,
    height: float,
    heightmap: list[list[float]] | None,
    rules: dict[str, Any],
    world_seed: int = 0,
) -> tuple[float, float] | None:
    """Find a valid placement position for a POI via rejection sampling.

    Tries random positions up to :data:`_MAX_PLACEMENT_ATTEMPTS` times,
    checking each against the placement rules (slope, elevation, biome,
    minimum distance).

    Parameters
    ----------
    rng : random.Random
        Seeded RNG for deterministic generation.
    poi_type : str
        Type key into :data:`POI_PLACEMENT_RULES`.
    existing_pois : list[dict]
        Already-placed POIs with ``"position"`` keys.
    width, height : float
        World bounds.
    heightmap : list[list[float]] | None
        Elevation grid.
    rules : dict
        Placement rule dict from :data:`POI_PLACEMENT_RULES`.

    Returns
    -------
    tuple[float, float] | None
        Valid (x, y) position, or None if no valid position found.
    """
    min_dist = rules.get("min_distance_from_others", 40.0)
    elev_lo, elev_hi = rules.get("elevation_range", (0.0, 1.0))
    slope_lo = rules.get("min_slope", 0.0)
    slope_hi = rules.get("max_slope", 90.0)
    preferred_biomes = rules.get("preferred_biomes", VB_BIOMES)
    pressure_lo, pressure_hi = rules.get("preferred_pressure_range", (0.0, 1.0))
    # Edge margin to avoid placing right on the boundary
    margin = min(width, height) * 0.05

    for _ in range(_MAX_PLACEMENT_ATTEMPTS):
        x = rng.uniform(margin, width - margin)
        y = rng.uniform(margin, height - margin)

        # --- Elevation check ---
        elev = _sample_heightmap(heightmap, x, y, width, height)
        if elev < elev_lo or elev > elev_hi:
            continue

        # --- Slope check ---
        slope = _calculate_slope(heightmap, x, y, width, height)
        if slope < slope_lo or slope > slope_hi:
            continue

        # --- Biome check ---
        biome = _get_biome_at(x, y, width, height, seed=world_seed)
        if biome not in preferred_biomes:
            # Allow placement with reduced probability even outside preferred biomes
            # This prevents impossible placement when biome zones don't cover enough area
            if rng.random() > 0.15:
                continue

        pressure = _veil_pressure_at(x, y, width, height, seed=world_seed)
        if pressure < pressure_lo or pressure > pressure_hi:
            if rng.random() > 0.2:
                continue

        # --- Minimum distance check ---
        too_close = False
        for existing in existing_pois:
            ex, ey = existing["position"]
            # Use the stricter of the two POIs' distance rules
            other_rules = POI_PLACEMENT_RULES.get(existing["type"], {})
            other_min = other_rules.get("min_distance_from_others", 0)
            effective_min = max(min_dist, other_min)
            if _distance((x, y), (ex, ey)) < effective_min:
                too_close = True
                break
        if too_close:
            continue

        return (x, y)

    return None


# ---------------------------------------------------------------------------
# Road network generation (MST + shortcuts)
# ---------------------------------------------------------------------------

def _generate_world_roads(
    pois: list[dict[str, Any]],
    width: float,
    height: float,
    heightmap: list[list[float]] | None = None,
    shortcut_count: int = 2,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Generate a road network connecting settlement POIs.

    Builds a minimum spanning tree (Prim's algorithm) over all settlement
    POIs, then adds a configurable number of shortcut edges for gameplay
    variety.  Non-settlement POIs (shrines, dungeons, etc.) are optionally
    connected to their nearest settlement if within range.

    Parameters
    ----------
    pois : list[dict]
        Placed POIs with ``"name"``, ``"type"``, ``"position"`` keys.
    width, height : float
        World dimensions (used for terrain cost estimation).
    heightmap : list[list[float]] | None
        Elevation grid for terrain-weighted road costs.
    shortcut_count : int
        Number of extra non-MST roads to add (default 2).
    seed : int
        Random seed.

    Returns
    -------
    list[dict]
        Road segments: ``{"from": str, "to": str, "distance": float,
        "road_type": str, "waypoints": list}``.
    """
    rng = random.Random(seed)

    # Separate settlements from non-settlements
    settlements = [p for p in pois if p["type"] in _SETTLEMENT_TYPES]
    non_settlements = [p for p in pois if p["type"] not in _SETTLEMENT_TYPES]

    roads: list[dict[str, Any]] = []

    if len(settlements) < 2:
        # Still connect non-settlements to their nearest settlement if one exists
        if settlements and non_settlements:
            for ns in non_settlements:
                nsx, nsy = ns["position"]
                sx, sy = settlements[0]["position"]
                dist = math.sqrt((nsx - sx) ** 2 + (nsy - sy) ** 2)
                if dist < 200.0:
                    roads.append({
                        "start": ns["position"], "end": settlements[0]["position"],
                        "width": 1.0, "style": "trail", "type": "trail",
                    })
        return roads

    n = len(settlements)

    # Build weighted distance matrix (terrain-aware)
    dist_matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(0.0)
            else:
                d = _distance(settlements[i]["position"], settlements[j]["position"])
                # Add terrain cost: penalise roads through steep terrain
                cost = _road_terrain_cost(
                    settlements[i]["position"],
                    settlements[j]["position"],
                    heightmap, width, height,
                )
                row.append(d * (1.0 + cost * 0.5))
        dist_matrix.append(row)

    # --- Prim's MST ---
    in_tree = [False] * n
    in_tree[0] = True
    mst_edges: list[tuple[int, int, float]] = []

    for _ in range(n - 1):
        best: tuple[int, int, float] | None = None
        for i in range(n):
            if not in_tree[i]:
                continue
            for j in range(n):
                if in_tree[j]:
                    continue
                w = dist_matrix[i][j]
                if best is None or w < best[2]:
                    best = (i, j, w)
        if best is None:
            break
        mst_edges.append(best)
        in_tree[best[1]] = True

    # Build edge set
    edge_set: set[tuple[int, int]] = set()
    roads: list[dict[str, Any]] = []
    for i, j, w in mst_edges:
        key = (min(i, j), max(i, j))
        edge_set.add(key)
        raw_dist = _distance(settlements[i]["position"], settlements[j]["position"])
        roads.append({
            "from": settlements[i]["name"],
            "to": settlements[j]["name"],
            "distance": round(raw_dist, 2),
            "road_type": "main",
            "waypoints": _generate_road_waypoints(
                settlements[i]["position"],
                settlements[j]["position"],
                heightmap, width, height, rng,
            ),
        })

    # --- Shortcut roads ---
    # Collect non-MST edges sorted by distance, pick top shortcut_count
    candidates: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) not in edge_set:
                raw_dist = _distance(
                    settlements[i]["position"],
                    settlements[j]["position"],
                )
                candidates.append((i, j, raw_dist))

    candidates.sort(key=lambda e: e[2])
    added = 0
    for i, j, d in candidates:
        if added >= shortcut_count:
            break
        edge_set.add((i, j))
        roads.append({
            "from": settlements[i]["name"],
            "to": settlements[j]["name"],
            "distance": round(d, 2),
            "road_type": "shortcut",
            "waypoints": _generate_road_waypoints(
                settlements[i]["position"],
                settlements[j]["position"],
                heightmap, width, height, rng,
            ),
        })
        added += 1

    # --- Connect non-settlement POIs to nearest settlement ---
    _connect_range = 200.0  # max distance to connect a non-settlement
    for ns in non_settlements:
        nearest_s: dict[str, Any] | None = None
        nearest_d = float("inf")
        for s in settlements:
            d = _distance(ns["position"], s["position"])
            if d < nearest_d:
                nearest_d = d
                nearest_s = s
        if nearest_s is not None and nearest_d <= _connect_range:
            roads.append({
                "from": ns["name"],
                "to": nearest_s["name"],
                "distance": round(nearest_d, 2),
                "road_type": "trail",
                "waypoints": _generate_road_waypoints(
                    ns["position"],
                    nearest_s["position"],
                    heightmap, width, height, rng,
                ),
            })

    return roads


def _road_terrain_cost(
    p1: tuple[float, float],
    p2: tuple[float, float],
    heightmap: list[list[float]] | None,
    width: float,
    height: float,
    samples: int = 5,
) -> float:
    """Estimate average slope along a straight line between two points.

    Used to penalise roads that cross steep terrain.

    Returns
    -------
    float
        Average slope in degrees divided by 45 (normalised cost, 0-2 range).
    """
    if heightmap is None:
        return 0.0

    total_slope = 0.0
    for i in range(samples):
        t = (i + 0.5) / samples
        sx = p1[0] + (p2[0] - p1[0]) * t
        sy = p1[1] + (p2[1] - p1[1]) * t
        total_slope += _calculate_slope(heightmap, sx, sy, width, height)

    avg_slope = total_slope / samples
    return avg_slope / 45.0


def _generate_road_waypoints(
    p1: tuple[float, float],
    p2: tuple[float, float],
    heightmap: list[list[float]] | None,
    width: float,
    height: float,
    rng: random.Random,
    segments: int = 4,
) -> list[tuple[float, float, float]]:
    """Generate waypoints along a road with slight random deviation.

    Returns 3D waypoints (x, y, z) where z is sampled from the heightmap.
    Roads get a gentle lateral wobble for organic appearance.
    """
    waypoints: list[tuple[float, float, float]] = []
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-6:
        z = _sample_heightmap(heightmap, p1[0], p1[1], width, height)
        return [(p1[0], p1[1], z)]

    # Perpendicular direction for lateral deviation
    perp_x = -dy / length
    perp_y = dx / length
    max_deviation = length * 0.05  # up to 5% lateral wobble

    for i in range(segments + 1):
        t = i / segments
        wx = p1[0] + dx * t
        wy = p1[1] + dy * t

        # Add lateral deviation (except at endpoints)
        if 0 < i < segments:
            offset = rng.uniform(-max_deviation, max_deviation)
            wx += perp_x * offset
            wy += perp_y * offset

        # Clamp to world bounds
        wx = max(0.0, min(wx, width))
        wy = max(0.0, min(wy, height))

        wz = _sample_heightmap(heightmap, wx, wy, width, height)
        waypoints.append((round(wx, 2), round(wy, 2), round(wz, 4)))

    return waypoints


def _generate_world_features(
    pois: list[dict[str, Any]],
    roads: list[dict[str, Any]],
    width: float,
    height: float,
    heightmap: list[list[float]] | None,
    seed: int,
) -> list[dict[str, Any]]:
    """Derive AAA-style world features from the placed POIs and roads.

    The map compiler should not stop at settlements and road segments. It
    should also emit the higher-level pieces that make a world feel built:
    farm belts, fences, camp perimeters, watch posts, market quarters, and
    bridge crossings.
    """
    rng = random.Random(seed + 0x5F3759DF)
    poi_lookup = {poi["name"]: poi for poi in pois}
    features: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    def add_feature(
        feature_type: str,
        anchor: str,
        position: tuple[float, float],
        *,
        style: str = "default",
        scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
        rotation: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        idx = counts.get(feature_type, 0)
        counts[feature_type] = idx + 1
        poi = poi_lookup.get(anchor)
        pressure = float(poi.get("pressure", 0.5)) if poi else 0.5
        pressure_band = poi.get("pressure_band", "frontier") if poi else "frontier"
        biome_variant = poi.get("biome_variant", "clean") if poi else "clean"
        px = max(0.0, min(width, position[0]))
        py = max(0.0, min(height, position[1]))
        features.append({
            "name": f"{anchor}_{feature_type}_{idx + 1}",
            "type": feature_type,
            "anchor": anchor,
            "position": (round(px, 2), round(py, 2)),
            "rotation": round(rotation, 3),
            "scale": tuple(round(v, 3) for v in scale),
            "style": style,
            "pressure": round(pressure, 4),
            "pressure_band": pressure_band,
            "biome_variant": biome_variant,
            "details": details or {},
        })

    settlement_feature_map: dict[str, list[tuple[str, str]]] = {
        "village": [
            ("farm_belt", "village_outskirts"),
            ("fence_line", "wooden_picket"),
        ],
        "town": [
            ("market_quarter", "market"),
            ("fence_line", "wooden_picket"),
            ("milestone", "road_marker"),
        ],
        "castle": [
            ("bridge_crossing", "stone"),
            ("lookout_post", "fortified"),
            ("fence_line", "iron_wrought"),
        ],
        "bandit_camp": [
            ("camp_perimeter", "rough"),
            ("barricade_line", "spiked"),
            ("lookout_post", "raised"),
        ],
        "dungeon_entrance": [
            ("bridge_crossing", "rope"),
            ("barricade_line", "stone"),
            ("milestone", "warning_marker"),
        ],
        "shrine": [
            ("sacrificial_circle", "sanctified"),
            ("waystone", "sanctified"),
        ],
        "veil_crack": [
            ("corruption_crystal", "veil-touched"),
            ("dark_obelisk", "veil-touched"),
            ("barricade_line", "ruined"),
        ],
    }

    for poi in pois:
        poi_type = poi["type"]
        if poi_type not in settlement_feature_map:
            continue

        x, y = poi["position"]
        pressure = float(poi.get("pressure", 0.5))
        band = poi.get("pressure_band", "frontier")
        base_rotation = rng.uniform(0.0, math.tau)
        scale_bias = 1.0 + (pressure - 0.5) * 0.25

        for offset_idx, (feature_type, style) in enumerate(settlement_feature_map[poi_type]):
            offset_angle = base_rotation + (offset_idx * math.tau / max(1, len(settlement_feature_map[poi_type])))
            offset_dist = 10.0 + (offset_idx * 4.0) + (pressure * 10.0)
            fx = x + math.cos(offset_angle) * offset_dist
            fy = y + math.sin(offset_angle) * offset_dist
            details = {
                "poi_type": poi_type,
                "pressure_band": band,
                "biome": poi.get("biome"),
            }

            if feature_type == "farm_belt":
                add_feature(
                    feature_type,
                    poi["name"],
                    (fx, fy),
                    style=style,
                    scale=(1.3 * scale_bias, 1.0 * scale_bias, 1.0),
                    rotation=offset_angle,
                    details={**details, "plot_count": 3},
                )
            elif feature_type == "market_quarter":
                add_feature(
                    feature_type,
                    poi["name"],
                    (fx, fy),
                    style=style,
                    scale=(1.2 * scale_bias, 1.0 * scale_bias, 1.0),
                    rotation=offset_angle,
                    details={**details, "stall_rows": 4},
                )
            elif feature_type == "camp_perimeter":
                add_feature(
                    feature_type,
                    poi["name"],
                    (fx, fy),
                    style=style,
                    scale=(1.0 * scale_bias, 1.0 * scale_bias, 1.0),
                    rotation=offset_angle,
                    details={**details, "tent_count": 4},
                )
            elif feature_type == "bridge_crossing":
                add_feature(
                    feature_type,
                    poi["name"],
                    (fx, fy),
                    style="stone" if poi_type in {"castle", "town"} else "rope",
                    scale=(1.0 + pressure * 0.3, 1.0, 1.0),
                    rotation=offset_angle,
                    details={**details, "crossing_role": poi_type},
                )
            else:
                add_feature(
                    feature_type,
                    poi["name"],
                    (fx, fy),
                    style=style,
                    scale=(scale_bias, scale_bias, 1.0),
                    rotation=offset_angle,
                    details=details,
                )

    # Road-derived features: bridge crossings and approach markers.
    for road in roads:
        waypoints = road.get("waypoints", [])
        if len(waypoints) < 2:
            continue
        start = waypoints[0]
        end = waypoints[-1]
        mid = waypoints[len(waypoints) // 2]
        sx, sy = start[0], start[1]
        ex, ey = end[0], end[1]
        mx, my = mid[0], mid[1]
        road_length = _distance((sx, sy), (ex, ey))
        if road_length < max(width, height) * 0.12:
            continue

        start_poi = poi_lookup.get(road.get("from", ""))
        end_poi = poi_lookup.get(road.get("to", ""))
        start_pressure = float(start_poi.get("pressure", 0.5)) if start_poi else 0.5
        end_pressure = float(end_poi.get("pressure", 0.5)) if end_poi else 0.5
        avg_pressure = (start_pressure + end_pressure) * 0.5

        z_values = [pt[2] if len(pt) >= 3 else 0.25 for pt in waypoints]
        valley_depth = (max(z_values[0], z_values[-1]) - min(z_values)) if z_values else 0.0
        bridge_style = "stone" if road.get("road_type") == "main" or avg_pressure < 0.55 else "rope"
        if heightmap is not None and (valley_depth > 0.04 or road.get("road_type") == "main"):
            add_feature(
                "bridge_crossing",
                road.get("from", road.get("to", "road")),
                (mx, my),
                style=bridge_style,
                scale=(1.0 + min(0.5, road_length / max(width, height) * 0.25), 1.0, 1.0),
                rotation=math.atan2(ey - sy, ex - sx),
                details={
                    "road_type": road.get("road_type", "path"),
                    "distance": road.get("distance", road_length),
                    "connected": [road.get("from"), road.get("to")],
                    "valley_depth": round(valley_depth, 4),
                },
            )
        if road_length > max(width, height) * 0.18:
            add_feature(
                "milestone",
                road.get("from", road.get("to", "road")),
                (
                    mx + math.cos(math.atan2(ey - sy, ex - sx)) * 4.0,
                    my + math.sin(math.atan2(ey - sy, ex - sx)) * 4.0,
                ),
                style="road_marker",
                scale=(0.8, 0.8, 0.8),
                rotation=math.atan2(ey - sy, ex - sx),
                details={
                    "road_type": road.get("road_type", "path"),
                    "distance": road.get("distance", road_length),
                    "connected": [road.get("from"), road.get("to")],
                },
            )

    return features


# ---------------------------------------------------------------------------
# Main composition function
# ---------------------------------------------------------------------------

def compose_world_map(
    width: float,
    height: float,
    poi_list: list[dict[str, Any]],
    seed: int | None = None,
    heightmap: list[list[float]] | None = None,
    shortcut_roads: int = 2,
) -> dict[str, Any]:
    """Compose a complete world map with intelligently placed locations.

    Takes a list of POI requests (type + count), places them according to
    biome, slope, and distance rules, then generates a road network
    connecting settlements.

    Parameters
    ----------
    width : float
        World width in units.
    height : float
        World height (depth) in units.
    poi_list : list[dict]
        Each dict has ``"type"`` (str) and ``"count"`` (int).
        Example: ``[{"type": "village", "count": 3}, ...]``
    seed : int | None
        Random seed for deterministic output.
    heightmap : list[list[float]] | None
        2D grid of elevation values in [0, 1].  If None, flat terrain
        is assumed.
    shortcut_roads : int
        Number of extra shortcut roads beyond the MST (default 2).

    Returns
    -------
    dict
        ``{"pois": [...], "roads": [...], "metadata": {...}}``

        Each POI: ``{"name": str, "type": str, "position": (x, y),
        "elevation": float, "biome": str, "slope": float}``

        Each road: ``{"from": str, "to": str, "distance": float,
        "road_type": str, "waypoints": [...]}``

        Metadata: ``{"seed": int, "world_size": (w, h),
        "total_pois_requested": int, "total_pois_placed": int,
        "placement_failures": list[dict], "road_count": int,
        "biome_distribution": dict[str, int]}``
    """
    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)

    placed_pois: list[dict[str, Any]] = []
    placement_failures: list[dict[str, Any]] = []
    total_requested = 0

    # Sort POI types by min_distance descending so that the most
    # space-demanding POIs (castles, towns) get placed first
    sorted_requests = sorted(
        poi_list,
        key=lambda p: POI_PLACEMENT_RULES.get(
            p["type"], {}
        ).get("min_distance_from_others", 0),
        reverse=True,
    )

    for request in sorted_requests:
        poi_type = request["type"]
        count = request.get("count", 1)
        total_requested += count

        rules = POI_PLACEMENT_RULES.get(poi_type)
        if rules is None:
            placement_failures.append({
                "type": poi_type,
                "reason": f"Unknown POI type: {poi_type}",
                "requested": count,
                "placed": 0,
            })
            continue

        placed_for_type = 0
        for i in range(count):
            pos = _find_valid_position(
                rng, poi_type, placed_pois, width, height, heightmap, rules,
                world_seed=seed if seed is not None else 0,
            )
            if pos is None:
                placement_failures.append({
                    "type": poi_type,
                    "reason": "No valid position found (exhausted attempts)",
                    "requested": count,
                    "placed": placed_for_type,
                })
                break

            x, y = pos
            elev = _sample_heightmap(heightmap, x, y, width, height)
            slope = _calculate_slope(heightmap, x, y, width, height)
            biome = _get_biome_at(x, y, width, height, seed=seed)
            pressure = _veil_pressure_at(x, y, width, height, seed=seed)

            placed_pois.append({
                "name": f"{poi_type}_{placed_for_type + 1}",
                "type": poi_type,
                "position": (round(x, 2), round(y, 2)),
                "elevation": round(elev, 4),
                "biome": biome,
                "slope": round(slope, 2),
                "pressure": round(pressure, 4),
                "pressure_band": _pressure_band(pressure),
                "biome_variant": _corruption_variant_for_pressure(biome, pressure, rng),
            })
            placed_for_type += 1

    # Generate road network
    roads = _generate_world_roads(
        placed_pois, width, height, heightmap,
        shortcut_count=shortcut_roads,
        seed=seed,
    )

    world_features = _generate_world_features(
        placed_pois,
        roads,
        width,
        height,
        heightmap,
        seed,
    )

    # Compute biome distribution
    biome_dist: dict[str, int] = {}
    for poi in placed_pois:
        b = poi["biome"]
        biome_dist[b] = biome_dist.get(b, 0) + 1

    feature_dist: dict[str, int] = {}
    for feature in world_features:
        feature_type = feature["type"]
        feature_dist[feature_type] = feature_dist.get(feature_type, 0) + 1

    return {
        "pois": placed_pois,
        "roads": roads,
        "world_features": world_features,
        "metadata": {
            "seed": seed,
            "world_size": (width, height),
            "veil_origin": (width * 0.92, height * 0.5),
            "safehold_origin": (width * 0.08, height * 0.5),
            "total_pois_requested": total_requested,
            "total_pois_placed": len(placed_pois),
            "placement_failures": placement_failures,
            "road_count": len(roads),
            "feature_count": len(world_features),
            "feature_distribution": feature_dist,
            "biome_distribution": biome_dist,
        },
    }


# ---------------------------------------------------------------------------
# Biome transition blending system
# ---------------------------------------------------------------------------

BIOME_TRANSITIONS: dict[tuple[str, str], dict[str, Any]] = {
    ("thornwood_forest", "corrupted_swamp"): {
        "props": ["dead_tree", "murky_pool", "moss_patch", "fungal_growth"],
        "density_modifier": 0.8,
        "description": "Dead trees, murky pools, moss",
    },
    ("mountain_pass", "thornwood_forest"): {
        "props": ["sparse_tree", "rocky_soil", "wind_bent_trunk", "fallen_boulder"],
        "density_modifier": 0.5,
        "description": "Sparse trees, rocky soil, wind-bent trunks",
    },
    ("sacred_shrine", "veil_crack_zone"): {
        "props": ["cracked_ground", "flickering_light", "corrupted_vegetation", "shattered_ward"],
        "density_modifier": 0.7,
        "description": "Cracked ground, flickering lights, corrupted vegetation",
    },
    ("thornwood_forest", "mountain_pass"): {
        "props": ["wind_bent_trunk", "rocky_soil", "sparse_tree", "alpine_shrub"],
        "density_modifier": 0.5,
        "description": "Sparse trees, rocky soil, wind-bent trunks",
    },
    ("corrupted_swamp", "veil_crack_zone"): {
        "props": ["toxic_pool", "corrupted_vegetation", "bone_scatter", "dark_mist"],
        "density_modifier": 0.9,
        "description": "Toxic pools, corrupted vegetation, bone scatter",
    },
    ("ruined_fortress", "battlefield"): {
        "props": ["rubble_pile", "broken_weapon", "scorched_earth", "crater"],
        "density_modifier": 0.6,
        "description": "Rubble, broken weapons, scorched earth",
    },
    ("cemetery", "corrupted_swamp"): {
        "props": ["broken_gravestone", "murky_pool", "bone_scatter", "dead_tree"],
        "density_modifier": 0.7,
        "description": "Broken gravestones, murky pools, bone scatter",
    },
    ("abandoned_village", "thornwood_forest"): {
        "props": ["overgrown_ruins", "fallen_log", "moss_patch", "wild_shrub"],
        "density_modifier": 0.55,
        "description": "Overgrown ruins, fallen logs, moss",
    },
    ("mountain_pass", "ruined_fortress"): {
        "props": ["rocky_soil", "rubble_pile", "fallen_boulder", "scorched_earth"],
        "density_modifier": 0.45,
        "description": "Rocky soil, rubble, fallen boulders",
    },
    ("sacred_shrine", "thornwood_forest"): {
        "props": ["prayer_stone", "wild_flower", "moss_patch", "sacred_tree"],
        "density_modifier": 0.35,
        "description": "Prayer stones, wild flowers, sacred trees",
    },
    ("veil_crack_zone", "underground_dungeon"): {
        "props": ["cracked_ground", "dark_mist", "corrupted_crystal", "bone_scatter"],
        "density_modifier": 0.85,
        "description": "Cracked ground, dark mist, corrupted crystals",
    },
    ("battlefield", "cemetery"): {
        "props": ["broken_weapon", "broken_gravestone", "scorched_earth", "bone_scatter"],
        "density_modifier": 0.65,
        "description": "Broken weapons, gravestones, scorched earth",
    },
}


def get_transition_props(
    biome_a: str,
    biome_b: str,
) -> dict[str, Any]:
    """Get props and density modifier for a biome transition zone.

    Looks up the transition in both directions (a->b and b->a).
    If no specific transition is defined, returns a generic transition set.

    Parameters
    ----------
    biome_a : str
        First biome name.
    biome_b : str
        Second biome name.

    Returns
    -------
    dict
        ``{"props": list[str], "density_modifier": float, "description": str}``
    """
    if biome_a == biome_b:
        return {"props": [], "density_modifier": 0.0, "description": "Same biome, no transition"}

    # Check both orderings
    key_ab = (biome_a, biome_b)
    key_ba = (biome_b, biome_a)

    if key_ab in BIOME_TRANSITIONS:
        return dict(BIOME_TRANSITIONS[key_ab])
    if key_ba in BIOME_TRANSITIONS:
        return dict(BIOME_TRANSITIONS[key_ba])

    # Generic fallback transition
    return {
        "props": ["dead_bush", "rock_small", "debris_pile", "fallen_log"],
        "density_modifier": 0.4,
        "description": f"Generic transition between {biome_a} and {biome_b}",
    }


def compute_biome_map(
    grid_size: int,
    biome_count: int = 6,
    seed: int = 42,
) -> list[list[dict[str, float]]]:
    """Compute a 2D biome weight map using Voronoi cells with domain-warped noise.

    Each cell in the grid receives a dict of biome weights (biome_name -> float)
    that sum to 1.0.  Near Voronoi cell boundaries, multiple biomes have
    non-zero weights, creating smooth transition zones 3-5 cells wide.

    Parameters
    ----------
    grid_size : int
        Size of the square grid (grid_size x grid_size).  Clamped to [4, 256].
    biome_count : int
        Number of distinct biomes to place.  Clamped to [2, len(VB_BIOMES)].
    seed : int
        Random seed for deterministic generation.

    Returns
    -------
    list[list[dict[str, float]]]
        2D array of shape (grid_size, grid_size), where each element is a dict
        mapping biome names to their weight at that cell.  Weights sum to 1.0.
    """
    rng = random.Random(seed)
    grid_size = max(4, min(grid_size, 256))
    biome_count = max(2, min(biome_count, len(VB_BIOMES)))

    # Select the biomes we'll use
    biomes_used = VB_BIOMES[:biome_count]

    # --- Generate Voronoi seed points ---
    voronoi_seeds: list[tuple[float, float]] = []
    seed_biomes: list[str] = []
    for i in range(biome_count):
        vx = rng.uniform(0.0, 1.0)
        vy = rng.uniform(0.0, 1.0)
        voronoi_seeds.append((vx, vy))
        seed_biomes.append(biomes_used[i])

    # --- Transition width in normalised space ---
    # 3-5 cells wide in a grid_size grid
    transition_width = 4.0 / grid_size  # ~4 cells wide in normalised [0,1] space

    # --- Domain warp parameters ---
    warp_strength = 0.08  # how much noise distorts the boundaries
    warp_freq = 3.0  # frequency of the domain warp noise

    # --- Build the biome weight map ---
    biome_map: list[list[dict[str, float]]] = []

    for gy in range(grid_size):
        row: list[dict[str, float]] = []
        for gx in range(grid_size):
            # Normalised position
            nx = (gx + 0.5) / grid_size
            ny = (gy + 0.5) / grid_size

            # Apply domain warping using hash noise
            warp_x = _hash_noise_2d(nx * warp_freq, ny * warp_freq, seed + 1) * warp_strength
            warp_y = _hash_noise_2d(nx * warp_freq + 100.0, ny * warp_freq + 100.0, seed + 2) * warp_strength
            warped_x = nx + warp_x
            warped_y = ny + warp_y

            # Compute distance to each Voronoi seed
            distances: list[tuple[float, int]] = []
            for i, (sx, sy) in enumerate(voronoi_seeds):
                dx = warped_x - sx
                dy = warped_y - sy
                d = math.sqrt(dx * dx + dy * dy)
                distances.append((d, i))

            distances.sort(key=lambda t: t[0])

            # Compute weights based on distance differences
            # The closest biome gets the most weight; biomes within
            # transition_width of the closest also get weight
            nearest_dist = distances[0][0]
            raw_weights: dict[str, float] = {}

            for dist, idx in distances:
                biome_name = seed_biomes[idx]
                gap = dist - nearest_dist

                if gap < 1e-9:
                    # This is the nearest (or tied nearest)
                    raw_weights[biome_name] = 1.0
                elif gap < transition_width:
                    # Within transition zone: linear falloff
                    w = 1.0 - (gap / transition_width)
                    raw_weights[biome_name] = max(0.0, w * w)  # quadratic for smoother blending
                # Beyond transition_width: weight = 0, skip

            # Normalise weights to sum to 1.0
            total = sum(raw_weights.values())
            if total < 1e-9:
                # Fallback: assign 100% to nearest
                cell_weights = {seed_biomes[distances[0][1]]: 1.0}
            else:
                cell_weights = {
                    name: round(w / total, 4) for name, w in raw_weights.items()
                }

            row.append(cell_weights)
        biome_map.append(row)

    return biome_map
