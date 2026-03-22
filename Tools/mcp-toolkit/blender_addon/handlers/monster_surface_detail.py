"""Monster surface detail generators for VeilBreakers.

Generates additional geometry layers for monster meshes to add visual
complexity: scale patterns, chitin segments, and billboard fur cards.

All functions are pure Python with math-only dependencies (no bpy/bmesh).
They take raw vertex/face/normal data and return additional geometry that
can be merged with the base mesh.

Provides:
  - generate_scale_pattern: Overlapping scale plate geometry
  - generate_chitin_segments: Arthropod chitin plate segments
  - generate_fur_card_layer: Billboard fur card geometry with UVs
  - compute_face_normals: Utility to compute per-face normals
  - compute_vertex_normals: Utility to compute averaged vertex normals
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Type aliases (matching monster_bodies.py)
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
FaceList = list[tuple[int, ...]]
VertList = list[Vec3]


# ---------------------------------------------------------------------------
# Vector math helpers
# ---------------------------------------------------------------------------


def _vec_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec_scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _vec_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_length(v: Vec3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _vec_normalize(v: Vec3) -> Vec3:
    length = _vec_length(v)
    if length < 1e-10:
        return (0.0, 1.0, 0.0)
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def _vec_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _face_center(vertices: VertList, face: tuple[int, ...]) -> Vec3:
    """Compute the centroid of a face."""
    n = len(face)
    if n == 0:
        return (0.0, 0.0, 0.0)
    sx = sum(vertices[i][0] for i in face)
    sy = sum(vertices[i][1] for i in face)
    sz = sum(vertices[i][2] for i in face)
    inv = 1.0 / n
    return (sx * inv, sy * inv, sz * inv)


def _face_normal(vertices: VertList, face: tuple[int, ...]) -> Vec3:
    """Compute the normal of a face (using first 3 vertices)."""
    if len(face) < 3:
        return (0.0, 1.0, 0.0)
    v0 = vertices[face[0]]
    v1 = vertices[face[1]]
    v2 = vertices[face[2]]
    edge1 = _vec_sub(v1, v0)
    edge2 = _vec_sub(v2, v0)
    normal = _vec_cross(edge1, edge2)
    return _vec_normalize(normal)


# ---------------------------------------------------------------------------
# Public normal computation utilities
# ---------------------------------------------------------------------------


def compute_face_normals(
    vertices: VertList,
    faces: FaceList,
) -> list[Vec3]:
    """Compute per-face normals for a mesh.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples.

    Returns:
        List of normalised (x, y, z) face normals, one per face.
    """
    return [_face_normal(vertices, face) for face in faces]


def compute_vertex_normals(
    vertices: VertList,
    faces: FaceList,
) -> list[Vec3]:
    """Compute averaged vertex normals from face normals.

    Each vertex normal is the normalised average of the normals of all
    faces that reference that vertex.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples.

    Returns:
        List of normalised (x, y, z) vertex normals, one per vertex.
    """
    accum = [(0.0, 0.0, 0.0)] * len(vertices)
    for face in faces:
        fn = _face_normal(vertices, face)
        for idx in face:
            old = accum[idx]
            accum[idx] = (old[0] + fn[0], old[1] + fn[1], old[2] + fn[2])
    return [_vec_normalize(n) for n in accum]


# ---------------------------------------------------------------------------
# Scale pattern generator
# ---------------------------------------------------------------------------


def generate_scale_pattern(
    vertices: VertList,
    faces: FaceList,
    normals: list[Vec3] | None = None,
    scale_size: float = 0.05,
    coverage: float = 0.8,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate geometric scale plate overlay for a monster mesh.

    Creates small diamond-shaped scale plates offset from the mesh surface
    along vertex normals. Scales are distributed across a fraction of the
    mesh faces controlled by ``coverage``.

    Args:
        vertices: Base mesh vertex positions.
        faces: Base mesh face index tuples.
        normals: Per-vertex normals. If None, computed from faces.
        scale_size: Size of each individual scale plate.
        coverage: Fraction of faces to receive scales (0.0-1.0).
        seed: Random seed for deterministic selection.

    Returns:
        Dict with:
          - vertices: List of new scale vertices
          - faces: List of new scale face tuples
          - scale_count: Number of scales generated
          - coverage_actual: Actual coverage fraction achieved
    """
    if not vertices or not faces:
        return {
            "vertices": [],
            "faces": [],
            "scale_count": 0,
            "coverage_actual": 0.0,
        }

    coverage = max(0.0, min(1.0, coverage))
    scale_size = max(0.001, scale_size)

    if coverage == 0.0:
        return {
            "vertices": [],
            "faces": [],
            "scale_count": 0,
            "coverage_actual": 0.0,
        }

    if normals is None:
        normals = compute_vertex_normals(vertices, faces)

    out_verts: VertList = []
    out_faces: FaceList = []
    scale_count = 0

    for fi, face in enumerate(faces):
        # Deterministic pseudo-random selection
        hash_val = (fi * 7919 + seed * 6271) % 10000
        if hash_val / 10000.0 > coverage:
            continue

        center = _face_center(vertices, face)
        fn = _face_normal(vertices, face)

        # Average normal at face center
        avg_normal = (0.0, 0.0, 0.0)
        for idx in face:
            n = normals[idx] if idx < len(normals) else fn
            avg_normal = _vec_add(avg_normal, n)
        avg_normal = _vec_normalize(avg_normal)

        # Create diamond scale plate: 4 vertices + offset from surface
        offset = _vec_scale(avg_normal, scale_size * 0.2)
        base = _vec_add(center, offset)

        # Build tangent and bitangent from normal
        if abs(avg_normal[1]) < 0.99:
            up = (0.0, 1.0, 0.0)
        else:
            up = (1.0, 0.0, 0.0)
        tangent = _vec_normalize(_vec_cross(avg_normal, up))
        bitangent = _vec_normalize(_vec_cross(avg_normal, tangent))

        half = scale_size * 0.5
        v_base = len(out_verts)
        # Diamond: top, right, bottom, left
        out_verts.append(_vec_add(base, _vec_scale(bitangent, half)))
        out_verts.append(_vec_add(base, _vec_scale(tangent, half)))
        out_verts.append(_vec_add(base, _vec_scale(bitangent, -half)))
        out_verts.append(_vec_add(base, _vec_scale(tangent, -half)))
        # Raised center point
        tip = _vec_add(base, _vec_scale(avg_normal, scale_size * 0.3))
        out_verts.append(tip)

        # 4 triangular faces forming a raised diamond
        out_faces.append((v_base + 0, v_base + 1, v_base + 4))
        out_faces.append((v_base + 1, v_base + 2, v_base + 4))
        out_faces.append((v_base + 2, v_base + 3, v_base + 4))
        out_faces.append((v_base + 3, v_base + 0, v_base + 4))

        scale_count += 1

    actual_coverage = scale_count / max(len(faces), 1)

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "scale_count": scale_count,
        "coverage_actual": actual_coverage,
    }


