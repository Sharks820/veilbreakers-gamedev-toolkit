"""Pure-logic settlement grammar rules for procedural medieval town generation.

NO bpy or bmesh imports -- fully testable without Blender.

Provides:
- Concentric ring district zoning (market_square -> civic_ring -> residential -> industrial -> outskirts)
- Soft gradient building type selection weighted by district and boundary proximity
- L-system + MST organic road network generation
- OBB recursive lot subdivision with street frontage tracking
- Building-to-lot assignment with district fill rates
- Prop manifest generation with corruption-tier spacing
- Curb geometry is handled in road_network.py (see _road_segment_mesh_spec_with_curbs)

Matches Phase 32/33 pure-grammar pattern: all functions return plain Python dicts/lists.
Blender materialization happens in worldbuilding.py handlers.
"""

from __future__ import annotations

import math
import random
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RING_THRESHOLDS: list[tuple[str, float]] = [
    ("market_square", 0.15),
    ("civic_ring",    0.35),
    ("residential",   0.60),
    ("industrial",    0.80),
    ("outskirts",     1.01),
]

DISTRICT_FILL_RATES: dict[str, float] = {
    "market_square": 1.00,
    "civic_ring":    0.90,
    "residential":   0.80,
    "industrial":    0.95,
    "outskirts":     0.60,
}

DISTRICT_BUILDING_TYPES: dict[str, list[str]] = {
    "market_square": ["market_stall_building", "tavern", "merchant_house"],
    "civic_ring":    ["temple", "town_hall", "guildhall", "barracks"],
    "residential":   ["house", "cottage", "inn"],
    "industrial":    ["blacksmith", "tannery", "mill", "warehouse"],
    "outskirts":     ["farmhouse", "stable", "hovel"],
}

CORRUPTION_TIERS: list[tuple[float, str, float, float]] = [
    (0.2,  "pristine",  3.0,  5.0),
    (0.5,  "weathered", 5.0,  8.0),
    (0.8,  "damaged",   8.0,  15.0),
    (1.01, "corrupted", 15.0, 50.0),
]

ROAD_PROP_TYPES: dict[str, list[str]] = {
    "market_square": ["lantern_post", "market_stall", "barrel_cluster", "cart"],
    "civic_ring":    ["lantern_post", "bench", "notice_board"],
    "residential":   ["lantern_post", "trough", "bench"],
    "industrial":    ["barrel_cluster", "cart", "trough"],
    "outskirts":     ["lantern_post"],
}

# District lot minimum areas (sq metres), keyed by ring name
DISTRICT_LOT_MIN_AREAS: dict[str, float] = {
    "market_square": 100.0,
    "civic_ring":    80.0,
    "residential":   25.0,
    "industrial":    60.0,
    "outskirts":     150.0,
}


# ---------------------------------------------------------------------------
# District ring functions
# ---------------------------------------------------------------------------

