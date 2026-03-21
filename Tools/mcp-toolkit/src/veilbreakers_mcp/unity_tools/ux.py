"""unity_ux tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

from veilbreakers_mcp.shared.unity_templates.ux_templates import (
    generate_minimap_script,
    generate_damage_numbers_script,
    generate_interaction_prompts_script,
    generate_primetween_sequence_script,
    generate_tmp_font_asset_script,
    generate_tmp_component_script,
    generate_tutorial_system_script,
    generate_accessibility_script,
    generate_character_select_script,
    generate_world_map_script,
    generate_rarity_vfx_script,
    generate_corruption_vfx_script,
)




# ===========================================================================
# Compound tool: unity_ux (Game UX & HUD Elements -- Phase 15)
# ===========================================================================


@mcp.tool()
async def unity_ux(
    action: Literal[
        "create_minimap",              # UIX-01
        "create_damage_numbers",       # UIX-03
        "create_interaction_prompts",  # UIX-04
        "create_primetween_sequence",  # SHDR-04
        "create_tmp_font_asset",       # PIPE-10
        "setup_tmp_components",        # PIPE-10
        "create_tutorial_system",      # UIX-02
        "create_accessibility",        # ACC-01
        "create_character_select",     # VB-09
        "create_world_map",            # RPG-08
        "create_rarity_vfx",           # EQUIP-07
        "create_corruption_vfx",       # EQUIP-08
    ],
    name: str = "default",
    # minimap params
    render_texture_size: int = 256,
    zoom: float = 50.0,
    follow_target: str = "Player",
    culling_layers: list[str] | None = None,
    compass_enabled: bool = True,
    marker_types: list[str] | None = None,
    update_interval: int = 3,
    # damage numbers params
    pool_size: int = 20,
    float_height: float = 80.0,
    duration: float = 0.8,
    crit_scale: float = 1.5,
    # interaction prompts params
    prompt_text: str = "Interact",
    trigger_radius: float = 2.5,
    fade_duration: float = 0.3,
    # primetween params
    sequence_type: str = "panel_entrance",
    # TMP font asset params
    font_path: str = "Assets/Fonts/Cinzel-Regular.ttf",
    font_output_path: str = "Assets/Fonts/Generated",
    sampling_size: int = 48,
    atlas_width: int = 1024,
    atlas_height: int = 1024,
    character_set: str | None = None,
    # TMP component params
    font_asset_path: str = "",
    font_size: int = 36,
    text_color: list[float] | None = None,
    rich_text: bool = True,
    auto_sizing: bool = False,
    min_font_size: int = 18,
    max_font_size: int = 72,
    # tutorial params
    steps: list[dict] | None = None,
    # character select params
    hero_paths: list[str] | None = None,
    # world map params
    map_resolution: int = 512,
    fog_resolution: int = 256,
    # common
    namespace: str = "",
) -> str:
    """Unity UX & HUD tools -- minimap, damage numbers, interaction prompts,
    PrimeTween sequences, TextMeshPro setup, tutorial system, accessibility,
    character select, world map, rarity VFX, corruption VFX.

    UX HUD actions (ux_templates.py batch 1):
    - create_minimap: Orthographic camera + RenderTexture minimap with markers (UIX-01)
    - create_damage_numbers: Floating damage numbers with PrimeTween + ObjectPool (UIX-03)
    - create_interaction_prompts: Context-sensitive prompts with Input System rebind (UIX-04)
    - create_primetween_sequence: PrimeTween UI animation utility class (SHDR-04)
    - create_tmp_font_asset: TMP font asset creation editor script (PIPE-10)
    - setup_tmp_components: TMP component configuration editor script (PIPE-10)

    UX System actions (ux_templates.py batch 2):
    - create_tutorial_system: Step-based tutorial with tooltips + highlight rects (UIX-02)
    - create_accessibility: Colorblind simulation, subtitles, screen reader, motor (ACC-01)
    - create_character_select: Hero path carousel with PrimeTween animations (VB-09)
    - create_world_map: Heightmap-to-texture world map with fog-of-war (RPG-08)
    - create_rarity_vfx: 5-tier rarity particle + glow VFX controller (EQUIP-07)
    - create_corruption_vfx: 0-100% progressive corruption visual controller (EQUIP-08)

    Args:
        action: The UX action to perform.
        name: Name for the generated system (used in file paths).
        render_texture_size: Minimap render texture size in pixels.
        zoom: Minimap camera orthographic size.
        follow_target: Minimap follow target GameObject name.
        culling_layers: Minimap camera culling layer names.
        compass_enabled: Whether minimap includes compass direction.
        marker_types: Minimap marker type names.
        update_interval: Minimap camera update frame interval.
        pool_size: Damage number object pool size.
        float_height: Damage number float height in screen pixels.
        duration: Damage number animation duration in seconds.
        crit_scale: Damage number critical hit scale multiplier.
        prompt_text: Interaction prompt default text.
        trigger_radius: Interaction prompt trigger radius.
        fade_duration: Interaction prompt fade animation duration.
        sequence_type: PrimeTween sequence type (panel_entrance/button_hover/notification_popup/screen_shake).
        font_path: Font file path for TMP font asset creation.
        font_output_path: Output directory for generated TMP font assets.
        sampling_size: TMP font sampling point size.
        atlas_width: TMP font atlas texture width.
        atlas_height: TMP font atlas texture height.
        character_set: Custom character set for TMP font (None = ASCII).
        font_asset_path: Path to existing TMP font asset for component setup.
        font_size: TMP component font size.
        text_color: TMP component text color [r,g,b,a].
        rich_text: TMP component rich text support.
        auto_sizing: TMP component auto-sizing enabled.
        min_font_size: TMP component minimum font size (auto-sizing).
        max_font_size: TMP component maximum font size (auto-sizing).
        steps: Tutorial step definitions (list of dicts with title/description).
        hero_paths: Character select hero path names.
        map_resolution: World map texture resolution.
        fog_resolution: World map fog-of-war texture resolution.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_minimap":
            return await _handle_ux_minimap(
                name, render_texture_size, zoom, follow_target,
                culling_layers, compass_enabled, marker_types,
                update_interval, ns_kwargs,
            )
        elif action == "create_damage_numbers":
            return await _handle_ux_damage_numbers(
                name, pool_size, float_height, duration, crit_scale, ns_kwargs,
            )
        elif action == "create_interaction_prompts":
            return await _handle_ux_interaction_prompts(
                name, prompt_text, trigger_radius, fade_duration, ns_kwargs,
            )
        elif action == "create_primetween_sequence":
            return await _handle_ux_primetween_sequence(
                sequence_type, name, ns_kwargs,
            )
        elif action == "create_tmp_font_asset":
            return await _handle_ux_tmp_font_asset(
                font_path, font_output_path, sampling_size,
                atlas_width, atlas_height, character_set, ns_kwargs,
            )
        elif action == "setup_tmp_components":
            return await _handle_ux_tmp_components(
                name, font_asset_path, font_size, text_color,
                rich_text, auto_sizing, min_font_size, max_font_size, ns_kwargs,
            )
        elif action == "create_tutorial_system":
            return await _handle_ux_tutorial(name, steps, ns_kwargs)
        elif action == "create_accessibility":
            return await _handle_ux_accessibility(name, ns_kwargs)
        elif action == "create_character_select":
            return await _handle_ux_character_select(hero_paths, ns_kwargs)
        elif action == "create_world_map":
            return await _handle_ux_world_map(name, map_resolution, fog_resolution, ns_kwargs)
        elif action == "create_rarity_vfx":
            return await _handle_ux_rarity_vfx(name, ns_kwargs)
        elif action == "create_corruption_vfx":
            return await _handle_ux_corruption_vfx(name, ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_ux action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# UX action handlers
# ---------------------------------------------------------------------------


async def _handle_ux_minimap(
    name: str, render_texture_size: int, zoom: float, follow_target: str,
    culling_layers: list[str] | None, compass_enabled: bool,
    marker_types: list[str] | None, update_interval: int, ns_kwargs: dict,
) -> str:
    """Create minimap system with orthographic camera + RenderTexture (UIX-01)."""
    editor_cs, runtime_cs = generate_minimap_script(
        name=name,
        render_texture_size=render_texture_size,
        zoom=zoom,
        follow_target=follow_target,
        culling_layers=culling_layers,
        compass_enabled=compass_enabled,
        marker_types=marker_types,
        update_interval=update_interval,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        editor_cs, f"Assets/Editor/Generated/UX/{safe_name}_MinimapSetup.cs",
    ))
    paths.append(_write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_Minimap.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_minimap",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the minimap system",
            "Run editor setup from VeilBreakers > UX > Create Minimap",
        ],
    }, indent=2)


