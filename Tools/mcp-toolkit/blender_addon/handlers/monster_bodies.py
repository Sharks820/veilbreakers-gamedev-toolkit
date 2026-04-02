"""Advanced monster body type mesh generators for VeilBreakers.

Expands on the 6 basic monster body generators in procedural_meshes.py with
full body-type + brand feature system. Each body type produces anatomically
structured meshes with joint positions for auto-rigging and brand-specific
geometric features for VFX attachment.

Body types: humanoid, quadruped, amorphous, arachnid, serpent, insect
Brands: IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND, RUIN, VOID

All functions are pure Python with math-only dependencies (no bpy/bmesh).
"""

from __future__ import annotations

import math
from typing import Any

from .mesh_smoothing import smooth_assembled_mesh, add_organic_noise

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
FaceList = list[tuple[int, ...]]
VertList = list[Vec3]
MonsterMeshResult = dict[str, Any]



def _auto_generate_uvs(vertices):
    """Generate fallback UVs via bounding-box XZ projection (0-1 range)."""
    if not vertices:
        return []
    v0 = vertices[0]
    min_x = max_x = v0[0]
    min_z = max_z = v0[2]
    for v in vertices:
        if v[0] < min_x:
            min_x = v[0]
        elif v[0] > max_x:
            max_x = v[0]
        if v[2] < min_z:
            min_z = v[2]
        elif v[2] > max_z:
            max_z = v[2]
    inv_w = 1.0 / max(max_x - min_x, 1e-6)
    inv_h = 1.0 / max(max_z - min_z, 1e-6)
    return [((v[0] - min_x) * inv_w, (v[2] - min_z) * inv_h) for v in vertices]

# ---------------------------------------------------------------------------
# Brand feature definitions
# ---------------------------------------------------------------------------
BRAND_FEATURES: dict[str, dict[str, bool]] = {
    "IRON": {"chains": True, "metal_plates": True, "shackles": True},
    "SAVAGE": {"thorns": True, "bone_spurs": True, "claw_marks": True},
    "SURGE": {"crystal_growths": True, "translucent_skin": True},
    "VENOM": {"pustules": True, "acid_drip_points": True},
    "DREAD": {"shadow_tendrils": True, "fear_runes": True},
    "LEECH": {"parasitic_tendrils": True, "pulsing_veins": True},
    "GRACE": {"feather_details": True, "glow_points": True},
    "MEND": {"crystal_formations": True, "growth_patterns": True},
    "RUIN": {"fracture_lines": True, "floating_debris_points": True},
    "VOID": {"reality_cracks": True, "void_emission_points": True},
}

ALL_BRANDS = list(BRAND_FEATURES.keys())
ALL_BODY_TYPES = ["humanoid", "quadruped", "amorphous", "arachnid", "serpent", "insect"]

# ---------------------------------------------------------------------------
# Low-level mesh primitives (pure math, no bpy)
# ---------------------------------------------------------------------------


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


def _weld_coincident_vertices(
    verts: VertList,
    faces: FaceList,
    threshold: float = 0.001,
) -> tuple[VertList, FaceList]:
    """Bug 4 fix: merge vertices within threshold distance for connected topology.

    After merging primitives, coincident vertices at junction points remain
    separate, preventing smooth shading from working across parts. This welds
    them together.
    """
    n = len(verts)
    if n == 0:
        return verts, faces

    # Build a mapping from old vertex index to new (canonical) index
    remap: list[int] = list(range(n))
    # Use threshold squared to avoid sqrt in inner loop
    thresh_sq = threshold * threshold

    # Simple O(n^2) approach -- acceptable for meshes under ~10k verts
    # For larger meshes, a spatial hash would be needed
    for i in range(n):
        if remap[i] != i:
            continue  # already merged
        xi, yi, zi = verts[i]
        for j in range(i + 1, n):
            if remap[j] != j:
                continue  # already merged
            dx = verts[j][0] - xi
            dy = verts[j][1] - yi
            dz = verts[j][2] - zi
            if dx * dx + dy * dy + dz * dz < thresh_sq:
                remap[j] = i

    # Build compacted vertex list and final remap
    new_indices: dict[int, int] = {}
    new_verts: VertList = []
    for i in range(n):
        canonical = remap[i]
        if canonical not in new_indices:
            new_indices[canonical] = len(new_verts)
            # Average position of coincident vertices for smoother junction
            new_verts.append(verts[canonical])
        # Map this index to the compacted index
        remap[i] = new_indices[canonical]

    # Remap faces, skip degenerate faces (where vertices collapse)
    new_faces: FaceList = []
    for face in faces:
        new_face = tuple(remap[idx] for idx in face)
        # Remove duplicate consecutive vertices
        deduped = []
        for vi in new_face:
            if not deduped or deduped[-1] != vi:
                deduped.append(vi)
        # Also check wrap-around
        if len(deduped) > 1 and deduped[0] == deduped[-1]:
            deduped.pop()
        if len(deduped) >= 3:
            new_faces.append(tuple(deduped))

    return new_verts, new_faces


def _sphere(
    cx: float, cy: float, cz: float,
    radius: float, rings: int = 8, sectors: int = 12,
) -> tuple[VertList, FaceList]:
    """Generate a UV sphere centred at (cx, cy, cz)."""
    # Bug 9 fix: guard against rings < 2 which would crash face generation
    rings = max(rings, 2)
    sectors = max(sectors, 3)
    verts: VertList = []
    faces: FaceList = []
    # Bottom pole
    verts.append((cx, cy - radius, cz))
    for i in range(1, rings):
        phi = math.pi * i / rings
        y = cy - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2.0 * math.pi * j / sectors
            verts.append((cx + ring_r * math.cos(theta), y, cz + ring_r * math.sin(theta)))
    # Top pole
    verts.append((cx, cy + radius, cz))
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
    return verts, faces


def _tapered_cylinder(
    cx: float, cy_bottom: float, cz: float,
    r_bottom: float, r_top: float, height: float,
    segments: int = 12, rings: int = 1,
    cap_top: bool = True, cap_bottom: bool = True,
) -> tuple[VertList, FaceList]:
    """Generate a tapered cylinder along Y axis."""
    verts: VertList = []
    faces: FaceList = []
    total_rings = rings + 1
    for ring in range(total_rings):
        t = ring / max(rings, 1)
        y = cy_bottom + t * height
        r = r_bottom + t * (r_top - r_bottom)
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
        last = rings * segments
        faces.append(tuple(last + i for i in range(segments)))
    return verts, faces


def _cone(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float, segments: int = 12,
) -> tuple[VertList, FaceList]:
    """Generate a cone with apex at top."""
    verts: VertList = []
    faces: FaceList = []
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


def _box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
) -> tuple[VertList, FaceList]:
    """Generate an axis-aligned box."""
    hx, hy, hz = sx, sy, sz
    verts: VertList = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces: FaceList = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return verts, faces


def _torus_link(
    cx: float, cy: float, cz: float,
    major_r: float, minor_r: float,
    major_segs: int = 8, minor_segs: int = 4,
) -> tuple[VertList, FaceList]:
    """Generate a torus (chain link shape) lying in XZ plane."""
    verts: VertList = []
    faces: FaceList = []
    for i in range(major_segs):
        theta = 2.0 * math.pi * i / major_segs
        ct, st = math.cos(theta), math.sin(theta)
        for j in range(minor_segs):
            phi = 2.0 * math.pi * j / minor_segs
            cp, sp = math.cos(phi), math.sin(phi)
            r = major_r + minor_r * cp
            verts.append((cx + r * ct, cy + minor_r * sp, cz + r * st))
    for i in range(major_segs):
        i_next = (i + 1) % major_segs
        for j in range(minor_segs):
            j_next = (j + 1) % minor_segs
            v0 = i * minor_segs + j
            v1 = i * minor_segs + j_next
            v2 = i_next * minor_segs + j_next
            v3 = i_next * minor_segs + j
            faces.append((v0, v1, v2, v3))
    return verts, faces


