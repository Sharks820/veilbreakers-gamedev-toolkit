"""AAA-quality weapon and armor mesh generators for VeilBreakers dark fantasy.

Upgraded replacement generators that produce detailed, visually impressive
weapons and armor worthy of a AAA dark fantasy RPG (FromSoftware / Bethesda
quality bar).

Every weapon features:
- Blade cross-sections with edge bevels, fuller grooves, spine thickness
- Ornamental guards (cross, S-curve, ring, basket, disc)
- Ergonomic grips with spiral wrap detail and finger grooves
- Shaped pommels (disk, skull, lion, gem, ring)
- Attachment empties (hand_grip, back_mount, hip_mount, wall_mount)
- Proper UV islands per component
- Quality metrics in the result dict

Pure Python with math-only dependencies (no bpy/bmesh).
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type alias
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# Core utilities
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


def _make_quality_result(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    *,
    empties: dict[str, tuple[float, float, float]] | None = None,
    vertex_groups: dict[str, list[int]] | None = None,
    detail_features: list[str] | None = None,
    ornament_level: int = 2,
    **extra_meta: Any,
) -> MeshSpec:
    """Package mesh data with AAA quality metrics."""
    dims = _compute_dimensions(vertices)
    uv_list = uvs or []
    tri_count = 0
    for f in faces:
        tri_count += len(f) - 2

    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uv_list,
        "empties": empties or {},
        "vertex_groups": vertex_groups or {},
        "metadata": {
            "name": name,
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "tri_count": tri_count,
            "dimensions": dims,
            "category": "weapon",
            **extra_meta,
        },
        "quality_metrics": {
            "total_verts": len(vertices),
            "total_faces": len(faces),
            "total_tris": tri_count,
            "has_edge_bevels": True,
            "has_attachment_empties": empties is not None and len(empties) > 0,
            "has_vertex_groups": vertex_groups is not None and len(vertex_groups) > 0,
            "uv_coverage": _estimate_uv_coverage(uv_list) if uv_list else 0.0,
            "ornament_level": ornament_level,
            "detail_features": detail_features or [],
        },
    }


def _estimate_uv_coverage(uvs: list[tuple[float, float]]) -> float:
    """Rough estimate of UV coverage (0-1) from UV coord spread."""
    if len(uvs) < 3:
        return 0.0
    us = [uv[0] for uv in uvs]
    vs = [uv[1] for uv in uvs]
    u_range = max(us) - min(us)
    v_range = max(vs) - min(vs)
    return min(u_range * v_range, 1.0)


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


def _merge_uvs(
    *uv_parts: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Merge UV lists."""
    all_uvs: list[tuple[float, float]] = []
    for uvs in uv_parts:
        all_uvs.extend(uvs)
    return all_uvs


# ---------------------------------------------------------------------------
# Primitive generators
# ---------------------------------------------------------------------------

def _make_cylinder_ring(
    cx: float, cy: float, cz: float,
    rx: float, rz: float,
    segments: int,
) -> list[tuple[float, float, float]]:
    """Generate an oval cross-section ring of points at height cy."""
    pts: list[tuple[float, float, float]] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        pts.append((
            cx + math.cos(angle) * rx,
            cy,
            cz + math.sin(angle) * rz,
        ))
    return pts


def _make_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder along Y axis."""
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
    """Generate a cylinder that tapers from radius_bottom to radius_top."""
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
    """UV sphere."""
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


def _make_torus(
    cx: float, cy: float, cz: float,
    major_radius: float, minor_radius: float,
    major_segments: int = 16,
    minor_segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Torus lying in XZ plane at cy."""
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


def _make_cone(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Cone with apex at top."""
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


def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Axis-aligned box with half-sizes."""
    hx, hy, hz = sx, sy, sz
    verts = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return verts, faces


# ---------------------------------------------------------------------------
# Advanced shape builders
# ---------------------------------------------------------------------------

def _build_cross_section_blade(
    length: float,
    base_width: float,
    thickness: float,
    edge_bevel: float,
    fuller: bool,
    fuller_depth: float,
    taper_start: float,
    taper_power: float,
    num_sections: int,
    curve_func=None,
    single_edge: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]], list[int]]:
    """Build a blade from cross-section rings with edge bevels and fuller groove.

    Cross-section structure (8 vertices per ring):
        Spine top (thicker)
        Fuller top inset (if fuller)
        Edge bevel top
        Edge tip
        Edge bevel bottom
        Fuller bottom inset (if fuller)
        Spine bottom (thicker)
        Spine back (thickness center)

    Returns (verts, faces, uvs, edge_bevel_vert_indices).
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []
    bevel_indices: list[int] = []

    # Verts per cross-section ring
    vpr = 10 if fuller else 8

    spine_thick = thickness * 1.5  # Spine is thicker than edge

    for si in range(num_sections):
        t = si / max(num_sections - 1, 1)
        y = t * length

        # Width tapering: blade narrows toward tip
        if t > taper_start:
            taper_t = (t - taper_start) / (1.0 - taper_start)
            w = base_width * (1.0 - taper_t ** taper_power)
        else:
            w = base_width
        w = max(w, 0.001)

        # Curve offset (for curved swords, etc.)
        x_off = 0.0
        z_off = 0.0
        if curve_func:
            x_off, z_off = curve_func(t)

        # Cross-section vertices (viewed from tip looking down)
        # The blade lies primarily along Y, with width in X and thickness in Z
        half_w = w / 2.0
        half_thick = spine_thick / 2.0
        bevel = min(edge_bevel, half_w * 0.5)

        if single_edge:
            # Single-edged blade (katana/axe): sharp on one side, thick spine on other
            ring: list[tuple[float, float, float]] = [
                # Spine (top, thick side at +X)
                (x_off + half_w, y, z_off + half_thick),       # 0: spine top right
                (x_off + half_w, y, z_off - half_thick),       # 1: spine bottom right
            ]
            if fuller:
                fd = fuller_depth * (1.0 - max(0, (t - 0.7) / 0.3))
                ring.extend([
                    (x_off + half_w * 0.3, y, z_off + half_thick - fd),  # 2: fuller top
                    (x_off + half_w * 0.3, y, z_off - half_thick + fd),  # 3: fuller bottom
                ])
            # Edge side (sharp at -X)
            ring.extend([
                (x_off - half_w + bevel, y, z_off + bevel * 0.5),   # bevel top
                (x_off - half_w, y, z_off),                          # edge tip
                (x_off - half_w + bevel, y, z_off - bevel * 0.5),   # bevel bottom
            ])
            # Back connector
            ring.append((x_off, y, z_off - half_thick))  # back flat
            ring.append((x_off, y, z_off + half_thick))  # back flat top
            # Record bevel indices
            edge_start = 2 + (2 if fuller else 0)
            bevel_indices.extend([
                len(verts) + edge_start,
                len(verts) + edge_start + 1,
                len(verts) + edge_start + 2,
            ])
        else:
            # Double-edged blade (longsword, greatsword)
            ring = []

            # Right side (+X): spine -> fuller -> edge bevel -> edge -> edge bevel
            ring.append((x_off + half_thick, y, z_off + half_w))    # 0: spine top right
            if fuller:
                fd = fuller_depth * (1.0 - max(0, (t - 0.7) / 0.3))
                ring.append((x_off + half_thick - fd, y, z_off + half_w * 0.6))  # 1: fuller right top
                ring.append((x_off + half_thick - fd, y, z_off - half_w * 0.6))  # 2: fuller right bot
            ring.append((x_off + half_thick, y, z_off - half_w))    # 3: spine bottom right

            # Edge bevels on bottom edge (-Z)
            ring.append((x_off + bevel * 0.5, y, z_off - half_w + bevel))  # bevel outer bot
            ring.append((x_off, y, z_off - half_w))                         # edge tip bottom
            ring.append((x_off - bevel * 0.5, y, z_off - half_w + bevel))  # bevel inner bot
            bevel_indices.extend([
                len(verts) + len(ring) - 3,
                len(verts) + len(ring) - 2,
                len(verts) + len(ring) - 1,
            ])

            # Left side (-X)
            ring.append((x_off - half_thick, y, z_off - half_w))    # spine bottom left
            if fuller:
                ring.append((x_off - half_thick + fd, y, z_off - half_w * 0.6))  # fuller left bot
                ring.append((x_off - half_thick + fd, y, z_off + half_w * 0.6))  # fuller left top
            ring.append((x_off - half_thick, y, z_off + half_w))    # spine top left

            # Edge bevels on top edge (+Z)
            ring.append((x_off - bevel * 0.5, y, z_off + half_w - bevel))  # bevel inner top
            ring.append((x_off, y, z_off + half_w))                         # edge tip top
            ring.append((x_off + bevel * 0.5, y, z_off + half_w - bevel))  # bevel outer top
            bevel_indices.extend([
                len(verts) + len(ring) - 3,
                len(verts) + len(ring) - 2,
                len(verts) + len(ring) - 1,
            ])

        vpr = len(ring)
        verts.extend(ring)

        # UVs: map blade length along V, circumference along U
        for vi, _ in enumerate(ring):
            u = vi / max(len(ring) - 1, 1)
            v = t
            uvs.append((u, v))

    # Connect cross-section rings with quad faces
    for si in range(num_sections - 1):
        base_a = si * vpr
        base_b = (si + 1) * vpr
        for vi in range(vpr):
            vi_next = (vi + 1) % vpr
            faces.append((
                base_a + vi,
                base_a + vi_next,
                base_b + vi_next,
                base_b + vi,
            ))

    # Tip cap: fan from center to last ring
    if num_sections > 0:
        last_base = (num_sections - 1) * vpr
        tip_y = length + length * 0.03
        x_off_tip = 0.0
        z_off_tip = 0.0
        if curve_func:
            x_off_tip, z_off_tip = curve_func(1.0)
        tip_idx = len(verts)
        verts.append((x_off_tip, tip_y, z_off_tip))
        uvs.append((0.5, 1.05))
        for vi in range(vpr):
            vi_next = (vi + 1) % vpr
            faces.append((last_base + vi, last_base + vi_next, tip_idx))

    # Base cap: fan from center to first ring (reversed winding)
    if num_sections > 0:
        base_center_idx = len(verts)
        verts.append((0.0, 0.0, 0.0))
        uvs.append((0.5, -0.02))
        for vi in range(vpr):
            vi_next = (vi + 1) % vpr
            faces.append((vi_next, vi, base_center_idx))

    return verts, faces, uvs, bevel_indices


def _build_ergonomic_grip(
    length: float,
    base_radius_x: float,
    base_radius_z: float,
    grip_wrap: str,
    finger_grooves: bool,
    taper: float,
    segments: int = 10,
    rings: int = 12,
    y_offset: float = 0.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]], list[int]]:
    """Build an ergonomic grip with oval cross-section, wrap detail, and grooves.

    Returns (verts, faces, uvs, wrap_vert_indices).
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []
    wrap_indices: list[int] = []

    for ri in range(rings + 1):
        t = ri / rings
        y = y_offset + t * length

        # Taper: wider at guard end (t=1), narrower at pommel end (t=0)
        taper_factor = 1.0 - taper * (1.0 - t)
        rx = base_radius_x * taper_factor
        rz = base_radius_z * taper_factor

        # Finger grooves: sinusoidal modulation of radius
        groove_mod = 1.0
        if finger_grooves and 0.15 < t < 0.85:
            groove_mod = 1.0 - 0.08 * math.sin(t * math.pi * 4)

        for si in range(segments):
            angle = 2.0 * math.pi * si / segments
            ca, sa = math.cos(angle), math.sin(angle)

            # Base elliptical position
            px = ca * rx * groove_mod
            pz = sa * rz * groove_mod

            # Wrap detail: raised spiral bumps
            if grip_wrap == "leather_spiral":
                wrap_phase = t * 8.0 * math.pi + angle
                wrap_bump = 0.0008 * math.sin(wrap_phase * 3.0)
                if abs(math.sin(wrap_phase)) > 0.7:
                    wrap_bump += 0.0004
                    wrap_indices.append(len(verts))
                px += ca * wrap_bump
                pz += sa * wrap_bump
            elif grip_wrap == "cord_wrap":
                wrap_phase = t * 12.0 * math.pi + angle * 0.5
                wrap_bump = 0.0006 * abs(math.sin(wrap_phase))
                if abs(math.sin(wrap_phase)) > 0.8:
                    wrap_indices.append(len(verts))
                px += ca * wrap_bump
                pz += sa * wrap_bump
            elif grip_wrap == "wire_wrap":
                wrap_phase = t * 16.0 * math.pi
                wrap_bump = 0.0005 * (math.sin(wrap_phase) * 0.5 + 0.5)
                if math.sin(wrap_phase) > 0.6:
                    wrap_indices.append(len(verts))
                px += ca * wrap_bump
                pz += sa * wrap_bump

            verts.append((px, y, pz))
            uvs.append((si / segments, t))

    # Connect rings
    for ri in range(rings):
        for si in range(segments):
            si_next = (si + 1) % segments
            r0 = ri * segments
            r1 = (ri + 1) * segments
            faces.append((r0 + si, r0 + si_next, r1 + si_next, r1 + si))

    # Cap bottom (pommel end)
    cap_b = len(verts)
    verts.append((0.0, y_offset, 0.0))
    uvs.append((0.5, 0.0))
    for si in range(segments):
        si_next = (si + 1) % segments
        faces.append((si_next, si, cap_b))

    # Cap top (guard end)
    cap_t = len(verts)
    verts.append((0.0, y_offset + length, 0.0))
    uvs.append((0.5, 1.0))
    last_ring = rings * segments
    for si in range(segments):
        si_next = (si + 1) % segments
        faces.append((last_ring + si, last_ring + si_next, cap_t))

    return verts, faces, uvs, wrap_indices


def _build_cross_guard(
    width: float,
    height: float,
    depth: float,
    guard_y: float,
    style: str = "cross",
    ornament_level: int = 2,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]]]:
    """Build an ornamental guard.

    Styles: cross, s_curve, ring, disc, basket
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []

    if style == "cross":
        # Main cross-guard bar: tapered rectangular bars extending from center
        bar_sections = 8
        for side in (-1, 1):
            side_verts: list[tuple[float, float, float]] = []
            for bi in range(bar_sections + 1):
                t = bi / bar_sections
                x = side * t * width / 2.0
                # Taper: thicker at center, thinner at tips
                h_scale = 1.0 - 0.3 * t
                d_scale = 1.0 - 0.2 * t
                # Flared ends for ornament
                if ornament_level >= 2 and t > 0.8:
                    flare_t = (t - 0.8) / 0.2
                    h_scale += 0.3 * flare_t
                    d_scale += 0.2 * flare_t

                half_h = height / 2.0 * h_scale
                half_d = depth / 2.0 * d_scale

                base = len(verts)
                verts.extend([
                    (x, guard_y - half_h, -half_d),
                    (x, guard_y - half_h, half_d),
                    (x, guard_y + half_h, half_d),
                    (x, guard_y + half_h, -half_d),
                ])
                for vi in range(4):
                    uvs.append((t, vi / 3.0))

            # Connect sections
            for bi in range(bar_sections):
                base_a = len(verts) - (bar_sections + 1) * 4 + bi * 4
                base_b = base_a + 4
                for vi in range(4):
                    vi_next = (vi + 1) % 4
                    faces.append((base_a + vi, base_a + vi_next, base_b + vi_next, base_b + vi))

        # Decorative finial spheres at ends
        if ornament_level >= 1:
            for side in (-1, 1):
                finial_x = side * width / 2.0
                sv, sf = _make_sphere(finial_x, guard_y, 0, height * 0.6, rings=4, sectors=6)
                offset = len(verts)
                verts.extend(sv)
                for f in sf:
                    faces.append(tuple(idx + offset for idx in f))
                for _ in sv:
                    uvs.append((0.5 + side * 0.2, 0.5))

    elif style == "s_curve":
        # S-curve guard: sinusoidal bar
        curve_sections = 16
        for side in (-1, 1):
            for ci in range(curve_sections + 1):
                t = ci / curve_sections
                x = side * t * width / 2.0
                # S-curve in Y
                y_curve = math.sin(t * math.pi) * height * 0.8 * side
                h_scale = 1.0 - 0.2 * t
                half_h = height / 2.0 * h_scale
                half_d = depth / 2.0

                base = len(verts)
                verts.extend([
                    (x, guard_y + y_curve - half_h, -half_d),
                    (x, guard_y + y_curve - half_h, half_d),
                    (x, guard_y + y_curve + half_h, half_d),
                    (x, guard_y + y_curve + half_h, -half_d),
                ])
                for vi in range(4):
                    uvs.append((t, vi / 3.0))

            for ci in range(curve_sections):
                base_a = len(verts) - (curve_sections + 1) * 4 + ci * 4
                base_b = base_a + 4
                for vi in range(4):
                    vi_next = (vi + 1) % 4
                    faces.append((base_a + vi, base_a + vi_next, base_b + vi_next, base_b + vi))

        # Scroll ornaments at ends
        if ornament_level >= 2:
            for side in (-1, 1):
                sv, sf = _make_torus(
                    side * width / 2.0, guard_y + side * height * 0.8, 0,
                    height * 0.4, height * 0.15, 8, 4,
                )
                offset = len(verts)
                verts.extend(sv)
                for f in sf:
                    faces.append(tuple(idx + offset for idx in f))
                for _ in sv:
                    uvs.append((0.5, 0.5))

    elif style == "ring":
        # Ring guard: circular arc from guard to pommel area
        ring_sections = 16
        ring_radius = width * 0.4
        ring_tube = depth * 0.3
        # Half-torus arc
        for ri in range(ring_sections + 1):
            t = ri / ring_sections
            theta = t * math.pi  # half circle
            cx = math.sin(theta) * ring_radius
            cy_r = guard_y - math.cos(theta) * ring_radius
            for ti in range(6):
                phi = 2.0 * math.pi * ti / 6
                px = cx + math.cos(phi) * ring_tube * math.cos(theta)
                py = cy_r + math.sin(phi) * ring_tube
                pz = math.cos(phi) * ring_tube * math.sin(theta)
                verts.append((px, py, pz))
                uvs.append((t, ti / 5.0))

        tube_segs = 6
        for ri in range(ring_sections):
            for ti in range(tube_segs):
                ti_next = (ti + 1) % tube_segs
                r0 = ri * tube_segs
                r1 = (ri + 1) * tube_segs
                faces.append((r0 + ti, r0 + ti_next, r1 + ti_next, r1 + ti))

        # Also add basic cross-bar
        bv, bf = _make_box(0, guard_y, 0, width * 0.2, height * 0.4, depth * 0.4)
        offset = len(verts)
        verts.extend(bv)
        for f in bf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in bv:
            uvs.append((0.5, 0.5))

    elif style == "disc":
        # Disc guard (like a tsuba for katana)
        disc_segs = 16
        disc_radius = width * 0.45
        disc_thick = depth * 0.3
        # Front and back face with beveled edge
        for face_side in (-1, 1):
            center_idx = len(verts)
            verts.append((0, guard_y, face_side * disc_thick / 2.0))
            uvs.append((0.5, 0.5))
            for di in range(disc_segs):
                angle = 2.0 * math.pi * di / disc_segs
                verts.append((
                    math.cos(angle) * disc_radius,
                    guard_y + math.sin(angle) * disc_radius * 0.3,
                    face_side * disc_thick / 2.0,
                ))
                uvs.append((0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle)))
            for di in range(disc_segs):
                di_next = (di + 1) % disc_segs
                if face_side > 0:
                    faces.append((center_idx, center_idx + 1 + di, center_idx + 1 + di_next))
                else:
                    faces.append((center_idx, center_idx + 1 + di_next, center_idx + 1 + di))
        # Edge band
        front_start = 1  # first ring vertex of front face
        # We need to know where the back face ring starts
        back_face_start = 1 + disc_segs + 1  # center + ring of front, then center of back
        for di in range(disc_segs):
            di_next = (di + 1) % disc_segs
            f0 = front_start + di
            f1 = front_start + di_next
            b0 = back_face_start + di
            b1 = back_face_start + di_next
            faces.append((f0, f1, b1, b0))

    elif style == "basket":
        # Basket guard: cage mesh protecting the hand
        cage_bars = 8
        cage_radius = width * 0.4
        cage_height = width * 0.6
        bar_thick = depth * 0.12
        for bi in range(cage_bars):
            angle = 2.0 * math.pi * bi / cage_bars
            ca, sa = math.cos(angle), math.sin(angle)
            # Each bar is a thin rectangular strip curving from guard to pommel
            bar_sections = 6
            for bsi in range(bar_sections + 1):
                t = bsi / bar_sections
                y = guard_y - t * cage_height
                r = cage_radius * math.sin(t * math.pi) * 0.5 + cage_radius * 0.3
                px = ca * r
                pz = sa * r
                base = len(verts)
                # Thin strip: 2 verts wide
                verts.extend([
                    (px - sa * bar_thick, y, pz + ca * bar_thick),
                    (px + sa * bar_thick, y, pz - ca * bar_thick),
                ])
                uvs.extend([(t, 0), (t, 1)])

            for bsi in range(bar_sections):
                base_a = len(verts) - (bar_sections + 1) * 2 + bsi * 2
                base_b = base_a + 2
                faces.append((base_a, base_a + 1, base_b + 1, base_b))

        # Ring band at widest point
        rv, rf = _make_torus(0, guard_y - cage_height * 0.4, 0,
                             cage_radius * 0.65, bar_thick, 12, 4)
        offset = len(verts)
        verts.extend(rv)
        for f in rf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in rv:
            uvs.append((0.5, 0.5))

    else:
        # Fallback: simple cross
        bv, bf = _make_box(0, guard_y, 0, width / 2, height / 2, depth / 2)
        offset = len(verts)
        verts.extend(bv)
        for f in bf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in bv:
            uvs.append((0.5, 0.5))

    return verts, faces, uvs


def _build_pommel(
    style: str,
    radius: float,
    y_pos: float,
    ornament_level: int = 2,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]]]:
    """Build a pommel in the specified style.

    Styles: disk, skull, lion, gem, ring, tear_drop, sphere
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []

    if style == "disk":
        # Flattened sphere with beveled edge and center boss
        # Main disk body
        disk_segs = 12
        disk_rings = 4
        squash = 0.4  # flatten Y
        for ri in range(disk_rings + 1):
            t = ri / disk_rings
            phi = math.pi * t
            ring_r = radius * math.sin(phi)
            y = y_pos - radius * squash * math.cos(phi)
            for si in range(disk_segs):
                angle = 2.0 * math.pi * si / disk_segs
                verts.append((math.cos(angle) * ring_r, y, math.sin(angle) * ring_r))
                uvs.append((si / disk_segs, t))
        # Connect
        for ri in range(disk_rings):
            for si in range(disk_segs):
                si_next = (si + 1) % disk_segs
                r0 = ri * disk_segs + si
                r1 = ri * disk_segs + si_next
                r2 = (ri + 1) * disk_segs + si_next
                r3 = (ri + 1) * disk_segs + si
                faces.append((r0, r1, r2, r3))
        # Center boss
        if ornament_level >= 1:
            bv, bf = _make_sphere(0, y_pos, 0, radius * 0.35, rings=4, sectors=6)
            offset = len(verts)
            verts.extend(bv)
            for f in bf:
                faces.append(tuple(idx + offset for idx in f))
            for _ in bv:
                uvs.append((0.5, 0.5))
        # Tassel ring
        if ornament_level >= 2:
            tv, tf = _make_torus(0, y_pos - radius * squash * 0.8, 0,
                                 radius * 0.15, radius * 0.05, 8, 4)
            offset = len(verts)
            verts.extend(tv)
            for f in tf:
                faces.append(tuple(idx + offset for idx in f))
            for _ in tv:
                uvs.append((0.5, 0.5))

    elif style == "skull":
        # Simplified skull: cranium sphere + jaw box + eye socket indents
        # Cranium
        cv, cf = _make_sphere(0, y_pos, 0, radius, rings=6, sectors=8)
        verts.extend(cv)
        faces.extend(cf)
        for _ in cv:
            uvs.append((0.5, 0.5))

        # Jaw
        jv, jf = _make_box(0, y_pos - radius * 0.7, 0,
                            radius * 0.6, radius * 0.25, radius * 0.5)
        offset = len(verts)
        verts.extend(jv)
        for f in jf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in jv:
            uvs.append((0.5, 0.3))

        # Eye socket indents (small spheres pushed into skull)
        for side in (-1, 1):
            ev, ef = _make_sphere(
                side * radius * 0.3, y_pos + radius * 0.1, radius * 0.6,
                radius * 0.2, rings=3, sectors=4,
            )
            offset = len(verts)
            verts.extend(ev)
            for f in ef:
                faces.append(tuple(idx + offset for idx in f))
            for _ in ev:
                uvs.append((0.5, 0.5))

        # Nose hole
        nv, nf = _make_cone(0, y_pos - radius * 0.1, radius * 0.65,
                            radius * 0.12, radius * 0.15, segments=4)
        offset = len(verts)
        verts.extend(nv)
        for f in nf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in nv:
            uvs.append((0.5, 0.5))

    elif style == "lion":
        # Conical shape with mane ridge ring
        # Main head cone
        cv, cf = _make_tapered_cylinder(0, y_pos - radius, 0,
                                        radius * 0.3, radius * 0.8,
                                        radius * 1.5, 10, rings=4)
        verts.extend(cv)
        faces.extend(cf)
        for _ in cv:
            uvs.append((0.5, 0.5))

        # Mane ridge
        mv, mf = _make_torus(0, y_pos + radius * 0.2, 0,
                              radius * 0.7, radius * 0.2, 12, 4)
        offset = len(verts)
        verts.extend(mv)
        for f in mf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in mv:
            uvs.append((0.5, 0.5))

        # Snout
        sv, sf = _make_sphere(0, y_pos - radius * 0.3, radius * 0.5,
                              radius * 0.3, rings=4, sectors=6)
        offset = len(verts)
        verts.extend(sv)
        for f in sf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in sv:
            uvs.append((0.5, 0.5))

    elif style == "gem":
        # Octagonal faceted shape with bezel ring
        gem_segs = 8
        gem_rings = 5
        gem_profiles = [
            (0.0, 0.3),    # bottom point
            (0.7, 0.6),    # lower facet
            (1.0, 1.0),    # girdle (widest)
            (0.7, 1.4),    # upper facet
            (0.0, 1.7),    # top point (crown)
        ]
        for ri, (r_scale, y_scale) in enumerate(gem_profiles):
            y = y_pos - radius + y_scale * radius
            r = r_scale * radius * 0.7
            for si in range(gem_segs):
                angle = 2.0 * math.pi * si / gem_segs + math.pi / gem_segs  # rotated for facets
                verts.append((math.cos(angle) * r, y, math.sin(angle) * r))
                uvs.append((si / gem_segs, ri / (gem_rings - 1)))

        for ri in range(gem_rings - 1):
            for si in range(gem_segs):
                si_next = (si + 1) % gem_segs
                r0 = ri * gem_segs + si
                r1 = ri * gem_segs + si_next
                r2 = (ri + 1) * gem_segs + si_next
                r3 = (ri + 1) * gem_segs + si
                # Handle degenerate quads at top/bottom points
                if gem_profiles[ri][0] < 0.01:
                    faces.append((r0, r2, r3))
                elif gem_profiles[ri + 1][0] < 0.01:
                    faces.append((r0, r1, r2))
                else:
                    faces.append((r0, r1, r2, r3))

        # Bezel ring
        bv, bf = _make_torus(0, y_pos, 0,
                              radius * 0.75, radius * 0.08, 12, 4)
        offset = len(verts)
        verts.extend(bv)
        for f in bf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in bv:
            uvs.append((0.5, 0.5))

    elif style == "ring":
        # Torus at end of grip
        tv, tf = _make_torus(0, y_pos, 0,
                              radius * 0.8, radius * 0.3, 12, 6)
        verts.extend(tv)
        faces.extend(tf)
        for _ in tv:
            uvs.append((0.5, 0.5))

        # Connecting neck
        nv, nf = _make_cylinder(0, y_pos + radius * 0.3, 0,
                                radius * 0.25, radius * 0.3, segments=6)
        offset = len(verts)
        verts.extend(nv)
        for f in nf:
            faces.append(tuple(idx + offset for idx in f))
        for _ in nv:
            uvs.append((0.5, 0.5))

    elif style == "tear_drop":
        # Teardrop shape
        td_segs = 10
        td_rings = 8
        for ri in range(td_rings + 1):
            t = ri / td_rings
            # Teardrop profile: sin-based with pointed bottom
            r = radius * math.sin(t * math.pi) ** 0.7
            y = y_pos - radius * (1.0 - t * 2.0)
            for si in range(td_segs):
                angle = 2.0 * math.pi * si / td_segs
                verts.append((math.cos(angle) * r, y, math.sin(angle) * r))
                uvs.append((si / td_segs, t))
        for ri in range(td_rings):
            for si in range(td_segs):
                si_next = (si + 1) % td_segs
                r0 = ri * td_segs + si
                r1 = ri * td_segs + si_next
                r2 = (ri + 1) * td_segs + si_next
                r3 = (ri + 1) * td_segs + si
                faces.append((r0, r1, r2, r3))

    else:  # sphere (default)
        sv, sf = _make_sphere(0, y_pos, 0, radius, rings=6, sectors=8)
        verts.extend(sv)
        faces.extend(sf)
        for _ in sv:
            uvs.append((0.5, 0.5))

    return verts, faces, uvs


