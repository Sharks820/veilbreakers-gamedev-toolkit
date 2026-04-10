"""Clothing mesh generation for VeilBreakers dark-fantasy characters.

Pure-logic module (NO bpy imports). Provides parametric clothing generators
for 12 garment types with multiple style variants each.  Every function
returns the same ``MeshSpec`` dict used by ``procedural_meshes.py``.

Garment types
-------------
- **Tunic** (5): peasant, noble, warrior, priest, tavern
- **Robe** (5): mage, monk, necromancer, royal, tattered
- **Cloak** (5): traveling, royal, assassin, tattered, fur_lined
- **Hood** (4): pointed, rounded, deep, chain_coif
- **Pants** (5): baggy, fitted, armored, tattered, noble
- **Shirt** (4): linen, padded, silk, ragged
- **Belt** (4): leather, rope, sash, chain
- **Scarf** (3): standard, wrapped, draped
- **Tabard** (3): plain, heraldic, split
- **Loincloth** (3): simple, layered, fringed
- **Bandage wrap** (3): arm, torso, head
- **Sash** (3): diagonal, waist, shoulder

Construction notes
~~~~~~~~~~~~~~~~~~
- Clothing is built from body-hugging quad grids offset along normals.
- Regular topology ensures cloth simulation compatibility.
- Vertex groups mark cloth_sim, pinned, hem, seam regions.
- UVs are laid out as flat sewing patterns for easy texturing.
- Robes/cloaks split draping lower portions into separate mesh pieces.
- Target poly counts: 800-4000 per garment for real-time use.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
FaceList = list[tuple[int, ...]]

# ---------------------------------------------------------------------------
# Style definitions
# ---------------------------------------------------------------------------

CLOTHING_STYLES: dict[str, list[str]] = {
    "tunic": ["peasant", "noble", "warrior", "priest", "tavern"],
    "robe": ["mage", "monk", "necromancer", "royal", "tattered"],
    "cloak": ["traveling", "royal", "assassin", "tattered", "fur_lined"],
    "hood": ["pointed", "rounded", "deep", "chain_coif"],
    "pants": ["baggy", "fitted", "armored", "tattered", "noble"],
    "shirt": ["linen", "padded", "silk", "ragged"],
    "belt": ["leather", "rope", "sash", "chain"],
    "scarf": ["standard", "wrapped", "draped"],
    "tabard": ["plain", "heraldic", "split"],
    "loincloth": ["simple", "layered", "fringed"],
    "bandage_wrap": ["arm", "torso", "head"],
    "sash": ["diagonal", "waist", "shoulder"],
}

ALL_CLOTHING_TYPES: list[str] = list(CLOTHING_STYLES.keys())

# Cloth thickness by material weight (metres)
_CLOTH_THICKNESS: dict[str, float] = {
    "silk": 0.003,
    "linen": 0.005,
    "wool": 0.008,
    "leather": 0.010,
    "padded": 0.012,
    "chain": 0.015,
    "heavy": 0.018,
}

# Body reference dimensions (standard humanoid, metres)
_BODY = {
    "shoulder_width": 0.42,
    "chest_radius": 0.15,
    "waist_radius": 0.13,
    "hip_radius": 0.14,
    "torso_height": 0.55,
    "leg_length": 0.85,
    "arm_length": 0.60,
    "head_radius": 0.11,
    "neck_radius": 0.06,
    "neck_height": 0.08,
    "thigh_radius": 0.08,
    "calf_radius": 0.05,
    "upper_arm_radius": 0.045,
    "forearm_radius": 0.035,
}

# Style-specific modifiers
_TUNIC_PARAMS: dict[str, dict[str, Any]] = {
    "peasant": {"length_factor": 0.6, "sleeve_length": 0.3, "flare": 0.15,
                "thickness": "linen", "collar": "round", "belt_line": True},
    "noble": {"length_factor": 0.7, "sleeve_length": 0.5, "flare": 0.10,
              "thickness": "silk", "collar": "high", "belt_line": True},
    "warrior": {"length_factor": 0.55, "sleeve_length": 0.2, "flare": 0.08,
                "thickness": "padded", "collar": "none", "belt_line": True},
    "priest": {"length_factor": 0.75, "sleeve_length": 0.55, "flare": 0.20,
               "thickness": "linen", "collar": "high", "belt_line": False},
    "tavern": {"length_factor": 0.5, "sleeve_length": 0.15, "flare": 0.12,
               "thickness": "linen", "collar": "v_neck", "belt_line": True},
}

_ROBE_PARAMS: dict[str, dict[str, Any]] = {
    "mage": {"length_factor": 1.0, "sleeve_width": 0.08, "flare": 0.25,
             "thickness": "wool", "hood_attached": True, "open_front": True},
    "monk": {"length_factor": 0.95, "sleeve_width": 0.06, "flare": 0.18,
             "thickness": "linen", "hood_attached": True, "open_front": False},
    "necromancer": {"length_factor": 1.0, "sleeve_width": 0.10, "flare": 0.30,
                    "thickness": "silk", "hood_attached": True, "open_front": True},
    "royal": {"length_factor": 1.0, "sleeve_width": 0.07, "flare": 0.22,
              "thickness": "silk", "hood_attached": False, "open_front": False},
    "tattered": {"length_factor": 0.9, "sleeve_width": 0.06, "flare": 0.20,
                 "thickness": "linen", "hood_attached": False, "open_front": True},
}

_CLOAK_PARAMS: dict[str, dict[str, Any]] = {
    "traveling": {"length_factor": 0.85, "width_factor": 0.9, "curve_depth": 0.12,
                  "thickness": "wool", "has_clasp": True},
    "royal": {"length_factor": 1.0, "width_factor": 1.0, "curve_depth": 0.10,
              "thickness": "silk", "has_clasp": True},
    "assassin": {"length_factor": 0.7, "width_factor": 0.75, "curve_depth": 0.14,
                 "thickness": "leather", "has_clasp": False},
    "tattered": {"length_factor": 0.8, "width_factor": 0.85, "curve_depth": 0.11,
                 "thickness": "linen", "has_clasp": False},
    "fur_lined": {"length_factor": 0.90, "width_factor": 0.95, "curve_depth": 0.13,
                  "thickness": "heavy", "has_clasp": True},
}

_PANTS_PARAMS: dict[str, dict[str, Any]] = {
    "baggy": {"tightness": 0.5, "length_factor": 1.0, "cuff": True,
              "thickness": "linen", "flare_bottom": 0.04},
    "fitted": {"tightness": 1.0, "length_factor": 1.0, "cuff": False,
               "thickness": "leather", "flare_bottom": 0.0},
    "armored": {"tightness": 0.8, "length_factor": 1.0, "cuff": False,
                "thickness": "padded", "flare_bottom": 0.01},
    "tattered": {"tightness": 0.7, "length_factor": 0.8, "cuff": False,
                 "thickness": "linen", "flare_bottom": 0.02},
    "noble": {"tightness": 0.9, "length_factor": 1.0, "cuff": True,
              "thickness": "silk", "flare_bottom": 0.0},
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _compute_dimensions(
    verts: list[Vec3],
) -> dict[str, float]:
    if not verts:
        return {"width": 0.0, "height": 0.0, "depth": 0.0}
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "depth": max(zs) - min(zs),
    }


def _make_result(
    name: str,
    vertices: list[Vec3],
    faces: FaceList,
    uvs: list[Vec2] | None = None,
    vertex_groups: dict[str, list[int]] | None = None,
    material_regions: dict[str, list[int]] | None = None,
    drape_mesh: MeshSpec | None = None,
    **extra_meta: Any,
) -> MeshSpec:
    dims = _compute_dimensions(vertices)
    result: MeshSpec = {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs or [],
        "vertex_groups": vertex_groups or {},
        "material_regions": material_regions or {},
        "metadata": {
            "name": name,
            "category": extra_meta.pop("category", "clothing"),
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "dimensions": dims,
            **extra_meta,
        },
    }
    if drape_mesh is not None:
        result["drape_mesh"] = drape_mesh
    return result


def _merge_meshes(
    *parts: tuple[list[Vec3], FaceList],
) -> tuple[list[Vec3], FaceList]:
    all_verts: list[Vec3] = []
    all_faces: FaceList = []
    for verts, faces in parts:
        offset = len(all_verts)
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces


def _pseudo_random(seed: float) -> float:
    """Deterministic pseudo-random 0..1 from a float seed."""
    return (math.sin(seed * 12.9898 + 78.233) * 43758.5453) % 1.0


# ---------------------------------------------------------------------------
# Core geometry generators
# ---------------------------------------------------------------------------


def _generate_tube_grid(
    center_y_start: float,
    center_y_end: float,
    radius_profile: list[float],
    circumference_segments: int,
    length_segments: int,
    center_x: float = 0.0,
    center_z: float = 0.0,
    y_curve_func: Any = None,
    z_offset_func: Any = None,
    open_front: bool = False,
    front_gap_angle: float = 0.0,
    tatter_factor: float = 0.0,
    tatter_seed: float = 0.0,
) -> tuple[list[Vec3], FaceList, list[Vec2], dict[str, list[int]]]:
    """Generate a tube-shaped clothing piece with regular quad grid topology.

    Returns vertices, faces, UVs, and vertex group index lists.
    The tube runs along Y axis from center_y_start to center_y_end.
    radius_profile controls radius at each ring (interpolated if len != length_segments+1).
    """
    verts: list[Vec3] = []
    uvs: list[Vec2] = []
    faces: FaceList = []
    vg_cloth_sim: list[int] = []
    vg_pinned: list[int] = []
    vg_hem: list[int] = []
    vg_seam: list[int] = []

    n_rings = length_segments + 1
    n_circ = circumference_segments

    # If open_front, we create an open tube with a gap
    arc_start = front_gap_angle / 2.0 if open_front else 0.0
    arc_end = (2.0 * math.pi - front_gap_angle / 2.0) if open_front else 2.0 * math.pi
    # For open front, add 1 extra segment column to close the UV seam
    actual_circ = n_circ + 1 if open_front else n_circ

    for ring_i in range(n_rings):
        t = ring_i / max(length_segments, 1)
        y = center_y_start + t * (center_y_end - center_y_start)

        # Apply Y curve
        if y_curve_func is not None:
            y = y_curve_func(t, y)

        # Interpolate radius from profile
        profile_t = t * (len(radius_profile) - 1)
        profile_idx = int(profile_t)
        profile_frac = profile_t - profile_idx
        if profile_idx >= len(radius_profile) - 1:
            r = radius_profile[-1]
        else:
            r = radius_profile[profile_idx] + profile_frac * (
                radius_profile[profile_idx + 1] - radius_profile[profile_idx]
            )

        z_off = 0.0
        if z_offset_func is not None:
            z_off = z_offset_func(t)

        for seg_i in range(actual_circ):
            if open_front:
                angle = arc_start + (arc_end - arc_start) * seg_i / n_circ
            else:
                angle = 2.0 * math.pi * seg_i / n_circ

            x = center_x + math.cos(angle) * r
            z = center_z + math.sin(angle) * r + z_off

            # Tatter: displace bottom vertices irregularly
            if tatter_factor > 0.0 and t > 0.75:
                tatter_t = (t - 0.75) / 0.25
                seed_v = tatter_seed + seg_i * 7.3 + ring_i * 13.7
                rnd = _pseudo_random(seed_v)
                y -= rnd * tatter_factor * tatter_t * abs(center_y_end - center_y_start) * 0.15

            vi = len(verts)
            verts.append((x, y, z))

            # UV: sewing pattern layout (flat)
            u = seg_i / n_circ if open_front else seg_i / n_circ
            v = t
            uvs.append((u, v))

            # Vertex group assignments
            if ring_i <= 1:
                vg_pinned.append(vi)
            else:
                vg_cloth_sim.append(vi)

            if ring_i == 0 or ring_i == n_rings - 1:
                vg_hem.append(vi)

            if open_front and (seg_i == 0 or seg_i == actual_circ - 1):
                vg_seam.append(vi)
            elif not open_front and seg_i == 0:
                vg_seam.append(vi)

    # Build faces
    for ring_i in range(length_segments):
        for seg_i in range(n_circ if open_front else n_circ):
            r0 = ring_i * actual_circ + seg_i
            if open_front:
                r1 = r0 + 1
                r2 = (ring_i + 1) * actual_circ + seg_i + 1
                r3 = (ring_i + 1) * actual_circ + seg_i
            else:
                r1 = ring_i * actual_circ + (seg_i + 1) % n_circ
                r2 = (ring_i + 1) * actual_circ + (seg_i + 1) % n_circ
                r3 = (ring_i + 1) * actual_circ + seg_i
            faces.append((r0, r1, r2, r3))

    vertex_groups = {
        "cloth_sim": vg_cloth_sim,
        "pinned": vg_pinned,
        "hem": vg_hem,
        "seam": vg_seam,
    }

    return verts, faces, uvs, vertex_groups


def _generate_sheet_grid(
    width: float,
    height: float,
    subdivs_x: int,
    subdivs_y: int,
    origin_y: float = 0.0,
    origin_z: float = 0.0,
    curve_func: Any = None,
    tatter_factor: float = 0.0,
    tatter_seed: float = 0.0,
) -> tuple[list[Vec3], FaceList, list[Vec2], dict[str, list[int]]]:
    """Generate a flat/curved sheet (for cloaks, tabards, scarves).

    Sheet hangs in the XY plane, with Z used for curvature/draping.
    """
    verts: list[Vec3] = []
    uvs: list[Vec2] = []
    faces: FaceList = []
    vg_cloth_sim: list[int] = []
    vg_pinned: list[int] = []
    vg_hem: list[int] = []
    vg_seam: list[int] = []

    for iy in range(subdivs_y + 1):
        ty = iy / subdivs_y
        y = origin_y + height * (1.0 - ty)  # top to bottom

        for ix in range(subdivs_x + 1):
            tx = ix / subdivs_x
            x = -width / 2.0 + tx * width
            z = origin_z

            if curve_func is not None:
                z = curve_func(tx, ty, z)

            # Tatter at bottom
            if tatter_factor > 0.0 and ty > 0.75:
                tatter_t = (ty - 0.75) / 0.25
                seed_v = tatter_seed + ix * 7.3 + iy * 13.7
                rnd = _pseudo_random(seed_v)
                y -= rnd * tatter_factor * tatter_t * height * 0.15

            vi = len(verts)
            verts.append((x, y, z))
            uvs.append((tx, 1.0 - ty))

            if iy <= 1:
                vg_pinned.append(vi)
            else:
                vg_cloth_sim.append(vi)

            if iy == 0 or iy == subdivs_y:
                vg_hem.append(vi)
            if ix == 0 or ix == subdivs_x:
                vg_seam.append(vi)

    cols = subdivs_x + 1
    for iy in range(subdivs_y):
        for ix in range(subdivs_x):
            v0 = iy * cols + ix
            v1 = v0 + 1
            v2 = v0 + cols + 1
            v3 = v0 + cols
            faces.append((v0, v1, v2, v3))

    vertex_groups = {
        "cloth_sim": vg_cloth_sim,
        "pinned": vg_pinned,
        "hem": vg_hem,
        "seam": vg_seam,
    }

    return verts, faces, uvs, vertex_groups


def _offset_mesh_outward(
    verts: list[Vec3],
    faces: FaceList,
    offset: float,
) -> list[Vec3]:
    """Push mesh outward along computed vertex normals by offset distance.

    Computes approximate per-vertex normals from face normals, then
    displaces each vertex outward.
    """
    n = len(verts)
    normals: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(n)]

    # Accumulate face normals
    for face in faces:
        if len(face) < 3:
            continue
        v0 = verts[face[0]]
        v1 = verts[face[1]]
        v2 = verts[face[2]]
        # Edge vectors
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        # Cross product
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        for idx in face:
            normals[idx][0] += nx
            normals[idx][1] += ny
            normals[idx][2] += nz

    # Normalize and offset
    result: list[Vec3] = []
    for i, v in enumerate(verts):
        nn = normals[i]
        length = math.sqrt(nn[0] ** 2 + nn[1] ** 2 + nn[2] ** 2)
        if length > 1e-8:
            nn[0] /= length
            nn[1] /= length
            nn[2] /= length
        result.append((
            v[0] + nn[0] * offset,
            v[1] + nn[1] * offset,
            v[2] + nn[2] * offset,
        ))
    return result


def _add_hem_detail(
    verts: list[Vec3],
    faces: FaceList,
    edge_indices: list[int],
    thickness: float,
) -> tuple[list[Vec3], FaceList]:
    """Add rolled/thickened hem at garment edges by extruding edge verts inward.

    Returns additional verts and faces to append.
    """
    if not edge_indices or thickness <= 0:
        return [], []

    new_verts: list[Vec3] = []
    new_faces: FaceList = []

    # Compute vertex normals for edge verts
    n = len(verts)
    normals: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(n)]
    for face in faces:
        if len(face) < 3:
            continue
        v0 = verts[face[0]]
        v1 = verts[face[1]]
        v2 = verts[face[2]]
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        for idx in face:
            normals[idx][0] += nx
            normals[idx][1] += ny
            normals[idx][2] += nz

    # Create offset verts and connecting faces
    base_offset = len(verts) + len(new_verts)  # will be adjusted by caller
    index_map: dict[int, int] = {}
    for i, vi in enumerate(edge_indices):
        nn = normals[vi]
        length = math.sqrt(nn[0] ** 2 + nn[1] ** 2 + nn[2] ** 2)
        if length > 1e-8:
            nn = [nn[0] / length, nn[1] / length, nn[2] / length]
        else:
            nn = [0.0, 1.0, 0.0]
        v = verts[vi]
        new_verts.append((
            v[0] + nn[0] * thickness,
            v[1] + nn[1] * thickness * 0.3,  # slight inward roll
            v[2] + nn[2] * thickness,
        ))
        index_map[vi] = base_offset + i

    # Connect adjacent edge verts with quads
    for i in range(len(edge_indices) - 1):
        v0 = edge_indices[i]
        v1 = edge_indices[i + 1]
        v2 = index_map[v1]
        v3 = index_map[v0]
        new_faces.append((v0, v1, v2, v3))

    return new_verts, new_faces


def _flatten_to_uv_pattern(
    verts: list[Vec3],
    faces: FaceList,
) -> list[Vec2]:
    """Create flat sewing-pattern UV layout from 3D garment.

    Uses simple cylindrical/planar projection normalized to 0-1 range.
    """
    if not verts:
        return []

    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max_x - min_x if max_x > min_x else 1.0
    range_y = max_y - min_y if max_y > min_y else 1.0

    uvs: list[Vec2] = []
    for v in verts:
        u = (v[0] - min_x) / range_x
        v_coord = (v[1] - min_y) / range_y
        uvs.append((max(0.0, min(1.0, u)), max(0.0, min(1.0, v_coord))))
    return uvs


# ---------------------------------------------------------------------------
# Sleeve generator
# ---------------------------------------------------------------------------


def _generate_sleeve(
    shoulder_x: float,
    shoulder_y: float,
    shoulder_z: float,
    length: float,
    upper_radius: float,
    lower_radius: float,
    segments: int = 8,
    rings: int = 6,
    side: float = 1.0,
) -> tuple[list[Vec3], FaceList, list[Vec2]]:
    """Generate a sleeve tube extending from the shoulder outward.

    Sleeves extend along the X axis (side=1 for right, side=-1 for left).
    """
    verts: list[Vec3] = []
    uvs: list[Vec2] = []
    faces: FaceList = []

    for ri in range(rings + 1):
        t = ri / rings
        x = shoulder_x + side * length * t
        y_c = shoulder_y - 0.02 * t  # slight droop
        z_c = shoulder_z
        r = upper_radius + t * (lower_radius - upper_radius)
        # Natural fabric drape: wider at bottom
        r *= 1.0 + 0.08 * math.sin(t * math.pi)

        for si in range(segments):
            angle = 2.0 * math.pi * si / segments
            y = y_c + math.cos(angle) * r
            z = z_c + math.sin(angle) * r
            verts.append((x, y, z))
            uvs.append((si / segments, t))

    for ri in range(rings):
        for si in range(segments):
            s_next = (si + 1) % segments
            r0 = ri * segments + si
            r1 = ri * segments + s_next
            r2 = (ri + 1) * segments + s_next
            r3 = (ri + 1) * segments + si
            faces.append((r0, r1, r2, r3))

    return verts, faces, uvs


# =========================================================================
# TUNIC GENERATOR
# =========================================================================


def generate_tunic(
    style: str = "peasant",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a tunic mesh with proper topology for cloth simulation.

    Tunics are torso-covering garments that fall to mid-thigh with short-to-medium
    sleeves. The mesh is built as a tube grid offset from body dimensions.
    """
    if style not in CLOTHING_STYLES["tunic"]:
        style = "peasant"

    params = _TUNIC_PARAMS[style]
    thickness = _CLOTH_THICKNESS[params["thickness"]]

    chest_r = (_BODY["chest_radius"] + thickness) * size
    waist_r = (_BODY["waist_radius"] + thickness) * size
    hip_r = (_BODY["hip_radius"] + thickness) * size
    torso_h = _BODY["torso_height"] * size
    length = torso_h * params["length_factor"]
    flare = params["flare"] * size

    # Radius profile: chest -> waist -> hip -> hem with flare
    profile = [
        chest_r * 1.05,     # collar
        chest_r,            # chest
        waist_r * 0.98,     # waist
        hip_r * 1.02,       # hip
        hip_r + flare,      # hem flare
    ]

    shoulder_y = torso_h * 0.9 * size
    hem_y = shoulder_y - length

    tatter_f = 0.8 if style == "priest" else 0.0
    tatter_s = 42.0 if style == "priest" else 0.0

    verts, faces, uvs, vgroups = _generate_tube_grid(
        center_y_start=shoulder_y,
        center_y_end=hem_y,
        radius_profile=profile,
        circumference_segments=16,
        length_segments=12,
        open_front=params["collar"] == "v_neck",
        front_gap_angle=0.8 if params["collar"] == "v_neck" else 0.0,
        tatter_factor=tatter_f,
        tatter_seed=tatter_s,
    )

    # Add sleeves
    sleeve_parts: list[tuple[list[Vec3], FaceList]] = []
    sl = params["sleeve_length"] * size
    if sl > 0.01:
        for side in (1.0, -1.0):
            sv, sf, _ = _generate_sleeve(
                shoulder_x=side * chest_r * 0.85,
                shoulder_y=shoulder_y - 0.03 * size,
                shoulder_z=0.0,
                length=sl,
                upper_radius=_BODY["upper_arm_radius"] * size + thickness,
                lower_radius=_BODY["forearm_radius"] * size + thickness * 0.8,
                segments=8,
                rings=max(4, int(sl * 20)),
                side=side,
            )
            sleeve_parts.append((sv, sf))

    # Merge sleeves
    all_parts = [(verts, faces)]
    all_parts.extend(sleeve_parts)
    final_verts, final_faces = _merge_meshes(*all_parts)

    # Recompute UVs for merged mesh
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    # Material regions
    body_vert_count = len(verts)
    mat_regions = {
        "outer_fabric": list(range(body_vert_count)),
        "inner_lining": [],
        "trim": list(range(body_vert_count, len(final_verts))),
    }

    return _make_result(
        name=f"tunic_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=vgroups,
        material_regions=mat_regions,
        clothing_type="tunic",
        style=style,
        has_sleeves=sl > 0.01,
    )


