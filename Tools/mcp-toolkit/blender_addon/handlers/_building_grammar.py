"""Pure-logic building grammar rules, style configs, and generation templates.

NO bpy or bmesh imports -- fully testable without Blender.

Provides:
- STYLE_CONFIGS: 5 architectural style presets
- BuildingSpec: dataclass for geometry operation lists
- evaluate_building_grammar(): grammar-rule building generation
- generate_castle_spec/tower_spec/bridge_spec/fortress_spec(): specialized templates
- apply_ruins_damage(): damage existing building specs
- generate_interior_layout(): furniture placement for room types
- MODULAR_CATALOG + generate_modular_pieces(): snap-together architecture kit
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Style Configurations
# ---------------------------------------------------------------------------

STYLE_CONFIGS: dict[str, dict] = {
    "medieval": {
        "foundation": {"height": 0.3, "inset": 0.05, "material": "stone_dark"},
        "walls": {"height_per_floor": 3.0, "thickness": 0.3, "material": "plaster_white"},
        "floor_slab": {"thickness": 0.2, "material": "wood_planks"},
        "roof": {"type": "gabled", "overhang": 0.4, "pitch": 35, "material": "thatch"},
        "windows": {"style": "arched", "width": 0.8, "height": 1.2, "per_wall": 2},
        "door": {"style": "wooden_arched", "width": 1.2, "height": 2.2},
        "details": ["timber_frame", "window_boxes", "chimney"],
    },
    "gothic": {
        "foundation": {"height": 0.5, "inset": 0.1, "material": "stone_grey"},
        "walls": {"height_per_floor": 4.5, "thickness": 0.5, "material": "stone_carved"},
        "floor_slab": {"thickness": 0.25, "material": "stone_slab"},
        "roof": {"type": "pointed", "overhang": 0.3, "pitch": 60, "material": "slate"},
        "windows": {"style": "pointed_arch", "width": 0.6, "height": 2.0, "per_wall": 3},
        "door": {"style": "gothic_arch", "width": 1.5, "height": 3.0},
        "details": ["flying_buttress", "gargoyle", "rose_window", "spire"],
    },
    "rustic": {
        "foundation": {"height": 0.2, "inset": 0.0, "material": "fieldstone"},
        "walls": {"height_per_floor": 2.5, "thickness": 0.25, "material": "log"},
        "floor_slab": {"thickness": 0.15, "material": "rough_planks"},
        "roof": {"type": "gabled", "overhang": 0.6, "pitch": 30, "material": "thatch_worn"},
        "windows": {"style": "square", "width": 0.6, "height": 0.6, "per_wall": 1},
        "door": {"style": "plank", "width": 1.0, "height": 2.0},
        "details": ["woodpile"],
    },
    "fortress": {
        "foundation": {"height": 0.6, "inset": 0.15, "material": "stone_heavy"},
        "walls": {"height_per_floor": 3.5, "thickness": 0.8, "material": "stone_fortified"},
        "floor_slab": {"thickness": 0.3, "material": "stone_slab"},
        "roof": {"type": "flat", "overhang": 0.0, "pitch": 0, "material": "stone_parapet"},
        "windows": {"style": "arrow_slit", "width": 0.15, "height": 1.0, "per_wall": 3},
        "door": {"style": "iron_gate", "width": 1.5, "height": 2.5},
        "details": ["battlement", "machicolation", "murder_hole"],
    },
    "organic": {
        "foundation": {"height": 0.4, "inset": 0.0, "material": "earth_packed"},
        "walls": {"height_per_floor": 3.0, "thickness": 0.35, "material": "cob"},
        "floor_slab": {"thickness": 0.2, "material": "packed_earth"},
        "roof": {"type": "domed", "overhang": 0.2, "pitch": 0, "material": "living_thatch"},
        "windows": {"style": "round", "width": 0.5, "height": 0.5, "per_wall": 2},
        "door": {"style": "rounded", "width": 1.0, "height": 1.8},
        "details": ["vine_growth", "moss_patches", "root_buttress"],
    },
}

# ---------------------------------------------------------------------------
# BuildingSpec dataclass
# ---------------------------------------------------------------------------


@dataclass
class BuildingSpec:
    """Output of grammar evaluation -- geometry operations for the handler.

    Each operation is a dict describing a geometry primitive:
      - {"type": "box", "position": [x,y,z], "size": [w,h,d], "material": str, "role": str}
      - {"type": "cylinder", "position": [x,y,z], "radius": float, "height": float,
         "segments": int, "material": str, "role": str}
      - {"type": "opening", "wall_index": int, "position": [x,y], "size": [w,h], "role": str}
    """

    footprint: tuple[float, float]
    floors: int
    style: str
    operations: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Grammar Evaluation
# ---------------------------------------------------------------------------


def evaluate_building_grammar(
    width: float,
    depth: float,
    floors: int,
    style: str,
    seed: int = 0,
) -> BuildingSpec:
    """Evaluate grammar rules to produce a building spec.

    Layer ordering: foundation -> walls (per floor) -> floor slabs -> roof
    -> window openings -> door opening -> detail operations.
    """
    rng = random.Random(seed)
    config = STYLE_CONFIGS[style]

    ops: list[dict] = []

    # 1. Foundation
    fnd = config["foundation"]
    ops.append({
        "type": "box",
        "position": [-fnd["inset"], -fnd["inset"], 0.0],
        "size": [width + 2 * fnd["inset"], depth + 2 * fnd["inset"], fnd["height"]],
        "material": fnd["material"],
        "role": "foundation",
    })

    wall_cfg = config["walls"]
    slab_cfg = config["floor_slab"]
    base_z = fnd["height"]

    # 2. Walls per floor + 3. Floor slabs between floors
    for floor_idx in range(floors):
        floor_z = base_z + floor_idx * (wall_cfg["height_per_floor"] + slab_cfg["thickness"])

        # Floor slab (between floors, not under ground floor)
        if floor_idx > 0:
            ops.append({
                "type": "box",
                "position": [0.0, 0.0, floor_z - slab_cfg["thickness"]],
                "size": [width, depth, slab_cfg["thickness"]],
                "material": slab_cfg["material"],
                "role": "floor_slab",
            })

        t = wall_cfg["thickness"]
        h = wall_cfg["height_per_floor"]
        mat = wall_cfg["material"]

        # 4 walls: front (y=0), back (y=depth-t), left (x=0), right (x=width-t)
        # Front wall
        ops.append({
            "type": "box",
            "position": [0.0, 0.0, floor_z],
            "size": [width, t, h],
            "material": mat,
            "role": "wall",
            "wall_index": 0,
            "floor": floor_idx,
        })
        # Back wall
        ops.append({
            "type": "box",
            "position": [0.0, depth - t, floor_z],
            "size": [width, t, h],
            "material": mat,
            "role": "wall",
            "wall_index": 1,
            "floor": floor_idx,
        })
        # Left wall
        ops.append({
            "type": "box",
            "position": [0.0, t, floor_z],
            "size": [t, depth - 2 * t, h],
            "material": mat,
            "role": "wall",
            "wall_index": 2,
            "floor": floor_idx,
        })
        # Right wall
        ops.append({
            "type": "box",
            "position": [width - t, t, floor_z],
            "size": [t, depth - 2 * t, h],
            "material": mat,
            "role": "wall",
            "wall_index": 3,
            "floor": floor_idx,
        })

    # 4. Roof
    roof_cfg = config["roof"]
    roof_z = base_z + floors * (wall_cfg["height_per_floor"] + slab_cfg["thickness"]) - slab_cfg["thickness"]

    if roof_cfg["type"] == "gabled":
        ridge_height = math.tan(math.radians(roof_cfg["pitch"])) * (depth / 2)
        overhang = roof_cfg["overhang"]
        ops.append({
            "type": "box",
            "position": [-overhang, -overhang, roof_z],
            "size": [width + 2 * overhang, depth + 2 * overhang, 0.1],
            "material": roof_cfg["material"],
            "role": "roof",
            "roof_type": "gabled",
            "ridge_height": ridge_height,
        })
    elif roof_cfg["type"] == "pointed":
        overhang = roof_cfg["overhang"]
        ridge_height = math.tan(math.radians(roof_cfg["pitch"])) * (depth / 2)
        ops.append({
            "type": "box",
            "position": [-overhang, -overhang, roof_z],
            "size": [width + 2 * overhang, depth + 2 * overhang, 0.1],
            "material": roof_cfg["material"],
            "role": "roof",
            "roof_type": "pointed",
            "ridge_height": ridge_height,
        })
    elif roof_cfg["type"] == "flat":
        ops.append({
            "type": "box",
            "position": [0.0, 0.0, roof_z],
            "size": [width, depth, 0.15],
            "material": roof_cfg["material"],
            "role": "roof",
            "roof_type": "flat",
        })
    elif roof_cfg["type"] == "domed":
        ops.append({
            "type": "cylinder",
            "position": [width / 2, depth / 2, roof_z],
            "radius": min(width, depth) / 2,
            "height": min(width, depth) / 3,
            "segments": 16,
            "material": roof_cfg["material"],
            "role": "roof",
            "roof_type": "domed",
        })

    # 5. Windows per wall per floor
    win_cfg = config["windows"]
    for floor_idx in range(floors):
        floor_z = base_z + floor_idx * (wall_cfg["height_per_floor"] + slab_cfg["thickness"])
        win_y = wall_cfg["height_per_floor"] * 0.4  # place windows at 40% wall height

        for wall_idx in range(4):
            wall_length = width if wall_idx < 2 else depth - 2 * wall_cfg["thickness"]
            n_windows = win_cfg["per_wall"]
            spacing = wall_length / (n_windows + 1)

            for w_i in range(n_windows):
                offset = spacing * (w_i + 1) - win_cfg["width"] / 2
                ops.append({
                    "type": "opening",
                    "wall_index": wall_idx,
                    "position": [offset, win_y],
                    "size": [win_cfg["width"], win_cfg["height"]],
                    "role": "window",
                    "floor": floor_idx,
                    "style": win_cfg["style"],
                })

    # 6. Door on front wall (ground floor)
    door_cfg = config["door"]
    door_x = (width - door_cfg["width"]) / 2
    ops.append({
        "type": "opening",
        "wall_index": 0,
        "position": [door_x, 0.0],
        "size": [door_cfg["width"], door_cfg["height"]],
        "role": "door",
        "floor": 0,
        "style": door_cfg["style"],
    })

    # 7. Detail operations from style config
    details = config["details"]
    for detail_name in details:
        # Place details at random positions along walls or roof
        detail_x = rng.uniform(0.5, width - 0.5)
        detail_y = rng.uniform(0.5, depth - 0.5)
        ops.append({
            "type": "box",
            "position": [detail_x, detail_y, roof_z],
            "size": [0.5, 0.5, 0.5],
            "material": detail_name,
            "role": "detail",
            "detail_type": detail_name,
        })

    return BuildingSpec(
        footprint=(width, depth),
        floors=floors,
        style=style,
        operations=ops,
    )


# ---------------------------------------------------------------------------
# Specialized Templates
# ---------------------------------------------------------------------------


def generate_castle_spec(
    outer_size: float = 40.0,
    keep_size: float = 12.0,
    tower_count: int = 4,
    seed: int = 0,
) -> BuildingSpec:
    """Generate a castle spec with curtain walls, corner towers, keep, gatehouse."""
    rng = random.Random(seed)
    ops: list[dict] = []
    wall_height = 8.0
    wall_thickness = 1.5
    tower_radius = 3.0
    tower_height = 12.0

    # Curtain walls (4 wall segments)
    # Front wall
    ops.append({
        "type": "box",
        "position": [0.0, 0.0, 0.0],
        "size": [outer_size, wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })
    # Back wall
    ops.append({
        "type": "box",
        "position": [0.0, outer_size - wall_thickness, 0.0],
        "size": [outer_size, wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })
    # Left wall
    ops.append({
        "type": "box",
        "position": [0.0, wall_thickness, 0.0],
        "size": [wall_thickness, outer_size - 2 * wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })
    # Right wall
    ops.append({
        "type": "box",
        "position": [outer_size - wall_thickness, wall_thickness, 0.0],
        "size": [wall_thickness, outer_size - 2 * wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })

    # Corner towers
    corners = [
        (0.0, 0.0),
        (outer_size, 0.0),
        (0.0, outer_size),
        (outer_size, outer_size),
    ]
    for i, (cx, cy) in enumerate(corners[:tower_count]):
        ops.append({
            "type": "cylinder",
            "position": [cx, cy, 0.0],
            "radius": tower_radius,
            "height": tower_height,
            "segments": 16,
            "material": "stone_fortified",
            "role": "tower",
        })
        # Battlements on top
        ops.append({
            "type": "box",
            "position": [cx - tower_radius, cy - tower_radius, tower_height],
            "size": [tower_radius * 2, tower_radius * 2, 1.0],
            "material": "stone_parapet",
            "role": "battlement",
        })

    # Keep (central building)
    keep_x = (outer_size - keep_size) / 2
    keep_y = (outer_size - keep_size) / 2
    keep_spec = evaluate_building_grammar(
        width=keep_size, depth=keep_size, floors=3, style="fortress", seed=seed
    )
    for op in keep_spec.operations:
        # Offset keep position to center of castle
        op_copy = dict(op)
        if "position" in op_copy and len(op_copy["position"]) >= 2:
            pos = list(op_copy["position"])
            pos[0] += keep_x
            pos[1] += keep_y
            op_copy["position"] = pos
        op_copy["role"] = "keep"
        ops.append(op_copy)

    # Gatehouse (front opening with portcullis)
    gate_x = (outer_size - 4.0) / 2
    ops.append({
        "type": "box",
        "position": [gate_x, -1.0, 0.0],
        "size": [4.0, wall_thickness + 2.0, wall_height + 2.0],
        "material": "stone_fortified",
        "role": "gatehouse",
    })
    ops.append({
        "type": "opening",
        "wall_index": 0,
        "position": [gate_x + 0.5, 0.0],
        "size": [3.0, wall_height - 1.0],
        "role": "gatehouse",
    })

    return BuildingSpec(
        footprint=(outer_size, outer_size),
        floors=3,
        style="fortress",
        operations=ops,
    )


def generate_tower_spec(
    radius: float = 3.0,
    height: float = 15.0,
    floors: int = 3,
    seed: int = 0,
) -> BuildingSpec:
    """Generate a standalone tower spec with cylindrical body and battlements."""
    rng = random.Random(seed)
    ops: list[dict] = []

    # Foundation
    ops.append({
        "type": "cylinder",
        "position": [0.0, 0.0, 0.0],
        "radius": radius + 0.2,
        "height": 0.4,
        "segments": 16,
        "material": "stone_dark",
        "role": "foundation",
    })

    # Main cylindrical body
    ops.append({
        "type": "cylinder",
        "position": [0.0, 0.0, 0.4],
        "radius": radius,
        "height": height,
        "segments": 16,
        "material": "stone_fortified",
        "role": "tower_body",
    })

    # Floor slabs (internal)
    floor_height = height / floors
    for i in range(1, floors):
        ops.append({
            "type": "cylinder",
            "position": [0.0, 0.0, 0.4 + i * floor_height],
            "radius": radius - 0.1,
            "height": 0.2,
            "segments": 16,
            "material": "stone_slab",
            "role": "floor_slab",
        })

    # Spiral staircase placeholder (thin cylinder offset from center)
    ops.append({
        "type": "cylinder",
        "position": [radius * 0.5, 0.0, 0.4],
        "radius": 0.5,
        "height": height,
        "segments": 8,
        "material": "stone_steps",
        "role": "stairs",
    })

    # Battlement ring at top
    top_z = 0.4 + height
    n_merlons = 8
    for i in range(n_merlons):
        angle = (2 * math.pi * i) / n_merlons
        mx = math.cos(angle) * (radius - 0.3)
        my = math.sin(angle) * (radius - 0.3)
        ops.append({
            "type": "box",
            "position": [mx - 0.3, my - 0.3, top_z],
            "size": [0.6, 0.6, 0.8],
            "material": "stone_parapet",
            "role": "battlement",
        })

    # Windows (arrow slits on each floor)
    for floor_idx in range(floors):
        floor_z = 0.4 + floor_idx * floor_height + floor_height * 0.5
        n_slits = rng.randint(2, 4)
        for s in range(n_slits):
            angle = rng.uniform(0, 2 * math.pi)
            ops.append({
                "type": "opening",
                "wall_index": 0,
                "position": [angle, floor_z],
                "size": [0.15, 1.0],
                "role": "window",
                "floor": floor_idx,
            })

    return BuildingSpec(
        footprint=(radius * 2, radius * 2),
        floors=floors,
        style="fortress",
        operations=ops,
    )


def generate_bridge_spec(
    span: float = 20.0,
    width: float = 5.0,
    arch_count: int = 3,
    seed: int = 0,
) -> BuildingSpec:
    """Generate a bridge spec with arches, road deck, and railings."""
    rng = random.Random(seed)
    ops: list[dict] = []

    arch_span = span / arch_count
    arch_radius = arch_span / 2
    deck_height = arch_radius + 0.5  # deck sits above arches

    # Abutments (end supports)
    abutment_depth = 2.0
    ops.append({
        "type": "box",
        "position": [0.0, 0.0, 0.0],
        "size": [width, abutment_depth, deck_height],
        "material": "stone_heavy",
        "role": "abutment",
    })
    ops.append({
        "type": "box",
        "position": [0.0, span - abutment_depth, 0.0],
        "size": [width, abutment_depth, deck_height],
        "material": "stone_heavy",
        "role": "abutment",
    })

    # Arches (semicircular -- approximated as series of boxes)
    for i in range(arch_count):
        arch_center_y = abutment_depth + arch_span * i + arch_radius
        n_segments = 8
        for s in range(n_segments):
            angle_start = math.pi * s / n_segments
            angle_end = math.pi * (s + 1) / n_segments
            ay1 = arch_center_y + math.cos(angle_start) * arch_radius
            az1 = math.sin(angle_start) * arch_radius
            ay2 = arch_center_y + math.cos(angle_end) * arch_radius
            az2 = math.sin(angle_end) * arch_radius
            seg_y = min(ay1, ay2)
            seg_z = min(az1, az2)
            seg_h = abs(az2 - az1) + 0.3
            seg_d = abs(ay2 - ay1) + 0.3
            ops.append({
                "type": "box",
                "position": [0.0, seg_y, seg_z],
                "size": [width, seg_d, seg_h],
                "material": "stone_arch",
                "role": "arch",
            })

    # Piers between arches
    for i in range(1, arch_count):
        pier_y = abutment_depth + arch_span * i - 0.5
        ops.append({
            "type": "box",
            "position": [0.5, pier_y, 0.0],
            "size": [width - 1.0, 1.0, deck_height],
            "material": "stone_heavy",
            "role": "pier",
        })

    # Road deck
    ops.append({
        "type": "box",
        "position": [0.0, 0.0, deck_height],
        "size": [width, span, 0.3],
        "material": "stone_road",
        "role": "road_deck",
    })

    # Railings
    railing_height = 1.0
    # Left railing
    ops.append({
        "type": "box",
        "position": [0.0, 0.0, deck_height + 0.3],
        "size": [0.2, span, railing_height],
        "material": "stone_railing",
        "role": "railing",
    })
    # Right railing
    ops.append({
        "type": "box",
        "position": [width - 0.2, 0.0, deck_height + 0.3],
        "size": [0.2, span, railing_height],
        "material": "stone_railing",
        "role": "railing",
    })

    return BuildingSpec(
        footprint=(width, span),
        floors=1,
        style="fortress",
        operations=ops,
    )


def generate_fortress_spec(
    size: float = 60.0,
    wall_thickness: float = 2.0,
    seed: int = 0,
) -> BuildingSpec:
    """Generate a fortress spec with outer walls, corner towers, keep, courtyard, gatehouse."""
    rng = random.Random(seed)
    ops: list[dict] = []
    wall_height = 10.0
    tower_radius = 4.0
    tower_height = 14.0
    keep_size = 15.0

    # Outer curtain walls
    # Front
    ops.append({
        "type": "box",
        "position": [0.0, 0.0, 0.0],
        "size": [size, wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })
    # Back
    ops.append({
        "type": "box",
        "position": [0.0, size - wall_thickness, 0.0],
        "size": [size, wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })
    # Left
    ops.append({
        "type": "box",
        "position": [0.0, wall_thickness, 0.0],
        "size": [wall_thickness, size - 2 * wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })
    # Right
    ops.append({
        "type": "box",
        "position": [size - wall_thickness, wall_thickness, 0.0],
        "size": [wall_thickness, size - 2 * wall_thickness, wall_height],
        "material": "stone_fortified",
        "role": "curtain_wall",
    })

    # Corner towers
    corners = [
        (0.0, 0.0),
        (size, 0.0),
        (0.0, size),
        (size, size),
    ]
    for cx, cy in corners:
        ops.append({
            "type": "cylinder",
            "position": [cx, cy, 0.0],
            "radius": tower_radius,
            "height": tower_height,
            "segments": 16,
            "material": "stone_fortified",
            "role": "tower",
        })

    # Central keep
    keep_x = (size - keep_size) / 2
    keep_y = (size - keep_size) / 2
    keep_spec = evaluate_building_grammar(
        width=keep_size, depth=keep_size, floors=3, style="fortress", seed=seed
    )
    for op in keep_spec.operations:
        op_copy = dict(op)
        if "position" in op_copy and len(op_copy["position"]) >= 2:
            pos = list(op_copy["position"])
            pos[0] += keep_x
            pos[1] += keep_y
            op_copy["position"] = pos
        op_copy["role"] = "keep"
        ops.append(op_copy)

    # Courtyard area (marker -- no solid geometry, but defines the open space)
    courtyard_inset = wall_thickness + 3.0
    ops.append({
        "type": "box",
        "position": [courtyard_inset, courtyard_inset, 0.0],
        "size": [
            size - 2 * courtyard_inset,
            size - 2 * courtyard_inset,
            0.05,
        ],
        "material": "dirt_packed",
        "role": "courtyard",
    })

    # Gatehouse
    gate_width = 5.0
    gate_x = (size - gate_width) / 2
    ops.append({
        "type": "box",
        "position": [gate_x, -1.5, 0.0],
        "size": [gate_width, wall_thickness + 3.0, wall_height + 3.0],
        "material": "stone_fortified",
        "role": "gatehouse",
    })
    ops.append({
        "type": "opening",
        "wall_index": 0,
        "position": [gate_x + 0.75, 0.0],
        "size": [3.5, wall_height - 1.0],
        "role": "gatehouse",
    })

    return BuildingSpec(
        footprint=(size, size),
        floors=3,
        style="fortress",
        operations=ops,
    )


# ---------------------------------------------------------------------------
# Ruins Damage
# ---------------------------------------------------------------------------

# Priority ordering for damage removal (roof goes first, foundation last)
_DAMAGE_PRIORITY = {
    "detail": 0,
    "roof": 1,
    "window": 2,
    "door": 2,
    "floor_slab": 3,
    "wall": 4,
    "foundation": 5,
    # Specialized roles
    "battlement": 1,
    "stairs": 3,
    "tower_body": 4,
    "curtain_wall": 4,
    "keep": 5,
    "gatehouse": 4,
    "courtyard": 6,
    "abutment": 5,
    "arch": 3,
    "road_deck": 3,
    "railing": 1,
    "pier": 4,
}


def apply_ruins_damage(
    spec: BuildingSpec,
    damage_level: float = 0.5,
    seed: int = 0,
) -> BuildingSpec:
    """Apply ruins damage to a building spec.

    damage_level: 0.0 = no damage, 1.0 = maximum destruction.
    Removes operations by priority (roof/details first, foundation last).
    Adds debris operations near removed elements.
    At high damage levels, adds vegetation markers.
    """
    if damage_level <= 0.0:
        return BuildingSpec(
            footprint=spec.footprint,
            floors=spec.floors,
            style=spec.style,
            operations=list(spec.operations),
        )

    rng = random.Random(seed)

    # Sort operations by damage priority (lower = removed first)
    indexed_ops = []
    for i, op in enumerate(spec.operations):
        role = op.get("role", "detail")
        priority = _DAMAGE_PRIORITY.get(role, 2)
        indexed_ops.append((priority, i, op))

    indexed_ops.sort(key=lambda x: x[0])

    surviving: list[dict] = []
    debris: list[dict] = []

    for priority, idx, op in indexed_ops:
        # Probability of removal increases with damage_level and lower priority
        max_priority = max(_DAMAGE_PRIORITY.values())
        # Normalize priority to [0, 1] where 0 = most vulnerable
        norm_priority = priority / max_priority if max_priority > 0 else 0
        # Removal threshold: items with lower priority removed at lower damage levels
        removal_threshold = norm_priority * 0.9 + 0.1  # range [0.1, 1.0]
        remove_chance = damage_level / removal_threshold

        if rng.random() < remove_chance and damage_level > 0:
            # Create debris near the removed element
            if "position" in op and len(op["position"]) >= 2:
                pos = op["position"]
                debris.append({
                    "type": "box",
                    "position": [
                        pos[0] + rng.uniform(-1.0, 1.0),
                        pos[1] + rng.uniform(-1.0, 1.0),
                        0.0,
                    ],
                    "size": [
                        rng.uniform(0.3, 1.0),
                        rng.uniform(0.3, 1.0),
                        rng.uniform(0.1, 0.5),
                    ],
                    "material": op.get("material", "rubble"),
                    "role": "debris",
                })
        else:
            surviving.append(op)

    # Combine surviving + debris
    result_ops = surviving + debris

    # At high damage levels (>= 0.6), add vegetation markers
    if damage_level >= 0.6:
        n_veg = max(1, int(damage_level * 5))
        for _ in range(n_veg):
            vx = rng.uniform(0, spec.footprint[0])
            vy = rng.uniform(0, spec.footprint[1])
            result_ops.append({
                "type": "box",
                "position": [vx, vy, 0.0],
                "size": [0.5, 0.5, rng.uniform(0.3, 1.5)],
                "material": rng.choice(["ivy", "moss", "vine", "fern"]),
                "role": "vegetation",
            })

    return BuildingSpec(
        footprint=spec.footprint,
        floors=spec.floors,
        style=spec.style,
        operations=result_ops,
    )


# ---------------------------------------------------------------------------
# Interior Generation
# ---------------------------------------------------------------------------

# Room type furniture definitions
# Each item: (type, placement_rule, base_size_xy, height)
# placement_rule: "wall" = along wall, "center" = center area, "corner" = in corner
_ROOM_CONFIGS: dict[str, list[tuple[str, str, tuple[float, float], float]]] = {
    "tavern": [
        ("bar_counter", "wall", (3.0, 0.8), 1.1),
        ("fireplace", "wall", (1.5, 0.8), 1.8),
        ("table", "center", (1.2, 1.2), 0.75),
        ("table", "center", (1.2, 1.2), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("barrel", "corner", (0.6, 0.6), 0.8),
        ("shelf", "wall", (1.5, 0.4), 1.8),
    ],
    "throne_room": [
        ("throne", "wall", (1.5, 1.2), 2.0),
        ("carpet", "center", (3.0, 8.0), 0.02),
        ("pillar", "wall", (0.6, 0.6), 3.0),
        ("pillar", "wall", (0.6, 0.6), 3.0),
        ("pillar", "wall", (0.6, 0.6), 3.0),
        ("pillar", "wall", (0.6, 0.6), 3.0),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("brazier", "center", (0.5, 0.5), 1.0),
        ("brazier", "center", (0.5, 0.5), 1.0),
    ],
    "dungeon_cell": [
        ("cot", "wall", (1.8, 0.7), 0.5),
        ("chains", "wall", (0.3, 0.3), 1.5),
        ("bucket", "corner", (0.4, 0.4), 0.4),
    ],
    "bedroom": [
        ("bed", "wall", (2.0, 1.5), 0.6),
        ("wardrobe", "wall", (1.2, 0.6), 1.8),
        ("desk", "wall", (1.2, 0.6), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("nightstand", "wall", (0.5, 0.5), 0.5),
        ("rug", "center", (2.0, 1.5), 0.02),
    ],
    "kitchen": [
        ("cooking_fire", "wall", (1.5, 0.8), 1.0),
        ("table", "center", (1.5, 1.0), 0.75),
        ("shelf", "wall", (2.0, 0.4), 1.8),
        ("barrel", "corner", (0.6, 0.6), 0.8),
        ("barrel", "corner", (0.6, 0.6), 0.8),
        ("crate", "corner", (0.6, 0.6), 0.6),
    ],
    "library": [
        ("bookshelf", "wall", (2.0, 0.5), 2.5),
        ("bookshelf", "wall", (2.0, 0.5), 2.5),
        ("bookshelf", "wall", (2.0, 0.5), 2.5),
        ("desk", "center", (1.5, 0.8), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("candelabra", "center", (0.3, 0.3), 1.2),
    ],
    "armory": [
        ("weapon_rack", "wall", (2.0, 0.5), 2.0),
        ("weapon_rack", "wall", (2.0, 0.5), 2.0),
        ("armor_stand", "wall", (0.6, 0.6), 1.8),
        ("armor_stand", "wall", (0.6, 0.6), 1.8),
        ("table", "center", (1.2, 0.8), 0.75),
        ("crate", "corner", (0.8, 0.8), 0.6),
    ],
    "chapel": [
        ("altar", "wall", (1.5, 0.8), 1.2),
        ("pew", "center", (2.0, 0.6), 0.8),
        ("pew", "center", (2.0, 0.6), 0.8),
        ("pew", "center", (2.0, 0.6), 0.8),
        ("candelabra", "center", (0.3, 0.3), 1.5),
        ("candelabra", "center", (0.3, 0.3), 1.5),
        ("banner", "wall", (0.8, 0.1), 2.5),
    ],
}


def generate_interior_layout(
    room_type: str,
    width: float,
    depth: float,
    height: float = 3.0,
    seed: int = 0,
) -> list[dict]:
    """Generate furniture placement for a room type.

    Returns list of dicts with: type, position (x,y,z), rotation, scale.
    Uses collision avoidance to prevent overlapping items.
    """
    rng = random.Random(seed)
    config = _ROOM_CONFIGS.get(room_type, [])
    if not config:
        return []

    placed: list[dict] = []
    occupied: list[tuple[float, float, float, float]] = []  # (cx, cy, sx, sy) bounding boxes

    # Margins from walls
    wall_margin = 0.15

    for item_type, rule, base_size, item_height in config:
        sx, sy = base_size
        rotation = 0.0

        # Try to find a non-overlapping placement
        max_attempts = 50
        placed_ok = False

        for attempt in range(max_attempts):
            if rule == "wall":
                # Place along a wall
                wall = rng.randint(0, 3)
                if wall == 0:  # front wall (y=0)
                    x = rng.uniform(sx / 2 + wall_margin, width - sx / 2 - wall_margin)
                    y = sy / 2 + wall_margin
                    rotation = 0.0
                elif wall == 1:  # back wall (y=depth)
                    x = rng.uniform(sx / 2 + wall_margin, width - sx / 2 - wall_margin)
                    y = depth - sy / 2 - wall_margin
                    rotation = math.pi
                elif wall == 2:  # left wall (x=0)
                    x = sy / 2 + wall_margin
                    y = rng.uniform(sx / 2 + wall_margin, depth - sx / 2 - wall_margin)
                    rotation = math.pi / 2
                    # swap effective size for rotated item
                    sx, sy = sy, sx
                else:  # right wall (x=width)
                    x = width - sy / 2 - wall_margin
                    y = rng.uniform(sx / 2 + wall_margin, depth - sx / 2 - wall_margin)
                    rotation = -math.pi / 2
                    sx, sy = sy, sx

            elif rule == "center":
                # Place in the center area (away from walls)
                margin = max(sx, sy) / 2 + 0.3
                x = rng.uniform(margin, width - margin)
                y = rng.uniform(margin, depth - margin)
                rotation = rng.uniform(-0.1, 0.1)  # slight random rotation

            elif rule == "corner":
                # Place in a corner
                corner = rng.randint(0, 3)
                if corner == 0:
                    x = sx / 2 + wall_margin
                    y = sy / 2 + wall_margin
                elif corner == 1:
                    x = width - sx / 2 - wall_margin
                    y = sy / 2 + wall_margin
                elif corner == 2:
                    x = sx / 2 + wall_margin
                    y = depth - sy / 2 - wall_margin
                else:
                    x = width - sx / 2 - wall_margin
                    y = depth - sy / 2 - wall_margin
                rotation = 0.0
            else:
                x = width / 2
                y = depth / 2
                rotation = 0.0

            # Check collision with previously placed items
            collides = False
            for ocx, ocy, osx, osy in occupied:
                if abs(x - ocx) < (sx + osx) / 2 and abs(y - ocy) < (sy + osy) / 2:
                    collides = True
                    break

            if not collides:
                # Check bounds
                if (sx / 2 <= x <= width - sx / 2 and
                        sy / 2 <= y <= depth - sy / 2):
                    occupied.append((x, y, sx, sy))
                    placed.append({
                        "type": item_type,
                        "position": [round(x, 4), round(y, 4), 0.0],
                        "rotation": round(rotation, 4),
                        "scale": [round(sx, 4), round(sy, 4), round(item_height, 4)],
                    })
                    placed_ok = True
                    break

            # Reset swapped sizes for next attempt
            sx, sy = base_size

        # If we exhausted attempts, skip this item silently

    return placed


# ---------------------------------------------------------------------------
# Modular Kit
# ---------------------------------------------------------------------------

# Dimensions as multiples of unit cell: (width_cells, depth_cells, height_cells)
MODULAR_CATALOG: dict[str, dict] = {
    "wall_straight": {
        "dimensions": (1, 1, 1),  # 1 cell wide, 1 cell thick (minimum), 1 cell tall
        "origin": "corner",
        "connection_points": [
            {"face": "left", "offset": [0.0, 0.5, 0.5]},
            {"face": "right", "offset": [1.0, 0.5, 0.5]},
        ],
    },
    "wall_corner": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "left", "offset": [0.0, 0.5, 0.5]},
            {"face": "front", "offset": [0.5, 0.0, 0.5]},
        ],
    },
    "wall_t": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "left", "offset": [0.0, 0.5, 0.5]},
            {"face": "right", "offset": [1.0, 0.5, 0.5]},
            {"face": "front", "offset": [0.5, 0.0, 0.5]},
        ],
    },
    "floor": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "left", "offset": [0.0, 0.5, 0.0]},
            {"face": "right", "offset": [1.0, 0.5, 0.0]},
            {"face": "front", "offset": [0.5, 0.0, 0.0]},
            {"face": "back", "offset": [0.5, 1.0, 0.0]},
        ],
    },
    "door_frame": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "left", "offset": [0.0, 0.5, 0.5]},
            {"face": "right", "offset": [1.0, 0.5, 0.5]},
        ],
    },
    "window_frame": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "left", "offset": [0.0, 0.5, 0.5]},
            {"face": "right", "offset": [1.0, 0.5, 0.5]},
        ],
    },
    "stairs": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "front", "offset": [0.5, 0.0, 0.0]},
            {"face": "back", "offset": [0.5, 1.0, 1.0]},
        ],
    },
    "pillar": {
        "dimensions": (1, 1, 1),
        "origin": "corner",
        "connection_points": [
            {"face": "top", "offset": [0.5, 0.5, 1.0]},
            {"face": "bottom", "offset": [0.5, 0.5, 0.0]},
        ],
    },
}


def generate_modular_pieces(
    cell_size: float = 2.0,
    pieces: Optional[list[str]] = None,
) -> list[dict]:
    """Generate modular kit piece specs scaled to cell_size.

    If pieces is None, generates all catalog entries.
    Returns list of piece spec dicts with scaled dimensions and connection points.
    """
    if pieces is None:
        piece_names = list(MODULAR_CATALOG.keys())
    else:
        piece_names = pieces

    result: list[dict] = []
    for name in piece_names:
        catalog_entry = MODULAR_CATALOG[name]
        raw_dims = catalog_entry["dimensions"]

        # Scale dimensions to cell_size (exact multiples, no floating point drift)
        scaled_dims = [
            round(d * cell_size, 10) for d in raw_dims
        ]

        # Scale connection point offsets
        scaled_cps = []
        for cp in catalog_entry["connection_points"]:
            scaled_cp = {
                "face": cp["face"],
                "offset": [round(o * cell_size, 10) for o in cp["offset"]],
            }
            scaled_cps.append(scaled_cp)

        result.append({
            "name": name,
            "dimensions": scaled_dims,
            "origin": catalog_entry["origin"],
            "connection_points": scaled_cps,
            "cell_size": cell_size,
        })

    return result
