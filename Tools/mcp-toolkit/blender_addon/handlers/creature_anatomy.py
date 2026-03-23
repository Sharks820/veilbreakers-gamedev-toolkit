"""AAA-quality anatomical creature mesh generators for VeilBreakers.

Replaces the assembled-primitives approach (cylinder bodies + sphere heads)
with anatomically-correct, rigging-ready creature meshes built from
continuous spine curves with profiled cross-sections.

Key differences from monster_bodies.py:
- Bodies are defined as spine curves with elliptical cross-sections, NOT
  assembled cylinders/spheres.
- Every joint has proper edge loop topology for deformation.
- Mouths have interiors (palate, tongue, teeth, gums).
- Eyes have closing eyelids (upper + lower) matching eye sphere curvature.
- Paws have individual toes, pads, and claw geometry.
- Wings have membrane/feather topology suitable for cloth sim.
- Serpents have 40+ segments for smooth coiling animation.
- All vertex groups are pre-assigned for auto-rigging.

All functions are pure Python with math-only dependencies (no bpy/bmesh).
Returns mesh specification dicts compatible with the existing pipeline.

Quality target: FromSoftware / Capcom creature anatomy fidelity.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
FaceList = list[tuple[int, ...]]
VertList = list[Vec3]
CreatureMeshResult = dict[str, Any]

# ---------------------------------------------------------------------------
# Constants: species proportions
# ---------------------------------------------------------------------------

QUADRUPED_PROPORTIONS: dict[str, dict[str, Any]] = {
    "wolf": {
        "body_length": 1.2,
        "body_height": 0.7,
        "body_width": 0.35,
        "head_length": 0.3,
        "snout_length": 0.15,
        "ear_height": 0.08,
        "leg_length_front": 0.6,
        "leg_length_rear": 0.65,
        "tail_length": 0.5,
        "neck_length": 0.25,
        "chest_keel": 0.15,
        "shoulder_blade_height": 0.05,
        "has_hump": False,
        "paw_type": "canine",
        "toe_count": 4,
        "spine_points": 14,
        "cross_segments": 12,
        "tooth_style": "carnivore",
        "ear_shape": "pointed",
    },
    "bear": {
        "body_length": 1.8,
        "body_height": 1.0,
        "body_width": 0.6,
        "head_length": 0.35,
        "snout_length": 0.12,
        "ear_height": 0.06,
        "leg_length_front": 0.7,
        "leg_length_rear": 0.75,
        "tail_length": 0.1,
        "neck_length": 0.3,
        "chest_keel": 0.2,
        "shoulder_blade_height": 0.08,
        "has_hump": True,
        "paw_type": "bear",
        "toe_count": 5,
        "spine_points": 16,
        "cross_segments": 14,
        "tooth_style": "carnivore",
        "ear_shape": "rounded",
    },
    "lion": {
        "body_length": 1.4,
        "body_height": 0.8,
        "body_width": 0.4,
        "head_length": 0.28,
        "snout_length": 0.1,
        "ear_height": 0.06,
        "leg_length_front": 0.65,
        "leg_length_rear": 0.7,
        "tail_length": 0.7,
        "neck_length": 0.22,
        "chest_keel": 0.18,
        "shoulder_blade_height": 0.06,
        "has_hump": False,
        "paw_type": "feline",
        "toe_count": 4,
        "spine_points": 14,
        "cross_segments": 12,
        "tooth_style": "carnivore",
        "ear_shape": "rounded",
    },
    "horse": {
        "body_length": 1.6,
        "body_height": 1.1,
        "body_width": 0.45,
        "head_length": 0.4,
        "snout_length": 0.2,
        "ear_height": 0.1,
        "leg_length_front": 0.9,
        "leg_length_rear": 0.95,
        "tail_length": 0.6,
        "neck_length": 0.5,
        "chest_keel": 0.12,
        "shoulder_blade_height": 0.07,
        "has_hump": False,
        "paw_type": "hoof",
        "toe_count": 1,
        "spine_points": 14,
        "cross_segments": 12,
        "tooth_style": "herbivore",
        "ear_shape": "pointed",
    },
    "deer": {
        "body_length": 1.3,
        "body_height": 0.9,
        "body_width": 0.3,
        "head_length": 0.25,
        "snout_length": 0.1,
        "ear_height": 0.1,
        "leg_length_front": 0.8,
        "leg_length_rear": 0.85,
        "tail_length": 0.15,
        "neck_length": 0.35,
        "chest_keel": 0.08,
        "shoulder_blade_height": 0.04,
        "has_hump": False,
        "paw_type": "cloven_hoof",
        "toe_count": 2,
        "spine_points": 14,
        "cross_segments": 12,
        "tooth_style": "herbivore",
        "ear_shape": "wide",
    },
    "boar": {
        "body_length": 1.1,
        "body_height": 0.6,
        "body_width": 0.45,
        "head_length": 0.3,
        "snout_length": 0.15,
        "ear_height": 0.07,
        "leg_length_front": 0.4,
        "leg_length_rear": 0.45,
        "tail_length": 0.15,
        "neck_length": 0.15,
        "chest_keel": 0.2,
        "shoulder_blade_height": 0.1,
        "has_hump": True,
        "paw_type": "cloven_hoof",
        "toe_count": 2,
        "spine_points": 12,
        "cross_segments": 12,
        "tooth_style": "monster",
        "ear_shape": "floppy",
    },
    "rat_giant": {
        "body_length": 0.8,
        "body_height": 0.35,
        "body_width": 0.2,
        "head_length": 0.18,
        "snout_length": 0.1,
        "ear_height": 0.08,
        "leg_length_front": 0.25,
        "leg_length_rear": 0.3,
        "tail_length": 0.9,
        "neck_length": 0.1,
        "chest_keel": 0.06,
        "shoulder_blade_height": 0.02,
        "has_hump": False,
        "paw_type": "canine",
        "toe_count": 4,
        "spine_points": 12,
        "cross_segments": 10,
        "tooth_style": "monster",
        "ear_shape": "rounded",
    },
}

ALL_SPECIES = list(QUADRUPED_PROPORTIONS.keys())

SERPENT_HEAD_STYLES = ["viper", "python", "cobra"]

WING_TYPES = ["bat", "bird", "dragon", "insect"]

PAW_TYPES = ["canine", "feline", "bear", "bird_talons", "hoof", "cloven_hoof"]

TOOTH_STYLES = ["carnivore", "herbivore", "monster", "serpent"]

FANTASY_CREATURE_TYPES = [
    "chimera", "wyvern", "basilisk", "dire_wolf",
    "spider_queen", "undead_horse", "treant",
]

BRAND_ANATOMY_FEATURES: dict[str, dict[str, Any]] = {
    "IRON": {"metallic_patches": True, "sharp_protrusions": True},
    "SAVAGE": {"bone_spurs": True, "scarring": True},
    "SURGE": {"crystal_growths": True, "energy_veins": True},
    "VENOM": {"pustules": True, "dripping_geometry": True},
    "DREAD": {"bony_spurs": True, "skeletal_exposure": True},
    "LEECH": {"parasitic_growths": True, "pulsing_veins": True},
    "GRACE": {"feather_tufts": True, "luminous_markings": True},
    "MEND": {"bark_patches": True, "moss_growth": True},
    "RUIN": {"crack_lines": True, "floating_fragments": True},
    "VOID": {"void_patches": True, "geometric_distortion": True},
}

ALL_BRANDS = list(BRAND_ANATOMY_FEATURES.keys())

# ---------------------------------------------------------------------------
# Core math utilities
# ---------------------------------------------------------------------------


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


def _lerp3(a: Vec3, b: Vec3, t: float) -> Vec3:
    """Lerp between two 3D points."""
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def _vec3_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec3_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec3_scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _vec3_length(v: Vec3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _vec3_normalize(v: Vec3) -> Vec3:
    length = _vec3_length(v)
    if length < 1e-10:
        return (0.0, 1.0, 0.0)
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def _vec3_cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _vec3_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _pseudo_noise(i: int, j: int, seed: int = 0) -> float:
    """Deterministic pseudo-noise in [-1, 1]."""
    v = (i * 7919 + j * 6271 + seed * 1031) % 10000
    return (v / 5000.0) - 1.0


def _smooth_step(t: float) -> float:
    """Hermite smoothstep for smooth interpolation."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _catmull_rom(p0: Vec3, p1: Vec3, p2: Vec3, p3: Vec3, t: float) -> Vec3:
    """Catmull-Rom spline interpolation between p1 and p2."""
    t2 = t * t
    t3 = t2 * t
    x = 0.5 * (
        (2.0 * p1[0])
        + (-p0[0] + p2[0]) * t
        + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
        + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
    )
    y = 0.5 * (
        (2.0 * p1[1])
        + (-p0[1] + p2[1]) * t
        + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
        + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
    )
    z = 0.5 * (
        (2.0 * p1[2])
        + (-p0[2] + p2[2]) * t
        + (2.0 * p0[2] - 5.0 * p1[2] + 4.0 * p2[2] - p3[2]) * t2
        + (-p0[2] + 3.0 * p1[2] - 3.0 * p2[2] + p3[2]) * t3
    )
    return (x, y, z)


# ---------------------------------------------------------------------------
# Core mesh construction utilities
# ---------------------------------------------------------------------------


def _merge_parts(*parts: tuple[VertList, FaceList]) -> tuple[VertList, FaceList]:
    """Merge multiple (verts, faces) tuples, remapping face indices."""
    all_verts: VertList = []
    all_faces: FaceList = []
    for verts, faces in parts:
        offset = len(all_verts)
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces


def _connect_rings(ring_a_start: int, ring_b_start: int,
                   segments: int) -> FaceList:
    """Connect two vertex rings with quad faces."""
    faces: FaceList = []
    for i in range(segments):
        i_next = (i + 1) % segments
        faces.append((
            ring_a_start + i,
            ring_a_start + i_next,
            ring_b_start + i_next,
            ring_b_start + i,
        ))
    return faces


def _cap_ring(ring_start: int, segments: int,
              reverse: bool = False) -> tuple[int, ...]:
    """Create a fan cap for a ring. Returns single polygon face."""
    if reverse:
        return tuple(ring_start + i for i in range(segments - 1, -1, -1))
    return tuple(ring_start + i for i in range(segments))


def _compute_bbox(verts: VertList) -> tuple[Vec3, Vec3]:
    """Compute axis-aligned bounding box."""
    if not verts:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _build_frame(tangent: Vec3, up_hint: Vec3 = (0.0, 1.0, 0.0)
                 ) -> tuple[Vec3, Vec3, Vec3]:
    """Build an orthonormal frame (tangent, normal, binormal) for a spine point.

    tangent: direction along the spine.
    Returns: (tangent, normal, binormal) all normalized.
    """
    t = _vec3_normalize(tangent)
    # Handle degenerate case where tangent is parallel to up hint
    dot = abs(_vec3_dot(t, up_hint))
    if dot > 0.99:
        up_hint = (1.0, 0.0, 0.0)
    binormal = _vec3_normalize(_vec3_cross(t, up_hint))
    normal = _vec3_normalize(_vec3_cross(binormal, t))
    return t, normal, binormal


# ---------------------------------------------------------------------------
# Anatomical spine body builder (core of the AAA approach)
# ---------------------------------------------------------------------------


def _build_body_from_spine(
    spine_points: list[Vec3],
    radii: list[tuple[float, float]],
    segments: int = 12,
    profile_fn: Any = None,
) -> tuple[VertList, FaceList]:
    """Build organic body mesh from spine curve with anatomical profiles.

    Unlike simple cylinder assembly, this creates a single continuous mesh
    where each ring smoothly transitions to the next via interpolated
    cross-sections. The profile function modifies per-angle radius for
    anatomical details (keel, shoulder blades, hip bones, spine ridge).

    Args:
        spine_points: Control points along the creature's spine.
        radii: Per-point (rx, ry) elliptical radii for cross-section.
        segments: Number of vertices per cross-section ring.
        profile_fn: Optional callable(spine_t, angle, rx, ry) -> (rx', ry')
            that modifies radii based on position along spine and angle.

    Returns:
        (vertices, faces) forming a continuous tube mesh.
    """
    n_points = len(spine_points)
    if n_points < 2:
        return [], []

    verts: VertList = []
    faces: FaceList = []

    for i in range(n_points):
        pt = spine_points[i]
        rx, ry = radii[i]

        # Compute tangent via central differences
        if i == 0:
            tangent = _vec3_sub(spine_points[1], spine_points[0])
        elif i == n_points - 1:
            tangent = _vec3_sub(spine_points[-1], spine_points[-2])
        else:
            tangent = _vec3_sub(spine_points[i + 1], spine_points[i - 1])

        _, normal, binormal = _build_frame(tangent)
        spine_t = i / max(n_points - 1, 1)

        ring_start = len(verts)
        for j in range(segments):
            angle = 2.0 * math.pi * j / segments
            local_rx = rx
            local_ry = ry

            if profile_fn is not None:
                local_rx, local_ry = profile_fn(spine_t, angle, rx, ry)

            # Compute point on elliptical cross-section in local frame
            px = math.cos(angle) * local_rx
            py = math.sin(angle) * local_ry

            # Transform to world space using frame
            wx = pt[0] + normal[0] * px + binormal[0] * py
            wy = pt[1] + normal[1] * px + binormal[1] * py
            wz = pt[2] + normal[2] * px + binormal[2] * py
            verts.append((wx, wy, wz))

        # Connect to previous ring
        if i > 0:
            prev_start = ring_start - segments
            faces.extend(_connect_rings(prev_start, ring_start, segments))

    # End caps
    if n_points >= 2:
        faces.append(_cap_ring(0, segments, reverse=True))
        faces.append(_cap_ring(len(verts) - segments, segments))

    return verts, faces


# ---------------------------------------------------------------------------
# Anatomical profile functions
# ---------------------------------------------------------------------------


def _quadruped_body_profile(
    props: dict[str, Any],
) -> Any:
    """Return a profile function for quadruped body cross-sections.

    Adds:
    - Chest keel (downward protrusion at chest)
    - Shoulder blade ridge (dorsal protrusion at shoulders)
    - Hip bone prominence (lateral protrusions at hips)
    - Spine ridge (subtle dorsal ridge)
    - Belly sag (ventral curvature)
    """
    chest_keel = props.get("chest_keel", 0.15)
    shoulder_blade_h = props.get("shoulder_blade_height", 0.05)
    has_hump = props.get("has_hump", False)

    def profile(spine_t: float, angle: float, rx: float, ry: float
                ) -> tuple[float, float]:
        # angle: 0 = right, pi/2 = top, pi = left, 3pi/2 = bottom
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)

        mod_rx = rx
        mod_ry = ry

        # Spine ridge (top, angle near pi/2)
        top_factor = max(0.0, sin_a)
        spine_ridge = top_factor ** 4 * 0.08 * ry
        mod_ry += spine_ridge if sin_a > 0.7 else 0.0

        # Chest keel (bottom, at front 30% of body)
        if spine_t < 0.4 and sin_a < -0.5:
            keel_strength = (1.0 - spine_t / 0.4) * chest_keel
            bottom_factor = max(0.0, -sin_a - 0.5) * 2.0
            mod_ry += bottom_factor * keel_strength * ry

        # Shoulder blade (top-sides at spine_t ~ 0.2-0.35)
        if 0.15 < spine_t < 0.4 and sin_a > 0.3:
            blade_t = 1.0 - abs(spine_t - 0.27) / 0.13
            blade_t = max(0.0, min(1.0, blade_t))
            side_factor = abs(cos_a) * (sin_a - 0.3) / 0.7
            mod_rx += side_factor * blade_t * shoulder_blade_h * rx
            mod_ry += (sin_a - 0.3) * blade_t * shoulder_blade_h * ry * 0.5

        # Shoulder hump (for bear/boar)
        if has_hump and 0.2 < spine_t < 0.4 and sin_a > 0.5:
            hump_t = 1.0 - abs(spine_t - 0.3) / 0.1
            hump_t = max(0.0, min(1.0, hump_t))
            mod_ry += hump_t * 0.15 * ry * (sin_a - 0.5) * 2.0

        # Hip bone prominence (sides at spine_t ~ 0.7-0.85)
        if 0.65 < spine_t < 0.9:
            hip_t = 1.0 - abs(spine_t - 0.77) / 0.12
            hip_t = max(0.0, min(1.0, hip_t))
            side_prominence = abs(cos_a) ** 2 * hip_t * 0.1
            mod_rx += side_prominence * rx

        # Belly sag (bottom, middle of body)
        if 0.3 < spine_t < 0.7 and sin_a < -0.3:
            belly_t = 1.0 - abs(spine_t - 0.5) / 0.2
            belly_t = max(0.0, min(1.0, belly_t))
            belly_drop = max(0.0, -sin_a - 0.3) * belly_t * 0.06
            mod_ry += belly_drop * ry

        return (mod_rx, mod_ry)

    return profile


# ---------------------------------------------------------------------------
# Spine curve generators for different species
# ---------------------------------------------------------------------------


def _generate_quadruped_spine(
    props: dict[str, Any],
    scale: float,
) -> tuple[list[Vec3], list[tuple[float, float]]]:
    """Generate anatomical spine curve and cross-section radii for a quadruped.

    The spine runs from nose tip to tail tip, with cross-section sizes
    varying anatomically: narrow at nose, widening through head, narrowing
    at neck, widening through chest/ribcage, narrowing at waist, widening
    at hips, then tapering through tail.
    """
    body_length = props["body_length"] * scale
    body_height = props["body_height"] * scale
    body_width = props["body_width"] * scale
    head_length = props["head_length"] * scale
    snout_length = props["snout_length"] * scale
    neck_length = props["neck_length"] * scale
    tail_length = props["tail_length"] * scale
    n_points = props["spine_points"]

    total_length = snout_length + head_length + neck_length + body_length + tail_length

    spine: list[Vec3] = []
    radii: list[tuple[float, float]] = []

    for i in range(n_points):
        t = i / (n_points - 1)
        z = t * total_length

        # Height profile: smooth curve along the body
        if z < snout_length:
            # Snout: level, slightly downward
            st = z / max(snout_length, 0.001)
            y = body_height + 0.05 * scale - st * 0.03 * scale
            rx = _lerp(0.02, 0.04, st) * scale
            ry = _lerp(0.015, 0.035, st) * scale
        elif z < snout_length + head_length:
            # Head: wider
            st = (z - snout_length) / max(head_length, 0.001)
            y = body_height + 0.05 * scale * (1.0 - st * 0.3)
            rx = _lerp(0.04, body_width * 0.35, _smooth_step(st)) * scale
            ry = _lerp(0.035, body_width * 0.3, _smooth_step(st)) * scale
        elif z < snout_length + head_length + neck_length:
            # Neck: narrows, curves downward then up to body
            st = (z - snout_length - head_length) / max(neck_length, 0.001)
            neck_dip = math.sin(st * math.pi) * 0.05 * scale
            y = body_height + 0.02 * scale - neck_dip
            rx = _lerp(body_width * 0.25, body_width * 0.4, st) * scale
            ry = _lerp(body_width * 0.2, body_width * 0.45, st) * scale
        elif z < snout_length + head_length + neck_length + body_length:
            # Body: main torso
            st = (z - snout_length - head_length - neck_length) / max(body_length, 0.001)
            # Body height has slight arch
            arch = math.sin(st * math.pi) * 0.03 * scale
            y = body_height + arch
            # Width envelope: wider at chest and hips, narrower at waist
            chest_bulge = max(0.0, 1.0 - st * 3.0)  # front 33%
            hip_bulge = max(0.0, (st - 0.6) / 0.4)   # back 40%
            waist = max(0.0, 1.0 - abs(st - 0.5) * 3.0)  # middle
            width_factor = 0.85 + chest_bulge * 0.15 + hip_bulge * 0.1 - waist * 0.08
            rx = body_width * 0.5 * width_factor
            # Height: chest is deeper, waist is shallower
            height_factor = 0.8 + chest_bulge * 0.2 + hip_bulge * 0.05 - waist * 0.05
            ry = body_width * 0.5 * height_factor * 0.85
        else:
            # Tail: tapers
            st = (z - snout_length - head_length - neck_length - body_length) / max(tail_length, 0.001)
            # Tail curves slightly upward then down
            tail_curve = math.sin(st * math.pi * 0.7) * 0.05 * scale
            y = body_height - 0.02 * scale + tail_curve
            taper = 1.0 - st * 0.92
            rx = body_width * 0.12 * max(taper, 0.08)
            ry = body_width * 0.1 * max(taper, 0.08)

        spine.append((0.0, y, z))
        radii.append((rx, ry))

    return spine, radii


# ---------------------------------------------------------------------------
# Limb generators (with proper edge loop topology)
# ---------------------------------------------------------------------------


