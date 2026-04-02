"""Texture handlers for PBR material creation, baking, and validation.

Provides three command handlers:
  - handle_create_pbr_material: Build a full PBR node tree with image textures
  - handle_bake_textures: Bake texture maps (high-to-low-poly or self-bake)
  - handle_validate_texture: Validate texture resolution, format, colorspace, UV coverage
"""

from __future__ import annotations

import math
import os
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

    # Texel density estimation
    texture_resolution = 0
    for t in textures:
        res = t.get("resolution", (0, 0))
        if isinstance(res, (list, tuple)) and len(res) >= 2:
            texture_resolution = max(texture_resolution, res[0], res[1])
    texel_density = _estimate_texel_density(obj, texture_resolution, uv_coverage_pct)
    texel_density_valid = texel_density <= 0.0 or (256.0 <= texel_density <= 2048.0)
    texel_density_issues: list[str] = []
    if texel_density > 0.0:
        if texel_density < 256.0:
            texel_density_issues.append(
                f"Texel density {texel_density:.1f} px/m is below minimum 256 px/m — texture will appear blurry up close."
            )
            overall_valid = False
        elif texel_density > 2048.0:
            texel_density_issues.append(
                f"Texel density {texel_density:.1f} px/m exceeds maximum 2048 px/m — texture resolution wasted."
            )
            overall_valid = False

    return {
        "object_name": object_name,
        "textures": textures,
        "uv_coverage_pct": round(uv_coverage_pct, 2),
        "texel_density": round(texel_density, 2),
        "texel_density_valid": texel_density_valid,
        "texel_density_issues": texel_density_issues,
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


def _estimate_texel_density(obj: Any, texture_resolution: int, uv_coverage_pct: float) -> float:
    """Estimate texel density in pixels per metre.

    Uses the object's bounding box world-space dimensions to approximate the
    surface area, then derives the effective world-space UV island size from
    the UV coverage fraction.

    Formula: texel_density = texture_resolution / uv_island_world_size
    where uv_island_world_size = sqrt(bbox_surface_area * uv_coverage_fraction)

    Returns 0.0 if inputs are insufficient for a meaningful estimate.
    """
    if texture_resolution <= 0:
        return 0.0

    if obj.type != "MESH" or obj.data is None:
        return 0.0

    # Bounding box dimensions in world space
    try:
        bbox = [obj.matrix_world @ __import__('mathutils').Vector(corner) for corner in obj.bound_box]
        xs = [v.x for v in bbox]
        ys = [v.y for v in bbox]
        zs = [v.z for v in bbox]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        dz = max(zs) - min(zs)
    except Exception:
        return 0.0

    # Approximate surface area of bounding box (open box heuristic: 2*(ab+bc+ca))
    bbox_surface_area = 2.0 * (dx * dy + dy * dz + dz * dx)
    if bbox_surface_area <= 0.0:
        return 0.0

    # Scale by UV coverage fraction to get the world-space area the UVs map to
    uv_fraction = max(0.0, min(1.0, uv_coverage_pct / 100.0))
    if uv_fraction <= 0.0:
        uv_fraction = 1.0  # Assume full coverage if no UV data

    uv_island_world_size = math.sqrt(bbox_surface_area * uv_fraction)
    if uv_island_world_size <= 0.0:
        return 0.0

    return float(texture_resolution) / uv_island_world_size


# ---------------------------------------------------------------------------
# Handler: load extracted textures (Tripo post-processing)
# ---------------------------------------------------------------------------

def handle_load_extracted_textures(params: dict) -> dict:
    """Wire pre-extracted PBR channel PNGs into a Blender PBR node tree.

    Unlike ``handle_create_pbr_material``, this handler does NOT create blank
    placeholder images.  It loads the already-extracted PNG files produced by
    ``glb_texture_extractor.extract_glb_textures`` and connects them to the
    correct Principled BSDF sockets.

    ORM channel handling: the ORM image is loaded as Non-Color and split via a
    Separate RGB node.  G -> Roughness, B -> Metallic, R -> AO multiply before
    Base Color.

    Params:
        object_name (str): Blender object to wire textures into.
        albedo_path (str, optional): Path to albedo (base color) PNG.
        albedo_delit_path (str, optional): Path to de-lit albedo -- preferred
            over albedo_path when present.
        normal_path (str, optional): Path to normal map PNG.
        orm_path (str, optional): Path to ORM-packed PNG (R=AO, G=rough, B=metal).

    Returns:
        Dict with status, channels_loaded (list), warnings (list).
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")

    # Get or create material
    if obj.data is None or not hasattr(obj.data, "materials"):
        raise ValueError(f"Object '{object_name}' does not support materials")

    if obj.data.materials and obj.data.materials[0] is not None:
        mat = obj.data.materials[0]
    else:
        mat = bpy.data.materials.new(name=f"{object_name}_PBR")
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    # Find or create Principled BSDF
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        # Ensure output node exists and is linked
        output = next(
            (n for n in nodes if n.type == "OUTPUT_MATERIAL"), None
        )
        if output is None:
            output = nodes.new("ShaderNodeOutputMaterial")
            output.location = (300, 0)
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    channels_loaded: list[str] = []
    warnings: list[str] = []
    albedo_tex_node = None
    y_pos = 300

    # Helper: load an image file and create a texture node
    def _load_tex(path: str, colorspace: str, label: str):
        nonlocal y_pos
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = colorspace
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.label = label
        tex.location = (-700, y_pos)
        y_pos -= 320
        return tex

    # ------------------------------------------------------------------
    # Albedo (prefer de-lit version)
    # ------------------------------------------------------------------
    albedo_path = params.get("albedo_delit_path") or params.get("albedo_path")
    if albedo_path:
        try:
            albedo_tex = _load_tex(albedo_path, "sRGB", "Albedo")
            albedo_tex_node = albedo_tex
            base_color_socket = _get_bsdf_input(bsdf, "base_color")
            links.new(albedo_tex.outputs["Color"], base_color_socket)
            channels_loaded.append("albedo")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Failed to load albedo: {exc}")

    # ------------------------------------------------------------------
    # ORM: load as Non-Color, split R/G/B via Separate RGB node
    # ------------------------------------------------------------------
    orm_path = params.get("orm_path")
    if orm_path:
        try:
            orm_tex = _load_tex(orm_path, "Non-Color", "ORM")
            sep = nodes.new("ShaderNodeSeparateRGB")
            sep.location = (-400, y_pos + 160)

            links.new(orm_tex.outputs["Color"], sep.inputs["Image"])

            # G -> Roughness
            rough_socket = _get_bsdf_input(bsdf, "roughness")
            links.new(sep.outputs["G"], rough_socket)

            # B -> Metallic
            metal_socket = _get_bsdf_input(bsdf, "metallic")
            links.new(sep.outputs["B"], metal_socket)

            # R -> AO multiply before Base Color (if albedo loaded)
            if albedo_tex_node is not None:
                ao_mix = nodes.new("ShaderNodeMixRGB")
                ao_mix.blend_type = "MULTIPLY"
                ao_mix.inputs["Fac"].default_value = 1.0
                ao_mix.location = (-200, 300)

                # Reconnect: albedo -> Mix A, AO R -> Mix B, Mix -> Base Color
                base_color_socket = _get_bsdf_input(bsdf, "base_color")
                # Remove existing albedo -> base_color link
                for link in list(links):
                    if (
                        link.to_socket == base_color_socket
                        and link.from_node == albedo_tex_node
                    ):
                        links.remove(link)
                links.new(albedo_tex_node.outputs["Color"], ao_mix.inputs["Color1"])
                links.new(sep.outputs["R"], ao_mix.inputs["Color2"])
                links.new(ao_mix.outputs["Color"], base_color_socket)

            channels_loaded.append("orm")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Failed to load ORM: {exc}")

    # ------------------------------------------------------------------
    # Normal map
    # ------------------------------------------------------------------
    normal_path = params.get("normal_path")
    if normal_path:
        try:
            normal_tex = _load_tex(normal_path, "Non-Color", "Normal")
            normal_map_node = nodes.new("ShaderNodeNormalMap")
            normal_map_node.location = (-400, y_pos + 160)
            links.new(normal_tex.outputs["Color"], normal_map_node.inputs["Color"])
            normal_socket = _get_bsdf_input(bsdf, "normal")
            links.new(normal_map_node.outputs["Normal"], normal_socket)
            channels_loaded.append("normal")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Failed to load normal: {exc}")

    return {
        "status": "success",
        "channels_loaded": channels_loaded,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Handler: generate wear map (per-vertex curvature via bmesh)
# ---------------------------------------------------------------------------

def handle_generate_wear_map(params: dict) -> dict:
    """Compute per-vertex curvature via bmesh for wear map generation.

    Params:
        object_name (str): Mesh object to analyze.

    Returns:
        Dict with object_name, vertex_count, curvature_data mapping
        vertex_index to curvature value, and uv_data for texture rendering.
    """
    import bmesh

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is type '{obj.type}', expected 'MESH'")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Compute per-vertex curvature as average angle defect:
    # curvature = 2*pi - sum(face_angles_at_vertex) for boundary awareness
    curvature_data: dict[int, float] = {}
    for vert in bm.verts:
        if not vert.link_faces:
            curvature_data[vert.index] = 0.0
            continue

        # Sum the face angles at this vertex
        angle_sum = 0.0
        for face in vert.link_faces:
            # Find the angle at this vertex in this face
            for loop in face.loops:
                if loop.vert == vert:
                    angle_sum += loop.calc_angle()
                    break

        # Angle defect: positive = convex, negative = concave
        curvature_data[vert.index] = 2.0 * math.pi - angle_sum

    # Extract UV data for texture rendering
    uv_data: list[list] = []
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is not None:
        for face in bm.faces:
            face_uvs = []
            for loop in face.loops:
                uv = loop[uv_layer].uv
                face_uvs.append((loop.vert.index, uv.x, uv.y))
            uv_data.append(face_uvs)

    vertex_count = len(bm.verts)
    bm.free()

    return {
        "object_name": object_name,
        "vertex_count": vertex_count,
        "curvature_data": curvature_data,
        "uv_data": uv_data,
    }


# ---------------------------------------------------------------------------
# Handler: get UV region for material slot
# ---------------------------------------------------------------------------

def handle_get_uv_region(params: dict) -> dict:
    """Extract UV polygons for a specific material slot via bmesh.

    Params:
        object_name (str): Mesh object to query.
        material_index (int, default 0): Material slot index.

    Returns:
        Dict with object_name, material_index, polygons list of UV coordinate lists.
    """
    import bmesh

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    material_index = params.get("material_index", 0)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is type '{obj.type}', expected 'MESH'")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        return {
            "object_name": object_name,
            "material_index": material_index,
            "polygons": [],
            "error": "No active UV layer",
        }

    polygons: list[list[list[float]]] = []
    for face in bm.faces:
        if face.material_index == material_index:
            poly = []
            for loop in face.loops:
                uv = loop[uv_layer].uv
                poly.append([uv.x, uv.y])
            polygons.append(poly)

    bm.free()

    return {
        "object_name": object_name,
        "material_index": material_index,
        "polygons": polygons,
    }


# ---------------------------------------------------------------------------
# Handler: get seam pixel coordinates
# ---------------------------------------------------------------------------

def handle_get_seam_pixels(params: dict) -> dict:
    """Extract UV seam edge pixel coordinates from a mesh.

    Params:
        object_name (str): Mesh object to query.
        texture_size (int, default 1024): Texture resolution for pixel mapping.

    Returns:
        Dict with object_name, texture_size, seam_pixels list of [x, y] pairs.
    """
    import bmesh

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    texture_size = params.get("texture_size", 1024)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is type '{obj.type}', expected 'MESH'")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        return {
            "object_name": object_name,
            "texture_size": texture_size,
            "seam_pixels": [],
            "error": "No active UV layer",
        }

    seam_pixels: list[list[int]] = []
    seen: set[tuple[int, int]] = set()

    for edge in bm.edges:
        if not edge.seam:
            continue

        # Get UV coordinates for this seam edge from adjacent loops
        for loop in edge.link_loops:
            uv_a = loop[uv_layer].uv
            uv_b = loop.link_loop_next[uv_layer].uv

            # Rasterize the edge into pixel coordinates using Bresenham-like sampling
            x0 = int(uv_a.x * texture_size)
            y0 = int((1.0 - uv_a.y) * texture_size)
            x1 = int(uv_b.x * texture_size)
            y1 = int((1.0 - uv_b.y) * texture_size)

            # Clamp to texture bounds
            x0 = max(0, min(x0, texture_size - 1))
            y0 = max(0, min(y0, texture_size - 1))
            x1 = max(0, min(x1, texture_size - 1))
            y1 = max(0, min(y1, texture_size - 1))

            # Simple line rasterization
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            steps = max(dx, dy, 1)
            for s in range(steps + 1):
                t = s / steps
                px = round(x0 + t * (x1 - x0))
                py = round(y0 + t * (y1 - y0))
                key = (px, py)
                if key not in seen:
                    seen.add(key)
                    seam_pixels.append([px, py])

    bm.free()

    return {
        "object_name": object_name,
        "texture_size": texture_size,
        "seam_pixels": seam_pixels,
    }


# ---------------------------------------------------------------------------
# Handler: bake procedural materials to image textures
# ---------------------------------------------------------------------------

# PBR channels to bake, with their bake type, pass_filter, and colorspace.
_PROCEDURAL_BAKE_CHANNELS: dict[str, tuple[str, set[str] | None, str]] = {
    "albedo": ("DIFFUSE", {"COLOR"}, "sRGB"),
    "normal": ("NORMAL", None, "Non-Color"),
    "roughness": ("ROUGHNESS", None, "Non-Color"),
    "metallic": ("EMIT", None, "Non-Color"),  # metallic baked via emission trick
    "ao": ("AO", None, "Non-Color"),
}


def _prepare_bake_image(
    name: str, width: int, height: int, colorspace: str
) -> "bpy.types.Image":
    """Create or get a blank image for baking."""
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, width, height, alpha=False)
    img.colorspace_settings.name = colorspace
    return img


def _set_active_image_node(obj: Any, image: Any) -> bool:
    """Set the active image texture node on all materials of an object.

    Creates a temporary image texture node if one doesn't exist, sets it
    as active and selected for baking. Returns True if at least one
    material was configured.
    """
    configured = False
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue
        tree = mat.node_tree
        # Look for an existing image texture node with this image
        target_node = None
        for node in tree.nodes:
            if node.type == "TEX_IMAGE" and node.image == image:
                target_node = node
                break
        if target_node is None:
            # Create a temporary bake target node
            target_node = tree.nodes.new("ShaderNodeTexImage")
            target_node.name = f"_bake_target_{image.name}"
            target_node.location = (-800, 0)
            target_node.image = image
        # Set as active and selected
        for node in tree.nodes:
            node.select = False
        target_node.select = True
        tree.nodes.active = target_node
        configured = True
    return configured


def _save_baked_image(image: Any, output_dir: str, filename: str) -> str:
    """Save a baked Blender image to disk as PNG."""
    filepath = os.path.join(output_dir, f"{filename}.png")
    image.filepath_raw = filepath
    image.file_format = "PNG"
    image.save()
    return filepath


def _cleanup_bake_nodes(obj: Any) -> None:
    """Remove temporary bake target nodes from all materials."""
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue
        tree = mat.node_tree
        to_remove = [n for n in tree.nodes if n.name.startswith("_bake_target_")]
        for node in to_remove:
            tree.nodes.remove(node)


def _bake_metallic_via_emission(obj: Any, image: Any, samples: int) -> None:
    """Bake the metallic channel by temporarily rewiring it through Emission.

    The Metallic input is a scalar that Cycles cannot bake directly.
    We temporarily disconnect the metallic source, wire it to an Emission
    shader output, bake EMIT, then restore the original connections.
    """
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue
        tree = mat.node_tree
        bsdf = None
        for node in tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break
        if bsdf is None:
            continue

        metallic_input = bsdf.inputs.get("Metallic")
        if metallic_input is None:
            continue

        # Check if metallic has a connected link
        if metallic_input.links:
            source_socket = metallic_input.links[0].from_socket
        else:
            # Create a Value node with the default metallic value
            val_node = tree.nodes.new("ShaderNodeValue")
            val_node.name = "_bake_metallic_value"
            val_node.outputs[0].default_value = metallic_input.default_value
            source_socket = val_node.outputs[0]

        # Create emission shader and wire metallic source to it
        emit_node = tree.nodes.new("ShaderNodeEmission")
        emit_node.name = "_bake_metallic_emit"
        emit_node.location = (200, -200)

        # Connect metallic source -> emission color (as grayscale)
        tree.links.new(source_socket, emit_node.inputs["Color"])

        # Find output node and store original connection
        output_node = None
        original_link_socket = None
        for node in tree.nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
                if output_node.inputs["Surface"].links:
                    original_link_socket = output_node.inputs["Surface"].links[0].from_socket
                break

        if output_node is not None:
            # Wire emission to output
            tree.links.new(emit_node.outputs["Emission"], output_node.inputs["Surface"])

    # Bake EMIT
    ctx = get_3d_context_override()
    bake_kwargs = {"type": "EMIT", "margin": 16}
    if ctx is not None:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.bake(**bake_kwargs)
    else:
        bpy.ops.object.bake(**bake_kwargs)

    # Restore original connections
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue
        tree = mat.node_tree
        # Remove temporary nodes
        for nname in ("_bake_metallic_emit", "_bake_metallic_value"):
            node = tree.nodes.get(nname)
            if node is not None:
                tree.nodes.remove(node)
        # Re-link original output
        output_node = None
        bsdf = None
        for node in tree.nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
            elif node.type == "BSDF_PRINCIPLED":
                bsdf = node
        if output_node is not None and bsdf is not None:
            tree.links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])


def handle_bake_procedural_to_images(params: dict) -> dict:
    """Bake procedural materials to image textures for export.

    This is CRITICAL for FBX/glTF export -- procedural shader nodes
    (Noise, Voronoi, Musgrave, etc.) do not survive export. This handler
    bakes each PBR channel to an image texture and optionally replaces
    the procedural nodes with Image Texture nodes.

    Params:
        object_name (str): Object with procedural materials.
        resolution (int, default 2048): Bake resolution (512/1024/2048/4096).
        output_dir (str): Directory to save baked textures.
        channels (list[str], optional): Channels to bake. Default: all 5
            (albedo, normal, roughness, metallic, ao).
        samples (int, default 32): Cycles samples for baking.
        replace_nodes (bool, default True): Replace procedural nodes with
            Image Texture nodes after baking.
        objects (list[str], optional): Multiple objects for batch baking.
            If provided, overrides object_name.

    Returns dict with baked_files, channels, resolution, objects.
    """
    object_name = params.get("object_name")
    resolution = params.get("resolution", 2048)
    output_dir = params.get("output_dir", "//textures/baked")
    channels = params.get("channels", list(_PROCEDURAL_BAKE_CHANNELS.keys()))
    samples = params.get("samples", 32)
    replace_nodes = params.get("replace_nodes", True)
    objects_list = params.get("objects")

    # Build list of objects to process
    if objects_list:
        obj_names = objects_list
    elif object_name:
        obj_names = [object_name]
    else:
        raise ValueError("'object_name' or 'objects' is required")

    # Resolve output directory (support Blender relative paths)
    abs_output_dir = bpy.path.abspath(output_dir)
    os.makedirs(abs_output_dir, exist_ok=True)

    prev_engine = bpy.context.scene.render.engine
    prev_samples = bpy.context.scene.cycles.samples

    all_baked: dict[str, dict[str, str]] = {}

    try:
        bpy.context.scene.render.engine = "CYCLES"
        bpy.context.scene.cycles.samples = samples
        # Use GPU if available, CPU otherwise
        bpy.context.scene.cycles.device = "GPU"

        for oname in obj_names:
            obj = bpy.data.objects.get(oname)
            if obj is None:
                raise ValueError(f"Object not found: {oname}")
            if obj.type != "MESH":
                raise ValueError(f"Object '{oname}' is type '{obj.type}', expected 'MESH'")

            # Ensure object has UVs
            if not obj.data.uv_layers:
                raise ValueError(f"Object '{oname}' has no UV layers. UV unwrap first.")

            # Select and activate
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            obj_baked: dict[str, str] = {}

            for ch_name in channels:
                if ch_name not in _PROCEDURAL_BAKE_CHANNELS:
                    continue

                bake_type, pass_filter, colorspace = _PROCEDURAL_BAKE_CHANNELS[ch_name]
                img_name = f"{oname}_{ch_name}"
                image = _prepare_bake_image(img_name, resolution, resolution, colorspace)

                # Set this image as active bake target on all materials
                _set_active_image_node(obj, image)

                if ch_name == "metallic":
                    _bake_metallic_via_emission(obj, image, samples)
                else:
                    bake_kwargs: dict[str, Any] = {
                        "type": bake_type,
                        "margin": 16,
                    }
                    if pass_filter is not None:
                        bake_kwargs["pass_filter"] = pass_filter

                    if bake_type == "NORMAL":
                        bake_kwargs["normal_space"] = "TANGENT"

                    ctx = get_3d_context_override()
                    if ctx is not None:
                        with bpy.context.temp_override(**ctx):
                            bpy.ops.object.bake(**bake_kwargs)
                    else:
                        bpy.ops.object.bake(**bake_kwargs)

                # Save to disk
                filepath = _save_baked_image(image, abs_output_dir, img_name)
                obj_baked[ch_name] = filepath

            # Replace procedural nodes with Image Texture nodes
            if replace_nodes:
                _replace_procedural_with_images(obj, obj_baked)

            # Clean up temporary bake target nodes
            _cleanup_bake_nodes(obj)

            all_baked[oname] = obj_baked

    finally:
        bpy.context.scene.render.engine = prev_engine
        bpy.context.scene.cycles.samples = prev_samples

    return {
        "baked_files": all_baked,
        "channels": channels,
        "resolution": resolution,
        "output_dir": abs_output_dir,
        "objects": obj_names,
    }


def _replace_procedural_with_images(
    obj: Any, baked_files: dict[str, str]
) -> None:
    """Replace procedural nodes with Image Texture nodes pointing to baked files.

    For each material on the object, removes procedural nodes (Noise, Voronoi,
    Musgrave, etc.) and wires Image Texture nodes to the Principled BSDF.
    """
    channels = _build_channel_config()

    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue
        tree = mat.node_tree

        # Find the Principled BSDF
        bsdf = None
        for node in tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break
        if bsdf is None:
            continue

        # Remove procedural nodes (Noise, Voronoi, Musgrave, Wave, Brick, etc.)
        procedural_types = {
            "TEX_NOISE", "TEX_VORONOI", "TEX_MUSGRAVE", "TEX_WAVE",
            "TEX_BRICK", "TEX_GRADIENT", "TEX_MAGIC", "TEX_CHECKER",
            "BUMP", "MAPPING", "TEX_COORD", "MATH", "MIX_RGB",
            "VALTORGB", "SEPARATE_XYZ", "COMBINE_XYZ",
        }
        to_remove = [
            n for n in tree.nodes
            if n.type in procedural_types and not n.name.startswith("_bake_target_")
        ]
        for node in to_remove:
            tree.nodes.remove(node)

        # Wire image textures for each baked channel
        y_offset = 0
        for ch_name, filepath in baked_files.items():
            if ch_name not in channels:
                continue
            suffix, bsdf_input, colorspace, needs_normal = channels[ch_name]

            tex_node = tree.nodes.new("ShaderNodeTexImage")
            tex_node.location = (-600, y_offset)
            tex_node.label = f"Baked {ch_name}"
            tex_node.image = bpy.data.images.load(filepath)
            tex_node.image.colorspace_settings.name = colorspace

            if needs_normal:
                normal_map = tree.nodes.new("ShaderNodeNormalMap")
                normal_map.location = (-300, y_offset)
                tree.links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
                bsdf_socket = _get_bsdf_input(bsdf, "normal")
                tree.links.new(normal_map.outputs["Normal"], bsdf_socket)
            elif bsdf_input is not None:
                semantic = bsdf_input.lower().replace(" ", "_")
                bsdf_socket = _get_bsdf_input(bsdf, semantic)
                tree.links.new(tex_node.outputs["Color"], bsdf_socket)

            y_offset -= 300


# ---------------------------------------------------------------------------
# Handler: bake material ID map
# ---------------------------------------------------------------------------

def handle_bake_id_map(params: dict) -> dict:
    """Bake a material ID map where each material gets a unique flat color.

    Useful for Substance Painter workflows and material masking.

    Params:
        object_name (str): Object to bake ID map for.
        resolution (int, default 1024): Output resolution.
        output_dir (str): Directory to save the ID map.
        objects (list[str], optional): Multiple objects for batch baking.

    Returns dict with id_map_path, material_colors, resolution.
    """
    object_name = params.get("object_name")
    resolution = params.get("resolution", 1024)
    output_dir = params.get("output_dir", "//textures/baked")
    objects_list = params.get("objects")

    if objects_list:
        obj_names = objects_list
    elif object_name:
        obj_names = [object_name]
    else:
        raise ValueError("'object_name' or 'objects' is required")

    abs_output_dir = bpy.path.abspath(output_dir)
    os.makedirs(abs_output_dir, exist_ok=True)

    prev_engine = bpy.context.scene.render.engine

    result_maps: dict[str, dict] = {}

    try:
        bpy.context.scene.render.engine = "CYCLES"
        bpy.context.scene.cycles.samples = 1  # ID map needs minimal samples

        for oname in obj_names:
            obj = bpy.data.objects.get(oname)
            if obj is None:
                raise ValueError(f"Object not found: {oname}")
            if obj.type != "MESH":
                raise ValueError(f"Object '{oname}' is not a mesh")

            if not obj.data.uv_layers:
                raise ValueError(f"Object '{oname}' has no UV layers")

            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            # Generate unique colors for each material
            mat_count = len(obj.material_slots)
            material_colors: dict[str, list[float]] = {}
            id_colors = _generate_id_colors(mat_count)

            img_name = f"{oname}_id_map"
            image = _prepare_bake_image(img_name, resolution, resolution, "sRGB")

            # Store original material emission values to restore later
            original_emissions: list[tuple[Any, Any, tuple]] = []

            for i, mat_slot in enumerate(obj.material_slots):
                mat = mat_slot.material
                if mat is None:
                    continue
                if not mat.use_nodes:
                    mat.use_nodes = True

                tree = mat.node_tree
                bsdf = None
                for node in tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        bsdf = node
                        break
                if bsdf is None:
                    continue

                color = id_colors[i] if i < len(id_colors) else [1.0, 0.0, 1.0]
                material_colors[mat.name] = color

                # Store original emission color
                emit_input = _get_bsdf_input(bsdf, "emission")
                original_color = list(emit_input.default_value)
                original_emissions.append((bsdf, emit_input, tuple(emit_input.default_value)))

                # Set emission to ID color (temporarily)
                emit_input.default_value = (*color, 1.0)

                # Also disconnect any existing emission links
                for link in list(tree.links):
                    if link.to_socket == emit_input:
                        tree.links.remove(link)

                # Set active image node for baking
                _set_active_image_node(obj, image)

            # Bake EMIT to capture the flat ID colors
            bake_kwargs = {"type": "EMIT", "margin": 16}
            ctx = get_3d_context_override()
            if ctx is not None:
                with bpy.context.temp_override(**ctx):
                    bpy.ops.object.bake(**bake_kwargs)
            else:
                bpy.ops.object.bake(**bake_kwargs)

            # Save the ID map
            filepath = _save_baked_image(image, abs_output_dir, img_name)

            # Restore original emission values
            for bsdf_node, emit_input, orig_color in original_emissions:
                emit_input.default_value = orig_color

            _cleanup_bake_nodes(obj)

            result_maps[oname] = {
                "id_map_path": filepath,
                "material_colors": material_colors,
            }

    finally:
        bpy.context.scene.render.engine = prev_engine

    return {
        "id_maps": result_maps,
        "resolution": resolution,
        "objects": obj_names,
    }


def _generate_id_colors(count: int) -> list[list[float]]:
    """Generate visually distinct colors for material ID map.

    Uses evenly spaced hues in HSV space at full saturation and value
    for maximum visual distinction between materials.
    """
    import colorsys

    colors: list[list[float]] = []
    for i in range(max(count, 1)):
        hue = i / max(count, 1)
        r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.95)
        colors.append([r, g, b])
    return colors


# ---------------------------------------------------------------------------
# Handler: bake thickness map for SSS
# ---------------------------------------------------------------------------

def handle_bake_thickness_map(params: dict) -> dict:
    """Bake a thickness map for subsurface scattering.

    Bakes AO from inside the mesh (inverted normals) to approximate
    surface thickness. Thin areas (ears, fingers, nostrils) appear
    bright, thick areas appear dark. Used for SSS quality in Unity.

    Params:
        object_name (str): Mesh object to bake.
        resolution (int, default 1024): Output resolution.
        output_dir (str): Directory to save the thickness map.
        samples (int, default 16): Bake samples.
        objects (list[str], optional): Multiple objects for batch baking.

    Returns dict with thickness_map_paths, resolution, objects.
    """
    object_name = params.get("object_name")
    resolution = params.get("resolution", 1024)
    output_dir = params.get("output_dir", "//textures/baked")
    samples = params.get("samples", 16)
    objects_list = params.get("objects")

    if objects_list:
        obj_names = objects_list
    elif object_name:
        obj_names = [object_name]
    else:
        raise ValueError("'object_name' or 'objects' is required")

    abs_output_dir = bpy.path.abspath(output_dir)
    os.makedirs(abs_output_dir, exist_ok=True)

    prev_engine = bpy.context.scene.render.engine
    prev_samples = bpy.context.scene.cycles.samples

    result_maps: dict[str, str] = {}

    try:
        bpy.context.scene.render.engine = "CYCLES"
        bpy.context.scene.cycles.samples = samples

        for oname in obj_names:
            obj = bpy.data.objects.get(oname)
            if obj is None:
                raise ValueError(f"Object not found: {oname}")
            if obj.type != "MESH":
                raise ValueError(f"Object '{oname}' is not a mesh")
            if not obj.data.uv_layers:
                raise ValueError(f"Object '{oname}' has no UV layers")

            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            img_name = f"{oname}_thickness"
            image = _prepare_bake_image(img_name, resolution, resolution, "Non-Color")
            _set_active_image_node(obj, image)

            # Flip normals temporarily to bake AO from inside
            bpy.ops.object.mode_set(mode="EDIT")
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
            bmesh.update_edit_mesh(obj.data)
            bpy.ops.object.mode_set(mode="OBJECT")

            try:
                # Bake AO (from inside)
                bake_kwargs = {"type": "AO", "margin": 16}
                ctx = get_3d_context_override()
                if ctx is not None:
                    with bpy.context.temp_override(**ctx):
                        bpy.ops.object.bake(**bake_kwargs)
                else:
                    bpy.ops.object.bake(**bake_kwargs)
            finally:
                # Always flip normals back, even if bake fails
                bpy.ops.object.mode_set(mode="EDIT")
                bm = bmesh.from_edit_mesh(obj.data)
                bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
                bmesh.update_edit_mesh(obj.data)
                bpy.ops.object.mode_set(mode="OBJECT")

            # Save
            filepath = _save_baked_image(image, abs_output_dir, img_name)
            result_maps[oname] = filepath

            _cleanup_bake_nodes(obj)

    finally:
        bpy.context.scene.render.engine = prev_engine
        bpy.context.scene.cycles.samples = prev_samples

    return {
        "thickness_maps": result_maps,
        "resolution": resolution,
        "objects": obj_names,
    }


# ---------------------------------------------------------------------------
# Handler: channel packing (R=Metallic, G=Roughness, B=AO)
# ---------------------------------------------------------------------------

def handle_channel_pack(params: dict) -> dict:
    """Pack multiple grayscale textures into a single RGB channel-packed texture.

    Default packing: R=Metallic, G=Roughness, B=AO.
    Reduces draw calls and texture memory in Unity.

    Params:
        red_path (str): Path to image for red channel (metallic).
        green_path (str): Path to image for green channel (roughness).
        blue_path (str): Path to image for blue channel (AO).
        output_path (str): Path to save the packed texture.
        resolution (int, optional): Override resolution. If not set,
            uses the resolution of the first input image.

    Returns dict with output_path, resolution, channels.
    """
    import numpy as np
    from PIL import Image as PILImage

    red_path = params.get("red_path")
    green_path = params.get("green_path")
    blue_path = params.get("blue_path")
    output_path = params.get("output_path")
    resolution = params.get("resolution")

    if not output_path:
        raise ValueError("'output_path' is required")

    def _load_channel(path: str | None, res: int) -> "np.ndarray":
        """Load a single grayscale channel, resize to target resolution."""
        if path and os.path.isfile(path):
            img = PILImage.open(path).convert("L")
            if img.size != (res, res):
                img = img.resize((res, res), PILImage.Resampling.LANCZOS)
            return np.array(img, dtype=np.uint8)
        # Default: black (0) for metallic, mid-gray (128) for roughness, white (255) for AO
        return np.zeros((res, res), dtype=np.uint8)

    # Determine resolution from first available image
    if resolution is None:
        for path in (red_path, green_path, blue_path):
            if path and os.path.isfile(path):
                with PILImage.open(path) as img:
                    resolution = img.size[0]
                break
    if resolution is None:
        resolution = 1024

    r_channel = _load_channel(red_path, resolution)
    g_channel = _load_channel(green_path, resolution)
    b_channel = _load_channel(blue_path, resolution)

    # Stack into RGB
    packed = np.stack([r_channel, g_channel, b_channel], axis=-1)
    packed_img = PILImage.fromarray(packed, "RGB")

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    packed_img.save(output_path, format="PNG")

    return {
        "output_path": output_path,
        "resolution": resolution,
        "channels": {
            "red": red_path or "default_black",
            "green": green_path or "default_black",
            "blue": blue_path or "default_black",
        },
    }


# ---------------------------------------------------------------------------
# Handler: ensure flat albedo (de-lighting verification)
# ---------------------------------------------------------------------------

def handle_ensure_flat_albedo(params: dict) -> dict:
    """Verify that an albedo texture has no baked-in lighting.

    Checks for high-contrast shadows and directional lighting artifacts
    in the albedo texture. If detected, flags the texture for de-lighting
    or manual review.

    Params:
        image_path (str): Path to the albedo texture.
        shadow_threshold (float, default 0.35): Maximum acceptable local
            contrast ratio. Higher values are more permissive.
        sample_grid (int, default 8): Grid size for sampling local regions.

    Returns dict with is_flat, issues, contrast_stats, recommendation.
    """
    import numpy as np
    from PIL import Image as PILImage

    image_path = params.get("image_path")
    shadow_threshold = params.get("shadow_threshold", 0.35)
    sample_grid = params.get("sample_grid", 8)

    if not image_path:
        raise ValueError("'image_path' is required")

    if not os.path.isfile(image_path):
        raise ValueError(f"Image file not found: {image_path}")

    img = PILImage.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.float64) / 255.0
    width, height = img.size

    # Convert to luminance for analysis
    luminance = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]

    # Analyze local contrast in grid cells
    cell_h = height // sample_grid
    cell_w = width // sample_grid
    issues: list[str] = []
    contrast_values: list[float] = []
    high_contrast_cells = 0

    for gy in range(sample_grid):
        for gx in range(sample_grid):
            y0 = gy * cell_h
            y1 = min((gy + 1) * cell_h, height)
            x0 = gx * cell_w
            x1 = min((gx + 1) * cell_w, width)

            cell = luminance[y0:y1, x0:x1]
            if cell.size == 0:
                continue

            cell_min = float(np.min(cell))
            cell_max = float(np.max(cell))
            local_contrast = cell_max - cell_min
            contrast_values.append(local_contrast)

            if local_contrast > shadow_threshold:
                high_contrast_cells += 1

    total_cells = sample_grid * sample_grid
    high_contrast_pct = high_contrast_cells / total_cells if total_cells > 0 else 0.0

    # Overall statistics
    global_min = float(np.min(luminance))
    global_max = float(np.max(luminance))
    global_contrast = global_max - global_min
    avg_local_contrast = float(np.mean(contrast_values)) if contrast_values else 0.0

    # Determine if the albedo is flat enough
    is_flat = True
    recommendation = "Albedo is flat -- suitable for PBR workflow."

    if high_contrast_pct > 0.25:
        is_flat = False
        issues.append(
            f"{high_contrast_pct:.0%} of cells have high local contrast "
            f"(threshold: {shadow_threshold}). Likely baked-in shadows."
        )
        recommendation = "Run delight action to remove baked lighting."

    if global_contrast > 0.7:
        is_flat = False
        issues.append(
            f"Global contrast range is {global_contrast:.2f} "
            "(max-min luminance). Exceeds 0.7 threshold."
        )
        if "delight" not in recommendation:
            recommendation = "Run delight action to remove baked lighting."

    if avg_local_contrast > shadow_threshold * 0.6:
        if is_flat:
            issues.append(
                f"Average local contrast ({avg_local_contrast:.3f}) is borderline. "
                "Consider manual review."
            )
            recommendation = "Borderline -- manually verify in-engine."
            # Keep is_flat True but flag for review

    return {
        "is_flat": is_flat,
        "issues": issues,
        "contrast_stats": {
            "global_contrast": round(global_contrast, 4),
            "avg_local_contrast": round(avg_local_contrast, 4),
            "high_contrast_cells_pct": round(high_contrast_pct, 4),
            "global_min_luminance": round(global_min, 4),
            "global_max_luminance": round(global_max, 4),
        },
        "recommendation": recommendation,
        "image_path": image_path,
    }


# ---------------------------------------------------------------------------
# Detail Texture Handler
# ---------------------------------------------------------------------------

def handle_apply_detail_texture(params: dict) -> dict:
    """Apply a close-up detail texture overlay to an object's material.

    Inserts camera-distance-dependent noise overlay nodes (using
    DETAIL_TEXTURE_TYPES presets from texture_quality) into the object's
    active material node tree.

    Params:
        object_name (str): Target object name.
        detail_type (str, default "stone_pores"): One of DETAIL_TEXTURE_TYPES keys.
            Valid types: stone_pores, wood_grain, metal_brushed, fabric_weave,
            leather_grain, rust_pitting, moss_micro, sand_grain, ice_crystal,
            bark_texture, bone_surface, crystal_facets.
        detail_scale (float, default 20.0): Texture tiling scale (1-100).
        detail_strength (float, default 0.3): Normal/color influence (0-1).
        blend_distance (float, default 5.0): Metres at which detail fades in (0.5-50).

    Returns dict with status, object_name, detail_type, code_executed.
    """
    from .texture_quality import generate_detail_texture_setup_code, VALID_DETAIL_TYPES

    object_name = params.get("object_name", "")
    detail_type = params.get("detail_type", "stone_pores")
    detail_scale = float(params.get("detail_scale", 20.0))
    detail_strength = float(params.get("detail_strength", 0.3))
    blend_distance = float(params.get("blend_distance", 5.0))

    if not object_name:
        raise ValueError("'object_name' is required")

    if detail_type not in VALID_DETAIL_TYPES:
        raise ValueError(
            f"Unknown detail_type '{detail_type}'. "
            f"Valid types: {sorted(VALID_DETAIL_TYPES)}"
        )

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return {"status": "error", "error": f"Object '{object_name}' not found"}

    if obj.type != "MESH":
        return {"status": "error", "error": f"Object '{object_name}' is not a mesh (type={obj.type})"}

    # Generate and execute the detail texture setup code
    code = generate_detail_texture_setup_code(
        object_name=object_name,
        detail_type=detail_type,
        detail_scale=detail_scale,
        detail_strength=detail_strength,
        blend_distance=blend_distance,
    )

    try:
        exec(compile(code, "<detail_texture_setup>", "exec"))  # noqa: S102
        return {
            "status": "success",
            "object_name": object_name,
            "detail_type": detail_type,
            "detail_scale": detail_scale,
            "detail_strength": detail_strength,
            "blend_distance": blend_distance,
            "code_executed": True,
        }
    except Exception as exc:
        return {
            "status": "error",
            "object_name": object_name,
            "detail_type": detail_type,
            "error": str(exc),
            "code_executed": False,
        }
