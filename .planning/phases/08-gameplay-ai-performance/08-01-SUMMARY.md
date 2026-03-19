---
phase: 08-gameplay-ai-performance
plan: 01
status: complete
completed: 2026-03-19
tests_passed: 120/120
full_suite: 1668/1668
---

# 08-01 Summary: Gameplay Templates

## What was done

Created `gameplay_templates.py` with 7 C# template generators and 4 pure-logic validators for Unity mob AI systems (MOB-01 through MOB-07). All generators produce runtime MonoBehaviour or ScriptableObject scripts with zero UnityEditor references.

## Artifacts

| File | Lines | Purpose |
|------|-------|---------|
| `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/gameplay_templates.py` | ~580 | 7 generators + 4 validators |
| `Tools/mcp-toolkit/tests/test_gameplay_templates.py` | ~430 | 120 unit tests across 12 test classes |

## Exports

### Generators
- `generate_mob_controller_script(name, detection_range, attack_range, leash_distance, patrol_speed, chase_speed, flee_health_pct)` -- MOB-01: FSM with enum MobState (Patrol/Aggro/Chase/Attack/Flee/ReturnToPatrol), NavMeshAgent, switch(currentState)
- `generate_aggro_system_script(name, detection_range, decay_rate, leash_distance, max_threats)` -- MOB-02: OverlapSphereNonAlloc with pre-allocated Collider[] buffer, Dictionary threat table, 0.2s decay timer, leash ReturnToPatrol
- `generate_patrol_route_script(name, waypoint_count, dwell_time, random_deviation)` -- MOB-03: Transform[] waypoints, per-point dwell times, NavMeshAgent.SetDestination, Random.insideUnitSphere deviation
- `generate_spawn_system_script(name, max_count, respawn_timer, spawn_radius, wave_cooldown, wave_count)` -- MOB-04: [System.Serializable] SpawnWave, coroutine spawning, maxAlive tracking, Random.insideUnitSphere area bounds
- `generate_behavior_tree_script(name, node_types)` -- MOB-05: abstract BT_Node ScriptableObject, Sequence/Selector/Leaf nodes, BehaviorTreeRunner MonoBehaviour, custom leaf scaffolding
- `generate_combat_ability_script(name, damage, cooldown, range, vfx_prefab, sound_name, hitbox_size)` -- MOB-06: [CreateAssetMenu] CombatAbility ScriptableObject, AbilityExecutor MonoBehaviour with Queue cooldown system
- `generate_projectile_script(name, velocity, trajectory, trail_width, impact_vfx, lifetime)` -- MOB-07: TrajectoryType enum (Straight/Arc/Homing), Rigidbody.AddForce for arc, transform.Translate for straight, TrailRenderer, OnTriggerEnter impact VFX

### Validators
- `_validate_mob_params` -- rejects detection_range <= attack_range, zero/negative speeds and ranges
- `_validate_spawn_params` -- rejects max_count <= 0, negative respawn_timer, zero/negative spawn_radius
- `_validate_ability_params` -- rejects negative cooldown or damage
- `_validate_projectile_params` -- rejects zero/negative velocity, invalid trajectory type

## Test Coverage

| Test Class | Tests | Requirement |
|-----------|-------|-------------|
| TestValidateMobParams | 7 | Validators |
| TestValidateSpawnParams | 7 | Validators |
| TestValidateAbilityParams | 5 | Validators |
| TestValidateProjectileParams | 6 | Validators |
| TestMobController | 16 | MOB-01 |
| TestAggroSystem | 14 | MOB-02 |
| TestPatrolRoute | 12 | MOB-03 |
| TestSpawnSystem | 12 | MOB-04 |
| TestBehaviorTree | 13 | MOB-05 |
| TestCombatAbility | 14 | MOB-06 |
| TestProjectileSystem | 14 | MOB-07 |

## Key Design Decisions

- **Runtime only**: All 7 generators produce runtime scripts (MonoBehaviour/ScriptableObject) with no UnityEditor references, unlike editor scripts in scene_templates.py
- **OverlapSphereNonAlloc**: Aggro system uses pre-allocated Collider[] buffer to avoid per-frame GC allocation
- **Decay timer**: Threat decay runs every 0.2s via timer, not every frame, reducing CPU overhead
- **NavMeshAgent only**: All movement uses agent.SetDestination(), never direct transform.position assignment
- **Queue-based cooldown**: AbilityExecutor uses Queue<CombatAbility> for ability queuing with per-ability cooldown tracking
- **Trajectory enum**: Projectile system dispatches on TrajectoryType to Rigidbody physics (Arc) or transform movement (Straight/Homing)