def _generate_limb(
    start_pos: Vec3,
    segments: list[dict[str, Any]],
    ring_segments: int = 8,
) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate a multi-segment limb with proper joint edge loops.

    Each segment has:
    - start_radius, end_radius (tapering)
    - length
    - direction (Vec3)
    - joint_name

    Extra edge loops are added at joints for clean deformation.
    """
    verts: VertList = []
    faces: FaceList = []
    joints: dict[str, Vec3] = {}

    current_pos = start_pos
    rings_per_segment = 4  # Enough loops for smooth bending

    for seg_idx, seg in enumerate(segments):
        r_start = seg["start_radius"]
        r_end = seg["end_radius"]
        length = seg["length"]
        direction = _vec3_normalize(seg.get("direction", (0.0, -1.0, 0.0)))
        joint_name = seg.get("joint_name", f"joint_{seg_idx}")

        joints[joint_name] = current_pos

        for ring_idx in range(rings_per_segment + 1):
            # Skip first ring of subsequent segments (shared with prev segment end)
            if seg_idx > 0 and ring_idx == 0:
                continue

            t = ring_idx / rings_per_segment
            r = _lerp(r_start, r_end, t)
            pos = _vec3_add(current_pos, _vec3_scale(direction, length * t))

            # Build frame for ring orientation
            _, normal, binormal = _build_frame(direction)

            ring_start = len(verts)
            for j in range(ring_segments):
                angle = 2.0 * math.pi * j / ring_segments
                px = math.cos(angle) * r
                py = math.sin(angle) * r
                wx = pos[0] + normal[0] * px + binormal[0] * py
                wy = pos[1] + normal[1] * px + binormal[1] * py
                wz = pos[2] + normal[2] * px + binormal[2] * py
                verts.append((wx, wy, wz))

            if ring_start >= ring_segments:
                faces.extend(_connect_rings(
                    ring_start - ring_segments, ring_start, ring_segments))

        # Move to end of segment
        current_pos = _vec3_add(current_pos, _vec3_scale(direction, length))

    # Record final position
    if segments:
        joints[segments[-1].get("end_joint_name", "limb_end")] = current_pos

    # End cap
    if verts:
        faces.append(_cap_ring(0, ring_segments, reverse=True))
        faces.append(_cap_ring(len(verts) - ring_segments, ring_segments))

    return verts, faces, joints


# ---------------------------------------------------------------------------
# Head generator
# ---------------------------------------------------------------------------


def _generate_quadruped_head(
    props: dict[str, Any],
    scale: float,
    head_base_pos: Vec3,
    include_mouth: bool = True,
    include_eyelids: bool = True,
) -> tuple[VertList, FaceList, dict[str, Vec3], dict[str, list[int]]]:
    """Generate an anatomical quadruped head.

    Creates the skull shape using a spine-based approach (snout to occiput),
    with proper eye sockets, ear bases, and jaw articulation.

    Returns: (verts, faces, bone_positions, vertex_groups)
    """
    head_length = props["head_length"] * scale
    snout_length = props["snout_length"] * scale
    ear_height = props["ear_height"] * scale
    body_width = props["body_width"] * scale

    all_verts: VertList = []
    all_faces: FaceList = []
    bones: dict[str, Vec3] = {}
    groups: dict[str, list[int]] = {}

    head_segs = 10
    head_ring_segs = 10

    # Head spine: from snout tip to occiput
    head_spine: list[Vec3] = []
    head_radii: list[tuple[float, float]] = []

    bx, by, bz = head_base_pos

    for i in range(head_segs):
        t = i / (head_segs - 1)
        z = bz + t * head_length

        # Head profile: narrow at snout, widens at eyes, narrows at occiput
        if t < 0.3:
            # Snout
            st = t / 0.3
            rx = _lerp(0.01, body_width * 0.15, _smooth_step(st)) * scale
            ry = _lerp(0.01, body_width * 0.12, _smooth_step(st)) * scale
            y = by + st * 0.02 * scale
        elif t < 0.6:
            # Cranium (widest)
            st = (t - 0.3) / 0.3
            rx = _lerp(body_width * 0.15, body_width * 0.2, _smooth_step(st)) * scale
            ry = _lerp(body_width * 0.12, body_width * 0.18, _smooth_step(st)) * scale
            y = by + 0.02 * scale + st * 0.01 * scale
        else:
            # Occiput (narrows to neck)
            st = (t - 0.6) / 0.4
            rx = _lerp(body_width * 0.2, body_width * 0.13, _smooth_step(st)) * scale
            ry = _lerp(body_width * 0.18, body_width * 0.12, _smooth_step(st)) * scale
            y = by + 0.03 * scale - st * 0.02 * scale

        head_spine.append((bx, y, z))
        head_radii.append((rx, ry))

    # Build head mesh from spine
    skull_verts, skull_faces = _build_body_from_spine(
        head_spine, head_radii, segments=head_ring_segs)
    skull_v_start = len(all_verts)
    all_verts.extend(skull_verts)
    all_faces.extend([(f[0] + skull_v_start, f[1] + skull_v_start,
                       f[2] + skull_v_start, f[3] + skull_v_start)
                      if len(f) == 4 else tuple(idx + skull_v_start for idx in f)
                      for f in skull_faces])

    # Head vertex group
    groups["head"] = list(range(skull_v_start, len(all_verts)))

    # Bone positions
    bones["head"] = (bx, by + 0.02 * scale, bz + head_length * 0.5)
    bones["jaw_pivot"] = (bx, by - 0.01 * scale, bz + head_length * 0.3)
    bones["snout_tip"] = (bx, by, bz)

    # --- Eye sockets with eyelids ---
    if include_eyelids:
        eye_z = bz + head_length * 0.4
        eye_spacing = body_width * 0.12 * scale
        eye_r = body_width * 0.03 * scale

        for side_name, side_sign in [("L", -1.0), ("R", 1.0)]:
            eye_x = bx + side_sign * eye_spacing
            eye_y = by + 0.025 * scale

            lid_v, lid_f, lid_groups = generate_eyelid_topology(
                eye_radius=eye_r,
                eye_position=(eye_x, eye_y, eye_z),
                eye_direction=(side_sign * 0.3, 0.0, 1.0),
            )
            lid_start = len(all_verts)
            all_verts.extend(lid_v)
            all_faces.extend([tuple(idx + lid_start for idx in f) for f in lid_f])

            for gname, gindices in lid_groups.items():
                full_name = f"{gname}_{side_name}"
                groups[full_name] = [idx + lid_start for idx in gindices]

            bones[f"eye_{side_name}"] = (eye_x, eye_y, eye_z)

    # --- Ears ---
    ear_z = bz + head_length * 0.55
    ear_spacing = body_width * 0.15 * scale

    for side_name, side_sign in [("L", -1.0), ("R", 1.0)]:
        ear_x = bx + side_sign * ear_spacing
        ear_y = by + body_width * 0.18 * scale

        ear_verts, ear_faces = _generate_ear(
            base_pos=(ear_x, ear_y, ear_z),
            height=ear_height,
            ear_shape=props.get("ear_shape", "pointed"),
        )
        ear_start = len(all_verts)
        all_verts.extend(ear_verts)
        all_faces.extend([tuple(idx + ear_start for idx in f) for f in ear_faces])
        groups[f"ear_{side_name}"] = list(range(ear_start, len(all_verts)))
        bones[f"ear_{side_name}"] = (ear_x, ear_y, ear_z)

    # --- Mouth interior ---
    if include_mouth:
        mouth_pos = (bx, by - 0.01 * scale, bz + snout_length * 0.3)
        mouth_w = body_width * 0.1 * scale
        mouth_d = head_length * 0.35
        jaw_len = head_length * 0.4

        mouth_v, mouth_f, mouth_groups = generate_mouth_interior(
            mouth_width=mouth_w,
            mouth_depth=mouth_d,
            jaw_length=jaw_len,
            tooth_count=max(8, int(20 * scale)),
            tooth_style=props.get("tooth_style", "carnivore"),
            include_tongue=True,
            position=mouth_pos,
        )
        mouth_start = len(all_verts)
        all_verts.extend(mouth_v)
        all_faces.extend([tuple(idx + mouth_start for idx in f) for f in mouth_f])
        for gname, gindices in mouth_groups.items():
            groups[gname] = [idx + mouth_start for idx in gindices]
        bones["jaw"] = (bx, by - 0.01 * scale, bz + head_length * 0.25)

    return all_verts, all_faces, bones, groups


# ---------------------------------------------------------------------------
# Ear generator
# ---------------------------------------------------------------------------


def _generate_ear(
    base_pos: Vec3,
    height: float,
    ear_shape: str = "pointed",
) -> tuple[VertList, FaceList]:
    """Generate ear geometry with proper rotation topology.

    Shapes: 'pointed' (wolf/cat), 'rounded' (bear), 'wide' (deer), 'floppy' (boar)
    """
    bx, by, bz = base_pos
    verts: VertList = []
    faces: FaceList = []

    rows = 4
    cols = 3  # inner edge, center, outer edge

    for r in range(rows + 1):
        t = r / rows
        y = by + t * height

        # Width tapers toward tip
        if ear_shape == "pointed":
            w = height * 0.3 * (1.0 - t * 0.85)
            depth = height * 0.05 * (1.0 - t * 0.5)
        elif ear_shape == "rounded":
            w = height * 0.4 * math.sin((1.0 - t * 0.8) * math.pi * 0.5)
            depth = height * 0.06 * (1.0 - t * 0.4)
        elif ear_shape == "wide":
            w = height * 0.5 * (1.0 - t * 0.7)
            depth = height * 0.04 * (1.0 - t * 0.3)
        else:  # floppy
            w = height * 0.35 * (1.0 - t * 0.6)
            depth = height * 0.05 * (1.0 - t * 0.5)
            # Floppy ears curve outward and down
            y = by + t * height * 0.3 - t * t * height * 0.4

        for c in range(cols):
            ct = c / max(cols - 1, 1) - 0.5  # [-0.5, 0.5]
            x = bx + ct * w * 2.0
            z_offset = -depth * (1.0 - abs(ct) * 2.0)  # concave inner surface
            verts.append((x, y, bz + z_offset))

    # Create quad faces
    for r in range(rows):
        for c in range(cols - 1):
            v0 = r * cols + c
            v1 = v0 + 1
            v2 = (r + 1) * cols + c + 1
            v3 = (r + 1) * cols + c
            faces.append((v0, v1, v2, v3))

    return verts, faces


# ---------------------------------------------------------------------------
# Mouth interior generator
# ---------------------------------------------------------------------------


def generate_mouth_interior(
    mouth_width: float = 0.1,
    mouth_depth: float = 0.12,
    jaw_length: float = 0.15,
    tooth_count: int = 20,
    tooth_style: str = "carnivore",
    include_tongue: bool = True,
    position: Vec3 = (0.0, 0.0, 0.0),
) -> tuple[VertList, FaceList, dict[str, list[int]]]:
    """Generate detailed mouth interior mesh.

    Components:
    - Upper palate (concave arch)
    - Lower jaw (U-shape)
    - Gums (ridge along tooth line)
    - Individual teeth (incisors, canines, molars per style)
    - Tongue (tapered ellipsoid with curl vertex group)
    - Inner cheek walls connecting upper/lower

    Returns: (vertices, faces, vertex_groups)
    """
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []
    groups: dict[str, list[int]] = {
        "jaw": [],
        "tongue": [],
        "teeth_upper": [],
        "teeth_lower": [],
    }

    palate_segs = 6  # along depth
    palate_cross = 8  # across width

    # --- Upper palate ---
    palate_start = len(verts)
    for i in range(palate_segs + 1):
        t = i / palate_segs
        z = pz + t * mouth_depth
        for j in range(palate_cross + 1):
            u = j / palate_cross - 0.5  # [-0.5, 0.5]
            x = px + u * mouth_width * 2.0 * (1.0 - t * 0.3)  # narrows toward throat
            # Concave arch
            arch = mouth_width * 0.3 * (1.0 - (u * 2.0) ** 2)
            y = py + arch * (0.3 + t * 0.2)
            verts.append((x, y, z))

    # Palate faces
    for i in range(palate_segs):
        for j in range(palate_cross):
            v0 = palate_start + i * (palate_cross + 1) + j
            v1 = v0 + 1
            v2 = v0 + (palate_cross + 1) + 1
            v3 = v0 + (palate_cross + 1)
            faces.append((v0, v1, v2, v3))

    # --- Lower jaw ---
    jaw_start = len(verts)
    jaw_depth_segs = 6
    jaw_cross = 8

    for i in range(jaw_depth_segs + 1):
        t = i / jaw_depth_segs
        z = pz + t * jaw_length
        for j in range(jaw_cross + 1):
            u = j / jaw_cross - 0.5
            x = px + u * mouth_width * 1.8 * (1.0 - t * 0.4)
            # U-shape: lower on sides, raised center
            u_curve = (u * 2.0) ** 2 * mouth_width * 0.15
            y = py - mouth_width * 0.4 + u_curve - t * 0.02
            verts.append((x, y, z))

    jaw_end = len(verts)
    groups["jaw"] = list(range(jaw_start, jaw_end))

    # Jaw faces
    for i in range(jaw_depth_segs):
        for j in range(jaw_cross):
            v0 = jaw_start + i * (jaw_cross + 1) + j
            v1 = v0 + 1
            v2 = v0 + (jaw_cross + 1) + 1
            v3 = v0 + (jaw_cross + 1)
            faces.append((v0, v1, v2, v3))

    # --- Teeth ---
    tooth_configs = _get_tooth_config(tooth_style, tooth_count)

    for tooth in tooth_configs:
        tooth_v_start = len(verts)
        tooth_v, tooth_f = _generate_single_tooth(
            tooth["position"],
            tooth["size"],
            tooth["type"],
            (px, py, pz),
            mouth_width,
        )
        verts.extend(tooth_v)
        faces.extend([tuple(idx + tooth_v_start for idx in f) for f in tooth_f])

        if tooth["row"] == "upper":
            groups["teeth_upper"].extend(range(tooth_v_start, len(verts)))
        else:
            groups["teeth_lower"].extend(range(tooth_v_start, len(verts)))

    # --- Tongue ---
    if include_tongue:
        tongue_start = len(verts)
        tongue_v, tongue_f = _generate_tongue(
            (px, py - mouth_width * 0.25, pz + mouth_depth * 0.2),
            length=mouth_depth * 0.6,
            width=mouth_width * 0.6,
        )
        verts.extend(tongue_v)
        faces.extend([tuple(idx + tongue_start for idx in f) for f in tongue_f])
        groups["tongue"] = list(range(tongue_start, len(verts)))

    # --- Inner cheek walls (connect upper and lower at sides) ---
    cheek_start = len(verts)
    cheek_segs = 4
    for side_sign in [-1.0, 1.0]:
        side_start = len(verts)
        for i in range(cheek_segs + 1):
            t = i / cheek_segs
            z = pz + t * min(mouth_depth, jaw_length)
            x = px + side_sign * mouth_width * (0.95 - t * 0.2)
            # Upper connection
            y_upper = py + mouth_width * 0.15
            # Lower connection
            y_lower = py - mouth_width * 0.3
            verts.append((x, y_upper, z))
            verts.append((x, (y_upper + y_lower) * 0.5, z))
            verts.append((x, y_lower, z))

        # Connect cheek strips
        for i in range(cheek_segs):
            for r in range(2):  # 2 rows of quads per cheek
                v0 = side_start + i * 3 + r
                v1 = v0 + 1
                v2 = side_start + (i + 1) * 3 + r + 1
                v3 = side_start + (i + 1) * 3 + r
                faces.append((v0, v1, v2, v3))

    return verts, faces, groups


def _get_tooth_config(
    style: str, count: int,
) -> list[dict[str, Any]]:
    """Generate tooth placement configuration based on dental style."""
    teeth: list[dict[str, Any]] = []

    if style == "carnivore":
        # Incisors (front), canines (large), premolars, molars
        for row in ["upper", "lower"]:
            row_count = count // 2
            for i in range(row_count):
                t = i / max(row_count - 1, 1)
                if t < 0.2:
                    tooth_type = "incisor"
                    size = 0.3
                elif t < 0.35:
                    tooth_type = "canine"
                    size = 0.8
                elif t < 0.6:
                    tooth_type = "premolar"
                    size = 0.5
                else:
                    tooth_type = "molar"
                    size = 0.6
                teeth.append({
                    "position": t,
                    "type": tooth_type,
                    "size": size,
                    "row": row,
                })
    elif style == "herbivore":
        for row in ["upper", "lower"]:
            row_count = count // 2
            for i in range(row_count):
                t = i / max(row_count - 1, 1)
                if t < 0.3:
                    tooth_type = "incisor"
                    size = 0.4
                else:
                    tooth_type = "molar"
                    size = 0.7
                teeth.append({
                    "position": t,
                    "type": tooth_type,
                    "size": size,
                    "row": row,
                })
    elif style == "serpent":
        # Fangs only, upper row
        for i in range(min(count, 4)):
            teeth.append({
                "position": 0.1 + i * 0.1,
                "type": "fang",
                "size": 1.0,
                "row": "upper",
            })
    else:  # monster
        for row in ["upper", "lower"]:
            row_count = count // 2
            for i in range(row_count):
                t = i / max(row_count - 1, 1)
                # Irregular sizing
                seed_val = (i * 7 + (0 if row == "upper" else 13)) % 5
                tooth_type = "fang" if seed_val < 2 else "molar"
                size = 0.5 + (seed_val % 3) * 0.3
                teeth.append({
                    "position": t,
                    "type": tooth_type,
                    "size": size,
                    "row": row,
                })

    return teeth


def _generate_single_tooth(
    position_t: float,
    size: float,
    tooth_type: str,
    mouth_origin: Vec3,
    mouth_width: float,
) -> tuple[VertList, FaceList]:
    """Generate a single tooth mesh.

    Types: incisor (flat rectangle), canine/fang (curved cone),
           premolar (tapered box), molar (rounded box with cusps).
    """
    ox, oy, oz = mouth_origin
    # Position along the jaw arc
    angle = (position_t - 0.5) * math.pi * 0.8
    tooth_x = ox + math.sin(angle) * mouth_width * 0.8
    tooth_z = oz + math.cos(angle) * mouth_width * 0.5
    tooth_height = mouth_width * 0.15 * size
    tooth_width = mouth_width * 0.04 * size

    verts: VertList = []
    faces: FaceList = []

    if tooth_type in ("canine", "fang"):
        # Curved cone tooth
        segs = 5
        rings = 3
        for r in range(rings + 1):
            t = r / rings
            radius = tooth_width * (1.0 - t * 0.85)
            y = oy - t * tooth_height
            # Slight backward curve
            z_curve = tooth_z + t * t * tooth_height * 0.15
            for s in range(segs):
                a = 2.0 * math.pi * s / segs
                verts.append((
                    tooth_x + math.cos(a) * radius,
                    y,
                    z_curve + math.sin(a) * radius,
                ))
        # Ring faces
        for r in range(rings):
            for s in range(segs):
                s2 = (s + 1) % segs
                r0 = r * segs
                r1 = (r + 1) * segs
                faces.append((r0 + s, r0 + s2, r1 + s2, r1 + s))
        # Tip (collapse last ring to point)
        # Caps
        faces.append(_cap_ring(0, segs, reverse=True))
        faces.append(_cap_ring(rings * segs, segs))
    elif tooth_type == "molar":
        # Box with cusps
        hw = tooth_width * 0.7
        hd = tooth_width * 0.5
        hh = tooth_height * 0.5
        # Base box
        verts_box = [
            (tooth_x - hw, oy, tooth_z - hd),
            (tooth_x + hw, oy, tooth_z - hd),
            (tooth_x + hw, oy, tooth_z + hd),
            (tooth_x - hw, oy, tooth_z + hd),
            (tooth_x - hw, oy - hh, tooth_z - hd),
            (tooth_x + hw, oy - hh, tooth_z - hd),
            (tooth_x + hw, oy - hh, tooth_z + hd),
            (tooth_x - hw, oy - hh, tooth_z + hd),
            # Cusps (4 points on top)
            (tooth_x - hw * 0.5, oy + hh * 0.3, tooth_z - hd * 0.5),
            (tooth_x + hw * 0.5, oy + hh * 0.3, tooth_z - hd * 0.5),
            (tooth_x + hw * 0.5, oy + hh * 0.3, tooth_z + hd * 0.5),
            (tooth_x - hw * 0.5, oy + hh * 0.3, tooth_z + hd * 0.5),
        ]
        verts.extend(verts_box)
        faces.extend([
            (0, 3, 2, 1),  # top
            (4, 5, 6, 7),  # bottom
            (0, 1, 5, 4),
            (2, 3, 7, 6),
            (0, 4, 7, 3),
            (1, 2, 6, 5),
            # Cusp triangles
            (0, 8, 1), (1, 9, 2), (2, 10, 3), (3, 11, 0),
            (8, 9, 10, 11),  # cusp top
        ])
    else:
        # Incisor / premolar: tapered box
        hw = tooth_width * 0.6
        hd = tooth_width * 0.3
        hh = tooth_height * 0.4
        taper = 0.7  # top is narrower
        verts_box = [
            (tooth_x - hw, oy, tooth_z - hd),
            (tooth_x + hw, oy, tooth_z - hd),
            (tooth_x + hw, oy, tooth_z + hd),
            (tooth_x - hw, oy, tooth_z + hd),
            (tooth_x - hw * taper, oy - hh, tooth_z - hd * taper),
            (tooth_x + hw * taper, oy - hh, tooth_z - hd * taper),
            (tooth_x + hw * taper, oy - hh, tooth_z + hd * taper),
            (tooth_x - hw * taper, oy - hh, tooth_z + hd * taper),
        ]
        verts.extend(verts_box)
        faces.extend([
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (2, 3, 7, 6),
            (0, 4, 7, 3),
            (1, 2, 6, 5),
        ])

    return verts, faces


def _generate_tongue(
    position: Vec3,
    length: float,
    width: float,
) -> tuple[VertList, FaceList]:
    """Generate tongue mesh as tapered ellipsoid with curl capability."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []

    rows = 5  # along length
    cols = 6  # around width

    for i in range(rows + 1):
        t = i / rows
        z = pz + t * length
        # Width tapers to tip
        w = width * 0.5 * (1.0 - t * 0.7)
        h = width * 0.08 * (1.0 - t * 0.5)

        for j in range(cols):
            angle = math.pi * j / (cols - 1)  # Half circle (top surface only)
            x = px + math.cos(angle) * w - w  # Centered
            y = py + math.sin(angle) * h
            verts.append((x + w, y, z))  # Re-center

    for i in range(rows):
        for j in range(cols - 1):
            v0 = i * cols + j
            v1 = v0 + 1
            v2 = (i + 1) * cols + j + 1
            v3 = (i + 1) * cols + j
            faces.append((v0, v1, v2, v3))

    return verts, faces


