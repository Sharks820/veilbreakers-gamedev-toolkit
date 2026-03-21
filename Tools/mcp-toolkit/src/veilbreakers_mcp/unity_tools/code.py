"""unity_code tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
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
    _sanitize_cs_identifier,
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
    parameter_type: str = "int",
) -> str:
    """C# code generation -- generate classes, modify scripts, create editor tools
    and architecture patterns.

    This compound tool generates C# source files covering arbitrary class types,
    script modification, editor windows/drawers/overlays, test classes, and
    common architecture patterns (service locator, object pool, singleton, state
    machine, event channels).

    Actions:
    - generate_class: Generate any C# class type (MonoBehaviour, SO, class, interface, enum, struct) (CODE-01)
    - modify_script: Modify existing C# script by adding usings, fields, properties, methods (CODE-02)
    - editor_window: Generate EditorWindow with MenuItem and OnGUI (CODE-03)
    - property_drawer: Generate CustomPropertyDrawer (CODE-03)
    - inspector_drawer: Generate CustomEditor (CODE-03)
    - scene_overlay: Generate SceneView Overlay (CODE-03)
    - generate_test: Generate NUnit test class for EditMode or PlayMode (CODE-04)
    - service_locator: Scaffold static service locator pattern (CODE-06)
    - object_pool: Scaffold generic ObjectPool<T> with optional GameObjectPool (CODE-07)
    - singleton: Scaffold MonoBehaviour or plain thread-safe singleton (CODE-08)
    - state_machine: Scaffold IState/StateMachine/BaseState framework (CODE-09)
    - event_channel: Scaffold ScriptableObject event channel system (CODE-10)

    Args:
        action: The code generation action to perform.
        class_name: Name of the class (required for generate_class, singleton, generate_test).
        class_type: Class type -- MonoBehaviour, ScriptableObject, class, static class, abstract class, interface, enum, struct.
        namespace: Optional C# namespace.
        base_class: Explicit base class override.
        interfaces: Interfaces to implement.
        usings: Additional using statements.
        attributes: Class-level attributes.
        fields: Field definitions (list of dicts).
        properties: Property definitions (list of dicts).
        methods: Method definitions (list of dicts).
        enum_values: Enum member names (only for enum class_type).
        summary: XML summary comment.
        output_dir: Output directory relative to Unity project (default Assets/Scripts/Generated).
        script_path: Path to existing script for modify_script action.
        add_usings: Usings to add (modify_script).
        add_fields: Fields to add (modify_script).
        add_properties: Properties to add (modify_script).
        add_methods: Methods to add (modify_script).
        add_attributes: Attributes to add (modify_script).
        window_name: EditorWindow class name (editor_window).
        menu_path: MenuItem path (editor_window).
        target_type: Target type for property_drawer/inspector_drawer.
        overlay_name: SceneView overlay class name.
        display_name: Display name for overlay header.
        drawer_body: Custom drawer OnGUI body.
        panel_body: Custom overlay panel body.
        on_gui_body: Custom OnGUI body for editor_window.
        fields_to_draw: Specific fields for inspector_drawer.
        test_mode: EditMode or PlayMode (generate_test).
        target_class: Target class for test setup (generate_test).
        test_methods: Test method definitions (generate_test).
        setup_body: SetUp method body (generate_test).
        teardown_body: TearDown method body (generate_test).
        singleton_type: MonoBehaviour or Plain (singleton).
        persistent: DontDestroyOnLoad for MonoBehaviour singletons.
        include_scene_persistent: Include auto-clear on scene load (service_locator).
        include_gameobject_pool: Include GameObjectPool subclass (object_pool).
        event_name: Event name for specific event channel subclass.
        has_parameter: Whether event carries a parameter (event_channel).
        parameter_type: C# type of event parameter (event_channel).
    """
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "modify_script":
            if not script_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "script_path is required"}
                )
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
            Path(backup_path).write_text(source, encoding="utf-8")
            modified, changes = modify_script(
                source=source,
                add_usings=add_usings,
                add_fields=add_fields,
                add_properties=add_properties,
                add_methods=add_methods,
                add_attributes=add_attributes,
            )
            full_path.write_text(modified, encoding="utf-8")
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": str(full_path),
                "backup_path": backup_path,
                "changes": changes,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the modified script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                    f"Execute menu item '{menu_path or f'VeilBreakers/Tools/{window_name}'}' from the menu bar",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the test class",
                    "Call unity_editor action='run_tests' to execute tests",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
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
