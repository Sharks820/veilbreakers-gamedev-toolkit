"""Procedural mesh generation library for VeilBreakers dark fantasy assets.

Provides pure-logic mesh generation functions that return mesh specifications
(vertices, faces, UVs, metadata) WITHOUT importing bpy. Each function returns
a dict that Blender handlers can convert to actual meshes.

Categories:
- FURNITURE: tables, chairs, shelves, chests, barrels, candelabras, bookshelves
- VEGETATION: trees, rocks, mushrooms, roots, ivy
- DUNGEON PROPS: torch sconces, prison doors, sarcophagi, altars, pillars, archways, chains, skull piles
- WEAPONS: hammers, spears, crossbows, scythes, flails, whips, claws, tomes,
  greatswords, curved swords, hand axes, battle axes, greataxes, clubs, maces,
  warhammers, halberds, glaives, shortbows, longbows, magic staves, wands,
  throwing knives, paired daggers, twin swords, dual axes, dual claws,
  brass knuckles, cestus, bladed gauntlets, iron fists, rapiers, estocs,
  javelins, throwing axes, shurikens, bolas, orb focus, skull fetish,
  holy symbol, totem (41 total)
- ARCHITECTURE: gargoyles, fountains, statues, bridges, gates, staircases
- FENCES & BARRIERS: fences, barricades, railings
- TRAPS: spike traps, bear traps, pressure plates, dart launchers, swinging blades, falling cages
- VEHICLES & TRANSPORT: carts, boats, wagon wheels
- STRUCTURAL ELEMENTS: column rows, buttresses, ramparts, drawbridges, wells, ladders, scaffolding
- DARK FANTASY: sacrificial circles, corruption crystals, veil tears, soul cages, blood fountains,
  bone thrones, dark obelisks, spider webs, coffins, gibbets
- MONSTER PARTS: horns, claws, tails, wings, tentacles, mandibles, carapaces, spine ridges, fangs
- MONSTER BODIES: humanoid beasts, quadrupeds, serpents, insectoids, skeletons, golems
- PROJECTILES: arrows, magic orbs, throwing knives, bombs
- ARMOR: helmets, pauldrons, gauntlets, greaves, breastplates, shields
- CONTAINERS & LOOT: urns, crates, sacks, baskets, treasure piles, potion bottles, scrolls
- LIGHT SOURCES: lanterns, braziers, campfires, crystal lights, magic orb lights
- DOORS & WINDOWS: doors, windows, trapdoors
- WALL & FLOOR DECORATIONS: banners, wall shields, mounted heads, painting frames, rugs, chandeliers, hanging cages
- CRAFTING & TRADE: anvils, forges, workbenches, cauldrons, grinding wheels, looms, market stalls
- SIGNS & MARKERS: signposts, gravestones, waystones, milestones
- NATURAL FORMATIONS: stalactites, stalagmites, bone piles, nests, geyser vents, fallen logs
- CONSUMABLES: health potions, mana potions, antidotes, bread, cheese, meat, apples, mushrooms, fish
- CRAFTING MATERIALS: ore, leather, herbs, gems, bone shards
- CURRENCY: coins, coin pouches
- KEY ITEMS: keys, map scrolls, lockpicks
- FOREST ANIMALS: deer, wolves, foxes, rabbits, owls, crows
- MOUNTAIN ANIMALS: mountain goats, eagles, bears
- DOMESTIC ANIMALS: horses, chickens, dogs, cats
- VERMIN: rats, bats, spiders, beetles
- SWAMP ANIMALS: frogs, snakes, turtles

All functions are pure Python with math-only dependencies (no bpy/bmesh).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

# ---------------------------------------------------------------------------
# Mesh result type alias
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Cached trig lookup table
# ---------------------------------------------------------------------------
# Many mesh generators call math.cos / math.sin with the same evenly-spaced
# angles (e.g. 6, 8, 10, 12, 16 segments). Caching the (cos, sin) pairs
# per segment count eliminates redundant trig calls across hundreds of
# cylinder, cone, lathe, sphere, and torus constructions.


@lru_cache(maxsize=32)
def _get_trig_table(segments: int) -> tuple[tuple[float, float], ...]:
    """Return cached (cos, sin) pairs for *segments* evenly-spaced angles."""
    step = 2.0 * math.pi / segments
    return tuple(
        (math.cos(i * step), math.sin(i * step)) for i in range(segments)
    )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _auto_detect_sharp_edges(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    angle_threshold_deg: float = 35.0,
) -> list[list[int]]:
    """Detect sharp edges by dihedral angle between adjacent faces.

    Returns list of [vert_a, vert_b] pairs for edges whose face angle
    exceeds the threshold, plus all boundary edges. This is embedded in
    the MeshSpec so the Blender bridge can mark them sharp at creation time.
    """
    if not vertices or not faces:
        return []

    threshold_rad = math.pi * angle_threshold_deg / 180.0
    cos_threshold = math.cos(threshold_rad)

    # Build edge -> face adjacency + face normals in a single pass
    edge_faces: dict[tuple[int, int], list[int]] = {}
    face_normals: list[tuple[float, float, float]] = []

    for fi, face in enumerate(faces):
        # Newell's method for face normal
        nx, ny, nz = 0.0, 0.0, 0.0
        n = len(face)
        for i in range(n):
            v0 = vertices[face[i]]
            v1 = vertices[face[(i + 1) % n]]
            nx += (v0[1] - v1[1]) * (v0[2] + v1[2])
            ny += (v0[2] - v1[2]) * (v0[0] + v1[0])
            nz += (v0[0] - v1[0]) * (v0[1] + v1[1])
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 1e-10:
            nx /= length
            ny /= length
            nz /= length
        face_normals.append((nx, ny, nz))

        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            key = (min(a, b), max(a, b))
            if key not in edge_faces:
                edge_faces[key] = []
            edge_faces[key].append(fi)

    sharp: list[list[int]] = []
    for (a, b), fi_list in edge_faces.items():
        if len(fi_list) == 2:
            n0 = face_normals[fi_list[0]]
            n1 = face_normals[fi_list[1]]
            dot = n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]
            dot = max(-1.0, min(1.0, dot))
            if dot < cos_threshold:
                sharp.append([a, b])
        elif len(fi_list) == 1:
            sharp.append([a, b])

    return sharp


def _make_result(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    sharp_angle: float = 35.0,
    **extra_meta: Any,
) -> MeshSpec:
    """Package vertices/faces into a standard mesh spec dict.

    Automatically computes sharp edges by dihedral angle and embeds them
    in the MeshSpec for the Blender bridge to process.

    Args:
        sharp_angle: Dihedral angle threshold (degrees) for sharp edge
            detection. Edges sharper than this get marked. Set to 0 to
            disable auto-detection.
    """
    dims = _compute_dimensions(vertices)
    result: MeshSpec = {
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
    # Auto-detect sharp edges for smooth shading support
    if sharp_angle > 0 and vertices and faces:
        result["sharp_edges"] = _auto_detect_sharp_edges(
            vertices, faces, sharp_angle
        )
    return result


def _compute_dimensions(
    verts: list[tuple[float, float, float]],
) -> dict[str, float]:
    """Return bounding-box width/height/depth from vertex list.

    Single-pass min/max instead of 6 separate passes (3 list comprehensions
    each calling min + max).
    """
    if not verts:
        return {"width": 0.0, "height": 0.0, "depth": 0.0}
    v0 = verts[0]
    min_x = max_x = v0[0]
    min_y = max_y = v0[1]
    min_z = max_z = v0[2]
    for v in verts:
        x, y, z = v[0], v[1], v[2]
        if x < min_x:
            min_x = x
        elif x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        elif y > max_y:
            max_y = y
        if z < min_z:
            min_z = z
        elif z > max_z:
            max_z = z
    return {
        "width": max_x - min_x,
        "height": max_y - min_y,
        "depth": max_z - min_z,
    }


def _circle_points(
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    segments: int,
    axis: str = "y",
) -> list[tuple[float, float, float]]:
    """Generate points on a circle in the specified plane.

    axis='y' means the circle lies in the XZ plane at height cy.
    axis='z' means the circle lies in the XY plane at height cz.

    Uses pre-computed trig lookup to avoid redundant sin/cos calls when
    the same segment count is reused across many invocations.
    """
    trig = _get_trig_table(segments)
    pts: list[tuple[float, float, float]] = []
    if axis == "y":
        for ca, sa in trig:
            pts.append((cx + ca * radius, cy, cz + sa * radius))
    elif axis == "z":
        for ca, sa in trig:
            pts.append((cx + ca * radius, cy + sa * radius, cz))
    else:  # 'x'
        for ca, sa in trig:
            pts.append((cx, cy + ca * radius, cz + sa * radius))
    return pts


def _make_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate an axis-aligned box centred at (cx, cy, cz) with half-sizes sx, sy, sz.

    Returns (vertices_8, faces_6) with face indices offset by base_idx.
    """
    hx, hy, hz = sx, sy, sz
    verts = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    b = base_idx
    faces = [
        (b + 0, b + 3, b + 2, b + 1),
        (b + 4, b + 5, b + 6, b + 7),
        (b + 0, b + 1, b + 5, b + 4),
        (b + 2, b + 3, b + 7, b + 6),
        (b + 0, b + 4, b + 7, b + 3),
        (b + 1, b + 2, b + 6, b + 5),
    ]
    return verts, faces


def _make_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
    base_idx: int = 0,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder (along Y axis) with optional caps."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Pre-compute trig once and reuse for both rings
    trig = _get_trig_table(segments)
    cy_top = cy_bottom + height

    # Bottom ring
    for ca, sa in trig:
        verts.append((cx + ca * radius, cy_bottom, cz + sa * radius))
    # Top ring
    for ca, sa in trig:
        verts.append((cx + ca * radius, cy_top, cz + sa * radius))

    b = base_idx
    # Side faces
    for i in range(segments):
        i1 = i
        i2 = (i + 1) % segments
        faces.append((b + i1, b + i2, b + segments + i2, b + segments + i1))

    # Bottom cap
    if cap_bottom:
        faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))

    # Top cap
    if cap_top:
        faces.append(tuple(b + segments + i for i in range(segments)))

    return verts, faces


def _make_cone(
    cx: float, cy_bottom: float, cz: float,
    radius: float, height: float,
    segments: int = 12,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cone (apex at top, along Y axis)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Base ring (cached trig)
    trig = _get_trig_table(segments)
    for ca, sa in trig:
        verts.append((cx + ca * radius, cy_bottom, cz + sa * radius))
    # Apex
    verts.append((cx, cy_bottom + height, cz))

    b = base_idx
    apex = b + segments
    # Side triangles
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((b + i, b + i2, apex))

    # Bottom cap
    faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))

    return verts, faces


def _make_torus_ring(
    cx: float, cy: float, cz: float,
    major_radius: float, minor_radius: float,
    major_segments: int = 16,
    minor_segments: int = 8,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a torus lying in the XZ plane centred at (cx, cy, cz)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for i in range(major_segments):
        theta = 2.0 * math.pi * i / major_segments
        ct, st = math.cos(theta), math.sin(theta)
        # Centre of the tube cross-section
        tcx = cx + major_radius * ct
        tcz = cz + major_radius * st
        for j in range(minor_segments):
            phi = 2.0 * math.pi * j / minor_segments
            cp, sp = math.cos(phi), math.sin(phi)
            r = major_radius + minor_radius * cp
            verts.append((
                cx + r * ct,
                cy + minor_radius * sp,
                cz + r * st,
            ))

    b = base_idx
    for i in range(major_segments):
        i_next = (i + 1) % major_segments
        for j in range(minor_segments):
            j_next = (j + 1) % minor_segments
            v0 = b + i * minor_segments + j
            v1 = b + i * minor_segments + j_next
            v2 = b + i_next * minor_segments + j_next
            v3 = b + i_next * minor_segments + j
            faces.append((v0, v1, v2, v3))

    return verts, faces


def _make_tapered_cylinder(
    cx: float, cy_bottom: float, cz: float,
    radius_bottom: float, radius_top: float,
    height: float,
    segments: int = 12,
    rings: int = 1,
    base_idx: int = 0,
    cap_top: bool = True,
    cap_bottom: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a cylinder that tapers from radius_bottom to radius_top."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    total_rings = rings + 1  # number of cross-section rings

    for ring in range(total_rings):
        t = ring / max(rings, 1)
        y = cy_bottom + t * height
        r = radius_bottom + t * (radius_top - radius_bottom)
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            verts.append((
                cx + math.cos(angle) * r,
                y,
                cz + math.sin(angle) * r,
            ))

    b = base_idx
    for ring in range(rings):
        for i in range(segments):
            i2 = (i + 1) % segments
            r0 = ring * segments
            r1 = (ring + 1) * segments
            faces.append((b + r0 + i, b + r0 + i2, b + r1 + i2, b + r1 + i))

    if cap_bottom:
        faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))
    if cap_top:
        last_ring = rings * segments
        faces.append(tuple(b + last_ring + i for i in range(segments)))

    return verts, faces


def _make_beveled_box(
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
    bevel: float = 0.02,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a box with beveled edges for better visual quality.

    Creates a 24-vertex box where each edge is inset by `bevel` amount,
    producing chamfered edges that catch light more naturally.
    """
    hx, hy, hz = sx, sy, sz
    b_val = bevel
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # For each of the 8 corners, emit 3 vertices slightly inset along each axis
    corners = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]

    for (sx_sign, sy_sign, sz_sign) in corners:
        base_x = cx + sx_sign * hx
        base_y = cy + sy_sign * hy
        base_z = cz + sz_sign * hz
        # Vertex inset along X
        verts.append((base_x - sx_sign * b_val, base_y, base_z))
        # Vertex inset along Y
        verts.append((base_x, base_y - sy_sign * b_val, base_z))
        # Vertex inset along Z
        verts.append((base_x, base_y, base_z - sz_sign * b_val))

    b = base_idx
    # Main faces (6 quads, each using the inset vertices from 4 corners)
    # Bottom face (Y-) uses vert index 1 from each bottom corner (0,1,2,3)
    # Corner 0 -> idx 0*3+1=1, Corner 1 -> idx 1*3+1=4, etc.

    # Bottom (y-): corners 0,1,2,3 -> use Y-inset verts (index 1 of each triple)
    faces.append((b + 0 * 3 + 1, b + 3 * 3 + 1, b + 2 * 3 + 1, b + 1 * 3 + 1))
    # Top (y+): corners 4,5,6,7
    faces.append((b + 4 * 3 + 1, b + 5 * 3 + 1, b + 6 * 3 + 1, b + 7 * 3 + 1))
    # Front (z-): corners 0,1,2,3 -> use Z-inset verts (index 2)
    faces.append((b + 0 * 3 + 2, b + 1 * 3 + 2, b + 2 * 3 + 2, b + 3 * 3 + 2))
    # Back (z+): corners 4,5,6,7
    faces.append((b + 4 * 3 + 2, b + 7 * 3 + 2, b + 6 * 3 + 2, b + 5 * 3 + 2))
    # Left (x-): corners 0,3,7,4 -> use X-inset verts (index 0)
    faces.append((b + 0 * 3 + 0, b + 4 * 3 + 0, b + 7 * 3 + 0, b + 3 * 3 + 0))
    # Right (x+): corners 1,2,6,5
    faces.append((b + 1 * 3 + 0, b + 2 * 3 + 0, b + 6 * 3 + 0, b + 5 * 3 + 0))

    # Bevel edge faces -- connect adjacent inset vertices along each of the 12 edges
    # Each edge of the original cube connects 2 corners; we create a quad
    # from their respective inset vertices.
    edge_pairs = [
        # Bottom ring (y-)
        (0, 1, 0, 2),  # edge 0-1: X-inset of 0, Z-inset of 0, Z-inset of 1, X-inset of 1
        (1, 2, 0, 2),
        (2, 3, 0, 2),
        (3, 0, 0, 2),
        # Top ring (y+)
        (4, 5, 0, 2),
        (5, 6, 0, 2),
        (6, 7, 0, 2),
        (7, 4, 0, 2),
        # Vertical edges
        (0, 4, 1, 1),  # Y-inset
        (1, 5, 1, 1),
        (2, 6, 1, 1),
        (3, 7, 1, 1),
    ]

    # For the 12 edges, determine which pair of inset vertices to use
    # Bottom horizontal edges (along X or Z axis at y-)
    # Edge 0-1: along +X at z-, y-  -> use verts [Z-inset of 0, X-inset of 1]
    # and [X-inset of 0, Z-inset of 1] - this creates the bevel strip

    # Simplified: for each edge, just make a quad from the two closest inset verts
    # of each corner pair. The 'axis' of the edge determines which inset verts to pick.

    # Horizontal bottom edges (y-): corners connected by x or z movement
    def _bevel_edge(c0: int, c1: int, ax0: int, ax1: int) -> tuple[int, ...]:
        return (b + c0 * 3 + ax0, b + c0 * 3 + ax1, b + c1 * 3 + ax1, b + c1 * 3 + ax0)

    # Bottom edges (y-, z-): 0->1 along X
    faces.append(_bevel_edge(0, 1, 2, 1))  # Z-inset, Y-inset
    faces.append(_bevel_edge(1, 2, 0, 1))  # X-inset, Y-inset
    faces.append(_bevel_edge(2, 3, 2, 1))
    faces.append(_bevel_edge(3, 0, 0, 1))
    # Top edges
    faces.append(_bevel_edge(4, 5, 1, 2))
    faces.append(_bevel_edge(5, 6, 1, 0))
    faces.append(_bevel_edge(6, 7, 1, 2))
    faces.append(_bevel_edge(7, 4, 1, 0))
    # Vertical edges
    faces.append(_bevel_edge(0, 4, 0, 2))
    faces.append(_bevel_edge(1, 5, 2, 0))
    faces.append(_bevel_edge(2, 6, 0, 2))
    faces.append(_bevel_edge(3, 7, 2, 0))

    return verts, faces


def _merge_meshes(
    *parts: tuple[list[tuple[float, float, float]], list[tuple[int, ...]]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Merge multiple (verts, faces) tuples, remapping face indices."""
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    for verts, faces in parts:
        offset = len(all_verts)
        all_verts.extend(verts)
        for face in faces:
            all_faces.append(tuple(idx + offset for idx in face))
    return all_verts, all_faces


def _make_faceted_rock_shell(
    size: float,
    detail: int,
    seed: int,
    *,
    height_scale: float = 1.0,
    width_scale: float = 1.0,
    depth_scale: float = 1.0,
    flat_base: bool = True,
    flat_top: bool = True,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Build an angular rock shell with fractured, non-spherical massing."""
    import random as _rng

    rng = _rng.Random(seed)
    detail = max(1, min(5, detail))
    segments = 8 + detail * 2
    rings = 2 + detail

    height = size * height_scale * (0.9 + 0.08 * detail)
    half_height = height * 0.5
    base_radius = size * 0.42
    x_scale = width_scale * rng.uniform(0.88, 1.12)
    z_scale = depth_scale * rng.uniform(0.82, 1.08)
    phase = rng.uniform(0.0, math.tau)
    fracture_bias = rng.uniform(-0.75, 0.75)

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for ring in range(rings + 1):
        t = ring / max(rings, 1)
        y = -half_height + t * height
        ring_radius = base_radius * (1.08 - 0.34 * t)
        if flat_base and ring == 0:
            ring_radius *= 0.82
            y -= height * 0.03
        if flat_top and ring == rings:
            ring_radius *= 0.72
            y += height * 0.03

        ring_radius *= 1.0 + 0.05 * math.sin((t * math.pi) + fracture_bias)

        for seg in range(segments):
            angle = (math.tau * seg / segments) + phase
            ca = math.cos(angle)
            sa = math.sin(angle)

            ridge = 1.0
            ridge += 0.16 * math.cos(angle * 2.0 + fracture_bias)
            ridge += 0.08 * math.sin(angle * 5.0 - fracture_bias * 0.7)
            ridge += rng.uniform(-0.08, 0.10)

            if ca > 0.55:
                ridge *= 0.88
            elif ca < -0.45:
                ridge *= 1.05
            if sa > 0.65:
                ridge *= 0.92
            elif sa < -0.65:
                ridge *= 1.02
            if ring == 0:
                ridge *= 0.92
            elif ring == rings:
                ridge *= 0.86

            radius = ring_radius * max(0.55, ridge)
            vertices.append((
                ca * radius * x_scale,
                y,
                sa * radius * z_scale,
            ))

    for ring in range(rings):
        start = ring * segments
        next_start = (ring + 1) * segments
        for seg in range(segments):
            seg_next = (seg + 1) % segments
            faces.append((
                start + seg,
                start + seg_next,
                next_start + seg_next,
                next_start + seg,
            ))

    faces.append(tuple(range(segments - 1, -1, -1)))
    top_start = rings * segments
    faces.append(tuple(top_start + i for i in range(segments)))

    return vertices, faces


def _make_sphere(
    cx: float, cy: float, cz: float,
    radius: float,
    rings: int = 8,
    sectors: int = 12,
    base_idx: int = 0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a UV sphere."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    # Bottom pole
    verts.append((cx, cy - radius, cz))
    for i in range(1, rings):
        phi = math.pi * i / rings
        y = cy - radius * math.cos(phi)
        ring_r = radius * math.sin(phi)
        for j in range(sectors):
            theta = 2.0 * math.pi * j / sectors
            verts.append((
                cx + ring_r * math.cos(theta),
                y,
                cz + ring_r * math.sin(theta),
            ))
    # Top pole
    verts.append((cx, cy + radius, cz))

    b = base_idx
    # Bottom cap triangles
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((b, b + 1 + j, b + 1 + j2))

    # Middle quads
    for i in range(rings - 2):
        for j in range(sectors):
            j2 = (j + 1) % sectors
            r0 = 1 + i * sectors
            r1 = 1 + (i + 1) * sectors
            faces.append((b + r0 + j, b + r1 + j, b + r1 + j2, b + r0 + j2))

    # Top cap triangles
    top_idx = b + len(verts) - 1
    last_ring_start = 1 + (rings - 2) * sectors
    for j in range(sectors):
        j2 = (j + 1) % sectors
        faces.append((b + last_ring_start + j, top_idx, b + last_ring_start + j2))

    return verts, faces


def _make_lathe(
    profile: list[tuple[float, float]],
    segments: int = 12,
    base_idx: int = 0,
    close_top: bool = False,
    close_bottom: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Revolve a 2D profile (r, y) around the Y axis to create a lathe mesh.

    Profile should be a list of (radius, height) pairs from bottom to top.
    """
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n_profile = len(profile)

    for i in range(n_profile):
        r, y = profile[i]
        for j in range(segments):
            angle = 2.0 * math.pi * j / segments
            verts.append((r * math.cos(angle), y, r * math.sin(angle)))

    b = base_idx
    for i in range(n_profile - 1):
        for j in range(segments):
            j2 = (j + 1) % segments
            r0 = i * segments
            r1 = (i + 1) * segments
            faces.append((b + r0 + j, b + r0 + j2, b + r1 + j2, b + r1 + j))

    if close_bottom and n_profile > 0:
        faces.append(tuple(b + i for i in range(segments - 1, -1, -1)))
    if close_top and n_profile > 0:
        last = (n_profile - 1) * segments
        faces.append(tuple(b + last + i for i in range(segments)))

    return verts, faces


def _make_profile_extrude(
    profile: list[tuple[float, float]],
    depth: float,
    base_idx: int = 0,
    center_z: float = 0.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Extrude a 2D profile (x, y) along the Z axis."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n = len(profile)
    hz = depth / 2.0

    # Front face vertices
    for x, y in profile:
        verts.append((x, y, center_z - hz))
    # Back face vertices
    for x, y in profile:
        verts.append((x, y, center_z + hz))

    b = base_idx
    # Side quads
    for i in range(n - 1):
        i2 = i + 1
        faces.append((b + i, b + i2, b + n + i2, b + n + i))

    # Close the loop
    faces.append((b + n - 1, b + 0, b + n, b + n + n - 1))

    # Front cap
    faces.append(tuple(b + i for i in range(n - 1, -1, -1)))
    # Back cap
    faces.append(tuple(b + n + i for i in range(n)))

    return verts, faces


# =========================================================================
# CATEGORY 1: FURNITURE
# =========================================================================


def generate_table_mesh(
    style: str = "tavern_rough",
    legs: int = 4,
    width: float = 1.2,
    height: float = 0.8,
    depth: float = 0.7,
) -> MeshSpec:
    """Generate a table mesh with proper geometry.

    Args:
        style: Visual style - "tavern_rough", "noble_carved", or "stone_slab".
        legs: Number of legs (2 or 4).
        width: Table width (X axis).
        height: Table height (Y axis).
        depth: Table depth (Z axis).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Table top
    top_thickness = 0.05 if style == "stone_slab" else 0.04
    if style == "noble_carved":
        top_thickness = 0.035
    top_verts, top_faces = _make_beveled_box(
        0, height - top_thickness / 2, 0,
        width / 2, top_thickness / 2, depth / 2,
        bevel=0.008,
    )
    parts.append((top_verts, top_faces))

    # Legs
    leg_radius = 0.035 if style == "tavern_rough" else 0.025
    leg_segments = 6 if style == "tavern_rough" else 8
    leg_height = height - top_thickness

    if style == "stone_slab":
        # Stone slab: two solid slab legs
        slab_w = width * 0.08
        slab_d = depth * 0.4
        for xoff in [-width * 0.35, width * 0.35]:
            sv, sf = _make_beveled_box(
                xoff, leg_height / 2, 0,
                slab_w, leg_height / 2, slab_d,
                bevel=0.01,
            )
            parts.append((sv, sf))
    else:
        positions = []
        inset_x = width * 0.42
        inset_z = depth * 0.42
        if legs == 4:
            positions = [
                (-inset_x, inset_z), (inset_x, inset_z),
                (-inset_x, -inset_z), (inset_x, -inset_z),
            ]
        elif legs == 2:
            positions = [(-inset_x, 0), (inset_x, 0)]
        else:
            # Default 4
            positions = [
                (-inset_x, inset_z), (inset_x, inset_z),
                (-inset_x, -inset_z), (inset_x, -inset_z),
            ]

        for lx, lz in positions:
            if style == "tavern_rough":
                # Slightly tapered rough legs
                lv, lf = _make_tapered_cylinder(
                    lx, 0, lz,
                    leg_radius * 1.2, leg_radius * 0.9,
                    leg_height, leg_segments, rings=3,
                )
            else:
                # Noble carved legs with profile
                lv, lf = _make_tapered_cylinder(
                    lx, 0, lz,
                    leg_radius * 0.8, leg_radius * 1.0,
                    leg_height, leg_segments, rings=4,
                )
            parts.append((lv, lf))

        # Cross-braces for tavern style
        if style == "tavern_rough" and legs == 4:
            brace_y = leg_height * 0.25
            brace_r = 0.012
            brace_segs = 6
            # Front-back brace
            sv, sf = _make_tapered_cylinder(
                0, brace_y, inset_z,
                brace_r, brace_r,
                width * 0.84, brace_segs, rings=1,
            )
            # Rotate by swapping axes -- approximate by placing horizontally
            rotated_v = [(v[1] - brace_y, brace_y, v[2]) for v in sv]
            # Re-place along X
            rotated_v = [
                (-width * 0.42 + (v[0] + brace_y) / leg_height * width * 0.84,
                 brace_y, inset_z)
                for i, v in enumerate(sv)
            ]
            # Simplified: just use a box brace
            bv, bf = _make_box(0, brace_y, inset_z, width * 0.42, brace_r, brace_r)
            parts.append((bv, bf))
            bv2, bf2 = _make_box(0, brace_y, -inset_z, width * 0.42, brace_r, brace_r)
            parts.append((bv2, bf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Table_{style}", verts, faces, style=style, category="furniture")


def generate_chair_mesh(
    style: str = "wooden_bench",
    has_arms: bool = False,
    has_back: bool = True,
) -> MeshSpec:
    """Generate a chair mesh.

    Args:
        style: "wooden_bench", "throne", or "stool".
        has_arms: Whether to include armrests.
        has_back: Whether to include a backrest.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    seat_w = 0.45 if style != "throne" else 0.6
    seat_d = 0.42 if style != "throne" else 0.55
    seat_h = 0.45
    seat_thick = 0.03

    # Seat
    sv, sf = _make_beveled_box(
        0, seat_h, 0,
        seat_w / 2, seat_thick / 2, seat_d / 2,
        bevel=0.005,
    )
    parts.append((sv, sf))

    # Legs
    leg_r = 0.02 if style != "throne" else 0.03
    leg_segs = 6
    inx = seat_w * 0.4
    inz = seat_d * 0.4
    for lx, lz in [(-inx, inz), (inx, inz), (-inx, -inz), (inx, -inz)]:
        lv, lf = _make_tapered_cylinder(
            lx, 0, lz,
            leg_r * 1.1, leg_r * 0.9, seat_h - seat_thick / 2,
            leg_segs, rings=2,
        )
        parts.append((lv, lf))

    # Backrest
    if has_back and style != "stool":
        back_h = 0.5 if style != "throne" else 0.9
        back_thick = 0.025 if style != "throne" else 0.04

        if style == "throne":
            # Throne: wide solid back with slight arch
            bv, bf = _make_beveled_box(
                0, seat_h + seat_thick / 2 + back_h / 2, -seat_d * 0.38,
                seat_w / 2, back_h / 2, back_thick / 2,
                bevel=0.008,
            )
            parts.append((bv, bf))
            # Throne finials (top ornaments)
            for xoff in [-seat_w * 0.38, seat_w * 0.38]:
                fv, ff = _make_sphere(
                    xoff, seat_h + seat_thick + back_h + 0.03, -seat_d * 0.38,
                    0.025, rings=5, sectors=6,
                )
                parts.append((fv, ff))
        else:
            # Wooden bench: two vertical slats
            slat_w = 0.04
            for xoff in [-seat_w * 0.25, seat_w * 0.25]:
                bv, bf = _make_beveled_box(
                    xoff, seat_h + seat_thick / 2 + back_h / 2, -seat_d * 0.38,
                    slat_w / 2, back_h / 2, back_thick / 2,
                    bevel=0.003,
                )
                parts.append((bv, bf))
            # Horizontal rail
            rv, rf = _make_beveled_box(
                0, seat_h + seat_thick + back_h * 0.85, -seat_d * 0.38,
                seat_w * 0.35, 0.015, back_thick / 2,
                bevel=0.003,
            )
            parts.append((rv, rf))

    # Armrests
    if has_arms:
        arm_h = 0.25
        arm_thick = 0.02
        arm_w = seat_d * 0.35
        for xoff in [-seat_w * 0.45, seat_w * 0.45]:
            # Arm support post
            pv, pf = _make_tapered_cylinder(
                xoff, seat_h + seat_thick / 2, seat_d * 0.15,
                leg_r, leg_r, arm_h, leg_segs, rings=1,
            )
            parts.append((pv, pf))
            # Arm rest pad
            av, af = _make_beveled_box(
                xoff, seat_h + seat_thick / 2 + arm_h, 0,
                arm_thick / 2, arm_thick / 2, arm_w,
                bevel=0.003,
            )
            parts.append((av, af))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Chair_{style}", verts, faces, style=style, category="furniture")


def generate_shelf_mesh(
    tiers: int = 3,
    width: float = 0.8,
    depth: float = 0.25,
    freestanding: bool = True,
) -> MeshSpec:
    """Generate a shelf mesh (wall-mounted or freestanding).

    Args:
        tiers: Number of shelf tiers.
        width: Width of the shelf.
        depth: Depth of each shelf.
        freestanding: If True, includes side panels; if False, wall-mount brackets.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    tier_spacing = 0.35
    shelf_thick = 0.02
    total_h = tiers * tier_spacing

    # Shelf boards
    for i in range(tiers):
        y = i * tier_spacing + shelf_thick / 2
        sv, sf = _make_beveled_box(
            0, y, 0,
            width / 2, shelf_thick / 2, depth / 2,
            bevel=0.004,
        )
        parts.append((sv, sf))

    if freestanding:
        # Side panels
        panel_thick = 0.018
        for xoff in [-width / 2 + panel_thick / 2, width / 2 - panel_thick / 2]:
            pv, pf = _make_beveled_box(
                xoff, total_h / 2, 0,
                panel_thick / 2, total_h / 2, depth / 2,
                bevel=0.003,
            )
            parts.append((pv, pf))
        # Back panel (thin)
        bv, bf = _make_beveled_box(
            0, total_h / 2, -depth / 2 + 0.005,
            width / 2, total_h / 2, 0.005,
            bevel=0.002,
        )
        parts.append((bv, bf))
    else:
        # Wall-mount brackets (L-shaped)
        bracket_thick = 0.015
        for xoff in [-width * 0.35, width * 0.35]:
            for i in range(tiers):
                y = i * tier_spacing
                # Horizontal part
                hv, hf = _make_box(
                    xoff, y - bracket_thick, -depth * 0.3,
                    bracket_thick, bracket_thick, depth * 0.3,
                )
                parts.append((hv, hf))
                # Vertical part
                vv, vf = _make_box(
                    xoff, y + tier_spacing * 0.3, -depth / 2 + bracket_thick,
                    bracket_thick, tier_spacing * 0.3, bracket_thick,
                )
                parts.append((vv, vf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Shelf", verts, faces, tiers=tiers, category="furniture")


def generate_chest_mesh(
    style: str = "wooden_bound",
    size: float = 1.0,
) -> MeshSpec:
    """Generate a chest/treasure box mesh.

    Args:
        style: "wooden_bound", "iron_locked", or "ornate_treasure".
        size: Scale factor (1.0 = standard).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    w = 0.5 * size
    h = 0.3 * size
    d = 0.35 * size

    # Main body (bottom half)
    bv, bf = _make_beveled_box(
        0, h * 0.4, 0,
        w / 2, h * 0.4, d / 2,
        bevel=0.008 * size,
    )
    parts.append((bv, bf))

    # Lid (half-cylinder top)
    lid_segs = 10
    lid_verts: list[tuple[float, float, float]] = []
    lid_faces: list[tuple[int, ...]] = []
    lid_base_y = h * 0.8
    lid_radius = d / 2

    for i in range(lid_segs + 1):
        t = i / lid_segs
        angle = math.pi * t
        y = lid_base_y + math.sin(angle) * lid_radius * 0.4
        z_scale = math.cos(angle)
        for xpos in [-w / 2, w / 2]:
            lid_verts.append((xpos, y, z_scale * lid_radius))

    for i in range(lid_segs):
        bi = i * 2
        lid_faces.append((bi, bi + 1, bi + 3, bi + 2))

    # End caps of lid
    left_indices = [i * 2 for i in range(lid_segs + 1)]
    right_indices = [i * 2 + 1 for i in range(lid_segs + 1)]
    lid_faces.append(tuple(left_indices[::-1]))
    lid_faces.append(tuple(right_indices))

    parts.append((lid_verts, lid_faces))

    # Iron bands for wooden_bound / ornate
    if style in ("wooden_bound", "ornate_treasure"):
        band_h = 0.01 * size
        band_offset = 0.005 * size
        for band_y in [h * 0.2, h * 0.6]:
            bv2, bf2 = _make_box(
                0, band_y, 0,
                w / 2 + band_offset, band_h, d / 2 + band_offset,
            )
            parts.append((bv2, bf2))

    # Lock hasp for iron_locked
    if style == "iron_locked":
        # Lock plate
        lv, lf = _make_beveled_box(
            0, h * 0.75, d / 2 + 0.01 * size,
            0.04 * size, 0.04 * size, 0.008 * size,
            bevel=0.003 * size,
        )
        parts.append((lv, lf))
        # Lock body (cylinder)
        cv, cf = _make_cylinder(
            0, h * 0.68, d / 2 + 0.018 * size,
            0.015 * size, 0.04 * size,
            segments=8,
        )
        parts.append((cv, cf))

    # Ornate corner pieces
    if style == "ornate_treasure":
        corner_r = 0.02 * size
        for xoff in [-w / 2, w / 2]:
            for zoff in [-d / 2, d / 2]:
                for yoff in [0, h * 0.78]:
                    sv, sf = _make_sphere(
                        xoff, yoff, zoff,
                        corner_r, rings=4, sectors=6,
                    )
                    parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Chest_{style}", verts, faces, style=style, category="furniture")


def generate_barrel_mesh(
    height: float = 0.9,
    radius: float = 0.25,
    staves: int = 16,
) -> MeshSpec:
    """Generate a barrel mesh with stave bulge and iron bands.

    Args:
        height: Barrel height.
        radius: Base radius.
        staves: Number of staves (vertical planks).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Main barrel body with bulge profile
    profile: list[tuple[float, float]] = []
    rings = 10
    for i in range(rings + 1):
        t = i / rings
        y = t * height
        # Barrel bulge: max at middle, narrower at top/bottom
        bulge = 1.0 + 0.12 * math.sin(t * math.pi)
        r = radius * bulge
        profile.append((r, y))

    bv, bf = _make_lathe(profile, segments=staves, close_top=True, close_bottom=True)
    parts.append((bv, bf))

    # Iron bands (torus rings)
    band_positions = [height * 0.15, height * 0.5, height * 0.85]
    for band_y in band_positions:
        # Use a thin cylinder as the band
        t = band_y / height
        bulge = 1.0 + 0.12 * math.sin(t * math.pi)
        band_r = radius * bulge + 0.005
        tv, tf = _make_torus_ring(
            0, band_y, 0,
            band_r, 0.008,
            major_segments=staves, minor_segments=4,
        )
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Barrel", verts, faces, category="furniture")


def generate_candelabra_mesh(
    arms: int = 5,
    height: float = 1.5,
    wall_mounted: bool = False,
) -> MeshSpec:
    """Generate a candelabra mesh.

    Args:
        arms: Number of candle arms.
        height: Total height.
        wall_mounted: If True, generates wall bracket version.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 8

    if wall_mounted:
        # Wall plate
        pv, pf = _make_beveled_box(
            0, height * 0.5, -0.02,
            0.06, height * 0.15, 0.01,
            bevel=0.003,
        )
        parts.append((pv, pf))
        # Single arm extending out
        av, af = _make_tapered_cylinder(
            0, height * 0.4, 0,
            0.01, 0.008, 0.2,
            segs, rings=2,
        )
        # Rotate arm forward (swap y/z approximation using horizontal placement)
        arm_verts = [(v[0], height * 0.45, v[1] - height * 0.4 + 0.15) for v in av]
        parts.append((arm_verts, af))
        # Candle cup at end
        cv, cf = _make_tapered_cylinder(
            0, height * 0.43, 0.18,
            0.02, 0.025, 0.03,
            segs, rings=1,
        )
        parts.append((cv, cf))
    else:
        # Standing candelabra
        # Base (wide disc)
        base_profile = [
            (0.12, 0),
            (0.13, 0.01),
            (0.11, 0.02),
            (0.04, 0.03),
        ]
        bsv, bsf = _make_lathe(base_profile, segments=segs, close_bottom=True)
        parts.append((bsv, bsf))

        # Central shaft
        shaft_profile = [
            (0.02, 0.03),
            (0.015, height * 0.3),
            (0.025, height * 0.35),  # Decorative node
            (0.015, height * 0.4),
            (0.012, height * 0.7),
            (0.02, height * 0.72),  # Another node
            (0.015, height * 0.75),
        ]
        sv, sf = _make_lathe(shaft_profile, segments=segs)
        parts.append((sv, sf))

        # Arms radiating from top
        arm_y = height * 0.75
        for i in range(arms):
            angle = 2.0 * math.pi * i / arms
            arm_len = 0.15
            end_x = math.cos(angle) * arm_len
            end_z = math.sin(angle) * arm_len
            # Arm (small cylinder approximated as box)
            mid_x = end_x * 0.5
            mid_z = end_z * 0.5
            arm_r = 0.008
            av, af = _make_cylinder(
                mid_x, arm_y - 0.01, mid_z,
                arm_r, 0.02, segments=6,
            )
            parts.append((av, af))

            # Curved upward section
            up_x = end_x * 0.85
            up_z = end_z * 0.85
            uv, uf = _make_cylinder(
                up_x, arm_y, up_z,
                arm_r, 0.05, segments=6,
            )
            parts.append((uv, uf))

            # Candle cup
            cv, cf = _make_tapered_cylinder(
                end_x, arm_y + 0.04, end_z,
                0.018, 0.022, 0.025,
                segs, rings=1,
            )
            parts.append((cv, cf))

            # Candle stub
            sv2, sf2 = _make_cylinder(
                end_x, arm_y + 0.065, end_z,
                0.008, 0.06, segments=6,
            )
            parts.append((sv2, sf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Candelabra", verts, faces, arms=arms, category="furniture")


def generate_bookshelf_mesh(
    sections: int = 3,
    with_books: bool = True,
) -> MeshSpec:
    """Generate a bookshelf mesh with optional book meshes.

    Args:
        sections: Number of vertical sections (rows of books).
        with_books: Whether to include book meshes on shelves.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    total_w = 0.9
    total_d = 0.28
    section_h = 0.32
    total_h = sections * section_h + 0.04  # top cap
    panel_thick = 0.02

    # Side panels
    for xoff in [-total_w / 2 + panel_thick / 2, total_w / 2 - panel_thick / 2]:
        sv, sf = _make_beveled_box(
            xoff, total_h / 2, 0,
            panel_thick / 2, total_h / 2, total_d / 2,
            bevel=0.003,
        )
        parts.append((sv, sf))

    # Shelf boards (including top and bottom)
    for i in range(sections + 1):
        y = i * section_h + panel_thick / 2
        sv, sf = _make_beveled_box(
            0, y, 0,
            total_w / 2, panel_thick / 2, total_d / 2,
            bevel=0.003,
        )
        parts.append((sv, sf))

    # Back panel
    bv, bf = _make_box(
        0, total_h / 2, -total_d / 2 + 0.005,
        total_w / 2, total_h / 2, 0.005,
    )
    parts.append((bv, bf))

    # Books
    if with_books:
        import random as _rng
        rng = _rng.Random(42)  # Deterministic book placement
        inner_w = total_w - panel_thick * 2
        for section in range(sections):
            shelf_y = section * section_h + panel_thick
            x_cursor = -inner_w / 2 + 0.02
            while x_cursor < inner_w / 2 - 0.03:
                book_w = rng.uniform(0.015, 0.035)
                book_h = rng.uniform(section_h * 0.6, section_h * 0.88)
                book_d = rng.uniform(total_d * 0.6, total_d * 0.85)
                # Slight lean
                lean = rng.uniform(-0.02, 0.02)
                bkv, bkf = _make_beveled_box(
                    x_cursor + book_w / 2 + lean,
                    shelf_y + book_h / 2,
                    -total_d / 2 + 0.01 + book_d / 2,
                    book_w / 2, book_h / 2, book_d / 2,
                    bevel=0.002,
                )
                parts.append((bkv, bkf))
                x_cursor += book_w + rng.uniform(0.002, 0.008)

    verts, faces = _merge_meshes(*parts)
    return _make_result("Bookshelf", verts, faces, sections=sections, category="furniture")


# =========================================================================
# CATEGORY 2: VEGETATION
# =========================================================================


def generate_tree_mesh(
    trunk_height: float = 3.0,
    trunk_radius: float = 0.2,
    branch_count: int = 8,
    canopy_style: str = "ancient_oak",
) -> MeshSpec:
    """Generate a tree mesh with trunk, branches, and canopy.

    Args:
        trunk_height: Height of the main trunk.
        trunk_radius: Radius of trunk base.
        branch_count: Number of branches.
        canopy_style: "dead_twisted", "ancient_oak", "dark_pine",
            "willow_hanging", "veil_healthy", "veil_boundary", or
            "veil_blighted".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 14

    # Trunk with taper and organic wobble
    trunk_profile: list[tuple[float, float]] = []
    trunk_rings = 16
    for i in range(trunk_rings + 1):
        t = i / trunk_rings
        y = t * trunk_height
        # Organic taper with slight bulges
        r = trunk_radius * (1.0 - t * 0.6)
        # Add subtle wobble for organic feel
        wobble = math.sin(t * 5.0) * trunk_radius * 0.05
        r += wobble
        # Root flare at base
        if t < 0.1:
            r += trunk_radius * 0.3 * (1.0 - t / 0.1)
        trunk_profile.append((max(r, 0.01), y))

    tv, tf = _make_lathe(trunk_profile, segments=segs, close_bottom=True)
    parts.append((tv, tf))

    # Branches
    sparse_styles = {"dead_twisted", "veil_blighted"}
    branch_start_y = trunk_height * (0.3 if canopy_style not in sparse_styles else 0.2)
    for i in range(branch_count):
        angle = 2.0 * math.pi * i / branch_count + (i * 0.3)  # Spiral offset
        t_branch = 0.3 + 0.6 * (i / max(branch_count - 1, 1))
        y = branch_start_y + (trunk_height - branch_start_y) * t_branch * 0.8
        branch_len = trunk_height * 0.3 * (1.0 - t_branch * 0.3)
        branch_r = trunk_radius * 0.2 * (1.0 - t_branch * 0.5)

        # Branch direction
        dx = math.cos(angle) * branch_len
        dz = math.sin(angle) * branch_len
        dy = branch_len * 0.3  # Slight upward

        if canopy_style == "willow_hanging":
            dy = -branch_len * 0.4  # Droop down
        elif canopy_style == "veil_blighted":
            dy = branch_len * 0.1
            dx *= 1.15
            dz *= 1.15
        elif canopy_style == "veil_boundary":
            dy = branch_len * 0.18
            dx *= 1.05
            dz *= 1.05

        # Branch as tapered cylinder segments
        n_seg = 4
        for s in range(n_seg):
            s_t = s / n_seg
            s_t2 = (s + 1) / n_seg
            x1 = dx * s_t
            y1 = y + dy * s_t
            z1 = dz * s_t
            x2 = dx * s_t2
            y2 = y + dy * s_t2
            z2 = dz * s_t2
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            mid_z = (z1 + z2) / 2
            seg_len = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
            seg_r = branch_r * (1.0 - s_t2 * 0.7)
            bv, bf = _make_cylinder(
                mid_x, mid_y - seg_len / 2, mid_z,
                max(seg_r, 0.005), seg_len, segments=6,
                cap_top=(s == n_seg - 1), cap_bottom=(s == 0),
            )
            parts.append((bv, bf))

    # Canopy
    if canopy_style == "ancient_oak":
        # Large irregular canopy blobs
        canopy_y = trunk_height * 0.85
        for i in range(5):
            angle = 2.0 * math.pi * i / 5
            ox = math.cos(angle) * trunk_height * 0.25
            oz = math.sin(angle) * trunk_height * 0.25
            oy = canopy_y + (i % 2) * trunk_height * 0.1
            cr = trunk_height * 0.2
            cv, cf = _make_sphere(ox, oy, oz, cr, rings=7, sectors=10)
            parts.append((cv, cf))
        # Central canopy mass
        cv, cf = _make_sphere(0, canopy_y + 0.1, 0, trunk_height * 0.25, rings=8, sectors=12)
        parts.append((cv, cf))

    elif canopy_style == "dark_pine":
        # Conical layered canopy
        canopy_base = trunk_height * 0.3
        canopy_top = trunk_height * 1.1
        layers = 5
        for i in range(layers):
            t = i / layers
            layer_y = canopy_base + t * (canopy_top - canopy_base)
            layer_r = trunk_height * 0.3 * (1.0 - t * 0.8)
            layer_h = (canopy_top - canopy_base) / layers * 0.6
            cv, cf = _make_cone(0, layer_y, 0, layer_r, layer_h, segments=8)
            parts.append((cv, cf))

    elif canopy_style == "dead_twisted":
        # No canopy, just twisted branch tips (already generated above)
        pass

    elif canopy_style == "veil_healthy":
        canopy_y = trunk_height * 0.82
        ring_offsets = (
            (0.00, 0.00, trunk_height * 0.30),
            (0.22, 0.08, trunk_height * 0.23),
            (-0.24, 0.02, trunk_height * 0.20),
            (0.10, -0.26, trunk_height * 0.19),
            (-0.12, 0.25, trunk_height * 0.18),
            (0.00, 0.18, trunk_height * 0.16),
        )
        for ox_mul, oz_mul, radius in ring_offsets:
            cv, cf = _make_sphere(
                ox_mul * trunk_height,
                canopy_y + abs(ox_mul) * trunk_height * 0.12,
                oz_mul * trunk_height,
                radius,
                rings=8,
                sectors=12,
            )
            parts.append((cv, cf))

    elif canopy_style == "veil_boundary":
        canopy_y = trunk_height * 0.78
        cluster_specs = (
            (0.18, 0.00, trunk_height * 0.18),
            (-0.18, 0.12, trunk_height * 0.16),
            (0.08, -0.18, trunk_height * 0.14),
        )
        for ox_mul, oz_mul, radius in cluster_specs:
            cv, cf = _make_sphere(
                ox_mul * trunk_height,
                canopy_y + (0.06 if ox_mul > 0 else -0.02) * trunk_height,
                oz_mul * trunk_height,
                radius,
                rings=6,
                sectors=10,
            )
            parts.append((cv, cf))
        # Sparse hanging masses so the boundary forest reads sickly, not dead.
        for i in range(6):
            angle = 2.0 * math.pi * i / 6
            ox = math.cos(angle) * trunk_height * 0.14
            oz = math.sin(angle) * trunk_height * 0.14
            sv, sf = _make_box(
                ox,
                canopy_y - trunk_height * 0.14,
                oz,
                0.03,
                trunk_height * 0.12,
                0.01,
            )
            parts.append((sv, sf))

    elif canopy_style == "veil_blighted":
        canopy_y = trunk_height * 0.72
        for ox, oz, radius in (
            (0.12, 0.00, trunk_height * 0.09),
            (-0.08, 0.10, trunk_height * 0.07),
        ):
            cv, cf = _make_sphere(
                ox * trunk_height,
                canopy_y,
                oz * trunk_height,
                radius,
                rings=5,
                sectors=9,
            )
            parts.append((cv, cf))
        for i in range(4):
            angle = 2.0 * math.pi * i / 4 + 0.4
            ox = math.cos(angle) * trunk_height * 0.18
            oz = math.sin(angle) * trunk_height * 0.18
            sv, sf = _make_box(
                ox,
                canopy_y - trunk_height * 0.10,
                oz,
                0.02,
                trunk_height * 0.10,
                0.008,
            )
            parts.append((sv, sf))

    elif canopy_style == "willow_hanging":
        # Drooping curtain of leaf strips
        canopy_y = trunk_height * 0.75
        for i in range(12):
            angle = 2.0 * math.pi * i / 12
            ox = math.cos(angle) * trunk_height * 0.2
            oz = math.sin(angle) * trunk_height * 0.2
            # Thin hanging strip
            sv, sf = _make_box(
                ox, canopy_y - trunk_height * 0.2, oz,
                0.02, trunk_height * 0.2, 0.005,
            )
            parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Tree_{canopy_style}", verts, faces,
                        style=canopy_style, category="vegetation")


def generate_rock_mesh(
    rock_type: str = "boulder",
    size: float = 1.0,
    detail: int = 3,
) -> MeshSpec:
    """Generate a rock mesh with irregular surface.

    Args:
        rock_type: "boulder", "standing_stone", "crystal", or "rubble_pile".
        size: Scale factor.
        detail: Detail level (1-5), affects ring/sector counts.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    detail = max(1, min(5, detail))
    parts = []

    if rock_type == "boulder":
        verts, faces = _make_faceted_rock_shell(
            size,
            detail,
            seed=1701 + detail * 97 + int(size * 1000),
            height_scale=1.0,
            width_scale=1.0,
            depth_scale=0.92,
            flat_base=True,
            flat_top=True,
        )
        return _make_result("Rock_boulder", verts, faces,
                            rock_type=rock_type, category="vegetation")

    elif rock_type == "cliff_outcrop":
        import random as _rng

        rng = _rng.Random(9127 + detail * 131 + int(size * 1000))
        layers = 3 + detail
        base_width = 0.95 * size
        base_depth = 0.58 * size
        total_height = 1.15 * size

        y_cursor = -total_height * 0.5
        for layer_idx in range(layers):
            t = layer_idx / max(layers - 1, 1)
            layer_height = total_height * (0.18 + 0.10 * ((layer_idx + 1) % 2)) * (1.0 - t * 0.15)
            layer_width = base_width * (1.0 - t * 0.24 + rng.uniform(-0.04, 0.04))
            layer_depth = base_depth * (1.0 - t * 0.28 + rng.uniform(-0.05, 0.05))
            x_off = rng.uniform(-0.08, 0.08) * size
            z_off = rng.uniform(-0.06, 0.06) * size
            y_center = y_cursor + layer_height * 0.5

            slab_v, slab_f = _make_beveled_box(
                x_off,
                y_center,
                z_off,
                layer_width * 0.5,
                layer_height * 0.5,
                layer_depth * 0.5,
                bevel=max(0.01, min(layer_width, layer_height, layer_depth) * 0.08),
            )
            parts.append((slab_v, slab_f))
            y_cursor += layer_height * 0.88

        fin_v, fin_f = _make_beveled_box(
            size * 0.18,
            total_height * 0.18,
            -size * 0.10,
            size * 0.20,
            total_height * 0.12,
            size * 0.08,
            bevel=max(0.004, size * 0.02),
        )
        parts.append((fin_v, fin_f))

        for _ in range(2):
            ox = rng.uniform(-0.25, 0.25) * size
            oz = rng.uniform(-0.18, 0.18) * size
            oy = -total_height * 0.45 + rng.uniform(0.0, 0.12) * size
            rv, rf = _make_beveled_box(
                ox,
                oy,
                oz,
                size * rng.uniform(0.12, 0.18),
                size * rng.uniform(0.05, 0.09),
                size * rng.uniform(0.10, 0.16),
                bevel=max(0.003, size * 0.01),
            )
            parts.append((rv, rf))

        verts, faces = _merge_meshes(*parts)
        return _make_result("Rock_cliff_outcrop", verts, faces,
                            rock_type=rock_type, category="vegetation")

    elif rock_type == "standing_stone":
        # Tall irregular column
        profile: list[tuple[float, float]] = []
        h = 1.5 * size
        base_r = 0.3 * size
        _rng_ss = __import__("random")
        rng = _rng_ss.Random(77)
        ring_count = 8 + detail * 2
        for i in range(ring_count + 1):
            t = i / ring_count
            y = t * h
            # Taper toward top with noise
            r = base_r * (1.0 - t * 0.4) * (1.0 + rng.uniform(-0.08, 0.08))
            profile.append((max(r, 0.02), y))

        sv, sf = _make_lathe(profile, segments=6 + detail, close_bottom=True, close_top=True)
        return _make_result("Rock_standing_stone", sv, sf,
                            rock_type=rock_type, category="vegetation")

    elif rock_type == "crystal":
        # Hexagonal crystal cluster
        import random as _rng
        rng = _rng.Random(99)
        for c in range(3 + detail):
            cx = rng.uniform(-0.15, 0.15) * size
            cz = rng.uniform(-0.15, 0.15) * size
            crystal_h = rng.uniform(0.3, 0.7) * size
            crystal_r = rng.uniform(0.04, 0.1) * size
            # Hexagonal prism with pointed top
            cv, cf = _make_tapered_cylinder(
                cx, 0, cz,
                crystal_r, crystal_r * 0.3,
                crystal_h, segments=6, rings=2,
                cap_top=True, cap_bottom=True,
            )
            parts.append((cv, cf))

        verts, faces = _merge_meshes(*parts)
        return _make_result("Rock_crystal", verts, faces,
                            rock_type=rock_type, category="vegetation")

    else:  # rubble_pile
        import random as _rng
        rng = _rng.Random(55)
        count = 5 + detail * 3
        for _ in range(count):
            rx = rng.uniform(-0.3, 0.3) * size
            rz = rng.uniform(-0.3, 0.3) * size
            ry = rng.uniform(0, 0.15) * size
            rs = rng.uniform(0.03, 0.12) * size
            # Small irregular boxes
            rv, rf = _make_beveled_box(
                rx, ry + rs, rz,
                rs * rng.uniform(0.7, 1.3),
                rs * rng.uniform(0.5, 1.0),
                rs * rng.uniform(0.7, 1.3),
                bevel=rs * 0.15,
            )
            parts.append((rv, rf))

        verts, faces = _merge_meshes(*parts)
        return _make_result("Rock_rubble_pile", verts, faces,
                            rock_type=rock_type, category="vegetation")


def generate_mushroom_mesh(
    size: float = 0.5,
    cap_style: str = "giant_cap",
) -> MeshSpec:
    """Generate a mushroom mesh.

    Args:
        size: Scale factor.
        cap_style: "giant_cap", "cluster", or "shelf_fungus".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 12

    if cap_style == "giant_cap":
        # Single large mushroom
        stem_h = 0.4 * size
        stem_r = 0.04 * size

        # Stem with slight bulge
        stem_profile = [
            (stem_r * 1.3, 0),
            (stem_r, stem_h * 0.1),
            (stem_r * 0.9, stem_h * 0.5),
            (stem_r * 1.1, stem_h * 0.8),
            (stem_r * 1.2, stem_h),
        ]
        sv, sf = _make_lathe(stem_profile, segments=segs, close_bottom=True)
        parts.append((sv, sf))

        # Cap (dome)
        cap_r = 0.2 * size
        cap_h = 0.12 * size
        cap_profile = [
            (cap_r * 1.05, stem_h - 0.01 * size),
            (cap_r, stem_h),
            (cap_r * 0.95, stem_h + cap_h * 0.3),
            (cap_r * 0.8, stem_h + cap_h * 0.6),
            (cap_r * 0.5, stem_h + cap_h * 0.85),
            (cap_r * 0.15, stem_h + cap_h),
            (0.001, stem_h + cap_h * 1.02),
        ]
        cv, cf = _make_lathe(cap_profile, segments=segs)
        parts.append((cv, cf))

        # Gill ring under cap
        gill_profile = [
            (cap_r * 0.3, stem_h - 0.005 * size),
            (cap_r * 0.9, stem_h - 0.01 * size),
        ]
        gv, gf = _make_lathe(gill_profile, segments=segs)
        parts.append((gv, gf))

    elif cap_style == "cluster":
        # Multiple small mushrooms
        import random as _rng
        rng = _rng.Random(33)
        cluster_count = 5
        for _ in range(cluster_count):
            ox = rng.uniform(-0.1, 0.1) * size
            oz = rng.uniform(-0.1, 0.1) * size
            s = rng.uniform(0.3, 0.8) * size
            sh = 0.2 * s
            sr = 0.02 * s

            # Small stem
            sv, sf = _make_cylinder(ox, 0, oz, sr, sh, segments=6)
            parts.append((sv, sf))
            # Small cap
            cv, cf = _make_cone(ox, sh, oz, 0.06 * s, 0.04 * s, segments=6)
            parts.append((cv, cf))

    else:  # shelf_fungus
        # Shelf bracket growing from a surface
        shelf_count = 3
        for i in range(shelf_count):
            y = i * 0.08 * size
            shelf_r = (0.12 - i * 0.02) * size
            shelf_thick = 0.015 * size
            # Half-disc shelf
            shelf_verts: list[tuple[float, float, float]] = []
            shelf_faces: list[tuple[int, ...]] = []
            n_pts = 8

            # Top surface
            shelf_verts.append((0, y + shelf_thick, 0))  # center
            for j in range(n_pts):
                angle = math.pi * j / (n_pts - 1)
                shelf_verts.append((
                    math.cos(angle) * shelf_r,
                    y + shelf_thick,
                    math.sin(angle) * shelf_r,
                ))

            # Bottom surface
            shelf_verts.append((0, y, 0))  # center
            for j in range(n_pts):
                angle = math.pi * j / (n_pts - 1)
                shelf_verts.append((
                    math.cos(angle) * shelf_r,
                    y,
                    math.sin(angle) * shelf_r,
                ))

            # Top fan
            for j in range(n_pts - 1):
                shelf_faces.append((0, j + 1, j + 2))
            # Bottom fan
            center2 = n_pts + 1
            for j in range(n_pts - 1):
                shelf_faces.append((center2, center2 + j + 2, center2 + j + 1))
            # Rim
            for j in range(n_pts - 1):
                t = j + 1
                b_idx = center2 + j + 1
                t2 = j + 2
                b2 = center2 + j + 2
                shelf_faces.append((t, b_idx, b2, t2))

            parts.append((shelf_verts, shelf_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Mushroom_{cap_style}", verts, faces,
                        style=cap_style, category="vegetation")


def generate_root_mesh(
    spread: float = 1.5,
    thickness: float = 0.08,
    segments: int = 5,
) -> MeshSpec:
    """Generate exposed tree root meshes.

    Args:
        spread: How far roots spread from centre.
        thickness: Root thickness at base.
        segments: Number of root tendrils.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs_circ = 6

    for i in range(segments):
        angle = 2.0 * math.pi * i / segments + (i * 0.2)
        length = spread * (0.6 + 0.4 * ((i * 7 + 3) % segments) / segments)

        # Root profile tapering along its length
        root_pts = 8
        for s in range(root_pts):
            t = s / root_pts
            x = math.cos(angle) * length * t
            z = math.sin(angle) * length * t
            # Roots dip down then come back up
            y = -thickness * 2 * math.sin(t * math.pi) * (1.0 - t * 0.3)
            r = thickness * (1.0 - t * 0.8)

            if s < root_pts - 1:
                cv, cf = _make_cylinder(
                    x, y - r, z,
                    max(r, 0.005), r * 2,
                    segments=segs_circ,
                    cap_top=(s == root_pts - 2),
                    cap_bottom=(s == 0),
                )
                parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Roots", verts, faces, category="vegetation")


def generate_grass_clump_mesh(
    blade_count: int = 14,
    height: float = 0.7,
    spread: float = 0.22,
    width: float = 0.045,
) -> MeshSpec:
    """Generate a reusable grass clump mesh for terrain scatter.

    Uses crossed quad-like blades with mild bend variation. This remains
    lightweight enough for instancing but avoids the flat grid-plane fallback.
    """
    import random as _rng

    rng = _rng.Random(211)
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for blade_idx in range(max(6, blade_count)):
        angle = (2.0 * math.pi * blade_idx / max(blade_count, 1)) + rng.uniform(-0.25, 0.25)
        base_r = rng.uniform(0.0, spread)
        cx = math.cos(angle) * base_r
        cz = math.sin(angle) * base_r
        blade_h = height * rng.uniform(0.72, 1.18)
        blade_w = width * rng.uniform(0.65, 1.25)
        bend = rng.uniform(-0.18, 0.18)
        lean_x = math.cos(angle + bend) * blade_h * 0.10
        lean_z = math.sin(angle + bend) * blade_h * 0.10
        twist = angle + math.pi * 0.5
        dx = math.cos(twist) * blade_w * 0.5
        dz = math.sin(twist) * blade_w * 0.5

        base_idx = len(vertices)
        vertices.extend([
            (cx - dx, 0.0, cz - dz),
            (cx + dx, 0.0, cz + dz),
            (cx + dx * 0.28 + lean_x, blade_h, cz + dz * 0.28 + lean_z),
            (cx - dx * 0.28 + lean_x, blade_h, cz - dz * 0.28 + lean_z),
        ])
        faces.append((base_idx, base_idx + 1, base_idx + 2, base_idx + 3))

    return _make_result(
        "GrassClump",
        vertices,
        faces,
        category="vegetation",
        style="grass_clump",
    )


def generate_shrub_mesh(
    radius: float = 0.45,
    height: float = 0.7,
    cluster_count: int = 6,
) -> MeshSpec:
    """Generate a dense shrub mesh with a woody core and leaf masses."""
    import random as _rng

    rng = _rng.Random(313)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    stem_v, stem_f = _make_tapered_cylinder(
        0.0,
        0.0,
        0.0,
        radius * 0.12,
        radius * 0.05,
        height * 0.45,
        segments=7,
        rings=2,
    )
    parts.append((stem_v, stem_f))

    for idx in range(max(4, cluster_count)):
        angle = 2.0 * math.pi * idx / max(cluster_count, 1) + rng.uniform(-0.28, 0.28)
        dist = radius * rng.uniform(0.18, 0.78)
        ox = math.cos(angle) * dist
        oz = math.sin(angle) * dist
        oy = height * rng.uniform(0.35, 0.88)
        blob_r = radius * rng.uniform(0.34, 0.58)
        blob_v, blob_f = _make_sphere(ox, oy, oz, blob_r, rings=5, sectors=8)
        parts.append((blob_v, blob_f))

    root_count = 4
    for idx in range(root_count):
        angle = 2.0 * math.pi * idx / root_count + rng.uniform(-0.2, 0.2)
        rv, rf = _make_cone(
            math.cos(angle) * radius * 0.16,
            0.03,
            math.sin(angle) * radius * 0.16,
            radius * 0.05,
            radius * 0.26,
            segments=4,
        )
        root_verts = [(vx, max(vy - radius * 0.08, 0.0), vz) for vx, vy, vz in rv]
        parts.append((root_verts, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        "Shrub",
        verts,
        faces,
        category="vegetation",
        style="shrub",
    )


def generate_ivy_mesh(
    length: float = 2.0,
    density: int = 5,
) -> MeshSpec:
    """Generate wall-climbing ivy strips.

    Args:
        length: Length of ivy growth.
        density: Number of vine strands.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    import random as _rng
    rng = _rng.Random(71)

    for strand in range(density):
        x_offset = rng.uniform(-0.3, 0.3)
        strand_len = length * rng.uniform(0.6, 1.0)
        vine_segs = 10
        vine_r = 0.005

        # Vine stem (series of small cylinders climbing up)
        for s in range(vine_segs):
            t = s / vine_segs
            y = t * strand_len
            x = x_offset + math.sin(t * 4 + strand) * 0.05
            z = 0.005  # Close to wall
            seg_h = strand_len / vine_segs
            cv, cf = _make_cylinder(
                x, y, z, vine_r, seg_h, segments=4,
                cap_top=False, cap_bottom=False,
            )
            parts.append((cv, cf))

            # Leaves at intervals
            if s % 2 == 0:
                leaf_size = rng.uniform(0.02, 0.04)
                lx = x + rng.choice([-1, 1]) * 0.03
                # Leaf as small diamond quad
                leaf_verts = [
                    (lx, y + leaf_size, z + 0.01),
                    (lx + leaf_size * 0.6, y + leaf_size * 0.5, z + 0.01),
                    (lx, y, z + 0.01),
                    (lx - leaf_size * 0.6, y + leaf_size * 0.5, z + 0.01),
                ]
                leaf_faces = [(0, 1, 2, 3)]
                parts.append((leaf_verts, leaf_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Ivy", verts, faces, category="vegetation")


# =========================================================================
# CATEGORY 3: DUNGEON PROPS
# =========================================================================


def generate_torch_sconce_mesh(
    style: str = "iron_bracket",
) -> MeshSpec:
    """Generate a wall-mounted torch holder.

    Args:
        style: "iron_bracket", "ornate_dragon", or "simple_ring".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 8

    # Wall plate
    plate_v, plate_f = _make_beveled_box(
        0, 0, -0.01,
        0.04, 0.06, 0.005,
        bevel=0.003,
    )
    parts.append((plate_v, plate_f))

    if style == "iron_bracket":
        # L-shaped bracket arm
        arm_v, arm_f = _make_box(0, 0, 0.06, 0.015, 0.015, 0.06)
        parts.append((arm_v, arm_f))
        # Torch cup at end
        cup_profile = [
            (0.025, -0.035),
            (0.03, -0.02),
            (0.035, 0),
            (0.033, 0.01),
            (0.028, 0.015),
        ]
        cv, cf = _make_lathe(cup_profile, segments=segs)
        # Offset to end of arm
        cv = [(v[0], v[1], v[2] + 0.12) for v in cv]
        parts.append((cv, cf))

    elif style == "ornate_dragon":
        # Curved arm
        arm_pts = 8
        for i in range(arm_pts):
            t = i / arm_pts
            y = 0.02 * math.sin(t * math.pi)
            z = t * 0.12
            r = 0.012
            cv, cf = _make_cylinder(0, y - r, z, r, r * 2, segments=6,
                                    cap_top=False, cap_bottom=False)
            parts.append((cv, cf))
        # Dragon head cup
        dv, df = _make_sphere(0, 0.02, 0.13, 0.025, rings=4, sectors=6)
        parts.append((dv, df))

    else:  # simple_ring
        # Ring holder
        rv, rf = _make_torus_ring(0, 0, 0.08, 0.03, 0.006,
                                  major_segments=8, minor_segments=4)
        parts.append((rv, rf))

    # Torch shaft
    tv, tf = _make_tapered_cylinder(0, 0.02, 0.12, 0.012, 0.008, 0.2, segs, rings=2)
    parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("TorchSconce", verts, faces, style=style, category="dungeon_prop")


def generate_prison_door_mesh(
    width: float = 1.0,
    height: float = 2.0,
    bar_count: int = 5,
) -> MeshSpec:
    """Generate an iron-barred prison door.

    Args:
        width: Door width.
        height: Door height.
        bar_count: Number of vertical bars.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bar_r = 0.015
    bar_segs = 6

    # Frame
    frame_thick = 0.04
    # Left post
    lv, lf = _make_beveled_box(
        -width / 2, height / 2, 0,
        frame_thick / 2, height / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((lv, lf))
    # Right post
    rv, rf = _make_beveled_box(
        width / 2, height / 2, 0,
        frame_thick / 2, height / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((rv, rf))
    # Top bar
    tv, tf = _make_beveled_box(
        0, height, 0,
        width / 2 + frame_thick / 2, frame_thick / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((tv, tf))
    # Bottom bar
    bv, bf = _make_beveled_box(
        0, 0, 0,
        width / 2 + frame_thick / 2, frame_thick / 2, frame_thick / 2,
        bevel=0.005,
    )
    parts.append((bv, bf))

    # Vertical bars
    inner_w = width - frame_thick
    for i in range(bar_count):
        x = -inner_w / 2 + inner_w * (i + 1) / (bar_count + 1)
        bv, bf = _make_cylinder(
            x, frame_thick, 0,
            bar_r, height - frame_thick * 2,
            segments=bar_segs,
        )
        parts.append((bv, bf))

    # Horizontal cross bars
    for y_pos in [height * 0.33, height * 0.66]:
        hv, hf = _make_cylinder(
            -inner_w / 2, y_pos, 0,
            bar_r * 0.8, inner_w,
            segments=bar_segs,
        )
        # Rotate to horizontal -- approximate by placing along X
        h_verts = [(v[1] - y_pos + (-inner_w / 2), y_pos, v[2]) for v in hv]
        parts.append((h_verts, hf))

    # Lock plate
    lv, lf = _make_beveled_box(
        width * 0.3, height * 0.45, 0.02,
        0.03, 0.04, 0.01,
        bevel=0.003,
    )
    parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("PrisonDoor", verts, faces, category="dungeon_prop")


def generate_sarcophagus_mesh(
    style: str = "stone_plain",
) -> MeshSpec:
    """Generate a stone sarcophagus (coffin) mesh.

    Args:
        style: "stone_plain", "ornate_carved", or "dark_ritual".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    w = 0.5
    h = 0.4
    d = 1.0

    # Main body (tapered slightly)
    body_profile = [
        (0, 0),
        (w * 0.45, 0),
        (w * 0.5, h * 0.1),
        (w * 0.5, h * 0.7),
        (w * 0.48, h * 0.8),
        (w * 0.4, h * 0.85),
    ]
    bv, bf = _make_profile_extrude(body_profile, d)
    parts.append((bv, bf))
    # Mirror for other side
    bv2 = [(-v[0], v[1], v[2]) for v in bv]
    bf2_r = [tuple(reversed(f)) for f in bf]
    parts.append((bv2, bf2_r))

    # Lid (slightly wider, with peaked top)
    lid_profile = [
        (w * 0.52, h * 0.85),
        (w * 0.52, h * 0.95),
        (w * 0.3, h * 1.1),
        (0, h * 1.15),
    ]
    lv, lf = _make_profile_extrude(lid_profile, d * 1.02)
    parts.append((lv, lf))
    lv2 = [(-v[0], v[1], v[2]) for v in lv]
    lf2_r = [tuple(reversed(f)) for f in lf]
    parts.append((lv2, lf2_r))

    if style == "ornate_carved":
        # Corner posts
        for xoff, zoff in [(w * 0.45, d * 0.45), (w * 0.45, -d * 0.45),
                           (-w * 0.45, d * 0.45), (-w * 0.45, -d * 0.45)]:
            cv, cf = _make_cylinder(xoff, 0, zoff, 0.03, h * 1.2, segments=6)
            parts.append((cv, cf))
            # Decorative sphere cap
            sv, sf = _make_sphere(xoff, h * 1.22, zoff, 0.035, rings=4, sectors=6)
            parts.append((sv, sf))

    elif style == "dark_ritual":
        # Rune channels (grooves along the sides as thin raised strips)
        for i in range(4):
            z = -d * 0.3 + i * d * 0.2
            rv, rf = _make_box(w * 0.52, h * 0.4, z, 0.005, h * 0.2, 0.02)
            parts.append((rv, rf))
            rv2, rf2 = _make_box(-w * 0.52, h * 0.4, z, 0.005, h * 0.2, 0.02)
            parts.append((rv2, rf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Sarcophagus_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_altar_mesh(
    style: str = "sacrificial",
) -> MeshSpec:
    """Generate an altar mesh.

    Args:
        style: "sacrificial", "prayer", or "dark_ritual".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "sacrificial":
        # Large stone slab on pillars
        slab_w, slab_h, slab_d = 1.2, 0.1, 0.7
        slab_y = 0.9
        sv, sf = _make_beveled_box(0, slab_y, 0, slab_w / 2, slab_h / 2, slab_d / 2,
                                   bevel=0.015)
        parts.append((sv, sf))

        # Blood channel groove on top (raised rim)
        rv, rf = _make_box(0, slab_y + slab_h / 2 + 0.01, 0,
                           slab_w * 0.4, 0.01, slab_d * 0.35)
        parts.append((rv, rf))

        # Four thick stone legs
        leg_r = 0.1
        for xoff, zoff in [(-0.4, 0.2), (0.4, 0.2), (-0.4, -0.2), (0.4, -0.2)]:
            lv, lf = _make_tapered_cylinder(xoff, 0, zoff, leg_r * 1.1, leg_r,
                                            slab_y - slab_h / 2, 8, rings=3)
            parts.append((lv, lf))

    elif style == "prayer":
        # Simple stone block with kneeling step
        main_w, main_h, main_d = 0.6, 0.8, 0.4
        mv, mf = _make_beveled_box(0, main_h / 2, 0, main_w / 2, main_h / 2, main_d / 2,
                                   bevel=0.01)
        parts.append((mv, mf))

        # Step in front
        step_v, step_f = _make_beveled_box(0, 0.08, main_d / 2 + 0.15,
                                           main_w * 0.4, 0.08, 0.12,
                                           bevel=0.008)
        parts.append((step_v, step_f))

        # Symbol on top (small raised disc)
        dv, df = _make_cylinder(0, main_h + 0.005, 0, 0.08, 0.01, segments=12)
        parts.append((dv, df))

    else:  # dark_ritual
        # Octagonal dark altar with rune pillars
        profile = [
            (0.5, 0),
            (0.52, 0.05),
            (0.52, 0.15),
            (0.48, 0.2),
            (0.45, 0.6),
            (0.5, 0.65),
            (0.55, 0.7),
        ]
        av, af = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
        parts.append((av, af))

        # Corner pillars
        for i in range(4):
            angle = math.pi / 4 + i * math.pi / 2
            px = math.cos(angle) * 0.7
            pz = math.sin(angle) * 0.7
            pv, pf = _make_tapered_cylinder(px, 0, pz, 0.04, 0.03, 1.0, 6, rings=3)
            parts.append((pv, pf))
            # Flame cup at top
            fv, ff = _make_cone(px, 1.0, pz, 0.05, 0.04, segments=6)
            parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Altar_{style}", verts, faces, style=style, category="dungeon_prop")


def generate_pillar_mesh(
    style: str = "stone_round",
    height: float = 3.0,
    radius: float = 0.2,
) -> MeshSpec:
    """Generate a pillar/column mesh.

    Args:
        style: "stone_round", "stone_square", "carved_serpent", "wooden", or "broken".
        height: Pillar height.
        radius: Pillar radius.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "stone_round":
        # Classical column with base and capital
        # Base (wider disc)
        base_profile = [
            (radius * 1.5, 0),
            (radius * 1.5, height * 0.02),
            (radius * 1.3, height * 0.03),
            (radius * 1.1, height * 0.05),
        ]
        bv, bf = _make_lathe(base_profile, segments=16, close_bottom=True)
        parts.append((bv, bf))

        # Shaft with entasis (slight mid-bulge)
        shaft_profile = []
        shaft_rings = 12
        for i in range(shaft_rings + 1):
            t = i / shaft_rings
            y = height * 0.05 + t * height * 0.85
            # Entasis: slight outward curve
            entasis = 1.0 + 0.03 * math.sin(t * math.pi)
            r = radius * entasis
            shaft_profile.append((r, y))
        sv, sf = _make_lathe(shaft_profile, segments=16)
        parts.append((sv, sf))

        # Capital (wider top)
        cap_profile = [
            (radius * 1.1, height * 0.9),
            (radius * 1.3, height * 0.93),
            (radius * 1.5, height * 0.96),
            (radius * 1.5, height),
        ]
        cv, cf = _make_lathe(cap_profile, segments=16, close_top=True)
        parts.append((cv, cf))

    elif style == "stone_square":
        # Square column with chamfered edges
        # Base
        bv, bf = _make_beveled_box(
            0, height * 0.025, 0,
            radius * 1.4, height * 0.025, radius * 1.4,
            bevel=0.01,
        )
        parts.append((bv, bf))
        # Shaft
        sv, sf = _make_beveled_box(
            0, height * 0.5, 0,
            radius, height * 0.45, radius,
            bevel=0.015,
        )
        parts.append((sv, sf))
        # Capital
        cv, cf = _make_beveled_box(
            0, height * 0.975, 0,
            radius * 1.4, height * 0.025, radius * 1.4,
            bevel=0.01,
        )
        parts.append((cv, cf))

    elif style == "wooden":
        # Rough wooden post with grain ridges
        shaft_profile = []
        shaft_rings = 16
        for i in range(shaft_rings + 1):
            t = i / shaft_rings
            y = t * height
            # Wood grain creates slight irregularity
            grain = 1.0 + 0.02 * math.sin(t * 12.0 * math.pi)
            r = radius * 0.9 * grain
            shaft_profile.append((r, y))
        sv, sf = _make_lathe(shaft_profile, segments=8, close_bottom=True, close_top=True)
        parts.append((sv, sf))

        # Cross braces near top and bottom
        for brace_y in [height * 0.15, height * 0.85]:
            for angle_off in [0, math.pi / 2]:
                bx = math.cos(angle_off) * radius * 0.02
                bz = math.sin(angle_off) * radius * 0.02
                bv, bf = _make_box(bx, brace_y, bz,
                                   radius * 1.2, 0.015, 0.015)
                parts.append((bv, bf))

    elif style == "broken":
        # Truncated column with rubble at the break point
        break_h = height * 0.55
        # Base (wider disc)
        base_profile = [
            (radius * 1.5, 0),
            (radius * 1.5, height * 0.02),
            (radius * 1.3, height * 0.03),
            (radius * 1.1, height * 0.05),
        ]
        bv, bf = _make_lathe(base_profile, segments=12, close_bottom=True)
        parts.append((bv, bf))

        # Truncated shaft
        shaft_profile = []
        shaft_rings = 8
        for i in range(shaft_rings + 1):
            t = i / shaft_rings
            y = height * 0.05 + t * (break_h - height * 0.05)
            entasis = 1.0 + 0.03 * math.sin(t * math.pi)
            r = radius * entasis
            shaft_profile.append((r, y))
        sv, sf = _make_lathe(shaft_profile, segments=12, close_top=True)
        parts.append((sv, sf))

        # Rubble chunks at the break point
        import random as _rng_pillar
        rng = _rng_pillar.Random(77)
        for _ in range(6):
            rx = rng.uniform(-radius * 1.5, radius * 1.5)
            rz = rng.uniform(-radius * 1.5, radius * 1.5)
            ry = break_h + rng.uniform(-0.05, 0.1)
            rs = rng.uniform(radius * 0.15, radius * 0.4)
            rv, rf = _make_beveled_box(rx, ry, rz, rs, rs * 0.7, rs * 0.8, bevel=0.005)
            parts.append((rv, rf))

        # Fallen chunk on the ground nearby
        fv, ff = _make_beveled_box(radius * 2.0, radius * 0.4, 0,
                                   radius * 0.6, radius * 0.4, radius * 0.5,
                                   bevel=0.008)
        parts.append((fv, ff))

    else:  # carved_serpent
        # Round column with spiral carved groove
        profile = []
        rings = 24
        for i in range(rings + 1):
            t = i / rings
            y = t * height
            # Serpent wrapping creates periodic radius variation
            serpent_phase = t * 4 * math.pi
            r = radius * (1.0 + 0.08 * math.sin(serpent_phase))
            profile.append((r, y))

        sv, sf = _make_lathe(profile, segments=12, close_bottom=True, close_top=True)
        parts.append((sv, sf))

        # Base and capital
        bv, bf = _make_cylinder(0, -0.02, 0, radius * 1.4, 0.04, segments=12)
        parts.append((bv, bf))
        cv, cf = _make_cylinder(0, height - 0.02, 0, radius * 1.4, 0.04, segments=12)
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Pillar_{style}", verts, faces, style=style, category="dungeon_prop")


def generate_archway_mesh(
    width: float = 1.5,
    height: float = 2.5,
    depth: float = 0.4,
    style: str = "stone_round",
) -> MeshSpec:
    """Generate a doorway/passage archway frame.

    Args:
        width: Opening width.
        height: Total height (arch peak).
        depth: Wall thickness.
        style: "stone_round", "stone_pointed", "wooden", or "ruined".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    post_w = 0.2
    arch_segs = 12

    # Left post
    lv, lf = _make_beveled_box(
        -width / 2 - post_w / 2, height * 0.4, 0,
        post_w / 2, height * 0.4, depth / 2,
        bevel=0.01,
    )
    parts.append((lv, lf))

    # Right post
    rv, rf = _make_beveled_box(
        width / 2 + post_w / 2, height * 0.4, 0,
        post_w / 2, height * 0.4, depth / 2,
        bevel=0.01,
    )
    parts.append((rv, rf))

    if style == "stone_pointed":
        # Gothic pointed arch
        arch_inner_r = width / 2
        arch_outer_r = arch_inner_r + post_w
        spring_y = height * 0.55
        peak_y = height

        arch_verts: list[tuple[float, float, float]] = []
        arch_faces: list[tuple[int, ...]] = []

        for i in range(arch_segs + 1):
            t = i / arch_segs
            # Pointed arch: two arcs meeting at apex
            if t <= 0.5:
                s = t * 2.0
                ix = -width / 2 + s * width * 0.1
                iy = spring_y + s * (peak_y - spring_y)
                ox = ix - post_w * (1.0 - s * 0.6)
                oy = iy + post_w * 0.3
            else:
                s = (t - 0.5) * 2.0
                ix = -width * 0.4 + s * (width / 2 + width * 0.4)
                iy = spring_y + (1.0 - s) * (peak_y - spring_y)
                ox = ix + post_w * (1.0 - (1.0 - s) * 0.6)
                oy = iy + post_w * 0.3

            arch_verts.append((ix, iy, -depth / 2))
            arch_verts.append((ox, oy, -depth / 2))
            arch_verts.append((ix, iy, depth / 2))
            arch_verts.append((ox, oy, depth / 2))

        for i in range(arch_segs):
            b = i * 4
            arch_faces.append((b + 1, b + 5, b + 4, b + 0))
            arch_faces.append((b + 2, b + 6, b + 7, b + 3))
            arch_faces.append((b + 1, b + 3, b + 7, b + 5))
            arch_faces.append((b + 0, b + 4, b + 6, b + 2))

        parts.append((arch_verts, arch_faces))

        # Pointed keystone
        kv, kf = _make_beveled_box(
            0, peak_y + 0.02, 0,
            post_w * 0.35, post_w * 0.4, depth / 2 + 0.01,
            bevel=0.006,
        )
        parts.append((kv, kf))

    elif style == "wooden":
        # Simple wooden lintel arch (flat top beam)
        lintel_y = height * 0.8
        # Extend posts to full height
        for x_side in [-width / 2 - post_w / 2, width / 2 + post_w / 2]:
            pv, pf = _make_box(x_side, lintel_y / 2, 0,
                               post_w * 0.4, lintel_y / 2, depth * 0.4)
            parts.append((pv, pf))

        # Horizontal lintel beam
        beam_h = 0.12
        bv2, bf2 = _make_beveled_box(
            0, lintel_y + beam_h / 2, 0,
            width / 2 + post_w + 0.05, beam_h / 2, depth * 0.4,
            bevel=0.008,
        )
        parts.append((bv2, bf2))

        # Cross braces (diagonal supports)
        brace_w = 0.04
        for x_sign in [-1, 1]:
            bx = x_sign * (width / 2 + post_w * 0.3)
            brace_v, brace_f = _make_box(bx, lintel_y * 0.7, 0,
                                         brace_w / 2, lintel_y * 0.12, brace_w / 2)
            parts.append((brace_v, brace_f))

    elif style == "ruined":
        # Crumbling stone arch with missing sections
        arch_inner_r = width / 2
        arch_outer_r = arch_inner_r + post_w
        spring_y = height * 0.6

        # Only build partial arch (60% of the arc, simulating collapse)
        partial_segs = int(arch_segs * 0.6)
        arch_verts2: list[tuple[float, float, float]] = []
        arch_faces2: list[tuple[int, ...]] = []

        for i in range(partial_segs + 1):
            t = i / arch_segs
            angle = math.pi * t
            ix = -math.cos(angle) * arch_inner_r
            iy = spring_y + math.sin(angle) * arch_inner_r
            ox = -math.cos(angle) * arch_outer_r
            oy = spring_y + math.sin(angle) * arch_outer_r

            arch_verts2.append((ix, iy, -depth / 2))
            arch_verts2.append((ox, oy, -depth / 2))
            arch_verts2.append((ix, iy, depth / 2))
            arch_verts2.append((ox, oy, depth / 2))

        for i in range(partial_segs):
            b = i * 4
            arch_faces2.append((b + 1, b + 5, b + 4, b + 0))
            arch_faces2.append((b + 2, b + 6, b + 7, b + 3))
            arch_faces2.append((b + 1, b + 3, b + 7, b + 5))
            arch_faces2.append((b + 0, b + 4, b + 6, b + 2))

        parts.append((arch_verts2, arch_faces2))

        # Fallen rubble on the ground (from collapsed portion)
        import random as _rng_arch
        rng = _rng_arch.Random(99)
        for _ in range(5):
            rx = rng.uniform(-width * 0.3, width * 0.8)
            rz = rng.uniform(-depth, depth)
            rs = rng.uniform(0.05, 0.15)
            rv, rf = _make_beveled_box(rx, rs * 0.5, rz,
                                       rs, rs * 0.5, rs * 0.8, bevel=0.005)
            parts.append((rv, rf))

    else:  # stone_round (default)
        # Arch (semi-circular top)
        arch_inner_r = width / 2
        arch_outer_r = arch_inner_r + post_w
        spring_y = height * 0.6

        arch_verts3: list[tuple[float, float, float]] = []
        arch_faces3: list[tuple[int, ...]] = []

        for i in range(arch_segs + 1):
            t = i / arch_segs
            angle = math.pi * t
            ix = -math.cos(angle) * arch_inner_r
            iy = spring_y + math.sin(angle) * arch_inner_r
            ox = -math.cos(angle) * arch_outer_r
            oy = spring_y + math.sin(angle) * arch_outer_r

            arch_verts3.append((ix, iy, -depth / 2))
            arch_verts3.append((ox, oy, -depth / 2))
            arch_verts3.append((ix, iy, depth / 2))
            arch_verts3.append((ox, oy, depth / 2))

        for i in range(arch_segs):
            b = i * 4
            arch_faces3.append((b + 1, b + 5, b + 4, b + 0))
            arch_faces3.append((b + 2, b + 6, b + 7, b + 3))
            arch_faces3.append((b + 1, b + 3, b + 7, b + 5))
            arch_faces3.append((b + 0, b + 4, b + 6, b + 2))

        parts.append((arch_verts3, arch_faces3))

        # Keystone at top
        kv, kf = _make_beveled_box(
            0, spring_y + arch_outer_r + 0.02, 0,
            post_w * 0.4, post_w * 0.3, depth / 2 + 0.01,
            bevel=0.008,
        )
        parts.append((kv, kf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Archway_{style}", verts, faces, style=style, category="dungeon_prop")


def generate_chain_mesh(
    links: int = 8,
    link_size: float = 0.04,
) -> MeshSpec:
    """Generate a hanging chain with interlocking links.

    Args:
        links: Number of chain links.
        link_size: Size of each link.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    link_spacing = link_size * 1.8
    wire_r = link_size * 0.15

    for i in range(links):
        y = -i * link_spacing
        # Alternate link orientation (0° and 90°)
        if i % 2 == 0:
            # Link as torus in XY plane
            tv, tf = _make_torus_ring(
                0, y, 0,
                link_size * 0.5, wire_r,
                major_segments=8, minor_segments=4,
            )
        else:
            # Link rotated 90° -- torus in YZ plane
            tv, tf = _make_torus_ring(
                0, y, 0,
                link_size * 0.5, wire_r,
                major_segments=8, minor_segments=4,
            )
            # Rotate 90° around Y axis: swap X and Z
            tv = [(v[2], v[1], v[0]) for v in tv]

        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Chain", verts, faces, links=links, category="dungeon_prop")


def generate_skull_pile_mesh(
    count: int = 5,
) -> MeshSpec:
    """Generate a dark fantasy skull pile arrangement.

    Args:
        count: Number of skulls in the pile.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    import random as _rng
    rng = _rng.Random(666)  # Appropriately dark seed

    skull_r = 0.06

    for i in range(count):
        # Arrange in a rough pile
        layer = 0 if i < max(count * 2 // 3, 1) else 1
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(0, skull_r * 2) if layer == 0 else rng.uniform(0, skull_r)
        x = math.cos(angle) * dist
        z = math.sin(angle) * dist
        y = layer * skull_r * 1.5 + skull_r

        # Each skull: elongated sphere (cranium) + jaw box
        # Cranium
        cv, cf = _make_sphere(x, y, z, skull_r, rings=5, sectors=6)
        parts.append((cv, cf))

        # Face/jaw (smaller box in front)
        face_angle = rng.uniform(0, 2 * math.pi)
        fx = x + math.cos(face_angle) * skull_r * 0.5
        fz = z + math.sin(face_angle) * skull_r * 0.5
        jv, jf = _make_box(fx, y - skull_r * 0.3, fz,
                           skull_r * 0.3, skull_r * 0.2, skull_r * 0.25)
        parts.append((jv, jf))

        # Eye sockets (two small indentations - represented as small spheres)
        for eye_side in [-1, 1]:
            ex = fx + eye_side * skull_r * 0.2
            ey = y + skull_r * 0.1
            ev, ef = _make_sphere(ex, ey, fz + skull_r * 0.15,
                                  skull_r * 0.12, rings=3, sectors=4)
            parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SkullPile", verts, faces, count=count, category="dungeon_prop")


# =========================================================================
# CATEGORY 4: WEAPONS (expanding beyond the existing 7 types)
# =========================================================================


def generate_hammer_mesh(
    head_style: str = "flat",
    handle_length: float = 0.9,
) -> MeshSpec:
    """Generate a warhammer mesh.

    Args:
        head_style: "flat", "spiked", or "ornate".
        handle_length: Length of the handle.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    handle_r = 0.015
    segs = 8

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9,
                                    handle_length, segs, rings=4)
    parts.append((hv, hf))

    # Pommel
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.5, rings=4, sectors=6)
    parts.append((pv, pf))

    # Hammer head
    head_y = handle_length * 0.85
    head_w = 0.12
    head_h = 0.08
    head_d = 0.06

    if head_style == "flat":
        mv, mf = _make_beveled_box(0, head_y, 0, head_w / 2, head_h / 2, head_d / 2,
                                   bevel=0.008)
        parts.append((mv, mf))

    elif head_style == "spiked":
        # Main block
        mv, mf = _make_beveled_box(0, head_y, 0, head_w / 2, head_h / 2, head_d / 2,
                                   bevel=0.005)
        parts.append((mv, mf))
        # Spike on top
        sv, sf = _make_cone(0, head_y + head_h / 2, 0, head_d * 0.3, 0.08, segments=6)
        parts.append((sv, sf))
        # Spike on back
        bsv, bsf = _make_cone(-head_w / 2, head_y, 0, head_d * 0.25, 0.06, segments=6)
        # Rotate spike to point outward (approximate)
        bsv_r = [(-head_w / 2 - (v[1] - head_y) * 0.8, head_y + (v[0] + head_w / 2), v[2])
                 for v in bsv]
        parts.append((bsv_r, bsf))

    else:  # ornate
        mv, mf = _make_beveled_box(0, head_y, 0, head_w / 2, head_h / 2, head_d / 2,
                                   bevel=0.01)
        parts.append((mv, mf))
        # Decorative rings
        for yoff in [-head_h * 0.3, head_h * 0.3]:
            rv, rf = _make_torus_ring(0, head_y + yoff, 0,
                                      head_d * 0.45, 0.005,
                                      major_segments=8, minor_segments=4)
            parts.append((rv, rf))

    # Grip wrap (subtle rings)
    for gi in range(5):
        gy = handle_length * 0.1 + gi * handle_length * 0.08
        gv, gf = _make_torus_ring(0, gy, 0,
                                  handle_r * 1.3, handle_r * 0.15,
                                  major_segments=segs, minor_segments=3)
        parts.append((gv, gf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Hammer_{head_style}", verts, faces,
                        style=head_style, category="weapon")


def generate_spear_mesh(
    head_style: str = "leaf",
    shaft_length: float = 2.0,
) -> MeshSpec:
    """Generate a spear or halberd mesh.

    Args:
        head_style: "leaf", "broad", or "halberd".
        shaft_length: Length of the shaft.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    shaft_r = 0.012
    segs = 8

    # Shaft
    sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r * 0.9,
                                    shaft_length, segs, rings=6)
    parts.append((sv, sf))

    # Butt cap
    bv, bf = _make_sphere(0, -0.01, 0, shaft_r * 1.5, rings=4, sectors=6)
    parts.append((bv, bf))

    # Spearhead
    head_base_y = shaft_length
    if head_style == "leaf":
        # Leaf-shaped blade
        blade_h = 0.2
        blade_w = 0.04
        blade_d = 0.008
        profile = []
        blade_segs = 8
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = head_base_y + t * blade_h
            w = blade_w * math.sin(t * math.pi) * (1.0 - t * 0.3)
            profile.append((max(w, 0.001), y))
        hv, hf = _make_lathe(profile, segments=4, close_bottom=True, close_top=True)
        parts.append((hv, hf))

    elif head_style == "broad":
        # Wide triangular head
        head_h = 0.15
        head_w = 0.06
        head_d = 0.006
        head_verts = [
            (0, head_base_y + head_h, 0),  # Tip
            (-head_w, head_base_y, head_d),
            (head_w, head_base_y, head_d),
            (-head_w, head_base_y, -head_d),
            (head_w, head_base_y, -head_d),
        ]
        head_faces = [
            (0, 1, 2),  # Front
            (0, 4, 3),  # Back
            (0, 2, 4),  # Right
            (0, 3, 1),  # Left
            (1, 3, 4, 2),  # Bottom
        ]
        parts.append((head_verts, head_faces))

    else:  # halberd
        # Axe blade + spike + back spike
        # Main axe blade
        blade_h = 0.2
        blade_w = 0.15
        blade_d = 0.008
        blade_verts = [
            (blade_w, head_base_y + blade_h * 0.7, blade_d),
            (blade_w, head_base_y - blade_h * 0.3, blade_d),
            (0, head_base_y - blade_h * 0.2, blade_d),
            (0, head_base_y + blade_h * 0.6, blade_d),
            (blade_w, head_base_y + blade_h * 0.7, -blade_d),
            (blade_w, head_base_y - blade_h * 0.3, -blade_d),
            (0, head_base_y - blade_h * 0.2, -blade_d),
            (0, head_base_y + blade_h * 0.6, -blade_d),
        ]
        blade_faces = [
            (0, 1, 2, 3),
            (7, 6, 5, 4),
            (0, 4, 5, 1),
            (2, 6, 7, 3),
            (0, 3, 7, 4),
            (1, 5, 6, 2),
        ]
        parts.append((blade_verts, blade_faces))

        # Top spike
        tsv, tsf = _make_cone(0, head_base_y, 0, shaft_r * 2, 0.15, segments=6)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Spear_{head_style}", verts, faces,
                        style=head_style, category="weapon")


def generate_crossbow_mesh(
    size: float = 1.0,
) -> MeshSpec:
    """Generate a crossbow mesh with mechanism.

    Args:
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Stock (main body)
    stock_len = 0.5 * s
    stock_w = 0.03 * s
    stock_h = 0.04 * s
    sv, sf = _make_beveled_box(0, 0, 0, stock_w, stock_h, stock_len / 2,
                               bevel=0.005 * s)
    parts.append((sv, sf))

    # Trigger guard
    tgv, tgf = _make_box(0, -stock_h * 1.5, -stock_len * 0.15,
                         stock_w * 0.8, stock_h * 0.8, 0.01 * s)
    parts.append((tgv, tgf))

    # Bow arms (two curved limbs)
    arm_len = 0.3 * s
    arm_segs = 6
    for side in [-1, 1]:
        arm_verts: list[tuple[float, float, float]] = []
        arm_faces_local: list[tuple[int, ...]] = []
        for i in range(arm_segs + 1):
            t = i / arm_segs
            # Curved outward
            x = side * t * arm_len
            z = stock_len / 2 - 0.02 * s
            y = -t * t * arm_len * 0.3  # Slight droop
            r = 0.01 * s * (1.0 - t * 0.3)
            cv, cf = _make_cylinder(x, y - r, z, max(r, 0.003 * s), r * 2,
                                    segments=4, cap_top=False, cap_bottom=False)
            parts.append((cv, cf))

    # String
    string_v = [
        (-arm_len, -arm_len * 0.3 * arm_len, stock_len / 2 - 0.02 * s),
        (0, 0, stock_len / 2 - 0.01 * s),
        (arm_len, -arm_len * 0.3 * arm_len, stock_len / 2 - 0.02 * s),
    ]
    string_f = [(0, 1, 2)]  # Simple triangle for string
    parts.append((string_v, string_f))

    # Rail on top
    rv, rf = _make_box(0, stock_h + 0.005 * s, 0.05 * s,
                       0.005 * s, 0.005 * s, stock_len * 0.4)
    parts.append((rv, rf))

    # Bolt/quarrel
    bv, bf = _make_tapered_cylinder(0, stock_h + 0.015 * s, 0.1 * s,
                                    0.003 * s, 0.001 * s, 0.25 * s,
                                    segments=4, rings=2)
    parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Crossbow", verts, faces, category="weapon")


def generate_scythe_mesh(
    blade_curve: float = 0.8,
    handle_length: float = 1.8,
) -> MeshSpec:
    """Generate a reaper scythe mesh.

    Args:
        blade_curve: How curved the blade is (0.5-1.5).
        handle_length: Length of the handle/shaft.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    shaft_r = 0.015
    segs = 8

    # Long shaft
    sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r * 0.85,
                                    handle_length, segs, rings=6)
    parts.append((sv, sf))

    # Scythe blade - curved using parametric points
    blade_len = 0.6
    blade_segs = 12
    blade_thick = 0.004

    blade_verts: list[tuple[float, float, float]] = []
    blade_faces: list[tuple[int, ...]] = []

    for i in range(blade_segs + 1):
        t = i / blade_segs
        # Parametric curve for blade
        angle = t * math.pi * blade_curve * 0.8
        bx = -math.sin(angle) * blade_len * t
        by = handle_length + math.cos(angle) * blade_len * t * 0.3
        # Width tapers to edge
        edge_w = 0.06 * (1.0 - t * 0.7) * math.sin(t * math.pi + 0.2)
        # Four vertices per cross-section: inner edge, outer edge, front, back
        blade_verts.append((bx, by, blade_thick))
        blade_verts.append((bx - edge_w, by - edge_w * 0.3, 0))  # Cutting edge
        blade_verts.append((bx, by, -blade_thick))

    # Connect blade quads
    for i in range(blade_segs):
        b = i * 3
        for j in range(2):
            blade_faces.append((b + j, b + j + 1, b + 3 + j + 1, b + 3 + j))

    parts.append((blade_verts, blade_faces))

    # Collar where blade meets shaft
    cv, cf = _make_torus_ring(0, handle_length, 0,
                              shaft_r * 2, shaft_r * 0.5,
                              major_segments=segs, minor_segments=4)
    parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Scythe", verts, faces, category="weapon")


def generate_flail_mesh(
    head_count: int = 1,
    chain_length: float = 0.3,
) -> MeshSpec:
    """Generate a flail (ball and chain) mesh.

    Args:
        head_count: Number of spiked balls (1-3).
        chain_length: Length of the chain.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    handle_len = 0.4
    handle_r = 0.018
    segs = 8

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.2, handle_r,
                                    handle_len, segs, rings=3)
    parts.append((hv, hf))

    # Pommel
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.5, rings=4, sectors=6)
    parts.append((pv, pf))

    # Grip wrapping
    for gi in range(4):
        gy = handle_len * 0.1 + gi * handle_len * 0.12
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.3, handle_r * 0.12,
                                  major_segments=segs, minor_segments=3)
        parts.append((gv, gf))

    head_count = max(1, min(3, head_count))

    for h in range(head_count):
        h_angle = 0 if head_count == 1 else (h - (head_count - 1) / 2) * 0.4

        # Chain links
        link_count = max(3, int(chain_length / 0.03))
        link_r = 0.008
        wire_r = 0.002
        for li in range(link_count):
            t = li / link_count
            ly = handle_len + t * chain_length
            lx = math.sin(h_angle) * t * chain_length
            tv, tf = _make_torus_ring(
                lx, ly, 0, link_r, wire_r,
                major_segments=6, minor_segments=3,
            )
            if li % 2 == 1:
                tv = [(v[2] + lx, v[1], v[0] - lx) for v in tv]
            parts.append((tv, tf))

        # Spiked ball
        ball_x = math.sin(h_angle) * chain_length
        ball_y = handle_len + chain_length
        ball_r = 0.04
        bv, bf = _make_sphere(ball_x, ball_y, 0, ball_r, rings=5, sectors=8)
        parts.append((bv, bf))

        # Spikes
        spike_count = 8
        for si in range(spike_count):
            s_phi = math.pi * (si // 4 + 0.5) / 2
            s_theta = 2 * math.pi * (si % 4) / 4 + (si // 4) * math.pi / 4
            sx = ball_x + math.sin(s_phi) * math.cos(s_theta) * ball_r
            sy = ball_y + math.cos(s_phi) * ball_r
            sz = math.sin(s_phi) * math.sin(s_theta) * ball_r
            spike_r = 0.008
            spike_h = 0.025
            spv, spf = _make_cone(sx, sy, sz, spike_r, spike_h, segments=4)
            parts.append((spv, spf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Flail", verts, faces, head_count=head_count, category="weapon")


def generate_whip_mesh(
    length: float = 2.0,
    segments: int = 20,
) -> MeshSpec:
    """Generate a segmented whip mesh.

    Args:
        length: Total whip length.
        segments: Number of whip segments.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    handle_len = 0.25
    handle_r = 0.018
    segs_circ = 6

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.2, handle_r,
                                    handle_len, segs_circ, rings=3)
    parts.append((hv, hf))

    # Pommel knot
    pv, pf = _make_sphere(0, -0.01, 0, handle_r * 1.3, rings=3, sectors=5)
    parts.append((pv, pf))

    # Whip segments -- each tapers thinner
    whip_length = length - handle_len
    for i in range(segments):
        t = i / segments
        t2 = (i + 1) / segments
        seg_len = whip_length / segments
        r = handle_r * (1.0 - t * 0.85)

        # Apply a gentle curve
        y1 = handle_len + t * whip_length
        y2 = handle_len + t2 * whip_length
        x_curve = math.sin(t * math.pi * 2) * length * 0.05
        z_curve = math.cos(t * math.pi * 1.5) * length * 0.03

        sv, sf = _make_cylinder(
            x_curve, y1, z_curve,
            max(r, 0.002), seg_len,
            segments=segs_circ,
            cap_top=(i == segments - 1),
            cap_bottom=(i == 0),
        )
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Whip", verts, faces, category="weapon")


def generate_claw_mesh(
    finger_count: int = 4,
    curve: float = 0.7,
) -> MeshSpec:
    """Generate monster claw/gauntlet mesh.

    Args:
        finger_count: Number of claw fingers (3-5).
        curve: How curved the claws are (0.3-1.5).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    finger_count = max(3, min(5, finger_count))

    # Palm/gauntlet base
    palm_r = 0.06
    palm_h = 0.08
    pv, pf = _make_tapered_cylinder(0, 0, 0, palm_r * 1.2, palm_r,
                                    palm_h, segments=finger_count * 2, rings=2)
    parts.append((pv, pf))

    # Wrist guard
    wv, wf = _make_tapered_cylinder(0, -0.05, 0, palm_r * 0.9, palm_r * 1.1,
                                    0.05, segments=8, rings=1)
    parts.append((wv, wf))

    # Claw fingers
    for i in range(finger_count):
        angle = math.pi * 0.3 + (math.pi * 0.4) * i / (finger_count - 1) if finger_count > 1 else math.pi * 0.5
        fx = math.cos(angle) * palm_r * 0.8
        fz = math.sin(angle) * palm_r * 0.8
        finger_len = 0.12 + 0.03 * (1.0 if i == 1 else 0)  # Middle finger longer

        # Finger segments
        n_segs = 4
        for s in range(n_segs):
            t = s / n_segs
            t2 = (s + 1) / n_segs
            # Curve the finger forward and inward
            seg_x = fx + math.sin(t * curve * math.pi * 0.5) * finger_len * 0.5
            seg_y = palm_h + t * finger_len * 0.8
            seg_z = fz + math.cos(t * curve * math.pi * 0.3) * finger_len * 0.2
            seg_r = 0.01 * (1.0 - t * 0.5)
            seg_h = finger_len / n_segs

            cv, cf = _make_cylinder(
                seg_x, seg_y, seg_z,
                max(seg_r, 0.003), seg_h,
                segments=4, cap_top=(s == n_segs - 1), cap_bottom=(s == 0),
            )
            parts.append((cv, cf))

        # Claw tip (sharp cone)
        tip_x = fx + math.sin(curve * math.pi * 0.5) * finger_len * 0.5
        tip_y = palm_h + finger_len * 0.8
        tip_z = fz + math.cos(curve * math.pi * 0.3) * finger_len * 0.2
        tv, tf = _make_cone(tip_x, tip_y, tip_z, 0.008, 0.04, segments=4)
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Claw", verts, faces, finger_count=finger_count, category="weapon")


def generate_tome_mesh(
    size: float = 1.0,
    pages: int = 200,
) -> MeshSpec:
    """Generate a spellbook/grimoire mesh.

    Args:
        size: Scale factor.
        pages: Number of pages (affects spine thickness).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    cover_w = 0.15 * s
    cover_h = 0.2 * s
    spine_thick = max(0.02, pages * 0.0002) * s
    cover_thick = 0.005 * s

    # Front cover
    fv, ff = _make_beveled_box(
        cover_w / 2, cover_h / 2, spine_thick / 2 + cover_thick / 2,
        cover_w / 2, cover_h / 2, cover_thick / 2,
        bevel=0.003 * s,
    )
    parts.append((fv, ff))

    # Back cover
    bv, bf = _make_beveled_box(
        cover_w / 2, cover_h / 2, -spine_thick / 2 - cover_thick / 2,
        cover_w / 2, cover_h / 2, cover_thick / 2,
        bevel=0.003 * s,
    )
    parts.append((bv, bf))

    # Spine (curved)
    spine_profile = [
        (cover_h / 2 + 0.003 * s, -spine_thick / 2 - cover_thick),
        (cover_h / 2 + 0.005 * s, -spine_thick / 4),
        (cover_h / 2 + 0.006 * s, 0),
        (cover_h / 2 + 0.005 * s, spine_thick / 4),
        (cover_h / 2 + 0.003 * s, spine_thick / 2 + cover_thick),
    ]
    # The spine runs along the left edge (x=0)
    spine_verts: list[tuple[float, float, float]] = []
    spine_faces: list[tuple[int, ...]] = []
    spine_h_segs = 8
    for i in range(len(spine_profile)):
        r, z = spine_profile[i]
        for j in range(spine_h_segs + 1):
            t = j / spine_h_segs
            y = t * cover_h
            spine_verts.append((0, y, z))

    for i in range(len(spine_profile) - 1):
        for j in range(spine_h_segs):
            s0 = i * (spine_h_segs + 1) + j
            s1 = s0 + 1
            s2 = (i + 1) * (spine_h_segs + 1) + j + 1
            s3 = (i + 1) * (spine_h_segs + 1) + j
            spine_faces.append((s0, s1, s2, s3))

    parts.append((spine_verts, spine_faces))

    # Pages block (slightly inset from covers)
    page_inset = 0.005 * s
    pv, pf = _make_box(
        cover_w / 2 + page_inset,
        cover_h / 2,
        0,
        cover_w / 2 - page_inset * 2,
        cover_h / 2 - page_inset,
        spine_thick / 2 - 0.002 * s,
    )
    parts.append((pv, pf))

    # Corner metal clasps
    clasp_size = 0.012 * s
    for yoff in [0.01 * s, cover_h - 0.01 * s]:
        for zoff in [spine_thick / 2 + cover_thick, -spine_thick / 2 - cover_thick]:
            cv, cf = _make_sphere(cover_w - 0.01 * s, yoff, zoff,
                                  clasp_size, rings=3, sectors=4)
            parts.append((cv, cf))

    # Central emblem on front cover
    ev, ef = _make_cylinder(
        cover_w / 2, cover_h / 2, spine_thick / 2 + cover_thick + 0.002 * s,
        0.02 * s, 0.003 * s, segments=6,
    )
    parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Tome", verts, faces, pages=pages, category="weapon")


def generate_greatsword_mesh(style: str = "standard") -> MeshSpec:
    """Generate a greatsword mesh -- wide blade, ricasso, two-hand grip.

    Args:
        style: "standard", "flamberge", or "executioner".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    handle_len = 0.35
    handle_r = 0.018
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.95, handle_len, segs, rings=4)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.025, 0, handle_r * 2.0, rings=5, sectors=8)
    parts.append((pv, pf))
    for gi in range(7):
        gy = 0.02 + gi * handle_len * 0.12
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.25, handle_r * 0.12, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    guard_y = handle_len
    gv2, gf2 = _make_beveled_box(0, guard_y + 0.0075, 0, 0.06, 0.0075, 0.01, bevel=0.004)
    parts.append((gv2, gf2))
    ricasso_h = 0.08
    rv, rf = _make_beveled_box(0, guard_y + 0.015 + ricasso_h / 2, 0, 0.0175, ricasso_h / 2, 0.0035, bevel=0.003)
    parts.append((rv, rf))
    blade_base_y = guard_y + 0.015 + ricasso_h
    if style == "flamberge":
        blade_h, blade_segs, blade_thick = 0.8, 16, 0.005
        bv_l: list[tuple[float, float, float]] = []
        bf_l: list[tuple[int, ...]] = []
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = blade_base_y + t * blade_h
            wave = math.sin(t * math.pi * 4) * 0.008
            w = 0.03 * (1.0 - t * 0.6) + wave
            bv_l.extend([(-w, y, blade_thick), (w, y, blade_thick), (w, y, -blade_thick), (-w, y, -blade_thick)])
        for i in range(blade_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bf_l.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        tip_y = blade_base_y + blade_h
        bv_l.append((0, tip_y + 0.04, 0))
        tb = blade_segs * 4
        ti = len(bv_l) - 1
        for j in range(4):
            bf_l.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((bv_l, bf_l))
        trail_top_y = tip_y + 0.04
    elif style == "executioner":
        bv3, bf3 = _make_beveled_box(0, blade_base_y + 0.325, 0, 0.045, 0.325, 0.006, bevel=0.004)
        parts.append((bv3, bf3))
        trail_top_y = blade_base_y + 0.65
    else:
        blade_h, blade_segs, blade_thick = 0.75, 10, 0.005
        bv2: list[tuple[float, float, float]] = []
        bf2: list[tuple[int, ...]] = []
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = blade_base_y + t * blade_h
            w = 0.03 * (1.0 - t * 0.4)
            bv2.extend([(-w, y, blade_thick), (w, y, blade_thick), (w, y, -blade_thick), (-w, y, -blade_thick)])
        for i in range(blade_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bf2.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        tip_y2 = blade_base_y + blade_h
        bv2.append((0, tip_y2 + 0.05, 0))
        tb2 = blade_segs * 4
        ti2 = len(bv2) - 1
        for j in range(4):
            bf2.append((tb2 + j, tb2 + (j + 1) % 4, ti2))
        parts.append((bv2, bf2))
        trail_top_y = tip_y2 + 0.05
    fv, ff = _make_beveled_box(0, blade_base_y + 0.25, 0, 0.005, 0.2, 0.001, bevel=0.001)
    parts.append((fv, ff))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Greatsword_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.4, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, blade_base_y, 0.0))


def generate_curved_sword_mesh(style: str = "scimitar") -> MeshSpec:
    """Generate a curved single-edge sword mesh.

    Args:
        style: "scimitar", "katana", or "falchion".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    handle_len, handle_r = 0.2, 0.014
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=3)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.8, rings=4, sectors=6)
    parts.append((pv, pf))
    for gi in range(4):
        gy = 0.02 + gi * handle_len * 0.2
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.2, handle_r * 0.1, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    guard_y = handle_len
    if style == "katana":
        tv, tf = _make_cylinder(0, guard_y, 0, 0.04, 0.005, segments=12)
        parts.append((tv, tf))
    else:
        gv2, gf2 = _make_beveled_box(0, guard_y + 0.008, 0, 0.03, 0.008, 0.012, bevel=0.003)
        parts.append((gv2, gf2))
    blade_base_y = guard_y + 0.016
    blade_len = 0.6 if style != "falchion" else 0.45
    blade_segs, blade_thick = 12, 0.004
    curve_amount = 0.08 if style == "scimitar" else (0.05 if style == "katana" else 0.1)
    blade_w_base = 0.025 if style != "falchion" else 0.035
    bvl: list[tuple[float, float, float]] = []
    bfl: list[tuple[int, ...]] = []
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * blade_len
        x_off = math.sin(t * math.pi * 0.5) * curve_amount
        w = blade_w_base * (1.0 - t * 0.5) if style != "falchion" else blade_w_base * (1.0 + t * 0.3 - t * t * 1.2)
        w = max(w, 0.003)
        bvl.extend([(x_off - w * 0.3, y, blade_thick), (x_off + w, y, 0), (x_off - w * 0.3, y, -blade_thick)])
    for i in range(blade_segs):
        b = i * 3
        for j in range(3):
            j2 = (j + 1) % 3
            bfl.append((b + j, b + j2, b + 3 + j2, b + 3 + j))
    tip_x = math.sin(math.pi * 0.5) * curve_amount
    tip_y = blade_base_y + blade_len + 0.03
    bvl.append((tip_x, tip_y, 0))
    tb = blade_segs * 3
    ti = len(bvl) - 1
    for j in range(3):
        bfl.append((tb + j, tb + (j + 1) % 3, ti))
    parts.append((bvl, bfl))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"CurvedSword_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.4, 0.0), trail_top=(tip_x, tip_y, 0.0),
                        trail_bottom=(0.0, blade_base_y, 0.0))


def generate_hand_axe_mesh(style: str = "standard") -> MeshSpec:
    """Generate a small single-head hand axe mesh.

    Args:
        style: "standard", "bearded", or "tomahawk".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    haft_len, haft_r = 0.35, 0.012
    hv, hf = _make_tapered_cylinder(0, 0, 0, haft_r * 1.05, haft_r * 0.95, haft_len, segs, rings=3)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.015, 0, haft_r * 1.5, rings=3, sectors=6)
    parts.append((pv, pf))
    head_y = haft_len * 0.8
    if style == "bearded":
        bv = [(0.06, head_y + 0.03, 0.006), (0.06, head_y - 0.06, 0.006),
              (0.0, head_y - 0.02, 0.006), (0.0, head_y + 0.04, 0.006),
              (0.06, head_y + 0.03, -0.006), (0.06, head_y - 0.06, -0.006),
              (0.0, head_y - 0.02, -0.006), (0.0, head_y + 0.04, -0.006)]
    elif style == "tomahawk":
        bv = [(0.055, head_y + 0.025, 0.005), (0.055, head_y - 0.025, 0.005),
              (0.0, head_y - 0.015, 0.005), (0.0, head_y + 0.015, 0.005),
              (0.055, head_y + 0.025, -0.005), (0.055, head_y - 0.025, -0.005),
              (0.0, head_y - 0.015, -0.005), (0.0, head_y + 0.015, -0.005)]
    else:
        bv = [(0.065, head_y + 0.035, 0.006), (0.065, head_y - 0.035, 0.006),
              (0.0, head_y - 0.02, 0.006), (0.0, head_y + 0.02, 0.006),
              (0.065, head_y + 0.035, -0.006), (0.065, head_y - 0.035, -0.006),
              (0.0, head_y - 0.02, -0.006), (0.0, head_y + 0.02, -0.006)]
    bf = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
    parts.append((bv, bf))
    ev, ef = _make_torus_ring(0, head_y, 0, haft_r * 1.5, haft_r * 0.3, major_segments=segs, minor_segments=3)
    parts.append((ev, ef))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"HandAxe_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, haft_len * 0.3, 0.0), trail_top=(0.065, head_y + 0.04, 0.0),
                        trail_bottom=(0.065, head_y - 0.035, 0.0))


def generate_battle_axe_mesh(style: str = "double") -> MeshSpec:
    """Generate a battle axe mesh with medium haft.

    Args:
        style: "double", "crescent", or "single_large".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    haft_len, haft_r = 0.7, 0.014
    hv, hf = _make_tapered_cylinder(0, 0, 0, haft_r * 1.1, haft_r * 0.9, haft_len, segs, rings=5)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.02, 0, haft_r * 1.8, rings=4, sectors=6)
    parts.append((pv, pf))
    for gi in range(5):
        gy = 0.02 + gi * 0.05
        gv, gf = _make_torus_ring(0, gy, 0, haft_r * 1.3, haft_r * 0.12, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    head_y = haft_len * 0.82
    bd = 0.008
    if style == "double":
        for side in [1, -1]:
            bv = [(side * 0.1, head_y + 0.06, bd), (side * 0.1, head_y - 0.06, bd),
                  (side * 0.01, head_y - 0.03, bd), (side * 0.01, head_y + 0.03, bd),
                  (side * 0.1, head_y + 0.06, -bd), (side * 0.1, head_y - 0.06, -bd),
                  (side * 0.01, head_y - 0.03, -bd), (side * 0.01, head_y + 0.03, -bd)]
            bf = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
            parts.append((bv, bf))
        trail_top_y = head_y + 0.06
    elif style == "crescent":
        bsegs = 10
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        for i in range(bsegs + 1):
            t = i / bsegs
            angle = (t - 0.5) * math.pi * 0.8
            bvl.extend([(math.cos(angle) * 0.1, head_y + math.sin(angle) * 0.1, bd),
                        (math.cos(angle) * 0.03, head_y + math.sin(angle) * 0.03, bd),
                        (math.cos(angle) * 0.03, head_y + math.sin(angle) * 0.03, -bd),
                        (math.cos(angle) * 0.1, head_y + math.sin(angle) * 0.1, -bd)])
        for i in range(bsegs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        parts.append((bvl, bfl))
        trail_top_y = head_y + 0.1
    else:
        bv3 = [(0.12, head_y + 0.07, bd), (0.12, head_y - 0.07, bd),
               (0.0, head_y - 0.035, bd), (0.0, head_y + 0.035, bd),
               (0.12, head_y + 0.07, -bd), (0.12, head_y - 0.07, -bd),
               (0.0, head_y - 0.035, -bd), (0.0, head_y + 0.035, -bd)]
        bf3 = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
        parts.append((bv3, bf3))
        trail_top_y = head_y + 0.07
    ev, ef = _make_torus_ring(0, head_y, 0, haft_r * 2, haft_r * 0.4, major_segments=segs, minor_segments=3)
    parts.append((ev, ef))
    sv, sf = _make_cone(0, head_y + 0.03, 0, haft_r * 1.5, 0.06, segments=6)
    parts.append((sv, sf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"BattleAxe_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, haft_len * 0.25, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.1, head_y - 0.07, 0.0))


def generate_greataxe_mesh(style: str = "massive") -> MeshSpec:
    """Generate a greataxe mesh -- massive head, long haft.

    Args:
        style: "massive", "cleaver", or "moon".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    haft_len, haft_r = 1.2, 0.016
    hv, hf = _make_tapered_cylinder(0, 0, 0, haft_r * 1.15, haft_r * 0.9, haft_len, segs, rings=6)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.03, 0, haft_r * 2.2, rings=5, sectors=8)
    parts.append((pv, pf))
    for gi in range(8):
        gy = 0.03 + gi * 0.045
        gv, gf = _make_torus_ring(0, gy, 0, haft_r * 1.3, haft_r * 0.12, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    head_y = haft_len * 0.85
    bd = 0.01
    if style == "moon":
        bsegs = 14
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        for i in range(bsegs + 1):
            t = i / bsegs
            angle = (t - 0.5) * math.pi
            x_o, y_o = math.cos(angle) * 0.15, head_y + math.sin(angle) * 0.15
            x_i, y_i = math.cos(angle) * 0.05, head_y + math.sin(angle) * 0.05
            bvl.extend([(x_o, y_o, bd), (x_i, y_i, bd), (x_i, y_i, -bd), (x_o, y_o, -bd)])
        for i in range(bsegs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        parts.append((bvl, bfl))
        trail_top_y = head_y + 0.15
    elif style == "cleaver":
        bv, bf = _make_beveled_box(0.08, head_y, 0, 0.08, 0.1, bd, bevel=0.005)
        parts.append((bv, bf))
        trail_top_y = head_y + 0.1
    else:
        for side in [1, -1]:
            bv2 = [(side * 0.14, head_y + 0.09, bd), (side * 0.14, head_y - 0.09, bd),
                   (side * 0.02, head_y - 0.05, bd), (side * 0.02, head_y + 0.05, bd),
                   (side * 0.14, head_y + 0.09, -bd), (side * 0.14, head_y - 0.09, -bd),
                   (side * 0.02, head_y - 0.05, -bd), (side * 0.02, head_y + 0.05, -bd)]
            bf2 = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
            parts.append((bv2, bf2))
        trail_top_y = head_y + 0.09
    ev, ef = _make_torus_ring(0, head_y, 0, haft_r * 2.5, haft_r * 0.5, major_segments=segs, minor_segments=4)
    parts.append((ev, ef))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Greataxe_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, haft_len * 0.2, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.14, head_y - 0.09, 0.0))


def generate_club_mesh(style: str = "wooden") -> MeshSpec:
    """Generate a rough club mesh with nail/spike extrusions.

    Args:
        style: "wooden", "spiked", or "bone".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    handle_len, handle_r = 0.3, 0.02
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r, handle_r * 0.85, handle_len, segs, rings=3)
    parts.append((hv, hf))
    body_len = 0.4
    body_r_top = 0.045 if style != "bone" else 0.05
    bv, bf = _make_tapered_cylinder(0, handle_len, 0, handle_r * 1.2, body_r_top, body_len, segs, rings=4)
    parts.append((bv, bf))
    tv, tf = _make_sphere(0, handle_len + body_len, 0, body_r_top * 0.95, rings=4, sectors=segs)
    parts.append((tv, tf))
    if style == "spiked":
        head_cy = handle_len + body_len * 0.7
        for si in range(10):
            s_phi = math.pi * (0.3 + 0.4 * (si // 5))
            s_theta = 2 * math.pi * (si % 5) / 5 + (si // 5) * math.pi / 5
            sx = math.sin(s_phi) * math.cos(s_theta) * body_r_top
            sy = head_cy + math.cos(s_phi) * body_r_top * 1.5
            sz = math.sin(s_phi) * math.sin(s_theta) * body_r_top
            nv, nf = _make_tapered_cylinder(sx * 1.2, sy, sz * 1.2, 0.004, 0.002, 0.025, segments=4, rings=1)
            parts.append((nv, nf))
    elif style == "bone":
        for ki in range(5):
            angle = 2 * math.pi * ki / 5
            kv, kf = _make_sphere(math.cos(angle) * body_r_top * 0.9, handle_len + body_len * 0.75,
                                  math.sin(angle) * body_r_top * 0.9, 0.012, rings=3, sectors=4)
            parts.append((kv, kf))
    for ri in range(3):
        ry = handle_len + body_len * (0.3 + ri * 0.2)
        r_at = handle_r * 1.2 + (body_r_top - handle_r * 1.2) * (0.3 + ri * 0.2)
        rv, rf = _make_torus_ring(0, ry, 0, r_at * 0.95, 0.003, major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    trail_top_y = handle_len + body_len + body_r_top
    return _make_result(f"Club_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.4, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, handle_len + body_len * 0.5, 0.0))


def generate_mace_mesh(style: str = "flanged") -> MeshSpec:
    """Generate a mace mesh with flanged or studded head.

    Args:
        style: "flanged", "studded", or "morningstar".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    handle_len, handle_r = 0.35, 0.014
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=3)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.8, rings=4, sectors=6)
    parts.append((pv, pf))
    for gi in range(4):
        gy = 0.02 + gi * handle_len * 0.2
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.2, handle_r * 0.1, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    head_y = handle_len + 0.01
    head_r = 0.035
    if style == "flanged":
        sv, sf = _make_sphere(0, head_y + head_r, 0, head_r, rings=5, sectors=8)
        parts.append((sv, sf))
        for fi in range(7):
            angle = 2 * math.pi * fi / 7
            fx, fz = math.cos(angle), math.sin(angle)
            fv = [(fx * head_r, head_y + head_r + head_r * 0.7, fz * head_r),
                  (fx * head_r, head_y + head_r - head_r * 0.7, fz * head_r),
                  (fx * head_r * 1.6, head_y + head_r, fz * head_r * 1.6)]
            parts.append((fv, [(0, 1, 2)]))
    elif style == "studded":
        sv, sf = _make_sphere(0, head_y + head_r, 0, head_r, rings=5, sectors=8)
        parts.append((sv, sf))
        for si in range(12):
            s_phi = math.pi * (si // 4 + 0.5) / 3 + 0.3
            s_theta = 2 * math.pi * (si % 4) / 4 + (si // 4) * math.pi / 4
            sx = math.sin(s_phi) * math.cos(s_theta) * head_r
            sy = head_y + head_r + math.cos(s_phi) * head_r
            sz = math.sin(s_phi) * math.sin(s_theta) * head_r
            sv2, sf2 = _make_sphere(sx, sy, sz, 0.006, rings=3, sectors=4)
            parts.append((sv2, sf2))
    else:
        sv, sf = _make_sphere(0, head_y + head_r, 0, head_r, rings=5, sectors=8)
        parts.append((sv, sf))
        for si in range(12):
            s_phi = math.pi * (si // 4 + 0.5) / 3 + 0.3
            s_theta = 2 * math.pi * (si % 4) / 4 + (si // 4) * math.pi / 4
            sx = math.sin(s_phi) * math.cos(s_theta) * head_r * 1.1
            sy = head_y + head_r + math.cos(s_phi) * head_r * 1.1
            sz = math.sin(s_phi) * math.sin(s_theta) * head_r * 1.1
            spv, spf = _make_cone(sx, sy, sz, 0.008, 0.025, segments=4)
            parts.append((spv, spf))
    cv, cf = _make_torus_ring(0, head_y, 0, handle_r * 1.5, handle_r * 0.3, major_segments=segs, minor_segments=3)
    parts.append((cv, cf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Mace_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.35, 0.0), trail_top=(0.0, head_y + head_r * 2, 0.0),
                        trail_bottom=(0.0, head_y, 0.0))


def generate_warhammer_mesh(style: str = "standard") -> MeshSpec:
    """Generate a warhammer mesh -- flat striking face + pick on back.

    Args:
        style: "standard", "maul", or "lucerne".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    handle_len, handle_r = 0.55, 0.015
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=4)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 2.0, rings=4, sectors=6)
    parts.append((pv, pf))
    for gi in range(5):
        gy = 0.02 + gi * handle_len * 0.1
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.25, handle_r * 0.12, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    head_y = handle_len * 0.82
    if style == "maul":
        mv, mf = _make_beveled_box(0, head_y, 0, 0.06, 0.04, 0.03, bevel=0.006)
        parts.append((mv, mf))
        trail_top_y = head_y + 0.04
    elif style == "lucerne":
        fv, ff = _make_beveled_box(0.04, head_y, 0, 0.03, 0.03, 0.03, bevel=0.004)
        parts.append((fv, ff))
        pkverts = [(-0.02, head_y + 0.01, 0.01), (-0.02, head_y - 0.01, 0.01),
                   (-0.02, head_y + 0.01, -0.01), (-0.02, head_y - 0.01, -0.01), (-0.1, head_y, 0)]
        parts.append((pkverts, [(0, 1, 4), (1, 3, 4), (3, 2, 4), (2, 0, 4), (0, 2, 3, 1)]))
        tsv, tsf = _make_cone(0, head_y + 0.03, 0, handle_r * 1.5, 0.1, segments=6)
        parts.append((tsv, tsf))
        trail_top_y = head_y + 0.13
    else:
        fv, ff = _make_beveled_box(0.03, head_y, 0, 0.02, 0.025, 0.02, bevel=0.005)
        parts.append((fv, ff))
        pkverts2 = [(-0.015, head_y + 0.015, 0.01), (-0.015, head_y - 0.015, 0.01),
                    (-0.015, head_y + 0.015, -0.01), (-0.015, head_y - 0.015, -0.01), (-0.09, head_y, 0)]
        parts.append((pkverts2, [(0, 1, 4), (1, 3, 4), (3, 2, 4), (2, 0, 4), (0, 2, 3, 1)]))
        trail_top_y = head_y + 0.025
    ev, ef = _make_torus_ring(0, head_y, 0, handle_r * 2, handle_r * 0.4, major_segments=segs, minor_segments=3)
    parts.append((ev, ef))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Warhammer_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.3, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.04, head_y - 0.04, 0.0))


def generate_halberd_mesh(style: str = "standard") -> MeshSpec:
    """Generate a halberd mesh -- axe head + spike + hook on pole.

    Args:
        style: "standard", "voulge", or "partisan".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    pole_len, pole_r = 2.0, 0.014
    pv, pf = _make_tapered_cylinder(0, 0, 0, pole_r, pole_r * 0.9, pole_len, segs, rings=8)
    parts.append((pv, pf))
    bv, bf = _make_sphere(0, -0.015, 0, pole_r * 1.5, rings=3, sectors=6)
    parts.append((bv, bf))
    head_y = pole_len * 0.85
    bd = 0.007
    bw = 0.12
    if style == "voulge":
        bw = 0.08
        blade_h = 0.35
        bvl = [(bw, head_y + blade_h * 0.4, bd), (bw, head_y - blade_h * 0.6, bd),
               (0, head_y - blade_h * 0.5, bd), (0, head_y + blade_h * 0.3, bd),
               (bw, head_y + blade_h * 0.4, -bd), (bw, head_y - blade_h * 0.6, -bd),
               (0, head_y - blade_h * 0.5, -bd), (0, head_y + blade_h * 0.3, -bd)]
        parts.append((bvl, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]))
        tsv, tsf = _make_cone(0, head_y + blade_h * 0.3, 0, pole_r * 2, 0.15, segments=6)
        parts.append((tsv, tsf))
        trail_top_y = head_y + blade_h * 0.3 + 0.15
    elif style == "partisan":
        bw = 0.04
        blade_h = 0.25
        bvl2 = [(0, head_y + blade_h, 0), (-bw, head_y, bd), (bw, head_y, bd), (-bw, head_y, -bd), (bw, head_y, -bd)]
        parts.append((bvl2, [(0, 1, 2), (0, 4, 3), (0, 2, 4), (0, 3, 1), (1, 3, 4, 2)]))
        for side in [1, -1]:
            lv = [(side * 0.07, head_y + 0.02, bd * 0.5), (side * 0.07, head_y - 0.02, bd * 0.5),
                  (0, head_y, bd * 0.5), (side * 0.07, head_y + 0.02, -bd * 0.5),
                  (side * 0.07, head_y - 0.02, -bd * 0.5), (0, head_y, -bd * 0.5)]
            parts.append((lv, [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (0, 2, 5, 3)]))
        trail_top_y = head_y + blade_h
    else:
        blade_h = 0.18
        bvl3 = [(bw, head_y + blade_h * 0.5, bd), (bw, head_y - blade_h * 0.5, bd),
                (0, head_y - blade_h * 0.3, bd), (0, head_y + blade_h * 0.3, bd),
                (bw, head_y + blade_h * 0.5, -bd), (bw, head_y - blade_h * 0.5, -bd),
                (0, head_y - blade_h * 0.3, -bd), (0, head_y + blade_h * 0.3, -bd)]
        parts.append((bvl3, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]))
        tsv, tsf = _make_cone(0, head_y + blade_h * 0.3, 0, pole_r * 2, 0.15, segments=6)
        parts.append((tsv, tsf))
        hkverts = [(-0.015, head_y + 0.02, bd * 0.5), (-0.015, head_y - 0.02, bd * 0.5),
                   (-0.015, head_y + 0.02, -bd * 0.5), (-0.015, head_y - 0.02, -bd * 0.5), (-0.06, head_y - 0.01, 0)]
        parts.append((hkverts, [(0, 1, 4), (1, 3, 4), (3, 2, 4), (2, 0, 4), (0, 2, 3, 1)]))
        trail_top_y = head_y + blade_h * 0.3 + 0.15
    for angle in [0, math.pi]:
        lv, lf = _make_beveled_box(math.cos(angle) * pole_r * 0.8, head_y - 0.15,
                                    math.sin(angle) * pole_r * 0.8, 0.004, 0.07, 0.004, bevel=0.002)
        parts.append((lv, lf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Halberd_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, pole_len * 0.3, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(bw if style != "partisan" else 0.04, head_y - 0.1, 0.0))


def generate_glaive_mesh(style: str = "curved") -> MeshSpec:
    """Generate a glaive mesh -- curved blade on pole.

    Args:
        style: "curved", "naginata", or "guandao".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    pole_len, pole_r = 1.8, 0.013
    pv, pf = _make_tapered_cylinder(0, 0, 0, pole_r, pole_r * 0.9, pole_len, segs, rings=7)
    parts.append((pv, pf))
    bv, bf = _make_sphere(0, -0.015, 0, pole_r * 1.4, rings=3, sectors=6)
    parts.append((bv, bf))
    head_y = pole_len * 0.88
    bt = 0.005
    bsegs = 10
    if style == "naginata":
        blen, bw = 0.4, 0.03
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        for i in range(bsegs + 1):
            t = i / bsegs
            y = head_y + t * blen
            cx = t * t * 0.02
            w = bw * (1.0 - t * 0.5)
            bvl.extend([(cx - w * 0.3, y, bt), (cx + w, y, 0), (cx - w * 0.3, y, -bt)])
        for i in range(bsegs):
            b = i * 3
            for j in range(3):
                j2 = (j + 1) % 3
                bfl.append((b + j, b + j2, b + 3 + j2, b + 3 + j))
        bvl.append((0.02, head_y + blen + 0.02, 0))
        tb, ti = bsegs * 3, len(bvl) - 1
        for j in range(3):
            bfl.append((tb + j, tb + (j + 1) % 3, ti))
        parts.append((bvl, bfl))
        trail_top_y = head_y + blen + 0.02
    elif style == "guandao":
        blen, bw = 0.45, 0.06
        bvl2: list[tuple[float, float, float]] = []
        bfl2: list[tuple[int, ...]] = []
        for i in range(bsegs + 1):
            t = i / bsegs
            y = head_y + t * blen
            cx = math.sin(t * math.pi * 0.5) * 0.04
            w = bw * math.sin(t * math.pi * 0.8 + 0.2) * (1.0 - t * 0.3)
            w = max(w, 0.005)
            bvl2.extend([(cx, y, bt), (cx + w, y, 0), (cx, y, -bt)])
        for i in range(bsegs):
            b = i * 3
            for j in range(3):
                j2 = (j + 1) % 3
                bfl2.append((b + j, b + j2, b + 3 + j2, b + 3 + j))
        bvl2.append((0.04, head_y + blen + 0.03, 0))
        tb2, ti2 = bsegs * 3, len(bvl2) - 1
        for j in range(3):
            bfl2.append((tb2 + j, tb2 + (j + 1) % 3, ti2))
        parts.append((bvl2, bfl2))
        trail_top_y = head_y + blen + 0.03
    else:
        blen, bw = 0.35, 0.035
        bvl3: list[tuple[float, float, float]] = []
        bfl3: list[tuple[int, ...]] = []
        for i in range(bsegs + 1):
            t = i / bsegs
            y = head_y + t * blen
            cx = math.sin(t * math.pi * 0.6) * 0.05
            w = bw * (1.0 - t * 0.4)
            bvl3.extend([(cx - w * 0.3, y, bt), (cx + w, y, 0), (cx - w * 0.3, y, -bt)])
        for i in range(bsegs):
            b = i * 3
            for j in range(3):
                j2 = (j + 1) % 3
                bfl3.append((b + j, b + j2, b + 3 + j2, b + 3 + j))
        last_cx = math.sin(math.pi * 0.6) * 0.05
        bvl3.append((last_cx, head_y + blen + 0.02, 0))
        tb3, ti3 = bsegs * 3, len(bvl3) - 1
        for j in range(3):
            bfl3.append((tb3 + j, tb3 + (j + 1) % 3, ti3))
        parts.append((bvl3, bfl3))
        trail_top_y = head_y + blen + 0.02
    cv, cf = _make_torus_ring(0, head_y, 0, pole_r * 2, pole_r * 0.4, major_segments=segs, minor_segments=3)
    parts.append((cv, cf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Glaive_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, pole_len * 0.3, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, head_y, 0.0))


def _make_bow_limb(cx: float, cy: float, cz: float, length: float, curve: float,
                   limb_width: float, limb_thick: float, segments: int,
                   direction: int = 1) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a curved bow limb along Y axis."""
    verts: list[tuple[float, float, float]] = []
    faces_out: list[tuple[int, ...]] = []
    for i in range(segments + 1):
        t = i / segments
        y = cy + direction * t * length
        z = cz + math.sin(t * math.pi * 0.8) * curve
        w = limb_width * (1.0 - t * 0.6)
        d = limb_thick * (1.0 - t * 0.4)
        verts.extend([(cx - w, y, z + d), (cx + w, y, z + d), (cx + w, y, z - d), (cx - w, y, z - d)])
    for i in range(segments):
        b = i * 4
        for j in range(4):
            j2 = (j + 1) % 4
            faces_out.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
    return verts, faces_out


def generate_shortbow_mesh(style: str = "recurve") -> MeshSpec:
    """Generate a shortbow mesh with curved limbs and string.

    Args:
        style: "recurve", "flat", or "composite".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    grip_h, grip_w, grip_d = 0.12, 0.015, 0.02
    gv, gf = _make_beveled_box(0, 0, 0, grip_w, grip_h / 2, grip_d, bevel=0.004)
    parts.append((gv, gf))
    nv, nf = _make_box(0, 0.01, grip_d + 0.005, 0.005, 0.005, 0.005)
    parts.append((nv, nf))
    limb_len = 0.35
    curve = 0.06 if style == "recurve" else (0.03 if style == "flat" else 0.08)
    limb_w = 0.012 if style != "composite" else 0.015
    uv, uf = _make_bow_limb(0, grip_h / 2, 0, limb_len, curve, limb_w, 0.008, segments=8, direction=1)
    parts.append((uv, uf))
    lv, lf = _make_bow_limb(0, -grip_h / 2, 0, limb_len, curve, limb_w, 0.008, segments=8, direction=-1)
    parts.append((lv, lf))
    nock_z = math.sin(0.8 * math.pi) * curve
    for y_pos in [grip_h / 2 + limb_len, -(grip_h / 2 + limb_len)]:
        tv, tf = _make_sphere(0, y_pos, nock_z, 0.005, rings=3, sectors=4)
        parts.append((tv, tf))
    str_top = grip_h / 2 + limb_len
    str_bot = -(grip_h / 2 + limb_len)
    sv, sf = _make_tapered_cylinder(0, str_bot, nock_z * 0.15, 0.001, 0.001, str_top - str_bot, segments=4, rings=3)
    parts.append((sv, sf))
    if style == "composite":
        for yi in range(3):
            for d in [1, -1]:
                wy = d * (grip_h / 2 + limb_len * (0.2 + yi * 0.25))
                wv, wf = _make_torus_ring(0, wy, 0, limb_w * 1.3, 0.002, major_segments=6, minor_segments=3)
                parts.append((wv, wf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Shortbow_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0), trail_top=(0.0, str_top, 0.0), trail_bottom=(0.0, str_bot, 0.0))


def generate_longbow_mesh(style: str = "recurve") -> MeshSpec:
    """Generate a longbow mesh -- taller than shortbow with longer limbs.

    Args:
        style: "recurve", "english", or "elven".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    grip_h, grip_w, grip_d = 0.15, 0.018, 0.022
    gv, gf = _make_beveled_box(0, 0, 0, grip_w, grip_h / 2, grip_d, bevel=0.005)
    parts.append((gv, gf))
    nv, nf = _make_box(0, 0.01, grip_d + 0.006, 0.006, 0.006, 0.006)
    parts.append((nv, nf))
    limb_len = 0.7
    if style == "english":
        curve, limb_w = 0.02, 0.016
    elif style == "elven":
        curve, limb_w = 0.1, 0.01
    else:
        curve, limb_w = 0.08, 0.014
    uv, uf = _make_bow_limb(0, grip_h / 2, 0, limb_len, curve, limb_w, 0.009, segments=10, direction=1)
    parts.append((uv, uf))
    lv, lf = _make_bow_limb(0, -grip_h / 2, 0, limb_len, curve, limb_w, 0.009, segments=10, direction=-1)
    parts.append((lv, lf))
    nock_z = math.sin(0.8 * math.pi) * curve
    for y_pos in [grip_h / 2 + limb_len, -(grip_h / 2 + limb_len)]:
        tv, tf = _make_sphere(0, y_pos, nock_z, 0.006, rings=3, sectors=4)
        parts.append((tv, tf))
    str_top = grip_h / 2 + limb_len
    str_bot = -(grip_h / 2 + limb_len)
    sv, sf = _make_tapered_cylinder(0, str_bot, nock_z * 0.15, 0.0012, 0.0012, str_top - str_bot, segments=4, rings=4)
    parts.append((sv, sf))
    if style == "elven":
        for gi in range(3):
            gy = -grip_h * 0.3 + gi * grip_h * 0.3
            gv2, gf2 = _make_torus_ring(0, gy, 0, grip_w * 1.4, 0.003, major_segments=6, minor_segments=3)
            parts.append((gv2, gf2))
    for gi in range(4):
        gy = -grip_h * 0.35 + gi * grip_h * 0.2
        wv, wf = _make_torus_ring(0, gy, 0, grip_w * 1.15, 0.002, major_segments=6, minor_segments=3)
        parts.append((wv, wf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Longbow_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0), trail_top=(0.0, str_top, 0.0), trail_bottom=(0.0, str_bot, 0.0))


def generate_staff_magic_mesh(style: str = "gnarled") -> MeshSpec:
    """Generate a magic staff mesh -- gnarled wood with crystal/orb head.

    Args:
        style: "gnarled", "crystal", or "runic".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    shaft_len, shaft_r = 1.6, 0.016
    if style == "gnarled":
        s_segs = 12
        svl: list[tuple[float, float, float]] = []
        sfl: list[tuple[int, ...]] = []
        for ring in range(s_segs + 1):
            t = ring / s_segs
            y = t * shaft_len
            r = shaft_r * (1.0 + 0.15 * math.sin(t * math.pi * 5)) * (1.0 - t * 0.2)
            for i in range(segs):
                angle = 2 * math.pi * i / segs
                wobble = 0.003 * math.sin(angle * 3 + t * 7)
                svl.append((math.cos(angle) * (r + wobble), y, math.sin(angle) * (r + wobble)))
        for ring in range(s_segs):
            for i in range(segs):
                i2 = (i + 1) % segs
                sfl.append((ring * segs + i, ring * segs + i2, (ring + 1) * segs + i2, (ring + 1) * segs + i))
        sfl.append(tuple(i for i in range(segs - 1, -1, -1)))
        sfl.append(tuple(s_segs * segs + i for i in range(segs)))
        parts.append((svl, sfl))
        for ri in range(3):
            angle = 2 * math.pi * ri / 3
            rv, rf = _make_tapered_cylinder(math.cos(angle) * shaft_r * 2, -0.05, math.sin(angle) * shaft_r * 2,
                                            shaft_r * 0.6, shaft_r * 0.2, 0.08, segments=4, rings=2)
            parts.append((rv, rf))
        cv, cf = _make_sphere(0, shaft_len + 0.03, 0, 0.03, rings=5, sectors=8)
        parts.append((cv, cf))
        for ti in range(4):
            angle = 2 * math.pi * ti / 4
            tv, tf = _make_tapered_cylinder(math.cos(angle) * 0.018, shaft_len - 0.02, math.sin(angle) * 0.018,
                                            0.005, 0.003, 0.08, segments=4, rings=2)
            parts.append((tv, tf))
    elif style == "crystal":
        sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r * 0.85, shaft_len, segs, rings=6)
        parts.append((sv, sf))
        for ci in range(5):
            angle = 2 * math.pi * ci / 5
            tilt = 0.15 + ci * 0.05
            cx = math.sin(tilt) * math.cos(angle) * 0.02
            cz = math.sin(tilt) * math.sin(angle) * 0.02
            cv, cf = _make_cone(cx, shaft_len + ci * 0.01, cz, max(0.012 - ci * 0.001, 0.005),
                                0.06 + ci * 0.015, segments=6)
            parts.append((cv, cf))
    else:
        sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r, shaft_len, segs, rings=6)
        parts.append((sv, sf))
        for ri in range(6):
            ry = shaft_len * (0.15 + ri * 0.12)
            rv, rf = _make_torus_ring(0, ry, 0, shaft_r * 1.15, 0.003, major_segments=segs, minor_segments=3)
            parts.append((rv, rf))
        ov, of_ = _make_sphere(0, shaft_len + 0.025, 0, 0.025, rings=5, sectors=8)
        parts.append((ov, of_))
        for ci in range(3):
            angle = 2 * math.pi * ci / 3
            cv, cf = _make_tapered_cylinder(math.cos(angle) * 0.015, shaft_len - 0.01, math.sin(angle) * 0.015,
                                            0.004, 0.002, 0.04, segments=4, rings=1)
            parts.append((cv, cf))
    bv, bf = _make_sphere(0, -0.02, 0, shaft_r * 1.3, rings=3, sectors=6)
    parts.append((bv, bf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"StaffMagic_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, shaft_len * 0.35, 0.0), trail_top=(0.0, shaft_len + 0.06, 0.0),
                        trail_bottom=(0.0, 0.0, 0.0))


def generate_wand_mesh(style: str = "straight") -> MeshSpec:
    """Generate a magic wand mesh -- short shaft with ornate tip.

    Args:
        style: "straight", "twisted", or "bone".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6
    wand_len, wand_r = 0.35, 0.008
    if style == "twisted":
        t_segs = 16
        tvl: list[tuple[float, float, float]] = []
        tfl: list[tuple[int, ...]] = []
        for ring in range(t_segs + 1):
            t = ring / t_segs
            y = t * wand_len
            r = wand_r * (1.0 - t * 0.3)
            ta = t * math.pi * 3
            for i in range(segs):
                angle = 2 * math.pi * i / segs + ta
                tvl.append((math.cos(angle) * r, y, math.sin(angle) * r))
        for ring in range(t_segs):
            for i in range(segs):
                i2 = (i + 1) % segs
                tfl.append((ring * segs + i, ring * segs + i2, (ring + 1) * segs + i2, (ring + 1) * segs + i))
        tfl.append(tuple(i for i in range(segs - 1, -1, -1)))
        tfl.append(tuple(t_segs * segs + i for i in range(segs)))
        parts.append((tvl, tfl))
    elif style == "bone":
        sv, sf = _make_tapered_cylinder(0, 0, 0, wand_r * 0.9, wand_r * 0.7, wand_len, segs, rings=4)
        parts.append((sv, sf))
        for ki in range(3):
            kv, kf = _make_sphere(0, wand_len * (0.25 + ki * 0.25), 0, wand_r * 1.4, rings=3, sectors=5)
            parts.append((kv, kf))
    else:
        sv, sf = _make_tapered_cylinder(0, 0, 0, wand_r * 1.1, wand_r * 0.7, wand_len, segs, rings=4)
        parts.append((sv, sf))
    pv, pf = _make_sphere(0, -0.01, 0, wand_r * 1.6, rings=4, sectors=6)
    parts.append((pv, pf))
    for gi in range(3):
        gy = 0.02 + gi * 0.025
        gv, gf = _make_torus_ring(0, gy, 0, wand_r * 1.2, wand_r * 0.15, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    if style == "bone":
        sv2, sf2 = _make_sphere(0, wand_len + 0.012, 0, 0.012, rings=4, sectors=6)
        parts.append((sv2, sf2))
        for side in [-1, 1]:
            ev, ef = _make_sphere(side * 0.005, wand_len + 0.015, 0.008, 0.004, rings=2, sectors=4)
            parts.append((ev, ef))
    else:
        cv, cf = _make_cone(0, wand_len, 0, 0.01, 0.025, segments=6)
        parts.append((cv, cf))
        rv, rf = _make_torus_ring(0, wand_len + 0.002, 0, 0.012, 0.003, major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Wand_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, wand_len * 0.15, 0.0), trail_top=(0.0, wand_len + 0.025, 0.0),
                        trail_bottom=(0.0, wand_len * 0.5, 0.0))


def generate_throwing_knife_weapon_mesh(style: str = "balanced") -> MeshSpec:
    """Generate a balanced throwing knife mesh (weapon-class, not projectile).

    Args:
        style: "balanced", "kunai", or "star".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    if style == "kunai":
        bl = 0.18
        bw, bd = 0.02, 0.005
        bv = [(0, bl, 0), (-bw, bl * 0.3, bd), (bw, bl * 0.3, bd), (-bw, bl * 0.3, -bd), (bw, bl * 0.3, -bd),
              (0, 0, bd * 0.5), (0, 0, -bd * 0.5)]
        parts.append((bv, [(0, 1, 2), (0, 4, 3), (0, 2, 4), (0, 3, 1), (1, 5, 6, 3), (2, 4, 6, 5), (1, 3, 6, 5)]))
        rv, rf = _make_torus_ring(0, -0.03, 0, 0.015, 0.003, major_segments=8, minor_segments=3)
        parts.append((rv, rf))
        hv, hf = _make_tapered_cylinder(0, -0.03, 0, 0.008, 0.006, 0.06, segments=4, rings=2)
        parts.append((hv, hf))
        wv, wf = _make_tapered_cylinder(0, 0, 0, 0.009, 0.007, 0.05, segments=4, rings=2)
        parts.append((wv, wf))
        trail_top_y = bl
    elif style == "star":
        cr = 0.02
        cv, cf = _make_cylinder(0, -0.003, 0, cr, 0.006, segments=8)
        parts.append((cv, cf))
        for bi in range(4):
            angle = 2 * math.pi * bi / 4
            bx, bz = math.cos(angle), math.sin(angle)
            br = 0.05
            bv2 = [(bx * cr, 0.003, bz * cr), (bx * br, 0.003, bz * br),
                   (bx * cr, -0.003, bz * cr), (bx * br, -0.003, bz * br),
                   (bx * br * 0.8 + bz * 0.015, 0, bz * br * 0.8 - bx * 0.015)]
            parts.append((bv2, [(0, 1, 4), (2, 4, 3), (0, 4, 2), (1, 3, 4), (0, 2, 3, 1)]))
        trail_top_y = 0.05
    else:
        bl = 0.15
        bw, bd = 0.018, 0.004
        bv3 = [(0, bl, 0), (-bw, bl * 0.6, bd), (bw, bl * 0.6, bd), (-bw, bl * 0.6, -bd), (bw, bl * 0.6, -bd),
               (-bw * 0.6, 0, bd * 0.8), (bw * 0.6, 0, bd * 0.8), (-bw * 0.6, 0, -bd * 0.8), (bw * 0.6, 0, -bd * 0.8)]
        parts.append((bv3, [(0, 1, 2), (0, 4, 3), (0, 2, 4), (0, 3, 1), (1, 5, 6, 2), (4, 8, 7, 3),
                            (2, 6, 8, 4), (1, 3, 7, 5), (5, 7, 8, 6)]))
        hv, hf = _make_tapered_cylinder(0, -0.08, 0, bw * 0.35, bw * 0.25, 0.08, segments=6, rings=2)
        parts.append((hv, hf))
        gv, gf = _make_box(0, 0, 0, bw * 0.8, bd * 1.5, bd * 1.5)
        parts.append((gv, gf))
        pv, pf = _make_sphere(0, -0.09, 0, bw * 0.4, rings=3, sectors=5)
        parts.append((pv, pf))
        trail_top_y = bl
    verts, faces = _merge_meshes(*parts)
    grip_y = -0.03 if style != "star" else 0.0
    return _make_result(f"ThrowingKnifeWeapon_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, grip_y, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, 0.0, 0.0))


# =========================================================================
# CATEGORY 4b: DUAL-WIELD PAIRED WEAPONS
# =========================================================================


def generate_paired_daggers_mesh(style: str = "standard") -> MeshSpec:
    """Generate a pair of mirrored daggers for dual-wielding.

    Args:
        style: "standard", "curved", or "serrated".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6

    for side_x in [-0.06, 0.06]:
        mirror = -1.0 if side_x < 0 else 1.0
        # Handle
        handle_len, handle_r = 0.1, 0.01
        hv, hf = _make_tapered_cylinder(side_x, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=2)
        parts.append((hv, hf))
        # Pommel
        pv, pf = _make_sphere(side_x, -0.012, 0, handle_r * 1.4, rings=3, sectors=5)
        parts.append((pv, pf))
        # Guard -- small cross-guard
        gv, gf = _make_beveled_box(side_x, handle_len + 0.005, 0, 0.018, 0.005, 0.008, bevel=0.002)
        parts.append((gv, gf))
        # Blade
        blade_base_y = handle_len + 0.01
        blade_len = 0.18
        blade_segs, blade_thick = 6, 0.003
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = blade_base_y + t * blade_len
            w = 0.015 * (1.0 - t * 0.7)
            if style == "curved":
                x_off = side_x + mirror * math.sin(t * math.pi * 0.4) * 0.015
            elif style == "serrated":
                x_off = side_x + mirror * math.sin(t * math.pi * 6) * 0.003 * (1.0 - t)
            else:
                x_off = side_x
            bvl.extend([(x_off - w, y, blade_thick), (x_off + w, y, blade_thick),
                        (x_off + w, y, -blade_thick), (x_off - w, y, -blade_thick)])
        for i in range(blade_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        # Tip
        tip_y = blade_base_y + blade_len + 0.02
        bvl.append((side_x, tip_y, 0))
        tb = blade_segs * 4
        ti = len(bvl) - 1
        for j in range(4):
            bfl.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((bvl, bfl))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"PairedDaggers_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.04, 0.0), trail_top=(0.06, 0.31, 0.0),
                        trail_bottom=(0.06, 0.11, 0.0), dual_wield=True)


def generate_twin_swords_mesh(style: str = "standard") -> MeshSpec:
    """Generate matched pair of swords for dual-wielding.

    Args:
        style: "standard", "falcata", or "gladius".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    for side_x in [-0.07, 0.07]:
        mirror = -1.0 if side_x < 0 else 1.0
        handle_len, handle_r = 0.15, 0.013
        hv, hf = _make_tapered_cylinder(side_x, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=3)
        parts.append((hv, hf))
        pv, pf = _make_sphere(side_x, -0.018, 0, handle_r * 1.6, rings=3, sectors=6)
        parts.append((pv, pf))
        for gi in range(3):
            gy = 0.02 + gi * handle_len * 0.25
            gv, gf = _make_torus_ring(side_x, gy, 0, handle_r * 1.2, handle_r * 0.1, major_segments=segs, minor_segments=3)
            parts.append((gv, gf))
        # Guard
        guard_w = 0.035 if style != "gladius" else 0.02
        gv2, gf2 = _make_beveled_box(side_x, handle_len + 0.007, 0, guard_w, 0.007, 0.01, bevel=0.003)
        parts.append((gv2, gf2))
        # Blade
        blade_base_y = handle_len + 0.014
        if style == "gladius":
            blade_len, blade_w = 0.45, 0.025
        elif style == "falcata":
            blade_len, blade_w = 0.4, 0.03
        else:
            blade_len, blade_w = 0.5, 0.022
        blade_segs, blade_thick = 8, 0.004
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = blade_base_y + t * blade_len
            if style == "falcata":
                w = blade_w * (1.0 + t * 0.3 - t * t * 1.3)
                x_off = side_x + mirror * math.sin(t * math.pi * 0.3) * 0.02
            elif style == "gladius":
                leaf = 1.0 + 0.3 * math.sin(t * math.pi) - t * 0.3
                w = blade_w * leaf
                x_off = side_x
            else:
                w = blade_w * (1.0 - t * 0.5)
                x_off = side_x
            w = max(w, 0.003)
            bvl.extend([(x_off - w, y, blade_thick), (x_off + w, y, blade_thick),
                        (x_off + w, y, -blade_thick), (x_off - w, y, -blade_thick)])
        for i in range(blade_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        tip_y = blade_base_y + blade_len + 0.03
        bvl.append((side_x, tip_y, 0))
        tb = blade_segs * 4
        ti = len(bvl) - 1
        for j in range(4):
            bfl.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((bvl, bfl))

    verts, faces = _merge_meshes(*parts)
    trail_top_y = 0.15 + 0.014 + (0.5 if style == "standard" else 0.45 if style == "gladius" else 0.4) + 0.03
    return _make_result(f"TwinSwords_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.06, 0.0), trail_top=(0.07, trail_top_y, 0.0),
                        trail_bottom=(0.07, 0.164, 0.0), dual_wield=True)


def generate_dual_axes_mesh(style: str = "hand") -> MeshSpec:
    """Generate paired hand/throwing axes for dual-wielding.

    Args:
        style: "hand", "hatchet", or "tomahawk".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    for side_x in [-0.08, 0.08]:
        mirror = 1.0 if side_x > 0 else -1.0
        haft_len, haft_r = 0.3, 0.011
        hv, hf = _make_tapered_cylinder(side_x, 0, 0, haft_r * 1.05, haft_r * 0.9, haft_len, segs, rings=3)
        parts.append((hv, hf))
        pv, pf = _make_sphere(side_x, -0.012, 0, haft_r * 1.4, rings=3, sectors=5)
        parts.append((pv, pf))
        # Axe head
        head_y = haft_len * 0.8
        bd = 0.005
        if style == "hatchet":
            bv = [(side_x + mirror * 0.05, head_y + 0.035, bd),
                  (side_x + mirror * 0.05, head_y - 0.025, bd),
                  (side_x, head_y - 0.015, bd), (side_x, head_y + 0.02, bd),
                  (side_x + mirror * 0.05, head_y + 0.035, -bd),
                  (side_x + mirror * 0.05, head_y - 0.025, -bd),
                  (side_x, head_y - 0.015, -bd), (side_x, head_y + 0.02, -bd)]
        elif style == "tomahawk":
            bv = [(side_x + mirror * 0.045, head_y + 0.02, bd),
                  (side_x + mirror * 0.045, head_y - 0.02, bd),
                  (side_x, head_y - 0.012, bd), (side_x, head_y + 0.012, bd),
                  (side_x + mirror * 0.045, head_y + 0.02, -bd),
                  (side_x + mirror * 0.045, head_y - 0.02, -bd),
                  (side_x, head_y - 0.012, -bd), (side_x, head_y + 0.012, -bd)]
        else:
            bv = [(side_x + mirror * 0.055, head_y + 0.03, bd),
                  (side_x + mirror * 0.055, head_y - 0.03, bd),
                  (side_x, head_y - 0.018, bd), (side_x, head_y + 0.018, bd),
                  (side_x + mirror * 0.055, head_y + 0.03, -bd),
                  (side_x + mirror * 0.055, head_y - 0.03, -bd),
                  (side_x, head_y - 0.018, -bd), (side_x, head_y + 0.018, -bd)]
        bf = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
        parts.append((bv, bf))
        # Collar ring
        ev, ef = _make_torus_ring(side_x, head_y, 0, haft_r * 1.4, haft_r * 0.25, major_segments=segs, minor_segments=3)
        parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"DualAxes_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.1, 0.0), trail_top=(0.08, 0.27, 0.0),
                        trail_bottom=(0.08, 0.21, 0.0), dual_wield=True)


def generate_dual_claws_mesh(style: str = "tiger") -> MeshSpec:
    """Generate paired claw weapons for dual-wielding.

    Args:
        style: "tiger", "hook", or "katar".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6

    for side_x in [-0.06, 0.06]:
        mirror = 1.0 if side_x > 0 else -1.0
        if style == "katar":
            # H-frame grip
            grip_w, grip_h = 0.025, 0.08
            gv, gf = _make_beveled_box(side_x, grip_h / 2, 0, grip_w, grip_h / 2, 0.012, bevel=0.003)
            parts.append((gv, gf))
            # Cross bars
            for bar_y in [0.01, grip_h - 0.01]:
                bv, bf = _make_beveled_box(side_x, bar_y, 0, grip_w * 1.3, 0.004, 0.004, bevel=0.001)
                parts.append((bv, bf))
            # Single triangular blade
            blade_len = 0.2
            blade_base_y = grip_h
            bvl: list[tuple[float, float, float]] = []
            bfl_l: list[tuple[int, ...]] = []
            blade_segs = 6
            for i in range(blade_segs + 1):
                t = i / blade_segs
                y = blade_base_y + t * blade_len
                w = 0.018 * (1.0 - t * 0.8)
                bvl.extend([(side_x - w, y, 0.004), (side_x + w, y, 0.004),
                            (side_x + w, y, -0.004), (side_x - w, y, -0.004)])
            for i in range(blade_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    bfl_l.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            bvl.append((side_x, blade_base_y + blade_len + 0.02, 0))
            tb = blade_segs * 4
            ti = len(bvl) - 1
            for j in range(4):
                bfl_l.append((tb + j, tb + (j + 1) % 4, ti))
            parts.append((bvl, bfl_l))
        else:
            # Fist grip bar
            gv, gf = _make_cylinder(side_x, 0, 0, 0.012, 0.07, segments=segs)
            parts.append((gv, gf))
            # Knuckle plate
            kv, kf = _make_beveled_box(side_x, 0.07, 0, 0.02, 0.008, 0.015, bevel=0.003)
            parts.append((kv, kf))
            # Claw blades
            num_claws = 3 if style == "tiger" else 2
            for ci in range(num_claws):
                claw_z = 0.015 * (ci - (num_claws - 1) / 2.0)
                blade_len = 0.15 if style == "tiger" else 0.12
                claw_segs = 5
                cvl: list[tuple[float, float, float]] = []
                cfl: list[tuple[int, ...]] = []
                for i in range(claw_segs + 1):
                    t = i / claw_segs
                    y = 0.078 + t * blade_len
                    w = 0.005 * (1.0 - t * 0.6)
                    if style == "hook":
                        x_off = side_x + mirror * math.sin(t * math.pi * 0.6) * 0.03
                    else:
                        x_off = side_x + mirror * t * 0.005
                    cvl.extend([(x_off - w, y, claw_z + 0.002), (x_off + w, y, claw_z + 0.002),
                                (x_off + w, y, claw_z - 0.002), (x_off - w, y, claw_z - 0.002)])
                for i in range(claw_segs):
                    b = i * 4
                    for j in range(4):
                        j2 = (j + 1) % 4
                        cfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
                # Claw tip
                tip_y = 0.078 + blade_len + 0.015
                if style == "hook":
                    tip_x = side_x + mirror * math.sin(math.pi * 0.6) * 0.03
                else:
                    tip_x = side_x + mirror * 0.005
                cvl.append((tip_x, tip_y, claw_z))
                tb = claw_segs * 4
                ti = len(cvl) - 1
                for j in range(4):
                    cfl.append((tb + j, tb + (j + 1) % 4, ti))
                parts.append((cvl, cfl))

    verts, faces = _merge_meshes(*parts)
    trail_top_y = 0.3 if style == "katar" else 0.243
    return _make_result(f"DualClaws_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.035, 0.0), trail_top=(0.06, trail_top_y, 0.0),
                        trail_bottom=(0.06, 0.078, 0.0), dual_wield=True)


# =========================================================================
# CATEGORY 4c: FIST / GAUNTLET WEAPONS
# =========================================================================


def generate_brass_knuckles_mesh(style: str = "standard") -> MeshSpec:
    """Generate brass knuckles / knuckle-duster mesh.

    Args:
        style: "standard", "spiked", or "bladed".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Main frame bar (across knuckles)
    frame_w, frame_h, frame_d = 0.06, 0.012, 0.01
    fv, ff = _make_beveled_box(0, 0.04, 0, frame_w, frame_h, frame_d, bevel=0.003)
    parts.append((fv, ff))
    # Grip bar (palm side)
    gv, gf = _make_beveled_box(0, 0.0, 0, frame_w * 0.85, 0.008, frame_d * 0.8, bevel=0.002)
    parts.append((gv, gf))
    # Side connectors
    for sx in [-frame_w + 0.008, frame_w - 0.008]:
        cv, cf = _make_beveled_box(sx, 0.02, 0, 0.005, 0.02, frame_d * 0.6, bevel=0.002)
        parts.append((cv, cf))
    # Finger rings
    for fi in range(4):
        fx = -0.04 + fi * 0.027
        rv, rf = _make_torus_ring(fx, 0.04, 0, 0.012, 0.004, major_segments=segs, minor_segments=4)
        parts.append((rv, rf))

    if style == "spiked":
        for fi in range(4):
            fx = -0.04 + fi * 0.027
            sv, sf = _make_cone(fx, 0.054, 0, 0.006, 0.025, segments=5)
            parts.append((sv, sf))
    elif style == "bladed":
        bv, bf = _make_beveled_box(0, 0.065, 0, frame_w * 0.9, 0.015, 0.003, bevel=0.002)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"BrassKnuckles_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0), trail_top=(0.0, 0.065 if style != "spiked" else 0.079, 0.0),
                        trail_bottom=(0.0, 0.028, 0.0))


def generate_cestus_mesh(style: str = "leather") -> MeshSpec:
    """Generate wrapped fighting glove / cestus mesh.

    Args:
        style: "leather", "studded", or "iron".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Main glove body (tapered box)
    glove_h = 0.12
    gv, gf = _make_tapered_cylinder(0, 0, 0, 0.035, 0.03, glove_h, segs, rings=4)
    parts.append((gv, gf))
    # Wrist cuff
    wv, wf = _make_torus_ring(0, 0.0, 0, 0.038, 0.006, major_segments=segs, minor_segments=4)
    parts.append((wv, wf))
    # Finger knuckle ridge
    kv, kf = _make_beveled_box(0, glove_h - 0.01, 0, 0.032, 0.008, 0.025, bevel=0.004)
    parts.append((kv, kf))

    if style == "studded":
        for si in range(6):
            s_angle = 2.0 * math.pi * si / 6
            sx = math.cos(s_angle) * 0.033
            sz = math.sin(s_angle) * 0.033
            sv, sf = _make_sphere(sx, glove_h * 0.5 + si * 0.005, sz, 0.005, rings=3, sectors=4)
            parts.append((sv, sf))
    elif style == "iron":
        # Metal plate overlays
        for pi in range(3):
            py = 0.03 + pi * 0.03
            pv, pf = _make_beveled_box(0, py, 0.028, 0.025, 0.012, 0.003, bevel=0.002)
            parts.append((pv, pf))
        # Iron knuckle guard
        igv, igf = _make_beveled_box(0, glove_h, 0, 0.035, 0.006, 0.028, bevel=0.003)
        parts.append((igv, igf))

    # Wrap bands
    for wi in range(3):
        wy = 0.02 + wi * 0.035
        wbv, wbf = _make_torus_ring(0, wy, 0, 0.036, 0.003, major_segments=segs, minor_segments=3)
        parts.append((wbv, wbf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cestus_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0), trail_top=(0.0, glove_h, 0.0),
                        trail_bottom=(0.0, glove_h * 0.7, 0.0))


def generate_bladed_gauntlet_mesh(style: str = "wrist_blade") -> MeshSpec:
    """Generate a gauntlet with integrated blades.

    Args:
        style: "wrist_blade", "finger_blades", or "claw_tips".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Forearm guard
    arm_h = 0.18
    av, af = _make_tapered_cylinder(0, 0, 0, 0.035, 0.03, arm_h, segs, rings=4)
    parts.append((av, af))
    # Wrist ring
    wv, wf = _make_torus_ring(0, 0, 0, 0.038, 0.005, major_segments=segs, minor_segments=4)
    parts.append((wv, wf))
    # Hand section
    hv, hf = _make_tapered_cylinder(0, arm_h, 0, 0.03, 0.025, 0.08, segs, rings=3)
    parts.append((hv, hf))
    # Knuckle guard
    kv, kf = _make_beveled_box(0, arm_h + 0.07, 0, 0.028, 0.006, 0.02, bevel=0.003)
    parts.append((kv, kf))

    blade_top_y = arm_h + 0.08
    if style == "wrist_blade":
        # Single retractable blade from top of forearm
        blade_len = 0.22
        blade_segs = 6
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        for i in range(blade_segs + 1):
            t = i / blade_segs
            y = arm_h + 0.08 + t * blade_len
            w = 0.012 * (1.0 - t * 0.7)
            bvl.extend([(-w, y, 0.003), (w, y, 0.003), (w, y, -0.003), (-w, y, -0.003)])
        for i in range(blade_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        bvl.append((0, arm_h + 0.08 + blade_len + 0.02, 0))
        tb = blade_segs * 4
        ti = len(bvl) - 1
        for j in range(4):
            bfl.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((bvl, bfl))
        blade_top_y = arm_h + 0.08 + blade_len + 0.02
    elif style == "finger_blades":
        for fi in range(4):
            fz = -0.015 + fi * 0.01
            blade_len = 0.1
            fvl: list[tuple[float, float, float]] = []
            ffl: list[tuple[int, ...]] = []
            f_segs = 4
            for i in range(f_segs + 1):
                t = i / f_segs
                y = arm_h + 0.08 + t * blade_len
                w = 0.004 * (1.0 - t * 0.6)
                fvl.extend([(-w, y, fz + 0.002), (w, y, fz + 0.002),
                            (w, y, fz - 0.002), (-w, y, fz - 0.002)])
            for i in range(f_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    ffl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            fvl.append((0, arm_h + 0.08 + blade_len + 0.01, fz))
            tb = f_segs * 4
            ti = len(fvl) - 1
            for j in range(4):
                ffl.append((tb + j, tb + (j + 1) % 4, ti))
            parts.append((fvl, ffl))
        blade_top_y = arm_h + 0.08 + 0.11
    else:  # claw_tips
        for ci in range(3):
            cz = -0.01 + ci * 0.01
            claw_len = 0.08
            c_segs = 4
            cvl: list[tuple[float, float, float]] = []
            cfl: list[tuple[int, ...]] = []
            for i in range(c_segs + 1):
                t = i / c_segs
                y = arm_h + 0.08 + t * claw_len
                x_off = math.sin(t * math.pi * 0.4) * 0.015
                w = 0.005 * (1.0 - t * 0.5)
                cvl.extend([(x_off - w, y, cz + 0.002), (x_off + w, y, cz + 0.002),
                            (x_off + w, y, cz - 0.002), (x_off - w, y, cz - 0.002)])
            for i in range(c_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    cfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            tip_x = math.sin(math.pi * 0.4) * 0.015
            cvl.append((tip_x, arm_h + 0.08 + claw_len + 0.01, cz))
            tb = c_segs * 4
            ti = len(cvl) - 1
            for j in range(4):
                cfl.append((tb + j, tb + (j + 1) % 4, ti))
            parts.append((cvl, cfl))
        blade_top_y = arm_h + 0.08 + 0.09

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"BladedGauntlet_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0), trail_top=(0.0, blade_top_y, 0.0),
                        trail_bottom=(0.0, arm_h + 0.08, 0.0))


def generate_iron_fist_mesh(style: str = "standard") -> MeshSpec:
    """Generate a heavy metal fist weapon.

    Args:
        style: "standard", "hammer_fist", or "spiked".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Forearm brace
    brace_h = 0.15
    bv, bf = _make_tapered_cylinder(0, 0, 0, 0.032, 0.028, brace_h, segs, rings=3)
    parts.append((bv, bf))
    # Wrist joint
    wv, wf = _make_torus_ring(0, brace_h, 0, 0.03, 0.008, major_segments=segs, minor_segments=4)
    parts.append((wv, wf))

    fist_base_y = brace_h + 0.01
    if style == "hammer_fist":
        # Oversized rectangular hammer head on fist
        hv, hf = _make_beveled_box(0, fist_base_y + 0.04, 0, 0.04, 0.04, 0.035, bevel=0.005)
        parts.append((hv, hf))
        # Flat striking face
        sv, sf = _make_beveled_box(0, fist_base_y + 0.08, 0, 0.035, 0.005, 0.03, bevel=0.003)
        parts.append((sv, sf))
        trail_top_y = fist_base_y + 0.085
    elif style == "spiked":
        # Round fist with spikes
        fv, ff = _make_sphere(0, fist_base_y + 0.035, 0, 0.035, rings=5, sectors=8)
        parts.append((fv, ff))
        # Spikes radiating out
        for si in range(6):
            s_angle = 2.0 * math.pi * si / 6
            sx = math.cos(s_angle) * 0.03
            sz = math.sin(s_angle) * 0.03
            sv, sf = _make_cone(sx, fist_base_y + 0.035 + abs(math.sin(s_angle)) * 0.01, sz,
                                0.008, 0.03, segments=5)
            parts.append((sv, sf))
        # Top spike
        tv, tf = _make_cone(0, fist_base_y + 0.07, 0, 0.008, 0.035, segments=5)
        parts.append((tv, tf))
        trail_top_y = fist_base_y + 0.105
    else:
        # Standard iron fist -- rounded box
        fv, ff = _make_beveled_box(0, fist_base_y + 0.035, 0, 0.035, 0.035, 0.03, bevel=0.006)
        parts.append((fv, ff))
        # Knuckle ridge
        kv, kf = _make_beveled_box(0, fist_base_y + 0.065, 0, 0.032, 0.006, 0.025, bevel=0.003)
        parts.append((kv, kf))
        trail_top_y = fist_base_y + 0.071

    # Straps
    for si in range(2):
        sy = 0.03 + si * 0.06
        sv2, sf2 = _make_torus_ring(0, sy, 0, 0.034, 0.004, major_segments=segs, minor_segments=3)
        parts.append((sv2, sf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"IronFist_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0), trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, fist_base_y, 0.0))


# =========================================================================
# CATEGORY 4d: RAPIERS / THRUSTING SWORDS
# =========================================================================


def generate_rapier_mesh(style: str = "standard") -> MeshSpec:
    """Generate a rapier with thin blade and swept hilt.

    Args:
        style: "standard", "ornate", or "basket_hilt".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Handle -- wire-wrapped grip
    handle_len, handle_r = 0.14, 0.012
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.05, handle_r * 0.95, handle_len, segs, rings=3)
    parts.append((hv, hf))
    # Pommel -- faceted
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 2.0, rings=4, sectors=6)
    parts.append((pv, pf))
    # Grip wraps
    for gi in range(5):
        gy = 0.015 + gi * handle_len * 0.18
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.15, handle_r * 0.08, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))

    guard_y = handle_len
    if style == "basket_hilt":
        # Basket guard -- series of curved bars
        for bi in range(6):
            b_angle = 2.0 * math.pi * bi / 6
            bar_r = 0.04
            bar_segs = 6
            bvl: list[tuple[float, float, float]] = []
            bfl_l: list[tuple[int, ...]] = []
            for i in range(bar_segs + 1):
                t = i / bar_segs
                arc_angle = t * math.pi * 0.7
                bx = math.cos(b_angle) * bar_r * math.sin(arc_angle)
                bz = math.sin(b_angle) * bar_r * math.sin(arc_angle)
                by = guard_y + math.cos(arc_angle) * 0.03
                bvl.extend([(bx - 0.003, by, bz - 0.003), (bx + 0.003, by, bz - 0.003),
                            (bx + 0.003, by, bz + 0.003), (bx - 0.003, by, bz + 0.003)])
            for i in range(bar_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    bfl_l.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            parts.append((bvl, bfl_l))
    elif style == "ornate":
        # Elaborate swept guard with quillons + knuckle bow
        gv2, gf2 = _make_beveled_box(0, guard_y + 0.006, 0, 0.05, 0.006, 0.008, bevel=0.003)
        parts.append((gv2, gf2))
        # Knuckle bow
        bow_segs = 8
        bvl2: list[tuple[float, float, float]] = []
        bfl2: list[tuple[int, ...]] = []
        for i in range(bow_segs + 1):
            t = i / bow_segs
            arc = t * math.pi
            bx = math.sin(arc) * 0.03
            by = guard_y + 0.006 - math.cos(arc) * 0.04
            bvl2.extend([(bx - 0.003, by, 0.003), (bx + 0.003, by, 0.003),
                         (bx + 0.003, by, -0.003), (bx - 0.003, by, -0.003)])
        for i in range(bow_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl2.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        parts.append((bvl2, bfl2))
        # Decorative rings on quillons
        for qx in [-0.04, 0.04]:
            rv, rf = _make_torus_ring(qx, guard_y + 0.006, 0, 0.008, 0.003, major_segments=6, minor_segments=3)
            parts.append((rv, rf))
    else:
        # Standard swept guard
        gv2, gf2 = _make_beveled_box(0, guard_y + 0.006, 0, 0.04, 0.006, 0.01, bevel=0.003)
        parts.append((gv2, gf2))
        # Simple knuckle guard
        bow_segs = 6
        bvl3: list[tuple[float, float, float]] = []
        bfl3: list[tuple[int, ...]] = []
        for i in range(bow_segs + 1):
            t = i / bow_segs
            arc = t * math.pi * 0.8
            bx = math.sin(arc) * 0.025
            by = guard_y - math.cos(arc) * 0.035
            bvl3.extend([(bx - 0.003, by, 0.003), (bx + 0.003, by, 0.003),
                         (bx + 0.003, by, -0.003), (bx - 0.003, by, -0.003)])
        for i in range(bow_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl3.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        parts.append((bvl3, bfl3))

    # Thin blade -- diamond cross section
    blade_base_y = guard_y + 0.012
    blade_len = 0.8
    blade_segs = 14
    blade_w_base = 0.01
    bvl_b: list[tuple[float, float, float]] = []
    bfl_b: list[tuple[int, ...]] = []
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * blade_len
        w = blade_w_base * (1.0 - t * 0.6)
        d = 0.005 * (1.0 - t * 0.5)
        # Diamond cross-section: 4 points
        bvl_b.extend([(0, y, d), (w, y, 0), (0, y, -d), (-w, y, 0)])
    for i in range(blade_segs):
        b = i * 4
        for j in range(4):
            j2 = (j + 1) % 4
            bfl_b.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
    # Tip
    tip_y = blade_base_y + blade_len + 0.03
    bvl_b.append((0, tip_y, 0))
    tb = blade_segs * 4
    ti = len(bvl_b) - 1
    for j in range(4):
        bfl_b.append((tb + j, tb + (j + 1) % 4, ti))
    parts.append((bvl_b, bfl_b))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Rapier_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.4, 0.0),
                        trail_top=(0.0, tip_y, 0.0),
                        trail_bottom=(0.0, blade_base_y, 0.0))


def generate_estoc_mesh(style: str = "standard") -> MeshSpec:
    """Generate an estoc -- stiff thrusting sword with triangular cross-section.

    Args:
        style: "standard", "heavy", or "light".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    if style == "heavy":
        handle_len, handle_r = 0.22, 0.015
    elif style == "light":
        handle_len, handle_r = 0.14, 0.011
    else:
        handle_len, handle_r = 0.18, 0.013

    # Handle
    hv, hf = _make_tapered_cylinder(0, 0, 0, handle_r * 1.1, handle_r * 0.9, handle_len, segs, rings=3)
    parts.append((hv, hf))
    # Pommel
    pv, pf = _make_sphere(0, -0.02, 0, handle_r * 1.8, rings=4, sectors=6)
    parts.append((pv, pf))
    # Grip wraps
    for gi in range(4):
        gy = 0.02 + gi * handle_len * 0.2
        gv, gf = _make_torus_ring(0, gy, 0, handle_r * 1.2, handle_r * 0.1, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    # Guard -- simple cross
    gv2, gf2 = _make_beveled_box(0, handle_len + 0.007, 0, 0.035, 0.007, 0.01, bevel=0.003)
    parts.append((gv2, gf2))

    # Blade -- triangular cross-section (3 verts per ring)
    blade_base_y = handle_len + 0.014
    if style == "heavy":
        blade_len, blade_w = 0.75, 0.016
    elif style == "light":
        blade_len, blade_w = 0.6, 0.01
    else:
        blade_len, blade_w = 0.7, 0.013

    blade_segs = 10
    bvl: list[tuple[float, float, float]] = []
    bfl: list[tuple[int, ...]] = []
    for i in range(blade_segs + 1):
        t = i / blade_segs
        y = blade_base_y + t * blade_len
        w = blade_w * (1.0 - t * 0.7)
        d = w * 0.866  # equilateral triangle depth
        bvl.extend([(0, y, d * 0.667), (-w, y, -d * 0.333), (w, y, -d * 0.333)])
    for i in range(blade_segs):
        b = i * 3
        for j in range(3):
            j2 = (j + 1) % 3
            bfl.append((b + j, b + j2, b + 3 + j2, b + 3 + j))
    # Tip
    tip_y = blade_base_y + blade_len + 0.03
    bvl.append((0, tip_y, 0))
    tb = blade_segs * 3
    ti = len(bvl) - 1
    for j in range(3):
        bfl.append((tb + j, tb + (j + 1) % 3, ti))
    parts.append((bvl, bfl))

    # Ricasso / blade reinforcement near base
    rv, rf = _make_beveled_box(0, blade_base_y + 0.03, 0, blade_w * 1.1, 0.03, blade_w * 0.6, bevel=0.002)
    parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Estoc_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_len * 0.4, 0.0),
                        trail_top=(0.0, tip_y, 0.0),
                        trail_bottom=(0.0, blade_base_y, 0.0))


# =========================================================================
# CATEGORY 4e: THROWING WEAPONS
# =========================================================================


def generate_javelin_mesh(style: str = "standard") -> MeshSpec:
    """Generate a javelin -- heavy thrown spear.

    Args:
        style: "standard", "barbed", or "fire".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    shaft_len, shaft_r = 1.2, 0.01
    hv, hf = _make_tapered_cylinder(0, 0, 0, shaft_r * 1.05, shaft_r * 0.9, shaft_len, segs, rings=6)
    parts.append((hv, hf))
    # Grip wrap at balance point
    for gi in range(3):
        gy = shaft_len * 0.4 + gi * 0.03
        gv, gf = _make_torus_ring(0, gy, 0, shaft_r * 1.3, shaft_r * 0.15, major_segments=segs, minor_segments=3)
        parts.append((gv, gf))
    # Rear stabilizer fin (simple)
    fv, ff = _make_beveled_box(0, 0.02, 0, 0.003, 0.04, 0.015, bevel=0.001)
    parts.append((fv, ff))

    # Head
    head_base_y = shaft_len
    if style == "barbed":
        # Barbed head with backward-pointing hooks
        head_len = 0.12
        head_w = 0.02
        bvl: list[tuple[float, float, float]] = []
        bfl: list[tuple[int, ...]] = []
        h_segs = 5
        for i in range(h_segs + 1):
            t = i / h_segs
            y = head_base_y + t * head_len
            w = head_w * (1.0 - t * 0.8)
            if t > 0.3 and t < 0.6:
                w *= 1.4  # Barb bulge
            bvl.extend([(-w, y, 0.004), (w, y, 0.004), (w, y, -0.004), (-w, y, -0.004)])
        for i in range(h_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                bfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        bvl.append((0, head_base_y + head_len + 0.02, 0))
        tb = h_segs * 4
        ti = len(bvl) - 1
        for j in range(4):
            bfl.append((tb + j, tb + (j + 1) % 4, ti))
        parts.append((bvl, bfl))
        # Barb fins
        for bx_sign in [-1, 1]:
            barb_v = [(bx_sign * 0.015, head_base_y + head_len * 0.5, 0.003),
                      (bx_sign * 0.03, head_base_y + head_len * 0.3, 0.003),
                      (bx_sign * 0.015, head_base_y + head_len * 0.35, 0.003),
                      (bx_sign * 0.015, head_base_y + head_len * 0.5, -0.003),
                      (bx_sign * 0.03, head_base_y + head_len * 0.3, -0.003),
                      (bx_sign * 0.015, head_base_y + head_len * 0.35, -0.003)]
            parts.append((barb_v, [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (0, 2, 5, 3)]))
        trail_top_y = head_base_y + head_len + 0.02
    elif style == "fire":
        # Wider leaf-shaped head with oil channels
        cv, cf = _make_cone(0, head_base_y, 0, 0.018, 0.15, segments=8)
        parts.append((cv, cf))
        # Wrap for fire material
        for wi in range(2):
            wy = head_base_y + 0.02 + wi * 0.04
            wv, wf = _make_torus_ring(0, wy, 0, 0.02, 0.004, major_segments=segs, minor_segments=3)
            parts.append((wv, wf))
        trail_top_y = head_base_y + 0.15
    else:
        # Standard conical head
        cv, cf = _make_cone(0, head_base_y, 0, 0.015, 0.12, segments=8)
        parts.append((cv, cf))
        # Binding ring
        rv, rf = _make_torus_ring(0, head_base_y, 0, shaft_r * 1.5, shaft_r * 0.3, major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
        trail_top_y = head_base_y + 0.12

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Javelin_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, shaft_len * 0.4, 0.0),
                        trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, head_base_y, 0.0))


def generate_throwing_axe_mesh(style: str = "tomahawk") -> MeshSpec:
    """Generate a balanced throwing axe.

    Args:
        style: "tomahawk", "francisca", or "double".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    haft_len, haft_r = 0.28, 0.01
    hv, hf = _make_tapered_cylinder(0, 0, 0, haft_r * 1.05, haft_r * 0.9, haft_len, segs, rings=3)
    parts.append((hv, hf))
    pv, pf = _make_sphere(0, -0.012, 0, haft_r * 1.4, rings=3, sectors=5)
    parts.append((pv, pf))

    head_y = haft_len * 0.85
    bd = 0.005
    if style == "francisca":
        # Curved forward-weighted head
        f_segs = 8
        fvl: list[tuple[float, float, float]] = []
        ffl: list[tuple[int, ...]] = []
        for i in range(f_segs + 1):
            t = i / f_segs
            angle = (t - 0.5) * math.pi * 0.7
            x_o = math.cos(angle) * 0.06
            y_o = head_y + math.sin(angle) * 0.04
            x_i = math.cos(angle) * 0.015
            y_i = head_y + math.sin(angle) * 0.01
            fvl.extend([(x_o, y_o, bd), (x_i, y_i, bd), (x_i, y_i, -bd), (x_o, y_o, -bd)])
        for i in range(f_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                ffl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        parts.append((fvl, ffl))
    elif style == "double":
        # Double-bladed throwing axe
        for side in [1, -1]:
            bv = [(side * 0.05, head_y + 0.025, bd), (side * 0.05, head_y - 0.025, bd),
                  (0, head_y - 0.012, bd), (0, head_y + 0.012, bd),
                  (side * 0.05, head_y + 0.025, -bd), (side * 0.05, head_y - 0.025, -bd),
                  (0, head_y - 0.012, -bd), (0, head_y + 0.012, -bd)]
            bf = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
            parts.append((bv, bf))
    else:  # tomahawk
        bv = [(0.05, head_y + 0.022, bd), (0.05, head_y - 0.022, bd),
              (0, head_y - 0.012, bd), (0, head_y + 0.012, bd),
              (0.05, head_y + 0.022, -bd), (0.05, head_y - 0.022, -bd),
              (0, head_y - 0.012, -bd), (0, head_y + 0.012, -bd)]
        bf = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
        parts.append((bv, bf))

    # Collar ring
    ev, ef = _make_torus_ring(0, head_y, 0, haft_r * 1.4, haft_r * 0.25, major_segments=segs, minor_segments=3)
    parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"ThrowingAxe_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, haft_len * 0.3, 0.0),
                        trail_top=(0.05, head_y + 0.025, 0.0),
                        trail_bottom=(0.0, head_y - 0.025, 0.0))


def generate_shuriken_mesh(style: str = "four_point") -> MeshSpec:
    """Generate a throwing star / shuriken.

    Args:
        style: "four_point", "six_point", or "circular".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    center_r = 0.015
    thick = 0.003
    # Central disc
    cv, cf = _make_cylinder(0, -thick, 0, center_r, thick * 2, segments=12)
    parts.append((cv, cf))

    if style == "circular":
        # Circular blade ring with serrations
        ring_r = 0.06
        ring_segs = 24
        rvl: list[tuple[float, float, float]] = []
        rfl: list[tuple[int, ...]] = []
        for i in range(ring_segs):
            angle = 2.0 * math.pi * i / ring_segs
            serration = 0.005 * (1 if i % 2 == 0 else -1)
            outer_r = ring_r + serration
            inner_r = ring_r - 0.01
            rvl.extend([(math.cos(angle) * outer_r, thick, math.sin(angle) * outer_r),
                        (math.cos(angle) * inner_r, thick, math.sin(angle) * inner_r),
                        (math.cos(angle) * inner_r, -thick, math.sin(angle) * inner_r),
                        (math.cos(angle) * outer_r, -thick, math.sin(angle) * outer_r)])
        for i in range(ring_segs):
            b = i * 4
            nb = ((i + 1) % ring_segs) * 4
            for j in range(4):
                j2 = (j + 1) % 4
                rfl.append((b + j, b + j2, nb + j2, nb + j))
        parts.append((rvl, rfl))
    else:
        num_points = 4 if style == "four_point" else 6
        blade_r = 0.055
        for pi in range(num_points):
            angle = 2.0 * math.pi * pi / num_points
            ca, sa = math.cos(angle), math.sin(angle)
            # Each blade is a flattened wedge
            tip_x, tip_z = ca * blade_r, sa * blade_r
            # Perpendicular direction for blade width
            px, pz = -sa * 0.012, ca * 0.012
            base_x, base_z = ca * center_r, sa * center_r
            bv = [(base_x + px, thick, base_z + pz),
                  (base_x - px, thick, base_z - pz),
                  (tip_x, thick, tip_z),
                  (base_x + px, -thick, base_z + pz),
                  (base_x - px, -thick, base_z - pz),
                  (tip_x, -thick, tip_z)]
            bf = [(0, 1, 2), (5, 4, 3),
                  (0, 3, 4, 1), (1, 4, 5, 2), (0, 2, 5, 3)]
            parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Shuriken_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0),
                        trail_top=(0.0, thick, 0.055),
                        trail_bottom=(0.0, -thick, -0.055))


def generate_bola_mesh(style: str = "standard") -> MeshSpec:
    """Generate a bola -- weighted rope/chain weapon.

    Args:
        style: "standard", "chain", or "spiked".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    num_weights = 3
    rope_len = 0.25
    for wi in range(num_weights):
        angle = 2.0 * math.pi * wi / num_weights
        wx = math.cos(angle) * rope_len
        wz = math.sin(angle) * rope_len
        # Weight ball
        if style == "spiked":
            sv, sf = _make_sphere(wx, 0, wz, 0.025, rings=5, sectors=6)
            parts.append((sv, sf))
            for si in range(4):
                s_a = 2.0 * math.pi * si / 4
                sx = wx + math.cos(s_a) * 0.02
                sz = wz + math.sin(s_a) * 0.02
                spike_v, spike_f = _make_cone(sx, 0, sz, 0.006, 0.02, segments=4)
                parts.append((spike_v, spike_f))
        else:
            w_r = 0.02 if style == "standard" else 0.018
            wv, wf = _make_sphere(wx, 0, wz, w_r, rings=4, sectors=6)
            parts.append((wv, wf))

        # Rope/chain segments connecting to center
        rope_segs = 6
        for ri in range(rope_segs):
            t = ri / rope_segs
            rx = wx * t
            rz = wz * t
            if style == "chain":
                lv, lf = _make_torus_ring(rx, 0, rz, 0.006, 0.002, major_segments=6, minor_segments=3)
            else:
                lv, lf = _make_cylinder(rx, -0.003, rz, 0.003, 0.006, segments=4)
            parts.append((lv, lf))

    # Central knot
    cv, cf = _make_sphere(0, 0, 0, 0.012, rings=4, sectors=6)
    parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bola_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, 0.0, 0.0),
                        trail_top=(0.0, 0.025, rope_len),
                        trail_bottom=(0.0, -0.025, -rope_len))


# =========================================================================
# CATEGORY 4f: OFF-HAND FOCUS ITEMS
# =========================================================================


def generate_orb_focus_mesh(style: str = "crystal") -> MeshSpec:
    """Generate a mage's focus orb for off-hand.

    Args:
        style: "crystal", "elemental", or "void".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10

    # Handle / grip cradle
    cradle_h = 0.08
    cv, cf = _make_tapered_cylinder(0, 0, 0, 0.012, 0.018, cradle_h, segs, rings=3)
    parts.append((cv, cf))
    # Cradle prongs
    for pi in range(4):
        p_angle = 2.0 * math.pi * pi / 4
        px = math.cos(p_angle) * 0.015
        pz = math.sin(p_angle) * 0.015
        prong_segs = 4
        pvl: list[tuple[float, float, float]] = []
        pfl: list[tuple[int, ...]] = []
        for i in range(prong_segs + 1):
            t = i / prong_segs
            y = cradle_h + t * 0.04
            r_off = 0.015 + math.sin(t * math.pi) * 0.01
            vx = math.cos(p_angle) * r_off
            vz = math.sin(p_angle) * r_off
            pvl.extend([(vx - 0.003, y, vz), (vx + 0.003, y, vz),
                        (vx, y, vz + 0.003), (vx, y, vz - 0.003)])
        for i in range(prong_segs):
            b = i * 4
            for j in range(4):
                j2 = (j + 1) % 4
                pfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
        parts.append((pvl, pfl))

    orb_y = cradle_h + 0.04
    orb_r = 0.04
    if style == "crystal":
        # Faceted crystal orb
        ov, of = _make_sphere(0, orb_y, 0, orb_r, rings=6, sectors=8)
        parts.append((ov, of))
        # Inner crystal facets -- smaller sphere
        iv, i_f = _make_sphere(0, orb_y, 0, orb_r * 0.6, rings=4, sectors=6)
        parts.append((iv, i_f))
    elif style == "elemental":
        # Orb with elemental swirl bands
        ov, of = _make_sphere(0, orb_y, 0, orb_r, rings=7, sectors=10)
        parts.append((ov, of))
        # Swirl ring bands
        for ri in range(3):
            r_angle = math.pi * 0.3 * (ri - 1)
            ry = orb_y + math.sin(r_angle) * orb_r * 0.5
            rr = math.cos(r_angle) * orb_r * 0.8
            rv, rf = _make_torus_ring(0, ry, 0, max(rr, 0.01), 0.003, major_segments=segs, minor_segments=3)
            parts.append((rv, rf))
    else:  # void
        # Dark sphere with cracks
        ov, of = _make_sphere(0, orb_y, 0, orb_r * 1.1, rings=6, sectors=8)
        parts.append((ov, of))
        # Void tendrils
        for ti in range(3):
            t_angle = 2.0 * math.pi * ti / 3
            tv, tf = _make_cone(
                math.cos(t_angle) * orb_r * 0.8, orb_y + 0.01, math.sin(t_angle) * orb_r * 0.8,
                0.005, 0.04, segments=4)
            parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"OrbFocus_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, cradle_h * 0.3, 0.0),
                        trail_top=(0.0, orb_y + orb_r, 0.0),
                        trail_bottom=(0.0, orb_y - orb_r, 0.0),
                        offhand=True)


def generate_skull_fetish_mesh(style: str = "human") -> MeshSpec:
    """Generate a skull fetish -- necromancer off-hand focus.

    Args:
        style: "human", "beast", or "demon".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Bone handle
    handle_h = 0.15
    hv, hf = _make_tapered_cylinder(0, 0, 0, 0.01, 0.008, handle_h, segs, rings=3)
    parts.append((hv, hf))
    # Wrapping sinew
    for wi in range(3):
        wy = 0.02 + wi * 0.04
        wv, wf = _make_torus_ring(0, wy, 0, 0.012, 0.003, major_segments=segs, minor_segments=3)
        parts.append((wv, wf))

    skull_y = handle_h + 0.01
    if style == "beast":
        # Elongated beast skull with snout
        sv, sf = _make_beveled_box(0, skull_y + 0.03, 0, 0.03, 0.025, 0.025, bevel=0.008)
        parts.append((sv, sf))
        # Snout
        mv, mf = _make_tapered_cylinder(0, skull_y + 0.01, 0.03, 0.015, 0.008, 0.04, segs, rings=2)
        parts.append((mv, mf))
        # Horns
        for hx in [-0.025, 0.025]:
            horn_v, horn_f = _make_cone(hx, skull_y + 0.05, 0, 0.008, 0.06, segments=5)
            parts.append((horn_v, horn_f))
        # Eye sockets
        for ex in [-0.012, 0.012]:
            ev, ef = _make_sphere(ex, skull_y + 0.04, 0.02, 0.006, rings=3, sectors=4)
            parts.append((ev, ef))
        trail_top_y = skull_y + 0.11
    elif style == "demon":
        # Wide demonic skull with large horns
        sv, sf = _make_sphere(0, skull_y + 0.03, 0, 0.035, rings=5, sectors=8)
        parts.append((sv, sf))
        # Large curved horns
        for hx_sign in [-1, 1]:
            horn_segs = 6
            hvl: list[tuple[float, float, float]] = []
            hfl: list[tuple[int, ...]] = []
            for i in range(horn_segs + 1):
                t = i / horn_segs
                hy = skull_y + 0.05 + t * 0.08
                hx = hx_sign * (0.03 + t * 0.03)
                hr = 0.008 * (1.0 - t * 0.6)
                hvl.extend([(hx - hr, hy, hr), (hx + hr, hy, hr), (hx + hr, hy, -hr), (hx - hr, hy, -hr)])
            for i in range(horn_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    hfl.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            hvl.append((hx_sign * 0.06, skull_y + 0.14, 0))
            tb = horn_segs * 4
            ti = len(hvl) - 1
            for j in range(4):
                hfl.append((tb + j, tb + (j + 1) % 4, ti))
            parts.append((hvl, hfl))
        # Jaw
        jv, jf = _make_beveled_box(0, skull_y + 0.005, 0.02, 0.025, 0.008, 0.015, bevel=0.004)
        parts.append((jv, jf))
        trail_top_y = skull_y + 0.14
    else:  # human
        # Human skull shape
        sv, sf = _make_sphere(0, skull_y + 0.03, 0, 0.03, rings=5, sectors=8)
        parts.append((sv, sf))
        # Jaw
        jv, jf = _make_beveled_box(0, skull_y + 0.005, 0.015, 0.02, 0.01, 0.012, bevel=0.004)
        parts.append((jv, jf))
        # Eye sockets
        for ex in [-0.012, 0.012]:
            ev, ef = _make_sphere(ex, skull_y + 0.035, 0.025, 0.007, rings=3, sectors=4)
            parts.append((ev, ef))
        trail_top_y = skull_y + 0.06

    # Dangling trinkets / bones
    for di in range(2):
        dx = -0.015 + di * 0.03
        dv, df = _make_cylinder(dx, -0.02, 0, 0.003, 0.04, segments=4)
        parts.append((dv, df))
        bead_v, bead_f = _make_sphere(dx, -0.025, 0, 0.005, rings=3, sectors=4)
        parts.append((bead_v, bead_f))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"SkullFetish_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, handle_h * 0.4, 0.0),
                        trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, skull_y, 0.0),
                        offhand=True)


def generate_holy_symbol_mesh(style: str = "pendant") -> MeshSpec:
    """Generate a holy symbol -- paladin off-hand focus.

    Args:
        style: "pendant", "reliquary", or "chalice".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    if style == "chalice":
        # Stem
        sv, sf = _make_tapered_cylinder(0, 0, 0, 0.015, 0.008, 0.1, segs, rings=3)
        parts.append((sv, sf))
        # Base
        bv, bf = _make_cylinder(0, -0.005, 0, 0.03, 0.005, segments=segs)
        parts.append((bv, bf))
        # Cup bowl
        cup_profile = [(0.01, 0.1), (0.025, 0.12), (0.035, 0.16), (0.035, 0.2), (0.03, 0.22)]
        cupv, cupf = _make_lathe(cup_profile, segments=segs, close_bottom=True)
        parts.append((cupv, cupf))
        # Decorative ring
        rv, rf = _make_torus_ring(0, 0.1, 0, 0.018, 0.004, major_segments=segs, minor_segments=4)
        parts.append((rv, rf))
        grip_y = 0.05
        trail_top_y = 0.22
        trail_bottom_y = 0.0
    elif style == "reliquary":
        # Handle
        hv, hf = _make_tapered_cylinder(0, 0, 0, 0.01, 0.008, 0.1, segs, rings=2)
        parts.append((hv, hf))
        # Reliquary box on top
        rv, rf = _make_beveled_box(0, 0.13, 0, 0.03, 0.03, 0.02, bevel=0.005)
        parts.append((rv, rf))
        # Cross on front
        crv1, crf1 = _make_beveled_box(0, 0.13, 0.022, 0.004, 0.018, 0.002, bevel=0.001)
        parts.append((crv1, crf1))
        crv2, crf2 = _make_beveled_box(0, 0.14, 0.022, 0.012, 0.004, 0.002, bevel=0.001)
        parts.append((crv2, crf2))
        # Decorative corners
        for cx, cy_off in [(-0.025, -0.025), (0.025, -0.025), (-0.025, 0.025), (0.025, 0.025)]:
            dv, df = _make_sphere(cx, 0.13 + cy_off, 0.02, 0.005, rings=3, sectors=4)
            parts.append((dv, df))
        # Chain loop
        lv, lf = _make_torus_ring(0, 0.16, 0, 0.008, 0.003, major_segments=6, minor_segments=3)
        parts.append((lv, lf))
        grip_y = 0.04
        trail_top_y = 0.16
        trail_bottom_y = 0.0
    else:  # pendant
        # Chain / handle
        for ci in range(5):
            cy = 0.0 + ci * 0.025
            lv, lf = _make_torus_ring(0, cy, 0, 0.008, 0.002, major_segments=6, minor_segments=3)
            parts.append((lv, lf))
        # Pendant disc
        pv, pf = _make_cylinder(0, 0.12, 0, 0.03, 0.004, segments=segs)
        parts.append((pv, pf))
        # Sun / cross emblem
        crv1, crf1 = _make_beveled_box(0, 0.125, 0, 0.003, 0.02, 0.002, bevel=0.001)
        parts.append((crv1, crf1))
        crv2, crf2 = _make_beveled_box(0, 0.135, 0, 0.015, 0.003, 0.002, bevel=0.001)
        parts.append((crv2, crf2))
        # Sun rays
        for ri in range(8):
            r_angle = 2.0 * math.pi * ri / 8
            rx = math.cos(r_angle) * 0.025
            ry = 0.122 + math.sin(r_angle) * 0.025
            ray_v, ray_f = _make_beveled_box(rx, ry, 0, 0.002, 0.008, 0.002, bevel=0.001)
            parts.append((ray_v, ray_f))
        grip_y = 0.04
        trail_top_y = 0.155
        trail_bottom_y = 0.0

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"HolySymbol_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, grip_y, 0.0),
                        trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, trail_bottom_y, 0.0),
                        offhand=True)


def generate_totem_mesh(style: str = "wooden") -> MeshSpec:
    """Generate a druid/shaman totem -- off-hand focus.

    Args:
        style: "wooden", "bone", or "stone".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Main shaft
    shaft_h = 0.2
    if style == "bone":
        shaft_r = 0.012
        sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r * 1.2, shaft_r * 0.8, shaft_h, segs, rings=4)
        parts.append((sv, sf))
        # Bone knobs
        for ki in range(3):
            ky = 0.03 + ki * 0.06
            kv, kf = _make_sphere(0, ky, 0, shaft_r * 1.5, rings=3, sectors=5)
            parts.append((kv, kf))
    elif style == "stone":
        shaft_r = 0.015
        sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r, shaft_r * 0.9, shaft_h * 0.7, segs, rings=3)
        parts.append((sv, sf))
        # Stone head -- rough hewn
        shv, shf = _make_beveled_box(0, shaft_h * 0.7 + 0.03, 0, 0.025, 0.03, 0.02, bevel=0.008)
        parts.append((shv, shf))
    else:  # wooden
        shaft_r = 0.013
        sv, sf = _make_tapered_cylinder(0, 0, 0, shaft_r * 1.1, shaft_r * 0.85, shaft_h, segs, rings=4)
        parts.append((sv, sf))

    # Totem carving at top
    totem_y = shaft_h
    if style == "wooden":
        # Carved face
        tv, tf = _make_beveled_box(0, totem_y + 0.025, 0, 0.02, 0.025, 0.018, bevel=0.006)
        parts.append((tv, tf))
        # Eyes
        for ex in [-0.008, 0.008]:
            ev, ef = _make_sphere(ex, totem_y + 0.035, 0.016, 0.005, rings=3, sectors=4)
            parts.append((ev, ef))
        # Feathers
        for fi in range(2):
            fx = -0.015 + fi * 0.03
            fv, ff = _make_beveled_box(fx, totem_y + 0.06, 0, 0.003, 0.02, 0.008, bevel=0.001)
            parts.append((fv, ff))
        trail_top_y = totem_y + 0.08
    elif style == "bone":
        # Skull-like top
        bsv, bsf = _make_sphere(0, totem_y + 0.02, 0, 0.02, rings=4, sectors=6)
        parts.append((bsv, bsf))
        # Teeth
        for ti in range(4):
            tx = -0.01 + ti * 0.007
            tv2, tf2 = _make_cone(tx, totem_y + 0.005, 0.015, 0.003, 0.01, segments=4)
            parts.append((tv2, tf2))
        trail_top_y = totem_y + 0.04
    else:  # stone
        # Rune-carved stone piece
        rsv, rsf = _make_sphere(0, shaft_h * 0.7 + 0.06, 0, 0.022, rings=4, sectors=6)
        parts.append((rsv, rsf))
        trail_top_y = shaft_h * 0.7 + 0.082

    # Hanging charms
    for chi in range(3):
        ch_angle = 2.0 * math.pi * chi / 3
        chx = math.cos(ch_angle) * 0.02
        chz = math.sin(ch_angle) * 0.02
        # Thread
        thv, thf = _make_cylinder(chx, shaft_h * 0.6, chz, 0.002, 0.03, segments=3)
        parts.append((thv, thf))
        # Charm bead
        cbv, cbf = _make_sphere(chx, shaft_h * 0.58, chz, 0.005, rings=3, sectors=4)
        parts.append((cbv, cbf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Totem_{style}", verts, faces, style=style, category="weapon",
                        grip_point=(0.0, shaft_h * 0.3, 0.0),
                        trail_top=(0.0, trail_top_y, 0.0),
                        trail_bottom=(0.0, shaft_h * 0.5, 0.0),
                        offhand=True)


# =========================================================================
# CATEGORY 5: ARCHITECTURAL DETAILS
# =========================================================================


def generate_gargoyle_mesh(
    pose: str = "crouching",
) -> MeshSpec:
    """Generate a wall-mounted gargoyle mesh.

    Args:
        pose: "crouching", "winged", or "screaming".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Body (hunched torso)
    body_r = 0.12
    bv, bf = _make_sphere(0, 0.15, 0.1, body_r, rings=6, sectors=8)
    parts.append((bv, bf))

    # Head
    head_r = 0.07
    hv, hf = _make_sphere(0, 0.28, 0.18, head_r, rings=5, sectors=6)
    parts.append((hv, hf))

    # Snout/jaw
    sv, sf = _make_tapered_cylinder(0, 0.24, 0.24, 0.04, 0.02, 0.06, 6, rings=1)
    parts.append((sv, sf))

    # Horns
    for side in [-1, 1]:
        horn_v, horn_f = _make_tapered_cylinder(
            side * 0.05, 0.32, 0.15,
            0.015, 0.005, 0.08, 5, rings=2,
        )
        parts.append((horn_v, horn_f))

    # Eyes (indentations)
    for side in [-1, 1]:
        ev, ef = _make_sphere(side * 0.03, 0.3, 0.22, 0.012, rings=3, sectors=4)
        parts.append((ev, ef))

    # Limbs (crouching legs)
    for side in [-1, 1]:
        # Upper leg
        ulv, ulf = _make_tapered_cylinder(
            side * 0.08, 0.05, 0.08,
            0.04, 0.03, 0.12, 6, rings=2,
        )
        parts.append((ulv, ulf))
        # Foot/claw
        fv, ff = _make_box(side * 0.08, 0, 0.12, 0.03, 0.02, 0.04)
        parts.append((fv, ff))
        # Arm
        av, af = _make_tapered_cylinder(
            side * 0.12, 0.18, 0.12,
            0.025, 0.02, 0.1, 6, rings=2,
        )
        parts.append((av, af))

    if pose == "winged":
        # Wings (thin triangular surfaces)
        for side in [-1, 1]:
            wing_verts = [
                (side * 0.12, 0.2, 0.05),   # Wing root
                (side * 0.35, 0.3, -0.05),   # Wing tip
                (side * 0.25, 0.1, -0.1),    # Lower edge
                (side * 0.12, 0.08, 0.0),    # Lower root
            ]
            wing_faces = [(0, 1, 2, 3)] if side > 0 else [(3, 2, 1, 0)]
            parts.append((wing_verts, wing_faces))

    elif pose == "screaming":
        # Open mouth
        mv, mf = _make_cylinder(0, 0.25, 0.25, 0.03, 0.03, segments=6)
        parts.append((mv, mf))

    # Wall mounting base
    bsv, bsf = _make_beveled_box(0, 0.12, -0.05, 0.1, 0.12, 0.05, bevel=0.008)
    parts.append((bsv, bsf))

    # Tail (curving around the base)
    for i in range(6):
        t = i / 6
        tx = math.sin(t * math.pi * 2) * 0.1
        ty = 0.05 + t * 0.02
        tz = -0.05 + math.cos(t * math.pi * 2) * 0.08
        tr = 0.015 * (1.0 - t * 0.6)
        tv, tf = _make_cylinder(tx, ty, tz, max(tr, 0.004), 0.03, segments=4,
                                cap_top=False, cap_bottom=False)
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gargoyle_{pose}", verts, faces, pose=pose, category="architecture")


def generate_fountain_mesh(
    tiers: int = 2,
    basin_size: float = 1.0,
) -> MeshSpec:
    """Generate a stone fountain mesh.

    Args:
        tiers: Number of basin tiers (1-3).
        basin_size: Size of the bottom basin.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    tiers = max(1, min(3, tiers))

    for tier in range(tiers):
        scale = 1.0 - tier * 0.35
        r = basin_size * 0.5 * scale
        y_offset = tier * basin_size * 0.4

        # Basin (bowl shape via lathe)
        basin_profile = [
            (r * 0.15, y_offset),
            (r * 0.2, y_offset + 0.02),
            (r * 0.8, y_offset + 0.03),
            (r, y_offset + 0.08),
            (r * 1.05, y_offset + 0.1),
            (r * 1.05, y_offset + 0.15),
            (r * 0.95, y_offset + 0.15),
            (r * 0.9, y_offset + 0.12),
            (r * 0.5, y_offset + 0.1),
        ]
        bv, bf = _make_lathe(basin_profile, segments=16)
        parts.append((bv, bf))

        # Pedestal for upper tiers
        if tier > 0:
            ped_r = r * 0.2
            ped_h = basin_size * 0.4
            prev_y = (tier - 1) * basin_size * 0.4 + 0.15
            pv, pf = _make_tapered_cylinder(
                0, prev_y, 0,
                ped_r * 1.2, ped_r, ped_h - 0.15,
                segments=8, rings=3,
            )
            parts.append((pv, pf))

    # Central spout on top
    top_y = (tiers - 1) * basin_size * 0.4 + 0.15
    spout_profile = [
        (0.03, top_y),
        (0.025, top_y + 0.1),
        (0.035, top_y + 0.2),
        (0.02, top_y + 0.25),
        (0.015, top_y + 0.3),
    ]
    sv, sf = _make_lathe(spout_profile, segments=8, close_top=True)
    parts.append((sv, sf))

    # Base platform
    base_r = basin_size * 0.55
    base_profile = [
        (base_r, -0.05),
        (base_r, 0),
        (base_r * 0.9, 0.01),
    ]
    bsv, bsf = _make_lathe(base_profile, segments=16, close_bottom=True)
    parts.append((bsv, bsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Fountain", verts, faces, tiers=tiers, category="architecture")


def generate_statue_mesh(
    pose: str = "standing",
    size: float = 1.0,
) -> MeshSpec:
    """Generate a generic humanoid statue mesh.

    Args:
        pose: "standing", "praying", or "warrior".
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Pedestal
    ped_h = 0.3 * s
    pv, pf = _make_beveled_box(0, ped_h / 2, 0, 0.25 * s, ped_h / 2, 0.25 * s,
                               bevel=0.015 * s)
    parts.append((pv, pf))

    # Torso
    torso_h = 0.5 * s
    torso_w = 0.15 * s
    tv, tf = _make_tapered_cylinder(0, ped_h, 0, torso_w, torso_w * 0.85,
                                    torso_h, segments=8, rings=4)
    parts.append((tv, tf))

    # Head
    head_r = 0.08 * s
    hv, hf = _make_sphere(0, ped_h + torso_h + head_r, 0,
                          head_r, rings=6, sectors=8)
    parts.append((hv, hf))

    # Legs
    leg_h = 0.4 * s  # Partly hidden by robe but still there
    leg_r = 0.05 * s
    for side in [-1, 1]:
        lx = side * 0.06 * s
        lv, lf = _make_tapered_cylinder(lx, ped_h - leg_h * 0.3, 0,
                                        leg_r, leg_r * 0.8,
                                        leg_h, segments=6, rings=2)
        parts.append((lv, lf))

    # Arms
    arm_r = 0.035 * s
    arm_h = 0.4 * s
    if pose == "standing":
        for side in [-1, 1]:
            ax = side * (torso_w + 0.01 * s)
            av, af = _make_tapered_cylinder(ax, ped_h + torso_h * 0.3, 0,
                                            arm_r, arm_r * 0.7,
                                            arm_h, segments=6, rings=2)
            parts.append((av, af))

    elif pose == "praying":
        # Arms together in front
        for side in [-1, 1]:
            ax = side * 0.04 * s
            av, af = _make_tapered_cylinder(ax, ped_h + torso_h * 0.4, 0.08 * s,
                                            arm_r, arm_r * 0.7,
                                            arm_h * 0.6, segments=6, rings=2)
            parts.append((av, af))

    elif pose == "warrior":
        # One arm raised with weapon
        # Right arm raised
        av, af = _make_tapered_cylinder(torso_w + 0.01 * s, ped_h + torso_h * 0.6, 0,
                                        arm_r, arm_r * 0.7,
                                        arm_h * 0.7, segments=6, rings=2)
        parts.append((av, af))
        # Sword in hand
        sv, sf = _make_cylinder(torso_w + 0.02 * s,
                                ped_h + torso_h * 0.6 + arm_h * 0.6, 0,
                                0.008 * s, 0.4 * s, segments=4)
        parts.append((sv, sf))
        # Left arm with shield
        av2, af2 = _make_tapered_cylinder(-torso_w - 0.01 * s, ped_h + torso_h * 0.35,
                                          0.05 * s,
                                          arm_r, arm_r * 0.7,
                                          arm_h * 0.5, segments=6, rings=2)
        parts.append((av2, af2))
        # Shield disc
        shv, shf = _make_cylinder(-torso_w - 0.03 * s,
                                  ped_h + torso_h * 0.35, 0.08 * s,
                                  0.1 * s, 0.01 * s, segments=8)
        parts.append((shv, shf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Statue_{pose}", verts, faces, pose=pose, category="architecture")


def generate_bridge_mesh(
    span: float = 6.0,
    width: float = 2.0,
    style: str = "stone_arch",
) -> MeshSpec:
    """Generate a bridge mesh.

    Args:
        span: Bridge length.
        width: Bridge width.
        style: "stone_arch", "rope", or "drawbridge".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "stone_arch":
        # Arch curve underneath
        arch_segs = 16
        arch_h = span * 0.25
        deck_thick = 0.15
        wall_h = 0.5

        # Deck surface (slightly curved)
        deck_verts: list[tuple[float, float, float]] = []
        deck_faces: list[tuple[int, ...]] = []
        for i in range(arch_segs + 1):
            t = i / arch_segs
            z = -span / 2 + t * span
            y_arch = math.sin(t * math.pi) * arch_h * 0.1  # Slight crown
            # Inner left, outer left, outer right, inner right
            deck_verts.append((-width / 2, y_arch, z))
            deck_verts.append((-width / 2, y_arch - deck_thick, z))
            deck_verts.append((width / 2, y_arch - deck_thick, z))
            deck_verts.append((width / 2, y_arch, z))

        for i in range(arch_segs):
            b = i * 4
            # Top surface
            deck_faces.append((b + 0, b + 3, b + 7, b + 4))
            # Bottom surface
            deck_faces.append((b + 1, b + 5, b + 6, b + 2))
            # Left side
            deck_faces.append((b + 0, b + 4, b + 5, b + 1))
            # Right side
            deck_faces.append((b + 3, b + 2, b + 6, b + 7))

        parts.append((deck_verts, deck_faces))

        # Arch ribs (curved supports underneath)
        for x_pos in [-width * 0.4, 0, width * 0.4]:
            arch_v: list[tuple[float, float, float]] = []
            arch_f: list[tuple[int, ...]] = []
            rib_thick = 0.08
            for i in range(arch_segs + 1):
                t = i / arch_segs
                z = -span / 2 + t * span
                y = -math.sin(t * math.pi) * arch_h
                arch_v.append((x_pos - rib_thick / 2, y, z))
                arch_v.append((x_pos + rib_thick / 2, y, z))
                arch_v.append((x_pos + rib_thick / 2, y - rib_thick, z))
                arch_v.append((x_pos - rib_thick / 2, y - rib_thick, z))

            for i in range(arch_segs):
                b = i * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    arch_f.append((b + j, b + j2, b + 4 + j2, b + 4 + j))
            parts.append((arch_v, arch_f))

        # Side walls/railings
        for x_side in [-width / 2, width / 2]:
            wv, wf = _make_box(x_side, wall_h / 2, 0,
                               0.06, wall_h / 2, span / 2)
            parts.append((wv, wf))

    elif style == "rope":
        # Plank walkway with rope sides
        plank_count = int(span / 0.15)
        plank_w = width * 0.9
        plank_thick = 0.03
        plank_d = 0.12

        for i in range(plank_count):
            z = -span / 2 + i * span / plank_count
            # Slight sag in the middle
            t = (z + span / 2) / span
            sag = -math.sin(t * math.pi) * span * 0.05
            pv, pf = _make_box(0, sag, z, plank_w / 2, plank_thick / 2, plank_d / 2)
            parts.append((pv, pf))

        # Rope handrails
        rope_r = 0.015
        rope_h = 0.7
        for x_side in [-width / 2, width / 2]:
            for i in range(plank_count // 2):
                z = -span / 2 + i * 2 * span / plank_count
                t = (z + span / 2) / span
                sag = -math.sin(t * math.pi) * span * 0.05
                # Vertical rope post
                pv, pf = _make_cylinder(x_side, sag, z, rope_r * 2, rope_h,
                                        segments=4)
                parts.append((pv, pf))

    else:  # drawbridge
        # Thick wooden bridge deck
        deck_thick = 0.12
        dv, df = _make_beveled_box(0, -deck_thick / 2, 0,
                                   width / 2, deck_thick / 2, span / 2,
                                   bevel=0.015)
        parts.append((dv, df))

        # Plank lines (surface detail)
        plank_count = int(width / 0.2)
        for i in range(plank_count):
            x = -width / 2 + (i + 0.5) * width / plank_count
            lv, lf = _make_box(x, 0.005, 0, 0.003, 0.005, span / 2 - 0.02)
            parts.append((lv, lf))

        # Chain attachments at the end
        for x_side in [-width * 0.4, width * 0.4]:
            rv, rf = _make_torus_ring(x_side, 0.05, span / 2 - 0.05,
                                      0.03, 0.008,
                                      major_segments=6, minor_segments=3)
            parts.append((rv, rf))

        # Hinge mounts at near end
        for x_side in [-width * 0.4, width * 0.4]:
            hv, hf = _make_cylinder(x_side, 0, -span / 2,
                                    0.02, 0.04, segments=6)
            parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bridge_{style}", verts, faces, style=style, category="architecture")


def generate_gate_mesh(
    width: float = 2.0,
    height: float = 3.0,
    style: str = "portcullis",
) -> MeshSpec:
    """Generate a gate mesh.

    Args:
        width: Gate width.
        height: Gate height.
        style: "portcullis", "wooden_double", or "iron_grid".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "portcullis":
        bar_r = 0.02
        bar_segs = 6
        h_spacing = width / 8
        v_spacing = height / 6

        # Vertical bars
        for i in range(9):
            x = -width / 2 + i * h_spacing
            bv, bf = _make_cylinder(x, 0, 0, bar_r, height, segments=bar_segs)
            parts.append((bv, bf))

        # Horizontal bars
        for i in range(7):
            y = i * v_spacing
            hv, hf = _make_cylinder(-width / 2, y, 0, bar_r * 0.8, width,
                                    segments=bar_segs)
            # Rotate to horizontal
            h_verts = [(v[1] - y + (-width / 2), y, v[2]) for v in hv]
            parts.append((h_verts, hf))

        # Bottom spikes
        for i in range(9):
            x = -width / 2 + i * h_spacing
            sv, sf = _make_cone(x, -0.01, 0, bar_r * 1.5, 0.08, segments=4)
            # Point downward by flipping
            sv_down = [(v[0], -v[1], v[2]) for v in sv]
            parts.append((sv_down, sf))

    elif style == "wooden_double":
        door_thick = 0.06
        # Left door
        ldv, ldf = _make_beveled_box(
            -width / 4, height / 2, 0,
            width / 4 - 0.01, height / 2, door_thick / 2,
            bevel=0.01,
        )
        parts.append((ldv, ldf))
        # Right door
        rdv, rdf = _make_beveled_box(
            width / 4, height / 2, 0,
            width / 4 - 0.01, height / 2, door_thick / 2,
            bevel=0.01,
        )
        parts.append((rdv, rdf))

        # Plank lines
        plank_w = width / 2 / 5
        for door_side in [-1, 1]:
            for i in range(5):
                x = door_side * (width / 4) - width / 4 + (i + 0.5) * plank_w
                if door_side == 1:
                    x = door_side * (width / 4) - width / 4 + width / 2 + (i + 0.5) * plank_w
                pv, pf = _make_box(
                    door_side * (i * plank_w + plank_w / 2 + 0.01),
                    height / 2,
                    door_thick / 2 + 0.002,
                    0.003, height / 2 - 0.02, 0.002,
                )
                parts.append((pv, pf))

        # Iron bands
        for band_y in [height * 0.2, height * 0.5, height * 0.8]:
            bv, bf = _make_box(0, band_y, door_thick / 2 + 0.003,
                               width / 2, 0.015, 0.003)
            parts.append((bv, bf))

        # Large ring handles
        for side in [-1, 1]:
            rv, rf = _make_torus_ring(
                side * width / 4, height * 0.45, door_thick / 2 + 0.015,
                0.04, 0.008,
                major_segments=8, minor_segments=4,
            )
            parts.append((rv, rf))

        # Hinges
        for y_pos in [height * 0.2, height * 0.8]:
            for x_side in [-width / 2, width / 2]:
                hv, hf = _make_cylinder(x_side, y_pos, 0,
                                        0.015, 0.08, segments=6)
                parts.append((hv, hf))

    else:  # iron_grid
        bar_r = 0.015
        bar_segs = 6
        grid_spacing = 0.15

        # Grid bars
        h_bars = int(width / grid_spacing) + 1
        v_bars = int(height / grid_spacing) + 1

        for i in range(h_bars):
            x = -width / 2 + i * grid_spacing
            bv, bf = _make_cylinder(x, 0, 0, bar_r, height, segments=bar_segs)
            parts.append((bv, bf))

        for i in range(v_bars):
            y = i * grid_spacing
            hv, hf = _make_cylinder(-width / 2, y, 0, bar_r, width,
                                    segments=bar_segs)
            h_verts = [(v[1] - y + (-width / 2), y, v[2]) for v in hv]
            parts.append((h_verts, hf))

        # Frame
        frame_w = 0.05
        for x_side in [-width / 2 - frame_w / 2, width / 2 + frame_w / 2]:
            fv, ff = _make_beveled_box(x_side, height / 2, 0,
                                       frame_w / 2, height / 2, frame_w / 2,
                                       bevel=0.005)
            parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gate_{style}", verts, faces, style=style, category="architecture")


def generate_staircase_mesh(
    steps: int = 12,
    width: float = 1.0,
    direction: str = "straight",
) -> MeshSpec:
    """Generate a staircase mesh.

    Args:
        steps: Number of steps.
        width: Step width.
        direction: "straight" or "spiral".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    step_h = 0.18
    step_d = 0.28

    if direction == "straight":
        for i in range(steps):
            y = i * step_h
            z = i * step_d
            sv, sf = _make_beveled_box(
                0, y + step_h / 2, z,
                width / 2, step_h / 2, step_d / 2,
                bevel=0.005,
            )
            parts.append((sv, sf))

        # Side stringers (support beams)
        total_rise = steps * step_h
        total_run = steps * step_d
        stringer_len = math.sqrt(total_rise ** 2 + total_run ** 2)
        for x_side in [-width / 2 - 0.02, width / 2 + 0.02]:
            # Approximate with a box along the diagonal
            sv, sf = _make_box(
                x_side,
                total_rise / 2 - step_h / 2,
                total_run / 2 - step_d / 2,
                0.02, total_rise / 2, total_run / 2,
            )
            parts.append((sv, sf))

    else:  # spiral
        center_r = 0.1
        outer_r = center_r + width
        angle_per_step = math.pi * 2 / max(steps, 4) * 1.2  # Slightly more than full turn

        # Central pillar
        total_h = steps * step_h
        pv, pf = _make_cylinder(0, 0, 0, center_r, total_h + step_h,
                                segments=12)
        parts.append((pv, pf))

        for i in range(steps):
            y = i * step_h
            angle = i * angle_per_step

            # Pie-slice shaped step
            step_verts: list[tuple[float, float, float]] = []
            step_faces_local: list[tuple[int, ...]] = []

            n_arc = 5
            # Top surface
            step_verts.append((0, y + step_h, 0))  # Center
            for j in range(n_arc + 1):
                a = angle + j * angle_per_step / n_arc
                step_verts.append((
                    math.cos(a) * outer_r,
                    y + step_h,
                    math.sin(a) * outer_r,
                ))
            # Bottom surface
            step_verts.append((0, y, 0))  # Center bottom
            for j in range(n_arc + 1):
                a = angle + j * angle_per_step / n_arc
                step_verts.append((
                    math.cos(a) * outer_r,
                    y,
                    math.sin(a) * outer_r,
                ))

            top_center = 0
            bot_center = n_arc + 2
            # Top fan
            for j in range(n_arc):
                step_faces_local.append((top_center, j + 1, j + 2))
            # Bottom fan (reversed winding)
            for j in range(n_arc):
                step_faces_local.append((bot_center, bot_center + j + 2, bot_center + j + 1))
            # Front riser
            step_faces_local.append((top_center, bot_center, bot_center + 1, 1))
            # Outer rim
            for j in range(n_arc):
                t = j + 1
                b = bot_center + j + 1
                step_faces_local.append((t, b, b + 1, t + 1))
            # Back riser
            step_faces_local.append((n_arc + 1, bot_center + n_arc + 1, bot_center, top_center))

            parts.append((step_verts, step_faces_local))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Staircase_{direction}", verts, faces,
                        direction=direction, category="architecture")


# =========================================================================
# CATEGORY 6: FENCES & BARRIERS
# =========================================================================


def generate_fence_mesh(
    length: float = 4.0,
    posts: int = 5,
    style: str = "wooden_picket",
) -> MeshSpec:
    """Generate a fence mesh.

    Args:
        length: Total fence length along X axis.
        posts: Number of fence posts.
        style: "wooden_picket", "iron_wrought", "stone_low_wall", or "bone_fence".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    posts = max(2, posts)
    spacing = length / (posts - 1)

    if style == "wooden_picket":
        post_r = 0.03
        post_h = 0.9
        picket_h = 0.7
        picket_w = 0.04
        picket_d = 0.015
        rail_h = 0.015
        rail_d = 0.03

        # Posts (thicker)
        for i in range(posts):
            x = -length / 2 + i * spacing
            pv, pf = _make_beveled_box(
                x, post_h / 2, 0,
                post_r, post_h / 2, post_r,
                bevel=0.005,
            )
            parts.append((pv, pf))
            # Pointed top
            cv, cf = _make_cone(x, post_h, 0, post_r * 1.2, 0.06, segments=4)
            parts.append((cv, cf))

        # Horizontal rails (top and bottom)
        for rail_y in [post_h * 0.3, post_h * 0.75]:
            rv, rf = _make_box(
                0, rail_y, 0,
                length / 2, rail_h, rail_d,
            )
            parts.append((rv, rf))

        # Pickets between posts
        picket_spacing = spacing / 4
        for i in range(posts - 1):
            base_x = -length / 2 + i * spacing
            for j in range(1, 4):
                px = base_x + j * picket_spacing
                pv, pf = _make_box(
                    px, picket_h / 2, 0,
                    picket_w / 2, picket_h / 2, picket_d,
                )
                parts.append((pv, pf))
                # Pointed picket top
                tv, tf = _make_cone(px, picket_h, 0, picket_w * 0.7, 0.04, segments=4)
                parts.append((tv, tf))

    elif style == "iron_wrought":
        post_r = 0.025
        post_h = 1.2
        bar_r = 0.01
        bar_segs = 6

        # Posts with decorative tops
        for i in range(posts):
            x = -length / 2 + i * spacing
            pv, pf = _make_cylinder(x, 0, 0, post_r, post_h, segments=8)
            parts.append((pv, pf))
            # Finial (sphere on top)
            sv, sf = _make_sphere(x, post_h + 0.03, 0, 0.025, rings=4, sectors=6)
            parts.append((sv, sf))

        # Horizontal rails
        for rail_y in [0.15, post_h * 0.85]:
            rv, rf = _make_cylinder(
                -length / 2, rail_y, 0, bar_r * 0.8, length, segments=bar_segs,
            )
            # Rotate to horizontal: swap X and Y components
            r_verts = [(v[1] - rail_y + (-length / 2), rail_y, v[2]) for v in rv]
            parts.append((r_verts, rf))

        # Vertical bars with spear tips
        bar_spacing = spacing / 3
        for i in range(posts - 1):
            base_x = -length / 2 + i * spacing
            for j in range(1, 3):
                bx = base_x + j * bar_spacing
                bv, bf = _make_cylinder(bx, 0.15, 0, bar_r, post_h * 0.7, segments=bar_segs)
                parts.append((bv, bf))
                # Spear tip
                sv, sf = _make_cone(bx, 0.15 + post_h * 0.7, 0, bar_r * 2, 0.05, segments=4)
                parts.append((sv, sf))

    elif style == "stone_low_wall":
        wall_h = 0.6
        wall_d = 0.25

        # Main wall body
        wv, wf = _make_beveled_box(
            0, wall_h / 2, 0,
            length / 2, wall_h / 2, wall_d / 2,
            bevel=0.01,
        )
        parts.append((wv, wf))

        # Cap stones on top
        cap_len = spacing * 0.45
        for i in range(posts):
            x = -length / 2 + i * spacing
            cv, cf = _make_beveled_box(
                x, wall_h + 0.03, 0,
                cap_len / 2, 0.03, wall_d / 2 + 0.01,
                bevel=0.005,
            )
            parts.append((cv, cf))

        # Stone line detail
        for row in range(3):
            y = 0.12 + row * 0.18
            for i in range(posts - 1):
                x = -length / 2 + i * spacing + spacing / 2
                sv, sf = _make_box(
                    x, y, wall_d / 2 + 0.002,
                    spacing * 0.4, 0.002, 0.002,
                )
                parts.append((sv, sf))

    else:  # bone_fence
        post_h = 1.0

        # Bone posts (tapered cylinders resembling femurs)
        for i in range(posts):
            x = -length / 2 + i * spacing
            pv, pf = _make_tapered_cylinder(
                x, 0, 0, 0.04, 0.02, post_h * 0.7,
                segments=6, rings=3,
            )
            parts.append((pv, pf))
            # Knobby joint at top
            sv, sf = _make_sphere(x, post_h * 0.7 + 0.03, 0, 0.035, rings=4, sectors=6)
            parts.append((sv, sf))
            # Upper shaft
            uv, uf = _make_tapered_cylinder(
                x, post_h * 0.7 + 0.06, 0, 0.02, 0.035, post_h * 0.25,
                segments=6, rings=2,
            )
            parts.append((uv, uf))

        # Horizontal bone rails
        for rail_y in [post_h * 0.3, post_h * 0.6]:
            rv, rf = _make_tapered_cylinder(
                -length / 2, rail_y, 0, 0.02, 0.015, length,
                segments=6, rings=4,
            )
            # Rotate to horizontal
            r_verts = [(v[1] - rail_y + (-length / 2), rail_y + v[0] - (-length / 2) * 0, v[2]) for v in rv]
            # Proper rotation: the cylinder is along Y, we need it along X
            r_verts2 = []
            for v in rv:
                nx = v[1] - rail_y + (-length / 2)
                ny = rail_y
                nz = v[2]
                r_verts2.append((nx, ny, nz))
            parts.append((r_verts2, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Fence_{style}", verts, faces,
                        style=style, posts=posts, category="fence_barrier")


def generate_barricade_mesh(
    width: float = 2.0,
    style: str = "wooden_hasty",
) -> MeshSpec:
    """Generate a barricade mesh.

    Args:
        width: Barricade width.
        style: "wooden_hasty", "wagon_overturned", or "sandbag".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "wooden_hasty":
        # Main angled planks
        plank_w = 0.12
        plank_d = 0.025
        plank_h = 1.0
        n_planks = max(3, int(width / 0.3))

        for i in range(n_planks):
            x = -width / 2 + (i + 0.5) * width / n_planks
            # Slight random angle via deterministic offset
            angle_off = 0.05 * ((i * 7 + 3) % 5 - 2)
            pv, pf = _make_beveled_box(
                x, plank_h / 2 + angle_off, 0,
                plank_w / 2, plank_h / 2, plank_d,
                bevel=0.003,
            )
            parts.append((pv, pf))

        # Cross braces
        for brace_y in [0.25, 0.7]:
            bv, bf = _make_box(
                0, brace_y, plank_d + 0.005,
                width / 2, 0.03, 0.015,
            )
            parts.append((bv, bf))

        # Support struts (angled back)
        for x_pos in [-width * 0.3, width * 0.3]:
            # Diagonal brace going backward
            sv, sf = _make_box(
                x_pos, 0.35, 0.2,
                0.025, 0.4, 0.015,
            )
            parts.append((sv, sf))

    elif style == "wagon_overturned":
        # Overturned wagon body
        body_w = width / 2
        body_h = 0.5
        body_d = 0.8

        # Main body (on its side)
        bv, bf = _make_beveled_box(
            0, body_h / 2, 0,
            body_w, body_h / 2, body_d / 2,
            bevel=0.015,
        )
        parts.append((bv, bf))

        # Wheels (visible, stuck up)
        for x_side in [-body_w * 0.8, body_w * 0.8]:
            # Wheel as torus
            wv, wf = _make_torus_ring(
                x_side, body_h + 0.25, 0,
                0.2, 0.03,
                major_segments=12, minor_segments=4,
            )
            parts.append((wv, wf))
            # Spokes
            for spoke in range(6):
                angle = math.pi * spoke / 6
                sv, sf = _make_cylinder(
                    x_side, body_h + 0.25 + math.sin(angle) * 0.15, math.cos(angle) * 0.15,
                    0.008, 0.01, segments=4,
                )
                parts.append((sv, sf))

        # Debris planks
        for i in range(3):
            dx = -0.3 + i * 0.3
            dv, df = _make_box(
                dx, 0.02, body_d / 2 + 0.1 + i * 0.05,
                0.25, 0.015, 0.04,
            )
            parts.append((dv, df))

    else:  # sandbag
        bag_w = 0.35
        bag_h = 0.12
        bag_d = 0.2
        rows = 3
        total_h = 0.0

        for row in range(rows):
            bags_in_row = max(2, int(width / bag_w))
            y = total_h + bag_h / 2
            offset_x = bag_w * 0.5 if row % 2 else 0
            for i in range(bags_in_row):
                x = -width / 2 + offset_x + (i + 0.5) * width / bags_in_row
                # Sandbag as slightly squished beveled box
                sv, sf = _make_beveled_box(
                    x, y, 0,
                    bag_w / 2 * 0.9, bag_h / 2, bag_d / 2,
                    bevel=0.01,
                )
                parts.append((sv, sf))
            total_h += bag_h * 0.9  # Slight compression

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Barricade_{style}", verts, faces,
                        style=style, category="fence_barrier")


def generate_railing_mesh(
    length: float = 3.0,
    style: str = "iron_ornate",
) -> MeshSpec:
    """Generate a railing mesh.

    Args:
        length: Railing length along X axis.
        style: "iron_ornate", "wooden_simple", or "stone_balustrade".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    rail_h = 0.9

    if style == "iron_ornate":
        post_r = 0.02
        bar_r = 0.008
        bar_segs = 6

        # End posts
        for x in [-length / 2, length / 2]:
            pv, pf = _make_cylinder(x, 0, 0, post_r, rail_h, segments=8)
            parts.append((pv, pf))
            # Decorative finial
            sv, sf = _make_sphere(x, rail_h + 0.02, 0, 0.022, rings=4, sectors=6)
            parts.append((sv, sf))

        # Top rail
        rv, rf = _make_cylinder(
            -length / 2, rail_h, 0, bar_r * 1.5, length, segments=bar_segs,
        )
        r_verts = [(v[1] - rail_h + (-length / 2), rail_h, v[2]) for v in rv]
        parts.append((r_verts, rf))

        # Balusters with scroll shapes
        n_bars = max(4, int(length / 0.12))
        bar_spacing = length / (n_bars + 1)
        for i in range(1, n_bars + 1):
            x = -length / 2 + i * bar_spacing
            bv, bf = _make_cylinder(x, 0.05, 0, bar_r, rail_h - 0.1, segments=bar_segs)
            parts.append((bv, bf))
            # Small scroll at midpoint (torus)
            sv, sf = _make_torus_ring(
                x, rail_h * 0.5, 0, 0.015, 0.004,
                major_segments=6, minor_segments=3,
            )
            parts.append((sv, sf))

    elif style == "wooden_simple":
        post_w = 0.04
        post_count = max(2, int(length / 1.0) + 1)
        post_spacing = length / (post_count - 1)

        # Posts
        for i in range(post_count):
            x = -length / 2 + i * post_spacing
            pv, pf = _make_beveled_box(
                x, rail_h / 2, 0,
                post_w / 2, rail_h / 2, post_w / 2,
                bevel=0.003,
            )
            parts.append((pv, pf))

        # Top rail
        rv, rf = _make_beveled_box(
            0, rail_h - 0.015, 0,
            length / 2, 0.015, post_w / 2,
            bevel=0.003,
        )
        parts.append((rv, rf))

        # Mid rail
        mv, mf = _make_beveled_box(
            0, rail_h * 0.45, 0,
            length / 2, 0.012, post_w / 2 * 0.8,
            bevel=0.002,
        )
        parts.append((mv, mf))

    else:  # stone_balustrade
        n_balusters = max(3, int(length / 0.2))
        bal_spacing = length / (n_balusters + 1)

        # Base rail (bottom)
        bv, bf = _make_beveled_box(
            0, 0.03, 0,
            length / 2, 0.03, 0.06,
            bevel=0.005,
        )
        parts.append((bv, bf))

        # Top rail (handrail)
        tv, tf = _make_beveled_box(
            0, rail_h, 0,
            length / 2 + 0.01, 0.03, 0.07,
            bevel=0.005,
        )
        parts.append((tv, tf))

        # Balusters (turned profile via lathe)
        baluster_profile = [
            (0.025, 0.06),
            (0.03, 0.1),
            (0.015, 0.2),
            (0.025, 0.35),
            (0.03, 0.5),
            (0.015, 0.65),
            (0.025, 0.8),
            (0.025, rail_h - 0.03),
        ]
        for i in range(1, n_balusters + 1):
            x = -length / 2 + i * bal_spacing
            bv, bf = _make_lathe(baluster_profile, segments=6)
            # Offset to position
            bv_offset = [(v[0] + x, v[1], v[2]) for v in bv]
            parts.append((bv_offset, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Railing_{style}", verts, faces,
                        style=style, category="fence_barrier")


# =========================================================================
# CATEGORY 7: TRAPS
# =========================================================================


def generate_spike_trap_mesh(
    size: float = 1.0,
    spike_count: int = 9,
) -> MeshSpec:
    """Generate a floor spike trap mesh with pit and spikes.

    Args:
        size: Trap pit size (square).
        spike_count: Number of spikes in the pit.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    hs = size / 2
    pit_depth = 0.3

    # Pit floor
    fv, ff = _make_box(0, -pit_depth, 0, hs, 0.02, hs)
    parts.append((fv, ff))

    # Pit walls (4 sides)
    wall_thick = 0.03
    for side, (cx, cz, wx, wz) in enumerate([
        (0, -hs, hs, wall_thick),
        (0, hs, hs, wall_thick),
        (-hs, 0, wall_thick, hs),
        (hs, 0, wall_thick, hs),
    ]):
        wv, wf = _make_box(cx, -pit_depth / 2, cz, wx, pit_depth / 2, wz)
        parts.append((wv, wf))

    # Rim/lip around pit edge
    rim_w = 0.05
    for side, (cx, cz, rx, rz) in enumerate([
        (0, -hs - rim_w / 2, hs + rim_w, rim_w / 2),
        (0, hs + rim_w / 2, hs + rim_w, rim_w / 2),
        (-hs - rim_w / 2, 0, rim_w / 2, hs),
        (hs + rim_w / 2, 0, rim_w / 2, hs),
    ]):
        rv, rf = _make_beveled_box(cx, 0.01, cz, rx, 0.015, rz, bevel=0.003)
        parts.append((rv, rf))

    # Spikes
    grid_n = int(math.sqrt(spike_count))
    spike_r = size * 0.02
    spike_h = 0.2
    placed = 0
    for row in range(grid_n):
        for col in range(grid_n):
            if placed >= spike_count:
                break
            sx = -hs * 0.7 + col * (size * 0.7 / max(grid_n - 1, 1))
            sz = -hs * 0.7 + row * (size * 0.7 / max(grid_n - 1, 1))
            sv, sf = _make_cone(
                sx, -pit_depth + 0.02, sz,
                spike_r, spike_h, segments=4,
            )
            parts.append((sv, sf))
            placed += 1

    verts, faces = _merge_meshes(*parts)
    return _make_result("SpikeTrap", verts, faces,
                        spike_count=spike_count, category="trap")


def generate_bear_trap_mesh(
    size: float = 0.4,
) -> MeshSpec:
    """Generate an iron bear/jaw trap mesh.

    Args:
        size: Overall trap diameter.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    r = size / 2
    plate_h = 0.015

    # Base plate (circular disc)
    bv, bf = _make_cylinder(0, 0, 0, r, plate_h, segments=12)
    parts.append((bv, bf))

    # Jaw teeth (two arcs of triangular teeth)
    n_teeth = 8
    tooth_h = size * 0.25
    tooth_r = size * 0.03

    for jaw_side in [0, 1]:
        base_angle = math.pi * jaw_side
        arc_span = math.pi * 0.8
        for i in range(n_teeth):
            angle = base_angle - arc_span / 2 + i * arc_span / (n_teeth - 1)
            tx = math.cos(angle) * (r * 0.85)
            tz = math.sin(angle) * (r * 0.85)
            tv, tf = _make_cone(
                tx, plate_h, tz,
                tooth_r, tooth_h, segments=4,
            )
            parts.append((tv, tf))

    # Jaw arms (two curved bars)
    arm_r = 0.012
    for jaw_side in [0, 1]:
        angle = math.pi * jaw_side
        ax = math.cos(angle) * r * 0.5
        az = math.sin(angle) * r * 0.5
        av, af = _make_cylinder(
            ax, plate_h, az, arm_r, tooth_h * 0.6, segments=6,
        )
        parts.append((av, af))

    # Spring mechanism (central coil)
    sv, sf = _make_torus_ring(
        0, plate_h + 0.01, 0,
        r * 0.15, 0.008,
        major_segments=8, minor_segments=4,
    )
    parts.append((sv, sf))

    # Trigger plate (small central disc)
    tv, tf = _make_cylinder(0, plate_h, 0, r * 0.2, 0.005, segments=8)
    parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("BearTrap", verts, faces, category="trap")


def generate_pressure_plate_mesh(
    size: float = 0.6,
) -> MeshSpec:
    """Generate a stone pressure plate mesh.

    Args:
        size: Plate size (square).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    hs = size / 2
    plate_h = 0.03
    recess_depth = 0.015

    # Surrounding floor frame (slightly recessed channel)
    frame_w = size + 0.08
    hf = frame_w / 2
    gap = 0.008

    # Frame border pieces (4 sides)
    border_w = 0.03
    for side, (cx, cz, bx, bz) in enumerate([
        (0, -hf + border_w / 2, hf, border_w / 2),
        (0, hf - border_w / 2, hf, border_w / 2),
        (-hf + border_w / 2, 0, border_w / 2, hf - border_w),
        (hf - border_w / 2, 0, border_w / 2, hf - border_w),
    ]):
        fv, ff = _make_beveled_box(
            cx, -recess_depth / 2, cz,
            bx, recess_depth / 2, bz,
            bevel=0.002,
        )
        parts.append((fv, ff))

    # Pressure plate itself (slightly raised or depressed)
    pv, pf = _make_beveled_box(
        0, plate_h / 2 - recess_depth, 0,
        hs - gap, plate_h / 2, hs - gap,
        bevel=0.004,
    )
    parts.append((pv, pf))

    # Carved rune/symbol on top (decorative cross lines)
    line_w = 0.005
    line_depth = 0.002
    top_y = plate_h - recess_depth + 0.001
    for cx, cz, lx, lz in [
        (0, 0, hs * 0.6, line_w),
        (0, 0, line_w, hs * 0.6),
    ]:
        lv, lf = _make_box(cx, top_y, cz, lx, line_depth, lz)
        parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("PressurePlate", verts, faces, category="trap")


def generate_dart_launcher_mesh(
    style: str = "stone",
) -> MeshSpec:
    """Generate a wall-mounted dart launcher trap.

    Args:
        style: "stone" or "metal" housing style.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Wall mount plate
    plate_w = 0.2
    plate_h = 0.2
    plate_d = 0.03

    if style == "stone":
        mv, mf = _make_beveled_box(
            0, 0, 0,
            plate_w / 2, plate_h / 2, plate_d / 2,
            bevel=0.005,
        )
    else:
        mv, mf = _make_beveled_box(
            0, 0, 0,
            plate_w / 2, plate_h / 2, plate_d / 2,
            bevel=0.008,
        )
    parts.append((mv, mf))

    # Dart tubes (3 holes)
    tube_r = 0.015
    tube_depth = 0.08
    tube_segs = 6
    tube_positions = [(0, 0.04), (-0.05, -0.03), (0.05, -0.03)]

    for tx, ty in tube_positions:
        tv, tf = _make_cylinder(
            tx, ty, plate_d / 2, tube_r, tube_depth, segments=tube_segs,
        )
        # Rotate tubes to point outward (along Z)
        t_verts = [(v[0], v[1], v[1] - ty + plate_d / 2) for v in tv]
        # Proper: cylinder is along Y, we need it along Z
        t_verts2 = []
        for v in tv:
            nz = v[1] - ty + plate_d / 2
            ny = ty
            t_verts2.append((v[0], ny, nz))
        parts.append((t_verts2, tf))

        # Dart inside (thin cone)
        dv, df = _make_cone(tx, ty, plate_d / 2 + tube_depth * 0.3,
                            tube_r * 0.5, tube_depth * 0.6, segments=4)
        # Rotate dart to point along Z
        d_verts = []
        for v in dv:
            nz = v[1] - ty + plate_d / 2 + tube_depth * 0.3
            ny = ty
            d_verts.append((v[0], ny, nz))
        parts.append((d_verts, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"DartLauncher_{style}", verts, faces,
                        style=style, category="trap")


def generate_swinging_blade_mesh(
    blade_length: float = 1.2,
    arc: float = 0.8,
) -> MeshSpec:
    """Generate a pendulum swinging blade trap.

    Args:
        blade_length: Length of the blade.
        arc: Width of the swing arc (for mounting bar).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Ceiling mount bracket
    bracket_w = arc
    bracket_h = 0.08
    bracket_d = 0.06
    bv, bf = _make_beveled_box(
        0, 0, 0,
        bracket_w / 2, bracket_h / 2, bracket_d / 2,
        bevel=0.005,
    )
    parts.append((bv, bf))

    # Pivot axle
    axle_r = 0.02
    av, af = _make_cylinder(
        -bracket_w / 2, -bracket_h / 2, 0,
        axle_r, bracket_w, segments=8,
    )
    # Rotate to horizontal (along X)
    a_verts = [(v[1] + bracket_h / 2 + (-bracket_w / 2), -bracket_h / 2, v[2]) for v in av]
    parts.append((a_verts, af))

    # Pendulum arm (long rod hanging down)
    arm_r = 0.015
    arm_len = blade_length * 0.7
    rv, rf = _make_cylinder(0, -bracket_h / 2 - arm_len, 0, arm_r, arm_len, segments=6)
    parts.append((rv, rf))

    # Blade (flat profile extruded)
    blade_w = 0.3
    blade_h = blade_length * 0.3
    blade_d = 0.008
    blade_y = -bracket_h / 2 - arm_len

    # Blade body
    blv, blf = _make_beveled_box(
        0, blade_y - blade_h / 2, 0,
        blade_w / 2, blade_h / 2, blade_d,
        bevel=0.002,
    )
    parts.append((blv, blf))

    # Blade edge (tapered bottom)
    ev, ef = _make_box(
        0, blade_y - blade_h - 0.01, 0,
        blade_w / 2, 0.01, blade_d * 0.3,
    )
    parts.append((ev, ef))

    # Counterweight at top
    cwv, cwf = _make_sphere(0, -bracket_h / 2 - 0.05, 0, 0.04, rings=4, sectors=6)
    parts.append((cwv, cwf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SwingingBlade", verts, faces,
                        blade_length=blade_length, category="trap")


def generate_falling_cage_mesh(
    size: float = 1.5,
) -> MeshSpec:
    """Generate a ceiling-mounted falling cage trap.

    Args:
        size: Cage width/depth.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    hs = size / 2
    cage_h = size * 1.2
    bar_r = 0.012
    bar_segs = 6

    # Top frame (square)
    frame_thick = 0.03
    for side, (cx, cz, fx, fz) in enumerate([
        (0, -hs, hs, frame_thick / 2),
        (0, hs, hs, frame_thick / 2),
        (-hs, 0, frame_thick / 2, hs),
        (hs, 0, frame_thick / 2, hs),
    ]):
        fv, ff = _make_beveled_box(
            cx, cage_h, cz,
            fx, frame_thick / 2, fz,
            bevel=0.003,
        )
        parts.append((fv, ff))

    # Bottom ring (heavier)
    for side, (cx, cz, fx, fz) in enumerate([
        (0, -hs, hs, frame_thick),
        (0, hs, hs, frame_thick),
        (-hs, 0, frame_thick, hs),
        (hs, 0, frame_thick, hs),
    ]):
        fv, ff = _make_beveled_box(
            cx, 0, cz,
            fx, frame_thick, fz,
            bevel=0.004,
        )
        parts.append((fv, ff))

    # Vertical bars
    n_bars_per_side = max(3, int(size / 0.2))
    bar_spacing = size / (n_bars_per_side + 1)
    for side in range(4):
        for i in range(1, n_bars_per_side + 1):
            t = -hs + i * bar_spacing
            if side == 0:
                bx, bz = t, -hs
            elif side == 1:
                bx, bz = t, hs
            elif side == 2:
                bx, bz = -hs, t
            else:
                bx, bz = hs, t
            bv, bf = _make_cylinder(bx, 0, bz, bar_r, cage_h, segments=bar_segs)
            parts.append((bv, bf))

    # Ceiling chain mount (chain links going up)
    chain_link_r = 0.02
    chain_wire = 0.005
    for i in range(4):
        cy = cage_h + i * chain_link_r * 2.5
        if i % 2 == 0:
            cv, cf = _make_torus_ring(
                0, cy, 0, chain_link_r, chain_wire,
                major_segments=6, minor_segments=3,
            )
        else:
            cv, cf = _make_torus_ring(
                0, cy, 0, chain_link_r, chain_wire,
                major_segments=6, minor_segments=3,
            )
            cv = [(v[2], v[1], v[0]) for v in cv]
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("FallingCage", verts, faces, category="trap")


# =========================================================================
# CATEGORY 8: VEHICLES & TRANSPORT
# =========================================================================


def generate_cart_mesh(
    size: float = 1.0,
    wheels: int = 4,
    style: str = "merchant_covered",
) -> MeshSpec:
    """Generate a cart mesh.

    Args:
        size: Scale multiplier.
        wheels: Number of wheels (2 or 4).
        style: "merchant_covered", "farm_open", or "prison_cage".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Base platform
    platform_w = 1.2 * s
    platform_d = 0.7 * s
    platform_h = 0.06 * s
    axle_h = 0.35 * s

    pv, pf = _make_beveled_box(
        0, axle_h, 0,
        platform_w / 2, platform_h / 2, platform_d / 2,
        bevel=0.005 * s,
    )
    parts.append((pv, pf))

    # Wheel axles
    axle_r = 0.015 * s
    if wheels == 4:
        axle_positions = [-platform_w * 0.35, platform_w * 0.35]
    else:
        axle_positions = [platform_w * 0.2]

    for ax in axle_positions:
        av, af = _make_cylinder(
            ax, axle_h - platform_h / 2, -platform_d / 2 - 0.05 * s,
            axle_r, platform_d + 0.1 * s, segments=6,
        )
        # Rotate axle to run along Z
        a_verts = [(v[0], axle_h - platform_h / 2, v[1] - (axle_h - platform_h / 2) + (-platform_d / 2 - 0.05 * s)) for v in av]
        parts.append((a_verts, af))

    # Wheels
    wheel_r = 0.25 * s
    wheel_thick = 0.03 * s
    wheel_positions = []
    if wheels == 4:
        for ax in axle_positions:
            wheel_positions.append((ax, -platform_d / 2 - 0.06 * s))
            wheel_positions.append((ax, platform_d / 2 + 0.06 * s))
    else:
        for ax in axle_positions:
            wheel_positions.append((ax, -platform_d / 2 - 0.06 * s))
            wheel_positions.append((ax, platform_d / 2 + 0.06 * s))

    for wx, wz in wheel_positions:
        # Wheel rim (torus)
        wv, wf = _make_torus_ring(
            wx, axle_h - platform_h / 2, wz,
            wheel_r, wheel_thick,
            major_segments=12, minor_segments=4,
        )
        parts.append((wv, wf))
        # Hub
        hv, hf = _make_cylinder(
            wx, axle_h - platform_h / 2, wz,
            0.03 * s, wheel_thick, segments=6,
        )
        parts.append((hv, hf))

    if style == "merchant_covered":
        # Side walls
        wall_h = 0.4 * s
        for z_side in [-platform_d / 2, platform_d / 2]:
            wv, wf = _make_beveled_box(
                0, axle_h + platform_h / 2 + wall_h / 2, z_side,
                platform_w / 2, wall_h / 2, 0.015 * s,
                bevel=0.003 * s,
            )
            parts.append((wv, wf))

        # Canvas cover supports (hoops)
        n_hoops = 4
        hoop_r = platform_d / 2 + 0.05 * s
        cover_y = axle_h + platform_h / 2 + wall_h
        for i in range(n_hoops):
            hx = -platform_w / 2 + (i + 0.5) * platform_w / n_hoops
            hv, hf = _make_torus_ring(
                hx, cover_y + hoop_r * 0.3, 0,
                hoop_r, 0.008 * s,
                major_segments=8, minor_segments=3,
            )
            # Take only top half (approximate by filtering)
            h_verts = [(v[0], max(v[1], cover_y), v[2]) for v in hv]
            parts.append((h_verts, hf))

    elif style == "prison_cage":
        # Cage bars
        cage_h = 0.8 * s
        cage_bar_r = 0.01 * s
        cage_y = axle_h + platform_h / 2

        # Corner posts
        for cx, cz in [
            (-platform_w / 2 * 0.9, -platform_d / 2 * 0.9),
            (platform_w / 2 * 0.9, -platform_d / 2 * 0.9),
            (-platform_w / 2 * 0.9, platform_d / 2 * 0.9),
            (platform_w / 2 * 0.9, platform_d / 2 * 0.9),
        ]:
            cv, cf = _make_cylinder(cx, cage_y, cz, cage_bar_r * 1.5, cage_h, segments=6)
            parts.append((cv, cf))

        # Cage bars along sides
        for side_z in [-platform_d / 2 * 0.9, platform_d / 2 * 0.9]:
            n_bars = 5
            for i in range(1, n_bars):
                bx = -platform_w / 2 * 0.9 + i * platform_w * 0.9 / n_bars * 2
                bv, bf = _make_cylinder(bx, cage_y, side_z, cage_bar_r, cage_h, segments=6)
                parts.append((bv, bf))

        # Top frame bars
        for cz in [-platform_d / 2 * 0.9, platform_d / 2 * 0.9]:
            tv, tf = _make_box(
                0, cage_y + cage_h, cz,
                platform_w / 2 * 0.9, cage_bar_r, cage_bar_r,
            )
            parts.append((tv, tf))

    else:  # farm_open
        # Low side walls
        wall_h = 0.2 * s
        for z_side in [-platform_d / 2, platform_d / 2]:
            wv, wf = _make_beveled_box(
                0, axle_h + platform_h / 2 + wall_h / 2, z_side,
                platform_w / 2, wall_h / 2, 0.015 * s,
                bevel=0.003 * s,
            )
            parts.append((wv, wf))

        # Back wall
        bv, bf = _make_beveled_box(
            -platform_w / 2, axle_h + platform_h / 2 + wall_h / 2, 0,
            0.015 * s, wall_h / 2, platform_d / 2,
            bevel=0.003 * s,
        )
        parts.append((bv, bf))

    # Tongue/handle (for pulling)
    tongue_len = 0.6 * s
    tv, tf = _make_box(
        platform_w / 2 + tongue_len / 2, axle_h - 0.05 * s, 0,
        tongue_len / 2, 0.015 * s, 0.015 * s,
    )
    parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cart_{style}", verts, faces,
                        style=style, wheels=wheels, category="vehicle")


def generate_boat_mesh(
    size: float = 1.0,
    style: str = "rowboat",
) -> MeshSpec:
    """Generate a boat mesh.

    Args:
        size: Scale multiplier.
        style: "rowboat", "viking_longship", or "gondola".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    if style == "rowboat":
        # Hull via lathe-like profile (half hull, mirrored)
        hull_len = 2.0 * s
        hull_w = 0.6 * s
        hull_h = 0.3 * s
        hull_thick = 0.03 * s

        # Outer hull profile (side view cross-sections along length)
        n_sections = 8
        hull_verts: list[tuple[float, float, float]] = []
        hull_faces: list[tuple[int, ...]] = []
        segs = 6  # half-circle segments for cross-section

        for i in range(n_sections + 1):
            t = i / n_sections
            x = -hull_len / 2 + t * hull_len
            # Width tapers at bow/stern
            taper = math.sin(t * math.pi)
            w = hull_w / 2 * max(taper, 0.15)
            # Depth varies
            d = hull_h * max(taper, 0.3)

            for j in range(segs + 1):
                u = j / segs
                angle = math.pi * u  # Bottom semicircle
                y = -d * math.cos(angle) * 0.5
                z = w * math.sin(angle)
                if j == 0:
                    z = -w
                elif j == segs:
                    z = w
                hull_verts.append((x, y, z))

        # Connect cross-sections with quads
        n_per_section = segs + 1
        for i in range(n_sections):
            for j in range(segs):
                v0 = i * n_per_section + j
                v1 = i * n_per_section + j + 1
                v2 = (i + 1) * n_per_section + j + 1
                v3 = (i + 1) * n_per_section + j
                hull_faces.append((v0, v1, v2, v3))

        parts.append((hull_verts, hull_faces))

        # Bench seats
        for bench_t in [0.35, 0.65]:
            bx = -hull_len / 2 + bench_t * hull_len
            taper = math.sin(bench_t * math.pi)
            bw = hull_w / 2 * taper * 0.8
            bv, bf = _make_box(bx, hull_h * 0.15, 0, 0.04 * s, 0.015 * s, bw)
            parts.append((bv, bf))

        # Oars (simplified)
        for side_z in [-1, 1]:
            ov, of = _make_cylinder(
                0, hull_h * 0.2, side_z * hull_w / 2, 0.01 * s, hull_len * 0.4,
                segments=4,
            )
            # Rotate to angle outward
            o_verts = [(v[1] - hull_h * 0.2, hull_h * 0.2, v[2] + side_z * 0.1 * s) for v in ov]
            parts.append((o_verts, of))

    elif style == "viking_longship":
        hull_len = 4.0 * s
        hull_w = 0.8 * s
        hull_h = 0.5 * s

        # Long hull
        n_sections = 12
        hull_verts: list[tuple[float, float, float]] = []
        hull_faces: list[tuple[int, ...]] = []
        segs = 6

        for i in range(n_sections + 1):
            t = i / n_sections
            x = -hull_len / 2 + t * hull_len
            taper = math.sin(t * math.pi)
            w = hull_w / 2 * max(taper, 0.1)
            d = hull_h * max(taper, 0.2)

            for j in range(segs + 1):
                u = j / segs
                angle = math.pi * u
                y = -d * math.cos(angle) * 0.5
                z = w * math.sin(angle)
                if j == 0:
                    z = -w
                elif j == segs:
                    z = w
                hull_verts.append((x, y, z))

        n_per_section = segs + 1
        for i in range(n_sections):
            for j in range(segs):
                v0 = i * n_per_section + j
                v1 = i * n_per_section + j + 1
                v2 = (i + 1) * n_per_section + j + 1
                v3 = (i + 1) * n_per_section + j
                hull_faces.append((v0, v1, v2, v3))

        parts.append((hull_verts, hull_faces))

        # Dragon prow (bow decoration)
        prow_x = hull_len / 2
        pv, pf = _make_tapered_cylinder(
            prow_x, hull_h * 0.3, 0,
            0.06 * s, 0.03 * s, hull_h * 0.8,
            segments=6, rings=3,
        )
        parts.append((pv, pf))
        # Dragon head (sphere)
        dv, df = _make_sphere(prow_x, hull_h * 1.1, 0, 0.08 * s, rings=4, sectors=6)
        parts.append((dv, df))

        # Shields along sides
        n_shields = 6
        shield_r = 0.08 * s
        for i in range(n_shields):
            sx = -hull_len * 0.3 + i * hull_len * 0.6 / (n_shields - 1)
            for side_z in [-1, 1]:
                t_pos = (sx + hull_len / 2) / hull_len
                taper = math.sin(t_pos * math.pi)
                sz = side_z * hull_w / 2 * taper
                sv, sf = _make_cylinder(
                    sx, hull_h * 0.25, sz,
                    shield_r, 0.01 * s, segments=8,
                )
                parts.append((sv, sf))

        # Mast
        mast_h = hull_len * 0.4
        mv, mf = _make_cylinder(0, hull_h * 0.1, 0, 0.03 * s, mast_h, segments=6)
        parts.append((mv, mf))

        # Crossbeam
        yard_w = hull_w * 1.5
        yv, yf = _make_cylinder(
            -yard_w / 2, hull_h * 0.1 + mast_h * 0.75, 0,
            0.015 * s, yard_w, segments=4,
        )
        y_verts = [(v[1] - (hull_h * 0.1 + mast_h * 0.75) + (-yard_w / 2),
                     hull_h * 0.1 + mast_h * 0.75, v[2]) for v in yv]
        parts.append((y_verts, yf))

    else:  # gondola
        hull_len = 3.0 * s
        hull_w = 0.45 * s
        hull_h = 0.3 * s

        # Sleek narrow hull
        n_sections = 10
        hull_verts_g: list[tuple[float, float, float]] = []
        hull_faces_g: list[tuple[int, ...]] = []
        segs = 5

        for i in range(n_sections + 1):
            t = i / n_sections
            x = -hull_len / 2 + t * hull_len
            # Gondola: very pointed at both ends
            taper = math.sin(t * math.pi) ** 0.7
            w = hull_w / 2 * max(taper, 0.05)
            d = hull_h * max(taper, 0.15)

            for j in range(segs + 1):
                u = j / segs
                angle = math.pi * u
                y = -d * math.cos(angle) * 0.4
                z = w * math.sin(angle)
                if j == 0:
                    z = -w
                elif j == segs:
                    z = w
                hull_verts_g.append((x, y, z))

        n_per_section_g = segs + 1
        for i in range(n_sections):
            for j in range(segs):
                v0 = i * n_per_section_g + j
                v1 = i * n_per_section_g + j + 1
                v2 = (i + 1) * n_per_section_g + j + 1
                v3 = (i + 1) * n_per_section_g + j
                hull_faces_g.append((v0, v1, v2, v3))

        parts.append((hull_verts_g, hull_faces_g))

        # Ferro (bow ornament - curved metal piece)
        fv, ff = _make_tapered_cylinder(
            hull_len / 2, 0, 0,
            0.04 * s, 0.02 * s, hull_h * 0.6,
            segments=4, rings=2,
        )
        parts.append((fv, ff))

        # Standing platform at stern
        pv, pf = _make_box(
            -hull_len / 2 + 0.2 * s, hull_h * 0.15, 0,
            0.15 * s, 0.015 * s, hull_w / 2 * 0.7,
        )
        parts.append((pv, pf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Boat_{style}", verts, faces,
                        style=style, category="vehicle")


def generate_wagon_wheel_mesh(
    radius: float = 0.4,
    spokes: int = 8,
) -> MeshSpec:
    """Generate a standalone wagon wheel mesh (also useful as decoration).

    Args:
        radius: Wheel outer radius.
        spokes: Number of spokes.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    rim_minor = radius * 0.06
    hub_r = radius * 0.15
    hub_h = rim_minor * 2.5
    spoke_r = radius * 0.025

    # Outer rim (torus)
    rv, rf = _make_torus_ring(
        0, 0, 0,
        radius, rim_minor,
        major_segments=spokes * 3, minor_segments=4,
    )
    parts.append((rv, rf))

    # Hub (cylinder)
    hv, hf = _make_cylinder(
        0, -hub_h / 2, 0, hub_r, hub_h, segments=spokes,
    )
    parts.append((hv, hf))

    # Hub cap (slightly wider discs)
    for y_side in [-hub_h / 2, hub_h / 2]:
        cv, cf = _make_cylinder(0, y_side - 0.005, 0, hub_r * 1.2, 0.01, segments=spokes)
        parts.append((cv, cf))

    # Spokes
    spoke_len = radius - hub_r - rim_minor
    for i in range(spokes):
        angle = 2.0 * math.pi * i / spokes
        sx = math.cos(angle) * (hub_r + spoke_len / 2)
        sz = math.sin(angle) * (hub_r + spoke_len / 2)
        # Each spoke is a cylinder from hub to rim, rotated into the XZ plane
        sv, sf = _make_cylinder(
            sx, -spoke_r, sz,
            spoke_r, spoke_r * 2, segments=4,
        )
        # Create spoke as a box oriented radially
        sv2, sf2 = _make_box(
            sx, 0, sz,
            spoke_len / 2, spoke_r, spoke_r,
        )
        # Rotate box to align with spoke direction
        ca, sa = math.cos(angle), math.sin(angle)
        sv_rotated = []
        for v in sv2:
            # Rotate around Y axis
            nx = v[0] * ca - v[2] * sa
            nz = v[0] * sa + v[2] * ca
            sv_rotated.append((nx, v[1], nz))
        # Recalculate position for rotated spoke
        mid_r = (hub_r + radius - rim_minor) / 2
        offset_x = math.cos(angle) * mid_r
        offset_z = math.sin(angle) * mid_r
        sv_final = []
        for v in sv_rotated:
            sv_final.append((v[0] - sx + offset_x, v[1], v[2] - sz + offset_z))
        parts.append((sv_final, sf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result("WagonWheel", verts, faces,
                        spokes=spokes, category="vehicle")


# =========================================================================
# CATEGORY 9: STRUCTURAL ELEMENTS
# =========================================================================


def generate_column_row_mesh(
    count: int = 4,
    spacing: float = 2.0,
    style: str = "doric",
) -> MeshSpec:
    """Generate a colonnade (row of columns).

    Args:
        count: Number of columns.
        spacing: Distance between columns.
        style: "doric", "corinthian", or "gothic".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    col_h = 3.0

    for i in range(count):
        x = (i - (count - 1) / 2) * spacing

        if style == "doric":
            # Simple tapered column with flat capital
            col_r_bot = 0.2
            col_r_top = 0.16
            cv, cf = _make_tapered_cylinder(
                x, 0, 0, col_r_bot, col_r_top, col_h,
                segments=12, rings=4,
            )
            parts.append((cv, cf))

            # Capital (wider disc)
            capv, capf = _make_cylinder(
                x, col_h, 0, col_r_top * 1.4, 0.08, segments=12,
            )
            parts.append((capv, capf))

            # Base
            bv, bf = _make_cylinder(x, -0.05, 0, col_r_bot * 1.2, 0.05, segments=12)
            parts.append((bv, bf))

        elif style == "corinthian":
            # Fluted column with ornate capital
            col_r = 0.18
            cv, cf = _make_tapered_cylinder(
                x, 0, 0, col_r, col_r * 0.85, col_h,
                segments=16, rings=6,
            )
            parts.append((cv, cf))

            # Ornate capital (stacked elements)
            cap_r = col_r * 1.6
            # Abacus (top square)
            av, af = _make_beveled_box(
                x, col_h + 0.12, 0,
                cap_r, 0.03, cap_r,
                bevel=0.005,
            )
            parts.append((av, af))
            # Echinus (curved transition)
            ev, ef = _make_tapered_cylinder(
                x, col_h, 0, col_r * 0.85, cap_r * 0.9, 0.1,
                segments=12, rings=2,
            )
            parts.append((ev, ef))

            # Base molding
            base_profile = [
                (col_r * 1.3, -0.08),
                (col_r * 1.2, -0.04),
                (col_r * 1.1, 0),
                (col_r, 0.02),
            ]
            bv, bf = _make_lathe(base_profile, segments=12, close_bottom=True)
            bv_offset = [(v[0] + x, v[1], v[2]) for v in bv]
            parts.append((bv_offset, bf))

        else:  # gothic
            # Clustered columns (4 small columns around a core)
            core_r = 0.1
            cluster_r = 0.07
            cluster_dist = 0.12

            # Core column
            cv, cf = _make_cylinder(x, 0, 0, core_r, col_h, segments=8)
            parts.append((cv, cf))

            # Clustered columns
            for angle_idx in range(4):
                angle = math.pi / 4 + angle_idx * math.pi / 2
                cx_off = x + math.cos(angle) * cluster_dist
                cz_off = math.sin(angle) * cluster_dist
                ccv, ccf = _make_cylinder(cx_off, 0, cz_off, cluster_r, col_h, segments=6)
                parts.append((ccv, ccf))

            # Pointed arch capital
            pv, pf = _make_cone(x, col_h, 0, core_r * 2, 0.15, segments=8)
            # Invert to make it a splayed capital
            p_verts = [(v[0], col_h + (col_h + 0.15 - v[1]) if v[1] > col_h else v[1], v[2])
                       for v in pv]
            parts.append((p_verts, pf))

    # Entablature (beam across tops)
    total_len = (count - 1) * spacing + 0.6
    ev, ef = _make_beveled_box(
        0, col_h + 0.2, 0,
        total_len / 2, 0.06, 0.25,
        bevel=0.008,
    )
    parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"ColumnRow_{style}", verts, faces,
                        style=style, count=count, category="structural")


def generate_buttress_mesh(
    height: float = 4.0,
    style: str = "flying",
) -> MeshSpec:
    """Generate a buttress mesh for gothic architecture.

    Args:
        height: Buttress height.
        style: "flying" or "standard".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "flying":
        # Pier (outer support pillar)
        pier_w = 0.4
        pier_d = 0.4
        pier_h = height * 0.6
        pv, pf = _make_beveled_box(
            0, pier_h / 2, -1.5,
            pier_w / 2, pier_h / 2, pier_d / 2,
            bevel=0.01,
        )
        parts.append((pv, pf))

        # Pinnacle on top of pier
        pinv, pinf = _make_cone(0, pier_h, -1.5, pier_w / 2 * 0.6, height * 0.15, segments=4)
        parts.append((pinv, pinf))

        # Flying arch (connecting pier to wall)
        # Approximate with angled box
        arch_len = 1.5
        arch_h = 0.2
        arch_d = 0.3

        # Arch body (angled from pier top to wall)
        n_arch_segs = 6
        for i in range(n_arch_segs):
            t = i / n_arch_segs
            ax = 0
            ay = pier_h + t * (height - pier_h) * 0.5
            az = -1.5 + t * 1.5
            seg_len = 1.5 / n_arch_segs
            sv, sf = _make_beveled_box(
                ax, ay, az + seg_len / 2,
                arch_d / 2, arch_h / 2, seg_len / 2,
                bevel=0.005,
            )
            parts.append((sv, sf))

    else:  # standard
        # Solid triangular buttress against wall
        base_w = 0.5
        base_d = 1.0

        # Main body (tapered box)
        bv, bf = _make_beveled_box(
            0, height / 2, -base_d / 2,
            base_w / 2, height / 2, base_d / 2,
            bevel=0.01,
        )
        parts.append((bv, bf))

        # Stepped offsets (3 tiers getting narrower)
        for tier in range(3):
            t = (tier + 1) / 4
            ty = height * t
            td = base_d * (1 - t * 0.3)
            tv, tf = _make_beveled_box(
                0, ty + 0.05, -td / 2,
                base_w / 2 + 0.02, 0.05, td / 2,
                bevel=0.005,
            )
            parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Buttress_{style}", verts, faces,
                        style=style, category="structural")


def generate_rampart_mesh(
    length: float = 6.0,
    height: float = 3.0,
) -> MeshSpec:
    """Generate a castle wall rampart with walkway and crenellations.

    Args:
        length: Wall length.
        height: Wall height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    wall_thick = 0.6
    walkway_w = 0.8
    merlon_h = 0.5
    merlon_w = 0.3
    crenel_w = 0.25

    # Main wall
    wv, wf = _make_beveled_box(
        0, height / 2, 0,
        length / 2, height / 2, wall_thick / 2,
        bevel=0.01,
    )
    parts.append((wv, wf))

    # Walkway on top
    pv, pf = _make_beveled_box(
        0, height + 0.03, wall_thick / 2 + walkway_w / 2 - wall_thick / 2,
        length / 2, 0.03, walkway_w / 2,
        bevel=0.005,
    )
    parts.append((pv, pf))

    # Crenellations (merlons)
    merlon_spacing = merlon_w + crenel_w
    n_merlons = int(length / merlon_spacing)
    for i in range(n_merlons):
        mx = -length / 2 + (i + 0.5) * merlon_spacing
        mv, mf = _make_beveled_box(
            mx, height + merlon_h / 2, -wall_thick / 2 + 0.05,
            merlon_w / 2, merlon_h / 2, 0.08,
            bevel=0.005,
        )
        parts.append((mv, mf))

    # Inner parapet (low wall on walkway side)
    iv, inf = _make_beveled_box(
        0, height + 0.2, wall_thick / 2 + walkway_w - 0.05,
        length / 2, 0.2, 0.05,
        bevel=0.005,
    )
    parts.append((iv, inf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Rampart", verts, faces, category="structural")


def generate_drawbridge_mesh(
    width: float = 3.0,
    length: float = 4.0,
) -> MeshSpec:
    """Generate a drawbridge mesh with chains.

    Args:
        width: Bridge width.
        length: Bridge length.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    plank_thick = 0.1

    # Main bridge deck (planks)
    n_planks = max(6, int(length / 0.3))
    plank_len = length / n_planks
    for i in range(n_planks):
        px = -length / 2 + (i + 0.5) * plank_len
        pv, pf = _make_beveled_box(
            px, -plank_thick / 2, 0,
            plank_len / 2 - 0.005, plank_thick / 2, width / 2,
            bevel=0.003,
        )
        parts.append((pv, pf))

    # Cross beams underneath
    n_beams = 3
    beam_h = 0.06
    for i in range(n_beams):
        bx = -length / 2 + (i + 1) * length / (n_beams + 1)
        bv, bf = _make_box(
            bx, -plank_thick - beam_h / 2, 0,
            0.04, beam_h / 2, width / 2,
        )
        parts.append((bv, bf))

    # Side edge reinforcement
    for z_side in [-width / 2, width / 2]:
        sv, sf = _make_beveled_box(
            0, 0, z_side,
            length / 2, 0.03, 0.04,
            bevel=0.003,
        )
        parts.append((sv, sf))

    # Chains (on each side, from bridge end going up)
    chain_link_r = 0.025
    chain_wire = 0.006
    n_links = 6
    for z_side in [-width / 2 + 0.05, width / 2 - 0.05]:
        for i in range(n_links):
            cy = i * chain_link_r * 2.5
            cx = length / 2 - 0.1
            if i % 2 == 0:
                cv, cf = _make_torus_ring(
                    cx, cy, z_side,
                    chain_link_r, chain_wire,
                    major_segments=6, minor_segments=3,
                )
            else:
                cv, cf = _make_torus_ring(
                    cx, cy, z_side,
                    chain_link_r, chain_wire,
                    major_segments=6, minor_segments=3,
                )
                cv = [(v[2] - z_side + cx, v[1], v[0] - cx + z_side) for v in cv]
            parts.append((cv, cf))

    # Hinge mounts at base end
    for z_side in [-width / 2 + 0.1, width / 2 - 0.1]:
        hv, hf = _make_cylinder(
            -length / 2, 0, z_side,
            0.03, 0.08, segments=6,
        )
        parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Drawbridge", verts, faces, category="structural")


def generate_well_mesh(
    radius: float = 0.5,
    depth: float = 2.0,
    roof: bool = True,
) -> MeshSpec:
    """Generate a stone well with optional roof cover.

    Args:
        radius: Well outer radius.
        depth: Well shaft depth.
        roof: Whether to include a roof structure.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    wall_thick = 0.1
    wall_h = 0.6
    inner_r = radius - wall_thick

    # Well wall (outer cylinder)
    ov, of = _make_cylinder(
        0, 0, 0, radius, wall_h, segments=12, cap_bottom=False,
    )
    parts.append((ov, of))

    # Well wall (inner cylinder - slightly smaller, reversed normals effect via separate mesh)
    iv, inf = _make_cylinder(
        0, 0, 0, inner_r, wall_h, segments=12, cap_bottom=False,
    )
    # Reverse winding for inner wall
    inf_reversed = [tuple(reversed(f)) for f in inf]
    parts.append((iv, inf_reversed))

    # Well rim (top cap ring)
    rim_profile = [
        (inner_r, wall_h),
        (inner_r * 0.95, wall_h + 0.03),
        (radius * 1.05, wall_h + 0.05),
        (radius * 1.08, wall_h + 0.04),
        (radius * 1.05, wall_h + 0.02),
    ]
    rv, rf = _make_lathe(rim_profile, segments=12)
    parts.append((rv, rf))

    # Well shaft (inner dark cylinder going down)
    sv, sf = _make_cylinder(0, -depth, 0, inner_r, depth, segments=12)
    parts.append((sv, sf))

    # Base stone platform
    bv, bf = _make_cylinder(0, -0.05, 0, radius * 1.3, 0.05, segments=12)
    parts.append((bv, bf))

    if roof:
        # Two support posts
        post_h = 1.5
        post_r = 0.04
        for z_side in [-radius * 0.6, radius * 0.6]:
            pv, pf = _make_cylinder(
                0, wall_h, z_side, post_r, post_h, segments=6,
            )
            parts.append((pv, pf))

        # Crossbeam
        beam_y = wall_h + post_h
        cbv, cbf = _make_box(
            0, beam_y, 0,
            0.03, 0.03, radius * 0.7,
        )
        parts.append((cbv, cbf))

        # Roof (two angled planes - A-frame)
        roof_w = radius * 1.3
        roof_d = radius * 1.5
        roof_h = 0.4
        roof_y = beam_y + 0.03

        for side in [-1, 1]:
            rv2, rf2 = _make_box(
                0, roof_y + roof_h / 2, side * roof_d / 4,
                roof_w / 2, 0.02, roof_d / 2,
            )
            parts.append((rv2, rf2))

        # Bucket (small cylinder hanging from beam)
        bucket_profile = [
            (0.06, beam_y - 0.4),
            (0.07, beam_y - 0.38),
            (0.08, beam_y - 0.2),
            (0.08, beam_y - 0.05),
            (0.085, beam_y - 0.03),
        ]
        bkv, bkf = _make_lathe(bucket_profile, segments=8, close_bottom=True)
        parts.append((bkv, bkf))

        # Rope (thin cylinder)
        ropev, ropef = _make_cylinder(0, beam_y - 0.4, 0, 0.005, 0.4, segments=4)
        parts.append((ropev, ropef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Well", verts, faces,
                        has_roof=roof, category="structural")


def generate_ladder_mesh(
    height: float = 3.0,
    rungs: int = 8,
) -> MeshSpec:
    """Generate a ladder mesh.

    Args:
        height: Total ladder height.
        rungs: Number of rungs.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    ladder_w = 0.4
    rail_w = 0.04
    rail_d = 0.025
    rung_r = 0.015
    rung_spacing = height / (rungs + 1)

    # Side rails
    for x_side in [-ladder_w / 2, ladder_w / 2]:
        rv, rf = _make_beveled_box(
            x_side, height / 2, 0,
            rail_w / 2, height / 2, rail_d / 2,
            bevel=0.003,
        )
        parts.append((rv, rf))

    # Rungs
    for i in range(1, rungs + 1):
        ry = i * rung_spacing
        # Rung as a cylinder
        rung_v, rung_f = _make_cylinder(
            -ladder_w / 2 + rail_w / 2, ry, 0,
            rung_r, ladder_w - rail_w, segments=6,
        )
        # Rotate to horizontal (along X)
        r_verts = [(v[1] - ry + (-ladder_w / 2 + rail_w / 2), ry, v[2]) for v in rung_v]
        parts.append((r_verts, rung_f))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Ladder", verts, faces,
                        rungs=rungs, category="structural")


def generate_scaffolding_mesh(
    width: float = 2.0,
    height: float = 4.0,
    levels: int = 3,
) -> MeshSpec:
    """Generate construction scaffolding mesh.

    Args:
        width: Scaffolding width.
        height: Total height.
        levels: Number of platform levels.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    depth = 0.8
    pole_r = 0.025
    pole_segs = 6
    level_h = height / levels

    # Vertical poles (4 corners)
    for cx, cz in [
        (-width / 2, -depth / 2),
        (width / 2, -depth / 2),
        (-width / 2, depth / 2),
        (width / 2, depth / 2),
    ]:
        pv, pf = _make_cylinder(cx, 0, cz, pole_r, height, segments=pole_segs)
        parts.append((pv, pf))

    for level in range(levels):
        ly = (level + 1) * level_h

        # Platform (planks)
        n_planks = max(3, int(width / 0.3))
        plank_w = width / n_planks
        for i in range(n_planks):
            px = -width / 2 + (i + 0.5) * plank_w
            pv, pf = _make_box(
                px, ly, 0,
                plank_w / 2 - 0.005, 0.015, depth / 2,
            )
            parts.append((pv, pf))

        # Horizontal braces (front and back)
        for cz in [-depth / 2, depth / 2]:
            bv, bf = _make_box(
                0, ly - 0.02, cz,
                width / 2, pole_r, pole_r,
            )
            parts.append((bv, bf))

        # Side braces
        for cx in [-width / 2, width / 2]:
            sv, sf = _make_box(
                cx, ly - 0.02, 0,
                pole_r, pole_r, depth / 2,
            )
            parts.append((sv, sf))

    # Diagonal braces (X-patterns on sides)
    for side_z in [-depth / 2, depth / 2]:
        for level in range(levels):
            ly_bot = level * level_h
            ly_top = (level + 1) * level_h
            # Approximate diagonal with a thin box
            diag_len = math.sqrt(width ** 2 + level_h ** 2)
            dv, df = _make_box(
                0, (ly_bot + ly_top) / 2, side_z,
                width / 2, 0.01, pole_r,
            )
            parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Scaffolding", verts, faces,
                        levels=levels, category="structural")


# =========================================================================
# CATEGORY 10: DARK FANTASY SPECIFIC
# =========================================================================


def generate_sacrificial_circle_mesh(
    radius: float = 2.0,
    rune_count: int = 6,
) -> MeshSpec:
    """Generate a ritual/sacrificial circle with rune stones.

    Args:
        radius: Circle radius.
        rune_count: Number of rune stones around the circle.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Ground circle disc
    gv, gf = _make_cylinder(0, -0.02, 0, radius, 0.02, segments=24)
    parts.append((gv, gf))

    # Inner circle groove (ring)
    inner_r = radius * 0.6
    groove_r = radius * 0.55
    irv, irf = _make_torus_ring(
        0, 0.005, 0,
        (inner_r + groove_r) / 2, (inner_r - groove_r) / 2,
        major_segments=24, minor_segments=4,
    )
    parts.append((irv, irf))

    # Outer circle groove
    orv, orf = _make_torus_ring(
        0, 0.005, 0,
        radius * 0.95, 0.015,
        major_segments=24, minor_segments=4,
    )
    parts.append((orv, orf))

    # Rune stones (standing stones around perimeter)
    for i in range(rune_count):
        angle = 2.0 * math.pi * i / rune_count
        sx = math.cos(angle) * radius * 0.8
        sz = math.sin(angle) * radius * 0.8
        stone_h = 0.5 + 0.15 * ((i * 3) % 5 - 2) / 2  # Vary height

        # Stone body (tapered box)
        sv, sf = _make_beveled_box(
            sx, stone_h / 2, sz,
            0.08, stone_h / 2, 0.04,
            bevel=0.008,
        )
        parts.append((sv, sf))

        # Rune carving (small inset box on face)
        rv, rf = _make_box(
            sx + math.cos(angle) * 0.001, stone_h * 0.5,
            sz + math.sin(angle) * 0.001,
            0.015, stone_h * 0.2, 0.002,
        )
        parts.append((rv, rf))

    # Central altar stone (flat)
    av, af = _make_beveled_box(
        0, 0.05, 0,
        0.3, 0.05, 0.3,
        bevel=0.008,
    )
    parts.append((av, af))

    # Channel grooves from center to rune stones (blood channels)
    for i in range(rune_count):
        angle = 2.0 * math.pi * i / rune_count
        mid_r = radius * 0.4
        cx = math.cos(angle) * mid_r
        cz = math.sin(angle) * mid_r
        chan_len = radius * 0.5
        # Approximate channel as thin box along radial direction
        cv, cf = _make_box(
            cx, 0.008, cz,
            0.01, 0.005, chan_len / 2,
        )
        # Rotate to point outward
        ca, sa = math.cos(angle), math.sin(angle)
        c_verts = []
        for v in cv:
            nx = v[0] * ca - v[2] * sa
            nz = v[0] * sa + v[2] * ca
            c_verts.append((nx, v[1], nz))
        parts.append((c_verts, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SacrificialCircle", verts, faces,
                        rune_count=rune_count, category="dark_fantasy")


def generate_corruption_crystal_mesh(
    height: float = 1.5,
    facets: int = 6,
) -> MeshSpec:
    """Generate a corrupted energy crystal.

    Args:
        height: Crystal height.
        facets: Number of crystal facets.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Main crystal (hexagonal prism with pointed ends)
    crystal_r = height * 0.15
    mid_h = height * 0.6
    point_h = height * 0.2

    # Main body
    cv, cf = _make_cylinder(
        0, point_h, 0, crystal_r, mid_h,
        segments=facets, cap_top=False, cap_bottom=False,
    )
    parts.append((cv, cf))

    # Bottom point (cone)
    bv, bf = _make_cone(0, 0, 0, crystal_r, point_h, segments=facets)
    # Flip to point downward
    b_verts = [(v[0], point_h - v[1], v[2]) for v in bv]
    parts.append((b_verts, bf))

    # Top point (cone)
    tv, tf = _make_cone(0, point_h + mid_h, 0, crystal_r, point_h, segments=facets)
    parts.append((tv, tf))

    # Secondary crystal shards growing from base
    import random as _rng
    rng = _rng.Random(42)
    n_shards = max(3, facets // 2)
    for i in range(n_shards):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(crystal_r * 0.8, crystal_r * 1.5)
        shard_h = rng.uniform(height * 0.2, height * 0.4)
        shard_r = rng.uniform(crystal_r * 0.2, crystal_r * 0.4)
        sx = math.cos(angle) * dist
        sz = math.sin(angle) * dist

        # Small shard (tapered cylinder + cone)
        sv, sf = _make_tapered_cylinder(
            sx, 0, sz, shard_r, shard_r * 0.6, shard_h * 0.7,
            segments=facets, rings=2,
            cap_bottom=True, cap_top=False,
        )
        parts.append((sv, sf))
        # Shard point
        spv, spf = _make_cone(sx, shard_h * 0.7, sz, shard_r * 0.6, shard_h * 0.3, segments=facets)
        parts.append((spv, spf))

    # Base cluster (rough ground)
    ground_r = crystal_r * 3
    gv, gf = _make_cylinder(0, -0.02, 0, ground_r, 0.04, segments=8)
    parts.append((gv, gf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("CorruptionCrystal", verts, faces,
                        facets=facets, category="dark_fantasy")


def generate_veil_tear_mesh(
    width: float = 2.0,
    height: float = 3.0,
) -> MeshSpec:
    """Generate a reality tear / portal frame mesh.

    Args:
        width: Tear width.
        height: Tear height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Jagged frame (irregular ring of shards)
    n_shards = 16
    frame_thick = 0.08
    frame_depth = 0.15

    # Create jagged border using displaced points on an ellipse
    import random as _rng
    rng = _rng.Random(777)

    for i in range(n_shards):
        angle = 2.0 * math.pi * i / n_shards
        next_angle = 2.0 * math.pi * (i + 1) / n_shards

        # Elliptical base shape with jagged displacement
        r_inner = 0.85 + rng.uniform(-0.1, 0.1)
        r_outer = 1.15 + rng.uniform(-0.1, 0.15)

        ix = math.cos(angle) * width / 2 * r_inner
        iy = math.sin(angle) * height / 2 * r_inner + height / 2
        ox = math.cos(angle) * width / 2 * r_outer
        oy = math.sin(angle) * height / 2 * r_outer + height / 2

        nix = math.cos(next_angle) * width / 2 * r_inner
        niy = math.sin(next_angle) * height / 2 * r_inner + height / 2
        nox = math.cos(next_angle) * width / 2 * r_outer
        noy = math.sin(next_angle) * height / 2 * r_outer + height / 2

        # Shard as beveled box segment
        cx = (ix + ox + nix + nox) / 4
        cy = (iy + oy + niy + noy) / 4
        seg_w = max(abs(ox - ix), abs(nox - nix), 0.05)
        seg_h = max(abs(oy - iy), abs(noy - niy), 0.05)

        sv, sf = _make_beveled_box(
            cx, cy, 0,
            seg_w / 2, seg_h / 2, frame_depth / 2,
            bevel=0.005,
        )
        parts.append((sv, sf))

    # Energy wisps (small spheres scattered in the tear)
    for i in range(6):
        wx = rng.uniform(-width / 3, width / 3)
        wy = rng.uniform(height / 3, height * 2 / 3)
        wr = rng.uniform(0.03, 0.06)
        wv, wf = _make_sphere(wx, wy, 0, wr, rings=3, sectors=4)
        parts.append((wv, wf))

    # Ground scorching (disc at base)
    gv, gf = _make_cylinder(0, -0.01, 0, width / 2, 0.01, segments=12)
    parts.append((gv, gf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("VeilTear", verts, faces, category="dark_fantasy")


def generate_soul_cage_mesh(
    size: float = 0.8,
    bars: int = 8,
) -> MeshSpec:
    """Generate an ethereal soul cage/prison.

    Args:
        size: Cage diameter.
        bars: Number of vertical bars.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    r = size / 2
    cage_h = size * 1.4
    bar_r = 0.008

    # Top ring
    trv, trf = _make_torus_ring(
        0, cage_h, 0,
        r, 0.015,
        major_segments=bars * 2, minor_segments=4,
    )
    parts.append((trv, trf))

    # Bottom ring
    brv, brf = _make_torus_ring(
        0, 0, 0,
        r, 0.015,
        major_segments=bars * 2, minor_segments=4,
    )
    parts.append((brv, brf))

    # Middle ring
    mrv, mrf = _make_torus_ring(
        0, cage_h / 2, 0,
        r * 1.1, 0.012,
        major_segments=bars * 2, minor_segments=3,
    )
    parts.append((mrv, mrf))

    # Curved bars (approximate with segmented cylinders)
    for i in range(bars):
        angle = 2.0 * math.pi * i / bars
        n_segs = 6
        for j in range(n_segs):
            t0 = j / n_segs
            t1 = (j + 1) / n_segs
            # Barrel curve: wider at middle
            bulge0 = 1.0 + 0.15 * math.sin(t0 * math.pi)
            bulge1 = 1.0 + 0.15 * math.sin(t1 * math.pi)

            x0 = math.cos(angle) * r * bulge0
            z0 = math.sin(angle) * r * bulge0
            y0 = t0 * cage_h
            x1 = math.cos(angle) * r * bulge1
            z1 = math.sin(angle) * r * bulge1
            y1 = t1 * cage_h

            # Segment as small cylinder
            seg_len = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
            sv, sf = _make_box(
                (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2,
                bar_r, seg_len / 2, bar_r,
            )
            parts.append((sv, sf))

    # Suspension chain (top)
    chain_r = 0.018
    chain_wire = 0.005
    for i in range(3):
        cy = cage_h + i * chain_r * 2.5
        if i % 2 == 0:
            cv, cf = _make_torus_ring(
                0, cy, 0, chain_r, chain_wire,
                major_segments=6, minor_segments=3,
            )
        else:
            cv, cf = _make_torus_ring(
                0, cy, 0, chain_r, chain_wire,
                major_segments=6, minor_segments=3,
            )
            cv = [(v[2], v[1], v[0]) for v in cv]
        parts.append((cv, cf))

    # Soul wisp inside (small sphere)
    wv, wf = _make_sphere(0, cage_h / 2, 0, size * 0.1, rings=4, sectors=6)
    parts.append((wv, wf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SoulCage", verts, faces,
                        bars=bars, category="dark_fantasy")


def generate_blood_fountain_mesh(
    tiers: int = 2,
) -> MeshSpec:
    """Generate a dark fantasy blood fountain.

    Args:
        tiers: Number of basin tiers (1-3).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    tiers = max(1, min(3, tiers))
    basin_size = 1.2

    for tier in range(tiers):
        scale = 1.0 - tier * 0.3
        r = basin_size * 0.5 * scale
        y_offset = tier * basin_size * 0.4

        # Basin (skull-decorated bowl via lathe)
        basin_profile = [
            (r * 0.12, y_offset),
            (r * 0.2, y_offset + 0.02),
            (r * 0.85, y_offset + 0.04),
            (r * 1.0, y_offset + 0.1),
            (r * 1.08, y_offset + 0.13),
            (r * 1.08, y_offset + 0.18),
            (r * 0.95, y_offset + 0.18),
            (r * 0.85, y_offset + 0.14),
            (r * 0.45, y_offset + 0.12),
        ]
        bv, bf = _make_lathe(basin_profile, segments=16)
        parts.append((bv, bf))

        # Skull decorations around rim
        n_skulls = 4 + tier * 2
        for i in range(n_skulls):
            angle = 2.0 * math.pi * i / n_skulls
            skull_x = math.cos(angle) * r * 1.05
            skull_z = math.sin(angle) * r * 1.05
            skull_y = y_offset + 0.15
            sv, sf = _make_sphere(skull_x, skull_y, skull_z, 0.03, rings=3, sectors=4)
            parts.append((sv, sf))

        # Pedestal for upper tiers
        if tier > 0:
            ped_r = r * 0.2
            prev_y = (tier - 1) * basin_size * 0.4 + 0.18
            pv, pf = _make_tapered_cylinder(
                0, prev_y, 0,
                ped_r * 1.3, ped_r, basin_size * 0.4 - 0.18,
                segments=8, rings=3,
            )
            parts.append((pv, pf))

    # Central spout (demonic figure)
    top_y = (tiers - 1) * basin_size * 0.4 + 0.18
    # Body
    spout_profile = [
        (0.04, top_y),
        (0.035, top_y + 0.08),
        (0.05, top_y + 0.15),
        (0.04, top_y + 0.22),
        (0.03, top_y + 0.28),
    ]
    sv, sf = _make_lathe(spout_profile, segments=8, close_top=True)
    parts.append((sv, sf))

    # Horns on spout
    for side in [-1, 1]:
        hv, hf = _make_cone(
            side * 0.03, top_y + 0.28, 0,
            0.008, 0.08, segments=4,
        )
        parts.append((hv, hf))

    # Base platform (hexagonal)
    base_r = basin_size * 0.6
    bpv, bpf = _make_cylinder(0, -0.06, 0, base_r, 0.06, segments=6)
    parts.append((bpv, bpf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("BloodFountain", verts, faces,
                        tiers=tiers, category="dark_fantasy")


def generate_bone_throne_mesh() -> MeshSpec:
    """Generate a throne made of bones and skulls.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    seat_w = 0.7
    seat_d = 0.6
    seat_h = 0.5
    back_h = 1.5

    # Seat (beveled platform)
    sv, sf = _make_beveled_box(
        0, seat_h, 0,
        seat_w / 2, 0.04, seat_d / 2,
        bevel=0.008,
    )
    parts.append((sv, sf))

    # Bone legs (4 femur-style)
    for cx, cz in [
        (-seat_w / 2 * 0.8, -seat_d / 2 * 0.8),
        (seat_w / 2 * 0.8, -seat_d / 2 * 0.8),
        (-seat_w / 2 * 0.8, seat_d / 2 * 0.8),
        (seat_w / 2 * 0.8, seat_d / 2 * 0.8),
    ]:
        # Femur bone shape
        lv, lf = _make_tapered_cylinder(
            cx, 0, cz, 0.04, 0.025, seat_h * 0.7,
            segments=6, rings=2,
        )
        parts.append((lv, lf))
        # Knobby joint
        jv, jf = _make_sphere(cx, seat_h * 0.7, cz, 0.03, rings=3, sectors=5)
        parts.append((jv, jf))
        # Upper shaft
        uv, uf = _make_cylinder(cx, seat_h * 0.7 + 0.02, cz, 0.025, seat_h * 0.25, segments=6)
        parts.append((uv, uf))

    # Backrest frame (rising from back edge)
    # Central spine column of bones
    spine_x = 0
    spine_z = -seat_d / 2
    for i in range(6):
        by = seat_h + i * (back_h - seat_h) / 6
        bone_r = 0.025 - i * 0.002
        bv, bf = _make_cylinder(spine_x, by, spine_z, bone_r, (back_h - seat_h) / 6 * 0.8, segments=6)
        parts.append((bv, bf))
        # Joint sphere
        jv, jf = _make_sphere(spine_x, by + (back_h - seat_h) / 6 * 0.8, spine_z, bone_r * 1.1, rings=3, sectors=4)
        parts.append((jv, jf))

    # Side bone armrests
    for side in [-1, 1]:
        ax = side * seat_w / 2 * 0.9
        # Arm bone (horizontal)
        av, af = _make_tapered_cylinder(
            ax, seat_h + 0.25, seat_d / 4, 0.03, 0.02, seat_d * 0.5,
            segments=6, rings=2,
        )
        # Rotate to run along Z by swapping axes
        a_verts = [(v[0], seat_h + 0.25, v[1] - (seat_h + 0.25) + seat_d / 4) for v in av]
        parts.append((a_verts, af))

    # Skull decorations on backrest top
    for i, x_off in enumerate([-0.12, 0, 0.12]):
        skull_r = 0.05 if i == 1 else 0.04  # Center skull larger
        sx, sy, sz = x_off, back_h + skull_r, -seat_d / 2
        # Cranium
        cv, cf = _make_sphere(sx, sy, sz, skull_r, rings=4, sectors=6)
        parts.append((cv, cf))
        # Jaw
        jv, jf = _make_box(sx, sy - skull_r * 0.5, sz + skull_r * 0.3,
                           skull_r * 0.4, skull_r * 0.25, skull_r * 0.3)
        parts.append((jv, jf))

    # Rib bones fanning out from backrest
    n_ribs = 4
    for side in [-1, 1]:
        for i in range(n_ribs):
            ry = seat_h + 0.3 + i * 0.2
            # Each rib curves outward
            rib_r = 0.012
            for j in range(3):
                t = (j + 1) / 4
                rx = side * (0.05 + t * seat_w * 0.4)
                rz = -seat_d / 2 + t * 0.15
                rv, rf = _make_sphere(rx, ry, rz, rib_r, rings=3, sectors=4)
                parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("BoneThrone", verts, faces, category="dark_fantasy")


def generate_dark_obelisk_mesh(
    height: float = 3.0,
    runes: int = 4,
) -> MeshSpec:
    """Generate an ominous monolith/obelisk with rune engravings.

    Args:
        height: Obelisk height.
        runes: Number of rune engravings.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    base_w = height * 0.15
    top_w = base_w * 0.6

    # Main body (tapered box - 4-sided)
    body_verts: list[tuple[float, float, float]] = []
    body_faces: list[tuple[int, ...]] = []

    # Bottom face
    hw_b = base_w / 2
    hw_t = top_w / 2
    body_verts.extend([
        (-hw_b, 0, -hw_b),
        (hw_b, 0, -hw_b),
        (hw_b, 0, hw_b),
        (-hw_b, 0, hw_b),
    ])
    # Top face
    body_verts.extend([
        (-hw_t, height, -hw_t),
        (hw_t, height, -hw_t),
        (hw_t, height, hw_t),
        (-hw_t, height, hw_t),
    ])

    # Faces
    body_faces.append((3, 2, 1, 0))  # Bottom
    body_faces.append((4, 5, 6, 7))  # Top
    body_faces.append((0, 1, 5, 4))  # Front
    body_faces.append((2, 3, 7, 6))  # Back
    body_faces.append((3, 0, 4, 7))  # Left
    body_faces.append((1, 2, 6, 5))  # Right
    parts.append((body_verts, body_faces))

    # Pyramidion (top point)
    pv, pf = _make_cone(0, height, 0, top_w / 2 * 1.1, height * 0.08, segments=4)
    parts.append((pv, pf))

    # Base platform
    bpv, bpf = _make_beveled_box(
        0, -0.05, 0,
        base_w * 0.8, 0.05, base_w * 0.8,
        bevel=0.008,
    )
    parts.append((bpv, bpf))

    # Second base tier
    b2v, b2f = _make_beveled_box(
        0, -0.12, 0,
        base_w * 1.0, 0.04, base_w * 1.0,
        bevel=0.008,
    )
    parts.append((b2v, b2f))

    # Rune engravings (small raised rectangles on faces)
    rune_h = 0.06
    rune_w = 0.04
    for i in range(runes):
        face_idx = i % 4
        ry = height * 0.2 + i * (height * 0.6) / max(runes - 1, 1)
        # Calculate face normal direction
        face_offsets = [
            (0, 0, -1),  # Front
            (0, 0, 1),   # Back
            (-1, 0, 0),  # Left
            (1, 0, 0),   # Right
        ]
        dx, _, dz = face_offsets[face_idx]
        # Width at this height
        t = ry / height
        w_at_h = base_w / 2 * (1 - t) + top_w / 2 * t
        rx = dx * (w_at_h + 0.002)
        rz = dz * (w_at_h + 0.002)

        rv, rf = _make_box(
            rx, ry, rz,
            rune_w / 2 if abs(dx) < 0.5 else 0.002,
            rune_h / 2,
            rune_w / 2 if abs(dz) < 0.5 else 0.002,
        )
        parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("DarkObelisk", verts, faces,
                        runes=runes, category="dark_fantasy")


def generate_spider_web_mesh(
    radius: float = 1.0,
    rings: int = 5,
    radials: int = 8,
) -> MeshSpec:
    """Generate a geometric spider web mesh.

    Args:
        radius: Web radius.
        rings: Number of concentric rings.
        radials: Number of radial strands.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    strand_r = 0.003
    strand_segs = 3

    # Center point hub
    cv, cf = _make_sphere(0, 0, 0, strand_r * 3, rings=3, sectors=4)
    parts.append((cv, cf))

    # Radial strands (from center to edge)
    for i in range(radials):
        angle = 2.0 * math.pi * i / radials
        ex = math.cos(angle) * radius
        ez = math.sin(angle) * radius

        # Strand as series of thin boxes
        n_segs = rings * 2
        for j in range(n_segs):
            t0 = j / n_segs
            t1 = (j + 1) / n_segs
            x0 = math.cos(angle) * radius * t0
            z0 = math.sin(angle) * radius * t0
            x1 = math.cos(angle) * radius * t1
            z1 = math.sin(angle) * radius * t1
            # Slight sag
            sag = -0.02 * math.sin(t0 * math.pi) * radius
            sv, sf = _make_box(
                (x0 + x1) / 2, sag, (z0 + z1) / 2,
                strand_r, strand_r, radius / n_segs / 2,
            )
            # Rotate to align with radial direction
            ca, sa = math.cos(angle), math.sin(angle)
            s_verts = []
            for v in sv:
                nx = v[0] * ca - v[2] * sa
                nz = v[0] * sa + v[2] * ca
                s_verts.append((nx, v[1], nz))
            parts.append((s_verts, sf))

    # Concentric rings (spiral capture thread)
    for ring in range(1, rings + 1):
        ring_r = radius * ring / rings
        n_arc = radials * 3
        for i in range(n_arc):
            a0 = 2.0 * math.pi * i / n_arc
            a1 = 2.0 * math.pi * (i + 1) / n_arc
            x0 = math.cos(a0) * ring_r
            z0 = math.sin(a0) * ring_r
            x1 = math.cos(a1) * ring_r
            z1 = math.sin(a1) * ring_r
            sag = -0.01 * math.sin((ring / rings) * math.pi) * radius
            sv, sf = _make_box(
                (x0 + x1) / 2, sag, (z0 + z1) / 2,
                strand_r, strand_r, ring_r * math.pi / n_arc,
            )
            # Rotate segment to follow arc
            mid_angle = (a0 + a1) / 2
            ca, sa = math.cos(mid_angle + math.pi / 2), math.sin(mid_angle + math.pi / 2)
            s_verts = []
            for v in sv:
                nx = v[0] * ca - v[2] * sa
                nz = v[0] * sa + v[2] * ca
                s_verts.append((nx, v[1], nz))
            parts.append((s_verts, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SpiderWeb", verts, faces,
                        rings_count=rings, radials=radials, category="dark_fantasy")


def generate_coffin_mesh(
    style: str = "wooden_simple",
) -> MeshSpec:
    """Generate a coffin mesh.

    Args:
        style: "wooden_simple", "stone_ornate", or "iron_bound".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    # Classic hexagonal coffin shape
    coffin_l = 1.9
    coffin_w = 0.6
    coffin_h = 0.35
    shoulder_l = coffin_l * 0.35  # Where it widens

    if style == "wooden_simple":
        bevel = 0.005
    elif style == "stone_ornate":
        bevel = 0.01
    else:
        bevel = 0.008

    # Coffin body (hexagonal cross-section extruded)
    # Create as a profile in XY, extrude along Z (which we treat as depth)
    # Hexagonal coffin: wider at shoulders, narrow at head and feet
    half_l = coffin_l / 2
    half_w = coffin_w / 2
    head_w = coffin_w * 0.35

    coffin_profile = [
        (-half_l, -head_w / 2),          # Foot left
        (-half_l, head_w / 2),           # Foot right
        (-half_l + shoulder_l, half_w),  # Shoulder right
        (half_l * 0.3, half_w * 0.9),   # Upper body right
        (half_l, head_w / 2),            # Head right
        (half_l, -head_w / 2),           # Head left
        (half_l * 0.3, -half_w * 0.9),  # Upper body left
        (-half_l + shoulder_l, -half_w), # Shoulder left
    ]

    pv, pf = _make_profile_extrude(coffin_profile, coffin_h)
    # Rotate so coffin lies flat (depth becomes height)
    p_verts = [(v[0], v[2], v[1]) for v in pv]
    parts.append((p_verts, pf))

    if style == "stone_ornate":
        # Carved cross on lid
        cross_h = 0.005
        cv, cf = _make_box(0, coffin_h / 2 + cross_h, 0, 0.03, cross_h, coffin_l * 0.3)
        parts.append((cv, cf))
        ch, chf = _make_box(0, coffin_h / 2 + cross_h, coffin_l * 0.1, 0.15, cross_h, 0.03)
        parts.append((ch, chf))

        # Decorative border on lid edge
        border_r = 0.008
        for i in range(len(coffin_profile)):
            x0, z0 = coffin_profile[i]
            x1, z1 = coffin_profile[(i + 1) % len(coffin_profile)]
            bv, bf = _make_box(
                (x0 + x1) / 2, coffin_h / 2 + 0.003, (z0 + z1) / 2,
                border_r, border_r,
                math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2) / 2,
            )
            parts.append((bv, bf))

    elif style == "iron_bound":
        # Iron bands
        for band_x in [-coffin_l * 0.3, 0, coffin_l * 0.3]:
            bv, bf = _make_box(
                band_x, coffin_h / 2 + 0.003, 0,
                0.02, 0.005, half_w + 0.01,
            )
            parts.append((bv, bf))

        # Corner rivets
        for px, pz in coffin_profile:
            rv, rf = _make_sphere(px, coffin_h / 2 + 0.005, pz, 0.008, rings=3, sectors=4)
            parts.append((rv, rf))

        # Lock/latch
        lv, lf = _make_box(0, coffin_h / 2 + 0.005, half_w, 0.04, 0.01, 0.02)
        parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Coffin_{style}", verts, faces,
                        style=style, category="dark_fantasy")


def generate_gibbet_mesh(
    height: float = 3.5,
) -> MeshSpec:
    """Generate a gibbet (hanging cage on pole) mesh.

    Args:
        height: Total pole height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    pole_r = 0.04
    cage_r = 0.25
    cage_h = 0.8

    # Main pole
    pv, pf = _make_cylinder(0, 0, 0, pole_r, height, segments=8)
    parts.append((pv, pf))

    # Cross arm at top (extends to one side)
    arm_len = 0.6
    arm_y = height - 0.1
    av, af = _make_box(arm_len / 2, arm_y, 0, arm_len / 2, pole_r * 0.8, pole_r * 0.8)
    parts.append((av, af))

    # Hanging chain from arm tip
    chain_r = 0.015
    chain_wire = 0.004
    chain_x = arm_len
    for i in range(4):
        cy = arm_y - (i + 1) * chain_r * 2.5
        if i % 2 == 0:
            cv, cf = _make_torus_ring(
                chain_x, cy, 0, chain_r, chain_wire,
                major_segments=6, minor_segments=3,
            )
        else:
            cv, cf = _make_torus_ring(
                chain_x, cy, 0, chain_r, chain_wire,
                major_segments=6, minor_segments=3,
            )
            cv = [(v[2] - 0 + chain_x, v[1], v[0] - chain_x + 0) for v in cv]
        parts.append((cv, cf))

    # Cage body
    cage_y = arm_y - 4 * chain_r * 2.5 - cage_h
    cage_bar_r = 0.006
    n_cage_bars = 8

    # Cage top ring
    trv, trf = _make_torus_ring(
        chain_x, cage_y + cage_h, 0,
        cage_r, 0.01,
        major_segments=n_cage_bars * 2, minor_segments=3,
    )
    parts.append((trv, trf))

    # Cage bottom ring
    brv, brf = _make_torus_ring(
        chain_x, cage_y, 0,
        cage_r * 0.7, 0.01,
        major_segments=n_cage_bars * 2, minor_segments=3,
    )
    parts.append((brv, brf))

    # Cage bars
    for i in range(n_cage_bars):
        angle = 2.0 * math.pi * i / n_cage_bars
        top_x = chain_x + math.cos(angle) * cage_r
        top_z = math.sin(angle) * cage_r
        bot_x = chain_x + math.cos(angle) * cage_r * 0.7
        bot_z = math.sin(angle) * cage_r * 0.7

        # Approximate curved bar as segments
        n_segs = 4
        for j in range(n_segs):
            t0 = j / n_segs
            t1 = (j + 1) / n_segs
            x0 = top_x * (1 - t0) + bot_x * t0
            z0 = top_z * (1 - t0) + bot_z * t0
            y0 = cage_y + cage_h * (1 - t0)
            x1 = top_x * (1 - t1) + bot_x * t1
            z1 = top_z * (1 - t1) + bot_z * t1
            y1 = cage_y + cage_h * (1 - t1)

            sv, sf = _make_box(
                (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2,
                cage_bar_r, cage_h / n_segs / 2, cage_bar_r,
            )
            parts.append((sv, sf))

    # Pole base (wider)
    bv, bf = _make_tapered_cylinder(0, -0.05, 0, pole_r * 2, pole_r, 0.15, segments=8)
    parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Gibbet", verts, faces, category="dark_fantasy")


# =========================================================================
# CATEGORY 10: CONTAINERS & LOOT OBJECTS
# =========================================================================


def generate_urn_mesh(
    height: float = 0.5,
    style: str = "ceramic_round",
) -> MeshSpec:
    """Generate an urn/vase mesh.

    Args:
        height: Urn height.
        style: "ceramic_round", "metal_ornate", or "stone_burial".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 16

    if style == "ceramic_round":
        profile = [
            (0.001, 0),
            (height * 0.22, height * 0.01),
            (height * 0.32, height * 0.08),
            (height * 0.38, height * 0.20),
            (height * 0.40, height * 0.35),
            (height * 0.38, height * 0.55),
            (height * 0.30, height * 0.70),
            (height * 0.18, height * 0.82),
            (height * 0.14, height * 0.88),
            (height * 0.16, height * 0.92),
            (height * 0.18, height * 0.95),
            (height * 0.17, height * 0.98),
            (height * 0.15, height * 1.0),
        ]
        bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((bv, bf))

    elif style == "metal_ornate":
        profile = [
            (0.001, 0),
            (height * 0.18, height * 0.02),
            (height * 0.20, height * 0.05),
            (height * 0.25, height * 0.10),
            (height * 0.32, height * 0.25),
            (height * 0.35, height * 0.40),
            (height * 0.32, height * 0.55),
            (height * 0.25, height * 0.65),
            (height * 0.18, height * 0.72),
            (height * 0.12, height * 0.78),
            (height * 0.10, height * 0.82),
            (height * 0.11, height * 0.86),
            (height * 0.14, height * 0.90),
            (height * 0.15, height * 0.93),
            (height * 0.14, height * 0.96),
            (height * 0.12, height * 1.0),
        ]
        bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((bv, bf))

        # Ornamental band ring
        band_r = height * 0.36
        tv, tf = _make_torus_ring(0, height * 0.40, 0, band_r, height * 0.012,
                                  major_segments=segs, minor_segments=4)
        parts.append((tv, tf))
        tv2, tf2 = _make_torus_ring(0, height * 0.25, 0, height * 0.26, height * 0.008,
                                    major_segments=segs, minor_segments=4)
        parts.append((tv2, tf2))

        # Two ornate handles
        for angle_off in [0, math.pi]:
            handle_segs = 8
            for s in range(handle_segs):
                t = s / handle_segs
                a = math.pi * 0.3 + t * math.pi * 0.4
                hr = height * 0.08
                hx = math.cos(angle_off) * (height * 0.30 + math.sin(a) * hr)
                hz = math.sin(angle_off) * (height * 0.30 + math.sin(a) * hr)
                hy = height * 0.55 + math.cos(a) * hr * 2
                cv, cf = _make_sphere(hx, hy, hz, height * 0.015, rings=3, sectors=4)
                parts.append((cv, cf))

    else:  # stone_burial
        profile = [
            (0.001, 0),
            (height * 0.25, height * 0.02),
            (height * 0.30, height * 0.08),
            (height * 0.32, height * 0.20),
            (height * 0.30, height * 0.60),
            (height * 0.28, height * 0.70),
            (height * 0.22, height * 0.80),
            (height * 0.18, height * 0.88),
            (height * 0.15, height * 0.92),
            (height * 0.12, height * 0.95),
            (height * 0.10, height * 0.98),
            (0.001, height * 1.0),
        ]
        bv, bf = _make_lathe(profile, segments=12, close_bottom=True, close_top=True)
        parts.append((bv, bf))

        # Flat stone lid on top
        lv, lf = _make_cylinder(0, height * 0.95, 0, height * 0.20, height * 0.06,
                                segments=12)
        parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Urn_{style}", verts, faces, style=style, category="container")


def generate_crate_mesh(
    size: float = 0.6,
    condition: str = "new",
) -> MeshSpec:
    """Generate a wooden crate mesh.

    Args:
        size: Crate dimension (cube-ish).
        condition: "new", "weathered", or "broken_open".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    hs = size / 2
    plank_t = size * 0.02  # plank thickness
    bevel = size * 0.005

    if condition == "broken_open":
        # Bottom
        bv, bf = _make_beveled_box(0, plank_t, 0, hs, plank_t, hs, bevel=bevel)
        parts.append((bv, bf))
        # Three sides (one missing/broken)
        for side in range(3):
            if side == 0:
                sv, sf = _make_beveled_box(-hs, hs, 0, plank_t, hs, hs, bevel=bevel)
            elif side == 1:
                sv, sf = _make_beveled_box(hs, hs, 0, plank_t, hs, hs, bevel=bevel)
            else:
                sv, sf = _make_beveled_box(0, hs, -hs, hs, hs, plank_t, bevel=bevel)
            parts.append((sv, sf))
        # Broken plank leaning against side
        plank_v, plank_f = _make_beveled_box(
            hs * 0.3, hs * 0.4, hs + plank_t * 2,
            hs * 0.8, hs * 0.6, plank_t,
            bevel=bevel,
        )
        parts.append((plank_v, plank_f))
    else:
        # Full crate
        bv, bf = _make_beveled_box(0, hs, 0, hs, hs, hs, bevel=bevel)
        parts.append((bv, bf))

        # Plank strips on each face
        strip_count = 3
        strip_w = size * 0.08
        for i in range(strip_count):
            t = (i + 1) / (strip_count + 1)
            z_pos = -hs + t * size
            # Front/back strips
            sv, sf = _make_box(0, hs, z_pos, hs + plank_t, strip_w, plank_t)
            parts.append((sv, sf))

        # Corner posts
        post_r = size * 0.03
        for xo in [-hs, hs]:
            for zo in [-hs, hs]:
                pv, pf = _make_box(xo, hs, zo, post_r, hs, post_r)
                parts.append((pv, pf))

        if condition == "weathered":
            # Add some damage - dent on one side (inset box)
            dv, df = _make_box(hs * 0.3, hs * 0.6, hs + plank_t,
                               hs * 0.2, hs * 0.15, plank_t * 0.5)
            parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Crate_{condition}", verts, faces,
                        condition=condition, category="container")


def generate_sack_mesh(
    fullness: float = 0.7,
) -> MeshSpec:
    """Generate a grain sack mesh.

    Args:
        fullness: 0.0 (empty/flat) to 1.0 (fully stuffed round).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    fullness = max(0.0, min(1.0, fullness))
    parts = []
    segs = 12
    h = 0.4
    base_r = 0.15

    # Body shape changes with fullness
    bulge = 0.6 + fullness * 0.4
    top_pinch = 0.3 + (1.0 - fullness) * 0.3
    droop = (1.0 - fullness) * 0.15

    profile = [
        (base_r * 0.8, 0),
        (base_r * bulge, h * 0.05),
        (base_r * bulge * 1.1, h * 0.20),
        (base_r * bulge * 1.15, h * 0.40),
        (base_r * bulge * 1.0, h * 0.60 - droop),
        (base_r * bulge * 0.7, h * 0.75 - droop),
        (base_r * top_pinch, h * 0.85 - droop),
        (base_r * 0.15, h * 0.92 - droop),
        (base_r * 0.08, h * 0.95 - droop),
        (0.001, h * 1.0 - droop),
    ]
    bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((bv, bf))

    # Tied-off top knot (torus at neck)
    knot_y = h * 0.88 - droop
    knot_r = base_r * 0.12
    tv, tf = _make_torus_ring(0, knot_y, 0, base_r * 0.12, knot_r * 0.5,
                              major_segments=segs, minor_segments=4)
    parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Sack", verts, faces, fullness=fullness, category="container")


def generate_basket_mesh(
    size: float = 0.3,
    handle: bool = True,
) -> MeshSpec:
    """Generate a woven basket mesh.

    Args:
        size: Overall basket size.
        handle: Whether to include an arched handle.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 16
    h = size * 0.8
    r_bottom = size * 0.35
    r_top = size * 0.5

    # Basket body - tapered cylinder with woven band rings
    profile = [
        (r_bottom, 0),
        (r_bottom * 1.02, h * 0.05),
        (r_bottom + (r_top - r_bottom) * 0.25, h * 0.25),
        (r_bottom + (r_top - r_bottom) * 0.50, h * 0.50),
        (r_bottom + (r_top - r_bottom) * 0.75, h * 0.75),
        (r_top, h * 0.95),
        (r_top * 1.03, h),
    ]
    bv, bf = _make_lathe(profile, segments=segs, close_bottom=True)
    parts.append((bv, bf))

    # Rim at top
    tv, tf = _make_torus_ring(0, h, 0, r_top * 1.03, size * 0.02,
                              major_segments=segs, minor_segments=4)
    parts.append((tv, tf))

    # Woven band rings for visual detail
    for band_t in [0.2, 0.5, 0.8]:
        band_y = h * band_t
        band_r = r_bottom + (r_top - r_bottom) * band_t + 0.003
        tv2, tf2 = _make_torus_ring(0, band_y, 0, band_r, size * 0.008,
                                    major_segments=segs, minor_segments=3)
        parts.append((tv2, tf2))

    if handle:
        # Arched handle across the top
        handle_segs = 12
        handle_r = size * 0.015
        for i in range(handle_segs):
            t = i / (handle_segs - 1)
            angle = math.pi * t
            hx = math.cos(angle) * r_top * 0.8
            hy = h + math.sin(angle) * size * 0.35
            cv, cf = _make_sphere(hx, hy, 0, handle_r, rings=3, sectors=4)
            parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Basket", verts, faces, handle=handle, category="container")


def generate_treasure_pile_mesh(
    size: float = 0.5,
    coin_count: int = 20,
) -> MeshSpec:
    """Generate a pile of coins and gems.

    Args:
        size: Pile spread radius.
        coin_count: Number of coins to scatter.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(42)
    parts = []

    # Base mound (flattened sphere)
    mound_profile = [
        (0.001, 0),
        (size * 0.6, size * 0.02),
        (size * 0.8, size * 0.06),
        (size * 0.9, size * 0.10),
        (size * 0.7, size * 0.16),
        (size * 0.4, size * 0.20),
        (0.001, size * 0.22),
    ]
    mv, mf = _make_lathe(mound_profile, segments=12, close_bottom=True, close_top=True)
    parts.append((mv, mf))

    # Scatter coins (thin cylinders)
    for _ in range(coin_count):
        cx = rng.uniform(-size * 0.7, size * 0.7)
        cz = rng.uniform(-size * 0.7, size * 0.7)
        dist = math.sqrt(cx * cx + cz * cz)
        if dist > size * 0.8:
            continue
        cy = size * 0.15 * (1.0 - dist / size) + rng.uniform(0, size * 0.05)
        coin_r = rng.uniform(size * 0.025, size * 0.04)
        cv, cf = _make_cylinder(cx, cy, cz, coin_r, size * 0.005, segments=6)
        parts.append((cv, cf))

    # A few gem shapes (octahedra approximated as double cones)
    gem_count = max(2, coin_count // 5)
    for _ in range(gem_count):
        gx = rng.uniform(-size * 0.4, size * 0.4)
        gz = rng.uniform(-size * 0.4, size * 0.4)
        gy = size * 0.15 + rng.uniform(0, size * 0.08)
        gem_r = rng.uniform(size * 0.02, size * 0.04)
        # Top cone
        cv, cf = _make_cone(gx, gy, gz, gem_r, gem_r * 1.2, segments=6)
        parts.append((cv, cf))
        # Bottom inverted cone (approximated as a small sphere)
        sv, sf = _make_sphere(gx, gy - gem_r * 0.3, gz, gem_r * 0.6,
                              rings=3, sectors=6)
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("TreasurePile", verts, faces,
                        coin_count=coin_count, category="container")


def generate_potion_bottle_mesh(
    style: str = "round_flask",
) -> MeshSpec:
    """Generate a potion bottle mesh.

    Args:
        style: "round_flask", "tall_vial", "skull_bottle", or "crystal_decanter".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 12

    if style == "round_flask":
        profile = [
            (0.001, 0),
            (0.05, 0.005),
            (0.08, 0.02),
            (0.10, 0.05),
            (0.11, 0.08),
            (0.10, 0.12),
            (0.08, 0.15),
            (0.04, 0.17),
            (0.025, 0.18),
            (0.025, 0.22),
            (0.028, 0.225),
            (0.025, 0.23),
        ]
        bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((bv, bf))

        # Cork/stopper
        sv, sf = _make_cylinder(0, 0.225, 0, 0.022, 0.025, segments=6)
        parts.append((sv, sf))

    elif style == "tall_vial":
        profile = [
            (0.001, 0),
            (0.03, 0.005),
            (0.035, 0.02),
            (0.035, 0.20),
            (0.03, 0.22),
            (0.02, 0.24),
            (0.015, 0.26),
            (0.015, 0.30),
            (0.018, 0.305),
            (0.015, 0.31),
        ]
        bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((bv, bf))

        # Cork
        sv, sf = _make_cylinder(0, 0.305, 0, 0.013, 0.02, segments=6)
        parts.append((sv, sf))

    elif style == "skull_bottle":
        # Skull-shaped bottle body (sphere with indentations)
        skull_r = 0.08
        sv, sf = _make_sphere(0, skull_r + 0.01, 0, skull_r, rings=8, sectors=12)
        parts.append((sv, sf))

        # Eye sockets (small spheres that could be boolean'd)
        for xoff in [-skull_r * 0.35, skull_r * 0.35]:
            ev, ef = _make_sphere(xoff, skull_r * 1.15 + 0.01, skull_r * 0.6,
                                  skull_r * 0.2, rings=4, sectors=6)
            parts.append((ev, ef))

        # Jaw shelf
        jv, jf = _make_beveled_box(0, 0.01, skull_r * 0.3,
                                   skull_r * 0.5, skull_r * 0.15, skull_r * 0.2,
                                   bevel=skull_r * 0.05)
        parts.append((jv, jf))

        # Neck / spout
        nv, nf = _make_tapered_cylinder(0, skull_r * 2 + 0.01, 0,
                                        skull_r * 0.3, skull_r * 0.2,
                                        skull_r * 0.6, segments=8)
        parts.append((nv, nf))

    else:  # crystal_decanter
        profile = [
            (0.001, 0),
            (0.06, 0.005),
            (0.065, 0.01),
            (0.065, 0.04),
            (0.07, 0.06),
            (0.075, 0.10),
            (0.07, 0.14),
            (0.055, 0.17),
            (0.03, 0.19),
            (0.02, 0.22),
            (0.02, 0.28),
            (0.035, 0.30),
            (0.04, 0.31),
            (0.035, 0.32),
        ]
        bv, bf = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
        parts.append((bv, bf))

        # Crystal stopper (diamond shape)
        sv, sf = _make_cone(0, 0.32, 0, 0.025, 0.04, segments=8)
        parts.append((sv, sf))
        # Inverted cone below
        sv2, sf2 = _make_cone(0, 0.30, 0, 0.025, 0.02, segments=8)
        parts.append((sv2, sf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"PotionBottle_{style}", verts, faces,
                        style=style, category="container")


def generate_scroll_mesh(
    rolled: bool = True,
    length: float = 0.3,
) -> MeshSpec:
    """Generate a scroll/parchment mesh.

    Args:
        rolled: If True, generates a rolled scroll; if False, an unrolled sheet.
        length: Length of the scroll.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 12

    if rolled:
        # Main rolled tube
        scroll_r = length * 0.08
        sv, sf = _make_cylinder(0, 0, 0, scroll_r, length, segments=segs)
        # Rotate to lie horizontal: swap Y and Z
        sv = [(v[0], v[2], v[1]) for v in sv]
        parts.append((sv, sf))

        # End caps (ornamental knobs)
        for z_end in [0, length]:
            knob_r = scroll_r * 1.4
            kv, kf = _make_sphere(0, z_end, 0, knob_r, rings=4, sectors=8)
            # Swap Y/Z to match orientation
            kv = [(v[0], v[2], v[1]) for v in kv]
            parts.append((kv, kf))

        # Slight unroll at one end (curved sheet)
        unroll_pts = 8
        for i in range(unroll_pts):
            t = i / (unroll_pts - 1)
            angle = math.pi * 0.3 + t * math.pi * 0.8
            ux = math.cos(angle) * scroll_r * 1.5
            uy = math.sin(angle) * scroll_r * 1.5 - scroll_r
            cv, cf = _make_box(ux, 0, uy, 0.002, length * 0.9 * 0.48, scroll_r * 0.15)
            # Swap Y/Z
            cv = [(v[0], v[2], v[1]) for v in cv]
            parts.append((cv, cf))
    else:
        # Unrolled flat sheet with curled edges
        sheet_w = length * 0.8
        sheet_h = length
        sheet_t = 0.003

        # Main flat sheet
        sv, sf = _make_box(0, sheet_t / 2, 0, sheet_w / 2, sheet_t / 2, sheet_h / 2)
        parts.append((sv, sf))

        # Curled top edge
        curl_segs = 6
        curl_r = 0.015
        for i in range(curl_segs):
            t = i / curl_segs
            angle = t * math.pi * 0.8
            cy_pos = sheet_t + math.sin(angle) * curl_r
            cz_pos = sheet_h / 2 + math.cos(angle) * curl_r
            cv, cf = _make_box(0, cy_pos, cz_pos, sheet_w / 2, curl_r * 0.3, curl_r * 0.2)
            parts.append((cv, cf))

        # Curled bottom edge
        for i in range(curl_segs):
            t = i / curl_segs
            angle = t * math.pi * 0.6
            cy_pos = sheet_t + math.sin(angle) * curl_r
            cz_pos = -sheet_h / 2 - math.cos(angle) * curl_r
            cv, cf = _make_box(0, cy_pos, cz_pos, sheet_w / 2, curl_r * 0.3, curl_r * 0.2)
            parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Scroll", verts, faces, rolled=rolled, category="container")


# =========================================================================
# CATEGORY 11: LIGHT SOURCES
# =========================================================================


def generate_lantern_mesh(
    style: str = "iron_cage",
) -> MeshSpec:
    """Generate a lantern mesh.

    Args:
        style: "iron_cage", "paper_hanging", "crystal_embedded", or "skull_lantern".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 8

    if style == "iron_cage":
        h = 0.35
        r = 0.08
        # Top cap (cone)
        cv, cf = _make_cone(0, h * 0.75, 0, r * 1.2, h * 0.25, segments=segs)
        parts.append((cv, cf))
        # Bottom plate
        bv, bf = _make_cylinder(0, 0, 0, r * 1.1, h * 0.05, segments=segs)
        parts.append((bv, bf))
        # Vertical bars
        bar_count = segs
        bar_r = 0.005
        for i in range(bar_count):
            angle = 2.0 * math.pi * i / bar_count
            bx = math.cos(angle) * r
            bz = math.sin(angle) * r
            bv2, bf2 = _make_cylinder(bx, h * 0.05, bz, bar_r, h * 0.70, segments=4)
            parts.append((bv2, bf2))
        # Hanging ring at top
        tv, tf = _make_torus_ring(0, h + 0.02, 0, 0.025, 0.006,
                                  major_segments=8, minor_segments=4)
        parts.append((tv, tf))
        # Candle inside
        cv2, cf2 = _make_cylinder(0, h * 0.05, 0, 0.015, h * 0.3, segments=6)
        parts.append((cv2, cf2))

    elif style == "paper_hanging":
        h = 0.4
        r = 0.12
        # Paper shade (lathe profile - oval shape)
        profile = [
            (0.001, 0),
            (r * 0.5, h * 0.05),
            (r * 0.9, h * 0.20),
            (r, h * 0.40),
            (r * 0.95, h * 0.60),
            (r * 0.7, h * 0.80),
            (r * 0.3, h * 0.92),
            (0.001, h),
        ]
        sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((sv, sf))
        # Wire frame rings
        for t in [0.2, 0.5, 0.8]:
            ring_y = h * t
            ring_r = r * (0.9 if t == 0.5 else 0.7)
            tv2, tf2 = _make_torus_ring(0, ring_y, 0, ring_r, 0.003,
                                        major_segments=segs, minor_segments=3)
            parts.append((tv2, tf2))
        # Hanging cord
        cv2, cf2 = _make_cylinder(0, h, 0, 0.004, 0.15, segments=4)
        parts.append((cv2, cf2))

    elif style == "crystal_embedded":
        h = 0.3
        # Stone base
        base_profile = [
            (0.06, 0),
            (0.07, 0.02),
            (0.065, 0.05),
            (0.05, 0.08),
            (0.03, 0.10),
        ]
        bv, bf = _make_lathe(base_profile, segments=8, close_bottom=True, close_top=True)
        parts.append((bv, bf))
        # Central crystal (hexagonal prism)
        cv, cf = _make_tapered_cylinder(0, 0.06, 0, 0.03, 0.01, h * 0.7,
                                        segments=6)
        parts.append((cv, cf))
        # Smaller crystals around base
        for i in range(4):
            angle = 2.0 * math.pi * i / 4 + 0.3
            cx = math.cos(angle) * 0.04
            cz = math.sin(angle) * 0.04
            sv, sf = _make_tapered_cylinder(cx, 0.05, cz, 0.015, 0.005,
                                            h * 0.4, segments=6)
            parts.append((sv, sf))

    else:  # skull_lantern
        h = 0.3
        # Skull body
        skull_r = 0.07
        sv, sf = _make_sphere(0, skull_r + 0.02, 0, skull_r, rings=6, sectors=8)
        parts.append((sv, sf))
        # Eye sockets
        for xoff in [-skull_r * 0.35, skull_r * 0.35]:
            ev, ef = _make_sphere(xoff, skull_r * 1.2 + 0.02, skull_r * 0.65,
                                  skull_r * 0.22, rings=3, sectors=4)
            parts.append((ev, ef))
        # Jaw
        jv, jf = _make_beveled_box(0, 0.02, skull_r * 0.4,
                                   skull_r * 0.55, skull_r * 0.2, skull_r * 0.2,
                                   bevel=skull_r * 0.05)
        parts.append((jv, jf))
        # Chain attachment at top
        tv, tf = _make_torus_ring(0, skull_r * 2 + 0.04, 0, 0.02, 0.005,
                                  major_segments=8, minor_segments=4)
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Lantern_{style}", verts, faces,
                        style=style, category="light_source")


def generate_brazier_mesh(
    style: str = "iron_standing",
    size: float = 0.5,
) -> MeshSpec:
    """Generate a brazier mesh.

    Args:
        style: "iron_standing", "stone_bowl", or "hanging_chain".
        size: Overall size scale.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 12

    if style == "iron_standing":
        # Bowl
        bowl_profile = [
            (size * 0.25, size * 0.5),
            (size * 0.30, size * 0.52),
            (size * 0.35, size * 0.56),
            (size * 0.38, size * 0.62),
            (size * 0.36, size * 0.70),
            (size * 0.30, size * 0.74),
        ]
        bv, bf = _make_lathe(bowl_profile, segments=segs, close_bottom=True)
        parts.append((bv, bf))

        # Rim ring
        tv, tf = _make_torus_ring(0, size * 0.74, 0, size * 0.30, size * 0.015,
                                  major_segments=segs, minor_segments=4)
        parts.append((tv, tf))

        # Three legs
        for i in range(3):
            angle = 2.0 * math.pi * i / 3
            lx = math.cos(angle) * size * 0.22
            lz = math.sin(angle) * size * 0.22
            lv, lf = _make_tapered_cylinder(lx, 0, lz, size * 0.03, size * 0.02,
                                            size * 0.5, segments=6)
            parts.append((lv, lf))
            # Foot pad
            fv, ff = _make_cylinder(lx, 0, lz, size * 0.04, size * 0.02, segments=6)
            parts.append((fv, ff))

    elif style == "stone_bowl":
        # Heavy stone bowl on pedestal
        bowl_profile = [
            (size * 0.10, 0),
            (size * 0.15, size * 0.05),
            (size * 0.12, size * 0.15),
            (size * 0.14, size * 0.25),
            (size * 0.20, size * 0.35),
            (size * 0.30, size * 0.42),
            (size * 0.38, size * 0.50),
            (size * 0.40, size * 0.55),
            (size * 0.38, size * 0.60),
        ]
        bv, bf = _make_lathe(bowl_profile, segments=segs,
                             close_bottom=True, close_top=False)
        parts.append((bv, bf))

        # Inner bowl cavity
        inner_profile = [
            (size * 0.32, size * 0.60),
            (size * 0.30, size * 0.55),
            (size * 0.25, size * 0.50),
            (size * 0.15, size * 0.47),
            (0.001, size * 0.45),
        ]
        iv, i_f = _make_lathe(inner_profile, segments=segs, close_top=True)
        parts.append((iv, i_f))

    else:  # hanging_chain
        # Bowl
        bowl_profile = [
            (0.001, size * 0.3),
            (size * 0.15, size * 0.32),
            (size * 0.25, size * 0.38),
            (size * 0.30, size * 0.45),
            (size * 0.28, size * 0.50),
        ]
        bv, bf = _make_lathe(bowl_profile, segments=segs, close_top=False)
        parts.append((bv, bf))

        # Rim
        tv, tf = _make_torus_ring(0, size * 0.50, 0, size * 0.28, size * 0.012,
                                  major_segments=segs, minor_segments=4)
        parts.append((tv, tf))

        # Three chains going up (represented as cylinder segments)
        chain_h = size * 0.6
        for i in range(3):
            angle = 2.0 * math.pi * i / 3
            cx = math.cos(angle) * size * 0.25
            cz = math.sin(angle) * size * 0.25
            cv, cf = _make_cylinder(cx, size * 0.50, cz, size * 0.008,
                                    chain_h, segments=4)
            parts.append((cv, cf))

        # Top ring where chains meet
        tv2, tf2 = _make_torus_ring(0, size * 0.50 + chain_h, 0, size * 0.04,
                                    size * 0.008, major_segments=8, minor_segments=4)
        parts.append((tv2, tf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Brazier_{style}", verts, faces,
                        style=style, category="light_source")


def generate_campfire_mesh(
    log_count: int = 4,
) -> MeshSpec:
    """Generate a campfire mesh with logs and stone ring.

    Args:
        log_count: Number of logs in the fire (2-8).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    log_count = max(2, min(8, log_count))
    parts = []

    # Stone ring
    ring_r = 0.3
    stone_count = 12
    stone_r = 0.06
    for i in range(stone_count):
        angle = 2.0 * math.pi * i / stone_count
        sx = math.cos(angle) * ring_r
        sz = math.sin(angle) * ring_r
        # Slightly irregular stones (beveled boxes)
        variation = 0.8 + (i % 3) * 0.15
        sv, sf = _make_beveled_box(
            sx, stone_r * variation, sz,
            stone_r * variation, stone_r * variation, stone_r * 0.8,
            bevel=stone_r * 0.15,
        )
        parts.append((sv, sf))

    # Logs arranged in a rough teepee pattern
    log_r = 0.03
    log_len = 0.35
    for i in range(log_count):
        angle = 2.0 * math.pi * i / log_count + 0.2
        # Logs tilt inward
        mid_x = math.cos(angle) * log_len * 0.2
        mid_z = math.sin(angle) * log_len * 0.2
        lv, lf = _make_tapered_cylinder(
            mid_x, stone_r * 0.3, mid_z,
            log_r * 1.1, log_r * 0.8,
            log_len * 0.6, segments=6, rings=2,
        )
        parts.append((lv, lf))

    # Central ash pile
    ash_profile = [
        (0.001, 0),
        (0.12, 0.005),
        (0.15, 0.015),
        (0.10, 0.025),
        (0.001, 0.03),
    ]
    av, af = _make_lathe(ash_profile, segments=8, close_bottom=True, close_top=True)
    parts.append((av, af))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Campfire", verts, faces,
                        log_count=log_count, category="light_source")


def generate_crystal_light_mesh(
    cluster_count: int = 5,
    size: float = 0.3,
) -> MeshSpec:
    """Generate a glowing crystal cluster for lighting.

    Args:
        cluster_count: Number of crystal shards (2-12).
        size: Overall cluster size.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(77)
    cluster_count = max(2, min(12, cluster_count))
    parts = []

    # Base rock
    base_r = size * 0.3
    bv, bf = _make_sphere(0, 0, 0, base_r, rings=4, sectors=6)
    # Flatten bottom half
    bv = [(v[0], max(v[1], -base_r * 0.2), v[2]) for v in bv]
    parts.append((bv, bf))

    # Crystal shards (hexagonal prisms tapering to points)
    for _ in range(cluster_count):
        cx = rng.uniform(-size * 0.15, size * 0.15)
        cz = rng.uniform(-size * 0.15, size * 0.15)
        cy = rng.uniform(0, size * 0.1)
        c_height = rng.uniform(size * 0.3, size * 0.8)
        c_radius = rng.uniform(size * 0.04, size * 0.08)
        cv, cf = _make_tapered_cylinder(
            cx, cy, cz,
            c_radius, c_radius * 0.05,
            c_height, segments=6,
            cap_top=True, cap_bottom=True,
        )
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("CrystalLight", verts, faces,
                        cluster_count=cluster_count, category="light_source")


def generate_magic_orb_light_mesh(
    radius: float = 0.1,
    cage: bool = True,
) -> MeshSpec:
    """Generate a floating magic orb light with optional metal cage.

    Args:
        radius: Orb radius.
        cage: Whether to surround with a decorative cage.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Central glowing orb
    ov, of = _make_sphere(0, 0, 0, radius, rings=8, sectors=12)
    parts.append((ov, of))

    if cage:
        # Cage bands (3 orthogonal rings)
        cage_r = radius * 1.3
        band_r = radius * 0.04
        # Equatorial ring (XZ plane)
        tv, tf = _make_torus_ring(0, 0, 0, cage_r, band_r,
                                  major_segments=16, minor_segments=4)
        parts.append((tv, tf))

        # Meridian ring (XY plane) - rotate by swapping Y and Z
        tv2, tf2 = _make_torus_ring(0, 0, 0, cage_r, band_r,
                                    major_segments=16, minor_segments=4)
        tv2 = [(v[0], v[2], v[1]) for v in tv2]
        parts.append((tv2, tf2))

        # Another meridian at 90 degrees (YZ plane) - swap X and Z
        tv3, tf3 = _make_torus_ring(0, 0, 0, cage_r, band_r,
                                    major_segments=16, minor_segments=4)
        tv3 = [(v[2], v[1], v[0]) for v in tv3]
        parts.append((tv3, tf3))

        # Top mounting point
        mv, mf = _make_cone(0, cage_r, 0, radius * 0.15, radius * 0.2, segments=6)
        parts.append((mv, mf))

        # Hanging chain hook
        hv, hf = _make_torus_ring(0, cage_r + radius * 0.25, 0,
                                  radius * 0.1, radius * 0.03,
                                  major_segments=8, minor_segments=4)
        parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("MagicOrbLight", verts, faces,
                        cage=cage, category="light_source")


# =========================================================================
# CATEGORY 12: DOORS & WINDOWS
# =========================================================================


def generate_door_mesh(
    style: str = "wooden_plank",
    width: float = 1.0,
    height: float = 2.2,
) -> MeshSpec:
    """Generate a door mesh.

    Args:
        style: "wooden_plank", "iron_reinforced", "stone_carved",
               "hidden_bookcase", or "dungeon_gate".
        width: Door width.
        height: Door height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    depth = 0.08
    bevel = 0.005

    if style == "wooden_plank":
        # Main door panel
        dv, df = _make_beveled_box(0, height / 2, 0, width / 2, height / 2,
                                   depth / 2, bevel=bevel)
        parts.append((dv, df))

        # Plank lines (horizontal strips)
        plank_count = 4
        for i in range(plank_count + 1):
            t = i / plank_count
            line_y = t * height
            lv, lf = _make_box(0, line_y, depth / 2 + 0.002,
                               width / 2, 0.005, 0.002)
            parts.append((lv, lf))

        # Hinges
        for hy in [height * 0.2, height * 0.8]:
            hv, hf = _make_cylinder(-width / 2 - 0.01, hy - 0.03, depth / 2,
                                    0.012, 0.06, segments=6)
            parts.append((hv, hf))

        # Handle
        hv2, hf2 = _make_torus_ring(width * 0.3, height * 0.5, depth / 2 + 0.02,
                                    0.03, 0.006, major_segments=8, minor_segments=4)
        parts.append((hv2, hf2))

    elif style == "iron_reinforced":
        # Thick door panel
        dv, df = _make_beveled_box(0, height / 2, 0, width / 2, height / 2,
                                   depth / 2, bevel=bevel)
        parts.append((dv, df))

        # Iron bands (horizontal)
        band_count = 5
        for i in range(band_count):
            t = (i + 0.5) / band_count
            by = t * height
            bv2, bf2 = _make_box(0, by, depth / 2 + 0.003,
                                 width / 2 + 0.005, 0.02, 0.003)
            parts.append((bv2, bf2))

        # Corner studs (rivets)
        stud_r = 0.008
        for sx in [-width * 0.4, -width * 0.15, width * 0.15, width * 0.4]:
            for sy_t in [0.15, 0.35, 0.55, 0.75, 0.95]:
                sv, sf = _make_sphere(sx, height * sy_t, depth / 2 + 0.005,
                                      stud_r, rings=3, sectors=4)
                parts.append((sv, sf))

        # Heavy iron handle
        hv, hf = _make_torus_ring(width * 0.3, height * 0.5, depth / 2 + 0.03,
                                  0.04, 0.008, major_segments=8, minor_segments=4)
        parts.append((hv, hf))

    elif style == "stone_carved":
        # Stone door slab
        dv, df = _make_beveled_box(0, height / 2, 0, width / 2, height / 2,
                                   depth, bevel=0.01)
        parts.append((dv, df))

        # Arched top carving (decorative arc)
        arch_segs = 10
        arch_r = width * 0.35
        for i in range(arch_segs):
            t = i / (arch_segs - 1)
            angle = math.pi * t
            ax = math.cos(angle) * arch_r
            ay = height * 0.7 + math.sin(angle) * arch_r * 0.5
            sv, sf = _make_box(ax, ay, depth + 0.005, 0.015, 0.015, 0.008)
            parts.append((sv, sf))

        # Central carved symbol (circle)
        tv, tf = _make_torus_ring(0, height * 0.5, depth + 0.008,
                                  width * 0.15, 0.01,
                                  major_segments=12, minor_segments=3)
        parts.append((tv, tf))

    elif style == "hidden_bookcase":
        # Bookcase frame
        shelf_w = width
        shelf_h = height
        shelf_d = 0.25
        frame_t = 0.03

        # Back panel
        bv2, bf2 = _make_beveled_box(0, shelf_h / 2, -shelf_d / 2 + frame_t / 2,
                                     shelf_w / 2, shelf_h / 2, frame_t / 2, bevel=0.003)
        parts.append((bv2, bf2))

        # Side panels
        for xoff in [-shelf_w / 2, shelf_w / 2]:
            sv, sf = _make_beveled_box(xoff, shelf_h / 2, 0,
                                       frame_t / 2, shelf_h / 2, shelf_d / 2, bevel=0.003)
            parts.append((sv, sf))

        # Shelves
        shelf_count = 5
        for i in range(shelf_count + 1):
            sy = i * shelf_h / shelf_count
            sv2, sf2 = _make_box(0, sy, 0, shelf_w / 2, frame_t / 2, shelf_d / 2)
            parts.append((sv2, sf2))

        # Books on shelves (thin boxes)
        import random as _rng
        rng = _rng.Random(88)
        for shelf_i in range(shelf_count):
            base_y = shelf_i * shelf_h / shelf_count + frame_t
            book_x = -shelf_w / 2 + frame_t + 0.02
            while book_x < shelf_w / 2 - frame_t - 0.02:
                bw = rng.uniform(0.02, 0.04)
                bh = rng.uniform(shelf_h / shelf_count * 0.5, shelf_h / shelf_count * 0.85)
                bkv, bkf = _make_box(book_x + bw / 2, base_y + bh / 2, 0,
                                     bw / 2, bh / 2, shelf_d * 0.35)
                parts.append((bkv, bkf))
                book_x += bw + rng.uniform(0.002, 0.008)

    else:  # dungeon_gate
        # Portcullis-style gate
        bar_r = 0.015
        bar_spacing = width / 8

        # Vertical bars
        x = -width / 2 + bar_spacing
        while x < width / 2:
            bv2, bf2 = _make_cylinder(x, 0, 0, bar_r, height, segments=6)
            parts.append((bv2, bf2))
            x += bar_spacing

        # Horizontal cross bars
        cross_count = 4
        for i in range(cross_count):
            cy = (i + 1) * height / (cross_count + 1)
            cv2, cf2 = _make_box(0, cy, 0, width / 2, bar_r, bar_r)
            parts.append((cv2, cf2))

        # Bottom spikes
        spike_x = -width / 2 + bar_spacing
        while spike_x < width / 2:
            sv, sf = _make_cone(spike_x, -0.01, 0, bar_r * 1.5, 0.05, segments=6)
            # Invert cone to point down
            sv = [(v[0], -v[1], v[2]) for v in sv]
            parts.append((sv, sf))
            spike_x += bar_spacing

        # Top frame
        fv, ff = _make_box(0, height + bar_r, 0, width / 2 + bar_r * 2,
                           bar_r * 2, bar_r * 2)
        parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Door_{style}", verts, faces,
                        style=style, category="door")


def generate_window_mesh(
    style: str = "arched_gothic",
    width: float = 0.6,
    height: float = 1.0,
) -> MeshSpec:
    """Generate a window frame mesh.

    Args:
        style: "arched_gothic", "circular_rose", "arrow_slit", or "stained_frame".
        width: Window width.
        height: Window height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    frame_t = 0.04  # frame thickness
    frame_d = 0.06  # frame depth

    if style == "arched_gothic":
        # Rectangular bottom section frame
        rect_h = height * 0.6
        # Left post
        lv, lf = _make_beveled_box(-width / 2, rect_h / 2, 0,
                                   frame_t / 2, rect_h / 2, frame_d / 2, bevel=0.003)
        parts.append((lv, lf))
        # Right post
        rv, rf = _make_beveled_box(width / 2, rect_h / 2, 0,
                                   frame_t / 2, rect_h / 2, frame_d / 2, bevel=0.003)
        parts.append((rv, rf))
        # Bottom sill
        sv, sf = _make_beveled_box(0, -frame_t / 2, 0,
                                   width / 2 + frame_t, frame_t / 2, frame_d / 2 + 0.01,
                                   bevel=0.003)
        parts.append((sv, sf))

        # Gothic arch at top
        arch_segs = 12
        arch_base_y = rect_h
        arch_h = height - rect_h
        for i in range(arch_segs + 1):
            t = i / arch_segs
            angle = math.pi * t
            ax = math.cos(angle) * (width / 2)
            ay = arch_base_y + math.sin(angle) * arch_h
            sv2, sf2 = _make_sphere(ax, ay, 0, frame_t / 2, rings=3, sectors=4)
            parts.append((sv2, sf2))

        # Central mullion (vertical divider)
        mv, mf = _make_box(0, rect_h / 2, 0, frame_t / 4, rect_h / 2, frame_d / 2)
        parts.append((mv, mf))

    elif style == "circular_rose":
        # Circular frame
        tv, tf = _make_torus_ring(0, 0, 0, width / 2, frame_t,
                                  major_segments=24, minor_segments=6)
        parts.append((tv, tf))

        # Radiating spokes (mullions)
        spoke_count = 8
        for i in range(spoke_count):
            angle = 2.0 * math.pi * i / spoke_count
            sx = math.cos(angle) * width * 0.2
            sy = math.sin(angle) * width * 0.2
            ex = math.cos(angle) * width * 0.45
            ey = math.sin(angle) * width * 0.45
            mx = (sx + ex) / 2
            my = (sy + ey) / 2
            spoke_len = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
            sv2, sf2 = _make_box(mx, my, 0, frame_t / 4, spoke_len / 2, frame_d / 2)
            parts.append((sv2, sf2))

        # Inner ring
        tv2, tf2 = _make_torus_ring(0, 0, 0, width * 0.2, frame_t * 0.6,
                                    major_segments=16, minor_segments=4)
        parts.append((tv2, tf2))

    elif style == "arrow_slit":
        # Narrow vertical opening
        slit_w = width * 0.15
        # Outer frame (thick stone)
        ov, of = _make_beveled_box(0, height / 2, 0,
                                   width / 2, height / 2, frame_d,
                                   bevel=0.008)
        parts.append((ov, of))

        # Inner cutout represented by inset frame pieces
        # Top horizontal
        tv2, tf2 = _make_box(0, height - frame_t, 0, slit_w, frame_t, frame_d * 0.8)
        parts.append((tv2, tf2))
        # Bottom horizontal
        bv2, bf2 = _make_box(0, frame_t, 0, slit_w, frame_t, frame_d * 0.8)
        parts.append((bv2, bf2))
        # Cross slit (horizontal expansion at center)
        cv, cf = _make_box(0, height / 2, 0, width * 0.3, frame_t / 2, frame_d * 0.5)
        parts.append((cv, cf))

    else:  # stained_frame
        # Rectangular frame with decorative divisions
        for side in [
            (-width / 2, height / 2, frame_t / 2, height / 2),  # left
            (width / 2, height / 2, frame_t / 2, height / 2),   # right
            (0, 0, width / 2, frame_t / 2),                      # bottom
            (0, height, width / 2, frame_t / 2),                 # top
        ]:
            fv, ff = _make_beveled_box(side[0], side[1], 0,
                                       side[2], side[3], frame_d / 2, bevel=0.003)
            parts.append((fv, ff))

        # Cross dividers
        hv, hf = _make_box(0, height * 0.5, 0, width / 2, frame_t / 3, frame_d / 2)
        parts.append((hv, hf))
        vv, vf = _make_box(0, height / 2, 0, frame_t / 3, height / 2, frame_d / 2)
        parts.append((vv, vf))

        # Decorative top arc
        arc_segs = 8
        for i in range(arc_segs + 1):
            t = i / arc_segs
            angle = math.pi * t
            ax = math.cos(angle) * width * 0.3
            ay = height + math.sin(angle) * height * 0.15
            sv2, sf2 = _make_sphere(ax, ay, 0, frame_t * 0.4, rings=3, sectors=4)
            parts.append((sv2, sf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Window_{style}", verts, faces,
                        style=style, category="door")


def generate_trapdoor_mesh(
    size: float = 0.8,
    style: str = "wooden",
) -> MeshSpec:
    """Generate a floor trapdoor mesh.

    Args:
        size: Trapdoor size (square dimensions).
        style: "wooden" or "iron".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    hs = size / 2
    thickness = 0.04

    if style == "iron":
        # Iron plate
        dv, df = _make_beveled_box(0, thickness / 2, 0, hs, thickness / 2, hs,
                                   bevel=0.008)
        parts.append((dv, df))

        # Rivets around the edge
        rivet_r = 0.008
        rivet_count = 6
        for i in range(rivet_count):
            t = (i + 0.5) / rivet_count
            # Four edges
            for edge_x, edge_z in [
                (-hs + t * size, -hs + 0.02),
                (-hs + t * size, hs - 0.02),
                (-hs + 0.02, -hs + t * size),
                (hs - 0.02, -hs + t * size),
            ]:
                rv, rf = _make_sphere(edge_x, thickness + rivet_r * 0.5, edge_z,
                                      rivet_r, rings=3, sectors=4)
                parts.append((rv, rf))

        # Heavy ring handle
        tv, tf = _make_torus_ring(0, thickness + 0.015, 0, 0.04, 0.008,
                                  major_segments=8, minor_segments=4)
        # Rotate ring to stand upright
        tv = [(v[0], thickness + abs(v[2]) * 2, v[1]) for v in tv]
        parts.append((tv, tf))

    else:  # wooden
        # Wooden plank door
        dv, df = _make_beveled_box(0, thickness / 2, 0, hs, thickness / 2, hs,
                                   bevel=0.005)
        parts.append((dv, df))

        # Plank groove lines
        plank_count = 4
        for i in range(plank_count + 1):
            t = i / plank_count
            lx = -hs + t * size
            lv, lf = _make_box(lx, thickness + 0.001, 0, 0.003, 0.001, hs)
            parts.append((lv, lf))

        # Cross braces (underneath)
        for bz in [-hs * 0.5, hs * 0.5]:
            bv2, bf2 = _make_box(0, -0.01, bz, hs * 0.9, 0.008, 0.02)
            parts.append((bv2, bf2))

        # Iron hinge
        hv, hf = _make_cylinder(-hs, -0.005, 0, 0.012, size * 0.3, segments=6)
        parts.append((hv, hf))

        # Ring handle
        tv, tf = _make_torus_ring(0, thickness + 0.01, 0, 0.03, 0.005,
                                  major_segments=8, minor_segments=4)
        tv = [(v[0], thickness + abs(v[2]) * 1.5, v[1]) for v in tv]
        parts.append((tv, tf))

    # Floor frame surround
    frame_w = 0.04
    for side in [
        (-hs - frame_w / 2, 0, frame_w / 2, hs + frame_w),
        (hs + frame_w / 2, 0, frame_w / 2, hs + frame_w),
        (0, 0, hs + frame_w, frame_w / 2),
    ]:
        fv, ff = _make_box(side[0], thickness / 2, side[1],
                           side[2], thickness / 2, side[3])
        parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Trapdoor_{style}", verts, faces,
                        style=style, category="door")


# =========================================================================
# CATEGORY 13: WALL & FLOOR DECORATIONS
# =========================================================================


def generate_banner_mesh(
    width: float = 0.5,
    length: float = 1.2,
    style: str = "pointed",
) -> MeshSpec:
    """Generate a hanging banner/tapestry mesh with drape.

    Args:
        width: Banner width.
        length: Banner length (hanging down).
        style: "pointed" (V-bottom), "straight", or "swallowtail".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Hanging rod (box approximation)
    rod_r = 0.012
    rv2, rf2 = _make_box(0, 0, 0, width / 2 + 0.02, rod_r, rod_r)
    parts.append((rv2, rf2))

    # Rod end finials
    for xend in [-width / 2 - 0.02, width / 2 + 0.02]:
        fv, ff = _make_sphere(xend, 0, 0, rod_r * 1.8, rings=4, sectors=6)
        parts.append((fv, ff))

    # Banner fabric (quad grid with drape curve)
    cols = 8
    rows = 12
    fabric_verts: list[tuple[float, float, float]] = []
    fabric_faces: list[tuple[int, ...]] = []

    for r in range(rows + 1):
        t = r / rows
        y = -t * length
        # Slight wave/drape in Z
        drape_z = math.sin(t * math.pi) * 0.03
        for c in range(cols + 1):
            s = c / cols
            x = -width / 2 + s * width
            # Subtle wave across width
            z = drape_z + math.sin(s * math.pi * 2 + t * 3) * 0.008
            fabric_verts.append((x, y, z))

    for r in range(rows):
        for c in range(cols):
            i0 = r * (cols + 1) + c
            i1 = i0 + 1
            i2 = i0 + (cols + 1) + 1
            i3 = i0 + (cols + 1)
            fabric_faces.append((i0, i1, i2, i3))

    parts.append((fabric_verts, fabric_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Banner_{style}", verts, faces,
                        style=style, category="wall_decor")


def generate_wall_shield_mesh(
    style: str = "kite",
) -> MeshSpec:
    """Generate a decorative wall-mounted shield mesh.

    Args:
        style: "kite", "round", "heater", or "tower".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "round":
        # Circular shield with boss
        shield_r = 0.3
        profile = [
            (0.001, -0.02),
            (shield_r * 0.3, -0.018),
            (shield_r * 0.6, -0.012),
            (shield_r * 0.85, -0.005),
            (shield_r, 0),
            (shield_r * 0.98, 0.015),
            (shield_r * 0.85, 0.02),
            (shield_r * 0.6, 0.022),
            (shield_r * 0.3, 0.023),
            (0.001, 0.024),
        ]
        sv, sf = _make_lathe(profile, segments=16, close_bottom=True, close_top=True)
        parts.append((sv, sf))

        # Central boss
        boss_profile = [
            (0.001, 0.024),
            (0.04, 0.028),
            (0.06, 0.035),
            (0.05, 0.05),
            (0.02, 0.06),
            (0.001, 0.062),
        ]
        bv, bf = _make_lathe(boss_profile, segments=8, close_top=True)
        parts.append((bv, bf))

        # Rim ring
        tv, tf = _make_torus_ring(0, 0, 0, shield_r, 0.012,
                                  major_segments=16, minor_segments=4)
        parts.append((tv, tf))

    elif style == "kite":
        # Kite shield (pointed bottom)
        hw = 0.22
        top_h = 0.15
        bot_h = 0.45
        d = 0.025
        bv, bf = _make_beveled_box(0, top_h / 2, 0, hw, top_h / 2, d, bevel=0.005)
        parts.append((bv, bf))
        # Tapered lower section
        tv, tf = _make_tapered_cylinder(0, -bot_h, 0, hw * 0.08, hw, bot_h,
                                        segments=8, cap_top=False, cap_bottom=True)
        parts.append((tv, tf))

        # Central ridge
        rv, rf = _make_box(0, -bot_h / 2 + top_h / 2, d + 0.005,
                           0.008, (top_h + bot_h) / 2, 0.008)
        parts.append((rv, rf))

    elif style == "heater":
        # Heater shield (rounded top, pointed bottom)
        hw = 0.2
        h = 0.5
        d = 0.025
        bv, bf = _make_beveled_box(0, h * 0.65, 0, hw, h * 0.35, d, bevel=0.005)
        parts.append((bv, bf))
        tv, tf = _make_tapered_cylinder(0, 0, 0, hw * 0.15, hw, h * 0.3,
                                        segments=8, cap_bottom=True, cap_top=False)
        parts.append((tv, tf))

        # Rim detail
        rv, rf = _make_box(0, h * 0.5, d + 0.003, hw + 0.005, h * 0.5, 0.003)
        parts.append((rv, rf))

    else:  # tower
        hw = 0.25
        hh = 0.5
        d = 0.03
        bv, bf = _make_beveled_box(0, 0, 0, hw, hh, d, bevel=0.008)
        parts.append((bv, bf))

        rv, rf = _make_box(0, 0, d + 0.003, hw + 0.005, hh + 0.005, 0.003)
        parts.append((rv, rf))

        sv, sf = _make_sphere(0, 0, d + 0.02, 0.04, rings=4, sectors=6)
        parts.append((sv, sf))

    # Wall mount bracket (behind shield)
    mv, mf = _make_box(0, 0, -0.03, 0.03, 0.03, 0.02)
    parts.append((mv, mf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"WallShield_{style}", verts, faces,
                        style=style, category="wall_decor")


def generate_mounted_head_mesh(
    creature: str = "deer",
) -> MeshSpec:
    """Generate a mounted trophy head mesh.

    Args:
        creature: "deer", "boar", "dragon", or "demon".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    # Wall plaque (shield-shaped mount)
    plaque_profile = [
        (0.001, -0.15),
        (0.12, -0.14),
        (0.18, -0.10),
        (0.20, 0),
        (0.18, 0.10),
        (0.12, 0.14),
        (0.001, 0.15),
    ]
    pv, pf = _make_lathe(plaque_profile, segments=12, close_bottom=True, close_top=True)
    # Flatten to be wall-mounted (thin disc)
    pv = [(v[0], v[1], v[2] * 0.3 - 0.04) for v in pv]
    parts.append((pv, pf))

    if creature == "deer":
        # Head (elongated sphere)
        hv, hf = _make_sphere(0, 0.05, 0.08, 0.08, rings=6, sectors=8)
        hv = [(v[0], v[1], v[2] * 1.3) for v in hv]
        parts.append((hv, hf))
        # Snout
        sv, sf = _make_tapered_cylinder(0, -0.02, 0.18, 0.04, 0.03, 0.08,
                                        segments=6, cap_top=True)
        sv = [(v[0], v[2] - 0.08, v[1] + 0.02) for v in sv]
        parts.append((sv, sf))
        # Antlers (branching cones)
        for xsign in [-1, 1]:
            for i in range(5):
                t = i / 4
                ax = xsign * (0.05 + t * 0.15)
                ay = 0.12 + t * 0.20
                az = 0.05 - t * 0.02
                av, af = _make_sphere(ax, ay, az, 0.012 * (1.0 - t * 0.5),
                                      rings=3, sectors=4)
                parts.append((av, af))
            for ti in range(2):
                bt = (ti + 1) / 3
                bx = xsign * (0.05 + bt * 0.15 + 0.05)
                by = 0.12 + bt * 0.20 + 0.08
                av2, af2 = _make_cone(bx, by, 0.03, 0.008, 0.06, segments=4)
                parts.append((av2, af2))

    elif creature == "boar":
        hv, hf = _make_sphere(0, 0, 0.10, 0.10, rings=6, sectors=8)
        hv = [(v[0] * 1.2, v[1], v[2] * 1.1) for v in hv]
        parts.append((hv, hf))
        sv, sf = _make_cylinder(0, -0.05, 0.18, 0.05, 0.06, segments=8)
        sv = [(v[0], v[2] - 0.03, v[1] + 0.05) for v in sv]
        parts.append((sv, sf))
        for xsign in [-1, 1]:
            tv, tf = _make_cone(xsign * 0.05, -0.06, 0.20, 0.01, 0.08, segments=4)
            tv = [(v[0], v[1] - 0.02, v[2]) for v in tv]
            parts.append((tv, tf))

    elif creature == "dragon":
        hv, hf = _make_sphere(0, 0.05, 0.12, 0.12, rings=6, sectors=8)
        hv = [(v[0], v[1], v[2] * 1.5) for v in hv]
        parts.append((hv, hf))
        jv, jf = _make_tapered_cylinder(0, -0.04, 0.25, 0.06, 0.04, 0.12,
                                        segments=6, cap_top=True)
        jv = [(v[0], v[2] - 0.06, v[1] + 0.04) for v in jv]
        parts.append((jv, jf))
        for xsign in [-1, 1]:
            cv, cf = _make_cone(xsign * 0.08, 0.15, 0.05, 0.02, 0.15, segments=6)
            parts.append((cv, cf))
        for i in range(4):
            t = i / 3
            sz = 0.05 + t * 0.15
            sv2, sf2 = _make_cone(0, 0.14 - t * 0.02, sz, 0.01, 0.04, segments=4)
            parts.append((sv2, sf2))

    else:  # demon
        hv, hf = _make_sphere(0, 0.05, 0.10, 0.11, rings=6, sectors=8)
        parts.append((hv, hf))
        for xsign in [-1, 1]:
            for i in range(6):
                t = i / 5
                ax = xsign * (0.08 + t * 0.10)
                ay = 0.12 + math.sin(t * math.pi * 0.8) * 0.15
                az = 0.08 - t * 0.05
                r = 0.015 * (1.0 - t * 0.4)
                sv2, sf2 = _make_sphere(ax, ay, az, r, rings=3, sectors=4)
                parts.append((sv2, sf2))
        for xsign in [-1, 1]:
            ev, ef = _make_cone(xsign * 0.12, 0.08, 0.08, 0.02, 0.06, segments=4)
            parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MountedHead_{creature}", verts, faces,
                        creature=creature, category="wall_decor")


def generate_painting_frame_mesh(
    width: float = 0.5,
    height: float = 0.7,
    frame_style: str = "ornate",
) -> MeshSpec:
    """Generate an ornate picture frame mesh.

    Args:
        width: Frame outer width.
        height: Frame outer height.
        frame_style: "ornate", "simple", or "gothic".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    frame_w = 0.04 if frame_style == "simple" else 0.06
    frame_d = 0.03
    inner_w = width - frame_w * 2
    inner_h = height - frame_w * 2
    bevel_size = 0.003 if frame_style == "simple" else 0.005

    # Four frame sides
    tv, tf = _make_beveled_box(0, height / 2 - frame_w / 2, 0,
                               width / 2, frame_w / 2, frame_d / 2, bevel=bevel_size)
    parts.append((tv, tf))
    bv, bf = _make_beveled_box(0, -height / 2 + frame_w / 2, 0,
                               width / 2, frame_w / 2, frame_d / 2, bevel=bevel_size)
    parts.append((bv, bf))
    lv, lf = _make_beveled_box(-width / 2 + frame_w / 2, 0, 0,
                               frame_w / 2, height / 2 - frame_w, frame_d / 2,
                               bevel=bevel_size)
    parts.append((lv, lf))
    rv, rf = _make_beveled_box(width / 2 - frame_w / 2, 0, 0,
                               frame_w / 2, height / 2 - frame_w, frame_d / 2,
                               bevel=bevel_size)
    parts.append((rv, rf))

    # Canvas/painting surface (thin plane)
    cv, cf = _make_box(0, 0, -frame_d / 2 + 0.002,
                       inner_w / 2, inner_h / 2, 0.002)
    parts.append((cv, cf))

    if frame_style == "ornate":
        for xo in [-width / 2, width / 2]:
            for yo in [-height / 2, height / 2]:
                sv, sf = _make_sphere(xo, yo, frame_d / 2,
                                      frame_w * 0.4, rings=4, sectors=6)
                parts.append((sv, sf))
        for pos in [(0, height / 2), (0, -height / 2),
                    (-width / 2, 0), (width / 2, 0)]:
            sv2, sf2 = _make_sphere(pos[0], pos[1], frame_d / 2,
                                    frame_w * 0.3, rings=3, sectors=5)
            parts.append((sv2, sf2))

    elif frame_style == "gothic":
        arch_segs = 8
        for i in range(arch_segs + 1):
            t = i / arch_segs
            angle = math.pi * t
            ax = math.cos(angle) * width * 0.35
            ay = height / 2 + math.sin(angle) * height * 0.12
            sv, sf = _make_sphere(ax, ay, 0, frame_w * 0.35, rings=3, sectors=4)
            parts.append((sv, sf))

    # Wall hook
    hv, hf = _make_box(0, height / 2 + 0.02, -frame_d, 0.01, 0.02, 0.01)
    parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"PaintingFrame_{frame_style}", verts, faces,
                        frame_style=frame_style, category="wall_decor")


def generate_rug_mesh(
    width: float = 1.5,
    length: float = 2.0,
    style: str = "rectangular",
) -> MeshSpec:
    """Generate a floor rug/carpet mesh.

    Args:
        width: Rug width (X axis).
        length: Rug length (Z axis).
        style: "rectangular", "circular", or "runner".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "circular":
        rug_r = min(width, length) / 2
        segs = 24
        thickness = 0.008
        profile = [
            (0.001, thickness),
            (rug_r * 0.5, thickness),
            (rug_r * 0.9, thickness * 0.8),
            (rug_r, thickness * 0.3),
            (rug_r, 0),
            (rug_r * 0.9, 0),
            (0.001, 0),
        ]
        rv, rf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((rv, rf))

        tassel_count = segs
        for i in range(tassel_count):
            angle = 2.0 * math.pi * i / tassel_count
            tx = math.cos(angle) * (rug_r + 0.02)
            tz = math.sin(angle) * (rug_r + 0.02)
            tv, tf = _make_box(tx, thickness / 2, tz, 0.008, thickness / 2, 0.015)
            parts.append((tv, tf))

    elif style == "runner":
        run_width = width * 0.4
        thickness = 0.006
        rv, rf = _make_box(0, thickness / 2, 0, run_width / 2, thickness / 2, length / 2)
        parts.append((rv, rf))

        for xedge in [-run_width / 2, run_width / 2]:
            ev, ef = _make_box(xedge, thickness, 0, 0.005, thickness / 2, length / 2)
            parts.append((ev, ef))

        fringe_count = 8
        for zend in [-length / 2 - 0.02, length / 2 + 0.02]:
            for i in range(fringe_count):
                t = (i + 0.5) / fringe_count
                fx = -run_width / 2 + t * run_width
                fv, ff = _make_box(fx, thickness / 2, zend, 0.005, thickness / 2, 0.015)
                parts.append((fv, ff))

    else:  # rectangular
        thickness = 0.008
        rv, rf = _make_box(0, thickness / 2, 0, width / 2, thickness / 2, length / 2)
        parts.append((rv, rf))

        border_inset = 0.05
        border_h = 0.003
        for side in [
            (0, -length / 2 + border_inset, width / 2 - border_inset, 0.005),
            (0, length / 2 - border_inset, width / 2 - border_inset, 0.005),
            (-width / 2 + border_inset, 0, 0.005, length / 2 - border_inset),
            (width / 2 - border_inset, 0, 0.005, length / 2 - border_inset),
        ]:
            ev, ef = _make_box(side[0], thickness + border_h / 2, side[1],
                               side[2], border_h / 2, side[3])
            parts.append((ev, ef))

        fringe_count = 10
        for zend_sign in [-1, 1]:
            for i in range(fringe_count):
                t = (i + 0.5) / fringe_count
                fx = -width / 2 + t * width
                fz = zend_sign * (length / 2 + 0.02)
                fv, ff = _make_box(fx, thickness / 2, fz, 0.006, thickness / 2, 0.018)
                parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Rug_{style}", verts, faces,
                        style=style, category="wall_decor")


def generate_chandelier_mesh(
    arms: int = 6,
    tiers: int = 1,
) -> MeshSpec:
    """Generate a hanging chandelier mesh.

    Args:
        arms: Number of candle arms per tier (3-12).
        tiers: Number of tiers (1-3).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    arms = max(3, min(12, arms))
    tiers = max(1, min(3, tiers))
    parts = []

    total_h = 0.3 + (tiers - 1) * 0.2
    # Central chain/rod
    cv, cf = _make_cylinder(0, 0, 0, 0.008, total_h + 0.15, segments=6)
    parts.append((cv, cf))

    # Top hook ring
    tv, tf = _make_torus_ring(0, total_h + 0.15, 0, 0.025, 0.005,
                              major_segments=8, minor_segments=4)
    parts.append((tv, tf))

    for tier in range(tiers):
        tier_y = total_h - tier * 0.2
        tier_r = 0.15 + tier * 0.08

        ring_v, ring_f = _make_torus_ring(0, tier_y, 0, tier_r, 0.008,
                                          major_segments=16, minor_segments=4)
        parts.append((ring_v, ring_f))

        for i in range(arms):
            angle = 2.0 * math.pi * i / arms
            ax = math.cos(angle) * tier_r
            az = math.sin(angle) * tier_r
            arm_end_x = math.cos(angle) * (tier_r + 0.08)
            arm_end_z = math.sin(angle) * (tier_r + 0.08)
            mid_x = (ax + arm_end_x) / 2
            mid_z = (az + arm_end_z) / 2
            av, af = _make_box(mid_x, tier_y, mid_z, 0.04, 0.005, 0.005)
            parts.append((av, af))

            cup_profile = [
                (0.001, tier_y - 0.01),
                (0.015, tier_y - 0.008),
                (0.018, tier_y),
                (0.015, tier_y + 0.005),
            ]
            cuv, cuf = _make_lathe(cup_profile, segments=6,
                                   close_bottom=True, close_top=False)
            cuv = [(v[0] + arm_end_x, v[1], v[2] + arm_end_z) for v in cuv]
            parts.append((cuv, cuf))

            candle_v, candle_f = _make_cylinder(
                arm_end_x, tier_y + 0.005, arm_end_z,
                0.008, 0.05, segments=6,
            )
            parts.append((candle_v, candle_f))

    # Bottom finial
    fv, ff = _make_cone(0, -0.05, 0, 0.02, 0.05, segments=6)
    fv = [(v[0], -v[1] + total_h * 0.05, v[2]) for v in fv]
    parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Chandelier", verts, faces,
                        arms=arms, tiers=tiers, category="wall_decor")


def generate_hanging_cage_mesh(
    size: float = 0.5,
) -> MeshSpec:
    """Generate a suspended prison cage (dark fantasy gibbet).

    Args:
        size: Overall cage size.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bar_r = size * 0.01

    # Cage body - vertical bars in a cylindrical arrangement
    cage_r = size * 0.3
    cage_h = size * 0.8
    bar_count = 12

    for i in range(bar_count):
        angle = 2.0 * math.pi * i / bar_count
        bx = math.cos(angle) * cage_r
        bz = math.sin(angle) * cage_r
        bv, bf = _make_cylinder(bx, 0, bz, bar_r, cage_h, segments=4)
        parts.append((bv, bf))

    # Horizontal rings
    ring_count = 4
    for i in range(ring_count):
        ry = i * cage_h / (ring_count - 1)
        rv, rf = _make_torus_ring(0, ry, 0, cage_r, bar_r * 1.2,
                                  major_segments=bar_count, minor_segments=4)
        parts.append((rv, rf))

    # Top dome (cone)
    cv, cf = _make_cone(0, cage_h, 0, cage_r, size * 0.2, segments=bar_count)
    parts.append((cv, cf))

    # Bottom plate
    bpv, bpf = _make_cylinder(0, -bar_r, 0, cage_r, bar_r * 2, segments=bar_count)
    parts.append((bpv, bpf))

    # Hanging chain (cylinder going up)
    chain_h = size * 0.4
    chv, chf = _make_cylinder(0, cage_h + size * 0.2, 0, bar_r * 1.5,
                              chain_h, segments=4)
    parts.append((chv, chf))

    # Top ring
    trv, trf = _make_torus_ring(0, cage_h + size * 0.2 + chain_h, 0,
                                size * 0.04, bar_r * 2,
                                major_segments=8, minor_segments=4)
    parts.append((trv, trf))

    # Door outline
    door_w = cage_r * 0.5
    dv, df = _make_box(cage_r + bar_r * 2, cage_h * 0.35, 0,
                       bar_r * 2, cage_h * 0.3, door_w / 2)
    parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result("HangingCage", verts, faces,
                        size=size, category="wall_decor")


# =========================================================================
# CATEGORY 14: CRAFTING & TRADE OBJECTS
# =========================================================================


def generate_anvil_mesh(
    size: float = 1.0,
) -> MeshSpec:
    """Generate a blacksmith anvil mesh.

    Args:
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Main body
    body_w = 0.15 * s
    body_h = 0.12 * s
    body_d = 0.35 * s
    bv, bf = _make_beveled_box(0, body_h / 2, 0, body_w, body_h / 2, body_d / 2,
                               bevel=0.005 * s)
    parts.append((bv, bf))

    # Top face (wider working surface)
    top_w = 0.18 * s
    top_h = 0.03 * s
    tv, tf = _make_beveled_box(0, body_h + top_h / 2, 0,
                               top_w, top_h / 2, body_d / 2 + 0.02 * s,
                               bevel=0.003 * s)
    parts.append((tv, tf))

    # Horn (cone at front)
    hv3, hf3 = _make_cone(0, body_h + top_h, body_d / 2 + 0.08 * s,
                           top_w * 0.4, 0.15 * s * 0.3, segments=6)
    parts.append((hv3, hf3))

    # Tail (stepped flat end)
    tail_w = 0.08 * s
    tail_h = 0.025 * s
    tail_d = 0.08 * s
    tv2, tf2 = _make_beveled_box(0, body_h + tail_h / 2, -body_d / 2 - tail_d / 2,
                                 tail_w, tail_h / 2, tail_d / 2, bevel=0.003 * s)
    parts.append((tv2, tf2))

    # Base / pedestal
    base_w = 0.20 * s
    base_h = 0.05 * s
    base_d = 0.25 * s
    bv2, bf2 = _make_beveled_box(0, -base_h / 2, 0, base_w, base_h / 2, base_d,
                                 bevel=0.005 * s)
    parts.append((bv2, bf2))

    # Feet
    foot_w = 0.22 * s
    foot_h = 0.03 * s
    fv, ff = _make_beveled_box(0, -base_h - foot_h / 2, 0,
                               foot_w, foot_h / 2, base_d + 0.02 * s,
                               bevel=0.005 * s)
    parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Anvil", verts, faces, category="crafting")


def generate_forge_mesh(
    size: float = 1.0,
) -> MeshSpec:
    """Generate a forge with chimney and bellows shape.

    Args:
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    s = size

    # Main forge body (stone/brick base)
    base_w = 0.5 * s
    base_h = 0.5 * s
    base_d = 0.4 * s
    bv, bf = _make_beveled_box(0, base_h / 2, 0, base_w / 2, base_h / 2, base_d / 2,
                               bevel=0.01 * s)
    parts.append((bv, bf))

    # Fire pit (recessed top)
    pit_profile = [
        (base_w * 0.4, base_h),
        (base_w * 0.38, base_h + 0.02 * s),
        (base_w * 0.35, base_h + 0.05 * s),
        (base_w * 0.30, base_h + 0.08 * s),
    ]
    pv, pf = _make_lathe(pit_profile, segments=8, close_top=False)
    parts.append((pv, pf))

    # Chimney/hood
    hood_w = base_w * 0.6
    hood_h = 0.4 * s
    hv, hf = _make_tapered_cylinder(0, base_h + 0.08 * s, 0,
                                    hood_w * 0.5, hood_w * 0.2,
                                    hood_h, segments=8, cap_top=True)
    parts.append((hv, hf))

    # Chimney pipe
    chimney_r = 0.06 * s
    chimney_h = 0.5 * s
    cv, cf = _make_cylinder(0, base_h + 0.08 * s + hood_h, 0,
                            chimney_r, chimney_h, segments=8)
    parts.append((cv, cf))

    # Bellows (wedge shape on the side)
    bellow_d = 0.25 * s
    bellow_h = 0.20 * s
    blv, blf = _make_tapered_cylinder(base_w / 2 + 0.075 * s, base_h * 0.3,
                                      0, bellow_d * 0.3, bellow_d * 0.15,
                                      bellow_h, segments=4)
    parts.append((blv, blf))

    # Bellows handle
    bhv, bhf = _make_cylinder(base_w / 2 + 0.15 * s,
                              base_h * 0.3 + bellow_h * 0.8, 0,
                              0.01 * s, 0.1 * s, segments=4)
    parts.append((bhv, bhf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Forge", verts, faces, category="crafting")


def generate_workbench_mesh(
    width: float = 1.5,
    tools: bool = True,
) -> MeshSpec:
    """Generate a carpenter/alchemist workbench mesh.

    Args:
        width: Bench width.
        tools: Whether to include tool shapes on the surface.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    depth = 0.6
    height = 0.85
    top_t = 0.05

    # Tabletop
    tv, tf = _make_beveled_box(0, height, 0, width / 2, top_t / 2, depth / 2,
                               bevel=0.005)
    parts.append((tv, tf))

    # Four sturdy legs
    leg_r = 0.04
    for xo in [-width * 0.42, width * 0.42]:
        for zo in [-depth * 0.38, depth * 0.38]:
            lv, lf = _make_tapered_cylinder(xo, 0, zo, leg_r * 1.1, leg_r,
                                            height - top_t / 2, segments=6)
            parts.append((lv, lf))

    # Bottom shelf
    shelf_y = height * 0.2
    sv, sf = _make_box(0, shelf_y, 0, width * 0.40, 0.01, depth * 0.35)
    parts.append((sv, sf))

    # Back board
    bbv, bbf = _make_beveled_box(0, height + 0.3, -depth / 2 + 0.01,
                                 width / 2, 0.3, 0.01, bevel=0.003)
    parts.append((bbv, bbf))

    if tools:
        # Vise on one end
        vise_w = 0.06
        vv, vf = _make_beveled_box(-width * 0.4, height + top_t / 2 + 0.04,
                                   depth * 0.3,
                                   vise_w, 0.04, 0.04, bevel=0.003)
        parts.append((vv, vf))
        vv2, vf2 = _make_beveled_box(-width * 0.4, height + top_t / 2 + 0.04,
                                     depth * 0.3 + 0.06,
                                     vise_w, 0.04, 0.02, bevel=0.003)
        parts.append((vv2, vf2))
        vsv, vsf = _make_cylinder(-width * 0.4, height + top_t / 2 + 0.04,
                                  depth * 0.3 + 0.08, 0.008, 0.04, segments=6)
        parts.append((vsv, vsf))

        # Bottles on back shelf
        for i in range(3):
            bx = -width * 0.2 + i * 0.15
            bottle_profile = [
                (0.001, height + 0.58),
                (0.015, height + 0.59),
                (0.018, height + 0.62),
                (0.015, height + 0.67),
                (0.008, height + 0.69),
                (0.008, height + 0.72),
            ]
            bpv, bpf = _make_lathe(bottle_profile, segments=6,
                                   close_bottom=True, close_top=True)
            bpv = [(v[0] + bx, v[1], v[2] - depth / 2 + 0.03) for v in bpv]
            parts.append((bpv, bpf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Workbench", verts, faces,
                        tools=tools, category="crafting")


def generate_cauldron_mesh(
    size: float = 0.5,
    legs: int = 3,
) -> MeshSpec:
    """Generate a cauldron mesh with tripod/legs.

    Args:
        size: Cauldron size.
        legs: Number of legs (3 or 4).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 16

    profile = [
        (0.001, 0),
        (size * 0.25, size * 0.02),
        (size * 0.38, size * 0.08),
        (size * 0.42, size * 0.18),
        (size * 0.44, size * 0.30),
        (size * 0.42, size * 0.40),
        (size * 0.38, size * 0.46),
        (size * 0.36, size * 0.48),
        (size * 0.38, size * 0.50),
        (size * 0.40, size * 0.52),
        (size * 0.38, size * 0.53),
    ]
    bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=False)
    parts.append((bv, bf))

    # Rim
    tv, tf = _make_torus_ring(0, size * 0.52, 0, size * 0.38, size * 0.02,
                              major_segments=segs, minor_segments=4)
    parts.append((tv, tf))

    # Legs
    leg_h = size * 0.15
    for i in range(legs):
        angle = 2.0 * math.pi * i / legs
        lx = math.cos(angle) * size * 0.30
        lz = math.sin(angle) * size * 0.30
        lv, lf = _make_tapered_cylinder(lx, -leg_h, lz, size * 0.025, size * 0.035,
                                        leg_h, segments=6, cap_bottom=True)
        parts.append((lv, lf))

    # Handles
    for angle_off in [0, math.pi]:
        handle_pts = 6
        for i in range(handle_pts):
            t = i / (handle_pts - 1)
            a = math.pi * t
            hx = math.cos(angle_off) * (size * 0.40 + math.sin(a) * size * 0.06)
            hz = math.sin(angle_off) * (size * 0.40 + math.sin(a) * size * 0.06)
            hy = size * 0.42 + math.cos(a) * size * 0.08
            sv, sf = _make_sphere(hx, hy, hz, size * 0.015, rings=3, sectors=4)
            parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Cauldron", verts, faces, legs=legs, category="crafting")


def generate_grinding_wheel_mesh(
    radius: float = 0.3,
) -> MeshSpec:
    """Generate a grinding/sharpening wheel mesh.

    Args:
        radius: Wheel radius.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 16
    wheel_t = radius * 0.15

    # Grinding wheel
    wheel_profile = [
        (radius * 0.15, -wheel_t / 2),
        (radius * 0.9, -wheel_t / 2),
        (radius, -wheel_t * 0.3),
        (radius, wheel_t * 0.3),
        (radius * 0.9, wheel_t / 2),
        (radius * 0.15, wheel_t / 2),
    ]
    wv, wf = _make_lathe(wheel_profile, segments=segs,
                         close_bottom=True, close_top=True)
    wheel_y = radius + 0.1
    wv = [(v[0], v[1] + wheel_y, v[2]) for v in wv]
    parts.append((wv, wf))

    # Axle through center
    av, af = _make_cylinder(0, wheel_y, -wheel_t, 0.015, wheel_t * 2, segments=6)
    av = [(v[0], wheel_y, v[1] - wheel_y) for v in av]
    parts.append((av, af))

    # Frame supports
    frame_h = radius + 0.15
    for xside in [-radius * 0.5, radius * 0.5]:
        fv, ff = _make_box(xside, frame_h / 2, 0, 0.02, frame_h / 2, 0.02)
        parts.append((fv, ff))
        ftv, ftf = _make_box(xside, 0.01, 0, 0.04, 0.01, 0.06)
        parts.append((ftv, ftf))

    # Foot pedal / trough
    tv, tf = _make_box(0, 0.02, radius * 0.6, radius * 0.3, 0.015, 0.05)
    parts.append((tv, tf))

    # Water trough beneath
    trough_profile = [
        (radius * 0.35, -0.02),
        (radius * 0.3, 0),
        (radius * 0.25, 0.02),
        (0.001, 0.03),
    ]
    tv2, tf2 = _make_lathe(trough_profile, segments=8, close_top=True)
    tv2 = [(v[0], v[1] + 0.02, v[2]) for v in tv2]
    parts.append((tv2, tf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result("GrindingWheel", verts, faces, category="crafting")


def generate_loom_mesh() -> MeshSpec:
    """Generate a weaving loom frame mesh.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    beam_r = 0.02
    width = 0.8
    height = 1.2
    depth = 0.5

    # Four corner posts
    for xo in [-width / 2, width / 2]:
        for zo in [-depth / 2, depth / 2]:
            pv, pf = _make_cylinder(xo, 0, zo, beam_r, height, segments=6)
            parts.append((pv, pf))

    # Top beam
    tv, tf = _make_box(0, height, 0, width / 2, beam_r, beam_r)
    parts.append((tv, tf))

    # Bottom beam
    bv, bf = _make_box(0, beam_r * 2, 0, width / 2, beam_r, beam_r)
    parts.append((bv, bf))

    # Warp beam (top roller)
    wv2, wf2 = _make_box(0, height * 0.85, -depth / 2, width / 2, beam_r * 1.5, beam_r)
    parts.append((wv2, wf2))

    # Cloth beam (bottom roller)
    cbv, cbf = _make_box(0, height * 0.15, depth / 2, width / 2, beam_r * 1.5, beam_r)
    parts.append((cbv, cbf))

    # Heddle frame
    hv, hf = _make_box(0, height * 0.55, 0, width / 2 - 0.05, beam_r * 0.8, beam_r * 0.5)
    parts.append((hv, hf))

    # Side cross braces
    for xo in [-width / 2, width / 2]:
        cv, cf = _make_box(xo, height * 0.5, 0, beam_r, height * 0.3, depth / 2)
        parts.append((cv, cf))

    # Foot treadles
    for xo in [-width * 0.25, width * 0.25]:
        fv, ff = _make_box(xo, 0.005, depth * 0.3, width * 0.15, 0.005, 0.06)
        parts.append((fv, ff))

    # Vertical warp threads
    thread_count = 12
    for i in range(thread_count):
        t = (i + 0.5) / thread_count
        tx = -width / 2 + t * width + 0.03
        tv3, tf3 = _make_box(tx, height * 0.5, 0, 0.002, height * 0.35, 0.001)
        parts.append((tv3, tf3))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Loom", verts, faces, category="crafting")


def generate_market_stall_mesh(
    width: float = 2.0,
    canopy: bool = True,
) -> MeshSpec:
    """Generate a vendor market stall mesh.

    Args:
        width: Stall width.
        canopy: Whether to include a cloth canopy.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    depth = 1.0
    counter_h = 0.9
    post_r = 0.03

    # Counter surface
    cv, cf = _make_beveled_box(0, counter_h, 0, width / 2, 0.025, depth / 2,
                               bevel=0.005)
    parts.append((cv, cf))

    # Front panel
    fpv, fpf = _make_beveled_box(0, counter_h / 2, depth / 2 - 0.01,
                                 width / 2, counter_h / 2, 0.01, bevel=0.003)
    parts.append((fpv, fpf))

    # Four corner posts
    canopy_h = 2.2
    for xo in [-width / 2, width / 2]:
        for zo in [-depth / 2, depth / 2]:
            pv, pf = _make_cylinder(xo, 0, zo, post_r, canopy_h, segments=6)
            parts.append((pv, pf))

    # Side shelf
    sv, sf = _make_box(0, counter_h * 0.4, -depth / 2 + 0.01, width / 2, 0.01, 0.005)
    parts.append((sv, sf))

    if canopy:
        # Canopy frame beams
        tv, tf = _make_box(0, canopy_h, depth / 2, width / 2, post_r, post_r)
        parts.append((tv, tf))
        bv2, bf2 = _make_box(0, canopy_h, -depth / 2, width / 2, post_r, post_r)
        parts.append((bv2, bf2))
        for xo in [-width / 2, width / 2]:
            sv2, sf2 = _make_box(xo, canopy_h, 0, post_r, post_r, depth / 2)
            parts.append((sv2, sf2))

        # Canopy fabric (quad grid with sag)
        canopy_cols = 6
        canopy_rows = 4
        fabric_verts: list[tuple[float, float, float]] = []
        fabric_faces: list[tuple[int, ...]] = []

        for r in range(canopy_rows + 1):
            zt = r / canopy_rows
            z = -depth / 2 + zt * depth
            for c in range(canopy_cols + 1):
                xt = c / canopy_cols
                x = -width / 2 + xt * width
                sag = -0.08 * math.sin(xt * math.pi) * math.sin(zt * math.pi)
                fabric_verts.append((x, canopy_h + 0.02 + sag, z))

        for r in range(canopy_rows):
            for c in range(canopy_cols):
                i0 = r * (canopy_cols + 1) + c
                i1 = i0 + 1
                i2 = i0 + (canopy_cols + 1) + 1
                i3 = i0 + (canopy_cols + 1)
                fabric_faces.append((i0, i1, i2, i3))

        parts.append((fabric_verts, fabric_faces))

        # Front valance
        val_h = 0.15
        for c in range(canopy_cols):
            xt = (c + 0.5) / canopy_cols
            x = -width / 2 + xt * width
            vv, vf = _make_box(x, canopy_h - val_h / 2, depth / 2 + 0.01,
                               width / canopy_cols / 2 * 0.9, val_h / 2, 0.003)
            parts.append((vv, vf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("MarketStall", verts, faces,
                        canopy=canopy, category="crafting")


# =========================================================================
# CATEGORY 15: SIGNS & MARKERS
# =========================================================================


def generate_signpost_mesh(
    arms: int = 2,
) -> MeshSpec:
    """Generate a directional signpost mesh.

    Args:
        arms: Number of directional sign arms (1-4).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    arms = max(1, min(4, arms))
    parts = []

    # Main post
    post_h = 1.5
    post_r = 0.03
    pv, pf = _make_tapered_cylinder(0, 0, 0, post_r * 1.2, post_r * 0.9,
                                    post_h, segments=6, rings=3)
    parts.append((pv, pf))

    # Post cap
    cv, cf = _make_cone(0, post_h, 0, post_r * 1.5, 0.06, segments=6)
    parts.append((cv, cf))

    # Sign arms at different heights
    for i in range(arms):
        arm_y = post_h * 0.6 + i * 0.2
        x_dir = 1 if i % 2 == 0 else -1
        arm_w = 0.3
        arm_h = 0.08
        arm_d = 0.015

        sv, sf = _make_beveled_box(x_dir * (arm_w / 2 + post_r), arm_y, 0,
                                   arm_w / 2, arm_h / 2, arm_d, bevel=0.003)
        parts.append((sv, sf))

        # Pointed end
        tip_x = x_dir * (arm_w + post_r + 0.02)
        tv, tf = _make_cone(tip_x, arm_y, 0, arm_h / 2, x_dir * 0.04, segments=4)
        tv = [(tip_x + (v[1] - arm_y) * x_dir * 0.5, arm_y + (v[0] - tip_x) * 0.3, v[2])
              for v in tv]
        parts.append((tv, tf))

    # Base stone
    base_profile = [
        (0.001, -0.02),
        (0.08, 0),
        (0.10, 0.02),
        (0.08, 0.05),
        (0.05, 0.06),
    ]
    bv, bf = _make_lathe(base_profile, segments=6, close_bottom=True, close_top=True)
    parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Signpost", verts, faces, arms=arms, category="sign")


def generate_gravestone_mesh(
    style: str = "rounded",
) -> MeshSpec:
    """Generate a gravestone mesh.

    Args:
        style: "cross", "rounded", "obelisk", or "fallen_broken".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "cross":
        arm_w = 0.08
        arm_h = 0.5
        cross_w = 0.35
        cross_h = 0.08
        depth = 0.05

        vv, vf = _make_beveled_box(0, arm_h / 2, 0, arm_w / 2, arm_h / 2, depth / 2,
                                   bevel=0.005)
        parts.append((vv, vf))
        hv, hf = _make_beveled_box(0, arm_h * 0.65, 0, cross_w / 2, cross_h / 2,
                                   depth / 2, bevel=0.005)
        parts.append((hv, hf))
        bv, bf = _make_beveled_box(0, -0.02, 0, arm_w * 1.5, 0.02, depth * 1.2,
                                   bevel=0.003)
        parts.append((bv, bf))

    elif style == "rounded":
        w = 0.3
        h = 0.5
        d = 0.06

        bv, bf = _make_beveled_box(0, h * 0.4, 0, w / 2, h * 0.4, d / 2, bevel=0.005)
        parts.append((bv, bf))

        arch_segs = 8
        for i in range(arch_segs + 1):
            t = i / arch_segs
            angle = math.pi * t
            ax = math.cos(angle) * w / 2
            ay = h * 0.8 + math.sin(angle) * w * 0.3
            sv, sf = _make_box(ax, ay, 0, 0.02, 0.02, d / 2)
            parts.append((sv, sf))

        gv, gf = _make_box(0, -0.01, 0, w * 0.6, 0.015, d * 1.2)
        parts.append((gv, gf))

    elif style == "obelisk":
        h = 0.8
        base_w = 0.15

        tv, tf = _make_tapered_cylinder(0, 0, 0, base_w, base_w * 0.5,
                                        h, segments=4, rings=4,
                                        cap_top=True, cap_bottom=True)
        parts.append((tv, tf))

        cv, cf = _make_cone(0, h, 0, base_w * 0.5, 0.1, segments=4)
        parts.append((cv, cf))

        for i in range(3):
            step_w = base_w * (1.4 - i * 0.1)
            step_h = 0.03
            sv, sf = _make_beveled_box(0, -i * step_h - step_h / 2, 0,
                                       step_w, step_h / 2, step_w, bevel=0.003)
            parts.append((sv, sf))

    else:  # fallen_broken
        w = 0.3
        h = 0.5
        d = 0.06

        bv, bf = _make_beveled_box(0.1, d / 2 + 0.01, 0, h * 0.3, d / 2, w / 2,
                                   bevel=0.005)
        parts.append((bv, bf))

        bbv, bbf = _make_beveled_box(-0.05, h * 0.08, 0, w / 2, h * 0.08, d / 2,
                                     bevel=0.005)
        parts.append((bbv, bbf))

        mv, mf = _make_box(0, 0.005, 0, w * 0.8, 0.01, w * 0.6)
        parts.append((mv, mf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gravestone_{style}", verts, faces,
                        style=style, category="sign")


def generate_waystone_mesh(
    height: float = 1.0,
) -> MeshSpec:
    """Generate a runic waypoint marker stone.

    Args:
        height: Stone height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    base_r = height * 0.12
    sv, sf = _make_tapered_cylinder(0, 0, 0, base_r, base_r * 0.7,
                                    height, segments=6, rings=4,
                                    cap_top=True, cap_bottom=True)
    parts.append((sv, sf))

    # Rune band rings
    for t in [0.25, 0.5, 0.75]:
        ring_y = height * t
        ring_r = base_r + (base_r * 0.7 - base_r) * t + 0.005
        rv, rf = _make_torus_ring(0, ring_y, 0, abs(ring_r), height * 0.01,
                                  major_segments=6, minor_segments=3)
        parts.append((rv, rf))

    # Crystal cap at top
    crystal_h = height * 0.15
    crystal_r = base_r * 0.4
    cv, cf = _make_tapered_cylinder(0, height, 0, crystal_r, crystal_r * 0.1,
                                    crystal_h, segments=6, cap_top=True)
    parts.append((cv, cf))

    # Base platform
    bp_r = base_r * 1.5
    bpv, bpf = _make_cylinder(0, -0.03, 0, bp_r, 0.03, segments=6)
    parts.append((bpv, bpf))

    # Ground-level step
    gsv, gsf = _make_cylinder(0, -0.05, 0, bp_r * 1.3, 0.02, segments=6)
    parts.append((gsv, gsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Waystone", verts, faces, category="sign")


def generate_milestone_mesh() -> MeshSpec:
    """Generate a road distance marker stone.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    stone_w = 0.15
    stone_h = 0.6
    stone_d = 0.10
    sv, sf = _make_beveled_box(0, stone_h / 2, 0, stone_w / 2, stone_h / 2, stone_d / 2,
                               bevel=0.01)
    parts.append((sv, sf))

    # Rounded top cap
    cap_segs = 6
    for i in range(cap_segs + 1):
        t = i / cap_segs
        angle = math.pi * t
        cx = math.cos(angle) * stone_w / 2
        cy = stone_h + math.sin(angle) * stone_w * 0.3
        cv, cf = _make_box(cx, cy, 0, 0.015, 0.015, stone_d / 2)
        parts.append((cv, cf))

    # Inscription area
    inset_d = 0.003
    iv, i_f = _make_box(0, stone_h * 0.45, stone_d / 2 - inset_d,
                        stone_w * 0.35, stone_h * 0.2, inset_d)
    parts.append((iv, i_f))

    # Ground base
    gv, gf = _make_box(0, -0.01, 0, stone_w * 0.8, 0.015, stone_d * 0.8)
    parts.append((gv, gf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Milestone", verts, faces, category="sign")


# =========================================================================
# CATEGORY 16: NATURAL FORMATIONS
# =========================================================================


def generate_stalactite_mesh(
    length: float = 0.5,
    thickness: float = 0.08,
) -> MeshSpec:
    """Generate a ceiling stalactite formation.

    Args:
        length: Stalactite length (hangs down).
        thickness: Base thickness.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(31)
    parts = []
    segs = 8

    profile = [
        (0.001, -length),
        (thickness * 0.1, -length * 0.95),
        (thickness * 0.25, -length * 0.85),
        (thickness * 0.4, -length * 0.70),
        (thickness * 0.55, -length * 0.50),
        (thickness * 0.7, -length * 0.30),
        (thickness * 0.85, -length * 0.15),
        (thickness * 0.95, -length * 0.05),
        (thickness, 0),
    ]
    sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((sv, sf))

    # Ceiling attachment
    base_profile = [
        (thickness, 0),
        (thickness * 1.3, 0.01),
        (thickness * 1.5, 0.025),
        (thickness * 1.3, 0.04),
    ]
    bv, bf = _make_lathe(base_profile, segments=segs, close_top=True)
    parts.append((bv, bf))

    # Secondary drip formations
    for _ in range(3):
        ox = rng.uniform(-thickness * 0.5, thickness * 0.5)
        oz = rng.uniform(-thickness * 0.5, thickness * 0.5)
        sl = length * rng.uniform(0.2, 0.5)
        sr = thickness * rng.uniform(0.2, 0.4)
        dv, df = _make_tapered_cylinder(ox, -sl, oz, 0.001, sr, sl,
                                        segments=5, cap_top=True, cap_bottom=True)
        parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Stalactite", verts, faces, category="natural")


def generate_stalagmite_mesh(
    height: float = 0.4,
    thickness: float = 0.1,
) -> MeshSpec:
    """Generate a floor stalagmite formation.

    Args:
        height: Stalagmite height.
        thickness: Base thickness.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(37)
    parts = []
    segs = 8

    profile = [
        (thickness, 0),
        (thickness * 0.95, height * 0.05),
        (thickness * 0.85, height * 0.15),
        (thickness * 0.70, height * 0.30),
        (thickness * 0.55, height * 0.50),
        (thickness * 0.40, height * 0.65),
        (thickness * 0.25, height * 0.80),
        (thickness * 0.12, height * 0.92),
        (0.001, height),
    ]
    sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((sv, sf))

    base_profile = [
        (thickness * 1.5, -0.02),
        (thickness * 1.3, 0),
        (thickness * 1.1, 0.01),
        (thickness, 0.02),
    ]
    bv, bf = _make_lathe(base_profile, segments=segs, close_bottom=True)
    parts.append((bv, bf))

    for _ in range(2):
        ox = rng.uniform(-thickness * 0.6, thickness * 0.6)
        oz = rng.uniform(-thickness * 0.6, thickness * 0.6)
        sh = height * rng.uniform(0.2, 0.5)
        sr = thickness * rng.uniform(0.2, 0.4)
        dv, df = _make_tapered_cylinder(ox, 0, oz, sr, 0.001, sh,
                                        segments=5, cap_top=True, cap_bottom=True)
        parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Stalagmite", verts, faces, category="natural")


def generate_bone_pile_mesh(
    count: int = 10,
    creature_size: float = 1.0,
) -> MeshSpec:
    """Generate a scattered bone pile mesh.

    Args:
        count: Number of bones (5-30).
        creature_size: Scale factor (1.0 = human-sized bones).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(66)
    count = max(5, min(30, count))
    parts = []
    s = creature_size

    for _ in range(count):
        bone_type = rng.choice(["long", "short", "round"])
        bx = rng.uniform(-0.3 * s, 0.3 * s)
        bz = rng.uniform(-0.3 * s, 0.3 * s)
        by = rng.uniform(0, 0.05 * s)

        if bone_type == "long":
            bone_len = rng.uniform(0.15, 0.3) * s
            bone_r = rng.uniform(0.008, 0.015) * s
            bv, bf = _make_tapered_cylinder(bx, by, bz, bone_r, bone_r * 0.8,
                                            bone_len, segments=5,
                                            cap_top=True, cap_bottom=True)
            parts.append((bv, bf))
            kv, kf = _make_sphere(bx, by + bone_len, bz,
                                  bone_r * 1.5, rings=3, sectors=4)
            parts.append((kv, kf))

        elif bone_type == "short":
            bone_r = rng.uniform(0.01, 0.02) * s
            bone_h = rng.uniform(0.01, 0.02) * s
            bv, bf = _make_cylinder(bx, by, bz, bone_r, bone_h, segments=5)
            parts.append((bv, bf))

        else:  # round
            bone_r = rng.uniform(0.015, 0.035) * s
            bv, bf = _make_sphere(bx, by + bone_r, bz,
                                  bone_r, rings=4, sectors=5)
            parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("BonePile", verts, faces,
                        count=count, category="natural")


def generate_nest_mesh(
    size: float = 0.4,
    material: str = "bird_sticks",
) -> MeshSpec:
    """Generate a nest mesh.

    Args:
        size: Overall nest size.
        material: "bird_sticks", "spider_web", or "dragon_bones".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(44)
    parts = []

    if material == "bird_sticks":
        bowl_profile = [
            (0.001, 0),
            (size * 0.2, 0.005),
            (size * 0.35, 0.015),
            (size * 0.42, 0.03),
            (size * 0.45, 0.06),
            (size * 0.43, 0.09),
        ]
        bv, bf = _make_lathe(bowl_profile, segments=10,
                             close_bottom=True, close_top=False)
        parts.append((bv, bf))

        rv, rf = _make_torus_ring(0, 0.09, 0, size * 0.43, size * 0.02,
                                  major_segments=10, minor_segments=4)
        parts.append((rv, rf))

        twig_count = 15
        for _ in range(twig_count):
            tx = rng.uniform(-size * 0.4, size * 0.4)
            tz = rng.uniform(-size * 0.4, size * 0.4)
            ty = rng.uniform(0.04, 0.10)
            tl = rng.uniform(size * 0.1, size * 0.3)
            tr = size * 0.005
            tv, tf = _make_cylinder(tx, ty, tz, tr, tl, segments=3)
            parts.append((tv, tf))

        for _ in range(3):
            ex = rng.uniform(-size * 0.1, size * 0.1)
            ez = rng.uniform(-size * 0.1, size * 0.1)
            er = size * 0.04
            ev, ef = _make_sphere(ex, 0.03, ez, er, rings=4, sectors=6)
            ev = [(v[0], v[1] * 1.2, v[2]) for v in ev]
            parts.append((ev, ef))

    elif material == "spider_web":
        sv, sf = _make_sphere(0, size * 0.5, 0, size * 0.5, rings=6, sectors=8)
        parts.append((sv, sf))

        iv, i_f = _make_sphere(0, size * 0.5, 0, size * 0.35, rings=4, sectors=6)
        parts.append((iv, i_f))

        strand_count = 6
        for i in range(strand_count):
            angle = 2.0 * math.pi * i / strand_count
            sx = math.cos(angle) * size * 0.8
            sz = math.sin(angle) * size * 0.8
            sy = size * 0.5 + rng.uniform(-size * 0.2, size * 0.2)
            mid_x = sx * 0.5
            mid_z = sz * 0.5
            sv2, sf2 = _make_cylinder(mid_x, sy, mid_z, size * 0.003,
                                      size * 0.5, segments=3)
            parts.append((sv2, sf2))

    else:  # dragon_bones
        bowl_profile = [
            (0.001, 0),
            (size * 0.4, 0.02),
            (size * 0.6, 0.05),
            (size * 0.7, 0.10),
            (size * 0.65, 0.18),
        ]
        bv, bf = _make_lathe(bowl_profile, segments=8,
                             close_bottom=True, close_top=False)
        parts.append((bv, bf))

        bone_count = 8
        for i in range(bone_count):
            angle = 2.0 * math.pi * i / bone_count
            bx = math.cos(angle) * size * 0.55
            bz = math.sin(angle) * size * 0.55
            bone_len = size * rng.uniform(0.3, 0.6)
            bone_r = size * 0.025
            bov, bof = _make_tapered_cylinder(bx, 0.08, bz, bone_r, bone_r * 0.5,
                                              bone_len, segments=5, cap_top=True)
            parts.append((bov, bof))
            kv, kf = _make_sphere(bx, 0.08 + bone_len, bz,
                                  bone_r * 1.5, rings=3, sectors=4)
            parts.append((kv, kf))

        skull_r = size * 0.12
        skv, skf = _make_sphere(0, skull_r + 0.05, 0, skull_r, rings=5, sectors=6)
        parts.append((skv, skf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Nest_{material}", verts, faces,
                        material=material, category="natural")


def generate_geyser_vent_mesh(
    radius: float = 0.3,
) -> MeshSpec:
    """Generate a ground geyser/steam vent opening.

    Args:
        radius: Vent opening radius.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(51)
    parts = []
    segs = 12

    rim_profile = [
        (radius * 1.8, -0.02),
        (radius * 1.5, 0),
        (radius * 1.3, 0.03),
        (radius * 1.1, 0.06),
        (radius * 0.9, 0.08),
        (radius * 0.8, 0.07),
        (radius * 0.6, 0.04),
        (radius * 0.5, 0.02),
    ]
    rv, rf = _make_lathe(rim_profile, segments=segs, close_bottom=True)
    parts.append((rv, rf))

    vent_profile = [
        (radius * 0.5, 0.02),
        (radius * 0.45, 0),
        (radius * 0.35, -0.05),
        (radius * 0.25, -0.12),
        (radius * 0.15, -0.20),
        (0.001, -0.30),
    ]
    vv, vf = _make_lathe(vent_profile, segments=segs, close_top=True)
    parts.append((vv, vf))

    for i in range(8):
        angle = 2.0 * math.pi * i / 8 + rng.uniform(-0.2, 0.2)
        dx = math.cos(angle) * radius * rng.uniform(0.8, 1.2)
        dz = math.sin(angle) * radius * rng.uniform(0.8, 1.2)
        dh = rng.uniform(0.02, 0.06)
        dr = rng.uniform(radius * 0.05, radius * 0.12)
        cv, cf = _make_cone(dx, 0.04, dz, dr, dh, segments=5)
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("GeyserVent", verts, faces, category="natural")


def generate_fallen_log_mesh(
    length: float = 2.0,
    diameter: float = 0.3,
) -> MeshSpec:
    """Generate a fallen/rotting tree log mesh.

    Args:
        length: Log length.
        diameter: Log diameter.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng
    rng = _rng.Random(73)
    parts = []
    segs = 12
    r = diameter / 2

    profile = [
        (r * 1.05, 0),
        (r * 1.02, length * 0.1),
        (r, length * 0.2),
        (r * 0.98, length * 0.4),
        (r * 0.95, length * 0.6),
        (r * 0.90, length * 0.8),
        (r * 0.82, length * 0.95),
        (r * 0.75, length),
    ]
    lv, lf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)

    # Rotate to lie horizontal (swap Y and Z)
    lv = [(v[0], v[2] + r, v[1]) for v in lv]
    parts.append((lv, lf))

    # Broken branch stubs
    stub_count = 4
    for _ in range(stub_count):
        sz = rng.uniform(0.1, 0.9) * length
        angle = rng.uniform(0, 2.0 * math.pi)
        sx = math.cos(angle) * r * 0.9
        sy = r + math.sin(angle) * r * 0.9
        stub_r = r * rng.uniform(0.08, 0.15)
        stub_h = rng.uniform(0.05, 0.15)
        sv, sf = _make_cone(sx, sy, sz, stub_r, stub_h, segments=5)
        parts.append((sv, sf))

    # Root end
    for i in range(4):
        angle = 2.0 * math.pi * i / 4 + 0.3
        rx = math.cos(angle) * r * 0.6
        ry = r + math.sin(angle) * r * 0.6
        rv2, rf2 = _make_cone(rx, ry, -0.01, r * 0.08, r * 0.3, segments=4)
        rv2 = [(v[0], v[1], v[2] - 0.05) for v in rv2]
        parts.append((rv2, rf2))

    # Shelf mushrooms
    for i in range(2):
        my = r * 0.5
        mz = length * (0.3 + i * 0.4)
        shelf_r = r * 0.2
        shelf_verts: list[tuple[float, float, float]] = []
        shelf_faces: list[tuple[int, ...]] = []
        n_pts = 6
        shelf_thick = r * 0.04

        shelf_verts.append((0, my + shelf_thick, mz))
        for j in range(n_pts):
            a = math.pi * j / (n_pts - 1)
            shelf_verts.append((
                math.cos(a) * shelf_r,
                my + shelf_thick,
                mz + math.sin(a) * shelf_r * 0.5,
            ))

        shelf_verts.append((0, my, mz))
        for j in range(n_pts):
            a = math.pi * j / (n_pts - 1)
            shelf_verts.append((
                math.cos(a) * shelf_r,
                my,
                mz + math.sin(a) * shelf_r * 0.5,
            ))

        for j in range(n_pts - 1):
            shelf_faces.append((0, j + 1, j + 2))
        c2 = n_pts + 1
        for j in range(n_pts - 1):
            shelf_faces.append((c2, c2 + j + 2, c2 + j + 1))
        for j in range(n_pts - 1):
            t_idx = j + 1
            b_idx = c2 + j + 1
            shelf_faces.append((t_idx, b_idx, b_idx + 1, t_idx + 1))

        parts.append((shelf_verts, shelf_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result("FallenLog", verts, faces, category="natural")


# =========================================================================
# CATEGORY: MONSTER PARTS
# =========================================================================


def generate_horn_mesh(
    style: str = "demon_straight", length: float = 0.4,
    curve: float = 0.5, segments: int = 8,
) -> MeshSpec:
    """Generate a horn mesh with various fantasy styles.

    Args:
        style: "ram_curl", "demon_straight", "antler_branching", or "unicorn_spiral".
        length: Total length of the horn.
        curve: Curvature amount (0 = straight, 1 = heavy curve).
        segments: Number of segments along the horn length.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = max(4, segments)
    ring_segs = 8
    if style == "ram_curl":
        horn_verts: list[tuple[float, float, float]] = []
        horn_faces: list[tuple[int, ...]] = []
        for i in range(segs + 1):
            t = i / segs
            angle = t * math.pi * 1.8 * curve
            r = length * 0.08 * (1.0 - t * 0.75)
            cx = math.sin(angle) * t * length * 0.4
            cy = t * length * 0.6 + math.cos(angle) * t * length * 0.2
            cz = -t * length * 0.3
            for j in range(ring_segs):
                a = 2.0 * math.pi * j / ring_segs
                horn_verts.append((cx + math.cos(a) * r,
                                   cy + math.sin(a) * r * 0.8,
                                   cz + math.sin(a) * r * 0.6))
        for i in range(segs):
            for j in range(ring_segs):
                j2 = (j + 1) % ring_segs
                horn_faces.append((i * ring_segs + j, i * ring_segs + j2,
                                   (i + 1) * ring_segs + j2, (i + 1) * ring_segs + j))
        horn_faces.append(tuple(range(ring_segs - 1, -1, -1)))
        horn_faces.append(tuple(segs * ring_segs + j for j in range(ring_segs)))
        parts.append((horn_verts, horn_faces))
    elif style == "antler_branching":
        profile_main = [(length * 0.04 * (1.0 - t / segs), t * length / segs)
                        for t in range(segs + 1)]
        mv, mf = _make_lathe(profile_main, segments=ring_segs,
                             close_bottom=True, close_top=True)
        parts.append((mv, mf))
        for ti in range(3):
            branch_y = (0.3 + 0.25 * ti) * length
            branch_len = length * (0.35 - 0.08 * ti)
            ba = math.pi * 0.25 + ti * 0.2
            bx, bz = math.sin(ba) * 0.02, math.cos(ba) * 0.02
            bv, bf = _make_tapered_cylinder(bx, branch_y, bz, length * 0.025,
                                            length * 0.008, branch_len,
                                            segments=6, rings=3)
            rotated = [(bx + (v[0] - bx) * math.cos(0.6) - (v[1] - branch_y) * math.sin(0.6),
                        branch_y + (v[0] - bx) * math.sin(0.6) + (v[1] - branch_y) * math.cos(0.6),
                        v[2]) for v in bv]
            parts.append((rotated, bf))
    elif style == "unicorn_spiral":
        horn_verts_u: list[tuple[float, float, float]] = []
        horn_faces_u: list[tuple[int, ...]] = []
        spiral_segs = segs * 2
        for i in range(spiral_segs + 1):
            t = i / spiral_segs
            r = length * 0.05 * (1.0 - t * 0.85)
            groove = 1.0 + 0.15 * math.sin(t * math.pi * 8)
            cy = t * length
            for j in range(ring_segs):
                a = 2.0 * math.pi * j / ring_segs
                lg = groove + 0.1 * math.sin(a * 3 + t * math.pi * 6)
                horn_verts_u.append((math.cos(a) * r * lg, cy, math.sin(a) * r * lg))
        for i in range(spiral_segs):
            for j in range(ring_segs):
                j2 = (j + 1) % ring_segs
                horn_faces_u.append((i * ring_segs + j, i * ring_segs + j2,
                                     (i + 1) * ring_segs + j2, (i + 1) * ring_segs + j))
        horn_faces_u.append(tuple(range(ring_segs - 1, -1, -1)))
        horn_faces_u.append(tuple(spiral_segs * ring_segs + j for j in range(ring_segs)))
        parts.append((horn_verts_u, horn_faces_u))
    else:  # demon_straight
        profile = [(length * 0.06 * (1.0 - (t / segs) * 0.8), t * length / segs)
                   for t in range(segs + 1)]
        sv, sf = _make_lathe(profile, segments=ring_segs,
                             close_bottom=True, close_top=True)
        curved = [(v[0], v[1] + curve * 0.1 * v[1] * v[1],
                   v[2] - curve * 0.05 * v[1]) for v in sv]
        parts.append((curved, sf))
        for ri in range(segs - 1):
            t = (ri + 1) / segs
            rr = length * 0.008
            rv, rf = _make_box(0, t * length, length * 0.06 * (1.0 - t * 0.8),
                               rr, rr * 2, rr * 0.5)
            parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Horn_{style}", verts, faces,
                        style=style, category="monster_part")


def generate_claw_set_mesh(
    fingers: int = 4, length: float = 0.15, curve: float = 0.6,
) -> MeshSpec:
    """Generate a set of monster claws (hand or foot).

    Args:
        fingers: Number of claw digits (3-6).
        length: Length of each claw.
        curve: Curvature of the claws (0.2-1.5).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    fingers = max(3, min(6, fingers))
    pad_r = length * 0.6
    pv, pf = _make_tapered_cylinder(0, 0, 0, pad_r, pad_r * 0.8,
                                    length * 0.3, segments=fingers * 2, rings=2)
    parts.append((pv, pf))
    spread = math.pi * 0.6
    for i in range(fingers):
        ang = -spread / 2 + spread * i / max(fingers - 1, 1)
        fx = math.sin(ang) * pad_r * 0.7
        fz = math.cos(ang) * pad_r * 0.7
        for s in range(5):
            t = s / 5
            ca = t * curve * math.pi * 0.5
            sr = length * 0.05 * (1.0 - t * 0.7)
            sx = fx + math.sin(ca) * length * 0.3
            sy = length * 0.3 + t * length * 0.7 * math.cos(ca * 0.5)
            cv, cf = _make_cylinder(sx, sy, fz, max(sr, 0.002), length / 5 * 0.9,
                                    segments=4, cap_top=(s == 4), cap_bottom=(s == 0))
            parts.append((cv, cf))
        ta = curve * math.pi * 0.5
        tv, tf = _make_cone(fx + math.sin(ta) * length * 0.3,
                            length * 0.3 + length * 0.7 * math.cos(ta * 0.5),
                            fz, length * 0.02, length * 0.12, segments=4)
        parts.append((tv, tf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("ClawSet", verts, faces, fingers=fingers, category="monster_part")


def generate_tail_mesh(
    length: float = 1.0, segments: int = 12, tip_style: str = "spike",
) -> MeshSpec:
    """Generate a creature tail mesh with various tip styles.

    Args:
        length: Total length of the tail.
        segments: Number of segments along the tail.
        tip_style: "spike", "club", "blade", "whip", or "stinger".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = max(6, segments)
    rs = 8
    tv: list[tuple[float, float, float]] = []
    tfa: list[tuple[int, ...]] = []
    for i in range(segs + 1):
        t = i / segs
        r = length * 0.06 * (1.0 - t * 0.6)
        cx = -t * length * 0.8
        cy = length * 0.15 * math.sin(t * math.pi * 0.8)
        for j in range(rs):
            a = 2.0 * math.pi * j / rs
            tv.append((cx + math.cos(a) * r * 0.8, cy + math.sin(a) * r,
                       math.cos(a) * r * 0.8))
    for i in range(segs):
        for j in range(rs):
            j2 = (j + 1) % rs
            tfa.append((i * rs + j, i * rs + j2, (i + 1) * rs + j2, (i + 1) * rs + j))
    tfa.append(tuple(range(rs - 1, -1, -1)))
    parts.append((tv, tfa))
    tip_x = -length * 0.8
    tip_y = length * 0.15 * math.sin(math.pi * 0.8)
    tip_r = length * 0.06 * 0.4
    if tip_style == "spike":
        cv, cf = _make_cone(tip_x, tip_y, 0, tip_r * 1.2, length * 0.15, segments=6)
        parts.append(([(v[0] - (v[1] - tip_y) * 0.8, tip_y + (v[0] - tip_x) * 0.1,
                        v[2]) for v in cv], cf))
    elif tip_style == "club":
        sv, sf = _make_sphere(tip_x - length * 0.05, tip_y, 0,
                              tip_r * 3, rings=6, sectors=8)
        parts.append((sv, sf))
        for ri in range(4):
            a = math.pi * 0.5 * ri
            rv, rf = _make_cone(tip_x - length * 0.05 + math.cos(a) * tip_r * 2.5,
                                tip_y + math.sin(a) * tip_r * 2.5, 0,
                                tip_r * 0.5, tip_r * 1.5, segments=4)
            parts.append((rv, rf))
    elif tip_style == "blade":
        bv, bf = _make_box(tip_x - length * 0.06, tip_y, 0,
                           length * 0.06, tip_r * 1.5, tip_r * 0.3)
        parts.append((bv, bf))
        ev, ef = _make_cone(tip_x - length * 0.12, tip_y, 0,
                            tip_r * 1.2, length * 0.06, segments=4)
        parts.append(([(v[0] - (v[1] - tip_y) * 0.5, tip_y, v[2]) for v in ev], ef))
    elif tip_style == "whip":
        wv, wf = _make_tapered_cylinder(tip_x, tip_y, 0, tip_r, tip_r * 0.1,
                                        length * 0.25, segments=6, rings=4)
        parts.append(([(v[0] - (v[1] - tip_y) * 0.3, v[1], v[2]) for v in wv], wf))
    else:  # stinger
        sv, sf = _make_sphere(tip_x - tip_r * 1.5, tip_y, 0,
                              tip_r * 2, rings=5, sectors=6)
        parts.append((sv, sf))
        stv, stf = _make_cone(tip_x - tip_r * 3.5, tip_y, 0,
                              tip_r * 0.8, tip_r * 4, segments=6)
        parts.append(([(v[0] - (v[1] - tip_y) * 0.9,
                        tip_y + (v[0] - tip_x + tip_r * 3.5) * 0.05, v[2])
                       for v in stv], stf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Tail_{tip_style}", verts, faces,
                        tip_style=tip_style, category="monster_part")


def generate_wing_mesh(
    span: float = 1.5, style: str = "bat_leather", membrane: bool = True,
) -> MeshSpec:
    """Generate a creature wing mesh.

    Args:
        span: Total wingspan (one wing).
        style: "bat_leather", "dragon_scaled", "skeletal_bone", or "feathered".
        membrane: Whether to include wing membrane between bones.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    bone_r = span * 0.015
    elbow = (span * 0.4, span * 0.1, 0.0)
    n_fingers = 4 if style != "feathered" else 3
    arm_len = math.sqrt(elbow[0]**2 + elbow[1]**2)
    av, af = _make_tapered_cylinder(0, 0, 0, bone_r * 1.5, bone_r, arm_len,
                                    segments=6, rings=2)
    aa = math.atan2(elbow[1], elbow[0])
    parts.append(([(v[0] * math.cos(aa) - v[1] * math.sin(aa),
                    v[0] * math.sin(aa) + v[1] * math.cos(aa), v[2]) for v in av], af))
    finger_tips: list[tuple[float, float, float]] = []
    for fi in range(n_fingers):
        t = fi / max(n_fingers - 1, 1)
        fa = math.pi * 0.1 + t * math.pi * 0.35
        fl = span * (0.6 - fi * 0.08)
        tx = elbow[0] + math.cos(fa) * fl
        ty = elbow[1] + math.sin(fa) * fl
        finger_tips.append((tx, ty, 0.0))
        fv, ff = _make_tapered_cylinder(elbow[0], elbow[1], 0, bone_r * 0.8,
                                        bone_r * 0.3, fl, segments=4, rings=2)
        faa = math.atan2(ty - elbow[1], tx - elbow[0])
        parts.append(([(elbow[0] + (v[0] - elbow[0]) * math.cos(faa) -
                        (v[1] - elbow[1]) * math.sin(faa),
                        elbow[1] + (v[0] - elbow[0]) * math.sin(faa) +
                        (v[1] - elbow[1]) * math.cos(faa), v[2]) for v in fv], ff))
    if membrane and len(finger_tips) >= 2:
        for fi in range(len(finger_tips) - 1):
            p0, p1 = finger_tips[fi], finger_tips[fi + 1]
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, 0.0)
            parts.append(([elbow, p0, mid, p1], [(0, 1, 2), (0, 2, 3)]))
        parts.append(([elbow, finger_tips[-1], (0.0, -span * 0.15, 0.0)], [(0, 1, 2)]))
    if style == "dragon_scaled":
        for tip in finger_tips:
            for si in range(4):
                st = (si + 1) / 5
                scv, scf = _make_cone(elbow[0] + (tip[0] - elbow[0]) * st,
                                      elbow[1] + (tip[1] - elbow[1]) * st,
                                      bone_r * 0.5, bone_r * 0.6, bone_r * 1.5, segments=4)
                parts.append((scv, scf))
    elif style == "skeletal_bone":
        jv, jf = _make_sphere(elbow[0], elbow[1], 0, bone_r * 2.5, rings=4, sectors=6)
        parts.append((jv, jf))
        sv2, sf2 = _make_sphere(0, 0, 0, bone_r * 2, rings=4, sectors=6)
        parts.append((sv2, sf2))
    elif style == "feathered":
        for fi in range(len(finger_tips) - 1):
            p0, p1 = finger_tips[fi], finger_tips[fi + 1]
            for qi in range(5):
                ft = (qi + 0.5) / 5
                qv, qf = _make_tapered_cylinder(p0[0] + (p1[0] - p0[0]) * ft,
                                                p0[1] + (p1[1] - p0[1]) * ft, 0,
                                                bone_r * 0.3, bone_r * 0.1,
                                                span * 0.08, segments=4, rings=1)
                parts.append((qv, qf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Wing_{style}", verts, faces,
                        style=style, span=span, category="monster_part")


def generate_tentacle_mesh(
    length: float = 1.0, segments: int = 16, suckers: bool = True,
) -> MeshSpec:
    """Generate a tentacle mesh with taper and optional suckers.

    Args:
        length: Total tentacle length.
        segments: Number of segments along the tentacle.
        suckers: Whether to add sucker details along the underside.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = max(6, segments)
    rs = 8
    tv: list[tuple[float, float, float]] = []
    tfa: list[tuple[int, ...]] = []
    for i in range(segs + 1):
        t = i / segs
        r = length * 0.04 * (1.0 - t * 0.85)
        cx = t * length
        cy = length * 0.08 * math.sin(t * math.pi * 2.0)
        cz = length * 0.05 * math.sin(t * math.pi * 1.5 + 0.5)
        for j in range(rs):
            a = 2.0 * math.pi * j / rs
            tv.append((cx, cy + math.sin(a) * r, cz + math.cos(a) * r))
    for i in range(segs):
        for j in range(rs):
            j2 = (j + 1) % rs
            tfa.append((i * rs + j, i * rs + j2, (i + 1) * rs + j2, (i + 1) * rs + j))
    tfa.append(tuple(range(rs - 1, -1, -1)))
    tfa.append(tuple(segs * rs + j for j in range(rs)))
    parts.append((tv, tfa))
    if suckers:
        ns = segs // 2
        for si in range(ns):
            t = (si + 0.5) / ns * 0.85
            sx = t * length
            sy = length * 0.08 * math.sin(t * math.pi * 2.0) - length * 0.04 * (1.0 - t * 0.85)
            sz = length * 0.05 * math.sin(t * math.pi * 1.5 + 0.5)
            sr = length * 0.015 * (1.0 - t * 0.5)
            sv, sf = _make_torus_ring(sx, sy, sz, sr, sr * 0.3,
                                      major_segments=6, minor_segments=4)
            parts.append((sv, sf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Tentacle", verts, faces, suckers=suckers, category="monster_part")


def generate_mandible_mesh(size: float = 0.15, style: str = "insect") -> MeshSpec:
    """Generate insect/spider mandible mesh.

    Args:
        size: Overall size of the mandible pair.
        style: "insect" or "spider".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    for sm in [-1.0, 1.0]:
        if style == "spider":
            bx = sm * size * 0.15
            bv, bf = _make_tapered_cylinder(bx, 0, 0, size * 0.08, size * 0.06,
                                            size * 0.3, segments=6, rings=2)
            parts.append((bv, bf))
            fv: list[tuple[float, float, float]] = []
            ff: list[tuple[int, ...]] = []
            fs, fr = 6, 4
            for i in range(fs + 1):
                t = i / fs
                r = size * 0.04 * (1.0 - t * 0.8)
                ca = t * math.pi * 0.5
                fx = bx + math.sin(ca) * size * 0.1 * sm
                fy = size * 0.3 - math.sin(ca) * size * 0.2
                fz = -math.cos(ca) * size * 0.15
                for j in range(fr):
                    a = 2.0 * math.pi * j / fr
                    fv.append((fx + math.cos(a) * r, fy + math.sin(a) * r, fz))
            for i in range(fs):
                for j in range(fr):
                    j2 = (j + 1) % fr
                    ff.append((i * fr + j, i * fr + j2,
                               (i + 1) * fr + j2, (i + 1) * fr + j))
            ff.append(tuple(range(fr - 1, -1, -1)))
            parts.append((fv, ff))
        else:
            jv, jf = _make_beveled_box(sm * size * 0.15, size * 0.1, -size * 0.05,
                                       size * 0.06, size * 0.2, size * 0.03,
                                       bevel=size * 0.01)
            parts.append((jv, jf))
            for ti in range(3):
                t = (ti + 0.5) / 3
                ty = size * 0.1 - size * 0.2 + t * size * 0.4
                tv2, tf2 = _make_cone(sm * size * 0.08, ty, -size * 0.05,
                                      size * 0.01, size * 0.03, segments=4)
                parts.append((tv2, tf2))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Mandible_{style}", verts, faces,
                        style=style, category="monster_part")


def generate_carapace_mesh(
    width: float = 0.5, length: float = 0.8, segments: int = 6,
) -> MeshSpec:
    """Generate an armored carapace/shell plate mesh.

    Args:
        width: Width of the shell.
        length: Length of the shell.
        segments: Number of segmented plates.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = max(3, segments)
    rs = 12
    for si in range(segs):
        t0 = si / segs
        seg_y0 = -length / 2 + t0 * length
        seg_y1 = -length / 2 + (si + 1) / segs * length
        seg_w = width * (0.8 + 0.2 * math.sin(t0 * math.pi))
        dh = width * 0.15
        pv: list[tuple[float, float, float]] = []
        pf: list[tuple[int, ...]] = []
        ndr = 4
        for di in range(ndr + 1):
            dt = di / ndr
            dr = seg_w / 2 * math.cos(dt * math.pi * 0.5)
            dz = dh * math.sin(dt * math.pi * 0.5)
            y = seg_y0 + (seg_y1 - seg_y0) * 0.5
            for j in range(rs):
                a = math.pi * j / (rs - 1)
                pv.append((math.cos(a) * dr,
                           y + (seg_y1 - seg_y0) * 0.3 * (dt - 0.5),
                           dz + math.sin(a) * dr * 0.1))
        for di in range(ndr):
            for j in range(rs - 1):
                pf.append((di * rs + j, di * rs + j + 1,
                           (di + 1) * rs + j + 1, (di + 1) * rs + j))
        parts.append((pv, pf))
    rv, rf = _make_tapered_cylinder(0, -length / 2, 0, width / 2, width / 2 * 0.9,
                                    length, segments=rs, rings=segs,
                                    cap_top=False, cap_bottom=False)
    parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Carapace", verts, faces, segments=segs, category="monster_part")


def generate_spine_ridge_mesh(
    count: int = 8, length: float = 0.12, curve: float = 0.3,
) -> MeshSpec:
    """Generate dorsal spines/fins along a creature's back.

    Args:
        count: Number of spines.
        length: Length of each spine.
        curve: How much spines curve backward.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    count = max(3, min(20, count))
    total_span = count * length * 0.6
    for i in range(count):
        t = i / max(count - 1, 1)
        sx = -total_span / 2 + t * total_span
        spine_h = length * (0.6 + 0.4 * math.sin(t * math.pi))
        sr = length * 0.08
        sv, sf = _make_tapered_cylinder(sx, 0, 0, sr, sr * 0.15, spine_h,
                                        segments=4, rings=3, cap_top=True, cap_bottom=True)
        curved = [(v[0] - curve * (v[1] / spine_h) ** 2 * spine_h * 0.3, v[1], v[2])
                  for v in sv]
        parts.append((curved, sf))
        if i < count - 1:
            nx = -total_span / 2 + (t + 1.0 / max(count - 1, 1)) * total_span
            wh = spine_h * 0.4
            parts.append(([(sx, 0, 0), (sx, wh, 0), (nx, wh * 0.8, 0), (nx, 0, 0)],
                          [(0, 1, 2, 3)]))
    verts, faces = _merge_meshes(*parts)
    return _make_result("SpineRidge", verts, faces, count=count, category="monster_part")


def generate_fang_mesh(
    count: int = 4, length: float = 0.08, curve: float = 0.3,
) -> MeshSpec:
    """Generate a teeth/fangs arrangement.

    Args:
        count: Number of fangs.
        length: Length of each fang.
        curve: Curvature of the fangs.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    count = max(2, min(16, count))
    rs = 6
    gum_r = count * length * 0.3
    gv, gf = _make_torus_ring(0, 0, 0, gum_r, length * 0.08,
                              major_segments=count * 2, minor_segments=4)
    parts.append((gv, gf))
    for i in range(count):
        ang = 2.0 * math.pi * i / count
        fx = math.cos(ang) * gum_r
        fz = math.sin(ang) * gum_r
        sm = 1.0 + 0.3 * math.cos(ang)
        fh = length * sm
        fv: list[tuple[float, float, float]] = []
        ff: list[tuple[int, ...]] = []
        for si in range(6):
            t = si / 5
            r = length * 0.025 * (1.0 - t * 0.8) * sm
            co = curve * t * t * fh * 0.3
            cy = -t * fh
            lfx = fx + math.cos(ang) * co
            lfz = fz + math.sin(ang) * co
            for j in range(rs):
                a = 2.0 * math.pi * j / rs
                fv.append((lfx + math.cos(a) * r, cy, lfz + math.sin(a) * r))
        for si in range(5):
            for j in range(rs):
                j2 = (j + 1) % rs
                ff.append((si * rs + j, si * rs + j2,
                           (si + 1) * rs + j2, (si + 1) * rs + j))
        ff.append(tuple(range(rs)))
        ff.append(tuple(5 * rs + j for j in range(rs - 1, -1, -1)))
        parts.append((fv, ff))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Fangs", verts, faces, count=count, category="monster_part")


# =========================================================================
# CATEGORY: MONSTER BASE BODIES
# =========================================================================


def generate_humanoid_beast_body(
    height: float = 2.0, bulk: float = 1.0, hunch: float = 0.3,
) -> MeshSpec:
    """Generate a hunched beast-man torso and limbs base mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10
    th = height * 0.4
    trb = height * 0.12 * bulk
    trt = height * 0.15 * bulk
    tv, tf = _make_tapered_cylinder(0, height * 0.35, 0, trb, trt, th,
                                    segments=segs, rings=4, cap_top=True, cap_bottom=True)
    parts.append(([(v[0], v[1], v[2] - hunch * max(0, (v[1] - height * 0.35) / th) ** 2
                    * height * 0.15) for v in tv], tf))
    hz = -hunch * height * 0.12
    hv, hf = _make_sphere(0, height * 0.8, hz, height * 0.08 * bulk, rings=6, sectors=8)
    parts.append((hv, hf))
    nv, nf = _make_tapered_cylinder(0, height * 0.7, hz * 0.5, height * 0.05 * bulk,
                                    height * 0.04 * bulk, height * 0.08, segments=6, rings=1)
    parts.append((nv, nf))
    for sm in [-1.0, 1.0]:
        ax = sm * trt * 1.1
        uv, uf = _make_tapered_cylinder(ax, height * 0.6, -hunch * height * 0.05,
                                        height * 0.05 * bulk, height * 0.04 * bulk,
                                        height * 0.2, segments=6, rings=2)
        parts.append(([(v[0] + sm * (v[1] - height * 0.6) * 0.2,
                        v[1] - abs(v[1] - height * 0.6) * 0.1, v[2]) for v in uv], uf))
        fav, faf = _make_tapered_cylinder(ax + sm * height * 0.06, height * 0.38,
                                          -hunch * height * 0.03, height * 0.04 * bulk,
                                          height * 0.035 * bulk, height * 0.18,
                                          segments=6, rings=2)
        parts.append((fav, faf))
    for sm in [-1.0, 1.0]:
        lx = sm * trb * 0.6
        ulv, ulf = _make_tapered_cylinder(lx, height * 0.15, 0, height * 0.06 * bulk,
                                          height * 0.05 * bulk, height * 0.2,
                                          segments=6, rings=2)
        parts.append((ulv, ulf))
        llv, llf = _make_tapered_cylinder(lx, 0, height * 0.02, height * 0.04 * bulk,
                                          height * 0.05 * bulk, height * 0.17,
                                          segments=6, rings=2)
        parts.append((llv, llf))
    pv, pf = _make_sphere(0, height * 0.35, 0, trb * 0.9, rings=4, sectors=segs)
    parts.append((pv, pf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("HumanoidBeast", verts, faces,
                        bulk=bulk, hunch=hunch, category="monster_body")


def generate_quadruped_body(
    length: float = 1.5, height: float = 1.0, bulk: float = 1.0,
) -> MeshSpec:
    """Generate a four-legged beast base mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10
    br = height * 0.2 * bulk
    bv, bf = _make_tapered_cylinder(0, height * 0.6, -length * 0.1, br * 0.85, br,
                                    length * 0.6, segments=segs, rings=4,
                                    cap_top=True, cap_bottom=True)
    parts.append(([(v[0], height * 0.6 + (v[2] + length * 0.1),
                    -length * 0.1 + (v[1] - height * 0.6)) for v in bv], bf))
    hr = height * 0.1 * bulk
    hv, hf = _make_sphere(0, height * 0.7, length * 0.35, hr, rings=6, sectors=8)
    parts.append((hv, hf))
    nv, nf = _make_tapered_cylinder(0, height * 0.55, length * 0.2, br * 0.5,
                                    hr * 0.8, height * 0.2, segments=6, rings=2)
    parts.append((nv, nf))
    for lx, lz in [(-br * 0.6, length * 0.2), (br * 0.6, length * 0.2),
                   (-br * 0.6, -length * 0.25), (br * 0.6, -length * 0.25)]:
        ur = height * 0.05 * bulk
        ulv, ulf = _make_tapered_cylinder(lx, height * 0.3, lz, ur * 1.2, ur,
                                          height * 0.3, segments=6, rings=2)
        parts.append((ulv, ulf))
        llv, llf = _make_tapered_cylinder(lx, 0, lz + height * 0.02, ur * 0.7,
                                          ur * 0.9, height * 0.32, segments=6, rings=2)
        parts.append((llv, llf))
    rv, rf = _make_sphere(0, height * 0.6, length * 0.05, br * 1.05, rings=5, sectors=segs)
    parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Quadruped", verts, faces, bulk=bulk, category="monster_body")


def generate_serpent_body(
    length: float = 3.0, segments: int = 24, thickness: float = 0.15,
) -> MeshSpec:
    """Generate a snake/wyrm body with taper."""
    segs = max(8, segments)
    rs = 10
    bv: list[tuple[float, float, float]] = []
    bfa: list[tuple[int, ...]] = []
    for i in range(segs + 1):
        t = i / segs
        env = math.sin(t * math.pi)
        if t < 0.1:
            env = t / 0.1 * math.sin(0.1 * math.pi)
        r = thickness * max(0.05, env)
        cx = length * 0.05 * math.sin(t * math.pi * 3)
        cy = thickness * 0.3 + r
        cz = t * length - length / 2
        for j in range(rs):
            a = 2.0 * math.pi * j / rs
            bv.append((cx + math.cos(a) * r * 1.1, cy + math.sin(a) * r * 0.85, cz))
    for i in range(segs):
        for j in range(rs):
            j2 = (j + 1) % rs
            bfa.append((i * rs + j, i * rs + j2, (i + 1) * rs + j2, (i + 1) * rs + j))
    bfa.append(tuple(range(rs)))
    bfa.append(tuple(segs * rs + j for j in range(rs - 1, -1, -1)))
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = [(bv, bfa)]
    ns = segs // 3
    for si in range(ns):
        st = (si + 1) / (ns + 1)
        sz = st * length - length / 2
        env = math.sin(st * math.pi)
        if st < 0.1:
            env = st / 0.1 * math.sin(0.1 * math.pi)
        sr = thickness * max(0.05, env)
        sx = length * 0.05 * math.sin(st * math.pi * 3)
        sv, sf = _make_box(sx, sr * 0.05, sz, sr * 0.9, sr * 0.05, length / segs * 0.4)
        parts.append((sv, sf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Serpent", verts, faces, segments=segs, category="monster_body")


def generate_insectoid_body(segments: int = 3, leg_pairs: int = 3) -> MeshSpec:
    """Generate a segmented insect body mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segments = max(2, min(8, segments))
    leg_pairs = max(2, min(6, leg_pairs))
    rs = 8
    tl = 0.3 * segments
    sp: list[tuple[float, float]] = []
    for si in range(segments):
        t = si / max(segments - 1, 1)
        sz = -tl / 2 + t * tl
        sr = tl * (0.08 if si == 0 else (0.15 if si == segments - 1 else 0.1))
        sp.append((sz, sr))
        sv, sf = _make_sphere(0, sr, sz, sr, rings=5, sectors=rs)
        parts.append((sv, sf))
    for si in range(segments - 1):
        z0, r0 = sp[si]
        z1, r1 = sp[si + 1]
        cr = min(r0, r1) * 0.5
        cl = abs(z1 - z0) - r0 - r1
        if cl > 0:
            cv, cf = _make_tapered_cylinder(0, cr, z0 + r0, cr, cr * 0.8, cl,
                                            segments=6, rings=1)
            parts.append(([(v[0], cr + (v[2] - z0 - r0) * 0.1,
                            z0 + r0 + (v[1] - cr)) for v in cv], cf))
    tz = sp[min(1, segments - 1)][0]
    tr = sp[min(1, segments - 1)][1]
    ls = tl * 0.15
    for li in range(leg_pairs):
        for sm in [-1.0, 1.0]:
            lz = tz - ls * (leg_pairs - 1) / 2 + li * ls
            lx = sm * tr * 0.8
            ulv, ulf = _make_tapered_cylinder(lx, tr * 0.3, lz, tr * 0.08, tr * 0.06,
                                              tl * 0.15, segments=4, rings=1)
            parts.append(([(v[0] + sm * abs(v[1] - tr * 0.3) * 0.8,
                            v[1] - abs(v[1] - tr * 0.3) * 0.3, v[2]) for v in ulv], ulf))
            llv, llf = _make_tapered_cylinder(lx + sm * tl * 0.105, 0, lz, tr * 0.05,
                                              tr * 0.03, tr * 0.5, segments=4, rings=1)
            parts.append((llv, llf))
    hz, hr2 = sp[0]
    for sm in [-1.0, 1.0]:
        av, af = _make_tapered_cylinder(sm * hr2 * 0.3, hr2 * 1.5, hz + hr2 * 0.5,
                                        hr2 * 0.05, hr2 * 0.015, tl * 0.2,
                                        segments=4, rings=2)
        parts.append((av, af))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Insectoid", verts, faces,
                        segments=segments, leg_pairs=leg_pairs, category="monster_body")


def generate_skeletal_frame(height: float = 1.8, bone_thickness: float = 0.02) -> MeshSpec:
    """Generate an undead skeleton base mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    br = bone_thickness
    segs = 6
    sv, sf = _make_tapered_cylinder(0, height * 0.25, 0, br * 1.2, br * 0.8,
                                    height * 0.45, segments=segs, rings=6)
    parts.append((sv, sf))
    for vi in range(8):
        vv, vf = _make_sphere(0, height * 0.25 + vi / 8 * height * 0.45, br * 1.5,
                              br * 1.8, rings=3, sectors=4)
        parts.append((vv, vf))
    sv2, sf2 = _make_sphere(0, height * 0.85, 0, height * 0.07, rings=6, sectors=8)
    parts.append((sv2, sf2))
    jv, jf = _make_box(0, height * 0.79, height * 0.02, height * 0.04,
                       height * 0.015, height * 0.03)
    parts.append((jv, jf))
    for ri in range(6):
        rib_r = height * 0.1 * (1.0 - abs(ri - 3) / 6 * 0.6)
        rv, rf = _make_torus_ring(0, height * 0.45 + ri * height * 0.04, 0,
                                  rib_r, br * 0.8, major_segments=8, minor_segments=3)
        parts.append((rv, rf))
    pv, pf = _make_torus_ring(0, height * 0.25, 0, height * 0.08, br * 1.5,
                              major_segments=8, minor_segments=4)
    parts.append((pv, pf))
    for sm in [-1.0, 1.0]:
        ax = sm * height * 0.12
        hv2, hf2 = _make_tapered_cylinder(ax, height * 0.5, 0, br, br * 0.8,
                                          height * 0.18, segments=segs, rings=2)
        parts.append(([(v[0] + sm * abs(v[1] - height * 0.65) * 0.15,
                        v[1] - abs(v[1] - height * 0.65) * 0.1, v[2]) for v in hv2], hf2))
        kv, kf = _make_sphere(ax, height * 0.5, 0, br * 2, rings=3, sectors=4)
        parts.append((kv, kf))
        fav, faf = _make_tapered_cylinder(ax + sm * height * 0.03, height * 0.32, 0,
                                          br * 0.9, br * 0.6, height * 0.17,
                                          segments=segs, rings=2)
        parts.append((fav, faf))
        hv3, hf3 = _make_box(ax + sm * height * 0.04, height * 0.3, 0,
                             height * 0.02, height * 0.025, br * 0.8)
        parts.append((hv3, hf3))
    for sm in [-1.0, 1.0]:
        lx = sm * height * 0.06
        fv2, ff2 = _make_tapered_cylinder(lx, height * 0.05, 0, br * 1.1, br * 0.9,
                                          height * 0.22, segments=segs, rings=2)
        parts.append((fv2, ff2))
        kv2, kf2 = _make_sphere(lx, height * 0.27, 0, br * 2, rings=3, sectors=4)
        parts.append((kv2, kf2))
        tv2, tf2 = _make_tapered_cylinder(lx, 0, height * 0.01, br * 0.8, br,
                                          height * 0.2, segments=segs, rings=2)
        parts.append((tv2, tf2))
        ftv, ftf = _make_box(lx, height * 0.01, height * 0.03,
                             height * 0.025, height * 0.01, height * 0.04)
        parts.append((ftv, ftf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("SkeletalFrame", verts, faces,
                        bone_thickness=bone_thickness, category="monster_body")


def generate_golem_body(height: float = 2.5, material_style: str = "stone_rough") -> MeshSpec:
    """Generate a golem body mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    tw, th2, td = height * 0.2, height * 0.3, height * 0.15
    if material_style == "stone_rough":
        tv, tf = _make_beveled_box(0, height * 0.45, 0, tw, th2 / 2, td,
                                   bevel=height * 0.02)
        parts.append((tv, tf))
        for ci in range(4):
            cv, cf = _make_box((ci % 2 - 0.5) * tw * 0.8,
                               height * 0.35 + ci * th2 * 0.2, td * 0.5,
                               tw * 0.15, th2 * 0.08, td * 0.1)
            parts.append((cv, cf))
    elif material_style == "crystal":
        tv, tf = _make_beveled_box(0, height * 0.45, 0, tw * 0.9, th2 / 2,
                                   td * 0.9, bevel=height * 0.01)
        parts.append((tv, tf))
        for ci in range(5):
            a = ci * math.pi * 2 / 5
            cv, cf = _make_cone(math.cos(a) * tw * 0.7, height * 0.4 + ci * th2 * 0.12,
                                math.sin(a) * td * 0.7, height * 0.02, height * 0.08,
                                segments=5)
            parts.append((cv, cf))
    elif material_style == "iron_plates":
        tv, tf = _make_beveled_box(0, height * 0.45, 0, tw, th2 / 2, td,
                                   bevel=height * 0.015)
        parts.append((tv, tf))
        for pi in range(3):
            pv, pf = _make_box(0, height * 0.35 + pi * th2 * 0.3, td * 1.01,
                               tw * 0.95, height * 0.005, height * 0.005)
            parts.append((pv, pf))
        for ri in range(6):
            rv, rf = _make_sphere((ri % 2 - 0.5) * tw * 1.4,
                                  height * 0.35 + (ri // 2) * th2 * 0.25,
                                  td * 1.01, height * 0.008, rings=3, sectors=4)
            parts.append((rv, rf))
    else:  # wood_twisted
        tv, tf = _make_tapered_cylinder(0, height * 0.3, 0, tw * 0.8, tw * 0.6, th2,
                                        segments=segs, rings=5)
        twisted = [(v[0] * math.cos(((v[1] - height * 0.3) / th2 if th2 > 0 else 0) * 0.5) -
                    v[2] * math.sin(((v[1] - height * 0.3) / th2 if th2 > 0 else 0) * 0.5),
                    v[1],
                    v[0] * math.sin(((v[1] - height * 0.3) / th2 if th2 > 0 else 0) * 0.5) +
                    v[2] * math.cos(((v[1] - height * 0.3) / th2 if th2 > 0 else 0) * 0.5))
                   for v in tv]
        parts.append((twisted, tf))
        for bi in range(3):
            ba = bi * math.pi * 2 / 3
            bv, bf = _make_tapered_cylinder(math.cos(ba) * tw * 0.6,
                                            height * 0.35 + bi * height * 0.1,
                                            math.sin(ba) * td * 0.6,
                                            height * 0.02, height * 0.005,
                                            height * 0.1, segments=4, rings=2)
            parts.append((bv, bf))
    hv, hf = _make_sphere(0, height * 0.78, 0, height * 0.06, rings=5, sectors=segs)
    parts.append((hv, hf))
    for sm in [-1.0, 1.0]:
        ax = sm * tw * 1.2
        shv, shf = _make_sphere(ax, height * 0.65, 0, height * 0.06, rings=4, sectors=6)
        parts.append((shv, shf))
        uav, uaf = _make_tapered_cylinder(ax, height * 0.4, 0, height * 0.055,
                                          height * 0.045, height * 0.22,
                                          segments=segs, rings=2)
        parts.append((uav, uaf))
        fav, faf = _make_tapered_cylinder(ax + sm * height * 0.02, height * 0.2, 0,
                                          height * 0.05, height * 0.06, height * 0.2,
                                          segments=segs, rings=2)
        parts.append((fav, faf))
        ftv, ftf = _make_sphere(ax + sm * height * 0.02, height * 0.18, 0,
                                height * 0.06, rings=4, sectors=6)
        parts.append((ftv, ftf))
    for sm in [-1.0, 1.0]:
        lx = sm * tw * 0.5
        ulv, ulf = _make_tapered_cylinder(lx, height * 0.05, 0, height * 0.07,
                                          height * 0.06, height * 0.25,
                                          segments=segs, rings=2)
        parts.append((ulv, ulf))
        fv2, ff2 = _make_box(lx, height * 0.02, height * 0.02,
                             height * 0.06, height * 0.02, height * 0.07)
        parts.append((fv2, ff2))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Golem_{material_style}", verts, faces,
                        material_style=material_style, category="monster_body")


# =========================================================================
# CATEGORY: PROJECTILES & COMBAT OBJECTS
# =========================================================================


def generate_arrow_mesh(shaft_length: float = 0.7, head_style: str = "broadhead") -> MeshSpec:
    """Generate an arrow mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.008
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=6, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(3):
        a = fi * math.pi * 2 / 3
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 4, shaft_length * 0.06, math.sin(a) * sr * 4),
                       (math.cos(a) * sr * 3, shaft_length * 0.14, math.sin(a) * sr * 3),
                       (math.cos(a) * sr, shaft_length * 0.12, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    nv, nf = _make_cylinder(0, 0, 0, sr * 1.3, shaft_length * 0.015, segments=6)
    parts.append((nv, nf))
    hy = shaft_length
    if head_style == "broadhead":
        hh, hw = shaft_length * 0.06, sr * 6
        dv = [(0, hy, 0), (hw, hy + hh * 0.4, 0), (0, hy + hh, 0), (-hw, hy + hh * 0.4, 0)]
        parts.append((dv, [(0, 1, 2, 3)]))
        parts.append(([(v[0], v[1], sr * 0.5) for v in dv], [(3, 2, 1, 0)]))
    elif head_style == "bodkin":
        hv, hf = _make_cone(0, hy, 0, sr * 2, shaft_length * 0.08, segments=4)
        parts.append((hv, hf))
    elif head_style == "barbed":
        hv, hf = _make_cone(0, hy, 0, sr * 3, shaft_length * 0.05, segments=4)
        parts.append((hv, hf))
        for bi in range(2):
            ba = bi * math.pi
            bx, bz = math.cos(ba) * sr * 2, math.sin(ba) * sr * 2
            parts.append(([(bx, hy + shaft_length * 0.02, bz),
                           (bx * 1.8, hy - shaft_length * 0.01, bz * 1.8),
                           (bx * 0.5, hy - shaft_length * 0.005, bz * 0.5)], [(0, 1, 2)]))
    else:  # fire
        hv, hf = _make_cone(0, hy, 0, sr * 2.5, shaft_length * 0.05, segments=6)
        parts.append((hv, hf))
        fv, ff = _make_sphere(0, hy - shaft_length * 0.01, 0, sr * 3.5, rings=4, sectors=6)
        parts.append((fv, ff))
        for ri in range(2):
            rv, rf = _make_torus_ring(0, hy - shaft_length * 0.02 + ri * shaft_length * 0.02,
                                      0, sr * 3.5, sr * 0.5, major_segments=6, minor_segments=3)
            parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Arrow_{head_style}", verts, faces,
                        head_style=head_style, category="projectile")


def generate_magic_orb_mesh(radius: float = 0.15, style: str = "smooth") -> MeshSpec:
    """Generate a magic projectile orb mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    if style == "smooth":
        sv, sf = _make_sphere(0, 0, 0, radius, rings=8, sectors=12)
        parts.append((sv, sf))
        iv, ifa = _make_sphere(0, 0, 0, radius * 0.6, rings=5, sectors=8)
        parts.append((iv, ifa))
    elif style == "crackling":
        sv, sf = _make_sphere(0, 0, 0, radius * 0.8, rings=6, sectors=10)
        parts.append((sv, sf))
        for si in range(8):
            phi = math.acos(1 - 2 * (si + 0.5) / 8)
            theta = math.pi * (1 + 5**0.5) * si
            cv, cf = _make_cone(math.sin(phi) * math.cos(theta) * radius,
                                math.cos(phi) * radius,
                                math.sin(phi) * math.sin(theta) * radius,
                                radius * 0.06,
                                radius * (0.3 + 0.4 * abs(math.sin(si * 1.7))), segments=4)
            parts.append((cv, cf))
    elif style == "void_rift":
        sv, sf = _make_sphere(0, 0, 0, radius, rings=6, sectors=8)
        parts.append((sv, sf))
        iv, ifa = _make_sphere(0, 0, 0, radius * 0.5, rings=5, sectors=6)
        parts.append((iv, ifa))
        for di in range(6):
            da = di * math.pi * 2 / 6
            dv, df = _make_box(math.cos(da) * radius * 1.3, math.sin(da * 2) * radius * 0.3,
                               math.sin(da) * radius * 1.3,
                               radius * 0.06, radius * 0.08, radius * 0.05)
            parts.append((dv, df))
    else:  # flame_core
        sv, sf = _make_sphere(0, 0, 0, radius * 0.5, rings=6, sectors=8)
        parts.append((sv, sf))
        for fi in range(10):
            phi = math.acos(1 - 2 * (fi + 0.5) / 10)
            theta = math.pi * (1 + 5**0.5) * fi
            fv, ff = _make_cone(math.sin(phi) * math.cos(theta) * radius * 0.5,
                                math.cos(phi) * radius * 0.5,
                                math.sin(phi) * math.sin(theta) * radius * 0.5,
                                radius * 0.08,
                                radius * (0.5 + 0.3 * abs(math.sin(fi * 2.3))), segments=4)
            parts.append((fv, ff))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MagicOrb_{style}", verts, faces, style=style, category="projectile")


def generate_throwing_knife_mesh(blade_length: float = 0.2) -> MeshSpec:
    """Generate a balanced throwing blade mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    bw, bd, hl = blade_length * 0.15, blade_length * 0.03, blade_length * 0.6
    bverts = [(0, blade_length, 0), (-bw, blade_length * 0.65, bd),
              (bw, blade_length * 0.65, bd), (-bw, blade_length * 0.65, -bd),
              (bw, blade_length * 0.65, -bd), (-bw * 0.5, 0, bd * 0.8),
              (bw * 0.5, 0, bd * 0.8), (-bw * 0.5, 0, -bd * 0.8), (bw * 0.5, 0, -bd * 0.8)]
    parts.append((bverts, [(0, 1, 2), (0, 4, 3), (0, 2, 4), (0, 3, 1),
                           (1, 5, 6, 2), (4, 8, 7, 3), (2, 6, 8, 4), (1, 3, 7, 5),
                           (5, 7, 8, 6)]))
    hv, hf = _make_tapered_cylinder(0, -hl, 0, bw * 0.25, bw * 0.2, hl, segments=6, rings=2)
    parts.append((hv, hf))
    gv, gf = _make_box(0, 0, 0, bw * 0.7, bd * 1.5, bd * 1.5)
    parts.append((gv, gf))
    pv, pf = _make_sphere(0, -hl, 0, bw * 0.3, rings=4, sectors=6)
    parts.append((pv, pf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("ThrowingKnife", verts, faces, category="projectile")


def generate_bomb_mesh(size: float = 0.1, style: str = "round_fused") -> MeshSpec:
    """Generate a throwable bomb/explosive mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    if style == "round_fused":
        sv, sf = _make_sphere(0, size, 0, size, rings=8, sectors=10)
        parts.append((sv, sf))
        cv, cf = _make_cylinder(0, size * 2, 0, size * 0.15, size * 0.1, segments=6)
        parts.append((cv, cf))
        for fi in range(6):
            t = fi / 6
            fv, ff = _make_cylinder(math.sin(t * math.pi * 2) * size * 0.08,
                                    size * 2.1 + t * size * 0.5,
                                    math.cos(t * math.pi * 2) * size * 0.08,
                                    size * 0.02, size * 0.08, segments=4, cap_top=(fi == 5))
            parts.append((fv, ff))
        bv, bf = _make_torus_ring(0, size, 0, size * 1.02, size * 0.03,
                                  major_segments=10, minor_segments=4)
        parts.append((bv, bf))
    elif style == "flask_potion":
        profile = [(size * 0.6, 0), (size * 0.8, size * 0.3), (size * 0.8, size * 0.8),
                   (size * 0.6, size), (size * 0.2, size * 1.2),
                   (size * 0.2, size * 1.5), (size * 0.25, size * 1.55)]
        lv, lf = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
        parts.append((lv, lf))
        cv, cf = _make_cylinder(0, size * 1.55, 0, size * 0.18, size * 0.15, segments=6)
        parts.append((cv, cf))
    else:  # crystal_charge
        cv, cf = _make_tapered_cylinder(0, 0, 0, size * 0.3, size * 0.05, size * 2,
                                        segments=6, rings=1)
        parts.append((cv, cf))
        for ci in range(5):
            a = ci * math.pi * 2 / 5
            xv, xf = _make_tapered_cylinder(math.cos(a) * size * 0.4, size * 0.2,
                                            math.sin(a) * size * 0.4, size * 0.15,
                                            size * 0.02,
                                            size * (1.2 + 0.4 * math.sin(ci * 1.7)),
                                            segments=5, rings=1)
            parts.append((xv, xf))
        rv, rf = _make_torus_ring(0, size * 0.3, 0, size * 0.5, size * 0.06,
                                  major_segments=8, minor_segments=4)
        parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bomb_{style}", verts, faces, style=style, category="projectile")


# =========================================================================
# CATEGORY: ARMOR PIECES
# =========================================================================


def generate_helmet_mesh(style: str = "open_face") -> MeshSpec:
    """Generate a helmet/headgear mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hr = 0.11
    segs = 10
    if style == "open_face":
        profile = [(hr * 1.05, 0), (hr * 1.08, hr * 0.3), (hr * 1.05, hr * 0.7),
                   (hr * 0.8, hr), (hr * 0.3, hr * 1.15)]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((hv, hf))
        nv, nf = _make_box(0, hr * 0.35, hr * 1.05, hr * 0.05, hr * 0.3, hr * 0.02)
        parts.append((nv, nf))
        rv, rf = _make_torus_ring(0, hr * 0.5, 0, hr * 1.08, hr * 0.03,
                                  major_segments=segs, minor_segments=4)
        parts.append((rv, rf))
    elif style == "full_helm":
        profile = [(hr * 0.9, -hr * 0.2), (hr * 1.1, 0), (hr * 1.12, hr * 0.4),
                   (hr * 1.08, hr * 0.8), (hr * 0.7, hr * 1.1), (hr * 0.2, hr * 1.2)]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((hv, hf))
        vv = [(-hr * 0.4, hr * 0.35, hr * 1.12), (hr * 0.4, hr * 0.35, hr * 1.12),
              (hr * 0.4, hr * 0.45, hr * 1.12), (-hr * 0.4, hr * 0.45, hr * 1.12)]
        vb = [(v[0], v[1], v[2] + hr * 0.02) for v in vv]
        parts.append((vv + vb, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (2, 6, 7, 3)]))
        for ci in range(5):
            cv, cf = _make_box(0, hr * 0.8 + ci * hr * 0.08, -hr * 0.3 + ci * hr * 0.15,
                               hr * 0.02, hr * 0.04, hr * 0.03)
            parts.append((cv, cf))
    elif style == "crown":
        bv, bf = _make_torus_ring(0, hr * 0.3, 0, hr * 1.05, hr * 0.08,
                                  major_segments=segs, minor_segments=4)
        parts.append((bv, bf))
        for pi in range(5):
            pa = pi * math.pi * 2 / 5
            px, pz = math.cos(pa) * hr * 1.05, math.sin(pa) * hr * 1.05
            pv, pf = _make_box(px, hr * 0.4, pz, hr * 0.04, hr * 0.125, hr * 0.04)
            parts.append((pv, pf))
            jv, jf = _make_sphere(px, hr * 0.5, pz, hr * 0.02, rings=3, sectors=4)
            parts.append((jv, jf))
    elif style == "hood_chainmail":
        profile = [(hr * 0.95, -hr * 0.3), (hr * 1.05, 0), (hr * 1.08, hr * 0.5),
                   (hr, hr * 0.9), (hr * 0.6, hr * 1.1)]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=False, close_top=True)
        parts.append((hv, hf))
        fv, ff = _make_torus_ring(0, hr * 0.4, hr * 0.3, hr * 0.45, hr * 0.025,
                                  major_segments=8, minor_segments=3)
        parts.append((fv, ff))
    else:  # horned_viking
        profile = [(hr, 0), (hr * 1.1, hr * 0.3), (hr * 1.08, hr * 0.7),
                   (hr * 0.8, hr), (hr * 0.3, hr * 1.1)]
        hv, hf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((hv, hf))
        nv, nf = _make_box(0, hr * 0.2, hr * 1.08, hr * 0.04, hr * 0.25, hr * 0.015)
        parts.append((nv, nf))
        for sm in [-1.0, 1.0]:
            hs, hring = 6, 6
            hvl: list[tuple[float, float, float]] = []
            hfl: list[tuple[int, ...]] = []
            for hi in range(hs + 1):
                ht = hi / hs
                r = hr * 0.04 * (1.0 - ht * 0.7)
                ha = ht * math.pi * 0.4
                hx = sm * (hr * 1.05 + math.sin(ha) * hr * 0.5)
                hy = hr * 0.7 + math.cos(ha) * hr * 0.3
                for j in range(hring):
                    a = 2.0 * math.pi * j / hring
                    hvl.append((hx + math.cos(a) * r, hy + math.sin(a) * r, 0.0))
            for hi in range(hs):
                for j in range(hring):
                    j2 = (j + 1) % hring
                    hfl.append((hi * hring + j, hi * hring + j2,
                                (hi + 1) * hring + j2, (hi + 1) * hring + j))
            hfl.append(tuple(range(hring - 1, -1, -1)))
            hfl.append(tuple(hs * hring + j for j in range(hring)))
            parts.append((hvl, hfl))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Helmet_{style}", verts, faces, style=style, category="armor")


def generate_pauldron_mesh(style: str = "plate_smooth", side: str = "left") -> MeshSpec:
    """Generate a shoulder armor pauldron mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    pr = 0.15
    sm = -1.0 if side == "left" else 1.0
    segs = 8
    if style == "plate_smooth":
        profile = [(pr, 0), (pr * 1.1, pr * 0.3), (pr * 0.9, pr * 0.6), (pr * 0.5, pr * 0.8)]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append(([(v[0] + sm * 0.15, v[1], v[2]) for v in pv], pf))
        rv, rf = _make_torus_ring(sm * 0.15, 0, 0, pr * 1.02, pr * 0.02,
                                  major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
    elif style == "plate_spiked":
        profile = [(pr, 0), (pr * 1.05, pr * 0.3), (pr * 0.85, pr * 0.6), (pr * 0.4, pr * 0.75)]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append(([(v[0] + sm * 0.15, v[1], v[2]) for v in pv], pf))
        for si in range(3):
            sa = (si + 0.5) * math.pi * 2 / 3
            sv2, sf2 = _make_cone(sm * 0.15 + math.cos(sa) * pr * 0.8, pr * 0.4,
                                  math.sin(sa) * pr * 0.8, pr * 0.06, pr * 0.4, segments=4)
            parts.append((sv2, sf2))
    else:  # leather_layered
        for li in range(4):
            lr = pr * (1.0 - li * 0.12)
            lv, lf = _make_box(sm * 0.15, li * pr * 0.15, 0, lr * 0.8, pr * 0.04, lr * 0.6)
            parts.append((lv, lf))
        sv2, sf2 = _make_box(sm * 0.08, pr * 0.3, 0, pr * 0.3, pr * 0.015, pr * 0.05)
        parts.append((sv2, sf2))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Pauldron_{style}_{side}", verts, faces,
                        style=style, side=side, category="armor")


def generate_gauntlet_mesh(style: str = "plate_fingers") -> MeshSpec:
    """Generate a gauntlet/glove armor mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hw, hh, fl = 0.045, 0.12, 0.06
    if style == "plate_fingers":
        hv, hf = _make_beveled_box(0, hh / 2, 0, hw, hh / 2, hw * 0.4, bevel=0.003)
        parts.append((hv, hf))
        wv, wf = _make_tapered_cylinder(0, 0, 0, hw * 1.1, hw * 0.9, hh * 0.3, segments=6, rings=2)
        parts.append((wv, wf))
        for fi in range(4):
            fx = -hw * 0.6 + fi * hw * 0.4
            for si in range(3):
                sy = hh + si * fl / 3
                sh = fl / 3 * 0.85
                fv, ff = _make_box(fx, sy + sh / 2, 0, hw * 0.12, sh / 2, hw * 0.25)
                parts.append((fv, ff))
        tv, tf = _make_tapered_cylinder(-hw * 0.8, hh * 0.5, hw * 0.2, hw * 0.1, hw * 0.07,
                                        fl * 0.7, segments=4, rings=2)
        parts.append((tv, tf))
    elif style == "chainmail_glove":
        gv, gf = _make_tapered_cylinder(0, 0, 0, hw, hw * 0.85, hh, segments=8, rings=3)
        parts.append((gv, gf))
        for fi in range(4):
            fv, ff = _make_tapered_cylinder(-hw * 0.5 + fi * hw * 0.35, hh, 0,
                                            hw * 0.1, hw * 0.07, fl, segments=4, rings=2)
            parts.append((fv, ff))
        tv, tf = _make_tapered_cylinder(-hw * 0.7, hh * 0.4, hw * 0.15, hw * 0.09,
                                        hw * 0.06, fl * 0.6, segments=4, rings=1)
        parts.append((tv, tf))
        wv, wf = _make_torus_ring(0, hh * 0.05, 0, hw * 1.05, hw * 0.04,
                                  major_segments=8, minor_segments=3)
        parts.append((wv, wf))
    else:  # claw_tipped
        hv, hf = _make_beveled_box(0, hh / 2, 0, hw, hh / 2, hw * 0.4, bevel=0.003)
        parts.append((hv, hf))
        wv, wf = _make_tapered_cylinder(0, 0, 0, hw * 1.2, hw, hh * 0.25, segments=6, rings=1)
        parts.append((wv, wf))
        for fi in range(4):
            fx = -hw * 0.6 + fi * hw * 0.4
            fv, ff = _make_cylinder(fx, hh, 0, hw * 0.1, fl * 0.4, segments=4,
                                    cap_bottom=True, cap_top=False)
            parts.append((fv, ff))
            cv, cf = _make_cone(fx, hh + fl * 0.4, 0, hw * 0.08, fl * 1.2, segments=4)
            parts.append((cv, cf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Gauntlet_{style}", verts, faces, style=style, category="armor")


def generate_greave_mesh(style: str = "plate_shin") -> MeshSpec:
    """Generate a leg armor greave mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr, sh, segs = 0.05, 0.35, 8
    if style == "plate_shin":
        profile = [(sr * 1.15, 0), (sr * 1.2, sh * 0.1), (sr * 1.15, sh * 0.5),
                   (sr * 1.1, sh * 0.9), (sr, sh)]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((pv, pf))
        kv, kf = _make_sphere(0, sh, sr * 0.5, sr * 0.6, rings=4, sectors=6)
        parts.append((kv, kf))
        for ri in range(3):
            rv, rf = _make_torus_ring(0, sh * 0.2 + ri * sh * 0.25, 0, sr * 1.18, sr * 0.02,
                                      major_segments=segs, minor_segments=3)
            parts.append((rv, rf))
    elif style == "leather_wrapped":
        sv, sf = _make_tapered_cylinder(0, 0, 0, sr * 0.95, sr * 1.05, sh,
                                        segments=segs, rings=3)
        parts.append((sv, sf))
        for wi in range(5):
            wv, wf = _make_torus_ring(0, wi * sh / 5 + sh * 0.05, 0, sr * 1.05, sr * 0.04,
                                      major_segments=segs, minor_segments=3)
            parts.append((wv, wf))
        bv, bf = _make_box(sr * 0.8, sh * 0.5, 0, sr * 0.15, sr * 0.15, sr * 0.08)
        parts.append((bv, bf))
    else:  # bone_strapped
        sv, sf = _make_tapered_cylinder(0, 0, 0, sr, sr * 0.9, sh, segments=segs, rings=2)
        parts.append((sv, sf))
        for bi in range(3):
            bv, bf = _make_beveled_box(0, bi * sh * 0.3 + sh * 0.1, sr * 0.8,
                                       sr * 0.6, sh * 0.12, sr * 0.08, bevel=0.003)
            parts.append((bv, bf))
        for si in range(2):
            sv2, sf2 = _make_torus_ring(0, sh * 0.25 + si * sh * 0.4, 0, sr * 1.1, sr * 0.03,
                                        major_segments=segs, minor_segments=3)
            parts.append((sv2, sf2))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Greave_{style}", verts, faces, style=style, category="armor")


def generate_breastplate_mesh(style: str = "plate_full") -> MeshSpec:
    """Generate a breastplate/chest armor mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    cw, ch, cd, segs = 0.2, 0.3, 0.12, 10
    if style == "plate_full":
        profile = [(cw * 0.9, 0), (cw, ch * 0.2), (cw * 1.05, ch * 0.5),
                   (cw * 0.95, ch * 0.8), (cw * 0.7, ch)]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((pv, pf))
        rv, rf = _make_box(0, ch * 0.5, cw, cw * 0.02, ch * 0.35, cw * 0.01)
        parts.append((rv, rf))
        gv, gf = _make_torus_ring(0, ch, 0, cw * 0.5, cw * 0.04, major_segments=segs, minor_segments=4)
        parts.append((gv, gf))
        wv, wf = _make_torus_ring(0, 0, 0, cw * 0.95, cw * 0.03, major_segments=segs, minor_segments=4)
        parts.append((wv, wf))
    elif style == "chainmail":
        sv, sf = _make_tapered_cylinder(0, 0, 0, cw * 0.95, cw * 0.7, ch, segments=segs, rings=5)
        parts.append((sv, sf))
        cv, cf = _make_torus_ring(0, ch, 0, cw * 0.55, cw * 0.04, major_segments=segs, minor_segments=3)
        parts.append((cv, cf))
        skv, skf = _make_tapered_cylinder(0, -ch * 0.3, 0, cw * 1.05, cw * 0.95, ch * 0.3,
                                          segments=segs, rings=2, cap_bottom=True, cap_top=False)
        parts.append((skv, skf))
    elif style == "leather_studded":
        sv, sf = _make_tapered_cylinder(0, 0, 0, cw * 0.9, cw * 0.7, ch, segments=segs, rings=4)
        parts.append((sv, sf))
        for ri in range(4):
            ry = ch * 0.15 + ri * ch * 0.2
            rr = cw * (0.9 - ri * 0.05)
            for si in range(6):
                sa = si * math.pi * 2 / 6
                stv, stf = _make_sphere(math.cos(sa) * rr, ry, math.sin(sa) * rr,
                                        cw * 0.02, rings=2, sectors=4)
                parts.append((stv, stf))
        for sm in [-1.0, 1.0]:
            sv2, sf2 = _make_box(sm * cw * 0.5, ch * 0.9, 0, cw * 0.06, ch * 0.15, cw * 0.5)
            parts.append((sv2, sf2))
    else:  # bone_ribcage
        spv, spf = _make_tapered_cylinder(0, 0, -cd * 0.8, cw * 0.04, cw * 0.03, ch,
                                          segments=6, rings=3)
        parts.append((spv, spf))
        for ri in range(5):
            rib_r = cw * (0.8 + 0.15 * math.sin(ri / 5 * math.pi))
            rv, rf = _make_torus_ring(0, ch * 0.1 + ri * ch * 0.17, 0, rib_r, cw * 0.02,
                                      major_segments=8, minor_segments=3)
            parts.append((rv, rf))
        for sm in [-1.0, 1.0]:
            bv, bf = _make_box(sm * cw * 0.6, ch * 0.85, 0, cw * 0.2, ch * 0.06, cd * 0.3)
            parts.append((bv, bf))
        stv, stf = _make_box(0, ch * 0.5, cd * 0.7, cw * 0.06, ch * 0.3, cw * 0.02)
        parts.append((stv, stf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Breastplate_{style}", verts, faces, style=style, category="armor")


def generate_shield_mesh(style: str = "round_buckler", size: float = 1.0) -> MeshSpec:
    """Generate a shield mesh."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    base_r, thick, segs = 0.25 * size, 0.02 * size, 12
    if style == "round_buckler":
        profile = [(base_r * 0.85, thick * 0.5), (base_r, 0), (base_r * 0.85, -thick * 0.5)]
        sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((sv, sf))
        bv, bf = _make_sphere(0, 0, thick * 0.5, base_r * 0.2, rings=4, sectors=6)
        parts.append((bv, bf))
        rv, rf = _make_torus_ring(0, 0, 0, base_r, thick * 0.4, major_segments=segs, minor_segments=4)
        parts.append((rv, rf))
    elif style == "kite_pointed":
        sw, sh = base_r * 0.8, base_r * 1.5
        kv = [(0, sh * 0.5, thick * 0.3), (-sw, sh * 0.2, thick * 0.2),
              (-sw * 0.8, -sh * 0.1, thick * 0.1), (0, -sh * 0.5, 0),
              (sw * 0.8, -sh * 0.1, thick * 0.1), (sw, sh * 0.2, thick * 0.2)]
        parts.append((kv, [(0, 1, 2, 3), (0, 3, 4, 5)]))
        kb = [(v[0], v[1], -thick * 0.2) for v in kv]
        parts.append((kb, [(3, 2, 1, 0), (5, 4, 3, 0)]))
        for ei in range(6):
            ei2 = (ei + 1) % 6
            parts.append(([kv[ei], kv[ei2], kb[ei2], kb[ei]], [(0, 1, 2, 3)]))
        bv, bf = _make_sphere(0, sh * 0.1, thick * 0.4, base_r * 0.12, rings=3, sectors=6)
        parts.append((bv, bf))
    elif style == "tower_rectangular":
        sw, sh = base_r, base_r * 2
        bv, bf = _make_beveled_box(0, 0, 0, sw / 2, sh / 2, thick, bevel=thick * 0.5)
        parts.append((bv, bf))
        cv, cf = _make_box(0, 0, -thick, sw * 0.03, sh * 0.4, thick * 0.3)
        parts.append((cv, cf))
        hv, hf = _make_box(0, 0, -thick, sw * 0.35, sh * 0.02, thick * 0.3)
        parts.append((hv, hf))
        rv, rf = _make_torus_ring(0, 0, 0, sw * 0.55, thick * 0.3, major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
        bov, bof = _make_sphere(0, sh * 0.15, thick * 1.2, base_r * 0.1, rings=4, sectors=6)
        parts.append((bov, bof))
    else:  # spiked_boss
        profile = [(base_r * 0.9, thick * 0.3), (base_r, 0), (base_r * 0.9, -thick * 0.3)]
        sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((sv, sf))
        spv, spf = _make_cone(0, 0, thick * 0.5, base_r * 0.1, base_r * 0.5, segments=6)
        parts.append((spv, spf))
        bv, bf = _make_torus_ring(0, 0, thick * 0.3, base_r * 0.15, thick * 0.4,
                                  major_segments=8, minor_segments=4)
        parts.append((bv, bf))
        for ri in range(6):
            ra = ri * math.pi * 2 / 6
            rsv, rsf = _make_cone(math.cos(ra) * base_r * 0.85, 0,
                                  math.sin(ra) * base_r * 0.85 + thick * 0.3,
                                  base_r * 0.04, base_r * 0.15, segments=4)
            parts.append((rsv, rsf))
        rv, rf = _make_torus_ring(0, 0, 0, base_r, thick * 0.35,
                                  major_segments=segs, minor_segments=4)
        parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Shield_{style}", verts, faces, style=style, size=size, category="armor")


# =========================================================================
# EXPANDED SHIELD TYPES (8 new shield variants)
# =========================================================================


def generate_heater_shield_mesh(size: float = 1.0) -> MeshSpec:
    """Generate a classic medieval heater shield (inverted triangle top)."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sw, sh, thick = 0.25 * size, 0.40 * size, 0.02 * size
    segs = 10
    front: list[tuple[float, float, float]] = [
        (-sw, sh * 0.5, thick * 0.3), (sw, sh * 0.5, thick * 0.3),
        (sw, sh * 0.1, thick * 0.2), (sw * 0.5, -sh * 0.2, thick * 0.1),
        (0, -sh * 0.5, 0), (-sw * 0.5, -sh * 0.2, thick * 0.1),
        (-sw, sh * 0.1, thick * 0.2),
    ]
    back = [(v[0], v[1], -thick * 0.2) for v in front]
    parts.append((front, [(0, 1, 2, 6), (6, 2, 3, 5), (5, 3, 4)]))
    parts.append((back, [(6, 2, 1, 0), (5, 3, 2, 6), (4, 3, 5)]))
    nv = len(front)
    for i in range(nv):
        i2 = (i + 1) % nv
        parts.append(([front[i], front[i2], back[i2], back[i]], [(0, 1, 2, 3)]))
    bv, bf = _make_sphere(0, sh * 0.15, thick * 0.5, thick * 2.5, rings=4, sectors=6)
    parts.append((bv, bf))
    rim_v, rim_f = _make_torus_ring(0, sh * 0.15, 0, sw * 0.5, thick * 0.3,
                                    major_segments=segs, minor_segments=3)
    parts.append((rim_v, rim_f))
    hv, hf = _make_cylinder(0, sh * 0.05, -thick * 0.8, thick * 0.3, sw * 0.5,
                            segments=4, cap_top=True, cap_bottom=True)
    hv = [(v[2], v[1], v[0]) for v in hv]
    parts.append((hv, hf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_heater", verts, faces, style="heater", size=size, category="armor")


def generate_pavise_mesh(size: float = 1.0) -> MeshSpec:
    """Generate a full-body standing pavise shield with prop stand."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    pw, ph, thick = 0.35 * size, 0.80 * size, 0.03 * size
    subdiv_x, subdiv_y = 6, 10
    pv: list[tuple[float, float, float]] = []
    pf: list[tuple[int, ...]] = []
    for iy in range(subdiv_y + 1):
        ty = iy / subdiv_y
        y = -ph * 0.5 + ty * ph
        for ix in range(subdiv_x + 1):
            tx = ix / subdiv_x
            x = -pw * 0.5 + tx * pw
            z = thick * 0.5 * math.cos(tx * math.pi)
            pv.append((x, y, z))
    cols = subdiv_x + 1
    for iy in range(subdiv_y):
        for ix in range(subdiv_x):
            v0 = iy * cols + ix
            pf.append((v0, v0 + 1, v0 + cols + 1, v0 + cols))
    parts.append((pv, pf))
    bv, bf = _make_box(0, 0, -thick * 0.3, pw * 0.48, ph * 0.48, thick * 0.1)
    parts.append((bv, bf))
    for sx in [-pw * 0.3, pw * 0.3]:
        lv, lf = _make_box(sx, -ph * 0.1, -thick * 2.0, thick * 0.3, ph * 0.35, thick * 0.15)
        parts.append((lv, lf))
    cbv, cbf = _make_box(0, -ph * 0.2, -thick * 1.5, pw * 0.25, thick * 0.2, thick * 0.1)
    parts.append((cbv, cbf))
    tv, tf = _make_box(0, ph * 0.48, thick * 0.15, pw * 0.50, thick * 0.5, thick * 0.15)
    parts.append((tv, tf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_pavise", verts, faces, style="pavise", size=size, category="armor")


def generate_targe_mesh(size: float = 1.0) -> MeshSpec:
    """Generate a small highland targe shield with spike."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    tr = 0.18 * size
    thick = 0.015 * size
    segs = 12
    profile = [(tr, thick * 0.3), (tr * 0.9, thick * 0.8),
               (tr * 0.6, thick * 1.2), (tr * 0.2, thick * 1.3)]
    sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((sv, sf))
    bkv, bkf = _make_cylinder(0, -thick * 0.3, 0, tr * 0.85, thick * 0.3,
                              segments=segs, cap_top=True, cap_bottom=True)
    parts.append((bkv, bkf))
    spv, spf = _make_cone(0, thick * 1.3, 0, thick * 1.0, tr * 0.5, segments=6)
    parts.append((spv, spf))
    for ri in range(3):
        rr = tr * (0.3 + ri * 0.25)
        rv, rf = _make_torus_ring(0, thick * 0.5, 0, rr, thick * 0.15,
                                  major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
    hv, hf = _make_box(0, -thick * 0.8, 0, tr * 0.3, thick * 0.3, thick * 0.5)
    parts.append((hv, hf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_targe", verts, faces, style="targe", size=size, category="armor")


def generate_magical_barrier_mesh(size: float = 1.0) -> MeshSpec:
    """Generate a translucent energy/magical barrier shield."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    br = 0.30 * size
    segs = 16
    # Upper hemisphere dome via lathe profile
    dome_profile = []
    for _ri in range(7):
        phi = math.pi * 0.5 * _ri / 6
        dome_profile.append((br * math.cos(phi), br * math.sin(phi)))
    sv, sf = _make_lathe(dome_profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((sv, sf))
    hex_rings = 3
    for ring in range(1, hex_rings + 1):
        hex_count = ring * 6
        ring_r = br * ring / (hex_rings + 1)
        for hi in range(hex_count):
            ha = 2.0 * math.pi * hi / hex_count
            hx = math.cos(ha) * ring_r
            hz = math.sin(ha) * ring_r
            hy = math.sqrt(max(0, br * br - ring_r * ring_r)) * 0.9
            hv, hf = _make_torus_ring(hx, hy, hz, br * 0.06, br * 0.008,
                                      major_segments=6, minor_segments=3)
            parts.append((hv, hf))
    cv, cf = _make_sphere(0, br * 0.85, 0, br * 0.08, rings=4, sectors=6)
    parts.append((cv, cf))
    rv, rf = _make_torus_ring(0, 0, 0, br, br * 0.02, major_segments=segs, minor_segments=4)
    parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_magical_barrier", verts, faces,
                        style="magical_barrier", size=size, category="armor")


def generate_bone_shield_mesh(size: float = 1.0) -> MeshSpec:
    """Generate a shield made from monster bones."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    s_r = 0.25 * size
    thick = 0.03 * size
    segs = 8
    cv, cf = _make_sphere(0, 0, thick * 0.5, s_r * 0.25, rings=5, sectors=7)
    parts.append((cv, cf))
    rib_count = 8
    for ri in range(rib_count):
        ra = 2.0 * math.pi * ri / rib_count
        rx, rz_dir = math.cos(ra), math.sin(ra)
        rv, rf = _make_tapered_cylinder(rx * s_r * 0.2, rz_dir * s_r * 0.2, thick * 0.3,
                                        thick * 0.8, thick * 0.3, s_r * 0.7, segments=4, rings=2)
        rv_rot: list[tuple[float, float, float]] = []
        for v in rv:
            lx = v[0] - rx * s_r * 0.2
            ly = v[1] - rz_dir * s_r * 0.2
            dist = v[2] - thick * 0.3
            rv_rot.append((rx * (s_r * 0.2 + dist) + lx * 0.3,
                           rz_dir * (s_r * 0.2 + dist) + ly * 0.3,
                           thick * 0.3 + abs(lx) * 0.2))
        parts.append((rv_rot, rf))
        kx = rx * s_r * 0.85
        ky = rz_dir * s_r * 0.85
        kv, kf = _make_sphere(kx, ky, thick * 0.3, thick * 0.6, rings=3, sectors=4)
        parts.append((kv, kf))
    for ri in range(rib_count):
        ra1 = 2.0 * math.pi * ri / rib_count
        ra2 = 2.0 * math.pi * ((ri + 1) % rib_count) / rib_count
        mid_a = (ra1 + ra2) / 2
        mx = math.cos(mid_a) * s_r * 0.5
        my = math.sin(mid_a) * s_r * 0.5
        mpv, mpf = _make_box(mx, my, thick * 0.15, s_r * 0.15, s_r * 0.15, thick * 0.05)
        parts.append((mpv, mpf))
    for li in range(3):
        lr = s_r * (0.3 + li * 0.2)
        lv, lf = _make_torus_ring(0, 0, thick * 0.3, lr, thick * 0.08,
                                  major_segments=segs, minor_segments=3)
        parts.append((lv, lf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_bone", verts, faces, style="bone", size=size, category="armor")


def generate_crystal_shield_mesh(size: float = 1.0) -> MeshSpec:
    """Generate a crystalline shield with faceted geometry."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    cr = 0.28 * size
    thick = 0.04 * size
    hex_segs = 6
    hex_vf: list[tuple[float, float, float]] = []
    hex_vb: list[tuple[float, float, float]] = []
    for i in range(hex_segs):
        a = 2.0 * math.pi * i / hex_segs + math.pi / 6
        hex_vf.append((math.cos(a) * cr, math.sin(a) * cr, thick * 0.5))
        hex_vb.append((math.cos(a) * cr, math.sin(a) * cr, -thick * 0.3))
    parts.append((hex_vf, [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)]))
    parts.append((hex_vb, [(2, 1, 0), (3, 2, 0), (4, 3, 0), (5, 4, 0)]))
    for i in range(hex_segs):
        i2 = (i + 1) % hex_segs
        parts.append(([hex_vf[i], hex_vf[i2], hex_vb[i2], hex_vb[i]], [(0, 1, 2, 3)]))
    for sx, sy in [(0, cr * 0.3), (cr * 0.3, -cr * 0.1),
                   (-cr * 0.25, cr * 0.15), (cr * 0.1, -cr * 0.35)]:
        spv, spf = _make_cone(sx, sy, thick * 0.5, thick * 0.8, cr * 0.25, segments=5)
        parts.append((spv, spf))
    for i in range(hex_segs):
        a = 2.0 * math.pi * i / hex_segs
        iv, i_f = _make_box(math.cos(a) * cr * 0.5, math.sin(a) * cr * 0.5,
                            thick * 0.4, thick * 0.5, thick * 0.5, thick * 0.15)
        parts.append((iv, i_f))
    gv, gf = _make_sphere(0, 0, thick * 0.8, thick * 1.5, rings=4, sectors=6)
    parts.append((gv, gf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_crystal", verts, faces, style="crystal", size=size, category="armor")


def generate_living_wood_shield_mesh(size: float = 1.0) -> MeshSpec:
    """Generate an organic living wood shield with growing branches."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    wr = 0.27 * size
    thick = 0.025 * size
    segs = 12
    profile = [(wr * 0.85, thick * 0.4), (wr * 0.95, thick * 0.2),
               (wr, 0), (wr * 0.90, -thick * 0.3), (wr * 0.70, -thick * 0.4)]
    sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((sv, sf))
    for ri in range(4):
        rr = wr * (0.3 + ri * 0.18)
        rv, rf = _make_torus_ring(0, 0, 0, rr, thick * 0.15,
                                  major_segments=segs, minor_segments=3)
        parts.append((rv, rf))
    for bx, by, bz, br_r, bl in [(0, wr * 0.85, thick * 0.3, 0.06, 0.15),
                                  (wr * 0.6, wr * 0.5, thick * 0.2, 0.05, 0.12),
                                  (-wr * 0.5, wr * 0.6, thick * 0.25, 0.05, 0.10),
                                  (wr * 0.7, -wr * 0.3, thick * 0.2, 0.04, 0.08),
                                  (-wr * 0.65, -wr * 0.4, thick * 0.15, 0.04, 0.09)]:
        brv, brf = _make_tapered_cylinder(bx, by, bz, br_r * size, br_r * 0.3 * size,
                                          bl * size, segments=5, rings=2)
        parts.append((brv, brf))
    for lx, ly, lz in [(0, wr * 0.95, thick * 0.5), (wr * 0.65, wr * 0.6, thick * 0.4),
                        (-wr * 0.55, wr * 0.7, thick * 0.45)]:
        leaf_v, leaf_f = _make_sphere(lx, ly, lz, thick * 1.5, rings=3, sectors=4)
        leaf_v = [(v[0], v[1], lz + (v[2] - lz) * 0.3) for v in leaf_v]
        parts.append((leaf_v, leaf_f))
    vine_segs = 24
    vine_r = thick * 0.2
    vv: list[tuple[float, float, float]] = []
    vf: list[tuple[int, ...]] = []
    tube = 3
    for i in range(vine_segs):
        a = 2.0 * math.pi * i / vine_segs * 1.5
        vr = wr * 0.7 + thick * math.sin(a * 3) * 2
        vx = math.cos(a) * vr
        vy = math.sin(a) * vr
        vz = thick * 0.3 + math.sin(a * 2) * thick * 0.3
        for j in range(tube):
            ta = 2.0 * math.pi * j / tube
            vv.append((vx + (-math.sin(a)) * math.cos(ta) * vine_r,
                       vy + math.cos(a) * math.cos(ta) * vine_r,
                       vz + math.sin(ta) * vine_r))
    for i in range(vine_segs - 1):
        for j in range(tube):
            j2 = (j + 1) % tube
            vf.append((i * tube + j, i * tube + j2, (i + 1) * tube + j2, (i + 1) * tube + j))
    parts.append((vv, vf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_living_wood", verts, faces,
                        style="living_wood", size=size, category="armor")


def generate_aegis_mesh(size: float = 1.0) -> MeshSpec:
    """Generate an ornate ceremonial aegis shield with face relief."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    ar = 0.30 * size
    thick = 0.025 * size
    segs = 14
    profile = [(ar, thick * 0.2), (ar * 0.95, thick * 0.6), (ar * 0.80, thick * 1.0),
               (ar * 0.50, thick * 1.3), (ar * 0.15, thick * 1.4)]
    sv, sf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((sv, sf))
    rim_v, rim_f = _make_torus_ring(0, 0, 0, ar, thick * 0.6,
                                    major_segments=segs, minor_segments=5)
    parts.append((rim_v, rim_f))
    for ex in [-ar * 0.12, ar * 0.12]:
        ev, ef = _make_sphere(ex, ar * 0.08, thick * 1.5, thick * 0.8, rings=3, sectors=5)
        parts.append((ev, ef))
    nose_v, nose_f = _make_box(0, -ar * 0.02, thick * 1.5, thick * 0.4, thick * 0.8, thick * 0.3)
    parts.append((nose_v, nose_f))
    mouth_v, mouth_f = _make_box(0, -ar * 0.12, thick * 1.3, thick * 1.5, thick * 0.3, thick * 0.2)
    parts.append((mouth_v, mouth_f))
    fcv, fcf = _make_box(0, ar * 0.20, thick * 1.2, ar * 0.18, thick * 0.5, thick * 0.3)
    parts.append((fcv, fcf))
    for fi in range(12):
        fa = 2.0 * math.pi * fi / 12
        fv, ff = _make_cone(math.cos(fa) * ar * 0.85, math.sin(fa) * ar * 0.85,
                            thick * 0.3, thick * 0.8, ar * 0.12, segments=4)
        parts.append((fv, ff))
    for si in range(2):
        s_phase = si * math.pi
        s_segs_count = 20
        s_tube = 3
        s_r = thick * 0.6
        ssv: list[tuple[float, float, float]] = []
        ssf: list[tuple[int, ...]] = []
        for i in range(s_segs_count):
            a = 2.0 * math.pi * i / s_segs_count + s_phase
            wave = math.sin(a * 4 + s_phase) * thick * 2
            sx_s = math.cos(a) * (ar + thick * 0.5)
            sy_s = math.sin(a) * (ar + thick * 0.5)
            for j in range(s_tube):
                ta = 2.0 * math.pi * j / s_tube
                ssv.append((sx_s + (-math.sin(a)) * math.cos(ta) * s_r,
                            sy_s + math.cos(a) * math.cos(ta) * s_r,
                            wave + math.sin(ta) * s_r))
        for i in range(s_segs_count - 1):
            for j in range(s_tube):
                j2 = (j + 1) % s_tube
                ssf.append((i * s_tube + j, i * s_tube + j2,
                            (i + 1) * s_tube + j2, (i + 1) * s_tube + j))
        parts.append((ssv, ssf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Shield_aegis", verts, faces, style="aegis", size=size, category="armor")


# =========================================================================
# SPELL SCROLLS, RUNE STONES & SPECIAL AMMO
# =========================================================================


def generate_spell_scroll_mesh(style: str = "fire") -> MeshSpec:
    """Generate a spell scroll mesh with distinct visual per element.

    Styles: fire, ice, lightning, teleport, protection, identify.
    """
    _STYLES = ["fire", "ice", "lightning", "teleport", "protection", "identify"]
    if style not in _STYLES:
        style = "fire"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    scroll_len = 0.22
    scroll_r = scroll_len * 0.07
    segs = 10

    sv, sf = _make_cylinder(0, 0, 0, scroll_r, scroll_len, segments=segs)
    sv = [(v[0], v[2], v[1]) for v in sv]
    parts.append((sv, sf))
    for z_end in [-scroll_len * 0.5, scroll_len * 0.5]:
        kv, kf = _make_sphere(0, 0, z_end, scroll_r * 1.3, rings=3, sectors=6)
        parts.append((kv, kf))

    seal_y = scroll_r * 1.3
    seal_z = 0
    if style == "fire":
        wsv, wsf = _make_cone(0, seal_y, seal_z, scroll_r * 0.6, scroll_r * 1.2, segments=5)
        parts.append((wsv, wsf))
        wbv, wbf = _make_sphere(0, seal_y, seal_z, scroll_r * 0.5, rings=3, sectors=5)
        parts.append((wbv, wbf))
    elif style == "ice":
        wbv, wbf = _make_sphere(0, seal_y, seal_z, scroll_r * 0.45, rings=3, sectors=6)
        parts.append((wbv, wbf))
        for ci in range(6):
            ca = ci * math.pi / 3
            cv, c_f = _make_box(math.cos(ca) * scroll_r * 0.5, seal_y,
                               seal_z + math.sin(ca) * scroll_r * 0.5,
                               scroll_r * 0.08, scroll_r * 0.15, scroll_r * 0.08)
            parts.append((cv, c_f))
    elif style == "lightning":
        wbv, wbf = _make_sphere(0, seal_y, seal_z, scroll_r * 0.4, rings=3, sectors=5)
        parts.append((wbv, wbf))
        bolt_pts = [(-scroll_r * 0.3, seal_y + scroll_r * 0.6),
                    (scroll_r * 0.15, seal_y + scroll_r * 0.3),
                    (-scroll_r * 0.1, seal_y),
                    (scroll_r * 0.3, seal_y - scroll_r * 0.5)]
        for bi in range(len(bolt_pts) - 1):
            bbv, bbf = _make_box((bolt_pts[bi][0] + bolt_pts[bi + 1][0]) / 2,
                                 (bolt_pts[bi][1] + bolt_pts[bi + 1][1]) / 2,
                                 seal_z, scroll_r * 0.06, scroll_r * 0.15, scroll_r * 0.04)
            parts.append((bbv, bbf))
    elif style == "teleport":
        wrv, wrf = _make_torus_ring(0, seal_y, seal_z, scroll_r * 0.5, scroll_r * 0.12,
                                    major_segments=8, minor_segments=3)
        parts.append((wrv, wrf))
        wcv, wcf = _make_sphere(0, seal_y, seal_z, scroll_r * 0.25, rings=3, sectors=5)
        parts.append((wcv, wcf))
    elif style == "protection":
        wbv, wbf = _make_box(0, seal_y, seal_z, scroll_r * 0.5, scroll_r * 0.55, scroll_r * 0.1)
        parts.append((wbv, wbf))
        wcv, wcf = _make_sphere(0, seal_y, seal_z + scroll_r * 0.1,
                                scroll_r * 0.25, rings=3, sectors=5)
        parts.append((wcv, wcf))
    elif style == "identify":
        wcv, wcf = _make_sphere(0, seal_y, seal_z, scroll_r * 0.4, rings=4, sectors=6)
        parts.append((wcv, wcf))
        wpv, wpf = _make_sphere(0, seal_y + scroll_r * 0.15, seal_z,
                                scroll_r * 0.15, rings=2, sectors=4)
        parts.append((wpv, wpf))

    rbv, rbf = _make_box(0, seal_y - scroll_r * 0.3, seal_z,
                         scroll_r * 0.15, scroll_r * 0.8, scroll_r * 0.03)
    parts.append((rbv, rbf))
    for rx in [-scroll_r * 0.08, scroll_r * 0.08]:
        rfv, rff = _make_box(rx, seal_y - scroll_r * 1.0, seal_z,
                             scroll_r * 0.05, scroll_r * 0.25, scroll_r * 0.02)
        parts.append((rfv, rff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"SpellScroll_{style}", verts, faces,
                        style=style, category="combat_item")


_BRAND_NAMES = ["IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                "LEECH", "GRACE", "MEND", "RUIN", "VOID"]


def generate_rune_stone_mesh(brand: str = "IRON") -> MeshSpec:
    """Generate a brand-specific rune stone with distinct geometry per brand."""
    if brand not in _BRAND_NAMES:
        brand = "IRON"

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    base_r = 0.04
    segs = 8

    if brand == "IRON":
        bv, bf = _make_box(0, base_r * 0.5, 0, base_r, base_r * 0.5, base_r * 0.6)
        parts.append((bv, bf))
        nv, nf = _make_box(0, base_r * 1.05, 0, base_r * 0.4, base_r * 0.08, base_r * 0.65)
        parts.append((nv, nf))
        rv, rf = _make_box(0, base_r * 0.5, base_r * 0.65, base_r * 0.6, base_r * 0.3, base_r * 0.03)
        parts.append((rv, rf))
    elif brand == "SAVAGE":
        sv, sf = _make_sphere(0, base_r, 0, base_r, rings=5, sectors=6)
        sv = [(v[0] * (1 + 0.15 * math.sin(v[1] * 20)), v[1],
               v[2] * (1 + 0.1 * math.cos(v[0] * 15))) for v in sv]
        parts.append((sv, sf))
        for ci in range(3):
            cv, c_f = _make_box(-base_r * 0.3 + ci * base_r * 0.3, base_r * 1.0, base_r * 0.8,
                               base_r * 0.02, base_r * 0.6, base_r * 0.02)
            parts.append((cv, c_f))
    elif brand == "SURGE":
        sv, sf = _make_cone(0, 0, 0, base_r * 0.6, base_r * 1.5, segments=6)
        parts.append((sv, sf))
        sv2, sf2 = _make_cone(0, 0, 0, base_r * 0.6, -base_r * 0.8, segments=6)
        parts.append((sv2, sf2))
        for ri in range(2):
            rv, rf = _make_torus_ring(0, base_r * (0.5 + ri * 0.5), 0, base_r * 0.4,
                                      base_r * 0.04, major_segments=6, minor_segments=3)
            parts.append((rv, rf))
    elif brand == "VENOM":
        sv, sf = _make_tapered_cylinder(0, 0, 0, base_r * 0.7, base_r * 0.2,
                                        base_r * 2, segments=segs, rings=3)
        parts.append((sv, sf))
        for di in range(3):
            da = di * math.pi * 2 / 3
            dv, df = _make_cone(math.cos(da) * base_r * 0.5, -base_r * 0.2,
                                math.sin(da) * base_r * 0.5, base_r * 0.08, base_r * 0.4, segments=4)
            dv = [(v[0], -v[1], v[2]) for v in dv]
            parts.append((dv, df))
    elif brand == "DREAD":
        sv, sf = _make_sphere(0, base_r, 0, base_r, rings=5, sectors=7)
        parts.append((sv, sf))
        for ex in [-base_r * 0.35, base_r * 0.35]:
            ev, ef = _make_sphere(ex, base_r * 1.15, base_r * 0.7,
                                  base_r * 0.2, rings=3, sectors=4)
            parts.append((ev, ef))
        jv, jf = _make_box(0, base_r * 0.4, base_r * 0.6,
                           base_r * 0.5, base_r * 0.1, base_r * 0.15)
        parts.append((jv, jf))
    elif brand == "LEECH":
        sv, sf = _make_sphere(0, base_r, 0, base_r * 0.9, rings=5, sectors=7)
        parts.append((sv, sf))
        for ti in range(5):
            ta = ti * math.pi * 2 / 5
            tv, tf = _make_tapered_cylinder(math.cos(ta) * base_r * 0.8, base_r * 0.5,
                                            math.sin(ta) * base_r * 0.8,
                                            base_r * 0.08, base_r * 0.02,
                                            base_r * 0.6, segments=4, rings=2)
            parts.append((tv, tf))
        mmv, mmf = _make_torus_ring(0, base_r * 0.3, base_r * 0.85,
                                    base_r * 0.25, base_r * 0.06,
                                    major_segments=6, minor_segments=3)
        parts.append((mmv, mmf))
    elif brand == "GRACE":
        sv, sf = _make_sphere(0, base_r, 0, base_r * 0.8, rings=6, sectors=8)
        parts.append((sv, sf))
        hv, hf = _make_torus_ring(0, base_r * 1.6, 0, base_r * 0.7, base_r * 0.05,
                                  major_segments=12, minor_segments=4)
        parts.append((hv, hf))
        for ri in range(4):
            ra = ri * math.pi / 2
            rrv, rrf = _make_box(math.cos(ra) * base_r * 0.7, base_r * 1.6,
                                 math.sin(ra) * base_r * 0.7,
                                 base_r * 0.02, base_r * 0.02, base_r * 0.15)
            parts.append((rrv, rrf))
    elif brand == "MEND":
        sv, sf = _make_sphere(0, base_r, 0, base_r * 0.85, rings=5, sectors=7)
        parts.append((sv, sf))
        cv, c_f = _make_box(0, base_r, base_r * 0.9,
                           base_r * 0.08, base_r * 0.5, base_r * 0.03)
        parts.append((cv, c_f))
        chv, chf = _make_box(0, base_r * 1.2, base_r * 0.9,
                            base_r * 0.3, base_r * 0.08, base_r * 0.03)
        parts.append((chv, chf))
        wv, wf = _make_torus_ring(0, base_r, 0, base_r * 0.9, base_r * 0.04,
                                  major_segments=segs, minor_segments=3)
        parts.append((wv, wf))
    elif brand == "RUIN":
        ov, of = _make_tapered_cylinder(0, 0, 0, base_r * 0.5, base_r * 0.3,
                                        base_r * 2.5, segments=5, rings=3)
        parts.append((ov, of))
        for ci in range(3):
            cv, c_f = _make_box(base_r * 0.35, base_r * (0.5 + ci * 0.6), 0,
                               base_r * 0.02, base_r * 0.3, base_r * 0.1)
            parts.append((cv, c_f))
        for di in range(4):
            da = di * math.pi * 2 / 4
            dv, df = _make_box(math.cos(da) * base_r * 0.6, base_r * 0.1,
                               math.sin(da) * base_r * 0.6,
                               base_r * 0.12, base_r * 0.12, base_r * 0.1)
            parts.append((dv, df))
    elif brand == "VOID":
        sv, sf = _make_sphere(0, base_r, 0, base_r, rings=6, sectors=8)
        parts.append((sv, sf))
        iv, i_f = _make_sphere(0, base_r, 0, base_r * 0.5, rings=4, sectors=6)
        parts.append((iv, i_f))
        for fi in range(3):
            fa = fi * math.pi * 2 / 3
            fv, ff = _make_box(math.cos(fa) * base_r * 0.9, base_r,
                               math.sin(fa) * base_r * 0.9,
                               base_r * 0.05, base_r * 0.3, base_r * 0.05)
            parts.append((fv, ff))
        for oi in range(4):
            oa = oi * math.pi / 2
            oov, oof = _make_box(math.cos(oa) * base_r * 1.4, base_r,
                                 math.sin(oa) * base_r * 1.4,
                                 base_r * 0.08, base_r * 0.08, base_r * 0.08)
            parts.append((oov, oof))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"RuneStone_{brand}", verts, faces,
                        brand=brand, category="combat_item")


# -- Elemental & Special Ammo Variants --


def generate_fire_arrow_mesh(shaft_length: float = 0.7) -> MeshSpec:
    """Generate a fire arrow with burning head and oil-soaked wrapping."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.008
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=6, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(3):
        a = fi * math.pi * 2 / 3
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 4, shaft_length * 0.06, math.sin(a) * sr * 4),
                       (math.cos(a) * sr * 3, shaft_length * 0.14, math.sin(a) * sr * 3),
                       (math.cos(a) * sr, shaft_length * 0.12, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    hy = shaft_length
    hh, hw = shaft_length * 0.06, sr * 5
    dv = [(0, hy, 0), (hw, hy + hh * 0.4, 0), (0, hy + hh, 0), (-hw, hy + hh * 0.4, 0)]
    parts.append((dv, [(0, 1, 2, 3)]))
    parts.append(([(v[0], v[1], sr * 0.5) for v in dv], [(3, 2, 1, 0)]))
    wv, wf = _make_sphere(0, hy - shaft_length * 0.02, 0, sr * 4, rings=4, sectors=6)
    parts.append((wv, wf))
    for wi in range(3):
        wa = wi * math.pi * 2 / 3
        fv, ff = _make_cone(math.cos(wa) * sr * 3, hy + hh * 0.2,
                            math.sin(wa) * sr * 3, sr * 1.5, shaft_length * 0.04, segments=4)
        parts.append((fv, ff))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Arrow_fire", verts, faces, element="fire", category="projectile")


def generate_ice_arrow_mesh(shaft_length: float = 0.7) -> MeshSpec:
    """Generate an ice arrow with crystalline frost head."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.008
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=6, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(3):
        a = fi * math.pi * 2 / 3
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 4, shaft_length * 0.06, math.sin(a) * sr * 4),
                       (math.cos(a) * sr * 3, shaft_length * 0.14, math.sin(a) * sr * 3),
                       (math.cos(a) * sr, shaft_length * 0.12, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    hy = shaft_length
    cv, cf = _make_cone(0, hy, 0, sr * 3, shaft_length * 0.10, segments=4)
    parts.append((cv, cf))
    for ci in range(4):
        ca = ci * math.pi / 2
        scv, scf = _make_cone(math.cos(ca) * sr * 3, hy + shaft_length * 0.02,
                              math.sin(ca) * sr * 3, sr * 1.2, shaft_length * 0.05, segments=3)
        parts.append((scv, scf))
    frv, frf = _make_torus_ring(0, hy - shaft_length * 0.01, 0,
                                sr * 4, sr * 0.5, major_segments=6, minor_segments=3)
    parts.append((frv, frf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Arrow_ice", verts, faces, element="ice", category="projectile")


def generate_poison_arrow_mesh(shaft_length: float = 0.7) -> MeshSpec:
    """Generate a poison arrow with dripping venom coating."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.008
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=6, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(3):
        a = fi * math.pi * 2 / 3
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 4, shaft_length * 0.06, math.sin(a) * sr * 4),
                       (math.cos(a) * sr * 3, shaft_length * 0.14, math.sin(a) * sr * 3),
                       (math.cos(a) * sr, shaft_length * 0.12, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    hy = shaft_length
    hhv, hhf = _make_cone(0, hy, 0, sr * 2.5, shaft_length * 0.06, segments=4)
    parts.append((hhv, hhf))
    for bi in range(2):
        ba = bi * math.pi
        bx = math.cos(ba) * sr * 2
        bz = math.sin(ba) * sr * 2
        parts.append(([(bx, hy + shaft_length * 0.02, bz),
                       (bx * 1.8, hy - shaft_length * 0.01, bz * 1.8),
                       (bx * 0.5, hy - shaft_length * 0.005, bz * 0.5)], [(0, 1, 2)]))
    for di in range(3):
        da = di * math.pi * 2 / 3
        dx = math.cos(da) * sr * 2.5
        dz = math.sin(da) * sr * 2.5
        ddv, ddf = _make_sphere(dx, hy - shaft_length * 0.015, dz,
                                sr * 1.2, rings=3, sectors=4)
        ddv = [(v[0], v[1] - abs(v[1] - hy + shaft_length * 0.015) * 0.5, v[2]) for v in ddv]
        parts.append((ddv, ddf))
    vcv, vcf = _make_torus_ring(0, hy - shaft_length * 0.02, 0,
                                sr * 3, sr * 0.6, major_segments=6, minor_segments=3)
    parts.append((vcv, vcf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Arrow_poison", verts, faces, element="poison", category="projectile")


def generate_explosive_bolt_mesh(shaft_length: float = 0.5) -> MeshSpec:
    """Generate a crossbow bolt with explosive charge head."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.012
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=6, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(2):
        a = fi * math.pi
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 3, shaft_length * 0.04, math.sin(a) * sr * 3),
                       (math.cos(a) * sr * 2.5, shaft_length * 0.10, math.sin(a) * sr * 2.5),
                       (math.cos(a) * sr, shaft_length * 0.08, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    hy = shaft_length
    ev, ef = _make_sphere(0, hy + sr * 4, 0, sr * 5, rings=5, sectors=7)
    parts.append((ev, ef))
    fuse_v, fuse_f = _make_cylinder(0, hy + sr * 9, 0, sr * 0.5, sr * 4,
                                    segments=3, cap_top=True, cap_bottom=True)
    parts.append((fuse_v, fuse_f))
    for ri in range(2):
        rrv, rrf = _make_torus_ring(0, hy + sr * (2 + ri * 4), 0, sr * 5.2, sr * 0.5,
                                    major_segments=8, minor_segments=3)
        parts.append((rrv, rrf))
    pv, pf = _make_cone(0, hy + sr * 9, 0, sr * 1.5, sr * 3, segments=4)
    parts.append((pv, pf))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Bolt_explosive", verts, faces, element="explosive", category="projectile")


def generate_silver_arrow_mesh(shaft_length: float = 0.7) -> MeshSpec:
    """Generate a silver arrow for slaying undead/werewolves."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.008
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=8, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(3):
        a = fi * math.pi * 2 / 3
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 5, shaft_length * 0.05, math.sin(a) * sr * 5),
                       (math.cos(a) * sr * 4, shaft_length * 0.16, math.sin(a) * sr * 4),
                       (math.cos(a) * sr, shaft_length * 0.14, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    hy = shaft_length
    hh = shaft_length * 0.07
    hw = sr * 7
    ddv = [(0, hy, 0), (hw, hy + hh * 0.3, 0), (hw * 0.6, hy + hh * 0.7, 0),
           (0, hy + hh, 0), (-hw * 0.6, hy + hh * 0.7, 0), (-hw, hy + hh * 0.3, 0)]
    parts.append((ddv, [(0, 1, 2, 3), (0, 3, 4, 5)]))
    parts.append(([(v[0], v[1], sr * 0.4) for v in ddv], [(3, 2, 1, 0), (5, 4, 3, 0)]))
    for ri in range(2):
        rrv, rrf = _make_torus_ring(0, shaft_length * (0.4 + ri * 0.2), 0, sr * 1.5, sr * 0.15,
                                    major_segments=6, minor_segments=3)
        parts.append((rrv, rrf))
    nock_v, nock_f = _make_cylinder(0, 0, 0, sr * 1.3, shaft_length * 0.02,
                                    segments=6, cap_top=True, cap_bottom=True)
    parts.append((nock_v, nock_f))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Arrow_silver", verts, faces, element="silver", category="projectile")


def generate_barbed_arrow_mesh(shaft_length: float = 0.7) -> MeshSpec:
    """Generate a barbed arrow designed to cause bleeding on removal."""
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    sr = shaft_length * 0.008
    sv, sf = _make_cylinder(0, 0, 0, sr, shaft_length, segments=6, cap_top=False, cap_bottom=True)
    parts.append((sv, sf))
    for fi in range(3):
        a = fi * math.pi * 2 / 3
        parts.append(([(math.cos(a) * sr, shaft_length * 0.02, math.sin(a) * sr),
                       (math.cos(a) * sr * 4, shaft_length * 0.06, math.sin(a) * sr * 4),
                       (math.cos(a) * sr * 3, shaft_length * 0.14, math.sin(a) * sr * 3),
                       (math.cos(a) * sr, shaft_length * 0.12, math.sin(a) * sr)],
                      [(0, 1, 2, 3)]))
    hy = shaft_length
    hhv, hhf = _make_cone(0, hy, 0, sr * 3, shaft_length * 0.06, segments=4)
    parts.append((hhv, hhf))
    for level in range(3):
        ly = hy + shaft_length * 0.01 * level
        for bi in range(3):
            ba = bi * math.pi * 2 / 3 + level * math.pi / 3
            bx = math.cos(ba) * sr * 2.5
            bz = math.sin(ba) * sr * 2.5
            parts.append(([(bx, ly + shaft_length * 0.015, bz),
                           (bx * 1.6, ly - shaft_length * 0.005, bz * 1.6),
                           (bx * 0.8, ly - shaft_length * 0.012, bz * 0.8)], [(0, 1, 2)]))
    sev, sef = _make_torus_ring(0, hy, 0, sr * 3.5, sr * 0.3,
                                major_segments=6, minor_segments=3)
    parts.append((sev, sef))
    verts, faces = _merge_meshes(*parts)
    return _make_result("Arrow_barbed", verts, faces, element="barbed", category="projectile")


# =========================================================================
# INTERIOR FURNITURE & PROPS (bed, wardrobe, cabinet, curtain, mirror,
#   hay_bale, wine_rack, bathtub, fireplace)
# =========================================================================


def generate_bed_mesh(
    style: str = "simple",
    width: float = 2.0,
    depth: float = 0.9,
    height: float = 0.5,
) -> MeshSpec:
    """Generate a bed mesh.

    Args:
        style: "simple" (wooden frame + mattress), "ornate" (headboard + footboard + posts),
               or "bedroll" (rolled fabric on ground).
        width: Bed length along X.
        depth: Bed width along Z.
        height: Bed height along Y.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "bedroll":
        # Rolled fabric on ground -- simple cylinder + flat pad
        # Flat pad
        pad_h = 0.04
        pv, pf = _make_beveled_box(0, pad_h / 2, 0, width * 0.4, pad_h / 2, depth * 0.4,
                                    bevel=0.005)
        parts.append((pv, pf))
        # Rolled portion at one end
        roll_r = 0.08
        rv, rf = _make_cylinder(width * 0.35, pad_h, 0, roll_r, depth * 0.6,
                                segments=10, cap_top=True, cap_bottom=True)
        # Rotate cylinder to lie along Z -- swap Y/Z
        rv_rot = [(v[0], v[2] + pad_h + roll_r, v[1]) for v in rv]
        parts.append((rv_rot, rf))
        # Small pillow bump
        sv, sf = _make_sphere(-width * 0.25, pad_h + 0.03, 0, 0.07,
                              rings=4, sectors=6)
        parts.append((sv, sf))
    else:
        # --- Frame rails ---
        rail_h = 0.04
        rail_w = 0.04
        leg_r = 0.03
        leg_segs = 6
        frame_top = height * 0.55
        mattress_h = height * 0.35

        # Side rails (along X)
        for z_off in [-depth / 2 + rail_w / 2, depth / 2 - rail_w / 2]:
            rv, rf = _make_beveled_box(0, frame_top - rail_h / 2, z_off,
                                       width / 2, rail_h / 2, rail_w / 2,
                                       bevel=0.003)
            parts.append((rv, rf))

        # End rails (along Z)
        for x_off in [-width / 2 + rail_w / 2, width / 2 - rail_w / 2]:
            rv, rf = _make_beveled_box(x_off, frame_top - rail_h / 2, 0,
                                       rail_w / 2, rail_h / 2, depth / 2 - rail_w,
                                       bevel=0.003)
            parts.append((rv, rf))

        # Slat support board
        sv, sf = _make_beveled_box(0, frame_top - rail_h, 0,
                                   width / 2 - rail_w, 0.01, depth / 2 - rail_w,
                                   bevel=0.002)
        parts.append((sv, sf))

        # 4 legs
        leg_height = frame_top - rail_h
        for xm in [-1, 1]:
            for zm in [-1, 1]:
                lx = xm * (width / 2 - leg_r)
                lz = zm * (depth / 2 - leg_r)
                lv, lf = _make_tapered_cylinder(
                    lx, 0, lz, leg_r * 1.1, leg_r * 0.9,
                    leg_height, leg_segs, rings=2,
                    cap_top=True, cap_bottom=True,
                )
                parts.append((lv, lf))

        # Mattress -- slightly rounded beveled box on top of frame
        mat_y = frame_top
        mv, mf = _make_beveled_box(0, mat_y + mattress_h / 2, 0,
                                   width / 2 - rail_w * 0.5,
                                   mattress_h / 2,
                                   depth / 2 - rail_w * 0.5,
                                   bevel=0.015)
        parts.append((mv, mf))

        # Pillow
        pv, pf = _make_beveled_box(-width * 0.35, mat_y + mattress_h + 0.03, 0,
                                   0.12, 0.03, depth * 0.3,
                                   bevel=0.01)
        parts.append((pv, pf))

        if style == "ornate":
            # Headboard
            hb_h = height * 0.7
            hb_w = depth - 0.02
            hv, hf = _make_beveled_box(-width / 2 + 0.02, frame_top + hb_h / 2, 0,
                                       0.02, hb_h / 2, hb_w / 2,
                                       bevel=0.005)
            parts.append((hv, hf))

            # Footboard (shorter)
            fb_h = height * 0.3
            fv, ff = _make_beveled_box(width / 2 - 0.02, frame_top + fb_h / 2, 0,
                                       0.02, fb_h / 2, hb_w / 2,
                                       bevel=0.005)
            parts.append((fv, ff))

            # 4 corner posts (taller)
            post_h = height * 0.9
            post_r = 0.025
            for xm in [-1, 1]:
                for zm in [-1, 1]:
                    px = xm * (width / 2 - 0.01)
                    pz = zm * (depth / 2 - 0.01)
                    ppv, ppf = _make_tapered_cylinder(
                        px, frame_top, pz,
                        post_r, post_r * 0.7, post_h,
                        segments=6, rings=3,
                        cap_top=True, cap_bottom=True,
                    )
                    parts.append((ppv, ppf))
                    # Finial ball on top
                    bsv, bsf = _make_sphere(px, frame_top + post_h + post_r * 0.5, pz,
                                            post_r * 0.9, rings=4, sectors=6)
                    parts.append((bsv, bsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bed_{style}", verts, faces,
                        style=style, category="furniture")


def generate_wardrobe_mesh(
    style: str = "wooden",
    width: float = 1.0,
    depth: float = 0.5,
    height: float = 2.0,
) -> MeshSpec:
    """Generate a wardrobe / armoire mesh.

    Args:
        style: "wooden" (simple doors), "ornate" (carved panels), "armoire" (tall with crown).
        width: Width along X.
        depth: Depth along Z.
        height: Height along Y.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    wall = 0.025  # wall thickness
    door_gap = 0.005

    # Main body shell (outer)
    bv, bf = _make_beveled_box(0, height / 2, 0,
                               width / 2, height / 2, depth / 2,
                               bevel=0.008)
    parts.append((bv, bf))

    # Hollow interior (slightly smaller box, inverted normals approximation --
    # we just add the inner box since the outer shell + inner box give thickness)
    inner_w = width / 2 - wall
    inner_h = height / 2 - wall
    inner_d = depth / 2 - wall
    iv, i_f = _make_box(0, height / 2, 0, inner_w, inner_h, inner_d)
    parts.append((iv, i_f))

    # Two front doors (slightly recessed)
    door_w = (width / 2 - door_gap * 1.5) / 1.0
    door_h = height - wall * 4
    door_thick = 0.015
    for side in [-1, 1]:
        dx = side * (door_w / 2 + door_gap / 2)
        dv, df = _make_beveled_box(dx, height / 2, -depth / 2 + door_thick / 2 - 0.001,
                                   door_w / 2 - door_gap, door_h / 2, door_thick / 2,
                                   bevel=0.004)
        parts.append((dv, df))

        # Door handle knob
        kv, kf = _make_sphere(dx - side * (door_w / 2 - 0.06),
                              height * 0.5,
                              -depth / 2 - 0.01,
                              0.012, rings=3, sectors=6)
        parts.append((kv, kf))

    # Internal shelves (3 shelves)
    shelf_thick = 0.012
    for i in range(3):
        sy = wall * 2 + (i + 1) * (height - wall * 4) / 4
        shv, shf = _make_box(0, sy, 0,
                             inner_w - 0.005, shelf_thick / 2, inner_d - 0.005)
        parts.append((shv, shf))

    if style == "ornate":
        # Carved panel insets on doors (recessed rectangles)
        panel_w = door_w * 0.35
        panel_h = door_h * 0.3
        for side in [-1, 1]:
            dx = side * (door_w / 2 + door_gap / 2)
            for py_mult in [0.33, 0.67]:
                pv, pf = _make_beveled_box(
                    dx, height * py_mult, -depth / 2 - 0.015,
                    panel_w, panel_h / 2, 0.003,
                    bevel=0.003,
                )
                parts.append((pv, pf))

    elif style == "armoire":
        # Crown molding strip along top
        crown_h = 0.04
        crown_overhang = 0.02
        cv, cf = _make_beveled_box(0, height + crown_h / 2, 0,
                                   width / 2 + crown_overhang,
                                   crown_h / 2,
                                   depth / 2 + crown_overhang,
                                   bevel=0.006)
        parts.append((cv, cf))

        # Base molding
        base_h = 0.05
        bmv, bmf = _make_beveled_box(0, base_h / 2, 0,
                                     width / 2 + crown_overhang * 0.5,
                                     base_h / 2,
                                     depth / 2 + crown_overhang * 0.5,
                                     bevel=0.005)
        parts.append((bmv, bmf))

        # Feet (small spheres)
        for xm in [-1, 1]:
            for zm in [-1, 1]:
                fv, ff = _make_sphere(
                    xm * (width / 2 - 0.05), 0.02,
                    zm * (depth / 2 - 0.05),
                    0.025, rings=3, sectors=6,
                )
                parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Wardrobe_{style}", verts, faces,
                        style=style, category="furniture")


def generate_cabinet_mesh(
    style: str = "simple",
    width: float = 0.8,
    depth: float = 0.4,
    height: float = 1.0,
) -> MeshSpec:
    """Generate a cabinet mesh.

    Args:
        style: "simple", "apothecary" (many small drawers), or "display" (glass front).
        width: Width along X.
        depth: Depth along Z.
        height: Height along Y.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    wall = 0.02

    # Main body
    bv, bf = _make_beveled_box(0, height / 2, 0,
                               width / 2, height / 2, depth / 2,
                               bevel=0.006)
    parts.append((bv, bf))

    if style == "apothecary":
        # Grid of small drawers (4 columns x 5 rows)
        cols, rows = 4, 5
        drawer_gap = 0.008
        total_gap_x = drawer_gap * (cols + 1)
        total_gap_y = drawer_gap * (rows + 1)
        dw = (width - total_gap_x - wall * 2) / cols
        dh = (height - total_gap_y - wall * 2) / rows
        d_thick = 0.01

        for r in range(rows):
            for c in range(cols):
                dx = -width / 2 + wall + drawer_gap + c * (dw + drawer_gap) + dw / 2
                dy = wall + drawer_gap + r * (dh + drawer_gap) + dh / 2
                # Drawer face
                dv, df = _make_beveled_box(
                    dx, dy, -depth / 2 - 0.001,
                    dw / 2 - 0.002, dh / 2 - 0.002, d_thick / 2,
                    bevel=0.002,
                )
                parts.append((dv, df))
                # Tiny knob
                kv, kf = _make_sphere(dx, dy, -depth / 2 - d_thick,
                                      0.006, rings=3, sectors=4)
                parts.append((kv, kf))

    elif style == "display":
        # Single large glass-front door
        door_h = height - wall * 4
        door_w = width - wall * 4
        d_thick = 0.008

        # Door frame
        dv, df = _make_beveled_box(0, height / 2, -depth / 2 - 0.001,
                                   door_w / 2, door_h / 2, d_thick / 2,
                                   bevel=0.003)
        parts.append((dv, df))

        # Glass pane (thin flat quad inside frame)
        # Slightly inset
        gv, gf = _make_box(0, height / 2, -depth / 2 - d_thick,
                           door_w / 2 - 0.015, door_h / 2 - 0.015, 0.002)
        parts.append((gv, gf))

        # Handle
        hv, hf = _make_sphere(door_w / 2 - 0.03, height * 0.5,
                              -depth / 2 - d_thick - 0.005,
                              0.01, rings=3, sectors=6)
        parts.append((hv, hf))

        # 2 internal shelves
        for i in range(2):
            sy = wall + (i + 1) * (height - wall * 2) / 3
            sv, sf = _make_box(0, sy, 0,
                               width / 2 - wall - 0.005,
                               0.006,
                               depth / 2 - wall - 0.005)
            parts.append((sv, sf))
    else:
        # Simple: 2 doors + 1 shelf
        door_w = (width - wall * 2 - 0.01) / 2
        door_h = height - wall * 4
        d_thick = 0.012

        for side in [-1, 1]:
            dx = side * (door_w / 2 + 0.003)
            dv, df = _make_beveled_box(dx, height / 2, -depth / 2 - 0.001,
                                       door_w / 2 - 0.003, door_h / 2, d_thick / 2,
                                       bevel=0.003)
            parts.append((dv, df))
            # Knob
            kv, kf = _make_sphere(dx - side * (door_w / 2 - 0.04), height * 0.5,
                                  -depth / 2 - d_thick,
                                  0.008, rings=3, sectors=5)
            parts.append((kv, kf))

        # 1 internal shelf
        sv, sf = _make_box(0, height * 0.5, 0,
                           width / 2 - wall - 0.005, 0.006,
                           depth / 2 - wall - 0.005)
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cabinet_{style}", verts, faces,
                        style=style, category="furniture")


def generate_curtain_mesh(
    style: str = "hanging",
    width: float = 1.0,
    height: float = 1.5,
    folds: int = 8,
) -> MeshSpec:
    """Generate a curtain mesh -- a flat subdivided plane with wave deformation.

    Args:
        style: "hanging" (straight drape), "gathered" (bunched folds),
               or "tattered" (torn lower edge).
        width: Curtain width along X.
        height: Curtain height along Y.
        folds: Number of wave folds across width.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Subdivided plane with wave deformation
    res_x = max(folds * 4, 16)  # horizontal resolution
    res_y = 12  # vertical resolution
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []

    for iy in range(res_y + 1):
        ty = iy / res_y
        y = height * (1.0 - ty)  # top to bottom
        for ix in range(res_x + 1):
            tx = ix / res_x
            x = (tx - 0.5) * width

            # Wave deformation along Z
            wave_amp = 0.03
            if style == "gathered":
                wave_amp = 0.06 + 0.02 * math.sin(ty * math.pi)
                # Gather toward center at bottom
                gather = (1.0 - ty) * 0.3
                x *= (1.0 - gather * 0.5)
            elif style == "tattered":
                wave_amp = 0.03 + 0.01 * math.sin(ty * 7.0)

            z = math.sin(tx * folds * math.pi * 2) * wave_amp

            # For tattered style: cut the bottom edge irregularly
            if style == "tattered" and ty > 0.7:
                # Irregular bottom by varying y based on x position
                tear_offset = math.sin(tx * 13.7) * 0.15 + math.sin(tx * 7.3) * 0.1
                y -= max(0, tear_offset * (ty - 0.7) / 0.3) * height * 0.2

            verts.append((x, y, z))
            uvs.append((tx, 1.0 - ty))

    # Faces
    for iy in range(res_y):
        for ix in range(res_x):
            i0 = iy * (res_x + 1) + ix
            i1 = i0 + 1
            i2 = i0 + (res_x + 1) + 1
            i3 = i0 + (res_x + 1)
            faces.append((i0, i1, i2, i3))

    # Curtain rod (cylinder at top)
    rod_r = 0.012
    rod_len = width * 1.1
    rod_segs = 8
    rod_base = len(verts)
    rv, rf = _make_cylinder(0, height + rod_r, 0, rod_r, rod_len,
                            segments=rod_segs, cap_top=True, cap_bottom=True,
                            base_idx=rod_base)
    # Rotate to lie along X axis: swap Y with local-axis
    rv_rotated = [(-rod_len / 2 + v[1] - (height + rod_r),
                   height + rod_r + v[0],
                   v[2]) for v in rv]
    verts.extend(rv_rotated)
    faces.extend(rf)

    return _make_result(f"Curtain_{style}", verts, faces, uvs=uvs,
                        style=style, folds=folds, category="furniture")


def generate_mirror_mesh(
    style: str = "wall",
    width: float = 0.5,
    height: float = 0.7,
) -> MeshSpec:
    """Generate a mirror mesh with frame and reflective surface.

    Args:
        style: "wall" (rectangular wall-mounted), "standing" (floor mirror with legs),
               or "hand" (small oval hand mirror).
        width: Mirror width along X.
        height: Mirror height along Y.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "hand":
        # Small oval hand mirror with handle
        mirror_r = 0.06
        frame_thick = 0.008
        handle_len = 0.1

        # Mirror face (disc approximation via lathe)
        profile = [(0.0, 0.0), (mirror_r, 0.0), (mirror_r, frame_thick)]
        dv, df = _make_lathe(profile, segments=10,
                             close_bottom=True, close_top=True)
        parts.append((dv, df))

        # Frame ring
        rv, rf = _make_torus_ring(0, frame_thick / 2, 0,
                                  mirror_r, frame_thick * 0.6,
                                  major_segments=12, minor_segments=4)
        parts.append((rv, rf))

        # Handle
        hv, hf = _make_tapered_cylinder(
            0, -mirror_r - handle_len / 2, 0,
            0.012, 0.008, handle_len,
            segments=6, rings=2,
            cap_top=True, cap_bottom=True,
        )
        # Rotate handle to point downward from mirror
        hv_rot = [(v[0], -mirror_r + (v[1] + mirror_r + handle_len / 2) * -1, v[2])
                  for v in hv]
        # Simpler: just position handle below
        hv2, hf2 = _make_tapered_cylinder(
            0, -(mirror_r + 0.01), 0,
            0.012, 0.008, handle_len,
            segments=6, rings=2,
            cap_top=True, cap_bottom=True,
        )
        parts.append((hv2, hf2))

    elif style == "standing":
        frame_w = 0.015
        frame_d = 0.01

        # Mirror glass (thin flat box)
        gv, gf = _make_box(0, height / 2 + 0.3, 0,
                           width / 2 - frame_w, height / 2, 0.003)
        parts.append((gv, gf))

        # Frame around mirror (4 beveled box strips)
        cy = height / 2 + 0.3
        # Top
        fv, ff = _make_beveled_box(0, cy + height / 2, 0,
                                   width / 2, frame_w / 2, frame_d / 2,
                                   bevel=0.003)
        parts.append((fv, ff))
        # Bottom
        fv2, ff2 = _make_beveled_box(0, cy - height / 2, 0,
                                     width / 2, frame_w / 2, frame_d / 2,
                                     bevel=0.003)
        parts.append((fv2, ff2))
        # Left
        fv3, ff3 = _make_beveled_box(-width / 2, cy, 0,
                                     frame_w / 2, height / 2, frame_d / 2,
                                     bevel=0.003)
        parts.append((fv3, ff3))
        # Right
        fv4, ff4 = _make_beveled_box(width / 2, cy, 0,
                                     frame_w / 2, height / 2, frame_d / 2,
                                     bevel=0.003)
        parts.append((fv4, ff4))

        # Two legs (A-frame)
        leg_h = cy - height / 2
        for side in [-1, 1]:
            lv, lf = _make_tapered_cylinder(
                side * width * 0.4, 0, 0.05,
                0.015, 0.012, leg_h + 0.05,
                segments=6, rings=2,
                cap_top=True, cap_bottom=True,
            )
            parts.append((lv, lf))

        # Rear support strut
        sv, sf = _make_tapered_cylinder(0, 0, 0.12,
                                        0.012, 0.01, leg_h * 0.7,
                                        segments=6, rings=2,
                                        cap_top=True, cap_bottom=True)
        parts.append((sv, sf))

    else:  # wall
        frame_w = 0.02
        frame_d = 0.015

        # Mirror glass
        gv, gf = _make_box(0, 0, 0,
                           width / 2 - frame_w, height / 2 - frame_w, 0.003)
        parts.append((gv, gf))

        # Frame (4 strips)
        # Top
        fv, ff = _make_beveled_box(0, height / 2, 0,
                                   width / 2 + frame_w * 0.3, frame_w / 2, frame_d / 2,
                                   bevel=0.004)
        parts.append((fv, ff))
        # Bottom
        fv2, ff2 = _make_beveled_box(0, -height / 2, 0,
                                     width / 2 + frame_w * 0.3, frame_w / 2, frame_d / 2,
                                     bevel=0.004)
        parts.append((fv2, ff2))
        # Left
        fv3, ff3 = _make_beveled_box(-width / 2, 0, 0,
                                     frame_w / 2, height / 2 + frame_w * 0.3, frame_d / 2,
                                     bevel=0.004)
        parts.append((fv3, ff3))
        # Right
        fv4, ff4 = _make_beveled_box(width / 2, 0, 0,
                                     frame_w / 2, height / 2 + frame_w * 0.3, frame_d / 2,
                                     bevel=0.004)
        parts.append((fv4, ff4))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Mirror_{style}", verts, faces,
                        style=style, category="furniture")


def generate_hay_bale_mesh(
    style: str = "rectangular",
    width: float = 0.9,
    height: float = 0.45,
    depth: float = 0.45,
) -> MeshSpec:
    """Generate a hay bale mesh.

    Args:
        style: "rectangular", "round" (cylindrical), or "scattered" (loose pile).
        width: Bale length along X.
        height: Bale height along Y.
        depth: Bale depth along Z.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "round":
        # Cylindrical hay bale lying on side
        radius = height * 0.8
        length = width
        cv, cf = _make_cylinder(0, radius, 0, radius, length,
                                segments=14, cap_top=True, cap_bottom=True)
        # Rotate to lie along X: swap Y and local axis
        cv_rot = [(v[1] - radius, radius + v[0], v[2]) for v in cv]
        # Re-center along X
        cv_final = [(v[0] - length / 2, v[1] - radius, v[2]) for v in cv_rot]
        parts.append((cv_final, cf))

        # Binding straps (2 torus rings)
        for xpos in [-length * 0.25, length * 0.25]:
            tv, tf = _make_torus_ring(xpos, radius, 0,
                                      radius + 0.005, 0.008,
                                      major_segments=12, minor_segments=4)
            parts.append((tv, tf))

    elif style == "scattered":
        # Loose pile: several small irregular boxes
        import random as _rng
        rng = _rng.Random(42)  # Deterministic
        for _ in range(8):
            sx = rng.uniform(0.05, 0.15)
            sy = rng.uniform(0.02, 0.06)
            sz = rng.uniform(0.03, 0.08)
            px = rng.uniform(-0.3, 0.3)
            py = sy  # sit on ground
            pz = rng.uniform(-0.3, 0.3)
            sv, sf = _make_beveled_box(px, py, pz, sx, sy, sz, bevel=0.005)
            parts.append((sv, sf))

    else:  # rectangular
        # Main bale body with beveled edges
        bv, bf = _make_beveled_box(0, height / 2, 0,
                                   width / 2, height / 2, depth / 2,
                                   bevel=0.01)
        parts.append((bv, bf))

        # Binding straps (2 thin bands)
        strap_h = 0.005
        strap_w = 0.015
        for xpos in [-width * 0.25, width * 0.25]:
            # Top strap
            sv, sf = _make_box(xpos, height + strap_h / 2, 0,
                               strap_w / 2, strap_h / 2, depth / 2 + 0.005)
            parts.append((sv, sf))
            # Side straps (front + back)
            for zm in [-1, 1]:
                ssv, ssf = _make_box(xpos, height / 2, zm * (depth / 2 + strap_h / 2),
                                     strap_w / 2, height / 2, strap_h / 2)
                parts.append((ssv, ssf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"HayBale_{style}", verts, faces,
                        style=style, category="furniture")


def generate_wine_rack_mesh(
    style: str = "wall",
    cols: int = 4,
    rows: int = 3,
    cell_size: float = 0.12,
) -> MeshSpec:
    """Generate a wine rack mesh with a grid of bottle slots.

    Args:
        style: "wall" (wall-mounted grid), "diamond" (X-pattern slots),
               or "barrel" (built into barrel end).
        cols: Number of columns.
        rows: Number of rows.
        cell_size: Size of each bottle slot.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    total_w = cols * cell_size + 0.04
    total_h = rows * cell_size + 0.04
    depth = cell_size * 1.8
    frame_thick = 0.015

    if style == "diamond":
        # Diamond / X-pattern rack
        # Outer frame
        fv, ff = _make_beveled_box(0, total_h / 2, 0,
                                   total_w / 2, total_h / 2, depth / 2,
                                   bevel=0.005)
        parts.append((fv, ff))

        # X-pattern dividers
        div_thick = 0.008
        for r in range(rows + 1):
            for c in range(cols + 1):
                cx = -total_w / 2 + 0.02 + c * cell_size
                cy = 0.02 + r * cell_size
                if c < cols and r < rows:
                    # Horizontal divider piece
                    hv, hf = _make_box(cx + cell_size / 2, cy + cell_size / 2, 0,
                                       cell_size / 2 - 0.005, div_thick / 2, depth / 2 - 0.01)
                    parts.append((hv, hf))

    elif style == "barrel":
        # Barrel end with bottle holes
        barrel_r = max(total_w, total_h) * 0.6
        profile = [(barrel_r, -depth / 2), (barrel_r, depth / 2)]
        bv, bf = _make_lathe(profile, segments=12,
                             close_bottom=True, close_top=True)
        parts.append((bv, bf))

        # Grid of cylindrical cutouts approximated as small cylinders
        for r in range(rows):
            for c in range(cols):
                cx = -cols * cell_size / 2 + c * cell_size + cell_size / 2
                cy = -rows * cell_size / 2 + r * cell_size + cell_size / 2
                rv, rf = _make_cylinder(cx, cy, -depth / 2,
                                        cell_size * 0.35, depth,
                                        segments=6, cap_top=False, cap_bottom=False)
                # Re-orient: swap y/z for depth along Z
                rv_rot = [(v[0], v[2] + cy, v[1] - cy + cy) for v in rv]
                parts.append((rv_rot, rf))

    else:  # wall
        # Outer frame
        fv, ff = _make_beveled_box(0, total_h / 2, 0,
                                   total_w / 2, total_h / 2, depth / 2,
                                   bevel=0.005)
        parts.append((fv, ff))

        # Grid dividers -- horizontal bars
        for r in range(rows + 1):
            hy = 0.02 + r * cell_size
            hv, hf = _make_box(0, hy, 0,
                               total_w / 2 - frame_thick,
                               frame_thick / 2, depth / 2 - 0.005)
            parts.append((hv, hf))

        # Vertical dividers
        for c in range(cols + 1):
            vx = -total_w / 2 + 0.02 + c * cell_size
            vv, vf = _make_box(vx, total_h / 2, 0,
                               frame_thick / 2,
                               total_h / 2 - frame_thick,
                               depth / 2 - 0.005)
            parts.append((vv, vf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"WineRack_{style}", verts, faces,
                        style=style, cols=cols, rows=rows, category="furniture")


def generate_bathtub_mesh(
    style: str = "wooden",
    length: float = 1.4,
    width: float = 0.7,
    height: float = 0.6,
) -> MeshSpec:
    """Generate a bathtub mesh.

    Args:
        style: "wooden" (barrel-like tub), or "metal" (clawfoot cast iron).
        length: Tub length along X.
        width: Tub width along Z.
        height: Tub height along Y.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "metal":
        # Clawfoot bathtub -- elongated oval profile
        segments = 16
        rings = 6
        wall_thick = 0.025

        # Outer shell via lathe-like approach: build elliptical cross-sections
        verts_outer: list[tuple[float, float, float]] = []
        faces_outer: list[tuple[int, ...]] = []

        for ri in range(rings + 1):
            t = ri / rings
            y = t * height
            # Taper slightly toward bottom
            scale = 0.85 + 0.15 * t
            rx = length / 2 * scale
            rz = width / 2 * scale
            for si in range(segments):
                angle = 2.0 * math.pi * si / segments
                verts_outer.append((
                    rx * math.cos(angle),
                    y,
                    rz * math.sin(angle),
                ))

        # Side faces
        for ri in range(rings):
            for si in range(segments):
                s2 = (si + 1) % segments
                r0 = ri * segments
                r1 = (ri + 1) * segments
                faces_outer.append((r0 + si, r0 + s2, r1 + s2, r1 + si))

        # Bottom cap
        faces_outer.append(tuple(range(segments - 1, -1, -1)))

        parts.append((verts_outer, faces_outer))

        # Rolled rim at top (torus ring)
        rim_r = 0.018
        # Approximate elliptical rim with individual torus segments
        for si in range(segments):
            angle = 2.0 * math.pi * si / segments
            rx = length / 2
            rz = width / 2
            px = rx * math.cos(angle)
            pz = rz * math.sin(angle)
            sv, sf = _make_sphere(px, height, pz, rim_r, rings=3, sectors=4)
            parts.append((sv, sf))

        # 4 claw feet
        foot_h = 0.06
        for xm in [-1, 1]:
            for zm in [-1, 1]:
                fx = xm * length * 0.3
                fz = zm * width * 0.25
                # Claw shape: tapered cylinder + sphere
                fv, ff = _make_tapered_cylinder(fx, -foot_h, fz,
                                                0.025, 0.015, foot_h,
                                                segments=6, rings=2,
                                                cap_top=True, cap_bottom=True)
                parts.append((fv, ff))
                # Ball under claw
                bv, bf = _make_sphere(fx, -foot_h, fz, 0.018,
                                      rings=3, sectors=5)
                parts.append((bv, bf))

    else:  # wooden
        # Barrel-like wooden tub: cylinder with staves implied
        segments = 16
        outer_r_x = length / 2
        outer_r_z = width / 2
        inner_offset = 0.03

        # Outer wall
        verts_all: list[tuple[float, float, float]] = []
        faces_all: list[tuple[int, ...]] = []

        rings_count = 4
        for ri in range(rings_count + 1):
            t = ri / rings_count
            y = t * height
            # Slight barrel bulge
            bulge = 1.0 + 0.05 * math.sin(t * math.pi)
            for si in range(segments):
                angle = 2.0 * math.pi * si / segments
                verts_all.append((
                    outer_r_x * bulge * math.cos(angle),
                    y,
                    outer_r_z * bulge * math.sin(angle),
                ))

        for ri in range(rings_count):
            for si in range(segments):
                s2 = (si + 1) % segments
                r0 = ri * segments
                r1 = (ri + 1) * segments
                faces_all.append((r0 + si, r0 + s2, r1 + s2, r1 + si))

        # Bottom cap
        faces_all.append(tuple(range(segments - 1, -1, -1)))

        parts.append((verts_all, faces_all))

        # Metal bands (2 torus rings)
        for band_t in [0.25, 0.75]:
            band_y = band_t * height
            bulge = 1.0 + 0.05 * math.sin(band_t * math.pi)
            # Approximate elliptical band
            band_r = (outer_r_x * bulge + outer_r_z * bulge) / 2
            tv, tf = _make_torus_ring(0, band_y, 0,
                                      band_r + 0.005, 0.008,
                                      major_segments=16, minor_segments=4)
            parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bathtub_{style}", verts, faces,
                        style=style, category="furniture")


def generate_fireplace_mesh(
    style: str = "stone",
    width: float = 1.2,
    height: float = 1.0,
    depth: float = 0.5,
) -> MeshSpec:
    """Generate a fireplace mesh with surround, mantel, hearth, and firebox.

    Args:
        style: "stone" (rustic), "grand" (ornate mantel + columns), or "simple" (hearth only).
        width: Fireplace width along X.
        height: Fireplace height along Y.
        depth: Fireplace depth along Z.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    wall_thick = 0.06
    firebox_w = width * 0.55
    firebox_h = height * 0.5
    firebox_d = depth * 0.7

    if style == "simple":
        # Simple hearth: just a raised stone platform + back wall + fire area
        # Hearth platform
        hearth_h = 0.08
        hearth_w = width * 0.8
        hearth_d = depth * 0.5
        hv, hf = _make_beveled_box(0, hearth_h / 2, 0,
                                   hearth_w / 2, hearth_h / 2, hearth_d / 2,
                                   bevel=0.008)
        parts.append((hv, hf))

        # Back wall
        bw_h = height * 0.6
        bw, bf = _make_beveled_box(0, hearth_h + bw_h / 2, depth * 0.35,
                                   hearth_w / 2 + 0.02, bw_h / 2, wall_thick / 2,
                                   bevel=0.005)
        parts.append((bw, bf))

        # Side walls
        for side in [-1, 1]:
            sv, sf = _make_beveled_box(
                side * hearth_w / 2, hearth_h + bw_h * 0.3, depth * 0.2,
                wall_thick / 2, bw_h * 0.3, hearth_d * 0.3,
                bevel=0.005,
            )
            parts.append((sv, sf))

    else:
        # Full fireplace surround (stone or grand)

        # Back panel (full height)
        bv, bf = _make_beveled_box(0, height / 2, depth / 2 - wall_thick / 2,
                                   width / 2, height / 2, wall_thick / 2,
                                   bevel=0.005)
        parts.append((bv, bf))

        # Left surround pillar
        for side in [-1, 1]:
            pv, pf = _make_beveled_box(
                side * (firebox_w / 2 + wall_thick / 2), height * 0.4, 0,
                wall_thick / 2, height * 0.4, depth / 2 - wall_thick,
                bevel=0.005,
            )
            parts.append((pv, pf))

        # Firebox interior (recessed cavity)
        fbv, fbf = _make_box(0, firebox_h / 2 + 0.02, depth * 0.1,
                             firebox_w / 2 - 0.01, firebox_h / 2,
                             firebox_d / 2)
        parts.append((fbv, fbf))

        # Hearth (floor extension)
        hearth_h = 0.06
        hearth_extend = 0.15
        hhv, hhf = _make_beveled_box(0, hearth_h / 2, -hearth_extend / 2,
                                     width / 2 + 0.05, hearth_h / 2,
                                     depth / 2 + hearth_extend / 2,
                                     bevel=0.008)
        parts.append((hhv, hhf))

        # Mantel shelf
        mantel_h = 0.04
        mantel_overhang = 0.06
        mv, mf = _make_beveled_box(
            0, height * 0.8 + mantel_h / 2, -mantel_overhang / 2,
            width / 2 + mantel_overhang, mantel_h / 2,
            depth * 0.3 + mantel_overhang,
            bevel=0.006,
        )
        parts.append((mv, mf))

        # Arch over firebox
        arch_segs = 8
        arch_r = firebox_w / 2
        arch_cy = firebox_h + 0.02
        for i in range(arch_segs + 1):
            t = i / arch_segs
            angle = math.pi * t
            ax = math.cos(angle) * arch_r
            ay = arch_cy + math.sin(angle) * arch_r * 0.3
            av, af = _make_beveled_box(ax, ay, 0,
                                       0.025, 0.025, depth * 0.15,
                                       bevel=0.004)
            parts.append((av, af))

        if style == "grand":
            # Ornate columns flanking firebox
            col_r = 0.04
            col_h = height * 0.75
            for side in [-1, 1]:
                cx = side * (firebox_w / 2 + wall_thick + col_r + 0.01)
                cv, cf = _make_tapered_cylinder(cx, 0, -depth * 0.1,
                                                col_r, col_r * 0.85, col_h,
                                                segments=10, rings=5,
                                                cap_top=True, cap_bottom=True)
                parts.append((cv, cf))

                # Column capital (sphere)
                capv, capf = _make_sphere(cx, col_h + col_r * 0.5, -depth * 0.1,
                                          col_r * 1.2, rings=4, sectors=8)
                parts.append((capv, capf))

                # Column base (wider disc)
                basev, basef = _make_cylinder(cx, 0, -depth * 0.1,
                                              col_r * 1.5, 0.03,
                                              segments=10,
                                              cap_top=True, cap_bottom=True)
                parts.append((basev, basef))

            # Decorative keystone at arch apex
            ksv, ksf = _make_beveled_box(0, arch_cy + arch_r * 0.3 + 0.03, -depth * 0.05,
                                         0.04, 0.04, depth * 0.1,
                                         bevel=0.005)
            parts.append((ksv, ksf))

        # Chimney stack above mantel
        chimney_w = firebox_w * 0.6
        chimney_h = height * 0.18
        chv, chf = _make_beveled_box(0, height + chimney_h / 2, depth * 0.25,
                                     chimney_w / 2, chimney_h / 2, depth * 0.2,
                                     bevel=0.005)
        parts.append((chv, chf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Fireplace_{style}", verts, faces,
                        style=style, category="furniture")


# =========================================================================
# CATEGORY: ITEMS & CONSUMABLES
# =========================================================================


def generate_health_potion_mesh(style: str = "small") -> MeshSpec:
    """Generate a health potion bottle mesh.

    Args:
        style: "small" (8cm), "medium" (12cm), or "large" (15cm).
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10
    scale = {"small": 0.08, "medium": 0.12, "large": 0.15}.get(style, 0.08)
    h = scale

    if style == "small":
        profile = [
            (0.001, 0), (h * 0.35, h * 0.03), (h * 0.50, h * 0.12),
            (h * 0.55, h * 0.30), (h * 0.52, h * 0.50), (h * 0.40, h * 0.62),
            (h * 0.18, h * 0.72), (h * 0.14, h * 0.78), (h * 0.14, h * 0.88),
            (h * 0.16, h * 0.90), (h * 0.14, h * 0.92),
        ]
    elif style == "medium":
        profile = [
            (0.001, 0), (h * 0.30, h * 0.02), (h * 0.45, h * 0.08),
            (h * 0.50, h * 0.20), (h * 0.52, h * 0.35), (h * 0.50, h * 0.50),
            (h * 0.42, h * 0.58), (h * 0.28, h * 0.65), (h * 0.15, h * 0.72),
            (h * 0.12, h * 0.78), (h * 0.12, h * 0.88), (h * 0.14, h * 0.90),
            (h * 0.12, h * 0.93),
        ]
    else:
        profile = [
            (0.001, 0), (h * 0.28, h * 0.02), (h * 0.42, h * 0.06),
            (h * 0.48, h * 0.14), (h * 0.50, h * 0.25), (h * 0.50, h * 0.45),
            (h * 0.48, h * 0.55), (h * 0.38, h * 0.62), (h * 0.22, h * 0.68),
            (h * 0.14, h * 0.74), (h * 0.12, h * 0.80), (h * 0.12, h * 0.90),
            (h * 0.15, h * 0.92), (h * 0.12, h * 0.95),
        ]

    bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((bv, bf))
    cork_y = profile[-1][1]
    sv, sf = _make_cylinder(0, cork_y, 0, h * 0.10, h * 0.08, segments=6)
    parts.append((sv, sf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"HealthPotion_{style}", verts, faces,
                        style=style, category="consumable")


def generate_mana_potion_mesh(style: str = "small") -> MeshSpec:
    """Generate a mana potion bottle mesh -- angular/ornate shape.

    Args:
        style: "small", "medium", or "large".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    scale = {"small": 0.08, "medium": 0.12, "large": 0.15}.get(style, 0.08)
    h = scale

    if style == "small":
        profile = [
            (0.001, 0), (h * 0.20, h * 0.02), (h * 0.45, h * 0.10),
            (h * 0.48, h * 0.35), (h * 0.45, h * 0.55), (h * 0.20, h * 0.65),
            (h * 0.12, h * 0.70), (h * 0.12, h * 0.85), (h * 0.15, h * 0.88),
            (h * 0.12, h * 0.92),
        ]
    elif style == "medium":
        profile = [
            (0.001, 0), (h * 0.18, h * 0.02), (h * 0.40, h * 0.08),
            (h * 0.50, h * 0.15), (h * 0.52, h * 0.30), (h * 0.50, h * 0.48),
            (h * 0.38, h * 0.58), (h * 0.18, h * 0.66), (h * 0.12, h * 0.72),
            (h * 0.10, h * 0.82), (h * 0.10, h * 0.90), (h * 0.13, h * 0.92),
            (h * 0.10, h * 0.95),
        ]
    else:
        profile = [
            (0.001, 0), (h * 0.22, h * 0.02), (h * 0.42, h * 0.06),
            (h * 0.55, h * 0.12), (h * 0.58, h * 0.28), (h * 0.55, h * 0.45),
            (h * 0.42, h * 0.55), (h * 0.22, h * 0.64), (h * 0.14, h * 0.70),
            (h * 0.10, h * 0.78), (h * 0.10, h * 0.88), (h * 0.14, h * 0.90),
            (h * 0.10, h * 0.94),
        ]

    bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((bv, bf))
    cork_y = profile[-1][1]
    sv, sf = _make_cone(0, cork_y, 0, h * 0.08, h * 0.12, segments=segs)
    parts.append((sv, sf))
    neck_y = profile[-4][1] if len(profile) > 4 else h * 0.70
    rv, rf = _make_torus_ring(0, neck_y, 0, h * 0.16, h * 0.02,
                              major_segments=segs, minor_segments=4)
    parts.append((rv, rf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"ManaPotion_{style}", verts, faces,
                        style=style, category="consumable")


def generate_antidote_mesh(style: str = "vial") -> MeshSpec:
    """Generate an antidote vial mesh with wax seal.

    Args:
        style: "vial", "ampoule", or "flask".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    h = 0.10
    segs = 10

    if style == "vial":
        profile = [
            (0.001, 0), (h * 0.15, h * 0.02), (h * 0.20, h * 0.08),
            (h * 0.22, h * 0.40), (h * 0.20, h * 0.55), (h * 0.10, h * 0.65),
            (h * 0.06, h * 0.70), (h * 0.06, h * 0.88), (h * 0.08, h * 0.90),
            (h * 0.06, h * 0.93),
        ]
    elif style == "ampoule":
        profile = [
            (0.001, 0), (h * 0.12, h * 0.02), (h * 0.18, h * 0.10),
            (h * 0.20, h * 0.35), (h * 0.18, h * 0.50), (h * 0.05, h * 0.60),
            (h * 0.04, h * 0.65), (h * 0.10, h * 0.75), (h * 0.12, h * 0.85),
            (h * 0.08, h * 0.95), (h * 0.001, h * 1.0),
        ]
    else:
        profile = [
            (0.001, 0), (h * 0.20, h * 0.02), (h * 0.30, h * 0.10),
            (h * 0.32, h * 0.35), (h * 0.30, h * 0.50), (h * 0.15, h * 0.60),
            (h * 0.08, h * 0.68), (h * 0.08, h * 0.85), (h * 0.10, h * 0.88),
            (h * 0.08, h * 0.92),
        ]

    bv, bf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
    parts.append((bv, bf))
    if style != "ampoule":
        seal_y = profile[-1][1]
        wv, wf = _make_cylinder(0, seal_y, 0, h * 0.09, h * 0.03, segments=8)
        parts.append((wv, wf))
    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Antidote_{style}", verts, faces,
                        style=style, category="consumable")


def generate_bread_mesh(style: str = "loaf") -> MeshSpec:
    """Generate a bread mesh.

    Args:
        style: "loaf", "roll", or "flatbread".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "loaf":
        width = 0.10
        height = 0.08
        length = 0.20
        sv, sf = _make_sphere(0, height, 0, 1.0, rings=6, sectors=10)
        sv = [(v[0] * width, v[1] * height, v[2] * length) for v in sv]
        sv = [(v[0], max(v[1], 0.0), v[2]) for v in sv]
        parts.append((sv, sf))
        for i in range(3):
            z_off = -0.06 + i * 0.06
            sv2, sf2 = _make_box(0, height * 1.6, z_off, width * 0.6, 0.003, 0.005)
            parts.append((sv2, sf2))
    elif style == "roll":
        sv, sf = _make_sphere(0, 0.04, 0, 0.04, rings=6, sectors=8)
        sv = [(v[0], max(v[1], 0.0), v[2]) for v in sv]
        parts.append((sv, sf))
        sv2, sf2 = _make_box(0, 0.075, 0, 0.03, 0.002, 0.003)
        parts.append((sv2, sf2))
        sv3, sf3 = _make_box(0, 0.075, 0, 0.003, 0.002, 0.03)
        parts.append((sv3, sf3))
    else:
        profile = [
            (0.001, 0), (0.10, 0.002), (0.12, 0.008),
            (0.12, 0.015), (0.10, 0.020), (0.001, 0.022),
        ]
        bv, bf = _make_lathe(profile, segments=12, close_bottom=True, close_top=True)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bread_{style}", verts, faces,
                        style=style, category="consumable")


def generate_cheese_mesh(style: str = "wheel") -> MeshSpec:
    """Generate a cheese mesh.

    Args:
        style: "wheel", "wedge", or "block".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "wheel":
        cv, cf = _make_cylinder(0, 0, 0, 0.10, 0.05, segments=16)
        parts.append((cv, cf))
        rv, rf = _make_torus_ring(0, 0.025, 0, 0.10, 0.008,
                                  major_segments=16, minor_segments=4)
        parts.append((rv, rf))
    elif style == "wedge":
        w = 0.10
        h_val = 0.05
        d = 0.12
        verts_raw: list[tuple[float, float, float]] = [
            (0, 0, 0), (w, 0, 0), (0, 0, d),
            (0, h_val, 0), (w, h_val, 0), (0, h_val, d),
        ]
        faces_raw: list[tuple[int, ...]] = [
            (0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (0, 3, 5, 2),
        ]
        parts.append((verts_raw, faces_raw))
    else:
        bv, bf = _make_beveled_box(0, 0.03, 0, 0.06, 0.03, 0.08, bevel=0.005)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cheese_{style}", verts, faces,
                        style=style, category="consumable")


def generate_meat_mesh(style: str = "drumstick") -> MeshSpec:
    """Generate a cooked meat mesh.

    Args:
        style: "drumstick", "steak", or "ham".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "drumstick":
        bv, bf = _make_cylinder(0, 0, 0, 0.008, 0.12, segments=6)
        parts.append((bv, bf))
        kv, kf = _make_sphere(0, 0, 0, 0.012, rings=4, sectors=6)
        parts.append((kv, kf))
        mv, mf = _make_sphere(0, 0.10, 0, 0.04, rings=6, sectors=8)
        mv = [(v[0] * 1.1, v[1], v[2] * 1.1) for v in mv]
        parts.append((mv, mf))
    elif style == "steak":
        profile = [
            (0.001, 0), (0.06, 0.003), (0.08, 0.01),
            (0.08, 0.02), (0.06, 0.027), (0.001, 0.03),
        ]
        sv, sf = _make_lathe(profile, segments=10, close_bottom=True, close_top=True)
        sv = [(v[0], v[1], v[2] * 1.4) for v in sv]
        parts.append((sv, sf))
        tv, tf = _make_box(0, 0.015, 0, 0.002, 0.015, 0.06)
        parts.append((tv, tf))
        tv2, tf2 = _make_box(0, 0.015, -0.05, 0.03, 0.008, 0.003)
        parts.append((tv2, tf2))
    else:
        profile = [
            (0.001, 0), (0.04, 0.01), (0.07, 0.04), (0.08, 0.10),
            (0.07, 0.16), (0.05, 0.20), (0.03, 0.22), (0.015, 0.24),
        ]
        hv, hf = _make_lathe(profile, segments=10, close_bottom=True, close_top=True)
        parts.append((hv, hf))
        bv, bf = _make_cylinder(0, 0.24, 0, 0.008, 0.04, segments=6)
        parts.append((bv, bf))
        kv, kf = _make_sphere(0, 0.28, 0, 0.012, rings=4, sectors=6)
        parts.append((kv, kf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Meat_{style}", verts, faces,
                        style=style, category="consumable")


def generate_apple_mesh(style: str = "whole") -> MeshSpec:
    """Generate a fruit (apple) mesh.

    Args:
        style: "whole", "bitten", or "rotten".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    r = 0.035

    if style == "whole":
        profile = [
            (0.001, 0), (r * 0.30, r * 0.08), (r * 0.70, r * 0.20),
            (r * 0.95, r * 0.45), (r * 1.0, r * 0.70), (r * 0.95, r * 0.90),
            (r * 0.80, r * 1.05), (r * 0.50, r * 1.15), (r * 0.20, r * 1.20),
            (r * 0.05, r * 1.22),
        ]
        av, af = _make_lathe(profile, segments=10, close_bottom=True, close_top=True)
        parts.append((av, af))
        sv, sf = _make_cylinder(0, r * 1.22, 0, r * 0.06, r * 0.30, segments=4)
        parts.append((sv, sf))
        lv, lf = _make_box(r * 0.10, r * 1.40, 0, r * 0.20, r * 0.02, r * 0.08)
        parts.append((lv, lf))
    elif style == "bitten":
        profile = [
            (0.001, 0), (r * 0.30, r * 0.08), (r * 0.70, r * 0.20),
            (r * 0.95, r * 0.45), (r * 1.0, r * 0.70), (r * 0.95, r * 0.90),
            (r * 0.80, r * 1.05), (r * 0.50, r * 1.15), (r * 0.20, r * 1.20),
            (r * 0.05, r * 1.22),
        ]
        av, af = _make_lathe(profile, segments=10, close_bottom=True, close_top=True)
        parts.append((av, af))
        bv, bf = _make_sphere(r * 0.8, r * 0.65, 0, r * 0.45, rings=4, sectors=6)
        parts.append((bv, bf))
        sv, sf = _make_cylinder(0, r * 1.22, 0, r * 0.06, r * 0.30, segments=4)
        parts.append((sv, sf))
    else:
        profile = [
            (0.001, 0), (r * 0.35, r * 0.05), (r * 0.75, r * 0.15),
            (r * 0.90, r * 0.35), (r * 0.85, r * 0.55), (r * 0.70, r * 0.70),
            (r * 0.45, r * 0.80), (r * 0.20, r * 0.85), (r * 0.05, r * 0.88),
        ]
        av, af = _make_lathe(profile, segments=10, close_bottom=True, close_top=True)
        import random as _rng
        gen = _rng.Random(42)
        av = [(v[0] + gen.uniform(-r * 0.08, r * 0.08),
               v[1] + gen.uniform(-r * 0.04, r * 0.04),
               v[2] + gen.uniform(-r * 0.08, r * 0.08)) for v in av]
        parts.append((av, af))
        sv, sf = _make_cylinder(r * 0.01, r * 0.85, 0, r * 0.05, r * 0.15, segments=4)
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Apple_{style}", verts, faces,
                        style=style, category="consumable")


def generate_mushroom_food_mesh(style: str = "cap") -> MeshSpec:
    """Generate an edible mushroom mesh (smaller than scatter mushrooms).

    Args:
        style: "cap" or "cluster".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    def _single_mush(
        cx: float, cz: float, mh: float, cap_r: float,
    ) -> list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]]:
        p: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
        sv, sf = _make_tapered_cylinder(cx, 0, cz, mh * 0.12, mh * 0.08,
                                        mh * 0.65, segments=6, rings=2)
        p.append((sv, sf))
        cap_profile = [
            (0.001, 0), (cap_r * 0.50, cap_r * 0.10), (cap_r * 0.90, cap_r * 0.30),
            (cap_r * 1.0, cap_r * 0.50), (cap_r * 0.80, cap_r * 0.70),
            (cap_r * 0.40, cap_r * 0.80), (cap_r * 0.10, cap_r * 0.85),
        ]
        cap_profile = [(rr, y + mh * 0.55) for rr, y in cap_profile]
        cv, cf = _make_lathe(cap_profile, segments=8, close_bottom=True, close_top=True)
        cv = [(v[0] + cx, v[1], v[2] + cz) for v in cv]
        p.append((cv, cf))
        return p

    if style == "cap":
        parts.extend(_single_mush(0, 0, 0.04, 0.02))
    else:
        parts.extend(_single_mush(0, 0, 0.04, 0.02))
        parts.extend(_single_mush(0.025, 0.015, 0.035, 0.018))
        parts.extend(_single_mush(-0.015, 0.02, 0.03, 0.015))
        parts.extend(_single_mush(0.01, -0.02, 0.028, 0.014))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MushroomFood_{style}", verts, faces,
                        style=style, category="consumable")


def generate_fish_mesh(style: str = "whole") -> MeshSpec:
    """Generate a fish mesh.

    Args:
        style: "whole" or "fillet".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "whole":
        profile = [
            (0.001, 0), (0.015, 0.01), (0.030, 0.03), (0.035, 0.06),
            (0.035, 0.10), (0.030, 0.14), (0.020, 0.17), (0.010, 0.20),
            (0.005, 0.22),
        ]
        fv, ff = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
        fv = [(v[0], v[1], v[2] * 0.5) for v in fv]
        fv = [(v[0], v[2] + 0.02, v[1]) for v in fv]
        parts.append((fv, ff))
        tail_v: list[tuple[float, float, float]] = [
            (0, 0.02, 0.22), (0.04, 0.02, 0.25),
            (0, 0.02, 0.28), (-0.04, 0.02, 0.25),
        ]
        parts.append((tail_v, [(0, 1, 2, 3)]))
        dv: list[tuple[float, float, float]] = [
            (0, 0.035, 0.06), (0, 0.05, 0.10), (0, 0.035, 0.14),
        ]
        parts.append((dv, [(0, 1, 2)]))
        ev, ef = _make_sphere(0.02, 0.025, 0.04, 0.005, rings=3, sectors=4)
        parts.append((ev, ef))
    else:
        profile = [
            (0.001, 0), (0.04, 0.003), (0.05, 0.008),
            (0.05, 0.012), (0.04, 0.015), (0.001, 0.018),
        ]
        fv, ff = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
        fv = [(v[0], v[1], v[2] * 2.0) for v in fv]
        parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Fish_{style}", verts, faces,
                        style=style, category="consumable")


# =========================================================================
# CATEGORY: CRAFTING MATERIALS
# =========================================================================


def generate_ore_mesh(style: str = "iron") -> MeshSpec:
    """Generate a raw ore chunk mesh.

    Args:
        style: "iron", "copper", "gold", or "dark_crystal".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    import random as _rng
    seed_map = {"iron": 10, "copper": 20, "gold": 30, "dark_crystal": 40}
    gen = _rng.Random(seed_map.get(style, 10))

    if style == "dark_crystal":
        for ci in range(4):
            angle = ci * math.pi * 2 / 4 + gen.uniform(-0.3, 0.3)
            dist = gen.uniform(0.01, 0.03)
            cx = math.cos(angle) * dist
            cz = math.sin(angle) * dist
            cr_h = gen.uniform(0.04, 0.08)
            cr_r = gen.uniform(0.01, 0.02)
            cv, cf = _make_tapered_cylinder(cx, 0, cz, cr_r, cr_r * 0.1, cr_h,
                                            segments=5, rings=1)
            parts.append((cv, cf))
        bv, bf = _make_sphere(0, 0.01, 0, 0.035, rings=4, sectors=6)
        bv = [(v[0], max(v[1], 0.0), v[2]) for v in bv]
        parts.append((bv, bf))
    else:
        base_r = {"iron": 0.04, "copper": 0.045, "gold": 0.035}.get(style, 0.04)
        sv, sf = _make_sphere(0, base_r, 0, base_r, rings=4, sectors=6)
        sv = [(v[0] + gen.uniform(-base_r * 0.3, base_r * 0.3),
               max(v[1] + gen.uniform(-base_r * 0.2, base_r * 0.2), 0.0),
               v[2] + gen.uniform(-base_r * 0.3, base_r * 0.3)) for v in sv]
        parts.append((sv, sf))
        frag_r = base_r * 0.5
        offset_x = gen.uniform(base_r * 0.6, base_r * 0.9)
        fv, ff = _make_sphere(offset_x, frag_r, 0, frag_r, rings=3, sectors=5)
        fv = [(v[0] + gen.uniform(-frag_r * 0.2, frag_r * 0.2),
               max(v[1] + gen.uniform(-frag_r * 0.15, frag_r * 0.15), 0.0),
               v[2] + gen.uniform(-frag_r * 0.2, frag_r * 0.2)) for v in fv]
        parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Ore_{style}", verts, faces,
                        style=style, category="crafting_material")


def generate_leather_mesh(style: str = "folded") -> MeshSpec:
    """Generate a leather material mesh.

    Args:
        style: "folded", "strip", or "hide".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "folded":
        for i in range(3):
            y = i * 0.012
            offset_x = i * 0.005 - 0.005
            offset_z = i * 0.003 - 0.003
            sv, sf = _make_beveled_box(offset_x, y + 0.005, offset_z,
                                       0.06, 0.004, 0.08, bevel=0.002)
            parts.append((sv, sf))
    elif style == "strip":
        strip_segs = 8
        strip_l = 0.20
        for i in range(strip_segs):
            t = i / (strip_segs - 1)
            z = -strip_l / 2 + t * strip_l
            y = 0.003 + math.sin(t * math.pi) * 0.01
            sv, sf = _make_box(0, y, z, 0.01, 0.002, strip_l / strip_segs * 0.55)
            parts.append((sv, sf))
    else:
        profile = [
            (0.001, 0), (0.08, 0.001), (0.14, 0.003),
            (0.15, 0.005), (0.14, 0.007), (0.08, 0.009), (0.001, 0.010),
        ]
        hv, hf = _make_lathe(profile, segments=12, close_bottom=True, close_top=True)
        import random as _rng
        gen = _rng.Random(77)
        hv = [(v[0] + gen.uniform(-0.01, 0.01), v[1],
               v[2] + gen.uniform(-0.01, 0.01)) for v in hv]
        parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Leather_{style}", verts, faces,
                        style=style, category="crafting_material")


def generate_herb_mesh(style: str = "leaf") -> MeshSpec:
    """Generate a medicinal herb mesh.

    Args:
        style: "leaf", "bundle", or "flower".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "leaf":
        sv, sf = _make_cylinder(0, 0, 0, 0.002, 0.08, segments=4)
        parts.append((sv, sf))
        lv1: list[tuple[float, float, float]] = [
            (0, 0.05, 0), (0.02, 0.065, 0.002), (0, 0.09, 0), (-0.02, 0.065, -0.002),
        ]
        lf1: list[tuple[int, ...]] = [(0, 1, 2, 3)]
        parts.append((lv1, lf1))
        lv2: list[tuple[float, float, float]] = [
            (0, 0.03, 0), (-0.015, 0.045, -0.002), (0, 0.07, 0), (0.015, 0.045, 0.002),
        ]
        parts.append((lv2, lf1))
    elif style == "bundle":
        for i in range(5):
            angle = i * math.pi * 2 / 5
            cx = math.cos(angle) * 0.008
            cz = math.sin(angle) * 0.008
            sv, sf = _make_cylinder(cx, 0, cz, 0.002, 0.10, segments=4)
            parts.append((sv, sf))
            lv: list[tuple[float, float, float]] = [
                (cx, 0.08, cz), (cx + 0.012, 0.10, cz),
                (cx, 0.12, cz), (cx - 0.012, 0.10, cz),
            ]
            parts.append((lv, [(0, 1, 2, 3)]))
        tv, tf = _make_torus_ring(0, 0.03, 0, 0.012, 0.003,
                                  major_segments=8, minor_segments=4)
        parts.append((tv, tf))
    else:
        sv, sf = _make_cylinder(0, 0, 0, 0.003, 0.07, segments=4)
        parts.append((sv, sf))
        for i in range(5):
            angle = i * math.pi * 2 / 5
            px = math.cos(angle) * 0.015
            pz = math.sin(angle) * 0.015
            pv: list[tuple[float, float, float]] = [
                (0, 0.07, 0), (px * 0.5, 0.072, pz * 0.5),
                (px, 0.068, pz), (px * 0.5, 0.066, pz * 0.5),
            ]
            parts.append((pv, [(0, 1, 2, 3)]))
        cv, cf = _make_sphere(0, 0.072, 0, 0.005, rings=3, sectors=4)
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Herb_{style}", verts, faces,
                        style=style, category="crafting_material")


def generate_gem_mesh(style: str = "ruby") -> MeshSpec:
    """Generate a cut gemstone mesh (brilliant-cut faceted crystal).

    Args:
        style: "ruby", "sapphire", "emerald", "diamond", or "amethyst".
    """
    size_map = {
        "ruby": (0.012, 0.008), "sapphire": (0.014, 0.009),
        "emerald": (0.010, 0.012), "diamond": (0.013, 0.010),
        "amethyst": (0.015, 0.011),
    }
    r, crown_h = size_map.get(style, (0.012, 0.008))
    pavilion_h = r * 1.2
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    n_sides = 8

    table_r = r * 0.55
    for i in range(n_sides):
        angle = 2.0 * math.pi * i / n_sides
        verts.append((table_r * math.cos(angle), crown_h, table_r * math.sin(angle)))
    for i in range(n_sides):
        angle = 2.0 * math.pi * i / n_sides
        verts.append((r * math.cos(angle), 0, r * math.sin(angle)))
    verts.append((0, -pavilion_h, 0))

    faces.append(tuple(range(n_sides)))
    for i in range(n_sides):
        i2 = (i + 1) % n_sides
        faces.append((i, i2, n_sides + i2))
        faces.append((i, n_sides + i2, n_sides + i))
    culet = 2 * n_sides
    for i in range(n_sides):
        i2 = (i + 1) % n_sides
        faces.append((n_sides + i, n_sides + i2, culet))

    return _make_result(f"Gem_{style}", verts, faces,
                        style=style, category="crafting_material")


def generate_bone_shard_mesh(style: str = "fragment") -> MeshSpec:
    """Generate a monster bone drop mesh.

    Args:
        style: "fragment", "fang", or "horn".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "fragment":
        import random as _rng
        gen = _rng.Random(55)
        sv, sf = _make_sphere(0, 0.025, 0, 0.025, rings=4, sectors=6)
        sv = [(v[0] + gen.uniform(-0.008, 0.008),
               max(v[1] + gen.uniform(-0.005, 0.005), 0.0),
               v[2] + gen.uniform(-0.008, 0.008)) for v in sv]
        parts.append((sv, sf))
        spv, spf = _make_tapered_cylinder(0.02, 0, 0, 0.008, 0.002, 0.05,
                                          segments=5, rings=1)
        parts.append((spv, spf))
    elif style == "fang":
        profile = [
            (0.015, 0), (0.018, 0.01), (0.016, 0.03), (0.012, 0.05),
            (0.008, 0.07), (0.003, 0.09), (0.001, 0.10),
        ]
        fv, ff = _make_lathe(profile, segments=6, close_bottom=True, close_top=True)
        parts.append((fv, ff))
        rv, rf = _make_sphere(0, 0.005, 0, 0.02, rings=3, sectors=6)
        rv = [(v[0], max(v[1], 0.0), v[2]) for v in rv]
        parts.append((rv, rf))
    else:
        horn_segs = 8
        horn_r_base = 0.02
        horn_h = 0.12
        for i in range(horn_segs):
            t = i / (horn_segs - 1)
            seg_r = horn_r_base * (1.0 - t * 0.85)
            y = t * horn_h
            x_off = t * t * 0.04
            cv, cf = _make_cylinder(x_off, y, 0, seg_r, horn_h / horn_segs * 0.55,
                                    segments=6)
            parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"BoneShard_{style}", verts, faces,
                        style=style, category="crafting_material")


# =========================================================================
# CATEGORY: CURRENCY
# =========================================================================


def generate_coin_mesh(style: str = "gold") -> MeshSpec:
    """Generate a currency coin mesh with embossed detail.

    Args:
        style: "copper", "silver", or "gold".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    size_map = {"copper": 0.012, "silver": 0.014, "gold": 0.016}
    r = size_map.get(style, 0.014)
    thickness = r * 0.15

    cv, cf = _make_cylinder(0, 0, 0, r, thickness, segments=16)
    parts.append((cv, cf))
    rv, rf = _make_torus_ring(0, thickness / 2, 0, r * 0.90, r * 0.04,
                              major_segments=16, minor_segments=4)
    parts.append((rv, rf))
    ev, ef = _make_cylinder(0, thickness, 0, r * 0.4, r * 0.02, segments=8)
    parts.append((ev, ef))
    ev2, ef2 = _make_cylinder(0, -r * 0.02, 0, r * 0.35, r * 0.02, segments=6)
    parts.append((ev2, ef2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Coin_{style}", verts, faces,
                        style=style, category="currency")


def generate_coin_pouch_mesh(style: str = "small") -> MeshSpec:
    """Generate a coin pouch/money bag mesh.

    Args:
        style: "small" or "large".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10

    if style == "small":
        profile = [
            (0.001, 0), (0.025, 0.005), (0.035, 0.015), (0.040, 0.030),
            (0.038, 0.045), (0.030, 0.055), (0.015, 0.060), (0.008, 0.065),
            (0.010, 0.070), (0.005, 0.075),
        ]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((pv, pf))
        tv, tf = _make_torus_ring(0, 0.062, 0, 0.012, 0.002,
                                  major_segments=8, minor_segments=3)
        parts.append((tv, tf))
        rv, rf = _make_cylinder(0.012, 0.065, 0, 0.001, 0.015, segments=3)
        parts.append((rv, rf))
    else:
        profile = [
            (0.001, 0), (0.06, 0.01), (0.09, 0.03), (0.10, 0.06),
            (0.10, 0.10), (0.08, 0.13), (0.05, 0.15), (0.025, 0.16),
            (0.015, 0.17), (0.020, 0.18), (0.010, 0.19),
        ]
        pv, pf = _make_lathe(profile, segments=segs, close_bottom=True, close_top=True)
        parts.append((pv, pf))
        tv, tf = _make_torus_ring(0, 0.16, 0, 0.022, 0.003,
                                  major_segments=8, minor_segments=3)
        parts.append((tv, tf))
        for ci in range(3):
            angle = ci * math.pi * 2 / 3 + 0.5
            cx = math.cos(angle) * 0.10
            cz = math.sin(angle) * 0.10
            cv, cf = _make_cylinder(cx, 0, cz, 0.014, 0.003, segments=8)
            parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"CoinPouch_{style}", verts, faces,
                        style=style, category="currency")


# =========================================================================
# CATEGORY: KEY ITEMS
# =========================================================================


def generate_key_mesh(style: str = "skeleton") -> MeshSpec:
    """Generate a key mesh.

    Args:
        style: "skeleton", "dungeon", or "master".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "skeleton":
        bv, bf = _make_torus_ring(0, 0.07, 0, 0.018, 0.004,
                                  major_segments=12, minor_segments=4)
        parts.append((bv, bf))
        sv, sf = _make_box(0, 0.035, 0, 0.003, 0.035, 0.003)
        parts.append((sv, sf))
        for i in range(3):
            x_off = 0.006 * (i - 1)
            tooth_h = 0.010 + i * 0.004
            tv, tf = _make_box(x_off, tooth_h / 2, 0.005, 0.002, tooth_h / 2, 0.002)
            parts.append((tv, tf))
        dv, df = _make_sphere(0, 0.07, 0, 0.006, rings=3, sectors=4)
        parts.append((dv, df))
    elif style == "dungeon":
        bv, bf = _make_torus_ring(0, 0.06, 0, 0.012, 0.003,
                                  major_segments=8, minor_segments=3)
        parts.append((bv, bf))
        sv, sf = _make_box(0, 0.03, 0, 0.004, 0.03, 0.004)
        parts.append((sv, sf))
        for i in range(2):
            x_off = 0.006 * (i * 2 - 1)
            tv, tf = _make_box(x_off, 0.006, 0.006, 0.002, 0.006, 0.002)
            parts.append((tv, tf))
    else:
        bv, bf = _make_torus_ring(0, 0.08, 0, 0.022, 0.005,
                                  major_segments=8, minor_segments=5)
        parts.append((bv, bf))
        iv, i_f = _make_torus_ring(0, 0.08, 0, 0.012, 0.002,
                                   major_segments=8, minor_segments=3)
        parts.append((iv, i_f))
        sv, sf = _make_box(0, 0.038, 0, 0.004, 0.038, 0.004)
        parts.append((sv, sf))
        for i in range(4):
            y = 0.015 + i * 0.012
            nv, nf = _make_box(0.005, y, 0, 0.002, 0.003, 0.005)
            parts.append((nv, nf))
        for i in range(4):
            x_off = 0.004 * (i - 1.5)
            tooth_h = 0.006 + (i % 2) * 0.006
            tv, tf = _make_box(x_off, tooth_h / 2, 0.006, 0.002, tooth_h / 2, 0.002)
            parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Key_{style}", verts, faces,
                        style=style, category="key_item")


def generate_map_scroll_mesh(style: str = "rolled") -> MeshSpec:
    """Generate a map/document scroll mesh.

    Args:
        style: "rolled", "open", or "sealed".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "rolled":
        length = 0.18
        scroll_r = 0.014
        sv, sf = _make_cylinder(0, 0, 0, scroll_r, length, segments=10)
        sv = [(v[0], v[2], v[1]) for v in sv]
        parts.append((sv, sf))
        for z_end in [0.0, length]:
            kv, kf = _make_sphere(0, z_end, 0, scroll_r * 1.3, rings=4, sectors=6)
            kv = [(v[0], v[2], v[1]) for v in kv]
            parts.append((kv, kf))
        rv, rf = _make_torus_ring(0, length * 0.5, 0, scroll_r * 1.1, 0.002,
                                  major_segments=8, minor_segments=3)
        rv = [(v[0], v[2], v[1]) for v in rv]
        parts.append((rv, rf))
        tv, tf = _make_box(0, length * 0.5, scroll_r * 1.3, 0.002, 0.025, 0.001)
        tv = [(v[0], v[2], v[1]) for v in tv]
        parts.append((tv, tf))
    elif style == "open":
        map_w = 0.20
        map_h = 0.15
        thickness = 0.002
        sv, sf = _make_box(0, thickness / 2, 0, map_w / 2, thickness / 2, map_h / 2)
        parts.append((sv, sf))
        for sx, sz in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            curl_r = 0.008
            cx = sx * (map_w / 2 - curl_r)
            cz = sz * (map_h / 2 - curl_r)
            cv, cf = _make_cylinder(cx, thickness, cz, curl_r, 0.012, segments=6)
            parts.append((cv, cf))
    else:
        length = 0.16
        scroll_r = 0.012
        sv, sf = _make_cylinder(0, 0, 0, scroll_r, length, segments=10)
        sv = [(v[0], v[2], v[1]) for v in sv]
        parts.append((sv, sf))
        seal_r = 0.015
        wv, wf = _make_cylinder(0, length * 0.5, scroll_r, seal_r, 0.004, segments=8)
        wv = [(v[0], v[2], v[1]) for v in wv]
        parts.append((wv, wf))
        ev, ef = _make_cylinder(0, length * 0.5, scroll_r + 0.004,
                                seal_r * 0.5, 0.002, segments=6)
        ev = [(v[0], v[2], v[1]) for v in ev]
        parts.append((ev, ef))
        rv, rf = _make_box(0, length * 0.5, scroll_r + 0.002,
                           seal_r * 0.8, 0.001, 0.002)
        rv = [(v[0], v[2], v[1]) for v in rv]
        parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MapScroll_{style}", verts, faces,
                        style=style, category="key_item")


def generate_lockpick_mesh(style: str = "set") -> MeshSpec:
    """Generate a lockpick tool set mesh.

    Args:
        style: "set", "single", or "skeleton_key".
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    if style == "set":
        roll_w = 0.08
        roll_h = 0.12
        rv, rf = _make_box(0, 0.002, 0, roll_w / 2, 0.002, roll_h / 2)
        parts.append((rv, rf))
        for i in range(5):
            x = -roll_w / 2 + 0.01 + i * 0.015
            sv, sf = _make_box(x, 0.005, 0, 0.001, 0.001, roll_h * 0.45)
            parts.append((sv, sf))
            tip_z = roll_h * 0.45
            if i % 3 == 0:
                tv, tf = _make_box(x, 0.007, tip_z, 0.002, 0.002, 0.004)
            elif i % 3 == 1:
                tv, tf = _make_box(x, 0.006, tip_z, 0.003, 0.003, 0.003)
            else:
                tv, tf = _make_box(x, 0.005, tip_z, 0.001, 0.001, 0.008)
            parts.append((tv, tf))
            hv, hf = _make_cylinder(x, 0.005, -roll_h * 0.40,
                                    0.003, 0.015, segments=4)
            parts.append((hv, hf))
        tv, tf = _make_box(roll_w / 2 + 0.005, 0.003, 0,
                           0.002, 0.002, roll_h * 0.3)
        parts.append((tv, tf))
    elif style == "single":
        hv, hf = _make_cylinder(0, 0, 0, 0.004, 0.03, segments=6)
        parts.append((hv, hf))
        sv, sf = _make_box(0, 0.03, 0, 0.001, 0.04, 0.001)
        parts.append((sv, sf))
        tv, tf = _make_box(0.003, 0.068, 0, 0.003, 0.003, 0.001)
        parts.append((tv, tf))
    else:
        hv, hf = _make_torus_ring(0, 0, 0, 0.008, 0.003,
                                  major_segments=8, minor_segments=4)
        parts.append((hv, hf))
        sv, sf = _make_box(0, 0.04, 0, 0.0015, 0.04, 0.0015)
        parts.append((sv, sf))
        tv, tf = _make_box(0, 0.078, 0, 0.004, 0.004, 0.001)
        parts.append((tv, tf))
        tv2, tf2 = _make_box(0.004, 0.074, 0, 0.001, 0.008, 0.001)
        parts.append((tv2, tf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Lockpick_{style}", verts, faces,
                        style=style, category="key_item")


# =========================================================================
# CATEGORY: OUTDOOR STRUCTURES & FORTIFICATIONS
# =========================================================================


def generate_palisade_mesh(
    style: str = "pointed",
    width: float = 3.0,
    height: float = 2.5,
) -> MeshSpec:
    """Generate a palisade wall section.

    Args:
        style: "pointed" (sharpened tips), "flat" (cut tops), "damaged" (gaps/broken logs).
        width: Total width of the palisade section.
        height: Total height of the palisade.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    log_radius = 0.08
    log_spacing = log_radius * 2.2
    n_logs = max(3, int(width / log_spacing))
    actual_spacing = width / n_logs
    segs = 8

    if style == "pointed":
        for i in range(n_logs):
            x = -width / 2 + (i + 0.5) * actual_spacing
            # Main log cylinder
            lv, lf = _make_cylinder(x, 0, 0, log_radius, height * 0.85, segments=segs)
            parts.append((lv, lf))
            # Pointed tip cone
            cv, cf = _make_cone(x, height * 0.85, 0, log_radius, height * 0.15, segments=segs)
            parts.append((cv, cf))

        # Horizontal cross-beam at back
        for beam_y in [height * 0.3, height * 0.65]:
            bv, bf = _make_box(0, beam_y, log_radius + 0.03,
                               width / 2, 0.04, 0.04)
            parts.append((bv, bf))

    elif style == "flat":
        for i in range(n_logs):
            x = -width / 2 + (i + 0.5) * actual_spacing
            lv, lf = _make_cylinder(x, 0, 0, log_radius, height, segments=segs)
            parts.append((lv, lf))

        # Cross-beams
        for beam_y in [height * 0.25, height * 0.6]:
            bv, bf = _make_box(0, beam_y, log_radius + 0.03,
                               width / 2, 0.04, 0.04)
            parts.append((bv, bf))

    else:  # damaged
        for i in range(n_logs):
            x = -width / 2 + (i + 0.5) * actual_spacing
            # Some logs are shorter or missing (deterministic pattern)
            skip = (i * 13 + 5) % 7 == 0
            if skip:
                continue
            h_mult = 0.5 + 0.5 * ((i * 17 + 3) % 5) / 4
            log_h = height * h_mult
            lv, lf = _make_cylinder(x, 0, 0, log_radius, log_h, segments=segs)
            parts.append((lv, lf))
            # Jagged broken top (small irregular cone)
            if h_mult < 0.9:
                cv, cf = _make_cone(x, log_h, 0, log_radius * 0.7,
                                    height * 0.06, segments=4)
                parts.append((cv, cf))
            else:
                cv, cf = _make_cone(x, log_h, 0, log_radius, height * 0.12,
                                    segments=segs)
                parts.append((cv, cf))

        # Partially broken cross-beam
        bv, bf = _make_box(0, height * 0.3, log_radius + 0.03,
                           width * 0.35, 0.04, 0.04)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Palisade_{style}", verts, faces,
                        style=style, category="fortification")


def generate_watchtower_mesh(
    style: str = "wooden",
    base_size: float = 3.0,
    height: float = 6.0,
) -> MeshSpec:
    """Generate a multi-level watchtower.

    Args:
        style: "wooden" (log construction), "stone" (masonry), "ruined".
        base_size: Width/depth of the base.
        height: Total height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    hs = base_size / 2

    if style == "wooden":
        # Four corner posts
        post_r = 0.1
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                px = sx * (hs - post_r)
                pz = sz * (hs - post_r)
                pv, pf = _make_cylinder(px, 0, pz, post_r, height, segments=6)
                parts.append((pv, pf))

        # Floor platforms at 3 levels
        for level in range(3):
            floor_y = level * height / 3
            fv, ff = _make_box(0, floor_y, 0, hs, 0.04, hs)
            parts.append((fv, ff))

        # Lookout platform at top (slightly wider)
        top_hs = hs + 0.2
        tv, tf = _make_box(0, height, 0, top_hs, 0.05, top_hs)
        parts.append((tv, tf))

        # Railing on top platform
        rail_h = 0.8
        rail_r = 0.03
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                rv, rf = _make_cylinder(sx * top_hs, height + 0.05, sz * top_hs,
                                        rail_r, rail_h, segments=4)
                parts.append((rv, rf))
        # Horizontal rails
        for sx in [-1, 1]:
            bv, bf = _make_box(sx * top_hs, height + 0.05 + rail_h,
                               0, rail_r, rail_r, top_hs)
            parts.append((bv, bf))
        for sz in [-1, 1]:
            bv, bf = _make_box(0, height + 0.05 + rail_h,
                               sz * top_hs, top_hs, rail_r, rail_r)
            parts.append((bv, bf))

        # Ladder (simple rungs)
        ladder_x = hs - 0.15
        for rung in range(int(height / 0.4)):
            ry = 0.2 + rung * 0.4
            rv, rf = _make_box(ladder_x, ry, 0, 0.15, 0.02, 0.02)
            parts.append((rv, rf))
        # Ladder side rails
        for lz in [-0.15, 0.15]:
            sv, sf = _make_box(ladder_x, height / 2, lz, 0.02, height / 2, 0.02)
            parts.append((sv, sf))

    elif style == "stone":
        # Solid stone walls with windows
        wall_thick = 0.2
        # Four walls
        for axis, sx, sz in [("x", -1, 0), ("x", 1, 0), ("z", 0, -1), ("z", 0, 1)]:
            wx = sx * hs
            wz = sz * hs
            if axis == "x":
                wv, wf = _make_beveled_box(wx, height / 2, 0,
                                           wall_thick / 2, height / 2, hs,
                                           bevel=0.01)
            else:
                wv, wf = _make_beveled_box(0, height / 2, wz,
                                           hs, height / 2, wall_thick / 2,
                                           bevel=0.01)
            parts.append((wv, wf))

        # Floor platforms
        for level in [0, height * 0.33, height * 0.66]:
            fv, ff = _make_box(0, level, 0, hs - wall_thick, 0.05, hs - wall_thick)
            parts.append((fv, ff))

        # Crenellated top
        merlon_w = 0.3
        merlon_h = 0.4
        n_merlons = max(2, int(base_size / merlon_w / 2))
        for side_x, side_z, along in [(hs, 0, "z"), (-hs, 0, "z"),
                                       (0, hs, "x"), (0, -hs, "x")]:
            for mi in range(n_merlons):
                offset = -hs + (mi * 2 + 1) * hs / n_merlons
                if along == "z":
                    mv, mf = _make_box(side_x, height + merlon_h / 2, offset,
                                       wall_thick / 2 + 0.02, merlon_h / 2, merlon_w / 2)
                else:
                    mv, mf = _make_box(offset, height + merlon_h / 2, side_z,
                                       merlon_w / 2, merlon_h / 2, wall_thick / 2 + 0.02)
                parts.append((mv, mf))

    else:  # ruined
        # Partial stone walls at varying heights
        wall_thick = 0.2
        wall_heights = [height * 0.8, height * 0.5, height * 0.6, height * 0.3]
        positions = [(-hs, 0, "x"), (hs, 0, "x"), (0, -hs, "z"), (0, hs, "z")]

        for (wx, wz, axis), wh in zip(positions, wall_heights):
            if axis == "x":
                wv, wf = _make_beveled_box(wx, wh / 2, 0,
                                           wall_thick / 2, wh / 2, hs,
                                           bevel=0.01)
            else:
                wv, wf = _make_beveled_box(0, wh / 2, wz,
                                           hs, wh / 2, wall_thick / 2,
                                           bevel=0.01)
            parts.append((wv, wf))

        # Rubble at base
        for i in range(5):
            rx = -hs * 0.5 + i * hs * 0.25
            rz = hs * 0.3 * ((i * 3) % 3 - 1)
            rv, rf = _make_beveled_box(rx, 0.1, rz, 0.15, 0.1, 0.12, bevel=0.02)
            parts.append((rv, rf))

        # Broken floor
        fv, ff = _make_box(0, 0, 0, hs - wall_thick, 0.04, hs - wall_thick)
        parts.append((fv, ff))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Watchtower_{style}", verts, faces,
                        style=style, category="fortification")


def generate_battlement_mesh(
    style: str = "stone",
    width: float = 4.0,
    height: float = 1.2,
) -> MeshSpec:
    """Generate a crenellated battlement wall top section.

    Args:
        style: "stone" (standard), "weathered" (chipped edges), "ruined" (partially collapsed).
        width: Total width of the battlement section.
        height: Total height including merlons.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    wall_thick = 0.4
    wall_h = height * 0.5  # Lower wall portion
    merlon_h = height * 0.5  # Upper merlon portion

    if style == "stone":
        # Base wall
        wv, wf = _make_beveled_box(0, wall_h / 2, 0,
                                   width / 2, wall_h / 2, wall_thick / 2,
                                   bevel=0.01)
        parts.append((wv, wf))

        # Alternating merlons (raised) and crenels (gaps)
        merlon_w = 0.5
        n_merlons = max(2, int(width / (merlon_w * 2)))
        merlon_spacing = width / (n_merlons * 2)
        for i in range(n_merlons):
            mx = -width / 2 + (i * 2 + 0.5) * merlon_spacing * 2
            mv, mf = _make_beveled_box(mx, wall_h + merlon_h / 2, 0,
                                       merlon_w / 2, merlon_h / 2, wall_thick / 2 + 0.02,
                                       bevel=0.008)
            parts.append((mv, mf))

    elif style == "weathered":
        # Slightly rougher wall
        wv, wf = _make_beveled_box(0, wall_h / 2, 0,
                                   width / 2, wall_h / 2, wall_thick / 2,
                                   bevel=0.015)
        parts.append((wv, wf))

        # Weathered merlons with slight size variation
        merlon_w = 0.5
        n_merlons = max(2, int(width / (merlon_w * 2)))
        merlon_spacing = width / (n_merlons * 2)
        for i in range(n_merlons):
            mx = -width / 2 + (i * 2 + 0.5) * merlon_spacing * 2
            # Slight height variation
            h_var = 1.0 - 0.15 * ((i * 7 + 2) % 3) / 2
            mv, mf = _make_beveled_box(mx, wall_h + merlon_h * h_var / 2, 0,
                                       merlon_w / 2 * 0.95, merlon_h * h_var / 2,
                                       wall_thick / 2 + 0.02,
                                       bevel=0.012)
            parts.append((mv, mf))

    else:  # ruined
        # Broken wall base
        wv, wf = _make_beveled_box(0, wall_h / 2, 0,
                                   width / 2, wall_h / 2, wall_thick / 2,
                                   bevel=0.02)
        parts.append((wv, wf))

        # Only some merlons remain
        merlon_w = 0.5
        n_merlons = max(2, int(width / (merlon_w * 2)))
        merlon_spacing = width / (n_merlons * 2)
        for i in range(n_merlons):
            if (i * 11 + 3) % 4 == 0:
                continue  # Missing merlon
            mx = -width / 2 + (i * 2 + 0.5) * merlon_spacing * 2
            h_var = 0.4 + 0.6 * ((i * 13 + 1) % 5) / 4
            mv, mf = _make_beveled_box(mx, wall_h + merlon_h * h_var / 2, 0,
                                       merlon_w / 2, merlon_h * h_var / 2,
                                       wall_thick / 2,
                                       bevel=0.015)
            parts.append((mv, mf))

        # Rubble pieces
        for i in range(3):
            rx = -width * 0.3 + i * width * 0.3
            rv, rf = _make_box(rx, 0.05, wall_thick / 2 + 0.1,
                               0.12, 0.05, 0.08)
            parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Battlement_{style}", verts, faces,
                        style=style, category="fortification")


def generate_moat_edge_mesh(
    style: str = "stone",
    width: float = 4.0,
    depth: float = 1.5,
) -> MeshSpec:
    """Generate a moat edge section with sloped bank and retaining wall.

    Args:
        style: "stone" (masonry retaining wall), "earth" (natural slope), "reinforced" (buttressed).
        width: Total width of the section.
        depth: Depth of the moat.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    section_d = 2.0  # Depth along Z axis

    if style == "stone":
        # Vertical retaining wall
        wall_thick = 0.3
        wv, wf = _make_beveled_box(0, -depth / 2, 0,
                                   width / 2, depth / 2, wall_thick / 2,
                                   bevel=0.01)
        parts.append((wv, wf))

        # Top edge / lip
        lv, lf = _make_beveled_box(0, 0.05, -wall_thick / 2 - 0.1,
                                   width / 2 + 0.05, 0.05, 0.15,
                                   bevel=0.008)
        parts.append((lv, lf))

        # Ground surface behind wall
        gv, gf = _make_box(0, 0, -wall_thick / 2 - section_d / 2 - 0.1,
                           width / 2 + 0.1, 0.03, section_d / 2)
        parts.append((gv, gf))

        # Stone blocks detail
        block_h = depth / 4
        for row in range(4):
            for col in range(max(2, int(width / 0.8))):
                bx = -width / 2 + (col + 0.5) * width / max(2, int(width / 0.8))
                by = -depth + (row + 0.5) * block_h
                sv, sf = _make_box(bx, by, wall_thick / 2 + 0.005,
                                   0.35, block_h / 2 - 0.01, 0.005)
                parts.append((sv, sf))

    elif style == "earth":
        # Sloped bank using a wedge shape
        # Top ground level
        gv, gf = _make_box(0, 0, -section_d / 2,
                           width / 2, 0.03, section_d / 2)
        parts.append((gv, gf))

        # Slope as series of stepped boxes
        n_steps = 6
        for i in range(n_steps):
            t = i / n_steps
            sx = width / 2
            sy = -t * depth
            sz = t * section_d / 2
            step_h = depth / n_steps
            sv, sf = _make_box(0, sy - step_h / 2, sz,
                               sx * (1.0 - t * 0.3), step_h / 2, section_d / n_steps / 2)
            parts.append((sv, sf))

    else:  # reinforced
        # Stone wall with buttresses
        wall_thick = 0.35
        wv, wf = _make_beveled_box(0, -depth / 2, 0,
                                   width / 2, depth / 2, wall_thick / 2,
                                   bevel=0.01)
        parts.append((wv, wf))

        # Buttresses
        n_buttresses = max(2, int(width / 1.5))
        for i in range(n_buttresses):
            bx = -width / 2 + (i + 0.5) * width / n_buttresses
            # Tapered buttress
            bv, bf = _make_tapered_cylinder(bx, -depth, wall_thick / 2,
                                            0.15, 0.08, depth,
                                            segments=4, rings=1)
            parts.append((bv, bf))

        # Top lip
        lv, lf = _make_beveled_box(0, 0.05, -wall_thick / 2 - 0.1,
                                   width / 2 + 0.1, 0.06, 0.15,
                                   bevel=0.01)
        parts.append((lv, lf))

        # Ground surface
        gv, gf = _make_box(0, 0, -wall_thick / 2 - section_d / 2 - 0.1,
                           width / 2, 0.03, section_d / 2)
        parts.append((gv, gf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MoatEdge_{style}", verts, faces,
                        style=style, category="fortification")


def generate_windmill_mesh(
    style: str = "wooden",
    base_radius: float = 2.0,
    height: float = 8.0,
) -> MeshSpec:
    """Generate a windmill mesh.

    Args:
        style: "wooden" (Dutch style) or "stone" (tower mill).
        base_radius: Radius of the base.
        height: Total height of the tower.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    segs = 12

    if style == "wooden":
        # Tapered octagonal body
        body_v, body_f = _make_tapered_cylinder(
            0, 0, 0, base_radius, base_radius * 0.6, height * 0.8,
            segments=8, rings=3)
        parts.append((body_v, body_f))

        # Roof (cone)
        roof_v, roof_f = _make_cone(0, height * 0.8, 0, base_radius * 0.65,
                                     height * 0.2, segments=8)
        parts.append((roof_v, roof_f))

        # Door
        door_w = 0.4
        door_h = 1.0
        dv, df = _make_beveled_box(0, door_h / 2, base_radius + 0.02,
                                   door_w / 2, door_h / 2, 0.03,
                                   bevel=0.005)
        parts.append((dv, df))

        # Windows (2 levels)
        for level in [height * 0.35, height * 0.6]:
            for angle_idx in range(4):
                angle = math.pi * 2 * angle_idx / 4
                r_at_h = base_radius + (base_radius * 0.6 - base_radius) * level / (height * 0.8)
                wx = math.cos(angle) * (r_at_h + 0.02)
                wz = math.sin(angle) * (r_at_h + 0.02)
                wv, wf = _make_box(wx, level, wz, 0.12, 0.15, 0.03)
                parts.append((wv, wf))

        # Four sails/blades
        blade_len = height * 0.45
        hub_y = height * 0.7
        hub_z = base_radius * 0.65 + 0.1
        # Hub
        hv, hf = _make_cylinder(0, hub_y, hub_z, 0.12, 0.15, segments=8)
        parts.append((hv, hf))

        for blade in range(4):
            angle = math.pi / 2 * blade + math.pi / 8
            # Blade arm
            bx = math.cos(angle) * blade_len / 2
            by = hub_y + math.sin(angle) * blade_len / 2
            arm_v, arm_f = _make_box(bx, by, hub_z + 0.08,
                                     0.03, blade_len / 2, 0.02)
            parts.append((arm_v, arm_f))

            # Sail cloth (thin plane along each arm)
            sail_offset_x = math.cos(angle) * blade_len * 0.4
            sail_offset_y = math.sin(angle) * blade_len * 0.4
            sv, sf = _make_box(sail_offset_x, hub_y + sail_offset_y,
                               hub_z + 0.1,
                               0.25, blade_len * 0.35, 0.005)
            parts.append((sv, sf))

    else:  # stone
        # Cylindrical stone tower
        body_v, body_f = _make_tapered_cylinder(
            0, 0, 0, base_radius, base_radius * 0.8, height * 0.85,
            segments=segs, rings=4)
        parts.append((body_v, body_f))

        # Conical roof
        roof_v, roof_f = _make_cone(0, height * 0.85, 0, base_radius * 0.85,
                                     height * 0.15, segments=segs)
        parts.append((roof_v, roof_f))

        # Door
        dv, df = _make_beveled_box(0, 0.5, base_radius + 0.02,
                                   0.4, 0.5, 0.03, bevel=0.005)
        parts.append((dv, df))

        # Stone band details
        for band_y in [height * 0.25, height * 0.5, height * 0.75]:
            r_at = base_radius + (base_radius * 0.8 - base_radius) * band_y / (height * 0.85)
            bv, bf = _make_torus_ring(0, band_y, 0, r_at + 0.02, 0.03,
                                      major_segments=segs, minor_segments=4)
            parts.append((bv, bf))

        # Four sails
        blade_len = height * 0.4
        hub_y = height * 0.75
        r_at_hub = base_radius + (base_radius * 0.8 - base_radius) * hub_y / (height * 0.85)
        hub_z = r_at_hub + 0.15
        hv, hf = _make_cylinder(0, hub_y, hub_z, 0.1, 0.12, segments=8)
        parts.append((hv, hf))

        for blade in range(4):
            angle = math.pi / 2 * blade
            bx = math.cos(angle) * blade_len * 0.4
            by = hub_y + math.sin(angle) * blade_len * 0.4
            sv, sf = _make_box(bx, by, hub_z + 0.08,
                               0.25, blade_len * 0.35, 0.005)
            parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Windmill_{style}", verts, faces,
                        style=style, category="infrastructure")


def generate_dock_mesh(
    style: str = "wooden",
    width: float = 3.0,
    length: float = 8.0,
) -> MeshSpec:
    """Generate a waterfront dock/pier.

    Args:
        style: "wooden" (plank pier) or "stone" (masonry pier).
        width: Dock width.
        length: Dock length along Z axis.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "wooden":
        # Support posts underneath
        post_r = 0.08
        post_h = 1.5
        n_post_rows = max(2, int(length / 2.0))
        for row in range(n_post_rows):
            z = -length / 2 + (row + 0.5) * length / n_post_rows
            for side in [-1, 1]:
                x = side * (width / 2 - 0.1)
                pv, pf = _make_cylinder(x, -post_h, z, post_r, post_h,
                                        segments=6)
                parts.append((pv, pf))

        # Main deck (planks)
        deck_h = 0.05
        dv, df = _make_box(0, -deck_h / 2, 0, width / 2, deck_h / 2, length / 2)
        parts.append((dv, df))

        # Plank line details
        n_planks = int(width / 0.2)
        for i in range(n_planks):
            px = -width / 2 + (i + 0.5) * width / n_planks
            lv, lf = _make_box(px, 0.005, 0, 0.003, 0.005, length / 2 - 0.05)
            parts.append((lv, lf))

        # Mooring posts
        for z_pos in [-length / 2 + 0.5, length / 2 - 0.5]:
            for side in [-1, 1]:
                mx = side * (width / 2 - 0.15)
                mv, mf = _make_cylinder(mx, 0, z_pos, 0.06, 0.5, segments=6)
                parts.append((mv, mf))
                # Top cap
                cv, cf = _make_sphere(mx, 0.52, z_pos, 0.07, rings=4, sectors=6)
                parts.append((cv, cf))

        # Rope cleats
        for z_pos in [-length * 0.25, length * 0.25]:
            cv, cf = _make_box(width / 2 - 0.05, 0.03, z_pos,
                               0.04, 0.02, 0.08)
            parts.append((cv, cf))

    else:  # stone
        # Solid stone base
        base_h = 1.0
        bv, bf = _make_beveled_box(0, -base_h / 2, 0,
                                   width / 2, base_h / 2, length / 2,
                                   bevel=0.02)
        parts.append((bv, bf))

        # Stone surface
        sv, sf = _make_box(0, 0.02, 0, width / 2 + 0.02, 0.02, length / 2 + 0.02)
        parts.append((sv, sf))

        # Mooring posts (stone bollards)
        for z_pos in [-length / 2 + 0.5, length / 2 - 0.5]:
            for side in [-1, 1]:
                mx = side * (width / 2 - 0.2)
                mv, mf = _make_tapered_cylinder(mx, 0, z_pos, 0.1, 0.07, 0.4,
                                                 segments=8, rings=1)
                parts.append((mv, mf))

        # Step blocks at end
        for i in range(3):
            sy = -i * 0.25
            sv, sf = _make_beveled_box(0, sy, length / 2 + 0.15 + i * 0.3,
                                       width / 2 * 0.8, 0.1, 0.12,
                                       bevel=0.01)
            parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Dock_{style}", verts, faces,
                        style=style, category="infrastructure")


def generate_bridge_stone_mesh(
    style: str = "arch",
    span: float = 10.0,
    width: float = 3.0,
) -> MeshSpec:
    """Generate a stone bridge.

    Args:
        style: "arch" (single arch), "multi_arch" (3 arches), "flat" (beam bridge).
        span: Total length of the bridge.
        width: Bridge width.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    deck_thick = 0.2
    railing_h = 0.6

    if style == "arch":
        # Single arch
        arch_segs = 20
        arch_h = span * 0.2

        # Deck with slight crown
        deck_verts: list[tuple[float, float, float]] = []
        deck_faces: list[tuple[int, ...]] = []
        for i in range(arch_segs + 1):
            t = i / arch_segs
            z = -span / 2 + t * span
            y_crown = math.sin(t * math.pi) * arch_h * 0.08
            deck_verts.append((-width / 2, y_crown, z))
            deck_verts.append((-width / 2, y_crown - deck_thick, z))
            deck_verts.append((width / 2, y_crown - deck_thick, z))
            deck_verts.append((width / 2, y_crown, z))

        for i in range(arch_segs):
            b = i * 4
            deck_faces.append((b + 0, b + 3, b + 7, b + 4))
            deck_faces.append((b + 1, b + 5, b + 6, b + 2))
            deck_faces.append((b + 0, b + 4, b + 5, b + 1))
            deck_faces.append((b + 3, b + 2, b + 6, b + 7))
        parts.append((deck_verts, deck_faces))

        # Arch underneath
        arch_thick = 0.12
        arch_v: list[tuple[float, float, float]] = []
        arch_f: list[tuple[int, ...]] = []
        for i in range(arch_segs + 1):
            t = i / arch_segs
            z = -span / 2 + t * span
            y = -math.sin(t * math.pi) * arch_h - deck_thick
            for dx in [-width * 0.4, width * 0.4]:
                arch_v.append((dx - arch_thick / 2, y, z))
                arch_v.append((dx + arch_thick / 2, y, z))
                arch_v.append((dx + arch_thick / 2, y - arch_thick, z))
                arch_v.append((dx - arch_thick / 2, y - arch_thick, z))

        for i in range(arch_segs):
            for side in range(2):
                b = i * 8 + side * 4
                for j in range(4):
                    j2 = (j + 1) % 4
                    arch_f.append((b + j, b + j2, b + 8 + j2, b + 8 + j))
        parts.append((arch_v, arch_f))

        # Railings
        for sx in [-width / 2, width / 2]:
            rv, rf = _make_box(sx, railing_h / 2, 0,
                               0.08, railing_h / 2, span / 2)
            parts.append((rv, rf))

        # Cobble surface detail
        for i in range(int(span / 0.5)):
            z = -span / 2 + (i + 0.5) * 0.5
            sv, sf = _make_box(0, 0.005, z, width / 2 - 0.1, 0.005, 0.2)
            parts.append((sv, sf))

    elif style == "multi_arch":
        n_arches = 3
        arch_span = span / n_arches
        arch_h = arch_span * 0.35

        # Deck
        dv, df = _make_beveled_box(0, 0, 0,
                                   width / 2, deck_thick / 2, span / 2,
                                   bevel=0.01)
        parts.append((dv, df))

        # Three arches underneath
        arch_segs = 12
        for a in range(n_arches):
            center_z = -span / 2 + (a + 0.5) * arch_span
            arch_v: list[tuple[float, float, float]] = []
            arch_f: list[tuple[int, ...]] = []
            for i in range(arch_segs + 1):
                t = i / arch_segs
                z = center_z - arch_span / 2 + t * arch_span
                y = -math.sin(t * math.pi) * arch_h - deck_thick
                arch_v.append((-width * 0.35, y, z))
                arch_v.append((-width * 0.35, y - 0.1, z))
                arch_v.append((width * 0.35, y - 0.1, z))
                arch_v.append((width * 0.35, y, z))

            for i in range(arch_segs):
                b = i * 4
                arch_f.append((b + 0, b + 3, b + 7, b + 4))
                arch_f.append((b + 1, b + 5, b + 6, b + 2))
                arch_f.append((b + 0, b + 4, b + 5, b + 1))
                arch_f.append((b + 3, b + 2, b + 6, b + 7))
            parts.append((arch_v, arch_f))

        # Piers between arches
        for p in range(n_arches - 1):
            pz = -span / 2 + (p + 1) * arch_span
            pv, pf = _make_beveled_box(0, -arch_h / 2 - deck_thick, pz,
                                       width / 2 * 0.9, arch_h / 2, 0.2,
                                       bevel=0.01)
            parts.append((pv, pf))

        # Railings
        for sx in [-width / 2, width / 2]:
            rv, rf = _make_box(sx, railing_h / 2 + deck_thick / 2, 0,
                               0.08, railing_h / 2, span / 2)
            parts.append((rv, rf))

    else:  # flat
        # Simple beam bridge
        dv, df = _make_beveled_box(0, 0, 0,
                                   width / 2, deck_thick / 2, span / 2,
                                   bevel=0.01)
        parts.append((dv, df))

        # Support beams underneath
        n_beams = max(3, int(span / 2.5))
        for i in range(n_beams):
            bz = -span / 2 + (i + 0.5) * span / n_beams
            bv, bf = _make_box(0, -deck_thick / 2 - 0.15, bz,
                               width / 2 - 0.1, 0.1, 0.08)
            parts.append((bv, bf))

        # Railings
        for sx in [-width / 2, width / 2]:
            rv, rf = _make_box(sx, railing_h / 2 + deck_thick / 2, 0,
                               0.06, railing_h / 2, span / 2)
            parts.append((rv, rf))

        # Railing posts
        n_posts = max(2, int(span / 1.5))
        for sx in [-width / 2, width / 2]:
            for i in range(n_posts):
                pz = -span / 2 + (i + 0.5) * span / n_posts
                pv, pf = _make_cylinder(sx, deck_thick / 2, pz,
                                        0.04, railing_h, segments=6)
                parts.append((pv, pf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"StoneBridge_{style}", verts, faces,
                        style=style, category="infrastructure")


def generate_rope_bridge_mesh(
    style: str = "simple",
    span: float = 8.0,
    width: float = 1.5,
) -> MeshSpec:
    """Generate a rope/plank bridge with catenary sag.

    Args:
        style: "simple" (basic planks), "sturdy" (reinforced), "damaged" (missing planks).
        span: Bridge span length.
        width: Bridge width.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    plank_count = int(span / 0.18)
    rope_r = 0.015
    rope_h = 0.7
    sag_factor = 0.06

    if style == "simple":
        # Planks with catenary sag
        for i in range(plank_count):
            z = -span / 2 + (i + 0.5) * span / plank_count
            t = (z + span / 2) / span
            sag = -math.sin(t * math.pi) * span * sag_factor
            pv, pf = _make_box(0, sag, z, width / 2 * 0.9, 0.015, 0.07)
            parts.append((pv, pf))

        # Rope handrails (series of short cylinders following catenary)
        rope_segs = plank_count // 2
        for sx in [-width / 2, width / 2]:
            for i in range(rope_segs):
                z = -span / 2 + (i + 0.5) * span / rope_segs
                t = (z + span / 2) / span
                sag = -math.sin(t * math.pi) * span * sag_factor
                # Vertical rope posts
                pv, pf = _make_cylinder(sx, sag, z, rope_r * 2, rope_h, segments=4)
                parts.append((pv, pf))

        # Top rope rails
        for sx in [-width / 2, width / 2]:
            rv, rf = _make_box(sx, rope_h * 0.5, 0, rope_r, rope_r, span / 2)
            parts.append((rv, rf))

    elif style == "sturdy":
        # More planks, thicker ropes
        for i in range(plank_count):
            z = -span / 2 + (i + 0.5) * span / plank_count
            t = (z + span / 2) / span
            sag = -math.sin(t * math.pi) * span * sag_factor * 0.5
            pv, pf = _make_box(0, sag, z, width / 2 * 0.95, 0.025, 0.08)
            parts.append((pv, pf))

        # Sturdier support posts
        n_posts = max(4, int(span / 1.5))
        for sx in [-width / 2, width / 2]:
            for i in range(n_posts):
                z = -span / 2 + (i + 0.5) * span / n_posts
                t = (z + span / 2) / span
                sag = -math.sin(t * math.pi) * span * sag_factor * 0.5
                pv, pf = _make_cylinder(sx, sag, z, rope_r * 3, rope_h,
                                        segments=6)
                parts.append((pv, pf))

        # Double rope rails
        for sx in [-width / 2, width / 2]:
            for ry in [rope_h * 0.4, rope_h * 0.8]:
                rv, rf = _make_box(sx, ry, 0, rope_r * 1.5, rope_r * 1.5, span / 2)
                parts.append((rv, rf))

        # Cross-bracing underneath
        for i in range(int(span / 2)):
            z = -span / 2 + (i + 0.5) * 2.0
            cv, cf = _make_box(0, -0.1, z, width / 2, 0.01, 0.02)
            parts.append((cv, cf))

    else:  # damaged
        # Some planks missing
        for i in range(plank_count):
            if (i * 11 + 7) % 5 == 0:
                continue  # Missing plank
            z = -span / 2 + (i + 0.5) * span / plank_count
            t = (z + span / 2) / span
            sag = -math.sin(t * math.pi) * span * sag_factor * 1.2
            # Some planks are tilted/broken
            y_off = 0.02 * ((i * 7) % 3 - 1)
            pv, pf = _make_box(0, sag + y_off, z,
                               width / 2 * (0.7 + 0.2 * ((i * 3) % 3)),
                               0.012, 0.065)
            parts.append((pv, pf))

        # Frayed rope posts (fewer)
        n_posts = max(3, int(span / 2.5))
        for sx in [-width / 2, width / 2]:
            for i in range(n_posts):
                z = -span / 2 + (i + 0.5) * span / n_posts
                t = (z + span / 2) / span
                sag = -math.sin(t * math.pi) * span * sag_factor * 1.2
                pv, pf = _make_cylinder(sx, sag, z, rope_r * 1.5,
                                        rope_h * (0.5 + 0.5 * ((i * 7) % 3) / 2),
                                        segments=4)
                parts.append((pv, pf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"RopeBridge_{style}", verts, faces,
                        style=style, category="infrastructure")


def generate_tent_mesh(
    style: str = "small",
) -> MeshSpec:
    """Generate a camping tent.

    Args:
        style: "small" (A-frame), "large" (pavilion), "command" (multi-room).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "small":
        # A-frame tent
        tent_w = 1.2
        tent_h = 1.0
        tent_d = 1.8
        hw = tent_w / 2
        hd = tent_d / 2

        # Tent body as triangular prism
        tent_verts = [
            (-hw, 0, -hd),
            (hw, 0, -hd),
            (0, tent_h, -hd),
            (-hw, 0, hd),
            (hw, 0, hd),
            (0, tent_h, hd),
        ]
        tent_faces = [
            (0, 2, 1),
            (3, 4, 5),
            (0, 3, 5, 2),
            (1, 2, 5, 4),
            (0, 1, 4, 3),
        ]
        parts.append((tent_verts, tent_faces))

        # Support poles
        pv, pf = _make_cylinder(0, 0, -hd - 0.05, 0.02, tent_h + 0.1, segments=4)
        parts.append((pv, pf))
        pv, pf = _make_cylinder(0, 0, hd + 0.05, 0.02, tent_h + 0.1, segments=4)
        parts.append((pv, pf))

        # Ridge pole
        rv, rf = _make_box(0, tent_h + 0.02, 0, 0.015, 0.015, hd + 0.05)
        parts.append((rv, rf))

        # Guy rope anchors
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                gv, gf = _make_box(sx * (hw + 0.3), 0.01, sz * (hd + 0.3),
                                   0.005, 0.005, 0.005)
                parts.append((gv, gf))

    elif style == "large":
        # Pavilion tent (4-pole)
        tent_w = 3.0
        tent_h = 2.5
        tent_d = 3.0
        hw = tent_w / 2
        hd = tent_d / 2
        wall_h = 1.2

        # Four corner poles
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                pv, pf = _make_cylinder(sx * (hw - 0.05), 0, sz * (hd - 0.05),
                                        0.04, wall_h + 0.5, segments=6)
                parts.append((pv, pf))

        # Center pole
        pv, pf = _make_cylinder(0, 0, 0, 0.05, tent_h, segments=6)
        parts.append((pv, pf))

        # Roof (pyramid)
        roof_verts = [
            (-hw, wall_h, -hd),
            (hw, wall_h, -hd),
            (hw, wall_h, hd),
            (-hw, wall_h, hd),
            (0, tent_h, 0),
        ]
        roof_faces = [
            (0, 1, 4),
            (1, 2, 4),
            (2, 3, 4),
            (3, 0, 4),
        ]
        parts.append((roof_verts, roof_faces))

        # Wall panels
        wall_thick = 0.02
        for sz in [-hd, hd]:
            wv, wf = _make_box(0, wall_h / 2, sz, hw, wall_h / 2, wall_thick)
            parts.append((wv, wf))
        for sx in [-hw, hw]:
            wv, wf = _make_box(sx, wall_h / 2, 0, wall_thick, wall_h / 2, hd)
            parts.append((wv, wf))

        # Entrance flap
        fv, ff = _make_box(hw * 0.3, wall_h / 2, -hd - 0.03,
                           hw * 0.25, wall_h / 2, wall_thick)
        parts.append((fv, ff))

    else:  # command
        # Multi-room command tent
        tent_w = 4.0
        tent_h = 2.8
        tent_d = 5.0
        hw = tent_w / 2
        hd = tent_d / 2
        wall_h = 1.5

        # Main poles (6)
        for sx in [-1, 0, 1]:
            for sz in [-1, 1]:
                pv, pf = _make_cylinder(sx * (hw - 0.1), 0, sz * (hd - 0.1),
                                        0.05, wall_h + 0.8, segments=6)
                parts.append((pv, pf))

        # Two center poles for ridge
        for sz in [-hd * 0.4, hd * 0.4]:
            pv, pf = _make_cylinder(0, 0, sz, 0.06, tent_h, segments=6)
            parts.append((pv, pf))

        # Ridge beam
        rv, rf = _make_box(0, tent_h, 0, 0.03, 0.03, hd * 0.8)
        parts.append((rv, rf))

        # Roof panels (two slopes)
        for sx_sign in [-1, 1]:
            roof_verts = [
                (sx_sign * hw, wall_h, -hd),
                (0, tent_h, -hd * 0.8),
                (0, tent_h, hd * 0.8),
                (sx_sign * hw, wall_h, hd),
            ]
            roof_faces = [(0, 1, 2, 3)]
            parts.append((roof_verts, roof_faces))

        # End caps (triangles)
        for sz_sign in [-1, 1]:
            cap_verts = [
                (-hw, wall_h, sz_sign * hd),
                (hw, wall_h, sz_sign * hd),
                (0, tent_h, sz_sign * hd * 0.8),
            ]
            cap_faces = [(0, 1, 2) if sz_sign == -1 else (0, 2, 1)]
            parts.append((cap_verts, cap_faces))

        # Wall panels
        for sz in [-hd, hd]:
            wv, wf = _make_box(0, wall_h / 2, sz, hw, wall_h / 2, 0.02)
            parts.append((wv, wf))
        for sx in [-hw, hw]:
            wv, wf = _make_box(sx, wall_h / 2, 0, 0.02, wall_h / 2, hd)
            parts.append((wv, wf))

        # Interior divider wall
        dv, df = _make_box(0, wall_h / 2, 0, hw * 0.9, wall_h / 2, 0.015)
        parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Tent_{style}", verts, faces,
                        style=style, category="camp")


def generate_hitching_post_mesh(
    style: str = "wooden",
) -> MeshSpec:
    """Generate a hitching post for tying horses.

    Args:
        style: "wooden" (rough timber) or "iron" (metal post).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    post_h = 1.0
    bar_len = 1.5

    if style == "wooden":
        for sx in [-bar_len / 2, bar_len / 2]:
            pv, pf = _make_beveled_box(sx, post_h / 2, 0,
                                       0.05, post_h / 2, 0.05,
                                       bevel=0.005)
            parts.append((pv, pf))

        bv, bf = _make_beveled_box(0, post_h, 0,
                                   bar_len / 2, 0.04, 0.04,
                                   bevel=0.005)
        parts.append((bv, bf))

        for i in range(3):
            rx = -bar_len / 3 + i * bar_len / 3
            rv, rf = _make_torus_ring(rx, post_h - 0.08, 0.06,
                                      0.04, 0.008,
                                      major_segments=8, minor_segments=4)
            parts.append((rv, rf))

    else:  # iron
        for sx in [-bar_len / 2, bar_len / 2]:
            pv, pf = _make_cylinder(sx, 0, 0, 0.03, post_h, segments=8)
            parts.append((pv, pf))
            cv, cf = _make_sphere(sx, post_h + 0.03, 0, 0.04, rings=4, sectors=6)
            parts.append((cv, cf))

        hv, hf = _make_box(0, post_h * 0.85, 0, bar_len / 2, 0.02, 0.02)
        parts.append((hv, hf))

        for i in range(3):
            rx = -bar_len / 3 + i * bar_len / 3
            rv, rf = _make_torus_ring(rx, post_h * 0.85 - 0.06, 0.04,
                                      0.035, 0.006,
                                      major_segments=8, minor_segments=4)
            parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"HitchingPost_{style}", verts, faces,
                        style=style, category="camp")


def generate_feeding_trough_mesh(
    style: str = "wooden",
) -> MeshSpec:
    """Generate an animal feeding trough.

    Args:
        style: "wooden" (timber) or "stone" (masonry).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    trough_w = 1.2
    trough_h = 0.4
    trough_d = 0.5

    if style == "wooden":
        ov, of_ = _make_beveled_box(0, trough_h / 2 + 0.3, 0,
                                    trough_w / 2, trough_h / 2, trough_d / 2,
                                    bevel=0.01)
        parts.append((ov, of_))

        iv, if_ = _make_box(0, trough_h / 2 + 0.33, 0,
                            trough_w / 2 - 0.04, trough_h / 2 - 0.03,
                            trough_d / 2 - 0.04)
        parts.append((iv, if_))

        leg_h = 0.3
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                lx = sx * (trough_w / 2 - 0.08)
                lz = sz * (trough_d / 2 - 0.06)
                lv, lf = _make_beveled_box(lx, leg_h / 2, lz,
                                           0.04, leg_h / 2, 0.04,
                                           bevel=0.005)
                parts.append((lv, lf))

    else:  # stone
        ov, of_ = _make_beveled_box(0, trough_h / 2 + 0.2, 0,
                                    trough_w / 2, trough_h / 2, trough_d / 2,
                                    bevel=0.015)
        parts.append((ov, of_))

        iv, if_ = _make_box(0, trough_h / 2 + 0.25, 0,
                            trough_w / 2 - 0.06, trough_h / 2 - 0.04,
                            trough_d / 2 - 0.06)
        parts.append((iv, if_))

        bv, bf = _make_beveled_box(0, 0.1, 0,
                                   trough_w / 2 + 0.03, 0.1, trough_d / 2 + 0.03,
                                   bevel=0.01)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"FeedingTrough_{style}", verts, faces,
                        style=style, category="camp")


def generate_barricade_outdoor_mesh(
    style: str = "wooden",
    width: float = 2.0,
    height: float = 1.2,
) -> MeshSpec:
    """Generate a defensive barricade for outdoor fortification.

    Args:
        style: "wooden" (angled stakes), "sandbag" (stacked bags), "rubble" (piled debris).
        width: Barricade width.
        height: Barricade height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "wooden":
        n_stakes = max(4, int(width / 0.25))
        stake_r = 0.03
        for i in range(n_stakes):
            x = -width / 2 + (i + 0.5) * width / n_stakes
            sv, sf = _make_cylinder(x, 0, 0, stake_r, height, segments=6)
            tilt = 0.15
            tilted = []
            for v in sv:
                ny = v[1]
                nz = v[2] + (v[1] / height) * tilt * height
                tilted.append((v[0], ny, nz))
            parts.append((tilted, sf))

            cv, cf = _make_cone(x, height, tilt * height,
                                stake_r * 1.5, height * 0.12, segments=4)
            parts.append((cv, cf))

        bv, bf = _make_box(0, height * 0.4, -0.05,
                           width / 2, 0.03, 0.03)
        parts.append((bv, bf))

        lv, lf = _make_box(0, 0.04, -0.1, width / 2, 0.04, 0.06)
        parts.append((lv, lf))

    elif style == "sandbag":
        bag_w = 0.35
        bag_h = 0.12
        bag_d = 0.25
        rows = max(2, int(height / (bag_h * 0.9)))

        total_h = 0.0
        for row in range(rows):
            bags_in_row = max(2, int(width / bag_w))
            y = total_h + bag_h / 2
            offset_x = bag_w * 0.5 if row % 2 else 0
            for i in range(bags_in_row):
                x = -width / 2 + offset_x + (i + 0.5) * width / bags_in_row
                sv, sf = _make_beveled_box(x, y, 0,
                                           bag_w / 2 * 0.9, bag_h / 2,
                                           bag_d / 2,
                                           bevel=0.01)
                parts.append((sv, sf))
            total_h += bag_h * 0.9

    else:  # rubble
        n_pieces = max(8, int(width * height * 5))
        for i in range(n_pieces):
            t = i / n_pieces
            x = -width / 2 + t * width + 0.1 * ((i * 7 + 3) % 5 - 2)
            h_frac = 1.0 - abs(t - 0.5) * 2
            y = h_frac * height * ((i * 11 + 1) % 5) / 5
            z = 0.15 * ((i * 13 + 2) % 4 - 2)
            sz_x = 0.08 + 0.12 * ((i * 17 + 1) % 3) / 2
            sz_y = 0.05 + 0.08 * ((i * 19 + 3) % 3) / 2
            sz_z = 0.06 + 0.1 * ((i * 23 + 2) % 3) / 2
            rv, rf = _make_beveled_box(x, y + sz_y, z,
                                       sz_x, sz_y, sz_z,
                                       bevel=0.01)
            parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"BarricadeOutdoor_{style}", verts, faces,
                        style=style, category="camp")


def generate_lookout_post_mesh(
    style: str = "raised",
) -> MeshSpec:
    """Generate an elevated observation/lookout post.

    Args:
        style: "raised" (tall platform) or "ground" (low blind).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "raised":
        platform_h = 3.0
        platform_size = 1.5
        hs = platform_size / 2
        post_r = 0.06

        for sx in [-1, 1]:
            for sz in [-1, 1]:
                top_x = sx * (hs - 0.05)
                top_z = sz * (hs - 0.05)
                bot_x = sx * (hs + 0.15)
                bot_z = sz * (hs + 0.15)
                pv, pf = _make_cylinder(top_x, 0, top_z, post_r,
                                        platform_h, segments=6)
                splayed = []
                for v in pv:
                    t = v[1] / platform_h
                    nx = v[0] + (1.0 - t) * (bot_x - top_x)
                    nz = v[2] + (1.0 - t) * (bot_z - top_z)
                    splayed.append((nx, v[1], nz))
                parts.append((splayed, pf))

        for brace_h in [platform_h * 0.3, platform_h * 0.6]:
            bv, bf = _make_box(0, brace_h, 0, hs + 0.1, 0.02, 0.02)
            parts.append((bv, bf))
            bv, bf = _make_box(0, brace_h, 0, 0.02, 0.02, hs + 0.1)
            parts.append((bv, bf))

        fv, ff = _make_box(0, platform_h, 0, hs + 0.1, 0.04, hs + 0.1)
        parts.append((fv, ff))

        rail_h = 0.7
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                rv, rf = _make_cylinder(sx * hs, platform_h + 0.04, sz * hs,
                                        0.025, rail_h, segments=4)
                parts.append((rv, rf))
        for sx in [-hs, hs]:
            hv, hf = _make_box(sx, platform_h + 0.04 + rail_h, 0,
                               0.02, 0.02, hs)
            parts.append((hv, hf))
        for sz in [-hs, hs]:
            hv, hf = _make_box(0, platform_h + 0.04 + rail_h, sz,
                               hs, 0.02, 0.02)
            parts.append((hv, hf))

        roof_h = 1.0
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                rv, rf = _make_cylinder(sx * (hs - 0.05),
                                        platform_h + 0.04 + rail_h, sz * (hs - 0.05),
                                        0.02, roof_h, segments=4)
                parts.append((rv, rf))
        roof_top = platform_h + 0.04 + rail_h + roof_h
        rv, rf = _make_box(0, roof_top, 0, hs + 0.15, 0.03, hs + 0.15)
        parts.append((rv, rf))

        ladder_x = hs + 0.05
        for rung in range(int(platform_h / 0.35)):
            ry = 0.2 + rung * 0.35
            rv, rf = _make_box(ladder_x, ry, 0, 0.12, 0.015, 0.015)
            parts.append((rv, rf))
        for lz in [-0.12, 0.12]:
            sv, sf = _make_box(ladder_x, platform_h / 2, lz,
                               0.015, platform_h / 2, 0.015)
            parts.append((sv, sf))

    else:  # ground
        blind_w = 1.5
        blind_h = 1.2
        blind_d = 1.5

        wv, wf = _make_box(0, blind_h / 2, -blind_d / 2,
                           blind_w / 2, blind_h / 2, 0.04)
        parts.append((wv, wf))
        for sx in [-blind_w / 2, blind_w / 2]:
            wv, wf = _make_box(sx, blind_h / 2, 0,
                               0.04, blind_h / 2, blind_d / 2)
            parts.append((wv, wf))

        rv, rf = _make_box(0, blind_h + 0.03, -blind_d * 0.1,
                           blind_w / 2 + 0.1, 0.03, blind_d / 2 + 0.1)
        parts.append((rv, rf))

        sv, sf = _make_box(0, blind_h * 0.7, blind_d / 2 - 0.04,
                           blind_w * 0.3, 0.05, 0.02)
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"LookoutPost_{style}", verts, faces,
                        style=style, category="camp")


def generate_spike_fence_mesh(
    style: str = "iron",
    length: float = 3.0,
    height: float = 1.5,
) -> MeshSpec:
    """Generate a defensive spiked fence section.

    Args:
        style: "iron" (ornamental) or "wood" (rough stakes).
        length: Total fence length.
        height: Total fence height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "iron":
        n_spikes = max(4, int(length / 0.15))
        spike_spacing = length / n_spikes
        bar_r = 0.012

        for i in range(n_spikes):
            x = -length / 2 + (i + 0.5) * spike_spacing
            sv, sf = _make_cylinder(x, 0, 0, bar_r, height * 0.85,
                                    segments=6)
            parts.append((sv, sf))
            tv, tf = _make_cone(x, height * 0.85, 0, bar_r * 2.5,
                                height * 0.15, segments=4)
            parts.append((tv, tf))

        for ry in [height * 0.15, height * 0.5, height * 0.8]:
            rv, rf = _make_box(0, ry, 0, length / 2, bar_r * 1.2, bar_r * 1.2)
            parts.append((rv, rf))

        for sx in [-length / 2, length / 2]:
            pv, pf = _make_cylinder(sx, 0, 0, bar_r * 3, height, segments=8)
            parts.append((pv, pf))
            fv, ff = _make_sphere(sx, height + 0.02, 0, bar_r * 4,
                                  rings=4, sectors=6)
            parts.append((fv, ff))

        for i in range(max(1, n_spikes // 4)):
            x = -length / 2 + (i + 0.5) * length / max(1, n_spikes // 4)
            dv, df = _make_torus_ring(x, height * 0.65, 0,
                                      0.04, 0.005,
                                      major_segments=8, minor_segments=3)
            parts.append((dv, df))

    else:  # wood
        n_stakes = max(4, int(length / 0.2))
        stake_spacing = length / n_stakes

        for i in range(n_stakes):
            x = -length / 2 + (i + 0.5) * stake_spacing
            h_var = 0.85 + 0.15 * ((i * 7 + 2) % 4) / 3
            stake_h = height * h_var
            sv, sf = _make_cylinder(x, 0, 0, 0.03, stake_h * 0.8,
                                    segments=5)
            parts.append((sv, sf))
            tv, tf = _make_cone(x, stake_h * 0.8, 0, 0.04, stake_h * 0.2,
                                segments=4)
            parts.append((tv, tf))

        for ry in [height * 0.2, height * 0.55]:
            rv, rf = _make_box(0, ry, 0.04, length / 2, 0.03, 0.03)
            parts.append((rv, rf))

        for sx in [-length / 2, length / 2]:
            pv, pf = _make_cylinder(sx, 0, 0, 0.05, height, segments=6)
            parts.append((pv, pf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"SpikeFence_{style}", verts, faces,
                        style=style, category="camp")


# =========================================================================
# CATEGORY: DUNGEON PROPS & TRAPS (expanded)
# =========================================================================


def generate_portcullis_mesh(
    width: float = 2.0,
    height: float = 2.5,
) -> MeshSpec:
    """Generate an iron portcullis gate mesh.

    Args:
        width: Gate width.
        height: Gate height.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bar_r = 0.018
    h_bar_r = 0.012
    v_bar_count = 8
    h_bar_count = 5
    bar_spacing = width / (v_bar_count + 1)

    # Vertical bars with pointed bottoms
    for i in range(v_bar_count):
        bx = -width / 2 + (i + 1) * bar_spacing
        bv, bf = _make_cylinder(bx, 0, 0, bar_r, height, segments=6)
        parts.append((bv, bf))
        # Pointed tip at bottom
        pv, pf = _make_cone(bx, -0.08, 0, bar_r, 0.08, segments=6)
        parts.append((pv, pf))

    # Horizontal bars
    for j in range(h_bar_count):
        hy = (j + 1) * height / (h_bar_count + 1)
        hv, hf = _make_box(0, hy, 0, width / 2, h_bar_r, h_bar_r)
        parts.append((hv, hf))

    # Top frame bar
    tv, tf = _make_beveled_box(0, height + 0.03, 0,
                               width / 2 + 0.04, 0.03, 0.03,
                               bevel=0.005)
    parts.append((tv, tf))

    # Track channels on sides
    track_depth = 0.04
    track_width = bar_r * 3
    for side in [-1, 1]:
        tx = side * (width / 2 + track_width)
        tv2, tf2 = _make_beveled_box(tx, height / 2, 0,
                                     track_width / 2, height / 2, track_depth,
                                     bevel=0.003)
        parts.append((tv2, tf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Portcullis", verts, faces, category="dungeon_prop")


def generate_iron_gate_mesh(
    width: float = 1.2,
    height: float = 2.0,
    style: str = "barred",
) -> MeshSpec:
    """Generate an iron gate/door mesh.

    Args:
        width: Gate width.
        height: Gate height.
        style: "barred", "solid", or "ornate".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    frame_w = 0.06
    frame_d = 0.04

    # Door frame
    lv, lf = _make_beveled_box(-width / 2 - frame_w / 2, height / 2, 0,
                               frame_w / 2, height / 2, frame_d,
                               bevel=0.005)
    parts.append((lv, lf))
    rv, rf = _make_beveled_box(width / 2 + frame_w / 2, height / 2, 0,
                               frame_w / 2, height / 2, frame_d,
                               bevel=0.005)
    parts.append((rv, rf))
    tv, tf = _make_beveled_box(0, height + frame_w / 2, 0,
                               width / 2 + frame_w, frame_w / 2, frame_d,
                               bevel=0.005)
    parts.append((tv, tf))

    if style == "barred":
        bar_r = 0.012
        bar_count = 6
        spacing = width / (bar_count + 1)
        for i in range(bar_count):
            bx = -width / 2 + (i + 1) * spacing
            bv, bf = _make_cylinder(bx, 0, 0, bar_r, height, segments=6)
            parts.append((bv, bf))
        cv, cf = _make_box(0, height * 0.5, 0, width / 2, 0.015, 0.015)
        parts.append((cv, cf))
        cv2, cf2 = _make_box(0, height * 0.25, 0, width / 2, 0.015, 0.015)
        parts.append((cv2, cf2))

    elif style == "solid":
        panel_thick = 0.02
        pv, pf = _make_beveled_box(0, height / 2, 0,
                                   width / 2 - 0.01, height / 2 - 0.01, panel_thick,
                                   bevel=0.003)
        parts.append((pv, pf))
        rivet_r = 0.006
        for rx in [-width * 0.3, 0, width * 0.3]:
            for ry in [height * 0.2, height * 0.5, height * 0.8]:
                sv, sf = _make_sphere(rx, ry, panel_thick + rivet_r * 0.5,
                                      rivet_r, rings=3, sectors=4)
                parts.append((sv, sf))

    else:  # ornate
        bar_r = 0.014
        bar_count = 5
        spacing = width / (bar_count + 1)
        for i in range(bar_count):
            bx = -width / 2 + (i + 1) * spacing
            bv, bf = _make_cylinder(bx, 0, 0, bar_r, height, segments=6)
            parts.append((bv, bf))
            sv, sf = _make_torus_ring(bx, height * 0.5, 0,
                                      0.04, 0.006,
                                      major_segments=8, minor_segments=4)
            parts.append((sv, sf))
        for i in range(8):
            angle = math.pi * i / 7
            ox = -width * 0.3 + math.cos(angle) * width * 0.3
            oy = height - 0.1 + math.sin(angle) * 0.15
            sv2, sf2 = _make_sphere(ox, oy, 0, 0.012, rings=3, sectors=4)
            parts.append((sv2, sf2))

    # Hinge hardware
    for hy in [height * 0.2, height * 0.8]:
        hv, hf = _make_cylinder(-width / 2 - frame_w, hy, 0,
                                0.015, 0.06, segments=6)
        parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"IronGate_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_bridge_plank_mesh(
    length: float = 3.0,
    width: float = 1.0,
    style: str = "wooden",
) -> MeshSpec:
    """Generate a bridge plank/walkway mesh.

    Args:
        length: Bridge length.
        width: Bridge width.
        style: "wooden", "stone", or "rope".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "wooden":
        plank_d = 0.12
        gap = 0.02
        plank_count = max(1, int(length / (plank_d + gap)))
        plank_w = width * 0.9
        plank_thick = 0.03

        for i in range(plank_count):
            z = -length / 2 + i * (plank_d + gap)
            pv, pf = _make_beveled_box(0, -plank_thick / 2, z,
                                       plank_w / 2, plank_thick / 2, plank_d / 2,
                                       bevel=0.003)
            parts.append((pv, pf))

        for bx in [-width * 0.35, width * 0.35]:
            sv, sf = _make_box(bx, -plank_thick - 0.03, 0,
                               0.04, 0.03, length / 2)
            parts.append((sv, sf))

    elif style == "stone":
        slab_thick = 0.08
        sv, sf = _make_beveled_box(0, -slab_thick / 2, 0,
                                   width / 2, slab_thick / 2, length / 2,
                                   bevel=0.01)
        parts.append((sv, sf))

        post_count = max(2, int(length / 0.8))
        for i in range(post_count):
            z = -length / 2 + (i + 0.5) * length / post_count
            for x_side in [-width / 2 - 0.05, width / 2 + 0.05]:
                pv, pf = _make_beveled_box(x_side, 0.25, z,
                                           0.04, 0.25, 0.04,
                                           bevel=0.005)
                parts.append((pv, pf))

    else:  # rope
        plank_count = max(2, int(length / 0.18))
        plank_w = width * 0.8
        plank_thick = 0.02
        rope_r = 0.012

        for i in range(plank_count):
            t = i / max(plank_count - 1, 1)
            z = -length / 2 + t * length
            sag = -math.sin(t * math.pi) * length * 0.04
            pv, pf = _make_box(0, sag, z, plank_w / 2, plank_thick / 2, 0.06)
            parts.append((pv, pf))

        for x_side in [-width / 2, width / 2]:
            rope_segs = plank_count * 2
            for j in range(rope_segs):
                t0 = j / rope_segs
                t1 = (j + 1) / rope_segs
                z0 = -length / 2 + t0 * length
                z1 = -length / 2 + t1 * length
                sag0 = -math.sin(t0 * math.pi) * length * 0.03 + 0.3
                sag1 = -math.sin(t1 * math.pi) * length * 0.03 + 0.3
                rv, rf = _make_box(x_side, (sag0 + sag1) / 2, (z0 + z1) / 2,
                                   rope_r, rope_r, abs(z1 - z0) / 2 + 0.001)
                parts.append((rv, rf))

        for i in range(0, plank_count, 2):
            t = i / max(plank_count - 1, 1)
            z = -length / 2 + t * length
            sag = -math.sin(t * math.pi) * length * 0.04
            rail_y = -math.sin(t * math.pi) * length * 0.03 + 0.3
            for x_side in [-width / 2, width / 2]:
                rv2, rf2 = _make_box(x_side, (sag + rail_y) / 2, z,
                                     rope_r, max(0.001, (rail_y - sag) / 2), rope_r)
                parts.append((rv2, rf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"BridgePlank_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_shackle_mesh(
    style: str = "wall",
) -> MeshSpec:
    """Generate an iron shackle/manacle mesh.

    Args:
        style: "wall" (wall-mounted), "floor", or "hanging".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    ring_r = 0.035
    wire_r = 0.006
    chain_link_r = 0.015
    chain_wire = 0.004

    if style == "wall":
        mv, mf = _make_beveled_box(0, 0, -0.02, 0.04, 0.04, 0.02, bevel=0.003)
        parts.append((mv, mf))
        bv, bf = _make_cylinder(0, 0, -0.04, 0.008, 0.01, segments=6)
        parts.append((bv, bf))
        for i in range(4):
            cy = -ring_r * 2 - i * chain_link_r * 2.5
            if i % 2 == 0:
                cv, cf = _make_torus_ring(0, cy, 0, chain_link_r, chain_wire,
                                          major_segments=6, minor_segments=3)
            else:
                cv, cf = _make_torus_ring(0, cy, 0, chain_link_r, chain_wire,
                                          major_segments=6, minor_segments=3)
                cv = [(v[2], v[1], v[0]) for v in cv]
            parts.append((cv, cf))
        shackle_y = -ring_r * 2 - 4 * chain_link_r * 2.5
        for j in range(10):
            angle = math.pi * 0.15 + j * math.pi * 1.4 / 9
            sx = math.cos(angle) * ring_r
            sy = shackle_y + math.sin(angle) * ring_r
            sv, sf = _make_sphere(sx, sy, 0, wire_r, rings=3, sectors=4)
            parts.append((sv, sf))

    elif style == "floor":
        pv, pf = _make_cylinder(0, -0.01, 0, 0.06, 0.01, segments=8)
        parts.append((pv, pf))
        rv, rf = _make_torus_ring(0, 0.005, 0, 0.03, 0.006,
                                  major_segments=8, minor_segments=4)
        parts.append((rv, rf))
        for i in range(3):
            cy = 0.02 + i * chain_link_r * 2.5
            if i % 2 == 0:
                cv, cf = _make_torus_ring(0, cy, 0, chain_link_r, chain_wire,
                                          major_segments=6, minor_segments=3)
            else:
                cv, cf = _make_torus_ring(0, cy, 0, chain_link_r, chain_wire,
                                          major_segments=6, minor_segments=3)
                cv = [(v[2], v[1], v[0]) for v in cv]
            parts.append((cv, cf))
        shackle_y = 0.02 + 3 * chain_link_r * 2.5
        sv, sf = _make_torus_ring(0, shackle_y, 0, ring_r, wire_r,
                                  major_segments=10, minor_segments=4)
        parts.append((sv, sf))

    else:  # hanging
        mv, mf = _make_cylinder(0, 0, 0, 0.03, 0.02, segments=8)
        parts.append((mv, mf))
        for i in range(8):
            cy = -0.03 - i * chain_link_r * 2.5
            if i % 2 == 0:
                cv, cf = _make_torus_ring(0, cy, 0, chain_link_r, chain_wire,
                                          major_segments=6, minor_segments=3)
            else:
                cv, cf = _make_torus_ring(0, cy, 0, chain_link_r, chain_wire,
                                          major_segments=6, minor_segments=3)
                cv = [(v[2], v[1], v[0]) for v in cv]
            parts.append((cv, cf))
        shackle_y = -0.03 - 8 * chain_link_r * 2.5
        sv, sf = _make_torus_ring(0, shackle_y, 0, ring_r, wire_r,
                                  major_segments=10, minor_segments=4)
        parts.append((sv, sf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Shackle_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_cage_mesh(
    style: str = "hanging",
    size: float = 0.8,
) -> MeshSpec:
    """Generate a prison cage mesh.

    Args:
        style: "hanging", "floor", or "gibbet".
        size: Overall cage size.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bar_r = size * 0.008
    cage_r = size * 0.35
    cage_h = size

    if style == "hanging":
        bar_count = 10
        for i in range(bar_count):
            angle = 2.0 * math.pi * i / bar_count
            bx = math.cos(angle) * cage_r
            bz = math.sin(angle) * cage_r
            bv, bf = _make_cylinder(bx, 0, bz, bar_r, cage_h, segments=4)
            parts.append((bv, bf))
        for ry in [0.0, cage_h * 0.33, cage_h * 0.66, cage_h]:
            rv, rf = _make_torus_ring(0, ry, 0, cage_r, bar_r * 1.5,
                                      major_segments=bar_count, minor_segments=3)
            parts.append((rv, rf))
        cv, cf = _make_cone(0, cage_h, 0, cage_r, size * 0.15, segments=bar_count)
        parts.append((cv, cf))
        bpv, bpf = _make_cylinder(0, -bar_r, 0, cage_r, bar_r * 2, segments=bar_count)
        parts.append((bpv, bpf))
        chv, chf = _make_cylinder(0, cage_h + size * 0.15, 0,
                                  bar_r * 2, size * 0.5, segments=4)
        parts.append((chv, chf))

    elif style == "floor":
        cage_w = size * 0.6
        cage_d = size * 0.6
        bar_count_side = 5
        for i in range(bar_count_side):
            bx = -cage_w / 2 + (i + 0.5) * cage_w / bar_count_side
            for z_side in [-cage_d / 2, cage_d / 2]:
                bv, bf = _make_cylinder(bx, 0, z_side, bar_r, cage_h, segments=4)
                parts.append((bv, bf))
        for j in range(bar_count_side):
            bz = -cage_d / 2 + (j + 0.5) * cage_d / bar_count_side
            for x_side in [-cage_w / 2, cage_w / 2]:
                bv, bf = _make_cylinder(x_side, 0, bz, bar_r, cage_h, segments=4)
                parts.append((bv, bf))
        for fy in [-0.01, cage_h]:
            for pos_pair in [
                (0, fy, -cage_d / 2, cage_w / 2, bar_r * 2, bar_r * 2),
                (0, fy, cage_d / 2, cage_w / 2, bar_r * 2, bar_r * 2),
                (-cage_w / 2, fy, 0, bar_r * 2, bar_r * 2, cage_d / 2),
                (cage_w / 2, fy, 0, bar_r * 2, bar_r * 2, cage_d / 2),
            ]:
                fv, ff = _make_box(*pos_pair)
                parts.append((fv, ff))

    else:  # gibbet
        n_rings = 6
        for ring_i in range(n_rings):
            t = ring_i / (n_rings - 1)
            ry = t * cage_h
            shape = 1.0 - 2.0 * abs(t - 0.4)
            rr = cage_r * max(0.4, shape)
            rv, rf = _make_torus_ring(0, ry, 0, rr, bar_r * 1.5,
                                      major_segments=8, minor_segments=3)
            parts.append((rv, rf))
        for i in range(8):
            angle = 2.0 * math.pi * i / 8
            for seg in range(n_rings - 1):
                t0 = seg / (n_rings - 1)
                t1 = (seg + 1) / (n_rings - 1)
                shape0 = max(0.4, 1.0 - 2.0 * abs(t0 - 0.4))
                shape1 = max(0.4, 1.0 - 2.0 * abs(t1 - 0.4))
                x0 = math.cos(angle) * cage_r * shape0
                z0 = math.sin(angle) * cage_r * shape0
                y0 = t0 * cage_h
                y1 = t1 * cage_h
                sv, sf = _make_box(
                    (x0 + math.cos(angle) * cage_r * shape1) / 2,
                    (y0 + y1) / 2,
                    (z0 + math.sin(angle) * cage_r * shape1) / 2,
                    bar_r, (y1 - y0) / 2, bar_r,
                )
                parts.append((sv, sf))
        hv, hf = _make_cone(0, cage_h + 0.02, 0, bar_r * 3, 0.05, segments=6)
        parts.append((hv, hf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cage_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_stocks_mesh() -> MeshSpec:
    """Generate a wooden stocks (pillory) mesh for prisoners.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    board_w = 0.8
    board_h = 0.04
    board_d = 0.25

    post_h = 1.0
    post_r = 0.05
    for x_side in [-board_w / 2 - 0.02, board_w / 2 + 0.02]:
        pv, pf = _make_beveled_box(x_side, post_h / 2, 0,
                                   post_r, post_h / 2, post_r,
                                   bevel=0.005)
        parts.append((pv, pf))

    board_y = post_h * 0.65
    bv, bf = _make_beveled_box(0, board_y, 0,
                               board_w / 2, board_h / 2, board_d / 2,
                               bevel=0.003)
    parts.append((bv, bf))
    tv, tf = _make_beveled_box(0, board_y + board_h + 0.005, 0,
                               board_w / 2, board_h / 2, board_d / 2,
                               bevel=0.003)
    parts.append((tv, tf))

    head_r = 0.07
    hv, hf = _make_torus_ring(0, board_y + board_h / 2, 0,
                               head_r, 0.008,
                               major_segments=10, minor_segments=4)
    parts.append((hv, hf))

    hand_r = 0.04
    for hx in [-board_w * 0.3, board_w * 0.3]:
        handv, handf = _make_torus_ring(hx, board_y + board_h / 2, 0,
                                        hand_r, 0.006,
                                        major_segments=8, minor_segments=3)
        parts.append((handv, handf))

    basev, basef = _make_beveled_box(0, 0.02, 0,
                                     board_w / 2 + 0.1, 0.02, 0.15,
                                     bevel=0.005)
    parts.append((basev, basef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("Stocks", verts, faces, category="dungeon_prop")


def generate_iron_maiden_mesh() -> MeshSpec:
    """Generate a medieval iron maiden mesh.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    w = 0.35
    h = 1.8
    d = 0.3

    body_profile = [
        (w * 0.4, 0),
        (w * 0.48, h * 0.05),
        (w * 0.5, h * 0.15),
        (w * 0.5, h * 0.65),
        (w * 0.45, h * 0.80),
        (w * 0.35, h * 0.90),
        (w * 0.2, h * 0.95),
        (w * 0.05, h),
    ]
    bv, bf = _make_lathe(body_profile, segments=10, close_bottom=True, close_top=True)
    parts.append((bv, bf))

    door_profile = [
        (w * 0.38, 0),
        (w * 0.46, h * 0.05),
        (w * 0.48, h * 0.15),
        (w * 0.48, h * 0.65),
        (w * 0.43, h * 0.80),
        (w * 0.33, h * 0.90),
        (w * 0.18, h * 0.95),
        (w * 0.03, h),
    ]
    door_segs = 5
    door_verts: list[tuple[float, float, float]] = []
    door_faces: list[tuple[int, ...]] = []
    n_prof = len(door_profile)
    door_offset_x = w * 0.6

    for i in range(n_prof):
        r, y = door_profile[i]
        for j in range(door_segs + 1):
            angle = -math.pi / 2 + j * math.pi / door_segs
            door_verts.append((
                door_offset_x + r * math.cos(angle),
                y,
                d * 0.3 + r * math.sin(angle),
            ))

    for i in range(n_prof - 1):
        for j in range(door_segs):
            v0 = i * (door_segs + 1) + j
            v1 = v0 + 1
            v2 = v0 + door_segs + 2
            v3 = v0 + door_segs + 1
            door_faces.append((v0, v1, v2, v3))

    parts.append((door_verts, door_faces))

    spike_count = 8
    for i in range(spike_count):
        sy = h * 0.1 + i * h * 0.7 / spike_count
        for angle_off in [-0.5, 0, 0.5]:
            spike_r = w * 0.35
            sx = math.cos(math.pi + angle_off) * spike_r * 0.3
            sz = math.sin(math.pi + angle_off) * spike_r * 0.3
            sv, sf = _make_cone(sx, sy, sz, 0.005, 0.04, segments=4)
            parts.append((sv, sf))

    for hy in [h * 0.2, h * 0.8]:
        hv, hf = _make_cylinder(w * 0.5, hy, d * 0.15, 0.01, 0.04, segments=6)
        parts.append((hv, hf))

    basev, basef = _make_beveled_box(0, -0.02, 0,
                                     w * 0.6, 0.02, d * 0.5,
                                     bevel=0.005)
    parts.append((basev, basef))

    verts, faces = _merge_meshes(*parts)
    return _make_result("IronMaiden", verts, faces, category="dungeon_prop")


def generate_prisoner_skeleton_mesh() -> MeshSpec:
    """Generate a chained prisoner skeleton prop mesh.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bone_r = 0.012

    sv, sf = _make_sphere(0, 1.6, 0, 0.08, rings=5, sectors=8)
    parts.append((sv, sf))
    for ex in [-0.025, 0.025]:
        ev, ef = _make_sphere(ex, 1.62, 0.06, 0.02, rings=3, sectors=4)
        parts.append((ev, ef))
    jv, jf = _make_sphere(0, 1.55, 0.02, 0.04, rings=3, sectors=6)
    parts.append((jv, jf))

    for i in range(8):
        sy = 1.5 - i * 0.06
        sv2, sf2 = _make_cylinder(0, sy, 0, bone_r, 0.05, segments=5)
        parts.append((sv2, sf2))

    for i in range(5):
        rib_y = 1.35 - i * 0.05
        for side in [-1, 1]:
            for j in range(4):
                angle = side * (0.3 + j * 0.25)
                rx = math.sin(angle) * 0.12
                rz = math.cos(angle) * 0.12 - 0.05
                rv, rf = _make_sphere(rx, rib_y, rz, bone_r * 0.8,
                                      rings=2, sectors=4)
                parts.append((rv, rf))

    pv, pf = _make_sphere(0, 1.0, 0, 0.07, rings=4, sectors=6)
    parts.append((pv, pf))

    for side in [-1, 1]:
        for j in range(4):
            ay = 1.45 - j * 0.08
            ax = side * (0.15 + j * 0.01)
            av, af = _make_cylinder(ax, ay, 0, bone_r, 0.07, segments=4)
            parts.append((av, af))
        for j in range(4):
            ay = 1.12 - j * 0.08
            ax = side * 0.19
            av, af = _make_cylinder(ax, ay, 0, bone_r * 0.9, 0.07, segments=4)
            parts.append((av, af))
        wrist_y = 1.12 - 4 * 0.08
        sv3, sf3 = _make_torus_ring(side * 0.19, wrist_y, 0,
                                    0.025, 0.005,
                                    major_segments=8, minor_segments=3)
        parts.append((sv3, sf3))

    for side in [-1, 1]:
        for j in range(6):
            ly = 0.95 - j * 0.08
            lx = side * 0.06
            lv, lf = _make_cylinder(lx, ly, 0, bone_r, 0.07, segments=4)
            parts.append((lv, lf))

    chain_r = 0.015
    chain_wire = 0.004
    for i in range(4):
        cy = 1.75 + i * chain_r * 2.5
        if i % 2 == 0:
            cv, cf = _make_torus_ring(0, cy, 0, chain_r, chain_wire,
                                      major_segments=6, minor_segments=3)
        else:
            cv, cf = _make_torus_ring(0, cy, 0, chain_r, chain_wire,
                                      major_segments=6, minor_segments=3)
            cv = [(v[2], v[1], v[0]) for v in cv]
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("PrisonerSkeleton", verts, faces, category="dungeon_prop")


def generate_summoning_circle_mesh(
    radius: float = 1.5,
    rune_count: int = 8,
) -> MeshSpec:
    """Generate a summoning circle floor marking mesh.

    Args:
        radius: Circle radius.
        rune_count: Number of rune symbols.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    line_h = 0.008
    line_w = 0.015

    orv, orf = _make_torus_ring(0, line_h, 0, radius, line_w,
                                major_segments=32, minor_segments=4)
    parts.append((orv, orf))

    inner_r = radius * 0.65
    irv, irf = _make_torus_ring(0, line_h, 0, inner_r, line_w * 0.8,
                                major_segments=24, minor_segments=4)
    parts.append((irv, irf))

    star_r = radius * 0.6
    for i in range(5):
        angle0 = math.pi / 2 + i * 2 * math.pi / 5
        angle1 = math.pi / 2 + ((i + 2) % 5) * 2 * math.pi / 5
        x0 = math.cos(angle0) * star_r
        z0 = math.sin(angle0) * star_r
        x1 = math.cos(angle1) * star_r
        z1 = math.sin(angle1) * star_r
        mx = (x0 + x1) / 2
        mz = (z0 + z1) / 2
        line_len = math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2) / 2
        lv, lf = _make_box(mx, line_h, mz, line_w, line_h * 0.5, line_len)
        ang = math.atan2(z1 - z0, x1 - x0)
        ca, sa = math.cos(ang), math.sin(ang)
        l_verts = []
        for v in lv:
            nx = mx + (v[0] - mx) * ca - (v[2] - mz) * sa
            nz = mz + (v[0] - mx) * sa + (v[2] - mz) * ca
            l_verts.append((nx, v[1], nz))
        parts.append((l_verts, lf))

    for i in range(rune_count):
        angle = 2.0 * math.pi * i / rune_count
        rx = math.cos(angle) * radius
        rz = math.sin(angle) * radius
        rv, rf = _make_beveled_box(rx, 0.02, rz,
                                   0.025, 0.02, 0.015,
                                   bevel=0.003)
        parts.append((rv, rf))

    cv, cf = _make_sphere(0, 0.02, 0, 0.03, rings=4, sectors=6)
    parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SummoningCircle", verts, faces,
                        rune_count=rune_count, category="dark_fantasy")


def generate_ritual_candles_mesh(
    count: int = 5,
    arrangement: str = "circle",
) -> MeshSpec:
    """Generate a cluster of ritual candles.

    Args:
        count: Number of candles (3-9).
        arrangement: "circle" or "cluster".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng_candles
    rng = _rng_candles.Random(55)
    parts = []
    count = max(3, min(9, count))

    for i in range(count):
        if arrangement == "circle":
            angle = 2.0 * math.pi * i / count
            dist = 0.12
            cx = math.cos(angle) * dist
            cz = math.sin(angle) * dist
        else:
            cx = rng.uniform(-0.1, 0.1)
            cz = rng.uniform(-0.1, 0.1)

        candle_h = 0.08 + rng.uniform(0, 0.06)
        candle_r = 0.008 + rng.uniform(0, 0.004)

        cv, cf = _make_tapered_cylinder(cx, 0, cz,
                                        candle_r, candle_r * 0.85, candle_h,
                                        segments=6, cap_top=True, cap_bottom=True)
        parts.append((cv, cf))

        dv, df = _make_sphere(cx + candle_r * 0.5, candle_h * 0.7, cz,
                              candle_r * 0.4, rings=3, sectors=4)
        parts.append((dv, df))

        fv, ff = _make_cone(cx, candle_h, cz,
                            candle_r * 0.5, candle_r * 2.5, segments=4)
        parts.append((fv, ff))

        wv, wf = _make_cylinder(cx, candle_h - 0.002, cz,
                                0.001, candle_r * 1.5, segments=3)
        parts.append((wv, wf))

    pool_r = 0.15 if arrangement == "circle" else 0.12
    pv, pf = _make_cylinder(0, -0.002, 0, pool_r, 0.002, segments=12)
    parts.append((pv, pf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("RitualCandles", verts, faces,
                        count=count, category="dark_fantasy")


def generate_occult_symbols_mesh(
    symbol_type: str = "pentagram",
) -> MeshSpec:
    """Generate floor-level occult symbol geometry.

    Args:
        symbol_type: "pentagram", "runes", or "sigil".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    line_h = 0.005
    line_w = 0.012

    if symbol_type == "pentagram":
        radius = 0.4
        orv, orf = _make_torus_ring(0, line_h, 0, radius, line_w,
                                    major_segments=24, minor_segments=3)
        parts.append((orv, orf))
        for i in range(5):
            a0 = math.pi / 2 + i * 2 * math.pi / 5
            a1 = math.pi / 2 + ((i + 2) % 5) * 2 * math.pi / 5
            x0 = math.cos(a0) * radius * 0.9
            z0 = math.sin(a0) * radius * 0.9
            x1 = math.cos(a1) * radius * 0.9
            z1 = math.sin(a1) * radius * 0.9
            mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
            line_len = math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2)
            lv, lf = _make_box(mx, line_h, mz, line_w, line_h, line_len / 2)
            ang = math.atan2(z1 - z0, x1 - x0)
            ca, sa = math.cos(ang), math.sin(ang)
            l_verts = [(mx + (v[0] - mx) * ca - (v[2] - mz) * sa,
                        v[1],
                        mz + (v[0] - mx) * sa + (v[2] - mz) * ca) for v in lv]
            parts.append((l_verts, lf))

    elif symbol_type == "runes":
        for i in range(5):
            rx = -0.3 + i * 0.15
            rv, rf = _make_beveled_box(rx, 0.015, 0,
                                       0.025, 0.015, 0.035,
                                       bevel=0.003)
            parts.append((rv, rf))
            lv, lf = _make_box(rx, 0.031, 0, 0.002, 0.001, 0.025)
            parts.append((lv, lf))
            lv2, lf2 = _make_box(rx + 0.008, 0.031, 0.01, 0.008, 0.001, 0.002)
            parts.append((lv2, lf2))

    else:  # sigil
        for ring_r in [0.15, 0.25, 0.35]:
            rv, rf = _make_torus_ring(0, line_h, 0, ring_r, line_w * 0.8,
                                      major_segments=20, minor_segments=3)
            parts.append((rv, rf))
        for angle in [0, math.pi / 2, math.pi / 4, -math.pi / 4]:
            x0 = math.cos(angle) * 0.35
            z0 = math.sin(angle) * 0.35
            lv, lf = _make_box(x0 / 2, line_h, z0 / 2,
                               line_w, line_h, 0.175)
            ca, sa = math.cos(angle), math.sin(angle)
            l_verts = [(v[0] * ca - v[2] * sa, v[1],
                        v[0] * sa + v[2] * ca) for v in lv]
            parts.append((l_verts, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"OccultSymbols_{symbol_type}", verts, faces,
                        symbol_type=symbol_type, category="dark_fantasy")


def generate_cobweb_mesh(
    style: str = "corner",
    size: float = 0.5,
) -> MeshSpec:
    """Generate a cobweb mesh.

    Args:
        style: "corner", "spanning", or "draped".
        size: Overall web size.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    strand_r = 0.002

    if style == "corner":
        radials = 6
        rings = 4
        for i in range(radials):
            t = i / max(radials - 1, 1)
            ex = size * (1.0 - t)
            ez = size * t
            n_segs = rings * 2
            for j in range(n_segs):
                s0 = j / n_segs
                s1 = (j + 1) / n_segs
                x0, z0 = ex * s0, ez * s0
                x1, z1 = ex * s1, ez * s1
                sag = -0.01 * math.sin(s0 * math.pi) * size
                seg_len = max(0.001, math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2) / 2)
                sv, sf = _make_box((x0 + x1) / 2, sag, (z0 + z1) / 2,
                                   strand_r, strand_r, seg_len)
                parts.append((sv, sf))

        for ring in range(1, rings + 1):
            rt = ring / rings
            arc_segs = radials * 2
            for i in range(arc_segs):
                a0 = i / arc_segs
                a1 = (i + 1) / arc_segs
                x0 = size * (1.0 - a0) * rt
                z0 = size * a0 * rt
                x1 = size * (1.0 - a1) * rt
                z1 = size * a1 * rt
                sag = -0.005 * math.sin(rt * math.pi) * size
                seg_len = max(0.001, math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2) / 2)
                sv, sf = _make_box((x0 + x1) / 2, sag, (z0 + z1) / 2,
                                   strand_r, strand_r, seg_len)
                parts.append((sv, sf))

    elif style == "spanning":
        radials = 8
        rings = 5
        hv, hf = _make_sphere(0, 0, 0, strand_r * 3, rings=3, sectors=4)
        parts.append((hv, hf))

        for i in range(radials):
            angle = 2.0 * math.pi * i / radials
            n_segs = rings * 2
            for j in range(n_segs):
                s = (j + 0.5) / n_segs
                x0 = math.cos(angle) * size * j / n_segs
                z0 = math.sin(angle) * size * j / n_segs
                sag = -0.015 * math.sin(s * math.pi) * size
                sv, sf = _make_box(x0, sag, z0,
                                   strand_r, strand_r, size / n_segs / 2)
                ca, sa = math.cos(angle), math.sin(angle)
                s_verts = [(v[0] * ca - v[2] * sa, v[1],
                            v[0] * sa + v[2] * ca) for v in sv]
                parts.append((s_verts, sf))

        for ring in range(1, rings + 1):
            ring_r = size * ring / rings
            n_arc = radials * 3
            for i in range(n_arc):
                a0 = 2.0 * math.pi * i / n_arc
                a1 = 2.0 * math.pi * (i + 1) / n_arc
                x0 = math.cos(a0) * ring_r
                z0 = math.sin(a0) * ring_r
                x1 = math.cos(a1) * ring_r
                z1 = math.sin(a1) * ring_r
                sag = -0.008 * math.sin((ring / rings) * math.pi) * size
                sv, sf = _make_box((x0 + x1) / 2, sag, (z0 + z1) / 2,
                                   strand_r, strand_r,
                                   ring_r * math.pi / n_arc)
                mid_angle = (a0 + a1) / 2
                ca, sa = math.cos(mid_angle + math.pi / 2), math.sin(mid_angle + math.pi / 2)
                s_verts = [(v[0] * ca - v[2] * sa, v[1],
                            v[0] * sa + v[2] * ca) for v in sv]
                parts.append((s_verts, sf))

    else:  # draped
        strand_count = 8
        for i in range(strand_count):
            sx = -size / 2 + i * size / max(strand_count - 1, 1)
            n_segs = 6
            for j in range(n_segs):
                t = j / n_segs
                sy = -t * size * 0.8
                sag = math.sin(t * math.pi) * 0.03 * (1 + (i % 3) * 0.5)
                sv, sf = _make_box(sx, sy, sag,
                                   strand_r, size * 0.8 / n_segs / 2, strand_r)
                parts.append((sv, sf))
            if i < strand_count - 1:
                for j in range(0, n_segs, 2):
                    t = j / n_segs
                    y = -t * size * 0.8
                    x0 = sx
                    x1 = -size / 2 + (i + 1) * size / max(strand_count - 1, 1)
                    cv, cf = _make_box((x0 + x1) / 2, y, 0,
                                       abs(x1 - x0) / 2, strand_r, strand_r)
                    parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cobweb_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_spider_egg_sac_mesh(
    count: int = 5,
) -> MeshSpec:
    """Generate a cluster of spider egg sacs.

    Args:
        count: Number of egg sacs in the cluster.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng_eggs
    rng = _rng_eggs.Random(88)
    parts = []

    for _ in range(count):
        ox = rng.uniform(-0.08, 0.08)
        oy = rng.uniform(-0.03, 0.03)
        oz = rng.uniform(-0.08, 0.08)
        sac_r = rng.uniform(0.02, 0.04)

        egg_profile = [
            (0.001, oy - sac_r * 0.8),
            (sac_r * 0.6, oy - sac_r * 0.5),
            (sac_r, oy),
            (sac_r * 0.8, oy + sac_r * 0.4),
            (sac_r * 0.3, oy + sac_r * 0.7),
            (0.001, oy + sac_r * 0.8),
        ]
        ev, ef = _make_lathe(egg_profile, segments=6, close_bottom=True, close_top=True)
        e_verts = [(v[0] + ox, v[1], v[2] + oz) for v in ev]
        parts.append((e_verts, ef))

    thread_r = 0.001
    rng2 = _rng_eggs.Random(88)
    positions = []
    for _ in range(count):
        positions.append((
            rng2.uniform(-0.08, 0.08),
            rng2.uniform(-0.03, 0.03),
            rng2.uniform(-0.08, 0.08),
        ))
    for i in range(min(count - 1, 4)):
        p0 = positions[i]
        p1 = positions[i + 1]
        mx = (p0[0] + p1[0]) / 2
        my = (p0[1] + p1[1]) / 2
        mz = (p0[2] + p1[2]) / 2
        dist = max(0.001, math.sqrt(sum((a - b) ** 2 for a, b in zip(p0, p1))) / 2)
        tv, tf = _make_box(mx, my, mz, thread_r, thread_r, dist)
        parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("SpiderEggSac", verts, faces,
                        count=count, category="dungeon_prop")


def generate_rubble_pile_mesh(
    style: str = "stone",
    size: float = 0.5,
) -> MeshSpec:
    """Generate a pile of rubble/debris.

    Args:
        style: "stone", "wood", or "mixed".
        size: Overall pile size.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng_rubble
    rng = _rng_rubble.Random(44)
    parts = []

    mound_profile = [
        (0.001, 0),
        (size * 0.6, size * 0.02),
        (size * 0.8, size * 0.08),
        (size * 0.6, size * 0.15),
        (size * 0.3, size * 0.2),
        (0.001, size * 0.22),
    ]
    mv, mf = _make_lathe(mound_profile, segments=8, close_bottom=True, close_top=True)
    parts.append((mv, mf))

    chunk_count = 12 if style in ("stone", "mixed") else 8

    for _ in range(chunk_count):
        cx = rng.uniform(-size * 0.6, size * 0.6)
        cz = rng.uniform(-size * 0.6, size * 0.6)
        dist = math.sqrt(cx * cx + cz * cz)
        if dist > size * 0.7:
            continue
        cy = size * 0.15 * (1.0 - dist / size) + rng.uniform(0, size * 0.05)

        if style == "stone" or (style == "mixed" and rng.random() > 0.4):
            cs = rng.uniform(size * 0.04, size * 0.12)
            cv, cf = _make_beveled_box(cx, cy, cz,
                                       cs, cs * rng.uniform(0.5, 1.0),
                                       cs * rng.uniform(0.6, 1.2),
                                       bevel=cs * 0.1)
            parts.append((cv, cf))
        else:
            pw = rng.uniform(size * 0.02, size * 0.04)
            pl = rng.uniform(size * 0.1, size * 0.25)
            ph = rng.uniform(size * 0.01, size * 0.03)
            cv, cf = _make_box(cx, cy, cz, pw, ph, pl)
            parts.append((cv, cf))

    dv, df = _make_cylinder(0, -0.005, 0, size * 0.7, 0.005, segments=10)
    parts.append((dv, df))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"RubblePile_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_hanging_skeleton_mesh() -> MeshSpec:
    """Generate a skeleton hanging from chains.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    bone_r = 0.01

    chain_r = 0.015
    chain_wire = 0.004
    for i in range(6):
        cy = 2.0 + i * chain_r * 2.5
        if i % 2 == 0:
            cv, cf = _make_torus_ring(0, cy, 0, chain_r, chain_wire,
                                      major_segments=6, minor_segments=3)
        else:
            cv, cf = _make_torus_ring(0, cy, 0, chain_r, chain_wire,
                                      major_segments=6, minor_segments=3)
            cv = [(v[2], v[1], v[0]) for v in cv]
        parts.append((cv, cf))

    sv, sf = _make_sphere(0, 1.95, 0, 0.07, rings=5, sectors=8)
    parts.append((sv, sf))
    for ex in [-0.02, 0.02]:
        ev, ef = _make_sphere(ex, 1.97, 0.05, 0.018, rings=3, sectors=4)
        parts.append((ev, ef))

    for i in range(6):
        sy = 1.85 - i * 0.06
        sv2, sf2 = _make_cylinder(0, sy, 0, bone_r, 0.05, segments=4)
        parts.append((sv2, sf2))

    for i in range(4):
        rib_y = 1.75 - i * 0.06
        for side in [-1, 1]:
            for j in range(3):
                rx = side * (0.02 + j * 0.03)
                rz = -0.02 - j * 0.01
                rv, rf = _make_sphere(rx, rib_y - j * 0.01, rz,
                                      bone_r * 0.7, rings=2, sectors=4)
                parts.append((rv, rf))

    for side in [-1, 1]:
        for j in range(6):
            ay = 1.80 - j * 0.07
            ax = side * (0.1 + j * 0.005)
            av, af = _make_cylinder(ax, ay, 0, bone_r * 0.8, 0.06, segments=4)
            parts.append((av, af))

    for side in [-1, 1]:
        for j in range(5):
            ly = 1.50 - j * 0.08
            lv, lf = _make_cylinder(side * 0.04, ly, 0, bone_r, 0.07, segments=4)
            parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("HangingSkeleton", verts, faces, category="dungeon_prop")


def generate_dripping_water_mesh() -> MeshSpec:
    """Generate a stalactite with water drip formation.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    length = 0.4
    thickness = 0.06

    profile = [
        (0.001, -length),
        (thickness * 0.1, -length * 0.93),
        (thickness * 0.25, -length * 0.80),
        (thickness * 0.4, -length * 0.65),
        (thickness * 0.55, -length * 0.45),
        (thickness * 0.7, -length * 0.25),
        (thickness * 0.85, -length * 0.10),
        (thickness, 0),
    ]
    sv, sf = _make_lathe(profile, segments=8, close_bottom=True, close_top=True)
    parts.append((sv, sf))

    base_profile = [
        (thickness, 0),
        (thickness * 1.3, 0.01),
        (thickness * 1.4, 0.025),
        (thickness * 1.2, 0.035),
    ]
    bv, bf = _make_lathe(base_profile, segments=8, close_top=True)
    parts.append((bv, bf))

    dv, df = _make_sphere(0, -length - 0.008, 0, 0.006, rings=3, sectors=4)
    parts.append((dv, df))

    pool_y = -length - 1.5
    pv, pf = _make_cylinder(0, pool_y, 0, 0.05, 0.003, segments=8)
    parts.append((pv, pf))

    d2v, d2f = _make_tapered_cylinder(thickness * 0.3, -length * 0.6, thickness * 0.2,
                                      0.001, thickness * 0.2, length * 0.3,
                                      segments=5, cap_top=True, cap_bottom=True)
    parts.append((d2v, d2f))

    verts, faces = _merge_meshes(*parts)
    return _make_result("DrippingWater", verts, faces, category="dungeon_prop")


def generate_rat_nest_mesh() -> MeshSpec:
    """Generate a small rat nest (debris pile).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng_nest
    rng = _rng_nest.Random(66)
    parts = []
    nest_r = 0.12

    mound_profile = [
        (0.001, 0),
        (nest_r * 0.7, 0.005),
        (nest_r, 0.012),
        (nest_r * 0.8, 0.025),
        (nest_r * 0.4, 0.035),
        (0.001, 0.04),
    ]
    mv, mf = _make_lathe(mound_profile, segments=8, close_bottom=True, close_top=True)
    parts.append((mv, mf))

    for _ in range(10):
        sx = rng.uniform(-nest_r * 0.7, nest_r * 0.7)
        sz = rng.uniform(-nest_r * 0.7, nest_r * 0.7)
        if math.sqrt(sx * sx + sz * sz) > nest_r * 0.8:
            continue
        sy = rng.uniform(0.01, 0.035)
        pw = rng.uniform(0.005, 0.015)
        pl = rng.uniform(0.01, 0.03)
        sv, sf = _make_box(sx, sy, sz, pw, 0.002, pl)
        parts.append((sv, sf))

    for _ in range(3):
        bx = rng.uniform(-nest_r * 0.5, nest_r * 0.5)
        bz = rng.uniform(-nest_r * 0.5, nest_r * 0.5)
        bv, bf = _make_cylinder(bx, 0.02, bz, 0.003, 0.025, segments=4)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("RatNest", verts, faces, category="dungeon_prop")


def generate_rotting_barrel_mesh() -> MeshSpec:
    """Generate a damaged/rotting barrel variant.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    height = 0.8
    radius = 0.22

    barrel_profile = []
    rings = 12
    for i in range(rings + 1):
        t = i / rings
        y = t * height
        bulge = 1.0 + 0.08 * math.sin(t * math.pi)
        damage = 1.0 - 0.04 * max(0, math.sin(t * 5.0))
        r = radius * bulge * damage
        barrel_profile.append((r, y))

    bv, bf = _make_lathe(barrel_profile, segments=10, close_bottom=True, close_top=True)
    parts.append((bv, bf))

    band_h = 0.008
    for band_y in [height * 0.25, height * 0.75]:
        t = band_y / height
        bulge = 1.0 + 0.08 * math.sin(t * math.pi)
        br = radius * bulge + 0.003
        rv, rf = _make_torus_ring(0, band_y, 0, br, band_h,
                                  major_segments=10, minor_segments=3)
        parts.append((rv, rf))

    gap_angle = 1.2
    gx = math.cos(gap_angle) * radius * 0.9
    gz = math.sin(gap_angle) * radius * 0.9
    gv, gf = _make_box(gx, height * 0.4, gz, 0.03, height * 0.15, 0.01)
    parts.append((gv, gf))

    lid_profile = [
        (radius * 0.95, height - 0.005),
        (radius * 0.9, height),
        (radius * 0.4, height + 0.01),
        (0.001, height + 0.012),
    ]
    lv, lf = _make_lathe(lid_profile, segments=10, close_bottom=True, close_top=True)
    l_verts = [(v[0] + 0.02, v[1] + 0.01, v[2]) for v in lv]
    parts.append((l_verts, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("RottingBarrel", verts, faces, category="dungeon_prop")


def generate_treasure_chest_mesh(
    style: str = "locked",
    size: float = 1.0,
) -> MeshSpec:
    """Generate a dungeon treasure chest mesh.

    Args:
        style: "locked", "open", "trapped", or "ornate".
        size: Scale factor.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []
    w = 0.5 * size
    h = 0.3 * size
    d = 0.35 * size

    bv, bf = _make_beveled_box(0, h * 0.4, 0,
                               w / 2, h * 0.4, d / 2,
                               bevel=0.008 * size)
    parts.append((bv, bf))

    if style == "open":
        lid_v, lid_f = _make_beveled_box(0, h * 0.85, -d / 2 - 0.05 * size,
                                         w / 2 - 0.01, 0.015 * size, d / 2 * 0.3,
                                         bevel=0.005 * size)
        parts.append((lid_v, lid_f))
        inner_v, inner_f = _make_box(0, h * 0.45, 0,
                                     w / 2 - 0.02 * size, h * 0.1,
                                     d / 2 - 0.02 * size)
        parts.append((inner_v, inner_f))
        for i in range(5):
            angle = i * math.pi * 2 / 5
            gx = math.cos(angle) * w * 0.15
            gz = math.sin(angle) * d * 0.15
            gv, gf = _make_sphere(gx, h * 0.55, gz, 0.012 * size,
                                  rings=3, sectors=4)
            parts.append((gv, gf))
    else:
        lid_segs = 10
        lid_verts: list[tuple[float, float, float]] = []
        lid_faces: list[tuple[int, ...]] = []
        lid_base_y = h * 0.8
        lid_radius = d / 2

        for i in range(lid_segs + 1):
            t = i / lid_segs
            angle = math.pi * t
            y = lid_base_y + math.sin(angle) * lid_radius * 0.4
            z_scale = math.cos(angle)
            for xpos in [-w / 2, w / 2]:
                lid_verts.append((xpos, y, z_scale * lid_radius))

        for i in range(lid_segs):
            bi = i * 2
            lid_faces.append((bi, bi + 1, bi + 3, bi + 2))

        left_indices = [i * 2 for i in range(lid_segs + 1)]
        right_indices = [i * 2 + 1 for i in range(lid_segs + 1)]
        lid_faces.append(tuple(left_indices[::-1]))
        lid_faces.append(tuple(right_indices))
        parts.append((lid_verts, lid_faces))

    band_h = 0.01 * size
    band_offset = 0.005 * size
    for band_y in [h * 0.2, h * 0.6]:
        bv2, bf2 = _make_box(0, band_y, 0,
                              w / 2 + band_offset, band_h, d / 2 + band_offset)
        parts.append((bv2, bf2))

    if style == "locked":
        lv, lf = _make_beveled_box(0, h * 0.75, d / 2 + 0.01 * size,
                                   0.04 * size, 0.04 * size, 0.008 * size,
                                   bevel=0.003 * size)
        parts.append((lv, lf))
        cv, cf = _make_cylinder(0, h * 0.68, d / 2 + 0.018 * size,
                                0.015 * size, 0.04 * size, segments=8)
        parts.append((cv, cf))

    elif style == "trapped":
        pp_v, pp_f = _make_beveled_box(0, h * 0.1, d / 2 + 0.02 * size,
                                       w * 0.3, 0.01 * size, 0.015 * size,
                                       bevel=0.002 * size)
        parts.append((pp_v, pp_f))
        tw_v, tw_f = _make_box(-w * 0.3, h * 0.3, d / 2 + 0.03 * size,
                               w * 0.3, 0.002 * size, 0.002 * size)
        parts.append((tw_v, tw_f))
        lv2, lf2 = _make_beveled_box(0, h * 0.75, d / 2 + 0.008 * size,
                                     0.03 * size, 0.03 * size, 0.006 * size,
                                     bevel=0.002 * size)
        parts.append((lv2, lf2))

    elif style == "ornate":
        corner_r = 0.02 * size
        for xoff in [-w / 2, w / 2]:
            for zoff in [-d / 2, d / 2]:
                for yoff in [0, h * 0.78]:
                    sv, sf = _make_sphere(xoff, yoff, zoff,
                                          corner_r, rings=4, sectors=6)
                    parts.append((sv, sf))
        ev, ef = _make_beveled_box(0, h * 0.4, d / 2 + 0.005 * size,
                                   w * 0.25, h * 0.2, 0.003 * size,
                                   bevel=0.002 * size)
        parts.append((ev, ef))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"TreasureChest_{style}", verts, faces,
                        style=style, category="dungeon_prop")


def generate_gem_pile_mesh(
    size: float = 0.3,
    gem_count: int = 12,
) -> MeshSpec:
    """Generate a scattered pile of gems.

    Args:
        size: Pile spread radius.
        gem_count: Number of gems.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng_gems
    rng = _rng_gems.Random(33)
    parts = []

    for _ in range(gem_count):
        gx = rng.uniform(-size * 0.6, size * 0.6)
        gz = rng.uniform(-size * 0.6, size * 0.6)
        dist = math.sqrt(gx * gx + gz * gz)
        if dist > size * 0.7:
            continue
        gy = 0.005 + rng.uniform(0, size * 0.04)
        gem_r = rng.uniform(size * 0.03, size * 0.06)

        cv, cf = _make_cone(gx, gy, gz, gem_r, gem_r * 1.0, segments=6)
        parts.append((cv, cf))
        bv, bf = _make_sphere(gx, gy - gem_r * 0.2, gz,
                              gem_r * 0.5, rings=3, sectors=6)
        parts.append((bv, bf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("GemPile", verts, faces,
                        gem_count=gem_count, category="dungeon_prop")


def generate_gold_pile_mesh(
    size: float = 0.3,
    coin_count: int = 25,
) -> MeshSpec:
    """Generate a scattered pile of gold coins.

    Args:
        size: Pile spread radius.
        coin_count: Number of coins.

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    import random as _rng_gold
    rng = _rng_gold.Random(42)
    parts = []

    mound_profile = [
        (0.001, 0),
        (size * 0.5, 0.003),
        (size * 0.7, 0.012),
        (size * 0.5, 0.02),
        (size * 0.2, 0.025),
        (0.001, 0.028),
    ]
    mv, mf = _make_lathe(mound_profile, segments=8, close_bottom=True, close_top=True)
    parts.append((mv, mf))

    for _ in range(coin_count):
        cx = rng.uniform(-size * 0.6, size * 0.6)
        cz = rng.uniform(-size * 0.6, size * 0.6)
        dist = math.sqrt(cx * cx + cz * cz)
        if dist > size * 0.7:
            continue
        cy = 0.015 * (1.0 - dist / size) + rng.uniform(0, 0.008)
        coin_r = rng.uniform(0.008, 0.012)
        cv, cf = _make_cylinder(cx, cy, cz, coin_r, 0.002, segments=6)
        parts.append((cv, cf))

    verts, faces = _merge_meshes(*parts)
    return _make_result("GoldPile", verts, faces,
                        coin_count=coin_count, category="dungeon_prop")


def generate_lore_tablet_mesh(
    style: str = "stone",
) -> MeshSpec:
    """Generate a stone tablet with carved surface for lore text.

    Args:
        style: "stone", "clay", or "obsidian".

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    if style == "stone":
        w, h, d = 0.25, 0.35, 0.04
        bv, bf = _make_beveled_box(0, h / 2, 0, w / 2, h / 2, d / 2, bevel=0.008)
        parts.append((bv, bf))
        cap_segs = 6
        cap_r = w / 2
        for i in range(cap_segs):
            angle0 = i * math.pi / cap_segs
            angle1 = (i + 1) * math.pi / cap_segs
            x0 = math.cos(angle0) * cap_r
            y0 = h + math.sin(angle0) * cap_r * 0.3
            x1 = math.cos(angle1) * cap_r
            y1 = h + math.sin(angle1) * cap_r * 0.3
            cv, cf = _make_box((x0 + x1) / 2, (y0 + y1) / 2, 0,
                               abs(x1 - x0) / 2 + 0.001, abs(y1 - y0) / 2 + 0.001, d / 2)
            parts.append((cv, cf))
        for i in range(5):
            ly = h * 0.2 + i * h * 0.12
            lv, lf = _make_box(0, ly, d / 2 + 0.001,
                               w * 0.35, 0.003, 0.001)
            parts.append((lv, lf))

    elif style == "clay":
        w, h, d = 0.2, 0.15, 0.03
        bv, bf = _make_beveled_box(0, h / 2 + 0.01, 0,
                                   w / 2, h / 2, d / 2, bevel=0.01)
        parts.append((bv, bf))
        for row in range(3):
            for col in range(5):
                mx = -w * 0.3 + col * w * 0.15
                my = h * 0.25 + row * h * 0.22 + 0.01
                mv2, mf2 = _make_box(mx, my, d / 2 + 0.001,
                                     0.006, 0.004, 0.001)
                parts.append((mv2, mf2))

    else:  # obsidian
        w, h, d = 0.22, 0.3, 0.025
        bv, bf = _make_beveled_box(0, h / 2, 0, w / 2, h / 2, d / 2, bevel=0.005)
        parts.append((bv, bf))
        for i in range(3):
            ry = h * 0.25 + i * h * 0.2
            rv, rf = _make_torus_ring(0, ry, d / 2 + 0.001,
                                      w * 0.15, 0.003,
                                      major_segments=8, minor_segments=3)
            parts.append((rv, rf))

    stand_v, stand_f = _make_beveled_box(0, -0.015, 0,
                                         0.06, 0.015, 0.05, bevel=0.003)
    parts.append((stand_v, stand_f))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"LoreTablet_{style}", verts, faces,
                        style=style, category="dungeon_prop")


# =========================================================================
# CATEGORY: FOREST ANIMALS
# =========================================================================


def generate_deer_mesh(style: str = "adult") -> MeshSpec:
    """Generate a stylized deer mesh with antlers.

    Args:
        style: "adult" (full antlers) or "fawn" (no antlers, smaller).

    Returns:
        MeshSpec ~2-4K tris. Dark fantasy silhouette-readable deer.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_fawn = style == "fawn"
    sc = 0.7 if is_fawn else 1.0

    # Body - elongated barrel
    body_len = 0.9 * sc
    body_r = 0.18 * sc
    bv, bf = _make_tapered_cylinder(
        0, 0.55 * sc, 0, body_r * 0.9, body_r,
        body_len, segments=segs, rings=3, cap_top=True, cap_bottom=True,
    )
    # Rotate body to lie along Z axis
    bv_rot = [(v[0], 0.55 * sc + (v[2]) * 0.15, v[1] - 0.55 * sc + body_len * 0.1)
              for v in bv]
    parts.append((bv_rot, bf))

    # Torso sphere for volume
    tv, tf = _make_sphere(0, 0.6 * sc, 0, body_r * 1.05, rings=5, sectors=segs)
    parts.append((tv, tf))

    # Haunches (rear bulk)
    hv, hf = _make_sphere(0, 0.58 * sc, -body_len * 0.35, body_r * 0.95,
                           rings=5, sectors=segs)
    parts.append((hv, hf))

    # Neck - tapered cylinder angled forward/up
    neck_r = 0.08 * sc
    neck_h = 0.35 * sc
    nv, nf = _make_tapered_cylinder(
        0, 0.65 * sc, body_len * 0.35,
        neck_r * 1.3, neck_r, neck_h, segments=6, rings=2,
    )
    # Angle the neck forward
    nv_angled = [(v[0], v[1] + (v[1] - 0.65 * sc) * 0.3,
                  v[2] + (v[1] - 0.65 * sc) * 0.5) for v in nv]
    parts.append((nv_angled, nf))

    # Head
    head_y = 0.95 * sc
    head_z = body_len * 0.45
    head_r = 0.07 * sc
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout
    snout_r = 0.04 * sc
    sv, sf = _make_tapered_cylinder(
        0, head_y - 0.02 * sc, head_z + head_r * 0.8,
        snout_r * 1.1, snout_r * 0.6, 0.08 * sc, segments=6, rings=1,
    )
    sv_rot = [(v[0], v[1], v[2]) for v in sv]
    parts.append((sv_rot, sf))

    # Ears (two thin cones)
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.04 * sc, head_y + head_r * 0.6, head_z - 0.01 * sc,
            0.015 * sc, 0.06 * sc, segments=4,
        )
        parts.append((ev, ef))

    # Legs (4 legs: front-left, front-right, rear-left, rear-right)
    leg_positions = [
        (-0.09 * sc, body_len * 0.25),
        (0.09 * sc, body_len * 0.25),
        (-0.09 * sc, -body_len * 0.3),
        (0.09 * sc, -body_len * 0.3),
    ]
    for lx, lz in leg_positions:
        # Upper leg
        ulv, ulf = _make_tapered_cylinder(
            lx, 0.28 * sc, lz,
            0.035 * sc, 0.025 * sc, 0.28 * sc, segments=6, rings=2,
        )
        parts.append((ulv, ulf))
        # Lower leg (thinner)
        llv, llf = _make_tapered_cylinder(
            lx, 0, lz + 0.02 * sc,
            0.02 * sc, 0.015 * sc, 0.3 * sc, segments=6, rings=1,
        )
        parts.append((llv, llf))

    # Tail (short, upward)
    tlv, tlf = _make_tapered_cylinder(
        0, 0.6 * sc, -body_len * 0.42,
        0.02 * sc, 0.008 * sc, 0.1 * sc, segments=4, rings=1,
    )
    parts.append((tlv, tlf))

    # Antlers (only for adult)
    if not is_fawn:
        for side in [-1.0, 1.0]:
            ax = side * 0.03
            # Main beam
            abv, abf = _make_tapered_cylinder(
                ax, head_y + head_r * 0.5, head_z,
                0.012, 0.006, 0.25, segments=4, rings=3,
            )
            # Angle outward
            abv_a = [(v[0] + side * (v[1] - head_y - head_r * 0.5) * 0.4,
                       v[1], v[2] - (v[1] - head_y - head_r * 0.5) * 0.15) for v in abv]
            parts.append((abv_a, abf))
            # Tines (2 per side)
            for ti, th in enumerate([0.12, 0.2]):
                ty = head_y + head_r * 0.5 + th
                tx = ax + side * th * 0.4
                tv2, tf2 = _make_tapered_cylinder(
                    tx, ty, head_z - th * 0.15,
                    0.008, 0.003, 0.08, segments=4, rings=1,
                )
                tv2_a = [(v[0] + side * (v[1] - ty) * 0.3, v[1],
                          v[2] + (v[1] - ty) * 0.2) for v in tv2]
                parts.append((tv2_a, tf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Deer_{style}", verts, faces,
                        style=style, category="forest_animal")


def generate_wolf_mesh(style: str = "adult") -> MeshSpec:
    """Generate a stylized wolf/canine mesh.

    Args:
        style: "adult" (full size) or "pup" (smaller, rounder).

    Returns:
        MeshSpec ~2-4K tris. Dark fantasy wolf silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_pup = style == "pup"
    sc = 0.6 if is_pup else 1.0

    # Body barrel
    body_r = 0.16 * sc
    body_len = 0.7 * sc
    bv, bf = _make_sphere(0, 0.45 * sc, 0, body_r, rings=6, sectors=segs)
    parts.append((bv, bf))

    # Extended torso
    tv, tf = _make_tapered_cylinder(
        0, 0.35 * sc, -body_len * 0.2,
        body_r * 0.95, body_r * 0.85, body_len * 0.5,
        segments=segs, rings=2, cap_top=True, cap_bottom=True,
    )
    tv_rot = [(v[0], 0.45 * sc + (v[2] + body_len * 0.2) * 0.05,
               -body_len * 0.2 + (v[1] - 0.35 * sc)) for v in tv]
    parts.append((tv_rot, tf))

    # Chest (front bulk)
    cv, cf = _make_sphere(0, 0.48 * sc, body_len * 0.2, body_r * 0.9,
                           rings=5, sectors=segs)
    parts.append((cv, cf))

    # Neck
    neck_r = 0.08 * sc
    nv, nf = _make_tapered_cylinder(
        0, 0.48 * sc, body_len * 0.3,
        neck_r * 1.4, neck_r, 0.2 * sc, segments=6, rings=2,
    )
    parts.append((nv, nf))

    # Head - slightly elongated
    head_y = 0.55 * sc
    head_z = body_len * 0.42
    head_r = 0.07 * sc
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r * (1.3 if is_pup else 1.0),
                             rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout (longer than deer)
    snv, snf = _make_tapered_cylinder(
        0, head_y - 0.015 * sc, head_z + head_r,
        0.04 * sc, 0.02 * sc, 0.1 * sc, segments=6, rings=1,
    )
    parts.append((snv, snf))

    # Ears (pointed triangular, larger than deer)
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.035 * sc, head_y + head_r * 0.7, head_z - 0.01,
            0.018 * sc, 0.07 * sc, segments=4,
        )
        parts.append((ev, ef))

    # Legs
    leg_positions = [
        (-0.08 * sc, body_len * 0.15),
        (0.08 * sc, body_len * 0.15),
        (-0.08 * sc, -body_len * 0.25),
        (0.08 * sc, -body_len * 0.25),
    ]
    for lx, lz in leg_positions:
        ulv, ulf = _make_tapered_cylinder(
            lx, 0.22 * sc, lz, 0.03 * sc, 0.022 * sc,
            0.24 * sc, segments=6, rings=2,
        )
        parts.append((ulv, ulf))
        llv, llf = _make_tapered_cylinder(
            lx, 0, lz + 0.015 * sc, 0.018 * sc, 0.013 * sc,
            0.24 * sc, segments=6, rings=1,
        )
        parts.append((llv, llf))

    # Tail - bushy, curved down
    tail_segs = 6
    for i in range(tail_segs):
        t = i / tail_segs
        tr = (0.03 - t * 0.015) * sc
        ty = 0.45 * sc - t * 0.12 * sc
        tz = -body_len * 0.35 - t * 0.08 * sc
        tsv, tsf = _make_sphere(0, ty, tz, tr, rings=4, sectors=5)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Wolf_{style}", verts, faces,
                        style=style, category="forest_animal")


def generate_fox_mesh(style: str = "adult") -> MeshSpec:
    """Generate a stylized fox mesh (smaller canine).

    Args:
        style: "adult" or "kit" (smaller, proportionally larger head/ears).

    Returns:
        MeshSpec ~1-3K tris.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_kit = style == "kit"
    sc = 0.5 if is_kit else 0.75  # Fox is smaller than wolf

    # Body
    body_r = 0.12 * sc
    bv, bf = _make_sphere(0, 0.35 * sc, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Rear
    rv, rf = _make_sphere(0, 0.33 * sc, -0.15 * sc, body_r * 0.9, rings=5, sectors=segs)
    parts.append((rv, rf))

    # Chest
    cv, cf = _make_sphere(0, 0.37 * sc, 0.12 * sc, body_r * 0.85, rings=5, sectors=segs)
    parts.append((cv, cf))

    # Neck
    nv, nf = _make_tapered_cylinder(
        0, 0.38 * sc, 0.18 * sc,
        0.06 * sc, 0.045 * sc, 0.15 * sc, segments=6, rings=1,
    )
    parts.append((nv, nf))

    # Head - more pointed than wolf
    head_y = 0.48 * sc
    head_z = 0.28 * sc
    head_r = 0.055 * sc * (1.2 if is_kit else 1.0)
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Pointed snout
    snv, snf = _make_cone(
        0, head_y - 0.01 * sc, head_z + head_r * 0.9,
        0.025 * sc, 0.09 * sc, segments=6,
    )
    # Rotate cone to point forward (swap Y/Z)
    snv_rot = [(v[0], head_y - 0.01 * sc + (v[2] - head_z - head_r * 0.9) * 0.1,
                head_z + head_r * 0.9 + (v[1] - head_y + 0.01 * sc)) for v in snv]
    parts.append((snv_rot, snf))

    # Large pointed ears (fox hallmark)
    ear_scale = 1.3 if is_kit else 1.0
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.03 * sc, head_y + head_r * 0.8, head_z - 0.005,
            0.015 * sc * ear_scale, 0.08 * sc * ear_scale, segments=4,
        )
        parts.append((ev, ef))

    # Legs (slender)
    leg_positions = [
        (-0.06 * sc, 0.1 * sc),
        (0.06 * sc, 0.1 * sc),
        (-0.06 * sc, -0.13 * sc),
        (0.06 * sc, -0.13 * sc),
    ]
    for lx, lz in leg_positions:
        lv, lf = _make_tapered_cylinder(
            lx, 0, lz, 0.015 * sc, 0.01 * sc,
            0.35 * sc, segments=5, rings=2,
        )
        parts.append((lv, lf))

    # Bushy tail - fox's signature feature, larger and fluffier
    tail_segs = 8
    for i in range(tail_segs):
        t = i / tail_segs
        tr = (0.035 - t * 0.01) * sc * (1.0 - t * 0.3)
        ty = 0.32 * sc - t * 0.08 * sc
        tz = -0.22 * sc - t * 0.06 * sc
        tsv, tsf = _make_sphere(0, ty, tz, tr, rings=4, sectors=5)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Fox_{style}", verts, faces,
                        style=style, category="forest_animal")


def generate_rabbit_mesh(style: str = "sitting") -> MeshSpec:
    """Generate a stylized rabbit mesh in sitting pose.

    Args:
        style: "sitting" (upright) or "alert" (ears fully up, slightly taller).

    Returns:
        MeshSpec ~500-1K tris. Compact silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6
    is_alert = style == "alert"

    # Body (round, sitting)
    body_r = 0.06
    bv, bf = _make_sphere(0, 0.08, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Haunches (larger sphere behind)
    hv, hf = _make_sphere(0, 0.065, -0.04, body_r * 1.1, rings=5, sectors=segs)
    parts.append((hv, hf))

    # Head
    head_r = 0.04
    head_y = 0.16
    hdv, hdf = _make_sphere(0, head_y, 0.03, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout (tiny bump)
    snv, snf = _make_sphere(0, head_y - 0.005, 0.03 + head_r * 0.9,
                             0.015, rings=3, sectors=5)
    parts.append((snv, snf))

    # Ears (long, the most distinctive feature)
    ear_h = 0.1 if is_alert else 0.08
    for side in [-1.0, 1.0]:
        # Ear as thin tapered cylinder
        ev, ef = _make_tapered_cylinder(
            side * 0.015, head_y + head_r * 0.6, 0.025,
            0.01, 0.005, ear_h, segments=4, rings=2,
        )
        # Slight outward lean
        ev_lean = [(v[0] + side * (v[1] - head_y - head_r * 0.6) * 0.15,
                    v[1], v[2]) for v in ev]
        parts.append((ev_lean, ef))

    # Front paws (tiny)
    for side in [-1.0, 1.0]:
        pv, pf = _make_sphere(side * 0.025, 0.02, 0.04,
                               0.012, rings=3, sectors=4)
        parts.append((pv, pf))

    # Hind legs (folded, sitting)
    for side in [-1.0, 1.0]:
        hlv, hlf = _make_sphere(side * 0.04, 0.04, -0.03,
                                 0.025, rings=4, sectors=5)
        parts.append((hlv, hlf))
        # Hind foot
        fv, ff = _make_tapered_cylinder(
            side * 0.04, 0, -0.01,
            0.012, 0.008, 0.015, segments=4, rings=1,
        )
        parts.append((fv, ff))

    # Tail (cotton ball)
    tlv, tlf = _make_sphere(0, 0.08, -0.07, 0.018, rings=3, sectors=5)
    parts.append((tlv, tlf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Rabbit_{style}", verts, faces,
                        style=style, category="forest_animal")


def generate_owl_mesh(style: str = "perched") -> MeshSpec:
    """Generate a stylized owl mesh in perched pose.

    Args:
        style: "perched" (sitting upright) or "spread" (wings partially open).

    Returns:
        MeshSpec ~800-1.5K tris. Rounded silhouette with distinctive face disc.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Body (round barrel shape, upright)
    body_r = 0.06
    bv, bf = _make_sphere(0, 0.1, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Breast
    brv, brf = _make_sphere(0, 0.08, 0.02, body_r * 0.9, rings=4, sectors=segs)
    parts.append((brv, brf))

    # Head (large, round -- owls have big heads)
    head_r = 0.045
    head_y = 0.19
    hdv, hdf = _make_sphere(0, head_y, 0.01, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Facial disc (flat-ish sphere in front of face)
    fdv, fdf = _make_sphere(0, head_y, 0.01 + head_r * 0.7,
                             head_r * 0.8, rings=4, sectors=segs)
    parts.append((fdv, fdf))

    # Eye tufts / horn-like ear tufts
    for side in [-1.0, 1.0]:
        tv, tf = _make_cone(
            side * 0.025, head_y + head_r * 0.7, 0.005,
            0.008, 0.03, segments=4,
        )
        parts.append((tv, tf))

    # Beak
    bkv, bkf = _make_cone(
        0, head_y - 0.01, 0.01 + head_r * 1.1,
        0.008, 0.02, segments=4,
    )
    # Point forward
    bkv_rot = [(v[0], head_y - 0.01 + (v[2] - 0.01 - head_r * 1.1) * 0.1,
                0.01 + head_r * 1.1 + (v[1] - head_y + 0.01)) for v in bkv]
    parts.append((bkv_rot, bkf))

    # Wings (folded along body)
    for side in [-1.0, 1.0]:
        wv, wf = _make_tapered_cylinder(
            side * 0.055, 0.06, -0.01,
            0.025, 0.015, 0.1, segments=5, rings=2,
        )
        parts.append((wv, wf))

    if style == "spread":
        # Extended wing tips
        for side in [-1.0, 1.0]:
            ewv, ewf = _make_tapered_cylinder(
                side * 0.09, 0.1, -0.01,
                0.02, 0.008, 0.08, segments=4, rings=1,
            )
            # Angle outward
            ewv_a = [(v[0] + side * (v[1] - 0.1) * 0.5, v[1], v[2]) for v in ewv]
            parts.append((ewv_a, ewf))

    # Talons (perching feet)
    for side in [-1.0, 1.0]:
        fv, ff = _make_sphere(side * 0.02, 0.01, 0.01, 0.012, rings=3, sectors=4)
        parts.append((fv, ff))
        # Toes (3 forward toes)
        for ti in range(3):
            angle = (ti - 1) * 0.4 + side * 0.1
            tv, tf = _make_tapered_cylinder(
                side * 0.02 + math.sin(angle) * 0.008, 0,
                0.01 + math.cos(angle) * 0.008,
                0.004, 0.002, 0.015, segments=3, rings=1,
            )
            parts.append((tv, tf))

    # Tail feathers
    tlv, tlf = _make_box(0, 0.04, -0.06, 0.02, 0.008, 0.025)
    parts.append((tlv, tlf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Owl_{style}", verts, faces,
                        style=style, category="forest_animal")


def generate_crow_mesh(style: str = "perched") -> MeshSpec:
    """Generate a stylized crow/raven mesh.

    Args:
        style: "perched" (sitting) or "flying" (wings spread).

    Returns:
        MeshSpec ~500-1K tris. Sleek dark silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6

    # Body (sleek, elongated)
    body_rx = 0.03
    body_ry = 0.035
    bv, bf = _make_sphere(0, 0.08, 0, body_ry, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Head (small, round)
    head_r = 0.022
    head_y = 0.13
    head_z = 0.04
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=4, sectors=segs)
    parts.append((hdv, hdf))

    # Beak (long, pointed -- crow signature)
    bkv, bkf = _make_cone(
        0, head_y - 0.003, head_z + head_r,
        0.006, 0.035, segments=4,
    )
    bkv_rot = [(v[0], head_y - 0.003 + (v[2] - head_z - head_r) * 0.05,
                head_z + head_r + (v[1] - head_y + 0.003)) for v in bkv]
    parts.append((bkv_rot, bkf))

    # Neck
    nv, nf = _make_tapered_cylinder(
        0, 0.1, 0.03, 0.018, 0.015, 0.04, segments=5, rings=1,
    )
    parts.append((nv, nf))

    if style == "flying":
        # Wings spread wide
        for side in [-1.0, 1.0]:
            # Inner wing
            iwv, iwf = _make_box(side * 0.06, 0.085, -0.01,
                                  0.04, 0.003, 0.025)
            parts.append((iwv, iwf))
            # Outer wing
            owv, owf = _make_box(side * 0.12, 0.09, -0.015,
                                  0.035, 0.002, 0.02)
            parts.append((owv, owf))
    else:
        # Wings folded
        for side in [-1.0, 1.0]:
            wv, wf = _make_tapered_cylinder(
                side * 0.03, 0.06, -0.01,
                0.015, 0.008, 0.06, segments=4, rings=1,
            )
            parts.append((wv, wf))

    # Tail feathers (fan shape)
    tfv, tff = _make_box(0, 0.06, -0.06, 0.015, 0.003, 0.025)
    parts.append((tfv, tff))

    # Legs and feet
    for side in [-1.0, 1.0]:
        lv, lf = _make_tapered_cylinder(
            side * 0.015, 0, 0.005,
            0.004, 0.003, 0.08, segments=4, rings=1,
        )
        parts.append((lv, lf))
        # Toes
        for ti in range(3):
            angle = (ti - 1) * 0.5
            tv, tf = _make_tapered_cylinder(
                side * 0.015 + math.sin(angle) * 0.005, 0,
                0.005 + math.cos(angle) * 0.005,
                0.003, 0.001, 0.012, segments=3, rings=1,
            )
            parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Crow_{style}", verts, faces,
                        style=style, category="forest_animal")


# =========================================================================
# CATEGORY: MOUNTAIN ANIMALS
# =========================================================================


def generate_mountain_goat_mesh(style: str = "standing") -> MeshSpec:
    """Generate a stylized mountain goat mesh with horns.

    Args:
        style: "standing" or "climbing" (front legs higher).

    Returns:
        MeshSpec ~1.5-3K tris. Stocky, sure-footed silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_climbing = style == "climbing"

    # Body (stocky barrel)
    body_r = 0.13
    bv, bf = _make_sphere(0, 0.38, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Rear
    rv, rf = _make_sphere(0, 0.36, -0.12, body_r * 0.95, rings=5, sectors=segs)
    parts.append((rv, rf))

    # Chest (deep)
    cv, cf = _make_sphere(0, 0.4, 0.1, body_r * 0.9, rings=5, sectors=segs)
    parts.append((cv, cf))

    # Neck (thick, short)
    nv, nf = _make_tapered_cylinder(
        0, 0.42, 0.16, 0.065, 0.05, 0.15, segments=6, rings=1,
    )
    parts.append((nv, nf))

    # Head
    head_y = 0.52
    head_z = 0.22
    head_r = 0.05
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout
    snv, snf = _make_tapered_cylinder(
        0, head_y - 0.01, head_z + head_r * 0.8,
        0.03, 0.02, 0.05, segments=5, rings=1,
    )
    parts.append((snv, snf))

    # Horns (curved backward)
    for side in [-1.0, 1.0]:
        horn_segs = 5
        for hi in range(horn_segs):
            t = hi / horn_segs
            hr = 0.01 - t * 0.005
            hy = head_y + head_r * 0.5 + t * 0.1
            hz = head_z - t * 0.06
            hx = side * (0.025 + t * 0.015)
            hsv, hsf = _make_sphere(hx, hy, hz, hr, rings=3, sectors=4)
            parts.append((hsv, hsf))

    # Ears
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.035, head_y + head_r * 0.3, head_z - 0.01,
            0.01, 0.03, segments=4,
        )
        ev_a = [(v[0] + side * (v[1] - head_y - head_r * 0.3) * 0.3,
                 v[1], v[2]) for v in ev]
        parts.append((ev_a, ef))

    # Legs (sturdy, shorter)
    front_y_offset = 0.03 if is_climbing else 0
    leg_positions = [
        (-0.07, 0.14, front_y_offset),
        (0.07, 0.14, front_y_offset),
        (-0.07, -0.1, 0),
        (0.07, -0.1, 0),
    ]
    for lx, lz, ly_off in leg_positions:
        ulv, ulf = _make_tapered_cylinder(
            lx, 0.18 + ly_off, lz,
            0.028, 0.02, 0.2, segments=6, rings=2,
        )
        parts.append((ulv, ulf))
        llv, llf = _make_tapered_cylinder(
            lx, ly_off, lz + 0.01,
            0.016, 0.013, 0.2, segments=5, rings=1,
        )
        parts.append((llv, llf))

    # Tail (short)
    tlv, tlf = _make_tapered_cylinder(
        0, 0.38, -0.17, 0.012, 0.005, 0.05, segments=4, rings=1,
    )
    parts.append((tlv, tlf))

    # Beard (goat signature)
    bdv, bdf = _make_cone(
        0, head_y - head_r * 0.8, head_z + 0.01,
        0.008, 0.04, segments=4,
    )
    bdv_a = [(v[0], v[1], v[2]) for v in bdv]
    parts.append((bdv_a, bdf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MountainGoat_{style}", verts, faces,
                        style=style, category="mountain_animal")


def generate_eagle_mesh(style: str = "perched") -> MeshSpec:
    """Generate a stylized eagle mesh (large bird of prey).

    Args:
        style: "perched" or "soaring" (wings fully spread).

    Returns:
        MeshSpec ~1-2K tris. Imposing raptor silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8

    # Body (larger than crow, more muscular)
    body_r = 0.06
    bv, bf = _make_sphere(0, 0.12, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Breast (prominent)
    brv, brf = _make_sphere(0, 0.11, 0.03, body_r * 0.9, rings=4, sectors=segs)
    parts.append((brv, brf))

    # Head
    head_r = 0.03
    head_y = 0.2
    head_z = 0.05
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Brow ridge (fierce look)
    brow_v, brow_f = _make_box(0, head_y + head_r * 0.3,
                                head_z + head_r * 0.5, 0.025, 0.005, 0.008)
    parts.append((brow_v, brow_f))

    # Hooked beak (raptor signature)
    bkv, bkf = _make_cone(
        0, head_y - 0.005, head_z + head_r * 0.9,
        0.01, 0.04, segments=5,
    )
    bkv_rot = [(v[0], head_y - 0.005 + (v[2] - head_z - head_r * 0.9) * 0.15,
                head_z + head_r * 0.9 + (v[1] - head_y + 0.005) * 0.8) for v in bkv]
    parts.append((bkv_rot, bkf))

    # Neck
    nv, nf = _make_tapered_cylinder(
        0, 0.14, 0.035, 0.025, 0.02, 0.06, segments=6, rings=1,
    )
    parts.append((nv, nf))

    if style == "soaring":
        # Wide wingspan
        for side in [-1.0, 1.0]:
            # Inner wing
            iwv, iwf = _make_box(side * 0.1, 0.13, -0.01, 0.06, 0.004, 0.035)
            parts.append((iwv, iwf))
            # Middle wing
            mwv, mwf = _make_box(side * 0.2, 0.135, -0.015, 0.05, 0.003, 0.03)
            parts.append((mwv, mwf))
            # Outer wing (tapered)
            owv, owf = _make_box(side * 0.28, 0.14, -0.02, 0.035, 0.002, 0.02)
            parts.append((owv, owf))
    else:
        # Folded wings
        for side in [-1.0, 1.0]:
            wv, wf = _make_tapered_cylinder(
                side * 0.05, 0.08, -0.02,
                0.025, 0.012, 0.1, segments=5, rings=2,
            )
            parts.append((wv, wf))

    # Tail feathers (wider, fan-shaped)
    tfv, tff = _make_box(0, 0.08, -0.09, 0.025, 0.004, 0.03)
    parts.append((tfv, tff))

    # Talons (powerful)
    for side in [-1.0, 1.0]:
        # Leg
        lv, lf = _make_tapered_cylinder(
            side * 0.025, 0, 0.01,
            0.008, 0.006, 0.12, segments=5, rings=1,
        )
        parts.append((lv, lf))
        # Talon toes
        for ti in range(3):
            angle = (ti - 1) * 0.5 + side * 0.1
            tv, tf = _make_cone(
                side * 0.025 + math.sin(angle) * 0.01, 0,
                0.01 + math.cos(angle) * 0.01,
                0.004, 0.02, segments=3,
            )
            tv_rot = [(v[0], (v[2] - 0.01 - math.cos(angle) * 0.01) * 0.3,
                        0.01 + math.cos(angle) * 0.01 + (v[1]) * 0.5) for v in tv]
            parts.append((tv_rot, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Eagle_{style}", verts, faces,
                        style=style, category="mountain_animal")


def generate_bear_mesh(style: str = "standing") -> MeshSpec:
    """Generate a stylized bear mesh (large quadruped).

    Args:
        style: "standing" (on all fours) or "rearing" (on hind legs).

    Returns:
        MeshSpec ~3-5K tris. Massive, hulking silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10
    is_rearing = style == "rearing"

    # Body (massive barrel)
    body_r = 0.25
    if is_rearing:
        body_y = 0.6
        bv, bf = _make_sphere(0, body_y, 0, body_r, rings=6, sectors=segs)
    else:
        body_y = 0.45
        bv, bf = _make_sphere(0, body_y, 0, body_r, rings=6, sectors=segs)
    parts.append((bv, bf))

    # Rear bulk
    rear_z = -0.2
    rv, rf = _make_sphere(0, body_y - 0.03, rear_z, body_r * 0.95,
                           rings=5, sectors=segs)
    parts.append((rv, rf))

    # Shoulder hump (bear signature)
    shv, shf = _make_sphere(0, body_y + 0.08, 0.1, body_r * 0.7,
                             rings=5, sectors=segs)
    parts.append((shv, shf))

    # Neck (thick)
    neck_y = body_y + 0.05
    neck_z = 0.2
    nv, nf = _make_tapered_cylinder(
        0, neck_y - 0.05, neck_z, 0.12, 0.09, 0.2,
        segments=segs, rings=2,
    )
    parts.append((nv, nf))

    # Head (broad, flat)
    head_y = body_y + 0.1 if is_rearing else body_y + 0.02
    head_z = 0.35 if not is_rearing else 0.25
    head_r = 0.09
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout (elongated)
    snv, snf = _make_tapered_cylinder(
        0, head_y - 0.02, head_z + head_r * 0.8,
        0.05, 0.03, 0.08, segments=6, rings=1,
    )
    parts.append((snv, snf))

    # Nose tip
    nosev, nosef = _make_sphere(0, head_y - 0.015, head_z + head_r * 0.8 + 0.08,
                                 0.015, rings=3, sectors=5)
    parts.append((nosev, nosef))

    # Ears (small, round)
    for side in [-1.0, 1.0]:
        ev, ef = _make_sphere(side * 0.06, head_y + head_r * 0.7, head_z - 0.01,
                               0.018, rings=3, sectors=4)
        parts.append((ev, ef))

    if is_rearing:
        # Hind legs (weight-bearing, thick)
        for side in [-1.0, 1.0]:
            ulv, ulf = _make_tapered_cylinder(
                side * 0.12, 0.25, -0.1,
                0.06, 0.05, 0.35, segments=segs, rings=3,
            )
            parts.append((ulv, ulf))
            llv, llf = _make_tapered_cylinder(
                side * 0.12, 0, -0.08,
                0.05, 0.06, 0.27, segments=segs, rings=2,
            )
            parts.append((llv, llf))
        # Front legs (raised)
        for side in [-1.0, 1.0]:
            ulv, ulf = _make_tapered_cylinder(
                side * 0.15, body_y + 0.05, 0.15,
                0.05, 0.04, 0.2, segments=8, rings=2,
            )
            ulv_a = [(v[0] + side * (v[1] - body_y - 0.05) * 0.15,
                      v[1], v[2] + (v[1] - body_y - 0.05) * 0.3) for v in ulv]
            parts.append((ulv_a, ulf))
            # Paw
            pv, pf = _make_sphere(side * 0.18, body_y + 0.22, 0.2,
                                   0.04, rings=4, sectors=6)
            parts.append((pv, pf))
    else:
        # All four legs (thick, powerful)
        leg_positions = [
            (-0.12, 0.15),
            (0.12, 0.15),
            (-0.12, -0.18),
            (0.12, -0.18),
        ]
        for lx, lz in leg_positions:
            ulv, ulf = _make_tapered_cylinder(
                lx, 0.2, lz, 0.05, 0.04,
                0.27, segments=8, rings=2,
            )
            parts.append((ulv, ulf))
            llv, llf = _make_tapered_cylinder(
                lx, 0, lz + 0.02, 0.04, 0.045,
                0.22, segments=8, rings=1,
            )
            parts.append((llv, llf))
            # Paw
            pv, pf = _make_sphere(lx, 0.02, lz + 0.02,
                                   0.035, rings=3, sectors=5)
            parts.append((pv, pf))

    # Tail (short stub)
    tail_y = body_y - 0.05
    tail_z = rear_z - 0.15
    tlv, tlf = _make_sphere(0, tail_y, tail_z, 0.025, rings=3, sectors=5)
    parts.append((tlv, tlf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bear_{style}", verts, faces,
                        style=style, category="mountain_animal")


# =========================================================================
# CATEGORY: DOMESTIC ANIMALS
# =========================================================================


def generate_horse_mesh(style: str = "standing") -> MeshSpec:
    """Generate a stylized horse mesh.

    Args:
        style: "standing" or "galloping" (legs extended).

    Returns:
        MeshSpec ~3-5K tris. Elegant, muscular silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 10

    # Body (long, muscular barrel)
    body_r = 0.2
    body_len = 0.9
    bv, bf = _make_sphere(0, 0.7, 0, body_r, rings=6, sectors=segs)
    parts.append((bv, bf))

    # Rear
    rv, rf = _make_sphere(0, 0.68, -body_len * 0.3, body_r * 0.95,
                           rings=5, sectors=segs)
    parts.append((rv, rf))

    # Chest
    cv, cf = _make_sphere(0, 0.72, body_len * 0.25, body_r * 0.9,
                           rings=5, sectors=segs)
    parts.append((cv, cf))

    # Neck (long, arched)
    neck_base_y = 0.75
    neck_base_z = body_len * 0.35
    nv, nf = _make_tapered_cylinder(
        0, neck_base_y, neck_base_z,
        0.09, 0.06, 0.4, segments=8, rings=3,
    )
    # Angle neck upward
    nv_angled = [(v[0], v[1] + (v[1] - neck_base_y) * 0.5,
                  v[2] + (v[1] - neck_base_y) * 0.4) for v in nv]
    parts.append((nv_angled, nf))

    # Head (long, refined)
    head_y = 1.1
    head_z = body_len * 0.5
    head_r = 0.06
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Long snout/muzzle
    snv, snf = _make_tapered_cylinder(
        0, head_y - 0.02, head_z + head_r * 0.8,
        0.04, 0.03, 0.12, segments=6, rings=2,
    )
    parts.append((snv, snf))

    # Nostrils (small spheres)
    for side in [-1.0, 1.0]:
        nsv, nsf = _make_sphere(side * 0.02, head_y - 0.03, head_z + head_r + 0.1,
                                 0.008, rings=3, sectors=4)
        parts.append((nsv, nsf))

    # Ears (small, pointed)
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.03, head_y + head_r * 0.7, head_z - 0.01,
            0.01, 0.05, segments=4,
        )
        parts.append((ev, ef))

    # Mane (along neck - series of thin boxes)
    for i in range(6):
        t = i / 5
        my = neck_base_y + t * (head_y - neck_base_y) * 0.8
        mz = neck_base_z + t * (head_z - neck_base_z) * 0.8
        mv, mf = _make_box(0, my + 0.03, mz, 0.003, 0.025, 0.015)
        parts.append((mv, mf))

    is_galloping = style == "galloping"

    # Legs (long, slender)
    if is_galloping:
        leg_configs = [
            (-0.09, body_len * 0.2, 0.06, -0.03),   # FL forward
            (0.09, body_len * 0.2, -0.02, 0.02),     # FR mid
            (-0.09, -body_len * 0.25, -0.03, 0.06),  # RL back
            (0.09, -body_len * 0.25, 0.04, -0.02),   # RR mid
        ]
    else:
        leg_configs = [
            (-0.09, body_len * 0.2, 0, 0),
            (0.09, body_len * 0.2, 0, 0),
            (-0.09, -body_len * 0.25, 0, 0),
            (0.09, -body_len * 0.25, 0, 0),
        ]
    for lx, lz, z_upper_off, z_lower_off in leg_configs:
        # Upper leg
        ulv, ulf = _make_tapered_cylinder(
            lx, 0.35, lz + z_upper_off,
            0.04, 0.03, 0.36, segments=8, rings=2,
        )
        parts.append((ulv, ulf))
        # Lower leg
        llv, llf = _make_tapered_cylinder(
            lx, 0, lz + z_lower_off,
            0.025, 0.02, 0.37, segments=6, rings=2,
        )
        parts.append((llv, llf))
        # Hoof
        hfv, hff = _make_cylinder(
            lx, 0, lz + z_lower_off,
            0.025, 0.03, segments=6,
        )
        parts.append((hfv, hff))

    # Tail (long, flowing)
    tail_segs = 8
    for i in range(tail_segs):
        t = i / tail_segs
        tr = 0.015 - t * 0.005
        ty = 0.65 - t * 0.2
        tz = -body_len * 0.4 - t * 0.1
        tsv, tsf = _make_sphere(0, ty, tz, tr, rings=3, sectors=4)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Horse_{style}", verts, faces,
                        style=style, category="domestic_animal")


def generate_chicken_mesh(style: str = "standing") -> MeshSpec:
    """Generate a stylized chicken mesh.

    Args:
        style: "standing" or "pecking" (head lowered).

    Returns:
        MeshSpec ~500-800 tris. Plump barnyard bird.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6

    # Body (plump, round)
    body_r = 0.05
    bv, bf = _make_sphere(0, 0.1, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Breast
    brv, brf = _make_sphere(0, 0.09, 0.025, body_r * 0.85, rings=4, sectors=segs)
    parts.append((brv, brf))

    # Head
    head_y = 0.17 if style != "pecking" else 0.12
    head_z = 0.04 if style != "pecking" else 0.08
    head_r = 0.022
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=4, sectors=segs)
    parts.append((hdv, hdf))

    # Beak (short, pointed)
    bkv, bkf = _make_cone(
        0, head_y - 0.005, head_z + head_r * 0.9,
        0.006, 0.015, segments=4,
    )
    bkv_rot = [(v[0], head_y - 0.005 + (v[2] - head_z - head_r * 0.9) * 0.1,
                head_z + head_r * 0.9 + (v[1] - head_y + 0.005)) for v in bkv]
    parts.append((bkv_rot, bkf))

    # Comb (on top of head)
    cmv, cmf = _make_box(0, head_y + head_r * 0.7, head_z + 0.005,
                          0.003, 0.01, 0.008)
    parts.append((cmv, cmf))

    # Wattle (below beak)
    wv, wf = _make_sphere(0, head_y - head_r * 0.7, head_z + head_r * 0.5,
                           0.006, rings=3, sectors=4)
    parts.append((wv, wf))

    # Neck
    nv, nf = _make_tapered_cylinder(
        0, 0.12, 0.03, 0.018, 0.015, 0.05, segments=5, rings=1,
    )
    parts.append((nv, nf))

    # Wings (folded)
    for side in [-1.0, 1.0]:
        wgv, wgf = _make_tapered_cylinder(
            side * 0.04, 0.08, -0.01,
            0.015, 0.008, 0.05, segments=4, rings=1,
        )
        parts.append((wgv, wgf))

    # Tail feathers (upward fan)
    for i in range(3):
        angle = (i - 1) * 0.3
        tfv, tff = _make_box(
            math.sin(angle) * 0.008, 0.12 + i * 0.01, -0.06 - i * 0.005,
            0.003, 0.015, 0.008,
        )
        parts.append((tfv, tff))

    # Legs
    for side in [-1.0, 1.0]:
        lv, lf = _make_tapered_cylinder(
            side * 0.02, 0, 0.005,
            0.005, 0.004, 0.1, segments=4, rings=1,
        )
        parts.append((lv, lf))
        # Toes (3 forward, 1 back)
        for ti in range(3):
            ta = (ti - 1) * 0.4
            tv, tf = _make_tapered_cylinder(
                side * 0.02 + math.sin(ta) * 0.006, 0,
                0.005 + math.cos(ta) * 0.006,
                0.003, 0.001, 0.012, segments=3, rings=1,
            )
            parts.append((tv, tf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Chicken_{style}", verts, faces,
                        style=style, category="domestic_animal")


def generate_dog_mesh(style: str = "sitting") -> MeshSpec:
    """Generate a stylized medium dog mesh.

    Args:
        style: "sitting" or "standing".

    Returns:
        MeshSpec ~1.5-3K tris. Loyal companion silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_sitting = style == "sitting"

    # Body
    body_r = 0.1
    body_y = 0.3 if not is_sitting else 0.2
    bv, bf = _make_sphere(0, body_y, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Chest
    cv, cf = _make_sphere(0, body_y + 0.02, 0.08, body_r * 0.85,
                           rings=5, sectors=segs)
    parts.append((cv, cf))

    # Haunches
    hv, hf = _make_sphere(0, body_y - 0.02, -0.1, body_r * 0.9,
                           rings=5, sectors=segs)
    parts.append((hv, hf))

    # Neck
    nv, nf = _make_tapered_cylinder(
        0, body_y + 0.03, 0.12,
        0.05, 0.04, 0.12, segments=6, rings=1,
    )
    parts.append((nv, nf))

    # Head
    head_y = body_y + 0.12
    head_z = 0.18
    head_r = 0.05
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout
    snv, snf = _make_tapered_cylinder(
        0, head_y - 0.01, head_z + head_r * 0.8,
        0.03, 0.018, 0.06, segments=5, rings=1,
    )
    parts.append((snv, snf))

    # Nose
    nosev, nosef = _make_sphere(0, head_y - 0.005, head_z + head_r + 0.05,
                                 0.01, rings=3, sectors=4)
    parts.append((nosev, nosef))

    # Ears (floppy)
    for side in [-1.0, 1.0]:
        ev, ef = _make_tapered_cylinder(
            side * 0.035, head_y + head_r * 0.3, head_z - 0.01,
            0.015, 0.01, 0.05, segments=4, rings=1,
        )
        # Flop downward
        ev_a = [(v[0] + side * (v[1] - head_y - head_r * 0.3) * 0.4,
                 v[1] - abs(v[1] - head_y - head_r * 0.3) * 0.3, v[2]) for v in ev]
        parts.append((ev_a, ef))

    if is_sitting:
        # Front legs straight
        for side in [-1.0, 1.0]:
            flv, flf = _make_tapered_cylinder(
                side * 0.06, 0, 0.08,
                0.02, 0.015, 0.2, segments=6, rings=2,
            )
            parts.append((flv, flf))
        # Hind legs folded
        for side in [-1.0, 1.0]:
            hlv, hlf = _make_sphere(side * 0.07, 0.1, -0.08,
                                     0.04, rings=4, sectors=6)
            parts.append((hlv, hlf))
            hfv, hff = _make_tapered_cylinder(
                side * 0.07, 0, -0.04,
                0.015, 0.012, 0.05, segments=5, rings=1,
            )
            parts.append((hfv, hff))
    else:
        # All four legs standing
        leg_positions = [
            (-0.06, 0.08),
            (0.06, 0.08),
            (-0.06, -0.1),
            (0.06, -0.1),
        ]
        for lx, lz in leg_positions:
            ulv, ulf = _make_tapered_cylinder(
                lx, 0.14, lz, 0.025, 0.018,
                0.17, segments=6, rings=2,
            )
            parts.append((ulv, ulf))
            llv, llf = _make_tapered_cylinder(
                lx, 0, lz + 0.01, 0.015, 0.012,
                0.16, segments=5, rings=1,
            )
            parts.append((llv, llf))

    # Tail (curved upward)
    tail_segs = 5
    for i in range(tail_segs):
        t = i / tail_segs
        tr = 0.012 - t * 0.005
        ty = body_y - 0.02 + t * 0.06
        tz = -0.15 - t * 0.04
        tsv, tsf = _make_sphere(0, ty, tz, tr, rings=3, sectors=4)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Dog_{style}", verts, faces,
                        style=style, category="domestic_animal")


def generate_cat_mesh(style: str = "sitting") -> MeshSpec:
    """Generate a stylized cat mesh.

    Args:
        style: "sitting" (upright) or "walking".

    Returns:
        MeshSpec ~1-2K tris. Sleek feline silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_sitting = style == "sitting"

    # Body (sleek, smaller than dog)
    body_r = 0.06
    body_y = 0.15 if is_sitting else 0.2
    bv, bf = _make_sphere(0, body_y, 0, body_r, rings=5, sectors=segs)
    parts.append((bv, bf))

    # Chest
    cv, cf = _make_sphere(0, body_y + 0.01, 0.05, body_r * 0.8,
                           rings=4, sectors=segs)
    parts.append((cv, cf))

    # Haunches
    hv, hf = _make_sphere(0, body_y - 0.01, -0.06, body_r * 0.9,
                           rings=4, sectors=segs)
    parts.append((hv, hf))

    # Neck (slender)
    nv, nf = _make_tapered_cylinder(
        0, body_y + 0.03, 0.07,
        0.03, 0.025, 0.08, segments=6, rings=1,
    )
    parts.append((nv, nf))

    # Head (round, proportionally large)
    head_y = body_y + 0.1
    head_z = 0.1
    head_r = 0.04
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=5, sectors=segs)
    parts.append((hdv, hdf))

    # Snout (small, delicate)
    snv, snf = _make_sphere(0, head_y - 0.01, head_z + head_r * 0.85,
                             0.015, rings=3, sectors=5)
    parts.append((snv, snf))

    # Ears (large, triangular -- cat signature)
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.025, head_y + head_r * 0.8, head_z - 0.005,
            0.012, 0.04, segments=4,
        )
        parts.append((ev, ef))

    if is_sitting:
        # Front paws
        for side in [-1.0, 1.0]:
            fpv, fpf = _make_tapered_cylinder(
                side * 0.035, 0, 0.04,
                0.012, 0.01, 0.15, segments=5, rings=1,
            )
            parts.append((fpv, fpf))
        # Hind legs tucked
        for side in [-1.0, 1.0]:
            hlv, hlf = _make_sphere(side * 0.04, 0.07, -0.04,
                                     0.025, rings=4, sectors=5)
            parts.append((hlv, hlf))
    else:
        # Four legs standing
        leg_positions = [
            (-0.035, 0.04),
            (0.035, 0.04),
            (-0.035, -0.05),
            (0.035, -0.05),
        ]
        for lx, lz in leg_positions:
            lv, lf = _make_tapered_cylinder(
                lx, 0, lz, 0.012, 0.008,
                0.2, segments=5, rings=2,
            )
            parts.append((lv, lf))

    # Tail (long, curved, elegant)
    tail_segs = 8
    for i in range(tail_segs):
        t = i / tail_segs
        tr = 0.008 - t * 0.003
        ty = body_y - 0.02 + t * 0.05 + math.sin(t * math.pi) * 0.03
        tz = -0.09 - t * 0.06
        tx = math.sin(t * math.pi * 0.5) * 0.02
        tsv, tsf = _make_sphere(tx, ty, tz, tr, rings=3, sectors=4)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Cat_{style}", verts, faces,
                        style=style, category="domestic_animal")


# =========================================================================
# CATEGORY: VERMIN
# =========================================================================


def generate_rat_mesh(style: str = "standing") -> MeshSpec:
    """Generate a stylized rat mesh (tiny quadruped).

    Args:
        style: "standing" or "crouching".

    Returns:
        MeshSpec ~300-600 tris. Small, hunched rodent.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6

    # Body (hunched, elongated)
    body_r = 0.025
    body_y = 0.035
    bv, bf = _make_sphere(0, body_y, 0, body_r, rings=4, sectors=segs)
    parts.append((bv, bf))

    # Rear (slightly larger)
    rv, rf = _make_sphere(0, body_y - 0.003, -0.025, body_r * 1.05,
                           rings=4, sectors=segs)
    parts.append((rv, rf))

    # Head (pointed)
    head_y = body_y + 0.01 if style != "crouching" else body_y
    head_z = 0.03
    head_r = 0.018
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=4, sectors=segs)
    parts.append((hdv, hdf))

    # Snout (very pointed)
    snv, snf = _make_cone(
        0, head_y - 0.003, head_z + head_r * 0.9,
        0.008, 0.02, segments=4,
    )
    snv_rot = [(v[0], head_y - 0.003 + (v[2] - head_z - head_r * 0.9) * 0.05,
                head_z + head_r * 0.9 + (v[1] - head_y + 0.003)) for v in snv]
    parts.append((snv_rot, snf))

    # Ears (round, relatively large)
    for side in [-1.0, 1.0]:
        ev, ef = _make_sphere(side * 0.012, head_y + head_r * 0.6, head_z - 0.003,
                               0.008, rings=3, sectors=4)
        parts.append((ev, ef))

    # Legs (tiny)
    leg_positions = [
        (-0.015, 0.015),
        (0.015, 0.015),
        (-0.015, -0.02),
        (0.015, -0.02),
    ]
    for lx, lz in leg_positions:
        lv, lf = _make_tapered_cylinder(
            lx, 0, lz, 0.006, 0.004,
            body_y, segments=4, rings=1,
        )
        parts.append((lv, lf))

    # Tail (long, thin, naked)
    tail_segs = 6
    for i in range(tail_segs):
        t = i / tail_segs
        tr = 0.004 - t * 0.002
        ty = body_y - 0.01 - t * 0.01
        tz = -0.04 - t * 0.03
        tsv, tsf = _make_sphere(0, ty, tz, tr, rings=3, sectors=3)
        parts.append((tsv, tsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Rat_{style}", verts, faces,
                        style=style, category="vermin")


def generate_bat_mesh(style: str = "flying") -> MeshSpec:
    """Generate a stylized bat mesh with wings spread.

    Args:
        style: "flying" (wings fully spread) or "hanging" (wings folded, upside down).

    Returns:
        MeshSpec ~400-800 tris. Distinctive wing silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6

    # Body (small, compact)
    body_r = 0.02
    bv, bf = _make_sphere(0, 0, 0, body_r, rings=4, sectors=segs)
    parts.append((bv, bf))

    # Head (tiny)
    head_r = 0.012
    head_y = 0.025
    hdv, hdf = _make_sphere(0, head_y, 0.005, head_r, rings=4, sectors=segs)
    parts.append((hdv, hdf))

    # Ears (large for echolocation -- bat signature)
    for side in [-1.0, 1.0]:
        ev, ef = _make_cone(
            side * 0.008, head_y + head_r * 0.7, 0.002,
            0.005, 0.02, segments=4,
        )
        parts.append((ev, ef))

    # Snout (tiny)
    snv, snf = _make_sphere(0, head_y - 0.002, 0.005 + head_r * 0.9,
                             0.005, rings=3, sectors=3)
    parts.append((snv, snf))

    if style == "flying":
        # Wings spread (the dominant feature)
        for side in [-1.0, 1.0]:
            # Wing membrane: flat boxes for segments
            # Inner wing
            iwv, iwf = _make_box(side * 0.04, 0.005, -0.005,
                                  0.025, 0.002, 0.018)
            parts.append((iwv, iwf))
            # Mid wing
            mwv, mwf = _make_box(side * 0.08, 0.01, -0.008,
                                  0.022, 0.001, 0.02)
            parts.append((mwv, mwf))
            # Outer wing
            owv, owf = _make_box(side * 0.115, 0.015, -0.01,
                                  0.018, 0.001, 0.016)
            parts.append((owv, owf))
            # Wing finger bones
            for bi in range(3):
                bx = side * (0.03 + bi * 0.035)
                bbv, bbf = _make_tapered_cylinder(
                    bx, 0.003, -0.01, 0.002, 0.001,
                    0.035, segments=3, rings=1,
                )
                parts.append((bbv, bbf))
    else:
        # Wings folded (hanging bat)
        for side in [-1.0, 1.0]:
            wv, wf = _make_tapered_cylinder(
                side * 0.02, -0.01, 0,
                0.012, 0.008, 0.03, segments=4, rings=1,
            )
            parts.append((wv, wf))

    # Tiny legs
    for side in [-1.0, 1.0]:
        lv, lf = _make_tapered_cylinder(
            side * 0.01, -body_r, 0,
            0.003, 0.002, 0.015, segments=3, rings=1,
        )
        parts.append((lv, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Bat_{style}", verts, faces,
                        style=style, category="vermin")


def generate_small_spider_mesh(style: str = "standard") -> MeshSpec:
    """Generate a stylized small spider mesh (8-legged).

    Args:
        style: "standard" or "fat" (wider abdomen, for cave spiders).

    Returns:
        MeshSpec ~300-600 tris. Creepy eight-legged silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6
    is_fat = style == "fat"

    # Cephalothorax (front body)
    ct_r = 0.015
    ctv, ctf = _make_sphere(0, 0.02, 0.015, ct_r, rings=4, sectors=segs)
    parts.append((ctv, ctf))

    # Abdomen (rear, larger)
    ab_r = 0.022 if not is_fat else 0.03
    abv, abf = _make_sphere(0, 0.022, -0.02, ab_r, rings=4, sectors=segs)
    parts.append((abv, abf))

    # Eyes (cluster of tiny bumps)
    for side in [-1.0, 1.0]:
        for row in range(2):
            esv, esf = _make_sphere(
                side * 0.005, 0.028 + row * 0.003, 0.025 + row * 0.002,
                0.003, rings=2, sectors=3,
            )
            parts.append((esv, esf))

    # Mandibles
    for side in [-1.0, 1.0]:
        mv, mf = _make_cone(
            side * 0.005, 0.015, 0.03,
            0.003, 0.012, segments=3,
        )
        mv_rot = [(v[0], 0.015 + (v[2] - 0.03) * 0.2,
                    0.03 + (v[1] - 0.015) * 0.8) for v in mv]
        parts.append((mv_rot, mf))

    # 8 legs (4 pairs)
    for pair in range(4):
        pair_z = 0.015 - pair * 0.008
        for side in [-1.0, 1.0]:
            # Upper leg (outward and up)
            angle_out = 0.3 + pair * 0.2
            ul_len = 0.035 + pair * 0.005
            ulv, ulf = _make_tapered_cylinder(
                side * ct_r * 0.8, 0.02, pair_z,
                0.003, 0.002, ul_len, segments=3, rings=1,
            )
            # Angle outward
            ulv_a = [(v[0] + side * (v[1] - 0.02) * 1.2,
                      v[1] + (v[1] - 0.02) * 0.3, v[2]) for v in ulv]
            parts.append((ulv_a, ulf))
            # Lower leg (downward)
            ll_x = side * (ct_r * 0.8 + ul_len * 0.8)
            ll_y = 0.02 + ul_len * 0.4
            llv, llf = _make_tapered_cylinder(
                ll_x, 0, pair_z, 0.002, 0.001,
                ll_y, segments=3, rings=1,
            )
            parts.append((llv, llf))

    # Spinnerets (tiny bump at rear)
    spv, spf = _make_cone(0, 0.018, -0.02 - ab_r * 0.8,
                           0.004, 0.008, segments=3)
    spv_rot = [(v[0], 0.018 + (v[2] + 0.02 + ab_r * 0.8) * 0.1,
                -0.02 - ab_r * 0.8 + (v[1] - 0.018) * -0.5) for v in spv]
    parts.append((spv_rot, spf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"SmallSpider_{style}", verts, faces,
                        style=style, category="vermin")


def generate_beetle_mesh(style: str = "standard") -> MeshSpec:
    """Generate a stylized beetle mesh.

    Args:
        style: "standard" or "horned" (with horn on head).

    Returns:
        MeshSpec ~200-400 tris. Compact insect silhouette.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6
    is_horned = style == "horned"

    # Elytra (wing covers -- the dome shape, beetle signature)
    el_r = 0.018
    elv, elf = _make_sphere(0, 0.015, -0.005, el_r, rings=4, sectors=segs)
    # Flatten the bottom
    elv_flat = [(v[0], max(v[1], 0.005), v[2]) for v in elv]
    parts.append((elv_flat, elf))

    # Head (small, forward)
    head_r = 0.01
    head_z = 0.015
    hdv, hdf = _make_sphere(0, 0.012, head_z, head_r, rings=3, sectors=segs)
    parts.append((hdv, hdf))

    # Horn (if horned style)
    if is_horned:
        hrnv, hrnf = _make_cone(
            0, 0.018, head_z + head_r * 0.5,
            0.004, 0.025, segments=4,
        )
        hrnv_rot = [(v[0], 0.018 + (v[2] - head_z - head_r * 0.5) * 0.3,
                     head_z + head_r * 0.5 + (v[1] - 0.018) * 0.6) for v in hrnv]
        parts.append((hrnv_rot, hrnf))

    # Mandibles
    for side in [-1.0, 1.0]:
        mv, mf = _make_tapered_cylinder(
            side * 0.004, 0.01, head_z + head_r * 0.7,
            0.002, 0.001, 0.008, segments=3, rings=1,
        )
        parts.append((mv, mf))

    # Antennae
    for side in [-1.0, 1.0]:
        av, af = _make_tapered_cylinder(
            side * 0.006, 0.018, head_z + head_r * 0.3,
            0.001, 0.0008, 0.015, segments=3, rings=1,
        )
        av_a = [(v[0] + side * (v[1] - 0.018) * 0.3, v[1], v[2]) for v in av]
        parts.append((av_a, af))

    # Legs (6 -- 3 pairs)
    for pair in range(3):
        pz = 0.005 - pair * 0.008
        for side in [-1.0, 1.0]:
            lv, lf = _make_tapered_cylinder(
                side * el_r * 0.7, 0, pz,
                0.002, 0.001, 0.015, segments=3, rings=1,
            )
            lv_a = [(v[0] + side * (v[1]) * 0.8, v[1], v[2]) for v in lv]
            parts.append((lv_a, lf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Beetle_{style}", verts, faces,
                        style=style, category="vermin")


# =========================================================================
# CATEGORY: SWAMP ANIMALS
# =========================================================================


def generate_frog_mesh(style: str = "sitting") -> MeshSpec:
    """Generate a stylized frog mesh in sitting pose.

    Args:
        style: "sitting" (crouched) or "leaping" (legs extended).

    Returns:
        MeshSpec ~400-800 tris. Wide, squat amphibian.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 6
    is_leaping = style == "leaping"

    # Body (wide, flat, squat)
    body_rx = 0.035
    body_ry = 0.02
    bv, bf = _make_sphere(0, 0.03, 0, body_ry, rings=4, sectors=segs)
    # Squash vertically, widen horizontally
    bv_squash = [(v[0] * 1.5, v[1] * 0.7, v[2] * 1.2) for v in bv]
    parts.append((bv_squash, bf))

    # Head (wide, flat)
    head_y = 0.035
    head_z = 0.03
    hdv, hdf = _make_sphere(0, head_y, head_z, 0.018, rings=4, sectors=segs)
    hdv_sq = [(v[0] * 1.4, v[1] * 0.8, v[2]) for v in hdv]
    parts.append((hdv_sq, hdf))

    # Bulging eyes (frog signature)
    for side in [-1.0, 1.0]:
        ev, ef = _make_sphere(side * 0.02, head_y + 0.012, head_z + 0.005,
                               0.008, rings=3, sectors=4)
        parts.append((ev, ef))

    # Mouth line (wide jaw)
    mjv, mjf = _make_box(0, head_y - 0.01, head_z + 0.015,
                          0.025, 0.003, 0.005)
    parts.append((mjv, mjf))

    if is_leaping:
        # Hind legs extended back
        for side in [-1.0, 1.0]:
            # Thigh
            thv, thf = _make_tapered_cylinder(
                side * 0.03, 0.01, -0.03,
                0.012, 0.008, 0.04, segments=4, rings=1,
            )
            thv_a = [(v[0] + side * (v[1] - 0.01) * 0.3,
                      v[1] - abs(v[1] - 0.01) * 0.2,
                      v[2] - abs(v[1] - 0.01) * 0.3) for v in thv]
            parts.append((thv_a, thf))
            # Shin
            shv, shf = _make_tapered_cylinder(
                side * 0.04, 0.005, -0.06,
                0.007, 0.005, 0.035, segments=4, rings=1,
            )
            parts.append((shv, shf))
            # Webbed foot
            fv, ff = _make_box(side * 0.04, 0, -0.085, 0.01, 0.002, 0.012)
            parts.append((fv, ff))
    else:
        # Hind legs tucked (sitting)
        for side in [-1.0, 1.0]:
            hlv, hlf = _make_sphere(side * 0.03, 0.015, -0.02,
                                     0.015, rings=4, sectors=5)
            parts.append((hlv, hlf))
            # Folded shin
            fsv, fsf = _make_tapered_cylinder(
                side * 0.035, 0, -0.01,
                0.006, 0.008, 0.02, segments=4, rings=1,
            )
            parts.append((fsv, fsf))

    # Front legs (small)
    for side in [-1.0, 1.0]:
        flv, flf = _make_tapered_cylinder(
            side * 0.025, 0, 0.02,
            0.006, 0.004, 0.03, segments=4, rings=1,
        )
        parts.append((flv, flf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Frog_{style}", verts, faces,
                        style=style, category="swamp_animal")


def generate_snake_ambient_mesh(style: str = "coiled") -> MeshSpec:
    """Generate a stylized non-monster snake mesh (ambient wildlife).

    Args:
        style: "coiled" (resting coil) or "slithering" (S-curve).

    Returns:
        MeshSpec ~300-600 tris. Thin serpentine silhouette.
    """
    is_coiled = style == "coiled"
    rs = 6  # ring segments
    total_segs = 16
    thickness = 0.008
    length = 0.3

    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for i in range(total_segs + 1):
        t = i / total_segs
        # Taper: thicker in middle, thin at head and tail
        env = math.sin(t * math.pi)
        if t < 0.1:
            env = t / 0.1 * math.sin(0.1 * math.pi)
        r = thickness * max(0.3, env)

        if is_coiled:
            # Spiral coil
            coil_angle = t * math.pi * 4
            coil_r = 0.04 * (1.0 - t * 0.3)
            cx = math.cos(coil_angle) * coil_r
            cz = math.sin(coil_angle) * coil_r
            cy = thickness * 0.5 + r + t * 0.03  # Stack upward slightly
        else:
            # S-curve
            cx = math.sin(t * math.pi * 2) * 0.04
            cy = thickness * 0.5 + r
            cz = t * length - length / 2

        for j in range(rs):
            a = 2.0 * math.pi * j / rs
            verts.append((
                cx + math.cos(a) * r,
                cy + math.sin(a) * r * 0.8,
                cz,
            ))

    # Side faces
    for i in range(total_segs):
        for j in range(rs):
            j2 = (j + 1) % rs
            faces.append((
                i * rs + j, i * rs + j2,
                (i + 1) * rs + j2, (i + 1) * rs + j,
            ))

    # End caps
    faces.append(tuple(range(rs)))
    faces.append(tuple(total_segs * rs + j for j in range(rs - 1, -1, -1)))

    # Head (slightly wider at front end -- index total_segs)
    head_t = 1.0  # at the end of body
    if is_coiled:
        coil_a = head_t * math.pi * 4
        coil_r2 = 0.04 * (1.0 - head_t * 0.3)
        hx = math.cos(coil_a) * coil_r2
        hz = math.sin(coil_a) * coil_r2
        hy = thickness * 0.5 + thickness * 0.3 + head_t * 0.03
    else:
        hx = math.sin(head_t * math.pi * 2) * 0.04
        hy = thickness * 0.5 + thickness * 0.3
        hz = head_t * length - length / 2

    head_parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    hv, hf = _make_sphere(hx, hy + 0.003, hz, thickness * 1.3, rings=3, sectors=5)
    head_parts.append((hv, hf))

    # Eyes
    for side in [-1.0, 1.0]:
        esv, esf = _make_sphere(hx + side * thickness * 1.0,
                                 hy + 0.006, hz + thickness * 0.5,
                                 0.002, rings=2, sectors=3)
        head_parts.append((esv, esf))

    head_v, head_f = _merge_meshes(*head_parts)
    # Merge head onto body
    offset = len(verts)
    verts.extend(head_v)
    for face in head_f:
        faces.append(tuple(idx + offset for idx in face))

    return _make_result(f"SnakeAmbient_{style}", verts, faces,
                        style=style, category="swamp_animal")


def generate_turtle_mesh(style: str = "standing") -> MeshSpec:
    """Generate a stylized turtle mesh with shell.

    Args:
        style: "standing" (walking) or "retracted" (head/legs partially pulled in).

    Returns:
        MeshSpec ~500-1K tris. Dome shell with peeking limbs.
    """
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []
    segs = 8
    is_retracted = style == "retracted"

    # Shell (dome -- the most important feature)
    shell_r = 0.05
    # Upper shell (half sphere)
    usv, usf = _make_sphere(0, 0.03, 0, shell_r, rings=5, sectors=segs)
    # Flatten the bottom half
    usv_dome = [(v[0], max(v[1], 0.015), v[2]) for v in usv]
    parts.append((usv_dome, usf))

    # Plastron (bottom shell -- flat disc)
    pv, pf = _make_cylinder(0, 0.01, 0, shell_r * 0.9, 0.008,
                             segments=segs, cap_top=True, cap_bottom=True)
    parts.append((pv, pf))

    # Shell ridge pattern (rings on top)
    for ring_i in range(3):
        ring_r = shell_r * (0.8 - ring_i * 0.2)
        ring_y = 0.03 + shell_r * 0.3 * (1.0 - (ring_i * 0.25))
        rv, rf = _make_torus_ring(0, ring_y, 0, ring_r, 0.003,
                                   major_segments=segs, minor_segments=3)
        parts.append((rv, rf))

    head_extend = 0.6 if is_retracted else 1.0

    # Head
    head_z = shell_r * 0.9 * head_extend
    head_y = 0.03
    head_r = 0.015
    hdv, hdf = _make_sphere(0, head_y, head_z, head_r, rings=4, sectors=segs)
    parts.append((hdv, hdf))

    # Neck
    nv, nf = _make_tapered_cylinder(
        0, head_y - 0.005, shell_r * 0.5,
        0.01, 0.008, head_z - shell_r * 0.5, segments=5, rings=1,
    )
    parts.append((nv, nf))

    # Eyes
    for side in [-1.0, 1.0]:
        esv, esf = _make_sphere(side * 0.008, head_y + 0.008,
                                 head_z + head_r * 0.5,
                                 0.004, rings=2, sectors=3)
        parts.append((esv, esf))

    # Legs (4 stubby legs poking out from under shell)
    leg_extend = 0.5 if is_retracted else 1.0
    leg_positions = [
        (-0.035, 0.025),
        (0.035, 0.025),
        (-0.035, -0.025),
        (0.035, -0.025),
    ]
    for lx, lz in leg_positions:
        lv, lf = _make_tapered_cylinder(
            lx * leg_extend, 0, lz * leg_extend,
            0.01, 0.008, 0.02, segments=4, rings=1,
        )
        # Angle outward
        lv_a = [(v[0] + (lx / abs(lx) if lx != 0 else 0) * v[1] * 0.3,
                 v[1], v[2]) for v in lv]
        parts.append((lv_a, lf))

    # Tail (tiny)
    tlv, tlf = _make_cone(0, 0.02, -shell_r * 0.85 * leg_extend,
                           0.005, 0.015, segments=3)
    tlv_rot = [(v[0], 0.02 + (v[2] + shell_r * 0.85 * leg_extend) * 0.1,
                -shell_r * 0.85 * leg_extend + (v[1] - 0.02) * -0.5) for v in tlv]
    parts.append((tlv_rot, tlf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Turtle_{style}", verts, faces,
                        style=style, category="swamp_animal")


# =========================================================================
# Buildings & Structures (Task #43)
# =========================================================================


def generate_mine_entrance_mesh(style: str = "timber") -> MeshSpec:
    """Generate a mine shaft entrance with support beams, track, and cart.

    Args:
        style: "timber" (wooden beam supports), "stone" (hewn rock),
               "abandoned" (collapsed, overgrown).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    tunnel_w = 2.0
    tunnel_h = 2.5
    tunnel_d = 3.0
    hw = tunnel_w / 2
    hd = tunnel_d / 2

    if style == "timber":
        # Frame archway -- two vertical posts + crossbeam
        beam_r = 0.1
        for sx in [-1, 1]:
            pv, pf = _make_box(sx * hw, tunnel_h / 2, -hd,
                               beam_r, tunnel_h / 2, beam_r)
            parts.append((pv, pf))
        # Crossbeam
        cv, cf = _make_box(0, tunnel_h + beam_r, -hd,
                           hw + beam_r, beam_r, beam_r)
        parts.append((cv, cf))

        # Interior support beams (3 sets receding into the mine)
        for i in range(3):
            z_off = -hd - (i + 1) * 1.5
            for sx in [-1, 1]:
                sv, sf = _make_box(sx * (hw - 0.05), tunnel_h / 2, z_off,
                                   beam_r * 0.8, tunnel_h / 2, beam_r * 0.8)
                parts.append((sv, sf))
            # Crossbeam
            cbv, cbf = _make_box(0, tunnel_h + beam_r * 0.8, z_off,
                                 hw, beam_r * 0.8, beam_r * 0.8)
            parts.append((cbv, cbf))

        # Ground platform
        gv, gf = _make_box(0, -0.05, -hd * 2, hw + 0.5, 0.05, hd * 2)
        parts.append((gv, gf))

        # Rail tracks (two rails running into the mine)
        rail_w = 0.04
        rail_h = 0.03
        track_spacing = 0.5
        track_len = tunnel_d + 3.0
        for sx in [-1, 1]:
            rv, rf = _make_box(sx * track_spacing, rail_h / 2, -track_len / 2,
                               rail_w / 2, rail_h / 2, track_len / 2)
            parts.append((rv, rf))

        # Rail ties
        tie_count = int(track_len / 0.5)
        for i in range(tie_count):
            tz = -0.5 + (i + 0.5) * track_len / tie_count - track_len / 2
            tv, tf = _make_box(0, 0.005, tz,
                               track_spacing + 0.15, 0.01, 0.06)
            parts.append((tv, tf))

        # Mine cart (simple box on the track)
        cart_w = 0.6
        cart_h = 0.4
        cart_d = 0.8
        # Cart body
        mv, mf = _make_beveled_box(0, rail_h + cart_h / 2 + 0.1, 1.0,
                                   cart_w / 2, cart_h / 2, cart_d / 2,
                                   bevel=0.02)
        parts.append((mv, mf))
        # Cart wheels (4 small cylinders)
        for sz in [-1, 1]:
            for sx in [-1, 1]:
                wv, wf = _make_cylinder(sx * (cart_w / 2 + 0.02),
                                        rail_h + 0.08,
                                        1.0 + sz * cart_d * 0.35,
                                        0.06, 0.04, segments=6)
                parts.append((wv, wf))

    elif style == "stone":
        # Hewn stone entrance arch
        arch_thick = 0.3
        for sx in [-1, 1]:
            pv, pf = _make_beveled_box(sx * hw, tunnel_h / 2, -hd,
                                       arch_thick / 2, tunnel_h / 2, arch_thick / 2,
                                       bevel=0.02)
            parts.append((pv, pf))
        # Stone lintel
        lv, lf = _make_beveled_box(0, tunnel_h + arch_thick / 2, -hd,
                                   hw + arch_thick, arch_thick / 2, arch_thick / 2,
                                   bevel=0.02)
        parts.append((lv, lf))

        # Rough rock face around entrance
        for i in range(4):
            rx = -hw - 0.5 + i * (tunnel_w + 1.0) / 3
            ry = tunnel_h * 0.3 + i * 0.2
            rv, rf = _make_beveled_box(rx, ry, -hd - 0.3,
                                       0.4, 0.3, 0.2, bevel=0.05)
            parts.append((rv, rf))

        # Stone floor
        gv, gf = _make_beveled_box(0, -0.05, -hd * 2, hw + 0.3, 0.05, hd * 2,
                                   bevel=0.01)
        parts.append((gv, gf))

        # Rail tracks
        for sx in [-1, 1]:
            rv, rf = _make_box(sx * 0.5, 0.02, -tunnel_d, 0.03, 0.02, tunnel_d)
            parts.append((rv, rf))

    else:  # abandoned
        # Collapsed timber frame
        beam_r = 0.1
        # One standing post, one tilted
        pv, pf = _make_box(-hw, tunnel_h / 2, -hd,
                           beam_r, tunnel_h / 2, beam_r)
        parts.append((pv, pf))
        # Tilted post (lean inward)
        tv = [(-hw + tunnel_w * 0.9, 0, -hd - beam_r),
              (-hw + tunnel_w * 0.9 + beam_r * 2, 0, -hd - beam_r),
              (-hw + tunnel_w * 0.9 + beam_r * 2, 0, -hd + beam_r),
              (-hw + tunnel_w * 0.9, 0, -hd + beam_r),
              (-hw + tunnel_w * 0.7, tunnel_h * 0.7, -hd - beam_r),
              (-hw + tunnel_w * 0.7 + beam_r * 2, tunnel_h * 0.7, -hd - beam_r),
              (-hw + tunnel_w * 0.7 + beam_r * 2, tunnel_h * 0.7, -hd + beam_r),
              (-hw + tunnel_w * 0.7, tunnel_h * 0.7, -hd + beam_r)]
        tf = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        parts.append((tv, tf))

        # Fallen crossbeam
        fcv, fcf = _make_box(0, 0.15, -hd, hw * 0.8, beam_r * 0.8, beam_r * 0.8)
        parts.append((fcv, fcf))

        # Rubble pile
        for i in range(6):
            rx = -hw * 0.6 + i * hw * 0.24
            rz = -hd + 0.5 * ((i * 7) % 3 - 1)
            rv, rf = _make_beveled_box(rx, 0.1, rz, 0.2, 0.1, 0.15, bevel=0.03)
            parts.append((rv, rf))

        # Overgrown ground
        gv, gf = _make_box(0, -0.05, -hd, hw + 0.5, 0.05, hd + 0.5)
        parts.append((gv, gf))

        # Rusted broken rail
        rv, rf = _make_box(0, 0.02, -1.0, 0.03, 0.02, 1.5)
        parts.append((rv, rf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"MineEntrance_{style}", verts, faces,
                        style=style, category="building")


def generate_sewer_tunnel_mesh(style: str = "brick") -> MeshSpec:
    """Generate a brick-lined sewer tunnel section with water channel and walkway.

    Args:
        style: "brick" (intact masonry), "stone" (rough-hewn),
               "collapsed" (partially caved in).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    tunnel_w = 3.0
    tunnel_h = 2.5
    tunnel_d = 6.0
    hw = tunnel_w / 2
    hd = tunnel_d / 2
    wall_thick = 0.2

    if style == "brick":
        # Tunnel walls (left and right)
        for sx in [-1, 1]:
            wv, wf = _make_beveled_box(sx * (hw + wall_thick / 2), tunnel_h / 2, 0,
                                       wall_thick / 2, tunnel_h / 2, hd,
                                       bevel=0.01)
            parts.append((wv, wf))

        # Ceiling (arched approximation -- flat slab)
        cv, cf = _make_beveled_box(0, tunnel_h + wall_thick / 2, 0,
                                   hw + wall_thick, wall_thick / 2, hd,
                                   bevel=0.01)
        parts.append((cv, cf))

        # Floor
        fv, ff = _make_box(0, -0.05, 0, hw + wall_thick, 0.05, hd)
        parts.append((fv, ff))

        # Water channel (central trough)
        channel_w = 1.0
        channel_d = 0.3
        # Channel depression
        chv, chf = _make_box(0, -channel_d / 2 - 0.05, 0,
                             channel_w / 2, channel_d / 2, hd - 0.1)
        parts.append((chv, chf))
        # Water surface (slightly below floor level)
        wsv, wsf = _make_box(0, -0.15, 0, channel_w / 2 - 0.05, 0.01, hd - 0.2)
        parts.append((wsv, wsf))

        # Walkways (raised edges along each side of channel)
        for sx in [-1, 1]:
            walk_x = sx * (channel_w / 2 + (hw - channel_w / 2) / 2)
            walk_w = (hw - channel_w / 2) / 2
            wkv, wkf = _make_box(walk_x, 0.02, 0, walk_w, 0.07, hd - 0.05)
            parts.append((wkv, wkf))

        # Grate openings (ceiling drains)
        for z in [-hd * 0.5, 0, hd * 0.5]:
            gv, gf = _make_box(0, tunnel_h - 0.01, z, 0.3, 0.01, 0.3)
            parts.append((gv, gf))

        # Pipe outlets (side wall)
        for z in [-hd * 0.3, hd * 0.4]:
            pv, pf = _make_cylinder(hw, tunnel_h * 0.4, z,
                                    0.12, wall_thick + 0.1, segments=8)
            parts.append((pv, pf))

    elif style == "stone":
        # Rougher stone walls
        for sx in [-1, 1]:
            wv, wf = _make_beveled_box(sx * (hw + wall_thick / 2), tunnel_h / 2, 0,
                                       wall_thick / 2 + 0.03, tunnel_h / 2, hd,
                                       bevel=0.03)
            parts.append((wv, wf))

        # Rough ceiling
        cv, cf = _make_beveled_box(0, tunnel_h + wall_thick / 2, 0,
                                   hw + wall_thick + 0.03, wall_thick / 2 + 0.03, hd,
                                   bevel=0.03)
        parts.append((cv, cf))

        # Uneven floor
        fv, ff = _make_beveled_box(0, -0.05, 0,
                                   hw + wall_thick, 0.05, hd, bevel=0.02)
        parts.append((fv, ff))

        # Central water channel
        chv, chf = _make_box(0, -0.2, 0, 0.6, 0.15, hd - 0.2)
        parts.append((chv, chf))

        # Walkways
        for sx in [-1, 1]:
            wkv, wkf = _make_beveled_box(sx * (hw * 0.6), 0.03, 0,
                                         hw * 0.3, 0.08, hd - 0.1,
                                         bevel=0.02)
            parts.append((wkv, wkf))

        # Stalactites from ceiling
        for i in range(4):
            sz = -hd * 0.6 + i * hd * 0.4
            sx = (-1) ** i * hw * 0.3
            sv, sf = _make_tapered_cylinder(sx, tunnel_h, sz,
                                            0.06, 0.01, -0.3,
                                            segments=5, rings=1)
            parts.append((sv, sf))

    else:  # collapsed
        # Partial walls
        wv, wf = _make_beveled_box(-hw - wall_thick / 2, tunnel_h / 2, 0,
                                   wall_thick / 2, tunnel_h / 2, hd,
                                   bevel=0.02)
        parts.append((wv, wf))
        # Right wall partially collapsed
        wv2, wf2 = _make_beveled_box(hw + wall_thick / 2, tunnel_h * 0.35, 0,
                                     wall_thick / 2 + 0.05, tunnel_h * 0.35, hd,
                                     bevel=0.03)
        parts.append((wv2, wf2))

        # Broken ceiling
        cv, cf = _make_beveled_box(-hw * 0.3, tunnel_h + wall_thick / 2, hd * 0.3,
                                   hw * 0.7, wall_thick / 2, hd * 0.6,
                                   bevel=0.02)
        parts.append((cv, cf))

        # Floor with debris
        fv, ff = _make_box(0, -0.05, 0, hw + wall_thick, 0.05, hd)
        parts.append((fv, ff))

        # Rubble pile from collapsed section
        for i in range(8):
            rx = hw * 0.2 + i * 0.2
            rz = -hd * 0.3 + (i * 5) % 4 * 0.4
            ry = 0.05 + i * 0.05
            rv, rf = _make_beveled_box(rx, ry, rz, 0.15, 0.1, 0.12, bevel=0.03)
            parts.append((rv, rf))

        # Stagnant water pool
        wsv, wsf = _make_box(0, -0.1, 0, 0.8, 0.01, hd * 0.7)
        parts.append((wsv, wsf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"SewerTunnel_{style}", verts, faces,
                        style=style, category="building")


def generate_catacomb_mesh(style: str = "ossuary") -> MeshSpec:
    """Generate a narrow corridor with burial niches in walls.

    Args:
        style: "ossuary" (skull-lined walls), "crypt" (stone sarcophagi),
               "burial_chamber" (open grave niches).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    corridor_w = 2.0
    corridor_h = 2.8
    corridor_d = 8.0
    hw = corridor_w / 2
    hd = corridor_d / 2
    wall_thick = 0.25

    # Base corridor walls
    for sx in [-1, 1]:
        wv, wf = _make_beveled_box(sx * (hw + wall_thick / 2), corridor_h / 2, 0,
                                   wall_thick / 2, corridor_h / 2, hd,
                                   bevel=0.01)
        parts.append((wv, wf))

    # Ceiling (vaulted -- flat approximation)
    cv, cf = _make_beveled_box(0, corridor_h + wall_thick / 2, 0,
                               hw + wall_thick, wall_thick / 2, hd,
                               bevel=0.01)
    parts.append((cv, cf))

    # Floor
    fv, ff = _make_beveled_box(0, -0.05, 0,
                               hw + wall_thick, 0.05, hd, bevel=0.01)
    parts.append((fv, ff))

    niche_count = 6  # per side

    if style == "ossuary":
        # Skull-lined niches along both walls
        for sx in [-1, 1]:
            for i in range(niche_count):
                nz = -hd + (i + 0.5) * corridor_d / niche_count
                ny = corridor_h * 0.4
                # Niche recess (box cutout visual)
                nv, nf = _make_box(sx * (hw + wall_thick * 0.3), ny, nz,
                                   wall_thick * 0.4, 0.25, 0.3)
                parts.append((nv, nf))
                # Skull placeholder (small sphere)
                sv, sf = _make_sphere(sx * (hw + wall_thick * 0.2), ny, nz,
                                      0.07, rings=4, sectors=6)
                parts.append((sv, sf))
            # Second row higher
            for i in range(niche_count):
                nz = -hd + (i + 0.5) * corridor_d / niche_count
                ny = corridor_h * 0.7
                nv, nf = _make_box(sx * (hw + wall_thick * 0.3), ny, nz,
                                   wall_thick * 0.4, 0.2, 0.25)
                parts.append((nv, nf))
                sv, sf = _make_sphere(sx * (hw + wall_thick * 0.2), ny, nz,
                                      0.06, rings=4, sectors=6)
                parts.append((sv, sf))

    elif style == "crypt":
        # Stone sarcophagi in wall alcoves
        for sx in [-1, 1]:
            for i in range(niche_count // 2):
                nz = -hd + (i + 0.5) * corridor_d / (niche_count // 2)
                # Alcove
                av, af = _make_box(sx * (hw + wall_thick), corridor_h * 0.35, nz,
                                   wall_thick * 0.8, 0.35, 0.5)
                parts.append((av, af))
                # Sarcophagus lid
                lv, lf = _make_beveled_box(sx * (hw + wall_thick), corridor_h * 0.55, nz,
                                           wall_thick * 0.6, 0.08, 0.4,
                                           bevel=0.02)
                parts.append((lv, lf))

        # Floor slab markers
        for i in range(4):
            fmv, fmf = _make_box(0, 0.01, -hd * 0.6 + i * hd * 0.4,
                                 hw * 0.7, 0.005, 0.35)
            parts.append((fmv, fmf))

    else:  # burial_chamber
        # Open grave niches (rectangular holes in walls)
        for sx in [-1, 1]:
            for i in range(niche_count):
                nz = -hd + (i + 0.5) * corridor_d / niche_count
                # Lower niche
                nv, nf = _make_box(sx * (hw + wall_thick * 0.5),
                                   corridor_h * 0.3, nz,
                                   wall_thick * 0.6, 0.3, 0.4)
                parts.append((nv, nf))
                # Upper niche
                nv2, nf2 = _make_box(sx * (hw + wall_thick * 0.5),
                                     corridor_h * 0.65, nz,
                                     wall_thick * 0.6, 0.25, 0.35)
                parts.append((nv2, nf2))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Catacomb_{style}", verts, faces,
                        style=style, category="building")


def generate_temple_mesh(style: str = "gothic") -> MeshSpec:
    """Generate a large temple with nave, columns, and altar platform.

    Args:
        style: "gothic" (pointed arches, tall), "ancient" (classical columns),
               "ruined" (collapsed roof, broken columns).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    temple_w = 10.0
    temple_d = 16.0
    temple_h = 8.0
    hw = temple_w / 2
    hd = temple_d / 2
    wall_thick = 0.3

    if style == "gothic":
        # Floor
        fv, ff = _make_beveled_box(0, -0.05, 0, hw + wall_thick, 0.05, hd + wall_thick,
                                   bevel=0.02)
        parts.append((fv, ff))

        # Side walls
        for sx in [-1, 1]:
            wv, wf = _make_beveled_box(sx * (hw + wall_thick / 2), temple_h / 2, 0,
                                       wall_thick / 2, temple_h / 2, hd,
                                       bevel=0.02)
            parts.append((wv, wf))

        # Back wall
        bwv, bwf = _make_beveled_box(0, temple_h / 2, -hd - wall_thick / 2,
                                     hw + wall_thick, temple_h / 2, wall_thick / 2,
                                     bevel=0.02)
        parts.append((bwv, bwf))

        # Front wall (with entrance gap -- two segments)
        front_half = hw * 0.35
        for sx in [-1, 1]:
            fwv, fwf = _make_beveled_box(sx * (hw - front_half / 2 + wall_thick / 2),
                                         temple_h / 2, hd + wall_thick / 2,
                                         front_half / 2, temple_h / 2, wall_thick / 2,
                                         bevel=0.02)
            parts.append((fwv, fwf))

        # Nave columns (two rows)
        col_spacing = temple_d / 6
        col_r = 0.2
        for sx in [-1, 1]:
            for i in range(5):
                cz = -hd + (i + 1) * col_spacing
                cv, cf = _make_cylinder(sx * (hw * 0.6), 0, cz,
                                        col_r, temple_h, segments=8)
                parts.append((cv, cf))

        # Pointed roof (two slanted planes)
        ridge_h = temple_h + 3.0
        roof_verts = [
            (-hw - wall_thick, temple_h, -hd - wall_thick),
            (hw + wall_thick, temple_h, -hd - wall_thick),
            (0, ridge_h, -hd - wall_thick),
            (-hw - wall_thick, temple_h, hd + wall_thick),
            (hw + wall_thick, temple_h, hd + wall_thick),
            (0, ridge_h, hd + wall_thick),
        ]
        roof_faces = [
            (0, 2, 1),
            (3, 4, 5),
            (0, 3, 5, 2),
            (1, 2, 5, 4),
        ]
        parts.append((roof_verts, roof_faces))

        # Altar platform
        av, af = _make_beveled_box(0, 0.3, -hd + 2.0, 1.5, 0.3, 1.0, bevel=0.03)
        parts.append((av, af))
        # Altar slab on top
        asv, asf = _make_beveled_box(0, 0.75, -hd + 2.0, 1.0, 0.15, 0.6, bevel=0.02)
        parts.append((asv, asf))

    elif style == "ancient":
        # Raised platform (stylobate)
        step_h = 0.2
        for i in range(3):
            sv, sf = _make_beveled_box(0, i * step_h + step_h / 2, 0,
                                       hw + wall_thick + (2 - i) * 0.3,
                                       step_h / 2,
                                       hd + wall_thick + (2 - i) * 0.3,
                                       bevel=0.01)
            parts.append((sv, sf))

        base_y = 3 * step_h

        # Floor
        fv, ff = _make_box(0, base_y, 0, hw, 0.05, hd)
        parts.append((fv, ff))

        # Peristyle columns (around perimeter)
        col_r = 0.25
        n_side = 6
        n_front = 4
        # Front/back columns
        for row_z, count in [(hd - 0.3, n_front), (-hd + 0.3, n_front)]:
            for i in range(count):
                cx_pos = -hw + (i + 0.5) * temple_w / count + 0.3
                cv, cf = _make_tapered_cylinder(cx_pos, base_y, row_z,
                                                col_r, col_r * 0.85, temple_h - base_y,
                                                segments=8, rings=1)
                parts.append((cv, cf))
        # Side columns
        for side_x in [-hw + 0.3, hw - 0.3]:
            for i in range(n_side):
                cz_pos = -hd + (i + 0.5) * temple_d / n_side + 0.3
                cv, cf = _make_tapered_cylinder(side_x, base_y, cz_pos,
                                                col_r, col_r * 0.85, temple_h - base_y,
                                                segments=8, rings=1)
                parts.append((cv, cf))

        # Entablature (beam across top of columns)
        ev, ef = _make_box(0, temple_h + 0.15, 0,
                           hw + 0.3, 0.3, hd + 0.3)
        parts.append((ev, ef))

        # Pediment (triangular gable on front)
        ped_h = 2.0
        ped_verts = [
            (-hw - 0.3, temple_h + 0.3, hd + 0.3),
            (hw + 0.3, temple_h + 0.3, hd + 0.3),
            (0, temple_h + 0.3 + ped_h, hd + 0.3),
        ]
        ped_faces = [(0, 1, 2)]
        parts.append((ped_verts, ped_faces))

        # Altar
        av, af = _make_beveled_box(0, base_y + 0.5, -hd * 0.5,
                                   0.8, 0.5, 0.5, bevel=0.02)
        parts.append((av, af))

    else:  # ruined
        # Broken floor
        fv, ff = _make_beveled_box(0, -0.05, 0, hw + wall_thick, 0.05, hd,
                                   bevel=0.02)
        parts.append((fv, ff))

        # Partial walls (varying heights)
        wall_configs = [
            (-hw - wall_thick / 2, 0, temple_h * 0.6, hd),       # left
            (hw + wall_thick / 2, 0, temple_h * 0.4, hd * 0.7),  # right partial
            (0, -hd - wall_thick / 2, temple_h * 0.5, hw),       # back partial
        ]
        for wx, wz, wh, wlen in wall_configs:
            if abs(wx) > abs(wz):
                wv, wf = _make_beveled_box(wx, wh / 2, 0,
                                           wall_thick / 2, wh / 2, wlen,
                                           bevel=0.02)
            else:
                wv, wf = _make_beveled_box(0, wh / 2, wz,
                                           wlen, wh / 2, wall_thick / 2,
                                           bevel=0.02)
            parts.append((wv, wf))

        # Broken columns (some standing, some fallen)
        col_r = 0.2
        standing = [(-hw * 0.6, -hd * 0.3), (hw * 0.6, hd * 0.2)]
        for cx_pos, cz_pos in standing:
            ch = temple_h * 0.5 + abs(cx_pos) * 0.3
            cv, cf = _make_cylinder(cx_pos, 0, cz_pos, col_r, ch, segments=8)
            parts.append((cv, cf))

        # Fallen column (horizontal)
        fcv, fcf = _make_cylinder(hw * 0.2, col_r, hd * 0.3,
                                  col_r, temple_h * 0.4, segments=8)
        # Rotate 90 degrees by swapping Y and Z
        fcv_rot = [(v[0], v[2] - hd * 0.3 + col_r, v[1] + hd * 0.3) for v in fcv]
        parts.append((fcv_rot, fcf))

        # Rubble
        for i in range(8):
            rx = -hw * 0.5 + i * hw * 0.15
            rz = hd * 0.1 * ((i * 3) % 5 - 2)
            rv, rf = _make_beveled_box(rx, 0.12, rz, 0.2, 0.12, 0.18, bevel=0.03)
            parts.append((rv, rf))

        # Broken altar
        av, af = _make_beveled_box(0.3, 0.25, -hd * 0.4, 0.7, 0.25, 0.5, bevel=0.03)
        parts.append((av, af))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"Temple_{style}", verts, faces,
                        style=style, category="building")


def generate_harbor_dock_mesh(style: str = "wooden") -> MeshSpec:
    """Generate an extended dock complex with multiple berths, crane, and warehouse.

    Args:
        style: "wooden" (timber construction), "stone" (masonry quay),
               "fortified" (military harbor with defensive elements).

    Returns:
        MeshSpec with vertices, faces, uvs, and metadata.
    """
    parts = []

    dock_w = 12.0
    dock_d = 18.0
    hw = dock_w / 2
    hd = dock_d / 2

    if style == "wooden":
        # Main pier platform
        deck_h = 0.1
        dv, df = _make_box(0, -deck_h / 2, 0, hw, deck_h / 2, hd)
        parts.append((dv, df))

        # Support piles (grid)
        pile_r = 0.12
        pile_h = 2.0
        n_rows = 6
        n_cols = 4
        for row in range(n_rows):
            for col in range(n_cols):
                px = -hw + (col + 0.5) * dock_w / n_cols
                pz = -hd + (row + 0.5) * dock_d / n_rows
                pv, pf = _make_cylinder(px, -pile_h, pz, pile_r, pile_h, segments=6)
                parts.append((pv, pf))

        # Berth fingers (3 perpendicular docks)
        finger_w = 2.0
        finger_d = 6.0
        for i in range(3):
            fz = -hd + (i + 1) * dock_d / 4
            fv, ff = _make_box(hw + finger_d / 2, -deck_h / 2, fz,
                               finger_d / 2, deck_h / 2, finger_w / 2)
            parts.append((fv, ff))
            # Finger piles
            for j in range(3):
                fpx = hw + (j + 0.5) * finger_d / 3
                for side in [-1, 1]:
                    fpz = fz + side * finger_w / 2 * 0.8
                    fpv, fpf = _make_cylinder(fpx, -pile_h, fpz,
                                              pile_r * 0.8, pile_h, segments=6)
                    parts.append((fpv, fpf))

            # Mooring bollards
            for side in [-1, 1]:
                bv, bf = _make_cylinder(hw + finger_d - 0.3, 0,
                                        fz + side * finger_w * 0.35,
                                        0.08, 0.4, segments=6)
                parts.append((bv, bf))

        # Crane structure (A-frame crane)
        crane_x = -hw * 0.5
        crane_z = hd * 0.5
        crane_h = 5.0
        # Two legs
        for sx in [-0.4, 0.4]:
            lv = [(crane_x + sx, 0, crane_z),
                  (crane_x + sx + 0.1, 0, crane_z),
                  (crane_x + sx + 0.1, 0, crane_z + 0.1),
                  (crane_x + sx, 0, crane_z + 0.1),
                  (crane_x + 0.05, crane_h, crane_z + 0.05),
                  (crane_x + 0.15, crane_h, crane_z + 0.05),
                  (crane_x + 0.15, crane_h, crane_z + 0.15),
                  (crane_x + 0.05, crane_h, crane_z + 0.15)]
            lf = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                  (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            parts.append((lv, lf))
        # Boom arm
        bav, baf = _make_box(crane_x, crane_h + 0.05, crane_z + 2.0,
                             0.05, 0.05, 2.0)
        parts.append((bav, baf))
        # Pulley block
        pbv, pbf = _make_box(crane_x, crane_h - 0.5, crane_z + 3.5,
                             0.05, 0.5, 0.05)
        parts.append((pbv, pbf))

        # Warehouse (simple box building)
        wh_w = 4.0
        wh_h = 3.0
        wh_d = 5.0
        whv, whf = _make_beveled_box(-hw * 0.3, wh_h / 2, -hd + wh_d / 2,
                                     wh_w / 2, wh_h / 2, wh_d / 2, bevel=0.03)
        parts.append((whv, whf))
        # Warehouse roof (slightly larger)
        wrv, wrf = _make_box(-hw * 0.3, wh_h + 0.1, -hd + wh_d / 2,
                             wh_w / 2 + 0.2, 0.1, wh_d / 2 + 0.2)
        parts.append((wrv, wrf))

    elif style == "stone":
        # Solid stone quay
        quay_h = 1.5
        qv, qf = _make_beveled_box(0, quay_h / 2, 0, hw, quay_h / 2, hd,
                                   bevel=0.03)
        parts.append((qv, qf))

        # Quay surface
        sv, sf = _make_box(0, quay_h + 0.02, 0, hw + 0.1, 0.02, hd + 0.1)
        parts.append((sv, sf))

        # Berth recesses (3 indentations in the quay face)
        for i in range(3):
            bz = -hd + (i + 1) * dock_d / 4
            bv, bf = _make_box(hw + 0.5, quay_h * 0.4, bz,
                               0.5, quay_h * 0.4, 1.5)
            parts.append((bv, bf))

        # Stone bollards
        for i in range(6):
            bz = -hd + (i + 0.5) * dock_d / 6
            bv, bf = _make_tapered_cylinder(hw - 0.3, quay_h, bz,
                                            0.12, 0.08, 0.5,
                                            segments=8, rings=1)
            parts.append((bv, bf))

        # Stone crane base
        crane_bv, crane_bf = _make_beveled_box(-hw * 0.4, quay_h + 0.5,
                                                hd * 0.5,
                                                0.5, 0.5, 0.5, bevel=0.02)
        parts.append((crane_bv, crane_bf))
        # Crane arm
        cav, caf = _make_box(-hw * 0.4, quay_h + 3.0, hd * 0.5 + 1.5,
                             0.06, 0.06, 1.5)
        parts.append((cav, caf))

        # Stone warehouse
        whv, whf = _make_beveled_box(-hw * 0.3, quay_h + 2.0, -hd + 3.0,
                                     2.5, 2.0, 2.5, bevel=0.03)
        parts.append((whv, whf))

    else:  # fortified
        # Reinforced stone quay with battlements
        quay_h = 2.0
        qv, qf = _make_beveled_box(0, quay_h / 2, 0, hw, quay_h / 2, hd,
                                   bevel=0.03)
        parts.append((qv, qf))

        # Surface
        sv, sf = _make_box(0, quay_h + 0.02, 0, hw + 0.1, 0.02, hd + 0.1)
        parts.append((sv, sf))

        # Defensive wall on seaward side
        dw_h = 3.0
        dwv, dwf = _make_beveled_box(hw + 0.2, quay_h + dw_h / 2, 0,
                                     0.2, dw_h / 2, hd, bevel=0.02)
        parts.append((dwv, dwf))

        # Merlons (crenellations)
        merlon_w = 0.4
        n_merlons = int(dock_d / (merlon_w * 2))
        for i in range(n_merlons):
            mz = -hd + (i * 2 + 0.5) * dock_d / (n_merlons * 2)
            mv, mf = _make_box(hw + 0.2, quay_h + dw_h + 0.25, mz,
                               0.22, 0.25, merlon_w / 2)
            parts.append((mv, mf))

        # Guard towers at corners
        tower_r = 1.0
        tower_h = 5.0
        for tz in [-hd + tower_r, hd - tower_r]:
            tv, tf = _make_cylinder(hw, quay_h, tz,
                                    tower_r, tower_h, segments=8)
            parts.append((tv, tf))
            # Tower cap
            tcv, tcf = _make_tapered_cylinder(hw, quay_h + tower_h, tz,
                                              tower_r * 1.1, tower_r * 0.3, 1.5,
                                              segments=8, rings=1)
            parts.append((tcv, tcf))

        # Chain boom anchors
        for tz in [-hd * 0.3, hd * 0.3]:
            cbv, cbf = _make_cylinder(hw + 0.5, quay_h, tz,
                                      0.15, 1.0, segments=6)
            parts.append((cbv, cbf))

        # Military warehouse (armored)
        whv, whf = _make_beveled_box(-hw * 0.3, quay_h + 2.5, -hd + 3.5,
                                     2.5, 2.5, 3.0, bevel=0.04)
        parts.append((whv, whf))

    verts, faces = _merge_meshes(*parts)
    return _make_result(f"HarborDock_{style}", verts, faces,
                        style=style, category="building")


# =========================================================================
# Registry: all generators by category
# =========================================================================

GENERATORS = {
    "furniture": {
        "table": generate_table_mesh,
        "chair": generate_chair_mesh,
        "shelf": generate_shelf_mesh,
        "chest": generate_chest_mesh,
        "barrel": generate_barrel_mesh,
        "candelabra": generate_candelabra_mesh,
        "bookshelf": generate_bookshelf_mesh,
        "bed": generate_bed_mesh,
        "wardrobe": generate_wardrobe_mesh,
        "cabinet": generate_cabinet_mesh,
        "curtain": generate_curtain_mesh,
        "mirror": generate_mirror_mesh,
        "hay_bale": generate_hay_bale_mesh,
        "wine_rack": generate_wine_rack_mesh,
        "bathtub": generate_bathtub_mesh,
        "fireplace": generate_fireplace_mesh,
    },
    "vegetation": {
        "tree": generate_tree_mesh,
        "rock": generate_rock_mesh,
        "mushroom": generate_mushroom_mesh,
        "root": generate_root_mesh,
        "ivy": generate_ivy_mesh,
    },
    "dungeon_prop": {
        "torch_sconce": generate_torch_sconce_mesh,
        "prison_door": generate_prison_door_mesh,
        "sarcophagus": generate_sarcophagus_mesh,
        "altar": generate_altar_mesh,
        "pillar": generate_pillar_mesh,
        "archway": generate_archway_mesh,
        "chain": generate_chain_mesh,
        "skull_pile": generate_skull_pile_mesh,
        # Structural
        "portcullis": generate_portcullis_mesh,
        "iron_gate": generate_iron_gate_mesh,
        "bridge_plank": generate_bridge_plank_mesh,
        # Imprisonment
        "shackle": generate_shackle_mesh,
        "cage": generate_cage_mesh,
        "stocks": generate_stocks_mesh,
        "iron_maiden": generate_iron_maiden_mesh,
        "prisoner_skeleton": generate_prisoner_skeleton_mesh,
        # Ambiance
        "cobweb": generate_cobweb_mesh,
        "spider_egg_sac": generate_spider_egg_sac_mesh,
        "rubble_pile": generate_rubble_pile_mesh,
        "hanging_skeleton": generate_hanging_skeleton_mesh,
        "dripping_water": generate_dripping_water_mesh,
        "rat_nest": generate_rat_nest_mesh,
        "rotting_barrel": generate_rotting_barrel_mesh,
        # Loot/Discovery
        "treasure_chest": generate_treasure_chest_mesh,
        "gem_pile": generate_gem_pile_mesh,
        "gold_pile": generate_gold_pile_mesh,
        "lore_tablet": generate_lore_tablet_mesh,
    },
    "weapon": {
        "hammer": generate_hammer_mesh,
        "spear": generate_spear_mesh,
        "crossbow": generate_crossbow_mesh,
        "scythe": generate_scythe_mesh,
        "flail": generate_flail_mesh,
        "whip": generate_whip_mesh,
        "claw": generate_claw_mesh,
        "tome": generate_tome_mesh,
        "greatsword": generate_greatsword_mesh,
        "curved_sword": generate_curved_sword_mesh,
        "hand_axe": generate_hand_axe_mesh,
        "battle_axe": generate_battle_axe_mesh,
        "greataxe": generate_greataxe_mesh,
        "club": generate_club_mesh,
        "mace": generate_mace_mesh,
        "warhammer": generate_warhammer_mesh,
        "halberd": generate_halberd_mesh,
        "glaive": generate_glaive_mesh,
        "shortbow": generate_shortbow_mesh,
        "longbow": generate_longbow_mesh,
        "staff_magic": generate_staff_magic_mesh,
        "wand": generate_wand_mesh,
        "throwing_knife_weapon": generate_throwing_knife_weapon_mesh,
        # Dual-wield paired weapons
        "paired_daggers": generate_paired_daggers_mesh,
        "twin_swords": generate_twin_swords_mesh,
        "dual_axes": generate_dual_axes_mesh,
        "dual_claws": generate_dual_claws_mesh,
        # Fist / gauntlet weapons
        "brass_knuckles": generate_brass_knuckles_mesh,
        "cestus": generate_cestus_mesh,
        "bladed_gauntlet": generate_bladed_gauntlet_mesh,
        "iron_fist": generate_iron_fist_mesh,
        # Rapiers / thrusting swords
        "rapier": generate_rapier_mesh,
        "estoc": generate_estoc_mesh,
        # Throwing weapons
        "javelin": generate_javelin_mesh,
        "throwing_axe": generate_throwing_axe_mesh,
        "shuriken": generate_shuriken_mesh,
        "bola": generate_bola_mesh,
        # Off-hand focus items
        "orb_focus": generate_orb_focus_mesh,
        "skull_fetish": generate_skull_fetish_mesh,
        "holy_symbol": generate_holy_symbol_mesh,
        "totem": generate_totem_mesh,
    },
    "architecture": {
        "gargoyle": generate_gargoyle_mesh,
        "fountain": generate_fountain_mesh,
        "statue": generate_statue_mesh,
        "bridge": generate_bridge_mesh,
        "gate": generate_gate_mesh,
        "staircase": generate_staircase_mesh,
    },
    "fence_barrier": {
        "fence": generate_fence_mesh,
        "barricade": generate_barricade_mesh,
        "railing": generate_railing_mesh,
    },
    "trap": {
        "spike_trap": generate_spike_trap_mesh,
        "bear_trap": generate_bear_trap_mesh,
        "pressure_plate": generate_pressure_plate_mesh,
        "dart_launcher": generate_dart_launcher_mesh,
        "swinging_blade": generate_swinging_blade_mesh,
        "falling_cage": generate_falling_cage_mesh,
    },
    "vehicle": {
        "cart": generate_cart_mesh,
        "boat": generate_boat_mesh,
        "wagon_wheel": generate_wagon_wheel_mesh,
    },
    "structural": {
        "column_row": generate_column_row_mesh,
        "buttress": generate_buttress_mesh,
        "rampart": generate_rampart_mesh,
        "drawbridge": generate_drawbridge_mesh,
        "well": generate_well_mesh,
        "ladder": generate_ladder_mesh,
        "scaffolding": generate_scaffolding_mesh,
    },
    "dark_fantasy": {
        "sacrificial_circle": generate_sacrificial_circle_mesh,
        "corruption_crystal": generate_corruption_crystal_mesh,
        "veil_tear": generate_veil_tear_mesh,
        "soul_cage": generate_soul_cage_mesh,
        "blood_fountain": generate_blood_fountain_mesh,
        "bone_throne": generate_bone_throne_mesh,
        "dark_obelisk": generate_dark_obelisk_mesh,
        "spider_web": generate_spider_web_mesh,
        "coffin": generate_coffin_mesh,
        "gibbet": generate_gibbet_mesh,
        # Ritual
        "summoning_circle": generate_summoning_circle_mesh,
        "ritual_candles": generate_ritual_candles_mesh,
        "occult_symbols": generate_occult_symbols_mesh,
    },
    "container": {
        "urn": generate_urn_mesh,
        "crate": generate_crate_mesh,
        "sack": generate_sack_mesh,
        "basket": generate_basket_mesh,
        "treasure_pile": generate_treasure_pile_mesh,
        "potion_bottle": generate_potion_bottle_mesh,
        "scroll": generate_scroll_mesh,
    },
    "light_source": {
        "lantern": generate_lantern_mesh,
        "brazier": generate_brazier_mesh,
        "campfire": generate_campfire_mesh,
        "crystal_light": generate_crystal_light_mesh,
        "magic_orb_light": generate_magic_orb_light_mesh,
    },
    "door_window": {
        "door": generate_door_mesh,
        "window": generate_window_mesh,
        "trapdoor": generate_trapdoor_mesh,
    },
    "wall_decor": {
        "banner": generate_banner_mesh,
        "wall_shield": generate_wall_shield_mesh,
        "mounted_head": generate_mounted_head_mesh,
        "painting_frame": generate_painting_frame_mesh,
        "rug": generate_rug_mesh,
        "chandelier": generate_chandelier_mesh,
        "hanging_cage": generate_hanging_cage_mesh,
    },
    "crafting": {
        "anvil": generate_anvil_mesh,
        "forge": generate_forge_mesh,
        "workbench": generate_workbench_mesh,
        "cauldron": generate_cauldron_mesh,
        "grinding_wheel": generate_grinding_wheel_mesh,
        "loom": generate_loom_mesh,
        "market_stall": generate_market_stall_mesh,
    },
    "sign": {
        "signpost": generate_signpost_mesh,
        "gravestone": generate_gravestone_mesh,
        "waystone": generate_waystone_mesh,
        "milestone": generate_milestone_mesh,
    },
    "natural": {
        "stalactite": generate_stalactite_mesh,
        "stalagmite": generate_stalagmite_mesh,
        "bone_pile": generate_bone_pile_mesh,
        "nest": generate_nest_mesh,
        "geyser_vent": generate_geyser_vent_mesh,
        "fallen_log": generate_fallen_log_mesh,
    },
    "monster_part": {
        "horn": generate_horn_mesh,
        "claw_set": generate_claw_set_mesh,
        "tail": generate_tail_mesh,
        "wing": generate_wing_mesh,
        "tentacle": generate_tentacle_mesh,
        "mandible": generate_mandible_mesh,
        "carapace": generate_carapace_mesh,
        "spine_ridge": generate_spine_ridge_mesh,
        "fang": generate_fang_mesh,
    },
    "monster_body": {
        "humanoid_beast": generate_humanoid_beast_body,
        "quadruped": generate_quadruped_body,
        "serpent": generate_serpent_body,
        "insectoid": generate_insectoid_body,
        "skeletal_frame": generate_skeletal_frame,
        "golem": generate_golem_body,
    },
    "projectile": {
        "arrow": generate_arrow_mesh,
        "magic_orb": generate_magic_orb_mesh,
        "throwing_knife": generate_throwing_knife_mesh,
        "bomb": generate_bomb_mesh,
        "fire_arrow": generate_fire_arrow_mesh,
        "ice_arrow": generate_ice_arrow_mesh,
        "poison_arrow": generate_poison_arrow_mesh,
        "explosive_bolt": generate_explosive_bolt_mesh,
        "silver_arrow": generate_silver_arrow_mesh,
        "barbed_arrow": generate_barbed_arrow_mesh,
    },
    "armor": {
        "helmet": generate_helmet_mesh,
        "pauldron": generate_pauldron_mesh,
        "gauntlet": generate_gauntlet_mesh,
        "greave": generate_greave_mesh,
        "breastplate": generate_breastplate_mesh,
        "shield": generate_shield_mesh,
        "heater_shield": generate_heater_shield_mesh,
        "pavise": generate_pavise_mesh,
        "targe": generate_targe_mesh,
        "magical_barrier": generate_magical_barrier_mesh,
        "bone_shield": generate_bone_shield_mesh,
        "crystal_shield": generate_crystal_shield_mesh,
        "living_wood_shield": generate_living_wood_shield_mesh,
        "aegis": generate_aegis_mesh,
    },
    "combat_item": {
        "spell_scroll": generate_spell_scroll_mesh,
        "rune_stone": generate_rune_stone_mesh,
    },
    "fortification": {
        "palisade": generate_palisade_mesh,
        "watchtower": generate_watchtower_mesh,
        "battlement": generate_battlement_mesh,
        "moat_edge": generate_moat_edge_mesh,
    },
    "infrastructure": {
        "windmill": generate_windmill_mesh,
        "dock": generate_dock_mesh,
        "bridge_stone": generate_bridge_stone_mesh,
        "rope_bridge": generate_rope_bridge_mesh,
    },
    "camp": {
        "tent": generate_tent_mesh,
        "hitching_post": generate_hitching_post_mesh,
        "feeding_trough": generate_feeding_trough_mesh,
        "barricade_outdoor": generate_barricade_outdoor_mesh,
        "lookout_post": generate_lookout_post_mesh,
        "spike_fence": generate_spike_fence_mesh,
    },
    "consumable": {
        "health_potion": generate_health_potion_mesh,
        "mana_potion": generate_mana_potion_mesh,
        "antidote": generate_antidote_mesh,
        "bread": generate_bread_mesh,
        "cheese": generate_cheese_mesh,
        "meat": generate_meat_mesh,
        "apple": generate_apple_mesh,
        "mushroom_food": generate_mushroom_food_mesh,
        "fish": generate_fish_mesh,
    },
    "crafting_material": {
        "ore": generate_ore_mesh,
        "leather": generate_leather_mesh,
        "herb": generate_herb_mesh,
        "gem": generate_gem_mesh,
        "bone_shard": generate_bone_shard_mesh,
    },
    "currency": {
        "coin": generate_coin_mesh,
        "coin_pouch": generate_coin_pouch_mesh,
    },
    "key_item": {
        "key": generate_key_mesh,
        "map_scroll": generate_map_scroll_mesh,
        "lockpick": generate_lockpick_mesh,
    },
    "forest_animals": {
        "deer": generate_deer_mesh,
        "wolf": generate_wolf_mesh,
        "fox": generate_fox_mesh,
        "rabbit": generate_rabbit_mesh,
        "owl": generate_owl_mesh,
        "crow": generate_crow_mesh,
    },
    "mountain_animals": {
        "mountain_goat": generate_mountain_goat_mesh,
        "eagle": generate_eagle_mesh,
        "bear": generate_bear_mesh,
    },
    "domestic_animals": {
        "horse": generate_horse_mesh,
        "chicken": generate_chicken_mesh,
        "dog": generate_dog_mesh,
        "cat": generate_cat_mesh,
    },
    "vermin": {
        "rat": generate_rat_mesh,
        "bat": generate_bat_mesh,
        "small_spider": generate_small_spider_mesh,
        "beetle": generate_beetle_mesh,
    },
    "swamp_animals": {
        "frog": generate_frog_mesh,
        "snake_ambient": generate_snake_ambient_mesh,
        "turtle": generate_turtle_mesh,
    },
    "building": {
        "mine_entrance": generate_mine_entrance_mesh,
        "sewer_tunnel": generate_sewer_tunnel_mesh,
        "catacomb": generate_catacomb_mesh,
        "temple": generate_temple_mesh,
        "harbor_dock": generate_harbor_dock_mesh,
    },
}
