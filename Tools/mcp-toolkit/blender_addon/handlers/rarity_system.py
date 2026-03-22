"""Rarity visual differentiation system for VeilBreakers equipment.

Defines five rarity tiers (common -> legendary) with visual property
modifiers that scale mesh detail, add gem sockets, emission glow,
particle effect hints, and material tier associations.

Provides:
- RARITY_TIERS: 5-tier visual property dict
- VALID_RARITIES: frozenset of valid rarity names
- BRAND_EMISSION_COLORS: per-brand emission RGB for rare+ gear
- apply_rarity_to_mesh(mesh_data, rarity, brand): modify mesh metadata with rarity visuals
- compute_gem_socket_positions(vertices, faces, count): find optimal gem socket positions
- get_rarity_material_tier(rarity): map rarity to default metal tier name
- validate_rarity(rarity): raise ValueError on unknown rarity

All pure logic -- no bpy imports -- testable standalone.
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Brand emission colors (RGB 0-1) -- used when emission_color == "brand"
# ---------------------------------------------------------------------------

BRAND_EMISSION_COLORS: dict[str, tuple[float, float, float]] = {
    "IRON": (0.8, 0.5, 0.2),       # warm orange-amber
    "SAVAGE": (0.9, 0.2, 0.1),     # blood red
    "SURGE": (0.3, 0.6, 1.0),      # electric blue
    "VENOM": (0.3, 0.9, 0.1),      # toxic green
    "DREAD": (0.5, 0.1, 0.6),      # dark purple
    "LEECH": (0.6, 0.0, 0.3),      # crimson-magenta
    "GRACE": (1.0, 0.9, 0.5),      # golden white
    "MEND": (0.2, 0.8, 0.5),       # healing teal
    "RUIN": (0.9, 0.4, 0.0),       # destruction orange
    "VOID": (0.2, 0.0, 0.4),       # deep void purple
}

VALID_BRANDS = frozenset(BRAND_EMISSION_COLORS.keys())


# ---------------------------------------------------------------------------
# Rarity tiers
# ---------------------------------------------------------------------------

RARITY_TIERS: dict[str, dict[str, Any]] = {
    "common": {
        "detail_multiplier": 1.0,
        "trim_detail": False,
        "gem_sockets": 0,
        "emission": 0.0,
        "particle_effect": None,
        "material_tier": "iron",
        "color_saturation_boost": 0.0,
    },
    "uncommon": {
        "detail_multiplier": 1.2,
        "trim_detail": True,
        "gem_sockets": 0,
        "emission": 0.0,
        "particle_effect": None,
        "material_tier": "steel",
        "color_saturation_boost": 0.05,
    },
    "rare": {
        "detail_multiplier": 1.5,
        "trim_detail": True,
        "gem_sockets": 1,
        "emission": 0.1,
        "emission_color": "brand",
        "particle_effect": "subtle_glow",
        "material_tier": "silver",
        "color_saturation_boost": 0.1,
    },
    "epic": {
        "detail_multiplier": 2.0,
        "trim_detail": True,
        "gem_sockets": 2,
        "emission": 0.3,
        "emission_color": "brand",
        "particle_effect": "rune_orbit",
        "material_tier": "mithril",
        "color_saturation_boost": 0.15,
    },
    "legendary": {
        "detail_multiplier": 3.0,
        "trim_detail": True,
        "gem_sockets": 3,
        "emission": 0.5,
        "emission_color": "brand",
        "particle_effect": "aura_glow",
        "material_tier": "void_touched",
        "color_saturation_boost": 0.2,
        "unique_silhouette": True,
    },
}

VALID_RARITIES = frozenset(RARITY_TIERS.keys())

# Ordered from lowest to highest for comparisons
RARITY_ORDER: list[str] = ["common", "uncommon", "rare", "epic", "legendary"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_rarity(rarity: str) -> str:
    """Validate and normalise a rarity string.

    Returns lowercase rarity name.
    Raises ValueError if unknown.
    """
    rarity = rarity.lower().strip()
    if rarity not in VALID_RARITIES:
        raise ValueError(
            f"Unknown rarity: {rarity!r}. "
            f"Valid: {sorted(VALID_RARITIES)}"
        )
    return rarity


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_rarity_material_tier(rarity: str) -> str:
    """Return the default metal material tier name for a rarity level.

    Args:
        rarity: One of 'common', 'uncommon', 'rare', 'epic', 'legendary'.

    Returns:
        Material tier name string (e.g. 'iron', 'steel', 'silver', ...).
    """
    rarity = validate_rarity(rarity)
    return RARITY_TIERS[rarity]["material_tier"]


def _resolve_emission_color(
    tier_data: dict[str, Any],
    brand: str | None,
) -> tuple[float, float, float] | None:
    """Resolve the emission color for a rarity tier.

    If tier has no emission or emission == 0, returns None.
    If emission_color == "brand" and a brand is given, returns brand color.
    Falls back to a neutral white glow.
    """
    emission = tier_data.get("emission", 0.0)
    if emission <= 0.0:
        return None

    color_spec = tier_data.get("emission_color")
    if color_spec == "brand" and brand:
        brand_upper = brand.upper().strip()
        if brand_upper in BRAND_EMISSION_COLORS:
            return BRAND_EMISSION_COLORS[brand_upper]

    # Neutral white-silver fallback for non-branded emission
    if color_spec == "brand" and not brand:
        return (0.8, 0.8, 0.9)

    return (0.8, 0.8, 0.9)


def apply_rarity_to_mesh(
    mesh_data: dict[str, Any],
    rarity: str,
    brand: str | None = None,
) -> dict[str, Any]:
    """Apply rarity visual modifications to mesh metadata.

    Does NOT mutate the input dict. Returns a new dict with rarity
    properties merged into the metadata.

    Args:
        mesh_data: Mesh spec dict with at least 'metadata' key.
        rarity: Rarity tier string.
        brand: Optional VeilBreakers brand name for emission color.

    Returns:
        New dict with rarity visual properties added to metadata:
        - rarity, detail_multiplier, trim_detail, gem_sockets,
          emission, emission_color (resolved RGB), particle_effect,
          material_tier, color_saturation_boost, unique_silhouette,
          gem_positions (if gem_sockets > 0 and vertices available).
    """
    rarity = validate_rarity(rarity)
    tier = RARITY_TIERS[rarity]

    # Deep-ish copy: new top-level dict, new metadata dict
    result = dict(mesh_data)
    old_meta = mesh_data.get("metadata", {})
    new_meta = dict(old_meta)

    # Inject rarity properties
    new_meta["rarity"] = rarity
    new_meta["detail_multiplier"] = tier["detail_multiplier"]
    new_meta["trim_detail"] = tier["trim_detail"]
    new_meta["gem_sockets"] = tier["gem_sockets"]
    new_meta["emission"] = tier["emission"]
    new_meta["particle_effect"] = tier["particle_effect"]
    new_meta["material_tier"] = tier["material_tier"]
    new_meta["color_saturation_boost"] = tier["color_saturation_boost"]
    new_meta["unique_silhouette"] = tier.get("unique_silhouette", False)

    # Resolve emission color
    resolved_color = _resolve_emission_color(tier, brand)
    if resolved_color is not None:
        new_meta["emission_color"] = resolved_color

    # Compute gem socket positions if applicable
    gem_count = tier["gem_sockets"]
    if gem_count > 0:
        vertices = mesh_data.get("vertices", [])
        faces = mesh_data.get("faces", [])
        if vertices and faces:
            positions = compute_gem_socket_positions(vertices, faces, gem_count)
            new_meta["gem_positions"] = positions

    result["metadata"] = new_meta
    return result


def compute_gem_socket_positions(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    count: int,
) -> list[tuple[float, float, float]]:
    """Find optimal positions for gem sockets on a weapon/armor mesh.

    Strategy:
    1. Compute face centroids and areas.
    2. Sort faces by area (largest first) -- gems go on prominent surfaces.
    3. Filter to faces in the upper 60% of the mesh height (gems near blade/head).
    4. Select evenly-spaced faces from filtered set.
    5. Return face centroid positions.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples.
        count: Number of gem socket positions to find.

    Returns:
        List of (x, y, z) positions for gem sockets.
    """
    if count <= 0:
        return []
    if not vertices or not faces:
        return [(0.0, 0.0, 0.0)] * count

    n_verts = len(vertices)

    # Compute bounding box for height filtering
    ys = [v[1] for v in vertices]
    min_y, max_y = min(ys), max(ys)
    height_range = max_y - min_y
    if height_range < 1e-9:
        height_range = 1.0

    # Height threshold: prefer upper 60% of mesh
    height_threshold = min_y + height_range * 0.4

    # Compute face centroids and approximate areas
    face_data: list[tuple[float, float, float, float]] = []  # (cx, cy, cz, area)
    for face in faces:
        # Skip degenerate faces or faces with invalid indices
        valid = all(0 <= idx < n_verts for idx in face)
        if not valid or len(face) < 3:
            continue

        # Centroid
        cx = sum(vertices[idx][0] for idx in face) / len(face)
        cy = sum(vertices[idx][1] for idx in face) / len(face)
        cz = sum(vertices[idx][2] for idx in face) / len(face)

        # Approximate area using first triangle of face
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]
        # Cross product of two edges
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        cross = (
            e1[1] * e2[2] - e1[2] * e2[1],
            e1[2] * e2[0] - e1[0] * e2[2],
            e1[0] * e2[1] - e1[1] * e2[0],
        )
        area = 0.5 * math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)

        face_data.append((cx, cy, cz, area))

    if not face_data:
        return [(0.0, 0.0, 0.0)] * count

    # Filter to upper region faces
    upper_faces = [f for f in face_data if f[1] >= height_threshold]
    if len(upper_faces) < count:
        # Fall back to all faces if not enough in upper region
        upper_faces = face_data

    # Sort by area descending (largest faces are best for gem placement)
    upper_faces.sort(key=lambda f: f[3], reverse=True)

    # Select evenly-spaced faces from the sorted list
    positions: list[tuple[float, float, float]] = []
    step = max(1, len(upper_faces) // max(count, 1))
    for i in range(count):
        idx = min(i * step, len(upper_faces) - 1)
        f = upper_faces[idx]
        positions.append((f[0], f[1], f[2]))

    return positions


def get_rarity_tier(rarity: str) -> dict[str, Any]:
    """Return a copy of the rarity tier properties.

    Args:
        rarity: One of 'common', 'uncommon', 'rare', 'epic', 'legendary'.

    Returns:
        Dict of rarity visual properties.
    """
    rarity = validate_rarity(rarity)
    return dict(RARITY_TIERS[rarity])
