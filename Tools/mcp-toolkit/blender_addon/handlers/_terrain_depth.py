"""Pure-logic terrain depth generators for VeilBreakers.

Produces vertical/3D terrain geometry beyond heightmap limitations:
cliff faces, cave entrances, biome transitions, waterfalls, and bridges.

Also provides cliff edge detection for automatic cliff overlay placement
at steep terrain edges.

NO bpy/bmesh imports. All functions return MeshSpec dicts compatible
with the procedural_meshes module. Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any

import numpy as np

from .procedural_meshes import (
    _make_result,
    _merge_meshes,
    _compute_dimensions,
    generate_bridge_mesh,
)

# ---------------------------------------------------------------------------
# Type alias (matches procedural_meshes.py)
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# Generator 1: Cliff Face
# ---------------------------------------------------------------------------


def generate_cliff_face_mesh(
    width: float = 20.0,
    height: float = 15.0,
    segments_horizontal: int = 16,
    segments_vertical: int = 12,
    noise_amplitude: float = 0.8,
    noise_scale: float = 3.0,
    seed: int = 0,
    style: str = "granite",
) -> MeshSpec:
    """Generate a curved vertical cliff face with noise displacement.

    Creates a partial-cylinder surface standing upright (Y is vertical).
    Each grid vertex gets Gaussian noise displacement for natural rock look.

    Args:
        width: Horizontal extent of the cliff face.
        height: Vertical extent (Y-axis).
        segments_horizontal: Grid subdivisions along width.
        segments_vertical: Grid subdivisions along height.
        noise_amplitude: Strength of random surface displacement.
        noise_scale: Frequency scaling for noise variation.
        seed: Random seed for reproducibility.
        style: Visual style label stored in metadata.

    Returns:
        MeshSpec with cliff face geometry.
    """
    rng = random.Random(seed)
    seg_h = segments_horizontal
    seg_v = segments_vertical

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for iy in range(seg_v + 1):
        for ix in range(seg_h + 1):
            x_frac = ix / seg_h
            y_frac = iy / seg_v

            x = (x_frac - 0.5) * width
            y = y_frac * height

            # Base concave curve (partial cylinder effect)
            base_curve = 0.3 * math.sin(x_frac * math.pi)

            # Noise displacement in Z
            noise = rng.gauss(0.0, noise_amplitude) * (
                math.sin(x_frac * noise_scale * math.pi)
                * math.sin(y_frac * noise_scale * math.pi)
                + 0.5
            )

            z = base_curve + noise

            vertices.append((x, y, z))

    # Quad faces for the grid
    for iy in range(seg_v):
        for ix in range(seg_h):
            row_width = seg_h + 1
            v0 = iy * row_width + ix
            v1 = v0 + 1
            v2 = v0 + row_width + 1
            v3 = v0 + row_width
            faces.append((v0, v1, v2, v3))

    return _make_result(
        f"CliffFace_{style}",
        vertices,
        faces,
        category="terrain_depth",
        style=style,
        segments_horizontal=seg_h,
        segments_vertical=seg_v,
    )


# ---------------------------------------------------------------------------
# Generator 2: Cave Entrance
# ---------------------------------------------------------------------------


def generate_cave_entrance_mesh(
    width: float = 4.0,
    height: float = 4.0,
    depth: float = 3.0,
    arch_segments: int = 12,
    terrain_edge_height: float = 0.0,
    style: str = "natural",
    seed: int = 0,
) -> MeshSpec:
    """Generate a cave entrance archway with interior tunnel.

    Creates a semicircular arch opening with rectangular sides,
    extending into the terrain as a short tunnel segment.

    Args:
        width: Width of the entrance opening.
        height: Height of the entrance opening (to top of arch).
        depth: How far the tunnel extends into terrain (Z-axis).
        arch_segments: Number of segments in the semicircular arch.
        terrain_edge_height: Y offset for terrain-level placement.
        style: Visual style label.
        seed: Random seed for noise displacement.

    Returns:
        MeshSpec with cave entrance geometry.
    """
    rng = random.Random(seed)
    half_w = width / 2.0
    # The arch sits above rectangular sides. The straight sides go from
    # terrain_edge_height to the arch spring-line. The arch semicircle
    # then curves from spring-line up to the apex.
    spring_y = terrain_edge_height + height * 0.5  # where the arch starts curving
    apex_y = terrain_edge_height + height  # top of the arch

    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    # Number of depth segments for the tunnel
    depth_segs = max(2, int(depth / 0.5))

    # Build the tunnel profile at multiple depth slices
    # Each slice is the arch profile (semicircle + sides)
    profile_rings: list[list[tuple[float, float, float]]] = []

    for dz_i in range(depth_segs + 1):
        z_frac = dz_i / depth_segs
        z = -z_frac * depth  # tunnel goes in -Z direction

        ring: list[tuple[float, float, float]] = []

        # Left side bottom to spring-line
        side_segs = 3
        for si in range(side_segs + 1):
            y_frac = si / side_segs
            y = terrain_edge_height + y_frac * (spring_y - terrain_edge_height)
            noise = rng.gauss(0.0, 0.05) if style == "natural" else 0.0
            ring.append((-half_w + noise, y, z))

        # Arch semicircle (left to right across the top)
        arch_radius = half_w
        arch_center_y = spring_y
        for ai in range(1, arch_segments):
            angle = math.pi * ai / arch_segments  # 0 to pi
            x = -math.cos(angle) * arch_radius
            y = arch_center_y + math.sin(angle) * (apex_y - spring_y)
            noise_x = rng.gauss(0.0, 0.05) if style == "natural" else 0.0
            noise_y = rng.gauss(0.0, 0.05) if style == "natural" else 0.0
            ring.append((x + noise_x, y + noise_y, z))

        # Right side spring-line down to bottom
        for si in range(side_segs, -1, -1):
            y_frac = si / side_segs
            y = terrain_edge_height + y_frac * (spring_y - terrain_edge_height)
            noise = rng.gauss(0.0, 0.05) if style == "natural" else 0.0
            ring.append((half_w + noise, y, z))

        profile_rings.append(ring)

    # Connect consecutive rings with quad faces
    ring_size = len(profile_rings[0])
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []

    for ring in profile_rings:
        all_verts.extend(ring)

    for di in range(depth_segs):
        for ri in range(ring_size):
            ri_next = (ri + 1) % ring_size
            v0 = di * ring_size + ri
            v1 = di * ring_size + ri_next
            v2 = (di + 1) * ring_size + ri_next
            v3 = (di + 1) * ring_size + ri
            all_faces.append((v0, v1, v2, v3))

    parts.append((all_verts, all_faces))

    # Merge and return
    verts, faces = _merge_meshes(*parts)
    return _make_result(
        f"CaveEntrance_{style}",
        verts,
        faces,
        category="terrain_depth",
        style=style,
        terrain_edge_height=terrain_edge_height,
    )


# ---------------------------------------------------------------------------
# Generator 3: Biome Transition
# ---------------------------------------------------------------------------


def generate_biome_transition_mesh(
    biome_a: str = "forest",
    biome_b: str = "swamp",
    zone_width: float = 10.0,
    zone_depth: float = 20.0,
    segments: int = 12,
    seed: int = 0,
) -> MeshSpec:
    """Generate a ground-level transition strip between two biomes.

    Creates a subdivided ground plane with noise-displaced height.
    Vertex blend weights transition from 0.0 (biome_a) to 1.0 (biome_b)
    across the width axis.

    Args:
        biome_a: Name of the first biome.
        biome_b: Name of the second biome.
        zone_width: Width of the transition zone (X-axis).
        zone_depth: Depth of the transition zone (Z-axis).
        segments: Grid subdivisions in each direction.
        seed: Random seed for height noise.

    Returns:
        MeshSpec with transition zone geometry and blend weights in metadata.
    """
    rng = random.Random(seed)

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    vertex_groups: list[float] = []

    for iz in range(segments + 1):
        for ix in range(segments + 1):
            x_frac = ix / segments
            z_frac = iz / segments

            x = (x_frac - 0.5) * zone_width
            z = (z_frac - 0.5) * zone_depth

            # Noise-displaced height for uneven ground
            y = rng.gauss(0.0, 0.15) * (
                math.sin(x_frac * 3.0 * math.pi) * 0.5 + 0.5
            )

            vertices.append((x, y, z))

            # Blend weight: 0.0 at biome_a edge, 1.0 at biome_b edge
            blend = max(0.0, min(1.0, x_frac))
            vertex_groups.append(blend)

    # Quad faces
    for iz in range(segments):
        for ix in range(segments):
            row_width = segments + 1
            v0 = iz * row_width + ix
            v1 = v0 + 1
            v2 = v0 + row_width + 1
            v3 = v0 + row_width
            faces.append((v0, v1, v2, v3))

    return _make_result(
        f"BiomeTransition_{biome_a}_to_{biome_b}",
        vertices,
        faces,
        category="terrain_depth",
        biome_a=biome_a,
        biome_b=biome_b,
        vertex_groups=vertex_groups,
    )


# ---------------------------------------------------------------------------
# Generator 4: Waterfall
# ---------------------------------------------------------------------------


def generate_waterfall_mesh(
    width: float = 3.0,
    height: float = 10.0,
    steps: int = 4,
    step_depth: float = 0.5,
    pool_radius: float = 2.0,
    style: str = "rocky_cascade",
    seed: int = 0,
) -> MeshSpec:
    """Generate a stepped waterfall cascade with pool at base.

    Creates horizontal water surface planes at decreasing heights connected
    by vertical water curtain faces. A circular pool disk sits at the base.

    Args:
        width: Width of the waterfall.
        height: Total vertical height of the cascade.
        steps: Number of cascade steps.
        step_depth: Horizontal depth of each step ledge.
        pool_radius: Radius of the base pool.
        style: Visual style label.
        seed: Random seed for surface variation.

    Returns:
        MeshSpec with waterfall geometry.
    """
    rng = random.Random(seed)
    parts: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = []

    step_height = height / steps
    half_w = width / 2.0

    current_z = 0.0  # Each step pushes forward in Z

    for si in range(steps):
        y_top = height - si * step_height
        y_bottom = y_top - step_height

        # Slight random width variation per step
        w_var = rng.uniform(-0.1, 0.1)
        sw = half_w + w_var

        # Horizontal ledge surface (top of this step)
        ledge_verts: list[tuple[float, float, float]] = []
        ledge_faces: list[tuple[int, ...]] = []

        # Subdivide the ledge for non-uniform surface
        ledge_segs = 4
        for lz in range(ledge_segs + 1):
            for lx in range(ledge_segs + 1):
                x_frac = lx / ledge_segs
                z_frac = lz / ledge_segs
                x = (x_frac - 0.5) * 2.0 * sw
                z = current_z + z_frac * step_depth
                y_noise = rng.gauss(0.0, 0.02)
                ledge_verts.append((x, y_top + y_noise, z))

        for lz in range(ledge_segs):
            for lx in range(ledge_segs):
                row_w = ledge_segs + 1
                v0 = lz * row_w + lx
                v1 = v0 + 1
                v2 = v0 + row_w + 1
                v3 = v0 + row_w
                ledge_faces.append((v0, v1, v2, v3))

        parts.append((ledge_verts, ledge_faces))

        # Vertical curtain face (waterfall between this step and next)
        curtain_verts: list[tuple[float, float, float]] = []
        curtain_faces: list[tuple[int, ...]] = []
        curtain_segs = 4
        z_front = current_z + step_depth

        for cx_i in range(curtain_segs + 1):
            x_frac = cx_i / curtain_segs
            x = (x_frac - 0.5) * 2.0 * sw
            noise = rng.gauss(0.0, 0.03)
            curtain_verts.append((x, y_top + noise, z_front))
            curtain_verts.append((x, y_bottom + noise, z_front))

        for ci in range(curtain_segs):
            b = ci * 2
            curtain_faces.append((b, b + 2, b + 3, b + 1))

        parts.append((curtain_verts, curtain_faces))

        current_z += step_depth

    # Circular pool disk at the base
    pool_segs = 16
    pool_verts: list[tuple[float, float, float]] = []
    pool_faces: list[tuple[int, ...]] = []

    # Center vertex
    pool_y = height - steps * step_height  # bottom of cascade
    pool_verts.append((0.0, pool_y - 0.05, current_z + pool_radius))

    for pi in range(pool_segs):
        angle = 2.0 * math.pi * pi / pool_segs
        px = math.cos(angle) * pool_radius
        pz = current_z + pool_radius + math.sin(angle) * pool_radius
        pool_verts.append((px, pool_y - 0.05 + rng.gauss(0.0, 0.01), pz))

    # Fan triangles from center
    for pi in range(pool_segs):
        pi_next = (pi + 1) % pool_segs
        pool_faces.append((0, pi + 1, pi_next + 1))

    parts.append((pool_verts, pool_faces))

    verts, faces = _merge_meshes(*parts)
    return _make_result(
        f"Waterfall_{style}",
        verts,
        faces,
        category="terrain_depth",
        style=style,
        cascade_steps=steps,
        has_pool=True,
    )


# ---------------------------------------------------------------------------
# Generator 5: Terrain Bridge
# ---------------------------------------------------------------------------


def generate_terrain_bridge_mesh(
    start_pos: tuple[float, float, float] = (0, 0, 0),
    end_pos: tuple[float, float, float] = (10, 0, 0),
    width: float = 3.0,
    style: str = "stone_arch",
    seed: int = 0,
) -> MeshSpec:
    """Generate a terrain-aware bridge between two world positions.

    Wraps generate_bridge_mesh() with position/rotation transformation
    to connect arbitrary world-space endpoints.

    Args:
        start_pos: World position of bridge start (x, y, z).
        end_pos: World position of bridge end (x, y, z).
        width: Bridge width.
        style: Bridge style ("stone_arch", "rope", "drawbridge").
        seed: Random seed (reserved for future noise variation).

    Returns:
        MeshSpec with bridge geometry transformed to world position.
    """
    sx, sy, sz = start_pos
    ex, ey, ez = end_pos

    dx = ex - sx
    dy = ey - sy
    dz = ez - sz

    # Compute span (horizontal distance, ignoring vertical)
    horizontal_dist = math.sqrt(dx * dx + dz * dz)
    span = max(horizontal_dist, 1.0)  # avoid zero-length bridge

    # Get base bridge mesh (centered at origin, spanning along Z axis)
    base = generate_bridge_mesh(span=span, width=width, style=style)

    # Compute rotation angle in XZ plane (yaw)
    yaw = math.atan2(dx, dz)  # angle from Z-axis toward X-axis
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)

    # Midpoint offset
    mid_x = (sx + ex) / 2.0
    mid_y = (sy + ey) / 2.0
    mid_z = (sz + ez) / 2.0

    # Transform vertices: rotate around Y-axis then translate
    transformed_verts: list[tuple[float, float, float]] = []
    for vx, vy, vz in base["vertices"]:
        # The base bridge spans along Z from -span/2 to +span/2
        # Rotate (vx, vz) by yaw around Y-axis
        rx = vx * cos_yaw + vz * sin_yaw
        rz = -vx * sin_yaw + vz * cos_yaw

        # Translate to midpoint
        tx = rx + mid_x
        ty = vy + mid_y
        tz = rz + mid_z

        transformed_verts.append((tx, ty, tz))

    return _make_result(
        f"TerrainBridge_{style}",
        transformed_verts,
        base["faces"],
        category="terrain_depth",
        style=style,
        start_pos=start_pos,
        end_pos=end_pos,
        span=span,
    )


# ---------------------------------------------------------------------------
# Cliff Edge Detection -- find steep terrain regions for overlay placement
# ---------------------------------------------------------------------------


def detect_cliff_edges(
    heightmap: np.ndarray,
    slope_threshold_deg: float = 60.0,
    min_cluster_size: int = 4,
    terrain_size: float = 100.0,
) -> list[dict[str, Any]]:
    """Find terrain regions where slope exceeds threshold for cliff overlay.

    Pure-logic function. Analyzes the heightmap gradient to locate steep
    cliff regions, clusters adjacent steep cells, and returns placement
    parameters for cliff face mesh overlays.

    Args:
        heightmap: 2D numpy array of height values (normalized or world-scale).
        slope_threshold_deg: Minimum slope in degrees to qualify as cliff.
        min_cluster_size: Minimum number of connected steep cells to form
            a cliff placement (filters noise).
        terrain_size: World-space size of the terrain (for coordinate mapping).

    Returns:
        List of cliff placement dicts, each containing:
          - position: [x, y, z] world-space center of the cliff region
          - rotation: [rx, ry, rz] Euler angles for cliff face orientation
          - width: Estimated width of the cliff face
          - height: Estimated vertical extent of the cliff
          - cell_count: Number of steep cells in this cluster
    """
    from ._terrain_noise import compute_slope_map

    slope_map = compute_slope_map(heightmap)
    rows, cols = heightmap.shape

    # Binary mask of steep cells
    cliff_mask = slope_map > slope_threshold_deg

    # Connected component labeling using simple flood-fill
    labels = np.full((rows, cols), -1, dtype=np.int32)
    label_id = 0

    for r in range(rows):
        for c in range(cols):
            if cliff_mask[r, c] and labels[r, c] < 0:
                # Flood-fill from this cell
                stack = [(r, c)]
                cluster: list[tuple[int, int]] = []
                while stack:
                    cr, cc = stack.pop()
                    if (
                        0 <= cr < rows
                        and 0 <= cc < cols
                        and cliff_mask[cr, cc]
                        and labels[cr, cc] < 0
                    ):
                        labels[cr, cc] = label_id
                        cluster.append((cr, cc))
                        # 4-connected neighbors
                        stack.append((cr - 1, cc))
                        stack.append((cr + 1, cc))
                        stack.append((cr, cc - 1))
                        stack.append((cr, cc + 1))
                label_id += 1

    # Extract placement info for each qualifying cluster
    placements: list[dict[str, Any]] = []
    cell_to_world = terrain_size / max(rows, cols)

    # TERR-001: Compute gradient once before loop (not per-cluster)
    dy, dx = np.gradient(heightmap)

    for lid in range(label_id):
        cells = np.argwhere(labels == lid)
        if len(cells) < min_cluster_size:
            continue

        # Bounding box in grid coordinates
        r_min, c_min = cells.min(axis=0)
        r_max, c_max = cells.max(axis=0)

        # Center position in world space
        r_center = (r_min + r_max) / 2.0
        c_center = (c_min + c_max) / 2.0

        # Map to world coordinates: grid center -> world center
        wx = (c_center / cols - 0.5) * terrain_size
        wy = (r_center / rows - 0.5) * terrain_size

        # Height at center
        ri = int(np.clip(r_center, 0, rows - 1))
        ci = int(np.clip(c_center, 0, cols - 1))
        wz = float(heightmap[ri, ci])

        # Gradient direction at center (for rotation)
        grad_x = float(dx[ri, ci])
        grad_y = float(dy[ri, ci])
        face_angle = math.atan2(grad_y, grad_x)

        # Cliff dimensions from cluster extent
        width = (c_max - c_min + 1) * cell_to_world
        height_range = float(
            heightmap[cells[:, 0], cells[:, 1]].max()
            - heightmap[cells[:, 0], cells[:, 1]].min()
        )
        # Minimum cliff height based on cell count
        cliff_height = max(height_range * terrain_size * 0.1, 2.0)

        placements.append({
            "position": [wx, wy, wz],
            "rotation": [0.0, 0.0, face_angle],
            "width": max(width, 2.0),
            "height": cliff_height,
            "cell_count": len(cells),
        })

    return placements
