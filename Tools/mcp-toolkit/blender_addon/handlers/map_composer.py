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
    "sacred_shrine",
    "veil_crack_zone",
    "battlefield",
    "underground_dungeon",
]

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
    },
    "town": {
        "preferred_biomes": ["thornwood_forest"],
        "min_slope": 0,
        "max_slope": 10,
        "min_distance_from_others": 120.0,
        "near_water": True,
        "elevation_range": (0.1, 0.3),
    },
    "bandit_camp": {
        "preferred_biomes": ["corrupted_swamp", "thornwood_forest", "battlefield"],
        "min_slope": 0,
        "max_slope": 25,
        "min_distance_from_others": 40.0,
        "near_water": False,
        "elevation_range": (0.2, 0.6),
    },
    "dungeon_entrance": {
        "preferred_biomes": ["mountain_pass", "ruined_fortress", "underground_dungeon"],
        "min_slope": 10,
        "max_slope": 45,
        "min_distance_from_others": 60.0,
        "near_water": False,
        "elevation_range": (0.3, 0.8),
    },
    "shrine": {
        "preferred_biomes": ["sacred_shrine", "thornwood_forest"],
        "min_slope": 0,
        "max_slope": 20,
        "min_distance_from_others": 30.0,
        "near_water": False,
        "elevation_range": (0.2, 0.7),
    },
    "veil_crack": {
        "preferred_biomes": ["veil_crack_zone"],
        "min_slope": 0,
        "max_slope": 60,
        "min_distance_from_others": 50.0,
        "near_water": False,
        "elevation_range": (0.4, 0.9),
    },
    "castle": {
        "preferred_biomes": ["mountain_pass", "ruined_fortress"],
        "min_slope": 0,
        "max_slope": 20,
        "min_distance_from_others": 150.0,
        "near_water": False,
        "elevation_range": (0.5, 0.8),
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


def _hash_noise_2d(x: float, y: float, seed: int = 0) -> float:
    """Deterministic pseudo-noise via integer hashing.  Returns [-1, 1]."""
    # Use Python's built-in hash for speed; mix in seed
    h = hash((round(x, 6), round(y, 6), seed))
    # Map to [-1, 1]
    return ((h & 0xFFFFFFFF) / 0x7FFFFFFF) - 1.0


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
        biome = _get_biome_at(x, y, width, height, seed=rng.randint(0, 2**31))
        if biome not in preferred_biomes:
            # Allow placement with reduced probability even outside preferred biomes
            # This prevents impossible placement when biome zones don't cover enough area
            if rng.random() > 0.15:
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

    if len(settlements) < 2:
        return []

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

            placed_pois.append({
                "name": f"{poi_type}_{placed_for_type + 1}",
                "type": poi_type,
                "position": (round(x, 2), round(y, 2)),
                "elevation": round(elev, 4),
                "biome": biome,
                "slope": round(slope, 2),
            })
            placed_for_type += 1

    # Generate road network
    roads = _generate_world_roads(
        placed_pois, width, height, heightmap,
        shortcut_count=shortcut_roads,
        seed=seed,
    )

    # Compute biome distribution
    biome_dist: dict[str, int] = {}
    for poi in placed_pois:
        b = poi["biome"]
        biome_dist[b] = biome_dist.get(b, 0) + 1

    return {
        "pois": placed_pois,
        "roads": roads,
        "metadata": {
            "seed": seed,
            "world_size": (width, height),
            "total_pois_requested": total_requested,
            "total_pois_placed": len(placed_pois),
            "placement_failures": placement_failures,
            "road_count": len(roads),
            "biome_distribution": biome_dist,
        },
    }
