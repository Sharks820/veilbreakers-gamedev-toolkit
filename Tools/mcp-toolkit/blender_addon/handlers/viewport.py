import math
import os
import tempfile

import bpy


def handle_get_viewport_screenshot(params: dict) -> dict:
    max_size = params.get("max_size", 1024)
    filepath = params.get("filepath") or os.path.join(
        tempfile.gettempdir(), "vb_screenshot.png"
    )
    fmt = params.get("format", "PNG").upper()

    scene = bpy.context.scene
    old_filepath = scene.render.filepath
    old_format = scene.render.image_settings.file_format
    old_x = scene.render.resolution_x
    old_y = scene.render.resolution_y

    scene.render.filepath = filepath
    scene.render.image_settings.file_format = fmt
    scene.render.resolution_x = max_size
    scene.render.resolution_y = max_size

    bpy.ops.render.opengl(write_still=True)

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
    scene.camera = cam

    old_x = scene.render.resolution_x
    old_y = scene.render.resolution_y
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]

    paths = []
    for i, (azimuth, elevation) in enumerate(angles):
        az_rad = math.radians(azimuth)
        el_rad = math.radians(elevation)
        x = center.x + distance * math.cos(el_rad) * math.cos(az_rad)
        y = center.y + distance * math.cos(el_rad) * math.sin(az_rad)
        z = center.z + distance * math.sin(el_rad)
        cam.location = (x, y, z)

        from mathutils import Vector
        direction = Vector(center) - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        path = os.path.join(tempfile.gettempdir(), f"vb_contact_{i}.png")
        scene.render.filepath = path
        scene.render.image_settings.file_format = "PNG"
        cam.hide_render = False
        bpy.ops.render.render(write_still=True)
        cam.hide_render = True
        paths.append(path)

    scene.camera = old_cam
    scene.render.resolution_x = old_x
    scene.render.resolution_y = old_y

    return {
        "paths": paths,
        "count": len(paths),
        "angles": angles,
        "object_name": object_name,
    }
