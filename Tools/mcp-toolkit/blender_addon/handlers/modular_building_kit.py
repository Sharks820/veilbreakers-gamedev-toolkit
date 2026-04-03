"""Modular building kit -- snap-together architecture pieces for 5 styles.

175 piece variants (25 core pieces x 5 styles + ruined variants).
All pieces are pure math (no bpy) returning {"vertices": [...], "faces": [...]}.

Grid: 2m horizontal, 3m vertical per floor.
Wall thickness: 0.3-0.5m (never single-face).
Target: 250-500 tris per wall section.

Styles: medieval, gothic, fortress, organic, ruined.

Entry points:
- generate_modular_piece(piece_type, style, **kwargs) -- main dispatch
- assemble_building(spec) -- combine piece placements
- get_available_pieces() -- list all available piece types per style
"""

from __future__ import annotations

import math
import random
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]

# Styles available
STYLES = ("medieval", "gothic", "fortress", "organic", "ruined")

# Default grid dimensions
GRID_H = 2.0   # horizontal cell
GRID_V = 3.0   # vertical cell (floor height)

# Style-specific thickness overrides
_STYLE_THICKNESS: dict[str, float] = {
    "medieval": 0.3,
    "gothic": 0.4,
    "fortress": 0.5,
    "organic": 0.35,
    "ruined": 0.3,
}

# Per-vertex jitter amplitude by style
_STYLE_JITTER: dict[str, float] = {
    "medieval": 0.005,
    "gothic": 0.003,
    "fortress": 0.008,
    "organic": 0.015,
    "ruined": 0.025,
}


# ---------------------------------------------------------------------------
# Utility helpers
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
        "height": max(zs) - min(zs),
        "depth": max(ys) - min(ys),
    }



def _auto_generate_uvs(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]] | None = None,
) -> list[tuple[float, float]]:
    """Generate per-vertex UVs using triplanar projection to avoid Y-face stretching.

    For each vertex, we blend between three axis-aligned projections (XZ, YZ, XY)
    based on which axes have the most variation in the mesh bounding box.
    This ensures wall faces oriented along Y still receive un-stretched UVs.
    """
    if not vertices:
        return []

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    span_z = max(max_z - min_z, 1e-6)

    # Determine dominant projection for this mesh piece:
    # If span_y > span_x * 0.5 (Y-facing face or depth-significant piece)
    # use YZ projection for the U axis so depth faces are not squashed.
    # Otherwise fall back to the classic XZ projection.
    if span_y > span_x * 0.5:
        # Triplanar: U = max(X-span, Y-span) axis, V = Z
        if span_x >= span_y:
            return [
                ((v[0] - min_x) / span_x, (v[2] - min_z) / span_z)
                for v in vertices
            ]
        else:
            return [
                ((v[1] - min_y) / span_y, (v[2] - min_z) / span_z)
                for v in vertices
            ]
    else:
        # Standard XZ projection for front/back-facing wall pieces
        inv_w = 1.0 / span_x
        inv_h = 1.0 / span_z
        return [((v[0] - min_x) * inv_w, (v[2] - min_z) * inv_h) for v in vertices]

def _make_result(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    style: str = "medieval",
    piece_type: str = "",
    **extra: Any,
) -> MeshSpec:
    if not uvs and vertices:
        uvs = _auto_generate_uvs(vertices)
    dims = _compute_dimensions(vertices)
    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs or [],
        "metadata": {
            "name": name,
            "piece_type": piece_type,
            "style": style,
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "dimensions": dims,
            **extra,
        },
    }


def _jitter(
    verts: list[tuple[float, float, float]],
    amplitude: float,
    seed: int = 42,
) -> list[tuple[float, float, float]]:
    """Apply per-vertex random displacement for organic imperfection."""
    if amplitude <= 0:
        return verts
    rng = random.Random(seed)
    result = []
    for x, y, z in verts:
        result.append((
            x + rng.uniform(-amplitude, amplitude),
            y + rng.uniform(-amplitude, amplitude),
            z + rng.uniform(-amplitude, amplitude),
        ))
    return result


def _get_thickness(style: str) -> float:
    return _STYLE_THICKNESS.get(style, 0.3)


def _get_jitter(style: str) -> float:
    return _STYLE_JITTER.get(style, 0.005)


# ---------------------------------------------------------------------------
# Box primitive: corner-origin box from (x0,y0,z0) to (x0+w, y0+d, z0+h)
# ---------------------------------------------------------------------------

def _box(
    x0: float, y0: float, z0: float,
    w: float, d: float, h: float,
    base: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Axis-aligned box with origin at min corner (x0,y0,z0)."""
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),  # bottom
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),  # top
    ]
    b = base
    faces = [
        (b+0, b+3, b+2, b+1),  # bottom
        (b+4, b+5, b+6, b+7),  # top
        (b+0, b+1, b+5, b+4),  # front
        (b+2, b+3, b+7, b+6),  # back
        (b+0, b+4, b+7, b+3),  # left
        (b+1, b+2, b+6, b+5),  # right
    ]
    return verts, faces


def _merge_geometry(
    parts: list[tuple],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]]]:
    """Merge multiple (verts, faces) tuples into one, with auto-generated UVs."""
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[tuple[float, float]] = []
    for part in parts:
        verts = part[0]
        faces = part[1]
        uvs = part[2] if len(part) > 2 and part[2] else None
        offset = len(all_verts)
        all_verts.extend(verts)
        if uvs is not None and len(uvs) == len(verts):
            all_uvs.extend(uvs)
        else:
            all_uvs.extend(_auto_generate_uvs(verts))
        for f in faces:
            all_faces.append(tuple(i + offset for i in f))
    return all_verts, all_faces, all_uvs


# ---------------------------------------------------------------------------
# Style detail generators (add beams, buttresses, etc.)
# ---------------------------------------------------------------------------

def _add_timber_frame(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    width: float, height: float, thickness: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Add half-timber beams to a medieval wall (horizontal + vertical beams)."""
    parts = [(verts, faces)]
    beam_w = 0.08
    beam_d = 0.04  # protrusion from wall face
    # Vertical beams at edges and center
    for bx in [0.0, width / 2 - beam_w / 2, width - beam_w]:
        bv, bf = _box(bx, -beam_d, 0.0, beam_w, beam_d, height, 0)
        parts.append((bv, bf))
    # Horizontal beam at mid-height
    bv, bf = _box(0.0, -beam_d, height / 2 - beam_w / 2, width, beam_d, beam_w, 0)
    parts.append((bv, bf))
    # Diagonal brace in upper half
    # Approximated as a thin box rotated via skewed vertices
    diag_base = len(verts) + sum(len(p[0]) for p in parts[1:])
    mid_x = width / 4
    bv2, bf2 = _box(mid_x, -beam_d, height / 2, width / 2, beam_d, beam_w, 0)
    parts.append((bv2, bf2))
    return _merge_geometry(parts)


def _add_buttresses(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    width: float, height: float, thickness: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Add gothic flying buttress details to a wall."""
    parts = [(verts, faces)]
    butt_w = 0.15
    butt_d = 0.25
    # Buttress pillars at 1/3 and 2/3 of width
    for bx in [width / 3 - butt_w / 2, 2 * width / 3 - butt_w / 2]:
        bv, bf = _box(bx, -butt_d, 0.0, butt_w, butt_d, height * 0.8, 0)
        parts.append((bv, bf))
        # Angled top
        cap_v, cap_f = _box(bx - 0.02, -butt_d - 0.05, height * 0.8,
                            butt_w + 0.04, butt_d + 0.05, 0.1, 0)
        parts.append((cap_v, cap_f))
    return _merge_geometry(parts)


def _add_arrow_slits(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    width: float, height: float, thickness: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Add arrow slit recesses to a fortress wall."""
    parts = [(verts, faces)]
    slit_w = 0.06
    slit_h = 0.8
    slit_d = thickness * 0.3
    count = max(1, int(width / 0.8))
    spacing = width / (count + 1)
    for i in range(count):
        sx = spacing * (i + 1) - slit_w / 2
        sz = height * 0.5 - slit_h / 2
        # Recess box (negative space marker for visuals)
        sv, sf = _box(sx, 0.0, sz, slit_w, slit_d, slit_h, 0)
        parts.append((sv, sf))
    return _merge_geometry(parts)


def _add_root_supports(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    width: float, height: float, thickness: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Add root-like organic supports at the base of a wall."""
    parts = [(verts, faces)]
    root_count = max(2, int(width / 0.6))
    rng = random.Random(hash(("roots", width, height)))
    for i in range(root_count):
        rx = rng.uniform(0.1, width - 0.1)
        rw = rng.uniform(0.06, 0.12)
        rh = rng.uniform(0.3, 0.6)
        rd = rng.uniform(0.08, 0.15)
        rv, rf = _box(rx - rw / 2, -rd, 0.0, rw, rd, rh, 0)
        parts.append((rv, rf))
    return _merge_geometry(parts)


def _apply_style_detail(
    style: str,
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    width: float, height: float, thickness: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[tuple[float, float]]]:
    """Apply style-specific detail geometry to a wall piece."""
    if style == "medieval":
        return _add_timber_frame(verts, faces, width, height, thickness)
    elif style == "gothic":
        return _add_buttresses(verts, faces, width, height, thickness)
    elif style == "fortress":
        return _add_arrow_slits(verts, faces, width, height, thickness)
    elif style == "organic":
        return _add_root_supports(verts, faces, width, height, thickness)
    # ruined: no extra detail (damage handles it)
    return verts, faces, _auto_generate_uvs(verts)


# ---------------------------------------------------------------------------
# WALL PIECES (9)
# ---------------------------------------------------------------------------

def wall_solid(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """Solid wall panel. Thickness auto-set from style if 0."""
    t = thickness if thickness > 0 else _get_thickness(style)
    verts, faces = _box(0.0, 0.0, 0.0, width, t, height)
    # Style details
    verts, faces, *_ = _apply_style_detail(style, verts, faces, width, height, t)
    # Jitter
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_solid_{style}", verts, faces,
        style=style, piece_type="wall_solid",
        grid_size=(width, t, height),
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "right", "position": (width, t / 2, height / 2)},
            {"face": "top", "position": (width / 2, t / 2, height)},
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


def _cut_opening(
    width: float, height: float, thickness: float,
    opening_x: float, opening_z: float,
    opening_w: float, opening_h: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Create a wall with a rectangular opening cut out.

    Returns geometry for: bottom strip + left strip + right strip + top strip +
    inner faces (sill, header, jambs forming the depth of the opening).
    Wall extends along X (width), Y (thickness), Z (height).
    Opening at (opening_x, opening_z) with size (opening_w, opening_h).
    """
    t = thickness
    ox, oz = opening_x, opening_z
    ow, oh = opening_w, opening_h
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Bottom strip (below opening)
    if oz > 0:
        parts.append(_box(0.0, 0.0, 0.0, width, t, oz))
    # Top strip (above opening)
    top_z = oz + oh
    if top_z < height:
        parts.append(_box(0.0, 0.0, top_z, width, t, height - top_z))
    # Left strip (beside opening, between bottom and top strips)
    if ox > 0:
        parts.append(_box(0.0, 0.0, oz, ox, t, oh))
    # Right strip (beside opening, between bottom and top strips)
    right_x = ox + ow
    if right_x < width:
        parts.append(_box(right_x, 0.0, oz, width - right_x, t, oh))

    # Inner faces of the opening (depth = thickness)
    # Sill (bottom of opening)
    parts.append(_box(ox, 0.0, oz - 0.02, ow, t, 0.02))
    # Header (top of opening)
    parts.append(_box(ox, 0.0, oz + oh, ow, t, 0.02))
    # Left jamb
    parts.append(_box(ox - 0.02, 0.0, oz, 0.02, t, oh))
    # Right jamb
    parts.append(_box(ox + ow, 0.0, oz, 0.02, t, oh))

    return _merge_geometry(parts)


def _window_opening_params(
    style: str, width: float, height: float,
    window_style: str,
) -> tuple[float, float, float, float]:
    """Return (ox, oz, ow, oh) for a centered window opening."""
    if style == "fortress":
        # Arrow slit style: narrow
        ow = 0.15
        oh = 1.0
    elif style == "gothic":
        ow = 0.6
        oh = min(1.8, height * 0.6)
    elif style == "organic":
        ow = 0.5
        oh = 0.5
    else:
        # medieval, ruined
        ow = 0.8
        oh = 1.2
    ox = (width - ow) / 2
    oz = height * 0.35
    return ox, oz, ow, oh


def wall_window(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    window_style: str = "rectangular",
    seed: int = 42,
) -> MeshSpec:
    """Wall panel with window opening cut + sill + frame."""
    t = thickness if thickness > 0 else _get_thickness(style)
    ox, oz, ow, oh = _window_opening_params(style, width, height, window_style)
    verts, faces, _uvs = _cut_opening(width, height, t, ox, oz, ow, oh)
    verts, faces, *_ = _apply_style_detail(style, verts, faces, width, height, t)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_window_{style}", verts, faces,
        style=style, piece_type="wall_window",
        opening={"x": ox, "z": oz, "width": ow, "height": oh},
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "right", "position": (width, t / 2, height / 2)},
        ],
    )


