"""Riggable environmental object generators for VeilBreakers dark fantasy assets.

Provides generators for environmental objects with proper articulation points,
pivot empties, vertex groups, and topology suitable for rigging and physics
simulation.  Every generator returns a dict with:

    vertices   -- list of (x, y, z) tuples
    faces      -- list of index tuples (quads where possible)
    uvs        -- list of (u, v) per vertex
    empties    -- dict mapping empty name -> (x, y, z) position
    vertex_groups -- dict mapping group name -> list of vertex indices
    metadata   -- name, poly_count, vertex_count, dimensions, rig_info, category

All functions are pure Python with math-only dependencies (no bpy/bmesh).

Categories:
- DOORS: wooden_plank, iron_bound, dungeon_gate, portcullis,
         double_door, barn_door, castle_gate, secret_passage
- CHAINS: interlocking torus-link chains with per-link groups
- FLAGS/BANNERS: banner, pennant, gonfalon, standard, tattered
- TREASURE CHESTS: wooden, iron_bound, ornate_gold, skeleton_coffin,
                   mimic, barrel_stash
- CHANDELIERS: iron_ring, candelabra, bone_chandelier, cage_lantern
- DRAWBRIDGES: planked drawbridge with hinge and chain points
- ROPE BRIDGES: catenary-draped planked bridges with side ropes
- HANGING SIGNS: wall-mounted swinging signs with bracket
- WINDMILLS: tower + rotating blade assembly with cloth panels
- CAGES: hanging_cage, prison_cell, gibbet, animal_trap
"""

from __future__ import annotations

import math
import random as _rng
from typing import Any

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# =========================================================================
# Utility helpers
# =========================================================================

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


def _make_riggable_result(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    empties: dict[str, tuple[float, float, float]] | None = None,
    vertex_groups: dict[str, list[int]] | None = None,
    rig_info: dict[str, Any] | None = None,
    **extra_meta: Any,
) -> MeshSpec:
    """Package vertices/faces/empties/groups into a riggable mesh spec."""
    dims = _compute_dimensions(vertices)
    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs or [],
        "empties": empties or {},
        "vertex_groups": vertex_groups or {},
        "metadata": {
            "name": name,
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "dimensions": dims,
            "rig_info": rig_info or {},
            **extra_meta,
        },
    }


def _merge_parts(
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


def _merge_parts_tracked(
    *parts: tuple[list[tuple[float, float, float]], list[tuple[int, ...]]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[int, int]]]:
    """Merge parts and track (start_index, end_index) of each part's verts."""
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    ranges: list[tuple[int, int]] = []
    for verts, faces in parts:
        offset = len(all_verts)
        ranges.append((offset, offset + len(verts)))
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces, ranges


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Axis-aligned box centred at (cx, cy, cz) with half-sizes sx, sy, sz."""
    verts = [
        (cx - sx, cy - sy, cz - sz),
        (cx + sx, cy - sy, cz - sz),
        (cx + sx, cy + sy, cz - sz),
        (cx - sx, cy + sy, cz - sz),
        (cx - sx, cy - sy, cz + sz),
        (cx + sx, cy - sy, cz + sz),
        (cx + sx, cy + sy, cz + sz),
        (cx - sx, cy + sy, cz + sz),
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
    """Cylinder along Y axis."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(a) * radius, cy_bottom, cz + math.sin(a) * radius))
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(a) * radius, cy_bottom + height, cz + math.sin(a) * radius))
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((i, i2, segments + i2, segments + i))
    if cap_bottom:
        faces.append(tuple(range(segments - 1, -1, -1)))
    if cap_top:
        faces.append(tuple(segments + i for i in range(segments)))
    return verts, faces


def _make_torus(
    cx: float, cy: float, cz: float,
    major_r: float, minor_r: float,
    major_seg: int = 16, minor_seg: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Torus lying in the XZ plane at height cy."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(major_seg):
        theta = 2.0 * math.pi * i / major_seg
        ct, st = math.cos(theta), math.sin(theta)
        tcx = cx + major_r * ct
        tcz = cz + major_r * st
        for j in range(minor_seg):
            phi = 2.0 * math.pi * j / minor_seg
            cp, sp = math.cos(phi), math.sin(phi)
            r = major_r + minor_r * cp
            verts.append((
                cx + r * ct,
                cy + minor_r * sp,
                cz + r * st,
            ))
    for i in range(major_seg):
        i_next = (i + 1) % major_seg
        for j in range(minor_seg):
            j_next = (j + 1) % minor_seg
            v0 = i * minor_seg + j
            v1 = i * minor_seg + j_next
            v2 = i_next * minor_seg + j_next
            v3 = i_next * minor_seg + j
            faces.append((v0, v3, v2, v1))
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
    for r in range(1, rings):
        phi = math.pi * r / rings
        sp, cp = math.sin(phi), math.cos(phi)
        for s in range(sectors):
            theta = 2.0 * math.pi * s / sectors
            verts.append((
                cx + radius * sp * math.cos(theta),
                cy - radius * cp,
                cz + radius * sp * math.sin(theta),
            ))
    verts.append((cx, cy + radius, cz))
    # Bottom cap triangles
    for s in range(sectors):
        s2 = (s + 1) % sectors
        faces.append((0, 1 + s2, 1 + s))
    # Middle quads
    for r in range(rings - 2):
        for s in range(sectors):
            s2 = (s + 1) % sectors
            base = 1 + r * sectors
            faces.append((base + s, base + s2, base + sectors + s2, base + sectors + s))
    # Top cap triangles
    top = len(verts) - 1
    base = 1 + (rings - 2) * sectors
    for s in range(sectors):
        s2 = (s + 1) % sectors
        faces.append((base + s, top, base + s2))
    return verts, faces


# ---------------------------------------------------------------------------
# Plank row helper
# ---------------------------------------------------------------------------

def _plank_row(
    count: int,
    total_width: float,
    height: float,
    gap: float = 0.003,
    thickness: float = 0.03,
    y_offset: float = 0.0,
    z_offset: float = 0.0,
    height_variation: float = 0.0,
    seed: int = 42,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]], list[tuple[int, int]]]:
    """Generate a row of wooden planks with gaps.

    Returns (verts, faces, uvs, plank_ranges) where plank_ranges is
    a list of (start_vert_idx, end_vert_idx) per plank.
    """
    rng = _rng.Random(seed)
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[tuple[float, float]] = []
    plank_ranges: list[tuple[int, int]] = []

    usable = total_width - gap * (count - 1)
    plank_w = usable / count
    half_t = thickness / 2.0

    x_cursor = -total_width / 2.0

    for pi in range(count):
        h_var = rng.uniform(-height_variation, height_variation) if height_variation > 0 else 0.0
        pw = plank_w
        ph = height + h_var
        start = len(all_verts)

        # 8 vertices per plank (a box)
        x0 = x_cursor
        x1 = x_cursor + pw
        y0 = y_offset
        y1 = y_offset + ph
        z0 = z_offset - half_t
        z1 = z_offset + half_t

        all_verts.extend([
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
        ])
        b = start
        all_faces.extend([
            (b+0, b+3, b+2, b+1),  # front
            (b+4, b+5, b+6, b+7),  # back
            (b+0, b+1, b+5, b+4),  # bottom
            (b+2, b+3, b+7, b+6),  # top
            (b+0, b+4, b+7, b+3),  # left
            (b+1, b+2, b+6, b+5),  # right
        ])
        # UV: map front face of each plank to its portion of UV space
        u0 = pi / count
        u1 = (pi + 1) / count
        for _ in range(8):
            all_uvs.append((
                rng.uniform(u0, u1),
                rng.uniform(0.0, 1.0),
            ))
        plank_ranges.append((start, start + 8))
        x_cursor += pw + gap

    return all_verts, all_faces, all_uvs, plank_ranges


# ---------------------------------------------------------------------------
# Torus link helper (for chains)
# ---------------------------------------------------------------------------

