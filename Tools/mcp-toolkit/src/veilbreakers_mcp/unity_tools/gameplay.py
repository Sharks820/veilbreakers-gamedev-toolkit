"""unity_gameplay tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_mob_controller_script,
    generate_aggro_system_script,
    generate_patrol_route_script,
    generate_spawn_system_script,
    generate_behavior_tree_script,
    generate_combat_ability_script,
    generate_projectile_script,
    _validate_mob_params,
    _validate_spawn_params,
    _validate_ability_params,
    _validate_projectile_params,
)
from veilbreakers_mcp.shared.unity_templates.encounter_templates import (
    generate_encounter_system_script,
    generate_ai_director_script,
    generate_encounter_simulator_script as generate_encounter_sim_script,
    generate_boss_ai_script,
)




# ---------------------------------------------------------------------------
# Gameplay tool -- compound tool covering MOB-01 through MOB-07
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_gameplay(
    action: Literal[
        "create_mob_controller",     # MOB-01: FSM-based mob AI
        "create_aggro_system",       # MOB-02: detection + threat + leash
        "create_patrol_route",       # MOB-03: waypoints + dwell + deviation
        "create_spawn_system",       # MOB-04: spawn points + waves
        "create_behavior_tree",      # MOB-05: ScriptableObject BT scaffolding
        "create_combat_ability",     # MOB-06: ability prefab data + executor
        "create_projectile_system",  # MOB-07: trajectory + trail + impact
        "create_encounter_system",   # AID-01: wave SO + encounter manager
        "create_ai_director",        # AID-02: AnimationCurve difficulty
        "simulate_encounters",       # AID-03: Monte Carlo encounter sim
        "create_boss_ai",            # VB-10: multi-phase boss FSM
    ],
    name: str = "default",
    # Mob controller params (MOB-01, MOB-02)
    detection_range: float = 15.0,
    attack_range: float = 3.0,
    leash_distance: float = 30.0,
    patrol_speed: float = 2.0,
    chase_speed: float = 5.0,
    flee_health_pct: float = 0.2,
    # Aggro params (MOB-02)
    decay_rate: float = 1.0,
    max_threats: int = 5,
    # Patrol params (MOB-03)
    waypoint_count: int = 4,
    dwell_time: float = 2.0,
    random_deviation: float = 1.5,
    # Spawn params (MOB-04)
    max_count: int = 10,
    respawn_timer: float = 30.0,
    spawn_radius: float = 5.0,
    wave_cooldown: float = 10.0,
    wave_count: int = 3,
    # Behavior tree params (MOB-05)
    node_types: list[str] | None = None,
    # Combat ability params (MOB-06)
    damage: float = 25.0,
    cooldown: float = 2.0,
    ability_range: float = 3.0,
    vfx_prefab: str = "",
    sound_name: str = "",
    hitbox_size: float = 1.0,
    # Projectile params (MOB-07)
    velocity: float = 20.0,
    trajectory: str = "straight",
    trail_width: float = 0.3,
    impact_vfx: str = "",
    lifetime: float = 5.0,
    # Boss AI params (VB-10)
    phase_count: int = 3,
    # Common namespace
    namespace: str = ""
) -> str:
    """Unity Gameplay AI -- mob controllers, aggro, patrol, spawning, behavior trees, combat abilities, projectiles, encounters, AI director, boss AI."""
    try:
        if action == "create_mob_controller":
            return await _handle_gameplay_mob_controller(
                name, detection_range, attack_range, leash_distance,
                patrol_speed, chase_speed, flee_health_pct,
            )
        elif action == "create_aggro_system":
            return await _handle_gameplay_aggro_system(
                name, detection_range, decay_rate, leash_distance, max_threats,
            )
        elif action == "create_patrol_route":
            return await _handle_gameplay_patrol_route(
                name, waypoint_count, dwell_time, random_deviation,
            )
        elif action == "create_spawn_system":
            return await _handle_gameplay_spawn_system(
                name, max_count, respawn_timer, spawn_radius, wave_cooldown, wave_count,
            )
        elif action == "create_behavior_tree":
            return await _handle_gameplay_behavior_tree(name, node_types)
        elif action == "create_combat_ability":
            return await _handle_gameplay_combat_ability(
                name, damage, cooldown, ability_range, vfx_prefab, sound_name, hitbox_size,
            )
        elif action == "create_projectile_system":
            return await _handle_gameplay_projectile_system(
                name, velocity, trajectory, trail_width, impact_vfx, lifetime,
            )
        elif action == "create_encounter_system":
            ns_kwargs: dict = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_encounter_system(name, ns_kwargs)
        elif action == "create_ai_director":
            ns_kwargs = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_ai_director(name, ns_kwargs)
        elif action == "simulate_encounters":
            ns_kwargs = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_encounter_simulator(name, ns_kwargs)
        elif action == "create_boss_ai":
            ns_kwargs = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_boss_ai(name, phase_count, ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_gameplay action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Gameplay action handlers
# ---------------------------------------------------------------------------


async def _handle_gameplay_mob_controller(
    name: str,
    detection_range: float,
    attack_range: float,
    leash_distance: float,
    patrol_speed: float,
    chase_speed: float,
    flee_health_pct: float,
) -> str:
    """Create FSM-based mob controller (MOB-01)."""
    error = _validate_mob_params(
        detection_range, attack_range, leash_distance,
        patrol_speed, chase_speed, flee_health_pct,
    )
    if error:
        return json.dumps({"status": "error", "action": "create_mob_controller", "message": error})

    script = generate_mob_controller_script(
        name=name,
        detection_range=detection_range,
        attack_range=attack_range,
        leash_distance=leash_distance,
        patrol_speed=patrol_speed,
        chase_speed=chase_speed,
        flee_health_pct=flee_health_pct,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/AI/VeilBreakers_MobController_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_mob_controller", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_mob_controller",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_aggro_system(
    name: str,
    detection_range: float,
    decay_rate: float,
    leash_distance: float,
    max_threats: int,
) -> str:
    """Create aggro/threat detection system (MOB-02)."""
    script = generate_aggro_system_script(
        name=name,
        detection_range=detection_range,
        decay_rate=decay_rate,
        leash_distance=leash_distance,
        max_threats=max_threats,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/AI/VeilBreakers_AggroSystem_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_aggro_system", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_aggro_system",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_patrol_route(
    name: str,
    waypoint_count: int,
    dwell_time: float,
    random_deviation: float,
) -> str:
    """Create waypoint patrol route (MOB-03)."""
    script = generate_patrol_route_script(
        name=name,
        waypoint_count=waypoint_count,
        dwell_time=dwell_time,
        random_deviation=random_deviation,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/AI/VeilBreakers_PatrolRoute_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_patrol_route", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_patrol_route",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_spawn_system(
    name: str,
    max_count: int,
    respawn_timer: float,
    spawn_radius: float,
    wave_cooldown: float,
    wave_count: int,
) -> str:
    """Create wave-based spawn system (MOB-04)."""
    error = _validate_spawn_params(max_count, respawn_timer, spawn_radius)
    if error:
        return json.dumps({"status": "error", "action": "create_spawn_system", "message": error})

    script = generate_spawn_system_script(
        name=name,
        max_count=max_count,
        respawn_timer=respawn_timer,
        spawn_radius=spawn_radius,
        wave_cooldown=wave_cooldown,
        wave_count=wave_count,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/Spawning/VeilBreakers_SpawnManager_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_spawn_system", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_spawn_system",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_behavior_tree(
    name: str,
    node_types: list[str] | None,
) -> str:
    """Create behavior tree scaffolding (MOB-05)."""
    script = generate_behavior_tree_script(
        name=name,
        node_types=node_types,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/BehaviorTree/VeilBreakers_BehaviorTree_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_behavior_tree", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_behavior_tree",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_combat_ability(
    name: str,
    damage: float,
    cooldown: float,
    ability_range: float,
    vfx_prefab: str,
    sound_name: str,
    hitbox_size: float,
) -> str:
    """Create combat ability data + executor (MOB-06)."""
    error = _validate_ability_params(cooldown, damage)
    if error:
        return json.dumps({"status": "error", "action": "create_combat_ability", "message": error})

    script = generate_combat_ability_script(
        name=name,
        damage=damage,
        cooldown=cooldown,
        ability_range=ability_range,
        vfx_prefab=vfx_prefab,
        sound_name=sound_name,
        hitbox_size=hitbox_size,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/Combat/VeilBreakers_CombatAbility_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_combat_ability", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_combat_ability",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_projectile_system(
    name: str,
    velocity: float,
    trajectory: str,
    trail_width: float,
    impact_vfx: str,
    lifetime: float,
) -> str:
    """Create projectile system (MOB-07)."""
    error = _validate_projectile_params(velocity, trajectory)
    if error:
        return json.dumps({"status": "error", "action": "create_projectile_system", "message": error})

    script = generate_projectile_script(
        name=name,
        velocity=velocity,
        trajectory=trajectory,
        trail_width=trail_width,
        impact_vfx=impact_vfx,
        lifetime=lifetime,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/Combat/VeilBreakers_Projectile_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_projectile_system", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_projectile_system",
            "name": name,
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Encounter action handlers (AID-01, AID-02, AID-03, VB-10)
# ---------------------------------------------------------------------------


async def _handle_gameplay_encounter_system(name: str, ns_kwargs: dict) -> str:
    """Create encounter wave system with SO definitions + manager (AID-01)."""
    wave_so_cs, manager_cs = generate_encounter_system_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    try:
        paths.append(_write_to_unity(
            wave_so_cs, f"Assets/ScriptableObjects/Encounters/VB_WaveData_{safe_name}.cs",
        ))
        paths.append(_write_to_unity(
            manager_cs, f"Assets/Scripts/Runtime/AI/VB_EncounterManager_{safe_name}.cs",
        ))
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_encounter_system", "message": str(exc)}
        )
    return json.dumps({
        "status": "success",
        "action": "create_encounter_system",
        "name": name,
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_gameplay_ai_director(name: str, ns_kwargs: dict) -> str:
    """Create AI director with AnimationCurve-driven difficulty (AID-02)."""
    script = generate_ai_director_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/AI/VB_AIDirector_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_ai_director", "message": str(exc)}
        )
    return json.dumps({
        "status": "success",
        "action": "create_ai_director",
        "name": name,
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_gameplay_encounter_simulator(name: str, ns_kwargs: dict) -> str:
    """Create Monte Carlo encounter simulator EditorWindow (AID-03)."""
    script = generate_encounter_sim_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Tools/VB_EncounterSim_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "simulate_encounters", "message": str(exc)}
        )
    return json.dumps({
        "status": "success",
        "action": "simulate_encounters",
        "name": name,
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_gameplay_boss_ai(name: str, phase_count: int, ns_kwargs: dict) -> str:
    """Create multi-phase boss AI with hierarchical FSM (VB-10)."""
    script = generate_boss_ai_script(name=name, phase_count=phase_count, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/AI/VB_BossAI_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_boss_ai", "message": str(exc)}
        )
    return json.dumps({
        "status": "success",
        "action": "create_boss_ai",
        "name": name,
        "phase_count": phase_count,
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)
