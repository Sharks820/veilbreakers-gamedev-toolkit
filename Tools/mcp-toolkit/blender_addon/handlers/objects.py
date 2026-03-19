import bpy

MESH_OPS = {
    "cube": bpy.ops.mesh.primitive_cube_add,
    "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
    "cylinder": bpy.ops.mesh.primitive_cylinder_add,
    "plane": bpy.ops.mesh.primitive_plane_add,
    "cone": bpy.ops.mesh.primitive_cone_add,
    "torus": bpy.ops.mesh.primitive_torus_add,
    "monkey": bpy.ops.mesh.primitive_monkey_add,
}


def handle_create_object(params: dict) -> dict:
    mesh_type = params.get("mesh_type", "cube")
    position = params.get("position", [0, 0, 0])
    name = params.get("name")

    op = MESH_OPS.get(mesh_type)
    if op is None:
        raise ValueError(f"Unknown mesh type: {mesh_type}. Valid: {list(MESH_OPS.keys())}")

    op(location=tuple(position))
    obj = bpy.context.active_object
    if name:
        obj.name = name

    if "rotation" in params and params["rotation"]:
        obj.rotation_euler = tuple(params["rotation"])
    if "scale" in params and params["scale"]:
        obj.scale = tuple(params["scale"])

    return {
        "name": obj.name,
        "type": obj.type,
        "vertex_count": len(obj.data.vertices),
        "location": list(obj.location),
    }


def handle_modify_object(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise ValueError("Object name is required")

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    if "position" in params and params["position"]:
        obj.location = tuple(params["position"])
    if "rotation" in params and params["rotation"]:
        obj.rotation_euler = tuple(params["rotation"])
    if "scale" in params and params["scale"]:
        obj.scale = tuple(params["scale"])

    return {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation": list(obj.rotation_euler),
        "scale": list(obj.scale),
    }


def handle_delete_object(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise ValueError("Object name is required")

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": name}


def handle_duplicate_object(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise ValueError("Object name is required")

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(new_obj)

    new_name = params.get("new_name")
    if new_name:
        new_obj.name = new_name

    offset = params.get("offset", [2, 0, 0])
    new_obj.location.x += offset[0]
    new_obj.location.y += offset[1]
    new_obj.location.z += offset[2]

    return {
        "name": new_obj.name,
        "type": new_obj.type,
        "location": list(new_obj.location),
        "source": name,
    }
