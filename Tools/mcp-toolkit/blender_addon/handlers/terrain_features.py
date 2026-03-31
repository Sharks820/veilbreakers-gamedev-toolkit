"""Terrain feature generators -- pure logic, no bpy/bmesh.

Generates walkable terrain features (canyons, waterfalls, cliff faces, swamps,
natural arches, geysers, sinkholes, floating rocks, ice formations, lava flows)
as mesh specification dicts. Each function returns vertices, faces, materials,
and feature metadata.

All functions are pure and operate on plain Python data structures.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any

from ._terrain_noise import _make_noise_generator


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Noise utility -- opensimplex via _terrain_noise (replaces old sin-hash)
# ---------------------------------------------------------------------------

# Module-level cache to avoid recreating noise generators per call.
_features_gen = None
_features_seed: int = -1


def _hash_noise(x: float, y: float, seed: int) -> float:
    """Opensimplex noise replacing old sin-hash. Returns values in [-1, 1]."""
    global _features_gen, _features_seed
    if _features_gen is None or _features_seed != seed:
        _features_gen = _make_noise_generator(seed)
        _features_seed = seed
    return _features_gen.noise2(x, y)


def _fbm(x: float, y: float, seed: int, octaves: int = 4) -> float:
    """Fractal Brownian motion noise using opensimplex."""
    gen = _make_noise_generator(seed)
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(octaves):
        total += gen.noise2(x * frequency, y * frequency) * amplitude
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


# ---------------------------------------------------------------------------
# Natural arch generator
# ---------------------------------------------------------------------------

def generate_natural_arch(
    span_width: float = 8.0,
    arch_height: float = 6.0,
    thickness: float = 2.0,
    roughness: float = 0.3,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a stone arch bridge formation with support pillars.

    The arch spans along the X axis centered at the origin. Two pillars
    support the arch at each end, and the arch surface is displaced with
    noise for a natural rocky appearance.

    Parameters
    ----------
    span_width : float
        Distance between the two support pillars.
    arch_height : float
        Maximum height of the arch apex above ground.
    thickness : float
        Thickness of the arch band (radial thickness of the stone).
    roughness : float
        Amount of noise displacement on the arch surface [0, 1].
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "pillars": list of pillar dicts (position, width, height)
        - "arch_apex": (x, y, z) of the highest point
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict with span_width, arch_height, thickness
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=arch_stone, 1=pillar_stone, 2=moss, 3=weathered_rock
    materials = ["arch_stone", "pillar_stone", "moss", "weathered_rock"]

    half_span = span_width / 2.0
    arch_depth = thickness * 1.5  # Depth into Y axis
    half_depth = arch_depth / 2.0

    # --- Arch curve ---
    # Parametric arch: semi-ellipse from -half_span to +half_span
    arch_segments = max(12, int(span_width * 3))
    ring_segments = max(6, int(thickness * 3))

    # Generate arch as a swept tube along the semi-elliptical path
    arch_start = len(vertices)
    for i in range(arch_segments + 1):
        t = i / arch_segments  # 0..1 along the arch
        angle = math.pi * t  # 0..pi (left pillar to right pillar)

        # Center of the arch tube at this point
        cx = -half_span * math.cos(angle)
        cz = arch_height * math.sin(angle)

        # Tangent direction for the cross-section orientation
        tx = half_span * math.sin(angle)
        tz = arch_height * math.cos(angle)
        tlen = math.sqrt(tx * tx + tz * tz)
        if tlen > 0:
            tx /= tlen
            tz /= tlen
        else:
            tx, tz = 0.0, 1.0

        # Normal (perpendicular to tangent in XZ plane)
        nx = -tz
        nz = tx

        for j in range(ring_segments):
            ring_t = j / ring_segments
            ring_angle = 2 * math.pi * ring_t

            # Cross-section: elliptical ring
            r_xz = thickness / 2.0  # Radius in the arch plane
            r_y = half_depth  # Radius perpendicular (Y axis)

            # Noise displacement
            noise_val = roughness * _hash_noise(
                cx * 0.3 + j * 1.7, cz * 0.3 + i * 0.5, seed
            ) * 0.5

            local_r_xz = r_xz + noise_val
            local_r_y = r_y + noise_val * 0.5

            # Position on the ring
            offset_xz = math.cos(ring_angle) * local_r_xz
            offset_y = math.sin(ring_angle) * local_r_y

            vx = cx + nx * offset_xz
            vy = offset_y
            vz = cz + nz * offset_xz

            vertices.append((vx, vy, vz))

    # Faces for the arch tube
    for i in range(arch_segments):
        for j in range(ring_segments):
            j_next = (j + 1) % ring_segments
            v0 = arch_start + i * ring_segments + j
            v1 = arch_start + i * ring_segments + j_next
            v2 = arch_start + (i + 1) * ring_segments + j_next
            v3 = arch_start + (i + 1) * ring_segments + j
            faces.append((v0, v1, v2, v3))
            # Moss on top half of arch (where rain collects)
            mat_idx = 2 if (j < ring_segments // 4 or j > 3 * ring_segments // 4) else 0
            # Weathered on the underside
            if ring_segments // 3 < j < 2 * ring_segments // 3:
                mat_idx = 3
            mat_indices.append(mat_idx)

    # --- Support pillars ---
    pillar_width = thickness * 0.8
    pillar_depth = arch_depth
    pillar_height_left = arch_height * 0.15  # Pillars extend below arch start
    pillar_height_right = arch_height * 0.15
    pillar_res_z = max(4, int(pillar_height_left * 2) + 2)

    pillars: list[dict[str, Any]] = []

    for side in (-1, 1):
        pillar_cx = side * half_span
        p_height = pillar_height_left if side == -1 else pillar_height_right
        # Make pillar taller: from ground (z=0) to slightly above arch base
        actual_pillar_h = max(p_height, thickness)

        pillar_start = len(vertices)
        hw = pillar_width / 2.0
        hd = pillar_depth / 2.0
        p_res_z = pillar_res_z

        for k in range(p_res_z):
            kt = k / max(p_res_z - 1, 1)
            z = -actual_pillar_h + kt * actual_pillar_h

            # Slight taper and noise
            taper = 1.0 - kt * 0.1
            noise_x = roughness * _hash_noise(z * 0.3, pillar_cx * 0.2, seed + 10 + side) * 0.2
            noise_y = roughness * _hash_noise(z * 0.3, pillar_cx * 0.2, seed + 20 + side) * 0.2

            # 4 corners of the pillar cross-section
            vertices.append((pillar_cx - hw * taper + noise_x, -hd * taper + noise_y, z))
            vertices.append((pillar_cx + hw * taper + noise_x, -hd * taper + noise_y, z))
            vertices.append((pillar_cx + hw * taper + noise_x, hd * taper + noise_y, z))
            vertices.append((pillar_cx - hw * taper + noise_x, hd * taper + noise_y, z))

        # Connect pillar faces
        for k in range(p_res_z - 1):
            base = pillar_start + k * 4
            top = pillar_start + (k + 1) * 4
            for f in range(4):
                f_next = (f + 1) % 4
                faces.append((base + f, base + f_next, top + f_next, top + f))
                mat_indices.append(1)

        pillars.append({
            "position": (pillar_cx, 0.0, -actual_pillar_h / 2.0),
            "width": pillar_width,
            "depth": pillar_depth,
            "height": actual_pillar_h,
        })

    arch_apex: Vec3 = (0.0, 0.0, arch_height)

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "pillars": pillars,
        "arch_apex": arch_apex,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "span_width": span_width,
            "arch_height": arch_height,
            "thickness": thickness,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Geyser generator
# ---------------------------------------------------------------------------

def generate_geyser(
    pool_radius: float = 3.0,
    pool_depth: float = 0.5,
    vent_height: float = 1.0,
    mineral_rim_width: float = 0.8,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a hot spring with geyser vent, mineral rim, and terraced deposits.

    The geyser is centered at the origin. A circular depression forms the pool,
    surrounded by a raised mineral rim. A central vent cone rises from the pool
    center. Terraced mineral deposits ring the outside.

    Parameters
    ----------
    pool_radius : float
        Radius of the hot spring pool.
    pool_depth : float
        Depth of the pool below ground level.
    vent_height : float
        Height of the central geyser vent cone above pool surface.
    mineral_rim_width : float
        Width of the mineral deposit rim around the pool.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "vent": dict with position and height
        - "pool": dict with center, radius, depth
        - "terraces": list of terrace ring dicts
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=mineral_deposit, 1=pool_water, 2=vent_rock, 3=sulfur_crust, 4=terrace_mineral
    materials = ["mineral_deposit", "pool_water", "vent_rock", "sulfur_crust", "terrace_mineral"]

    radial_res = max(16, int(pool_radius * 6))
    total_radius = pool_radius + mineral_rim_width * 3  # 3 terrace tiers

    # --- Pool bottom (concave disc) ---
    pool_start = len(vertices)
    # Center vertex
    vertices.append((0.0, 0.0, -pool_depth))

    for i in range(radial_res):
        angle = 2 * math.pi * i / radial_res
        r = pool_radius
        noise = _hash_noise(math.cos(angle) * 2.0, math.sin(angle) * 2.0, seed) * 0.1
        x = math.cos(angle) * (r + noise)
        y = math.sin(angle) * (r + noise)
        # Pool bottom slopes from center to edges
        edge_depth = pool_depth * 0.6
        z = -edge_depth
        vertices.append((x, y, z))

    # Pool bottom fan triangles
    for i in range(radial_res):
        i_next = (i + 1) % radial_res
        faces.append((pool_start, pool_start + 1 + i, pool_start + 1 + i_next))
        mat_indices.append(1)  # pool_water

    # --- Vent cone ---
    vent_start = len(vertices)
    vent_base_radius = min(pool_radius * 0.3, 1.0)
    vent_res = max(8, radial_res // 2)

    # Vent base ring
    for i in range(vent_res):
        angle = 2 * math.pi * i / vent_res
        noise = _hash_noise(math.cos(angle) * 3.0, math.sin(angle) * 3.0, seed + 5) * 0.08
        x = math.cos(angle) * (vent_base_radius + noise)
        y = math.sin(angle) * (vent_base_radius + noise)
        vertices.append((x, y, -pool_depth * 0.3))

    # Vent mid ring (narrower)
    vent_mid_start = len(vertices)
    vent_mid_radius = vent_base_radius * 0.6
    for i in range(vent_res):
        angle = 2 * math.pi * i / vent_res
        noise = _hash_noise(math.cos(angle) * 4.0, math.sin(angle) * 4.0, seed + 6) * 0.05
        x = math.cos(angle) * (vent_mid_radius + noise)
        y = math.sin(angle) * (vent_mid_radius + noise)
        vertices.append((x, y, vent_height * 0.5))

    # Vent tip
    vent_tip_idx = len(vertices)
    vertices.append((0.0, 0.0, vent_height))

    # Vent base to mid quads
    for i in range(vent_res):
        i_next = (i + 1) % vent_res
        v0 = vent_start + i
        v1 = vent_start + i_next
        v2 = vent_mid_start + i_next
        v3 = vent_mid_start + i
        faces.append((v0, v1, v2, v3))
        mat_indices.append(2)  # vent_rock

    # Vent mid to tip triangles
    for i in range(vent_res):
        i_next = (i + 1) % vent_res
        v0 = vent_mid_start + i
        v1 = vent_mid_start + i_next
        faces.append((v0, v1, vent_tip_idx))
        mat_indices.append(3)  # sulfur_crust

    # --- Mineral rim and terraces ---
    num_terraces = 3
    terraces: list[dict[str, Any]] = []

    prev_ring_start = pool_start + 1  # Pool edge ring
    prev_ring_count = radial_res

    for tier in range(num_terraces):
        tier_inner_r = pool_radius + tier * mineral_rim_width
        tier_outer_r = pool_radius + (tier + 1) * mineral_rim_width
        tier_z = mineral_rim_width * 0.3 * (tier + 1)  # Each terrace slightly higher
        tier_z += _hash_noise(float(tier), 0.0, seed + 20) * 0.05

        ring_start = len(vertices)
        for i in range(radial_res):
            angle = 2 * math.pi * i / radial_res
            noise = _hash_noise(
                math.cos(angle) * (tier + 2), math.sin(angle) * (tier + 2), seed + 30 + tier
            ) * mineral_rim_width * 0.15
            r = tier_outer_r + noise
            x = math.cos(angle) * r
            y = math.sin(angle) * r
            z = tier_z + _hash_noise(x * 0.5, y * 0.5, seed + 40 + tier) * 0.05
            vertices.append((x, y, z))

        # Connect previous ring to this ring
        for i in range(radial_res):
            i_next = (i + 1) % radial_res
            v0 = prev_ring_start + i
            v1 = prev_ring_start + i_next
            v2 = ring_start + i_next
            v3 = ring_start + i
            faces.append((v0, v1, v2, v3))
            mat_idx = 0 if tier == 0 else 4  # mineral_deposit for rim, terrace_mineral for outer
            mat_indices.append(mat_idx)

        terraces.append({
            "tier": tier + 1,
            "inner_radius": tier_inner_r,
            "outer_radius": tier_outer_r,
            "elevation": tier_z,
        })

        prev_ring_start = ring_start
        prev_ring_count = radial_res

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "vent": {
            "position": (0.0, 0.0, vent_height),
            "height": vent_height,
            "base_radius": vent_base_radius,
        },
        "pool": {
            "center": (0.0, 0.0, -pool_depth),
            "radius": pool_radius,
            "depth": pool_depth,
        },
        "terraces": terraces,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "pool_radius": pool_radius,
            "pool_depth": pool_depth,
            "vent_height": vent_height,
            "mineral_rim_width": mineral_rim_width,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Sinkhole generator
# ---------------------------------------------------------------------------

def generate_sinkhole(
    radius: float = 5.0,
    depth: float = 8.0,
    wall_roughness: float = 0.5,
    has_bottom_cave: bool = True,
    rubble_density: float = 0.3,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a collapsed ground sinkhole with rough walls and rubble.

    The sinkhole is centered at the origin. The rim sits at Z=0, walls
    descend to -depth. Optional cave opening at the bottom and scattered
    rubble on the floor.

    Parameters
    ----------
    radius : float
        Radius of the sinkhole opening at ground level.
    depth : float
        Depth from rim to floor.
    wall_roughness : float
        Amount of noise on the wall surfaces [0, 1].
    has_bottom_cave : bool
        Whether to include a cave opening at the bottom.
    rubble_density : float
        Fraction of floor area covered with rubble [0, 1].
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "rim": dict with radius and vertices
        - "cave": dict with position, width, height (if has_bottom_cave)
        - "rubble": list of rubble piece dicts (position, size)
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=dirt_wall, 1=exposed_rock, 2=rubble, 3=cave_entrance, 4=rim_ground
    materials = ["dirt_wall", "exposed_rock", "rubble", "cave_entrance", "rim_ground"]

    radial_res = max(16, int(radius * 4))
    depth_res = max(6, int(depth * 2))

    # --- Ground rim (annular ring around the opening) ---
    rim_width = radius * 0.4
    rim_start = len(vertices)
    rim_verts: list[Vec3] = []

    for i in range(radial_res):
        angle = 2 * math.pi * i / radial_res
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Outer rim
        noise_outer = _hash_noise(cos_a * 3.0, sin_a * 3.0, seed + 1) * rim_width * 0.2
        r_outer = radius + rim_width + noise_outer
        v_outer = (cos_a * r_outer, sin_a * r_outer, 0.0)
        vertices.append(v_outer)

        # Inner rim (at the sinkhole edge)
        noise_inner = wall_roughness * _hash_noise(cos_a * 5.0, sin_a * 5.0, seed + 2) * radius * 0.08
        r_inner = radius + noise_inner
        z_inner = _hash_noise(cos_a * 2.0, sin_a * 2.0, seed + 3) * 0.15
        v_inner = (cos_a * r_inner, sin_a * r_inner, z_inner)
        vertices.append(v_inner)
        rim_verts.append(v_inner)

    # Rim faces (quads connecting outer-inner rings)
    for i in range(radial_res):
        i_next = (i + 1) % radial_res
        v_o0 = rim_start + i * 2
        v_i0 = rim_start + i * 2 + 1
        v_o1 = rim_start + i_next * 2
        v_i1 = rim_start + i_next * 2 + 1
        faces.append((v_o0, v_o1, v_i1, v_i0))
        mat_indices.append(4)  # rim_ground

    # --- Sinkhole walls ---
    wall_start = len(vertices)
    for k in range(depth_res + 1):
        kt = k / depth_res  # 0=top, 1=bottom
        z = -kt * depth

        # Radius narrows slightly toward bottom (natural collapse shape)
        r_at_depth = radius * (1.0 - kt * 0.15)

        for i in range(radial_res):
            angle = 2 * math.pi * i / radial_res
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)

            # Wall roughness: more noise further down
            noise_r = wall_roughness * _fbm(
                cos_a * 3.0 + kt * 2.0, sin_a * 3.0 + kt * 2.0, seed + 10
            ) * radius * 0.12
            noise_z = wall_roughness * _hash_noise(
                angle * 3.0, kt * 5.0, seed + 11
            ) * 0.3

            r = r_at_depth + noise_r
            x = cos_a * r
            y = sin_a * r
            vertices.append((x, y, z + noise_z))

    # Wall faces
    for k in range(depth_res):
        for i in range(radial_res):
            i_next = (i + 1) % radial_res
            v0 = wall_start + k * radial_res + i
            v1 = wall_start + k * radial_res + i_next
            v2 = wall_start + (k + 1) * radial_res + i_next
            v3 = wall_start + (k + 1) * radial_res + i
            faces.append((v0, v1, v2, v3))
            # Upper half dirt, lower half exposed rock
            mat_indices.append(0 if k < depth_res // 2 else 1)

    # --- Floor ---
    floor_start = len(vertices)
    floor_center_idx = len(vertices)
    vertices.append((0.0, 0.0, -depth))

    # Floor edge uses the bottom wall ring
    bottom_ring_start = wall_start + depth_res * radial_res
    for i in range(radial_res):
        i_next = (i + 1) % radial_res
        faces.append((floor_center_idx, bottom_ring_start + i, bottom_ring_start + i_next))
        mat_indices.append(2)  # rubble material for floor

    # --- Rubble pieces ---
    rubble: list[dict[str, Any]] = []
    floor_radius = radius * 0.85 * (1.0 - 0.15)  # Bottom radius
    num_rubble = max(0, int(rubble_density * 30))

    for ri in range(num_rubble):
        # Random position on floor
        r_pos = rng.uniform(0.0, floor_radius * 0.8)
        r_angle = rng.uniform(0.0, 2 * math.pi)
        rx = math.cos(r_angle) * r_pos
        ry = math.sin(r_angle) * r_pos
        rz = -depth
        r_size = rng.uniform(0.2, 0.8)

        rubble.append({
            "position": (rx, ry, rz),
            "size": r_size,
        })

        # Add simple rubble geometry (small displaced box)
        rb_start = len(vertices)
        hs = r_size / 2.0
        # Rubble is an irregular box with noise
        for dx, dy, dz in [
            (-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ]:
            noise_d = _hash_noise(
                rx + dx * 2.0, ry + dy * 2.0, seed + 100 + ri
            ) * r_size * 0.3
            vertices.append((
                rx + dx * hs + noise_d * 0.5,
                ry + dy * hs + noise_d * 0.5,
                rz + dz * r_size + abs(noise_d) * 0.3,
            ))
        # 6 faces of the box
        box_faces = [
            (0, 1, 2, 3), (4, 7, 6, 5),  # bottom, top
            (0, 4, 5, 1), (2, 6, 7, 3),  # front, back
            (0, 3, 7, 4), (1, 5, 6, 2),  # left, right
        ]
        for bf in box_faces:
            faces.append((rb_start + bf[0], rb_start + bf[1], rb_start + bf[2], rb_start + bf[3]))
            mat_indices.append(2)

    # --- Bottom cave ---
    cave_info: dict[str, Any] | None = None
    if has_bottom_cave:
        cave_angle = rng.uniform(0.0, 2 * math.pi)
        cave_width = rng.uniform(1.5, min(3.0, radius * 0.5))
        cave_height = rng.uniform(1.5, min(3.0, depth * 0.3))
        cave_depth_val = rng.uniform(3.0, 8.0)
        cave_r = radius * 0.85 * 0.85  # Near the bottom wall
        cave_x = math.cos(cave_angle) * cave_r
        cave_y = math.sin(cave_angle) * cave_r
        cave_z = -depth + cave_height * 0.5

        cave_info = {
            "position": (cave_x, cave_y, cave_z),
            "direction_angle": cave_angle,
            "width": cave_width,
            "height": cave_height,
            "depth": cave_depth_val,
        }

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "rim": {
            "radius": radius,
            "vertices": rim_verts,
        },
        "cave": cave_info,
        "rubble": rubble,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "radius": radius,
            "depth": depth,
            "wall_roughness": wall_roughness,
            "rubble_density": rubble_density,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Floating rocks generator
# ---------------------------------------------------------------------------

def generate_floating_rocks(
    count: int = 5,
    base_height: float = 4.0,
    max_size: float = 3.0,
    chain_links: int = 2,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a cluster of floating rock formations at varying heights.

    Each rock is an irregular polyhedron hovering above the ground at Y=0.
    Optional chain-link geometry connects rocks to anchor points on the ground.

    Parameters
    ----------
    count : int
        Number of floating rocks to generate.
    base_height : float
        Minimum hover height of the lowest rock.
    max_size : float
        Maximum diameter of any single rock.
    chain_links : int
        Number of chain links connecting each rock to ground (0 = no chains).
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "rocks": list of rock dicts (center, size, vertex_range)
        - "chains": list of chain dicts (anchor, rock_attach, links)
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=rock_surface, 1=rock_underside, 2=crystal_vein, 3=chain_metal
    materials = ["rock_surface", "rock_underside", "crystal_vein", "chain_metal"]

    rocks: list[dict[str, Any]] = []
    chains: list[dict[str, Any]] = []

    spread = max_size * count * 0.4  # Horizontal spread of the cluster

    for ri in range(count):
        # Determine rock position
        rock_x = rng.uniform(-spread, spread)
        rock_y = rng.uniform(-spread, spread)
        rock_z = base_height + rng.uniform(0.0, base_height * 1.5)
        rock_size = rng.uniform(max_size * 0.3, max_size)
        rock_half = rock_size / 2.0

        rock_start = len(vertices)

        # Generate an irregular polyhedron using an icosahedron-like approach
        # with noise displacement for natural irregularity
        ico_res = max(3, int(rock_size * 2))  # Resolution rings
        ring_count = ico_res

        # Top vertex
        top_idx = len(vertices)
        top_noise = _hash_noise(rock_x, rock_z + 10, seed + ri * 7) * rock_half * 0.2
        vertices.append((rock_x, rock_y, rock_z + rock_half + top_noise))

        # Latitude rings
        ring_starts: list[int] = []
        ring_sizes: list[int] = []
        for k in range(1, ring_count):
            kt = k / ring_count
            lat_angle = math.pi * kt  # 0..pi (top to bottom)
            ring_r = math.sin(lat_angle) * rock_half
            ring_z = rock_z + math.cos(lat_angle) * rock_half

            segments = max(5, int(6 + rock_size))
            ring_start_idx = len(vertices)
            ring_starts.append(ring_start_idx)
            ring_sizes.append(segments)

            for s in range(segments):
                s_angle = 2 * math.pi * s / segments
                noise_r = _hash_noise(
                    s_angle * 2.0 + ri, lat_angle * 3.0, seed + ri * 13 + k
                ) * rock_half * 0.25
                noise_z = _hash_noise(
                    s_angle * 3.0 + ri, lat_angle * 2.0, seed + ri * 17 + k
                ) * rock_half * 0.15

                r = ring_r + noise_r
                vx = rock_x + math.cos(s_angle) * r
                vy = rock_y + math.sin(s_angle) * r
                vz = ring_z + noise_z
                vertices.append((vx, vy, vz))

        # Bottom vertex
        bottom_idx = len(vertices)
        bottom_noise = _hash_noise(rock_x, rock_z - 10, seed + ri * 11) * rock_half * 0.2
        vertices.append((rock_x, rock_y, rock_z - rock_half + bottom_noise))

        # --- Faces ---
        # Top cap: connect top vertex to first ring
        if ring_starts:
            first_ring = ring_starts[0]
            first_size = ring_sizes[0]
            for s in range(first_size):
                s_next = (s + 1) % first_size
                faces.append((top_idx, first_ring + s, first_ring + s_next))
                mat_indices.append(0)  # rock_surface

            # Middle rings: connect adjacent rings
            for r_idx in range(len(ring_starts) - 1):
                r0_start = ring_starts[r_idx]
                r0_size = ring_sizes[r_idx]
                r1_start = ring_starts[r_idx + 1]
                r1_size = ring_sizes[r_idx + 1]

                # Connect rings with triangles (handle different segment counts)
                if r0_size == r1_size:
                    for s in range(r0_size):
                        s_next = (s + 1) % r0_size
                        v0 = r0_start + s
                        v1 = r0_start + s_next
                        v2 = r1_start + s_next
                        v3 = r1_start + s
                        faces.append((v0, v1, v2, v3))
                        # Underside material for bottom half
                        is_bottom = (r_idx + 1) > len(ring_starts) // 2
                        mat_indices.append(1 if is_bottom else 0)
                else:
                    # Fan triangles for mismatched rings
                    ratio = r1_size / r0_size
                    for s in range(r0_size):
                        s_next = (s + 1) % r0_size
                        s1 = int(s * ratio) % r1_size
                        s1_next = int(s_next * ratio) % r1_size
                        faces.append((r0_start + s, r0_start + s_next, r1_start + s1_next))
                        mat_indices.append(0)
                        if s1 != s1_next:
                            faces.append((r0_start + s, r1_start + s1_next, r1_start + s1))
                            mat_indices.append(0)

            # Bottom cap: connect last ring to bottom vertex
            last_ring = ring_starts[-1]
            last_size = ring_sizes[-1]
            for s in range(last_size):
                s_next = (s + 1) % last_size
                faces.append((last_ring + s, bottom_idx, last_ring + s_next))
                mat_indices.append(1)  # rock_underside

        rock_end = len(vertices)
        rocks.append({
            "center": (rock_x, rock_y, rock_z),
            "size": rock_size,
            "vertex_range": (rock_start, rock_end),
        })

        # --- Chain links ---
        if chain_links > 0:
            anchor_x = rock_x + rng.uniform(-0.5, 0.5)
            anchor_y = rock_y + rng.uniform(-0.5, 0.5)
            anchor_z = 0.0

            attach_z = rock_z - rock_half

            chain_link_list: list[dict[str, Any]] = []
            link_height = (attach_z - anchor_z) / max(chain_links, 1)
            link_radius = 0.08

            for li in range(chain_links):
                link_z_bottom = anchor_z + li * link_height
                link_z_top = link_z_bottom + link_height
                link_z_mid = (link_z_bottom + link_z_top) / 2.0

                link_start = len(vertices)
                # Simple chain link: 4-vertex ring at each end
                for end_z in (link_z_bottom, link_z_top):
                    for ci in range(4):
                        ca = 2 * math.pi * ci / 4
                        lx = anchor_x + math.cos(ca) * link_radius
                        ly = anchor_y + math.sin(ca) * link_radius
                        vertices.append((lx, ly, end_z))

                # Link faces (connect the two rings)
                for ci in range(4):
                    ci_next = (ci + 1) % 4
                    v0 = link_start + ci
                    v1 = link_start + ci_next
                    v2 = link_start + 4 + ci_next
                    v3 = link_start + 4 + ci
                    faces.append((v0, v1, v2, v3))
                    mat_indices.append(3)  # chain_metal

                chain_link_list.append({
                    "position": (anchor_x, anchor_y, link_z_mid),
                    "height": link_height,
                })

            chains.append({
                "rock_index": ri,
                "anchor": (anchor_x, anchor_y, anchor_z),
                "rock_attach": (rock_x, rock_y, attach_z),
                "links": chain_link_list,
            })

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "rocks": rocks,
        "chains": chains,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "count": count,
            "base_height": base_height,
            "max_size": max_size,
            "chain_links": chain_links,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Ice formation generator
# ---------------------------------------------------------------------------

def generate_ice_formation(
    width: float = 6.0,
    height: float = 4.0,
    depth: float = 3.0,
    stalactite_count: int = 8,
    ice_wall: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate ice cave/wall features with stalactites and refraction zones.

    The formation is oriented along the X axis. Ice stalactites hang from
    the ceiling (top of formation). An optional ice wall provides a
    semi-transparent backdrop with refraction-hint material zones.

    Parameters
    ----------
    width : float
        Width of the formation along X.
    height : float
        Height of the formation in Z.
    depth : float
        Depth of the formation into Y.
    stalactite_count : int
        Number of ice stalactites hanging from the ceiling.
    ice_wall : bool
        Whether to include an ice wall backdrop.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "stalactites": list of stalactite dicts (tip_position, length, base_radius)
        - "wall_info": dict with dimensions and refraction zones (if ice_wall)
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=clear_ice, 1=frosted_ice, 2=blue_ice, 3=ice_wall_refraction, 4=icicle_tip
    materials = ["clear_ice", "frosted_ice", "blue_ice", "ice_wall_refraction", "icicle_tip"]

    half_w = width / 2.0
    half_d = depth / 2.0

    # --- Ice stalactites ---
    stalactites: list[dict[str, Any]] = []
    for si in range(stalactite_count):
        # Position along ceiling
        sx = rng.uniform(-half_w * 0.9, half_w * 0.9)
        sy = rng.uniform(-half_d * 0.5, half_d * 0.5)
        stl_length = rng.uniform(height * 0.2, height * 0.8)
        stl_base_r = rng.uniform(0.1, 0.4)

        stalactites.append({
            "tip_position": (sx, sy, height - stl_length),
            "length": stl_length,
            "base_radius": stl_base_r,
        })

        # Generate cone geometry for stalactite
        cone_segments = 6
        cone_rings = max(3, int(stl_length * 2))

        stl_start = len(vertices)

        # Rings from base (at ceiling) to tip
        for k in range(cone_rings):
            kt = k / max(cone_rings - 1, 1)  # 0=base (ceiling), 1=tip
            ring_z = height - kt * stl_length

            # Radius tapers from base_r to near-zero
            ring_r = stl_base_r * (1.0 - kt * 0.95)
            # Add slight irregularity
            ring_r += _hash_noise(sx + kt * 3.0, sy + k * 1.5, seed + si * 7) * stl_base_r * 0.15

            for s in range(cone_segments):
                s_angle = 2 * math.pi * s / cone_segments
                noise = _hash_noise(s_angle * 2.0, kt * 4.0, seed + si * 11 + k) * ring_r * 0.1
                vx = sx + math.cos(s_angle) * (ring_r + noise)
                vy = sy + math.sin(s_angle) * (ring_r + noise)
                vertices.append((vx, vy, ring_z))

        # Tip vertex
        tip_idx = len(vertices)
        tip_noise_z = _hash_noise(sx * 2.0, sy * 2.0, seed + si * 13) * 0.05
        vertices.append((sx, sy, height - stl_length + tip_noise_z))

        # Stalactite faces: ring quads
        for k in range(cone_rings - 1):
            for s in range(cone_segments):
                s_next = (s + 1) % cone_segments
                v0 = stl_start + k * cone_segments + s
                v1 = stl_start + k * cone_segments + s_next
                v2 = stl_start + (k + 1) * cone_segments + s_next
                v3 = stl_start + (k + 1) * cone_segments + s
                faces.append((v0, v1, v2, v3))
                # Material: frosted near base, clear in middle, blue at tip
                if kt < 0.3:
                    mat_indices.append(1)  # frosted
                elif kt > 0.7:
                    mat_indices.append(2)  # blue
                else:
                    mat_indices.append(0)  # clear

        # Tip triangles (last ring to tip)
        last_ring_start = stl_start + (cone_rings - 1) * cone_segments
        for s in range(cone_segments):
            s_next = (s + 1) % cone_segments
            faces.append((last_ring_start + s, last_ring_start + s_next, tip_idx))
            mat_indices.append(4)  # icicle_tip

    # --- Ice wall ---
    wall_info: dict[str, Any] | None = None
    if ice_wall:
        wall_res_x = max(8, int(width * 2))
        wall_res_z = max(6, int(height * 2))
        wall_start = len(vertices)

        refraction_zones: list[dict[str, Any]] = []

        for k in range(wall_res_z):
            kt = k / max(wall_res_z - 1, 1)
            z = kt * height

            for ix in range(wall_res_x):
                ixt = ix / max(wall_res_x - 1, 1)
                x = -half_w + ixt * width

                # Wall surface with ice undulations
                y_base = half_d
                y_noise = _fbm(x * 0.3, z * 0.3, seed + 50, octaves=3) * 0.3
                y = y_base + y_noise

                vertices.append((x, y, z))

        # Wall faces
        for k in range(wall_res_z - 1):
            for ix in range(wall_res_x - 1):
                v0 = wall_start + k * wall_res_x + ix
                v1 = v0 + 1
                v2 = v0 + wall_res_x + 1
                v3 = v0 + wall_res_x
                faces.append((v0, v1, v2, v3))

                # Refraction zones: areas with high curvature
                x_center = -half_w + (ix + 0.5) / max(wall_res_x - 1, 1) * width
                z_center = (k + 0.5) / max(wall_res_z - 1, 1) * height
                curvature = abs(_fbm(x_center * 0.5, z_center * 0.5, seed + 60, octaves=2))

                if curvature > 0.3:
                    mat_indices.append(3)  # refraction zone
                else:
                    mat_indices.append(2)  # blue_ice

        # Identify distinct refraction zones
        num_zones = rng.randint(2, 5)
        for zi in range(num_zones):
            zx = rng.uniform(-half_w * 0.7, half_w * 0.7)
            zz = rng.uniform(height * 0.1, height * 0.9)
            z_radius = rng.uniform(0.5, 1.5)
            refraction_zones.append({
                "center": (zx, half_d, zz),
                "radius": z_radius,
            })

        wall_info = {
            "width": width,
            "height": height,
            "y_position": half_d,
            "refraction_zones": refraction_zones,
        }

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "stalactites": stalactites,
        "wall_info": wall_info,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "width": width,
            "height": height,
            "depth": depth,
            "stalactite_count": stalactite_count,
            "ice_wall": ice_wall,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


# ---------------------------------------------------------------------------
# Lava flow generator
# ---------------------------------------------------------------------------

def generate_lava_flow(
    length: float = 30.0,
    width: float = 4.0,
    edge_crust_width: float = 1.0,
    flow_segments: int = 20,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a sinuous lava river with cooled rock edges.

    The flow runs primarily along the X axis with sinusoidal curves.
    Hot lava in the center, cooling crust at edges, and solid rock beyond.

    Parameters
    ----------
    length : float
        Total length of the lava flow along X.
    width : float
        Width of the hot lava channel.
    edge_crust_width : float
        Width of the cooled crust on each side.
    flow_segments : int
        Number of segments along the flow length.
    seed : int
        Random seed.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices and faces
        - "flow_path": list of (x, y, z) centerline waypoints
        - "heat_zones": list of zone dicts (center, temperature)
        - "materials": list of material names
        - "material_indices": per-face material index list
        - "dimensions": dict
    """
    rng = random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    mat_indices: list[int] = []

    # Materials: 0=hot_lava, 1=cooling_crust, 2=solid_rock, 3=ember_glow
    materials = ["hot_lava", "cooling_crust", "solid_rock", "ember_glow"]

    total_width = width + 2 * edge_crust_width
    # Cross-section resolution: solid_rock | cooling_crust | hot_lava | cooling_crust | solid_rock
    # We need enough strips for material zones
    cross_res = max(8, int(total_width * 2))

    flow_path: list[Vec3] = []
    heat_zones: list[dict[str, Any]] = []

    # Sinuous curve parameters
    amplitude = width * 1.5
    frequency = 2 * math.pi / (length * 0.4)

    # --- Generate flow mesh ---
    rock_edge_outer = total_width / 2.0 + edge_crust_width  # Extra solid rock border

    for i in range(flow_segments + 1):
        t = i / flow_segments
        x = t * length

        # Sinuous Y offset
        y_center = amplitude * math.sin(frequency * x + _hash_noise(x * 0.1, 0.0, seed) * 1.5)
        # Slight Z variation (not flat)
        z_center = _hash_noise(x * 0.05, 0.0, seed + 5) * 0.5

        flow_path.append((x, y_center, z_center))

        # Tangent direction for cross-section orientation
        x_next = min((i + 1) / flow_segments, 1.0) * length
        y_next = amplitude * math.sin(frequency * x_next + _hash_noise(x_next * 0.1, 0.0, seed) * 1.5)
        dx = x_next - x if i < flow_segments else x - ((i - 1) / flow_segments * length)
        dy = y_next - y_center if i < flow_segments else y_center - amplitude * math.sin(
            frequency * ((i - 1) / flow_segments * length) + _hash_noise(
                ((i - 1) / flow_segments * length) * 0.1, 0.0, seed
            ) * 1.5
        )
        perp_len = math.sqrt(dx * dx + dy * dy)
        if perp_len > 0:
            # Perpendicular: rotate tangent 90 degrees
            perp_x = -dy / perp_len
            perp_y = dx / perp_len
        else:
            perp_x, perp_y = 0.0, 1.0

        # Generate cross-section vertices
        for j in range(cross_res + 1):
            jt = j / cross_res  # 0..1 across the flow
            offset = -rock_edge_outer + jt * 2 * rock_edge_outer

            # Height profile: raised edges, sunken center
            dist_from_center = abs(offset)
            if dist_from_center < width / 2.0:
                # Hot lava: slightly depressed
                z_profile = -0.2
            elif dist_from_center < width / 2.0 + edge_crust_width:
                # Cooling crust: slightly raised
                crust_t = (dist_from_center - width / 2.0) / edge_crust_width
                z_profile = 0.3 * crust_t
            else:
                # Solid rock: raised bank
                z_profile = 0.3 + 0.4 * ((dist_from_center - width / 2.0 - edge_crust_width) / edge_crust_width)
                z_profile = min(z_profile, 1.0)

            # Add noise
            noise = _hash_noise(x * 0.2 + offset * 0.5, offset * 0.3, seed + 15) * 0.15

            vx = x + perp_x * offset
            vy = y_center + perp_y * offset
            vz = z_center + z_profile + noise

            vertices.append((vx, vy, vz))

    # Generate faces
    for i in range(flow_segments):
        for j in range(cross_res):
            v0 = i * (cross_res + 1) + j
            v1 = v0 + 1
            v2 = (i + 1) * (cross_res + 1) + j + 1
            v3 = (i + 1) * (cross_res + 1) + j

            faces.append((v0, v1, v2, v3))

            # Determine material based on cross-section position
            jt = (j + 0.5) / cross_res
            offset = -rock_edge_outer + jt * 2 * rock_edge_outer
            dist = abs(offset)

            if dist < width / 2.0 * 0.6:
                mat_indices.append(0)  # hot_lava (center)
            elif dist < width / 2.0:
                mat_indices.append(3)  # ember_glow (transition)
            elif dist < width / 2.0 + edge_crust_width:
                mat_indices.append(1)  # cooling_crust
            else:
                mat_indices.append(2)  # solid_rock

    # --- Heat zones (for gameplay/VFX placement) ---
    num_heat_zones = max(3, flow_segments // 4)
    for hi in range(num_heat_zones):
        ht = (hi + 0.5) / num_heat_zones
        hx = ht * length
        hy = amplitude * math.sin(frequency * hx + _hash_noise(hx * 0.1, 0.0, seed) * 1.5)
        hz = _hash_noise(hx * 0.05, 0.0, seed + 5) * 0.5

        # Temperature varies along the flow (hotter near source)
        temperature = 1.0 - ht * 0.4 + rng.uniform(-0.1, 0.1)
        temperature = max(0.3, min(1.0, temperature))

        heat_zones.append({
            "center": (hx, hy, hz),
            "temperature": temperature,
            "radius": width * 0.8,
        })

    return {
        "mesh": {
            "vertices": vertices,
            "faces": faces,
        },
        "flow_path": flow_path,
        "heat_zones": heat_zones,
        "materials": materials,
        "material_indices": mat_indices,
        "dimensions": {
            "length": length,
            "width": width,
            "edge_crust_width": edge_crust_width,
            "flow_segments": flow_segments,
        },
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }
