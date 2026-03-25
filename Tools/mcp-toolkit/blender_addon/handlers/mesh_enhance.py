"""Geometry enhancement pipeline for AAA-quality mesh post-processing.

Transforms raw procedural geometry (primitive compositions) into production-
quality game assets through:

1. Sharp edge detection by dihedral angle
2. Edge crease assignment for SubD preservation
3. Subdivision Surface (Catmull-Clark) modifier
4. Bevel modifier on weighted edges for edge definition
5. Weighted normals for proper hard-surface shading
6. Smooth shading with auto-smooth angle threshold
7. Optional displacement for organic surface detail
8. High-poly to low-poly normal map baking

Profile presets tune parameters per asset category:
  weapon, architecture, organic, prop, character, vegetation
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Pure-logic: enhancement profiles (no bpy imports)
# ---------------------------------------------------------------------------

ENHANCE_PROFILES: dict[str, dict[str, Any]] = {
    "weapon": {
        "description": "Hard-surface weapon with sharp bevels and crisp edges",
        "sharp_angle_threshold": 35.0,       # degrees - edges sharper than this get creased
        "crease_value": 0.8,                 # SubD crease weight for sharp edges
        "subdiv_levels_viewport": 1,         # SubD viewport level
        "subdiv_levels_render": 2,           # SubD render level
        "bevel_width": 0.003,                # Bevel width in Blender units
        "bevel_segments": 2,                 # Bevel segment count
        "bevel_angle_limit": 30.0,           # Only bevel edges sharper than this
        "use_weighted_normals": True,        # Weighted normals modifier
        "smooth_shading": True,              # Apply smooth shading
        "auto_smooth_angle": 30.0,           # Auto-smooth angle threshold
        "displacement_strength": 0.0,        # No displacement for weapons
        "displacement_scale": 0.0,
    },
    "architecture": {
        "description": "Architectural asset with stone/wood surface detail",
        "sharp_angle_threshold": 40.0,
        "crease_value": 1.0,                 # Full crease to keep building edges sharp
        "subdiv_levels_viewport": 1,
        "subdiv_levels_render": 2,
        "bevel_width": 0.005,
        "bevel_segments": 2,
        "bevel_angle_limit": 35.0,
        "use_weighted_normals": True,
        "smooth_shading": True,
        "auto_smooth_angle": 40.0,           # Wider angle for architectural hard edges
        "displacement_strength": 0.002,      # Subtle stone surface roughness
        "displacement_scale": 8.0,           # Noise scale for displacement
    },
    "organic": {
        "description": "Organic/creature mesh with smooth flowing surfaces",
        "sharp_angle_threshold": 60.0,       # Very few sharp edges
        "crease_value": 0.5,
        "subdiv_levels_viewport": 2,         # More subdivision for smooth surfaces
        "subdiv_levels_render": 3,
        "bevel_width": 0.0,                  # No bevel on organic meshes
        "bevel_segments": 0,
        "bevel_angle_limit": 0.0,
        "use_weighted_normals": False,       # Not needed for organic
        "smooth_shading": True,
        "auto_smooth_angle": 60.0,
        "displacement_strength": 0.001,      # Subtle skin/surface texture
        "displacement_scale": 15.0,
    },
    "prop": {
        "description": "Game prop - balanced between hard and soft surfaces",
        "sharp_angle_threshold": 38.0,
        "crease_value": 0.7,
        "subdiv_levels_viewport": 1,
        "subdiv_levels_render": 2,
        "bevel_width": 0.004,
        "bevel_segments": 2,
        "bevel_angle_limit": 32.0,
        "use_weighted_normals": True,
        "smooth_shading": True,
        "auto_smooth_angle": 35.0,
        "displacement_strength": 0.001,
        "displacement_scale": 10.0,
    },
    "character": {
        "description": "Character mesh with armor/cloth/skin mix",
        "sharp_angle_threshold": 45.0,
        "crease_value": 0.6,
        "subdiv_levels_viewport": 1,
        "subdiv_levels_render": 2,
        "bevel_width": 0.002,
        "bevel_segments": 2,
        "bevel_angle_limit": 35.0,
        "use_weighted_normals": True,
        "smooth_shading": True,
        "auto_smooth_angle": 40.0,
        "displacement_strength": 0.0005,
        "displacement_scale": 12.0,
    },
    "vegetation": {
        "description": "Foliage/trees - smooth with minimal modifiers for perf",
        "sharp_angle_threshold": 50.0,
        "crease_value": 0.3,
        "subdiv_levels_viewport": 0,         # No SubD - use normals only
        "subdiv_levels_render": 1,
        "bevel_width": 0.0,
        "bevel_segments": 0,
        "bevel_angle_limit": 0.0,
        "use_weighted_normals": False,
        "smooth_shading": True,
        "auto_smooth_angle": 45.0,
        "displacement_strength": 0.0,
        "displacement_scale": 0.0,
    },
}


def get_enhance_profile(profile_name: str) -> dict[str, Any]:
    """Return enhancement profile by name, with fallback to 'prop'."""
    return dict(ENHANCE_PROFILES.get(profile_name, ENHANCE_PROFILES["prop"]))


def list_enhance_profiles() -> dict[str, str]:
    """Return dict mapping profile name -> description."""
    return {k: v["description"] for k, v in ENHANCE_PROFILES.items()}


def compute_sharp_edges_pure(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    angle_threshold_deg: float = 35.0,
) -> list[tuple[int, int]]:
    """Compute edges that should be marked sharp based on dihedral angle.

    Pure-logic implementation (no bpy) for testing. Returns list of
    (vert_idx_a, vert_idx_b) pairs representing sharp edges.

    An edge shared by two faces is sharp if the angle between their
    normals exceeds angle_threshold_deg.
    """
    if not vertices or not faces:
        return []

    threshold_rad = math.radians(angle_threshold_deg)
    cos_threshold = math.cos(threshold_rad)

    # Build edge -> face adjacency map
    edge_faces: dict[tuple[int, int], list[int]] = {}
    face_normals: list[tuple[float, float, float]] = []

    for fi, face in enumerate(faces):
        # Compute face normal via Newell's method
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

        # Register edges
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            edge_key = (min(a, b), max(a, b))
            if edge_key not in edge_faces:
                edge_faces[edge_key] = []
            edge_faces[edge_key].append(fi)

    # Find sharp edges
    sharp_edges: list[tuple[int, int]] = []
    for edge_key, fi_list in edge_faces.items():
        if len(fi_list) == 2:
            n0 = face_normals[fi_list[0]]
            n1 = face_normals[fi_list[1]]
            dot = n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]
            dot = max(-1.0, min(1.0, dot))
            if dot < cos_threshold:
                sharp_edges.append(edge_key)
        elif len(fi_list) == 1:
            # Boundary edge - always sharp
            sharp_edges.append(edge_key)

    return sharp_edges


# ---------------------------------------------------------------------------
# Blender-dependent: actual mesh enhancement (guarded import)
# ---------------------------------------------------------------------------

try:
    import bpy
    import bmesh
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False


def _get_mesh_object(name: str) -> Any:
    """Validate and return a mesh object by name."""
    if not _HAS_BPY:
        raise RuntimeError("Blender (bpy) not available")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")
    return obj


def _detect_and_crease_sharp_edges(
    obj: Any,
    angle_threshold_deg: float,
    crease_value: float,
) -> dict[str, int]:
    """Detect sharp edges by dihedral angle and set crease + sharp flags.

    Returns stats dict with edge counts.
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        threshold_rad = math.radians(angle_threshold_deg)

        # Get or create crease layer
        crease_layer = bm.edges.layers.float.get("crease_edge")
        if crease_layer is None:
            crease_layer = bm.edges.layers.float.new("crease_edge")

        sharp_count = 0
        boundary_count = 0
        total_edges = len(bm.edges)

        for edge in bm.edges:
            linked_faces = edge.link_faces
            if len(linked_faces) == 2:
                angle = edge.calc_face_angle(0.0)
                if angle > threshold_rad:
                    edge[crease_layer] = crease_value
                    edge.smooth = False  # Mark as sharp
                    sharp_count += 1
                else:
                    edge.smooth = True
            elif len(linked_faces) <= 1:
                # Boundary edge - mark sharp
                edge[crease_layer] = 1.0
                edge.smooth = False
                boundary_count += 1
            else:
                edge.smooth = True

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    return {
        "total_edges": total_edges,
        "sharp_edges": sharp_count,
        "boundary_edges": boundary_count,
        "crease_value": crease_value,
        "angle_threshold_deg": angle_threshold_deg,
    }


