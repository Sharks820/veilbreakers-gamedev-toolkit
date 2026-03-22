"""Armor system mesh generators for VeilBreakers dark-fantasy equipment.

Provides parametric armor piece generators across 12 equipment slots (52 style
variants total).  Every function is pure Python/math -- no ``bpy`` dependency --
and returns the same ``MeshSpec`` dict used by ``procedural_meshes.py``.

Slots & styles
--------------
- **Helmets** (5):  open_face, full_helm, hood, crown, skull_mask
- **Chest armor** (5):  plate, chain, leather, robes, light
- **Gauntlets** (3):  plate, leather, wraps
- **Boots** (3):  plate, leather, sandals
- **Pauldrons / shoulders** (3):  plate, fur, bone
- **Capes** (3):  full, half, tattered
- **Belts** (5):  leather, chain, rope, ornate, utility
- **Bracers** (5):  leather, metal_vambrace, enchanted, chain, bone
- **Rings** (5):  band, gem_set, rune_etched, signet, twisted
- **Amulets** (5):  pendant, choker, torc, medallion, holy_symbol
- **Back items** (5):  backpack, quiver, wings, trophy_mount, bedroll
- **Face items** (5):  mask, blindfold, war_paint_frame, plague_doctor, domino

Construction notes
~~~~~~~~~~~~~~~~~~
- Each piece is modelled to fit on a standardised humanoid body.
- Helmets are built around a head sphere (radius ~0.11 m).
- Chest armour is built around a torso capsule.
- Gauntlets / boots wrap around limb cylinders.
- Capes are curved sheet meshes.
- Belts/bracers wrap around waist/forearm cylinders.
- Rings/amulets are small accessory meshes.
- Back items mount to the upper back/shoulders.
- Face items overlay the face region.
- Target triangle counts: 1 500 -- 5 000 per piece.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# Utility helpers  (mirrored from procedural_meshes.py to stay self-contained)
# ---------------------------------------------------------------------------


def _compute_dimensions(
    verts: list[tuple[float, float, float]],
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
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    **extra_meta: Any,
) -> MeshSpec:
    dims = _compute_dimensions(vertices)
    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs or [],
        "metadata": {
            "name": name,
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "dimensions": dims,
            **extra_meta,
        },
    }


def _merge_meshes(
    *parts: tuple[list[tuple[float, float, float]], list[tuple[int, ...]]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    for verts, faces in parts:
        offset = len(all_verts)
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces


# -- primitive generators ---------------------------------------------------

def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    hx, hy, hz = sx, sy, sz
    verts = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (2, 3, 7, 6),
        (0, 4, 7, 3),
        (1, 2, 6, 5),
    ]
    return verts, faces


def _make_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(angle) * radius, cy_bottom, cz + math.sin(angle) * radius))
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(angle) * radius, cy_bottom + height, cz + math.sin(angle) * radius))
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((i, i2, segments + i2, segments + i))
    if cap_bottom:
        faces.append(tuple(range(segments - 1, -1, -1)))
    if cap_top:
        faces.append(tuple(segments + i for i in range(segments)))
    return verts, faces


def _make_tapered_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius_bottom: float, radius_top: float,
    height: float,
    segments: int = 12,
    rings: int = 1,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    total_rings = rings + 1
    for ring in range(total_rings):
        t = ring / max(rings, 1)
        y = cy_bottom + t * height
        r = radius_bottom + t * (radius_top - radius_bottom)
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            verts.append((cx + math.cos(angle) * r, y, cz + math.sin(angle) * r))
    for ring in range(rings):
        for i in range(segments):
            i2 = (i + 1) % segments
            r0 = ring * segments
            r1 = (ring + 1) * segments
            faces.append((r0 + i, r0 + i2, r1 + i2, r1 + i))
    if cap_bottom:
        faces.append(tuple(range(segments - 1, -1, -1)))
    if cap_top:
        last_ring = rings * segments
        faces.append(tuple(last_ring + i for i in range(segments)))
    return verts, faces


def _make_sphere(
    cx: float, cy: float, cz: float,
    radius: float,
    rings: int = 8,
    sectors: int = 12,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    verts.append((cx, cy - radius, cz))
    for i in range(1, rings):
        phi = math.pi * i / rings
        y = cy - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2.0 * math.pi * j / sectors
            verts.append((cx + ring_r * math.cos(theta), y, cz + ring_r * math.sin(theta)))
    verts.append((cx, cy + radius, cz))
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((0, 1 + j, 1 + j2))
    for i in range(rings - 2):
        for j in range(sectors):
            j2 = (j + 1) % sectors
            r0 = 1 + i * sectors
            r1 = 1 + (i + 1) * sectors
            faces.append((r0 + j, r1 + j, r1 + j2, r0 + j2))
    top_idx = len(verts) - 1
    last_ring_start = 1 + (rings - 2) * sectors
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((last_ring_start + j, top_idx, last_ring_start + j2))
    return verts, faces


def _make_cone(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(angle) * radius, cy_bottom, cz + math.sin(angle) * radius))
    verts.append((cx, cy_bottom + height, cz))
    apex = segments
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((i, i2, apex))
    faces.append(tuple(range(segments - 1, -1, -1)))
    return verts, faces


def _make_lathe(
    profile: list[tuple[float, float]],
    segments: int = 12,
    close_top: bool = False,
    close_bottom: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n_profile = len(profile)
    for i in range(n_profile):
        r, y = profile[i]
        for j in range(segments):
            angle = 2.0 * math.pi * j / segments
            verts.append((r * math.cos(angle), y, r * math.sin(angle)))
    for i in range(n_profile - 1):
        for j in range(segments):
            j2 = (j + 1) % segments
            r0 = i * segments
            r1 = (i + 1) * segments
            faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    if close_bottom and n_profile > 0:
        faces.append(tuple(range(segments - 1, -1, -1)))
    if close_top and n_profile > 0:
        last = (n_profile - 1) * segments
        faces.append(tuple(last + i for i in range(segments)))
    return verts, faces


def _make_torus_ring(
    cx: float, cy: float, cz: float,
    major_radius: float, minor_radius: float,
    major_segments: int = 16,
    minor_segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(major_segments):
        theta = 2.0 * math.pi * i / major_segments
        ct, st = math.cos(theta), math.sin(theta)
        for j in range(minor_segments):
            phi = 2.0 * math.pi * j / minor_segments
            cp, sp = math.cos(phi), math.sin(phi)
            r = major_radius + minor_radius * cp
            verts.append((cx + r * ct, cy + minor_radius * sp, cz + r * st))
    for i in range(major_segments):
        i_next = (i + 1) % major_segments
        for j in range(minor_segments):
            j_next = (j + 1) % minor_segments
            v0 = i * minor_segments + j
            v1 = i * minor_segments + j_next
            v2 = i_next * minor_segments + j_next
            v3 = i_next * minor_segments + j
            faces.append((v0, v1, v2, v3))
    return verts, faces


def _make_half_sphere(
    cx: float, cy: float, cz: float,
    radius: float,
    rings: int = 6,
    sectors: int = 12,
    top: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate upper or lower hemisphere."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    if top:
        # Equator ring first, then up to pole
        for i in range(rings + 1):
            phi = math.pi * 0.5 * i / rings
            y = cy + radius * math.sin(phi)
            ring_r = radius * math.cos(phi)
            if ring_r < 1e-6 and i == rings:
                # Pole
                verts.append((cx, y, cz))
                break
            for j in range(sectors):
                theta = 2.0 * math.pi * j / sectors
                verts.append((cx + ring_r * math.cos(theta), y, cz + ring_r * math.sin(theta)))
        n_full_rings = rings  # rings that have full vertex circles
        # Check if last ring is a pole
        is_pole = len(verts) == n_full_rings * sectors + 1
        for i in range(n_full_rings - 1):
            for j in range(sectors):
                j2 = (j + 1) % sectors
                r0 = i * sectors
                r1 = (i + 1) * sectors
                faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
        if is_pole:
            pole_idx = len(verts) - 1
            last_ring = (n_full_rings - 1) * sectors
            for j in range(sectors):
                j2 = (j + 1) % sectors
                faces.append((last_ring + j, last_ring + j2, pole_idx))
    else:
        # Below equator
        for i in range(rings + 1):
            phi = math.pi * 0.5 * i / rings
            y = cy - radius * math.sin(phi)
            ring_r = radius * math.cos(phi)
            if ring_r < 1e-6 and i == rings:
                verts.append((cx, y, cz))
                break
            for j in range(sectors):
                theta = 2.0 * math.pi * j / sectors
                verts.append((cx + ring_r * math.cos(theta), y, cz + ring_r * math.sin(theta)))
        n_full_rings = rings
        is_pole = len(verts) == n_full_rings * sectors + 1
        for i in range(n_full_rings - 1):
            for j in range(sectors):
                j2 = (j + 1) % sectors
                r0 = i * sectors
                r1 = (i + 1) * sectors
                faces.append((r0 + j, r1 + j, r1 + j2, r0 + j2))
        if is_pole:
            pole_idx = len(verts) - 1
            last_ring = (n_full_rings - 1) * sectors
            for j in range(sectors):
                j2 = (j + 1) % sectors
                faces.append((last_ring + j, pole_idx, last_ring + j2))
    return verts, faces


def _make_flat_mesh(
    width: float, depth: float,
    subdivs_x: int, subdivs_z: int,
    cy: float = 0.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a subdivided flat quad (XZ plane) centred at origin."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for iz in range(subdivs_z + 1):
        tz = iz / subdivs_z
        z = -depth / 2 + tz * depth
        for ix in range(subdivs_x + 1):
            tx = ix / subdivs_x
            x = -width / 2 + tx * width
            verts.append((x, cy, z))
    cols = subdivs_x + 1
    for iz in range(subdivs_z):
        for ix in range(subdivs_x):
            v0 = iz * cols + ix
            v1 = v0 + 1
            v2 = v0 + cols + 1
            v3 = v0 + cols
            faces.append((v0, v1, v2, v3))
    return verts, faces


# =========================================================================
# HELMET GENERATORS  (5 styles)
# =========================================================================

_HELMET_STYLES = ["open_face", "full_helm", "hood", "crown", "skull_mask"]


def generate_helmet_mesh(style: str = "open_face") -> MeshSpec:
    """Generate a helmet mesh in the requested style.

    Styles: open_face, full_helm, hood, crown, skull_mask.
    Built around a head sphere of radius ~0.11 m.
    """
    if style not in _HELMET_STYLES:
        style = "open_face"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hr = 0.11  # head radius
    segs = 12

    if style == "open_face":
        # Dome with cheek guards, nose guard, forehead plate
        profile = [
            (hr * 1.06, 0),
            (hr * 1.10, hr * 0.2),
            (hr * 1.12, hr * 0.5),
            (hr * 1.08, hr * 0.8),
            (hr * 0.80, hr * 1.05),
            (hr * 0.30, hr * 1.18),
        ]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((hv, hf))
        # Nose guard
        nv, nf = _make_box(0, hr * 0.35, hr * 1.12, hr * 0.05, hr * 0.30, hr * 0.02)
        parts.append((nv, nf))
        # Forehead plate
        fpv, fpf = _make_box(0, hr * 0.75, hr * 1.08, hr * 0.30, hr * 0.08, hr * 0.02)
        parts.append((fpv, fpf))
        # Cheek guards (left / right)
        for side in (-1.0, 1.0):
            cgv, cgf = _make_box(
                side * hr * 0.90, hr * 0.20, hr * 0.40,
                hr * 0.10, hr * 0.25, hr * 0.08,
            )
            parts.append((cgv, cgf))
        # Rim ring
        rv, rf = _make_torus_ring(0, hr * 0.02, 0, hr * 1.08, hr * 0.025,
                                  major_segments=segs, minor_segments=4)
        parts.append((rv, rf))

    elif style == "full_helm":
        # Enclosed helmet with visor slit, breathing holes, crest mount
        profile = [
            (hr * 0.90, -hr * 0.25),
            (hr * 1.12, 0),
            (hr * 1.15, hr * 0.35),
            (hr * 1.12, hr * 0.70),
            (hr * 0.85, hr * 1.05),
            (hr * 0.25, hr * 1.22),
        ]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((hv, hf))
        # Visor slit
        vs_verts = [
            (-hr * 0.45, hr * 0.32, hr * 1.15),
            (hr * 0.45, hr * 0.32, hr * 1.15),
            (hr * 0.45, hr * 0.40, hr * 1.15),
            (-hr * 0.45, hr * 0.40, hr * 1.15),
        ]
        vs_back = [(v[0], v[1], v[2] + hr * 0.025) for v in vs_verts]
        parts.append((vs_verts + vs_back, [
            (0, 1, 2, 3), (7, 6, 5, 4),
            (0, 4, 5, 1), (2, 6, 7, 3),
            (0, 3, 7, 4), (1, 5, 6, 2),
        ]))
        # Breathing holes (small cylinders on right cheek)
        for bh in range(4):
            by = hr * 0.10 + bh * hr * 0.08
            bv, bf = _make_cylinder(
                hr * 0.85, by, hr * 0.75,
                hr * 0.018, hr * 0.04, segments=5,
                cap_top=True, cap_bottom=True,
            )
            parts.append((bv, bf))
        # Crest mount ridge
        for ci in range(6):
            cx_c = 0.0
            cy_c = hr * 0.85 + ci * hr * 0.07
            cz_c = -hr * 0.15 + ci * hr * 0.12
            cv, cf = _make_box(cx_c, cy_c, cz_c, hr * 0.02, hr * 0.04, hr * 0.03)
            parts.append((cv, cf))

    elif style == "hood":
        # Cloth mesh with face shadow overhang
        profile = [
            (hr * 1.00, -hr * 0.40),
            (hr * 1.08, -hr * 0.10),
            (hr * 1.15, hr * 0.30),
            (hr * 1.12, hr * 0.70),
            (hr * 0.95, hr * 1.00),
            (hr * 0.55, hr * 1.15),
        ]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=False, close_top=True)
        parts.append((hv, hf))
        # Face shadow brim
        brim_profile = [
            (hr * 1.18, hr * 0.55),
            (hr * 1.25, hr * 0.65),
            (hr * 1.15, hr * 0.75),
        ]
        bv, bf = _make_lathe(brim_profile, segments=8, close_bottom=False, close_top=False)
        # Only keep front half by filtering verts with z > -0.01
        parts.append((bv, bf))
        # Drape tail at back
        dv, df = _make_box(0, -hr * 0.20, -hr * 0.80, hr * 0.35, hr * 0.55, hr * 0.04)
        parts.append((dv, df))
        # Fold wrinkles
        for wi in range(3):
            wy = hr * 0.2 + wi * hr * 0.25
            wv, wf = _make_torus_ring(0, wy, 0, hr * 1.10, hr * 0.015,
                                      major_segments=segs, minor_segments=3)
            parts.append((wv, wf))

    elif style == "crown":
        # Thin metallic band with gem sockets
        # Base band
        bv, bf = _make_torus_ring(0, hr * 0.45, 0, hr * 1.06, hr * 0.06,
                                  major_segments=segs, minor_segments=5)
        parts.append((bv, bf))
        # Prong points (5 prongs)
        for pi in range(5):
            pa = pi * math.pi * 2 / 5
            px = math.cos(pa) * hr * 1.06
            pz = math.sin(pa) * hr * 1.06
            # Tall prong
            pv, pf = _make_box(px, hr * 0.55, pz, hr * 0.04, hr * 0.15, hr * 0.04)
            parts.append((pv, pf))
            # Gem socket (sphere on top)
            gv, gf = _make_sphere(px, hr * 0.72, pz, hr * 0.025, rings=4, sectors=5)
            parts.append((gv, gf))
        # Inner gem at front
        fgv, fgf = _make_sphere(0, hr * 0.50, hr * 1.06, hr * 0.035, rings=4, sectors=6)
        parts.append((fgv, fgf))
        # Secondary band (upper)
        ubv, ubf = _make_torus_ring(0, hr * 0.60, 0, hr * 1.02, hr * 0.02,
                                    major_segments=segs, minor_segments=3)
        parts.append((ubv, ubf))

    elif style == "skull_mask":
        # Bone-textured face plate covering front of head
        # Main face plate (half-sphere front)
        fpv, fpf = _make_half_sphere(0, hr * 0.35, hr * 0.15, hr * 1.05,
                                     rings=6, sectors=segs, top=True)
        parts.append((fpv, fpf))
        # Eye sockets (indented spheres)
        for side in (-1.0, 1.0):
            ev, ef = _make_sphere(
                side * hr * 0.30, hr * 0.45, hr * 0.85,
                hr * 0.12, rings=4, sectors=6,
            )
            parts.append((ev, ef))
        # Nose hole (small triangle box)
        nv, nf = _make_box(0, hr * 0.28, hr * 0.95, hr * 0.05, hr * 0.08, hr * 0.03)
        parts.append((nv, nf))
        # Jaw piece
        jv, jf = _make_box(0, hr * 0.05, hr * 0.70, hr * 0.35, hr * 0.06, hr * 0.12)
        parts.append((jv, jf))
        # Teeth row
        for ti in range(7):
            tx = -hr * 0.28 + ti * hr * 0.095
            tv, tf = _make_box(tx, hr * 0.12, hr * 0.82, hr * 0.02, hr * 0.04, hr * 0.02)
            parts.append((tv, tf))
        # Forehead ridges
        for ri in range(3):
            ry = hr * 0.60 + ri * hr * 0.12
            rv, rf = _make_box(0, ry, hr * 0.80, hr * 0.30, hr * 0.015, hr * 0.04)
            parts.append((rv, rf))
        # Strap at back
        sv, sf = _make_torus_ring(0, hr * 0.35, 0, hr * 1.02, hr * 0.02,
                                  major_segments=segs, minor_segments=3)
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Helmet_{style}", verts, faces,
                        style=style, slot="helmet", category="armor")


# =========================================================================
# CHEST ARMOR GENERATORS  (5 styles)
# =========================================================================

_CHEST_STYLES = ["plate", "chain", "leather", "robes", "light"]


def generate_chest_armor_mesh(style: str = "plate") -> MeshSpec:
    """Generate chest armor mesh.

    Styles: plate, chain, leather, robes, light.
    Built around a torso capsule (scaled cylinder, ~0.20 m width).
    """
    if style not in _CHEST_STYLES:
        style = "plate"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    cw = 0.20   # half-width of torso
    ch = 0.35   # chest height
    cd = 0.12   # chest depth
    segs = 12

    if style == "plate":
        # Overlapping plates front, back plate, gorget ring
        # Main torso shell
        profile = [
            (cw * 0.88, 0),
            (cw * 1.00, ch * 0.15),
            (cw * 1.08, ch * 0.40),
            (cw * 1.05, ch * 0.65),
            (cw * 0.95, ch * 0.85),
            (cw * 0.70, ch),
        ]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((pv, pf))
        # Back plate (extra plating behind)
        bv, bf = _make_box(0, ch * 0.50, -cw * 1.02, cw * 0.75, ch * 0.35, cw * 0.04)
        parts.append((bv, bf))
        # Gorget ring at neck
        gv, gf = _make_torus_ring(0, ch, 0, cw * 0.58, cw * 0.06,
                                  major_segments=segs, minor_segments=5)
        parts.append((gv, gf))
        # Waist rim
        wv, wf = _make_torus_ring(0, 0, 0, cw * 0.92, cw * 0.04,
                                  major_segments=segs, minor_segments=4)
        parts.append((wv, wf))
        # Overlapping plate ridges (3 horizontal bands)
        for ri in range(3):
            ry = ch * 0.20 + ri * ch * 0.22
            rr = cw * (1.06 - ri * 0.03)
            rv, rf = _make_torus_ring(0, ry, 0, rr, cw * 0.02,
                                      major_segments=segs, minor_segments=3)
            parts.append((rv, rf))
        # Center ridge (sternum)
        srv, srf = _make_box(0, ch * 0.50, cw * 1.05, cw * 0.02, ch * 0.30, cw * 0.015)
        parts.append((srv, srf))

    elif style == "chain":
        # Ring pattern base + leather trim at edges
        # Main chain body (slightly bumpy cylinder)
        sv, sf = _make_tapered_cylinder(
            0, 0, 0, cw * 0.95, cw * 0.72, ch,
            segments=segs, rings=6,
        )
        parts.append((sv, sf))
        # Collar
        cv, cf = _make_torus_ring(0, ch, 0, cw * 0.58, cw * 0.05,
                                  major_segments=segs, minor_segments=4)
        parts.append((cv, cf))
        # Leather trim at waist
        ltv, ltf = _make_torus_ring(0, ch * 0.02, 0, cw * 0.98, cw * 0.04,
                                    major_segments=segs, minor_segments=4)
        parts.append((ltv, ltf))
        # Leather shoulder straps
        for side in (-1.0, 1.0):
            sv2, sf2 = _make_box(side * cw * 0.45, ch * 0.90, 0,
                                 cw * 0.10, ch * 0.06, cw * 0.50)
            parts.append((sv2, sf2))
        # Chain skirt extension
        skv, skf = _make_tapered_cylinder(
            0, -ch * 0.25, 0, cw * 1.05, cw * 0.98, ch * 0.25,
            segments=segs, rings=2, cap_bottom=True, cap_top=False,
        )
        parts.append((skv, skf))
        # Ring detail bumps
        for ri in range(4):
            for si in range(6):
                ry = ch * 0.10 + ri * ch * 0.20
                sa = si * math.pi * 2 / 6 + ri * 0.3
                rx = math.cos(sa) * cw * 0.96
                rz = math.sin(sa) * cw * 0.96
                rv, rf = _make_sphere(rx, ry, rz, cw * 0.015, rings=2, sectors=4)
                parts.append((rv, rf))

    elif style == "leather":
        # Panels with stitching seams, buckles
        # Main body
        sv, sf = _make_tapered_cylinder(
            0, 0, 0, cw * 0.92, cw * 0.68, ch,
            segments=segs, rings=4,
        )
        parts.append((sv, sf))
        # Panel seam ridges (vertical)
        for si in range(4):
            sa = si * math.pi * 2 / 4
            sx = math.cos(sa) * cw * 0.94
            sz = math.sin(sa) * cw * 0.94
            sv2, sf2 = _make_box(sx, ch * 0.50, sz, cw * 0.012, ch * 0.40, cw * 0.012)
            parts.append((sv2, sf2))
        # Buckles on front
        for bi in range(3):
            by = ch * 0.18 + bi * ch * 0.28
            bv, bf = _make_box(cw * 0.50, by, cw * 0.75,
                               cw * 0.06, cw * 0.04, cw * 0.03)
            parts.append((bv, bf))
            # Buckle prong
            bpv, bpf = _make_box(cw * 0.50, by, cw * 0.80,
                                 cw * 0.015, cw * 0.03, cw * 0.01)
            parts.append((bpv, bpf))
        # Collar
        cv, cf = _make_torus_ring(0, ch * 0.98, 0, cw * 0.60, cw * 0.03,
                                  major_segments=segs, minor_segments=3)
        parts.append((cv, cf))
        # Shoulder pads (small)
        for side in (-1.0, 1.0):
            spv, spf = _make_box(side * cw * 0.80, ch * 0.88, 0,
                                 cw * 0.15, cw * 0.05, cw * 0.25)
            parts.append((spv, spf))

    elif style == "robes":
        # Flowing cloth mesh, belt/sash
        # Main robe body (wide tapered cylinder from waist to ankles)
        rv, rf = _make_tapered_cylinder(
            0, -ch * 0.8, 0, cw * 1.20, cw * 0.72, ch * 1.8,
            segments=segs, rings=6,
            cap_bottom=True, cap_top=True,
        )
        parts.append((rv, rf))
        # Upper chest / neckline
        uv, uf = _make_tapered_cylinder(
            0, ch, 0, cw * 0.72, cw * 0.50, ch * 0.25,
            segments=segs, rings=2,
            cap_bottom=False, cap_top=True,
        )
        parts.append((uv, uf))
        # Belt / sash
        bv, bf = _make_torus_ring(0, ch * 0.05, 0, cw * 0.96, cw * 0.05,
                                  major_segments=segs, minor_segments=5)
        parts.append((bv, bf))
        # Sash tail hanging down
        stv, stf = _make_box(cw * 0.50, -ch * 0.30, cw * 0.80,
                             cw * 0.12, ch * 0.40, cw * 0.02)
        parts.append((stv, stf))
        # Fold/wrinkle rings
        for wi in range(4):
            wy = -ch * 0.3 + wi * ch * 0.35
            wr = cw * (1.15 - wi * 0.08)
            wv, wf = _make_torus_ring(0, wy, 0, wr, cw * 0.012,
                                      major_segments=segs, minor_segments=3)
            parts.append((wv, wf))
        # Sleeve hints
        for side in (-1.0, 1.0):
            slv, slf = _make_tapered_cylinder(
                side * cw * 0.75, ch * 0.60, 0,
                cw * 0.18, cw * 0.25, ch * 0.35,
                segments=6, rings=2,
                cap_bottom=True, cap_top=True,
            )
            parts.append((slv, slf))

    elif style == "light":
        # Minimal chest wrap / bandage style
        # Thin wrap around torso
        wv, wf = _make_tapered_cylinder(
            0, 0, 0, cw * 0.88, cw * 0.70, ch * 0.85,
            segments=segs, rings=3,
            cap_bottom=True, cap_top=True,
        )
        parts.append((wv, wf))
        # Wrap bands (horizontal straps)
        for wi in range(5):
            wy = ch * 0.08 + wi * ch * 0.16
            wr = cw * (0.90 - wi * 0.02)
            wbv, wbf = _make_torus_ring(0, wy, 0, wr, cw * 0.025,
                                        major_segments=segs, minor_segments=3)
            parts.append((wbv, wbf))
        # Single shoulder strap
        ssv, ssf = _make_box(cw * 0.35, ch * 0.85, 0,
                             cw * 0.08, ch * 0.10, cw * 0.40)
        parts.append((ssv, ssf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"ChestArmor_{style}", verts, faces,
                        style=style, slot="chest", category="armor")


# =========================================================================
# GAUNTLET GENERATORS  (3 styles)
# =========================================================================

_GAUNTLET_STYLES = ["plate", "leather", "wraps"]


def generate_gauntlet_mesh(style: str = "plate") -> MeshSpec:
    """Generate gauntlet / hand armor mesh.

    Styles: plate, leather, wraps.
    Built around a hand/forearm cylinder (~0.045 m half-width).
    """
    if style not in _GAUNTLET_STYLES:
        style = "plate"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hw = 0.045  # hand half-width
    hh = 0.12   # hand height (wrist to fingertip)
    fl = 0.065  # finger length
    segs = 8

    if style == "plate":
        # Articulated fingers, wrist guard, knuckle plates
        # Main hand box
        hv, hf = _make_box(0, hh / 2, 0, hw, hh / 2, hw * 0.40)
        parts.append((hv, hf))
        # Wrist guard (flared cylinder)
        wv, wf = _make_tapered_cylinder(
            0, -hh * 0.05, 0, hw * 1.20, hw * 0.95, hh * 0.35,
            segments=segs, rings=2,
        )
        parts.append((wv, wf))
        # Knuckle plate (ridge across knuckles)
        kv, kf = _make_box(0, hh * 0.95, 0, hw * 0.85, hw * 0.06, hw * 0.35)
        parts.append((kv, kf))
        # Articulated finger segments (4 fingers, 3 segments each)
        for fi in range(4):
            fx = -hw * 0.60 + fi * hw * 0.40
            for si in range(3):
                sy = hh + si * fl / 3
                sh = fl / 3 * 0.85
                fv, ff = _make_box(fx, sy + sh / 2, 0, hw * 0.10, sh / 2, hw * 0.22)
                parts.append((fv, ff))
        # Thumb
        tv, tf = _make_tapered_cylinder(
            -hw * 0.80, hh * 0.45, hw * 0.20,
            hw * 0.10, hw * 0.07, fl * 0.70,
            segments=5, rings=2,
        )
        parts.append((tv, tf))
        # Knuckle spikes
        for ki in range(4):
            kx = -hw * 0.60 + ki * hw * 0.40
            kv2, kf2 = _make_cone(kx, hh * 1.01, 0, hw * 0.04, hw * 0.12, segments=4)
            parts.append((kv2, kf2))

    elif style == "leather":
        # Stitched seams, reinforced palms
        # Main glove body
        gv, gf = _make_tapered_cylinder(
            0, 0, 0, hw * 0.95, hw * 0.80, hh,
            segments=segs, rings=4,
        )
        parts.append((gv, gf))
        # Fingers
        for fi in range(4):
            fx = -hw * 0.50 + fi * hw * 0.35
            fv, ff = _make_tapered_cylinder(
                fx, hh, 0, hw * 0.10, hw * 0.07, fl,
                segments=5, rings=2,
            )
            parts.append((fv, ff))
        # Thumb
        tv, tf = _make_tapered_cylinder(
            -hw * 0.70, hh * 0.40, hw * 0.15,
            hw * 0.09, hw * 0.06, fl * 0.60,
            segments=5, rings=1,
        )
        parts.append((tv, tf))
        # Stitching seam lines (torus bands)
        for si in range(3):
            sy = hh * 0.15 + si * hh * 0.30
            sv, sf = _make_torus_ring(0, sy, 0, hw * 0.97, hw * 0.008,
                                      major_segments=segs, minor_segments=3)
            parts.append((sv, sf))
        # Reinforced palm pad
        pv, pf = _make_box(0, hh * 0.40, -hw * 0.35, hw * 0.55, hh * 0.20, hw * 0.04)
        parts.append((pv, pf))
        # Wrist cuff
        wv, wf = _make_torus_ring(0, hh * 0.02, 0, hw * 0.98, hw * 0.03,
                                  major_segments=segs, minor_segments=3)
        parts.append((wv, wf))

    elif style == "wraps":
        # Wrapped cloth/leather with forearm guard
        # Forearm guard (long tapered cylinder)
        fgv, fgf = _make_tapered_cylinder(
            0, -hh * 0.50, 0, hw * 1.10, hw * 0.85, hh * 1.20,
            segments=segs, rings=4,
        )
        parts.append((fgv, fgf))
        # Wrap bands (diagonal feel via offset torus rings)
        for wi in range(6):
            wy = -hh * 0.35 + wi * hh * 0.28
            wr = hw * (1.08 - wi * 0.03)
            wv, wf = _make_torus_ring(0, wy, 0, wr, hw * 0.018,
                                      major_segments=segs, minor_segments=3)
            parts.append((wv, wf))
        # Open fingers (no finger armor)
        # Hand shape
        hdv, hdf = _make_box(0, hh * 0.60, 0, hw * 0.70, hh * 0.15, hw * 0.30)
        parts.append((hdv, hdf))
        # Knuckle wrap
        kwv, kwf = _make_torus_ring(0, hh * 0.78, 0, hw * 0.72, hw * 0.015,
                                    major_segments=segs, minor_segments=3)
        parts.append((kwv, kwf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gauntlet_{style}", verts, faces,
                        style=style, slot="gauntlet", category="armor")


# =========================================================================
# BOOT GENERATORS  (3 styles)
# =========================================================================

_BOOT_STYLES = ["plate", "leather", "sandals"]


def generate_boot_mesh(style: str = "plate") -> MeshSpec:
    """Generate boot / foot armor mesh.

    Styles: plate, leather, sandals.
    Built around a lower-leg cylinder (~0.05 m radius).
    """
    if style not in _BOOT_STYLES:
        style = "plate"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    lr = 0.05    # leg radius
    sh = 0.38    # shin height
    fl = 0.15    # foot length
    segs = 10

    if style == "plate":
        # Shin guard, knee cop, sabatons
        # Shin guard (main cylinder)
        sgv, sgf = _make_tapered_cylinder(
            0, 0, 0, lr * 1.15, lr * 1.05, sh,
            segments=segs, rings=3,
        )
        parts.append((sgv, sgf))
        # Knee cop (bulge at top)
        kcv, kcf = _make_sphere(0, sh, lr * 0.50, lr * 0.55,
                                rings=5, sectors=segs)
        parts.append((kcv, kcf))
        # Sabaton (foot plate)
        sbv, sbf = _make_box(0, -lr * 0.30, fl * 0.30,
                             lr * 0.80, lr * 0.25, fl * 0.55)
        parts.append((sbv, sbf))
        # Sole plate
        slv, slf = _make_box(0, -lr * 0.55, fl * 0.30,
                             lr * 0.85, lr * 0.05, fl * 0.60)
        parts.append((slv, slf))
        # Articulated toe plates
        for ti in range(3):
            tz = fl * 0.65 + ti * fl * 0.12
            tv, tf = _make_box(0, -lr * 0.20, tz,
                               lr * 0.65, lr * 0.10, fl * 0.05)
            parts.append((tv, tf))
        # Shin ridge bands
        for ri in range(3):
            ry = sh * 0.15 + ri * sh * 0.25
            rv, rf = _make_torus_ring(0, ry, 0, lr * 1.18, lr * 0.025,
                                      major_segments=segs, minor_segments=3)
            parts.append((rv, rf))

    elif style == "leather":
        # Tall shaft, buckle straps, sole detail
        # Boot shaft
        bsv, bsf = _make_tapered_cylinder(
            0, 0, 0, lr * 1.05, lr * 0.90, sh * 0.85,
            segments=segs, rings=4,
        )
        parts.append((bsv, bsf))
        # Foot box
        fv, ff = _make_box(0, -lr * 0.25, fl * 0.25,
                           lr * 0.75, lr * 0.22, fl * 0.45)
        parts.append((fv, ff))
        # Sole
        slv, slf = _make_box(0, -lr * 0.48, fl * 0.28,
                             lr * 0.80, lr * 0.04, fl * 0.50)
        parts.append((slv, slf))
        # Heel
        hlv, hlf = _make_box(0, -lr * 0.40, -fl * 0.05,
                             lr * 0.40, lr * 0.08, fl * 0.08)
        parts.append((hlv, hlf))
        # Buckle straps (3 straps)
        for si in range(3):
            sy = sh * 0.12 + si * sh * 0.25
            sv, sf = _make_torus_ring(0, sy, 0, lr * 1.08, lr * 0.025,
                                      major_segments=segs, minor_segments=3)
            parts.append((sv, sf))
            # Buckle
            bkv, bkf = _make_box(lr * 0.90, sy, lr * 0.45,
                                 lr * 0.06, lr * 0.04, lr * 0.04)
            parts.append((bkv, bkf))
        # Top rim fold
        trv, trf = _make_torus_ring(0, sh * 0.82, 0, lr * 0.95, lr * 0.04,
                                    major_segments=segs, minor_segments=4)
        parts.append((trv, trf))

    elif style == "sandals":
        # Minimal coverage: sole + straps
        # Sole plate
        slv, slf = _make_box(0, -lr * 0.45, fl * 0.20,
                             lr * 0.75, lr * 0.04, fl * 0.50)
        parts.append((slv, slf))
        # Toe strap
        tsv, tsf = _make_torus_ring(0, -lr * 0.20, fl * 0.55,
                                    lr * 0.60, lr * 0.02,
                                    major_segments=8, minor_segments=3)
        parts.append((tsv, tsf))
        # Ankle straps (cross pattern)
        for si in range(3):
            sy = -lr * 0.10 + si * lr * 0.60
            sv, sf = _make_torus_ring(0, sy, lr * 0.05,
                                      lr * 0.55, lr * 0.015,
                                      major_segments=8, minor_segments=3)
            parts.append((sv, sf))
        # Heel cup
        hcv, hcf = _make_box(0, -lr * 0.15, -fl * 0.15,
                             lr * 0.50, lr * 0.30, lr * 0.04)
        parts.append((hcv, hcf))
        # Ankle guard (minimal)
        agv, agf = _make_box(0, lr * 0.60, 0,
                             lr * 0.55, lr * 0.15, lr * 0.04)
        parts.append((agv, agf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Boot_{style}", verts, faces,
                        style=style, slot="boot", category="armor")


# =========================================================================
# PAULDRON / SHOULDER GENERATORS  (3 styles)
# =========================================================================

_PAULDRON_STYLES = ["plate", "fur", "bone"]


def generate_pauldron_mesh(style: str = "plate", side: str = "left") -> MeshSpec:
    """Generate shoulder pauldron mesh.

    Styles: plate, fur, bone.
    ``side`` can be 'left' or 'right' (mirrors X position).
    """
    if style not in _PAULDRON_STYLES:
        style = "plate"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    pr = 0.15   # pauldron radius
    sm = -1.0 if side == "left" else 1.0
    segs = 10

    if style == "plate":
        # Layered plates with spike/horn mounts
        # Main dome
        profile = [
            (pr, 0),
            (pr * 1.12, pr * 0.20),
            (pr * 1.15, pr * 0.45),
            (pr * 1.00, pr * 0.65),
            (pr * 0.55, pr * 0.80),
        ]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append(([(v[0] + sm * 0.18, v[1], v[2]) for v in pv], pf))
        # Layer plate ridges (3 overlapping)
        for li in range(3):
            ly = pr * 0.10 + li * pr * 0.22
            lr_val = pr * (1.10 - li * 0.08)
            rv, rf = _make_torus_ring(sm * 0.18, ly, 0, lr_val, pr * 0.02,
                                      major_segments=segs, minor_segments=3)
            parts.append((rv, rf))
        # Spike/horn mount
        sv, sf = _make_cone(sm * 0.18, pr * 0.65, 0,
                            pr * 0.08, pr * 0.45, segments=6)
        parts.append((sv, sf))
        # Attachment ring at base
        av, af = _make_torus_ring(sm * 0.18, 0, 0, pr * 0.85, pr * 0.03,
                                  major_segments=segs, minor_segments=3)
        parts.append((av, af))

    elif style == "fur":
        # Draped fur mesh over shoulder
        # Base leather pad
        bv, bf = _make_box(sm * 0.15, pr * 0.15, 0,
                           pr * 0.65, pr * 0.08, pr * 0.50)
        parts.append((bv, bf))
        # Fur drape (overlapping tapered shapes)
        for fi in range(5):
            fa = (fi - 2) * math.pi / 6
            fx = sm * 0.15 + math.cos(fa) * pr * 0.30
            fz = math.sin(fa) * pr * 0.40
            fy_base = pr * 0.20
            # Fur tuft (tapered cylinder drooping down)
            fv, ff = _make_tapered_cylinder(
                fx, fy_base - pr * 0.30, fz,
                pr * 0.12, pr * 0.18, pr * 0.50,
                segments=5, rings=2,
                cap_bottom=True, cap_top=True,
            )
            parts.append((fv, ff))
        # Fur bump texture (small spheres)
        for bi in range(8):
            ba = bi * math.pi * 2 / 8
            bx = sm * 0.15 + math.cos(ba) * pr * 0.45
            bz = math.sin(ba) * pr * 0.35
            by = pr * 0.12
            bsv, bsf = _make_sphere(bx, by, bz, pr * 0.04, rings=3, sectors=4)
            parts.append((bsv, bsf))
        # Leather strap crossing chest
        lsv, lsf = _make_box(sm * 0.08, pr * 0.10, pr * 0.30,
                             pr * 0.35, pr * 0.02, pr * 0.04)
        parts.append((lsv, lsf))

    elif style == "bone":
        # Monster bone/trophy on leather base
        # Leather shoulder pad
        lv, lf = _make_box(sm * 0.15, pr * 0.10, 0,
                           pr * 0.55, pr * 0.06, pr * 0.40)
        parts.append((lv, lf))
        # Main bone piece (curved tapered cylinder)
        bone_segs = 8
        bone_len = pr * 1.20
        for bi in range(bone_segs):
            t = bi / (bone_segs - 1)
            bx = sm * 0.15 + math.sin(t * math.pi * 0.4) * pr * 0.20
            by = pr * 0.15 + t * bone_len * 0.8
            bz = math.cos(t * math.pi * 0.3) * pr * 0.05
            r = pr * 0.06 * (1.0 + 0.3 * math.sin(t * math.pi))
            sv, sf = _make_sphere(bx, by, bz, r, rings=3, sectors=5)
            parts.append((sv, sf))
        # Bone knob ends
        for end_t in (0.0, 1.0):
            ex = sm * 0.15 + math.sin(end_t * math.pi * 0.4) * pr * 0.20
            ey = pr * 0.15 + end_t * bone_len * 0.8
            ez = math.cos(end_t * math.pi * 0.3) * pr * 0.05
            ev, ef = _make_sphere(ex, ey, ez, pr * 0.10, rings=4, sectors=6)
            parts.append((ev, ef))
        # Leather straps binding bone
        for si in range(2):
            sy = pr * 0.30 + si * pr * 0.35
            sv, sf = _make_torus_ring(sm * 0.15, sy, 0, pr * 0.15, pr * 0.02,
                                      major_segments=6, minor_segments=3)
            parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Pauldron_{style}_{side}", verts, faces,
                        style=style, side=side, slot="pauldron", category="armor")


# =========================================================================
# CAPE GENERATORS  (3 styles)
# =========================================================================

_CAPE_STYLES = ["full", "half", "tattered"]


def generate_cape_mesh(style: str = "full") -> MeshSpec:
    """Generate cape / cloak mesh.

    Styles: full, half, tattered.
    Constructed as curved sheet mesh from shoulder to heel.
    """
    if style not in _CAPE_STYLES:
        style = "full"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    cape_width = 0.55
    cape_height = 0.90
    cape_curve = 0.12   # forward curve depth

    if style == "full":
        # Shoulder-to-heel drape with clasp geometry
        subdiv_x = 10
        subdiv_y = 14
        verts: list[tuple[float, float, float]] = []
        faces_list: list[tuple[int, ...]] = []
        for iy in range(subdiv_y + 1):
            ty = iy / subdiv_y
            y = cape_height * (1.0 - ty)   # top to bottom
            # Width expands toward bottom
            w = cape_width * (0.70 + 0.30 * ty)
            # Curve: deeper at middle height
            curve_z = -cape_curve * math.sin(ty * math.pi) * 0.8
            for ix in range(subdiv_x + 1):
                tx = ix / subdiv_x
                x = -w / 2 + tx * w
                # Slight lateral curve
                z_lateral = -cape_curve * 0.3 * math.sin(tx * math.pi)
                verts.append((x, y, curve_z + z_lateral))
        cols = subdiv_x + 1
        for iy in range(subdiv_y):
            for ix in range(subdiv_x):
                v0 = iy * cols + ix
                v1 = v0 + 1
                v2 = v0 + cols + 1
                v3 = v0 + cols
                faces_list.append((v0, v1, v2, v3))
        parts.append((verts, faces_list))
        # Clasp at collar (two spheres + connecting bar)
        for side in (-1.0, 1.0):
            csv, csf = _make_sphere(side * cape_width * 0.25, cape_height, 0,
                                    0.015, rings=4, sectors=5)
            parts.append((csv, csf))
        # Clasp bar
        cbv, cbf = _make_cylinder(0, cape_height - 0.005, 0,
                                  0.008, 0.01, segments=6,
                                  cap_top=True, cap_bottom=True)
        # Rotate bar to be horizontal -- approximate with a box
        cbv2, cbf2 = _make_box(0, cape_height, 0,
                               cape_width * 0.25, 0.006, 0.006)
        parts.append((cbv2, cbf2))
        # Collar fold
        cfv, cff = _make_box(0, cape_height * 0.95, -cape_curve * 0.3,
                             cape_width * 0.35, cape_height * 0.04, 0.02)
        parts.append((cfv, cff))

    elif style == "half":
        # One-shoulder cape, asymmetric
        subdiv_x = 8
        subdiv_y = 12
        verts = []
        faces_list = []
        for iy in range(subdiv_y + 1):
            ty = iy / subdiv_y
            y = cape_height * 0.85 * (1.0 - ty)
            # Only covers right side, narrowing at bottom
            w = cape_width * 0.55 * (1.0 - ty * 0.40)
            curve_z = -cape_curve * math.sin(ty * math.pi) * 0.6
            for ix in range(subdiv_x + 1):
                tx = ix / subdiv_x
                x = tx * w  # One-sided: 0 to w
                z_lateral = -cape_curve * 0.2 * math.sin(tx * math.pi)
                verts.append((x, y, curve_z + z_lateral))
        cols = subdiv_x + 1
        for iy in range(subdiv_y):
            for ix in range(subdiv_x):
                v0 = iy * cols + ix
                v1 = v0 + 1
                v2 = v0 + cols + 1
                v3 = v0 + cols
                faces_list.append((v0, v1, v2, v3))
        parts.append((verts, faces_list))
        # Shoulder clasp
        scv, scf = _make_sphere(cape_width * 0.10, cape_height * 0.82, 0,
                                0.018, rings=4, sectors=5)
        parts.append((scv, scf))
        # Shoulder drape thickening
        sdv, sdf = _make_box(cape_width * 0.15, cape_height * 0.78, -0.02,
                             cape_width * 0.15, 0.02, 0.025)
        parts.append((sdv, sdf))

    elif style == "tattered":
        # Pre-damaged edges with irregular bottom
        subdiv_x = 10
        subdiv_y = 14
        verts = []
        faces_list = []
        for iy in range(subdiv_y + 1):
            ty = iy / subdiv_y
            # Irregular bottom edge
            base_y = cape_height * 0.80 * (1.0 - ty)
            w = cape_width * (0.65 + 0.20 * ty)
            curve_z = -cape_curve * math.sin(ty * math.pi) * 0.7
            for ix in range(subdiv_x + 1):
                tx = ix / subdiv_x
                x = -w / 2 + tx * w
                z_lateral = -cape_curve * 0.25 * math.sin(tx * math.pi)
                # Tatter: irregular Y offset at bottom rows
                y_jitter = 0.0
                if ty > 0.75:
                    # Pseudo-random jitter based on position
                    seed_val = math.sin(ix * 7.3 + iy * 13.7) * 0.5 + 0.5
                    y_jitter = -seed_val * cape_height * 0.12
                verts.append((x, base_y + y_jitter, curve_z + z_lateral))
        cols = subdiv_x + 1
        for iy in range(subdiv_y):
            for ix in range(subdiv_x):
                v0 = iy * cols + ix
                v1 = v0 + 1
                v2 = v0 + cols + 1
                v3 = v0 + cols
                faces_list.append((v0, v1, v2, v3))
        parts.append((verts, faces_list))
        # Torn holes (remove some faces would require post-processing;
        # instead add hole-rim geometry)
        for hi in range(3):
            hx = -cape_width * 0.20 + hi * cape_width * 0.20
            hy = cape_height * (0.30 + hi * 0.15)
            hr_hole = 0.025 + hi * 0.008
            hv, hf = _make_torus_ring(hx, hy, -cape_curve * 0.3,
                                      hr_hole, hr_hole * 0.3,
                                      major_segments=8, minor_segments=3)
            parts.append((hv, hf))
        # Frayed threads at edges (tiny cylinders hanging down)
        for fi in range(6):
            fx = -cape_width * 0.30 + fi * cape_width * 0.12
            fy = cape_height * 0.10
            fv, ff = _make_cylinder(fx, fy - 0.04, -cape_curve * 0.2,
                                    0.003, 0.04, segments=4,
                                    cap_top=True, cap_bottom=True)
            parts.append((fv, ff))
        # Clasp (simple)
        csv, csf = _make_sphere(0, cape_height * 0.78, 0,
                                0.012, rings=3, sectors=4)
        parts.append((csv, csf))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"Cape_{style}", verts_final, faces_final,
                        style=style, slot="cape", category="armor")


# =========================================================================
# BELT GENERATORS  (5 styles)
# =========================================================================

_BELT_STYLES = ["leather", "chain", "rope", "ornate", "utility"]


def generate_belt_mesh(style: str = "leather") -> MeshSpec:
    """Generate a belt mesh in the requested style.

    Styles: leather, chain, rope, ornate, utility.
    Built around a waist cylinder (radius ~0.15 m).
    """
    if style not in _BELT_STYLES:
        style = "leather"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    waist_r = 0.15
    belt_h = 0.04
    segs = 16

    if style == "leather":
        # Simple leather band with buckle
        bv, bf = _make_torus_ring(0, 0, 0, waist_r, belt_h * 0.5,
                                  major_segments=segs, minor_segments=4)
        parts.append((bv, bf))
        # Buckle -- rectangular plate at front
        bkv, bkf = _make_box(0, 0, waist_r + belt_h * 0.3,
                             belt_h * 0.6, belt_h * 0.5, belt_h * 0.15)
        parts.append((bkv, bkf))
        # Buckle prong
        pv, pf = _make_cylinder(0, -belt_h * 0.3, waist_r + belt_h * 0.25,
                                belt_h * 0.05, belt_h * 0.6, segments=4)
        parts.append((pv, pf))
        # Belt tongue/strap hanging down
        sv, sf = _make_box(belt_h * 0.8, -belt_h * 0.5, waist_r + belt_h * 0.1,
                           belt_h * 0.15, belt_h * 1.0, belt_h * 0.05)
        parts.append((sv, sf))

    elif style == "chain":
        # Chain links forming a belt
        link_count = segs
        for i in range(link_count):
            angle = 2.0 * math.pi * i / link_count
            lx = math.cos(angle) * waist_r
            lz = math.sin(angle) * waist_r
            lr = belt_h * 0.25
            lv, lf = _make_torus_ring(lx, 0, lz, lr, lr * 0.3,
                                      major_segments=6, minor_segments=3)
            parts.append((lv, lf))
        # Chain clasp at front
        cv, cf = _make_sphere(0, 0, waist_r + belt_h * 0.3,
                              belt_h * 0.4, rings=4, sectors=6)
        parts.append((cv, cf))

    elif style == "rope":
        # Twisted rope belt -- two intertwined helices
        rope_r = belt_h * 0.2
        rope_segs = 48
        for strand in range(2):
            strand_offset = strand * math.pi
            verts_strand: list[tuple[float, float, float]] = []
            faces_strand: list[tuple[int, ...]] = []
            tube_segs = 4
            for i in range(rope_segs):
                angle_main = 2.0 * math.pi * i / rope_segs
                twist = angle_main * 4 + strand_offset
                cx = math.cos(angle_main) * waist_r
                cz = math.sin(angle_main) * waist_r
                cy = math.sin(twist) * rope_r * 0.6
                for j in range(tube_segs):
                    t_angle = 2.0 * math.pi * j / tube_segs
                    # Offset perpendicular to the ring tangent
                    nx = -math.sin(angle_main)
                    nz = math.cos(angle_main)
                    px = cx + (nx * math.cos(t_angle) * rope_r)
                    py = cy + math.sin(t_angle) * rope_r
                    pz = cz + (nz * math.cos(t_angle) * rope_r)
                    verts_strand.append((px, py, pz))
            for i in range(rope_segs):
                i2 = (i + 1) % rope_segs
                for j in range(tube_segs):
                    j2 = (j + 1) % tube_segs
                    v0 = i * tube_segs + j
                    v1 = i * tube_segs + j2
                    v2 = i2 * tube_segs + j2
                    v3 = i2 * tube_segs + j
                    faces_strand.append((v0, v1, v2, v3))
            parts.append((verts_strand, faces_strand))
        # Knot at front
        kv, kf = _make_sphere(0, 0, waist_r + belt_h * 0.15,
                              belt_h * 0.5, rings=4, sectors=6)
        parts.append((kv, kf))

    elif style == "ornate":
        # Decorated metal belt with gem plates
        bv, bf = _make_torus_ring(0, 0, 0, waist_r, belt_h * 0.6,
                                  major_segments=segs, minor_segments=5)
        parts.append((bv, bf))
        # Decorative plates evenly spaced
        plate_count = 6
        for i in range(plate_count):
            angle = 2.0 * math.pi * i / plate_count
            px = math.cos(angle) * (waist_r + belt_h * 0.3)
            pz = math.sin(angle) * (waist_r + belt_h * 0.3)
            pv, pf = _make_box(px, 0, pz, belt_h * 0.35, belt_h * 0.45, belt_h * 0.08)
            parts.append((pv, pf))
            # Gem on each plate
            gv, gf = _make_sphere(px, 0, pz + belt_h * 0.1,
                                  belt_h * 0.12, rings=3, sectors=5)
            parts.append((gv, gf))
        # Central buckle medallion
        mv, mf = _make_cylinder(0, -belt_h * 0.5, waist_r + belt_h * 0.4,
                                belt_h * 0.5, belt_h * 1.0, segments=8)
        parts.append((mv, mf))
        # Filigree ring around buckle
        fv, ff = _make_torus_ring(0, 0, waist_r + belt_h * 0.4,
                                  belt_h * 0.55, belt_h * 0.06,
                                  major_segments=8, minor_segments=3)
        parts.append((fv, ff))

    elif style == "utility":
        # Leather belt with pouches and tool loops
        bv, bf = _make_torus_ring(0, 0, 0, waist_r, belt_h * 0.45,
                                  major_segments=segs, minor_segments=4)
        parts.append((bv, bf))
        # Buckle
        bkv, bkf = _make_box(0, 0, waist_r + belt_h * 0.2,
                             belt_h * 0.5, belt_h * 0.4, belt_h * 0.1)
        parts.append((bkv, bkf))
        # Pouches (3 around the belt)
        pouch_angles = [math.pi * 0.3, math.pi * 0.7, math.pi * 1.3]
        for pa in pouch_angles:
            px = math.cos(pa) * (waist_r + belt_h * 0.8)
            pz = math.sin(pa) * (waist_r + belt_h * 0.8)
            # Pouch body
            pbv, pbf = _make_box(px, -belt_h * 0.3, pz,
                                 belt_h * 0.4, belt_h * 0.55, belt_h * 0.35)
            parts.append((pbv, pbf))
            # Pouch flap
            pfv, pff = _make_box(px, belt_h * 0.25, pz,
                                 belt_h * 0.42, belt_h * 0.06, belt_h * 0.38)
            parts.append((pfv, pff))
            # Flap button
            fbv, fbf = _make_sphere(px, belt_h * 0.2, pz + belt_h * 0.35,
                                    belt_h * 0.06, rings=2, sectors=4)
            parts.append((fbv, fbf))
        # Tool loops (2 small rings)
        for tl in [math.pi * 1.0, math.pi * 1.6]:
            tx = math.cos(tl) * (waist_r + belt_h * 0.3)
            tz = math.sin(tl) * (waist_r + belt_h * 0.3)
            tv, tf = _make_torus_ring(tx, -belt_h * 0.1, tz,
                                      belt_h * 0.15, belt_h * 0.04,
                                      major_segments=6, minor_segments=3)
            parts.append((tv, tf))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"Belt_{style}", verts_final, faces_final,
                        style=style, slot="belt", category="armor")


# =========================================================================
# BRACER GENERATORS  (5 styles)
# =========================================================================

_BRACER_STYLES = ["leather", "metal_vambrace", "enchanted", "chain", "bone"]


def generate_bracer_mesh(style: str = "leather") -> MeshSpec:
    """Generate a bracer/wrist guard mesh in the requested style.

    Styles: leather, metal_vambrace, enchanted, chain, bone.
    Built around a forearm cylinder (radius ~0.04 m, length ~0.15 m).
    """
    if style not in _BRACER_STYLES:
        style = "leather"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    arm_r = 0.04
    bracer_len = 0.15
    segs = 12

    if style == "leather":
        # Wrapped leather with stitching detail and reinforced knuckle guard
        bv, bf = _make_tapered_cylinder(0, 0, 0, arm_r * 1.15, arm_r * 1.25,
                                        bracer_len, segments=segs, rings=3)
        parts.append((bv, bf))
        # Stitching lines (thin ridges along length)
        for si in range(3):
            angle = si * math.pi * 2 / 3
            sx = math.cos(angle) * (arm_r * 1.28)
            sz = math.sin(angle) * (arm_r * 1.28)
            sv, sf = _make_cylinder(sx, 0, sz, arm_r * 0.01, bracer_len * 0.9,
                                    segments=3, cap_top=True, cap_bottom=True)
            parts.append((sv, sf))
        # Wrist strap
        wv, wf = _make_torus_ring(0, bracer_len * 0.1, 0, arm_r * 1.30, arm_r * 0.05,
                                  major_segments=segs, minor_segments=3)
        parts.append((wv, wf))

    elif style == "metal_vambrace":
        # Articulated metal plates covering forearm
        plate_count = 4
        plate_h = bracer_len / plate_count
        for pi in range(plate_count):
            py = pi * plate_h
            r = arm_r * (1.20 + pi * 0.03)
            pv, pf = _make_tapered_cylinder(0, py, 0, r, r * 0.98,
                                            plate_h * 0.85, segments=segs, rings=1)
            parts.append((pv, pf))
        # Rivets along edges
        for pi in range(plate_count):
            for ri in range(4):
                ra = ri * math.pi * 2 / 4
                rx = math.cos(ra) * arm_r * 1.32
                rz = math.sin(ra) * arm_r * 1.32
                rv, rf = _make_sphere(rx, pi * plate_h + plate_h * 0.5, rz,
                                      arm_r * 0.03, rings=2, sectors=4)
                parts.append((rv, rf))
        # Elbow guard flare
        ev, ef = _make_cone(0, bracer_len, 0, arm_r * 1.5, bracer_len * 0.15,
                            segments=segs)
        parts.append((ev, ef))

    elif style == "enchanted":
        # Smooth bracer with glowing rune channels
        bv, bf = _make_tapered_cylinder(0, 0, 0, arm_r * 1.18, arm_r * 1.22,
                                        bracer_len, segments=segs, rings=4)
        parts.append((bv, bf))
        # Rune channel grooves (inset torus rings)
        for ri in range(3):
            ry = bracer_len * (0.25 + ri * 0.25)
            rv, rf = _make_torus_ring(0, ry, 0, arm_r * 1.22, arm_r * 0.03,
                                      major_segments=segs, minor_segments=3)
            parts.append((rv, rf))
        # Central gem mount
        gv, gf = _make_sphere(0, bracer_len * 0.5, arm_r * 1.25,
                              arm_r * 0.15, rings=4, sectors=6)
        parts.append((gv, gf))
        # Gem socket ring
        gsv, gsf = _make_torus_ring(0, bracer_len * 0.5, arm_r * 1.25,
                                    arm_r * 0.18, arm_r * 0.025,
                                    major_segments=8, minor_segments=3)
        parts.append((gsv, gsf))

    elif style == "chain":
        # Chainmail sleeve
        link_rows = 6
        link_cols = segs
        link_r = arm_r * 0.08
        for row in range(link_rows):
            ry = row * bracer_len / link_rows
            for col in range(link_cols):
                angle = 2.0 * math.pi * col / link_cols
                # Offset every other row
                if row % 2 == 1:
                    angle += math.pi / link_cols
                lx = math.cos(angle) * arm_r * 1.18
                lz = math.sin(angle) * arm_r * 1.18
                lv, lf = _make_torus_ring(lx, ry, lz, link_r, link_r * 0.3,
                                          major_segments=4, minor_segments=3)
                parts.append((lv, lf))
        # Wrist band
        wv, wf = _make_torus_ring(0, 0, 0, arm_r * 1.22, arm_r * 0.06,
                                  major_segments=segs, minor_segments=4)
        parts.append((wv, wf))

    elif style == "bone":
        # Bone fragments lashed together
        bone_count = 5
        for bi in range(bone_count):
            angle = 2.0 * math.pi * bi / bone_count
            bx = math.cos(angle) * arm_r * 1.1
            bz = math.sin(angle) * arm_r * 1.1
            # Each bone is a tapered cylinder with knobby ends
            bbv, bbf = _make_tapered_cylinder(bx, 0, bz, arm_r * 0.06, arm_r * 0.04,
                                              bracer_len * 0.85, segments=5, rings=2)
            parts.append((bbv, bbf))
            # Knobs at ends
            for ky in [0.0, bracer_len * 0.85]:
                kv, kf = _make_sphere(bx, ky, bz, arm_r * 0.07, rings=3, sectors=4)
                parts.append((kv, kf))
        # Lashing cord wraps
        for li in range(3):
            ly = bracer_len * (0.2 + li * 0.3)
            lv, lf = _make_torus_ring(0, ly, 0, arm_r * 1.20, arm_r * 0.02,
                                      major_segments=segs, minor_segments=3)
            parts.append((lv, lf))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"Bracer_{style}", verts_final, faces_final,
                        style=style, slot="bracer", category="armor")


# =========================================================================
# RING GENERATORS  (5 styles)
# =========================================================================

_RING_STYLES = ["band", "gem_set", "rune_etched", "signet", "twisted"]


def generate_ring_mesh(style: str = "band") -> MeshSpec:
    """Generate a finger ring mesh in the requested style.

    Styles: band, gem_set, rune_etched, signet, twisted.
    Finger radius ~0.009 m.
    """
    if style not in _RING_STYLES:
        style = "band"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    finger_r = 0.009
    ring_thick = 0.002

    if style == "band":
        # Simple polished band
        rv, rf = _make_torus_ring(0, 0, 0, finger_r, ring_thick,
                                  major_segments=16, minor_segments=6)
        parts.append((rv, rf))

    elif style == "gem_set":
        # Band with raised gem setting
        rv, rf = _make_torus_ring(0, 0, 0, finger_r, ring_thick,
                                  major_segments=16, minor_segments=6)
        parts.append((rv, rf))
        # Prong setting
        for pi in range(4):
            pa = pi * math.pi * 2 / 4 + math.pi / 4
            px = math.cos(pa) * ring_thick * 0.6
            pz = math.sin(pa) * ring_thick * 0.6
            pv, pf = _make_cylinder(px, finger_r + ring_thick, pz,
                                    ring_thick * 0.15, ring_thick * 1.2,
                                    segments=3, cap_top=True, cap_bottom=True)
            parts.append((pv, pf))
        # Gem (faceted sphere approximation)
        gv, gf = _make_sphere(0, finger_r + ring_thick * 1.8, 0,
                              ring_thick * 0.8, rings=4, sectors=6)
        parts.append((gv, gf))

    elif style == "rune_etched":
        # Wider band with channel grooves for rune patterns
        rv, rf = _make_torus_ring(0, 0, 0, finger_r, ring_thick * 1.3,
                                  major_segments=20, minor_segments=6)
        parts.append((rv, rf))
        # Rune groove channels (inner torus rings)
        for gi in range(3):
            angle = gi * math.pi * 2 / 3
            gx = math.cos(angle) * finger_r
            gz = math.sin(angle) * finger_r
            gv, gf = _make_torus_ring(gx, ring_thick * 0.8, gz,
                                      ring_thick * 0.3, ring_thick * 0.08,
                                      major_segments=5, minor_segments=3)
            parts.append((gv, gf))

    elif style == "signet":
        # Band with flat face plate for crest/seal
        rv, rf = _make_torus_ring(0, 0, 0, finger_r, ring_thick,
                                  major_segments=16, minor_segments=6)
        parts.append((rv, rf))
        # Flat signet face
        sv, sf = _make_box(0, finger_r + ring_thick * 0.8, 0,
                           ring_thick * 1.5, ring_thick * 0.3, ring_thick * 1.5)
        parts.append((sv, sf))
        # Crest relief (raised octagon)
        crest_r = ring_thick * 1.0
        crest_segs = 8
        crest_verts: list[tuple[float, float, float]] = []
        cy_crest = finger_r + ring_thick * 1.15
        for ci in range(crest_segs):
            ca = 2.0 * math.pi * ci / crest_segs
            crest_verts.append((math.cos(ca) * crest_r, cy_crest,
                               math.sin(ca) * crest_r))
        crest_verts.append((0, cy_crest, 0))
        crest_faces: list[tuple[int, ...]] = []
        center_idx = crest_segs
        for ci in range(crest_segs):
            ci2 = (ci + 1) % crest_segs
            crest_faces.append((ci, ci2, center_idx))
        parts.append((crest_verts, crest_faces))

    elif style == "twisted":
        # Two intertwined bands
        twist_segs = 32
        tube_segs = 4
        for strand in range(2):
            strand_phase = strand * math.pi
            sv: list[tuple[float, float, float]] = []
            sf: list[tuple[int, ...]] = []
            for i in range(twist_segs):
                main_angle = 2.0 * math.pi * i / twist_segs
                twist_angle = main_angle * 3 + strand_phase
                # Position on the main ring
                cx = math.cos(main_angle) * finger_r
                cz = math.sin(main_angle) * finger_r
                # Offset for twist
                off_y = math.sin(twist_angle) * ring_thick * 0.5
                off_r = math.cos(twist_angle) * ring_thick * 0.5
                cx2 = cx + math.cos(main_angle) * off_r
                cz2 = cz + math.sin(main_angle) * off_r
                for j in range(tube_segs):
                    ta = 2.0 * math.pi * j / tube_segs
                    nx = -math.sin(main_angle)
                    nz = math.cos(main_angle)
                    tr = ring_thick * 0.35
                    px = cx2 + nx * math.cos(ta) * tr
                    py = off_y + math.sin(ta) * tr
                    pz = cz2 + nz * math.cos(ta) * tr
                    sv.append((px, py, pz))
            for i in range(twist_segs):
                i2 = (i + 1) % twist_segs
                for j in range(tube_segs):
                    j2 = (j + 1) % tube_segs
                    v0 = i * tube_segs + j
                    v1 = i * tube_segs + j2
                    v2 = i2 * tube_segs + j2
                    v3 = i2 * tube_segs + j
                    sf.append((v0, v1, v2, v3))
            parts.append((sv, sf))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"Ring_{style}", verts_final, faces_final,
                        style=style, slot="ring", category="armor")


# =========================================================================
# AMULET GENERATORS  (5 styles)
# =========================================================================

_AMULET_STYLES = ["pendant", "choker", "torc", "medallion", "holy_symbol"]


def generate_amulet_mesh(style: str = "pendant") -> MeshSpec:
    """Generate an amulet/necklace mesh in the requested style.

    Styles: pendant, choker, torc, medallion, holy_symbol.
    Neck radius ~0.06 m.
    """
    if style not in _AMULET_STYLES:
        style = "pendant"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    neck_r = 0.06
    segs = 12

    if style == "pendant":
        # Chain with hanging pendant gem
        # Chain (torus around neck)
        cv, cf = _make_torus_ring(0, 0, 0, neck_r * 1.3, 0.002,
                                  major_segments=20, minor_segments=3)
        parts.append((cv, cf))
        # Pendant drop
        pv, pf = _make_cone(0, -neck_r * 0.5, neck_r * 1.1,
                            0.012, 0.025, segments=6)
        parts.append((pv, pf))
        # Gem at pendant center
        gv, gf = _make_sphere(0, -neck_r * 0.45, neck_r * 1.1,
                              0.008, rings=4, sectors=6)
        parts.append((gv, gf))
        # Bail (connector ring)
        bv, bf = _make_torus_ring(0, -neck_r * 0.25, neck_r * 1.1,
                                  0.005, 0.001, major_segments=6, minor_segments=3)
        parts.append((bv, bf))

    elif style == "choker":
        # Thick band around throat
        bv, bf = _make_torus_ring(0, 0, 0, neck_r * 1.15, 0.012,
                                  major_segments=segs, minor_segments=6)
        parts.append((bv, bf))
        # Stud decorations
        for si in range(8):
            sa = 2.0 * math.pi * si / 8
            sx = math.cos(sa) * neck_r * 1.15
            sz = math.sin(sa) * neck_r * 1.15
            sv, sf = _make_sphere(sx, 0, sz, 0.004, rings=3, sectors=4)
            parts.append((sv, sf))
        # Central ornament
        ov, of = _make_box(0, 0, neck_r * 1.17,
                           0.015, 0.012, 0.005)
        parts.append((ov, of))

    elif style == "torc":
        # Open-ended twisted metal collar
        torc_segs = 40
        tube_segs = 6
        torc_r = neck_r * 1.25
        wire_r = 0.005
        # Open torc (270 degrees)
        sv: list[tuple[float, float, float]] = []
        sf_list: list[tuple[int, ...]] = []
        open_fraction = 0.75
        for i in range(torc_segs):
            angle = 2.0 * math.pi * open_fraction * i / (torc_segs - 1) + math.pi * 0.25
            cx = math.cos(angle) * torc_r
            cz = math.sin(angle) * torc_r
            for j in range(tube_segs):
                ta = 2.0 * math.pi * j / tube_segs
                nx = -math.sin(angle)
                nz = math.cos(angle)
                px = cx + nx * math.cos(ta) * wire_r
                py = math.sin(ta) * wire_r
                pz = cz + nz * math.cos(ta) * wire_r
                sv.append((px, py, pz))
        for i in range(torc_segs - 1):
            for j in range(tube_segs):
                j2 = (j + 1) % tube_segs
                v0 = i * tube_segs + j
                v1 = i * tube_segs + j2
                v2 = (i + 1) * tube_segs + j2
                v3 = (i + 1) * tube_segs + j
                sf_list.append((v0, v1, v2, v3))
        parts.append((sv, sf_list))
        # Terminal knobs (animal heads / spheres at ends)
        start_angle = math.pi * 0.25
        end_angle = math.pi * 0.25 + 2.0 * math.pi * open_fraction
        for ta in [start_angle, end_angle]:
            tx = math.cos(ta) * torc_r
            tz = math.sin(ta) * torc_r
            tv, tf = _make_sphere(tx, 0, tz, wire_r * 2.5, rings=4, sectors=5)
            parts.append((tv, tf))

    elif style == "medallion":
        # Chain with large flat disk medallion
        cv, cf = _make_torus_ring(0, 0, 0, neck_r * 1.3, 0.002,
                                  major_segments=20, minor_segments=3)
        parts.append((cv, cf))
        # Medallion disk
        mv, mf = _make_cylinder(0, -neck_r * 0.5, neck_r * 1.15,
                                0.02, 0.004, segments=12, cap_top=True, cap_bottom=True)
        parts.append((mv, mf))
        # Medallion border ring
        mrv, mrf = _make_torus_ring(0, -neck_r * 0.5, neck_r * 1.15,
                                    0.022, 0.002, major_segments=12, minor_segments=3)
        parts.append((mrv, mrf))
        # Relief pattern (cross)
        for axis_fn in [(1, 0), (0, 1)]:
            ax, az = axis_fn
            rv, rf = _make_box(ax * 0.0, -neck_r * 0.5, neck_r * 1.15 + az * 0.0,
                               0.002 + ax * 0.015, 0.003, 0.002 + az * 0.015)
            parts.append((rv, rf))

    elif style == "holy_symbol":
        # Sacred symbol on chain -- star shape
        cv, cf = _make_torus_ring(0, 0, 0, neck_r * 1.3, 0.002,
                                  major_segments=20, minor_segments=3)
        parts.append((cv, cf))
        # Symbol center
        sy_y = -neck_r * 0.55
        sy_z = neck_r * 1.1
        scv, scf = _make_sphere(0, sy_y, sy_z, 0.006, rings=3, sectors=6)
        parts.append((scv, scf))
        # Star points (6 rays)
        for ri in range(6):
            ra = ri * math.pi * 2 / 6
            rx = math.cos(ra) * 0.018
            rz_off = math.sin(ra) * 0.018
            rv, rf = _make_box(rx, sy_y, sy_z + rz_off,
                               0.003, 0.003, 0.002)
            parts.append((rv, rf))
        # Bail
        bv, bf = _make_torus_ring(0, sy_y + 0.015, sy_z,
                                  0.004, 0.001, major_segments=6, minor_segments=3)
        parts.append((bv, bf))
        # Halo ring behind symbol
        hv, hf = _make_torus_ring(0, sy_y, sy_z - 0.003,
                                  0.022, 0.001, major_segments=12, minor_segments=3)
        parts.append((hv, hf))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"Amulet_{style}", verts_final, faces_final,
                        style=style, slot="amulet", category="armor")


# =========================================================================
# BACK ITEM GENERATORS  (5 styles)
# =========================================================================

_BACK_ITEM_STYLES = ["backpack", "quiver", "wings", "trophy_mount", "bedroll"]


def generate_back_item_mesh(style: str = "backpack") -> MeshSpec:
    """Generate a back-mounted item mesh in the requested style.

    Styles: backpack, quiver, wings, trophy_mount, bedroll.
    Positioned relative to upper back center.
    """
    if style not in _BACK_ITEM_STYLES:
        style = "backpack"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "backpack":
        # Framed backpack with straps and flap
        bw, bh, bd = 0.20, 0.30, 0.12
        # Main body
        bv, bf = _make_box(0, bh * 0.5, -bd * 0.5, bw * 0.5, bh * 0.5, bd * 0.5)
        parts.append((bv, bf))
        # Top flap
        fv, ff = _make_box(0, bh + 0.01, -bd * 0.3, bw * 0.52, 0.015, bd * 0.4)
        parts.append((fv, ff))
        # Shoulder straps (left / right)
        for sx in [-bw * 0.35, bw * 0.35]:
            sv, sf = _make_box(sx, bh * 0.5, bd * 0.05,
                               0.018, bh * 0.45, 0.008)
            parts.append((sv, sf))
        # Side pockets
        for sx in [-bw * 0.55, bw * 0.55]:
            pv, pf = _make_box(sx, bh * 0.25, -bd * 0.3,
                               0.03, bh * 0.22, bd * 0.2)
            parts.append((pv, pf))
        # Frame (top/bottom bars)
        for fy in [0.01, bh - 0.01]:
            frv, frf = _make_cylinder(0, fy, 0, 0.008, bw * 0.9,
                                      segments=4, cap_top=True, cap_bottom=True)
            # Rotate to horizontal (X axis) by swapping
            frv = [(v[2], v[1], v[0]) for v in frv]
            parts.append((frv, frf))
        # Bedroll on top
        brv, brf = _make_cylinder(0, bh + 0.04, -bd * 0.3,
                                  0.03, bw * 0.7, segments=8)
        brv = [(v[2], v[1], v[0]) for v in brv]
        parts.append((brv, brf))

    elif style == "quiver":
        # Arrow quiver with arrows visible
        qr = 0.05
        qh = 0.40
        # Quiver body (tapered cylinder)
        qv, qf = _make_tapered_cylinder(0, 0, -0.05, qr, qr * 0.7,
                                        qh, segments=8, rings=2)
        parts.append((qv, qf))
        # Rim at top
        rv, rf = _make_torus_ring(0, qh, -0.05, qr, qr * 0.08,
                                  major_segments=8, minor_segments=3)
        parts.append((rv, rf))
        # Strap
        sv, sf = _make_box(qr * 0.5, qh * 0.5, 0.02,
                           0.012, qh * 0.4, 0.005)
        parts.append((sv, sf))
        # Arrow shafts poking out (5 arrows)
        for ai in range(5):
            ax = (ai - 2) * qr * 0.3
            az = -0.05 + (ai % 2) * qr * 0.2
            av, af = _make_cylinder(ax, qh - 0.02, az, 0.003, 0.12,
                                    segments=4, cap_top=True, cap_bottom=False)
            parts.append((av, af))
            # Fletching
            fv, ff = _make_box(ax, qh + 0.08, az, 0.008, 0.015, 0.001)
            parts.append((fv, ff))

    elif style == "wings":
        # Decorative or angelic wings (folded)
        wing_span = 0.25
        wing_h = 0.35
        for side in [-1.0, 1.0]:
            # Main wing surface (curved sheet)
            subdiv_x = 6
            subdiv_y = 8
            wv: list[tuple[float, float, float]] = []
            wf: list[tuple[int, ...]] = []
            for iy in range(subdiv_y + 1):
                ty = iy / subdiv_y
                for ix in range(subdiv_x + 1):
                    tx = ix / subdiv_x
                    x = side * tx * wing_span * (1.0 - ty * 0.4)
                    y = wing_h * (1.0 - ty)
                    z = -0.02 - tx * 0.08 * math.sin(ty * math.pi)
                    wv.append((x, y, z))
            cols = subdiv_x + 1
            for iy in range(subdiv_y):
                for ix in range(subdiv_x):
                    v0 = iy * cols + ix
                    v1 = v0 + 1
                    v2 = v0 + cols + 1
                    v3 = v0 + cols
                    wf.append((v0, v1, v2, v3))
            parts.append((wv, wf))
            # Feather tips at bottom edge
            for fi in range(4):
                fx = side * (fi + 1) * wing_span * 0.2
                fv, ff = _make_box(fx, -0.02, -0.04,
                                   0.015, 0.03, 0.004)
                parts.append((fv, ff))
        # Central spine
        csv, csf = _make_cylinder(0, 0, -0.03, 0.008, wing_h * 0.8,
                                  segments=5, cap_top=True, cap_bottom=True)
        parts.append((csv, csf))

    elif style == "trophy_mount":
        # Rack with mounted trophies (skulls, horns)
        # Wooden frame
        frame_w, frame_h = 0.18, 0.22
        fv, ff = _make_box(0, frame_h * 0.5, -0.04,
                           frame_w * 0.5, frame_h * 0.5, 0.015)
        parts.append((fv, ff))
        # Cross bar
        cbv, cbf = _make_cylinder(0, frame_h * 0.7, -0.03,
                                  0.008, frame_w * 0.8, segments=5)
        cbv = [(v[2], v[1], v[0]) for v in cbv]
        parts.append((cbv, cbf))
        # Trophy skull (simplified)
        sv, sf = _make_sphere(0, frame_h * 0.8, -0.06,
                              0.04, rings=5, sectors=7)
        parts.append((sv, sf))
        # Horns on skull
        for hside in [-1.0, 1.0]:
            hv, hf = _make_cone(hside * 0.04, frame_h * 0.85, -0.07,
                                0.008, 0.06, segments=5)
            parts.append((hv, hf))
        # Hanging chains
        for ci in range(2):
            cx = (-0.06 + ci * 0.12)
            ccv, ccf = _make_cylinder(cx, 0.02, -0.03,
                                      0.003, frame_h * 0.5, segments=3)
            parts.append((ccv, ccf))
        # Strap
        stv, stf = _make_box(0, frame_h * 0.5, 0.02,
                             0.015, frame_h * 0.35, 0.005)
        parts.append((stv, stf))

    elif style == "bedroll":
        # Simple rolled blanket/sleeping bag
        roll_r = 0.06
        roll_w = 0.35
        rv, rf = _make_cylinder(0, 0, -0.04, roll_r, roll_w,
                                segments=10, cap_top=True, cap_bottom=True)
        # Rotate to horizontal
        rv = [(v[2], v[1], v[0]) for v in rv]
        parts.append((rv, rf))
        # Tie straps
        for tx in [-roll_w * 0.3, 0, roll_w * 0.3]:
            tv, tf = _make_torus_ring(tx, 0, -0.04, roll_r * 1.1, roll_r * 0.06,
                                      major_segments=8, minor_segments=3)
            parts.append((tv, tf))
        # Exposed blanket edge
        ev, ef = _make_box(roll_w * 0.45, 0, -0.04,
                           0.01, roll_r * 0.8, roll_r * 0.8)
        parts.append((ev, ef))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"BackItem_{style}", verts_final, faces_final,
                        style=style, slot="back_item", category="armor")


# =========================================================================
# FACE ITEM GENERATORS  (5 styles)
# =========================================================================

_FACE_ITEM_STYLES = ["mask", "blindfold", "war_paint_frame", "plague_doctor", "domino"]


def generate_face_item_mesh(style: str = "mask") -> MeshSpec:
    """Generate a face-covering item mesh in the requested style.

    Styles: mask, blindfold, war_paint_frame, plague_doctor, domino.
    Built around a face region (head radius ~0.11 m).
    """
    if style not in _FACE_ITEM_STYLES:
        style = "mask"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hr = 0.11  # head radius
    segs = 10

    if style == "mask":
        # Full-face mask with eye holes and breathing slits
        # Curved face plate
        fpv, fpf = _make_half_sphere(0, hr * 0.35, hr * 0.15, hr * 1.08,
                                     rings=6, sectors=segs, top=True)
        parts.append((fpv, fpf))
        # Eye holes (inset spheres for depth)
        for sx in [-1.0, 1.0]:
            ev, ef = _make_sphere(sx * hr * 0.28, hr * 0.48, hr * 0.90,
                                  hr * 0.10, rings=3, sectors=5)
            parts.append((ev, ef))
        # Nose ridge
        nv, nf = _make_box(0, hr * 0.30, hr * 1.05,
                           hr * 0.04, hr * 0.12, hr * 0.02)
        parts.append((nv, nf))
        # Mouth breathing slits (3 horizontal bars)
        for mi in range(3):
            mv, mf = _make_box(0, hr * 0.10 + mi * hr * 0.06, hr * 1.00,
                               hr * 0.18, hr * 0.01, hr * 0.015)
            parts.append((mv, mf))
        # Strap anchors (sides)
        for sx in [-1.0, 1.0]:
            av, af = _make_box(sx * hr * 0.85, hr * 0.40, hr * 0.50,
                               hr * 0.05, hr * 0.08, hr * 0.04)
            parts.append((av, af))

    elif style == "blindfold":
        # Cloth strip covering eyes
        bf_w = hr * 1.8
        bf_h = hr * 0.35
        bf_d = 0.005
        # Main strip (curved to follow head)
        subdiv = 8
        bv: list[tuple[float, float, float]] = []
        bfaces: list[tuple[int, ...]] = []
        for iy in range(3):
            ty = iy / 2
            y = hr * 0.35 + ty * bf_h
            for ix in range(subdiv + 1):
                tx = ix / subdiv
                angle = (tx - 0.5) * math.pi * 0.8
                x = math.sin(angle) * hr * 1.10
                z = math.cos(angle) * hr * 1.10
                bv.append((x, y, z))
        cols = subdiv + 1
        for iy in range(2):
            for ix in range(subdiv):
                v0 = iy * cols + ix
                v1 = v0 + 1
                v2 = v0 + cols + 1
                v3 = v0 + cols
                bfaces.append((v0, v1, v2, v3))
        parts.append((bv, bfaces))
        # Knot at back
        kv, kf = _make_sphere(0, hr * 0.50, -hr * 1.05,
                              hr * 0.06, rings=3, sectors=5)
        parts.append((kv, kf))
        # Trailing tails
        for side in [-1.0, 1.0]:
            tv, tf = _make_box(side * hr * 0.08, hr * 0.35, -hr * 1.10,
                               hr * 0.03, hr * 0.20, hr * 0.01)
            parts.append((tv, tf))

    elif style == "war_paint_frame":
        # Skeletal face frame outlining war paint regions
        # Brow ridge
        brv, brf = _make_torus_ring(0, hr * 0.60, hr * 0.65, hr * 0.45, hr * 0.025,
                                    major_segments=8, minor_segments=3)
        parts.append((brv, brf))
        # Cheekbone struts
        for sx in [-1.0, 1.0]:
            cv, cf = _make_box(sx * hr * 0.50, hr * 0.30, hr * 0.80,
                               hr * 0.03, hr * 0.15, hr * 0.02)
            parts.append((cv, cf))
        # Nose bridge
        nv, nf = _make_box(0, hr * 0.38, hr * 1.02,
                           hr * 0.025, hr * 0.18, hr * 0.015)
        parts.append((nv, nf))
        # Jaw outline
        jv, jf = _make_torus_ring(0, hr * 0.08, hr * 0.60, hr * 0.40, hr * 0.02,
                                  major_segments=8, minor_segments=3)
        parts.append((jv, jf))
        # Temple horns (small)
        for sx in [-1.0, 1.0]:
            thv, thf = _make_cone(sx * hr * 0.65, hr * 0.55, hr * 0.55,
                                  hr * 0.03, hr * 0.08, segments=4)
            parts.append((thv, thf))

    elif style == "plague_doctor":
        # Plague doctor beak mask
        # Face plate (half sphere)
        fpv, fpf = _make_half_sphere(0, hr * 0.35, hr * 0.15, hr * 1.06,
                                     rings=5, sectors=segs, top=True)
        parts.append((fpv, fpf))
        # Eye lenses (cylindrical goggle rings)
        for sx in [-1.0, 1.0]:
            lv, lf = _make_cylinder(sx * hr * 0.28, hr * 0.45, hr * 0.95,
                                    hr * 0.10, hr * 0.08, segments=8,
                                    cap_top=True, cap_bottom=True)
            # Orient forward (swap Y/Z)
            lv = [(v[0], v[1], v[2]) for v in lv]
            parts.append((lv, lf))
            # Lens rim
            lrv, lrf = _make_torus_ring(sx * hr * 0.28, hr * 0.45, hr * 1.03,
                                        hr * 0.10, hr * 0.015,
                                        major_segments=8, minor_segments=3)
            parts.append((lrv, lrf))
        # Beak (tapered cone)
        beak_len = hr * 0.8
        bkv, bkf = _make_tapered_cylinder(0, hr * 0.20, hr * 1.05,
                                          hr * 0.10, hr * 0.02,
                                          beak_len, segments=6, rings=3)
        # Orient forward (bend beak from face)
        bkv_r: list[tuple[float, float, float]] = []
        for v in bkv:
            fwd = (v[1] - hr * 0.20) / max(beak_len, 0.001)
            new_y = hr * 0.20 + (v[1] - hr * 0.20) * 0.3
            new_z = hr * 1.05 + fwd * beak_len * 0.9
            bkv_r.append((v[0], new_y, new_z))
        parts.append((bkv_r, bkf))
        # Strap
        for sx in [-1.0, 1.0]:
            sv, sf = _make_box(sx * hr * 0.85, hr * 0.40, hr * 0.40,
                               hr * 0.04, hr * 0.06, hr * 0.03)
            parts.append((sv, sf))

    elif style == "domino":
        # Simple half-mask covering upper face
        # Curved strip across eyes
        subdiv_x = 10
        subdiv_y = 3
        dv: list[tuple[float, float, float]] = []
        df: list[tuple[int, ...]] = []
        for iy in range(subdiv_y + 1):
            ty = iy / subdiv_y
            y = hr * 0.35 + ty * hr * 0.35
            for ix in range(subdiv_x + 1):
                tx = ix / subdiv_x
                angle = (tx - 0.5) * math.pi * 0.7
                x = math.sin(angle) * hr * 1.08
                z = math.cos(angle) * hr * 1.08
                dv.append((x, y, z))
        cols = subdiv_x + 1
        for iy in range(subdiv_y):
            for ix in range(subdiv_x):
                v0 = iy * cols + ix
                v1 = v0 + 1
                v2 = v0 + cols + 1
                v3 = v0 + cols
                df.append((v0, v1, v2, v3))
        parts.append((dv, df))
        # Eye holes (cutout markers)
        for sx in [-1.0, 1.0]:
            ev, ef = _make_sphere(sx * hr * 0.25, hr * 0.48, hr * 1.02,
                                  hr * 0.07, rings=3, sectors=5)
            parts.append((ev, ef))
        # Decorative points at outer edges
        for sx in [-1.0, 1.0]:
            pv, pf = _make_cone(sx * hr * 0.70, hr * 0.50, hr * 0.80,
                                hr * 0.03, hr * 0.06, segments=4)
            parts.append((pv, pf))

    verts_final, faces_final = _merge_meshes(*parts)
    return _make_result(f"FaceItem_{style}", verts_final, faces_final,
                        style=style, slot="face_item", category="armor")


# =========================================================================
# ARMOR_GENERATORS registry
# =========================================================================

ARMOR_GENERATORS = {
    "helmet": (generate_helmet_mesh, {"styles": _HELMET_STYLES}),
    "chest_armor": (generate_chest_armor_mesh, {"styles": _CHEST_STYLES}),
    "gauntlet": (generate_gauntlet_mesh, {"styles": _GAUNTLET_STYLES}),
    "boot": (generate_boot_mesh, {"styles": _BOOT_STYLES}),
    "pauldron": (generate_pauldron_mesh, {"styles": _PAULDRON_STYLES}),
    "cape": (generate_cape_mesh, {"styles": _CAPE_STYLES}),
    "belt": (generate_belt_mesh, {"styles": _BELT_STYLES}),
    "bracer": (generate_bracer_mesh, {"styles": _BRACER_STYLES}),
    "ring": (generate_ring_mesh, {"styles": _RING_STYLES}),
    "amulet": (generate_amulet_mesh, {"styles": _AMULET_STYLES}),
    "back_item": (generate_back_item_mesh, {"styles": _BACK_ITEM_STYLES}),
    "face_item": (generate_face_item_mesh, {"styles": _FACE_ITEM_STYLES}),
}
