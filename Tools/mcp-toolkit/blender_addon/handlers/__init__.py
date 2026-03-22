from typing import Any, Callable

from .scene import (
    handle_get_scene_info,
    handle_clear_scene,
    handle_configure_scene,
    handle_list_objects,
)
from .objects import (
    handle_create_object,
    handle_modify_object,
    handle_delete_object,
    handle_duplicate_object,
)
from .viewport import (
    handle_get_viewport_screenshot,
    handle_render_contact_sheet,
    handle_set_shading,
    handle_navigate_camera,
    handle_setup_beauty_scene,
    handle_setup_dark_fantasy_lighting,
    handle_setup_ground_plane,
    handle_auto_frame_camera,
    handle_run_quality_checks,
)
from .materials import (
    handle_material_create,
    handle_material_assign,
    handle_material_modify,
    handle_material_list,
)
from .export import (
    handle_export_fbx,
    handle_export_gltf,
)
from .execute import handle_execute_code
from .mesh import (
    handle_analyze_topology,
    handle_auto_repair,
    handle_check_game_ready,
    handle_select_geometry,
    handle_edit_mesh,
    handle_boolean_op,
    handle_retopologize,
    handle_sculpt,
)
from .uv import (  # noqa: F401, E402
    handle_analyze_uv,
    handle_unwrap_xatlas,
    handle_unwrap_blender,
    handle_pack_islands,
    handle_generate_lightmap_uv,
    handle_equalize_density,
    handle_export_uv_layout,
    handle_set_active_uv_layer,
    handle_ensure_xatlas,
)
from .texture import (
    handle_create_pbr_material,
    handle_bake_textures,
    handle_validate_texture,
    handle_generate_wear_map,
    handle_get_uv_region,
    handle_get_seam_pixels,
    handle_bake_procedural_to_images,
    handle_bake_id_map,
    handle_bake_thickness_map,
    handle_channel_pack,
    handle_ensure_flat_albedo,
)
from .pipeline_lod import handle_generate_lods
from .lod_pipeline import handle_generate_lods as handle_generate_lod_chain
from .rigging import (
    handle_analyze_for_rigging,
    handle_apply_rig_template,
    handle_build_custom_rig,
)
from .rigging_weights import (
    handle_auto_weight,
    handle_test_deformation,
    handle_validate_rig,
    handle_fix_weights,
)
from .rigging_advanced import (
    handle_setup_facial,
    handle_setup_ik,
    handle_setup_spring_bones,
    handle_setup_ragdoll,
    handle_retarget_rig,
    handle_add_shape_keys,
)
from .animation import (
    handle_generate_walk,
    handle_generate_fly,
    handle_generate_idle,
    handle_generate_attack,
    handle_generate_reaction,
    handle_generate_custom,
)
from .animation_export import (
    handle_preview_animation,
    handle_add_secondary_motion,
    handle_extract_root_motion,
    handle_retarget_mixamo,
    handle_generate_ai_motion,
    handle_batch_export,
)
from .environment import (
    handle_generate_terrain,
    handle_paint_terrain,
    handle_carve_river,
    handle_generate_road,
    handle_create_water,
    handle_export_heightmap,
)
from .worldbuilding import (
    handle_generate_building,
    handle_generate_castle,
    handle_generate_ruins,
    handle_generate_interior,
    handle_generate_modular_kit,
    handle_generate_location,
    handle_generate_boss_arena,
    handle_generate_world_graph,
    handle_generate_linked_interior,
    handle_generate_multi_floor_dungeon,
    handle_generate_overrun_variant,
    handle_generate_easter_egg,
    handle_add_storytelling_props,
)
from .worldbuilding_layout import (
    handle_generate_dungeon,
    handle_generate_cave,
    handle_generate_town,
)
from .environment_scatter import (
    handle_scatter_vegetation,
    handle_scatter_props,
    handle_create_breakable,
)
from .equipment import (
    handle_equipment_generate_weapon,
    handle_equipment_split_character,
    handle_equipment_fit_armor,
    handle_equipment_render_icon,
)
from .procedural_materials import (
    handle_create_procedural_material,
)
from .vertex_colors import (
    handle_auto_paint_vertex_colors,
)
from .weathering import (
    handle_apply_weathering,
)
from .terrain_materials import (
    handle_setup_terrain_biome,
    handle_create_biome_terrain,
)
from .vegetation_system import (
    handle_scatter_biome_vegetation,
)
from .road_network import (  # noqa: F401 -- road network generation
    compute_road_network,
    compute_mst_edges,
    ROAD_TYPES,
)
from .coastline import (  # noqa: F401 -- coastline terrain generation
    generate_coastline,
    COASTLINE_STYLES,
)
from .terrain_features import (  # noqa: F401 -- terrain feature generators
    generate_canyon,
    generate_waterfall,
    generate_cliff_face,
    generate_swamp_terrain,
)
from .material_tiers import (  # noqa: F401 -- material tier system (EQ-040)
    METAL_TIERS,
    WOOD_TIERS,
    LEATHER_TIERS,
    CLOTH_TIERS,
    get_material_tier,
    get_tier_names,
    apply_material_tier_to_equipment,
)
from .armor_meshes import ARMOR_GENERATORS  # noqa: F401 -- 22-style armor system
from .npc_characters import (  # noqa: F401 -- NPC body mesh generation
    generate_npc_body_mesh,
    NPC_GENERATORS,
)
from .monster_bodies import (  # noqa: F401 -- Monster body type system
    generate_monster_body,
    ALL_BODY_TYPES,
    ALL_BRANDS,
    BRAND_FEATURES,
)
from .rarity_system import (  # noqa: F401 -- Rarity visual differentiation
    RARITY_TIERS,
    VALID_RARITIES,
    RARITY_ORDER,
    BRAND_EMISSION_COLORS,
    apply_rarity_to_mesh,
    compute_gem_socket_positions,
    get_rarity_material_tier,
    get_rarity_tier,
    validate_rarity,
)
from .legendary_weapons import (  # noqa: F401 -- Legendary unique weapons
    LEGENDARY_WEAPONS,
    LEGENDARY_GENERATORS,
    generate_legendary_weapon_mesh,
)
from .world_map import (  # noqa: F401 -- World map generator + landmarks + storytelling
    generate_world_map,
    place_landmarks,
    generate_storytelling_scene,
    world_map_to_dict,
    BIOME_TYPES,
    POI_TYPES,
    LANDMARK_TYPES,
    STORYTELLING_PATTERNS,
)
from .light_integration import (  # noqa: F401 -- Light source integration
    compute_light_placements,
    merge_nearby_lights,
    compute_light_budget,
    LIGHT_PROP_MAP,
    FLICKER_PRESETS,
)
from .atmospheric_volumes import (  # noqa: F401 -- Atmospheric volume props
    compute_atmospheric_placements,
    compute_volume_mesh_spec,
    estimate_atmosphere_performance,
    ATMOSPHERIC_VOLUMES,
    BIOME_ATMOSPHERE_RULES,
)

