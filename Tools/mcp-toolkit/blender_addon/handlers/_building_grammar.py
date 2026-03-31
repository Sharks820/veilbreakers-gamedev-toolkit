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
# Facade grammar
# ---------------------------------------------------------------------------


FACADE_STYLE_RULES: dict[str, dict[str, float | int | bool | str]] = {
    "medieval": {
        "plinth_height": 0.42,
        "plinth_projection": 0.16,
        "stringcourse_height": 0.14,
        "cornice_height": 0.28,
        "bay_divisor": 3,
        "pilaster_width": 0.28,
        "pilaster_depth": 0.15,
        "opening_frame": 0.12,
        "sill_height": 0.08,
        "lintel_height": 0.1,
        "has_balcony": 1,
        "has_awning": 1,
        "has_shutters": 1,
        "has_buttress": 0,
    },
    "gothic": {
        "plinth_height": 0.56,
        "plinth_projection": 0.22,
        "stringcourse_height": 0.18,
        "cornice_height": 0.34,
        "bay_divisor": 4,
        "pilaster_width": 0.34,
        "pilaster_depth": 0.18,
        "opening_frame": 0.14,
        "sill_height": 0.09,
        "lintel_height": 0.16,
        "has_balcony": 0,
        "has_awning": 0,
        "has_shutters": 0,
        "has_buttress": 1,
    },
    "rustic": {
        "plinth_height": 0.3,
        "plinth_projection": 0.12,
        "stringcourse_height": 0.1,
        "cornice_height": 0.22,
        "bay_divisor": 2,
        "pilaster_width": 0.22,
        "pilaster_depth": 0.1,
        "opening_frame": 0.08,
        "sill_height": 0.06,
        "lintel_height": 0.08,
        "has_balcony": 0,
        "has_awning": 0,
        "has_shutters": 1,
        "has_buttress": 0,
    },
    "fortress": {
        "plinth_height": 0.78,
        "plinth_projection": 0.24,
        "stringcourse_height": 0.18,
        "cornice_height": 0.42,
        "bay_divisor": 5,
        "pilaster_width": 0.42,
        "pilaster_depth": 0.24,
        "opening_frame": 0.16,
        "sill_height": 0.06,
        "lintel_height": 0.14,
        "has_balcony": 0,
        "has_awning": 0,
        "has_shutters": 0,
        "has_buttress": 1,
    },
    "organic": {
        "plinth_height": 0.38,
        "plinth_projection": 0.1,
        "stringcourse_height": 0.08,
        "cornice_height": 0.18,
        "bay_divisor": 3,
        "pilaster_width": 0.24,
        "pilaster_depth": 0.08,
        "opening_frame": 0.08,
        "sill_height": 0.04,
        "lintel_height": 0.08,
        "has_balcony": 0,
        "has_awning": 0,
        "has_shutters": 0,
        "has_buttress": 0,
    },
}


def _add_facade_box(
    modules: list[dict],
    *,
    role: str,
    material: str,
    position: tuple[float, float, float],
    size: tuple[float, float, float],
    wall: str,
    anchor: str | None = None,
) -> None:
    """Append a facade box module when all dimensions are positive."""
    if min(size) <= 0.0:
        return
    modules.append({
        "type": "box",
        "role": role,
        "material": material,
        "position": [round(position[0], 4), round(position[1], 4), round(position[2], 4)],
        "size": [round(size[0], 4), round(size[1], 4), round(size[2], 4)],
        "wall": wall,
        "anchor": anchor,
    })


def _bay_guides(length: float, bay_count: int) -> list[float]:
    """Return normalized bay guide positions along a wall length."""
    if bay_count <= 1:
        return [length * 0.5]
    return [length * (idx / bay_count) for idx in range(1, bay_count)]


def plan_modular_facade(
    width: float,
    depth: float,
    floors: int,
    style: str,
    *,
    wall_height: float,
    wall_thickness: float,
    openings: list[dict] | None = None,
    site_profile: str = "",
    seed: int = 0,
) -> dict[str, object]:
    """Plan facade modules that enrich a procedural building shell.

    Returns a deterministic module list using the building's local space,
    where the shell root is still corner-based (0..width, 0..depth).
    """
    rng = random.Random(seed)
    rules = FACADE_STYLE_RULES.get(style, FACADE_STYLE_RULES["medieval"])
    openings = list(openings or [])
    site_profile = str(site_profile or "").strip().lower()
    total_height = wall_height * max(1, floors)
    frame_depth = max(0.06, float(rules["opening_frame"]))
    band_depth = max(0.06, float(rules["plinth_projection"]))
    pilaster_w = max(0.16, float(rules["pilaster_width"]))
    pilaster_depth = max(0.06, float(rules["pilaster_depth"]))
    modules: list[dict] = []
    wall_material = STYLE_CONFIGS[style]["walls"]["material"]
    foundation_material = STYLE_CONFIGS[style]["foundation"]["material"]
    roof_material = STYLE_CONFIGS[style]["roof"]["material"]

    def _wall_span(wall_name: str) -> float:
        return width if wall_name in {"front", "back"} else max(0.0, depth - 2.0 * wall_thickness)

    # Base plinth bands
    plinth_h = min(total_height * 0.3, float(rules["plinth_height"]))
    _add_facade_box(
        modules,
        role="facade_plinth",
        material=foundation_material,
        position=(0.0, -band_depth, 0.0),
        size=(width, band_depth + wall_thickness * 0.4, plinth_h),
        wall="front",
    )
    _add_facade_box(
        modules,
        role="facade_plinth",
        material=foundation_material,
        position=(0.0, depth - wall_thickness * 0.4, 0.0),
        size=(width, band_depth + wall_thickness * 0.4, plinth_h),
        wall="back",
    )
    _add_facade_box(
        modules,
        role="facade_plinth",
        material=foundation_material,
        position=(-band_depth, wall_thickness, 0.0),
        size=(band_depth + wall_thickness * 0.4, max(0.0, depth - 2.0 * wall_thickness), plinth_h),
        wall="left",
    )
    _add_facade_box(
        modules,
        role="facade_plinth",
        material=foundation_material,
        position=(width - wall_thickness * 0.4, wall_thickness, 0.0),
        size=(band_depth + wall_thickness * 0.4, max(0.0, depth - 2.0 * wall_thickness), plinth_h),
        wall="right",
    )

    # Stringcourses between floors and cornice at the top.
    course_h = max(0.06, float(rules["stringcourse_height"]))
    for floor_idx in range(1, max(1, floors)):
        z = floor_idx * wall_height - course_h * 0.5
        for wall_name in ("front", "back"):
            y = -band_depth * 0.35 if wall_name == "front" else depth - wall_thickness * 0.25
            _add_facade_box(
                modules,
                role="facade_stringcourse",
                material=foundation_material,
                position=(0.0, y, z),
                size=(width, band_depth * 0.8 + wall_thickness * 0.35, course_h),
                wall=wall_name,
            )
        for wall_name, x in (("left", -band_depth * 0.35), ("right", width - wall_thickness * 0.25)):
            _add_facade_box(
                modules,
                role="facade_stringcourse",
                material=foundation_material,
                position=(x, wall_thickness, z),
                size=(band_depth * 0.8 + wall_thickness * 0.35, max(0.0, depth - 2.0 * wall_thickness), course_h),
                wall=wall_name,
            )

    cornice_h = max(0.12, float(rules["cornice_height"]))
    cornice_z = max(0.0, total_height - cornice_h)
    for wall_name in ("front", "back"):
        y = -band_depth * 0.45 if wall_name == "front" else depth - wall_thickness * 0.3
        _add_facade_box(
            modules,
            role="facade_cornice",
            material=roof_material,
            position=(0.0, y, cornice_z),
            size=(width, band_depth + wall_thickness * 0.45, cornice_h),
            wall=wall_name,
        )
    for wall_name, x in (("left", -band_depth * 0.45), ("right", width - wall_thickness * 0.3)):
        _add_facade_box(
            modules,
            role="facade_cornice",
            material=roof_material,
            position=(x, wall_thickness, cornice_z),
            size=(band_depth + wall_thickness * 0.45, max(0.0, depth - 2.0 * wall_thickness), cornice_h),
            wall=wall_name,
        )

    # Corner pilasters / quoins
    corner_specs = (
        ("front", (0.0, -pilaster_depth, plinth_h * 0.1)),
        ("front", (width - pilaster_w, -pilaster_depth, plinth_h * 0.1)),
        ("back", (0.0, depth - wall_thickness * 0.2, plinth_h * 0.1)),
        ("back", (width - pilaster_w, depth - wall_thickness * 0.2, plinth_h * 0.1)),
        ("left", (-pilaster_depth, wall_thickness, plinth_h * 0.1)),
        ("left", (-pilaster_depth, depth - wall_thickness - pilaster_w, plinth_h * 0.1)),
        ("right", (width - wall_thickness * 0.2, wall_thickness, plinth_h * 0.1)),
        ("right", (width - wall_thickness * 0.2, depth - wall_thickness - pilaster_w, plinth_h * 0.1)),
    )
    for wall_name, pos in corner_specs:
        size = (
            pilaster_w if wall_name in {"front", "back"} else pilaster_depth + wall_thickness * 0.35,
            pilaster_depth + wall_thickness * 0.35 if wall_name in {"front", "back"} else pilaster_w,
            max(0.6, total_height - cornice_h * 0.4),
        )
        _add_facade_box(
            modules,
            role="facade_pilaster",
            material=foundation_material,
            position=pos,
            size=size,
            wall=wall_name,
            anchor="corner",
        )

    openings_by_wall: dict[str, list[dict]] = {"front": [], "back": [], "left": [], "right": []}
    for opening in openings:
        wall_name = str(opening.get("wall", "front")).strip().lower()
        if wall_name in openings_by_wall:
            openings_by_wall[wall_name].append(opening)

    # Rhythm pilasters and opening trims.
    for wall_name, wall_openings in openings_by_wall.items():
        span = _wall_span(wall_name)
        if span <= 0.0:
            continue
        bay_count = max(2, int(rules["bay_divisor"]))
        if wall_openings:
            bay_count = max(bay_count, min(6, len(wall_openings) + 1))
        for guide in _bay_guides(span, bay_count):
            if any(abs(float(op.get("center", 0.0)) - guide) < max(0.8, pilaster_w * 1.4) for op in wall_openings):
                continue
            if wall_name == "front":
                pos = (max(0.0, min(width - pilaster_w, guide - pilaster_w * 0.5)), -pilaster_depth * 0.8, plinth_h)
                size = (pilaster_w, pilaster_depth + wall_thickness * 0.35, max(0.5, total_height - cornice_h - plinth_h))
            elif wall_name == "back":
                pos = (max(0.0, min(width - pilaster_w, guide - pilaster_w * 0.5)), depth - wall_thickness * 0.2, plinth_h)
                size = (pilaster_w, pilaster_depth + wall_thickness * 0.35, max(0.5, total_height - cornice_h - plinth_h))
            elif wall_name == "left":
                pos = (-pilaster_depth * 0.8, wall_thickness + max(0.0, min(span - pilaster_w, guide - pilaster_w * 0.5)), plinth_h)
                size = (pilaster_depth + wall_thickness * 0.35, pilaster_w, max(0.5, total_height - cornice_h - plinth_h))
            else:
                pos = (width - wall_thickness * 0.2, wall_thickness + max(0.0, min(span - pilaster_w, guide - pilaster_w * 0.5)), plinth_h)
                size = (pilaster_depth + wall_thickness * 0.35, pilaster_w, max(0.5, total_height - cornice_h - plinth_h))
            _add_facade_box(
                modules,
                role="facade_pilaster",
                material=foundation_material,
                position=pos,
                size=size,
                wall=wall_name,
                anchor="bay",
            )

        for opening in wall_openings:
            center = float(opening.get("center", 0.0))
            base_z = float(opening.get("world_bottom", opening.get("bottom", 0.0)))
            o_width = float(opening.get("width", 1.0))
            o_height = float(opening.get("height", 1.0))
            half_w = o_width * 0.5
            surround_w = o_width + frame_depth * 2.0
            surround_h = o_height + frame_depth * 2.0
            anchor = opening.get("kind", "window")
            if wall_name == "front":
                _add_facade_box(
                    modules,
                    role="facade_surround",
                    material=foundation_material,
                    position=(center - surround_w * 0.5, -frame_depth, base_z - frame_depth),
                    size=(surround_w, frame_depth + wall_thickness * 0.35, surround_h),
                    wall=wall_name,
                    anchor=anchor,
                )
                _add_facade_box(
                    modules,
                    role="facade_sill",
                    material=foundation_material,
                    position=(center - half_w - frame_depth * 0.8, -frame_depth * 1.2, max(0.0, base_z - float(rules["sill_height"]))),
                    size=(o_width + frame_depth * 1.6, frame_depth + wall_thickness * 0.2, float(rules["sill_height"])),
                    wall=wall_name,
                    anchor=anchor,
                )
                _add_facade_box(
                    modules,
                    role="facade_lintel",
                    material=foundation_material,
                    position=(center - half_w - frame_depth * 0.6, -frame_depth * 1.2, base_z + o_height),
                    size=(o_width + frame_depth * 1.2, frame_depth + wall_thickness * 0.2, float(rules["lintel_height"])),
                    wall=wall_name,
                    anchor=anchor,
                )
            elif wall_name == "back":
                _add_facade_box(
                    modules,
                    role="facade_surround",
                    material=foundation_material,
                    position=(center - surround_w * 0.5, depth - wall_thickness * 0.2, base_z - frame_depth),
                    size=(surround_w, frame_depth + wall_thickness * 0.35, surround_h),
                    wall=wall_name,
                    anchor=anchor,
                )
            elif wall_name == "left":
                _add_facade_box(
                    modules,
                    role="facade_surround",
                    material=foundation_material,
                    position=(-frame_depth, wall_thickness + center - surround_w * 0.5, base_z - frame_depth),
                    size=(frame_depth + wall_thickness * 0.35, surround_w, surround_h),
                    wall=wall_name,
                    anchor=anchor,
                )
            else:
                _add_facade_box(
                    modules,
                    role="facade_surround",
                    material=foundation_material,
                    position=(width - wall_thickness * 0.2, wall_thickness + center - surround_w * 0.5, base_z - frame_depth),
                    size=(frame_depth + wall_thickness * 0.35, surround_w, surround_h),
                    wall=wall_name,
                    anchor=anchor,
                )

    if bool(rules["has_buttress"]):
        buttress_h = max(wall_height * 0.9, total_height * 0.42)
        for wall_name, position in (
            ("front", (0.18, -band_depth * 1.2, 0.0)),
            ("front", (width - 0.72, -band_depth * 1.2, 0.0)),
            ("back", (0.18, depth - wall_thickness * 0.25, 0.0)),
            ("back", (width - 0.72, depth - wall_thickness * 0.25, 0.0)),
        ):
            modules.append({
                "type": "buttress",
                "role": "facade_buttress",
                "material": foundation_material,
                "position": [round(position[0], 4), round(position[1], 4), round(position[2], 4)],
                "height": round(buttress_h, 4),
                "width": round(max(0.48, pilaster_w * 1.3), 4),
                "depth": round(max(0.56, pilaster_depth * 2.4), 4),
                "wall": wall_name,
            })

    if bool(rules["has_awning"]) and site_profile in {"market", "waterfront"}:
        awning_w = max(1.8, width * 0.28)
        awning_x = width * (0.52 if site_profile == "market" else 0.34) - awning_w * 0.5
        _add_facade_box(
            modules,
            role="facade_awning",
            material=roof_material,
            position=(max(0.2, awning_x), -0.55, min(total_height * 0.45, wall_height * 0.72)),
            size=(min(width - 0.4, awning_w), 0.5, 0.1),
            wall="front",
            anchor="shopfront",
        )

    if bool(rules["has_balcony"]) and floors >= 2:
        balcony_w = min(width * 0.36, max(1.8, width * 0.24))
        _add_facade_box(
            modules,
            role="facade_balcony",
            material=roof_material,
            position=(width * 0.5 - balcony_w * 0.5, -0.78, wall_height + 0.05),
            size=(balcony_w, 0.68, 0.12),
            wall="front",
            anchor="upper_front",
        )

    if style in {"medieval", "rustic"} or site_profile in {"rural", "market"}:
        chimney_x = width * (0.22 if rng.random() < 0.5 else 0.74)
        chimney_y = depth * (0.22 if rng.random() < 0.5 else 0.72)
        modules.append({
            "type": "chimney",
            "role": "facade_chimney",
            "material": foundation_material,
            "position": [round(chimney_x, 4), round(chimney_y, 4), round(total_height - 0.2, 4)],
            "height": round(max(1.2, wall_height * 0.7), 4),
            "width": round(max(0.42, pilaster_w * 1.4), 4),
            "depth": round(max(0.42, pilaster_w * 1.2), 4),
            "wall": "roof",
        })

    return {
        "style": style,
        "site_profile": site_profile,
        "module_count": len(modules),
        "modules": modules,
    }


