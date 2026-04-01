"""Pure-logic settlement grammar — no bpy dependency.

Provides procedural generation of:
  - Organic road networks (L-system + MST perturbation)
  - Concentric ring district zones
  - OBB recursive lot subdivision
  - District-weighted building assignment
  - Corruption-scaled prop manifests with Tripo prompt templates
  - Prop cache keying by (prop_type, corruption_band)

All functions operate on plain Python data structures.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]

# ---------------------------------------------------------------------------
# Concentric ring district constants (D-03)
# ---------------------------------------------------------------------------

RING_THRESHOLDS: list[tuple[str, float]] = [
    ("market_square", 0.15),
    ("civic_ring", 0.35),
    ("residential", 0.60),
    ("industrial", 0.80),
    ("outskirts", 1.01),
]

# ---------------------------------------------------------------------------
# Corruption tier constants (D-08)
# ---------------------------------------------------------------------------

CORRUPTION_TIERS: list[tuple[float, str, float, float]] = [
    # (pressure_threshold, band_name, spacing_min, spacing_max)
    (0.2, "pristine", 3.0, 5.0),
    (0.5, "weathered", 5.0, 8.0),
    (0.8, "damaged", 8.0, 15.0),
    (1.01, "corrupted", 15.0, 50.0),
]

# District fill rates (D-06)
DISTRICT_FILL_RATES: dict[str, float] = {
    "market_square": 1.00,
    "civic_ring": 0.95,
    "residential": 0.80,
    "industrial": 0.95,
    "outskirts": 0.60,
}

# ---------------------------------------------------------------------------
# Prop Prompts (D-07, D-10) — Task 1 of Plan 36-02
# ---------------------------------------------------------------------------

PROP_PROMPTS: dict[str, str] = {
    "lantern_post": (
        "iron lantern post on stone base, dark fantasy medieval, hand-crafted, "
        "wrought iron scrollwork, flickering flame inside glass, PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
    "market_stall": (
        "wooden market stall with faded fabric canopy, dark fantasy medieval merchant, "
        "worn wood grain, rope ties, PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
    "well": (
        "stone well with wooden crossbeam and rope, dark fantasy medieval, hand-carved "
        "stone blocks, iron bucket, PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
    "barrel_cluster": (
        "cluster of 3 weathered oak barrels, dark fantasy medieval market, iron hoops, "
        "wood stave detail, PBR-ready, {corruption_desc}, "
        "single object group, no environment, white background"
    ),
    "cart": (
        "wooden merchant cart with spoked wheels, dark fantasy medieval, "
        "worn planks, iron fittings, PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
    "bench": (
        "rough-hewn stone bench, dark fantasy medieval, weathered granite, "
        "PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
    "trough": (
        "stone horse trough with water, dark fantasy medieval, mossy stone blocks, "
        "iron ring bolts, PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
    "notice_board": (
        "wooden notice board with posted parchments, dark fantasy medieval town, "
        "dark stained wood post, frayed paper, PBR-ready, {corruption_desc}, "
        "single object, no environment, white background"
    ),
}

CORRUPTION_DESCS: dict[str, str] = {
    "pristine": "pristine condition, vibrant colors, clean surfaces",
    "weathered": "weathered aged condition, worn textures, subtle moss and grime",
    "damaged": "damaged cracked condition, dark corruption spreading at edges, faint void energy",
    "corrupted": "heavily corrupted by dark void energy, blackened crumbling surfaces, eldritch runes glowing",
}

# ---------------------------------------------------------------------------
# Prop prompt helper (Task 1)
# ---------------------------------------------------------------------------


def get_prop_prompt(prop_type: str, corruption_band: str) -> str:
    """Return a formatted Tripo AI prompt for the given prop type and corruption band.

    Parameters
    ----------
    prop_type : str
        Key into PROP_PROMPTS (e.g. "lantern_post", "well").
    corruption_band : str
        Key into CORRUPTION_DESCS (e.g. "pristine", "corrupted").

    Returns
    -------
    str
        Fully formatted prompt with {corruption_desc} substituted.

    Raises
    ------
    KeyError
        If prop_type or corruption_band is not recognized.
    """
    template = PROP_PROMPTS[prop_type]
    desc = CORRUPTION_DESCS[corruption_band]
    return template.format(corruption_desc=desc)


# ---------------------------------------------------------------------------
# District ring assignment (D-03)
# ---------------------------------------------------------------------------


def ring_for_position(pos: Vec2 | Vec3, center: Vec2 | Vec3, radius: float) -> str:
    """Return the district ring name for a position.

    Parameters
    ----------
    pos : (x, y) or (x, y, z)
        World-space position to classify.
    center : (x, y) or (x, y, z)
        Settlement center.
    radius : float
        Settlement radius.

    Returns
    -------
    str
        One of: market_square, civic_ring, residential, industrial, outskirts.
    """
    dx = pos[0] - center[0]
    dy = pos[1] - center[1]
    dist = math.sqrt(dx * dx + dy * dy)
    dist_norm = dist / max(radius, 1e-6)
    for name, threshold in RING_THRESHOLDS:
        if dist_norm < threshold:
            return name
    return "outskirts"


# ---------------------------------------------------------------------------
# Corruption tier lookup (D-08)
# ---------------------------------------------------------------------------


def prop_tier_for_pressure(pressure: float) -> tuple[str, float, float]:
    """Return (band_name, spacing_min, spacing_max) for the given Veil pressure.

    Parameters
    ----------
    pressure : float
        Veil pressure in [0.0, 1.0].

    Returns
    -------
    tuple[str, float, float]
        (corruption_band, spacing_min_meters, spacing_max_meters).
    """
    for threshold, band, spacing_min, spacing_max in CORRUPTION_TIERS:
        if pressure < threshold:
            return band, spacing_min, spacing_max
    return "corrupted", 15.0, 50.0


# ---------------------------------------------------------------------------
# Road network organic perturbation (D-01)
# ---------------------------------------------------------------------------


def _perturb_road_segment(
    start: Vec3,
    end: Vec3,
    rng: random.Random,
    amplitude: float = 1.5,
    steps: int = 3,
) -> list[Vec3]:
    """Insert mid-points with perpendicular noise for organic road feel.

    Parameters
    ----------
    start, end : Vec3
        Endpoints of the road segment.
    rng : random.Random
        Seeded RNG for deterministic perturbation.
    amplitude : float
        Max perpendicular offset in metres.
    steps : int
        Number of interpolation steps (more = smoother curve).

    Returns
    -------
    list of Vec3
        Perturbed point list including start and end.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length_2d = math.sqrt(dx * dx + dy * dy) or 1.0

    # Perpendicular direction in XY
    perp_x = -dy / length_2d
    perp_y = dx / length_2d

    points: list[Vec3] = [start]
    for i in range(1, steps):
        t = i / steps
        mx = start[0] + dx * t
        my = start[1] + dy * t
        mz = start[2] + dz * t
        offset = rng.uniform(-amplitude, amplitude)
        points.append((mx + perp_x * offset, my + perp_y * offset, mz))
    points.append(end)
    return points


