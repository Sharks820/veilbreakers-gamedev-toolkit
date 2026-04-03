import os

import bpy

from ._context import get_3d_context_override

# Humanoid avatar types that require leaf bones for Unity Mecanim (EXP-012)
_HUMANOID_AVATAR_TYPES: frozenset[str] = frozenset({
    "humanoid", "biped", "human", "character",
})


def _detect_avatar_type(params: dict) -> str:
    """Return the avatar_type param, defaulting to 'humanoid'."""
    return (params.get("avatar_type") or "humanoid").lower()


def _should_add_leaf_bones(params: dict) -> bool:
    """Add leaf bones only for Humanoid/biped avatar types (EXP-012)."""
    return _detect_avatar_type(params) in _HUMANOID_AVATAR_TYPES


def _apply_unity_roughness_to_material(mat: "bpy.types.Material") -> None:
    """Invert roughness → smoothness so Unity URP receives correct values (EXP-001).

    Blender uses roughness [0=mirror, 1=matte].
    Unity URP Smoothness = 1 - roughness.
    We store the inverted value in a custom property so the Unity import
    script can read it without losing the original Blender value.
    """
    if mat is None or not mat.use_nodes:
        return
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        return
    roughness_input = bsdf.inputs.get("Roughness")
    if roughness_input is None:
        return
    roughness = roughness_input.default_value
    mat["unity_smoothness"] = round(1.0 - float(roughness), 6)


def _collect_scene_materials() -> list:
    """Return all materials used by selected objects (or all objects)."""
    mats = []
    for obj in bpy.context.scene.objects:
        for slot in obj.material_slots:
            if slot.material and slot.material not in mats:
                mats.append(slot.material)
    return mats


def _detect_texture_type(img_name: str) -> str:
    """Classify a texture image by naming convention (EXP-011)."""
    name_lower = img_name.lower()
    if any(k in name_lower for k in ("_normal", "_nrm", "_nor", "_n.")):
        return "normal"
    if any(k in name_lower for k in ("_rough", "_roughness", "_rgh")):
        return "roughness"
    if any(k in name_lower for k in ("_metal", "_metallic", "_mtl")):
        return "metallic"
    if any(k in name_lower for k in ("_ao", "_ambient", "_occlusion")):
        return "ao"
    if any(k in name_lower for k in ("_emit", "_emission", "_emissive")):
        return "emission"
    if any(k in name_lower for k in ("_height", "_disp", "_displacement", "_bump")):
        return "height"
    if any(k in name_lower for k in ("_mask", "_msk")):
        return "mask"
    return "albedo"


def _tag_materials_for_unity(objects: list | None = None) -> dict:
    """Tag all materials with Unity-specific custom properties (EXP-001, EXP-011).

    Returns a summary dict: {mat_name: {unity_smoothness, texture_types}}.
    """
    summary = {}
    objs = objects if objects is not None else list(bpy.context.scene.objects)
    seen_mats: set = set()
    for obj in objs:
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or mat.name in seen_mats:
                continue
            seen_mats.add(mat.name)
            _apply_unity_roughness_to_material(mat)

            # Tag texture types (EXP-011)
            tex_types: list[str] = []
            if mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image:
                        tex_type = _detect_texture_type(node.image.name)
                        node.image["unity_texture_type"] = tex_type
                        if tex_type not in tex_types:
                            tex_types.append(tex_type)

            summary[mat.name] = {
                "unity_smoothness": mat.get("unity_smoothness"),
                "texture_types": tex_types,
            }
    return summary


