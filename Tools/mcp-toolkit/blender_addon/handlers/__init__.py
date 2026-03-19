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
}
