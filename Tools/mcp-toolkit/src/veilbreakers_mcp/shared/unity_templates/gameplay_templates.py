"""Gameplay C# template generators for Unity mob AI systems.

Each function returns a complete C# source string for a runtime
MonoBehaviour or ScriptableObject script. These are placed in the Unity
project's Assets/Scripts/Runtime/ directory -- they are NOT editor scripts
and must NEVER reference the UnityEditor namespace.

Exports:
    generate_mob_controller_script              -- MOB-01: FSM state machine controller
    generate_aggro_system_script                -- MOB-02: OverlapSphereNonAlloc detection
    generate_patrol_route_script                -- MOB-03: NavMeshAgent waypoint patrol
    generate_spawn_system_script                -- MOB-04: Wave spawning with area bounds
    generate_behavior_tree_script               -- MOB-05: ScriptableObject behavior tree
    generate_combat_ability_script              -- MOB-06: Ability prefab + executor
    generate_projectile_script                  -- MOB-07: Trajectory + trail + impact
    generate_tactical_ai_coordinator_script     -- TAC-01: Multi-mob tactical coordination
    generate_boss_phase_controller_script       -- TAC-02: Multi-phase boss encounters
    generate_player_combat_controller_script    -- TAC-03: Player combat (stamina/poise/parry)
    generate_motion_warping_script              -- CMB-01: FromSoftware-style motion warping
    generate_attack_telegraph_script            -- CMB-02: Attack telegraph system
    generate_status_effect_system_script        -- SFX-01: Runtime status effect / buff-debuff system

Validators:
    _validate_mob_params               -- detection/attack range, speeds
    _validate_spawn_params             -- max count, respawn timer, radius
    _validate_ability_params           -- cooldown, damage
    _validate_projectile_params        -- velocity, trajectory type
    _validate_tactical_params          -- max attackers, coordination radius
    _validate_boss_phase_params        -- phase thresholds
    _validate_player_combat_params     -- stamina, poise, parry window
    _validate_motion_warping_params    -- warp distance, angle, window
    _validate_attack_telegraph_params  -- telegraph type, duration, radius
    _validate_status_effect_params     -- duration, tick interval, max stacks
"""

from __future__ import annotations

import re
from typing import Optional

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _validate_mob_params(
    detection_range: float,
    attack_range: float,
    leash_distance: float,
    patrol_speed: float,
    chase_speed: float,
    flee_health_pct: float,
) -> Optional[str]:
    """Validate mob controller parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if detection_range <= 0:
        return "detection_range must be > 0"
    if attack_range <= 0:
        return "attack_range must be > 0"
    if leash_distance <= 0:
        return "leash_distance must be > 0"
    if patrol_speed <= 0:
        return "patrol_speed must be > 0"
    if chase_speed <= 0:
        return "chase_speed must be > 0"
    if detection_range <= attack_range:
        return "detection_range must be greater than attack_range"
    if not (0 <= flee_health_pct <= 1):
        return "flee_health_pct must be between 0 and 1"
    return None


def _validate_spawn_params(
    max_count: int,
    respawn_timer: float,
    spawn_radius: float,
) -> Optional[str]:
    """Validate spawn system parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if max_count <= 0:
        return "max_count must be > 0"
    if respawn_timer < 0:
        return "respawn_timer must be >= 0"
    if spawn_radius <= 0:
        return "spawn_radius must be > 0"
    return None


def _validate_ability_params(
    cooldown: float,
    damage: float,
) -> Optional[str]:
    """Validate combat ability parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if cooldown < 0:
        return "cooldown must be >= 0"
    if damage < 0:
        return "damage must be >= 0"
    return None


def _validate_projectile_params(
    velocity: float,
    trajectory: str,
) -> Optional[str]:
    """Validate projectile parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if velocity <= 0:
        return "velocity must be > 0"
    if trajectory not in ("straight", "arc", "homing"):
        return f"trajectory must be one of: straight, arc, homing (got '{trajectory}')"
    return None


# ---------------------------------------------------------------------------
# MOB-01: Mob controller (FSM state machine)
# ---------------------------------------------------------------------------