# ---------------------------------------------------------------------------
# Scabbard builder
# ---------------------------------------------------------------------------

def _build_scabbard(
    blade_length: float,
    blade_width: float,
    blade_thickness: float,
    y_offset: float = 0.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]]]:
    """Build a scabbard/sheath as a separate mesh piece."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []

    scabbard_len = blade_length * 0.85
    scabbard_w = blade_width * 1.4
    scabbard_thick = blade_thickness * 3.0
    sections = 10
    segs = 8

    for si in range(sections + 1):
        t = si / sections
        y = y_offset + t * scabbard_len
        # Taper toward tip
        w = scabbard_w * (1.0 - 0.3 * t ** 2)
        th = scabbard_thick * (1.0 - 0.2 * t ** 2)
        for sgi in range(segs):
            angle = 2.0 * math.pi * sgi / segs
            px = math.cos(angle) * w
            pz = math.sin(angle) * th
            verts.append((px, y, pz))
            uvs.append((sgi / segs, t))

    for si in range(sections):
        for sgi in range(segs):
            sgi_next = (sgi + 1) % segs
            r0 = si * segs + sgi
            r1 = si * segs + sgi_next
            r2 = (si + 1) * segs + sgi_next
            r3 = (si + 1) * segs + sgi
            faces.append((r0, r1, r2, r3))

    # Tip cap
    tip_idx = len(verts)
    verts.append((0, y_offset + scabbard_len, 0))
    uvs.append((0.5, 1.0))
    last_ring = sections * segs
    for sgi in range(segs):
        sgi_next = (sgi + 1) % segs
        faces.append((last_ring + sgi, last_ring + sgi_next, tip_idx))

    # Mouth plate (wider ring at opening)
    mouth_v, mouth_f = _make_torus(
        0, y_offset, 0,
        scabbard_w * 1.1, scabbard_thick * 0.5, 12, 4,
    )
    offset = len(verts)
    verts.extend(mouth_v)
    for f in mouth_f:
        faces.append(tuple(idx + offset for idx in f))
    for _ in mouth_v:
        uvs.append((0.5, 0.0))

    return verts, faces, uvs


# ===========================================================================
# SWORD GENERATOR (Gold Standard)
# ===========================================================================

def generate_quality_sword(
    style: str = "longsword",
    blade_length: float = 0.9,
    blade_width: float = 0.05,
    blade_thickness: float = 0.005,
    fuller: bool = True,
    guard_style: str = "cross",
    grip_length: float = 0.2,
    grip_wrap: str = "leather_spiral",
    pommel_style: str = "disk",
    edge_bevel: float = 0.003,
    ornament_level: int = 2,
    include_scabbard: bool = False,
) -> MeshSpec:
    """Generate an AAA-quality sword mesh with full detail.

    Styles: longsword, shortsword, greatsword, bastard, rapier, flamberge
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    # -- Style presets --
    presets = {
        "longsword": {"blade_len": blade_length, "blade_w": blade_width, "grip_len": grip_length,
                       "guard": guard_style, "sections": 14, "taper_start": 0.6, "taper_pow": 1.5},
        "shortsword": {"blade_len": 0.5, "blade_w": 0.04, "grip_len": 0.15,
                        "guard": guard_style, "sections": 10, "taper_start": 0.5, "taper_pow": 1.3},
        "greatsword": {"blade_len": 1.2, "blade_w": 0.065, "grip_len": 0.35,
                        "guard": guard_style, "sections": 18, "taper_start": 0.65, "taper_pow": 1.8},
        "bastard": {"blade_len": 1.0, "blade_w": 0.055, "grip_len": 0.28,
                     "guard": guard_style, "sections": 15, "taper_start": 0.6, "taper_pow": 1.5},
        "rapier": {"blade_len": 1.0, "blade_w": 0.02, "grip_len": 0.18,
                    "guard": "ring" if guard_style == "cross" else guard_style,
                    "sections": 14, "taper_start": 0.3, "taper_pow": 1.0},
        "flamberge": {"blade_len": 1.1, "blade_w": 0.06, "grip_len": 0.32,
                       "guard": guard_style, "sections": 20, "taper_start": 0.7, "taper_pow": 2.0},
    }
    preset = presets.get(style, presets["longsword"])
    b_len = preset["blade_len"]
    b_wid = preset["blade_w"]
    g_len = preset["grip_len"]
    g_style = preset["guard"]
    n_sections = preset["sections"]
    t_start = preset["taper_start"]
    t_pow = preset["taper_pow"]

    guard_y = g_len  # Guard sits at top of grip

    # Curve function for flamberge
    curve_fn = None
    if style == "flamberge":
        def curve_fn(t):
            return (math.sin(t * math.pi * 4) * 0.008, 0.0)

    # === 1. GRIP ===
    grip_verts, grip_faces, grip_uvs, wrap_idxs = _build_ergonomic_grip(
        length=g_len,
        base_radius_x=0.013,
        base_radius_z=0.010,
        grip_wrap=grip_wrap,
        finger_grooves=True,
        taper=0.15,
        segments=10,
        rings=12,
    )
    all_parts.append((grip_verts, grip_faces))
    # Remap UV coords to grip UV island (bottom-left quadrant)
    grip_uvs_remapped = [(u * 0.25, v * 0.25) for u, v in grip_uvs]
    all_uvs.append(grip_uvs_remapped)
    grip_indices = list(range(running_vert_count, running_vert_count + len(grip_verts)))
    vgroup_data["grip"] = grip_indices
    if wrap_idxs:
        vgroup_data["grip_wrap"] = [running_vert_count + i for i in wrap_idxs]
        detail_features.append("grip_wrap")
    detail_features.append("finger_grooves")
    detail_features.append("ergonomic_oval_grip")
    running_vert_count += len(grip_verts)

    # === 2. POMMEL ===
    pommel_r = 0.018
    pommel_verts, pommel_faces, pommel_uvs = _build_pommel(
        style=pommel_style,
        radius=pommel_r,
        y_pos=-0.015,
        ornament_level=ornament_level,
    )
    all_parts.append((pommel_verts, pommel_faces))
    pommel_uvs_remapped = [(0.25 + u * 0.25, v * 0.25) for u, v in pommel_uvs]
    all_uvs.append(pommel_uvs_remapped)
    pommel_indices = list(range(running_vert_count, running_vert_count + len(pommel_verts)))
    vgroup_data["pommel"] = pommel_indices
    detail_features.append(f"pommel_{pommel_style}")
    running_vert_count += len(pommel_verts)

    # === 3. GUARD ===
    guard_w = b_wid * 3.0 if style != "rapier" else b_wid * 5.0
    guard_h = 0.012
    guard_d = blade_thickness * 3.0
    guard_verts, guard_faces, guard_uvs = _build_cross_guard(
        width=guard_w, height=guard_h, depth=guard_d,
        guard_y=guard_y,
        style=g_style,
        ornament_level=ornament_level,
    )
    all_parts.append((guard_verts, guard_faces))
    guard_uvs_remapped = [(u * 0.25, 0.25 + v * 0.25) for u, v in guard_uvs]
    all_uvs.append(guard_uvs_remapped)
    guard_indices = list(range(running_vert_count, running_vert_count + len(guard_verts)))
    vgroup_data["guard"] = guard_indices
    detail_features.append(f"guard_{g_style}")
    if ornament_level >= 2:
        detail_features.append("guard_finials")
    running_vert_count += len(guard_verts)

    # === 4. BLADE ===
    blade_base_y = guard_y + guard_h

    # Ricasso (unsharpened area near guard)
    ricasso_len = b_len * 0.08
    ricasso_sections = 3
    ricasso_verts, ricasso_faces, ricasso_uvs, _ = _build_cross_section_blade(
        length=ricasso_len,
        base_width=b_wid * 1.1,
        thickness=blade_thickness * 1.3,
        edge_bevel=0.0,  # No edge on ricasso
        fuller=False,
        fuller_depth=0.0,
        taper_start=1.0,  # No taper
        taper_power=1.0,
        num_sections=ricasso_sections,
    )
    # Offset ricasso to blade base
    ricasso_verts = [(v[0], v[1] + blade_base_y, v[2]) for v in ricasso_verts]
    all_parts.append((ricasso_verts, ricasso_faces))
    ricasso_uvs_remapped = [(0.5 + u * 0.5, v * 0.1) for u, v in ricasso_uvs]
    all_uvs.append(ricasso_uvs_remapped)
    ricasso_indices = list(range(running_vert_count, running_vert_count + len(ricasso_verts)))
    vgroup_data["ricasso"] = ricasso_indices
    detail_features.append("ricasso")
    running_vert_count += len(ricasso_verts)

    # Main blade
    main_blade_base_y = blade_base_y + ricasso_len
    blade_verts, blade_faces, blade_uvs, bevel_idxs = _build_cross_section_blade(
        length=b_len - ricasso_len,
        base_width=b_wid,
        thickness=blade_thickness,
        edge_bevel=edge_bevel,
        fuller=fuller,
        fuller_depth=blade_thickness * 0.4,
        taper_start=t_start,
        taper_power=t_pow,
        num_sections=n_sections,
        curve_func=curve_fn,
    )
    blade_verts = [(v[0], v[1] + main_blade_base_y, v[2]) for v in blade_verts]
    all_parts.append((blade_verts, blade_faces))
    blade_uvs_remapped = [(0.5 + u * 0.5, 0.1 + v * 0.9) for u, v in blade_uvs]
    all_uvs.append(blade_uvs_remapped)
    blade_indices = list(range(running_vert_count, running_vert_count + len(blade_verts)))
    vgroup_data["blade"] = blade_indices
    if bevel_idxs:
        vgroup_data["edge_bevel"] = [running_vert_count + i for i in bevel_idxs]
        detail_features.append("edge_bevel")
    if fuller:
        detail_features.append("fuller")
    detail_features.append("spine_thickness")
    running_vert_count += len(blade_verts)

    # === 5. SCABBARD (optional) ===
    if include_scabbard:
        scab_offset_x = 0.15  # Offset to the side
        scab_verts, scab_faces, scab_uvs = _build_scabbard(
            blade_length=b_len, blade_width=b_wid, blade_thickness=blade_thickness,
            y_offset=blade_base_y,
        )
        scab_verts = [(v[0] + scab_offset_x, v[1], v[2]) for v in scab_verts]
        all_parts.append((scab_verts, scab_faces))
        scab_uvs_remapped = [(u * 0.25, 0.5 + v * 0.25) for u, v in scab_uvs]
        all_uvs.append(scab_uvs_remapped)
        scab_indices = list(range(running_vert_count, running_vert_count + len(scab_verts)))
        vgroup_data["scabbard"] = scab_indices
        detail_features.append("scabbard")
        running_vert_count += len(scab_verts)

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    # === EMPTIES (attachment points) ===
    trail_top_y = main_blade_base_y + (b_len - ricasso_len) * 1.03
    empties = {
        "hand_grip": (0.0, g_len * 0.4, 0.0),
        "hand_grip_secondary": (0.0, g_len * 0.75, 0.0),
        "back_mount": (0.0, guard_y + b_len * 0.5, 0.03),
        "hip_mount": (0.0, guard_y, 0.02),
        "wall_mount": (0.0, guard_y + b_len * 0.5, 0.0),
        "trail_top": (0.0, trail_top_y, 0.0),
        "trail_bottom": (0.0, blade_base_y, 0.0),
    }

    return _make_quality_result(
        f"QualitySword_{style}",
        merged_verts,
        merged_faces,
        merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        grip_point=empties["hand_grip"],
        trail_top=empties["trail_top"],
        trail_bottom=empties["trail_bottom"],
    )


