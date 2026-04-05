"""Pure-logic scatter engine: Poisson disk sampling, biome filtering,
context-aware prop placement, and breakable variant generation.

NO bpy/bmesh imports. Fully testable without Blender.

Provides:
  - poisson_disk_sample: Bridson's algorithm for blue-noise point distribution
  - biome_filter_points: Altitude/slope rule filtering with vegetation assignment
  - context_scatter: Context-aware prop placement near tagged buildings
  - generate_breakable_variants: Intact + destroyed mesh spec pairs
  - PROP_AFFINITY: Building-type -> weighted prop list mapping
  - BREAKABLE_PROPS: Standard breakable prop definitions
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Poisson Disk Sampling (Bridson's algorithm)
# ---------------------------------------------------------------------------

def poisson_disk_sample(
    width: float,
    depth: float,
    min_distance: float,
    seed: int = 0,
    max_attempts: int = 30,
) -> list[tuple[float, float]]:
    """Generate blue-noise distributed 2D points via Bridson's algorithm.

    Parameters
    ----------
    width, depth : float
        Area bounds [0, width] x [0, depth].
    min_distance : float
        Minimum distance between any two points.
    seed : int
        Random seed for deterministic generation.
    max_attempts : int
        Samples to try around each active point before rejection.

    Returns
    -------
    list of (x, y) tuples
        Points within the specified bounds.
    """
    rng = random.Random(seed)

    cell_size = min_distance / math.sqrt(2)
    grid_w = max(1, int(math.ceil(width / cell_size)))
    grid_h = max(1, int(math.ceil(depth / cell_size)))

    # Grid stores index into points list, -1 means empty
    grid: list[int] = [-1] * (grid_w * grid_h)
    points: list[tuple[float, float]] = []
    active: list[int] = []

    def _grid_idx(x: float, y: float) -> int:
        gx = int(x / cell_size)
        gy = int(y / cell_size)
        gx = max(0, min(gx, grid_w - 1))
        gy = max(0, min(gy, grid_h - 1))
        return gy * grid_w + gx

    def _is_valid(x: float, y: float) -> bool:
        if x < 0 or x >= width or y < 0 or y >= depth:
            return False
        gx = int(x / cell_size)
        gy = int(y / cell_size)
        # Check 5x5 neighborhood
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < grid_w and 0 <= ny < grid_h:
                    idx = grid[ny * grid_w + nx]
                    if idx != -1:
                        px, py = points[idx]
                        dist_sq = (x - px) ** 2 + (y - py) ** 2
                        if dist_sq < min_distance * min_distance:
                            return False
        return True

    # Start with a random initial point
    x0 = rng.uniform(0, width)
    y0 = rng.uniform(0, depth)
    points.append((x0, y0))
    grid[_grid_idx(x0, y0)] = 0
    active.append(0)

    while active:
        # Pick a random active point
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
            # Remove from active list
            active[active_idx] = active[-1]
            active.pop()

    return points


# ---------------------------------------------------------------------------
# Biome Filter
# ---------------------------------------------------------------------------

def biome_filter_points(
    points: list[tuple[float, float]],
    heightmap: Any,  # np.ndarray
    slope_map: Any,  # np.ndarray
    rules: list[dict[str, Any]],
    terrain_size: float = 100.0,
    terrain_width: float | None = None,
    terrain_depth: float | None = None,
    seed: int = 0,
    max_tilt_angle: float = 90.0,
    moisture_map: Any | None = None,  # optional np.ndarray
) -> list[dict[str, Any]]:
    """Filter scatter points through biome altitude/slope rules.

    Parameters
    ----------
    points : list of (x, y) tuples
        Candidate scatter positions.
    heightmap : np.ndarray
        2D heightmap with values in [0, 1].
    slope_map : np.ndarray
        2D slope map in degrees [0, 90].
    rules : list of dict
        Each rule has: vegetation_type, min_alt, max_alt, min_slope, max_slope,
        scale_range (tuple), density (0-1 probability of keeping).
        Optional per-rule keys: min_moisture, max_moisture (0-1).
    terrain_size : float
        Backward-compatible square terrain extent used when axis-specific
        dimensions are not provided.
    terrain_width : float | None
        Optional world-space width of terrain for X coordinate mapping.
    terrain_depth : float | None
        Optional world-space depth of terrain for Y coordinate mapping.
    seed : int
        Random seed for density and scale/rotation randomization.
    max_tilt_angle : float
        Global maximum terrain normal angle in degrees (default 90.0).
        Points where the slope exceeds this angle are rejected outright.
        Set to 45.0 to reject steep cliff faces.
    moisture_map : np.ndarray or None
        Optional 2D array of moisture values in [0, 1], same shape as
        heightmap. When provided, rules can specify min_moisture/max_moisture
        to restrict vegetation to wet or dry areas.

    Returns
    -------
    list of dict
        Placement dicts with: position, vegetation_type, scale, rotation.
    """
    rng = random.Random(seed)
    placements: list[dict[str, Any]] = []
    rows, cols = heightmap.shape
    width = max(float(terrain_width if terrain_width is not None else terrain_size), 1e-9)
    depth = max(float(terrain_depth if terrain_depth is not None else terrain_size), 1e-9)

    for x, y in points:
        # Map world position to heightmap indices
        u = x / width
        v = y / depth
        col_idx = int(u * (cols - 1))
        row_idx = int(v * (rows - 1))
        col_idx = max(0, min(col_idx, cols - 1))
        row_idx = max(0, min(row_idx, rows - 1))

        altitude = float(heightmap[row_idx, col_idx])
        slope = float(slope_map[row_idx, col_idx])

        # Global tilt filtering: reject points on terrain steeper than threshold
        if slope > max_tilt_angle:
            continue

        # Sample moisture if map is provided
        moisture = None
        if moisture_map is not None:
            moisture = float(moisture_map[row_idx, col_idx])

        matching_rules: list[dict[str, Any]] = []
        for rule in rules:
            min_alt = rule.get("min_alt", 0.0)
            max_alt = rule.get("max_alt", 1.0)
            min_slope = rule.get("min_slope", 0.0)
            max_slope = rule.get("max_slope", 90.0)

            if not (min_alt <= altitude <= max_alt
                    and min_slope <= slope <= max_slope):
                continue

            # Moisture filtering (if moisture_map provided and rule has bounds)
            if moisture is not None:
                rule_min_moisture = rule.get("min_moisture", 0.0)
                rule_max_moisture = rule.get("max_moisture", 1.0)
                if not (rule_min_moisture <= moisture <= rule_max_moisture):
                    continue

            matching_rules.append(rule)

        if not matching_rules:
            continue

        accepted_rules: list[dict[str, Any]] = []
        for rule in matching_rules:
            density = float(rule.get("density", 1.0))
            density = max(0.0, min(1.0, density))
            if rng.random() <= density:
                accepted_rules.append(rule)

        if not accepted_rules:
            continue

        if len(accepted_rules) == 1:
            chosen_rule = accepted_rules[0]
        else:
            total_weight = sum(max(0.001, float(rule.get("density", 1.0))) for rule in accepted_rules)
            pick = rng.uniform(0.0, total_weight)
            cumulative = 0.0
            chosen_rule = accepted_rules[-1]
            for rule in accepted_rules:
                cumulative += max(0.001, float(rule.get("density", 1.0)))
                if pick <= cumulative:
                    chosen_rule = rule
                    break

        scale_range = chosen_rule.get("scale_range", (0.8, 1.2))
        scale = rng.uniform(scale_range[0], scale_range[1])
        rotation = rng.uniform(0, 360)

        placements.append({
            "position": (x, y),
            "vegetation_type": chosen_rule["vegetation_type"],
            "scale": scale,
            "rotation": rotation,
        })

    return placements


# ---------------------------------------------------------------------------
# Context-Aware Scatter
# ---------------------------------------------------------------------------

PROP_AFFINITY: dict[str, list[tuple[str, float]]] = {
    "tavern": [
        ("barrel", 0.3),
        ("bench", 0.2),
        ("mug", 0.15),
        ("lantern", 0.1),
        ("crate", 0.1),
    ],
    "dock": [
        ("crate", 0.3),
        ("rope_coil", 0.2),
        ("barrel", 0.15),
        ("anchor", 0.1),
        ("lantern", 0.05),
    ],
    "blacksmith": [
        ("anvil", 0.2),
        ("weapon_rack", 0.2),
        ("coal_pile", 0.15),
        ("barrel", 0.1),
        ("crate", 0.1),
    ],
    "graveyard": [
        ("tombstone", 0.3),
        ("dead_tree", 0.15),
        ("lantern", 0.1),
        ("fence", 0.1),
        ("pot", 0.05),
    ],
    "market": [
        ("crate", 0.25),
        ("barrel", 0.2),
        ("cart", 0.15),
        ("bench", 0.1),
        ("lantern", 0.1),
    ],
}

_GENERIC_PROPS: list[tuple[str, float]] = [
    ("rock", 0.24),
    ("bush", 0.22),
    ("crate", 0.20),
    ("barrel", 0.18),
    ("lantern", 0.16),
]


def context_scatter(
    buildings: list[dict[str, Any]],
    area_size: float,
    prop_density: float = 0.3,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Place props near buildings using context-aware affinity scoring.

    Parameters
    ----------
    buildings : list of dict
        Each has: type (str), position (x, y), footprint (w, d) optional.
    area_size : float
        Scatter area size (square).
    prop_density : float
        Controls scatter density via min_distance scaling.
    seed : int
        Random seed.

    Returns
    -------
    list of dict
        Placement dicts with: type, position, rotation, scale.
    """
    rng = random.Random(seed)

    # min_distance inversely proportional to density
    min_dist = max(1.0, 3.0 / max(prop_density, 0.01))
    candidates = poisson_disk_sample(area_size, area_size, min_dist, seed=seed)

    placements: list[dict[str, Any]] = []

    for cx, cy in candidates:
        # Check exclusion zones (building footprints)
        inside_building = False
        for bld in buildings:
            bx, by = bld["position"]
            fw, fd = bld.get("footprint", (5.0, 5.0))
            half_w, half_d = fw / 2.0, fd / 2.0
            if (bx - half_w <= cx <= bx + half_w
                    and by - half_d <= cy <= by + half_d):
                inside_building = True
                break

        if inside_building:
            continue

        # Find nearest building and compute distance
        nearest_bld = None
        nearest_dist = float("inf")
        for bld in buildings:
            bx, by = bld["position"]
            d = math.sqrt((cx - bx) ** 2 + (cy - by) ** 2)
            if d < nearest_dist:
                nearest_dist = d
                nearest_bld = bld

        # Select prop type based on affinity
        affinity_radius = 15.0  # Props within this distance use building affinity
        if nearest_bld is not None and nearest_dist < affinity_radius:
            bld_type = nearest_bld.get("type", "")
            prop_list = PROP_AFFINITY.get(bld_type, _GENERIC_PROPS)
            # Blend with generic based on distance
            blend = nearest_dist / affinity_radius  # 0=at building, 1=at radius edge
            if rng.random() < blend:
                prop_list = _GENERIC_PROPS
        else:
            prop_list = _GENERIC_PROPS

        # Weighted random selection
        prop_type = _weighted_choice(prop_list, rng)
        rotation = rng.uniform(0, 360)
        scale = rng.uniform(0.7, 1.3)

        placements.append({
            "type": prop_type,
            "position": (cx, cy),
            "rotation": rotation,
            "scale": scale,
        })

    return placements


