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
- FURNITURE_SCALE_REFERENCE: real-world scale constraints for validation (WORLD-07)
- expanded room set covering taverns, smithies, storage halls, barracks,
  guard posts, shrines, treasuries, war rooms, alchemy labs, torture chambers,
  crypts, and dining halls (WORLD-02)
- validate_furniture_scale(): dimension validation against reference (WORLD-07)
- _STORYTELLING_PROPS + add_storytelling_props(): layer-3 narrative clutter (AAA-05)
- generate_overrun_variant(): narrative debris beyond structural damage (WORLD-09)
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
        "door": {"style": "rounded", "width": 1.0, "height": 2.2},
        "details": ["vine_growth", "moss_patches", "root_buttress"],
    },
}

# ---------------------------------------------------------------------------
# Furniture Scale Reference (WORLD-07)
# ---------------------------------------------------------------------------

FURNITURE_SCALE_REFERENCE: dict[str, dict[str, tuple[float, float]]] = {
    "door": {"width": (1.0, 1.2), "height": (2.0, 2.2)},
    "ceiling": {"height": (2.8, 3.5)},
    "table": {"height": (0.72, 0.78), "width": (0.8, 1.8)},
    "chair": {"height": (0.80, 1.00), "seat_height": (0.45, 0.50), "seat_depth": (0.4, 0.5)},
    "bed": {"width": (0.9, 2.1), "length": (1.4, 2.1), "height": (0.45, 0.65)},
    "shelf": {"depth": (0.3, 0.5), "height": (1.5, 2.6)},
    "barrel": {"diameter": (0.4, 0.6), "height": (0.8, 1.0)},
    "crate": {"size": (0.4, 0.8)},
    "torch_sconce": {"height": (1.5, 1.8), "protrusion": (0.15, 0.25)},
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
        overhang = roof_cfg["overhang"]
        ridge_height = math.tan(math.radians(roof_cfg["pitch"])) * (depth / 2 + overhang)
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
        ridge_height = math.tan(math.radians(roof_cfg["pitch"])) * (depth / 2 + overhang)
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


def _append_fortress_tower_kit(
    ops: list[dict],
    *,
    cx: float,
    cy: float,
    base_z: float,
    radius: float,
    height: float,
    material: str,
    role: str,
) -> None:
    """Append a tower built from stacked masses rather than a single shaft.

    The goal is to keep fortress and castle towers readable as deliberate
    architecture: a grounded base, a stepped shaft, a stair annex, and a
    crenellated crown with visible shoulders. This intentionally avoids the
    "cylinder with blocks" read.
    """
    shaft_height = max(2.8, height * 0.78)
    crown_height = max(0.8, height * 0.12)
    lower_h = max(0.9, height * 0.22)
    mid_h = max(1.2, height * 0.30)
    upper_h = max(0.9, height * 0.18)
    plinth = radius * 2.35
    shaft = radius * 1.82
    stair_w = radius * 0.92
    stair_d = radius * 0.78
    stair_h = max(1.6, height * 0.52)
    buttress_w = radius * 0.58
    buttress_d = radius * 0.66
    buttress_h = max(1.0, height * 0.36)
    crown = radius * 1.96

    ops.extend([
        {
            "type": "box",
            "position": [cx - plinth * 0.5, cy - plinth * 0.5, base_z],
            "size": [plinth, plinth, max(0.45, height * 0.10)],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - shaft * 0.5, cy - shaft * 0.5, base_z + height * 0.08],
            "size": [shaft, shaft, lower_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - shaft * 0.46, cy - shaft * 0.46, base_z + height * 0.34],
            "size": [shaft * 0.92, shaft * 0.92, mid_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - shaft * 0.38, cy - shaft * 0.38, base_z + height * 0.62],
            "size": [shaft * 0.76, shaft * 0.76, upper_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx + radius * 0.58, cy - stair_d * 0.30, base_z + height * 0.14],
            "size": [stair_w, stair_d, stair_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - radius * 1.12, cy + radius * 0.10, base_z + height * 0.18],
            "size": [buttress_w, buttress_d, buttress_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - crown * 0.5, cy - crown * 0.5, base_z + height * 0.76],
            "size": [crown, crown, crown_height * 0.18],
            "material": material,
            "role": role,
        },
    ])

    merlon_size = radius * 0.28
    merlon_z = base_z + height - max(0.35, crown_height * 0.45)
    for mx, my in (
        (cx - radius * 0.95, cy - radius * 0.08),
        (cx + radius * 0.95 - merlon_size, cy - radius * 0.08),
        (cx - radius * 0.08, cy - radius * 0.95),
        (cx - radius * 0.08, cy + radius * 0.95 - merlon_size),
    ):
        ops.append({
            "type": "box",
            "position": [mx, my, merlon_z],
            "size": [merlon_size, merlon_size, max(0.55, crown_height * 0.50)],
            "material": material,
            "role": role,
        })


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
    tower_radius = max(3.4, outer_size * 0.085)
    tower_height = wall_height + max(2.4, outer_size * 0.055)
    tower_segments = 8
    tower_taper = 0.9
    tower_crown_height = max(0.8, tower_height * 0.10)
    keep_height = tower_height + max(3.5, keep_size * 0.18)

    plinth_margin = max(0.7, outer_size * 0.02)
    ops.append({
        "type": "box",
        "position": [-plinth_margin, -plinth_margin, 0.0],
        "size": [outer_size + 2 * plinth_margin, outer_size + 2 * plinth_margin, 0.7],
        "material": "stone_heavy",
        "role": "foundation",
    })

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

    # Corner towers: octagonal, tapering shafts with crenellated crowns.
    corners = [
        (0.0, 0.0),
        (outer_size, 0.0),
        (0.0, outer_size),
        (outer_size, outer_size),
    ]
    for i, (cx, cy) in enumerate(corners[:tower_count]):
        _append_fortress_tower_kit(
            ops,
            cx=cx,
            cy=cy,
            base_z=0.0,
            radius=tower_radius,
            height=tower_height,
            material="stone_fortified",
            role="tower",
        )

    # Optional mid-wall towers for larger castles, so long walls do not read flat.
    extra_towers = max(0, tower_count - 4)
    if extra_towers > 0:
        spacing = outer_size / (extra_towers + 1)
        for ti in range(extra_towers):
            px = spacing * (ti + 1)
            side = ti % 2
            py = -tower_radius * 0.12 if side == 0 else outer_size + tower_radius * 0.12
            _append_fortress_tower_kit(
                ops,
                cx=px,
                cy=py,
                base_z=0.0,
                radius=tower_radius * 0.85,
                height=tower_height * 0.95,
                material="stone_fortified",
                role="tower",
            )

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

    keep_annex_depth = max(2.2, keep_size * 0.18)
    keep_annex_height = max(2.4, keep_height * 0.38)
    keep_annex_width = max(3.0, keep_size * 0.54)
    ops.extend([
        {
            "type": "box",
            "position": [keep_x + keep_size * 0.18, keep_y - keep_annex_depth * 0.55, 0.55],
            "size": [keep_annex_width, keep_annex_depth, keep_annex_height],
            "material": "stone_fortified",
            "role": "keep_wing",
        },
        {
            "type": "box",
            "position": [keep_x + keep_size * 0.10, keep_y + keep_size - keep_annex_depth * 0.45, 0.55],
            "size": [keep_annex_width * 0.95, keep_annex_depth, keep_annex_height * 0.92],
            "material": "stone_fortified",
            "role": "keep_wing",
        },
        {
            "type": "box",
            "position": [keep_x - keep_annex_depth * 0.45, keep_y + keep_size * 0.22, 0.55],
            "size": [keep_annex_depth, max(3.0, keep_size * 0.54), keep_annex_height * 0.88],
            "material": "stone_fortified",
            "role": "keep_buttress",
        },
        {
            "type": "box",
            "position": [keep_x + keep_size - keep_annex_depth * 0.58, keep_y + keep_size * 0.22, 0.55],
            "size": [keep_annex_depth, max(3.0, keep_size * 0.54), keep_annex_height * 0.88],
            "material": "stone_fortified",
            "role": "keep_buttress",
        },
    ])

    # Crown turret: keep it anchored to the keep roofline instead of floating
    # above the structure. This should read as a deliberate roof mass, not a
    # separate tower copied on top of the keep.
    keep_crown_height = max(5.2, keep_height * 0.44)
    keep_crown_base_z = 0.45 + keep_height * 0.56
    ops.append({
        "type": "tower",
        "position": [keep_x + keep_size / 2.0, keep_y + keep_size / 2.0, keep_crown_base_z],
        "radius": keep_size * 0.28,
        "height": keep_crown_height,
        "segments": 8,
        "taper": 0.86,
        "crown_height": max(0.8, keep_crown_height * 0.12),
        "profile": "keep",
        "material": "stone_fortified",
        "role": "keep_crown",
    })

    # Gatehouse (front opening with portcullis)
    gate_x = (outer_size - 4.0) / 2
    ops.append({
        "type": "box",
        "position": [gate_x - 1.0, -1.6, 0.0],
        "size": [6.0, wall_thickness + 3.2, wall_height + 2.8],
        "material": "stone_fortified",
        "role": "gatehouse",
    })
    ops.append({
        "type": "box",
        "position": [gate_x - 1.25, -3.0, 0.0],
        "size": [6.5, 1.8, wall_height * 0.7],
        "material": "stone_fortified",
        "role": "gatehouse",
    })
    ops.append({
        "type": "box",
        "position": [gate_x - 1.45, -0.9, 0.0],
        "size": [1.2, 1.2, wall_height * 0.9],
        "material": "stone_fortified",
        "role": "gatehouse_bastion",
    })
    ops.append({
        "type": "box",
        "position": [gate_x + 4.25, -0.9, 0.0],
        "size": [1.2, 1.2, wall_height * 0.9],
        "material": "stone_fortified",
        "role": "gatehouse_bastion",
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
    """Generate a standalone tower spec with layered fortress massing and battlements."""
    rng = random.Random(seed)
    ops: list[dict] = []
    tower_height = max(10.0, height)
    crown_height = max(0.9, tower_height * 0.12)

    # Foundation
    ops.append({
        "type": "box",
        "position": [-(radius + 0.35), -(radius + 0.35), 0.0],
        "size": [(radius + 0.35) * 2.0, (radius + 0.35) * 2.0, 0.45],
        "material": "stone_dark",
        "role": "foundation",
    })

    # Main tower body. The taper and crown keep it from reading as a simple slab.
    ops.append({
        "type": "tower",
        "position": [0.0, 0.0, 0.45],
        "radius": radius,
        "height": tower_height,
        "segments": 8,
        "taper": 0.88,
        "crown_height": crown_height,
        "profile": "fortress",
        "material": "stone_fortified",
        "role": "tower_body",
    })

    # Floor slabs (internal)
    floor_height = tower_height / floors
    for i in range(1, floors):
        ops.append({
            "type": "box",
            "position": [-(radius - 0.1), -(radius - 0.1), 0.45 + i * floor_height - 0.1],
            "size": [(radius - 0.1) * 2.0, (radius - 0.1) * 2.0, 0.2],
            "material": "stone_slab",
            "role": "floor_slab",
        })

    # Attached stair and shoulder masses break the tower's cylindrical read.
    ops.extend([
        {
            "type": "box",
            "position": [radius * 0.58, -radius * 0.46, 0.45],
            "size": [radius * 0.58, radius * 0.42, tower_height * 0.55],
            "material": "stone_steps",
            "role": "stairs",
        },
        {
            "type": "box",
            "position": [-radius * 0.30, -radius * 0.34, 0.45],
            "size": [radius * 0.44, radius * 0.30, tower_height * 0.28],
            "material": "stone_fortified",
            "role": "tower_entry",
        },
        {
            "type": "box",
            "position": [-radius * 1.08, -radius * 0.34, 0.45],
            "size": [radius * 0.44, radius * 0.46, tower_height * 0.34],
            "material": "stone_fortified",
            "role": "tower_buttress",
        },
        {
            "type": "box",
            "position": [radius * 0.72, radius * 0.42, 0.45],
            "size": [radius * 0.38, radius * 0.42, tower_height * 0.38],
            "material": "stone_fortified",
            "role": "tower_buttress",
        },
    ])

    # Windows (arrow slits on each floor)
    for floor_idx in range(floors):
        floor_z = 0.45 + floor_idx * floor_height + floor_height * 0.5
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
    tower_radius = max(4.2, size * 0.08)
    tower_height = wall_height + max(2.8, size * 0.055)
    tower_segments = 8
    tower_taper = 0.9
    tower_crown_height = max(0.9, tower_height * 0.10)
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
        _append_fortress_tower_kit(
            ops,
            cx=cx,
            cy=cy,
            base_z=0.0,
            radius=tower_radius,
            height=tower_height,
            material="stone_fortified",
            role="tower",
        )

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

    keep_crown_height = max(5.0, tower_height * 0.42)
    keep_crown_base_z = 0.45 + tower_height * 0.58
    ops.append({
        "type": "tower",
        "position": [keep_x + keep_size / 2.0, keep_y + keep_size / 2.0, keep_crown_base_z],
        "radius": keep_size * 0.27,
        "height": keep_crown_height,
        "segments": 8,
        "taper": 0.86,
        "crown_height": max(0.8, keep_crown_height * 0.12),
        "profile": "keep",
        "material": "stone_fortified",
        "role": "keep_crown",
    })

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
    "smithy": [
        ("anvil", "center", (0.7, 0.5), 0.75),
        ("forge", "wall", (1.5, 0.8), 1.2),
        ("workbench", "wall", (1.5, 0.6), 0.78),
        ("weapon_rack", "wall", (1.8, 0.4), 1.8),
        ("barrel", "corner", (0.6, 0.6), 0.8),
        ("crate", "corner", (0.6, 0.6), 0.6),
    ],
    "storage": [
        ("shelf", "wall", (2.0, 0.45), 2.1),
        ("shelf", "wall", (2.0, 0.45), 2.1),
        ("crate", "corner", (0.8, 0.8), 0.65),
        ("crate", "corner", (0.8, 0.8), 0.65),
        ("crate", "corner", (0.8, 0.8), 0.65),
        ("barrel", "corner", (0.6, 0.6), 0.8),
        ("barrel", "corner", (0.6, 0.6), 0.8),
    ],
    "barracks": [
        ("bed", "wall", (2.0, 1.4), 0.6),
        ("bed", "wall", (2.0, 1.4), 0.6),
        ("bed", "wall", (2.0, 1.4), 0.6),
        ("weapon_rack", "wall", (1.8, 0.4), 1.8),
        ("table", "center", (1.3, 1.0), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("crate", "corner", (0.8, 0.8), 0.6),
    ],
    "guard_post": [
        ("table", "center", (1.5, 0.8), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("weapon_rack", "wall", (1.8, 0.4), 1.8),
        ("banner", "wall", (0.8, 0.1), 2.2),
        ("brazier", "corner", (0.6, 0.6), 1.0),
        ("crate", "corner", (0.8, 0.8), 0.6),
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
    "study": [
        ("desk", "wall", (1.6, 0.7), 0.75),
        ("desk", "wall", (1.6, 0.7), 0.75),
        ("bookshelf", "wall", (2.0, 0.5), 2.4),
        ("bookshelf", "wall", (2.0, 0.5), 2.4),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("map_display", "wall", (1.4, 0.4), 0.08),
        ("candelabra", "center", (0.3, 0.3), 1.2),
    ],
    "great_hall": [
        ("long_table", "center", (2.0, 4.5), 0.75),
        ("long_table", "center", (2.0, 3.5), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chandelier", "center", (0.8, 0.8), 0.35),
        ("fireplace", "wall", (2.0, 1.0), 2.0),
        ("banner", "wall", (1.0, 0.15), 2.8),
        ("banner", "wall", (1.0, 0.15), 2.8),
        ("candelabra", "center", (0.3, 0.3), 1.4),
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
    "shrine_room": [
        ("altar", "wall", (1.5, 0.8), 1.2),
        ("pew", "center", (2.0, 0.6), 0.8),
        ("pew", "center", (2.0, 0.6), 0.8),
        ("candelabra", "center", (0.3, 0.3), 1.5),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("rug", "center", (2.0, 1.2), 0.02),
    ],
    # ---- 8 new room types (WORLD-02) ----
    "blacksmith": [
        ("anvil", "center", (0.7, 0.5), 0.75),
        ("forge", "wall", (1.5, 0.8), 1.2),
        ("workbench", "wall", (1.5, 0.6), 0.78),
        ("weapon_rack", "wall", (1.8, 0.4), 1.8),
        ("tool_rack", "wall", (1.2, 0.35), 1.6),
        ("bellows", "wall", (0.6, 0.5), 1.0),
    ],
    "guard_barracks": [
        ("bed", "wall", (2.0, 1.4), 0.6),
        ("bed", "wall", (2.0, 1.4), 0.6),
        ("bed", "wall", (2.0, 1.4), 0.6),
        ("bunk_bed", "wall", (2.0, 1.2), 0.7),
        ("weapon_rack", "wall", (1.8, 0.4), 1.8),
        ("table", "center", (1.2, 1.2), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("crate", "corner", (0.8, 0.8), 0.6),
    ],
    "treasury": [
        ("coin_pile", "center", (0.8, 0.8), 0.4),
        ("display_case", "wall", (1.5, 0.5), 1.5),
        ("locked_chest", "center", (0.7, 0.5), 0.5),
        ("locked_chest", "center", (0.7, 0.5), 0.5),
        ("locked_chest", "center", (0.7, 0.5), 0.5),
        ("chandelier", "center", (0.6, 0.6), 0.3),
        ("safe", "wall", (0.6, 0.5), 1.0),
    ],
    "war_room": [
        ("large_table", "center", (1.8, 1.2), 0.78),
        ("map_display", "center", (1.4, 0.8), 0.05),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("candelabra", "center", (0.3, 0.3), 1.2),
    ],
    "alchemy_lab": [
        ("workbench", "center", (1.5, 0.6), 0.78),
        ("shelf_with_bottles", "wall", (1.8, 0.35), 1.8),
        ("shelf_with_bottles", "wall", (1.8, 0.35), 1.8),
        ("cauldron", "center", (0.8, 0.8), 0.7),
        ("herb_rack", "wall", (1.2, 0.35), 1.6),
        ("distillation_apparatus", "wall", (0.8, 0.5), 1.2),
    ],
    "torture_chamber": [
        ("rack", "center", (2.0, 0.8), 1.0),
        ("iron_maiden", "wall", (0.8, 0.6), 2.0),
        ("chains", "wall", (0.3, 0.3), 1.8),
        ("brazier", "center", (0.5, 0.5), 0.8),
        ("cage", "corner", (1.2, 1.2), 2.0),
    ],
    "crypt": [
        ("sarcophagus", "center", (1.0, 2.0), 0.9),
        ("sarcophagus", "center", (1.0, 2.0), 0.9),
        ("wall_tomb", "wall", (1.2, 0.6), 0.9),
        ("wall_tomb", "wall", (1.2, 0.6), 0.9),
        ("candelabra", "corner", (0.3, 0.3), 1.5),
        ("altar", "wall", (1.5, 0.8), 1.2),
    ],
    "dining_hall": [
        ("long_table", "center", (1.8, 4.0), 0.75),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chandelier", "center", (0.6, 0.6), 0.3),
        ("fireplace", "wall", (1.5, 0.8), 1.8),
        ("serving_table", "wall", (1.5, 0.6), 0.75),
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


# ---------------------------------------------------------------------------
# Furniture Scale Validation (WORLD-07)
# ---------------------------------------------------------------------------

# Mapping from furniture item types to FURNITURE_SCALE_REFERENCE keys and
# which dimensions should be checked: (ref_key, [(item_dim_index, ref_dim)])
_FURNITURE_SCALE_MAP: dict[str, list[tuple[str, str, int]]] = {
    # (ref_category, ref_dimension, item_tuple_index)
    # item_tuple_index: 0=width(sx), 1=depth(sy), 2=height(item_height)
    "table": [("table", "height", 2), ("table", "width", 0)],
    "large_table": [("table", "height", 2), ("table", "width", 0)],
    "long_table": [("table", "height", 2), ("table", "width", 0)],
    "serving_table": [("table", "height", 2)],
    "desk": [("table", "height", 2)],
    "workbench": [("table", "height", 2)],
    "chair": [("chair", "height", 2)],
    "bed": [("bed", "height", 2), ("bed", "width", 0), ("bed", "length", 1)],
    "bunk_bed": [("bed", "width", 0)],
    "cot": [("bed", "width", 0)],
    "shelf": [("shelf", "height", 2), ("shelf", "depth", 1)],
    "bookshelf": [("shelf", "height", 2)],
    "shelf_with_bottles": [("shelf", "height", 2), ("shelf", "depth", 1)],
    "herb_rack": [("shelf", "depth", 1)],
    "tool_rack": [("shelf", "depth", 1)],
    "barrel": [("barrel", "height", 2), ("barrel", "diameter", 0)],
    "crate": [("crate", "size", 0)],
    "footlocker": [("crate", "size", 0)],
}


def validate_furniture_scale(
    room_type: str,
    ceiling_height: float = 3.0,
) -> list[str]:
    """Validate furniture in *room_type* against FURNITURE_SCALE_REFERENCE.

    Returns list of violation strings (empty if all valid).
    Also validates ceiling height against reference.
    """
    violations: list[str] = []

    # Ceiling height check
    ceil_ref = FURNITURE_SCALE_REFERENCE["ceiling"]["height"]
    if not (ceil_ref[0] <= ceiling_height <= ceil_ref[1]):
        violations.append(
            f"ceiling height {ceiling_height} outside range "
            f"[{ceil_ref[0]}, {ceil_ref[1]}]"
        )

    config = _ROOM_CONFIGS.get(room_type)
    if config is None:
        return violations

    for item_type, _rule, base_size, item_height in config:
        checks = _FURNITURE_SCALE_MAP.get(item_type, [])
        for ref_category, ref_dimension, dim_index in checks:
            ref_range = FURNITURE_SCALE_REFERENCE.get(ref_category, {}).get(ref_dimension)
            if ref_range is None:
                continue
            # Get actual value from the item tuple
            if dim_index == 0:
                actual = base_size[0]
            elif dim_index == 1:
                actual = base_size[1]
            else:
                actual = item_height

            lo, hi = ref_range
            if not (lo <= actual <= hi):
                violations.append(
                    f"{room_type}/{item_type}: {ref_dimension} = {actual} "
                    f"outside [{lo}, {hi}]"
                )

    return violations


# ---------------------------------------------------------------------------
# Storytelling Props (AAA-05)
# ---------------------------------------------------------------------------

_STORYTELLING_PROPS: dict[str, dict] = {
    "cobwebs": {"placement": "corner", "density": 0.3},
    "bloodstains": {"placement": "floor_random", "density": 0.1},
    "scattered_papers": {"placement": "near_table", "density": 0.2},
    "broken_pottery": {"placement": "floor_random", "density": 0.15},
    "dust_piles": {"placement": "corner", "density": 0.2},
    "candle_stubs": {"placement": "near_table", "density": 0.25},
    "wall_cracks": {"placement": "wall", "density": 0.15},
    "rat_bones": {"placement": "corner", "density": 0.05},
}

# Room-type density modifiers: multiply base density by these factors.
# Missing rooms get factor 1.0 (neutral).
_ROOM_PROP_MODIFIERS: dict[str, dict[str, float]] = {
    "crypt": {
        "cobwebs": 2.0,
        "rat_bones": 3.0,
        "dust_piles": 2.0,
        "bloodstains": 0.5,
        "scattered_papers": 0.2,
    },
    "kitchen": {
        "bloodstains": 0.1,
        "broken_pottery": 2.0,
        "scattered_papers": 0.3,
    },
    "library": {
        "scattered_papers": 3.0,
        "candle_stubs": 2.0,
        "broken_pottery": 0.3,
        "bloodstains": 0.1,
    },
    "torture_chamber": {
        "bloodstains": 3.0,
        "rat_bones": 2.0,
        "cobwebs": 1.5,
    },
    "dining_hall": {
        "broken_pottery": 1.5,
        "candle_stubs": 2.0,
        "bloodstains": 0.2,
    },
    "treasury": {
        "dust_piles": 2.0,
        "cobwebs": 1.5,
        "bloodstains": 0.1,
        "scattered_papers": 0.5,
    },
    "alchemy_lab": {
        "broken_pottery": 2.5,
        "scattered_papers": 2.0,
        "candle_stubs": 1.5,
    },
    "guard_barracks": {
        "scattered_papers": 0.5,
        "dust_piles": 0.5,
    },
}


def add_storytelling_props(
    room_type: str,
    room_width: float,
    room_depth: float,
    density_modifier: float = 1.0,
    seed: int = 0,
) -> list[dict]:
    """Generate storytelling prop placements for a room.

    Returns list of dicts with: prop_type, position (x, y, z), placement_rule.
    Different room types produce different prop distributions via modifiers.
    """
    rng = random.Random(seed)
    props: list[dict] = []

    modifiers = _ROOM_PROP_MODIFIERS.get(room_type, {})

    for prop_name, prop_info in _STORYTELLING_PROPS.items():
        base_density = prop_info["density"]
        room_mod = modifiers.get(prop_name, 1.0)
        effective_density = base_density * room_mod * density_modifier

        # Number of this prop type to place (Poisson-like: density * area factor)
        expected_count = effective_density * 3  # 3 = nominal area factor
        count = 0
        for _ in range(max(1, int(expected_count + 1))):
            if rng.random() < effective_density:
                count += 1

        placement = prop_info["placement"]
        for _ in range(count):
            if placement == "corner":
                # Pick a corner with slight offset
                cx = rng.choice([0.3, room_width - 0.3])
                cy = rng.choice([0.3, room_depth - 0.3])
            elif placement == "floor_random":
                cx = rng.uniform(0.5, room_width - 0.5)
                cy = rng.uniform(0.5, room_depth - 0.5)
            elif placement == "near_table":
                # Center area where tables typically are
                cx = rng.uniform(room_width * 0.25, room_width * 0.75)
                cy = rng.uniform(room_depth * 0.25, room_depth * 0.75)
            elif placement == "wall":
                wall = rng.randint(0, 3)
                if wall == 0:
                    cx = rng.uniform(0.5, room_width - 0.5)
                    cy = 0.1
                elif wall == 1:
                    cx = rng.uniform(0.5, room_width - 0.5)
                    cy = room_depth - 0.1
                elif wall == 2:
                    cx = 0.1
                    cy = rng.uniform(0.5, room_depth - 0.5)
                else:
                    cx = room_width - 0.1
                    cy = rng.uniform(0.5, room_depth - 0.5)
            else:
                cx = rng.uniform(0.5, room_width - 0.5)
                cy = rng.uniform(0.5, room_depth - 0.5)

            props.append({
                "prop_type": prop_name,
                "position": [round(cx, 4), round(cy, 4), 0.0],
                "placement_rule": placement,
            })

    return props


# ---------------------------------------------------------------------------
# Overrun Variant (WORLD-09)
# ---------------------------------------------------------------------------

# Types of narrative debris added by overrun generation
_OVERRUN_DEBRIS_TYPES = [
    "rubble_pile", "fallen_beam", "collapsed_wall_section",
    "broken_furniture", "shattered_crate",
]

_OVERRUN_VEGETATION_TYPES = [
    "ivy_growth", "moss_patch", "vine_curtain",
    "root_intrusion", "mushroom_cluster", "fern_growth",
]

_OVERRUN_REMAINS_TYPES = [
    "scattered_bones", "torn_banner", "rusted_weapon",
    "broken_shield", "skull", "tattered_cloth",
]


def generate_overrun_variant(
    layout: list[dict],
    room_width: float,
    room_depth: float,
    corruption_level: float = 0.5,
    seed: int = 0,
) -> list[dict]:
    """Generate an overrun variant of an existing interior layout.

    Extends *layout* with narrative debris, broken walls, vegetation, and
    scattered remains.  Higher *corruption_level* (0.0--1.0) produces more
    destruction.  The original furniture items are preserved but some may be
    marked as ``damaged``.

    Returns a new list combining original items + overrun additions.
    """
    rng = random.Random(seed)
    result: list[dict] = []

    # 1. Copy original items, optionally marking some as damaged
    for item in layout:
        item_copy = dict(item)
        if rng.random() < corruption_level * 0.6:
            item_copy["damaged"] = True
        result.append(item_copy)

    # 2. Add debris (scales with corruption)
    n_debris = max(1, int(corruption_level * 8))
    for _ in range(n_debris):
        debris_type = rng.choice(_OVERRUN_DEBRIS_TYPES)
        result.append({
            "type": debris_type,
            "position": [
                round(rng.uniform(0.3, room_width - 0.3), 4),
                round(rng.uniform(0.3, room_depth - 0.3), 4),
                0.0,
            ],
            "rotation": round(rng.uniform(0, math.pi * 2), 4),
            "scale": [
                round(rng.uniform(0.3, 1.0), 4),
                round(rng.uniform(0.3, 1.0), 4),
                round(rng.uniform(0.1, 0.5), 4),
            ],
            "role": "debris",
        })

    # 3. Add broken wall segments (high corruption only)
    if corruption_level >= 0.3:
        n_walls = max(1, int(corruption_level * 4))
        for _ in range(n_walls):
            wall = rng.randint(0, 3)
            if wall == 0:
                wx = rng.uniform(0.5, room_width - 0.5)
                wy = 0.0
            elif wall == 1:
                wx = rng.uniform(0.5, room_width - 0.5)
                wy = room_depth
            elif wall == 2:
                wx = 0.0
                wy = rng.uniform(0.5, room_depth - 0.5)
            else:
                wx = room_width
                wy = rng.uniform(0.5, room_depth - 0.5)
            result.append({
                "type": "broken_wall",
                "position": [round(wx, 4), round(wy, 4), 0.0],
                "rotation": 0.0,
                "scale": [
                    round(rng.uniform(1.0, 2.5), 4),
                    round(rng.uniform(0.2, 0.5), 4),
                    round(rng.uniform(0.5, 2.0), 4),
                ],
                "role": "broken_wall",
            })

    # 4. Add vegetation overgrowth (moderate+ corruption)
    if corruption_level >= 0.4:
        n_veg = max(1, int(corruption_level * 6))
        for _ in range(n_veg):
            veg_type = rng.choice(_OVERRUN_VEGETATION_TYPES)
            result.append({
                "type": veg_type,
                "position": [
                    round(rng.uniform(0.2, room_width - 0.2), 4),
                    round(rng.uniform(0.2, room_depth - 0.2), 4),
                    0.0,
                ],
                "rotation": round(rng.uniform(0, math.pi * 2), 4),
                "scale": [
                    round(rng.uniform(0.3, 1.2), 4),
                    round(rng.uniform(0.3, 1.2), 4),
                    round(rng.uniform(0.2, 1.0), 4),
                ],
                "role": "vegetation",
            })

    # 5. Add scattered remains
    n_remains = max(1, int(corruption_level * 5))
    for _ in range(n_remains):
        remains_type = rng.choice(_OVERRUN_REMAINS_TYPES)
        result.append({
            "type": remains_type,
            "position": [
                round(rng.uniform(0.5, room_width - 0.5), 4),
                round(rng.uniform(0.5, room_depth - 0.5), 4),
                0.0,
            ],
            "rotation": round(rng.uniform(0, math.pi * 2), 4),
            "scale": [
                round(rng.uniform(0.2, 0.6), 4),
                round(rng.uniform(0.2, 0.6), 4),
                round(rng.uniform(0.05, 0.2), 4),
            ],
            "role": "remains",
        })

    return result
