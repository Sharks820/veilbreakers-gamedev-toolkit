"""UV analysis, unwrapping, packing, lightmap, and density equalization handlers.

Provides 9 handler functions for the blender_uv MCP compound tool:
  handle_analyze_uv          - UV quality analysis (stretch, overlap, density, islands, seams)
  handle_unwrap_xatlas       - High-quality UV unwrap via xatlas library
  handle_unwrap_blender      - Native Blender UV unwrap (smart_project or angle_based)
  handle_pack_islands        - UV island packing within 0-1 space
  handle_generate_lightmap_uv - Generate UV2 layer for Unity lightmaps
  handle_equalize_density    - Equalize texel density across all UV islands
  handle_export_uv_layout    - Export UV wireframe as PNG image
  handle_set_active_uv_layer - Switch active UV layer by name
  handle_ensure_xatlas       - Install xatlas into Blender Python if missing

Pure math helpers (_polygon_area_2d, etc.) are testable without Blender.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
import uuid
from collections import deque

import bpy
import bmesh

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Pure math helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _polygon_area_2d(coords: list) -> float:
    """Compute 2D polygon area using the shoelace formula.

    Args:
        coords: List of objects with .x and .y attributes (mathutils.Vector,
                 or any compatible 2D point).

    Returns:
        Absolute area of the polygon. Returns 0.0 for fewer than 3 vertices.
    """
    n = len(coords)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i].x * coords[j].y
        area -= coords[j].x * coords[i].y
    return abs(area) / 2.0


# ---------------------------------------------------------------------------
# UV island / connectivity helpers (require bmesh + uv_layer)
# ---------------------------------------------------------------------------


def _faces_share_uv_edge(f1, f2, edge, uv_layer) -> bool:
    """Check if two faces share a UV-connected edge (same UV coords at shared verts)."""
    uv1 = {}
    for loop in f1.loops:
        if loop.vert in edge.verts:
            uv1[loop.vert.index] = tuple(round(c, 6) for c in loop[uv_layer].uv)
    uv2 = {}
    for loop in f2.loops:
        if loop.vert in edge.verts:
            uv2[loop.vert.index] = tuple(round(c, 6) for c in loop[uv_layer].uv)
    for vi in uv1:
        if vi in uv2 and uv1[vi] != uv2[vi]:
            return False
    return True


def _count_uv_islands(bm, uv_layer) -> int:
    """Count connected UV islands using BFS flood fill.

    Seams and UV-discontinuities break island connectivity.
    """
    visited: set[int] = set()
    island_count = 0
    for face in bm.faces:
        if face.index in visited:
            continue
        island_count += 1
        queue = deque([face])
        while queue:
            f = queue.popleft()
            if f.index in visited:
                continue
            visited.add(f.index)
            for edge in f.edges:
                if edge.seam:
                    continue
                for linked_face in edge.link_faces:
                    if linked_face.index not in visited:
                        if _faces_share_uv_edge(f, linked_face, edge, uv_layer):
                            queue.append(linked_face)
    return island_count


def _get_island_faces(bm, uv_layer) -> list[list]:
    """Return list of face groups, one list per UV island."""
    visited: set[int] = set()
    islands: list[list] = []
    for face in bm.faces:
        if face.index in visited:
            continue
        island: list = []
        queue = deque([face])
        while queue:
            f = queue.popleft()
            if f.index in visited:
                continue
            visited.add(f.index)
            island.append(f)
            for edge in f.edges:
                if edge.seam:
                    continue
                for linked_face in edge.link_faces:
                    if linked_face.index not in visited:
                        if _faces_share_uv_edge(f, linked_face, edge, uv_layer):
                            queue.append(linked_face)
        islands.append(island)
    return islands


def _count_uv_overlaps(bm, uv_layer) -> int:
    """Detect UV overlaps using spatial grid hash.

    For meshes >10k faces, samples 10% and extrapolates. Returns overlap count.
    """
    faces = list(bm.faces)
    total_faces = len(faces)
    sampled = False

    if total_faces > 10000:
        # Sample 10% evenly spaced
        step = total_faces // (total_faces // 10)
        faces = faces[::step]
        sampled = True

    grid_size = 100
    grid: dict[tuple[int, int], list[int]] = {}

    overlap_count = 0
    for face in faces:
        uv_coords = [loop[uv_layer].uv for loop in face.loops]
        # Bounding box in UV space
        min_u = min(c.x for c in uv_coords)
        max_u = max(c.x for c in uv_coords)
        min_v = min(c.y for c in uv_coords)
        max_v = max(c.y for c in uv_coords)

        cell_min_u = int(min_u * grid_size)
        cell_max_u = int(max_u * grid_size)
        cell_min_v = int(min_v * grid_size)
        cell_max_v = int(max_v * grid_size)

        cells = set()
        for cu in range(cell_min_u, cell_max_u + 1):
            for cv in range(cell_min_v, cell_max_v + 1):
                cells.add((cu, cv))

        for cell in cells:
            if cell in grid:
                for existing_idx in grid[cell]:
                    if existing_idx != face.index:
                        overlap_count += 1
                        break
                grid[cell].append(face.index)
            else:
                grid[cell] = [face.index]

    if sampled:
        overlap_count = int(overlap_count * (total_faces / len(faces)))

    return overlap_count


# ---------------------------------------------------------------------------
# Handler 1: UV Analysis (UV-01)
# ---------------------------------------------------------------------------


def handle_analyze_uv(params: dict) -> dict:
    """Comprehensive UV quality analysis.

    Returns island count, stretch metrics, texel density stats, overlap count,
    and seam information.
    """
    name = params.get("object_name")
    texture_size = params.get("texture_size", 1024)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        bm.free()
        return {"has_uvs": False, "error": "No UV layer found"}

    # Per-face metrics
    stretch_values: list[float] = []
    texel_densities: list[float] = []
    total_3d_area = 0.0
    total_uv_area = 0.0

    for face in bm.faces:
        face_3d_area = face.calc_area()
        total_3d_area += face_3d_area

        uv_coords = [loop[uv_layer].uv.copy() for loop in face.loops]
        uv_area = _polygon_area_2d(uv_coords)
        total_uv_area += uv_area

        # Stretch: ratio of UV area to 3D area (1.0 = no distortion)
        if face_3d_area > 1e-8 and uv_area > 1e-8:
            stretch = uv_area / face_3d_area
            stretch_values.append(stretch)
        else:
            stretch_values.append(0.0)

        # Texel density: pixels per world unit
        if face_3d_area > 1e-8:
            td = math.sqrt(uv_area / face_3d_area) * texture_size
            texel_densities.append(td)

    # Island counting
    island_count = _count_uv_islands(bm, uv_layer)

    # Overlap detection
    overlap_count = _count_uv_overlaps(bm, uv_layer)

    # Seam edges
    seam_edges = sum(1 for e in bm.edges if e.seam)

    bm.free()

    # Compute statistics
    avg_td = sum(texel_densities) / max(len(texel_densities), 1)
    min_td = min(texel_densities) if texel_densities else 0.0
    max_td = max(texel_densities) if texel_densities else 0.0
    td_variance = (max_td - min_td) / max(avg_td, 1e-8)

    # Stretch deviation from median
    if stretch_values:
        sorted_stretch = sorted(stretch_values)
        median_stretch = sorted_stretch[len(sorted_stretch) // 2]
        stretch_deviations = [
            abs(s - median_stretch) / max(median_stretch, 1e-8)
            for s in stretch_values
        ]
        avg_stretch_deviation = sum(stretch_deviations) / len(stretch_deviations)
    else:
        avg_stretch_deviation = 0.0

    return {
        "object_name": name,
        "has_uvs": True,
        "island_count": island_count,
        "overlap_count": overlap_count,
        "seam_edge_count": seam_edges,
        "total_3d_area": round(total_3d_area, 4),
        "total_uv_area": round(total_uv_area, 6),
        "uv_coverage": round(total_uv_area, 4),
        "texel_density": {
            "average": round(avg_td, 1),
            "min": round(min_td, 1),
            "max": round(max_td, 1),
            "variance_ratio": round(td_variance, 2),
            "texture_size": texture_size,
        },
        "stretch": {
            "average_deviation": round(avg_stretch_deviation, 3),
            "faces_analyzed": len(stretch_values),
        },
    }


# ---------------------------------------------------------------------------
# Handler 2: xatlas UV Unwrap (UV-02)
# ---------------------------------------------------------------------------


def handle_unwrap_xatlas(params: dict) -> dict:
    """UV unwrap using xatlas library for high-quality parameterization."""
    try:
        import xatlas
    except ImportError:
        raise RuntimeError(
            "xatlas not installed in Blender Python. "
            "Use the 'ensure_xatlas' action first to install it."
        )

    import numpy as np

    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    mesh = obj.data

    # Extract geometry via numpy
    vert_count = len(mesh.vertices)
    loop_count = len(mesh.loops)

    vertices = [0.0] * (vert_count * 3)
    mesh.vertices.foreach_get("co", vertices)
    vertices = np.array(vertices, dtype=np.float32).reshape(-1, 3)

    normals = [0.0] * (vert_count * 3)
    mesh.vertices.foreach_get("normal", normals)
    normals = np.array(normals, dtype=np.float32).reshape(-1, 3)

    # Get loop vertex indices
    loop_indices = [0] * loop_count
    mesh.loops.foreach_get("vertex_index", loop_indices)

    # Fan-triangulate polygons, tracking which original polygon each tri came from
    triangles: list[list[int]] = []
    tri_to_poly: list[int] = []
    for poly in mesh.polygons:
        verts = [loop_indices[li] for li in poly.loop_indices]
        for i in range(1, len(verts) - 1):
            triangles.append([verts[0], verts[i], verts[i + 1]])
            tri_to_poly.append(poly.index)

    faces = np.array(triangles, dtype=np.uint32)

    # Create atlas
    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices, faces, normals)

    chart_options = xatlas.ChartOptions()
    pack_options = xatlas.PackOptions()

    if params.get("max_chart_area") is not None:
        chart_options.max_chart_area = params["max_chart_area"]
    if params.get("normal_deviation_weight") is not None:
        chart_options.normal_deviation_weight = params["normal_deviation_weight"]
    if params.get("max_iterations") is not None:
        chart_options.max_iterations = params["max_iterations"]

    pack_options.padding = params.get("padding", 2)
    pack_options.resolution = params.get("resolution", 1024)
    pack_options.bilinear = params.get("bilinear", True)
    pack_options.rotate_charts = params.get("rotate_charts", True)

    atlas.generate(chart_options, pack_options)

    vmapping, indices, uvs = atlas[0]

    # Write UVs back to Blender mesh via bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        uv_layer = bm.loops.layers.uv.new("UVMap")

    # Build per-original-vertex UV mapping.
    # xatlas may split vertices at seams (vmapping maps new -> original).
    # For seam vertices, multiple new indices map to the same original vertex
    # but with different UVs. We build a dict keyed by (original_vert_idx, tri_idx)
    # to handle this correctly via the tri_to_poly mapping.
    #
    # Strategy: for each xatlas triangle, assign UVs to the corresponding
    # original polygon's loops by matching vertex indices.
    poly_vert_uv: dict[tuple[int, int], tuple[float, float]] = {}
    # MISC-007: also build a plain vert->uv fallback dict (first UV seen per vertex)
    vert_uv_fallback: dict[int, tuple[float, float]] = {}
    for tri_idx in range(len(indices) // 3):
        poly_idx = tri_to_poly[tri_idx]
        for k in range(3):
            new_vert_idx = indices[tri_idx * 3 + k]
            orig_vert_idx = int(vmapping[new_vert_idx])
            uv_val = (float(uvs[new_vert_idx][0]), float(uvs[new_vert_idx][1]))
            poly_vert_uv[(poly_idx, orig_vert_idx)] = uv_val
            vert_uv_fallback.setdefault(orig_vert_idx, uv_val)

    # Apply UVs to bmesh loops
    for face in bm.faces:
        for loop in face.loops:
            key = (face.index, loop.vert.index)
            if key in poly_vert_uv:
                loop[uv_layer].uv = poly_vert_uv[key]
            else:
                # MISC-007: fallback via plain vert index lookup (fixed index math)
                uv_fb = vert_uv_fallback.get(loop.vert.index)
                if uv_fb is not None:
                    loop[uv_layer].uv = uv_fb

    bm.to_mesh(mesh)
    mesh.update()
    bm.free()

    chart_count = -1
    if hasattr(atlas, "chartCount"):
        chart_count = atlas.chartCount
    elif hasattr(atlas, "chart_count"):
        chart_count = atlas.chart_count

    return {
        "object_name": name,
        "atlas_width": atlas.width,
        "atlas_height": atlas.height,
        "chart_count": chart_count,
        "uv_layer": "UVMap",
    }


# ---------------------------------------------------------------------------
# Handler 3: Blender Native UV Unwrap (UV-02 fallback)
# ---------------------------------------------------------------------------


def handle_unwrap_blender(params: dict) -> dict:
    """UV unwrap using Blender's built-in methods (smart_project or angle_based)."""
    name = params.get("object_name")
    method = params.get("method", "smart_project")
    angle_limit = params.get("angle_limit", 66.0)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    override = get_3d_context_override()
    if not override:
        raise RuntimeError("No 3D viewport for UV unwrap")

    old_active = bpy.context.view_layer.objects.active
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        with bpy.context.temp_override(**override, active_object=obj):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")

            if method == "smart_project":
                bpy.ops.uv.smart_project(
                    angle_limit=math.radians(angle_limit),
                    island_margin=0.001,
                )
            else:
                bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.001)

            bpy.ops.object.mode_set(mode="OBJECT")
    finally:
        if old_active:
            bpy.context.view_layer.objects.active = old_active

    return {
        "object_name": name,
        "method": method,
        "uv_layer": obj.data.uv_layers.active.name if obj.data.uv_layers.active else "UVMap",
    }


