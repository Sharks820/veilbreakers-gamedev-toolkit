"""Road network generator -- pure logic, no bpy/bmesh.

Computes connected road networks between waypoints using MST connectivity.
Returns mesh-spec dicts and metadata (segments, intersections, bridges, switchbacks).

Features:
  - MST-based connectivity ensuring all waypoints are reachable
  - Road width varies by importance (main=4m, path=2m, trail=1m)
  - Intersection detection (T-junction, crossroads, Y-junction)
  - Bridge auto-placement where roads cross below water_level
  - Switchback generation on slopes > 30 degrees

All functions are pure and operate on plain Python data structures.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Vec3 = tuple[float, float, float]
Segment = tuple[Vec3, Vec3, float, str]  # (start, end, width, road_type)


# ---------------------------------------------------------------------------
# Road type definitions
# ---------------------------------------------------------------------------

ROAD_TYPES: dict[str, dict[str, Any]] = {
    "main": {"width": 4.0, "priority": 0},
    "path": {"width": 2.0, "priority": 1},
    "trail": {"width": 1.0, "priority": 2},
}


# ---------------------------------------------------------------------------
# MST computation (Kruskal's algorithm)
# ---------------------------------------------------------------------------

def _distance_3d(a: Vec3, b: Vec3) -> float:
    """Euclidean distance between two 3D points."""
    return math.sqrt(
        (a[0] - b[0]) ** 2
        + (a[1] - b[1]) ** 2
        + (a[2] - b[2]) ** 2
    )


def _distance_2d(a: Vec3, b: Vec3) -> float:
    """Euclidean distance in XY plane (ignoring Z)."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


class _UnionFind:
    """Disjoint-set / union-find for Kruskal's MST."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


def compute_mst_edges(
    waypoints: list[Vec3],
) -> list[tuple[int, int, float]]:
    """Compute MST edges from a list of waypoints using Kruskal's algorithm.

    Returns list of (index_a, index_b, distance) tuples forming the MST.
    """
    n = len(waypoints)
    if n < 2:
        return []

    # Build all edges sorted by distance
    edges: list[tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            d = _distance_3d(waypoints[i], waypoints[j])
            edges.append((d, i, j))
    edges.sort()

    uf = _UnionFind(n)
    mst: list[tuple[int, int, float]] = []
    for dist, i, j in edges:
        if uf.union(i, j):
            mst.append((i, j, dist))
            if len(mst) == n - 1:
                break

    return mst


# ---------------------------------------------------------------------------
# Road type classification
# ---------------------------------------------------------------------------

def _classify_road_type(
    distance: float,
    max_distance: float,
) -> str:
    """Classify a road segment by its relative importance.

    Shorter MST edges (connecting nearby waypoints) get higher classification.
    """
    if max_distance <= 0:
        return "main"
    ratio = distance / max_distance
    if ratio < 0.33:
        return "main"
    elif ratio < 0.66:
        return "path"
    else:
        return "trail"


# ---------------------------------------------------------------------------
# Slope and switchback computation
# ---------------------------------------------------------------------------

def _compute_slope_degrees(start: Vec3, end: Vec3) -> float:
    """Compute slope angle in degrees between two 3D points."""
    horiz = _distance_2d(start, end)
    if horiz < 1e-6:
        return 90.0 if abs(end[2] - start[2]) > 1e-6 else 0.0
    return math.degrees(math.atan(abs(end[2] - start[2]) / horiz))


def _generate_switchback_points(
    start: Vec3,
    end: Vec3,
    max_slope: float = 30.0,
    turn_width: float = 8.0,
    seed: int = 42,
) -> list[Vec3]:
    """Generate switchback waypoints when slope exceeds max_slope.

    Returns a list of intermediate points that create a zigzag path
    keeping each sub-segment under the max_slope threshold.
    """
    slope = _compute_slope_degrees(start, end)
    if slope <= max_slope:
        return []

    rng = random.Random(seed)
    horiz = _distance_2d(start, end)
    vert = abs(end[2] - start[2])

    # Number of switchback turns needed
    max_rise_per_run = horiz * math.tan(math.radians(max_slope))
    if max_rise_per_run < 1e-6:
        return []
    num_turns = max(1, int(math.ceil(vert / max_rise_per_run)))

    # Direction vector in XY plane
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_xy = math.sqrt(dx * dx + dy * dy)
    if length_xy < 1e-6:
        return []

    # Perpendicular direction for switchback offset
    perp_x = -dy / length_xy
    perp_y = dx / length_xy

    points: list[Vec3] = []
    z_step = vert / (num_turns + 1) * (1 if end[2] > start[2] else -1)

    for i in range(1, num_turns + 1):
        t = i / (num_turns + 1)
        base_x = start[0] + dx * t
        base_y = start[1] + dy * t
        base_z = start[2] + z_step * i

        # Alternate sides with slight randomness
        side = 1 if i % 2 == 0 else -1
        offset = turn_width * (0.8 + 0.4 * rng.random())

        px = base_x + perp_x * offset * side
        py = base_y + perp_y * offset * side

        points.append((px, py, base_z))

    return points


# ---------------------------------------------------------------------------
# Intersection detection
# ---------------------------------------------------------------------------

def _segments_near(
    seg_a: tuple[Vec3, Vec3],
    seg_b: tuple[Vec3, Vec3],
    threshold: float = 2.0,
) -> Vec3 | None:
    """Check if two line segments come within threshold distance.

    Returns the approximate intersection point (midpoint of closest approach)
    or None if segments are too far apart.

    Uses parameterized line segment closest-point computation.
    """
    p1, p2 = seg_a
    p3, p4 = seg_b

    d1x, d1y = p2[0] - p1[0], p2[1] - p1[1]
    d2x, d2y = p4[0] - p3[0], p4[1] - p3[1]

    denom = d1x * d2y - d1y * d2x
    if abs(denom) < 1e-10:
        # Parallel -- check midpoint distance
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        mx2 = (p3[0] + p4[0]) / 2
        my2 = (p3[1] + p4[1]) / 2
        dist = math.sqrt((mx - mx2) ** 2 + (my - my2) ** 2)
        if dist < threshold:
            z = (p1[2] + p2[2] + p3[2] + p4[2]) / 4
            return ((mx + mx2) / 2, (my + my2) / 2, z)
        return None

    dx = p3[0] - p1[0]
    dy = p3[1] - p1[1]

    t = (dx * d2y - dy * d2x) / denom
    u = (dx * d1y - dy * d1x) / denom

    # Check if intersection is within both segments
    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = p1[0] + t * d1x
        iy = p1[1] + t * d1y
        iz = (p1[2] + p2[2]) / 2  # Average Z
        return (ix, iy, iz)

    return None


def _classify_intersection(
    point: Vec3,
    connected_segments: list[tuple[Vec3, Vec3]],
) -> str:
    """Classify intersection type by the number of roads meeting.

    Returns "T", "cross", or "Y" based on angle analysis.
    """
    if len(connected_segments) <= 2:
        return "T"

    # Compute angles of each road direction from the intersection
    angles: list[float] = []
    for seg_start, seg_end in connected_segments:
        # Use the endpoint farther from intersection
        da = _distance_2d(point, seg_start)
        db = _distance_2d(point, seg_end)
        far = seg_end if da < db else seg_start
        angle = math.atan2(far[1] - point[1], far[0] - point[0])
        angles.append(angle)

    angles.sort()

    if len(angles) >= 4:
        return "cross"

    # Check angular spread for Y vs T
    if len(angles) >= 3:
        spreads = []
        for i in range(len(angles)):
            diff = angles[(i + 1) % len(angles)] - angles[i]
            if diff < 0:
                diff += 2 * math.pi
            spreads.append(diff)
        max_spread = max(spreads)
        # Y-junction has roughly 120-degree spacing; T has one ~180 gap
        if max_spread > math.radians(150):
            return "T"
        return "Y"

    return "T"


# ---------------------------------------------------------------------------
# Bridge detection
# ---------------------------------------------------------------------------

def _detect_bridges(
    segments: list[Segment],
    water_level: float = 0.0,
    heightmap: list[list[float]] | None = None,
) -> list[dict[str, Any]]:
    """Detect bridge positions where road segments cross below water_level.

    A bridge is needed when the terrain height along the road dips below
    water_level, or when the segment endpoints straddle the water level.
    """
    bridges: list[dict[str, Any]] = []

    for start, end, width, road_type in segments:
        # Sample points along the segment
        length = _distance_3d(start, end)
        num_samples = max(2, int(length / 2.0))

        below_water = False
        bridge_start: Vec3 | None = None
        bridge_end: Vec3 | None = None

        for i in range(num_samples + 1):
            t = i / num_samples
            px = start[0] + (end[0] - start[0]) * t
            py = start[1] + (end[1] - start[1]) * t
            pz = start[2] + (end[2] - start[2]) * t

            # Check heightmap if available
            terrain_z = pz
            if heightmap is not None:
                rows = len(heightmap)
                cols = len(heightmap[0]) if rows > 0 else 0
                if rows > 0 and cols > 0:
                    # Map world coords to heightmap indices (simplified)
                    ri = max(0, min(int(py) % rows, rows - 1))
                    ci = max(0, min(int(px) % cols, cols - 1))
                    terrain_z = heightmap[ri][ci]

            if terrain_z < water_level:
                if not below_water:
                    bridge_start = (px, py, pz)
                    below_water = True
                bridge_end = (px, py, pz)
            else:
                if below_water and bridge_start is not None and bridge_end is not None:
                    bridges.append({
                        "start": bridge_start,
                        "end": bridge_end,
                        "width": width,
                        "road_type": road_type,
                        "length": _distance_3d(bridge_start, bridge_end),
                    })
                    below_water = False
                    bridge_start = None

        # Handle segment ending while below water
        if below_water and bridge_start is not None and bridge_end is not None:
            bridges.append({
                "start": bridge_start,
                "end": bridge_end,
                "width": width,
                "road_type": road_type,
                "length": _distance_3d(bridge_start, bridge_end),
            })

    return bridges


# ---------------------------------------------------------------------------
# Road mesh spec generation
# ---------------------------------------------------------------------------

def _road_segment_mesh_spec(
    start: Vec3,
    end: Vec3,
    width: float,
    resolution: int = 4,
) -> dict[str, Any]:
    """Generate a mesh spec for a road segment as a flat strip.

    Returns a dict with vertices and faces forming a flat quad strip
    along the road direction.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-6:
        return {"vertices": [], "faces": []}

    # Perpendicular direction
    nx = -dy / length
    ny = dx / length
    hw = width / 2.0

    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int, int]] = []

    for i in range(resolution + 1):
        t = i / resolution
        px = start[0] + dx * t
        py = start[1] + dy * t
        pz = start[2] + (end[2] - start[2]) * t

        # Left and right edge vertices
        vertices.append((px + nx * hw, py + ny * hw, pz))
        vertices.append((px - nx * hw, py - ny * hw, pz))

    # Create quad faces
    for i in range(resolution):
        base = i * 2
        faces.append((base, base + 1, base + 3, base + 2))

    return {
        "vertices": vertices,
        "faces": faces,
        "type": "road_strip",
    }


