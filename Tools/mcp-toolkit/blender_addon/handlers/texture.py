"""Texture handlers for PBR material creation, baking, and validation.

Provides three command handlers:
  - handle_create_pbr_material: Build a full PBR node tree with image textures
  - handle_bake_textures: Bake texture maps (high-to-low-poly or self-bake)
  - handle_validate_texture: Validate texture resolution, format, colorspace, UV coverage
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import bpy

from ._context import get_3d_context_override

# ---------------------------------------------------------------------------
# Version-aware Principled BSDF socket name lookup
# ---------------------------------------------------------------------------

# Maps semantic names to Blender 4.0+ socket names.
# For sockets unchanged between 3.x and 4.x, the same name works.
# For renamed sockets, we use the NEW (4.0+) names as primary.
BSDF_INPUT_MAP: dict[str, str] = {
    # Core PBR channels (unchanged across versions)
    "base_color": "Base Color",
    "metallic": "Metallic",
    "roughness": "Roughness",
    "normal": "Normal",
    "ior": "IOR",
    "alpha": "Alpha",
    # Blender 4.0+ renamed sockets:
    "subsurface": "Subsurface Weight",
    "specular": "Specular IOR Level",
    "transmission": "Transmission Weight",
    "coat": "Coat Weight",
    "sheen": "Sheen Weight",
    "emission": "Emission Color",
}

# Fallback names for Blender 3.x (pre-4.0) sockets that were renamed.
_BSDF_FALLBACK_MAP: dict[str, str] = {
    "Subsurface Weight": "Subsurface",
    "Specular IOR Level": "Specular",
    "Transmission Weight": "Transmission",
    "Coat Weight": "Clearcoat",
    "Sheen Weight": "Sheen",
    "Emission Color": "Emission",
}


def _get_bsdf_input(bsdf_node: Any, semantic_name: str) -> Any:
    """Get a Principled BSDF input socket by semantic name.

    Tries the BSDF_INPUT_MAP name first (Blender 4.0+), then falls back
    to pre-4.0 names. Raises ValueError with a clear message if neither
    socket exists.
    """
    socket_name = BSDF_INPUT_MAP.get(semantic_name)
    if socket_name is None:
        raise ValueError(
            f"Unknown BSDF input: '{semantic_name}'. "
            f"Valid names: {sorted(BSDF_INPUT_MAP.keys())}"
        )

    # Try primary (4.0+) name
    socket = bsdf_node.inputs.get(socket_name)
    if socket is not None:
        return socket

    # Try fallback (3.x) name
    fallback = _BSDF_FALLBACK_MAP.get(socket_name)
    if fallback:
        socket = bsdf_node.inputs.get(fallback)
        if socket is not None:
            return socket

    raise ValueError(
        f"BSDF node has no input '{socket_name}'"
        + (f" (or fallback '{fallback}')" if fallback else "")
        + f". Available: {[s.name for s in bsdf_node.inputs]}"
    )


# ---------------------------------------------------------------------------
# PBR channel configuration
# ---------------------------------------------------------------------------

def _build_channel_config() -> dict[str, tuple[str, str | None, str, bool]]:
    """Return PBR channel configuration.

    Returns a dict mapping channel name to:
        (file_suffix, bsdf_input_name, colorspace, needs_normal_node)

    The bsdf_input_name is None for AO (mixed via MixRGB, not direct input).
    """
    return {
        "albedo": ("_albedo", "Base Color", "sRGB", False),
        "metallic": ("_metallic", "Metallic", "Non-Color", False),
        "roughness": ("_roughness", "Roughness", "Non-Color", False),
        "normal": ("_normal", "Normal", "Non-Color", True),
        "ao": ("_ao", None, "Non-Color", False),
    }


# ---------------------------------------------------------------------------
# Texture validation (pure logic -- no bpy dependency)
# ---------------------------------------------------------------------------

def _is_power_of_two(n: int) -> bool:
    """Check if an integer is a power of two."""
    return n > 0 and (n & (n - 1)) == 0


def _validate_texture_metadata(
    width: int,
    height: int,
    format_name: str,
    colorspace: str,
) -> dict[str, Any]:
    """Validate texture metadata and return issues.

    Pure function -- no Blender dependency. Returns dict with:
        width, height, format, colorspace, is_power_of_two, issues
    """
    issues: list[str] = []

    pot = _is_power_of_two(width) and _is_power_of_two(height)
    if not pot:
        issues.append(
            f"Non-power-of-two resolution ({width}x{height}). "
            "Game engines require power-of-two textures for mipmapping."
        )

    if width < 256 or height < 256:
        issues.append(
            f"Low resolution ({width}x{height}). "
            "Minimum recommended size is 256x256."
        )

    if width > 8192 or height > 8192:
        issues.append(
            f"Oversized resolution ({width}x{height}). "
            "Maximum recommended size is 8192x8192."
        )

    return {
        "width": width,
        "height": height,
        "format": format_name,
        "colorspace": colorspace,
        "is_power_of_two": pot,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# Bake parameter validation (pure logic)
# ---------------------------------------------------------------------------

_ALLOWED_BAKE_TYPES = frozenset({
    "NORMAL", "AO", "COMBINED", "ROUGHNESS", "EMIT", "DIFFUSE",
})


def _validate_bake_params(bake_type: str) -> None:
    """Validate bake parameters. Raises ValueError on invalid input."""
    if bake_type not in _ALLOWED_BAKE_TYPES:
        raise ValueError(
            f"Invalid bake_type '{bake_type}'. "
            f"Allowed types: {sorted(_ALLOWED_BAKE_TYPES)}"
        )


# ---------------------------------------------------------------------------
# Texture file discovery
# ---------------------------------------------------------------------------

_TEXTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tga", ".exr")


def _find_texture_file(texture_dir: str, name: str, suffix: str) -> str | None:
    """Search for a texture file matching {name}{suffix}.{ext} in texture_dir."""
    for ext in _TEXTURE_EXTENSIONS:
        candidate = os.path.join(texture_dir, f"{name}{suffix}{ext}")
        if os.path.isfile(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Handler: create PBR material
# ---------------------------------------------------------------------------

def handle_create_pbr_material(params: dict) -> dict:
    """Create a full PBR material with image texture nodes for all channels.

    Params:
        name (str): Material name
        texture_dir (str, optional): Directory containing texture files
        texture_size (int, default 1024): Size for blank images
        object_name (str, optional): Object to assign material to

    Returns dict with material_name, channels, texture_size, assigned_to.
    """
    name = params.get("name", "PBR_Material")
    texture_dir = params.get("texture_dir")
    texture_size = params.get("texture_size", 1024)
    object_name = params.get("object_name")

    # Create material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree

    # Clear default nodes
    tree.nodes.clear()

    # Create output and BSDF
    output_node = tree.nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (400, 0)

    bsdf_node = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_node.location = (0, 0)

    # Link BSDF to output
    tree.links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    channels = _build_channel_config()
    channel_nodes: dict[str, str] = {}
    albedo_tex_node = None
    y_offset = 0

    for ch_name, (suffix, bsdf_input, colorspace, needs_normal) in channels.items():
        # Create image texture node
        tex_node = tree.nodes.new("ShaderNodeTexImage")
        tex_node.location = (-600, y_offset)
        tex_node.label = f"{name}{suffix}"

        # Load or create image
        image_loaded = False
        if texture_dir:
            filepath = _find_texture_file(texture_dir, name, suffix)
            if filepath:
                tex_node.image = bpy.data.images.load(filepath)
                image_loaded = True

        if not image_loaded:
            img = bpy.data.images.new(
                f"{name}{suffix}", texture_size, texture_size
            )
            tex_node.image = img

        # Set colorspace
        tex_node.image.colorspace_settings.name = colorspace

        # Wire to BSDF
        if needs_normal:
            # Normal channel: insert Normal Map node between tex and BSDF
            normal_map_node = tree.nodes.new("ShaderNodeNormalMap")
            normal_map_node.location = (-300, y_offset)
            tree.links.new(tex_node.outputs["Color"], normal_map_node.inputs["Color"])
            bsdf_input_socket = _get_bsdf_input(bsdf_node, "normal")
            tree.links.new(normal_map_node.outputs["Normal"], bsdf_input_socket)
        elif ch_name == "albedo":
            # Store albedo tex node for AO mix later
            albedo_tex_node = tex_node
            bsdf_input_socket = _get_bsdf_input(bsdf_node, "base_color")
            tree.links.new(tex_node.outputs["Color"], bsdf_input_socket)
        elif ch_name == "ao":
            # AO: create MixRGB (Multiply) blending AO with albedo
            mix_node = tree.nodes.new("ShaderNodeMixRGB")
            mix_node.blend_type = "MULTIPLY"
            mix_node.location = (-300, y_offset)
            mix_node.inputs["Fac"].default_value = 1.0

            if albedo_tex_node is not None:
                tree.links.new(
                    albedo_tex_node.outputs["Color"], mix_node.inputs["Color1"]
                )
            tree.links.new(tex_node.outputs["Color"], mix_node.inputs["Color2"])

            # Replace direct albedo link with AO-multiplied output
            bsdf_input_socket = _get_bsdf_input(bsdf_node, "base_color")
            # Remove existing albedo link to Base Color
            for link in list(tree.links):
                if (
                    link.to_socket == bsdf_input_socket
                    and albedo_tex_node is not None
                    and link.from_node == albedo_tex_node
                ):
                    tree.links.remove(link)
            tree.links.new(mix_node.outputs["Color"], bsdf_input_socket)
        elif bsdf_input is not None:
            # Direct connection for metallic, roughness
            bsdf_input_socket = _get_bsdf_input(
                bsdf_node, bsdf_input.lower().replace(" ", "_")
            )
            tree.links.new(tex_node.outputs["Color"], bsdf_input_socket)

        channel_nodes[ch_name] = tex_node.name
        y_offset -= 300

    # Assign to object if requested
    assigned_to = None
    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object not found: {object_name}")
        if obj.data is None or not hasattr(obj.data, "materials"):
            raise ValueError(f"Object '{object_name}' does not support materials")
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        assigned_to = obj.name

    return {
        "material_name": mat.name,
        "channels": channel_nodes,
        "texture_size": texture_size,
        "assigned_to": assigned_to,
    }


# ---------------------------------------------------------------------------
# Handler: bake textures
# ---------------------------------------------------------------------------

def handle_bake_textures(params: dict) -> dict:
    """Bake texture maps from high-poly to low-poly or self-bake.

    Params:
        object_name (str): Target object for baking
        bake_type (str): NORMAL|AO|COMBINED|ROUGHNESS|EMIT|DIFFUSE
        source_object (str, optional): High-poly source for selected-to-active
        image_name (str): Name of image texture node to bake into
        margin (int, default 16): Bake margin in pixels
        cage_extrusion (float, default 0.1): Ray cast distance for selected-to-active
        samples (int, default 32): Cycles render samples for bake

    Returns dict with baked, bake_type, object, source, image.
    """
    object_name = params.get("object_name")
    bake_type = params.get("bake_type", "COMBINED")
    source_object = params.get("source_object")
    image_name = params.get("image_name")
    margin = params.get("margin", 16)
    cage_extrusion = params.get("cage_extrusion", 0.1)
    samples = params.get("samples", 32)

    if not object_name:
        raise ValueError("'object_name' is required")
    if not image_name:
        raise ValueError("'image_name' is required")

    _validate_bake_params(bake_type)

    target = bpy.data.objects.get(object_name)
    if target is None:
        raise ValueError(f"Object not found: {object_name}")

    # Store previous render engine to restore after bake
    prev_engine = bpy.context.scene.render.engine

    try:
        # Switch to Cycles for baking
        bpy.context.scene.render.engine = "CYCLES"
        bpy.context.scene.cycles.samples = samples

        # Configure selection
        bpy.ops.object.select_all(action="DESELECT")

        if source_object:
            # Selected-to-active bake: select source (high-poly), then target
            source = bpy.data.objects.get(source_object)
            if source is None:
                raise ValueError(f"Source object not found: {source_object}")
            source.select_set(True)
            target.select_set(True)
            bpy.context.view_layer.objects.active = target
        else:
            # Self-bake
            target.select_set(True)
            bpy.context.view_layer.objects.active = target

        # Find and activate the target image texture node
        node_found = False
        for mat_slot in target.material_slots:
            mat = mat_slot.material
            if mat is None or not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if (
                    node.type == "TEX_IMAGE"
                    and node.image is not None
                    and node.image.name == image_name
                ):
                    node.select = True
                    mat.node_tree.nodes.active = node
                    node_found = True
                    break
            if node_found:
                break

        if not node_found:
            raise ValueError(
                f"No image texture node with image '{image_name}' "
                f"found on object '{object_name}'"
            )

        # Build bake kwargs
        bake_kwargs: dict[str, Any] = {
            "type": bake_type,
            "margin": margin,
            "use_selected_to_active": bool(source_object),
        }

        if source_object:
            bake_kwargs["cage_extrusion"] = cage_extrusion

        if bake_type == "NORMAL":
            bake_kwargs["normal_space"] = "TANGENT"

        # Execute bake with context override
        ctx = get_3d_context_override()
        if ctx is not None:
            with bpy.context.temp_override(**ctx):
                bpy.ops.object.bake(**bake_kwargs)
        else:
            bpy.ops.object.bake(**bake_kwargs)

    finally:
        # ALWAYS restore previous render engine
        bpy.context.scene.render.engine = prev_engine

    return {
        "baked": True,
        "bake_type": bake_type,
        "object": object_name,
        "source": source_object,
        "image": image_name,
    }


# ---------------------------------------------------------------------------
# Handler: validate texture
# ---------------------------------------------------------------------------

def handle_validate_texture(params: dict) -> dict:
    """Validate textures on an object's materials.

    Params:
        object_name (str): Object to validate
        texture_size (int, optional): Expected texture size for UV coverage check

    Returns dict with object_name, textures list, uv_coverage_pct, overall_valid.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")

    textures: list[dict[str, Any]] = []
    overall_valid = True

    # Inspect all materials on the object
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue

        for node in mat.node_tree.nodes:
            if node.type != "TEX_IMAGE" or node.image is None:
                continue

            img = node.image
            width, height = img.size[0], img.size[1]
            fmt = img.file_format if hasattr(img, "file_format") else "UNKNOWN"
            cs = (
                img.colorspace_settings.name
                if hasattr(img, "colorspace_settings")
                else "UNKNOWN"
            )

            validation = _validate_texture_metadata(width, height, fmt, cs)
            validation["name"] = img.name

            if validation["issues"]:
                overall_valid = False

            textures.append(validation)

    # UV coverage estimation
    uv_coverage_pct = 0.0
    if (
        obj.type == "MESH"
        and obj.data is not None
        and hasattr(obj.data, "uv_layers")
        and obj.data.uv_layers
    ):
        uv_coverage_pct = _estimate_uv_coverage(obj)

    return {
        "object_name": object_name,
        "textures": textures,
        "uv_coverage_pct": round(uv_coverage_pct, 2),
        "overall_valid": overall_valid,
    }


def _estimate_uv_coverage(obj: Any) -> float:
    """Estimate UV coverage percentage via sampling.

    Approximate the fraction of UV space [0,1]x[0,1] occupied by UV islands.
    Uses a grid sampling approach for speed.
    """
    import bmesh

    mesh = obj.data
    if not mesh.uv_layers:
        return 0.0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        return 0.0

    # Sum UV face areas using shoelace formula
    total_uv_area = 0.0
    for face in bm.faces:
        uvs = [loop[uv_layer].uv for loop in face.loops]
        n = len(uvs)
        if n < 3:
            continue
        # Shoelace formula
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += uvs[i].x * uvs[j].y
            area -= uvs[j].x * uvs[i].y
        total_uv_area += abs(area) / 2.0

    bm.free()

    # UV space is [0,1]x[0,1] = area 1.0
    # Coverage is total UV area (clamped to 100%)
    return min(total_uv_area * 100.0, 100.0)
