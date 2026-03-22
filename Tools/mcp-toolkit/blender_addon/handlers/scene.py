"""Scene management handlers: info, clear, configure, lights, cameras, world, collections.

Provides:
- handle_get_scene_info: Inspect current scene state
- handle_clear_scene: Remove all objects from scene
- handle_configure_scene: Set render engine, fps, unit scale
- handle_list_objects: List all scene objects
- handle_setup_world: Configure world environment (HDRI/COLOR/GRADIENT)
- handle_add_light: Add a light to the scene
- handle_add_camera: Add a camera to the scene
- handle_configure_render: Configure render settings
- handle_create_collection: Create a new collection
- handle_move_to_collection: Move an object to a collection
- handle_set_visibility: Set object or collection visibility
"""

from __future__ import annotations

import math

import bpy


# ---------------------------------------------------------------------------
# Valid enums for validation
# ---------------------------------------------------------------------------

_VALID_ENVIRONMENT_TYPES = frozenset({"HDRI", "COLOR", "GRADIENT"})
_VALID_LIGHT_TYPES = frozenset({"POINT", "SUN", "SPOT", "AREA"})
_VALID_RENDER_ENGINES = frozenset({"BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES", "EEVEE"})
_VALID_COLOR_TAGS = frozenset({
    "NONE", "COLOR_01", "COLOR_02", "COLOR_03", "COLOR_04",
    "COLOR_05", "COLOR_06", "COLOR_07", "COLOR_08",
})


# ---------------------------------------------------------------------------
# Pure-logic validation functions (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_setup_world_params(params: dict) -> dict:
    """Validate and normalise world setup parameters.

    Returns dict with validated ``environment_type``, ``color``, ``strength``,
    ``use_nodes``.
    Raises ``ValueError`` for invalid values.
    """
    environment_type = params.get("environment_type", "COLOR")
    if environment_type not in _VALID_ENVIRONMENT_TYPES:
        raise ValueError(
            f"Invalid environment_type: {environment_type!r}. "
            f"Valid: {sorted(_VALID_ENVIRONMENT_TYPES)}"
        )

    color = params.get("color", [0.05, 0.05, 0.05])
    if not isinstance(color, (list, tuple)) or len(color) != 3:
        raise ValueError(f"color must be a 3-element [r,g,b] list, got {color!r}")
    for i, c in enumerate(color):
        if not isinstance(c, (int, float)):
            raise ValueError(f"color[{i}] must be numeric, got {type(c).__name__}")
        if c < 0.0 or c > 1.0:
            raise ValueError(f"color[{i}] must be between 0 and 1, got {c}")

    strength = params.get("strength", 1.0)
    if not isinstance(strength, (int, float)):
        raise ValueError(f"strength must be a number, got {type(strength).__name__}")
    if strength < 0.0:
        raise ValueError(f"strength must be non-negative, got {strength}")

    use_nodes = params.get("use_nodes", True)
    if not isinstance(use_nodes, bool):
        raise ValueError(f"use_nodes must be a boolean, got {type(use_nodes).__name__}")

    return {
        "environment_type": environment_type,
        "color": [float(c) for c in color],
        "strength": float(strength),
        "use_nodes": use_nodes,
    }


def _validate_add_light_params(params: dict) -> dict:
    """Validate and normalise add_light parameters.

    Returns dict with validated ``light_type``, ``position``, ``rotation``,
    ``color``, ``energy``, ``radius``, ``shadow_soft_size``.
    Raises ``ValueError`` for invalid values.
    """
    light_type = params.get("light_type", "POINT")
    if light_type not in _VALID_LIGHT_TYPES:
        raise ValueError(
            f"Invalid light_type: {light_type!r}. "
            f"Valid: {sorted(_VALID_LIGHT_TYPES)}"
        )

    position = params.get("position", [0.0, 0.0, 3.0])
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise ValueError(f"position must be a 3-element list, got {position!r}")

    rotation = params.get("rotation", [0.0, 0.0, 0.0])
    if not isinstance(rotation, (list, tuple)) or len(rotation) != 3:
        raise ValueError(f"rotation must be a 3-element list, got {rotation!r}")

    color = params.get("color", [1.0, 1.0, 1.0])
    if not isinstance(color, (list, tuple)) or len(color) != 3:
        raise ValueError(f"color must be a 3-element [r,g,b] list, got {color!r}")
    for i, c in enumerate(color):
        if not isinstance(c, (int, float)):
            raise ValueError(f"color[{i}] must be numeric, got {type(c).__name__}")
        if c < 0.0 or c > 1.0:
            raise ValueError(f"color[{i}] must be between 0 and 1, got {c}")

    energy = params.get("energy", 1000.0)
    if not isinstance(energy, (int, float)):
        raise ValueError(f"energy must be a number, got {type(energy).__name__}")
    if energy < 0.0:
        raise ValueError(f"energy must be non-negative, got {energy}")

    radius = params.get("radius", 0.25)
    if not isinstance(radius, (int, float)):
        raise ValueError(f"radius must be a number, got {type(radius).__name__}")
    if radius < 0.0:
        raise ValueError(f"radius must be non-negative, got {radius}")

    shadow_soft_size = params.get("shadow_soft_size", 0.25)
    if not isinstance(shadow_soft_size, (int, float)):
        raise ValueError(f"shadow_soft_size must be a number, got {type(shadow_soft_size).__name__}")
    if shadow_soft_size < 0.0:
        raise ValueError(f"shadow_soft_size must be non-negative, got {shadow_soft_size}")

    return {
        "light_type": light_type,
        "position": [float(v) for v in position],
        "rotation": [float(v) for v in rotation],
        "color": [float(c) for c in color],
        "energy": float(energy),
        "radius": float(radius),
        "shadow_soft_size": float(shadow_soft_size),
    }


def _validate_add_camera_params(params: dict) -> dict:
    """Validate and normalise add_camera parameters.

    Returns dict with validated ``position``, ``rotation``, ``focal_length``,
    ``sensor_size``, ``near_clip``, ``far_clip``, ``dof_focus_distance``.
    Raises ``ValueError`` for invalid values.
    """
    position = params.get("position", [0.0, -5.0, 2.0])
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise ValueError(f"position must be a 3-element list, got {position!r}")

    rotation = params.get("rotation", [1.1, 0.0, 0.0])
    if not isinstance(rotation, (list, tuple)) or len(rotation) != 3:
        raise ValueError(f"rotation must be a 3-element list, got {rotation!r}")

    focal_length = params.get("focal_length", 50.0)
    if not isinstance(focal_length, (int, float)):
        raise ValueError(f"focal_length must be a number, got {type(focal_length).__name__}")
    if focal_length <= 0.0:
        raise ValueError(f"focal_length must be positive, got {focal_length}")

    sensor_size = params.get("sensor_size", 36.0)
    if not isinstance(sensor_size, (int, float)):
        raise ValueError(f"sensor_size must be a number, got {type(sensor_size).__name__}")
    if sensor_size <= 0.0:
        raise ValueError(f"sensor_size must be positive, got {sensor_size}")

    near_clip = params.get("near_clip", 0.1)
    if not isinstance(near_clip, (int, float)):
        raise ValueError(f"near_clip must be a number, got {type(near_clip).__name__}")
    if near_clip <= 0.0:
        raise ValueError(f"near_clip must be positive, got {near_clip}")

    far_clip = params.get("far_clip", 1000.0)
    if not isinstance(far_clip, (int, float)):
        raise ValueError(f"far_clip must be a number, got {type(far_clip).__name__}")
    if far_clip <= near_clip:
        raise ValueError(f"far_clip ({far_clip}) must be greater than near_clip ({near_clip})")

    dof_focus_distance = params.get("dof_focus_distance")
    if dof_focus_distance is not None:
        if not isinstance(dof_focus_distance, (int, float)):
            raise ValueError(f"dof_focus_distance must be a number, got {type(dof_focus_distance).__name__}")
        if dof_focus_distance <= 0.0:
            raise ValueError(f"dof_focus_distance must be positive, got {dof_focus_distance}")
        dof_focus_distance = float(dof_focus_distance)

    return {
        "position": [float(v) for v in position],
        "rotation": [float(v) for v in rotation],
        "focal_length": float(focal_length),
        "sensor_size": float(sensor_size),
        "near_clip": float(near_clip),
        "far_clip": float(far_clip),
        "dof_focus_distance": dof_focus_distance,
    }


