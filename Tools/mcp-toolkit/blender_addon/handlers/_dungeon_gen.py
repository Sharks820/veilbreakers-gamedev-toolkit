"""Pure-logic dungeon, cave, and town layout generation.

BSP dungeon partitioning, cellular automata cave generation, and
Voronoi-based town layout algorithms.  **Zero bpy/bmesh imports** --
fully testable outside Blender.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Room:
    """A rectangular room within a dungeon."""

    x: int
    y: int
    width: int
    height: int
    room_type: str = "generic"  # generic, spawn, boss, treasure, entrance, exit

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    def intersects(self, other: "Room") -> bool:
        """Return True if this room's interior overlaps *other*'s interior."""
        return (
            self.x < other.x2
            and self.x2 > other.x
            and self.y < other.y2
            and self.y2 > other.y
        )


@dataclass
class DungeonLayout:
    """Complete BSP dungeon data."""

    width: int
    height: int
    rooms: list[Room] = field(default_factory=list)
    corridors: list[tuple[tuple[int, int], tuple[int, int]]] = field(
        default_factory=list
    )
    doors: list[tuple[int, int]] = field(default_factory=list)
    spawn_points: list[tuple[int, int]] = field(default_factory=list)
    loot_points: list[tuple[int, int]] = field(default_factory=list)
    grid: Optional[np.ndarray] = None  # int8: 0=wall 1=floor 2=corridor 3=door


@dataclass
class CaveMap:
    """Cellular-automata cave data."""

    width: int
    height: int
    grid: Optional[np.ndarray] = None  # int8: 0=wall 1=floor
    regions: list[set[tuple[int, int]]] = field(default_factory=list)
    largest_region: int = 0  # index into *regions*


@dataclass
class TownLayout:
    """Voronoi-based town layout data."""

    width: int
    height: int
    districts: list[dict] = field(default_factory=list)
    roads: set[tuple[int, int]] = field(default_factory=set)
    building_plots: list[dict] = field(default_factory=list)
    landmarks: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BSP helpers
# ---------------------------------------------------------------------------

@dataclass
class _BSPNode:
    x: int
    y: int
    w: int
    h: int
    left: Optional["_BSPNode"] = None
    right: Optional["_BSPNode"] = None
    room: Optional[Room] = None


def _split_bsp(
    node: _BSPNode,
    depth: int,
    max_depth: int,
    min_room_size: int,
    rng: random.Random,
) -> None:
    """Recursively partition *node* via BSP."""
    if depth >= max_depth:
        return

    # Decide split orientation based on aspect ratio + randomness
    min_split = min_room_size + 2  # room + 1-cell border each side
    can_split_h = node.h >= 2 * min_split
    can_split_v = node.w >= 2 * min_split

    if not can_split_h and not can_split_v:
        return

    if can_split_h and can_split_v:
        split_horizontal = (node.h > node.w) if rng.random() < 0.6 else rng.random() < 0.5
    elif can_split_h:
        split_horizontal = True
    else:
        split_horizontal = False

    if split_horizontal:
        split = rng.randint(min_split, node.h - min_split)
        node.left = _BSPNode(node.x, node.y, node.w, split)
        node.right = _BSPNode(node.x, node.y + split, node.w, node.h - split)
    else:
        split = rng.randint(min_split, node.w - min_split)
        node.left = _BSPNode(node.x, node.y, split, node.h)
        node.right = _BSPNode(node.x + split, node.y, node.w - split, node.h)

    _split_bsp(node.left, depth + 1, max_depth, min_room_size, rng)
    _split_bsp(node.right, depth + 1, max_depth, min_room_size, rng)


def _place_rooms(node: _BSPNode, min_room_size: int, rng: random.Random) -> list[Room]:
    """Place one room per leaf node, returns list of rooms."""
    if node.left is None and node.right is None:
        # Leaf -- place a room with random inset
        max_w = node.w - 2
        max_h = node.h - 2
        if max_w < min_room_size or max_h < min_room_size:
            return []
        rw = rng.randint(min_room_size, max_w)
        rh = rng.randint(min_room_size, max_h)
        rx = node.x + rng.randint(1, node.w - rw - 1)
        ry = node.y + rng.randint(1, node.h - rh - 1)
        room = Room(rx, ry, rw, rh)
        node.room = room
        return [room]

    rooms: list[Room] = []
    if node.left:
        rooms.extend(_place_rooms(node.left, min_room_size, rng))
    if node.right:
        rooms.extend(_place_rooms(node.right, min_room_size, rng))
    return rooms


def _get_room(node: _BSPNode) -> Optional[Room]:
    """Return any room in this subtree (preference: left then right)."""
    if node.room is not None:
        return node.room
    if node.left:
        r = _get_room(node.left)
        if r:
            return r
    if node.right:
        r = _get_room(node.right)
        if r:
            return r
    return None


def _connect_rooms(
    node: _BSPNode,
    grid: np.ndarray,
    rng: random.Random,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Connect sibling rooms with L-shaped corridors."""
    corridors: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if node.left is None or node.right is None:
        return corridors

    # Recurse first
    corridors.extend(_connect_rooms(node.left, grid, rng))
    corridors.extend(_connect_rooms(node.right, grid, rng))

    # Find a room in each subtree to connect
    room_a = _get_room(node.left)
    room_b = _get_room(node.right)
    if room_a is None or room_b is None:
        return corridors

    cx_a, cy_a = room_a.center
    cx_b, cy_b = room_b.center

    # L-shaped corridor: go horizontal first, then vertical (or vice versa)
    if rng.random() < 0.5:
        _carve_h_corridor(grid, cy_a, cx_a, cx_b)
        _carve_v_corridor(grid, cx_b, cy_a, cy_b)
    else:
        _carve_v_corridor(grid, cx_a, cy_a, cy_b)
        _carve_h_corridor(grid, cy_b, cx_a, cx_b)

    corridors.append(((cx_a, cy_a), (cx_b, cy_b)))
    return corridors


