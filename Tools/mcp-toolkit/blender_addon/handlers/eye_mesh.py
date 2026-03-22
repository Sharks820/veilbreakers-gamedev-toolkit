"""Eye mesh generation for VeilBreakers characters.

Generates anatomically structured two-layer eye meshes (inner eyeball +
outer cornea) with proper UV mapping for iris/pupil/sclera textures and
material slot assignments for multi-material rendering.

All functions are pure Python -- no bpy/bmesh imports. Returns mesh specs
with vertices, faces, UV coordinates, and material slot assignments.

Usage:
    from .eye_mesh import generate_eye_pair, generate_eye_mesh

    # Single eye
    eye = generate_eye_mesh(radius=0.012)

    # Pair positioned for a head
    pair = generate_eye_pair(head_center=(0, 0, 1.64), head_radius=0.10)
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
VertList = list[Vec3]
FaceList = list[tuple[int, ...]]
UVList = list[Vec2]
EyeMeshResult = dict[str, Any]


# ---------------------------------------------------------------------------
# UV sphere generator with UV coordinates
# ---------------------------------------------------------------------------


def _uv_sphere(
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    rings: int,
    sectors: int,
) -> tuple[VertList, FaceList, UVList]:
    """Generate a UV sphere with per-vertex UV coordinates.

    UV mapping: U wraps around the sphere (0..1 = full circle),
    V goes from bottom pole (0) to top pole (1).

    Returns (vertices, faces, uvs) where uvs has one entry per vertex.
    """
    verts: VertList = []
    uvs: UVList = []
    faces: FaceList = []

    # Bottom pole
    verts.append((cx, cy, cz - radius))
    uvs.append((0.5, 0.0))

    # Intermediate rings
    for r in range(1, rings):
        phi = math.pi * r / rings
        z = cz - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        v_coord = r / rings

        for s in range(sectors):
            theta = 2.0 * math.pi * s / sectors
            x = cx + ring_r * math.cos(theta)
            y = cy + ring_r * math.sin(theta)
            u_coord = s / sectors
            verts.append((x, y, z))
            uvs.append((u_coord, v_coord))

    # Top pole
    verts.append((cx, cy, cz + radius))
    uvs.append((0.5, 1.0))

    # Bottom cap triangles
    for s in range(sectors):
        s_next = (s + 1) % sectors
        faces.append((0, 1 + s_next, 1 + s))

    # Middle quads
    for r in range(rings - 2):
        ring_a = 1 + r * sectors
        ring_b = 1 + (r + 1) * sectors
        for s in range(sectors):
            s_next = (s + 1) % sectors
            faces.append((ring_a + s, ring_b + s, ring_b + s_next, ring_a + s_next))

    # Top cap triangles
    top_pole = len(verts) - 1
    last_ring = 1 + (rings - 2) * sectors
    for s in range(sectors):
        s_next = (s + 1) % sectors
        faces.append((top_pole, last_ring + s, last_ring + s_next))

    return verts, faces, uvs


# ---------------------------------------------------------------------------
# Iris UV mapping
# ---------------------------------------------------------------------------


def _compute_iris_uvs(
    verts: VertList,
    center: Vec3,
    radius: float,
    iris_radius_ratio: float,
    pupil_radius_ratio: float,
    forward_axis: int = 1,
    forward_sign: float = -1.0,
) -> UVList:
    """Compute UVs that map the front hemisphere to a centered iris circle.

    The UV layout places the iris as a circle at center (0.5, 0.5) with
    radius = iris_radius_ratio * 0.5 in UV space. The pupil sits at the
    center within that circle. Sclera occupies the rest.

    For each vertex:
    - Project onto a plane perpendicular to the forward direction
    - Map that projection into UV space
    - Front-facing vertices get mapped to the iris region
    - Side/back vertices get mapped to the sclera region

    Args:
        verts: Vertex positions of the eyeball.
        center: Center of the eye sphere.
        radius: Radius of the eye sphere.
        iris_radius_ratio: Fraction of eye radius that is the iris (0..1).
        pupil_radius_ratio: Fraction of eye radius for the pupil (0..1).
        forward_axis: Which axis is "forward" (0=X, 1=Y, 2=Z).
        forward_sign: Direction along forward axis (-1 = -Y is front).

    Returns:
        UV coordinates list, one per vertex. The UV maps:
        - (0.5, 0.5) = pupil center
        - Circle of radius iris_radius_ratio * 0.5 around center = iris
        - Outside that = sclera
    """
    cx, cy, cz = center
    iris_uv_radius = iris_radius_ratio * 0.5  # in UV space [0..1]

    uvs: UVList = []
    for vx, vy, vz in verts:
        # Direction from center to vertex, normalized
        dx = vx - cx
        dy = vy - cy
        dz = vz - cz
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-10:
            uvs.append((0.5, 0.5))
            continue
        dx /= length
        dy /= length
        dz /= length

        # Compute how much this vertex faces forward (dot with forward dir)
        d = [dx, dy, dz]
        forward_dot = d[forward_axis] * forward_sign

        # Project vertex direction onto the plane perpendicular to forward axis
        # Get the two tangent axes
        axes = [0, 1, 2]
        axes.remove(forward_axis)
        ax0, ax1 = axes

        # Tangent components (how far left/right and up/down on the eye face)
        t0 = d[ax0]
        t1 = d[ax1]

        if forward_dot > 0:
            # Front hemisphere - map into iris circle
            # Use angular distance from forward direction to scale UV
            # acos(forward_dot) gives angle from forward (0 = dead center)
            angle_from_front = math.acos(min(1.0, max(-1.0, forward_dot)))
            # Max angle for front hemisphere is pi/2
            # Normalize to [0, 1] within front hemisphere
            front_t = angle_from_front / (math.pi * 0.5)

            # Direction in tangent plane
            tangent_len = math.sqrt(t0 * t0 + t1 * t1)
            if tangent_len > 1e-10:
                tang_dir0 = t0 / tangent_len
                tang_dir1 = t1 / tangent_len
            else:
                tang_dir0, tang_dir1 = 0.0, 0.0

            # UV position: center + direction * distance
            # front_t=0 is center (pupil), front_t=1 is edge of iris region
            uv_dist = front_t * iris_uv_radius
            u = 0.5 + tang_dir0 * uv_dist
            v = 0.5 + tang_dir1 * uv_dist

        else:
            # Back hemisphere - sclera region
            # Map to the ring between iris_uv_radius and 0.5 in UV space
            angle_from_back = math.acos(min(1.0, max(-1.0, -forward_dot)))
            back_t = angle_from_back / (math.pi * 0.5)  # 0=dead back, 1=equator

            tangent_len = math.sqrt(t0 * t0 + t1 * t1)
            if tangent_len > 1e-10:
                tang_dir0 = t0 / tangent_len
                tang_dir1 = t1 / tangent_len
            else:
                # Dead backward vertex: use a default direction so UV
                # is placed at the sclera edge, not at center
                tang_dir0, tang_dir1 = 1.0, 0.0

            # Map from iris edge to UV edge
            uv_dist = iris_uv_radius + (1.0 - back_t) * (0.5 - iris_uv_radius)
            u = 0.5 + tang_dir0 * uv_dist
            v = 0.5 + tang_dir1 * uv_dist

        # Clamp to [0, 1]
        u = max(0.0, min(1.0, u))
        v = max(0.0, min(1.0, v))
        uvs.append((u, v))

    return uvs


# ---------------------------------------------------------------------------
# Material region assignment for eye faces
# ---------------------------------------------------------------------------


def _assign_eye_material_regions(
    verts: VertList,
    faces: FaceList,
    center: Vec3,
    radius: float,
    iris_radius_ratio: float,
    forward_axis: int = 1,
    forward_sign: float = -1.0,
    layer: str = "inner",
) -> dict[int, str]:
    """Assign material regions to each face of an eye mesh.

    For inner eyeball:
    - Faces in front hemisphere center -> "eye_pupil"
    - Faces in front hemisphere ring -> "eye_iris"
    - Faces in back hemisphere -> "eye_sclera"

    For outer cornea:
    - All faces -> "eye_cornea"

    Args:
        verts: Vertex positions.
        faces: Face index tuples.
        center: Eye center position.
        radius: Eye radius.
        iris_radius_ratio: Fraction of radius that is iris.
        forward_axis: Forward-facing axis index.
        forward_sign: Direction along forward axis.
        layer: "inner" for eyeball, "outer" for cornea.

    Returns:
        Dict mapping face_index -> material region name.
    """
    if layer == "outer":
        return {fi: "eye_cornea" for fi in range(len(faces))}

    cx, cy, cz = center
    pupil_threshold = iris_radius_ratio * 0.6  # pupil is inner ~60% of iris

    regions: dict[int, str] = {}
    for fi, face in enumerate(faces):
        # Average forward-dot of face vertices
        total_dot = 0.0
        total_angle = 0.0
        for vi in face:
            vx, vy, vz = verts[vi]
            dx = vx - cx
            dy = vy - cy
            dz = vz - cz
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            if length < 1e-10:
                total_dot += 1.0
                continue
            d = [dx / length, dy / length, dz / length]
            dot = d[forward_axis] * forward_sign
            total_dot += dot

            # Angle from forward direction
            angle = math.acos(min(1.0, max(-1.0, dot)))
            total_angle += angle

        avg_dot = total_dot / len(face)
        avg_angle = total_angle / len(face)

        if avg_dot <= 0:
            # Back hemisphere
            regions[fi] = "eye_sclera"
        else:
            # Front hemisphere - check angular distance
            # Normalize angle to fraction of hemisphere (pi/2)
            front_fraction = avg_angle / (math.pi * 0.5)
            if front_fraction < pupil_threshold:
                regions[fi] = "eye_pupil"
            elif front_fraction < iris_radius_ratio:
                regions[fi] = "eye_iris"
            else:
                regions[fi] = "eye_sclera"

    return regions


# ---------------------------------------------------------------------------
# Single eye mesh generator
# ---------------------------------------------------------------------------


def generate_eye_mesh(
    radius: float = 0.012,
    iris_radius_ratio: float = 0.45,
    pupil_radius_ratio: float = 0.2,
    cx: float = 0.0,
    cy: float = 0.0,
    cz: float = 0.0,
    cornea_scale: float = 1.03,
    rings: int = 8,
    sectors: int = 12,
    forward_axis: int = 1,
    forward_sign: float = -1.0,
) -> EyeMeshResult:
    """Generate a two-layer eye mesh: inner eyeball + outer cornea.

    The inner sphere (eyeball) is UV-mapped for iris/pupil/sclera texture.
    The UV maps the front hemisphere to a circle centered at (0.5, 0.5)
    with the pupil at dead center and iris surrounding it.

    The outer sphere (cornea) is slightly larger, intended for a glossy
    transparent material with high metallic + low roughness for wet
    reflections. It has its own material slot.

    Args:
        radius: Eyeball radius in scene units (default 0.012m = 12mm).
        iris_radius_ratio: Fraction of eye that is the iris (0.0-1.0).
        pupil_radius_ratio: Fraction of eye for the pupil center (0.0-1.0).
        cx, cy, cz: Center position of the eye.
        cornea_scale: How much larger the cornea is vs eyeball (default 1.03).
        rings: Latitudinal ring count for sphere.
        sectors: Longitudinal sector count for sphere.
        forward_axis: Which axis faces forward (0=X, 1=Y, 2=Z).
        forward_sign: Direction along that axis (-1.0 = -Y is front).

    Returns:
        EyeMeshResult dict with:
        - inner_vertices, inner_faces, inner_uvs: Eyeball geometry + UVs
        - outer_vertices, outer_faces, outer_uvs: Cornea geometry + UVs
        - material_regions: face_index -> material name for all faces
        - material_slots: ordered list of material slot names
        - metadata: vertex/face counts, dimensions
    """
    iris_radius_ratio = max(0.1, min(0.9, iris_radius_ratio))
    pupil_radius_ratio = max(0.05, min(iris_radius_ratio * 0.8, pupil_radius_ratio))
    rings = max(4, rings)
    sectors = max(6, sectors)

    center: Vec3 = (cx, cy, cz)

    # -- Inner eyeball --
    inner_verts, inner_faces, inner_uvs_standard = _uv_sphere(
        cx, cy, cz, radius, rings, sectors,
    )

    # Compute iris-mapped UVs for inner eyeball
    inner_uvs = _compute_iris_uvs(
        inner_verts, center, radius,
        iris_radius_ratio, pupil_radius_ratio,
        forward_axis, forward_sign,
    )

    # Assign material regions to inner faces
    inner_regions = _assign_eye_material_regions(
        inner_verts, inner_faces, center, radius,
        iris_radius_ratio, forward_axis, forward_sign,
        layer="inner",
    )

    # -- Outer cornea --
    cornea_radius = radius * cornea_scale
    outer_verts, outer_faces, outer_uvs = _uv_sphere(
        cx, cy, cz, cornea_radius, rings, sectors,
    )

    # Assign cornea material region
    outer_regions = _assign_eye_material_regions(
        outer_verts, outer_faces, center, cornea_radius,
        iris_radius_ratio, forward_axis, forward_sign,
        layer="outer",
    )

    # -- Merge regions into unified face-index mapping --
    # Inner faces: indices 0..len(inner_faces)-1
    # Outer faces: indices len(inner_faces)..len(inner_faces)+len(outer_faces)-1
    material_regions: dict[int, str] = {}
    for fi, region in inner_regions.items():
        material_regions[fi] = region
    inner_face_count = len(inner_faces)
    for fi, region in outer_regions.items():
        material_regions[inner_face_count + fi] = region

    total_verts = len(inner_verts) + len(outer_verts)
    total_faces = len(inner_faces) + len(outer_faces)

    return {
        "inner_vertices": inner_verts,
        "inner_faces": inner_faces,
        "inner_uvs": inner_uvs,
        "outer_vertices": outer_verts,
        "outer_faces": outer_faces,
        "outer_uvs": outer_uvs,
        "material_regions": material_regions,
        "material_slots": ["eye_pupil", "eye_iris", "eye_sclera", "eye_cornea"],
        "center": center,
        "radius": radius,
        "cornea_radius": cornea_radius,
        "metadata": {
            "inner_vertex_count": len(inner_verts),
            "inner_face_count": len(inner_faces),
            "outer_vertex_count": len(outer_verts),
            "outer_face_count": len(outer_faces),
            "total_vertex_count": total_verts,
            "total_face_count": total_faces,
            "iris_radius_ratio": iris_radius_ratio,
            "pupil_radius_ratio": pupil_radius_ratio,
            "cornea_scale": cornea_scale,
        },
    }


# ---------------------------------------------------------------------------
# Eye pair generator (positioned for head)
# ---------------------------------------------------------------------------


def generate_eye_pair(
    head_center: Vec3 = (0.0, 0.0, 1.64),
    head_radius: float = 0.10,
    eye_radius: float = 0.012,
    iris_radius_ratio: float = 0.45,
    pupil_radius_ratio: float = 0.2,
    eye_separation: float = 0.55,
    eye_height: float = 0.15,
    eye_depth: float = 0.85,
    cornea_scale: float = 1.03,
    rings: int = 8,
    sectors: int = 12,
) -> dict[str, Any]:
    """Generate a pair of eyes positioned for a character head.

    Calculates left and right eye positions based on head dimensions,
    placing them at appropriate inter-pupillary distance and depth
    (slightly recessed into the skull).

    Args:
        head_center: Center of the head sphere (x, y, z).
        head_radius: Radius of the head.
        eye_radius: Radius of each eyeball.
        iris_radius_ratio: Fraction of eye that is iris.
        pupil_radius_ratio: Fraction of eye for pupil center.
        eye_separation: Fraction of head_radius for horizontal eye spacing
                        (distance from center to each eye, in head radii).
        eye_height: Vertical offset from head center as fraction of head_radius.
        eye_depth: How deep into the head (fraction of head_radius from front).
        cornea_scale: Size ratio of cornea to eyeball.
        rings: Sphere ring count.
        sectors: Sphere sector count.

    Returns:
        Dict with:
        - left_eye: EyeMeshResult for left eye
        - right_eye: EyeMeshResult for right eye
        - eye_positions: {"left": (x,y,z), "right": (x,y,z)}
    """
    hx, hy, hz = head_center

    # Eye positions: slightly forward (-Y), above center (+Z), symmetric X
    eye_x_offset = head_radius * eye_separation
    eye_z_offset = head_radius * eye_height
    eye_y_offset = -head_radius * eye_depth  # forward is -Y

    left_pos = (hx - eye_x_offset, hy + eye_y_offset, hz + eye_z_offset)
    right_pos = (hx + eye_x_offset, hy + eye_y_offset, hz + eye_z_offset)

    left_eye = generate_eye_mesh(
        radius=eye_radius,
        iris_radius_ratio=iris_radius_ratio,
        pupil_radius_ratio=pupil_radius_ratio,
        cx=left_pos[0], cy=left_pos[1], cz=left_pos[2],
        cornea_scale=cornea_scale,
        rings=rings, sectors=sectors,
        forward_axis=1, forward_sign=-1.0,
    )

    right_eye = generate_eye_mesh(
        radius=eye_radius,
        iris_radius_ratio=iris_radius_ratio,
        pupil_radius_ratio=pupil_radius_ratio,
        cx=right_pos[0], cy=right_pos[1], cz=right_pos[2],
        cornea_scale=cornea_scale,
        rings=rings, sectors=sectors,
        forward_axis=1, forward_sign=-1.0,
    )

    return {
        "left_eye": left_eye,
        "right_eye": right_eye,
        "eye_positions": {
            "left": left_pos,
            "right": right_pos,
        },
    }