def _deformed_sphere(
    cx: float, cy: float, cz: float,
    radius: float, noise_scale: float = 0.3,
    rings: int = 10, sectors: int = 12, seed: int = 0,
) -> tuple[VertList, FaceList]:
    """Generate a sphere with organic noise deformation."""
    verts: VertList = []
    faces: FaceList = []
    # Simple deterministic pseudo-noise based on vertex position
    def _noise(i: int, j: int) -> float:
        v = (i * 7919 + j * 6271 + seed * 1031) % 10000
        return (v / 10000.0 - 0.5) * 2.0 * noise_scale

    verts.append((cx, cy - radius * (1.0 + _noise(0, 0) * 0.5), cz))
    for i in range(1, rings):
        phi = math.pi * i / rings
        y_base = -radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2.0 * math.pi * j / sectors
            n = _noise(i, j)
            r = ring_r * (1.0 + n)
            y = cy + y_base * (1.0 + n * 0.3)
            verts.append((cx + r * math.cos(theta), y, cz + r * math.sin(theta)))
    verts.append((cx, cy + radius * (1.0 + _noise(rings, 0) * 0.5), cz))
    # Faces - same topology as regular sphere
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


def _compute_bbox(verts: VertList) -> tuple[Vec3, Vec3]:
    """Compute axis-aligned bounding box from vertex list."""
    if not verts:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


# ---------------------------------------------------------------------------
# Brand feature geometry generators
# ---------------------------------------------------------------------------