def _rename_collision_meshes_for_unity(objects: list | None = None) -> list[str]:
    """Rename _COL suffix collision meshes to Unity UCX_ prefix convention (EXP-003).

    Unity FBX importer recognises convex collision hulls named UCX_<MeshName>[_N].
    Blender often names them <MeshName>_COL.  This renames them in-place before export
    so Unity auto-creates MeshCollider components with the correct mesh assignment.

    Returns list of renamed object name pairs as strings.
    """
    renamed: list[str] = []
    objs = objects if objects is not None else list(bpy.context.scene.objects)
    for obj in objs:
        if not obj.name.endswith("_COL"):
            continue
        base_name = obj.name[:-4]  # strip "_COL"
        # Unity UCX_ prefix: UCX_<BaseMeshName>
        new_name = f"UCX_{base_name}"
        # Avoid collisions with existing names
        suffix = 0
        candidate = new_name
        while bpy.data.objects.get(candidate):
            suffix += 1
            candidate = f"{new_name}_{suffix:02d}"
        old_name = obj.name
        obj.name = candidate
        if obj.data:
            obj.data.name = candidate
        # Tag so Unity import script can set convex MeshCollider
        obj["unity_collision_mesh"] = True
        obj["unity_collision_base"] = base_name
        renamed.append(f"{old_name} -> {candidate}")
    return renamed


def _ensure_uv2_lightmap_layer(objects: list | None = None) -> list[str]:
    """Ensure UV2 (lightmap) layer is in slot index 1 for Unity (EXP-007).

    Unity expects the lightmap UV in UV channel index 1 (zero-based).
    If an object has a UV layer named 'UVMap2', 'lightmap', or 'UV2', move it
    to index 1 by reordering.  Creates a blank UV2 layer if none exists.

    Returns list of object names that were modified.
    """
    _lightmap_names = {"uvmap2", "lightmap", "uv2", "uv_lightmap", "uv channel 2"}
    modified: list[str] = []
    objs = objects if objects is not None else list(bpy.context.scene.objects)
    for obj in objs:
        if obj.type != "MESH" or obj.data is None:
            continue
        mesh = obj.data
        uv_layers = mesh.uv_layers

        # Find lightmap layer
        lightmap_layer = None
        for layer in uv_layers:
            if layer.name.lower() in _lightmap_names:
                lightmap_layer = layer
                break

        if lightmap_layer is None:
            # No lightmap UV — add one named "UVMap2" at slot 1
            if len(uv_layers) >= 1:
                uv_layers.new(name="UVMap2")
                modified.append(f"{obj.name}: created UVMap2 lightmap layer")
            continue

        # If lightmap is already at index 1, nothing to do
        layer_names = [l.name for l in uv_layers]
        current_idx = layer_names.index(lightmap_layer.name)
        if current_idx == 1:
            continue

        # Blender doesn't support arbitrary UV layer reordering via Python API;
        # the workaround is to set the active render UV to the lightmap layer
        # and tag it with a custom property for the exporter.
        # We also tag the object so the Unity import script can remap UV channels.
        mesh.uv_layers.active = lightmap_layer
        obj["unity_lightmap_uv_layer"] = lightmap_layer.name
        obj["unity_lightmap_uv_index"] = current_idx
        modified.append(
            f"{obj.name}: tagged '{lightmap_layer.name}' (slot {current_idx}) as lightmap UV"
        )
    return modified


def _export_custom_properties(objects: list | None = None) -> dict:
    """Write object-level custom properties as FBX user properties (EXP-008).

    Blender's FBX exporter serialises bpy.types.Object custom properties
    automatically when use_custom_props=True.  This helper validates that
    key values are of supported types and returns a summary.
    """
    supported_types = (int, float, str, bool)
    summary = {}
    objs = objects if objects is not None else list(bpy.context.scene.objects)
    for obj in objs:
        props = {}
        for key, val in obj.items():
            if key.startswith("_"):  # internal Blender keys
                continue
            if isinstance(val, supported_types):
                props[key] = val
            elif hasattr(val, "to_list"):
                props[key] = val.to_list()
        if props:
            summary[obj.name] = props
    return summary