def _carve_h_corridor(grid: np.ndarray, y: int, x1: int, x2: int) -> None:
    lo, hi = min(x1, x2), max(x1, x2)
    h, w = grid.shape
    for x in range(lo, hi + 1):
        if 0 <= y < h and 0 <= x < w:
            if grid[y, x] == 0:
                grid[y, x] = 2  # corridor


def _carve_v_corridor(grid: np.ndarray, x: int, y1: int, y2: int) -> None:
    lo, hi = min(y1, y2), max(y1, y2)
    h, w = grid.shape
    for y in range(lo, hi + 1):
        if 0 <= y < h and 0 <= x < w:
            if grid[y, x] == 0:
                grid[y, x] = 2  # corridor


# ---------------------------------------------------------------------------
# BSP dungeon generation
# ---------------------------------------------------------------------------

def generate_bsp_dungeon(
    width: int = 64,
    height: int = 64,
    min_room_size: int = 6,
    max_depth: int = 5,
    seed: int = 0,
) -> DungeonLayout:
    """Generate a dungeon using BSP partitioning.

    Returns a :class:`DungeonLayout` with rooms, corridors, doors,
    spawn/loot points, and a 2-D grid (0=wall, 1=floor, 2=corridor, 3=door).

    Guarantees all rooms are reachable from the entrance via flood-fill.
    """
    rng = random.Random(seed)

    # 1. BSP partition
    root = _BSPNode(0, 0, width, height)
    _split_bsp(root, 0, max_depth, min_room_size, rng)

    # 2. Place rooms in leaves
    rooms = _place_rooms(root, min_room_size, rng)
    if len(rooms) < 2:
        # Force at least 2 rooms for a viable dungeon
        rooms = _force_rooms(width, height, min_room_size, rng)

    # 3. Build grid
    grid = np.zeros((height, width), dtype=np.int8)

    # Carve room floors
    for room in rooms:
        grid[room.y : room.y2, room.x : room.x2] = 1

    # 4. Connect rooms via BSP siblings
    corridors = _connect_rooms(root, grid, rng)

    # If BSP tree didn't produce corridors (e.g. forced rooms), connect linearly
    if not corridors:
        for i in range(len(rooms) - 1):
            cx_a, cy_a = rooms[i].center
            cx_b, cy_b = rooms[i + 1].center
            _carve_h_corridor(grid, cy_a, cx_a, cx_b)
            _carve_v_corridor(grid, cx_b, cy_a, cy_b)
            corridors.append(((cx_a, cy_a), (cx_b, cy_b)))

    # 5. Place doors where corridors meet room edges
    doors = _place_doors(grid, rooms, height, width)

    # 6. Assign room types
    _assign_room_types(rooms, rng)

    # 7. Spawn / loot points
    spawn_points = _place_spawn_points(rooms, grid, rng)
    loot_points = _place_loot_points(rooms, grid, rng)

    layout = DungeonLayout(
        width=width,
        height=height,
        rooms=rooms,
        corridors=corridors,
        doors=doors,
        spawn_points=spawn_points,
        loot_points=loot_points,
        grid=grid,
    )

    # 8. Connectivity guarantee
    _ensure_connectivity(layout, rng)

    return layout


