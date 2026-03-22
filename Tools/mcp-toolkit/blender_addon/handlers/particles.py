"""Particle system handlers for Blender addon.

Provides:
- handle_add_particle_system: Add emitter or hair particle system (PART-01)
- handle_configure_particle_physics: Configure particle physics settings (PART-02)
- handle_hair_grooming: Hair grooming operations (PART-03)

All handlers follow the standard params-dict-in, result-dict-out pattern.
Validation functions are pure-logic and testable without Blender.
"""

from __future__ import annotations

import bpy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PARTICLE_TYPES = frozenset({"EMITTER", "HAIR"})

_HAIR_OPERATIONS = frozenset({"COMB", "CUT", "LENGTH", "PUFF", "SMOOTH"})

_PHYSICS_SETTINGS_KEYS = frozenset({
    "mass", "drag", "brownian", "damping", "timestep",
    "gravity", "size", "random_size", "lifetime_random",
    "factor_random", "angular_velocity_factor",
})


# ---------------------------------------------------------------------------
# Pure-logic validators (testable without Blender)
# ---------------------------------------------------------------------------


def validate_particle_system_params(params: dict) -> list[str]:
    """Validate add_particle_system parameters. Returns list of errors."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    particle_type = params.get("particle_type", "EMITTER")
    if particle_type not in _PARTICLE_TYPES:
        errors.append(
            f"Invalid particle_type: {particle_type!r}. "
            f"Valid: {sorted(_PARTICLE_TYPES)}"
        )

    count = params.get("count", 1000)
    if not isinstance(count, int) or count < 1:
        errors.append(f"count must be a positive integer, got {count!r}")

    lifetime = params.get("lifetime", 50.0)
    if not isinstance(lifetime, (int, float)) or lifetime <= 0:
        errors.append(f"lifetime must be a positive number, got {lifetime!r}")

    start_frame = params.get("start_frame", 1)
    end_frame = params.get("end_frame", 200)
    if not isinstance(start_frame, (int, float)):
        errors.append(f"start_frame must be numeric, got {start_frame!r}")
    if not isinstance(end_frame, (int, float)):
        errors.append(f"end_frame must be numeric, got {end_frame!r}")
    if (isinstance(start_frame, (int, float))
            and isinstance(end_frame, (int, float))
            and end_frame <= start_frame):
        errors.append(
            f"end_frame ({end_frame}) must be greater than "
            f"start_frame ({start_frame})"
        )

    velocity = params.get("velocity", 0.0)
    if not isinstance(velocity, (int, float)):
        errors.append(f"velocity must be numeric, got {velocity!r}")

    gravity = params.get("gravity", 1.0)
    if not isinstance(gravity, (int, float)):
        errors.append(f"gravity must be numeric, got {gravity!r}")

    size = params.get("size", 0.05)
    if not isinstance(size, (int, float)) or size <= 0:
        errors.append(f"size must be a positive number, got {size!r}")

    return errors


def validate_particle_physics_params(params: dict) -> list[str]:
    """Validate configure_particle_physics parameters. Returns list of errors."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    system_name = params.get("system_name")
    if not system_name or not isinstance(system_name, str):
        errors.append("system_name is required and must be a non-empty string")

    settings = params.get("settings")
    if settings is not None:
        if not isinstance(settings, dict):
            errors.append("settings must be a dict")
        else:
            bad_keys = set(settings.keys()) - _PHYSICS_SETTINGS_KEYS
            if bad_keys:
                errors.append(
                    f"Invalid settings keys: {sorted(bad_keys)}. "
                    f"Allowed: {sorted(_PHYSICS_SETTINGS_KEYS)}"
                )
            # Validate numeric values
            for key, val in settings.items():
                if key in _PHYSICS_SETTINGS_KEYS:
                    if not isinstance(val, (int, float)):
                        errors.append(
                            f"settings.{key} must be numeric, got {val!r}"
                        )

    return errors


def validate_hair_grooming_params(params: dict) -> list[str]:
    """Validate hair_grooming parameters. Returns list of errors."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    operation = params.get("operation")
    if not operation:
        errors.append("operation is required")
    elif operation not in _HAIR_OPERATIONS:
        errors.append(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_HAIR_OPERATIONS)}"
        )

    strength = params.get("strength", 0.5)
    if not isinstance(strength, (int, float)) or strength < 0 or strength > 1:
        errors.append(f"strength must be a float between 0 and 1, got {strength!r}")

    radius = params.get("radius", 50.0)
    if not isinstance(radius, (int, float)) or radius <= 0:
        errors.append(f"radius must be a positive number, got {radius!r}")

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


def handle_add_particle_system(params: dict) -> dict:
    """Add a particle system (emitter or hair) to an object.

    Params:
        name: Object name (required).
        particle_type: 'EMITTER' or 'HAIR' (default 'EMITTER').
        count: Number of particles (default 1000).
        lifetime: Particle lifetime in frames (default 50.0).
        start_frame: Emission start frame (default 1).
        end_frame: Emission end frame (default 200).
        velocity: Initial velocity (default 0.0).
        gravity: Gravity multiplier (default 1.0).
        size: Particle display size (default 0.05).

    Returns dict with particle system details.
    """
    errors = validate_particle_system_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    particle_type = params.get("particle_type", "EMITTER")
    count = params.get("count", 1000)
    lifetime = params.get("lifetime", 50.0)
    start_frame = params.get("start_frame", 1)
    end_frame = params.get("end_frame", 200)
    velocity = params.get("velocity", 0.0)
    gravity = params.get("gravity", 1.0)
    size = params.get("size", 0.05)

    # Add particle system modifier
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.particle_system_add()

    ps = obj.particle_systems[-1]
    ps_settings = ps.settings

    ps_settings.type = particle_type
    ps_settings.count = count
    ps_settings.lifetime = lifetime
    ps_settings.frame_start = start_frame
    ps_settings.frame_end = end_frame
    ps_settings.normal_factor = velocity
    ps_settings.effector_weights.gravity = gravity
    ps_settings.particle_size = size

    system_name = ps.name

    return {
        "object_name": name,
        "system_name": system_name,
        "particle_type": particle_type,
        "count": count,
        "lifetime": lifetime,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "velocity": velocity,
        "gravity": gravity,
        "size": size,
    }


def handle_configure_particle_physics(params: dict) -> dict:
    """Configure physics settings on an existing particle system.

    Params:
        name: Object name (required).
        system_name: Particle system name (required).
        settings: Dict of physics settings (mass, drag, brownian,
            damping, timestep, gravity, size, random_size,
            lifetime_random, factor_random, angular_velocity_factor).

    Returns dict with applied settings.
    """
    errors = validate_particle_physics_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    system_name = params["system_name"]

    ps = obj.particle_systems.get(system_name)
    if ps is None:
        raise ValueError(
            f"Particle system '{system_name}' not found on '{name}'. "
            f"Available: {[s.name for s in obj.particle_systems]}"
        )

    settings = params.get("settings") or {}
    ps_settings = ps.settings
    applied = {}

    setting_map = {
        "mass": "mass",
        "drag": "drag_factor",
        "brownian": "brownian_factor",
        "damping": "damping",
        "timestep": "timestep",
        "size": "particle_size",
        "random_size": "size_random",
        "lifetime_random": "lifetime_random",
        "factor_random": "factor_random",
        "angular_velocity_factor": "angular_velocity_factor",
    }

    for key, val in settings.items():
        if key == "gravity":
            ps_settings.effector_weights.gravity = val
            applied[key] = val
        elif key in setting_map:
            attr = setting_map[key]
            setattr(ps_settings, attr, val)
            applied[key] = val

    return {
        "object_name": name,
        "system_name": system_name,
        "applied_settings": applied,
    }


def handle_hair_grooming(params: dict) -> dict:
    """Hair grooming operations on a hair particle system.

    Params:
        name: Object name (required).
        operation: One of COMB, CUT, LENGTH, PUFF, SMOOTH (required).
        strength: Operation strength 0-1 (default 0.5).
        radius: Brush radius (default 50.0).

    Returns dict with operation details.
    """
    errors = validate_hair_grooming_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    operation = params["operation"]
    strength = params.get("strength", 0.5)
    radius = params.get("radius", 50.0)

    # Verify object has a hair particle system
    hair_ps = None
    for ps in obj.particle_systems:
        if ps.settings.type == "HAIR":
            hair_ps = ps
            break
    if hair_ps is None:
        raise ValueError(f"No hair particle system found on '{name}'")

    # Set active particle system
    obj.particle_systems.active_index = list(
        obj.particle_systems
    ).index(hair_ps)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Enter particle edit mode -- wrap in try/finally to guarantee
    # we restore OBJECT mode even if grooming operations fail.
    bpy.ops.object.mode_set(mode="PARTICLE_EDIT")
    try:
        # Configure tool settings
        pe = bpy.context.scene.tool_settings.particle_edit
        pe.use_emitter_deflect = False

        tool_map = {
            "COMB": "COMB",
            "CUT": "CUT",
            "LENGTH": "LENGTH",
            "PUFF": "PUFF",
            "SMOOTH": "SMOOTH",
        }
        pe.tool = tool_map[operation]
        pe.brush.strength = strength
        pe.brush.size = int(radius)

        # Apply a stroke at object center
        loc = obj.location
        stroke = [{
            "name": "stroke",
            "is_start": True,
            "location": (loc.x, loc.y, loc.z),
            "mouse": (0, 0),
            "mouse_event": (0, 0),
            "pen_flip": False,
            "pressure": 1.0,
            "size": int(radius),
            "time": 0.0,
            "x_tilt": 0.0,
            "y_tilt": 0.0,
        }]

        bpy.ops.particle.brush_edit(stroke=stroke)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "system_name": hair_ps.name,
        "operation": operation,
        "strength": strength,
        "radius": radius,
    }