# ---------------------------------------------------------------------------
# Chitin segment generator
# ---------------------------------------------------------------------------


def generate_chitin_segments(
    vertices: VertList,
    faces: FaceList,
    segment_count: int = 8,
    overlap: float = 0.15,
    thickness: float = 0.02,
) -> dict[str, Any]:
    """Generate overlapping chitin plate segments along body axis.

    Splits the mesh along the Y axis into ``segment_count`` bands and
    generates a curved shell plate for each band, creating the appearance
    of arthropod exoskeleton segments.

    Args:
        vertices: Base mesh vertex positions.
        faces: Base mesh face index tuples.
        segment_count: Number of chitin segments to generate.
        overlap: Fraction of overlap between adjacent segments (0.0-0.5).
        thickness: Thickness of each chitin plate.

    Returns:
        Dict with:
          - vertices: List of chitin plate vertices
          - faces: List of chitin plate face tuples
          - segment_count: Number of segments generated
          - segments: List of per-segment metadata dicts
    """
    if not vertices or not faces or segment_count < 1:
        return {
            "vertices": [],
            "faces": [],
            "segment_count": 0,
            "segments": [],
        }

    segment_count = max(1, segment_count)
    overlap = max(0.0, min(0.5, overlap))
    thickness = max(0.001, thickness)

    # Find Y extent
    ys = [v[1] for v in vertices]
    y_min = min(ys)
    y_max = max(ys)
    y_range = y_max - y_min
    if y_range < 1e-6:
        return {
            "vertices": [],
            "faces": [],
            "segment_count": 0,
            "segments": [],
        }

    # Find radial extent per segment band
    segment_height = y_range / segment_count
    overlap_amount = segment_height * overlap

    out_verts: VertList = []
    out_faces: FaceList = []
    segment_meta: list[dict[str, Any]] = []

    ring_segments = 12  # vertices per ring of each plate

    for seg_i in range(segment_count):
        band_y_start = y_min + seg_i * segment_height - overlap_amount
        band_y_end = y_min + (seg_i + 1) * segment_height + overlap_amount

        # Gather vertices in this Y band
        band_verts = [
            v for v in vertices
            if band_y_start <= v[1] <= band_y_end
        ]

        if len(band_verts) < 3:
            continue

        # Compute average radius from Y axis in this band
        radii = [
            math.sqrt(v[0] * v[0] + v[2] * v[2])
            for v in band_verts
        ]
        avg_radius = sum(radii) / len(radii) + thickness
        band_center_y = (band_y_start + band_y_end) * 0.5

        # Generate a shell ring: outer + inner ring to form the plate
        v_base = len(out_verts)
        plate_half_h = (band_y_end - band_y_start) * 0.5

        for ring_i in range(2):  # 0=bottom, 1=top of plate
            y_pos = band_center_y + (-plate_half_h if ring_i == 0 else plate_half_h)
            for layer in range(2):  # 0=outer, 1=inner
                r = avg_radius if layer == 0 else avg_radius - thickness
                for j in range(ring_segments):
                    angle = 2.0 * math.pi * j / ring_segments
                    out_verts.append((
                        math.cos(angle) * r,
                        y_pos,
                        math.sin(angle) * r,
                    ))

        # Connect rings into quads
        # Structure: 4 rings of ring_segments verts each
        # ring 0: bottom outer, ring 1: bottom inner
        # ring 2: top outer, ring 3: top inner
        rings = [v_base + k * ring_segments for k in range(4)]

        # Outer surface: connect bottom_outer -> top_outer
        for j in range(ring_segments):
            j2 = (j + 1) % ring_segments
            out_faces.append((
                rings[0] + j, rings[0] + j2,
                rings[2] + j2, rings[2] + j,
            ))

        # Inner surface: connect top_inner -> bottom_inner
        for j in range(ring_segments):
            j2 = (j + 1) % ring_segments
            out_faces.append((
                rings[3] + j, rings[3] + j2,
                rings[1] + j2, rings[1] + j,
            ))

        # Top cap: outer -> inner
        for j in range(ring_segments):
            j2 = (j + 1) % ring_segments
            out_faces.append((
                rings[2] + j, rings[2] + j2,
                rings[3] + j2, rings[3] + j,
            ))

        # Bottom cap: inner -> outer
        for j in range(ring_segments):
            j2 = (j + 1) % ring_segments
            out_faces.append((
                rings[1] + j, rings[1] + j2,
                rings[0] + j2, rings[0] + j,
            ))

        segment_meta.append({
            "index": seg_i,
            "y_start": band_y_start,
            "y_end": band_y_end,
            "avg_radius": avg_radius,
            "vertex_range": (v_base, len(out_verts)),
        })

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "segment_count": len(segment_meta),
        "segments": segment_meta,
    }


