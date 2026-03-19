import bpy


def handle_material_create(params: dict) -> dict:
    name = params.get("name", "Material")
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")

    if bsdf:
        if params.get("base_color") is not None:
            color = params["base_color"]
            if len(color) == 3:
                color = [*color, 1.0]
            bsdf.inputs["Base Color"].default_value = color
        if params.get("metallic") is not None:
            bsdf.inputs["Metallic"].default_value = params["metallic"]
        if params.get("roughness") is not None:
            bsdf.inputs["Roughness"].default_value = params["roughness"]

    return {
        "name": mat.name,
        "use_nodes": mat.use_nodes,
    }


def handle_material_assign(params: dict) -> dict:
    mat_name = params.get("name")
    obj_name = params.get("object_name")
    if not mat_name:
        raise ValueError("Material 'name' is required")
    if not obj_name:
        raise ValueError("'object_name' is required")

    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        raise ValueError(f"Material not found: {mat_name}")

    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        raise ValueError(f"Object not found: {obj_name}")

    if obj.data is None or not hasattr(obj.data, "materials"):
        raise ValueError(f"Object '{obj_name}' does not support materials")

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return {
        "material": mat.name,
        "object": obj.name,
        "assigned": True,
    }


def handle_material_modify(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise ValueError("Material 'name' is required")

    mat = bpy.data.materials.get(name)
    if mat is None:
        raise ValueError(f"Material not found: {name}")

    if not mat.use_nodes:
        raise ValueError(f"Material '{name}' does not use nodes")

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf:
        raise ValueError(f"Material '{name}' has no Principled BSDF node")

    if params.get("base_color") is not None:
        color = params["base_color"]
        if len(color) == 3:
            color = [*color, 1.0]
        bsdf.inputs["Base Color"].default_value = color
    if params.get("metallic") is not None:
        bsdf.inputs["Metallic"].default_value = params["metallic"]
    if params.get("roughness") is not None:
        bsdf.inputs["Roughness"].default_value = params["roughness"]

    return {
        "name": mat.name,
        "modified": True,
    }


def handle_material_list(params: dict) -> list:
    return [
        {
            "name": mat.name,
            "use_nodes": mat.use_nodes,
            "users": mat.users,
        }
        for mat in bpy.data.materials
    ]
