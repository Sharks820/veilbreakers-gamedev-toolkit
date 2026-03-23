"""Equipment-body integration for VeilBreakers characters.

Pure-logic module (NO bpy imports). Provides:
- compute_equipment_body_changes: Determine which body parts to hide/shrink
  based on equipped items
- apply_body_shrink: Shrink body mesh vertices inward under armor to
  prevent clipping
- get_body_region_vertices: Map vertex indices to body regions

Equipment visibility rules control what parts of the character's body
mesh and hair are shown or hidden when armor pieces are equipped.
Body shrink moves body vertices inward along their normals so that
the body doesn't poke through armor meshes.

All functions are pure Python -- no bpy/bmesh imports.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]

# ---------------------------------------------------------------------------
# Equipment visibility rules
# ---------------------------------------------------------------------------

BODY_PART_VISIBILITY: dict[str, dict[str, dict[str, Any]]] = {
    "helmet": {
        "full_helm": {"hide": ["head_hair", "facial_hair", "ears"]},
        "open_face": {"hide": ["head_hair_top"]},
        "hood": {"hide": ["head_hair_back", "head_hair_sides"]},
        "crown": {"hide": []},
        "skull_mask": {"hide": ["facial_hair"]},
    },
    "chest_armor": {
        "plate": {"hide": ["torso_skin"], "shrink_body": 0.02},
        "chain": {"hide": ["torso_skin"], "shrink_body": 0.01},
        "leather": {"hide": ["torso_skin"], "shrink_body": 0.005},
        "robes": {"hide": ["torso_skin", "upper_legs_skin"], "shrink_body": 0.0},
        "light": {"hide": [], "shrink_body": 0.0},
    },
    "gauntlet": {
        "plate": {"hide": ["hand_skin", "forearm_skin"]},
        "leather": {"hide": ["hand_skin"]},
        "wraps": {"hide": []},
    },
    "boot": {
        "plate": {"hide": ["foot_skin", "shin_skin"]},
        "leather": {"hide": ["foot_skin"]},
        "sandals": {"hide": []},
    },
    "pauldron": {
        "plate": {"hide": ["shoulder_skin"], "shrink_body": 0.015},
        "fur": {"hide": [], "shrink_body": 0.005},
        "bone": {"hide": [], "shrink_body": 0.005},
    },
    "leg_armor": {
        "plate": {"hide": ["upper_legs_skin", "knee_skin"], "shrink_body": 0.015},
        "chain": {"hide": ["upper_legs_skin"], "shrink_body": 0.008},
        "leather": {"hide": ["upper_legs_skin"], "shrink_body": 0.003},
        "cloth": {"hide": [], "shrink_body": 0.0},
    },
    "bracer": {
        "leather": {"hide": []},
        "metal_vambrace": {"hide": ["forearm_skin"], "shrink_body": 0.005},
        "enchanted": {"hide": []},
        "chain": {"hide": [], "shrink_body": 0.003},
        "bone": {"hide": [], "shrink_body": 0.003},
    },
}

# Mapping from hide region names to body region names for shrink
_HIDE_TO_SHRINK_REGION: dict[str, str] = {
    "torso_skin": "torso",
    "upper_legs_skin": "upper_legs",
    "hand_skin": "hands",
    "forearm_skin": "forearms",
    "foot_skin": "feet",
    "shin_skin": "shins",
    "shoulder_skin": "shoulders",
    "knee_skin": "knees",
}

# Hair-related hide regions
_HAIR_REGIONS = frozenset({
    "head_hair", "head_hair_top", "head_hair_back", "head_hair_sides",
})
_FACIAL_HAIR_REGIONS = frozenset({
    "facial_hair",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_equipment_body_changes(equipped_items: dict[str, str]) -> dict[str, Any]:
    """Given equipped items, compute which body parts to hide and how much to shrink.

    Args:
        equipped_items: Dict mapping slot name to equipment style.
            Example: {"helmet": "full_helm", "chest_armor": "plate", "boot": "leather"}

    Returns:
        Dict with:
            hide_regions: list[str] - body regions to hide
            shrink_regions: dict[str, float] - region -> shrink amount (meters)
            hair_visible: bool - whether head hair should be shown
            facial_hair_visible: bool - whether facial hair should be shown

    Raises:
        ValueError: If a slot or style is not recognized.
    """
    if not isinstance(equipped_items, dict):
        raise TypeError(
            f"equipped_items must be a dict, got {type(equipped_items).__name__}"
        )

    hide_regions: list[str] = []
    shrink_regions: dict[str, float] = {}
    hair_visible = True
    facial_hair_visible = True

    for slot, style in equipped_items.items():
        if slot not in BODY_PART_VISIBILITY:
            raise ValueError(
                f"Unknown equipment slot: {slot!r}. "
                f"Valid slots: {sorted(BODY_PART_VISIBILITY.keys())}"
            )

        slot_styles = BODY_PART_VISIBILITY[slot]
        if style not in slot_styles:
            raise ValueError(
                f"Unknown style {style!r} for slot {slot!r}. "
                f"Valid styles: {sorted(slot_styles.keys())}"
            )

        rules = slot_styles[style]
        regions_to_hide = rules.get("hide", [])
        shrink_amount = rules.get("shrink_body", 0.0)

        for region in regions_to_hide:
            if region not in hide_regions:
                hide_regions.append(region)

            # Check if this affects hair visibility
            if region in _HAIR_REGIONS or region == "head_hair":
                hair_visible = False
            if region in _FACIAL_HAIR_REGIONS:
                facial_hair_visible = False

            # Map hide region to shrink region
            if region in _HIDE_TO_SHRINK_REGION:
                shrink_name = _HIDE_TO_SHRINK_REGION[region]
                # Use the maximum shrink amount if multiple items affect same region
                if shrink_amount > 0:
                    shrink_regions[shrink_name] = max(
                        shrink_regions.get(shrink_name, 0.0),
                        shrink_amount,
                    )

        # Some items apply shrink without hiding (e.g., fur pauldrons)
        if shrink_amount > 0 and not regions_to_hide:
            # Apply shrink to the slot's default region
            default_shrink_region = _slot_to_default_shrink_region(slot)
            if default_shrink_region:
                shrink_regions[default_shrink_region] = max(
                    shrink_regions.get(default_shrink_region, 0.0),
                    shrink_amount,
                )

    return {
        "hide_regions": hide_regions,
        "shrink_regions": shrink_regions,
        "hair_visible": hair_visible,
        "facial_hair_visible": facial_hair_visible,
    }


def _slot_to_default_shrink_region(slot: str) -> str | None:
    """Map an equipment slot to its default body shrink region."""
    mapping = {
        "helmet": "head",
        "chest_armor": "torso",
        "gauntlet": "hands",
        "boot": "feet",
        "pauldron": "shoulders",
        "leg_armor": "upper_legs",
        "bracer": "forearms",
    }
    return mapping.get(slot)


def apply_body_shrink(
    body_vertices: list[Vec3],
    body_normals: list[Vec3],
    region_assignments: dict[str, list[int]],
    shrink_map: dict[str, float],
) -> list[Vec3]:
    """Slightly shrink body mesh under armor to prevent clipping.

    Each region's vertices are moved inward (opposite to their normal)
    by the specified shrink amount.

    Args:
        body_vertices: List of (x, y, z) vertex positions.
        body_normals: List of (nx, ny, nz) per-vertex normals.
        region_assignments: Dict mapping region name to list of vertex indices.
            Example: {"torso": [0, 1, 2, ...], "hands": [100, 101, ...]}
        shrink_map: Dict mapping region name to shrink distance (meters).
            Example: {"torso": 0.02, "hands": 0.005}

    Returns:
        New list of vertices with shrink applied. Unaffected vertices
        are returned unchanged.

    Raises:
        ValueError: If vertices and normals have different lengths.
        ValueError: If any vertex index in region_assignments is out of range.
    """
    if len(body_vertices) != len(body_normals):
        raise ValueError(
            f"body_vertices length ({len(body_vertices)}) != "
            f"body_normals length ({len(body_normals)})"
        )

    n_verts = len(body_vertices)

    # Validate region vertex indices
    for region_name, indices in region_assignments.items():
        for idx in indices:
            if idx < 0 or idx >= n_verts:
                raise ValueError(
                    f"Vertex index {idx} in region {region_name!r} "
                    f"out of range [0, {n_verts})"
                )

    # Start with a copy of all vertices
    result = list(body_vertices)

    # Apply shrink per region
    for region_name, shrink_dist in shrink_map.items():
        if shrink_dist <= 0:
            continue

        indices = region_assignments.get(region_name)
        if not indices:
            continue

        for idx in indices:
            vx, vy, vz = result[idx]
            nx, ny, nz = body_normals[idx]

            # Normalize the normal
            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len > 1e-9:
                nx /= n_len
                ny /= n_len
                nz /= n_len
            else:
                continue  # Skip zero-normal vertices

            # Move vertex inward (opposite normal direction)
            result[idx] = (
                vx - nx * shrink_dist,
                vy - ny * shrink_dist,
                vz - nz * shrink_dist,
            )

    return result


def get_body_region_vertices(
    vertices: list[Vec3],
    body_center: Vec3 = (0.0, 0.0, 0.0),
    body_height: float = 1.8,
) -> dict[str, list[int]]:
    """Assign vertices to body regions based on their position.

    Uses height-based segmentation of a humanoid body to classify
    each vertex into a body region. This is a heuristic for when
    explicit vertex group data is not available.

    Args:
        vertices: List of (x, y, z) vertex positions.
        body_center: (x, y, z) base center of the body (feet position).
        body_height: Total height of the body in meters.

    Returns:
        Dict mapping region name to list of vertex indices.
    """
    regions: dict[str, list[int]] = {
        "head": [],
        "torso": [],
        "shoulders": [],
        "upper_legs": [],
        "knees": [],
        "shins": [],
        "feet": [],
        "hands": [],
        "forearms": [],
    }

    base_z = body_center[2]
    cx, cy = body_center[0], body_center[1]

    # Height thresholds as fractions of body height
    foot_top = base_z + body_height * 0.05
    shin_top = base_z + body_height * 0.25
    knee_top = base_z + body_height * 0.30
    upper_leg_top = base_z + body_height * 0.47
    torso_top = base_z + body_height * 0.80
    shoulder_top = base_z + body_height * 0.85
    head_bottom = base_z + body_height * 0.85

    # Width threshold for arms vs torso
    arm_threshold = body_height * 0.18

    for i, (vx, vy, vz) in enumerate(vertices):
        height = vz
        lateral_dist = math.sqrt((vx - cx) ** 2 + (vy - cy) ** 2)

        if height >= head_bottom:
            regions["head"].append(i)
        elif height >= shoulder_top:
            if lateral_dist > arm_threshold:
                regions["shoulders"].append(i)
            else:
                regions["torso"].append(i)
        elif height >= upper_leg_top:
            if lateral_dist > arm_threshold:
                # Check if it's forearm/hand height
                if height < torso_top * 0.7:
                    regions["hands"].append(i)
                else:
                    regions["forearms"].append(i)
            else:
                regions["torso"].append(i)
        elif height >= knee_top:
            regions["upper_legs"].append(i)
        elif height >= shin_top:
            regions["knees"].append(i)
        elif height >= foot_top:
            regions["shins"].append(i)
        else:
            regions["feet"].append(i)

    return regions


def compute_vertex_normals(
    vertices: list[Vec3],
    faces: list[tuple[int, ...]],
) -> list[Vec3]:
    """Compute per-vertex normals from face data by averaging face normals.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face tuples (vertex indices).

    Returns:
        List of (nx, ny, nz) normalized per-vertex normals.
    """
    normals = [(0.0, 0.0, 0.0)] * len(vertices)
    accum = [[0.0, 0.0, 0.0] for _ in range(len(vertices))]

    for face in faces:
        if len(face) < 3:
            continue

        # Compute face normal from first triangle
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]

        # Edge vectors
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        # Cross product
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]

        # Accumulate for each vertex in the face
        for idx in face:
            if 0 <= idx < len(vertices):
                accum[idx][0] += nx
                accum[idx][1] += ny
                accum[idx][2] += nz

    # Normalize
    result: list[Vec3] = []
    for a in accum:
        length = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
        if length > 1e-9:
            result.append((a[0] / length, a[1] / length, a[2] / length))
        else:
            result.append((0.0, 0.0, 1.0))  # Default up normal

    return result
