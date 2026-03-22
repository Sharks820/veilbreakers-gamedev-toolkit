"""Settlement composition system for generating complete, unique locations.

Generates towns, camps, castles, villages, and outposts with:
- Unique building placement per seed
- Road networks connecting all structures
- Prop decoration (signs, crates, market stalls, etc.)
- Room function-based interior furnishing
- Terrain-aware foundation placement

Pure-logic data structures only -- NO bpy/bmesh imports.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Settlement type configurations
# ---------------------------------------------------------------------------

SETTLEMENT_TYPES: dict[str, dict[str, Any]] = {
    "village": {
        "building_count": (4, 8),
        "has_walls": False,
        "has_market": False,
        "has_shrine": True,
        "road_style": "dirt_path",
        "building_types": [
            "abandoned_house", "abandoned_house", "forge", "shrine_minor",
        ],
        "prop_density": 0.3,
        "perimeter_props": ["fence", "signpost"],
        "layout_pattern": "organic",
    },
    "town": {
        "building_count": (8, 16),
        "has_walls": True,
        "has_market": True,
        "has_shrine": True,
        "road_style": "cobblestone",
        "building_types": [
            "abandoned_house", "forge", "shrine_major", "market_stall_cluster",
        ],
        "prop_density": 0.5,
        "perimeter_props": ["wall_segment", "gate", "watchtower"],
        "layout_pattern": "grid",
    },
    "bandit_camp": {
        "building_count": (3, 6),
        "has_walls": False,
        "has_market": False,
        "has_shrine": False,
        "road_style": "none",
        "building_types": ["tent", "lean_to", "campfire_area", "cage"],
        "prop_density": 0.6,
        "perimeter_props": ["barricade", "spike_fence", "lookout_post"],
        "layout_pattern": "circular",
    },
    "castle": {
        "building_count": (5, 10),
        "has_walls": True,
        "has_market": False,
        "has_shrine": True,
        "road_style": "stone",
        "building_types": [
            "ruined_fortress_tower", "shrine_minor", "forge", "barracks",
        ],
        "prop_density": 0.4,
        "perimeter_props": ["wall_segment", "gate_large", "corner_tower"],
        "layout_pattern": "concentric",
    },
    "outpost": {
        "building_count": (2, 4),
        "has_walls": True,
        "has_market": False,
        "has_shrine": False,
        "road_style": "dirt_path",
        "building_types": ["watchtower", "barracks", "supply_tent"],
        "prop_density": 0.3,
        "perimeter_props": ["palisade", "gate"],
        "layout_pattern": "grid",
    },
}

# ---------------------------------------------------------------------------
# Room function -> furniture mapping
# ---------------------------------------------------------------------------

ROOM_FURNISHINGS: dict[str, list[str]] = {
    "bedroom": ["bed_frame", "chest", "candelabra", "rug"],
    "kitchen": ["table", "chair", "barrel", "shelf", "cauldron"],
    "smithy": ["anvil", "forge_fire", "bellows", "weapon_rack", "quench_trough"],
    "shrine_room": ["altar", "candelabra", "prayer_mat", "offering_bowl"],
    "storage": ["barrel", "crate", "sack", "shelf"],
    "tavern": ["table", "chair", "chair", "barrel", "candelabra", "banner"],
    "prison": ["shackle", "chain", "cell_door_broken", "skull_pile"],
    "throne_room": [
        "bone_throne", "banner", "candelabra", "rug", "chandelier",
    ],
    "barracks": ["bed_frame", "weapon_rack", "chest", "barrel"],
    "market": ["market_stall", "crate", "sack", "basket", "signpost"],
    "guard_post": ["weapon_rack", "chair", "lantern", "barrel"],
}

# Building type -> default room functions
_BUILDING_ROOMS: dict[str, list[str]] = {
    "abandoned_house": ["bedroom", "kitchen", "storage"],
    "forge": ["smithy", "storage"],
    "shrine_minor": ["shrine_room"],
    "shrine_major": ["shrine_room", "storage"],
    "market_stall_cluster": ["market"],
    "tent": ["bedroom"],
    "lean_to": ["storage"],
    "campfire_area": [],
    "cage": ["prison"],
    "ruined_fortress_tower": ["guard_post", "storage"],
    "barracks": ["barracks", "barracks", "storage"],
    "watchtower": ["guard_post"],
    "supply_tent": ["storage"],
}

# Furniture bounding boxes (width, depth) for collision checks
_FURNITURE_SIZES: dict[str, tuple[float, float]] = {
    "bed_frame": (1.0, 2.0),
    "chest": (0.8, 0.5),
    "candelabra": (0.3, 0.3),
    "rug": (1.5, 2.0),
    "table": (1.2, 0.8),
    "chair": (0.5, 0.5),
    "barrel": (0.5, 0.5),
    "shelf": (1.0, 0.4),
    "cauldron": (0.6, 0.6),
    "anvil": (0.7, 0.5),
    "forge_fire": (1.0, 1.0),
    "bellows": (0.4, 0.6),
    "weapon_rack": (1.2, 0.3),
    "quench_trough": (0.8, 0.5),
    "altar": (1.0, 0.6),
    "prayer_mat": (0.8, 1.2),
    "offering_bowl": (0.3, 0.3),
    "crate": (0.6, 0.6),
    "sack": (0.4, 0.4),
    "banner": (0.3, 0.1),
    "market_stall": (2.0, 1.2),
    "basket": (0.4, 0.4),
    "signpost": (0.3, 0.3),
    "shackle": (0.3, 0.3),
    "chain": (0.2, 0.2),
    "cell_door_broken": (1.0, 0.2),
    "skull_pile": (0.5, 0.5),
    "bone_throne": (1.2, 1.0),
    "chandelier": (0.8, 0.8),
    "lantern": (0.3, 0.3),
}

# Furniture placement rules: "wall" = against wall, "center" = in open area
_FURNITURE_PLACEMENT: dict[str, str] = {
    "bed_frame": "wall",
    "chest": "wall",
    "candelabra": "wall",
    "rug": "center",
    "table": "center",
    "chair": "center",
    "barrel": "wall",
    "shelf": "wall",
    "cauldron": "center",
    "anvil": "center",
    "forge_fire": "center",
    "bellows": "wall",
    "weapon_rack": "wall",
    "quench_trough": "wall",
    "altar": "center",
    "prayer_mat": "center",
    "offering_bowl": "center",
    "crate": "wall",
    "sack": "wall",
    "banner": "wall",
    "market_stall": "center",
    "basket": "wall",
    "signpost": "center",
    "shackle": "wall",
    "chain": "wall",
    "cell_door_broken": "wall",
    "skull_pile": "wall",
    "bone_throne": "center",
    "chandelier": "center",
    "lantern": "wall",
}

# Road-side decoration props (placed at intervals along roads)
_ROAD_PROPS: dict[str, list[str]] = {
    "cobblestone": ["lantern_post", "bench", "planter"],
    "dirt_path": ["torch_post", "milestone"],
    "stone": ["brazier", "banner_stand", "statue_small"],
    "none": [],
}

# Open-area scatter props
_SCATTER_PROPS: list[str] = [
    "rock_small", "rock_medium", "debris_pile", "dead_bush",
    "fallen_log", "mushroom_cluster", "bone_scatter",
]

# Building footprint sizes (width, depth)
_BUILDING_FOOTPRINTS: dict[str, tuple[float, float]] = {
    "abandoned_house": (8.0, 6.0),
    "forge": (7.0, 7.0),
    "shrine_minor": (5.0, 5.0),
    "shrine_major": (8.0, 8.0),
    "market_stall_cluster": (10.0, 6.0),
    "tent": (4.0, 4.0),
    "lean_to": (3.0, 3.0),
    "campfire_area": (5.0, 5.0),
    "cage": (3.0, 3.0),
    "ruined_fortress_tower": (6.0, 6.0),
    "barracks": (10.0, 8.0),
    "watchtower": (4.0, 4.0),
    "supply_tent": (5.0, 5.0),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dist2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _aabb_overlaps(
    pos_a: tuple[float, float],
    size_a: tuple[float, float],
    pos_b: tuple[float, float],
    size_b: tuple[float, float],
    margin: float = 1.0,
) -> bool:
    """Check AABB overlap with margin between two axis-aligned rectangles.

    Each rectangle is defined by its center ``pos`` and (width, depth).
    """
    hw_a, hd_a = size_a[0] / 2.0 + margin, size_a[1] / 2.0 + margin
    hw_b, hd_b = size_b[0] / 2.0, size_b[1] / 2.0

    return (
        abs(pos_a[0] - pos_b[0]) < hw_a + hw_b
        and abs(pos_a[1] - pos_b[1]) < hd_a + hd_b
    )


def _angle_to(
    from_pt: tuple[float, float], to_pt: tuple[float, float]
) -> float:
    """Angle in radians from ``from_pt`` to ``to_pt``."""
    return math.atan2(to_pt[1] - from_pt[1], to_pt[0] - from_pt[0])


# ---------------------------------------------------------------------------
# Building placement
# ---------------------------------------------------------------------------

def _place_buildings(
    rng: random.Random,
    config: dict[str, Any],
    center: tuple[float, float],
    radius: float,
) -> list[dict[str, Any]]:
    """Place buildings in a layout pattern, avoiding overlaps.

    Each building gets:
    - position: (x, y) world coordinate
    - rotation: facing road/center in radians
    - type: building type string
    - unique_seed: per-building seed for variation
    - room_functions: list of room type strings
    - footprint: (width, depth) tuple

    Placement rules:
    - Shrine placed at center (concentric/grid) or near edge (organic)
    - Market placed at the largest road intersection area
    - Other buildings distributed via layout pattern

    Parameters
    ----------
    rng : random.Random
        Seeded RNG instance.
    config : dict
        Settlement configuration from SETTLEMENT_TYPES.
    center : tuple
        Settlement center (x, y).
    radius : float
        Maximum settlement radius.

    Returns
    -------
    list of dict
        Placed building specifications.
    """
    min_count, max_count = config["building_count"]
    count = rng.randint(min_count, max_count)
    building_types = config["building_types"]
    pattern = config.get("layout_pattern", "organic")
    has_shrine = config.get("has_shrine", False)
    has_market = config.get("has_market", False)

    buildings: list[dict[str, Any]] = []
    occupied: list[tuple[tuple[float, float], tuple[float, float]]] = []

    def _try_place(
        btype: str, target_pos: tuple[float, float]
    ) -> dict[str, Any] | None:
        fp = _BUILDING_FOOTPRINTS.get(btype, (6.0, 6.0))
        # Check collisions with all already-placed buildings
        for opos, osize in occupied:
            if _aabb_overlaps(target_pos, fp, opos, osize, margin=2.0):
                return None
        rotation = _angle_to(target_pos, center)
        building = {
            "position": (round(target_pos[0], 2), round(target_pos[1], 2)),
            "rotation": round(rotation, 4),
            "type": btype,
            "unique_seed": rng.randint(0, 2**31),
            "room_functions": list(
                _BUILDING_ROOMS.get(btype, ["storage"])
            ),
            "footprint": fp,
        }
        occupied.append((target_pos, fp))
        return building

    # --- Priority placements ---

    # 1. Shrine at center or near edge
    if has_shrine:
        shrine_types = [
            t for t in building_types if "shrine" in t
        ]
        shrine_type = shrine_types[0] if shrine_types else "shrine_minor"
        if pattern in ("concentric", "grid"):
            shrine_pos = (center[0], center[1])
        else:
            angle = rng.uniform(0, 2 * math.pi)
            shrine_pos = (
                center[0] + math.cos(angle) * radius * 0.7,
                center[1] + math.sin(angle) * radius * 0.7,
            )
        placed = _try_place(shrine_type, shrine_pos)
        if placed:
            buildings.append(placed)
            count -= 1

    # 2. Market near center (offset slightly for crossroads feel)
    if has_market:
        market_types = [
            t for t in building_types if "market" in t
        ]
        market_type = market_types[0] if market_types else "market_stall_cluster"
        market_offset = rng.uniform(3.0, radius * 0.3)
        market_angle = rng.uniform(0, 2 * math.pi)
        market_pos = (
            center[0] + math.cos(market_angle) * market_offset,
            center[1] + math.sin(market_angle) * market_offset,
        )
        placed = _try_place(market_type, market_pos)
        if placed:
            buildings.append(placed)
            count -= 1

    # --- Remaining buildings by layout pattern ---
    # Filter building types to exclude already-placed priority types
    remaining_types = [
        t for t in building_types
        if "shrine" not in t and "market" not in t
    ]
    if not remaining_types:
        remaining_types = list(building_types)

    for i in range(count):
        btype = remaining_types[i % len(remaining_types)]
        placed_building = None

        for attempt in range(80):
            if pattern == "circular":
                # Circular: buildings arranged in a ring
                angle = (2 * math.pi * i / max(count, 1)) + rng.uniform(
                    -0.3, 0.3
                )
                dist = rng.uniform(radius * 0.3, radius * 0.75)
                px = center[0] + math.cos(angle) * dist
                py = center[1] + math.sin(angle) * dist

            elif pattern == "grid":
                # Grid: rough grid with jitter
                cols = max(1, int(math.ceil(math.sqrt(count))))
                row = i // cols
                col = i % cols
                spacing = (radius * 1.4) / max(cols, 1)
                base_x = center[0] - radius * 0.7 + col * spacing + spacing * 0.5
                base_y = center[1] - radius * 0.7 + row * spacing + spacing * 0.5
                px = base_x + rng.uniform(-spacing * 0.2, spacing * 0.2)
                py = base_y + rng.uniform(-spacing * 0.2, spacing * 0.2)

            elif pattern == "concentric":
                # Concentric: inner ring is important, outer ring is common
                ring = 0 if i < max(count // 3, 1) else 1
                ring_radius = radius * (0.3 if ring == 0 else 0.65)
                ring_count = max(count // 3, 1) if ring == 0 else count
                angle = (2 * math.pi * i / max(ring_count, 1)) + rng.uniform(
                    -0.4, 0.4
                )
                px = center[0] + math.cos(angle) * ring_radius
                py = center[1] + math.sin(angle) * ring_radius

            else:  # organic
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(radius * 0.15, radius * 0.8)
                px = center[0] + math.cos(angle) * dist
                py = center[1] + math.sin(angle) * dist

            candidate_pos = (px, py)
            result = _try_place(btype, candidate_pos)
            if result is not None:
                placed_building = result
                break

        if placed_building is not None:
            buildings.append(placed_building)

    return buildings


# ---------------------------------------------------------------------------
# Road network generation (MST + main road)
# ---------------------------------------------------------------------------

def _generate_roads(
    buildings: list[dict[str, Any]],
    center: tuple[float, float],
    road_style: str,
) -> list[dict[str, Any]]:
    """Generate road segments connecting all buildings via MST.

    Also adds a main road from the settlement edge to the center.

    Each road segment:
    - start: (x, y)
    - end: (x, y)
    - width: float
    - style: road style string

    Parameters
    ----------
    buildings : list of dict
        Placed buildings with ``position`` keys.
    center : tuple
        Settlement center.
    road_style : str
        Road surface type (cobblestone, dirt_path, stone, none).

    Returns
    -------
    list of dict
        Road segment specifications.
    """
    if road_style == "none" or len(buildings) < 2:
        return []

    roads: list[dict[str, Any]] = []
    n = len(buildings)
    positions = [b["position"] for b in buildings]

    # Build distance matrix
    dist_matrix = [
        [_dist2d(positions[i], positions[j]) for j in range(n)]
        for i in range(n)
    ]

    # Prim's MST
    in_tree = [False] * n
    in_tree[0] = True
    mst_edges: list[tuple[int, int]] = []

    for _ in range(n - 1):
        best_i, best_j, best_d = -1, -1, float("inf")
        for i in range(n):
            if not in_tree[i]:
                continue
            for j in range(n):
                if in_tree[j]:
                    continue
                if dist_matrix[i][j] < best_d:
                    best_i, best_j, best_d = i, j, dist_matrix[i][j]
        if best_j == -1:
            break
        mst_edges.append((best_i, best_j))
        in_tree[best_j] = True

    # Width based on style
    width_map = {
        "cobblestone": 3.0,
        "dirt_path": 2.0,
        "stone": 3.5,
    }
    base_width = width_map.get(road_style, 2.0)

    for i, j in mst_edges:
        roads.append({
            "start": positions[i],
            "end": positions[j],
            "width": base_width,
            "style": road_style,
        })

    # Main road: from settlement edge toward center (closest building)
    # Find the building closest to center
    closest_idx = min(range(n), key=lambda k: _dist2d(positions[k], center))
    # Determine edge point: extend outward from center through the farthest building
    farthest_idx = max(
        range(n), key=lambda k: _dist2d(positions[k], center)
    )
    far_pos = positions[farthest_idx]
    edge_angle = _angle_to(center, far_pos)
    farthest_dist = _dist2d(center, far_pos)
    edge_point = (
        center[0] + math.cos(edge_angle) * (farthest_dist + 10.0),
        center[1] + math.sin(edge_angle) * (farthest_dist + 10.0),
    )
    roads.append({
        "start": (round(edge_point[0], 2), round(edge_point[1], 2)),
        "end": positions[closest_idx],
        "width": base_width + 1.0,
        "style": road_style,
        "is_main_road": True,
    })

    return roads


# ---------------------------------------------------------------------------
# Prop scatter
# ---------------------------------------------------------------------------

def _scatter_settlement_props(
    rng: random.Random,
    buildings: list[dict[str, Any]],
    roads: list[dict[str, Any]],
    config: dict[str, Any],
    radius: float,
    center: tuple[float, float] = (0.0, 0.0),
) -> list[dict[str, Any]]:
    """Scatter decoration props throughout the settlement.

    Placement rules:
    - Road-side: lanterns/torches at regular intervals along roads
    - Building-adjacent: crates, barrels, signs near building doors
    - Open-area: random scatter of rocks, debris in remaining space

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    buildings : list of dict
        Placed buildings.
    roads : list of dict
        Road segments.
    config : dict
        Settlement configuration.
    radius : float
        Settlement radius.
    center : tuple
        Settlement center.

    Returns
    -------
    list of dict
        Prop placement specs with position, rotation, type, scale.
    """
    props: list[dict[str, Any]] = []
    prop_density = config.get("prop_density", 0.3)
    road_style = config.get("road_style", "none")

    # 1. Road-side props: place at regular intervals along each road
    road_prop_types = _ROAD_PROPS.get(road_style, [])
    if road_prop_types:
        interval = max(4.0, 8.0 * (1.0 - prop_density))
        for road in roads:
            sx, sy = road["start"]
            ex, ey = road["end"]
            length = _dist2d((sx, sy), (ex, ey))
            if length < 0.01:
                continue
            dx = (ex - sx) / length
            dy = (ey - sy) / length
            # Perpendicular offset for placing props beside the road
            perp_x, perp_y = -dy, dx
            offset_dist = road["width"] * 0.6

            num_props = max(1, int(length / interval))
            for k in range(num_props):
                t = (k + 0.5) / max(num_props, 1)
                px = sx + dx * length * t
                py = sy + dy * length * t
                # Alternate sides
                side = 1.0 if k % 2 == 0 else -1.0
                px += perp_x * offset_dist * side
                py += perp_y * offset_dist * side
                props.append({
                    "type": rng.choice(road_prop_types),
                    "position": (round(px, 2), round(py, 2)),
                    "rotation": round(
                        math.atan2(dy, dx) + math.pi / 2, 4
                    ),
                    "scale": round(rng.uniform(0.85, 1.15), 2),
                    "source": "road",
                })

    # 2. Building-adjacent props: crates, barrels near doors
    building_props = ["crate", "barrel", "sack", "firewood_stack"]
    for bld in buildings:
        bx, by = bld["position"]
        rot = bld["rotation"]
        fp = bld.get("footprint", (6.0, 6.0))
        # Place 1-3 props near the door side (front of building)
        num_adj = rng.randint(1, max(1, int(3 * prop_density + 0.5)))
        for j in range(num_adj):
            offset_along = rng.uniform(-fp[0] * 0.3, fp[0] * 0.3)
            offset_out = fp[1] * 0.5 + rng.uniform(0.5, 2.0)
            # Place in front of building (rotation direction)
            px = bx + math.cos(rot) * offset_out + math.sin(rot) * offset_along
            py = by + math.sin(rot) * offset_out - math.cos(rot) * offset_along
            props.append({
                "type": rng.choice(building_props),
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(rng.uniform(0, 2 * math.pi), 4),
                "scale": round(rng.uniform(0.8, 1.2), 2),
                "source": "building_adjacent",
            })

    # 3. Open-area scatter: random debris/rocks in settlement area
    num_scatter = max(
        2, int(prop_density * radius * 0.8)
    )
    for _ in range(num_scatter):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(radius * 0.1, radius * 0.9)
        px = center[0] + math.cos(angle) * dist
        py = center[1] + math.sin(angle) * dist

        # Skip if too close to a building
        too_close = False
        for bld in buildings:
            if _dist2d((px, py), bld["position"]) < 4.0:
                too_close = True
                break
        if too_close:
            continue

        props.append({
            "type": rng.choice(_SCATTER_PROPS),
            "position": (round(px, 2), round(py, 2)),
            "rotation": round(rng.uniform(0, 2 * math.pi), 4),
            "scale": round(rng.uniform(0.6, 1.4), 2),
            "source": "scatter",
        })

    return props


# ---------------------------------------------------------------------------
# Interior furnishing
# ---------------------------------------------------------------------------

def _furnish_interior(
    rng: random.Random,
    room_type: str,
    room_bounds: dict[str, Any],
) -> list[dict[str, Any]]:
    """Place furniture in a room based on its function.

    Wall-aligned items are placed against the room perimeter;
    center items are placed in the open area.  Collision checks
    prevent overlapping furniture.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    room_type : str
        Room function key (bedroom, kitchen, smithy, ...).
    room_bounds : dict
        ``{"min": (x, y), "max": (x, y)}`` of the room.

    Returns
    -------
    list of dict
        Furniture placements with type, position, rotation.
    """
    furnishing_list = ROOM_FURNISHINGS.get(room_type, ["crate"])
    rx_min, ry_min = room_bounds["min"]
    rx_max, ry_max = room_bounds["max"]
    room_w = rx_max - rx_min
    room_d = ry_max - ry_min

    if room_w < 1.0 or room_d < 1.0:
        return []

    placed: list[dict[str, Any]] = []
    placed_positions: list[tuple[tuple[float, float], tuple[float, float]]] = []

    # Compute wall and center zones
    wall_margin = 0.5
    center_margin = room_w * 0.25

    for item_type in furnishing_list:
        item_size = _FURNITURE_SIZES.get(item_type, (0.5, 0.5))
        placement_rule = _FURNITURE_PLACEMENT.get(item_type, "wall")

        placed_item = None
        for attempt in range(30):
            if placement_rule == "wall":
                # Pick a random wall (N/S/E/W) and place along it
                wall = rng.choice(["north", "south", "east", "west"])
                if wall == "north":
                    px = rng.uniform(
                        rx_min + wall_margin + item_size[0] / 2,
                        rx_max - wall_margin - item_size[0] / 2,
                    )
                    py = ry_max - wall_margin - item_size[1] / 2
                    rot = 0.0
                elif wall == "south":
                    px = rng.uniform(
                        rx_min + wall_margin + item_size[0] / 2,
                        rx_max - wall_margin - item_size[0] / 2,
                    )
                    py = ry_min + wall_margin + item_size[1] / 2
                    rot = math.pi
                elif wall == "east":
                    px = rx_max - wall_margin - item_size[1] / 2
                    py = rng.uniform(
                        ry_min + wall_margin + item_size[0] / 2,
                        ry_max - wall_margin - item_size[0] / 2,
                    )
                    rot = math.pi / 2
                else:  # west
                    px = rx_min + wall_margin + item_size[1] / 2
                    py = rng.uniform(
                        ry_min + wall_margin + item_size[0] / 2,
                        ry_max - wall_margin - item_size[0] / 2,
                    )
                    rot = -math.pi / 2
            else:
                # Center placement
                px = rng.uniform(
                    rx_min + center_margin + item_size[0] / 2,
                    rx_max - center_margin - item_size[0] / 2,
                )
                py = rng.uniform(
                    ry_min + center_margin + item_size[1] / 2,
                    ry_max - center_margin - item_size[1] / 2,
                )
                rot = rng.uniform(0, 2 * math.pi)

            # Collision check
            overlaps = False
            for opos, osize in placed_positions:
                if _aabb_overlaps(
                    (px, py), item_size, opos, osize, margin=0.2
                ):
                    overlaps = True
                    break

            if not overlaps:
                placed_item = {
                    "type": item_type,
                    "position": (round(px, 2), round(py, 2)),
                    "rotation": round(rot, 4),
                }
                placed_positions.append(((px, py), item_size))
                break

        if placed_item is not None:
            placed.append(placed_item)

    return placed


# ---------------------------------------------------------------------------
# Building variation
# ---------------------------------------------------------------------------

def _apply_building_variation(
    rng: random.Random,
    building: dict[str, Any],
) -> dict[str, Any]:
    """Apply per-instance visual variation to a building.

    Randomizes:
    - wall_damage: 0-30% of wall surface showing damage
    - roof_condition: intact / damaged / missing
    - window_count: 0-4 windows
    - prop_additions: list of small detail props on/near the building
    - door_condition: intact / broken / missing

    Parameters
    ----------
    rng : random.Random
        Seeded with the building's unique_seed.
    building : dict
        Building spec to augment (not mutated; returns new dict).

    Returns
    -------
    dict
        Building spec with added ``variation`` key.
    """
    variation: dict[str, Any] = {}

    # Wall damage (0-30%)
    variation["wall_damage"] = round(rng.uniform(0.0, 0.3), 2)

    # Roof condition
    roof_roll = rng.random()
    if roof_roll < 0.5:
        variation["roof_condition"] = "intact"
    elif roof_roll < 0.8:
        variation["roof_condition"] = "damaged"
    else:
        variation["roof_condition"] = "missing"

    # Window count
    variation["window_count"] = rng.randint(0, 4)

    # Door condition
    door_roll = rng.random()
    if door_roll < 0.6:
        variation["door_condition"] = "intact"
    elif door_roll < 0.85:
        variation["door_condition"] = "broken"
    else:
        variation["door_condition"] = "missing"

    # Small detail props on the building
    detail_candidates = [
        "hanging_sign", "flower_box", "skull_mount",
        "lantern_hook", "ivy_patch", "cobweb", "moss_patch",
    ]
    num_details = rng.randint(0, 3)
    variation["prop_additions"] = rng.sample(
        detail_candidates, min(num_details, len(detail_candidates))
    )

    result = dict(building)
    result["variation"] = variation
    return result


# ---------------------------------------------------------------------------
# Perimeter walls / gates
# ---------------------------------------------------------------------------

def _generate_perimeter(
    rng: random.Random,
    config: dict[str, Any],
    center: tuple[float, float],
    radius: float,
) -> list[dict[str, Any]]:
    """Generate perimeter wall segments and gates.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG.
    config : dict
        Settlement config.
    center : tuple
        Settlement center.
    radius : float
        Settlement radius.

    Returns
    -------
    list of dict
        Perimeter element specs (wall_segment, gate, tower, etc.).
    """
    if not config.get("has_walls", False):
        return []

    perimeter_types = config.get("perimeter_props", ["wall_segment", "gate"])
    elements: list[dict[str, Any]] = []

    # Wall segments around the circumference
    wall_radius = radius * 0.9
    segment_length = 6.0
    circumference = 2 * math.pi * wall_radius
    num_segments = max(4, int(circumference / segment_length))

    # Decide gate positions (1-2 gates)
    num_gates = rng.randint(1, 2)
    gate_indices: set[int] = set()
    gate_angle_step = num_segments / max(num_gates, 1)
    for g in range(num_gates):
        gate_indices.add(int(g * gate_angle_step) % num_segments)

    gate_types = [t for t in perimeter_types if "gate" in t]
    gate_type = gate_types[0] if gate_types else "gate"
    wall_types = [t for t in perimeter_types if "wall" in t]
    wall_type = wall_types[0] if wall_types else "wall_segment"
    tower_types = [t for t in perimeter_types if "tower" in t]
    tower_type = tower_types[0] if tower_types else None

    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        px = center[0] + math.cos(angle) * wall_radius
        py = center[1] + math.sin(angle) * wall_radius
        facing = angle + math.pi  # face inward

        if i in gate_indices:
            elements.append({
                "type": gate_type,
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_gate": True,
            })
        else:
            elements.append({
                "type": wall_type,
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_gate": False,
            })

        # Add towers at corners (every quarter)
        if tower_type and i % max(1, num_segments // 4) == 0 and i not in gate_indices:
            elements.append({
                "type": tower_type,
                "position": (round(px, 2), round(py, 2)),
                "rotation": round(facing, 4),
                "is_tower": True,
            })

    return elements


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_settlement(
    settlement_type: str,
    seed: int | None = None,
    center: tuple[float, float] = (0.0, 0.0),
    radius: float = 50.0,
) -> dict[str, Any]:
    """Generate a complete settlement layout.

    Composes building placement, road network, prop scattering,
    perimeter walls, interior furnishing, and per-building variation
    into a single data structure.

    Parameters
    ----------
    settlement_type : str
        One of: village, town, bandit_camp, castle, outpost.
    seed : int or None
        Random seed for deterministic generation.  None uses system
        randomness.
    center : tuple
        World-space (x, y) center of the settlement.
    radius : float
        Approximate radius of the settlement area.

    Returns
    -------
    dict with:
        - settlement_type: str
        - seed: int
        - center: tuple
        - radius: float
        - buildings: list of placed building specs with variation
        - roads: list of road segments
        - props: list of decoration placements
        - perimeter: list of wall/gate elements
        - interiors: dict mapping building index to furniture list
        - metadata: summary statistics

    Raises
    ------
    ValueError
        If ``settlement_type`` is not recognized.
    """
    if settlement_type not in SETTLEMENT_TYPES:
        raise ValueError(
            f"Unknown settlement type '{settlement_type}'. "
            f"Valid types: {sorted(SETTLEMENT_TYPES.keys())}"
        )

    config = SETTLEMENT_TYPES[settlement_type]

    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)

    # 1. Place buildings
    buildings = _place_buildings(rng, config, center, radius)

    # 2. Apply per-building variation
    varied_buildings: list[dict[str, Any]] = []
    for bld in buildings:
        variation_rng = random.Random(bld["unique_seed"])
        varied_buildings.append(
            _apply_building_variation(variation_rng, bld)
        )

    # 3. Generate roads
    roads = _generate_roads(varied_buildings, center, config["road_style"])

    # 4. Scatter props
    props = _scatter_settlement_props(
        rng, varied_buildings, roads, config, radius, center
    )

    # 5. Perimeter walls
    perimeter = _generate_perimeter(rng, config, center, radius)

    # 6. Furnish interiors
    interiors: dict[int, list[dict[str, Any]]] = {}
    for idx, bld in enumerate(varied_buildings):
        rooms = bld.get("room_functions", [])
        if not rooms:
            continue
        bx, by = bld["position"]
        fp = bld.get("footprint", (6.0, 6.0))
        # Divide building footprint into rooms (stacked vertically)
        room_height = fp[1] / max(len(rooms), 1)
        room_furnishings: list[dict[str, Any]] = []
        for ri, room_type in enumerate(rooms):
            room_bounds = {
                "min": (bx - fp[0] / 2, by - fp[1] / 2 + ri * room_height),
                "max": (bx + fp[0] / 2, by - fp[1] / 2 + (ri + 1) * room_height),
            }
            room_rng = random.Random(bld["unique_seed"] + ri)
            furnishings = _furnish_interior(room_rng, room_type, room_bounds)
            room_furnishings.extend(furnishings)
        if room_furnishings:
            interiors[idx] = room_furnishings

    # 7. Metadata
    metadata = {
        "building_count": len(varied_buildings),
        "road_count": len(roads),
        "prop_count": len(props),
        "perimeter_element_count": len(perimeter),
        "furnished_building_count": len(interiors),
        "total_furniture_pieces": sum(
            len(v) for v in interiors.values()
        ),
        "has_walls": config["has_walls"],
        "layout_pattern": config.get("layout_pattern", "organic"),
    }

    return {
        "settlement_type": settlement_type,
        "seed": seed,
        "center": center,
        "radius": radius,
        "buildings": varied_buildings,
        "roads": roads,
        "props": props,
        "perimeter": perimeter,
        "interiors": interiors,
        "metadata": metadata,
    }