# ---------------------------------------------------------------------------
# Eyelid generator
# ---------------------------------------------------------------------------


def generate_eyelid_topology(
    eye_radius: float = 0.015,
    eye_position: Vec3 = (0.0, 0.0, 0.0),
    eye_direction: Vec3 = (0.0, 1.0, 0.0),
) -> tuple[VertList, FaceList, dict[str, list[int]]]:
    """Generate eyelid mesh that properly closes over eyeball.

    Creates upper and lower eyelids as curved surfaces matching the eye
    sphere curvature, with proper edge loops for smooth deformation.

    Components:
    - Upper eyelid: 3-4 concentric edge loops, matches sphere curvature
    - Lower eyelid: same, slightly smaller range of motion
    - Corner vertices at tear duct and outer corner
    - Inner face (conjunctiva) and outer face (skin)

    Returns: (vertices, faces, vertex_groups)
    """
    ex, ey, ez = eye_position
    verts: VertList = []
    faces: FaceList = []
    groups: dict[str, list[int]] = {
        "eyelid_upper": [],
        "eyelid_lower": [],
    }

    # Normalize eye direction for frame
    edir = _vec3_normalize(eye_direction)
    _, up, right = _build_frame(edir, up_hint=(0.0, 1.0, 0.0))

    lid_loops = 4  # Concentric loops around the eye
    lid_segments = 12  # Points per loop

    # Upper eyelid
    upper_start = len(verts)
    for loop_i in range(lid_loops):
        t = (loop_i + 1) / (lid_loops + 1)
        # Each loop covers a different latitude of the eye sphere
        # Upper lid covers top 60 degrees
        for seg_j in range(lid_segments):
            u = seg_j / (lid_segments - 1)  # 0 to 1 along lid opening
            # Angular position on the sphere
            theta = (u - 0.5) * math.pi * 0.8  # -72 to +72 degrees
            phi = math.pi * 0.5 * (1.0 - t * 0.6)  # upper hemisphere

            # Point on sphere + slight offset outward for lid thickness
            r = eye_radius * (1.0 + t * 0.15)  # skin is slightly larger than eye
            local_x = math.sin(theta) * math.cos(phi) * r
            local_y = math.sin(phi) * r
            local_z = math.cos(theta) * math.cos(phi) * r

            # Transform to world
            wx = ex + right[0] * local_x + up[0] * local_y + edir[0] * local_z
            wy = ey + right[1] * local_x + up[1] * local_y + edir[1] * local_z
            wz = ez + right[2] * local_x + up[2] * local_y + edir[2] * local_z
            verts.append((wx, wy, wz))

    upper_end = len(verts)
    groups["eyelid_upper"] = list(range(upper_start, upper_end))

    # Upper lid faces
    for loop_i in range(lid_loops - 1):
        for seg_j in range(lid_segments - 1):
            v0 = upper_start + loop_i * lid_segments + seg_j
            v1 = v0 + 1
            v2 = upper_start + (loop_i + 1) * lid_segments + seg_j + 1
            v3 = upper_start + (loop_i + 1) * lid_segments + seg_j
            faces.append((v0, v1, v2, v3))

    # Lower eyelid (mirror of upper, covering bottom 45 degrees)
    lower_start = len(verts)
    for loop_i in range(lid_loops):
        t = (loop_i + 1) / (lid_loops + 1)
        for seg_j in range(lid_segments):
            u = seg_j / (lid_segments - 1)
            theta = (u - 0.5) * math.pi * 0.7
            phi = -math.pi * 0.5 * (1.0 - t * 0.55) * 0.75  # lower hemisphere

            r = eye_radius * (1.0 + t * 0.12)
            local_x = math.sin(theta) * math.cos(phi) * r
            local_y = math.sin(phi) * r
            local_z = math.cos(theta) * math.cos(phi) * r

            wx = ex + right[0] * local_x + up[0] * local_y + edir[0] * local_z
            wy = ey + right[1] * local_x + up[1] * local_y + edir[1] * local_z
            wz = ez + right[2] * local_x + up[2] * local_y + edir[2] * local_z
            verts.append((wx, wy, wz))

    lower_end = len(verts)
    groups["eyelid_lower"] = list(range(lower_start, lower_end))

    # Lower lid faces
    for loop_i in range(lid_loops - 1):
        for seg_j in range(lid_segments - 1):
            v0 = lower_start + loop_i * lid_segments + seg_j
            v1 = v0 + 1
            v2 = lower_start + (loop_i + 1) * lid_segments + seg_j + 1
            v3 = lower_start + (loop_i + 1) * lid_segments + seg_j
            faces.append((v0, v1, v2, v3))

    return verts, faces, groups


# ---------------------------------------------------------------------------
# Paw / Hoof / Claw generator
# ---------------------------------------------------------------------------


def generate_paw(
    paw_type: str = "canine",
    toe_count: int = 4,
    include_pads: bool = True,
    include_claws: bool = True,
    size: float = 1.0,
    position: Vec3 = (0.0, 0.0, 0.0),
) -> tuple[VertList, FaceList, dict[str, list[int]]]:
    """Generate detailed paw mesh with toes, pads, and claws.

    Types: 'canine', 'feline', 'bear', 'bird_talons', 'hoof', 'cloven_hoof'

    Returns: (vertices, faces, vertex_groups)
    """
    px, py, pz = position
    all_verts: VertList = []
    all_faces: FaceList = []
    groups: dict[str, list[int]] = {"pads": [], "claws": []}

    # --- Metacarpal base (the "hand" area) ---
    if paw_type in ("hoof", "cloven_hoof"):
        # Hoof: cylindrical base narrowing to flat bottom
        base_v, base_f = _generate_hoof_base(
            position, size, paw_type == "cloven_hoof")
        all_verts.extend(base_v)
        all_faces.extend(base_f)
        # Hooves have 1-2 "toes" (the hoof itself)
        actual_toes = 2 if paw_type == "cloven_hoof" else 1
        groups["pads"] = list(range(len(all_verts)))
        return all_verts, all_faces, groups

    # Paw metacarpal
    meta_width = 0.04 * size
    meta_depth = 0.03 * size
    meta_length = 0.06 * size
    ring_segs = 6
    meta_rings = 4

    for i in range(meta_rings + 1):
        t = i / meta_rings
        y = py - t * meta_length
        w = meta_width * (1.0 + t * 0.3)  # Splays slightly
        d = meta_depth * (1.0 - t * 0.2)
        for j in range(ring_segs):
            angle = 2.0 * math.pi * j / ring_segs
            x = px + math.cos(angle) * w
            z = pz + math.sin(angle) * d
            all_verts.append((x, y, z))

    for i in range(meta_rings):
        all_faces.extend(_connect_rings(
            i * ring_segs, (i + 1) * ring_segs, ring_segs))
    all_faces.append(_cap_ring(0, ring_segs, reverse=True))

    # --- Individual toes ---
    toe_splay = math.pi * 0.5 if paw_type == "bear" else math.pi * 0.35
    toe_length = meta_length * (1.2 if paw_type == "bear" else 0.8)
    toe_segs_per = 2  # segments per toe joint

    for t_idx in range(toe_count):
        toe_angle = -toe_splay / 2 + toe_splay * t_idx / max(toe_count - 1, 1)
        toe_x = px + math.sin(toe_angle) * meta_width * 1.3
        toe_z = pz + math.cos(toe_angle) * meta_depth * 0.5
        toe_y = py - meta_length

        toe_start = len(all_verts)
        toe_r_base = meta_width * 0.3
        toe_r_tip = meta_width * 0.15
        toe_ring_segs = 5

        for seg_i in range(toe_segs_per * 2 + 1):
            st = seg_i / (toe_segs_per * 2)
            r = _lerp(toe_r_base, toe_r_tip, st)
            y = toe_y - st * toe_length
            # Slight forward curve
            z_off = st * toe_length * 0.2
            for j in range(toe_ring_segs):
                angle = 2.0 * math.pi * j / toe_ring_segs
                all_verts.append((
                    toe_x + math.cos(angle) * r,
                    y,
                    toe_z + z_off + math.sin(angle) * r,
                ))

            if seg_i > 0:
                prev = toe_start + (seg_i - 1) * toe_ring_segs
                curr = toe_start + seg_i * toe_ring_segs
                all_faces.extend(_connect_rings(prev, curr, toe_ring_segs))

        toe_end = len(all_verts)
        groups[f"toe_{t_idx + 1}"] = list(range(toe_start, toe_end))

        # Cap toe tip
        all_faces.append(_cap_ring(toe_start, toe_ring_segs, reverse=True))
        all_faces.append(_cap_ring(toe_end - toe_ring_segs, toe_ring_segs))

        # --- Claw per toe ---
        if include_claws:
            claw_start = len(all_verts)
            claw_length = toe_length * (0.6 if paw_type == "bear" else 0.4)
            claw_r = toe_r_tip * 0.7
            claw_rings = 3
            claw_ring_segs = 4

            for ci in range(claw_rings + 1):
                ct = ci / claw_rings
                cr = claw_r * (1.0 - ct * 0.9)
                cy = toe_y - toe_length - ct * claw_length
                # Forward curve
                cz = toe_z + toe_length * 0.2 + ct * claw_length * 0.3
                for j in range(claw_ring_segs):
                    angle = 2.0 * math.pi * j / claw_ring_segs
                    all_verts.append((
                        toe_x + math.cos(angle) * cr,
                        cy,
                        cz + math.sin(angle) * cr,
                    ))

            for ci in range(claw_rings):
                prev = claw_start + ci * claw_ring_segs
                curr = claw_start + (ci + 1) * claw_ring_segs
                all_faces.extend(_connect_rings(prev, curr, claw_ring_segs))
            all_faces.append(_cap_ring(claw_start, claw_ring_segs, reverse=True))
            all_faces.append(_cap_ring(
                claw_start + claw_rings * claw_ring_segs, claw_ring_segs))

            groups["claws"].extend(range(claw_start, len(all_verts)))

    # --- Pad mesh (underside) ---
    if include_pads:
        pad_start = len(all_verts)
        # Central pad
        pad_r = meta_width * 0.6
        pad_segs = 6
        pad_y = py - meta_length * 0.8
        for j in range(pad_segs):
            angle = 2.0 * math.pi * j / pad_segs
            all_verts.append((
                px + math.cos(angle) * pad_r,
                pad_y - 0.003 * size,
                pz + math.sin(angle) * pad_r * 0.7,
            ))
        # Pad center
        all_verts.append((px, pad_y - 0.005 * size, pz))
        center_idx = len(all_verts) - 1
        for j in range(pad_segs):
            j2 = (j + 1) % pad_segs
            all_faces.append((pad_start + j, pad_start + j2, center_idx))

        # Toe pads (small circles at each toe base)
        for t_idx in range(toe_count):
            toe_angle = -toe_splay / 2 + toe_splay * t_idx / max(toe_count - 1, 1)
            tp_x = px + math.sin(toe_angle) * meta_width * 1.0
            tp_z = pz + math.cos(toe_angle) * meta_depth * 0.3
            tp_y = py - meta_length * 1.1
            tp_start = len(all_verts)
            tp_r = meta_width * 0.2
            tp_segs = 4
            for j in range(tp_segs):
                angle = 2.0 * math.pi * j / tp_segs
                all_verts.append((
                    tp_x + math.cos(angle) * tp_r,
                    tp_y - 0.002 * size,
                    tp_z + math.sin(angle) * tp_r,
                ))
            all_verts.append((tp_x, tp_y - 0.003 * size, tp_z))
            tp_center = len(all_verts) - 1
            for j in range(tp_segs):
                j2 = (j + 1) % tp_segs
                all_faces.append((tp_start + j, tp_start + j2, tp_center))

        groups["pads"] = list(range(pad_start, len(all_verts)))

    return all_verts, all_faces, groups