def _torus_link(
    cx: float, cy: float, cz: float,
    major_r: float, minor_r: float,
    orientation: int = 0,
    segments: int = 12,
    tube_seg: int = 6,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a single chain link as a rounded-rectangle torus.

    orientation=0: link lies in XY plane (hangs vertically, wide in X)
    orientation=1: link lies in YZ plane (rotated 90 deg, wide in Z)

    The link is an elongated torus: stretched along one axis for the
    classic oblong chain-link shape.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Elongation makes it an oblong link (not a perfect circle)
    stretch = major_r * 0.5  # half the straight segment length

    total_path = segments
    for i in range(total_path):
        t = i / total_path
        # Parameterise: 4 segments of the oblong path
        # top arc -> right straight -> bottom arc -> left straight
        frac = t * 4.0
        if frac < 1.0:
            # Top arc (semicircle)
            a = math.pi * frac
            px = math.cos(a) * major_r
            py = stretch + math.sin(a) * major_r
        elif frac < 2.0:
            # Right straight section
            f = frac - 1.0
            px = -major_r
            py = stretch * (1.0 - 2.0 * f)
        elif frac < 3.0:
            # Bottom arc (semicircle)
            a = math.pi * (frac - 2.0)
            px = -math.cos(a) * major_r
            py = -stretch - math.sin(a) * major_r
        else:
            # Left straight section
            f = frac - 3.0
            px = major_r
            py = -stretch * (1.0 - 2.0 * f)

        # Compute tangent for tube orientation
        dt = 1.0 / total_path
        t2 = t + dt
        frac2 = t2 * 4.0
        if frac2 < 1.0:
            a2 = math.pi * frac2
            nx = math.cos(a2) * major_r
            ny = stretch + math.sin(a2) * major_r
        elif frac2 < 2.0:
            f2 = frac2 - 1.0
            nx = -major_r
            ny = stretch * (1.0 - 2.0 * f2)
        elif frac2 < 3.0:
            a2 = math.pi * (frac2 - 2.0)
            nx = -math.cos(a2) * major_r
            ny = -stretch - math.sin(a2) * major_r
        else:
            f2 = frac2 - 3.0
            nx = major_r
            ny = -stretch * (1.0 - 2.0 * f2)

        dx = nx - px
        dy = ny - py
        dl = math.sqrt(dx * dx + dy * dy) or 1e-9
        dx /= dl
        dy /= dl
        # Normal perpendicular to tangent in 2D: (-dy, dx)
        perp_x = -dy
        perp_y = dx

        for j in range(tube_seg):
            phi = 2.0 * math.pi * j / tube_seg
            cp, sp = math.cos(phi), math.sin(phi)
            # offset in the plane perpendicular to path
            offset_in_plane = minor_r * cp
            offset_z = minor_r * sp

            lx = px + perp_x * offset_in_plane
            ly = py + perp_y * offset_in_plane
            lz = offset_z

            # Apply orientation
            if orientation == 0:
                # XY plane: link wide in X, tall in Y
                verts.append((cx + lx, cy + ly, cz + lz))
            else:
                # YZ plane: link wide in Z, tall in Y
                verts.append((cx + lz, cy + ly, cz + lx))

    # Faces
    for i in range(total_path):
        i_next = (i + 1) % total_path
        for j in range(tube_seg):
            j_next = (j + 1) % tube_seg
            v0 = i * tube_seg + j
            v1 = i * tube_seg + j_next
            v2 = i_next * tube_seg + j_next
            v3 = i_next * tube_seg + j
            faces.append((v0, v3, v2, v1))

    return verts, faces


# ---------------------------------------------------------------------------
# Catenary curve helper
# ---------------------------------------------------------------------------

def _catenary_curve(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    sag: float,
    num_points: int,
) -> list[tuple[float, float, float]]:
    """Compute catenary curve between two 3D points.

    Uses a parabolic approximation of a catenary which is visually
    indistinguishable for typical game distances.

    Returns list of num_points positions from start to end.
    """
    points: list[tuple[float, float, float]] = []
    for i in range(num_points):
        t = i / max(num_points - 1, 1)
        # Linear interpolation
        x = start[0] + (end[0] - start[0]) * t
        y = start[1] + (end[1] - start[1]) * t
        z = start[2] + (end[2] - start[2]) * t
        # Parabolic sag: maximum at t=0.5
        droop = -sag * 4.0 * t * (1.0 - t)
        y += droop
        points.append((x, y, z))
    return points


# ---------------------------------------------------------------------------
# Iron strap helper
# ---------------------------------------------------------------------------

def _iron_strap(
    x0: float, y0: float, z0: float,
    x1: float, y1: float, z1: float,
    width: float = 0.03,
    thickness: float = 0.005,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a decorative iron strap/binding strip between two points."""
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    if length < 1e-9:
        return [], []

    # Normalise direction
    dx /= length
    dy /= length
    dz /= length

    # Find perpendicular vectors
    if abs(dy) < 0.99:
        up = (0.0, 1.0, 0.0)
    else:
        up = (1.0, 0.0, 0.0)
    # Cross product: direction x up
    px = dy * up[2] - dz * up[1]
    py = dz * up[0] - dx * up[2]
    pz = dx * up[1] - dy * up[0]
    pl = math.sqrt(px*px + py*py + pz*pz) or 1e-9
    px /= pl
    py /= pl
    pz /= pl
    # Second perp: direction x first_perp
    qx = dy * pz - dz * py
    qy = dz * px - dx * pz
    qz = dx * py - dy * px

    hw = width / 2.0
    ht = thickness / 2.0

    verts = []
    for (bx, by, bz) in [(x0, y0, z0), (x1, y1, z1)]:
        verts.append((bx - px*hw - qx*ht, by - py*hw - qy*ht, bz - pz*hw - qz*ht))
        verts.append((bx + px*hw - qx*ht, by + py*hw - qy*ht, bz + pz*hw - qz*ht))
        verts.append((bx + px*hw + qx*ht, by + py*hw + qy*ht, bz + pz*hw + qz*ht))
        verts.append((bx - px*hw + qx*ht, by - py*hw + qy*ht, bz - pz*hw + qz*ht))

    faces = [
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
        (0, 3, 2, 1),
        (4, 5, 6, 7),
    ]
    return verts, faces


# ---------------------------------------------------------------------------
# Rivet/stud helper
# ---------------------------------------------------------------------------

def _rivet(
    cx: float, cy: float, cz: float,
    radius: float = 0.006,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Small dome rivet (half sphere)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    sectors = 6
    rings = 3
    # Base centre
    verts.append((cx, cy, cz))
    for r in range(1, rings + 1):
        phi = (math.pi / 2.0) * r / rings
        sp, cp = math.sin(phi), math.cos(phi)
        for s in range(sectors):
            theta = 2.0 * math.pi * s / sectors
            verts.append((
                cx + radius * cp * math.cos(theta),
                cy + radius * cp * math.sin(theta),
                cz + radius * sp,
            ))
    # Top point
    verts.append((cx, cy, cz + radius))
    # Base fan
    for s in range(sectors):
        s2 = (s + 1) % sectors
        faces.append((0, 1 + s, 1 + s2))
    # Middle quads
    for r in range(rings - 1):
        for s in range(sectors):
            s2 = (s + 1) % sectors
            base = 1 + r * sectors
            faces.append((base + s, base + sectors + s, base + sectors + s2, base + s2))
    # Top fan
    top = len(verts) - 1
    base = 1 + (rings - 1) * sectors
    for s in range(sectors):
        s2 = (s + 1) % sectors
        faces.append((base + s, top, base + s2))
    return verts, faces


# ---------------------------------------------------------------------------
# UV helpers
# ---------------------------------------------------------------------------

def _generate_box_uvs(count: int) -> list[tuple[float, float]]:
    """Generate simple per-vertex UVs for box-based geometry."""
    uvs: list[tuple[float, float]] = []
    for i in range(count):
        # Simple planar projection
        uvs.append(((i % 4) / 3.0, (i // 4) / max((count // 4) - 1, 1)))
    return uvs


def _generate_planar_uvs(
    verts: list[tuple[float, float, float]],
    axis: str = "xz",
    scale: float = 1.0,
) -> list[tuple[float, float]]:
    """Generate UVs via planar projection along specified axes."""
    uvs: list[tuple[float, float]] = []
    if not verts:
        return uvs
    if axis == "xz":
        xs = [v[0] for v in verts]
        zs = [v[2] for v in verts]
    elif axis == "xy":
        xs = [v[0] for v in verts]
        zs = [v[1] for v in verts]
    else:  # yz
        xs = [v[1] for v in verts]
        zs = [v[2] for v in verts]

    x_min, x_max = min(xs), max(xs)
    z_min, z_max = min(zs), max(zs)
    x_range = (x_max - x_min) or 1.0
    z_range = (z_max - z_min) or 1.0

    for i in range(len(verts)):
        u = (xs[i] - x_min) / x_range * scale
        v = (zs[i] - z_min) / z_range * scale
        uvs.append((max(0.0, min(1.0, u)), max(0.0, min(1.0, v))))
    return uvs


# =========================================================================
# 1. DOORS
# =========================================================================

def generate_door(
    style: str = "wooden_plank",
    width: float = 1.0,
    height: float = 2.0,
    thickness: float = 0.06,
) -> MeshSpec:
    """Generate a door with hinge empties and proper pivot points.

    Styles: wooden_plank, iron_bound, dungeon_gate, portcullis,
            double_door, barn_door, castle_gate, secret_passage

    Features:
    - Individual plank boards with gaps and random height variation
    - Iron bindings/straps for iron_bound
    - Frame with threshold and lintel
    - Hinge empties at top/bottom of hinge side
    - Vertex groups for hinge, panel, frame
    - Portcullis: vertical bars with cross-bars (slides vertically)
    - Double door: two panels with independent hinges
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}
    all_uvs: list[tuple[float, float]] = []
    rig_info: dict[str, Any] = {"type": "door", "style": style}

    half_w = width / 2.0
    half_t = thickness / 2.0
    frame_w = 0.08  # frame member width
    frame_d = thickness + 0.02

    # ----- FRAME (common to most styles) -----
    frame_verts: list[tuple[float, float, float]] = []
    frame_faces: list[tuple[int, ...]] = []

    if style != "portcullis":
        # Left jamb
        lj_v, lj_f = _make_box(-half_w - frame_w / 2, height / 2, 0,
                                frame_w / 2, height / 2, frame_d / 2)
        # Right jamb
        rj_v, rj_f = _make_box(half_w + frame_w / 2, height / 2, 0,
                                frame_w / 2, height / 2, frame_d / 2)
        # Lintel (top)
        lt_v, lt_f = _make_box(0, height + frame_w / 2, 0,
                                half_w + frame_w, frame_w / 2, frame_d / 2)
        # Threshold (bottom)
        th_v, th_f = _make_box(0, -frame_w / 4, 0,
                                half_w + frame_w, frame_w / 4, frame_d / 2)
        frame_verts, frame_faces, _ = _merge_parts_tracked(
            (lj_v, lj_f), (rj_v, rj_f), (lt_v, lt_f), (th_v, th_f)
        )

    frame_offset = 0
    frame_count = len(frame_verts)
    frame_indices = list(range(frame_offset, frame_offset + frame_count))

    # ----- DOOR PANEL(S) -----
    if style in ("wooden_plank", "iron_bound", "barn_door", "secret_passage"):
        plank_count = max(4, int(width / 0.15))
        pv, pf, p_uvs, p_ranges = _plank_row(
            plank_count, width, height,
            gap=0.004, thickness=thickness,
            height_variation=0.02 if style != "secret_passage" else 0.0,
            seed=101,
        )
        panel_offset = frame_count
        panel_indices = list(range(panel_offset, panel_offset + len(pv)))

        all_parts_verts = frame_verts + pv
        all_parts_faces = frame_faces[:]
        for f in pf:
            all_parts_faces.append(tuple(idx + frame_count for idx in f))
        all_uvs = _generate_planar_uvs(frame_verts, "xy") + p_uvs

        # Iron bindings for iron_bound style
        if style == "iron_bound":
            strap_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
            strap_count = 3
            for si in range(strap_count):
                sy = height * (si + 1) / (strap_count + 1)
                sv, sf = _iron_strap(
                    -half_w, sy, half_t + 0.002,
                    half_w, sy, half_t + 0.002,
                    width=0.04, thickness=0.006,
                )
                strap_parts.append((sv, sf))
                # Add rivets at strap ends
                for rx in [-half_w + 0.05, half_w - 0.05]:
                    rv, rf = _rivet(rx, sy, half_t + 0.008, radius=0.008)
                    strap_parts.append((rv, rf))
            strap_v, strap_f, _ = _merge_parts_tracked(*strap_parts)
            strap_offset = len(all_parts_verts)
            all_parts_verts.extend(strap_v)
            for f in strap_f:
                all_parts_faces.append(tuple(idx + strap_offset for idx in f))
            all_uvs.extend(_generate_planar_uvs(strap_v, "xy"))
            # Add strap verts to panel group
            panel_indices.extend(range(strap_offset, strap_offset + len(strap_v)))

        # Barn door: cross brace
        if style == "barn_door":
            brace_v, brace_f = _iron_strap(
                -half_w + 0.05, height * 0.15, -half_t - 0.005,
                half_w - 0.05, height * 0.85, -half_t - 0.005,
                width=0.06, thickness=0.02,
            )
            bo = len(all_parts_verts)
            all_parts_verts.extend(brace_v)
            for f in brace_f:
                all_parts_faces.append(tuple(idx + bo for idx in f))
            all_uvs.extend(_generate_planar_uvs(brace_v, "xy"))
            panel_indices.extend(range(bo, bo + len(brace_v)))

        # Hinges
        hinge_x = -half_w
        empties["hinge_top"] = (hinge_x, height * 0.85, 0.0)
        empties["hinge_bottom"] = (hinge_x, height * 0.15, 0.0)
        empties["hinge_axis"] = (hinge_x, 0.0, 0.0)
        rig_info["hinge_side"] = "left"
        rig_info["rotation_axis"] = "Y"

        # Hinge vertex group: verts near hinge axis
        hinge_indices = []
        for vi, v in enumerate(all_parts_verts):
            if abs(v[0] - hinge_x) < 0.05:
                hinge_indices.append(vi)

        vertex_groups["hinge"] = hinge_indices
        vertex_groups["panel"] = panel_indices
        vertex_groups["frame"] = frame_indices

        final_verts = all_parts_verts
        final_faces = all_parts_faces

    elif style == "portcullis":
        # Vertical bars with cross-bars -- slides vertically
        bar_r = 0.015
        bar_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
        bar_count = max(5, int(width / 0.12))
        bar_spacing = width / (bar_count + 1)
        bar_indices: list[int] = []

        for bi in range(bar_count):
            bx = -half_w + bar_spacing * (bi + 1)
            bv, bf = _make_cylinder(bx, 0, 0, bar_r, height, segments=6)
            bar_parts.append((bv, bf))

        # Cross-bars
        cross_count = max(3, int(height / 0.4))
        for ci in range(cross_count):
            cy = height * (ci + 1) / (cross_count + 1)
            cv, cf = _make_cylinder(-half_w, cy - bar_r, 0, bar_r * 0.8, width, segments=6)
            # Rotate: cylinder is along Y, we want along X
            # Swap x and y
            cv = [(v[1] + half_w, cy, v[2]) for v in cv]
            # Actually, re-generate as a box for simplicity
            cv, cf = _make_box(0, cy, 0, half_w, bar_r * 0.8, bar_r * 0.8)
            bar_parts.append((cv, cf))

        final_verts, final_faces, ranges = _merge_parts_tracked(*bar_parts)
        bar_indices = list(range(len(final_verts)))

        empties["slide_top"] = (0, height + 0.2, 0)
        empties["slide_bottom"] = (0, 0, 0)
        rig_info["motion_type"] = "translate_vertical"
        vertex_groups["bars"] = bar_indices
        vertex_groups["frame"] = []
        all_uvs = _generate_planar_uvs(final_verts, "xy")

    elif style == "double_door":
        # Two independent panels
        panel_w = (width - 0.01) / 2.0  # gap in middle
        plank_count_per = max(3, int(panel_w / 0.15))

        # Left panel
        lv, lf, l_uvs, l_ranges = _plank_row(
            plank_count_per, panel_w, height,
            gap=0.004, thickness=thickness,
            height_variation=0.015, seed=201,
        )
        # Shift left
        lv = [(v[0] - panel_w / 2 - 0.005, v[1], v[2]) for v in lv]

        # Right panel
        rv, rf, r_uvs, r_ranges = _plank_row(
            plank_count_per, panel_w, height,
            gap=0.004, thickness=thickness,
            height_variation=0.015, seed=202,
        )
        # Shift right
        rv = [(v[0] + panel_w / 2 + 0.005, v[1], v[2]) for v in rv]

        # Merge frame + left + right
        left_offset = frame_count
        right_offset = frame_count + len(lv)

        final_verts = frame_verts + lv + rv
        final_faces = frame_faces[:]
        for f in lf:
            final_faces.append(tuple(idx + left_offset for idx in f))
        for f in rf:
            final_faces.append(tuple(idx + right_offset for idx in f))

        left_indices = list(range(left_offset, left_offset + len(lv)))
        right_indices = list(range(right_offset, right_offset + len(rv)))

        empties["hinge_left_top"] = (-half_w, height * 0.85, 0)
        empties["hinge_left_bottom"] = (-half_w, height * 0.15, 0)
        empties["hinge_right_top"] = (half_w, height * 0.85, 0)
        empties["hinge_right_bottom"] = (half_w, height * 0.15, 0)

        vertex_groups["panel_left"] = left_indices
        vertex_groups["panel_right"] = right_indices
        vertex_groups["frame"] = frame_indices

        # Hinge groups
        hinge_left = [i for i in left_indices if abs(final_verts[i][0] + half_w) < 0.05]
        hinge_right = [i for i in right_indices if abs(final_verts[i][0] - half_w) < 0.05]
        vertex_groups["hinge_left"] = hinge_left
        vertex_groups["hinge_right"] = hinge_right
        rig_info["motion_type"] = "double_hinge"

        all_uvs = (_generate_planar_uvs(frame_verts, "xy") + l_uvs + r_uvs)

    elif style == "dungeon_gate":
        # Heavy iron gate with thick bars and arch top
        bar_r = 0.02
        gate_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
        bar_count = max(4, int(width / 0.15))
        bar_spacing = width / (bar_count + 1)

        for bi in range(bar_count):
            bx = -half_w + bar_spacing * (bi + 1)
            bv, bf = _make_cylinder(bx, 0, 0, bar_r, height, segments=8)
            gate_parts.append((bv, bf))

        # Horizontal bars
        for cy in [height * 0.25, height * 0.5, height * 0.75]:
            hv, hf = _make_box(0, cy, 0, half_w, bar_r, bar_r)
            gate_parts.append((hv, hf))

        # Frame
        gate_parts_with_frame: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
        if frame_verts:
            gate_parts_with_frame.append((frame_verts, frame_faces))
        gate_parts_with_frame.extend(gate_parts)

        final_verts, final_faces, ranges = _merge_parts_tracked(*gate_parts_with_frame)
        gate_indices = list(range(ranges[1][0] if len(ranges) > 1 else 0, len(final_verts))) if len(ranges) > 1 else list(range(len(final_verts)))

        empties["hinge_top"] = (-half_w, height * 0.85, 0)
        empties["hinge_bottom"] = (-half_w, height * 0.15, 0)

        vertex_groups["panel"] = gate_indices
        vertex_groups["frame"] = list(range(ranges[0][0], ranges[0][1])) if frame_verts else []
        rig_info["hinge_side"] = "left"
        all_uvs = _generate_planar_uvs(final_verts, "xy")

    elif style == "castle_gate":
        # Massive reinforced double gate with arch
        panel_w = (width - 0.02) / 2.0
        plank_count_per = max(5, int(panel_w / 0.12))

        lv, lf, l_uvs, _ = _plank_row(
            plank_count_per, panel_w, height,
            gap=0.005, thickness=thickness * 1.5,
            height_variation=0.01, seed=301,
        )
        lv = [(v[0] - panel_w / 2 - 0.01, v[1], v[2]) for v in lv]

        rv, rf, r_uvs, _ = _plank_row(
            plank_count_per, panel_w, height,
            gap=0.005, thickness=thickness * 1.5,
            height_variation=0.01, seed=302,
        )
        rv = [(v[0] + panel_w / 2 + 0.01, v[1], v[2]) for v in rv]

        # Iron cross-straps on each panel
        strap_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
        for offset_x, pw in [(-panel_w / 2 - 0.01, panel_w), (panel_w / 2 + 0.01, panel_w)]:
            for si in range(4):
                sy = height * (si + 1) / 5
                sv, sf = _iron_strap(
                    offset_x - pw / 2 + 0.02, sy, thickness * 0.75 + 0.005,
                    offset_x + pw / 2 - 0.02, sy, thickness * 0.75 + 0.005,
                    width=0.05, thickness=0.008,
                )
                strap_parts.append((sv, sf))

        strap_v, strap_f = ([], []) if not strap_parts else _merge_parts(*strap_parts)

        left_offset = frame_count
        right_offset = frame_count + len(lv)
        strap_offset = right_offset + len(rv)

        final_verts = frame_verts + lv + rv + strap_v
        final_faces = frame_faces[:]
        for f in lf:
            final_faces.append(tuple(idx + left_offset for idx in f))
        for f in rf:
            final_faces.append(tuple(idx + right_offset for idx in f))
        for f in strap_f:
            final_faces.append(tuple(idx + strap_offset for idx in f))

        vertex_groups["panel_left"] = list(range(left_offset, left_offset + len(lv)))
        vertex_groups["panel_right"] = list(range(right_offset, right_offset + len(rv)))
        vertex_groups["frame"] = frame_indices
        vertex_groups["straps"] = list(range(strap_offset, strap_offset + len(strap_v)))

        empties["hinge_left_top"] = (-half_w, height * 0.85, 0)
        empties["hinge_left_bottom"] = (-half_w, height * 0.15, 0)
        empties["hinge_right_top"] = (half_w, height * 0.85, 0)
        empties["hinge_right_bottom"] = (half_w, height * 0.15, 0)
        rig_info["motion_type"] = "double_hinge"
        all_uvs = (_generate_planar_uvs(frame_verts, "xy") + l_uvs + r_uvs +
                   _generate_planar_uvs(strap_v, "xy"))

    elif style == "secret_passage":
        # Looks like a wall section, pivots from centre
        # Stone-block pattern
        stone_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
        rows = max(6, int(height / 0.25))
        cols = max(3, int(width / 0.3))
        stone_h = height / rows
        stone_w = width / cols
        gap = 0.005

        for r in range(rows):
            offset = (stone_w * 0.5) if (r % 2) else 0.0
            for c in range(cols):
                sx = -half_w + c * stone_w + stone_w / 2 + offset
                if sx - stone_w / 2 < -half_w - 0.01 or sx + stone_w / 2 > half_w + 0.01:
                    continue
                sy = r * stone_h + stone_h / 2
                sv, sf = _make_box(
                    sx, sy, 0,
                    stone_w / 2 - gap, stone_h / 2 - gap, half_t,
                )
                stone_parts.append((sv, sf))

        panel_verts, panel_faces = _merge_parts(*stone_parts)
        left_offset = frame_count
        final_verts = frame_verts + panel_verts
        final_faces = frame_faces[:]
        for f in panel_faces:
            final_faces.append(tuple(idx + left_offset for idx in f))

        panel_indices = list(range(left_offset, left_offset + len(panel_verts)))
        vertex_groups["panel"] = panel_indices
        vertex_groups["frame"] = frame_indices
        # Pivot from centre
        empties["pivot_center"] = (0, height / 2, 0)
        rig_info["motion_type"] = "center_pivot"
        all_uvs = _generate_planar_uvs(final_verts, "xy")

    else:
        # Fallback: simple plank door
        pv, pf, p_uvs, _ = _plank_row(
            5, width, height, gap=0.004, thickness=thickness, seed=999,
        )
        final_verts = frame_verts + pv
        final_faces = frame_faces[:]
        for f in pf:
            final_faces.append(tuple(idx + frame_count for idx in f))
        vertex_groups["panel"] = list(range(frame_count, frame_count + len(pv)))
        vertex_groups["frame"] = frame_indices
        empties["hinge_top"] = (-half_w, height * 0.85, 0)
        empties["hinge_bottom"] = (-half_w, height * 0.15, 0)
        all_uvs = _generate_planar_uvs(final_verts, "xy")

    # Handle empty for knob/pull
    if style not in ("portcullis",):
        empties["handle"] = (half_w * 0.6, height * 0.5, half_t + 0.02)

    return _make_riggable_result(
        f"Door_{style}",
        final_verts,
        final_faces,
        uvs=all_uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info=rig_info,
        category="door",
        style=style,
    )


# =========================================================================
# 2. CHAINS
# =========================================================================

def generate_chain(
    link_count: int = 8,
    link_width: float = 0.04,
    link_height: float = 0.06,
    link_thickness: float = 0.01,
    style: str = "iron",
) -> MeshSpec:
    """Generate a chain with per-link mesh and bone positions.

    Each link is a proper rounded-rectangle torus shape with thickness.
    Links alternate 90-degree orientation for interlocking.
    Per-link vertex groups and bone positions for rigging.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}
    bone_positions: list[dict[str, Any]] = []

    major_r = link_width / 2.0
    minor_r = link_thickness / 2.0
    # Spacing: each link overlaps with the previous
    link_spacing = link_height * 0.85

    seg = 12 if style == "iron" else 8
    tube = 6 if style == "iron" else 4

    vert_offset = 0
    for i in range(link_count):
        cy = -i * link_spacing
        orientation = i % 2  # alternating for interlocking
        lv, lf = _torus_link(
            0, cy, 0,
            major_r, minor_r,
            orientation=orientation,
            segments=seg,
            tube_seg=tube,
        )
        parts.append((lv, lf))

        link_vert_count = len(lv)
        vertex_groups[f"link_{i}"] = list(range(vert_offset, vert_offset + link_vert_count))
        bone_positions.append({
            "name": f"bone_link_{i}",
            "head": (0, cy, 0),
            "tail": (0, cy - link_spacing * 0.5, 0),
        })
        vert_offset += link_vert_count

    final_verts, final_faces = _merge_parts(*parts)

    empties["attach_start"] = (0, 0, 0)
    empties["attach_end"] = (0, -(link_count - 1) * link_spacing, 0)
    for bp in bone_positions:
        empties[bp["name"]] = bp["head"]

    uvs = _generate_planar_uvs(final_verts, "xy")

    return _make_riggable_result(
        f"Chain_{style}_{link_count}",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "chain",
            "style": style,
            "link_count": link_count,
            "bone_positions": bone_positions,
            "constraint": "chain_ik",
        },
        category="chain",
    )


# =========================================================================
# 3. FLAGS / BANNERS
# =========================================================================

def generate_flag(
    width: float = 1.5,
    height: float = 1.0,
    pole_height: float = 3.0,
    subdivisions: int = 12,
    style: str = "banner",
) -> MeshSpec:
    """Generate cloth-sim-ready flag with pole.

    Styles: banner (rectangular), pennant (triangular), gonfalon (pointed bottom),
            standard (with topper), tattered (torn edges)

    The flag mesh is a regular grid of quads for cloth simulation.
    'pinned' vertex group contains vertices along the pole edge.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}
    all_uvs: list[tuple[float, float]] = []

    pole_r = 0.02
    flag_attach_y = pole_height - 0.1  # top of flag

    # --- FLAG MESH: regular grid ---
    rows = subdivisions
    cols = subdivisions
    flag_verts: list[tuple[float, float, float]] = []
    flag_faces: list[tuple[int, ...]] = []
    flag_uvs: list[tuple[float, float]] = []
    pinned_indices: list[int] = []
    flag_body_indices: list[int] = []

    rng_tatter = _rng.Random(777)
    removed_cells: set[tuple[int, int]] = set()

    if style == "tattered":
        # Remove ~20% of edge cells for torn look
        for r in range(rows):
            for c in range(cols):
                is_edge = (r == 0 or r == rows - 1 or c == cols - 1)
                if is_edge and rng_tatter.random() < 0.25:
                    removed_cells.add((r, c))
                # Also random interior holes
                if c > cols * 0.6 and rng_tatter.random() < 0.08:
                    removed_cells.add((r, c))

    for r in range(rows + 1):
        for c in range(cols + 1):
            u = c / cols
            v = r / rows
            fx = u * width  # extends from pole (x=0) to right

            # Shape modification based on style
            if style == "pennant":
                # Triangular: width narrows toward bottom
                fy = flag_attach_y - v * height
                fx *= (1.0 - v * 0.9)  # narrows to 10% at bottom
            elif style == "gonfalon":
                # Pointed bottom: normal width but V-cut at bottom
                fy = flag_attach_y - v * height
                if v > 0.7:
                    # V-cut: centre drops lower
                    centre_dist = abs(u - 0.5) * 2.0
                    extra_drop = (1.0 - centre_dist) * height * 0.3 * ((v - 0.7) / 0.3)
                    fy -= extra_drop
            else:
                fy = flag_attach_y - v * height

            fz = 0.0
            flag_verts.append((fx, fy, fz))
            flag_uvs.append((u, 1.0 - v))

            vi = r * (cols + 1) + c
            flag_body_indices.append(vi)
            # Pinned: vertices along the pole edge (c == 0)
            if c == 0:
                pinned_indices.append(vi)

    # Build quad faces
    for r in range(rows):
        for c in range(cols):
            if (r, c) in removed_cells:
                continue
            v0 = r * (cols + 1) + c
            v1 = v0 + 1
            v2 = (r + 1) * (cols + 1) + c + 1
            v3 = (r + 1) * (cols + 1) + c
            flag_faces.append((v0, v1, v2, v3))

    # Tattered: add jagged displacement to remaining edge verts
    if style == "tattered":
        for vi in range(len(flag_verts)):
            r = vi // (cols + 1)
            c = vi % (cols + 1)
            if c == cols or r == 0 or r == rows:
                jitter = rng_tatter.uniform(-0.02, 0.02)
                v = flag_verts[vi]
                flag_verts[vi] = (v[0] + jitter, v[1] + jitter * 0.5, v[2])

    # --- POLE ---
    pole_v, pole_f = _make_cylinder(0, 0, 0, pole_r, pole_height, segments=8)
    pole_offset = len(flag_verts)
    pole_indices = list(range(pole_offset, pole_offset + len(pole_v)))

    # --- FINIAL (ball on top) ---
    finial_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    if style == "standard":
        # Spear-point finial
        spear_h = 0.15
        spear_v: list[tuple[float, float, float]] = []
        spear_f: list[tuple[int, ...]] = []
        seg_count = 8
        for i in range(seg_count):
            a = 2.0 * math.pi * i / seg_count
            spear_v.append((
                math.cos(a) * pole_r * 1.5,
                pole_height,
                math.sin(a) * pole_r * 1.5,
            ))
        spear_v.append((0, pole_height + spear_h, 0))
        for i in range(seg_count):
            i2 = (i + 1) % seg_count
            spear_f.append((i, i2, seg_count))
        spear_f.append(tuple(range(seg_count - 1, -1, -1)))
        finial_parts.append((spear_v, spear_f))
    else:
        # Ball finial
        ball_v, ball_f = _make_sphere(0, pole_height + pole_r * 2, 0,
                                       pole_r * 1.8, rings=4, sectors=6)
        finial_parts.append((ball_v, ball_f))

    finial_v, finial_f = _merge_parts(*finial_parts) if finial_parts else ([], [])
    finial_offset = pole_offset + len(pole_v)

    # Merge all
    final_verts = flag_verts + pole_v + finial_v
    final_faces = flag_faces[:]
    for f in pole_f:
        final_faces.append(tuple(idx + pole_offset for idx in f))
    for f in finial_f:
        final_faces.append(tuple(idx + finial_offset for idx in f))

    # UV
    pole_uvs = _generate_planar_uvs(pole_v, "xy")
    finial_uvs = _generate_planar_uvs(finial_v, "xy") if finial_v else []
    all_uvs = flag_uvs + pole_uvs + finial_uvs

    # Vertex groups
    vertex_groups["pinned"] = pinned_indices
    vertex_groups["flag_body"] = flag_body_indices
    vertex_groups["pole"] = pole_indices

    # Empties
    empties["pole_base"] = (0, 0, 0)
    empties["pole_top"] = (0, pole_height, 0)
    empties["flag_attach_top"] = (0, flag_attach_y, 0)
    empties["flag_attach_bottom"] = (0, flag_attach_y - height, 0)

    # Vertex color data (distance from pole for wind simulation)
    wind_data = []
    for vi in range(len(flag_verts)):
        r_idx = vi // (cols + 1)
        c_idx = vi % (cols + 1)
        dist_from_pole = c_idx / cols  # R channel
        dist_from_top = r_idx / rows    # G channel
        wind_data.append({"R": dist_from_pole, "G": dist_from_top, "B": 0.0})

    return _make_riggable_result(
        f"Flag_{style}",
        final_verts,
        final_faces,
        uvs=all_uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "flag",
            "style": style,
            "grid_rows": rows,
            "grid_cols": cols,
            "cloth_sim": True,
            "wind_vertex_colors": wind_data,
        },
        category="flag",
    )