def generate_road_network_organic(
    center: Vec2,
    radius: float,
    seed: int,
    road_style: str = "medieval",
    waypoint_count: int = 8,
) -> list[dict[str, Any]]:
    """Generate organic road segments radiating from center (L-system style).

    Returns list of road segment dicts (no bpy objects):
      {start, end, width, style, points}

    Parameters
    ----------
    center : (x, y)
        Settlement center in world space.
    radius : float
        Settlement radius.
    seed : int
        Deterministic seed.
    road_style : str
        "medieval" (default) — winding organic layout.
    waypoint_count : int
        Number of radial road endpoints around the perimeter.

    Returns
    -------
    list of dict
        Each dict: {start, end, width, style, points}
    """
    rng = random.Random(seed)
    segments: list[dict[str, Any]] = []

    cx, cy = center

    # Generate radial waypoints around the perimeter with angular jitter
    waypoints: list[Vec3] = []
    for i in range(waypoint_count):
        base_angle = (2.0 * math.pi * i) / waypoint_count
        angle_jitter = rng.uniform(-math.pi / waypoint_count * 0.4, math.pi / waypoint_count * 0.4)
        angle = base_angle + angle_jitter
        r = radius * rng.uniform(0.7, 0.95)
        wx = cx + math.cos(angle) * r
        wy = cy + math.sin(angle) * r
        waypoints.append((wx, wy, 0.0))

    # Add a few intermediate waypoints for alley cross-connects
    mid_waypoints: list[Vec3] = []
    for i in range(min(4, waypoint_count // 2)):
        angle = rng.uniform(0, 2.0 * math.pi)
        r = radius * rng.uniform(0.3, 0.6)
        mx = cx + math.cos(angle) * r
        my = cy + math.sin(angle) * r
        mid_waypoints.append((mx, my, 0.0))

    center_3d: Vec3 = (cx, cy, 0.0)

    # Main roads: center to each perimeter waypoint
    for i, wp in enumerate(waypoints):
        points = _perturb_road_segment(
            center_3d, wp, rng, amplitude=radius * 0.08, steps=3
        )
        segments.append({
            "start": points[0],
            "end": points[-1],
            "points": points,
            "width": 4.0,
            "style": "main_road",
        })

    # Alley connects: adjacent waypoints
    for i in range(len(waypoints)):
        a = waypoints[i]
        b = waypoints[(i + 1) % len(waypoints)]
        points = _perturb_road_segment(a, b, rng, amplitude=radius * 0.05, steps=3)
        segments.append({
            "start": points[0],
            "end": points[-1],
            "points": points,
            "width": 2.0,
            "style": "alley",
        })

    # Short trails from mid-waypoints
    for mp in mid_waypoints:
        nearest = min(waypoints, key=lambda w: math.sqrt((w[0] - mp[0])**2 + (w[1] - mp[1])**2))
        points = _perturb_road_segment(mp, nearest, rng, amplitude=radius * 0.04, steps=2)
        segments.append({
            "start": points[0],
            "end": points[-1],
            "points": points,
            "width": 1.5,
            "style": "trail",
        })

    return segments


# ---------------------------------------------------------------------------
# Concentric district assignment (D-03)
# ---------------------------------------------------------------------------


def generate_concentric_districts(
    center: Vec2,
    radius: float,
    seed: int,
) -> dict[str, Any]:
    """Generate district zone boundaries using concentric ring model.

    Returns a district map describing zone radii and names.

    Parameters
    ----------
    center : (x, y)
        Settlement center.
    radius : float
        Outer radius of the settlement.
    seed : int
        Deterministic seed (reserved for future stochastic variation).

    Returns
    -------
    dict with:
        - "center": (x, y)
        - "radius": float
        - "rings": list of {name, inner_r, outer_r, fill_rate}
        - "thresholds": list of (name, threshold)
    """
    rings = []
    prev_r = 0.0
    thresholds = list(RING_THRESHOLDS)
    for idx, (name, threshold) in enumerate(thresholds):
        # Cap the outermost ring to exactly the settlement radius so tests
        # asserting last_ring["outer_r"] == radius pass (threshold=1.01 is
        # only used by ring_for_position() to catch edge-case positions).
        outer_r = radius if idx == len(thresholds) - 1 else radius * threshold
        rings.append({
            "name": name,
            "inner_r": prev_r,
            "outer_r": outer_r,
            "fill_rate": DISTRICT_FILL_RATES.get(name, 0.8),
        })
        prev_r = outer_r

    return {
        "center": center,
        "radius": radius,
        "rings": rings,
        "thresholds": RING_THRESHOLDS,
    }


# ---------------------------------------------------------------------------
# OBB recursive lot subdivision (D-05)
# ---------------------------------------------------------------------------


def _block_area(polygon: list[Vec2]) -> float:
    """Compute signed area of a 2D polygon using the shoelace formula."""
    n = len(polygon)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return abs(area) / 2.0


def subdivide_block_to_lots(
    block_polygon: list[Vec2],
    district: str,
    seed: int,
    min_lot_area: float = 25.0,
) -> list[dict[str, Any]]:
    """Recursively split a road-bounded block into building lots.

    Uses axis-aligned split along the polygon's bounding-box longest axis
    (simplified OBB — avoids numpy dependency in pure-logic layer).

    Parameters
    ----------
    block_polygon : list of (x, y)
        Convex polygon vertices defining the block.
    district : str
        District ring name (affects minimum lot sizes).
    seed : int
        Deterministic seed for split ratio randomization.
    min_lot_area : float
        Stop splitting when block area is below this (metres²).

    Returns
    -------
    list of dict
        Each lot: {polygon, district, area, street_frontage_edge}
    """
    # District-specific minimum lot area overrides
    district_min = {
        "market_square": 60.0,
        "civic_ring": 50.0,
        "residential": 25.0,
        "industrial": 40.0,
        "outskirts": 20.0,
    }
    effective_min = district_min.get(district, min_lot_area)

    def _split(poly: list[Vec2], rng: random.Random, depth: int) -> list[list[Vec2]]:
        area = _block_area(poly)
        if area < effective_min * 2 or depth > 6:
            return [poly]

        # AABB longest-axis split — operate on bounding box to guarantee
        # proper winding order in both halves.
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        x_range = x1 - x0
        y_range = y1 - y0

        split_ratio = rng.uniform(0.4, 0.6)
        if x_range >= y_range:
            split_x = x0 + x_range * split_ratio
            # CCW rectangles: bottom-left → bottom-right → top-right → top-left
            left  = [(x0, y0), (split_x, y0), (split_x, y1), (x0, y1)]
            right = [(split_x, y0), (x1, y0), (x1, y1), (split_x, y1)]
        else:
            split_y = y0 + y_range * split_ratio
            left  = [(x0, y0), (x1, y0), (x1, split_y), (x0, split_y)]
            right = [(x0, split_y), (x1, split_y), (x1, y1), (x0, y1)]

        # Recurse or keep each half
        result = []
        for half in [left, right]:
            half_area = _block_area(half)
            if half_area >= effective_min * 2:
                result.extend(_split(half, rng, depth + 1))
            elif half_area > 0.0:
                result.append(half)
        return result

    rng = random.Random(seed)
    raw_lots = _split(block_polygon, rng, 0)

    lots = []
    for lot_poly in raw_lots:
        area = _block_area(lot_poly)
        # Street frontage edge: longest edge (simplified — real impl tracks road adjacency)
        longest_edge = 0
        longest_len = 0.0
        for i in range(len(lot_poly)):
            j = (i + 1) % len(lot_poly)
            dx = lot_poly[j][0] - lot_poly[i][0]
            dy = lot_poly[j][1] - lot_poly[i][1]
            l = math.sqrt(dx * dx + dy * dy)
            if l > longest_len:
                longest_len = l
                longest_edge = i
        lots.append({
            "polygon": lot_poly,
            "district": district,
            "area": area,
            "street_frontage_edge": longest_edge,
        })

    return lots


# ---------------------------------------------------------------------------
# District-weighted building assignment (D-06)
# ---------------------------------------------------------------------------

# Building types weighted per district ring.  The first entry in each list is
# the most common — ``random.choices`` uses descending weights.
_DISTRICT_BUILDING_TYPES: dict[str, list[str]] = {
    "market_square": [
        "market_stall_cluster", "tavern", "guild_hall", "blacksmith",
    ],
    "civic_ring": [
        "manor", "shrine_major", "barracks", "guild_hall", "tavern",
    ],
    "residential": [
        "abandoned_house", "abandoned_house", "forge", "shrine_minor",
    ],
    "industrial": [
        "forge", "blacksmith", "abandoned_house", "watchtower",
    ],
    "outskirts": [
        "abandoned_house", "shrine_minor", "watchtower",
    ],
}


def assign_buildings_to_lots(
    lots: list[dict[str, Any]],
    center: Vec2 = (0.0, 0.0),
    radius: float = 50.0,
    veil_pressure: float = 0.0,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Assign a ``building_type`` to each lot based on its district ring.

    Parameters
    ----------
    lots : list of dict
        Lot dicts from ``subdivide_block_to_lots`` (must have *polygon* and
        *district* keys).
    center, radius : settlement geometry for ring classification.
    veil_pressure : float
        Currently unused — reserved for corruption-biased type selection.
    seed : int
        Deterministic seed.

    Returns
    -------
    list of dict
        The same lot dicts, each augmented with a ``building_type`` key.
    """
    rng = random.Random(seed + 7777)
    for lot in lots:
        district = lot.get("district", "outskirts")
        available = _DISTRICT_BUILDING_TYPES.get(district, ["abandoned_house"])
        # Descending weight: first item ~2x more likely than last
        weights = [max(1, len(available) - i) for i in range(len(available))]
        lot["building_type"] = rng.choices(available, weights=weights, k=1)[0]
    return lots


# ---------------------------------------------------------------------------
# Prop manifest generation (D-07, D-08, D-09)
# ---------------------------------------------------------------------------


def generate_prop_manifest(
    road_segments: list[dict[str, Any]],
    veil_pressure: float,
    seed: int,
    center: Vec2 = (0.0, 0.0),
    radius: float = 50.0,
) -> list[dict[str, Any]]:
    """Generate a corruption-scaled list of prop placement specs.

    No bpy — returns pure data dicts. The worldbuilding.py handler
    materializes these via Tripo AI.

    Parameters
    ----------
    road_segments : list of dict
        Road segment dicts from generate_road_network_organic().
    veil_pressure : float
        Veil corruption pressure in [0.0, 1.0].
    seed : int
        Deterministic seed.
    center : (x, y)
        Settlement center for district ring calculation.
    radius : float
        Settlement radius.

    Returns
    -------
    list of dict
        Each dict: {
            prop_type: str,
            position: (x, y, z),
            rotation_z: float,
            corruption_band: str,
            cache_key: (str, str),
        }
    """
    rng = random.Random(seed + 9999)
    corruption_band, spacing_min, spacing_max = prop_tier_for_pressure(veil_pressure)

    # Prop types per district ring
    district_prop_types: dict[str, list[str]] = {
        "market_square": ["market_stall", "barrel_cluster", "cart", "well", "notice_board"],
        "civic_ring": ["bench", "notice_board", "lantern_post", "well"],
        "residential": ["bench", "trough", "barrel_cluster", "lantern_post"],
        "industrial": ["barrel_cluster", "cart", "trough"],
        "outskirts": ["lantern_post", "bench"],
    }

    props: list[dict[str, Any]] = []
    spacing = rng.uniform(spacing_min, spacing_max)

    for seg in road_segments:
        start = seg.get("start", (0.0, 0.0, 0.0))
        end = seg.get("end", (0.0, 0.0, 0.0))
        seg_style = seg.get("style", "main_road")

        # Only place props along main roads and alleys (not trails)
        if seg_style == "trail":
            continue

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        seg_len = math.sqrt(dx * dx + dy * dy)
        if seg_len < spacing:
            continue

        # Perpendicular offset direction
        nx = -dy / seg_len if seg_len > 1e-6 else 0.0
        ny = dx / seg_len if seg_len > 1e-6 else 0.0
        road_width = seg.get("width", 4.0)
        side_offset = road_width / 2.0 + 0.5

        # Place props at spacing intervals along the segment, alternating sides
        t = spacing / 2.0
        side = 1
        while t < seg_len:
            px = start[0] + dx * (t / seg_len)
            py = start[1] + dy * (t / seg_len)
            pz = 0.0

            # Determine district from position
            district = ring_for_position((px, py), center, radius)
            available_types = district_prop_types.get(district, ["barrel_cluster"])
            prop_type = rng.choice(available_types)

            # Place on alternating sides of the road
            px += nx * side_offset * side
            py += ny * side_offset * side

            rotation_z = rng.uniform(0.0, 2.0 * math.pi)

            props.append({
                "prop_type": prop_type,
                "position": (px, py, pz),
                "rotation_z": rotation_z,
                "corruption_band": corruption_band,
                "cache_key": (prop_type, corruption_band),
            })

            t += spacing * rng.uniform(0.8, 1.2)
            side *= -1

    return props


# ---------------------------------------------------------------------------
# Road mesh spec with curbs (D-02) — used by worldbuilding.py
# ---------------------------------------------------------------------------


def _road_segment_mesh_spec_with_curbs(
    start: Vec3,
    end: Vec3,
    width: float,
    curb_height: float = 0.15,
    gutter_width: float = 0.3,
    resolution: int = 4,
) -> dict[str, Any]:
    """Generate a mesh spec for a road segment with raised curb geometry.

    Cross-section layout (left to right):
      outer_gutter (gutter_width) | road_surface (width) | outer_gutter (gutter_width)
    Curb top verts raised by curb_height above road surface.

    Vertex column indices along segment:
      col 0: outer gutter left  (Z = road_z)
      col 1: curb top left      (Z = road_z + curb_height)
      col 2: inner gutter left  (Z = road_z)
      col 3: road center        (Z = road_z)
      col 4: inner gutter right (Z = road_z)
      col 5: curb top right     (Z = road_z + curb_height)
      col 6: outer gutter right (Z = road_z)

    Parameters
    ----------
    start, end : Vec3
        Road segment endpoints.
    width : float
        Road surface width in metres.
    curb_height : float
        Height of raised curb above road surface (default 0.15m).
    gutter_width : float
        Width of gutter/curb zone on each side (default 0.3m).
    resolution : int
        Number of cross-sections along segment length.

    Returns
    -------
    dict with:
        - "vertices": list of (x, y, z) tuples
        - "faces": list of (i, j, k, l) quad index tuples
        - "uv_groups": {"road_surface": face_indices, "curb": face_indices}
        - "type": "road_curb_strip"
        - "total_width": float
        - "road_width": float
        - "curb_height": float
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-6:
        return {
            "vertices": [], "faces": [], "uv_groups": {},
            "type": "road_curb_strip",
            "total_width": width + 2 * gutter_width,
            "road_width": width,
            "curb_height": curb_height,
        }

    # Perpendicular unit vector
    nx = -dy / length
    ny = dx / length

    hw = width / 2.0
    total_hw = hw + gutter_width  # half of total width

    # Column X offsets from road centerline (left to right)
    # col 0: -total_hw (outer gutter left)
    # col 1: -(hw + gutter_width * 0.5) = curb top left edge
    # col 2: -hw (inner gutter left / curb inner edge)
    # col 3: 0.0 (road center)
    # col 4: +hw (inner gutter right)
    # col 5: +(hw + gutter_width * 0.5) = curb top right edge
    # col 6: +total_hw (outer gutter right)
    col_offsets = [-total_hw, -(hw + gutter_width * 0.5), -hw, 0.0, hw, (hw + gutter_width * 0.5), total_hw]
    # Z offsets: curb tops (cols 1, 5) are raised
    col_z_offsets = [0.0, curb_height, 0.0, 0.0, 0.0, curb_height, 0.0]

    COLS = 7  # vertices per cross-section

    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int, int]] = []
    road_face_indices: list[int] = []
    curb_face_indices: list[int] = []

    for i in range(resolution + 1):
        t = i / resolution
        px = start[0] + dx * t
        py = start[1] + dy * t
        pz = start[2] + (end[2] - start[2]) * t

        for col in range(COLS):
            offset = col_offsets[col]
            z_extra = col_z_offsets[col]
            vx = px + nx * offset
            vy = py + ny * offset
            vz = pz + z_extra
            vertices.append((vx, vy, vz))

    # Build quad faces between adjacent cross-sections
    face_index = 0
    for i in range(resolution):
        base_a = i * COLS
        base_b = (i + 1) * COLS
        for col in range(COLS - 1):
            a = base_a + col
            b = base_b + col
            c = base_b + col + 1
            d = base_a + col + 1
            faces.append((a, b, c, d))
            # Classify face: road_surface (cols 2-3), curb (cols 1, 5), gutter (cols 0, 6)
            if col == 2 or col == 3:
                road_face_indices.append(face_index)
            elif col == 1 or col == 5:
                curb_face_indices.append(face_index)
            face_index += 1

    return {
        "vertices": vertices,
        "faces": faces,
        "uv_groups": {
            "road_surface": road_face_indices,
            "curb": curb_face_indices,
        },
        "type": "road_curb_strip",
        "total_width": width + 2 * gutter_width,
        "road_width": width,
        "curb_height": curb_height,
    }