def _apply_smooth_shading(obj: Any, auto_smooth_angle_deg: float) -> None:
    """Apply smooth shading with auto-smooth angle threshold."""
    mesh = obj.data

    # Set all faces to smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Blender 4.x: auto_smooth is via modifier or mesh attribute
    # Blender 3.x: use_auto_smooth property
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(auto_smooth_angle_deg)
    else:
        # Blender 4.1+: auto smooth via geometry nodes or sharp edges only
        # Sharp edges already marked by _detect_and_crease_sharp_edges
        pass


def _add_subdivision_surface(
    obj: Any,
    levels_viewport: int,
    levels_render: int,
) -> str | None:
    """Add Catmull-Clark subdivision surface modifier. Returns modifier name."""
    if levels_viewport <= 0 and levels_render <= 0:
        return None

    mod = obj.modifiers.new(name="VB_SubD", type="SUBSURF")
    mod.subdivision_type = "CATMULL_CLARK"
    mod.levels = min(levels_viewport, 4)
    mod.render_levels = min(levels_render, 5)
    mod.quality = 3
    mod.use_limit_surface = True
    # Use creases for SubD boundary behavior
    mod.uv_smooth = "PRESERVE_CORNERS"
    mod.boundary_smooth = "PRESERVE_CORNERS"
    return mod.name