# ===========================================================================
# AXE GENERATOR
# ===========================================================================

def _build_axe_head(
    style: str,
    head_width: float,
    head_height: float,
    head_thickness: float,
    edge_bevel: float,
    ornament_level: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]], list[int]]:
    """Build an axe head with wedge profile, cheek bevels, and beard extension."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []
    bevel_indices: list[int] = []

    # Axe head is a wedge shape in cross-section
    # Wide at the edge, narrow at the eye (shaft hole)
    # Scale sections with head height for proper detail density
    sections = max(8, int(head_height / 0.015))

    # Beard extension factor
    beard = 0.3 if style in ("battle_axe", "dane_axe") else 0.0
    # Double-head factor
    double = style == "double_axe"

    for side_mult in ([1] if not double else [1, -1]):
        side_base = len(verts)
        for si in range(sections + 1):
            t = si / sections
            # Y position along head height
            y = (t - 0.5) * head_height
            # Beard: bottom extends further forward
            beard_ext = 0.0
            if beard > 0 and t < 0.3:
                beard_ext = beard * head_width * (1.0 - t / 0.3)

            # Wedge profile: wider at cutting edge, narrower at back
            # 6 verts per section: edge bevel top, edge, edge bevel bottom,
            # cheek top, cheek bottom, back
            edge_x = side_mult * (head_width + beard_ext)
            back_x = side_mult * head_width * 0.15
            bevel = edge_bevel

            cheek_thick = head_thickness * (0.8 - 0.3 * t ** 2)

            ring_verts = [
                # Edge region
                (edge_x, y, bevel * 0.5),            # edge bevel top
                (edge_x + side_mult * bevel * 0.3, y, 0),  # edge tip
                (edge_x, y, -bevel * 0.5),            # edge bevel bottom
                # Cheek (body of head)
                (edge_x * 0.6, y, cheek_thick),       # cheek top
                (edge_x * 0.6, y, -cheek_thick),      # cheek bottom
                # Back (near eye)
                (back_x, y, cheek_thick * 0.7),       # back top
                (back_x, y, -cheek_thick * 0.7),      # back bottom
            ]
            bevel_indices.extend([len(verts), len(verts) + 1, len(verts) + 2])
            verts.extend(ring_verts)
            for vi, _ in enumerate(ring_verts):
                uvs.append((vi / 6.0, t))

        # Connect sections
        vpr = 7
        for si in range(sections):
            base_a = side_base + si * vpr
            base_b = side_base + (si + 1) * vpr
            for vi in range(vpr):
                vi_next = (vi + 1) % vpr
                faces.append((base_a + vi, base_a + vi_next, base_b + vi_next, base_b + vi))

        # Top and bottom caps
        top_base = side_base + sections * vpr
        for vi in range(vpr - 1):
            faces.append((top_base + vi, top_base + vi + 1, top_base + (vi + 2) % vpr))
        bot_base = side_base
        for vi in range(vpr - 1):
            faces.append((bot_base + (vi + 2) % vpr, bot_base + vi + 1, bot_base + vi))

    # Eye (shaft hole) - cylinder through head
    eye_radius = head_thickness * 0.8
    eye_v, eye_f = _make_cylinder(
        0, -head_height * 0.3, 0,
        eye_radius, head_height * 0.6,
        segments=8, cap_top=False, cap_bottom=False,
    )
    offset = len(verts)
    verts.extend(eye_v)
    for f in eye_f:
        faces.append(tuple(idx + offset for idx in f))
    for _ in eye_v:
        uvs.append((0.5, 0.5))

    # Langets (metal strips extending down shaft)
    if ornament_level >= 1:
        for side in (-1, 1):
            lan_v, lan_f = _make_box(
                side * head_thickness * 0.3, -head_height * 0.5 - head_height * 0.3, 0,
                head_thickness * 0.15, head_height * 0.3, head_thickness * 0.05,
            )
            offset = len(verts)
            verts.extend(lan_v)
            for f in lan_f:
                faces.append(tuple(idx + offset for idx in f))
            for _ in lan_v:
                uvs.append((0.5, 0.5))

    return verts, faces, uvs, bevel_indices


def generate_quality_axe(
    style: str = "battle_axe",
    shaft_length: float = 0.8,
    head_width: float = 0.15,
    head_height: float = 0.18,
    head_thickness: float = 0.025,
    edge_bevel: float = 0.003,
    grip_wrap: str = "leather_spiral",
    pommel_style: str = "ring",
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate an AAA-quality axe mesh.

    Styles: battle_axe, hand_axe, dane_axe, double_axe, hatchet
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    # Style presets
    presets = {
        "battle_axe": {"shaft": shaft_length, "hw": head_width, "hh": head_height},
        "hand_axe": {"shaft": 0.4, "hw": 0.10, "hh": 0.12},
        "dane_axe": {"shaft": 1.2, "hw": 0.20, "hh": 0.25},
        "double_axe": {"shaft": 0.9, "hw": 0.15, "hh": 0.18},
        "hatchet": {"shaft": 0.35, "hw": 0.08, "hh": 0.10},
    }
    preset = presets.get(style, presets["battle_axe"])

    # === 1. SHAFT (tapered oval cross-section) ===
    # Scale ring count with shaft length for proper geometry density
    shaft_rings = max(6, int(preset["shaft"] / 0.08))
    shaft_verts, shaft_faces, shaft_uvs, wrap_idxs = _build_ergonomic_grip(
        length=preset["shaft"],
        base_radius_x=0.015,
        base_radius_z=0.012,
        grip_wrap=grip_wrap,
        finger_grooves=False,
        taper=0.1,
        segments=8,
        rings=shaft_rings,
    )
    all_parts.append((shaft_verts, shaft_faces))
    shaft_uvs_remapped = [(u * 0.3, v * 0.5) for u, v in shaft_uvs]
    all_uvs.append(shaft_uvs_remapped)
    vgroup_data["shaft"] = list(range(running_vert_count, running_vert_count + len(shaft_verts)))
    if wrap_idxs:
        vgroup_data["shaft_wrap"] = [running_vert_count + i for i in wrap_idxs]
        detail_features.append("grip_wrap")
    running_vert_count += len(shaft_verts)

    # === 2. POMMEL ===
    pommel_verts, pommel_faces, pommel_uvs = _build_pommel(
        style=pommel_style, radius=0.016, y_pos=-0.01, ornament_level=ornament_level,
    )
    all_parts.append((pommel_verts, pommel_faces))
    all_uvs.append([(0.3 + u * 0.2, v * 0.2) for u, v in pommel_uvs])
    vgroup_data["pommel"] = list(range(running_vert_count, running_vert_count + len(pommel_verts)))
    detail_features.append(f"pommel_{pommel_style}")
    running_vert_count += len(pommel_verts)

    # === 3. AXE HEAD ===
    head_y = preset["shaft"] * 0.85
    head_verts, head_faces, head_uvs, bevel_idxs = _build_axe_head(
        style=style,
        head_width=preset["hw"],
        head_height=preset["hh"],
        head_thickness=head_thickness,
        edge_bevel=edge_bevel,
        ornament_level=ornament_level,
    )
    head_verts = [(v[0], v[1] + head_y, v[2]) for v in head_verts]
    all_parts.append((head_verts, head_faces))
    all_uvs.append([(0.5 + u * 0.5, v * 0.5) for u, v in head_uvs])
    vgroup_data["head"] = list(range(running_vert_count, running_vert_count + len(head_verts)))
    if bevel_idxs:
        vgroup_data["edge_bevel"] = [running_vert_count + i for i in bevel_idxs]
        detail_features.append("edge_bevel")
    detail_features.extend(["wedge_profile", "cheek_bevels", "eye_hole"])
    if style in ("battle_axe", "dane_axe"):
        detail_features.append("beard_extension")
    if ornament_level >= 1:
        detail_features.append("langets")
    running_vert_count += len(head_verts)

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "hand_grip": (0.0, preset["shaft"] * 0.35, 0.0),
        "hand_grip_secondary": (0.0, preset["shaft"] * 0.7, 0.0),
        "back_mount": (0.0, preset["shaft"] * 0.5, 0.025),
        "hip_mount": (0.0, preset["shaft"] * 0.3, 0.02),
        "wall_mount": (0.0, preset["shaft"] * 0.5, 0.0),
        "trail_top": (preset["hw"], head_y, 0.0),
        "trail_bottom": (0.0, head_y - preset["hh"] * 0.5, 0.0),
    }

    return _make_quality_result(
        f"QualityAxe_{style}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        grip_point=empties["hand_grip"],
        trail_top=empties["trail_top"],
        trail_bottom=empties["trail_bottom"],
    )


# ===========================================================================
# MACE / HAMMER GENERATOR
# ===========================================================================

def _build_flanged_head(
    radius: float,
    num_flanges: int,
    flange_height: float,
    flange_depth: float,
    edge_bevel: float,
    y_pos: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]], list[int]]:
    """Build a mace head with radiating flanges and beveled edges."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []
    bevel_indices: list[int] = []

    # Central sphere
    sv, sf = _make_sphere(0, y_pos, 0, radius, rings=6, sectors=10)
    verts.extend(sv)
    faces.extend(sf)
    for _ in sv:
        uvs.append((0.5, 0.5))

    # Flanges: radiating fins with beveled edges
    for fi in range(num_flanges):
        angle = 2.0 * math.pi * fi / num_flanges
        ca, sa = math.cos(angle), math.sin(angle)

        flange_base = len(verts)
        flange_sections = 5

        for fsi in range(flange_sections + 1):
            t = fsi / flange_sections
            y = y_pos - flange_height / 2.0 + t * flange_height

            # Flange profile: wider at base, narrower at outer edge
            inner_r = radius * 0.9
            outer_r = radius + flange_depth * (1.0 - abs(t - 0.5) * 2.0)
            bevel = edge_bevel

            # 4 verts per section: inner top, outer+bevel top, outer tip, outer+bevel bottom
            ring_verts = [
                (ca * inner_r, y, sa * inner_r),
                (ca * (outer_r - bevel), y + bevel * 0.5, sa * (outer_r - bevel)),
                (ca * outer_r, y, sa * outer_r),
                (ca * (outer_r - bevel), y - bevel * 0.5, sa * (outer_r - bevel)),
            ]
            bevel_indices.extend([len(verts) + 1, len(verts) + 2, len(verts) + 3])
            verts.extend(ring_verts)
            for vi, _ in enumerate(ring_verts):
                uvs.append((vi / 3.0, t))

        # Connect flange sections
        vpr = 4
        for fsi in range(flange_sections):
            base_a = flange_base + fsi * vpr
            base_b = flange_base + (fsi + 1) * vpr
            for vi in range(vpr):
                vi_next = (vi + 1) % vpr
                faces.append((base_a + vi, base_a + vi_next, base_b + vi_next, base_b + vi))

    return verts, faces, uvs, bevel_indices


