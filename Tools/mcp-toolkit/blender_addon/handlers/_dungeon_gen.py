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
        for dy in range(2):  # 2 cells wide for combat clearance
            yy = y + dy
            if 0 <= yy < h and 0 <= x < w:
                if grid[yy, x] == 0:
                    grid[yy, x] = 2  # corridor


def _carve_v_corridor(grid: np.ndarray, x: int, y1: int, y2: int) -> None:
    lo, hi = min(y1, y2), max(y1, y2)
    h, w = grid.shape
    for y in range(lo, hi + 1):
        for dx in range(2):  # 2 cells wide for combat clearance
            xx = x + dx
            if 0 <= y < h and 0 <= xx < w:
                if grid[y, xx] == 0:
                    grid[y, xx] = 2  # corridor


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

    # 5. T-junction cleanup for corridor intersections
    _cleanup_t_junctions(grid, height, width)

    # 6. Place doors where corridors meet room edges
    doors = _place_doors(grid, rooms, height, width)

    # 7. Assign room types (pass grid dims for boss room boundary clamping)
    _assign_room_types(rooms, rng, grid=grid, grid_width=width, grid_height=height)

    # 8. Spawn / loot points
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

    # 9. Connectivity guarantee
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


def _cleanup_t_junctions(grid: np.ndarray, h: int, w: int) -> int:
    """Clean up T-junction artifacts where corridors meet at right angles.

    Fills in isolated wall cells surrounded on 3+ sides by corridor/floor
    to smooth corridor intersections.

    Returns the number of wall cells converted to corridor.
    """
    fixed = 0
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y, x] != 0:
                continue
            # Count walkable neighbours (floor=1, corridor=2, door=3)
            neighbours = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if grid[y + dy, x + dx] > 0:
                    neighbours += 1
            # Wall surrounded by 3+ walkable cells is a T-junction artifact
            if neighbours >= 3:
                grid[y, x] = 2  # convert to corridor
                fixed += 1
    return fixed


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


