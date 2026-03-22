"""Loot drop ground display system for VeilBreakers.

Generates loot bag/chest meshes, rarity beams, and ground placement data
for dropped items. All functions are pure Python/math -- no ``bpy``
dependency -- for testability.

Rarity tiers:
  - common: small bag, no glow, no beam
  - uncommon: medium bag, green glow, short beam
  - rare: large bag, blue glow, medium beam
  - epic: chest, purple glow, tall beam
  - legendary: ornate chest, gold glow, very tall beam

Provides:
  - LOOT_DISPLAY: rarity display definitions
  - RARITY_ORDER: ordered rarity list
  - generate_loot_bag_mesh(): create bag/chest mesh for rarity
  - generate_loot_beam_mesh(): create vertical light beam mesh
  - compute_item_ground_placement(): ground placement parameters
  - get_loot_display(): retrieve display data for a rarity
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Mesh result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# Loot display definitions by rarity
# ---------------------------------------------------------------------------

LOOT_DISPLAY: dict[str, dict[str, Any]] = {
    "common": {
        "glow_color": None,
        "beam_height": 0,
        "ground_mesh": "loot_bag_small",
        "pickup_radius": 1.0,
        "despawn_time": 60.0,
        "bob_amplitude": 0.0,
    },
    "uncommon": {
        "glow_color": (0.2, 0.8, 0.2),
        "beam_height": 1.0,
        "ground_mesh": "loot_bag_medium",
        "pickup_radius": 1.5,
        "despawn_time": 120.0,
        "bob_amplitude": 0.02,
    },
    "rare": {
        "glow_color": (0.2, 0.4, 1.0),
        "beam_height": 2.0,
        "ground_mesh": "loot_bag_large",
        "pickup_radius": 2.0,
        "despawn_time": 180.0,
        "bob_amplitude": 0.03,
    },
    "epic": {
        "glow_color": (0.7, 0.3, 1.0),
        "beam_height": 3.0,
        "ground_mesh": "loot_chest",
        "pickup_radius": 2.5,
        "despawn_time": 300.0,
        "bob_amplitude": 0.04,
    },
    "legendary": {
        "glow_color": (1.0, 0.8, 0.2),
        "beam_height": 5.0,
        "ground_mesh": "loot_chest_ornate",
        "pickup_radius": 3.0,
        "despawn_time": 600.0,
        "bob_amplitude": 0.06,
    },
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _compute_dimensions(
    verts: list[tuple[float, float, float]],
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
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
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


def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
    offset: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Create a box centered at (cx, cy+sy, cz) with half-extents (sx, sy, sz)."""
    hx, hy, hz = sx, sy, sz
    verts = [
        (cx - hx, cy, cz - hz),
        (cx + hx, cy, cz - hz),
        (cx + hx, cy + 2 * hy, cz - hz),
        (cx - hx, cy + 2 * hy, cz - hz),
        (cx - hx, cy, cz + hz),
        (cx + hx, cy, cz + hz),
        (cx + hx, cy + 2 * hy, cz + hz),
        (cx - hx, cy + 2 * hy, cz + hz),
    ]
    faces = [
        (offset + 0, offset + 3, offset + 2, offset + 1),
        (offset + 4, offset + 5, offset + 6, offset + 7),
        (offset + 0, offset + 1, offset + 5, offset + 4),
        (offset + 2, offset + 3, offset + 7, offset + 6),
        (offset + 0, offset + 4, offset + 7, offset + 3),
        (offset + 1, offset + 2, offset + 6, offset + 5),
    ]
    return verts, faces


# ---------------------------------------------------------------------------
# Lookup function
# ---------------------------------------------------------------------------

def get_loot_display(rarity: str) -> dict[str, Any]:
    """Retrieve loot display data for a rarity tier.

    Args:
        rarity: Rarity name (common/uncommon/rare/epic/legendary).

    Returns:
        Copy of loot display dict.

    Raises:
        ValueError: If rarity is unknown.
    """
    rarity_lower = rarity.lower()
    if rarity_lower not in LOOT_DISPLAY:
        raise ValueError(
            f"Unknown rarity '{rarity}'. "
            f"Valid rarities: {RARITY_ORDER}"
        )
    return dict(LOOT_DISPLAY[rarity_lower])


# ---------------------------------------------------------------------------
# Mesh generators
# ---------------------------------------------------------------------------