def generate_mob_controller_script(
    name: str,
    detection_range: float = 15.0,
    attack_range: float = 3.0,
    leash_distance: float = 30.0,
    patrol_speed: float = 2.0,
    chase_speed: float = 5.0,
    flee_health_pct: float = 0.2,
) -> str:
    """Generate C# runtime MonoBehaviour for a mob controller with FSM.

    Produces a state machine with Patrol, Aggro, Chase, Attack, Flee, and
    ReturnToPatrol states. Uses NavMeshAgent for all movement.

    Args:
        name: Mob type name (sanitized for C# identifier).
        detection_range: Range at which mob detects the player.
        attack_range: Range at which mob can attack.
        leash_distance: Max distance from spawn before returning.
        patrol_speed: NavMeshAgent speed during patrol.
        chase_speed: NavMeshAgent speed during chase.
        flee_health_pct: Health percentage threshold to trigger flee.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using UnityEngine.AI;

/// <summary>
/// FSM-based mob controller for {sanitize_cs_string(name)}.
/// States: Patrol, Aggro, Chase, Attack, Flee, ReturnToPatrol.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>
public class VeilBreakers_MobController_{safe_name} : MonoBehaviour
{{
    public enum MobState {{ Patrol, Aggro, Chase, Attack, Flee, ReturnToPatrol }}

    [Header("Detection")]
    public float detectionRange = {detection_range}f;
    public float attackRange = {attack_range}f;
    public float leashDistance = {leash_distance}f;

    [Header("Movement")]
    public float patrolSpeed = {patrol_speed}f;
    public float chaseSpeed = {chase_speed}f;

    [Header("Combat")]
    public float fleeHealthPercent = {flee_health_pct}f;
    public float currentHealth = 100f;
    public float maxHealth = 100f;

    private NavMeshAgent agent;
    private MobState currentState = MobState.Patrol;
    private Transform playerTransform;
    private Vector3 spawnPosition;

    private void Start()
    {{
        agent = GetComponent<NavMeshAgent>();
        spawnPosition = transform.position;
        agent.speed = patrolSpeed;

        // Find player by tag
        var player = GameObject.FindGameObjectWithTag("Player");
        if (player != null)
            playerTransform = player.transform;
    }}

    private void Update()
    {{
        if (playerTransform == null) return;

        float sqrDistToPlayer = (transform.position - playerTransform.position).sqrMagnitude;
        float sqrDistToSpawn = (transform.position - spawnPosition).sqrMagnitude;
        float healthPct = currentHealth / maxHealth;

        float sqrDetection = detectionRange * detectionRange;
        float sqrAttack = attackRange * attackRange;
        float sqrLeash = leashDistance * leashDistance;

        switch (currentState)
        {{
            case MobState.Patrol:
                agent.speed = patrolSpeed;
                if (sqrDistToPlayer <= sqrDetection)
                    currentState = MobState.Aggro;
                break;

            case MobState.Aggro:
                if (sqrDistToSpawn > sqrLeash)
                {{
                    currentState = MobState.ReturnToPatrol;
                    break;
                }}
                currentState = MobState.Chase;
                break;

            case MobState.Chase:
                agent.speed = chaseSpeed;
                agent.SetDestination(playerTransform.position);
                if (sqrDistToSpawn > sqrLeash)
                {{
                    currentState = MobState.ReturnToPatrol;
                    break;
                }}
                if (healthPct <= fleeHealthPercent)
                {{
                    currentState = MobState.Flee;
                    break;
                }}
                if (sqrDistToPlayer <= sqrAttack)
                    currentState = MobState.Attack;
                else if (sqrDistToPlayer > sqrDetection)
                    currentState = MobState.ReturnToPatrol;
                break;

            case MobState.Attack:
                agent.SetDestination(transform.position); // Stop moving
                if (healthPct <= fleeHealthPercent)
                {{
                    currentState = MobState.Flee;
                    break;
                }}
                if (sqrDistToPlayer > sqrAttack)
                    currentState = MobState.Chase;
                if (sqrDistToSpawn > sqrLeash)
                    currentState = MobState.ReturnToPatrol;
                break;

            case MobState.Flee:
                agent.speed = chaseSpeed;
                Vector3 fleeDir = (transform.position - playerTransform.position).normalized;
                agent.SetDestination(transform.position + fleeDir * detectionRange);
                if (sqrDistToSpawn > sqrLeash)
                    currentState = MobState.ReturnToPatrol;
                break;

            case MobState.ReturnToPatrol:
                agent.speed = patrolSpeed;
                agent.SetDestination(spawnPosition);
                if ((transform.position - spawnPosition).sqrMagnitude < 1.5f * 1.5f)
                    currentState = MobState.Patrol;
                break;
        }}
    }}

    public void TakeDamage(float amount)
    {{
        currentHealth -= amount;
        if (currentHealth <= 0)
        {{
            currentHealth = 0;
            OnDeath();
        }}
    }}

    private void OnDeath()
    {{
        Destroy(gameObject);
    }}
}}
'''


# ---------------------------------------------------------------------------
# MOB-02: Aggro system (detection + threat + leash)
# ---------------------------------------------------------------------------


def generate_aggro_system_script(
    name: str,
    detection_range: float = 15.0,
    decay_rate: float = 1.0,
    leash_distance: float = 30.0,
    max_threats: int = 10,
) -> str:
    """Generate C# runtime MonoBehaviour for an aggro / threat system.

    Uses OverlapSphereNonAlloc with a pre-allocated Collider buffer to
    detect targets without per-frame GC allocation. Maintains a threat
    table with decay on a timer (every 0.2s, not every frame).

    Args:
        name: System name (sanitized for C# identifier).
        detection_range: Sphere overlap radius for target detection.
        decay_rate: Threat points removed per decay tick.
        leash_distance: Distance from spawn that forces ReturnToPatrol.
        max_threats: Size of the pre-allocated Collider buffer.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Aggro / threat detection system for {sanitize_cs_string(name)}.
/// Uses OverlapSphereNonAlloc for zero-allocation detection.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>
public class VeilBreakers_AggroSystem_{safe_name} : MonoBehaviour
{{
    [Header("Detection")]
    public float detectionRange = {detection_range}f;
    public LayerMask targetLayer;
    public float decayRate = {decay_rate}f;
    public float leashDistance = {leash_distance}f;

    [Header("State")]
    public bool isAggro = false;

    private Collider[] overlapBuffer = new Collider[{max_threats}];
    private Dictionary<Transform, float> threatTable = new Dictionary<Transform, float>();
    private Vector3 spawnPosition;
    private float decayTimer = 0f;
    private const float DECAY_INTERVAL = 0.2f;

    private void Start()
    {{
        spawnPosition = transform.position;
    }}

    private void Update()
    {{
        // Leash check: force ReturnToPatrol if too far from spawn
        float distToSpawn = Vector3.Distance(transform.position, spawnPosition);
        if (distToSpawn > leashDistance)
        {{
            ReturnToPatrol();
            return;
        }}

        // Detection via OverlapSphereNonAlloc (zero allocation)
        int hitCount = Physics.OverlapSphereNonAlloc(
            transform.position, detectionRange, overlapBuffer, targetLayer
        );

        for (int i = 0; i < hitCount; i++)
        {{
            if (overlapBuffer[i] == null) continue;
            Transform target = overlapBuffer[i].transform;
            if (!threatTable.ContainsKey(target))
                threatTable[target] = 0f;
            threatTable[target] += Time.deltaTime * 10f;
        }}

        // Threat decay on timer (not every frame)
        decayTimer += Time.deltaTime;
        if (decayTimer >= DECAY_INTERVAL)
        {{
            decayTimer = 0f;
            DecayThreats();
        }}

        // Update aggro state
        isAggro = threatTable.Count > 0 && GetHighestThreat() != null;
    }}

    private void DecayThreats()
    {{
        var toRemove = new List<Transform>();
        var keys = new List<Transform>(threatTable.Keys);
        foreach (var key in keys)
        {{
            threatTable[key] -= decayRate * DECAY_INTERVAL;
            if (threatTable[key] <= 0f)
                toRemove.Add(key);
        }}
        foreach (var key in toRemove)
            threatTable.Remove(key);
    }}

    /// <summary>
    /// Returns the transform with the highest threat value, or null.
    /// </summary>
    public Transform GetHighestThreat()
    {{
        Transform highest = null;
        float maxThreat = 0f;
        foreach (var kvp in threatTable)
        {{
            if (kvp.Value > maxThreat)
            {{
                maxThreat = kvp.Value;
                highest = kvp.Key;
            }}
        }}
        return highest;
    }}

    /// <summary>
    /// Add threat from an external source (e.g. taking damage).
    /// </summary>
    public void AddThreat(Transform source, float amount)
    {{
        if (!threatTable.ContainsKey(source))
            threatTable[source] = 0f;
        threatTable[source] += amount;
    }}

    /// <summary>
    /// Clear all threat and return to patrol behavior.
    /// </summary>
    public void ReturnToPatrol()
    {{
        threatTable.Clear();
        isAggro = false;
    }}

    private void OnDrawGizmosSelected()
    {{
        Gizmos.color = Color.red;
        Gizmos.DrawWireSphere(transform.position, detectionRange);
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(
            Application.isPlaying ? spawnPosition : transform.position,
            leashDistance
        );
    }}
}}
'''


# ---------------------------------------------------------------------------
# MOB-03: Patrol route (waypoints + dwell + deviation)
# ---------------------------------------------------------------------------


def generate_patrol_route_script(
    name: str,
    waypoint_count: int = 4,
    dwell_time: float = 2.0,
    random_deviation: float = 1.0,
) -> str:
    """Generate C# runtime MonoBehaviour for waypoint patrol.

    Uses NavMeshAgent.SetDestination for movement with configurable
    per-point dwell times and random deviation offsets.

    Args:
        name: Patrol route name (sanitized for C# identifier).
        waypoint_count: Default number of waypoint slots.
        dwell_time: Default dwell time at each waypoint (seconds).
        random_deviation: Random offset radius applied to each waypoint.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using UnityEngine.AI;

/// <summary>
/// Waypoint patrol route for {sanitize_cs_string(name)}.
/// NavMeshAgent-based with dwell times and random deviation.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>
public class VeilBreakers_PatrolRoute_{safe_name} : MonoBehaviour
{{
    [Header("Waypoints")]
    public Transform[] waypoints = new Transform[{waypoint_count}];
    public float defaultDwellTime = {dwell_time}f;
    public float[] dwellTimes;
    public float randomDeviation = {random_deviation}f;

    private NavMeshAgent agent;
    private int currentWaypointIndex = 0;
    private float dwellTimer = 0f;
    private bool isWaiting = false;

    private void Start()
    {{
        agent = GetComponent<NavMeshAgent>();

        // Initialize dwell times if not set
        if (dwellTimes == null || dwellTimes.Length != waypoints.Length)
        {{
            dwellTimes = new float[waypoints.Length];
            for (int i = 0; i < dwellTimes.Length; i++)
                dwellTimes[i] = defaultDwellTime;
        }}

        MoveToNextWaypoint();
    }}

    private void Update()
    {{
        if (waypoints.Length == 0) return;

        if (isWaiting)
        {{
            dwellTimer -= Time.deltaTime;
            if (dwellTimer <= 0f)
            {{
                isWaiting = false;
                currentWaypointIndex = (currentWaypointIndex + 1) % waypoints.Length;
                MoveToNextWaypoint();
            }}
            return;
        }}

        // Check if we've reached the current waypoint
        if (!agent.pathPending && agent.remainingDistance <= agent.stoppingDistance + 0.1f)
        {{
            isWaiting = true;
            dwellTimer = dwellTimes[currentWaypointIndex];
        }}
    }}

    private void MoveToNextWaypoint()
    {{
        if (waypoints.Length == 0 || waypoints[currentWaypointIndex] == null) return;

        Vector3 destination = waypoints[currentWaypointIndex].position;

        // Apply random deviation offset
        if (randomDeviation > 0f)
        {{
            Vector3 offset = Random.insideUnitSphere * randomDeviation;
            offset.y = 0f; // Keep on ground plane
            destination += offset;
        }}

        agent.SetDestination(destination);
    }}

    private void OnDrawGizmosSelected()
    {{
        if (waypoints == null) return;
        Gizmos.color = Color.cyan;
        for (int i = 0; i < waypoints.Length; i++)
        {{
            if (waypoints[i] == null) continue;
            Gizmos.DrawSphere(waypoints[i].position, 0.3f);
            if (i < waypoints.Length - 1 && waypoints[i + 1] != null)
                Gizmos.DrawLine(waypoints[i].position, waypoints[i + 1].position);
        }}
        // Close the loop
        if (waypoints.Length > 1 && waypoints[0] != null && waypoints[waypoints.Length - 1] != null)
            Gizmos.DrawLine(waypoints[waypoints.Length - 1].position, waypoints[0].position);
    }}
}}
'''


# ---------------------------------------------------------------------------
# MOB-04: Spawn system (waves + area bounds)
# ---------------------------------------------------------------------------


def generate_spawn_system_script(
    name: str,
    max_count: int = 10,
    respawn_timer: float = 5.0,
    spawn_radius: float = 10.0,
    wave_cooldown: float = 15.0,
    wave_count: int = 3,
) -> str:
    """Generate C# runtime MonoBehaviour for wave-based spawn system.

    Features SpawnWave serializable class, coroutine-based spawning,
    max alive tracking, respawn timer, and area bounds via
    Random.insideUnitSphere.

    Args:
        name: Spawn system name (sanitized for C# identifier).
        max_count: Maximum number of alive spawned instances.
        respawn_timer: Delay before respawning after death.
        spawn_radius: Radius for random spawn position offset.
        wave_cooldown: Delay between waves.
        wave_count: Number of wave slots.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Wave-based spawn system for {sanitize_cs_string(name)}.
/// Supports max alive count, respawn timer, and area bounds.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>
public class VeilBreakers_SpawnSystem_{safe_name} : MonoBehaviour
{{
    [System.Serializable]
    public class SpawnWave
    {{
        public GameObject[] prefabs;
        public int count = {wave_count};
        public float delayBetweenSpawns = 0.5f;
    }}

    [Header("Waves")]
    public SpawnWave[] waves;
    public float waveCooldown = {wave_cooldown}f;

    [Header("Spawn Settings")]
    public int maxAlive = {max_count};
    public float respawnTimer = {respawn_timer}f;
    public float spawnRadius = {spawn_radius}f;

    private List<GameObject> aliveInstances = new List<GameObject>();
    private int currentWave = 0;
    private bool isSpawning = false;

    private void Start()
    {{
        if (waves != null && waves.Length > 0)
            StartCoroutine(SpawnWaveCoroutine());
    }}

    private IEnumerator SpawnWaveCoroutine()
    {{
        while (currentWave < waves.Length)
        {{
            isSpawning = true;
            var wave = waves[currentWave];

            for (int i = 0; i < wave.count; i++)
            {{
                // Wait for slot to open
                while (GetAliveCount() >= maxAlive)
                    yield return new WaitForSeconds(0.5f);

                if (wave.prefabs != null && wave.prefabs.Length > 0)
                {{
                    GameObject prefab = wave.prefabs[Random.Range(0, wave.prefabs.Length)];
                    if (prefab != null)
                    {{
                        Vector3 spawnPos = transform.position + Random.insideUnitSphere * spawnRadius;
                        spawnPos.y = transform.position.y;
                        // Raycast down to find actual ground position
                        if (Physics.Raycast(spawnPos + Vector3.up * 50f, Vector3.down, out RaycastHit groundHit, 100f))
                            spawnPos.y = groundHit.point.y;
                        GameObject instance = Instantiate(prefab, spawnPos, Quaternion.identity);
                        aliveInstances.Add(instance);
                    }}
                }}

                yield return new WaitForSeconds(wave.delayBetweenSpawns);
            }}

            currentWave++;
            isSpawning = false;

            if (currentWave < waves.Length)
                yield return new WaitForSeconds(waveCooldown);
        }}
    }}

    private int GetAliveCount()
    {{
        aliveInstances.RemoveAll(obj => obj == null);
        return aliveInstances.Count;
    }}

    /// <summary>
    /// Trigger respawn after an entity dies.
    /// </summary>
    public void OnEntityDeath(GameObject entity)
    {{
        aliveInstances.Remove(entity);
        if (respawnTimer > 0f)
            StartCoroutine(RespawnCoroutine());
    }}

    private IEnumerator RespawnCoroutine()
    {{
        yield return new WaitForSeconds(respawnTimer);

        if (GetAliveCount() < maxAlive && waves != null && waves.Length > 0)
        {{
            var wave = waves[Mathf.Min(currentWave, waves.Length - 1)];
            if (wave.prefabs != null && wave.prefabs.Length > 0)
            {{
                GameObject prefab = wave.prefabs[Random.Range(0, wave.prefabs.Length)];
                if (prefab != null)
                {{
                    Vector3 spawnPos = transform.position + Random.insideUnitSphere * spawnRadius;
                    spawnPos.y = transform.position.y;
                    // Raycast down to find actual ground position
                    if (Physics.Raycast(spawnPos + Vector3.up * 50f, Vector3.down, out RaycastHit groundHit, 100f))
                        spawnPos.y = groundHit.point.y;
                    GameObject instance = Instantiate(prefab, spawnPos, Quaternion.identity);
                    aliveInstances.Add(instance);
                }}
            }}
        }}
    }}

    private void OnDrawGizmosSelected()
    {{
        Gizmos.color = Color.green;
        Gizmos.DrawWireSphere(transform.position, spawnRadius);
    }}
}}
'''


# ---------------------------------------------------------------------------
# MOB-05: Behavior tree (ScriptableObject nodes + runner)
# ---------------------------------------------------------------------------


def generate_behavior_tree_script(
    name: str,
    node_types: list[str] | None = None,
) -> str:
    """Generate C# for a behavior tree system with ScriptableObject nodes.

    Produces an abstract BT_Node base class (ScriptableObject), concrete
    Sequence, Selector, and Leaf node types, and a BehaviorTreeRunner
    MonoBehaviour that ticks the root node.

    Args:
        name: Behavior tree name (sanitized for C# identifier).
        node_types: Optional list of custom leaf node class names to scaffold.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)
    node_types = node_types or []

    custom_nodes = ""
    for nt in node_types:
        safe_nt = sanitize_cs_identifier(nt)
        custom_nodes += f'''

/// <summary>Custom leaf node: {sanitize_cs_string(nt)}</summary>
[CreateAssetMenu(menuName = "VeilBreakers/BehaviorTree/{safe_name}/{safe_nt}")]
public class BT_{safe_nt}_{safe_name} : BT_Leaf_{safe_name}
{{
    public override NodeState_{safe_name} Evaluate(BehaviorTreeRunner_{safe_name} runner)
    {{
        // TODO: Implement {safe_nt} logic
        Debug.Log("[BT] {safe_nt} executing");
        return NodeState_{safe_name}.Success;
    }}
}}
'''

    return f'''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Behavior tree system for {sanitize_cs_string(name)}.
/// Abstract BT_Node ScriptableObject base with Sequence, Selector, Leaf nodes.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>

// ---------------------------------------------------------------------------
// Node state enum
// ---------------------------------------------------------------------------
public enum NodeState_{safe_name} {{ Running, Success, Failure }}

// ---------------------------------------------------------------------------
// Abstract base node (ScriptableObject)
// ---------------------------------------------------------------------------
public abstract class BT_Node_{safe_name} : ScriptableObject
{{
    public string nodeName;

    public abstract NodeState_{safe_name} Evaluate(BehaviorTreeRunner_{safe_name} runner);
}}

// ---------------------------------------------------------------------------
// Sequence node: succeeds only if ALL children succeed (left to right)
// ---------------------------------------------------------------------------
[CreateAssetMenu(menuName = "VeilBreakers/BehaviorTree/{safe_name}/Sequence")]
public class BT_Sequence_{safe_name} : BT_Node_{safe_name}
{{
    public List<BT_Node_{safe_name}> children = new List<BT_Node_{safe_name}>();

    public override NodeState_{safe_name} Evaluate(BehaviorTreeRunner_{safe_name} runner)
    {{
        foreach (var child in children)
        {{
            var result = child.Evaluate(runner);
            if (result == NodeState_{safe_name}.Failure)
                return NodeState_{safe_name}.Failure;
            if (result == NodeState_{safe_name}.Running)
                return NodeState_{safe_name}.Running;
        }}
        return NodeState_{safe_name}.Success;
    }}
}}

// ---------------------------------------------------------------------------
// Selector node: succeeds if ANY child succeeds (first match)
// ---------------------------------------------------------------------------
[CreateAssetMenu(menuName = "VeilBreakers/BehaviorTree/{safe_name}/Selector")]
public class BT_Selector_{safe_name} : BT_Node_{safe_name}
{{
    public List<BT_Node_{safe_name}> children = new List<BT_Node_{safe_name}>();

    public override NodeState_{safe_name} Evaluate(BehaviorTreeRunner_{safe_name} runner)
    {{
        foreach (var child in children)
        {{
            var result = child.Evaluate(runner);
            if (result == NodeState_{safe_name}.Success)
                return NodeState_{safe_name}.Success;
            if (result == NodeState_{safe_name}.Running)
                return NodeState_{safe_name}.Running;
        }}
        return NodeState_{safe_name}.Failure;
    }}
}}

// ---------------------------------------------------------------------------
// Abstract Leaf node: override Evaluate with custom logic
// ---------------------------------------------------------------------------
public abstract class BT_Leaf_{safe_name} : BT_Node_{safe_name}
{{
    // Subclasses implement Evaluate() with specific behavior
}}
{custom_nodes}
// ---------------------------------------------------------------------------
// BehaviorTreeRunner: MonoBehaviour that ticks the root node each frame
// ---------------------------------------------------------------------------
public class BehaviorTreeRunner_{safe_name} : MonoBehaviour
{{
    [Header("Tree Configuration")]
    public BT_Node_{safe_name} rootNode;

    [Header("Runtime State")]
    public Transform targetTransform;

    private void Update()
    {{
        if (rootNode != null)
        {{
            rootNode.Evaluate(this);
        }}
    }}

    /// <summary>
    /// Replace the root node at runtime.
    /// </summary>
    public void SetRootNode(BT_Node_{safe_name} newRoot)
    {{
        rootNode = newRoot;
    }}
}}
'''


# ---------------------------------------------------------------------------
# MOB-06: Combat ability (ScriptableObject + executor)
# ---------------------------------------------------------------------------


def generate_combat_ability_script(
    name: str,
    damage: float = 25.0,
    cooldown: float = 1.5,
    ability_range: float = 5.0,
    vfx_prefab: str = "",
    sound_name: str = "",
    hitbox_size: float = 1.0,
) -> str:
    """Generate C# for a combat ability data class and executor.

    Produces a CombatAbility ScriptableObject (data) with CreateAssetMenu
    and an AbilityExecutor MonoBehaviour with a Queue-based cooldown system.

    Args:
        name: Ability name (sanitized for C# identifier).
        damage: Base damage value.
        cooldown: Cooldown duration in seconds.
        ability_range: Ability effective range.
        vfx_prefab: Name/path of VFX prefab to instantiate.
        sound_name: Audio clip name to play on use.
        hitbox_size: Size of the hitbox collider.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)
    safe_vfx = sanitize_cs_string(vfx_prefab)
    safe_sound = sanitize_cs_string(sound_name)

    return f'''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Combat ability system for {sanitize_cs_string(name)}.
/// CombatAbility ScriptableObject + AbilityExecutor MonoBehaviour.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>

// ---------------------------------------------------------------------------
// IDamageable interface for type-safe damage delivery
// ---------------------------------------------------------------------------
public interface IDamageable_{safe_name}
{{
    void TakeDamage(float amount);
}}

// ---------------------------------------------------------------------------
// CombatAbility: ScriptableObject data container
// ---------------------------------------------------------------------------
[CreateAssetMenu(menuName = "VeilBreakers/Combat/Ability/{safe_name}")]
public class CombatAbility_{safe_name} : ScriptableObject
{{
    [Header("Damage")]
    public float damage = {damage}f;
    public float hitboxSize = {hitbox_size}f;
    public float range = {ability_range}f;

    [Header("Timing")]
    public float cooldown = {cooldown}f;

    [Header("Animation")]
    public string animTrigger = "Attack_{safe_name}";

    [Header("Effects")]
    public GameObject vfxPrefab;
    public string vfxPrefabName = "{safe_vfx}";
    public string soundName = "{safe_sound}";
}}

// ---------------------------------------------------------------------------
// AbilityExecutor: MonoBehaviour with cooldown queue
// ---------------------------------------------------------------------------
public class AbilityExecutor_{safe_name} : MonoBehaviour
{{
    [Header("Abilities")]
    public List<CombatAbility_{safe_name}> abilities = new List<CombatAbility_{safe_name}>();

    private Queue<CombatAbility_{safe_name}> abilityQueue = new Queue<CombatAbility_{safe_name}>();
    private Dictionary<CombatAbility_{safe_name}, float> cooldownTimers = new Dictionary<CombatAbility_{safe_name}, float>();
    private Collider[] hitBuffer = new Collider[32];
    private Animator animator;
    private AudioSource audioSource;

    private void Start()
    {{
        animator = GetComponent<Animator>();
        audioSource = GetComponent<AudioSource>();
    }}

    private void Update()
    {{
        // Update cooldown timers
        var keys = new List<CombatAbility_{safe_name}>(cooldownTimers.Keys);
        foreach (var ability in keys)
        {{
            cooldownTimers[ability] -= Time.deltaTime;
            if (cooldownTimers[ability] <= 0f)
                cooldownTimers.Remove(ability);
        }}

        // Process queued abilities
        if (abilityQueue.Count > 0)
        {{
            var next = abilityQueue.Peek();
            if (!cooldownTimers.ContainsKey(next))
            {{
                abilityQueue.Dequeue();
                ExecuteAbility(next);
            }}
        }}
    }}

    /// <summary>
    /// Queue an ability for execution. Will fire when off cooldown.
    /// </summary>
    public void QueueAbility(CombatAbility_{safe_name} ability)
    {{
        abilityQueue.Enqueue(ability);
    }}

    /// <summary>
    /// Try to use an ability immediately. Returns false if on cooldown.
    /// </summary>
    public bool TryUseAbility(CombatAbility_{safe_name} ability)
    {{
        if (cooldownTimers.ContainsKey(ability))
            return false;
        ExecuteAbility(ability);
        return true;
    }}

    private void ExecuteAbility(CombatAbility_{safe_name} ability)
    {{
        // Start cooldown
        cooldownTimers[ability] = ability.cooldown;

        // Animation trigger
        if (animator != null && !string.IsNullOrEmpty(ability.animTrigger))
            animator.SetTrigger(ability.animTrigger);

        // VFX
        if (ability.vfxPrefab != null)
            Instantiate(ability.vfxPrefab, transform.position, transform.rotation);

        // Sound
        if (audioSource != null && !string.IsNullOrEmpty(ability.soundName))
            audioSource.Play();

        // Hitbox damage check (zero-allocation)
        int hitCount = Physics.OverlapSphereNonAlloc(transform.position, ability.hitboxSize, hitBuffer);
        for (int i = 0; i < hitCount; i++)
        {{
            if (hitBuffer[i] == null || hitBuffer[i].gameObject == gameObject) continue;
            var damageable = hitBuffer[i].GetComponent<IDamageable_{safe_name}>();
            if (damageable != null)
                damageable.TakeDamage(ability.damage);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# MOB-07: Projectile system (trajectory + trail + impact)
# ---------------------------------------------------------------------------


def generate_projectile_script(
    name: str,
    velocity: float = 20.0,
    trajectory: str = "straight",
    trail_width: float = 0.1,
    impact_vfx: str = "",
    lifetime: float = 5.0,
) -> str:
    """Generate C# runtime MonoBehaviour for a projectile system.

    Supports three trajectory types: Straight (transform.Translate),
    Arc (Rigidbody.AddForce), and Homing (steering towards target).
    Includes TrailRenderer reference and impact VFX spawning on
    OnTriggerEnter.

    Args:
        name: Projectile name (sanitized for C# identifier).
        velocity: Projectile speed.
        trajectory: One of "straight", "arc", "homing".
        trail_width: Width of the TrailRenderer.
        impact_vfx: Name/path of impact VFX prefab.
        lifetime: Seconds before auto-destroy.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)
    safe_impact = sanitize_cs_string(impact_vfx)

    trajectory_enum_value = {
        "straight": "Straight",
        "arc": "Arc",
        "homing": "Homing",
    }.get(trajectory, "Straight")

    return f'''using UnityEngine;

/// <summary>
/// Projectile system for {sanitize_cs_string(name)}.
/// Trajectory: {trajectory_enum_value}. Trail + impact VFX.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>

// ---------------------------------------------------------------------------
// IDamageable interface for type-safe damage delivery
// ---------------------------------------------------------------------------
public interface IDamageable_{safe_name}
{{
    void TakeDamage(float amount);
}}

public class VeilBreakers_Projectile_{safe_name} : MonoBehaviour
{{
    public enum TrajectoryType {{ Straight, Arc, Homing }}

    [Header("Trajectory")]
    public TrajectoryType trajectoryType = TrajectoryType.{trajectory_enum_value};
    public float velocity = {velocity}f;
    public float lifetime = {lifetime}f;

    [Header("Trail")]
    public TrailRenderer trailRenderer;
    public float trailWidth = {trail_width}f;

    [Header("Impact")]
    public GameObject impactVFXPrefab;
    public string impactVFXName = "{safe_impact}";

    [Header("Homing")]
    public Transform homingTarget;
    public float homingTurnSpeed = 5f;

    [Header("Arc")]
    public float arcAngle = 45f;

    private Rigidbody rb;
    private float spawnTime;

    private void Start()
    {{
        spawnTime = Time.time;
        rb = GetComponent<Rigidbody>();

        // Setup trail
        if (trailRenderer != null)
        {{
            trailRenderer.startWidth = trailWidth;
            trailRenderer.endWidth = trailWidth * 0.1f;
        }}

        // Launch based on trajectory type
        switch (trajectoryType)
        {{
            case TrajectoryType.Straight:
                // Straight projectiles use transform.Translate in Update
                if (rb != null) rb.isKinematic = true;
                break;

            case TrajectoryType.Arc:
                // Arc projectiles use Rigidbody physics
                if (rb == null) rb = gameObject.AddComponent<Rigidbody>();
                rb.useGravity = true;
                float rad = arcAngle * Mathf.Deg2Rad;
                Vector3 launchVelocity = transform.forward * velocity * Mathf.Cos(rad)
                                        + Vector3.up * velocity * Mathf.Sin(rad);
                rb.AddForce(launchVelocity, ForceMode.VelocityChange);
                break;

            case TrajectoryType.Homing:
                // Homing uses transform steering in Update
                if (rb != null) rb.isKinematic = true;
                break;
        }}

        // Auto-destroy after lifetime
        Destroy(gameObject, lifetime);
    }}

    private void Update()
    {{
        switch (trajectoryType)
        {{
            case TrajectoryType.Straight:
                transform.Translate(Vector3.forward * velocity * Time.deltaTime);
                break;

            case TrajectoryType.Homing:
                if (homingTarget != null)
                {{
                    Vector3 direction = (homingTarget.position - transform.position).normalized;
                    Quaternion targetRotation = Quaternion.LookRotation(direction);
                    transform.rotation = Quaternion.Slerp(
                        transform.rotation, targetRotation, homingTurnSpeed * Time.deltaTime
                    );
                }}
                transform.Translate(Vector3.forward * velocity * Time.deltaTime);
                break;

            case TrajectoryType.Arc:
                // Physics handles movement via Rigidbody
                break;
        }}
    }}

    private void OnTriggerEnter(Collider other)
    {{
        // Spawn impact VFX
        if (impactVFXPrefab != null)
            Instantiate(impactVFXPrefab, transform.position, Quaternion.identity);

        // Deliver damage via IDamageable interface
        var damageable = other.GetComponent<IDamageable_{safe_name}>();
        if (damageable != null)
            damageable.TakeDamage(velocity);

        // Destroy projectile
        Destroy(gameObject);
    }}
}}
'''


# ---------------------------------------------------------------------------
# Validator: motion warping params
# ---------------------------------------------------------------------------


def _validate_motion_warping_params(
    max_warp_distance: float,
    max_warp_angle: float,
    warp_window_start: float,
    warp_window_end: float,
) -> Optional[str]:
    """Validate motion warping parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if max_warp_distance <= 0:
        return "max_warp_distance must be > 0"
    if max_warp_angle <= 0:
        return "max_warp_angle must be > 0"
    if max_warp_angle > 180:
        return "max_warp_angle must be <= 180"
    if not (0.0 <= warp_window_start < 1.0):
        return "warp_window_start must be in [0.0, 1.0)"
    if not (0.0 < warp_window_end <= 1.0):
        return "warp_window_end must be in (0.0, 1.0]"
    if warp_window_start >= warp_window_end:
        return "warp_window_start must be less than warp_window_end"
    return None


# ---------------------------------------------------------------------------
# Validator: attack telegraph params
# ---------------------------------------------------------------------------


def _validate_attack_telegraph_params(
    telegraph_type: str,
    duration: float,
    radius: float,
) -> Optional[str]:
    """Validate attack telegraph parameters.

    Returns None if valid, or an error string describing the problem.
    """
    valid_types = ("GROUND_CIRCLE", "GROUND_CONE", "GROUND_LINE", "WEAPON_GLOW")
    if telegraph_type not in valid_types:
        return (
            f"telegraph_type must be one of: {', '.join(valid_types)} "
            f"(got '{telegraph_type}')"
        )
    if duration <= 0:
        return "duration must be > 0"
    if radius <= 0:
        return "radius must be > 0"
    return None


# ---------------------------------------------------------------------------
# CMB-01: Motion warping (FromSoftware-style attack alignment)
# ---------------------------------------------------------------------------


def generate_motion_warping_script(
    name: str,
    max_warp_distance: float = 3.0,
    max_warp_angle: float = 45.0,
    warp_window_start: float = 0.0,
    warp_window_end: float = 0.3,
) -> str:
    """Generate C# runtime MonoBehaviour for motion warping.

    FromSoftware-style system that dynamically adjusts root motion during
    attack wind-up to align the attacker toward the locked-on target.
    Prevents "ice skating" by magnetically snapping attacks toward their
    intended target during a configurable animation window.

    Uses Vector3.MoveTowards and Quaternion.RotateTowards for smooth
    warping. Integrates with NavMeshAgent (if present). Includes an
    Animator StateMachineBehaviour for tagging warp-enabled states.

    Args:
        name: System name (sanitized for C# identifier).
        max_warp_distance: Maximum distance (meters) the warp can cover.
        max_warp_angle: Maximum rotation (degrees) the warp can apply.
        warp_window_start: Normalized animation time when warp begins.
        warp_window_end: Normalized animation time when warp ends.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using UnityEngine.AI;

namespace VeilBreakers.Gameplay
{{
    /// <summary>
    /// FromSoftware-style motion warping for {sanitize_cs_string(name)}.
    /// Dynamically aligns attacker toward locked-on target during wind-up.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    public class VB_MotionWarping_{safe_name} : MonoBehaviour
    {{
        [Header("Warp Settings")]
        [Tooltip("Maximum distance the warp can cover (meters).")]
        public float maxWarpDistance = {max_warp_distance}f;

        [Tooltip("Maximum rotation the warp can apply (degrees).")]
        public float maxWarpAngle = {max_warp_angle}f;

        [Header("Warp Window (normalized animation time)")]
        [Range(0f, 1f)]
        public float warpWindowStart = {warp_window_start}f;

        [Range(0f, 1f)]
        public float warpWindowEnd = {warp_window_end}f;

        [Header("Easing")]
        [Tooltip("Curve controlling warp intensity over the window.")]
        public AnimationCurve warpCurve = AnimationCurve.EaseInOut(0f, 0f, 1f, 1f);

        [Header("Target")]
        [Tooltip("Assign lock-on target at runtime.")]
        public Transform warpTarget;

        private Animator animator;
        private NavMeshAgent navAgent;
        private bool isWarping;
        private Vector3 warpStartPosition;
        private Quaternion warpStartRotation;

        private void Start()
        {{
            animator = GetComponent<Animator>();
            navAgent = GetComponent<NavMeshAgent>();
        }}

        private void Update()
        {{
            if (!isWarping || warpTarget == null || animator == null)
                return;

            AnimatorStateInfo stateInfo = animator.GetCurrentAnimatorStateInfo(0);
            float normalizedTime = stateInfo.normalizedTime % 1f;

            // Only warp inside the designated window
            if (normalizedTime < warpWindowStart || normalizedTime > warpWindowEnd)
            {{
                if (normalizedTime > warpWindowEnd)
                    StopWarping();
                return;
            }}

            // Calculate progress within warp window [0..1]
            float windowProgress = Mathf.InverseLerp(warpWindowStart, warpWindowEnd, normalizedTime);
            float curveValue = warpCurve.Evaluate(windowProgress);

            Vector3 toTarget = warpTarget.position - transform.position;
            toTarget.y = 0f; // Keep on ground plane
            float distanceToTarget = toTarget.magnitude;

            // Abort warp if target is too far
            if (distanceToTarget > maxWarpDistance * 2f)
            {{
                StopWarping();
                return;
            }}

            // -- Rotation warp --
            if (distanceToTarget > 0.01f)
            {{
                Quaternion targetRotation = Quaternion.LookRotation(toTarget.normalized);
                float maxAngleStep = maxWarpAngle * curveValue * Time.deltaTime * 10f;
                transform.rotation = Quaternion.RotateTowards(
                    transform.rotation, targetRotation, maxAngleStep
                );
            }}

            // -- Translation warp --
            if (distanceToTarget > 0.1f && distanceToTarget <= maxWarpDistance)
            {{
                float moveStep = maxWarpDistance * curveValue * Time.deltaTime * 5f;
                Vector3 newPosition = Vector3.MoveTowards(
                    transform.position, warpTarget.position, moveStep
                );
                newPosition.y = transform.position.y; // Maintain Y

                if (navAgent != null && navAgent.enabled)
                {{
                    navAgent.Warp(newPosition);
                }}
                else
                {{
                    transform.position = newPosition;
                }}
            }}
        }}

        /// <summary>
        /// Begin warping toward the current warpTarget.
        /// Call this from animation event or state machine behaviour.
        /// </summary>
        public void BeginWarping()
        {{
            if (warpTarget == null) return;

            float dist = Vector3.Distance(transform.position, warpTarget.position);
            if (dist > maxWarpDistance)
                return;

            isWarping = true;
            warpStartPosition = transform.position;
            warpStartRotation = transform.rotation;

            // Disable NavMeshAgent obstacle avoidance during warp
            if (navAgent != null && navAgent.enabled)
                navAgent.obstacleAvoidanceType = ObstacleAvoidanceType.NoObstacleAvoidance;
        }}

        /// <summary>
        /// Stop warping and restore normal movement.
        /// </summary>
        public void StopWarping()
        {{
            isWarping = false;

            // Restore NavMeshAgent obstacle avoidance
            if (navAgent != null && navAgent.enabled)
                navAgent.obstacleAvoidanceType = ObstacleAvoidanceType.HighQualityObstacleAvoidance;
        }}

        /// <summary>
        /// Set the lock-on target for warping.
        /// </summary>
        public void SetTarget(Transform target)
        {{
            warpTarget = target;
        }}
    }}

    /// <summary>
    /// Animator StateMachineBehaviour that triggers motion warping
    /// on tagged animation states. Attach to attack states in Animator.
    /// </summary>
    public class VB_MotionWarpState_{safe_name} : StateMachineBehaviour
    {{
        public override void OnStateEnter(Animator animator, AnimatorStateInfo stateInfo, int layerIndex)
        {{
            var warping = animator.GetComponent<VB_MotionWarping_{safe_name}>();
            if (warping != null)
                warping.BeginWarping();
        }}

        public override void OnStateExit(Animator animator, AnimatorStateInfo stateInfo, int layerIndex)
        {{
            var warping = animator.GetComponent<VB_MotionWarping_{safe_name}>();
            if (warping != null)
                warping.StopWarping();
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# CMB-02: Attack telegraph system (Elden Ring / Monster Hunter style)
# ---------------------------------------------------------------------------


def generate_attack_telegraph_script(
    name: str,
    default_duration: float = 1.0,
    default_radius: float = 3.0,
    telegraph_type: str = "GROUND_CIRCLE",
) -> str:
    """Generate C# runtime MonoBehaviour for attack telegraph system.

    Fair combat telegraph system (Elden Ring / Monster Hunter style) that
    spawns visual warnings before enemy attacks land. Supports ground
    circle (AoE), ground cone (sweep), ground line (charge), and weapon
    glow (melee swing) telegraph types.

    Uses URP Decal Projector references for ground effects and
    MaterialPropertyBlock for weapon glow emission. Duration synced to
    attack wind-up via AnimationEvent callbacks. Includes fade-in and
    impact flash animations. Can be disabled via difficulty settings.

    Args:
        name: System name (sanitized for C# identifier).
        default_duration: Default telegraph duration in seconds.
        default_radius: Default telegraph radius/length.
        telegraph_type: Default type (GROUND_CIRCLE, GROUND_CONE,
            GROUND_LINE, WEAPON_GLOW).

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    type_enum_value = {
        "GROUND_CIRCLE": "GroundCircle",
        "GROUND_CONE": "GroundCone",
        "GROUND_LINE": "GroundLine",
        "WEAPON_GLOW": "WeaponGlow",
    }.get(telegraph_type, "GroundCircle")

    return f'''using UnityEngine;
using System.Collections;

namespace VeilBreakers.Gameplay
{{
    /// <summary>
    /// Telegraph data for a single attack warning.
    /// </summary>
    [System.Serializable]
    public struct TelegraphData_{safe_name}
    {{
        public TelegraphType_{safe_name} type;
        public float radius;
        public float length;
        public float duration;
        public Color color;
        public float delay;
    }}

    /// <summary>
    /// Telegraph type enum.
    /// </summary>
    public enum TelegraphType_{safe_name}
    {{
        GroundCircle,
        GroundCone,
        GroundLine,
        WeaponGlow
    }}

    /// <summary>
    /// Attack telegraph system for {sanitize_cs_string(name)}.
    /// Spawns visual warnings before enemy attacks land.
    /// Elden Ring / Monster Hunter style fair combat indicators.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    public class VB_AttackTelegraph_{safe_name} : MonoBehaviour
    {{
        [Header("Default Settings")]
        public TelegraphType_{safe_name} defaultType = TelegraphType_{safe_name}.{type_enum_value};
        public float defaultDuration = {default_duration}f;
        public float defaultRadius = {default_radius}f;

        [Header("Color Coding")]
        [Tooltip("Damage zone color (default red).")]
        public Color damageColor = new Color(1f, 0f, 0f, 0.6f);

        [Tooltip("Warning color (default orange).")]
        public Color warningColor = new Color(1f, 0.5f, 0f, 0.5f);

        [Tooltip("Parry timing window color (default yellow).")]
        public Color parryWindowColor = new Color(1f, 1f, 0f, 0.7f);

        [Header("Weapon Glow")]
        [Tooltip("Renderer on the weapon mesh for glow effect.")]
        public Renderer weaponRenderer;

        [Tooltip("Emission color for weapon glow.")]
        public Color weaponGlowColor = new Color(1f, 0.3f, 0f, 1f);

        [Tooltip("Emission intensity multiplier.")]
        public float glowIntensity = 5f;

        [Header("Ground Telegraph Prefabs")]
        [Tooltip("Prefab with DecalProjector for circle telegraph.")]
        public GameObject circleDecalPrefab;

        [Tooltip("Prefab with DecalProjector for cone telegraph.")]
        public GameObject coneDecalPrefab;

        [Tooltip("Prefab with LineRenderer for line telegraph.")]
        public GameObject lineRendererPrefab;

        [Header("Impact Flash")]
        [Tooltip("Duration of the bright flash at impact moment.")]
        public float flashDuration = 0.1f;

        [Tooltip("Flash brightness multiplier.")]
        public float flashBrightness = 3f;

        [Header("Difficulty")]
        [Tooltip("Set to false to disable all telegraphs (hard mode).")]
        public bool telegraphsEnabled = true;

        private MaterialPropertyBlock weaponMPB;
        private static readonly int EmissionColorID = Shader.PropertyToID("_EmissionColor");

        private void Start()
        {{
            weaponMPB = new MaterialPropertyBlock();
        }}

        // ---------------------------------------------------------------
        // Public API: called from AnimationEvents or AI scripts
        // ---------------------------------------------------------------

        /// <summary>
        /// Spawn a telegraph using a TelegraphData struct.
        /// </summary>
        public void ShowTelegraph(TelegraphData_{safe_name} data)
        {{
            if (!telegraphsEnabled) return;

            switch (data.type)
            {{
                case TelegraphType_{safe_name}.GroundCircle:
                    StartCoroutine(GroundCircleRoutine(
                        data.radius, data.duration, data.color, data.delay));
                    break;

                case TelegraphType_{safe_name}.GroundCone:
                    StartCoroutine(GroundConeRoutine(
                        data.radius, data.length, data.duration, data.color, data.delay));
                    break;

                case TelegraphType_{safe_name}.GroundLine:
                    StartCoroutine(GroundLineRoutine(
                        data.length, data.duration, data.color, data.delay));
                    break;

                case TelegraphType_{safe_name}.WeaponGlow:
                    StartCoroutine(WeaponGlowRoutine(
                        data.duration, data.color, data.delay));
                    break;
            }}
        }}

        /// <summary>
        /// Convenience: spawn default circle telegraph at this transform.
        /// Suitable for AnimationEvent callback (no parameters needed).
        /// </summary>
        public void ShowDefaultTelegraph()
        {{
            var data = new TelegraphData_{safe_name}
            {{
                type = defaultType,
                radius = defaultRadius,
                length = defaultRadius * 2f,
                duration = defaultDuration,
                color = damageColor,
                delay = 0f
            }};
            ShowTelegraph(data);
        }}

        // ---------------------------------------------------------------
        // Coroutine implementations
        // ---------------------------------------------------------------

        private IEnumerator GroundCircleRoutine(
            float radius, float duration, Color color, float delay)
        {{
            if (delay > 0f) yield return new WaitForSeconds(delay);

            GameObject decal = null;
            if (circleDecalPrefab != null)
            {{
                decal = Instantiate(circleDecalPrefab, transform.position, Quaternion.identity);
                decal.transform.localScale = Vector3.zero;
            }}

            float elapsed = 0f;
            while (elapsed < duration)
            {{
                elapsed += Time.deltaTime;
                float t = elapsed / duration;

                // Fade in: scale up and increase opacity
                if (decal != null)
                {{
                    float scale = Mathf.Lerp(0f, radius * 2f, t);
                    decal.transform.localScale = new Vector3(scale, scale, scale);

                    var rend = decal.GetComponentInChildren<Renderer>();
                    if (rend != null)
                    {{
                        Color c = color;
                        c.a = Mathf.Lerp(0f, color.a, t);
                        var mpb = new MaterialPropertyBlock();
                        rend.GetPropertyBlock(mpb);
                        mpb.SetColor("_BaseColor", c);
                        rend.SetPropertyBlock(mpb);
                    }}
                }}

                yield return null;
            }}

            // Impact flash
            yield return ImpactFlash(decal);

            if (decal != null) Destroy(decal);
        }}

        private IEnumerator GroundConeRoutine(
            float radius, float length, float duration, Color color, float delay)
        {{
            if (delay > 0f) yield return new WaitForSeconds(delay);

            GameObject decal = null;
            if (coneDecalPrefab != null)
            {{
                decal = Instantiate(coneDecalPrefab, transform.position, transform.rotation);
                decal.transform.localScale = Vector3.zero;
            }}

            float elapsed = 0f;
            while (elapsed < duration)
            {{
                elapsed += Time.deltaTime;
                float t = elapsed / duration;

                if (decal != null)
                {{
                    float scaleX = Mathf.Lerp(0f, radius * 2f, t);
                    float scaleZ = Mathf.Lerp(0f, length, t);
                    decal.transform.localScale = new Vector3(scaleX, 1f, scaleZ);

                    var rend = decal.GetComponentInChildren<Renderer>();
                    if (rend != null)
                    {{
                        Color c = color;
                        c.a = Mathf.Lerp(0f, color.a, t);
                        var mpb = new MaterialPropertyBlock();
                        rend.GetPropertyBlock(mpb);
                        mpb.SetColor("_BaseColor", c);
                        rend.SetPropertyBlock(mpb);
                    }}
                }}

                yield return null;
            }}

            yield return ImpactFlash(decal);
            if (decal != null) Destroy(decal);
        }}

        private IEnumerator GroundLineRoutine(
            float length, float duration, Color color, float delay)
        {{
            if (delay > 0f) yield return new WaitForSeconds(delay);

            GameObject lineObj = null;
            LineRenderer lr = null;
            if (lineRendererPrefab != null)
            {{
                lineObj = Instantiate(lineRendererPrefab, transform.position, transform.rotation);
                lr = lineObj.GetComponent<LineRenderer>();
            }}

            float elapsed = 0f;
            while (elapsed < duration)
            {{
                elapsed += Time.deltaTime;
                float t = elapsed / duration;

                if (lr != null)
                {{
                    float currentLength = Mathf.Lerp(0f, length, t);
                    lr.SetPosition(0, transform.position);
                    lr.SetPosition(1, transform.position + transform.forward * currentLength);

                    Color c = color;
                    c.a = Mathf.Lerp(0f, color.a, t);
                    lr.startColor = c;
                    lr.endColor = c;
                }}

                yield return null;
            }}

            // Flash
            if (lr != null)
            {{
                Color flash = color * flashBrightness;
                flash.a = 1f;
                lr.startColor = flash;
                lr.endColor = flash;
                yield return new WaitForSeconds(flashDuration);
            }}

            if (lineObj != null) Destroy(lineObj);
        }}

        private IEnumerator WeaponGlowRoutine(
            float duration, Color color, float delay)
        {{
            if (delay > 0f) yield return new WaitForSeconds(delay);

            if (weaponRenderer == null) yield break;

            Color glowColor = color.linear * glowIntensity;

            float elapsed = 0f;
            while (elapsed < duration)
            {{
                elapsed += Time.deltaTime;
                float t = elapsed / duration;

                // Fade in emission
                Color current = Color.Lerp(Color.black, glowColor, t);
                weaponRenderer.GetPropertyBlock(weaponMPB);
                weaponMPB.SetColor(EmissionColorID, current);
                weaponRenderer.SetPropertyBlock(weaponMPB);

                yield return null;
            }}

            // Impact flash: brief bright pulse
            weaponRenderer.GetPropertyBlock(weaponMPB);
            weaponMPB.SetColor(EmissionColorID, glowColor * flashBrightness);
            weaponRenderer.SetPropertyBlock(weaponMPB);
            yield return new WaitForSeconds(flashDuration);

            // Reset emission
            weaponRenderer.GetPropertyBlock(weaponMPB);
            weaponMPB.SetColor(EmissionColorID, Color.black);
            weaponRenderer.SetPropertyBlock(weaponMPB);
        }}

        // ---------------------------------------------------------------
        // Impact flash helper
        // ---------------------------------------------------------------

        private IEnumerator ImpactFlash(GameObject decal)
        {{
            if (decal == null) yield break;

            var rend = decal.GetComponentInChildren<Renderer>();
            if (rend != null)
            {{
                var mpb = new MaterialPropertyBlock();
                rend.GetPropertyBlock(mpb);
                Color flash = Color.white * flashBrightness;
                flash.a = 1f;
                mpb.SetColor("_BaseColor", flash);
                rend.SetPropertyBlock(mpb);
            }}

            // Scale pulse
            Vector3 originalScale = decal.transform.localScale;
            decal.transform.localScale = originalScale * 1.2f;
            yield return new WaitForSeconds(flashDuration);
            decal.transform.localScale = originalScale;
        }}

        private void OnDrawGizmosSelected()
        {{
            Gizmos.color = damageColor;
            switch (defaultType)
            {{
                case TelegraphType_{safe_name}.GroundCircle:
                    Gizmos.DrawWireSphere(transform.position, defaultRadius);
                    break;

                case TelegraphType_{safe_name}.GroundCone:
                    Vector3 forward = transform.forward * defaultRadius * 2f;
                    Vector3 right = transform.right * defaultRadius;
                    Gizmos.DrawLine(transform.position, transform.position + forward + right);
                    Gizmos.DrawLine(transform.position, transform.position + forward - right);
                    Gizmos.DrawLine(
                        transform.position + forward + right,
                        transform.position + forward - right);
                    break;

                case TelegraphType_{safe_name}.GroundLine:
                    Gizmos.DrawLine(
                        transform.position,
                        transform.position + transform.forward * defaultRadius * 2f);
                    break;

                case TelegraphType_{safe_name}.WeaponGlow:
                    Gizmos.DrawWireCube(transform.position, Vector3.one * 0.5f);
                    break;
            }}
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# Validators for tactical AI systems
# ---------------------------------------------------------------------------


def _validate_tactical_params(
    max_simultaneous_attackers: int,
    coordination_radius: float,
) -> Optional[str]:
    """Validate tactical AI coordinator parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if max_simultaneous_attackers <= 0:
        return "max_simultaneous_attackers must be > 0"
    if coordination_radius <= 0:
        return "coordination_radius must be > 0"
    return None


def _validate_boss_phase_params(
    phase_thresholds: list[float],
) -> Optional[str]:
    """Validate boss phase controller parameters.

    Phase thresholds must be descending values between 0 and 1 exclusive.
    Returns None if valid, or an error string describing the problem.
    """
    if not phase_thresholds:
        return "phase_thresholds must not be empty"
    for i, t in enumerate(phase_thresholds):
        if not (0 < t < 1):
            return f"phase_thresholds[{i}] must be between 0 and 1 exclusive (got {t})"
    for i in range(len(phase_thresholds) - 1):
        if phase_thresholds[i] <= phase_thresholds[i + 1]:
            return "phase_thresholds must be in strictly descending order"
    return None


def _validate_player_combat_params(
    stamina_max: float,
    poise_max: float,
    parry_window: float,
) -> Optional[str]:
    """Validate player combat controller parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if stamina_max <= 0:
        return "stamina_max must be > 0"
    if poise_max <= 0:
        return "poise_max must be > 0"
    if parry_window <= 0:
        return "parry_window must be > 0"
    if parry_window > 1.0:
        return "parry_window must be <= 1.0 seconds"
    return None


# ---------------------------------------------------------------------------
# TAC-01: Tactical AI coordinator (Elden Ring-style group combat)
# ---------------------------------------------------------------------------


def generate_tactical_ai_coordinator_script(
    name: str,
    max_simultaneous_attackers: int = 2,
    coordination_radius: float = 25.0,
    token_cooldown: float = 1.5,
    flank_radius: float = 5.0,
    reposition_speed: float = 3.0,
    max_managed_mobs: int = 16,
) -> str:
    """Generate C# runtime MonoBehaviour for multi-mob tactical AI coordination.

    Produces an Elden Ring-style group combat coordinator that manages
    attack tokens, flanking assignments, role-based behavior (aggressive,
    support, circler, waiting), and dynamic re-assignment on mob death
    or player movement. Uses OverlapSphereNonAlloc for efficient mob
    discovery with zero per-frame GC allocation.

    Args:
        name: Coordinator name (sanitized for C# identifier).
        max_simultaneous_attackers: Maximum mobs attacking simultaneously.
        coordination_radius: Radius for discovering managed mobs.
        token_cooldown: Seconds before a returned token can be re-issued.
        flank_radius: Circle radius for flanking positions around player.
        reposition_speed: NavMeshAgent speed for circling/repositioning mobs.
        max_managed_mobs: Size of the pre-allocated Collider buffer.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using UnityEngine.AI;
using System.Collections.Generic;

namespace VeilBreakers.Gameplay
{{
    /// <summary>
    /// Tactical AI coordinator for {sanitize_cs_string(name)}.
    /// Manages group combat with attack tokens, flanking, and role assignment.
    /// Prevents mob pile-on by limiting simultaneous attackers.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    public class TacticalCoordinator_{safe_name} : MonoBehaviour
    {{
        /// <summary>Combat role assigned to each managed mob.</summary>
        public enum MobRole {{ Aggressive, Support, Circler, Waiting }}

        /// <summary>Tracked state for each mob in the coordination group.</summary>
        [System.Serializable]
        public class MobEntry
        {{
            public GameObject mob;
            public MobRole role;
            public float tokenCooldownRemaining;
            public int flankSlot;
            public bool hasAttackToken;
        }}

        [Header("Coordination")]
        public int maxSimultaneousAttackers = {max_simultaneous_attackers};
        public float coordinationRadius = {coordination_radius}f;
        public float tokenCooldown = {token_cooldown}f;
        public LayerMask mobLayer;

        [Header("Flanking")]
        public float flankRadius = {flank_radius}f;
        public float repositionSpeed = {reposition_speed}f;

        [Header("Runtime State")]
        public Transform playerTransform;
        public List<MobEntry> managedMobs = new List<MobEntry>();

        private Collider[] overlapBuffer = new Collider[{max_managed_mobs}];
        private int activeTokenCount = 0;
        private float discoveryTimer = 0f;
        private const float DISCOVERY_INTERVAL = 0.5f;
        private const int FLANK_SLOTS = 8;

        private void Start()
        {{
            var player = GameObject.FindGameObjectWithTag("Player");
            if (player != null)
                playerTransform = player.transform;
        }}

        private void Update()
        {{
            if (playerTransform == null) return;

            // Periodic mob discovery (not every frame)
            discoveryTimer += Time.deltaTime;
            if (discoveryTimer >= DISCOVERY_INTERVAL)
            {{
                discoveryTimer = 0f;
                DiscoverMobs();
            }}

            // Clean up dead mobs
            CleanupDeadMobs();

            // Update token cooldowns
            UpdateTokenCooldowns();

            // Assign roles based on token availability
            AssignRoles();

            // Direct mob behavior based on role
            DirectMobs();
        }}

        /// <summary>
        /// Discover nearby mobs using OverlapSphereNonAlloc (zero-allocation).
        /// </summary>
        private void DiscoverMobs()
        {{
            int hitCount = Physics.OverlapSphereNonAlloc(
                transform.position, coordinationRadius, overlapBuffer, mobLayer
            );

            for (int i = 0; i < hitCount; i++)
            {{
                if (overlapBuffer[i] == null) continue;
                GameObject mob = overlapBuffer[i].gameObject;

                // Check if already managed
                bool alreadyManaged = false;
                for (int j = 0; j < managedMobs.Count; j++)
                {{
                    if (managedMobs[j].mob == mob)
                    {{
                        alreadyManaged = true;
                        break;
                    }}
                }}

                if (!alreadyManaged)
                {{
                    managedMobs.Add(new MobEntry
                    {{
                        mob = mob,
                        role = MobRole.Waiting,
                        tokenCooldownRemaining = 0f,
                        flankSlot = AssignFlankSlot(),
                        hasAttackToken = false
                    }});
                }}
            }}
        }}

        /// <summary>
        /// Remove entries for destroyed or null mobs and reclaim their tokens.
        /// </summary>
        private void CleanupDeadMobs()
        {{
            for (int i = managedMobs.Count - 1; i >= 0; i--)
            {{
                if (managedMobs[i].mob == null)
                {{
                    if (managedMobs[i].hasAttackToken)
                        activeTokenCount--;
                    managedMobs.RemoveAt(i);
                }}
            }}
        }}

        /// <summary>
        /// Tick down token cooldowns for mobs that recently returned a token.
        /// </summary>
        private void UpdateTokenCooldowns()
        {{
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                if (managedMobs[i].tokenCooldownRemaining > 0f)
                    managedMobs[i].tokenCooldownRemaining -= Time.deltaTime;
            }}
        }}

        /// <summary>
        /// Assign roles: grant attack tokens to waiting mobs, assign support/circler to rest.
        /// </summary>
        private void AssignRoles()
        {{
            // Grant tokens to waiting mobs if slots available
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                var entry = managedMobs[i];
                if (entry.hasAttackToken)
                {{
                    entry.role = MobRole.Aggressive;
                    continue;
                }}

                if (activeTokenCount < maxSimultaneousAttackers
                    && entry.tokenCooldownRemaining <= 0f
                    && entry.role == MobRole.Waiting)
                {{
                    entry.hasAttackToken = true;
                    entry.role = MobRole.Aggressive;
                    activeTokenCount++;
                    continue;
                }}

                // Assign non-token roles based on distance
                if (entry.mob == null) continue;
                float sqrDist = (entry.mob.transform.position - playerTransform.position).sqrMagnitude;

                // Mobs far away support; mobs nearby circle
                if (sqrDist > flankRadius * flankRadius * 4f)
                    entry.role = MobRole.Support;
                else if (!entry.hasAttackToken)
                    entry.role = MobRole.Circler;
            }}
        }}

        /// <summary>
        /// Direct each mob's NavMeshAgent based on assigned role.
        /// </summary>
        private void DirectMobs()
        {{
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                var entry = managedMobs[i];
                if (entry.mob == null) continue;

                var agent = entry.mob.GetComponent<NavMeshAgent>();
                if (agent == null) continue;

                switch (entry.role)
                {{
                    case MobRole.Aggressive:
                        // Move directly toward player to attack
                        agent.SetDestination(playerTransform.position);
                        agent.speed = repositionSpeed * 1.5f;
                        break;

                    case MobRole.Support:
                        // Hold position, face player (for ranged attacks / buffs)
                        agent.SetDestination(agent.transform.position);
                        agent.transform.LookAt(new Vector3(
                            playerTransform.position.x,
                            agent.transform.position.y,
                            playerTransform.position.z
                        ));
                        break;

                    case MobRole.Circler:
                        // Circle the player at flank radius
                        Vector3 flankPos = GetFlankPosition(entry.flankSlot);
                        agent.SetDestination(flankPos);
                        agent.speed = repositionSpeed;
                        break;

                    case MobRole.Waiting:
                        // Hold position, wait for token
                        agent.SetDestination(agent.transform.position);
                        break;
                }}
            }}
        }}

        /// <summary>
        /// Calculate flanking position around the player for a given slot.
        /// Distributes mobs evenly around the player in a circle.
        /// </summary>
        private Vector3 GetFlankPosition(int slot)
        {{
            float angle = (360f / FLANK_SLOTS) * slot * Mathf.Deg2Rad;
            Vector3 offset = new Vector3(
                Mathf.Cos(angle) * flankRadius,
                0f,
                Mathf.Sin(angle) * flankRadius
            );
            return playerTransform.position + offset;
        }}

        /// <summary>
        /// Assign the next available flank slot index.
        /// </summary>
        private int AssignFlankSlot()
        {{
            bool[] occupied = new bool[FLANK_SLOTS];
            for (int i = 0; i < managedMobs.Count; i++)
                occupied[managedMobs[i].flankSlot % FLANK_SLOTS] = true;

            for (int i = 0; i < FLANK_SLOTS; i++)
            {{
                if (!occupied[i]) return i;
            }}
            return managedMobs.Count % FLANK_SLOTS;
        }}

        /// <summary>
        /// Request an attack token. Returns true if granted.
        /// Called by individual mob AI scripts.
        /// </summary>
        public bool RequestAttackToken(GameObject mob)
        {{
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                if (managedMobs[i].mob == mob)
                {{
                    if (managedMobs[i].hasAttackToken) return true;
                    if (activeTokenCount < maxSimultaneousAttackers
                        && managedMobs[i].tokenCooldownRemaining <= 0f)
                    {{
                        managedMobs[i].hasAttackToken = true;
                        managedMobs[i].role = MobRole.Aggressive;
                        activeTokenCount++;
                        return true;
                    }}
                    return false;
                }}
            }}
            return false;
        }}

        /// <summary>
        /// Return an attack token after completing an attack or disengaging.
        /// Called by individual mob AI scripts.
        /// </summary>
        public void ReturnAttackToken(GameObject mob)
        {{
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                if (managedMobs[i].mob == mob && managedMobs[i].hasAttackToken)
                {{
                    managedMobs[i].hasAttackToken = false;
                    managedMobs[i].role = MobRole.Waiting;
                    managedMobs[i].tokenCooldownRemaining = tokenCooldown;
                    activeTokenCount--;
                    return;
                }}
            }}
        }}

        /// <summary>
        /// Notify the coordinator that a mob's state has changed.
        /// Triggers re-evaluation of role assignments.
        /// </summary>
        public void NotifyStateChange(GameObject mob, string newState)
        {{
            // Force immediate role re-assignment on next frame
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                if (managedMobs[i].mob == mob)
                {{
                    if (newState == "dead" || newState == "fled")
                    {{
                        if (managedMobs[i].hasAttackToken)
                        {{
                            managedMobs[i].hasAttackToken = false;
                            activeTokenCount--;
                        }}
                        managedMobs.RemoveAt(i);
                    }}
                    return;
                }}
            }}
        }}

        /// <summary>
        /// Get the current role assigned to a specific mob.
        /// </summary>
        public MobRole GetMobRole(GameObject mob)
        {{
            for (int i = 0; i < managedMobs.Count; i++)
            {{
                if (managedMobs[i].mob == mob)
                    return managedMobs[i].role;
            }}
            return MobRole.Waiting;
        }}

        private void OnDrawGizmosSelected()
        {{
            Gizmos.color = Color.yellow;
            Gizmos.DrawWireSphere(transform.position, coordinationRadius);

            if (playerTransform != null)
            {{
                Gizmos.color = Color.cyan;
                Gizmos.DrawWireSphere(playerTransform.position, flankRadius);

                // Draw flank slot positions
                Gizmos.color = Color.green;
                for (int i = 0; i < FLANK_SLOTS; i++)
                {{
                    float angle = (360f / FLANK_SLOTS) * i * Mathf.Deg2Rad;
                    Vector3 pos = playerTransform.position + new Vector3(
                        Mathf.Cos(angle) * flankRadius, 0f,
                        Mathf.Sin(angle) * flankRadius
                    );
                    Gizmos.DrawSphere(pos, 0.3f);
                }}
            }}
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# TAC-02: Boss phase controller (FromSoftware-quality multi-phase)
# ---------------------------------------------------------------------------


def generate_boss_phase_controller_script(
    name: str,
    phase_thresholds: list[float] | None = None,
    transition_invuln_duration: float = 2.0,
    rage_speed_multiplier: float = 1.3,
    vulnerability_window_duration: float = 1.5,
    telegraph_delay: float = 0.8,
) -> str:
    """Generate C# runtime MonoBehaviour for a multi-phase boss encounter.

    Produces a FromSoftware-quality boss controller with configurable
    phase transitions, rage mechanics, vulnerability windows, telegraphed
    attacks with visual warnings, and pattern memory that tracks player
    dodge behavior. Includes UnityEvents for phase change, enrage,
    vulnerability, telegraph, and health bar integration.

    Args:
        name: Boss name (sanitized for C# identifier).
        phase_thresholds: Health percentage thresholds for phase transitions
            (descending order, e.g. [0.7, 0.4]). Defaults to [0.7, 0.4].
        transition_invuln_duration: Seconds of invulnerability during transition.
        rage_speed_multiplier: Speed multiplier at max rage within a phase.
        vulnerability_window_duration: Seconds the boss is vulnerable after attack.
        telegraph_delay: Seconds of visual warning before telegraphed attacks.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)
    thresholds = phase_thresholds or [0.7, 0.4]

    # Build phase definitions array initializer
    phase_count = len(thresholds) + 1
    threshold_entries = ", ".join(f"{t}f" for t in thresholds)

    return f'''using UnityEngine;
using UnityEngine.Events;
using System.Collections;
using System.Collections.Generic;

namespace VeilBreakers.Gameplay
{{
    /// <summary>
    /// Multi-phase boss encounter controller for {sanitize_cs_string(name)}.
    /// Supports phase transitions, rage, vulnerability windows,
    /// telegraphed attacks, and pattern memory.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    public class BossPhaseController_{safe_name} : MonoBehaviour
    {{
        /// <summary>Serializable phase definition.</summary>
        [System.Serializable]
        public class BossPhase
        {{
            public string phaseName;
            public float healthThreshold;
            public float speedMultiplier = 1f;
            public float damageMultiplier = 1f;
            public string[] unlockedAbilities;
            public string transitionAnimTrigger;
            public string dialogueLine;
        }}

        /// <summary>Telegraphed attack definition.</summary>
        [System.Serializable]
        public class TelegraphedAttack
        {{
            public string attackName;
            public float damage = 30f;
            public float telegraphDelay = {telegraph_delay}f;
            public float vulnerabilityDuration = {vulnerability_window_duration}f;
            public string animTrigger;
            public float hitboxRadius = 3f;
        }}

        [Header("Health")]
        public float maxHealth = 1000f;
        public float currentHealth;

        [Header("Phases")]
        public BossPhase[] phases;
        public int currentPhaseIndex = 0;

        [Header("Phase Transition")]
        public float transitionInvulnDuration = {transition_invuln_duration}f;
        public bool isInvulnerable = false;
        public bool isTransitioning = false;

        [Header("Rage")]
        public float rageSpeedMultiplier = {rage_speed_multiplier}f;
        public float currentRageLevel = 0f;
        public float rageDecayRate = 0.1f;
        public float rageBuildRate = 0.05f;

        [Header("Vulnerability")]
        public float vulnerabilityWindowDuration = {vulnerability_window_duration}f;
        public bool isVulnerable = false;

        [Header("Telegraphed Attacks")]
        public TelegraphedAttack[] telegraphedAttacks;
        public float telegraphDelay = {telegraph_delay}f;
        public bool isTelegraphing = false;

        [Header("Pattern Memory")]
        public int dodgeTrackingWindow = 10;
        public float timingVariationRange = 0.3f;

        [Header("Events")]
        public UnityEvent<int> OnPhaseChange;
        public UnityEvent OnEnrage;
        public UnityEvent<float> OnVulnerabilityWindow;
        public UnityEvent<string> OnTelegraph;
        public UnityEvent<float> OnHealthChanged;

        private float[] phaseThresholds = new float[] {{ {threshold_entries} }};
        private List<float> playerDodgeTimes = new List<float>();
        private float currentSpeedMultiplier = 1f;
        private float currentDamageMultiplier = 1f;
        private Animator animator;
        private Collider[] hitBuffer = new Collider[32];

        private void Start()
        {{
            currentHealth = maxHealth;
            animator = GetComponent<Animator>();

            // Initialize default phases if not configured in Inspector
            if (phases == null || phases.Length == 0)
            {{
                phases = new BossPhase[{phase_count}];
                for (int i = 0; i < phases.Length; i++)
                {{
                    phases[i] = new BossPhase();
                    phases[i].phaseName = "Phase " + (i + 1);
                    phases[i].speedMultiplier = 1f + (i * 0.15f);
                    phases[i].damageMultiplier = 1f + (i * 0.2f);
                }}
            }}
        }}

        private void Update()
        {{
            if (currentHealth <= 0f) return;

            // Rage build/decay within current phase
            UpdateRage();

            // Apply current phase multipliers with rage scaling
            float rageBonus = Mathf.Lerp(1f, rageSpeedMultiplier, currentRageLevel);
            currentSpeedMultiplier = GetCurrentPhase().speedMultiplier * rageBonus;
            currentDamageMultiplier = GetCurrentPhase().damageMultiplier * rageBonus;
        }}

        /// <summary>
        /// Deal damage to the boss. Handles phase transitions and death.
        /// </summary>
        public void TakeDamage(float amount)
        {{
            if (isInvulnerable || currentHealth <= 0f) return;

            // Vulnerability window bonus damage
            float finalDamage = isVulnerable ? amount * 1.5f : amount;
            currentHealth -= finalDamage;
            currentHealth = Mathf.Max(0f, currentHealth);

            // Build rage when taking damage
            currentRageLevel = Mathf.Min(1f, currentRageLevel + rageBuildRate);

            OnHealthChanged?.Invoke(currentHealth / maxHealth);

            // Check phase transition
            CheckPhaseTransition();

            if (currentHealth <= 0f)
                OnDeath();
        }}

        /// <summary>
        /// Check if health has dropped below the next phase threshold.
        /// </summary>
        private void CheckPhaseTransition()
        {{
            float healthPct = currentHealth / maxHealth;
            int nextPhase = currentPhaseIndex;

            for (int i = currentPhaseIndex; i < phaseThresholds.Length; i++)
            {{
                if (healthPct <= phaseThresholds[i])
                    nextPhase = i + 1;
            }}

            if (nextPhase != currentPhaseIndex && !isTransitioning)
                StartCoroutine(PhaseTransitionCoroutine(nextPhase));
        }}

        /// <summary>
        /// Execute phase transition: invulnerability, animation, events.
        /// </summary>
        private IEnumerator PhaseTransitionCoroutine(int newPhase)
        {{
            isTransitioning = true;
            isInvulnerable = true;

            // Play transition animation
            if (animator != null && phases.Length > newPhase)
            {{
                string trigger = phases[newPhase].transitionAnimTrigger;
                if (!string.IsNullOrEmpty(trigger))
                    animator.SetTrigger(trigger);
            }}

            // Fire phase change event
            currentPhaseIndex = newPhase;
            OnPhaseChange?.Invoke(currentPhaseIndex);

            // Reset rage on phase change
            currentRageLevel = 0f;

            yield return new WaitForSeconds(transitionInvulnDuration);

            isInvulnerable = false;
            isTransitioning = false;
        }}

        /// <summary>
        /// Execute a telegraphed attack with visual warning and vulnerability window.
        /// </summary>
        public void ExecuteTelegraphedAttack(int attackIndex)
        {{
            if (telegraphedAttacks == null || attackIndex < 0
                || attackIndex >= telegraphedAttacks.Length)
                return;

            StartCoroutine(TelegraphedAttackCoroutine(telegraphedAttacks[attackIndex]));
        }}

        private IEnumerator TelegraphedAttackCoroutine(TelegraphedAttack attack)
        {{
            isTelegraphing = true;
            OnTelegraph?.Invoke(attack.attackName);

            // Telegraph phase: visual warning
            if (animator != null && !string.IsNullOrEmpty(attack.animTrigger))
                animator.SetTrigger(attack.animTrigger);

            // Apply pattern memory timing variation
            float variation = GetTimingVariation();
            yield return new WaitForSeconds(attack.telegraphDelay + variation);

            isTelegraphing = false;

            // Execute the attack hitbox
            float damage = attack.damage * currentDamageMultiplier;
            int hitCount = Physics.OverlapSphereNonAlloc(
                transform.position, attack.hitboxRadius, hitBuffer
            );
            for (int i = 0; i < hitCount; i++)
            {{
                if (hitBuffer[i] == null || hitBuffer[i].gameObject == gameObject)
                    continue;
                if (hitBuffer[i].CompareTag("Player"))
                {{
                    // Record dodge timing if player dodged
                    RecordDodgeAttempt();
                }}
            }}

            // Vulnerability window after attack
            StartCoroutine(VulnerabilityCoroutine(attack.vulnerabilityDuration));
        }}

        /// <summary>
        /// Open a vulnerability window where the boss takes extra damage.
        /// </summary>
        private IEnumerator VulnerabilityCoroutine(float duration)
        {{
            isVulnerable = true;
            OnVulnerabilityWindow?.Invoke(duration);

            yield return new WaitForSeconds(duration);

            isVulnerable = false;
        }}

        /// <summary>
        /// Update rage level: builds on hit, decays over time.
        /// </summary>
        private void UpdateRage()
        {{
            if (currentRageLevel > 0f)
            {{
                currentRageLevel -= rageDecayRate * Time.deltaTime;
                currentRageLevel = Mathf.Max(0f, currentRageLevel);
            }}

            // Fire enrage event when rage hits max
            if (currentRageLevel >= 1f)
                OnEnrage?.Invoke();
        }}

        /// <summary>
        /// Record player dodge timing for pattern memory analysis.
        /// </summary>
        public void RecordDodgeAttempt()
        {{
            playerDodgeTimes.Add(Time.time);
            if (playerDodgeTimes.Count > dodgeTrackingWindow)
                playerDodgeTimes.RemoveAt(0);
        }}

        /// <summary>
        /// Analyze player dodge patterns and return timing variation.
        /// Boss occasionally varies attack timing to counter predictable dodges.
        /// </summary>
        private float GetTimingVariation()
        {{
            if (playerDodgeTimes.Count < 3)
                return 0f;

            // Calculate average interval between dodges
            float avgInterval = 0f;
            for (int i = 1; i < playerDodgeTimes.Count; i++)
                avgInterval += playerDodgeTimes[i] - playerDodgeTimes[i - 1];
            avgInterval /= (playerDodgeTimes.Count - 1);

            // Vary timing proportional to how consistent the player's dodges are
            float consistency = 0f;
            for (int i = 1; i < playerDodgeTimes.Count; i++)
            {{
                float interval = playerDodgeTimes[i] - playerDodgeTimes[i - 1];
                consistency += Mathf.Abs(interval - avgInterval);
            }}
            consistency /= (playerDodgeTimes.Count - 1);

            // Low consistency variance = predictable player = more variation
            float variationFactor = Mathf.Clamp01(1f - (consistency / avgInterval));
            return Random.Range(-timingVariationRange, timingVariationRange) * variationFactor;
        }}

        /// <summary>
        /// Get the current active boss phase configuration.
        /// </summary>
        public BossPhase GetCurrentPhase()
        {{
            if (phases == null || phases.Length == 0) return new BossPhase();
            return phases[Mathf.Min(currentPhaseIndex, phases.Length - 1)];
        }}

        /// <summary>
        /// Get the current effective speed multiplier (phase + rage).
        /// </summary>
        public float GetSpeedMultiplier()
        {{
            return currentSpeedMultiplier;
        }}

        /// <summary>
        /// Get the current effective damage multiplier (phase + rage).
        /// </summary>
        public float GetDamageMultiplier()
        {{
            return currentDamageMultiplier;
        }}

        private void OnDeath()
        {{
            StopAllCoroutines();
            isInvulnerable = false;
            isVulnerable = false;
            isTelegraphing = false;
        }}

        private void OnDrawGizmosSelected()
        {{
            if (telegraphedAttacks == null) return;
            Gizmos.color = Color.red;
            for (int i = 0; i < telegraphedAttacks.Length; i++)
                Gizmos.DrawWireSphere(transform.position, telegraphedAttacks[i].hitboxRadius);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# TAC-03: Player combat controller (stamina / poise / parry)
# ---------------------------------------------------------------------------


def generate_player_combat_controller_script(
    name: str = "Default",
    stamina_max: float = 100.0,
    stamina_regen_rate: float = 15.0,
    stamina_regen_delay: float = 1.0,
    poise_max: float = 50.0,
    poise_regen_rate: float = 5.0,
    parry_window: float = 0.2,
    block_stamina_drain: float = 15.0,
    weapon_slots: int = 2,
    ability_slots: int = 4,
    lock_on_range: float = 20.0,
    lock_on_angle: float = 60.0,
) -> str:
    """Generate C# runtime MonoBehaviour for an action RPG player combat controller.

    Produces a comprehensive player combat system with stamina management,
    poise/stagger mechanics, guard/block with stamina drain, perfect parry
    timing window, weapon switching, ability slots, target lock-on with
    view cone, animation state machine integration, and Input System support.
    Uses namespace VeilBreakers.Gameplay -- no UnityEditor references.

    Args:
        name: Controller variant name (sanitized for C# identifier).
        stamina_max: Maximum stamina pool.
        stamina_regen_rate: Stamina regenerated per second when idle.
        stamina_regen_delay: Seconds after last action before regen starts.
        poise_max: Maximum poise before stagger.
        poise_regen_rate: Poise regenerated per second.
        parry_window: Perfect parry timing window in seconds.
        block_stamina_drain: Stamina cost per blocked hit.
        weapon_slots: Number of weapon slots available.
        ability_slots: Number of ability buttons mapped to skills.
        lock_on_range: Maximum range for target lock-on.
        lock_on_angle: View cone half-angle for lock-on acquisition.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(name)

    return f'''using UnityEngine;
using UnityEngine.InputSystem;
using System.Collections.Generic;

namespace VeilBreakers.Gameplay
{{
    /// <summary>
    /// Player combat controller for {sanitize_cs_string(name)}.
    /// Features: stamina, poise/stagger, guard/block, perfect parry,
    /// weapon switching, ability slots, and target lock-on.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    public class VB_PlayerCombatController_{safe_name} : MonoBehaviour
    {{
        /// <summary>Player combat state machine states.</summary>
        public enum CombatState
        {{
            Idle,
            Attacking,
            Blocking,
            Parrying,
            Dodging,
            Staggered,
            UsingAbility,
            Dead
        }}

        /// <summary>Weapon slot data.</summary>
        [System.Serializable]
        public class WeaponSlot
        {{
            public GameObject weaponPrefab;
            public float baseDamage = 20f;
            public float attackStaminaCost = 15f;
            public float poiseDamage = 10f;
            public float attackSpeed = 1f;
            public string animOverride;
        }}

        /// <summary>Ability slot data.</summary>
        [System.Serializable]
        public class AbilitySlot
        {{
            public string abilityName;
            public float cooldown = 5f;
            public float staminaCost = 25f;
            public float remainingCooldown;
        }}

        [Header("Stamina")]
        public float staminaMax = {stamina_max}f;
        public float staminaCurrent;
        public float staminaRegenRate = {stamina_regen_rate}f;
        public float staminaRegenDelay = {stamina_regen_delay}f;

        [Header("Poise")]
        public float poiseMax = {poise_max}f;
        public float poiseCurrent;
        public float poiseRegenRate = {poise_regen_rate}f;
        public float staggerDuration = 1.0f;

        [Header("Block / Parry")]
        public float blockStaminaDrain = {block_stamina_drain}f;
        public float blockDamageReduction = 0.7f;
        public float parryWindow = {parry_window}f;
        public float parryDamageMultiplier = 2.0f;

        [Header("Weapons")]
        public WeaponSlot[] weaponSlots = new WeaponSlot[{weapon_slots}];
        public int activeWeaponIndex = 0;

        [Header("Abilities")]
        public AbilitySlot[] abilitySlots = new AbilitySlot[{ability_slots}];

        [Header("Lock-On")]
        public float lockOnRange = {lock_on_range}f;
        public float lockOnAngle = {lock_on_angle}f;
        public LayerMask enemyLayer;
        public Transform lockOnTarget;
        public bool isLockedOn = false;

        [Header("Dodge")]
        public float dodgeStaminaCost = 20f;
        public float dodgeDistance = 4f;
        public float dodgeIFrameDuration = 0.25f;
        public float dodgeDuration = 0.4f;

        [Header("State")]
        public CombatState currentState = CombatState.Idle;
        public float currentHealth = 100f;
        public float maxHealth = 100f;

        private Animator animator;
        private float lastActionTime;
        private float stateTimer = 0f;
        private bool isInvincible = false;
        private float blockStartTime;
        private Collider[] lockOnBuffer = new Collider[16];

        private void Start()
        {{
            staminaCurrent = staminaMax;
            poiseCurrent = poiseMax;
            animator = GetComponent<Animator>();
        }}

        private void Update()
        {{
            if (currentState == CombatState.Dead) return;

            UpdateStamina();
            UpdatePoise();
            UpdateAbilityCooldowns();
            UpdateStateTimer();
        }}

        // -----------------------------------------------------------------
        // Stamina
        // -----------------------------------------------------------------

        /// <summary>
        /// Regenerate stamina after delay since last action.
        /// </summary>
        private void UpdateStamina()
        {{
            if (Time.time - lastActionTime >= staminaRegenDelay
                && currentState == CombatState.Idle)
            {{
                staminaCurrent = Mathf.Min(staminaMax,
                    staminaCurrent + staminaRegenRate * Time.deltaTime);
            }}
        }}

        /// <summary>
        /// Consume stamina for an action. Returns false if insufficient.
        /// </summary>
        public bool ConsumeStamina(float amount)
        {{
            if (staminaCurrent < amount) return false;
            staminaCurrent -= amount;
            lastActionTime = Time.time;
            return true;
        }}

        // -----------------------------------------------------------------
        // Poise / Stagger
        // -----------------------------------------------------------------

        /// <summary>
        /// Regenerate poise over time.
        /// </summary>
        private void UpdatePoise()
        {{
            if (currentState != CombatState.Staggered)
            {{
                poiseCurrent = Mathf.Min(poiseMax,
                    poiseCurrent + poiseRegenRate * Time.deltaTime);
            }}
        }}

        /// <summary>
        /// Apply poise damage. If poise breaks, enter stagger state.
        /// </summary>
        public void ApplyPoiseDamage(float amount)
        {{
            poiseCurrent -= amount;
            if (poiseCurrent <= 0f)
            {{
                poiseCurrent = 0f;
                EnterStagger();
            }}
        }}

        /// <summary>
        /// Enter stagger state: player is briefly unable to act.
        /// </summary>
        private void EnterStagger()
        {{
            currentState = CombatState.Staggered;
            stateTimer = staggerDuration;
            if (animator != null)
                animator.SetTrigger("Stagger");
        }}

        // -----------------------------------------------------------------
        // Block / Parry
        // -----------------------------------------------------------------

        /// <summary>
        /// Begin blocking. If called within parry window timing, activates parry.
        /// </summary>
        public void StartBlock()
        {{
            if (currentState != CombatState.Idle) return;
            currentState = CombatState.Blocking;
            blockStartTime = Time.time;
            if (animator != null)
                animator.SetBool("IsBlocking", true);
        }}

        /// <summary>
        /// End blocking and return to idle.
        /// </summary>
        public void EndBlock()
        {{
            if (currentState == CombatState.Blocking || currentState == CombatState.Parrying)
            {{
                currentState = CombatState.Idle;
                if (animator != null)
                    animator.SetBool("IsBlocking", false);
            }}
        }}

        /// <summary>
        /// Check if the block started within the parry window (perfect parry).
        /// </summary>
        public bool IsInParryWindow()
        {{
            return currentState == CombatState.Blocking
                && (Time.time - blockStartTime) <= parryWindow;
        }}

        /// <summary>
        /// Process an incoming hit while blocking.
        /// Returns remaining damage after block/parry reduction.
        /// </summary>
        public float ProcessBlockedHit(float incomingDamage, float poiseDamage)
        {{
            if (IsInParryWindow())
            {{
                // Perfect parry: negate damage, reflect poise damage
                currentState = CombatState.Parrying;
                stateTimer = 0.3f;
                if (animator != null)
                    animator.SetTrigger("Parry");
                return 0f;
            }}

            // Normal block: reduce damage, drain stamina
            if (!ConsumeStamina(blockStaminaDrain))
            {{
                // Guard broken: take full damage and stagger
                EndBlock();
                ApplyPoiseDamage(poiseDamage);
                return incomingDamage;
            }}

            return incomingDamage * (1f - blockDamageReduction);
        }}

        // -----------------------------------------------------------------
        // Attack
        // -----------------------------------------------------------------

        /// <summary>
        /// Execute a light attack with the active weapon.
        /// </summary>
        public void LightAttack()
        {{
            if (currentState != CombatState.Idle) return;

            WeaponSlot weapon = GetActiveWeapon();
            if (weapon == null) return;

            if (!ConsumeStamina(weapon.attackStaminaCost)) return;

            currentState = CombatState.Attacking;
            stateTimer = 0.5f / weapon.attackSpeed;
            if (animator != null)
                animator.SetTrigger("LightAttack");
        }}

        /// <summary>
        /// Execute a heavy attack with the active weapon (more damage, more stamina).
        /// </summary>
        public void HeavyAttack()
        {{
            if (currentState != CombatState.Idle) return;

            WeaponSlot weapon = GetActiveWeapon();
            if (weapon == null) return;

            float heavyCost = weapon.attackStaminaCost * 1.5f;
            if (!ConsumeStamina(heavyCost)) return;

            currentState = CombatState.Attacking;
            stateTimer = 0.8f / weapon.attackSpeed;
            if (animator != null)
                animator.SetTrigger("HeavyAttack");
        }}

        // -----------------------------------------------------------------
        // Dodge
        // -----------------------------------------------------------------

        /// <summary>
        /// Execute a dodge roll with i-frames.
        /// </summary>
        public void Dodge(Vector3 direction)
        {{
            if (currentState != CombatState.Idle) return;
            if (!ConsumeStamina(dodgeStaminaCost)) return;

            currentState = CombatState.Dodging;
            stateTimer = dodgeDuration;
            isInvincible = true;

            if (animator != null)
                animator.SetTrigger("Dodge");

            // Apply dodge movement
            Vector3 dodgeDir = direction.sqrMagnitude > 0.01f
                ? direction.normalized : -transform.forward;
            transform.position += dodgeDir * dodgeDistance;

            // Schedule i-frame end
            StartCoroutine(EndIFrames());
        }}

        private System.Collections.IEnumerator EndIFrames()
        {{
            yield return new WaitForSeconds(dodgeIFrameDuration);
            isInvincible = false;
        }}

        // -----------------------------------------------------------------
        // Weapon Switching
        // -----------------------------------------------------------------

        /// <summary>
        /// Switch to the next weapon slot.
        /// </summary>
        public void SwitchWeapon()
        {{
            if (currentState != CombatState.Idle) return;
            activeWeaponIndex = (activeWeaponIndex + 1) % weaponSlots.Length;
            if (animator != null)
                animator.SetInteger("WeaponIndex", activeWeaponIndex);
        }}

        /// <summary>
        /// Switch to a specific weapon slot by index.
        /// </summary>
        public void SwitchToWeapon(int index)
        {{
            if (currentState != CombatState.Idle) return;
            if (index < 0 || index >= weaponSlots.Length) return;
            activeWeaponIndex = index;
            if (animator != null)
                animator.SetInteger("WeaponIndex", activeWeaponIndex);
        }}

        /// <summary>
        /// Get the currently active weapon slot data.
        /// </summary>
        public WeaponSlot GetActiveWeapon()
        {{
            if (weaponSlots == null || weaponSlots.Length == 0) return null;
            return weaponSlots[activeWeaponIndex];
        }}

        // -----------------------------------------------------------------
        // Abilities
        // -----------------------------------------------------------------

        /// <summary>
        /// Use an ability from a specific slot (0 to {ability_slots - 1}).
        /// </summary>
        public bool UseAbility(int slotIndex)
        {{
            if (currentState != CombatState.Idle) return false;
            if (slotIndex < 0 || slotIndex >= abilitySlots.Length) return false;

            AbilitySlot slot = abilitySlots[slotIndex];
            if (slot == null || string.IsNullOrEmpty(slot.abilityName)) return false;
            if (slot.remainingCooldown > 0f) return false;
            if (!ConsumeStamina(slot.staminaCost)) return false;

            currentState = CombatState.UsingAbility;
            stateTimer = 0.5f;
            slot.remainingCooldown = slot.cooldown;

            if (animator != null)
                animator.SetTrigger("Ability_" + slotIndex);

            return true;
        }}

        /// <summary>
        /// Update all ability cooldown timers.
        /// </summary>
        private void UpdateAbilityCooldowns()
        {{
            for (int i = 0; i < abilitySlots.Length; i++)
            {{
                if (abilitySlots[i] != null && abilitySlots[i].remainingCooldown > 0f)
                    abilitySlots[i].remainingCooldown -= Time.deltaTime;
            }}
        }}

        // -----------------------------------------------------------------
        // Target Lock-On
        // -----------------------------------------------------------------

        /// <summary>
        /// Toggle target lock-on. Finds closest enemy in view cone.
        /// </summary>
        public void ToggleLockOn()
        {{
            if (isLockedOn)
            {{
                isLockedOn = false;
                lockOnTarget = null;
                return;
            }}

            lockOnTarget = FindLockOnTarget();
            isLockedOn = lockOnTarget != null;
        }}

        /// <summary>
        /// Find the closest enemy within lock-on range and view cone angle.
        /// Uses OverlapSphereNonAlloc for zero-allocation detection.
        /// </summary>
        private Transform FindLockOnTarget()
        {{
            int hitCount = Physics.OverlapSphereNonAlloc(
                transform.position, lockOnRange, lockOnBuffer, enemyLayer
            );

            Transform closest = null;
            float closestDist = float.MaxValue;

            for (int i = 0; i < hitCount; i++)
            {{
                if (lockOnBuffer[i] == null) continue;
                Transform candidate = lockOnBuffer[i].transform;

                // View cone check
                Vector3 dirToTarget = (candidate.position - transform.position).normalized;
                float angle = Vector3.Angle(transform.forward, dirToTarget);
                if (angle > lockOnAngle) continue;

                float dist = (candidate.position - transform.position).sqrMagnitude;
                if (dist < closestDist)
                {{
                    closestDist = dist;
                    closest = candidate;
                }}
            }}

            return closest;
        }}

        /// <summary>
        /// Cycle to the next lock-on target when already locked on.
        /// </summary>
        public void CycleLockOnTarget()
        {{
            if (!isLockedOn) return;

            int hitCount = Physics.OverlapSphereNonAlloc(
                transform.position, lockOnRange, lockOnBuffer, enemyLayer
            );

            // Find next target after current one
            Transform nextTarget = null;
            float closestDistAfterCurrent = float.MaxValue;
            float currentDist = lockOnTarget != null
                ? (lockOnTarget.position - transform.position).sqrMagnitude : 0f;

            for (int i = 0; i < hitCount; i++)
            {{
                if (lockOnBuffer[i] == null) continue;
                Transform candidate = lockOnBuffer[i].transform;
                if (candidate == lockOnTarget) continue;

                Vector3 dirToTarget = (candidate.position - transform.position).normalized;
                float angle = Vector3.Angle(transform.forward, dirToTarget);
                if (angle > lockOnAngle) continue;

                float dist = (candidate.position - transform.position).sqrMagnitude;
                if (dist > currentDist && dist < closestDistAfterCurrent)
                {{
                    closestDistAfterCurrent = dist;
                    nextTarget = candidate;
                }}
            }}

            if (nextTarget != null)
                lockOnTarget = nextTarget;
        }}

        // -----------------------------------------------------------------
        // Damage Handling
        // -----------------------------------------------------------------

        /// <summary>
        /// Take damage from an external source. Respects i-frames and blocking.
        /// </summary>
        public void TakeDamage(float damage, float poiseDmg = 0f)
        {{
            if (isInvincible || currentState == CombatState.Dead) return;

            if (currentState == CombatState.Blocking || currentState == CombatState.Parrying)
            {{
                damage = ProcessBlockedHit(damage, poiseDmg);
                if (damage <= 0f) return;
            }}

            currentHealth -= damage;
            ApplyPoiseDamage(poiseDmg);

            if (currentHealth <= 0f)
            {{
                currentHealth = 0f;
                currentState = CombatState.Dead;
                if (animator != null)
                    animator.SetTrigger("Death");
            }}
        }}

        // -----------------------------------------------------------------
        // State Timer
        // -----------------------------------------------------------------

        /// <summary>
        /// Count down state timer and return to idle when expired.
        /// </summary>
        private void UpdateStateTimer()
        {{
            if (stateTimer > 0f)
            {{
                stateTimer -= Time.deltaTime;
                if (stateTimer <= 0f)
                {{
                    if (currentState != CombatState.Dead && currentState != CombatState.Blocking)
                        currentState = CombatState.Idle;
                }}
            }}
        }}

        // -----------------------------------------------------------------
        // Input System Integration
        // -----------------------------------------------------------------

        /// <summary>Input callback for light attack (InputSystem).</summary>
        public void OnLightAttack(InputAction.CallbackContext context)
        {{
            if (context.performed) LightAttack();
        }}

        /// <summary>Input callback for heavy attack (InputSystem).</summary>
        public void OnHeavyAttack(InputAction.CallbackContext context)
        {{
            if (context.performed) HeavyAttack();
        }}

        /// <summary>Input callback for block (InputSystem).</summary>
        public void OnBlock(InputAction.CallbackContext context)
        {{
            if (context.started) StartBlock();
            if (context.canceled) EndBlock();
        }}

        /// <summary>Input callback for dodge (InputSystem).</summary>
        public void OnDodge(InputAction.CallbackContext context)
        {{
            if (context.performed) Dodge(transform.forward);
        }}

        /// <summary>Input callback for weapon switch (InputSystem).</summary>
        public void OnSwitchWeapon(InputAction.CallbackContext context)
        {{
            if (context.performed) SwitchWeapon();
        }}

        /// <summary>Input callback for lock-on toggle (InputSystem).</summary>
        public void OnLockOn(InputAction.CallbackContext context)
        {{
            if (context.performed) ToggleLockOn();
        }}

        /// <summary>Input callback for ability slot 0 (InputSystem).</summary>
        public void OnAbility0(InputAction.CallbackContext context)
        {{
            if (context.performed) UseAbility(0);
        }}

        /// <summary>Input callback for ability slot 1 (InputSystem).</summary>
        public void OnAbility1(InputAction.CallbackContext context)
        {{
            if (context.performed) UseAbility(1);
        }}

        /// <summary>Input callback for ability slot 2 (InputSystem).</summary>
        public void OnAbility2(InputAction.CallbackContext context)
        {{
            if (context.performed) UseAbility(2);
        }}

        /// <summary>Input callback for ability slot 3 (InputSystem).</summary>
        public void OnAbility3(InputAction.CallbackContext context)
        {{
            if (context.performed) UseAbility(3);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SFX-01: Status Effect / Buff-Debuff System
# ---------------------------------------------------------------------------


def _validate_status_effect_params(
    duration: float,
    tick_interval: float,
    max_stacks: int,
    cc_immunity_window: float,
) -> Optional[str]:
    """Validate status effect system parameters.

    Returns None if valid, or an error string describing the problem.
    """
    if duration < 0:
        return "duration must be >= 0"
    if tick_interval < 0:
        return "tick_interval must be >= 0"
    if max_stacks < 1:
        return "max_stacks must be >= 1"
    if cc_immunity_window < 0:
        return "cc_immunity_window must be >= 0"
    return None


def generate_status_effect_system_script(
    namespace: str = "VeilBreakers.Gameplay",
    default_duration: float = 5.0,
    default_tick_interval: float = 1.0,
    default_max_stacks: int = 3,
    default_cc_immunity_window: float = 3.0,
) -> tuple[str, str]:
    """Generate a runtime status effect / buff-debuff system for 10 brands.

    Produces two C# scripts:
      1. StatusEffect ScriptableObject definition + StatusEffectInstance class
      2. StatusEffectManager MonoBehaviour (applies, ticks, removes effects)

    Supports DoT/HoT, crowd control with diminishing returns, stacking,
    stat modifiers, brand-specific combo interactions, and 10 built-in
    brand presets (IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND,
    RUIN, VOID).

    Args:
        namespace: C# namespace for generated classes.
        default_duration: Default effect duration in seconds.
        default_tick_interval: Default tick interval in seconds.
        default_max_stacks: Default max stacks for stackable effects.
        default_cc_immunity_window: Seconds of CC immunity after a CC ends.

    Returns:
        (status_effect_so_cs, status_effect_manager_cs) tuple.
    """
    err = _validate_status_effect_params(
        default_duration, default_tick_interval,
        default_max_stacks, default_cc_immunity_window,
    )
    if err:
        raise ValueError(err)

    safe_ns = sanitize_cs_identifier(namespace.replace(".", "_"))
    ns = namespace

    status_effect_so_cs = f'''using System;
using System.Collections.Generic;
using UnityEngine;

namespace {ns}
{{
    // =====================================================================
    // Enums
    // =====================================================================

    /// <summary>The 10 VeilBreakers elemental brands.</summary>
    public enum Brand
    {{
        None = 0,
        IRON,
        SAVAGE,
        SURGE,
        VENOM,
        DREAD,
        LEECH,
        GRACE,
        MEND,
        RUIN,
        VOID
    }}

    /// <summary>Stat types that can be modified by status effects.</summary>
    public enum StatType
    {{
        Health,
        MaxHealth,
        Attack,
        Defense,
        MovementSpeed,
        AttackSpeed,
        CritChance,
        CritDamage,
        HealingReceived,
        DamageTaken
    }}

    /// <summary>How a stat modifier is applied.</summary>
    public enum ModifierType
    {{
        Flat,
        Percent
    }}

    /// <summary>Crowd control types.</summary>
    public enum CrowdControlType
    {{
        None,
        Stun,
        Root,
        Silence,
        Fear,
        Knockback
    }}

    // =====================================================================
    // Data Structures
    // =====================================================================

    /// <summary>A single stat modification entry.</summary>
    [Serializable]
    public struct StatModifier
    {{
        public StatType statType;
        public ModifierType modifierType;
        public float value;
    }}

    // =====================================================================
    // StatusEffect ScriptableObject
    // =====================================================================

    /// <summary>
    /// ScriptableObject definition for a status effect / buff / debuff.
    /// Supports DoT, HoT, stat modifiers, crowd control, and brand combos.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    [CreateAssetMenu(fileName = "NewStatusEffect", menuName = "VeilBreakers/Status Effect")]
    public class StatusEffect : ScriptableObject
    {{
        [Header("Identity")]
        public string effectName = "NewEffect";
        [TextArea(2, 4)]
        public string description = "";
        public Brand brand = Brand.None;
        public Sprite icon;

        [Header("Timing")]
        [Tooltip("Total duration in seconds. 0 = infinite (must be removed manually).")]
        public float duration = {default_duration}f;
        [Tooltip("Seconds between ticks for DoT/HoT. 0 = no ticking.")]
        public float tickInterval = {default_tick_interval}f;

        [Header("Stacking")]
        public bool isStackable = false;
        [Min(1)]
        public int maxStacks = {default_max_stacks};

        [Header("Stat Modifiers")]
        public List<StatModifier> statModifiers = new List<StatModifier>();

        [Header("Damage / Healing Over Time")]
        [Tooltip("Damage dealt per tick (DoT).")]
        public float damagePerTick = 0f;
        [Tooltip("Healing applied per tick (HoT).")]
        public float healPerTick = 0f;

        [Header("Movement")]
        [Tooltip("Multiplier applied to movement speed. 1 = no change, <1 = slow, >1 = haste.")]
        public float movementSpeedModifier = 1f;

        [Header("Crowd Control")]
        public CrowdControlType crowdControlType = CrowdControlType.None;
        [Tooltip("Seconds of CC immunity after this CC ends (diminishing returns).")]
        public float ccImmunityWindow = {default_cc_immunity_window}f;

        [Header("VFX / SFX")]
        [Tooltip("Path to VFX prefab in Resources.")]
        public string vfxPrefabPath = "";
        [Tooltip("Path to SFX AudioClip in Resources.")]
        public string sfxClipPath = "";
    }}

    // =====================================================================
    // StatusEffectInstance (runtime tracker)
    // =====================================================================

    /// <summary>
    /// Runtime instance tracking a single applied status effect.
    /// Manages duration countdown, tick timing, and stack count.
    /// </summary>
    public class StatusEffectInstance
    {{
        public StatusEffect Definition {{ get; private set; }}
        public float RemainingDuration {{ get; set; }}
        public int CurrentStacks {{ get; set; }}
        public GameObject Source {{ get; private set; }}
        public float TickTimer {{ get; set; }}
        public bool IsExpired => Definition.duration > 0f && RemainingDuration <= 0f;

        public StatusEffectInstance(StatusEffect definition, GameObject source)
        {{
            Definition = definition;
            Source = source;
            RemainingDuration = definition.duration;
            CurrentStacks = 1;
            TickTimer = definition.tickInterval;
        }}

        /// <summary>Apply initial effect (stat mods, CC, VFX).</summary>
        public void Apply(StatusEffectManager manager)
        {{
            // Spawn VFX
            if (!string.IsNullOrEmpty(Definition.vfxPrefabPath))
            {{
                var prefab = Resources.Load<GameObject>(Definition.vfxPrefabPath);
                if (prefab != null)
                {{
                    var vfx = UnityEngine.Object.Instantiate(prefab, manager.transform);
                    manager.RegisterVFX(Definition.effectName, vfx);
                }}
            }}

            // Play SFX
            if (!string.IsNullOrEmpty(Definition.sfxClipPath))
            {{
                var clip = Resources.Load<AudioClip>(Definition.sfxClipPath);
                if (clip != null)
                {{
                    AudioSource.PlayClipAtPoint(clip, manager.transform.position);
                }}
            }}
        }}

        /// <summary>Tick: apply DoT/HoT damage, reduce timers.</summary>
        public void Tick(float deltaTime, StatusEffectManager manager)
        {{
            if (Definition.duration > 0f)
                RemainingDuration -= deltaTime;

            if (Definition.tickInterval > 0f)
            {{
                TickTimer -= deltaTime;
                if (TickTimer <= 0f)
                {{
                    TickTimer += Definition.tickInterval;
                    OnTick(manager);
                }}
            }}
        }}

        /// <summary>Handle a single tick: DoT damage and HoT healing.</summary>
        private void OnTick(StatusEffectManager manager)
        {{
            float dot = Definition.damagePerTick * CurrentStacks;
            float hot = Definition.healPerTick * CurrentStacks;

            if (dot > 0f)
                manager.ApplyDamage(dot, Source);

            if (hot > 0f)
                manager.ApplyHealing(hot, Source);

            // LEECH brand: heal source for DoT amount
            if (Definition.brand == Brand.LEECH && dot > 0f && Source != null)
            {{
                var sourceManager = Source.GetComponent<StatusEffectManager>();
                if (sourceManager != null)
                    sourceManager.ApplyHealing(dot, Source);
            }}
        }}

        /// <summary>Remove effect: cleanup VFX, restore state.</summary>
        public void Remove(StatusEffectManager manager)
        {{
            manager.DestroyVFX(Definition.effectName);
        }}
    }}
}}
'''

    status_effect_manager_cs = f'''using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace {ns}
{{
    /// <summary>
    /// Runtime status effect manager. Handles applying, ticking, stacking,
    /// and removing status effects with CC diminishing returns and brand
    /// combo interactions.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    public class StatusEffectManager : MonoBehaviour
    {{
        // =================================================================
        // Events
        // =================================================================

        /// <summary>Fired when any effect is first applied.</summary>
        public event Action<StatusEffectInstance> OnEffectApplied;
        /// <summary>Fired when an effect is removed (expired or manual).</summary>
        public event Action<StatusEffectInstance> OnEffectRemoved;
        /// <summary>Fired when an existing effect gains a stack.</summary>
        public event Action<StatusEffectInstance> OnEffectStacked;
        /// <summary>Fired when a crowd control effect is applied.</summary>
        public event Action<CrowdControlType, float> OnCCApplied;

        // =================================================================
        // State
        // =================================================================

        private readonly Dictionary<string, List<StatusEffectInstance>> activeEffects =
            new Dictionary<string, List<StatusEffectInstance>>();

        private readonly Dictionary<CrowdControlType, float> ccImmunityTimers =
            new Dictionary<CrowdControlType, float>();

        private readonly Dictionary<string, GameObject> activeVFX =
            new Dictionary<string, GameObject>();

        // =================================================================
        // Public API
        // =================================================================

        /// <summary>Current health (assign or bind to your health system).</summary>
        [Header("Health (bind to your health system)")]
        public float currentHealth = 100f;
        public float maxHealth = 100f;

        /// <summary>
        /// Apply a status effect to this target.
        /// Handles stacking, CC immunity, and brand combos.
        /// </summary>
        public void ApplyEffect(StatusEffect effect, GameObject target, GameObject source)
        {{
            if (effect == null) return;

            // --- CC diminishing returns check ---
            if (effect.crowdControlType != CrowdControlType.None)
            {{
                if (ccImmunityTimers.TryGetValue(effect.crowdControlType, out float remaining) && remaining > 0f)
                {{
                    // Immune -- skip this CC
                    return;
                }}
            }}

            // --- Check for brand combo interactions ---
            CheckBrandCombos(effect, source);

            string key = effect.effectName;

            // --- Stacking logic ---
            if (activeEffects.TryGetValue(key, out var instances) && instances.Count > 0)
            {{
                if (effect.isStackable)
                {{
                    var existing = instances[0];
                    if (existing.CurrentStacks < effect.maxStacks)
                    {{
                        existing.CurrentStacks++;
                        existing.RemainingDuration = effect.duration; // refresh
                        OnEffectStacked?.Invoke(existing);
                        return;
                    }}
                    else
                    {{
                        // At max stacks -- just refresh duration
                        existing.RemainingDuration = effect.duration;
                        return;
                    }}
                }}
                else
                {{
                    // Non-stackable: refresh duration
                    instances[0].RemainingDuration = effect.duration;
                    return;
                }}
            }}

            // --- Apply new effect ---
            var instance = new StatusEffectInstance(effect, source);
            if (!activeEffects.ContainsKey(key))
                activeEffects[key] = new List<StatusEffectInstance>();
            activeEffects[key].Add(instance);
            instance.Apply(this);

            // --- Apply CC ---
            if (effect.crowdControlType != CrowdControlType.None)
            {{
                OnCCApplied?.Invoke(effect.crowdControlType, effect.duration);
            }}

            OnEffectApplied?.Invoke(instance);
        }}

        /// <summary>Remove all instances of an effect by name.</summary>
        public void RemoveEffect(string effectName)
        {{
            if (activeEffects.TryGetValue(effectName, out var instances))
            {{
                foreach (var inst in instances)
                {{
                    HandleEffectRemoval(inst);
                }}
                activeEffects.Remove(effectName);
            }}
        }}

        /// <summary>Remove all active effects.</summary>
        public void RemoveAllEffects()
        {{
            foreach (var kvp in activeEffects)
            {{
                foreach (var inst in kvp.Value)
                {{
                    HandleEffectRemoval(inst);
                }}
            }}
            activeEffects.Clear();
        }}

        /// <summary>Check if an effect is currently active.</summary>
        public bool HasEffect(string effectName)
        {{
            return activeEffects.TryGetValue(effectName, out var instances) && instances.Count > 0;
        }}

        /// <summary>Get current stack count for an effect. Returns 0 if not active.</summary>
        public int GetStacks(string effectName)
        {{
            if (activeEffects.TryGetValue(effectName, out var instances) && instances.Count > 0)
                return instances[0].CurrentStacks;
            return 0;
        }}

        /// <summary>Get all stat modifiers currently active on this entity.</summary>
        public List<StatModifier> GetAllActiveModifiers()
        {{
            var mods = new List<StatModifier>();
            foreach (var kvp in activeEffects)
            {{
                foreach (var inst in kvp.Value)
                {{
                    foreach (var mod in inst.Definition.statModifiers)
                    {{
                        // Scale flat modifiers by stack count
                        var scaled = mod;
                        if (mod.modifierType == ModifierType.Flat)
                            scaled.value = mod.value * inst.CurrentStacks;
                        else
                            scaled.value = mod.value * inst.CurrentStacks;
                        mods.Add(scaled);
                    }}
                }}
            }}
            return mods;
        }}

        /// <summary>Get effective movement speed multiplier from all active effects.</summary>
        public float GetMovementSpeedMultiplier()
        {{
            float multiplier = 1f;
            foreach (var kvp in activeEffects)
            {{
                foreach (var inst in kvp.Value)
                {{
                    multiplier *= inst.Definition.movementSpeedModifier;
                }}
            }}
            return multiplier;
        }}

        // =================================================================
        // Update Loop
        // =================================================================

        private void Update()
        {{
            float dt = Time.deltaTime;

            // Tick CC immunity timers
            var ccKeys = new List<CrowdControlType>(ccImmunityTimers.Keys);
            foreach (var key in ccKeys)
            {{
                ccImmunityTimers[key] -= dt;
                if (ccImmunityTimers[key] <= 0f)
                    ccImmunityTimers.Remove(key);
            }}

            // Tick all active effects
            var effectKeys = new List<string>(activeEffects.Keys);
            foreach (var key in effectKeys)
            {{
                if (!activeEffects.TryGetValue(key, out var instances)) continue;

                for (int i = instances.Count - 1; i >= 0; i--)
                {{
                    var inst = instances[i];
                    inst.Tick(dt, this);

                    if (inst.IsExpired)
                    {{
                        HandleEffectRemoval(inst);
                        instances.RemoveAt(i);
                    }}
                }}

                if (instances.Count == 0)
                    activeEffects.Remove(key);
            }}
        }}

        // =================================================================
        // Internal Helpers
        // =================================================================

        private void HandleEffectRemoval(StatusEffectInstance inst)
        {{
            // Start CC immunity window if this was a CC effect
            if (inst.Definition.crowdControlType != CrowdControlType.None
                && inst.Definition.ccImmunityWindow > 0f)
            {{
                ccImmunityTimers[inst.Definition.crowdControlType] = inst.Definition.ccImmunityWindow;
            }}

            inst.Remove(this);
            OnEffectRemoved?.Invoke(inst);
        }}

        /// <summary>Apply damage to this entity (override for your health system).</summary>
        public void ApplyDamage(float amount, GameObject source)
        {{
            currentHealth = Mathf.Max(0f, currentHealth - amount);
        }}

        /// <summary>Apply healing to this entity (override for your health system).</summary>
        public void ApplyHealing(float amount, GameObject source)
        {{
            currentHealth = Mathf.Min(maxHealth, currentHealth + amount);
        }}

        /// <summary>Register a spawned VFX instance for later cleanup.</summary>
        public void RegisterVFX(string effectName, GameObject vfxInstance)
        {{
            if (activeVFX.ContainsKey(effectName) && activeVFX[effectName] != null)
                Destroy(activeVFX[effectName]);
            activeVFX[effectName] = vfxInstance;
        }}

        /// <summary>Destroy VFX associated with an effect.</summary>
        public void DestroyVFX(string effectName)
        {{
            if (activeVFX.TryGetValue(effectName, out var vfx) && vfx != null)
            {{
                Destroy(vfx);
                activeVFX.Remove(effectName);
            }}
        }}

        // =================================================================
        // Brand Combo Interactions
        // =================================================================

        /// <summary>
        /// Check and trigger brand-specific combo interactions when a new
        /// effect is applied on top of existing effects.
        /// </summary>
        private void CheckBrandCombos(StatusEffect incomingEffect, GameObject source)
        {{
            // SURGE + VENOM = "Corrosive" combo: bonus damage + defense shred
            if (incomingEffect.brand == Brand.SURGE && HasBrandEffect(Brand.VENOM))
            {{
                ApplyDamage(15f, source);
                Debug.Log("[StatusEffect] COMBO: Corrosive (SURGE + VENOM) - bonus damage!");
            }}
            else if (incomingEffect.brand == Brand.VENOM && HasBrandEffect(Brand.SURGE))
            {{
                ApplyDamage(15f, source);
                Debug.Log("[StatusEffect] COMBO: Corrosive (VENOM + SURGE) - bonus damage!");
            }}

            // RUIN + SAVAGE = "Hemorrhage" combo: doubled bleed damage
            if (incomingEffect.brand == Brand.RUIN && HasBrandEffect(Brand.SAVAGE))
            {{
                Debug.Log("[StatusEffect] COMBO: Hemorrhage (RUIN + SAVAGE) - doubled bleed!");
                // Double existing SAVAGE bleed stacks damage
                BoostBrandDamage(Brand.SAVAGE, 2f);
            }}
            else if (incomingEffect.brand == Brand.SAVAGE && HasBrandEffect(Brand.RUIN))
            {{
                Debug.Log("[StatusEffect] COMBO: Hemorrhage (SAVAGE + RUIN) - doubled bleed!");
            }}

            // VOID + DREAD = "Abyss" combo: extended CC duration
            if (incomingEffect.brand == Brand.VOID && HasBrandEffect(Brand.DREAD))
            {{
                Debug.Log("[StatusEffect] COMBO: Abyss (VOID + DREAD) - extended CC!");
            }}
            else if (incomingEffect.brand == Brand.DREAD && HasBrandEffect(Brand.VOID))
            {{
                Debug.Log("[StatusEffect] COMBO: Abyss (DREAD + VOID) - extended CC!");
            }}

            // GRACE + MEND = "Sanctuary" combo: burst heal
            if (incomingEffect.brand == Brand.GRACE && HasBrandEffect(Brand.MEND))
            {{
                ApplyHealing(25f, source);
                Debug.Log("[StatusEffect] COMBO: Sanctuary (GRACE + MEND) - burst heal!");
            }}
            else if (incomingEffect.brand == Brand.MEND && HasBrandEffect(Brand.GRACE))
            {{
                ApplyHealing(25f, source);
                Debug.Log("[StatusEffect] COMBO: Sanctuary (MEND + GRACE) - burst heal!");
            }}

            // IRON + LEECH = "Fortified Drain": armor boost while draining
            if (incomingEffect.brand == Brand.IRON && HasBrandEffect(Brand.LEECH))
            {{
                Debug.Log("[StatusEffect] COMBO: Fortified Drain (IRON + LEECH)!");
            }}
            else if (incomingEffect.brand == Brand.LEECH && HasBrandEffect(Brand.IRON))
            {{
                Debug.Log("[StatusEffect] COMBO: Fortified Drain (LEECH + IRON)!");
            }}
        }}

        /// <summary>Check if any active effect has the given brand.</summary>
        private bool HasBrandEffect(Brand brand)
        {{
            foreach (var kvp in activeEffects)
            {{
                foreach (var inst in kvp.Value)
                {{
                    if (inst.Definition.brand == brand) return true;
                }}
            }}
            return false;
        }}

        /// <summary>Boost DoT damage for all effects of a given brand.</summary>
        private void BoostBrandDamage(Brand brand, float multiplier)
        {{
            foreach (var kvp in activeEffects)
            {{
                foreach (var inst in kvp.Value)
                {{
                    if (inst.Definition.brand == brand)
                    {{
                        // We boost via extra immediate damage since SO is shared
                        float boosted = inst.Definition.damagePerTick * inst.CurrentStacks * (multiplier - 1f);
                        if (boosted > 0f)
                            ApplyDamage(boosted, inst.Source);
                    }}
                }}
            }}
        }}

        // =================================================================
        // Brand Preset Factory (10 built-in presets)
        // =================================================================

        /// <summary>
        /// Create a runtime StatusEffect instance (not saved as asset) for
        /// the given brand preset.  Useful for quick prototyping.
        /// </summary>
        public static StatusEffect CreateBrandPreset(Brand brand)
        {{
            var effect = ScriptableObject.CreateInstance<StatusEffect>();

            switch (brand)
            {{
                case Brand.IRON:
                    effect.effectName = "ArmorUp";
                    effect.description = "IRON brand: increased defense.";
                    effect.brand = Brand.IRON;
                    effect.duration = 10f;
                    effect.tickInterval = 0f;
                    effect.isStackable = false;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.Defense, modifierType = ModifierType.Flat, value = 20f }}
                    }};
                    break;

                case Brand.SAVAGE:
                    effect.effectName = "Bleed";
                    effect.description = "SAVAGE brand: bleeding damage over time.";
                    effect.brand = Brand.SAVAGE;
                    effect.duration = 5f;
                    effect.tickInterval = 1f;
                    effect.isStackable = true;
                    effect.maxStacks = 3;
                    effect.damagePerTick = 3f;
                    break;

                case Brand.SURGE:
                    effect.effectName = "Electrified";
                    effect.description = "SURGE brand: stun then increased damage taken.";
                    effect.brand = Brand.SURGE;
                    effect.duration = 5f;
                    effect.tickInterval = 0f;
                    effect.crowdControlType = CrowdControlType.Stun;
                    effect.ccImmunityWindow = {default_cc_immunity_window}f;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.DamageTaken, modifierType = ModifierType.Percent, value = 15f }}
                    }};
                    break;

                case Brand.VENOM:
                    effect.effectName = "Poison";
                    effect.description = "VENOM brand: poison damage and reduced healing.";
                    effect.brand = Brand.VENOM;
                    effect.duration = 8f;
                    effect.tickInterval = 1f;
                    effect.damagePerTick = 2f;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.HealingReceived, modifierType = ModifierType.Percent, value = -20f }}
                    }};
                    break;

                case Brand.DREAD:
                    effect.effectName = "Fear";
                    effect.description = "DREAD brand: fear and reduced attack.";
                    effect.brand = Brand.DREAD;
                    effect.duration = 5f;
                    effect.tickInterval = 0f;
                    effect.crowdControlType = CrowdControlType.Fear;
                    effect.ccImmunityWindow = {default_cc_immunity_window}f;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.Attack, modifierType = ModifierType.Percent, value = -15f }}
                    }};
                    break;

                case Brand.LEECH:
                    effect.effectName = "Drain";
                    effect.description = "LEECH brand: damage over time, heals source.";
                    effect.brand = Brand.LEECH;
                    effect.duration = 6f;
                    effect.tickInterval = 1f;
                    effect.damagePerTick = 1.5f;
                    break;

                case Brand.GRACE:
                    effect.effectName = "Blessed";
                    effect.description = "GRACE brand: increased healing and defense.";
                    effect.brand = Brand.GRACE;
                    effect.duration = 8f;
                    effect.tickInterval = 0f;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.HealingReceived, modifierType = ModifierType.Percent, value = 25f }},
                        new StatModifier {{ statType = StatType.Defense, modifierType = ModifierType.Percent, value = 10f }}
                    }};
                    break;

                case Brand.MEND:
                    effect.effectName = "Regen";
                    effect.description = "MEND brand: healing over time.";
                    effect.brand = Brand.MEND;
                    effect.duration = 6f;
                    effect.tickInterval = 1f;
                    effect.healPerTick = 3f;
                    break;

                case Brand.RUIN:
                    effect.effectName = "Shatter";
                    effect.description = "RUIN brand: reduced defense.";
                    effect.brand = Brand.RUIN;
                    effect.duration = 6f;
                    effect.tickInterval = 0f;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.Defense, modifierType = ModifierType.Percent, value = -30f }}
                    }};
                    break;

                case Brand.VOID:
                    effect.effectName = "VoidMark";
                    effect.description = "VOID brand: silence and increased VOID damage taken.";
                    effect.brand = Brand.VOID;
                    effect.duration = 10f;
                    effect.tickInterval = 0f;
                    effect.crowdControlType = CrowdControlType.Silence;
                    effect.ccImmunityWindow = {default_cc_immunity_window}f;
                    effect.statModifiers = new System.Collections.Generic.List<StatModifier>
                    {{
                        new StatModifier {{ statType = StatType.DamageTaken, modifierType = ModifierType.Percent, value = 20f }}
                    }};
                    break;

                default:
                    effect.effectName = "Unknown";
                    effect.description = "No brand preset.";
                    break;
            }}

            return effect;
        }}
    }}
}}
'''

    return (status_effect_so_cs, status_effect_manager_cs)