def _validate_configure_render_params(params: dict) -> dict:
    """Validate and normalise configure_render parameters.

    Returns dict with validated ``engine``, ``samples``, ``resolution_x``,
    ``resolution_y``, ``use_denoising``, ``film_transparent``.
    Raises ``ValueError`` for invalid values.
    """
    engine = params.get("engine", "EEVEE")
    # Normalise EEVEE -> BLENDER_EEVEE_NEXT for Blender 4.x
    if engine not in _VALID_RENDER_ENGINES:
        raise ValueError(
            f"Invalid engine: {engine!r}. "
            f"Valid: {sorted(_VALID_RENDER_ENGINES)}"
        )

    samples = params.get("samples", 128)
    if not isinstance(samples, int):
        raise ValueError(f"samples must be an integer, got {type(samples).__name__}")
    if samples < 1:
        raise ValueError(f"samples must be >= 1, got {samples}")

    resolution_x = params.get("resolution_x", 1920)
    if not isinstance(resolution_x, int):
        raise ValueError(f"resolution_x must be an integer, got {type(resolution_x).__name__}")
    if resolution_x < 1:
        raise ValueError(f"resolution_x must be >= 1, got {resolution_x}")

    resolution_y = params.get("resolution_y", 1080)
    if not isinstance(resolution_y, int):
        raise ValueError(f"resolution_y must be an integer, got {type(resolution_y).__name__}")
    if resolution_y < 1:
        raise ValueError(f"resolution_y must be >= 1, got {resolution_y}")

    use_denoising = params.get("use_denoising", True)
    if not isinstance(use_denoising, bool):
        raise ValueError(f"use_denoising must be a boolean, got {type(use_denoising).__name__}")

    film_transparent = params.get("film_transparent", False)
    if not isinstance(film_transparent, bool):
        raise ValueError(f"film_transparent must be a boolean, got {type(film_transparent).__name__}")

    return {
        "engine": engine,
        "samples": samples,
        "resolution_x": resolution_x,
        "resolution_y": resolution_y,
        "use_denoising": use_denoising,
        "film_transparent": film_transparent,
    }


def _validate_create_collection_params(params: dict) -> dict:
    """Validate and normalise create_collection parameters.

    Returns dict with validated ``name``, ``parent_collection``, ``color_tag``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    parent_collection = params.get("parent_collection")
    if parent_collection is not None and not isinstance(parent_collection, str):
        raise ValueError(f"parent_collection must be a string, got {type(parent_collection).__name__}")

    color_tag = params.get("color_tag", "NONE")
    if color_tag not in _VALID_COLOR_TAGS:
        raise ValueError(
            f"Invalid color_tag: {color_tag!r}. "
            f"Valid: {sorted(_VALID_COLOR_TAGS)}"
        )

    return {
        "name": name,
        "parent_collection": parent_collection,
        "color_tag": color_tag,
    }


def _validate_move_to_collection_params(params: dict) -> dict:
    """Validate and normalise move_to_collection parameters.

    Returns dict with validated ``object_name``, ``collection_name``.
    Raises ``ValueError`` for invalid values.
    """
    object_name = params.get("object_name")
    if not object_name or not isinstance(object_name, str):
        raise ValueError("object_name is required and must be a non-empty string")

    collection_name = params.get("collection_name")
    if not collection_name or not isinstance(collection_name, str):
        raise ValueError("collection_name is required and must be a non-empty string")

    return {
        "object_name": object_name,
        "collection_name": collection_name,
    }


def _validate_set_visibility_params(params: dict) -> dict:
    """Validate and normalise set_visibility parameters.

    Returns dict with validated ``name``, ``visible``, ``render_visible``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    visible = params.get("visible")
    if visible is not None and not isinstance(visible, bool):
        raise ValueError(f"visible must be a boolean, got {type(visible).__name__}")

    render_visible = params.get("render_visible")
    if render_visible is not None and not isinstance(render_visible, bool):
        raise ValueError(f"render_visible must be a boolean, got {type(render_visible).__name__}")

    if visible is None and render_visible is None:
        raise ValueError("At least one of 'visible' or 'render_visible' must be provided")

    return {
        "name": name,
        "visible": visible,
        "render_visible": render_visible,
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy at runtime)
# ---------------------------------------------------------------------------


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