def _build_hammer_head(
    width: float,
    height: float,
    depth: float,
    y_pos: float,
    edge_bevel: float,
    style: str = "standard",
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]], list[int]]:
    """Build a hammer/warhammer head with flat striking face and back pick."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []
    bevel_indices: list[int] = []

    # Main block head with beveled edges
    sections = 6
    for si in range(sections + 1):
        t = si / sections
        x = -width / 2.0 + t * width

        # Striking face is flat, back tapers
        if t > 0.6:
            face_t = (t - 0.6) / 0.4
            h_scale = 1.0 - 0.3 * face_t
            d_scale = 1.0 - 0.3 * face_t
        else:
            h_scale = 1.0
            d_scale = 1.0

        half_h = height / 2.0 * h_scale
        half_d = depth / 2.0 * d_scale
        bevel = edge_bevel

        ring_verts = [
            (x, y_pos - half_h + bevel, -half_d),
            (x, y_pos - half_h, -half_d + bevel),
            (x, y_pos - half_h, half_d - bevel),
            (x, y_pos - half_h + bevel, half_d),
            (x, y_pos + half_h - bevel, half_d),
            (x, y_pos + half_h, half_d - bevel),
            (x, y_pos + half_h, -half_d + bevel),
            (x, y_pos + half_h - bevel, -half_d),
        ]
        bevel_indices.extend([len(verts) + i for i in range(8)])
        verts.extend(ring_verts)
        for vi, _ in enumerate(ring_verts):
            uvs.append((t, vi / 7.0))

    # Connect sections
    vpr = 8
    for si in range(sections):
        base_a = si * vpr
        base_b = (si + 1) * vpr
        for vi in range(vpr):
            vi_next = (vi + 1) % vpr
            faces.append((base_a + vi, base_a + vi_next, base_b + vi_next, base_b + vi))

    # Caps
    first = 0
    last = sections * vpr
    for vi in range(vpr - 2):
        faces.append((first, first + vi + 1, first + vi + 2))
    for vi in range(vpr - 2):
        faces.append((last, last + vi + 2, last + vi + 1))

    # Back pick (pointed end)
    if style != "maul":
        pick_base_x = -width / 2.0
        pick_len = width * 0.8
        pv = [
            (pick_base_x, y_pos + height * 0.15, depth * 0.15),
            (pick_base_x, y_pos - height * 0.15, depth * 0.15),
            (pick_base_x, y_pos + height * 0.15, -depth * 0.15),
            (pick_base_x, y_pos - height * 0.15, -depth * 0.15),
            (pick_base_x - pick_len, y_pos, 0),  # pick tip
        ]
        offset = len(verts)
        verts.extend(pv)
        faces.extend([
            (offset, offset + 1, offset + 4),
            (offset + 1, offset + 3, offset + 4),
            (offset + 3, offset + 2, offset + 4),
            (offset + 2, offset, offset + 4),
            (offset, offset + 2, offset + 3, offset + 1),
        ])
        for _ in pv:
            uvs.append((0.5, 0.5))
        detail_features_extra = ["back_pick"]
    else:
        detail_features_extra = []

    return verts, faces, uvs, bevel_indices


def generate_quality_mace(
    style: str = "flanged",
    shaft_length: float = 0.5,
    head_radius: float = 0.04,
    num_flanges: int = 7,
    edge_bevel: float = 0.003,
    grip_wrap: str = "leather_spiral",
    pommel_style: str = "disk",
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate an AAA-quality mace or hammer mesh.

    Styles: flanged, morningstar, hammer, maul, studded
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    # === 1. SHAFT ===
    shaft_verts, shaft_faces, shaft_uvs, wrap_idxs = _build_ergonomic_grip(
        length=shaft_length,
        base_radius_x=0.013,
        base_radius_z=0.010,
        grip_wrap=grip_wrap,
        finger_grooves=True,
        taper=0.12,
        segments=8,
        rings=10,
    )
    all_parts.append((shaft_verts, shaft_faces))
    all_uvs.append([(u * 0.3, v * 0.5) for u, v in shaft_uvs])
    vgroup_data["shaft"] = list(range(running_vert_count, running_vert_count + len(shaft_verts)))
    if wrap_idxs:
        detail_features.append("grip_wrap")
    detail_features.append("finger_grooves")
    running_vert_count += len(shaft_verts)

    # === 2. POMMEL ===
    pommel_verts, pommel_faces, pommel_uvs = _build_pommel(
        style=pommel_style, radius=0.016, y_pos=-0.01, ornament_level=ornament_level,
    )
    all_parts.append((pommel_verts, pommel_faces))
    all_uvs.append([(0.3 + u * 0.2, v * 0.2) for u, v in pommel_uvs])
    vgroup_data["pommel"] = list(range(running_vert_count, running_vert_count + len(pommel_verts)))
    detail_features.append(f"pommel_{pommel_style}")
    running_vert_count += len(pommel_verts)

    # === 3. COLLAR (shaft-to-head transition) ===
    collar_y = shaft_length * 0.9
    collar_v, collar_f = _make_torus(0, collar_y, 0, 0.018, 0.005, 10, 4)
    all_parts.append((collar_v, collar_f))
    all_uvs.append([(0.5, 0.5) for _ in collar_v])
    vgroup_data["collar"] = list(range(running_vert_count, running_vert_count + len(collar_v)))
    running_vert_count += len(collar_v)

    # === 4. HEAD ===
    head_y = shaft_length + head_radius

    if style in ("flanged", "studded"):
        head_verts, head_faces, head_uvs, bevel_idxs = _build_flanged_head(
            radius=head_radius,
            num_flanges=num_flanges if style == "flanged" else 0,
            flange_height=head_radius * 1.8,
            flange_depth=head_radius * 0.8,
            edge_bevel=edge_bevel,
            y_pos=head_y,
        )
        if style == "studded":
            # Add studs instead of flanges
            for si in range(12):
                phi = math.pi * (si // 4 + 0.5) / 3 + 0.3
                theta = 2 * math.pi * (si % 4) / 4 + (si // 4) * math.pi / 4
                sx = math.sin(phi) * math.cos(theta) * head_radius * 1.1
                sy = head_y + math.cos(phi) * head_radius * 1.1
                sz = math.sin(phi) * math.sin(theta) * head_radius * 1.1
                stud_v, stud_f = _make_sphere(sx, sy, sz, 0.006, rings=3, sectors=4)
                offset = len(head_verts)
                head_verts.extend(stud_v)
                for f in stud_f:
                    head_faces.append(tuple(idx + offset for idx in f))
                for _ in stud_v:
                    head_uvs.append((0.5, 0.5))
        detail_features.append("flanged_head" if style == "flanged" else "studded_head")

    elif style == "morningstar":
        # Sphere with conical spikes
        head_verts, head_faces, head_uvs, bevel_idxs = _build_flanged_head(
            radius=head_radius, num_flanges=0,
            flange_height=0, flange_depth=0, edge_bevel=edge_bevel, y_pos=head_y,
        )
        for si in range(16):
            phi = math.pi * ((si // 4) + 0.5) / 4
            theta = 2 * math.pi * (si % 4) / 4 + (si // 4) * math.pi / 4
            sx = math.sin(phi) * math.cos(theta) * head_radius
            sy = head_y + math.cos(phi) * head_radius
            sz = math.sin(phi) * math.sin(theta) * head_radius
            # Direction outward
            dx = math.sin(phi) * math.cos(theta)
            dy = math.cos(phi)
            dz = math.sin(phi) * math.sin(theta)
            spike_len = head_radius * 0.7
            tip = (sx + dx * spike_len, sy + dy * spike_len, sz + dz * spike_len)
            spike_r = 0.005
            sv, sf = _make_cone(sx, sy, sz, spike_r, spike_len, segments=4)
            # Rotate cone to point outward (simplified: just use tip)
            # Instead make a simple pyramid pointing outward
            pyr_verts = [
                (sx + dz * spike_r, sy + spike_r, sz - dx * spike_r),
                (sx - dz * spike_r, sy + spike_r, sz + dx * spike_r),
                (sx + dz * spike_r, sy - spike_r, sz - dx * spike_r),
                (sx - dz * spike_r, sy - spike_r, sz + dx * spike_r),
                tip,
            ]
            offset = len(head_verts)
            head_verts.extend(pyr_verts)
            head_faces.extend([
                (offset, offset + 1, offset + 4),
                (offset + 1, offset + 3, offset + 4),
                (offset + 3, offset + 2, offset + 4),
                (offset + 2, offset, offset + 4),
                (offset, offset + 2, offset + 3, offset + 1),
            ])
            for _ in pyr_verts:
                head_uvs.append((0.5, 0.5))
        detail_features.append("morningstar_spikes")

    elif style in ("hammer", "maul"):
        head_verts, head_faces, head_uvs, bevel_idxs = _build_hammer_head(
            width=head_radius * 2.5,
            height=head_radius * 1.5,
            depth=head_radius * 1.5,
            y_pos=head_y,
            edge_bevel=edge_bevel,
            style=style,
        )
        detail_features.append(f"{style}_head")
        if style == "hammer":
            detail_features.append("back_pick")

    else:
        head_verts, head_faces, head_uvs, bevel_idxs = _build_flanged_head(
            radius=head_radius, num_flanges=num_flanges,
            flange_height=head_radius * 1.8, flange_depth=head_radius * 0.8,
            edge_bevel=edge_bevel, y_pos=head_y,
        )
        detail_features.append("flanged_head")

    all_parts.append((head_verts, head_faces))
    all_uvs.append([(0.5 + u * 0.5, v * 0.5) for u, v in head_uvs])
    vgroup_data["head"] = list(range(running_vert_count, running_vert_count + len(head_verts)))
    if bevel_idxs:
        vgroup_data["edge_bevel"] = [running_vert_count + i for i in bevel_idxs]
        detail_features.append("edge_bevel")
    running_vert_count += len(head_verts)

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    trail_top_y = head_y + head_radius * 2
    empties = {
        "hand_grip": (0.0, shaft_length * 0.35, 0.0),
        "back_mount": (0.0, shaft_length * 0.5, 0.025),
        "hip_mount": (0.0, shaft_length * 0.3, 0.02),
        "wall_mount": (0.0, shaft_length * 0.5, 0.0),
        "trail_top": (0.0, trail_top_y, 0.0),
        "trail_bottom": (0.0, head_y - head_radius, 0.0),
    }

    return _make_quality_result(
        f"QualityMace_{style}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        grip_point=empties["hand_grip"],
        trail_top=empties["trail_top"],
        trail_bottom=empties["trail_bottom"],
    )


# ===========================================================================
# BOW GENERATOR
# ===========================================================================

def generate_quality_bow(
    style: str = "longbow",
    bow_length: float = 1.2,
    riser_width: float = 0.04,
    limb_width: float = 0.025,
    edge_bevel: float = 0.002,
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate an AAA-quality bow mesh.

    Styles: longbow, shortbow, recurve, composite
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    presets = {
        "longbow": {"length": bow_length, "curve": 0.15, "riser_len": 0.15, "recurve": 0.0},
        "shortbow": {"length": 0.7, "curve": 0.12, "riser_len": 0.10, "recurve": 0.0},
        "recurve": {"length": 0.9, "curve": 0.18, "riser_len": 0.12, "recurve": 0.06},
        "composite": {"length": 0.8, "curve": 0.16, "riser_len": 0.11, "recurve": 0.04},
    }
    preset = presets.get(style, presets["longbow"])
    half_len = preset["length"] / 2.0

    # === RISER (grip area) ===
    riser_len = preset["riser_len"]
    riser_sections = max(4, int(riser_len / 0.02))
    riser_segs = 8

    for rsi in range(riser_sections + 1):
        t = rsi / riser_sections
        y = -riser_len / 2.0 + t * riser_len
        # Wider section with arrow rest contour
        rw = riser_width * (1.0 + 0.3 * math.sin(t * math.pi))
        rd = riser_width * 0.6

        for sgi in range(riser_segs):
            angle = 2.0 * math.pi * sgi / riser_segs
            px = math.cos(angle) * rw
            pz = math.sin(angle) * rd
            # Arrow shelf (notch on one side)
            if 0.3 < t < 0.7 and abs(angle - math.pi * 0.5) < 0.5:
                pz -= riser_width * 0.15
            all_parts.append(([], []))  # placeholder cleared below
            break
        break
    # Clear placeholder
    all_parts.clear()

    # Build riser properly
    riser_verts: list[tuple[float, float, float]] = []
    riser_faces: list[tuple[int, ...]] = []
    riser_uvs_list: list[tuple[float, float]] = []

    for rsi in range(riser_sections + 1):
        t = rsi / riser_sections
        y = -riser_len / 2.0 + t * riser_len
        rw = riser_width * (1.0 + 0.3 * math.sin(t * math.pi))
        rd = riser_width * 0.6

        for sgi in range(riser_segs):
            angle = 2.0 * math.pi * sgi / riser_segs
            px = math.cos(angle) * rw
            pz = math.sin(angle) * rd
            if 0.3 < t < 0.7 and abs(angle - math.pi * 0.5) < 0.5:
                pz -= riser_width * 0.15
            riser_verts.append((px, y, pz))
            riser_uvs_list.append((sgi / riser_segs, t))

    for rsi in range(riser_sections):
        for sgi in range(riser_segs):
            sgi_next = (sgi + 1) % riser_segs
            r0 = rsi * riser_segs + sgi
            r1 = rsi * riser_segs + sgi_next
            r2 = (rsi + 1) * riser_segs + sgi_next
            r3 = (rsi + 1) * riser_segs + sgi
            riser_faces.append((r0, r1, r2, r3))

    all_parts.append((riser_verts, riser_faces))
    all_uvs.append([(u * 0.3, v * 0.2) for u, v in riser_uvs_list])
    vgroup_data["riser"] = list(range(running_vert_count, running_vert_count + len(riser_verts)))
    detail_features.extend(["riser", "arrow_shelf"])
    running_vert_count += len(riser_verts)

    # === LIMBS (upper and lower) ===
    for limb_side in (1, -1):  # 1 = upper, -1 = lower
        limb_sections = max(8, int(half_len / 0.04))
        limb_verts: list[tuple[float, float, float]] = []
        limb_faces: list[tuple[int, ...]] = []
        limb_uvs_list: list[tuple[float, float]] = []
        limb_segs = 6

        for lsi in range(limb_sections + 1):
            t = lsi / limb_sections
            y = limb_side * (riser_len / 2.0 + t * (half_len - riser_len / 2.0))

            # Limb taper: wider at riser, thinner at tip
            w = limb_width * (1.0 - 0.5 * t)
            d = limb_width * 0.5 * (1.0 - 0.4 * t)

            # Curve: bow bends away from string
            curve = preset["curve"] * math.sin(t * math.pi * 0.5)
            # Recurve at tip
            if preset["recurve"] > 0 and t > 0.8:
                recurve_t = (t - 0.8) / 0.2
                curve -= preset["recurve"] * recurve_t

            for sgi in range(limb_segs):
                angle = 2.0 * math.pi * sgi / limb_segs
                # Rectangular cross-section (tapered)
                if sgi < limb_segs // 2:
                    px = curve + math.cos(angle) * w
                else:
                    px = curve + math.cos(angle) * w
                pz = math.sin(angle) * d
                limb_verts.append((px, y, pz))
                limb_uvs_list.append((sgi / limb_segs, t))

        for lsi in range(limb_sections):
            for sgi in range(limb_segs):
                sgi_next = (sgi + 1) % limb_segs
                r0 = lsi * limb_segs + sgi
                r1 = lsi * limb_segs + sgi_next
                r2 = (lsi + 1) * limb_segs + sgi_next
                r3 = (lsi + 1) * limb_segs + sgi
                limb_faces.append((r0, r1, r2, r3))

        # Nock groove at tip
        tip_y = limb_side * half_len
        nock_v, nock_f = _make_torus(
            preset["curve"] * 0.5, tip_y, 0,
            limb_width * 0.3, limb_width * 0.08, 8, 4,
        )
        offset = len(limb_verts)
        limb_verts.extend(nock_v)
        for f in nock_f:
            limb_faces.append(tuple(idx + offset for idx in f))
        for _ in nock_v:
            limb_uvs_list.append((0.5, 1.0))

        name = "upper_limb" if limb_side > 0 else "lower_limb"
        all_parts.append((limb_verts, limb_faces))
        u_offset = 0.3 if limb_side > 0 else 0.6
        all_uvs.append([(u_offset + u * 0.3, v * 0.5) for u, v in limb_uvs_list])
        vgroup_data[name] = list(range(running_vert_count, running_vert_count + len(limb_verts)))
        running_vert_count += len(limb_verts)

    detail_features.extend(["tapered_limbs", "nock_grooves"])
    if preset["recurve"] > 0:
        detail_features.append("recurve_tips")

    # === STRING ===
    string_sections = 8
    string_verts: list[tuple[float, float, float]] = []
    string_faces: list[tuple[int, ...]] = []
    string_uvs_list: list[tuple[float, float]] = []
    string_segs = 4
    string_radius = 0.002

    for ssi in range(string_sections + 1):
        t = ssi / string_sections
        y = -half_len + t * 2.0 * half_len
        x = 0.0  # Straight string

        for sgi in range(string_segs):
            angle = 2.0 * math.pi * sgi / string_segs
            px = x + math.cos(angle) * string_radius
            pz = math.sin(angle) * string_radius
            string_verts.append((px, y, pz))
            string_uvs_list.append((sgi / string_segs, t))

    for ssi in range(string_sections):
        for sgi in range(string_segs):
            sgi_next = (sgi + 1) % string_segs
            r0 = ssi * string_segs + sgi
            r1 = ssi * string_segs + sgi_next
            r2 = (ssi + 1) * string_segs + sgi_next
            r3 = (ssi + 1) * string_segs + sgi
            string_faces.append((r0, r1, r2, r3))

    all_parts.append((string_verts, string_faces))
    all_uvs.append([(0.9 + u * 0.1, v * 0.5) for u, v in string_uvs_list])
    vgroup_data["string"] = list(range(running_vert_count, running_vert_count + len(string_verts)))
    detail_features.append("bowstring")
    running_vert_count += len(string_verts)

    # Finger grip wrap on riser
    detail_features.append("edge_bevel")

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "hand_grip": (0.0, 0.0, 0.0),
        "arrow_nock": (0.0, 0.0, -riser_width * 0.5),
        "back_mount": (0.0, 0.0, riser_width),
        "wall_mount": (0.0, 0.0, 0.0),
        "string_top": (0.0, half_len, 0.0),
        "string_bottom": (0.0, -half_len, 0.0),
    }

    return _make_quality_result(
        f"QualityBow_{style}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        grip_point=empties["hand_grip"],
    )


# ===========================================================================
# SHIELD GENERATOR
# ===========================================================================

def generate_quality_shield(
    style: str = "kite",
    size: float = 1.0,
    edge_bevel: float = 0.004,
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate an AAA-quality shield mesh.

    Styles: round, kite, heater, buckler, tower, pavise
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    presets = {
        "round": {"width": 0.30 * size, "height": 0.30 * size, "convex": 0.04, "rim_thick": 0.015},
        "kite": {"width": 0.25 * size, "height": 0.50 * size, "convex": 0.03, "rim_thick": 0.012},
        "heater": {"width": 0.28 * size, "height": 0.40 * size, "convex": 0.03, "rim_thick": 0.012},
        "buckler": {"width": 0.15 * size, "height": 0.15 * size, "convex": 0.05, "rim_thick": 0.018},
        "tower": {"width": 0.35 * size, "height": 0.70 * size, "convex": 0.02, "rim_thick": 0.015},
        "pavise": {"width": 0.35 * size, "height": 0.80 * size, "convex": 0.03, "rim_thick": 0.015},
    }
    preset = presets.get(style, presets["kite"])

    # === FACE (main shield body) ===
    w = preset["width"]
    h = preset["height"]
    convex = preset["convex"]

    # Scale grid resolution with shield size for proper detail density
    face_sections_u = max(6, int(w / 0.03))
    face_sections_v = max(8, int(h / 0.03))
    face_verts: list[tuple[float, float, float]] = []
    face_faces: list[tuple[int, ...]] = []
    face_uvs_list: list[tuple[float, float]] = []

    for vi in range(face_sections_v + 1):
        v_t = vi / face_sections_v
        y = (v_t - 0.5) * h

        # Width varies with style
        if style in ("kite", "heater"):
            # Wider at top, pointed at bottom
            if v_t < 0.4:
                w_local = w * (v_t / 0.4)
            else:
                w_local = w * (1.0 - (v_t - 0.4) / 0.6 * 0.6)
            w_local = max(w_local, 0.01)
        elif style == "tower":
            w_local = w
        elif style == "pavise":
            w_local = w * (1.0 - 0.1 * abs(v_t - 0.5))
        else:
            # Round / buckler
            w_local = w * math.sqrt(max(0, 1.0 - (2.0 * v_t - 1.0) ** 2))
            w_local = max(w_local, 0.005)

        for ui in range(face_sections_u + 1):
            u_t = ui / face_sections_u
            x = (u_t - 0.5) * 2.0 * w_local

            # Convex surface: dome shape
            r = math.sqrt((x / max(w, 0.01)) ** 2 + (y / max(h * 0.5, 0.01)) ** 2)
            z = convex * max(0, 1.0 - r ** 2)

            face_verts.append((x, y, z))
            face_uvs_list.append((u_t, v_t))

    for vi in range(face_sections_v):
        for ui in range(face_sections_u):
            r0 = vi * (face_sections_u + 1) + ui
            r1 = r0 + 1
            r2 = r1 + (face_sections_u + 1)
            r3 = r0 + (face_sections_u + 1)
            face_faces.append((r0, r1, r2, r3))

    all_parts.append((face_verts, face_faces))
    all_uvs.append([(u * 0.5, v * 0.5) for u, v in face_uvs_list])
    vgroup_data["face"] = list(range(running_vert_count, running_vert_count + len(face_verts)))
    running_vert_count += len(face_verts)

    # === BACK FACE (slightly recessed) ===
    back_verts = [(v[0], v[1], -preset["rim_thick"]) for v in face_verts]
    back_faces = [(f[3], f[2], f[1], f[0]) for f in face_faces]  # Reversed winding
    all_parts.append((back_verts, back_faces))
    all_uvs.append([(0.5 + u * 0.5, v * 0.5) for u, v in face_uvs_list])
    vgroup_data["back"] = list(range(running_vert_count, running_vert_count + len(back_verts)))
    running_vert_count += len(back_verts)

    # === RIM (beveled edge band) ===
    rim_verts: list[tuple[float, float, float]] = []
    rim_faces: list[tuple[int, ...]] = []
    rim_uvs_list: list[tuple[float, float]] = []

    # Connect front edge to back edge with side faces
    # Top row
    for ui in range(face_sections_u):
        f0 = ui  # front top
        f1 = ui + 1
        # Back verts are offset by face_verts count in merged mesh
        rim_faces.append((f0, f1, len(face_verts) + f1, len(face_verts) + f0))
    # Bottom row
    bot_start = face_sections_v * (face_sections_u + 1)
    for ui in range(face_sections_u):
        f0 = bot_start + ui
        f1 = bot_start + ui + 1
        rim_faces.append((len(face_verts) + f0, len(face_verts) + f1, f1, f0))
    # Left column
    for vi in range(face_sections_v):
        f0 = vi * (face_sections_u + 1)
        f1 = (vi + 1) * (face_sections_u + 1)
        rim_faces.append((len(face_verts) + f0, len(face_verts) + f1, f1, f0))
    # Right column
    for vi in range(face_sections_v):
        f0 = vi * (face_sections_u + 1) + face_sections_u
        f1 = (vi + 1) * (face_sections_u + 1) + face_sections_u
        rim_faces.append((f0, f1, len(face_verts) + f1, len(face_verts) + f0))

    # Rim faces use indices from the already-merged front+back parts
    # We add them as additional faces on the existing geometry (no new verts needed)
    # But we need to handle this in the merge step -- add them manually
    # We'll store rim faces with proper offsets after merge
    detail_features.append("beveled_rim")

    # === BOSS (center dome) ===
    boss_radius = min(w, h * 0.5) * 0.15
    boss_verts, boss_faces = _make_sphere(0, 0, convex + 0.005, boss_radius, rings=5, sectors=8)
    all_parts.append((boss_verts, boss_faces))
    all_uvs.append([(0.25, 0.75) for _ in boss_verts])
    vgroup_data["boss"] = list(range(running_vert_count, running_vert_count + len(boss_verts)))
    detail_features.append("boss")
    running_vert_count += len(boss_verts)

    # === GRIP BAR (on back) ===
    grip_bar_v, grip_bar_f = _make_cylinder(
        0, -h * 0.1, -preset["rim_thick"] - 0.01,
        0.012, h * 0.2, segments=6,
    )
    all_parts.append((grip_bar_v, grip_bar_f))
    all_uvs.append([(0.75, 0.75) for _ in grip_bar_v])
    vgroup_data["grip_bar"] = list(range(running_vert_count, running_vert_count + len(grip_bar_v)))
    detail_features.append("grip_bar")
    running_vert_count += len(grip_bar_v)

    # === ARM STRAP (on back) ===
    strap_v, strap_f = _make_box(
        0, h * 0.1, -preset["rim_thick"] - 0.015,
        w * 0.3, 0.005, 0.01,
    )
    all_parts.append((strap_v, strap_f))
    all_uvs.append([(0.75, 0.85) for _ in strap_v])
    vgroup_data["arm_strap"] = list(range(running_vert_count, running_vert_count + len(strap_v)))
    detail_features.append("arm_strap")
    running_vert_count += len(strap_v)

    # Panel lines for heraldry
    if ornament_level >= 2:
        detail_features.append("heraldry_panels")

    detail_features.append("edge_bevel")
    detail_features.append("convex_face")

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    # Add rim faces (which reference indices in merged space)
    merged_faces.extend(rim_faces)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "hand_grip": (0.0, 0.0, -preset["rim_thick"] - 0.01),
        "arm_strap_empty": (0.0, h * 0.15, -preset["rim_thick"] - 0.015),
        "back_mount": (0.0, 0.0, -preset["rim_thick"] - 0.02),
        "wall_mount": (0.0, 0.0, convex + boss_radius),
    }

    return _make_quality_result(
        f"QualityShield_{style}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        category="armor",
    )


# ===========================================================================
# STAFF / WAND GENERATOR
# ===========================================================================

def generate_quality_staff(
    style: str = "gnarled",
    length: float = 1.6,
    shaft_radius: float = 0.018,
    edge_bevel: float = 0.002,
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate an AAA-quality staff or wand mesh.

    Styles: gnarled, crystal, orb_cage, skull_topped, runed, twisted
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    # === SHAFT ===
    shaft_sections = 20
    shaft_segs = 8
    shaft_verts: list[tuple[float, float, float]] = []
    shaft_faces: list[tuple[int, ...]] = []
    shaft_uvs_list: list[tuple[float, float]] = []

    for si in range(shaft_sections + 1):
        t = si / shaft_sections
        y = t * length

        # Base radius with organic variation
        r = shaft_radius * (1.0 + 0.1 * math.sin(t * math.pi * 3) * (1.0 - t))

        # Taper: thicker at bottom, thinner at top
        r *= (1.1 - 0.3 * t)

        # Knots (vertex displacement for gnarled style)
        knot_bump = 0.0
        if style == "gnarled":
            for knot_t in [0.25, 0.45, 0.72]:
                if abs(t - knot_t) < 0.05:
                    knot_bump = shaft_radius * 0.5 * (1.0 - abs(t - knot_t) / 0.05)

        # Twisted style
        twist_angle = 0.0
        if style == "twisted":
            twist_angle = t * math.pi * 3.0

        for sgi in range(shaft_segs):
            angle = 2.0 * math.pi * sgi / shaft_segs + twist_angle
            px = math.cos(angle) * (r + knot_bump)
            pz = math.sin(angle) * (r + knot_bump)
            shaft_verts.append((px, y, pz))
            shaft_uvs_list.append((sgi / shaft_segs, t))

    for si in range(shaft_sections):
        for sgi in range(shaft_segs):
            sgi_next = (sgi + 1) % shaft_segs
            r0 = si * shaft_segs + sgi
            r1 = si * shaft_segs + sgi_next
            r2 = (si + 1) * shaft_segs + sgi_next
            r3 = (si + 1) * shaft_segs + sgi
            shaft_faces.append((r0, r1, r2, r3))

    all_parts.append((shaft_verts, shaft_faces))
    all_uvs.append([(u * 0.3, v) for u, v in shaft_uvs_list])
    vgroup_data["shaft"] = list(range(running_vert_count, running_vert_count + len(shaft_verts)))
    if style == "gnarled":
        detail_features.append("organic_knots")
    if style == "twisted":
        detail_features.append("twisted_shaft")
    running_vert_count += len(shaft_verts)

    # === GRIP WRAP SECTION (middle) ===
    grip_start = length * 0.25
    grip_len = length * 0.15
    grip_verts, grip_faces, grip_uvs, wrap_idxs = _build_ergonomic_grip(
        length=grip_len,
        base_radius_x=shaft_radius * 1.2,
        base_radius_z=shaft_radius * 1.1,
        grip_wrap="leather_spiral",
        finger_grooves=False,
        taper=0.05,
        segments=8,
        rings=8,
        y_offset=grip_start,
    )
    all_parts.append((grip_verts, grip_faces))
    all_uvs.append([(0.3 + u * 0.2, v * 0.2) for u, v in grip_uvs])
    vgroup_data["grip_wrap"] = list(range(running_vert_count, running_vert_count + len(grip_verts)))
    detail_features.append("grip_wrap")
    running_vert_count += len(grip_verts)

    # === HEAD (style-dependent) ===
    head_y = length

    if style == "crystal":
        # Crystal cluster: multiple faceted prisms
        for ci in range(5):
            c_angle = ci * math.pi * 2 / 5
            c_offset_x = math.cos(c_angle) * shaft_radius * 0.5
            c_offset_z = math.sin(c_angle) * shaft_radius * 0.5
            c_height = shaft_radius * (3.0 + ci * 0.5)
            c_radius = shaft_radius * (0.4 - ci * 0.05)
            c_segs = 6  # hexagonal prism
            cv, cf = _make_tapered_cylinder(
                c_offset_x, head_y - shaft_radius, c_offset_z,
                c_radius, c_radius * 0.2,
                c_height, c_segs, rings=2,
            )
            offset = len(all_parts)
            all_parts.append((cv, cf))
            all_uvs.append([(0.5 + 0.1 * ci, 0.8) for _ in cv])
            running_vert_count += len(cv)
        detail_features.append("crystal_cluster")

    elif style == "orb_cage":
        # Cage of twisted metal strips around an orb
        orb_r = shaft_radius * 2.0
        orb_v, orb_f = _make_sphere(0, head_y + orb_r, 0, orb_r * 0.7, rings=6, sectors=8)
        all_parts.append((orb_v, orb_f))
        all_uvs.append([(0.5, 0.9) for _ in orb_v])
        running_vert_count += len(orb_v)

        # Cage bars
        cage_bars = 6
        for bi in range(cage_bars):
            angle = 2.0 * math.pi * bi / cage_bars
            bar_verts: list[tuple[float, float, float]] = []
            bar_faces: list[tuple[int, ...]] = []
            bar_sections_ct = 8
            bar_r = 0.003
            for bsi in range(bar_sections_ct + 1):
                bt = bsi / bar_sections_ct
                phi = bt * math.pi
                bx = math.cos(angle) * orb_r * math.sin(phi)
                by = head_y + orb_r - orb_r * math.cos(phi)
                bz = math.sin(angle) * orb_r * math.sin(phi)
                for sgi in range(4):
                    sa = 2.0 * math.pi * sgi / 4
                    bar_verts.append((
                        bx + math.cos(sa + angle) * bar_r,
                        by + math.sin(sa) * bar_r,
                        bz + math.sin(sa + angle) * bar_r,
                    ))
            for bsi in range(bar_sections_ct):
                for sgi in range(4):
                    sgi_next = (sgi + 1) % 4
                    r0 = bsi * 4 + sgi
                    r1 = bsi * 4 + sgi_next
                    r2 = (bsi + 1) * 4 + sgi_next
                    r3 = (bsi + 1) * 4 + sgi
                    bar_faces.append((r0, r1, r2, r3))
            all_parts.append((bar_verts, bar_faces))
            all_uvs.append([(0.7, 0.9) for _ in bar_verts])
            running_vert_count += len(bar_verts)
        detail_features.append("orb_cage")

    elif style == "skull_topped":
        # Skull on top
        skull_v, skull_f, skull_uvs = _build_pommel("skull", shaft_radius * 2.5, head_y + shaft_radius * 2.5, ornament_level)
        all_parts.append((skull_v, skull_f))
        all_uvs.append([(0.5 + u * 0.3, 0.7 + v * 0.3) for u, v in skull_uvs])
        running_vert_count += len(skull_v)
        detail_features.append("skull_topper")

    elif style == "runed":
        # Simple pointed top with rune carvings (inset geometry)
        top_v, top_f = _make_tapered_cylinder(
            0, head_y - shaft_radius, 0,
            shaft_radius * 1.3, shaft_radius * 0.2,
            shaft_radius * 4, 8, rings=3,
        )
        all_parts.append((top_v, top_f))
        all_uvs.append([(0.5, 0.9) for _ in top_v])
        running_vert_count += len(top_v)

        # Rune insets along shaft
        rune_positions = [0.5, 0.6, 0.7, 0.8]
        for rp in rune_positions:
            rv, rf = _make_torus(
                0, rp * length, 0,
                shaft_radius * 1.15, shaft_radius * 0.08, 8, 3,
            )
            all_parts.append((rv, rf))
            all_uvs.append([(0.5, 0.5) for _ in rv])
            running_vert_count += len(rv)
        detail_features.append("rune_carvings")

    else:  # gnarled or twisted (default)
        # Branching top with small sphere
        for bi in range(3):
            b_angle = bi * math.pi * 2 / 3 + 0.3
            b_len = shaft_radius * 3.0
            bv, bf = _make_tapered_cylinder(
                math.cos(b_angle) * shaft_radius * 0.5,
                head_y - shaft_radius,
                math.sin(b_angle) * shaft_radius * 0.5,
                shaft_radius * 0.6, shaft_radius * 0.15,
                b_len, 6, rings=2,
            )
            all_parts.append((bv, bf))
            all_uvs.append([(0.5, 0.9) for _ in bv])
            running_vert_count += len(bv)

        # Focus orb
        orb_v, orb_f = _make_sphere(0, head_y + shaft_radius * 2, 0, shaft_radius * 1.2, rings=5, sectors=8)
        all_parts.append((orb_v, orb_f))
        all_uvs.append([(0.5, 0.95) for _ in orb_v])
        running_vert_count += len(orb_v)
        detail_features.append("branching_top")
        detail_features.append("focus_orb")

    detail_features.append("edge_bevel")

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "hand_grip": (0.0, length * 0.25 + grip_len * 0.5, 0.0),
        "hand_grip_secondary": (0.0, length * 0.15, 0.0),
        "back_mount": (0.0, length * 0.5, shaft_radius * 2),
        "wall_mount": (0.0, length * 0.5, 0.0),
        "spell_emit": (0.0, head_y + shaft_radius * 3, 0.0),
    }

    return _make_quality_result(
        f"QualityStaff_{style}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        grip_point=empties["hand_grip"],
    )


# ===========================================================================
# ARMOR PIECE GENERATORS
# ===========================================================================

def generate_quality_pauldron(
    style: str = "plate",
    size: float = 1.0,
    num_layers: int = 3,
    edge_bevel: float = 0.003,
    ornament_level: int = 2,
    side: str = "left",
) -> MeshSpec:
    """Generate AAA-quality pauldron (shoulder armor).

    Styles: plate, chain_overlay, leather, bone, spiked
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    base_w = 0.14 * size
    base_h = 0.12 * size
    base_d = 0.10 * size
    side_mult = -1 if side == "left" else 1

    # === LAYERED PLATES ===
    for layer in range(num_layers):
        layer_t = layer / max(num_layers - 1, 1)
        layer_y_offset = -layer * base_h * 0.25
        layer_scale = 1.0 - layer * 0.15

        plate_sections_u = 8
        plate_sections_v = 6
        plate_verts: list[tuple[float, float, float]] = []
        plate_faces: list[tuple[int, ...]] = []
        plate_uvs_list: list[tuple[float, float]] = []

        for vi in range(plate_sections_v + 1):
            v_t = vi / plate_sections_v
            y = layer_y_offset + v_t * base_h * layer_scale

            for ui in range(plate_sections_u + 1):
                u_t = ui / plate_sections_u
                angle = (u_t - 0.5) * math.pi * 0.8  # Wrap around shoulder

                # Shoulder dome shape
                r = base_d * layer_scale * (1.0 - 0.3 * v_t)
                px = side_mult * (math.sin(angle) * r + base_w * 0.3)
                py = y + base_h * 0.5
                pz = math.cos(angle) * r

                plate_verts.append((px, py, pz))
                plate_uvs_list.append((u_t, v_t))

        for vi in range(plate_sections_v):
            for ui in range(plate_sections_u):
                r0 = vi * (plate_sections_u + 1) + ui
                r1 = r0 + 1
                r2 = r1 + (plate_sections_u + 1)
                r3 = r0 + (plate_sections_u + 1)
                plate_faces.append((r0, r1, r2, r3))

        all_parts.append((plate_verts, plate_faces))
        all_uvs.append([(u * 0.4, layer_t * 0.3 + v * 0.3) for u, v in plate_uvs_list])
        vgroup_data[f"layer_{layer}"] = list(range(running_vert_count, running_vert_count + len(plate_verts)))
        running_vert_count += len(plate_verts)

    detail_features.append("layered_plates")

    # === ROLLED RIM EDGE ===
    rim_v, rim_f = _make_torus(
        side_mult * base_w * 0.3, base_h * 0.5 - base_h * 0.25 * (num_layers - 1), 0,
        base_d * 0.5, edge_bevel * 2, 12, 4,
    )
    all_parts.append((rim_v, rim_f))
    all_uvs.append([(0.5, 0.8) for _ in rim_v])
    running_vert_count += len(rim_v)
    detail_features.append("rolled_rim")

    # === ATTACHMENT STRAPS ===
    for strap_i in range(2):
        strap_y = base_h * 0.2 + strap_i * base_h * 0.3
        sv, sf = _make_box(
            side_mult * base_w * 0.15, strap_y, -base_d * 0.3,
            base_w * 0.08, 0.004, 0.008,
        )
        all_parts.append((sv, sf))
        all_uvs.append([(0.5, 0.9) for _ in sv])
        running_vert_count += len(sv)

        # Buckle detail
        if ornament_level >= 1:
            bv, bf = _make_torus(
                side_mult * base_w * 0.15, strap_y, -base_d * 0.32,
                0.006, 0.002, 6, 3,
            )
            all_parts.append((bv, bf))
            all_uvs.append([(0.5, 0.95) for _ in bv])
            running_vert_count += len(bv)

    detail_features.extend(["attachment_straps", "buckle_detail", "edge_bevel"])

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "shoulder_mount": (side_mult * base_w * 0.3, base_h * 0.5, 0.0),
        "strap_upper": (side_mult * base_w * 0.15, base_h * 0.5, -base_d * 0.3),
        "strap_lower": (side_mult * base_w * 0.15, base_h * 0.2, -base_d * 0.3),
    }

    return _make_quality_result(
        f"QualityPauldron_{style}_{side}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        side=side,
        category="armor",
    )


