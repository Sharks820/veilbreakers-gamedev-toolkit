"""Equipment mesh generation, modular splitting, armor fitting, and icon rendering.

Provides:
- handle_equipment_generate_weapon: Parametric weapon mesh with empties and collision (EQUIP-01)
- handle_equipment_split_character: Split rigged mesh into modular armor-swappable parts (EQUIP-03)
- handle_equipment_fit_armor: Fit armor to character with surface deform + weight transfer (EQUIP-04)
- handle_equipment_render_icon: Render transparent equipment preview icon with studio lighting (EQUIP-05)

All handlers follow the standard handler pattern: def handler(params: dict) -> dict.
Only allowed imports are used: bpy, bmesh, mathutils, math, json.
"""

from __future__ import annotations

import math

import bmesh
import bpy
import mathutils


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_WEAPON_TYPES = frozenset({
    # Original 7
    "sword", "axe", "mace", "staff", "bow", "dagger", "shield",
    # Extended weapon types (synced with procedural_meshes.py generators)
    "hammer", "spear", "crossbow", "scythe", "flail", "whip",
    "claw", "tome", "greatsword", "curved_sword", "hand_axe",
    "battle_axe", "greataxe", "club", "warhammer", "halberd",
    "glaive", "shortbow", "longbow", "staff_magic", "wand",
    "throwing_knife",
})

# Weapon classification by grip/trail behaviour
_POLEARM_TYPES = frozenset({
    "spear", "halberd", "glaive",
})
_TWO_HANDED_TYPES = frozenset({
    "greatsword", "greataxe", "warhammer",
})
_RANGED_TYPES = frozenset({
    "bow", "crossbow", "shortbow", "longbow",
})
_MAGIC_TYPES = frozenset({
    "staff_magic", "wand", "tome",
})
_CHAIN_TYPES = frozenset({
    "flail", "whip",
})
_THROWN_TYPES = frozenset({
    "throwing_knife",
})

DEFAULT_BODY_PARTS = [
    "head", "torso", "upper_arms", "lower_arms",
    "upper_legs", "lower_legs", "feet",
]

DEFAULT_BODY_TYPES = ["default", "muscular", "slim"]


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_weapon_params(params: dict) -> dict:
    """Validate and normalise weapon generation parameters.

    Returns dict with weapon_type, length, width, material_name.
    """
    weapon_type = params.get("weapon_type", "sword").lower()
    if weapon_type not in VALID_WEAPON_TYPES:
        raise ValueError(
            f"Unknown weapon_type: {weapon_type!r}. "
            f"Valid: {sorted(VALID_WEAPON_TYPES)}"
        )
    length = float(params.get("length", 1.0))
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")

    width = float(params.get("blade_width", params.get("head_size", 0.15)))
    if width <= 0:
        raise ValueError(f"blade_width/head_size must be positive, got {width}")

    material_name = params.get("material_name", "")
    return {
        "weapon_type": weapon_type,
        "length": length,
        "width": width,
        "material_name": material_name,
    }


def _validate_split_params(params: dict) -> dict:
    """Validate character split parameters."""
    object_name = params.get("object_name", "")
    if not object_name:
        raise ValueError("object_name is required for character splitting")
    parts = params.get("parts", DEFAULT_BODY_PARTS)
    if not parts or not isinstance(parts, list):
        raise ValueError("parts must be a non-empty list of body part names")
    return {"object_name": object_name, "parts": parts}


def _validate_armor_params(params: dict) -> dict:
    """Validate armor fitting parameters."""
    armor_name = params.get("armor_object_name", "")
    char_name = params.get("character_object_name", "")
    if not armor_name:
        raise ValueError("armor_object_name is required")
    if not char_name:
        raise ValueError("character_object_name is required")
    use_shape_keys = bool(params.get("use_shape_keys", True))
    body_types = params.get("body_types", DEFAULT_BODY_TYPES)
    return {
        "armor_object_name": armor_name,
        "character_object_name": char_name,
        "use_shape_keys": use_shape_keys,
        "body_types": body_types,
    }


def _validate_icon_params(params: dict) -> dict:
    """Validate icon rendering parameters."""
    object_name = params.get("object_name", "")
    if not object_name:
        raise ValueError("object_name is required for icon rendering")
    output_path = params.get("output_path", "")
    if not output_path:
        raise ValueError("output_path is required for icon rendering")
    resolution = int(params.get("resolution", 256))
    if resolution < 16:
        raise ValueError(f"resolution must be >= 16, got {resolution}")
    camera_distance = float(params.get("camera_distance", 2.0))
    camera_angle = params.get("camera_angle", (30, 45, 0))
    background_alpha = float(params.get("background_alpha", 0.0))
    return {
        "object_name": object_name,
        "output_path": output_path,
        "resolution": resolution,
        "camera_distance": camera_distance,
        "camera_angle": tuple(camera_angle),
        "background_alpha": background_alpha,
    }


# ---------------------------------------------------------------------------
# Weapon mesh generators (bmesh-based)
# ---------------------------------------------------------------------------


def _create_sword_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create a tapered sword blade with cross-guard, hilt, and pommel."""
    # Blade -- tapered quad strip from base to tip
    blade_segs = 8
    blade_base_y = 0.3 * length  # blade starts above hilt
    blade_tip_y = length
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * (blade_tip_y - blade_base_y)
        # Taper from full width to 0 at tip
        hw = width * 0.5 * (1.0 - t * 0.9)
        depth = width * 0.1 * (1.0 - t * 0.8)
        bm.verts.new((-hw, y, depth))
        bm.verts.new((hw, y, depth))
        bm.verts.new((hw, y, -depth))
        bm.verts.new((-hw, y, -depth))

    bm.verts.ensure_lookup_table()
    # Connect blade quads
    for i in range(blade_segs):
        base = i * 4
        for j in range(4):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % 4]
            v2 = bm.verts[base + 4 + (j + 1) % 4]
            v3 = bm.verts[base + 4 + j]
            bm.faces.new((v0, v1, v2, v3))

    # Cross-guard -- flat wide piece at blade base
    guard_y = blade_base_y
    gw = width * 1.2
    gd = width * 0.3
    gh = width * 0.15
    base_idx = len(bm.verts)
    for dy in (-gh, gh):
        bm.verts.new((-gw, guard_y + dy, gd))
        bm.verts.new((gw, guard_y + dy, gd))
        bm.verts.new((gw, guard_y + dy, -gd))
        bm.verts.new((-gw, guard_y + dy, -gd))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        v0 = bm.verts[base_idx + j]
        v1 = bm.verts[base_idx + (j + 1) % 4]
        v2 = bm.verts[base_idx + 4 + (j + 1) % 4]
        v3 = bm.verts[base_idx + 4 + j]
        bm.faces.new((v0, v1, v2, v3))

    # Hilt -- simple cylinder-like quad strip
    hilt_segs = 4
    hilt_radius = width * 0.15
    hilt_bottom = 0.0
    hilt_top = blade_base_y
    base_idx = len(bm.verts)
    for i in range(hilt_segs + 1):
        t = i / hilt_segs
        y = hilt_bottom + t * (hilt_top - hilt_bottom)
        for a in range(4):
            angle = a * math.pi * 0.5
            bm.verts.new((math.cos(angle) * hilt_radius, y,
                          math.sin(angle) * hilt_radius))
    bm.verts.ensure_lookup_table()
    for i in range(hilt_segs):
        base = base_idx + i * 4
        for j in range(4):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % 4]
            v2 = bm.verts[base + 4 + (j + 1) % 4]
            v3 = bm.verts[base + 4 + j]
            bm.faces.new((v0, v1, v2, v3))

    # Pommel -- small sphere-like bump at bottom
    base_idx = len(bm.verts)
    pommel_r = width * 0.2
    bm.verts.new((0, -pommel_r * 0.5, 0))  # bottom center
    for a in range(6):
        angle = a * math.pi / 3
        bm.verts.new((math.cos(angle) * pommel_r, 0,
                      math.sin(angle) * pommel_r))
    bm.verts.ensure_lookup_table()
    center = bm.verts[base_idx]
    for a in range(6):
        v1 = bm.verts[base_idx + 1 + a]
        v2 = bm.verts[base_idx + 1 + (a + 1) % 6]
        bm.faces.new((center, v1, v2))


def _create_axe_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create axe with handle cylinder and wedge-shaped head."""
    # Handle -- cylinder
    handle_segs = 6
    handle_radius = width * 0.12
    sides = 6
    base_idx = len(bm.verts)
    for i in range(handle_segs + 1):
        t = i / handle_segs
        y = t * length * 0.7
        for a in range(sides):
            angle = a * 2 * math.pi / sides
            bm.verts.new((math.cos(angle) * handle_radius, y,
                          math.sin(angle) * handle_radius))
    bm.verts.ensure_lookup_table()
    for i in range(handle_segs):
        base = base_idx + i * sides
        for j in range(sides):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % sides]
            v2 = bm.verts[base + sides + (j + 1) % sides]
            v3 = bm.verts[base + sides + j]
            bm.faces.new((v0, v1, v2, v3))

    # Axe head -- wedge shape
    head_y = length * 0.65
    head_h = width * 0.8
    head_d = width * 0.1  # thin edge
    head_d_back = width * 0.3
    base_idx = len(bm.verts)
    # Front edge (thin cutting edge)
    bm.verts.new((width * 0.6, head_y - head_h * 0.5, head_d))
    bm.verts.new((width * 0.6, head_y + head_h * 0.5, head_d))
    bm.verts.new((width * 0.6, head_y + head_h * 0.5, -head_d))
    bm.verts.new((width * 0.6, head_y - head_h * 0.5, -head_d))
    # Back (thick near handle)
    bm.verts.new((0, head_y - head_h * 0.3, head_d_back))
    bm.verts.new((0, head_y + head_h * 0.3, head_d_back))
    bm.verts.new((0, head_y + head_h * 0.3, -head_d_back))
    bm.verts.new((0, head_y - head_h * 0.3, -head_d_back))
    bm.verts.ensure_lookup_table()
    # Connect front to back quads
    for j in range(4):
        v0 = bm.verts[base_idx + j]
        v1 = bm.verts[base_idx + (j + 1) % 4]
        v2 = bm.verts[base_idx + 4 + (j + 1) % 4]
        v3 = bm.verts[base_idx + 4 + j]
        bm.faces.new((v0, v1, v2, v3))


