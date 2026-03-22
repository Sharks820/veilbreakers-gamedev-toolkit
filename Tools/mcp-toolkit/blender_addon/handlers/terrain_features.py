"""Terrain feature generators -- pure logic, no bpy/bmesh.

Generates walkable terrain features (canyons, waterfalls, cliff faces, swamps)
as mesh specification dicts. Each function returns vertices, faces, materials,
and feature metadata.

All functions are pure and operate on plain Python data structures.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Noise utility (deterministic, no external dependency)
# ---------------------------------------------------------------------------

def _hash_noise(x: float, y: float, seed: int) -> float:
    """Simple deterministic pseudo-noise in [-1, 1]."""
    val = math.sin(x * 12.9898 + y * 78.233 + seed * 43.1234) * 43758.5453
    return (val - math.floor(val)) * 2.0 - 1.0


def _fbm(x: float, y: float, seed: int, octaves: int = 4) -> float:
    """Fractal Brownian motion noise."""
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(octaves):
        total += _hash_noise(x * frequency, y * frequency, seed) * amplitude
        max_val += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return total / max_val if max_val > 0 else 0.0


# ---------------------------------------------------------------------------
# Canyon generator
# ---------------------------------------------------------------------------

def generate_canyon(
    width: float = 5.0,
    length: float = 50.0,
    depth: float = 15.0,
    wall_roughness: float = 0.5,
    num_side_caves: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a walkable canyon with high walls, floor path, and side caves.

    The canyon runs along the X axis. The floor is at Z=0 with walls
    rising on both sides.

    Parameters
    ----------
    width : float
        Canyon floor width (walkable area).
    length : float
        Canyon length along X.
    depth : float
        Wall height (how deep the canyon is).
    wall_roughness : float
        Amount of irregular noise on wall surfaces [0, 1].
    num_side_caves : int
        Number of side cave openings to place in walls.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "floor_path": list of (x, y, z) waypoints along canyon floor
        - "side_caves": list of cave opening dicts
        - "materials": list of material zone names
        - "material_indices": list of per-face material indices
        - "dimensions": dict with width, length, depth
    """
    rng = random.Random(seed)
    res_along = max(4, int(length / 2))
    res_across = max(4, int(width) + 6)  # Extra for walls
    res_wall = max(4, int(depth / 2))

    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    half_w = width / 2.0

    # Material zones: 0=floor, 1=wall_rock, 2=wet_rock, 3=ledge
    materials = ["canyon_floor", "canyon_wall", "wet_rock", "canyon_ledge"]

    # --- Floor mesh ---
    floor_verts_start = len(vertices)
    for i in range(res_along):
        t = i / max(res_along - 1, 1)
        x = t * length

        for j in range(res_across):
            jt = j / max(res_across - 1, 1)
            y = -half_w + jt * width

            # Canyon floor with slight variation
            z = _hash_noise(x * 0.1, y * 0.1, seed) * 0.3
            # Slight downward slope for drainage
            z -= t * 0.5

            vertices.append((x, y, z))

    for i in range(res_along - 1):
        for j in range(res_across - 1):
            v0 = floor_verts_start + i * res_across + j
            v1 = v0 + 1
            v2 = v0 + res_across + 1
            v3 = v0 + res_across
            faces.append((v0, v1, v2, v3))
            mat_indices.append(0)  # floor

    # --- Left wall ---
    left_wall_start = len(vertices)
    for i in range(res_along):
        t = i / max(res_along - 1, 1)
        x = t * length

        for k in range(res_wall):
            kt = k / max(res_wall - 1, 1)
            z = kt * depth

            # Wall profile: slightly inward at top, rough
            y_offset = -wall_roughness * _hash_noise(x * 0.15, z * 0.15, seed + 1) * 1.5
            # Inward lean
            y_offset -= kt * 0.3
            y = -half_w + y_offset

            vertices.append((x, y, z))

    for i in range(res_along - 1):
        for k in range(res_wall - 1):
            v0 = left_wall_start + i * res_wall + k
            v1 = v0 + 1
            v2 = v0 + res_wall + 1
            v3 = v0 + res_wall
            faces.append((v0, v1, v2, v3))
            # Lower portions are wet
            mat_indices.append(2 if k < res_wall // 4 else 1)

    # --- Right wall ---
    right_wall_start = len(vertices)
    for i in range(res_along):
        t = i / max(res_along - 1, 1)
        x = t * length

        for k in range(res_wall):
            kt = k / max(res_wall - 1, 1)
            z = kt * depth

            y_offset = wall_roughness * _hash_noise(x * 0.15, z * 0.15, seed + 2) * 1.5
            y_offset += kt * 0.3
            y = half_w + y_offset

            vertices.append((x, y, z))

    for i in range(res_along - 1):
        for k in range(res_wall - 1):
            v0 = right_wall_start + i * res_wall + k
            v1 = v0 + 1
            v2 = v0 + res_wall + 1
            v3 = v0 + res_wall
            faces.append((v0, v1, v2, v3))
            mat_indices.append(2 if k < res_wall // 4 else 1)

    # --- Floor path (walkable waypoints) ---
    floor_path: list[Vec3] = []
    for i in range(0, res_along, max(1, res_along // 10)):
        t = i / max(res_along - 1, 1)
        x = t * length
        z = _hash_noise(x * 0.1, 0, seed) * 0.3 - t * 0.5
        floor_path.append((x, 0.0, z))
    # Ensure last point
    if floor_path and floor_path[-1][0] < length:
        z = _hash_noise(length * 0.1, 0, seed) * 0.3 - 0.5
        floor_path.append((length, 0.0, z))

    # --- Side caves ---
    side_caves: list[dict[str, Any]] = []
    for ci in range(num_side_caves):
        cave_x = rng.uniform(length * 0.1, length * 0.9)
        cave_side = rng.choice(["left", "right"])
        cave_y = -half_w if cave_side == "left" else half_w
        cave_z = rng.uniform(0.5, depth * 0.4)
        cave_width = rng.uniform(1.5, min(3.0, width * 0.6))
        cave_height = rng.uniform(1.5, 3.0)
        cave_depth = rng.uniform(3.0, 8.0)

        side_caves.append({
            "position": (cave_x, cave_y, cave_z),
            "side": cave_side,
            "width": cave_width,
            "height": cave_height,
            "depth": cave_depth,
        })

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "floor_path": floor_path,
        "side_caves": side_caves,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "width": width,
            "length": length,
            "depth": depth,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Waterfall generator
# ---------------------------------------------------------------------------

def generate_waterfall(
    height: float = 10.0,
    width: float = 3.0,
    pool_radius: float = 4.0,
    num_steps: int = 3,
    has_cave_behind: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate step-down terrain with wet rock, splash zone, and hidden cave.

    The waterfall faces along the -Y direction (water flows from +Y to -Y).
    The cliff face is at Y=0, pool extends into -Y.

    Parameters
    ----------
    height : float
        Total height of the waterfall.
    width : float
        Width of the water stream.
    pool_radius : float
        Radius of the splash pool at the base.
    num_steps : int
        Number of step-down ledges (1 = sheer drop, >1 = cascading).
    has_cave_behind : bool
        Whether to include a cave behind the waterfall.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "steps": list of step ledge dicts (position, width, height)
        - "pool": dict with center, radius, depth
        - "cave": dict with position and dimensions (if has_cave_behind)
        - "splash_zone": dict with center and radius
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict with height, width, pool_radius
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=cliff_rock, 1=wet_rock, 2=pool_bottom, 3=ledge, 4=moss
    materials = ["cliff_rock", "wet_rock", "pool_bottom", "ledge_stone", "moss"]

    step_height = height / max(num_steps, 1)
    half_w = width / 2.0

    # --- Cliff face (behind waterfall) ---
    cliff_res_x = max(4, int(width * 2) + 4)
    cliff_res_z = max(4, int(height))
    cliff_start = len(vertices)
    cliff_extent = width * 3  # Wider than the water stream

    for k in range(cliff_res_z):
        kt = k / max(cliff_res_z - 1, 1)
        z = kt * height

        for ix in range(cliff_res_x):
            ixt = ix / max(cliff_res_x - 1, 1)
            x = -cliff_extent / 2 + ixt * cliff_extent

            # Cliff face with roughness
            y_noise = _hash_noise(x * 0.2, z * 0.2, seed) * 0.5
            y = y_noise

            vertices.append((x, y, z))

    for k in range(cliff_res_z - 1):
        for ix in range(cliff_res_x - 1):
            v0 = cliff_start + k * cliff_res_x + ix
            v1 = v0 + 1
            v2 = v0 + cliff_res_x + 1
            v3 = v0 + cliff_res_x
            faces.append((v0, v1, v2, v3))
            # Wet zone in the center where water flows
            x_center = abs((ix / max(cliff_res_x - 1, 1)) - 0.5) * 2
            mat_indices.append(1 if x_center < 0.4 else 0)

    # --- Step ledges ---
    steps: list[dict[str, Any]] = []
    for si in range(num_steps):
        step_z = height - (si + 1) * step_height
        step_y = -(si + 1) * 1.5  # Each step protrudes forward
        step_w = width + rng.uniform(-0.5, 0.5)
        step_d = rng.uniform(0.8, 1.5)

        steps.append({
            "position": (0.0, step_y, step_z),
            "width": step_w,
            "depth": step_d,
            "height_drop": step_height,
        })

        # Add ledge geometry (simple quad)
        ledge_start = len(vertices)
        hw = step_w / 2
        vertices.extend([
            (-hw, step_y, step_z),
            (hw, step_y, step_z),
            (hw, step_y - step_d, step_z),
            (-hw, step_y - step_d, step_z),
            (-hw, step_y, step_z - 0.3),
            (hw, step_y, step_z - 0.3),
            (hw, step_y - step_d, step_z - 0.3),
            (-hw, step_y - step_d, step_z - 0.3),
        ])
        # Top face
        faces.append((ledge_start, ledge_start + 1, ledge_start + 2, ledge_start + 3))
        mat_indices.append(3)
        # Front face
        faces.append((ledge_start + 4, ledge_start + 5, ledge_start + 1, ledge_start))
        mat_indices.append(1)

    # --- Splash pool ---
    pool_res = 16
    pool_start = len(vertices)
    pool_depth = rng.uniform(0.5, 1.5)
    pool_center_y = -(num_steps * 1.5 + pool_radius * 0.5)

    for i in range(pool_res):
        angle = 2 * math.pi * i / pool_res
        x = math.cos(angle) * pool_radius
        y = pool_center_y + math.sin(angle) * pool_radius
        vertices.append((x, y, -pool_depth))

    # Pool center vertex
    pool_center_idx = len(vertices)
    vertices.append((0.0, pool_center_y, -pool_depth - 0.2))

    for i in range(pool_res):
        v0 = pool_start + i
        v1 = pool_start + (i + 1) % pool_res
        faces.append((v0, v1, pool_center_idx))
        mat_indices.append(2)

    pool_info = {
        "center": (0.0, pool_center_y, -pool_depth),
        "radius": pool_radius,
        "depth": pool_depth,
    }

    # --- Splash zone ---
    splash_zone = {
        "center": (0.0, pool_center_y, 0.0),
        "radius": pool_radius * 1.3,
    }

    # --- Cave behind waterfall ---
    cave_info: dict[str, Any] | None = None
    if has_cave_behind:
        cave_width = width * 0.8
        cave_height = min(height * 0.4, 3.0)
        cave_depth = rng.uniform(3.0, 6.0)
        cave_z = height * 0.1

        cave_info = {
            "position": (0.0, cave_depth * 0.5, cave_z),
            "width": cave_width,
            "height": cave_height,
            "depth": cave_depth,
            "entrance": (0.0, 0.5, cave_z),
        }

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "steps": steps,
        "pool": pool_info,
        "cave": cave_info,
        "splash_zone": splash_zone,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "height": height,
            "width": width,
            "pool_radius": pool_radius,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Cliff face generator
# ---------------------------------------------------------------------------

def generate_cliff_face(
    width: float = 20.0,
    height: float = 15.0,
    overhang: float = 3.0,
    num_cave_entrances: int = 2,
    has_ledge_path: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a vertical cliff with overhang, cave entrances, and ledge path.

    The cliff face runs along the X axis at Y=0, rising in Z.

    Parameters
    ----------
    width : float
        Width of the cliff face along X.
    height : float
        Cliff height in Z.
    overhang : float
        How far the top overhangs (in Y, toward -Y).
    num_cave_entrances : int
        Number of cave entrances in the cliff face.
    has_ledge_path : bool
        Whether to include a narrow ledge path along the cliff.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "cave_entrances": list of cave dicts
        - "ledge_path": list of (x, y, z) waypoints (if has_ledge_path)
        - "overhang_zone": dict with extent and vertices
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=cliff_rock, 1=moss_rock, 2=ledge, 3=overhang
    materials = ["cliff_rock", "moss_rock", "ledge_stone", "overhang_rock"]

    res_x = max(8, int(width))
    res_z = max(8, int(height))

    half_w = width / 2.0

    # --- Main cliff face ---
    cliff_start = len(vertices)
    for k in range(res_z):
        kt = k / max(res_z - 1, 1)
        z = kt * height

        # Overhang: top leans forward (toward -Y)
        overhang_amount = 0.0
        if kt > 0.7:
            overhang_factor = (kt - 0.7) / 0.3
            overhang_amount = -overhang * overhang_factor

        for ix in range(res_x):
            ixt = ix / max(res_x - 1, 1)
            x = -half_w + ixt * width

            # Rock surface roughness
            noise = _hash_noise(x * 0.1, z * 0.15, seed) * 0.8
            noise += _hash_noise(x * 0.3, z * 0.3, seed + 1) * 0.3

            y = noise + overhang_amount

            vertices.append((x, y, z))

    for k in range(res_z - 1):
        for ix in range(res_x - 1):
            v0 = cliff_start + k * res_x + ix
            v1 = v0 + 1
            v2 = v0 + res_x + 1
            v3 = v0 + res_x
            faces.append((v0, v1, v2, v3))

            kt = k / max(res_z - 1, 1)
            if kt > 0.7:
                mat_indices.append(3)  # overhang
            elif kt > 0.5:
                mat_indices.append(1)  # moss
            else:
                mat_indices.append(0)  # rock

    # --- Overhang underside ---
    overhang_start = len(vertices)
    overhang_res = max(4, int(width / 2))
    overhang_zone_verts: list[Vec3] = []

    for ix in range(overhang_res):
        ixt = ix / max(overhang_res - 1, 1)
        x = -half_w + ixt * width
        z = height

        for iy in range(4):
            iyt = iy / 3
            y = -overhang * iyt
            y += _hash_noise(x * 0.2, iyt * 10, seed + 3) * 0.3

            # Underside curves down slightly
            z_under = z - iyt * overhang * 0.15
            vt = (x, y, z_under)
            vertices.append(vt)
            overhang_zone_verts.append(vt)

    for ix in range(overhang_res - 1):
        for iy in range(3):
            v0 = overhang_start + ix * 4 + iy
            v1 = v0 + 1
            v2 = v0 + 4 + 1
            v3 = v0 + 4
            faces.append((v0, v1, v2, v3))
            mat_indices.append(3)

    # --- Cave entrances ---
    cave_entrances: list[dict[str, Any]] = []
    for ci in range(num_cave_entrances):
        cave_x = rng.uniform(-half_w * 0.7, half_w * 0.7)
        cave_z = rng.uniform(0.5, height * 0.4)
        c_width = rng.uniform(2.0, min(4.0, width * 0.3))
        c_height = rng.uniform(2.0, min(3.5, height * 0.2))
        c_depth = rng.uniform(3.0, 8.0)

        cave_entrances.append({
            "position": (cave_x, 0.0, cave_z),
            "width": c_width,
            "height": c_height,
            "depth": c_depth,
        })

    # --- Ledge path ---
    ledge_path: list[Vec3] = []
    if has_ledge_path:
        ledge_z = rng.uniform(height * 0.2, height * 0.5)
        ledge_width_val = rng.uniform(0.6, 1.2)

        for ix in range(res_x):
            ixt = ix / max(res_x - 1, 1)
            x = -half_w + ixt * width
            z = ledge_z + _hash_noise(x * 0.1, ledge_z, seed + 4) * 0.5
            y = -ledge_width_val + _hash_noise(x * 0.2, 0, seed + 5) * 0.2
            ledge_path.append((x, y, z))

        # Add ledge geometry
        ledge_start = len(vertices)
        for wp in ledge_path:
            vertices.append(wp)
            vertices.append((wp[0], wp[1] - ledge_width_val, wp[2]))

        for i in range(len(ledge_path) - 1):
            v0 = ledge_start + i * 2
            v1 = v0 + 1
            v2 = v0 + 3
            v3 = v0 + 2
            faces.append((v0, v1, v2, v3))
            mat_indices.append(2)

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "cave_entrances": cave_entrances,
        "ledge_path": ledge_path,
        "overhang_zone": {
            "extent": overhang,
            "vertices": overhang_zone_verts,
        },
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "width": width,
            "height": height,
            "overhang": overhang,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Swamp terrain generator
# ---------------------------------------------------------------------------

def generate_swamp_terrain(
    size: float = 50.0,
    water_level: float = 0.3,
    hummock_count: int = 12,
    island_count: int = 4,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate flat terrain with hummocks, waterlogged depressions, and islands.

    The terrain is a square grid centered at origin. Areas below water_level
    are marked as waterlogged.

    Parameters
    ----------
    size : float
        Side length of the square terrain.
    water_level : float
        Normalized water level [0, 1]. Areas below this are flooded.
    hummock_count : int
        Number of raised hummocks (small mounds).
    island_count : int
        Number of larger dry islands.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "hummocks": list of hummock dicts (position, radius, height)
        - "islands": list of island dicts
        - "water_zones": list of waterlogged area rects
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
        - "water_coverage": float (fraction of faces underwater)
    """
    rng = random.Random(seed)
    resolution = max(8, int(size / 2))
    half_size = size / 2.0

    # Materials: 0=mud, 1=shallow_water, 2=deep_water, 3=moss_ground, 4=dead_vegetation
    materials = ["swamp_mud", "shallow_water", "deep_water", "moss_ground", "dead_vegetation"]

    # Generate base heightmap
    heights: list[list[float]] = []
    for i in range(resolution):
        row: list[float] = []
        for j in range(resolution):
            x = -half_size + (j / max(resolution - 1, 1)) * size
            y = -half_size + (i / max(resolution - 1, 1)) * size

            # Very flat base with low-frequency undulation
            h = 0.2 + _fbm(x * 0.02, y * 0.02, seed, octaves=3) * 0.15
            # Add some micro-bumps
            h += _hash_noise(x * 0.1, y * 0.1, seed + 1) * 0.03
            row.append(h)
        heights.append(row)

    # Add hummocks (raised mounds)
    hummocks: list[dict[str, Any]] = []
    for hi in range(hummock_count):
        hx = rng.uniform(-half_size * 0.8, half_size * 0.8)
        hy = rng.uniform(-half_size * 0.8, half_size * 0.8)
        h_radius = rng.uniform(1.5, 4.0)
        h_height = rng.uniform(0.2, 0.6)

        hummocks.append({
            "position": (hx, hy, 0.0),
            "radius": h_radius,
            "height": h_height,
        })

        # Apply hummock to heightmap
        for i in range(resolution):
            for j in range(resolution):
                gx = -half_size + (j / max(resolution - 1, 1)) * size
                gy = -half_size + (i / max(resolution - 1, 1)) * size
                dist = math.sqrt((gx - hx) ** 2 + (gy - hy) ** 2)
                if dist < h_radius:
                    falloff = 1.0 - (dist / h_radius) ** 2
                    heights[i][j] += h_height * falloff

    # Add islands (larger dry areas)
    islands: list[dict[str, Any]] = []
    for ii in range(island_count):
        ix = rng.uniform(-half_size * 0.6, half_size * 0.6)
        iy = rng.uniform(-half_size * 0.6, half_size * 0.6)
        i_radius = rng.uniform(4.0, 10.0)
        i_height = rng.uniform(0.3, 0.7)

        islands.append({
            "position": (ix, iy, 0.0),
            "radius": i_radius,
            "height": i_height,
        })

        for i in range(resolution):
            for j in range(resolution):
                gx = -half_size + (j / max(resolution - 1, 1)) * size
                gy = -half_size + (i / max(resolution - 1, 1)) * size
                dist = math.sqrt((gx - ix) ** 2 + (gy - iy) ** 2)
                if dist < i_radius:
                    falloff = 1.0 - (dist / i_radius) ** 2
                    # Smoother falloff for islands
                    falloff = falloff * falloff
                    heights[i][j] += i_height * falloff

    # Create mesh
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int, int]] = []
    mat_indices: list[int] = []

    height_scale = size * 0.1  # Scale heights to world units

    for i in range(resolution):
        for j in range(resolution):
            x = -half_size + (j / max(resolution - 1, 1)) * size
            y = -half_size + (i / max(resolution - 1, 1)) * size
            z = heights[i][j] * height_scale
            vertices.append((x, y, z))

    water_z = water_level * height_scale
    water_face_count = 0

    for i in range(resolution - 1):
        for j in range(resolution - 1):
            v0 = i * resolution + j
            v1 = v0 + 1
            v2 = (i + 1) * resolution + j + 1
            v3 = (i + 1) * resolution + j
            faces.append((v0, v1, v2, v3))

            # Average height of face
            avg_z = (
                vertices[v0][2] + vertices[v1][2]
                + vertices[v2][2] + vertices[v3][2]
            ) / 4

            if avg_z < water_z - 0.5:
                mat_indices.append(2)  # deep water
                water_face_count += 1
            elif avg_z < water_z:
                mat_indices.append(1)  # shallow water
                water_face_count += 1
            elif avg_z < water_z + 0.5:
                mat_indices.append(0)  # mud
            elif avg_z < water_z + 1.5:
                mat_indices.append(3)  # moss ground
            else:
                mat_indices.append(4)  # dead vegetation

    # Compute water zones (axis-aligned rects of connected water faces)
    water_zones: list[dict[str, Any]] = []
    total_faces = len(faces)
    water_coverage = water_face_count / total_faces if total_faces > 0 else 0.0

    # Simplified: find bounding boxes of water regions
    water_cells: set[tuple[int, int]] = set()
    face_idx = 0
    for i in range(resolution - 1):
        for j in range(resolution - 1):
            if face_idx < len(mat_indices) and mat_indices[face_idx] in (1, 2):
                water_cells.add((i, j))
            face_idx += 1

    # Find connected components using flood fill
    visited: set[tuple[int, int]] = set()
    for cell in water_cells:
        if cell in visited:
            continue
        # BFS flood fill
        component: list[tuple[int, int]] = []
        queue = [cell]
        while queue:
            c = queue.pop()
            if c in visited or c not in water_cells:
                continue
            visited.add(c)
            component.append(c)
            ci, cj = c
            for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ni, nj = ci + di, cj + dj
                if (ni, nj) not in visited and (ni, nj) in water_cells:
                    queue.append((ni, nj))

        if component:
            min_i = min(c[0] for c in component)
            max_i = max(c[0] for c in component)
            min_j = min(c[1] for c in component)
            max_j = max(c[1] for c in component)

            # Convert grid coords to world coords
            x_min = -half_size + (min_j / max(resolution - 1, 1)) * size
            x_max = -half_size + ((max_j + 1) / max(resolution - 1, 1)) * size
            y_min = -half_size + (min_i / max(resolution - 1, 1)) * size
            y_max = -half_size + ((max_i + 1) / max(resolution - 1, 1)) * size

            water_zones.append({
                "bounds": (x_min, y_min, x_max, y_max),
                "cell_count": len(component),
            })

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "hummocks": hummocks,
        "islands": islands,
        "water_zones": water_zones,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "size": size,
            "water_level": water_level,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "water_coverage": water_coverage,
    }
