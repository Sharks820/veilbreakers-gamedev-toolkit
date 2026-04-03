"""Viewport screenshot, contact sheet, shading, navigation, and beauty setup handlers.

Provides:
- handle_get_viewport_screenshot: Capture viewport as image (with auto beauty setup)
- handle_render_contact_sheet: Multi-angle contact sheet (with auto beauty setup)
- handle_set_shading: Switch viewport shading mode
- handle_navigate_camera: Position scene camera
- handle_setup_beauty_scene: Professional viewport presentation setup
- handle_setup_dark_fantasy_lighting: 3-point dark fantasy lighting rig
- handle_setup_ground_plane: Dark reflective ground plane
- handle_auto_frame_camera: Frame camera to object bounding box
- handle_run_quality_checks: Post-generation mesh quality verification
"""

from __future__ import annotations

import math
import os
import tempfile
import uuid

import bpy

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Beauty lighting presets
BEAUTY_KEY_LIGHT = {
    "name": "VB_Beauty_Key",
    "type": "AREA",
    "energy": 2.0,
    "color_temp": 3200,  # warm
    "color": (1.0, 0.85, 0.7),  # warm fallback
    "size": 2.0,
    "azimuth": 45.0,
    "elevation": 45.0,
    "distance_factor": 3.0,
    "use_shadow": True,
}

BEAUTY_FILL_LIGHT = {
    "name": "VB_Beauty_Fill",
    "type": "AREA",
    "energy": 0.5,
    "color_temp": 6500,  # cool
    "color": (0.7, 0.85, 1.0),  # cool fallback
    "size": 3.0,
    "azimuth": -135.0,
    "elevation": 15.0,
    "distance_factor": 4.0,
    "use_shadow": False,
}

BEAUTY_RIM_LIGHT = {
    "name": "VB_Beauty_Rim",
    "type": "AREA",
    "energy": 1.5,
    "color": (1.0, 1.0, 1.0),  # neutral
    "size": 1.5,
    "azimuth": 180.0,
    "elevation": 30.0,
    "distance_factor": 3.5,
    "use_shadow": False,
}

BEAUTY_LIGHT_PREFIX = "VB_Beauty_"

DARK_FANTASY_LIGHTING_PRESETS = {
    "default": {
        "ambient": 0.05,
        "world_color": (0.01, 0.01, 0.02, 1.0),
        "sun": None,
        "key_energy": 2.0,
        "fill_energy": 0.5,
        "rim_energy": 1.5,
        "mist_start": 8.0,
        "mist_depth": 55.0,
    },
    "forest_healthy": {
        "ambient": 0.035,
        "world_color": (0.03, 0.04, 0.05, 1.0),
        "sun": {"energy": 1.7, "azimuth": -40.0, "elevation": 26.0, "color": (0.62, 0.70, 0.56)},
        "key_energy": 1.6,
        "fill_energy": 0.35,
        "rim_energy": 1.1,
        "mist_start": 10.0,
        "mist_depth": 62.0,
    },
    "forest_transition": {
        "ambient": 0.026,
        "world_color": (0.02, 0.025, 0.035, 1.0),
        "sun": {"energy": 1.2, "azimuth": -55.0, "elevation": 18.0, "color": (0.54, 0.61, 0.67)},
        "key_energy": 1.35,
        "fill_energy": 0.25,
        "rim_energy": 0.95,
        "mist_start": 6.0,
        "mist_depth": 44.0,
    },
    "forest_review": {
        "ambient": 0.055,
        "world_color": (0.07, 0.08, 0.09, 1.0),
        "sun": {"energy": 2.2, "azimuth": -38.0, "elevation": 30.0, "color": (0.74, 0.76, 0.68)},
        "key_energy": 1.85,
        "fill_energy": 0.70,
        "rim_energy": 1.20,
        "mist_start": 14.0,
        "mist_depth": 80.0,
    },
    "veil_corrupted": {
        "ambient": 0.02,
        "world_color": (0.015, 0.012, 0.025, 1.0),
        "sun": {"energy": 0.7, "azimuth": -65.0, "elevation": 12.0, "color": (0.44, 0.40, 0.54)},
        "key_energy": 1.0,
        "fill_energy": 0.14,
        "rim_energy": 0.85,
        "mist_start": 4.0,
        "mist_depth": 30.0,
    },
}

# Ground plane settings
GROUND_PLANE_NAME = "VB_Beauty_Ground"
GROUND_MATERIAL_NAME = "VB_Beauty_Ground_Mat"
GROUND_COLOR = (0.1, 0.1, 0.1, 1.0)
GROUND_ROUGHNESS = 0.6
GROUND_SCALE_FACTOR = 8.0

# Camera settings
BEAUTY_CAMERA_NAME = "VB_Beauty_Camera"
BEAUTY_FOCAL_LENGTH = 50.0
BEAUTY_ELEVATION_DEG = 30.0
BEAUTY_DISTANCE_FACTOR = 2.0

# HDRI settings for Material Preview
BEAUTY_STUDIO_LIGHT = "forest.exr"
BEAUTY_STUDIO_INTENSITY = 1.0

# Minimum quality thresholds
MIN_VERT_COUNT = 500
MIN_UV_COVERAGE = 0.01  # any UV coverage counts


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------

def compute_light_position(
    center: tuple[float, float, float],
    distance: float,
    azimuth_deg: float,
    elevation_deg: float,
) -> tuple[float, float, float]:
    """Compute 3D position from spherical coordinates around a center point.

    Args:
        center: (x, y, z) target center.
        azimuth_deg: Horizontal angle in degrees (0=front, 90=right).
        elevation_deg: Vertical angle in degrees (0=horizon, 90=above).
        distance: Distance from center.

    Returns:
        (x, y, z) world-space position.
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = center[0] + distance * math.cos(el) * math.cos(az)
    y = center[1] + distance * math.cos(el) * math.sin(az)
    z = center[2] + distance * math.sin(el)
    return (x, y, z)


def compute_camera_distance(
    dimensions: tuple[float, float, float],
    focal_length: float = BEAUTY_FOCAL_LENGTH,
) -> float:
    """Compute camera distance from object dimensions using bounding sphere.

    Longer focal lengths compress perspective and effectively bring the subject
    closer, so we push the camera farther out proportionally to maintain correct
    framing (distance scales with focal_length / reference 50mm).

    Args:
        dimensions: (width, height, depth) of the object.
        focal_length: Lens focal length in mm (default 50mm).

    Returns:
        Camera distance (at least 2.0 units).
    """
    bounding_radius = math.sqrt(
        dimensions[0] ** 2 + dimensions[1] ** 2 + dimensions[2] ** 2
    ) / 2.0
    focal_scale = focal_length / 50.0
    distance = max(bounding_radius * BEAUTY_DISTANCE_FACTOR * focal_scale, 2.0)
    return distance


def compute_ground_size(dimensions: tuple[float, float, float]) -> float:
    """Compute ground plane size based on object dimensions.

    Returns a size that is GROUND_SCALE_FACTOR times the largest dimension,
    with a minimum of 4.0.
    """
    largest = max(dimensions)
    return max(largest * GROUND_SCALE_FACTOR, 4.0)


def compute_ground_z(obj_location_z: float, half_height: float) -> float:
    """Compute ground plane Z position (bottom of object).

    Args:
        obj_location_z: Object origin Z.
        half_height: Half the object height (dimensions.z / 2).

    Returns:
        Z coordinate for the ground plane.
    """
    return obj_location_z - half_height


def run_quality_checks_pure(
    vert_count: int,
    has_materials: bool,
    has_textures: bool,
    has_uvs: bool,
    uv_area: float,
    face_count: int,
) -> list[str]:
    """Run quality checks on mesh metrics (pure logic, no bpy).

    Args:
        vert_count: Number of vertices.
        has_materials: Whether object has at least one material slot.
        has_textures: Whether any material has image texture nodes.
        has_uvs: Whether mesh has UV layers.
        uv_area: Total UV area (0.0 if no UVs).
        face_count: Number of faces.

    Returns:
        List of issue strings. Empty list means all checks passed.
    """
    issues: list[str] = []

    if vert_count < MIN_VERT_COUNT:
        issues.append(
            f"Low vertex count: {vert_count} (minimum {MIN_VERT_COUNT} for "
            f"non-primitive mesh)"
        )

    if not has_materials:
        issues.append("No materials assigned")
    elif not has_textures:
        issues.append("Materials have no image textures (blank material)")

    if not has_uvs:
        issues.append("No UV maps present")
    elif uv_area < MIN_UV_COVERAGE:
        issues.append(
            f"UV coverage too low: {uv_area:.4f} (possible unwrapped or "
            f"collapsed UVs)"
        )

    if face_count == 0:
        issues.append("Mesh has no faces")

    return issues


# ---------------------------------------------------------------------------
# Temp path helper
# ---------------------------------------------------------------------------

def _unique_temp_path(prefix: str, suffix: str = ".png") -> str:
    """Generate a unique temp file path to avoid race conditions."""
    return os.path.join(
        tempfile.gettempdir(), f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"
    )


# ---------------------------------------------------------------------------
# State save/restore for beauty setup
# ---------------------------------------------------------------------------

def _save_viewport_state() -> dict:
    """Capture current viewport shading state for later restoration."""
    state = {"areas": []}
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    s = space.shading
                    state["areas"].append({
                        "space": space,
                        "shading_type": s.type,
                        "use_scene_lights": s.use_scene_lights,
                        "use_scene_world": s.use_scene_world,
                        "studio_light": getattr(s, "studio_light", ""),
                        "studiolight_rotate_z": getattr(
                            s, "studiolight_rotate_z", 0.0
                        ),
                        "studiolight_intensity": getattr(
                            s, "studiolight_intensity", 1.0
                        ),
                    })
    return state


def _restore_viewport_state(state: dict) -> None:
    """Restore previously saved viewport shading state."""
    for entry in state.get("areas", []):
        space = entry["space"]
        s = space.shading
        s.type = entry["shading_type"]
        s.use_scene_lights = entry["use_scene_lights"]
        s.use_scene_world = entry["use_scene_world"]
        if hasattr(s, "studio_light"):
            s.studio_light = entry["studio_light"]
        if hasattr(s, "studiolight_rotate_z"):
            s.studiolight_rotate_z = entry["studiolight_rotate_z"]
        if hasattr(s, "studiolight_intensity"):
            s.studiolight_intensity = entry["studiolight_intensity"]


def _save_eevee_state() -> dict:
    """Capture current EEVEE settings for later restoration."""
    scene = bpy.context.scene
    state = {
        "render_engine": scene.render.engine,
    }
    # EEVEE settings may not exist in all engine modes
    eevee = getattr(scene, "eevee", None)
    if eevee:
        state["use_bloom"] = getattr(eevee, "use_bloom", False)
        state["bloom_threshold"] = getattr(eevee, "bloom_threshold", 0.8)
        state["bloom_intensity"] = getattr(eevee, "bloom_intensity", 0.05)
        state["use_gtao"] = getattr(eevee, "use_gtao", False)
        state["gtao_distance"] = getattr(eevee, "gtao_distance", 0.2)
    return state


def _restore_eevee_state(state: dict) -> None:
    """Restore previously saved EEVEE settings."""
    scene = bpy.context.scene
    scene.render.engine = state.get("render_engine", "BLENDER_EEVEE_NEXT")
    eevee = getattr(scene, "eevee", None)
    if eevee:
        if "use_bloom" in state and hasattr(eevee, "use_bloom"):
            eevee.use_bloom = state["use_bloom"]
        if "bloom_threshold" in state and hasattr(eevee, "bloom_threshold"):
            eevee.bloom_threshold = state["bloom_threshold"]
        if "bloom_intensity" in state and hasattr(eevee, "bloom_intensity"):
            eevee.bloom_intensity = state["bloom_intensity"]
        if "use_gtao" in state and hasattr(eevee, "use_gtao"):
            eevee.use_gtao = state["use_gtao"]
        if "gtao_distance" in state and hasattr(eevee, "gtao_distance"):
            eevee.gtao_distance = state["gtao_distance"]


# ---------------------------------------------------------------------------
# Beauty cleanup helper
# ---------------------------------------------------------------------------

def _cleanup_beauty_objects() -> list[str]:
    """Remove all VB_Beauty_ prefixed objects and lights from the scene.

    Returns list of removed object names.
    """
    removed = []
    # Collect objects to remove (can't modify collection while iterating)
    to_remove = [
        obj for obj in bpy.data.objects
        if obj.name.startswith(BEAUTY_LIGHT_PREFIX)
        or obj.name == GROUND_PLANE_NAME
        or obj.name == BEAUTY_CAMERA_NAME
    ]
    for obj in to_remove:
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
    return removed


# ---------------------------------------------------------------------------
# Beauty scene setup
# ---------------------------------------------------------------------------

def _apply_viewport_shading() -> int:
    """Apply Material Preview shading with dark HDRI to all 3D viewports.

    Returns the number of viewports configured.
    """
    configured = 0
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    s = space.shading
                    s.type = "MATERIAL"
                    s.use_scene_lights = True
                    s.use_scene_world = False
                    # Use dark HDRI for professional look
                    if hasattr(s, "studio_light"):
                        s.studio_light = BEAUTY_STUDIO_LIGHT
                    if hasattr(s, "studiolight_rotate_z"):
                        s.studiolight_rotate_z = 0.0
                    if hasattr(s, "studiolight_intensity"):
                        s.studiolight_intensity = BEAUTY_STUDIO_INTENSITY
                    configured += 1
    return configured


def _configure_eevee() -> dict:
    """Configure EEVEE for fast, good-looking viewport rendering.

    Tries BLENDER_EEVEE_NEXT first (Blender 4.x), falls back to
    BLENDER_EEVEE (Blender 3.x).

    Returns dict with configured settings.
    """
    scene = bpy.context.scene
    result = {}

    # Try EEVEE Next (Blender 4.x) first, then classic EEVEE
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            result["engine"] = engine
            break
        except TypeError:
            continue
    else:
        result["engine"] = scene.render.engine
        result["engine_warning"] = "Could not set EEVEE engine"

    eevee = getattr(scene, "eevee", None)
    if eevee:
        # Bloom for glow effects
        if hasattr(eevee, "use_bloom"):
            eevee.use_bloom = True
            result["bloom"] = True
        if hasattr(eevee, "bloom_threshold"):
            eevee.bloom_threshold = 0.8
        if hasattr(eevee, "bloom_intensity"):
            eevee.bloom_intensity = 0.1
        # Screen space AO for depth
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
            result["ssao"] = True
        if hasattr(eevee, "gtao_distance"):
            eevee.gtao_distance = 0.2

    return result


def handle_setup_beauty_scene(params: dict) -> dict:
    """Set up professional viewport presentation for screenshots.

    Configures Material Preview shading with dark HDRI, sets up EEVEE
    with bloom and SSAO. Optionally targets a specific object for
    camera framing.

    Params:
        object_name (str, optional): Object to focus beauty setup on.

    Returns:
        Dict with setup details.
    """
    object_name = params.get("object_name")

    # Clean up any previous beauty objects
    removed = _cleanup_beauty_objects()

    # Apply viewport shading
    viewport_count = _apply_viewport_shading()

    # Configure EEVEE
    eevee_config = _configure_eevee()

    result = {
        "viewports_configured": viewport_count,
        "eevee": eevee_config,
        "shading": "MATERIAL",
        "studio_light": BEAUTY_STUDIO_LIGHT,
    }

    if removed:
        result["cleaned_up"] = removed

    if object_name:
        result["target_object"] = object_name

    return result


# ---------------------------------------------------------------------------
# Dark fantasy lighting
# ---------------------------------------------------------------------------

def _create_area_light(
    preset: dict,
    center: tuple[float, float, float],
    base_distance: float,
) -> object:
    """Create an area light from a preset definition.

    Args:
        preset: Light preset dict with name, energy, color, etc.
        center: Target center point.
        base_distance: Base distance (object bounding sphere * factor).

    Returns:
        The created light object.
    """
    from mathutils import Vector

    name = preset["name"]
    light_data = bpy.data.lights.new(name=name, type=preset["type"])
    light_data.energy = preset["energy"]
    light_data.color = preset["color"][:3]
    if hasattr(light_data, "size"):
        light_data.size = preset["size"]
    if hasattr(light_data, "use_shadow"):
        light_data.use_shadow = preset.get("use_shadow", True)

    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)

    # Position using spherical coordinates
    distance = base_distance * preset.get("distance_factor", 3.0)
    pos = compute_light_position(
        center, distance,
        preset["azimuth"], preset["elevation"],
    )
    light_obj.location = pos

    # Point at center
    direction = Vector(center) - Vector(pos)
    if direction.length > 0.001:
        light_obj.rotation_euler = direction.to_track_quat(
            "-Z", "Y"
        ).to_euler()

    return light_obj


def _create_sun_light(
    *,
    name: str,
    energy: float,
    color: tuple[float, float, float],
    azimuth: float,
    elevation: float,
) -> object:
    """Create a directional sun light for outdoor readability."""
    light_data = bpy.data.lights.new(name=name, type="SUN")
    light_data.energy = energy
    light_data.color = color
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (
        math.radians(90.0 - elevation),
        0.0,
        math.radians(azimuth),
    )
    return light_obj


def _lighting_preset_for_name(name: str) -> dict:
    preset_name = str(name or "default").strip().lower()
    return DARK_FANTASY_LIGHTING_PRESETS.get(
        preset_name,
        DARK_FANTASY_LIGHTING_PRESETS["default"],
    )


def handle_setup_dark_fantasy_lighting(params: dict) -> dict:
    """Set up 3-point dark fantasy lighting rig.

    Creates key, fill, and rim area lights positioned around the target
    object (or scene origin). Optimized for dark fantasy aesthetic:
    warm key, cool fill, neutral rim, very dark ambient.

    Params:
        object_name (str, optional): Object to light around.
        ambient (float, optional): World ambient strength (default from preset).
        preset (str, optional): `default`, `forest_healthy`,
            `forest_transition`, or `veil_corrupted`.

    Returns:
        Dict with created light info.
    """
    object_name = params.get("object_name")
    preset_name = params.get("preset", "default")
    preset = _lighting_preset_for_name(preset_name)
    ambient = params.get("ambient", preset["ambient"])

    # Determine center and distance
    center = (0.0, 0.0, 0.0)
    base_distance = 3.0

    if object_name:
        target = bpy.data.objects.get(object_name)
        if target:
            center = tuple(target.location)
            # Use bounding sphere radius
            dims = tuple(target.dimensions)
            base_distance = max(
                math.sqrt(dims[0] ** 2 + dims[1] ** 2 + dims[2] ** 2) / 2.0,
                1.0,
            )

    # Remove existing beauty lights
    for obj in list(bpy.data.objects):
        if obj.name.startswith(BEAUTY_LIGHT_PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Create 3-point lighting
    lights_created = []
    tuned_lights = []
    for base in (BEAUTY_KEY_LIGHT, BEAUTY_FILL_LIGHT, BEAUTY_RIM_LIGHT):
        local = dict(base)
        if base["name"].endswith("Key"):
            local["energy"] = float(preset["key_energy"])
        elif base["name"].endswith("Fill"):
            local["energy"] = float(preset["fill_energy"])
        else:
            local["energy"] = float(preset["rim_energy"])
        tuned_lights.append(local)

    for light_preset in tuned_lights:
        light_obj = _create_area_light(light_preset, center, base_distance)
        lights_created.append({
            "name": light_obj.name,
            "energy": light_preset["energy"],
            "position": list(light_obj.location),
        })

    sun_cfg = preset.get("sun")
    if isinstance(sun_cfg, dict):
        sun_obj = _create_sun_light(
            name=f"{BEAUTY_LIGHT_PREFIX}Sun",
            energy=float(sun_cfg["energy"]),
            color=tuple(sun_cfg["color"]),
            azimuth=float(sun_cfg["azimuth"]),
            elevation=float(sun_cfg["elevation"]),
        )
        lights_created.append({
            "name": sun_obj.name,
            "energy": float(sun_cfg["energy"]),
            "position": list(sun_obj.location),
        })

    # Set dark ambient world
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("VB_Beauty_World")
        bpy.context.scene.world = world
    world.use_nodes = True
    if world.use_nodes and world.node_tree:
        bg_node = world.node_tree.nodes.get("Background")
        if bg_node is None:
            # Fresh world node tree may only have an Output node — create Background.
            bg_node = world.node_tree.nodes.new("ShaderNodeBackground")
            bg_node.location = (0, 0)
            out_node = world.node_tree.nodes.get("World Output") or world.node_tree.nodes.get("ShaderNodeOutputWorld")
            if out_node is None:
                out_node = world.node_tree.nodes.new("ShaderNodeOutputWorld")
                out_node.location = (300, 0)
            world.node_tree.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
        bg_node.inputs["Strength"].default_value = ambient
        bg_node.inputs["Color"].default_value = preset["world_color"]

    mist = getattr(world, "mist_settings", None)
    if mist is not None:
        mist.use_mist = True
        mist.start = float(preset["mist_start"])
        mist.depth = float(preset["mist_depth"])
        mist.falloff = "QUADRATIC"

    scene = bpy.context.scene
    eevee = getattr(scene, "eevee", None)
    if eevee is not None:
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
        if hasattr(eevee, "use_volumetric_lights"):
            eevee.use_volumetric_lights = True
        if hasattr(eevee, "use_volumetric_shadows"):
            eevee.use_volumetric_shadows = True

    return {
        "lights": lights_created,
        "ambient": ambient,
        "preset": str(preset_name),
        "center": list(center),
        "base_distance": base_distance,
    }


# ---------------------------------------------------------------------------
# Ground plane
# ---------------------------------------------------------------------------

def handle_setup_ground_plane(params: dict) -> dict:
    """Create a dark, slightly reflective ground plane below the object.

    Params:
        object_name (str, optional): Object to place ground under.
        color (list[float], optional): Ground color RGBA (default dark gray).
        roughness (float, optional): Surface roughness (default 0.6).

    Returns:
        Dict with ground plane info.
    """
    object_name = params.get("object_name")
    color = params.get("color", list(GROUND_COLOR))
    roughness = params.get("roughness", GROUND_ROUGHNESS)

    # Determine placement
    center_xy = (0.0, 0.0)
    ground_z = 0.0
    plane_size = 4.0

    if object_name:
        target = bpy.data.objects.get(object_name)
        if target:
            center_xy = (target.location.x, target.location.y)
            dims = tuple(target.dimensions)
            plane_size = compute_ground_size(dims)
            ground_z = compute_ground_z(
                target.location.z, dims[2] / 2.0
            )

    # Remove existing ground plane
    existing = bpy.data.objects.get(GROUND_PLANE_NAME)
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    # Create plane
    bpy.ops.mesh.primitive_plane_add(
        size=plane_size,
        location=(center_xy[0], center_xy[1], ground_z),
    )
    plane = bpy.context.active_object
    plane.name = GROUND_PLANE_NAME

    # Create dark material
    mat = bpy.data.materials.get(GROUND_MATERIAL_NAME)
    if not mat:
        mat = bpy.data.materials.new(name=GROUND_MATERIAL_NAME)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = tuple(color[:4]) if len(
            color
        ) >= 4 else (*color[:3], 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        # Slight metallic for reflections
        bsdf.inputs["Metallic"].default_value = 0.05

    plane.data.materials.clear()
    plane.data.materials.append(mat)

    return {
        "name": GROUND_PLANE_NAME,
        "size": plane_size,
        "position": [center_xy[0], center_xy[1], ground_z],
        "roughness": roughness,
        "color": color,
    }


# ---------------------------------------------------------------------------
# Auto-frame camera
# ---------------------------------------------------------------------------

def handle_auto_frame_camera(params: dict) -> dict:
    """Frame camera to object at professional distance and angle.

    Positions camera at 2x bounding sphere distance, 30-degree elevation,
    with 50mm focal length for flattering 3D asset presentation.

    Params:
        object_name (str): Object to frame (required).
        elevation (float, optional): Camera elevation in degrees (default 30).
        focal_length (float, optional): Lens focal length in mm (default 50).

    Returns:
        Dict with camera position and settings.
    """
    from mathutils import Vector

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required for auto_frame_camera")

    target = bpy.data.objects.get(object_name)
    if not target:
        raise ValueError(f"Object not found: {object_name}")

    elevation = params.get("elevation", BEAUTY_ELEVATION_DEG)
    focal_length = params.get("focal_length", BEAUTY_FOCAL_LENGTH)
    azimuth = params.get("azimuth", 35.0)

    # Calculate distance from object dimensions (accounts for focal length)
    dims = tuple(target.dimensions)
    distance = compute_camera_distance(dims, focal_length)
    center = tuple(target.location)

    # Position camera
    cam = bpy.data.objects.get(BEAUTY_CAMERA_NAME)
    if not cam:
        cam_data = bpy.data.cameras.new(BEAUTY_CAMERA_NAME)
        cam = bpy.data.objects.new(BEAUTY_CAMERA_NAME, cam_data)
        bpy.context.scene.collection.objects.link(cam)

    cam_data = cam.data
    cam_data.lens = focal_length
    cam_data.clip_start = 0.1
    cam_data.clip_end = max(distance * 10, 100.0)

    # Position using spherical coords (parameterized azimuth + elevation)
    pos = compute_light_position(center, distance, azimuth, elevation)
    cam.location = pos

    # Point at object center
    direction = Vector(center) - cam.location
    if direction.length > 0.001:
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    # Set as active camera
    bpy.context.scene.camera = cam

    return {
        "camera": BEAUTY_CAMERA_NAME,
        "position": list(cam.location),
        "target": list(center),
        "distance": distance,
        "focal_length": focal_length,
        "elevation": elevation,
        "azimuth": azimuth,
    }


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def _check_material_textures(obj) -> tuple[bool, bool]:
    """Check if object has materials and if they have image textures.

    Returns:
        (has_materials, has_textures)
    """
    if not obj.data.materials or len(obj.data.materials) == 0:
        return False, False

    has_materials = False
    has_textures = False

    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None:
            continue
        has_materials = True
        if mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image is not None:
                    has_textures = True
                    break
        if has_textures:
            break

    return has_materials, has_textures


def _compute_uv_area(mesh) -> float:
    """Compute total UV area for the active UV layer.

    Returns 0.0 if no UV layers exist.
    """
    if not mesh.uv_layers or len(mesh.uv_layers) == 0:
        return 0.0

    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        return 0.0

    total_area = 0.0
    for poly in mesh.polygons:
        if len(poly.loop_indices) < 3:
            continue
        # Compute UV polygon area using shoelace formula
        uvs = [uv_layer.data[li].uv for li in poly.loop_indices]
        n = len(uvs)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += uvs[i][0] * uvs[j][1]
            area -= uvs[j][0] * uvs[i][1]
        total_area += abs(area) / 2.0

    return total_area


def handle_run_quality_checks(params: dict) -> dict:
    """Run post-generation quality checks on a mesh object.

    Checks vertex count, material assignments, texture presence,
    UV unwrapping quality.

    Params:
        object_name (str): Object to check (required).

    Returns:
        Dict with issues list and pass/fail status.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required for quality_checks")

    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object not found: {object_name}")

    if obj.type != "MESH":
        return {
            "object_name": object_name,
            "passed": False,
            "issues": [f"Object is type '{obj.type}', not MESH"],
        }

    mesh = obj.data
    vert_count = len(mesh.vertices)
    face_count = len(mesh.polygons)
    has_materials, has_textures = _check_material_textures(obj)
    has_uvs = bool(mesh.uv_layers) and len(mesh.uv_layers) > 0
    uv_area = _compute_uv_area(mesh) if has_uvs else 0.0

    issues = run_quality_checks_pure(
        vert_count=vert_count,
        has_materials=has_materials,
        has_textures=has_textures,
        has_uvs=has_uvs,
        uv_area=uv_area,
        face_count=face_count,
    )

    return {
        "object_name": object_name,
        "passed": len(issues) == 0,
        "issues": issues,
        "metrics": {
            "vertices": vert_count,
            "faces": face_count,
            "has_materials": has_materials,
            "has_textures": has_textures,
            "has_uvs": has_uvs,
            "uv_area": round(uv_area, 4),
        },
    }


# ---------------------------------------------------------------------------
# Screenshot handler (with auto beauty setup)
# ---------------------------------------------------------------------------

def handle_get_viewport_screenshot(params: dict) -> dict:
    """Capture viewport screenshot with optional auto beauty setup.

    Unless skip_beauty is True, applies professional viewport shading
    before capture for consistently good-looking screenshots.

    Params:
        max_size (int): Max resolution (default 1024).
        filepath (str, optional): Output path.
        format (str): Image format (default PNG).
        skip_beauty (bool): Skip beauty setup (default False).

    Returns:
        Dict with filepath, dimensions, format.
    """
    max_size = params.get("max_size", 1024)
    filepath = params.get("filepath") or _unique_temp_path("vb_screenshot")
    fmt = params.get("format", "PNG").upper()
    skip_beauty = params.get("skip_beauty", False)

    scene = bpy.context.scene
    old_filepath = scene.render.filepath
    old_format = scene.render.image_settings.file_format
    old_x = scene.render.resolution_x
    old_y = scene.render.resolution_y

    # Apply beauty setup unless explicitly skipped
    viewport_state = None
    if not skip_beauty:
        viewport_state = _save_viewport_state()
        _apply_viewport_shading()

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

        # Restore viewport state if we changed it
        if viewport_state is not None:
            _restore_viewport_state(viewport_state)

    return {
        "filepath": filepath,
        "width": max_size,
        "height": max_size,
        "format": fmt.lower(),
        "beauty_applied": not skip_beauty,
    }


