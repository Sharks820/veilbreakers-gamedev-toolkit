"""AAA-quality building and architecture generators for dark fantasy.

Every surface has GEOMETRIC detail -- stone blocks are individual geometry
with mortar gaps, roof tiles are individual overlapping elements, timber
beams are proud 3D structure.  Nothing relies on textures alone.

Pure Python, no bpy -- fully testable without Blender.

Generators:
- generate_stone_wall: Stone block wall with mortar gaps (5 styles)
- generate_timber_frame: Exposed timber frame building (4 styles)
- generate_gothic_window: Gothic window with tracery and voussoirs
- generate_roof: Detailed roof with individual tiles/shingles (6 shapes, 4 materials)
- generate_staircase: Staircase with individual steps and railings (5 styles)
- generate_archway: Detailed stone archway with voussoirs (5 styles)
- generate_chimney: Chimney with brick/stone pattern and cap
- generate_interior_trim: Baseboard, crown molding, beams, floor planks, wainscoting
- generate_battlements: Castle wall with crenellations, machicolations, arrow loops

Helpers:
- _stone_block_grid: Running bond block layout
- _arch_curve: Parametric arch curve for any style
- _voussoir_blocks: Individual wedge-shaped arch stones
- _molding_profile_extrude: Profile extrusion along a path
- _shingle_row: One row of overlapping roof shingles
"""

from __future__ import annotations

import math
import random
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


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
        "height": max(zs) - min(zs),
        "depth": max(ys) - min(ys),
    }


def _make_result(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    material_ids: list[int] | None = None,
    components: list[str] | None = None,
    **extra_meta: Any,
) -> MeshSpec:
    dims = _compute_dimensions(vertices)
    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs or [],
        "material_ids": material_ids or [],
        "components": components or [],
        "metadata": {
            "name": name,
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "dimensions": dims,
            **extra_meta,
        },
    }


# ---------------------------------------------------------------------------
# Low-level primitives
# ---------------------------------------------------------------------------

def _box(
    x0: float, y0: float, z0: float,
    w: float, d: float, h: float,
    base: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Axis-aligned box from corner (x0,y0,z0) with size (w,d,h)."""
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    b = base
    faces = [
        (b, b + 3, b + 2, b + 1),
        (b + 4, b + 5, b + 6, b + 7),
        (b, b + 1, b + 5, b + 4),
        (b + 2, b + 3, b + 7, b + 6),
        (b, b + 4, b + 7, b + 3),
        (b + 1, b + 2, b + 6, b + 5),
    ]
    return verts, faces


def _merge(
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Merge multiple (verts, faces) into one mesh."""
    all_v: list[tuple[float, float, float]] = []
    all_f: list[tuple[int, ...]] = []
    for verts, faces in parts:
        off = len(all_v)
        all_v.extend(verts)
        for f in faces:
            all_f.append(tuple(i + off for i in f))
    return all_v, all_f


def _quad(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    p3: tuple[float, float, float],
    base: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Single quad face from 4 points."""
    return [p0, p1, p2, p3], [(base, base + 1, base + 2, base + 3)]


def _cylinder_ring(
    cx: float, cz: float, y: float,
    radius: float, segments: int,
) -> list[tuple[float, float, float]]:
    """Circle of points in XZ plane at height y."""
    pts = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        pts.append((cx + math.cos(a) * radius, y, cz + math.sin(a) * radius))
    return pts


def _cylinder(
    cx: float, y0: float, cz: float,
    radius: float, height: float,
    segments: int = 8,
    base: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Simple cylinder along Z axis (y0 to y0+height)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    bot = _cylinder_ring(cx, cz, y0, radius, segments)
    top = _cylinder_ring(cx, cz, y0 + height, radius, segments)
    verts.extend(bot)
    verts.extend(top)
    b = base
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((b + i, b + i2, b + segments + i2, b + segments + i))
    # caps
    faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))
    faces.append(tuple(b + segments + i for i in range(segments)))
    return verts, faces


# ---------------------------------------------------------------------------
# HELPER: Stone block grid
# ---------------------------------------------------------------------------

def _stone_block_grid(
    width: float,
    height: float,
    block_w: float,
    block_h: float,
    mortar_gap: float,
    variation: float,
    offset_alternate: bool = True,
    seed: int = 42,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], int]:
    """Generate a grid of stone blocks in a running bond pattern.

    Each block is a quad at z=0 (the proud face), and the mortar sits at
    z=-mortar_depth behind them.  Returns (verts, faces, block_count).
    Blocks are in XZ plane: x is width, z is height (wall facing -Y).
    Actually we produce blocks as flat quads at depth=0 and mortar at
    depth=-mortar_gap.  Caller wraps into 3D wall.
    """
    rng = random.Random(seed)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    block_count = 0

    z = 0.0
    row = 0
    while z < height:
        bh = block_h + rng.uniform(-block_h * variation * 0.3, block_h * variation * 0.3)
        bh = max(bh, block_h * 0.5)
        if z + bh > height:
            bh = height - z
        if bh < 0.005:
            break

        x_offset = 0.0
        if offset_alternate and row % 2 == 1:
            x_offset = block_w * 0.5 + rng.uniform(-block_w * variation * 0.1,
                                                      block_w * variation * 0.1)

        x = -x_offset
        while x < width:
            bw = block_w + rng.uniform(-block_w * variation, block_w * variation)
            bw = max(bw, block_w * 0.4)

            # Clamp to wall width
            x_start = max(0.0, x)
            x_end = min(width, x + bw)
            actual_w = x_end - x_start
            if actual_w < 0.01:
                x += bw + mortar_gap
                continue

            # Slight random inset per block for organic feel
            depth_var = rng.uniform(0.0, mortar_gap * 0.3)

            b = len(verts)
            verts.extend([
                (x_start + mortar_gap * 0.5, -depth_var, z + mortar_gap * 0.5),
                (x_end - mortar_gap * 0.5, -depth_var, z + mortar_gap * 0.5),
                (x_end - mortar_gap * 0.5, -depth_var, z + bh - mortar_gap * 0.5),
                (x_start + mortar_gap * 0.5, -depth_var, z + bh - mortar_gap * 0.5),
            ])
            faces.append((b, b + 1, b + 2, b + 3))
            block_count += 1

            x += bw + mortar_gap
        z += bh + mortar_gap
        row += 1

    return verts, faces, block_count


# ---------------------------------------------------------------------------
# HELPER: Arch curve
# ---------------------------------------------------------------------------

def _arch_curve(
    width: float,
    height: float,
    style: str = "gothic_pointed",
    num_points: int = 16,
) -> list[tuple[float, float]]:
    """Generate arch curve points (x, z) from left to right.

    The arch spans x in [-width/2, +width/2] with the base at z=0
    and the peak at z=height.
    """
    hw = width / 2.0
    pts: list[tuple[float, float]] = []

    if style == "roman_round" or style == "round_arch":
        # Elliptical arc: half-width horizontally, full height vertically
        for i in range(num_points + 1):
            t = math.pi * i / num_points
            x = -math.cos(t) * hw
            z = math.sin(t) * height
            pts.append((x, z))

    elif style == "gothic_pointed" or style == "pointed_arch":
        # Two arcs meeting at a point, centres offset inward
        # Each arc has its centre on the opposite side
        offset = hw * 0.3  # how "pointed" the arch is
        r = math.sqrt((hw + offset) ** 2 + height ** 2)
        half_pts = num_points // 2

        # Left arc (centre at +offset, z=0)
        for i in range(half_pts + 1):
            t = i / half_pts
            # Angle from centre (+offset, 0) to left base (-hw, 0) and up to peak (0, height)
            a_start = math.atan2(0.0, -hw - offset)
            a_end = math.atan2(height, -offset)
            angle = a_start + t * (a_end - a_start)
            x = offset + r * math.cos(angle)
            z = r * math.sin(angle)
            z = max(0.0, z)
            pts.append((x, z))

        # Right arc (centre at -offset, z=0)
        for i in range(1, half_pts + 1):
            t = i / half_pts
            a_start = math.atan2(height, offset)
            a_end = math.atan2(0.0, hw + offset)
            angle = a_start + t * (a_end - a_start)
            x = -offset + r * math.cos(angle)
            z = r * math.sin(angle)
            z = max(0.0, z)
            pts.append((x, z))

    elif style == "horseshoe":
        # More than semicircle, extends below spring line
        # Scale horizontally by hw*1.1, vertically by height
        rx = hw * 1.1
        for i in range(num_points + 1):
            t = -0.15 * math.pi + (1.3 * math.pi) * i / num_points
            x = -math.cos(t) * rx
            z = math.sin(t) * height
            pts.append((x, max(0.0, z)))

    elif style == "ogee":
        # S-curve pointed arch
        half_pts = num_points // 2
        for i in range(half_pts + 1):
            t = i / half_pts
            # Lower convex part
            if t < 0.5:
                t2 = t * 2.0
                x = -hw + t2 * hw * 0.6
                z = (math.sin(t2 * math.pi / 2)) * height * 0.5
            else:
                # Upper concave part
                t2 = (t - 0.5) * 2.0
                x = -hw * 0.4 + t2 * hw * 0.4
                z = height * 0.5 + (math.sin(t2 * math.pi / 2)) * height * 0.5
            pts.append((x, z))
        # Mirror for right side
        mirrored = [(- p[0], p[1]) for p in reversed(pts[:-1])]
        pts.extend(mirrored)

    elif style == "flat_lintel":
        # Simple flat top
        pts = [(-hw, 0.0), (-hw, height), (hw, height), (hw, 0.0)]

    elif style == "lancet":
        # Very tall narrow pointed arch -- like gothic but taller
        offset = hw * 0.6
        r = math.sqrt((hw + offset) ** 2 + height ** 2)
        half_pts = num_points // 2
        for i in range(half_pts + 1):
            t = i / half_pts
            a_start = math.atan2(0.0, -hw - offset)
            a_end = math.atan2(height, -offset)
            angle = a_start + t * (a_end - a_start)
            x = offset + r * math.cos(angle)
            z = r * math.sin(angle)
            z = max(0.0, z)
            pts.append((x, z))
        for i in range(1, half_pts + 1):
            t = i / half_pts
            a_start = math.atan2(height, offset)
            a_end = math.atan2(0.0, hw + offset)
            angle = a_start + t * (a_end - a_start)
            x = -offset + r * math.cos(angle)
            z = r * math.sin(angle)
            z = max(0.0, z)
            pts.append((x, z))

    else:
        # Default rectangular
        pts = [(-hw, 0.0), (-hw, height), (hw, height), (hw, 0.0)]

    return pts


# ---------------------------------------------------------------------------
# HELPER: Voussoir blocks (arch stones)
# ---------------------------------------------------------------------------

def _voussoir_blocks(
    arch_points: list[tuple[float, float]],
    depth: float,
    block_count: int = 9,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], int]:
    """Generate individual wedge-shaped arch stones from arch curve points.

    Each voussoir is a 3D wedge: inner face on the intrados, outer face
    on the extrados.  The keystone (middle block) is slightly larger.

    Returns (verts, faces, voussoir_count).
    """
    if len(arch_points) < 3:
        return [], [], 0

    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Resample arch to block_count+1 evenly spaced points
    total_len = 0.0
    seg_lengths = []
    for i in range(len(arch_points) - 1):
        dx = arch_points[i + 1][0] - arch_points[i][0]
        dz = arch_points[i + 1][1] - arch_points[i][1]
        seg_lengths.append(math.sqrt(dx * dx + dz * dz))
        total_len += seg_lengths[-1]

    if total_len < 1e-6:
        return [], [], 0

    # Generate evenly spaced parameter values
    even_pts: list[tuple[float, float]] = []
    for bi in range(block_count + 1):
        target = (bi / block_count) * total_len
        accum = 0.0
        for si, sl in enumerate(seg_lengths):
            if accum + sl >= target - 1e-9:
                t = (target - accum) / sl if sl > 1e-9 else 0.0
                t = max(0.0, min(1.0, t))
                x = arch_points[si][0] + t * (arch_points[si + 1][0] - arch_points[si][0])
                z = arch_points[si][1] + t * (arch_points[si + 1][1] - arch_points[si][1])
                even_pts.append((x, z))
                break
            accum += sl
        else:
            even_pts.append(arch_points[-1])

    voussoir_thickness = depth * 0.3  # how thick the voussoir ring is

    keystone_idx = block_count // 2
    count = 0

    for bi in range(block_count):
        x0, z0 = even_pts[bi]
        x1, z1 = even_pts[bi + 1]

        # Compute outward normal for this segment
        dx = x1 - x0
        dz = z1 - z0
        seg_len = math.sqrt(dx * dx + dz * dz)
        if seg_len < 1e-9:
            continue
        nx = -dz / seg_len
        nz = dx / seg_len

        # Keystone is slightly thicker
        thickness = voussoir_thickness
        if bi == keystone_idx:
            thickness *= 1.3

        # Inner face (intrados) - 4 points
        # Outer face (extrados) - 4 points
        b = len(verts)

        # Front face (y=0) and back face (y=depth)
        for y_val in [0.0, depth]:
            verts.append((x0, y_val, z0))                              # inner start
            verts.append((x1, y_val, z1))                              # inner end
            verts.append((x1 + nx * thickness, y_val, z1 + nz * thickness))  # outer end
            verts.append((x0 + nx * thickness, y_val, z0 + nz * thickness))  # outer start

        # 8 verts per voussoir: 0-3 front, 4-7 back
        # Front face
        faces.append((b, b + 1, b + 2, b + 3))
        # Back face
        faces.append((b + 7, b + 6, b + 5, b + 4))
        # Inner face (intrados)
        faces.append((b, b + 4, b + 5, b + 1))
        # Outer face (extrados)
        faces.append((b + 3, b + 2, b + 6, b + 7))
        # Left end
        faces.append((b, b + 3, b + 7, b + 4))
        # Right end
        faces.append((b + 1, b + 5, b + 6, b + 2))

        count += 1

    return verts, faces, count


# ---------------------------------------------------------------------------
# HELPER: Molding profile extrusion
# ---------------------------------------------------------------------------

def _molding_profile_extrude(
    profile_points: list[tuple[float, float]],
    path_points: list[tuple[float, float, float]],
    base: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Extrude a 2D profile along a 3D path.

    Profile is in local (right, up) space relative to path direction.
    For straight horizontal paths along X, right=Y, up=Z.
    """
    if len(path_points) < 2 or len(profile_points) < 2:
        return [], []

    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n_prof = len(profile_points)

    for pi, pp in enumerate(path_points):
        # Compute tangent
        if pi == 0:
            tang = (
                path_points[1][0] - pp[0],
                path_points[1][1] - pp[1],
                path_points[1][2] - pp[2],
            )
        elif pi == len(path_points) - 1:
            tang = (
                pp[0] - path_points[pi - 1][0],
                pp[1] - path_points[pi - 1][1],
                pp[2] - path_points[pi - 1][2],
            )
        else:
            tang = (
                path_points[pi + 1][0] - path_points[pi - 1][0],
                path_points[pi + 1][1] - path_points[pi - 1][1],
                path_points[pi + 1][2] - path_points[pi - 1][2],
            )

        tl = math.sqrt(tang[0] ** 2 + tang[1] ** 2 + tang[2] ** 2)
        if tl < 1e-9:
            tang = (1.0, 0.0, 0.0)
            tl = 1.0
        tang = (tang[0] / tl, tang[1] / tl, tang[2] / tl)

        # Simple basis: up = Z if tangent is mostly horizontal
        up = (0.0, 0.0, 1.0)
        # Right = tangent x up
        right = (
            tang[1] * up[2] - tang[2] * up[1],
            tang[2] * up[0] - tang[0] * up[2],
            tang[0] * up[1] - tang[1] * up[0],
        )
        rl = math.sqrt(right[0] ** 2 + right[1] ** 2 + right[2] ** 2)
        if rl < 1e-9:
            right = (0.0, 1.0, 0.0)
            rl = 1.0
        right = (right[0] / rl, right[1] / rl, right[2] / rl)

        # Recompute up for orthogonality
        up = (
            right[1] * tang[2] - right[2] * tang[1],
            right[2] * tang[0] - right[0] * tang[2],
            right[0] * tang[1] - right[1] * tang[0],
        )

        for pr, pu in profile_points:
            verts.append((
                pp[0] + right[0] * pr + up[0] * pu,
                pp[1] + right[1] * pr + up[1] * pu,
                pp[2] + right[2] * pr + up[2] * pu,
            ))

    b = base
    for pi in range(len(path_points) - 1):
        for qi in range(n_prof - 1):
            v0 = b + pi * n_prof + qi
            v1 = b + pi * n_prof + qi + 1
            v2 = b + (pi + 1) * n_prof + qi + 1
            v3 = b + (pi + 1) * n_prof + qi
            faces.append((v0, v3, v2, v1))

    return verts, faces


# ---------------------------------------------------------------------------
# HELPER: Shingle row
# ---------------------------------------------------------------------------

def _shingle_row(
    width: float,
    row_y: float,
    shingle_w: float,
    shingle_h: float,
    overlap: float,
    variation: float,
    row_index: int = 0,
    seed: int = 42,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], int]:
    """Generate one row of overlapping roof shingles.

    Shingles are quads in the XZ plane with slight random variation.
    Each shingle is a separate quad so it catches light individually.
    Returns (verts, faces, shingle_count).
    """
    rng = random.Random(seed + row_index * 997)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    count = 0

    # Stagger alternate rows
    x_offset = (shingle_w * 0.5) if (row_index % 2 == 1) else 0.0
    x = -x_offset

    while x < width:
        sw = shingle_w + rng.uniform(-shingle_w * variation, shingle_w * variation)
        sw = max(sw, shingle_w * 0.5)

        x_start = max(0.0, x)
        x_end = min(width, x + sw)
        actual_w = x_end - x_start
        if actual_w < 0.005:
            x += sw
            continue

        # Slight random tilt and depth offset per shingle
        z_var = rng.uniform(-0.002, 0.002)
        y_var = rng.uniform(-0.003, 0.003)

        b = len(verts)
        verts.extend([
            (x_start, y_var, row_y + z_var),
            (x_end, y_var, row_y + z_var),
            (x_end, y_var - 0.005, row_y + shingle_h + z_var),
            (x_start, y_var - 0.005, row_y + shingle_h + z_var),
        ])
        faces.append((b, b + 1, b + 2, b + 3))
        count += 1
        x += sw
    return verts, faces, count


# ===================================================================
# GENERATOR 1: Stone Wall with Block Pattern
# ===================================================================

def generate_stone_wall(
    width: float = 4.0,
    height: float = 3.0,
    thickness: float = 0.4,
    block_style: str = "ashlar",
    mortar_depth: float = 0.005,
    block_variation: float = 0.3,
    seed: int = 42,
) -> MeshSpec:
    """Generate wall with visible stone blocks and mortar lines.

    Styles:
    - 'ashlar': Regular rectangular blocks in courses (grand buildings)
    - 'rubble': Irregular stones of varying sizes (peasant buildings)
    - 'coursed_rubble': Irregular stones in rough horizontal courses
    - 'cyclopean': Very large irregular blocks (ancient/megalithic)
    - 'brick': Small regular bricks in running bond pattern

    The wall is a solid slab with block faces proud of the mortar base.
    Each block is individual geometry -- mortar gaps are real 3D depth
    that catches light.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Block size by style
    style_block_sizes = {
        "ashlar": (0.5, 0.25),
        "rubble": (0.3, 0.2),
        "coursed_rubble": (0.35, 0.22),
        "cyclopean": (0.8, 0.5),
        "brick": (0.22, 0.065),
    }
    block_w, block_h = style_block_sizes.get(block_style, (0.5, 0.25))

    # Mortar gap
    mortar_gap = mortar_depth * 2

    # Variation by style
    style_variation = {
        "ashlar": block_variation * 0.3,
        "rubble": block_variation * 1.5,
        "coursed_rubble": block_variation * 0.8,
        "cyclopean": block_variation * 0.5,
        "brick": block_variation * 0.1,
    }
    var = style_variation.get(block_style, block_variation)

    rng = random.Random(seed)

    # 1. Mortar base slab (the recessed surface behind block faces)
    base_v, base_f = _box(0.0, 0.0, 0.0, width, thickness, height)
    parts.append((base_v, base_f))

    # 2. Front face blocks -- proud of base by mortar_depth
    front_v, front_f, front_count = _stone_block_grid(
        width, height, block_w, block_h, mortar_gap, var,
        offset_alternate=(block_style != "rubble"),
        seed=seed,
    )
    # Offset front blocks to sit proud of front face (y=0)
    front_v_3d = []
    for x, y, z in front_v:
        front_v_3d.append((x, y - mortar_depth, z))
    parts.append((front_v_3d, front_f))

    # 3. Back face blocks
    back_v, back_f, back_count = _stone_block_grid(
        width, height, block_w, block_h, mortar_gap, var,
        offset_alternate=(block_style != "rubble"),
        seed=seed + 1000,
    )
    back_v_3d = []
    for x, y, z in back_v:
        back_v_3d.append((x, thickness - y + mortar_depth, z))
    parts.append((back_v_3d, back_f))

    # 4. For ashlar/cyclopean: add corner interlocking stones
    if block_style in ("ashlar", "cyclopean"):
        corner_depth = block_w * 0.6
        z = 0.0
        row = 0
        while z < height:
            ch = block_h + rng.uniform(-block_h * 0.1, block_h * 0.1)
            if z + ch > height:
                ch = height - z
            if ch < 0.005:
                break

            # Left corner: alternate between long-on-front and long-on-side
            if row % 2 == 0:
                cv, cf = _box(-corner_depth * 0.3, -mortar_depth, z,
                              corner_depth * 0.3, thickness + mortar_depth * 2, ch)
            else:
                cv, cf = _box(0.0, -mortar_depth, z,
                              block_w * 0.3, thickness + mortar_depth * 2, ch)
            parts.append((cv, cf))

            # Right corner
            if row % 2 == 1:
                cv, cf = _box(width, -mortar_depth, z,
                              corner_depth * 0.3, thickness + mortar_depth * 2, ch)
            else:
                cv, cf = _box(width - block_w * 0.3, -mortar_depth, z,
                              block_w * 0.3, thickness + mortar_depth * 2, ch)
            parts.append((cv, cf))

            z += ch + mortar_gap
            row += 1

    # Build material_ids: part 0 = mortar base slab (slot 0), all block/corner parts = stone (slot 1)
    mat_ids: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    total_blocks = front_count + back_count
    return _make_result(
        f"stone_wall_{block_style}",
        all_v, all_f,
        material_ids=mat_ids,
        block_style=block_style,
        block_count=total_blocks,
        mortar_depth=mortar_depth,
        generator="building_quality",
    )


# ===================================================================
# GENERATOR 2: Timber Frame Structure
# ===================================================================

def generate_timber_frame(
    width: float = 5.0,
    height: float = 3.0,
    depth: float = 4.0,
    frame_style: str = "medieval",
    beam_width: float = 0.15,
    beam_depth: float = 0.15,
    seed: int = 42,
) -> MeshSpec:
    """Generate exposed timber frame building.

    Styles: 'medieval' (cross-bracing), 'tudor' (decorative patterns),
            'japanese' (post-and-beam), 'barn' (heavy timber)

    Features:
    - Structural posts at corners and wall divisions
    - Horizontal beams (sill, wall plate, tie beam)
    - Diagonal braces in each panel
    - Infill panels between beams (plaster/wattle for medieval)
    - Beams extend beyond wall surface (proud structure)
    - Tenon joint detail at beam intersections
    - Beams have slight bow for organic aged feel
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    bw = beam_width
    bd = beam_depth
    proud = bd * 0.4  # how far beams protrude beyond infill

    style_configs = {
        "medieval": {"panel_divisions": 2, "has_cross_brace": True, "has_infill": True,
                     "beam_bow": 0.005},
        "tudor": {"panel_divisions": 3, "has_cross_brace": True, "has_infill": True,
                  "beam_bow": 0.003, "decorative_pattern": True},
        "japanese": {"panel_divisions": 2, "has_cross_brace": False, "has_infill": True,
                     "beam_bow": 0.002},
        "barn": {"panel_divisions": 1, "has_cross_brace": True, "has_infill": False,
                 "beam_bow": 0.008, "heavy_factor": 1.5},
    }
    config = style_configs.get(frame_style, style_configs["medieval"])

    heavy = config.get("heavy_factor", 1.0)
    bw *= heavy
    bd *= heavy
    proud *= heavy
    bow = config.get("beam_bow", 0.005)

    divisions = config["panel_divisions"]
    panel_width = (width - (divisions + 1) * bw) / divisions

    # Helper to add bow to a beam
    def _bowed_box(x0, y0, z0, w, d, h, bow_amount=0.0):
        """Box with optional midpoint bow (Y axis)."""
        if abs(bow_amount) < 1e-6 or (w < bw * 2 and h < bw * 2):
            return _box(x0, y0, z0, w, d, h)
        # Split into 3 segments with mid segment bowed
        seg_parts = []
        if w > h:  # horizontal beam -- bow along X
            seg_w = w / 3.0
            for si in range(3):
                by = bow_amount * math.sin(math.pi * (si + 0.5) / 3.0) if si == 1 else 0.0
                sv, sf = _box(x0 + si * seg_w, y0 + by, z0, seg_w, d, h)
                seg_parts.append((sv, sf))
        else:  # vertical beam -- bow along Z
            seg_h = h / 3.0
            for si in range(3):
                by = bow_amount * math.sin(math.pi * (si + 0.5) / 3.0) if si == 1 else 0.0
                sv, sf = _box(x0, y0 + by, z0 + si * seg_h, w, d, seg_h)
                seg_parts.append((sv, sf))
        return _merge(seg_parts)

    bow_val = rng.uniform(bow * 0.5, bow * 1.5)

    # === Front wall frame ===

    # Sill beam (bottom horizontal)
    sv, sf = _bowed_box(0.0, -proud, 0.0, width, bd + proud, bw, bow_val)
    parts.append((sv, sf))

    # Wall plate (top horizontal)
    sv, sf = _bowed_box(0.0, -proud, height - bw, width, bd + proud, bw,
                        rng.uniform(bow * 0.5, bow * 1.5))
    parts.append((sv, sf))

    # Mid rail (horizontal at ~mid height)
    mid_z = height * 0.5 - bw * 0.5
    sv, sf = _bowed_box(0.0, -proud, mid_z, width, bd + proud, bw,
                        rng.uniform(bow * 0.5, bow * 1.5))
    parts.append((sv, sf))

    # Vertical posts
    for pi in range(divisions + 1):
        px = pi * (panel_width + bw)
        sv, sf = _bowed_box(px, -proud, 0.0, bw, bd + proud, height,
                            rng.uniform(bow * 0.5, bow * 1.5))
        parts.append((sv, sf))

    # Centre post in each panel (for tudor)
    if frame_style == "tudor" or divisions >= 3:
        for pi in range(divisions):
            cx = pi * (panel_width + bw) + bw + panel_width * 0.5 - bw * 0.25
            sv, sf = _box(cx, -proud, 0.0, bw * 0.5, bd + proud, height)
            parts.append((sv, sf))

    # Diagonal braces
    if config["has_cross_brace"]:
        brace_w = bw * 0.7
        brace_d = bd * 0.7
        for pi in range(divisions):
            px = pi * (panel_width + bw) + bw
            # Lower panel: brace from bottom-left to mid-right
            # Approximate as a series of small boxes along diagonal
            n_segs = 4
            for si in range(n_segs):
                t0 = si / n_segs
                t1 = (si + 1) / n_segs
                sx = px + t0 * panel_width
                sz = bw + t0 * (mid_z - bw)
                ex = px + t1 * panel_width
                ez = bw + t1 * (mid_z - bw)
                seg_w = ex - sx
                seg_h = ez - sz
                sv, sf = _box(sx, -proud * 0.5, sz, seg_w, brace_d, max(seg_h, 0.01))
                parts.append((sv, sf))

            # Upper panel: opposite diagonal
            for si in range(n_segs):
                t0 = si / n_segs
                t1 = (si + 1) / n_segs
                sx = px + panel_width - t0 * panel_width
                sz = mid_z + bw + t0 * (height - bw - mid_z - bw)
                ex = px + panel_width - t1 * panel_width
                ez = mid_z + bw + t1 * (height - bw - mid_z - bw)
                seg_w = abs(ex - sx)
                seg_h = abs(ez - sz)
                sv, sf = _box(min(sx, ex), -proud * 0.5, min(sz, ez),
                              max(seg_w, 0.01), brace_d, max(seg_h, 0.01))
                parts.append((sv, sf))

    # Infill panels (recessed behind beams)
    if config.get("has_infill", True):
        infill_thickness = bd * 0.3
        for pi in range(divisions):
            px = pi * (panel_width + bw) + bw
            # Lower infill
            iv, if_ = _box(px, 0.0, bw, panel_width, infill_thickness,
                           mid_z - bw)
            parts.append((iv, if_))
            # Upper infill
            iv, if_ = _box(px, 0.0, mid_z + bw, panel_width, infill_thickness,
                           height - bw - mid_z - bw)
            parts.append((iv, if_))

    # Tenon joint pegs at intersections (small protruding cylinders)
    peg_r = bw * 0.12
    peg_h = proud * 0.8
    for pi in range(divisions + 1):
        px = pi * (panel_width + bw) + bw * 0.5
        for tz in [bw * 0.5, mid_z + bw * 0.5, height - bw * 0.5]:
            cv, cf = _cylinder(px, -proud - peg_h * 0.3, 0.0, peg_r, peg_h, 6)
            # Reposition Z
            cv = [(v[0], v[1], tz) for v in cv]
            parts.append((cv, cf))

    # === Back wall frame (offset by depth) ===
    # Sill
    sv, sf = _box(0.0, depth - bd, 0.0, width, bd + proud, bw)
    parts.append((sv, sf))
    # Wall plate
    sv, sf = _box(0.0, depth - bd, height - bw, width, bd + proud, bw)
    parts.append((sv, sf))

    # === Side beams connecting front to back ===
    # Bottom side beams
    for sx in [0.0, width - bw]:
        sv, sf = _box(sx, 0.0, 0.0, bw, depth, bw)
        parts.append((sv, sf))
    # Top side beams
    for sx in [0.0, width - bw]:
        sv, sf = _box(sx, 0.0, height - bw, bw, depth, bw)
        parts.append((sv, sf))

    all_v, all_f = _merge(parts)

    return _make_result(
        f"timber_frame_{frame_style}",
        all_v, all_f,
        frame_style=frame_style,
        beam_proud=proud,
        generator="building_quality",
    )


# ===================================================================
# GENERATOR 3: Gothic Window
# ===================================================================

def generate_gothic_window(
    width: float = 0.8,
    height: float = 1.5,
    style: str = "pointed_arch",
    tracery: bool = True,
    has_shutters: bool = False,
    has_sill: bool = True,
    frame_depth: float = 0.15,
    seed: int = 42,
) -> MeshSpec:
    """Generate detailed gothic window with tracery and voussoirs.

    Styles: 'pointed_arch', 'round_arch', 'lancet', 'rose_window',
            'rectangular', 'arrow_slit'

    Components: frame, arch, mullions, tracery, sill, shutters, glass pane areas.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []
    hw = width / 2.0

    # Frame thickness
    frame_w = 0.05  # width of frame stone surround
    chamfer = 0.015  # inner chamfer

    # Stone frame surround
    # Left jamb
    jv, jf = _box(-hw - frame_w, 0.0, 0.0, frame_w, frame_depth, height * 0.7)
    parts.append((jv, jf))
    components.append("frame_left_jamb")

    # Right jamb
    jv, jf = _box(hw, 0.0, 0.0, frame_w, frame_depth, height * 0.7)
    parts.append((jv, jf))
    components.append("frame_right_jamb")

    # Chamfered inner edge (smaller boxes along inner frame edge)
    for side_x in [-hw, hw - chamfer]:
        cv, cf = _box(side_x, frame_depth * 0.3, 0.0, chamfer, frame_depth * 0.4, height * 0.7)
        parts.append((cv, cf))

    # Arch (voussoirs)
    arch_height = height * 0.3
    if style in ("pointed_arch", "lancet"):
        arch_style = "gothic_pointed" if style == "pointed_arch" else "lancet"
    elif style == "round_arch":
        arch_style = "roman_round"
    elif style == "rose_window":
        arch_style = "roman_round"
    elif style == "arrow_slit":
        arch_style = "gothic_pointed"
    else:
        arch_style = "flat_lintel"

    arch_pts = _arch_curve(width, arch_height, arch_style, num_points=20)

    # Offset arch points up to sit on top of jambs
    arch_base_z = height * 0.7
    arch_pts_3d = [(p[0], p[1] + arch_base_z) for p in arch_pts]

    # Voussoir blocks
    voussoir_count = 11 if style != "arrow_slit" else 5
    # Convert 2D arch to 3D for voussoir generation
    av, af, v_count = _voussoir_blocks(arch_pts_3d, frame_depth, voussoir_count)
    if av:
        parts.append((av, af))
        components.append("arch_voussoirs")

    # Mullions (vertical stone dividers)
    if style != "arrow_slit" and width > 0.4:
        mullion_count = 1 if width < 0.8 else 2
        mullion_w = 0.03
        mullion_d = frame_depth * 0.6
        for mi in range(mullion_count):
            mx = -hw + (mi + 1) * width / (mullion_count + 1) - mullion_w * 0.5
            mv, mf = _box(mx, frame_depth * 0.2, 0.0, mullion_w, mullion_d, height * 0.7)
            parts.append((mv, mf))
            components.append(f"mullion_{mi}")

    # Tracery (decorative stone patterns in arch area)
    if tracery and style not in ("rectangular", "arrow_slit") and arch_height > 0.1:
        # Trefoil: three overlapping circles approximated as hexagonal rings
        trac_r = arch_height * 0.2
        trac_w = 0.02
        centre_z = arch_base_z + arch_height * 0.5

        # Central circle ring
        n_seg = 6
        for i in range(n_seg):
            a0 = 2.0 * math.pi * i / n_seg
            a1 = 2.0 * math.pi * (i + 1) / n_seg
            x0t = math.cos(a0) * trac_r
            z0t = centre_z + math.sin(a0) * trac_r
            x1t = math.cos(a1) * trac_r
            z1t = centre_z + math.sin(a1) * trac_r
            tv, tf = _box(min(x0t, x1t), frame_depth * 0.3,
                          min(z0t, z1t),
                          abs(x1t - x0t) + trac_w,
                          trac_w,
                          abs(z1t - z0t) + trac_w)
            parts.append((tv, tf))
        components.append("tracery")

        # Side lobes (for trefoil)
        for lobe_x_sign in [-1, 1]:
            lobe_cx = lobe_x_sign * trac_r * 0.8
            for i in range(n_seg):
                a0 = 2.0 * math.pi * i / n_seg
                a1 = 2.0 * math.pi * (i + 1) / n_seg
                lr = trac_r * 0.6
                x0t = lobe_cx + math.cos(a0) * lr
                z0t = centre_z + math.sin(a0) * lr
                x1t = lobe_cx + math.cos(a1) * lr
                z1t = centre_z + math.sin(a1) * lr
                tv, tf = _box(
                    min(x0t, x1t), frame_depth * 0.3,
                    min(z0t, z1t),
                    abs(x1t - x0t) + trac_w * 0.5,
                    trac_w,
                    abs(z1t - z0t) + trac_w * 0.5)
                parts.append((tv, tf))

    # Sill
    if has_sill:
        sill_projection = 0.04
        sill_h = 0.03
        sv, sf = _box(-hw - frame_w - sill_projection, -sill_projection, -sill_h,
                       width + 2 * (frame_w + sill_projection), frame_depth + sill_projection * 2,
                       sill_h)
        parts.append((sv, sf))
        components.append("sill")

    # Glass pane (thin transparent quad)
    glass_y = frame_depth * 0.5
    gv = [
        (-hw + frame_w, glass_y, 0.0),
        (hw - frame_w, glass_y, 0.0),
        (hw - frame_w, glass_y, height * 0.7),
        (-hw + frame_w, glass_y, height * 0.7),
    ]
    gf = [(0, 1, 2, 3)]
    parts.append((gv, gf))
    components.append("glass_pane")

    # Shutters
    if has_shutters:
        shutter_w = hw + frame_w
        shutter_h = height * 0.7
        shutter_thickness = 0.025
        plank_count = 4
        plank_h = shutter_h / plank_count
        plank_gap = 0.003

        for side, sx in [("left", -hw - frame_w - shutter_w),
                         ("right", hw + frame_w)]:
            for pi in range(plank_count):
                pz = pi * plank_h + plank_gap
                ph = plank_h - plank_gap * 2
                sv, sf = _box(sx, 0.0, pz, shutter_w, shutter_thickness, ph)
                parts.append((sv, sf))
            # Cross brace on shutter
            sv, sf = _box(sx + shutter_w * 0.1, shutter_thickness,
                          shutter_h * 0.2,
                          shutter_w * 0.8, shutter_thickness * 0.5,
                          shutter_h * 0.6)
            parts.append((sv, sf))
            components.append(f"shutter_{side}")

    # Build material_ids: slot 0 = frame/jamb/sill (structural), slot 1 = tracery/voussoir/shutter (detail)
    mat_ids_win: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids_win.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    # Check arch symmetry: mirror left/right of arch points
    arch_symmetric = True
    n_pts = len(arch_pts)
    for i in range(n_pts // 2):
        lx, lz = arch_pts[i]
        rx, rz = arch_pts[n_pts - 1 - i]
        if abs(lx + rx) > 0.05 or abs(lz - rz) > 0.05:
            arch_symmetric = False
            break

    return _make_result(
        f"gothic_window_{style}",
        all_v, all_f,
        components=components,
        material_ids=mat_ids_win,
        style=style,
        has_tracery=tracery,
        has_shutters=has_shutters,
        has_sill=has_sill,
        arch_symmetric=arch_symmetric,
        voussoir_count=v_count,
        generator="building_quality",
    )


# ===================================================================
# GENERATOR 4: Detailed Roof
# ===================================================================

def generate_roof(
    width: float = 6.0,
    depth: float = 5.0,
    pitch: float = 45.0,
    style: str = "gable",
    material: str = "tile",
    overhang: float = 0.3,
    seed: int = 42,
) -> MeshSpec:
    """Generate roof with individual tile/shingle rows.

    Roof styles: 'gable', 'hip', 'gambrel', 'mansard', 'shed', 'conical_tower'
    Materials: 'tile', 'shingle', 'slate', 'thatch'
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []

    pitch_rad = math.radians(pitch)
    ridge_height = (width / 2.0) * math.tan(pitch_rad)

    # Material-specific tile sizes
    tile_sizes = {
        "tile": (0.25, 0.18),       # w, h (visible portion)
        "shingle": (0.15, 0.12),
        "slate": (0.30, 0.22),
        "thatch": (0.10, 0.30),     # thatch bundles
    }
    tile_w, tile_h = tile_sizes.get(material, (0.25, 0.18))

    # Roof base structure (rafters)
    rafter_w = 0.06
    rafter_d = 0.08
    rafter_count = max(2, int(depth / 0.6))
    total_tiles = 0

    total_w = width + 2 * overhang
    half_w = total_w / 2.0

    if style == "gable":
        # Two sloping surfaces meeting at ridge
        slope_len = half_w / math.cos(pitch_rad)
        slope_rise = half_w * math.tan(pitch_rad)

        # Left slope tiles
        row_count = max(1, int(slope_len / tile_h))
        total_tiles = 0
        for ri in range(row_count):
            row_z_frac = ri / row_count
            # Position along slope
            slope_x = -half_w + row_z_frac * half_w
            slope_z = row_z_frac * slope_rise
            y_start = -overhang

            sv, sf, sc = _shingle_row(
                depth + 2 * overhang, 0.0, tile_w, tile_h, tile_h * 0.5,
                0.1, row_index=ri, seed=seed + ri,
            )
            # Transform: rotate to slope angle and position
            cos_p = math.cos(pitch_rad)
            sin_p = math.sin(pitch_rad)
            transformed_v = []
            for vx, vy, vz in sv:
                # vx = along depth, vy = thickness, vz = along slope
                # Map to world:
                wx = slope_x + vz * cos_p  # negative cos for left slope
                wy = vx - overhang
                wz = slope_z + vz * sin_p + vy
                transformed_v.append((wx, wy, wz))
            parts.append((transformed_v, sf))
            total_tiles += sc

        # Right slope tiles (mirror)
        for ri in range(row_count):
            row_z_frac = ri / row_count
            slope_x = half_w - row_z_frac * half_w
            slope_z = row_z_frac * slope_rise

            sv, sf, sc = _shingle_row(
                depth + 2 * overhang, 0.0, tile_w, tile_h, tile_h * 0.5,
                0.1, row_index=ri + 1000, seed=seed + ri + 1000,
            )
            transformed_v = []
            cos_p = math.cos(pitch_rad)
            sin_p = math.sin(pitch_rad)
            for vx, vy, vz in sv:
                wx = slope_x - vz * cos_p
                wy = vx - overhang
                wz = slope_z + vz * sin_p + vy
                transformed_v.append((wx, wy, wz))
            parts.append((transformed_v, sf))
            total_tiles += sc

        components.append("left_slope_tiles")
        components.append("right_slope_tiles")

        # Ridge tiles along peak
        ridge_z = slope_rise
        ridge_tile_w = tile_w * 1.5
        ridge_y = -overhang
        while ridge_y < depth + overhang:
            rv, rf = _box(-ridge_tile_w * 0.3, ridge_y, ridge_z - 0.01,
                          ridge_tile_w * 0.6, tile_w, 0.04)
            parts.append((rv, rf))
            ridge_y += tile_w + 0.005
        components.append("ridge_tiles")

        # Fascia board along eave edges
        fascia_h = 0.06
        fascia_d = 0.02
        # Left eave
        fv, ff = _box(-half_w, -overhang, -fascia_h,
                       0.02, depth + 2 * overhang, fascia_h)
        parts.append((fv, ff))
        # Right eave
        fv, ff = _box(half_w - 0.02, -overhang, -fascia_h,
                       0.02, depth + 2 * overhang, fascia_h)
        parts.append((fv, ff))
        components.append("fascia")

        # Gable end triangles (close the roof at front and back)
        # Front gable (y = -overhang)
        gable_y_front = -overhang
        gable_y_back = depth + overhang
        gable_thickness = 0.08  # thin wall to close the gable

        for gy in [gable_y_front, gable_y_back]:
            # Triangle: bottom-left, bottom-right, peak
            # Build as a thin triangular prism for solidity
            bl = (-half_w, gy, 0.0)
            br = (half_w, gy, 0.0)
            pk = (0.0, gy, ridge_height)
            bl2 = (-half_w, gy + gable_thickness, 0.0)
            br2 = (half_w, gy + gable_thickness, 0.0)
            pk2 = (0.0, gy + gable_thickness, ridge_height)
            gv = [bl, br, pk, bl2, br2, pk2]
            # 8 faces: front tri, back tri, 3 side quads
            gf = [
                (0, 1, 2),       # front triangle
                (5, 4, 3),       # back triangle
                (0, 3, 4, 1),   # bottom quad
                (1, 4, 5, 2),   # right slope quad
                (2, 5, 3, 0),   # left slope quad
            ]
            parts.append((gv, gf))
        components.append("gable_ends")

        # Rafters (visible structural beams)
        for ri in range(rafter_count):
            ry = -overhang + (ri + 0.5) * (depth + 2 * overhang) / rafter_count
            # Left rafter
            rv, rf = _box(-half_w, ry, 0.0, half_w, rafter_w, rafter_d)
            # Angle it -- approximate with skewed top vertices
            parts.append((rv, rf))
            # Right rafter
            rv, rf = _box(0.0, ry, 0.0, half_w, rafter_w, rafter_d)
            parts.append((rv, rf))
        components.append("rafters")

    elif style == "hip":
        # Four sloping surfaces meeting at a ridge
        slope_len = half_w / math.cos(pitch_rad)
        slope_rise = half_w * math.tan(pitch_rad)

        # Front and back slopes + left and right (abbreviated triangular)
        # Main left/right slopes same as gable
        row_count = max(1, int(slope_len / tile_h))
        total_tiles = 0
        for side in [-1, 1]:
            for ri in range(row_count):
                row_z_frac = ri / row_count
                slope_x = side * (half_w - row_z_frac * half_w)
                slope_z = row_z_frac * slope_rise
                sv, sf, sc = _shingle_row(
                    depth + 2 * overhang, 0.0, tile_w, tile_h, tile_h * 0.5,
                    0.1, row_index=ri + (2000 if side > 0 else 0), seed=seed + ri,
                )
                cos_p = math.cos(pitch_rad)
                sin_p = math.sin(pitch_rad)
                transformed_v = []
                for vx, vy, vz in sv:
                    wx = slope_x + (-side) * vz * cos_p
                    wy = vx - overhang
                    wz = slope_z + vz * sin_p + vy
                    transformed_v.append((wx, wy, wz))
                parts.append((transformed_v, sf))
                total_tiles += sc
        components.extend(["left_slope_tiles", "right_slope_tiles"])

        # Hip ridge tiles
        ridge_z = slope_rise
        rv, rf = _box(-0.03, -overhang, ridge_z - 0.01, 0.06, depth + 2 * overhang, 0.04)
        parts.append((rv, rf))
        components.append("ridge_tiles")

    elif style == "shed":
        # Single slope from high side to low side
        slope_rise = total_w * math.tan(pitch_rad)
        slope_len = total_w / math.cos(pitch_rad)
        row_count = max(1, int(slope_len / tile_h))
        total_tiles = 0
        for ri in range(row_count):
            row_z_frac = ri / row_count
            slope_z = slope_rise - row_z_frac * slope_rise
            sv, sf, sc = _shingle_row(
                depth + 2 * overhang, 0.0, tile_w, tile_h, tile_h * 0.5,
                0.1, row_index=ri, seed=seed + ri,
            )
            cos_p = math.cos(pitch_rad)
            sin_p = math.sin(pitch_rad)
            transformed_v = []
            for vx, vy, vz in sv:
                wx = -half_w + row_z_frac * total_w + vz * cos_p
                wy = vx - overhang
                wz = slope_z - vz * sin_p + vy
                transformed_v.append((wx, wy, wz))
            parts.append((transformed_v, sf))
            total_tiles += sc
        components.append("slope_tiles")

    elif style == "flat":
        # Dark-fantasy flat roof with a stone slab and low parapet.
        slab_h = 0.12 if material in {"tile", "slate"} else 0.18
        slab_v, slab_f = _box(
            -half_w,
            -overhang,
            0.0,
            total_w,
            depth + 2 * overhang,
            slab_h,
        )
        parts.append((slab_v, slab_f))
        components.append("flat_slab")

        parapet_h = 0.45 if material == "stone" else 0.35
        parapet_t = 0.08
        # Front/back rails
        for y in (-overhang, depth + overhang - parapet_t):
            pv, pf = _box(-half_w, y, slab_h, total_w, parapet_t, parapet_h)
            parts.append((pv, pf))
        # Left/right rails
        for x in (-half_w, half_w - parapet_t):
            pv, pf = _box(x, -overhang, slab_h, parapet_t, depth + 2 * overhang, parapet_h)
            parts.append((pv, pf))

        # Corner finials for a more fortified silhouette.
        finial_r = 0.08
        finial_h = 0.24
        for x in (-half_w + finial_r, half_w - finial_r):
            for y in (-overhang + finial_r, depth + overhang - finial_r):
                cv, cf = _cylinder(x, y, slab_h + parapet_h, finial_r, finial_h, 6)
                parts.append((cv, cf))

    elif style == "conical_tower":
        # Vertical tower crown without any cone silhouette. This is intentionally
        # built as an octagonal shaft with a stepped top and crenellations.
        radius = width / 2.0 + overhang
        shaft_h = max(0.85, radius * 1.9)
        crown_h = max(0.55, radius * 0.7)
        segments = 8

        tower_verts: list[tuple[float, float, float]] = []
        tower_faces: list[tuple[int, ...]] = []

        def add_ring(z: float, ring_radius: float, twist: float = 0.0) -> int:
            start = len(tower_verts)
            for i in range(segments):
                ang = 2.0 * math.pi * i / segments + twist
                tower_verts.append((math.cos(ang) * ring_radius, math.sin(ang) * ring_radius, z))
            return start

        ring0 = add_ring(0.0, radius)
        ring1 = add_ring(shaft_h * 0.48, radius * 0.97, twist=math.pi / 8.0)
        ring2 = add_ring(shaft_h * 0.88, radius * 0.88)
        ring3 = add_ring(shaft_h + crown_h * 0.24, radius * 0.80, twist=math.pi / 8.0)
        ring4 = add_ring(shaft_h + crown_h * 0.50, radius * 0.74)

        for base in (ring0, ring1, ring2, ring3):
            top = base + segments
            for i in range(segments):
                i_next = (i + 1) % segments
                tower_faces.append((base + i, base + i_next, top + i_next, top + i))

        tower_faces.append(tuple(range(ring0 + segments - 1, ring0 - 1, -1)))
        tower_faces.append(tuple(range(ring4, ring4 + segments)))
        parts.append((tower_verts, tower_faces))
        components.append("octagonal_shaft")
        components.append("crown_bands")

        # Battlements at the top edge.
        merlon_w = max(0.18, radius * 0.22)
        merlon_d = max(0.18, radius * 0.22)
        merlon_h = max(0.32, crown_h * 0.45)
        merlon_z = shaft_h + crown_h * 0.50
        merlon_r = radius * 0.84
        for mi in range(segments):
            if mi % 2 == 1:
                continue
            ang = 2.0 * math.pi * mi / segments
            mx = math.cos(ang) * merlon_r
            my = math.sin(ang) * merlon_r
            mv, mf = _box(
                mx - merlon_w * 0.5,
                my - merlon_d * 0.5,
                merlon_z,
                merlon_w,
                merlon_d,
                merlon_h,
            )
            parts.append((mv, mf))
        components.append("merlons")

    elif style == "gambrel":
        # Two slopes per side: steep lower, shallow upper
        lower_pitch = pitch * 1.4
        upper_pitch = pitch * 0.5
        lower_h = ridge_height * 0.6
        upper_h = ridge_height * 0.4

        lower_run = lower_h / math.tan(math.radians(lower_pitch))
        upper_run = half_w - lower_run

        total_tiles = 0
        for section in ["lower", "upper"]:
            p = math.radians(lower_pitch if section == "lower" else upper_pitch)
            section_h = lower_h if section == "lower" else upper_h
            section_len = section_h / math.sin(p) if math.sin(p) > 0.01 else section_h
            row_count = max(1, int(section_len / tile_h))

            for side in [-1, 1]:
                for ri in range(row_count):
                    sv, sf, sc = _shingle_row(
                        depth + 2 * overhang, 0.0, tile_w, tile_h, tile_h * 0.5,
                        0.1, row_index=ri, seed=seed + ri + (3000 if section == "upper" else 0),
                    )
                    frac = ri / row_count
                    if section == "lower":
                        slope_x = side * (half_w - frac * lower_run)
                        slope_z = frac * lower_h
                    else:
                        slope_x = side * (half_w - lower_run - frac * upper_run)
                        slope_z = lower_h + frac * upper_h

                    cos_p = math.cos(p)
                    sin_p = math.sin(p)
                    transformed_v = []
                    for vx, vy, vz in sv:
                        wx = slope_x + (-side) * vz * cos_p
                        wy = vx - overhang
                        wz = slope_z + vz * sin_p + vy
                        transformed_v.append((wx, wy, wz))
                    parts.append((transformed_v, sf))
                    total_tiles += sc

        components.extend(["lower_slope_tiles", "upper_slope_tiles"])

    elif style == "mansard":
        # Like gambrel but on all four sides
        lower_pitch_val = pitch * 1.4
        lower_h = ridge_height * 0.7
        total_tiles = 0

        p = math.radians(lower_pitch_val)
        section_len = lower_h / math.sin(p) if math.sin(p) > 0.01 else lower_h
        row_count = max(1, int(section_len / tile_h))

        for side in [-1, 1]:
            for ri in range(row_count):
                sv, sf, sc = _shingle_row(
                    depth + 2 * overhang, 0.0, tile_w, tile_h, tile_h * 0.5,
                    0.1, row_index=ri, seed=seed + ri,
                )
                frac = ri / row_count
                lower_run = lower_h / math.tan(p) if math.tan(p) > 0.01 else half_w
                slope_x = side * (half_w - frac * lower_run)
                slope_z = frac * lower_h

                cos_p = math.cos(p)
                sin_p = math.sin(p)
                transformed_v = []
                for vx, vy, vz in sv:
                    wx = slope_x + (-side) * vz * cos_p
                    wy = vx - overhang
                    wz = slope_z + vz * sin_p + vy
                    transformed_v.append((wx, wy, wz))
                parts.append((transformed_v, sf))
                total_tiles += sc

        # Flat top
        flat_w = total_w - 2 * (lower_h / math.tan(p) if math.tan(p) > 0.01 else half_w)
        if flat_w > 0.1:
            fv, ff = _box(-flat_w / 2, -overhang, lower_h,
                          flat_w, depth + 2 * overhang, 0.05)
            parts.append((fv, ff))
        components.append("mansard_slopes")

    else:
        total_tiles = 0

    # Thatch special: thick rounded edge at eave
    if material == "thatch" and style in ("gable", "hip", "shed"):
        thatch_roll_r = 0.08
        thatch_segs = 6
        for y_pos in [0.0, depth]:
            for i in range(thatch_segs):
                a0 = math.pi * i / thatch_segs
                a1 = math.pi * (i + 1) / thatch_segs
                tv = [
                    (-half_w + math.cos(a0) * thatch_roll_r, y_pos,
                     -math.sin(a0) * thatch_roll_r),
                    (-half_w + math.cos(a1) * thatch_roll_r, y_pos,
                     -math.sin(a1) * thatch_roll_r),
                    (-half_w + math.cos(a1) * thatch_roll_r, y_pos + 0.1,
                     -math.sin(a1) * thatch_roll_r),
                    (-half_w + math.cos(a0) * thatch_roll_r, y_pos + 0.1,
                     -math.sin(a0) * thatch_roll_r),
                ]
                parts.append((tv, [(0, 1, 2, 3)]))
        components.append("thatch_roll")

    # Build material_ids: slot 0 = base structure, slot 1 = tiles/shingles/detail
    mat_ids_roof: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids_roof.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    return _make_result(
        f"roof_{style}_{material}",
        all_v, all_f,
        components=components,
        material_ids=mat_ids_roof,
        roof_style=style,
        material=material,
        pitch=pitch,
        overhang=overhang,
        tile_count=total_tiles if "total_tiles" in dir() else 0,
        generator="building_quality",
    )


# ===================================================================
# GENERATOR 5: Staircase
# ===================================================================

def generate_staircase(
    style: str = "straight",
    step_count: int = 12,
    step_width: float = 1.0,
    step_height: float = 0.18,
    step_depth: float = 0.28,
    railing: bool = True,
    seed: int = 42,
) -> MeshSpec:
    """Generate staircase with individual steps and railings.

    Styles: 'straight', 'spiral', 'l_shaped', 'u_shaped', 'ladder'

    Each step is individual geometry with nosing overhang. Railings have
    newel posts, balusters, and handrails.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []

    nosing = 0.02  # how far step overhangs

    if style == "straight":
        for si in range(step_count):
            sz = si * step_height
            sy = si * step_depth

            # Tread (top of step with nosing)
            tv, tf = _box(-nosing, sy - nosing, sz,
                          step_width + 2 * nosing, step_depth + nosing, step_height)
            parts.append((tv, tf))
            components.append(f"step_{si}")

        # Stringer beams (side supports)
        total_h = step_count * step_height
        total_d = step_count * step_depth
        stringer_w = 0.04
        stringer_h = 0.12

        # Left stringer
        for si in range(step_count):
            sz = si * step_height
            sy = si * step_depth
            sv, sf = _box(-stringer_w - nosing, sy, sz - stringer_h,
                          stringer_w, step_depth, stringer_h + step_height)
            parts.append((sv, sf))

        # Right stringer
        for si in range(step_count):
            sz = si * step_height
            sy = si * step_depth
            sv, sf = _box(step_width + nosing, sy, sz - stringer_h,
                          stringer_w, step_depth, stringer_h + step_height)
            parts.append((sv, sf))
        components.append("stringers")

        if railing:
            _add_straight_railing(parts, components, step_count, step_width,
                                  step_height, step_depth, nosing, rng)

    elif style == "spiral":
        pole_r = 0.06
        outer_r = step_width
        angle_per_step = 2.0 * math.pi / max(step_count, 1) * 1.5  # 1.5 turns total

        # Central pole
        cv, cf = _cylinder(0.0, 0.0, 0.0, pole_r, step_count * step_height + step_height, 8)
        parts.append((cv, cf))
        components.append("central_pole")

        for si in range(step_count):
            angle = si * angle_per_step
            sz = si * step_height
            # Wedge-shaped step: inner edge at pole, outer edge at radius
            n_seg = 4  # segments per step arc
            step_verts = []
            step_faces = []

            for seg_i in range(n_seg + 1):
                a = angle + (seg_i / n_seg) * angle_per_step
                ca, sa = math.cos(a), math.sin(a)
                # Inner point
                step_verts.append((ca * pole_r, sa * pole_r, sz))
                step_verts.append((ca * pole_r, sa * pole_r, sz + step_height))
                # Outer point
                step_verts.append((ca * outer_r, sa * outer_r, sz))
                step_verts.append((ca * outer_r, sa * outer_r, sz + step_height))

            # Create faces between segments
            for seg_i in range(n_seg):
                b_idx = seg_i * 4
                n_idx = (seg_i + 1) * 4
                # Top face
                step_faces.append((b_idx + 1, b_idx + 3, n_idx + 3, n_idx + 1))
                # Bottom face
                step_faces.append((b_idx, n_idx, n_idx + 2, b_idx + 2))
                # Outer face
                step_faces.append((b_idx + 2, b_idx + 3, n_idx + 3, n_idx + 2))
                # Inner face
                step_faces.append((b_idx, b_idx + 1, n_idx + 1, n_idx))
                # Riser at front
                if seg_i == 0:
                    step_faces.append((b_idx, b_idx + 2, b_idx + 3, b_idx + 1))

            parts.append((step_verts, step_faces))
            components.append(f"step_{si}")

        if railing:
            # Outer railing as a series of vertical posts
            for si in range(step_count + 1):
                angle = si * angle_per_step
                sz = si * step_height
                ca, sa = math.cos(angle), math.sin(angle)
                px = ca * (outer_r - 0.02)
                py = sa * (outer_r - 0.02)
                bv, bf = _box(px - 0.015, py - 0.015, sz,
                              0.03, 0.03, step_height * 3)
                parts.append((bv, bf))
            components.append("railing_posts")

    elif style == "l_shaped":
        # First run
        half_steps = step_count // 2
        for si in range(half_steps):
            sz = si * step_height
            sy = si * step_depth
            tv, tf = _box(-nosing, sy - nosing, sz,
                          step_width + 2 * nosing, step_depth + nosing, step_height)
            parts.append((tv, tf))
            components.append(f"step_{si}")

        # Landing platform
        landing_z = half_steps * step_height
        landing_y = half_steps * step_depth
        lv, lf = _box(-nosing, landing_y, landing_z,
                       step_width + step_depth + nosing, step_depth, step_height)
        parts.append((lv, lf))
        components.append("landing")

        # Second run (perpendicular)
        for si in range(step_count - half_steps):
            sz = landing_z + (si + 1) * step_height
            sx = step_width + si * step_depth
            tv, tf = _box(sx - nosing, landing_y - nosing, sz,
                          step_depth + nosing, step_width + 2 * nosing, step_height)
            parts.append((tv, tf))
            components.append(f"step_{half_steps + si}")

        if railing:
            _add_l_shaped_railing(parts, components, step_count, step_width,
                                  step_height, step_depth, nosing, rng)

    elif style == "u_shaped":
        half_steps = step_count // 2
        for si in range(half_steps):
            sz = si * step_height
            sy = si * step_depth
            tv, tf = _box(-nosing, sy - nosing, sz,
                          step_width + 2 * nosing, step_depth + nosing, step_height)
            parts.append((tv, tf))
            components.append(f"step_{si}")

        # Landing
        landing_z = half_steps * step_height
        landing_y = half_steps * step_depth
        lv, lf = _box(-step_width - nosing, landing_y, landing_z,
                       step_width * 2 + 2 * nosing, step_depth * 2, step_height)
        parts.append((lv, lf))
        components.append("landing")

        # Second run (parallel, opposite direction)
        for si in range(step_count - half_steps):
            sz = landing_z + (si + 1) * step_height
            sy = landing_y + step_depth * 2 - (si + 1) * step_depth
            tv, tf = _box(-step_width - nosing, sy - nosing, sz,
                          step_width + 2 * nosing, step_depth + nosing, step_height)
            parts.append((tv, tf))
            components.append(f"step_{half_steps + si}")

        if railing:
            _add_u_shaped_railing(parts, components, step_count, step_width,
                                  step_height, step_depth, nosing, rng)

    elif style == "ladder":
        # Side rails
        rail_w = 0.04
        rail_d = 0.06
        total_h = step_count * step_height
        rung_r = 0.015

        # Left rail
        lv, lf = _box(0.0, 0.0, 0.0, rail_w, rail_d, total_h + step_height)
        parts.append((lv, lf))
        # Right rail
        rv, rf = _box(step_width - rail_w, 0.0, 0.0, rail_w, rail_d, total_h + step_height)
        parts.append((rv, rf))
        components.extend(["left_rail", "right_rail"])

        # Rungs (cylindrical)
        for si in range(step_count):
            rz = (si + 0.5) * step_height + step_height * 0.5
            # Approximate rung as a thin box
            rv, rf = _box(rail_w, rail_d * 0.3, rz - rung_r,
                          step_width - 2 * rail_w, rail_d * 0.4, rung_r * 2)
            parts.append((rv, rf))
            components.append(f"rung_{si}")

    # Build material_ids: slot 0 = tread/step faces, slot 1 = railing/riser detail
    mat_ids_stair: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids_stair.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    return _make_result(
        f"staircase_{style}",
        all_v, all_f,
        components=components,
        material_ids=mat_ids_stair,
        stair_style=style,
        step_count=step_count,
        has_railing=railing,
        generator="building_quality",
    )


def _add_straight_railing(
    parts: list, components: list,
    step_count: int, step_width: float,
    step_height: float, step_depth: float,
    nosing: float, rng: random.Random,
) -> None:
    """Add railing to straight staircase: newel posts, balusters, handrail."""
    railing_h = 0.9  # standard railing height
    post_w = 0.06
    baluster_w = 0.025
    handrail_w = 0.05
    handrail_h = 0.04

    total_rise = step_count * step_height
    total_run = step_count * step_depth

    for side_x in [-nosing - post_w, step_width + nosing]:
        # Newel post at bottom
        nv, nf = _box(side_x, -nosing, 0.0, post_w, post_w, railing_h + step_height)
        parts.append((nv, nf))

        # Newel post at top
        nv, nf = _box(side_x, total_run - post_w, total_rise,
                       post_w, post_w, railing_h + step_height)
        parts.append((nv, nf))

        # Balusters (one per step)
        for si in range(step_count):
            sz = si * step_height + step_height
            sy = si * step_depth + step_depth * 0.5
            bx = side_x + (post_w - baluster_w) * 0.5
            bv, bf = _box(bx, sy, sz, baluster_w, baluster_w, railing_h)
            parts.append((bv, bf))

        # Handrail (series of boxes following stair angle)
        for si in range(step_count):
            sz = si * step_height + step_height + railing_h
            sy = si * step_depth
            hv, hf = _box(side_x, sy, sz, handrail_w, step_depth, handrail_h)
            parts.append((hv, hf))

    components.extend(["newel_posts", "balusters", "handrail"])


def _add_l_shaped_railing(
    parts: list, components: list,
    step_count: int, step_width: float,
    step_height: float, step_depth: float,
    nosing: float, rng: random.Random,
) -> None:
    """Add railing to L-shaped staircase: posts and handrail along outer edge."""
    railing_h = 0.9
    post_w = 0.06
    baluster_w = 0.025
    handrail_w = 0.05
    handrail_h = 0.04

    half_steps = step_count // 2

    # --- First run (along +Y, outer edge at x = step_width + nosing) ---
    side_x = step_width + nosing
    # Newel at bottom
    nv, nf = _box(side_x, -nosing, 0.0, post_w, post_w, railing_h + step_height)
    parts.append((nv, nf))
    for si in range(half_steps):
        sz = si * step_height + step_height
        sy = si * step_depth + step_depth * 0.5
        bv, bf = _box(side_x, sy, sz, baluster_w, baluster_w, railing_h)
        parts.append((bv, bf))
        hv, hf = _box(side_x, si * step_depth, sz - step_height + railing_h,
                       handrail_w, step_depth, handrail_h)
        parts.append((hv, hf))

    # --- Landing corner newel ---
    landing_z = half_steps * step_height
    landing_y = half_steps * step_depth
    nv, nf = _box(side_x, landing_y, landing_z, post_w, post_w,
                   railing_h + step_height)
    parts.append((nv, nf))

    # --- Second run (along +X, outer edge at y = landing_y + step_depth + nosing) ---
    side_y = landing_y + step_depth * 2 + nosing  # outer side of second run
    for si in range(step_count - half_steps):
        sz = landing_z + (si + 1) * step_height
        sx = step_width + si * step_depth + step_depth * 0.5
        bv, bf = _box(sx, side_y, sz, baluster_w, baluster_w, railing_h)
        parts.append((bv, bf))
        hv, hf = _box(step_width + si * step_depth, side_y, sz - step_height + railing_h,
                       step_depth, handrail_w, handrail_h)
        parts.append((hv, hf))

    # Newel at top of second run
    final_x = step_width + (step_count - half_steps) * step_depth
    final_z = step_count * step_height
    nv, nf = _box(final_x, side_y, final_z, post_w, post_w,
                   railing_h + step_height)
    parts.append((nv, nf))

    components.extend(["newel_posts", "balusters", "handrail"])


def _add_u_shaped_railing(
    parts: list, components: list,
    step_count: int, step_width: float,
    step_height: float, step_depth: float,
    nosing: float, rng: random.Random,
) -> None:
    """Add railing to U-shaped staircase: posts and handrail along outer edges."""
    railing_h = 0.9
    post_w = 0.06
    baluster_w = 0.025
    handrail_w = 0.05
    handrail_h = 0.04

    half_steps = step_count // 2

    # --- First run (along +Y, outer edge at x = step_width + nosing) ---
    side_x = step_width + nosing
    nv, nf = _box(side_x, -nosing, 0.0, post_w, post_w, railing_h + step_height)
    parts.append((nv, nf))
    for si in range(half_steps):
        sz = si * step_height + step_height
        sy = si * step_depth + step_depth * 0.5
        bv, bf = _box(side_x, sy, sz, baluster_w, baluster_w, railing_h)
        parts.append((bv, bf))
        hv, hf = _box(side_x, si * step_depth, sz - step_height + railing_h,
                       handrail_w, step_depth, handrail_h)
        parts.append((hv, hf))

    # --- Landing newel ---
    landing_z = half_steps * step_height
    landing_y = half_steps * step_depth
    nv, nf = _box(side_x, landing_y + step_depth * 2, landing_z, post_w, post_w,
                   railing_h + step_height)
    parts.append((nv, nf))

    # --- Second run (along -Y, outer edge at x = -step_width - nosing) ---
    side_x2 = -step_width - nosing - post_w
    nv, nf = _box(side_x2, landing_y + step_depth * 2, landing_z, post_w, post_w,
                   railing_h + step_height)
    parts.append((nv, nf))
    for si in range(step_count - half_steps):
        sz = landing_z + (si + 1) * step_height
        sy = landing_y + step_depth * 2 - (si + 1) * step_depth + step_depth * 0.5
        bv, bf = _box(side_x2, sy, sz, baluster_w, baluster_w, railing_h)
        parts.append((bv, bf))
        sy_h = landing_y + step_depth * 2 - (si + 1) * step_depth
        hv, hf = _box(side_x2, sy_h, sz - step_height + railing_h,
                       handrail_w, step_depth, handrail_h)
        parts.append((hv, hf))

    # Newel at top of second run
    final_z = step_count * step_height
    final_y = landing_y + step_depth * 2 - (step_count - half_steps) * step_depth
    nv, nf = _box(side_x2, final_y, final_z, post_w, post_w,
                   railing_h + step_height)
    parts.append((nv, nf))

    components.extend(["newel_posts", "balusters", "handrail"])


# ===================================================================
# GENERATOR 6: Archway/Doorframe
# ===================================================================

def generate_archway(
    width: float = 1.2,
    height: float = 2.5,
    depth: float = 0.5,
    arch_style: str = "gothic_pointed",
    has_keystone: bool = True,
    seed: int = 42,
) -> MeshSpec:
    """Generate detailed stone archway with voussoirs.

    Styles: 'gothic_pointed', 'roman_round', 'flat_lintel', 'horseshoe', 'ogee'

    Components: jambs, imposts, arch voussoirs, keystone, intrados, spandrel.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []
    hw = width / 2.0

    # Jamb dimensions
    jamb_w = 0.12
    jamb_chamfer = 0.03

    # 1. Jambs (side posts with chamfered inner edge)
    # Left jamb
    jv, jf = _box(-hw - jamb_w, 0.0, 0.0, jamb_w, depth, height * 0.7)
    parts.append((jv, jf))
    components.append("left_jamb")

    # Right jamb
    jv, jf = _box(hw, 0.0, 0.0, jamb_w, depth, height * 0.7)
    parts.append((jv, jf))
    components.append("right_jamb")

    # Chamfered inner edges
    for side_x, ch_x in [(-hw, -hw - jamb_chamfer), (hw - jamb_chamfer, hw)]:
        cv, cf = _box(ch_x, depth * 0.15, 0.0, jamb_chamfer, depth * 0.7, height * 0.7)
        parts.append((cv, cf))

    # 2. Imposts (capitals where arch springs from jambs)
    impost_h = 0.06
    impost_proj = 0.03
    for side_x in [-hw - jamb_w - impost_proj, hw - impost_proj]:
        iv, if_ = _box(side_x, -impost_proj, height * 0.7 - impost_h,
                        jamb_w + 2 * impost_proj, depth + 2 * impost_proj, impost_h)
        parts.append((iv, if_))
    components.append("imposts")

    # 3. Arch voussoirs
    arch_h = height * 0.3
    arch_pts = _arch_curve(width, arch_h, arch_style, num_points=24)
    spring_z = height * 0.7
    arch_pts_3d = [(p[0], p[1] + spring_z) for p in arch_pts]

    block_count = 11
    av, af, v_count = _voussoir_blocks(arch_pts_3d, depth, block_count)
    if av:
        parts.append((av, af))
        components.append("voussoirs")

    # 3b. Keystone -- trapezoidal wedge at the apex of the arch
    if has_keystone and arch_pts_3d:
        # Find the apex (highest point on the arch curve)
        apex_idx = max(range(len(arch_pts_3d)), key=lambda i: arch_pts_3d[i][1])
        apex_x, apex_z = arch_pts_3d[apex_idx]
        ks_w_top = 0.08  # width at the top (wider)
        ks_w_bot = 0.05  # width at the bottom (narrower, gives taper)
        ks_h = 0.12      # keystone height (extends above arch)
        ks_d = depth + 0.02  # slightly proud of the arch
        ks_y0 = -0.01    # slight projection forward
        # Trapezoidal prism: 8 verts (wider at top, narrower at bottom)
        kv = [
            # Bottom face (narrower)
            (apex_x - ks_w_bot / 2, ks_y0, apex_z),
            (apex_x + ks_w_bot / 2, ks_y0, apex_z),
            (apex_x + ks_w_bot / 2, ks_y0 + ks_d, apex_z),
            (apex_x - ks_w_bot / 2, ks_y0 + ks_d, apex_z),
            # Top face (wider)
            (apex_x - ks_w_top / 2, ks_y0, apex_z + ks_h),
            (apex_x + ks_w_top / 2, ks_y0, apex_z + ks_h),
            (apex_x + ks_w_top / 2, ks_y0 + ks_d, apex_z + ks_h),
            (apex_x - ks_w_top / 2, ks_y0 + ks_d, apex_z + ks_h),
        ]
        kf = [
            (0, 1, 2, 3),  # bottom
            (4, 7, 6, 5),  # top
            (0, 4, 5, 1),  # front
            (2, 6, 7, 3),  # back
            (0, 3, 7, 4),  # left
            (1, 5, 6, 2),  # right
        ]
        parts.append((kv, kf))
        components.append("keystone")

    # 4. Spandrel fill (wall above arch, between arch extrados and rectangular frame)
    spandrel_top = height
    # Left spandrel
    sv, sf = _box(-hw - jamb_w, 0.0, spring_z + arch_h * 0.5,
                   jamb_w, depth, spandrel_top - spring_z - arch_h * 0.5)
    parts.append((sv, sf))
    # Right spandrel
    sv, sf = _box(hw, 0.0, spring_z + arch_h * 0.5,
                   jamb_w, depth, spandrel_top - spring_z - arch_h * 0.5)
    parts.append((sv, sf))
    # Top lintel above arch
    sv, sf = _box(-hw - jamb_w, 0.0, height - 0.1,
                   width + 2 * jamb_w, depth, 0.1)
    parts.append((sv, sf))
    components.append("spandrel")

    # 5. Intrados (the inner curved surface you walk under)
    # Use arch curve to build the inner surface of the passthrough
    if len(arch_pts_3d) >= 2:
        for pi in range(len(arch_pts_3d) - 1):
            x0, z0 = arch_pts_3d[pi]
            x1, z1 = arch_pts_3d[pi + 1]
            iv = [
                (x0, 0.0, z0),
                (x1, 0.0, z1),
                (x1, depth, z1),
                (x0, depth, z0),
            ]
            iff = [(0, 1, 2, 3)]
            parts.append((iv, iff))
        components.append("intrados")

    # Build material_ids: slot 0 = jamb/wall structure, slot 1 = voussoir/keystone/intrados detail
    mat_ids_arch: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids_arch.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    return _make_result(
        f"archway_{arch_style}",
        all_v, all_f,
        components=components,
        material_ids=mat_ids_arch,
        arch_style=arch_style,
        has_keystone=has_keystone,
        voussoir_count=v_count,
        generator="building_quality",
    )


# ===================================================================
# GENERATOR 7: Chimney
# ===================================================================

def generate_chimney(
    height: float = 2.0,
    style: str = "stone",
    has_cap: bool = True,
    chimney_width: float = 0.5,
    chimney_depth: float = 0.5,
    seed: int = 42,
) -> MeshSpec:
    """Generate chimney with brick/stone pattern and cap.

    Styles: 'stone', 'brick', 'rustic'

    Features: shaft with visible block pattern, corbeling near top,
    chimney pot/cap, flue opening, base flashing strip.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []

    cw, cd = chimney_width, chimney_depth

    # Block sizing by style
    if style == "brick":
        block_w, block_h = 0.22, 0.065
        mortar = 0.008
        variation = 0.05
    elif style == "rustic":
        block_w, block_h = 0.25, 0.15
        mortar = 0.012
        variation = 0.4
    else:  # stone
        block_w, block_h = 0.2, 0.12
        mortar = 0.01
        variation = 0.2

    # 1. Shaft with block pattern on all 4 sides
    # Front face
    fv, ff, _ = _stone_block_grid(cw, height, block_w, block_h, mortar, variation,
                                   seed=seed)
    fv_3d = [(x, -mortar, z) for x, y, z in fv]
    parts.append((fv_3d, ff))

    # Back face
    bv, bf, _ = _stone_block_grid(cw, height, block_w, block_h, mortar, variation,
                                   seed=seed + 100)
    bv_3d = [(x, cd + mortar, z) for x, y, z in bv]
    parts.append((bv_3d, bf))

    # Left face
    lv, lf, _ = _stone_block_grid(cd, height, block_w, block_h, mortar, variation,
                                   seed=seed + 200)
    lv_3d = [(-mortar - y, x, z) for x, y, z in lv]
    parts.append((lv_3d, lf))

    # Right face
    rv, rf, _ = _stone_block_grid(cd, height, block_w, block_h, mortar, variation,
                                   seed=seed + 300)
    rv_3d = [(cw + mortar + y, cd - x, z) for x, y, z in rv]
    parts.append((rv_3d, rf))

    # Inner shaft (solid core)
    wall_t = 0.08
    sv, sf = _box(wall_t, wall_t, 0.0, cw - 2 * wall_t, cd - 2 * wall_t, height)
    parts.append((sv, sf))
    components.append("shaft")

    # 2. Corbeling (stepped outward projection near top)
    corbel_start = height * 0.8
    corbel_steps = 3
    for ci in range(corbel_steps):
        proj = (ci + 1) * 0.015
        cz = corbel_start + ci * 0.04
        cv, cf = _box(-proj, -proj, cz, cw + 2 * proj, cd + 2 * proj, 0.035)
        parts.append((cv, cf))
    components.append("corbeling")

    # 3. Cap or pot
    if has_cap:
        cap_z = height
        if style == "brick":
            # Chimney pot: cylindrical
            pot_r = min(cw, cd) * 0.3
            pv, pf = _cylinder(cw * 0.5, cap_z, cd * 0.5, pot_r, 0.25, 8)
            parts.append((pv, pf))
            components.append("chimney_pot")
        else:
            # Stone cap: slab on pillars
            pillar_w = 0.04
            pillar_h = 0.12
            cap_overhang = 0.05
            # 4 corner pillars
            for px, py in [(0, 0), (cw - pillar_w, 0),
                           (0, cd - pillar_w), (cw - pillar_w, cd - pillar_w)]:
                pv, pf = _box(px, py, cap_z, pillar_w, pillar_w, pillar_h)
                parts.append((pv, pf))
            # Top slab
            sv, sf = _box(-cap_overhang, -cap_overhang, cap_z + pillar_h,
                           cw + 2 * cap_overhang, cd + 2 * cap_overhang, 0.04)
            parts.append((sv, sf))
            components.append("stone_cap")

    # 4. Flue opening (dark recessed area at top)
    flue_inset = 0.06
    fv, ff = _box(flue_inset, flue_inset, height - 0.02,
                   cw - 2 * flue_inset, cd - 2 * flue_inset, 0.01)
    parts.append((fv, ff))
    components.append("flue")

    # 5. Base flashing (angled strip where chimney meets roof)
    flash_w = 0.06
    flash_h = 0.08
    # Simple angled strips around base
    for side in range(4):
        if side == 0:
            fv, ff = _box(-flash_w, -flash_w, 0.0, cw + 2 * flash_w, flash_w, flash_h)
        elif side == 1:
            fv, ff = _box(-flash_w, cd, 0.0, cw + 2 * flash_w, flash_w, flash_h)
        elif side == 2:
            fv, ff = _box(-flash_w, 0.0, 0.0, flash_w, cd, flash_h)
        else:
            fv, ff = _box(cw, 0.0, 0.0, flash_w, cd, flash_h)
        parts.append((fv, ff))
    components.append("flashing")

    # Build material_ids: slot 0 = shaft structure, slot 1 = cap/corbel/flashing detail
    mat_ids_chimney: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids_chimney.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    return _make_result(
        f"chimney_{style}",
        all_v, all_f,
        components=components,
        material_ids=mat_ids_chimney,
        chimney_style=style,
        has_cap=has_cap,
        generator="building_quality",
    )


# ===================================================================
# GENERATOR 8: Interior Detail Kit
# ===================================================================

def generate_interior_trim(
    room_width: float = 4.0,
    room_depth: float = 5.0,
    room_height: float = 3.0,
    style: str = "medieval",
    seed: int = 42,
) -> MeshSpec:
    """Generate interior architectural detail as SEPARATE mesh components.

    Components: baseboard, crown molding, ceiling beams, floor planks,
    wainscoting, chair rail, door/window trim.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []

    w, d, h = room_width, room_depth, room_height

    # Style-specific parameters
    style_params = {
        "medieval": {
            "baseboard_h": 0.08, "baseboard_d": 0.015,
            "crown_h": 0.06, "crown_d": 0.04,
            "beam_w": 0.12, "beam_h": 0.15, "beam_count": 3,
            "plank_w": 0.15, "plank_gap": 0.003, "plank_h": 0.02,
            "wainscot_h": 0.9, "wainscot_d": 0.02,
            "panel_w": 0.4, "panel_h": 0.5, "panel_inset": 0.005,
        },
        "gothic": {
            "baseboard_h": 0.12, "baseboard_d": 0.02,
            "crown_h": 0.1, "crown_d": 0.06,
            "beam_w": 0.1, "beam_h": 0.1, "beam_count": 4,
            "plank_w": 0.2, "plank_gap": 0.002, "plank_h": 0.025,
            "wainscot_h": 1.2, "wainscot_d": 0.025,
            "panel_w": 0.35, "panel_h": 0.7, "panel_inset": 0.008,
        },
        "rustic": {
            "baseboard_h": 0.06, "baseboard_d": 0.01,
            "crown_h": 0.04, "crown_d": 0.03,
            "beam_w": 0.15, "beam_h": 0.18, "beam_count": 2,
            "plank_w": 0.2, "plank_gap": 0.005, "plank_h": 0.025,
            "wainscot_h": 0.7, "wainscot_d": 0.015,
            "panel_w": 0.5, "panel_h": 0.4, "panel_inset": 0.003,
        },
    }
    sp = style_params.get(style, style_params["medieval"])

    # 1. BASEBOARD MOLDING -- along floor/wall junction
    bb_h = sp["baseboard_h"]
    bb_d = sp["baseboard_d"]

    # Profile for baseboard (simple stepped)
    bb_profile = [
        (0.0, 0.0),
        (bb_d, 0.0),
        (bb_d, bb_h * 0.7),
        (bb_d * 0.6, bb_h * 0.85),
        (bb_d * 0.3, bb_h),
        (0.0, bb_h),
    ]

    # Four walls
    # Front wall (y=0)
    path_front = [(x, 0.0, 0.0) for x in _linspace(0.0, w, 4)]
    bv, bf = _molding_profile_extrude(bb_profile, path_front)
    parts.append((bv, bf))

    # Back wall (y=d)
    path_back = [(x, d, 0.0) for x in _linspace(w, 0.0, 4)]
    bv, bf = _molding_profile_extrude(bb_profile, path_back)
    parts.append((bv, bf))

    # Left wall (x=0)
    path_left = [(0.0, y, 0.0) for y in _linspace(0.0, d, 4)]
    bv, bf = _molding_profile_extrude(bb_profile, path_left)
    parts.append((bv, bf))

    # Right wall (x=w)
    path_right = [(w, y, 0.0) for y in _linspace(d, 0.0, 4)]
    bv, bf = _molding_profile_extrude(bb_profile, path_right)
    parts.append((bv, bf))
    components.append("baseboard")

    # 2. CROWN MOLDING -- along ceiling/wall junction
    cr_h = sp["crown_h"]
    cr_d = sp["crown_d"]
    cr_profile = [
        (0.0, 0.0),
        (cr_d * 0.3, -cr_h * 0.2),
        (cr_d * 0.7, -cr_h * 0.6),
        (cr_d, -cr_h),
    ]

    for path in [
        [(x, 0.0, h) for x in _linspace(0.0, w, 4)],
        [(x, d, h) for x in _linspace(w, 0.0, 4)],
        [(0.0, y, h) for y in _linspace(0.0, d, 4)],
        [(w, y, h) for y in _linspace(d, 0.0, 4)],
    ]:
        cv, cf = _molding_profile_extrude(cr_profile, path)
        parts.append((cv, cf))
    components.append("crown_molding")

    # 3. CEILING BEAMS (exposed timber)
    bm_w = sp["beam_w"]
    bm_h = sp["beam_h"]
    bm_count = sp["beam_count"]
    spacing = d / (bm_count + 1)

    for bi in range(bm_count):
        by = (bi + 1) * spacing - bm_w * 0.5
        bv, bf = _box(0.0, by, h - bm_h, w, bm_w, bm_h)
        parts.append((bv, bf))
    components.append("ceiling_beams")

    # 4. FLOOR PLANKS (individual boards with gaps)
    pl_w = sp["plank_w"]
    pl_gap = sp["plank_gap"]
    pl_h = sp["plank_h"]
    plank_count = 0

    x = 0.0
    while x < w:
        actual_w = min(pl_w, w - x)
        if actual_w < 0.01:
            break
        # Each plank has slight random length variation
        length = d + rng.uniform(-0.05, 0.05)
        length = min(length, d)
        pv, pf = _box(x, 0.0, -pl_h, actual_w - pl_gap, length, pl_h)
        parts.append((pv, pf))
        plank_count += 1
        x += pl_w
    components.append("floor_planks")

    # 5. WAINSCOTING (wood paneling on lower wall)
    wh = sp["wainscot_h"]
    wd = sp["wainscot_d"]
    panel_w = sp["panel_w"]
    panel_h = sp["panel_h"]
    panel_inset = sp["panel_inset"]

    # Front wall wainscoting
    # Backing board
    wv, wf = _box(0.0, -wd, bb_h, w, wd, wh - bb_h)
    parts.append((wv, wf))

    # Recessed panels
    panel_y = bb_h + (wh - bb_h - panel_h) * 0.5
    px = (w - int(w / panel_w) * panel_w) * 0.5
    while px + panel_w <= w:
        pv, pf = _box(px + panel_inset * 2, -wd + panel_inset, panel_y,
                       panel_w - panel_inset * 4, panel_inset, panel_h)
        parts.append((pv, pf))
        px += panel_w

    # Back wall
    wv, wf = _box(0.0, d, bb_h, w, wd, wh - bb_h)
    parts.append((wv, wf))
    components.append("wainscoting")

    # 6. CHAIR RAIL (horizontal molding at ~900mm)
    rail_h = 0.025
    rail_d = 0.015
    for path in [
        [(x, -wd, wh) for x in _linspace(0.0, w, 4)],
        [(x, d + wd, wh) for x in _linspace(w, 0.0, 4)],
    ]:
        rv, rf = _molding_profile_extrude(
            [(0.0, 0.0), (rail_d, 0.0), (rail_d, rail_h),
             (rail_d * 0.5, rail_h * 1.2), (0.0, rail_h)],
            path,
        )
        parts.append((rv, rf))
    components.append("chair_rail")

    # 7. DOOR TRIM (casing around a standard doorway)
    door_w = 1.0
    door_h = 2.2
    trim_w = 0.06
    trim_d = 0.015
    door_x = w * 0.5 - door_w * 0.5

    # Left casing
    tv, tf = _box(door_x - trim_w, -trim_d, 0.0, trim_w, trim_d, door_h + trim_w)
    parts.append((tv, tf))
    # Right casing
    tv, tf = _box(door_x + door_w, -trim_d, 0.0, trim_w, trim_d, door_h + trim_w)
    parts.append((tv, tf))
    # Top casing (header)
    tv, tf = _box(door_x - trim_w, -trim_d, door_h, door_w + 2 * trim_w, trim_d, trim_w)
    parts.append((tv, tf))
    components.append("door_trim")

    all_v, all_f = _merge(parts)

    return _make_result(
        f"interior_trim_{style}",
        all_v, all_f,
        components=components,
        interior_style=style,
        plank_count=plank_count,
        generator="building_quality",
    )


def _linspace(start: float, stop: float, count: int) -> list[float]:
    """Linearly spaced values from start to stop inclusive."""
    if count < 2:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + i * step for i in range(count)]


# ===================================================================
# GENERATOR 9: Fortress Battlements
# ===================================================================

def generate_battlements(
    wall_length: float = 10.0,
    wall_height: float = 6.0,
    wall_thickness: float = 1.5,
    merlon_style: str = "squared",
    has_machicolations: bool = True,
    has_arrow_loops: bool = True,
    tower_interval: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """Generate castle wall with battlements/crenellations.

    Merlon styles: 'squared', 'swallow_tail', 'rounded'

    Features: merlons with arrow slits, crenels, parapet walk,
    machicolations, arrow loops in wall, stone block surface.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    components: list[str] = []

    wl = wall_length
    wh = wall_height
    wt = wall_thickness

    # 1. Main wall body with stone block pattern
    # Front face blocks
    block_w, block_h = 0.4, 0.2
    mortar = 0.008
    fv, ff, _ = _stone_block_grid(wl, wh, block_w, block_h, mortar, 0.2, seed=seed)
    fv_3d = [(x, -mortar, z) for x, y, z in fv]
    parts.append((fv_3d, ff))

    # Back face blocks
    bv, bf, _ = _stone_block_grid(wl, wh, block_w, block_h, mortar, 0.2, seed=seed + 500)
    bv_3d = [(x, wt + mortar, z) for x, y, z in bv]
    parts.append((bv_3d, bf))

    # Wall core
    cv, cf = _box(0.0, 0.0, 0.0, wl, wt, wh)
    parts.append((cv, cf))
    components.append("wall_body")

    # 2. Parapet walk (walkway behind battlements at top of wall)
    walk_width = wt * 0.6
    walk_h = 0.15
    pv, pf = _box(0.0, wt * 0.2, wh, wl, walk_width, walk_h)
    parts.append((pv, pf))
    components.append("parapet_walk")

    # 3. Merlons and Crenels
    merlon_w = 0.6
    merlon_h = 0.8
    crenel_w = 0.4
    merlon_d = wt * 0.4
    battlement_z = wh + walk_h

    spacing = merlon_w + crenel_w
    merlon_count = 0
    x = 0.0
    while x + merlon_w <= wl:
        # Merlon (raised section)
        if merlon_style == "squared":
            mv, mf = _box(x, 0.0, battlement_z, merlon_w, merlon_d, merlon_h)
            parts.append((mv, mf))
        elif merlon_style == "swallow_tail":
            # V-notch in top
            mv, mf = _box(x, 0.0, battlement_z, merlon_w, merlon_d, merlon_h * 0.7)
            parts.append((mv, mf))
            # Two prongs
            prong_w = merlon_w * 0.35
            mv, mf = _box(x, 0.0, battlement_z, prong_w, merlon_d, merlon_h)
            parts.append((mv, mf))
            mv, mf = _box(x + merlon_w - prong_w, 0.0, battlement_z,
                          prong_w, merlon_d, merlon_h)
            parts.append((mv, mf))
        elif merlon_style == "rounded":
            mv, mf = _box(x, 0.0, battlement_z, merlon_w, merlon_d, merlon_h * 0.8)
            parts.append((mv, mf))
            # Rounded top (approximate with small boxes)
            cap_segs = 4
            cap_r = merlon_w * 0.5
            for ci in range(cap_segs):
                a0 = math.pi * ci / cap_segs
                a1 = math.pi * (ci + 1) / cap_segs
                cx_pos = x + merlon_w * 0.5 + math.cos(a0) * cap_r * 0.5
                cz_pos = battlement_z + merlon_h * 0.8 + math.sin(a0) * cap_r * 0.3
                seg_w = abs(math.cos(a1) - math.cos(a0)) * cap_r * 0.5 + 0.01
                seg_h = abs(math.sin(a1) - math.sin(a0)) * cap_r * 0.3 + 0.01
                mv, mf = _box(min(cx_pos, cx_pos + seg_w) - seg_w * 0.5,
                              0.0, cz_pos, seg_w, merlon_d, seg_h)
                parts.append((mv, mf))

        # Arrow slit in merlon
        if has_arrow_loops:
            slit_w = 0.04
            slit_h = merlon_h * 0.5
            cross_w = 0.12
            cross_h = 0.04
            slit_x = x + merlon_w * 0.5 - slit_w * 0.5
            slit_z = battlement_z + merlon_h * 0.25

            # Vertical slit
            sv, sf = _box(slit_x, -0.01, slit_z, slit_w, merlon_d * 0.3, slit_h)
            parts.append((sv, sf))
            # Cross piece (horizontal widening)
            sv, sf = _box(slit_x - (cross_w - slit_w) * 0.5, -0.01,
                          slit_z + slit_h * 0.4,
                          cross_w, merlon_d * 0.3, cross_h)
            parts.append((sv, sf))

        merlon_count += 1
        x += spacing

    components.append("merlons")
    components.append("arrow_slits")

    # 4. Machicolations (overhanging stone platforms with murder holes)
    if has_machicolations:
        mach_proj = 0.4  # how far they project from wall face
        mach_h = 0.3
        mach_w = merlon_w + crenel_w
        mach_z = wh - mach_h

        mach_count = max(1, int(wl / mach_w))
        for mi in range(mach_count):
            mx = mi * mach_w

            # Platform
            pv, pf = _box(mx, -mach_proj, mach_z, min(mach_w, wl - mx), mach_proj, 0.08)
            parts.append((pv, pf))

            # Support corbels (angled brackets)
            corbel_w = 0.1
            for ci_pos in [mx + mach_w * 0.2, mx + mach_w * 0.8]:
                if ci_pos > wl:
                    continue
                # Simple bracket approximation
                for step_i in range(3):
                    proj_step = mach_proj * (step_i + 1) / 4
                    step_z = mach_z - (3 - step_i) * 0.08
                    sv, sf = _box(ci_pos - corbel_w * 0.5, -proj_step, step_z,
                                  corbel_w, proj_step, 0.07)
                    parts.append((sv, sf))

            # Murder hole (gap in platform) - represented as a recessed box
            hole_w = mach_w * 0.3
            hole_d = mach_proj * 0.5
            hv, hf = _box(mx + mach_w * 0.35, -mach_proj * 0.75,
                          mach_z - 0.02, hole_w, hole_d, 0.02)
            parts.append((hv, hf))

        components.append("machicolations")

    # 5. Wall arrow loops (in main wall body)
    if has_arrow_loops:
        loop_spacing = 2.0
        loop_count = max(1, int(wl / loop_spacing))
        loop_h = 0.8
        loop_w = 0.04
        loop_z = wh * 0.5 - loop_h * 0.5

        for li in range(loop_count):
            lx = (li + 0.5) * wl / loop_count - loop_w * 0.5
            # Narrow slit through wall
            sv, sf = _box(lx, -0.02, loop_z, loop_w, wt * 0.3, loop_h)
            parts.append((sv, sf))
            # Cross widening
            cross_w = 0.1
            sv, sf = _box(lx - (cross_w - loop_w) * 0.5, -0.02,
                          loop_z + loop_h * 0.4, cross_w, wt * 0.3, 0.04)
            parts.append((sv, sf))
        components.append("wall_arrow_loops")

    # 6. Towers at intervals (if specified)
    if tower_interval > 0:
        tower_r = wt * 1.2
        tower_h = wh + walk_h + merlon_h + 1.0
        tower_count = max(0, int(wl / tower_interval) - 1)

        for ti in range(tower_count):
            tx = (ti + 1) * tower_interval
            if tx > wl:
                break
            # Tower body: layered octagonal massing with subtle profile warping so
            # the silhouette reads like masonry, not a smooth cylinder.
            tower_segs = 8
            base_r = tower_r * 1.08
            mid_r = tower_r * 0.98
            top_r = tower_r * 0.86
            crown_h = max(0.55, tower_r * 0.62)
            base_z = -tower_r * 0.5

            def _oct_ring(z: float, radius: float, twist: float = 0.0, profile: float = 0.0) -> list[tuple[float, float, float]]:
                pts: list[tuple[float, float, float]] = []
                for i in range(tower_segs):
                    ang = 2.0 * math.pi * i / tower_segs + twist
                    if profile > 0.0:
                        lobe = math.cos(ang * 4.0)
                        facet = math.cos(ang * 8.0 + twist * 0.5)
                        radial = 1.0 + profile * (0.72 * lobe + 0.28 * facet)
                    else:
                        radial = 1.0
                    pts.append((tx + math.cos(ang) * radius * radial, 0.0 + math.sin(ang) * radius * radial, z))
                return pts

            ring_a = _oct_ring(base_z, base_r, profile=0.24)
            ring_b = _oct_ring(base_z + tower_h * 0.40, mid_r, twist=math.pi / 8.0, profile=0.16)
            ring_c = _oct_ring(base_z + tower_h * 0.76, top_r, profile=0.10)
            ring_d = _oct_ring(base_z + tower_h, top_r * 0.90, twist=math.pi / 8.0, profile=0.06)
            tower_v = ring_a + ring_b + ring_c + ring_d
            tower_f: list[tuple[int, ...]] = []
            for base_idx in (0, tower_segs, tower_segs * 2):
                top_idx = base_idx + tower_segs
                for ci in range(tower_segs):
                    ci2 = (ci + 1) % tower_segs
                    tower_f.append((base_idx + ci, base_idx + ci2, top_idx + ci2, top_idx + ci))
            tower_f.append(tuple(range(tower_segs - 1, -1, -1)))
            tower_f.append(tuple(range(tower_segs * 3, tower_segs * 4)))
            parts.append((tower_v, tower_f))

            # Skirt and shoulder masses interrupt the cylindrical read at street level.
            skirt_w = tower_r * 2.32
            skirt_h = max(0.34, tower_h * 0.16)
            parts.append(_box(tx - skirt_w * 0.5, -tower_r * 1.02, base_z - skirt_h * 0.25, skirt_w, tower_r * 2.04, skirt_h))

            buttress_w = max(0.34, tower_r * 0.26)
            buttress_h = max(0.8, tower_h * 0.28)
            buttress_r = tower_r * 0.92
            for bx, by, bw, bh in (
                (buttress_r, 0.0, buttress_w * 0.68, buttress_h * 0.95),
                (-buttress_r, 0.0, buttress_w * 0.68, buttress_h * 0.95),
                (0.0, buttress_r, buttress_w * 0.82, buttress_h),
                (0.0, -buttress_r, buttress_w * 0.82, buttress_h),
            ):
                parts.append(_box(tx + bx - bw * 0.5, by - bw * 0.5, base_z + skirt_h * 0.08, bw, bw, bh))

            # Battlement crown: low parapet + alternating merlons.
            crown_z = base_z + tower_h
            crown_v, crown_f = _box(
                tx - top_r * 0.95,
                -top_r * 0.95,
                crown_z - crown_h * 0.12,
                top_r * 1.9,
                top_r * 1.9,
                crown_h * 0.18,
            )
            parts.append((crown_v, crown_f))

            merlon_w = top_r * 0.32
            merlon_d = top_r * 0.32
            merlon_h = max(0.28, crown_h * 0.58)
            merlon_z = crown_z + crown_h * 0.04
            for mi in range(tower_segs):
                if mi % 2 == 1:
                    continue
                ang = 2.0 * math.pi * mi / tower_segs
                mx = tx + math.cos(ang) * (top_r * 0.84)
                my = math.sin(ang) * (top_r * 0.84)
                mv, mf = _box(
                    mx - merlon_w * 0.5,
                    my - merlon_d * 0.5,
                    merlon_z,
                    merlon_w,
                    merlon_d,
                    merlon_h,
                )
                parts.append((mv, mf))

            # Low broken ledges make the tower silhouette feel layered and fortified.
            for offset in (-0.34, 0.34):
                lv, lf = _box(
                    tx - top_r * 0.55,
                    offset - 0.05,
                    base_z + tower_h * 0.36,
                    top_r * 1.1,
                    0.08,
                    0.12,
                )
                parts.append((lv, lf))
        components.append("towers")

    # Build material_ids: slot 0 = walkway/wall base, slot 1 = merlons/machicolations/arrow loops
    mat_ids_batt: list[int] = []
    for part_idx, (_, part_faces) in enumerate(parts):
        slot = 0 if part_idx == 0 else 1
        mat_ids_batt.extend([slot] * len(part_faces))

    all_v, all_f = _merge(parts)

    return _make_result(
        f"battlements_{merlon_style}",
        all_v, all_f,
        components=components,
        material_ids=mat_ids_batt,
        merlon_style=merlon_style,
        merlon_count=merlon_count,
        has_machicolations=has_machicolations,
        has_arrow_loops=has_arrow_loops,
        generator="building_quality",
    )


# ===================================================================
# Public API registry
# ===================================================================

BUILDING_QUALITY_GENERATORS = {
    "stone_wall": generate_stone_wall,
    "timber_frame": generate_timber_frame,
    "gothic_window": generate_gothic_window,
    "roof": generate_roof,
    "staircase": generate_staircase,
    "archway": generate_archway,
    "chimney": generate_chimney,
    "interior_trim": generate_interior_trim,
    "battlements": generate_battlements,
}


# ---------------------------------------------------------------------------
# Trim Sheet UV Band Assignment (Plan 39-03)
# ---------------------------------------------------------------------------

# 2048x2048 shared trim sheet atlas layout:
# stone band  : Y   0 – 256   (exterior wall stone)
# wood band   : Y 384 – 640   (timber frames, doors, window surrounds)
# roof band   : Y 1024 – 1280 (roof tiles / shingles)
# ground band : Y 1280 – 1408 (foundation, cobble ground)

TRIM_SHEET_ATLAS_SIZE = 2048
TRIM_SHEET_BANDS: dict[str, tuple[int, int]] = {
    "wall":   (0, 256),
    "stone":  (0, 256),
    "wood":   (384, 640),
    "roof":   (1024, 1280),
    "ground": (1280, 1408),
}


def get_trim_sheet_uv_band(surface_type: str) -> dict[str, Any]:
    """Return UV band coordinates for a surface type in the trim sheet atlas.

    Parameters
    ----------
    surface_type : "wall" | "stone" | "wood" | "roof" | "ground"

    Returns
    -------
    dict with atlas_size, band_pixel_range (y_min_px, y_max_px),
    uv_band (y_min_uv, y_max_uv in [0, 1]).
    """
    key = surface_type.lower().strip()
    px_lo, px_hi = TRIM_SHEET_BANDS.get(key, TRIM_SHEET_BANDS["wall"])
    inv = TRIM_SHEET_ATLAS_SIZE  # pixel → UV normalisation
    return {
        "atlas_size": TRIM_SHEET_ATLAS_SIZE,
        "surface_type": surface_type,
        "band_pixel_range": (px_lo, px_hi),
        "uv_band": (px_lo / inv, px_hi / inv),
    }


def apply_trim_sheet_uvs(mesh_spec: MeshSpec) -> MeshSpec:
    """Annotate a MeshSpec with trim sheet UV bands for each component.

    Reads ``components`` list from the spec and assigns the correct
    ``uv_band`` to each component based on its surface role.

    This is a pure-logic annotation — the actual UV assignment happens in
    the Blender handler that materialises the mesh.

    Parameters
    ----------
    mesh_spec : MeshSpec returned by any building_quality generator.

    Returns
    -------
    The same MeshSpec dict, augmented with ``trim_sheet_uvs`` mapping:
    ``{component_name: {atlas_size, band_pixel_range, uv_band}}``.
    """
    components = mesh_spec.get("components", [])
    uv_map: dict[str, Any] = {}

    for comp in components:
        comp_lower = comp.lower()
        if any(k in comp_lower for k in ("wall", "stone", "battlement", "merlon", "arch", "parapet")):
            uv_map[comp] = get_trim_sheet_uv_band("wall")
        elif any(k in comp_lower for k in ("timber", "wood", "beam", "plank", "door", "window_surround")):
            uv_map[comp] = get_trim_sheet_uv_band("wood")
        elif any(k in comp_lower for k in ("roof", "tile", "shingle", "gable")):
            uv_map[comp] = get_trim_sheet_uv_band("roof")
        elif any(k in comp_lower for k in ("ground", "floor", "foundation", "cobble")):
            uv_map[comp] = get_trim_sheet_uv_band("ground")
        else:
            # Default to wall/stone for unrecognised components
            uv_map[comp] = get_trim_sheet_uv_band("wall")

    mesh_spec["trim_sheet_uvs"] = uv_map
    mesh_spec["trim_sheet_atlas_size"] = TRIM_SHEET_ATLAS_SIZE
    return mesh_spec
