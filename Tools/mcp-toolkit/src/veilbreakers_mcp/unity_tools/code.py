"""unity_code tool handler."""

import json
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.code_templates import (
    generate_class,
    modify_script,
    generate_editor_window,
    generate_property_drawer,
    generate_inspector_drawer,
    generate_scene_overlay,
    generate_test_class,
    generate_service_locator,
    generate_object_pool,
    generate_singleton,
    generate_state_machine,
    generate_so_event_channel,
)




# ---------------------------------------------------------------------------
# unity_code compound tool (CODE-01 through CODE-10)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_code(
    action: Literal[
        "generate_class",       # CODE-01: Generate any C# class type
        "modify_script",        # CODE-02: Modify existing C# script
        "editor_window",        # CODE-03: Generate EditorWindow
        "property_drawer",      # CODE-03: Generate PropertyDrawer
        "inspector_drawer",     # CODE-03: Generate custom Inspector
        "scene_overlay",        # CODE-03: Generate SceneView overlay
        "generate_test",        # CODE-04: Generate test class
        "service_locator",      # CODE-06: Scaffold service locator pattern
        "object_pool",          # CODE-07: Scaffold object pool pattern
        "singleton",            # CODE-08: Scaffold singleton pattern
        "state_machine",        # CODE-09: Scaffold state machine pattern
        "event_channel",        # CODE-10: Scaffold SO event channel
    ],
    # Class generation params (CODE-01)
    class_name: str = "",
    class_type: str = "MonoBehaviour",
    namespace: str = "",
    base_class: str = "",
    interfaces: list[str] | None = None,
    usings: list[str] | None = None,
    attributes: list[str] | None = None,
    fields: list[dict] | None = None,
    properties: list[dict] | None = None,
    methods: list[dict] | None = None,
    enum_values: list[str] | None = None,
    summary: str = "",
    output_dir: str = "Assets/Scripts/Generated",
    # Script modification params (CODE-02)
    script_path: str = "",
    add_usings: list[str] | None = None,
    add_fields: list[dict] | None = None,
    add_properties: list[dict] | None = None,
    add_methods: list[dict] | None = None,
    add_attributes: list[dict] | None = None,
    # Editor tool params (CODE-03)
    window_name: str = "",
    menu_path: str = "",
    target_type: str = "",
    overlay_name: str = "",
    display_name: str = "",
    drawer_body: str = "",
    panel_body: str = "",
    on_gui_body: str = "",
    fields_to_draw: list[str] | None = None,
    # Test params (CODE-04)
    test_mode: str = "EditMode",
    target_class: str = "",
    test_methods: list[dict] | None = None,
    setup_body: str = "",
    teardown_body: str = "",
    # Architecture pattern params (CODE-06-10)
    singleton_type: str = "MonoBehaviour",
    persistent: bool = True,
    include_scene_persistent: bool = True,
    include_gameobject_pool: bool = True,
    event_name: str = "",
    has_parameter: bool = False,
    parameter_type: str = "int"
) -> str:
    """C# code generation -- generate classes, modify scripts, create editor tools and architecture patterns."""
    try:
        if action == "generate_class":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            script = generate_class(
                class_name=class_name,
                class_type=class_type,
                namespace=namespace,
                usings=usings,
                base_class=base_class,
                interfaces=interfaces,
                attributes=attributes,
                fields=fields,
                properties=properties,
                methods=methods,
                enum_values=enum_values,
                summary=summary,
            )
            rel_path = f"{output_dir}/{class_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "class_name": class_name,
                "class_type": class_type,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "modify_script":
            if not script_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "script_path is required"}
                )
            if not settings.unity_project_path:
                raise ValueError("UNITY_PROJECT_PATH not configured")
            project_root = Path(settings.unity_project_path).resolve()
            full_path = (project_root / script_path).resolve()
            try:
                full_path.relative_to(project_root)
            except ValueError:
                return json.dumps(
                    {"status": "error", "action": action, "message": "Path traversal detected"}
                )
            if not full_path.exists():
                return json.dumps(
                    {"status": "error", "action": action, "message": f"Script not found: {script_path}"}
                )
            source = full_path.read_text(encoding="utf-8")
            # Create backup
            backup_path = str(full_path) + ".bak"
            _write_to_unity(source, f"{script_path}.bak")
            modified, changes = modify_script(
                source=source,
                add_usings=add_usings,
                add_fields=add_fields,
                add_properties=add_properties,
                add_methods=add_methods,
                add_attributes=add_attributes,
            )
            _write_to_unity(modified, script_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": str(full_path),
                "backup_path": backup_path,
                "changes": changes,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "editor_window":
            if not window_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "window_name is required"}
                )
            script = generate_editor_window(
                window_name=window_name,
                menu_path=menu_path or f"VeilBreakers/Tools/{window_name}",
                namespace=namespace or "VeilBreakers.Editor",
                fields=fields,
                on_gui_body=on_gui_body,
            )
            rel_path = f"Assets/Editor/Generated/Code/{window_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "property_drawer":
            if not target_type:
                return json.dumps(
                    {"status": "error", "action": action, "message": "target_type is required"}
                )
            script = generate_property_drawer(
                target_type=target_type,
                namespace=namespace or "VeilBreakers.Editor",
                drawer_body=drawer_body,
            )
            rel_path = f"Assets/Editor/Generated/Code/{target_type}Drawer.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "inspector_drawer":
            if not target_type:
                return json.dumps(
                    {"status": "error", "action": action, "message": "target_type is required"}
                )
            script = generate_inspector_drawer(
                target_type=target_type,
                namespace=namespace or "VeilBreakers.Editor",
                fields_to_draw=fields_to_draw,
            )
            rel_path = f"Assets/Editor/Generated/Code/{target_type}Editor.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "scene_overlay":
            if not overlay_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "overlay_name is required"}
                )
            script = generate_scene_overlay(
                overlay_name=overlay_name,
                display_name=display_name or overlay_name,
                namespace=namespace or "VeilBreakers.Editor",
                panel_body=panel_body,
            )
            rel_path = f"Assets/Editor/Generated/Code/{overlay_name}Overlay.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "generate_test":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            script = generate_test_class(
                class_name=class_name,
                test_mode=test_mode,
                namespace=namespace,
                target_class=target_class,
                test_methods=test_methods,
                setup_body=setup_body,
                teardown_body=teardown_body,
            )
            rel_path = f"Assets/Tests/{test_mode}/{class_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "test_mode": test_mode,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "service_locator":
            script = generate_service_locator(
                namespace=namespace or "VeilBreakers.Patterns",
                include_scene_persistent=include_scene_persistent,
            )
            rel_path = f"{output_dir}/ServiceLocator.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "object_pool":
            script = generate_object_pool(
                namespace=namespace or "VeilBreakers.Patterns",
                include_gameobject_pool=include_gameobject_pool,
            )
            rel_path = f"{output_dir}/ObjectPool.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "singleton":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            script = generate_singleton(
                class_name=class_name,
                singleton_type=singleton_type,
                namespace=namespace or "VeilBreakers.Patterns",
                persistent=persistent,
            )
            rel_path = f"{output_dir}/{class_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "singleton_type": singleton_type,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "state_machine":
            script = generate_state_machine(
                namespace=namespace or "VeilBreakers.Patterns",
            )
            rel_path = f"{output_dir}/StateMachine.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "event_channel":
            script = generate_so_event_channel(
                event_name=event_name,
                has_parameter=has_parameter,
                parameter_type=parameter_type,
                namespace=namespace or "VeilBreakers.Events.Channels",
            )
            file_name = f"{event_name}Event.cs" if event_name else "GameEvent.cs"
            rel_path = f"{output_dir}/{file_name}"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "event_name": event_name or "GameEvent (base classes)",
                "next_steps": STANDARD_NEXT_STEPS,
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_code action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )
