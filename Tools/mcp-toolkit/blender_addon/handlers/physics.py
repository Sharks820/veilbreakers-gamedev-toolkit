"""Physics simulation handlers for Blender addon.

Provides:
- handle_add_rigid_body: Add rigid body physics to an object (PHYS-01)
- handle_add_cloth: Add cloth simulation to an object (PHYS-02)
- handle_add_soft_body: Add soft body simulation to an object (PHYS-03)
- handle_bake_physics: Bake physics simulation for a frame range (PHYS-04)

All handlers follow the standard params-dict-in, result-dict-out pattern.
Validation functions are pure-logic and testable without Blender.
"""

from __future__ import annotations

import bpy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RIGID_BODY_TYPES = frozenset({"ACTIVE", "PASSIVE"})

_COLLISION_SHAPES = frozenset({
    "BOX", "SPHERE", "CAPSULE", "MESH", "CONVEX_HULL",
})

# Cloth quality range
_CLOTH_QUALITY_MIN = 1
_CLOTH_QUALITY_MAX = 10


# ---------------------------------------------------------------------------
# Pure-logic validators (testable without Blender)
# ---------------------------------------------------------------------------


def validate_rigid_body_params(params: dict) -> list[str]:
    """Validate add_rigid_body parameters. Returns list of errors."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    body_type = params.get("body_type", "ACTIVE")
    if body_type not in _RIGID_BODY_TYPES:
        errors.append(
            f"Invalid body_type: {body_type!r}. "
            f"Valid: {sorted(_RIGID_BODY_TYPES)}"
        )

    mass = params.get("mass", 1.0)
    if not isinstance(mass, (int, float)) or mass <= 0:
        errors.append(f"mass must be a positive number, got {mass!r}")

    friction = params.get("friction", 0.5)
    if not isinstance(friction, (int, float)) or friction < 0:
        errors.append(f"friction must be a non-negative number, got {friction!r}")

    restitution = params.get("restitution", 0.0)
    if not isinstance(restitution, (int, float)) or restitution < 0 or restitution > 1:
        errors.append(
            f"restitution must be between 0 and 1, got {restitution!r}"
        )

    collision_shape = params.get("collision_shape", "CONVEX_HULL")
    if collision_shape not in _COLLISION_SHAPES:
        errors.append(
            f"Invalid collision_shape: {collision_shape!r}. "
            f"Valid: {sorted(_COLLISION_SHAPES)}"
        )

    return errors


def validate_cloth_params(params: dict) -> list[str]:
    """Validate add_cloth parameters. Returns list of errors."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    quality = params.get("quality", 5)
    if not isinstance(quality, int) or quality < _CLOTH_QUALITY_MIN or quality > _CLOTH_QUALITY_MAX:
        errors.append(
            f"quality must be an integer between {_CLOTH_QUALITY_MIN} and "
            f"{_CLOTH_QUALITY_MAX}, got {quality!r}"
        )

    mass = params.get("mass", 0.3)
    if not isinstance(mass, (int, float)) or mass <= 0:
        errors.append(f"mass must be a positive number, got {mass!r}")

    air_damping = params.get("air_damping", 1.0)
    if not isinstance(air_damping, (int, float)) or air_damping < 0:
        errors.append(
            f"air_damping must be a non-negative number, got {air_damping!r}"
        )

    pin_group = params.get("pin_group")
    if pin_group is not None and not isinstance(pin_group, str):
        errors.append(f"pin_group must be a string, got {type(pin_group).__name__}")

    return errors