async def _handle_ux_damage_numbers(
    name: str, pool_size: int, float_height: float,
    duration: float, crit_scale: float, ns_kwargs: dict,
) -> str:
    """Create floating damage numbers with PrimeTween + ObjectPool (UIX-03)."""
    script = generate_damage_numbers_script(
        name=name,
        pool_size=pool_size,
        float_height=float_height,
        duration=duration,
        crit_scale=crit_scale,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_DamageNumbers_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_damage_numbers",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile damage numbers",
            "Attach VB_DamageNumbers to a Canvas or HUD manager",
        ],
    }, indent=2)


async def _handle_ux_interaction_prompts(
    name: str, prompt_text: str, trigger_radius: float,
    fade_duration: float, ns_kwargs: dict,
) -> str:
    """Create interaction prompts with Input System rebind display (UIX-04)."""
    script = generate_interaction_prompts_script(
        name=name,
        prompt_text=prompt_text,
        trigger_radius=trigger_radius,
        fade_duration=fade_duration,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_InteractionPrompt_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_interaction_prompts",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile interaction prompts",
            "Attach to interactable objects with a trigger collider",
        ],
    }, indent=2)


async def _handle_ux_primetween_sequence(
    sequence_type: str, name: str, ns_kwargs: dict,
) -> str:
    """Create PrimeTween UI animation sequence utility (SHDR-04)."""
    script = generate_primetween_sequence_script(
        sequence_type=sequence_type,
        name=name,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UI/VB_PrimeTweenSequence_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_primetween_sequence",
        "sequence_type": sequence_type,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the animation utility",
            "Call static methods from UI scripts for PrimeTween animations",
        ],
    }, indent=2)


