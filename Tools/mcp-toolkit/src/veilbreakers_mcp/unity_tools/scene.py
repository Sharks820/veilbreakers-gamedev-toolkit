"""unity_scene tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_terrain_setup_script,
    generate_tiled_terrain_setup_script,
    generate_object_scatter_script,
    generate_lighting_setup_script,
    generate_navmesh_bake_script,
    generate_animator_controller_script,
    generate_avatar_config_script,
    generate_animation_rigging_script,
)
from veilbreakers_mcp.shared.unity_templates.animation_templates import (
    generate_blend_tree_script,
    generate_additive_layer_script,
)




# ---------------------------------------------------------------------------
# Scene tool -- compound tool covering SCENE-01 through SCENE-07 plus SCENE-01b
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_scene(
    action: Literal[
        "setup_terrain",            # SCENE-01: terrain from heightmap + splatmaps
        "setup_tiled_terrain",      # SCENE-01b: multi-tile terrain import
        "scatter_objects",          # SCENE-02: density-based object placement
        "setup_lighting",           # SCENE-03: directional light, fog, post-processing
        "bake_navmesh",             # SCENE-04: NavMesh with agent settings
        "create_animator",          # SCENE-05: Animator Controller with states/transitions
        "configure_avatar",         # SCENE-06: Humanoid/Generic bone mapping
        "setup_animation_rigging",  # SCENE-07: TwoBoneIK, MultiAim constraints
        "create_blend_tree",        # ANIM3-03: directional/speed blend trees
        "create_additive_layer",    # ANIM3-04: additive animation layers
    ],
    # Common
    name: str = "default",
    # Terrain params
    heightmap_path: str = "",
    terrain_size: list[float] | None = None,
    terrain_resolution: int = 513,
    splatmap_layers: list[dict] | None = None,
    terrain_tiles: list[dict] | None = None,
    tile_parent_name: str = "VB_TerrainRoot",
    # Scatter params
    prefab_paths: list[str] | None = None,
    density: float = 0.5,
    min_slope: float = 0.0,
    max_slope: float = 45.0,
    min_altitude: float = 0.0,
    max_altitude: float = 1000.0,
    scatter_seed: int = 42,
    # Lighting params
    sun_color: list[float] | None = None,
    sun_intensity: float = 1.0,
    ambient_color: list[float] | None = None,
    fog_enabled: bool = True,
    fog_color: list[float] | None = None,
    fog_density: float = 0.01,
    skybox_material: str = "",
    time_of_day: str = "noon",
    # NavMesh params
    agent_radius: float = 0.5,
    agent_height: float = 2.0,
    nav_max_slope: float = 45.0,
    step_height: float = 0.4,
    nav_links: list[dict] | None = None,
    # Animator params
    states: list[dict] | None = None,
    transitions: list[dict] | None = None,
    parameters: list[dict] | None = None,
    blend_trees: list[dict] | None = None,
    # Avatar params
    fbx_path: str = "",
    animation_type: str = "Humanoid",
    bone_mapping: dict | None = None,
    # Animation Rigging params
    constraints: list[dict] | None = None,
    # Blend tree params (ANIM3-03)
    blend_type: str = "directional_8way",
    controller_name: str = "VB_Locomotion",
    motion_clips: dict[str, str] | None = None,
    # Additive layer params (ANIM3-04)
    layer_name: str = "Additive",
    base_layer_index: int = 0,
    additive_clips: list[dict] | None = None,
    default_weight: float = 1.0,
    avatar_mask_path: str = ""
) -> str:
    """Unity Scene setup -- terrain, object scattering, lighting, NavMesh, animation."""
    try:
        if action == "setup_terrain":
            return await _handle_scene_setup_terrain(
                heightmap_path, terrain_size, terrain_resolution, splatmap_layers
            )
        elif action == "setup_tiled_terrain":
            return await _handle_scene_setup_tiled_terrain(
                terrain_tiles, terrain_size, terrain_resolution, splatmap_layers,
                tile_parent_name,
            )
        elif action == "scatter_objects":
            return await _handle_scene_scatter_objects(
                prefab_paths, density, min_slope, max_slope,
                min_altitude, max_altitude, scatter_seed,
            )
        elif action == "setup_lighting":
            return await _handle_scene_setup_lighting(
                sun_color, sun_intensity, ambient_color, fog_enabled,
                fog_color, fog_density, skybox_material, time_of_day,
            )
        elif action == "bake_navmesh":
            return await _handle_scene_bake_navmesh(
                agent_radius, agent_height, nav_max_slope, step_height, nav_links,
            )
        elif action == "create_animator":
            return await _handle_scene_create_animator(
                name, states, transitions, parameters, blend_trees,
            )
        elif action == "configure_avatar":
            return await _handle_scene_configure_avatar(
                fbx_path, animation_type, bone_mapping,
            )
        elif action == "setup_animation_rigging":
            return await _handle_scene_setup_animation_rigging(name, constraints)
        elif action == "create_blend_tree":
            return await _handle_scene_create_blend_tree(
                blend_type, controller_name, states, parameters, motion_clips,
            )
        elif action == "create_additive_layer":
            return await _handle_scene_create_additive_layer(
                name, layer_name, base_layer_index, additive_clips,
                default_weight, avatar_mask_path,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_scene action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Scene action handlers
# ---------------------------------------------------------------------------


async def _handle_scene_setup_terrain(
    heightmap_path: str,
    terrain_size: list[float] | None,
    terrain_resolution: int,
    splatmap_layers: list[dict] | None,
) -> str:
    """Create terrain from heightmap (SCENE-01)."""
    if not heightmap_path:
        return json.dumps({
            "status": "error",
            "action": "setup_terrain",
            "message": "heightmap_path is required for setup_terrain action",
        })

    size_tuple = tuple(terrain_size) if terrain_size and len(terrain_size) == 3 else (1000, 600, 1000)

    script = generate_terrain_setup_script(
        heightmap_path=heightmap_path,
        size=size_tuple,
        resolution=terrain_resolution,
        splatmap_layers=splatmap_layers,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_TerrainSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_terrain", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_terrain",
            "script_path": abs_path,
            "heightmap_path": heightmap_path,
            "terrain_size": list(size_tuple),
            "resolution": terrain_resolution,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_setup_tiled_terrain(
    terrain_tiles: list[dict] | None,
    terrain_size: list[float] | None,
    terrain_resolution: int,
    splatmap_layers: list[dict] | None,
    tile_parent_name: str,
) -> str:
    """Create a tiled terrain set from multiple heightmap tiles."""
    if not terrain_tiles:
        return json.dumps({
            "status": "error",
            "action": "setup_tiled_terrain",
            "message": "terrain_tiles is required for setup_tiled_terrain action",
        })

    size_tuple = tuple(terrain_size) if terrain_size and len(terrain_size) == 3 else (1000, 600, 1000)

    script = generate_tiled_terrain_setup_script(
        tiles=terrain_tiles,
        default_size=size_tuple,
        default_resolution=terrain_resolution,
        splatmap_layers=splatmap_layers,
        parent_name=tile_parent_name,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_TiledTerrainSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_tiled_terrain", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_tiled_terrain",
            "script_path": abs_path,
            "tile_count": len(terrain_tiles),
            "terrain_size": list(size_tuple),
            "resolution": terrain_resolution,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_scatter_objects(
    prefab_paths: list[str] | None,
    density: float,
    min_slope: float,
    max_slope: float,
    min_altitude: float,
    max_altitude: float,
    seed: int,
) -> str:
    """Scatter objects on terrain (SCENE-02)."""
    if not prefab_paths:
        return json.dumps({
            "status": "error",
            "action": "scatter_objects",
            "message": "prefab_paths is required for scatter_objects action",
        })

    script = generate_object_scatter_script(
        prefab_paths=prefab_paths,
        density=density,
        min_slope=min_slope,
        max_slope=max_slope,
        min_altitude=min_altitude,
        max_altitude=max_altitude,
        seed=seed,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_ObjectScatter.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "scatter_objects", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "scatter_objects",
            "script_path": abs_path,
            "prefab_paths": prefab_paths,
            "density": density,
            "seed": seed,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_setup_lighting(
    sun_color: list[float] | None,
    sun_intensity: float,
    ambient_color: list[float] | None,
    fog_enabled: bool,
    fog_color: list[float] | None,
    fog_density: float,
    skybox_material: str,
    time_of_day: str,
) -> str:
    """Setup scene lighting, fog, and post-processing (SCENE-03)."""
    script = generate_lighting_setup_script(
        sun_color=sun_color,
        sun_intensity=sun_intensity,
        ambient_color=ambient_color,
        fog_enabled=fog_enabled,
        fog_color=fog_color,
        fog_density=fog_density,
        skybox_material=skybox_material,
        time_of_day=time_of_day,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_LightingSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_lighting", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_lighting",
            "script_path": abs_path,
            "time_of_day": time_of_day,
            "fog_enabled": fog_enabled,
            "sun_intensity": sun_intensity,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_bake_navmesh(
    agent_radius: float,
    agent_height: float,
    max_slope: float,
    step_height: float,
    nav_links: list[dict] | None,
) -> str:
    """Bake NavMesh with agent settings (SCENE-04)."""
    script = generate_navmesh_bake_script(
        agent_radius=agent_radius,
        agent_height=agent_height,
        max_slope=max_slope,
        step_height=step_height,
        nav_links=nav_links,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_NavMeshBake.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "bake_navmesh", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "bake_navmesh",
            "script_path": abs_path,
            "agent_radius": agent_radius,
            "agent_height": agent_height,
            "max_slope": max_slope,
            "step_height": step_height,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_create_animator(
    name: str,
    states: list[dict] | None,
    transitions: list[dict] | None,
    parameters: list[dict] | None,
    blend_trees: list[dict] | None,
) -> str:
    """Create Animator Controller (SCENE-05)."""
    if not states:
        return json.dumps({
            "status": "error",
            "action": "create_animator",
            "message": "states is required for create_animator action (at least one state)",
        })

    script = generate_animator_controller_script(
        name=name,
        states=states,
        transitions=transitions or [],
        parameters=parameters or [],
        blend_trees=blend_trees,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/Scene/VeilBreakers_Animator_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_animator", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_animator",
            "name": name,
            "script_path": abs_path,
            "state_count": len(states),
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_configure_avatar(
    fbx_path: str,
    animation_type: str,
    bone_mapping: dict | None,
) -> str:
    """Configure avatar animation type (SCENE-06)."""
    if not fbx_path:
        return json.dumps({
            "status": "error",
            "action": "configure_avatar",
            "message": "fbx_path is required for configure_avatar action",
        })

    script = generate_avatar_config_script(
        fbx_path=fbx_path,
        animation_type=animation_type,
        bone_mapping=bone_mapping,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_AvatarConfig.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "configure_avatar", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "configure_avatar",
            "script_path": abs_path,
            "fbx_path": fbx_path,
            "animation_type": animation_type,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_setup_animation_rigging(
    name: str,
    constraints: list[dict] | None,
) -> str:
    """Setup Animation Rigging constraints (SCENE-07)."""
    if not constraints:
        return json.dumps({
            "status": "error",
            "action": "setup_animation_rigging",
            "message": "constraints is required for setup_animation_rigging action",
        })

    script = generate_animation_rigging_script(
        rig_name=name,
        constraints=constraints,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/Scene/VeilBreakers_Rigging_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_animation_rigging", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_animation_rigging",
            "name": name,
            "script_path": abs_path,
            "constraint_count": len(constraints),
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_create_blend_tree(
    blend_type: str, controller_name: str, states: list[dict] | None,
    parameters: list[dict] | None, motion_clips: dict[str, str] | None,
) -> str:
    """Create advanced blend tree (ANIM3-03)."""
    script = generate_blend_tree_script(
        blend_type=blend_type,
        controller_name=controller_name,
        states=states,
        parameters=parameters,
        motion_clips=motion_clips,
    )
    safe_name = controller_name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Animation/VeilBreakers_BlendTree_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_blend_tree", "message": str(exc)})
    return json.dumps({
        "status": "success",
        "action": "create_blend_tree",
        "blend_type": blend_type,
        "controller_name": controller_name,
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_scene_create_additive_layer(
    name: str, layer_name: str, base_layer_index: int,
    additive_clips: list[dict] | None, default_weight: float,
    avatar_mask_path: str,
) -> str:
    """Create additive animation layer (ANIM3-04)."""
    # Inject handler-level defaults into each clip dict so the template
    # picks them up (it reads "default_weight" and "avatar_mask" per layer).
    if additive_clips:
        for clip in additive_clips:
            if "default_weight" not in clip:
                clip["default_weight"] = default_weight
            if "avatar_mask" not in clip and avatar_mask_path:
                clip["avatar_mask"] = avatar_mask_path
    script = generate_additive_layer_script(
        controller_name=name,
        base_layer_name=layer_name,
        additive_layers=additive_clips,
        base_states=None,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Animation/VeilBreakers_AdditiveLayer_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_additive_layer", "message": str(exc)})
    return json.dumps({
        "status": "success",
        "action": "create_additive_layer",
        "controller_name": name,
        "layer_name": layer_name,
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)