def _create_mace_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create mace with handle cylinder and spherical head."""
    # Handle
    handle_segs = 6
    handle_radius = width * 0.12
    sides = 6
    base_idx = len(bm.verts)
    for i in range(handle_segs + 1):
        t = i / handle_segs
        y = t * length * 0.65
        for a in range(sides):
            angle = a * 2 * math.pi / sides
            bm.verts.new((math.cos(angle) * handle_radius, y,
                          math.sin(angle) * handle_radius))
    bm.verts.ensure_lookup_table()
    for i in range(handle_segs):
        base = base_idx + i * sides
        for j in range(sides):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % sides]
            v2 = bm.verts[base + sides + (j + 1) % sides]
            v3 = bm.verts[base + sides + j]
            bm.faces.new((v0, v1, v2, v3))

    # Mace head -- sphere approximation using UV sphere rings
    head_center_y = length * 0.7
    head_radius = width * 0.5
    rings = 6
    sectors = 8
    base_idx = len(bm.verts)
    # Bottom pole
    bm.verts.new((0, head_center_y - head_radius, 0))
    for i in range(1, rings):
        phi = math.pi * i / rings
        ring_y = head_center_y - head_radius * math.cos(phi)
        ring_r = head_radius * math.sin(phi)
        for j in range(sectors):
            theta = 2 * math.pi * j / sectors
            bm.verts.new((ring_r * math.cos(theta), ring_y,
                          ring_r * math.sin(theta)))
    # Top pole
    bm.verts.new((0, head_center_y + head_radius, 0))
    bm.verts.ensure_lookup_table()

    # Bottom cap triangles
    bottom_pole = bm.verts[base_idx]
    for j in range(sectors):
        v1 = bm.verts[base_idx + 1 + j]
        v2 = bm.verts[base_idx + 1 + (j + 1) % sectors]
        bm.faces.new((bottom_pole, v1, v2))
    # Ring quads
    for i in range(rings - 2):
        for j in range(sectors):
            r1 = base_idx + 1 + i * sectors
            r2 = base_idx + 1 + (i + 1) * sectors
            v0 = bm.verts[r1 + j]
            v1 = bm.verts[r1 + (j + 1) % sectors]
            v2 = bm.verts[r2 + (j + 1) % sectors]
            v3 = bm.verts[r2 + j]
            bm.faces.new((v0, v1, v2, v3))
    # Top cap triangles
    top_pole = bm.verts[base_idx + 1 + (rings - 1) * sectors]
    last_ring = base_idx + 1 + (rings - 2) * sectors
    for j in range(sectors):
        v1 = bm.verts[last_ring + j]
        v2 = bm.verts[last_ring + (j + 1) % sectors]
        bm.faces.new((top_pole, v2, v1))


def _create_staff_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create staff with tapered cylinder and ornamental top sphere."""
    segs = 10
    sides = 6
    base_idx = len(bm.verts)
    for i in range(segs + 1):
        t = i / segs
        y = t * length
        # Slight taper: thicker at bottom, thinner at top
        radius = width * 0.1 * (1.0 - t * 0.3)
        for a in range(sides):
            angle = a * 2 * math.pi / sides
            bm.verts.new((math.cos(angle) * radius, y,
                          math.sin(angle) * radius))
    bm.verts.ensure_lookup_table()
    for i in range(segs):
        base = base_idx + i * sides
        for j in range(sides):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % sides]
            v2 = bm.verts[base + sides + (j + 1) % sides]
            v3 = bm.verts[base + sides + j]
            bm.faces.new((v0, v1, v2, v3))

    # Ornamental top sphere (crystal placeholder)
    orb_center_y = length + width * 0.15
    orb_radius = width * 0.2
    orb_rings = 4
    orb_sectors = 6
    base_idx = len(bm.verts)
    bm.verts.new((0, orb_center_y - orb_radius, 0))
    for i in range(1, orb_rings):
        phi = math.pi * i / orb_rings
        ry = orb_center_y - orb_radius * math.cos(phi)
        rr = orb_radius * math.sin(phi)
        for j in range(orb_sectors):
            theta = 2 * math.pi * j / orb_sectors
            bm.verts.new((rr * math.cos(theta), ry, rr * math.sin(theta)))
    bm.verts.new((0, orb_center_y + orb_radius, 0))
    bm.verts.ensure_lookup_table()

    bottom = bm.verts[base_idx]
    for j in range(orb_sectors):
        v1 = bm.verts[base_idx + 1 + j]
        v2 = bm.verts[base_idx + 1 + (j + 1) % orb_sectors]
        bm.faces.new((bottom, v1, v2))
    for i in range(orb_rings - 2):
        for j in range(orb_sectors):
            r1 = base_idx + 1 + i * orb_sectors
            r2 = base_idx + 1 + (i + 1) * orb_sectors
            v0 = bm.verts[r1 + j]
            v1 = bm.verts[r1 + (j + 1) % orb_sectors]
            v2 = bm.verts[r2 + (j + 1) % orb_sectors]
            v3 = bm.verts[r2 + j]
            bm.faces.new((v0, v1, v2, v3))
    top = bm.verts[base_idx + 1 + (orb_rings - 1) * orb_sectors]
    last_r = base_idx + 1 + (orb_rings - 2) * orb_sectors
    for j in range(orb_sectors):
        v1 = bm.verts[last_r + j]
        v2 = bm.verts[last_r + (j + 1) % orb_sectors]
        bm.faces.new((top, v2, v1))


def _create_bow_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create bow with curved limb arc and string line."""
    # Bow limb -- arc of vertices in a bezier-like curve
    limb_segs = 12
    limb_radius = width * 0.06
    sides = 4
    base_idx = len(bm.verts)
    for i in range(limb_segs + 1):
        t = i / limb_segs
        # Arc curve: x = curve_amount * sin(pi * t), y spans length
        y = -length * 0.5 + t * length
        x = width * 2.0 * math.sin(math.pi * t)
        # Slight taper at tips
        r = limb_radius * (1.0 - 0.5 * abs(t - 0.5))
        for a in range(sides):
            angle = a * math.pi * 0.5
            dx = math.cos(angle) * r
            dz = math.sin(angle) * r
            bm.verts.new((x + dx, y, dz))
    bm.verts.ensure_lookup_table()
    for i in range(limb_segs):
        base = base_idx + i * sides
        for j in range(sides):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % sides]
            v2 = bm.verts[base + sides + (j + 1) % sides]
            v3 = bm.verts[base + sides + j]
            bm.faces.new((v0, v1, v2, v3))

    # String -- thin line between bow endpoints
    string_radius = limb_radius * 0.2
    string_base_idx = len(bm.verts)
    for end_t in (0.0, 1.0):
        y = -length * 0.5 + end_t * length
        x = width * 2.0 * math.sin(math.pi * end_t)  # 0 at endpoints
        for a in range(4):
            angle = a * math.pi * 0.5
            bm.verts.new((x + math.cos(angle) * string_radius, y,
                          math.sin(angle) * string_radius))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        v0 = bm.verts[string_base_idx + j]
        v1 = bm.verts[string_base_idx + (j + 1) % 4]
        v2 = bm.verts[string_base_idx + 4 + (j + 1) % 4]
        v3 = bm.verts[string_base_idx + 4 + j]
        bm.faces.new((v0, v1, v2, v3))


def _create_dagger_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create dagger -- shorter, wider sword variant."""
    # Scale: shorter blade, wider proportionally
    blade_segs = 5
    blade_base_y = 0.3 * length
    blade_tip_y = length
    blade_width = width * 1.3  # wider proportionally than sword
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * (blade_tip_y - blade_base_y)
        hw = blade_width * 0.5 * (1.0 - t * 0.85)
        depth = blade_width * 0.08 * (1.0 - t * 0.7)
        bm.verts.new((-hw, y, depth))
        bm.verts.new((hw, y, depth))
        bm.verts.new((hw, y, -depth))
        bm.verts.new((-hw, y, -depth))

    bm.verts.ensure_lookup_table()
    for i in range(blade_segs):
        base = i * 4
        for j in range(4):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % 4]
            v2 = bm.verts[base + 4 + (j + 1) % 4]
            v3 = bm.verts[base + 4 + j]
            bm.faces.new((v0, v1, v2, v3))

    # Short guard
    guard_y = blade_base_y
    gw = blade_width * 0.8
    gd = blade_width * 0.2
    gh = blade_width * 0.1
    base_idx = len(bm.verts)
    for dy in (-gh, gh):
        bm.verts.new((-gw, guard_y + dy, gd))
        bm.verts.new((gw, guard_y + dy, gd))
        bm.verts.new((gw, guard_y + dy, -gd))
        bm.verts.new((-gw, guard_y + dy, -gd))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        v0 = bm.verts[base_idx + j]
        v1 = bm.verts[base_idx + (j + 1) % 4]
        v2 = bm.verts[base_idx + 4 + (j + 1) % 4]
        v3 = bm.verts[base_idx + 4 + j]
        bm.faces.new((v0, v1, v2, v3))

    # Hilt
    hilt_segs = 3
    hilt_radius = blade_width * 0.12
    base_idx = len(bm.verts)
    for i in range(hilt_segs + 1):
        t = i / hilt_segs
        y = t * blade_base_y
        for a in range(4):
            angle = a * math.pi * 0.5
            bm.verts.new((math.cos(angle) * hilt_radius, y,
                          math.sin(angle) * hilt_radius))
    bm.verts.ensure_lookup_table()
    for i in range(hilt_segs):
        base = base_idx + i * 4
        for j in range(4):
            v0 = bm.verts[base + j]
            v1 = bm.verts[base + (j + 1) % 4]
            v2 = bm.verts[base + 4 + (j + 1) % 4]
            v3 = bm.verts[base + 4 + j]
            bm.faces.new((v0, v1, v2, v3))


def _create_shield_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create kite-shaped shield with center boss bump."""
    # Kite shape -- elongated diamond with rounded top
    shield_width = width * 2.0
    shield_height = length
    segs_top = 6  # rounded top half
    segs_bottom = 3  # pointed bottom
    depth = width * 0.05  # flat shield

    base_idx = len(bm.verts)
    # Top curved section
    for i in range(segs_top + 1):
        t = i / segs_top
        angle = math.pi * t  # 0 to pi (left to right over top)
        x = shield_width * 0.5 * math.cos(angle)
        y = shield_height * 0.4 + shield_height * 0.3 * math.sin(angle)
        bm.verts.new((x, y, depth))
        bm.verts.new((x, y, -depth))

    # Bottom point
    bm.verts.new((0, 0, depth))
    bm.verts.new((0, 0, -depth))
    bm.verts.ensure_lookup_table()

    # Connect top curve quads
    for i in range(segs_top):
        f_idx = base_idx + i * 2
        bm.faces.new((
            bm.verts[f_idx], bm.verts[f_idx + 1],
            bm.verts[f_idx + 3], bm.verts[f_idx + 2],
        ))

    # Connect sides to bottom point
    bottom_front = bm.verts[base_idx + (segs_top + 1) * 2]
    bottom_back = bm.verts[base_idx + (segs_top + 1) * 2 + 1]
    # Left side (first top vertex to bottom)
    left_f = bm.verts[base_idx]
    left_b = bm.verts[base_idx + 1]
    bm.faces.new((left_f, bottom_front, bottom_back, left_b))
    # Right side (last top vertex to bottom)
    right_f = bm.verts[base_idx + segs_top * 2]
    right_b = bm.verts[base_idx + segs_top * 2 + 1]
    bm.faces.new((right_f, right_b, bottom_back, bottom_front))

    # Center boss (small hemisphere bump)
    boss_y = shield_height * 0.45
    boss_r = shield_width * 0.12
    boss_base_idx = len(bm.verts)
    # Center top
    bm.verts.new((0, boss_y, depth + boss_r))
    # Ring around boss
    for a in range(6):
        angle = a * math.pi / 3
        bm.verts.new((
            math.cos(angle) * boss_r,
            boss_y + math.sin(angle) * boss_r * 0.5,
            depth + boss_r * 0.5 * (1 + math.cos(angle * 0.5)),
        ))
    bm.verts.ensure_lookup_table()
    center = bm.verts[boss_base_idx]
    for a in range(6):
        v1 = bm.verts[boss_base_idx + 1 + a]
        v2 = bm.verts[boss_base_idx + 1 + (a + 1) % 6]
        bm.faces.new((center, v1, v2))


# ---------------------------------------------------------------------------
# Extended weapon mesh generators (23 new types)
# ---------------------------------------------------------------------------


def _create_hammer_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create warhammer-style weapon: long handle with box head."""
    _make_handle(bm, length * 0.75, width * 0.1, sides=6)
    # Box head at top
    head_y = length * 0.7
    hw = width * 0.4
    hd = width * 0.35
    hh = width * 0.25
    base_idx = len(bm.verts)
    for dy in (-hh, hh):
        bm.verts.new((-hw, head_y + dy, hd))
        bm.verts.new((hw, head_y + dy, hd))
        bm.verts.new((hw, head_y + dy, -hd))
        bm.verts.new((-hw, head_y + dy, -hd))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        v0 = bm.verts[base_idx + j]
        v1 = bm.verts[base_idx + (j + 1) % 4]
        v2 = bm.verts[base_idx + 4 + (j + 1) % 4]
        v3 = bm.verts[base_idx + 4 + j]
        bm.faces.new((v0, v1, v2, v3))
    # Cap faces
    bm.faces.new([bm.verts[base_idx + i] for i in range(4)])
    bm.faces.new([bm.verts[base_idx + 4 + i] for i in range(3, -1, -1)])


def _create_spear_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create spear: long thin shaft with pointed head."""
    _make_handle(bm, length * 0.85, width * 0.06, sides=6)
    # Spearhead -- elongated diamond
    head_base_y = length * 0.8
    head_tip_y = length
    segs = 4
    for i in range(segs + 1):
        t = i / segs
        y = head_base_y + t * (head_tip_y - head_base_y)
        hw = width * 0.3 * (1.0 - t)
        depth = width * 0.05 * (1.0 - t)
        bm.verts.new((-hw, y, depth))
        bm.verts.new((hw, y, depth))
        bm.verts.new((hw, y, -depth))
        bm.verts.new((-hw, y, -depth))
    bm.verts.ensure_lookup_table()
    base_idx = len(bm.verts) - (segs + 1) * 4
    for i in range(segs):
        b = base_idx + i * 4
        for j in range(4):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % 4],
                          bm.verts[b + 4 + (j + 1) % 4], bm.verts[b + 4 + j]))


def _create_crossbow_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create crossbow: stock + horizontal bow limbs."""
    # Stock
    _make_handle(bm, length * 0.6, width * 0.08, sides=4)
    # Horizontal bow limbs
    limb_segs = 6
    limb_r = width * 0.04
    base_idx = len(bm.verts)
    mid_y = length * 0.5
    for i in range(limb_segs + 1):
        t = i / limb_segs
        x = -width * 1.5 + t * width * 3.0
        curve_z = width * 0.3 * math.sin(math.pi * t)
        for a in range(4):
            angle = a * math.pi * 0.5
            bm.verts.new((x + math.cos(angle) * limb_r, mid_y,
                          curve_z + math.sin(angle) * limb_r))
    bm.verts.ensure_lookup_table()
    for i in range(limb_segs):
        b = base_idx + i * 4
        for j in range(4):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % 4],
                          bm.verts[b + 4 + (j + 1) % 4], bm.verts[b + 4 + j]))


def _create_scythe_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create scythe: long shaft with curved blade at top."""
    _make_handle(bm, length * 0.85, width * 0.07, sides=6)
    # Curved blade
    blade_segs = 8
    base_idx = len(bm.verts)
    blade_start_y = length * 0.8
    for i in range(blade_segs + 1):
        t = i / blade_segs
        angle = t * math.pi * 0.7
        x = width * 1.5 * math.sin(angle)
        y = blade_start_y + width * 0.8 * (1.0 - math.cos(angle))
        hw = width * 0.04 * (1.0 - t * 0.6)
        bm.verts.new((x, y, hw))
        bm.verts.new((x, y, -hw))
    bm.verts.ensure_lookup_table()
    for i in range(blade_segs):
        b = base_idx + i * 2
        bm.faces.new((bm.verts[b], bm.verts[b + 1],
                      bm.verts[b + 3], bm.verts[b + 2]))


def _create_flail_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create flail: handle + chain links + spiked ball head."""
    _make_handle(bm, length * 0.5, width * 0.1, sides=6)
    # Chain segment (simplified as thin cylinder sections)
    chain_y = length * 0.5
    for ci in range(3):
        seg_y = chain_y + ci * width * 0.3
        base_idx = len(bm.verts)
        for dy in (0, width * 0.2):
            for a in range(4):
                angle = a * math.pi * 0.5
                bm.verts.new((math.cos(angle) * width * 0.04,
                              seg_y + dy,
                              math.sin(angle) * width * 0.04))
        bm.verts.ensure_lookup_table()
        for j in range(4):
            bm.faces.new((bm.verts[base_idx + j], bm.verts[base_idx + (j + 1) % 4],
                          bm.verts[base_idx + 4 + (j + 1) % 4],
                          bm.verts[base_idx + 4 + j]))
    # Spiked ball head (reuse mace-style sphere)
    _make_sphere_head(bm, length * 0.5 + width * 1.2, width * 0.35,
                      rings=4, sectors=6)


def _create_whip_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create whip: handle with tapering segmented lash."""
    _make_handle(bm, length * 0.25, width * 0.1, sides=4)
    # Lash -- tapering segmented strip
    lash_segs = 12
    base_idx = len(bm.verts)
    for i in range(lash_segs + 1):
        t = i / lash_segs
        y = length * 0.25 + t * length * 0.75
        # Wave pattern + taper
        x = width * 0.3 * math.sin(t * math.pi * 3) * (1.0 - t * 0.8)
        r = width * 0.06 * (1.0 - t * 0.85)
        for a in range(4):
            angle = a * math.pi * 0.5
            bm.verts.new((x + math.cos(angle) * r, y, math.sin(angle) * r))
    bm.verts.ensure_lookup_table()
    for i in range(lash_segs):
        b = base_idx + i * 4
        for j in range(4):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % 4],
                          bm.verts[b + 4 + (j + 1) % 4], bm.verts[b + 4 + j]))


def _create_claw_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create claw weapon: knuckle guard with curved blades."""
    # Knuckle guard -- flat curved bar
    base_idx = len(bm.verts)
    guard_segs = 6
    for i in range(guard_segs + 1):
        t = i / guard_segs
        x = -width * 0.6 + t * width * 1.2
        y = 0.0
        bm.verts.new((x, y, width * 0.05))
        bm.verts.new((x, y, -width * 0.05))
        bm.verts.new((x, y + width * 0.15, width * 0.05))
        bm.verts.new((x, y + width * 0.15, -width * 0.05))
    bm.verts.ensure_lookup_table()
    for i in range(guard_segs):
        b = base_idx + i * 4
        for j in range(2):
            bm.faces.new((bm.verts[b + j], bm.verts[b + j + 2],
                          bm.verts[b + 4 + j + 2], bm.verts[b + 4 + j]))
    # Three curved blades
    for blade_i in range(3):
        blade_x = -width * 0.4 + blade_i * width * 0.4
        blade_base_idx = len(bm.verts)
        blade_segs = 5
        for i in range(blade_segs + 1):
            t = i / blade_segs
            cy = t * length * 0.8
            cz = -width * 0.1 * math.sin(t * math.pi * 0.5)
            hw = width * 0.02 * (1.0 - t * 0.7)
            bm.verts.new((blade_x - hw, cy, cz))
            bm.verts.new((blade_x + hw, cy, cz))
        bm.verts.ensure_lookup_table()
        for i in range(blade_segs):
            b = blade_base_idx + i * 2
            bm.faces.new((bm.verts[b], bm.verts[b + 1],
                          bm.verts[b + 3], bm.verts[b + 2]))


def _create_tome_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create tome/spellbook: thick rectangular book."""
    bw = width * 1.5
    bh = length * 0.6
    bd = width * 0.4
    base_idx = len(bm.verts)
    # 8 corners of the book box
    for z in (-bd, bd):
        bm.verts.new((-bw * 0.5, 0, z))
        bm.verts.new((bw * 0.5, 0, z))
        bm.verts.new((bw * 0.5, bh, z))
        bm.verts.new((-bw * 0.5, bh, z))
    bm.verts.ensure_lookup_table()
    # Front/back
    bm.faces.new([bm.verts[base_idx + i] for i in range(4)])
    bm.faces.new([bm.verts[base_idx + 4 + i] for i in range(3, -1, -1)])
    # Side quads
    for j in range(4):
        bm.faces.new((bm.verts[base_idx + j], bm.verts[base_idx + (j + 1) % 4],
                      bm.verts[base_idx + 4 + (j + 1) % 4],
                      bm.verts[base_idx + 4 + j]))
    # Spine ridge
    spine_idx = len(bm.verts)
    bm.verts.new((-bw * 0.55, 0, 0))
    bm.verts.new((-bw * 0.55, bh, 0))
    bm.verts.ensure_lookup_table()
    bm.faces.new((bm.verts[base_idx], bm.verts[base_idx + 3],
                  bm.verts[spine_idx + 1], bm.verts[spine_idx]))


def _create_greatsword_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create greatsword: scaled-up sword with wider blade."""
    _create_sword_mesh(bm, length * 1.4, width * 1.5)


def _create_curved_sword_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create curved sword (scimitar): blade with lateral curve."""
    blade_segs = 10
    blade_base_y = 0.3 * length
    blade_tip_y = length
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * (blade_tip_y - blade_base_y)
        curve_x = width * 0.4 * math.sin(t * math.pi * 0.5)
        hw = width * 0.45 * (1.0 - t * 0.85)
        depth = width * 0.08 * (1.0 - t * 0.7)
        bm.verts.new((curve_x - hw, y, depth))
        bm.verts.new((curve_x + hw, y, depth))
        bm.verts.new((curve_x + hw, y, -depth))
        bm.verts.new((curve_x - hw, y, -depth))
    bm.verts.ensure_lookup_table()
    for i in range(blade_segs):
        base = i * 4
        for j in range(4):
            bm.faces.new((bm.verts[base + j], bm.verts[base + (j + 1) % 4],
                          bm.verts[base + 4 + (j + 1) % 4], bm.verts[base + 4 + j]))
    # Hilt
    hilt_base = len(bm.verts)
    hilt_r = width * 0.12
    for i in range(5):
        t = i / 4
        y = t * blade_base_y
        for a in range(4):
            angle = a * math.pi * 0.5
            bm.verts.new((math.cos(angle) * hilt_r, y, math.sin(angle) * hilt_r))
    bm.verts.ensure_lookup_table()
    for i in range(4):
        b = hilt_base + i * 4
        for j in range(4):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % 4],
                          bm.verts[b + 4 + (j + 1) % 4], bm.verts[b + 4 + j]))


def _create_hand_axe_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create hand axe: shorter, lighter axe variant."""
    _create_axe_mesh(bm, length * 0.6, width * 0.8)