# ---------------------------------------------------------------------------
# Detail geometry generation -- wires building_quality AAA generators
# ---------------------------------------------------------------------------


def _mesh_spec_to_op(
    mesh: dict,
    *,
    position: tuple[float, float, float],
    detail_type: str,
    material: str = "stone",
) -> dict:
    """Convert a building_quality MeshSpec dict into a BuildingSpec operation.

    Offsets all vertices by *position* so the detail sits at the correct
    world-space location within the building.
    """
    px, py, pz = position
    offset_verts = [
        (v[0] + px, v[1] + py, v[2] + pz)
        for v in mesh["vertices"]
    ]
    return {
        "type": "mesh_spec",
        "vertices": offset_verts,
        "faces": mesh["faces"],
        "material": material,
        "role": "detail",
        "detail_type": detail_type,
    }


def _generate_detail_operations(
    details: list[str],
    width: float,
    depth: float,
    roof_z: float,
    base_z: float,
    floors: int,
    floor_height: float,
    wall_thickness: float,
    style: str,
    rng: random.Random,
) -> list[dict]:
    """Generate AAA-quality detail geometry for a building.

    Uses building_quality generators to produce real geometry instead of
    placeholder 0.5m cubes.  Each detail type maps to a specific generator
    or inline geometry function.

    Returns a list of BuildingSpec operations (type='mesh_spec' with full
    vertex/face data, or standard box/cylinder ops).
    """
    from .building_quality import (
        generate_chimney,
        generate_gothic_window,
        generate_battlements,
        generate_archway,
    )

    ops: list[dict] = []

    for detail_name in details:

        if detail_name == "chimney":
            # Place chimney on roof near back wall
            cx = rng.uniform(width * 0.3, width * 0.7)
            cy = rng.uniform(depth * 0.5, depth * 0.8)
            chimney_style = "stone" if style in ("gothic", "fortress") else "brick"
            if style == "rustic":
                chimney_style = "rustic"
            mesh = generate_chimney(
                height=rng.uniform(1.5, 2.5),
                style=chimney_style,
                chimney_width=rng.uniform(0.4, 0.6),
                chimney_depth=rng.uniform(0.4, 0.6),
                seed=rng.randint(0, 99999),
            )
            ops.append(_mesh_spec_to_op(
                mesh, position=(cx, cy, roof_z),
                detail_type="chimney", material="stone_dark",
            ))

        elif detail_name == "timber_frame":
            # Add timber frame overlay on front and back walls per floor
            for floor_idx in range(floors):
                floor_z = base_z + floor_idx * floor_height
                # Front wall timber overlay
                _add_timber_frame_detail(
                    ops, 0.0, 0.0, floor_z,
                    width, floor_height, wall_thickness,
                    rng, "front",
                )
                # Back wall
                _add_timber_frame_detail(
                    ops, 0.0, depth - wall_thickness, floor_z,
                    width, floor_height, wall_thickness,
                    rng, "back",
                )

        elif detail_name == "window_boxes":
            # Planter boxes under windows on front wall
            bay_count = max(2, int(width / 2.0))
            spacing = width / (bay_count + 1)
            for bi in range(bay_count):
                bx = spacing * (bi + 1) - 0.3
                bz = base_z + floor_height * 0.35
                _add_window_box_detail(ops, bx, -0.15, bz, rng)

        elif detail_name == "flying_buttress":
            # Gothic flying buttresses on side walls
            butt_count = max(2, int(depth / 3.0))
            spacing = depth / (butt_count + 1)
            total_h = base_z + floors * floor_height
            for bi in range(butt_count):
                by = spacing * (bi + 1)
                # Left side buttress
                _add_flying_buttress_detail(
                    ops, -0.1, by, base_z, total_h, rng,
                )
                # Right side buttress
                _add_flying_buttress_detail(
                    ops, width + 0.1, by, base_z, total_h, rng,
                )

        elif detail_name == "gargoyle":
            # Gargoyles perched on corners at roof line
            gargoyle_positions = [
                (0.0, 0.0), (width, 0.0),
                (0.0, depth), (width, depth),
            ]
            for gx, gy in gargoyle_positions:
                if rng.random() < 0.6:  # not every corner
                    _add_gargoyle_detail(ops, gx, gy, roof_z, rng)

        elif detail_name == "rose_window":
            # Large circular window on front facade (upper floor)
            cx = width / 2.0
            cz = roof_z - floor_height * 0.4
            mesh = generate_gothic_window(
                width=min(1.5, width * 0.25),
                height=min(1.5, width * 0.25),
                style="rose_window",
                tracery=True,
                seed=rng.randint(0, 99999),
            )
            ops.append(_mesh_spec_to_op(
                mesh, position=(cx, -0.05, cz),
                detail_type="rose_window", material="stone_carved",
            ))

        elif detail_name == "spire":
            # Pointed spire on roof
            cx = width / 2.0
            cy = depth / 2.0
            _add_spire_detail(ops, cx, cy, roof_z, rng)

        elif detail_name == "battlement":
            # Crenellated parapet on fortress roofline
            mesh = generate_battlements(
                wall_length=width,
                wall_height=1.2,
                wall_thickness=wall_thickness * 0.8,
                merlon_style=rng.choice(["squared", "swallow_tail"]),
                has_machicolations=True,
                has_arrow_loops=False,
                seed=rng.randint(0, 99999),
            )
            # Front parapet
            ops.append(_mesh_spec_to_op(
                mesh, position=(0.0, 0.0, roof_z),
                detail_type="battlement", material="stone_fortified",
            ))
            # Back parapet
            ops.append(_mesh_spec_to_op(
                mesh, position=(0.0, depth - wall_thickness, roof_z),
                detail_type="battlement", material="stone_fortified",
            ))

        elif detail_name == "machicolation":
            # Machicolation corbels along front wall top
            corbel_count = max(3, int(width / 1.5))
            spacing = width / (corbel_count + 1)
            for ci in range(corbel_count):
                cx = spacing * (ci + 1)
                cz = roof_z - 0.3
                _add_machicolation_detail(ops, cx, -0.1, cz, rng)

        elif detail_name == "murder_hole":
            # Murder hole above door (ground floor ceiling)
            door_cx = width / 2.0
            mh_z = base_z + floor_height - 0.1
            ops.append({
                "type": "box",
                "position": [door_cx - 0.3, wall_thickness * 0.2, mh_z],
                "size": [0.6, wall_thickness * 0.6, 0.15],
                "material": "stone_dark",
                "role": "detail",
                "detail_type": "murder_hole",
            })

        elif detail_name == "vine_growth":
            # Organic vines climbing walls
            vine_count = rng.randint(2, 5)
            for _ in range(vine_count):
                vx = rng.uniform(0.2, width - 0.2)
                vy = rng.choice([0.0, depth])
                max_z = base_z + floors * floor_height
                _add_vine_detail(ops, vx, vy, base_z, max_z, rng)

        elif detail_name == "moss_patches":
            # Moss patches at base and joints
            patch_count = rng.randint(3, 8)
            for _ in range(patch_count):
                px = rng.uniform(0.0, width)
                py = rng.choice([0.0, depth])
                pz = rng.uniform(0.0, base_z + floor_height * 0.3)
                ops.append({
                    "type": "box",
                    "position": [px - 0.15, py - 0.02, pz],
                    "size": [rng.uniform(0.2, 0.5), 0.03, rng.uniform(0.1, 0.3)],
                    "material": "moss",
                    "role": "detail",
                    "detail_type": "moss_patch",
                })

        elif detail_name == "root_buttress":
            # Organic root supports at base
            root_count = rng.randint(2, 4)
            for _ in range(root_count):
                rx = rng.uniform(0.3, width - 0.3)
                ry = rng.choice([0.0, depth])
                _add_root_detail(ops, rx, ry, base_z, rng)

        elif detail_name == "woodpile":
            # Stacked logs against a wall
            wpx = rng.uniform(0.3, width - 1.0)
            wpy = rng.choice([-0.3, depth + 0.1])
            _add_woodpile_detail(ops, wpx, wpy, base_z, rng)

        else:
            # Fallback: small architectural accent box (better than 0.5m cube)
            detail_x = rng.uniform(0.3, width - 0.3)
            detail_y = rng.uniform(0.3, depth - 0.3)
            ops.append({
                "type": "box",
                "position": [detail_x, detail_y, roof_z],
                "size": [0.3, 0.3, rng.uniform(0.2, 0.6)],
                "material": detail_name,
                "role": "detail",
                "detail_type": detail_name,
            })

    return ops


def _add_timber_frame_detail(
    ops: list[dict],
    x0: float, y0: float, z0: float,
    width: float, height: float, thickness: float,
    rng: random.Random, wall_name: str,
) -> None:
    """Add half-timber frame beams to a wall section."""
    beam_w = 0.08
    beam_d = 0.04  # protrusion
    y_off = -beam_d if wall_name == "front" else thickness

    # Vertical posts at 1/3 intervals
    post_count = max(2, int(width / 2.0))
    spacing = width / post_count
    for pi in range(post_count + 1):
        px = x0 + pi * spacing
        ops.append({
            "type": "box",
            "position": [px - beam_w / 2, y0 + y_off, z0],
            "size": [beam_w, beam_d, height],
            "material": "timber",
            "role": "detail",
            "detail_type": "timber_post",
        })

    # Horizontal rails at top and mid
    for frac in [0.0, 0.5, 1.0]:
        rz = z0 + frac * height - beam_w / 2
        ops.append({
            "type": "box",
            "position": [x0, y0 + y_off, max(z0, rz)],
            "size": [width, beam_d, beam_w],
            "material": "timber",
            "role": "detail",
            "detail_type": "timber_rail",
        })

    # Diagonal braces in each bay (upper half)
    for pi in range(post_count):
        bx = x0 + pi * spacing + spacing * 0.1
        bz = z0 + height * 0.5
        ops.append({
            "type": "box",
            "position": [bx, y0 + y_off, bz],
            "size": [spacing * 0.8, beam_d, beam_w],
            "material": "timber",
            "role": "detail",
            "detail_type": "timber_brace",
        })


def _add_window_box_detail(
    ops: list[dict],
    x: float, y: float, z: float,
    rng: random.Random,
) -> None:
    """Add a planter box with vegetation cluster."""
    box_w = rng.uniform(0.5, 0.7)
    box_h = 0.12
    box_d = 0.15
    # Planter box
    ops.append({
        "type": "box",
        "position": [x, y, z],
        "size": [box_w, box_d, box_h],
        "material": "wood_planks",
        "role": "detail",
        "detail_type": "window_box",
    })
    # Vegetation cluster (small rounded mass above)
    ops.append({
        "type": "box",
        "position": [x + 0.05, y - 0.02, z + box_h],
        "size": [box_w - 0.1, box_d + 0.04, rng.uniform(0.08, 0.15)],
        "material": "vegetation",
        "role": "detail",
        "detail_type": "window_box_plants",
    })


def _add_flying_buttress_detail(
    ops: list[dict],
    x: float, y: float, z_base: float,
    building_height: float,
    rng: random.Random,
) -> None:
    """Add a gothic flying buttress with pier and arch strut."""
    pier_w = rng.uniform(0.25, 0.4)
    pier_d = rng.uniform(0.25, 0.35)
    pier_h = building_height * rng.uniform(0.7, 0.85)
    strut_h = 0.15

    # Pier (vertical pillar)
    sign = -1.0 if x < 0.5 else 1.0
    pier_x = x + sign * 0.5
    ops.append({
        "type": "box",
        "position": [pier_x - pier_w / 2, y - pier_d / 2, z_base],
        "size": [pier_w, pier_d, pier_h],
        "material": "stone_grey",
        "role": "detail",
        "detail_type": "buttress_pier",
    })
    # Pier cap (wider at top)
    ops.append({
        "type": "box",
        "position": [pier_x - pier_w * 0.7, y - pier_d * 0.7, z_base + pier_h],
        "size": [pier_w * 1.4, pier_d * 1.4, 0.1],
        "material": "stone_grey",
        "role": "detail",
        "detail_type": "buttress_cap",
    })
    # Angled strut connecting pier top to wall
    strut_w = pier_w * 0.6
    ops.append({
        "type": "box",
        "position": [min(x, pier_x) - 0.05, y - strut_w / 2,
                      z_base + pier_h * 0.6],
        "size": [abs(pier_x - x) + 0.1, strut_w, strut_h],
        "material": "stone_grey",
        "role": "detail",
        "detail_type": "buttress_strut",
    })
    # Pinnacle on top of pier
    pin_s = pier_w * 0.4
    ops.append({
        "type": "box",
        "position": [pier_x - pin_s / 2, y - pin_s / 2,
                      z_base + pier_h + 0.1],
        "size": [pin_s, pin_s, rng.uniform(0.3, 0.5)],
        "material": "stone_grey",
        "role": "detail",
        "detail_type": "buttress_pinnacle",
    })


def _add_gargoyle_detail(
    ops: list[dict],
    x: float, y: float, z: float,
    rng: random.Random,
) -> None:
    """Add a gargoyle creature perched on a corner ledge."""
    # Base/perch (corbel)
    perch_w = 0.25
    perch_d = 0.3
    perch_h = 0.08
    # Direction: outward from corner
    dx = -0.15 if x < 1.0 else 0.15
    dy = -0.15 if y < 1.0 else 0.15
    ops.append({
        "type": "box",
        "position": [x + dx - perch_w / 2, y + dy - perch_d / 2, z - perch_h],
        "size": [perch_w, perch_d, perch_h],
        "material": "stone_carved",
        "role": "detail",
        "detail_type": "gargoyle_perch",
    })
    # Body (hunched creature torso)
    body_w = 0.18
    body_d = 0.22
    body_h = 0.2
    ops.append({
        "type": "box",
        "position": [x + dx - body_w / 2, y + dy - body_d / 2, z],
        "size": [body_w, body_d, body_h],
        "material": "stone_carved",
        "role": "detail",
        "detail_type": "gargoyle_body",
    })
    # Head (smaller, forward-facing)
    head_s = 0.1
    ops.append({
        "type": "box",
        "position": [x + dx - head_s / 2, y + dy * 1.5 - head_s / 2, z + body_h],
        "size": [head_s, head_s * 1.2, head_s],
        "material": "stone_carved",
        "role": "detail",
        "detail_type": "gargoyle_head",
    })
    # Wings (two angled plates)
    wing_w = 0.15
    wing_h = 0.15
    wing_d = 0.03
    for wing_side in [-1, 1]:
        ops.append({
            "type": "box",
            "position": [x + dx + wing_side * body_w * 0.5, y + dy,
                          z + body_h * 0.3],
            "size": [wing_w, wing_d, wing_h],
            "material": "stone_carved",
            "role": "detail",
            "detail_type": "gargoyle_wing",
        })


def _add_spire_detail(
    ops: list[dict],
    cx: float, cy: float, z: float,
    rng: random.Random,
) -> None:
    """Add a pointed spire (octagonal tapered tower)."""
    spire_h = rng.uniform(2.0, 4.0)
    base_r = rng.uniform(0.3, 0.5)
    # Build as stacked octagonal rings shrinking upward
    segments = 8
    rings = 6
    for ri in range(rings):
        frac = ri / rings
        next_frac = (ri + 1) / rings
        r0 = base_r * (1.0 - frac * 0.9)
        r1 = base_r * (1.0 - next_frac * 0.9)
        z0 = z + frac * spire_h
        ring_h = spire_h / rings
        # Approximate each ring as a box (octagon approximation)
        ops.append({
            "type": "box",
            "position": [cx - r0, cy - r0, z0],
            "size": [r0 * 2, r0 * 2, ring_h],
            "material": "slate",
            "role": "detail",
            "detail_type": "spire_ring",
        })
    # Finial at top
    ops.append({
        "type": "box",
        "position": [cx - 0.03, cy - 0.03, z + spire_h],
        "size": [0.06, 0.06, 0.2],
        "material": "iron",
        "role": "detail",
        "detail_type": "spire_finial",
    })


def _add_machicolation_detail(
    ops: list[dict],
    x: float, y: float, z: float,
    rng: random.Random,
) -> None:
    """Add a single machicolation corbel."""
    corbel_w = 0.2
    corbel_d = 0.25
    corbel_h = 0.15
    # Corbel bracket
    ops.append({
        "type": "box",
        "position": [x - corbel_w / 2, y, z],
        "size": [corbel_w, corbel_d, corbel_h],
        "material": "stone_fortified",
        "role": "detail",
        "detail_type": "machicolation_corbel",
    })
    # Platform on top
    ops.append({
        "type": "box",
        "position": [x - corbel_w * 0.7, y - 0.05, z + corbel_h],
        "size": [corbel_w * 1.4, corbel_d + 0.1, 0.08],
        "material": "stone_fortified",
        "role": "detail",
        "detail_type": "machicolation_platform",
    })


def _add_vine_detail(
    ops: list[dict],
    x: float, y: float, z_base: float, z_top: float,
    rng: random.Random,
) -> None:
    """Add climbing vine geometry along a wall."""
    vine_w = 0.04
    vine_d = 0.03
    height = (z_top - z_base) * rng.uniform(0.3, 0.8)
    # Main stem
    ops.append({
        "type": "box",
        "position": [x - vine_w / 2, y - vine_d, z_base],
        "size": [vine_w, vine_d, height],
        "material": "vine",
        "role": "detail",
        "detail_type": "vine_stem",
    })
    # Leaf clusters along stem
    leaf_count = max(2, int(height / 0.4))
    for li in range(leaf_count):
        lz = z_base + (li + 0.5) * height / leaf_count
        lx_off = rng.uniform(-0.12, 0.12)
        ops.append({
            "type": "box",
            "position": [x + lx_off - 0.06, y - vine_d - 0.01, lz],
            "size": [0.12, 0.02, rng.uniform(0.06, 0.12)],
            "material": "leaf",
            "role": "detail",
            "detail_type": "vine_leaves",
        })


def _add_root_detail(
    ops: list[dict],
    x: float, y: float, z_base: float,
    rng: random.Random,
) -> None:
    """Add an organic root/tendril at the building base."""
    root_w = rng.uniform(0.06, 0.15)
    root_d = rng.uniform(0.1, 0.2)
    root_h = rng.uniform(0.3, 0.8)
    dy = -root_d if y < 0.5 else 0.0
    ops.append({
        "type": "box",
        "position": [x - root_w / 2, y + dy, z_base],
        "size": [root_w, root_d, root_h],
        "material": "root",
        "role": "detail",
        "detail_type": "root_support",
    })
    # Root tip curving outward
    ops.append({
        "type": "box",
        "position": [x - root_w * 0.3, y + dy - 0.05, z_base],
        "size": [root_w * 0.6, root_d + 0.1, root_w],
        "material": "root",
        "role": "detail",
        "detail_type": "root_tip",
    })


def _add_woodpile_detail(
    ops: list[dict],
    x: float, y: float, z_base: float,
    rng: random.Random,
) -> None:
    """Add a stack of logs against a wall."""
    log_count = rng.randint(4, 8)
    log_r = 0.06
    stack_w = rng.uniform(0.6, 1.0)
    for li in range(log_count):
        row = li // 3
        col = li % 3
        lx = x + col * (log_r * 2.2)
        lz = z_base + row * (log_r * 2.1)
        ops.append({
            "type": "box",
            "position": [lx, y, lz],
            "size": [log_r * 2, 0.4, log_r * 2],
            "material": "wood_log",
            "role": "detail",
            "detail_type": "woodpile_log",
        })


# ---------------------------------------------------------------------------
# Roof generation -- wires building_quality.generate_roof()
# ---------------------------------------------------------------------------

# Mapping from STYLE_CONFIGS roof type to building_quality roof style
_ROOF_TYPE_MAP: dict[str, str] = {
    "gabled": "gable",
    "pointed": "hip",
    "flat": "flat",
    "domed": "conical_tower",
    "mansard": "mansard",
    "gambrel": "gambrel",
    "shed": "shed",
}

# Mapping from STYLE_CONFIGS roof material to building_quality material
_ROOF_MATERIAL_MAP: dict[str, str] = {
    "thatch": "thatch",
    "thatch_worn": "thatch",
    "slate": "slate",
    "stone_parapet": "tile",
    "living_thatch": "thatch",
    "tile": "tile",
    "shingle": "shingle",
}


def _generate_roof_operations(
    width: float,
    depth: float,
    roof_z: float,
    roof_cfg: dict,
    style: str,
    rng: random.Random,
) -> list[dict]:
    """Generate AAA roof geometry using building_quality.generate_roof().

    Produces a mesh_spec operation with individual tiles/shingles, ridge tiles,
    fascia, gable ends, and rafters -- instead of a flat box placeholder.

    Falls back to simple box for unknown roof types.
    """
    from .building_quality import generate_roof

    roof_type = roof_cfg.get("type", "gabled")
    overhang = roof_cfg.get("overhang", 0.3)
    pitch = roof_cfg.get("pitch", 35)
    material_key = roof_cfg.get("material", "tile")

    # Map to building_quality parameters
    bq_style = _ROOF_TYPE_MAP.get(roof_type, "gable")
    bq_material = _ROOF_MATERIAL_MAP.get(material_key, "tile")

    # Handle domed specially -- keep as cylinder for now
    if roof_type == "domed":
        return [{
            "type": "cylinder",
            "position": [width / 2, depth / 2, roof_z],
            "radius": min(width, depth) / 2,
            "height": min(width, depth) / 3,
            "segments": 16,
            "material": material_key,
            "role": "roof",
            "roof_type": "domed",
        }]

    # Generate AAA roof mesh
    mesh = generate_roof(
        width=width,
        depth=depth,
        pitch=pitch,
        style=bq_style,
        material=bq_material,
        overhang=overhang,
        seed=rng.randint(0, 99999),
    )

    # Offset roof vertices to sit at roof_z height, centered on building
    # generate_roof() produces geometry centered at origin, x spans -half_w to half_w
    # We need to shift: x += width/2 (center to corner-origin), z += roof_z
    ops: list[dict] = []
    offset_verts = [
        (v[0] + width / 2.0, v[1] + depth / 2.0, v[2] + roof_z)
        for v in mesh["vertices"]
    ]

    ops.append({
        "type": "mesh_spec",
        "vertices": offset_verts,
        "faces": mesh["faces"],
        "material": material_key,
        "role": "roof",
        "roof_type": bq_style,
        "detail_type": "roof_tiles",
    })

    # Also keep a simplified roof bounding box for collision/raycasting reference
    ridge_height = math.tan(math.radians(pitch)) * (width / 2 + overhang)
    ops.append({
        "type": "box",
        "position": [-overhang, -overhang, roof_z],
        "size": [width + 2 * overhang, depth + 2 * overhang, 0.05],
        "material": material_key,
        "role": "roof_base",
        "roof_type": bq_style,
        "ridge_height": ridge_height,
    })

    return ops


# ---------------------------------------------------------------------------
# CGA-style facade split grammar
# ---------------------------------------------------------------------------

# Bay fill types with their probability weights per floor context
_BAY_FILL_TYPES = {
    "ground": {
        "window": 0.4,
        "door": 0.15,
        "wall_panel": 0.3,
        "balcony": 0.0,
        "archway": 0.15,
    },
    "upper": {
        "window": 0.55,
        "door": 0.0,
        "wall_panel": 0.2,
        "balcony": 0.15,
        "archway": 0.1,
    },
    "top": {
        "window": 0.45,
        "door": 0.0,
        "wall_panel": 0.25,
        "balcony": 0.2,
        "archway": 0.1,
    },
}

# Style overrides for bay fill probabilities
_STYLE_BAY_OVERRIDES: dict[str, dict[str, dict[str, float]]] = {
    "fortress": {
        "ground": {"window": 0.2, "door": 0.1, "wall_panel": 0.5, "balcony": 0.0, "archway": 0.2},
        "upper": {"window": 0.3, "door": 0.0, "wall_panel": 0.5, "balcony": 0.0, "archway": 0.2},
        "top": {"window": 0.2, "door": 0.0, "wall_panel": 0.4, "balcony": 0.0, "archway": 0.4},
    },
    "gothic": {
        "ground": {"window": 0.5, "door": 0.15, "wall_panel": 0.15, "balcony": 0.0, "archway": 0.2},
        "upper": {"window": 0.65, "door": 0.0, "wall_panel": 0.1, "balcony": 0.05, "archway": 0.2},
        "top": {"window": 0.5, "door": 0.0, "wall_panel": 0.1, "balcony": 0.1, "archway": 0.3},
    },
    "rustic": {
        "ground": {"window": 0.3, "door": 0.2, "wall_panel": 0.5, "balcony": 0.0, "archway": 0.0},
        "upper": {"window": 0.4, "door": 0.0, "wall_panel": 0.5, "balcony": 0.1, "archway": 0.0},
        "top": {"window": 0.3, "door": 0.0, "wall_panel": 0.6, "balcony": 0.1, "archway": 0.0},
    },
    "organic": {
        "ground": {"window": 0.35, "door": 0.15, "wall_panel": 0.4, "balcony": 0.0, "archway": 0.1},
        "upper": {"window": 0.45, "door": 0.0, "wall_panel": 0.35, "balcony": 0.1, "archway": 0.1},
        "top": {"window": 0.35, "door": 0.0, "wall_panel": 0.45, "balcony": 0.1, "archway": 0.1},
    },
}


