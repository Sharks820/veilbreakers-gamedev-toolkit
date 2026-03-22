"""UDIM multi-tile UV and trim sheet support for VeilBreakers.

Pure-logic module (NO bpy imports). Provides:
- UDIM_LAYOUTS: predefined tile configurations for hero characters and NPCs
- compute_udim_tile_assignment: assign faces to UDIM tiles based on material regions
- compute_trim_sheet_uvs: project face UVs onto horizontal strips of a trim sheet

All functions work with vertex position data and face index lists.
Fulfils character texture quality requirements (Task #52).
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# UDIM layout presets
# ---------------------------------------------------------------------------

UDIM_LAYOUTS: dict[str, dict[str, Any]] = {
    "hero_character": {
        "tiles": {
            1001: {"name": "head", "coverage": 0.40},
            1002: {"name": "body", "coverage": 0.35},
            1003: {"name": "arms_hands", "coverage": 0.15},
            1004: {"name": "legs_feet", "coverage": 0.10},
        },
        "resolution_per_tile": 4096,
    },
    "standard_npc": {
        "tiles": {
            1001: {"name": "body_head", "coverage": 0.60},
            1002: {"name": "extremities", "coverage": 0.40},
        },
        "resolution_per_tile": 2048,
    },
    "boss_character": {
        "tiles": {
            1001: {"name": "head", "coverage": 0.30},
            1002: {"name": "upper_body", "coverage": 0.25},
            1003: {"name": "lower_body", "coverage": 0.20},
            1004: {"name": "arms_hands", "coverage": 0.15},
            1005: {"name": "legs_feet", "coverage": 0.10},
        },
        "resolution_per_tile": 4096,
    },
    "prop": {
        "tiles": {
            1001: {"name": "main", "coverage": 0.70},
            1002: {"name": "detail", "coverage": 0.30},
        },
        "resolution_per_tile": 2048,
    },
}

# ---------------------------------------------------------------------------
# Region name -> height fraction ranges (for auto-assignment by Y position)
# Assumes a ~1.8m character standing upright, Y-up
# ---------------------------------------------------------------------------

_DEFAULT_REGION_Y_RANGES: dict[str, tuple[float, float]] = {
    "head": (0.87, 1.0),
    "body": (0.47, 0.87),
    "body_head": (0.47, 1.0),
    "upper_body": (0.60, 0.87),
    "lower_body": (0.47, 0.60),
    "arms_hands": (0.35, 0.75),
    "extremities": (0.0, 0.47),
    "legs_feet": (0.0, 0.47),
    "main": (0.3, 1.0),
    "detail": (0.0, 0.3),
}


def _face_centroid(
    vertices: list[tuple[float, float, float]],
    face: tuple[int, ...],
) -> tuple[float, float, float]:
    """Compute the centroid of a face from its vertex indices."""
    n = len(face)
    if n == 0:
        return (0.0, 0.0, 0.0)
    sx = sy = sz = 0.0
    for vi in face:
        v = vertices[vi]
        sx += v[0]
        sy += v[1]
        sz += v[2]
    return (sx / n, sy / n, sz / n)


def compute_udim_tile_assignment(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    material_regions: dict[str, list[int]] | None = None,
    layout_name: str = "hero_character",
) -> dict[str, Any]:
    """Assign faces to UDIM tiles based on material regions or auto-detection.

    If material_regions is provided, it maps region names (matching tile names
    in the layout) to lists of face indices. Otherwise, faces are auto-assigned
    based on their centroid Y position relative to the mesh bounding box.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face tuples (vertex indices).
        material_regions: Optional mapping of region_name -> [face_indices].
        layout_name: Which UDIM layout preset to use.

    Returns:
        Dict with:
        - layout_name: str
        - tile_assignments: dict[int, list[int]] -- tile_id -> face indices
        - face_to_tile: dict[int, int] -- face_index -> tile_id
        - coverage_actual: dict[int, float] -- actual face fraction per tile
        - unassigned: list[int] -- faces not matching any region
        - tile_count: int
        - resolution_per_tile: int
    """
    if layout_name not in UDIM_LAYOUTS:
        return {
            "layout_name": layout_name,
            "tile_assignments": {},
            "face_to_tile": {},
            "coverage_actual": {},
            "unassigned": list(range(len(faces))),
            "tile_count": 0,
            "resolution_per_tile": 0,
            "error": f"Unknown layout: '{layout_name}'. "
                     f"Valid: {sorted(UDIM_LAYOUTS.keys())}",
        }

    layout = UDIM_LAYOUTS[layout_name]
    tiles = layout["tiles"]
    resolution = layout["resolution_per_tile"]

    # Build name -> tile_id lookup
    name_to_tile: dict[str, int] = {}
    for tile_id, info in tiles.items():
        name_to_tile[info["name"]] = tile_id

    tile_assignments: dict[int, list[int]] = {tid: [] for tid in tiles}
    face_to_tile: dict[int, int] = {}
    unassigned: list[int] = []

    if material_regions:
        # Use explicit region assignments
        assigned_faces: set[int] = set()
        for region_name, face_indices in material_regions.items():
            tile_id = name_to_tile.get(region_name)
            if tile_id is None:
                # Try partial match
                for tname, tid in name_to_tile.items():
                    if region_name in tname or tname in region_name:
                        tile_id = tid
                        break
            if tile_id is not None:
                for fi in face_indices:
                    if 0 <= fi < len(faces):
                        tile_assignments[tile_id].append(fi)
                        face_to_tile[fi] = tile_id
                        assigned_faces.add(fi)

        unassigned = [i for i in range(len(faces)) if i not in assigned_faces]
    else:
        # Auto-assign by Y position
        if not vertices:
            return {
                "layout_name": layout_name,
                "tile_assignments": tile_assignments,
                "face_to_tile": face_to_tile,
                "coverage_actual": {},
                "unassigned": [],
                "tile_count": len(tiles),
                "resolution_per_tile": resolution,
            }

        ys = [v[1] for v in vertices]
        min_y = min(ys)
        max_y = max(ys)
        height = max_y - min_y
        if height < 1e-8:
            height = 1.0

        for fi, face in enumerate(faces):
            centroid = _face_centroid(vertices, face)
            y_frac = (centroid[1] - min_y) / height

            # Determine X position for arm detection
            centroid_x = centroid[0]
            xs = [vertices[vi][0] for vi in face]
            center_x = sum(v[0] for v in vertices) / max(len(vertices), 1)

            assigned = False
            # Check each tile region
            for tile_id, info in tiles.items():
                tile_name = info["name"]
                y_range = _DEFAULT_REGION_Y_RANGES.get(tile_name)
                if y_range is None:
                    continue

                y_lo, y_hi = y_range

                # Arms check: lateral position
                if "arm" in tile_name:
                    lateral_dist = abs(centroid_x - center_x)
                    body_half_width = (max(v[0] for v in vertices) -
                                       min(v[0] for v in vertices)) / 2.0
                    if lateral_dist < body_half_width * 0.4:
                        continue  # too central for arms

                if y_lo <= y_frac <= y_hi:
                    tile_assignments[tile_id].append(fi)
                    face_to_tile[fi] = tile_id
                    assigned = True
                    break

            if not assigned:
                # Fallback: assign to the tile with the broadest coverage
                best_tile = max(tiles, key=lambda t: tiles[t]["coverage"])
                tile_assignments[best_tile].append(fi)
                face_to_tile[fi] = best_tile

    # Compute actual coverage fractions
    total_faces = max(len(faces), 1)
    coverage_actual: dict[int, float] = {}
    for tid in tiles:
        coverage_actual[tid] = len(tile_assignments[tid]) / total_faces

    return {
        "layout_name": layout_name,
        "tile_assignments": tile_assignments,
        "face_to_tile": face_to_tile,
        "coverage_actual": coverage_actual,
        "unassigned": unassigned,
        "tile_count": len(tiles),
        "resolution_per_tile": resolution,
    }


# ---------------------------------------------------------------------------
# Trim sheet UV projection
# ---------------------------------------------------------------------------

def compute_trim_sheet_uvs(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    strip_index: int,
    total_strips: int = 8,
) -> list[dict[str, Any]]:
    """Project face UVs onto a specific horizontal strip of a trim sheet.

    A trim sheet is divided into horizontal strips (rows). Each strip contains
    a different material/detail (e.g., strip 0 = molding, 1 = cornice, etc.).
    This function projects the given faces' UVs into the specified strip region.

    The UV mapping uses a planar projection based on the face's local bounding
    box within the strip's V range: [strip_v_min, strip_v_max].

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face tuples (vertex indices).
        strip_index: Which strip (0 = top, total_strips-1 = bottom).
        total_strips: Number of horizontal strips in the trim sheet.

    Returns:
        List of dicts per face, each with:
        - face_index: int
        - uvs: list of (u, v) per vertex in the face
        - strip_index: int
        - strip_name: str (descriptive name)
    """
    total_strips = max(1, total_strips)
    strip_index = max(0, min(strip_index, total_strips - 1))

    strip_names = [
        "molding", "cornice", "base_trim", "wall_panel",
        "floor_border", "column_wrap", "arch_detail", "frieze",
    ]
    # Extend names if more strips needed
    while len(strip_names) < total_strips:
        strip_names.append(f"strip_{len(strip_names)}")

    strip_height = 1.0 / total_strips
    strip_v_min = 1.0 - (strip_index + 1) * strip_height
    strip_v_max = 1.0 - strip_index * strip_height

    if not vertices or not faces:
        return []

    # Compute global bounding box for U mapping
    all_face_verts: set[int] = set()
    for face in faces:
        for vi in face:
            all_face_verts.add(vi)

    if not all_face_verts:
        return []

    face_vert_list = list(all_face_verts)
    xs = [vertices[vi][0] for vi in face_vert_list]
    ys = [vertices[vi][1] for vi in face_vert_list]
    zs = [vertices[vi][2] for vi in face_vert_list]

    # Use the widest axis pair for planar projection
    x_range = max(xs) - min(xs)
    y_range = max(ys) - min(ys)
    z_range = max(zs) - min(zs)

    # Pick primary (U) and secondary (V within strip) axes
    ranges = [(x_range, 0, "x"), (y_range, 1, "y"), (z_range, 2, "z")]
    ranges.sort(key=lambda r: r[0], reverse=True)

    u_axis = ranges[0][1]
    v_axis = ranges[1][1]

    u_min = min(vertices[vi][u_axis] for vi in face_vert_list)
    u_max = max(vertices[vi][u_axis] for vi in face_vert_list)
    v_min_3d = min(vertices[vi][v_axis] for vi in face_vert_list)
    v_max_3d = max(vertices[vi][v_axis] for vi in face_vert_list)

    u_span = u_max - u_min
    v_span_3d = v_max_3d - v_min_3d
    if u_span < 1e-8:
        u_span = 1.0
    if v_span_3d < 1e-8:
        v_span_3d = 1.0

    result: list[dict[str, Any]] = []
    for fi, face in enumerate(faces):
        face_uvs: list[tuple[float, float]] = []
        for vi in face:
            vert = vertices[vi]
            # Normalize to [0, 1] in the U direction
            u = (vert[u_axis] - u_min) / u_span

            # Normalize to [strip_v_min, strip_v_max] in V
            v_norm = (vert[v_axis] - v_min_3d) / v_span_3d
            v = strip_v_min + v_norm * strip_height

            # Clamp
            u = max(0.0, min(1.0, u))
            v = max(strip_v_min, min(strip_v_max, v))

            face_uvs.append((u, v))

        result.append({
            "face_index": fi,
            "uvs": face_uvs,
            "strip_index": strip_index,
            "strip_name": strip_names[strip_index],
        })

    return result