def _create_battle_axe_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create battle axe: double-headed axe."""
    _create_axe_mesh(bm, length, width)
    # Mirror the axe head to the other side
    head_y = length * 0.65
    head_h = width * 0.8
    head_d = width * 0.1
    head_d_back = width * 0.3
    base_idx = len(bm.verts)
    bm.verts.new((-width * 0.6, head_y - head_h * 0.5, head_d))
    bm.verts.new((-width * 0.6, head_y + head_h * 0.5, head_d))
    bm.verts.new((-width * 0.6, head_y + head_h * 0.5, -head_d))
    bm.verts.new((-width * 0.6, head_y - head_h * 0.5, -head_d))
    bm.verts.new((0, head_y - head_h * 0.3, head_d_back))
    bm.verts.new((0, head_y + head_h * 0.3, head_d_back))
    bm.verts.new((0, head_y + head_h * 0.3, -head_d_back))
    bm.verts.new((0, head_y - head_h * 0.3, -head_d_back))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        bm.faces.new((bm.verts[base_idx + j], bm.verts[base_idx + (j + 1) % 4],
                      bm.verts[base_idx + 4 + (j + 1) % 4],
                      bm.verts[base_idx + 4 + j]))


def _create_greataxe_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create greataxe: oversized two-handed axe."""
    _create_battle_axe_mesh(bm, length * 1.3, width * 1.4)


def _create_club_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create club: thick tapered cylinder, thicker at head."""
    segs = 8
    sides = 6
    base_idx = len(bm.verts)
    for i in range(segs + 1):
        t = i / segs
        y = t * length
        # Thicker at the top (inverted taper from staff)
        radius = width * 0.1 * (0.8 + t * 0.8)
        for a in range(sides):
            angle = a * 2 * math.pi / sides
            bm.verts.new((math.cos(angle) * radius, y, math.sin(angle) * radius))
    bm.verts.ensure_lookup_table()
    for i in range(segs):
        b = base_idx + i * sides
        for j in range(sides):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % sides],
                          bm.verts[b + sides + (j + 1) % sides],
                          bm.verts[b + sides + j]))


def _create_warhammer_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create warhammer: long handle with heavy rectangular head and spike."""
    _make_handle(bm, length * 0.75, width * 0.09, sides=6)
    # Heavy rectangular head
    head_y = length * 0.7
    hw = width * 0.5
    hd = width * 0.4
    hh = width * 0.2
    base_idx = len(bm.verts)
    for dy in (-hh, hh):
        bm.verts.new((-hw, head_y + dy, hd))
        bm.verts.new((hw, head_y + dy, hd))
        bm.verts.new((hw, head_y + dy, -hd))
        bm.verts.new((-hw, head_y + dy, -hd))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        bm.faces.new((bm.verts[base_idx + j], bm.verts[base_idx + (j + 1) % 4],
                      bm.verts[base_idx + 4 + (j + 1) % 4],
                      bm.verts[base_idx + 4 + j]))
    bm.faces.new([bm.verts[base_idx + i] for i in range(4)])
    bm.faces.new([bm.verts[base_idx + 4 + i] for i in range(3, -1, -1)])
    # Top spike
    spike_idx = len(bm.verts)
    bm.verts.new((0, head_y + hh + width * 0.5, 0))
    bm.verts.ensure_lookup_table()
    for i in range(4):
        bm.faces.new((bm.verts[base_idx + 4 + i],
                      bm.verts[base_idx + 4 + (i + 1) % 4],
                      bm.verts[spike_idx]))


def _create_halberd_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create halberd: long shaft + axe blade + spear tip."""
    _make_handle(bm, length * 0.9, width * 0.06, sides=6)
    # Axe blade on one side
    head_y = length * 0.8
    base_idx = len(bm.verts)
    bm.verts.new((width * 0.8, head_y - width * 0.4, width * 0.04))
    bm.verts.new((width * 0.8, head_y + width * 0.4, width * 0.04))
    bm.verts.new((width * 0.8, head_y + width * 0.4, -width * 0.04))
    bm.verts.new((width * 0.8, head_y - width * 0.4, -width * 0.04))
    bm.verts.new((0, head_y - width * 0.2, width * 0.1))
    bm.verts.new((0, head_y + width * 0.2, width * 0.1))
    bm.verts.new((0, head_y + width * 0.2, -width * 0.1))
    bm.verts.new((0, head_y - width * 0.2, -width * 0.1))
    bm.verts.ensure_lookup_table()
    for j in range(4):
        bm.faces.new((bm.verts[base_idx + j], bm.verts[base_idx + (j + 1) % 4],
                      bm.verts[base_idx + 4 + (j + 1) % 4],
                      bm.verts[base_idx + 4 + j]))
    # Spear tip
    tip_base = length * 0.88
    tip_end = length
    tip_idx = len(bm.verts)
    for i in range(3):
        t = i / 2
        y = tip_base + t * (tip_end - tip_base)
        hw = width * 0.15 * (1.0 - t)
        bm.verts.new((-hw, y, hw * 0.3))
        bm.verts.new((hw, y, hw * 0.3))
        bm.verts.new((hw, y, -hw * 0.3))
        bm.verts.new((-hw, y, -hw * 0.3))
    bm.verts.ensure_lookup_table()
    for i in range(2):
        b = tip_idx + i * 4
        for j in range(4):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % 4],
                          bm.verts[b + 4 + (j + 1) % 4], bm.verts[b + 4 + j]))


def _create_glaive_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create glaive: long shaft with single-edged blade at top."""
    _make_handle(bm, length * 0.85, width * 0.06, sides=6)
    # Wide blade at top
    blade_segs = 6
    base_idx = len(bm.verts)
    blade_start = length * 0.75
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_start + t * length * 0.25
        hw = width * 0.6 * (1.0 - t * 0.7)
        depth = width * 0.03 * (1.0 - t * 0.5)
        bm.verts.new((hw, y, depth))
        bm.verts.new((hw, y, -depth))
        bm.verts.new((-width * 0.02, y, -depth))
        bm.verts.new((-width * 0.02, y, depth))
    bm.verts.ensure_lookup_table()
    for i in range(blade_segs):
        b = base_idx + i * 4
        for j in range(4):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % 4],
                          bm.verts[b + 4 + (j + 1) % 4], bm.verts[b + 4 + j]))


def _create_shortbow_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create shortbow: smaller, more curved bow variant."""
    _create_bow_mesh(bm, length * 0.7, width * 0.8)


def _create_longbow_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create longbow: taller, straighter bow variant."""
    _create_bow_mesh(bm, length * 1.4, width * 0.6)


def _create_staff_magic_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create magic staff: ornate staff with crystal head and rune bands."""
    _create_staff_mesh(bm, length, width)
    # Add rune band rings along the shaft
    for ring_t in (0.3, 0.5):
        ring_y = ring_t * length
        ring_r = width * 0.14
        base_idx = len(bm.verts)
        for a in range(8):
            angle = a * math.pi * 0.25
            bm.verts.new((math.cos(angle) * ring_r, ring_y - width * 0.02,
                          math.sin(angle) * ring_r))
            bm.verts.new((math.cos(angle) * ring_r, ring_y + width * 0.02,
                          math.sin(angle) * ring_r))
        bm.verts.ensure_lookup_table()
        for a in range(8):
            b = base_idx + a * 2
            nb = base_idx + ((a + 1) % 8) * 2
            bm.faces.new((bm.verts[b], bm.verts[b + 1],
                          bm.verts[nb + 1], bm.verts[nb]))


def _create_wand_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create wand: short thin rod with ornate tip."""
    # Thin tapered shaft
    segs = 6
    sides = 6
    base_idx = len(bm.verts)
    for i in range(segs + 1):
        t = i / segs
        y = t * length * 0.5
        r = width * 0.05 * (1.0 - t * 0.2)
        for a in range(sides):
            angle = a * 2 * math.pi / sides
            bm.verts.new((math.cos(angle) * r, y, math.sin(angle) * r))
    bm.verts.ensure_lookup_table()
    for i in range(segs):
        b = base_idx + i * sides
        for j in range(sides):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % sides],
                          bm.verts[b + sides + (j + 1) % sides],
                          bm.verts[b + sides + j]))
    # Ornate tip (small orb)
    _make_sphere_head(bm, length * 0.5 + width * 0.08, width * 0.1,
                      rings=3, sectors=6)


def _create_throwing_knife_mesh(bm: bmesh.types.BMesh, length: float, width: float) -> None:
    """Create throwing knife: balanced flat blade."""
    blade_segs = 5
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = t * length * 0.4
        # Diamond cross-section, tapers to point
        hw = width * 0.4 * (1.0 - abs(t - 0.5) * 1.5) if t < 0.9 else width * 0.02
        depth = width * 0.02
        bm.verts.new((-hw, y, depth))
        bm.verts.new((hw, y, depth))
        bm.verts.new((hw, y, -depth))
        bm.verts.new((-hw, y, -depth))
    bm.verts.ensure_lookup_table()
    for i in range(blade_segs):
        base = i * 4
        for j in range(4):
            bm.faces.new((bm.verts[base + j], bm.verts[base + (j + 1) % 4],
                          bm.verts[base + 4 + (j + 1) % 4], bm.verts[base + 4 + j]))