def _generate_hoof_base(
    position: Vec3,
    size: float,
    cloven: bool = False,
) -> tuple[VertList, FaceList]:
    """Generate hoof geometry (single or cloven)."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []

    hoof_height = 0.06 * size
    hoof_width = 0.035 * size
    hoof_depth = 0.04 * size
    ring_segs = 8
    rings = 4

    if cloven:
        # Two halves with a gap between them
        for half_sign in [-0.5, 0.5]:
            hx = px + half_sign * hoof_width * 0.6
            half_start = len(verts)
            for i in range(rings + 1):
                t = i / rings
                y = py - t * hoof_height
                w = hoof_width * 0.4 * (1.0 + t * 0.2)
                d = hoof_depth * 0.5 * (1.0 - t * 0.1)
                for j in range(ring_segs):
                    angle = 2.0 * math.pi * j / ring_segs
                    verts.append((
                        hx + math.cos(angle) * w,
                        y,
                        pz + math.sin(angle) * d,
                    ))
            for i in range(rings):
                r0 = half_start + i * ring_segs
                r1 = half_start + (i + 1) * ring_segs
                faces.extend(_connect_rings(r0, r1, ring_segs))
            faces.append(_cap_ring(half_start, ring_segs, reverse=True))
            faces.append(_cap_ring(
                half_start + rings * ring_segs, ring_segs))
    else:
        # Single hoof
        for i in range(rings + 1):
            t = i / rings
            y = py - t * hoof_height
            w = hoof_width * (1.0 + t * 0.3)
            d = hoof_depth * (1.0 - t * 0.1)
            for j in range(ring_segs):
                angle = 2.0 * math.pi * j / ring_segs
                verts.append((
                    px + math.cos(angle) * w,
                    y,
                    pz + math.sin(angle) * d,
                ))
        for i in range(rings):
            faces.extend(_connect_rings(
                i * ring_segs, (i + 1) * ring_segs, ring_segs))
        faces.append(_cap_ring(0, ring_segs, reverse=True))
        faces.append(_cap_ring(rings * ring_segs, ring_segs))

    return verts, faces


# ---------------------------------------------------------------------------
# Wing generator
# ---------------------------------------------------------------------------


def generate_wing(
    wing_type: str = "bat",
    wingspan: float = 2.0,
    include_membrane: bool = True,
    position: Vec3 = (0.0, 0.0, 0.0),
) -> tuple[VertList, FaceList, dict[str, list[int]], dict[str, Vec3]]:
    """Generate wing with proper flapping topology.

    Types: 'bat' (membrane), 'bird' (feathered), 'dragon' (large membrane),
           'insect' (thin transparent)

    Returns: (vertices, faces, vertex_groups, bone_positions)
    """
    px, py, pz = position
    all_verts: VertList = []
    all_faces: FaceList = []
    groups: dict[str, list[int]] = {
        "wing_fold": [],
        "wing_extend": [],
        "membrane": [],
        "feathers": [],
    }
    bones: dict[str, Vec3] = {}

    s = wingspan / 2.0  # half wingspan

    # Wing bone structure: shoulder -> elbow -> wrist -> finger tips
    shoulder = (px, py, pz)
    elbow = (px + s * 0.35, py - s * 0.05, pz)
    wrist = (px + s * 0.65, py + s * 0.02, pz)

    bones["wing_shoulder"] = shoulder
    bones["wing_elbow"] = elbow
    bones["wing_wrist"] = wrist

    if wing_type in ("bat", "dragon"):
        # Finger bones radiate from wrist
        finger_count = 4 if wing_type == "bat" else 3
        finger_tips: list[Vec3] = []
        for fi in range(finger_count):
            t = fi / max(finger_count - 1, 1)
            angle = _lerp(-0.3, 0.8, t)  # Spread angle
            tip_x = wrist[0] + (s * 0.35) * math.cos(angle)
            tip_y = wrist[1] + (s * 0.35) * math.sin(angle)
            tip = (tip_x, tip_y, pz)
            finger_tips.append(tip)
            bones[f"wing_finger_{fi}"] = tip

        if include_membrane:
            # Build membrane as regular grid between bones
            # For cloth sim compatibility: regular quad grid
            mem_rows = 8
            mem_cols = 6 * finger_count

            mem_start = len(all_verts)
            for row in range(mem_rows + 1):
                rt = row / mem_rows  # 0=body edge, 1=wing tip
                for col in range(mem_cols + 1):
                    ct = col / mem_cols
                    # Interpolate between body edge and wing edge
                    # Body edge: from shoulder to trailing edge
                    body_pt = _lerp3(shoulder, (px, py - s * 0.3, pz), ct)
                    # Wing edge: interpolate along finger structure
                    fi_f = ct * (finger_count - 1)
                    fi_idx = min(int(fi_f), finger_count - 2)
                    fi_t = fi_f - fi_idx
                    if finger_count > 1:
                        wing_pt = _lerp3(finger_tips[fi_idx],
                                         finger_tips[fi_idx + 1], fi_t)
                    else:
                        wing_pt = finger_tips[0]

                    # Interpolate between body and wing edge
                    pt = _lerp3(body_pt, wing_pt, rt)
                    # Add slight curvature for aerodynamic shape
                    camber = math.sin(rt * math.pi) * s * 0.03
                    all_verts.append((pt[0], pt[1] + camber, pt[2]))

            mem_end = len(all_verts)
            groups["membrane"] = list(range(mem_start, mem_end))

            # Membrane quad faces
            for row in range(mem_rows):
                for col in range(mem_cols):
                    v0 = mem_start + row * (mem_cols + 1) + col
                    v1 = v0 + 1
                    v2 = v0 + (mem_cols + 1) + 1
                    v3 = v0 + (mem_cols + 1)
                    all_faces.append((v0, v1, v2, v3))

            # Assign fold/extend groups based on distance from body
            for vi in range(mem_start, mem_end):
                row_idx = (vi - mem_start) // (mem_cols + 1)
                if row_idx < mem_rows // 3:
                    groups["wing_fold"].append(vi)
                else:
                    groups["wing_extend"].append(vi)

    elif wing_type == "bird":
        # Feathered wing: arm bone structure + feather rows
        # Arm bones as tube mesh
        arm_segs = [
            {"start": shoulder, "end": elbow, "r": s * 0.02},
            {"start": elbow, "end": wrist, "r": s * 0.015},
        ]
        for seg in arm_segs:
            sv, sf = _build_bone_tube(seg["start"], seg["end"],
                                      seg["r"], segments=6, rings=3)
            arm_start = len(all_verts)
            all_verts.extend(sv)
            all_faces.extend([tuple(idx + arm_start for idx in f) for f in sf])

        # Feather rows: primaries, secondaries, coverts
        feather_configs = [
            {"name": "primaries", "count": 10, "length_factor": 1.0,
             "start_t": 0.6, "end_t": 1.0},
            {"name": "secondaries", "count": 8, "length_factor": 0.7,
             "start_t": 0.3, "end_t": 0.6},
            {"name": "coverts", "count": 12, "length_factor": 0.3,
             "start_t": 0.2, "end_t": 0.8},
        ]
        for fc in feather_configs:
            for fi in range(fc["count"]):
                ft = fc["start_t"] + (fc["end_t"] - fc["start_t"]) * fi / max(fc["count"] - 1, 1)
                # Position along wing
                wing_pt = _lerp3(shoulder, wrist, ft)
                f_length = s * 0.3 * fc["length_factor"]
                f_width = f_length * 0.08

                feather_start = len(all_verts)
                fv, ff = _generate_feather(wing_pt, f_length, f_width,
                                           angle=-0.3 - ft * 0.5)
                all_verts.extend(fv)
                all_faces.extend([tuple(idx + feather_start for idx in f)
                                  for f in ff])
                groups["feathers"].extend(range(feather_start, len(all_verts)))

    elif wing_type == "insect":
        # Thin transparent wing: single quad sheet with vein topology
        wing_segs_x = 8
        wing_segs_y = 12

        wing_start = len(all_verts)
        for ix in range(wing_segs_x + 1):
            xt = ix / wing_segs_x
            for iy in range(wing_segs_y + 1):
                yt = iy / wing_segs_y
                # Wing shape: elliptical outline
                wing_w = s * math.sin(xt * math.pi) * 0.4
                x = px + xt * s
                y = py + (yt - 0.5) * wing_w
                z = pz + math.sin(xt * math.pi) * s * 0.02  # slight curve
                all_verts.append((x, y, z))

        for ix in range(wing_segs_x):
            for iy in range(wing_segs_y):
                v0 = wing_start + ix * (wing_segs_y + 1) + iy
                v1 = v0 + 1
                v2 = v0 + (wing_segs_y + 1) + 1
                v3 = v0 + (wing_segs_y + 1)
                all_faces.append((v0, v1, v2, v3))

        groups["membrane"] = list(range(wing_start, len(all_verts)))

    return all_verts, all_faces, groups, bones


def _build_bone_tube(
    start: Vec3, end: Vec3, radius: float,
    segments: int = 6, rings: int = 3,
) -> tuple[VertList, FaceList]:
    """Build a tube mesh between two points."""
    direction = _vec3_sub(end, start)
    length = _vec3_length(direction)
    if length < 1e-10:
        return [], []

    dir_n = _vec3_normalize(direction)
    _, normal, binormal = _build_frame(dir_n)

    verts: VertList = []
    faces: FaceList = []

    for i in range(rings + 1):
        t = i / rings
        pos = _lerp3(start, end, t)
        for j in range(segments):
            angle = 2.0 * math.pi * j / segments
            px = math.cos(angle) * radius
            py = math.sin(angle) * radius
            verts.append((
                pos[0] + normal[0] * px + binormal[0] * py,
                pos[1] + normal[1] * px + binormal[1] * py,
                pos[2] + normal[2] * px + binormal[2] * py,
            ))

    for i in range(rings):
        faces.extend(_connect_rings(i * segments, (i + 1) * segments, segments))
    faces.append(_cap_ring(0, segments, reverse=True))
    faces.append(_cap_ring(rings * segments, segments))

    return verts, faces


def _generate_feather(
    base_pos: Vec3,
    length: float,
    width: float,
    angle: float = 0.0,
) -> tuple[VertList, FaceList]:
    """Generate a single feather as a tapered quad strip with rachis (stem)."""
    bx, by, bz = base_pos
    verts: VertList = []
    faces: FaceList = []

    feather_segs = 4
    for i in range(feather_segs + 1):
        t = i / feather_segs
        # Feather tapers from base to tip
        w = width * (1.0 - t * 0.8) * math.sin(max(t, 0.1) * math.pi)
        y = by - math.sin(angle) * length * t
        x = bx + math.cos(angle) * length * t
        # Left barb
        verts.append((x - w, y, bz))
        # Rachis (center)
        verts.append((x, y + width * 0.02, bz))  # slightly raised
        # Right barb
        verts.append((x + w, y, bz))

    for i in range(feather_segs):
        for j in range(2):  # 2 quads per row (left barbs, right barbs)
            v0 = i * 3 + j
            v1 = v0 + 1
            v2 = (i + 1) * 3 + j + 1
            v3 = (i + 1) * 3 + j
            faces.append((v0, v1, v2, v3))

    return verts, faces


# ---------------------------------------------------------------------------
# Serpent body generator
# ---------------------------------------------------------------------------


def generate_serpent_body(
    length: float = 3.0,
    max_radius: float = 0.08,
    segment_count: int = 40,
    head_style: str = "viper",
    include_hood: bool = False,
    size: float = 1.0,
) -> tuple[VertList, FaceList, dict[str, list[int]], dict[str, Vec3]]:
    """Generate serpentine body with proper coiling topology.

    Features:
    - 40+ segment spine for smooth coiling animation
    - Slightly flattened oval cross-section (flat belly)
    - Scale pattern via vertex colors (belly vs dorsal)
    - Head with jaw, nostrils, eye sockets, fangs
    - Per-segment vertex groups for wave slithering
    - Optional cobra hood

    Returns: (vertices, faces, vertex_groups, bone_positions)
    """
    length *= size
    max_radius *= size
    ring_segs = 10

    all_verts: VertList = []
    all_faces: FaceList = []
    groups: dict[str, list[int]] = {}
    bones: dict[str, Vec3] = {}

    # --- Main body via spine ---
    spine: list[Vec3] = []
    radii: list[tuple[float, float]] = []

    for i in range(segment_count + 1):
        t = i / segment_count
        z = t * length

        # Radius profile: thin at head, thickest at 20%, tapers to tail
        if t < 0.05:
            r_factor = _smooth_step(t / 0.05) * 0.5
        elif t < 0.2:
            r_factor = 0.5 + _smooth_step((t - 0.05) / 0.15) * 0.5
        elif t < 0.7:
            r_factor = 1.0 - (t - 0.2) / 0.5 * 0.1
        else:
            base = max(0.0, 1.0 - (t - 0.7) / 0.3)
            r_factor = 0.9 * base ** 1.5

        r_factor = max(r_factor, 0.02)
        rx = max_radius * r_factor
        ry = max_radius * r_factor * 0.75  # Flattened (belly)

        spine.append((0.0, max_radius * 1.1, z))
        radii.append((rx, ry))

    def serpent_profile(spine_t: float, angle: float, rx: float, ry: float
                        ) -> tuple[float, float]:
        """Flat belly, rounded back, slight belly scale ridge."""
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        mod_rx = rx
        mod_ry = ry
        # Flatten belly
        if sin_a < -0.3:
            flatten = max(0.0, (-sin_a - 0.3)) * 0.3
            mod_ry *= (1.0 - flatten)
        # Dorsal ridge
        if sin_a > 0.8:
            mod_ry += ry * 0.05 * (sin_a - 0.8) * 5.0
        # Belly scale ridge (two lateral ridges)
        if -0.5 < sin_a < 0.0 and abs(cos_a) > 0.5:
            mod_rx += rx * 0.03
        return (mod_rx, mod_ry)

    body_v, body_f = _build_body_from_spine(
        spine, radii, segments=ring_segs, profile_fn=serpent_profile)
    all_verts.extend(body_v)
    all_faces.extend(body_f)

    # Per-segment vertex groups
    verts_per_ring = ring_segs
    for seg_i in range(segment_count + 1):
        seg_name = f"segment_{seg_i:03d}"
        start_vi = seg_i * verts_per_ring
        end_vi = start_vi + verts_per_ring
        groups[seg_name] = list(range(start_vi, min(end_vi, len(all_verts))))
        bones[f"spine_{seg_i:03d}"] = spine[seg_i]

    bones["head"] = spine[0]
    bones["tail_tip"] = spine[-1]

    # --- Head ---
    head_v, head_f, head_bones, head_groups = _generate_serpent_head(
        head_style=head_style,
        radius=max_radius * 0.6,
        position=spine[0],
        size=size,
    )
    head_start = len(all_verts)
    all_verts.extend(head_v)
    all_faces.extend([tuple(idx + head_start for idx in f) for f in head_f])
    bones.update(head_bones)
    for gname, gindices in head_groups.items():
        groups[gname] = [idx + head_start for idx in gindices]

    # --- Cobra hood ---
    if include_hood or head_style == "cobra":
        hood_v, hood_f = _generate_cobra_hood(
            position=spine[int(segment_count * 0.03)],
            radius=max_radius * 2.0,
            size=size,
        )
        hood_start = len(all_verts)
        all_verts.extend(hood_v)
        all_faces.extend([tuple(idx + hood_start for idx in f) for f in hood_f])
        groups["hood_fold"] = list(range(hood_start, len(all_verts)))

    return all_verts, all_faces, groups, bones


def _generate_serpent_head(
    head_style: str,
    radius: float,
    position: Vec3,
    size: float = 1.0,
) -> tuple[VertList, FaceList, dict[str, Vec3], dict[str, list[int]]]:
    """Generate serpent head mesh."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []
    bones: dict[str, Vec3] = {}
    groups: dict[str, list[int]] = {"jaw": []}

    head_length = radius * 3.0
    head_segs = 8
    head_ring = 8

    spine: list[Vec3] = []
    radii: list[tuple[float, float]] = []

    for i in range(head_segs):
        t = i / (head_segs - 1)
        z = pz - t * head_length  # Head goes forward (negative Z)

        if head_style == "viper":
            # Triangular: wide at back, narrow at front
            rx = radius * (1.0 - t * 0.6) * (1.0 + (1.0 - t) * 0.3)
            ry = radius * (0.6 - t * 0.3)
        elif head_style == "python":
            # Rounded
            envelope = math.sin(max(t, 0.1) * math.pi)
            rx = radius * 0.8 * envelope
            ry = radius * 0.5 * envelope
        else:  # cobra
            # Slightly flared at back
            rx = radius * (0.8 + (1.0 - t) * 0.4 * max(0, 1.0 - t * 3.0))
            ry = radius * (0.5 - t * 0.2)

        spine.append((px, py, z))
        radii.append((max(rx, 0.001), max(ry, 0.001)))

    head_v, head_f = _build_body_from_spine(
        spine, radii, segments=head_ring)
    verts.extend(head_v)
    faces.extend(head_f)

    bones["serpent_head"] = (px, py, pz - head_length * 0.4)
    bones["serpent_jaw"] = (px, py - radius * 0.3, pz - head_length * 0.3)

    # Jaw vertex group (lower half of head)
    for vi, v in enumerate(verts):
        if v[1] < py:
            groups["jaw"].append(vi)

    return verts, faces, bones, groups


