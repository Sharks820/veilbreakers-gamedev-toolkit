"""unity_settings tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.settings_templates import (
    generate_physics_settings_script,
    generate_physics_material_script,
    generate_player_settings_script,
    generate_build_settings_script,
    generate_quality_settings_script,
    generate_package_install_script,
    generate_package_remove_script,
    generate_tag_layer_script,
    generate_tag_layer_sync_script,
    generate_time_settings_script,
    generate_graphics_settings_script,
)




# ---------------------------------------------------------------------------
# unity_settings compound tool -- EDIT-04/05/06/07/08/09/11
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_settings(
    action: Literal[
        "configure_physics",
        "create_physics_material",
        "configure_player",
        "configure_build",
        "configure_quality",
        "install_package",
        "remove_package",
        "manage_tags_layers",
        "sync_tags_layers",
        "configure_time",
        "configure_graphics",
    ],
    # Physics params
    collision_matrix: dict | None = None,
    gravity: list[float] | None = None,
    material_name: str = "",
    friction: float = 0.5,
    bounciness: float = 0.0,
    friction_combine: str = "Average",
    bounce_combine: str = "Average",
    # Player settings params
    company: str = "",
    product: str = "",
    color_space: str = "",
    scripting_backend: str = "",
    api_level: str = "",
    icon_path: str = "",
    splash_path: str = "",
    default_screen_width: int = 0,
    default_screen_height: int = 0,
    # Build settings params
    scenes: list[str] | None = None,
    platform: str = "",
    defines: list[str] | None = None,
    # Quality settings params
    quality_levels: list[dict] | None = None,
    # Package params
    package_id: str = "",
    version: str = "",
    source: str = "upm",
    registry_url: str = "",
    scopes: list[str] | None = None,
    # Tag/layer params
    tags: list[str] | None = None,
    layers: list[str] | None = None,
    sorting_layers: list[str] | None = None,
    constants_cs_path: str = "",
    # Time params
    fixed_timestep: float = 0.02,
    maximum_timestep: float = 0.1,
    time_scale: float = 1.0,
    # Graphics params
    render_pipeline_path: str = "",
    fog_mode: str = "",
    fog_color: list[float] | None = None,
    fog_density: float = 0.0
) -> str:
    """Unity project settings automation -- configure Player, Build, Quality, Physics, Time, Graphics settings, manage packages, and tags/layers."""
    try:
        if action == "configure_physics":
            return await _handle_settings_physics(collision_matrix, gravity)
        elif action == "create_physics_material":
            if not material_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "material_name is required"}
                )
            return await _handle_settings_physics_material(
                material_name, friction, bounciness, friction_combine, bounce_combine
            )
        elif action == "configure_player":
            return await _handle_settings_player(
                company, product, color_space, scripting_backend, api_level,
                icon_path, splash_path, default_screen_width, default_screen_height,
            )
        elif action == "configure_build":
            return await _handle_settings_build(scenes, platform, defines)
        elif action == "configure_quality":
            if not quality_levels:
                return json.dumps(
                    {"status": "error", "action": action, "message": "quality_levels must be a non-empty list"}
                )
            return await _handle_settings_quality(quality_levels)
        elif action == "install_package":
            if not package_id:
                return json.dumps(
                    {"status": "error", "action": action, "message": "package_id is required"}
                )
            return await _handle_settings_install_package(
                package_id, version, source, registry_url, scopes
            )
        elif action == "remove_package":
            if not package_id:
                return json.dumps(
                    {"status": "error", "action": action, "message": "package_id is required"}
                )
            return await _handle_settings_remove_package(package_id)
        elif action == "manage_tags_layers":
            return await _handle_settings_tags_layers(tags, layers, sorting_layers)
        elif action == "sync_tags_layers":
            if not constants_cs_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "constants_cs_path is required"}
                )
            return await _handle_settings_sync_tags_layers(constants_cs_path)
        elif action == "configure_time":
            return await _handle_settings_time(fixed_timestep, maximum_timestep, time_scale)
        elif action == "configure_graphics":
            return await _handle_settings_graphics(
                render_pipeline_path, fog_mode, fog_color, fog_density
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_settings action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


async def _handle_settings_physics(
    collision_matrix: dict | None, gravity: list[float] | None
) -> str:
    """Generate and write the physics settings script."""
    script = generate_physics_settings_script(
        collision_matrix=collision_matrix, gravity=gravity
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_ConfigurePhysics.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_physics", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_physics",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_physics_material(
    material_name: str,
    friction: float,
    bounciness: float,
    friction_combine: str,
    bounce_combine: str,
) -> str:
    """Generate and write the physics material creation script."""
    script = generate_physics_material_script(
        name=material_name,
        friction=friction,
        bounciness=bounciness,
        friction_combine=friction_combine,
        bounce_combine=bounce_combine,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_CreatePhysicsMaterial.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_physics_material", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "create_physics_material",
            "script_path": abs_path,
            "material_name": material_name,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_player(
    company: str,
    product: str,
    color_space: str,
    scripting_backend: str,
    api_level: str,
    icon_path: str,
    splash_path: str,
    default_screen_width: int,
    default_screen_height: int,
) -> str:
    """Generate and write the player settings script."""
    script = generate_player_settings_script(
        company=company,
        product=product,
        color_space=color_space,
        scripting_backend=scripting_backend,
        api_level=api_level,
        icon_path=icon_path,
        splash_path=splash_path,
        default_screen_width=default_screen_width,
        default_screen_height=default_screen_height,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_PlayerSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_player", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_player",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_build(
    scenes: list[str] | None, platform: str, defines: list[str] | None
) -> str:
    """Generate and write the build settings script."""
    try:
        script = generate_build_settings_script(
            scenes=scenes, platform=platform, defines=defines
        )
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_build", "message": str(exc)})

    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_BuildSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_build", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_build",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_quality(quality_levels: list[dict]) -> str:
    """Generate and write the quality settings script."""
    script = generate_quality_settings_script(levels=quality_levels)
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_QualitySettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_quality", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_quality",
            "script_path": abs_path,
            "levels_count": len(quality_levels),
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_install_package(
    package_id: str,
    version: str,
    source: str,
    registry_url: str,
    scopes: list[str] | None,
) -> str:
    """Generate and write the package install script."""
    script = generate_package_install_script(
        package_id=package_id,
        version=version,
        source=source,
        registry_url=registry_url,
        scopes=scopes,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_InstallPackage.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "install_package", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "install_package",
            "script_path": abs_path,
            "package_id": package_id,
            "source": source,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_remove_package(package_id: str) -> str:
    """Generate and write the package remove script."""
    script = generate_package_remove_script(package_id=package_id)
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_RemovePackage.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "remove_package", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "remove_package",
            "script_path": abs_path,
            "package_id": package_id,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_tags_layers(
    tags: list[str] | None,
    layers: list[str] | None,
    sorting_layers: list[str] | None,
) -> str:
    """Generate and write the tag/layer management script."""
    script = generate_tag_layer_script(
        tags=tags, layers=layers, sorting_layers=sorting_layers
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_TagsLayers.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "manage_tags_layers", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "manage_tags_layers",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_sync_tags_layers(constants_cs_path: str) -> str:
    """Generate and write the tag/layer sync script."""
    script = generate_tag_layer_sync_script(constants_cs_path=constants_cs_path)
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_SyncTagsLayers.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "sync_tags_layers", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "sync_tags_layers",
            "script_path": abs_path,
            "constants_path": constants_cs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_time(
    fixed_timestep: float, maximum_timestep: float, time_scale: float
) -> str:
    """Generate and write the time settings script."""
    script = generate_time_settings_script(
        fixed_timestep=fixed_timestep,
        maximum_timestep=maximum_timestep,
        time_scale=time_scale,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_TimeSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_time", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_time",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_graphics(
    render_pipeline_path: str,
    fog_mode: str,
    fog_color: list[float] | None,
    fog_density: float,
) -> str:
    """Generate and write the graphics settings script."""
    script = generate_graphics_settings_script(
        render_pipeline_path=render_pipeline_path,
        fog_mode=fog_mode,
        fog_color=fog_color,
        fog_density=fog_density,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_GraphicsSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_graphics", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_graphics",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )
