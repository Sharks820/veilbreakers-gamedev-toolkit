"""Multi-channel texture painting and projection/stencil painting.

Substance-Painter-style multi-channel brushing: one stroke writes to color,
roughness, metallic, normal, emission, and height textures simultaneously.
Projection painting projects 2D images onto 3D surfaces via camera,
planar, cylindrical, spherical, or tri-planar box mapping.  Stencil
painting masks the paint area with a black/white image.

Pure-logic helpers (testable without bpy):
  - compute_projection_uvs: Perspective / planar / cylindrical / spherical UV projection
  - compute_box_projection_uvs: Tri-planar box projection with blend
  - apply_stencil_mask: Stencil mask alpha compositing
  - compute_multi_channel_blend: Per-channel blend with MIX/ADD/MULTIPLY/OVERLAY/SUBTRACT/SCREEN
  - validate_projection_type: Reject invalid projection types
  - validate_blend_mode: Reject invalid blend modes
  - validate_paint_channels: Reject invalid channel names

Handler functions (require bpy):
  - handle_multi_channel_paint: Paint multiple PBR channels at a position
  - handle_paint_stroke: Multi-point stroke with pressure sensitivity
  - handle_projection_paint: Project 2D image onto mesh surface
  - handle_stencil_paint: Spray-paint through a stencil mask
"""

from __future__ import annotations

import math
from typing import Any

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PROJECTION_TYPES = frozenset({"camera", "planar", "cylindrical", "spherical", "box"})
VALID_PAINT_CHANNELS = frozenset({"color", "roughness", "metallic", "normal", "emission", "height"})
VALID_BLEND_MODES = frozenset({"MIX", "ADD", "MULTIPLY", "OVERLAY", "SUBTRACT", "SCREEN"})
VALID_FALLOFF_TYPES = frozenset({"SMOOTH", "LINEAR", "SHARP", "CONSTANT"})

# Map from PBR channel name to Principled BSDF input socket name
_CHANNEL_TO_BSDF_SOCKET: dict[str, str] = {
    "color": "Base Color",
    "roughness": "Roughness",
    "metallic": "Metallic",
    "normal": "Normal",
    "emission": "Emission Color",
    "height": "Displacement",
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_projection_type(projection_type: str) -> None:
    """Raise ``ValueError`` if *projection_type* is not recognised."""
    if projection_type not in VALID_PROJECTION_TYPES:
        raise ValueError(
            f"Invalid projection type '{projection_type}'. "
            f"Valid types: {sorted(VALID_PROJECTION_TYPES)}"
        )


def validate_blend_mode(blend_mode: str) -> None:
    """Raise ``ValueError`` if *blend_mode* is not recognised."""
    if blend_mode not in VALID_BLEND_MODES:
        raise ValueError(
            f"Invalid blend mode '{blend_mode}'. "
            f"Valid modes: {sorted(VALID_BLEND_MODES)}"
        )


def validate_paint_channels(channels: list[str] | set[str]) -> None:
    """Raise ``ValueError`` if any channel name is not recognised."""
    for ch in channels:
        if ch not in VALID_PAINT_CHANNELS:
            raise ValueError(
                f"Invalid paint channel '{ch}'. "
                f"Valid channels: {sorted(VALID_PAINT_CHANNELS)}"
            )


# ---------------------------------------------------------------------------
# Internal: falloff curve
# ---------------------------------------------------------------------------


def _apply_falloff(t: float, falloff_type: str) -> float:
    """Map normalised distance *t* (0 = center, 1 = edge) to weight in [0, 1].

    Supported falloff types: SMOOTH, LINEAR, SHARP, CONSTANT.
    """
    t = max(0.0, min(1.0, t))
    if falloff_type == "CONSTANT":
        return 1.0
    elif falloff_type == "LINEAR":
        return 1.0 - t
    elif falloff_type == "SHARP":
        return (1.0 - t) ** 2
    else:  # SMOOTH (default) -- cubic Hermite
        s = t * t * (3.0 - 2.0 * t)
        return 1.0 - s


# ---------------------------------------------------------------------------
# Internal: vector math helpers
# ---------------------------------------------------------------------------


def _vec_sub(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(ai - bi for ai, bi in zip(a, b))


def _vec_add(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(ai + bi for ai, bi in zip(a, b))


def _vec_scale(v: tuple[float, ...], s: float) -> tuple[float, ...]:
    return tuple(vi * s for vi in v)


def _vec_dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(ai * bi for ai, bi in zip(a, b))


def _vec_length(v: tuple[float, ...]) -> float:
    return math.sqrt(sum(vi * vi for vi in v))


def _vec_normalize(v: tuple[float, ...]) -> tuple[float, ...]:
    length = _vec_length(v)
    if length < 1e-12:
        return tuple(0.0 for _ in v)
    return tuple(vi / length for vi in v)


def _vec_cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


# ---------------------------------------------------------------------------
# Pure-logic: Multi-channel blend
# ---------------------------------------------------------------------------


def compute_multi_channel_blend(
    existing_values: dict[str, Any],
    paint_values: dict[str, Any],
    strength: float,
    blend_mode: str,
) -> dict[str, Any]:
    """Blend painted values with existing values per channel.

    Supports scalar (roughness, metallic, height, normal_strength) and
    colour-tuple (color, emission) channels.

    Args:
        existing_values: ``{channel: value}`` -- current texture values.
        paint_values: ``{channel: value}`` -- new paint values.
        strength: Overall paint opacity in [0, 1].
        blend_mode: One of MIX, ADD, MULTIPLY, OVERLAY, SUBTRACT, SCREEN.

    Returns:
        Blended ``{channel: value}`` dict.  Only channels present in both
        *existing_values* and *paint_values* are included.
    """
    validate_blend_mode(blend_mode)
    strength = max(0.0, min(1.0, strength))

    result: dict[str, Any] = {}

    for channel in paint_values:
        if channel not in existing_values:
            continue

        existing = existing_values[channel]
        paint = paint_values[channel]

        # Determine if we are blending tuples or scalars
        if isinstance(existing, (list, tuple)) and isinstance(paint, (list, tuple)):
            blended = _blend_tuple(tuple(existing), tuple(paint), strength, blend_mode)
            result[channel] = blended
        elif isinstance(existing, (int, float)) and isinstance(paint, (int, float)):
            blended = _blend_scalar(float(existing), float(paint), strength, blend_mode)
            result[channel] = blended
        else:
            # Type mismatch -- keep existing
            result[channel] = existing

    return result


def _blend_scalar(existing: float, paint: float, strength: float, mode: str) -> float:
    """Blend two scalar values with the given mode and strength."""
    if mode == "MIX":
        val = existing + (paint - existing) * strength
    elif mode == "ADD":
        val = existing + paint * strength
    elif mode == "SUBTRACT":
        val = existing - paint * strength
    elif mode == "MULTIPLY":
        factor = 1.0 + (paint - 1.0) * strength
        val = existing * factor
    elif mode == "OVERLAY":
        # Overlay: if existing < 0.5 -> 2*a*b, else 1 - 2*(1-a)*(1-b)
        if existing < 0.5:
            overlay = 2.0 * existing * paint
        else:
            overlay = 1.0 - 2.0 * (1.0 - existing) * (1.0 - paint)
        val = existing + (overlay - existing) * strength
    elif mode == "SCREEN":
        screen = 1.0 - (1.0 - existing) * (1.0 - paint)
        val = existing + (screen - existing) * strength
    else:
        val = existing + (paint - existing) * strength

    return max(0.0, min(1.0, val))


def _blend_tuple(
    existing: tuple[float, ...],
    paint: tuple[float, ...],
    strength: float,
    mode: str,
) -> tuple[float, ...]:
    """Blend two colour tuples component-wise."""
    length = min(len(existing), len(paint))
    result = []
    for i in range(length):
        result.append(_blend_scalar(existing[i], paint[i], strength, mode))
    return tuple(result)


# ---------------------------------------------------------------------------
# Pure-logic: Stencil mask
# ---------------------------------------------------------------------------


def apply_stencil_mask(
    paint_color: tuple[float, ...],
    mask_value: float,
    strength: float,
) -> tuple[float, ...]:
    """Apply stencil mask to a paint colour.

    Returns the colour with its last component (alpha) multiplied by
    ``mask_value * strength``.  If the tuple has fewer than 4 components,
    a fourth (alpha) component is appended.

    Args:
        paint_color: RGB or RGBA colour tuple (values in [0, 1]).
        mask_value: Stencil mask intensity at this pixel (0 = blocked, 1 = pass).
        strength: Overall paint strength in [0, 1].

    Returns:
        RGBA tuple with effective alpha = original_alpha * mask_value * strength,
        all components clamped to [0, 1].
    """
    mask_value = max(0.0, min(1.0, mask_value))
    strength = max(0.0, min(1.0, strength))

    components = list(paint_color)
    # Ensure we have an alpha channel
    while len(components) < 4:
        components.append(1.0)

    original_alpha = components[3]
    effective_alpha = original_alpha * mask_value * strength
    components[3] = max(0.0, min(1.0, effective_alpha))

    # Clamp colour channels too
    for i in range(3):
        components[i] = max(0.0, min(1.0, components[i]))

    return (components[0], components[1], components[2], components[3])


# ---------------------------------------------------------------------------
# Pure-logic: Projection UV computation
# ---------------------------------------------------------------------------


def compute_projection_uvs(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    projection_type: str,
    camera_pos: tuple[float, float, float] | None = None,
    camera_target: tuple[float, float, float] | None = None,
    fov: float = 60.0,
    plane_normal: tuple[float, float, float] | None = None,
    plane_point: tuple[float, float, float] | None = None,
) -> list[tuple[float, float]]:
    """Compute per-vertex UV coordinates from 3D projection.

    Supported projection types:

    * ``'camera'`` -- perspective projection from a camera viewpoint.
      Vertices behind the camera get ``(-1, -1)`` (clipped).
    * ``'planar'`` -- orthographic projection onto an infinite plane.
    * ``'cylindrical'`` -- cylindrical unwrap around the Y axis.
    * ``'spherical'`` -- equirectangular (lat/lon) projection.

    For ``'box'`` projection, use :func:`compute_box_projection_uvs` instead.

    Args:
        vertices: List of (x, y, z) world positions.
        faces: Face index lists (used for some projections; may be empty).
        projection_type: One of ``'camera'``, ``'planar'``, ``'cylindrical'``,
            ``'spherical'``.
        camera_pos: Camera world position (required for ``'camera'``).
        camera_target: Camera look-at target (required for ``'camera'``).
        fov: Vertical field of view in degrees (used for ``'camera'``).
        plane_normal: Normal of the projection plane (required for ``'planar'``).
        plane_point: A point on the projection plane (required for ``'planar'``).

    Returns:
        Per-vertex ``(u, v)`` list.  UVs are normalised to [0, 1] where
        possible.  Camera-clipped vertices return ``(-1, -1)``.
    """
    validate_projection_type(projection_type)

    if projection_type == "box":
        raise ValueError(
            "Use compute_box_projection_uvs() for box projection."
        )

    if projection_type == "camera":
        return _project_camera(vertices, camera_pos, camera_target, fov)
    elif projection_type == "planar":
        return _project_planar(vertices, plane_normal, plane_point)
    elif projection_type == "cylindrical":
        return _project_cylindrical(vertices)
    elif projection_type == "spherical":
        return _project_spherical(vertices)
    else:
        raise ValueError(f"Unhandled projection type: '{projection_type}'")


def _project_camera(
    vertices: list[tuple[float, float, float]],
    camera_pos: tuple[float, float, float] | None,
    camera_target: tuple[float, float, float] | None,
    fov: float,
) -> list[tuple[float, float]]:
    """Perspective projection from a camera viewpoint.

    Vertices behind the near plane are clipped to (-1, -1).
    Visible vertices are mapped to [0, 1] based on the projected bounding box.
    """
    if camera_pos is None or camera_target is None:
        raise ValueError("camera_pos and camera_target are required for camera projection")

    # Build camera basis (right-handed: forward = -Z, right = +X, up = +Y)
    forward = _vec_normalize(_vec_sub(camera_target, camera_pos))
    world_up = (0.0, 1.0, 0.0)

    # Handle degenerate case: forward is parallel to world up
    if abs(_vec_dot(forward, world_up)) > 0.999:
        world_up = (1.0, 0.0, 0.0)

    right = _vec_normalize(_vec_cross(forward, world_up))
    up = _vec_cross(right, forward)

    half_fov_tan = math.tan(math.radians(fov * 0.5))
    near = 0.001  # near clip distance

    # Project each vertex
    raw_uvs: list[tuple[float, float] | None] = []
    valid_us: list[float] = []
    valid_vs: list[float] = []

    for vx, vy, vz in vertices:
        # Vector from camera to vertex
        to_vert = _vec_sub((vx, vy, vz), camera_pos)

        # Depth along camera forward axis
        depth = _vec_dot(to_vert, forward)

        if depth < near:
            # Behind camera -- clip
            raw_uvs.append(None)
            continue

        # Project onto camera plane
        proj_x = _vec_dot(to_vert, right)
        proj_y = _vec_dot(to_vert, up)

        # Normalise by depth and FOV
        ndc_x = proj_x / (depth * half_fov_tan)
        ndc_y = proj_y / (depth * half_fov_tan)

        # NDC is in [-1, 1] for a 1:1 aspect ratio; remap to [0, 1]
        u = ndc_x * 0.5 + 0.5
        v = ndc_y * 0.5 + 0.5

        raw_uvs.append((u, v))
        valid_us.append(u)
        valid_vs.append(v)

    # If no valid vertices, return all clipped
    if not valid_us:
        return [(-1.0, -1.0)] * len(vertices)

    # Remap valid UVs to fill [0, 1] based on bounding box of projected points
    u_min, u_max = min(valid_us), max(valid_us)
    v_min, v_max = min(valid_vs), max(valid_vs)
    u_range = u_max - u_min if u_max - u_min > 1e-10 else 1.0
    v_range = v_max - v_min if v_max - v_min > 1e-10 else 1.0

    result: list[tuple[float, float]] = []
    for raw in raw_uvs:
        if raw is None:
            result.append((-1.0, -1.0))
        else:
            u = (raw[0] - u_min) / u_range
            v = (raw[1] - v_min) / v_range
            u = max(0.0, min(1.0, u))
            v = max(0.0, min(1.0, v))
            result.append((u, v))

    return result


def _project_planar(
    vertices: list[tuple[float, float, float]],
    plane_normal: tuple[float, float, float] | None,
    plane_point: tuple[float, float, float] | None,
) -> list[tuple[float, float]]:
    """Orthographic projection onto an infinite plane.

    The projection plane is defined by a point and normal.  Two tangent
    axes are constructed automatically.  UVs are normalised to [0, 1]
    from the bounding box of the projected coordinates.
    """
    if plane_normal is None or plane_point is None:
        raise ValueError("plane_normal and plane_point are required for planar projection")

    normal = _vec_normalize(plane_normal)

    # Build tangent frame on the plane
    world_up = (0.0, 1.0, 0.0)
    if abs(_vec_dot(normal, world_up)) > 0.999:
        world_up = (1.0, 0.0, 0.0)

    tangent_u = _vec_normalize(_vec_cross(normal, world_up))
    tangent_v = _vec_cross(normal, tangent_u)

    # Project each vertex onto the tangent axes
    raw_us: list[float] = []
    raw_vs: list[float] = []

    for vx, vy, vz in vertices:
        to_vert = _vec_sub((vx, vy, vz), plane_point)
        u = _vec_dot(to_vert, tangent_u)
        v = _vec_dot(to_vert, tangent_v)
        raw_us.append(u)
        raw_vs.append(v)

    # Normalise to [0, 1]
    if not raw_us:
        return []

    u_min, u_max = min(raw_us), max(raw_us)
    v_min, v_max = min(raw_vs), max(raw_vs)
    u_range = u_max - u_min if u_max - u_min > 1e-10 else 1.0
    v_range = v_max - v_min if v_max - v_min > 1e-10 else 1.0

    result: list[tuple[float, float]] = []
    for u, v in zip(raw_us, raw_vs):
        nu = (u - u_min) / u_range
        nv = (v - v_min) / v_range
        result.append((max(0.0, min(1.0, nu)), max(0.0, min(1.0, nv))))

    return result


def _project_cylindrical(
    vertices: list[tuple[float, float, float]],
) -> list[tuple[float, float]]:
    """Cylindrical projection around the Y axis.

    U wraps around the Y axis (0..1 mapping from -pi..pi).
    V is the normalised height along Y.

    The seam is at U=0 and U=1 (they represent the same angle: -pi / +pi).
    """
    if not vertices:
        return []

    raw_us: list[float] = []
    raw_vs: list[float] = []
    y_min = float("inf")
    y_max = float("-inf")

    for vx, vy, vz in vertices:
        angle = math.atan2(vx, vz)  # -pi .. pi
        u = (angle + math.pi) / (2.0 * math.pi)  # 0 .. 1
        raw_us.append(u)
        raw_vs.append(vy)
        y_min = min(y_min, vy)
        y_max = max(y_max, vy)

    y_range = y_max - y_min if y_max - y_min > 1e-10 else 1.0

    result: list[tuple[float, float]] = []
    for u, vy in zip(raw_us, raw_vs):
        v = (vy - y_min) / y_range
        result.append((max(0.0, min(1.0, u)), max(0.0, min(1.0, v))))

    return result


def _project_spherical(
    vertices: list[tuple[float, float, float]],
) -> list[tuple[float, float]]:
    """Equirectangular (spherical) projection.

    U = longitude (0..1 wrapping around Y axis).
    V = latitude (0 = south pole at -Y, 1 = north pole at +Y).

    The poles map to V=0 and V=1.  At the poles, U is 0.5 (atan2 of a
    zero-length XZ vector defaults to 0, remapped to 0.5).
    """
    if not vertices:
        return []

    result: list[tuple[float, float]] = []

    for vx, vy, vz in vertices:
        r = math.sqrt(vx * vx + vy * vy + vz * vz)
        if r < 1e-12:
            # Vertex at origin -- map to centre
            result.append((0.5, 0.5))
            continue

        # Latitude: asin(y/r) gives -pi/2 .. pi/2
        lat = math.asin(max(-1.0, min(1.0, vy / r)))
        v = (lat + math.pi / 2.0) / math.pi  # 0 .. 1

        # Longitude: atan2(x, z) gives -pi .. pi
        lon = math.atan2(vx, vz)
        u = (lon + math.pi) / (2.0 * math.pi)  # 0 .. 1

        result.append((max(0.0, min(1.0, u)), max(0.0, min(1.0, v))))

    return result


# ---------------------------------------------------------------------------
# Pure-logic: Box (tri-planar) projection
# ---------------------------------------------------------------------------


def compute_box_projection_uvs(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    face_normals: list[tuple[float, float, float]],
    blend_amount: float = 0.2,
) -> list[tuple[float, float]]:
    """Compute tri-planar box projection UVs.

    Each face selects the projection axis most aligned with its normal:
    * X-dominant -> project using (Y, Z).
    * Y-dominant -> project using (X, Z).
    * Z-dominant -> project using (X, Y).

    Per-vertex UVs are averaged from all faces that share the vertex,
    weighted by the alignment of each face normal with its dominant axis
    (sharper alignment = higher weight).

    The ``blend_amount`` parameter controls how much off-axis projections
    contribute.  At 0.0, only the dominant axis counts.  At 1.0, all three
    axes contribute equally.

    UVs are normalised to [0, 1] from the vertex position bounding box.

    Args:
        vertices: Per-vertex (x, y, z) positions.
        faces: Face index tuples.
        face_normals: Per-face (nx, ny, nz) normals (same order as *faces*).
        blend_amount: Blend factor in [0, 1].

    Returns:
        Per-vertex (u, v) list normalised to [0, 1].
    """
    blend_amount = max(0.0, min(1.0, blend_amount))

    if not vertices:
        return []

    # Compute bounding box for normalisation
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_range = x_max - x_min if x_max - x_min > 1e-10 else 1.0
    y_range = y_max - y_min if y_max - y_min > 1e-10 else 1.0
    z_range = z_max - z_min if z_max - z_min > 1e-10 else 1.0

    def _normalise_coord(val: float, vmin: float, vrange: float) -> float:
        return (val - vmin) / vrange

    # For each face, compute the projection axis and per-vertex UVs
    # Accumulate weighted UVs per vertex
    vert_uv_accum: list[list[float]] = [[0.0, 0.0] for _ in vertices]
    vert_weight_accum: list[float] = [0.0] * len(vertices)

    for face_idx, face in enumerate(faces):
        if face_idx >= len(face_normals):
            continue

        nx, ny, nz = face_normals[face_idx]
        abs_nx, abs_ny, abs_nz = abs(nx), abs(ny), abs(nz)

        # Compute axis weights
        # Dominant axis gets weight 1.0; others get blend_amount if > 0
        max_axis = max(abs_nx, abs_ny, abs_nz)
        if max_axis < 1e-10:
            continue

        # Weight for each axis: pow(abs_component / max_axis, sharpness)
        # sharpness is derived from blend_amount: lower blend -> sharper
        if blend_amount < 1e-6:
            # No blending: only dominant axis
            wx = 1.0 if abs_nx == max_axis else 0.0
            wy = 1.0 if abs_ny == max_axis else 0.0
            wz = 1.0 if abs_nz == max_axis else 0.0
        else:
            # Smooth blending using power function
            sharpness = 1.0 / max(blend_amount, 1e-6)
            wx = (abs_nx / max_axis) ** sharpness if abs_nx > 1e-10 else 0.0
            wy = (abs_ny / max_axis) ** sharpness if abs_ny > 1e-10 else 0.0
            wz = (abs_nz / max_axis) ** sharpness if abs_nz > 1e-10 else 0.0

        total_w = wx + wy + wz
        if total_w < 1e-10:
            continue
        wx /= total_w
        wy /= total_w
        wz /= total_w

        for vi in face:
            if vi >= len(vertices):
                continue
            vx, vy, vz = vertices[vi]

            # X-axis projection -> YZ
            u_x = _normalise_coord(vy, y_min, y_range)
            v_x = _normalise_coord(vz, z_min, z_range)

            # Y-axis projection -> XZ
            u_y = _normalise_coord(vx, x_min, x_range)
            v_y = _normalise_coord(vz, z_min, z_range)

            # Z-axis projection -> XY
            u_z = _normalise_coord(vx, x_min, x_range)
            v_z = _normalise_coord(vy, y_min, y_range)

            blended_u = wx * u_x + wy * u_y + wz * u_z
            blended_v = wx * v_x + wy * v_y + wz * v_z

            vert_uv_accum[vi][0] += blended_u
            vert_uv_accum[vi][1] += blended_v
            vert_weight_accum[vi] += 1.0

    # Average and clamp
    result: list[tuple[float, float]] = []
    for i in range(len(vertices)):
        w = vert_weight_accum[i]
        if w < 1e-10:
            # Vertex not part of any face -- fallback to XY projection
            vx, vy, vz = vertices[i]
            u = _normalise_coord(vx, x_min, x_range)
            v = _normalise_coord(vy, y_min, y_range)
        else:
            u = vert_uv_accum[i][0] / w
            v = vert_uv_accum[i][1] / w

        result.append((max(0.0, min(1.0, u)), max(0.0, min(1.0, v))))

    return result


# ---------------------------------------------------------------------------
# Blender handler: Multi-channel paint
# ---------------------------------------------------------------------------


def handle_multi_channel_paint(params: dict[str, Any]) -> dict[str, Any]:
    """Paint multiple PBR channels simultaneously at a position.

    One brush stroke paints colour, roughness, metallic, normal, emission,
    and height textures at the specified world or UV coordinate.  Only
    channels explicitly provided in *params* are affected.

    Args (via params dict):
        object_name (str): Target mesh object.
        paint_position (list): ``[x, y, z]`` world-space coordinate, **or**
        uv_coord (list): ``[u, v]`` direct UV coordinate.
        brush_radius (float): Brush radius.  Default ``0.05`` in UV space.
        falloff (str): SMOOTH / LINEAR / SHARP / CONSTANT.  Default SMOOTH.
        color (list): ``[r, g, b, a]`` base colour.
        roughness (float): Roughness value.
        metallic (float): Metallic value.
        normal_strength (float): Normal/bump strength.
        emission (list): ``[r, g, b]`` emission colour.
        height (float): Displacement height.
        blend_mode (str): MIX / ADD / MULTIPLY / OVERLAY.  Default MIX.
        strength (float): Overall paint opacity in [0, 1].  Default 1.0.

    Returns:
        Dict with status, channels painted, and pixel counts.
    """
    if bpy is None:
        return {"status": "error", "error": "bpy not available -- Blender required"}

    object_name = params.get("object_name")
    if not object_name:
        return {"status": "error", "error": "object_name is required"}

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return {"status": "error", "error": f"Object '{object_name}' not found"}
    if obj.type != "MESH":
        return {"status": "error", "error": f"Object '{object_name}' is not a mesh"}

    blend_mode = params.get("blend_mode", "MIX")
    if blend_mode not in VALID_BLEND_MODES:
        return {"status": "error", "error": f"Invalid blend_mode '{blend_mode}'"}

    falloff = params.get("falloff", "SMOOTH")
    if falloff not in VALID_FALLOFF_TYPES:
        return {"status": "error", "error": f"Invalid falloff '{falloff}'"}

    strength = max(0.0, min(1.0, float(params.get("strength", 1.0))))
    brush_radius = float(params.get("brush_radius", 0.05))

    # Resolve UV coordinate
    uv_center = params.get("uv_coord")
    paint_position = params.get("paint_position")

    if uv_center is None and paint_position is not None:
        # Raycast to find UV
        uv_center = _raycast_to_uv(obj, paint_position)
        if uv_center is None:
            return {"status": "error", "error": "paint_position did not hit the mesh surface"}

    if uv_center is None:
        return {"status": "error", "error": "Either paint_position or uv_coord is required"}

    # Collect channels to paint
    channel_values: dict[str, Any] = {}
    if "color" in params:
        channel_values["color"] = tuple(params["color"])
    if "roughness" in params:
        channel_values["roughness"] = float(params["roughness"])
    if "metallic" in params:
        channel_values["metallic"] = float(params["metallic"])
    if "normal_strength" in params:
        channel_values["normal"] = float(params["normal_strength"])
    if "emission" in params:
        channel_values["emission"] = tuple(params["emission"])
    if "height" in params:
        channel_values["height"] = float(params["height"])

    if not channel_values:
        return {"status": "error", "error": "No paint channels specified"}

    # Find material and image textures
    mat = _get_active_material(obj)
    if mat is None:
        return {"status": "error", "error": f"Object '{object_name}' has no material"}

    channel_images = _map_material_to_channel_images(mat)

    painted_channels: list[str] = []
    total_pixels = 0

    for channel_name, value in channel_values.items():
        if channel_name not in channel_images:
            continue

        img = channel_images[channel_name]
        count = _paint_image_at_uv(
            img, uv_center, brush_radius, falloff, strength, blend_mode,
            channel_name, value,
        )
        painted_channels.append(channel_name)
        total_pixels += count

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "uv_center": list(uv_center),
            "channels_painted": painted_channels,
            "total_pixels_affected": total_pixels,
            "blend_mode": blend_mode,
            "strength": strength,
        },
    }


# ---------------------------------------------------------------------------
# Blender handler: Paint stroke
# ---------------------------------------------------------------------------


def handle_paint_stroke(params: dict[str, Any]) -> dict[str, Any]:
    """Paint a continuous stroke across multiple points with pressure.

    Each point in the stroke applies multi-channel paint independently,
    with pressure modulating the effective strength.

    Args (via params dict):
        object_name (str): Target mesh object.
        stroke_points (list): ``[{position: [x,y,z], pressure: float}, ...]``
        channels (dict): Channel values (same keys as multi_channel_paint).
        brush_radius (float): Base brush radius.
        falloff (str): Falloff type.
        strength (float): Base paint strength.
        blend_mode (str): Blend mode.

    Returns:
        Dict with status and per-point results.
    """
    if bpy is None:
        return {"status": "error", "error": "bpy not available -- Blender required"}

    object_name = params.get("object_name")
    if not object_name:
        return {"status": "error", "error": "object_name is required"}

    stroke_points = params.get("stroke_points", [])
    if not stroke_points:
        return {"status": "error", "error": "stroke_points is required and cannot be empty"}

    channels = params.get("channels", {})
    if not channels:
        return {"status": "error", "error": "channels dict is required"}

    base_strength = max(0.0, min(1.0, float(params.get("strength", 1.0))))
    brush_radius = float(params.get("brush_radius", 0.05))
    falloff = params.get("falloff", "SMOOTH")
    blend_mode = params.get("blend_mode", "MIX")

    points_painted = 0
    total_pixels = 0

    for point in stroke_points:
        pressure = max(0.0, min(1.0, float(point.get("pressure", 1.0))))
        position = point.get("position")
        if position is None:
            continue

        # Build per-point params
        point_params: dict[str, Any] = {
            "object_name": object_name,
            "paint_position": position,
            "brush_radius": brush_radius * (0.5 + 0.5 * pressure),  # pressure affects radius
            "falloff": falloff,
            "blend_mode": blend_mode,
            "strength": base_strength * pressure,
        }
        point_params.update(channels)

        result = handle_multi_channel_paint(point_params)
        if result.get("status") == "success":
            points_painted += 1
            total_pixels += result["result"].get("total_pixels_affected", 0)

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "stroke_points_count": len(stroke_points),
            "points_painted": points_painted,
            "total_pixels_affected": total_pixels,
        },
    }


# ---------------------------------------------------------------------------
# Blender handler: Projection paint
# ---------------------------------------------------------------------------


def handle_projection_paint(params: dict[str, Any]) -> dict[str, Any]:
    """Project a 2D image onto a 3D mesh surface.

    Supports camera, planar, cylindrical, spherical, and box projection.
    The projected image is blended into the specified PBR channels.

    Args (via params dict):
        object_name (str): Target mesh.
        image_path (str): 2D image file to project.
        projection_type (str): camera / planar / cylindrical / spherical / box.
        camera_position (list): ``[x,y,z]`` (for camera projection).
        camera_target (list): ``[x,y,z]`` (for camera projection).
        fov (float): Field of view in degrees (for camera projection).
        plane_normal (list): ``[x,y,z]`` (for planar projection).
        plane_point (list): ``[x,y,z]`` (for planar projection).
        blend_amount (float): Box projection blend (for box projection).
        channels (list[str]): Which channels to affect.
        strength (float): Blend strength.
        mask_image_path (str): Optional stencil mask image.

    Returns:
        Dict with status and projection details.
    """
    if bpy is None:
        return {"status": "error", "error": "bpy not available -- Blender required"}

    object_name = params.get("object_name")
    if not object_name:
        return {"status": "error", "error": "object_name is required"}

    image_path = params.get("image_path")
    if not image_path:
        return {"status": "error", "error": "image_path is required"}

    projection_type = params.get("projection_type", "camera")
    if projection_type not in VALID_PROJECTION_TYPES:
        return {"status": "error", "error": f"Invalid projection_type '{projection_type}'"}

    channels = params.get("channels", ["color"])
    strength = max(0.0, min(1.0, float(params.get("strength", 1.0))))
    mask_image_path = params.get("mask_image_path")

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return {"status": "error", "error": f"Object '{object_name}' not found"}
    if obj.type != "MESH":
        return {"status": "error", "error": f"Object '{object_name}' is not a mesh"}

    mesh = obj.data

    # Load projection image
    try:
        proj_img = bpy.data.images.load(image_path, check_existing=True)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to load image: {exc}"}

    # Load optional mask
    mask_img = None
    if mask_image_path:
        try:
            mask_img = bpy.data.images.load(mask_image_path, check_existing=True)
        except Exception as exc:
            return {"status": "error", "error": f"Failed to load mask image: {exc}"}

    # Get mesh data
    world_matrix = obj.matrix_world
    verts = []
    for v in mesh.vertices:
        co = world_matrix @ v.co
        verts.append((co.x, co.y, co.z))

    faces = [tuple(p.vertices) for p in mesh.polygons]
    face_normals = [(p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons]

    # Compute projection UVs
    if projection_type == "box":
        proj_uvs = compute_box_projection_uvs(
            verts, faces, face_normals,
            blend_amount=float(params.get("blend_amount", 0.2)),
        )
    else:
        proj_uvs = compute_projection_uvs(
            verts, faces, projection_type,
            camera_pos=tuple(params["camera_position"]) if "camera_position" in params else None,
            camera_target=tuple(params["camera_target"]) if "camera_target" in params else None,
            fov=float(params.get("fov", 60.0)),
            plane_normal=tuple(params["plane_normal"]) if "plane_normal" in params else None,
            plane_point=tuple(params["plane_point"]) if "plane_point" in params else None,
        )

    # Get material channel images
    mat = _get_active_material(obj)
    if mat is None:
        return {"status": "error", "error": f"Object '{object_name}' has no material"}

    channel_images = _map_material_to_channel_images(mat)

    # Project image onto each channel
    projected_channels: list[str] = []
    total_pixels = 0

    for ch_name in channels:
        if ch_name not in channel_images:
            continue

        target_img = channel_images[ch_name]
        count = _project_image_onto_texture(
            target_img, proj_img, proj_uvs, mesh, strength,
            mask_img=mask_img,
        )
        projected_channels.append(ch_name)
        total_pixels += count

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "projection_type": projection_type,
            "channels_projected": projected_channels,
            "total_pixels_affected": total_pixels,
            "source_image": image_path,
            "strength": strength,
        },
    }


# ---------------------------------------------------------------------------
# Blender handler: Stencil paint
# ---------------------------------------------------------------------------


def handle_stencil_paint(params: dict[str, Any]) -> dict[str, Any]:
    """Paint through a stencil mask onto the mesh surface.

    Like spray-painting through a cut-out: the stencil image controls
    where paint lands.  White pixels in the stencil = paint through,
    black pixels = no paint.

    Args (via params dict):
        object_name (str): Target mesh.
        stencil_image_path (str): Black/white mask image.
        paint_color (list): ``[r, g, b, a]`` paint colour.
        paint_roughness (float): Optional roughness value.
        paint_metallic (float): Optional metallic value.
        brush_size_factor (float): Scale factor for stencil on surface.
        rotation (float): Stencil rotation in degrees.

    Returns:
        Dict with status and pixel counts.
    """
    if bpy is None:
        return {"status": "error", "error": "bpy not available -- Blender required"}

    object_name = params.get("object_name")
    if not object_name:
        return {"status": "error", "error": "object_name is required"}

    stencil_path = params.get("stencil_image_path")
    if not stencil_path:
        return {"status": "error", "error": "stencil_image_path is required"}

    paint_color = tuple(params.get("paint_color", [1.0, 1.0, 1.0, 1.0]))
    paint_roughness = params.get("paint_roughness")
    paint_metallic = params.get("paint_metallic")
    brush_size_factor = float(params.get("brush_size_factor", 1.0))
    rotation_deg = float(params.get("rotation", 0.0))

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return {"status": "error", "error": f"Object '{object_name}' not found"}
    if obj.type != "MESH":
        return {"status": "error", "error": f"Object '{object_name}' is not a mesh"}

    # Load stencil image
    try:
        stencil_img = bpy.data.images.load(stencil_path, check_existing=True)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to load stencil: {exc}"}

    mat = _get_active_material(obj)
    if mat is None:
        return {"status": "error", "error": f"Object '{object_name}' has no material"}

    channel_images = _map_material_to_channel_images(mat)

    stencil_w, stencil_h = stencil_img.size
    stencil_pixels = list(stencil_img.pixels)
    rotation_rad = math.radians(rotation_deg)
    cos_r = math.cos(rotation_rad)
    sin_r = math.sin(rotation_rad)

    total_pixels = 0
    painted_channels: list[str] = []

    # Paint colour channel
    if "color" in channel_images:
        target = channel_images["color"]
        tw, th = target.size
        target_pixels = list(target.pixels)

        for py_idx in range(th):
            for px_idx in range(tw):
                # Map target pixel to stencil coordinates
                su = (px_idx / tw - 0.5) / brush_size_factor
                sv = (py_idx / th - 0.5) / brush_size_factor

                # Apply rotation
                ru = su * cos_r - sv * sin_r + 0.5
                rv = su * sin_r + sv * cos_r + 0.5

                if ru < 0.0 or ru >= 1.0 or rv < 0.0 or rv >= 1.0:
                    continue

                # Sample stencil
                sx = int(ru * (stencil_w - 1))
                sy = int(rv * (stencil_h - 1))
                stencil_idx = (sy * stencil_w + sx) * 4
                if stencil_idx + 3 >= len(stencil_pixels):
                    continue

                mask_value = stencil_pixels[stencil_idx]  # Red channel as mask

                if mask_value < 0.001:
                    continue

                masked = apply_stencil_mask(paint_color, mask_value, 1.0)

                target_idx = (py_idx * tw + px_idx) * 4
                if target_idx + 3 >= len(target_pixels):
                    continue

                for c in range(4):
                    existing = target_pixels[target_idx + c]
                    target_pixels[target_idx + c] = existing + (masked[c] - existing) * masked[3]

                total_pixels += 1

        target.pixels[:] = target_pixels
        target.update()
        painted_channels.append("color")

    # Paint roughness channel
    if paint_roughness is not None and "roughness" in channel_images:
        target = channel_images["roughness"]
        tw, th = target.size
        target_pixels = list(target.pixels)

        for py_idx in range(th):
            for px_idx in range(tw):
                su = (px_idx / tw - 0.5) / brush_size_factor
                sv = (py_idx / th - 0.5) / brush_size_factor
                ru = su * cos_r - sv * sin_r + 0.5
                rv = su * sin_r + sv * cos_r + 0.5

                if ru < 0.0 or ru >= 1.0 or rv < 0.0 or rv >= 1.0:
                    continue

                sx = int(ru * (stencil_w - 1))
                sy = int(rv * (stencil_h - 1))
                stencil_idx = (sy * stencil_w + sx) * 4
                if stencil_idx + 3 >= len(stencil_pixels):
                    continue

                mask_value = stencil_pixels[stencil_idx]
                if mask_value < 0.001:
                    continue

                effective = mask_value
                target_idx = (py_idx * tw + px_idx) * 4
                if target_idx >= len(target_pixels):
                    continue

                existing = target_pixels[target_idx]
                target_pixels[target_idx] = existing + (paint_roughness - existing) * effective

        target.pixels[:] = target_pixels
        target.update()
        painted_channels.append("roughness")

    # Paint metallic channel
    if paint_metallic is not None and "metallic" in channel_images:
        target = channel_images["metallic"]
        tw, th = target.size
        target_pixels = list(target.pixels)

        for py_idx in range(th):
            for px_idx in range(tw):
                su = (px_idx / tw - 0.5) / brush_size_factor
                sv = (py_idx / th - 0.5) / brush_size_factor
                ru = su * cos_r - sv * sin_r + 0.5
                rv = su * sin_r + sv * cos_r + 0.5

                if ru < 0.0 or ru >= 1.0 or rv < 0.0 or rv >= 1.0:
                    continue

                sx = int(ru * (stencil_w - 1))
                sy = int(rv * (stencil_h - 1))
                stencil_idx = (sy * stencil_w + sx) * 4
                if stencil_idx + 3 >= len(stencil_pixels):
                    continue

                mask_value = stencil_pixels[stencil_idx]
                if mask_value < 0.001:
                    continue

                target_idx = (py_idx * tw + px_idx) * 4
                if target_idx >= len(target_pixels):
                    continue

                existing = target_pixels[target_idx]
                target_pixels[target_idx] = existing + (paint_metallic - existing) * mask_value

        target.pixels[:] = target_pixels
        target.update()
        painted_channels.append("metallic")

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "stencil_image": stencil_path,
            "channels_painted": painted_channels,
            "total_pixels_affected": total_pixels,
            "rotation": rotation_deg,
            "brush_size_factor": brush_size_factor,
        },
    }


# ---------------------------------------------------------------------------
# Internal Blender helpers
# ---------------------------------------------------------------------------


def _get_active_material(obj: Any) -> Any:
    """Return the active material of an object, or None."""
    if not obj.data.materials:
        return None
    mat = obj.active_material
    if mat is None and len(obj.data.materials) > 0:
        mat = obj.data.materials[0]
    return mat


def _map_material_to_channel_images(mat: Any) -> dict[str, Any]:
    """Map PBR channel names to Blender image datablocks from the node tree.

    Walks the Principled BSDF node and traces each input back to an
    Image Texture node.  Returns ``{channel_name: bpy.types.Image}``.
    """
    if not mat.use_nodes or not mat.node_tree:
        return {}

    # Find Principled BSDF
    bsdf = None
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            bsdf = node
            break

    if bsdf is None:
        return {}

    result: dict[str, Any] = {}

    socket_to_channel = {
        "Base Color": "color",
        "Roughness": "roughness",
        "Metallic": "metallic",
        "Normal": "normal",
        "Emission Color": "emission",
        "Emission": "emission",  # Blender 3.x fallback
    }

    for socket_name, channel_name in socket_to_channel.items():
        inp = bsdf.inputs.get(socket_name)
        if inp is None or not inp.links:
            continue

        # Trace back through links (handle Normal Map nodes, etc.)
        linked_node = inp.links[0].from_node
        img = _trace_to_image(linked_node)
        if img is not None:
            result[channel_name] = img

    return result


def _trace_to_image(node: Any) -> Any:
    """Trace from a node back to an Image Texture node, returning the image."""
    if node.type == "TEX_IMAGE" and node.image is not None:
        return node.image

    # Look one level deeper (e.g. Normal Map -> Image Texture)
    for inp in node.inputs:
        if inp.links:
            linked = inp.links[0].from_node
            if linked.type == "TEX_IMAGE" and linked.image is not None:
                return linked.image

    return None


def _raycast_to_uv(obj: Any, position: list[float]) -> tuple[float, float] | None:
    """Raycast from a world position to find UV coordinates on the mesh.

    Casts a ray from the position toward the mesh surface.  Returns the
    UV coordinate at the hit point, or ``None`` if no hit.
    """
    from mathutils import Vector

    # Cast toward the object centre
    origin = Vector(position)
    target = obj.matrix_world.translation
    direction = (target - origin).normalized()

    # Use the scene's raycast via the object's evaluated mesh
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result, location, normal, face_index = obj.ray_cast(
        obj.matrix_world.inverted() @ origin,
        obj.matrix_world.inverted().to_3x3() @ direction,
    )

    if not result:
        return None

    mesh = obj.data
    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        return None

    poly = mesh.polygons[face_index]
    # Use first loop UV as approximation (proper barycentric would be better
    # but this is sufficient for brush centre placement)
    loop_idx = poly.loop_indices[0]
    uv = uv_layer.data[loop_idx].uv
    return (uv.x, uv.y)