def _weighted_choice(options: dict[str, float], rng: random.Random) -> str:
    """Pick a key from *options* dict with weighted probabilities."""
    items = list(options.items())
    total = sum(w for _, w in items)
    if total <= 0:
        return items[0][0]
    r = rng.uniform(0, total)
    cumulative = 0.0
    for key, weight in items:
        cumulative += weight
        if r <= cumulative:
            return key
    return items[-1][0]


def _cga_facade_split(
    *,
    width: float,
    depth: float,
    floors: int,
    base_z: float,
    floor_height: float,
    slab_thickness: float,
    wall_thickness: float,
    win_cfg: dict,
    door_cfg: dict,
    facade_rules: dict,
    style: str,
    rng: random.Random,
) -> list[dict]:
    """CGA-style recursive facade split grammar.

    Pipeline: comp(faces) -> split(y, floors) -> split(x, bays) -> fill(rule)

    For each wall face of the building:
      1. Split vertically into floor bands
      2. Split each floor band horizontally into bays
      3. Fill each bay with a rule: window, door, wall_panel, balcony, archway
      4. Corner bays are always solid (structural)
      5. Ground floor gets at least one door on the front wall
      6. Windows are aligned across floors (same column positions)

    Returns list of BuildingSpec opening/detail operations.
    """
    ops: list[dict] = []

    # Determine bay count per wall (randomized within style range)
    base_bay = int(facade_rules.get("bay_divisor", 3))
    bay_variation = rng.randint(-1, 1)
    front_bays = max(2, base_bay + bay_variation)
    back_bays = max(2, base_bay + rng.randint(-1, 0))
    # Side walls get fewer bays
    side_bays = max(2, base_bay - 1 + rng.randint(-1, 0))

    # Randomize window dimensions within +/- 20%
    win_w = win_cfg["width"] * rng.uniform(0.8, 1.2)
    win_h = win_cfg["height"] * rng.uniform(0.8, 1.2)
    win_style = win_cfg["style"]

    # Get style-specific fill probabilities
    style_fills = _STYLE_BAY_OVERRIDES.get(style, _BAY_FILL_TYPES)

    # Pre-compute column positions for alignment across floors
    # Each wall gets its own column grid
    wall_configs = [
        {"wall_idx": 0, "length": width, "bays": front_bays, "is_front": True},
        {"wall_idx": 1, "length": width, "bays": back_bays, "is_front": False},
        {"wall_idx": 2, "length": depth - 2 * wall_thickness, "bays": side_bays, "is_front": False},
        {"wall_idx": 3, "length": depth - 2 * wall_thickness, "bays": side_bays, "is_front": False},
    ]

    # Track door placement -- ensure at least one on front wall
    door_placed = False

    for wc in wall_configs:
        wall_idx = wc["wall_idx"]
        wall_len = wc["length"]
        n_bays = wc["bays"]
        is_front = wc["is_front"]

        if wall_len < 1.0:
            continue

        # Compute bay column positions (consistent across floors for alignment)
        bay_width = wall_len / n_bays
        bay_centers = [bay_width * (i + 0.5) for i in range(n_bays)]

        # Select which bays are "fillable" (exclude corners)
        fillable_bays = list(range(n_bays))
        if n_bays >= 3:
            # Corner bays are solid wall panels
            fillable_bays = list(range(1, n_bays - 1))

        # Pre-select a door bay on the front wall ground floor
        door_bay_idx = -1
        if is_front and not door_placed:
            # Pick a bay near center for the door
            center_bay = len(fillable_bays) // 2
            if fillable_bays:
                door_bay_idx = fillable_bays[center_bay]
                # Allow off-center variation
                if len(fillable_bays) >= 3:
                    offset = rng.randint(-1, 1)
                    clamped = max(0, min(len(fillable_bays) - 1, center_bay + offset))
                    door_bay_idx = fillable_bays[clamped]

        # Split(y, floors) -- iterate floor bands
        for floor_idx in range(floors):
            floor_z = base_z + floor_idx * (floor_height + slab_thickness)

            # Determine floor context for fill rules
            if floor_idx == 0:
                floor_ctx = "ground"
            elif floor_idx == floors - 1:
                floor_ctx = "top"
            else:
                floor_ctx = "upper"

            fill_probs = style_fills.get(floor_ctx, _BAY_FILL_TYPES[floor_ctx])

            # Split(x, bays) -- iterate bay columns
            for bay_idx in range(n_bays):
                bay_x = bay_centers[bay_idx] - win_w / 2

                # Corner bays: always solid panel (no opening)
                if bay_idx not in fillable_bays:
                    continue

                # Ground floor front wall: place door in selected bay
                if floor_idx == 0 and is_front and bay_idx == door_bay_idx:
                    door_x = bay_centers[bay_idx] - door_cfg["width"] / 2
                    ops.append({
                        "type": "opening",
                        "wall_index": wall_idx,
                        "position": [door_x, 0.0],
                        "size": [door_cfg["width"], door_cfg["height"]],
                        "role": "door",
                        "floor": floor_idx,
                        "style": door_cfg["style"],
                        "bay_index": bay_idx,
                    })
                    door_placed = True
                    continue

                # Fill rule selection
                fill_type = _weighted_choice(fill_probs, rng)

                if fill_type == "window":
                    # Window at 35-45% wall height (slight per-bay variation)
                    win_y_frac = rng.uniform(0.35, 0.45)
                    win_y = floor_height * win_y_frac
                    ops.append({
                        "type": "opening",
                        "wall_index": wall_idx,
                        "position": [bay_x, win_y],
                        "size": [win_w, win_h],
                        "role": "window",
                        "floor": floor_idx,
                        "style": win_style,
                        "bay_index": bay_idx,
                    })

                elif fill_type == "balcony":
                    # Balcony: window + projecting platform
                    win_y = floor_height * 0.15  # lower for balcony access
                    ops.append({
                        "type": "opening",
                        "wall_index": wall_idx,
                        "position": [bay_x, win_y],
                        "size": [win_w * 1.2, win_h * 1.1],
                        "role": "window",
                        "floor": floor_idx,
                        "style": win_style,
                        "bay_index": bay_idx,
                    })

                elif fill_type == "archway":
                    # Archway: tall opening with arch profile
                    arch_w = win_w * 1.1
                    arch_h = win_h * 1.3
                    ops.append({
                        "type": "opening",
                        "wall_index": wall_idx,
                        "position": [bay_centers[bay_idx] - arch_w / 2, 0.0],
                        "size": [arch_w, arch_h],
                        "role": "window",
                        "floor": floor_idx,
                        "style": "pointed_arch" if style == "gothic" else "arched",
                        "bay_index": bay_idx,
                    })

                elif fill_type == "door" and floor_idx == 0:
                    # Secondary door (side/back entrance)
                    d_w = door_cfg["width"] * rng.uniform(0.8, 1.0)
                    d_h = door_cfg["height"] * rng.uniform(0.85, 1.0)
                    ops.append({
                        "type": "opening",
                        "wall_index": wall_idx,
                        "position": [bay_centers[bay_idx] - d_w / 2, 0.0],
                        "size": [d_w, d_h],
                        "role": "door",
                        "floor": floor_idx,
                        "style": door_cfg["style"],
                        "bay_index": bay_idx,
                    })

                # wall_panel: no opening (solid bay) -- intentionally no operation

    # Fallback: if no door was placed (very narrow building), force one
    if not door_placed:
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

    return ops


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
    -> CGA facade split -> detail operations.

    Variation system ensures no two buildings with different seeds look
    identical:
    - Per-floor height randomized within +/- 15%
    - Wall thickness varied +/- 10%
    - Random subset of style details selected
    - CGA split provides bay count, window size, fill type variation
    - Roof generation uses randomized seed
    """
    rng = random.Random(seed)
    config = STYLE_CONFIGS[style]

    ops: list[dict] = []

    # --- Variation: per-building parameter randomization ---
    base_floor_h = config["walls"]["height_per_floor"]
    base_wall_t = config["walls"]["thickness"]
    # Per-floor height variation (+/- 15%)
    floor_heights = [
        base_floor_h * rng.uniform(0.85, 1.15) for _ in range(floors)
    ]
    # Wall thickness variation (+/- 10%)
    wall_thickness_var = base_wall_t * rng.uniform(0.90, 1.10)

    # 1. Foundation
    fnd = config["foundation"]
    # Slight foundation height variation
    fnd_h = fnd["height"] * rng.uniform(0.9, 1.1)
    ops.append({
        "type": "box",
        "position": [-fnd["inset"], -fnd["inset"], 0.0],
        "size": [width + 2 * fnd["inset"], depth + 2 * fnd["inset"], fnd_h],
        "material": fnd["material"],
        "role": "foundation",
    })

    wall_cfg = config["walls"]
    slab_cfg = config["floor_slab"]
    base_z = fnd_h

    # 2. Walls per floor + 3. Floor slabs between floors
    cumulative_z = base_z
    for floor_idx in range(floors):
        floor_z = cumulative_z

        # Floor slab (between floors, not under ground floor)
        if floor_idx > 0:
            ops.append({
                "type": "box",
                "position": [0.0, 0.0, floor_z - slab_cfg["thickness"]],
                "size": [width, depth, slab_cfg["thickness"]],
                "material": slab_cfg["material"],
                "role": "floor_slab",
            })

        t = wall_thickness_var
        h = floor_heights[floor_idx]
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

        # Advance cumulative Z for next floor
        cumulative_z += h + slab_cfg["thickness"]

    # 4. Roof -- AAA geometry from building_quality.generate_roof()
    roof_cfg = config["roof"]
    roof_z = cumulative_z - slab_cfg["thickness"]
    roof_ops = _generate_roof_operations(
        width, depth, roof_z, roof_cfg, style, rng,
    )
    ops.extend(roof_ops)

    # Use average floor height for facade split (column alignment)
    avg_floor_h = sum(floor_heights) / len(floor_heights) if floor_heights else base_floor_h

    # 5 + 6. CGA facade split: comp(faces) -> split(y, floors) -> split(x, bays) -> fill
    win_cfg = config["windows"]
    door_cfg = config["door"]
    facade_rules = FACADE_STYLE_RULES.get(style, FACADE_STYLE_RULES["medieval"])
    facade_ops = _cga_facade_split(
        width=width,
        depth=depth,
        floors=floors,
        base_z=base_z,
        floor_height=avg_floor_h,
        slab_thickness=slab_cfg["thickness"],
        wall_thickness=wall_thickness_var,
        win_cfg=win_cfg,
        door_cfg=door_cfg,
        facade_rules=facade_rules,
        style=style,
        rng=rng,
    )
    ops.extend(facade_ops)

    # 7. Detail operations from style config -- AAA geometry from building_quality
    # Variation: select a random subset of details (at least 1, at most all)
    all_details = list(config["details"])
    if len(all_details) > 1:
        min_details = max(1, len(all_details) - 1)
        detail_count = rng.randint(min_details, len(all_details))
        details = rng.sample(all_details, detail_count)
    else:
        details = all_details
    detail_ops = _generate_detail_operations(
        details, width, depth, roof_z, base_z, floors,
        avg_floor_h, wall_thickness_var,
        style, rng,
    )
    ops.extend(detail_ops)

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

# ---------------------------------------------------------------------------
# Room Spatial Graphs -- define spatial relationships per room type
# ---------------------------------------------------------------------------
# focal_points: items anchoring room zones with preferred wall placement
#   - wall_pref: "back" | "front" | "side" | "exterior" | "any"
# clusters: groups of items placed relative to an anchor item
#   - anchor: item type name, members: list of (type, offset_dist, face_anchor)
# wall_preferences: default wall preference for specific furniture types

ROOM_SPATIAL_GRAPHS: dict[str, dict] = {
    "tavern": {
        "focal_points": [
            {"type": "bar_counter", "wall_pref": "back"},
            {"type": "fireplace", "wall_pref": "side"},
        ],
        "clusters": [
            {
                "anchor": "table",
                "members": [
                    ("chair", 0.7, True),
                    ("chair", 0.7, True),
                ],
            },
            {
                "anchor": "table",
                "members": [
                    ("chair", 0.7, True),
                    ("chair", 0.7, True),
                ],
            },
        ],
        "wall_preferences": {
            "shelf": "side",
            "barrel": "back",
        },
    },
    "bedroom": {
        "focal_points": [
            {"type": "bed", "wall_pref": "back"},
        ],
        "clusters": [
            {
                "anchor": "bed",
                "members": [
                    ("nightstand", 0.4, False),
                ],
            },
            {
                "anchor": "desk",
                "members": [
                    ("chair", 0.6, True),
                ],
            },
        ],
        "wall_preferences": {
            "wardrobe": "side",
            "desk": "side",
        },
    },
    "kitchen": {
        "focal_points": [
            {"type": "cooking_fire", "wall_pref": "back"},
        ],
        "clusters": [
            {
                "anchor": "table",
                "members": [],
            },
        ],
        "wall_preferences": {
            "shelf": "side",
            "barrel": "side",
            "crate": "side",
        },
    },
    "blacksmith": {
        "focal_points": [
            {"type": "forge", "wall_pref": "back"},
        ],
        "clusters": [
            {
                "anchor": "forge",
                "members": [
                    ("bellows", 0.8, False),
                ],
            },
            {
                "anchor": "anvil",
                "members": [],
            },
        ],
        "wall_preferences": {
            "workbench": "side",
            "weapon_rack": "side",
            "tool_rack": "side",
        },
    },
    "library": {
        "focal_points": [
            {"type": "desk", "wall_pref": "any"},
        ],
        "clusters": [
            {
                "anchor": "desk",
                "members": [
                    ("chair", 0.6, True),
                    ("candelabra", 0.5, False),
                ],
            },
        ],
        "wall_preferences": {
            "bookshelf": "back",
        },
    },
    "chapel": {
        "focal_points": [
            {"type": "altar", "wall_pref": "back"},
        ],
        "clusters": [],
        "wall_preferences": {
            "pew": "center_rows",
            "candelabra": "side",
            "banner": "side",
        },
    },
    "throne_room": {
        "focal_points": [
            {"type": "throne", "wall_pref": "back"},
        ],
        "clusters": [],
        "wall_preferences": {
            "pillar": "side",
            "banner": "side",
            "brazier": "center",
            "carpet": "center",
        },
    },
    "smithy": {
        "focal_points": [
            {"type": "forge", "wall_pref": "back"},
        ],
        "clusters": [
            {
                "anchor": "anvil",
                "members": [],
            },
        ],
        "wall_preferences": {
            "workbench": "side",
            "weapon_rack": "side",
        },
    },
    "great_hall": {
        "focal_points": [
            {"type": "fireplace", "wall_pref": "side"},
        ],
        "clusters": [],
        "wall_preferences": {
            "long_table": "center",
            "chandelier": "center",
            "banner": "side",
        },
    },
    "dining_hall": {
        "focal_points": [
            {"type": "fireplace", "wall_pref": "side"},
        ],
        "clusters": [],
        "wall_preferences": {
            "long_table": "center",
            "chandelier": "center",
            "serving_table": "side",
            "banner": "side",
        },
    },
    "war_room": {
        "focal_points": [
            {"type": "large_table", "wall_pref": "any"},
        ],
        "clusters": [
            {
                "anchor": "large_table",
                "members": [
                    ("chair", 0.8, True),
                    ("chair", 0.8, True),
                    ("chair", 0.8, True),
                    ("chair", 0.8, True),
                ],
            },
        ],
        "wall_preferences": {
            "banner": "side",
            "candelabra": "side",
        },
    },
    "alchemy_lab": {
        "focal_points": [
            {"type": "cauldron", "wall_pref": "any"},
        ],
        "clusters": [
            {
                "anchor": "workbench",
                "members": [],
            },
        ],
        "wall_preferences": {
            "shelf_with_bottles": "back",
            "herb_rack": "side",
        },
    },
    "crypt": {
        "focal_points": [
            {"type": "altar", "wall_pref": "back"},
        ],
        "clusters": [],
        "wall_preferences": {
            "sarcophagus": "center",
            "wall_tomb": "side",
            "candelabra": "side",
        },
    },
}

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


def _pick_wall_position(
    wall_id: int,
    sx: float,
    sy: float,
    width: float,
    depth: float,
    wall_margin: float,
    rng: random.Random,
) -> tuple[float, float, float, float, float]:
    """Return (x, y, rotation, effective_sx, effective_sy) for a wall placement."""
    if wall_id == 0:  # front wall (y=0)
        x = rng.uniform(sx / 2 + wall_margin, width - sx / 2 - wall_margin)
        y = sy / 2 + wall_margin
        return x, y, 0.0, sx, sy
    elif wall_id == 1:  # back wall (y=depth)
        x = rng.uniform(sx / 2 + wall_margin, width - sx / 2 - wall_margin)
        y = depth - sy / 2 - wall_margin
        return x, y, math.pi, sx, sy
    elif wall_id == 2:  # left wall (x=0)
        x = sy / 2 + wall_margin
        y = rng.uniform(sx / 2 + wall_margin, depth - sx / 2 - wall_margin)
        return x, y, math.pi / 2, sy, sx
    else:  # right wall (x=width)
        x = width - sy / 2 - wall_margin
        y = rng.uniform(sx / 2 + wall_margin, depth - sx / 2 - wall_margin)
        return x, y, -math.pi / 2, sy, sx


def _wall_pref_to_ids(wall_pref: str, rng: random.Random) -> list[int]:
    """Convert a wall preference string to ordered wall IDs to try."""
    if wall_pref == "back":
        return [1]
    elif wall_pref == "front":
        return [0]
    elif wall_pref == "side":
        return [2, 3] if rng.random() < 0.5 else [3, 2]
    elif wall_pref == "exterior":
        return [1, 2, 3]
    else:  # "any"
        walls = [0, 1, 2, 3]
        rng.shuffle(walls)
        return walls


def _check_collision(
    x: float,
    y: float,
    sx: float,
    sy: float,
    occupied: list[tuple[float, float, float, float]],
) -> bool:
    """Return True if (x,y,sx,sy) AABB overlaps any occupied box."""
    for ocx, ocy, osx, osy in occupied:
        if abs(x - ocx) < (sx + osx) / 2 and abs(y - ocy) < (sy + osy) / 2:
            return True
    return False


def _in_bounds(x: float, y: float, sx: float, sy: float,
               width: float, depth: float) -> bool:
    """Check item center+extents fit within room."""
    return (sx / 2 <= x <= width - sx / 2 and
            sy / 2 <= y <= depth - sy / 2)


def _place_item(
    x: float,
    y: float,
    rotation: float,
    sx: float,
    sy: float,
    item_type: str,
    item_height: float,
    occupied: list[tuple[float, float, float, float]],
    placed: list[dict],
) -> bool:
    """Append an item to placed/occupied lists. Returns True on success."""
    occupied.append((x, y, sx, sy))
    placed.append({
        "type": item_type,
        "position": [round(x, 4), round(y, 4), 0.0],
        "rotation": round(rotation, 4),
        "scale": [round(sx, 4), round(sy, 4), round(item_height, 4)],
    })
    return True


def _door_corridor_clear(
    x: float, y: float, sx: float, sy: float,
    width: float, depth: float, corridor_width: float,
    item_height: float = 1.0,
) -> bool:
    """Check that an item does not block the 1.0m door-to-center corridor.

    Door zones are assumed at the center of the front wall (y=0).
    The corridor runs from (width/2, 0) to (width/2, depth/2).
    Floor-level items (height < 0.1m) like rugs/carpets are walkable and exempt.
    """
    # Floor-level items (rugs, carpets, map displays) are walkable -- exempt
    if item_height < 0.1:
        return True
    corridor_cx = width / 2
    corridor_half_w = corridor_width / 2
    # Item must not overlap the corridor rectangle from y=0 to y=depth/2
    item_left = x - sx / 2
    item_right = x + sx / 2
    item_front = y - sy / 2
    item_back = y + sy / 2
    corr_left = corridor_cx - corridor_half_w
    corr_right = corridor_cx + corridor_half_w
    # Check overlap
    if item_right > corr_left and item_left < corr_right:
        if item_front < depth / 2 and item_back > 0:
            return False
    return True


def generate_interior_layout(
    room_type: str,
    width: float,
    depth: float,
    height: float = 3.0,
    seed: int = 0,
) -> list[dict]:
    """Generate spatially-aware furniture placement for a room type.

    Uses ROOM_SPATIAL_GRAPHS for relationship-based placement when available:
      Phase 1: Place focal points on preferred walls
      Phase 2: Place clustered items relative to anchors (chairs face tables)
      Phase 3: Place remaining wall/corner items with 0.3m wall clearance
      Phase 4: Enforce 1.0m door clearance corridor

    Returns list of dicts with: type, position (x,y,z), rotation, scale.
    """
    rng = random.Random(seed)
    config = _ROOM_CONFIGS.get(room_type, [])
    if not config:
        return []

    placed: list[dict] = []
    occupied: list[tuple[float, float, float, float]] = []  # (cx, cy, sx, sy)

    wall_margin = 0.3
    door_corridor_width = 1.0

    # Build lookup from config for quick access
    config_items: list[tuple[str, str, tuple[float, float], float]] = list(config)

    spatial = ROOM_SPATIAL_GRAPHS.get(room_type)

    if spatial is None:
        # Fallback: use basic placement for room types without spatial graphs
        return _generate_interior_layout_basic(
            config_items, width, depth, wall_margin, door_corridor_width, rng,
        )

    # Track which config items have been placed (by index)
    placed_indices: set[int] = set()
    # Map anchor type -> placed position for cluster resolution
    anchor_positions: dict[str, tuple[float, float]] = {}

    # ---- Phase 1: Place focal points on preferred walls ----
    for fp in spatial.get("focal_points", []):
        fp_type = fp["type"]
        wall_pref = fp.get("wall_pref", "any")
        # Find matching config item
        idx = _find_config_index(config_items, fp_type, placed_indices)
        if idx is None:
            continue
        _, rule, base_size, item_height = config_items[idx]
        sx, sy = base_size
        wall_ids = _wall_pref_to_ids(wall_pref, rng)

        ok = False
        for wall_id in wall_ids:
            for _attempt in range(20):
                px, py, rot, esx, esy = _pick_wall_position(
                    wall_id, sx, sy, width, depth, wall_margin, rng,
                )
                if (not _check_collision(px, py, esx, esy, occupied)
                        and _in_bounds(px, py, esx, esy, width, depth)
                        and _door_corridor_clear(px, py, esx, esy, width, depth,
                                                 door_corridor_width, item_height)):
                    _place_item(px, py, rot, esx, esy, fp_type, item_height,
                                occupied, placed)
                    anchor_positions[fp_type] = (px, py)
                    placed_indices.add(idx)
                    ok = True
                    break
            if ok:
                break

    # ---- Phase 2: Place clustered items relative to anchors ----
    for cluster in spatial.get("clusters", []):
        anchor_type = cluster["anchor"]
        members = cluster.get("members", [])

        # If anchor not yet placed, place it now (as center item)
        if anchor_type not in anchor_positions:
            idx = _find_config_index(config_items, anchor_type, placed_indices)
            if idx is None:
                continue
            _, rule, base_size, item_height = config_items[idx]
            sx, sy = base_size
            # Place anchor in center area
            ok = False
            for _attempt in range(50):
                margin = max(sx, sy) / 2 + wall_margin
                px = rng.uniform(margin, width - margin)
                py = rng.uniform(margin, depth - margin)
                rot = rng.uniform(-0.1, 0.1)
                if (not _check_collision(px, py, sx, sy, occupied)
                        and _in_bounds(px, py, sx, sy, width, depth)
                        and _door_corridor_clear(px, py, sx, sy, width, depth,
                                                 door_corridor_width)):
                    _place_item(px, py, rot, sx, sy, anchor_type, item_height,
                                occupied, placed)
                    anchor_positions[anchor_type] = (px, py)
                    placed_indices.add(idx)
                    ok = True
                    break

        anchor_pos = anchor_positions.get(anchor_type)
        if anchor_pos is None:
            continue

        # Place cluster members around anchor
        ax, ay = anchor_pos
        for member_type, offset_dist, face_anchor in members:
            idx = _find_config_index(config_items, member_type, placed_indices)
            if idx is None:
                continue
            _, rule, base_size, item_height = config_items[idx]
            msx, msy = base_size

            ok = False
            for _attempt in range(30):
                angle = rng.uniform(0, 2 * math.pi)
                px = ax + math.cos(angle) * offset_dist
                py = ay + math.sin(angle) * offset_dist
                if face_anchor:
                    # Rotate to face anchor center
                    rot = math.atan2(ay - py, ax - px) - math.pi / 2
                else:
                    rot = rng.uniform(-0.1, 0.1)
                if (not _check_collision(px, py, msx, msy, occupied)
                        and _in_bounds(px, py, msx, msy, width, depth)
                        and _door_corridor_clear(px, py, msx, msy, width, depth,
                                                 door_corridor_width)):
                    _place_item(px, py, rot, msx, msy, member_type, item_height,
                                occupied, placed)
                    placed_indices.add(idx)
                    ok = True
                    break

    # ---- Phase 3: Place remaining items (wall/corner with preferences) ----
    wall_prefs = spatial.get("wall_preferences", {})
    for idx, (item_type, rule, base_size, item_height) in enumerate(config_items):
        if idx in placed_indices:
            continue
        sx, sy = base_size

        pref = wall_prefs.get(item_type, None)
        ok = False

        if rule == "wall":
            if pref and pref not in ("center", "center_rows"):
                wall_ids = _wall_pref_to_ids(pref, rng)
            else:
                wall_ids = [0, 1, 2, 3]
                rng.shuffle(wall_ids)

            for wall_id in wall_ids:
                for _attempt in range(15):
                    px, py, rot, esx, esy = _pick_wall_position(
                        wall_id, sx, sy, width, depth, wall_margin, rng,
                    )
                    if (not _check_collision(px, py, esx, esy, occupied)
                            and _in_bounds(px, py, esx, esy, width, depth)
                            and _door_corridor_clear(px, py, esx, esy, width,
                                                     depth, door_corridor_width)):
                        _place_item(px, py, rot, esx, esy, item_type,
                                    item_height, occupied, placed)
                        placed_indices.add(idx)
                        ok = True
                        break
                if ok:
                    break

        elif rule == "center":
            for _attempt in range(50):
                margin = max(sx, sy) / 2 + wall_margin
                px = rng.uniform(margin, width - margin)
                py = rng.uniform(margin, depth - margin)
                rot = rng.uniform(-0.1, 0.1)
                if (not _check_collision(px, py, sx, sy, occupied)
                        and _in_bounds(px, py, sx, sy, width, depth)
                        and _door_corridor_clear(px, py, sx, sy, width, depth,
                                                 door_corridor_width)):
                    _place_item(px, py, rot, sx, sy, item_type, item_height,
                                occupied, placed)
                    placed_indices.add(idx)
                    ok = True
                    break

        elif rule == "corner":
            corners = [0, 1, 2, 3]
            rng.shuffle(corners)
            for corner in corners:
                if corner == 0:
                    px, py = sx / 2 + wall_margin, sy / 2 + wall_margin
                elif corner == 1:
                    px, py = width - sx / 2 - wall_margin, sy / 2 + wall_margin
                elif corner == 2:
                    px, py = sx / 2 + wall_margin, depth - sy / 2 - wall_margin
                else:
                    px, py = (width - sx / 2 - wall_margin,
                              depth - sy / 2 - wall_margin)
                rot = 0.0
                if (not _check_collision(px, py, sx, sy, occupied)
                        and _in_bounds(px, py, sx, sy, width, depth)
                        and _door_corridor_clear(px, py, sx, sy, width, depth,
                                                 door_corridor_width)):
                    _place_item(px, py, rot, sx, sy, item_type, item_height,
                                occupied, placed)
                    placed_indices.add(idx)
                    ok = True
                    break

    return placed


def _find_config_index(
    config_items: list[tuple[str, str, tuple[float, float], float]],
    item_type: str,
    placed_indices: set[int],
) -> Optional[int]:
    """Find the first unplaced config index matching item_type."""
    for i, (itype, _rule, _size, _h) in enumerate(config_items):
        if itype == item_type and i not in placed_indices:
            return i
    return None


def _generate_interior_layout_basic(
    config_items: list[tuple[str, str, tuple[float, float], float]],
    width: float,
    depth: float,
    wall_margin: float,
    door_corridor_width: float,
    rng: random.Random,
) -> list[dict]:
    """Basic interior layout for room types without spatial graphs.

    Uses improved collision + wall clearance + door corridor enforcement.
    """
    placed: list[dict] = []
    occupied: list[tuple[float, float, float, float]] = []

    for item_type, rule, base_size, item_height in config_items:
        sx, sy = base_size
        rotation = 0.0
        max_attempts = 50

        for _attempt in range(max_attempts):
            if rule == "wall":
                wall = rng.randint(0, 3)
                px, py, rot, esx, esy = _pick_wall_position(
                    wall, sx, sy, width, depth, wall_margin, rng,
                )
            elif rule == "center":
                margin = max(sx, sy) / 2 + wall_margin
                px = rng.uniform(margin, width - margin)
                py = rng.uniform(margin, depth - margin)
                rot = rng.uniform(-0.1, 0.1)
                esx, esy = sx, sy
            elif rule == "corner":
                corner = rng.randint(0, 3)
                if corner == 0:
                    px, py = sx / 2 + wall_margin, sy / 2 + wall_margin
                elif corner == 1:
                    px, py = (width - sx / 2 - wall_margin,
                              sy / 2 + wall_margin)
                elif corner == 2:
                    px, py = (sx / 2 + wall_margin,
                              depth - sy / 2 - wall_margin)
                else:
                    px, py = (width - sx / 2 - wall_margin,
                              depth - sy / 2 - wall_margin)
                rot = 0.0
                esx, esy = sx, sy
            else:
                px, py = width / 2, depth / 2
                rot = 0.0
                esx, esy = sx, sy

            if (not _check_collision(px, py, esx, esy, occupied)
                    and _in_bounds(px, py, esx, esy, width, depth)
                    and _door_corridor_clear(px, py, esx, esy, width, depth,
                                             door_corridor_width)):
                _place_item(px, py, rot, esx, esy, item_type, item_height,
                            occupied, placed)
                break

            # Reset swapped sizes for next attempt
            sx, sy = base_size

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


# ---------------------------------------------------------------------------
# Interior-Exterior Consistency Linking (AAA-06)
# ---------------------------------------------------------------------------

# Building type → floor assignments (ground floor first, upper floors follow)
BUILDING_FLOOR_PLANS: dict[str, list[list[str]]] = {
    "tavern": [
        ["tavern", "kitchen"],           # ground: main hall + kitchen
        ["bedroom", "bedroom"],          # upper: guest rooms
    ],
    "house": [
        ["kitchen", "storage"],          # ground
        ["bedroom", "study"],            # upper
    ],
    "shop": [
        ["storage", "storage"],          # ground: shop floor
        ["bedroom"],                     # upper: shopkeeper quarters
    ],
    "castle": [
        ["guard_post", "armory"],        # ground
        ["great_hall", "war_room"],      # first
        ["throne_room"],                 # second
        ["bedroom", "study"],            # third
    ],
    "cathedral": [
        ["chapel"],                      # ground: nave
        ["library"],                     # upper: scriptorium
    ],
    "tower": [
        ["storage"],                     # ground
        ["alchemy_lab"],                 # first
        ["library"],                     # second
        ["bedroom"],                     # top
    ],
    "forge": [
        ["blacksmith"],                  # ground
        ["storage", "bedroom"],          # upper
    ],
    "shrine": [
        ["shrine_room"],                 # single floor
    ],
    "dungeon": [
        ["guard_post"],                  # entry
        ["dungeon_cell", "dungeon_cell", "torture_chamber"],
        ["crypt", "treasury"],           # deepest
    ],
    "barracks": [
        ["guard_barracks", "armory"],    # ground
        ["guard_barracks", "guard_barracks"],  # upper
    ],
    "library": [
        ["library", "library"],          # ground
        ["study", "study"],              # upper
    ],
    "temple": [
        ["chapel"],                      # ground
        ["shrine_room", "library"],      # upper
    ],
    "wizard_tower": [
        ["alchemy_lab"],                 # ground
        ["library"],                     # first
        ["study"],                       # second
        ["bedroom"],                     # top
    ],
}

# Lighting rules per room type — what light sources to auto-place
ROOM_LIGHTING: dict[str, list[dict]] = {
    "tavern": [
        {"type": "fireplace_light", "position": "fireplace", "range": 8.0, "color": [1.0, 0.7, 0.4], "intensity": 1.2},
        {"type": "hanging_lantern", "position": "ceiling_center", "range": 5.0, "color": [1.0, 0.8, 0.5], "intensity": 0.8},
    ],
    "dungeon_cell": [
        {"type": "torch_sconce", "position": "wall_by_door", "range": 4.0, "color": [1.0, 0.6, 0.3], "intensity": 0.5},
    ],
    "library": [
        {"type": "candelabra_light", "position": "desk", "range": 3.0, "color": [1.0, 0.85, 0.6], "intensity": 0.6},
        {"type": "window_light", "position": "window", "range": 6.0, "color": [0.9, 0.95, 1.0], "intensity": 1.0},
    ],
    "throne_room": [
        {"type": "chandelier_light", "position": "ceiling_center", "range": 10.0, "color": [1.0, 0.9, 0.7], "intensity": 1.5},
        {"type": "brazier_light", "position": "brazier", "range": 5.0, "color": [1.0, 0.6, 0.3], "intensity": 0.8},
    ],
    "chapel": [
        {"type": "candelabra_light", "position": "altar", "range": 4.0, "color": [1.0, 0.9, 0.7], "intensity": 0.7},
        {"type": "window_light", "position": "window", "range": 8.0, "color": [0.8, 0.85, 1.0], "intensity": 1.2},
    ],
    "blacksmith": [
        {"type": "forge_glow", "position": "forge", "range": 6.0, "color": [1.0, 0.4, 0.1], "intensity": 1.5},
    ],
    "crypt": [
        {"type": "candle_cluster", "position": "altar", "range": 3.0, "color": [0.9, 0.8, 0.5], "intensity": 0.3},
    ],
    "alchemy_lab": [
        {"type": "potion_glow", "position": "cauldron", "range": 3.0, "color": [0.3, 1.0, 0.5], "intensity": 0.4},
        {"type": "candelabra_light", "position": "workbench", "range": 3.0, "color": [1.0, 0.85, 0.6], "intensity": 0.6},
    ],
    "torture_chamber": [
        {"type": "brazier_light", "position": "brazier", "range": 4.0, "color": [1.0, 0.5, 0.2], "intensity": 0.6},
    ],
}

# Default lighting for rooms not in ROOM_LIGHTING
_DEFAULT_LIGHTING = [
    {"type": "torch_sconce", "position": "wall_center", "range": 5.0, "color": [1.0, 0.7, 0.4], "intensity": 0.7},
]


def generate_consistent_interior(
    building_spec: BuildingSpec,
    building_type: str = "house",
    seed: int = 0,
) -> dict:
    """Generate interior layouts that match a building exterior.

    Given a BuildingSpec (from evaluate_building_grammar), derive matching
    interior rooms with:
    - Room dimensions matching the exterior footprint
    - Door positions matching exterior door openings
    - Window positions aligned with exterior windows
    - Room function assignments based on building type
    - Furniture placement per room
    - Lighting placement per room type
    - Walkability clearance of 0.8m minimum paths

    Parameters
    ----------
    building_spec : BuildingSpec
        The exterior building specification.
    building_type : str
        Building archetype for room function assignment.
    seed : int
        Random seed for deterministic layout.

    Returns
    -------
    dict with:
        floors: list of floor dicts, each containing:
            - rooms: list of room dicts with type, bounds, furniture, lighting
            - doors: list of door positions connecting rooms
            - windows: list of window positions (from exterior)
        metadata: building_type, total_rooms, total_furniture, total_lights
    """
    rng = random.Random(seed)
    width, depth = building_spec.footprint
    floors_count = building_spec.floors
    style = building_spec.style
    config = STYLE_CONFIGS.get(style, STYLE_CONFIGS["medieval"])

    wall_thickness = config["walls"]["thickness"]
    floor_height = config["walls"]["height_per_floor"]
    fnd_height = config["foundation"]["height"]

    # Get floor plan for building type
    floor_plan = BUILDING_FLOOR_PLANS.get(building_type, [["storage"]])

    # Extract exterior openings from the building spec
    exterior_doors = []
    exterior_windows = []
    for op in building_spec.operations:
        if op.get("role") == "door_opening":
            exterior_doors.append(op)
        elif op.get("role") == "window_opening":
            exterior_windows.append(op)

    # Interior usable space (subtract wall thickness)
    inner_width = width - 2 * wall_thickness
    inner_depth = depth - 2 * wall_thickness

    floors_result = []
    total_furniture = 0
    total_lights = 0
    total_rooms = 0
    min_clearance = 0.8  # minimum walkable path width

    for floor_idx in range(floors_count):
        floor_z = fnd_height + floor_idx * floor_height

        # Get room types for this floor
        if floor_idx < len(floor_plan):
            room_types = floor_plan[floor_idx]
        else:
            # Repeat last floor plan or default to storage
            room_types = floor_plan[-1] if floor_plan else ["storage"]

        # Subdivide floor into rooms
        num_rooms = len(room_types)
        rooms = []

        if num_rooms == 1:
            # Single room takes the whole floor
            room_bounds = [(wall_thickness, wall_thickness, inner_width, inner_depth)]
        elif num_rooms == 2:
            # Split along the longer axis
            if inner_width >= inner_depth:
                half_w = inner_width / 2 - wall_thickness / 2
                room_bounds = [
                    (wall_thickness, wall_thickness, half_w, inner_depth),
                    (wall_thickness + half_w + wall_thickness, wall_thickness, half_w, inner_depth),
                ]
            else:
                half_d = inner_depth / 2 - wall_thickness / 2
                room_bounds = [
                    (wall_thickness, wall_thickness, inner_width, half_d),
                    (wall_thickness, wall_thickness + half_d + wall_thickness, inner_width, half_d),
                ]
        elif num_rooms == 3:
            # L-shaped subdivision: two rooms on one side, one large on other
            half_w = inner_width / 2 - wall_thickness / 2
            half_d = inner_depth / 2 - wall_thickness / 2
            room_bounds = [
                (wall_thickness, wall_thickness, half_w, inner_depth),  # full-depth left
                (wall_thickness + half_w + wall_thickness, wall_thickness, half_w, half_d),  # top-right
                (wall_thickness + half_w + wall_thickness, wall_thickness + half_d + wall_thickness, half_w, half_d),  # bottom-right
            ]
        else:
            # 4+ rooms: grid subdivision
            cols = min(num_rooms, max(2, int(math.sqrt(num_rooms) + 0.5)))
            rows = math.ceil(num_rooms / cols)
            cell_w = (inner_width - (cols - 1) * wall_thickness) / cols
            cell_d = (inner_depth - (rows - 1) * wall_thickness) / rows
            room_bounds = []
            for ri in range(num_rooms):
                row = ri // cols
                col = ri % cols
                rx = wall_thickness + col * (cell_w + wall_thickness)
                ry = wall_thickness + row * (cell_d + wall_thickness)
                room_bounds.append((rx, ry, cell_w, cell_d))

        # Generate each room
        for room_idx, room_type in enumerate(room_types):
            if room_idx >= len(room_bounds):
                break
            rx, ry, rw, rd = room_bounds[room_idx]

            # Generate furniture with collision avoidance
            furniture = generate_interior_layout(
                room_type=room_type,
                width=rw,
                depth=rd,
                height=floor_height - 0.1,
                seed=seed + floor_idx * 100 + room_idx,
            )

            # Validate walkability — ensure 0.8m clearance to door
            # Door is always on the wall nearest to the building entrance
            door_x = rw / 2
            door_y = 0.1
            walkable = True
            for item in furniture:
                ix, iy = item["position"][0], item["position"][1]
                isx, isy = item["scale"][0], item["scale"][1]
                # Check if item blocks the door access path
                if abs(ix - door_x) < (isx / 2 + min_clearance) and iy < (isy / 2 + min_clearance + 0.3):
                    walkable = False
                    # Push item back from door
                    item["position"][1] = round(isy / 2 + min_clearance + 0.4, 4)

            # Assign lighting
            lighting_rules = ROOM_LIGHTING.get(room_type, _DEFAULT_LIGHTING)
            lights = []
            for light_rule in lighting_rules:
                light = dict(light_rule)
                # Resolve position to actual coordinates
                pos_hint = light["position"]
                if pos_hint == "ceiling_center":
                    light["world_position"] = [round(rx + rw / 2, 4), round(ry + rd / 2, 4), round(floor_z + floor_height - 0.3, 4)]
                elif pos_hint in ("fireplace", "forge", "brazier", "altar", "cauldron", "workbench", "desk"):
                    # Find the furniture item matching this type
                    matched = [f for f in furniture if pos_hint in f["type"]]
                    if matched:
                        fp = matched[0]["position"]
                        light["world_position"] = [round(rx + fp[0], 4), round(ry + fp[1], 4), round(floor_z + 1.0, 4)]
                    else:
                        light["world_position"] = [round(rx + rw / 2, 4), round(ry + rd / 2, 4), round(floor_z + 1.5, 4)]
                elif pos_hint == "wall_center":
                    wall_side = rng.randint(0, 3)
                    if wall_side == 0:
                        light["world_position"] = [round(rx + rw / 2, 4), round(ry + 0.1, 4), round(floor_z + floor_height * 0.7, 4)]
                    elif wall_side == 1:
                        light["world_position"] = [round(rx + rw / 2, 4), round(ry + rd - 0.1, 4), round(floor_z + floor_height * 0.7, 4)]
                    elif wall_side == 2:
                        light["world_position"] = [round(rx + 0.1, 4), round(ry + rd / 2, 4), round(floor_z + floor_height * 0.7, 4)]
                    else:
                        light["world_position"] = [round(rx + rw - 0.1, 4), round(ry + rd / 2, 4), round(floor_z + floor_height * 0.7, 4)]
                elif pos_hint == "wall_by_door":
                    light["world_position"] = [round(rx + door_x + 0.5, 4), round(ry + 0.1, 4), round(floor_z + floor_height * 0.7, 4)]
                elif pos_hint == "window":
                    # Match exterior window position if available
                    floor_windows = [w for w in exterior_windows if w.get("floor") == floor_idx]
                    if floor_windows:
                        w = floor_windows[0]
                        wp = w.get("position", [rw / 2, 0, floor_height / 2])
                        light["world_position"] = [round(rx + wp[0], 4), round(ry + wp[1], 4), round(floor_z + wp[2], 4)]
                    else:
                        light["world_position"] = [round(rx + rw / 2, 4), round(ry + 0.1, 4), round(floor_z + floor_height * 0.6, 4)]
                else:
                    light["world_position"] = [round(rx + rw / 2, 4), round(ry + rd / 2, 4), round(floor_z + 1.5, 4)]

                lights.append(light)

            # Collect windows for this floor
            floor_windows_data = [
                {
                    "wall_index": w.get("wall_index", 0),
                    "position": w.get("position", [0, 0, 0]),
                    "size": w.get("size", [0.8, 1.2]),
                }
                for w in exterior_windows if w.get("floor") == floor_idx
            ]

            rooms.append({
                "type": room_type,
                "bounds": {"x": round(rx, 4), "y": round(ry, 4), "width": round(rw, 4), "depth": round(rd, 4)},
                "floor_z": round(floor_z, 4),
                "ceiling_z": round(floor_z + floor_height, 4),
                "furniture": furniture,
                "lighting": lights,
                "windows": floor_windows_data,
                "walkable": walkable,
            })

            total_furniture += len(furniture)
            total_lights += len(lights)
            total_rooms += 1

        # Internal doors between rooms on same floor
        internal_doors = []
        for i in range(len(rooms) - 1):
            r1 = rooms[i]["bounds"]
            r2 = rooms[i + 1]["bounds"]
            # Door at the shared wall between adjacent rooms
            if abs((r1["x"] + r1["width"]) - r2["x"]) < wall_thickness * 2:
                # Vertical shared wall
                door_y_pos = max(r1["y"], r2["y"]) + min(r1["depth"], r2["depth"]) / 2
                internal_doors.append({
                    "position": [round(r2["x"], 4), round(door_y_pos, 4), round(floor_z, 4)],
                    "size": [config["door"]["width"], config["door"]["height"]],
                    "connects": [rooms[i]["type"], rooms[i + 1]["type"]],
                    "orientation": "x",
                })
            elif abs((r1["y"] + r1["depth"]) - r2["y"]) < wall_thickness * 2:
                # Horizontal shared wall
                door_x_pos = max(r1["x"], r2["x"]) + min(r1["width"], r2["width"]) / 2
                internal_doors.append({
                    "position": [round(door_x_pos, 4), round(r2["y"], 4), round(floor_z, 4)],
                    "size": [config["door"]["width"], config["door"]["height"]],
                    "connects": [rooms[i]["type"], rooms[i + 1]["type"]],
                    "orientation": "y",
                })

        floors_result.append({
            "floor_index": floor_idx,
            "floor_z": round(floor_z, 4),
            "rooms": rooms,
            "internal_doors": internal_doors,
        })

    return {
        "floors": floors_result,
        "metadata": {
            "building_type": building_type,
            "style": style,
            "footprint": [width, depth],
            "total_floors": floors_count,
            "total_rooms": total_rooms,
            "total_furniture": total_furniture,
            "total_lights": total_lights,
            "wall_thickness": wall_thickness,
            "floor_height": floor_height,
        },
    }


# ---------------------------------------------------------------------------
# Lighting Placement Engine (Phase 33 Task 4)
# ---------------------------------------------------------------------------

# Light type physical properties -- color temperatures in 2700-3500K range
_LIGHT_TYPE_PROPS: dict[str, dict] = {
    "torch_sconce":     {"color_temperature": 2800, "radius": 4.0, "intensity": 1.0},
    "candle":           {"color_temperature": 3000, "radius": 2.0, "intensity": 0.5},
    "fireplace_light":  {"color_temperature": 2700, "radius": 5.0, "intensity": 1.5},
    "chandelier_light": {"color_temperature": 3200, "radius": 8.0, "intensity": 2.0},
    "brazier_light":    {"color_temperature": 3000, "radius": 3.0, "intensity": 0.8},
}

# Per-room lighting schemas:
#   mandatory: list of light type strings that are always placed
#   conditional: list of dicts with 'type' and 'trigger' (furniture substring)
LIGHTING_SCHEMAS: dict[str, dict] = {
    "tavern": {
        "mandatory": ["torch_sconce", "torch_sconce", "fireplace_light"],
        "conditional": [
            {"type": "chandelier_light", "trigger": "chandelier"},
            {"type": "candle",           "trigger": "table"},
        ],
    },
    "smithy": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "brazier_light", "trigger": "brazier"},
            {"type": "fireplace_light", "trigger": "forge"},
        ],
    },
    "storage": {
        "mandatory": ["torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "table"},
        ],
    },
    "barracks": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "brazier_light", "trigger": "brazier"},
            {"type": "candle", "trigger": "table"},
        ],
    },
    "guard_post": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "brazier_light", "trigger": "brazier"},
            {"type": "candle", "trigger": "table"},
        ],
    },
    "throne_room": {
        "mandatory": ["chandelier_light", "torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "brazier_light", "trigger": "brazier"},
            {"type": "candle", "trigger": "candelabra"},
        ],
    },
    "dungeon_cell": {
        "mandatory": ["torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "table"},
        ],
    },
    "bedroom": {
        "mandatory": ["torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "nightstand"},
            {"type": "candle", "trigger": "desk"},
            {"type": "fireplace_light", "trigger": "fireplace"},
        ],
    },
    "kitchen": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "fireplace_light", "trigger": "cooking_fire"},
            {"type": "candle", "trigger": "table"},
        ],
    },
    "library": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "desk"},
            {"type": "chandelier_light", "trigger": "chandelier"},
        ],
    },
    "study": {
        "mandatory": ["torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "desk"},
        ],
    },
    "great_hall": {
        "mandatory": ["chandelier_light", "torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "fireplace_light", "trigger": "fireplace"},
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "table"},
        ],
    },
    "armory": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "table"},
            {"type": "brazier_light", "trigger": "brazier"},
        ],
    },
    "chapel": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "altar"},
            {"type": "chandelier_light", "trigger": "chandelier"},
        ],
    },
    "shrine_room": {
        "mandatory": ["torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "altar"},
        ],
    },
    "blacksmith": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "fireplace_light", "trigger": "forge"},
            {"type": "brazier_light", "trigger": "brazier"},
        ],
    },
    "guard_barracks": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "brazier_light", "trigger": "brazier"},
            {"type": "candle", "trigger": "table"},
        ],
    },
    "treasury": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "chandelier_light", "trigger": "chandelier"},
            {"type": "candle", "trigger": "candelabra"},
        ],
    },
    "war_room": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "table"},
            {"type": "chandelier_light", "trigger": "chandelier"},
        ],
    },
    "alchemy_lab": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "workbench"},
            {"type": "brazier_light", "trigger": "brazier"},
        ],
    },
    "torture_chamber": {
        "mandatory": ["torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "brazier_light", "trigger": "brazier"},
            {"type": "fireplace_light", "trigger": "fireplace"},
        ],
    },
    "crypt": {
        "mandatory": ["torch_sconce"],
        "conditional": [
            {"type": "candle", "trigger": "candelabra"},
            {"type": "candle", "trigger": "altar"},
        ],
    },
    "dining_hall": {
        "mandatory": ["chandelier_light", "torch_sconce", "torch_sconce"],
        "conditional": [
            {"type": "fireplace_light", "trigger": "fireplace"},
            {"type": "candle", "trigger": "table"},
        ],
    },
}

# Minimum guaranteed light sources per room
_MIN_LIGHTS_PER_ROOM = 2


def generate_lighting_layout(
    room_type: str,
    width: float,
    depth: float,
    height: float,
    furniture_items: list[dict],
    door_positions: list[tuple[float, float]],
    seed: int = 0,
) -> list[dict]:
    """Generate a deterministic lighting layout for a room.

    Placement rules:
    - Torches at doorway positions (both sides, 1.6m height)
    - Candles on table surfaces (furniture with "table" in type name)
    - Fireplace emissive if fireplace in furniture_items
    - Chandelier at ceiling center if room > 8m in any dimension
    - Minimum 2 light sources guaranteed via supplemental wall torches

    Parameters
    ----------
    room_type : str
        Key into LIGHTING_SCHEMAS. Falls back to a minimal default schema.
    width, depth, height : float
        Room dimensions in metres.
    furniture_items : list[dict]
        List of placed furniture dicts with at least a "type" key.
    door_positions : list[tuple[float, float]]
        (x, y) positions of doors along the room perimeter.
    seed : int
        RNG seed for deterministic placement.

    Returns
    -------
    list[dict] with keys:
        type, position (x, y, z), color_temperature, radius, intensity
    """
    rng = random.Random(seed)
    lights: list[dict] = []

    schema = LIGHTING_SCHEMAS.get(room_type, {
        "mandatory": ["torch_sconce"],
        "conditional": [],
    })

    furniture_types: list[str] = [
        str(item.get("type", "")).lower() for item in furniture_items
    ]

    def _has_furniture(trigger: str) -> bool:
        return any(trigger in ft for ft in furniture_types)

    def _make_light(
        light_type: str,
        x: float,
        y: float,
        z: float,
    ) -> dict:
        props = _LIGHT_TYPE_PROPS.get(light_type, _LIGHT_TYPE_PROPS["torch_sconce"])
        return {
            "type": light_type,
            "position": (round(x, 4), round(y, 4), round(z, 4)),
            "color_temperature": props["color_temperature"],
            "radius": props["radius"],
            "intensity": props["intensity"],
        }

    def _clamp_to_room(x: float, y: float) -> tuple[float, float]:
        margin = 0.15
        cx = max(margin, min(width - margin, x))
        cy = max(margin, min(depth - margin, y))
        return cx, cy

    # ------------------------------------------------------------------
    # 1. Torches at doorway positions (both sides of each door, 1.6m h)
    # ------------------------------------------------------------------
    torch_height = 1.6
    for dx, dy in door_positions:
        # Determine which wall the door is on and place torches on each side
        # Door on front wall (y ~ 0) or back wall (y ~ depth)
        on_front = dy < depth * 0.2
        on_back = dy > depth * 0.8
        on_left = dx < width * 0.2
        on_right = dx > width * 0.8

        if on_front or on_back:
            offset = 0.7
            tx1, ty1 = _clamp_to_room(dx - offset, dy)
            tx2, ty2 = _clamp_to_room(dx + offset, dy)
        elif on_left or on_right:
            offset = 0.7
            tx1, ty1 = _clamp_to_room(dx, dy - offset)
            tx2, ty2 = _clamp_to_room(dx, dy + offset)
        else:
            # Door at ambiguous position — offset along x
            offset = 0.7
            tx1, ty1 = _clamp_to_room(dx - offset, dy)
            tx2, ty2 = _clamp_to_room(dx + offset, dy)

        lights.append(_make_light("torch_sconce", tx1, ty1, torch_height))
        lights.append(_make_light("torch_sconce", tx2, ty2, torch_height))

    # ------------------------------------------------------------------
    # 2. Candles on table surfaces
    # ------------------------------------------------------------------
    candle_height_above_table = 0.78 + 0.05  # table height + candle base
    for item in furniture_items:
        itype = str(item.get("type", "")).lower()
        if "table" in itype:
            pos = item.get("position", [width / 2, depth / 2, 0.0])
            cx, cy = _clamp_to_room(pos[0], pos[1])
            lights.append(_make_light("candle", cx, cy, candle_height_above_table))

    # ------------------------------------------------------------------
    # 3. Fireplace emissive if fireplace present
    # ------------------------------------------------------------------
    if _has_furniture("fireplace") or _has_furniture("cooking_fire"):
        for item in furniture_items:
            itype = str(item.get("type", "")).lower()
            if "fireplace" in itype or "cooking_fire" in itype:
                pos = item.get("position", [width / 2, depth / 2, 0.0])
                fx, fy = _clamp_to_room(pos[0], pos[1])
                lights.append(_make_light("fireplace_light", fx, fy, 0.8))
                break  # one fireplace light per fireplace

    # ------------------------------------------------------------------
    # 4. Chandelier at ceiling center if room > 8m in any dimension
    # ------------------------------------------------------------------
    if width > 8.0 or depth > 8.0:
        cx, cy = width / 2, depth / 2
        chandelier_z = height - 0.3
        lights.append(_make_light("chandelier_light", cx, cy, chandelier_z))

    # ------------------------------------------------------------------
    # 5. Mandatory lights from schema (skip if type already contributed)
    # ------------------------------------------------------------------
    # We add mandatory lights from the schema as supplemental wall torches
    # positioned deterministically along the walls
    mandatory_list = list(schema.get("mandatory", []))
    # Wall positions for supplemental lights: evenly spaced along walls
    wall_positions: list[tuple[float, float]] = [
        (width * 0.25, 0.15),           # front wall left quarter
        (width * 0.75, 0.15),           # front wall right quarter
        (width * 0.25, depth - 0.15),   # back wall left quarter
        (width * 0.75, depth - 0.15),   # back wall right quarter
        (0.15, depth * 0.25),           # left wall lower
        (0.15, depth * 0.75),           # left wall upper
        (width - 0.15, depth * 0.25),   # right wall lower
        (width - 0.15, depth * 0.75),   # right wall upper
    ]
    wall_idx = 0
    for mtype in mandatory_list:
        if wall_idx >= len(wall_positions):
            break
        wx, wy = wall_positions[wall_idx]
        wall_idx += 1
        lights.append(_make_light(mtype, wx, wy, torch_height))

    # ------------------------------------------------------------------
    # 6. Conditional lights from schema
    # ------------------------------------------------------------------
    for cond in schema.get("conditional", []):
        trigger = cond.get("trigger", "")
        ctype = cond.get("type", "torch_sconce")
        if _has_furniture(trigger) and wall_idx < len(wall_positions):
            wx, wy = wall_positions[wall_idx]
            wall_idx += 1
            lights.append(_make_light(ctype, wx, wy, torch_height))

    # ------------------------------------------------------------------
    # 7. Guarantee minimum 2 light sources — add supplemental wall torches
    # ------------------------------------------------------------------
    while len(lights) < _MIN_LIGHTS_PER_ROOM and wall_idx < len(wall_positions):
        wx, wy = wall_positions[wall_idx]
        wall_idx += 1
        lights.append(_make_light("torch_sconce", wx, wy, torch_height))

    # Fallback if wall_positions exhausted but still < minimum
    if len(lights) < _MIN_LIGHTS_PER_ROOM:
        lights.append(_make_light(
            "torch_sconce",
            round(width / 2 + rng.uniform(-0.5, 0.5), 4),
            round(depth / 4, 4),
            torch_height,
        ))
        if len(lights) < _MIN_LIGHTS_PER_ROOM:
            lights.append(_make_light(
                "candle",
                round(width / 2, 4),
                round(depth * 3 / 4, 4),
                0.83,
            ))

    return lights


# ---------------------------------------------------------------------------
# Decorative Clutter Scatter (Task 33-03)
# ---------------------------------------------------------------------------

CLUTTER_POOLS: dict[str, list[str]] = {
    "tavern": [
        "mug", "plate", "bottle", "candle_stub", "coin_pile",
        "food_scrap", "spilled_drink",
    ],
    "bedroom": [
        "book", "candle", "mirror", "clothing_pile", "comb", "jewelry_box",
    ],
    "kitchen": [
        "pot", "ladle", "cutting_board", "vegetable", "flour_bag", "herb_bunch",
    ],
    "blacksmith": [
        "hammer", "tongs", "horseshoe", "metal_ingot", "grinding_stone", "coal_pile",
    ],
    "library": [
        "open_book", "quill_ink", "scroll", "magnifying_glass", "globe_small",
    ],
    "chapel": [
        "prayer_bead", "incense_holder", "offering_bowl", "holy_water_vial",
    ],
    # Remaining room types from _ROOM_CONFIGS
    "smithy": [
        "hammer", "tongs", "metal_ingot", "coal_pile", "horseshoe", "grinding_stone",
    ],
    "storage": [
        "rope_coil", "broken_crate_lid", "loose_nail", "dust_rag", "old_sack",
    ],
    "barracks": [
        "boot", "ration_pouch", "playing_card", "dice", "canteen", "rolled_cloth",
    ],
    "guard_post": [
        "playing_card", "dice", "canteen", "torn_notice", "boot", "ration_pouch",
    ],
    "throne_room": [
        "goblet", "flower_arrangement", "parchment_scroll", "wax_seal", "quill_ink",
    ],
    "dungeon_cell": [
        "gnawed_bone", "torn_cloth", "rusted_chain_link", "straw_pile", "crude_cup",
    ],
    "study": [
        "open_book", "quill_ink", "scroll", "ink_pot", "loose_paper", "wax_candle",
    ],
    "great_hall": [
        "goblet", "plate", "candle_stub", "flower_arrangement", "discarded_bone",
    ],
    "armory": [
        "oilcloth", "whetstone", "broken_sword_hilt", "spare_buckle", "leather_strap",
    ],
    "shrine_room": [
        "prayer_bead", "incense_holder", "offering_bowl", "flower_offering", "votive_candle",
    ],
    "guard_barracks": [
        "boot", "canteen", "playing_card", "dice", "ration_pouch", "rolled_cloth",
    ],
    "treasury": [
        "coin_pile", "gem_chip", "wax_seal", "counting_stone", "old_ledger",
    ],
    "war_room": [
        "parchment_scroll", "quill_ink", "wax_seal", "miniature_soldier", "empty_goblet",
    ],
    "alchemy_lab": [
        "glass_vial", "mortar_pestle", "dried_herb", "stoppered_bottle", "crystal_shard",
    ],
    "torture_chamber": [
        "rusted_chain_link", "torn_cloth", "gnawed_bone", "broken_manacle", "dried_blood_rag",
    ],
    "crypt": [
        "prayer_bead", "flower_offering", "candle_stub", "offering_bowl", "skull_fragment",
    ],
    "dining_hall": [
        "plate", "goblet", "candle_stub", "discarded_bone", "bread_heel", "spilled_wine",
    ],
}

# Fallback pool for room types not explicitly listed
_DEFAULT_CLUTTER_POOL: list[str] = [
    "candle_stub", "dust_pile", "old_rag", "broken_cup", "loose_coin",
]


def _poisson_disk_scatter_2d(
    width: float,
    depth: float,
    min_distance: float,
    rng: random.Random,
    max_attempts: int = 30,
) -> list[tuple[float, float]]:
    """Bridson's Poisson disk sampling in 2D. Deterministic with the given rng.

    Returns a list of (x, y) sample points where no two points are closer
    than min_distance apart. Points are within [0, width] x [0, depth].
    """
    if min_distance <= 0 or width <= 0 or depth <= 0:
        return []

    cell_size = min_distance / math.sqrt(2.0)
    grid_cols = max(1, int(math.ceil(width / cell_size)))
    grid_rows = max(1, int(math.ceil(depth / cell_size)))
    grid: dict[tuple[int, int], tuple[float, float]] = {}

    def _grid_cell(px: float, py: float) -> tuple[int, int]:
        return int(px / cell_size), int(py / cell_size)

    def _has_neighbour_too_close(px: float, py: float) -> bool:
        gx, gy = _grid_cell(px, py)
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                neighbour = grid.get((gx + dx, gy + dy))
                if neighbour is not None:
                    dist_sq = (px - neighbour[0]) ** 2 + (py - neighbour[1]) ** 2
                    if dist_sq < min_distance * min_distance:
                        return True
        return False

    # Initial random point
    x0 = rng.uniform(0.0, width)
    y0 = rng.uniform(0.0, depth)
    samples: list[tuple[float, float]] = [(x0, y0)]
    active: list[tuple[float, float]] = [(x0, y0)]
    grid[_grid_cell(x0, y0)] = (x0, y0)

    while active:
        idx = rng.randint(0, len(active) - 1)
        ax, ay = active[idx]
        found = False
        for _ in range(max_attempts):
            angle = rng.uniform(0.0, 2.0 * math.pi)
            radius = rng.uniform(min_distance, 2.0 * min_distance)
            nx = ax + radius * math.cos(angle)
            ny = ay + radius * math.sin(angle)
            if 0.0 <= nx <= width and 0.0 <= ny <= depth:
                if not _has_neighbour_too_close(nx, ny):
                    samples.append((nx, ny))
                    active.append((nx, ny))
                    grid[_grid_cell(nx, ny)] = (nx, ny)
                    found = True
                    break
        if not found:
            active.pop(idx)

    return samples


def generate_clutter_layout(
    room_type: str,
    width: float,
    depth: float,
    furniture_items: list[dict],
    seed: int,
    density: float = 0.5,
) -> list[dict]:
    """Generate decorative clutter placement for a room.

    Identifies scatter surfaces from furniture bounding boxes (table tops,
    shelf tops, floor zones), samples candidate points via Poisson disk
    sampling, and assigns room-appropriate clutter items.

    Args:
        room_type: Key into CLUTTER_POOLS (e.g. "tavern", "kitchen").
        width: Room width in metres.
        depth: Room depth in metres.
        furniture_items: List of furniture dicts from generate_interior_layout().
            Each dict has 'type', 'position' [x, y, z], 'scale' [sx, sy, sz].
        seed: Random seed for deterministic output. Same seed = same layout.
        density: 0.0-1.0 multiplier. item_count = clamp(floor(5 + density*10), 5, 15).

    Returns:
        List of dicts: {name, position:(x,y,z), rotation:(rx,ry,rz),
                        scale:(sx,sy,sz), surface_parent}.
    """
    rng = random.Random(seed)
    pool = CLUTTER_POOLS.get(room_type, _DEFAULT_CLUTTER_POOL)
    if not pool:
        return []

    target_count = max(5, min(15, int(5 + density * 10)))

    # ---- Build scatter surfaces ----
    # Each surface: {"type": "table_top"|"shelf_top"|"floor", "cx", "cy", "z",
    #                "w", "d", "parent"}
    surfaces: list[dict] = []

    # Surface-eligible furniture types and the height offset to place on top
    _TABLE_TYPES = {"table", "long_table", "large_table", "workbench", "desk",
                    "serving_table", "bar_counter", "altar"}
    _SHELF_TYPES = {"shelf", "bookshelf", "shelf_with_bottles", "weapon_rack",
                    "display_case", "herb_rack", "tool_rack"}

    for item in furniture_items:
        itype = item.get("type", "")
        pos = item.get("position", [0.0, 0.0, 0.0])
        sc = item.get("scale", [1.0, 1.0, 1.0])
        cx, cy = float(pos[0]), float(pos[1])
        floor_z = float(pos[2]) if len(pos) > 2 else 0.0
        sw, sd, sh = float(sc[0]), float(sc[1]), float(sc[2])

        if itype in _TABLE_TYPES:
            surfaces.append({
                "surface_type": "table_top",
                "cx": cx, "cy": cy,
                "z": floor_z + sh,
                "w": sw * 0.8,  # inset slightly from edges
                "d": sd * 0.8,
                "parent": itype,
                "min_dist": 0.15,
            })
        elif itype in _SHELF_TYPES:
            # One scatter zone per shelf level (simplified: one top surface)
            surfaces.append({
                "surface_type": "shelf_top",
                "cx": cx, "cy": cy,
                "z": floor_z + sh * 0.6,  # mid-shelf level
                "w": sw * 0.7,
                "d": sd * 0.7,
                "parent": itype,
                "min_dist": 0.12,
            })

    # Always include floor scatter zones (corners + center strip)
    margin = 0.4
    floor_zones = [
        # Center strip
        {
            "surface_type": "floor",
            "cx": width / 2, "cy": depth / 2,
            "z": 0.0,
            "w": max(0.1, width - 2 * margin),
            "d": max(0.1, depth - 2 * margin),
            "parent": "floor",
            "min_dist": 0.25,
        },
    ]
    surfaces.extend(floor_zones)

    # ---- Sample points per surface using Poisson disk ----
    candidate_points: list[tuple[float, float, float, str]] = []  # (x, y, z, parent)

    for surf in surfaces:
        half_w = surf["w"] / 2.0
        half_d = surf["d"] / 2.0
        if half_w < 0.05 or half_d < 0.05:
            continue

        pts = _poisson_disk_scatter_2d(
            surf["w"], surf["d"], surf["min_dist"], rng,
        )
        for px, py in pts:
            world_x = round(surf["cx"] - half_w + px, 4)
            world_y = round(surf["cy"] - half_d + py, 4)
            world_z = round(surf["z"], 4)
            # Clamp to room bounds
            world_x = max(margin, min(width - margin, world_x))
            world_y = max(margin, min(depth - margin, world_y))
            candidate_points.append((world_x, world_y, world_z, surf["parent"]))

    if not candidate_points:
        # Fallback: uniform random floor points
        for _ in range(target_count):
            fx = rng.uniform(margin, width - margin)
            fy = rng.uniform(margin, depth - margin)
            candidate_points.append((round(fx, 4), round(fy, 4), 0.0, "floor"))

    # ---- Sample target_count points and assign clutter items ----
    rng.shuffle(candidate_points)
    selected = candidate_points[:target_count]

    result: list[dict] = []
    for x, y, z, parent in selected:
        item_name = rng.choice(pool)
        # Scale variation +/-15%
        base_scale = 1.0
        sv = round(base_scale * rng.uniform(0.85, 1.15), 4)
        rx = 0.0
        ry = 0.0
        rz = round(rng.uniform(0.0, 2.0 * math.pi), 4)

        result.append({
            "name": item_name,
            "position": (x, y, z),
            "rotation": (rx, ry, rz),
            "scale": (sv, sv, sv),
            "surface_parent": parent,
        })

    return result