def _road_segment_mesh_spec_with_curbs(
    start: Vec3,
    end: Vec3,
    width: float,
    curb_height: float = 0.15,
    gutter_width: float = 0.3,
    resolution: int = 4,
) -> dict[str, Any]:
    """Generate a mesh spec for a road segment with raised curb geometry.

    Cross-section layout (6 vertex columns per row, indexed left-to-right):
      col 0: outer-left gutter    X = -(width/2 + gutter_width),  Z = 0
      col 1: curb-top-left        X = -width/2,                   Z = curb_height
      col 2: inner-left road      X = -(width/2 - gutter_width*0.3), Z = 0
      col 3: inner-right road     X =  (width/2 - gutter_width*0.3), Z = 0
      col 4: curb-top-right       X =  width/2,                   Z = curb_height
      col 5: outer-right gutter   X =  (width/2 + gutter_width),  Z = 0

    The 5 quad strips per segment step:
      gutter-L  (col0-col1-col1'-col0')
      curb-L    (col1-col2-col2'-col1')
      road-surf (col2-col3-col3'-col2')
      curb-R    (col3-col4-col4'-col3')
      gutter-R  (col4-col5-col5'-col4')

    UV layers:
      road_surface — U along road direction, V across road width (0-1 over full width+gutters)
      curb         — U along road direction, V 0-1 over curb face height only

    Returns a dict with vertices, faces, uv_layers (road_surface, curb), type.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-6:
        return {"vertices": [], "faces": [], "uv_layers": {"road_surface": [], "curb": []}}

    # Unit along-road direction
    tx = dx / length
    ty = dy / length
    # Unit perpendicular (left normal)
    nx = -ty
    ny = tx

    hw = width / 2.0
    # Column X offsets from road center (local space, positive = right)
    col_offsets: list[tuple[float, float]] = [
        (-(hw + gutter_width), 0.0),            # col 0: outer-left gutter
        (-hw, curb_height),                     # col 1: curb-top-left
        (-(hw - gutter_width * 0.3), 0.0),      # col 2: inner-left road
        (hw - gutter_width * 0.3, 0.0),         # col 3: inner-right road
        (hw, curb_height),                      # col 4: curb-top-right
        (hw + gutter_width, 0.0),               # col 5: outer-right gutter
    ]
    num_cols = len(col_offsets)  # 6

    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int, int]] = []

    # UV data per face (4 UV coords per quad, one entry per face)
    uv_road_surface: list[list[tuple[float, float]]] = []
    uv_curb: list[list[tuple[float, float]]] = []

    # Total span for V normalisation in road_surface UV
    total_span = 2.0 * (hw + gutter_width)

    for row in range(resolution + 1):
        t = row / resolution
        px = start[0] + dx * t
        py = start[1] + dy * t
        pz = start[2] + (end[2] - start[2]) * t
        u = t  # UV along road direction

        for col_xoff, col_z in col_offsets:
            wx = px + nx * col_xoff
            wy = py + ny * col_xoff
            wz = pz + col_z
            vertices.append((wx, wy, wz))

    # Build quads between consecutive rows
    for row in range(resolution):
        base_a = row * num_cols
        base_b = (row + 1) * num_cols
        u0 = row / resolution
        u1 = (row + 1) / resolution

        for col in range(num_cols - 1):
            # Quad: (a_col, a_col+1, b_col+1, b_col)  -- CCW
            ia0 = base_a + col
            ia1 = base_a + col + 1
            ib0 = base_b + col
            ib1 = base_b + col + 1
            faces.append((ia0, ia1, ib1, ib0))

            # road_surface UV: V goes from left to right over full span
            xoff_l = col_offsets[col][0]
            xoff_r = col_offsets[col + 1][0]
            v0 = (xoff_l + hw + gutter_width) / total_span
            v1 = (xoff_r + hw + gutter_width) / total_span
            uv_road_surface.append([
                (u0, v0), (u0, v1), (u1, v1), (u1, v0)
            ])

            # curb UV: only meaningful on curb strips (col 1 and col 3)
            # For non-curb quads emit zeros; consumers read only relevant strips.
            if col in (1, 3):
                # V goes 0 (road surface) to 1 (curb top)
                z0 = col_offsets[col][1]
                z1 = col_offsets[col + 1][1]
                cv0 = z0 / curb_height if curb_height > 0 else 0.0
                cv1 = z1 / curb_height if curb_height > 0 else 0.0
                uv_curb.append([
                    (u0, cv0), (u0, cv1), (u1, cv1), (u1, cv0)
                ])
            else:
                uv_curb.append([(0.0, 0.0)] * 4)

    return {
        "vertices": vertices,
        "faces": faces,
        "uv_layers": {
            "road_surface": uv_road_surface,
            "curb": uv_curb,
        },
        "type": "road_strip_with_curbs",
        "width": width,
        "curb_height": curb_height,
        "gutter_width": gutter_width,
    }


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def compute_road_network(
    waypoints: list[Vec3],
    terrain_heightmap: list[list[float]] | None = None,
    water_level: float = 0.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a connected road network between waypoints.

    Uses MST to ensure all waypoints are connected. Classifies road
    segments by importance, detects intersections, places bridges over
    water crossings, and generates switchbacks on steep slopes.

    Parameters
    ----------
    waypoints : list of (x, y, z) tuples
        World-space positions to connect.
    terrain_heightmap : list of list of float, optional
        2D heightmap for terrain sampling. If None, segment Z values
        are interpolated linearly between waypoints.
    water_level : float
        Z height of water. Roads below this get bridges.
    seed : int
        Random seed for switchback jitter.

    Returns
    -------
    dict with:
        - "segments": list of (start, end, width, road_type)
        - "intersections": list of {"position": Vec3, "type": str}
        - "bridges": list of bridge dicts
        - "switchbacks": list of switchback position lists
        - "mesh_specs": list of mesh spec dicts for each segment
        - "waypoint_count": int
        - "total_length": float
    """
    if len(waypoints) < 2:
        return {
            "segments": [],
            "intersections": [],
            "bridges": [],
            "switchbacks": [],
            "mesh_specs": [],
            "waypoint_count": len(waypoints),
            "total_length": 0.0,
        }

    # Step 1: MST connectivity
    mst_edges = compute_mst_edges(waypoints)
    max_dist = max((d for _, _, d in mst_edges), default=1.0)

    # Step 2: Build road segments with classification
    segments: list[Segment] = []
    all_line_segs: list[tuple[Vec3, Vec3, int]] = []  # (start, end, segment_index)
    switchbacks: list[list[Vec3]] = []
    total_length = 0.0

    for idx_a, idx_b, dist in mst_edges:
        road_type = _classify_road_type(dist, max_dist)
        width = ROAD_TYPES[road_type]["width"]
        start = waypoints[idx_a]
        end = waypoints[idx_b]

        # Check for switchbacks on steep segments
        slope = _compute_slope_degrees(start, end)
        if slope > 30.0:
            sb_points = _generate_switchback_points(
                start, end, max_slope=30.0, seed=seed + idx_a * 1000 + idx_b
            )
            if sb_points:
                switchbacks.append(sb_points)
                # Split segment into sub-segments through switchback points
                all_pts = [start] + sb_points + [end]
                for i in range(len(all_pts) - 1):
                    seg = (all_pts[i], all_pts[i + 1], width, road_type)
                    segments.append(seg)
                    seg_idx = len(segments) - 1
                    all_line_segs.append((all_pts[i], all_pts[i + 1], seg_idx))
                    total_length += _distance_3d(all_pts[i], all_pts[i + 1])
                continue

        segments.append((start, end, width, road_type))
        seg_idx = len(segments) - 1
        all_line_segs.append((start, end, seg_idx))
        total_length += dist

    # Step 3: Detect intersections
    intersections: list[dict[str, Any]] = []
    checked: set[tuple[int, int]] = set()

    for i, (s1, e1, si) in enumerate(all_line_segs):
        for j, (s2, e2, sj) in enumerate(all_line_segs):
            if i >= j:
                continue
            key = (min(si, sj), max(si, sj))
            if key in checked:
                continue
            checked.add(key)

            pt = _segments_near((s1, e1), (s2, e2), threshold=2.0)
            if pt is not None:
                # Gather connected segments for classification
                connected = [(s1, e1), (s2, e2)]
                itype = _classify_intersection(pt, connected)
                intersections.append({
                    "position": pt,
                    "type": itype,
                    "segment_indices": [si, sj],
                })

    # Step 4: Detect bridges
    bridges = _detect_bridges(
        segments,
        water_level=water_level,
        heightmap=terrain_heightmap,
    )

    # Step 5: Generate mesh specs
    # Main roads and cobblestone streets get full curb geometry;
    # paths and trails use the simpler flat strip.
    _curb_road_types = {"main", "cobblestone"}
    mesh_specs: list[dict[str, Any]] = []
    for start, end, width, road_type in segments:
        if road_type in _curb_road_types:
            spec = _road_segment_mesh_spec_with_curbs(start, end, width)
        else:
            spec = _road_segment_mesh_spec(start, end, width)
        spec["road_type"] = road_type
        spec["width"] = width
        mesh_specs.append(spec)

    return {
        "segments": segments,
        "intersections": intersections,
        "bridges": bridges,
        "switchbacks": switchbacks,
        "mesh_specs": mesh_specs,
        "waypoint_count": len(waypoints),
        "total_length": total_length,
    }
