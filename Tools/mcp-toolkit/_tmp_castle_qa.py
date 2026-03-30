from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(os.getcwd())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender_addon.handlers.worldbuilding import handle_generate_castle, handle_generate_location  # noqa: E402


OUT_DIR = Path(os.environ.get("VEILBREAKERS_QA_DIR", str(Path.home() / "AppData" / "Local" / "Temp" / "veilbreakers_qa")))
OUT_DIR.mkdir(parents=True, exist_ok=True)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"


def add_sun(name: str, rotation=(0.9, 0.0, 0.8), strength: float = 4.0) -> None:
    light_data = bpy.data.lights.new(name, type="SUN")
    light_data.energy = strength
    light = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(light)
    light.rotation_euler = rotation


def add_camera(location, target, lens: float = 35.0) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new("QA_Camera")
    cam_data.lens = lens
    cam = bpy.data.objects.new("QA_Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = location
    direction = (
        target[0] - location[0],
        target[1] - location[1],
        target[2] - location[2],
    )
    cam.rotation_euler = Vector(direction).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def add_framed_camera(target, span: float, *, side: float = 1.0, height: float = 0.7, lens: float = 35.0) -> bpy.types.Object:
    distance = max(6.0, span * 0.45)
    location = (
        target[0] + distance * 1.0 * side,
        target[1] - distance * 1.1,
        target[2] + distance * height,
    )
    return add_camera(location, target, lens=lens)


def direction_to_euler(direction):
    dx, dy, dz = direction
    yaw = math.atan2(dx, dy)
    dist = math.sqrt(dx * dx + dy * dy)
    pitch = math.atan2(dz, dist)
    return (math.pi / 2 - pitch, 0.0, yaw)


def render(filepath: Path) -> None:
    bpy.context.scene.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True)


def setup_world_background():
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    bg = nodes.get("Background")
    if bg is not None:
        bg.inputs[1].default_value = 0.75
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)


def frame_selected_objects(buffer: float = 1.2):
    deps = bpy.context.evaluated_depsgraph_get()
    objs = [
        o for o in bpy.context.scene.objects
        if o.type == "MESH" and not o.name.startswith("QA_Ground")
    ]
    if not objs:
        return
    xs, ys, zs = [], [], []
    for obj in objs:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            xs.append(world.x)
            ys.append(world.y)
            zs.append(world.z)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    center = ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, (min_z + max_z) * 0.5)
    span = max(max_x - min_x, max_y - min_y, max_z - min_z) * buffer
    return center, span


def create_ground_plane(size: float = 200.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0.0, 0.0, -0.05))
    ground = bpy.context.active_object
    ground.name = "QA_Ground"
    return ground


def main():
    # Render 1: standalone castle
    reset_scene()
    setup_world_background()
    add_sun("QA_Sun_A", rotation=(0.85, 0.0, 0.7), strength=4.5)
    add_sun("QA_Sun_B", rotation=(2.2, 0.0, -1.0), strength=1.2)
    create_ground_plane()
    handle_generate_castle({
        "name": "QA_Castle",
        "outer_size": 48.0,
        "keep_size": 14.0,
        "tower_count": 6,
        "seed": 23,
    })
    center, span = frame_selected_objects()
    if center is None:
        center = (24.0, 24.0, 16.0)
        span = 60.0
    add_framed_camera(center, span, side=1.0, height=0.72, lens=28.0)
    render(OUT_DIR / "qa_castle_stronghold.png")

    # Render 2: cliff keep location
    reset_scene()
    setup_world_background()
    add_sun("QA_Sun_C", rotation=(0.95, 0.0, 0.45), strength=4.0)
    add_sun("QA_Sun_D", rotation=(2.6, 0.0, -0.75), strength=1.0)
    handle_generate_location({
        "name": "QA_CliffKeep",
        "location_type": "cliff_keep",
        "building_count": 4,
        "path_count": 3,
        "poi_count": 3,
        "seed": 23,
    })
    center, span = frame_selected_objects()
    if center is None:
        center = (72.0, 72.0, 24.0)
        span = 80.0
    add_framed_camera(center, span, side=1.1, height=0.82, lens=30.0)
    render(OUT_DIR / "qa_cliff_keep_stronghold.png")


if __name__ == "__main__":
    main()
