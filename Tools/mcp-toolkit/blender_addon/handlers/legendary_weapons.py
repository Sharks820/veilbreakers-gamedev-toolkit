"""Legendary unique weapon mesh generation for VeilBreakers.

Each legendary weapon has a DRAMATICALLY different silhouette from its
base weapon type -- not just a material swap. These are one-of-a-kind
weapons with distinctive visual features.

Provides:
- LEGENDARY_WEAPONS: registry of 10 legendary weapon definitions
- generate_legendary_weapon_mesh(weapon_name): generate mesh for a named legendary
- LEGENDARY_GENERATORS: dict mapping weapon_name -> generator function

All functions are pure Python with math-only dependencies (no bpy/bmesh).
Uses the same _make_result / _merge_meshes pattern as procedural_meshes.py.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type alias (same as procedural_meshes.py)
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# Internal mesh primitives (self-contained, no import from procedural_meshes)
# ---------------------------------------------------------------------------


def _compute_dimensions(
    verts: list[tuple[float, float, float]],
) -> dict[str, float]:
    """Return bounding-box width/height/depth from vertex list."""
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
    """Package vertices/faces into a standard mesh spec dict."""
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
            "category": "legendary_weapon",
            **extra_meta,
        },
    }


def _merge_meshes(
    *parts: tuple[list[tuple[float, float, float]], list[tuple[int, ...]]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Merge multiple (verts, faces) tuples, remapping face indices."""
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    for verts, faces in parts:
        offset = len(all_verts)
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces


def _make_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder along Y axis."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for ring in range(2):
        y = cy_bottom + ring * height
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            verts.append((cx + math.cos(a) * radius, y, cz + math.sin(a) * radius))
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((i, i2, segments + i2, segments + i))
    faces.append(tuple(range(segments - 1, -1, -1)))
    faces.append(tuple(range(segments, 2 * segments)))
    return verts, faces


