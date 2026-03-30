"""unity_prefab tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.prefab_templates import (
    generate_prefab_create_script,
    generate_prefab_variant_script,
    generate_prefab_modify_script,
    generate_prefab_delete_script,
    generate_scaffold_prefab_script,
    generate_add_component_script,
    generate_remove_component_script,
    generate_configure_component_script,
    generate_reflect_component_script,
    generate_hierarchy_script,
    generate_batch_configure_script,
    generate_variant_matrix_script,
    generate_joint_setup_script,
    generate_navmesh_setup_script,
    generate_bone_socket_script,
    generate_validate_project_script,
    generate_job_script,
)
from veilbreakers_mcp.shared.unity_templates.character_templates import (
    generate_cloth_setup_script,
)




# ---------------------------------------------------------------------------
# unity_prefab compound tool -- Prefab, Component, Hierarchy, Physics, NavMesh
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_prefab(
    action: Literal[
        "create",
        "create_variant",
        "modify",
        "delete",
        "create_scaffold",
        "add_component",
        "remove_component",
        "configure",
        "reflect_component",
        "hierarchy",
        "batch_configure",
        "batch_job",
        "generate_variants",
        "setup_joints",
        "setup_navmesh",
        "setup_bone_sockets",
        "validate_project",
        "cloth_setup",              # CHAR-07: Unity Cloth component configuration
    ],
    # Params for create/scaffold
    name: str = "",
    prefab_type: str = "prop",
    save_dir: str = "Assets/Prefabs",
    # Params for variant
    base_prefab_path: str = "",
    overrides: dict | None = None,
    # Params for modify
    prefab_path: str = "",
    modifications: list[dict] | None = None,
    # Params for component/hierarchy/joint/navmesh -- SELECTOR-BASED
    selector: dict | str | None = None,
    # Legacy backward-compat
    object_name: str = "",
    component_type: str = "",
    properties: list[dict] | None = None,
    # Params for hierarchy
    operation: str = "",
    parent_name: str = "",
    new_name: str = "",
    layer: str = "",
    tag: str = "",
    enabled: bool = True,
    # Params for batch_configure
    batch_selector: dict | None = None,
    # Params for batch_job
    operations: list[dict] | None = None,
    # Params for variant matrix
    corruption_tiers: list[int] | None = None,
    brands: list[str] | None = None,
    output_dir: str = "Assets/Prefabs/Variants",
    # Params for joints
    joint_type: str = "HingeJoint",
    joint_config: dict | None = None,
    # Params for navmesh
    navmesh_operation: str = "add_obstacle",
    # Params for bone sockets
    sockets: list[str] | None = None,
    # Params for components list (auto-wire override)
    components: list[dict] | None = None,
    # Params for cloth_setup (CHAR-07)
    cloth_type: str = "cape",
    cloth_stiffness: float | None = None,
    cloth_damping: float | None = None,
    wind_main: float = 1.0,
    wind_turbulence: float = 0.5,
    collision_spheres: list[dict] | None = None
) -> str:
    """Unity Prefab, Component, and Hierarchy automation."""
    # Resolve selector: prefer explicit selector dict/str, fall back to object_name
    resolved_selector = selector if selector is not None else (object_name if object_name else None)

    try:
        if action == "create":
            return await _handle_prefab_create(name, prefab_type, save_dir, components)
        elif action == "create_variant":
            return await _handle_prefab_create_variant(name, base_prefab_path, overrides)
        elif action == "modify":
            return await _handle_prefab_modify(prefab_path, modifications)
        elif action == "delete":
            return await _handle_prefab_delete(prefab_path)
        elif action == "create_scaffold":
            return await _handle_prefab_scaffold(name, prefab_type)
        elif action == "add_component":
            return await _handle_prefab_add_component(resolved_selector, component_type, properties)
        elif action == "remove_component":
            return await _handle_prefab_remove_component(resolved_selector, component_type)
        elif action == "configure":
            return await _handle_prefab_configure(resolved_selector, component_type, properties)
        elif action == "reflect_component":
            return await _handle_prefab_reflect(resolved_selector, component_type)
        elif action == "hierarchy":
            return await _handle_prefab_hierarchy(
                operation, resolved_selector, parent_name, new_name, layer, tag, enabled, name
            )
        elif action == "batch_configure":
            return await _handle_prefab_batch_configure(batch_selector, component_type, properties)
        elif action == "batch_job":
            return await _handle_prefab_batch_job(operations)
        elif action == "generate_variants":
            return await _handle_prefab_generate_variants(
                name, base_prefab_path, corruption_tiers, brands, output_dir
            )
        elif action == "setup_joints":
            return await _handle_prefab_setup_joints(resolved_selector, joint_type, joint_config)
        elif action == "setup_navmesh":
            return await _handle_prefab_setup_navmesh(navmesh_operation, resolved_selector, joint_config)
        elif action == "setup_bone_sockets":
            return await _handle_prefab_setup_bone_sockets(prefab_path, sockets)
        elif action == "validate_project":
            return await _handle_prefab_validate_project()
        elif action == "cloth_setup":
            return await _handle_prefab_cloth_setup(
                name or "CharacterCloth", cloth_type, cloth_stiffness,
                cloth_damping, wind_main, wind_turbulence, collision_spheres,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_prefab action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Prefab handler functions
# ---------------------------------------------------------------------------


async def _handle_prefab_create(
    name: str, prefab_type: str, save_dir: str, components: list[dict] | None
) -> str:
    if not name:
        return json.dumps({"status": "error", "action": "create", "message": "name is required"})
    script = generate_prefab_create_script(name, prefab_type, save_dir, components)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_CreatePrefab.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_create_variant(
    name: str, base_prefab_path: str, overrides: dict | None
) -> str:
    if not base_prefab_path:
        return json.dumps({"status": "error", "action": "create_variant", "message": "base_prefab_path is required"})
    script = generate_prefab_variant_script(name, base_prefab_path, overrides)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_CreateVariant.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_variant", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_variant", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_modify(
    prefab_path: str, modifications: list[dict] | None
) -> str:
    if not prefab_path or not modifications:
        return json.dumps({"status": "error", "action": "modify", "message": "prefab_path and modifications are required"})
    script = generate_prefab_modify_script(prefab_path, modifications)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ModifyPrefab.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "modify", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "modify", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_delete(prefab_path: str) -> str:
    if not prefab_path:
        return json.dumps({"status": "error", "action": "delete", "message": "prefab_path is required"})
    script = generate_prefab_delete_script(prefab_path)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_DeletePrefab.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "delete", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "delete", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_scaffold(name: str, prefab_type: str) -> str:
    if not name:
        return json.dumps({"status": "error", "action": "create_scaffold", "message": "name is required"})
    script = generate_scaffold_prefab_script(name, prefab_type)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_CreateScaffold.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_scaffold", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_scaffold", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_add_component(
    resolved_selector: dict | str | None, component_type: str, properties: list[dict] | None
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "add_component", "message": "selector and component_type are required"})
    script = generate_add_component_script(resolved_selector, component_type, properties)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_AddComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "add_component", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "add_component", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_remove_component(
    resolved_selector: dict | str | None, component_type: str
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "remove_component", "message": "selector and component_type are required"})
    script = generate_remove_component_script(resolved_selector, component_type)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_RemoveComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "remove_component", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "remove_component", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_configure(
    resolved_selector: dict | str | None, component_type: str, properties: list[dict] | None
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "configure", "message": "selector and component_type are required"})
    if not properties:
        return json.dumps({"status": "error", "action": "configure", "message": "properties list is required"})
    script = generate_configure_component_script(resolved_selector, component_type, properties)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ConfigureComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "configure", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_reflect(
    resolved_selector: dict | str | None, component_type: str
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "reflect_component", "message": "selector and component_type are required"})
    script = generate_reflect_component_script(resolved_selector, component_type)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ReflectComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "reflect_component", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "reflect_component", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_hierarchy(
    operation: str,
    resolved_selector: dict | str | None,
    parent_name: str,
    new_name: str,
    layer: str,
    tag: str,
    enabled: bool,
    name: str,
) -> str:
    if not operation:
        return json.dumps({"status": "error", "action": "hierarchy", "message": "operation is required"})
    kwargs = {}
    if resolved_selector:
        kwargs["selector"] = resolved_selector
    if parent_name:
        kwargs["parent_name"] = parent_name
    if new_name:
        kwargs["new_name"] = new_name
    if layer:
        kwargs["layer"] = layer
    if tag:
        kwargs["tag"] = tag
    if name:
        kwargs["name"] = name
    kwargs["enabled"] = enabled
    script = generate_hierarchy_script(operation, **kwargs)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_Hierarchy.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "hierarchy", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "hierarchy", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_batch_configure(
    batch_selector: dict | None, component_type: str, properties: list[dict] | None
) -> str:
    if not batch_selector or not component_type:
        return json.dumps({"status": "error", "action": "batch_configure", "message": "batch_selector and component_type are required"})
    if not properties:
        return json.dumps({"status": "error", "action": "batch_configure", "message": "properties list is required"})
    script = generate_batch_configure_script(batch_selector, component_type, properties)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_BatchConfigure.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "batch_configure", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "batch_configure", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_batch_job(operations: list[dict] | None) -> str:
    if not operations:
        return json.dumps({"status": "error", "action": "batch_job", "message": "operations list is required"})
    script = generate_job_script(operations)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_JobScript.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "batch_job", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "batch_job", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_generate_variants(
    name: str,
    base_prefab_path: str,
    corruption_tiers: list[int] | None,
    brands: list[str] | None,
    output_dir: str,
) -> str:
    if not name or not base_prefab_path:
        return json.dumps({"status": "error", "action": "generate_variants", "message": "name and base_prefab_path are required"})
    if not corruption_tiers or not brands:
        return json.dumps({"status": "error", "action": "generate_variants", "message": "corruption_tiers and brands must have items"})
    script = generate_variant_matrix_script(name, base_prefab_path, corruption_tiers, brands, output_dir)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_VariantMatrix.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "generate_variants", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "generate_variants", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_setup_joints(
    resolved_selector: dict | str | None, joint_type: str, joint_config: dict | None
) -> str:
    if not resolved_selector or not joint_type:
        return json.dumps({"status": "error", "action": "setup_joints", "message": "selector and joint_type are required"})
    script = generate_joint_setup_script(resolved_selector, joint_type, joint_config or {})
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_SetupJoint.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "setup_joints", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "setup_joints", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_setup_navmesh(
    navmesh_operation: str, resolved_selector: dict | str | None, config: dict | None
) -> str:
    if not resolved_selector:
        return json.dumps({"status": "error", "action": "setup_navmesh", "message": "selector is required"})
    script = generate_navmesh_setup_script(navmesh_operation, resolved_selector, **(config or {}))
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_NavMeshSetup.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "setup_navmesh", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "setup_navmesh", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_setup_bone_sockets(
    prefab_path: str, sockets: list[str] | None
) -> str:
    if not prefab_path:
        return json.dumps({"status": "error", "action": "setup_bone_sockets", "message": "prefab_path is required"})
    script = generate_bone_socket_script(prefab_path, sockets)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_BoneSockets.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "setup_bone_sockets", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "setup_bone_sockets", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_validate_project() -> str:
    script = generate_validate_project_script()
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ValidateProject.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "validate_project", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "validate_project", "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_cloth_setup(
    mesh_name: str, cloth_type: str, stiffness: float | None,
    damping: float | None, wind_main: float, wind_turbulence: float,
    collision_spheres: list[dict] | None,
) -> str:
    """Configure Unity Cloth component on mesh (CHAR-07)."""
    script = generate_cloth_setup_script(
        mesh_name=mesh_name,
        cloth_type=cloth_type,
        stiffness=stiffness,
        damping=damping,
        wind_main=wind_main,
        wind_turbulence=wind_turbulence,
        collision_spheres=collision_spheres,
    )
    safe_name = mesh_name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Character/VeilBreakers_Cloth_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "cloth_setup", "message": str(exc)})
    return json.dumps({
        "status": "success",
        "action": "cloth_setup",
        "script_path": abs_path,
        "cloth_type": cloth_type,
        "mesh_name": mesh_name,
        "next_steps": STANDARD_NEXT_STEPS,
        "result_file": "Temp/vb_result.json",
    }, indent=2)
