"""unity_gameobject tool handler.

Real-time Unity GameObject/component/scene operations via VBBridge TCP.
Unlike other Unity tools, these are bridge-only -- no script fallback.
If the bridge is unavailable, return an error directing user to run
unity_qa action=setup_bridge first.
"""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import mcp, logger, _try_bridge


@mcp.tool()
async def unity_gameobject(
    action: Literal[
        "create", "delete", "duplicate", "reparent",
        "set_transform", "update", "find",
        "get_components", "add_component", "remove_component",
        "get_hierarchy", "get_scene_info", "save_scene",
        "undo", "redo", "instantiate_prefab",
    ],
    name: str = "",
    path: str = "",
    instance_id: int = 0,
    primitive_type: str = "",
    parent_path: str = "",
    new_parent_path: str = "",
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
    local: bool = False,
    tag: str = "",
    layer: int = -1,
    active: bool | None = None,
    name_contains: str = "",
    component_type: str = "",
    include_inactive: bool = False,
    include_components: bool = False,
    max_depth: int = 10,
    index: int = 0,
    prefab_path: str = "",
    scene_path: str = "",
) -> str:
    """Real-time Unity GameObject, component, and scene operations via VBBridge.

    Bridge-only tool -- requires VBBridge TCP connection (port 9877).
    If the bridge is not running, returns an error with setup instructions.

    Actions:
        create: Create a new GameObject (optionally with primitive mesh).
        delete: Delete a GameObject by path or instance_id.
        duplicate: Clone a GameObject.
        reparent: Move a GameObject to a new parent (or root).
        set_transform: Set position/rotation/scale (world or local).
        update: Modify name/tag/layer/active state.
        find: Search for GameObjects with filters (name, tag, layer, component).
        get_components: List all components on a GameObject with field values.
        add_component: Add a component by type name.
        remove_component: Remove a component by type name and optional index.
        get_hierarchy: Get full scene hierarchy tree with depth limit.
        get_scene_info: Get active scene name, path, root count, dirty state.
        save_scene: Save the active scene (optionally to a new path).
        undo: Perform Unity undo.
        redo: Perform Unity redo.
        instantiate_prefab: Instantiate a prefab from an asset path.
    """
    _NOT_CONNECTED = json.dumps({
        "status": "error",
        "message": (
            "VBBridge not connected. Start Unity and run "
            "unity_qa action=setup_bridge first."
        ),
    })

    try:
        bridge_cmd, params = _build_command(
            action, name=name, path=path, instance_id=instance_id,
            primitive_type=primitive_type, parent_path=parent_path,
            new_parent_path=new_parent_path, position=position,
            rotation=rotation, scale=scale, local=local, tag=tag,
            layer=layer, active=active, name_contains=name_contains,
            component_type=component_type, include_inactive=include_inactive,
            include_components=include_components, max_depth=max_depth,
            index=index, prefab_path=prefab_path, scene_path=scene_path,
        )

        result = await _try_bridge(bridge_cmd, params)
        if result is None:
            return _NOT_CONNECTED

        return json.dumps({
            "status": "success",
            "action": action,
            "bridge": True,
            **result,
        }, indent=2)

    except Exception as exc:
        logger.exception("unity_gameobject action '%s' failed", action)
        return json.dumps({
            "status": "error",
            "action": action,
            "message": str(exc),
        })


def _build_command(
    action: str, **kwargs,
) -> tuple[str, dict]:
    """Map an MCP action to a bridge command name and parameter dict."""
    ACTION_MAP = {
        "create": "create_gameobject",
        "delete": "delete_gameobject",
        "duplicate": "duplicate_gameobject",
        "reparent": "reparent_gameobject",
        "set_transform": "set_transform",
        "update": "update_gameobject",
        "find": "find_gameobjects",
        "get_components": "get_components",
        "add_component": "add_component",
        "remove_component": "remove_component",
        "get_hierarchy": "get_hierarchy",
        "get_scene_info": "get_scene_info",
        "save_scene": "save_scene",
        "undo": "undo",
        "redo": "redo",
        "instantiate_prefab": "instantiate_prefab",
    }

    bridge_cmd = ACTION_MAP.get(action)
    if not bridge_cmd:
        raise ValueError(f"Unknown action: {action}")

    # Build params dict, only including non-default values
    params: dict = {}

    # Common identifiers
    if kwargs.get("name"):
        params["name"] = kwargs["name"]
    if kwargs.get("path"):
        params["path"] = kwargs["path"]
    if kwargs.get("instance_id"):
        params["instance_id"] = kwargs["instance_id"]

    # Transform
    if kwargs.get("position") is not None:
        params["position"] = kwargs["position"]
    if kwargs.get("rotation") is not None:
        params["rotation"] = kwargs["rotation"]
    if kwargs.get("scale") is not None:
        params["scale"] = kwargs["scale"]
    if kwargs.get("local"):
        params["local"] = True

    # GameObject properties
    if kwargs.get("primitive_type"):
        params["primitive_type"] = kwargs["primitive_type"]
    if kwargs.get("parent_path"):
        params["parent_path"] = kwargs["parent_path"]
    if kwargs.get("new_parent_path"):
        params["new_parent_path"] = kwargs["new_parent_path"]
    if kwargs.get("tag"):
        params["tag"] = kwargs["tag"]
    if kwargs.get("layer", -1) >= 0:
        params["layer"] = kwargs["layer"]
    if kwargs.get("active") is not None:
        params["active"] = kwargs["active"]

    # Search filters
    if kwargs.get("name_contains"):
        params["name_contains"] = kwargs["name_contains"]
    if kwargs.get("component_type"):
        params["component_type"] = kwargs["component_type"]
    if kwargs.get("include_inactive"):
        params["include_inactive"] = True
    if kwargs.get("include_components"):
        params["include_components"] = True
    if kwargs.get("max_depth", 10) != 10:
        params["max_depth"] = kwargs["max_depth"]
    if kwargs.get("index"):
        params["index"] = kwargs["index"]

    # Prefab/scene paths
    if kwargs.get("prefab_path"):
        params["prefab_path"] = kwargs["prefab_path"]
    if kwargs.get("scene_path"):
        params["scene_path"] = kwargs["scene_path"]

    return bridge_cmd, params
