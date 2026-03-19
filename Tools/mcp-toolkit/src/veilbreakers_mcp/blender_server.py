import json
from typing import Literal

from mcp.server.fastmcp import FastMCP, Image
from veilbreakers_mcp.shared.blender_client import BlenderConnection, BlenderCommandError
from veilbreakers_mcp.shared.config import Settings
from veilbreakers_mcp.shared.security import validate_code
from veilbreakers_mcp.shared.image_utils import compose_contact_sheet

settings = Settings()
mcp = FastMCP(
    "veilbreakers-blender",
    instructions="VeilBreakers Blender game development tools",
)

_connection: BlenderConnection | None = None


def get_blender_connection() -> BlenderConnection:
    global _connection
    if _connection is None or not _connection.is_alive():
        _connection = BlenderConnection(
            host=settings.blender_host,
            port=settings.blender_port,
            timeout=settings.blender_timeout,
        )
        _connection.connect()
    return _connection


async def _with_screenshot(
    blender: BlenderConnection, result: dict, capture: bool = True
) -> list:
    """Return structured result + viewport screenshot for mutation tools."""
    parts: list = [json.dumps(result, indent=2, default=str)]
    if capture:
        try:
            screenshot_bytes = await blender.capture_viewport_bytes()
            parts.append(Image(data=screenshot_bytes, format="png"))
        except Exception:
            parts.append("[Screenshot capture failed - Blender viewport may not be visible]")
    return parts


@mcp.tool()
async def blender_scene(
    action: Literal["inspect", "clear", "configure", "list_objects"],
    render_engine: str | None = None,
    fps: int | None = None,
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
        if render_engine:
            params["render_engine"] = render_engine
        if fps:
            params["fps"] = fps
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
    params = {}
    if name:
        params["name"] = name
    if mesh_type:
        params["mesh_type"] = mesh_type
    if position:
        params["position"] = position
    if rotation:
        params["rotation"] = rotation
    if scale:
        params["scale"] = scale

    if action == "list":
        result = await blender.send_command("list_objects")
        return json.dumps(result, indent=2, default=str)

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
    params = {}
    if name:
        params["name"] = name
    if object_name:
        params["object_name"] = object_name
    if base_color:
        params["base_color"] = base_color
    if metallic is not None:
        params["metallic"] = metallic
    if roughness is not None:
        params["roughness"] = roughness

    if action == "list":
        result = await blender.send_command("material_list")
        return json.dumps(result, indent=2, default=str)

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
        return Image(data=screenshot_bytes, format="png")

    elif action == "contact_sheet":
        params = {}
        if object_name:
            params["object_name"] = object_name
        if angles:
            params["angles"] = angles
        if resolution:
            params["resolution"] = resolution
        result = await blender.send_command("render_contact_sheet", params)
        paths = result.get("paths", [])
        if paths:
            sheet_bytes = compose_contact_sheet(paths)
            return Image(data=sheet_bytes, format="png")
        return "No images rendered for contact sheet"

    elif action == "set_shading":
        result = await blender.send_command(
            "set_shading", {"shading_type": shading_type}
        )
        return await _with_screenshot(blender, result)

    elif action == "navigate":
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
    Blocked: os, sys, subprocess, socket, exec, eval, getattr.
    """
    is_safe, violations = validate_code(code)
    if not is_safe:
        return f"SECURITY ERROR: Code validation failed:\n" + "\n".join(
            f"  - {v}" for v in violations
        )

    blender = get_blender_connection()
    result = await blender.send_command("execute_code", {"code": code})
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_export(
    format: Literal["fbx", "gltf"],
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
    cmd = f"export_{format}"
    result = await blender.send_command(cmd, {
        "filepath": filepath,
        "selected_only": selected_only,
        "apply_modifiers": apply_modifiers,
    })
    return json.dumps(result, indent=2, default=str)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
