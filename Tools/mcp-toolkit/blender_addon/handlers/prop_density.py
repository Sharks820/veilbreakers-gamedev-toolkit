"""Pure-logic prop density scatter system for AAA-quality interior/exterior
detail placement.

NO bpy/bmesh imports. Fully testable without Blender.

Fills rooms and outdoor areas with small detail props at AAA density
(50-200 props per room), using surface-zone classification (floor, table,
wall, shelf, ceiling) and Poisson-disk distribution for natural spacing.

Provides:
  - ROOM_DENSITY_RULES: per-room-type density configurations for 12 room types
  - compute_detail_prop_placements: main placement engine
  - _sample_surface_zone: zone-aware Poisson sampling within bounds
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Room Density Rules -- 12 room types
# ---------------------------------------------------------------------------

ROOM_DENSITY_RULES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "tavern": {
        "floor": [
            {"type": "straw", "density": 0.3, "scale": (0.1, 0.3)},
            {"type": "food_scraps", "density": 0.1, "scale": (0.05, 0.1)},
            {"type": "spilled_drink", "density": 0.05, "scale": (0.1, 0.2)},
            {"type": "dirt_patch", "density": 0.08, "scale": (0.15, 0.3)},
        ],
        "table_surface": [
            {"type": "mug", "density": 0.8, "scale": (0.08, 0.12)},
            {"type": "plate", "density": 0.6, "scale": (0.1, 0.15)},
            {"type": "candle", "density": 0.4, "scale": (0.05, 0.08)},
            {"type": "food_item", "density": 0.3, "scale": (0.05, 0.1)},
            {"type": "coin_pile", "density": 0.1, "scale": (0.03, 0.05)},
        ],
        "walls": [
            {"type": "cobweb_corner", "density": 0.2, "position": "corner_top", "scale": (0.2, 0.4)},
            {"type": "mounted_trophy", "density": 0.1, "position": "wall_center", "scale": (0.3, 0.5)},
            {"type": "torch_sconce", "density": 0.15, "position": "wall_center", "scale": (0.1, 0.15)},
        ],
        "shelves": [
            {"type": "bottle", "density": 0.7, "scale": (0.05, 0.1)},
            {"type": "mug", "density": 0.3, "scale": (0.08, 0.12)},
            {"type": "bowl", "density": 0.2, "scale": (0.08, 0.12)},
        ],
    },
    "dungeon_corridor": {
        "floor": [
            {"type": "rubble_small", "density": 0.15, "scale": (0.05, 0.15)},
            {"type": "bone_scatter", "density": 0.05, "scale": (0.05, 0.12)},
            {"type": "puddle", "density": 0.08, "scale": (0.2, 0.5)},
            {"type": "chain_pile", "density": 0.03, "scale": (0.1, 0.2)},
        ],
        "walls": [
            {"type": "cobweb", "density": 0.3, "position": "corner", "scale": (0.2, 0.5)},
            {"type": "crack_decal", "density": 0.2, "position": "wall_center", "scale": (0.3, 0.8)},
            {"type": "moss_patch", "density": 0.15, "position": "wall_lower", "scale": (0.2, 0.4)},
        ],
        "ceiling": [
            {"type": "stalactite_small", "density": 0.1, "scale": (0.05, 0.15)},
            {"type": "cobweb_hanging", "density": 0.2, "scale": (0.3, 0.6)},
        ],
    },
    "bedroom": {
        "floor": [
            {"type": "rug_fragment", "density": 0.15, "scale": (0.3, 0.6)},
            {"type": "dust_pile", "density": 0.1, "scale": (0.1, 0.2)},
            {"type": "shoe", "density": 0.05, "scale": (0.1, 0.15)},
        ],
        "table_surface": [
            {"type": "candle", "density": 0.7, "scale": (0.05, 0.08)},
            {"type": "book", "density": 0.5, "scale": (0.1, 0.15)},
            {"type": "quill_ink", "density": 0.3, "scale": (0.05, 0.1)},
            {"type": "potion_bottle", "density": 0.2, "scale": (0.05, 0.08)},
        ],
        "walls": [
            {"type": "cobweb_corner", "density": 0.15, "position": "corner_top", "scale": (0.2, 0.4)},
            {"type": "tapestry_torn", "density": 0.1, "position": "wall_center", "scale": (0.5, 1.0)},
        ],
    },
    "throne_room": {
        "floor": [
            {"type": "carpet_edge", "density": 0.1, "scale": (0.3, 0.5)},
            {"type": "gold_coin", "density": 0.05, "scale": (0.02, 0.03)},
            {"type": "petal_scatter", "density": 0.08, "scale": (0.02, 0.05)},
        ],
        "walls": [
            {"type": "banner", "density": 0.2, "position": "wall_upper", "scale": (0.5, 1.0)},
            {"type": "torch_sconce", "density": 0.25, "position": "wall_center", "scale": (0.1, 0.15)},
            {"type": "shield_mount", "density": 0.1, "position": "wall_center", "scale": (0.3, 0.5)},
        ],
        "ceiling": [
            {"type": "chandelier_chain", "density": 0.05, "scale": (0.3, 0.5)},
            {"type": "cobweb_corner", "density": 0.1, "scale": (0.3, 0.5)},
        ],
    },
    "chapel": {
        "floor": [
            {"type": "candle_wax_drip", "density": 0.12, "scale": (0.05, 0.1)},
            {"type": "incense_residue", "density": 0.08, "scale": (0.1, 0.15)},
            {"type": "stone_chip", "density": 0.06, "scale": (0.03, 0.08)},
        ],
        "table_surface": [
            {"type": "candle_cluster", "density": 0.8, "scale": (0.1, 0.2)},
            {"type": "holy_book", "density": 0.5, "scale": (0.15, 0.2)},
            {"type": "offering_bowl", "density": 0.3, "scale": (0.08, 0.12)},
        ],
        "walls": [
            {"type": "stained_glass_shard", "density": 0.08, "position": "wall_upper", "scale": (0.1, 0.2)},
            {"type": "icon_plaque", "density": 0.15, "position": "wall_center", "scale": (0.2, 0.3)},
        ],
    },
    "library": {
        "floor": [
            {"type": "loose_page", "density": 0.15, "scale": (0.1, 0.15)},
            {"type": "book_fallen", "density": 0.08, "scale": (0.1, 0.15)},
            {"type": "dust_pile", "density": 0.1, "scale": (0.1, 0.2)},
        ],
        "table_surface": [
            {"type": "book_open", "density": 0.7, "scale": (0.15, 0.2)},
            {"type": "scroll_rolled", "density": 0.4, "scale": (0.1, 0.2)},
            {"type": "candle", "density": 0.5, "scale": (0.05, 0.08)},
            {"type": "ink_bottle", "density": 0.3, "scale": (0.04, 0.06)},
            {"type": "quill", "density": 0.3, "scale": (0.05, 0.08)},
        ],
        "shelves": [
            {"type": "book_row", "density": 0.9, "scale": (0.1, 0.15)},
            {"type": "scroll_tube", "density": 0.2, "scale": (0.05, 0.1)},
            {"type": "candle_holder", "density": 0.15, "scale": (0.05, 0.08)},
        ],
        "walls": [
            {"type": "cobweb_corner", "density": 0.2, "position": "corner_top", "scale": (0.2, 0.4)},
        ],
    },
    "kitchen": {
        "floor": [
            {"type": "spilled_grain", "density": 0.12, "scale": (0.1, 0.2)},
            {"type": "food_scraps", "density": 0.15, "scale": (0.05, 0.1)},
            {"type": "grease_stain", "density": 0.08, "scale": (0.15, 0.3)},
        ],
        "table_surface": [
            {"type": "cutting_board", "density": 0.6, "scale": (0.15, 0.2)},
            {"type": "knife", "density": 0.5, "scale": (0.1, 0.15)},
            {"type": "vegetable", "density": 0.4, "scale": (0.05, 0.1)},
            {"type": "bowl", "density": 0.5, "scale": (0.08, 0.12)},
            {"type": "ladle", "density": 0.2, "scale": (0.08, 0.12)},
        ],
        "shelves": [
            {"type": "pot", "density": 0.6, "scale": (0.1, 0.2)},
            {"type": "jar", "density": 0.5, "scale": (0.08, 0.12)},
            {"type": "herb_bundle", "density": 0.3, "scale": (0.05, 0.1)},
        ],
        "walls": [
            {"type": "hanging_pan", "density": 0.2, "position": "wall_center", "scale": (0.15, 0.2)},
            {"type": "soot_stain", "density": 0.15, "position": "wall_lower", "scale": (0.3, 0.5)},
        ],
    },
    "armory": {
        "floor": [
            {"type": "iron_filings", "density": 0.1, "scale": (0.05, 0.1)},
            {"type": "leather_scrap", "density": 0.08, "scale": (0.05, 0.1)},
            {"type": "broken_link", "density": 0.05, "scale": (0.02, 0.04)},
        ],
        "table_surface": [
            {"type": "whetstone", "density": 0.5, "scale": (0.08, 0.12)},
            {"type": "oil_rag", "density": 0.4, "scale": (0.08, 0.12)},
            {"type": "arrowhead_pile", "density": 0.3, "scale": (0.05, 0.08)},
        ],
        "walls": [
            {"type": "weapon_rack", "density": 0.3, "position": "wall_center", "scale": (0.5, 0.8)},
            {"type": "shield_mount", "density": 0.2, "position": "wall_center", "scale": (0.3, 0.5)},
            {"type": "armor_stand", "density": 0.15, "position": "wall_center", "scale": (0.4, 0.6)},
        ],
        "shelves": [
            {"type": "helmet", "density": 0.4, "scale": (0.15, 0.2)},
            {"type": "gauntlet", "density": 0.3, "scale": (0.1, 0.15)},
            {"type": "chain_coil", "density": 0.2, "scale": (0.1, 0.15)},
        ],
    },
    "prison_cell": {
        "floor": [
            {"type": "straw_pile", "density": 0.25, "scale": (0.2, 0.4)},
            {"type": "rat_droppings", "density": 0.1, "scale": (0.02, 0.05)},
            {"type": "bone_fragment", "density": 0.08, "scale": (0.05, 0.1)},
            {"type": "puddle", "density": 0.06, "scale": (0.15, 0.3)},
        ],
        "walls": [
            {"type": "scratch_marks", "density": 0.25, "position": "wall_lower", "scale": (0.1, 0.3)},
            {"type": "chain_mount", "density": 0.15, "position": "wall_center", "scale": (0.1, 0.2)},
            {"type": "moss_patch", "density": 0.2, "position": "wall_lower", "scale": (0.2, 0.4)},
        ],
    },
    "alchemy_lab": {
        "floor": [
            {"type": "glass_shard", "density": 0.1, "scale": (0.03, 0.08)},
            {"type": "powder_spill", "density": 0.08, "scale": (0.1, 0.2)},
            {"type": "stain_chemical", "density": 0.06, "scale": (0.1, 0.25)},
        ],
        "table_surface": [
            {"type": "flask", "density": 0.7, "scale": (0.05, 0.1)},
            {"type": "mortar_pestle", "density": 0.4, "scale": (0.08, 0.12)},
            {"type": "herb_bundle", "density": 0.5, "scale": (0.05, 0.1)},
            {"type": "alembic", "density": 0.3, "scale": (0.1, 0.15)},
            {"type": "candle", "density": 0.4, "scale": (0.05, 0.08)},
            {"type": "scroll_recipe", "density": 0.3, "scale": (0.08, 0.12)},
        ],
        "shelves": [
            {"type": "potion_bottle", "density": 0.8, "scale": (0.05, 0.08)},
            {"type": "ingredient_jar", "density": 0.6, "scale": (0.06, 0.1)},
            {"type": "skull_small", "density": 0.1, "scale": (0.08, 0.12)},
        ],
        "walls": [
            {"type": "chart_pinned", "density": 0.15, "position": "wall_center", "scale": (0.2, 0.3)},
        ],
    },
    "crypt": {
        "floor": [
            {"type": "bone_scatter", "density": 0.12, "scale": (0.05, 0.15)},
            {"type": "rubble_small", "density": 0.1, "scale": (0.05, 0.15)},
            {"type": "cobweb_ground", "density": 0.08, "scale": (0.2, 0.4)},
            {"type": "candle_melted", "density": 0.06, "scale": (0.03, 0.06)},
        ],
        "walls": [
            {"type": "cobweb", "density": 0.35, "position": "corner", "scale": (0.3, 0.6)},
            {"type": "moss_patch", "density": 0.2, "position": "wall_lower", "scale": (0.2, 0.4)},
            {"type": "crack_decal", "density": 0.15, "position": "wall_center", "scale": (0.3, 0.6)},
        ],
        "ceiling": [
            {"type": "cobweb_hanging", "density": 0.3, "scale": (0.3, 0.6)},
            {"type": "root_tendril", "density": 0.1, "scale": (0.1, 0.3)},
        ],
    },
    "forge": {
        "floor": [
            {"type": "coal_scatter", "density": 0.2, "scale": (0.03, 0.08)},
            {"type": "iron_filings", "density": 0.15, "scale": (0.05, 0.1)},
            {"type": "ash_pile", "density": 0.1, "scale": (0.1, 0.2)},
            {"type": "water_puddle", "density": 0.05, "scale": (0.15, 0.25)},
        ],
        "table_surface": [
            {"type": "tongs", "density": 0.6, "scale": (0.12, 0.18)},
            {"type": "hammer", "density": 0.5, "scale": (0.1, 0.15)},
            {"type": "metal_ingot", "density": 0.4, "scale": (0.05, 0.1)},
            {"type": "mold", "density": 0.2, "scale": (0.1, 0.15)},
        ],
        "walls": [
            {"type": "tool_rack", "density": 0.25, "position": "wall_center", "scale": (0.4, 0.6)},
            {"type": "soot_stain", "density": 0.3, "position": "wall_lower", "scale": (0.3, 0.5)},
        ],
    },
}


# ---------------------------------------------------------------------------
# Surface zone definitions (Z-height ranges for placement)
# ---------------------------------------------------------------------------

SURFACE_ZONES: dict[str, dict[str, Any]] = {
    "floor": {"z_range": (0.0, 0.05), "normal": (0, 0, 1)},
    "table_surface": {"z_range": (0.7, 0.9), "normal": (0, 0, 1)},
    "shelves": {"z_range": (1.0, 2.0), "normal": (0, 0, 1)},
    "walls": {"z_range": (0.3, 2.5), "normal": "perpendicular"},
    "ceiling": {"z_range": (2.5, 3.0), "normal": (0, 0, -1)},
}


# ---------------------------------------------------------------------------
# Placement Engine
# ---------------------------------------------------------------------------

def _poisson_disk_2d(
    width: float,
    depth: float,
    min_distance: float,
    rng: random.Random,
    max_attempts: int = 30,
) -> list[tuple[float, float]]:
    """Bridson's Poisson disk sampling for a rectangular area.

    Lighter-weight version embedded here to avoid coupling to the
    scatter_engine module (which serves a different purpose).
    """
    cell_size = min_distance / math.sqrt(2)
    grid_w = max(1, int(math.ceil(width / cell_size)))
    grid_h = max(1, int(math.ceil(depth / cell_size)))

    grid: list[int] = [-1] * (grid_w * grid_h)
    points: list[tuple[float, float]] = []
    active: list[int] = []

    def _grid_idx(x: float, y: float) -> int:
        gx = max(0, min(int(x / cell_size), grid_w - 1))
        gy = max(0, min(int(y / cell_size), grid_h - 1))
        return gy * grid_w + gx

    def _is_valid(x: float, y: float) -> bool:
        if x < 0 or x >= width or y < 0 or y >= depth:
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

    x0 = rng.uniform(0, max(width, 0.001))
    y0 = rng.uniform(0, max(depth, 0.001))
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
            active[active_idx] = active[-1]
            active.pop()

    return points


def _collides_with_furniture(
    x: float, y: float,
    furniture: list[dict[str, Any]],
    clearance: float = 0.15,
) -> bool:
    """Check if a position overlaps any furniture bounding box + clearance."""
    for furn in furniture:
        fp = furn.get("position", (0, 0, 0))
        fs = furn.get("size", (1, 1, 1))
        half_x = fs[0] / 2.0 + clearance
        half_y = fs[1] / 2.0 + clearance
        if (fp[0] - half_x <= x <= fp[0] + half_x
                and fp[1] - half_y <= y <= fp[1] + half_y):
            return True
    return False


def _compute_zone_z(
    zone: str,
    rng: random.Random,
) -> float:
    """Return a Z coordinate appropriate for the given surface zone."""
    zone_info = SURFACE_ZONES.get(zone, SURFACE_ZONES["floor"])
    z_min, z_max = zone_info["z_range"]
    return rng.uniform(z_min, z_max)


def compute_detail_prop_placements(
    room_bounds: tuple,
    room_type: str,
    furniture_positions: list[dict[str, Any]] | None = None,
    seed: int = 42,
    density_multiplier: float = 1.0,
) -> list[dict[str, Any]]:
    """Compute placement positions for small detail props.

    Parameters
    ----------
    room_bounds : tuple
        ((min_x, min_y, min_z), (max_x, max_y, max_z)) defining the room.
    room_type : str
        Key into ROOM_DENSITY_RULES (e.g. "tavern", "dungeon_corridor").
    furniture_positions : list of dict, optional
        Existing furniture to avoid. Each dict has "position" (x,y,z) and
        "size" (w,d,h).
    seed : int
        Random seed for deterministic generation.
    density_multiplier : float
        Scale factor for prop density (1.0 = default, 2.0 = double, etc.).

    Returns
    -------
    list of dict
        Each dict has: "type" (str), "position" (x, y, z), "rotation" (float
        in degrees), "scale" (float), "zone" (str).
    """
    if furniture_positions is None:
        furniture_positions = []

    rules = ROOM_DENSITY_RULES.get(room_type)
    if rules is None:
        raise ValueError(
            f"Unknown room type '{room_type}'. "
            f"Valid types: {sorted(ROOM_DENSITY_RULES.keys())}"
        )

    rng = random.Random(seed)
    (min_x, min_y, min_z), (max_x, max_y, max_z) = room_bounds
    room_width = max(max_x - min_x, 0.1)
    room_depth = max(max_y - min_y, 0.1)
    room_area = room_width * room_depth

    placements: list[dict[str, Any]] = []

    for zone_name, prop_list in rules.items():
        for prop_rule in prop_list:
            prop_type = prop_rule["type"]
            density = prop_rule["density"] * density_multiplier
            scale_range = prop_rule.get("scale", (0.1, 0.2))
            wall_position = prop_rule.get("position", None)

            # Compute target count from density and room area
            # density is probability per square meter, scaled
            target_count = max(1, int(density * room_area + 0.5))

            # Compute min_distance for Poisson sampling based on target count
            # area / count = area per point; sqrt gives spacing
            area_per_point = room_area / max(target_count, 1)
            min_dist = max(0.05, math.sqrt(area_per_point) * 0.6)

            if zone_name in ("walls", "ceiling"):
                # Wall/ceiling props: distribute along perimeter or ceiling grid
                wall_props = _place_wall_props(
                    min_x, min_y, max_x, max_y,
                    zone_name, prop_type, target_count,
                    scale_range, wall_position, rng,
                )
                placements.extend(wall_props)
            else:
                # Floor / table / shelf zones: 2D Poisson scatter
                candidates = _poisson_disk_2d(
                    room_width, room_depth, min_dist, rng,
                )

                placed = 0
                for cx, cy in candidates:
                    if placed >= target_count:
                        break

                    world_x = cx + min_x
                    world_y = cy + min_y

                    if _collides_with_furniture(world_x, world_y,
                                                furniture_positions):
                        continue

                    z = _compute_zone_z(zone_name, rng)
                    scale = rng.uniform(scale_range[0], scale_range[1])
                    rotation = rng.uniform(0, 360)

                    placements.append({
                        "type": prop_type,
                        "position": (world_x, world_y, z),
                        "rotation": rotation,
                        "scale": scale,
                        "zone": zone_name,
                    })
                    placed += 1

    return placements


def _place_wall_props(
    min_x: float, min_y: float,
    max_x: float, max_y: float,
    zone_name: str,
    prop_type: str,
    target_count: int,
    scale_range: tuple,
    wall_position: str | None,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Place props along walls or on ceiling surfaces."""
    results: list[dict[str, Any]] = []

    if zone_name == "ceiling":
        # Scatter on ceiling grid
        room_w = max_x - min_x
        room_d = max_y - min_y
        z = SURFACE_ZONES["ceiling"]["z_range"][0]
        for _ in range(target_count):
            x = rng.uniform(min_x, max_x)
            y = rng.uniform(min_y, max_y)
            scale = rng.uniform(scale_range[0], scale_range[1])
            results.append({
                "type": prop_type,
                "position": (x, y, z + rng.uniform(0, 0.3)),
                "rotation": rng.uniform(0, 360),
                "scale": scale,
                "zone": zone_name,
            })
        return results

    # Wall placement: distribute along 4 walls
    walls = [
        # (start_x, start_y, end_x, end_y, face_normal)
        (min_x, min_y, max_x, min_y, (0, 1, 0)),   # south wall
        (max_x, min_y, max_x, max_y, (-1, 0, 0)),   # east wall
        (min_x, max_y, max_x, max_y, (0, -1, 0)),   # north wall
        (min_x, min_y, min_x, max_y, (1, 0, 0)),    # west wall
    ]

    per_wall = max(1, target_count // len(walls))
    remainder = target_count - per_wall * len(walls)

    for wall_idx, (sx, sy, ex, ey, normal) in enumerate(walls):
        count = per_wall + (1 if wall_idx < remainder else 0)
        wall_len = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
        if wall_len < 0.01:
            continue

        for _ in range(count):
            t = rng.uniform(0.05, 0.95)
            x = sx + t * (ex - sx)
            y = sy + t * (ey - sy)

            # Z position depends on wall_position hint
            if wall_position == "corner_top":
                z = rng.uniform(2.0, 2.8)
            elif wall_position == "wall_upper":
                z = rng.uniform(1.8, 2.5)
            elif wall_position == "wall_lower":
                z = rng.uniform(0.1, 0.8)
            else:  # wall_center or default
                z = rng.uniform(1.0, 2.0)

            scale = rng.uniform(scale_range[0], scale_range[1])

            # Rotation faces outward from wall
            face_angle = math.degrees(math.atan2(normal[1], normal[0]))

            results.append({
                "type": prop_type,
                "position": (x, y, z),
                "rotation": face_angle + rng.uniform(-10, 10),
                "scale": scale,
                "zone": zone_name,
            })

    return results


def get_available_room_types() -> list[str]:
    """Return sorted list of all supported room types."""
    return sorted(ROOM_DENSITY_RULES.keys())


def get_zone_types(room_type: str) -> list[str]:
    """Return the surface zones defined for a given room type."""
    rules = ROOM_DENSITY_RULES.get(room_type, {})
    return list(rules.keys())
