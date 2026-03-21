"""Procedural mesh generation library for VeilBreakers dark fantasy assets.

Provides pure-logic mesh generation functions that return mesh specifications
(vertices, faces, UVs, metadata) WITHOUT importing bpy. Each function returns
a dict that Blender handlers can convert to actual meshes.

Categories:
- FURNITURE: tables, chairs, shelves, chests, barrels, candelabras, bookshelves
- VEGETATION: trees, rocks, mushrooms, roots, ivy
- DUNGEON PROPS: torch sconces, prison doors, sarcophagi, altars, pillars, archways, chains, skull piles
- WEAPONS: hammers, spears, crossbows, scythes, flails, whips, claws, tomes
- ARCHITECTURE: gargoyles, fountains, statues, bridges, gates, staircases

All functions are pure Python with math-only dependencies (no bpy/bmesh).
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type alias
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


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
            **extra_meta,
        },
    }


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


def _circle_points(
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    segments: int,
    axis: str = "y",
) -> list[tuple[float, float, float]]:
    """Generate points on a circle in the specified plane.

    axis='y' means the circle lies in the XZ plane at height cy.
    axis='z' means the circle lies in the XY plane at height cz.
    """
    pts: list[tuple[float, float, float]] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        ca, sa = math.cos(angle), math.sin(angle)
        if axis == "y":
            pts.append((cx + ca * radius, cy, cz + sa * radius))
        elif axis == "z":
            pts.append((cx + ca * radius, cy + sa * radius, cz))
        else:  # 'x'
            pts.append((cx, cy + ca * radius, cz + sa * radius))
    return pts


def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate an axis-aligned box centred at (cx, cy, cz) with half-sizes sx, sy, sz.

    Returns (vertices_8, faces_6) with face indices offset by base_idx.
    """
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
    b = base_idx
    faces = [
        (b + 0, b + 3, b + 2, b + 1),
        (b + 4, b + 5, b + 6, b + 7),
        (b + 0, b + 1, b + 5, b + 4),
        (b + 2, b + 3, b + 7, b + 6),
        (b + 0, b + 4, b + 7, b + 3),
        (b + 1, b + 2, b + 6, b + 5),
    ]
    return verts, faces


def _make_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
    base_idx: int = 0,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder (along Y axis) with optional caps."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Bottom ring
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((
            cx + math.cos(angle) * radius,
            cy_bottom,
            cz + math.sin(angle) * radius,
        ))
    # Top ring
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((
            cx + math.cos(angle) * radius,
            cy_bottom + height,
            cz + math.sin(angle) * radius,
        ))

    b = base_idx
    # Side faces
    for i in range(segments):
        i1 = i
        i2 = (i + 1) % segments
        faces.append((b + i1, b + i2, b + segments + i2, b + segments + i1))

    # Bottom cap
    if cap_bottom:
        faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))

    # Top cap
    if cap_top:
        faces.append(tuple(b + segments + i for i in range(segments)))

    return verts, faces


def _make_cone(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cone (apex at top, along Y axis)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Base ring
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((
            cx + math.cos(angle) * radius,
            cy_bottom,
            cz + math.sin(angle) * radius,
        ))
    # Apex
    verts.append((cx, cy_bottom + height, cz))

    b = base_idx
    apex = b + segments
    # Side triangles
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((b + i, b + i2, apex))

    # Bottom cap
    faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))

    return verts, faces


def _make_torus_ring(
    cx: float, cy: float, cz: float,
    major_radius: float, minor_radius: float,
    major_segments: int = 16,
    minor_segments: int = 8,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a torus lying in the XZ plane centred at (cx, cy, cz)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for i in range(major_segments):
        theta = 2.0 * math.pi * i / major_segments
        ct, st = math.cos(theta), math.sin(theta)
        # Centre of the tube cross-section
        tcx = cx + major_radius * ct
        tcz = cz + major_radius * st
        for j in range(minor_segments):
            phi = 2.0 * math.pi * j / minor_segments
            cp, sp = math.cos(phi), math.sin(phi)
            r = major_radius + minor_radius * cp
            verts.append((
                cx + r * ct,
                cy + minor_radius * sp,
                cz + r * st,
            ))

    b = base_idx
    for i in range(major_segments):
        i_next = (i + 1) % major_segments
        for j in range(minor_segments):
            j_next = (j + 1) % minor_segments
            v0 = b + i * minor_segments + j
            v1 = b + i * minor_segments + j_next
            v2 = b + i_next * minor_segments + j_next
            v3 = b + i_next * minor_segments + j
            faces.append((v0, v1, v2, v3))

    return verts, faces


def _make_tapered_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius_bottom: float, radius_top: float,
    height: float,
    segments: int = 12,
    rings: int = 1,
    base_idx: int = 0,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder that tapers from radius_bottom to radius_top."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    total_rings = rings + 1  # number of cross-section rings

    for ring in range(total_rings):
        t = ring / max(rings, 1)
        y = cy_bottom + t * height
        r = radius_bottom + t * (radius_top - radius_bottom)
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            verts.append((
                cx + math.cos(angle) * r,
                y,
                cz + math.sin(angle) * r,
            ))

    b = base_idx
    for ring in range(rings):
        for i in range(segments):
            i2 = (i + 1) % segments
            r0 = ring * segments
            r1 = (ring + 1) * segments
            faces.append((b + r0 + i, b + r0 + i2, b + r1 + i2, b + r1 + i))

    if cap_bottom:
        faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))
    if cap_top:
        last_ring = rings * segments
        faces.append(tuple(b + last_ring + i for i in range(segments)))

    return verts, faces