def _door_opening_params(
    style: str, width: float, height: float,
    door_style: str,
) -> tuple[float, float, float, float]:
    """Return (ox, oz, ow, oh) for a centered door opening."""
    if style == "gothic":
        ow = 1.5
        oh = min(2.8, height * 0.9)
    elif style == "fortress":
        ow = 1.5
        oh = 2.5
    elif style == "organic":
        ow = 1.0
        oh = 1.8
    else:
        ow = 1.2
        oh = 2.2
    ox = (width - ow) / 2
    oz = 0.0  # doors start at ground
    return ox, oz, ow, oh


def wall_door(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    door_style: str = "arched",
    seed: int = 42,
) -> MeshSpec:
    """Wall panel with door opening + frame."""
    t = thickness if thickness > 0 else _get_thickness(style)
    ox, oz, ow, oh = _door_opening_params(style, width, height, door_style)
    verts, faces, _uvs = _cut_opening(width, height, t, ox, oz, ow, oh)
    verts, faces, *_ = _apply_style_detail(style, verts, faces, width, height, t)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_door_{style}", verts, faces,
        style=style, piece_type="wall_door",
        opening={"x": ox, "z": oz, "width": ow, "height": oh},
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "right", "position": (width, t / 2, height / 2)},
        ],
    )


def wall_damaged(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    damage_amount: float = 0.3,
    seed: int = 42,
) -> MeshSpec:
    """Wall with broken top edge -- random vertex displacement on top vertices."""
    t = thickness if thickness > 0 else _get_thickness(style)
    verts, faces = _box(0.0, 0.0, 0.0, width, t, height)

    # Displace top-row vertices (z near height) downward randomly
    rng = random.Random(seed)
    max_drop = height * damage_amount
    displaced = []
    for x, y, z in verts:
        if abs(z - height) < 0.01:
            drop = rng.uniform(0.0, max_drop)
            displaced.append((
                x + rng.uniform(-0.05, 0.05),
                y + rng.uniform(-0.02, 0.02),
                z - drop,
            ))
        else:
            displaced.append((x, y, z))
    verts = displaced

    # Additional jitter
    verts = _jitter(verts, _get_jitter("ruined"), seed + 1)
    return _make_result(
        f"wall_damaged_{style}", verts, faces,
        style=style, piece_type="wall_damaged",
        damage_amount=damage_amount,
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "right", "position": (width, t / 2, height / 2)},
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


def wall_half(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """Half-height wall for balconies, railings."""
    t = thickness if thickness > 0 else _get_thickness(style)
    half_h = height / 2
    verts, faces = _box(0.0, 0.0, 0.0, width, t, half_h)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_half_{style}", verts, faces,
        style=style, piece_type="wall_half",
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, half_h / 2)},
            {"face": "right", "position": (width, t / 2, half_h / 2)},
            {"face": "top", "position": (width / 2, t / 2, half_h)},
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


def wall_corner_inner(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """90-degree inner corner piece (L-shaped in plan).

    ARCH-035: Apply style detail per arm to avoid beams spanning the empty corner
    region. X-arm uses full width; Y-arm uses depth=(width-t) with rotated coords.
    """
    t = thickness if thickness > 0 else _get_thickness(style)
    # Arm along X axis: extends x=0..width, y=0..t
    x_verts, x_faces = _box(0.0, 0.0, 0.0, width, t, height)
    # Apply style detail to X arm (standard orientation: width x height)
    x_verts, x_faces, _ = _apply_style_detail(style, x_verts, x_faces, width, height, t)

    # Arm along Y axis: extends x=0..t, y=t..width (length = width-t)
    y_verts, y_faces = _box(0.0, t, 0.0, t, width - t, height)
    # Apply style detail to Y arm treating its length (width-t) as the "width"
    # Beams project in the -x direction (y-arm faces x=0 side), so we don't call
    # _apply_style_detail here (it projects in -y direction and would overlap with
    # the X arm). Instead, skip extra beams on the short Y arm to avoid z-fighting.

    verts, faces, uvs = _merge_geometry([(x_verts, x_faces), (y_verts, y_faces)])
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_corner_inner_{style}", verts, faces,
        style=style, piece_type="wall_corner_inner",
        connection_points=[
            {"face": "right", "position": (width, t / 2, height / 2)},
            {"face": "back", "position": (t / 2, width, height / 2)},
        ],
    )


def wall_corner_outer(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """90-degree outer corner piece (L-shaped, exterior facing)."""
    t = thickness if thickness > 0 else _get_thickness(style)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    # Wall along X axis (full width + corner overlap)
    parts.append(_box(0.0, 0.0, 0.0, width + t, t, height))
    # Wall along Y axis
    parts.append(_box(width, t, 0.0, t, width, height))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_corner_outer_{style}", verts, faces,
        style=style, piece_type="wall_corner_outer",
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "back", "position": (width + t / 2, width + t, height / 2)},
        ],
    )


def wall_t_junction(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """T-intersection wall piece."""
    t = thickness if thickness > 0 else _get_thickness(style)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    # Main wall along X axis
    parts.append(_box(0.0, 0.0, 0.0, width, t, height))
    # Perpendicular wall from center
    cx = width / 2 - t / 2
    parts.append(_box(cx, t, 0.0, t, width / 2, height))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_t_junction_{style}", verts, faces,
        style=style, piece_type="wall_t_junction",
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "right", "position": (width, t / 2, height / 2)},
            {"face": "back", "position": (width / 2, t + width / 2, height / 2)},
        ],
    )


def wall_end_cap(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 3.0,
    thickness: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """Exposed wall end with visible cross-section."""
    t = thickness if thickness > 0 else _get_thickness(style)
    # Thicker end with a visible cap face
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    # Main wall segment (shorter than standard)
    seg_len = width / 2
    parts.append(_box(0.0, 0.0, 0.0, seg_len, t, height))
    # End cap block (slightly wider for visual emphasis)
    cap_extra = 0.03
    parts.append(_box(seg_len, -cap_extra, 0.0, 0.05, t + 2 * cap_extra, height))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"wall_end_cap_{style}", verts, faces,
        style=style, piece_type="wall_end_cap",
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, height / 2)},
        ],
    )


# ---------------------------------------------------------------------------
# FLOOR PIECES (3)
# ---------------------------------------------------------------------------

