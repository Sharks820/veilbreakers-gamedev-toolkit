"""unity_game tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.game_templates import (
    generate_save_system_script,
    generate_health_system_script,
    generate_character_controller_script,
    generate_input_config_script,
    generate_settings_menu_script,
    generate_http_client_script,
    generate_interactable_script,
)
from veilbreakers_mcp.shared.unity_templates.vb_combat_templates import (
    generate_player_combat_script,
    generate_ability_system_script,
    generate_synergy_engine_script,
    generate_corruption_gameplay_script,
    generate_xp_leveling_script,
    generate_currency_system_script,
    generate_damage_type_script,
)
from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier




@mcp.tool()
async def unity_game(
    action: Literal[
        # Core Game Systems (game_templates.py)
        "create_save_system",          # GAME-01
        "create_health_system",        # GAME-05
        "create_character_controller",  # GAME-06
        "create_input_config",         # GAME-07
        "create_settings_menu",        # GAME-08
        "create_http_client",          # MEDIA-02
        "create_interactable",         # RPG-03
        # VeilBreakers Combat (vb_combat_templates.py)
        "create_player_combat",        # VB-01
        "create_ability_system",       # VB-02
        "create_synergy_engine",       # VB-03
        "create_corruption_gameplay",  # VB-04
        "create_xp_leveling",         # VB-05
        "create_currency_system",      # VB-06
        "create_damage_types",         # VB-07
    ],
    name: str = "default",
    # Save system params (GAME-01)
    slot_count: int = 3,
    use_encryption: bool = True,
    use_compression: bool = True,
    auto_save: bool = True,
    # Health system params (GAME-05)
    max_hp: int = 100,
    use_damage_numbers: bool = True,
    use_respawn: bool = True,
    respawn_delay: float = 3.0,
    # Character controller params (GAME-06)
    mode: str = "third_person",
    move_speed: float = 5.0,
    sprint_multiplier: float = 1.5,
    jump_height: float = 1.5,
    gravity: float = -20.0,
    rotation_speed: float = 10.0,
    # Input params (GAME-07)
    action_maps: list[dict] | None = None,
    include_gamepad: bool = True,
    include_rebinding: bool = True,
    # Settings params (GAME-08)
    categories: list[str] | None = None,
    theme: str = "dark_fantasy",
    # HTTP params (MEDIA-02)
    base_url: str = "",
    max_retries: int = 3,
    timeout_seconds: int = 30,
    # Interactable params (RPG-03)
    interactable_types: list[str] | None = None,
    interaction_radius: float = 2.0,
    use_animation: bool = True,
    use_sound: bool = True,
    # Combat params (VB-01)
    light_combo_count: int = 3,
    heavy_combo_count: int = 2,
    dodge_iframe_duration: float = 0.2,
    dodge_distance: float = 4.0,
    block_stamina_drain: float = 10.0,
    stamina_max: float = 100.0,
    stamina_regen_rate: float = 15.0,
    # Ability params (VB-02)
    max_ability_slots: int = 4,
    mana_max: float = 100.0,
    mana_regen_rate: float = 5.0,
    # Corruption params (VB-04)
    thresholds: list[int] | None = None,
    # XP params (VB-05)
    max_level: int = 50,
    base_xp_per_level: int = 100,
    xp_scaling_factor: float = 1.15,
    # Currency params (VB-06)
    currency_types: list[str] | None = None,
    # Namespace (shared)
    namespace: str = ""
) -> str:
    """Core game systems and VeilBreakers combat -- save/load, health, character controller, input, settings, HTTP client, interactables, player combat, abilities, synergy, corruption, XP/leveling, currency, and damage types."""
    try:
        # Build namespace kwargs -- only pass if non-empty to use generator defaults
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_save_system":
            return await _handle_game_save_system(
                slot_count, use_encryption, use_compression, auto_save, ns_kwargs,
            )
        elif action == "create_health_system":
            return await _handle_game_health_system(
                max_hp, use_damage_numbers, use_respawn, respawn_delay, ns_kwargs,
            )
        elif action == "create_character_controller":
            return await _handle_game_character_controller(
                mode, move_speed, sprint_multiplier, jump_height, gravity,
                rotation_speed, ns_kwargs,
            )
        elif action == "create_input_config":
            return await _handle_game_input_config(
                action_maps, include_gamepad, include_rebinding, ns_kwargs,
            )
        elif action == "create_settings_menu":
            return await _handle_game_settings_menu(categories, theme, ns_kwargs)
        elif action == "create_http_client":
            return await _handle_game_http_client(
                base_url, max_retries, timeout_seconds, ns_kwargs,
            )
        elif action == "create_interactable":
            return await _handle_game_interactable(
                interactable_types, interaction_radius, use_animation, use_sound,
                ns_kwargs,
            )
        elif action == "create_player_combat":
            return await _handle_game_player_combat(
                light_combo_count, heavy_combo_count, dodge_iframe_duration,
                dodge_distance, block_stamina_drain, stamina_max, stamina_regen_rate,
                ns_kwargs=ns_kwargs,
            )
        elif action == "create_ability_system":
            return await _handle_game_ability_system(
                max_ability_slots, mana_max, mana_regen_rate, ns_kwargs,
            )
        elif action == "create_synergy_engine":
            return await _handle_game_synergy_engine(ns_kwargs)
        elif action == "create_corruption_gameplay":
            return await _handle_game_corruption_gameplay(thresholds, ns_kwargs)
        elif action == "create_xp_leveling":
            return await _handle_game_xp_leveling(
                max_level, base_xp_per_level, xp_scaling_factor, ns_kwargs,
            )
        elif action == "create_currency_system":
            return await _handle_game_currency_system(currency_types, ns_kwargs)
        elif action == "create_damage_types":
            return await _handle_game_damage_types(ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_game action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Game action handlers -- Core Game Systems
# ---------------------------------------------------------------------------


async def _handle_game_save_system(
    slot_count: int, use_encryption: bool, use_compression: bool,
    auto_save: bool, ns_kwargs: dict,
) -> str:
    """Create save system (GAME-01)."""
    script = generate_save_system_script(
        slot_count=slot_count,
        use_encryption=use_encryption,
        use_compression=use_compression,
        auto_save=auto_save,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/SaveSystem/SaveSystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_save_system",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_health_system(
    max_hp: int, use_damage_numbers: bool, use_respawn: bool,
    respawn_delay: float, ns_kwargs: dict,
) -> str:
    """Create health system (GAME-05)."""
    script = generate_health_system_script(
        max_hp=max_hp,
        use_damage_numbers=use_damage_numbers,
        use_respawn=use_respawn,
        respawn_delay=respawn_delay,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Health/HealthSystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_health_system",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_character_controller(
    mode: str, move_speed: float, sprint_multiplier: float,
    jump_height: float, gravity: float, rotation_speed: float,
    ns_kwargs: dict,
) -> str:
    """Create character controller (GAME-06)."""
    safe_mode = sanitize_cs_identifier(mode) or "third_person"
    script = generate_character_controller_script(
        mode=safe_mode,
        move_speed=move_speed,
        sprint_multiplier=sprint_multiplier,
        jump_height=jump_height,
        gravity=gravity,
        rotation_speed=rotation_speed,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Character/CharacterController.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_character_controller",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_input_config(
    action_maps: list[dict] | None, include_gamepad: bool,
    include_rebinding: bool, ns_kwargs: dict,
) -> str:
    """Create input config (GAME-07) -- returns tuple (JSON, C#)."""
    json_content, cs_content = generate_input_config_script(
        action_maps=action_maps,
        include_gamepad=include_gamepad,
        include_rebinding=include_rebinding,
        **ns_kwargs,
    )
    # Write .inputactions JSON to Settings folder
    json_path = "Assets/Settings/VeilBreakers.inputactions"
    abs_json = _write_to_unity(json_content, json_path)
    # Write C# wrapper to Runtime
    cs_path = "Assets/Scripts/Runtime/GameSystems/Input/InputConfig.cs"
    abs_cs = _write_to_unity(cs_content, cs_path)
    return json.dumps({
        "status": "success",
        "action": "create_input_config",
        "files": {
            "inputactions": abs_json,
            "csharp": abs_cs,
        },
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_settings_menu(
    categories: list[str] | None, theme: str, ns_kwargs: dict,
) -> str:
    """Create settings menu (GAME-08) -- returns tuple (C#, UXML, USS)."""
    safe_theme = sanitize_cs_identifier(theme) or "dark_fantasy"
    cs_content, uxml_content, uss_content = generate_settings_menu_script(
        categories=categories,
        theme=safe_theme,
        **ns_kwargs,
    )
    # Write C# controller to Runtime
    cs_path = "Assets/Scripts/Runtime/GameSystems/Settings/SettingsMenu.cs"
    abs_cs = _write_to_unity(cs_content, cs_path)
    # Write UXML layout to UI folder
    uxml_path = "Assets/UI/SettingsMenu.uxml"
    abs_uxml = _write_to_unity(uxml_content, uxml_path)
    # Write USS stylesheet to UI folder
    uss_path = "Assets/UI/SettingsMenu.uss"
    abs_uss = _write_to_unity(uss_content, uss_path)
    return json.dumps({
        "status": "success",
        "action": "create_settings_menu",
        "files": {
            "csharp": abs_cs,
            "uxml": abs_uxml,
            "uss": abs_uss,
        },
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_http_client(
    base_url: str, max_retries: int, timeout_seconds: int, ns_kwargs: dict,
) -> str:
    """Create HTTP client (MEDIA-02)."""
    script = generate_http_client_script(
        base_url=base_url,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Network/HttpClient.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_http_client",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_interactable(
    interactable_types: list[str] | None, interaction_radius: float,
    use_animation: bool, use_sound: bool, ns_kwargs: dict,
) -> str:
    """Create interactable system (RPG-03)."""
    script = generate_interactable_script(
        interactable_types=interactable_types,
        interaction_radius=interaction_radius,
        use_animation=use_animation,
        use_sound=use_sound,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Interaction/Interactable.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_interactable",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


# ---------------------------------------------------------------------------
# Game action handlers -- VeilBreakers Combat
# ---------------------------------------------------------------------------


async def _handle_game_player_combat(
    light_combo_count: int, heavy_combo_count: int,
    dodge_iframe_duration: float, dodge_distance: float,
    block_stamina_drain: float, stamina_max: float,
    stamina_regen_rate: float, combat_mode: str = "realtime",
    ns_kwargs: dict | None = None,
) -> str:
    """Create player combat controller (VB-01)."""
    if ns_kwargs is None:
        ns_kwargs = {}
    script = generate_player_combat_script(
        light_combo_count=light_combo_count,
        heavy_combo_count=heavy_combo_count,
        dodge_iframe_duration=dodge_iframe_duration,
        dodge_distance=dodge_distance,
        block_stamina_drain=block_stamina_drain,
        stamina_max=stamina_max,
        stamina_regen_rate=stamina_regen_rate,
        combat_mode=combat_mode,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/Combat/PlayerCombat.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_player_combat",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_ability_system(
    max_ability_slots: int, mana_max: float, mana_regen_rate: float,
    ns_kwargs: dict,
) -> str:
    """Create ability system (VB-02)."""
    script = generate_ability_system_script(
        max_ability_slots=max_ability_slots,
        mana_max=mana_max,
        mana_regen_rate=mana_regen_rate,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/Combat/AbilitySystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_ability_system",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_synergy_engine(ns_kwargs: dict) -> str:
    """Create synergy engine (VB-03)."""
    script = generate_synergy_engine_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Runtime/Combat/SynergyEngine.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_synergy_engine",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_corruption_gameplay(
    thresholds: list[int] | None, ns_kwargs: dict,
) -> str:
    """Create corruption gameplay system (VB-04)."""
    script = generate_corruption_gameplay_script(
        thresholds=thresholds,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/Combat/CorruptionGameplay.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_corruption_gameplay",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_xp_leveling(
    max_level: int, base_xp_per_level: int, xp_scaling_factor: float,
    ns_kwargs: dict,
) -> str:
    """Create XP/leveling system (VB-05)."""
    script = generate_xp_leveling_script(
        max_level=max_level,
        base_xp_per_level=base_xp_per_level,
        xp_scaling_factor=xp_scaling_factor,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Progression/XPLeveling.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_xp_leveling",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_currency_system(
    currency_types: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create currency system (VB-06)."""
    script = generate_currency_system_script(
        currency_types=currency_types,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Progression/CurrencySystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_currency_system",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_game_damage_types(ns_kwargs: dict) -> str:
    """Create damage type system (VB-07)."""
    script = generate_damage_type_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Runtime/Combat/DamageTypes.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_damage_types",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)
