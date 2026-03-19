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
}