# =========================================================================
# 4. TREASURE CHESTS
# =========================================================================

def generate_chest(
    style: str = "wooden",
    width: float = 0.6,
    height: float = 0.4,
    depth: float = 0.4,
) -> MeshSpec:
    """Generate openable treasure chest with lid hinge.

    Styles: wooden, iron_bound, ornate_gold, skeleton_coffin, mimic, barrel_stash

    Features:
    - Base box with interior faces
    - Lid as separate mesh piece with rounded top
    - Hinge empties at back edge
    - Lock plate and clasp geometry
    """
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    hw = width / 2.0
    hd = depth / 2.0
    base_h = height * 0.55  # base is slightly more than half
    lid_h = height - base_h
    wall = 0.02  # wall thickness

    # --- BASE BOX ---
    base_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Outer shell
    outer_v, outer_f = _make_box(0, base_h / 2, 0, hw, base_h / 2, hd)
    base_parts.append((outer_v, outer_f))

    # Interior cavity (slightly smaller box, inverted normals for visible inside)
    inner_v, inner_f = _make_box(0, base_h / 2 + wall / 2, 0,
                                  hw - wall, base_h / 2 - wall / 2, hd - wall)
    # Flip face winding for inner faces
    inner_f = [tuple(reversed(f)) for f in inner_f]
    base_parts.append((inner_v, inner_f))

    # Plank detail on front (for wooden / iron_bound)
    if style in ("wooden", "iron_bound"):
        plank_count = max(3, int(width / 0.12))
        for pi in range(plank_count):
            px = -hw + (pi + 0.5) * width / plank_count
            groove_v, groove_f = _make_box(
                px, base_h / 2, hd + 0.001,
                0.002, base_h / 2 - 0.01, 0.001,
            )
            base_parts.append((groove_v, groove_f))

    base_verts, base_faces = _merge_parts(*base_parts)
    base_indices = list(range(len(base_verts)))

    # --- LID ---
    lid_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Rounded top profile via arc
    arc_segments = 8
    lid_verts: list[tuple[float, float, float]] = []
    lid_faces: list[tuple[int, ...]] = []

    for si in range(arc_segments + 1):
        t = si / arc_segments
        angle = math.pi * t
        ly = base_h + math.sin(angle) * lid_h
        lz = math.cos(angle) * hd

        lid_verts.append((-hw, ly, lz))
        lid_verts.append((hw, ly, lz))

    for si in range(arc_segments):
        b = si * 2
        lid_faces.append((b, b + 1, b + 3, b + 2))

    # End caps
    left_cap = [si * 2 for si in range(arc_segments + 1)]
    right_cap = [si * 2 + 1 for si in range(arc_segments + 1)]
    lid_faces.append(tuple(reversed(left_cap)))
    lid_faces.append(tuple(right_cap))

    lid_parts.append((lid_verts, lid_faces))

    lid_merged_verts, lid_merged_faces = _merge_parts(*lid_parts)
    lid_offset = len(base_verts)
    lid_indices = list(range(lid_offset, lid_offset + len(lid_merged_verts)))

    # --- DECORATION based on style ---
    deco_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "iron_bound":
        # Iron straps around chest
        for sy in [base_h * 0.3, base_h * 0.7]:
            sv, sf = _iron_strap(-hw - 0.002, sy, hd, hw + 0.002, sy, hd,
                                  width=0.03, thickness=0.005)
            deco_parts.append((sv, sf))
            sv2, sf2 = _iron_strap(-hw - 0.002, sy, -hd, hw + 0.002, sy, -hd,
                                    width=0.03, thickness=0.005)
            deco_parts.append((sv2, sf2))
        # Corner brackets
        for cx_s in [-1, 1]:
            for cz_s in [-1, 1]:
                rv, rf = _rivet(cx_s * hw, base_h * 0.3, cz_s * hd, radius=0.008)
                deco_parts.append((rv, rf))
                rv2, rf2 = _rivet(cx_s * hw, base_h * 0.7, cz_s * hd, radius=0.008)
                deco_parts.append((rv2, rf2))

    elif style == "ornate_gold":
        # Embossed corner brackets
        for cx_s in [-1, 1]:
            for cz_s in [-1, 1]:
                bv, bf = _make_box(
                    cx_s * (hw - 0.02), base_h * 0.5, cz_s * (hd + 0.003),
                    0.04, base_h * 0.4, 0.003,
                )
                deco_parts.append((bv, bf))
        # Embossed front panel
        panel_v, panel_f = _make_box(0, base_h * 0.5, hd + 0.004,
                                      hw * 0.6, base_h * 0.3, 0.003)
        deco_parts.append((panel_v, panel_f))

    elif style == "mimic":
        # Teeth along opening edge
        tooth_count = int(width / 0.04)
        for ti in range(tooth_count):
            tx = -hw + (ti + 0.5) * width / tooth_count
            # Top teeth (on base top edge)
            tv, tf = _make_box(tx, base_h + 0.01, hd * 0.7,
                                0.008, 0.02, 0.005)
            deco_parts.append((tv, tf))
            # Bottom teeth (on base top edge, front)
            tv2, tf2 = _make_box(tx, base_h + 0.01, -hd * 0.7,
                                  0.008, 0.02, 0.005)
            deco_parts.append((tv2, tf2))
        # Tongue inside
        tongue_v: list[tuple[float, float, float]] = []
        tongue_f: list[tuple[int, ...]] = []
        t_segs = 6
        for ti in range(t_segs + 1):
            t = ti / t_segs
            tx_pos = 0.0
            ty_pos = base_h * 0.3 + t * base_h * 0.3
            tz_pos = -hd * 0.3 + t * hd * 1.2
            t_width = 0.08 * (1.0 - t * 0.5)
            tongue_v.append((tx_pos - t_width, ty_pos, tz_pos))
            tongue_v.append((tx_pos + t_width, ty_pos, tz_pos))
        for ti in range(t_segs):
            b = ti * 2
            tongue_f.append((b, b + 1, b + 3, b + 2))
        deco_parts.append((tongue_v, tongue_f))

    elif style == "skeleton_coffin":
        # Hexagonal coffin shape base modifier: widen at shoulders
        # Add coffin shaping struts
        for sy in [base_h * 0.2, base_h * 0.6, base_h * 0.9]:
            sv, sf = _iron_strap(-hw, sy, hd + 0.003, hw, sy, hd + 0.003,
                                  width=0.02, thickness=0.004)
            deco_parts.append((sv, sf))
        # Cross on lid
        cv1, cf1 = _iron_strap(-0.02, base_h + lid_h * 0.3, hd + 0.005,
                                -0.02, base_h + lid_h * 0.8, hd + 0.005,
                                width=0.015, thickness=0.004)
        cv2, cf2 = _iron_strap(-0.06, base_h + lid_h * 0.5, hd + 0.005,
                                0.02, base_h + lid_h * 0.5, hd + 0.005,
                                width=0.015, thickness=0.004)
        deco_parts.extend([(cv1, cf1), (cv2, cf2)])

    # Lock plate (most styles)
    if style not in ("mimic", "barrel_stash"):
        lock_v, lock_f = _make_box(0, base_h, hd + 0.008,
                                    0.03, 0.02, 0.005)
        deco_parts.append((lock_v, lock_f))
        # Keyhole
        key_v, key_f = _make_cylinder(0, base_h - 0.005, hd + 0.014,
                                       0.005, 0.01, segments=6)
        deco_parts.append((key_v, key_f))

    # Clasp/latch
    if style in ("wooden", "iron_bound"):
        clasp_v, clasp_f = _iron_strap(
            -0.02, base_h + 0.005, hd + 0.005,
            0.02, base_h + 0.005, hd + 0.005,
            width=0.02, thickness=0.004,
        )
        deco_parts.append((clasp_v, clasp_f))

    deco_verts, deco_faces = _merge_parts(*deco_parts) if deco_parts else ([], [])
    deco_offset = lid_offset + len(lid_merged_verts)

    # Merge all
    final_verts = base_verts + lid_merged_verts + deco_verts
    final_faces = base_faces[:]
    for f in lid_merged_faces:
        final_faces.append(tuple(idx + lid_offset for idx in f))
    for f in deco_faces:
        final_faces.append(tuple(idx + deco_offset for idx in f))

    vertex_groups["base"] = base_indices
    vertex_groups["lid"] = lid_indices

    # Hinge empties at back edge
    empties["hinge_left"] = (-hw, base_h, -hd)
    empties["hinge_right"] = (hw, base_h, -hd)
    empties["hinge_axis"] = (0, base_h, -hd)
    empties["lock"] = (0, base_h, hd + 0.01)
    empties["loot_spawn"] = (0, base_h * 0.3, 0)

    uvs = _generate_planar_uvs(final_verts, "xz")

    return _make_riggable_result(
        f"Chest_{style}",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "chest",
            "style": style,
            "lid_hinge_axis": "X",
            "lid_rotation_range": (0, 110),
        },
        category="chest",
    )