# ---------------------------------------------------------------------------
# Handler 4: Pack UV Islands (UV-03)
# ---------------------------------------------------------------------------


def handle_pack_islands(params: dict) -> dict:
    """Pack UV islands within 0-1 UV space with configurable margin."""
    name = params.get("object_name")
    margin = params.get("margin", 0.001)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    override = get_3d_context_override()
    if not override:
        raise RuntimeError("No 3D viewport for UV pack")

    old_active = bpy.context.view_layer.objects.active
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        with bpy.context.temp_override(**override, active_object=obj):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.pack_islands(margin=margin)
            bpy.ops.object.mode_set(mode="OBJECT")
    finally:
        if old_active:
            bpy.context.view_layer.objects.active = old_active

    return {
        "object_name": name,
        "margin": margin,
        "packed": True,
    }


# ---------------------------------------------------------------------------
# Handler 5: Lightmap UV Generation (UV-04)
# ---------------------------------------------------------------------------


def handle_generate_lightmap_uv(params: dict) -> dict:
    """Generate a second UV layer (UV2) for Unity lightmaps via xatlas.

    Creates UV2 with no overlaps and lightmap-appropriate padding,
    preserving the primary UV1 layer.
    """
    try:
        import xatlas
    except ImportError:
        raise RuntimeError(
            "xatlas not installed in Blender Python. "
            "Use the 'ensure_xatlas' action first to install it."
        )

    import numpy as np

    name = params.get("object_name")
    padding = params.get("padding", 4)
    resolution = params.get("resolution", 1024)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    mesh = obj.data

    # Extract geometry
    vert_count = len(mesh.vertices)
    loop_count = len(mesh.loops)

    vertices = [0.0] * (vert_count * 3)
    mesh.vertices.foreach_get("co", vertices)
    vertices = np.array(vertices, dtype=np.float32).reshape(-1, 3)

    normals = [0.0] * (vert_count * 3)
    mesh.vertices.foreach_get("normal", normals)
    normals = np.array(normals, dtype=np.float32).reshape(-1, 3)

    loop_indices = [0] * loop_count
    mesh.loops.foreach_get("vertex_index", loop_indices)

    triangles: list[list[int]] = []
    tri_to_poly: list[int] = []
    for poly in mesh.polygons:
        verts = [loop_indices[li] for li in poly.loop_indices]
        for i in range(1, len(verts) - 1):
            triangles.append([verts[0], verts[i], verts[i + 1]])
            tri_to_poly.append(poly.index)

    faces = np.array(triangles, dtype=np.uint32)

    # Create atlas with lightmap settings
    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices, faces, normals)

    chart_options = xatlas.ChartOptions()
    pack_options = xatlas.PackOptions()
    pack_options.padding = padding
    pack_options.resolution = resolution
    pack_options.bilinear = True
    pack_options.rotate_charts = True

    atlas.generate(chart_options, pack_options)

    vmapping, indices, uvs = atlas[0]

    # Write UVs to UV2 layer via bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Create or get UV2 layer
    uv2_layer = bm.loops.layers.uv.get("UV2")
    if not uv2_layer:
        uv2_layer = bm.loops.layers.uv.new("UV2")

    # Build per-polygon UV mapping (same approach as handle_unwrap_xatlas)
    poly_vert_uv: dict[tuple[int, int], tuple[float, float]] = {}
    for tri_idx in range(len(indices) // 3):
        poly_idx = tri_to_poly[tri_idx]
        for k in range(3):
            new_vert_idx = indices[tri_idx * 3 + k]
            orig_vert_idx = int(vmapping[new_vert_idx])
            uv_val = (float(uvs[new_vert_idx][0]), float(uvs[new_vert_idx][1]))
            poly_vert_uv[(poly_idx, orig_vert_idx)] = uv_val

    # Write to UV2 only (preserve UV1)
    for face in bm.faces:
        for loop in face.loops:
            key = (face.index, loop.vert.index)
            if key in poly_vert_uv:
                loop[uv2_layer].uv = poly_vert_uv[key]

    bm.to_mesh(mesh)
    mesh.update()
    bm.free()

    return {
        "object_name": name,
        "uv_layer": "UV2",
        "atlas_width": atlas.width,
        "atlas_height": atlas.height,
        "padding": padding,
    }


# ---------------------------------------------------------------------------
# Handler 6: Texel Density Equalization (UV-05)
# ---------------------------------------------------------------------------


def handle_equalize_density(params: dict) -> dict:
    """Equalize texel density across all UV islands.

    Scales each island's UVs so all islands have the same texel density,
    then repacks.
    """
    name = params.get("object_name")
    target_density = params.get("target_density")
    texture_size = params.get("texture_size", 1024)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        bm.free()
        raise ValueError(f"No UV layer found on '{name}'")

    islands = _get_island_faces(bm, uv_layer)

    # Calculate per-island texel density
    island_densities: list[float] = []
    island_data: list[dict] = []

    for island_faces in islands:
        total_3d = 0.0
        total_uv = 0.0
        for face in island_faces:
            total_3d += face.calc_area()
            uv_coords = [loop[uv_layer].uv.copy() for loop in face.loops]
            total_uv += _polygon_area_2d(uv_coords)

        if total_3d > 1e-8 and total_uv > 1e-8:
            density = math.sqrt(total_uv / total_3d) * texture_size
        else:
            density = 0.0

        island_densities.append(density)
        island_data.append({
            "faces": island_faces,
            "density": density,
            "uv_area": total_uv,
            "3d_area": total_3d,
        })

    # Determine target density
    nonzero_densities = [d for d in island_densities if d > 0]
    if not nonzero_densities:
        bm.free()
        return {"object_name": name, "error": "No valid UV islands to equalize"}

    if target_density is None:
        sorted_densities = sorted(nonzero_densities)
        target_density = sorted_densities[len(sorted_densities) // 2]

    before_variance = (
        (max(nonzero_densities) - min(nonzero_densities))
        / max(sum(nonzero_densities) / len(nonzero_densities), 1e-8)
    )

    # Scale each island's UVs to match target density
    for data in island_data:
        if data["density"] < 1e-8:
            continue
        scale_factor = target_density / data["density"]
        if abs(scale_factor - 1.0) < 0.001:
            continue

        # Compute island UV center
        all_uvs = []
        for face in data["faces"]:
            for loop in face.loops:
                all_uvs.append(loop[uv_layer].uv.copy())

        if not all_uvs:
            continue

        center_u = sum(uv.x for uv in all_uvs) / len(all_uvs)
        center_v = sum(uv.y for uv in all_uvs) / len(all_uvs)

        # Scale around center
        for face in data["faces"]:
            for loop in face.loops:
                uv = loop[uv_layer].uv
                uv.x = center_u + (uv.x - center_u) * scale_factor
                uv.y = center_v + (uv.y - center_v) * scale_factor

    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()

    # Repack islands via operator
    override = get_3d_context_override()
    if override:
        old_active = bpy.context.view_layer.objects.active
        try:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            with bpy.context.temp_override(**override, active_object=obj):
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.pack_islands(margin=0.001)
                bpy.ops.object.mode_set(mode="OBJECT")
        finally:
            if old_active:
                bpy.context.view_layer.objects.active = old_active

    # Recalculate after density
    after_densities = []
    bm2 = bmesh.new()
    bm2.from_mesh(obj.data)
    bm2.faces.ensure_lookup_table()
    bm2.edges.ensure_lookup_table()
    uv_layer2 = bm2.loops.layers.uv.active
    if uv_layer2:
        for island_faces in _get_island_faces(bm2, uv_layer2):
            total_3d = sum(f.calc_area() for f in island_faces)
            total_uv = sum(
                _polygon_area_2d([l[uv_layer2].uv.copy() for l in f.loops])
                for f in island_faces
            )
            if total_3d > 1e-8 and total_uv > 1e-8:
                after_densities.append(
                    math.sqrt(total_uv / total_3d) * texture_size
                )
    bm2.free()

    after_nonzero = [d for d in after_densities if d > 0]
    after_variance = (
        (max(after_nonzero) - min(after_nonzero))
        / max(sum(after_nonzero) / len(after_nonzero), 1e-8)
        if after_nonzero
        else 0.0
    )

    return {
        "object_name": name,
        "target_density": round(target_density, 1),
        "islands_processed": len(island_data),
        "before": {
            "density_variance_ratio": round(before_variance, 2),
            "density_range": [
                round(min(nonzero_densities), 1),
                round(max(nonzero_densities), 1),
            ],
        },
        "after": {
            "density_variance_ratio": round(after_variance, 2),
            "density_range": (
                [round(min(after_nonzero), 1), round(max(after_nonzero), 1)]
                if after_nonzero
                else [0.0, 0.0]
            ),
        },
    }


# ---------------------------------------------------------------------------
# Handler 7: Export UV Layout (visual verification)
# ---------------------------------------------------------------------------


def handle_export_uv_layout(params: dict) -> dict:
    """Export UV layout as a PNG image for visual review."""
    name = params.get("object_name")
    size = params.get("size", 1024)
    opacity = params.get("opacity", 0.25)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    filepath = os.path.join(
        tempfile.gettempdir(), f"vb_uv_layout_{uuid.uuid4().hex[:8]}.png"
    )

    override = get_3d_context_override()
    if not override:
        # Fallback: manual UV rendering (no UV editor available)
        return _render_uv_layout_fallback(obj, filepath, size)

    old_active = bpy.context.view_layer.objects.active
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        with bpy.context.temp_override(**override, active_object=obj):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            try:
                bpy.ops.uv.export_layout(
                    filepath=filepath,
                    export_all=True,
                    mode="PNG",
                    size=(size, size),
                    opacity=opacity,
                )
            except (RuntimeError, TypeError, AttributeError):
                # UV export operator may fail without UV editor context
                bpy.ops.object.mode_set(mode="OBJECT")
                if old_active:
                    bpy.context.view_layer.objects.active = old_active
                return _render_uv_layout_fallback(obj, filepath, size)
            bpy.ops.object.mode_set(mode="OBJECT")
    finally:
        if old_active:
            bpy.context.view_layer.objects.active = old_active

    return {
        "filepath": filepath,
        "size": size,
        "format": "png",
    }


def _render_uv_layout_fallback(obj, filepath: str, size: int) -> dict:
    """Render UV layout using Pillow when bpy.ops.uv.export_layout is unavailable."""
    try:
        from PIL import Image as PILImage, ImageDraw
    except ImportError:
        raise RuntimeError(
            "Neither UV export operator nor Pillow available for UV layout rendering"
        )

    img = PILImage.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.active
    if uv_layer:
        for face in bm.faces:
            uv_coords = [loop[uv_layer].uv for loop in face.loops]
            # Convert UV (0-1) to pixel coords
            points = [
                (int(uv.x * (size - 1)), int((1.0 - uv.y) * (size - 1)))
                for uv in uv_coords
            ]
            if len(points) >= 3:
                draw.polygon(points, outline=(255, 255, 255, 200))
    bm.free()

    img.save(filepath, "PNG")
    return {
        "filepath": filepath,
        "size": size,
        "format": "png",
        "method": "pillow_fallback",
    }


# ---------------------------------------------------------------------------
# Handler 8: Set Active UV Layer (utility)
# ---------------------------------------------------------------------------


def handle_set_active_uv_layer(params: dict) -> dict:
    """Set the named UV layer as active on the mesh."""
    name = params.get("object_name")
    layer_name = params.get("layer_name")

    if not layer_name:
        raise ValueError("'layer_name' is required")

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    uv_layers = obj.data.uv_layers
    if layer_name not in uv_layers:
        available = [l.name for l in uv_layers]
        raise ValueError(
            f"UV layer '{layer_name}' not found. Available: {available}"
        )

    uv_layers[layer_name].active = True
    return {
        "object_name": name,
        "active_uv_layer": layer_name,
        "total_uv_layers": len(uv_layers),
    }


# ---------------------------------------------------------------------------
# Handler 9: Ensure xatlas (setup)
# ---------------------------------------------------------------------------


def handle_ensure_xatlas(params: dict) -> dict:
    """Install xatlas into Blender's Python if not already present."""
    try:
        import xatlas

        return {
            "installed": True,
            "version": getattr(xatlas, "__version__", "unknown"),
            "just_installed": False,
        }
    except ImportError:
        pass

    # Install xatlas into Blender's Python
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "xatlas==0.0.11"],
        timeout=120,
    )

    # Re-import to verify
    import importlib

    xatlas = importlib.import_module("xatlas")
    return {
        "installed": True,
        "version": getattr(xatlas, "__version__", "unknown"),
        "just_installed": True,
    }
