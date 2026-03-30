"""unity_world tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, _handle_dict_template, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.world_templates import (
    generate_scene_creation_script,
    generate_scene_transition_script,
    generate_probe_setup_script,
    generate_occlusion_setup_script,
    generate_environment_setup_script,
    generate_terrain_detail_script,
    generate_tilemap_setup_script,
    generate_2d_physics_script,
    generate_time_of_day_preset_script,
    generate_fast_travel_script,
    generate_puzzle_mechanics_script,
    generate_trap_system_script,
    generate_spatial_loot_script,
    generate_weather_system_script,
    generate_day_night_cycle_script,
    generate_npc_placement_script,
    generate_dungeon_lighting_script,
    generate_terrain_building_blend_script,
    generate_wfc_dungeon_script,
    generate_interior_streaming_script,
    generate_door_system_script,
)




# ===========================================================================
# Compound tool: unity_world (Scene & World Systems -- Phase 14)
# ===========================================================================


@mcp.tool()
async def unity_world(
    action: Literal[
        "create_scene",               # SCNE-01
        "create_transition_system",    # SCNE-02
        "setup_probes",               # SCNE-03
        "setup_occlusion",            # SCNE-04
        "setup_environment",          # SCNE-05
        "paint_terrain_detail",       # SCNE-06
        "create_tilemap",             # TWO-01
        "setup_2d_physics",           # TWO-02
        "apply_time_of_day",          # WORLD-08
        "create_fast_travel",         # RPG-02
        "create_puzzle",              # RPG-04
        "create_trap",                # RPG-06
        "create_spatial_loot",        # RPG-07
        "create_weather",             # RPG-09
        "create_day_night",           # RPG-10
        "create_npc_placement",       # RPG-11
        "create_dungeon_lighting",    # RPG-12
        "create_terrain_blend",       # RPG-13
        "create_wfc_dungeon",         # WORLD-11: WFC tile-based dungeon generation
        "create_interior_streaming",  # WORLD-12: seamless interior/exterior streaming
        "create_door_system",         # WORLD-13: door/gate/lock and lever system
    ],
    name: str = "default",
    # scene params
    scene_name: str = "",
    scene_setup: str = "DefaultGameObjects",
    loading_mode: str = "single",
    build_index: int = -1,
    # transition params
    fade_duration: float = 0.5,
    show_loading_screen: bool = True,
    # probe params
    reflection_probe_count: int = 4,
    reflection_resolution: int = 256,
    probe_box_size: list[float] | None = None,
    light_probe_grid_spacing: float = 2.0,
    light_probe_grid_size: list[int] | None = None,
    # occlusion params
    smallest_occluder: float = 5.0,
    smallest_hole: float = 0.25,
    backface_threshold: float = 100.0,
    # environment params
    skybox_shader: str = "Skybox/Procedural",
    ambient_mode: str = "Skybox",
    default_reflection_mode: str = "Skybox",
    enable_gi: bool = True,
    # terrain detail params
    detail_prototypes: list[dict] | None = None,
    paint_density: int = 8,
    # tilemap params
    grid_cell_size: list[float] | None = None,
    tile_entries: list[dict] | None = None,
    rule_tile_name: str = "",
    rule_tile_rules: list[dict] | None = None,
    # 2d physics params
    gravity: list[float] | None = None,
    collider_type: str = "box",
    body_type: str = "Dynamic",
    joint_type: str = "",
    joint_params: dict | None = None,
    # time of day params
    preset_name: str = "noon",
    custom_overrides: dict | None = None,
    apply_fog: bool = True,
    # fast travel params
    waypoint_prefab_path: str = "",
    teleport_fade_duration: float = 0.5,
    save_key: str = "discoveredWaypoints",
    # puzzle params
    puzzle_types: list[str] | None = None,
    # trap params
    trap_types: list[str] | None = None,
    base_damage: float = 25.0,
    cooldown: float = 3.0,
    # spatial loot params
    chest_prefab_path: str = "",
    loot_table_so_path: str = "",
    room_loot_density: float = 0.3,
    # weather params
    weather_states: list[str] | None = None,
    transition_duration: float = 3.0,
    default_state: str = "Clear",
    # day/night params
    day_duration_minutes: float = 10.0,
    start_hour: float = 8.0,
    time_presets: list[str] | None = None,
    # npc placement params
    npc_roles: list[str] | None = None,
    # dungeon lighting params
    torch_spacing: float = 5.0,
    torch_light_range: float = 8.0,
    torch_color: list[float] | None = None,
    fog_density: float = 0.03,
    fog_color: list[float] | None = None,
    # terrain blend params
    blend_radius: float = 2.0,
    decal_material_path: str = "",
    depression_depth: float = 0.1,
    vertex_color_falloff: float = 1.5,
    # WFC dungeon params (WORLD-11)
    wfc_grid_width: int = 20,
    wfc_grid_height: int = 20,
    wfc_seed: int = -1,
    tile_set_path: str = "Assets/Prefabs/DungeonTiles",
    # Interior streaming params (WORLD-12)
    max_loaded_cells: int = 3,
    preload_distance: float = 15.0,
    lighting_transition_time: float = 1.5,
    audio_crossfade_time: float = 2.0,
    # Door system params (WORLD-13)
    default_open_speed: float = 2.0,
    default_auto_close_delay: float = 5.0,
    # common
    namespace: str = ""
) -> str:
    """Scene and world systems -- scene creation, transitions, probes, occlusion, environment, terrain detail, tilemaps, 2D physics, time-of-day, fast travel, puzzles, traps, spatial loot, weather, day/night cycle, NPC placement, dungeon lighting, terrain-building blending."""
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_scene":
            return await _handle_world_create_scene(
                scene_name or name, scene_setup, loading_mode, build_index, ns_kwargs,
            )
        elif action == "create_transition_system":
            return await _handle_world_transition(
                name, fade_duration, show_loading_screen, ns_kwargs,
            )
        elif action == "setup_probes":
            return await _handle_world_probes(
                name, reflection_probe_count, reflection_resolution,
                probe_box_size, light_probe_grid_spacing, light_probe_grid_size,
                ns_kwargs,
            )
        elif action == "setup_occlusion":
            return await _handle_world_occlusion(
                name, smallest_occluder, smallest_hole, backface_threshold, ns_kwargs,
            )
        elif action == "setup_environment":
            return await _handle_world_environment(
                name, skybox_shader, ambient_mode, default_reflection_mode,
                enable_gi, ns_kwargs,
            )
        elif action == "paint_terrain_detail":
            return await _handle_world_terrain_detail(
                name, detail_prototypes, paint_density, ns_kwargs,
            )
        elif action == "create_tilemap":
            return await _handle_world_tilemap(
                name, grid_cell_size, tile_entries, rule_tile_name,
                rule_tile_rules, ns_kwargs,
            )
        elif action == "setup_2d_physics":
            return await _handle_world_2d_physics(
                name, gravity, collider_type, body_type, joint_type,
                joint_params, ns_kwargs,
            )
        elif action == "apply_time_of_day":
            return await _handle_world_time_of_day(
                name, preset_name, custom_overrides, apply_fog, ns_kwargs,
            )
        elif action == "create_fast_travel":
            return await _handle_world_fast_travel(
                name, waypoint_prefab_path, teleport_fade_duration, save_key,
                ns_kwargs,
            )
        elif action == "create_puzzle":
            return await _handle_world_puzzle(name, puzzle_types, ns_kwargs)
        elif action == "create_trap":
            return await _handle_world_trap(
                name, trap_types, base_damage, cooldown, ns_kwargs,
            )
        elif action == "create_spatial_loot":
            return await _handle_world_spatial_loot(
                name, chest_prefab_path, loot_table_so_path,
                room_loot_density, ns_kwargs,
            )
        elif action == "create_weather":
            return await _handle_world_weather(
                name, weather_states, transition_duration, default_state,
                ns_kwargs,
            )
        elif action == "create_day_night":
            return await _handle_world_day_night(
                name, day_duration_minutes, start_hour, time_presets, ns_kwargs,
            )
        elif action == "create_npc_placement":
            return await _handle_world_npc_placement(name, npc_roles, ns_kwargs)
        elif action == "create_dungeon_lighting":
            return await _handle_world_dungeon_lighting(
                name, torch_spacing, torch_light_range, torch_color,
                fog_density, fog_color, ns_kwargs,
            )
        elif action == "create_terrain_blend":
            return await _handle_world_terrain_blend(
                name, blend_radius, decal_material_path, depression_depth,
                vertex_color_falloff, ns_kwargs,
            )
        elif action == "create_wfc_dungeon":
            return await _handle_world_wfc_dungeon(
                name, wfc_grid_width, wfc_grid_height, wfc_seed,
                tile_set_path, namespace,
            )
        elif action == "create_interior_streaming":
            return await _handle_world_interior_streaming(
                name, max_loaded_cells, preload_distance,
                lighting_transition_time, audio_crossfade_time, namespace,
            )
        elif action == "create_door_system":
            return await _handle_world_door_system(
                name, default_open_speed, default_auto_close_delay, namespace,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_world action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# World action handlers
# ---------------------------------------------------------------------------


async def _handle_world_create_scene(
    scene_name: str, scene_setup: str, loading_mode: str,
    build_index: int, ns_kwargs: dict,
) -> str:
    """Create new scene (SCNE-01)."""
    script = generate_scene_creation_script(
        scene_name=scene_name,
        scene_setup=scene_setup,
        loading_mode=loading_mode,
        build_index=build_index,
        **ns_kwargs,
    )
    safe_name = scene_name.replace(" ", "_")
    rel_path = f"Assets/Editor/Generated/World/{safe_name}_SceneCreator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_scene",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_transition(
    name: str, fade_duration: float, show_loading_screen: bool, ns_kwargs: dict,
) -> str:
    """Create scene transition system (SCNE-02)."""
    editor_cs, runtime_cs = generate_scene_transition_script(
        fade_duration=fade_duration,
        show_loading_screen=show_loading_screen,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_TransitionSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_SceneTransition.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_transition_system",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_probes(
    name: str, reflection_probe_count: int, reflection_resolution: int,
    probe_box_size: list[float] | None, light_probe_grid_spacing: float,
    light_probe_grid_size: list[int] | None, ns_kwargs: dict,
) -> str:
    """Setup reflection + light probes (SCNE-03)."""
    script = generate_probe_setup_script(
        reflection_probe_count=reflection_probe_count,
        reflection_resolution=reflection_resolution,
        probe_box_size=probe_box_size,
        light_probe_grid_spacing=light_probe_grid_spacing,
        light_probe_grid_size=light_probe_grid_size,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_ProbeSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_probes",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_occlusion(
    name: str, smallest_occluder: float, smallest_hole: float,
    backface_threshold: float, ns_kwargs: dict,
) -> str:
    """Setup occlusion culling (SCNE-04)."""
    script = generate_occlusion_setup_script(
        smallest_occluder=smallest_occluder,
        smallest_hole=smallest_hole,
        backface_threshold=backface_threshold,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_OcclusionSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_occlusion",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_environment(
    name: str, skybox_shader: str, ambient_mode: str,
    default_reflection_mode: str, enable_gi: bool, ns_kwargs: dict,
) -> str:
    """Setup environment (skybox, ambient, GI) (SCNE-05)."""
    script = generate_environment_setup_script(
        skybox_shader=skybox_shader,
        ambient_mode=ambient_mode,
        default_reflection_mode=default_reflection_mode,
        enable_gi=enable_gi,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_EnvironmentSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_environment",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_terrain_detail(
    name: str, detail_prototypes: list[dict] | None, paint_density: int,
    ns_kwargs: dict,
) -> str:
    """Paint terrain detail prototypes (SCNE-06)."""
    script = generate_terrain_detail_script(
        detail_prototypes=detail_prototypes,
        paint_density=paint_density,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_TerrainDetail.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "paint_terrain_detail",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_tilemap(
    name: str, grid_cell_size: list[float] | None, tile_entries: list[dict] | None,
    rule_tile_name: str, rule_tile_rules: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Create tilemap setup (TWO-01)."""
    script = generate_tilemap_setup_script(
        grid_cell_size=grid_cell_size,
        tile_entries=tile_entries,
        rule_tile_name=rule_tile_name,
        rule_tile_rules=rule_tile_rules,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_TilemapSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_tilemap",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_2d_physics(
    name: str, gravity: list[float] | None, collider_type: str,
    body_type: str, joint_type: str, joint_params: dict | None,
    ns_kwargs: dict,
) -> str:
    """Setup 2D physics (TWO-02)."""
    script = generate_2d_physics_script(
        gravity=gravity,
        collider_type=collider_type,
        body_type=body_type,
        joint_type=joint_type,
        joint_params=joint_params,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_2DPhysicsSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_2d_physics",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_time_of_day(
    name: str, preset_name: str, custom_overrides: dict | None,
    apply_fog: bool, ns_kwargs: dict,
) -> str:
    """Apply time-of-day lighting preset (WORLD-08)."""
    script = generate_time_of_day_preset_script(
        preset_name=preset_name,
        custom_overrides=custom_overrides,
        apply_fog=apply_fog,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_TimeOfDay.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "apply_time_of_day",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_fast_travel(
    name: str, waypoint_prefab_path: str, teleport_fade_duration: float,
    save_key: str, ns_kwargs: dict,
) -> str:
    """Create fast travel system (RPG-02)."""
    editor_cs, runtime_cs = generate_fast_travel_script(
        waypoint_prefab_path=waypoint_prefab_path or "Prefabs/Waypoint",
        teleport_fade_duration=teleport_fade_duration,
        save_key=save_key,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_FastTravelSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_FastTravel.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_fast_travel",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_puzzle(
    name: str, puzzle_types: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create puzzle mechanics system (RPG-04)."""
    editor_cs, runtime_cs = generate_puzzle_mechanics_script(
        puzzle_types=puzzle_types,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_PuzzleSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_PuzzleMechanics.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_puzzle",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_trap(
    name: str, trap_types: list[str] | None, base_damage: float,
    cooldown: float, ns_kwargs: dict,
) -> str:
    """Create trap system (RPG-06)."""
    editor_cs, runtime_cs = generate_trap_system_script(
        trap_types=trap_types,
        base_damage=base_damage,
        cooldown=cooldown,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_TrapSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_TrapSystem.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_trap",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_spatial_loot(
    name: str, chest_prefab_path: str, loot_table_so_path: str,
    room_loot_density: float, ns_kwargs: dict,
) -> str:
    """Create spatial loot system (RPG-07)."""
    editor_cs, runtime_cs = generate_spatial_loot_script(
        chest_prefab_path=chest_prefab_path or "Prefabs/TreasureChest",
        loot_table_so_path=loot_table_so_path or "Data/LootTables",
        room_loot_density=room_loot_density,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_LootSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_SpatialLoot.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_spatial_loot",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_weather(
    name: str, weather_states: list[str] | None, transition_duration: float,
    default_state: str, ns_kwargs: dict,
) -> str:
    """Create weather system (RPG-09)."""
    editor_cs, runtime_cs = generate_weather_system_script(
        weather_states=weather_states,
        transition_duration=transition_duration,
        default_state=default_state,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_WeatherSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_WeatherSystem.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_weather",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_day_night(
    name: str, day_duration_minutes: float, start_hour: float,
    time_presets: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create day/night cycle system (RPG-10)."""
    editor_cs, runtime_cs = generate_day_night_cycle_script(
        day_duration_minutes=day_duration_minutes,
        start_hour=start_hour,
        time_presets=time_presets,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_DayNightSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_DayNightCycle.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_day_night",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_npc_placement(
    name: str, npc_roles: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create NPC placement system (RPG-11)."""
    so_cs, runtime_cs, editor_cs = generate_npc_placement_script(
        npc_roles=npc_roles,
        **ns_kwargs,
    )
    paths = []
    paths.append(_write_to_unity(
        so_cs, f"Assets/ScriptableObjects/World/{name}_NPCPlacementData.cs",
    ))
    paths.append(_write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_NPCPlacement.cs",
    ))
    paths.append(_write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_NPCPlacementSetup.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_npc_placement",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_dungeon_lighting(
    name: str, torch_spacing: float, torch_light_range: float,
    torch_color: list[float] | None, fog_density: float,
    fog_color: list[float] | None, ns_kwargs: dict,
) -> str:
    """Create dungeon lighting system (RPG-12)."""
    editor_cs, runtime_cs = generate_dungeon_lighting_script(
        torch_spacing=torch_spacing,
        torch_light_range=torch_light_range,
        torch_color=torch_color,
        fog_density=fog_density,
        fog_color=fog_color,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_DungeonLightingSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_DungeonLighting.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_dungeon_lighting",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_terrain_blend(
    name: str, blend_radius: float, decal_material_path: str,
    depression_depth: float, vertex_color_falloff: float, ns_kwargs: dict,
) -> str:
    """Create terrain-building blending system (RPG-13)."""
    editor_cs, runtime_cs = generate_terrain_building_blend_script(
        blend_radius=blend_radius,
        decal_material_path=decal_material_path or "Materials/TerrainBlendDecal",
        depression_depth=depression_depth,
        vertex_color_falloff=vertex_color_falloff,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_TerrainBlendSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_TerrainBlend.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_terrain_blend",
        "paths": [editor_path, runtime_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_wfc_dungeon(
    name: str, grid_width: int, grid_height: int, seed: int,
    tile_set_path: str, namespace: str,
) -> str:
    """Create WFC tile-based dungeon generation script (WORLD-11)."""
    ns = namespace or "VeilBreakers.WorldSystems"
    result = generate_wfc_dungeon_script(
        grid_width=grid_width, grid_height=grid_height, seed=seed,
        tile_set_path=tile_set_path, namespace=ns,
    )
    return await _handle_dict_template("create_wfc_dungeon", result)


async def _handle_world_interior_streaming(
    name: str, max_loaded_cells: int, preload_distance: float,
    lighting_transition_time: float, audio_crossfade_time: float,
    namespace: str,
) -> str:
    """Create seamless interior/exterior streaming scripts (WORLD-12)."""
    ns = namespace or "VeilBreakers.WorldSystems"
    manager_cs, trigger_cs = generate_interior_streaming_script(
        max_loaded_cells=max_loaded_cells,
        preload_distance=preload_distance,
        lighting_transition_time=lighting_transition_time,
        audio_crossfade_time=audio_crossfade_time,
        namespace=ns,
    )
    safe_name = name.replace(" ", "_")
    manager_path = _write_to_unity(
        manager_cs, f"Assets/Scripts/Runtime/WorldSystems/{safe_name}_InteriorStreamingManager.cs",
    )
    trigger_path = _write_to_unity(
        trigger_cs, f"Assets/Scripts/Runtime/WorldSystems/{safe_name}_InteriorStreamingTrigger.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_interior_streaming",
        "paths": [manager_path, trigger_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_world_door_system(
    name: str, default_open_speed: float, default_auto_close_delay: float,
    namespace: str,
) -> str:
    """Create door/gate/lock and lever system (WORLD-13)."""
    ns = namespace or "VeilBreakers.WorldSystems"
    door_cs, lever_cs = generate_door_system_script(
        default_open_speed=default_open_speed,
        default_auto_close_delay=default_auto_close_delay,
        namespace=ns,
    )
    safe_name = name.replace(" ", "_")
    door_path = _write_to_unity(
        door_cs, f"Assets/Scripts/Runtime/WorldSystems/{safe_name}_Door.cs",
    )
    lever_path = _write_to_unity(
        lever_cs, f"Assets/Scripts/Runtime/WorldSystems/{safe_name}_Lever.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_door_system",
        "paths": [door_path, lever_path],
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)