# =========================================================================
# 5. CHANDELIERS
# =========================================================================

def generate_chandelier(
    style: str = "iron_ring",
    candle_count: int = 8,
    chain_length: float = 1.5,
) -> MeshSpec:
    """Generate chandelier with chain suspension.

    Styles: iron_ring, candelabra, bone_chandelier, cage_lantern
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    ring_y = -chain_length
    ring_r = 0.3 + candle_count * 0.03  # scale with candle count

    # --- SUSPENSION CHAIN ---
    chain_spec = generate_chain(
        link_count=max(4, int(chain_length / 0.05)),
        link_width=0.025,
        link_height=0.04,
        link_thickness=0.006,
    )
    chain_verts = chain_spec["vertices"]
    chain_faces = chain_spec["faces"]
    # Shift chain so it hangs from (0, 0, 0) downward
    # chain already hangs downward from its generate_chain default
    parts.append((chain_verts, chain_faces))
    chain_vert_count = len(chain_verts)

    # --- MAIN RING / FRAME ---
    if style == "iron_ring":
        ring_v, ring_f = _make_torus(0, ring_y, 0, ring_r, 0.015,
                                      major_seg=candle_count * 2, minor_seg=6)
        parts.append((ring_v, ring_f))
        # Cross bars
        for i in range(4):
            angle = math.pi * i / 4
            sv, sf = _iron_strap(
                math.cos(angle) * ring_r * 0.3, ring_y, math.sin(angle) * ring_r * 0.3,
                math.cos(angle + math.pi) * ring_r * 0.3, ring_y, math.sin(angle + math.pi) * ring_r * 0.3,
                width=0.015, thickness=0.008,
            )
            parts.append((sv, sf))

    elif style == "candelabra":
        # Central pole with arms
        pole_v, pole_f = _make_cylinder(0, ring_y - 0.3, 0, 0.015, 0.4, segments=8)
        parts.append((pole_v, pole_f))
        for i in range(candle_count):
            angle = 2.0 * math.pi * i / candle_count
            arm_end_x = math.cos(angle) * ring_r
            arm_end_z = math.sin(angle) * ring_r
            av, af = _iron_strap(
                0, ring_y, 0,
                arm_end_x, ring_y - 0.05, arm_end_z,
                width=0.012, thickness=0.008,
            )
            parts.append((av, af))

    elif style == "bone_chandelier":
        ring_v, ring_f = _make_torus(0, ring_y, 0, ring_r, 0.02,
                                      major_seg=12, minor_seg=4)
        parts.append((ring_v, ring_f))
        # Hanging bone-like shapes
        for i in range(candle_count):
            angle = 2.0 * math.pi * i / candle_count
            bx = math.cos(angle) * ring_r
            bz = math.sin(angle) * ring_r
            bone_v, bone_f = _make_cylinder(bx, ring_y - 0.15, bz,
                                             0.008, 0.12, segments=4)
            parts.append((bone_v, bone_f))
            # Knuckle joint
            kv, kf = _make_sphere(bx, ring_y - 0.15, bz, 0.012, rings=3, sectors=4)
            parts.append((kv, kf))

    elif style == "cage_lantern":
        # Cage-like structure
        bar_count = 8
        cage_h = 0.3
        cage_r = ring_r * 0.6
        for i in range(bar_count):
            angle = 2.0 * math.pi * i / bar_count
            bx = math.cos(angle) * cage_r
            bz = math.sin(angle) * cage_r
            bv, bf = _make_cylinder(bx, ring_y - cage_h, bz,
                                     0.006, cage_h, segments=4)
            parts.append((bv, bf))
        # Top and bottom rings
        tr_v, tr_f = _make_torus(0, ring_y, 0, cage_r, 0.008,
                                  major_seg=12, minor_seg=4)
        parts.append((tr_v, tr_f))
        br_v, br_f = _make_torus(0, ring_y - cage_h, 0, cage_r, 0.008,
                                  major_seg=12, minor_seg=4)
        parts.append((br_v, br_f))

    # --- CANDLE HOLDERS + CANDLES ---
    candle_positions: list[tuple[float, float, float]] = []
    for i in range(candle_count):
        angle = 2.0 * math.pi * i / candle_count
        cx_pos = math.cos(angle) * ring_r
        cz_pos = math.sin(angle) * ring_r
        cy_pos = ring_y

        # Holder cup
        cup_v, cup_f = _make_cylinder(cx_pos, cy_pos - 0.005, cz_pos,
                                       0.02, 0.015, segments=6)
        parts.append((cup_v, cup_f))

        # Candle (slightly tapered cylinder)
        candle_h = 0.08
        candle_v, candle_f = _make_cylinder(cx_pos, cy_pos + 0.01, cz_pos,
                                             0.008, candle_h, segments=6)
        parts.append((candle_v, candle_f))

        flame_pos = (cx_pos, cy_pos + 0.01 + candle_h + 0.01, cz_pos)
        candle_positions.append(flame_pos)
        empties[f"flame_{i}"] = flame_pos

    # Merge everything
    final_verts, final_faces = _merge_parts(*parts)

    # Sway vertex group: everything below the anchor
    sway_indices = list(range(len(final_verts)))

    empties["ceiling_anchor"] = (0, 0, 0)
    empties["chandelier_center"] = (0, ring_y, 0)
    vertex_groups["sway"] = sway_indices
    vertex_groups["chain"] = list(range(chain_vert_count))

    uvs = _generate_planar_uvs(final_verts, "xz")

    return _make_riggable_result(
        f"Chandelier_{style}",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "chandelier",
            "style": style,
            "candle_count": candle_count,
            "candle_positions": candle_positions,
            "physics": "pendulum",
        },
        category="chandelier",
    )


# =========================================================================
# 6. DRAWBRIDGES
# =========================================================================

def generate_drawbridge(
    width: float = 4.0,
    length: float = 3.0,
    plank_count: int = 12,
) -> MeshSpec:
    """Generate drawbridge with hinge and chain attachment.

    Features:
    - Individual plank meshes with gaps
    - Cross-beam support structure
    - Hinge empties at wall-side edge
    - Chain attachment empties at free-end corners
    - Side rail/guard meshes
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    plank_thickness = 0.08
    plank_gap = 0.005
    rail_height = 0.3
    beam_size = 0.06

    # --- PLANKS (laid along Z axis, width along X) ---
    bridge_indices: list[int] = []
    plank_depth = (length - plank_gap * (plank_count - 1)) / plank_count
    plank_hw = width / 2.0

    rng = _rng.Random(555)

    for pi in range(plank_count):
        z_start = pi * (plank_depth + plank_gap)
        z_center = z_start + plank_depth / 2.0
        # Slight random width variation per plank
        w_var = rng.uniform(-0.01, 0.01)

        pv, pf = _make_box(
            0, -plank_thickness / 2, z_center,
            plank_hw + w_var, plank_thickness / 2, plank_depth / 2,
        )
        start_v = sum(len(p[0]) for p in parts)
        bridge_indices.extend(range(start_v, start_v + len(pv)))
        parts.append((pv, pf))

    # --- CROSS BEAMS (underneath) ---
    beam_count = 3
    beam_indices: list[int] = []
    for bi in range(beam_count):
        bz = length * (bi + 1) / (beam_count + 1)
        bv, bf = _make_box(
            0, -plank_thickness - beam_size / 2, bz,
            plank_hw - 0.05, beam_size / 2, beam_size / 2,
        )
        start_v = sum(len(p[0]) for p in parts)
        beam_indices.extend(range(start_v, start_v + len(bv)))
        parts.append((bv, bf))

    # --- SIDE RAILS ---
    rail_indices: list[int] = []
    for side in [-1, 1]:
        rx = side * (plank_hw + 0.02)
        # Vertical posts at each end and middle
        for pz in [0.1, length / 2, length - 0.1]:
            rv, rf = _make_cylinder(rx, 0, pz, 0.025, rail_height, segments=6)
            start_v = sum(len(p[0]) for p in parts)
            rail_indices.extend(range(start_v, start_v + len(rv)))
            parts.append((rv, rf))
        # Horizontal rail
        rail_v, rail_f = _make_box(
            rx, rail_height, length / 2,
            0.02, 0.02, length / 2 - 0.05,
        )
        start_v = sum(len(p[0]) for p in parts)
        rail_indices.extend(range(start_v, start_v + len(rail_v)))
        parts.append((rail_v, rail_f))

    final_verts, final_faces = _merge_parts(*parts)

    vertex_groups["bridge"] = bridge_indices
    vertex_groups["beams"] = beam_indices
    vertex_groups["rails"] = rail_indices

    # Hinges at wall-side edge (z=0)
    empties["hinge_left"] = (-plank_hw, 0, 0)
    empties["hinge_right"] = (plank_hw, 0, 0)
    empties["hinge_axis"] = (0, 0, 0)
    # Chain attachment at free end
    empties["chain_attach_left"] = (-plank_hw + 0.1, 0.05, length)
    empties["chain_attach_right"] = (plank_hw - 0.1, 0.05, length)
    empties["bridge_center"] = (0, 0, length / 2)

    uvs = _generate_planar_uvs(final_verts, "xz")

    return _make_riggable_result(
        "Drawbridge",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "drawbridge",
            "hinge_axis": "X",
            "rotation_range": (0, 90),
            "chain_driven": True,
        },
        category="drawbridge",
    )