def floor_stone(
    width: float = 2.0,
    depth: float = 2.0,
    thickness: float = 0.15,
    seed: int = 42,
) -> MeshSpec:
    """Stone slab floor with subtle stone block lines."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    # Main slab
    parts.append(_box(0.0, 0.0, 0.0, width, depth, thickness))
    # Stone block line ridges (raised seams between stones)
    ridge_h = 0.005
    block_size = 0.5
    for ix in range(int(width / block_size)):
        x = ix * block_size
        if x > 0:
            parts.append(_box(x - 0.005, 0.0, thickness, 0.01, depth, ridge_h))
    for iy in range(int(depth / block_size)):
        y = iy * block_size
        if y > 0:
            parts.append(_box(0.0, y - 0.005, thickness, width, 0.01, ridge_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, 0.003, seed)
    return _make_result(
        "floor_stone", verts, faces,
        style="stone", piece_type="floor_stone",
        connection_points=[
            {"face": "left", "position": (0.0, depth / 2, thickness / 2)},
            {"face": "right", "position": (width, depth / 2, thickness / 2)},
            {"face": "front", "position": (width / 2, 0.0, thickness / 2)},
            {"face": "back", "position": (width / 2, depth, thickness / 2)},
        ],
    )


def floor_wood(
    width: float = 2.0,
    depth: float = 2.0,
    thickness: float = 0.1,
    plank_width: float = 0.2,
    seed: int = 42,
) -> MeshSpec:
    """Wooden plank floor with individual plank strips."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    gap = 0.01
    num_planks = max(1, int(depth / plank_width))
    actual_pw = (depth - gap * (num_planks - 1)) / num_planks
    rng = random.Random(seed)
    for i in range(num_planks):
        py = i * (actual_pw + gap)
        # Slight height variation per plank
        pz_offset = rng.uniform(-0.003, 0.003)
        pv, pf = _box(0.0, py, pz_offset, width, actual_pw, thickness)
        parts.append((pv, pf))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, 0.002, seed)
    return _make_result(
        "floor_wood", verts, faces,
        style="wood", piece_type="floor_wood",
        connection_points=[
            {"face": "left", "position": (0.0, depth / 2, thickness / 2)},
            {"face": "right", "position": (width, depth / 2, thickness / 2)},
            {"face": "front", "position": (width / 2, 0.0, thickness / 2)},
            {"face": "back", "position": (width / 2, depth, thickness / 2)},
        ],
    )


def floor_dirt(
    width: float = 2.0,
    depth: float = 2.0,
    thickness: float = 0.08,
    seed: int = 42,
) -> MeshSpec:
    """Dirt floor with rough, uneven surface (subdivided top face)."""
    # Create a subdivided slab for undulating top
    subdiv = 6  # 6x6 grid on top
    rng = random.Random(seed)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Bottom 4 vertices
    verts.extend([
        (0.0, 0.0, 0.0),
        (width, 0.0, 0.0),
        (width, depth, 0.0),
        (0.0, depth, 0.0),
    ])
    # Bottom face
    faces.append((0, 3, 2, 1))

    # Top grid
    top_start = len(verts)
    for iy in range(subdiv + 1):
        for ix in range(subdiv + 1):
            x = width * ix / subdiv
            y = depth * iy / subdiv
            z = thickness + rng.uniform(-0.02, 0.02)
            verts.append((x, y, z))

    # Top faces (quads)
    for iy in range(subdiv):
        for ix in range(subdiv):
            i0 = top_start + iy * (subdiv + 1) + ix
            i1 = i0 + 1
            i2 = i0 + (subdiv + 1) + 1
            i3 = i0 + (subdiv + 1)
            faces.append((i0, i1, i2, i3))

    # Side faces connecting bottom corners to top edge vertices
    # Front side (y=0)
    for ix in range(subdiv):
        t0 = top_start + ix
        t1 = top_start + ix + 1
        if ix == 0:
            faces.append((0, t0, t1, 1) if subdiv == 1 else (0, t0, t1))
        if ix == subdiv - 1:
            faces.append((t0, 1, t1) if False else None)
    # Simplified: just use 4 side quads connecting bottom to top edge
    # Front side
    faces.append((0, 1, top_start + subdiv, top_start))
    # Right side
    faces.append((1, 2, top_start + (subdiv + 1) * subdiv + subdiv,
                  top_start + subdiv))
    # Back side
    faces.append((2, 3, top_start + (subdiv + 1) * subdiv,
                  top_start + (subdiv + 1) * subdiv + subdiv))
    # Left side
    faces.append((3, 0, top_start, top_start + (subdiv + 1) * subdiv))

    # Remove any None entries from faces
    faces = [f for f in faces if f is not None]

    return _make_result(
        "floor_dirt", verts, faces,
        style="dirt", piece_type="floor_dirt",
        connection_points=[
            {"face": "left", "position": (0.0, depth / 2, thickness / 2)},
            {"face": "right", "position": (width, depth / 2, thickness / 2)},
            {"face": "front", "position": (width / 2, 0.0, thickness / 2)},
            {"face": "back", "position": (width / 2, depth, thickness / 2)},
        ],
    )


# ---------------------------------------------------------------------------
# ROOF PIECES (4)
# ---------------------------------------------------------------------------

def roof_slope(
    width: float = 2.0,
    depth: float = 2.0,
    pitch: float = 35.0,
    thickness: float = 0.08,
    seed: int = 42,
) -> MeshSpec:
    """Angled roof section. Slopes from z=0 at front to z=rise at back."""
    rise = depth * math.tan(math.radians(pitch))
    t = thickness

    # Outer surface (4 vertices, sloped)
    verts: list[tuple[float, float, float]] = [
        (0.0, 0.0, 0.0),         # front-left bottom
        (width, 0.0, 0.0),       # front-right bottom
        (width, depth, rise),     # back-right top
        (0.0, depth, rise),       # back-left top
    ]
    # Inner surface (offset downward by thickness normal to slope)
    # Normal direction: perpendicular to slope surface
    slope_len = math.sqrt(depth * depth + rise * rise)
    nx = 0.0
    ny = -rise / slope_len * t
    nz = depth / slope_len * t
    verts.extend([
        (0.0 + nx, 0.0 + ny, 0.0 - nz),
        (width + nx, 0.0 + ny, 0.0 - nz),
        (width + nx, depth + ny, rise - nz),
        (0.0 + nx, depth + ny, rise - nz),
    ])

    faces: list[tuple[int, ...]] = [
        (0, 1, 2, 3),  # outer face
        (7, 6, 5, 4),  # inner face
        (0, 4, 5, 1),  # front edge
        (2, 6, 7, 3),  # back edge (actually this is the top edge)
        (0, 3, 7, 4),  # left edge
        (1, 5, 6, 2),  # right edge
    ]

    verts = _jitter(verts, 0.003, seed)
    return _make_result(
        "roof_slope", verts, faces,
        style="roof", piece_type="roof_slope",
        pitch=pitch, rise=rise,
        connection_points=[
            {"face": "left", "position": (0.0, depth / 2, rise / 2)},
            {"face": "right", "position": (width, depth / 2, rise / 2)},
            {"face": "bottom", "position": (width / 2, 0.0, 0.0)},
            {"face": "top", "position": (width / 2, depth, rise)},
        ],
    )


def roof_peak(
    width: float = 2.0,
    depth: float = 2.0,
    pitch: float = 35.0,
    thickness: float = 0.08,
    seed: int = 42,
) -> MeshSpec:
    """Ridge/peak piece -- two slopes meeting at a center ridge."""
    rise = (width / 2) * math.tan(math.radians(pitch))
    t = thickness
    half_w = width / 2

    # Build as two sloped panels meeting at the ridge
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Left slope outer
    verts.extend([
        (0.0, 0.0, 0.0),          # 0: left-front-bottom
        (half_w, 0.0, rise),       # 1: ridge-front
        (half_w, depth, rise),     # 2: ridge-back
        (0.0, depth, 0.0),        # 3: left-back-bottom
    ])
    # Left slope inner
    verts.extend([
        (0.0, 0.0, -t),           # 4
        (half_w, 0.0, rise - t),   # 5
        (half_w, depth, rise - t), # 6
        (0.0, depth, -t),         # 7
    ])
    # Right slope outer
    verts.extend([
        (half_w, 0.0, rise),      # 8: ridge-front (shared with 1)
        (width, 0.0, 0.0),        # 9: right-front-bottom
        (width, depth, 0.0),      # 10: right-back-bottom
        (half_w, depth, rise),     # 11: ridge-back (shared with 2)
    ])
    # Right slope inner
    verts.extend([
        (half_w, 0.0, rise - t),   # 12
        (width, 0.0, -t),         # 13
        (width, depth, -t),        # 14
        (half_w, depth, rise - t), # 15
    ])

    # Left slope faces
    faces.extend([
        (0, 1, 2, 3),   # outer
        (7, 6, 5, 4),   # inner
        (0, 4, 5, 1),   # front
        (3, 2, 6, 7),   # back
        (0, 3, 7, 4),   # left edge
    ])
    # Right slope faces
    faces.extend([
        (8, 9, 10, 11),   # outer
        (15, 14, 13, 12), # inner
        (8, 12, 13, 9),   # front
        (11, 10, 14, 15), # back
        (9, 13, 14, 10),  # right edge
    ])

    verts = _jitter(verts, 0.003, seed)
    return _make_result(
        "roof_peak", verts, faces,
        style="roof", piece_type="roof_peak",
        pitch=pitch, rise=rise,
        connection_points=[
            {"face": "left", "position": (0.0, depth / 2, 0.0)},
            {"face": "right", "position": (width, depth / 2, 0.0)},
            {"face": "front", "position": (width / 2, 0.0, rise)},
            {"face": "back", "position": (width / 2, depth, rise)},
        ],
    )


def roof_flat(
    width: float = 2.0,
    depth: float = 2.0,
    thickness: float = 0.15,
    seed: int = 42,
) -> MeshSpec:
    """Flat roof / walkway with slight lip around the edge."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    # Main slab
    parts.append(_box(0.0, 0.0, 0.0, width, depth, thickness))
    # Lip / parapet around edge
    lip_h = 0.1
    lip_t = 0.05
    # Front lip
    parts.append(_box(0.0, 0.0, thickness, width, lip_t, lip_h))
    # Back lip
    parts.append(_box(0.0, depth - lip_t, thickness, width, lip_t, lip_h))
    # Left lip
    parts.append(_box(0.0, lip_t, thickness, lip_t, depth - 2 * lip_t, lip_h))
    # Right lip
    parts.append(_box(width - lip_t, lip_t, thickness, lip_t, depth - 2 * lip_t, lip_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, 0.003, seed)
    return _make_result(
        "roof_flat", verts, faces,
        style="roof", piece_type="roof_flat",
        connection_points=[
            {"face": "left", "position": (0.0, depth / 2, thickness / 2)},
            {"face": "right", "position": (width, depth / 2, thickness / 2)},
            {"face": "front", "position": (width / 2, 0.0, thickness / 2)},
            {"face": "back", "position": (width / 2, depth, thickness / 2)},
        ],
    )


def roof_gutter(
    width: float = 2.0,
    depth: float = 0.3,
    thickness: float = 0.04,
    seed: int = 42,
) -> MeshSpec:
    """Eave overhang / gutter piece."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    # Main shelf extending outward
    parts.append(_box(0.0, 0.0, 0.0, width, depth, thickness))
    # Lip at the outer edge (drip edge)
    parts.append(_box(0.0, depth - 0.02, -0.05, width, 0.02, 0.05 + thickness))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, 0.002, seed)
    return _make_result(
        "roof_gutter", verts, faces,
        style="roof", piece_type="roof_gutter",
        connection_points=[
            {"face": "back", "position": (width / 2, 0.0, thickness / 2)},
        ],
    )


# ---------------------------------------------------------------------------
# STAIR PIECES (3)
# ---------------------------------------------------------------------------

def stair_straight(
    width: float = 2.0,
    height: float = 3.0,
    depth: float = 3.0,
    step_count: int = 0,
    seed: int = 42,
) -> MeshSpec:
    """Straight staircase with individual steps."""
    if step_count <= 0:
        step_count = max(3, int(height / 0.2))
    step_h = height / step_count
    step_d = depth / step_count
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    for i in range(step_count):
        sz = i * step_h
        sy = i * step_d
        # Each step is a box
        parts.append(_box(0.0, sy, sz, width, step_d, step_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, 0.004, seed)
    return _make_result(
        "stair_straight", verts, faces,
        style="stair", piece_type="stair_straight",
        step_count=step_count,
        connection_points=[
            {"face": "front", "position": (width / 2, 0.0, 0.0)},
            {"face": "back", "position": (width / 2, depth, height)},
        ],
    )


def stair_spiral(
    radius: float = 1.5,
    height: float = 3.0,
    turns: float = 1.0,
    steps_per_turn: int = 12,
    seed: int = 42,
) -> MeshSpec:
    """Spiral staircase with wedge-shaped steps around a central column."""
    total_steps = max(4, int(turns * steps_per_turn))
    angle_per_step = (2 * math.pi * turns) / total_steps
    step_h = height / total_steps
    inner_r = 0.15  # central column radius
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    rng = random.Random(seed)

    for i in range(total_steps):
        a0 = i * angle_per_step
        a1 = (i + 1) * angle_per_step
        z0 = i * step_h
        z1 = z0 + step_h

        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)

        # Wedge: 4 bottom verts, 4 top verts
        step_verts = [
            # Bottom face
            (inner_r * c0, inner_r * s0, z0),    # inner start
            (radius * c0, radius * s0, z0),      # outer start
            (radius * c1, radius * s1, z0),      # outer end
            (inner_r * c1, inner_r * s1, z0),    # inner end
            # Top face (at step height)
            (inner_r * c0, inner_r * s0, z1),
            (radius * c0, radius * s0, z1),
            (radius * c1, radius * s1, z1),
            (inner_r * c1, inner_r * s1, z1),
        ]
        step_faces = [
            (0, 3, 2, 1),  # bottom
            (4, 5, 6, 7),  # top (tread)
            (0, 1, 5, 4),  # front
            (2, 3, 7, 6),  # back
            (0, 4, 7, 3),  # inner
            (1, 2, 6, 5),  # outer
        ]
        parts.append((step_verts, step_faces))

    # Central column
    col_segs = 8
    col_verts: list[tuple[float, float, float]] = []
    col_faces: list[tuple[int, ...]] = []
    for i in range(col_segs):
        a = 2 * math.pi * i / col_segs
        col_verts.append((inner_r * math.cos(a), inner_r * math.sin(a), 0.0))
    for i in range(col_segs):
        a = 2 * math.pi * i / col_segs
        col_verts.append((inner_r * math.cos(a), inner_r * math.sin(a), height))
    # Side faces
    for i in range(col_segs):
        i2 = (i + 1) % col_segs
        col_faces.append((i, i2, col_segs + i2, col_segs + i))
    # Caps
    col_faces.append(tuple(range(col_segs - 1, -1, -1)))
    col_faces.append(tuple(range(col_segs, 2 * col_segs)))
    parts.append((col_verts, col_faces))

    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, 0.003, seed)
    return _make_result(
        "stair_spiral", verts, faces,
        style="stair", piece_type="stair_spiral",
        turns=turns, total_steps=total_steps,
        connection_points=[
            {"face": "bottom", "position": (0.0, 0.0, 0.0)},
            {"face": "top", "position": (0.0, 0.0, height)},
        ],
    )


def stair_ramp(
    width: float = 2.0,
    height: float = 3.0,
    depth: float = 4.0,
    seed: int = 42,
) -> MeshSpec:
    """Sloped ramp (no steps, smooth incline)."""
    t = 0.15  # ramp thickness
    # Top surface: slopes from (y=0,z=0) to (y=depth,z=height)
    verts: list[tuple[float, float, float]] = [
        # Top surface
        (0.0, 0.0, 0.0),
        (width, 0.0, 0.0),
        (width, depth, height),
        (0.0, depth, height),
        # Bottom surface
        (0.0, 0.0, -t),
        (width, 0.0, -t),
        (width, depth, height - t),
        (0.0, depth, height - t),
    ]
    faces: list[tuple[int, ...]] = [
        (0, 1, 2, 3),  # top
        (7, 6, 5, 4),  # bottom
        (0, 4, 5, 1),  # front
        (2, 6, 7, 3),  # back (this is actually the top edge)
        (0, 3, 7, 4),  # left
        (1, 5, 6, 2),  # right
    ]
    verts = _jitter(verts, 0.005, seed)
    return _make_result(
        "stair_ramp", verts, faces,
        style="stair", piece_type="stair_ramp",
        connection_points=[
            {"face": "front", "position": (width / 2, 0.0, 0.0)},
            {"face": "back", "position": (width / 2, depth, height)},
        ],
    )


# ---------------------------------------------------------------------------
# DOOR PIECES (3)
# ---------------------------------------------------------------------------

def door_single(
    style: str = "medieval",
    width: float = 1.0,
    height: float = 2.2,
    thickness: float = 0.06,
    seed: int = 42,
) -> MeshSpec:
    """Single door panel with style-appropriate frame."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    t = thickness
    # Door panel
    parts.append(_box(0.0, 0.0, 0.0, width, t, height))
    # Frame: top
    frame_w = 0.06
    parts.append(_box(-frame_w, -0.01, height, width + 2 * frame_w, t + 0.02, frame_w))
    # Frame: left
    parts.append(_box(-frame_w, -0.01, 0.0, frame_w, t + 0.02, height))
    # Frame: right
    parts.append(_box(width, -0.01, 0.0, frame_w, t + 0.02, height))
    # Handle (small box)
    handle_z = height * 0.45
    handle_side = 0.04
    parts.append(_box(width * 0.8, -0.02, handle_z, handle_side, 0.04, handle_side))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"door_single_{style}", verts, faces,
        style=style, piece_type="door_single",
        connection_points=[
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


def door_double(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 2.5,
    thickness: float = 0.06,
    seed: int = 42,
) -> MeshSpec:
    """Double door with center gap and frame."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    t = thickness
    half = width / 2
    gap = 0.02
    # Left panel
    parts.append(_box(0.0, 0.0, 0.0, half - gap / 2, t, height))
    # Right panel
    parts.append(_box(half + gap / 2, 0.0, 0.0, half - gap / 2, t, height))
    # Frame
    frame_w = 0.08
    parts.append(_box(-frame_w, -0.01, 0.0, frame_w, t + 0.02, height + frame_w))
    parts.append(_box(width, -0.01, 0.0, frame_w, t + 0.02, height + frame_w))
    parts.append(_box(-frame_w, -0.01, height, width + 2 * frame_w, t + 0.02, frame_w))
    # Handles
    handle_z = height * 0.45
    parts.append(_box(half - gap / 2 - 0.05, -0.02, handle_z, 0.03, 0.04, 0.03))
    parts.append(_box(half + gap / 2 + 0.02, -0.02, handle_z, 0.03, 0.04, 0.03))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"door_double_{style}", verts, faces,
        style=style, piece_type="door_double",
        connection_points=[
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


def door_arched(
    style: str = "medieval",
    width: float = 1.4,
    height: float = 2.4,
    thickness: float = 0.06,
    arch_segments: int = 8,
    seed: int = 42,
) -> MeshSpec:
    """Arched doorway with semicircular top."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    t = thickness
    # Door panel (rectangular part below arch)
    arch_radius = width / 2
    rect_height = height - arch_radius
    parts.append(_box(0.0, 0.0, 0.0, width, t, rect_height))

    # Arch segments (semicircle at top)
    cx = width / 2
    cz = rect_height
    arch_verts: list[tuple[float, float, float]] = []
    arch_faces: list[tuple[int, ...]] = []
    # Build arch as wedge segments
    for i in range(arch_segments):
        a0 = math.pi * i / arch_segments
        a1 = math.pi * (i + 1) / arch_segments
        x0 = cx + arch_radius * math.cos(math.pi - a0)
        z0 = cz + arch_radius * math.sin(a0)
        x1 = cx + arch_radius * math.cos(math.pi - a1)
        z1 = cz + arch_radius * math.sin(a1)
        b = len(arch_verts)
        arch_verts.extend([
            (x0, 0.0, z0),
            (x1, 0.0, z1),
            (x1, t, z1),
            (x0, t, z0),
        ])
        arch_faces.extend([
            (b, b + 1, b + 2, b + 3),  # outer face
        ])
    parts.append((arch_verts, arch_faces))

    # Frame
    frame_w = 0.07
    parts.append(_box(-frame_w, -0.01, 0.0, frame_w, t + 0.02, rect_height))
    parts.append(_box(width, -0.01, 0.0, frame_w, t + 0.02, rect_height))

    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"door_arched_{style}", verts, faces,
        style=style, piece_type="door_arched",
        connection_points=[
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


# ---------------------------------------------------------------------------
# WINDOW PIECES (3)
# ---------------------------------------------------------------------------

def window_small(
    style: str = "medieval",
    width: float = 0.5,
    height: float = 0.5,
    depth: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """Small square window with frame."""
    d = depth if depth > 0 else _get_thickness(style)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    frame_w = 0.04
    # Frame: 4 pieces
    parts.append(_box(0.0, 0.0, 0.0, width, d, frame_w))         # bottom
    parts.append(_box(0.0, 0.0, height - frame_w, width, d, frame_w))  # top
    parts.append(_box(0.0, 0.0, frame_w, frame_w, d, height - 2 * frame_w))  # left
    parts.append(_box(width - frame_w, 0.0, frame_w, frame_w, d, height - 2 * frame_w))  # right
    # Cross bar (horizontal)
    parts.append(_box(frame_w, 0.0, height / 2 - 0.01, width - 2 * frame_w, d, 0.02))
    # Cross bar (vertical)
    parts.append(_box(width / 2 - 0.01, 0.0, frame_w, 0.02, d, height - 2 * frame_w))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"window_small_{style}", verts, faces,
        style=style, piece_type="window_small",
        connection_points=[
            {"face": "back", "position": (width / 2, d, height / 2)},
        ],
    )


def window_large(
    style: str = "medieval",
    width: float = 0.8,
    height: float = 1.2,
    depth: float = 0.0,
    seed: int = 42,
) -> MeshSpec:
    """Large rectangular window with frame and mullion."""
    d = depth if depth > 0 else _get_thickness(style)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    frame_w = 0.05
    # Frame
    parts.append(_box(0.0, 0.0, 0.0, width, d, frame_w))
    parts.append(_box(0.0, 0.0, height - frame_w, width, d, frame_w))
    parts.append(_box(0.0, 0.0, frame_w, frame_w, d, height - 2 * frame_w))
    parts.append(_box(width - frame_w, 0.0, frame_w, frame_w, d, height - 2 * frame_w))
    # Horizontal mullion at 1/3 and 2/3
    for frac in [1 / 3, 2 / 3]:
        mz = height * frac - 0.01
        parts.append(_box(frame_w, 0.0, mz, width - 2 * frame_w, d, 0.02))
    # Vertical mullion center
    parts.append(_box(width / 2 - 0.01, 0.0, frame_w, 0.02, d, height - 2 * frame_w))
    # Sill (protruding ledge at bottom)
    parts.append(_box(-0.02, -0.04, -0.02, width + 0.04, d + 0.06, 0.02))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"window_large_{style}", verts, faces,
        style=style, piece_type="window_large",
        connection_points=[
            {"face": "back", "position": (width / 2, d, height / 2)},
        ],
    )


def window_pointed(
    style: str = "gothic",
    width: float = 0.6,
    height: float = 1.8,
    depth: float = 0.0,
    arch_segments: int = 8,
    seed: int = 42,
) -> MeshSpec:
    """Gothic pointed arch window."""
    d = depth if depth > 0 else _get_thickness(style)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    frame_w = 0.04

    # Rectangular frame section (below arch)
    arch_h = width * 0.6  # pointed arch height
    rect_h = height - arch_h

    # Frame sides
    parts.append(_box(0.0, 0.0, 0.0, frame_w, d, rect_h))  # left
    parts.append(_box(width - frame_w, 0.0, 0.0, frame_w, d, rect_h))  # right
    # Frame bottom
    parts.append(_box(0.0, 0.0, 0.0, width, d, frame_w))
    # Vertical mullion
    parts.append(_box(width / 2 - 0.01, 0.0, frame_w, 0.02, d, rect_h - frame_w))

    # Pointed arch at top (two arcs meeting at center peak)
    cx = width / 2
    peak_z = rect_h + arch_h
    arch_verts: list[tuple[float, float, float]] = []
    arch_faces: list[tuple[int, ...]] = []
    for i in range(arch_segments):
        frac0 = i / arch_segments
        frac1 = (i + 1) / arch_segments
        # Left arc
        a0 = frac0 * math.pi / 2
        a1 = frac1 * math.pi / 2
        x0 = cx - (cx - 0) * math.cos(a0)
        z0 = rect_h + arch_h * math.sin(a0)
        x1 = cx - (cx - 0) * math.cos(a1)
        z1 = rect_h + arch_h * math.sin(a1)
        b = len(arch_verts)
        arch_verts.extend([
            (x0, 0.0, z0), (x1, 0.0, z1),
            (x1, d, z1), (x0, d, z0),
        ])
        arch_faces.append((b, b + 1, b + 2, b + 3))
    # Right arc (mirror)
    for i in range(arch_segments):
        frac0 = i / arch_segments
        frac1 = (i + 1) / arch_segments
        a0 = frac0 * math.pi / 2
        a1 = frac1 * math.pi / 2
        x0 = cx + (width - cx) * math.cos(math.pi / 2 - a0)
        z0 = rect_h + arch_h * math.sin(math.pi / 2 - a0)
        x1 = cx + (width - cx) * math.cos(math.pi / 2 - a1)
        z1 = rect_h + arch_h * math.sin(math.pi / 2 - a1)
        b = len(arch_verts)
        arch_verts.extend([
            (x0, 0.0, z0), (x1, 0.0, z1),
            (x1, d, z1), (x0, d, z0),
        ])
        arch_faces.append((b, b + 1, b + 2, b + 3))
    parts.append((arch_verts, arch_faces))

    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"window_pointed_{style}", verts, faces,
        style=style, piece_type="window_pointed",
        connection_points=[
            {"face": "back", "position": (width / 2, d, height / 2)},
        ],
    )


# ---------------------------------------------------------------------------
# ADDITIONAL PIECES: Foundation, Columns, Balconies, Beams, Trim, etc.
# (27 new pieces to bring total from 25 to 52)
# ---------------------------------------------------------------------------


def foundation_block(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 0.4,
    seed: int = 42,
) -> MeshSpec:
    """Solid foundation block with stepped top profile."""
    t = _get_thickness(style) * 1.3
    parts = []
    # Main block
    parts.append(_box(0.0, 0.0, 0.0, width, t, height))
    # Stepped lip at top
    lip_h = 0.05
    parts.append(_box(-0.03, -0.03, height - lip_h, width + 0.06, t + 0.06, lip_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"foundation_block_{style}", verts, faces,
        style=style, piece_type="foundation_block",
        grid_size=(width, t, height),
        connection_points=[
            {"face": "top", "position": (width / 2, t / 2, height)},
            {"face": "left", "position": (0.0, t / 2, height / 2)},
            {"face": "right", "position": (width, t / 2, height / 2)},
        ],
    )


def foundation_stepped(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 0.6,
    steps: int = 3,
    seed: int = 42,
) -> MeshSpec:
    """Stepped foundation with progressively narrowing courses."""
    t = _get_thickness(style) * 1.5
    parts = []
    step_h = height / steps
    for si in range(steps):
        inset = si * 0.04
        parts.append(_box(inset, inset, si * step_h,
                          width - 2 * inset, t - 2 * inset, step_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"foundation_stepped_{style}", verts, faces,
        style=style, piece_type="foundation_stepped",
        grid_size=(width, t, height),
        connection_points=[
            {"face": "top", "position": (width / 2, t / 2, height)},
        ],
    )


def column_round(
    style: str = "medieval",
    height: float = 3.0,
    radius: float = 0.12,
    segments: int = 8,
    seed: int = 42,
) -> MeshSpec:
    """Round column with base and capital."""
    parts = []
    rng = random.Random(seed)
    # Base (wider)
    base_h = 0.1
    base_r = radius * 1.4
    bv: list[tuple[float, float, float]] = []
    bf: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        bv.append((math.cos(a) * base_r, math.sin(a) * base_r, 0.0))
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        bv.append((math.cos(a) * base_r, math.sin(a) * base_r, base_h))
    for i in range(segments):
        i2 = (i + 1) % segments
        bf.append((i, i2, i2 + segments, i + segments))
    bf.append(tuple(range(segments - 1, -1, -1)))
    bf.append(tuple(range(segments, 2 * segments)))
    parts.append((bv, bf))

    # Shaft
    sv: list[tuple[float, float, float]] = []
    sf: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        sv.append((math.cos(a) * radius, math.sin(a) * radius, base_h))
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        sv.append((math.cos(a) * radius, math.sin(a) * radius, height - base_h))
    for i in range(segments):
        i2 = (i + 1) % segments
        sf.append((i, i2, i2 + segments, i + segments))
    parts.append((sv, sf))

    # Capital (wider at top)
    cap_r = radius * 1.5
    cv: list[tuple[float, float, float]] = []
    cf: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        cv.append((math.cos(a) * radius, math.sin(a) * radius, height - base_h))
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        cv.append((math.cos(a) * cap_r, math.sin(a) * cap_r, height))
    for i in range(segments):
        i2 = (i + 1) % segments
        cf.append((i, i2, i2 + segments, i + segments))
    cf.append(tuple(range(segments, 2 * segments)))
    parts.append((cv, cf))

    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"column_round_{style}", verts, faces,
        style=style, piece_type="column_round",
        grid_size=(radius * 2, radius * 2, height),
        connection_points=[
            {"face": "top", "position": (0.0, 0.0, height)},
            {"face": "bottom", "position": (0.0, 0.0, 0.0)},
        ],
    )


def column_square(
    style: str = "medieval",
    height: float = 3.0,
    width: float = 0.2,
    seed: int = 42,
) -> MeshSpec:
    """Square column with chamfered base and capital."""
    parts = []
    # Base (wider)
    base_h = 0.1
    base_w = width * 1.4
    parts.append(_box(-base_w / 2, -base_w / 2, 0.0, base_w, base_w, base_h))
    # Shaft
    parts.append(_box(-width / 2, -width / 2, base_h, width, width, height - 2 * base_h))
    # Capital
    cap_w = width * 1.5
    parts.append(_box(-cap_w / 2, -cap_w / 2, height - base_h, cap_w, cap_w, base_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"column_square_{style}", verts, faces,
        style=style, piece_type="column_square",
        grid_size=(width, width, height),
        connection_points=[
            {"face": "top", "position": (0.0, 0.0, height)},
            {"face": "bottom", "position": (0.0, 0.0, 0.0)},
        ],
    )


def column_cluster(
    style: str = "gothic",
    height: float = 3.0,
    radius: float = 0.08,
    count: int = 4,
    seed: int = 42,
) -> MeshSpec:
    """Cluster of small columns arranged in a group (gothic pillar)."""
    parts = []
    segments = 6
    spread = radius * 2.5
    rng = random.Random(seed)
    for ci in range(count):
        angle = 2.0 * math.pi * ci / count
        cx = math.cos(angle) * spread
        cy = math.sin(angle) * spread
        # Each mini-column as a simple box approximation
        col_w = radius * 2
        parts.append(_box(cx - radius, cy - radius, 0.0, col_w, col_w, height))
    # Shared capital
    cap_r = spread + radius * 2
    parts.append(_box(-cap_r, -cap_r, height - 0.08, cap_r * 2, cap_r * 2, 0.08))
    # Shared base
    parts.append(_box(-cap_r, -cap_r, 0.0, cap_r * 2, cap_r * 2, 0.06))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"column_cluster_{style}", verts, faces,
        style=style, piece_type="column_cluster",
        grid_size=(cap_r * 2, cap_r * 2, height),
        connection_points=[
            {"face": "top", "position": (0.0, 0.0, height)},
        ],
    )


def balcony_simple(
    style: str = "medieval",
    width: float = 2.0,
    depth: float = 0.8,
    seed: int = 42,
) -> MeshSpec:
    """Simple balcony platform with railing."""
    t = _get_thickness(style)
    parts = []
    rng = random.Random(seed)
    # Platform slab
    slab_h = 0.1
    parts.append(_box(0.0, 0.0, 0.0, width, depth, slab_h))
    # Railing: 3 sides
    rail_h = 0.9
    rail_t = 0.04
    # Front rail
    parts.append(_box(0.0, depth - rail_t, slab_h, width, rail_t, rail_h))
    # Side rails
    parts.append(_box(0.0, 0.0, slab_h, rail_t, depth, rail_h))
    parts.append(_box(width - rail_t, 0.0, slab_h, rail_t, depth, rail_h))
    # Support brackets underneath
    bracket_w = 0.08
    bracket_h = 0.3
    for bx in [width * 0.2, width * 0.8]:
        parts.append(_box(bx - bracket_w / 2, 0.0, -bracket_h, bracket_w, depth * 0.6, bracket_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"balcony_simple_{style}", verts, faces,
        style=style, piece_type="balcony_simple",
        grid_size=(width, depth, slab_h + rail_h),
        connection_points=[
            {"face": "back", "position": (width / 2, 0.0, slab_h / 2)},
        ],
    )


def balcony_ornate(
    style: str = "gothic",
    width: float = 2.0,
    depth: float = 1.0,
    seed: int = 42,
) -> MeshSpec:
    """Ornate balcony with balusters and corbels."""
    parts = []
    rng = random.Random(seed)
    slab_h = 0.12
    # Platform
    parts.append(_box(0.0, 0.0, 0.0, width, depth, slab_h))
    # Decorative edge (thicker lip)
    parts.append(_box(-0.03, -0.03, 0.0, width + 0.06, depth + 0.03, 0.04))
    # Balusters along front
    baluster_count = max(3, int(width / 0.2))
    baluster_h = 0.8
    baluster_w = 0.04
    spacing = width / (baluster_count + 1)
    for bi in range(baluster_count):
        bx = spacing * (bi + 1) - baluster_w / 2
        parts.append(_box(bx, depth - baluster_w, slab_h, baluster_w, baluster_w, baluster_h))
    # Top rail
    parts.append(_box(0.0, depth - 0.05, slab_h + baluster_h, width, 0.05, 0.04))
    # Corbel brackets (3 under platform)
    for cx_frac in [0.15, 0.5, 0.85]:
        cx = width * cx_frac
        parts.append(_box(cx - 0.06, 0.0, -0.25, 0.12, depth * 0.5, 0.25))
        parts.append(_box(cx - 0.08, 0.0, -0.25, 0.16, depth * 0.3, 0.06))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"balcony_ornate_{style}", verts, faces,
        style=style, piece_type="balcony_ornate",
        grid_size=(width, depth, slab_h + baluster_h + 0.04),
        connection_points=[
            {"face": "back", "position": (width / 2, 0.0, slab_h / 2)},
        ],
    )


def beam_horizontal(
    style: str = "medieval",
    length: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Horizontal structural beam."""
    bw = 0.12
    bh = 0.15
    verts, faces = _box(0.0, 0.0, 0.0, length, bw, bh)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"beam_horizontal_{style}", verts, faces,
        style=style, piece_type="beam_horizontal",
        grid_size=(length, bw, bh),
        connection_points=[
            {"face": "left", "position": (0.0, bw / 2, bh / 2)},
            {"face": "right", "position": (length, bw / 2, bh / 2)},
        ],
    )