def _paint_image_at_uv(
    img: Any,
    uv_center: tuple[float, float],
    brush_radius: float,
    falloff: str,
    strength: float,
    blend_mode: str,
    channel_name: str,
    value: Any,
) -> int:
    """Paint a circular brush stamp into a Blender image at UV coordinates.

    Returns the number of pixels affected.
    """
    w, h = img.size
    pixels = list(img.pixels)

    # Convert UV to pixel space
    cx_px = uv_center[0] * w
    cy_px = uv_center[1] * h
    radius_px = brush_radius * max(w, h)

    # Bounding box in pixels
    x_min = max(0, int(cx_px - radius_px))
    x_max = min(w - 1, int(cx_px + radius_px))
    y_min = max(0, int(cy_px - radius_px))
    y_max = min(h - 1, int(cy_px + radius_px))

    count = 0

    for py in range(y_min, y_max + 1):
        for px in range(x_min, x_max + 1):
            dx = px - cx_px
            dy = py - cy_px
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > radius_px:
                continue

            t = dist / radius_px if radius_px > 0 else 0
            weight = _apply_falloff(t, falloff)
            effective = strength * weight

            idx = (py * w + px) * 4

            if channel_name == "color" and isinstance(value, tuple):
                for c in range(min(len(value), 4)):
                    existing = pixels[idx + c]
                    blended = _blend_scalar(existing, value[c], effective, blend_mode)
                    pixels[idx + c] = blended
            elif channel_name == "emission" and isinstance(value, tuple):
                for c in range(min(len(value), 3)):
                    existing = pixels[idx + c]
                    blended = _blend_scalar(existing, value[c], effective, blend_mode)
                    pixels[idx + c] = blended
            elif channel_name in ("roughness", "metallic", "normal", "height"):
                scalar_val = float(value)
                existing = pixels[idx]  # Single-channel textures use R
                blended = _blend_scalar(existing, scalar_val, effective, blend_mode)
                pixels[idx] = blended
                # Set G and B to same value for greyscale
                pixels[idx + 1] = blended
                pixels[idx + 2] = blended

            count += 1

    img.pixels[:] = pixels
    img.update()
    return count