# =========================================================================
# 7. ROPE BRIDGES
# =========================================================================

def generate_rope_bridge(
    length: float = 8.0,
    width: float = 1.2,
    plank_count: int = 20,
    sag: float = 0.5,
) -> MeshSpec:
    """Generate physics-ready rope bridge.

    Features:
    - Individual plank meshes on catenary curve
    - Side rope meshes with catenary drape
    - Hand ropes at railing height
    - Vertical rope ties connecting planks to side ropes
    - Per-plank vertex groups for physics
    - Anchor vertex groups at fixed ends
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    hw = width / 2.0
    plank_thickness = 0.04
    plank_w = width * 0.9
    plank_depth = 0.12
    rope_r = 0.015
    hand_rail_h = 0.8

    # Compute catenary positions for planks
    plank_positions = _catenary_curve(
        (0, 0, 0), (length, 0, 0),
        sag, plank_count,
    )

    anchor_start_indices: list[int] = []
    anchor_end_indices: list[int] = []

    # --- PLANKS ---
    for pi, pos in enumerate(plank_positions):
        px, py, pz = pos
        pv, pf = _make_box(
            px, py - plank_thickness / 2, 0,
            plank_depth / 2, plank_thickness / 2, plank_w / 2,
        )
        start_v = sum(len(p[0]) for p in parts)
        idx_range = list(range(start_v, start_v + len(pv)))
        vertex_groups[f"plank_{pi}"] = idx_range
        if pi == 0:
            anchor_start_indices.extend(idx_range)
        elif pi == plank_count - 1:
            anchor_end_indices.extend(idx_range)
        parts.append((pv, pf))

    # --- SIDE ROPES (catenary curves as thick tubes) ---
    for side in [-1, 1]:
        # Bottom rope (plank level)
        bottom_pts = _catenary_curve(
            (0, 0, side * hw), (length, 0, side * hw),
            sag, plank_count * 2,
        )
        for i in range(len(bottom_pts) - 1):
            p1 = bottom_pts[i]
            p2 = bottom_pts[i + 1]
            seg_v, seg_f = _iron_strap(
                p1[0], p1[1], p1[2],
                p2[0], p2[1], p2[2],
                width=rope_r * 2, thickness=rope_r * 2,
            )
            start_v = sum(len(p[0]) for p in parts)
            parts.append((seg_v, seg_f))

        # Hand rope (higher, less sag)
        hand_pts = _catenary_curve(
            (0, hand_rail_h, side * hw),
            (length, hand_rail_h, side * hw),
            sag * 0.3, plank_count * 2,
        )
        for i in range(len(hand_pts) - 1):
            p1 = hand_pts[i]
            p2 = hand_pts[i + 1]
            seg_v, seg_f = _iron_strap(
                p1[0], p1[1], p1[2],
                p2[0], p2[1], p2[2],
                width=rope_r * 1.5, thickness=rope_r * 1.5,
            )
            start_v = sum(len(p[0]) for p in parts)
            parts.append((seg_v, seg_f))

        # Vertical rope ties (connecting planks to hand ropes)
        for pi, pos in enumerate(plank_positions):
            px, py, _ = pos
            # Find corresponding hand rope height
            t = pi / max(plank_count - 1, 1)
            hy = hand_rail_h - sag * 0.3 * 4.0 * t * (1.0 - t)
            tie_v, tie_f = _iron_strap(
                px, py, side * hw,
                px, hy, side * hw,
                width=rope_r, thickness=rope_r,
            )
            start_v = sum(len(p[0]) for p in parts)
            parts.append((tie_v, tie_f))

    final_verts, final_faces = _merge_parts(*parts)

    vertex_groups["anchor_start"] = anchor_start_indices
    vertex_groups["anchor_end"] = anchor_end_indices

    empties["anchor_start"] = (0, 0, 0)
    empties["anchor_end"] = (length, 0, 0)
    empties["bridge_center"] = (length / 2, -sag, 0)

    uvs = _generate_planar_uvs(final_verts, "xz")

    return _make_riggable_result(
        "RopeBridge",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "rope_bridge",
            "plank_count": plank_count,
            "sag": sag,
            "physics": "chain_sim",
            "anchor_points": ["anchor_start", "anchor_end"],
        },
        category="rope_bridge",
    )


# =========================================================================
# 8. HANGING SIGNS
# =========================================================================

def generate_hanging_sign(
    width: float = 0.8,
    height: float = 0.5,
    bracket_style: str = "iron_scroll",
) -> MeshSpec:
    """Generate wall-mounted hanging sign with bracket.

    Features:
    - Sign board (wood planks)
    - Wall bracket (iron scroll or L-bracket)
    - Hanging chains/hooks
    - Pivot empty for swinging animation
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    sign_thickness = 0.025
    bracket_extend = 0.4  # how far bracket extends from wall
    sign_hang_y = -0.1  # below bracket

    # --- SIGN BOARD ---
    plank_count = max(3, int(height / 0.1))
    sign_v, sign_f, sign_uvs, sign_ranges = _plank_row(
        plank_count, width, height,
        gap=0.003, thickness=sign_thickness,
        height_variation=0.01,
        seed=444,
    )
    # Position sign: hanging below bracket, centred at bracket_extend distance
    sign_v = [(v[0] + bracket_extend, v[1] + sign_hang_y - height, v[2])
              for v in sign_v]
    sign_indices = list(range(len(sign_v)))
    parts.append((sign_v, sign_f))

    # --- BRACKET ---
    bracket_indices: list[int] = []
    bracket_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if bracket_style == "iron_scroll":
        # Decorative scrollwork: curved arm with curl at end
        arm_segs = 10
        arm_v: list[tuple[float, float, float]] = []
        arm_f: list[tuple[int, ...]] = []
        bar_w = 0.015
        for si in range(arm_segs + 1):
            t = si / arm_segs
            ax = t * bracket_extend
            # Slight upward curve
            ay = 0.02 * math.sin(math.pi * t)
            arm_v.append((ax, ay - bar_w, 0 - bar_w))
            arm_v.append((ax, ay + bar_w, 0 - bar_w))
            arm_v.append((ax, ay + bar_w, 0 + bar_w))
            arm_v.append((ax, ay - bar_w, 0 + bar_w))
        for si in range(arm_segs):
            b = si * 4
            arm_f.append((b+0, b+4, b+5, b+1))
            arm_f.append((b+1, b+5, b+6, b+2))
            arm_f.append((b+2, b+6, b+7, b+3))
            arm_f.append((b+3, b+7, b+4, b+0))
        # End caps
        arm_f.append((0, 1, 2, 3))
        last = arm_segs * 4
        arm_f.append((last, last+3, last+2, last+1))
        bracket_parts.append((arm_v, arm_f))

        # Scroll curl at end
        curl_segs = 8
        curl_r = 0.04
        curl_v: list[tuple[float, float, float]] = []
        curl_f: list[tuple[int, ...]] = []
        for ci in range(curl_segs + 1):
            t = ci / curl_segs
            angle = math.pi * 1.5 * t  # 270 degree curl
            cx_pos = bracket_extend + curl_r * math.cos(angle)
            cy_pos = -curl_r + curl_r * math.sin(angle)
            curl_v.append((cx_pos - bar_w, cy_pos, 0))
            curl_v.append((cx_pos + bar_w, cy_pos, 0))
        for ci in range(curl_segs):
            b = ci * 2
            curl_f.append((b, b+2, b+3, b+1))
        bracket_parts.append((curl_v, curl_f))

        # Wall plate
        wp_v, wp_f = _make_box(0, 0, 0, 0.04, 0.06, 0.005)
        bracket_parts.append((wp_v, wp_f))

    else:
        # Simple L-bracket
        # Horizontal arm
        h_v, h_f = _make_box(bracket_extend / 2, 0, 0,
                               bracket_extend / 2, 0.015, 0.015)
        bracket_parts.append((h_v, h_f))
        # Diagonal brace
        brace_v, brace_f = _iron_strap(
            0, -0.15, 0, bracket_extend * 0.8, -0.01, 0,
            width=0.02, thickness=0.008,
        )
        bracket_parts.append((brace_v, brace_f))
        # Wall plate
        wp_v, wp_f = _make_box(0, -0.075, 0, 0.03, 0.09, 0.005)
        bracket_parts.append((wp_v, wp_f))

    bracket_v, bracket_f = _merge_parts(*bracket_parts)
    b_offset = len(sign_v)
    bracket_indices = list(range(b_offset, b_offset + len(bracket_v)))

    # --- HANGING CHAINS (2 short chains connecting bracket to sign) ---
    chain_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hook_r = 0.006
    for hx in [bracket_extend - width * 0.3, bracket_extend + width * 0.3]:
        # Simple hook (small torus)
        hv, hf = _make_torus(hx, sign_hang_y * 0.3, 0, 0.015, hook_r,
                              major_seg=6, minor_seg=4)
        chain_parts.append((hv, hf))

    chain_v, chain_f = _merge_parts(*chain_parts) if chain_parts else ([], [])
    c_offset = b_offset + len(bracket_v)

    final_verts = sign_v + bracket_v + chain_v
    final_faces = sign_f[:]
    for f in bracket_f:
        final_faces.append(tuple(idx + b_offset for idx in f))
    for f in chain_f:
        final_faces.append(tuple(idx + c_offset for idx in f))

    vertex_groups["sign_board"] = sign_indices
    vertex_groups["bracket"] = bracket_indices

    empties["wall_mount"] = (0, 0, 0)
    empties["pivot"] = (bracket_extend, 0, 0)
    empties["sign_center"] = (bracket_extend, sign_hang_y - height / 2, 0)

    uvs = sign_uvs + _generate_planar_uvs(bracket_v + chain_v, "xy")

    return _make_riggable_result(
        f"HangingSign_{bracket_style}",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "hanging_sign",
            "bracket_style": bracket_style,
            "pivot_axis": "Z",
            "physics": "pendulum",
        },
        category="hanging_sign",
    )