# ---------------------------------------------------------------------------
# Shared bmesh helpers for extended generators
# ---------------------------------------------------------------------------


def _make_handle(bm: bmesh.types.BMesh, length: float, radius: float,
                 sides: int = 6) -> None:
    """Create a cylindrical handle from origin to (0, length, 0)."""
    segs = max(4, int(length / 0.15))
    base_idx = len(bm.verts)
    for i in range(segs + 1):
        t = i / segs
        y = t * length
        for a in range(sides):
            angle = a * 2 * math.pi / sides
            bm.verts.new((math.cos(angle) * radius, y, math.sin(angle) * radius))
    bm.verts.ensure_lookup_table()
    for i in range(segs):
        b = base_idx + i * sides
        for j in range(sides):
            bm.faces.new((bm.verts[b + j], bm.verts[b + (j + 1) % sides],
                          bm.verts[b + sides + (j + 1) % sides],
                          bm.verts[b + sides + j]))


def _make_sphere_head(bm: bmesh.types.BMesh, center_y: float, radius: float,
                      rings: int = 4, sectors: int = 6) -> None:
    """Create a sphere at (0, center_y, 0) with given radius."""
    base_idx = len(bm.verts)
    bm.verts.new((0, center_y - radius, 0))
    for i in range(1, rings):
        phi = math.pi * i / rings
        ry = center_y - radius * math.cos(phi)
        rr = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2 * math.pi * j / sectors
            bm.verts.new((rr * math.cos(theta), ry, rr * math.sin(theta)))
    bm.verts.new((0, center_y + radius, 0))
    bm.verts.ensure_lookup_table()

    bottom = bm.verts[base_idx]
    for j in range(sectors):
        bm.faces.new((bottom, bm.verts[base_idx + 1 + j],
                      bm.verts[base_idx + 1 + (j + 1) % sectors]))
    for i in range(rings - 2):
        for j in range(sectors):
            r1 = base_idx + 1 + i * sectors
            r2 = base_idx + 1 + (i + 1) * sectors
            bm.faces.new((bm.verts[r1 + j], bm.verts[r1 + (j + 1) % sectors],
                          bm.verts[r2 + (j + 1) % sectors], bm.verts[r2 + j]))
    top = bm.verts[base_idx + 1 + (rings - 1) * sectors]
    last_r = base_idx + 1 + (rings - 2) * sectors
    for j in range(sectors):
        bm.faces.new((top, bm.verts[last_r + (j + 1) % sectors],
                      bm.verts[last_r + j]))


# Dispatch table for weapon mesh generators
_WEAPON_GENERATORS = {
    # Original 7
    "sword": _create_sword_mesh,
    "axe": _create_axe_mesh,
    "mace": _create_mace_mesh,
    "staff": _create_staff_mesh,
    "bow": _create_bow_mesh,
    "dagger": _create_dagger_mesh,
    "shield": _create_shield_mesh,
    # Extended 16
    "hammer": _create_hammer_mesh,
    "spear": _create_spear_mesh,
    "crossbow": _create_crossbow_mesh,
    "scythe": _create_scythe_mesh,
    "flail": _create_flail_mesh,
    "whip": _create_whip_mesh,
    "claw": _create_claw_mesh,
    "tome": _create_tome_mesh,
    "greatsword": _create_greatsword_mesh,
    "curved_sword": _create_curved_sword_mesh,
    "hand_axe": _create_hand_axe_mesh,
    "battle_axe": _create_battle_axe_mesh,
    "greataxe": _create_greataxe_mesh,
    "club": _create_club_mesh,
    "warhammer": _create_warhammer_mesh,
    "halberd": _create_halberd_mesh,
    "glaive": _create_glaive_mesh,
    "shortbow": _create_shortbow_mesh,
    "longbow": _create_longbow_mesh,
    "staff_magic": _create_staff_magic_mesh,
    "wand": _create_wand_mesh,
    "throwing_knife": _create_throwing_knife_mesh,
}


# ---------------------------------------------------------------------------
# Weapon empty + collision helpers
# ---------------------------------------------------------------------------


def _compute_grip_point(weapon_type: str, length: float) -> tuple[float, float, float]:
    """Compute grip_point position based on weapon type.

    Categories:
    - Bladed 1H (sword, dagger, curved_sword, claw): near hilt
    - Polearms (spear, halberd, glaive): 1/3 from bottom
    - Two-handed (greatsword, greataxe, warhammer): lower grip + off-hand
    - Ranged (bow, crossbow, shortbow, longbow): center
    - Magic (staff_magic, wand, tome): center/bottom
    - Chain (flail, whip): handle end
    - Thrown (throwing_knife): center (balanced)
    - Blunt (mace, hammer, club): near bottom
    - Axes 1H (axe, hand_axe, battle_axe, scythe): near bottom
    - Shield: center back
    - Staff: near bottom (1/3)
    """
    if weapon_type in ("sword", "dagger", "curved_sword", "claw"):
        return (0.0, length * 0.15, 0.0)
    elif weapon_type in _POLEARM_TYPES:
        # Grip at 1/3 from bottom for leverage
        return (0.0, length * 0.33, 0.0)
    elif weapon_type in _TWO_HANDED_TYPES:
        # Main hand grip (off-hand computed separately if needed)
        return (0.0, length * 0.15, 0.0)
    elif weapon_type in _RANGED_TYPES:
        return (0.0, 0.0, 0.0)
    elif weapon_type in _MAGIC_TYPES:
        if weapon_type == "tome":
            return (0.0, length * 0.3, 0.0)
        return (0.0, length * 0.2, 0.0)
    elif weapon_type in _CHAIN_TYPES:
        return (0.0, length * 0.1, 0.0)
    elif weapon_type in _THROWN_TYPES:
        return (0.0, length * 0.2, 0.0)
    elif weapon_type == "shield":
        return (0.0, length * 0.4, 0.0)
    elif weapon_type in ("axe", "hand_axe", "battle_axe", "scythe"):
        return (0.0, length * 0.15, 0.0)
    elif weapon_type in ("mace", "hammer", "club"):
        return (0.0, length * 0.15, 0.0)
    elif weapon_type == "staff":
        return (0.0, length * 0.15, 0.0)
    else:
        return (0.0, length * 0.15, 0.0)


def _compute_trail_attach_top(weapon_type: str, length: float, width: float) -> tuple[float, float, float]:
    """Compute trail_attach_top (weapon tip / striking end).

    Categories:
    - Bladed: tip of blade
    - Polearms: full length (spear tip / blade top)
    - Two-handed: tip of oversized blade/head
    - Ranged: no trail (top of arc for bow types)
    - Magic: VFX emission point at top
    - Chain: head end (ball/lash tip)
    - Thrown: blade tip
    """
    if weapon_type in _RANGED_TYPES:
        return (width * 2.0, 0.0, 0.0)
    elif weapon_type == "shield":
        return (0.0, length * 0.7, 0.0)
    elif weapon_type in ("axe", "hand_axe"):
        return (width * 0.6, length * 0.65, 0.0)
    elif weapon_type in ("battle_axe", "greataxe"):
        return (width * 0.6, length * 0.65, 0.0)
    elif weapon_type == "scythe":
        return (width * 1.5, length * 0.9, 0.0)
    elif weapon_type in _POLEARM_TYPES:
        return (0.0, length, 0.0)
    elif weapon_type in _TWO_HANDED_TYPES:
        if weapon_type == "greatsword":
            return (0.0, length * 1.4, 0.0)
        return (0.0, length, 0.0)
    elif weapon_type in _MAGIC_TYPES:
        if weapon_type == "tome":
            return (0.0, length * 0.6, 0.0)
        return (0.0, length, 0.0)
    elif weapon_type in _CHAIN_TYPES:
        if weapon_type == "flail":
            return (0.0, length * 0.5 + width * 1.2, 0.0)
        return (0.0, length, 0.0)
    elif weapon_type == "claw":
        return (0.0, length * 0.8, 0.0)
    elif weapon_type in ("mace", "hammer", "club", "warhammer"):
        return (0.0, length, 0.0)
    else:
        return (0.0, length, 0.0)