# ---------------------------------------------------------------------------
# Fur card layer generator
# ---------------------------------------------------------------------------


def generate_fur_card_layer(
    vertices: VertList,
    faces: FaceList,
    normals: list[Vec3] | None = None,
    density: int = 100,
    length: float = 0.1,
    width: float = 0.02,
    seed: int = 0,
) -> dict[str, Any]:
    """Generate billboard fur cards distributed over mesh surface.

    Creates thin rectangular quads (cards) anchored at face centres and
    oriented along vertex normals. Each card has UV coordinates suitable
    for a fur/hair texture strip.

    Args:
        vertices: Base mesh vertex positions.
        faces: Base mesh face index tuples.
        normals: Per-vertex normals. If None, computed from faces.
        density: Target number of fur cards to generate.
        length: Length of each fur card along the normal direction.
        width: Width of each fur card perpendicular to the normal.
        seed: Random seed for deterministic placement.

    Returns:
        Dict with:
          - vertices: List of fur card vertices
          - faces: List of fur card face tuples (quads)
          - uvs: List of (u, v) per vertex for texture mapping
          - card_count: Number of fur cards generated
    """
    if not vertices or not faces or density < 1:
        return {
            "vertices": [],
            "faces": [],
            "uvs": [],
            "card_count": 0,
        }

    density = max(1, density)
    length = max(0.001, length)
    width = max(0.001, width)

    if normals is None:
        normals = compute_vertex_normals(vertices, faces)

    # Select faces for fur cards via deterministic sampling
    n_faces = len(faces)
    step = max(1, n_faces // density)

    out_verts: VertList = []
    out_faces: FaceList = []
    out_uvs: list[tuple[float, float]] = []
    card_count = 0

    for fi in range(0, n_faces, step):
        if card_count >= density:
            break

        face = faces[fi]
        center = _face_center(vertices, face)

        # Average normal at face center
        avg_normal = (0.0, 0.0, 0.0)
        for idx in face:
            n = normals[idx] if idx < len(normals) else (0.0, 1.0, 0.0)
            avg_normal = _vec_add(avg_normal, n)
        avg_normal = _vec_normalize(avg_normal)

        # Deterministic jitter for natural look
        jitter_hash = (fi * 3571 + seed * 8837) % 10000
        jitter_angle = (jitter_hash / 10000.0) * math.pi * 2.0

        # Build tangent frame
        if abs(avg_normal[1]) < 0.99:
            up = (0.0, 1.0, 0.0)
        else:
            up = (1.0, 0.0, 0.0)
        tangent = _vec_normalize(_vec_cross(avg_normal, up))
        bitangent = _vec_normalize(_vec_cross(avg_normal, tangent))

        # Rotate tangent by jitter angle for variety
        cos_j = math.cos(jitter_angle)
        sin_j = math.sin(jitter_angle)
        rot_tangent = _vec_add(
            _vec_scale(tangent, cos_j),
            _vec_scale(bitangent, sin_j),
        )

        half_w = width * 0.5

        # Card is a quad: base-left, base-right, tip-right, tip-left
        v_base = len(out_verts)
        base_left = _vec_add(center, _vec_scale(rot_tangent, -half_w))
        base_right = _vec_add(center, _vec_scale(rot_tangent, half_w))
        tip_offset = _vec_scale(avg_normal, length)
        tip_left = _vec_add(base_left, tip_offset)
        tip_right = _vec_add(base_right, tip_offset)

        out_verts.extend([base_left, base_right, tip_right, tip_left])
        out_faces.append((v_base, v_base + 1, v_base + 2, v_base + 3))

        # UV: bottom-left=0,0  bottom-right=1,0  top-right=1,1  top-left=0,1
        out_uvs.extend([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])

        card_count += 1

    return {
        "vertices": out_verts,
        "faces": out_faces,
        "uvs": out_uvs,
        "card_count": card_count,
    }