def handle_setup_world(params: dict) -> dict:
    """Configure world environment (HDRI/COLOR/GRADIENT).

    Params:
        environment_type: "HDRI", "COLOR", or "GRADIENT" (default "COLOR").
        color: [r, g, b] base color (default [0.05, 0.05, 0.05]).
        strength: Environment strength multiplier (default 1.0).
        use_nodes: Enable shader nodes on world (default True).

    Returns dict with applied world settings.
    """
    validated = _validate_setup_world_params(params)
    env_type = validated["environment_type"]
    color = validated["color"]
    strength = validated["strength"]
    use_nodes = validated["use_nodes"]

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = use_nodes

    if use_nodes and world.node_tree is not None:
        nodes = world.node_tree.nodes
        links = world.node_tree.links

        # Clear existing nodes
        nodes.clear()

        # Create output node
        output = nodes.new("ShaderNodeOutputWorld")
        output.location = (300, 0)

        if env_type == "COLOR":
            bg = nodes.new("ShaderNodeBackground")
            bg.location = (0, 0)
            bg.inputs["Color"].default_value = (*color, 1.0)
            bg.inputs["Strength"].default_value = strength
            links.new(bg.outputs["Background"], output.inputs["Surface"])

        elif env_type == "GRADIENT":
            bg = nodes.new("ShaderNodeBackground")
            bg.location = (0, 0)
            bg.inputs["Strength"].default_value = strength

            gradient = nodes.new("ShaderNodeTexGradient")
            gradient.location = (-400, 0)

            mapping = nodes.new("ShaderNodeMapping")
            mapping.location = (-600, 0)

            tex_coord = nodes.new("ShaderNodeTexCoord")
            tex_coord.location = (-800, 0)

            color_ramp = nodes.new("ShaderNodeValToRGB")
            color_ramp.location = (-200, 0)
            # Set gradient colors
            color_ramp.color_ramp.elements[0].color = (*color, 1.0)
            color_ramp.color_ramp.elements[1].color = (
                min(color[0] + 0.1, 1.0),
                min(color[1] + 0.1, 1.0),
                min(color[2] + 0.1, 1.0),
                1.0,
            )

            links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
            links.new(mapping.outputs["Vector"], gradient.inputs["Vector"])
            links.new(gradient.outputs["Color"], color_ramp.inputs["Fac"])
            links.new(color_ramp.outputs["Color"], bg.inputs["Color"])
            links.new(bg.outputs["Background"], output.inputs["Surface"])

        elif env_type == "HDRI":
            bg = nodes.new("ShaderNodeBackground")
            bg.location = (0, 0)
            bg.inputs["Strength"].default_value = strength

            env_tex = nodes.new("ShaderNodeTexEnvironment")
            env_tex.location = (-300, 0)

            tex_coord = nodes.new("ShaderNodeTexCoord")
            tex_coord.location = (-500, 0)

            links.new(tex_coord.outputs["Generated"], env_tex.inputs["Vector"])
            links.new(env_tex.outputs["Color"], bg.inputs["Color"])
            links.new(bg.outputs["Background"], output.inputs["Surface"])

    return {
        "world_name": world.name,
        "environment_type": env_type,
        "color": color,
        "strength": strength,
        "use_nodes": use_nodes,
    }