def _add_bevel_modifier(
    obj: Any,
    width: float,
    segments: int,
    angle_limit_deg: float,
) -> str | None:
    """Add angle-limited bevel modifier for edge definition. Returns modifier name."""
    if width <= 0 or segments <= 0:
        return None

    mod = obj.modifiers.new(name="VB_Bevel", type="BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle_limit_deg)
    mod.affect = "EDGES"
    mod.miter_outer = "MITER_ARC"
    mod.harden_normals = True
    return mod.name


def _add_weighted_normals(obj: Any) -> str | None:
    """Add weighted normals modifier for correct hard-surface shading."""
    mod = obj.modifiers.new(name="VB_WeightedNormals", type="WEIGHTED_NORMAL")
    mod.mode = "FACE_AREA_AND_ANGLE"
    mod.weight = 100
    mod.keep_sharp = True
    return mod.name


def _add_displacement(
    obj: Any,
    strength: float,
    noise_scale: float,
) -> str | None:
    """Add procedural displacement via texture for surface detail."""
    if strength <= 0:
        return None

    # Create noise texture for displacement
    tex_name = f"VB_Displace_{obj.name}"
    tex = bpy.data.textures.new(tex_name, type="CLOUDS")
    tex.noise_scale = noise_scale
    tex.noise_depth = 2
    tex.cloud_type = "COLOR"

    mod = obj.modifiers.new(name="VB_Displacement", type="DISPLACE")
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    mod.texture_coords = "LOCAL"
    return mod.name


def handle_enhance_geometry(params: dict) -> dict:
    """Enhance mesh geometry to AAA quality.

    Applies a profile-based enhancement pipeline:
    1. Detect and mark sharp edges by dihedral angle
    2. Set edge creases for SubD preservation
    3. Apply smooth shading with auto-smooth
    4. Add Subdivision Surface modifier (Catmull-Clark)
    5. Add Bevel modifier for edge definition
    6. Add Weighted Normals modifier
    7. Optionally add displacement for surface detail

    Params:
        object_name: Name of the Blender mesh object (required).
        profile: Enhancement profile preset (default "prop").
            One of: weapon, architecture, organic, prop, character, vegetation.
        subdiv_levels: Override SubD viewport levels (optional).
        render_levels: Override SubD render levels (optional).
        bevel_width: Override bevel width (optional).
        bevel_segments: Override bevel segments (optional).
        sharp_angle: Override sharp edge detection angle (optional).
        crease_value: Override edge crease weight (optional).
        displacement_strength: Override displacement strength (optional).
        apply_modifiers: If True, apply all modifiers (bake). Default False.
        skip_steps: List of step names to skip (optional).
            Valid: "sharp_edges", "smooth_shading", "subdivision",
                   "bevel", "weighted_normals", "displacement"

    Returns:
        Dict with enhancement results per step.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    obj = _get_mesh_object(object_name)

    # Load profile with overrides
    profile_name = params.get("profile", "prop")
    cfg = get_enhance_profile(profile_name)

    # Apply parameter overrides
    if params.get("subdiv_levels") is not None:
        cfg["subdiv_levels_viewport"] = params["subdiv_levels"]
    if params.get("render_levels") is not None:
        cfg["subdiv_levels_render"] = params["render_levels"]
    if params.get("bevel_width") is not None:
        cfg["bevel_width"] = params["bevel_width"]
    if params.get("bevel_segments") is not None:
        cfg["bevel_segments"] = params["bevel_segments"]
    if params.get("sharp_angle") is not None:
        cfg["sharp_angle_threshold"] = params["sharp_angle"]
    if params.get("crease_value") is not None:
        cfg["crease_value"] = params["crease_value"]
    if params.get("displacement_strength") is not None:
        cfg["displacement_strength"] = params["displacement_strength"]

    apply_mods = params.get("apply_modifiers", False)
    skip_steps = set(params.get("skip_steps") or [])

    results: dict[str, Any] = {
        "object_name": object_name,
        "profile": profile_name,
        "steps": {},
        "modifiers_added": [],
    }

    # Pre-enhancement mesh stats
    results["before"] = {
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
        "edge_count": len(obj.data.edges),
    }

    # Step 1: Detect and crease sharp edges
    if "sharp_edges" not in skip_steps:
        edge_stats = _detect_and_crease_sharp_edges(
            obj,
            cfg["sharp_angle_threshold"],
            cfg["crease_value"],
        )
        results["steps"]["sharp_edges"] = edge_stats

    # Step 2: Apply smooth shading
    if "smooth_shading" not in skip_steps and cfg["smooth_shading"]:
        _apply_smooth_shading(obj, cfg["auto_smooth_angle"])
        results["steps"]["smooth_shading"] = {
            "auto_smooth_angle": cfg["auto_smooth_angle"],
        }

    # Step 3: Bevel modifier (add BEFORE SubD for best results)
    if "bevel" not in skip_steps and cfg["bevel_width"] > 0:
        mod_name = _add_bevel_modifier(
            obj, cfg["bevel_width"], cfg["bevel_segments"], cfg["bevel_angle_limit"]
        )
        if mod_name:
            results["modifiers_added"].append(mod_name)
            results["steps"]["bevel"] = {
                "width": cfg["bevel_width"],
                "segments": cfg["bevel_segments"],
                "angle_limit": cfg["bevel_angle_limit"],
            }

    # Step 4: Subdivision Surface modifier
    if "subdivision" not in skip_steps:
        mod_name = _add_subdivision_surface(
            obj, cfg["subdiv_levels_viewport"], cfg["subdiv_levels_render"]
        )
        if mod_name:
            results["modifiers_added"].append(mod_name)
            results["steps"]["subdivision"] = {
                "viewport_levels": cfg["subdiv_levels_viewport"],
                "render_levels": cfg["subdiv_levels_render"],
            }

    # Step 5: Displacement (add AFTER SubD so it gets subdivided geometry)
    if "displacement" not in skip_steps and cfg["displacement_strength"] > 0:
        mod_name = _add_displacement(
            obj, cfg["displacement_strength"], cfg["displacement_scale"]
        )
        if mod_name:
            results["modifiers_added"].append(mod_name)
            results["steps"]["displacement"] = {
                "strength": cfg["displacement_strength"],
                "scale": cfg["displacement_scale"],
            }

    # Step 6: Weighted Normals (must be LAST in modifier stack)
    if "weighted_normals" not in skip_steps and cfg["use_weighted_normals"]:
        mod_name = _add_weighted_normals(obj)
        if mod_name:
            results["modifiers_added"].append(mod_name)
            results["steps"]["weighted_normals"] = {"mode": "FACE_AREA_AND_ANGLE"}

    # Optionally apply (bake) all modifiers
    if apply_mods and results["modifiers_added"]:
        from ._context import get_3d_context_override

        ctx = get_3d_context_override()
        if ctx is None:
            results["apply_warning"] = "No 3D Viewport for modifier apply"
        else:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            applied: list[str] = []
            for mod_name in list(results["modifiers_added"]):
                if mod_name in [m.name for m in obj.modifiers]:
                    with bpy.context.temp_override(**ctx):
                        bpy.ops.object.modifier_apply(modifier=mod_name)
                    applied.append(mod_name)
            results["modifiers_applied"] = applied

    # Post-enhancement mesh stats
    results["after"] = {
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
        "edge_count": len(obj.data.edges),
    }

    results["status"] = "success"
    return results


def handle_bake_detail_normals(params: dict) -> dict:
    """Bake normals from enhanced (high-poly) mesh to game-res (low-poly) copy.

    Creates a duplicate of the object, applies all modifiers to get the high-poly
    version, then bakes a normal map from high to the original low-poly mesh.

    Params:
        object_name: Name of the enhanced mesh (with modifiers, required).
        image_size: Normal map resolution (default 2048).
        cage_extrusion: Ray cast distance for baking (default 0.02).
        output_name: Name for the baked normal map image (optional).

    Returns:
        Dict with bake results including image name.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    obj = _get_mesh_object(object_name)
    image_size = params.get("image_size", 2048)
    cage_extrusion = params.get("cage_extrusion", 0.02)
    output_name = params.get("output_name", f"{object_name}_normal")

    if not _HAS_BPY:
        raise RuntimeError("Blender (bpy) not available")

    from ._context import get_3d_context_override
    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available")

    # Create high-poly duplicate
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.duplicate()
    high_poly = bpy.context.active_object
    high_poly.name = f"{object_name}_highpoly_tmp"

    # Apply all modifiers on high-poly copy
    bpy.context.view_layer.objects.active = high_poly
    while high_poly.modifiers:
        mod_name = high_poly.modifiers[0].name
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.modifier_apply(modifier=mod_name)

    # Create bake target image
    img = bpy.data.images.new(output_name, image_size, image_size)
    img.colorspace_settings.name = "Non-Color"

    # Ensure low-poly has a material with the image for baking
    mat = obj.data.materials[0] if obj.data.materials else None
    created_mat = False
    if mat is None:
        mat = bpy.data.materials.new(f"{object_name}_BakeMat")
        mat.use_nodes = True
        obj.data.materials.append(mat)
        created_mat = True

    nodes = mat.node_tree.nodes
    img_node = nodes.new("ShaderNodeTexImage")
    img_node.image = img
    img_node.name = "VB_BakeTarget"
    # Select the image node so Blender knows where to bake to
    for n in nodes:
        n.select = False
    img_node.select = True
    nodes.active = img_node

    # Configure bake settings
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.bake_type = "NORMAL"
    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.cage_extrusion = cage_extrusion
    bpy.context.scene.render.bake.use_cage = False
    bpy.context.scene.render.bake.normal_space = "TANGENT"

    # Select high-poly, active = low-poly
    bpy.ops.object.select_all(action="DESELECT")
    high_poly.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Bake
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.bake(type="NORMAL")

    # Cleanup: remove high-poly duplicate
    bpy.ops.object.select_all(action="DESELECT")
    high_poly.select_set(True)
    bpy.context.view_layer.objects.active = high_poly
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.delete()

    # Remove temp bake node (keep the image)
    if "VB_BakeTarget" in nodes:
        nodes.remove(nodes["VB_BakeTarget"])
    if created_mat and len(obj.data.materials) > 0:
        # Connect normal map to material
        principled = None
        for n in nodes:
            if n.type == "BSDF_PRINCIPLED":
                principled = n
                break
        if principled:
            normal_map_node = nodes.new("ShaderNodeNormalMap")
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.image = img
            tex_node.image.colorspace_settings.name = "Non-Color"
            mat.node_tree.links.new(tex_node.outputs["Color"],
                                     normal_map_node.inputs["Color"])
            mat.node_tree.links.new(normal_map_node.outputs["Normal"],
                                     principled.inputs["Normal"])

    high_poly_verts = len(obj.data.vertices)  # already deleted, use estimate
    return {
        "object_name": object_name,
        "normal_map_image": output_name,
        "image_size": image_size,
        "cage_extrusion": cage_extrusion,
        "status": "success",
    }