def _make_beveled_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
    bevel: float = 0.02,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a box with beveled edges for better visual quality.

    Creates a 24-vertex box where each edge is inset by `bevel` amount,
    producing chamfered edges that catch light more naturally.
    """
    hx, hy, hz = sx, sy, sz
    b_val = bevel
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # For each of the 8 corners, emit 3 vertices slightly inset along each axis
    corners = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]

    for (sx_sign, sy_sign, sz_sign) in corners:
        base_x = cx + sx_sign * hx
        base_y = cy + sy_sign * hy
        base_z = cz + sz_sign * hz
        # Vertex inset along X
        verts.append((base_x - sx_sign * b_val, base_y, base_z))
        # Vertex inset along Y
        verts.append((base_x, base_y - sy_sign * b_val, base_z))
        # Vertex inset along Z
        verts.append((base_x, base_y, base_z - sz_sign * b_val))

    b = base_idx
    # Main faces (6 quads, each using the inset vertices from 4 corners)
    # Bottom face (Y-) uses vert index 1 from each bottom corner (0,1,2,3)
    # Corner 0 -> idx 0*3+1=1, Corner 1 -> idx 1*3+1=4, etc.

    # Bottom (y-): corners 0,1,2,3 -> use Y-inset verts (index 1 of each triple)
    faces.append((b + 0 * 3 + 1, b + 3 * 3 + 1, b + 2 * 3 + 1, b + 1 * 3 + 1))
    # Top (y+): corners 4,5,6,7
    faces.append((b + 4 * 3 + 1, b + 5 * 3 + 1, b + 6 * 3 + 1, b + 7 * 3 + 1))
    # Front (z-): corners 0,1,2,3 -> use Z-inset verts (index 2)
    faces.append((b + 0 * 3 + 2, b + 1 * 3 + 2, b + 2 * 3 + 2, b + 3 * 3 + 2))
    # Back (z+): corners 4,5,6,7
    faces.append((b + 4 * 3 + 2, b + 7 * 3 + 2, b + 6 * 3 + 2, b + 5 * 3 + 2))
    # Left (x-): corners 0,3,7,4 -> use X-inset verts (index 0)
    faces.append((b + 0 * 3 + 0, b + 4 * 3 + 0, b + 7 * 3 + 0, b + 3 * 3 + 0))
    # Right (x+): corners 1,2,6,5
    faces.append((b + 1 * 3 + 0, b + 2 * 3 + 0, b + 6 * 3 + 0, b + 5 * 3 + 0))

    # Bevel edge faces -- connect adjacent inset vertices along each of the 12 edges
    # Each edge of the original cube connects 2 corners; we create a quad
    # from their respective inset vertices.
    edge_pairs = [
        # Bottom ring (y-)
        (0, 1, 0, 2),  # edge 0-1: X-inset of 0, Z-inset of 0, Z-inset of 1, X-inset of 1
        (1, 2, 0, 2),
        (2, 3, 0, 2),
        (3, 0, 0, 2),
        # Top ring (y+)
        (4, 5, 0, 2),
        (5, 6, 0, 2),
        (6, 7, 0, 2),
        (7, 4, 0, 2),
        # Vertical edges
        (0, 4, 1, 1),  # Y-inset
        (1, 5, 1, 1),
        (2, 6, 1, 1),
        (3, 7, 1, 1),
    ]

    # For the 12 edges, determine which pair of inset vertices to use
    # Bottom horizontal edges (along X or Z axis at y-)
    # Edge 0-1: along +X at z-, y-  -> use verts [Z-inset of 0, X-inset of 1]
    # and [X-inset of 0, Z-inset of 1] - this creates the bevel strip

    # Simplified: for each edge, just make a quad from the two closest inset verts
    # of each corner pair. The 'axis' of the edge determines which inset verts to pick.

    # Horizontal bottom edges (y-): corners connected by x or z movement
    def _bevel_edge(c0: int, c1: int, ax0: int, ax1: int) -> tuple[int, ...]:
        return (b + c0 * 3 + ax0, b + c0 * 3 + ax1, b + c1 * 3 + ax1, b + c1 * 3 + ax0)

    # Bottom edges (y-, z-): 0->1 along X
    faces.append(_bevel_edge(0, 1, 2, 1))  # Z-inset, Y-inset
    faces.append(_bevel_edge(1, 2, 0, 1))  # X-inset, Y-inset
    faces.append(_bevel_edge(2, 3, 2, 1))
    faces.append(_bevel_edge(3, 0, 0, 1))
    # Top edges
    faces.append(_bevel_edge(4, 5, 1, 2))
    faces.append(_bevel_edge(5, 6, 1, 0))
    faces.append(_bevel_edge(6, 7, 1, 2))
    faces.append(_bevel_edge(7, 4, 1, 0))
    # Vertical edges
    faces.append(_bevel_edge(0, 4, 0, 2))
    faces.append(_bevel_edge(1, 5, 2, 0))
    faces.append(_bevel_edge(2, 6, 0, 2))
    faces.append(_bevel_edge(3, 7, 2, 0))

    return verts, faces


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


def _make_sphere(
    cx: float, cy: float, cz: float,
    radius: float,
    rings: int = 8,
    sectors: int = 12,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a UV sphere."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Bottom pole
    verts.append((cx, cy - radius, cz))
    for i in range(1, rings):
        phi = math.pi * i / rings
        y = cy - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2.0 * math.pi * j / sectors
            verts.append((
                cx + ring_r * math.cos(theta),
                y,
                cz + ring_r * math.sin(theta),
            ))
    # Top pole
    verts.append((cx, cy + radius, cz))

    b = base_idx
    # Bottom cap triangles
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((b, b + 1 + j, b + 1 + j2))

    # Middle quads
    for i in range(rings - 2):
        for j in range(sectors):
            j2 = (j + 1) % sectors
            r0 = 1 + i * sectors
            r1 = 1 + (i + 1) * sectors
            faces.append((b + r0 + j, b + r1 + j, b + r1 + j2, b + r0 + j2))

    # Top cap triangles
    top_idx = b + len(verts) - 1
    last_ring_start = 1 + (rings - 2) * sectors
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((b + last_ring_start + j, top_idx, b + last_ring_start + j2))

    return verts, faces


def _make_lathe(
    profile: list[tuple[float, float]],
    segments: int = 12,
    base_idx: int = 0,
    close_top: bool = False,
    close_bottom: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Revolve a 2D profile (r, y) around the Y axis to create a lathe mesh.

    Profile should be a list of (radius, height) pairs from bottom to top.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n_profile = len(profile)

    for i in range(n_profile):
        r, y = profile[i]
        for j in range(segments):
            angle = 2.0 * math.pi * j / segments
            verts.append((r * math.cos(angle), y, r * math.sin(angle)))

    b = base_idx
    for i in range(n_profile - 1):
        for j in range(segments):
            j2 = (j + 1) % segments
            r0 = i * segments
            r1 = (i + 1) * segments
            faces.append((b + r0 + j, b + r0 + j2, b + r1 + j2, b + r1 + j))

    if close_bottom and n_profile > 0:
        faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))
    if close_top and n_profile > 0:
        last = (n_profile - 1) * segments
        faces.append(tuple(b + last + i for i in range(segments)))

    return verts, faces


def _make_profile_extrude(
    profile: list[tuple[float, float]],
    depth: float,
    base_idx: int = 0,
    center_z: float = 0.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Extrude a 2D profile (x, y) along the Z axis."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n = len(profile)
    hz = depth / 2.0

    # Front face vertices
    for x, y in profile:
        verts.append((x, y, center_z - hz))
    # Back face vertices
    for x, y in profile:
        verts.append((x, y, center_z + hz))

    b = base_idx
    # Side quads
    for i in range(n - 1):
        i2 = i + 1
        faces.append((b + i, b + i2, b + n + i2, b + n + i))

    # Close the loop
    faces.append((b + n - 1, b + 0, b + n, b + n + n - 1))

    # Front cap
    faces.append(tuple(b + i for i in range(n - 1, -1, -1)))
    # Back cap
    faces.append(tuple(b + n + i for i in range(n)))

    return verts, faces


# =========================================================================
# CATEGORY 1: FURNITURE
# =========================================================================


def generate_table_mesh(
    style: str = "tavern_rough",
    legs: int = 4,
    width: float = 1.2,
    height: float = 0.8,
    depth: float = 0.7,
) -> MeshSpec:
    """Generate a table mesh with proper geometry.

    Args:
        style: Visual style - "tavern_rough", "noble_carved", or "stone_slab".
        legs: Number of legs (2 or 4).
        width: Table width (X axis).
        height: Table height (Y axis).
        depth: Table depth (Z axis).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Table top
    top_thickness = 0.05 if style == "stone_slab" else 0.04
    if style == "noble_carved":
        top_thickness = 0.035
    top_verts, top_faces = _make_beveled_box(
        0, height - top_thickness / 2, 0,
        width / 2, top_thickness / 2, depth / 2,
        bevel=0.008,
    )
    parts.append((top_verts, top_faces))

    # Legs
    leg_radius = 0.035 if style == "tavern_rough" else 0.025
    leg_segments = 6 if style == "tavern_rough" else 8
    leg_height = height - top_thickness

    if style == "stone_slab":
        # Stone slab: two solid slab legs
        slab_w = width * 0.08
        slab_d = depth * 0.4
        for xoff in [-width * 0.35, width * 0.35]:
            sv, sf = _make_beveled_box(
                xoff, leg_height / 2, 0,
                slab_w, leg_height / 2, slab_d,
                bevel=0.01,
            )
            parts.append((sv, sf))
    else:
        positions = []
        inset_x = width * 0.42
        inset_z = depth * 0.42
        if legs == 4:
            positions = [
                (-inset_x, inset_z), (inset_x, inset_z),
                (-inset_x, -inset_z), (inset_x, -inset_z),
            ]
        elif legs == 2:
            positions = [(-inset_x, 0), (inset_x, 0)]
        else:
            # Default 4
            positions = [
                (-inset_x, inset_z), (inset_x, inset_z),
                (-inset_x, -inset_z), (inset_x, -inset_z),
            ]

        for lx, lz in positions:
            if style == "tavern_rough":
                # Slightly tapered rough legs
                lv, lf = _make_tapered_cylinder(
                    lx, 0, lz,
                    leg_radius * 1.2, leg_radius * 0.9,
                    leg_height, leg_segments, rings=3,
                )
            else:
                # Noble carved legs with profile
                lv, lf = _make_tapered_cylinder(
                    lx, 0, lz,
                    leg_radius * 0.8, leg_radius * 1.0,
                    leg_height, leg_segments, rings=4,
                )
            parts.append((lv, lf))

        # Cross-braces for tavern style
        if style == "tavern_rough" and legs == 4:
            brace_y = leg_height * 0.25
            brace_r = 0.012
            brace_segs = 6
            # Front-back brace
            sv, sf = _make_tapered_cylinder(
                0, brace_y, inset_z,
                brace_r, brace_r,
                width * 0.84, brace_segs, rings=1,
            )
            # Rotate by swapping axes -- approximate by placing horizontally
            rotated_v = [(v[1] - brace_y, brace_y, v[2]) for v in sv]
            # Re-place along X
            rotated_v = [
                (-width * 0.42 + (v[0] + brace_y) / leg_height * width * 0.84,
                 brace_y, inset_z)
                for i, v in enumerate(sv)
            ]
            # Simplified: just use a box brace
            bv, bf = _make_box(0, brace_y, inset_z, width * 0.42, brace_r, brace_r)
            parts.append((bv, bf))
            bv2, bf2 = _make_box(0, brace_y, -inset_z, width * 0.42, brace_r, brace_r)
            parts.append((bv2, bf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Table_{style}", verts, faces, style=style, category="furniture")


def generate_chair_mesh(
    style: str = "wooden_bench",
    has_arms: bool = False,
    has_back: bool = True,
) -> MeshSpec:
    """Generate a chair mesh.

    Args:
        style: "wooden_bench", "throne", or "stool".
        has_arms: Whether to include armrests.
        has_back: Whether to include a backrest.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    seat_w = 0.45 if style != "throne" else 0.6
    seat_d = 0.42 if style != "throne" else 0.55
    seat_h = 0.45
    seat_thick = 0.03

    # Seat
    sv, sf = _make_beveled_box(
        0, seat_h, 0,
        seat_w / 2, seat_thick / 2, seat_d / 2,
        bevel=0.005,
    )
    parts.append((sv, sf))

    # Legs
    leg_r = 0.02 if style != "throne" else 0.03
    leg_segs = 6
    inx = seat_w * 0.4
    inz = seat_d * 0.4
    for lx, lz in [(-inx, inz), (inx, inz), (-inx, -inz), (inx, -inz)]:
        lv, lf = _make_tapered_cylinder(
            lx, 0, lz,
            leg_r * 1.1, leg_r * 0.9, seat_h - seat_thick / 2,
            leg_segs, rings=2,
        )
        parts.append((lv, lf))

    # Backrest
    if has_back and style != "stool":
        back_h = 0.5 if style != "throne" else 0.9
        back_thick = 0.025 if style != "throne" else 0.04

        if style == "throne":
            # Throne: wide solid back with slight arch
            bv, bf = _make_beveled_box(
                0, seat_h + seat_thick / 2 + back_h / 2, -seat_d * 0.38,
                seat_w / 2, back_h / 2, back_thick / 2,
                bevel=0.008,
            )
            parts.append((bv, bf))
            # Throne finials (top ornaments)
            for xoff in [-seat_w * 0.38, seat_w * 0.38]:
                fv, ff = _make_sphere(
                    xoff, seat_h + seat_thick + back_h + 0.03, -seat_d * 0.38,
                    0.025, rings=5, sectors=6,
                )
                parts.append((fv, ff))
        else:
            # Wooden bench: two vertical slats
            slat_w = 0.04
            for xoff in [-seat_w * 0.25, seat_w * 0.25]:
                bv, bf = _make_beveled_box(
                    xoff, seat_h + seat_thick / 2 + back_h / 2, -seat_d * 0.38,
                    slat_w / 2, back_h / 2, back_thick / 2,
                    bevel=0.003,
                )
                parts.append((bv, bf))
            # Horizontal rail
            rv, rf = _make_beveled_box(
                0, seat_h + seat_thick + back_h * 0.85, -seat_d * 0.38,
                seat_w * 0.35, 0.015, back_thick / 2,
                bevel=0.003,
            )
            parts.append((rv, rf))

    # Armrests
    if has_arms:
        arm_h = 0.25
        arm_thick = 0.02
        arm_w = seat_d * 0.35
        for xoff in [-seat_w * 0.45, seat_w * 0.45]:
            # Arm support post
            pv, pf = _make_tapered_cylinder(
                xoff, seat_h + seat_thick / 2, seat_d * 0.15,
                leg_r, leg_r, arm_h, leg_segs, rings=1,
            )
            parts.append((pv, pf))
            # Arm rest pad
            av, af = _make_beveled_box(
                xoff, seat_h + seat_thick / 2 + arm_h, 0,
                arm_thick / 2, arm_thick / 2, arm_w,
                bevel=0.003,
            )
            parts.append((av, af))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Chair_{style}", verts, faces, style=style, category="furniture")


def generate_shelf_mesh(
    tiers: int = 3,
    width: float = 0.8,
    depth: float = 0.25,
    freestanding: bool = True,
) -> MeshSpec:
    """Generate a shelf mesh (wall-mounted or freestanding).

    Args:
        tiers: Number of shelf tiers.
        width: Width of the shelf.
        depth: Depth of each shelf.
        freestanding: If True, includes side panels; if False, wall-mount brackets.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    tier_spacing = 0.35
    shelf_thick = 0.02
    total_h = tiers * tier_spacing

    # Shelf boards
    for i in range(tiers):
        y = i * tier_spacing + shelf_thick / 2
        sv, sf = _make_beveled_box(
            0, y, 0,
            width / 2, shelf_thick / 2, depth / 2,
            bevel=0.004,
        )
        parts.append((sv, sf))

    if freestanding:
        # Side panels
        panel_thick = 0.018
        for xoff in [-width / 2 + panel_thick / 2, width / 2 - panel_thick / 2]:
            pv, pf = _make_beveled_box(
                xoff, total_h / 2, 0,
                panel_thick / 2, total_h / 2, depth / 2,
                bevel=0.003,
            )
            parts.append((pv, pf))
        # Back panel (thin)
        bv, bf = _make_beveled_box(
            0, total_h / 2, -depth / 2 + 0.005,
            width / 2, total_h / 2, 0.005,
            bevel=0.002,
        )
        parts.append((bv, bf))
    else:
        # Wall-mount brackets (L-shaped)
        bracket_thick = 0.015
        for xoff in [-width * 0.35, width * 0.35]:
            for i in range(tiers):
                y = i * tier_spacing
                # Horizontal part
                hv, hf = _make_box(
                    xoff, y - bracket_thick, -depth * 0.3,
                    bracket_thick, bracket_thick, depth * 0.3,
                )
                parts.append((hv, hf))
                # Vertical part
                vv, vf = _make_box(
                    xoff, y + tier_spacing * 0.3, -depth / 2 + bracket_thick,
                    bracket_thick, tier_spacing * 0.3, bracket_thick,
                )
                parts.append((vv, vf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Shelf", verts, faces, tiers=tiers, category="furniture")


def generate_chest_mesh(
    style: str = "wooden_bound",
    size: float = 1.0,
) -> MeshSpec:
    """Generate a chest/treasure box mesh.

    Args:
        style: "wooden_bound", "iron_locked", or "ornate_treasure".
        size: Scale factor (1.0 = standard).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    w = 0.5 * size
    h = 0.3 * size
    d = 0.35 * size

    # Main body (bottom half)
    bv, bf = _make_beveled_box(
        0, h * 0.4, 0,
        w / 2, h * 0.4, d / 2,
        bevel=0.008 * size,
    )
    parts.append((bv, bf))

    # Lid (half-cylinder top)
    lid_segs = 10
    lid_verts: list[tuple[float, float, float]] = []
    lid_faces: list[tuple[int, ...]] = []
    lid_base_y = h * 0.8
    lid_radius = d / 2

    for i in range(lid_segs + 1):
        t = i / lid_segs
        angle = math.pi * t
        y = lid_base_y + math.sin(angle) * lid_radius * 0.4
        z_scale = math.cos(angle)
        for xpos in [-w / 2, w / 2]:
            lid_verts.append((xpos, y, z_scale * lid_radius))

    for i in range(lid_segs):
        bi = i * 2
        lid_faces.append((bi, bi + 1, bi + 3, bi + 2))

    # End caps of lid
    left_indices = [i * 2 for i in range(lid_segs + 1)]
    right_indices = [i * 2 + 1 for i in range(lid_segs + 1)]
    lid_faces.append(tuple(left_indices[::-1]))
    lid_faces.append(tuple(right_indices))

    parts.append((lid_verts, lid_faces))

    # Iron bands for wooden_bound / ornate
    if style in ("wooden_bound", "ornate_treasure"):
        band_h = 0.01 * size
        band_offset = 0.005 * size
        for band_y in [h * 0.2, h * 0.6]:
            bv2, bf2 = _make_box(
                0, band_y, 0,
                w / 2 + band_offset, band_h, d / 2 + band_offset,
            )
            parts.append((bv2, bf2))

    # Lock hasp for iron_locked
    if style == "iron_locked":
        # Lock plate
        lv, lf = _make_beveled_box(
            0, h * 0.75, d / 2 + 0.01 * size,
            0.04 * size, 0.04 * size, 0.008 * size,
            bevel=0.003 * size,
        )
        parts.append((lv, lf))
        # Lock body (cylinder)
        cv, cf = _make_cylinder(
            0, h * 0.68, d / 2 + 0.018 * size,
            0.015 * size, 0.04 * size,
            segments=8,
        )
        parts.append((cv, cf))

    # Ornate corner pieces
    if style == "ornate_treasure":
        corner_r = 0.02 * size
        for xoff in [-w / 2, w / 2]:
            for zoff in [-d / 2, d / 2]:
                for yoff in [0, h * 0.78]:
                    sv, sf = _make_sphere(
                        xoff, yoff, zoff,
                        corner_r, rings=4, sectors=6,
                    )
                    parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Chest_{style}", verts, faces, style=style, category="furniture")


def generate_barrel_mesh(
    height: float = 0.9,
    radius: float = 0.25,
    staves: int = 16,
) -> MeshSpec:
    """Generate a barrel mesh with stave bulge and iron bands.

    Args:
        height: Barrel height.
        radius: Base radius.
        staves: Number of staves (vertical planks).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Main barrel body with bulge profile
    profile: list[tuple[float, float]] = []
    rings = 10
    for i in range(rings + 1):
        t = i / rings
        y = t * height
        # Barrel bulge: max at middle, narrower at top/bottom
        bulge = 1.0 + 0.12 * math.sin(t * math.pi)
        r = radius * bulge
        profile.append((r, y))

    bv, bf = _make_lathe(profile, segments=staves, close_top=True, close_bottom=True)
    parts.append((bv, bf))

    # Iron bands (torus rings)
    band_positions = [height * 0.15, height * 0.5, height * 0.85]
    for band_y in band_positions:
        # Use a thin cylinder as the band
        t = band_y / height
        bulge = 1.0 + 0.12 * math.sin(t * math.pi)
        band_r = radius * bulge + 0.005
        tv, tf = _make_torus_ring(
            0, band_y, 0,
            band_r, 0.008,
            major_segments=staves, minor_segments=4,
        )
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Barrel", verts, faces, category="furniture")


def generate_candelabra_mesh(
    arms: int = 5,
    height: float = 1.5,
    wall_mounted: bool = False,
) -> MeshSpec:
    """Generate a candelabra mesh.

    Args:
        arms: Number of candle arms.
        height: Total height.
        wall_mounted: If True, generates wall bracket version.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 8

    if wall_mounted:
        # Wall plate
        pv, pf = _make_beveled_box(
            0, height * 0.5, -0.02,
            0.06, height * 0.15, 0.01,
            bevel=0.003,
        )
        parts.append((pv, pf))
        # Single arm extending out
        av, af = _make_tapered_cylinder(
            0, height * 0.4, 0,
            0.01, 0.008, 0.2,
            segs, rings=2,
        )
        # Rotate arm forward (swap y/z approximation using horizontal placement)
        arm_verts = [(v[0], height * 0.45, v[1] - height * 0.4 + 0.15) for v in av]
        parts.append((arm_verts, af))
        # Candle cup at end
        cv, cf = _make_tapered_cylinder(
            0, height * 0.43, 0.18,
            0.02, 0.025, 0.03,
            segs, rings=1,
        )
        parts.append((cv, cf))
    else:
        # Standing candelabra
        # Base (wide disc)
        base_profile = [
            (0.12, 0),
            (0.13, 0.01),
            (0.11, 0.02),
            (0.04, 0.03),
        ]
        bsv, bsf = _make_lathe(base_profile, segments=segs, close_bottom=True)
        parts.append((bsv, bsf))

        # Central shaft
        shaft_profile = [
            (0.02, 0.03),
            (0.015, height * 0.3),
            (0.025, height * 0.35),  # Decorative node
            (0.015, height * 0.4),
            (0.012, height * 0.7),
            (0.02, height * 0.72),  # Another node
            (0.015, height * 0.75),
        ]
        sv, sf = _make_lathe(shaft_profile, segments=segs)
        parts.append((sv, sf))

        # Arms radiating from top
        arm_y = height * 0.75
        for i in range(arms):
            angle = 2.0 * math.pi * i / arms
            arm_len = 0.15
            end_x = math.cos(angle) * arm_len
            end_z = math.sin(angle) * arm_len
            # Arm (small cylinder approximated as box)
            mid_x = end_x * 0.5
            mid_z = end_z * 0.5
            arm_r = 0.008
            av, af = _make_cylinder(
                mid_x, arm_y - 0.01, mid_z,
                arm_r, 0.02, segments=6,
            )
            parts.append((av, af))

            # Curved upward section
            up_x = end_x * 0.85
            up_z = end_z * 0.85
            uv, uf = _make_cylinder(
                up_x, arm_y, up_z,
                arm_r, 0.05, segments=6,
            )
            parts.append((uv, uf))

            # Candle cup
            cv, cf = _make_tapered_cylinder(
                end_x, arm_y + 0.04, end_z,
                0.018, 0.022, 0.025,
                segs, rings=1,
            )
            parts.append((cv, cf))

            # Candle stub
            sv2, sf2 = _make_cylinder(
                end_x, arm_y + 0.065, end_z,
                0.008, 0.06, segments=6,
            )
            parts.append((sv2, sf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Candelabra", verts, faces, arms=arms, category="furniture")


def generate_bookshelf_mesh(
    sections: int = 3,
    with_books: bool = True,
) -> MeshSpec:
    """Generate a bookshelf mesh with optional book meshes.

    Args:
        sections: Number of vertical sections (rows of books).
        with_books: Whether to include book meshes on shelves.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    total_w = 0.9
    total_d = 0.28
    section_h = 0.32
    total_h = sections * section_h + 0.04  # top cap
    panel_thick = 0.02

    # Side panels
    for xoff in [-total_w / 2 + panel_thick / 2, total_w / 2 - panel_thick / 2]:
        sv, sf = _make_beveled_box(
            xoff, total_h / 2, 0,
            panel_thick / 2, total_h / 2, total_d / 2,
            bevel=0.003,
        )
        parts.append((sv, sf))

    # Shelf boards (including top and bottom)
    for i in range(sections + 1):
        y = i * section_h + panel_thick / 2
        sv, sf = _make_beveled_box(
            0, y, 0,
            total_w / 2, panel_thick / 2, total_d / 2,
            bevel=0.003,
        )
        parts.append((sv, sf))

    # Back panel
    bv, bf = _make_box(
        0, total_h / 2, -total_d / 2 + 0.005,
        total_w / 2, total_h / 2, 0.005,
    )
    parts.append((bv, bf))

    # Books
    if with_books:
        import random as _rng
        _rng.seed(42)  # Deterministic book placement
        inner_w = total_w - panel_thick * 2
        for section in range(sections):
            shelf_y = section * section_h + panel_thick
            x_cursor = -inner_w / 2 + 0.02
            while x_cursor < inner_w / 2 - 0.03:
                book_w = _rng.uniform(0.015, 0.035)
                book_h = _rng.uniform(section_h * 0.6, section_h * 0.88)
                book_d = _rng.uniform(total_d * 0.6, total_d * 0.85)
                # Slight lean
                lean = _rng.uniform(-0.02, 0.02)
                bkv, bkf = _make_beveled_box(
                    x_cursor + book_w / 2 + lean,
                    shelf_y + book_h / 2,
                    -total_d / 2 + 0.01 + book_d / 2,
                    book_w / 2, book_h / 2, book_d / 2,
                    bevel=0.002,
                )
                parts.append((bkv, bkf))
                x_cursor += book_w + _rng.uniform(0.002, 0.008)

    verts, faces = _merge_meshes(*parts)
    return _make_result("Bookshelf", verts, faces, sections=sections, category="furniture")


# =========================================================================
# CATEGORY 2: VEGETATION
# =========================================================================


def generate_tree_mesh(
    trunk_height: float = 3.0,
    trunk_radius: float = 0.2,
    branch_count: int = 8,
    canopy_style: str = "ancient_oak",
) -> MeshSpec:
    """Generate a tree mesh with trunk, branches, and canopy.

    Args:
        trunk_height: Height of the main trunk.
        trunk_radius: Radius of trunk base.
        branch_count: Number of branches.
        canopy_style: "dead_twisted", "ancient_oak", "dark_pine", or "willow_hanging".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 10

    # Trunk with taper and organic wobble
    trunk_profile: list[tuple[float, float]] = []
    trunk_rings = 12
    for i in range(trunk_rings + 1):
        t = i / trunk_rings
        y = t * trunk_height
        # Organic taper with slight bulges
        r = trunk_radius * (1.0 - t * 0.6)
        # Add subtle wobble for organic feel
        wobble = math.sin(t * 5.0) * trunk_radius * 0.05
        r += wobble
        # Root flare at base
        if t < 0.1:
            r += trunk_radius * 0.3 * (1.0 - t / 0.1)
        trunk_profile.append((max(r, 0.01), y))

    tv, tf = _make_lathe(trunk_profile, segments=segs, close_bottom=True)
    parts.append((tv, tf))

    # Branches
    branch_start_y = trunk_height * (0.3 if canopy_style != "dead_twisted" else 0.2)
    for i in range(branch_count):
        angle = 2.0 * math.pi * i / branch_count + (i * 0.3)  # Spiral offset
        t_branch = 0.3 + 0.6 * (i / max(branch_count - 1, 1))
        y = branch_start_y + (trunk_height - branch_start_y) * t_branch * 0.8
        branch_len = trunk_height * 0.3 * (1.0 - t_branch * 0.3)
        branch_r = trunk_radius * 0.2 * (1.0 - t_branch * 0.5)

        # Branch direction
        dx = math.cos(angle) * branch_len
        dz = math.sin(angle) * branch_len
        dy = branch_len * 0.3  # Slight upward

        if canopy_style == "willow_hanging":
            dy = -branch_len * 0.4  # Droop down

        # Branch as tapered cylinder segments
        n_seg = 4
        for s in range(n_seg):
            s_t = s / n_seg
            s_t2 = (s + 1) / n_seg
            x1 = dx * s_t
            y1 = y + dy * s_t
            z1 = dz * s_t
            x2 = dx * s_t2
            y2 = y + dy * s_t2
            z2 = dz * s_t2
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            mid_z = (z1 + z2) / 2
            seg_len = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
            seg_r = branch_r * (1.0 - s_t2 * 0.7)
            bv, bf = _make_cylinder(
                mid_x, mid_y - seg_len / 2, mid_z,
                max(seg_r, 0.005), seg_len, segments=6,
                cap_top=(s == n_seg - 1), cap_bottom=(s == 0),
            )
            parts.append((bv, bf))

    # Canopy
    if canopy_style == "ancient_oak":
        # Large irregular canopy blobs
        canopy_y = trunk_height * 0.85
        for i in range(5):
            angle = 2.0 * math.pi * i / 5
            ox = math.cos(angle) * trunk_height * 0.25
            oz = math.sin(angle) * trunk_height * 0.25
            oy = canopy_y + (i % 2) * trunk_height * 0.1
            cr = trunk_height * 0.2
            cv, cf = _make_sphere(ox, oy, oz, cr, rings=5, sectors=8)
            parts.append((cv, cf))
        # Central canopy mass
        cv, cf = _make_sphere(0, canopy_y + 0.1, 0, trunk_height * 0.25, rings=6, sectors=8)
        parts.append((cv, cf))

    elif canopy_style == "dark_pine":
        # Conical layered canopy
        canopy_base = trunk_height * 0.3
        canopy_top = trunk_height * 1.1
        layers = 5
        for i in range(layers):
            t = i / layers
            layer_y = canopy_base + t * (canopy_top - canopy_base)
            layer_r = trunk_height * 0.3 * (1.0 - t * 0.8)
            layer_h = (canopy_top - canopy_base) / layers * 0.6
            cv, cf = _make_cone(0, layer_y, 0, layer_r, layer_h, segments=8)
            parts.append((cv, cf))

    elif canopy_style == "dead_twisted":
        # No canopy, just twisted branch tips (already generated above)
        pass

    elif canopy_style == "willow_hanging":
        # Drooping curtain of leaf strips
        canopy_y = trunk_height * 0.75
        for i in range(12):
            angle = 2.0 * math.pi * i / 12
            ox = math.cos(angle) * trunk_height * 0.2
            oz = math.sin(angle) * trunk_height * 0.2
            # Thin hanging strip
            sv, sf = _make_box(
                ox, canopy_y - trunk_height * 0.2, oz,
                0.02, trunk_height * 0.2, 0.005,
            )
            parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Tree_{canopy_style}", verts, faces,
                        style=canopy_style, category="vegetation")


def generate_rock_mesh(
    rock_type: str = "boulder",
    size: float = 1.0,
    detail: int = 3,
) -> MeshSpec:
    """Generate a rock mesh with irregular surface.

    Args:
        rock_type: "boulder", "standing_stone", "crystal", or "rubble_pile".
        size: Scale factor.
        detail: Detail level (1-5), affects ring/sector counts.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    detail = max(1, min(5, detail))
    parts = []

    if rock_type == "boulder":
        # Deformed sphere
        rings = 4 + detail * 2
        sectors = 6 + detail * 2
        radius = 0.4 * size
        verts: list[tuple[float, float, float]] = []
        faces: list[tuple[int, ...]] = []

        # Generate deformed sphere
        import random as _rng
        _rng.seed(hash(rock_type) + detail)

        verts.append((0, -radius * 0.9, 0))  # Bottom pole
        for i in range(1, rings):
            phi = math.pi * i / rings
            y = -radius * math.cos(phi)
            ring_r = radius * math.sin(phi)
            for j in range(sectors):
                theta = 2.0 * math.pi * j / sectors
                # Add noise for irregular surface
                noise = 1.0 + _rng.uniform(-0.15, 0.2)
                r = ring_r * noise
                yn = y * (1.0 + _rng.uniform(-0.08, 0.08))
                verts.append((
                    r * math.cos(theta),
                    yn,
                    r * math.sin(theta),
                ))
        verts.append((0, radius * 0.85, 0))  # Top pole (slightly flat)

        # Bottom cap
        for j in range(sectors):
            j2 = (j + 1) % sectors
            faces.append((0, 1 + j, 1 + j2))

        # Middle quads
        for i in range(rings - 2):
            for j in range(sectors):
                j2 = (j + 1) % sectors
                r0 = 1 + i * sectors
                r1 = 1 + (i + 1) * sectors
                faces.append((r0 + j, r1 + j, r1 + j2, r0 + j2))

        # Top cap
        top_idx = len(verts) - 1
        last_ring = 1 + (rings - 2) * sectors
        for j in range(sectors):
            j2 = (j + 1) % sectors
            faces.append((last_ring + j, top_idx, last_ring + j2))

        return _make_result("Rock_boulder", verts, faces,
                            rock_type=rock_type, category="vegetation")

    elif rock_type == "standing_stone":
        # Tall irregular column
        profile: list[tuple[float, float]] = []
        h = 1.5 * size
        base_r = 0.3 * size
        _rng_ss = __import__("random")
        _rng_ss.seed(77)
        ring_count = 8 + detail * 2
        for i in range(ring_count + 1):
            t = i / ring_count
            y = t * h
            # Taper toward top with noise
            r = base_r * (1.0 - t * 0.4) * (1.0 + _rng_ss.uniform(-0.08, 0.08))
            profile.append((max(r, 0.02), y))

        sv, sf = _make_lathe(profile, segments=6 + detail, close_bottom=True, close_top=True)
        return _make_result("Rock_standing_stone", sv, sf,
                            rock_type=rock_type, category="vegetation")

    elif rock_type == "crystal":
        # Hexagonal crystal cluster
        import random as _rng
        _rng.seed(99)
        for c in range(3 + detail):
            cx = _rng.uniform(-0.15, 0.15) * size
            cz = _rng.uniform(-0.15, 0.15) * size
            crystal_h = _rng.uniform(0.3, 0.7) * size
            crystal_r = _rng.uniform(0.04, 0.1) * size
            # Hexagonal prism with pointed top
            cv, cf = _make_tapered_cylinder(
                cx, 0, cz,
                crystal_r, crystal_r * 0.3,
                crystal_h, segments=6, rings=2,
                cap_top=True, cap_bottom=True,
            )
            parts.append((cv, cf))

        verts, faces = _merge_meshes(*parts)
        return _make_result("Rock_crystal", verts, faces,
                            rock_type=rock_type, category="vegetation")

    else:  # rubble_pile
        import random as _rng
        _rng.seed(55)
        count = 5 + detail * 3
        for _ in range(count):
            rx = _rng.uniform(-0.3, 0.3) * size
            rz = _rng.uniform(-0.3, 0.3) * size
            ry = _rng.uniform(0, 0.15) * size
            rs = _rng.uniform(0.03, 0.12) * size
            # Small irregular boxes
            rv, rf = _make_beveled_box(
                rx, ry + rs, rz,
                rs * _rng.uniform(0.7, 1.3),
                rs * _rng.uniform(0.5, 1.0),
                rs * _rng.uniform(0.7, 1.3),
                bevel=rs * 0.15,
            )
            parts.append((rv, rf))

        verts, faces = _merge_meshes(*parts)
        return _make_result("Rock_rubble_pile", verts, faces,
                            rock_type=rock_type, category="vegetation")


def generate_mushroom_mesh(
    size: float = 0.5,
    cap_style: str = "giant_cap",
) -> MeshSpec:
    """Generate a mushroom mesh.

    Args:
        size: Scale factor.
        cap_style: "giant_cap", "cluster", or "shelf_fungus".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 12

    if cap_style == "giant_cap":
        # Single large mushroom
        stem_h = 0.4 * size
        stem_r = 0.04 * size

        # Stem with slight bulge
        stem_profile = [
            (stem_r * 1.3, 0),
            (stem_r, stem_h * 0.1),
            (stem_r * 0.9, stem_h * 0.5),
            (stem_r * 1.1, stem_h * 0.8),
            (stem_r * 1.2, stem_h),
        ]
        sv, sf = _make_lathe(stem_profile, segments=segs, close_bottom=True)
        parts.append((sv, sf))

        # Cap (dome)
        cap_r = 0.2 * size
        cap_h = 0.12 * size
        cap_profile = [
            (cap_r * 1.05, stem_h - 0.01 * size),
            (cap_r, stem_h),
            (cap_r * 0.95, stem_h + cap_h * 0.3),
            (cap_r * 0.8, stem_h + cap_h * 0.6),
            (cap_r * 0.5, stem_h + cap_h * 0.85),
            (cap_r * 0.15, stem_h + cap_h),
            (0.001, stem_h + cap_h * 1.02),
        ]
        cv, cf = _make_lathe(cap_profile, segments=segs)
        parts.append((cv, cf))

        # Gill ring under cap
        gill_profile = [
            (cap_r * 0.3, stem_h - 0.005 * size),
            (cap_r * 0.9, stem_h - 0.01 * size),
        ]
        gv, gf = _make_lathe(gill_profile, segments=segs)
        parts.append((gv, gf))

    elif cap_style == "cluster":
        # Multiple small mushrooms
        import random as _rng
        _rng.seed(33)
        cluster_count = 5
        for _ in range(cluster_count):
            ox = _rng.uniform(-0.1, 0.1) * size
            oz = _rng.uniform(-0.1, 0.1) * size
            s = _rng.uniform(0.3, 0.8) * size
            sh = 0.2 * s
            sr = 0.02 * s

            # Small stem
            sv, sf = _make_cylinder(ox, 0, oz, sr, sh, segments=6)
            parts.append((sv, sf))
            # Small cap
            cv, cf = _make_cone(ox, sh, oz, 0.06 * s, 0.04 * s, segments=6)
            parts.append((cv, cf))

    else:  # shelf_fungus
        # Shelf bracket growing from a surface
        shelf_count = 3
        for i in range(shelf_count):
            y = i * 0.08 * size
            shelf_r = (0.12 - i * 0.02) * size
            shelf_thick = 0.015 * size
            # Half-disc shelf
            shelf_verts: list[tuple[float, float, float]] = []
            shelf_faces: list[tuple[int, ...]] = []
            n_pts = 8

            # Top surface
            shelf_verts.append((0, y + shelf_thick, 0))  # center
            for j in range(n_pts):
                angle = math.pi * j / (n_pts - 1)
                shelf_verts.append((
                    math.cos(angle) * shelf_r,
                    y + shelf_thick,
                    math.sin(angle) * shelf_r,
                ))

            # Bottom surface
            shelf_verts.append((0, y, 0))  # center
            for j in range(n_pts):
                angle = math.pi * j / (n_pts - 1)
                shelf_verts.append((
                    math.cos(angle) * shelf_r,
                    y,
                    math.sin(angle) * shelf_r,
                ))

            # Top fan
            for j in range(n_pts - 1):
                shelf_faces.append((0, j + 1, j + 2))
            # Bottom fan
            center2 = n_pts + 1
            for j in range(n_pts - 1):
                shelf_faces.append((center2, center2 + j + 2, center2 + j + 1))
            # Rim
            for j in range(n_pts - 1):
                t = j + 1
                b_idx = center2 + j + 1
                t2 = j + 2
                b2 = center2 + j + 2
                shelf_faces.append((t, b_idx, b2, t2))

            parts.append((shelf_verts, shelf_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Mushroom_{cap_style}", verts, faces,
                        style=cap_style, category="vegetation")


def generate_root_mesh(
    spread: float = 1.5,
    thickness: float = 0.08,
    segments: int = 5,
) -> MeshSpec:
    """Generate exposed tree root meshes.

    Args:
        spread: How far roots spread from centre.
        thickness: Root thickness at base.
        segments: Number of root tendrils.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs_circ = 6

    for i in range(segments):
        angle = 2.0 * math.pi * i / segments + (i * 0.2)
        length = spread * (0.6 + 0.4 * ((i * 7 + 3) % segments) / segments)

        # Root profile tapering along its length
        root_pts = 8
        for s in range(root_pts):
            t = s / root_pts
            x = math.cos(angle) * length * t
            z = math.sin(angle) * length * t
            # Roots dip down then come back up
            y = -thickness * 2 * math.sin(t * math.pi) * (1.0 - t * 0.3)
            r = thickness * (1.0 - t * 0.8)

            if s < root_pts - 1:
                cv, cf = _make_cylinder(
                    x, y - r, z,
                    max(r, 0.005), r * 2,
                    segments=segs_circ,
                    cap_top=(s == root_pts - 2),
                    cap_bottom=(s == 0),
                )
                parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Roots", verts, faces, category="vegetation")


def generate_ivy_mesh(
    length: float = 2.0,
    density: int = 5,
) -> MeshSpec:
    """Generate wall-climbing ivy strips.

    Args:
        length: Length of ivy growth.
        density: Number of vine strands.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    import random as _rng
    _rng.seed(71)

    for strand in range(density):
        x_offset = _rng.uniform(-0.3, 0.3)
        strand_len = length * _rng.uniform(0.6, 1.0)
        vine_segs = 10
        vine_r = 0.005

        # Vine stem (series of small cylinders climbing up)
        for s in range(vine_segs):
            t = s / vine_segs
            y = t * strand_len
            x = x_offset + math.sin(t * 4 + strand) * 0.05
            z = 0.005  # Close to wall
            seg_h = strand_len / vine_segs
            cv, cf = _make_cylinder(
                x, y, z, vine_r, seg_h, segments=4,
                cap_top=False, cap_bottom=False,
            )
            parts.append((cv, cf))

            # Leaves at intervals
            if s % 2 == 0:
                leaf_size = _rng.uniform(0.02, 0.04)
                lx = x + _rng.choice([-1, 1]) * 0.03
                # Leaf as small diamond quad
                leaf_verts = [
                    (lx, y + leaf_size, z + 0.01),
                    (lx + leaf_size * 0.6, y + leaf_size * 0.5, z + 0.01),
                    (lx, y, z + 0.01),
                    (lx - leaf_size * 0.6, y + leaf_size * 0.5, z + 0.01),
                ]
                leaf_faces = [(0, 1, 2, 3)]
                parts.append((leaf_verts, leaf_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Ivy", verts, faces, category="vegetation")


# =========================================================================
# CATEGORY 3: DUNGEON PROPS
# =========================================================================


def generate_torch_sconce_mesh(
    style: str = "iron_bracket",
) -> MeshSpec:
    """Generate a wall-mounted torch holder.

    Args:
        style: "iron_bracket", "ornate_dragon", or "simple_ring".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 8

    # Wall plate
    plate_v, plate_f = _make_beveled_box(
        0, 0, -0.01,
        0.04, 0.06, 0.005,
        bevel=0.003,
    )
    parts.append((plate_v, plate_f))

    if style == "iron_bracket":
        # L-shaped bracket arm
        arm_v, arm_f = _make_box(0, 0, 0.06, 0.015, 0.015, 0.06)
        parts.append((arm_v, arm_f))
        # Torch cup at end
        cup_profile = [
            (0.025, -0.035),
            (0.03, -0.02),
            (0.035, 0),
            (0.033, 0.01),
            (0.028, 0.015),
        ]
        cv, cf = _make_lathe(cup_profile, segments=segs)
        # Offset to end of arm
        cv = [(v[0], v[1], v[2] + 0.12) for v in cv]
        parts.append((cv, cf))

    elif style == "ornate_dragon":
        # Curved arm
        arm_pts = 8
        for i in range(arm_pts):
            t = i / arm_pts
            y = 0.02 * math.sin(t * math.pi)
            z = t * 0.12
            r = 0.012
            cv, cf = _make_cylinder(0, y - r, z, r, r * 2, segments=6,
                                    cap_top=False, cap_bottom=False)
            parts.append((cv, cf))
        # Dragon head cup
        dv, df = _make_sphere(0, 0.02, 0.13, 0.025, rings=4, sectors=6)
        parts.append((dv, df))

    else:  # simple_ring
        # Ring holder
        rv, rf = _make_torus_ring(0, 0, 0.08, 0.03, 0.006,
                                  major_segments=8, minor_segments=4)
        parts.append((rv, rf))

    # Torch shaft
    tv, tf = _make_tapered_cylinder(0, 0.02, 0.12, 0.012, 0.008, 0.2, segs, rings=2)
    parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("TorchSconce", verts, faces, style=style, category="dungeon_prop")


def generate_prison_door_mesh(
    width: float = 1.0,
    height: float = 2.0,
    bar_count: int = 5,
) -> MeshSpec:
    """Generate an iron-barred prison door.

    Args:
        width: Door width.
        height: Door height.
        bar_count: Number of vertical bars.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bar_r = 0.015
    bar_segs = 6

    # Frame
    frame_thick = 0.04
    # Left post
    lv, lf = _make_beveled_box(
        -width / 2, height / 2, 0,
        frame_thick / 2, height / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((lv, lf))
    # Right post
    rv, rf = _make_beveled_box(
        width / 2, height / 2, 0,
        frame_thick / 2, height / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((rv, rf))
    # Top bar
    tv, tf = _make_beveled_box(
        0, height, 0,
        width / 2 + frame_thick / 2, frame_thick / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((tv, tf))
    # Bottom bar
    bv, bf = _make_beveled_box(
        0, 0, 0,
        width / 2 + frame_thick / 2, frame_thick / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((bv, bf))

    # Vertical bars
    inner_w = width - frame_thick
    for i in range(bar_count):
        x = -inner_w / 2 + inner_w * (i + 1) / (bar_count + 1)
        bv, bf = _make_cylinder(
            x, frame_thick, 0,
            bar_r, height - frame_thick * 2,
            segments=bar_segs,
        )
        parts.append((bv, bf))

    # Horizontal cross bars
    for y_pos in [height * 0.33, height * 0.66]:
        hv, hf = _make_cylinder(
            -inner_w / 2, y_pos, 0,
            bar_r * 0.8, inner_w,
            segments=bar_segs,
        )
        # Rotate to horizontal -- approximate by placing along X
        h_verts = [(v[1] - y_pos + (-inner_w / 2), y_pos, v[2]) for v in hv]
        parts.append((h_verts, hf))

    # Lock plate
    lv, lf = _make_beveled_box(
        width * 0.3, height * 0.45, 0.02,
        0.03, 0.04, 0.01,
        bevel=0.003,
    )
    parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("PrisonDoor", verts, faces, category="dungeon_prop")


def generate_sarcophagus_mesh(
    style: str = "stone_plain",
) -> MeshSpec:
    """Generate a stone sarcophagus (coffin) mesh.

    Args:
        style: "stone_plain", "ornate_carved", or "dark_ritual".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    w = 0.5
    h = 0.4
    d = 1.0

    # Main body (tapered slightly)
    body_profile = [
        (0, 0),
        (w * 0.45, 0),
        (w * 0.5, h * 0.1),
        (w * 0.5, h * 0.7),
        (w * 0.48, h * 0.8),
        (w * 0.4, h * 0.85),
    ]
    bv, bf = _make_profile_extrude(body_profile, d)
    parts.append((bv, bf))
    # Mirror for other side
    bv2 = [(-v[0], v[1], v[2]) for v in bv]
    bf2_r = [tuple(reversed(f)) for f in bf]
    parts.append((bv2, bf2_r))

    # Lid (slightly wider, with peaked top)
    lid_profile = [
        (w * 0.52, h * 0.85),
        (w * 0.52, h * 0.95),
        (w * 0.3, h * 1.1),
        (0, h * 1.15),
    ]
    lv, lf = _make_profile_extrude(lid_profile, d * 1.02)
    parts.append((lv, lf))
    lv2 = [(-v[0], v[1], v[2]) for v in lv]
    lf2_r = [tuple(reversed(f)) for f in lf]
    parts.append((lv2, lf2_r))

    if style == "ornate_carved":
        # Corner posts
        for xoff, zoff in [(w * 0.45, d * 0.45), (w * 0.45, -d * 0.45),
                           (-w * 0.45, d * 0.45), (-w * 0.45, -d * 0.45)]:
            cv, cf = _make_cylinder(xoff, 0, zoff, 0.03, h * 1.2, segments=6)
            parts.append((cv, cf))
            # Decorative sphere cap
            sv, sf = _make_sphere(xoff, h * 1.22, zoff, 0.035, rings=4, sectors=6)
            parts.append((sv, sf))

    elif style == "dark_ritual":
        # Rune channels (grooves along the sides as thin raised strips)
        for i in range(4):
            z = -d * 0.3 + i * d * 0.2
            rv, rf = _make_box(w * 0.52, h * 0.4, z, 0.005, h * 0.2, 0.02)
            parts.append((rv, rf))
            rv2, rf2 = _make_box(-w * 0.52, h * 0.4, z, 0.005, h * 0.2, 0.02)
            parts.append((rv2, rf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Sarcophagus_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_altar_mesh(
    style: str = "sacrificial",
) -> MeshSpec:
    """Generate an altar mesh.

    Args:
        style: "sacrificial", "prayer", or "dark_ritual".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "sacrificial":
        # Large stone slab on pillars
        slab_w, slab_h, slab_d = 1.2, 0.1, 0.7
        slab_y = 0.9
        sv, sf = _make_beveled_box(0, slab_y, 0, slab_w / 2, slab_h / 2, slab_d / 2,
                                   bevel=0.015)
        parts.append((sv, sf))

        # Blood channel groove on top (raised rim)
        rv, rf = _make_box(0, slab_y + slab_h / 2 + 0.01, 0,
                           slab_w * 0.4, 0.01, slab_d * 0.35)
        parts.append((rv, rf))

        # Four thick stone legs
        leg_r = 0.1
        for xoff, zoff in [(-0.4, 0.2), (0.4, 0.2), (-0.4, -0.2), (0.4, -0.2)]:
            lv, lf = _make_tapered_cylinder(xoff, 0, zoff, leg_r * 1.1, leg_r,
                                            slab_y - slab_h / 2, 8, rings=3)
            parts.append((lv, lf))

    elif style == "prayer":
        # Simple stone block with kneeling step
        main_w, main_h, main_d = 0.6, 0.8, 0.4
        mv, mf = _make_beveled_box(0, main_h / 2, 0, main_w / 2, main_h / 2, main_d / 2,
                                   bevel=0.01)
        parts.append((mv, mf))

        # Step in front
        step_v, step_f = _make_beveled_box(0, 0.08, main_d / 2 + 0.15,
                                           main_w * 0.4, 0.08, 0.12,
                                           bevel=0.008)
        parts.append((step_v, step_f))

        # Symbol on top (small raised disc)
        dv, df = _make_cylinder(0, main_h + 0.005, 0, 0.08, 0.01, segments=12)
        parts.append((dv, df))

    else:  # dark_ritual
        # Octagonal dark altar with rune pillars
        profile = [
            (0.5, 0),
            (0.52, 0.05),
            (0.52, 0.15),
            (0.48, 0.2),
            (0.45, 0.6),
            (0.5, 0.65),
            (0.55, 0.7),
        ]
        av, af = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
        parts.append((av, af))

        # Corner pillars
        for i in range(4):
            angle = math.pi / 4 + i * math.pi / 2
            px = math.cos(angle) * 0.7
            pz = math.sin(angle) * 0.7
            pv, pf = _make_tapered_cylinder(px, 0, pz, 0.04, 0.03, 1.0, 6, rings=3)
            parts.append((pv, pf))
            # Flame cup at top
            fv, ff = _make_cone(px, 1.0, pz, 0.05, 0.04, segments=6)
            parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Altar_{style}", verts, faces, style=style, category="dungeon_prop")


def generate_pillar_mesh(
    style: str = "stone_round",
    height: float = 3.0,
    radius: float = 0.2,
) -> MeshSpec:
    """Generate a pillar/column mesh.

    Args:
        style: "stone_round", "stone_square", or "carved_serpent".
        height: Pillar height.
        radius: Pillar radius.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "stone_round":
        # Classical column with base and capital
        # Base (wider disc)
        base_profile = [
            (radius * 1.5, 0),
            (radius * 1.5, height * 0.02),
            (radius * 1.3, height * 0.03),
            (radius * 1.1, height * 0.05),
        ]
        bv, bf = _make_lathe(base_profile, segments=16, close_bottom=True)
        parts.append((bv, bf))

        # Shaft with entasis (slight mid-bulge)
        shaft_profile = []
        shaft_rings = 12
        for i in range(shaft_rings + 1):
            t = i / shaft_rings
            y = height * 0.05 + t * height * 0.85
            # Entasis: slight outward curve
            entasis = 1.0 + 0.03 * math.sin(t * math.pi)
            r = radius * entasis
            shaft_profile.append((r, y))
        sv, sf = _make_lathe(shaft_profile, segments=16)
        parts.append((sv, sf))

        # Capital (wider top)
        cap_profile = [
            (radius * 1.1, height * 0.9),
            (radius * 1.3, height * 0.93),
            (radius * 1.5, height * 0.96),
            (radius * 1.5, height),
        ]
        cv, cf = _make_lathe(cap_profile, segments=16, close_top=True)
        parts.append((cv, cf))

    elif style == "stone_square":
        # Square column with chamfered edges
        # Base
        bv, bf = _make_beveled_box(
            0, height * 0.025, 0,
            radius * 1.4, height * 0.025, radius * 1.4,
            bevel=0.01,
        )
        parts.append((bv, bf))
        # Shaft
        sv, sf = _make_beveled_box(
            0, height * 0.5, 0,
            radius, height * 0.45, radius,
            bevel=0.015,
        )
        parts.append((sv, sf))
        # Capital
        cv, cf = _make_beveled_box(
            0, height * 0.975, 0,
            radius * 1.4, height * 0.025, radius * 1.4,
            bevel=0.01,
        )
        parts.append((cv, cf))

    else:  # carved_serpent
        # Round column with spiral carved groove
        profile = []
        rings = 24
        for i in range(rings + 1):
            t = i / rings
            y = t * height
            # Serpent wrapping creates periodic radius variation
            serpent_phase = t * 4 * math.pi
            r = radius * (1.0 + 0.08 * math.sin(serpent_phase))
            profile.append((r, y))

        sv, sf = _make_lathe(profile, segments=12, close_bottom=True, close_top=True)
        parts.append((sv, sf))

        # Base and capital
        bv, bf = _make_cylinder(0, -0.02, 0, radius * 1.4, 0.04, segments=12)
        parts.append((bv, bf))
        cv, cf = _make_cylinder(0, height - 0.02, 0, radius * 1.4, 0.04, segments=12)
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Pillar_{style}", verts, faces, style=style, category="dungeon_prop")


def generate_archway_mesh(
    width: float = 1.5,
    height: float = 2.5,
    depth: float = 0.4,
) -> MeshSpec:
    """Generate a doorway/passage archway frame.

    Args:
        width: Opening width.
        height: Total height (arch peak).
        depth: Wall thickness.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    post_w = 0.2
    arch_segs = 12

    # Left post
    lv, lf = _make_beveled_box(
        -width / 2 - post_w / 2, height * 0.4, 0,
        post_w / 2, height * 0.4, depth / 2,
        bevel=0.01,
    )
    parts.append((lv, lf))

    # Right post
    rv, rf = _make_beveled_box(
        width / 2 + post_w / 2, height * 0.4, 0,
        post_w / 2, height * 0.4, depth / 2,
        bevel=0.01,
    )
    parts.append((rv, rf))

    # Arch (semi-circular top)
    arch_inner_r = width / 2
    arch_outer_r = arch_inner_r + post_w
    spring_y = height * 0.6  # Where the arch springs from

    arch_verts: list[tuple[float, float, float]] = []
    arch_faces: list[tuple[int, ...]] = []

    for i in range(arch_segs + 1):
        t = i / arch_segs
        angle = math.pi * t
        # Inner edge
        ix = -math.cos(angle) * arch_inner_r
        iy = spring_y + math.sin(angle) * arch_inner_r
        # Outer edge
        ox = -math.cos(angle) * arch_outer_r
        oy = spring_y + math.sin(angle) * arch_outer_r

        # Front and back faces (depth)
        arch_verts.append((ix, iy, -depth / 2))
        arch_verts.append((ox, oy, -depth / 2))
        arch_verts.append((ix, iy, depth / 2))
        arch_verts.append((ox, oy, depth / 2))

    # Connect arch segments
    for i in range(arch_segs):
        b = i * 4
        # Front face (outer)
        arch_faces.append((b + 1, b + 5, b + 4, b + 0))
        # Back face (outer)
        arch_faces.append((b + 2, b + 6, b + 7, b + 3))
        # Top (outer surface)
        arch_faces.append((b + 1, b + 3, b + 7, b + 5))
        # Bottom (inner surface)
        arch_faces.append((b + 0, b + 4, b + 6, b + 2))

    parts.append((arch_verts, arch_faces))

    # Keystone at top
    kv, kf = _make_beveled_box(
        0, spring_y + arch_outer_r + 0.02, 0,
        post_w * 0.4, post_w * 0.3, depth / 2 + 0.01,
        bevel=0.008,
    )
    parts.append((kv, kf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Archway", verts, faces, category="dungeon_prop")


def generate_chain_mesh(
    links: int = 8,
    link_size: float = 0.04,
) -> MeshSpec:
    """Generate a hanging chain with interlocking links.

    Args:
        links: Number of chain links.
        link_size: Size of each link.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    link_spacing = link_size * 1.8
    wire_r = link_size * 0.15

    for i in range(links):
        y = -i * link_spacing
        # Alternate link orientation (0° and 90°)
        if i % 2 == 0:
            # Link as torus in XY plane
            tv, tf = _make_torus_ring(
                0, y, 0,
                link_size * 0.5, wire_r,
                major_segments=8, minor_segments=4,
            )
        else:
            # Link rotated 90° -- torus in YZ plane
            tv, tf = _make_torus_ring(
                0, y, 0,
                link_size * 0.5, wire_r,
                major_segments=8, minor_segments=4,
            )
            # Rotate 90° around Y axis: swap X and Z
            tv = [(v[2], v[1], v[0]) for v in tv]

        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Chain", verts, faces, links=links, category="dungeon_prop")


def generate_skull_pile_mesh(
    count: int = 5,
) -> MeshSpec:
    """Generate a dark fantasy skull pile arrangement.

    Args:
        count: Number of skulls in the pile.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    import random as _rng
    _rng.seed(666)  # Appropriately dark seed

    skull_r = 0.06

    for i in range(count):
        # Arrange in a rough pile
        layer = 0 if i < max(count * 2 // 3, 1) else 1
        angle = _rng.uniform(0, 2 * math.pi)
        dist = _rng.uniform(0, skull_r * 2) if layer == 0 else _rng.uniform(0, skull_r)
        x = math.cos(angle) * dist
        z = math.sin(angle) * dist
        y = layer * skull_r * 1.5 + skull_r

        # Each skull: elongated sphere (cranium) + jaw box
        # Cranium
        cv, cf = _make_sphere(x, y, z, skull_r, rings=5, sectors=6)
        parts.append((cv, cf))

        # Face/jaw (smaller box in front)
        face_angle = _rng.uniform(0, 2 * math.pi)
        fx = x + math.cos(face_angle) * skull_r * 0.5
        fz = z + math.sin(face_angle) * skull_r * 0.5
        jv, jf = _make_box(fx, y - skull_r * 0.3, fz,
                           skull_r * 0.3, skull_r * 0.2, skull_r * 0.25)
        parts.append((jv, jf))

        # Eye sockets (two small indentations - represented as small spheres)
        for eye_side in [-1, 1]:
            ex = fx + eye_side * skull_r * 0.2
            ey = y + skull_r * 0.1
            ev, ef = _make_sphere(ex, ey, fz + skull_r * 0.15,
                                  skull_r * 0.12, rings=3, sectors=4)
            parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SkullPile", verts, faces, count=count, category="dungeon_prop")


# =========================================================================
# CATEGORY 4: WEAPONS (expanding beyond the existing 7 types)
# =========================================================================


def generate_hammer_mesh(
    head_style: str = "flat",
    handle_length: float = 0.9,
) -> MeshSpec:
    """Generate a warhammer mesh.

    Args:
        head_style: "flat", "spiked", or "ornate".
        handle_length: Length of the handle.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    handle_r = 0.015
    segs = 8

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9,
                                    handle_length, segs, rings=4)
    parts.append((hv, hf))

    # Pommel
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.5, rings=4, sectors=6)
    parts.append((pv, pf))

    # Hammer head
    head_y = handle_length * 0.85
    head_w = 0.12
    head_h = 0.08
    head_d = 0.06

    if head_style == "flat":
        mv, mf = _make_beveled_box(0, head_y, 0, head_w / 2, head_h / 2, head_d / 2,
                                   bevel=0.008)
        parts.append((mv, mf))

    elif head_style == "spiked":
        # Main block
        mv, mf = _make_beveled_box(0, head_y, 0, head_w / 2, head_h / 2, head_d / 2,
                                   bevel=0.005)
        parts.append((mv, mf))
        # Spike on top
        sv, sf = _make_cone(0, head_y + head_h / 2, 0, head_d * 0.3, 0.08, segments=6)
        parts.append((sv, sf))
        # Spike on back
        bsv, bsf = _make_cone(-head_w / 2, head_y, 0, head_d * 0.25, 0.06, segments=6)
        # Rotate spike to point outward (approximate)
        bsv_r = [(-head_w / 2 - (v[1] - head_y) * 0.8, head_y + (v[0] + head_w / 2), v[2])
                 for v in bsv]
        parts.append((bsv_r, bsf))

    else:  # ornate
        mv, mf = _make_beveled_box(0, head_y, 0, head_w / 2, head_h / 2, head_d / 2,
                                   bevel=0.01)
        parts.append((mv, mf))
        # Decorative rings
        for yoff in [-head_h * 0.3, head_h * 0.3]:
            rv, rf = _make_torus_ring(0, head_y + yoff, 0,
                                      head_d * 0.45, 0.005,
                                      major_segments=8, minor_segments=4)
            parts.append((rv, rf))

    # Grip wrap (subtle rings)
    for gi in range(5):
        gy = handle_length * 0.1 + gi * handle_length * 0.08
        gv, gf = _make_torus_ring(0, gy, 0,
                                  handle_r * 1.3, handle_r * 0.15,
                                  major_segments=segs, minor_segments=3)
        parts.append((gv, gf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Hammer_{head_style}", verts, faces,
                        style=head_style, category="weapon")


def generate_spear_mesh(
    head_style: str = "leaf",
    shaft_length: float = 2.0,
) -> MeshSpec:
    """Generate a spear or halberd mesh.

    Args:
        head_style: "leaf", "broad", or "halberd".
        shaft_length: Length of the shaft.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    shaft_r = 0.012
    segs = 8

    # Shaft
    sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r * 0.9,
                                    shaft_length, segs, rings=6)
    parts.append((sv, sf))

    # Butt cap
    bv, bf = _make_sphere(0, -0.01, 0, shaft_r * 1.5, rings=4, sectors=6)
    parts.append((bv, bf))

    # Spearhead
    head_base_y = shaft_length
    if head_style == "leaf":
        # Leaf-shaped blade
        blade_h = 0.2
        blade_w = 0.04
        blade_d = 0.008
        profile = []
        blade_segs = 8
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = head_base_y + t * blade_h
            w = blade_w * math.sin(t * math.pi) * (1.0 - t * 0.3)
            profile.append((max(w, 0.001), y))
        hv, hf = _make_lathe(profile, segments=4, close_bottom=True, close_top=True)
        parts.append((hv, hf))

    elif head_style == "broad":
        # Wide triangular head
        head_h = 0.15
        head_w = 0.06
        head_d = 0.006
        head_verts = [
            (0, head_base_y + head_h, 0),  # Tip
            (-head_w, head_base_y, head_d),
            (head_w, head_base_y, head_d),
            (-head_w, head_base_y, -head_d),
            (head_w, head_base_y, -head_d),
        ]
        head_faces = [
            (0, 1, 2),  # Front
            (0, 4, 3),  # Back
            (0, 2, 4),  # Right
            (0, 3, 1),  # Left
            (1, 3, 4, 2),  # Bottom
        ]
        parts.append((head_verts, head_faces))

    else:  # halberd
        # Axe blade + spike + back spike
        # Main axe blade
        blade_h = 0.2
        blade_w = 0.15
        blade_d = 0.008
        blade_verts = [
            (blade_w, head_base_y + blade_h * 0.7, blade_d),
            (blade_w, head_base_y - blade_h * 0.3, blade_d),
            (0, head_base_y - blade_h * 0.2, blade_d),
            (0, head_base_y + blade_h * 0.6, blade_d),
            (blade_w, head_base_y + blade_h * 0.7, -blade_d),
            (blade_w, head_base_y - blade_h * 0.3, -blade_d),
            (0, head_base_y - blade_h * 0.2, -blade_d),
            (0, head_base_y + blade_h * 0.6, -blade_d),
        ]
        blade_faces = [
            (0, 1, 2, 3),
            (7, 6, 5, 4),
            (0, 4, 5, 1),
            (2, 6, 7, 3),
            (0, 3, 7, 4),
            (1, 5, 6, 2),
        ]
        parts.append((blade_verts, blade_faces))

        # Top spike
        tsv, tsf = _make_cone(0, head_base_y, 0, shaft_r * 2, 0.15, segments=6)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Spear_{head_style}", verts, faces,
                        style=head_style, category="weapon")


def generate_crossbow_mesh(
    size: float = 1.0,
) -> MeshSpec:
    """Generate a crossbow mesh with mechanism.

    Args:
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Stock (main body)
    stock_len = 0.5 * s
    stock_w = 0.03 * s
    stock_h = 0.04 * s
    sv, sf = _make_beveled_box(0, 0, 0, stock_w, stock_h, stock_len / 2,
                               bevel=0.005 * s)
    parts.append((sv, sf))

    # Trigger guard
    tgv, tgf = _make_box(0, -stock_h * 1.5, -stock_len * 0.15,
                         stock_w * 0.8, stock_h * 0.8, 0.01 * s)
    parts.append((tgv, tgf))

    # Bow arms (two curved limbs)
    arm_len = 0.3 * s
    arm_segs = 6
    for side in [-1, 1]:
        arm_verts: list[tuple[float, float, float]] = []
        arm_faces_local: list[tuple[int, ...]] = []
        for i in range(arm_segs + 1):
            t = i / arm_segs
            # Curved outward
            x = side * t * arm_len
            z = stock_len / 2 - 0.02 * s
            y = -t * t * arm_len * 0.3  # Slight droop
            r = 0.01 * s * (1.0 - t * 0.3)
            cv, cf = _make_cylinder(x, y - r, z, max(r, 0.003 * s), r * 2,
                                    segments=4, cap_top=False, cap_bottom=False)
            parts.append((cv, cf))

    # String
    string_v = [
        (-arm_len, -arm_len * 0.3 * arm_len, stock_len / 2 - 0.02 * s),
        (0, 0, stock_len / 2 - 0.01 * s),
        (arm_len, -arm_len * 0.3 * arm_len, stock_len / 2 - 0.02 * s),
    ]
    string_f = [(0, 1, 2)]  # Simple triangle for string
    parts.append((string_v, string_f))

    # Rail on top
    rv, rf = _make_box(0, stock_h + 0.005 * s, 0.05 * s,
                       0.005 * s, 0.005 * s, stock_len * 0.4)
    parts.append((rv, rf))

    # Bolt/quarrel
    bv, bf = _make_tapered_cylinder(0, stock_h + 0.015 * s, 0.1 * s,
                                    0.003 * s, 0.001 * s, 0.25 * s,
                                    segments=4, rings=2)
    parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Crossbow", verts, faces, category="weapon")


def generate_scythe_mesh(
    blade_curve: float = 0.8,
    handle_length: float = 1.8,
) -> MeshSpec:
    """Generate a reaper scythe mesh.

    Args:
        blade_curve: How curved the blade is (0.5-1.5).
        handle_length: Length of the handle/shaft.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    shaft_r = 0.015
    segs = 8

    # Long shaft
    sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r * 0.85,
                                    handle_length, segs, rings=6)
    parts.append((sv, sf))

    # Scythe blade - curved using parametric points
    blade_len = 0.6
    blade_segs = 12
    blade_thick = 0.004

    blade_verts: list[tuple[float, float, float]] = []
    blade_faces: list[tuple[int, ...]] = []

    for i in range(blade_segs + 1):
        t = i / blade_segs
        # Parametric curve for blade
        angle = t * math.pi * blade_curve * 0.8
        bx = -math.sin(angle) * blade_len * t
        by = handle_length + math.cos(angle) * blade_len * t * 0.3
        # Width tapers to edge
        edge_w = 0.06 * (1.0 - t * 0.7) * math.sin(t * math.pi + 0.2)
        # Four vertices per cross-section: inner edge, outer edge, front, back
        blade_verts.append((bx, by, blade_thick))
        blade_verts.append((bx - edge_w, by - edge_w * 0.3, 0))  # Cutting edge
        blade_verts.append((bx, by, -blade_thick))

    # Connect blade quads
    for i in range(blade_segs):
        b = i * 3
        for j in range(2):
            blade_faces.append((b + j, b + j + 1, b + 3 + j + 1, b + 3 + j))

    parts.append((blade_verts, blade_faces))

    # Collar where blade meets shaft
    cv, cf = _make_torus_ring(0, handle_length, 0,
                              shaft_r * 2, shaft_r * 0.5,
                              major_segments=segs, minor_segments=4)
    parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Scythe", verts, faces, category="weapon")


def generate_flail_mesh(
    head_count: int = 1,
    chain_length: float = 0.3,
) -> MeshSpec:
    """Generate a flail (ball and chain) mesh.

    Args:
        head_count: Number of spiked balls (1-3).
        chain_length: Length of the chain.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    handle_len = 0.4
    handle_r = 0.018
    segs = 8

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.2, handle_r,
                                    handle_len, segs, rings=3)
    parts.append((hv, hf))

    # Pommel
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.5, rings=4, sectors=6)
    parts.append((pv, pf))

    # Grip wrapping
    for gi in range(4):
        gy = handle_len * 0.1 + gi * handle_len * 0.12
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.3, handle_r * 0.12,
                                  major_segments=segs, minor_segments=3)
        parts.append((gv, gf))

    head_count = max(1, min(3, head_count))

    for h in range(head_count):
        h_angle = 0 if head_count == 1 else (h - (head_count - 1) / 2) * 0.4

        # Chain links
        link_count = max(3, int(chain_length / 0.03))
        link_r = 0.008
        wire_r = 0.002
        for li in range(link_count):
            t = li / link_count
            ly = handle_len + t * chain_length
            lx = math.sin(h_angle) * t * chain_length
            tv, tf = _make_torus_ring(
                lx, ly, 0, link_r, wire_r,
                major_segments=6, minor_segments=3,
            )
            if li % 2 == 1:
                tv = [(v[2] + lx, v[1], v[0] - lx) for v in tv]
            parts.append((tv, tf))

        # Spiked ball
        ball_x = math.sin(h_angle) * chain_length
        ball_y = handle_len + chain_length
        ball_r = 0.04
        bv, bf = _make_sphere(ball_x, ball_y, 0, ball_r, rings=5, sectors=8)
        parts.append((bv, bf))

        # Spikes
        spike_count = 8
        for si in range(spike_count):
            s_phi = math.pi * (si // 4 + 0.5) / 2
            s_theta = 2 * math.pi * (si % 4) / 4 + (si // 4) * math.pi / 4
            sx = ball_x + math.sin(s_phi) * math.cos(s_theta) * ball_r
            sy = ball_y + math.cos(s_phi) * ball_r
            sz = math.sin(s_phi) * math.sin(s_theta) * ball_r
            spike_r = 0.008
            spike_h = 0.025
            spv, spf = _make_cone(sx, sy, sz, spike_r, spike_h, segments=4)
            parts.append((spv, spf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Flail", verts, faces, head_count=head_count, category="weapon")


def generate_whip_mesh(
    length: float = 2.0,
    segments: int = 20,
) -> MeshSpec:
    """Generate a segmented whip mesh.

    Args:
        length: Total whip length.
        segments: Number of whip segments.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    handle_len = 0.25
    handle_r = 0.018
    segs_circ = 6

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.2, handle_r,
                                    handle_len, segs_circ, rings=3)
    parts.append((hv, hf))

    # Pommel knot
    pv, pf = _make_sphere(0, -0.01, 0, handle_r * 1.3, rings=3, sectors=5)
    parts.append((pv, pf))

    # Whip segments -- each tapers thinner
    whip_length = length - handle_len
    for i in range(segments):
        t = i / segments
        t2 = (i + 1) / segments
        seg_len = whip_length / segments
        r = handle_r * (1.0 - t * 0.85)

        # Apply a gentle curve
        y1 = handle_len + t * whip_length
        y2 = handle_len + t2 * whip_length
        x_curve = math.sin(t * math.pi * 2) * length * 0.05
        z_curve = math.cos(t * math.pi * 1.5) * length * 0.03

        sv, sf = _make_cylinder(
            x_curve, y1, z_curve,
            max(r, 0.002), seg_len,
            segments=segs_circ,
            cap_top=(i == segments - 1),
            cap_bottom=(i == 0),
        )
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Whip", verts, faces, category="weapon")


def generate_claw_mesh(
    finger_count: int = 4,
    curve: float = 0.7,
) -> MeshSpec:
    """Generate monster claw/gauntlet mesh.

    Args:
        finger_count: Number of claw fingers (3-5).
        curve: How curved the claws are (0.3-1.5).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    finger_count = max(3, min(5, finger_count))

    # Palm/gauntlet base
    palm_r = 0.06
    palm_h = 0.08
    pv, pf = _make_tapered_cylinder(0, 0, 0, palm_r * 1.2, palm_r,
                                    palm_h, segments=finger_count * 2, rings=2)
    parts.append((pv, pf))

    # Wrist guard
    wv, wf = _make_tapered_cylinder(0, -0.05, 0, palm_r * 0.9, palm_r * 1.1,
                                    0.05, segments=8, rings=1)
    parts.append((wv, wf))

    # Claw fingers
    for i in range(finger_count):
        angle = math.pi * 0.3 + (math.pi * 0.4) * i / (finger_count - 1) if finger_count > 1 else math.pi * 0.5
        fx = math.cos(angle) * palm_r * 0.8
        fz = math.sin(angle) * palm_r * 0.8
        finger_len = 0.12 + 0.03 * (1.0 if i == 1 else 0)  # Middle finger longer

        # Finger segments
        n_segs = 4
        for s in range(n_segs):
            t = s / n_segs
            t2 = (s + 1) / n_segs
            # Curve the finger forward and inward
            seg_x = fx + math.sin(t * curve * math.pi * 0.5) * finger_len * 0.5
            seg_y = palm_h + t * finger_len * 0.8
            seg_z = fz + math.cos(t * curve * math.pi * 0.3) * finger_len * 0.2
            seg_r = 0.01 * (1.0 - t * 0.5)
            seg_h = finger_len / n_segs

            cv, cf = _make_cylinder(
                seg_x, seg_y, seg_z,
                max(seg_r, 0.003), seg_h,
                segments=4, cap_top=(s == n_segs - 1), cap_bottom=(s == 0),
            )
            parts.append((cv, cf))

        # Claw tip (sharp cone)
        tip_x = fx + math.sin(curve * math.pi * 0.5) * finger_len * 0.5
        tip_y = palm_h + finger_len * 0.8
        tip_z = fz + math.cos(curve * math.pi * 0.3) * finger_len * 0.2
        tv, tf = _make_cone(tip_x, tip_y, tip_z, 0.008, 0.04, segments=4)
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Claw", verts, faces, finger_count=finger_count, category="weapon")


def generate_tome_mesh(
    size: float = 1.0,
    pages: int = 200,
) -> MeshSpec:
    """Generate a spellbook/grimoire mesh.

    Args:
        size: Scale factor.
        pages: Number of pages (affects spine thickness).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    cover_w = 0.15 * s
    cover_h = 0.2 * s
    spine_thick = max(0.02, pages * 0.0002) * s
    cover_thick = 0.005 * s

    # Front cover
    fv, ff = _make_beveled_box(
        cover_w / 2, cover_h / 2, spine_thick / 2 + cover_thick / 2,
        cover_w / 2, cover_h / 2, cover_thick / 2,
        bevel=0.003 * s,
    )
    parts.append((fv, ff))

    # Back cover
    bv, bf = _make_beveled_box(
        cover_w / 2, cover_h / 2, -spine_thick / 2 - cover_thick / 2,
        cover_w / 2, cover_h / 2, cover_thick / 2,
        bevel=0.003 * s,
    )
    parts.append((bv, bf))

    # Spine (curved)
    spine_profile = [
        (cover_h / 2 + 0.003 * s, -spine_thick / 2 - cover_thick),
        (cover_h / 2 + 0.005 * s, -spine_thick / 4),
        (cover_h / 2 + 0.006 * s, 0),
        (cover_h / 2 + 0.005 * s, spine_thick / 4),
        (cover_h / 2 + 0.003 * s, spine_thick / 2 + cover_thick),
    ]
    # The spine runs along the left edge (x=0)
    spine_verts: list[tuple[float, float, float]] = []
    spine_faces: list[tuple[int, ...]] = []
    spine_h_segs = 8
    for i in range(len(spine_profile)):
        r, z = spine_profile[i]
        for j in range(spine_h_segs + 1):
            t = j / spine_h_segs
            y = t * cover_h
            spine_verts.append((0, y, z))

    for i in range(len(spine_profile) - 1):
        for j in range(spine_h_segs):
            s0 = i * (spine_h_segs + 1) + j
            s1 = s0 + 1
            s2 = (i + 1) * (spine_h_segs + 1) + j + 1
            s3 = (i + 1) * (spine_h_segs + 1) + j
            spine_faces.append((s0, s1, s2, s3))

    parts.append((spine_verts, spine_faces))

    # Pages block (slightly inset from covers)
    page_inset = 0.005 * s
    pv, pf = _make_box(
        cover_w / 2 + page_inset,
        cover_h / 2,
        0,
        cover_w / 2 - page_inset * 2,
        cover_h / 2 - page_inset,
        spine_thick / 2 - 0.002 * s,
    )
    parts.append((pv, pf))

    # Corner metal clasps
    clasp_size = 0.012 * s
    for yoff in [0.01 * s, cover_h - 0.01 * s]:
        for zoff in [spine_thick / 2 + cover_thick, -spine_thick / 2 - cover_thick]:
            cv, cf = _make_sphere(cover_w - 0.01 * s, yoff, zoff,
                                  clasp_size, rings=3, sectors=4)
            parts.append((cv, cf))

    # Central emblem on front cover
    ev, ef = _make_cylinder(
        cover_w / 2, cover_h / 2, spine_thick / 2 + cover_thick + 0.002 * s,
        0.02 * s, 0.003 * s, segments=6,
    )
    parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Tome", verts, faces, pages=pages, category="weapon")


# =========================================================================
# CATEGORY 5: ARCHITECTURAL DETAILS
# =========================================================================


def generate_gargoyle_mesh(
    pose: str = "crouching",
) -> MeshSpec:
    """Generate a wall-mounted gargoyle mesh.

    Args:
        pose: "crouching", "winged", or "screaming".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Body (hunched torso)
    body_r = 0.12
    bv, bf = _make_sphere(0, 0.15, 0.1, body_r, rings=6, sectors=8)
    parts.append((bv, bf))

    # Head
    head_r = 0.07
    hv, hf = _make_sphere(0, 0.28, 0.18, head_r, rings=5, sectors=6)
    parts.append((hv, hf))

    # Snout/jaw
    sv, sf = _make_tapered_cylinder(0, 0.24, 0.24, 0.04, 0.02, 0.06, 6, rings=1)
    parts.append((sv, sf))

    # Horns
    for side in [-1, 1]:
        horn_v, horn_f = _make_tapered_cylinder(
            side * 0.05, 0.32, 0.15,
            0.015, 0.005, 0.08, 5, rings=2,
        )
        parts.append((horn_v, horn_f))

    # Eyes (indentations)
    for side in [-1, 1]:
        ev, ef = _make_sphere(side * 0.03, 0.3, 0.22, 0.012, rings=3, sectors=4)
        parts.append((ev, ef))

    # Limbs (crouching legs)
    for side in [-1, 1]:
        # Upper leg
        ulv, ulf = _make_tapered_cylinder(
            side * 0.08, 0.05, 0.08,
            0.04, 0.03, 0.12, 6, rings=2,
        )
        parts.append((ulv, ulf))
        # Foot/claw
        fv, ff = _make_box(side * 0.08, 0, 0.12, 0.03, 0.02, 0.04)
        parts.append((fv, ff))
        # Arm
        av, af = _make_tapered_cylinder(
            side * 0.12, 0.18, 0.12,
            0.025, 0.02, 0.1, 6, rings=2,
        )
        parts.append((av, af))

    if pose == "winged":
        # Wings (thin triangular surfaces)
        for side in [-1, 1]:
            wing_verts = [
                (side * 0.12, 0.2, 0.05),   # Wing root
                (side * 0.35, 0.3, -0.05),   # Wing tip
                (side * 0.25, 0.1, -0.1),    # Lower edge
                (side * 0.12, 0.08, 0.0),    # Lower root
            ]
            wing_faces = [(0, 1, 2, 3)] if side > 0 else [(3, 2, 1, 0)]
            parts.append((wing_verts, wing_faces))

    elif pose == "screaming":
        # Open mouth
        mv, mf = _make_cylinder(0, 0.25, 0.25, 0.03, 0.03, segments=6)
        parts.append((mv, mf))

    # Wall mounting base
    bsv, bsf = _make_beveled_box(0, 0.12, -0.05, 0.1, 0.12, 0.05, bevel=0.008)
    parts.append((bsv, bsf))

    # Tail (curving around the base)
    for i in range(6):
        t = i / 6
        tx = math.sin(t * math.pi * 2) * 0.1
        ty = 0.05 + t * 0.02
        tz = -0.05 + math.cos(t * math.pi * 2) * 0.08
        tr = 0.015 * (1.0 - t * 0.6)
        tv, tf = _make_cylinder(tx, ty, tz, max(tr, 0.004), 0.03, segments=4,
                                cap_top=False, cap_bottom=False)
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gargoyle_{pose}", verts, faces, pose=pose, category="architecture")


def generate_fountain_mesh(
    tiers: int = 2,
    basin_size: float = 1.0,
) -> MeshSpec:
    """Generate a stone fountain mesh.

    Args:
        tiers: Number of basin tiers (1-3).
        basin_size: Size of the bottom basin.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    tiers = max(1, min(3, tiers))

    for tier in range(tiers):
        scale = 1.0 - tier * 0.35
        r = basin_size * 0.5 * scale
        y_offset = tier * basin_size * 0.4

        # Basin (bowl shape via lathe)
        basin_profile = [
            (r * 0.15, y_offset),
            (r * 0.2, y_offset + 0.02),
            (r * 0.8, y_offset + 0.03),
            (r, y_offset + 0.08),
            (r * 1.05, y_offset + 0.1),
            (r * 1.05, y_offset + 0.15),
            (r * 0.95, y_offset + 0.15),
            (r * 0.9, y_offset + 0.12),
            (r * 0.5, y_offset + 0.1),
        ]
        bv, bf = _make_lathe(basin_profile, segments=16)
        parts.append((bv, bf))

        # Pedestal for upper tiers
        if tier > 0:
            ped_r = r * 0.2
            ped_h = basin_size * 0.4
            prev_y = (tier - 1) * basin_size * 0.4 + 0.15
            pv, pf = _make_tapered_cylinder(
                0, prev_y, 0,
                ped_r * 1.2, ped_r, ped_h - 0.15,
                segments=8, rings=3,
            )
            parts.append((pv, pf))

    # Central spout on top
    top_y = (tiers - 1) * basin_size * 0.4 + 0.15
    spout_profile = [
        (0.03, top_y),
        (0.025, top_y + 0.1),
        (0.035, top_y + 0.2),
        (0.02, top_y + 0.25),
        (0.015, top_y + 0.3),
    ]
    sv, sf = _make_lathe(spout_profile, segments=8, close_top=True)
    parts.append((sv, sf))

    # Base platform
    base_r = basin_size * 0.55
    base_profile = [
        (base_r, -0.05),
        (base_r, 0),
        (base_r * 0.9, 0.01),
    ]
    bsv, bsf = _make_lathe(base_profile, segments=16, close_bottom=True)
    parts.append((bsv, bsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Fountain", verts, faces, tiers=tiers, category="architecture")


def generate_statue_mesh(
    pose: str = "standing",
    size: float = 1.0,
) -> MeshSpec:
    """Generate a generic humanoid statue mesh.

    Args:
        pose: "standing", "praying", or "warrior".
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Pedestal
    ped_h = 0.3 * s
    pv, pf = _make_beveled_box(0, ped_h / 2, 0, 0.25 * s, ped_h / 2, 0.25 * s,
                               bevel=0.015 * s)
    parts.append((pv, pf))

    # Torso
    torso_h = 0.5 * s
    torso_w = 0.15 * s
    tv, tf = _make_tapered_cylinder(0, ped_h, 0, torso_w, torso_w * 0.85,
                                    torso_h, segments=8, rings=4)
    parts.append((tv, tf))

    # Head
    head_r = 0.08 * s
    hv, hf = _make_sphere(0, ped_h + torso_h + head_r, 0,
                          head_r, rings=6, sectors=8)
    parts.append((hv, hf))

    # Legs
    leg_h = 0.4 * s  # Partly hidden by robe but still there
    leg_r = 0.05 * s
    for side in [-1, 1]:
        lx = side * 0.06 * s
        lv, lf = _make_tapered_cylinder(lx, ped_h - leg_h * 0.3, 0,
                                        leg_r, leg_r * 0.8,
                                        leg_h, segments=6, rings=2)
        parts.append((lv, lf))

    # Arms
    arm_r = 0.035 * s
    arm_h = 0.4 * s
    if pose == "standing":
        for side in [-1, 1]:
            ax = side * (torso_w + 0.01 * s)
            av, af = _make_tapered_cylinder(ax, ped_h + torso_h * 0.3, 0,
                                            arm_r, arm_r * 0.7,
                                            arm_h, segments=6, rings=2)
            parts.append((av, af))

    elif pose == "praying":
        # Arms together in front
        for side in [-1, 1]:
            ax = side * 0.04 * s
            av, af = _make_tapered_cylinder(ax, ped_h + torso_h * 0.4, 0.08 * s,
                                            arm_r, arm_r * 0.7,
                                            arm_h * 0.6, segments=6, rings=2)
            parts.append((av, af))

    elif pose == "warrior":
        # One arm raised with weapon
        # Right arm raised
        av, af = _make_tapered_cylinder(torso_w + 0.01 * s, ped_h + torso_h * 0.6, 0,
                                        arm_r, arm_r * 0.7,
                                        arm_h * 0.7, segments=6, rings=2)
        parts.append((av, af))
        # Sword in hand
        sv, sf = _make_cylinder(torso_w + 0.02 * s,
                                ped_h + torso_h * 0.6 + arm_h * 0.6, 0,
                                0.008 * s, 0.4 * s, segments=4)
        parts.append((sv, sf))
        # Left arm with shield
        av2, af2 = _make_tapered_cylinder(-torso_w - 0.01 * s, ped_h + torso_h * 0.35,
                                          0.05 * s,
                                          arm_r, arm_r * 0.7,
                                          arm_h * 0.5, segments=6, rings=2)
        parts.append((av2, af2))
        # Shield disc
        shv, shf = _make_cylinder(-torso_w - 0.03 * s,
                                  ped_h + torso_h * 0.35, 0.08 * s,
                                  0.1 * s, 0.01 * s, segments=8)
        parts.append((shv, shf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Statue_{pose}", verts, faces, pose=pose, category="architecture")


def generate_bridge_mesh(
    span: float = 6.0,
    width: float = 2.0,
    style: str = "stone_arch",
) -> MeshSpec:
    """Generate a bridge mesh.

    Args:
        span: Bridge length.
        width: Bridge width.
        style: "stone_arch", "rope", or "drawbridge".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "stone_arch":
        # Arch curve underneath
        arch_segs = 16
        arch_h = span * 0.25
        deck_thick = 0.15
        wall_h = 0.5

        # Deck surface (slightly curved)
        deck_verts: list[tuple[float, float, float]] = []
        deck_faces: list[tuple[int, ...]] = []
        for i in range(arch_segs + 1):
            t = i / arch_segs
            z = -span / 2 + t * span
            y_arch = math.sin(t * math.pi) * arch_h * 0.1  # Slight crown
            # Inner left, outer left, outer right, inner right
            deck_verts.append((-width / 2, y_arch, z))
            deck_verts.append((-width / 2, y_arch - deck_thick, z))
            deck_verts.append((width / 2, y_arch - deck_thick, z))
            deck_verts.append((width / 2, y_arch, z))

        for i in range(arch_segs):
            b = i * 4
            # Top surface
            deck_faces.append((b + 0, b + 3, b + 7, b + 4))
            # Bottom surface
            deck_faces.append((b + 1, b + 5, b + 6, b + 2))
            # Left side
            deck_faces.append((b + 0, b + 4, b + 5, b + 1))
            # Right side
            deck_faces.append((b + 3, b + 2, b + 6, b + 7))

        parts.append((deck_verts, deck_faces))

        # Arch ribs (curved supports underneath)
        for x_pos in [-width * 0.4, 0, width * 0.4]:
            arch_v: list[tuple[float, float, float]] = []
            arch_f: list[tuple[int, ...]] = []
            rib_thick = 0.08
            for i in range(arch_segs + 1):
                t = i / arch_segs
                z = -span / 2 + t * span
                y = -math.sin(t * math.pi) * arch_h
                arch_v.append((x_pos - rib_thick / 2, y, z))
                arch_v.append((x_pos + rib_thick / 2, y, z))
                arch_v.append((x_pos + rib_thick / 2, y - rib_thick, z))
                arch_v.append((x_pos - rib_thick / 2, y - rib_thick, z))

            for i in range(arch_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    arch_f.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            parts.append((arch_v, arch_f))

        # Side walls/railings
        for x_side in [-width / 2, width / 2]:
            wv, wf = _make_box(x_side, wall_h / 2, 0,
                               0.06, wall_h / 2, span / 2)
            parts.append((wv, wf))

    elif style == "rope":
        # Plank walkway with rope sides
        plank_count = int(span / 0.15)
        plank_w = width * 0.9
        plank_thick = 0.03
        plank_d = 0.12

        for i in range(plank_count):
            z = -span / 2 + i * span / plank_count
            # Slight sag in the middle
            t = (z + span / 2) / span
            sag = -math.sin(t * math.pi) * span * 0.05
            pv, pf = _make_box(0, sag, z, plank_w / 2, plank_thick / 2, plank_d / 2)
            parts.append((pv, pf))

        # Rope handrails
        rope_r = 0.015
        rope_h = 0.7
        for x_side in [-width / 2, width / 2]:
            for i in range(plank_count // 2):
                z = -span / 2 + i * 2 * span / plank_count
                t = (z + span / 2) / span
                sag = -math.sin(t * math.pi) * span * 0.05
                # Vertical rope post
                pv, pf = _make_cylinder(x_side, sag, z, rope_r * 2, rope_h,
                                        segments=4)
                parts.append((pv, pf))

    else:  # drawbridge
        # Thick wooden bridge deck
        deck_thick = 0.12
        dv, df = _make_beveled_box(0, -deck_thick / 2, 0,
                                   width / 2, deck_thick / 2, span / 2,
                                   bevel=0.015)
        parts.append((dv, df))

        # Plank lines (surface detail)
        plank_count = int(width / 0.2)
        for i in range(plank_count):
            x = -width / 2 + (i + 0.5) * width / plank_count
            lv, lf = _make_box(x, 0.005, 0, 0.003, 0.005, span / 2 - 0.02)
            parts.append((lv, lf))

        # Chain attachments at the end
        for x_side in [-width * 0.4, width * 0.4]:
            rv, rf = _make_torus_ring(x_side, 0.05, span / 2 - 0.05,
                                      0.03, 0.008,
                                      major_segments=6, minor_segments=3)
            parts.append((rv, rf))

        # Hinge mounts at near end
        for x_side in [-width * 0.4, width * 0.4]:
            hv, hf = _make_cylinder(x_side, 0, -span / 2,
                                    0.02, 0.04, segments=6)
            parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bridge_{style}", verts, faces, style=style, category="architecture")


def generate_gate_mesh(
    width: float = 2.0,
    height: float = 3.0,
    style: str = "portcullis",
) -> MeshSpec:
    """Generate a gate mesh.

    Args:
        width: Gate width.
        height: Gate height.
        style: "portcullis", "wooden_double", or "iron_grid".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "portcullis":
        bar_r = 0.02
        bar_segs = 6
        h_spacing = width / 8
        v_spacing = height / 6

        # Vertical bars
        for i in range(9):
            x = -width / 2 + i * h_spacing
            bv, bf = _make_cylinder(x, 0, 0, bar_r, height, segments=bar_segs)
            parts.append((bv, bf))

        # Horizontal bars
        for i in range(7):
            y = i * v_spacing
            hv, hf = _make_cylinder(-width / 2, y, 0, bar_r * 0.8, width,
                                    segments=bar_segs)
            # Rotate to horizontal
            h_verts = [(v[1] - y + (-width / 2), y, v[2]) for v in hv]
            parts.append((h_verts, hf))

        # Bottom spikes
        for i in range(9):
            x = -width / 2 + i * h_spacing
            sv, sf = _make_cone(x, -0.01, 0, bar_r * 1.5, 0.08, segments=4)
            # Point downward by flipping
            sv_down = [(v[0], -v[1], v[2]) for v in sv]
            parts.append((sv_down, sf))

    elif style == "wooden_double":
        door_thick = 0.06
        # Left door
        ldv, ldf = _make_beveled_box(
            -width / 4, height / 2, 0,
            width / 4 - 0.01, height / 2, door_thick / 2,
            bevel=0.01,
        )
        parts.append((ldv, ldf))
        # Right door
        rdv, rdf = _make_beveled_box(
            width / 4, height / 2, 0,
            width / 4 - 0.01, height / 2, door_thick / 2,
            bevel=0.01,
        )
        parts.append((rdv, rdf))

        # Plank lines
        plank_w = width / 2 / 5
        for door_side in [-1, 1]:
            for i in range(5):
                x = door_side * (width / 4) - width / 4 + (i + 0.5) * plank_w
                if door_side == 1:
                    x = door_side * (width / 4) - width / 4 + width / 2 + (i + 0.5) * plank_w
                pv, pf = _make_box(
                    door_side * (i * plank_w + plank_w / 2 + 0.01),
                    height / 2,
                    door_thick / 2 + 0.002,
                    0.003, height / 2 - 0.02, 0.002,
                )
                parts.append((pv, pf))

        # Iron bands
        for band_y in [height * 0.2, height * 0.5, height * 0.8]:
            bv, bf = _make_box(0, band_y, door_thick / 2 + 0.003,
                               width / 2, 0.015, 0.003)
            parts.append((bv, bf))

        # Large ring handles
        for side in [-1, 1]:
            rv, rf = _make_torus_ring(
                side * width / 4, height * 0.45, door_thick / 2 + 0.015,
                0.04, 0.008,
                major_segments=8, minor_segments=4,
            )
            parts.append((rv, rf))

        # Hinges
        for y_pos in [height * 0.2, height * 0.8]:
            for x_side in [-width / 2, width / 2]:
                hv, hf = _make_cylinder(x_side, y_pos, 0,
                                        0.015, 0.08, segments=6)
                parts.append((hv, hf))

    else:  # iron_grid
        bar_r = 0.015
        bar_segs = 6
        grid_spacing = 0.15

        # Grid bars
        h_bars = int(width / grid_spacing) + 1
        v_bars = int(height / grid_spacing) + 1

        for i in range(h_bars):
            x = -width / 2 + i * grid_spacing
            bv, bf = _make_cylinder(x, 0, 0, bar_r, height, segments=bar_segs)
            parts.append((bv, bf))

        for i in range(v_bars):
            y = i * grid_spacing
            hv, hf = _make_cylinder(-width / 2, y, 0, bar_r, width,
                                    segments=bar_segs)
            h_verts = [(v[1] - y + (-width / 2), y, v[2]) for v in hv]
            parts.append((h_verts, hf))

        # Frame
        frame_w = 0.05
        for x_side in [-width / 2 - frame_w / 2, width / 2 + frame_w / 2]:
            fv, ff = _make_beveled_box(x_side, height / 2, 0,
                                       frame_w / 2, height / 2, frame_w / 2,
                                       bevel=0.005)
            parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gate_{style}", verts, faces, style=style, category="architecture")


def generate_staircase_mesh(
    steps: int = 12,
    width: float = 1.0,
    direction: str = "straight",
) -> MeshSpec:
    """Generate a staircase mesh.

    Args:
        steps: Number of steps.
        width: Step width.
        direction: "straight" or "spiral".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    step_h = 0.18
    step_d = 0.28

    if direction == "straight":
        for i in range(steps):
            y = i * step_h
            z = i * step_d
            sv, sf = _make_beveled_box(
                0, y + step_h / 2, z,
                width / 2, step_h / 2, step_d / 2,
                bevel=0.005,
            )
            parts.append((sv, sf))

        # Side stringers (support beams)
        total_rise = steps * step_h
        total_run = steps * step_d
        stringer_len = math.sqrt(total_rise ** 2 + total_run ** 2)
        for x_side in [-width / 2 - 0.02, width / 2 + 0.02]:
            # Approximate with a box along the diagonal
            sv, sf = _make_box(
                x_side,
                total_rise / 2 - step_h / 2,
                total_run / 2 - step_d / 2,
                0.02, total_rise / 2, total_run / 2,
            )
            parts.append((sv, sf))

    else:  # spiral
        center_r = 0.1
        outer_r = center_r + width
        angle_per_step = math.pi * 2 / max(steps, 4) * 1.2  # Slightly more than full turn

        # Central pillar
        total_h = steps * step_h
        pv, pf = _make_cylinder(0, 0, 0, center_r, total_h + step_h,
                                segments=12)
        parts.append((pv, pf))

        for i in range(steps):
            y = i * step_h
            angle = i * angle_per_step

            # Pie-slice shaped step
            step_verts: list[tuple[float, float, float]] = []
            step_faces_local: list[tuple[int, ...]] = []

            n_arc = 5
            # Top surface
            step_verts.append((0, y + step_h, 0))  # Center
            for j in range(n_arc + 1):
                a = angle + j * angle_per_step / n_arc
                step_verts.append((
                    math.cos(a) * outer_r,
                    y + step_h,
                    math.sin(a) * outer_r,
                ))
            # Bottom surface
            step_verts.append((0, y, 0))  # Center bottom
            for j in range(n_arc + 1):
                a = angle + j * angle_per_step / n_arc
                step_verts.append((
                    math.cos(a) * outer_r,
                    y,
                    math.sin(a) * outer_r,
                ))

            top_center = 0
            bot_center = n_arc + 2
            # Top fan
            for j in range(n_arc):
                step_faces_local.append((top_center, j + 1, j + 2))
            # Bottom fan (reversed winding)
            for j in range(n_arc):
                step_faces_local.append((bot_center, bot_center + j + 2, bot_center + j + 1))
            # Front riser
            step_faces_local.append((top_center, bot_center, bot_center + 1, 1))
            # Outer rim
            for j in range(n_arc):
                t = j + 1
                b = bot_center + j + 1
                step_faces_local.append((t, b, b + 1, t + 1))
            # Back riser
            step_faces_local.append((n_arc + 1, bot_center + n_arc + 1, bot_center, top_center))

            parts.append((step_verts, step_faces_local))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Staircase_{direction}", verts, faces,
                        direction=direction, category="architecture")


# =========================================================================
# Registry: all generators by category
# =========================================================================

GENERATORS = {
    "furniture": {
        "table": generate_table_mesh,
        "chair": generate_chair_mesh,
        "shelf": generate_shelf_mesh,
        "chest": generate_chest_mesh,
        "barrel": generate_barrel_mesh,
        "candelabra": generate_candelabra_mesh,
        "bookshelf": generate_bookshelf_mesh,
    },
    "vegetation": {
        "tree": generate_tree_mesh,
        "rock": generate_rock_mesh,
        "mushroom": generate_mushroom_mesh,
        "root": generate_root_mesh,
        "ivy": generate_ivy_mesh,
    },
    "dungeon_prop": {
        "torch_sconce": generate_torch_sconce_mesh,
        "prison_door": generate_prison_door_mesh,
        "sarcophagus": generate_sarcophagus_mesh,
        "altar": generate_altar_mesh,
        "pillar": generate_pillar_mesh,
        "archway": generate_archway_mesh,
        "chain": generate_chain_mesh,
        "skull_pile": generate_skull_pile_mesh,
    },
    "weapon": {
        "hammer": generate_hammer_mesh,
        "spear": generate_spear_mesh,
        "crossbow": generate_crossbow_mesh,
        "scythe": generate_scythe_mesh,
        "flail": generate_flail_mesh,
        "whip": generate_whip_mesh,
        "claw": generate_claw_mesh,
        "tome": generate_tome_mesh,
    },
    "architecture": {
        "gargoyle": generate_gargoyle_mesh,
        "fountain": generate_fountain_mesh,
        "statue": generate_statue_mesh,
        "bridge": generate_bridge_mesh,
        "gate": generate_gate_mesh,
        "staircase": generate_staircase_mesh,
    },
}
