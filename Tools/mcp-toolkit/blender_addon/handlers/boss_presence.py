"""Boss monster visual presence enhancements for VeilBreakers.

Adds visual gravitas to boss-tier monsters through additional geometry:
crown/head features, aura rings, ground interaction meshes, and
environmental damage cracks.

All functions are pure Python with math-only dependencies (no bpy/bmesh).
Boss enhancements take raw mesh data and return additional geometry that
can be merged with the base monster mesh.

Provides:
  - BOSS_ENHANCEMENTS: Default enhancement configuration
  - BOSS_TYPES: Supported boss archetypes
  - enhance_boss_mesh: Apply all boss visual enhancements
  - generate_crown_feature: Unique head/top geometry
  - generate_aura_ring: Floating particle ring mesh
  - generate_ground_interaction: Tentacles/roots into ground
  - generate_environmental_damage: Cracks in ground around boss
  - compute_boss_tri_budget: Calculate increased geometry budget
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
FaceList = list[tuple[int, ...]]
VertList = list[Vec3]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOSS_ENHANCEMENTS: dict[str, Any] = {
    "increased_detail": {
        "subdivision_levels": 2,
        "tri_budget_multiplier": 3.0,
    },
    "crown_feature": True,
    "aura_geometry": True,
    "ground_interaction": True,
    "environmental_damage": True,
}

BOSS_TYPES = [
    "generic", "brute", "caster", "swarm_lord",
    "corrupted", "ancient", "abyssal",
]

# Brand-specific visual accents for boss enhancements
_BRAND_CROWN_STYLES: dict[str, str] = {
    "IRON": "spiked_crown",
    "SAVAGE": "bone_antlers",
    "SURGE": "crystal_halo",
    "VENOM": "acid_crest",
    "DREAD": "shadow_horns",
    "LEECH": "parasitic_tendrils",
    "GRACE": "feather_crown",
    "MEND": "crystal_wreath",
    "RUIN": "shattered_crown",
    "VOID": "void_crown",
}

_VALID_BRANDS = frozenset(_BRAND_CROWN_STYLES.keys())


# ---------------------------------------------------------------------------
# Vector math helpers
# ---------------------------------------------------------------------------


def _vec_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec_scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _vec_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_length(v: Vec3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _compute_bbox(verts: VertList) -> tuple[Vec3, Vec3]:
    """Compute axis-aligned bounding box from vertex list."""
    if not verts:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _merge_parts(
    *parts: tuple[VertList, FaceList],
) -> tuple[VertList, FaceList]:
    """Merge multiple (verts, faces) tuples, remapping face indices."""
    all_verts: VertList = []
    all_faces: FaceList = []
    for verts, faces in parts:
        offset = len(all_verts)
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces


# ---------------------------------------------------------------------------
# Budget calculation
# ---------------------------------------------------------------------------


def compute_boss_tri_budget(
    base_tri_count: int,
    multiplier: float = 3.0,
) -> dict[str, Any]:
    """Calculate the increased geometry budget for a boss monster.

    Args:
        base_tri_count: Triangle count of a regular monster.
        multiplier: Tri budget multiplier (default from BOSS_ENHANCEMENTS).

    Returns:
        Dict with base, multiplier, boss_budget, and overhead fields.
    """
    multiplier = max(1.0, multiplier)
    boss_budget = int(base_tri_count * multiplier)
    overhead = boss_budget - base_tri_count
    return {
        "base_tri_count": base_tri_count,
        "multiplier": multiplier,
        "boss_budget": boss_budget,
        "overhead": overhead,
    }


# ---------------------------------------------------------------------------
# Crown feature generator
# ---------------------------------------------------------------------------


def generate_crown_feature(
    mesh_bbox: tuple[Vec3, Vec3],
    brand: str = "VOID",
    crown_scale: float = 1.0,
    spike_count: int = 6,
) -> dict[str, Any]:
    """Generate unique head/top geometry for a boss monster.

    Creates a crown, antler, halo, or other head feature depending on
    the brand. Positioned at the top of the bounding box.

    Args:
        mesh_bbox: Bounding box (min, max) of the base mesh.
        brand: Boss brand, affects crown visual style.
        crown_scale: Scale multiplier for the crown.
        spike_count: Number of spikes/points in the crown.

    Returns:
        Dict with vertices, faces, crown_style, attachment_point.
    """
    brand = brand.upper()
    if brand not in _VALID_BRANDS:
        brand = "VOID"

    bb_min, bb_max = mesh_bbox
    top_y = bb_max[1]
    center_x = (bb_min[0] + bb_max[0]) * 0.5
    center_z = (bb_min[2] + bb_max[2]) * 0.5

    body_width = max(bb_max[0] - bb_min[0], bb_max[2] - bb_min[2])
    crown_radius = body_width * 0.3 * crown_scale
    spike_height = crown_radius * 0.8

    spike_count = max(3, spike_count)

    out_verts: VertList = []
    out_faces: FaceList = []

    # Base ring
    base_y = top_y + crown_radius * 0.1
    for i in range(spike_count):
        angle = 2.0 * math.pi * i / spike_count
        x = center_x + math.cos(angle) * crown_radius
        z = center_z + math.sin(angle) * crown_radius
        out_verts.append((x, base_y, z))

    # Inner ring (slightly higher, smaller)
    inner_radius = crown_radius * 0.6
    inner_y = base_y + spike_height * 0.15
    for i in range(spike_count):
        angle = 2.0 * math.pi * i / spike_count
        x = center_x + math.cos(angle) * inner_radius
        z = center_z + math.sin(angle) * inner_radius
        out_verts.append((x, inner_y, z))

    # Spike tips (between outer ring positions)
    for i in range(spike_count):
        angle = 2.0 * math.pi * (i + 0.5) / spike_count
        spike_r = crown_radius * 0.85
        x = center_x + math.cos(angle) * spike_r
        z = center_z + math.sin(angle) * spike_r
        # Vary spike height by brand: IRON = uniform, SAVAGE = irregular
        height_var = 1.0
        if brand == "SAVAGE":
            height_var = 0.7 + (i % 3) * 0.3
        elif brand == "RUIN":
            height_var = 0.5 + (i % 2) * 0.5
        out_verts.append((x, base_y + spike_height * height_var, z))

    # Connect base ring to inner ring (quads)
    for i in range(spike_count):
        i2 = (i + 1) % spike_count
        out_faces.append((i, i2, spike_count + i2, spike_count + i))

    # Connect inner ring to spike tips (triangles)
    for i in range(spike_count):
        i2 = (i + 1) % spike_count
        tip_idx = 2 * spike_count + i
        out_faces.append((spike_count + i, spike_count + i2, tip_idx))

    # Connect base ring to spike tips (triangles for outer face)
    for i in range(spike_count):
        i2 = (i + 1) % spike_count
        tip_idx = 2 * spike_count + i
        out_faces.append((i2, i, tip_idx))

    crown_style = _BRAND_CROWN_STYLES.get(brand, "generic_crown")
    attachment_point = (center_x, top_y, center_z)

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "crown_style": crown_style,
        "attachment_point": attachment_point,
        "brand": brand,
        "spike_count": spike_count,
    }


# ---------------------------------------------------------------------------
# Aura ring generator
# ---------------------------------------------------------------------------


def generate_aura_ring(
    mesh_bbox: tuple[Vec3, Vec3],
    ring_radius_multiplier: float = 1.5,
    ring_segments: int = 24,
    ring_thickness: float = 0.03,
    vertical_offset: float = 0.0,
) -> dict[str, Any]:
    """Generate a floating particle ring mesh around a boss.

    Creates a torus-like ring at the boss's torso height for VFX particle
    emission and visual aura effects.

    Args:
        mesh_bbox: Bounding box (min, max) of the base mesh.
        ring_radius_multiplier: Multiplier applied to body radius.
        ring_segments: Number of segments around the ring.
        ring_thickness: Cross-section radius of the ring tube.
        vertical_offset: Y offset from mesh center (0 = mid-height).

    Returns:
        Dict with vertices, faces, ring_radius, center, emission_points.
    """
    bb_min, bb_max = mesh_bbox
    center_x = (bb_min[0] + bb_max[0]) * 0.5
    center_y = (bb_min[1] + bb_max[1]) * 0.5 + vertical_offset
    center_z = (bb_min[2] + bb_max[2]) * 0.5

    body_radius = max(
        (bb_max[0] - bb_min[0]) * 0.5,
        (bb_max[2] - bb_min[2]) * 0.5,
    )
    ring_radius = body_radius * ring_radius_multiplier

    ring_segments = max(6, ring_segments)
    ring_thickness = max(0.005, ring_thickness)
    tube_segments = 6

    out_verts: VertList = []
    out_faces: FaceList = []
    emission_points: list[Vec3] = []

    # Generate torus
    for i in range(ring_segments):
        theta = 2.0 * math.pi * i / ring_segments
        ct, st = math.cos(theta), math.sin(theta)

        # Center of this tube cross-section
        tube_center = (
            center_x + ring_radius * ct,
            center_y,
            center_z + ring_radius * st,
        )
        emission_points.append(tube_center)

        for j in range(tube_segments):
            phi = 2.0 * math.pi * j / tube_segments
            cp, sp = math.cos(phi), math.sin(phi)
            # Point on tube surface
            out_verts.append((
                tube_center[0] + ring_thickness * cp * ct,
                tube_center[1] + ring_thickness * sp,
                tube_center[2] + ring_thickness * cp * st,
            ))

    # Connect tube segments into quads
    for i in range(ring_segments):
        i_next = (i + 1) % ring_segments
        for j in range(tube_segments):
            j_next = (j + 1) % tube_segments
            v0 = i * tube_segments + j
            v1 = i * tube_segments + j_next
            v2 = i_next * tube_segments + j_next
            v3 = i_next * tube_segments + j
            out_faces.append((v0, v1, v2, v3))

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "ring_radius": ring_radius,
        "center": (center_x, center_y, center_z),
        "emission_points": emission_points,
    }


# ---------------------------------------------------------------------------
# Ground interaction generator
# ---------------------------------------------------------------------------


def generate_ground_interaction(
    mesh_bbox: tuple[Vec3, Vec3],
    tendril_count: int = 5,
    tendril_length: float = 0.5,
    tendril_segments: int = 6,
    tendril_radius: float = 0.04,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate tentacles/roots growing into the ground from the boss base.

    Creates tapered cylindrical tendrils that emerge from the bottom of
    the boss mesh and plunge into the ground plane (Y=0).

    Args:
        mesh_bbox: Bounding box (min, max) of the base mesh.
        tendril_count: Number of tendrils to generate.
        tendril_length: Length of each tendril.
        tendril_segments: Number of height segments per tendril.
        tendril_radius: Base radius of each tendril.
        seed: Random seed for placement variation.

    Returns:
        Dict with vertices, faces, tendril_count, anchor_points.
    """
    bb_min, bb_max = mesh_bbox
    base_y = bb_min[1]
    center_x = (bb_min[0] + bb_max[0]) * 0.5
    center_z = (bb_min[2] + bb_max[2]) * 0.5

    body_radius = max(
        (bb_max[0] - bb_min[0]) * 0.5,
        (bb_max[2] - bb_min[2]) * 0.5,
    )

    tendril_count = max(1, tendril_count)
    tendril_segments = max(2, tendril_segments)
    tendril_radius = max(0.005, tendril_radius)
    tendril_length = max(0.05, tendril_length)
    ring_verts = 6  # vertices per ring of each tendril

    out_verts: VertList = []
    out_faces: FaceList = []
    anchor_points: list[Vec3] = []

    for ti in range(tendril_count):
        # Distribute tendrils around the base
        angle = 2.0 * math.pi * ti / tendril_count
        # Jitter
        jitter = ((ti * 7919 + seed * 6271) % 10000) / 10000.0 * 0.3
        angle += jitter

        spawn_x = center_x + math.cos(angle) * body_radius * 0.8
        spawn_z = center_z + math.sin(angle) * body_radius * 0.8
        anchor_points.append((spawn_x, base_y, spawn_z))

        v_base = len(out_verts)

        # Generate tapered tendril going downward
        for si in range(tendril_segments + 1):
            t = si / tendril_segments
            y = base_y - t * tendril_length
            # Taper radius from full to near-zero
            r = tendril_radius * (1.0 - t * 0.85)
            # Add slight curve outward
            curve_offset = math.sin(t * math.pi) * tendril_length * 0.2
            cx = spawn_x + math.cos(angle) * curve_offset
            cz = spawn_z + math.sin(angle) * curve_offset

            for vi in range(ring_verts):
                va = 2.0 * math.pi * vi / ring_verts
                out_verts.append((
                    cx + math.cos(va) * r,
                    y,
                    cz + math.sin(va) * r,
                ))

        # Connect rings into quads
        for si in range(tendril_segments):
            for vi in range(ring_verts):
                vi2 = (vi + 1) % ring_verts
                r0 = v_base + si * ring_verts
                r1 = v_base + (si + 1) * ring_verts
                out_faces.append((r0 + vi, r0 + vi2, r1 + vi2, r1 + vi))

        # Cap the tip
        tip_ring = v_base + tendril_segments * ring_verts
        tip_center_idx = len(out_verts)
        tip_y = base_y - tendril_length
        out_verts.append((spawn_x, tip_y, spawn_z))
        for vi in range(ring_verts):
            vi2 = (vi + 1) % ring_verts
            out_faces.append((tip_ring + vi, tip_ring + vi2, tip_center_idx))

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "tendril_count": tendril_count,
        "anchor_points": anchor_points,
    }


# ---------------------------------------------------------------------------
# Environmental damage generator
# ---------------------------------------------------------------------------


def generate_environmental_damage(
    mesh_bbox: tuple[Vec3, Vec3],
    crack_count: int = 8,
    crack_length: float = 1.0,
    crack_width: float = 0.05,
    crack_depth: float = 0.03,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate cracks in the ground around a boss monster.

    Creates radial crack geometry emanating from beneath the boss,
    suggesting the boss's weight or power is damaging the environment.

    Args:
        mesh_bbox: Bounding box (min, max) of the base mesh.
        crack_count: Number of radial cracks.
        crack_length: Maximum length of each crack.
        crack_width: Width of each crack.
        crack_depth: Depth of each crack below Y=0.
        seed: Random seed for crack variation.

    Returns:
        Dict with vertices, faces, crack_count, crack_endpoints.
    """
    bb_min, bb_max = mesh_bbox
    center_x = (bb_min[0] + bb_max[0]) * 0.5
    center_z = (bb_min[2] + bb_max[2]) * 0.5
    ground_y = bb_min[1]

    body_radius = max(
        (bb_max[0] - bb_min[0]) * 0.5,
        (bb_max[2] - bb_min[2]) * 0.5,
    )

    crack_count = max(1, crack_count)
    crack_length = max(0.1, crack_length)
    crack_width = max(0.005, crack_width)
    crack_depth = max(0.001, crack_depth)

    out_verts: VertList = []
    out_faces: FaceList = []
    crack_endpoints: list[tuple[Vec3, Vec3]] = []

    for ci in range(crack_count):
        angle = 2.0 * math.pi * ci / crack_count
        # Jitter the angle
        jitter = ((ci * 4217 + seed * 8923) % 10000) / 10000.0 * 0.2
        angle += jitter

        # Vary crack length
        len_var = 0.6 + ((ci * 3571 + seed * 2237) % 10000) / 10000.0 * 0.4
        this_length = crack_length * len_var

        # Start point (at body base)
        start_r = body_radius * 0.3
        start_x = center_x + math.cos(angle) * start_r
        start_z = center_z + math.sin(angle) * start_r

        # End point
        end_r = body_radius * 0.3 + this_length
        end_x = center_x + math.cos(angle) * end_r
        end_z = center_z + math.sin(angle) * end_r

        crack_endpoints.append(
            ((start_x, ground_y, start_z), (end_x, ground_y, end_z))
        )

        # Build crack as a tapered trench
        # Perpendicular direction for width
        perp_x = -math.sin(angle)
        perp_z = math.cos(angle)

        segments = 4
        v_base = len(out_verts)

        for si in range(segments + 1):
            t = si / segments
            # Interpolate position along crack
            px = start_x + (end_x - start_x) * t
            pz = start_z + (end_z - start_z) * t

            # Taper width: widest in middle, narrow at ends
            width_factor = math.sin(t * math.pi) * crack_width
            depth_factor = math.sin(t * math.pi) * crack_depth

            # 3 vertices per cross-section: left edge, bottom, right edge
            out_verts.append((
                px + perp_x * width_factor,
                ground_y,
                pz + perp_z * width_factor,
            ))
            out_verts.append((
                px,
                ground_y - depth_factor,
                pz,
            ))
            out_verts.append((
                px - perp_x * width_factor,
                ground_y,
                pz - perp_z * width_factor,
            ))

        # Connect cross-sections
        for si in range(segments):
            r0 = v_base + si * 3
            r1 = v_base + (si + 1) * 3
            # Left wall: left_edge[si], left_edge[si+1], bottom[si+1], bottom[si]
            out_faces.append((r0, r1, r1 + 1, r0 + 1))
            # Right wall: bottom[si], bottom[si+1], right_edge[si+1], right_edge[si]
            out_faces.append((r0 + 1, r1 + 1, r1 + 2, r0 + 2))

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "crack_count": crack_count,
        "crack_endpoints": crack_endpoints,
    }


# ---------------------------------------------------------------------------
# Main boss enhancement function
# ---------------------------------------------------------------------------


def enhance_boss_mesh(
    base_mesh: dict[str, Any],
    boss_type: str = "generic",
    brand: str = "VOID",
    enhancements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add boss-specific visual enhancements to a monster mesh.

    Takes a base monster mesh result dict (as returned by
    ``generate_monster_body``) and generates additional geometry layers
    for boss-tier visual presence.

    Args:
        base_mesh: Dict with at minimum 'vertices' and 'faces' lists.
            Optionally 'bounding_box'.
        boss_type: Boss archetype (e.g. 'brute', 'caster'). Affects scale.
        brand: Boss brand for visual style (e.g. 'VOID', 'IRON').
        enhancements: Override dict for which enhancements to apply.
            Defaults to BOSS_ENHANCEMENTS.

    Returns:
        Dict with:
          - vertices: All enhancement vertices combined
          - faces: All enhancement face tuples combined
          - base_vertex_count: Original mesh vertex count
          - enhancement_vertex_count: Additional vertices added
          - enhancement_face_count: Additional faces added
          - crown: Crown feature result dict
          - aura: Aura ring result dict
          - ground: Ground interaction result dict
          - damage: Environmental damage result dict
          - boss_type: The boss type used
          - brand: The brand used
          - tri_budget: Budget calculation dict
    """
    if enhancements is None:
        enhancements = dict(BOSS_ENHANCEMENTS)

    base_verts = base_mesh.get("vertices", [])
    base_faces = base_mesh.get("faces", [])

    # Compute bounding box
    if "bounding_box" in base_mesh:
        bbox = base_mesh["bounding_box"]
        mesh_bbox = (tuple(bbox[0]), tuple(bbox[1]))
    elif base_verts:
        mesh_bbox = _compute_bbox(base_verts)
    else:
        mesh_bbox = ((0.0, 0.0, 0.0), (1.0, 2.0, 1.0))

    # Boss type scaling
    type_scale = {
        "generic": 1.0,
        "brute": 1.3,
        "caster": 0.9,
        "swarm_lord": 1.1,
        "corrupted": 1.2,
        "ancient": 1.4,
        "abyssal": 1.5,
    }.get(boss_type, 1.0)

    brand_upper = brand.upper() if brand else "VOID"
    if brand_upper not in _VALID_BRANDS:
        brand_upper = "VOID"

    # Compute tri budget
    detail_cfg = enhancements.get("increased_detail", {})
    multiplier = detail_cfg.get("tri_budget_multiplier", 3.0) if isinstance(detail_cfg, dict) else 3.0
    tri_budget = compute_boss_tri_budget(len(base_faces), multiplier)

    # Generate enhancements
    parts: list[tuple[VertList, FaceList]] = []

    crown_result = None
    if enhancements.get("crown_feature", True):
        crown_result = generate_crown_feature(
            mesh_bbox,
            brand=brand_upper,
            crown_scale=type_scale,
            spike_count=max(4, int(6 * type_scale)),
        )
        parts.append((crown_result["vertices"], crown_result["faces"]))

    aura_result = None
    if enhancements.get("aura_geometry", True):
        aura_result = generate_aura_ring(
            mesh_bbox,
            ring_radius_multiplier=1.5 * type_scale,
        )
        parts.append((aura_result["vertices"], aura_result["faces"]))

    ground_result = None
    if enhancements.get("ground_interaction", True):
        ground_result = generate_ground_interaction(
            mesh_bbox,
            tendril_count=max(3, int(5 * type_scale)),
        )
        parts.append((ground_result["vertices"], ground_result["faces"]))

    damage_result = None
    if enhancements.get("environmental_damage", True):
        damage_result = generate_environmental_damage(
            mesh_bbox,
            crack_count=max(4, int(8 * type_scale)),
        )
        parts.append((damage_result["vertices"], damage_result["faces"]))

    # Merge all enhancement geometry
    if parts:
        merged_verts, merged_faces = _merge_parts(*parts)
    else:
        merged_verts, merged_faces = [], []

    return {
        "vertices": merged_verts,
        "faces": merged_faces,
        "base_vertex_count": len(base_verts),
        "enhancement_vertex_count": len(merged_verts),
        "enhancement_face_count": len(merged_faces),
        "crown": crown_result,
        "aura": aura_result,
        "ground": ground_result,
        "damage": damage_result,
        "boss_type": boss_type,
        "brand": brand_upper,
        "tri_budget": tri_budget,
    }