def _assign_room_types(
    rooms: list[Room], rng: random.Random, grid: np.ndarray | None = None, grid_width: int = 0, grid_height: int = 0
) -> None:
    """Assign specialised room types with size-based heuristics.

    Room type assignments:
    - entrance: first room
    - boss: last room, expanded to 2x size (clamped to grid bounds)
    - treasure: 1-2 smaller rooms chosen from the middle
    - secret: 10% chance for remaining generic rooms (smallest first)
    - generic: everything else

    Parameters
    ----------
    rooms : list[Room]
        Rooms to assign types to.
    rng : random.Random
        Seeded RNG for secret room assignment.
    grid_width : int
        Grid width for boundary clamping (0 = no clamping).
    grid_height : int
        Grid height for boundary clamping (0 = no clamping).
    """
    if not rooms:
        return

    rooms[0].room_type = "entrance"

    if len(rooms) > 1:
        boss = rooms[-1]
        boss.room_type = "boss"
        # Expand boss room to ~2x area, clamped to grid bounds
        new_w = boss.width * 2
        new_h = boss.height * 2
        if grid_width > 0:
            new_w = min(new_w, grid_width - boss.x)
        if grid_height > 0:
            new_h = min(new_h, grid_height - boss.y)

        # Check overlap with other rooms before expanding
        can_expand = True
        expanded_candidate = Room(boss.x, boss.y, max(new_w, boss.width), max(new_h, boss.height))
        for other_room in rooms:
            if other_room is boss:
                continue
            if expanded_candidate.intersects(other_room):
                can_expand = False
                break

        if can_expand:
            boss.width = max(new_w, boss.width)
            boss.height = max(new_h, boss.height)

        # Carve expanded floor tiles into grid so walls don't remain
        if grid is not None:
            g_h, g_w = grid.shape
            for cy in range(boss.y, min(boss.y + boss.height, g_h)):
                for cx in range(boss.x, min(boss.x + boss.width, g_w)):
                    if grid[cy, cx] == 0:  # wall
                        grid[cy, cx] = 1  # floor

    # Pick 1-2 treasure rooms from middle, preferring smaller ones
    middle = [r for r in rooms[1:-1] if r.room_type == "generic"] if len(rooms) > 2 else []
    treasure_count = min(2, len(middle))
    if middle:
        middle_sorted = sorted(middle, key=lambda r: r.width * r.height)
        chosen = middle_sorted[:treasure_count]
        for r in chosen:
            r.room_type = "treasure"

    # Secret rooms: 10% chance for remaining generic rooms
    remaining = [r for r in rooms if r.room_type == "generic"]
    if remaining:
        remaining_sorted = sorted(remaining, key=lambda r: r.width * r.height)
        for r in remaining_sorted:
            if rng.random() < 0.10:
                r.room_type = "secret"

    # Mark corridor entrances to secret rooms as breakable/hidden walls
    if grid is not None:
        for room in rooms:
            if room.room_type != "secret":
                continue
            g_h, g_w = grid.shape
            # Check horizontal edges (top and bottom of room)
            for x in range(room.x, room.x2):
                for edge_y in [room.y - 1, room.y2]:
                    if 0 <= edge_y < g_h and 0 <= x < g_w and grid[edge_y, x] == 2:
                        grid[edge_y, x] = 3  # hidden wall (breakable)
                        break
            # Check vertical edges (left and right of room)
            for y in range(room.y, room.y2):
                for edge_x in [room.x - 1, room.x2]:
                    if 0 <= y < g_h and 0 <= edge_x < g_w and grid[y, edge_x] == 2:
                        grid[y, edge_x] = 3  # hidden wall (breakable)
                        break


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
        if room.room_type in ("treasure", "boss", "secret"):
            cx, cy = room.center
            if 0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1] and grid[cy, cx] == 1:
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

    # 2. Assign each cell to nearest seed (Euclidean Voronoi)
    assignment = np.zeros((height, width), dtype=np.int32)
    for y in range(height):
        for x in range(width):
            best_d = float("inf")
            best_i = 0
            for i, (sx, sy) in enumerate(seeds):
                dx = x - sx
                dy = y - sy
                d = dx * dx + dy * dy  # Euclidean distance squared
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
        (math.sqrt((sx - center_x) ** 2 + (sy - center_y) ** 2), i)
        for i, (sx, sy) in enumerate(seeds)
    ]
    dists_to_center.sort()

    # market_square = closest to center; civic = next; industrial = farthest;
    # commercial = next-to-civic; rest = residential
    type_assignment: dict[int, str] = {}
    type_assignment[dists_to_center[0][1]] = "market_square"
    if len(dists_to_center) > 1:
        type_assignment[dists_to_center[1][1]] = "civic"
    if len(dists_to_center) > 2:
        type_assignment[dists_to_center[2][1]] = "commercial"
    if len(dists_to_center) > 3:
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

    # Sort by area descending; tag the largest non-specialist district
    # that is not already assigned a specialist type as residential.
    by_area = sorted(districts, key=lambda d: len(d["cells"]), reverse=True)
    for d in by_area:
        if d["type"] not in ("market_square", "civic", "commercial", "industrial"):
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

    # 4b. Connect district centers with roads (Bresenham-style lines)
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            sx0, sy0 = seeds[i]
            sx1, sy1 = seeds[j]
            # Only connect adjacent districts (share a boundary)
            shares_boundary = False
            for rx, ry in roads:
                if assignment[ry, rx] == i:
                    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nnx, nny = rx + ddx, ry + ddy
                        if 0 <= nnx < width and 0 <= nny < height:
                            if assignment[nny, nnx] == j:
                                shares_boundary = True
                                break
                if shares_boundary:
                    break
            if not shares_boundary:
                continue
            # Bresenham line from center to center
            _bresenham_road(sx0, sy0, sx1, sy1, roads, width, height)

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