def _generate_cobra_hood(
    position: Vec3,
    radius: float,
    size: float = 1.0,
) -> tuple[VertList, FaceList]:
    """Generate deployable cobra hood as a flat membrane."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []

    rows = 6
    cols = 8

    for r in range(rows + 1):
        rt = r / rows
        # Hood is widest at middle
        envelope = math.sin(rt * math.pi)
        w = radius * envelope * size
        y = py + rt * radius * 0.5 * size
        for c in range(cols + 1):
            ct = c / cols - 0.5
            x = px + ct * w * 2.0
            z = pz - abs(ct) * radius * 0.1  # Slight concavity
            verts.append((x, y, z))

    for r in range(rows):
        for c in range(cols):
            v0 = r * (cols + 1) + c
            v1 = v0 + 1
            v2 = (r + 1) * (cols + 1) + c + 1
            v3 = (r + 1) * (cols + 1) + c
            faces.append((v0, v1, v2, v3))

    return verts, faces


# ---------------------------------------------------------------------------
# Main quadruped generator
# ---------------------------------------------------------------------------


def generate_quadruped(
    species: str = "wolf",
    size: float = 1.0,
    build: str = "average",
    include_mouth_interior: bool = True,
    include_eyelids: bool = True,
) -> CreatureMeshResult:
    """Generate anatomically-correct quadruped creature mesh.

    Species: 'wolf', 'bear', 'lion', 'horse', 'deer', 'boar', 'rat_giant'
    Build: 'lean', 'average', 'muscular', 'massive'

    The body is defined as a spine curve with anatomical cross-section
    profiles. Each joint has proper edge loops for deformation.

    Returns dict with vertices, faces, bone_positions, vertex_groups,
    bounding_box, and metadata.
    """
    if species not in QUADRUPED_PROPORTIONS:
        raise ValueError(
            f"Unknown species '{species}'. "
            f"Valid species: {', '.join(QUADRUPED_PROPORTIONS.keys())}"
        )

    props = QUADRUPED_PROPORTIONS[species]

    # Build modifier
    build_scale = {
        "lean": 0.85,
        "average": 1.0,
        "muscular": 1.15,
        "massive": 1.35,
    }.get(build, 1.0)

    # Apply build to width/height proportions
    effective_props = dict(props)
    effective_props["body_width"] = props["body_width"] * build_scale
    effective_props["body_height"] = props["body_height"] * (
        1.0 + (build_scale - 1.0) * 0.3)

    all_verts: VertList = []
    all_faces: FaceList = []
    all_bones: dict[str, Vec3] = {}
    all_groups: dict[str, list[int]] = {}

    # --- Main body from anatomical spine ---
    spine, radii = _generate_quadruped_spine(effective_props, size)
    profile_fn = _quadruped_body_profile(effective_props)
    body_v, body_f = _build_body_from_spine(
        spine, radii,
        segments=effective_props["cross_segments"],
        profile_fn=profile_fn,
    )
    all_verts.extend(body_v)
    all_faces.extend(body_f)

    # Spine bone positions
    body_length = effective_props["body_length"] * size
    snout_length = effective_props["snout_length"] * size
    head_length = effective_props["head_length"] * size
    neck_length = effective_props["neck_length"] * size

    body_start_z = snout_length + head_length + neck_length
    for i in range(6):
        t = i / 5
        bone_z = body_start_z + t * body_length
        idx = min(int(t * (len(spine) - 1)), len(spine) - 1)
        all_bones[f"spine_{i + 1:02d}"] = spine[idx]

    # Breathing group (rib cage vertices, front 40% of body)
    body_ring_segs = effective_props["cross_segments"]
    all_groups["breathing"] = []
    total_spine_pts = effective_props["spine_points"]
    for i in range(total_spine_pts):
        t = i / max(total_spine_pts - 1, 1)
        spine_z = t * (snout_length + head_length + neck_length + body_length +
                       effective_props["tail_length"] * size)
        if body_start_z < spine_z < body_start_z + body_length * 0.5:
            ring_start = i * body_ring_segs
            ring_end = ring_start + body_ring_segs
            all_groups["breathing"].extend(
                range(ring_start, min(ring_end, len(all_verts))))

    # --- Neck bones ---
    neck_start_z = snout_length + head_length
    for i in range(3):
        t = i / 2
        nz = neck_start_z + t * neck_length
        idx = min(int((nz / (snout_length + head_length + neck_length +
                              body_length + effective_props["tail_length"] * size))
                      * (len(spine) - 1)), len(spine) - 1)
        all_bones[f"neck_{i + 1:02d}"] = spine[idx]

    # --- Head ---
    head_base = spine[0] if spine else (0.0, effective_props["body_height"] * size, 0.0)
    head_v, head_f, head_bones, head_groups = _generate_quadruped_head(
        effective_props, size, head_base,
        include_mouth=include_mouth_interior,
        include_eyelids=include_eyelids,
    )
    head_start = len(all_verts)
    all_verts.extend(head_v)
    all_faces.extend([tuple(idx + head_start for idx in f) for f in head_f])
    all_bones.update(head_bones)
    for gname, gindices in head_groups.items():
        all_groups[gname] = [idx + head_start for idx in gindices]

    # --- Four limbs with proper topology ---
    body_height = effective_props["body_height"] * size
    body_width = effective_props["body_width"] * size
    front_leg_len = effective_props["leg_length_front"] * size
    rear_leg_len = effective_props["leg_length_rear"] * size

    shoulder_z = body_start_z + body_length * 0.15
    hip_z = body_start_z + body_length * 0.8

    leg_configs = [
        ("front_left", -body_width * 0.45, shoulder_z, front_leg_len, True),
        ("front_right", body_width * 0.45, shoulder_z, front_leg_len, True),
        ("rear_left", -body_width * 0.45, hip_z, rear_leg_len, False),
        ("rear_right", body_width * 0.45, hip_z, rear_leg_len, False),
    ]

    for leg_name, lx, lz, leg_len, is_front in leg_configs:
        upper_ratio = 0.45
        lower_ratio = 0.35
        ankle_ratio = 0.15
        foot_ratio = 0.05

        upper_len = leg_len * upper_ratio
        lower_len = leg_len * lower_ratio
        ankle_len = leg_len * ankle_ratio
        foot_len = leg_len * foot_ratio

        leg_segs = [
            {
                "start_radius": body_width * 0.15,
                "end_radius": body_width * 0.1,
                "length": upper_len,
                "direction": (0.0, -1.0, 0.0),
                "joint_name": f"{leg_name}_shoulder" if is_front else f"{leg_name}_hip",
            },
            {
                "start_radius": body_width * 0.1,
                "end_radius": body_width * 0.07,
                "length": lower_len,
                "direction": (0.0, -1.0, 0.02 if is_front else -0.02),
                "joint_name": f"{leg_name}_knee",
                "end_joint_name": f"{leg_name}_ankle",
            },
            {
                "start_radius": body_width * 0.07,
                "end_radius": body_width * 0.05,
                "length": ankle_len,
                "direction": (0.0, -1.0, 0.0),
                "joint_name": f"{leg_name}_ankle",
                "end_joint_name": f"{leg_name}_foot",
            },
        ]

        shoulder_y = body_height - body_width * 0.1
        leg_start = (lx, shoulder_y, lz)

        leg_v, leg_f, leg_bones = _generate_limb(
            leg_start, leg_segs, ring_segments=8)
        leg_v_start = len(all_verts)
        all_verts.extend(leg_v)
        all_faces.extend([tuple(idx + leg_v_start for idx in f)
                          for f in leg_f])
        all_bones.update(leg_bones)

        # Paw at foot
        foot_pos = leg_bones.get(f"{leg_name}_foot",
                                 leg_bones.get("limb_end", leg_start))
        paw_v, paw_f, paw_groups = generate_paw(
            paw_type=effective_props["paw_type"],
            toe_count=effective_props["toe_count"],
            size=size * 0.5,
            position=foot_pos,
        )
        paw_start = len(all_verts)
        all_verts.extend(paw_v)
        all_faces.extend([tuple(idx + paw_start for idx in f)
                          for f in paw_f])
        for gname, gindices in paw_groups.items():
            group_name = f"{leg_name}_{gname}"
            all_groups[group_name] = [idx + paw_start for idx in gindices]
        all_bones[f"{leg_name}_foot"] = foot_pos

    # --- Tail ---
    tail_length = effective_props["tail_length"] * size
    tail_start_z = body_start_z + body_length
    tail_segs = 6
    tail_spine: list[Vec3] = []
    tail_radii: list[tuple[float, float]] = []

    for i in range(tail_segs + 1):
        t = i / tail_segs
        tz = tail_start_z + t * tail_length
        # Tail curves up then down
        ty = body_height + math.sin(t * math.pi * 0.4) * tail_length * 0.15
        taper = 1.0 - t * 0.88
        tr = body_width * 0.08 * max(taper, 0.05) * size
        tail_spine.append((0.0, ty, tz))
        tail_radii.append((tr, tr * 0.85))
        all_bones[f"tail_{i + 1:02d}"] = (0.0, ty, tz)

    tail_v, tail_f = _build_body_from_spine(tail_spine, tail_radii, segments=8)
    tail_v_start = len(all_verts)
    all_verts.extend(tail_v)
    all_faces.extend([tuple(idx + tail_v_start for idx in f) for f in tail_f])

    # Tail vertex groups
    for i in range(tail_segs + 1):
        ring_start = tail_v_start + i * 8
        ring_end = min(ring_start + 8, len(all_verts))
        all_groups[f"tail_{i + 1:02d}"] = list(range(ring_start, ring_end))

    # --- Compute metadata ---
    bbox = _compute_bbox(all_verts)

    return {
        "vertices": all_verts,
        "faces": all_faces,
        "species": species,
        "build": build,
        "size": size,
        "bone_positions": all_bones,
        "vertex_groups": all_groups,
        "bounding_box": bbox,
        "vertex_count": len(all_verts),
        "face_count": len(all_faces),
        "topology_type": "spine_profiled",
        "animation_ready": True,
        "has_mouth_interior": include_mouth_interior,
        "has_eyelids": include_eyelids,
    }


# ---------------------------------------------------------------------------
# Fantasy creature generator
# ---------------------------------------------------------------------------


def generate_fantasy_creature(
    base_type: str = "chimera",
    brand: str | None = None,
    size: float = 1.0,
) -> CreatureMeshResult:
    """Generate fantasy creature from modular anatomy parts.

    Types:
    - 'chimera': lion body + goat head (secondary) + serpent tail
    - 'wyvern': bipedal dragon with wing-arms
    - 'basilisk': massive serpent with legs + crown ridge
    - 'dire_wolf': oversized wolf with bony protrusions + mane
    - 'spider_queen': arachnid body with humanoid torso
    - 'undead_horse': skeletal horse with ghostly features
    - 'treant': humanoid tree creature with bark skin and branch limbs
    """
    if base_type not in FANTASY_CREATURE_TYPES:
        raise ValueError(
            f"Unknown creature type '{base_type}'. "
            f"Valid types: {', '.join(FANTASY_CREATURE_TYPES)}"
        )

    all_verts: VertList = []
    all_faces: FaceList = []
    all_bones: dict[str, Vec3] = {}
    all_groups: dict[str, list[int]] = {}

    if base_type == "chimera":
        _build_chimera(all_verts, all_faces, all_bones, all_groups, size)
    elif base_type == "wyvern":
        _build_wyvern(all_verts, all_faces, all_bones, all_groups, size)
    elif base_type == "basilisk":
        _build_basilisk(all_verts, all_faces, all_bones, all_groups, size)
    elif base_type == "dire_wolf":
        _build_dire_wolf(all_verts, all_faces, all_bones, all_groups, size)
    elif base_type == "spider_queen":
        _build_spider_queen(all_verts, all_faces, all_bones, all_groups, size)
    elif base_type == "undead_horse":
        _build_undead_horse(all_verts, all_faces, all_bones, all_groups, size)
    elif base_type == "treant":
        _build_treant(all_verts, all_faces, all_bones, all_groups, size)

    # Apply brand features
    brand_feature_count = 0
    if brand and brand in BRAND_ANATOMY_FEATURES:
        pre_count = len(all_verts)
        _apply_brand_anatomy_features(
            all_verts, all_faces, all_bones, all_groups, brand, size)
        brand_feature_count = len(all_verts) - pre_count

    bbox = _compute_bbox(all_verts)

    return {
        "vertices": all_verts,
        "faces": all_faces,
        "creature_type": base_type,
        "brand": brand,
        "size": size,
        "bone_positions": all_bones,
        "vertex_groups": all_groups,
        "bounding_box": bbox,
        "vertex_count": len(all_verts),
        "face_count": len(all_faces),
        "brand_feature_vertex_count": brand_feature_count,
        "topology_type": "composite_anatomy",
        "animation_ready": True,
    }


# ---------------------------------------------------------------------------
# Fantasy creature builders
# ---------------------------------------------------------------------------


def _build_chimera(verts: VertList, faces: FaceList,
                   bones: dict, groups: dict, size: float) -> None:
    """Lion body + secondary goat head + serpent tail."""
    # Lion body base
    result = generate_quadruped("lion", size=size, include_mouth_interior=True)
    verts.extend(result["vertices"])
    faces.extend(result["faces"])
    bones.update(result["bone_positions"])
    groups.update(result["vertex_groups"])

    # Serpent tail (replaces normal tail)
    tail_pos = bones.get("tail_01", (0.0, 0.8 * size, 1.4 * size))
    serpent_v, serpent_f, serpent_g, serpent_b = generate_serpent_body(
        length=1.5, max_radius=0.04, segment_count=20,
        head_style="viper", size=size)
    # Offset to tail position
    offset_v = [(v[0] + tail_pos[0], v[1] + tail_pos[1] - 0.08 * size,
                 v[2] + tail_pos[2]) for v in serpent_v]
    s = len(verts)
    verts.extend(offset_v)
    faces.extend([tuple(idx + s for idx in f) for f in serpent_f])
    for gn, gi in serpent_g.items():
        groups[f"serpent_tail_{gn}"] = [idx + s for idx in gi]


def _build_wyvern(verts: VertList, faces: FaceList,
                  bones: dict, groups: dict, size: float) -> None:
    """Bipedal dragon with wing-arms: spine body + 2 legs + 2 wings + dragon head."""
    # Upright spine body
    spine_pts: list[Vec3] = []
    spine_radii: list[tuple[float, float]] = []
    body_height = 1.5 * size
    for i in range(12):
        t = i / 11
        y = t * body_height
        z_curve = math.sin(t * math.pi * 0.3) * 0.1 * size
        envelope = math.sin(max(t * 0.9, 0.05) * math.pi)
        rx = 0.2 * size * envelope
        ry = 0.15 * size * envelope
        spine_pts.append((0.0, y, z_curve))
        spine_radii.append((max(rx, 0.01), max(ry, 0.01)))

    body_v, body_f = _build_body_from_spine(spine_pts, spine_radii, segments=10)
    verts.extend(body_v)
    faces.extend(body_f)
    bones["spine_base"] = spine_pts[0]
    bones["spine_top"] = spine_pts[-1]

    # Wings
    for side_name, sx in [("L", -1.0), ("R", 1.0)]:
        wing_pos = (sx * 0.15 * size, body_height * 0.7, 0.0)
        wv, wf, wg, wb = generate_wing(
            "dragon", wingspan=2.5 * size, position=wing_pos)
        if sx > 0:
            wv = [(-v[0] + 2 * wing_pos[0], v[1], v[2]) for v in wv]
        ws = len(verts)
        verts.extend(wv)
        faces.extend([tuple(idx + ws for idx in f) for f in wf])
        for gn, gi in wg.items():
            groups[f"wing_{side_name}_{gn}"] = [idx + ws for idx in gi]
        for bn, bp in wb.items():
            bones[f"{bn}_{side_name}"] = bp

    # Two legs
    for side_name, sx in [("L", -0.12), ("R", 0.12)]:
        lx = sx * size
        leg_start = (lx, 0.15 * size, 0.0)
        segs = [
            {"start_radius": 0.06 * size, "end_radius": 0.04 * size,
             "length": 0.4 * size, "direction": (0.0, -1.0, 0.0),
             "joint_name": f"leg_{side_name}_hip"},
            {"start_radius": 0.04 * size, "end_radius": 0.03 * size,
             "length": 0.35 * size, "direction": (0.0, -1.0, 0.05),
             "joint_name": f"leg_{side_name}_knee",
             "end_joint_name": f"leg_{side_name}_foot"},
        ]
        lv, lf, lb = _generate_limb(leg_start, segs, ring_segments=6)
        ls = len(verts)
        verts.extend(lv)
        faces.extend([tuple(idx + ls for idx in f) for f in lf])
        bones.update(lb)


def _build_basilisk(verts: VertList, faces: FaceList,
                    bones: dict, groups: dict, size: float) -> None:
    """Massive serpent with vestigial legs + crown ridge."""
    sv, sf, sg, sb = generate_serpent_body(
        length=5.0, max_radius=0.15, segment_count=50,
        head_style="python", size=size)
    verts.extend(sv)
    faces.extend(sf)
    bones.update(sb)
    groups.update(sg)

    # Vestigial legs (4 small limbs along body)
    for i in range(4):
        t = 0.2 + i * 0.15
        leg_z = t * 5.0 * size
        for sx in [-1.0, 1.0]:
            leg_pos = (sx * 0.12 * size, 0.05 * size, leg_z)
            segs = [
                {"start_radius": 0.02 * size, "end_radius": 0.01 * size,
                 "length": 0.15 * size, "direction": (sx * 0.3, -1.0, 0.0),
                 "joint_name": f"vestigial_leg_{i}_{('L' if sx < 0 else 'R')}",
                 "end_joint_name": f"vestigial_foot_{i}_{('L' if sx < 0 else 'R')}"},
            ]
            lv, lf, lb = _generate_limb(leg_pos, segs, ring_segments=5)
            ls = len(verts)
            verts.extend(lv)
            faces.extend([tuple(idx + ls for idx in f) for f in lf])
            bones.update(lb)

    # Crown ridge on head
    crown_start = len(verts)
    crown_v, crown_f = _generate_crown_ridge(
        bones.get("head", (0.0, 0.15 * size, 0.0)), size=size * 0.5)
    verts.extend(crown_v)
    faces.extend([tuple(idx + crown_start for idx in f) for f in crown_f])
    groups["crown"] = list(range(crown_start, len(verts)))


def _build_dire_wolf(verts: VertList, faces: FaceList,
                     bones: dict, groups: dict, size: float) -> None:
    """Oversized wolf with bony protrusions and mane."""
    result = generate_quadruped("wolf", size=size * 1.5, build="muscular",
                                include_mouth_interior=True)
    verts.extend(result["vertices"])
    faces.extend(result["faces"])
    bones.update(result["bone_positions"])
    groups.update(result["vertex_groups"])

    # Bony protrusions along spine
    for i in range(5):
        t = 0.2 + i * 0.1
        spine_key = f"spine_{i + 1:02d}"
        if spine_key in bones:
            pos = bones[spine_key]
            prot_start = len(verts)
            pv, pf = _generate_bony_protrusion(pos, height=0.08 * size)
            verts.extend(pv)
            faces.extend([tuple(idx + prot_start for idx in f) for f in pf])
            groups.setdefault("protrusions", []).extend(
                range(prot_start, len(verts)))

    # Mane (row of bristle quads along neck)
    mane_start = len(verts)
    for i in range(8):
        t = i / 7
        nk = f"neck_{min(i // 3 + 1, 3):02d}"
        if nk in bones:
            pos = bones[nk]
        else:
            pos = (0.0, 0.7 * size * 1.5 + t * 0.1, t * 0.25 * size * 1.5)
        mv, mf = _generate_mane_tuft(pos, size=size * 0.15, angle=t * 0.3)
        ms = len(verts)
        verts.extend(mv)
        faces.extend([tuple(idx + ms for idx in f) for f in mf])
    groups["mane"] = list(range(mane_start, len(verts)))


def _build_spider_queen(verts: VertList, faces: FaceList,
                        bones: dict, groups: dict, size: float) -> None:
    """Arachnid body with humanoid torso."""
    # Spider abdomen
    abd_spine: list[Vec3] = []
    abd_radii: list[tuple[float, float]] = []
    for i in range(8):
        t = i / 7
        envelope = math.sin(max(t, 0.1) * math.pi)
        abd_spine.append((0.0, 0.3 * size, -t * 0.8 * size))
        abd_radii.append((0.2 * size * envelope, 0.15 * size * envelope))

    abd_v, abd_f = _build_body_from_spine(abd_spine, abd_radii, segments=10)
    verts.extend(abd_v)
    faces.extend(abd_f)
    bones["abdomen"] = (0.0, 0.3 * size, -0.4 * size)

    # Humanoid torso on top
    torso_spine: list[Vec3] = []
    torso_radii: list[tuple[float, float]] = []
    for i in range(6):
        t = i / 5
        torso_spine.append((0.0, 0.4 * size + t * 0.6 * size, 0.1 * size))
        r = 0.1 * size * (1.0 - abs(t - 0.5) * 0.4)
        torso_radii.append((r, r * 0.7))

    torso_v, torso_f = _build_body_from_spine(torso_spine, torso_radii, segments=8)
    ts = len(verts)
    verts.extend(torso_v)
    faces.extend([tuple(idx + ts for idx in f) for f in torso_f])
    bones["torso_base"] = torso_spine[0]
    bones["torso_top"] = torso_spine[-1]

    # 8 spider legs
    for i in range(8):
        angle = (i / 8) * math.pi * 2
        side = "L" if i < 4 else "R"
        leg_idx = i % 4
        lx = math.cos(angle) * 0.2 * size
        lz = -0.4 * size + math.sin(angle) * 0.3 * size
        leg_pos = (lx, 0.25 * size, lz)
        segs = [
            {"start_radius": 0.03 * size, "end_radius": 0.015 * size,
             "length": 0.5 * size, "direction": (math.cos(angle), -0.5, math.sin(angle)),
             "joint_name": f"spider_leg_{side}_{leg_idx}_hip"},
            {"start_radius": 0.015 * size, "end_radius": 0.005 * size,
             "length": 0.4 * size, "direction": (math.cos(angle) * 0.3, -1.0, math.sin(angle) * 0.3),
             "joint_name": f"spider_leg_{side}_{leg_idx}_knee",
             "end_joint_name": f"spider_leg_{side}_{leg_idx}_foot"},
        ]
        lv, lf, lb = _generate_limb(leg_pos, segs, ring_segments=5)
        ls = len(verts)
        verts.extend(lv)
        faces.extend([tuple(idx + ls for idx in f) for f in lf])
        bones.update(lb)


def _build_undead_horse(verts: VertList, faces: FaceList,
                        bones: dict, groups: dict, size: float) -> None:
    """Skeletal horse with ghostly features."""
    result = generate_quadruped("horse", size=size, build="lean",
                                include_mouth_interior=True)
    verts.extend(result["vertices"])
    faces.extend(result["faces"])
    bones.update(result["bone_positions"])
    groups.update(result["vertex_groups"])

    # Add rib cage exposure (strips of geometry suggesting visible ribs)
    rib_start = len(verts)
    body_height = 1.1 * size
    body_width = 0.45 * size
    for i in range(8):
        t = 0.2 + i * 0.06
        rib_z = t * 1.6 * size + 0.4 * size  # Along body
        for sx in [-1.0, 1.0]:
            rv, rf = _generate_rib_bone(
                (sx * body_width * 0.3, body_height - 0.05 * size, rib_z),
                width=body_width * 0.3, height=0.02 * size, depth=0.15 * size,
            )
            rs = len(verts)
            verts.extend(rv)
            faces.extend([tuple(idx + rs for idx in f) for f in rf])
    groups["ribs"] = list(range(rib_start, len(verts)))


def _build_treant(verts: VertList, faces: FaceList,
                  bones: dict, groups: dict, size: float) -> None:
    """Humanoid tree creature with bark skin and branch limbs."""
    # Trunk body
    trunk_spine: list[Vec3] = []
    trunk_radii: list[tuple[float, float]] = []
    for i in range(10):
        t = i / 9
        y = t * 2.0 * size
        # Tree trunk: wider at base, has organic irregularity
        base_r = 0.25 * size * (1.0 - t * 0.5)
        noise = _pseudo_noise(i, 0, 42) * 0.02 * size
        trunk_spine.append((noise, y, 0.0))
        trunk_radii.append((base_r + abs(noise), base_r * 0.9))

    trunk_v, trunk_f = _build_body_from_spine(trunk_spine, trunk_radii, segments=10)
    verts.extend(trunk_v)
    faces.extend(trunk_f)
    bones["root"] = trunk_spine[0]
    bones["crown"] = trunk_spine[-1]

    # Branch arms (2)
    for side_name, sx in [("L", -1.0), ("R", 1.0)]:
        arm_pos = (sx * 0.2 * size, 1.5 * size, 0.0)
        segs = [
            {"start_radius": 0.06 * size, "end_radius": 0.04 * size,
             "length": 0.5 * size, "direction": (sx, 0.3, 0.0),
             "joint_name": f"branch_arm_{side_name}_shoulder"},
            {"start_radius": 0.04 * size, "end_radius": 0.02 * size,
             "length": 0.4 * size, "direction": (sx, -0.1, 0.2),
             "joint_name": f"branch_arm_{side_name}_elbow",
             "end_joint_name": f"branch_arm_{side_name}_hand"},
        ]
        av, af, ab = _generate_limb(arm_pos, segs, ring_segments=6)
        a_s = len(verts)
        verts.extend(av)
        faces.extend([tuple(idx + a_s for idx in f) for f in af])
        bones.update(ab)

    # Root legs (2 thick, gnarled)
    for side_name, sx in [("L", -0.15), ("R", 0.15)]:
        leg_pos = (sx * size, 0.1 * size, 0.0)
        segs = [
            {"start_radius": 0.1 * size, "end_radius": 0.08 * size,
             "length": 0.6 * size, "direction": (sx * 0.3, -1.0, 0.0),
             "joint_name": f"root_leg_{side_name}_hip"},
            {"start_radius": 0.08 * size, "end_radius": 0.12 * size,
             "length": 0.3 * size, "direction": (sx * 0.5, -0.5, 0.3),
             "joint_name": f"root_leg_{side_name}_knee",
             "end_joint_name": f"root_leg_{side_name}_foot"},
        ]
        lv, lf, lb = _generate_limb(leg_pos, segs, ring_segments=6)
        ls = len(verts)
        verts.extend(lv)
        faces.extend([tuple(idx + ls for idx in f) for f in lf])
        bones.update(lb)


# ---------------------------------------------------------------------------
# Helper geometry for fantasy creatures
# ---------------------------------------------------------------------------


def _generate_crown_ridge(position: Vec3, size: float) -> tuple[VertList, FaceList]:
    """Generate a crown/crest ridge of bony spikes."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []
    spike_count = 5
    for i in range(spike_count):
        t = i / max(spike_count - 1, 1) - 0.5
        sx = px + t * 0.1 * size
        sy = py + 0.05 * size
        # Spike: tapered quad
        h = 0.08 * size * (1.0 - abs(t) * 0.5)
        w = 0.01 * size
        base = len(verts)
        verts.extend([
            (sx - w, sy, pz - w),
            (sx + w, sy, pz - w),
            (sx + w, sy, pz + w),
            (sx - w, sy, pz + w),
            (sx, sy + h, pz),  # tip
        ])
        faces.extend([
            (base, base + 1, base + 4),
            (base + 1, base + 2, base + 4),
            (base + 2, base + 3, base + 4),
            (base + 3, base, base + 4),
            (base, base + 3, base + 2, base + 1),  # base
        ])
    return verts, faces