def generate_loot_bag_mesh(rarity: str = "common") -> MeshSpec:
    """Generate a loot bag or chest mesh for the given rarity.

    Creates a simple geometric representation:
    - common/uncommon/rare: bag shapes (tapered cylinder/sphere-ish)
    - epic/legendary: chest shapes (box with lid)

    Args:
        rarity: Rarity tier name.

    Returns:
        MeshSpec dict with vertices, faces, uvs, and metadata.
    """
    display = get_loot_display(rarity)
    rarity_lower = rarity.lower()

    if rarity_lower in ("common", "uncommon", "rare"):
        # Bag mesh: truncated cone/sphere-like
        return _generate_bag_mesh(rarity_lower, display)
    else:
        # Chest mesh: box with lid
        return _generate_chest_mesh(rarity_lower, display)


def _generate_bag_mesh(rarity: str, display: dict[str, Any]) -> MeshSpec:
    """Generate a bag-shaped mesh."""
    # Size scales with rarity
    size_scale = {"common": 0.08, "uncommon": 0.12, "rare": 0.16}
    scale = size_scale.get(rarity, 0.1)

    segments = 8
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Bottom ring (smaller)
    bottom_radius = scale * 0.8
    for i in range(segments):
        angle = (math.tau / segments) * i
        x = math.cos(angle) * bottom_radius
        z = math.sin(angle) * bottom_radius
        vertices.append((x, 0.0, z))

    # Middle ring (widest - the bulge)
    mid_radius = scale * 1.2
    mid_height = scale * 0.6
    for i in range(segments):
        angle = (math.tau / segments) * i
        x = math.cos(angle) * mid_radius
        z = math.sin(angle) * mid_radius
        vertices.append((x, mid_height, z))

    # Top ring (gathered)
    top_radius = scale * 0.4
    top_height = scale * 1.2
    for i in range(segments):
        angle = (math.tau / segments) * i
        x = math.cos(angle) * top_radius
        z = math.sin(angle) * top_radius
        vertices.append((x, top_height, z))

    # Top center vertex (tied knot)
    knot_idx = len(vertices)
    vertices.append((0.0, top_height + scale * 0.3, 0.0))

    # Bottom center vertex
    bot_idx = len(vertices)
    vertices.append((0.0, 0.0, 0.0))

    # Faces: connect rings
    for ring in range(2):  # bottom-to-mid, mid-to-top
        base = ring * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((
                base + i,
                base + j,
                base + segments + j,
                base + segments + i,
            ))

    # Top cap: triangles to knot
    top_base = 2 * segments
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((top_base + i, top_base + j, knot_idx))

    # Bottom cap: triangles to center
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((j, i, bot_idx))

    return _make_result(
        name=display["ground_mesh"],
        vertices=vertices,
        faces=faces,
        rarity=rarity,
        mesh_type="bag",
    )


def _generate_chest_mesh(rarity: str, display: dict[str, Any]) -> MeshSpec:
    """Generate a chest-shaped mesh."""
    is_ornate = rarity == "legendary"
    scale = 0.20 if is_ornate else 0.16

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Base box (chest body)
    box_verts, box_faces = _make_box(0, 0, 0, scale, scale * 0.6, scale * 0.7)
    vertices.extend(box_verts)
    faces.extend(box_faces)

    # Lid (slightly wider, on top of body)
    lid_y = scale * 1.2  # top of body
    lid_offset = len(vertices)
    lid_verts, lid_faces = _make_box(
        0, lid_y, 0,
        scale * 1.05, scale * 0.2, scale * 0.75,
        offset=lid_offset,
    )
    vertices.extend(lid_verts)
    faces.extend(lid_faces)

    if is_ornate:
        # Add decorative knob on top of lid
        knob_y = lid_y + scale * 0.4
        knob_offset = len(vertices)
        knob_segments = 6
        knob_radius = scale * 0.15
        knob_height = scale * 0.15

        # Bottom ring of knob
        for i in range(knob_segments):
            angle = (math.tau / knob_segments) * i
            vertices.append((
                math.cos(angle) * knob_radius,
                knob_y,
                math.sin(angle) * knob_radius,
            ))

        # Top point of knob
        knob_top_idx = len(vertices)
        vertices.append((0.0, knob_y + knob_height, 0.0))

        # Knob faces
        for i in range(knob_segments):
            j = (i + 1) % knob_segments
            faces.append((knob_offset + i, knob_offset + j, knob_top_idx))

    return _make_result(
        name=display["ground_mesh"],
        vertices=vertices,
        faces=faces,
        rarity=rarity,
        mesh_type="chest",
        ornate=is_ornate,
    )


