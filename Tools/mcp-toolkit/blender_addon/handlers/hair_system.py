"""Hair style and facial hair mesh generation for VeilBreakers characters.

Pure-logic module (NO bpy imports). Provides:
- generate_hair_mesh: Generate hair card strips arranged around the head
- get_helmet_compatible_hair: Modify hair for helmet compatibility
- generate_facial_hair_mesh: Generate facial hair cards on the face surface

Hair cards are flat quads with root-to-tip UV gradient mapping, suitable
for alpha-tested hair rendering in Unity. Each style produces a distinct
silhouette through variation in card count, length, and coverage pattern.

All functions return pure data (vertices, faces, UVs, metadata).
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Hair style definitions
# ---------------------------------------------------------------------------

HAIR_STYLES: dict[str, dict[str, Any]] = {
    # Male styles
    "short_crop": {"card_count": 30, "length": 0.05, "coverage": "full"},
    "medium_swept": {"card_count": 50, "length": 0.12, "coverage": "full"},
    "long_flowing": {"card_count": 80, "length": 0.25, "coverage": "full"},
    "ponytail": {"card_count": 60, "length": 0.20, "coverage": "back_gathered"},
    "mohawk": {"card_count": 25, "length": 0.10, "coverage": "center_strip"},
    "bald": {"card_count": 0},
    "shaved_sides": {"card_count": 40, "length": 0.08, "coverage": "top_only"},
    # Female styles
    "short_bob": {"card_count": 45, "length": 0.08, "coverage": "full"},
    "long_straight": {"card_count": 90, "length": 0.30, "coverage": "full"},
    "braided": {"card_count": 60, "length": 0.22, "coverage": "braids"},
    "updo": {"card_count": 50, "length": 0.05, "coverage": "gathered_top"},
    "wild_loose": {"card_count": 100, "length": 0.20, "coverage": "full_wild"},
}

FACIAL_HAIR_STYLES: dict[str, dict[str, Any]] = {
    "clean_shaven": {"card_count": 0},
    "stubble": {"card_count": 20, "coverage": "jaw_chin", "length": 0.005},
    "short_beard": {"card_count": 40, "coverage": "jaw_chin_cheeks", "length": 0.02},
    "full_beard": {"card_count": 70, "coverage": "jaw_chin_cheeks_neck", "length": 0.05},
    "long_beard": {"card_count": 90, "coverage": "jaw_chin_cheeks_neck", "length": 0.12},
    "braided_beard": {"card_count": 80, "coverage": "jaw_chin", "length": 0.10, "braids": True},
    "mustache": {"card_count": 15, "coverage": "upper_lip", "length": 0.03},
    "goatee": {"card_count": 25, "coverage": "chin_lip", "length": 0.04},
}

# Coverage angle ranges (azimuth in radians around the head, measured from front)
# 0 = front, pi/2 = right side, pi = back, 3pi/2 = left side
_COVERAGE_RANGES: dict[str, list[tuple[float, float]]] = {
    "full": [(0.3, 2 * math.pi - 0.3)],  # Full wrap minus face area
    "back_gathered": [(math.pi - 0.5, math.pi + 0.5)],  # Narrow band at back
    "center_strip": [(math.pi - 0.15, math.pi + 0.15)],  # Thin center strip front-to-back
    "top_only": [(0.5, 2 * math.pi - 0.5)],  # Top/crown area
    "full_wild": [(0.2, 2 * math.pi - 0.2)],  # Wider coverage, wilder placement
    "braids": [(0.8, 2 * math.pi - 0.8)],  # Side and back braids
    "gathered_top": [(0.4, 2 * math.pi - 0.4)],  # Gathered up top
}

# Facial hair coverage regions - parametric positions on the face
# Defined as (elevation_min, elevation_max, azimuth_min, azimuth_max)
# Elevation: 0 = top of face, pi = bottom; Azimuth: 0 = front center
_FACIAL_COVERAGE_REGIONS: dict[str, list[tuple[float, float, float, float]]] = {
    "jaw_chin": [
        (1.6, 2.2, -0.8, 0.8),   # Jaw line
        (2.0, 2.5, -0.4, 0.4),   # Chin
    ],
    "jaw_chin_cheeks": [
        (1.4, 2.2, -1.0, 1.0),   # Jaw + cheeks
        (2.0, 2.5, -0.4, 0.4),   # Chin
    ],
    "jaw_chin_cheeks_neck": [
        (1.4, 2.2, -1.0, 1.0),   # Jaw + cheeks
        (2.0, 2.5, -0.4, 0.4),   # Chin
        (2.3, 2.8, -0.6, 0.6),   # Neck
    ],
    "upper_lip": [
        (1.6, 1.9, -0.3, 0.3),   # Upper lip area
    ],
    "chin_lip": [
        (1.7, 2.0, -0.3, 0.3),   # Lower lip area
        (2.0, 2.4, -0.3, 0.3),   # Chin
    ],
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _compute_dimensions(
    verts: list[Vec3],
) -> dict[str, float]:
    if not verts:
        return {"width": 0.0, "height": 0.0, "depth": 0.0}
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "depth": max(zs) - min(zs),
    }


def _make_result(
    name: str,
    vertices: list[Vec3],
    faces: list[tuple[int, ...]],
    uvs: list[Vec2] | None = None,
    **extra_meta: Any,
) -> MeshSpec:
    dims = _compute_dimensions(vertices)
    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs or [],
        "metadata": {
            "name": name,
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            "dimensions": dims,
            **extra_meta,
        },
    }


def _distribute_angles(
    count: int,
    coverage: str,
    seed_offset: float = 0.0,
) -> list[float]:
    """Distribute card angles within coverage range(s).

    Returns a list of azimuth angles (radians) where hair cards
    should be placed around the head.
    """
    ranges = _COVERAGE_RANGES.get(coverage, _COVERAGE_RANGES["full"])

    # Calculate total arc length across all ranges
    total_arc = sum(r[1] - r[0] for r in ranges)
    if total_arc <= 0 or count <= 0:
        return []

    angles: list[float] = []
    cards_placed = 0

    for rng_start, rng_end in ranges:
        arc = rng_end - rng_start
        # Proportional count for this range
        n = max(1, round(count * arc / total_arc))
        if cards_placed + n > count:
            n = count - cards_placed
        if n <= 0:
            continue

        step = arc / max(n, 1)
        for i in range(n):
            # Add slight pseudo-random jitter using golden ratio
            jitter = ((i * 0.618033988749895 + seed_offset) % 1.0 - 0.5) * step * 0.3
            angle = rng_start + step * (i + 0.5) + jitter
            angles.append(angle)
            cards_placed += 1

        if cards_placed >= count:
            break

    return angles[:count]


def _generate_hair_card(
    root_pos: Vec3,
    direction: Vec3,
    length: float,
    card_width: float,
    vert_offset: int,
    segments: int = 3,
) -> tuple[list[Vec3], list[tuple[int, ...]], list[Vec2]]:
    """Generate a single hair card strip.

    A hair card is a series of quads extending from root_pos in the given
    direction, with proper UV mapping (U: 0-1 across width, V: 0 at root,
    1 at tip).

    Args:
        root_pos: Base position of the card.
        direction: Normalized growth direction (x, y, z).
        length: Total length of the card.
        card_width: Width of the card strip.
        vert_offset: Starting vertex index for face indexing.
        segments: Number of quad segments along the card length.

    Returns:
        (vertices, faces, uvs) for this card.
    """
    verts: list[Vec3] = []
    uvs: list[Vec2] = []
    faces: list[tuple[int, ...]] = []

    dx, dy, dz = direction

    # Compute perpendicular vector for card width
    # Cross direction with up vector (0, 0, 1) to get tangent
    # If direction is nearly vertical, use (1, 0, 0) instead
    if abs(dz) > 0.95:
        up = (1.0, 0.0, 0.0)
    else:
        up = (0.0, 0.0, 1.0)

    # Cross product: direction x up
    tx = dy * up[2] - dz * up[1]
    ty = dz * up[0] - dx * up[2]
    tz = dx * up[1] - dy * up[0]
    t_len = math.sqrt(tx * tx + ty * ty + tz * tz)
    if t_len > 1e-9:
        tx /= t_len
        ty /= t_len
        tz /= t_len
    else:
        tx, ty, tz = 1.0, 0.0, 0.0

    half_w = card_width * 0.5

    for seg in range(segments + 1):
        t = seg / segments
        # Position along the card
        px = root_pos[0] + dx * length * t
        py = root_pos[1] + dy * length * t
        pz = root_pos[2] + dz * length * t

        # Slight taper: cards get narrower at the tip
        taper = 1.0 - t * 0.4
        hw = half_w * taper

        # Two vertices per row (left and right edges)
        verts.append((px - tx * hw, py - ty * hw, pz - tz * hw))
        verts.append((px + tx * hw, py + ty * hw, pz + tz * hw))

        # UVs: U = 0/1 for left/right, V = t (root=0, tip=1)
        uvs.append((0.0, t))
        uvs.append((1.0, t))

    # Build quad faces
    for seg in range(segments):
        base = vert_offset + seg * 2
        # Quad: bottom-left, bottom-right, top-right, top-left
        faces.append((base, base + 1, base + 3, base + 2))

    return verts, faces, uvs


def _head_surface_point(
    azimuth: float,
    elevation: float,
    head_center: Vec3,
    head_radius: float,
) -> Vec3:
    """Compute a point on a spherical head surface.

    azimuth: angle around the head (0 = front, pi = back)
    elevation: angle from top (0 = top, pi/2 = equator, pi = bottom)
    """
    x = head_center[0] + head_radius * math.sin(elevation) * math.sin(azimuth)
    y = head_center[1] + head_radius * math.sin(elevation) * math.cos(azimuth)
    z = head_center[2] + head_radius * math.cos(elevation)
    return (x, y, z)


def _outward_direction(
    azimuth: float,
    elevation: float,
    gravity_influence: float = 0.3,
) -> Vec3:
    """Compute hair growth direction from a head surface point.

    Hair grows outward from the scalp with some downward gravity influence.
    """
    # Outward normal on sphere
    nx = math.sin(elevation) * math.sin(azimuth)
    ny = math.sin(elevation) * math.cos(azimuth)
    nz = math.cos(elevation)

    # Add gravity (downward pull)
    nz -= gravity_influence

    # Normalize
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length > 1e-9:
        nx /= length
        ny /= length
        nz /= length

    return (nx, ny, nz)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_hair_mesh(
    style: str = "medium_swept",
    head_radius: float = 0.11,
    head_center: tuple[float, float, float] = (0.0, 0.0, 1.7),
    card_width: float = 0.015,
    segments_per_card: int = 3,
) -> MeshSpec:
    """Generate hair card strips arranged around the head.

    Returns mesh with alpha-ready UVs for hair texture. Each hair card
    is a strip of quads with UV mapping from root (V=0) to tip (V=1).

    Args:
        style: Hair style name from HAIR_STYLES dict.
        head_radius: Radius of the character's head sphere.
        head_center: (x, y, z) center of the head.
        card_width: Width of each hair card strip.
        segments_per_card: Number of quad segments per card.

    Returns:
        MeshSpec dict with vertices, faces, uvs, and metadata.

    Raises:
        ValueError: If style is not recognized.
    """
    if style not in HAIR_STYLES:
        raise ValueError(
            f"Unknown hair style: {style!r}. "
            f"Valid styles: {sorted(HAIR_STYLES.keys())}"
        )

    style_def = HAIR_STYLES[style]
    card_count = style_def.get("card_count", 0)

    # Bald style returns empty mesh
    if card_count == 0:
        return _make_result(
            name=f"hair_{style}",
            vertices=[],
            faces=[],
            uvs=[],
            style=style,
            card_count=0,
            coverage="none",
        )

    hair_length = style_def["length"]
    coverage = style_def.get("coverage", "full")

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[Vec2] = []

    # Distribute cards around head
    angles = _distribute_angles(card_count, coverage)

    # Elevation range for scalp (upper hemisphere of head)
    # Cards are placed between 15 and 75 degrees from top
    elev_min = 0.25  # ~15 degrees
    elev_max = 1.3   # ~75 degrees

    for i, azimuth in enumerate(angles):
        # Vary elevation per card using golden ratio distribution
        t = (i * 0.618033988749895) % 1.0
        elevation = elev_min + t * (elev_max - elev_min)

        # For specific coverages, adjust elevation
        if coverage == "center_strip":
            # Mohawk: narrow elevation band at top
            elevation = elev_min + t * 0.3
        elif coverage == "gathered_top":
            # Updo: concentrate at top
            elevation = elev_min + t * 0.4
        elif coverage == "back_gathered":
            # Ponytail: slightly below equator
            elevation = 0.8 + t * 0.4

        root = _head_surface_point(azimuth, elevation, head_center, head_radius)
        direction = _outward_direction(azimuth, elevation,
                                        gravity_influence=0.3 if hair_length > 0.1 else 0.1)

        # Slightly offset root outward so cards don't intersect head
        offset_dist = 0.002
        root = (
            root[0] + direction[0] * offset_dist,
            root[1] + direction[1] * offset_dist,
            root[2] + direction[2] * offset_dist,
        )

        card_verts, card_faces, card_uvs = _generate_hair_card(
            root_pos=root,
            direction=direction,
            length=hair_length,
            card_width=card_width,
            vert_offset=len(all_verts),
            segments=segments_per_card,
        )

        all_verts.extend(card_verts)
        all_faces.extend(card_faces)
        all_uvs.extend(card_uvs)

    return _make_result(
        name=f"hair_{style}",
        vertices=all_verts,
        faces=all_faces,
        uvs=all_uvs,
        style=style,
        card_count=len(angles),
        coverage=coverage,
        hair_length=hair_length,
    )


def get_helmet_compatible_hair(
    style: str,
    helmet_style: str,
) -> dict[str, Any]:
    """Return hair modification rules for helmet compatibility.

    Different helmet types hide different parts of the hair:
    - full_helm: hide all hair
    - open_face: show hair at back/sides only
    - hood: show front fringe only
    - crown: show all hair
    - skull_mask: show all hair (only covers face)

    Args:
        style: Hair style name from HAIR_STYLES.
        helmet_style: One of full_helm, open_face, hood, crown, skull_mask.

    Returns:
        Dict with:
            visible: bool - whether any hair is visible
            modified_coverage: str | None - new coverage if partially visible
            hide_regions: list[str] - which hair regions to hide
            original_style: str - the input style

    Raises:
        ValueError: If style or helmet_style is unknown.
    """
    if style not in HAIR_STYLES:
        raise ValueError(
            f"Unknown hair style: {style!r}. "
            f"Valid styles: {sorted(HAIR_STYLES.keys())}"
        )

    valid_helmets = {"full_helm", "open_face", "hood", "crown", "skull_mask"}
    if helmet_style not in valid_helmets:
        raise ValueError(
            f"Unknown helmet style: {helmet_style!r}. "
            f"Valid: {sorted(valid_helmets)}"
        )

    style_def = HAIR_STYLES[style]

    # Bald is always compatible
    if style_def.get("card_count", 0) == 0:
        return {
            "visible": False,
            "modified_coverage": None,
            "hide_regions": [],
            "original_style": style,
        }

    coverage = style_def.get("coverage", "full")

    if helmet_style == "full_helm":
        # Full helms hide ALL hair
        return {
            "visible": False,
            "modified_coverage": None,
            "hide_regions": ["all"],
            "original_style": style,
        }

    elif helmet_style == "open_face":
        # Open face: show hair at back and sides, hide top
        return {
            "visible": True,
            "modified_coverage": "back_and_sides",
            "hide_regions": ["top", "front"],
            "original_style": style,
        }

    elif helmet_style == "hood":
        # Hoods: show front fringe only
        return {
            "visible": True,
            "modified_coverage": "front_fringe",
            "hide_regions": ["back", "sides", "top"],
            "original_style": style,
        }

    elif helmet_style == "crown":
        # Crowns: show all hair unchanged
        return {
            "visible": True,
            "modified_coverage": coverage,
            "hide_regions": [],
            "original_style": style,
        }

    elif helmet_style == "skull_mask":
        # Skull mask covers face only, all hair visible
        return {
            "visible": True,
            "modified_coverage": coverage,
            "hide_regions": [],
            "original_style": style,
        }

    # Fallback
    return {
        "visible": True,
        "modified_coverage": coverage,
        "hide_regions": [],
        "original_style": style,
    }


def generate_facial_hair_mesh(
    style: str = "full_beard",
    face_center: tuple[float, float, float] = (0.0, 0.0, 1.64),
    face_radius: float = 0.10,
    card_width: float = 0.008,
    segments_per_card: int = 2,
) -> MeshSpec:
    """Generate facial hair cards positioned on the face.

    Cards are placed on the face surface according to the facial hair
    style's coverage regions. Each card grows outward from the face
    with proper UV mapping.

    Args:
        style: Facial hair style from FACIAL_HAIR_STYLES.
        face_center: (x, y, z) center of the face sphere.
        face_radius: Radius of the face sphere.
        card_width: Width of each facial hair card.
        segments_per_card: Quad segments per card.

    Returns:
        MeshSpec dict with vertices, faces, uvs, and metadata.

    Raises:
        ValueError: If style is not recognized.
    """
    if style not in FACIAL_HAIR_STYLES:
        raise ValueError(
            f"Unknown facial hair style: {style!r}. "
            f"Valid styles: {sorted(FACIAL_HAIR_STYLES.keys())}"
        )

    style_def = FACIAL_HAIR_STYLES[style]
    card_count = style_def.get("card_count", 0)

    # Clean shaven returns empty mesh
    if card_count == 0:
        return _make_result(
            name=f"facial_hair_{style}",
            vertices=[],
            faces=[],
            uvs=[],
            style=style,
            card_count=0,
            coverage="none",
        )

    hair_length = style_def["length"]
    coverage = style_def.get("coverage", "jaw_chin")
    is_braided = style_def.get("braids", False)

    # Get coverage regions
    regions = _FACIAL_COVERAGE_REGIONS.get(coverage, _FACIAL_COVERAGE_REGIONS["jaw_chin"])

    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[Vec2] = []

    # Distribute cards across regions
    total_region_area = sum(
        (r[1] - r[0]) * (r[3] - r[2]) for r in regions
    )

    cards_placed = 0
    for elev_min, elev_max, azim_min, azim_max in regions:
        region_area = (elev_max - elev_min) * (azim_max - azim_min)
        n = max(1, round(card_count * region_area / total_region_area))
        if cards_placed + n > card_count:
            n = card_count - cards_placed
        if n <= 0:
            continue

        for i in range(n):
            # Distribute within region using golden ratio
            t_elev = ((i * 0.618033988749895) % 1.0)
            t_azim = ((i * 0.381966011250105 + 0.1) % 1.0)

            elevation = elev_min + t_elev * (elev_max - elev_min)
            azimuth = azim_min + t_azim * (azim_max - azim_min)

            # Face surface point (front-facing sphere)
            x = face_center[0] + face_radius * math.sin(elevation) * math.sin(azimuth)
            y = face_center[1] + face_radius * math.sin(elevation) * math.cos(azimuth)
            z = face_center[2] + face_radius * math.cos(elevation)
            root = (x, y, z)

            # Outward direction with downward gravity
            nx = math.sin(elevation) * math.sin(azimuth)
            ny = math.sin(elevation) * math.cos(azimuth)
            nz = math.cos(elevation)

            # Strong downward pull for beards
            gravity = 0.5 if hair_length > 0.03 else 0.2
            nz -= gravity

            d_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if d_len > 1e-9:
                nx /= d_len
                ny /= d_len
                nz /= d_len

            # For braided beards, direct cards more downward
            if is_braided:
                nz = min(nz, -0.3)
                d_len = math.sqrt(nx * nx + ny * ny + nz * nz)
                if d_len > 1e-9:
                    nx /= d_len
                    ny /= d_len
                    nz /= d_len

            direction = (nx, ny, nz)

            # Offset root slightly outward from face
            offset = 0.001
            root = (
                root[0] + direction[0] * offset,
                root[1] + direction[1] * offset,
                root[2] + direction[2] * offset,
            )

            card_verts, card_faces, card_uvs = _generate_hair_card(
                root_pos=root,
                direction=direction,
                length=hair_length,
                card_width=card_width,
                vert_offset=len(all_verts),
                segments=segments_per_card,
            )

            all_verts.extend(card_verts)
            all_faces.extend(card_faces)
            all_uvs.extend(card_uvs)

            cards_placed += 1

    return _make_result(
        name=f"facial_hair_{style}",
        vertices=all_verts,
        faces=all_faces,
        uvs=all_uvs,
        style=style,
        card_count=cards_placed,
        coverage=coverage,
        hair_length=hair_length,
        braided=is_braided,
    )