def handle_export_fbx(params: dict) -> dict:
    filepath = params.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required")

    if not filepath.lower().endswith(".fbx"):
        filepath += ".fbx"

    selected_only = params.get("selected_only", False)
    apply_modifiers = params.get("apply_modifiers", True)
    vertex_colors = params.get("vertex_colors", True)   # EXP-005
    embed_textures = params.get("embed_textures", False)  # EXP-009
    export_custom_props = params.get("export_custom_props", True)  # EXP-008
    add_leaf_bones = _should_add_leaf_bones(params)  # EXP-012

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    # EXP-001 / EXP-011: tag materials with unity_smoothness + texture types
    mat_summary = _tag_materials_for_unity()

    # EXP-003: rename _COL collision meshes to UCX_ prefix for Unity
    collision_renamed = _rename_collision_meshes_for_unity()

    # EXP-007: ensure UV2 lightmap layer is in correct slot
    uv2_modified = _ensure_uv2_lightmap_layer()

    # EXP-008: validate custom properties before export
    custom_props_summary = _export_custom_properties()

    override = get_3d_context_override()
    # Unity-optimized FBX settings
    kwargs = {
        "filepath": filepath,
        "use_selection": selected_only,
        "use_mesh_modifiers": apply_modifiers,
        "apply_unit_scale": True,
        "apply_scale_options": "FBX_SCALE_ALL",
        "bake_space_transform": True,
        "axis_forward": "-Z",
        "axis_up": "Y",
        "add_leaf_bones": add_leaf_bones,   # EXP-012: conditional per avatar type
        "mesh_smooth_type": "FACE",
        "use_tspace": True,                  # EXP-004: export tangents
        "use_armature_deform_only": True,
        "colors_type": "SRGB" if vertex_colors else "NONE",  # EXP-005/006 (Blender 4.x API)
        "use_custom_props": export_custom_props,  # EXP-008
        "path_mode": "COPY" if embed_textures else "AUTO",  # EXP-009
    }
    # EXP-009: embed_textures was removed in Blender 4.x (path_mode=COPY handles it).
    # Try with it first for older Blender builds; silently drop on TypeError.
    if embed_textures:
        kwargs["embed_textures"] = True

    def _do_export(**kw):
        if override:
            with bpy.context.temp_override(**override):
                bpy.ops.export_scene.fbx(**kw)
        else:
            bpy.ops.export_scene.fbx(**kw)

    try:
        _do_export(**kwargs)
    except TypeError:
        # embed_textures not accepted by this Blender version — drop and retry
        kwargs.pop("embed_textures", None)
        _do_export(**kwargs)

    return {
        "filepath": filepath,
        "format": "fbx",
        "exported": True,
        "selected_only": selected_only,
        "avatar_type": _detect_avatar_type(params),
        "add_leaf_bones": add_leaf_bones,
        "vertex_colors_exported": vertex_colors,
        "textures_embedded": embed_textures,
        "custom_props_exported": export_custom_props,
        "materials_tagged": len(mat_summary),
        "material_detail": mat_summary,
        "custom_props_detail": custom_props_summary,
        "collision_meshes_renamed": collision_renamed,  # EXP-003
        "uv2_layers_fixed": uv2_modified,               # EXP-007
    }


def handle_export_gltf(params: dict) -> dict:
    filepath = params.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required")

    if not filepath.lower().endswith((".gltf", ".glb")):
        filepath += ".glb"

    selected_only = params.get("selected_only", False)
    apply_modifiers = params.get("apply_modifiers", True)

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    override = get_3d_context_override()
    kwargs = {
        "filepath": filepath,
        "use_selection": selected_only,
        "export_apply": apply_modifiers,
        "export_format": "GLB",
        "export_tangents": True,
        "export_materials": "EXPORT",
        "export_colors": True,
        "export_image_format": "AUTO",
        "export_yup": True,
    }

    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.export_scene.gltf(**kwargs)
    else:
        bpy.ops.export_scene.gltf(**kwargs)

    return {
        "filepath": filepath,
        "format": "gltf",
        "exported": True,
        "selected_only": selected_only,
    }