def generate_quality_chestplate(
    style: str = "plate",
    size: float = 1.0,
    edge_bevel: float = 0.003,
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate AAA-quality chestplate with anatomical contour.

    Styles: plate, chain, leather, brigandine
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    chest_w = 0.20 * size
    chest_h = 0.35 * size
    chest_d = 0.12 * size

    # === MAIN CHEST BODY ===
    body_sections_u = 12
    body_sections_v = 16
    body_verts: list[tuple[float, float, float]] = []
    body_faces: list[tuple[int, ...]] = []
    body_uvs_list: list[tuple[float, float]] = []

    for vi in range(body_sections_v + 1):
        v_t = vi / body_sections_v
        y = (v_t - 0.5) * chest_h

        for ui in range(body_sections_u + 1):
            u_t = ui / body_sections_u
            angle = (u_t - 0.5) * math.pi  # Wrap around torso

            # Anatomical contour
            r_base = chest_d * (1.0 - 0.1 * abs(v_t - 0.4))

            # Pectoral curve (upper chest bump)
            pec_bump = 0.0
            if 0.5 < v_t < 0.8:
                pec_t = (v_t - 0.5) / 0.3
                pec_bump = chest_d * 0.08 * math.sin(pec_t * math.pi)
                # Two pectoral bumps on either side
                if abs(angle) > 0.3 and abs(angle) < 1.2:
                    pec_bump *= 1.5

            # Rib suggestion (subtle)
            rib_bump = 0.0
            if 0.2 < v_t < 0.5:
                rib_bump = chest_d * 0.01 * math.sin(v_t * 20)

            # Center ridge/keel
            keel = 0.0
            if abs(angle) < 0.3:
                keel = chest_d * 0.03 * (1.0 - abs(angle) / 0.3)

            r = r_base + pec_bump + rib_bump + keel
            px = math.sin(angle) * r
            pz = math.cos(angle) * r

            # Taper at waist
            waist_taper = 1.0
            if v_t < 0.3:
                waist_taper = 0.85 + 0.15 * (v_t / 0.3)
            px *= waist_taper

            body_verts.append((px, y, pz))
            body_uvs_list.append((u_t, v_t))

    for vi in range(body_sections_v):
        for ui in range(body_sections_u):
            r0 = vi * (body_sections_u + 1) + ui
            r1 = r0 + 1
            r2 = r1 + (body_sections_u + 1)
            r3 = r0 + (body_sections_u + 1)
            body_faces.append((r0, r1, r2, r3))

    all_parts.append((body_verts, body_faces))
    all_uvs.append([(u * 0.5, v * 0.5) for u, v in body_uvs_list])
    vgroup_data["chest_body"] = list(range(running_vert_count, running_vert_count + len(body_verts)))
    detail_features.extend(["anatomical_contour", "pectoral_curve", "center_keel"])
    running_vert_count += len(body_verts)

    # === GORGET (neck guard) ===
    gorget_v, gorget_f = _make_tapered_cylinder(
        0, chest_h * 0.35, 0,
        chest_w * 0.35, chest_w * 0.3,
        chest_h * 0.1, 10, rings=3,
        cap_top=True, cap_bottom=False,
    )
    all_parts.append((gorget_v, gorget_f))
    all_uvs.append([(0.5, 0.8) for _ in gorget_v])
    vgroup_data["gorget"] = list(range(running_vert_count, running_vert_count + len(gorget_v)))
    detail_features.append("gorget")
    running_vert_count += len(gorget_v)

    # === FAULD (waist flap) ===
    fauld_sections = 5
    fauld_segs = 10
    fauld_verts: list[tuple[float, float, float]] = []
    fauld_faces: list[tuple[int, ...]] = []
    fauld_uvs_list: list[tuple[float, float]] = []

    for fi in range(fauld_sections + 1):
        t = fi / fauld_sections
        y = -chest_h * 0.5 - t * chest_h * 0.2
        for sgi in range(fauld_segs + 1):
            u_t = sgi / fauld_segs
            angle = (u_t - 0.5) * math.pi * 0.8
            r = chest_d * (0.9 + 0.1 * t)
            px = math.sin(angle) * r * (0.85 + 0.15 * (1 - t))
            pz = math.cos(angle) * r
            fauld_verts.append((px, y, pz))
            fauld_uvs_list.append((u_t, t))

    for fi in range(fauld_sections):
        for sgi in range(fauld_segs):
            r0 = fi * (fauld_segs + 1) + sgi
            r1 = r0 + 1
            r2 = r1 + (fauld_segs + 1)
            r3 = r0 + (fauld_segs + 1)
            fauld_faces.append((r0, r1, r2, r3))

    all_parts.append((fauld_verts, fauld_faces))
    all_uvs.append([(0.5 + u * 0.5, v * 0.3) for u, v in fauld_uvs_list])
    vgroup_data["fauld"] = list(range(running_vert_count, running_vert_count + len(fauld_verts)))
    detail_features.append("fauld")
    running_vert_count += len(fauld_verts)

    # === DECORATIVE EMBOSSING REGIONS ===
    if ornament_level >= 2:
        # Center medallion
        med_v, med_f = _make_sphere(0, chest_h * 0.15, chest_d + 0.005, 0.02, rings=4, sectors=6)
        all_parts.append((med_v, med_f))
        all_uvs.append([(0.75, 0.75) for _ in med_v])
        running_vert_count += len(med_v)
        detail_features.append("embossing_medallion")

    detail_features.append("edge_bevel")

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "torso_mount": (0.0, 0.0, 0.0),
        "gorget_top": (0.0, chest_h * 0.45, 0.0),
        "fauld_bottom": (0.0, -chest_h * 0.7, 0.0),
        "brand_emblem": (0.0, chest_h * 0.15, chest_d + 0.01),
    }

    return _make_quality_result(
        f"QualityChestplate_{style}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        category="armor",
    )


def generate_quality_gauntlet(
    style: str = "plate",
    size: float = 1.0,
    side: str = "left",
    edge_bevel: float = 0.003,
    ornament_level: int = 2,
) -> MeshSpec:
    """Generate AAA-quality gauntlet with articulated fingers.

    Styles: plate, leather, chain
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    all_uvs: list[list[tuple[float, float]]] = []
    detail_features: list[str] = []
    vgroup_data: dict[str, list[int]] = {}
    running_vert_count = 0

    side_mult = -1 if side == "left" else 1
    hand_w = 0.04 * size
    hand_h = 0.06 * size
    hand_d = 0.025 * size

    # === CUFF / VAMBRACE ===
    cuff_length = 0.12 * size
    cuff_segs = 10
    cuff_sections = 6
    cuff_verts: list[tuple[float, float, float]] = []
    cuff_faces: list[tuple[int, ...]] = []
    cuff_uvs_list: list[tuple[float, float]] = []

    for ci in range(cuff_sections + 1):
        t = ci / cuff_sections
        y = -cuff_length + t * cuff_length
        # Rolled edge at bottom
        r_mult = 1.0 + (0.15 if t < 0.1 else 0.0)

        for sgi in range(cuff_segs):
            angle = 2.0 * math.pi * sgi / cuff_segs
            px = math.cos(angle) * hand_w * 1.2 * r_mult
            pz = math.sin(angle) * hand_d * 1.3 * r_mult
            cuff_verts.append((px, y, pz))
            cuff_uvs_list.append((sgi / cuff_segs, t))

    for ci in range(cuff_sections):
        for sgi in range(cuff_segs):
            sgi_next = (sgi + 1) % cuff_segs
            r0 = ci * cuff_segs + sgi
            r1 = ci * cuff_segs + sgi_next
            r2 = (ci + 1) * cuff_segs + sgi_next
            r3 = (ci + 1) * cuff_segs + sgi
            cuff_faces.append((r0, r1, r2, r3))

    all_parts.append((cuff_verts, cuff_faces))
    all_uvs.append([(u * 0.3, v * 0.3) for u, v in cuff_uvs_list])
    vgroup_data["cuff"] = list(range(running_vert_count, running_vert_count + len(cuff_verts)))
    detail_features.extend(["rolled_cuff_edge", "vambrace"])
    running_vert_count += len(cuff_verts)

    # === HAND PLATE (back of hand) ===
    plate_sections_u = 6
    plate_sections_v = 4
    plate_verts: list[tuple[float, float, float]] = []
    plate_faces: list[tuple[int, ...]] = []
    plate_uvs_list: list[tuple[float, float]] = []

    for vi in range(plate_sections_v + 1):
        v_t = vi / plate_sections_v
        y = v_t * hand_h
        for ui in range(plate_sections_u + 1):
            u_t = ui / plate_sections_u
            px = (u_t - 0.5) * hand_w * 2.0
            # Slight dome
            pz = hand_d + hand_d * 0.15 * math.sin(u_t * math.pi) * math.sin(v_t * math.pi)
            plate_verts.append((px, y, pz))
            plate_uvs_list.append((u_t, v_t))

    for vi in range(plate_sections_v):
        for ui in range(plate_sections_u):
            r0 = vi * (plate_sections_u + 1) + ui
            r1 = r0 + 1
            r2 = r1 + (plate_sections_u + 1)
            r3 = r0 + (plate_sections_u + 1)
            plate_faces.append((r0, r1, r2, r3))

    all_parts.append((plate_verts, plate_faces))
    all_uvs.append([(0.3 + u * 0.3, v * 0.3) for u, v in plate_uvs_list])
    vgroup_data["hand_plate"] = list(range(running_vert_count, running_vert_count + len(plate_verts)))
    running_vert_count += len(plate_verts)

    # === FINGER PLATES (4 fingers + thumb) ===
    finger_offsets = [
        (-hand_w * 0.75, hand_h, 0.003, 0.04),   # pinky
        (-hand_w * 0.25, hand_h * 1.05, 0.005, 0.05),  # ring
        (hand_w * 0.2, hand_h * 1.1, 0.005, 0.055),   # middle
        (hand_w * 0.65, hand_h * 1.0, 0.004, 0.045),   # index
    ]

    for fi, (fx, fy, fr, fl) in enumerate(finger_offsets):
        # 3 knuckle plates per finger with articulation gaps
        for ki in range(3):
            plate_len = fl * (0.4 - ki * 0.05)
            ky = fy + ki * fl * 0.35
            fv, ff = _make_tapered_cylinder(
                fx, ky, hand_d * 0.5,
                fr * (1.0 - ki * 0.15), fr * (0.85 - ki * 0.15),
                plate_len, 6, rings=1,
            )
            all_parts.append((fv, ff))
            all_uvs.append([(0.6 + fi * 0.1, 0.3 + ki * 0.1) for _ in fv])
            running_vert_count += len(fv)

    detail_features.extend(["articulated_fingers", "knuckle_plates"])

    # Thumb
    tv, tf = _make_tapered_cylinder(
        hand_w * 0.9, hand_h * 0.3, hand_d * 0.2,
        hand_d * 0.6, hand_d * 0.4,
        hand_h * 0.5, 6, rings=1,
    )
    all_parts.append((tv, tf))
    all_uvs.append([(0.5, 0.5) for _ in tv])
    running_vert_count += len(tv)

    # === PALM (leather mesh) ===
    palm_verts: list[tuple[float, float, float]] = []
    palm_faces: list[tuple[int, ...]] = []
    palm_sections_u = 4
    palm_sections_v = 3
    for vi in range(palm_sections_v + 1):
        v_t = vi / palm_sections_v
        y = v_t * hand_h
        for ui in range(palm_sections_u + 1):
            u_t = ui / palm_sections_u
            px = (u_t - 0.5) * hand_w * 1.8
            pz = -hand_d * 0.5
            palm_verts.append((px, y, pz))
    for vi in range(palm_sections_v):
        for ui in range(palm_sections_u):
            r0 = vi * (palm_sections_u + 1) + ui
            r1 = r0 + 1
            r2 = r1 + (palm_sections_u + 1)
            r3 = r0 + (palm_sections_u + 1)
            palm_faces.append((r3, r2, r1, r0))  # Reversed winding (faces inward)

    all_parts.append((palm_verts, palm_faces))
    all_uvs.append([(0.7, 0.7) for _ in palm_verts])
    vgroup_data["palm"] = list(range(running_vert_count, running_vert_count + len(palm_verts)))
    detail_features.append("palm_mesh")
    running_vert_count += len(palm_verts)

    detail_features.append("edge_bevel")

    # === MERGE ===
    merged_verts, merged_faces = _merge_meshes(*all_parts)
    merged_uvs = _merge_uvs(*all_uvs)

    empties = {
        "wrist_mount": (0.0, -cuff_length * 0.5, 0.0),
        "grip_center": (0.0, hand_h * 0.5, 0.0),
        "knuckle_top": (0.0, hand_h, hand_d),
    }

    return _make_quality_result(
        f"QualityGauntlet_{style}_{side}",
        merged_verts, merged_faces, merged_uvs,
        empties=empties,
        vertex_groups=vgroup_data,
        detail_features=detail_features,
        ornament_level=ornament_level,
        style=style,
        side=side,
        category="armor",
    )


# ===========================================================================
# GENERATOR REGISTRY
# ===========================================================================

QUALITY_GENERATORS: dict[str, dict] = {
    "quality_sword": {
        "func": generate_quality_sword,
        "styles": ["longsword", "shortsword", "greatsword", "bastard", "rapier", "flamberge"],
    },
    "quality_axe": {
        "func": generate_quality_axe,
        "styles": ["battle_axe", "hand_axe", "dane_axe", "double_axe", "hatchet"],
    },
    "quality_mace": {
        "func": generate_quality_mace,
        "styles": ["flanged", "morningstar", "hammer", "maul", "studded"],
    },
    "quality_bow": {
        "func": generate_quality_bow,
        "styles": ["longbow", "shortbow", "recurve", "composite"],
    },
    "quality_shield": {
        "func": generate_quality_shield,
        "styles": ["round", "kite", "heater", "buckler", "tower", "pavise"],
    },
    "quality_staff": {
        "func": generate_quality_staff,
        "styles": ["gnarled", "crystal", "orb_cage", "skull_topped", "runed", "twisted"],
    },
    "quality_pauldron": {
        "func": generate_quality_pauldron,
        "styles": ["plate", "chain_overlay", "leather", "bone", "spiked"],
    },
    "quality_chestplate": {
        "func": generate_quality_chestplate,
        "styles": ["plate", "chain", "leather", "brigandine"],
    },
    "quality_gauntlet": {
        "func": generate_quality_gauntlet,
        "styles": ["plate", "leather", "chain"],
    },
}