# ---------------------------------------------------------------------------
# Contact sheet handler (with auto beauty setup)
# ---------------------------------------------------------------------------

def handle_render_contact_sheet(params: dict) -> dict:
    """Render multi-angle contact sheet with auto beauty setup.

    Applies beauty viewport shading before rendering for consistently
    professional-looking contact sheets.

    Params:
        object_name (str): Object to render (required).
        angles (list): List of [azimuth, elevation] pairs.
        resolution (list[int]): [width, height] per frame.
        skip_beauty (bool): Skip beauty setup (default False).

    Returns:
        Dict with image paths, count, angles.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    target = bpy.data.objects.get(object_name)
    if not target:
        raise ValueError(f"Object not found: {object_name}")

    skip_beauty = params.get("skip_beauty", False)
    angles = params.get("angles", [
        [0, 0], [90, 0], [180, 0], [270, 0], [0, 90], [45, 30]
    ])
    resolution = params.get("resolution", [512, 512])

    # Apply beauty setup unless explicitly skipped
    viewport_state = None
    eevee_state = None
    temp_lights = []
    old_world_strength = None
    old_world_color = None
    old_world = None
    world = None
    if not skip_beauty:
        viewport_state = _save_viewport_state()
        eevee_state = _save_eevee_state()
        _apply_viewport_shading()
        _configure_eevee()

        # Auto-create temporary 3-point lighting rig for the render.
        # EEVEE renders need much higher energy than viewport preview,
        # so we scale the beauty presets up for render-quality output.
        _RENDER_ENERGY_SCALE = 80.0  # multiplier for EEVEE render
        _center = tuple(target.location)
        _dims = tuple(target.dimensions)
        _base_dist = max(
            math.sqrt(_dims[0] ** 2 + _dims[1] ** 2 + _dims[2] ** 2) / 2.0,
            1.0,
        )
        for preset in (BEAUTY_KEY_LIGHT, BEAUTY_FILL_LIGHT, BEAUTY_RIM_LIGHT):
            boosted = dict(preset)
            boosted["energy"] = preset["energy"] * _RENDER_ENERGY_SCALE
            light_obj = _create_area_light(boosted, _center, _base_dist)
            light_obj.name = f"_CS_Temp_{preset['name']}"
            temp_lights.append(light_obj)

        # Set dark ambient world for the render
        old_world = bpy.context.scene.world
        world = old_world
        if world is None:
            world = bpy.data.worlds.new("_CS_Temp_World")
            bpy.context.scene.world = world
            world.use_nodes = True
        if world.use_nodes and world.node_tree:
            bg_node = world.node_tree.nodes.get("Background")
            if bg_node is None:
                # Freshly created world may lack a Background node — create one.
                bg_node = world.node_tree.nodes.new("ShaderNodeBackground")
                bg_node.location = (0, 0)
                out_node = (world.node_tree.nodes.get("World Output")
                            or world.node_tree.nodes.get("ShaderNodeOutputWorld"))
                if out_node is None:
                    out_node = world.node_tree.nodes.new("ShaderNodeOutputWorld")
                    out_node.location = (300, 0)
                world.node_tree.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
            old_world_strength = bg_node.inputs["Strength"].default_value
            old_world_color = tuple(bg_node.inputs["Color"].default_value)
            bg_node.inputs["Strength"].default_value = 0.05
            bg_node.inputs["Color"].default_value = (0.01, 0.01, 0.02, 1.0)

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

        # Clean up temporary contact sheet lights
        for light_obj in temp_lights:
            light_data_ref = light_obj.data
            bpy.data.objects.remove(light_obj, do_unlink=True)
            if light_data_ref is not None:
                bpy.data.lights.remove(light_data_ref)

        # Restore world settings
        if old_world_strength is not None:
            cur_world = bpy.context.scene.world
            if cur_world and cur_world.use_nodes and cur_world.node_tree:
                bg_node = cur_world.node_tree.nodes.get("Background")
                if bg_node:
                    bg_node.inputs["Strength"].default_value = old_world_strength
                    bg_node.inputs["Color"].default_value = old_world_color

        temp_world = world
        bpy.context.scene.world = old_world
        if old_world is None and temp_world is not None and temp_world.name == "_CS_Temp_World":
            bpy.data.worlds.remove(temp_world)

        # Restore viewport/eevee state if we changed it
        if viewport_state is not None:
            _restore_viewport_state(viewport_state)
        if eevee_state is not None:
            _restore_eevee_state(eevee_state)

        # Remove ContactSheet_Camera from the scene to avoid polluting the outliner
        cs_cam = bpy.data.objects.get("ContactSheet_Camera")
        if cs_cam is not None:
            cs_cam_data = cs_cam.data
            bpy.data.objects.remove(cs_cam, do_unlink=True)
            if cs_cam_data is not None:
                bpy.data.cameras.remove(cs_cam_data)

    return {
        "paths": paths,
        "count": len(paths),
        "angles": angles,
        "object_name": object_name,
        "beauty_applied": not skip_beauty,
    }


# ---------------------------------------------------------------------------
# Shading and navigation (unchanged behavior)
# ---------------------------------------------------------------------------

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


def handle_interior_camera_shot(params: dict) -> dict:
    """Position camera at eye height (1.7 m) inside room bounds for interior preview.

    Params:
        object_name (str, optional): Object whose bounds define the room.
        room_bounds (list[float], optional): [min_x, min_y, min_z, max_x, max_y, max_z].
        eye_height (float): Camera height above floor (default 1.7 m).

    Returns:
        Dict with camera name, position, and look-at target.
    """
    from mathutils import Vector

    eye_height = params.get("eye_height", 1.7)
    room_bounds = params.get("room_bounds")
    object_name = params.get("object_name")

    # Derive bounds from object if not explicitly provided
    if room_bounds is None and object_name:
        target = bpy.data.objects.get(object_name)
        if target is None:
            raise ValueError(f"Object not found: {object_name}")
        loc = target.location
        dims = target.dimensions
        room_bounds = [
            loc.x - dims.x / 2, loc.y - dims.y / 2, loc.z,
            loc.x + dims.x / 2, loc.y + dims.y / 2, loc.z + dims.z,
        ]

    if room_bounds is None or len(room_bounds) != 6:
        raise ValueError("room_bounds must be [min_x, min_y, min_z, max_x, max_y, max_z]")

    min_x, min_y, min_z, max_x, max_y, max_z = room_bounds
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    # Place camera at one-quarter into the room, looking toward center
    cam_x = min_x + (max_x - min_x) * 0.25
    cam_y = min_y + (max_y - min_y) * 0.25
    eye_height = min(eye_height, max_z - min_z - 0.1)
    cam_z = min_z + eye_height

    cam = bpy.data.objects.get(BEAUTY_CAMERA_NAME)
    if not cam:
        cam_data = bpy.data.cameras.new(BEAUTY_CAMERA_NAME)
        cam = bpy.data.objects.new(BEAUTY_CAMERA_NAME, cam_data)
        bpy.context.scene.collection.objects.link(cam)

    cam.data.lens = 24.0  # wide-angle for interiors
    cam.data.clip_start = 0.1
    cam.data.clip_end = 200.0
    cam.location = Vector((cam_x, cam_y, cam_z))

    look_at = Vector((cx, cy, cam_z))  # horizontal look toward room center
    direction = look_at - cam.location
    if direction.length > 0.001:
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    bpy.context.scene.camera = cam

    return {
        "camera": BEAUTY_CAMERA_NAME,
        "position": [cam_x, cam_y, cam_z],
        "look_at": [cx, cy, cam_z],
        "eye_height": eye_height,
        "room_bounds": room_bounds,
    }


def handle_render_orthographic_views(params: dict) -> dict:
    """Render four orthographic views: front, right, top, isometric.

    Params:
        object_name (str): Object to render (required).
        resolution (list[int]): [width, height] per frame (default [512, 512]).

    Returns:
        Dict with paths list and count.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    target = bpy.data.objects.get(object_name)
    if not target:
        raise ValueError(f"Object not found: {object_name}")

    resolution = params.get("resolution", [512, 512])
    from mathutils import Vector

    center = target.location.copy()
    dims = tuple(target.dimensions)
    distance = compute_camera_distance(dims, focal_length=50.0) * 1.5

    # Orthographic camera views: (azimuth_deg, elevation_deg, label)
    _ORTHO_ANGLES = [
        (0.0,   0.0,  "front"),
        (90.0,  0.0,  "right"),
        (0.0,  90.0,  "top"),
        (45.0, 30.0,  "iso"),
    ]

    # Create/reuse a dedicated ortho camera
    _ORTHO_CAM_NAME = "VB_Ortho_Camera"
    ortho_cam = bpy.data.objects.get(_ORTHO_CAM_NAME)
    if not ortho_cam:
        ortho_data = bpy.data.cameras.new(_ORTHO_CAM_NAME)
        ortho_cam = bpy.data.objects.new(_ORTHO_CAM_NAME, ortho_data)
        bpy.context.scene.collection.objects.link(ortho_cam)

    ortho_cam.data.type = "ORTHO"
    largest_dim = max(dims) if dims else 1.0
    ortho_cam.data.ortho_scale = largest_dim * 1.5

    scene = bpy.context.scene
    old_cam = scene.camera
    old_x = scene.render.resolution_x
    old_y = scene.render.resolution_y
    old_filepath = scene.render.filepath
    old_format = scene.render.image_settings.file_format

    paths: list[str] = []
    try:
        scene.camera = ortho_cam
        scene.render.resolution_x = resolution[0]
        scene.render.resolution_y = resolution[1]
        scene.render.image_settings.file_format = "PNG"

        for i, (azimuth, elevation, label) in enumerate(_ORTHO_ANGLES):
            pos = compute_light_position(
                (center.x, center.y, center.z), distance, azimuth, elevation
            )
            ortho_cam.location = Vector(pos)
            direction = Vector((center.x, center.y, center.z)) - ortho_cam.location
            if direction.length > 0.001:
                ortho_cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

            path = _unique_temp_path(f"vb_ortho_{label}")
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            paths.append(path)
    finally:
        scene.camera = old_cam
        scene.render.resolution_x = old_x
        scene.render.resolution_y = old_y
        scene.render.filepath = old_filepath
        scene.render.image_settings.file_format = old_format

        # Clean up ortho camera
        ortho_cam_obj = bpy.data.objects.get(_ORTHO_CAM_NAME)
        if ortho_cam_obj is not None:
            ortho_cam_data = ortho_cam_obj.data
            bpy.data.objects.remove(ortho_cam_obj, do_unlink=True)
            if ortho_cam_data is not None:
                bpy.data.cameras.remove(ortho_cam_data)

    return {
        "paths": paths,
        "count": len(paths),
        "object_name": object_name,
        "views": [label for _, _, label in _ORTHO_ANGLES],
    }
