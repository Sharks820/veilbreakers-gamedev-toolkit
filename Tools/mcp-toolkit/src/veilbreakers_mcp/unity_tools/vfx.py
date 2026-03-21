"""unity_vfx tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.vfx_templates import (
    generate_particle_vfx_script,
    generate_brand_vfx_script,
    generate_environmental_vfx_script,
    generate_trail_vfx_script,
    generate_aura_vfx_script,
    generate_post_processing_script,
    generate_screen_effect_script,
    generate_ability_vfx_script,
)
from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_corruption_shader,
    generate_dissolve_shader,
    generate_force_field_shader,
    generate_water_shader,
    generate_foliage_shader,
    generate_outline_shader,
    generate_damage_overlay_shader,
    generate_arbitrary_shader,
    generate_renderer_feature,
)
from veilbreakers_mcp.shared.unity_templates.vfx_mastery_templates import (
    generate_flipbook_script,
    generate_vfx_graph_composition_script,
    generate_projectile_vfx_chain_script,
    generate_aoe_vfx_script,
    generate_status_effect_vfx_script,
    generate_environmental_vfx_script as generate_deep_environmental_vfx_script,
    generate_directional_hit_vfx_script,
    generate_boss_transition_vfx_script,
)
from veilbreakers_mcp.shared.unity_templates.code_templates import _sanitize_cs_identifier




# ---------------------------------------------------------------------------
# VFX tool -- compound tool covering VFX-01 through VFX-10
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_vfx(
    action: Literal[
        "create_particle_vfx",      # VFX-01: text -> VFX Graph config
        "create_brand_vfx",         # VFX-02: per-brand damage VFX
        "create_environmental_vfx", # VFX-03: dust/fireflies/snow/rain/ash
        "create_trail_vfx",         # VFX-04: weapon/projectile trails
        "create_aura_vfx",          # VFX-05: character aura/buff
        "create_corruption_shader", # VFX-06: corruption scaling shader
        "create_shader",            # VFX-07: dissolve/force field/water/foliage/outline
        "setup_post_processing",    # VFX-08: bloom/color grading/vignette/AO/DOF
        "create_screen_effect",     # VFX-09: camera shake/damage vignette/etc
        "create_ability_vfx",       # VFX-10: ability VFX + animation integration
        "create_flipbook",           # VFX3-01: flipbook texture sheet generation
        "compose_vfx_graph",         # VFX3-02: programmatic VFX Graph composition
        "create_projectile_chain",   # VFX3-03: projectile VFX chain (spawn->travel->impact->aftermath)
        "create_aoe_vfx",            # VFX3-04: area-of-effect VFX
        "create_status_effect_vfx",  # VFX3-05: per-brand status effect VFX
        "create_deep_environmental_vfx",  # VFX3-06: volumetric fog/god rays/heat distortion/caustics
        "create_directional_hit_vfx",     # VFX3-07: directional combat hit VFX
        "create_boss_transition_vfx",     # VFX3-08: boss phase transition VFX
    ],
    # Common params
    name: str = "default",
    # Particle params (VFX-01)
    rate: float = 100,
    lifetime: float = 1.0,
    size: float = 0.5,
    color: list[float] | None = None,
    shape: str = "cone",
    # Brand params (VFX-02)
    brand: str = "IRON",
    # Environment params (VFX-03)
    effect_type: str = "dust",
    # Trail params (VFX-04)
    width: float = 0.5,
    trail_lifetime: float = 0.5,
    # Aura params (VFX-05)
    aura_intensity: float = 1.0,
    aura_radius: float = 1.5,
    # Shader params (VFX-07)
    shader_type: str = "dissolve",
    # Post-processing params (VFX-08)
    bloom_intensity: float = 1.5,
    bloom_threshold: float = 0.9,
    vignette_intensity: float = 0.35,
    ao_intensity: float = 0.5,
    dof_focus_distance: float = 10.0,
    # Screen effect params (VFX-09)
    screen_effect_type: str = "camera_shake",
    shake_intensity: float = 1.0,
    # Ability params (VFX-10)
    vfx_prefab_path: str = "",
    anim_clip_path: str = "",
    keyframe_time: float = 0.0,
    # Flipbook params (VFX3-01)
    rows: int = 4,
    columns: int = 4,
    frame_count: int = 16,
    resolution_per_frame: int = 128,
    flipbook_output_path: str = "Assets/Art/VFX/Flipbooks",
    # VFX Graph composition params (VFX3-02)
    spawn_config: dict | None = None,
    init_config: dict | None = None,
    update_config: dict | None = None,
    output_config: dict | None = None,
    # Projectile chain params (VFX3-03)
    stages: list[dict] | None = None,
    projectile_speed: float = 20.0,
    auto_generate: bool = True,
    # AoE VFX params (VFX3-04)
    aoe_type: str = "ground_circle",
    aoe_radius: float = 5.0,
    aoe_duration: float = 3.0,
    particle_count: int = 200,
    fade_out_time: float = 0.5,
    # Status effect params (VFX3-05)
    vfx_intensity: float = 1.0,
    target_transform_path: str = "",
    # Deep environmental VFX params (VFX3-06)
    deep_vfx_type: str = "volumetric_fog",
    area_size: float = 20.0,
    # Directional hit params (VFX3-07)
    hit_magnitude: float = 1.0,
    screen_effect_enabled: bool = True,
    # Boss transition params (VFX3-08)
    transition_type: str = "corruption_wave",
    boss_brand: str = "DREAD",
    transition_duration: float = 3.0,
    arena_radius: float = 20.0
) -> str:
    """Unity VFX system -- VFX particles, shaders, post-processing, screen effects."""
    try:
        if action == "create_particle_vfx":
            return await _handle_vfx_particle(name, rate, lifetime, size, color, shape)
        elif action == "create_brand_vfx":
            return await _handle_vfx_brand(brand)
        elif action == "create_environmental_vfx":
            return await _handle_vfx_environmental(effect_type)
        elif action == "create_trail_vfx":
            return await _handle_vfx_trail(name, width, color, trail_lifetime)
        elif action == "create_aura_vfx":
            return await _handle_vfx_aura(name, color, aura_intensity, aura_radius)
        elif action == "create_corruption_shader":
            return await _handle_vfx_corruption_shader(name)
        elif action == "create_shader":
            return await _handle_vfx_shader(name, shader_type)
        elif action == "setup_post_processing":
            return await _handle_vfx_post_processing(
                bloom_intensity, bloom_threshold, vignette_intensity,
                ao_intensity, dof_focus_distance,
            )
        elif action == "create_screen_effect":
            return await _handle_vfx_screen_effect(screen_effect_type, shake_intensity)
        elif action == "create_ability_vfx":
            return await _handle_vfx_ability(
                name, vfx_prefab_path, anim_clip_path, keyframe_time
            )
        elif action == "create_flipbook":
            return await _handle_dict_template(
                "create_flipbook",
                generate_flipbook_script(
                    effect_type=effect_type, rows=rows, columns=columns,
                    frame_count=frame_count, resolution_per_frame=resolution_per_frame,
                    output_path=flipbook_output_path,
                ),
            )
        elif action == "compose_vfx_graph":
            return await _handle_dict_template(
                "compose_vfx_graph",
                generate_vfx_graph_composition_script(
                    graph_name=name, spawn_config=spawn_config, init_config=init_config,
                    update_config=update_config, output_config=output_config,
                ),
            )
        elif action == "create_projectile_chain":
            return await _handle_dict_template(
                "create_projectile_chain",
                generate_projectile_vfx_chain_script(
                    projectile_name=name, brand=brand, stages=stages,
                    projectile_speed=projectile_speed, auto_generate=auto_generate,
                ),
            )
        elif action == "create_aoe_vfx":
            return await _handle_dict_template(
                "create_aoe_vfx",
                generate_aoe_vfx_script(
                    aoe_type=aoe_type, brand=brand, radius=aoe_radius,
                    duration=aoe_duration, particle_count=particle_count,
                    fade_out_time=fade_out_time,
                ),
            )
        elif action == "create_status_effect_vfx":
            return await _handle_dict_template(
                "create_status_effect_vfx",
                generate_status_effect_vfx_script(
                    brand=brand, intensity=vfx_intensity,
                    target_transform_path=target_transform_path,
                ),
            )
        elif action == "create_deep_environmental_vfx":
            return await _handle_dict_template(
                "create_deep_environmental_vfx",
                generate_deep_environmental_vfx_script(
                    vfx_type=deep_vfx_type, intensity=vfx_intensity,
                    color=color, area_size=area_size,
                ),
            )
        elif action == "create_directional_hit_vfx":
            return await _handle_dict_template(
                "create_directional_hit_vfx",
                generate_directional_hit_vfx_script(
                    brand=brand, hit_magnitude=hit_magnitude,
                    screen_effect_enabled=screen_effect_enabled,
                ),
            )
        elif action == "create_boss_transition_vfx":
            return await _handle_dict_template(
                "create_boss_transition_vfx",
                generate_boss_transition_vfx_script(
                    transition_type=transition_type, boss_brand=boss_brand,
                    duration=transition_duration, arena_radius=arena_radius,
                ),
            )
        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )
    except Exception as exc:
        logger.exception("unity_vfx action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# VFX action handlers
# ---------------------------------------------------------------------------


async def _handle_vfx_particle(
    name: str, rate: float, lifetime: float, size: float,
    color: list[float] | None, shape: str,
) -> str:
    """Create VFX Graph particle prefab (VFX-01)."""
    script = generate_particle_vfx_script(
        name=name, rate=rate, lifetime=lifetime, size=size, color=color, shape=shape,
    )
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_VFX_{name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_particle_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_particle_vfx",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_brand(brand: str) -> str:
    """Create per-brand damage VFX (VFX-02)."""
    script = generate_brand_vfx_script(brand=brand)
    brand_upper = brand.upper()
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_BrandVFX_{brand_upper}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_brand_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_brand_vfx",
            "brand": brand_upper,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_environmental(effect_type: str) -> str:
    """Create environmental VFX (VFX-03)."""
    script = generate_environmental_vfx_script(effect_type=effect_type)
    safe = effect_type.capitalize()
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_EnvVFX_{safe}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_environmental_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_environmental_vfx",
            "effect_type": effect_type,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_trail(
    name: str, width: float, color: list[float] | None, lifetime: float,
) -> str:
    """Create weapon/projectile trail VFX (VFX-04)."""
    script = generate_trail_vfx_script(
        name=name, width=width, color=color, lifetime=lifetime,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_Trail_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_trail_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_trail_vfx",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_aura(
    name: str, color: list[float] | None, intensity: float, radius: float,
) -> str:
    """Create character aura/buff VFX (VFX-05)."""
    script = generate_aura_vfx_script(
        name=name, color=color, intensity=intensity, radius=radius,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_Aura_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_aura_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_aura_vfx",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_corruption_shader(name: str) -> str:
    """Generate corruption scaling HLSL shader (VFX-06)."""
    shader = generate_corruption_shader()
    safe_name = _sanitize_cs_identifier(name) or "Shader"
    shader_path = f"Assets/Shaders/Generated/{safe_name}_Corruption.shader"

    try:
        abs_path = _write_to_unity(shader, shader_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_corruption_shader", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_corruption_shader",
            "shader_path": abs_path,
            "shader_name": "VeilBreakers/Corruption",
            "properties": [
                "_CorruptionAmount (Range 0-1)",
                "_CorruptionColor",
                "_VeinScale",
            ],
            "next_steps": STANDARD_NEXT_STEPS,
        },
        indent=2,
    )


async def _handle_vfx_shader(name: str, shader_type: str) -> str:
    """Generate HLSL shader by type (VFX-07)."""
    shader_generators = {
        "dissolve": generate_dissolve_shader,
        "force_field": generate_force_field_shader,
        "water": generate_water_shader,
        "foliage": generate_foliage_shader,
        "outline": generate_outline_shader,
        "damage_overlay": generate_damage_overlay_shader,
    }

    if shader_type not in shader_generators:
        return json.dumps({
            "status": "error",
            "action": "create_shader",
            "message": (
                f"Unknown shader_type: '{shader_type}'. "
                f"Valid types: {sorted(shader_generators)}"
            ),
        })

    shader = shader_generators[shader_type]()
    type_label = shader_type.title().replace("_", "")
    safe_name = _sanitize_cs_identifier(name) or "Shader"
    shader_path = f"Assets/Shaders/Generated/{safe_name}_{type_label}.shader"

    try:
        abs_path = _write_to_unity(shader, shader_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_shader", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_shader",
            "shader_type": shader_type,
            "shader_path": abs_path,
            "shader_name": f"VeilBreakers/{type_label}",
            "next_steps": STANDARD_NEXT_STEPS,
        },
        indent=2,
    )


async def _handle_vfx_post_processing(
    bloom_intensity: float,
    bloom_threshold: float,
    vignette_intensity: float,
    ao_intensity: float,
    dof_focus_distance: float,
) -> str:
    """Create post-processing Volume (VFX-08)."""
    script = generate_post_processing_script(
        bloom_intensity=bloom_intensity,
        bloom_threshold=bloom_threshold,
        vignette_intensity=vignette_intensity,
        ao_intensity=ao_intensity,
        dof_focus_distance=dof_focus_distance,
    )
    script_path = "Assets/Editor/Generated/VFX/VeilBreakers_PostProcessing.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_post_processing", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_post_processing",
            "script_path": abs_path,
            "settings": {
                "bloom": bloom_intensity,
                "vignette": vignette_intensity,
                "ao": ao_intensity,
                "dof_focus": dof_focus_distance,
            },
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_screen_effect(effect_type: str, intensity: float) -> str:
    """Create screen effect (VFX-09)."""
    script = generate_screen_effect_script(
        effect_type=effect_type, intensity=intensity,
    )
    safe_type = effect_type.replace("_", " ").title().replace(" ", "")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_ScreenEffect_{safe_type}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_screen_effect", "message": str(exc)}
        )

    label = effect_type.replace("_", " ").title()

    return json.dumps(
        {
            "status": "success",
            "action": "create_screen_effect",
            "effect_type": effect_type,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_ability(
    name: str, vfx_prefab_path: str, anim_clip_path: str, keyframe_time: float,
) -> str:
    """Bind VFX to AnimationEvent for ability effects (VFX-10)."""
    vfx_prefab = vfx_prefab_path or f"Assets/Prefabs/VFX/{name}.prefab"
    anim_clip = anim_clip_path or f"Assets/Animations/{name}.anim"

    script = generate_ability_vfx_script(
        ability_name=name,
        vfx_prefab=vfx_prefab,
        anim_clip=anim_clip,
        keyframe_time=keyframe_time,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_AbilityVFX_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_ability_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_ability_vfx",
            "ability": name,
            "vfx_prefab": vfx_prefab,
            "anim_clip": anim_clip,
            "keyframe_time": keyframe_time,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