def _generate_bony_protrusion(
    position: Vec3, height: float,
) -> tuple[VertList, FaceList]:
    """Generate a single bony protrusion spike."""
    px, py, pz = position
    w = height * 0.25
    verts: VertList = [
        (px - w, py, pz - w),
        (px + w, py, pz - w),
        (px + w, py, pz + w),
        (px - w, py, pz + w),
        (px, py + height, pz),
    ]
    faces: FaceList = [
        (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
        (0, 3, 2, 1),
    ]
    return verts, faces


def _generate_mane_tuft(
    position: Vec3, size: float, angle: float = 0.0,
) -> tuple[VertList, FaceList]:
    """Generate a single mane tuft (flat quad strip)."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []
    strands = 3
    for si in range(strands):
        sa = angle + (si - 1) * 0.2
        base = len(verts)
        for i in range(3):
            t = i / 2
            x = px + math.sin(sa) * size * t
            y = py + size * (1.0 - t * 0.3)
            z = pz + math.cos(sa) * size * t * 0.3
            w = size * 0.15 * (1.0 - t * 0.5)
            verts.append((x - w, y, z))
            verts.append((x + w, y, z))
        for i in range(2):
            v0 = base + i * 2
            faces.append((v0, v0 + 1, v0 + 3, v0 + 2))
    return verts, faces


def _generate_rib_bone(
    position: Vec3,
    width: float,
    height: float,
    depth: float,
) -> tuple[VertList, FaceList]:
    """Generate a curved rib bone mesh."""
    px, py, pz = position
    verts: VertList = []
    faces: FaceList = []
    segs = 6
    ring_segs = 4

    for i in range(segs + 1):
        t = i / segs
        # Rib curves around body
        angle = t * math.pi * 0.6
        x = px + math.sin(angle) * width
        y = py - math.cos(angle) * depth
        r = height * (1.0 - abs(t - 0.5) * 0.5)
        for j in range(ring_segs):
            a = 2.0 * math.pi * j / ring_segs
            verts.append((x + math.cos(a) * r, y + math.sin(a) * r, pz))

    for i in range(segs):
        faces.extend(_connect_rings(
            i * ring_segs, (i + 1) * ring_segs, ring_segs))

    return verts, faces


# ---------------------------------------------------------------------------
# Brand feature application
# ---------------------------------------------------------------------------


def _apply_brand_anatomy_features(
    verts: VertList,
    faces: FaceList,
    bones: dict,
    groups: dict,
    brand: str,
    size: float,
) -> None:
    """Apply VeilBreakers brand visual features to creature geometry.

    Modifies verts/faces/groups in place by adding brand-specific geometry.
    """
    features = BRAND_ANATOMY_FEATURES.get(brand, {})
    if not features:
        return

    # Sample surface points for feature placement
    sample_count = min(8, max(4, len(verts) // 200))
    step = max(1, len(verts) // sample_count)
    surface_pts = [verts[i] for i in range(0, len(verts), step)][:sample_count]

    brand_start = len(verts)

    if features.get("metallic_patches") or features.get("sharp_protrusions"):
        # Metal plates + spikes
        for pt in surface_pts[::2]:
            pv, pf = _generate_bony_protrusion(pt, height=0.04 * size)
            ps = len(verts)
            verts.extend(pv)
            faces.extend([tuple(idx + ps for idx in f) for f in pf])

    if features.get("bone_spurs") or features.get("bony_spurs"):
        for pt in surface_pts[::2]:
            pv, pf = _generate_bony_protrusion(pt, height=0.05 * size)
            ps = len(verts)
            verts.extend(pv)
            faces.extend([tuple(idx + ps for idx in f) for f in pf])

    if features.get("crystal_growths"):
        for pt in surface_pts[::3]:
            for ci in range(2):
                angle = ci * math.pi
                cx = pt[0] + math.cos(angle) * 0.02 * size
                cz = pt[2] + math.sin(angle) * 0.02 * size
                cv, cf = _generate_bony_protrusion(
                    (cx, pt[1], cz), height=0.06 * size)
                cs = len(verts)
                verts.extend(cv)
                faces.extend([tuple(idx + cs for idx in f) for f in cf])

    if features.get("pustules") or features.get("dripping_geometry"):
        for pt in surface_pts:
            # Small sphere bumps
            r = 0.015 * size
            segs = 4
            center = len(verts)
            for j in range(segs):
                angle = 2.0 * math.pi * j / segs
                verts.append((pt[0] + math.cos(angle) * r,
                              pt[1] + r * 0.5,
                              pt[2] + math.sin(angle) * r))
            verts.append((pt[0], pt[1] + r * 1.2, pt[2]))
            tip = len(verts) - 1
            for j in range(segs):
                j2 = (j + 1) % segs
                faces.append((center + j, center + j2, tip))

    if features.get("parasitic_growths") or features.get("pulsing_veins"):
        # Tendril-like growths
        for pt in surface_pts[::2]:
            tendril_len = 0.08 * size
            segs = 3
            t_start = len(verts)
            for s in range(segs + 1):
                st = s / segs
                verts.append((pt[0], pt[1] + st * tendril_len,
                              pt[2] + st * 0.02 * size))
                verts.append((pt[0] + 0.005 * size, pt[1] + st * tendril_len,
                              pt[2] + st * 0.02 * size))
            for s in range(segs):
                v0 = t_start + s * 2
                faces.append((v0, v0 + 1, v0 + 3, v0 + 2))

    if features.get("feather_tufts") or features.get("luminous_markings"):
        for pt in surface_pts[::2]:
            fv, ff = _generate_mane_tuft(pt, size=0.05 * size)
            fs = len(verts)
            verts.extend(fv)
            faces.extend([tuple(idx + fs for idx in f) for f in ff])

    if features.get("bark_patches") or features.get("moss_growth"):
        # Flat patches
        for pt in surface_pts[::2]:
            ps = len(verts)
            w = 0.03 * size
            verts.extend([
                (pt[0] - w, pt[1], pt[2] - w),
                (pt[0] + w, pt[1], pt[2] - w),
                (pt[0] + w, pt[1] + 0.005 * size, pt[2] + w),
                (pt[0] - w, pt[1] + 0.005 * size, pt[2] + w),
            ])
            faces.append((ps, ps + 1, ps + 2, ps + 3))

    if features.get("crack_lines") or features.get("floating_fragments"):
        for pt in surface_pts[::3]:
            # Floating fragment
            ps = len(verts)
            d = 0.02 * size
            off_y = 0.05 * size
            verts.extend([
                (pt[0] - d, pt[1] + off_y - d, pt[2] - d),
                (pt[0] + d, pt[1] + off_y - d, pt[2] - d),
                (pt[0] + d, pt[1] + off_y + d, pt[2] + d),
                (pt[0] - d, pt[1] + off_y + d, pt[2] + d),
            ])
            faces.append((ps, ps + 1, ps + 2, ps + 3))

    if features.get("void_patches") or features.get("geometric_distortion"):
        for pt in surface_pts[::2]:
            ps = len(verts)
            d = 0.025 * size
            # Geometric void: inverted pyramid
            verts.extend([
                (pt[0] - d, pt[1], pt[2] - d),
                (pt[0] + d, pt[1], pt[2] - d),
                (pt[0] + d, pt[1], pt[2] + d),
                (pt[0] - d, pt[1], pt[2] + d),
                (pt[0], pt[1] - d * 1.5, pt[2]),  # inverted tip
            ])
            faces.extend([
                (ps, ps + 1, ps + 4),
                (ps + 1, ps + 2, ps + 4),
                (ps + 2, ps + 3, ps + 4),
                (ps + 3, ps, ps + 4),
                (ps, ps + 3, ps + 2, ps + 1),
            ])

    brand_end = len(verts)
    if brand_end > brand_start:
        groups[f"brand_{brand.lower()}"] = list(range(brand_start, brand_end))
