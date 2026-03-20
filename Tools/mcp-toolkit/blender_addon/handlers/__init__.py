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
)
from .pipeline_lod import handle_generate_lods
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
    # Pipeline operations
    "pipeline_generate_lods": handle_generate_lods,
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
}