# =========================================================================
# 9. WINDMILLS
# =========================================================================

def generate_windmill(
    tower_height: float = 8.0,
    blade_count: int = 4,
    blade_length: float = 3.0,
) -> MeshSpec:
    """Generate windmill tower with rotating blade assembly.

    Features:
    - Stone tower (tapered cylinder with window openings)
    - Hub/axle with rotation empty
    - Blade frames (wooden lattice)
    - Blade cloth panels (grid topology, cloth-sim-ready)
    - Vertex groups for rotation and per-blade cloth
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    base_r = 2.0
    top_r = 1.4
    tower_seg = 16
    hub_y = tower_height * 0.85
    hub_r = 0.15

    # --- TOWER (tapered cylinder) ---
    tower_v: list[tuple[float, float, float]] = []
    tower_f: list[tuple[int, ...]] = []

    # Stone course rings (multiple rings for texture detail)
    ring_count = max(8, int(tower_height / 0.8))
    for ri in range(ring_count + 1):
        t = ri / ring_count
        ry = t * tower_height
        r = base_r + (top_r - base_r) * t
        for si in range(tower_seg):
            angle = 2.0 * math.pi * si / tower_seg
            tower_v.append((math.cos(angle) * r, ry, math.sin(angle) * r))

    for ri in range(ring_count):
        for si in range(tower_seg):
            si2 = (si + 1) % tower_seg
            b = ri * tower_seg
            tower_f.append((
                b + si, b + si2,
                b + tower_seg + si2, b + tower_seg + si,
            ))

    # Bottom cap
    tower_f.append(tuple(range(tower_seg - 1, -1, -1)))

    parts.append((tower_v, tower_f))
    tower_vert_count = len(tower_v)

    # --- WINDOW OPENINGS (small inset boxes on tower surface) ---
    window_count = 3
    for wi in range(window_count):
        wy = tower_height * (0.25 + wi * 0.25)
        wa = math.pi * 0.3 * wi  # stagger around tower
        r_at = base_r + (top_r - base_r) * (wy / tower_height)
        wx = math.cos(wa) * (r_at + 0.01)
        wz = math.sin(wa) * (r_at + 0.01)
        wv, wf = _make_box(wx, wy, wz, 0.2, 0.3, 0.05)
        parts.append((wv, wf))

    # --- HUB / AXLE ---
    hub_v, hub_f = _make_cylinder(0, hub_y - hub_r, top_r + 0.1,
                                   hub_r, hub_r * 2, segments=8)
    # The hub extends out from the tower front
    # Rotate to face outward (along Z)
    hub_v = [(v[0], v[1], v[2]) for v in hub_v]
    parts.append((hub_v, hub_f))

    empties["rotation_axis"] = (0, hub_y, top_r + 0.1 + hub_r)

    # --- BLADES ---
    blade_indices: list[int] = []
    cloth_groups: dict[str, list[int]] = {}

    for bi in range(blade_count):
        angle = 2.0 * math.pi * bi / blade_count
        # Blade frame (wooden lattice)
        frame_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

        # Main spar
        spar_segs = 6
        for ssi in range(spar_segs):
            t0 = ssi / spar_segs
            t1 = (ssi + 1) / spar_segs
            r0 = hub_r + t0 * blade_length
            r1 = hub_r + t1 * blade_length

            x0 = math.cos(angle) * r0
            y0 = hub_y + math.sin(angle) * r0
            x1 = math.cos(angle) * r1
            y1 = hub_y + math.sin(angle) * r1

            sv, sf = _iron_strap(
                x0, y0, top_r + 0.1,
                x1, y1, top_r + 0.1,
                width=0.05, thickness=0.03,
            )
            frame_parts.append((sv, sf))

        # Cross slats (perpendicular to spar)
        slat_count = 4
        perp_x = -math.sin(angle)
        perp_y = math.cos(angle)
        for sli in range(slat_count):
            t = (sli + 1) / (slat_count + 1)
            r = hub_r + t * blade_length
            cx_pos = math.cos(angle) * r
            cy_pos = hub_y + math.sin(angle) * r
            slat_half = 0.15 + (1.0 - t) * 0.1  # wider near hub

            sv, sf = _iron_strap(
                cx_pos - perp_x * slat_half, cy_pos - perp_y * slat_half, top_r + 0.1,
                cx_pos + perp_x * slat_half, cy_pos + perp_y * slat_half, top_r + 0.1,
                width=0.03, thickness=0.02,
            )
            frame_parts.append((sv, sf))

        frame_v, frame_f = _merge_parts(*frame_parts)
        f_offset = sum(len(p[0]) for p in parts)
        blade_indices.extend(range(f_offset, f_offset + len(frame_v)))
        parts.append((frame_v, frame_f))

        # --- CLOTH PANEL (grid topology for cloth sim) ---
        cloth_rows = 6
        cloth_cols = 4
        cloth_v: list[tuple[float, float, float]] = []
        cloth_f: list[tuple[int, ...]] = []

        for cr in range(cloth_rows + 1):
            for cc in range(cloth_cols + 1):
                t_r = cr / cloth_rows
                t_c = cc / cloth_cols
                r = hub_r * 1.5 + t_r * blade_length * 0.8
                # Perpendicular offset
                p_off = (t_c - 0.5) * 0.3 * (1.0 - t_r * 0.3)

                cx_pos = math.cos(angle) * r + perp_x * p_off
                cy_pos = hub_y + math.sin(angle) * r + perp_y * p_off
                cz_pos = top_r + 0.12  # slightly in front of frame

                cloth_v.append((cx_pos, cy_pos, cz_pos))

        for cr in range(cloth_rows):
            for cc in range(cloth_cols):
                v0 = cr * (cloth_cols + 1) + cc
                v1 = v0 + 1
                v2 = (cr + 1) * (cloth_cols + 1) + cc + 1
                v3 = (cr + 1) * (cloth_cols + 1) + cc
                cloth_f.append((v0, v1, v2, v3))

        c_offset = sum(len(p[0]) for p in parts)
        cloth_indices = list(range(c_offset, c_offset + len(cloth_v)))
        cloth_groups[f"cloth_{bi}"] = cloth_indices
        blade_indices.extend(cloth_indices)
        parts.append((cloth_v, cloth_f))

    vertex_groups["blades"] = blade_indices
    vertex_groups.update(cloth_groups)

    final_verts, final_faces = _merge_parts(*parts)

    empties["tower_base"] = (0, 0, 0)
    empties["tower_top"] = (0, tower_height, 0)

    uvs = _generate_planar_uvs(final_verts, "xy")

    return _make_riggable_result(
        "Windmill",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "windmill",
            "blade_count": blade_count,
            "rotation_empty": "rotation_axis",
            "rotation_axis": "Z",
            "cloth_panels": list(cloth_groups.keys()),
        },
        category="windmill",
    )


# =========================================================================
# 10. CAGES / PRISON CELLS
# =========================================================================

def generate_cage(
    style: str = "hanging_cage",
    width: float = 1.0,
    height: float = 1.5,
) -> MeshSpec:
    """Generate prison cage with door.

    Styles: hanging_cage (round, suspended), prison_cell (flat bars),
            gibbet (body-shaped), animal_trap
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    empties: dict[str, tuple[float, float, float]] = {}
    vertex_groups: dict[str, list[int]] = {}

    bar_r = 0.012
    bar_seg = 6
    hd = width / 2.0

    if style == "hanging_cage":
        # Round cage with dome top
        cage_r = width / 2.0
        bar_count = max(8, int(cage_r * 2 * math.pi / 0.12))
        cage_indices: list[int] = []

        # Vertical bars
        for bi in range(bar_count):
            angle = 2.0 * math.pi * bi / bar_count
            bx = math.cos(angle) * cage_r
            bz = math.sin(angle) * cage_r
            bv, bf = _make_cylinder(bx, 0, bz, bar_r, height * 0.75, segments=bar_seg)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(bv)))
            parts.append((bv, bf))

        # Dome top: converging bars
        for bi in range(bar_count):
            angle = 2.0 * math.pi * bi / bar_count
            bx = math.cos(angle) * cage_r
            bz = math.sin(angle) * cage_r
            sv, sf = _iron_strap(
                bx, height * 0.75, bz,
                0, height, 0,
                width=bar_r * 2, thickness=bar_r * 2,
            )
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(sv)))
            parts.append((sv, sf))

        # Horizontal rings (2-3)
        for ry in [height * 0.25, height * 0.5, height * 0.75]:
            rv, rf = _make_torus(0, ry, 0, cage_r, bar_r * 1.2,
                                  major_seg=bar_count, minor_seg=4)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(rv)))
            parts.append((rv, rf))

        # Floor disc
        floor_v, floor_f = _make_cylinder(0, -0.01, 0, cage_r * 0.95, 0.01,
                                           segments=bar_count)
        start_v = sum(len(p[0]) for p in parts)
        cage_indices.extend(range(start_v, start_v + len(floor_v)))
        parts.append((floor_v, floor_f))

        # Hanging ring at top
        ring_v, ring_f = _make_torus(0, height + 0.02, 0, 0.05, 0.01,
                                      major_seg=8, minor_seg=4)
        start_v = sum(len(p[0]) for p in parts)
        parts.append((ring_v, ring_f))

        vertex_groups["cage"] = cage_indices
        empties["hang_point"] = (0, height + 0.05, 0)
        empties["cage_center"] = (0, height * 0.4, 0)

        # Door: one section of bars is a door
        door_angle = 0
        dx = math.cos(door_angle) * cage_r
        dz = math.sin(door_angle) * cage_r
        empties["door_hinge_top"] = (dx, height * 0.7, dz)
        empties["door_hinge_bottom"] = (dx, 0.05, dz)

    elif style == "prison_cell":
        # Flat bar cage (rectangular)
        cell_d = width * 0.8
        bar_count_front = max(5, int(width / 0.15))
        bar_spacing = width / (bar_count_front + 1)
        cage_indices = []

        # Front bars
        for bi in range(bar_count_front):
            bx = -hd + bar_spacing * (bi + 1)
            bv, bf = _make_cylinder(bx, 0, cell_d / 2, bar_r, height, segments=bar_seg)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(bv)))
            parts.append((bv, bf))

        # Top and bottom horizontal bars (front)
        for hy in [0.05, height - 0.05]:
            hv, hf = _make_box(0, hy, cell_d / 2,
                                hd, bar_r, bar_r)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(hv)))
            parts.append((hv, hf))

        # Back wall (solid)
        wall_v, wall_f = _make_box(0, height / 2, -cell_d / 2,
                                    hd, height / 2, 0.05)
        start_v = sum(len(p[0]) for p in parts)
        parts.append((wall_v, wall_f))

        # Side walls
        for side_x in [-hd, hd]:
            sv, sf = _make_box(side_x, height / 2, 0,
                                0.05, height / 2, cell_d / 2)
            start_v_w = sum(len(p[0]) for p in parts)
            parts.append((sv, sf))

        # Floor
        fv, ff = _make_box(0, -0.025, 0, hd, 0.025, cell_d / 2)
        start_v = sum(len(p[0]) for p in parts)
        parts.append((fv, ff))

        vertex_groups["cage"] = cage_indices
        # Door hinge on left side
        empties["door_hinge_top"] = (-hd, height - 0.05, cell_d / 2)
        empties["door_hinge_bottom"] = (-hd, 0.05, cell_d / 2)
        empties["cell_center"] = (0, height * 0.4, 0)

    elif style == "gibbet":
        # Body-shaped cage (wider at shoulders, narrow at feet)
        cage_indices = []
        # Profile: head, shoulders, torso, legs
        profile = [
            (0.15, height * 1.0),   # top of head
            (0.2, height * 0.85),   # head
            (0.35, height * 0.7),   # shoulders
            (0.3, height * 0.5),    # torso
            (0.25, height * 0.35),  # waist
            (0.2, height * 0.15),   # legs
            (0.1, 0.0),             # feet
        ]

        # Build cage from vertical bar strips following the profile
        bar_count = 10
        for bi in range(bar_count):
            angle = 2.0 * math.pi * bi / bar_count
            # Generate bar following profile
            for pi in range(len(profile) - 1):
                r0, y0 = profile[pi]
                r1, y1 = profile[pi + 1]
                x0 = math.cos(angle) * r0
                z0 = math.sin(angle) * r0
                x1 = math.cos(angle) * r1
                z1 = math.sin(angle) * r1
                sv, sf = _iron_strap(x0, y0, z0, x1, y1, z1,
                                      width=bar_r * 2, thickness=bar_r * 2)
                start_v = sum(len(p[0]) for p in parts)
                cage_indices.extend(range(start_v, start_v + len(sv)))
                parts.append((sv, sf))

        # Horizontal rings at profile points
        for r, y in profile:
            rv, rf = _make_torus(0, y, 0, r, bar_r,
                                  major_seg=bar_count, minor_seg=4)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(rv)))
            parts.append((rv, rf))

        # Hanging hook
        hook_v, hook_f = _make_torus(0, height + 0.05, 0, 0.04, 0.008,
                                      major_seg=8, minor_seg=4)
        start_v = sum(len(p[0]) for p in parts)
        parts.append((hook_v, hook_f))

        vertex_groups["cage"] = cage_indices
        empties["hang_point"] = (0, height + 0.08, 0)
        empties["cage_center"] = (0, height * 0.5, 0)

    elif style == "animal_trap":
        # Box trap with spring-loaded door
        trap_h = height * 0.5
        trap_d = width * 1.5
        cage_indices = []

        # Frame bars (top, sides)
        # Top bars (along length)
        for bx in [-hd, hd]:
            bv, bf = _make_box(bx, trap_h, 0, bar_r, bar_r, trap_d / 2)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(bv)))
            parts.append((bv, bf))

        # Cross bars on top
        cross_count = max(4, int(trap_d / 0.2))
        for ci in range(cross_count):
            cz = -trap_d / 2 + (ci + 0.5) * trap_d / cross_count
            cv, cf = _make_box(0, trap_h, cz, hd, bar_r, bar_r * 0.8)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(cv)))
            parts.append((cv, cf))

        # Side bars
        side_bar_count = max(3, int(trap_d / 0.25))
        for side_x in [-hd, hd]:
            for sbi in range(side_bar_count):
                sz = -trap_d / 2 + (sbi + 0.5) * trap_d / side_bar_count
                sv, sf = _make_cylinder(side_x, 0, sz, bar_r, trap_h, segments=bar_seg)
                start_v = sum(len(p[0]) for p in parts)
                cage_indices.extend(range(start_v, start_v + len(sv)))
                parts.append((sv, sf))

        # Back wall (bars)
        for bbi in range(max(3, int(width / 0.2))):
            bx = -hd + (bbi + 0.5) * width / max(3, int(width / 0.2))
            bv, bf = _make_cylinder(bx, 0, -trap_d / 2, bar_r, trap_h, segments=bar_seg)
            start_v = sum(len(p[0]) for p in parts)
            cage_indices.extend(range(start_v, start_v + len(bv)))
            parts.append((bv, bf))

        # Floor
        fv, ff = _make_box(0, -0.01, 0, hd, 0.01, trap_d / 2)
        start_v = sum(len(p[0]) for p in parts)
        parts.append((fv, ff))

        # Drop door at front
        door_v, door_f = _make_box(0, trap_h / 2, trap_d / 2,
                                    hd - 0.01, trap_h / 2 - 0.01, bar_r * 2)
        start_v = sum(len(p[0]) for p in parts)
        door_indices = list(range(start_v, start_v + len(door_v)))
        parts.append((door_v, door_f))

        vertex_groups["cage"] = cage_indices
        vertex_groups["door"] = door_indices
        empties["door_hinge_top"] = (0, trap_h, trap_d / 2)
        empties["trigger_plate"] = (0, 0.01, 0)
        empties["trap_center"] = (0, trap_h / 2, 0)

    else:
        # Fallback to hanging_cage
        return generate_cage(style="hanging_cage", width=width, height=height)

    final_verts, final_faces = _merge_parts(*parts)

    # Lock mechanism (for styles with doors)
    if "door_hinge_top" in empties:
        empties["lock"] = (
            empties.get("door_hinge_top", (0, 0, 0))[0],
            empties.get("door_hinge_top", (0, 0, 0))[1] * 0.5,
            empties.get("door_hinge_top", (0, 0, 0))[2],
        )

    uvs = _generate_planar_uvs(final_verts, "xz")

    return _make_riggable_result(
        f"Cage_{style}",
        final_verts,
        final_faces,
        uvs=uvs,
        empties=empties,
        vertex_groups=vertex_groups,
        rig_info={
            "type": "cage",
            "style": style,
            "has_door": "door_hinge_top" in empties,
            "suspended": style in ("hanging_cage", "gibbet"),
        },
        category="cage",
    )
