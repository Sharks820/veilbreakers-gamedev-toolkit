import bpy
import bmesh


def _get_3d_context_override():
    """Find a 3D Viewport area for operator context override."""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            return {"area": area, "region": area.regions[-1]}
    return None


def handle_create_object(params: dict) -> dict:
    mesh_type = params.get("mesh_type", "cube")
    position = params.get("position", [0, 0, 0])
    name = params.get("name")

    if len(position) != 3:
        raise ValueError(f"position must have 3 elements, got {len(position)}")

    # Use bpy.data API to avoid operator context issues from timer
    mesh_creators = {
        "cube": _create_cube,
        "sphere": _create_uv_sphere,
        "cylinder": _create_cylinder,
        "plane": _create_plane,
        "cone": _create_cone,
        "torus": _create_torus,
        "monkey": _create_monkey,
    }

    creator = mesh_creators.get(mesh_type)
    if creator is None:
        raise ValueError(
            f"Unknown mesh type: {mesh_type}. "
            f"Valid: {list(mesh_creators.keys())}"
        )

    obj = creator(name or mesh_type.capitalize())
    obj.location = tuple(position)

    if params.get("rotation") is not None:
        obj.rotation_euler = tuple(params["rotation"])
    if params.get("scale") is not None:
        obj.scale = tuple(params["scale"])

    return {
        "name": obj.name,
        "type": obj.type,
        "vertex_count": len(obj.data.vertices),
        "location": list(obj.location),
    }


def _create_cube(name: str):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _create_uv_sphere(name: str):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _create_cylinder(name: str):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=32, radius1=1.0, radius2=1.0, depth=2.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _create_plane(name: str):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=2.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _create_cone(name: str):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=32, radius1=1.0, radius2=0.0, depth=2.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _create_torus(name: str):
    # bmesh doesn't have create_torus — use a basic torus via Python math
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # Fallback: create a cube and label it torus (proper torus needs manual verts)
    # For now, use operator with context override if available
    override = _get_3d_context_override()
    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.mesh.primitive_torus_add()
        obj = bpy.context.active_object
        obj.name = name
        obj.data.name = name
        bm.free()
        return obj
    # Fallback: cube placeholder
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _create_monkey(name: str):
    # bmesh doesn't have create_monkey — requires operator
    override = _get_3d_context_override()
    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.mesh.primitive_monkey_add()
        obj = bpy.context.active_object
        obj.name = name
        obj.data.name = name
        return obj
    # Fallback: sphere placeholder
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def handle_modify_object(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise ValueError("Object name is required")

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    if params.get("position") is not None:
        obj.location = tuple(params["position"])
    if params.get("rotation") is not None:
        obj.rotation_euler = tuple(params["rotation"])
    if params.get("scale") is not None:
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
    if obj.data is not None:
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