def _compute_trail_attach_bottom(weapon_type: str, length: float, width: float) -> tuple[float, float, float]:
    """Compute trail_attach_bottom (blade base / just above guard).

    Categories:
    - Bladed: blade base / guard
    - Polearms: start of blade section
    - Two-handed: blade base
    - Ranged: no trail
    - Magic: shaft midpoint
    - Chain: where chain meets handle
    - Thrown: center
    """
    if weapon_type in ("sword", "dagger", "curved_sword"):
        return (0.0, length * 0.3, 0.0)
    elif weapon_type in _RANGED_TYPES:
        return (width * 2.0, 0.0, 0.0)
    elif weapon_type == "shield":
        return (0.0, length * 0.1, 0.0)
    elif weapon_type in ("axe", "hand_axe"):
        return (width * 0.6, length * 0.5, 0.0)
    elif weapon_type in ("battle_axe", "greataxe"):
        return (width * 0.6, length * 0.5, 0.0)
    elif weapon_type == "scythe":
        return (0.0, length * 0.8, 0.0)
    elif weapon_type in _POLEARM_TYPES:
        return (0.0, length * 0.75, 0.0)
    elif weapon_type in _TWO_HANDED_TYPES:
        if weapon_type == "greatsword":
            return (0.0, length * 0.3, 0.0)
        return (0.0, length * 0.5, 0.0)
    elif weapon_type in _MAGIC_TYPES:
        if weapon_type == "tome":
            return (0.0, 0.0, 0.0)
        return (0.0, length * 0.5, 0.0)
    elif weapon_type in _CHAIN_TYPES:
        return (0.0, length * 0.5, 0.0)
    elif weapon_type in _THROWN_TYPES:
        return (0.0, length * 0.1, 0.0)
    elif weapon_type == "claw":
        return (0.0, 0.0, 0.0)
    elif weapon_type in ("mace", "hammer", "club", "warhammer"):
        return (0.0, length * 0.5, 0.0)
    else:
        return (0.0, length * 0.3, 0.0)


# ---------------------------------------------------------------------------
# Handler: Weapon generation (EQUIP-01)
# ---------------------------------------------------------------------------


