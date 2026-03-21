"""Gameplay C# template generators for Unity mob AI systems.

Each function returns a complete C# source string for a runtime
MonoBehaviour or ScriptableObject script. These are placed in the Unity
project's Assets/Scripts/Runtime/ directory -- they are NOT editor scripts
and must NEVER reference the UnityEditor namespace.

Exports:
    generate_mob_controller_script     -- MOB-01: FSM state machine controller
    generate_aggro_system_script       -- MOB-02: OverlapSphereNonAlloc detection
    generate_patrol_route_script       -- MOB-03: NavMeshAgent waypoint patrol
    generate_spawn_system_script       -- MOB-04: Wave spawning with area bounds
    generate_behavior_tree_script      -- MOB-05: ScriptableObject behavior tree
    generate_combat_ability_script     -- MOB-06: Ability prefab + executor
    generate_projectile_script         -- MOB-07: Trajectory + trail + impact

Validators:
    _validate_mob_params               -- detection/attack range, speeds
    _validate_spawn_params             -- max count, respawn timer, radius
    _validate_ability_params           -- cooldown, damage
    _validate_projectile_params        -- velocity, trajectory type
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

        float distToPlayer = Vector3.Distance(transform.position, playerTransform.position);
        float distToSpawn = Vector3.Distance(transform.position, spawnPosition);
        float healthPct = currentHealth / maxHealth;

        switch (currentState)
        {{
            case MobState.Patrol:
                agent.speed = patrolSpeed;
                if (distToPlayer <= detectionRange)
                    currentState = MobState.Aggro;
                break;

            case MobState.Aggro:
                if (distToSpawn > leashDistance)
                {{
                    currentState = MobState.ReturnToPatrol;
                    break;
                }}
                currentState = MobState.Chase;
                break;

            case MobState.Chase:
                agent.speed = chaseSpeed;
                agent.SetDestination(playerTransform.position);
                if (distToSpawn > leashDistance)
                {{
                    currentState = MobState.ReturnToPatrol;
                    break;
                }}
                if (healthPct <= fleeHealthPercent)
                {{
                    currentState = MobState.Flee;
                    break;
                }}
                if (distToPlayer <= attackRange)
                    currentState = MobState.Attack;
                else if (distToPlayer > detectionRange)
                    currentState = MobState.ReturnToPatrol;
                break;

            case MobState.Attack:
                agent.SetDestination(transform.position); // Stop moving
                if (healthPct <= fleeHealthPercent)
                {{
                    currentState = MobState.Flee;
                    break;
                }}
                if (distToPlayer > attackRange)
                    currentState = MobState.Chase;
                if (distToSpawn > leashDistance)
                    currentState = MobState.ReturnToPatrol;
                break;

            case MobState.Flee:
                agent.speed = chaseSpeed;
                Vector3 fleeDir = (transform.position - playerTransform.position).normalized;
                agent.SetDestination(transform.position + fleeDir * detectionRange);
                if (distToSpawn > leashDistance)
                    currentState = MobState.ReturnToPatrol;
                break;

            case MobState.ReturnToPatrol:
                agent.speed = patrolSpeed;
                agent.SetDestination(spawnPosition);
                if (Vector3.Distance(transform.position, spawnPosition) < 1.5f)
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
                        spawnPos.y = transform.position.y; // Keep on ground plane
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

        // Hitbox damage check
        Collider[] hits = Physics.OverlapSphere(transform.position, ability.hitboxSize);
        foreach (var hit in hits)
        {{
            if (hit.gameObject == gameObject) continue;
            // Send damage message
            hit.SendMessage("TakeDamage", ability.damage, SendMessageOptions.DontRequireReceiver);
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

        // Notify hit target
        other.SendMessage("OnProjectileHit", velocity, SendMessageOptions.DontRequireReceiver);

        // Destroy projectile
        Destroy(gameObject);
    }}
}}
'''