async def _handle_ux_tmp_font_asset(
    font_path: str, font_output_path: str, sampling_size: int,
    atlas_width: int, atlas_height: int, character_set: str | None,
    ns_kwargs: dict,
) -> str:
    """Create TMP font asset editor script (PIPE-10)."""
    script = generate_tmp_font_asset_script(
        font_path=font_path,
        output_path=font_output_path,
        sampling_size=sampling_size,
        atlas_width=atlas_width,
        atlas_height=atlas_height,
        character_set=character_set,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/UX/VB_TMPFontAssetCreator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_tmp_font_asset",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the font creator",
            "Execute menu item: VeilBreakers > UX > Create TMP Font Asset",
        ],
    }, indent=2)


async def _handle_ux_tmp_components(
    name: str, font_asset_path: str, font_size: int,
    text_color: list[float] | None, rich_text: bool,
    auto_sizing: bool, min_font_size: int, max_font_size: int,
    ns_kwargs: dict,
) -> str:
    """Create TMP component setup editor script (PIPE-10)."""
    script = generate_tmp_component_script(
        name=name,
        font_asset_path=font_asset_path,
        font_size=font_size,
        color=text_color,
        rich_text=rich_text,
        auto_sizing=auto_sizing,
        min_size=min_font_size,
        max_size=max_font_size,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/UX/VB_TMPSetup_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_tmp_components",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile TMP setup",
            "Execute menu item: VeilBreakers > UX > Setup TMP Components",
        ],
    }, indent=2)