# =========================================================================
# ROBE GENERATOR
# =========================================================================


def generate_robe(
    style: str = "mage",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a full-length robe with optional hood and open front.

    Robes have a separate drape_mesh for the lower flowing portion that
    should be physics-enabled in cloth simulation.
    """
    if style not in CLOTHING_STYLES["robe"]:
        style = "mage"

    params = _ROBE_PARAMS[style]
    thickness = _CLOTH_THICKNESS[params["thickness"]]

    chest_r = (_BODY["chest_radius"] + thickness) * size
    waist_r = (_BODY["waist_radius"] + thickness) * size
    hip_r = (_BODY["hip_radius"] + thickness) * size
    torso_h = _BODY["torso_height"] * size
    leg_h = _BODY["leg_length"] * size
    total_h = (torso_h + leg_h) * params["length_factor"]
    flare = params["flare"] * size

    shoulder_y = torso_h * 0.9 * size
    hem_y = shoulder_y - total_h

    # Upper body (pinned) portion: shoulder to waist
    waist_y = shoulder_y - torso_h * 0.5

    # Upper body profile
    upper_profile = [
        chest_r * 1.08,  # collar
        chest_r * 1.02,  # upper chest
        chest_r,         # chest
        waist_r,         # waist
    ]

    open_front = params["open_front"]
    front_gap = 1.2 if open_front else 0.0

    tatter_f = 1.0 if style == "tattered" else 0.0

    upper_verts, upper_faces, upper_uvs, upper_vgroups = _generate_tube_grid(
        center_y_start=shoulder_y,
        center_y_end=waist_y,
        radius_profile=upper_profile,
        circumference_segments=18,
        length_segments=8,
        open_front=open_front,
        front_gap_angle=front_gap,
    )

    # Lower body (drape) portion: waist to hem -- SEPARATE mesh
    lower_profile = [
        waist_r * 1.02,
        hip_r * 1.05,
        hip_r + flare * 0.5,
        hip_r + flare * 0.8,
        hip_r + flare,
    ]

    lower_verts, lower_faces, lower_uvs, lower_vgroups = _generate_tube_grid(
        center_y_start=waist_y,
        center_y_end=hem_y,
        radius_profile=lower_profile,
        circumference_segments=18,
        length_segments=12,
        open_front=open_front,
        front_gap_angle=front_gap * 1.3,
        tatter_factor=tatter_f,
        tatter_seed=99.0,
    )

    # Mark all lower verts as cloth_sim, first ring as pinned
    lower_vgroups["cloth_sim"] = list(range(len(lower_verts)))
    lower_vgroups["pinned"] = list(range(18 + (1 if open_front else 0)))

    drape_mesh = _make_result(
        name=f"robe_{style}_drape",
        vertices=lower_verts,
        faces=lower_faces,
        uvs=lower_uvs,
        vertex_groups=lower_vgroups,
        clothing_type="robe_drape",
        is_drape=True,
    )

    # Add sleeves to upper body
    sleeve_parts: list[tuple[list[Vec3], FaceList]] = []
    sw = params["sleeve_width"]
    for side_val in (1.0, -1.0):
        sv, sf, _ = _generate_sleeve(
            shoulder_x=side_val * chest_r * 0.85,
            shoulder_y=shoulder_y - 0.03 * size,
            shoulder_z=0.0,
            length=_BODY["arm_length"] * 0.75 * size,
            upper_radius=_BODY["upper_arm_radius"] * size + thickness + sw * 0.5,
            lower_radius=_BODY["forearm_radius"] * size + thickness + sw,
            segments=8,
            rings=8,
            side=side_val,
        )
        sleeve_parts.append((sv, sf))

    # Merge upper body + sleeves
    all_parts = [(upper_verts, upper_faces)]
    all_parts.extend(sleeve_parts)
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    body_count = len(upper_verts)
    mat_regions = {
        "outer_fabric": list(range(body_count)),
        "inner_lining": [],
        "trim": list(range(body_count, len(final_verts))),
    }

    return _make_result(
        name=f"robe_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=upper_vgroups,
        material_regions=mat_regions,
        drape_mesh=drape_mesh,
        clothing_type="robe",
        style=style,
        has_drape=True,
        has_hood=params["hood_attached"],
        open_front=open_front,
    )


# =========================================================================
# CLOAK GENERATOR
# =========================================================================


def generate_cloak(
    style: str = "traveling",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a cloak/cape that drapes from the shoulders.

    Cloaks are sheet meshes with curvature, split into upper (pinned)
    and lower (drape) sections for cloth simulation.
    """
    if style not in CLOTHING_STYLES["cloak"]:
        style = "traveling"

    params = _CLOAK_PARAMS[style]
    thickness = _CLOTH_THICKNESS[params["thickness"]]

    width = _BODY["shoulder_width"] * params["width_factor"] * size * 1.3
    torso_h = _BODY["torso_height"] * size
    leg_h = _BODY["leg_length"] * size
    total_height = (torso_h + leg_h) * params["length_factor"]
    curve_depth = params["curve_depth"] * size

    shoulder_y = torso_h * 0.9 * size
    split_y = shoulder_y - torso_h * 0.4  # drape split at mid-torso

    tatter_f = 1.0 if style == "tattered" else 0.0

    # Upper cloak: attached to shoulders (pinned)
    def upper_curve(tx: float, ty: float, z: float) -> float:
        # Body-hugging curvature
        return z - curve_depth * math.sin(tx * math.pi) * (0.3 + ty * 0.7)

    upper_h = shoulder_y - split_y
    upper_verts, upper_faces, upper_uvs, upper_vgroups = _generate_sheet_grid(
        width=width,
        height=upper_h,
        subdivs_x=10,
        subdivs_y=6,
        origin_y=split_y,
        origin_z=-thickness,
        curve_func=upper_curve,
    )
    # All upper verts pinned
    upper_vgroups["pinned"] = list(range(len(upper_verts)))
    upper_vgroups["cloth_sim"] = []

    # Lower cloak: draping portion (physics-enabled)
    lower_h = total_height - upper_h

    def lower_curve(tx: float, ty: float, z: float) -> float:
        flare = 1.0 + ty * 0.3  # widen as it goes down
        return z - curve_depth * flare * math.sin(tx * math.pi) * 0.8

    lower_verts, lower_faces, lower_uvs, lower_vgroups = _generate_sheet_grid(
        width=width * 1.15,  # wider at bottom
        height=lower_h,
        subdivs_x=12,
        subdivs_y=10,
        origin_y=split_y - lower_h,
        origin_z=-thickness,
        curve_func=lower_curve,
        tatter_factor=tatter_f,
        tatter_seed=77.0,
    )
    lower_vgroups["cloth_sim"] = list(range(len(lower_verts)))
    lower_vgroups["pinned"] = list(range(12 + 1))  # first row

    drape_mesh = _make_result(
        name=f"cloak_{style}_drape",
        vertices=lower_verts,
        faces=lower_faces,
        uvs=lower_uvs,
        vertex_groups=lower_vgroups,
        clothing_type="cloak_drape",
        is_drape=True,
    )

    final_uvs = _flatten_to_uv_pattern(upper_verts, upper_faces)

    mat_regions = {
        "outer_fabric": list(range(len(upper_verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"cloak_{style}",
        vertices=upper_verts,
        faces=upper_faces,
        uvs=final_uvs,
        vertex_groups=upper_vgroups,
        material_regions=mat_regions,
        drape_mesh=drape_mesh,
        clothing_type="cloak",
        style=style,
        has_drape=True,
    )


# =========================================================================
# HOOD GENERATOR
# =========================================================================


def generate_hood(
    style: str = "rounded",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a hood mesh covering the head.

    Hoods are partial spherical shells that follow the head contour
    with an opening at the face.
    """
    if style not in CLOTHING_STYLES["hood"]:
        style = "rounded"

    head_r = _BODY["head_radius"] * size
    neck_r = _BODY["neck_radius"] * size
    thickness = _CLOTH_THICKNESS.get(
        "chain" if style == "chain_coif" else "wool",
        0.008,
    )

    hood_r = head_r + thickness
    segments = 14
    rings = 10

    verts: list[Vec3] = []
    faces: FaceList = []
    vg_pinned: list[int] = []
    vg_cloth_sim: list[int] = []

    head_center_y = _BODY["torso_height"] * 0.9 * size + _BODY["neck_height"] * size + head_r

    # Pointedness factor
    point_factor = 0.0
    if style == "pointed":
        point_factor = 0.4
    elif style == "deep":
        point_factor = -0.1  # deeper, wider

    # Face opening angle (from front center)
    face_angle = math.pi * 0.35
    if style == "deep":
        face_angle = math.pi * 0.28
    elif style == "chain_coif":
        face_angle = math.pi * 0.30

    for ri in range(rings + 1):
        phi = math.pi * 0.5 * ri / rings  # 0 (top) to pi/2 (equator)

        # Pointedness at top
        effective_r = hood_r
        if ri < rings * 0.3:
            t = ri / (rings * 0.3)
            effective_r = hood_r * (0.3 + 0.7 * t) * (1.0 + point_factor * (1.0 - t))

        ring_r = effective_r * math.sin(phi)
        y = head_center_y + effective_r * math.cos(phi)

        if style == "chain_coif" and ri == rings:
            y -= 0.02 * size  # extend lower for coif

        for si in range(segments):
            # Skip face-area segments
            angle = face_angle + (2.0 * math.pi - 2.0 * face_angle) * si / (segments - 1)
            x = ring_r * math.cos(angle)
            z = ring_r * math.sin(angle)

            vi = len(verts)
            verts.append((x, y, z))

            if ri >= rings - 2:
                vg_pinned.append(vi)
            else:
                vg_cloth_sim.append(vi)

    # Build faces
    for ri in range(rings):
        for si in range(segments - 1):
            r0 = ri * segments + si
            r1 = ri * segments + si + 1
            r2 = (ri + 1) * segments + si + 1
            r3 = (ri + 1) * segments + si
            faces.append((r0, r1, r2, r3))

    uvs = _flatten_to_uv_pattern(verts, faces)

    vgroups = {
        "cloth_sim": vg_cloth_sim,
        "pinned": vg_pinned,
        "hem": [i for i in range(segments)],  # top ring
        "seam": [ri * segments for ri in range(rings + 1)] +
                [ri * segments + segments - 1 for ri in range(rings + 1)],
    }

    mat_regions = {
        "outer_fabric": list(range(len(verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"hood_{style}",
        vertices=verts,
        faces=faces,
        uvs=uvs,
        vertex_groups=vgroups,
        material_regions=mat_regions,
        clothing_type="hood",
        style=style,
    )


# =========================================================================
# PANTS GENERATOR
# =========================================================================


def generate_pants(
    style: str = "baggy",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate pants mesh as two leg tubes joined at the waist.

    Pants use a waistband (pinned) with two separate leg tubes
    that have proper topology for cloth simulation.
    """
    if style not in CLOTHING_STYLES["pants"]:
        style = "baggy"

    params = _PANTS_PARAMS[style]
    thickness = _CLOTH_THICKNESS[params["thickness"]]
    tightness = params["tightness"]

    waist_r = (_BODY["waist_radius"] + thickness) * size
    hip_r = (_BODY["hip_radius"] + thickness) * size
    thigh_r = (_BODY["thigh_radius"] + thickness) * size
    calf_r = (_BODY["calf_radius"] + thickness) * size
    leg_length = _BODY["leg_length"] * size * params["length_factor"]
    flare = params["flare_bottom"] * size

    waist_y = _BODY["torso_height"] * 0.4 * size
    crotch_y = waist_y - 0.15 * size
    ankle_y = waist_y - leg_length

    # Looseness factor
    loose = 1.0 + (1.0 - tightness) * 0.5

    tatter_f = 0.6 if style == "tattered" else 0.0

    # Waistband: tube around waist
    waist_verts, waist_faces, waist_uvs, waist_vgroups = _generate_tube_grid(
        center_y_start=waist_y,
        center_y_end=crotch_y,
        radius_profile=[waist_r, waist_r * 0.98, hip_r],
        circumference_segments=16,
        length_segments=4,
    )
    waist_vgroups["pinned"] = list(range(len(waist_verts)))
    waist_vgroups["cloth_sim"] = []

    # Left leg
    leg_sep = hip_r * 0.35  # separation between legs
    leg_profile = [
        thigh_r * loose,
        thigh_r * loose * 0.95,
        (thigh_r * 0.8 + calf_r * 0.2) * loose,
        calf_r * loose,
        calf_r * loose + flare,
    ]

    left_verts, left_faces, left_uvs, left_vgroups = _generate_tube_grid(
        center_y_start=crotch_y,
        center_y_end=ankle_y,
        radius_profile=leg_profile,
        circumference_segments=12,
        length_segments=10,
        center_x=-leg_sep,
        tatter_factor=tatter_f,
        tatter_seed=33.0,
    )

    right_verts, right_faces, right_uvs, right_vgroups = _generate_tube_grid(
        center_y_start=crotch_y,
        center_y_end=ankle_y,
        radius_profile=leg_profile,
        circumference_segments=12,
        length_segments=10,
        center_x=leg_sep,
        tatter_factor=tatter_f,
        tatter_seed=44.0,
    )

    # Merge all parts
    all_parts = [
        (waist_verts, waist_faces),
        (left_verts, left_faces),
        (right_verts, right_faces),
    ]
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    # Combine vertex groups
    waist_count = len(waist_verts)
    left_count = len(left_verts)
    combined_vgroups = {
        "cloth_sim": (
            left_vgroups["cloth_sim"] +
            [i + waist_count for i in left_vgroups["cloth_sim"]] +
            [i + waist_count + left_count for i in right_vgroups["cloth_sim"]]
        ),
        "pinned": waist_vgroups["pinned"],
        "hem": (
            [i + waist_count for i in left_vgroups["hem"]] +
            [i + waist_count + left_count for i in right_vgroups["hem"]]
        ),
        "seam": (
            waist_vgroups["seam"] +
            [i + waist_count for i in left_vgroups["seam"]] +
            [i + waist_count + left_count for i in right_vgroups["seam"]]
        ),
    }

    mat_regions = {
        "outer_fabric": list(range(len(final_verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"pants_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=combined_vgroups,
        material_regions=mat_regions,
        clothing_type="pants",
        style=style,
    )


# =========================================================================
# SHIRT GENERATOR
# =========================================================================


def generate_shirt(
    style: str = "linen",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a shirt mesh -- upper body covering with collar and sleeves."""
    if style not in CLOTHING_STYLES["shirt"]:
        style = "linen"

    thickness_map = {
        "linen": "linen",
        "padded": "padded",
        "silk": "silk",
        "ragged": "linen",
    }
    thickness = _CLOTH_THICKNESS[thickness_map[style]]

    chest_r = (_BODY["chest_radius"] + thickness) * size
    waist_r = (_BODY["waist_radius"] + thickness) * size

    shoulder_y = _BODY["torso_height"] * 0.9 * size
    hem_y = _BODY["torso_height"] * 0.35 * size  # shirt ends above hips

    # Padded is puffier
    puff = 1.15 if style == "padded" else 1.0
    # Silk is tighter
    tight = 0.95 if style == "silk" else 1.0

    profile = [
        chest_r * 1.05 * tight,
        chest_r * puff * tight,
        waist_r * 1.02 * tight * puff,
        waist_r * tight,
    ]

    tatter_f = 0.5 if style == "ragged" else 0.0

    verts, faces, uvs, vgroups = _generate_tube_grid(
        center_y_start=shoulder_y,
        center_y_end=hem_y,
        radius_profile=profile,
        circumference_segments=14,
        length_segments=8,
        tatter_factor=tatter_f,
        tatter_seed=55.0,
    )

    # Add sleeves
    sleeve_length = 0.45 * size if style != "ragged" else 0.30 * size
    sleeve_parts: list[tuple[list[Vec3], FaceList]] = []
    for side_val in (1.0, -1.0):
        sv, sf, _ = _generate_sleeve(
            shoulder_x=side_val * chest_r * 0.85,
            shoulder_y=shoulder_y - 0.03 * size,
            shoulder_z=0.0,
            length=sleeve_length,
            upper_radius=_BODY["upper_arm_radius"] * size + thickness,
            lower_radius=_BODY["forearm_radius"] * size + thickness * 0.7,
            segments=8,
            rings=6,
            side=side_val,
        )
        sleeve_parts.append((sv, sf))

    all_parts = [(verts, faces)]
    all_parts.extend(sleeve_parts)
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    body_count = len(verts)
    mat_regions = {
        "outer_fabric": list(range(body_count)),
        "inner_lining": [],
        "trim": list(range(body_count, len(final_verts))),
    }

    return _make_result(
        name=f"shirt_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=vgroups,
        material_regions=mat_regions,
        clothing_type="shirt",
        style=style,
        has_sleeves=True,
    )


# =========================================================================
# BELT GENERATOR
# =========================================================================


def generate_belt(
    style: str = "leather",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a belt mesh around the waist."""
    if style not in CLOTHING_STYLES["belt"]:
        style = "leather"

    waist_r = _BODY["waist_radius"] * size
    belt_width = 0.05 * size
    thickness = 0.008 * size

    if style == "rope":
        thickness = 0.012 * size
        belt_width = 0.03 * size
    elif style == "chain":
        thickness = 0.01 * size

    segments = 20
    rings = 4

    profile = [waist_r + thickness] * (rings + 1)
    belt_y = _BODY["torso_height"] * 0.4 * size

    verts, faces, uvs, vgroups = _generate_tube_grid(
        center_y_start=belt_y + belt_width / 2,
        center_y_end=belt_y - belt_width / 2,
        radius_profile=profile,
        circumference_segments=segments,
        length_segments=rings,
    )

    # Add buckle (small box at front)
    buckle_verts: list[Vec3] = []
    buckle_faces: FaceList = []
    bw = 0.025 * size
    bh = belt_width * 0.8
    bd = thickness * 2
    bx = waist_r + thickness + bd / 2
    by = belt_y

    # Buckle box
    hx, hy, hz = bw, bh / 2, bd / 2
    base = len(buckle_verts)
    buckle_verts.extend([
        (bx - hx, by - hy, -hz),
        (bx + hx, by - hy, -hz),
        (bx + hx, by + hy, -hz),
        (bx - hx, by + hy, -hz),
        (bx - hx, by - hy, hz),
        (bx + hx, by - hy, hz),
        (bx + hx, by + hy, hz),
        (bx - hx, by + hy, hz),
    ])
    buckle_faces.extend([
        (base + 0, base + 3, base + 2, base + 1),
        (base + 4, base + 5, base + 6, base + 7),
        (base + 0, base + 1, base + 5, base + 4),
        (base + 2, base + 3, base + 7, base + 6),
        (base + 0, base + 4, base + 7, base + 3),
        (base + 1, base + 2, base + 6, base + 5),
    ])

    all_parts = [(verts, faces), (buckle_verts, buckle_faces)]
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    # All belt verts are pinned (rigid)
    vgroups["pinned"] = list(range(len(final_verts)))
    vgroups["cloth_sim"] = []

    mat_regions = {
        "outer_fabric": list(range(len(verts))),
        "inner_lining": [],
        "trim": list(range(len(verts), len(final_verts))),
    }

    return _make_result(
        name=f"belt_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=vgroups,
        material_regions=mat_regions,
        clothing_type="belt",
        style=style,
    )


# =========================================================================
# SCARF GENERATOR
# =========================================================================


def generate_scarf(
    style: str = "standard",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a scarf mesh wrapping around the neck with a hanging tail."""
    if style not in CLOTHING_STYLES["scarf"]:
        style = "standard"

    neck_r = _BODY["neck_radius"] * size
    thickness = _CLOTH_THICKNESS["wool"]
    scarf_width = 0.08 * size
    tail_length = 0.25 * size

    if style == "wrapped":
        scarf_width = 0.12 * size
        tail_length = 0.15 * size
    elif style == "draped":
        scarf_width = 0.10 * size
        tail_length = 0.35 * size

    neck_y = _BODY["torso_height"] * 0.9 * size

    # Neck wrap portion
    wrap_verts, wrap_faces, wrap_uvs, wrap_vgroups = _generate_tube_grid(
        center_y_start=neck_y + scarf_width / 2,
        center_y_end=neck_y - scarf_width / 2,
        radius_profile=[neck_r + thickness, neck_r + thickness * 1.5, neck_r + thickness],
        circumference_segments=12,
        length_segments=3,
    )

    # Hanging tail: a sheet dangling from the front
    def tail_curve(tx: float, ty: float, z: float) -> float:
        return z + 0.02 * math.sin(ty * math.pi * 2) * size

    tail_verts, tail_faces, tail_uvs, tail_vgroups = _generate_sheet_grid(
        width=scarf_width * 0.8,
        height=tail_length,
        subdivs_x=4,
        subdivs_y=8,
        origin_y=neck_y - scarf_width / 2 - tail_length,
        origin_z=neck_r + thickness,
        curve_func=tail_curve,
    )

    all_parts = [(wrap_verts, wrap_faces), (tail_verts, tail_faces)]
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    wrap_count = len(wrap_verts)
    combined_vgroups = {
        "cloth_sim": [i + wrap_count for i in tail_vgroups["cloth_sim"]],
        "pinned": wrap_vgroups.get("pinned", []) + list(range(wrap_count)),
        "hem": [i + wrap_count for i in tail_vgroups["hem"]],
        "seam": wrap_vgroups.get("seam", []),
    }

    mat_regions = {
        "outer_fabric": list(range(len(final_verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"scarf_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=combined_vgroups,
        material_regions=mat_regions,
        clothing_type="scarf",
        style=style,
    )


# =========================================================================
# TABARD GENERATOR
# =========================================================================


def generate_tabard(
    style: str = "plain",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a tabard -- front/back panels hanging from shoulders.

    Tabards have separate front and back panels connected at the shoulders,
    with the sides open. The lower portions are drape-enabled.
    """
    if style not in CLOTHING_STYLES["tabard"]:
        style = "plain"

    chest_r = _BODY["chest_radius"] * size
    panel_width = _BODY["shoulder_width"] * 0.6 * size
    panel_length = _BODY["torso_height"] * 0.8 * size
    shoulder_y = _BODY["torso_height"] * 0.9 * size

    if style == "split":
        panel_width *= 0.8

    # Front panel
    def front_curve(tx: float, ty: float, z: float) -> float:
        return z + chest_r * 0.95 + 0.01 * math.sin(ty * math.pi)

    front_verts, front_faces, front_uvs, front_vgroups = _generate_sheet_grid(
        width=panel_width,
        height=panel_length,
        subdivs_x=6,
        subdivs_y=10,
        origin_y=shoulder_y - panel_length,
        origin_z=0.0,
        curve_func=front_curve,
    )

    # Back panel
    def back_curve(tx: float, ty: float, z: float) -> float:
        return z - chest_r * 0.95 - 0.01 * math.sin(ty * math.pi)

    back_verts, back_faces, back_uvs, back_vgroups = _generate_sheet_grid(
        width=panel_width,
        height=panel_length,
        subdivs_x=6,
        subdivs_y=10,
        origin_y=shoulder_y - panel_length,
        origin_z=0.0,
        curve_func=back_curve,
    )

    all_parts = [(front_verts, front_faces), (back_verts, back_faces)]
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    front_count = len(front_verts)
    combined_vgroups = {
        "cloth_sim": (
            front_vgroups["cloth_sim"] +
            [i + front_count for i in back_vgroups["cloth_sim"]]
        ),
        "pinned": (
            front_vgroups["pinned"] +
            [i + front_count for i in back_vgroups["pinned"]]
        ),
        "hem": (
            front_vgroups["hem"] +
            [i + front_count for i in back_vgroups["hem"]]
        ),
        "seam": (
            front_vgroups["seam"] +
            [i + front_count for i in back_vgroups["seam"]]
        ),
    }

    mat_regions = {
        "outer_fabric": list(range(len(final_verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"tabard_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=combined_vgroups,
        material_regions=mat_regions,
        clothing_type="tabard",
        style=style,
    )


# =========================================================================
# LOINCLOTH GENERATOR
# =========================================================================


def generate_loincloth(
    style: str = "simple",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a loincloth -- minimal waist covering."""
    if style not in CLOTHING_STYLES["loincloth"]:
        style = "simple"

    waist_r = _BODY["waist_radius"] * size
    panel_width = 0.15 * size
    panel_length = 0.25 * size
    waist_y = _BODY["torso_height"] * 0.4 * size
    thickness = _CLOTH_THICKNESS["linen"]

    if style == "layered":
        panel_width = 0.20 * size
        panel_length = 0.30 * size
    elif style == "fringed":
        panel_width = 0.18 * size

    # Waistband
    band_verts, band_faces, band_uvs, band_vgroups = _generate_tube_grid(
        center_y_start=waist_y + 0.02 * size,
        center_y_end=waist_y - 0.02 * size,
        radius_profile=[waist_r + thickness, waist_r + thickness],
        circumference_segments=14,
        length_segments=2,
    )
    band_vgroups["pinned"] = list(range(len(band_verts)))
    band_vgroups["cloth_sim"] = []

    # Front flap
    def front_curve(tx: float, ty: float, z: float) -> float:
        return z + waist_r + thickness + 0.005

    front_verts, front_faces, _, front_vgroups = _generate_sheet_grid(
        width=panel_width,
        height=panel_length,
        subdivs_x=4,
        subdivs_y=6,
        origin_y=waist_y - 0.02 * size - panel_length,
        curve_func=front_curve,
    )

    # Back flap
    def back_curve(tx: float, ty: float, z: float) -> float:
        return z - waist_r - thickness - 0.005

    back_verts, back_faces, _, back_vgroups = _generate_sheet_grid(
        width=panel_width,
        height=panel_length * 0.8,
        subdivs_x=4,
        subdivs_y=5,
        origin_y=waist_y - 0.02 * size - panel_length * 0.8,
        curve_func=back_curve,
    )

    all_parts = [(band_verts, band_faces), (front_verts, front_faces), (back_verts, back_faces)]
    final_verts, final_faces = _merge_meshes(*all_parts)
    final_uvs = _flatten_to_uv_pattern(final_verts, final_faces)

    band_count = len(band_verts)
    front_count = len(front_verts)
    combined_vgroups = {
        "cloth_sim": (
            [i + band_count for i in front_vgroups["cloth_sim"]] +
            [i + band_count + front_count for i in back_vgroups["cloth_sim"]]
        ),
        "pinned": band_vgroups["pinned"],
        "hem": (
            [i + band_count for i in front_vgroups["hem"]] +
            [i + band_count + front_count for i in back_vgroups["hem"]]
        ),
        "seam": [],
    }

    mat_regions = {
        "outer_fabric": list(range(len(final_verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"loincloth_{style}",
        vertices=final_verts,
        faces=final_faces,
        uvs=final_uvs,
        vertex_groups=combined_vgroups,
        material_regions=mat_regions,
        clothing_type="loincloth",
        style=style,
    )


# =========================================================================
# BANDAGE WRAP GENERATOR
# =========================================================================


def generate_bandage_wrap(
    style: str = "arm",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate bandage wrap strips -- wound wrapping for arms, torso, or head."""
    if style not in CLOTHING_STYLES["bandage_wrap"]:
        style = "arm"

    thickness = _CLOTH_THICKNESS["linen"] * 0.5  # thin bandage
    wrap_width = 0.03 * size  # narrow strips

    if style == "arm":
        # Spiral wrap around forearm
        center_r = _BODY["forearm_radius"] * size + thickness
        arm_length = 0.25 * size
        arm_y_start = _BODY["torso_height"] * 0.55 * size
        wraps = 5  # number of spiral turns
        segments_per_wrap = 12
        total_segments = wraps * segments_per_wrap

        verts: list[Vec3] = []
        faces: FaceList = []

        for i in range(total_segments + 1):
            t = i / total_segments
            angle = t * wraps * 2.0 * math.pi
            y = arm_y_start - t * arm_length
            # Inner edge
            r_inner = center_r
            x_in = _BODY["shoulder_width"] * 0.4 * size + math.cos(angle) * r_inner
            z_in = math.sin(angle) * r_inner
            verts.append((x_in, y, z_in))
            # Outer edge
            r_outer = center_r + wrap_width
            x_out = _BODY["shoulder_width"] * 0.4 * size + math.cos(angle) * r_outer
            z_out = math.sin(angle) * r_outer
            verts.append((x_out, y - wrap_width * 0.3, z_out))

        for i in range(total_segments):
            v0 = i * 2
            v1 = i * 2 + 1
            v2 = (i + 1) * 2 + 1
            v3 = (i + 1) * 2
            faces.append((v0, v3, v2, v1))

    elif style == "torso":
        # Horizontal wraps around torso
        chest_r = _BODY["chest_radius"] * size + thickness
        torso_y_top = _BODY["torso_height"] * 0.7 * size
        band_count = 4
        segments = 16

        verts = []
        faces = []

        for band in range(band_count):
            y_center = torso_y_top - band * wrap_width * 2.5
            base = len(verts)
            for si in range(segments + 1):
                angle = 2.0 * math.pi * si / segments
                # Inner ring
                x = math.cos(angle) * chest_r
                z = math.sin(angle) * chest_r
                verts.append((x, y_center + wrap_width / 2, z))
                # Outer ring
                x_o = math.cos(angle) * (chest_r + thickness)
                z_o = math.sin(angle) * (chest_r + thickness)
                verts.append((x_o, y_center - wrap_width / 2, z_o))

            for si in range(segments):
                v0 = base + si * 2
                v1 = base + si * 2 + 1
                v2 = base + (si + 1) * 2 + 1
                v3 = base + (si + 1) * 2
                faces.append((v0, v3, v2, v1))

    else:  # head
        head_r = _BODY["head_radius"] * size + thickness
        head_y = (_BODY["torso_height"] * 0.9 + _BODY["neck_height"] + _BODY["head_radius"]) * size
        wraps = 4
        segments_per_wrap = 10
        total_segments = wraps * segments_per_wrap

        verts = []
        faces = []

        for i in range(total_segments + 1):
            t = i / total_segments
            angle = t * wraps * 2.0 * math.pi
            # Spiral vertically around head
            phi = 0.3 + t * 1.2  # partial coverage
            r_ring = head_r * math.sin(phi)
            y = head_y + head_r * math.cos(phi)

            x_in = math.cos(angle) * r_ring
            z_in = math.sin(angle) * r_ring
            verts.append((x_in, y, z_in))

            r_out = r_ring + wrap_width
            x_out = math.cos(angle) * r_out
            z_out = math.sin(angle) * r_out
            verts.append((x_out, y + wrap_width * 0.2, z_out))

        for i in range(total_segments):
            v0 = i * 2
            v1 = i * 2 + 1
            v2 = (i + 1) * 2 + 1
            v3 = (i + 1) * 2
            faces.append((v0, v3, v2, v1))

    uvs = _flatten_to_uv_pattern(verts, faces)

    vgroups = {
        "cloth_sim": [],
        "pinned": list(range(len(verts))),  # bandages are tight-bound
        "hem": [],
        "seam": [],
    }

    mat_regions = {
        "outer_fabric": list(range(len(verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"bandage_wrap_{style}",
        vertices=verts,
        faces=faces,
        uvs=uvs,
        vertex_groups=vgroups,
        material_regions=mat_regions,
        clothing_type="bandage_wrap",
        style=style,
    )


# =========================================================================
# SASH GENERATOR
# =========================================================================


def generate_sash(
    style: str = "diagonal",
    size: float = 1.0,
    body_verts: list[Vec3] | None = None,
) -> MeshSpec:
    """Generate a sash -- diagonal/waist/shoulder fabric band."""
    if style not in CLOTHING_STYLES["sash"]:
        style = "diagonal"

    chest_r = _BODY["chest_radius"] * size
    thickness = _CLOTH_THICKNESS["silk"]
    sash_width = 0.06 * size

    if style == "diagonal":
        # Diagonal from shoulder to opposite hip
        shoulder_y = _BODY["torso_height"] * 0.88 * size
        hip_y = _BODY["torso_height"] * 0.35 * size

        def diag_curve(tx: float, ty: float, z: float) -> float:
            # Follow body surface
            t = ty
            r = chest_r * (1.0 - 0.1 * t) + thickness
            return z + r * math.cos(tx * math.pi * 0.5)

        verts, faces, uvs, vgroups = _generate_sheet_grid(
            width=sash_width,
            height=shoulder_y - hip_y,
            subdivs_x=3,
            subdivs_y=10,
            origin_y=hip_y,
            origin_z=0.0,
            curve_func=diag_curve,
        )

        # Rotate diagonally: shift x based on y
        rotated_verts: list[Vec3] = []
        min_y = min(v[1] for v in verts)
        max_y = max(v[1] for v in verts)
        y_range = max_y - min_y if max_y > min_y else 1.0
        for v in verts:
            t = (v[1] - min_y) / y_range
            x_shift = -chest_r * 0.6 + t * chest_r * 1.2
            rotated_verts.append((v[0] + x_shift, v[1], v[2]))
        verts = rotated_verts

    elif style == "waist":
        # Wide waist sash/cummerbund
        waist_r = _BODY["waist_radius"] * size + thickness
        waist_y = _BODY["torso_height"] * 0.42 * size
        sash_width = 0.10 * size

        verts, faces, uvs, vgroups = _generate_tube_grid(
            center_y_start=waist_y + sash_width / 2,
            center_y_end=waist_y - sash_width / 2,
            radius_profile=[waist_r, waist_r * 1.02, waist_r],
            circumference_segments=16,
            length_segments=4,
        )

    else:  # shoulder
        shoulder_y = _BODY["torso_height"] * 0.88 * size
        shoulder_r = _BODY["shoulder_width"] * 0.5 * size

        def shoulder_curve(tx: float, ty: float, z: float) -> float:
            return z + chest_r + thickness

        verts, faces, uvs, vgroups = _generate_sheet_grid(
            width=sash_width,
            height=0.20 * size,
            subdivs_x=3,
            subdivs_y=6,
            origin_y=shoulder_y - 0.20 * size,
            origin_z=0.0,
            curve_func=shoulder_curve,
        )

    final_uvs = _flatten_to_uv_pattern(verts, faces)

    mat_regions = {
        "outer_fabric": list(range(len(verts))),
        "inner_lining": [],
        "trim": [],
    }

    return _make_result(
        name=f"sash_{style}",
        vertices=verts,
        faces=faces,
        uvs=final_uvs,
        vertex_groups=vgroups,
        material_regions=mat_regions,
        clothing_type="sash",
        style=style,
    )


# =========================================================================
# Main entry point
# =========================================================================


CLOTHING_GENERATORS: dict[str, Any] = {
    "tunic": generate_tunic,
    "robe": generate_robe,
    "cloak": generate_cloak,
    "hood": generate_hood,
    "pants": generate_pants,
    "shirt": generate_shirt,
    "belt": generate_belt,
    "scarf": generate_scarf,
    "tabard": generate_tabard,
    "loincloth": generate_loincloth,
    "bandage_wrap": generate_bandage_wrap,
    "sash": generate_sash,
}


def generate_clothing(
    clothing_type: str,
    body_verts: list[Vec3] | None = None,
    size: float = 1.0,
    style: str = "default",
) -> MeshSpec:
    """Generate clothing mesh with proper topology for cloth simulation.

    Args:
        clothing_type: One of the 12 supported garment types.
        body_verts: Optional body vertices to drape over.
        size: Scale factor (1.0 = standard humanoid).
        style: Style variant; 'default' uses the first style for the type.

    Returns:
        MeshSpec with vertices, faces, vertex_groups, material_regions, uvs.
    """
    if clothing_type not in CLOTHING_GENERATORS:
        raise ValueError(
            f"Unknown clothing type '{clothing_type}'. "
            f"Must be one of: {list(CLOTHING_GENERATORS.keys())}"
        )

    gen = CLOTHING_GENERATORS[clothing_type]

    if style == "default":
        style = CLOTHING_STYLES[clothing_type][0]

    return gen(style=style, size=size, body_verts=body_verts)
