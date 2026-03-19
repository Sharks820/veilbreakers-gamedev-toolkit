import bpy


def handle_get_scene_info(params: dict) -> dict:
    scene = bpy.context.scene
    objects = []
    for obj in bpy.data.objects:
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "visible": obj.visible_get(),
        })
    return {
        "name": scene.name,
        "objects": objects,
        "object_count": len(objects),
        "render_engine": scene.render.engine,
        "fps": scene.render.fps,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "unit_scale": scene.unit_settings.scale_length,
    }


def handle_clear_scene(params: dict) -> dict:
    # Use bpy.data API directly — avoids operator context issues from timer
    count = len(bpy.data.objects)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"cleared": True, "objects_removed": count}


def handle_configure_scene(params: dict) -> dict:
    scene = bpy.context.scene
    if params.get("render_engine") is not None:
        scene.render.engine = params["render_engine"]
    if params.get("fps") is not None:
        scene.render.fps = params["fps"]
    if params.get("unit_scale") is not None:
        scene.unit_settings.scale_length = params["unit_scale"]
    return {
        "render_engine": scene.render.engine,
        "fps": scene.render.fps,
        "unit_scale": scene.unit_settings.scale_length,
    }


def handle_list_objects(params: dict) -> list:
    return [
        {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "visible": obj.visible_get(),
        }
        for obj in bpy.data.objects
    ]
