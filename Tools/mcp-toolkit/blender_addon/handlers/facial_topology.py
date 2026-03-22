"""Facial topology, hand/foot anatomy, monster extremities, and corrective blend shapes.

Pure-logic module (NO bpy imports). Provides:
- generate_face_mesh: AAA face mesh with concentric quad loops
- generate_blend_shape_targets: 30 FACS-based blend shape targets
- generate_hand_mesh: Anatomical hand with configurable finger count (2-5),
  nail geometry, knuckle bumps, palm curvature, webbing
- generate_foot_mesh: Anatomical foot with configurable toe count (1-5),
  toenails, arch curvature, ankle bones
- generate_claw_hand_mesh: Monster claw hand with sharp/hooked/blunt talons
- generate_hoof_mesh: Hooved foot (horse/cloven/padded styles)
- generate_paw_mesh: Animal paw with toe beans and optional claws
- generate_corrective_shapes: Corrective blend shapes for joint deformation

All functions return pure data (vertices, faces, shape deltas).
Fulfils Tasks #53, #54, #55.
"""

from __future__ import annotations

import math
from typing import Any

from .procedural_meshes import _make_result, MeshSpec

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
FaceList = list[tuple[int, ...]]

# ---------------------------------------------------------------------------
# Detail level specs
# ---------------------------------------------------------------------------

FACE_DETAIL_SPECS: dict[str, dict[str, Any]] = {
    "low": {
        "target_verts": 200,
        "eye_loops": 4,
        "mouth_loops": 3,
        "ring_segments": 8,
        "vertical_rings": 6,
        "has_ears": False,
        "nose_detail": 1,
    },
    "medium": {
        "target_verts": 400,
        "eye_loops": 5,
        "mouth_loops": 4,
        "ring_segments": 12,
        "vertical_rings": 8,
        "has_ears": True,
        "nose_detail": 2,
    },
    "high": {
        "target_verts": 800,
        "eye_loops": 7,
        "mouth_loops": 5,
        "ring_segments": 16,
        "vertical_rings": 12,
        "has_ears": True,
        "nose_detail": 3,
    },
}

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _ring_verts(
    cx: float, cy: float, cz: float,
    rx: float, ry: float,
    segments: int,
    start_angle: float = 0.0,
) -> list[Vec3]:
    """Generate a ring of vertices in the XZ plane at height cy."""
    pts: list[Vec3] = []
    for i in range(segments):
        angle = start_angle + 2.0 * math.pi * i / segments
        x = cx + math.cos(angle) * rx
        z = cz + math.sin(angle) * ry
        pts.append((x, cy, z))
    return pts


def _connect_rings_quad(
    base_a: int, base_b: int, segments: int,
) -> list[tuple[int, int, int, int]]:
    """Connect two rings with quad faces."""
    faces: list[tuple[int, int, int, int]] = []
    for i in range(segments):
        i_next = (i + 1) % segments
        faces.append((base_a + i, base_a + i_next, base_b + i_next, base_b + i))
    return faces


def _elliptical_loop(
    cx: float, cy: float, cz: float,
    rx: float, ry: float,
    count: int,
    tilt: float = 0.0,
) -> list[Vec3]:
    """Generate an elliptical ring of vertices, optionally tilted.

    The ring lies in the XZ plane centered at (cx, cy, cz) with radii rx, ry.
    tilt rotates the ring around the X axis (radians).
    """
    pts: list[Vec3] = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        lx = math.cos(angle) * rx
        lz = math.sin(angle) * ry
        # Apply tilt (rotation around X axis)
        ly = -lz * math.sin(tilt)
        lz_rot = lz * math.cos(tilt)
        pts.append((cx + lx, cy + ly, cz + lz_rot))
    return pts


# ---------------------------------------------------------------------------
# Task #53: Face mesh generation
# ---------------------------------------------------------------------------


def generate_face_mesh(detail_level: str = "medium") -> MeshSpec:
    """Generate a face mesh with proper AAA topology.

    Builds the face from anatomically-placed concentric quad loops:
    - Concentric loops around each eye (orbicularis oculi)
    - Elliptical loops around the mouth connecting to nasolabial folds
    - Brow ridge with forehead loops
    - Nostril loops
    - Ear geometry (medium/high only)
    - Chin definition
    - All quads, with triangles only at ear/nose tips

    Args:
        detail_level: One of "low", "medium", "high".

    Returns:
        MeshSpec with vertices, faces, metadata including loop counts.
    """
    if detail_level not in FACE_DETAIL_SPECS:
        detail_level = "medium"

    spec = FACE_DETAIL_SPECS[detail_level]
    eye_loops = spec["eye_loops"]
    mouth_loops = spec["mouth_loops"]
    ring_seg = spec["ring_segments"]
    v_rings = spec["vertical_rings"]
    has_ears = spec["has_ears"]
    nose_detail = spec["nose_detail"]

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []

    # Face dimensions (meters, for ~0.24m tall head)
    face_width = 0.08
    face_height = 0.12
    face_depth = 0.10

    # Center of face
    fc_x = 0.0
    fc_y = 0.0  # forward axis (depth)
    fc_z = 0.0  # vertical center

    # ----- Base face surface: vertical quad strips -----
    # Create the main face surface as a grid of quads
    cols = ring_seg
    rows = v_rings

    base_grid_start = len(all_verts)
    for row in range(rows + 1):
        t_v = row / rows
        z = fc_z - face_height / 2 + t_v * face_height

        for col in range(cols + 1):
            t_u = col / cols
            x = fc_x - face_width / 2 + t_u * face_width

            # Face curvature: ellipsoidal profile
            x_frac = (t_u - 0.5) * 2.0  # [-1, 1]
            z_frac = (t_v - 0.5) * 2.0  # [-1, 1]
            r_sq = x_frac * x_frac + z_frac * z_frac
            y = fc_y + face_depth * 0.5 * max(0.0, 1.0 - r_sq * 0.6)

            # Nose protrusion at center-upper area
            nose_zone = max(0.0, 1.0 - abs(x_frac) * 4.0)
            nose_vert = max(0.0, 1.0 - abs(z_frac - 0.15) * 5.0)
            y += nose_zone * nose_vert * 0.025 * (1 + nose_detail * 0.3)

            # Chin protrusion
            chin_zone = max(0.0, 1.0 - abs(x_frac) * 3.0)
            chin_vert = max(0.0, 1.0 - abs(z_frac + 0.7) * 4.0)
            y += chin_zone * chin_vert * 0.01

            # Brow ridge
            brow_zone = max(0.0, 1.0 - abs(z_frac - 0.5) * 6.0)
            y += brow_zone * 0.008

            all_verts.append((x, y, z))

    # Create quad faces for the base grid
    grid_cols = cols + 1
    for row in range(rows):
        for col in range(cols):
            v0 = base_grid_start + row * grid_cols + col
            v1 = v0 + 1
            v2 = v0 + grid_cols + 1
            v3 = v0 + grid_cols
            all_faces.append((v0, v1, v2, v3))

    # ----- Eye loops (concentric quads around each eye socket) -----
    eye_z = fc_z + face_height * 0.15  # eyes at ~65% up
    eye_spacing = face_width * 0.28
    eye_socket_rx = 0.012
    eye_socket_ry = 0.008

    eye_loop_data: dict[str, dict[str, Any]] = {}

    for side_name, side_sign in [("left", -1.0), ("right", 1.0)]:
        eye_cx = fc_x + side_sign * eye_spacing
        eye_cy = fc_y + face_depth * 0.48
        eye_cz = eye_z

        eye_base = len(all_verts)
        ring_bases: list[int] = []

        for loop_i in range(eye_loops):
            t = (loop_i + 1) / (eye_loops + 1)
            rx = eye_socket_rx * t
            ry = eye_socket_ry * t
            n_pts = max(4, ring_seg // 2 + loop_i * 2)

            ring_start = len(all_verts)
            ring_bases.append(ring_start)

            ring = _elliptical_loop(eye_cx, eye_cy, eye_cz, rx, ry, n_pts)
            all_verts.extend(ring)

            # Connect to previous ring with quads
            if loop_i > 0:
                prev_base = ring_bases[loop_i - 1]
                prev_count = max(4, ring_seg // 2 + (loop_i - 1) * 2)
                curr_count = n_pts

                # Match vertex counts between rings
                for j in range(min(prev_count, curr_count)):
                    j_next_prev = (j + 1) % prev_count
                    j_next_curr = (j + 1) % curr_count
                    all_faces.append((
                        prev_base + j,
                        prev_base + j_next_prev,
                        ring_start + j_next_curr,
                        ring_start + j,
                    ))

        eye_loop_data[side_name] = {
            "center": (eye_cx, eye_cy, eye_cz),
            "loop_count": eye_loops,
            "vertex_start": eye_base,
            "vertex_count": len(all_verts) - eye_base,
        }

    # ----- Mouth loops (elliptical quads around mouth) -----
    mouth_cz = fc_z - face_height * 0.15
    mouth_cx = fc_x
    mouth_cy = fc_y + face_depth * 0.45
    mouth_rx = 0.018
    mouth_ry = 0.008

    mouth_base = len(all_verts)
    mouth_ring_bases: list[int] = []

    for loop_i in range(mouth_loops):
        t = (loop_i + 1) / (mouth_loops + 1)
        rx = mouth_rx * t
        ry = mouth_ry * t
        n_pts = max(6, ring_seg // 2 + loop_i * 2)

        ring_start = len(all_verts)
        mouth_ring_bases.append(ring_start)

        ring = _elliptical_loop(mouth_cx, mouth_cy, mouth_cz, rx, ry, n_pts)
        all_verts.extend(ring)

        if loop_i > 0:
            prev_base = mouth_ring_bases[loop_i - 1]
            prev_count = max(6, ring_seg // 2 + (loop_i - 1) * 2)
            curr_count = n_pts

            for j in range(min(prev_count, curr_count)):
                j_next_prev = (j + 1) % prev_count
                j_next_curr = (j + 1) % curr_count
                all_faces.append((
                    prev_base + j,
                    prev_base + j_next_prev,
                    ring_start + j_next_curr,
                    ring_start + j,
                ))

    mouth_vert_count = len(all_verts) - mouth_base

    # ----- Nasolabial folds (connecting nose to mouth corners) -----
    # Bug 1 fix: generate connecting quad faces between nasolabial fold vertices
    # and adjacent face topology. Each side gets a strip of quads connecting
    # consecutive fold vertices via paired inner/outer vertices.
    naso_pairs = min(nose_detail + 1, 3)
    naso_base = len(all_verts)
    for side_idx, side_sign in enumerate([-1.0, 1.0]):
        side_start = len(all_verts)
        # Generate paired inner/outer vertices for each fold point
        for i in range(naso_pairs):
            t = (i + 1) / (naso_pairs + 1)
            x = fc_x + side_sign * mouth_rx * 1.2 * (1.0 - t * 0.3)
            z_start = eye_z - face_height * 0.1
            z_end = mouth_cz + mouth_ry * 1.5
            z = z_start + t * (z_end - z_start)
            y = fc_y + face_depth * 0.44 - t * 0.005
            # Outer fold vertex (crease)
            all_verts.append((x, y, z))
            # Inner fold vertex (slightly inward toward nose/mouth center)
            inner_x = x - side_sign * 0.003
            inner_y = y + 0.002  # slightly forward
            all_verts.append((inner_x, inner_y, z))

        # Connect consecutive nasolabial fold vertex pairs with quads
        for i in range(naso_pairs - 1):
            v_outer_0 = side_start + i * 2
            v_inner_0 = side_start + i * 2 + 1
            v_outer_1 = side_start + (i + 1) * 2
            v_inner_1 = side_start + (i + 1) * 2 + 1
            all_faces.append((v_outer_0, v_inner_0, v_inner_1, v_outer_1))

    # ----- Nostril loops -----
    nostril_z = fc_z + face_height * 0.05
    nostril_rx = 0.004 * (1 + nose_detail * 0.2)
    nostril_ry = 0.003

    for side_sign in [-1.0, 1.0]:
        nostril_cx = fc_x + side_sign * 0.007
        nostril_cy = fc_y + face_depth * 0.52
        n_pts = 4 + nose_detail * 2

        ring_start = len(all_verts)
        ring = _elliptical_loop(
            nostril_cx, nostril_cy, nostril_z,
            nostril_rx, nostril_ry, n_pts,
        )
        all_verts.extend(ring)

        # Close nostril ring with quads/tris
        for j in range(n_pts - 1):
            j_next = j + 1
            if j_next < n_pts - 1:
                all_faces.append((
                    ring_start + j,
                    ring_start + j_next,
                    ring_start + j_next + 1,
                    ring_start + (j + 2) % n_pts,
                ))

    # ----- Ear geometry (medium/high only) -----
    ear_vert_count = 0
    if has_ears:
        for side_sign in [-1.0, 1.0]:
            ear_cx = fc_x + side_sign * face_width * 0.5
            ear_cy = fc_y - face_depth * 0.1
            ear_cz = eye_z - 0.005

            ear_base = len(all_verts)
            ear_height = 0.03
            ear_width = 0.012
            ear_rows = 3 + nose_detail
            ear_cols = 3

            for row in range(ear_rows + 1):
                t_v = row / ear_rows
                ez = ear_cz - ear_height / 2 + t_v * ear_height
                for col in range(ear_cols + 1):
                    t_u = col / ear_cols
                    # Ear curvature: C-shape
                    depth_curve = math.sin(t_v * math.pi) * 0.008
                    width_curve = math.sin(t_u * math.pi) * ear_width * 0.5
                    ex = ear_cx + side_sign * (width_curve + 0.002)
                    ey = ear_cy - depth_curve
                    all_verts.append((ex, ey, ez))

            # Ear quad faces
            ear_grid_cols = ear_cols + 1
            for row in range(ear_rows):
                for col in range(ear_cols):
                    v0 = ear_base + row * ear_grid_cols + col
                    v1 = v0 + 1
                    v2 = v0 + ear_grid_cols + 1
                    v3 = v0 + ear_grid_cols
                    all_faces.append((v0, v1, v2, v3))

            # Ear tip triangle (only allowed triangle)
            top_row_start = ear_base + ear_rows * ear_grid_cols
            mid_col = ear_cols // 2
            if mid_col + 1 < ear_grid_cols:
                tip_vert = len(all_verts)
                tip_x = ear_cx + side_sign * ear_width * 0.3
                tip_y = ear_cy - 0.003
                tip_z = ear_cz + ear_height * 0.48
                all_verts.append((tip_x, tip_y, tip_z))
                all_faces.append((
                    top_row_start + mid_col,
                    top_row_start + mid_col + 1,
                    tip_vert,
                ))
                ear_vert_count += 1

            ear_vert_count += (ear_rows + 1) * (ear_cols + 1)

    # ----- Forehead / brow loops -----
    brow_z = fc_z + face_height * 0.35
    brow_rows = 2 + nose_detail
    brow_base = len(all_verts)

    for row in range(brow_rows):
        t = row / max(brow_rows - 1, 1)
        z = brow_z + t * face_height * 0.15
        brow_curve_depth = 0.003 * (1.0 - t)
        n_pts = ring_seg // 2 + 2

        for i in range(n_pts):
            t_u = i / max(n_pts - 1, 1)
            x = fc_x - face_width * 0.35 + t_u * face_width * 0.7
            y = fc_y + face_depth * 0.46 + brow_curve_depth
            all_verts.append((x, y, z))

    # Brow quad faces
    brow_cols = ring_seg // 2 + 2
    for row in range(brow_rows - 1):
        for col in range(brow_cols - 1):
            v0 = brow_base + row * brow_cols + col
            v1 = v0 + 1
            v2 = v0 + brow_cols + 1
            v3 = v0 + brow_cols
            all_faces.append((v0, v1, v2, v3))

    # Count face types
    quad_count = sum(1 for f in all_faces if len(f) == 4)
    tri_count = sum(1 for f in all_faces if len(f) == 3)

    return _make_result(
        name=f"FaceMesh_{detail_level}",
        vertices=all_verts,
        faces=all_faces,
        category="character_face",
        detail_level=detail_level,
        eye_loop_count=eye_loops,
        mouth_loop_count=mouth_loops,
        has_ears=has_ears,
        quad_count=quad_count,
        tri_count=tri_count,
        eye_data=eye_loop_data,
        mouth_vertex_count=mouth_vert_count,
        ear_vertex_count=ear_vert_count,
        nose_detail=nose_detail,
    )


# ---------------------------------------------------------------------------
# Task #53 continued: Blend shape targets
# ---------------------------------------------------------------------------

# The 30 FACS-based blend shape definitions
# Each maps a shape name to (affected_region, axis, magnitude, falloff_fn)
_BLEND_SHAPE_DEFS: dict[str, dict[str, Any]] = {
    # Jaw
    "jaw_open": {"region": "chin", "axis": (0, -0.015, -0.01), "z_range": (-0.5, -0.1)},
    "jaw_left": {"region": "chin", "axis": (-0.008, 0, 0), "z_range": (-0.5, -0.1)},
    "jaw_right": {"region": "chin", "axis": (0.008, 0, 0), "z_range": (-0.5, -0.1)},
    # Mouth
    "mouth_smile_L": {"region": "mouth_left", "axis": (-0.005, 0.002, 0.005), "z_range": (-0.3, 0.0)},
    "mouth_smile_R": {"region": "mouth_right", "axis": (0.005, 0.002, 0.005), "z_range": (-0.3, 0.0)},
    "mouth_frown_L": {"region": "mouth_left", "axis": (-0.003, 0, -0.005), "z_range": (-0.3, 0.0)},
    "mouth_frown_R": {"region": "mouth_right", "axis": (0.003, 0, -0.005), "z_range": (-0.3, 0.0)},
    "mouth_pucker": {"region": "mouth_center", "axis": (0, 0.008, 0), "z_range": (-0.25, -0.05)},
    "lips_together": {"region": "mouth_center", "axis": (0, 0, -0.003), "z_range": (-0.2, -0.1)},
    # Brow
    "brow_raise_L": {"region": "brow_left", "axis": (0, 0, 0.006), "z_range": (0.3, 0.5)},
    "brow_raise_R": {"region": "brow_right", "axis": (0, 0, 0.006), "z_range": (0.3, 0.5)},
    "brow_lower_L": {"region": "brow_left", "axis": (0, 0, -0.004), "z_range": (0.3, 0.5)},
    "brow_lower_R": {"region": "brow_right", "axis": (0, 0, -0.004), "z_range": (0.3, 0.5)},
    # Eyes
    "eye_blink_L": {"region": "eye_left", "axis": (0, 0, -0.004), "z_range": (0.1, 0.3)},
    "eye_blink_R": {"region": "eye_right", "axis": (0, 0, -0.004), "z_range": (0.1, 0.3)},
    "eye_wide_L": {"region": "eye_left", "axis": (0, 0, 0.003), "z_range": (0.1, 0.3)},
    "eye_wide_R": {"region": "eye_right", "axis": (0, 0, 0.003), "z_range": (0.1, 0.3)},
    "eye_squint_L": {"region": "eye_left", "axis": (0, -0.002, -0.002), "z_range": (0.1, 0.3)},
    "eye_squint_R": {"region": "eye_right", "axis": (0, -0.002, -0.002), "z_range": (0.1, 0.3)},
    # Cheeks
    "cheek_puff_L": {"region": "cheek_left", "axis": (-0.006, 0.004, 0), "z_range": (-0.1, 0.2)},
    "cheek_puff_R": {"region": "cheek_right", "axis": (0.006, 0.004, 0), "z_range": (-0.1, 0.2)},
    # Nose
    "nose_sneer_L": {"region": "nose_left", "axis": (-0.002, 0.002, 0.002), "z_range": (0.0, 0.15)},
    "nose_sneer_R": {"region": "nose_right", "axis": (0.002, 0.002, 0.002), "z_range": (0.0, 0.15)},
    # Tongue
    "tongue_out": {"region": "mouth_center", "axis": (0, 0.012, -0.005), "z_range": (-0.25, -0.1)},
    # Extra expressions
    "jaw_clench": {"region": "chin", "axis": (0, 0.002, 0.003), "z_range": (-0.4, -0.15)},
    "lip_stretch_L": {"region": "mouth_left", "axis": (-0.006, 0, 0), "z_range": (-0.25, -0.05)},
    "lip_stretch_R": {"region": "mouth_right", "axis": (0.006, 0, 0), "z_range": (-0.25, -0.05)},
    "dimple_L": {"region": "cheek_left", "axis": (0, -0.003, 0), "z_range": (-0.15, 0.05)},
    "dimple_R": {"region": "cheek_right", "axis": (0, -0.003, 0), "z_range": (-0.15, 0.05)},
    "chin_raise": {"region": "chin_tip", "axis": (0, 0.004, 0.002), "z_range": (-0.5, -0.3)},
}

# Region definitions: map region name to (x_range, z_range) as fractions of face dimensions
_REGION_BOUNDS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "chin": ((-0.5, 0.5), (-1.0, -0.3)),
    "chin_tip": ((-0.3, 0.3), (-1.0, -0.5)),
    "mouth_left": ((-0.6, -0.05), (-0.4, 0.05)),
    "mouth_right": ((0.05, 0.6), (-0.4, 0.05)),
    "mouth_center": ((-0.3, 0.3), (-0.35, 0.0)),
    "brow_left": ((-0.7, -0.05), (0.5, 1.0)),
    "brow_right": ((0.05, 0.7), (0.5, 1.0)),
    "eye_left": ((-0.7, -0.1), (0.15, 0.5)),
    "eye_right": ((0.1, 0.7), (0.15, 0.5)),
    "cheek_left": ((-0.8, -0.2), (-0.15, 0.3)),
    "cheek_right": ((0.2, 0.8), (-0.15, 0.3)),
    "nose_left": ((-0.3, -0.02), (-0.05, 0.25)),
    "nose_right": ((0.02, 0.3), (-0.05, 0.25)),
}


def generate_blend_shape_targets(
    base_vertices: list[Vec3],
    base_faces: list[tuple[int, ...]],
) -> dict[str, list[Vec3]]:
    """Generate 30 basic blend shape targets from base face mesh.

    Each blend shape is a list of displaced vertex positions (same length as
    base_vertices). Only vertices in the affected region are displaced;
    others remain at their base position.

    Args:
        base_vertices: Original face mesh vertex positions.
        base_faces: Face index lists (used to compute bounds).

    Returns:
        Dict mapping shape_name -> list of displaced vertex positions.
        30 shapes covering FACS-standard expressions.
    """
    if not base_vertices:
        return {}

    # Compute face bounding box for normalization
    xs = [v[0] for v in base_vertices]
    ys = [v[1] for v in base_vertices]
    zs = [v[2] for v in base_vertices]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    width = max_x - min_x
    height = max_z - min_z
    cx = (min_x + max_x) / 2.0
    cz = (min_z + max_z) / 2.0

    if width < 1e-8:
        width = 1.0
    if height < 1e-8:
        height = 1.0

    shapes: dict[str, list[Vec3]] = {}

    for shape_name, shape_def in _BLEND_SHAPE_DEFS.items():
        region = shape_def["region"]
        axis = shape_def["axis"]
        ax, ay, az = axis

        region_bounds = _REGION_BOUNDS.get(region)
        if region_bounds is None:
            shapes[shape_name] = list(base_vertices)
            continue

        (x_lo_frac, x_hi_frac), (z_lo_frac, z_hi_frac) = region_bounds

        displaced: list[Vec3] = []
        for vx, vy, vz in base_vertices:
            # Normalize to [-1, 1] range
            nx = (vx - cx) / (width / 2.0) if width > 1e-8 else 0.0
            nz = (vz - cz) / (height / 2.0) if height > 1e-8 else 0.0

            # Check if vertex is in the affected region
            if x_lo_frac <= nx <= x_hi_frac and z_lo_frac <= nz <= z_hi_frac:
                # Compute falloff based on distance from region center
                rx_center = (x_lo_frac + x_hi_frac) / 2.0
                rz_center = (z_lo_frac + z_hi_frac) / 2.0
                rx_extent = max((x_hi_frac - x_lo_frac) / 2.0, 0.01)
                rz_extent = max((z_hi_frac - z_lo_frac) / 2.0, 0.01)

                dx = (nx - rx_center) / rx_extent
                dz = (nz - rz_center) / rz_extent
                dist = math.sqrt(dx * dx + dz * dz)
                falloff = max(0.0, 1.0 - dist)  # linear falloff

                displaced.append((
                    vx + ax * falloff,
                    vy + ay * falloff,
                    vz + az * falloff,
                ))
            else:
                displaced.append((vx, vy, vz))

        shapes[shape_name] = displaced

    return shapes


# ---------------------------------------------------------------------------
# Task #54: Hand mesh generation
# ---------------------------------------------------------------------------

# Finger specs: (name, length_fracs, thickness_frac, x_offset, z_offset, is_thumb)
# x_offset: lateral position fraction of palm_width (negative=thumb side)
# Proportions: middle longest, ring slightly shorter, index similar, pinky shortest
_FINGER_SPECS: list[tuple[str, list[float], float, float, float, bool]] = [
    ("thumb", [0.20, 0.17, 0.15], 0.55, -0.35, -0.15, True),
    ("index", [0.22, 0.18, 0.15], 0.45, -0.15, 0.0, False),
    ("middle", [0.24, 0.20, 0.16], 0.48, 0.0, 0.03, False),
    ("ring", [0.22, 0.18, 0.15], 0.43, 0.15, 0.01, False),
    ("pinky", [0.18, 0.14, 0.12], 0.38, 0.28, -0.02, False),
]

# Maps finger_count to which _FINGER_SPECS entries to use.
# Always includes thumb first, then selects from the remaining 4.
_FINGER_COUNT_MAP: dict[int, list[int]] = {
    5: [0, 1, 2, 3, 4],          # all fingers
    4: [0, 1, 2, 4],             # no ring finger (alien)
    3: [0, 1, 4],                # thumb + index + pinky (monster)
    2: [0, 2],                   # thumb + middle (claw grip)
}


def _build_finger(
    all_verts: list[Vec3],
    all_faces: list[tuple[int, ...]],
    joint_positions: dict[str, Vec3],
    f_name: str,
    joint_lengths: list[float],
    thickness_frac: float,
    x_off: float,
    z_off: float,
    is_thumb: bool,
    palm_length: float,
    palm_width: float,
    palm_depth: float,
    mirror: float,
    segments: int,
    has_nails: bool,
    detail: str,
) -> dict[str, Any]:
    """Build a single finger with separated geometry, knuckle bumps, and nails.

    Each finger is geometrically independent -- no shared vertices with other
    fingers except at the webbing bridge quads at the base.

    Returns finger_data dict with joints, joint_count, is_thumb, has_nail.
    """
    finger_base_x = mirror * x_off * palm_width
    finger_base_y = palm_length
    finger_base_z = z_off * palm_depth

    finger_thickness = palm_depth * thickness_frac
    finger_width = finger_thickness * 0.9

    # Thumb starts from side of palm, rotated 90 degrees from other fingers
    if is_thumb:
        finger_base_y = palm_length * 0.3
        finger_base_x = mirror * (-palm_width * 0.45)
        finger_width = finger_thickness * 1.1  # Thumb is wider

    joint_pos_list: list[Vec3] = []
    joint_pos_list.append((finger_base_x, finger_base_y, finger_base_z))
    joint_positions[f"{f_name}_base"] = (finger_base_x, finger_base_y, finger_base_z)

    # Build finger as connected segments
    current_y = finger_base_y
    current_x = finger_base_x

    # Thumb opposition angle (rotated ~90 degrees from other fingers)
    thumb_angle = 0.5 if is_thumb else 0.0

    seg_per_joint = max(2, segments // 3)
    nail_generated = False

    for ji, joint_len_frac in enumerate(joint_lengths):
        joint_length = palm_length * joint_len_frac
        taper = 1.0 - ji * 0.15  # Fingers taper toward tip

        prev_y = current_y
        current_y += joint_length

        if is_thumb:
            current_x += mirror * joint_length * math.sin(thumb_angle) * 0.3

        joint_name = ["proximal", "intermediate", "distal"][ji]
        joint_pos = (current_x, current_y, finger_base_z)
        joint_pos_list.append(joint_pos)
        joint_positions[f"{f_name}_{joint_name}"] = joint_pos

        # Generate segment rings
        for si in range(seg_per_joint + 1):
            t = si / seg_per_joint
            seg_y = prev_y + t * joint_length
            seg_taper = taper * (1.0 - t * 0.1)
            seg_x = finger_base_x
            if is_thumb:
                seg_x += mirror * (seg_y - finger_base_y) * math.sin(thumb_angle) * 0.3

            ring_base = len(all_verts)
            half_w = finger_width * seg_taper * 0.5
            half_d = finger_thickness * seg_taper * 0.5

            # Rounded cross-section with finger separation gaps
            for ri in range(segments):
                angle = 2.0 * math.pi * ri / segments
                rx = seg_x + math.cos(angle) * half_w
                rz = finger_base_z + math.sin(angle) * half_d

                # Knuckle bump at joint transitions -- dorsal side only
                if t < 0.15 and ji > 0:
                    bump = 0.002 * (1.0 - t / 0.15)
                    rz += bump * max(0, math.sin(angle))

                all_verts.append((rx, seg_y, rz))

            # Connect to previous ring
            if si > 0 or ji > 0:
                prev_ring = ring_base - segments
                all_faces.extend(
                    _connect_rings_quad(prev_ring, ring_base, segments)
                )

        # Nail geometry on distal segment (medium and high detail, or when has_nails)
        is_distal = ji == len(joint_lengths) - 1
        should_nail = has_nails and is_distal and detail in ("medium", "high")
        if should_nail:
            tip_y = current_y
            tip_x = current_x if is_thumb else finger_base_x
            nail_base_idx = len(all_verts)
            nail_w = finger_width * taper * 0.4
            nail_l = joint_length * 0.5
            nail_d = finger_thickness * taper * 0.55
            nail_rise = 0.001  # Slight elevation above finger surface

            # Nail as extruded cap: 6-vertex curved nail plate
            # Bottom edge (proximal nail edge)
            all_verts.extend([
                (tip_x - nail_w, tip_y - nail_l, finger_base_z + nail_d),
                (tip_x, tip_y - nail_l, finger_base_z + nail_d + nail_rise * 0.5),
                (tip_x + nail_w, tip_y - nail_l, finger_base_z + nail_d),
            ])
            # Top edge (distal nail tip)
            all_verts.extend([
                (tip_x - nail_w * 0.85, tip_y, finger_base_z + nail_d + nail_rise),
                (tip_x, tip_y + 0.001, finger_base_z + nail_d + nail_rise * 1.5),
                (tip_x + nail_w * 0.85, tip_y, finger_base_z + nail_d + nail_rise),
            ])
            # Two quads forming the nail plate
            nb = nail_base_idx
            all_faces.append((nb, nb + 1, nb + 4, nb + 3))
            all_faces.append((nb + 1, nb + 2, nb + 5, nb + 4))
            nail_generated = True

    # Webbing: thin quad bridge at finger base connecting to palm
    # This creates the inter-finger webbing membrane without fusing fingers
    if not is_thumb:
        web_y = finger_base_y
        web_z = finger_base_z - finger_thickness * 0.3
        web_base = len(all_verts)
        # Two triangles forming a thin membrane from finger base downward
        web_half = finger_width * 0.3
        all_verts.extend([
            (finger_base_x - web_half, web_y, finger_base_z),
            (finger_base_x + web_half, web_y, finger_base_z),
            (finger_base_x + web_half, web_y - palm_length * 0.05, web_z),
            (finger_base_x - web_half, web_y - palm_length * 0.05, web_z),
        ])
        all_faces.append((web_base, web_base + 1, web_base + 2, web_base + 3))

    return {
        "joints": joint_pos_list,
        "joint_count": len(joint_lengths),
        "is_thumb": is_thumb,
        "has_nail": nail_generated,
    }


def generate_hand_mesh(
    detail: str = "medium",
    side: str = "right",
    finger_count: int = 5,
    has_nails: bool = True,
) -> MeshSpec:
    """Generate an anatomical hand mesh with accurate finger geometry.

    Features:
    - Configurable finger count (2-5) for humans and monsters
    - 3 joints per finger (proximal, intermediate, distal phalanges)
    - Thumb with proper opposition (rotated 90 deg, shorter, wider)
    - Fingernails as extruded cap geometry on distal phalanges (medium/high)
    - Knuckle bumps (vertex displacement at each joint)
    - Palm curvature (concave inner, convex outer)
    - Webbing between fingers (thin quad bridge at base)
    - Correct proportions: middle longest, ring slightly shorter,
      index similar to ring, pinky shortest, thumb widest

    Args:
        detail: "low", "medium", or "high".
        side: "left" or "right".
        finger_count: Number of fingers (2-5). 5=human, 3=monster, etc.
        has_nails: Whether to generate nail geometry on fingertips.

    Returns:
        MeshSpec with hand geometry, joint positions, and metadata.
    """
    if detail not in ("low", "medium", "high"):
        detail = "medium"
    finger_count = max(2, min(5, finger_count))

    segments = {"low": 4, "medium": 6, "high": 8}[detail]
    mirror = -1.0 if side == "left" else 1.0

    # Hand dimensions (meters)
    palm_length = 0.085
    palm_width = 0.08
    palm_depth = 0.025
    wrist_width = 0.055
    wrist_depth = 0.030

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    joint_positions: dict[str, Vec3] = {}

    # ----- Palm mesh -----
    # Palm as a subdivided quad surface with curvature
    palm_rows = 4
    palm_cols = segments
    palm_base = len(all_verts)

    for row in range(palm_rows + 1):
        t_row = row / palm_rows
        # Taper from wrist to knuckles
        current_width = wrist_width + (palm_width - wrist_width) * t_row
        current_depth = wrist_depth + (palm_depth - wrist_depth) * t_row
        y = t_row * palm_length

        for col in range(palm_cols + 1):
            t_col = col / palm_cols
            x = mirror * (-current_width / 2 + t_col * current_width)

            # Palm curvature: slight concavity on inside (palmar surface)
            curvature = -0.005 * math.sin(t_col * math.pi)
            # Thickness variation -- convex dorsal surface
            z = curvature + current_depth * 0.5 * (1.0 - abs(t_col - 0.5) * 0.5)

            all_verts.append((x, y, z))

    # Bottom of palm (palmar surface - slightly concave)
    palm_bottom_base = len(all_verts)
    for row in range(palm_rows + 1):
        t_row = row / palm_rows
        current_width = wrist_width + (palm_width - wrist_width) * t_row
        y = t_row * palm_length
        for col in range(palm_cols + 1):
            t_col = col / palm_cols
            x = mirror * (-current_width / 2 + t_col * current_width)
            z = -palm_depth * 0.4
            all_verts.append((x, y, z))

    palm_grid_cols = palm_cols + 1

    # Top face quads
    for row in range(palm_rows):
        for col in range(palm_cols):
            v0 = palm_base + row * palm_grid_cols + col
            v1 = v0 + 1
            v2 = v0 + palm_grid_cols + 1
            v3 = v0 + palm_grid_cols
            all_faces.append((v0, v1, v2, v3))

    # Bottom face quads (reverse winding)
    for row in range(palm_rows):
        for col in range(palm_cols):
            v0 = palm_bottom_base + row * palm_grid_cols + col
            v1 = v0 + 1
            v2 = v0 + palm_grid_cols + 1
            v3 = v0 + palm_grid_cols
            all_faces.append((v0, v3, v2, v1))

    # Side faces connecting top and bottom
    for row in range(palm_rows):
        # Left edge
        t0 = palm_base + row * palm_grid_cols
        t1 = palm_base + (row + 1) * palm_grid_cols
        b0 = palm_bottom_base + row * palm_grid_cols
        b1 = palm_bottom_base + (row + 1) * palm_grid_cols
        all_faces.append((t0, b0, b1, t1))

        # Right edge
        t0r = palm_base + row * palm_grid_cols + palm_cols
        t1r = palm_base + (row + 1) * palm_grid_cols + palm_cols
        b0r = palm_bottom_base + row * palm_grid_cols + palm_cols
        b1r = palm_bottom_base + (row + 1) * palm_grid_cols + palm_cols
        all_faces.append((t0r, t1r, b1r, b0r))

    # Wrist edge (close bottom)
    for col in range(palm_cols):
        t0 = palm_base + col
        t1 = palm_base + col + 1
        b0 = palm_bottom_base + col
        b1 = palm_bottom_base + col + 1
        all_faces.append((t0, t1, b1, b0))

    joint_positions["wrist"] = (0.0, 0.0, 0.0)

    # ----- Fingers -----
    # Select which fingers to generate based on finger_count
    spec_indices = _FINGER_COUNT_MAP.get(finger_count, list(range(finger_count)))
    active_specs = [_FINGER_SPECS[i] for i in spec_indices if i < len(_FINGER_SPECS)]

    finger_data: dict[str, dict[str, Any]] = {}

    for f_name, joint_lengths, thickness_frac, x_off, z_off, is_thumb in active_specs:
        fdata = _build_finger(
            all_verts=all_verts,
            all_faces=all_faces,
            joint_positions=joint_positions,
            f_name=f_name,
            joint_lengths=joint_lengths,
            thickness_frac=thickness_frac,
            x_off=x_off,
            z_off=z_off,
            is_thumb=is_thumb,
            palm_length=palm_length,
            palm_width=palm_width,
            palm_depth=palm_depth,
            mirror=mirror,
            segments=segments,
            has_nails=has_nails,
            detail=detail,
        )
        finger_data[f_name] = fdata

    return _make_result(
        name=f"Hand_{side}_{detail}",
        vertices=all_verts,
        faces=all_faces,
        category="character_hand",
        detail=detail,
        side=side,
        finger_count=len(active_specs),
        has_nails=has_nails,
        joint_positions=joint_positions,
        finger_data=finger_data,
    )


# ---------------------------------------------------------------------------
# Task #54: Foot mesh generation
# ---------------------------------------------------------------------------


def generate_foot_mesh(
    detail: str = "medium",
    side: str = "right",
    toe_count: int = 5,
    has_nails: bool = True,
) -> MeshSpec:
    """Generate an anatomical foot mesh with accurate toe geometry.

    Features:
    - Configurable toe count (1-5) with clear separation
    - Big toe larger and separated from others
    - Toenails on each toe (subtle extruded cap, medium/high detail)
    - Arch curvature (concave bottom)
    - Ankle bones (medial malleolus inner, lateral outer)
    - Heel definition (rounded back) with Achilles tendon ridge

    Args:
        detail: "low", "medium", or "high".
        side: "left" or "right".
        toe_count: Number of toes (1-5). 5=human default.
        has_nails: Whether to generate toenail geometry.

    Returns:
        MeshSpec with foot geometry, joint positions, and metadata.
    """
    if detail not in ("low", "medium", "high"):
        detail = "medium"
    toe_count = max(1, min(5, toe_count))

    segments = {"low": 4, "medium": 6, "high": 8}[detail]
    mirror = -1.0 if side == "left" else 1.0

    # Foot dimensions (meters)
    foot_length = 0.26
    foot_width = 0.09
    foot_height = 0.07  # ankle to ground
    arch_height = 0.025
    heel_width = 0.06
    toe_length = 0.04

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    joint_positions: dict[str, Vec3] = {}

    # ----- Main foot body -----
    # Build foot as a multi-section surface
    foot_sections = 6
    foot_cols = segments + 2

    foot_base = len(all_verts)

    for sec in range(foot_sections + 1):
        t = sec / foot_sections
        y = t * (foot_length - toe_length)  # Y along foot length

        # Width varies: heel (narrow) -> midfoot -> ball (widest)
        if t < 0.3:
            # Heel region
            w = heel_width + (foot_width - heel_width) * (t / 0.3) * 0.7
        elif t < 0.7:
            # Midfoot
            w = foot_width * (0.7 + 0.3 * ((t - 0.3) / 0.4))
        else:
            # Ball of foot
            w = foot_width

        # Arch height profile
        if t < 0.2:
            z_floor = 0.0  # flat heel
        elif t < 0.6:
            # Arch
            arch_t = (t - 0.2) / 0.4
            z_floor = arch_height * math.sin(arch_t * math.pi)
        else:
            z_floor = 0.0  # flat forefoot

        for col in range(foot_cols + 1):
            t_col = col / foot_cols
            x = mirror * (-w / 2 + t_col * w)

            # Top surface with gentle dome
            z_top = foot_height - abs(t_col - 0.5) * foot_height * 0.3
            # Reduce height toward toes
            z_top *= (1.0 - t * 0.35)

            all_verts.append((x, y, z_top))

    # Bottom surface
    foot_bottom_base = len(all_verts)
    for sec in range(foot_sections + 1):
        t = sec / foot_sections
        y = t * (foot_length - toe_length)

        if t < 0.3:
            w = heel_width + (foot_width - heel_width) * (t / 0.3) * 0.7
        elif t < 0.7:
            w = foot_width * (0.7 + 0.3 * ((t - 0.3) / 0.4))
        else:
            w = foot_width

        if t < 0.2:
            z_floor = 0.0
        elif t < 0.6:
            arch_t = (t - 0.2) / 0.4
            z_floor = arch_height * math.sin(arch_t * math.pi)
        else:
            z_floor = 0.0

        for col in range(foot_cols + 1):
            t_col = col / foot_cols
            x = mirror * (-w / 2 + t_col * w)
            all_verts.append((x, y, z_floor))

    grid_cols = foot_cols + 1

    # Top face quads
    for sec in range(foot_sections):
        for col in range(foot_cols):
            v0 = foot_base + sec * grid_cols + col
            v1 = v0 + 1
            v2 = v0 + grid_cols + 1
            v3 = v0 + grid_cols
            all_faces.append((v0, v1, v2, v3))

    # Bottom face quads (reverse winding)
    for sec in range(foot_sections):
        for col in range(foot_cols):
            v0 = foot_bottom_base + sec * grid_cols + col
            v1 = v0 + 1
            v2 = v0 + grid_cols + 1
            v3 = v0 + grid_cols
            all_faces.append((v0, v3, v2, v1))

    # Side faces
    for sec in range(foot_sections):
        # Left edge
        t0 = foot_base + sec * grid_cols
        t1 = foot_base + (sec + 1) * grid_cols
        b0 = foot_bottom_base + sec * grid_cols
        b1 = foot_bottom_base + (sec + 1) * grid_cols
        all_faces.append((t0, b0, b1, t1))

        # Right edge
        t0r = foot_base + sec * grid_cols + foot_cols
        t1r = foot_base + (sec + 1) * grid_cols + foot_cols
        b0r = foot_bottom_base + sec * grid_cols + foot_cols
        b1r = foot_bottom_base + (sec + 1) * grid_cols + foot_cols
        all_faces.append((t0r, t1r, b1r, b0r))

    # Heel back face
    for col in range(foot_cols):
        t0 = foot_base + col
        t1 = foot_base + col + 1
        b0 = foot_bottom_base + col
        b1 = foot_bottom_base + col + 1
        all_faces.append((t0, t1, b1, b0))

    joint_positions["ankle"] = (0.0, 0.0, foot_height)
    joint_positions["heel"] = (0.0, 0.0, 0.0)
    joint_positions["ball"] = (0.0, foot_length - toe_length, 0.0)

    # ----- Ankle bone bumps (malleolus) -----
    # Medial malleolus (inside ankle - higher)
    mal_med_x = mirror * (-foot_width * 0.45)
    mal_med_y = 0.02
    mal_med_z = foot_height * 0.7
    bump_segs = max(3, segments // 2)
    bump_radius = 0.008

    med_base = len(all_verts)
    for i in range(bump_segs):
        angle = 2.0 * math.pi * i / bump_segs
        bx = mal_med_x + math.cos(angle) * bump_radius * 0.7
        by = mal_med_y + math.sin(angle) * bump_radius * 0.5
        bz = mal_med_z + math.sin(angle) * bump_radius
        all_verts.append((bx, by, bz))
    # Close bump as n-gon
    all_faces.append(tuple(range(med_base, med_base + bump_segs)))

    joint_positions["malleolus_medial"] = (mal_med_x, mal_med_y, mal_med_z)

    # Lateral malleolus (outside ankle - lower)
    mal_lat_x = mirror * (foot_width * 0.45)
    mal_lat_y = 0.025
    mal_lat_z = foot_height * 0.55

    lat_base = len(all_verts)
    for i in range(bump_segs):
        angle = 2.0 * math.pi * i / bump_segs
        bx = mal_lat_x + math.cos(angle) * bump_radius * 0.7
        by = mal_lat_y + math.sin(angle) * bump_radius * 0.5
        bz = mal_lat_z + math.sin(angle) * bump_radius
        all_verts.append((bx, by, bz))
    all_faces.append(tuple(range(lat_base, lat_base + bump_segs)))

    joint_positions["malleolus_lateral"] = (mal_lat_x, mal_lat_y, mal_lat_z)

    # ----- Achilles tendon ridge -----
    achilles_base = len(all_verts)
    achilles_x = 0.0
    achilles_height_steps = 3
    achilles_width = 0.01

    for i in range(achilles_height_steps + 1):
        t = i / achilles_height_steps
        az = foot_height * 0.3 + t * foot_height * 0.7
        ay = -0.005 - t * 0.005  # slightly behind heel
        # Ridge protrusion
        protrusion = 0.004 * math.sin(t * math.pi)
        all_verts.append((achilles_x - achilles_width, ay - protrusion, az))
        all_verts.append((achilles_x + achilles_width, ay - protrusion, az))

    for i in range(achilles_height_steps):
        v0 = achilles_base + i * 2
        v1 = v0 + 1
        v2 = v0 + 3
        v3 = v0 + 2
        all_faces.append((v0, v1, v2, v3))

    joint_positions["achilles"] = (0.0, -0.005, foot_height * 0.6)

    # ----- Toes -----
    # Full spec: (name, width, x_offset_frac, length_extra)
    _all_toe_specs: list[tuple[str, float, float, float]] = [
        ("big_toe", 0.020, 0.0, 0.0),
        ("second_toe", 0.012, 0.22, -0.005),
        ("third_toe", 0.011, 0.40, -0.008),
        ("fourth_toe", 0.010, 0.55, -0.012),
        ("fifth_toe", 0.009, 0.68, -0.016),
    ]

    # Select toes based on toe_count; always include big toe
    individual_toes = detail in ("medium", "high")

    if toe_count == 1:
        toe_specs = [_all_toe_specs[0]]
    elif not individual_toes and toe_count >= 2:
        # Low detail: big toe + grouped smaller toes
        toe_specs = [
            _all_toe_specs[0],
            ("small_toes", 0.035, 0.45, -0.010),
        ]
    else:
        # Medium/high detail: individual toes up to toe_count
        toe_specs = list(_all_toe_specs[:toe_count])

    toe_base_y = foot_length - toe_length

    # Bug 3 fix: record the foot's front edge vertex indices for connecting toes
    foot_front_top = foot_base + foot_sections * grid_cols
    foot_front_bottom = foot_bottom_base + foot_sections * grid_cols

    nails_generated = 0

    for t_name, t_width, t_x_frac, t_len_extra in toe_specs:
        toe_cx = mirror * (-foot_width * 0.35 + t_x_frac * foot_width * 0.7)
        toe_base_z = 0.008
        actual_toe_len = toe_length + t_len_extra
        toe_segs = max(2, segments // 2)

        toe_start = len(all_verts)

        n_ring = 4  # cross section points per ring
        for si in range(toe_segs + 1):
            t = si / toe_segs
            ty = toe_base_y + t * actual_toe_len
            # Taper toward tip
            tw = t_width * (1.0 - t * 0.4)
            th = 0.008 * (1.0 - t * 0.3)

            # 4-point cross section (simplified)
            for ri in range(n_ring):
                angle = 2.0 * math.pi * ri / n_ring
                tx = toe_cx + math.cos(angle) * tw * 0.5
                tz = toe_base_z + math.sin(angle) * th
                all_verts.append((tx, ty, max(0.0, tz)))

            if si > 0:
                prev = toe_start + (si - 1) * n_ring
                curr = toe_start + si * n_ring
                all_faces.extend(_connect_rings_quad(prev, curr, n_ring))

        # Toenail geometry (medium/high detail)
        if has_nails and detail in ("medium", "high") and t_name != "small_toes":
            tip_y = toe_base_y + actual_toe_len
            nail_w = tw * 0.4  # Use final tapered width
            nail_l = actual_toe_len * 0.35
            nail_z = toe_base_z + th * 0.55
            nail_rise = 0.0008

            nail_base_idx = len(all_verts)
            # Nail as extruded cap on dorsal tip
            all_verts.extend([
                (toe_cx - nail_w, tip_y - nail_l, nail_z),
                (toe_cx + nail_w, tip_y - nail_l, nail_z),
                (toe_cx + nail_w * 0.85, tip_y, nail_z + nail_rise),
                (toe_cx - nail_w * 0.85, tip_y, nail_z + nail_rise),
            ])
            all_faces.append((nail_base_idx, nail_base_idx + 1,
                              nail_base_idx + 2, nail_base_idx + 3))
            nails_generated += 1

        # Bug 3 fix: connect toe base ring to foot body with bridge faces.
        best_col = 0
        best_dist = float('inf')
        for col in range(grid_cols):
            foot_vi = foot_front_top + col
            if foot_vi < len(all_verts):
                fv = all_verts[foot_vi]
                d = (fv[0] - toe_cx) ** 2
                if d < best_dist:
                    best_dist = d
                    best_col = col

        # Create bridge triangles from toe base ring to foot front edge
        foot_top_v = foot_front_top + best_col
        foot_top_v2 = foot_front_top + min(best_col + 1, grid_cols - 1)
        if foot_top_v < len(all_verts) and foot_top_v2 < len(all_verts):
            all_faces.append((toe_start, toe_start + 1, foot_top_v2, foot_top_v))
            all_faces.append((toe_start + 2, toe_start + 3, foot_top_v))

        joint_positions[f"{t_name}_base"] = (toe_cx, toe_base_y, toe_base_z)
        joint_positions[f"{t_name}_tip"] = (toe_cx, toe_base_y + actual_toe_len, toe_base_z)

    actual_toe_count = len(toe_specs)

    return _make_result(
        name=f"Foot_{side}_{detail}",
        vertices=all_verts,
        faces=all_faces,
        category="character_foot",
        detail=detail,
        side=side,
        toe_count=actual_toe_count,
        has_nails=has_nails,
        nails_generated=nails_generated,
        individual_toes=individual_toes,
        has_arch=True,
        has_ankle_bumps=True,
        has_achilles=True,
        joint_positions=joint_positions,
    )


# ---------------------------------------------------------------------------
# Monster extremity variants
# ---------------------------------------------------------------------------


def generate_claw_hand_mesh(
    claw_count: int = 3,
    style: str = "sharp",
    side: str = "right",
    detail: str = "medium",
) -> MeshSpec:
    """Generate a monster claw hand with sharp talons instead of fingernails.

    Produces a hand with thick, curved claws on each digit. The palm is
    wider and the digits are spaced further apart than a human hand.

    Args:
        claw_count: Number of claws (2-5). Default 3 for monsters.
        style: "sharp" (pointed talons), "hooked" (curved tips),
               "blunt" (thick rounded).
        side: "left" or "right".
        detail: "low", "medium", or "high".

    Returns:
        MeshSpec with claw hand geometry.
    """
    if detail not in ("low", "medium", "high"):
        detail = "medium"
    claw_count = max(2, min(5, claw_count))
    if style not in ("sharp", "hooked", "blunt"):
        style = "sharp"

    segments = {"low": 4, "medium": 6, "high": 8}[detail]
    mirror = -1.0 if side == "left" else 1.0

    # Claw hand is wider and thicker than human
    palm_length = 0.10
    palm_width = 0.10
    palm_depth = 0.035
    wrist_width = 0.07
    wrist_depth = 0.04

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    joint_positions: dict[str, Vec3] = {}
    claw_data: dict[str, dict[str, Any]] = {}

    # ----- Palm (broader, thicker) -----
    palm_rows = 3
    palm_cols = max(3, segments // 2)
    palm_base = len(all_verts)

    for row in range(palm_rows + 1):
        t_row = row / palm_rows
        cw = wrist_width + (palm_width - wrist_width) * t_row
        y = t_row * palm_length

        for col in range(palm_cols + 1):
            t_col = col / palm_cols
            x = mirror * (-cw / 2 + t_col * cw)
            z = palm_depth * 0.5 * (1.0 - abs(t_col - 0.5) * 0.3)
            all_verts.append((x, y, z))

    # Bottom
    palm_bottom_base = len(all_verts)
    for row in range(palm_rows + 1):
        t_row = row / palm_rows
        cw = wrist_width + (palm_width - wrist_width) * t_row
        y = t_row * palm_length
        for col in range(palm_cols + 1):
            t_col = col / palm_cols
            x = mirror * (-cw / 2 + t_col * cw)
            all_verts.append((x, y, -palm_depth * 0.4))

    grid = palm_cols + 1

    # Top + bottom quads
    for row in range(palm_rows):
        for col in range(palm_cols):
            v0 = palm_base + row * grid + col
            all_faces.append((v0, v0 + 1, v0 + grid + 1, v0 + grid))
            v0b = palm_bottom_base + row * grid + col
            all_faces.append((v0b, v0b + grid, v0b + grid + 1, v0b + 1))

    # Sides
    for row in range(palm_rows):
        tl = palm_base + row * grid
        tl2 = tl + grid
        bl = palm_bottom_base + row * grid
        bl2 = bl + grid
        all_faces.append((tl, bl, bl2, tl2))
        tr = palm_base + row * grid + palm_cols
        tr2 = tr + grid
        br = palm_bottom_base + row * grid + palm_cols
        br2 = br + grid
        all_faces.append((tr, tr2, br2, br))

    joint_positions["wrist"] = (0.0, 0.0, 0.0)

    # ----- Claws -----
    # Distribute claws evenly across palm width
    for ci in range(claw_count):
        if claw_count == 1:
            x_frac = 0.0
        else:
            x_frac = -0.4 + 0.8 * ci / (claw_count - 1)

        claw_name = f"claw_{ci}"
        claw_x = mirror * x_frac * palm_width
        claw_y = palm_length
        claw_z = 0.0

        joint_positions[f"{claw_name}_base"] = (claw_x, claw_y, claw_z)

        # Each claw: 2 phalanx segments + talon
        phalanx_lengths = [palm_length * 0.25, palm_length * 0.20]
        talon_length = palm_length * 0.30
        claw_thickness = palm_depth * 0.5
        claw_width_base = palm_depth * 0.45

        cur_y = claw_y
        cur_x = claw_x
        claw_joints: list[Vec3] = [(claw_x, claw_y, claw_z)]
        seg_per_phalanx = max(2, segments // 3)

        for pi, plen in enumerate(phalanx_lengths):
            prev_y = cur_y
            cur_y += plen
            jname = f"{claw_name}_phalanx_{pi}"
            joint_positions[jname] = (cur_x, cur_y, claw_z)
            claw_joints.append((cur_x, cur_y, claw_z))

            for si in range(seg_per_phalanx + 1):
                t = si / seg_per_phalanx
                sy = prev_y + t * plen
                tp = 1.0 - pi * 0.15 - t * 0.05
                rb = len(all_verts)
                hw = claw_width_base * tp * 0.5
                hd = claw_thickness * tp * 0.5

                for ri in range(segments):
                    angle = 2.0 * math.pi * ri / segments
                    all_verts.append((
                        cur_x + math.cos(angle) * hw,
                        sy,
                        claw_z + math.sin(angle) * hd,
                    ))
                if si > 0 or pi > 0:
                    all_faces.extend(_connect_rings_quad(rb - segments, rb, segments))

        # Talon: sharp curved extension
        tip_y = cur_y + talon_length
        talon_segs = max(2, segments // 2)

        # Style affects curvature
        curve_factor = {"sharp": 0.3, "hooked": 0.6, "blunt": 0.1}[style]
        taper_end = {"sharp": 0.05, "hooked": 0.1, "blunt": 0.3}[style]

        for si in range(talon_segs + 1):
            t = si / talon_segs
            ty = cur_y + t * talon_length
            # Curve downward
            tz = claw_z - t * t * curve_factor * talon_length
            tp = 1.0 - t * (1.0 - taper_end)
            rb = len(all_verts)
            hw = claw_width_base * 0.7 * tp * 0.5
            hd = claw_thickness * 0.7 * tp * 0.5

            for ri in range(segments):
                angle = 2.0 * math.pi * ri / segments
                all_verts.append((
                    cur_x + math.cos(angle) * hw,
                    ty,
                    tz + math.sin(angle) * hd,
                ))
            prev_ring = rb - segments
            all_faces.extend(_connect_rings_quad(prev_ring, rb, segments))

        talon_tip = (cur_x, tip_y, claw_z - curve_factor * talon_length)
        joint_positions[f"{claw_name}_talon_tip"] = talon_tip
        claw_joints.append(talon_tip)

        claw_data[claw_name] = {
            "joints": claw_joints,
            "joint_count": len(phalanx_lengths),
            "style": style,
        }

    return _make_result(
        name=f"ClawHand_{side}_{detail}",
        vertices=all_verts,
        faces=all_faces,
        category="character_claw_hand",
        detail=detail,
        side=side,
        claw_count=claw_count,
        style=style,
        joint_positions=joint_positions,
        claw_data=claw_data,
    )


def generate_hoof_mesh(
    style: str = "horse",
    side: str = "right",
    detail: str = "medium",
) -> MeshSpec:
    """Generate a hooved foot for quadrupeds.

    Styles:
    - horse: Single solid hoof with wall and sole
    - cloven: Split hoof (two toes) like cattle/deer
    - padded: Flat padded hoof like elephants

    Args:
        style: "horse", "cloven", or "padded".
        side: "left" or "right".
        detail: "low", "medium", or "high".

    Returns:
        MeshSpec with hoof geometry.
    """
    if detail not in ("low", "medium", "high"):
        detail = "medium"
    if style not in ("horse", "cloven", "padded"):
        style = "horse"

    segments = {"low": 6, "medium": 10, "high": 16}[detail]
    mirror = -1.0 if side == "left" else 1.0

    # Hoof dimensions
    hoof_width = 0.06
    hoof_depth = 0.07  # front to back
    hoof_height = 0.04
    pastern_height = 0.06  # leg segment above hoof
    pastern_radius = 0.025

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    joint_positions: dict[str, Vec3] = {}

    # ----- Pastern (leg segment above hoof) -----
    pastern_rings = 3
    for ri in range(pastern_rings + 1):
        t = ri / pastern_rings
        z = hoof_height + t * pastern_height
        r = pastern_radius * (1.0 + t * 0.1)  # Slight flare upward
        ring_base = len(all_verts)

        for si in range(segments):
            angle = 2.0 * math.pi * si / segments
            x = mirror * math.cos(angle) * r
            y = math.sin(angle) * r
            all_verts.append((x, y, z))

        if ri > 0:
            prev = ring_base - segments
            all_faces.extend(_connect_rings_quad(prev, ring_base, segments))

    joint_positions["pastern_top"] = (0.0, 0.0, hoof_height + pastern_height)
    joint_positions["coronet"] = (0.0, 0.0, hoof_height)

    if style == "horse":
        # Single solid hoof: wider at bottom, with rounded front wall
        hoof_rings = 4
        for ri in range(hoof_rings + 1):
            t = ri / hoof_rings
            z = hoof_height * (1.0 - t)
            # Hoof flares outward toward bottom
            rx = (hoof_width * 0.5) * (0.8 + 0.4 * t)
            ry = (hoof_depth * 0.5) * (0.7 + 0.5 * t)
            ring_base = len(all_verts)

            for si in range(segments):
                angle = 2.0 * math.pi * si / segments
                x = mirror * math.cos(angle) * rx
                y = math.sin(angle) * ry
                all_verts.append((x, y, z))

            prev = ring_base - segments
            all_faces.extend(_connect_rings_quad(prev, ring_base, segments))

        # Sole (bottom cap)
        sole_center = len(all_verts)
        all_verts.append((0.0, 0.0, 0.0))
        last_ring = sole_center - segments
        for si in range(segments):
            si_next = (si + 1) % segments
            all_faces.append((sole_center, last_ring + si_next, last_ring + si))

        joint_positions["sole"] = (0.0, 0.0, 0.0)

    elif style == "cloven":
        # Split hoof: two toe sections with cleft between them
        for toe_side in (-1, 1):
            toe_offset = mirror * toe_side * hoof_width * 0.25
            toe_rings = 3
            toe_segs = max(4, segments // 2)

            for ri in range(toe_rings + 1):
                t = ri / toe_rings
                z = hoof_height * (1.0 - t)
                rx = hoof_width * 0.22 * (0.9 + 0.3 * t)
                ry = hoof_depth * 0.35 * (0.8 + 0.4 * t)
                ring_base = len(all_verts)

                for si in range(toe_segs):
                    angle = 2.0 * math.pi * si / toe_segs
                    x = toe_offset + math.cos(angle) * rx
                    y = math.sin(angle) * ry
                    all_verts.append((x, y, z))

                if ri > 0:
                    prev = ring_base - toe_segs
                    all_faces.extend(_connect_rings_quad(prev, ring_base, toe_segs))
                elif ri == 0:
                    # Connect to pastern -- bridge from pastern bottom ring
                    pastern_bottom = pastern_rings * segments
                    # Simple connection via triangles
                    for si in range(min(toe_segs, segments)):
                        pi_idx = pastern_bottom + (si * segments // toe_segs) % segments
                        pi_next = pastern_bottom + ((si + 1) * segments // toe_segs) % segments
                        ci_idx = ring_base + si
                        ci_next = ring_base + (si + 1) % toe_segs
                        if pi_idx < ring_base and pi_next < ring_base:
                            all_faces.append((pi_idx, ci_idx, ci_next, pi_next))

            toe_name = "inner_toe" if toe_side == -1 else "outer_toe"
            joint_positions[f"{toe_name}_tip"] = (toe_offset, 0.0, 0.0)

        joint_positions["cleft"] = (0.0, 0.0, hoof_height * 0.3)

    else:  # padded
        # Flat wide pad, like elephant
        pad_rings = 3
        for ri in range(pad_rings + 1):
            t = ri / pad_rings
            z = hoof_height * (1.0 - t)
            rx = hoof_width * 0.55 * (1.0 + 0.2 * t)
            ry = hoof_depth * 0.55 * (1.0 + 0.15 * t)
            ring_base = len(all_verts)

            for si in range(segments):
                angle = 2.0 * math.pi * si / segments
                x = mirror * math.cos(angle) * rx
                y = math.sin(angle) * ry
                all_verts.append((x, y, z))

            prev = ring_base - segments
            all_faces.extend(_connect_rings_quad(prev, ring_base, segments))

        # Flat bottom with pad texture bumps
        pad_center = len(all_verts)
        all_verts.append((0.0, 0.0, 0.002))
        last_ring = pad_center - segments
        for si in range(segments):
            si_next = (si + 1) % segments
            all_faces.append((pad_center, last_ring + si_next, last_ring + si))

        joint_positions["pad_center"] = (0.0, 0.0, 0.0)

    return _make_result(
        name=f"Hoof_{style}_{side}_{detail}",
        vertices=all_verts,
        faces=all_faces,
        category="character_hoof",
        detail=detail,
        side=side,
        style=style,
        joint_positions=joint_positions,
    )


def generate_paw_mesh(
    toe_count: int = 4,
    has_claws: bool = True,
    side: str = "right",
    detail: str = "medium",
) -> MeshSpec:
    """Generate an animal paw with toe beans and optional claws.

    Produces a digitigrade paw with soft toe pads (beans), a central
    palm pad, and optional retractable/visible claws.

    Args:
        toe_count: Number of toes (2-5). Default 4 for most animals.
        has_claws: Whether to add claw geometry.
        side: "left" or "right".
        detail: "low", "medium", or "high".

    Returns:
        MeshSpec with paw geometry.
    """
    if detail not in ("low", "medium", "high"):
        detail = "medium"
    toe_count = max(2, min(5, toe_count))

    segments = {"low": 4, "medium": 6, "high": 8}[detail]
    mirror = -1.0 if side == "left" else 1.0

    # Paw dimensions
    paw_width = 0.07
    paw_length = 0.08
    paw_height = 0.03
    pad_depth = 0.005  # How much pads protrude below

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    joint_positions: dict[str, Vec3] = {}
    toe_data: dict[str, dict[str, Any]] = {}

    # ----- Main paw body -----
    paw_sections = 4
    paw_cols = max(3, segments // 2)
    paw_base = len(all_verts)

    for sec in range(paw_sections + 1):
        t = sec / paw_sections
        y = t * paw_length
        w = paw_width * (0.7 + 0.3 * math.sin(t * math.pi))

        for col in range(paw_cols + 1):
            tc = col / paw_cols
            x = mirror * (-w / 2 + tc * w)
            z = paw_height * (1.0 - abs(tc - 0.5) * 0.4)
            z *= (1.0 - t * 0.2)
            all_verts.append((x, y, z))

    # Bottom (with central palm pad bulge)
    paw_bottom = len(all_verts)
    for sec in range(paw_sections + 1):
        t = sec / paw_sections
        y = t * paw_length
        w = paw_width * (0.7 + 0.3 * math.sin(t * math.pi))

        for col in range(paw_cols + 1):
            tc = col / paw_cols
            x = mirror * (-w / 2 + tc * w)
            # Central pad bulge
            pad_bulge = pad_depth * math.exp(
                -((tc - 0.5) ** 2 + (t - 0.4) ** 2) * 10.0
            )
            all_verts.append((x, y, -pad_bulge))

    grid = paw_cols + 1

    # Top/bottom quads
    for sec in range(paw_sections):
        for col in range(paw_cols):
            v0 = paw_base + sec * grid + col
            all_faces.append((v0, v0 + 1, v0 + grid + 1, v0 + grid))
            v0b = paw_bottom + sec * grid + col
            all_faces.append((v0b, v0b + grid, v0b + grid + 1, v0b + 1))

    # Side faces
    for sec in range(paw_sections):
        tl = paw_base + sec * grid
        bl = paw_bottom + sec * grid
        all_faces.append((tl, bl, bl + grid, tl + grid))
        tr = paw_base + sec * grid + paw_cols
        br = paw_bottom + sec * grid + paw_cols
        all_faces.append((tr, tr + grid, br + grid, br))

    joint_positions["paw_base"] = (0.0, 0.0, paw_height)
    joint_positions["palm_pad"] = (0.0, paw_length * 0.4, 0.0)

    # ----- Toes with beans and optional claws -----
    for ti in range(toe_count):
        if toe_count == 1:
            x_frac = 0.0
        else:
            x_frac = -0.35 + 0.7 * ti / (toe_count - 1)

        toe_name = f"toe_{ti}"
        toe_x = mirror * x_frac * paw_width
        toe_y = paw_length
        toe_z = paw_height * 0.3

        joint_positions[f"{toe_name}_base"] = (toe_x, toe_y, toe_z)

        # Toe digit
        toe_len = paw_length * 0.35
        toe_thick = paw_height * 0.4
        toe_w = paw_width * 0.12
        toe_segs = max(2, segments // 2)
        n_ring = segments

        toe_start = len(all_verts)
        for si in range(toe_segs + 1):
            t = si / toe_segs
            ty = toe_y + t * toe_len
            tp = 1.0 - t * 0.3
            rb = len(all_verts)
            hw = toe_w * tp * 0.5
            hd = toe_thick * tp * 0.5

            for ri in range(n_ring):
                angle = 2.0 * math.pi * ri / n_ring
                all_verts.append((
                    toe_x + math.cos(angle) * hw,
                    ty,
                    toe_z + math.sin(angle) * hd,
                ))

            if si > 0:
                all_faces.extend(_connect_rings_quad(rb - n_ring, rb, n_ring))

        # Toe bean (soft pad on underside of toe tip)
        bean_base = len(all_verts)
        bean_r = toe_w * 0.6
        bean_y_pos = toe_y + toe_len * 0.7
        bean_segs = max(3, segments // 2)

        for bi in range(bean_segs):
            angle = 2.0 * math.pi * bi / bean_segs
            bx = toe_x + math.cos(angle) * bean_r
            by = bean_y_pos + math.sin(angle) * bean_r * 0.5
            all_verts.append((bx, by, -pad_depth * 0.5))

        all_faces.append(tuple(range(bean_base, bean_base + bean_segs)))

        joint_positions[f"{toe_name}_bean"] = (toe_x, bean_y_pos, -pad_depth * 0.5)

        # Claw
        claw_generated = False
        if has_claws:
            claw_base_y = toe_y + toe_len
            claw_len = toe_len * 0.5
            claw_segs = max(2, segments // 3)
            claw_thick = toe_thick * 0.3
            claw_w = toe_w * 0.3

            for si in range(claw_segs + 1):
                t = si / claw_segs
                cy = claw_base_y + t * claw_len
                cz = toe_z - t * t * claw_len * 0.4  # Curve down
                tp = 1.0 - t * 0.6  # Sharp taper
                rb = len(all_verts)
                hw = claw_w * tp * 0.5
                hd = claw_thick * tp * 0.5

                for ri in range(n_ring):
                    angle = 2.0 * math.pi * ri / n_ring
                    all_verts.append((
                        toe_x + math.cos(angle) * hw,
                        cy,
                        cz + math.sin(angle) * hd,
                    ))
                prev = rb - n_ring
                all_faces.extend(_connect_rings_quad(prev, rb, n_ring))

            claw_tip = (toe_x, claw_base_y + claw_len,
                        toe_z - claw_len * 0.4)
            joint_positions[f"{toe_name}_claw_tip"] = claw_tip
            claw_generated = True

        toe_tip_y = toe_y + toe_len
        joint_positions[f"{toe_name}_tip"] = (toe_x, toe_tip_y, toe_z)

        toe_data[toe_name] = {
            "has_bean": True,
            "has_claw": claw_generated,
        }

    return _make_result(
        name=f"Paw_{side}_{detail}",
        vertices=all_verts,
        faces=all_faces,
        category="character_paw",
        detail=detail,
        side=side,
        toe_count=toe_count,
        has_claws=has_claws,
        joint_positions=joint_positions,
        toe_data=toe_data,
    )


# ---------------------------------------------------------------------------
# Task #55: Corrective blend shapes
# ---------------------------------------------------------------------------

_CORRECTIVE_SHAPE_DEFS: dict[str, dict[str, Any]] = {
    "shoulder_raise_L": {
        "joint": "shoulder_L",
        "direction": (0.0, 0.0, 1.0),
        "magnitude": 0.015,
        "region_radius": 0.12,
        "description": "Fixes deltoid collapse when arm raised",
    },
    "shoulder_raise_R": {
        "joint": "shoulder_R",
        "direction": (0.0, 0.0, 1.0),
        "magnitude": 0.015,
        "region_radius": 0.12,
        "description": "Fixes deltoid collapse when arm raised",
    },
    "elbow_bend_L": {
        "joint": "elbow_L",
        "direction": (0.0, 0.01, 0.005),
        "magnitude": 0.01,
        "region_radius": 0.08,
        "description": "Fixes inner arm pinch at elbow bend",
    },
    "elbow_bend_R": {
        "joint": "elbow_R",
        "direction": (0.0, 0.01, 0.005),
        "magnitude": 0.01,
        "region_radius": 0.08,
        "description": "Fixes inner arm pinch at elbow bend",
    },
    "knee_bend_L": {
        "joint": "knee_L",
        "direction": (0.0, -0.01, 0.008),
        "magnitude": 0.012,
        "region_radius": 0.10,
        "description": "Fixes back-of-knee collapse",
    },
    "knee_bend_R": {
        "joint": "knee_R",
        "direction": (0.0, -0.01, 0.008),
        "magnitude": 0.012,
        "region_radius": 0.10,
        "description": "Fixes back-of-knee collapse",
    },
    "hip_flex_L": {
        "joint": "hip_L",
        "direction": (0.0, 0.008, 0.005),
        "magnitude": 0.012,
        "region_radius": 0.12,
        "description": "Fixes groin area during hip flexion",
    },
    "hip_flex_R": {
        "joint": "hip_R",
        "direction": (0.0, 0.008, 0.005),
        "magnitude": 0.012,
        "region_radius": 0.12,
        "description": "Fixes groin area during hip flexion",
    },
}


def generate_corrective_shapes(
    base_vertices: list[Vec3],
    joint_positions: dict[str, Vec3],
) -> dict[str, dict[str, Any]]:
    """Generate corrective blend shapes for body joint deformation.

    Corrective shapes compensate for volume loss at joints during extreme poses
    (e.g., shoulder raise losing deltoid volume, elbow bend pinching inner arm).

    For each corrective shape, vertices near the joint are displaced outward
    to preserve volume, with smooth falloff from the joint center.

    Args:
        base_vertices: Original body mesh vertex positions.
        joint_positions: Dict mapping joint names to (x, y, z) positions.
            Expected joints: shoulder_L/R, elbow_L/R, knee_L/R, hip_L/R.

    Returns:
        Dict mapping shape_name -> {
            "displaced_vertices": list of (x,y,z) -- same length as base_vertices,
            "joint": str,
            "affected_vertex_count": int,
            "max_displacement": float,
            "description": str,
        }
    """
    if not base_vertices:
        return {}

    results: dict[str, dict[str, Any]] = {}

    for shape_name, shape_def in _CORRECTIVE_SHAPE_DEFS.items():
        joint_name = shape_def["joint"]
        direction = shape_def["direction"]
        magnitude = shape_def["magnitude"]
        region_radius = shape_def["region_radius"]
        description = shape_def["description"]

        # Find joint position (use origin if not found)
        joint_pos = joint_positions.get(joint_name, (0.0, 0.0, 0.0))
        jx, jy, jz = joint_pos
        dx, dy, dz = direction

        displaced: list[Vec3] = []
        affected_count = 0
        max_disp = 0.0

        for vx, vy, vz in base_vertices:
            # Distance from joint
            dist_x = vx - jx
            dist_y = vy - jy
            dist_z = vz - jz
            dist = math.sqrt(dist_x * dist_x + dist_y * dist_y + dist_z * dist_z)

            if dist < region_radius:
                # Smooth cubic falloff
                t = dist / region_radius
                falloff = 1.0 - (3.0 * t * t - 2.0 * t * t * t)  # smoothstep

                disp_x = dx * magnitude * falloff
                disp_y = dy * magnitude * falloff
                disp_z = dz * magnitude * falloff

                disp_mag = math.sqrt(disp_x**2 + disp_y**2 + disp_z**2)
                max_disp = max(max_disp, disp_mag)

                displaced.append((vx + disp_x, vy + disp_y, vz + disp_z))
                affected_count += 1
            else:
                displaced.append((vx, vy, vz))

        results[shape_name] = {
            "displaced_vertices": displaced,
            "joint": joint_name,
            "affected_vertex_count": affected_count,
            "max_displacement": round(max_disp, 6),
            "description": description,
        }

    return results