def validate_soft_body_params(params: dict) -> list[str]:
    """Validate add_soft_body parameters. Returns list of errors."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    mass = params.get("mass", 1.0)
    if not isinstance(mass, (int, float)) or mass <= 0:
        errors.append(f"mass must be a positive number, got {mass!r}")

    friction = params.get("friction", 0.5)
    if not isinstance(friction, (int, float)) or friction < 0:
        errors.append(f"friction must be a non-negative number, got {friction!r}")

    speed = params.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or speed <= 0:
        errors.append(f"speed must be a positive number, got {speed!r}")

    return errors


def validate_bake_physics_params(params: dict) -> list[str]:
    """Validate bake_physics parameters. Returns list of errors."""
    errors: list[str] = []

    start_frame = params.get("start_frame", 1)
    if not isinstance(start_frame, int) or start_frame < 0:
        errors.append(f"start_frame must be a non-negative integer, got {start_frame!r}")

    end_frame = params.get("end_frame", 250)
    if not isinstance(end_frame, int) or end_frame < 1:
        errors.append(f"end_frame must be a positive integer, got {end_frame!r}")

    if (isinstance(start_frame, int) and isinstance(end_frame, int)
            and end_frame <= start_frame):
        errors.append(
            f"end_frame ({end_frame}) must be greater than "
            f"start_frame ({start_frame})"
        )

    return errors


# ---------------------------------------------------------------------------
# Blender handlers
# ---------------------------------------------------------------------------


def _get_mesh_object(name: str | None) -> object:
    """Validate and return a mesh object by name."""
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")
    return obj


def handle_add_rigid_body(params: dict) -> dict:
    """Add rigid body physics to a mesh object.

    Params:
        name: Object name (required).
        body_type: 'ACTIVE' or 'PASSIVE' (default 'ACTIVE').
        mass: Object mass in kg (default 1.0).
        friction: Surface friction (default 0.5).
        restitution: Bounciness 0-1 (default 0.0).
        collision_shape: Shape for collision detection (default 'CONVEX_HULL').
            One of BOX, SPHERE, CAPSULE, MESH, CONVEX_HULL.

    Returns dict with rigid body details.
    """
    errors = validate_rigid_body_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    body_type = params.get("body_type", "ACTIVE")
    mass = params.get("mass", 1.0)
    friction = params.get("friction", 0.5)
    restitution = params.get("restitution", 0.0)
    collision_shape = params.get("collision_shape", "CONVEX_HULL")

    # Ensure rigid body world exists
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()

    # Select and make active
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add rigid body
    bpy.ops.rigidbody.object_add(type=body_type)

    rb = obj.rigid_body
    rb.mass = mass
    rb.friction = friction
    rb.restitution = restitution
    rb.collision_shape = collision_shape

    return {
        "object_name": name,
        "body_type": body_type,
        "mass": mass,
        "friction": friction,
        "restitution": restitution,
        "collision_shape": collision_shape,
    }


def handle_add_cloth(params: dict) -> dict:
    """Add cloth simulation to a mesh object.

    Params:
        name: Object name (required).
        quality: Simulation quality steps 1-10 (default 5).
        mass: Cloth mass in kg (default 0.3).
        air_damping: Air resistance (default 1.0).
        pin_group: Vertex group name to pin vertices (optional).

    Returns dict with cloth simulation details.
    """
    errors = validate_cloth_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    quality = params.get("quality", 5)
    mass = params.get("mass", 0.3)
    air_damping = params.get("air_damping", 1.0)
    pin_group = params.get("pin_group")

    # Select and make active
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add cloth modifier
    cloth_mod = obj.modifiers.new(name="Cloth", type="CLOTH")
    cloth_settings = cloth_mod.settings

    cloth_settings.quality = quality
    cloth_settings.mass = mass
    cloth_settings.air_damping = air_damping

    if pin_group:
        # Verify vertex group exists
        if pin_group not in obj.vertex_groups:
            raise ValueError(
                f"Vertex group '{pin_group}' not found on '{name}'. "
                f"Available: {[vg.name for vg in obj.vertex_groups]}"
            )
        cloth_settings.vertex_group_mass = pin_group

    return {
        "object_name": name,
        "quality": quality,
        "mass": mass,
        "air_damping": air_damping,
        "pin_group": pin_group,
    }


def handle_add_soft_body(params: dict) -> dict:
    """Add soft body simulation to a mesh object.

    Params:
        name: Object name (required).
        mass: Object mass (default 1.0).
        friction: Surface friction (default 0.5).
        speed: Simulation speed multiplier (default 1.0).

    Returns dict with soft body details.
    """
    errors = validate_soft_body_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    mass = params.get("mass", 1.0)
    friction = params.get("friction", 0.5)
    speed = params.get("speed", 1.0)

    # Select and make active
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add soft body modifier
    sb_mod = obj.modifiers.new(name="Softbody", type="SOFT_BODY")
    sb_settings = sb_mod.settings

    sb_settings.mass = mass
    sb_settings.friction = friction
    sb_settings.speed = speed

    return {
        "object_name": name,
        "mass": mass,
        "friction": friction,
        "speed": speed,
    }


def handle_bake_physics(params: dict) -> dict:
    """Bake physics simulation for a frame range.

    Params:
        start_frame: Start frame for bake (default 1).
        end_frame: End frame for bake (default 250).

    Returns dict with bake details.
    """
    errors = validate_bake_physics_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    start_frame = params.get("start_frame", 1)
    end_frame = params.get("end_frame", 250)

    scene = bpy.context.scene

    # Configure frame range
    scene.frame_start = start_frame
    scene.frame_end = end_frame

    # Bake rigid body world if present
    baked_types = []
    if scene.rigidbody_world is not None:
        point_cache = scene.rigidbody_world.point_cache
        point_cache.frame_start = start_frame
        point_cache.frame_end = end_frame
        bpy.ops.ptcache.bake({"point_cache": point_cache}, bake=True)
        baked_types.append("rigid_body")

    # Bake cloth and soft body for each object that has them
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        for mod in obj.modifiers:
            if mod.type in ("CLOTH", "SOFT_BODY"):
                pc = mod.point_cache
                pc.frame_start = start_frame
                pc.frame_end = end_frame
                bpy.ops.ptcache.bake({"point_cache": pc}, bake=True)
                baked_types.append(f"{mod.type.lower()}:{obj.name}")

    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "frame_count": end_frame - start_frame + 1,
        "baked_types": baked_types,
    }