def _project_image_onto_texture(
    target_img: Any,
    source_img: Any,
    proj_uvs: list[tuple[float, float]],
    mesh: Any,
    strength: float,
    mask_img: Any | None = None,
) -> int:
    """Project a source image onto a target texture via projection UVs.

    For each face in the mesh, rasterises the face in the target texture's
    UV space and samples the source image at the projection UVs.

    Returns the number of pixels written.
    """
    tw, th = target_img.size
    target_pixels = list(target_img.pixels)
    sw, sh = source_img.size
    source_pixels = list(source_img.pixels)

    mask_pixels = None
    mw, mh = 0, 0
    if mask_img is not None:
        mw, mh = mask_img.size
        mask_pixels = list(mask_img.pixels)

    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        return 0

    count = 0

    for poly in mesh.polygons:
        loop_indices = list(poly.loop_indices)
        if len(loop_indices) < 3:
            continue

        # Get UV coordinates and projection UVs for this face's vertices
        face_tex_uvs = []
        face_proj_uvs = []
        for li in loop_indices:
            uv = uv_layer.data[li].uv
            face_tex_uvs.append((uv.x, uv.y))
            vi = mesh.loops[li].vertex_index
            if vi < len(proj_uvs):
                face_proj_uvs.append(proj_uvs[vi])
            else:
                face_proj_uvs.append((0.0, 0.0))

        # Triangulate the face (fan triangulation)
        for tri_idx in range(1, len(loop_indices) - 1):
            t_uvs = [face_tex_uvs[0], face_tex_uvs[tri_idx], face_tex_uvs[tri_idx + 1]]
            p_uvs = [face_proj_uvs[0], face_proj_uvs[tri_idx], face_proj_uvs[tri_idx + 1]]

            # Rasterise triangle in texture space
            count += _rasterise_triangle(
                t_uvs, p_uvs, tw, th, target_pixels,
                sw, sh, source_pixels, strength,
                mw, mh, mask_pixels,
            )

    target_img.pixels[:] = target_pixels
    target_img.update()
    return count


def _rasterise_triangle(
    tex_uvs: list[tuple[float, float]],
    proj_uvs: list[tuple[float, float]],
    tw: int, th: int, target_pixels: list[float],
    sw: int, sh: int, source_pixels: list[float],
    strength: float,
    mw: int, mh: int, mask_pixels: list[float] | None,
) -> int:
    """Rasterise a single triangle: sample source at projected UVs, write to target.

    Uses scanline rasterisation with barycentric interpolation.
    Returns pixel count.
    """
    # Convert texture UVs to pixel space
    px_coords = [(u * tw, v * th) for u, v in tex_uvs]

    # Bounding box
    xs = [p[0] for p in px_coords]
    ys = [p[1] for p in px_coords]
    x_min = max(0, int(min(xs)))
    x_max = min(tw - 1, int(max(xs)) + 1)
    y_min = max(0, int(min(ys)))
    y_max = min(th - 1, int(max(ys)) + 1)

    count = 0
    ax, ay = px_coords[0]
    bx, by = px_coords[1]
    cx_, cy_ = px_coords[2]

    # Precompute barycentric denominator
    denom = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
    if abs(denom) < 1e-10:
        return 0

    inv_denom = 1.0 / denom

    for py in range(y_min, y_max + 1):
        for px in range(x_min, x_max + 1):
            # Barycentric coordinates
            w0 = ((by - cy_) * (px - cx_) + (cx_ - bx) * (py - cy_)) * inv_denom
            w1 = ((cy_ - ay) * (px - cx_) + (ax - cx_) * (py - cy_)) * inv_denom
            w2 = 1.0 - w0 - w1

            if w0 < 0 or w1 < 0 or w2 < 0:
                continue

            # Interpolate projection UV
            pu = w0 * proj_uvs[0][0] + w1 * proj_uvs[1][0] + w2 * proj_uvs[2][0]
            pv = w0 * proj_uvs[0][1] + w1 * proj_uvs[1][1] + w2 * proj_uvs[2][1]

            # Skip clipped projection UVs
            if pu < 0 or pu > 1 or pv < 0 or pv > 1:
                continue

            # Sample source image
            sx_px = int(pu * (sw - 1))
            sy_px = int(pv * (sh - 1))
            src_idx = (sy_px * sw + sx_px) * 4
            if src_idx + 3 >= len(source_pixels):
                continue

            # Sample mask if present
            mask_val = 1.0
            if mask_pixels is not None and mw > 0 and mh > 0:
                mx = int(pu * (mw - 1))
                my = int(pv * (mh - 1))
                mi = (my * mw + mx) * 4
                if mi < len(mask_pixels):
                    mask_val = mask_pixels[mi]  # R channel

            effective = strength * mask_val

            # Write to target
            t_idx = (py * tw + px) * 4
            if t_idx + 3 >= len(target_pixels):
                continue

            for c in range(4):
                src_val = source_pixels[src_idx + c]
                existing = target_pixels[t_idx + c]
                target_pixels[t_idx + c] = existing + (src_val - existing) * effective

            count += 1

    return count