async def _handle_ux_tutorial(
    name: str, steps: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Create tutorial system with step-based state machine (UIX-02)."""
    data_so_cs, manager_cs, uxml, uss = generate_tutorial_system_script(
        name=name, steps=steps, **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        data_so_cs, f"Assets/ScriptableObjects/UX/{safe_name}_TutorialData.cs",
    ))
    paths.append(_write_to_unity(
        manager_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_TutorialManager.cs",
    ))
    paths.append(_write_to_unity(
        uxml, f"Assets/UI/Tutorial/{safe_name}_Tutorial.uxml",
    ))
    paths.append(_write_to_unity(
        uss, f"Assets/UI/Tutorial/{safe_name}_Tutorial.uss",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_tutorial_system",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the tutorial system",
            "Create TutorialData ScriptableObject assets with step definitions",
        ],
    }, indent=2)


async def _handle_ux_accessibility(name: str, ns_kwargs: dict) -> str:
    """Create accessibility system with colorblind, subtitles, motor options (ACC-01)."""
    settings_cs, shader_hlsl, renderer_feature_cs = generate_accessibility_script(
        name=name, **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        settings_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_AccessibilitySettings.cs",
    ))
    paths.append(_write_to_unity(
        shader_hlsl, f"Assets/Shaders/{safe_name}_ColorblindSimulation.shader",
    ))
    paths.append(_write_to_unity(
        renderer_feature_cs, f"Assets/Scripts/Runtime/Rendering/{safe_name}_ColorblindFeature.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_accessibility",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile accessibility system",
            "Add the ColorblindFeature to the URP Renderer in Project Settings",
        ],
    }, indent=2)


async def _handle_ux_character_select(
    hero_paths: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create character selection screen with hero path carousel (VB-09)."""
    data_so_cs, manager_cs, uxml, uss = generate_character_select_script(
        hero_paths=hero_paths, **ns_kwargs,
    )
    paths = []
    paths.append(_write_to_unity(
        data_so_cs, "Assets/ScriptableObjects/UX/VB_HeroPathData.cs",
    ))
    paths.append(_write_to_unity(
        manager_cs, "Assets/Scripts/Runtime/UX/VB_CharacterSelectManager.cs",
    ))
    paths.append(_write_to_unity(
        uxml, "Assets/UI/CharacterSelect/VB_CharacterSelect.uxml",
    ))
    paths.append(_write_to_unity(
        uss, "Assets/UI/CharacterSelect/VB_CharacterSelect.uss",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_character_select",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile character select",
            "Create HeroPathData ScriptableObject assets for each hero path",
        ],
    }, indent=2)


async def _handle_ux_world_map(
    name: str, map_resolution: int, fog_resolution: int, ns_kwargs: dict,
) -> str:
    """Create world map with heightmap-to-texture and fog-of-war (RPG-08)."""
    editor_cs, runtime_cs = generate_world_map_script(
        name=name,
        map_resolution=map_resolution,
        fog_resolution=fog_resolution,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        editor_cs, f"Assets/Editor/Generated/UX/{safe_name}_WorldMapGenerator.cs",
    ))
    paths.append(_write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_WorldMap.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_world_map",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the world map system",
            "Run editor tool: VeilBreakers > UX > Generate World Map Texture",
        ],
    }, indent=2)


async def _handle_ux_rarity_vfx(name: str, ns_kwargs: dict) -> str:
    """Create rarity VFX controller with 5 tiers (EQUIP-07)."""
    script = generate_rarity_vfx_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_RarityVFX_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_rarity_vfx",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile rarity VFX",
            "Attach to item pickup or equipment display objects",
        ],
    }, indent=2)


async def _handle_ux_corruption_vfx(name: str, ns_kwargs: dict) -> str:
    """Create corruption VFX controller with 0-100% progression (EQUIP-08)."""
    script = generate_corruption_vfx_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_CorruptionVFX_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_corruption_vfx",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile corruption VFX",
            "Attach to player character or affected objects",
        ],
    }, indent=2)


async def _handle_check_compile_status(bridge_port: int = 9877) -> str:
    """Query the Unity bridge for compile error status.

    Sends a ``check_compile_status`` command to the VBBridge TCP server
    running inside Unity Editor.  Returns JSON with ``is_compiling``,
    ``has_errors``, ``error_count``, and ``errors`` fields.

    This should be called after writing C# scripts to verify that
    compilation succeeded before attempting further Unity operations.
    """
    try:
        conn = UnityConnection(port=bridge_port)
        result = await conn.send_command("check_compile_status", {})
        return json.dumps({
            "status": "success",
            "action": "check_compile_status",
            "is_compiling": result.get("is_compiling", False) if isinstance(result, dict) else False,
            "has_errors": result.get("has_errors", False) if isinstance(result, dict) else False,
            "error_count": result.get("error_count", 0) if isinstance(result, dict) else 0,
            "errors": result.get("errors", []) if isinstance(result, dict) else [],
        }, indent=2)
    except (ConnectionError, UnityCommandError) as exc:
        return json.dumps({
            "status": "error",
            "action": "check_compile_status",
            "message": (
                f"Cannot reach Unity bridge on port {bridge_port}. "
                f"Ensure Unity is running with VBBridge addon loaded. "
                f"Detail: {exc}"
            ),
        }, indent=2)
