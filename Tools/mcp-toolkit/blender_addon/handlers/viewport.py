import math
import os
import tempfile
import uuid

import bpy

from ._context import get_3d_context_override


def _unique_temp_path(prefix: str, suffix: str = ".png") -> str:
    """Generate a unique temp file path to avoid race conditions."""
    return os.path.join(
        tempfile.gettempdir(), f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"
    )


def handle_get_viewport_screenshot(params: dict) -> dict:
    max_size = params.get("max_size", 1024)
    filepath = params.get("filepath") or _unique_temp_path("vb_screenshot")
    fmt = params.get("format", "PNG").upper()

    scene = bpy.context.scene
    old_filepath = scene.render.filepath
    old_format = scene.render.image_settings.file_format
    old_x = scene.render.resolution_x
    old_y = scene.render.resolution_y

    try:
        scene.render.filepath = filepath
        scene.render.image_settings.file_format = fmt
        scene.render.resolution_x = max_size
        scene.render.resolution_y = max_size

        # Use context override for render.opengl (needs 3D viewport)
        override = get_3d_context_override()
        if override:
            with bpy.context.temp_override(**override):
                bpy.ops.render.opengl(write_still=True)
        else:
            # Fallback: full render if no 3D viewport available
            bpy.ops.render.render(write_still=True)
    finally:
        scene.render.filepath = old_filepath
        scene.render.image_settings.file_format = old_format
        scene.render.resolution_x = old_x
        scene.render.resolution_y = old_y

    return {
        "filepath": filepath,
        "width": max_size,
        "height": max_size,
        "format": fmt.lower(),
    }


def handle_render_contact_sheet(params: dict) -> dict:
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    target = bpy.data.objects.get(object_name)
    if not target:
        raise ValueError(f"Object not found: {object_name}")

    angles = params.get("angles", [
        [0, 0], [90, 0], [180, 0], [270, 0], [0, 90], [45, 30]
    ])
    resolution = params.get("resolution", [512, 512])

    cam = bpy.data.objects.get("ContactSheet_Camera")
    if not cam:
        cam_data = bpy.data.cameras.new("ContactSheet_Camera")
        cam = bpy.data.objects.new("ContactSheet_Camera", cam_data)
        bpy.context.scene.collection.objects.link(cam)
    cam.hide_set(True)
    cam.hide_render = True

    center = target.location.copy()
    distance = max(target.dimensions) * 2.5
    if distance < 1.0:
        distance = 3.0

    scene = bpy.context.scene
    old_cam = scene.camera
    old_x = scene.render.resolution_x
    old_y = scene.render.resolution_y
    old_filepath = scene.render.filepath
    old_format = scene.render.image_settings.file_format

    paths = []
    try:
        scene.camera = cam
        scene.render.resolution_x = resolution[0]
        scene.render.resolution_y = resolution[1]
        scene.render.image_settings.file_format = "PNG"

        from mathutils import Vector

        for i, (azimuth, elevation) in enumerate(angles):
            az_rad = math.radians(azimuth)
            el_rad = math.radians(elevation)
            x = center.x + distance * math.cos(el_rad) * math.cos(az_rad)
            y = center.y + distance * math.cos(el_rad) * math.sin(az_rad)
            z = center.z + distance * math.sin(el_rad)
            cam.location = (x, y, z)

            direction = Vector(center) - cam.location
            cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

            path = _unique_temp_path(f"vb_contact_{i}")
            scene.render.filepath = path
            cam.hide_render = False
            bpy.ops.render.render(write_still=True)
            cam.hide_render = True
            paths.append(path)
    finally:
        scene.camera = old_cam
        scene.render.resolution_x = old_x
        scene.render.resolution_y = old_y
        scene.render.filepath = old_filepath
        scene.render.image_settings.file_format = old_format

    return {
        "paths": paths,
        "count": len(paths),
        "angles": angles,
        "object_name": object_name,
    }


def handle_set_shading(params: dict) -> dict:
    shading_type = params.get("shading_type", "SOLID").upper()
    valid = {"WIREFRAME", "SOLID", "MATERIAL", "RENDERED"}
    if shading_type not in valid:
        raise ValueError(f"Invalid shading type: {shading_type}. Valid: {valid}")

    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = shading_type
                    return {"shading_type": shading_type}
    raise RuntimeError("No 3D Viewport found")


def handle_navigate_camera(params: dict) -> dict:
    position = params.get("position")
    target_pos = params.get("target")

    if not position or not target_pos:
        raise ValueError("Both 'position' and 'target' are required")

    from mathutils import Vector

    cam = bpy.context.scene.camera
    if cam is None:
        raise ValueError("No active camera in scene")

    cam.location = Vector(position)
    direction = Vector(target_pos) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    return {
        "camera": cam.name,
        "position": list(cam.location),
        "target": target_pos,
    }