def _weighted_choice(
    items: list[tuple[str, float]],
    rng: random.Random,
) -> str:
    """Select from weighted list using random.Random instance."""
    total = sum(w for _, w in items)
    r = rng.uniform(0, total)
    cumulative = 0.0
    for name, weight in items:
        cumulative += weight
        if r <= cumulative:
            return name
    return items[-1][0]  # fallback


# ---------------------------------------------------------------------------
# Breakable Prop Variants
# ---------------------------------------------------------------------------

BREAKABLE_PROPS: dict[str, dict[str, Any]] = {
    "barrel": {
        "geometry": {"type": "cylinder", "radius": 0.4, "height": 1.0, "segments": 12},
        "fragment_count": (4, 6),
        "debris_count": (3, 5),
        "material": {"base_color": (0.45, 0.3, 0.15), "roughness": 0.8},
    },
    "crate": {
        "geometry": {"type": "box", "size": (0.8, 0.8, 0.8)},
        "fragment_count": (4, 8),
        "debris_count": (4, 6),
        "material": {"base_color": (0.5, 0.35, 0.2), "roughness": 0.85},
    },
    "pot": {
        "geometry": {"type": "cylinder", "radius": 0.3, "height": 0.5, "segments": 10},
        "fragment_count": (3, 5),
        "debris_count": (2, 4),
        "material": {"base_color": (0.6, 0.45, 0.3), "roughness": 0.7},
    },
    "fence": {
        "geometry": {"type": "box", "size": (2.0, 0.1, 1.2)},
        "fragment_count": (2, 3),
        "debris_count": (2, 3),
        "material": {"base_color": (0.4, 0.3, 0.18), "roughness": 0.9},
    },
    "cart": {
        "geometry": {"type": "box", "size": (2.0, 1.2, 1.0)},
        "fragment_count": (6, 10),
        "debris_count": (5, 8),
        "material": {"base_color": (0.42, 0.28, 0.15), "roughness": 0.85},
    },
}


