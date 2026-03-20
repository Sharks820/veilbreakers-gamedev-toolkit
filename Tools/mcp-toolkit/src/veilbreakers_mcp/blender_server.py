import atexit
import json
import logging
import os
from typing import Literal

from mcp.server.fastmcp import FastMCP, Image
from veilbreakers_mcp.shared.blender_client import BlenderConnection, BlenderCommandError
from veilbreakers_mcp.shared.config import Settings
from veilbreakers_mcp.shared.security import validate_code
from veilbreakers_mcp.shared.image_utils import compose_contact_sheet, resize_screenshot
from veilbreakers_mcp.shared.texture_ops import (
    apply_hsv_adjustment,
    blend_seams,
    generate_uv_mask,
    make_tileable,
    render_wear_map,
    inpaint_texture,
)
from veilbreakers_mcp.shared.texture_validation import validate_texture_file
from veilbreakers_mcp.shared.esrgan_runner import upscale_texture
from veilbreakers_mcp.shared.tripo_client import TripoGenerator
from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner
from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
from veilbreakers_mcp.shared.fal_client import (
    generate_concept_art,
    extract_color_palette,
    compose_style_board,
    test_silhouette_readability,
)
from veilbreakers_mcp.shared.delight import delight_albedo
from veilbreakers_mcp.shared.palette_validator import validate_palette as _validate_palette, validate_roughness_map

logger = logging.getLogger("veilbreakers_mcp")

settings = Settings()
mcp = FastMCP(
    "veilbreakers-blender",
    instructions="VeilBreakers Blender game development tools",
)

_connection: BlenderConnection | None = None


def get_blender_connection() -> BlenderConnection:
    global _connection
    if _connection is None:
        logger.info("Connecting to Blender at %s:%s", settings.blender_host, settings.blender_port)
        _connection = BlenderConnection(
            host=settings.blender_host,
            port=settings.blender_port,
            timeout=settings.blender_timeout,
        )
        # No eager connect() -- the server uses connection-per-command,
        # so _sync_send() calls reconnect() before each command.
        # An eager connect() would open a socket that the server handles
        # as a real client connection, wasting a server thread.
    return _connection


def _cleanup_connection():
    global _connection
    if _connection is not None:
        _connection.disconnect()
        _connection = None


atexit.register(_cleanup_connection)


async def _with_screenshot(
    blender: BlenderConnection, result: dict, capture: bool = True
) -> list:
    """Return structured result + viewport screenshot for mutation tools."""
    parts: list = [json.dumps(result, indent=2, default=str)]
    if capture:
        try:
            screenshot_bytes = await blender.capture_viewport_bytes()
            parts.append(Image(data=screenshot_bytes, format="png"))
        except (OSError, IOError, BlenderCommandError, ConnectionError) as e:
            parts.append(f"[Screenshot capture failed: {e}]")
    return parts


@mcp.tool()
async def blender_scene(
    action: Literal["inspect", "clear", "configure", "list_objects"],
    render_engine: str | None = None,
    fps: int | None = None,
    unit_scale: float | None = None,
):
    """Manage Blender scene state.

    Actions:
    - inspect: Get full scene info (objects, materials, render settings)
    - clear: Remove all objects from scene
    - configure: Set render engine, FPS, unit scale
    - list_objects: Get names and types of all objects
    """
    blender = get_blender_connection()
    if action == "inspect":
        result = await blender.send_command("get_scene_info")
        return json.dumps(result, indent=2, default=str)
    elif action == "clear":
        result = await blender.send_command("clear_scene")
        return await _with_screenshot(blender, result)
    elif action == "configure":
        params = {}
        if render_engine is not None:
            params["render_engine"] = render_engine
        if fps is not None:
            params["fps"] = fps
        if unit_scale is not None:
            params["unit_scale"] = unit_scale
        result = await blender.send_command("configure_scene", params)
        return await _with_screenshot(blender, result)
    elif action == "list_objects":
        result = await blender.send_command("list_objects")
        return json.dumps(result, indent=2, default=str)
    return "Unknown action"


@mcp.tool()
async def blender_object(
    action: Literal["create", "modify", "delete", "duplicate", "list"],
    name: str | None = None,
    mesh_type: str | None = None,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
    capture_viewport: bool = True,
):
    """Manage Blender objects with visual verification.

    Actions:
    - create: Add new mesh (mesh_type: cube/sphere/cylinder/plane/cone/torus/monkey)
    - modify: Change position/rotation/scale of existing object by name
    - delete: Remove object by name
    - duplicate: Copy object, optionally rename
    - list: List all objects (no screenshot)
    """
    blender = get_blender_connection()

    if action == "list":
        result = await blender.send_command("list_objects")
        return json.dumps(result, indent=2, default=str)

    if action in ("modify", "delete", "duplicate") and not name:
        return f"ERROR: 'name' is required for action '{action}'"
    if action == "create" and not mesh_type:
        return "ERROR: 'mesh_type' is required for action 'create'"

    params = {}
    if name is not None:
        params["name"] = name
    if mesh_type is not None:
        params["mesh_type"] = mesh_type
    if position is not None:
        params["position"] = position
    if rotation is not None:
        params["rotation"] = rotation
    if scale is not None:
        params["scale"] = scale

    cmd_map = {
        "create": "create_object",
        "modify": "modify_object",
        "delete": "delete_object",
        "duplicate": "duplicate_object",
    }
    result = await blender.send_command(cmd_map[action], params)
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_material(
    action: Literal["create", "assign", "modify", "list"],
    name: str | None = None,
    object_name: str | None = None,
    base_color: list[float] | None = None,
    metallic: float | None = None,
    roughness: float | None = None,
    capture_viewport: bool = True,
):
    """Manage Blender materials (basic PBR).

    Actions:
    - create: Create new material with optional PBR properties
    - assign: Assign material to object by name
    - modify: Change material properties
    - list: List all materials (no screenshot)
    """
    blender = get_blender_connection()

    if action == "list":
        result = await blender.send_command("material_list")
        return json.dumps(result, indent=2, default=str)

    if action == "assign" and (not name or not object_name):
        return "ERROR: 'name' and 'object_name' are required for action 'assign'"
    if action in ("modify",) and not name:
        return "ERROR: 'name' is required for action 'modify'"

    params = {}
    if name is not None:
        params["name"] = name
    if object_name is not None:
        params["object_name"] = object_name
    if base_color is not None:
        params["base_color"] = base_color
    if metallic is not None:
        params["metallic"] = metallic
    if roughness is not None:
        params["roughness"] = roughness

    cmd_map = {
        "create": "material_create",
        "assign": "material_assign",
        "modify": "material_modify",
    }
    result = await blender.send_command(cmd_map[action], params)
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_viewport(
    action: Literal["screenshot", "contact_sheet", "set_shading", "navigate"],
    object_name: str | None = None,
    shading_type: str | None = None,
    camera_position: list[float] | None = None,
    camera_target: list[float] | None = None,
    angles: list[list[float]] | None = None,
    resolution: list[int] | None = None,
    max_size: int = 1024,
):
    """Visual verification and viewport control.

    Actions:
    - screenshot: Capture current viewport
    - contact_sheet: Render multi-angle composite of object (default 6 angles)
    - set_shading: Change viewport shading (WIREFRAME, SOLID, MATERIAL, RENDERED)
    - navigate: Move viewport camera to position looking at target
    """
    blender = get_blender_connection()

    if action == "screenshot":
        screenshot_bytes = await blender.capture_viewport_bytes()
        resized = resize_screenshot(screenshot_bytes, max_size=max_size)
        return Image(data=resized, format="png")

    elif action == "contact_sheet":
        if not object_name:
            return "ERROR: 'object_name' is required for contact_sheet"
        params = {"object_name": object_name}
        if angles is not None:
            params["angles"] = angles
        if resolution is not None:
            params["resolution"] = resolution
        result = await blender.send_command("render_contact_sheet", params)
        paths = result.get("paths", [])
        if paths:
            try:
                sheet_bytes = compose_contact_sheet(paths)
                return Image(data=sheet_bytes, format="png")
            finally:
                for p in paths:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
        return "No images rendered for contact sheet"

    elif action == "set_shading":
        if not shading_type:
            return "ERROR: 'shading_type' is required for set_shading"
        result = await blender.send_command(
            "set_shading", {"shading_type": shading_type}
        )
        return await _with_screenshot(blender, result)

    elif action == "navigate":
        if not camera_position or not camera_target:
            return "ERROR: 'camera_position' and 'camera_target' are required for navigate"
        result = await blender.send_command("navigate_camera", {
            "position": camera_position,
            "target": camera_target,
        })
        return await _with_screenshot(blender, result)

    return "Unknown action"


@mcp.tool()
async def blender_execute(
    code: str,
    capture_viewport: bool = True,
):
    """Execute validated Python code in Blender.

    Code is AST-validated against a security whitelist before execution.
    Allowed imports: bpy, mathutils, bmesh, math, random, json.
    Blocked: os, sys, subprocess, socket, exec, eval, getattr, open.
    """
    is_safe, violations = validate_code(code)
    if not is_safe:
        return "SECURITY ERROR: Code validation failed:\n" + "\n".join(
            f"  - {v}" for v in violations
        )

    blender = get_blender_connection()
    result = await blender.send_command("execute_code", {"code": code})
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_export(
    export_format: Literal["fbx", "gltf"],
    filepath: str,
    selected_only: bool = False,
    apply_modifiers: bool = True,
) -> str:
    """Export scene or selection to game-ready format.

    Formats:
    - fbx: FBX export with Unity-compatible settings
    - gltf: glTF 2.0 export
    """
    blender = get_blender_connection()
    cmd = f"export_{export_format}"
    result = await blender.send_command(cmd, {
        "filepath": filepath,
        "selected_only": selected_only,
        "apply_modifiers": apply_modifiers,
    })
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def blender_mesh(
    action: Literal[
        "analyze", "repair", "game_check",
        "select", "edit", "boolean", "retopo", "sculpt"
    ],
    object_name: str,
    # Existing params (analyze/repair/game_check)
    merge_distance: float = 0.0001,
    max_hole_sides: int = 8,
    poly_budget: int = 50000,
    platform: str = "pc",
    # Selection params
    material_index: int | None = None,
    material_name: str | None = None,
    vertex_group: str | None = None,
    face_normal_direction: list[float] | None = None,
    normal_threshold: float = 0.7,
    loose_parts: bool = False,
    # Edit params
    operation: str | None = None,
    offset: list[float] | None = None,
    thickness: float = 0.1,
    depth: float = 0.0,
    axis: str = "X",
    separate_type: str = "SELECTED",
    object_names: list[str] | None = None,
    # Boolean params
    cutter_name: str | None = None,
    remove_cutter: bool = True,
    # Retopo params
    target_faces: int = 4000,
    preserve_sharp: bool = True,
    preserve_boundary: bool = True,
    smooth_normals: bool = True,
    use_symmetry: bool = False,
    seed: int = 0,
    # Sculpt params
    strength: float = 0.5,
    iterations: int = 3,
    capture_viewport: bool = True,
):
    """Mesh topology analysis, repair, editing, booleans, retopology, and sculpting.

    Actions:
    - analyze: Full topology analysis with A-F grading
    - repair: Auto-repair pipeline (remove doubles, fix normals, fill holes)
    - game_check: Composite game-readiness validation
    - select: Select geometry by material, vertex group, face normal, or loose parts
    - edit: Surgical mesh editing (extrude, inset, mirror, separate, join)
    - boolean: Boolean operations (union, difference, intersect) with another object
    - retopo: Retopology via Quadriflow with target face count
    - sculpt: Sculpt operations (smooth, inflate, flatten, crease)
    """
    blender = get_blender_connection()

    if action == "analyze":
        result = await blender.send_command(
            "mesh_analyze_topology", {"object_name": object_name}
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "repair":
        result = await blender.send_command(
            "mesh_auto_repair",
            {
                "object_name": object_name,
                "merge_distance": merge_distance,
                "max_hole_sides": max_hole_sides,
            },
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "game_check":
        result = await blender.send_command(
            "mesh_check_game_ready",
            {
                "object_name": object_name,
                "poly_budget": poly_budget,
                "platform": platform,
            },
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "select":
        params: dict = {"object_name": object_name}
        if material_index is not None:
            params["material_index"] = material_index
        if material_name is not None:
            params["material_name"] = material_name
        if vertex_group is not None:
            params["vertex_group"] = vertex_group
        if face_normal_direction is not None:
            params["face_normal_direction"] = face_normal_direction
            params["normal_threshold"] = normal_threshold
        if loose_parts:
            params["loose_parts"] = loose_parts
        result = await blender.send_command("mesh_select", params)
        return [json.dumps(result, indent=2, default=str)]

    elif action == "edit":
        params = {"object_name": object_name}
        if operation is not None:
            params["operation"] = operation
        if offset is not None:
            params["offset"] = offset
        params["thickness"] = thickness
        params["depth"] = depth
        params["axis"] = axis
        params["separate_type"] = separate_type
        if object_names is not None:
            params["object_names"] = object_names
        result = await blender.send_command("mesh_edit", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "boolean":
        params = {
            "object_name": object_name,
            "operation": operation or "DIFFERENCE",
            "remove_cutter": remove_cutter,
        }
        if cutter_name is not None:
            params["cutter_name"] = cutter_name
        result = await blender.send_command("mesh_boolean", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "retopo":
        result = await blender.send_command(
            "mesh_retopologize",
            {
                "object_name": object_name,
                "target_faces": target_faces,
                "preserve_sharp": preserve_sharp,
                "preserve_boundary": preserve_boundary,
                "smooth_normals": smooth_normals,
                "use_symmetry": use_symmetry,
                "seed": seed,
            },
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "sculpt":
        params = {
            "object_name": object_name,
            "strength": strength,
            "iterations": iterations,
        }
        if operation is not None:
            params["operation"] = operation
        result = await blender.send_command("mesh_sculpt", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return ["Unknown action"]



@mcp.tool()
async def blender_uv(
    action: Literal[
        "analyze",
        "unwrap",
        "unwrap_blender",
        "pack",
        "lightmap",
        "equalize",
        "export_layout",
        "set_layer",
        "ensure_xatlas",
    ],
    object_name: str | None = None,
    texture_size: int = 1024,
    padding: int = 2,
    resolution: int = 1024,
    margin: float = 0.001,
    layer_name: str | None = None,
    method: str = "smart_project",
    angle_limit: float = 66.0,
    max_chart_area: float | None = None,
    normal_deviation_weight: float | None = None,
    max_iterations: int | None = None,
    rotate_charts: bool = True,
    target_density: float | None = None,
    size: int = 1024,
    opacity: float = 0.25,
    capture_viewport: bool = True,
):
    """UV mapping analysis, unwrapping, packing, and optimization.

    Actions:
    - analyze: UV quality analysis (stretch, overlap, island count, texel density, seams)
    - unwrap: Automatic UV unwrap via xatlas (high quality, configurable)
    - unwrap_blender: Blender native UV unwrap (smart_project or angle_based)
    - pack: UV island packing optimization
    - lightmap: Generate lightmap UV2 for Unity (separate from UV1)
    - equalize: Texel density equalization across all UV islands
    - export_layout: Export UV layout as PNG image for visual review
    - set_layer: Set active UV layer by name
    - ensure_xatlas: Install xatlas into Blender Python if not present
    """
    blender = get_blender_connection()

    if action == "analyze":
        result = await blender.send_command(
            "uv_analyze",
            {"object_name": object_name, "texture_size": texture_size},
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "unwrap":
        params = {
            "object_name": object_name,
            "padding": padding,
            "resolution": resolution,
            "rotate_charts": rotate_charts,
        }
        if max_chart_area is not None:
            params["max_chart_area"] = max_chart_area
        if normal_deviation_weight is not None:
            params["normal_deviation_weight"] = normal_deviation_weight
        if max_iterations is not None:
            params["max_iterations"] = max_iterations
        result = await blender.send_command("uv_unwrap_xatlas", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "unwrap_blender":
        result = await blender.send_command(
            "uv_unwrap_blender",
            {"object_name": object_name, "method": method, "angle_limit": angle_limit},
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "pack":
        result = await blender.send_command(
            "uv_pack_islands",
            {"object_name": object_name, "margin": margin},
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "lightmap":
        result = await blender.send_command(
            "uv_generate_lightmap",
            {"object_name": object_name, "padding": padding, "resolution": resolution},
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "equalize":
        params_eq: dict = {
            "object_name": object_name,
            "texture_size": texture_size,
        }
        if target_density is not None:
            params_eq["target_density"] = target_density
        result = await blender.send_command("uv_equalize_density", params_eq)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "export_layout":
        result = await blender.send_command(
            "uv_export_layout",
            {"object_name": object_name, "size": size, "opacity": opacity},
        )
        filepath = result.get("filepath")
        if filepath and os.path.isfile(filepath):
            try:
                with open(filepath, "rb") as f:
                    image_data = f.read()
                return [
                    json.dumps(result, indent=2, default=str),
                    Image(data=image_data, format="png"),
                ]
            finally:
                try:
                    os.unlink(filepath)
                except OSError:
                    pass
        return [json.dumps(result, indent=2, default=str)]

    elif action == "set_layer":
        result = await blender.send_command(
            "uv_set_active_layer",
            {"object_name": object_name, "layer_name": layer_name},
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "ensure_xatlas":
        result = await blender.send_command("uv_ensure_xatlas", {})
        return [json.dumps(result, indent=2, default=str)]

    return ["Unknown action"]


# ---------------------------------------------------------------------------
# Compound tool: blender_texture
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_texture(
    action: Literal[
        "create_pbr", "mask_region", "inpaint", "hsv_adjust",
        "blend_seams", "generate_wear", "bake", "upscale",
        "make_tileable", "validate", "delight", "validate_palette",
    ],
    object_name: str | None = None,
    # PBR creation params
    name: str | None = None,
    texture_dir: str | None = None,
    texture_size: int = 1024,
    # Mask / HSV / blend params
    image_path: str | None = None,
    mask_path: str | None = None,
    material_index: int = 0,
    feather_radius: int = 5,
    hue_shift: float = 0.0,
    saturation_scale: float = 1.0,
    value_scale: float = 1.0,
    blend_radius: int = 6,
    # Inpaint params
    prompt: str | None = None,
    # Bake params
    bake_type: str = "COMBINED",
    source_object: str | None = None,
    image_name: str | None = None,
    margin: int = 16,
    cage_extrusion: float = 0.1,
    samples: int = 32,
    # Upscale params
    scale: int = 4,
    model: str = "realesrgan-x4plus",
    output_path: str | None = None,
    # Tileable params
    overlap_pct: float = 0.15,
    # Delight params
    blur_radius_pct: float = 0.12,
    strength: float = 0.75,
    # Palette validation params
    rules: dict | None = None,
    sample_pixels: int = 10000,
    capture_viewport: bool = True,
):
    """Comprehensive texture operations -- Blender-side and MCP-side.

    Actions:
    - create_pbr: Create full PBR material with image texture nodes
    - mask_region: Generate UV mask for a material slot
    - inpaint: AI texture inpainting (requires fal_key)
    - hsv_adjust: HSV color adjustment on masked region
    - blend_seams: Smooth UV seam boundaries
    - generate_wear: Compute per-vertex curvature wear map
    - bake: Bake texture maps (normal, AO, combined, etc.)
    - upscale: AI upscale via Real-ESRGAN
    - make_tileable: Make texture tile seamlessly
    - validate: Validate textures on object or file
    - delight: Remove baked-in lighting from albedo texture (AAA-01)
    - validate_palette: Validate dark fantasy palette rules on albedo texture (AAA-03)
    """
    blender = get_blender_connection()

    if action == "create_pbr":
        params = {"name": name or "PBR_Material", "texture_size": texture_size}
        if texture_dir:
            params["texture_dir"] = texture_dir
        if object_name:
            params["object_name"] = object_name
        result = await blender.send_command("texture_create_pbr", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "mask_region":
        if not object_name:
            return "ERROR: 'object_name' is required for mask_region"
        # Get UV polygons from Blender for the material slot
        uv_result = await blender.send_command(
            "texture_get_uv_region",
            {"object_name": object_name, "material_index": material_index},
        )
        polygons = uv_result.get("polygons", [])
        mask_bytes = generate_uv_mask(polygons, texture_size, feather_radius)
        return [
            json.dumps({"polygons_count": len(polygons), "texture_size": texture_size}),
            Image(data=mask_bytes, format="png"),
        ]

    elif action == "inpaint":
        if not image_path or not mask_path:
            return "ERROR: 'image_path' and 'mask_path' are required for inpaint"
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        with open(mask_path, "rb") as f:
            msk_bytes = f.read()
        result = inpaint_texture(img_bytes, msk_bytes, prompt or "", fal_key=settings.fal_key or None)
        return json.dumps(result, indent=2, default=str)

    elif action == "hsv_adjust":
        if not image_path or not mask_path:
            return "ERROR: 'image_path' and 'mask_path' are required for hsv_adjust"
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        with open(mask_path, "rb") as f:
            msk_bytes = f.read()
        result_bytes = apply_hsv_adjustment(
            img_bytes, msk_bytes, hue_shift, saturation_scale, value_scale,
        )
        return Image(data=result_bytes, format="png")

    elif action == "blend_seams":
        if not object_name or not image_path:
            return "ERROR: 'object_name' and 'image_path' are required for blend_seams"
        # Get seam pixels from Blender
        seam_result = await blender.send_command(
            "texture_get_seam_pixels",
            {"object_name": object_name, "texture_size": texture_size},
        )
        seam_pixels = [(p[0], p[1]) for p in seam_result.get("seam_pixels", [])]
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        result_bytes = blend_seams(img_bytes, seam_pixels, blend_radius)
        return Image(data=result_bytes, format="png")

    elif action == "generate_wear":
        if not object_name:
            return "ERROR: 'object_name' is required for generate_wear"
        wear_result = await blender.send_command(
            "texture_generate_wear", {"object_name": object_name},
        )
        curvature_data = {
            int(k): v for k, v in wear_result.get("curvature_data", {}).items()
        }
        uv_data = wear_result.get("uv_data")
        wear_bytes = render_wear_map(curvature_data, texture_size, uv_data)
        return [
            json.dumps({
                "object_name": object_name,
                "vertex_count": wear_result.get("vertex_count", 0),
                "texture_size": texture_size,
            }, indent=2, default=str),
            Image(data=wear_bytes, format="png"),
        ]

    elif action == "bake":
        if not object_name or not image_name:
            return "ERROR: 'object_name' and 'image_name' are required for bake"
        params = {
            "object_name": object_name,
            "bake_type": bake_type,
            "image_name": image_name,
            "margin": margin,
            "cage_extrusion": cage_extrusion,
            "samples": samples,
        }
        if source_object:
            params["source_object"] = source_object
        result = await blender.send_command("texture_bake", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "upscale":
        if not image_path:
            return "ERROR: 'image_path' is required for upscale"
        result = await upscale_texture(
            input_path=image_path,
            scale=scale,
            model=model,
            esrgan_path=settings.realesrgan_path,
            output_path=output_path,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "make_tileable":
        if not image_path:
            return "ERROR: 'image_path' is required for make_tileable"
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        result_bytes = make_tileable(img_bytes, overlap_pct)
        return Image(data=result_bytes, format="png")

    elif action == "validate":
        if image_path:
            result = validate_texture_file(image_path)
            return json.dumps(result, indent=2, default=str)
        elif object_name:
            result = await blender.send_command(
                "texture_validate", {"object_name": object_name},
            )
            return await _with_screenshot(blender, result, capture_viewport)
        return "ERROR: 'object_name' or 'image_path' is required for validate"

    elif action == "delight":
        if not image_path:
            return "ERROR: 'image_path' is required for delight"
        if not output_path:
            return "ERROR: 'output_path' is required for delight"
        result = delight_albedo(
            image_path=image_path,
            output_path=output_path,
            blur_radius_pct=blur_radius_pct,
            strength=strength,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "validate_palette":
        if not image_path:
            return "ERROR: 'image_path' is required for validate_palette"
        result = _validate_palette(
            image_path=image_path,
            rules=rules,
            sample_pixels=sample_pixels,
        )
        return json.dumps(result, indent=2, default=str)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: asset_pipeline
# ---------------------------------------------------------------------------

@mcp.tool()
async def asset_pipeline(
    action: Literal[
        "generate_3d", "cleanup", "generate_lods", "validate_export",
        "tag_metadata", "batch_process", "catalog_query", "catalog_add",
        # Equipment operations (Phase 13 -- EQUIP-01/03/04/05)
        "generate_weapon", "split_character", "fit_armor", "render_equipment_icon",
    ],
    # Common params
    object_name: str | None = None,
    # generate_3d params
    prompt: str | None = None,
    image_path: str | None = None,
    output_dir: str = ".",
    # cleanup params
    poly_budget: int = 50000,
    # generate_lods params
    ratios: list[float] | None = None,
    # validate_export params
    filepath: str | None = None,
    # tag_metadata params
    asset_id: str | None = None,
    output_path: str | None = None,
    # batch_process params
    object_names: list[str] | None = None,
    steps: list[str] | None = None,
    # catalog params
    name: str | None = None,
    asset_type: str | None = None,
    path: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    # equipment params (Phase 13 -- EQUIP-01/03/04/05)
    weapon_type: str | None = None,
    parts: list[str] | None = None,
    armor_object_name: str | None = None,
    character_object_name: str | None = None,
    resolution: int = 512,
    camera_distance: float = 2.0,
    camera_angle: str = "front",
    body_types: list[str] | None = None,
    capture_viewport: bool = True,
):
    """Asset pipeline management -- 3D generation, processing, LODs, catalog, equipment.

    Actions:
    - generate_3d: Generate 3D model from text prompt or image via Tripo3D
    - cleanup: Run repair -> UV -> PBR pipeline on AI-generated model
    - generate_lods: Generate LOD chain (LOD0-LOD3) with decimation
    - validate_export: Validate exported FBX/GLB file
    - tag_metadata: Export asset metadata as JSON sidecar
    - batch_process: Run pipeline for multiple objects
    - catalog_query: Search asset catalog by type, tags, status
    - catalog_add: Add asset to catalog database
    - generate_weapon: Generate parametric weapon mesh (EQUIP-01)
    - split_character: Split rigged character into modular parts (EQUIP-03)
    - fit_armor: Fit armor mesh to character (EQUIP-04)
    - render_equipment_icon: Render transparent equipment preview icon (EQUIP-05)
    """
    blender = get_blender_connection()

    if action == "generate_3d":
        if not prompt and not image_path:
            return "ERROR: 'prompt' or 'image_path' is required for generate_3d"
        api_key = settings.tripo_api_key
        if not api_key:
            return json.dumps({
                "status": "unavailable",
                "error": "TRIPO_API_KEY not configured",
            })
        gen = TripoGenerator(api_key=api_key)
        if image_path:
            result = await gen.generate_from_image(image_path, output_dir)
        else:
            result = await gen.generate_from_text(prompt, output_dir)
        return json.dumps(result, indent=2, default=str)

    elif action == "cleanup":
        if not object_name:
            return "ERROR: 'object_name' is required for cleanup"
        runner = PipelineRunner(blender, settings)
        result = await runner.cleanup_ai_model(object_name, poly_budget)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_lods":
        if not object_name:
            return "ERROR: 'object_name' is required for generate_lods"
        params = {"object_name": object_name}
        if ratios:
            params["ratios"] = ratios
        result = await blender.send_command("pipeline_generate_lods", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "validate_export":
        if not filepath:
            return "ERROR: 'filepath' is required for validate_export"
        runner = PipelineRunner(blender, settings)
        result = await runner.validate_export(filepath)
        return json.dumps(result, indent=2, default=str)

    elif action == "tag_metadata":
        if not asset_id or not output_path:
            return "ERROR: 'asset_id' and 'output_path' are required for tag_metadata"
        catalog = AssetCatalog(settings.asset_catalog_db)
        try:
            runner = PipelineRunner(blender, settings)
            result = await runner.tag_metadata(asset_id, output_path, catalog)
            return json.dumps(result, indent=2, default=str)
        finally:
            catalog.close()

    elif action == "batch_process":
        if not object_names:
            return "ERROR: 'object_names' is required for batch_process"
        runner = PipelineRunner(blender, settings)
        result = await runner.batch_process(object_names, steps)
        return json.dumps(result, indent=2, default=str)

    elif action == "catalog_query":
        catalog = AssetCatalog(settings.asset_catalog_db)
        try:
            results = catalog.query_assets(
                asset_type=asset_type,
                tags=tags,
                status=status,
            )
            return json.dumps(results, indent=2, default=str)
        finally:
            catalog.close()

    elif action == "catalog_add":
        if not name or not asset_type or not path:
            return "ERROR: 'name', 'asset_type', and 'path' are required for catalog_add"
        catalog = AssetCatalog(settings.asset_catalog_db)
        try:
            new_id = catalog.add_asset(
                name=name,
                asset_type=asset_type,
                path=path,
                tags=tags,
            )
            return json.dumps({"asset_id": new_id, "status": "added"}, indent=2)
        finally:
            catalog.close()

    # --- Equipment operations (Phase 13) ---

    elif action == "generate_weapon":
        if not weapon_type:
            return "ERROR: 'weapon_type' is required for generate_weapon"
        params = {"weapon_type": weapon_type}
        if object_name:
            params["object_name"] = object_name
        result = await blender.send_command("equipment_generate_weapon", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "split_character":
        if not object_name:
            return "ERROR: 'object_name' is required for split_character"
        params = {"object_name": object_name}
        if parts:
            params["parts"] = parts
        result = await blender.send_command("equipment_split_character", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "fit_armor":
        if not armor_object_name or not character_object_name:
            return "ERROR: 'armor_object_name' and 'character_object_name' are required for fit_armor"
        params = {
            "armor_object_name": armor_object_name,
            "character_object_name": character_object_name,
        }
        if body_types:
            params["body_types"] = body_types
        result = await blender.send_command("equipment_fit_armor", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "render_equipment_icon":
        if not object_name:
            return "ERROR: 'object_name' is required for render_equipment_icon"
        params = {
            "object_name": object_name,
            "resolution": resolution,
            "camera_distance": camera_distance,
            "camera_angle": camera_angle,
        }
        if output_path:
            params["output_path"] = output_path
        result = await blender.send_command("equipment_render_icon", params)
        return json.dumps(result, indent=2, default=str)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: concept_art
# ---------------------------------------------------------------------------

@mcp.tool()
async def concept_art(
    action: Literal["generate", "extract_palette", "style_board", "silhouette_test"],
    # generate params
    prompt: str | None = None,
    style: str = "fantasy",
    width: int = 1024,
    height: int = 1024,
    output_dir: str = ".",
    # palette params
    image_path: str | None = None,
    num_colors: int = 8,
    swatch_size: int = 64,
    # style_board params
    image_paths: list[str] | None = None,
    palette_colors: list[dict] | None = None,
    title: str = "Style Board",
    annotations: list[str] | None = None,
    board_width: int = 2048,
    # silhouette params
    threshold: int = 128,
    min_contrast_ratio: float = 0.3,
    distances: list[float] | None = None,
):
    """Concept art generation and visual analysis tools.

    Actions:
    - generate: Generate concept art via fal.ai FLUX
    - extract_palette: Extract dominant color palette from image
    - style_board: Compose reference style board from multiple images
    - silhouette_test: Test shape readability at game distances
    """
    if action == "generate":
        if not prompt:
            return "ERROR: 'prompt' is required for generate"
        result = generate_concept_art(
            prompt=prompt,
            style=style,
            width=width,
            height=height,
            output_dir=output_dir,
            fal_key=settings.fal_key or None,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "extract_palette":
        if not image_path:
            return "ERROR: 'image_path' is required for extract_palette"
        result = extract_color_palette(image_path, num_colors, swatch_size)
        parts = [json.dumps({
            "colors": result["colors"],
        }, indent=2, default=str)]
        if result.get("swatch_bytes"):
            parts.append(Image(data=result["swatch_bytes"], format="png"))
        return parts

    elif action == "style_board":
        if not image_paths:
            return "ERROR: 'image_paths' is required for style_board"
        board_bytes = compose_style_board(
            images=image_paths,
            palette_colors=palette_colors,
            title=title,
            annotations=annotations,
            board_width=board_width,
        )
        return Image(data=board_bytes, format="png")

    elif action == "silhouette_test":
        if not image_path:
            return "ERROR: 'image_path' is required for silhouette_test"
        result = test_silhouette_readability(
            image_path,
            threshold=threshold,
            min_contrast_ratio=min_contrast_ratio,
            distances=distances,
        )
        return json.dumps(result, indent=2, default=str)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_rig
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_rig(
    action: Literal[
        "analyze_mesh",        # RIG-01: Mesh analysis for rigging
        "apply_template",      # RIG-02: Apply creature rig template
        "build_custom",        # RIG-03: Custom rig from limb library
        "setup_facial",        # RIG-04: Facial rig with expressions
        "setup_ik",            # RIG-05: IK chain setup
        "setup_spring_bones",  # RIG-06: Spring/jiggle bone system
        "auto_weight",         # RIG-07: Auto weight painting
        "test_deformation",    # RIG-08: Deformation test at 8 poses
        "validate",            # RIG-09: Rig validation with grading
        "fix_weights",         # RIG-10: Weight mirror/normalize/smooth
        "setup_ragdoll",       # RIG-11: Ragdoll auto-setup
        "retarget",            # RIG-12: Rig retargeting
        "add_shape_keys",      # RIG-13: Shape keys for expressions/damage
    ],
    object_name: str,
    # Template / custom rig params
    template: str | None = None,
    limb_types: list[str] | None = None,
    # IK params
    bone_name: str | None = None,
    chain_length: int | None = None,
    constraint_type: str | None = None,
    pole_target: str | None = None,
    pole_bone: str | None = None,
    curve_points: list[list[float]] | None = None,
    rotation_limits: dict | None = None,
    # Spring bone params
    bone_names: list[str] | None = None,
    stiffness: float | None = None,
    damping: float | None = None,
    gravity: float | None = None,
    # Weight params
    armature_name: str | None = None,
    operation: str | None = None,
    direction: str | None = None,
    factor: float | None = None,
    repeat: int | None = None,
    threshold: float | None = None,
    # Deformation test params
    pose_names: list[str] | None = None,
    # Ragdoll params
    bone_collider_map: dict | None = None,
    preset: str | None = None,
    # Retarget params
    source_rig: str | None = None,
    target_rig: str | None = None,
    bone_mapping: dict | None = None,
    # Shape key params
    shape_key_name: str | None = None,
    mode: str | None = None,
    vertex_offsets: dict | None = None,
    expression_name: str | None = None,
    # Facial params
    expressions: list[str] | None = None,
    # Visual feedback
    capture_viewport: bool = True,
):
    """Rig creatures for game animation with visual verification.

    Actions:
    - analyze_mesh: Analyze mesh proportions and recommend rig template (RIG-01)
    - apply_template: Apply Rigify creature template (humanoid/quadruped/bird/etc.) (RIG-02)
    - build_custom: Build custom rig from limb library (mix-and-match) (RIG-03)
    - setup_facial: Add facial rig bones + monster expression presets (RIG-04)
    - setup_ik: Add IK constraints (2-bone or spline for tails) (RIG-05)
    - setup_spring_bones: Add spring/jiggle bones for secondary motion (RIG-06)
    - auto_weight: Auto weight paint mesh to armature (RIG-07)
    - test_deformation: Test deformation at 8 standard poses with contact sheet (RIG-08)
    - validate: Validate rig quality (unweighted verts, symmetry, rolls) A-F grade (RIG-09)
    - fix_weights: Normalize/clean/smooth/mirror weights (RIG-10)
    - setup_ragdoll: Auto-generate ragdoll colliders and joints (RIG-11)
    - retarget: Map bones between source and target rigs (RIG-12)
    - add_shape_keys: Create expression/damage shape keys (RIG-13)
    """
    blender = get_blender_connection()

    if action == "analyze_mesh":
        result = await blender.send_command("rig_analyze", {"object_name": object_name})
        return json.dumps(result, indent=2, default=str)

    elif action == "apply_template":
        params = {"object_name": object_name}
        if template is not None:
            params["template"] = template
        result = await blender.send_command("rig_apply_template", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "build_custom":
        params = {"object_name": object_name}
        if limb_types is not None:
            params["limb_types"] = limb_types
        result = await blender.send_command("rig_build_custom", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_facial":
        params = {"rig_name": object_name}
        if expressions is not None:
            params["expressions"] = expressions
        result = await blender.send_command("rig_setup_facial", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_ik":
        params = {"rig_name": object_name}
        if bone_name is not None:
            params["bone_name"] = bone_name
        if chain_length is not None:
            params["chain_length"] = chain_length
        if constraint_type is not None:
            params["constraint_type"] = constraint_type
        if pole_target is not None:
            params["pole_target"] = pole_target
        if pole_bone is not None:
            params["pole_target_bone"] = pole_bone
        if curve_points is not None:
            params["curve_points"] = curve_points
        if rotation_limits is not None:
            params["joint_limits"] = rotation_limits
        result = await blender.send_command("rig_setup_ik", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_spring_bones":
        params = {"rig_name": object_name}
        if bone_names is not None:
            params["bone_names"] = bone_names
        if stiffness is not None:
            params["stiffness"] = stiffness
        if damping is not None:
            params["damping"] = damping
        if gravity is not None:
            params["gravity"] = gravity
        result = await blender.send_command("rig_setup_spring_bones", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "auto_weight":
        params = {"mesh_name": object_name}
        if armature_name is not None:
            params["armature_name"] = armature_name
        result = await blender.send_command("rig_auto_weight", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "test_deformation":
        params = {"rig_name": object_name}
        if pose_names is not None:
            params["pose_names"] = pose_names
        result = await blender.send_command("rig_test_deformation", params)
        # Deformation test returns contact sheet -- always capture
        return await _with_screenshot(blender, result, True)

    elif action == "validate":
        params = {"mesh_name": object_name}
        if armature_name is not None:
            params["armature_name"] = armature_name
        result = await blender.send_command("rig_validate", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "fix_weights":
        params = {"mesh_name": object_name}
        if operation is not None:
            params["operation"] = operation
        if direction is not None:
            params["direction"] = direction
        if factor is not None:
            params["factor"] = factor
        if repeat is not None:
            params["repeat"] = repeat
        if threshold is not None:
            params["threshold"] = threshold
        result = await blender.send_command("rig_fix_weights", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_ragdoll":
        params = {"rig_name": object_name}
        if bone_collider_map is not None:
            params["bone_collider_map"] = bone_collider_map
        if preset is not None:
            params["preset"] = preset
        result = await blender.send_command("rig_setup_ragdoll", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "retarget":
        params = {}
        if source_rig is not None:
            params["source_rig"] = source_rig
        if target_rig is not None:
            params["target_rig"] = target_rig
        if bone_mapping is not None:
            params["mapping"] = bone_mapping
        result = await blender.send_command("rig_retarget", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "add_shape_keys":
        params = {"object_name": object_name}
        if shape_key_name is not None:
            params["shape_key_name"] = shape_key_name
        if mode is not None:
            params["mode"] = mode
        if vertex_offsets is not None:
            params["vertex_offsets"] = vertex_offsets
        if expression_name is not None:
            params["expression_name"] = expression_name
        result = await blender.send_command("rig_add_shape_keys", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_animation
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_animation(
    action: Literal[
        "generate_walk",       # ANIM-01: Procedural walk/run cycle
        "generate_fly",        # ANIM-02: Procedural fly/hover cycle
        "generate_idle",       # ANIM-03: Procedural idle animation
        "generate_attack",     # ANIM-04: Attack animations (8 types)
        "generate_reaction",   # ANIM-05: Death, hit, spawn animations
        "generate_custom",     # ANIM-06: Custom animation from text
        "preview",             # ANIM-07: Animation contact sheet preview
        "add_secondary",       # ANIM-08: Secondary motion physics bake
        "extract_root_motion", # ANIM-09: Root motion + animation events
        "retarget_mixamo",     # ANIM-10: Mixamo animation retargeting
        "generate_ai_motion",  # ANIM-11: AI motion generation (stub)
        "batch_export",        # ANIM-12: Batch export as Unity clips
    ],
    object_name: str,
    # Walk/run cycle params
    gait: str | None = None,           # biped/quadruped/hexapod/arachnid/serpent
    speed: str | None = None,          # walk/run
    frame_count: int | None = None,
    # Fly/hover params
    frequency: float | None = None,
    amplitude: float | None = None,
    glide_ratio: float | None = None,
    # Idle params
    breathing_intensity: float | None = None,
    # Attack params
    attack_type: str | None = None,
    intensity: float | None = None,
    # Reaction params
    reaction_type: str | None = None,
    direction: str | None = None,
    # Custom animation params
    description: str | None = None,
    # Preview params
    action_name: str | None = None,
    frame_step: int | None = None,
    angles: list[str] | None = None,
    resolution: int | None = None,
    # Secondary motion params
    bone_names: list[str] | None = None,
    # Root motion params
    hip_bone: str | None = None,
    root_bone: str | None = None,
    extract_rotation: bool | None = None,
    # Mixamo retarget params
    source_file: str | None = None,
    # AI motion params
    prompt: str | None = None,
    model: str | None = None,
    # Batch export params
    output_dir: str | None = None,
    naming: str | None = None,
    actions: list[str] | None = None,
    # Visual feedback
    capture_viewport: bool = True,
):
    """Generate, preview, and export game-ready animations for rigged creatures.

    Supports procedural gaits (5 types), combat animations (8 attack types + death/hit/spawn),
    custom text-to-animation, contact sheet preview, secondary motion baking, root motion
    extraction, Mixamo retargeting, and batch Unity FBX export.
    """
    blender = get_blender_connection()

    if action == "generate_walk":
        params = {"object_name": object_name}
        if gait is not None:
            params["gait"] = gait
        if speed is not None:
            params["speed"] = speed
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_walk", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_fly":
        params = {"object_name": object_name}
        if frequency is not None:
            params["frequency"] = frequency
        if amplitude is not None:
            params["amplitude"] = amplitude
        if glide_ratio is not None:
            params["glide_ratio"] = glide_ratio
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_fly", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_idle":
        params = {"object_name": object_name}
        if frame_count is not None:
            params["frame_count"] = frame_count
        if breathing_intensity is not None:
            params["breathing_intensity"] = breathing_intensity
        result = await blender.send_command("anim_generate_idle", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_attack":
        params = {"object_name": object_name}
        if attack_type is not None:
            params["attack_type"] = attack_type
        if frame_count is not None:
            params["frame_count"] = frame_count
        if intensity is not None:
            params["intensity"] = intensity
        result = await blender.send_command("anim_generate_attack", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_reaction":
        params = {"object_name": object_name}
        if reaction_type is not None:
            params["reaction_type"] = reaction_type
        if direction is not None:
            params["direction"] = direction
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_reaction", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_custom":
        params = {"object_name": object_name}
        if description is not None:
            params["description"] = description
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_custom", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "preview":
        params = {"object_name": object_name}
        if action_name is not None:
            params["action_name"] = action_name
        if frame_step is not None:
            params["frame_step"] = frame_step
        if angles is not None:
            params["angles"] = angles
        if resolution is not None:
            params["resolution"] = resolution
        result = await blender.send_command("anim_preview", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "add_secondary":
        params = {"object_name": object_name}
        if action_name is not None:
            params["action_name"] = action_name
        if bone_names is not None:
            params["bone_names"] = bone_names
        result = await blender.send_command("anim_add_secondary_motion", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "extract_root_motion":
        params = {"object_name": object_name}
        if action_name is not None:
            params["action_name"] = action_name
        if hip_bone is not None:
            params["hip_bone"] = hip_bone
        if root_bone is not None:
            params["root_bone"] = root_bone
        if extract_rotation is not None:
            params["extract_rotation"] = extract_rotation
        result = await blender.send_command("anim_extract_root_motion", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "retarget_mixamo":
        params = {"object_name": object_name}
        if source_file is not None:
            params["source_file"] = source_file
        if action_name is not None:
            params["action_name"] = action_name
        result = await blender.send_command("anim_retarget_mixamo", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_ai_motion":
        params = {"object_name": object_name}
        if prompt is not None:
            params["prompt"] = prompt
        if model is not None:
            params["model"] = model
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_ai_motion", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "batch_export":
        params = {"object_name": object_name}
        if output_dir is not None:
            params["output_dir"] = output_dir
        if naming is not None:
            params["naming"] = naming
        if actions is not None:
            params["actions"] = actions
        result = await blender.send_command("anim_batch_export", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_environment
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_environment(
    action: Literal[
        "generate_terrain",
        "paint_terrain",
        "carve_river",
        "generate_road",
        "create_water",
        "export_heightmap",
        "scatter_vegetation",
        "scatter_props",
        "create_breakable",
    ],
    # Common params
    name: str | None = None,
    terrain_name: str | None = None,
    seed: int | None = None,
    # generate_terrain params
    terrain_type: str | None = None,
    resolution: int | None = None,
    height_scale: float | None = None,
    scale: float | None = None,
    erosion: str | None = None,
    erosion_iterations: int | None = None,
    octaves: int | None = None,
    persistence: float | None = None,
    lacunarity: float | None = None,
    # paint_terrain params
    biome_rules: list[dict] | None = None,
    # carve_river params
    source: list[int] | None = None,
    destination: list[int] | None = None,
    # road / water / river params
    width: float | None = None,
    depth: float | None = None,
    waypoints: list[list[int]] | None = None,
    grade_strength: float | None = None,
    water_level: float | None = None,
    # export_heightmap params
    filepath: str | None = None,
    # scatter_vegetation params
    rules: list[dict] | None = None,
    min_distance: float | None = None,
    max_instances: int | None = None,
    # scatter_props params
    area_name: str | None = None,
    buildings: list[dict] | None = None,
    prop_density: float | None = None,
    # create_breakable params
    prop_type: str | None = None,
    position: list[float] | None = None,
    # Visual feedback
    capture_viewport: bool = True,
):
    """Environment generation -- terrain, biomes, rivers, roads, water, vegetation scatter, prop scatter, breakable props.

    Actions:
    - generate_terrain: Create heightmap terrain mesh with optional erosion
    - paint_terrain: Auto-paint biome materials based on slope/altitude
    - carve_river: Carve river channel along A* path
    - generate_road: Generate road between waypoints with grading
    - create_water: Create water plane at specified level
    - export_heightmap: Export terrain as 16-bit RAW for Unity
    - scatter_vegetation: Biome-aware vegetation scatter using Poisson disk
    - scatter_props: Context-aware prop placement near buildings
    - create_breakable: Generate intact + damaged prop variants
    """
    blender = get_blender_connection()

    if action == "generate_terrain":
        params: dict = {}
        if name is not None:
            params["name"] = name
        if terrain_type is not None:
            params["terrain_type"] = terrain_type
        if resolution is not None:
            params["resolution"] = resolution
        if height_scale is not None:
            params["height_scale"] = height_scale
        if scale is not None:
            params["scale"] = scale
        if seed is not None:
            params["seed"] = seed
        if erosion is not None:
            params["erosion"] = erosion
        if erosion_iterations is not None:
            params["erosion_iterations"] = erosion_iterations
        if octaves is not None:
            params["octaves"] = octaves
        if persistence is not None:
            params["persistence"] = persistence
        if lacunarity is not None:
            params["lacunarity"] = lacunarity
        result = await blender.send_command("env_generate_terrain", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "paint_terrain":
        params = {}
        if name is not None:
            params["name"] = name
        if biome_rules is not None:
            params["biome_rules"] = biome_rules
        if height_scale is not None:
            params["height_scale"] = height_scale
        result = await blender.send_command("env_paint_terrain", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "carve_river":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if source is not None:
            params["source"] = source
        if destination is not None:
            params["destination"] = destination
        if width is not None:
            params["width"] = int(width)
        if depth is not None:
            params["depth"] = depth
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_carve_river", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_road":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if waypoints is not None:
            params["waypoints"] = waypoints
        if width is not None:
            params["width"] = int(width)
        if grade_strength is not None:
            params["grade_strength"] = grade_strength
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_generate_road", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "create_water":
        params = {}
        if name is not None:
            params["name"] = name
        if water_level is not None:
            params["water_level"] = water_level
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        result = await blender.send_command("env_create_water", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "export_heightmap":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if filepath is not None:
            params["filepath"] = filepath
        result = await blender.send_command("env_export_heightmap", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "scatter_vegetation":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if rules is not None:
            params["rules"] = rules
        if min_distance is not None:
            params["min_distance"] = min_distance
        if seed is not None:
            params["seed"] = seed
        if max_instances is not None:
            params["max_instances"] = max_instances
        result = await blender.send_command("env_scatter_vegetation", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "scatter_props":
        params = {}
        if area_name is not None:
            params["area_name"] = area_name
        if buildings is not None:
            params["buildings"] = buildings
        if prop_density is not None:
            params["prop_density"] = prop_density
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_scatter_props", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "create_breakable":
        params = {}
        if prop_type is not None:
            params["prop_type"] = prop_type
        if position is not None:
            params["position"] = position
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_create_breakable", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_worldbuilding
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_worldbuilding(
    action: Literal[
        "generate_dungeon",
        "generate_cave",
        "generate_town",
        "generate_building",
        "generate_castle",
        "generate_ruins",
        "generate_interior",
        "generate_modular_kit",
    ],
    # Common params (float to accommodate both grid dimensions and building dimensions)
    name: str | None = None,
    width: float | None = None,
    height: float | None = None,
    depth: float | None = None,
    seed: int | None = None,
    # Dungeon params
    min_room_size: int | None = None,
    max_depth: int | None = None,
    cell_size: float | None = None,
    wall_height: float | None = None,
    # Cave params
    fill_probability: float | None = None,
    iterations: int | None = None,
    # Town params
    num_districts: int | None = None,
    # Building params
    floors: int | None = None,
    style: str | None = None,
    # Castle params
    outer_size: float | None = None,
    keep_size: float | None = None,
    tower_count: int | None = None,
    # Ruins params
    damage_level: float | None = None,
    # Interior params
    room_type: str | None = None,
    # Modular kit params
    name_prefix: str | None = None,
    pieces: list[str] | None = None,
    # Visual feedback
    capture_viewport: bool = True,
):
    """Worldbuilding generation -- dungeons, caves, towns, buildings, castles, ruins, interiors, modular kits.

    Actions:
    - generate_dungeon: BSP dungeon with rooms, corridors, doors
    - generate_cave: Cellular automata cave system
    - generate_town: Voronoi district town layout
    - generate_building: Grammar-based building from style presets
    - generate_castle: Castle with walls, towers, keep, gatehouse
    - generate_ruins: Damaged building with debris
    - generate_interior: Furnished room interior
    - generate_modular_kit: Modular architecture kit pieces
    """
    blender = get_blender_connection()

    if action == "generate_dungeon":
        params: dict = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if min_room_size is not None:
            params["min_room_size"] = min_room_size
        if max_depth is not None:
            params["max_depth"] = max_depth
        if seed is not None:
            params["seed"] = seed
        if cell_size is not None:
            params["cell_size"] = cell_size
        if wall_height is not None:
            params["wall_height"] = wall_height
        result = await blender.send_command("world_generate_dungeon", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_cave":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if fill_probability is not None:
            params["fill_probability"] = fill_probability
        if iterations is not None:
            params["iterations"] = iterations
        if seed is not None:
            params["seed"] = seed
        if cell_size is not None:
            params["cell_size"] = cell_size
        if wall_height is not None:
            params["wall_height"] = wall_height
        result = await blender.send_command("world_generate_cave", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_town":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if num_districts is not None:
            params["num_districts"] = num_districts
        if seed is not None:
            params["seed"] = seed
        if cell_size is not None:
            params["cell_size"] = cell_size
        result = await blender.send_command("world_generate_town", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_building":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        if floors is not None:
            params["floors"] = floors
        if style is not None:
            params["style"] = style
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_building", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_castle":
        params = {}
        if name is not None:
            params["name"] = name
        if outer_size is not None:
            params["outer_size"] = outer_size
        if keep_size is not None:
            params["keep_size"] = keep_size
        if tower_count is not None:
            params["tower_count"] = tower_count
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_castle", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_ruins":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        if floors is not None:
            params["floors"] = floors
        if style is not None:
            params["style"] = style
        if damage_level is not None:
            params["damage_level"] = damage_level
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_ruins", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_interior":
        params = {}
        if name is not None:
            params["name"] = name
        if room_type is not None:
            params["room_type"] = room_type
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        if height is not None:
            params["height"] = height
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_interior", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_modular_kit":
        params = {}
        if name_prefix is not None:
            params["name_prefix"] = name_prefix
        if cell_size is not None:
            params["cell_size"] = cell_size
        if pieces is not None:
            params["pieces"] = pieces
        result = await blender.send_command("world_generate_modular_kit", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