def _force_rooms(
    width: int, height: int, min_room_size: int, rng: random.Random
) -> list[Room]:
    """Create at least 3 non-overlapping rooms when BSP fails."""
    rooms: list[Room] = []
    attempts = 0
    while len(rooms) < 3 and attempts < 200:
        rw = rng.randint(min_room_size, min(min_room_size * 2, width // 3))
        rh = rng.randint(min_room_size, min(min_room_size * 2, height // 3))
        rx = rng.randint(1, width - rw - 1)
        ry = rng.randint(1, height - rh - 1)
        candidate = Room(rx, ry, rw, rh)
        if not any(candidate.intersects(r) for r in rooms):
            rooms.append(candidate)
        attempts += 1
    return rooms


def _place_doors(
    grid: np.ndarray, rooms: list[Room], h: int, w: int
) -> list[tuple[int, int]]:
    """Mark corridor cells at room boundaries as doors (value 3)."""
    doors: list[tuple[int, int]] = []
    for room in rooms:
        for x in range(room.x, room.x2):
            for y in (room.y - 1, room.y2):
                if 0 <= y < h and 0 <= x < w and grid[y, x] == 2:
                    grid[y, x] = 3
                    doors.append((x, y))
        for y in range(room.y, room.y2):
            for x in (room.x - 1, room.x2):
                if 0 <= y < h and 0 <= x < w and grid[y, x] == 2:
                    grid[y, x] = 3
                    doors.append((x, y))
    return doors


def _assign_room_types(rooms: list[Room], rng: random.Random) -> None:
    rooms[0].room_type = "entrance"
    if len(rooms) > 1:
        rooms[-1].room_type = "boss"
    treasure_count = min(2, len(rooms) - 2)
    middle = rooms[1:-1] if len(rooms) > 2 else []
    if middle:
        chosen = rng.sample(middle, min(treasure_count, len(middle)))
        for r in chosen:
            r.room_type = "treasure"


def _place_spawn_points(
    rooms: list[Room], grid: np.ndarray, rng: random.Random
) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for room in rooms:
        if room.room_type in ("generic", "entrance"):
            cx, cy = room.center
            if grid[cy, cx] == 1:
                points.append((cx, cy))
            # Add a couple more random floor cells
            for _ in range(2):
                px = rng.randint(room.x + 1, room.x2 - 2)
                py = rng.randint(room.y + 1, room.y2 - 2)
                if grid[py, px] == 1:
                    points.append((px, py))
    # Guarantee at least one
    if not points:
        room = rooms[0]
        points.append(room.center)
    return points


def _place_loot_points(
    rooms: list[Room], grid: np.ndarray, rng: random.Random
) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for room in rooms:
        if room.room_type in ("treasure", "boss"):
            cx, cy = room.center
            if grid[cy, cx] == 1:
                points.append((cx, cy))
    return points


# ---------------------------------------------------------------------------
# Connectivity helpers
# ---------------------------------------------------------------------------

def _flood_fill(grid: np.ndarray, start: tuple[int, int]) -> set[tuple[int, int]]:
    """BFS flood-fill from *start* over walkable cells (>= 1)."""
    h, w = grid.shape
    visited: set[tuple[int, int]] = set()
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        if grid[y, x] == 0:
            continue
        visited.add((x, y))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            queue.append((x + dx, y + dy))
    return visited


def _verify_connectivity(layout: DungeonLayout) -> bool:
    """Return True if every room is reachable from the entrance."""
    if not layout.rooms:
        return True
    entrance = layout.rooms[0]
    reachable = _flood_fill(layout.grid, entrance.center)
    for room in layout.rooms[1:]:
        if room.center not in reachable:
            return False
    return True


def _ensure_connectivity(layout: DungeonLayout, rng: random.Random) -> None:
    """Add forced corridors until every room is reachable."""
    max_iters = len(layout.rooms) * 2
    for _ in range(max_iters):
        if _verify_connectivity(layout):
            return
        # Find first unreachable room
        entrance = layout.rooms[0]
        reachable = _flood_fill(layout.grid, entrance.center)
        for room in layout.rooms[1:]:
            if room.center not in reachable:
                # Connect to entrance room
                cx_a, cy_a = entrance.center
                cx_b, cy_b = room.center
                _carve_h_corridor(layout.grid, cy_a, cx_a, cx_b)
                _carve_v_corridor(layout.grid, cx_b, cy_a, cy_b)
                layout.corridors.append(((cx_a, cy_a), (cx_b, cy_b)))
                break

    if not _verify_connectivity(layout):
        raise ValueError("Dungeon generation failed: rooms are still disconnected")


# ---------------------------------------------------------------------------
# Cellular automata cave generation
# ---------------------------------------------------------------------------

def _count_neighbors(grid: np.ndarray, x: int, y: int) -> int:
    """Count wall neighbours in the 3x3 neighbourhood (including self)."""
    h, w = grid.shape
    count = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                if grid[ny, nx] == 0:
                    count += 1
            else:
                count += 1  # out-of-bounds counts as wall
    return count


def _find_regions(grid: np.ndarray) -> list[set[tuple[int, int]]]:
    """Identify all connected floor regions via flood-fill."""
    h, w = grid.shape
    visited: set[tuple[int, int]] = set()
    regions: list[set[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if grid[y, x] == 1 and (x, y) not in visited:
                region = _flood_fill(grid, (x, y))
                visited |= region
                if region:
                    regions.append(region)
    return regions


def generate_cave_map(
    width: int = 64,
    height: int = 64,
    fill_probability: float = 0.45,
    iterations: int = 5,
    seed: int = 0,
) -> CaveMap:
    """Generate a cave map using cellular automata (4-5 rule).

    Returns a :class:`CaveMap` with a single connected region.
    """
    rng = random.Random(seed)

    # Initialise random grid
    grid = np.zeros((height, width), dtype=np.int8)
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            grid[y, x] = 0 if rng.random() < fill_probability else 1

    # Borders are always wall
    grid[0, :] = 0
    grid[-1, :] = 0
    grid[:, 0] = 0
    grid[:, -1] = 0

    # Cellular automata iterations (4-5 rule)
    for _ in range(iterations):
        new_grid = grid.copy()
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                neighbors = _count_neighbors(grid, x, y)
                if neighbors >= 5:
                    new_grid[y, x] = 0  # wall
                elif neighbors < 4:
                    new_grid[y, x] = 1  # floor
                # else keep current
        grid = new_grid

    # Re-enforce borders
    grid[0, :] = 0
    grid[-1, :] = 0
    grid[:, 0] = 0
    grid[:, -1] = 0

    # Find connected regions
    regions = _find_regions(grid)

    if not regions:
        # Degenerate case -- open up the centre
        cy, cx = height // 2, width // 2
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                ny, nx = cy + dy, cx + dx
                if 0 < ny < height - 1 and 0 < nx < width - 1:
                    grid[ny, nx] = 1
        regions = _find_regions(grid)

    # Keep only the largest region
    largest_idx = max(range(len(regions)), key=lambda i: len(regions[i]))
    largest = regions[largest_idx]
    for y in range(height):
        for x in range(width):
            if grid[y, x] == 1 and (x, y) not in largest:
                grid[y, x] = 0

    # Recompute regions after pruning
    regions = [largest]

    return CaveMap(
        width=width,
        height=height,
        grid=grid,
        regions=regions,
        largest_region=0,
    )


# ---------------------------------------------------------------------------
# Town layout generation (Voronoi-based)
# ---------------------------------------------------------------------------

_DISTRICT_TYPES = ("civic", "residential", "commercial", "industrial")


def generate_town_layout(
    width: int = 200,
    height: int = 200,
    num_districts: int = 6,
    seed: int = 0,
) -> TownLayout:
    """Generate a town layout with Voronoi districts, roads, and plots.

    Returns a :class:`TownLayout` with deterministic output for a given seed.
    """
    rng = random.Random(seed)

    # 1. Seed points for districts (semi-structured with jitter)
    seeds = _generate_district_seeds(width, height, num_districts, rng)

    # 2. Assign each cell to nearest seed (Voronoi)
    assignment = np.zeros((height, width), dtype=np.int32)
    for y in range(height):
        for x in range(width):
            best_d = float("inf")
            best_i = 0
            for i, (sx, sy) in enumerate(seeds):
                d = abs(x - sx) + abs(y - sy)  # Manhattan distance
                if d < best_d:
                    best_d = d
                    best_i = i
            assignment[y, x] = best_i

    # 3. Build district data
    district_cells: dict[int, set[tuple[int, int]]] = {
        i: set() for i in range(len(seeds))
    }
    for y in range(height):
        for x in range(width):
            district_cells[assignment[y, x]].add((x, y))

    # Tag districts
    districts: list[dict] = []
    center_x, center_y = width // 2, height // 2
    dists_to_center = [
        (abs(sx - center_x) + abs(sy - center_y), i)
        for i, (sx, sy) in enumerate(seeds)
    ]
    dists_to_center.sort()

    # Civic = closest to center; industrial = farthest; commercial = next-to-civic; rest = residential
    type_assignment: dict[int, str] = {}
    type_assignment[dists_to_center[0][1]] = "civic"
    if len(dists_to_center) > 1:
        type_assignment[dists_to_center[1][1]] = "commercial"
    if len(dists_to_center) > 2:
        type_assignment[dists_to_center[-1][1]] = "industrial"
    for _, idx in dists_to_center:
        if idx not in type_assignment:
            type_assignment[idx] = "residential"

    for i, (sx, sy) in enumerate(seeds):
        districts.append(
            {
                "id": i,
                "center": (sx, sy),
                "type": type_assignment.get(i, "residential"),
                "cells": district_cells[i],
            }
        )

    # Sort by area descending; tag the largest non-civic district that
    # is not already assigned a specialist type as residential.
    by_area = sorted(districts, key=lambda d: len(d["cells"]), reverse=True)
    for d in by_area:
        if d["type"] not in ("civic", "commercial", "industrial"):
            d["type"] = "residential"
            break

    # 4. Roads along district boundaries
    roads: set[tuple[int, int]] = set()
    for y in range(height):
        for x in range(width):
            current = assignment[y, x]
            for dx, dy in ((1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if assignment[ny, nx] != current:
                        roads.add((x, y))
                        roads.add((nx, ny))

    # 5. Building plots via rectangular subdivision in each district
    building_plots = _subdivide_plots(districts, roads, rng)

    # 6. Landmarks at district centres on road-adjacent cells
    landmarks = _place_landmarks(districts, roads, seeds)

    return TownLayout(
        width=width,
        height=height,
        districts=districts,
        roads=roads,
        building_plots=building_plots,
        landmarks=landmarks,
    )


def _generate_district_seeds(
    width: int, height: int, num_districts: int, rng: random.Random
) -> list[tuple[int, int]]:
    """Generate semi-structured seed points with jitter."""
    seeds: list[tuple[int, int]] = []
    # Place in a rough grid with jitter
    cols = max(2, int(math.sqrt(num_districts)))
    rows = max(2, (num_districts + cols - 1) // cols)
    cell_w = width // cols
    cell_h = height // rows
    for i in range(num_districts):
        r = i // cols
        c = i % cols
        base_x = c * cell_w + cell_w // 2
        base_y = r * cell_h + cell_h // 2
        jitter_x = rng.randint(-cell_w // 4, cell_w // 4)
        jitter_y = rng.randint(-cell_h // 4, cell_h // 4)
        sx = max(1, min(width - 2, base_x + jitter_x))
        sy = max(1, min(height - 2, base_y + jitter_y))
        seeds.append((sx, sy))
    return seeds


def _subdivide_plots(
    districts: list[dict],
    roads: set[tuple[int, int]],
    rng: random.Random,
    plot_min: int = 8,
    plot_max: int = 16,
) -> list[dict]:
    """Subdivide district interiors into rectangular building plots."""
    plots: list[dict] = []
    for district in districts:
        cells = district["cells"]
        if not cells:
            continue
        # Bounding box of district
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Tile with random-sized plots
        y = min_y + 2
        while y < max_y - plot_min:
            ph = rng.randint(plot_min, plot_max)
            x = min_x + 2
            while x < max_x - plot_min:
                pw = rng.randint(plot_min, plot_max)
                # Check that the origin cell belongs to the district and that
                # a majority of the plot area is within the district
                if (x, y) not in cells:
                    x += pw + 2
                    continue
                count_in = 0
                count_total = 0
                for py in range(y, min(y + ph, max_y)):
                    for px in range(x, min(x + pw, max_x)):
                        count_total += 1
                        if (px, py) in cells and (px, py) not in roads:
                            count_in += 1
                if count_total > 0 and count_in / count_total > 0.6:
                    plots.append(
                        {
                            "position": (x, y),
                            "size": (pw, ph),
                            "district": district["id"],
                        }
                    )
                x += pw + 2  # 2-cell gap (road/spacing)
            y += ph + 2
    return plots


def _place_landmarks(
    districts: list[dict],
    roads: set[tuple[int, int]],
    seeds: list[tuple[int, int]],
) -> list[dict]:
    """Place landmarks at district centres, preferring road-adjacent cells."""
    landmarks: list[dict] = []
    for district in districts:
        cx, cy = district["center"]
        # Search with expanding radius for a road-adjacent cell
        best = (cx, cy)
        best_dist = float("inf")
        search_radius = 50  # broad search to guarantee finding roads
        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                nx, ny = cx + dx, cy + dy
                # Check if this cell is on a road or adjacent to one
                is_near_road = (nx, ny) in roads
                if not is_near_road:
                    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if (nx + ddx, ny + ddy) in roads:
                            is_near_road = True
                            break
                if is_near_road:
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best_dist = d
                        best = (nx, ny)
        landmarks.append(
            {
                "position": best,
                "district": district["id"],
                "district_type": district["type"],
            }
        )
    return landmarks