def generate_breakable_variants(
    prop_type: str,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate intact and destroyed mesh specifications for a breakable prop.

    Parameters
    ----------
    prop_type : str
        One of the BREAKABLE_PROPS keys (barrel, crate, pot, fence, cart).
    seed : int
        Random seed for fragment variation.

    Returns
    -------
    dict with:
        intact_spec: dict with geometry_ops list and material
        destroyed_spec: dict with fragment_ops list, debris_ops list, material (darkened)
    """
    if prop_type not in BREAKABLE_PROPS:
        raise ValueError(
            f"Unknown breakable prop '{prop_type}'. "
            f"Valid types: {sorted(BREAKABLE_PROPS.keys())}"
        )

    rng = random.Random(seed)
    config = BREAKABLE_PROPS[prop_type]
    geom = config["geometry"]
    mat = config["material"]
    frag_min, frag_max = config["fragment_count"]
    debris_min, debris_max = config["debris_count"]

    # Build intact spec
    intact_ops = [_build_geometry_op(geom)]
    intact_spec = {
        "geometry_ops": intact_ops,
        "material": dict(mat),
    }

    # Build destroyed spec: fragment the intact geometry
    num_fragments = rng.randint(frag_min, frag_max)
    num_debris = rng.randint(debris_min, debris_max)

    fragment_ops = _generate_fragments(geom, num_fragments, rng)
    debris_ops = _generate_debris(geom, num_debris, rng)

    # Darken material for destroyed version
    base_r, base_g, base_b = mat["base_color"]
    darken_factor = 0.6
    destroyed_mat = {
        "base_color": (
            base_r * darken_factor,
            base_g * darken_factor,
            base_b * darken_factor,
        ),
        "roughness": min(1.0, mat["roughness"] + 0.1),
    }

    destroyed_spec = {
        "fragment_ops": fragment_ops,
        "debris_ops": debris_ops,
        "material": destroyed_mat,
    }

    return {
        "intact_spec": intact_spec,
        "destroyed_spec": destroyed_spec,
    }


def _build_geometry_op(geom: dict) -> dict:
    """Convert geometry config to an operation dict."""
    op: dict[str, Any] = {"type": geom["type"]}
    if geom["type"] == "cylinder":
        op["radius"] = geom["radius"]
        op["height"] = geom["height"]
        op["segments"] = geom.get("segments", 12)
        op["position"] = (0, 0, 0)
    elif geom["type"] == "box":
        op["size"] = tuple(geom["size"])
        op["position"] = (0, 0, 0)
    return op


def _generate_fragments(
    geom: dict,
    count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate fragment geometry ops by subdividing the original shape."""
    fragments: list[dict[str, Any]] = []

    if geom["type"] == "cylinder":
        radius = geom["radius"]
        height = geom["height"]
        # Stave-like fragments: arc slices
        for i in range(count):
            angle_start = (2 * math.pi * i) / count
            angle_mid = angle_start + math.pi / count
            # Fragment as a thin box approximating a stave
            frag_width = 2 * radius * math.sin(math.pi / count)
            frag_height = height * rng.uniform(0.5, 0.9)
            frag_depth = radius * 0.3
            cx = math.cos(angle_mid) * radius * 0.6
            cy = math.sin(angle_mid) * radius * 0.6
            fragments.append({
                "type": "box",
                "size": (frag_width, frag_depth, frag_height),
                "position": (cx, cy, rng.uniform(-0.1, 0.2)),
                "rotation": rng.uniform(0, 360),
            })
    elif geom["type"] == "box":
        sx, sy, sz = geom["size"]
        # Plank-like fragments
        for i in range(count):
            fw = sx / count * rng.uniform(0.8, 1.2)
            fh = sz * rng.uniform(0.4, 0.9)
            fd = sy * rng.uniform(0.3, 0.6)
            ox = (i - count / 2) * (sx / count) + rng.uniform(-0.1, 0.1)
            oy = rng.uniform(-sy * 0.3, sy * 0.3)
            oz = rng.uniform(-0.2, 0.1)
            fragments.append({
                "type": "box",
                "size": (fw, fd, fh),
                "position": (ox, oy, oz),
                "rotation": rng.uniform(0, 360),
            })

    return fragments


def _generate_debris(
    geom: dict,
    count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate small debris pieces scattered around the original position."""
    debris: list[dict[str, Any]] = []

    # Determine scatter radius from geometry bounds
    if geom["type"] == "cylinder":
        scatter_radius = geom["radius"] * 2.0
    elif geom["type"] == "box":
        scatter_radius = max(geom["size"][0], geom["size"][1]) * 1.5
    else:
        scatter_radius = 1.0

    for _ in range(count):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(0.1, scatter_radius)
        dx = math.cos(angle) * dist
        dy = math.sin(angle) * dist

        size = rng.uniform(0.05, 0.15)
        debris.append({
            "type": "box",
            "size": (size, size, size * rng.uniform(0.3, 1.0)),
            "position": (dx, dy, 0.0),
            "rotation": rng.uniform(0, 360),
        })

    return debris