def _bresenham_road(
    x0: int, y0: int, x1: int, y1: int,
    roads: set[tuple[int, int]],
    width: int, height: int,
    road_width: int = 2,
) -> None:
    """Rasterise a Bresenham line between two points and add to roads set.

    ``road_width`` adds parallel cells for a wider road.
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0

    while True:
        # Add road cells with width
        for offset in range(road_width):
            if dx >= dy:
                # Mostly horizontal -- widen vertically
                ny = y + offset
                if 0 <= x < width and 0 <= ny < height:
                    roads.add((x, ny))
            else:
                # Mostly vertical -- widen horizontally
                nx = x + offset
                if 0 <= nx < width and 0 <= y < height:
                    roads.add((nx, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


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
                    d = dx * dx + dy * dy  # Euclidean squared
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


# ---------------------------------------------------------------------------
# Multi-floor dungeon generation (WORLD-06)
# ---------------------------------------------------------------------------

@dataclass
class MultiFloorDungeon:
    """Multi-floor dungeon with vertical connections between floors."""

    width: int
    height: int
    num_floors: int
    floors: list[DungeonLayout] = field(default_factory=list)
    connections: list[dict] = field(default_factory=list)
    total_rooms: int = 0


def _place_connection_points(
    width: int,
    height: int,
    num_transitions: int,
    rng: random.Random,
    min_room_size: int = 6,
) -> list[tuple[int, int]]:
    """Place 1--2 connection points per floor transition.

    Returns grid coordinates that must fall within room cells.  The caller
    must guarantee that the generated dungeon has a walkable cell at each
    connection point -- :func:`generate_multi_floor_dungeon` enforces this.
    """
    points: list[tuple[int, int]] = []
    margin = min_room_size + 2  # stay away from edges
    for _ in range(num_transitions):
        # Place 1-2 connections per transition
        n_conns = rng.randint(1, 2)
        for _ in range(n_conns):
            cx = rng.randint(margin, width - margin - 1)
            cy = rng.randint(margin, height - margin - 1)
            points.append((cx, cy))
    return points


def generate_multi_floor_dungeon(
    width: int = 64,
    height: int = 64,
    num_floors: int = 3,
    min_room_size: int = 6,
    max_depth: int = 5,
    cell_size: float = 2.0,
    wall_height: float = 3.0,
    connection_types: Optional[list[str]] = None,
    seed: int = 0,
) -> MultiFloorDungeon:
    """Generate a multi-floor dungeon with vertical connections.

    Parameters
    ----------
    width, height : int
        Grid dimensions for each floor.
    num_floors : int
        Number of dungeon floors (default 3).
    min_room_size : int
        Minimum room size for BSP.
    max_depth : int
        BSP partition depth.
    cell_size : float
        World-space size of each grid cell.
    wall_height : float
        Height of walls per floor.
    connection_types : list of str, optional
        Types of vertical connections: "staircase", "elevator", "ladder",
        "pit_drop".  Defaults to ``["staircase"]``.
    seed : int
        Random seed for deterministic output.

    Returns
    -------
    MultiFloorDungeon
        Contains per-floor DungeonLayout, connection dicts, total_rooms.
    """
    if connection_types is None:
        connection_types = ["staircase"]

    rng = random.Random(seed)

    # 1. Determine staircase/connection positions shared across floor transitions
    num_transitions = num_floors - 1
    connection_positions = _place_connection_points(
        width, height, num_transitions, rng, min_room_size
    )

    # 2. Generate each floor
    floors: list[DungeonLayout] = []
    connections: list[dict] = []
    total_rooms = 0

    # Track which connection positions belong to which transition
    conn_idx = 0
    transition_conns: list[list[tuple[int, int]]] = []
    for t in range(num_transitions):
        n_conns = rng.randint(1, 2)
        t_conns: list[tuple[int, int]] = []
        for _ in range(n_conns):
            if conn_idx < len(connection_positions):
                t_conns.append(connection_positions[conn_idx])
                conn_idx += 1
        transition_conns.append(t_conns)

    for floor_idx in range(num_floors):
        floor_seed = seed + floor_idx * 1000
        layout = generate_bsp_dungeon(
            width=width,
            height=height,
            min_room_size=min_room_size,
            max_depth=max_depth,
            seed=floor_seed,
        )

        # Ensure connection points are walkable on this floor
        # For transitions FROM this floor (floor_idx) and TO this floor (floor_idx - 1)
        if floor_idx < num_transitions:
            for cx, cy in transition_conns[floor_idx]:
                if layout.grid[cy, cx] == 0:
                    # Carve a small room at the connection point
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            ny, nx = cy + dy, cx + dx
                            if 0 < ny < height - 1 and 0 < nx < width - 1:
                                layout.grid[ny, nx] = 1
                    # Connect to nearest room
                    nearest_room = min(
                        layout.rooms,
                        key=lambda r: abs(r.center[0] - cx) + abs(r.center[1] - cy),
                    )
                    rcx, rcy = nearest_room.center
                    _carve_h_corridor(layout.grid, cy, cx, rcx)
                    _carve_v_corridor(layout.grid, rcx, cy, rcy)

        if floor_idx > 0:
            for cx, cy in transition_conns[floor_idx - 1]:
                if layout.grid[cy, cx] == 0:
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            ny, nx = cy + dy, cx + dx
                            if 0 < ny < height - 1 and 0 < nx < width - 1:
                                layout.grid[ny, nx] = 1
                    nearest_room = min(
                        layout.rooms,
                        key=lambda r: abs(r.center[0] - cx) + abs(r.center[1] - cy),
                    )
                    rcx, rcy = nearest_room.center
                    _carve_h_corridor(layout.grid, cy, cx, rcx)
                    _carve_v_corridor(layout.grid, rcx, cy, rcy)

        floors.append(layout)
        total_rooms += len(layout.rooms)

    # 3. Build connection records
    for t_idx, t_conns in enumerate(transition_conns):
        conn_type = connection_types[t_idx % len(connection_types)]
        for pos in t_conns:
            connections.append({
                "from_floor": t_idx,
                "to_floor": t_idx + 1,
                "position": pos,
                "type": conn_type,
            })

    return MultiFloorDungeon(
        width=width,
        height=height,
        num_floors=num_floors,
        floors=floors,
        connections=connections,
        total_rooms=total_rooms,
    )


# ---------------------------------------------------------------------------
# Dungeon prop placement (pure-logic, no bpy)
# ---------------------------------------------------------------------------

# Prop types that can appear in generic rooms
_GENERIC_ROOM_PROPS = ("crate", "barrel", "skull_pile")


def generate_dungeon_prop_placements(
    layout: DungeonLayout,
    seed: int = 0,
) -> list[dict]:
    """Generate prop placement data for a dungeon layout.

    Pure-logic function -- returns placement dicts, not Blender objects.
    The caller (worldbuilding handler) consumes these and creates geometry
    via DUNGEON_PROP_MAP + mesh_from_spec.

    Placement rules by room type:
    - Corridors: torch_sconce every 4-6 cells along walls (alternating sides)
    - Boss rooms: altar at center, pillar at each corner
    - Treasure rooms: chest at center, torch_sconce at corners
    - Secret rooms: chest at center, skull_pile for atmosphere
    - Generic rooms: 1-2 random props (crate, barrel, skull_pile)
    - All rooms: 30% chance of archway at each door position

    Args:
        layout: DungeonLayout with rooms, corridors, doors, grid.
        seed: Random seed for deterministic output.

    Returns:
        List of dicts: ``{"type": str, "position": (x, y, z),
        "rotation": float, "room_type": str}``
    """
    rng = random.Random(seed)
    props: list[dict] = []

    # --- Room-based props ---
    for room in layout.rooms:
        cx, cy = room.center
        rt = room.room_type

        if rt == "boss":
            # Altar at center
            props.append({
                "type": "altar",
                "position": (cx, cy, 0),
                "rotation": 0.0,
                "room_type": rt,
            })
            # Pillar at each corner
            for dx, dy in [(0, 0), (room.width - 1, 0),
                           (0, room.height - 1), (room.width - 1, room.height - 1)]:
                px = room.x + dx
                py = room.y + dy
                props.append({
                    "type": "pillar",
                    "position": (px, py, 0),
                    "rotation": 0.0,
                    "room_type": rt,
                })

        elif rt == "treasure":
            # Chest at center
            props.append({
                "type": "chest",
                "position": (cx, cy, 0),
                "rotation": 0.0,
                "room_type": rt,
            })
            # Torch sconce at corners
            for dx, dy in [(0, 0), (room.width - 1, 0),
                           (0, room.height - 1), (room.width - 1, room.height - 1)]:
                px = room.x + dx
                py = room.y + dy
                props.append({
                    "type": "torch_sconce",
                    "position": (px, py, 0),
                    "rotation": 0.0,
                    "room_type": rt,
                })

        elif rt == "secret":
            # Secret room: chest at center + skull_pile for atmosphere
            props.append({
                "type": "chest",
                "position": (cx, cy, 0),
                "rotation": 0.0,
                "room_type": rt,
            })
            props.append({
                "type": "skull_pile",
                "position": (room.x + 1, room.y + 1, 0),
                "rotation": rng.uniform(0, 2 * math.pi),
                "room_type": rt,
            })

        elif rt in ("generic", "entrance", "exit"):
            # 1-2 random props
            n_props = rng.randint(1, 2)
            for _ in range(n_props):
                prop_type = rng.choice(_GENERIC_ROOM_PROPS)
                px = rng.randint(room.x + 1, max(room.x + 1, room.x2 - 2))
                py = rng.randint(room.y + 1, max(room.y + 1, room.y2 - 2))
                rotation = rng.uniform(0, 2 * math.pi)
                props.append({
                    "type": prop_type,
                    "position": (px, py, 0),
                    "rotation": rotation,
                    "room_type": rt,
                })

    # --- Corridor torch sconces ---
    # Walk corridors and place torches every 4-6 cells
    for (x1, y1), (x2, y2) in layout.corridors:
        # Compute corridor cells (L-shaped: horizontal then vertical)
        cells: list[tuple[int, int]] = []
        # Horizontal segment
        lo_x, hi_x = min(x1, x2), max(x1, x2)
        for x in range(lo_x, hi_x + 1):
            cells.append((x, y1))
        # Vertical segment
        lo_y, hi_y = min(y1, y2), max(y1, y2)
        for y in range(lo_y, hi_y + 1):
            cells.append((x2, y))

        # Place torch every 4-6 cells, alternating sides
        spacing = rng.randint(4, 6)
        side = 1
        for i in range(0, len(cells), spacing):
            cx_t, cy_t = cells[i]
            props.append({
                "type": "torch_sconce",
                "position": (cx_t, cy_t, 0),
                "rotation": side * math.pi / 2,
                "room_type": "corridor",
            })
            side *= -1

    # --- Archways at doorways (30% chance) ---
    for dx, dy in layout.doors:
        if rng.random() < 0.3:
            props.append({
                "type": "archway",
                "position": (dx, dy, 0),
                "rotation": 0.0,
                "room_type": "doorway",
            })

    return props