def _make_tapered_cylinder(
    cx: float, cy_bottom: float, cz: float,
    r_bottom: float, r_top: float, height: float,
    segments: int = 8, rings: int = 1,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder tapering from r_bottom to r_top along Y."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    total_rings = rings + 1
    for ring in range(total_rings):
        t = ring / max(rings, 1)
        y = cy_bottom + t * height
        r = r_bottom + t * (r_top - r_bottom)
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            verts.append((cx + math.cos(a) * r, y, cz + math.sin(a) * r))
    for ring in range(rings):
        for i in range(segments):
            i2 = (i + 1) % segments
            r0 = ring * segments
            r1 = (ring + 1) * segments
            faces.append((r0 + i, r0 + i2, r1 + i2, r1 + i))
    faces.append(tuple(range(segments - 1, -1, -1)))
    last = rings * segments
    faces.append(tuple(range(last, last + segments)))
    return verts, faces


def _make_cone(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cone with apex at top along Y."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(a) * radius, cy_bottom, cz + math.sin(a) * radius))
    apex_idx = segments
    verts.append((cx, cy_bottom + height, cz))
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((i, i2, apex_idx))
    faces.append(tuple(range(segments - 1, -1, -1)))
    return verts, faces


def _make_sphere(
    cx: float, cy: float, cz: float,
    radius: float, rings: int = 6, sectors: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a UV sphere."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    verts.append((cx, cy - radius, cz))
    for i in range(1, rings):
        phi = math.pi * i / rings
        y = cy - radius * math.cos(phi)
        rr = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2.0 * math.pi * j / sectors
            verts.append((cx + rr * math.cos(theta), y, cz + rr * math.sin(theta)))
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
    last_ring = 1 + (rings - 2) * sectors
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((last_ring + j, top_idx, last_ring + j2))
    return verts, faces


def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate an axis-aligned box with half-sizes sx, sy, sz."""
    verts = [
        (cx - sx, cy - sy, cz - sz), (cx + sx, cy - sy, cz - sz),
        (cx + sx, cy + sy, cz - sz), (cx - sx, cy + sy, cz - sz),
        (cx - sx, cy - sy, cz + sz), (cx + sx, cy - sy, cz + sz),
        (cx + sx, cy + sy, cz + sz), (cx - sx, cy + sy, cz + sz),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (2, 3, 7, 6), (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return verts, faces


def _make_torus_ring(
    cx: float, cy: float, cz: float,
    major_r: float, minor_r: float,
    major_segs: int = 8, minor_segs: int = 4,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a torus in XZ plane at (cx, cy, cz)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(major_segs):
        theta = 2.0 * math.pi * i / major_segs
        ct, st = math.cos(theta), math.sin(theta)
        for j in range(minor_segs):
            phi = 2.0 * math.pi * j / minor_segs
            cp, sp = math.cos(phi), math.sin(phi)
            r = major_r + minor_r * cp
            verts.append((cx + r * ct, cy + minor_r * sp, cz + r * st))
    for i in range(major_segs):
        inext = (i + 1) % major_segs
        for j in range(minor_segs):
            jnext = (j + 1) % minor_segs
            v0 = i * minor_segs + j
            v1 = i * minor_segs + jnext
            v2 = inext * minor_segs + jnext
            v3 = inext * minor_segs + j
            faces.append((v0, v1, v2, v3))
    return verts, faces


# ---------------------------------------------------------------------------
# Legendary weapon definitions
# ---------------------------------------------------------------------------

LEGENDARY_WEAPONS: dict[str, dict[str, str]] = {
    "voidreaver": {
        "type": "greatsword",
        "feature": "split_blade",
        "desc": "Blade splits into reality-tearing fork",
    },
    "chainbreaker": {
        "type": "warhammer",
        "feature": "anchor_head",
        "desc": "Massive anchor-shaped hammer head",
    },
    "serpents_fang": {
        "type": "curved_sword",
        "feature": "double_curve",
        "desc": "S-curved blade like a striking snake",
    },
    "crystalheart_staff": {
        "type": "staff",
        "feature": "crystal_cage",
        "desc": "Staff with caged floating crystal",
    },
    "widowmaker": {
        "type": "crossbow",
        "feature": "bone_frame",
        "desc": "Crossbow made of fused monster bones",
    },
    "soulcatcher": {
        "type": "shield",
        "feature": "eye_center",
        "desc": "Shield with living eye in center",
    },
    "bloodthorn": {
        "type": "whip",
        "feature": "vine_thorns",
        "desc": "Living vine whip with razor thorns",
    },
    "stormcaller": {
        "type": "halberd",
        "feature": "lightning_blade",
        "desc": "Halberd with jagged lightning-bolt blade",
    },
    "bonecrown": {
        "type": "helmet",
        "feature": "skull_horns",
        "desc": "Crown of fused skulls with horn spires",
    },
    "abyssal_claw": {
        "type": "claw",
        "feature": "void_fingers",
        "desc": "Gauntlet with void-energy finger extensions",
    },
}

VALID_LEGENDARY_NAMES = frozenset(LEGENDARY_WEAPONS.keys())


# ---------------------------------------------------------------------------
# Individual legendary weapon generators
# ---------------------------------------------------------------------------


def _generate_voidreaver() -> MeshSpec:
    """Voidreaver -- greatsword with split blade forking into two prongs.

    The blade starts as one piece, then splits 40% up into two diverging
    blades with a void gap between them. Dramatically different silhouette
    from any standard greatsword.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Handle
    handle_len, handle_r = 0.35, 0.018
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.95, handle_len, segs, rings=3)
    parts.append((hv, hf))

    # Pommel
    pv, pf = _make_sphere(0, -0.025, 0, handle_r * 2.2, rings=4, sectors=6)
    parts.append((pv, pf))

    # Guard -- wider than normal, angular
    guard_y = handle_len
    gv, gf = _make_box(0, guard_y + 0.008, 0, 0.08, 0.008, 0.012)
    parts.append((gv, gf))
    # Guard spikes
    for side in [-1, 1]:
        sv, sf = _make_cone(side * 0.08, guard_y + 0.008, 0, 0.008, side * 0.03, segments=4)
        parts.append((sv, sf))

    # Unified blade section (lower 40%)
    blade_base_y = guard_y + 0.016
    unified_h = 0.30
    blade_thick = 0.005
    blade_w = 0.035
    bv: list[tuple[float, float, float]] = []
    bf: list[tuple[int, ...]] = []
    blade_segs = 6
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * unified_h
        w = blade_w * (1.0 + t * 0.1)  # slightly widens before split
        bv.extend([(-w, y, blade_thick), (w, y, blade_thick),
                    (w, y, -blade_thick), (-w, y, -blade_thick)])
    for i in range(blade_segs):
        b = i * 4
        for j in range(4):
            j2 = (j + 1) % 4
            bf.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
    parts.append((bv, bf))

    # Split blade -- two prongs diverging outward
    split_y = blade_base_y + unified_h
    prong_h = 0.55
    prong_segs = 10
    for side in [-1, 1]:
        pv2: list[tuple[float, float, float]] = []
        pf2: list[tuple[int, ...]] = []
        for i in range(prong_segs + 1):
            t = i / prong_segs
            y = split_y + t * prong_h
            # Prongs diverge outward
            offset_x = side * (0.01 + t * 0.04)
            w = blade_w * 0.6 * (1.0 - t * 0.5)
            pv2.extend([(offset_x - w, y, blade_thick * 0.8),
                        (offset_x + w, y, blade_thick * 0.8),
                        (offset_x + w, y, -blade_thick * 0.8),
                        (offset_x - w, y, -blade_thick * 0.8)])
        for i in range(prong_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                pf2.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        # Tip
        tip_y = split_y + prong_h
        tip_x = side * (0.01 + 0.04)
        pv2.append((tip_x, tip_y + 0.04, 0))
        tb = prong_segs * 4
        ti = len(pv2) - 1
        for j in range(4):
            pf2.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((pv2, pf2))

    # Void crystal between prongs
    crystal_y = split_y + prong_h * 0.5
    cv, cf = _make_sphere(0, crystal_y, 0, 0.015, rings=4, sectors=6)
    parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    trail_top = split_y + prong_h + 0.04
    return _make_result(
        "Legendary_Voidreaver", verts, faces,
        legendary_name="voidreaver", weapon_type="greatsword",
        feature="split_blade",
        grip_point=(0.0, handle_len * 0.4, 0.0),
        trail_top=(0.0, trail_top, 0.0),
        trail_bottom=(0.0, blade_base_y, 0.0),
    )


def _generate_chainbreaker() -> MeshSpec:
    """Chainbreaker -- warhammer with massive anchor-shaped head.

    Instead of a standard hammer face, the head resembles a ship anchor
    with curved flukes on each side and a heavy crown at top.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Long handle
    handle_len, handle_r = 0.65, 0.016
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=4)
    parts.append((hv, hf))

    # Pommel -- heavy ball
    pv, pf = _make_sphere(0, -0.025, 0, handle_r * 2.5, rings=4, sectors=6)
    parts.append((pv, pf))

    # Collar at handle top
    cv, cf = _make_torus_ring(0, handle_len * 0.82, 0, handle_r * 2, handle_r * 0.5, 8, 4)
    parts.append((cv, cf))

    head_y = handle_len * 0.85

    # Central shank (vertical bar above handle)
    shank_h = 0.12
    sv, sf = _make_tapered_cylinder(0, head_y, 0, 0.015, 0.012, shank_h, 6, rings=2)
    parts.append((sv, sf))

    # Crown (top of anchor -- ring/ball)
    crown_y = head_y + shank_h
    crv, crf = _make_sphere(0, crown_y + 0.015, 0, 0.02, rings=4, sectors=6)
    parts.append((crv, crf))

    # Cross bar (horizontal bar of anchor)
    cross_w = 0.10
    cross_thick = 0.012
    cbv, cbf = _make_box(0, head_y, 0, cross_w, cross_thick / 2, cross_thick / 2)
    parts.append((cbv, cbf))

    # Flukes (curved anchor arms) -- each side
    fluke_segs = 8
    for side in [-1, 1]:
        fv: list[tuple[float, float, float]] = []
        ff: list[tuple[int, ...]] = []
        for i in range(fluke_segs + 1):
            t = i / fluke_segs
            # Curve downward and inward
            angle = t * math.pi * 0.6
            fx = side * (cross_w - t * cross_w * 0.3)
            fy = head_y - math.sin(angle) * 0.08
            fz = 0.0
            w = 0.008 * (1.0 - t * 0.3)
            fv.extend([(fx - w, fy, w), (fx + w, fy, w),
                       (fx + w, fy, -w), (fx - w, fy, -w)])
        for i in range(fluke_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                ff.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        # Fluke tip (pointed)
        last_t = 1.0
        tip_angle = last_t * math.pi * 0.6
        tip_x = side * (cross_w - last_t * cross_w * 0.3)
        tip_y = head_y - math.sin(tip_angle) * 0.08 - 0.03
        fv.append((tip_x, tip_y, 0))
        tb = fluke_segs * 4
        ti = len(fv) - 1
        for j in range(4):
            ff.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    trail_top_y = crown_y + 0.035
    return _make_result(
        "Legendary_Chainbreaker", verts, faces,
        legendary_name="chainbreaker", weapon_type="warhammer",
        feature="anchor_head",
        grip_point=(0.0, handle_len * 0.3, 0.0),
        trail_top=(0.0, trail_top_y, 0.0),
        trail_bottom=(0.0, head_y - 0.08, 0.0),
    )


def _generate_serpents_fang() -> MeshSpec:
    """Serpent's Fang -- S-curved blade like a striking snake.

    The blade follows a sinusoidal S-curve rather than a simple arc,
    giving it a distinctly serpentine silhouette with a fang-like tip.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Handle with wrapped texture (snake scales implied)
    handle_len, handle_r = 0.22, 0.013
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.2, handle_r * 0.8, handle_len, segs, rings=3)
    parts.append((hv, hf))

    # Snake head pommel
    pv, pf = _make_sphere(0, -0.02, 0, 0.02, rings=5, sectors=6)
    parts.append((pv, pf))
    # Eyes on pommel
    for side in [-1, 1]:
        ev, ef = _make_sphere(side * 0.015, -0.015, 0.012, 0.005, rings=3, sectors=4)
        parts.append((ev, ef))

    # Minimal guard -- fang-like
    guard_y = handle_len
    for side in [-1, 1]:
        gv, gf = _make_cone(side * 0.02, guard_y, 0, 0.005, side * 0.025, segments=4)
        parts.append((gv, gf))

    # S-curved blade
    blade_base_y = guard_y + 0.01
    blade_h = 0.65
    blade_segs = 20
    blade_thick = 0.004
    bv: list[tuple[float, float, float]] = []
    bf: list[tuple[int, ...]] = []
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * blade_h
        # S-curve: sine wave with one full period
        s_offset = math.sin(t * math.pi * 2) * 0.04
        # Width narrows toward tip
        w = 0.025 * (1.0 - t * 0.6)
        # Single-edge: thick back, thin edge
        bv.extend([(s_offset - w * 0.3, y, blade_thick),
                    (s_offset + w, y, blade_thick * 0.3),
                    (s_offset + w, y, -blade_thick * 0.3),
                    (s_offset - w * 0.3, y, -blade_thick)])
    for i in range(blade_segs):
        b = i * 4
        for j in range(4):
            j2 = (j + 1) % 4
            bf.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
    # Fang tip (sharp, curved forward)
    tip_y = blade_base_y + blade_h
    tip_offset = math.sin(math.pi * 2) * 0.04  # at t=1.0
    bv.append((tip_offset, tip_y + 0.03, 0))
    tb = blade_segs * 4
    ti = len(bv) - 1
    for j in range(4):
        bf.append((tb + j, tb + (j + 1) % 4, ti))
    parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_SerpentsFang", verts, faces,
        legendary_name="serpents_fang", weapon_type="curved_sword",
        feature="double_curve",
        grip_point=(0.0, handle_len * 0.4, 0.0),
        trail_top=(0.0, tip_y + 0.03, 0.0),
        trail_bottom=(0.0, blade_base_y, 0.0),
    )


def _generate_crystalheart_staff() -> MeshSpec:
    """Crystalheart Staff -- staff with a caged floating crystal at the top.

    The top of the staff has curved metal ribs forming an open cage,
    with a crystal sphere floating in the center. Distinctive from
    any standard staff silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Long staff shaft
    shaft_len, shaft_r = 1.5, 0.012
    sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r * 1.1, shaft_r * 0.9, shaft_len, segs, rings=6)
    parts.append((sv, sf))

    # Bottom cap -- crystal fragment
    bv, bf = _make_cone(0, -0.01, 0, shaft_r * 1.5, -0.04, segments=5)
    parts.append((bv, bf))

    # Cage ribs (4 ribs curving upward and inward)
    cage_base_y = shaft_len
    cage_h = 0.15
    cage_r = 0.05
    rib_segs = 8
    for rib in range(4):
        rib_angle = rib * math.pi / 2
        rv: list[tuple[float, float, float]] = []
        rf: list[tuple[int, ...]] = []
        for i in range(rib_segs + 1):
            t = i / rib_segs
            y = cage_base_y + t * cage_h
            # Ribs bow outward then converge at top
            bow = math.sin(t * math.pi) * cage_r
            rx = math.cos(rib_angle) * (shaft_r + bow)
            rz = math.sin(rib_angle) * (shaft_r + bow)
            rib_r = 0.004 * (1.0 - t * 0.3)
            # Simple quad strip for each rib
            rv.extend([(rx - rib_r, y, rz), (rx + rib_r, y, rz)])
        for i in range(rib_segs):
            b = i * 2
            rf.append((b, b + 1, b + 3, b + 2))
        parts.append((rv, rf))

    # Floating crystal in cage center
    crystal_y = cage_base_y + cage_h * 0.5
    crv, crf = _make_sphere(0, crystal_y, 0, 0.025, rings=5, sectors=6)
    parts.append((crv, crf))

    # Small crystal shards orbiting
    for i in range(3):
        shard_angle = i * math.pi * 2 / 3
        sx = math.cos(shard_angle) * 0.035
        sz = math.sin(shard_angle) * 0.035
        sy = crystal_y + math.sin(i * 1.5) * 0.01
        shv, shf = _make_cone(sx, sy, sz, 0.005, 0.015, segments=4)
        parts.append((shv, shf))

    # Cage crown (ring at top where ribs meet)
    crownv, crownf = _make_torus_ring(0, cage_base_y + cage_h, 0, shaft_r * 0.8, 0.004, 6, 3)
    parts.append((crownv, crownf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_CrystalheartStaff", verts, faces,
        legendary_name="crystalheart_staff", weapon_type="staff",
        feature="crystal_cage",
        grip_point=(0.0, shaft_len * 0.35, 0.0),
        trail_top=(0.0, cage_base_y + cage_h + 0.01, 0.0),
        trail_bottom=(0.0, cage_base_y, 0.0),
    )


def _generate_widowmaker() -> MeshSpec:
    """Widowmaker -- crossbow made of fused monster bones.

    Arms are curved bone limbs, stock is a spinal column,
    and the prod is a jawbone. Organic silhouette unlike any standard crossbow.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Spinal column stock
    stock_len = 0.5
    stock_segs = 10
    stock_r = 0.014
    sv: list[tuple[float, float, float]] = []
    sf: list[tuple[int, ...]] = []
    spine_segs_circ = 6
    for i in range(stock_segs + 1):
        t = i / stock_segs
        y = t * stock_len
        # Vertebra-like bumps
        bump = math.sin(t * math.pi * 8) * 0.003
        r = stock_r + bump
        for j in range(spine_segs_circ):
            a = 2.0 * math.pi * j / spine_segs_circ
            sv.append((math.cos(a) * r, y, math.sin(a) * r))
    for i in range(stock_segs):
        for j in range(spine_segs_circ):
            j2 = (j + 1) % spine_segs_circ
            r0 = i * spine_segs_circ
            r1 = (i + 1) * spine_segs_circ
            sf.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    parts.append((sv, sf))

    # Bone limbs (crossbow arms) -- curved bone
    prod_y = stock_len * 0.7
    for side in [-1, 1]:
        limb_segs = 8
        lv: list[tuple[float, float, float]] = []
        lf: list[tuple[int, ...]] = []
        for i in range(limb_segs + 1):
            t = i / limb_segs
            # Limbs curve outward and slightly forward
            lx = side * t * 0.15
            ly = prod_y + math.sin(t * math.pi * 0.3) * 0.03
            lz = t * 0.03
            r = 0.008 * (1.0 - t * 0.4)
            lv.extend([(lx - r, ly, lz + r), (lx + r, ly, lz + r),
                       (lx + r, ly, lz - r), (lx - r, ly, lz - r)])
        for i in range(limb_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                lf.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        # Bone tip
        tip_x = side * 0.15
        lv.append((tip_x, prod_y, 0.03))
        tb = limb_segs * 4
        ti = len(lv) - 1
        for j in range(4):
            lf.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((lv, lf))

    # Jawbone prod (where the string attaches)
    jv, jf = _make_box(0, prod_y, 0.02, 0.04, 0.006, 0.005)
    parts.append((jv, jf))

    # Skull at trigger area
    skull_y = stock_len * 0.15
    skv, skf = _make_sphere(0, skull_y, 0.015, 0.018, rings=4, sectors=6)
    parts.append((skv, skf))
    # Hollow eye sockets
    for side in [-1, 1]:
        ev, ef = _make_cone(side * 0.008, skull_y + 0.005, 0.028, 0.005, 0.008, segments=4)
        parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_Widowmaker", verts, faces,
        legendary_name="widowmaker", weapon_type="crossbow",
        feature="bone_frame",
        grip_point=(0.0, stock_len * 0.2, 0.0),
        trail_top=(0.0, prod_y + 0.03, 0.0),
        trail_bottom=(0.0, 0.0, 0.0),
    )


def _generate_soulcatcher() -> MeshSpec:
    """Soulcatcher -- shield with a living eye in the center.

    Round shield with an organic iris/pupil dome in the center,
    surrounded by veiny tendrils radiating outward. Unlike any standard shield.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    shield_r = 0.30
    thick = 0.025

    # Main shield disc (slightly convex)
    disc_segs = 16
    disc_rings = 4
    for ring in range(disc_rings + 1):
        t = ring / disc_rings
        r = shield_r * t
        z_bulge = thick * 0.3 * (1.0 - t * t)  # convex center
        ring_pts = 1 if ring == 0 else disc_segs
        for i in range(ring_pts):
            if ring == 0:
                parts_front_center = [(0.0, 0.0, z_bulge)]
            else:
                a = 2.0 * math.pi * i / disc_segs
                parts_front_center = []
                # Only add to main vertex list below
    # Build the shield as a simpler construction
    # Front face -- hemisphere-like
    fv: list[tuple[float, float, float]] = []
    ff: list[tuple[int, ...]] = []
    # Center point
    fv.append((0.0, 0.0, thick * 0.3))
    # Concentric rings
    for ring in range(1, disc_rings + 1):
        t = ring / disc_rings
        r = shield_r * t
        z = thick * 0.3 * (1.0 - t * t)
        for i in range(disc_segs):
            a = 2.0 * math.pi * i / disc_segs
            fv.append((math.cos(a) * r, math.sin(a) * r, z))
    # Triangles from center to first ring
    for i in range(disc_segs):
        i2 = (i + 1) % disc_segs
        ff.append((0, 1 + i, 1 + i2))
    # Quads between rings
    for ring in range(disc_rings - 1):
        r0_start = 1 + ring * disc_segs
        r1_start = 1 + (ring + 1) * disc_segs
        for i in range(disc_segs):
            i2 = (i + 1) % disc_segs
            ff.append((r0_start + i, r1_start + i, r1_start + i2, r0_start + i2))
    parts.append((fv, ff))

    # Back face (flat)
    bv: list[tuple[float, float, float]] = []
    bf: list[tuple[int, ...]] = []
    bv.append((0.0, 0.0, -thick))
    for i in range(disc_segs):
        a = 2.0 * math.pi * i / disc_segs
        bv.append((math.cos(a) * shield_r, math.sin(a) * shield_r, -thick))
    for i in range(disc_segs):
        i2 = (i + 1) % disc_segs
        bf.append((0, 1 + i2, 1 + i))  # reversed winding
    parts.append((bv, bf))

    # Rim
    rv, rf = _make_torus_ring(0, 0, 0, shield_r, thick * 0.5, disc_segs, 4)
    # Rotate torus to lie in XY plane (swap Y and Z)
    rv = [(v[0], v[2], v[1]) for v in rv]
    parts.append((rv, rf))

    # Central eye -- iris dome
    eye_r = shield_r * 0.2
    ev, ef = _make_sphere(0, 0, thick * 0.4, eye_r, rings=6, sectors=8)
    parts.append((ev, ef))

    # Pupil (smaller dark sphere protruding)
    pupil_r = eye_r * 0.4
    puv, puf = _make_sphere(0, 0, thick * 0.4 + eye_r * 0.6, pupil_r, rings=4, sectors=6)
    parts.append((puv, puf))

    # Veiny tendrils radiating from eye (8 directions)
    for i in range(8):
        angle = i * math.pi / 4
        tv: list[tuple[float, float, float]] = []
        tf: list[tuple[int, ...]] = []
        tendril_segs = 6
        for s in range(tendril_segs + 1):
            t = s / tendril_segs
            tr = eye_r + t * (shield_r * 0.6)
            tx = math.cos(angle) * tr
            ty = math.sin(angle) * tr
            tz = thick * 0.3 * (1.0 - t) + 0.005
            w = 0.005 * (1.0 - t * 0.5)
            # Perpendicular direction for width
            px = -math.sin(angle) * w
            py = math.cos(angle) * w
            tv.extend([(tx - px, ty - py, tz), (tx + px, ty + py, tz)])
        for s in range(tendril_segs):
            b = s * 2
            tf.append((b, b + 1, b + 3, b + 2))
        parts.append((tv, tf))

    # Handle on back
    hv, hf = _make_box(0, 0, -thick - 0.015, 0.03, 0.06, 0.008)
    parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_Soulcatcher", verts, faces,
        legendary_name="soulcatcher", weapon_type="shield",
        feature="eye_center",
        grip_point=(0.0, 0.0, -thick - 0.015),
        trail_top=(0.0, shield_r, 0.0),
        trail_bottom=(0.0, -shield_r, 0.0),
    )


def _generate_bloodthorn() -> MeshSpec:
    """Bloodthorn -- living vine whip with razor thorns.

    Organic, sinuous whip body with barbed thorns at intervals,
    ending in a bulbous pod. Completely different from standard whips.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Handle (wrapped in vine)
    handle_len, handle_r = 0.2, 0.014
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.3, handle_r, handle_len, 6, rings=3)
    parts.append((hv, hf))

    # Root-ball pommel
    pv, pf = _make_sphere(0, -0.02, 0, 0.022, rings=5, sectors=6)
    parts.append((pv, pf))

    # Vine whip body -- sinuous curve
    whip_len = 1.2
    whip_segs = 24
    vine_r = 0.006
    wv: list[tuple[float, float, float]] = []
    wf: list[tuple[int, ...]] = []
    circ_segs = 4
    for i in range(whip_segs + 1):
        t = i / whip_segs
        y = handle_len + t * whip_len
        # Sinuous curve in XZ
        wx = math.sin(t * math.pi * 3) * 0.03 * t
        wz = math.cos(t * math.pi * 2) * 0.02 * t
        r = vine_r * (1.0 - t * 0.5)
        for j in range(circ_segs):
            a = 2.0 * math.pi * j / circ_segs
            wv.append((wx + math.cos(a) * r, y, wz + math.sin(a) * r))
    for i in range(whip_segs):
        for j in range(circ_segs):
            j2 = (j + 1) % circ_segs
            r0 = i * circ_segs
            r1 = (i + 1) * circ_segs
            wf.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    parts.append((wv, wf))

    # Thorns at intervals along the vine
    for ti in range(8):
        t = (ti + 1) / 9
        y = handle_len + t * whip_len
        wx = math.sin(t * math.pi * 3) * 0.03 * t
        wz = math.cos(t * math.pi * 2) * 0.02 * t
        # Thorn pointing outward
        thorn_angle = ti * math.pi * 0.7
        thorn_dir_x = math.cos(thorn_angle) * 0.02
        thorn_dir_z = math.sin(thorn_angle) * 0.02
        tv, tf = _make_cone(
            wx + thorn_dir_x * 0.5, y, wz + thorn_dir_z * 0.5,
            0.004, 0.02, segments=4,
        )
        # Rotate cone to point outward (approximate by offsetting tip)
        # The cone already points upward, but thorns in different directions
        # add visual variety
        parts.append((tv, tf))

    # Bulbous pod at tip
    tip_y = handle_len + whip_len
    tip_x = math.sin(math.pi * 3) * 0.03
    tip_z = math.cos(math.pi * 2) * 0.02
    pod_v, pod_f = _make_sphere(tip_x, tip_y, tip_z, 0.015, rings=5, sectors=6)
    parts.append((pod_v, pod_f))

    # Pod spikes
    for i in range(5):
        sa = i * math.pi * 2 / 5
        spx = tip_x + math.cos(sa) * 0.015
        spz = tip_z + math.sin(sa) * 0.015
        spv, spf = _make_cone(spx, tip_y, spz, 0.003, 0.012, segments=3)
        parts.append((spv, spf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_Bloodthorn", verts, faces,
        legendary_name="bloodthorn", weapon_type="whip",
        feature="vine_thorns",
        grip_point=(0.0, handle_len * 0.4, 0.0),
        trail_top=(tip_x, tip_y + 0.012, tip_z),
        trail_bottom=(0.0, handle_len, 0.0),
    )


def _generate_stormcaller() -> MeshSpec:
    """Stormcaller -- halberd with jagged lightning-bolt blade.

    The axe blade is shaped like a zigzag lightning bolt rather than
    a smooth curve, with crackling spikes. The pole has conductive rings.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Pole
    pole_len, pole_r = 1.8, 0.013
    pv, pf = _make_tapered_cylinder(0, 0, 0, pole_r, pole_r * 0.9, pole_len, segs, rings=6)
    parts.append((pv, pf))

    # Conductive rings along pole
    for ri in range(6):
        ring_y = 0.15 + ri * pole_len * 0.12
        rv, rf = _make_torus_ring(0, ring_y, 0, pole_r * 1.4, pole_r * 0.15, 6, 3)
        parts.append((rv, rf))

    # Bottom spike
    bsv, bsf = _make_cone(0, -0.01, 0, pole_r * 1.3, -0.04, segments=4)
    parts.append((bsv, bsf))

    head_y = pole_len * 0.85

    # Lightning-bolt blade -- zigzag profile
    bolt_thick = 0.006
    # Define lightning zigzag points (going upward with side protrusions)
    zigzag = [
        (0.0, head_y - 0.05),
        (0.08, head_y),
        (0.03, head_y + 0.04),
        (0.12, head_y + 0.08),
        (0.05, head_y + 0.12),
        (0.10, head_y + 0.18),
        (0.02, head_y + 0.22),
        (0.0, head_y + 0.25),
    ]

    # Build blade from zigzag profile as extruded polygon
    blade_verts: list[tuple[float, float, float]] = []
    blade_faces: list[tuple[int, ...]] = []
    n_pts = len(zigzag)
    # Front and back faces
    for x, y in zigzag:
        blade_verts.append((x, y, bolt_thick))
    for x, y in zigzag:
        blade_verts.append((x, y, -bolt_thick))

    # Front face (fan from first point)
    for i in range(1, n_pts - 1):
        blade_faces.append((0, i, i + 1))
    # Back face (reversed)
    for i in range(1, n_pts - 1):
        blade_faces.append((n_pts, n_pts + i + 1, n_pts + i))
    # Side edges connecting front to back
    for i in range(n_pts):
        i2 = (i + 1) % n_pts
        blade_faces.append((i, n_pts + i, n_pts + i2, i2))

    parts.append((blade_verts, blade_faces))

    # Mirror blade on opposite side (smaller, for the hook)
    hook_zigzag = [
        (0.0, head_y - 0.03),
        (-0.04, head_y + 0.01),
        (-0.02, head_y + 0.04),
        (-0.05, head_y + 0.06),
        (0.0, head_y + 0.08),
    ]
    hook_verts: list[tuple[float, float, float]] = []
    hook_faces: list[tuple[int, ...]] = []
    n_hook = len(hook_zigzag)
    for x, y in hook_zigzag:
        hook_verts.append((x, y, bolt_thick * 0.8))
    for x, y in hook_zigzag:
        hook_verts.append((x, y, -bolt_thick * 0.8))
    for i in range(1, n_hook - 1):
        hook_faces.append((0, i, i + 1))
    for i in range(1, n_hook - 1):
        hook_faces.append((n_hook, n_hook + i + 1, n_hook + i))
    for i in range(n_hook):
        i2 = (i + 1) % n_hook
        hook_faces.append((i, n_hook + i, n_hook + i2, i2))
    parts.append((hook_verts, hook_faces))

    # Top spike (lightning rod)
    tsv, tsf = _make_cone(0, head_y + 0.25, 0, pole_r * 1.5, 0.12, segments=5)
    parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    trail_top_y = head_y + 0.37
    return _make_result(
        "Legendary_Stormcaller", verts, faces,
        legendary_name="stormcaller", weapon_type="halberd",
        feature="lightning_blade",
        grip_point=(0.0, pole_len * 0.3, 0.0),
        trail_top=(0.0, trail_top_y, 0.0),
        trail_bottom=(0.12, head_y, 0.0),
    )


def _generate_bonecrown() -> MeshSpec:
    """Bonecrown -- crown of fused skulls with horn spires.

    A helmet made from multiple fused skulls arranged in a ring,
    each with horns rising upward. Grotesque, organic silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    head_r = 0.12  # fits a head
    crown_y = 0.0

    # Base band (circlet)
    band_v, band_f = _make_torus_ring(0, crown_y, 0, head_r, 0.008, 12, 4)
    parts.append((band_v, band_f))

    # Upper dome (partial sphere, open at top for horns)
    dome_rings = 4
    dome_sectors = 10
    dv: list[tuple[float, float, float]] = []
    df: list[tuple[int, ...]] = []
    for ring in range(dome_rings + 1):
        phi = math.pi * 0.5 * ring / dome_rings  # 0 to 90 degrees (hemisphere)
        y = crown_y + head_r * 0.8 * math.sin(phi)
        rr = head_r * math.cos(phi)
        for j in range(dome_sectors):
            theta = 2.0 * math.pi * j / dome_sectors
            dv.append((math.cos(theta) * rr, y, math.sin(theta) * rr))
    for ring in range(dome_rings):
        for j in range(dome_sectors):
            j2 = (j + 1) % dome_sectors
            r0 = ring * dome_sectors
            r1 = (ring + 1) * dome_sectors
            df.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    parts.append((dv, df))

    # Skulls around the band (6 skulls)
    num_skulls = 6
    for si in range(num_skulls):
        skull_angle = si * math.pi * 2 / num_skulls
        sx = math.cos(skull_angle) * (head_r + 0.01)
        sz = math.sin(skull_angle) * (head_r + 0.01)
        # Skull body (elongated sphere)
        skull_v, skull_f = _make_sphere(sx, crown_y + 0.01, sz, 0.025, rings=4, sectors=5)
        parts.append((skull_v, skull_f))
        # Jaw
        jaw_v, jaw_f = _make_box(sx, crown_y - 0.015, sz, 0.015, 0.008, 0.012)
        parts.append((jaw_v, jaw_f))
        # Eye sockets (small cones inward)
        for eye_side in [-1, 1]:
            eye_offset = eye_side * 0.008
            # Perpendicular to radial direction
            perp_x = -math.sin(skull_angle) * eye_offset
            perp_z = math.cos(skull_angle) * eye_offset
            cev, cef = _make_cone(
                sx + perp_x, crown_y + 0.018, sz + perp_z,
                0.004, -0.008, segments=4,
            )
            parts.append((cev, cef))

    # Horn spires (6 horns rising from between skulls, plus 2 large central)
    for hi in range(num_skulls):
        horn_angle = (hi + 0.5) * math.pi * 2 / num_skulls
        hx = math.cos(horn_angle) * (head_r * 0.8)
        hz = math.sin(horn_angle) * (head_r * 0.8)
        # Curved horn -- tapered cylinder angled outward
        horn_h = 0.08 + (hi % 2) * 0.04  # Alternating heights
        horn_r = 0.008
        horn_v, horn_f = _make_tapered_cylinder(
            hx, crown_y + head_r * 0.5, hz,
            horn_r, horn_r * 0.2, horn_h, 5, rings=3,
        )
        parts.append((horn_v, horn_f))

    # Two large central horns
    for side in [-1, 1]:
        lhx = side * head_r * 0.3
        lhv, lhf = _make_tapered_cylinder(
            lhx, crown_y + head_r * 0.6, 0,
            0.012, 0.003, 0.15, 6, rings=4,
        )
        parts.append((lhv, lhf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_Bonecrown", verts, faces,
        legendary_name="bonecrown", weapon_type="helmet",
        feature="skull_horns",
        grip_point=(0.0, crown_y, 0.0),
        trail_top=(0.0, crown_y + head_r * 0.6 + 0.15, 0.0),
        trail_bottom=(0.0, crown_y - 0.02, 0.0),
    )


def _generate_abyssal_claw() -> MeshSpec:
    """Abyssal Claw -- gauntlet with void-energy finger extensions.

    A heavy gauntlet with elongated, curved claw blades extending
    from each finger, wreathed in void-crystal growths. Much more
    aggressive silhouette than standard claws.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Gauntlet body (box-ish hand shape)
    hand_w, hand_h, hand_d = 0.05, 0.025, 0.04
    gv, gf = _make_box(0, 0, 0, hand_w, hand_h, hand_d)
    parts.append((gv, gf))

    # Wrist guard (tapered cylinder)
    wv, wf = _make_tapered_cylinder(0, -hand_h, 0, 0.04, 0.035, 0.08, 6, rings=2)
    parts.append((wv, wf))

    # Wrist spikes
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        sx = math.cos(a) * 0.04
        sz = math.sin(a) * 0.04
        spv, spf = _make_cone(sx, -hand_h - 0.02, sz, 0.006, 0.025, segments=4)
        parts.append((spv, spf))

    # Five elongated claw fingers
    finger_positions = [
        (-0.035, hand_h, -0.02, 0.18),   # pinky (shorter)
        (-0.018, hand_h, -0.025, 0.22),  # ring
        (0.0, hand_h, -0.028, 0.25),     # middle (longest)
        (0.018, hand_h, -0.025, 0.22),   # index
        (0.038, hand_h, 0.01, 0.15),     # thumb (angled)
    ]

    for fx, fy, fz, flen in finger_positions:
        claw_segs = 10
        cv: list[tuple[float, float, float]] = []
        cf: list[tuple[int, ...]] = []
        for i in range(claw_segs + 1):
            t = i / claw_segs
            # Claws curve forward and slightly outward
            cy = fy + t * flen * 0.7
            cz = fz - t * flen * 0.8  # curves forward
            cx = fx + t * fx * 0.3  # splay outward
            r = 0.006 * (1.0 - t * 0.6)
            cv.extend([(cx - r, cy, cz + r), (cx + r, cy, cz + r),
                       (cx + r, cy, cz - r), (cx - r, cy, cz - r)])
        for i in range(claw_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                cf.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        # Sharp tip
        last_t = 1.0
        tip_y = fy + last_t * flen * 0.7
        tip_z = fz - last_t * flen * 0.8
        tip_x = fx + last_t * fx * 0.3
        cv.append((tip_x, tip_y + 0.01, tip_z - 0.02))
        tb = claw_segs * 4
        ti = len(cv) - 1
        for j in range(4):
            cf.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((cv, cf))

    # Void crystal growths on knuckles
    for i in range(3):
        crx = -0.015 + i * 0.015
        crv, crf = _make_cone(crx, hand_h + 0.005, -0.01, 0.006, 0.02, segments=4)
        parts.append((crv, crf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Legendary_AbyssalClaw", verts, faces,
        legendary_name="abyssal_claw", weapon_type="claw",
        feature="void_fingers",
        grip_point=(0.0, 0.0, 0.0),
        trail_top=(0.0, hand_h + 0.25, -0.2),
        trail_bottom=(0.0, hand_h, 0.0),
    )


# ---------------------------------------------------------------------------
# Generator registry
# ---------------------------------------------------------------------------

LEGENDARY_GENERATORS: dict[str, Any] = {
    "voidreaver": _generate_voidreaver,
    "chainbreaker": _generate_chainbreaker,
    "serpents_fang": _generate_serpents_fang,
    "crystalheart_staff": _generate_crystalheart_staff,
    "widowmaker": _generate_widowmaker,
    "soulcatcher": _generate_soulcatcher,
    "bloodthorn": _generate_bloodthorn,
    "stormcaller": _generate_stormcaller,
    "bonecrown": _generate_bonecrown,
    "abyssal_claw": _generate_abyssal_claw,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_legendary_weapon_mesh(weapon_name: str) -> MeshSpec:
    """Generate a unique legendary weapon mesh by name.

    Args:
        weapon_name: One of the keys in LEGENDARY_WEAPONS
                     (e.g. 'voidreaver', 'chainbreaker', ...).

    Returns:
        MeshSpec dict with vertices, faces, uvs, and metadata
        including legendary_name, weapon_type, and feature.

    Raises:
        ValueError: If weapon_name is unknown.
    """
    name = weapon_name.lower().strip()
    if name not in LEGENDARY_GENERATORS:
        raise ValueError(
            f"Unknown legendary weapon: {name!r}. "
            f"Valid: {sorted(LEGENDARY_GENERATORS.keys())}"
        )
    return LEGENDARY_GENERATORS[name]()
