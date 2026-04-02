from typing import Any, Callable

from ._mesh_bridge import mesh_from_spec

from .scene import (
    handle_get_scene_info,
    handle_clear_scene,
    handle_configure_scene,
    handle_list_objects,
    handle_setup_world,
    handle_add_light,
    handle_add_camera,
    handle_configure_render,
    handle_create_collection,
    handle_move_to_collection,
    handle_set_visibility,
    handle_organize_by_type,
    handle_toggle_collection_visibility,
    handle_list_collections,
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
    handle_loop_cut,
    handle_bevel_edges,
    handle_knife_project,
    handle_enter_sculpt_mode,
    handle_exit_sculpt_mode,
    handle_vertex_color,
    handle_custom_normals,
    handle_edge_data,
    handle_shape_key,
    # Advanced sculpt handlers (MESH-04b..f)
    handle_sculpt_brush,
    handle_dyntopo,
    handle_voxel_remesh,
    handle_face_sets,
    handle_multires,
    # Pure-logic position selection helpers (GAP-01)
    _select_by_box,
    _select_by_sphere,
    _select_by_plane,
)
from .mesh_enhance import (
    handle_enhance_geometry,
    handle_bake_detail_normals,
    handle_bake_ao_map,
    handle_bake_curvature_map,
    handle_validate_enhancement,
)
from .text_objects import (
    handle_create_text,
    handle_text_to_mesh,
)
from .drivers import (
    handle_add_driver,
    handle_remove_driver,
)
from .curves import (
    handle_create_curve,
    handle_curve_to_mesh,
    handle_extrude_along_curve,
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
    handle_load_extracted_textures,
    handle_apply_detail_texture,
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
    handle_add_animation_events,
    handle_list_animation_events,
    handle_remove_animation_event,
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
    handle_generate_settlement,
    handle_compose_world_map,
    handle_generate_boss_arena,
    handle_generate_encounter,
    handle_generate_world_graph,
    handle_generate_linked_interior,
    handle_generate_multi_floor_dungeon,
    handle_generate_overrun_variant,
    handle_generate_easter_egg,
    handle_add_storytelling_props,
    handle_prefetch_settlement_props,
)
from .worldbuilding_layout import (
    handle_generate_dungeon,
    handle_generate_cave,
    handle_generate_town,
    handle_generate_hearthvale,
)
from .environment_scatter import (
    handle_scatter_vegetation,
    handle_scatter_props,
    handle_create_breakable,
)
from .equipment import (
    handle_equipment_split_character,
    handle_equipment_fit_armor,
    handle_equipment_render_icon,
)
from .procedural_materials import (
    handle_create_procedural_material,
)
from .particles import (
    handle_add_particle_system,
    handle_configure_particle_physics,
    handle_hair_grooming,
)
from .physics import (
    handle_add_rigid_body,
    handle_add_cloth,
    handle_add_soft_body,
    handle_bake_physics,
)
from .vertex_colors import (
    handle_auto_paint_vertex_colors,
)
from .weathering import (
    handle_apply_weathering,
    handle_mix_weathering_over_texture,
)
from .terrain_materials import (
    handle_setup_terrain_biome,
    handle_create_biome_terrain,
)
from .vegetation_system import (
    handle_scatter_biome_vegetation,
)
from .addon_toolchain import (
    handle_inspect_external_toolchain,
    handle_configure_external_toolchain,
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
from .character_skin_modifier import (  # noqa: F401 -- Skin Modifier body generation (AAA)
    handle_generate_skin_body,
    handle_generate_character_body,
    get_skeleton,
    BODY_SKELETONS,
    MONSTER_SKELETONS,
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
from .terrain_sculpt import (  # noqa: F401 -- Terrain sculpting (GAP-09)
    handle_sculpt_terrain,
    # Pure-logic helpers (exported for tests)
    get_falloff_value,
    compute_brush_weights,
    compute_raise_displacements,
    compute_lower_displacements,
    compute_smooth_displacements,
    compute_flatten_displacements,
    compute_stamp_displacements,
)
from .atmospheric_volumes import (  # noqa: F401 -- Atmospheric volume props
    compute_atmospheric_placements,
    compute_volume_mesh_spec,
    estimate_atmosphere_performance,
    ATMOSPHERIC_VOLUMES,
    BIOME_ATMOSPHERE_RULES,
)
from .modeling_advanced import (  # noqa: F401 -- Advanced modeling (gaps 34-43, 67-78)
    handle_symmetry_edit,
    handle_loop_select,
    handle_selection_modify,
    handle_bridge_edges,
    handle_modifier,
    handle_circularize,
    handle_insert_mesh,
    handle_alpha_stamp,
    handle_proportional_edit,
    handle_bisect,
    handle_mesh_checkpoint,
    # Pure-logic exports for testing
    validate_symmetry_params,
    validate_loop_select_params,
    validate_selection_modify_params,
    validate_bridge_params,
    validate_modifier_params,
    validate_circularize_params,
    validate_insert_mesh_params,
    validate_alpha_stamp_params,
    validate_proportional_edit_params,
    validate_bisect_params,
    validate_checkpoint_params,
    compute_falloff_weight,
    compute_proportional_weights,
    compute_bisect_side,
    normalize_vector,
    VALID_MODIFIER_TYPES,
    VALID_FALLOFF_TYPES,
    VALID_ALPHA_PATTERNS,
)
from .hair_system import (  # noqa: F401 -- Hair/facial hair mesh generation
    generate_hair_mesh,
    get_helmet_compatible_hair,
    generate_facial_hair_mesh,
    HAIR_STYLES,
    FACIAL_HAIR_STYLES,
)
from .equipment_fitting import (  # noqa: F401 -- Equipment-body integration
    compute_equipment_body_changes,
    apply_body_shrink,
    get_body_region_vertices,
    compute_vertex_normals,
    BODY_PART_VISIBILITY,
)
from .terrain_advanced import (  # noqa: F401 -- Advanced terrain (gaps 44-48, 75, 28, 30)
    handle_spline_deform,
    handle_terrain_layers,
    handle_erosion_paint,
    handle_terrain_stamp,
    handle_snap_to_terrain,
    # Pure-logic exports for testing
    evaluate_spline,
    distance_point_to_polyline,
    compute_spline_deformation,
    compute_falloff,
    TerrainLayer,
    apply_layer_operation,
    flatten_layers,
    compute_erosion_brush,
    compute_flow_map,
    apply_thermal_erosion,
    compute_stamp_heightmap,
    apply_stamp_to_heightmap,
)
from .vegetation_lsystem import (  # noqa: F401 -- L-system vegetation pipeline
    generate_lsystem_tree,
    generate_leaf_cards,
    bake_wind_vertex_colors,
    generate_billboard_impostor,
    prepare_gpu_instancing_export,
    # Pure-logic exports for testing
    expand_lsystem,
    interpret_lsystem,
    branches_to_mesh,
    generate_roots,
    LSYSTEM_GRAMMARS,
)
from .riggable_objects import (  # noqa: F401 -- Riggable environmental objects
    generate_door,
    generate_chain,
    generate_flag,
    generate_chest,
    generate_chandelier,
    generate_drawbridge,
    generate_rope_bridge,
    generate_hanging_sign,
    generate_windmill,
    generate_cage,
)
from .weapon_quality import (  # noqa: F401 -- AAA quality weapon/armor generators
    generate_quality_sword,
    generate_quality_axe,
    generate_quality_mace,
    generate_quality_bow,
    generate_quality_shield,
    generate_quality_staff,
    generate_quality_pauldron,
    generate_quality_chestplate,
    generate_quality_gauntlet,
    QUALITY_GENERATORS,
)
from .creature_anatomy import (  # noqa: F401 -- AAA creature anatomy generators
    generate_mouth_interior,
    generate_eyelid_topology,
    generate_paw,
    generate_wing,
    generate_serpent_body,
    generate_quadruped,
    generate_fantasy_creature,
    QUADRUPED_PROPORTIONS,
    ALL_SPECIES,
    WING_TYPES,
    PAW_TYPES,
    FANTASY_CREATURE_TYPES,
    BRAND_ANATOMY_FEATURES,
)
from .building_quality import (  # noqa: F401 -- kept for internal worldbuilding layout use only
    generate_stone_wall,
    generate_gothic_window,
    generate_roof,
    generate_archway,
)
from .character_advanced import (  # noqa: F401 -- DNA blending, cloth proxies, hair, facial, morphs
    handle_dna_blend,
    handle_cloth_collision_proxy,
    handle_hair_strands,
    handle_facial_setup as handle_facial_setup_advanced,
    handle_body_morph,
    # Pure-logic exports for testing
    compute_collision_capsule,
    compute_collision_box,
    generate_strand_curve,
    generate_hair_guide_strands,
    compute_morph_deltas,
    VALID_HAIR_STYLES as CHARACTER_HAIR_STYLES,
    VALID_MORPH_NAMES,
    VALID_COLLISION_TYPES,
    VALID_FACIAL_LEVELS,
    VALID_BODY_PARTS,
    BODY_MORPH_TARGETS,
    FACIAL_LANDMARKS,
)
from .animation_production import (  # noqa: F401 -- FK/IK, retarget, mocap, pose lib, layers, keyframes, contact
    handle_fk_ik_switch,
    handle_retarget_motion,
    handle_import_mocap,
    handle_pose_library,
    handle_animation_layer,
    handle_keyframe_edit,
    handle_contact_solver,
    # Pure-logic exports for testing
    compute_bone_mapping_auto,
    compute_noise_filter,
    compute_contact_phases,
    compute_euler_filter,
    lerp_pose,
    validate_fk_ik_params,
    validate_retarget_params,
    validate_mocap_params,
    validate_pose_library_params,
    validate_animation_layer_params,
    validate_keyframe_edit_params,
    validate_contact_solver_params,
    VALID_LIMBS,
    VALID_FK_IK_MODES,
    LIMB_CHAIN_MAP,
    VALID_POSE_ACTIONS,
    VALID_POSE_CATEGORIES,
    VALID_LAYER_ACTIONS,
    VALID_KEYFRAME_OPERATIONS,
    VALID_INTERPOLATIONS,
    VALID_HANDLE_TYPES,
    VALID_CHANNELS,
)
from .geometry_nodes import (  # noqa: F401 -- Geometry Nodes management, scatter, particle-to-mesh
    handle_geometry_nodes,
    handle_face_scatter,
    handle_particle_to_mesh,
    # Pure-logic exports for testing
    compute_face_scatter_positions,
    compute_hair_card_mesh,
    generate_scatter_preset_code,
    generate_boolean_preset_code,
    generate_array_curve_preset_code,
    generate_vertex_displacement_code,
    VALID_GN_NODE_TYPES,
    VALID_GN_PRESETS,
)
from .facial_topology import (  # noqa: F401 -- Facial/extremity mesh generation
    generate_face_mesh,
    generate_blend_shape_targets,
    generate_hand_mesh,
    generate_foot_mesh,
    generate_claw_hand_mesh,
    generate_hoof_mesh,
    generate_paw_mesh,
    generate_corrective_shapes,
)
from .clothing_system import (  # noqa: F401 -- Clothing mesh generation
    generate_clothing,
    generate_tunic,
    generate_robe,
    generate_cloak,
    generate_hood,
    generate_pants,
    generate_shirt,
    generate_belt,
    generate_scarf,
    generate_tabard,
    generate_loincloth,
    generate_bandage_wrap,
    generate_sash,
    CLOTHING_GENERATORS,
    CLOTHING_STYLES,
)
from .texture_painting import (  # noqa: F401 -- Multi-channel texture painting
    handle_multi_channel_paint,
    handle_paint_stroke,
    handle_projection_paint,
    handle_stencil_paint,
    # Pure-logic exports for testing
    compute_multi_channel_blend,
    apply_stencil_mask,
    compute_projection_uvs,
    compute_box_projection_uvs,
    validate_projection_type,
    validate_blend_mode,
    validate_paint_channels,
    VALID_PROJECTION_TYPES,
    VALID_PAINT_CHANNELS,
    VALID_BLEND_MODES as TEXTURE_PAINT_BLEND_MODES,
    VALID_FALLOFF_TYPES as TEXTURE_PAINT_FALLOFF_TYPES,
)
from .vertex_paint_live import (  # noqa: F401 -- Live vertex color painting
    handle_vertex_paint,
    # Pure-logic exports for testing
    compute_paint_weights,
    compute_paint_weights_uv,
    blend_colors,
)
from .autonomous_loop import (  # noqa: F401 -- Autonomous quality loop
    handle_autonomous_refine,
    # Pure-logic exports for testing
    evaluate_mesh_quality,
    select_fix_action,
)
from .terrain_chunking import (  # noqa: F401 -- Terrain chunking for streaming
    compute_terrain_chunks,
    compute_chunk_lod,
    compute_streaming_distances,
    export_chunks_metadata,
)
from .texture_quality import (  # noqa: F401 -- AAA texture quality pipeline
    compute_smart_material_params,
    compute_trim_sheet_layout,
    compute_macro_variation_params,
    generate_smart_material_code,
    generate_trim_sheet_code,
    generate_macro_variation_code,
    generate_detail_texture_setup_code,
    generate_bake_map_code,
    SMART_MATERIAL_PRESETS,
    TRIM_ELEMENT_PBR,
    DETAIL_TEXTURE_TYPES,
    BAKE_MAP_TYPES,
)


# ---------------------------------------------------------------------------
# Quality mesh builder — converts pure-logic MeshSpec into a Blender object
# with empties, vertex groups, and returns a JSON-serializable result dict.
# ---------------------------------------------------------------------------

def _build_quality_object(spec: dict, position: tuple | None = None) -> dict:
    """Build a Blender object from a MeshSpec dict.

    Creates the mesh via mesh_from_spec, attaches empties for attachment
    points, assigns vertex groups, and returns a JSON-serializable summary.
    """
    import bpy
    import math

    loc = tuple(position) if position else (0.0, 0.0, 0.0)

    # Detect if this is a weapon/vertically-oriented asset (blade along Y)
    # and rotate so blade points UP (Z axis) for game-ready orientation
    category = spec.get("metadata", {}).get("category", "")
    is_weapon = category == "weapon" or any(
        k in spec.get("vertex_groups", {}) for k in ("blade", "shaft", "limb")
    )
    rot = (-math.pi / 2, 0.0, 0.0) if is_weapon else (0.0, 0.0, 0.0)

    obj = mesh_from_spec(spec, location=loc, rotation=rot)

    # Non-Blender fallback (testing)
    if isinstance(obj, dict):
        return spec

    # Apply smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    obj_name = obj.name

    # Create empties for attachment points
    empties_data = spec.get("empties", {})
    for empty_name, empty_pos in empties_data.items():
        empty = bpy.data.objects.new(empty_name, None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.02
        empty.location = tuple(empty_pos)
        empty.parent = obj
        bpy.context.collection.objects.link(empty)

    # Create vertex groups
    vgroups = spec.get("vertex_groups", {})
    for group_name, indices in vgroups.items():
        vg = obj.vertex_groups.new(name=group_name)
        vg.add(indices, 1.0, "ADD")

    # Build serializable result
    meta = spec.get("metadata", {})
    result: dict[str, Any] = {
        "object_name": obj_name,
        "vertices": meta.get("vertex_count", len(spec.get("vertices", []))),
        "faces": meta.get("poly_count", len(spec.get("faces", []))),
    }
    if empties_data:
        result["empties"] = list(empties_data.keys())
    if vgroups:
        result["vertex_groups"] = list(vgroups.keys())
    if "quality_metrics" in spec:
        result["quality_metrics"] = spec["quality_metrics"]
    if "dimensions" in meta:
        result["dimensions"] = meta["dimensions"]
    if "style" in meta:
        result["style"] = meta["style"]
    if "components" in spec:
        result["components"] = spec["components"]

    return result


COMMAND_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "ping": lambda params: {"status": "success", "result": "pong"},
    # Scene
    "get_scene_info": handle_get_scene_info,
    "clear_scene": handle_clear_scene,
    "configure_scene": handle_configure_scene,
    "list_objects": handle_list_objects,
    # Scene/World settings
    "setup_world": handle_setup_world,
    "add_light": handle_add_light,
    "add_camera": handle_add_camera,
    "configure_render": handle_configure_render,
    # Collection operations (SC-02)
    "create_collection": handle_create_collection,
    "move_to_collection": handle_move_to_collection,
    "set_visibility": handle_set_visibility,
    "organize_by_type": handle_organize_by_type,
    "toggle_collection_visibility": handle_toggle_collection_visibility,
    "list_collections": handle_list_collections,
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
    "mesh_loop_cut": handle_loop_cut,
    "mesh_bevel_edges": handle_bevel_edges,
    "mesh_knife_project": handle_knife_project,
    "mesh_proportional_edit": handle_proportional_edit,
    # Curve operations
    "curve_create": handle_create_curve,
    "curve_to_mesh": handle_curve_to_mesh,
    "curve_extrude_along": handle_extrude_along_curve,
    # Advanced sculpt operations (MESH-04b..f)
    "mesh_sculpt_brush": handle_sculpt_brush,
    "mesh_dyntopo": handle_dyntopo,
    "mesh_voxel_remesh": handle_voxel_remesh,
    "mesh_face_sets": handle_face_sets,
    "mesh_multires": handle_multires,
    # AAA geometry enhancement (MESH-ENH)
    "mesh_enhance_geometry": handle_enhance_geometry,
    "mesh_bake_detail_normals": handle_bake_detail_normals,
    "mesh_bake_ao_map": handle_bake_ao_map,
    "mesh_bake_curvature_map": handle_bake_curvature_map,
    "mesh_validate_enhancement": handle_validate_enhancement,
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
    "texture_load_extracted_textures": handle_load_extracted_textures,
    "texture_apply_detail": handle_apply_detail_texture,
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
    # Animation event markers (AN-05)
    "anim_add_events": handle_add_animation_events,
    "anim_list_events": handle_list_animation_events,
    "anim_remove_event": handle_remove_animation_event,
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
    "world_generate_hearthvale": handle_generate_hearthvale,
    # Worldbuilding v2 operations (Phase 14 -- world design)
    "world_generate_location": handle_generate_location,
    "world_generate_settlement": handle_generate_settlement,
    "world_compose_world_map": handle_compose_world_map,
    "world_generate_boss_arena": handle_generate_boss_arena,
    "world_generate_encounter": handle_generate_encounter,
    "world_generate_world_graph": handle_generate_world_graph,
    "world_generate_linked_interior": handle_generate_linked_interior,
    "world_generate_multi_floor_dungeon": handle_generate_multi_floor_dungeon,
    "world_generate_overrun_variant": handle_generate_overrun_variant,
    "world_generate_easter_egg": handle_generate_easter_egg,
    "world_prefetch_settlement_props": handle_prefetch_settlement_props,
    # Environment v2 operations (Phase 14 -- AAA-05 storytelling props)
    "env_add_storytelling_props": handle_add_storytelling_props,
    # Equipment operations — rewired to AAA quality generators
    "equipment_generate_weapon": lambda params: _build_quality_object(
        generate_quality_sword(
            style=params.get("style", "longsword"),
            blade_length=params.get("blade_length", 0.9),
            guard_style=params.get("guard_style", "cross"),
            pommel_style=params.get("pommel_style", "disk"),
            ornament_level=params.get("ornament_level", 2),
        )
        if params.get("weapon_type", "sword") == "sword"
        else generate_quality_axe(
            style=params.get("style", "battle_axe"),
            shaft_length=params.get("shaft_length", 0.8),
            ornament_level=params.get("ornament_level", 2),
        )
        if params.get("weapon_type") == "axe"
        else generate_quality_mace(
            style=params.get("style", "flanged"),
            shaft_length=params.get("shaft_length", 0.5),
            ornament_level=params.get("ornament_level", 2),
        )
        if params.get("weapon_type") == "mace"
        else generate_quality_bow(
            style=params.get("style", "longbow"),
            ornament_level=params.get("ornament_level", 2),
        )
        if params.get("weapon_type") == "bow"
        else generate_quality_shield(
            style=params.get("style", "kite"),
            ornament_level=params.get("ornament_level", 2),
        )
        if params.get("weapon_type") == "shield"
        else generate_quality_staff(
            style=params.get("style", "gnarled"),
            ornament_level=params.get("ornament_level", 2),
        )
        if params.get("weapon_type") == "staff"
        else generate_quality_sword(
            style=params.get("style", "longsword"),
            ornament_level=params.get("ornament_level", 2),
        )
    ),
    "equipment_split_character": handle_equipment_split_character,
    "equipment_fit_armor": handle_equipment_fit_armor,
    "equipment_render_icon": handle_equipment_render_icon,
    # Sculpt mode operations
    "sculpt_brush": handle_sculpt_brush,
    "sculpt_enter": handle_enter_sculpt_mode,
    "sculpt_exit": handle_exit_sculpt_mode,
    # Vertex colors and custom data operations
    "mesh_vertex_color": handle_vertex_color,
    "mesh_custom_normals": handle_custom_normals,
    "mesh_edge_data": handle_edge_data,
    # Particle system operations
    "particle_add_system": handle_add_particle_system,
    "particle_configure_physics": handle_configure_particle_physics,
    "particle_hair_groom": handle_hair_grooming,
    # Physics simulation operations
    "physics_add_rigid_body": handle_add_rigid_body,
    "physics_add_cloth": handle_add_cloth,
    "physics_add_soft_body": handle_add_soft_body,
    "physics_bake": handle_bake_physics,
    # Text object operations
    "text_create": handle_create_text,
    "text_to_mesh": handle_text_to_mesh,
    # Shape key workflow operations
    "mesh_shape_key": handle_shape_key,
    # Driver operations
    "driver_add": handle_add_driver,
    "driver_remove": handle_remove_driver,
    # Procedural material operations
    "material_create_procedural": handle_create_procedural_material,
    # Vertex color operations
    "vertex_colors_auto_paint": handle_auto_paint_vertex_colors,
    # Weathering operations
    "weathering_apply": handle_apply_weathering,
    "weathering_mix_over_texture": handle_mix_weathering_over_texture,
    # Terrain biome material operations
    "terrain_setup_biome": handle_setup_terrain_biome,
    "terrain_create_biome_material": handle_create_biome_terrain,
    # Per-biome vegetation quality system
    "env_scatter_biome_vegetation": handle_scatter_biome_vegetation,
    # External addon/toolchain inspection
    "toolchain_inspect_external": handle_inspect_external_toolchain,
    "toolchain_configure_external": handle_configure_external_toolchain,
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
    # Terrain sculpting (GAP-09)
    "terrain_sculpt": handle_sculpt_terrain,
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
    # Hair system (pure logic -- returns mesh specs)
    "hair_generate": lambda params: generate_hair_mesh(
        style=params.get("style", "short_crop"),
    ),
    "hair_helmet_compatible": lambda params: get_helmet_compatible_hair(
        style=params.get("style", "short_crop"),
        helmet_style=params.get("helmet_style", "open_face"),
    ),
    "hair_generate_facial": lambda params: generate_facial_hair_mesh(
        style=params.get("style", "stubble"),
    ),
    # Equipment-body integration (pure logic -- returns body change specs)
    "equipment_body_changes": lambda params: compute_equipment_body_changes(
        equipped_items=params.get("equipped_items", {}),
    ),
    "equipment_body_shrink": lambda params: apply_body_shrink(
        vertices=[tuple(v) for v in params.get("vertices", [])],
        normals=[tuple(n) for n in params.get("normals", [])],
        region_map=params.get("region_map", {}),
        shrink_regions=params.get("shrink_regions", {}),
    ),
    "equipment_body_regions": lambda params: get_body_region_vertices(
        vertices=[tuple(v) for v in params.get("vertices", [])],
    ),
    "equipment_vertex_normals": lambda params: compute_vertex_normals(
        vertices=[tuple(v) for v in params.get("vertices", [])],
        faces=params.get("faces", []),
    ),
    # Advanced modeling operations (gaps 34-43, 67-78)
    "mesh_symmetry": handle_symmetry_edit,
    "mesh_loop_select": handle_loop_select,
    "mesh_selection_modify": handle_selection_modify,
    "mesh_bridge": handle_bridge_edges,
    "mesh_modifier": handle_modifier,
    "mesh_circularize": handle_circularize,
    "mesh_insert": handle_insert_mesh,
    "mesh_alpha_stamp": handle_alpha_stamp,
    "mesh_proportional": handle_proportional_edit,
    "mesh_bisect": handle_bisect,
    "mesh_checkpoint": handle_mesh_checkpoint,
    # Advanced terrain operations (gaps 44-48, 75, 28, 30)
    "terrain_spline_deform": handle_spline_deform,
    "terrain_layers": handle_terrain_layers,
    "terrain_erosion_paint": handle_erosion_paint,
    "terrain_stamp": handle_terrain_stamp,
    "terrain_snap_objects": handle_snap_to_terrain,
    "terrain_flow_map": lambda params: compute_flow_map(
        heightmap=params.get("heightmap", []),
        resolution=params.get("resolution", 256),
    ),
    "terrain_thermal_erosion": lambda params: {
        "heightmap": apply_thermal_erosion(
            heightmap=params.get("heightmap", []),
            iterations=params.get("iterations", 50),
            talus_angle=params.get("talus_angle", 0.5),
            strength=params.get("strength", 0.3),
        ),
    },
    # L-system vegetation pipeline
    "vegetation_lsystem_tree": lambda params: generate_lsystem_tree(params),
    "vegetation_leaf_cards": lambda params: generate_leaf_cards(
        branch_tips=params.get("branch_tips", []),
        leaf_type=params.get("leaf_type", "broadleaf"),
        density=params.get("density", 0.8),
        seed=params.get("seed", 42),
    ),
    "vegetation_wind_colors": lambda params: bake_wind_vertex_colors(params),
    "vegetation_billboard": lambda params: generate_billboard_impostor(params),
    "vegetation_gpu_instancing": lambda params: prepare_gpu_instancing_export(params),
    # Skin Modifier character body generation (AAA quality)
    "character_generate_body": handle_generate_character_body,
    "character_generate_skin_code": handle_generate_skin_body,
    # Riggable environmental objects — build Blender objects from MeshSpec
    "riggable_generate_door": lambda params: _build_quality_object(generate_door(
        style=params.get("style", "wooden_plank"),
        width=params.get("width", 1.0),
        height=params.get("height", 2.0),
        thickness=params.get("thickness", 0.06),
    )),
    "riggable_generate_chain": lambda params: _build_quality_object(generate_chain(
        link_count=params.get("link_count", 8),
        link_width=params.get("link_width", 0.04),
        link_height=params.get("link_height", 0.06),
        link_thickness=params.get("link_thickness", 0.01),
        style=params.get("style", "iron"),
    )),
    "riggable_generate_flag": lambda params: _build_quality_object(generate_flag(
        width=params.get("width", 1.5),
        height=params.get("height", 1.0),
        pole_height=params.get("pole_height", 3.0),
        subdivisions=params.get("subdivisions", 12),
        style=params.get("style", "banner"),
    )),
    "riggable_generate_chest": lambda params: _build_quality_object(generate_chest(
        style=params.get("style", "wooden"),
        width=params.get("width", 0.6),
        height=params.get("height", 0.4),
        depth=params.get("depth", 0.4),
    )),
    "riggable_generate_chandelier": lambda params: _build_quality_object(generate_chandelier(
        style=params.get("style", "iron_ring"),
        candle_count=params.get("candle_count", 8),
        chain_length=params.get("chain_length", 1.5),
    )),
    "riggable_generate_drawbridge": lambda params: _build_quality_object(generate_drawbridge(
        width=params.get("width", 4.0),
        length=params.get("length", 3.0),
        plank_count=params.get("plank_count", 12),
    )),
    "riggable_generate_rope_bridge": lambda params: _build_quality_object(generate_rope_bridge(
        length=params.get("length", 8.0),
        width=params.get("width", 1.2),
        plank_count=params.get("plank_count", 20),
        sag=params.get("sag", 0.5),
    )),
    "riggable_generate_hanging_sign": lambda params: _build_quality_object(generate_hanging_sign(
        width=params.get("width", 0.8),
        height=params.get("height", 0.5),
        bracket_style=params.get("bracket_style", "iron_scroll"),
    )),
    "riggable_generate_windmill": lambda params: _build_quality_object(generate_windmill(
        tower_height=params.get("tower_height", 8.0),
        blade_count=params.get("blade_count", 4),
        blade_length=params.get("blade_length", 3.0),
    )),
    "riggable_generate_cage": lambda params: _build_quality_object(generate_cage(
        style=params.get("style", "hanging_cage"),
        width=params.get("width", 1.0),
        height=params.get("height", 1.5),
    )),
    # AAA quality weapon/armor generators — build Blender objects from MeshSpec
    "weapon_quality_sword": lambda params: _build_quality_object(generate_quality_sword(
        style=params.get("style", "longsword"),
        blade_length=params.get("blade_length", 0.9),
        blade_width=params.get("blade_width", 0.05),
        blade_thickness=params.get("blade_thickness", 0.005),
        fuller=params.get("fuller", True),
        guard_style=params.get("guard_style", "cross"),
        grip_length=params.get("grip_length", 0.2),
        grip_wrap=params.get("grip_wrap", "leather_spiral"),
        pommel_style=params.get("pommel_style", "disk"),
        edge_bevel=params.get("edge_bevel", 0.003),
        ornament_level=params.get("ornament_level", 2),
        include_scabbard=params.get("include_scabbard", False),
    )),
    "weapon_quality_axe": lambda params: _build_quality_object(generate_quality_axe(
        style=params.get("style", "battle_axe"),
        shaft_length=params.get("shaft_length", 0.8),
        head_width=params.get("head_width", 0.15),
        head_height=params.get("head_height", 0.18),
        head_thickness=params.get("head_thickness", 0.025),
        edge_bevel=params.get("edge_bevel", 0.003),
        grip_wrap=params.get("grip_wrap", "leather_spiral"),
        pommel_style=params.get("pommel_style", "ring"),
        ornament_level=params.get("ornament_level", 2),
    )),
    "weapon_quality_mace": lambda params: _build_quality_object(generate_quality_mace(
        style=params.get("style", "flanged"),
        shaft_length=params.get("shaft_length", 0.5),
        head_radius=params.get("head_radius", 0.04),
        num_flanges=params.get("num_flanges", 7),
        edge_bevel=params.get("edge_bevel", 0.003),
        grip_wrap=params.get("grip_wrap", "leather_spiral"),
        pommel_style=params.get("pommel_style", "disk"),
        ornament_level=params.get("ornament_level", 2),
    )),
    "weapon_quality_bow": lambda params: _build_quality_object(generate_quality_bow(
        style=params.get("style", "longbow"),
        bow_length=params.get("bow_length", 1.2),
        riser_width=params.get("riser_width", 0.04),
        limb_width=params.get("limb_width", 0.025),
        edge_bevel=params.get("edge_bevel", 0.002),
        ornament_level=params.get("ornament_level", 2),
    )),
    "weapon_quality_shield": lambda params: _build_quality_object(generate_quality_shield(
        style=params.get("style", "kite"),
        size=params.get("size", 1.0),
        edge_bevel=params.get("edge_bevel", 0.004),
        ornament_level=params.get("ornament_level", 2),
    )),
    "weapon_quality_staff": lambda params: _build_quality_object(generate_quality_staff(
        style=params.get("style", "gnarled"),
        length=params.get("length", 1.6),
        shaft_radius=params.get("shaft_radius", 0.018),
        edge_bevel=params.get("edge_bevel", 0.002),
        ornament_level=params.get("ornament_level", 2),
    )),
    "weapon_quality_pauldron": lambda params: _build_quality_object(generate_quality_pauldron(
        style=params.get("style", "plate"),
        size=params.get("size", 1.0),
        num_layers=params.get("num_layers", 3),
        edge_bevel=params.get("edge_bevel", 0.003),
        ornament_level=params.get("ornament_level", 2),
        side=params.get("side", "left"),
    )),
    "weapon_quality_chestplate": lambda params: _build_quality_object(generate_quality_chestplate(
        style=params.get("style", "plate"),
        size=params.get("size", 1.0),
        edge_bevel=params.get("edge_bevel", 0.003),
        ornament_level=params.get("ornament_level", 2),
    )),
    "weapon_quality_gauntlet": lambda params: _build_quality_object(generate_quality_gauntlet(
        style=params.get("style", "plate"),
        size=params.get("size", 1.0),
        side=params.get("side", "left"),
        edge_bevel=params.get("edge_bevel", 0.003),
        ornament_level=params.get("ornament_level", 2),
    )),
    # AAA creature anatomy generators — build Blender objects from MeshSpec
    "creature_mouth_interior": lambda params: _build_quality_object(generate_mouth_interior(
        mouth_width=params.get("mouth_width", 0.1),
        mouth_depth=params.get("mouth_depth", 0.12),
        jaw_length=params.get("jaw_length", 0.15),
        tooth_count=params.get("tooth_count", 20),
        tooth_style=params.get("tooth_style", "carnivore"),
        include_tongue=params.get("include_tongue", True),
        position=tuple(params.get("position", (0.0, 0.0, 0.0))),
    ), position=tuple(params.get("position", (0.0, 0.0, 0.0)))),
    "creature_eyelid_topology": lambda params: _build_quality_object(generate_eyelid_topology(
        eye_radius=params.get("eye_radius", 0.015),
        eye_position=tuple(params.get("eye_position", (0.0, 0.0, 0.0))),
    )),
    "creature_paw": lambda params: _build_quality_object(generate_paw(
        paw_type=params.get("paw_type", "canine"),
        toe_count=params.get("toe_count", 4),
        include_pads=params.get("include_pads", True),
        include_claws=params.get("include_claws", True),
        size=params.get("size", 1.0),
        position=tuple(params.get("position", (0.0, 0.0, 0.0))),
    ), position=tuple(params.get("position", (0.0, 0.0, 0.0)))),
    "creature_wing": lambda params: _build_quality_object(generate_wing(
        wing_type=params.get("wing_type", "bat"),
        wingspan=params.get("wingspan", 2.0),
        include_membrane=params.get("include_membrane", True),
        position=tuple(params.get("position", (0.0, 0.0, 0.0))),
    ), position=tuple(params.get("position", (0.0, 0.0, 0.0)))),
    "creature_serpent_body": lambda params: _build_quality_object(generate_serpent_body(
        length=params.get("length", 3.0),
        max_radius=params.get("max_radius", 0.08),
        segment_count=params.get("segment_count", 40),
        head_style=params.get("head_style", "viper"),
        include_hood=params.get("include_hood", False),
        size=params.get("size", 1.0),
    )),
    "creature_quadruped": lambda params: _build_quality_object(generate_quadruped(
        species=params.get("species", "wolf"),
        size=params.get("size", 1.0),
        build=params.get("build", "average"),
        include_mouth_interior=params.get("include_mouth_interior", True),
        include_eyelids=params.get("include_eyelids", True),
    )),
    "creature_fantasy": lambda params: _build_quality_object(generate_fantasy_creature(
        base_type=params.get("base_type", "chimera"),
        brand=params.get("brand"),
        size=params.get("size", 1.0),
    )),
    # AAA texture quality pipeline (pure logic -- returns params/code strings)
    "texture_smart_material_params": lambda params: compute_smart_material_params(
        material_type=params.get("material_type", "aged_stone"),
        age=params.get("age", 0.5),
        environment=params.get("environment", "indoor"),
    ),
    "texture_trim_sheet_layout": lambda params: compute_trim_sheet_layout(
        elements=params.get("elements"),
        resolution=params.get("resolution", 2048),
    ),
    "texture_macro_variation_params": lambda params: compute_macro_variation_params(
        surface_area=params.get("surface_area", 10.0),
        material_type=params.get("material_type", "stone"),
    ),
    "texture_smart_material_code": lambda params: generate_smart_material_code(
        material_type=params.get("material_type", "aged_stone"),
        object_name=params.get("object_name", "target"),
        wear_intensity=params.get("wear_intensity", 0.5),
        dirt_intensity=params.get("dirt_intensity", 0.5),
        moss_intensity=params.get("moss_intensity", 0.3),
        age=params.get("age", 0.5),
    ),
    "texture_trim_sheet_code": lambda params: generate_trim_sheet_code(
        sheet_name=params.get("sheet_name", "medieval_trim"),
        resolution=params.get("resolution", 2048),
        elements=params.get("elements"),
    ),
    "texture_macro_variation_code": lambda params: generate_macro_variation_code(
        object_name=params.get("object_name", "target"),
        variation_scale=params.get("variation_scale", 5.0),
        hue_shift=params.get("hue_shift", 0.03),
        value_shift=params.get("value_shift", 0.08),
    ),
    "texture_detail_setup_code": lambda params: generate_detail_texture_setup_code(
        object_name=params.get("object_name", "target"),
        detail_type=params.get("detail_type", "stone_pores"),
        detail_scale=params.get("detail_scale", 20.0),
        detail_strength=params.get("detail_strength", 0.3),
        blend_distance=params.get("blend_distance", 5.0),
    ),
    "texture_bake_map_code": lambda params: generate_bake_map_code(
        object_name=params.get("object_name", "target"),
        bake_type=params.get("bake_type", "position"),
        image_size=params.get("image_size", 1024),
    ),
    # Character advanced operations (DNA blending, cloth proxies, hair, facial, morphs)
    "character_dna_blend": handle_dna_blend,
    "character_cloth_collision_proxy": handle_cloth_collision_proxy,
    "character_hair_strands": handle_hair_strands,
    "character_facial_setup": handle_facial_setup_advanced,
    "character_body_morph": handle_body_morph,
    # Animation production operations (FK/IK, retarget, mocap, pose lib, layers, keyframes, contact)
    "anim_fk_ik_switch": handle_fk_ik_switch,
    "anim_retarget_motion": handle_retarget_motion,
    "anim_import_mocap": handle_import_mocap,
    "anim_pose_library": handle_pose_library,
    "anim_animation_layer": handle_animation_layer,
    "anim_keyframe_edit": handle_keyframe_edit,
    "anim_contact_solver": handle_contact_solver,
    # Geometry Nodes operations
    "geonodes_manage": handle_geometry_nodes,
    "geonodes_face_scatter": handle_face_scatter,
    "geonodes_particle_to_mesh": handle_particle_to_mesh,
    # Geometry Nodes preset code generators (pure logic -- returns code strings)
    "geonodes_scatter_preset_code": lambda params: generate_scatter_preset_code(
        target_name=params.get("target_name", "target"),
        instance_name=params.get("instance_name", "instance"),
        density=params.get("density", 10.0),
        seed=params.get("seed", 0),
    ),
    "geonodes_boolean_preset_code": lambda params: generate_boolean_preset_code(
        base_name=params.get("base_name", "base"),
        cutter_names=params.get("cutter_names", []),
        operation=params.get("operation", "UNION"),
    ),
    "geonodes_array_curve_preset_code": lambda params: generate_array_curve_preset_code(
        instance_name=params.get("instance_name", "instance"),
        curve_name=params.get("curve_name", "curve"),
        count=params.get("count", 10),
    ),
    "geonodes_vertex_displacement_code": lambda params: generate_vertex_displacement_code(
        target_name=params.get("target_name", "target"),
        scale=params.get("scale", 0.1),
        noise_scale=params.get("noise_scale", 5.0),
    ),
    # Clothing system — build Blender objects from MeshSpec
    "clothing_generate": lambda params: _build_quality_object(generate_clothing(
        clothing_type=params.get("clothing_type", "tunic"),
        body_verts=[tuple(v) for v in params.get("body_verts", [])] if params.get("body_verts") else None,
        size=params.get("size", 1.0),
        style=params.get("style", "default"),
    )),
    # Facial topology / extremity mesh generators — build Blender objects
    "facial_generate_face": lambda params: _build_quality_object(generate_face_mesh(
        detail_level=params.get("detail_level", "medium"),
    )),
    "facial_generate_hand": lambda params: _build_quality_object(generate_hand_mesh(
        detail=params.get("detail", "medium"),
        side=params.get("side", "right"),
        finger_count=params.get("finger_count", 5),
    )),
    "facial_generate_foot": lambda params: _build_quality_object(generate_foot_mesh(
        detail=params.get("detail", "medium"),
        side=params.get("side", "right"),
        toe_count=params.get("toe_count", 5),
    )),
    "facial_generate_claw_hand": lambda params: _build_quality_object(generate_claw_hand_mesh(
        claw_count=params.get("claw_count", 3),
        style=params.get("style", "sharp"),
        side=params.get("side", "right"),
    )),
    "facial_generate_hoof": lambda params: _build_quality_object(generate_hoof_mesh(
        style=params.get("style", "horse"),
        side=params.get("side", "right"),
        detail=params.get("detail", "medium"),
    )),
    "facial_generate_paw": lambda params: _build_quality_object(generate_paw_mesh(
        toe_count=params.get("toe_count", 4),
        has_claws=params.get("has_claws", True),
        side=params.get("side", "right"),
    )),
    # Legendary weapons — build Blender objects
    "legendary_weapon_generate": lambda params: _build_quality_object(
        generate_legendary_weapon_mesh(
            weapon_name=params.get("weapon_name", "shadowfang"),
        )
    ),
    # NPC body generation — build Blender objects
    "npc_generate_body": lambda params: _build_quality_object(generate_npc_body_mesh(
        gender=params.get("gender", "male"),
        build=params.get("build", "average"),
    )),
    # Texture painting operations
    "texture_multi_channel_paint": handle_multi_channel_paint,
    "texture_paint_stroke": handle_paint_stroke,
    "texture_projection_paint": handle_projection_paint,
    "texture_stencil_paint": handle_stencil_paint,
    # Vertex paint live operations
    "vertex_paint_live": handle_vertex_paint,
    # Autonomous quality loop
    "autonomous_refine": handle_autonomous_refine,
    # Autonomous quality evaluation (pure logic)
    "autonomous_evaluate_quality": lambda params: evaluate_mesh_quality(
        vertices=[tuple(v) for v in params.get("vertices", [])],
        faces=[tuple(f) for f in params.get("faces", [])],
        uvs=[tuple(uv) for uv in params.get("uvs", [])] if params.get("uvs") else None,
        normals=[tuple(n) for n in params.get("normals", [])] if params.get("normals") else None,
    ),
    "autonomous_select_fix": lambda params: select_fix_action(
        quality=params.get("quality", {}),
        targets=params.get("targets", {}),
        available_actions=params.get("available_actions", []),
    ),
    # Terrain chunking (pure logic -- returns chunk data)
    "terrain_compute_chunks": lambda params: compute_terrain_chunks(
        heightmap=params.get("heightmap", []),
        chunk_size=params.get("chunk_size", 64),
        overlap=params.get("overlap", 1),
        lod_levels=params.get("lod_levels", 4),
        world_scale=params.get("world_scale", 1.0),
    ),
    "terrain_chunk_lod": lambda params: compute_chunk_lod(
        heightmap_chunk=params.get("heightmap_chunk", []),
        target_resolution=params.get("target_resolution", 32),
    ),
    "terrain_streaming_distances": lambda params: compute_streaming_distances(
        chunk_world_size=params.get("chunk_world_size", 64.0),
        lod_levels=params.get("lod_levels", 4),
    ),
    "terrain_export_chunks_metadata": lambda params: export_chunks_metadata(
        chunks_result=params.get("chunks_result", {"chunks": [], "metadata": {}}),
        output_format=params.get("output_format", "json"),
    ),
}