def handle_equipment_generate_weapon(params: dict) -> dict:
    """Generate parametric weapon mesh with empties and collision mesh (EQUIP-01).

    Params:
        weapon_type: str -- any of 23 types: sword, axe, mace, staff, bow,
            dagger, shield, hammer, spear, crossbow, scythe, flail, whip,
            claw, tome, greatsword, curved_sword, hand_axe, battle_axe,
            greataxe, club, warhammer, halberd, glaive, shortbow, longbow,
            staff_magic, wand, throwing_knife
        length: float -- weapon length (default 1.0)
        blade_width / head_size: float -- width parameter (default 0.15)
        material_name: str -- optional material to assign

    Returns dict with object_name, weapon_type, vertices, faces,
    empties list, collision_object_name.
    """
    validated = _validate_weapon_params(params)
    weapon_type = validated["weapon_type"]
    length = validated["length"]
    width = validated["width"]
    material_name = validated["material_name"]

    # Create mesh via bmesh
    bm = bmesh.new()
    try:
        generator = _WEAPON_GENERATORS[weapon_type]
        generator(bm, length, width)

        # Create Blender mesh data and object
        mesh_name = f"Weapon_{weapon_type}"
        mesh_data = bpy.data.meshes.new(mesh_name)
        bm.to_mesh(mesh_data)
        vertex_count = len(mesh_data.vertices)
        face_count = len(mesh_data.polygons)
    finally:
        bm.free()

    obj = bpy.data.objects.new(mesh_name, mesh_data)
    bpy.context.collection.objects.link(obj)

    # Smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Assign material if specified
    if material_name:
        mat = bpy.data.materials.get(material_name)
        if mat:
            obj.data.materials.append(mat)

    # Create child empties for attachment points
    grip_pos = _compute_grip_point(weapon_type, length)
    trail_top_pos = _compute_trail_attach_top(weapon_type, length, width)
    trail_bottom_pos = _compute_trail_attach_bottom(weapon_type, length, width)

    empties = []
    for empty_name, pos in [
        ("grip_point", grip_pos),
        ("trail_attach_top", trail_top_pos),
        ("trail_attach_bottom", trail_bottom_pos),
    ]:
        empty = bpy.data.objects.new(f"{mesh_name}_{empty_name}", None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.05
        empty.location = mathutils.Vector(pos)
        bpy.context.collection.objects.link(empty)
        empty.parent = obj
        empty.matrix_parent_inverse = obj.matrix_world.inverted()
        empties.append(empty_name)

    # Create collision mesh (simplified convex hull)
    collision_name = f"{mesh_name}_collision"
    collision_bm = bmesh.new()
    try:
        collision_bm.from_mesh(mesh_data)
        # Convex hull for collision approximation
        result = bmesh.ops.convex_hull(collision_bm, input=collision_bm.verts)
        # Remove interior geometry from convex hull
        interior = result.get("geom_interior", [])
        if interior:
            bmesh.ops.delete(collision_bm, geom=interior, context="VERTS")

        collision_mesh = bpy.data.meshes.new(collision_name)
        collision_bm.to_mesh(collision_mesh)
    finally:
        collision_bm.free()

    collision_obj = bpy.data.objects.new(collision_name, collision_mesh)
    collision_obj.display_type = "WIRE"
    bpy.context.collection.objects.link(collision_obj)
    collision_obj.parent = obj
    collision_obj.matrix_parent_inverse = obj.matrix_world.inverted()

    bpy.context.view_layer.update()

    return {
        "object_name": obj.name,
        "weapon_type": weapon_type,
        "vertices": vertex_count,
        "faces": face_count,
        "empties": empties,
        "collision_object_name": collision_obj.name,
    }


# ---------------------------------------------------------------------------
# Handler: Modular character mesh splitting (EQUIP-03)
# ---------------------------------------------------------------------------


def handle_equipment_split_character(params: dict) -> dict:
    """Split a rigged character mesh into modular parts by vertex groups (EQUIP-03).

    Params:
        object_name: str -- name of the character mesh object
        parts: list[str] -- body parts to split (default: head/torso/arms/legs/feet)

    Each separated part retains the same armature modifier pointing to the
    shared skeleton. Returns dict with original_name, parts list, armature_name.
    """
    validated = _validate_split_params(params)
    object_name = validated["object_name"]
    parts = validated["parts"]

    obj = bpy.data.objects.get(object_name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {object_name}")

    # Find armature modifier
    armature_mod = None
    armature_name = ""
    for mod in obj.modifiers:
        if mod.type == "ARMATURE":
            armature_mod = mod
            armature_name = mod.object.name if mod.object else ""
            break

    if not armature_mod:
        raise ValueError(
            f"Object {object_name!r} has no armature modifier. "
            "Character must be rigged before splitting."
        )

    # Verify vertex groups exist for requested parts
    vg_names = {vg.name for vg in obj.vertex_groups}
    missing = [p for p in parts if p not in vg_names]
    if missing:
        raise ValueError(
            f"Missing vertex groups for parts: {missing}. "
            f"Available groups: {sorted(vg_names)}"
        )

    result_parts = []

    for part_name in parts:
        # Select vertices by vertex group weight > 0.5
        vg_index = obj.vertex_groups[part_name].index

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")

        # Use bmesh to select vertices by weight
        bpy.ops.object.mode_set(mode="OBJECT")
        mesh = obj.data
        for v in mesh.vertices:
            v.select = False
            for g in v.groups:
                if g.group == vg_index and g.weight > 0.5:
                    v.select = True
                    break

        # Track existing objects before separation
        objects_before = set(bpy.data.objects[:])

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.separate(type="SELECTED")
        bpy.ops.object.mode_set(mode="OBJECT")

        # Find the newly separated object by diffing before/after
        separated_name = f"{object_name}_{part_name}"
        new_objects = [o for o in bpy.data.objects if o not in objects_before]
        for candidate in new_objects:
            if candidate.type == "MESH":
                candidate.name = separated_name
                # Ensure armature modifier on separated part
                has_armature = any(
                    m.type == "ARMATURE" for m in candidate.modifiers
                )
                if not has_armature and armature_mod.object:
                    arm_mod = candidate.modifiers.new(
                        name="Armature", type="ARMATURE"
                    )
                    arm_mod.object = armature_mod.object

                result_parts.append({
                    "name": candidate.name,
                    "vertices": len(candidate.data.vertices),
                    "faces": len(candidate.data.polygons),
                })
                break

    bpy.context.view_layer.update()

    return {
        "original_name": object_name,
        "parts": result_parts,
        "armature_name": armature_name,
    }


# ---------------------------------------------------------------------------
# Handler: Armor fitting (EQUIP-04)
# ---------------------------------------------------------------------------


def handle_equipment_fit_armor(params: dict) -> dict:
    """Fit armor mesh to character body with surface deform and weight transfer (EQUIP-04).

    Params:
        armor_object_name: str -- the armor mesh
        character_object_name: str -- the character body mesh
        use_shape_keys: bool -- create shape keys for body types (default True)
        body_types: list[str] -- body type names for shape keys

    Uses Surface Deform modifier to conform armor, Data Transfer modifier
    for weight transfer, and optionally creates shape keys for body variations.
    """
    validated = _validate_armor_params(params)
    armor_name = validated["armor_object_name"]
    char_name = validated["character_object_name"]
    use_shape_keys = validated["use_shape_keys"]
    body_types = validated["body_types"]

    armor_obj = bpy.data.objects.get(armor_name)
    if not armor_obj or armor_obj.type != "MESH":
        raise ValueError(f"Armor mesh not found: {armor_name}")

    char_obj = bpy.data.objects.get(char_name)
    if not char_obj or char_obj.type != "MESH":
        raise ValueError(f"Character mesh not found: {char_name}")

    # Find character armature
    char_armature = None
    for mod in char_obj.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            char_armature = mod.object
            break

    # Add Surface Deform modifier to armor, bind to character
    surf_mod = armor_obj.modifiers.new(name="SurfaceDeform", type="SURFACE_DEFORM")
    surf_mod.target = char_obj

    # Bind the surface deform
    bpy.ops.object.select_all(action="DESELECT")
    armor_obj.select_set(True)
    bpy.context.view_layer.objects.active = armor_obj
    bpy.ops.object.surfacedeform_bind(modifier=surf_mod.name)

    # Transfer vertex weights via Data Transfer modifier
    dt_mod = armor_obj.modifiers.new(name="DataTransfer", type="DATA_TRANSFER")
    dt_mod.object = char_obj
    dt_mod.use_vert_data = True
    dt_mod.data_types_verts = {"VGROUP_WEIGHTS"}
    dt_mod.vert_mapping = "NEAREST"

    # Apply data transfer
    bpy.ops.object.modifier_apply(modifier=dt_mod.name)
    weight_groups = len(armor_obj.vertex_groups)

    # Shape keys for body type variations
    shape_key_names = []
    if use_shape_keys and body_types:
        # Ensure armor has a basis shape key
        if not armor_obj.data.shape_keys:
            armor_obj.shape_key_add(name="Basis", from_mix=False)

        for body_type in body_types:
            # If character has a shape key for this body type, activate it
            if char_obj.data.shape_keys:
                sk = char_obj.data.shape_keys.key_blocks.get(body_type)
                if sk:
                    sk.value = 1.0

            # The surface deform will deform armor accordingly
            bpy.context.view_layer.update()

            # Save current armor shape as shape key
            sk_armor = armor_obj.shape_key_add(name=body_type, from_mix=False)
            shape_key_names.append(sk_armor.name)

            # Reset character shape key
            if char_obj.data.shape_keys:
                sk = char_obj.data.shape_keys.key_blocks.get(body_type)
                if sk:
                    sk.value = 0.0

    # Apply surface deform modifier (shape keys already captured)
    bpy.ops.object.select_all(action="DESELECT")
    armor_obj.select_set(True)
    bpy.context.view_layer.objects.active = armor_obj
    bpy.ops.object.modifier_apply(modifier=surf_mod.name)

    # Assign same armature as character
    armature_name = ""
    if char_armature:
        arm_mod = armor_obj.modifiers.new(name="Armature", type="ARMATURE")
        arm_mod.object = char_armature
        armature_name = char_armature.name

    bpy.context.view_layer.update()

    return {
        "armor_name": armor_obj.name,
        "character_name": char_obj.name,
        "shape_keys": shape_key_names,
        "weight_groups_transferred": weight_groups,
        "armature_name": armature_name,
    }


# ---------------------------------------------------------------------------
# Handler: Equipment preview icon rendering (EQUIP-05)
# ---------------------------------------------------------------------------


def handle_equipment_render_icon(params: dict) -> dict:
    """Render transparent equipment preview icon with studio lighting (EQUIP-05).

    Params:
        object_name: str -- the equipment object to render
        output_path: str -- file path for the PNG output
        resolution: int -- icon resolution (default 256)
        camera_distance: float -- camera distance from object (default 2.0)
        camera_angle: tuple -- (pitch, yaw, roll) in degrees (default (30, 45, 0))
        background_alpha: float -- background transparency (default 0.0)

    Creates temporary camera and 3-point studio lighting, renders to PNG
    with alpha channel, then cleans up temporary objects.
    """
    validated = _validate_icon_params(params)
    object_name = validated["object_name"]
    output_path = validated["output_path"]
    resolution = validated["resolution"]
    camera_distance = validated["camera_distance"]
    camera_angle = validated["camera_angle"]
    background_alpha = validated["background_alpha"]

    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object not found: {object_name}")

    # Calculate camera position from distance and angle
    pitch_rad = math.radians(camera_angle[0])
    yaw_rad = math.radians(camera_angle[1])
    roll_rad = math.radians(camera_angle[2])

    # Object center for camera target (world space)
    obj_center = mathutils.Vector(obj.location)
    if hasattr(obj, "bound_box") and obj.bound_box:
        bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        obj_center = sum(bbox, mathutils.Vector()) / 8

    cam_x = obj_center.x + camera_distance * math.cos(pitch_rad) * math.sin(yaw_rad)
    cam_y = obj_center.y + camera_distance * math.cos(pitch_rad) * math.cos(yaw_rad)
    cam_z = obj_center.z + camera_distance * math.sin(pitch_rad)

    # Track temporary objects for cleanup
    temp_objects = []

    # Create temporary camera
    cam_data = bpy.data.cameras.new("IconCamera")
    cam_obj = bpy.data.objects.new("IconCamera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (cam_x, cam_y, cam_z)
    temp_objects.append(cam_obj)

    # Point camera at object center
    direction = obj_center - cam_obj.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()
    cam_obj.rotation_euler.z += roll_rad

    # 3-point studio lighting setup
    light_configs = [
        ("KeyLight", "SUN", 3.0, (cam_x + 1.5, cam_y - 1.0, cam_z + 2.0)),
        ("FillLight", "AREA", 1.5, (cam_x - 2.0, cam_y - 0.5, cam_z + 1.0)),
        ("RimLight", "SPOT", 2.0, (cam_x - 0.5, cam_y + 2.0, cam_z + 1.5)),
    ]

    for light_name, light_type, energy, position in light_configs:
        light_data = bpy.data.lights.new(name=light_name, type=light_type)
        light_data.energy = energy
        light_obj = bpy.data.objects.new(light_name, light_data)
        light_obj.location = position
        bpy.context.collection.objects.link(light_obj)
        # Point light at object
        light_direction = obj_center - light_obj.location
        light_rot = light_direction.to_track_quat("-Z", "Y")
        light_obj.rotation_euler = light_rot.to_euler()
        temp_objects.append(light_obj)

    # Configure render settings
    scene = bpy.context.scene
    original_camera = scene.camera
    original_res_x = scene.render.resolution_x
    original_res_y = scene.render.resolution_y
    original_film_transparent = scene.render.film_transparent
    original_filepath = scene.render.filepath
    original_format = scene.render.image_settings.file_format
    original_color_mode = scene.render.image_settings.color_mode

    scene.camera = cam_obj
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.film_transparent = (background_alpha < 1e-9)
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    try:
        # Render
        bpy.ops.render.render(write_still=True)
    finally:
        # Restore original settings
        scene.camera = original_camera
        scene.render.resolution_x = original_res_x
        scene.render.resolution_y = original_res_y
        scene.render.film_transparent = original_film_transparent
        scene.render.filepath = original_filepath
        scene.render.image_settings.file_format = original_format
        scene.render.image_settings.color_mode = original_color_mode

        # Clean up temporary objects
        for temp_obj in temp_objects:
            bpy.data.objects.remove(temp_obj, do_unlink=True)

        bpy.context.view_layer.update()

    # Get file size (only using bpy-compatible approach)
    file_size = 0
    try:
        img = bpy.data.images.load(output_path)
        file_size = img.size[0] * img.size[1] * 4  # estimate RGBA bytes
        bpy.data.images.remove(img)
    except Exception:
        pass

    return {
        "object_name": object_name,
        "output_path": output_path,
        "resolution": resolution,
        "file_size_bytes": file_size,
    }