def _generate_chains(
    surface_points: list[Vec3], link_radius: float = 0.03,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate chain-link geometry along surface points.

    Returns (verts, faces, feature_points) where feature_points
    mark positions for VFX attachment.
    """
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for i, pt in enumerate(surface_points):
        # Alternate chain link orientation
        link_v, link_f = _torus_link(
            pt[0], pt[1], pt[2],
            major_r=link_radius * 2, minor_r=link_radius * 0.5,
            major_segs=6, minor_segs=3,
        )
        if i % 2 == 1:
            # Rotate 90 degrees around Y for interlocking links
            link_v = [(v[2] - pt[2] + pt[0], v[1], -(v[0] - pt[0]) + pt[2]) for v in link_v]
        parts.append((link_v, link_f))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_metal_plates(
    surface_points: list[Vec3], plate_size: float = 0.08,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate flat extruded metal plate patches."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for pt in surface_points:
        pv, pf = _box(pt[0], pt[1], pt[2], plate_size, plate_size * 0.1, plate_size * 0.8)
        parts.append((pv, pf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_shackles(
    joint_positions: dict[str, Vec3], shackle_r: float = 0.04,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate shackle torus rings at wrist/ankle joint positions."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    targets = ["left_wrist", "right_wrist", "left_ankle", "right_ankle"]
    for key in targets:
        if key in joint_positions:
            pt = joint_positions[key]
            sv, sf = _torus_link(pt[0], pt[1], pt[2], shackle_r, shackle_r * 0.3,
                                 major_segs=8, minor_segs=4)
            parts.append((sv, sf))
            feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_thorns(
    surface_points: list[Vec3], normals: list[Vec3], thorn_length: float = 0.06,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate cone extrusions along surface normals."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for pt, normal in zip(surface_points, normals):
        # Cone base at surface point, tip along normal
        base_r = thorn_length * 0.3
        tv, tf = _cone(pt[0], pt[1], pt[2], base_r, thorn_length, segments=5)
        # Rotate cone to align with normal (simplified - offset tip position)
        tip_x = pt[0] + normal[0] * thorn_length
        tip_y = pt[1] + normal[1] * thorn_length
        tip_z = pt[2] + normal[2] * thorn_length
        # Replace apex vertex
        tv[-1] = (tip_x, tip_y, tip_z)
        parts.append((tv, tf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_bone_spurs(
    surface_points: list[Vec3], normals: list[Vec3], spur_length: float = 0.05,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate bone spur protrusions (tapered cylinders)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for pt, normal in zip(surface_points, normals):
        sv, sf = _tapered_cylinder(
            pt[0], pt[1], pt[2],
            spur_length * 0.25, spur_length * 0.05, spur_length,
            segments=5, rings=1,
        )
        parts.append((sv, sf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_crystal_growths(
    surface_points: list[Vec3], crystal_size: float = 0.07,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate faceted crystal cluster geometry."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        # 2-3 crystals per cluster point
        n_crystals = 2 + (idx % 2)
        for ci in range(n_crystals):
            angle_off = ci * 2.0 * math.pi / n_crystals
            ox = math.cos(angle_off) * crystal_size * 0.3
            oz = math.sin(angle_off) * crystal_size * 0.3
            h = crystal_size * (0.8 + (ci % 3) * 0.3)
            cv, cf = _tapered_cylinder(
                pt[0] + ox, pt[1], pt[2] + oz,
                crystal_size * 0.15, crystal_size * 0.02, h,
                segments=5, rings=1,
            )
            parts.append((cv, cf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_pustules(
    surface_points: list[Vec3], pustule_radius: float = 0.04,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate sphere bumps for VENOM brand."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        r = pustule_radius * (0.7 + (idx % 3) * 0.2)
        pv, pf = _sphere(pt[0], pt[1], pt[2], r, rings=4, sectors=6)
        parts.append((pv, pf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_tendrils(
    surface_points: list[Vec3], tendril_length: float = 0.12,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate tendril geometry (used by DREAD, LEECH)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        # Curved tendril via multi-ring tapered cylinder
        segments = 5
        angle = (idx * 1.618) * math.pi  # golden angle for variety
        dx = math.cos(angle) * tendril_length * 0.3
        dz = math.sin(angle) * tendril_length * 0.3
        tv, tf = _tapered_cylinder(
            pt[0] + dx * 0.5, pt[1], pt[2] + dz * 0.5,
            tendril_length * 0.08, tendril_length * 0.02, tendril_length,
            segments=segments, rings=3,
        )
        # Apply slight curve to vertices
        curved: VertList = []
        for v in tv:
            t = (v[1] - pt[1]) / max(tendril_length, 0.001)
            curve = math.sin(t * math.pi * 0.5) * tendril_length * 0.2
            curved.append((v[0] + curve * math.cos(angle), v[1], v[2] + curve * math.sin(angle)))
        parts.append((curved, tf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_rune_marks(
    surface_points: list[Vec3], rune_size: float = 0.05,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate small flat rune marker geometry (DREAD fear runes)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for pt in surface_points:
        rv, rf = _box(pt[0], pt[1], pt[2], rune_size, rune_size * 0.02, rune_size)
        parts.append((rv, rf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_glow_points(
    surface_points: list[Vec3], glow_r: float = 0.02,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate small sphere markers for glow emission (GRACE, VOID)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for pt in surface_points:
        gv, gf = _sphere(pt[0], pt[1], pt[2], glow_r, rings=3, sectors=4)
        parts.append((gv, gf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_feather_details(
    surface_points: list[Vec3], feather_size: float = 0.06,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate flat feather-shaped quads for GRACE brand."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        angle = idx * 0.618 * math.pi
        dx = math.cos(angle) * feather_size * 0.1
        dz = math.sin(angle) * feather_size * 0.1
        fv, ff = _box(
            pt[0] + dx, pt[1], pt[2] + dz,
            feather_size * 0.15, feather_size * 0.01, feather_size * 0.5,
        )
        parts.append((fv, ff))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_fracture_lines(
    surface_points: list[Vec3], line_length: float = 0.08,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate thin box geometry representing fracture/crack lines (RUIN)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        angle = idx * 2.399  # golden angle
        dx = math.cos(angle) * line_length * 0.5
        dz = math.sin(angle) * line_length * 0.5
        lv, lf = _box(
            pt[0] + dx * 0.5, pt[1], pt[2] + dz * 0.5,
            line_length * 0.5, line_length * 0.02, line_length * 0.02,
        )
        parts.append((lv, lf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_debris_points(
    surface_points: list[Vec3], debris_size: float = 0.03,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate small floating box debris (RUIN floating_debris_points)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        # Offset upward slightly to simulate floating
        offset_y = debris_size * (1.5 + (idx % 3) * 0.5)
        dv, df = _box(pt[0], pt[1] + offset_y, pt[2], debris_size, debris_size, debris_size)
        parts.append((dv, df))
        feature_pts.append((pt[0], pt[1] + offset_y, pt[2]))
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


def _generate_void_cracks(
    surface_points: list[Vec3], crack_size: float = 0.05,
) -> tuple[VertList, FaceList, list[Vec3]]:
    """Generate angular crack geometry for VOID brand (reality_cracks)."""
    parts: list[tuple[VertList, FaceList]] = []
    feature_pts: list[Vec3] = []
    for idx, pt in enumerate(surface_points):
        # Thin angular shard
        angle = idx * 1.2
        dx = math.cos(angle) * crack_size
        dz = math.sin(angle) * crack_size
        cv, cf = _cone(
            pt[0] + dx * 0.2, pt[1], pt[2] + dz * 0.2,
            crack_size * 0.3, crack_size * 1.5, segments=4,
        )
        parts.append((cv, cf))
        feature_pts.append(pt)
    if parts:
        verts, faces = _merge_parts(*parts)
    else:
        verts, faces = [], []
    return verts, faces, feature_pts


# ---------------------------------------------------------------------------
# Brand feature application dispatch
# ---------------------------------------------------------------------------


def _apply_brand_features(
    brand: str,
    surface_sample_points: list[Vec3],
    surface_normals: list[Vec3],
    joint_positions: dict[str, Vec3],
    scale: float,
) -> tuple[VertList, FaceList, dict[str, list[Vec3]]]:
    """Apply brand-specific geometric features to a body mesh.

    Returns (feature_verts, feature_faces, brand_feature_points).
    """
    features = BRAND_FEATURES.get(brand, {})
    all_parts: list[tuple[VertList, FaceList]] = []
    brand_feature_points: dict[str, list[Vec3]] = {}

    s = scale

    if features.get("chains"):
        # Use every 3rd surface point for chain placement
        chain_pts = surface_sample_points[::3]
        v, f, pts = _generate_chains(chain_pts, link_radius=0.03 * s)
        all_parts.append((v, f))
        brand_feature_points["chains"] = pts

    if features.get("metal_plates"):
        plate_pts = surface_sample_points[1::4]
        v, f, pts = _generate_metal_plates(plate_pts, plate_size=0.08 * s)
        all_parts.append((v, f))
        brand_feature_points["metal_plates"] = pts

    if features.get("shackles"):
        v, f, pts = _generate_shackles(joint_positions, shackle_r=0.04 * s)
        all_parts.append((v, f))
        brand_feature_points["shackles"] = pts

    if features.get("thorns"):
        thorn_pts = surface_sample_points[::2]
        thorn_normals = surface_normals[::2]
        v, f, pts = _generate_thorns(thorn_pts, thorn_normals, thorn_length=0.06 * s)
        all_parts.append((v, f))
        brand_feature_points["thorns"] = pts

    if features.get("bone_spurs"):
        spur_pts = surface_sample_points[1::3]
        spur_normals = surface_normals[1::3]
        v, f, pts = _generate_bone_spurs(spur_pts, spur_normals, spur_length=0.05 * s)
        all_parts.append((v, f))
        brand_feature_points["bone_spurs"] = pts

    if features.get("claw_marks"):
        # Just record positions, no extra geometry (vertex-painted in material)
        brand_feature_points["claw_marks"] = surface_sample_points[2::4]

    if features.get("crystal_growths"):
        crystal_pts = surface_sample_points[::3]
        v, f, pts = _generate_crystal_growths(crystal_pts, crystal_size=0.07 * s)
        all_parts.append((v, f))
        brand_feature_points["crystal_growths"] = pts

    if features.get("translucent_skin"):
        # Mark regions, no geometry change (handled by material)
        brand_feature_points["translucent_skin"] = surface_sample_points[::5]

    if features.get("pustules"):
        pust_pts = surface_sample_points[::2]
        v, f, pts = _generate_pustules(pust_pts, pustule_radius=0.04 * s)
        all_parts.append((v, f))
        brand_feature_points["pustules"] = pts

    if features.get("acid_drip_points"):
        # Mark drip locations (particle emitter points)
        brand_feature_points["acid_drip_points"] = surface_sample_points[1::3]

    if features.get("shadow_tendrils"):
        tend_pts = surface_sample_points[::4]
        v, f, pts = _generate_tendrils(tend_pts, tendril_length=0.12 * s)
        all_parts.append((v, f))
        brand_feature_points["shadow_tendrils"] = pts

    if features.get("fear_runes"):
        rune_pts = surface_sample_points[2::5]
        v, f, pts = _generate_rune_marks(rune_pts, rune_size=0.05 * s)
        all_parts.append((v, f))
        brand_feature_points["fear_runes"] = pts

    if features.get("parasitic_tendrils"):
        tend_pts = surface_sample_points[1::3]
        v, f, pts = _generate_tendrils(tend_pts, tendril_length=0.1 * s)
        all_parts.append((v, f))
        brand_feature_points["parasitic_tendrils"] = pts

    if features.get("pulsing_veins"):
        # Mark vein paths (no geometry, used for shader animation)
        brand_feature_points["pulsing_veins"] = surface_sample_points[::4]

    if features.get("feather_details"):
        feat_pts = surface_sample_points[::3]
        v, f, pts = _generate_feather_details(feat_pts, feather_size=0.06 * s)
        all_parts.append((v, f))
        brand_feature_points["feather_details"] = pts

    if features.get("glow_points"):
        glow_pts = surface_sample_points[1::4]
        v, f, pts = _generate_glow_points(glow_pts, glow_r=0.02 * s)
        all_parts.append((v, f))
        brand_feature_points["glow_points"] = pts

    if features.get("crystal_formations"):
        cryst_pts = surface_sample_points[::3]
        v, f, pts = _generate_crystal_growths(cryst_pts, crystal_size=0.06 * s)
        all_parts.append((v, f))
        brand_feature_points["crystal_formations"] = pts

    if features.get("growth_patterns"):
        # Mark growth regions (shader-driven)
        brand_feature_points["growth_patterns"] = surface_sample_points[::5]

    if features.get("fracture_lines"):
        frac_pts = surface_sample_points[::3]
        v, f, pts = _generate_fracture_lines(frac_pts, line_length=0.08 * s)
        all_parts.append((v, f))
        brand_feature_points["fracture_lines"] = pts

    if features.get("floating_debris_points"):
        deb_pts = surface_sample_points[1::4]
        v, f, pts = _generate_debris_points(deb_pts, debris_size=0.03 * s)
        all_parts.append((v, f))
        brand_feature_points["floating_debris_points"] = pts

    if features.get("reality_cracks"):
        crack_pts = surface_sample_points[::3]
        v, f, pts = _generate_void_cracks(crack_pts, crack_size=0.05 * s)
        all_parts.append((v, f))
        brand_feature_points["reality_cracks"] = pts

    if features.get("void_emission_points"):
        brand_feature_points["void_emission_points"] = surface_sample_points[1::3]

    if all_parts:
        verts, faces = _merge_parts(*all_parts)
    else:
        verts, faces = [], []

    return verts, faces, brand_feature_points


# ---------------------------------------------------------------------------
# Surface sampling helpers
# ---------------------------------------------------------------------------


def _sample_surface_points(
    verts: VertList, count: int = 12,
    faces: FaceList | None = None,
) -> tuple[list[Vec3], list[Vec3]]:
    """Sample spatially distributed points using area-weighted face sampling.

    Bug 15 fix: the old approach (surface_sample_points[::3]) clustered
    features on dense mesh areas. This uses face-area weighting and a simple
    spatial spread heuristic to distribute points more evenly.
    """
    if not verts:
        return [], []

    # Compute centroid for normal estimation
    cx = sum(v[0] for v in verts) / len(verts)
    cy = sum(v[1] for v in verts) / len(verts)
    cz = sum(v[2] for v in verts) / len(verts)

    def _outward_normal(pt: Vec3) -> Vec3:
        dx = pt[0] - cx
        dy = pt[1] - cy
        dz = pt[2] - cz
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length > 1e-6:
            return (dx / length, dy / length, dz / length)
        return (0.0, 1.0, 0.0)

    if faces and len(faces) >= count:
        # Area-weighted sampling from face centroids
        face_data: list[tuple[float, Vec3]] = []
        for face in faces:
            if len(face) < 3:
                continue
            # Face centroid
            fcx = sum(verts[i][0] for i in face if i < len(verts)) / len(face)
            fcy = sum(verts[i][1] for i in face if i < len(verts)) / len(face)
            fcz = sum(verts[i][2] for i in face if i < len(verts)) / len(face)
            # Approximate area using first triangle
            p0 = verts[face[0]] if face[0] < len(verts) else (0, 0, 0)
            p1 = verts[face[1]] if face[1] < len(verts) else (0, 0, 0)
            p2 = verts[face[2]] if face[2] < len(verts) else (0, 0, 0)
            e1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
            e2 = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
            cross = (
                e1[1] * e2[2] - e1[2] * e2[1],
                e1[2] * e2[0] - e1[0] * e2[2],
                e1[0] * e2[1] - e1[1] * e2[0],
            )
            area = 0.5 * math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2)
            face_data.append((area, (fcx, fcy, fcz)))

        if not face_data:
            # Fallback to vertex stepping
            step = max(1, len(verts) // count)
            points = [verts[i] for i in range(0, len(verts), step)][:count]
            normals = [_outward_normal(pt) for pt in points]
            return points, normals

        # Sort by area descending and pick spread-out points
        face_data.sort(key=lambda x: x[0], reverse=True)
        total_area = sum(a for a, _ in face_data)
        if total_area < 1e-12:
            total_area = 1.0

        # Cumulative area stepping to pick evenly by area
        points: list[Vec3] = []
        area_step = total_area / count
        accumulated = 0.0
        next_threshold = area_step * 0.5
        for area, centroid in face_data:
            accumulated += area
            if accumulated >= next_threshold:
                # Check minimum distance from existing points
                min_dist_sq = float('inf')
                for existing in points:
                    d = ((centroid[0] - existing[0])**2 +
                         (centroid[1] - existing[1])**2 +
                         (centroid[2] - existing[2])**2)
                    if d < min_dist_sq:
                        min_dist_sq = d
                # Only add if not too close to existing point
                if not points or min_dist_sq > 0.001:
                    points.append(centroid)
                    next_threshold += area_step
                if len(points) >= count:
                    break

        normals = [_outward_normal(pt) for pt in points]
        return points, normals
    else:
        # Fallback: simple vertex stepping
        step = max(1, len(verts) // count)
        points = [verts[i] for i in range(0, len(verts), step)][:count]
        normals = [_outward_normal(pt) for pt in points]
        return points, normals


# ---------------------------------------------------------------------------
# Body type generators
# ---------------------------------------------------------------------------


def _generate_humanoid_body(scale: float) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate a humanoid monster body mesh.

    Torso: 8-segment cross-section x 6 spine segments
    Arms: 3 segments each (upper, lower, hand)
    Legs: 3 segments each (thigh, shin, foot)
    Head: sphere with monster features
    """
    s = scale
    parts: list[tuple[VertList, FaceList]] = []
    joints: dict[str, Vec3] = {}

    # -- Torso: 6 spine segments with 8-segment cross-section --
    torso_segs = 6
    cross_segs = 8
    torso_height = 0.8 * s
    torso_width_base = 0.2 * s
    torso_width_top = 0.25 * s
    torso_depth_base = 0.12 * s
    torso_depth_top = 0.15 * s
    hip_y = 0.9 * s

    tv, tf = _tapered_cylinder(
        0, hip_y, 0,
        torso_width_base, torso_width_top, torso_height,
        segments=cross_segs, rings=torso_segs,
        cap_top=True, cap_bottom=True,
    )
    # Flatten front-back for torso shape
    tv = [(v[0], v[1], v[2] * (torso_depth_base / torso_width_base)) for v in tv]
    parts.append((tv, tf))
    joints["spine_base"] = (0.0, hip_y, 0.0)
    joints["spine_mid"] = (0.0, hip_y + torso_height * 0.5, 0.0)
    joints["spine_top"] = (0.0, hip_y + torso_height, 0.0)

    # -- Head --
    head_r = 0.12 * s
    head_y = hip_y + torso_height + head_r * 1.5
    hv, hf = _sphere(0, head_y, 0, head_r, rings=6, sectors=8)
    parts.append((hv, hf))
    joints["head"] = (0.0, head_y, 0.0)

    # -- Neck --
    neck_y = hip_y + torso_height
    nv, nf = _tapered_cylinder(
        0, neck_y, 0,
        0.06 * s, 0.05 * s, head_r * 1.2,
        segments=6, rings=1,
    )
    parts.append((nv, nf))
    joints["neck"] = (0.0, neck_y + head_r * 0.6, 0.0)

    # -- Arms (both sides) --
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        shoulder_x = sm * torso_width_top * 1.1
        shoulder_y = hip_y + torso_height * 0.85
        joints[f"{side}_shoulder"] = (shoulder_x, shoulder_y, 0.0)

        # Upper arm
        # Bug 7 fix: shoulder (top) should be wider (0.045) than elbow (bottom, 0.04)
        # _tapered_cylinder takes r_bottom, r_top -- bottom is at shoulder_y - upper_len (elbow)
        upper_len = 0.28 * s
        uav, uaf = _tapered_cylinder(
            shoulder_x, shoulder_y - upper_len, 0,
            0.04 * s, 0.045 * s, upper_len,
            segments=6, rings=2,
        )
        parts.append((uav, uaf))

        # Elbow
        elbow_y = shoulder_y - upper_len
        joints[f"{side}_elbow"] = (shoulder_x, elbow_y, 0.0)

        # Lower arm
        lower_len = 0.25 * s
        lav, laf = _tapered_cylinder(
            shoulder_x, elbow_y - lower_len, 0,
            0.038 * s, 0.03 * s, lower_len,
            segments=6, rings=2,
        )
        parts.append((lav, laf))

        # Wrist
        wrist_y = elbow_y - lower_len
        joints[f"{side}_wrist"] = (shoulder_x, wrist_y, 0.0)

        # Hand
        hand_size = 0.05 * s
        hdv, hdf = _sphere(shoulder_x, wrist_y - hand_size, 0, hand_size, rings=4, sectors=6)
        parts.append((hdv, hdf))
        joints[f"{side}_hand"] = (shoulder_x, wrist_y - hand_size, 0.0)

    # -- Legs (both sides) --
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        hip_x = sm * torso_width_base * 0.6
        joints[f"{side}_hip"] = (hip_x, hip_y, 0.0)

        # Thigh
        thigh_len = 0.35 * s
        thv, thf = _tapered_cylinder(
            hip_x, hip_y - thigh_len, 0,
            0.06 * s, 0.055 * s, thigh_len,
            segments=6, rings=2,
        )
        parts.append((thv, thf))

        # Knee
        knee_y = hip_y - thigh_len
        joints[f"{side}_knee"] = (hip_x, knee_y, 0.0)

        # Shin
        shin_len = 0.32 * s
        shv, shf = _tapered_cylinder(
            hip_x, knee_y - shin_len, 0,
            0.05 * s, 0.035 * s, shin_len,
            segments=6, rings=2,
        )
        parts.append((shv, shf))

        # Ankle
        ankle_y = knee_y - shin_len
        joints[f"{side}_ankle"] = (hip_x, ankle_y, 0.0)

        # Foot
        foot_len = 0.1 * s
        foot_h = 0.04 * s
        fv, ff = _box(hip_x, ankle_y - foot_h, foot_len * 0.3,
                       0.04 * s, foot_h, foot_len * 0.5)
        parts.append((fv, ff))
        joints[f"{side}_foot"] = (hip_x, ankle_y - foot_h, foot_len * 0.3)

    # -- Pelvis sphere --
    pv, pf = _sphere(0, hip_y, 0, torso_width_base * 0.85, rings=4, sectors=cross_segs)
    parts.append((pv, pf))

    verts, faces = _merge_parts(*parts)
    return verts, faces, joints


def _generate_quadruped_body(scale: float) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate a four-legged beast body mesh.

    Spine: 10-segment chain
    4 legs with shoulder/hip ball joint topology
    Tail: 6-segment tapered
    Head: box-modeled skull with hinged jaw
    """
    s = scale
    parts: list[tuple[VertList, FaceList]] = []
    joints: dict[str, Vec3] = {}

    # -- Spine: 10-segment body --
    spine_segs = 10
    body_length = 1.2 * s
    body_radius = 0.15 * s
    body_height = 0.7 * s

    sv, sf = _tapered_cylinder(
        0, body_height, 0,
        body_radius, body_radius * 0.85, body_length,
        segments=8, rings=spine_segs,
        cap_top=True, cap_bottom=True,
    )
    # Rotate to lie along Z axis (swap Y ring direction to Z)
    sv = [(v[0], body_height + (v[2]) * 0.1, v[1] - body_height) for v in sv]
    # Actually build horizontal body properly
    parts_body: list[tuple[VertList, FaceList]] = []
    for i in range(spine_segs):
        t = i / (spine_segs - 1)
        seg_z = -body_length / 2 + t * body_length
        # Body wider at middle
        width_mult = 1.0 - 0.3 * abs(t - 0.5) * 2
        seg_r = body_radius * width_mult
        if i < spine_segs - 1:
            t2 = (i + 1) / (spine_segs - 1)
            seg_z2 = -body_length / 2 + t2 * body_length
            width_mult2 = 1.0 - 0.3 * abs(t2 - 0.5) * 2
            seg_r2 = body_radius * width_mult2
            bv, bf = _tapered_cylinder(
                0, body_height - seg_r * 0.5, seg_z,
                seg_r, seg_r2, seg_z2 - seg_z,
                segments=8, rings=1,
                cap_top=(i == spine_segs - 2), cap_bottom=(i == 0),
            )
            # Rotate: height is along Z here, need to swap
            bv = [(v[0], v[1], seg_z + (v[1] - (body_height - seg_r * 0.5))) for v in bv]
            bv = [(v[0], body_height, v[2]) for v in bv]
            parts_body.append((bv, bf))
        joints[f"spine_{i}"] = (0.0, body_height, seg_z)

    # Simpler approach: one long tapered cylinder along Z
    main_body_v, main_body_f = _tapered_cylinder(
        0, body_height - body_radius, 0,
        body_radius, body_radius * 0.7, body_length,
        segments=8, rings=spine_segs,
    )
    # Rotate body to lie along Z: swap Y-growth to Z-growth
    main_body_v_rotated: VertList = []
    for v in main_body_v:
        new_y = v[1] + body_radius  # lift up
        new_z = (v[1] - (body_height - body_radius)) - body_length / 2  # Y progress -> Z
        main_body_v_rotated.append((v[0], body_height, new_z))
    # Better: use actual rings along Z
    body_verts: VertList = []
    body_faces: FaceList = []
    ring_segs = 8
    for i in range(spine_segs + 1):
        t = i / spine_segs
        seg_z = -body_length / 2 + t * body_length
        env = math.sin(t * math.pi)  # fatter in middle
        r = body_radius * (0.7 + 0.3 * env)
        for j in range(ring_segs):
            angle = 2.0 * math.pi * j / ring_segs
            bx = math.cos(angle) * r
            by = body_height + math.sin(angle) * r * 0.7  # slightly flattened
            body_verts.append((bx, by, seg_z))
    for i in range(spine_segs):
        for j in range(ring_segs):
            j2 = (j + 1) % ring_segs
            r0 = i * ring_segs
            r1 = (i + 1) * ring_segs
            body_faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    # End caps
    body_faces.append(tuple(range(ring_segs - 1, -1, -1)))
    body_faces.append(tuple(spine_segs * ring_segs + j for j in range(ring_segs)))
    parts.append((body_verts, body_faces))

    # -- Head: box skull + jaw --
    head_z = body_length / 2 + 0.08 * s
    head_w = 0.08 * s
    head_h = 0.07 * s
    head_d = 0.12 * s
    hv, hf = _box(0, body_height + head_h * 0.3, head_z, head_w, head_h, head_d)
    parts.append((hv, hf))
    joints["head"] = (0.0, body_height + head_h * 0.3, head_z)

    # Jaw (hinged)
    jv, jf = _box(0, body_height - head_h * 0.5, head_z + head_d * 0.3,
                   head_w * 0.8, head_h * 0.3, head_d * 0.7)
    parts.append((jv, jf))
    joints["jaw"] = (0.0, body_height - head_h * 0.5, head_z + head_d * 0.3)

    # Neck
    nv, nf = _tapered_cylinder(
        0, body_height - 0.02 * s, body_length / 2 - 0.05 * s,
        body_radius * 0.5, head_w * 0.8, 0.15 * s,
        segments=6, rings=2,
    )
    parts.append((nv, nf))
    joints["neck"] = (0.0, body_height, body_length / 2)

    # -- 4 Legs with shoulder/hip joints --
    leg_positions = [
        ("front_left", -body_radius * 0.7, body_length * 0.3),
        ("front_right", body_radius * 0.7, body_length * 0.3),
        ("rear_left", -body_radius * 0.7, -body_length * 0.3),
        ("rear_right", body_radius * 0.7, -body_length * 0.3),
    ]
    for name, lx, lz in leg_positions:
        # Shoulder/hip ball joint
        ball_y = body_height - body_radius * 0.3
        bv2, bf2 = _sphere(lx, ball_y, lz, 0.04 * s, rings=4, sectors=6)
        parts.append((bv2, bf2))
        joints[f"{name}_shoulder"] = (lx, ball_y, lz)

        # Upper leg
        upper_len = 0.25 * s
        ulv, ulf = _tapered_cylinder(
            lx, ball_y - upper_len, lz,
            0.045 * s, 0.035 * s, upper_len,
            segments=6, rings=2,
        )
        parts.append((ulv, ulf))
        joints[f"{name}_knee"] = (lx, ball_y - upper_len, lz)

        # Lower leg
        lower_len = 0.28 * s
        llv, llf = _tapered_cylinder(
            lx, ball_y - upper_len - lower_len, lz,
            0.03 * s, 0.025 * s, lower_len,
            segments=6, rings=2,
        )
        parts.append((llv, llf))
        joints[f"{name}_ankle"] = (lx, ball_y - upper_len - lower_len, lz)

        # Paw/hoof
        paw_r = 0.03 * s
        foot_y = ball_y - upper_len - lower_len
        pv2, pf2 = _sphere(lx, foot_y - paw_r * 0.5, lz, paw_r, rings=3, sectors=6)
        parts.append((pv2, pf2))
        joints[f"{name}_foot"] = (lx, foot_y - paw_r * 0.5, lz)

    # -- Tail: 6-segment tapered --
    tail_segs = 6
    tail_len = 0.5 * s
    tail_r = 0.04 * s
    tail_verts: VertList = []
    tail_faces: FaceList = []
    tail_ring_segs = 6
    for i in range(tail_segs + 1):
        t = i / tail_segs
        tz = -body_length / 2 - t * tail_len
        tr = tail_r * (1.0 - t * 0.85)  # taper to tip
        ty = body_height + math.sin(t * math.pi * 0.3) * tail_len * 0.1  # slight curve up
        for j in range(tail_ring_segs):
            angle = 2.0 * math.pi * j / tail_ring_segs
            tail_verts.append((math.cos(angle) * tr, ty + math.sin(angle) * tr, tz))
    for i in range(tail_segs):
        for j in range(tail_ring_segs):
            j2 = (j + 1) % tail_ring_segs
            r0 = i * tail_ring_segs
            r1 = (i + 1) * tail_ring_segs
            tail_faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    tail_faces.append(tuple(range(tail_ring_segs - 1, -1, -1)))
    tail_faces.append(tuple(tail_segs * tail_ring_segs + j for j in range(tail_ring_segs)))
    parts.append((tail_verts, tail_faces))
    joints["tail_base"] = (0.0, body_height, -body_length / 2)
    joints["tail_tip"] = (0.0, body_height, -body_length / 2 - tail_len)

    verts, faces = _merge_parts(*parts)
    return verts, faces, joints


def _generate_amorphous_body(scale: float) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate an amorphous body mesh.

    Central mass: deformed sphere with organic noise
    Pseudopod extensions: tapered cylinders
    No traditional joints -- shape key positions in metadata
    """
    s = scale
    parts: list[tuple[VertList, FaceList]] = []
    joints: dict[str, Vec3] = {}

    # -- Central mass: deformed sphere --
    mass_r = 0.4 * s
    mass_y = mass_r * 1.1
    mv, mf = _deformed_sphere(
        0, mass_y, 0, mass_r,
        noise_scale=0.35, rings=10, sectors=12, seed=42,
    )
    parts.append((mv, mf))
    joints["center_mass"] = (0.0, mass_y, 0.0)

    # -- Pseudopod extensions (4-6 tentacle-like extensions) --
    n_pods = 5
    for i in range(n_pods):
        angle = 2.0 * math.pi * i / n_pods + 0.3
        pod_len = (0.3 + (i % 3) * 0.1) * s
        pod_r = 0.06 * s
        base_x = math.cos(angle) * mass_r * 0.7
        base_z = math.sin(angle) * mass_r * 0.7
        base_y = mass_y - mass_r * 0.3

        # Multi-ring tapered cylinder for pseudopod
        pod_ring_segs = 6
        pod_segs = 5
        pod_verts: VertList = []
        pod_faces: FaceList = []
        for si in range(pod_segs + 1):
            t = si / pod_segs
            px = base_x + math.cos(angle) * t * pod_len
            py = base_y - t * pod_len * 0.3  # droop
            pz = base_z + math.sin(angle) * t * pod_len
            pr = pod_r * (1.0 - t * 0.8)
            for j in range(pod_ring_segs):
                a = 2.0 * math.pi * j / pod_ring_segs
                pod_verts.append((
                    px + math.cos(a) * pr,
                    py + math.sin(a) * pr,
                    pz,
                ))
        for si in range(pod_segs):
            for j in range(pod_ring_segs):
                j2 = (j + 1) % pod_ring_segs
                r0 = si * pod_ring_segs
                r1 = (si + 1) * pod_ring_segs
                pod_faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
        pod_faces.append(tuple(range(pod_ring_segs - 1, -1, -1)))
        pod_faces.append(tuple(pod_segs * pod_ring_segs + j for j in range(pod_ring_segs)))
        parts.append((pod_verts, pod_faces))

        tip_x = base_x + math.cos(angle) * pod_len
        tip_y = base_y - pod_len * 0.3
        tip_z = base_z + math.sin(angle) * pod_len
        joints[f"pseudopod_{i}_base"] = (base_x, base_y, base_z)
        joints[f"pseudopod_{i}_tip"] = (tip_x, tip_y, tip_z)

    # Shape key reference positions (for amorphous deformation)
    joints["shape_key_expand"] = (0.0, mass_y + mass_r * 0.5, 0.0)
    joints["shape_key_contract"] = (0.0, mass_y - mass_r * 0.3, 0.0)
    joints["shape_key_lean_forward"] = (0.0, mass_y, mass_r * 0.5)

    verts, faces = _merge_parts(*parts)
    return verts, faces, joints


def _generate_arachnid_body(scale: float) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate an arachnid (spider-like) body mesh.

    Cephalothorax: elongated sphere
    8 legs: 4 segments each
    Mandibles/fangs
    Abdomen: large sphere (egg sac for Broodmother)
    """
    s = scale
    parts: list[tuple[VertList, FaceList]] = []
    joints: dict[str, Vec3] = {}

    body_height = 0.35 * s

    # -- Cephalothorax: elongated sphere --
    ceph_r = 0.12 * s
    ceph_y = body_height
    ceph_z = 0.1 * s
    cv, cf = _sphere(0, ceph_y, ceph_z, ceph_r, rings=6, sectors=8)
    # Elongate along Z
    cv = [(v[0], v[1], v[2] * 1.4) for v in cv]
    parts.append((cv, cf))
    joints["cephalothorax"] = (0.0, ceph_y, ceph_z)

    # -- Abdomen: large sphere --
    abd_r = 0.18 * s
    abd_z = -0.25 * s
    av, af = _sphere(0, body_height + 0.02 * s, abd_z, abd_r, rings=8, sectors=10)
    # Elongate abdomen vertically
    av = [(v[0], v[1] * 1.1, v[2] * 1.3) for v in av]
    parts.append((av, af))
    joints["abdomen"] = (0.0, body_height + 0.02 * s, abd_z)

    # -- Pedicel (waist connecting cephalothorax to abdomen) --
    ped_v, ped_f = _tapered_cylinder(
        0, body_height - 0.02 * s, -0.05 * s,
        0.04 * s, 0.03 * s, 0.08 * s,
        segments=6, rings=1,
    )
    parts.append((ped_v, ped_f))

    # -- 8 Legs: 4 segments each --
    leg_angles = [
        0.3, 0.8, 1.3, 1.8,  # left side (positive X)
        -0.3, -0.8, -1.3, -1.8,  # right side (negative X -> map to pi+angle)
    ]
    for li in range(8):
        side = "left" if li < 4 else "right"
        leg_idx = li if li < 4 else li - 4
        side_mult = 1.0 if li < 4 else -1.0

        # Leg root angle from body center
        base_angle = abs(leg_angles[li])
        root_x = side_mult * math.cos(base_angle) * ceph_r * 0.9
        root_z = ceph_z + math.sin(base_angle) * ceph_r * 0.5
        root_y = body_height

        joints[f"leg_{side}_{leg_idx}_root"] = (root_x, root_y, root_z)

        # Segment lengths - legs reach outward and down
        seg_lengths = [0.12 * s, 0.15 * s, 0.18 * s, 0.12 * s]
        seg_radii = [0.02 * s, 0.015 * s, 0.012 * s, 0.008 * s]

        prev_x, prev_y, prev_z = root_x, root_y, root_z
        for si in range(4):
            t = si / 3.0
            # Coxa goes up, femur/patella go out, tarsus goes down
            if si == 0:
                # Coxa: slight upward
                dx = side_mult * seg_lengths[si] * 0.7
                dy = seg_lengths[si] * 0.5
                dz = 0
            elif si == 1:
                # Femur: outward and slightly up
                dx = side_mult * seg_lengths[si] * 0.8
                dy = seg_lengths[si] * 0.2
                dz = 0
            elif si == 2:
                # Tibia: outward and down
                dx = side_mult * seg_lengths[si] * 0.5
                dy = -seg_lengths[si] * 0.8
                dz = 0
            else:
                # Tarsus: down to ground
                dx = side_mult * seg_lengths[si] * 0.1
                dy = -seg_lengths[si] * 0.9
                dz = 0

            end_x = prev_x + dx
            end_y = prev_y + dy
            end_z = prev_z + dz

            # Create segment cylinder
            seg_len = math.sqrt(dx * dx + dy * dy + dz * dz)
            lv, lf = _tapered_cylinder(
                prev_x, prev_y, prev_z,
                seg_radii[si], seg_radii[si] * 0.7, seg_len,
                segments=5, rings=1,
                cap_top=True, cap_bottom=True,
            )
            parts.append((lv, lf))

            joint_name = ["coxa", "femur", "tibia", "tarsus"][si]
            joints[f"leg_{side}_{leg_idx}_{joint_name}"] = (end_x, end_y, end_z)

            prev_x, prev_y, prev_z = end_x, end_y, end_z

    # -- Mandibles/fangs --
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        fang_x = sm * 0.03 * s
        fang_y = body_height - 0.02 * s
        fang_z = ceph_z + ceph_r * 1.3
        fv, ff = _cone(
            fang_x, fang_y - 0.08 * s, fang_z,
            0.015 * s, 0.08 * s, segments=5,
        )
        parts.append((fv, ff))
        joints[f"fang_{side}"] = (fang_x, fang_y, fang_z)

    # Eyes (cluster of small spheres)
    for ei in range(4):
        ex = (ei % 2 - 0.5) * 0.04 * s
        ey = body_height + ceph_r * 0.6
        ez = ceph_z + ceph_r * 0.9 + ei * 0.01 * s
        ev, ef = _sphere(ex, ey, ez, 0.015 * s, rings=3, sectors=4)
        parts.append((ev, ef))

    verts, faces = _merge_parts(*parts)
    return verts, faces, joints


def _generate_serpent_body(scale: float) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate a serpent body mesh.

    20+ segment spine chain
    Tapered body (thick at center, thin at tail)
    Hood geometry (flared neck)
    Needle fangs
    """
    s = scale
    parts: list[tuple[VertList, FaceList]] = []
    joints: dict[str, Vec3] = {}

    # -- Main body: 24 segment spine chain --
    spine_segs = 24
    body_length = 2.5 * s
    max_radius = 0.1 * s
    ring_segs = 10

    body_verts: VertList = []
    body_faces: FaceList = []

    for i in range(spine_segs + 1):
        t = i / spine_segs
        # Z position along body length
        seg_z = t * body_length - body_length / 2

        # Radius envelope: thin at head, thick at center, thin at tail
        envelope = math.sin(t * math.pi)
        if t < 0.15:
            envelope = t / 0.15 * math.sin(0.15 * math.pi)
        r = max_radius * max(0.05, envelope)

        # Slight S-curve
        seg_x = 0.05 * s * math.sin(t * math.pi * 2.5)
        # Body rests on ground
        seg_y = r + 0.01 * s

        for j in range(ring_segs):
            angle = 2.0 * math.pi * j / ring_segs
            bx = seg_x + math.cos(angle) * r * 1.1  # slightly wider than tall
            by = seg_y + math.sin(angle) * r * 0.85
            body_verts.append((bx, by, seg_z))

        if i % 3 == 0:
            joints[f"spine_{i}"] = (seg_x, seg_y, seg_z)

    for i in range(spine_segs):
        for j in range(ring_segs):
            j2 = (j + 1) % ring_segs
            r0 = i * ring_segs
            r1 = (i + 1) * ring_segs
            body_faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    body_faces.append(tuple(range(ring_segs - 1, -1, -1)))
    body_faces.append(tuple(spine_segs * ring_segs + j for j in range(ring_segs)))
    parts.append((body_verts, body_faces))

    # -- Hood geometry (flared neck) --
    head_z = body_length / 2
    hood_segs = 6
    hood_width = 0.2 * s
    hood_height = 0.15 * s
    hood_verts: VertList = []
    hood_faces: FaceList = []

    for i in range(hood_segs + 1):
        t = i / hood_segs
        hz = head_z - 0.05 * s + t * hood_height * 0.3
        hy = 0.08 * s + t * hood_height
        # Hood flares outward from body then tapers
        flare = math.sin(t * math.pi)
        hw = 0.04 * s + flare * hood_width
        hd = 0.02 * s  # thin
        for j in range(8):
            angle = 2.0 * math.pi * j / 8
            hx = math.cos(angle) * hw
            hy_v = hy + math.sin(angle) * hd
            hood_verts.append((hx, hy_v, hz))

    for i in range(hood_segs):
        for j in range(8):
            j2 = (j + 1) % 8
            r0 = i * 8
            r1 = (i + 1) * 8
            hood_faces.append((r0 + j, r0 + j2, r1 + j2, r1 + j))
    parts.append((hood_verts, hood_faces))
    joints["hood_center"] = (0.0, 0.08 * s + hood_height * 0.5, head_z)

    # -- Head --
    head_y = 0.1 * s + hood_height
    hv, hf = _sphere(0, head_y, head_z + 0.05 * s, 0.05 * s, rings=5, sectors=8)
    # Elongate for snake head
    hv = [(v[0], v[1], v[2] * 1.5) for v in hv]
    parts.append((hv, hf))
    joints["head"] = (0.0, head_y, head_z + 0.05 * s)

    # -- Needle fangs --
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        fang_x = sm * 0.015 * s
        fang_y = head_y - 0.03 * s
        fang_z = head_z + 0.1 * s
        fv, ff = _cone(
            fang_x, fang_y - 0.06 * s, fang_z,
            0.005 * s, 0.06 * s, segments=4,
        )
        parts.append((fv, ff))
        joints[f"fang_{side}"] = (fang_x, fang_y, fang_z)

    # Eyes
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        ev, ef = _sphere(
            sm * 0.025 * s, head_y + 0.02 * s, head_z + 0.08 * s,
            0.01 * s, rings=3, sectors=4,
        )
        parts.append((ev, ef))

    joints["tail_tip"] = (0.0, 0.01 * s, -body_length / 2)

    verts, faces = _merge_parts(*parts)
    return verts, faces, joints


def _generate_insect_body(scale: float) -> tuple[VertList, FaceList, dict[str, Vec3]]:
    """Generate an insect body mesh.

    3-segment thorax
    6 legs: thin segmented cylinders
    4 wing membranes (alpha-ready)
    Compound eyes: faceted sphere
    """
    s = scale
    parts: list[tuple[VertList, FaceList]] = []
    joints: dict[str, Vec3] = {}

    body_height = 0.2 * s

    # -- 3-segment thorax --
    segment_sizes = [
        (0.05 * s, body_height + 0.02 * s, 0.08 * s),   # head
        (0.06 * s, body_height, 0.0),                      # thorax
        (0.08 * s, body_height - 0.01 * s, -0.12 * s),    # abdomen
    ]
    segment_names = ["head_segment", "thorax", "abdomen"]

    for idx, ((sr, sy, sz), name) in enumerate(zip(segment_sizes, segment_names)):
        sv, sf = _sphere(0, sy, sz, sr, rings=6, sectors=8)
        # Elongate abdomen
        if idx == 2:
            sv = [(v[0], v[1], v[2] * 1.5) for v in sv]
        parts.append((sv, sf))
        joints[name] = (0.0, sy, sz)

    # Connectors between segments
    for i in range(2):
        s1 = segment_sizes[i]
        s2 = segment_sizes[i + 1]
        cr = min(s1[0], s2[0]) * 0.4
        cv, cf = _tapered_cylinder(
            0, min(s1[1], s2[1]) - cr * 0.5,
            (s1[2] + s2[2]) / 2,
            cr, cr * 0.7, abs(s2[2] - s1[2]) * 0.4,
            segments=6, rings=1,
        )
        parts.append((cv, cf))

    # -- 6 Legs: thin segmented cylinders (3 pairs) --
    thorax_z = 0.0
    thorax_r = 0.06 * s
    leg_spacing = [-0.03 * s, 0.0, 0.03 * s]  # Z offsets for 3 pairs

    for pair_idx, leg_z_off in enumerate(leg_spacing):
        for side, sm in [("left", 1.0), ("right", -1.0)]:
            leg_name = f"leg_{side}_{pair_idx}"
            root_x = sm * thorax_r * 0.8
            root_y = body_height - 0.02 * s
            root_z = thorax_z + leg_z_off

            joints[f"{leg_name}_root"] = (root_x, root_y, root_z)

            # 3 segments per leg: coxa, femur, tarsus
            seg_lengths = [0.06 * s, 0.08 * s, 0.06 * s]
            seg_radii = [0.008 * s, 0.006 * s, 0.004 * s]

            prev_x, prev_y, prev_z = root_x, root_y, root_z
            for si in range(3):
                if si == 0:
                    # Coxa: outward
                    dx = sm * seg_lengths[si] * 0.8
                    dy = seg_lengths[si] * 0.3
                    dz = 0
                elif si == 1:
                    # Femur: outward and down
                    dx = sm * seg_lengths[si] * 0.6
                    dy = -seg_lengths[si] * 0.7
                    dz = 0
                else:
                    # Tarsus: down to ground
                    dx = sm * seg_lengths[si] * 0.1
                    dy = -seg_lengths[si] * 0.9
                    dz = 0

                lv, lf = _tapered_cylinder(
                    prev_x, prev_y, prev_z,
                    seg_radii[si], seg_radii[si] * 0.6, seg_lengths[si],
                    segments=4, rings=1,
                )
                parts.append((lv, lf))

                end_x = prev_x + dx
                end_y = prev_y + dy
                end_z = prev_z + dz
                joint_names = ["coxa", "femur", "tarsus"]
                joints[f"{leg_name}_{joint_names[si]}"] = (end_x, end_y, end_z)
                prev_x, prev_y, prev_z = end_x, end_y, end_z

    # -- 4 Wing membranes (alpha-ready) --
    wing_positions = [
        ("wing_front_left", 1.0, 0.02 * s),
        ("wing_front_right", -1.0, 0.02 * s),
        ("wing_rear_left", 1.0, -0.03 * s),
        ("wing_rear_right", -1.0, -0.03 * s),
    ]

    for wing_name, sm, wz_off in wing_positions:
        wing_len = 0.2 * s if "front" in wing_name else 0.15 * s
        wing_w = 0.08 * s if "front" in wing_name else 0.06 * s

        # Wing as thin flat geometry (2 triangles)
        root_x = sm * thorax_r * 0.3
        root_y = body_height + thorax_r * 0.5
        root_z = thorax_z + wz_off

        tip_x = sm * wing_len
        tip_y = root_y + wing_w * 0.3
        mid_x = sm * wing_len * 0.6
        mid_y = root_y + wing_w * 0.1

        wing_verts: VertList = [
            (root_x, root_y, root_z),
            (tip_x, tip_y, root_z + wing_w * 0.3),
            (mid_x, mid_y, root_z - wing_w * 0.3),
            (tip_x, tip_y - wing_w * 0.2, root_z),
        ]
        wing_faces: FaceList = [
            (0, 1, 3),
            (0, 3, 2),
        ]
        parts.append((wing_verts, wing_faces))
        joints[wing_name] = (root_x, root_y, root_z)

    # -- Compound eyes: faceted spheres --
    head_sz = segment_sizes[0]
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        eye_x = sm * head_sz[0] * 0.7
        eye_y = head_sz[1] + head_sz[0] * 0.4
        eye_z = head_sz[2] + head_sz[0] * 0.5
        # Low-poly sphere for faceted look
        ev, ef = _sphere(eye_x, eye_y, eye_z, head_sz[0] * 0.35, rings=4, sectors=5)
        parts.append((ev, ef))
        joints[f"eye_{side}"] = (eye_x, eye_y, eye_z)

    # -- Antennae --
    for side, sm in [("left", -1.0), ("right", 1.0)]:
        ant_x = sm * head_sz[0] * 0.3
        ant_y = head_sz[1] + head_sz[0] * 0.8
        ant_z = head_sz[2] + head_sz[0] * 0.3
        ant_v, ant_f = _tapered_cylinder(
            ant_x, ant_y, ant_z,
            0.003 * s, 0.001 * s, 0.12 * s,
            segments=4, rings=3,
        )
        parts.append((ant_v, ant_f))
        joints[f"antenna_{side}"] = (ant_x, ant_y + 0.12 * s, ant_z)

    verts, faces = _merge_parts(*parts)
    return verts, faces, joints


# ---------------------------------------------------------------------------
# Main dispatch function
# ---------------------------------------------------------------------------

# Body type dispatcher
_BODY_GENERATORS = {
    "humanoid": _generate_humanoid_body,
    "quadruped": _generate_quadruped_body,
    "amorphous": _generate_amorphous_body,
    "arachnid": _generate_arachnid_body,
    "serpent": _generate_serpent_body,
    "insect": _generate_insect_body,
}


def _brand_material_region(brand: str) -> str:
    """Map a brand name to its material region tag.

    Returns a material region string for brand-specific geometry faces.
    Brands are grouped into material categories:
    - Metal brands (IRON) -> "brand_metal"
    - Organic brands (SAVAGE, VENOM, LEECH) -> "brand_organic"
    - Crystal/energy brands (SURGE, GRACE, MEND) -> "brand_crystal"
    - Dark/void brands (DREAD, RUIN, VOID) -> "brand_dark"
    """
    metal_brands = {"IRON"}
    organic_brands = {"SAVAGE", "VENOM", "LEECH"}
    crystal_brands = {"SURGE", "GRACE", "MEND"}
    # DREAD, RUIN, VOID fall through to dark
    if brand in metal_brands:
        return "brand_metal"
    elif brand in organic_brands:
        return "brand_organic"
    elif brand in crystal_brands:
        return "brand_crystal"
    else:
        return "brand_dark"


def generate_monster_body(
    body_type: str = "humanoid",
    brand: str = "IRON",
    scale: float = 1.0,
) -> MonsterMeshResult:
    """Generate a monster body mesh with brand-specific features.

    Args:
        body_type: One of "humanoid", "quadruped", "amorphous", "arachnid",
                   "serpent", "insect".
        brand: One of "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD", "LEECH",
               "GRACE", "MEND", "RUIN", "VOID".
        scale: Scale multiplier (0.5 for small, 2.0 for large).

    Returns:
        Dict with vertices, faces, body_type, brand, joint_positions,
        brand_feature_points, and bounding_box.
    """
    if body_type not in _BODY_GENERATORS:
        raise ValueError(
            f"Unknown body_type '{body_type}'. "
            f"Valid types: {', '.join(_BODY_GENERATORS.keys())}"
        )
    if brand not in BRAND_FEATURES:
        raise ValueError(
            f"Unknown brand '{brand}'. "
            f"Valid brands: {', '.join(BRAND_FEATURES.keys())}"
        )

    # Generate base body
    base_verts, base_faces, joint_positions = _BODY_GENERATORS[body_type](scale)

    # Build material regions: base body faces -> "body_skin"
    material_regions: dict[int, str] = {
        fi: "body_skin" for fi in range(len(base_faces))
    }

    # Sample surface points for brand feature placement (Bug 15: pass faces for area-weighted)
    surface_points, surface_normals = _sample_surface_points(base_verts, count=16, faces=base_faces)

    # Apply brand features
    feature_verts, feature_faces, brand_feature_points = _apply_brand_features(
        brand, surface_points, surface_normals, joint_positions, scale,
    )

    # Bug 4 fix: weld coincident vertices on base body before merging brand features
    base_verts, base_faces = _weld_coincident_vertices(base_verts, base_faces)
    # Rebuild material regions after welding (face count may change)
    material_regions = {fi: "body_skin" for fi in range(len(base_faces))}

    # Merge base body with brand features
    if feature_verts:
        base_face_count = len(base_faces)
        all_verts, all_faces = _merge_parts(
            (base_verts, base_faces),
            (feature_verts, feature_faces),
        )
        # Tag brand feature faces with brand-specific material region
        brand_region = _brand_material_region(brand)
        for fi in range(base_face_count, len(all_faces)):
            material_regions[fi] = brand_region
    else:
        all_verts = base_verts
        all_faces = base_faces

    # Smooth assembled geometry to eliminate primitive junctions
    all_verts = smooth_assembled_mesh(
        all_verts, all_faces, smooth_iterations=3,
    )
    # Add organic imperfection noise
    all_verts = add_organic_noise(
        all_verts, faces=all_faces, strength=0.003 * scale,
    )

    # Compute bounding box
    bbox = _compute_bbox(all_verts)

    return {
        "vertices": all_verts,
        "faces": all_faces,
        "uvs": _auto_generate_uvs(all_verts),
        "body_type": body_type,
        "brand": brand,
        "scale": scale,
        "joint_positions": joint_positions,
        "brand_feature_points": brand_feature_points,
        "material_regions": material_regions,
        "bounding_box": bbox,
        "vertex_count": len(all_verts),
        "face_count": len(all_faces),
        "subdivision_levels": {"viewport": 1, "render": 2},
        "smooth_shading": True,
    }
