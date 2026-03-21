"""unity_gameplay tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
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
    namespace: str = "",
) -> str:
    """Unity Gameplay AI -- mob controllers, aggro, patrol, spawning, behavior trees, combat abilities, projectiles, encounters, AI director, boss AI.

    This compound tool generates C# runtime scripts for Unity gameplay AI
    systems: FSM mob controllers, aggro/threat detection, waypoint patrol,
    wave-based spawning, behavior trees, combat abilities, projectiles,
    encounter systems, AI director, encounter simulator, and boss AI.

    Actions:
    - create_mob_controller: FSM state machine with Patrol/Chase/Attack/Flee states (MOB-01)
    - create_aggro_system: OverlapSphereNonAlloc threat detection with decay (MOB-02)
    - create_patrol_route: NavMeshAgent waypoint patrol with dwell times (MOB-03)
    - create_spawn_system: Wave-based spawning with max alive tracking (MOB-04)
    - create_behavior_tree: ScriptableObject BT with Sequence/Selector/Leaf nodes (MOB-05)
    - create_combat_ability: Ability ScriptableObject + executor with cooldown queue (MOB-06)
    - create_projectile_system: Straight/arc/homing projectile with trail + impact VFX (MOB-07)
    - create_encounter_system: SO wave definitions + encounter manager MonoBehaviour (AID-01)
    - create_ai_director: AnimationCurve-driven dynamic difficulty adjustment (AID-02)
    - simulate_encounters: Monte Carlo encounter simulator EditorWindow (AID-03)
    - create_boss_ai: Multi-phase hierarchical FSM boss controller (VB-10)

    Args:
        action: The gameplay action to perform.
        name: Name for the generated script/system.
        detection_range: Detection sphere radius (MOB-01, MOB-02).
        attack_range: Attack engagement range (MOB-01).
        leash_distance: Max distance from spawn before returning (MOB-01, MOB-02).
        patrol_speed: NavMeshAgent patrol speed (MOB-01).
        chase_speed: NavMeshAgent chase speed (MOB-01).
        flee_health_pct: Health % threshold to trigger flee (MOB-01).
        decay_rate: Threat decay per tick (MOB-02).
        max_threats: Pre-allocated collider buffer size (MOB-02).
        waypoint_count: Default waypoint slot count (MOB-03).
        dwell_time: Dwell time at each waypoint in seconds (MOB-03).
        random_deviation: Random offset radius per waypoint (MOB-03).
        max_count: Maximum alive spawned instances (MOB-04).
        respawn_timer: Delay before respawn after death (MOB-04).
        spawn_radius: Random spawn position radius (MOB-04).
        wave_cooldown: Delay between spawn waves (MOB-04).
        wave_count: Number of wave slots (MOB-04).
        node_types: Custom leaf node class names to scaffold (MOB-05).
        damage: Base damage value (MOB-06).
        cooldown: Cooldown duration in seconds (MOB-06).
        ability_range: Ability effective range (MOB-06).
        vfx_prefab: VFX prefab name/path (MOB-06).
        sound_name: Audio clip name (MOB-06).
        hitbox_size: Hitbox collider size (MOB-06).
        velocity: Projectile speed (MOB-07).
        trajectory: Trajectory type: straight/arc/homing (MOB-07).
        trail_width: Trail renderer width (MOB-07).
        impact_vfx: Impact VFX prefab name/path (MOB-07).
        lifetime: Projectile auto-destroy time in seconds (MOB-07).
        phase_count: Number of boss phases 2-5 (VB-10).
        namespace: C# namespace override (empty = generator default).
    """
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated BehaviorTreeRunner MonoBehaviour to a GameObject in the scene",
            ],
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated AbilityExecutor MonoBehaviour to a GameObject in the scene",
            ],
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
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Attach the generated Projectile MonoBehaviour to a prefab",
            ],
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
    paths.append(_write_to_unity(
        wave_so_cs, f"Assets/ScriptableObjects/Encounters/VB_WaveData_{safe_name}.cs",
    ))
    paths.append(_write_to_unity(
        manager_cs, f"Assets/Scripts/Runtime/AI/VB_EncounterManager_{safe_name}.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_encounter_system",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the encounter system",
            "Create WaveData ScriptableObject assets and assign to encounter manager",
        ],
    }, indent=2)


async def _handle_gameplay_ai_director(name: str, ns_kwargs: dict) -> str:
    """Create AI director with AnimationCurve-driven difficulty (AID-02)."""
    script = generate_ai_director_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/AI/VB_AIDirector_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_ai_director",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the AI director",
            "Attach VB_AIDirector to a persistent game manager object",
        ],
    }, indent=2)


async def _handle_gameplay_encounter_simulator(name: str, ns_kwargs: dict) -> str:
    """Create Monte Carlo encounter simulator EditorWindow (AID-03)."""
    script = generate_encounter_sim_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Tools/VB_EncounterSim_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "simulate_encounters",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the simulator",
            "Open from VeilBreakers > Tools > Encounter Simulator",
        ],
    }, indent=2)


async def _handle_gameplay_boss_ai(name: str, phase_count: int, ns_kwargs: dict) -> str:
    """Create multi-phase boss AI with hierarchical FSM (VB-10)."""
    script = generate_boss_ai_script(name=name, phase_count=phase_count, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/AI/VB_BossAI_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_boss_ai",
        "name": name,
        "phase_count": phase_count,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the boss AI",
            "Attach VB_BossAI to the boss prefab root",
        ],
    }, indent=2)