def beam_diagonal(
    style: str = "medieval",
    length: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Diagonal brace beam (45 degree)."""
    bw = 0.1
    bh = 0.1
    # Create a skewed box for diagonal orientation
    half_len = length / 2.0
    verts = [
        (0.0, 0.0, 0.0), (bw, 0.0, 0.0), (bw, bh, 0.0), (0.0, bh, 0.0),
        (half_len, 0.0, half_len), (half_len + bw, 0.0, half_len),
        (half_len + bw, bh, half_len), (half_len, bh, half_len),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    verts_list = list(verts)
    verts_list = _jitter(verts_list, _get_jitter(style), seed)
    return _make_result(
        f"beam_diagonal_{style}", verts_list, faces,
        style=style, piece_type="beam_diagonal",
        grid_size=(half_len + bw, bh, half_len),
        connection_points=[
            {"face": "bottom", "position": (bw / 2, bh / 2, 0.0)},
            {"face": "top", "position": (half_len + bw / 2, bh / 2, half_len)},
        ],
    )


def beam_cross(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """X-shaped cross brace (two diagonal beams)."""
    bw = 0.08
    bd = 0.08
    parts = []
    # Diagonal 1: bottom-left to top-right (approximated as thin box)
    parts.append(_box(0.0, 0.0, 0.0, width, bd, bw))
    parts.append(_box(0.0, 0.0, height - bw, width, bd, bw))
    # Diagonal 2 cross member
    parts.append(_box(width / 2 - bw / 2, 0.0, 0.0, bw, bd, height))
    # Center cross point
    parts.append(_box(width / 2 - bw, 0.0, height / 2 - bw, bw * 2, bd, bw * 2))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"beam_cross_{style}", verts, faces,
        style=style, piece_type="beam_cross",
        grid_size=(width, bd, height),
        connection_points=[
            {"face": "left", "position": (0.0, bd / 2, height / 2)},
            {"face": "right", "position": (width, bd / 2, height / 2)},
        ],
    )


def trim_baseboard(
    style: str = "medieval",
    length: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Baseboard trim molding along floor-wall junction."""
    h = 0.08
    d = 0.02
    lip_h = 0.015
    parts = []
    parts.append(_box(0.0, 0.0, 0.0, length, d, h))
    # Top lip (ogee profile approximation)
    parts.append(_box(0.0, -0.005, h, length, d + 0.005, lip_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"trim_baseboard_{style}", verts, faces,
        style=style, piece_type="trim_baseboard",
        grid_size=(length, d, h + lip_h),
        connection_points=[
            {"face": "back", "position": (length / 2, d, h / 2)},
        ],
    )


def trim_crown(
    style: str = "medieval",
    length: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Crown molding trim at ceiling-wall junction."""
    h = 0.06
    d = 0.04
    parts = []
    # Main profile
    parts.append(_box(0.0, 0.0, 0.0, length, d, h))
    # Cove section (angled)
    parts.append(_box(0.0, d, -0.02, length, d * 0.5, h + 0.02))
    # Small bead at bottom
    parts.append(_box(0.0, -0.005, -0.01, length, 0.01, 0.01))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"trim_crown_{style}", verts, faces,
        style=style, piece_type="trim_crown",
        grid_size=(length, d * 1.5, h),
        connection_points=[
            {"face": "back", "position": (length / 2, d, h / 2)},
        ],
    )


def trim_corner(
    style: str = "medieval",
    height: float = 3.0,
    seed: int = 42,
) -> MeshSpec:
    """Corner trim piece for wall junctions."""
    w = 0.06
    parts = []
    # L-shaped profile running vertically
    parts.append(_box(0.0, 0.0, 0.0, w, 0.02, height))
    parts.append(_box(-0.02, 0.0, 0.0, 0.02, w, height))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"trim_corner_{style}", verts, faces,
        style=style, piece_type="trim_corner",
        grid_size=(w, w, height),
        connection_points=[
            {"face": "bottom", "position": (w / 2, w / 2, 0.0)},
            {"face": "top", "position": (w / 2, w / 2, height)},
        ],
    )


def chimney_stack(
    style: str = "medieval",
    height: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Chimney stack with visible brick/stone coursework."""
    cw = 0.5
    cd = 0.5
    parts = []
    rng = random.Random(seed)
    # Main shaft
    parts.append(_box(0.0, 0.0, 0.0, cw, cd, height))
    # Corbeling near top (stepped outward)
    for ci in range(3):
        step_z = height - 0.3 + ci * 0.08
        step_inset = -0.02 * (ci + 1)
        parts.append(_box(step_inset, step_inset, step_z,
                          cw - 2 * step_inset, cd - 2 * step_inset, 0.06))
    # Cap
    parts.append(_box(-0.04, -0.04, height, cw + 0.08, cd + 0.08, 0.05))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"chimney_stack_{style}", verts, faces,
        style=style, piece_type="chimney_stack",
        grid_size=(cw, cd, height + 0.05),
        connection_points=[
            {"face": "bottom", "position": (cw / 2, cd / 2, 0.0)},
        ],
    )


def chimney_pot(
    style: str = "medieval",
    height: float = 0.4,
    seed: int = 42,
) -> MeshSpec:
    """Chimney pot (sits on top of chimney stack)."""
    parts = []
    r = 0.08
    segments = 6
    # Cylindrical pot
    cv: list[tuple[float, float, float]] = []
    cf: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        cv.append((math.cos(a) * r, math.sin(a) * r, 0.0))
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        cv.append((math.cos(a) * r, math.sin(a) * r, height))
    for i in range(segments):
        i2 = (i + 1) % segments
        cf.append((i, i2, i2 + segments, i + segments))
    cf.append(tuple(range(segments - 1, -1, -1)))
    parts.append((cv, cf))
    # Flared top rim
    rim_r = r * 1.3
    rv: list[tuple[float, float, float]] = []
    rf: list[tuple[int, ...]] = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        rv.append((math.cos(a) * r, math.sin(a) * r, height))
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        rv.append((math.cos(a) * rim_r, math.sin(a) * rim_r, height + 0.03))
    for i in range(segments):
        i2 = (i + 1) % segments
        rf.append((i, i2, i2 + segments, i + segments))
    parts.append((rv, rf))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"chimney_pot_{style}", verts, faces,
        style=style, piece_type="chimney_pot",
        grid_size=(r * 2, r * 2, height + 0.03),
        connection_points=[
            {"face": "bottom", "position": (0.0, 0.0, 0.0)},
        ],
    )


def arch_round(
    style: str = "medieval",
    width: float = 1.2,
    height: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Round (Roman) archway piece."""
    t = _get_thickness(style)
    parts = []
    # Jambs
    jamb_w = 0.12
    rect_h = height * 0.65
    parts.append(_box(0.0, 0.0, 0.0, jamb_w, t, rect_h))
    parts.append(_box(width - jamb_w, 0.0, 0.0, jamb_w, t, rect_h))
    # Arch voussoirs (semicircular)
    arch_r = width / 2
    arch_segs = 8
    for i in range(arch_segs):
        a0 = math.pi * i / arch_segs
        a1 = math.pi * (i + 1) / arch_segs
        x0 = width / 2 + math.cos(a0) * arch_r
        z0 = rect_h + math.sin(a0) * arch_r
        x1 = width / 2 + math.cos(a1) * arch_r
        z1 = rect_h + math.sin(a1) * arch_r
        bv = [
            (x0, 0.0, z0), (x1, 0.0, z1),
            (x1, t, z1), (x0, t, z0),
        ]
        bf = [(0, 1, 2, 3)]
        parts.append((bv, bf))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"arch_round_{style}", verts, faces,
        style=style, piece_type="arch_round",
        grid_size=(width, t, height),
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, rect_h / 2)},
            {"face": "right", "position": (width, t / 2, rect_h / 2)},
        ],
    )


def arch_pointed(
    style: str = "gothic",
    width: float = 1.0,
    height: float = 2.5,
    seed: int = 42,
) -> MeshSpec:
    """Pointed (Gothic) archway piece."""
    t = _get_thickness(style)
    parts = []
    jamb_w = 0.1
    rect_h = height * 0.6
    parts.append(_box(0.0, 0.0, 0.0, jamb_w, t, rect_h))
    parts.append(_box(width - jamb_w, 0.0, 0.0, jamb_w, t, rect_h))
    # Pointed arch (two arcs meeting at peak)
    arch_segs = 8
    peak_z = height
    hw = width / 2
    for i in range(arch_segs):
        frac0 = i / arch_segs
        frac1 = (i + 1) / arch_segs
        # Left arc
        x0 = frac0 * hw
        z0 = rect_h + frac0 * (peak_z - rect_h)
        x1 = frac1 * hw
        z1 = rect_h + frac1 * (peak_z - rect_h)
        bv = [(x0, 0.0, z0), (x1, 0.0, z1), (x1, t, z1), (x0, t, z0)]
        parts.append((bv, [(0, 1, 2, 3)]))
        # Right arc (mirror)
        rx0 = width - x0
        rx1 = width - x1
        bv2 = [(rx0, 0.0, z0), (rx1, 0.0, z1), (rx1, t, z1), (rx0, t, z0)]
        parts.append((bv2, [(0, 1, 2, 3)]))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"arch_pointed_{style}", verts, faces,
        style=style, piece_type="arch_pointed",
        grid_size=(width, t, height),
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, rect_h / 2)},
            {"face": "right", "position": (width, t / 2, rect_h / 2)},
        ],
    )


def battlement_wall(
    style: str = "fortress",
    width: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Battlement parapet section with merlons and crenels."""
    t = _get_thickness(style)
    parts = []
    # Parapet base
    parapet_h = 0.5
    parts.append(_box(0.0, 0.0, 0.0, width, t, parapet_h))
    # Merlons
    merlon_w = 0.25
    merlon_h = 0.4
    crenel_w = 0.2
    x = 0.0
    while x + merlon_w <= width:
        parts.append(_box(x, 0.0, parapet_h, merlon_w, t, merlon_h))
        x += merlon_w + crenel_w
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"battlement_wall_{style}", verts, faces,
        style=style, piece_type="battlement_wall",
        grid_size=(width, t, parapet_h + merlon_h),
        connection_points=[
            {"face": "left", "position": (0.0, t / 2, parapet_h / 2)},
            {"face": "right", "position": (width, t / 2, parapet_h / 2)},
        ],
    )


def battlement_tower(
    style: str = "fortress",
    width: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Corner battlement tower piece (L-shaped parapet)."""
    t = _get_thickness(style)
    parts = []
    parapet_h = 0.5
    merlon_h = 0.4
    merlon_w = 0.25
    # L-shaped base
    parts.append(_box(0.0, 0.0, 0.0, width, t, parapet_h))
    parts.append(_box(0.0, 0.0, 0.0, t, width, parapet_h))
    # Merlons on both arms
    for mx in [0.0, width - merlon_w]:
        parts.append(_box(mx, 0.0, parapet_h, merlon_w, t, merlon_h))
    for my in [0.0, width - merlon_w]:
        parts.append(_box(0.0, my, parapet_h, t, merlon_w, merlon_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"battlement_tower_{style}", verts, faces,
        style=style, piece_type="battlement_tower",
        grid_size=(width, width, parapet_h + merlon_h),
        connection_points=[
            {"face": "right", "position": (width, t / 2, parapet_h / 2)},
            {"face": "back", "position": (t / 2, width, parapet_h / 2)},
        ],
    )


def dormer_gable(
    style: str = "medieval",
    width: float = 1.0,
    height: float = 1.2,
    seed: int = 42,
) -> MeshSpec:
    """Gable-roofed dormer window projection."""
    t = _get_thickness(style)
    depth = 0.6
    parts = []
    # Dormer walls
    wall_h = height * 0.6
    parts.append(_box(0.0, 0.0, 0.0, t * 0.5, depth, wall_h))  # left
    parts.append(_box(width - t * 0.5, 0.0, 0.0, t * 0.5, depth, wall_h))  # right
    # Front wall with window opening
    parts.append(_box(0.0, 0.0, 0.0, width, t * 0.5, wall_h))
    # Mini gable roof
    ridge_h = height - wall_h
    parts.append(_box(0.0, 0.0, wall_h, width, depth, 0.04))  # base
    # Triangle front
    tv = [
        (0.0, 0.0, wall_h), (width, 0.0, wall_h),
        (width / 2, 0.0, height),
        (0.0, 0.04, wall_h), (width, 0.04, wall_h),
        (width / 2, 0.04, height),
    ]
    tf = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    parts.append((tv, tf))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"dormer_gable_{style}", verts, faces,
        style=style, piece_type="dormer_gable",
        grid_size=(width, depth, height),
        connection_points=[
            {"face": "bottom", "position": (width / 2, depth / 2, 0.0)},
        ],
    )


def dormer_shed(
    style: str = "medieval",
    width: float = 1.0,
    height: float = 1.0,
    seed: int = 42,
) -> MeshSpec:
    """Shed-roofed dormer (single slope)."""
    depth = 0.5
    t = _get_thickness(style)
    parts = []
    wall_h = height * 0.7
    # Side walls (one taller than other for shed slope)
    parts.append(_box(0.0, 0.0, 0.0, t * 0.4, depth, wall_h))
    parts.append(_box(width - t * 0.4, 0.0, 0.0, t * 0.4, depth, wall_h * 0.7))
    # Front wall
    parts.append(_box(0.0, 0.0, 0.0, width, t * 0.4, wall_h))
    # Roof slab (angled)
    parts.append(_box(0.0, 0.0, wall_h, width, depth + 0.1, 0.04))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"dormer_shed_{style}", verts, faces,
        style=style, piece_type="dormer_shed",
        grid_size=(width, depth, height),
        connection_points=[
            {"face": "bottom", "position": (width / 2, depth / 2, 0.0)},
        ],
    )


def awning_simple(
    style: str = "medieval",
    width: float = 2.0,
    depth: float = 0.8,
    seed: int = 42,
) -> MeshSpec:
    """Simple awning/canopy projection over door or window."""
    parts = []
    # Angled canopy surface
    canopy_h = 0.03
    parts.append(_box(0.0, 0.0, 0.0, width, depth, canopy_h))
    # Support brackets
    bracket_w = 0.04
    bracket_h = 0.3
    for bx in [0.05, width - 0.05 - bracket_w]:
        parts.append(_box(bx, 0.0, -bracket_h, bracket_w, depth * 0.5, bracket_h))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"awning_simple_{style}", verts, faces,
        style=style, piece_type="awning_simple",
        grid_size=(width, depth, canopy_h + bracket_h),
        connection_points=[
            {"face": "back", "position": (width / 2, 0.0, 0.0)},
        ],
    )


def bracket_corbel(
    style: str = "gothic",
    height: float = 0.3,
    seed: int = 42,
) -> MeshSpec:
    """Decorative corbel bracket for supporting beams or balconies."""
    w = 0.15
    d = 0.2
    parts = []
    # Main bracket body (tapered)
    parts.append(_box(0.0, 0.0, 0.0, w, d, height))
    # Tapered bottom
    parts.append(_box(w * 0.15, d * 0.15, 0.0, w * 0.7, d * 0.7, height * 0.4))
    # Top platform
    parts.append(_box(-0.02, -0.02, height, w + 0.04, d + 0.04, 0.03))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"bracket_corbel_{style}", verts, faces,
        style=style, piece_type="bracket_corbel",
        grid_size=(w, d, height),
        connection_points=[
            {"face": "back", "position": (w / 2, 0.0, height / 2)},
            {"face": "top", "position": (w / 2, d / 2, height)},
        ],
    )


def gable_end(
    style: str = "medieval",
    width: float = 2.0,
    height: float = 1.5,
    seed: int = 42,
) -> MeshSpec:
    """Triangular gable end wall piece."""
    t = _get_thickness(style) * 0.5
    # Triangular prism
    verts = [
        (0.0, 0.0, 0.0), (width, 0.0, 0.0), (width / 2, 0.0, height),
        (0.0, t, 0.0), (width, t, 0.0), (width / 2, t, height),
    ]
    faces = [
        (0, 1, 2), (5, 4, 3),
        (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0),
    ]
    verts_list = list(verts)
    verts_list = _jitter(verts_list, _get_jitter(style), seed)
    return _make_result(
        f"gable_end_{style}", verts_list, faces,
        style=style, piece_type="gable_end",
        grid_size=(width, t, height),
        connection_points=[
            {"face": "bottom", "position": (width / 2, t / 2, 0.0)},
        ],
    )


def pillar_base(
    style: str = "medieval",
    width: float = 0.4,
    seed: int = 42,
) -> MeshSpec:
    """Pillar/column base piece with stepped profile."""
    parts = []
    h = 0.15
    # Bottom step (widest)
    parts.append(_box(0.0, 0.0, 0.0, width, width, h * 0.4))
    # Middle step
    inset1 = width * 0.1
    parts.append(_box(inset1, inset1, h * 0.4,
                       width - 2 * inset1, width - 2 * inset1, h * 0.3))
    # Top step (meets column)
    inset2 = width * 0.2
    parts.append(_box(inset2, inset2, h * 0.7,
                       width - 2 * inset2, width - 2 * inset2, h * 0.3))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"pillar_base_{style}", verts, faces,
        style=style, piece_type="pillar_base",
        grid_size=(width, width, h),
        connection_points=[
            {"face": "top", "position": (width / 2, width / 2, h)},
        ],
    )


def pillar_capital(
    style: str = "medieval",
    width: float = 0.4,
    seed: int = 42,
) -> MeshSpec:
    """Pillar/column capital piece with flared profile."""
    parts = []
    h = 0.12
    # Narrow bottom (meets column)
    inset = width * 0.2
    parts.append(_box(inset, inset, 0.0,
                       width - 2 * inset, width - 2 * inset, h * 0.4))
    # Flared middle
    inset2 = width * 0.08
    parts.append(_box(inset2, inset2, h * 0.4,
                       width - 2 * inset2, width - 2 * inset2, h * 0.3))
    # Wide top (supports beam/arch)
    parts.append(_box(0.0, 0.0, h * 0.7, width, width, h * 0.3))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"pillar_capital_{style}", verts, faces,
        style=style, piece_type="pillar_capital",
        grid_size=(width, width, h),
        connection_points=[
            {"face": "bottom", "position": (width / 2, width / 2, 0.0)},
            {"face": "top", "position": (width / 2, width / 2, h)},
        ],
    )


def bay_window(
    style: str = "medieval",
    width: float = 1.5,
    height: float = 2.0,
    seed: int = 42,
) -> MeshSpec:
    """Bay window projection (3-sided box protruding from wall)."""
    t = _get_thickness(style)
    depth = 0.6
    parts = []
    # 3 window walls
    panel_w = width / 3
    # Front panel
    parts.append(_box(panel_w, 0.0, 0.0, panel_w, t * 0.5, height))
    # Left angled panel
    parts.append(_box(0.0, t * 0.5, 0.0, panel_w, depth - t * 0.5, t * 0.5))
    parts.append(_box(0.0, 0.0, 0.0, t * 0.5, depth, height))
    # Right angled panel
    parts.append(_box(width - t * 0.5, 0.0, 0.0, t * 0.5, depth, height))
    # Floor slab
    parts.append(_box(0.0, 0.0, 0.0, width, depth, 0.08))
    # Ceiling slab
    parts.append(_box(0.0, 0.0, height - 0.06, width, depth, 0.06))
    verts, faces, uvs = _merge_geometry(parts)
    verts = _jitter(verts, _get_jitter(style), seed)
    return _make_result(
        f"bay_window_{style}", verts, faces,
        style=style, piece_type="bay_window",
        grid_size=(width, depth, height),
        connection_points=[
            {"face": "back", "position": (width / 2, depth, height / 2)},
        ],
    )


# ---------------------------------------------------------------------------
# PIECE REGISTRY
# ---------------------------------------------------------------------------

MODULAR_KIT_GENERATORS: dict[str, Any] = {
    # Walls
    "wall_solid": wall_solid,
    "wall_window": wall_window,
    "wall_door": wall_door,
    "wall_damaged": wall_damaged,
    "wall_half": wall_half,
    "wall_corner_inner": wall_corner_inner,
    "wall_corner_outer": wall_corner_outer,
    "wall_t_junction": wall_t_junction,
    "wall_end_cap": wall_end_cap,
    # Floors
    "floor_stone": floor_stone,
    "floor_wood": floor_wood,
    "floor_dirt": floor_dirt,
    # Roofs
    "roof_slope": roof_slope,
    "roof_peak": roof_peak,
    "roof_flat": roof_flat,
    "roof_gutter": roof_gutter,
    # Stairs
    "stair_straight": stair_straight,
    "stair_spiral": stair_spiral,
    "stair_ramp": stair_ramp,
    # Doors
    "door_single": door_single,
    "door_double": door_double,
    "door_arched": door_arched,
    # Windows
    "window_small": window_small,
    "window_large": window_large,
    "window_pointed": window_pointed,
    # Foundations
    "foundation_block": foundation_block,
    "foundation_stepped": foundation_stepped,
    # Columns
    "column_round": column_round,
    "column_square": column_square,
    "column_cluster": column_cluster,
    # Balconies
    "balcony_simple": balcony_simple,
    "balcony_ornate": balcony_ornate,
    # Beams
    "beam_horizontal": beam_horizontal,
    "beam_diagonal": beam_diagonal,
    "beam_cross": beam_cross,
    # Trim
    "trim_baseboard": trim_baseboard,
    "trim_crown": trim_crown,
    "trim_corner": trim_corner,
    # Chimneys
    "chimney_stack": chimney_stack,
    "chimney_pot": chimney_pot,
    # Arches
    "arch_round": arch_round,
    "arch_pointed": arch_pointed,
    # Battlements
    "battlement_wall": battlement_wall,
    "battlement_tower": battlement_tower,
    # Dormers
    "dormer_gable": dormer_gable,
    "dormer_shed": dormer_shed,
    # Misc
    "awning_simple": awning_simple,
    "bracket_corbel": bracket_corbel,
    "gable_end": gable_end,
    "pillar_base": pillar_base,
    "pillar_capital": pillar_capital,
    "bay_window": bay_window,
}

# All piece type names
ALL_PIECE_TYPES = list(MODULAR_KIT_GENERATORS.keys())


# ---------------------------------------------------------------------------
# Entry Points
# ---------------------------------------------------------------------------

def generate_modular_piece(
    piece_type: str,
    style: str = "medieval",
    **kwargs: Any,
) -> MeshSpec:
    """Main dispatch -- generate any modular piece by type and style.

    Args:
        piece_type: One of ALL_PIECE_TYPES (e.g. 'wall_solid', 'floor_stone').
        style: One of STYLES ('medieval', 'gothic', 'fortress', 'organic', 'ruined').
        **kwargs: Forwarded to the piece generator function.

    Returns:
        MeshSpec dict with vertices, faces, and metadata.
    """
    if piece_type not in MODULAR_KIT_GENERATORS:
        raise ValueError(
            f"Unknown piece type '{piece_type}'. "
            f"Available: {ALL_PIECE_TYPES}"
        )
    if style not in STYLES:
        raise ValueError(
            f"Unknown style '{style}'. Available: {list(STYLES)}"
        )
    gen_fn = MODULAR_KIT_GENERATORS[piece_type]
    # Determine which kwargs the function accepts
    import inspect
    sig = inspect.signature(gen_fn)
    params = sig.parameters
    # Build filtered kwargs
    call_kwargs: dict[str, Any] = {}
    if "style" in params:
        call_kwargs["style"] = style
    for k, v in kwargs.items():
        if k in params:
            call_kwargs[k] = v
    return gen_fn(**call_kwargs)


def get_available_pieces() -> dict[str, list[str]]:
    """Return all available piece types organized by category.

    Returns:
        Dict mapping category name to list of piece type names.
    """
    categories: dict[str, list[str]] = {
        "walls": [k for k in ALL_PIECE_TYPES if k.startswith("wall_")],
        "floors": [k for k in ALL_PIECE_TYPES if k.startswith("floor_")],
        "roofs": [k for k in ALL_PIECE_TYPES if k.startswith("roof_")],
        "stairs": [k for k in ALL_PIECE_TYPES if k.startswith("stair_")],
        "doors": [k for k in ALL_PIECE_TYPES if k.startswith("door_")],
        "windows": [k for k in ALL_PIECE_TYPES if k.startswith("window_")],
    }
    return {
        "styles": list(STYLES),
        "categories": categories,
        "total_piece_types": len(ALL_PIECE_TYPES),
        "total_variants": len(ALL_PIECE_TYPES) * len(STYLES),
    }


def assemble_building(
    spec: list[dict[str, Any]],
) -> MeshSpec:
    """Assemble a building from a list of piece placements.

    Each entry in spec is:
        {
            "piece_type": "wall_solid",
            "style": "medieval",
            "position": [x, y, z],
            "rotation_z": 0.0,  # degrees, optional
            **piece_kwargs
        }

    Returns combined MeshSpec with all pieces merged.
    """
    all_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    piece_count = 0

    for entry in spec:
        piece_type = entry["piece_type"]
        style = entry.get("style", "medieval")
        pos = entry.get("position", [0.0, 0.0, 0.0])
        rot_z = math.radians(entry.get("rotation_z", 0.0))

        # Extract piece-specific kwargs
        piece_kwargs = {
            k: v for k, v in entry.items()
            if k not in ("piece_type", "style", "position", "rotation_z")
        }

        result = generate_modular_piece(piece_type, style, **piece_kwargs)
        verts = result["vertices"]
        faces = result["faces"]

        # Apply rotation around Z axis, then translation
        cos_r, sin_r = math.cos(rot_z), math.sin(rot_z)
        transformed: list[tuple[float, float, float]] = []
        for x, y, z in verts:
            rx = x * cos_r - y * sin_r + pos[0]
            ry = x * sin_r + y * cos_r + pos[1]
            rz = z + pos[2]
            transformed.append((rx, ry, rz))

        all_parts.append((transformed, faces))
        piece_count += 1

    merged_verts, merged_faces, _merged_uvs = _merge_geometry(all_parts)
    return _make_result(
        "assembled_building", merged_verts, merged_faces,
        style="mixed", piece_type="assembly",
        piece_count=piece_count,
    )