def ring_for_position(
    pos: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> str:
    """Return the concentric ring district name for a 2D position.

    Uses RING_THRESHOLDS to map normalized distance (0..1) to a district.
    Positions beyond radius return "outskirts".

    Parameters
    ----------
    pos : (x, y)
    center : (cx, cy)
    radius : float  -- settlement radius in world units

    Returns
    -------
    str  -- district name from RING_THRESHOLDS
    """
    dx = pos[0] - center[0]
    dy = pos[1] - center[1]
    dist = math.sqrt(dx * dx + dy * dy)
    if radius <= 0.0:
        return "outskirts"
    dist_norm = dist / radius
    for name, threshold in RING_THRESHOLDS:
        if dist_norm < threshold:
            return name
    return "outskirts"


def weighted_building_type(
    district: str,
    neighbor_district: str,
    dist_to_boundary: float,
    seed: int,
) -> str:
    """Return a building type for a lot, with soft gradient near zone boundaries.

    If dist_to_boundary < 0.05 (within 5% of zone radius), there is a 30%
    chance to draw from the neighbor district's type list instead.

    Parameters
    ----------
    district : str  -- the lot's own district name
    neighbor_district : str  -- the adjacent ring district name
    dist_to_boundary : float  -- normalised distance to nearest ring boundary (0..1)
    seed : int

    Returns
    -------
    str  -- a building type string
    """
    rng = random.Random(seed)
    own_types = DISTRICT_BUILDING_TYPES.get(district, ["house"])
    neighbor_types = DISTRICT_BUILDING_TYPES.get(neighbor_district, own_types)

    if dist_to_boundary < 0.05 and rng.random() < 0.30:
        selected_list = neighbor_types
    else:
        selected_list = own_types

    return rng.choice(selected_list)


# ---------------------------------------------------------------------------
# Road network generation
# ---------------------------------------------------------------------------

def perturb_road_points(
    start: tuple[float, float],
    end: tuple[float, float],
    rng: random.Random,
    amplitude: float = 1.5,
    steps: int = 3,
) -> list[tuple[float, float]]:
    """Insert perturbed intermediate points between start and end.

    For each of (steps-1) intermediate points along the segment, the point
    is displaced perpendicular to the road direction by a uniform random
    offset in [-amplitude, amplitude].

    Returns list of tuples: [start, *midpoints, end].
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-6 or steps <= 1:
        return [start, end]

    # Perpendicular unit vector
    perp_x = -dy / length
    perp_y = dx / length

    points: list[tuple[float, float]] = [start]
    for i in range(1, steps):
        t = i / steps
        mx = start[0] + dx * t
        my = start[1] + dy * t
        offset = rng.uniform(-amplitude, amplitude)
        px = mx + perp_x * offset
        py = my + perp_y * offset
        points.append((round(px, 4), round(py, 4)))
    points.append(end)
    return points


def generate_road_network_organic(
    center: tuple[float, float],
    radius: float,
    seed: int,
    settlement_points: list[tuple[float, float]],
) -> list[dict[str, Any]]:
    """Generate an organic medieval road network using MST + L-system branching.

    Steps:
    1. Build MST using Kruskal's algorithm over settlement_points
    2. Classify edges: "main_road" if any endpoint has degree >= 3, else "alley"
    3. Perturb each edge into a curve with noise
    4. Add L-system branch alleys from main road midpoints (40% chance each)

    Parameters
    ----------
    center : (cx, cy)
    radius : float
    seed : int
    settlement_points : list of (x, y) -- key positions to connect

    Returns
    -------
    list of dict:
        {"points": [...], "width": float, "style": "main_road"|"alley", "seed": int}
        Main road width 4.0m, alley width 2.0m.
    """
    rng = random.Random(seed)
    n = len(settlement_points)
    if n < 2:
        return []

    # Build all edges
    edges: list[tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = settlement_points[i][0] - settlement_points[j][0]
            dy = settlement_points[i][1] - settlement_points[j][1]
            dist = math.sqrt(dx * dx + dy * dy)
            edges.append((dist, i, j))
    edges.sort()

    # Kruskal's MST via union-find
    parent = list(range(n))
    rank = [0] * n

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: int, b: int) -> bool:
        ra, rb = _find(a), _find(b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1
        return True

    mst: list[tuple[int, int]] = []
    for dist, i, j in edges:
        if _union(i, j):
            mst.append((i, j))
            if len(mst) == n - 1:
                break

    # Compute degree of each node
    degree: dict[int, int] = {i: 0 for i in range(n)}
    for i, j in mst:
        degree[i] += 1
        degree[j] += 1

    # Generate road segments
    segments: list[dict[str, Any]] = []
    for edge_idx, (i, j) in enumerate(mst):
        start = settlement_points[i]
        end = settlement_points[j]
        is_main = degree[i] >= 3 or degree[j] >= 3
        style = "main_road" if is_main else "alley"
        width = 4.0 if style == "main_road" else 2.0

        if style == "main_road":
            pts = perturb_road_points(start, end, rng, amplitude=1.5, steps=4)
        else:
            pts = perturb_road_points(start, end, rng, amplitude=0.8, steps=3)

        seg_seed = seed + edge_idx * 1000
        segments.append({
            "points": pts,
            "width": width,
            "style": style,
            "seed": seg_seed,
        })

    # L-system branch alleys: 40% chance per main road midpoint
    main_segs = [s for s in segments if s["style"] == "main_road"]
    for branch_idx, seg in enumerate(main_segs):
        if rng.random() > 0.40:
            continue
        pts = seg["points"]
        mid_idx = len(pts) // 2
        mid = pts[mid_idx]
        # Branch toward a random nearby settlement point
        if not settlement_points:
            continue
        target = rng.choice(settlement_points)
        branch_pts = perturb_road_points(mid, target, rng, amplitude=0.8, steps=3)
        branch_seed = seed + 90000 + branch_idx * 1000
        segments.append({
            "points": branch_pts,
            "width": 2.0,
            "style": "alley",
            "seed": branch_seed,
        })

    return segments


# ---------------------------------------------------------------------------
# OBB lot subdivision helpers
# ---------------------------------------------------------------------------

def _block_area(polygon_verts: list[tuple[float, float]]) -> float:
    """Compute polygon area using the Shoelace formula."""
    n = len(polygon_verts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x_i, y_i = polygon_verts[i]
        x_next, y_next = polygon_verts[(i + 1) % n]
        area += x_i * y_next
        area -= x_next * y_i
    return abs(area) * 0.5


def _nearest_edge_to_centroid(
    polygon_verts: list[tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return the edge of the polygon nearest to its centroid.

    Used to assign the street frontage edge (the edge a building entrance faces).
    """
    n = len(polygon_verts)
    if n < 2:
        return (polygon_verts[0], polygon_verts[0]) if polygon_verts else ((0.0, 0.0), (0.0, 0.0))
    cx = sum(v[0] for v in polygon_verts) / n
    cy = sum(v[1] for v in polygon_verts) / n
    best_edge = (polygon_verts[0], polygon_verts[1])
    best_dist = float("inf")
    for i in range(n):
        v1 = polygon_verts[i]
        v2 = polygon_verts[(i + 1) % n]
        edge_mid_x = (v1[0] + v2[0]) / 2.0
        edge_mid_y = (v1[1] + v2[1]) / 2.0
        d = math.sqrt((edge_mid_x - cx) ** 2 + (edge_mid_y - cy) ** 2)
        if d < best_dist:
            best_dist = d
            best_edge = (v1, v2)
    return best_edge


def _obb_split_polygon(
    polygon_verts: list[tuple[float, float]],
    rng: random.Random,
    split_ratio_range: tuple[float, float] = (0.4, 0.6),
) -> tuple[list[tuple[float, float]], list[tuple[float, float]] | None]:
    """Split a polygon along its principal axis (OBB longest axis).

    Uses PCA via numpy to find the dominant direction, then clips the
    polygon at a randomly-chosen split line perpendicular to that axis.

    Parameters
    ----------
    polygon_verts : list of (x, y)
    rng : random.Random
    split_ratio_range : (min, max) for split position along axis range

    Returns
    -------
    (half_a, half_b) -- two sub-polygons, or (polygon_verts, None) on failure
    """
    if len(polygon_verts) < 3:
        return polygon_verts, None

    pts = np.array(polygon_verts, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        return polygon_verts, None

    centroid = pts.mean(axis=0)
    centered = pts - centroid

    try:
        cov = np.cov(centered.T)
        if cov.ndim < 2:
            cov = np.array([[cov, 0.0], [0.0, 0.0]])
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        axis = eigenvectors[:, np.argmax(eigenvalues)]
    except (np.linalg.LinAlgError, ValueError):
        return polygon_verts, None

    # Project all points onto principal axis
    projections = centered @ axis
    proj_min = projections.min()
    proj_max = projections.max()
    if proj_max - proj_min < 1e-6:
        return polygon_verts, None

    split_t = rng.uniform(*split_ratio_range)
    split_val = proj_min + (proj_max - proj_min) * split_t
    # The split line passes through (centroid + split_val * axis) perpendicular to axis
    split_point = centroid + split_val * axis
    # Perpendicular to axis
    perp = np.array([-axis[1], axis[0]])

    # Clip polygon into two halves by the split line
    half_a: list[tuple[float, float]] = []
    half_b: list[tuple[float, float]] = []
    n = len(polygon_verts)

    for i in range(n):
        v1 = pts[i]
        v2 = pts[(i + 1) % n]

        # Sign of each vertex relative to split line (dot with axis)
        s1 = np.dot(v1 - split_point, axis)
        s2 = np.dot(v2 - split_point, axis)

        if s1 <= 0:
            half_a.append((float(v1[0]), float(v1[1])))
        else:
            half_b.append((float(v1[0]), float(v1[1])))

        # Edge crosses split line — find intersection
        if s1 * s2 < 0:
            t = s1 / (s1 - s2)
            ix = float(v1[0] + t * (v2[0] - v1[0]))
            iy = float(v1[1] + t * (v2[1] - v1[1]))
            inter = (ix, iy)
            half_a.append(inter)
            half_b.append(inter)

    if len(half_a) < 3 or len(half_b) < 3:
        return polygon_verts, None

    return half_a, half_b


def subdivide_block_to_lots(
    block_polygon: list[tuple[float, float]],
    district: str,
    seed: int,
    min_lot_area: float | None = None,
) -> list[dict[str, Any]]:
    """Recursively subdivide a block polygon into individual lots.

    Uses OBB split along principal axis. Respects district-specific minimum
    lot sizes (market=100m², civic=80m², residential=25m², etc.).

    Parameters
    ----------
    block_polygon : list of (x, y) vertices
    district : str
    seed : int
    min_lot_area : float or None -- override default per-district minimum

    Returns
    -------
    list of dict:
        {"polygon": [(x,y),...], "street_frontage_edge": ((x,y),(x,y)),
         "district": str, "area": float}
    """
    if min_lot_area is None:
        min_lot_area = DISTRICT_LOT_MIN_AREAS.get(district, 25.0)

    area = _block_area(block_polygon)
    rng = random.Random(seed)

    # Base case: too small to split further
    if area < min_lot_area * 2.0:
        frontage = _nearest_edge_to_centroid(block_polygon)
        return [{
            "polygon": block_polygon,
            "street_frontage_edge": frontage,
            "district": district,
            "area": round(area, 2),
        }]

    # Recursive case: split via OBB
    half_a, half_b = _obb_split_polygon(block_polygon, rng)
    if half_b is None:
        # Split failed — return as single lot
        frontage = _nearest_edge_to_centroid(block_polygon)
        return [{
            "polygon": block_polygon,
            "street_frontage_edge": frontage,
            "district": district,
            "area": round(area, 2),
        }]

    lots: list[dict[str, Any]] = []
    lots.extend(subdivide_block_to_lots(half_a, district, seed + 1, min_lot_area))
    lots.extend(subdivide_block_to_lots(half_b, district, seed + 2, min_lot_area))
    return lots


# ---------------------------------------------------------------------------
# Building assignment
# ---------------------------------------------------------------------------

def assign_buildings_to_lots(
    lots: list[dict[str, Any]],
    center: tuple[float, float],
    radius: float,
    veil_pressure: float,
    seed: int,
) -> list[dict[str, Any]]:
    """Assign building types to lots based on district, fill rate, and gradient.

    For each lot:
    - Determines district from lot centroid via ring_for_position
    - Determines neighbor district (adjacent ring)
    - Computes dist_to_boundary (fraction of ring band)
    - Selects building type via weighted_building_type
    - Applies fill rate: some lots become open space (building_type=None)

    Parameters
    ----------
    lots : list of lot dicts (from subdivide_block_to_lots)
    center : (cx, cy)
    radius : float
    veil_pressure : float  -- 0.0=pristine, 1.0=full corruption
    seed : int

    Returns
    -------
    list of dict -- each lot dict extended with building_type, orientation_edge
    """
    rng = random.Random(seed)
    result: list[dict[str, Any]] = []

    for lot in lots:
        poly = lot.get("polygon", [])
        if not poly:
            result.append(dict(lot))
            continue

        # Compute lot centroid
        cx_lot = sum(v[0] for v in poly) / len(poly)
        cy_lot = sum(v[1] for v in poly) / len(poly)
        pos = (cx_lot, cy_lot)

        district = ring_for_position(pos, center, radius)

        # Find neighbor district (inward ring)
        ring_names = [r[0] for r in RING_THRESHOLDS]
        ring_thresholds = [r[1] for r in RING_THRESHOLDS]
        dist_from_center = math.sqrt((pos[0] - center[0]) ** 2 + (pos[1] - center[1]) ** 2)
        dist_norm = dist_from_center / radius if radius > 0 else 0.0

        # Find which ring we're in and compute dist to boundary
        district_idx = ring_names.index(district) if district in ring_names else len(ring_names) - 1
        ring_upper = ring_thresholds[district_idx]
        ring_lower = ring_thresholds[district_idx - 1] if district_idx > 0 else 0.0
        ring_width = ring_upper - ring_lower
        dist_to_lower = dist_norm - ring_lower
        dist_to_upper = ring_upper - dist_norm
        dist_to_boundary = min(dist_to_lower, dist_to_upper) / ring_width if ring_width > 1e-6 else 0.5

        # Neighbor district = inward ring if near outer boundary, outward if near inner
        if dist_to_lower < dist_to_upper and district_idx > 0:
            neighbor_district = ring_names[district_idx - 1]
        elif district_idx < len(ring_names) - 1:
            neighbor_district = ring_names[district_idx + 1]
        else:
            neighbor_district = district

        lot_seed = rng.randint(0, 99999)
        building_type = weighted_building_type(district, neighbor_district, dist_to_boundary, lot_seed)

        fill_rate = DISTRICT_FILL_RATES.get(district, 0.8)
        if rng.random() > fill_rate:
            building_type = None

        out_lot = dict(lot)
        out_lot["building_type"] = building_type
        out_lot["orientation_edge"] = lot.get("street_frontage_edge")
        out_lot["district"] = district
        result.append(out_lot)

    return result


# ---------------------------------------------------------------------------
# Prop manifest generation
# ---------------------------------------------------------------------------

def prop_tier_for_pressure(pressure: float) -> tuple[str, float, float]:
    """Return the corruption band name and prop spacing (min, max) for a veil pressure.

    Parameters
    ----------
    pressure : float  -- 0.0 (pristine) to 1.0 (full corruption)

    Returns
    -------
    (band_name, spacing_min, spacing_max)
    """
    for threshold, band, spacing_min, spacing_max in CORRUPTION_TIERS:
        if pressure < threshold:
            return band, spacing_min, spacing_max
    return "corrupted", 15.0, 50.0


def generate_prop_manifest(
    road_segments: list[dict[str, Any]],
    center: tuple[float, float],
    radius: float,
    veil_pressure: float,
    seed: int,
) -> list[dict[str, Any]]:
    """Generate a list of prop placement specs along road segments.

    Uses corruption-tier spacing to determine prop density. Higher veil
    pressure = larger spacing = fewer props (desolate look near the Veil).

    Parameters
    ----------
    road_segments : list of road segment dicts (from generate_road_network_organic)
    center : (cx, cy)
    radius : float
    veil_pressure : float
    seed : int

    Returns
    -------
    list of dict:
        {"prop_type": str, "position": (x,y,z), "rotation_z": float,
         "corruption_band": str, "cache_key": (prop_type, band)}
    """
    rng = random.Random(seed)
    band, spacing_min, spacing_max = prop_tier_for_pressure(veil_pressure)
    props: list[dict[str, Any]] = []

    for seg_idx, segment in enumerate(road_segments):
        seg_pts = segment.get("points", [])
        seg_width = segment.get("width", 2.0)

        if len(seg_pts) < 2:
            continue

        # Walk along each sub-segment of the polyline
        for sub_idx in range(len(seg_pts) - 1):
            start = seg_pts[sub_idx]
            end = seg_pts[sub_idx + 1]
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            seg_length = math.sqrt(dx * dx + dy * dy)
            if seg_length < 1e-6:
                continue

            ux = dx / seg_length
            uy = dy / seg_length
            perp_x = -uy
            perp_y = ux
            side_offset = seg_width / 2.0 + 0.3

            # Poisson-disk-like spacing along edge
            current_dist = rng.uniform(spacing_min, spacing_max)
            while current_dist < seg_length:
                t = current_dist / seg_length
                base_x = start[0] + ux * current_dist
                base_y = start[1] + uy * current_dist

                for side in (-1.0, 1.0):
                    px = base_x + perp_x * side_offset * side
                    py = base_y + perp_y * side_offset * side
                    pos = (px, py)
                    district = ring_for_position(pos, center, radius)
                    prop_options = ROAD_PROP_TYPES.get(district, ["lantern_post"])
                    prop_type = rng.choice(prop_options)
                    rotation_z = round(math.atan2(uy, ux) + (math.pi / 2.0 * side), 4)

                    props.append({
                        "prop_type": prop_type,
                        "position": (round(px, 3), round(py, 3), 0.0),
                        "rotation_z": rotation_z,
                        "corruption_band": band,
                        "cache_key": (prop_type, band),
                    })

                current_dist += rng.uniform(spacing_min, spacing_max)

    return props