def handle_add_light(params: dict) -> dict:
    """Add a light to the scene.

    Params:
        light_type: "POINT", "SUN", "SPOT", or "AREA" (default "POINT").
        position: [x, y, z] world position (default [0, 0, 3]).
        rotation: [x, y, z] Euler rotation in radians (default [0, 0, 0]).
        color: [r, g, b] light color (default [1, 1, 1]).
        energy: Light energy/power in watts (default 1000).
        radius: Light radius (default 0.25).
        shadow_soft_size: Shadow softness (default 0.25).

    Returns dict with light name, type, position, and settings.
    """
    validated = _validate_add_light_params(params)
    light_type = validated["light_type"]
    position = validated["position"]
    rotation = validated["rotation"]
    color = validated["color"]
    energy = validated["energy"]
    radius = validated["radius"]
    shadow_soft_size = validated["shadow_soft_size"]

    name = params.get("name", f"{light_type.title()}_Light")

    light_data = bpy.data.lights.new(name=name, type=light_type)
    light_data.color = tuple(color)
    light_data.energy = energy
    light_data.shadow_soft_size = shadow_soft_size

    if hasattr(light_data, "shadow_buffer_clip_start"):
        light_data.shadow_buffer_clip_start = 0.1

    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    light_obj.location = tuple(position)
    light_obj.rotation_euler = tuple(rotation)

    bpy.context.collection.objects.link(light_obj)

    return {
        "name": light_obj.name,
        "light_type": light_type,
        "position": list(light_obj.location),
        "rotation": list(light_obj.rotation_euler),
        "color": color,
        "energy": energy,
        "radius": radius,
        "shadow_soft_size": shadow_soft_size,
    }


def handle_add_camera(params: dict) -> dict:
    """Add a camera to the scene.

    Params:
        position: [x, y, z] world position (default [0, -5, 2]).
        rotation: [x, y, z] Euler rotation in radians (default [1.1, 0, 0]).
        focal_length: Lens focal length in mm (default 50).
        sensor_size: Sensor width in mm (default 36).
        near_clip: Near clipping distance (default 0.1).
        far_clip: Far clipping distance (default 1000).
        dof_focus_distance: Depth-of-field focus distance (optional, None disables DOF).

    Returns dict with camera name, position, and lens settings.
    """
    validated = _validate_add_camera_params(params)
    position = validated["position"]
    rotation = validated["rotation"]
    focal_length = validated["focal_length"]
    sensor_size = validated["sensor_size"]
    near_clip = validated["near_clip"]
    far_clip = validated["far_clip"]
    dof_focus_distance = validated["dof_focus_distance"]

    name = params.get("name", "Camera")

    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = focal_length
    cam_data.sensor_width = sensor_size
    cam_data.clip_start = near_clip
    cam_data.clip_end = far_clip

    if dof_focus_distance is not None:
        cam_data.dof.use_dof = True
        cam_data.dof.focus_distance = dof_focus_distance
    else:
        cam_data.dof.use_dof = False

    cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
    cam_obj.location = tuple(position)
    cam_obj.rotation_euler = tuple(rotation)

    bpy.context.collection.objects.link(cam_obj)

    return {
        "name": cam_obj.name,
        "position": list(cam_obj.location),
        "rotation": list(cam_obj.rotation_euler),
        "focal_length": focal_length,
        "sensor_size": sensor_size,
        "near_clip": near_clip,
        "far_clip": far_clip,
        "dof_enabled": dof_focus_distance is not None,
        "dof_focus_distance": dof_focus_distance,
    }


def handle_configure_render(params: dict) -> dict:
    """Configure render settings.

    Params:
        engine: Render engine -- "EEVEE", "CYCLES" (default "EEVEE").
        samples: Render samples (default 128).
        resolution_x: Horizontal resolution in pixels (default 1920).
        resolution_y: Vertical resolution in pixels (default 1080).
        use_denoising: Enable denoising (default True).
        film_transparent: Transparent background (default False).

    Returns dict with applied render settings.
    """
    validated = _validate_configure_render_params(params)
    engine = validated["engine"]
    samples = validated["samples"]
    resolution_x = validated["resolution_x"]
    resolution_y = validated["resolution_y"]
    use_denoising = validated["use_denoising"]
    film_transparent = validated["film_transparent"]

    scene = bpy.context.scene

    # Normalise engine name for Blender 4.x
    if engine in ("EEVEE", "BLENDER_EEVEE"):
        # Try BLENDER_EEVEE_NEXT first (Blender 4.2+), fall back
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except TypeError:
            scene.render.engine = "BLENDER_EEVEE"
    elif engine == "BLENDER_EEVEE_NEXT":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    else:
        scene.render.engine = engine

    # Set samples based on engine
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = use_denoising
    else:
        # EEVEE
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = samples

    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.film_transparent = film_transparent

    return {
        "engine": scene.render.engine,
        "samples": samples,
        "resolution_x": resolution_x,
        "resolution_y": resolution_y,
        "use_denoising": use_denoising,
        "film_transparent": film_transparent,
    }


def handle_create_collection(params: dict) -> dict:
    """Create a new collection in the scene.

    Params:
        name: Collection name (required).
        parent_collection: Parent collection name (optional, defaults to scene collection).
        color_tag: Collection color tag (default "NONE").

    Returns dict with collection name, parent, and color tag.
    """
    validated = _validate_create_collection_params(params)
    name = validated["name"]
    parent_name = validated["parent_collection"]
    color_tag = validated["color_tag"]

    # Find parent collection
    if parent_name:
        parent = bpy.data.collections.get(parent_name)
        if parent is None:
            raise ValueError(f"Parent collection not found: {parent_name!r}")
    else:
        parent = bpy.context.scene.collection

    # Check if collection already exists
    existing = bpy.data.collections.get(name)
    if existing is not None:
        raise ValueError(f"Collection already exists: {name!r}")

    coll = bpy.data.collections.new(name=name)
    coll.color_tag = color_tag
    parent.children.link(coll)

    return {
        "name": coll.name,
        "parent": parent.name,
        "color_tag": color_tag,
    }


def handle_move_to_collection(params: dict) -> dict:
    """Move an object to a collection.

    Params:
        object_name: Name of the object to move (required).
        collection_name: Name of the target collection (required).

    Returns dict with object name, target collection, and source collections.
    """
    validated = _validate_move_to_collection_params(params)
    object_name = validated["object_name"]
    collection_name = validated["collection_name"]

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name!r}")

    target_coll = bpy.data.collections.get(collection_name)
    if target_coll is None:
        raise ValueError(f"Collection not found: {collection_name!r}")

    # Record source collections
    source_collections = [c.name for c in obj.users_collection]

    # Unlink from all current collections
    for coll in obj.users_collection:
        coll.objects.unlink(obj)

    # Link to target collection
    target_coll.objects.link(obj)

    return {
        "object_name": obj.name,
        "collection": target_coll.name,
        "previous_collections": source_collections,
    }


def handle_set_visibility(params: dict) -> dict:
    """Set object or collection visibility.

    Params:
        name: Name of the object or collection (required).
        visible: Viewport visibility (optional).
        render_visible: Render visibility (optional).

    At least one of ``visible`` or ``render_visible`` must be provided.
    Looks up objects first, then collections.

    Returns dict with name, type (object/collection), and visibility state.
    """
    validated = _validate_set_visibility_params(params)
    name = validated["name"]
    visible = validated["visible"]
    render_visible = validated["render_visible"]

    # Try object first
    obj = bpy.data.objects.get(name)
    if obj is not None:
        if visible is not None:
            obj.hide_viewport = not visible
        if render_visible is not None:
            obj.hide_render = not render_visible
        return {
            "name": obj.name,
            "target_type": "object",
            "visible": not obj.hide_viewport,
            "render_visible": not obj.hide_render,
        }

    # Try collection
    coll = bpy.data.collections.get(name)
    if coll is not None:
        if visible is not None:
            coll.hide_viewport = not visible
        if render_visible is not None:
            coll.hide_render = not render_visible
        return {
            "name": coll.name,
            "target_type": "collection",
            "visible": not coll.hide_viewport,
            "render_visible": not coll.hide_render,
        }

    raise ValueError(f"No object or collection found with name: {name!r}")