def generate_loot_beam_mesh(
    rarity: str = "rare",
    height: float | None = None,
) -> MeshSpec:
    """Generate a vertical light beam mesh for loot drops.

    Creates a tapered cylinder beam that rises from the ground, wider
    at the base and fading at the top. Only generates for rarities
    that have beam_height > 0.

    Args:
        rarity: Rarity tier name.
        height: Override beam height (defaults to rarity definition).

    Returns:
        MeshSpec dict with vertices, faces, uvs, and metadata.

    Raises:
        ValueError: If rarity has no beam (beam_height == 0).
    """
    display = get_loot_display(rarity)
    beam_height = height if height is not None else display["beam_height"]

    if beam_height <= 0:
        raise ValueError(
            f"Rarity '{rarity}' has no beam (beam_height=0). "
            f"Only uncommon+ rarities have beams."
        )

    segments = 8
    base_radius = 0.15
    top_radius = 0.05
    num_rings = 4  # vertical subdivisions

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Generate rings from bottom to top
    for ring in range(num_rings + 1):
        t = ring / num_rings
        y = t * beam_height
        # Lerp radius from base to top
        r = base_radius * (1 - t) + top_radius * t

        for i in range(segments):
            angle = (math.tau / segments) * i
            x = math.cos(angle) * r
            z = math.sin(angle) * r
            vertices.append((x, y, z))

    # Connect rings with quads
    for ring in range(num_rings):
        base = ring * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((
                base + i,
                base + j,
                base + segments + j,
                base + segments + i,
            ))

    glow_color = display["glow_color"]

    return _make_result(
        name=f"loot_beam_{rarity}",
        vertices=vertices,
        faces=faces,
        rarity=rarity,
        mesh_type="beam",
        beam_height=beam_height,
        glow_color=glow_color,
        segments=segments,
        rings=num_rings,
    )


def compute_item_ground_placement(
    item_type: str,
    position: tuple[float, float, float],
    rarity: str = "common",
) -> dict[str, Any]:
    """Compute ground placement parameters for a dropped item.

    Determines mesh selection, rotation, visual effects, and interaction
    radius for an item dropped at the given position.

    Args:
        item_type: Type of item (e.g. 'weapon', 'armor', 'consumable',
            'material', 'currency', 'quest_item').
        position: (x, y, z) drop position in world space.
        rarity: Rarity tier of the item.

    Returns:
        Dict with placement parameters:
        - 'position': adjusted ground position
        - 'rotation': (rx, ry, rz) rotation in radians
        - 'ground_mesh': which mesh to use
        - 'beam_height': height of rarity beam (0 if none)
        - 'glow_color': glow color tuple or None
        - 'pickup_radius': interaction radius
        - 'bob_amplitude': floating bob animation height
        - 'item_type': original item type
        - 'rarity': rarity tier
    """
    display = get_loot_display(rarity)

    # Adjust y to ground level
    ground_y = position[1]

    # Item type affects rotation
    type_rotations: dict[str, tuple[float, float, float]] = {
        "weapon": (0.0, 0.0, math.pi / 6),      # tilted
        "armor": (0.0, 0.0, 0.0),                # upright
        "consumable": (0.0, 0.0, 0.0),            # upright
        "material": (0.0, 0.0, 0.0),              # upright
        "currency": (0.0, math.pi / 4, 0.0),      # angled
        "quest_item": (0.0, 0.0, 0.0),            # upright
    }
    rotation = type_rotations.get(item_type, (0.0, 0.0, 0.0))

    # Add a pseudo-random Y rotation based on position for variety
    y_rot_hash = int(abs(position[0] * 73 + position[2] * 97)) % 360
    rotation = (rotation[0], rotation[1] + math.radians(y_rot_hash), rotation[2])

    return {
        "position": (position[0], ground_y, position[2]),
        "rotation": rotation,
        "ground_mesh": display["ground_mesh"],
        "beam_height": display["beam_height"],
        "glow_color": display["glow_color"],
        "pickup_radius": display["pickup_radius"],
        "despawn_time": display["despawn_time"],
        "bob_amplitude": display["bob_amplitude"],
        "item_type": item_type,
        "rarity": rarity.lower(),
    }
