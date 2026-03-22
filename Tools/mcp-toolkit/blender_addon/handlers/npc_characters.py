"""NPC character body mesh generation for VeilBreakers.

Provides pure-math procedural body mesh generation for 8 NPC body types
(2 genders x 4 builds). Each body is constructed from capsule torsos,
tapered cylinder limbs, sphere heads, and box extremities with proper
edge loops at joints for animation deformation.

All functions are pure Python -- no bpy/bmesh imports. Returns mesh specs
with vertices, faces, joint positions, and metadata.

Body types:
- male/female x heavy/average/slim/elder
- All fit standard ~1.8m height (plus/minus 0.1m for builds)
- 2000-4000 tris per body
- Quad topology at joints (shoulder, elbow, wrist, hip, knee, ankle, neck)
"""

from __future__ import annotations

import math
from typing import Any

from .mesh_smoothing import smooth_assembled_mesh, add_organic_noise
from .facial_topology import generate_hand_mesh, generate_foot_mesh


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_GENDERS = ("male", "female")
VALID_BUILDS = ("heavy", "average", "slim", "elder")

# Base proportions (average male as reference, all in meters, Z-up)
BASE_HEIGHT = 1.8
HEAD_RADIUS = 0.10
NECK_RADIUS = 0.055
NECK_HEIGHT = 0.08

TORSO_SECTIONS = 5  # vertical slices
TORSO_SEGMENTS = 8  # cross-section points

LIMB_SEGMENTS = 8  # cross-section for limbs

# ---------------------------------------------------------------------------
# Build multipliers: (torso_width, limb_thickness, belly_factor, height_mult, spine_curve)
# ---------------------------------------------------------------------------

BUILD_PARAMS: dict[str, dict[str, float]] = {
    "heavy": {
        "torso_width": 1.3,
        "limb_thickness": 1.2,
        "belly_factor": 1.25,
        "height_mult": 1.02,
        "spine_curve": 0.0,
    },
    "average": {
        "torso_width": 1.0,
        "limb_thickness": 1.0,
        "belly_factor": 1.0,
        "height_mult": 1.0,
        "spine_curve": 0.0,
    },
    "slim": {
        "torso_width": 0.85,
        "limb_thickness": 0.85,
        "belly_factor": 0.9,
        "height_mult": 1.01,
        "spine_curve": 0.0,
    },
    "elder": {
        "torso_width": 0.95,
        "limb_thickness": 0.88,
        "belly_factor": 1.0,
        "height_mult": 0.97,
        "spine_curve": 0.04,  # forward hunch
    },
}

# Gender proportions: (shoulder_width_mult, hip_width_mult, torso_taper)
GENDER_PARAMS: dict[str, dict[str, float]] = {
    "male": {
        "shoulder_width": 1.1,
        "hip_width": 0.9,
        "chest_depth": 1.05,
    },
    "female": {
        "shoulder_width": 0.9,
        "hip_width": 1.1,
        "chest_depth": 1.0,
    },
}


# ---------------------------------------------------------------------------
# Low-level geometry helpers
# ---------------------------------------------------------------------------


def _ring(
    cx: float,
    cy: float,
    cz: float,
    rx: float,
    ry: float,
    segments: int,
) -> list[tuple[float, float, float]]:
    """Generate a ring of points in the XY plane at height cz.

    rx, ry are radii along X and Y axes respectively.
    """
    pts: list[tuple[float, float, float]] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        x = cx + math.cos(angle) * rx
        y = cy + math.sin(angle) * ry
        pts.append((x, y, cz))
    return pts


def _connect_rings(
    base_a: int,
    base_b: int,
    segments: int,
) -> list[tuple[int, int, int, int]]:
    """Connect two adjacent rings of `segments` vertices with quad faces."""
    faces: list[tuple[int, int, int, int]] = []
    for i in range(segments):
        i_next = (i + 1) % segments
        faces.append((
            base_a + i,
            base_a + i_next,
            base_b + i_next,
            base_b + i,
        ))
    return faces


def _cap_ring(base: int, segments: int, flip: bool = False) -> tuple[int, ...]:
    """Create an n-gon cap for a ring. flip reverses winding."""
    if flip:
        return tuple(base + i for i in range(segments - 1, -1, -1))
    return tuple(base + i for i in range(segments))


def _weld_coincident_vertices(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    threshold: float = 0.001,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Bug 4 fix: merge vertices within threshold distance for connected topology."""
    n = len(verts)
    if n == 0:
        return verts, faces

    remap: list[int] = list(range(n))
    thresh_sq = threshold * threshold

    for i in range(n):
        if remap[i] != i:
            continue
        xi, yi, zi = verts[i]
        for j in range(i + 1, n):
            if remap[j] != j:
                continue
            dx = verts[j][0] - xi
            dy = verts[j][1] - yi
            dz = verts[j][2] - zi
            if dx * dx + dy * dy + dz * dz < thresh_sq:
                remap[j] = i

    new_indices: dict[int, int] = {}
    new_verts: list[tuple[float, float, float]] = []
    for i in range(n):
        canonical = remap[i]
        if canonical not in new_indices:
            new_indices[canonical] = len(new_verts)
            new_verts.append(verts[canonical])
        remap[i] = new_indices[canonical]

    new_faces: list[tuple[int, ...]] = []
    for face in faces:
        new_face = tuple(remap[idx] for idx in face)
        deduped = []
        for vi in new_face:
            if not deduped or deduped[-1] != vi:
                deduped.append(vi)
        if len(deduped) > 1 and deduped[0] == deduped[-1]:
            deduped.pop()
        if len(deduped) >= 3:
            new_faces.append(tuple(deduped))

    return new_verts, new_faces


def _tapered_cylinder(
    cx: float,
    cy: float,
    z_bottom: float,
    z_top: float,
    r_bottom: float,
    r_top: float,
    segments: int,
    num_sections: int,
    base_idx: int,
    cap_bottom: bool = False,
    cap_top: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a tapered cylinder along Z with multiple sections for edge loops.

    Returns (vertices, faces) with indices offset by base_idx.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for s in range(num_sections + 1):
        t = s / num_sections
        z = z_bottom + t * (z_top - z_bottom)
        r = r_bottom + t * (r_top - r_bottom)
        ring = _ring(cx, cy, z, r, r, segments)
        verts.extend(ring)

    # Connect rings
    for s in range(num_sections):
        ring_a = base_idx + s * segments
        ring_b = base_idx + (s + 1) * segments
        faces.extend(_connect_rings(ring_a, ring_b, segments))

    # Caps
    if cap_bottom:
        faces.append(_cap_ring(base_idx, segments, flip=True))
    if cap_top:
        last_ring = base_idx + num_sections * segments
        faces.append(_cap_ring(last_ring, segments, flip=False))

    return verts, faces


def _sphere(
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    segments: int,
    rings: int,
    base_idx: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a UV sphere centered at (cx, cy, cz).

    Returns (vertices, faces) with quad topology.
    """
    # Bug 9 fix: guard against rings < 2 which would crash face generation
    rings = max(rings, 2)
    segments = max(segments, 3)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Bottom pole
    verts.append((cx, cy, cz - radius))

    # Intermediate rings
    for r in range(1, rings):
        phi = math.pi * r / rings
        z = cz - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            x = cx + ring_r * math.cos(theta)
            y = cy + ring_r * math.sin(theta)
            verts.append((x, y, z))

    # Top pole
    verts.append((cx, cy, cz + radius))

    b = base_idx
    bottom_pole = b
    top_pole = b + 1 + (rings - 1) * segments

    # Bottom cap triangles
    first_ring = b + 1
    for s in range(segments):
        s_next = (s + 1) % segments
        faces.append((bottom_pole, first_ring + s_next, first_ring + s))

    # Middle quads
    for r in range(rings - 2):
        ring_a = b + 1 + r * segments
        ring_b = b + 1 + (r + 1) * segments
        faces.extend(_connect_rings(ring_a, ring_b, segments))

    # Top cap triangles
    last_ring = b + 1 + (rings - 2) * segments
    for s in range(segments):
        s_next = (s + 1) % segments
        faces.append((top_pole, last_ring + s, last_ring + s_next))

    return verts, faces


def _box_mesh(
    cx: float,
    cy: float,
    cz: float,
    sx: float,
    sy: float,
    sz: float,
    base_idx: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate an axis-aligned box with half-sizes sx, sy, sz."""
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
        (b + 0, b + 3, b + 2, b + 1),  # bottom
        (b + 4, b + 5, b + 6, b + 7),  # top
        (b + 0, b + 1, b + 5, b + 4),  # front
        (b + 2, b + 3, b + 7, b + 6),  # back
        (b + 0, b + 4, b + 7, b + 3),  # left
        (b + 1, b + 2, b + 6, b + 5),  # right
    ]
    return verts, faces


def _subdivided_box(
    cx: float,
    cy: float,
    cz: float,
    sx: float,
    sy: float,
    sz: float,
    divs_x: int,
    divs_z: int,
    base_idx: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a box subdivided along X and Z for finger/toe divisions.

    divs_x: divisions along X (finger count)
    divs_z: divisions along Z (vertical)
    Creates a grid of quads on top and bottom, sides are simple quads.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Create grid of points on top and bottom faces
    for face_z_offset in [-sz, sz]:
        for iz in range(divs_z + 1):
            tz = iz / divs_z
            z_local = -sy + 2 * sy * tz
            for ix in range(divs_x + 1):
                tx = ix / divs_x
                x_local = -sx + 2 * sx * tx
                verts.append((cx + x_local, cy + z_local, cz + face_z_offset))

    b = base_idx
    cols = divs_x + 1
    rows = divs_z + 1
    bottom_start = b
    top_start = b + rows * cols

    # Bottom face quads (flip winding)
    for iz in range(divs_z):
        for ix in range(divs_x):
            v0 = bottom_start + iz * cols + ix
            v1 = v0 + 1
            v2 = v0 + cols + 1
            v3 = v0 + cols
            faces.append((v0, v3, v2, v1))

    # Top face quads
    for iz in range(divs_z):
        for ix in range(divs_x):
            v0 = top_start + iz * cols + ix
            v1 = v0 + 1
            v2 = v0 + cols + 1
            v3 = v0 + cols
            faces.append((v0, v1, v2, v3))

    # Side faces connecting top and bottom edges
    # Front edge (iz=0)
    for ix in range(divs_x):
        b0 = bottom_start + ix
        b1 = bottom_start + ix + 1
        t0 = top_start + ix
        t1 = top_start + ix + 1
        faces.append((b0, b1, t1, t0))

    # Back edge (iz=divs_z)
    for ix in range(divs_x):
        b0 = bottom_start + divs_z * cols + ix
        b1 = b0 + 1
        t0 = top_start + divs_z * cols + ix
        t1 = t0 + 1
        faces.append((b1, b0, t0, t1))

    # Left edge (ix=0)
    for iz in range(divs_z):
        b0 = bottom_start + iz * cols
        b1 = bottom_start + (iz + 1) * cols
        t0 = top_start + iz * cols
        t1 = top_start + (iz + 1) * cols
        faces.append((b1, b0, t0, t1))

    # Right edge (ix=divs_x)
    for iz in range(divs_z):
        b0 = bottom_start + iz * cols + divs_x
        b1 = bottom_start + (iz + 1) * cols + divs_x
        t0 = top_start + iz * cols + divs_x
        t1 = top_start + (iz + 1) * cols + divs_x
        faces.append((b0, b1, t1, t0))

    return verts, faces


# ---------------------------------------------------------------------------
# Torso generation
# ---------------------------------------------------------------------------


def _generate_torso(
    shoulder_w: float,
    hip_w: float,
    chest_depth: float,
    belly_factor: float,
    spine_curve: float,
    z_bottom: float,
    z_top: float,
    segments: int,
    sections: int,
    base_idx: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate torso as a multi-section capsule with varying cross-sections.

    The torso tapers from hips at bottom to shoulders at top, with optional
    belly bulge and spine curvature (for elder builds).
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Define cross-section profiles at each section height
    # Sections from bottom (hips) to top (shoulders/neck)
    for s in range(sections + 1):
        t = s / sections
        z = z_bottom + t * (z_top - z_bottom)

        # Width interpolation: hips -> waist (narrower) -> chest (wider) -> shoulders
        if t < 0.3:
            # Hips to waist
            local_t = t / 0.3
            rx = hip_w * (1.0 - 0.15 * local_t)
        elif t < 0.55:
            # Waist to belly
            local_t = (t - 0.3) / 0.25
            rx = hip_w * 0.85 * (1.0 + (belly_factor - 1.0) * math.sin(local_t * math.pi))
        elif t < 0.8:
            # Belly to chest
            local_t = (t - 0.55) / 0.25
            rx = hip_w * 0.85 + (shoulder_w - hip_w * 0.85) * local_t
        else:
            # Chest to shoulders
            local_t = (t - 0.8) / 0.2
            rx = shoulder_w * (1.0 - 0.05 * local_t)

        # Depth varies with section
        if t < 0.5:
            ry = rx * 0.7 * chest_depth * belly_factor
        else:
            ry = rx * 0.65 * chest_depth

        # Apply spine curve (forward lean for elder)
        y_offset = spine_curve * math.sin(t * math.pi) * (z_top - z_bottom)

        ring = _ring(0.0, y_offset, z, rx, ry, segments)
        verts.extend(ring)

    # Connect rings
    for s in range(sections):
        ring_a = base_idx + s * segments
        ring_b = base_idx + (s + 1) * segments
        faces.extend(_connect_rings(ring_a, ring_b, segments))

    return verts, faces


# ---------------------------------------------------------------------------
# Head generation
# ---------------------------------------------------------------------------


def _generate_head(
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    segments: int,
    base_idx: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate head as a sphere with nose bump and eye socket indentations."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    rings = 6
    # Bottom pole
    verts.append((cx, cy, cz - radius * 0.7))  # Slightly flattened bottom (neck area)

    for r in range(1, rings):
        phi = math.pi * r / rings
        z = cz - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)

        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            x = cx + ring_r * math.cos(theta)
            y = cy + ring_r * math.sin(theta)

            # Nose bump: push forward vertices in front-center region
            if r == 3 and abs(theta) < 0.5:
                y -= radius * 0.12  # Push nose forward (negative Y is front)
            elif r == 3 and (abs(theta - 0.4) < 0.25 or abs(theta - (2 * math.pi - 0.4)) < 0.25):
                # Brow ridge / eye socket region
                y -= radius * 0.04

            # Eye sockets: slight indentation
            if r in (2, 3):
                # Check if vertex is in eye socket region
                eye_angle_l = math.pi * 0.15
                eye_angle_r = 2 * math.pi - math.pi * 0.15
                if abs(theta - eye_angle_l) < 0.3 or abs(theta - eye_angle_r) < 0.3:
                    if r == 3:
                        y += radius * 0.03  # Indent inward for socket

            verts.append((x, y, z))

    # Top pole
    verts.append((cx, cy, cz + radius))

    b = base_idx
    bottom_pole = b
    top_pole = b + 1 + (rings - 1) * segments

    # Bottom cap triangles
    first_ring = b + 1
    for s in range(segments):
        s_next = (s + 1) % segments
        faces.append((bottom_pole, first_ring + s_next, first_ring + s))

    # Middle quads
    for r in range(rings - 2):
        ring_a = b + 1 + r * segments
        ring_b = b + 1 + (r + 1) * segments
        faces.extend(_connect_rings(ring_a, ring_b, segments))

    # Top cap triangles
    last_ring = b + 1 + (rings - 2) * segments
    for s in range(segments):
        s_next = (s + 1) % segments
        faces.append((top_pole, last_ring + s, last_ring + s_next))

    return verts, faces


# ---------------------------------------------------------------------------
# Main body generator
# ---------------------------------------------------------------------------


def generate_npc_body_mesh(
    gender: str = "male",
    build: str = "average",
) -> MeshSpec:
    """Generate a complete NPC body mesh with joint positions for rigging.

    Args:
        gender: "male" or "female"
        build: "heavy", "average", "slim", or "elder"

    Returns:
        MeshSpec dict with vertices, faces, joint_positions, and metadata.
    """
    if gender not in VALID_GENDERS:
        raise ValueError(f"Invalid gender {gender!r}. Must be one of {VALID_GENDERS}")
    if build not in VALID_BUILDS:
        raise ValueError(f"Invalid build {build!r}. Must be one of {VALID_BUILDS}")

    bp = BUILD_PARAMS[build]
    gp = GENDER_PARAMS[gender]

    height = BASE_HEIGHT * bp["height_mult"]
    torso_width_mult = bp["torso_width"]
    limb_mult = bp["limb_thickness"]
    belly = bp["belly_factor"]
    spine_curve = bp["spine_curve"]
    shoulder_mult = gp["shoulder_width"]
    hip_mult = gp["hip_width"]
    chest_d = gp["chest_depth"]

    # Vertical proportions (fractions of total height)
    feet_top = 0.045 * height
    ankle_z = 0.047 * height
    shin_bottom = ankle_z
    knee_z = 0.28 * height
    thigh_bottom = knee_z
    hip_z = 0.52 * height
    torso_bottom = hip_z * 0.95
    torso_top = 0.80 * height
    neck_bottom = torso_top
    neck_top = 0.86 * height
    head_center_z = 0.91 * height

    # Widths
    base_shoulder_w = 0.19 * torso_width_mult * shoulder_mult
    base_hip_w = 0.14 * torso_width_mult * hip_mult

    # Limb radii
    upper_arm_r_top = 0.042 * limb_mult
    upper_arm_r_bottom = 0.035 * limb_mult
    lower_arm_r_top = 0.033 * limb_mult
    lower_arm_r_bottom = 0.025 * limb_mult
    thigh_r_top = 0.065 * limb_mult
    thigh_r_bottom = 0.045 * limb_mult
    shin_r_top = 0.043 * limb_mult
    shin_r_bottom = 0.032 * limb_mult

    # Joint positions
    shoulder_x = base_shoulder_w + upper_arm_r_top * 0.5
    elbow_z = 0.62 * height
    wrist_z = 0.45 * height
    shoulder_z = torso_top - 0.04 * height
    hip_x = base_hip_w * 0.65

    joints: dict[str, tuple[float, float, float]] = {
        "head": (0.0, 0.0, head_center_z),
        "neck": (0.0, 0.0, neck_bottom),
        "spine_upper": (0.0, 0.0, torso_top - 0.1 * height),
        "spine_mid": (0.0, 0.0, (torso_bottom + torso_top) * 0.5),
        "hips": (0.0, 0.0, hip_z),
        "shoulder_l": (-shoulder_x, 0.0, shoulder_z),
        "shoulder_r": (shoulder_x, 0.0, shoulder_z),
        "elbow_l": (-shoulder_x - 0.12, 0.0, elbow_z),
        "elbow_r": (shoulder_x + 0.12, 0.0, elbow_z),
        "wrist_l": (-shoulder_x - 0.25, 0.0, wrist_z),
        "wrist_r": (shoulder_x + 0.25, 0.0, wrist_z),
        "hip_l": (-hip_x, 0.0, hip_z),
        "hip_r": (hip_x, 0.0, hip_z),
        "knee_l": (-hip_x, 0.0, knee_z),
        "knee_r": (hip_x, 0.0, knee_z),
        "ankle_l": (-hip_x, 0.0, ankle_z),
        "ankle_r": (hip_x, 0.0, ankle_z),
    }

    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    material_regions: dict[int, str] = {}

    def _add(
        v: list[tuple[float, float, float]],
        f: list[tuple[int, ...]],
        region: str = "body_skin",
    ) -> None:
        face_start = len(all_faces)
        all_verts.extend(v)
        all_faces.extend(f)
        for fi in range(face_start, len(all_faces)):
            material_regions[fi] = region

    # --- Torso ---
    t_verts, t_faces = _generate_torso(
        shoulder_w=base_shoulder_w,
        hip_w=base_hip_w,
        chest_depth=chest_d,
        belly_factor=belly,
        spine_curve=spine_curve,
        z_bottom=torso_bottom,
        z_top=torso_top,
        segments=TORSO_SEGMENTS,
        sections=TORSO_SECTIONS,
        base_idx=len(all_verts),
    )
    _add(t_verts, t_faces, "body_skin")

    # --- Neck ---
    neck_r = NECK_RADIUS * torso_width_mult * 0.9
    n_verts, n_faces = _tapered_cylinder(
        cx=0.0, cy=0.0,
        z_bottom=neck_bottom,
        z_top=neck_top,
        r_bottom=neck_r * 1.1,
        r_top=neck_r * 0.9,
        segments=LIMB_SEGMENTS,
        num_sections=2,
        base_idx=len(all_verts),
    )
    _add(n_verts, n_faces, "head_skin")

    # --- Head ---
    head_r = HEAD_RADIUS * (1.05 if build == "heavy" else 1.0)
    h_verts, h_faces = _generate_head(
        cx=0.0, cy=spine_curve * 0.3, cz=head_center_z,
        radius=head_r,
        segments=LIMB_SEGMENTS,
        base_idx=len(all_verts),
    )
    _add(h_verts, h_faces, "head_skin")

    # --- Arms (both sides) ---
    for side in (-1, 1):
        arm_x = side * shoulder_x

        # Upper arm: shoulder to elbow
        ua_verts, ua_faces = _tapered_cylinder(
            cx=arm_x, cy=0.0,
            z_bottom=elbow_z,
            z_top=shoulder_z,
            r_bottom=upper_arm_r_bottom,
            r_top=upper_arm_r_top,
            segments=LIMB_SEGMENTS,
            num_sections=3,
            base_idx=len(all_verts),
        )
        _add(ua_verts, ua_faces, "body_skin")

        # Lower arm: elbow to wrist
        forearm_x = arm_x + side * 0.12
        la_cx = (arm_x + forearm_x + side * 0.25) * 0.5
        la_verts, la_faces = _tapered_cylinder(
            cx=forearm_x, cy=0.0,
            z_bottom=wrist_z,
            z_top=elbow_z,
            r_bottom=lower_arm_r_bottom,
            r_top=lower_arm_r_top,
            segments=LIMB_SEGMENTS,
            num_sections=3,
            base_idx=len(all_verts),
        )
        _add(la_verts, la_faces, "body_skin")

        # Hand -- Bug 14 fix: use anatomical hand mesh from facial_topology
        hand_cx = arm_x + side * 0.25
        hand_z = wrist_z - 0.08
        hand_side = "left" if side == -1 else "right"
        hand_spec = generate_hand_mesh(detail="low", side=hand_side)
        hand_raw_verts = hand_spec["vertices"]
        hand_raw_faces = hand_spec["faces"]
        # Offset hand vertices to correct position; hand mesh is at origin
        base_idx = len(all_verts)
        hand_verts = [(v[0] + hand_cx, v[1] + hand_z, v[2]) for v in hand_raw_verts]
        hand_faces = [tuple(idx + base_idx for idx in f) for f in hand_raw_faces]
        _add(hand_verts, hand_faces, "extremity_skin")

    # --- Legs (both sides) ---
    for side in (-1, 1):
        leg_x = side * hip_x

        # Thigh: hip to knee
        th_verts, th_faces = _tapered_cylinder(
            cx=leg_x, cy=0.0,
            z_bottom=knee_z,
            z_top=hip_z,
            r_bottom=thigh_r_bottom,
            r_top=thigh_r_top,
            segments=LIMB_SEGMENTS,
            num_sections=3,
            base_idx=len(all_verts),
        )
        _add(th_verts, th_faces, "body_skin")

        # Shin: knee to ankle
        sh_verts, sh_faces = _tapered_cylinder(
            cx=leg_x, cy=0.0,
            z_bottom=ankle_z,
            z_top=knee_z,
            r_bottom=shin_r_bottom,
            r_top=shin_r_top,
            segments=LIMB_SEGMENTS,
            num_sections=3,
            base_idx=len(all_verts),
        )
        _add(sh_verts, sh_faces, "body_skin")

        # Foot -- Bug 14 fix: use anatomical foot mesh from facial_topology
        foot_cx = leg_x
        foot_z = feet_top * 0.5
        foot_side = "left" if side == -1 else "right"
        foot_spec = generate_foot_mesh(detail="low", side=foot_side)
        foot_raw_verts = foot_spec["vertices"]
        foot_raw_faces = foot_spec["faces"]
        # Offset foot vertices to correct position; foot mesh is at origin
        base_idx_foot = len(all_verts)
        foot_verts = [(v[0] + foot_cx, v[1] - 0.04, v[2] + foot_z) for v in foot_raw_verts]
        foot_faces = [tuple(idx + base_idx_foot for idx in f) for f in foot_raw_faces]
        _add(foot_verts, foot_faces, "extremity_skin")

    # Bug 4 fix: weld coincident vertices at primitive junctions
    all_verts, all_faces = _weld_coincident_vertices(all_verts, all_faces)
    # Face indices are preserved during welding (only vertex indices remap).
    # Extend regions for any new faces from welding, keep existing assignments.
    for fi in range(len(all_faces)):
        if fi not in material_regions:
            material_regions[fi] = "body_skin"

    # Smooth assembled geometry to eliminate primitive junctions
    all_verts = smooth_assembled_mesh(
        all_verts, all_faces, smooth_iterations=3,
    )
    # Add organic imperfection noise
    all_verts = add_organic_noise(
        all_verts, faces=all_faces, strength=0.003,
    )

    return {
        "vertices": all_verts,
        "faces": all_faces,
        "joint_positions": joints,
        "material_regions": material_regions,
        "height": height,
        "gender": gender,
        "build": build,
        "subdivision_levels": {"viewport": 1, "render": 2},
        "smooth_shading": True,
        "metadata": {
            "name": f"NPC_{gender}_{build}",
            "poly_count": len(all_faces),
            "vertex_count": len(all_verts),
            "tri_count": _estimate_tri_count(all_faces),
            "gender": gender,
            "build": build,
            "height": height,
            "material_region_names": sorted(set(material_regions.values())),
        },
    }


def _estimate_tri_count(faces: list[tuple[int, ...]]) -> int:
    """Estimate triangle count from n-gon face list."""
    count = 0
    for f in faces:
        n = len(f)
        if n >= 3:
            count += n - 2
    return count


# ---------------------------------------------------------------------------
# NPC Registry
# ---------------------------------------------------------------------------

NPC_GENERATORS = {
    "body": (
        generate_npc_body_mesh,
        {
            "genders": list(VALID_GENDERS),
            "builds": list(VALID_BUILDS),
        },
    ),
}
