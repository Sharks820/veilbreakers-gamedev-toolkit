"""Edge wear and weathering pipeline for dark fantasy meshes.

Applies automated aging, wear, and environmental weathering effects to
generated meshes via vertex color layers. Makes geometry look aged, worn,
and lived-in -- essential for VeilBreakers dark fantasy AAA quality.

Provides:
  - handle_apply_weathering(): Main entry point (bpy handler)
  - apply_edge_wear(): Convex-edge wear mask (pure logic)
  - apply_dirt_accumulation(): Concave crevice dirt mask (pure logic)
  - apply_moss_growth(): Upward-facing moss tint mask (pure logic)
  - apply_rain_staining(): Vertical-surface rain streak mask (pure logic)
  - apply_structural_settling(): Gravity-based vertex displacement (pure logic)
  - apply_corruption_veins(): Purple corruption overlay mask (pure logic)
  - WEATHERING_PRESETS: Named preset configurations

All compute functions are pure logic (no bpy) for testability.
Handler wraps with bpy mesh data extraction and vertex color writing.
"""

from __future__ import annotations

import math
import random
from typing import Any

try:
    import bpy
    import bmesh
except ImportError:
    bpy = None  # type: ignore[assignment]
    bmesh = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# VeilBreakers Dark Fantasy Weathering Palette (linear sRGB)
# ---------------------------------------------------------------------------

# Tints applied during weathering -- match VB dark fantasy palette.
# Saturation capped at 40%, value range 10-50%.
WEAR_TINT = (0.30, 0.27, 0.22, 1.0)       # Exposed lighter surface
DIRT_TINT = (0.06, 0.05, 0.03, 1.0)        # Dark crevice grime
MOSS_TINT = (0.08, 0.12, 0.06, 1.0)        # Desaturated dark moss green
RAIN_TINT = (0.05, 0.05, 0.06, 1.0)        # Dark water stain
CORRUPTION_TINT = (0.12, 0.04, 0.14, 1.0)  # Purple corruption veins


# ---------------------------------------------------------------------------
# Weathering Presets
# ---------------------------------------------------------------------------

WEATHERING_PRESETS: dict[str, dict[str, float]] = {
    "light": {
        "edge_wear": 0.3,
        "dirt": 0.2,
        "moss": 0.0,
        "rain": 0.1,
        "settling": 0.002,
    },
    "medium": {
        "edge_wear": 0.5,
        "dirt": 0.4,
        "moss": 0.2,
        "rain": 0.3,
        "settling": 0.005,
    },
    "heavy": {
        "edge_wear": 0.7,
        "dirt": 0.6,
        "moss": 0.4,
        "rain": 0.5,
        "settling": 0.01,
    },
    "ancient": {
        "edge_wear": 0.9,
        "dirt": 0.8,
        "moss": 0.6,
        "rain": 0.7,
        "settling": 0.02,
    },
    "corrupted": {
        "edge_wear": 0.4,
        "dirt": 0.3,
        "moss": 0.0,
        "rain": 0.0,
        "settling": 0.015,
        "corruption_veins": 0.5,
    },
}

VALID_PRESETS = frozenset(WEATHERING_PRESETS.keys())

VALID_EFFECTS = frozenset({
    "edge_wear", "dirt", "moss", "rain", "settling", "corruption_veins",
})


# ---------------------------------------------------------------------------
# Mesh data helpers (pure logic)
# ---------------------------------------------------------------------------


def _compute_face_normals(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
) -> list[tuple[float, float, float]]:
    """Bug 13 fix: compute face normals from vertices and faces when not provided."""
    normals: list[tuple[float, float, float]] = []
    for face in faces:
        if len(face) < 3:
            normals.append((0.0, 0.0, 1.0))
            continue
        p0 = vertices[face[0]] if face[0] < len(vertices) else (0.0, 0.0, 0.0)
        p1 = vertices[face[1]] if face[1] < len(vertices) else (0.0, 0.0, 0.0)
        p2 = vertices[face[2]] if face[2] < len(vertices) else (0.0, 0.0, 0.0)
        e1x = p1[0] - p0[0]
        e1y = p1[1] - p0[1]
        e1z = p1[2] - p0[2]
        e2x = p2[0] - p0[0]
        e2y = p2[1] - p0[1]
        e2z = p2[2] - p0[2]
        nx = e1y * e2z - e1z * e2y
        ny = e1z * e2x - e1x * e2z
        nz = e1x * e2y - e1y * e2x
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 1e-10:
            normals.append((nx / length, ny / length, nz / length))
        else:
            normals.append((0.0, 0.0, 1.0))
    return normals


def _ensure_face_normals(mesh_data: dict[str, Any]) -> None:
    """Bug 13 fix: ensure mesh_data has face_normals; compute from geometry if missing."""
    face_normals = mesh_data.get("face_normals", [])
    if not face_normals or len(face_normals) < len(mesh_data.get("faces", [])):
        mesh_data["face_normals"] = _compute_face_normals(
            mesh_data.get("vertices", []),
            mesh_data.get("faces", []),
        )

def _compute_bounding_box(
    vertices: list[tuple[float, float, float]],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return (min_corner, max_corner) of vertex positions."""
    if not vertices:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    return (
        (min(xs), min(ys), min(zs)),
        (max(xs), max(ys), max(zs)),
    )


def _height_factor(
    z: float, z_min: float, z_max: float,
) -> float:
    """Return normalized height 0 (bottom) to 1 (top)."""
    dz = z_max - z_min
    if dz < 1e-8:
        return 0.0
    return max(0.0, min(1.0, (z - z_min) / dz))


def _compute_edge_convexity(
    mesh_data: dict[str, Any],
) -> dict[int, float]:
    """Compute per-vertex convexity from face angle defect.

    Positive values = convex (protruding edges), negative = concave (crevices).
    Returns dict mapping vertex index to curvature value in [-1, 1] range.
    Pure logic -- no bpy.
    """
    vertices = mesh_data["vertices"]
    faces = mesh_data["faces"]
    vertex_normals = mesh_data.get("vertex_normals", [])
    face_normals = mesh_data.get("face_normals", [])

    num_verts = len(vertices)
    # Accumulate angle sum per vertex from face corners
    angle_sum: dict[int, float] = {i: 0.0 for i in range(num_verts)}
    face_count: dict[int, int] = {i: 0 for i in range(num_verts)}

    for face in faces:
        n = len(face)
        for i_corner in range(n):
            vi = face[i_corner]
            v_prev = face[(i_corner - 1) % n]
            v_next = face[(i_corner + 1) % n]

            # Vectors from vi to neighbors
            p = vertices[vi]
            a = vertices[v_prev]
            b = vertices[v_next]

            ax, ay, az = a[0] - p[0], a[1] - p[1], a[2] - p[2]
            bx, by, bz = b[0] - p[0], b[1] - p[1], b[2] - p[2]

            dot = ax * bx + ay * by + az * bz
            mag_a = math.sqrt(ax * ax + ay * ay + az * az)
            mag_b = math.sqrt(bx * bx + by * by + bz * bz)

            if mag_a < 1e-12 or mag_b < 1e-12:
                continue

            cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
            angle = math.acos(cos_angle)
            angle_sum[vi] += angle
            face_count[vi] += 1

    # Bug 12 fix: detect boundary vertices (not fully surrounded by faces).
    # A vertex at the boundary has fewer faces than a fully interior vertex,
    # causing the angle defect formula to give a large positive value
    # (misclassifying open edges as highly convex).
    # Build edge-face count to detect boundary edges
    edge_face_count: dict[tuple[int, int], int] = {}
    for face in faces:
        fn = len(face)
        for i_edge in range(fn):
            a = face[i_edge]
            b = face[(i_edge + 1) % fn]
            edge_key = (min(a, b), max(a, b))
            edge_face_count[edge_key] = edge_face_count.get(edge_key, 0) + 1

    # Identify boundary vertices (incident to at least one boundary edge)
    boundary_verts: set[int] = set()
    for (a, b), count in edge_face_count.items():
        if count < 2:  # boundary edge: shared by fewer than 2 faces
            boundary_verts.add(a)
            boundary_verts.add(b)

    # Angle defect: 2*pi - sum(angles). Positive = convex, negative = concave.
    curvature: dict[int, float] = {}
    for vi in range(num_verts):
        if face_count[vi] == 0:
            curvature[vi] = 0.0
            continue
        if vi in boundary_verts:
            # Bug 12 fix: boundary vertices get neutral convexity
            curvature[vi] = 0.0
            continue
        defect = 2.0 * math.pi - angle_sum[vi]
        # Normalize to roughly [-1, 1] range
        # Typical defect range is [-pi, pi] for non-degenerate geometry
        curvature[vi] = max(-1.0, min(1.0, defect / math.pi))

    return curvature


def _simple_noise(x: float, y: float, z: float, seed: int = 0) -> float:
    """Deterministic pseudo-noise for vertex-level variation.

    Returns value in [0, 1]. Uses hash-based mixing for reproducibility.
    """
    # Quantize and mix via integer hashing
    ix = int(x * 1000) + seed
    iy = int(y * 1000) + seed * 31
    iz = int(z * 1000) + seed * 97

    h = (ix * 73856093) ^ (iy * 19349669) ^ (iz * 83492791)
    h = ((h >> 13) ^ h) * 1274126177
    h = (h >> 16) ^ h

    return (h & 0xFFFF) / 65535.0


# ---------------------------------------------------------------------------
# Pure-logic weathering functions
# ---------------------------------------------------------------------------

def apply_edge_wear(
    mesh_data: dict[str, Any],
    strength: float = 0.5,
) -> list[float]:
    """Compute per-vertex edge wear mask from mesh curvature and edge annotations.

    At convex edges (protruding corners, ridges): higher wear values.
    These areas would naturally show wear from contact and abrasion.

    Enhancement-aware: If the mesh_data contains ``sharp_edges`` from the
    geometry enhancement pipeline, vertices on those edges receive a wear
    boost since sharp/creased edges are the most prominent wear locations.

    Args:
        mesh_data: Dict with vertices, faces, face_normals, vertex_normals, edges.
            Optional: ``sharp_edges`` (list of [a, b] pairs from enhancement).
        strength: Effect intensity 0-1.

    Returns:
        Per-vertex wear mask, values in [0, 1].
    """
    vertices = mesh_data["vertices"]
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Bug 13: ensure face normals
    _ensure_face_normals(mesh_data)
    # Bug 16: use cached convexity if available
    curvature = mesh_data.get("_cached_convexity")
    if curvature is None:
        curvature = _compute_edge_convexity(mesh_data)

    # Enhancement-aware: boost wear on vertices that lie on sharp/creased edges
    sharp_vert_boost: dict[int, float] = {}
    sharp_edges = mesh_data.get("sharp_edges", [])
    if sharp_edges:
        for edge in sharp_edges:
            if len(edge) >= 2:
                sharp_vert_boost[edge[0]] = 0.3
                sharp_vert_boost[edge[1]] = 0.3

    wear_mask: list[float] = []
    for vi in range(num_verts):
        # Only convex areas show wear (positive curvature)
        convexity = max(0.0, curvature.get(vi, 0.0))
        # Boost from sharp edge annotation (enhancement pipeline data)
        sharp_boost = sharp_vert_boost.get(vi, 0.0)
        # Add slight noise for variation
        noise = _simple_noise(*vertices[vi], seed=42) * 0.2
        value = (convexity + sharp_boost + noise) * strength
        wear_mask.append(max(0.0, min(1.0, value)))

    return wear_mask


def apply_dirt_accumulation(
    mesh_data: dict[str, Any],
    strength: float = 0.5,
) -> list[float]:
    """Compute per-vertex dirt accumulation mask.

    Dirt accumulates in:
      - Concave areas (crevices, corners): from curvature analysis
      - Bottom of objects: height gradient (more dirt at base)

    Args:
        mesh_data: Dict with vertices, faces, face_normals, vertex_normals, edges.
        strength: Effect intensity 0-1.

    Returns:
        Per-vertex dirt mask, values in [0, 1].
    """
    vertices = mesh_data["vertices"]
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Bug 13: ensure face normals
    _ensure_face_normals(mesh_data)
    # Bug 16: use cached convexity if available
    curvature = mesh_data.get("_cached_convexity")
    if curvature is None:
        curvature = _compute_edge_convexity(mesh_data)
    # Bug 17: use cached bounding box if available
    cached_bbox = mesh_data.get("_cached_bbox")
    if cached_bbox is not None:
        bbox_min, bbox_max = cached_bbox
    else:
        bbox_min, bbox_max = _compute_bounding_box(vertices)

    dirt_mask: list[float] = []
    for vi in range(num_verts):
        # Concave areas accumulate dirt (negative curvature)
        concavity = max(0.0, -curvature.get(vi, 0.0))

        # Height gradient: more dirt at bottom
        h = _height_factor(vertices[vi][2], bbox_min[2], bbox_max[2])
        height_dirt = 1.0 - h  # Invert: 1 at bottom, 0 at top

        # Noise for organic variation
        noise = _simple_noise(*vertices[vi], seed=137) * 0.15

        # Combine: concavity dominant, height secondary
        value = (concavity * 0.6 + height_dirt * 0.3 + noise) * strength
        dirt_mask.append(max(0.0, min(1.0, value)))

    return dirt_mask


def apply_moss_growth(
    mesh_data: dict[str, Any],
    strength: float = 0.3,
    direction: str = "bottom",
) -> list[float]:
    """Compute per-vertex moss growth mask.

    Moss grows on:
      - Upward-facing surfaces (face normal Y or Z component > 0)
      - Lower portions of structures (height gradient)
      - North-facing surfaces when direction="north"

    Only surfaces facing generally upward receive moss.

    Args:
        mesh_data: Dict with vertices, faces, face_normals, vertex_normals, edges.
        strength: Effect intensity 0-1.
        direction: "bottom" (height-based) or "north" (north-facing bias).

    Returns:
        Per-vertex moss mask, values in [0, 1].
    """
    vertices = mesh_data["vertices"]
    # Bug 13: ensure face normals
    _ensure_face_normals(mesh_data)
    face_normals = mesh_data.get("face_normals", [])
    faces = mesh_data["faces"]
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Bug 17: use cached bounding box if available
    cached_bbox = mesh_data.get("_cached_bbox")
    if cached_bbox is not None:
        bbox_min, bbox_max = cached_bbox
    else:
        bbox_min, bbox_max = _compute_bounding_box(vertices)

    # Compute per-vertex upward-facing factor from face normals
    vert_upward: dict[int, float] = {i: 0.0 for i in range(num_verts)}
    vert_face_count: dict[int, int] = {i: 0 for i in range(num_verts)}

    for fi, face in enumerate(faces):
        if fi < len(face_normals):
            normal = face_normals[fi]
            # Z-up convention: normal[2] is the up component
            up_factor = max(0.0, normal[2])
            for vi in face:
                vert_upward[vi] += up_factor
                vert_face_count[vi] += 1

    # Average and build mask
    moss_mask: list[float] = []
    for vi in range(num_verts):
        # Upward-facing requirement (threshold: at least partially upward)
        if vert_face_count[vi] > 0:
            avg_up = vert_upward[vi] / vert_face_count[vi]
        else:
            avg_up = 0.0

        # Upward threshold: must face at least 30 degrees from horizontal
        if avg_up < 0.3:
            moss_mask.append(0.0)
            continue

        # Height gradient: more moss at base
        h = _height_factor(vertices[vi][2], bbox_min[2], bbox_max[2])
        if direction == "bottom":
            height_moss = 1.0 - h  # More at bottom
        else:
            # North-facing: use Y component instead
            height_moss = 0.5  # Uniform if north-based

        # Noise for organic clumping
        noise = _simple_noise(*vertices[vi], seed=271) * 0.25

        value = (avg_up * 0.5 + height_moss * 0.3 + noise) * strength
        moss_mask.append(max(0.0, min(1.0, value)))

    return moss_mask


def apply_rain_staining(
    mesh_data: dict[str, Any],
    strength: float = 0.3,
) -> list[float]:
    """Compute per-vertex rain staining mask.

    Rain stains appear on:
      - Near-vertical surfaces (walls) -- face normal mostly horizontal
      - Top-down darkening streaks (height gradient)
      - Streaky pattern using noise variation

    Only near-vertical surfaces receive rain staining.

    Args:
        mesh_data: Dict with vertices, faces, face_normals, vertex_normals, edges.
        strength: Effect intensity 0-1.

    Returns:
        Per-vertex rain stain mask, values in [0, 1].
    """
    vertices = mesh_data["vertices"]
    # Bug 13: ensure face normals
    _ensure_face_normals(mesh_data)
    face_normals = mesh_data.get("face_normals", [])
    faces = mesh_data["faces"]
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Bug 17: use cached bounding box if available
    cached_bbox = mesh_data.get("_cached_bbox")
    if cached_bbox is not None:
        bbox_min, bbox_max = cached_bbox
    else:
        bbox_min, bbox_max = _compute_bounding_box(vertices)

    # Compute per-vertex verticality from face normals
    vert_vertical: dict[int, float] = {i: 0.0 for i in range(num_verts)}
    vert_face_count: dict[int, int] = {i: 0 for i in range(num_verts)}

    for fi, face in enumerate(faces):
        if fi < len(face_normals):
            normal = face_normals[fi]
            # Verticality: how horizontal the normal is (wall = normal mostly in XY)
            # abs(nz) near 0 = vertical surface, abs(nz) near 1 = horizontal surface
            verticality = 1.0 - abs(normal[2])
            for vi in face:
                vert_vertical[vi] += verticality
                vert_face_count[vi] += 1

    rain_mask: list[float] = []
    for vi in range(num_verts):
        if vert_face_count[vi] > 0:
            avg_vert = vert_vertical[vi] / vert_face_count[vi]
        else:
            avg_vert = 0.0

        # Must be near-vertical (threshold: at least 60% vertical)
        if avg_vert < 0.6:
            rain_mask.append(0.0)
            continue

        # Height gradient: rain stains flow from top down
        h = _height_factor(vertices[vi][2], bbox_min[2], bbox_max[2])
        # More staining at top (rain hits top first), streaks down
        top_bias = h

        # Streaky noise pattern (use X coordinate for vertical streaks)
        px = vertices[vi][0]
        streak_noise = _simple_noise(px * 5.0, 0.0, vertices[vi][2] * 2.0, seed=313)

        # Combine: verticality check already passed, modulate by height and streaks
        value = (top_bias * 0.5 + streak_noise * 0.4 + avg_vert * 0.1) * strength
        rain_mask.append(max(0.0, min(1.0, value)))

    return rain_mask


def apply_structural_settling(
    vertices: list[tuple[float, float, float]],
    strength: float = 0.01,
    seed: int = 42,
    *,
    _cached_bbox: tuple[
        tuple[float, float, float], tuple[float, float, float]
    ] | None = None,
) -> list[tuple[float, float, float]]:
    """Apply small random vertex displacements simulating structural settling.

    More displacement at the top of structures (gravity settling effect).
    Creates slight imperfections that make geometry look hand-built.

    Args:
        vertices: List of (x, y, z) vertex positions.
        strength: Maximum displacement distance.
        seed: Random seed for reproducibility.
        _cached_bbox: Optional pre-computed (min_corner, max_corner) to
            avoid redundant bounding box computation.

    Returns:
        New list of displaced vertex positions.
    """
    if not vertices:
        return []

    if _cached_bbox is not None:
        bbox_min, bbox_max = _cached_bbox
    else:
        bbox_min, bbox_max = _compute_bounding_box(vertices)
    rng = random.Random(seed)

    result: list[tuple[float, float, float]] = []
    for vi, v in enumerate(vertices):
        # More displacement at top (gravity settling)
        h = _height_factor(v[2], bbox_min[2], bbox_max[2])
        local_strength = strength * (0.3 + 0.7 * h)  # 30% at bottom, 100% at top

        # Random displacement in XYZ
        dx = rng.uniform(-local_strength, local_strength)
        dy = rng.uniform(-local_strength, local_strength)
        # Z displacement biased downward (gravity)
        dz = rng.uniform(-local_strength * 0.5, local_strength * 0.3)

        result.append((v[0] + dx, v[1] + dy, v[2] + dz))

    return result


def apply_corruption_veins(
    mesh_data: dict[str, Any],
    strength: float = 0.5,
) -> list[float]:
    """Compute per-vertex corruption vein mask.

    Purple corruption veins creep along surfaces, concentrated in crevices
    and spreading outward. Uses noise to create vein-like patterns.

    Args:
        mesh_data: Dict with vertices, faces, face_normals, vertex_normals, edges.
        strength: Effect intensity 0-1.

    Returns:
        Per-vertex corruption mask, values in [0, 1].
    """
    vertices = mesh_data["vertices"]
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Bug 16: use cached convexity if available
    curvature = mesh_data.get("_cached_convexity")
    if curvature is None:
        curvature = _compute_edge_convexity(mesh_data)

    corruption_mask: list[float] = []
    for vi in range(num_verts):
        # Corruption concentrates in concave areas
        concavity = max(0.0, -curvature.get(vi, 0.0))

        # Vein-like noise pattern (high frequency)
        noise1 = _simple_noise(
            vertices[vi][0] * 8.0, vertices[vi][1] * 8.0, vertices[vi][2] * 8.0,
            seed=666,
        )
        # Second noise layer for thresholding into veins
        noise2 = _simple_noise(
            vertices[vi][0] * 3.0, vertices[vi][1] * 3.0, vertices[vi][2] * 3.0,
            seed=999,
        )

        # Create vein pattern: threshold noise to create sharp vein shapes
        vein = 1.0 if noise1 > 0.65 else noise1 * 0.5
        spread = noise2 * 0.3

        value = (concavity * 0.3 + vein * 0.5 + spread * 0.2) * strength
        corruption_mask.append(max(0.0, min(1.0, value)))

    return corruption_mask


# ---------------------------------------------------------------------------
# Combined weathering application (pure logic)
# ---------------------------------------------------------------------------

def compute_weathered_vertex_colors(
    mesh_data: dict[str, Any],
    base_color: tuple[float, float, float, float],
    preset_name: str | None = None,
    effects: dict[str, float] | None = None,
    seed: int = 42,
) -> list[tuple[float, float, float, float]]:
    """Compute final vertex colors after applying weathering effects.

    Blends wear, dirt, moss, rain, and corruption masks into vertex colors.
    Pure logic -- no bpy dependency.

    Args:
        mesh_data: Mesh geometry data dict.
        base_color: Base RGBA color for the mesh.
        preset_name: Named preset from WEATHERING_PRESETS.
        effects: Override dict mapping effect name to strength.
        seed: Random seed for structural settling.

    Returns:
        List of RGBA tuples, one per vertex.
    """
    num_verts = len(mesh_data["vertices"])
    if num_verts == 0:
        return []

    # Resolve effect strengths
    if effects is not None:
        strengths = effects
    elif preset_name and preset_name in WEATHERING_PRESETS:
        strengths = WEATHERING_PRESETS[preset_name]
    else:
        strengths = WEATHERING_PRESETS["medium"]

    # Bug 13 fix: ensure face normals are available
    _ensure_face_normals(mesh_data)

    # Bug 16 fix: compute edge convexity once, cache in mesh_data
    if "_cached_convexity" not in mesh_data:
        mesh_data["_cached_convexity"] = _compute_edge_convexity(mesh_data)

    # Bug 17 fix: compute bounding box once, cache in mesh_data
    if "_cached_bbox" not in mesh_data:
        mesh_data["_cached_bbox"] = _compute_bounding_box(mesh_data["vertices"])

    # Compute individual masks
    wear_mask = apply_edge_wear(mesh_data, strengths.get("edge_wear", 0.0))
    dirt_mask = apply_dirt_accumulation(mesh_data, strengths.get("dirt", 0.0))
    moss_mask = apply_moss_growth(mesh_data, strengths.get("moss", 0.0))
    rain_mask = apply_rain_staining(mesh_data, strengths.get("rain", 0.0))
    corruption_mask = (
        apply_corruption_veins(mesh_data, strengths.get("corruption_veins", 0.0))
        if strengths.get("corruption_veins", 0.0) > 0.0
        else [0.0] * num_verts
    )

    # Blend into vertex colors
    colors: list[tuple[float, float, float, float]] = []
    for vi in range(num_verts):
        r, g, b, a = base_color

        # Layer 1: Edge wear -- lighten and smooth
        w = wear_mask[vi]
        r = r + (WEAR_TINT[0] - r) * w
        g = g + (WEAR_TINT[1] - g) * w
        b = b + (WEAR_TINT[2] - b) * w

        # Layer 2: Dirt accumulation -- darken
        d = dirt_mask[vi]
        r = r + (DIRT_TINT[0] - r) * d
        g = g + (DIRT_TINT[1] - g) * d
        b = b + (DIRT_TINT[2] - b) * d

        # Layer 3: Moss -- green tint
        m = moss_mask[vi]
        r = r + (MOSS_TINT[0] - r) * m
        g = g + (MOSS_TINT[1] - g) * m
        b = b + (MOSS_TINT[2] - b) * m

        # Layer 4: Rain staining -- darken
        rn = rain_mask[vi]
        r = r + (RAIN_TINT[0] - r) * rn
        g = g + (RAIN_TINT[1] - g) * rn
        b = b + (RAIN_TINT[2] - b) * rn

        # Layer 5: Corruption veins -- purple overlay
        c = corruption_mask[vi]
        r = r + (CORRUPTION_TINT[0] - r) * c
        g = g + (CORRUPTION_TINT[1] - g) * c
        b = b + (CORRUPTION_TINT[2] - b) * c

        colors.append((
            max(0.0, min(1.0, r)),
            max(0.0, min(1.0, g)),
            max(0.0, min(1.0, b)),
            a,
        ))

    return colors


# ---------------------------------------------------------------------------
# Blender handler (bpy-dependent)
# ---------------------------------------------------------------------------

def _extract_mesh_data(obj: Any) -> dict[str, Any]:
    """Extract mesh geometry data from a Blender object into pure-data dict.

    Requires bpy/bmesh. Returns dict matching the mesh_data format
    expected by all pure-logic weathering functions.
    """
    mesh = obj.data
    mesh.calc_normals_split()

    vertices: list[tuple[float, float, float]] = [
        (v.co.x, v.co.y, v.co.z) for v in mesh.vertices
    ]

    faces: list[tuple[int, ...]] = [
        tuple(p.vertices) for p in mesh.polygons
    ]

    face_normals: list[tuple[float, float, float]] = [
        (p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons
    ]

    vertex_normals: list[tuple[float, float, float]] = [
        (v.normal.x, v.normal.y, v.normal.z) for v in mesh.vertices
    ]

    edges: list[tuple[int, int]] = [
        (e.vertices[0], e.vertices[1]) for e in mesh.edges
    ]

    return {
        "vertices": vertices,
        "faces": faces,
        "face_normals": face_normals,
        "vertex_normals": vertex_normals,
        "edges": edges,
    }


def _write_vertex_colors(
    obj: Any,
    colors: list[tuple[float, float, float, float]],
    layer_name: str = "Weathering",
) -> None:
    """Write per-vertex colors to a vertex color layer on a Blender mesh.

    Creates the layer if it doesn't exist. Maps per-vertex colors to
    per-loop colors (Blender stores colors per loop, not per vertex).
    """
    mesh = obj.data

    # Create or get color attribute
    if layer_name not in mesh.color_attributes:
        mesh.color_attributes.new(
            name=layer_name,
            type="FLOAT_COLOR",
            domain="CORNER",
        )

    color_layer = mesh.color_attributes[layer_name]

    # Write per-loop colors from per-vertex data
    for poly in mesh.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            if vi < len(colors):
                color_layer.data[li].color = colors[vi]


def handle_apply_weathering(params: dict[str, Any]) -> dict[str, Any]:
    """Apply weathering effects to a mesh object via vertex colors.

    Params:
        object_name (str): Target mesh object name.
        weathering_preset (str): Preset name from WEATHERING_PRESETS.
            One of: light, medium, heavy, ancient, corrupted.
        effects (list[str], optional): Specific effects to apply.
            Overrides preset selection of effects but uses preset strengths.
        base_color (list[float], optional): Base RGBA color [r,g,b,a].
            Defaults to reading from the object's first material.
        structural_settling (bool, default True): Also apply vertex displacement.
        seed (int, default 42): Random seed for reproducibility.

    Returns:
        Dict with object_name, preset, effects_applied, vertex_count,
        masks (per-effect summary stats).
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    preset_name = params.get("weathering_preset", "medium")
    if preset_name not in VALID_PRESETS:
        raise ValueError(
            f"Invalid preset '{preset_name}'. "
            f"Valid presets: {sorted(VALID_PRESETS)}"
        )

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is type '{obj.type}', expected 'MESH'"
        )

    # Extract mesh data for pure-logic functions
    mesh_data = _extract_mesh_data(obj)
    num_verts = len(mesh_data["vertices"])

    # Resolve base color
    base_color_param = params.get("base_color")
    if base_color_param and len(base_color_param) >= 3:
        base_color = tuple(base_color_param[:4]) if len(base_color_param) >= 4 else (
            base_color_param[0], base_color_param[1], base_color_param[2], 1.0
        )
    elif obj.data.materials and obj.data.materials[0]:
        mat = obj.data.materials[0]
        if mat.use_nodes:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bc = bsdf.inputs["Base Color"].default_value
                base_color = (bc[0], bc[1], bc[2], bc[3])
            else:
                base_color = (0.15, 0.13, 0.11, 1.0)
        else:
            dc = mat.diffuse_color
            base_color = (dc[0], dc[1], dc[2], dc[3])
    else:
        # Default dark stone color
        base_color = (0.15, 0.13, 0.11, 1.0)

    # Build effect strengths from preset, filtered by requested effects
    preset = WEATHERING_PRESETS[preset_name]
    requested_effects = params.get("effects")
    if requested_effects:
        # Filter preset to only requested effects
        effect_strengths = {
            k: v for k, v in preset.items()
            if k in requested_effects and k in VALID_EFFECTS
        }
    else:
        effect_strengths = {
            k: v for k, v in preset.items()
            if k != "settling"  # settling handled separately
        }

    seed = params.get("seed", 42)

    # Compute vertex colors
    colors = compute_weathered_vertex_colors(
        mesh_data,
        base_color=base_color,
        effects=effect_strengths,
        seed=seed,
    )

    # Write vertex colors to mesh
    _write_vertex_colors(obj, colors, layer_name="Weathering")

    # Apply structural settling (vertex displacement)
    apply_settling = params.get("structural_settling", True)
    settling_strength = preset.get("settling", 0.0)
    if apply_settling and settling_strength > 0.0:
        if requested_effects is None or "settling" in requested_effects:
            new_verts = apply_structural_settling(
                mesh_data["vertices"],
                strength=settling_strength,
                seed=seed,
                _cached_bbox=mesh_data.get("_cached_bbox"),
            )
            # Write displaced vertices back to mesh
            for vi, v in enumerate(new_verts):
                obj.data.vertices[vi].co.x = v[0]
                obj.data.vertices[vi].co.y = v[1]
                obj.data.vertices[vi].co.z = v[2]
            obj.data.update()

    # Compute mask statistics for response
    wear_mask = apply_edge_wear(mesh_data, effect_strengths.get("edge_wear", 0.0))
    dirt_mask = apply_dirt_accumulation(mesh_data, effect_strengths.get("dirt", 0.0))

    effects_applied = sorted(effect_strengths.keys())
    if apply_settling and settling_strength > 0.0:
        if requested_effects is None or "settling" in requested_effects:
            effects_applied.append("settling")

    return {
        "status": "success",
        "object_name": object_name,
        "preset": preset_name,
        "effects_applied": effects_applied,
        "vertex_count": num_verts,
        "base_color": list(base_color),
        "mask_stats": {
            "edge_wear_max": max(wear_mask) if wear_mask else 0.0,
            "dirt_max": max(dirt_mask) if dirt_mask else 0.0,
        },
    }