COMMAND_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "ping": lambda params: {"status": "success", "result": "pong"},
    # Scene
    "get_scene_info": handle_get_scene_info,
    "clear_scene": handle_clear_scene,
    "configure_scene": handle_configure_scene,
    "list_objects": handle_list_objects,
    # Objects
    "create_object": handle_create_object,
    "modify_object": handle_modify_object,
    "delete_object": handle_delete_object,
    "duplicate_object": handle_duplicate_object,
    # Viewport
    "get_viewport_screenshot": handle_get_viewport_screenshot,
    "render_contact_sheet": handle_render_contact_sheet,
    "set_shading": handle_set_shading,
    "navigate_camera": handle_navigate_camera,
    # Beauty setup
    "setup_beauty_scene": handle_setup_beauty_scene,
    "setup_dark_fantasy_lighting": handle_setup_dark_fantasy_lighting,
    "setup_ground_plane": handle_setup_ground_plane,
    "auto_frame_camera": handle_auto_frame_camera,
    "run_quality_checks": handle_run_quality_checks,
    # Materials
    "material_create": handle_material_create,
    "material_assign": handle_material_assign,
    "material_modify": handle_material_modify,
    "material_list": handle_material_list,
    # Export
    "export_fbx": handle_export_fbx,
    "export_gltf": handle_export_gltf,
    # Code execution
    "execute_code": handle_execute_code,
    # Mesh analysis and repair
    "mesh_analyze_topology": handle_analyze_topology,
    "mesh_auto_repair": handle_auto_repair,
    "mesh_check_game_ready": handle_check_game_ready,
    # Mesh editing (selection, edit, boolean, retopo, sculpt)
    "mesh_select": handle_select_geometry,
    "mesh_edit": handle_edit_mesh,
    "mesh_boolean": handle_boolean_op,
    "mesh_retopologize": handle_retopologize,
    "mesh_sculpt": handle_sculpt,
    # UV operations
    "uv_analyze": handle_analyze_uv,
    "uv_unwrap_xatlas": handle_unwrap_xatlas,
    "uv_unwrap_blender": handle_unwrap_blender,
    "uv_pack_islands": handle_pack_islands,
    "uv_generate_lightmap": handle_generate_lightmap_uv,
    "uv_equalize_density": handle_equalize_density,
    "uv_export_layout": handle_export_uv_layout,
    "uv_set_active_layer": handle_set_active_uv_layer,
    "uv_ensure_xatlas": handle_ensure_xatlas,
    # Texture operations
    "texture_create_pbr": handle_create_pbr_material,
    "texture_bake": handle_bake_textures,
    "texture_validate": handle_validate_texture,
    "texture_generate_wear": handle_generate_wear_map,
    "texture_get_uv_region": handle_get_uv_region,
    "texture_get_seam_pixels": handle_get_seam_pixels,
    "texture_bake_procedural": handle_bake_procedural_to_images,
    "texture_bake_id_map": handle_bake_id_map,
    "texture_bake_thickness": handle_bake_thickness_map,
    "texture_channel_pack": handle_channel_pack,
    "texture_ensure_flat_albedo": handle_ensure_flat_albedo,
    # Pipeline operations
    "pipeline_generate_lods": handle_generate_lods,
    "pipeline_generate_lod_chain": handle_generate_lod_chain,
    # Rigging operations
    "rig_analyze": handle_analyze_for_rigging,
    "rig_apply_template": handle_apply_rig_template,
    "rig_build_custom": handle_build_custom_rig,
    # Rig weight/validation operations
    "rig_auto_weight": handle_auto_weight,
    "rig_test_deformation": handle_test_deformation,
    "rig_validate": handle_validate_rig,
    "rig_fix_weights": handle_fix_weights,
    # Advanced rigging operations
    "rig_setup_facial": handle_setup_facial,
    "rig_setup_ik": handle_setup_ik,
    "rig_setup_spring_bones": handle_setup_spring_bones,
    "rig_setup_ragdoll": handle_setup_ragdoll,
    "rig_retarget": handle_retarget_rig,
    "rig_add_shape_keys": handle_add_shape_keys,
    # Animation operations
    "anim_generate_walk": handle_generate_walk,
    "anim_generate_fly": handle_generate_fly,
    "anim_generate_idle": handle_generate_idle,
    "anim_generate_attack": handle_generate_attack,
    "anim_generate_reaction": handle_generate_reaction,
    "anim_generate_custom": handle_generate_custom,
    # Animation export/integration operations
    "anim_preview": handle_preview_animation,
    "anim_add_secondary_motion": handle_add_secondary_motion,
    "anim_extract_root_motion": handle_extract_root_motion,
    "anim_retarget_mixamo": handle_retarget_mixamo,
    "anim_generate_ai_motion": handle_generate_ai_motion,
    "anim_batch_export": handle_batch_export,
    # Environment operations
    "env_generate_terrain": handle_generate_terrain,
    "env_paint_terrain": handle_paint_terrain,
    "env_carve_river": handle_carve_river,
    "env_generate_road": handle_generate_road,
    "env_create_water": handle_create_water,
    "env_export_heightmap": handle_export_heightmap,
    # Environment scatter operations
    "env_scatter_vegetation": handle_scatter_vegetation,
    "env_scatter_props": handle_scatter_props,
    "env_create_breakable": handle_create_breakable,
    # Worldbuilding operations
    "world_generate_building": handle_generate_building,
    "world_generate_castle": handle_generate_castle,
    "world_generate_ruins": handle_generate_ruins,
    "world_generate_interior": handle_generate_interior,
    "world_generate_modular_kit": handle_generate_modular_kit,
    # Worldbuilding layout operations (dungeon/cave/town)
    "world_generate_dungeon": handle_generate_dungeon,
    "world_generate_cave": handle_generate_cave,
    "world_generate_town": handle_generate_town,
    # Worldbuilding v2 operations (Phase 14 -- world design)
    "world_generate_location": handle_generate_location,
    "world_generate_boss_arena": handle_generate_boss_arena,
    "world_generate_world_graph": handle_generate_world_graph,
    "world_generate_linked_interior": handle_generate_linked_interior,
    "world_generate_multi_floor_dungeon": handle_generate_multi_floor_dungeon,
    "world_generate_overrun_variant": handle_generate_overrun_variant,
    "world_generate_easter_egg": handle_generate_easter_egg,
    # Environment v2 operations (Phase 14 -- AAA-05 storytelling props)
    "env_add_storytelling_props": handle_add_storytelling_props,
    # Equipment operations
    "equipment_generate_weapon": handle_equipment_generate_weapon,
    "equipment_split_character": handle_equipment_split_character,
    "equipment_fit_armor": handle_equipment_fit_armor,
    "equipment_render_icon": handle_equipment_render_icon,
    # Procedural material operations
    "material_create_procedural": handle_create_procedural_material,
    # Vertex color operations
    "vertex_colors_auto_paint": handle_auto_paint_vertex_colors,
    # Weathering operations
    "weathering_apply": handle_apply_weathering,
    # Terrain biome material operations
    "terrain_setup_biome": handle_setup_terrain_biome,
    "terrain_create_biome_material": handle_create_biome_terrain,
    # Per-biome vegetation quality system
    "env_scatter_biome_vegetation": handle_scatter_biome_vegetation,
    # Road network generation (pure logic -- returns mesh specs)
    "env_compute_road_network": lambda params: compute_road_network(
        waypoints=[tuple(wp) for wp in params.get("waypoints", [])],
        terrain_heightmap=params.get("terrain_heightmap"),
        water_level=params.get("water_level", 0.0),
        seed=params.get("seed", 42),
    ),
    # Coastline generation (pure logic -- returns mesh specs)
    "env_generate_coastline": lambda params: generate_coastline(
        length=params.get("length", 200.0),
        width=params.get("width", 50.0),
        style=params.get("style", "rocky"),
        resolution=params.get("resolution", 64),
        seed=params.get("seed", 42),
    ),
    # Terrain features (pure logic -- return mesh specs)
    "env_generate_canyon": lambda params: generate_canyon(
        width=params.get("width", 5.0),
        length=params.get("length", 50.0),
        depth=params.get("depth", 15.0),
        wall_roughness=params.get("wall_roughness", 0.5),
        num_side_caves=params.get("num_side_caves", 3),
        seed=params.get("seed", 42),
    ),
    "env_generate_waterfall": lambda params: generate_waterfall(
        height=params.get("height", 10.0),
        width=params.get("width", 3.0),
        pool_radius=params.get("pool_radius", 4.0),
        num_steps=params.get("num_steps", 3),
        has_cave_behind=params.get("has_cave_behind", True),
        seed=params.get("seed", 42),
    ),
    "env_generate_cliff_face": lambda params: generate_cliff_face(
        width=params.get("width", 20.0),
        height=params.get("height", 15.0),
        overhang=params.get("overhang", 3.0),
        num_cave_entrances=params.get("num_cave_entrances", 2),
        has_ledge_path=params.get("has_ledge_path", True),
        seed=params.get("seed", 42),
    ),
    "env_generate_swamp_terrain": lambda params: generate_swamp_terrain(
        size=params.get("size", 50.0),
        water_level=params.get("water_level", 0.3),
        hummock_count=params.get("hummock_count", 12),
        island_count=params.get("island_count", 4),
        seed=params.get("seed", 42),
    ),
    # World map generation (pure logic -- returns world map spec)
    "world_generate_world_map": lambda params: world_map_to_dict(
        generate_world_map(
            num_regions=params.get("num_regions", 6),
            map_size=params.get("map_size", 2000.0),
            seed=params.get("seed", 42),
            min_pois=params.get("min_pois", 300),
        )
    ),
    # Light integration (pure logic -- returns light placements)
    "env_compute_light_placements": lambda params: compute_light_placements(
        prop_positions=params.get("prop_positions", []),
    ),
    "env_merge_lights": lambda params: merge_nearby_lights(
        lights=params.get("lights", []),
        merge_distance=params.get("merge_distance", 2.0),
    ),
    "env_light_budget": lambda params: compute_light_budget(
        lights=params.get("lights", []),
    ),
    # Atmospheric volumes (pure logic -- returns volume placements)
    "env_compute_atmospheric_placements": lambda params: compute_atmospheric_placements(
        biome_name=params.get("biome_name", "dark_forest"),
        area_bounds=tuple(params.get("area_bounds", (0, 0, 100, 100))),
        seed=params.get("seed", 42),
        density_scale=params.get("density_scale", 1.0),
    ),
    "env_volume_mesh_spec": lambda params: compute_volume_mesh_spec(
        volume_type=params.get("volume_type", "ground_fog"),
        position=tuple(params.get("position", (0, 0, 0))),
        scale=params.get("scale", 1.0),
    ),
    "env_atmosphere_performance": lambda params: estimate_atmosphere_performance(
        placements=params.get("placements", []),
    ),
}
