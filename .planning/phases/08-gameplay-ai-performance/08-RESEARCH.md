# Phase 8: Gameplay AI & Performance - Research

**Researched:** 2026-03-19
**Domain:** Unity C# template generation for mob AI systems, spawn systems, behavior trees, combat abilities, projectile systems, scene profiling, LOD automation, lightmap baking, asset auditing, and build automation
**Confidence:** HIGH

## Summary

Phase 8 adds two new compound MCP tools to unity_server.py: `unity_gameplay` (MOB-01 through MOB-07) and `unity_performance` (PERF-01 through PERF-05). Both follow the exact same architecture as existing compound tools (unity_vfx, unity_audio, unity_scene, unity_ui, unity_editor) -- Python functions that generate complete C# editor scripts, write them to the Unity project via `_write_to_unity()`, and return JSON with next_steps for mcp-unity execution.

The gameplay tool generates runtime MonoBehaviour scripts (mob controllers, spawn systems, combat abilities, projectile systems) plus ScriptableObject behavior tree scaffolding. The performance tool generates editor scripts for profiling, LOD automation, lightmap baking, asset auditing, and build pipeline automation. All C# code is produced via Python f-string template functions in dedicated template files, following the pattern established in `scene_templates.py`, `vfx_templates.py`, and `audio_templates.py`.

This phase is purely additive -- no existing code needs modification beyond adding imports and two new compound tool functions to `unity_server.py`. The established `_sanitize_cs_string` / `_sanitize_cs_identifier` security functions must be used for all user-supplied values interpolated into C# templates. Pure-logic helper functions (parameter validation, threshold analysis, recommendation generation) must be extracted for unit testing without Unity runtime.

**Primary recommendation:** Create two new template files (`gameplay_templates.py` and `performance_templates.py`) in `shared/unity_templates/`, wire them into `unity_server.py` as two compound tools, and write test files that verify C# output contains expected Unity API calls and parameter substitutions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- State machine based: patrol (waypoints), aggro (detection radius), chase, attack, flee (health threshold)
- Configurable parameters per mob type: detection range, attack range, leash distance, patrol speed, aggro speed
- Waypoint patrol with wait times at each point
- Aggro triggers on player proximity within detection radius
- Leash distance forces return to patrol if player gets too far
- Ability prefabs combine: animation trigger + VFX prefab + hitbox collider + damage data + sound effect
- Projectile systems: velocity, trajectory (straight/arc/homing), trail VFX, impact VFX
- Cooldown system with ability queuing
- Spawn point components with: max count, respawn timer, area bounds, conditions
- Wave-based spawning with configurable wave delays
- Spawn conditions: time of day, player proximity, quest state
- Scene profiler reports: frame time, draw calls, batches, triangle count, memory usage
- Actionable recommendations based on threshold analysis
- Before/after comparison for optimization verification
- LOD chain generation (reuses existing pipeline_generate_lods)
- Lightmap baking with configurable quality settings
- Asset audit: unused assets, oversized textures, duplicate materials
- Occlusion culling setup

### Claude's Discretion
All implementation choices are at Claude's discretion -- autonomous execution mode.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MOB-01 | Mob controller generation (patrol, chase, attack, flee state machine) | C# template with enum-based FSM, NavMeshAgent integration, configurable state parameters |
| MOB-02 | Aggro system (detection range, decay, threat table, leash distance) | Sphere overlap detection, threat decay timer, leash return-to-patrol logic in controller template |
| MOB-03 | Patrol routes with waypoints, dwell times, random deviation | Transform[] waypoints, per-point dwell time, NavMeshAgent.SetDestination with random offset |
| MOB-04 | Spawn system (max count, respawn timer, conditions, area bounds) | SpawnPoint MonoBehaviour + SpawnManager, Random.insideUnitSphere for area bounds, condition checks |
| MOB-05 | Behavior tree scaffolding (ScriptableObject with nodes) | Abstract BT_Node ScriptableObject base, Sequence/Selector/Leaf node types, tree runner MonoBehaviour |
| MOB-06 | Combat ability prefab (animation + VFX + hitbox + damage + sound) | CombatAbility ScriptableObject data class + AbilityExecutor MonoBehaviour with cooldown queue |
| MOB-07 | Projectile system (trajectory, trail VFX, impact effect) | Projectile MonoBehaviour with trajectory enum (Straight/Arc/Homing), Rigidbody or transform-based movement |
| PERF-01 | Scene profiling (frame time, draw calls, batches, tris, memory) | ProfilerRecorder API for render stats, FrameTimingManager for frame times, JSON report output |
| PERF-02 | LODGroup auto-generation for scene meshes | LODGroup.SetLODs with MeshRenderer assignment, configurable screen percentage thresholds |
| PERF-03 | Lightmap baking with progress monitoring | Lightmapping.BakeAsync + isRunning polling, LightmapEditorSettings configuration |
| PERF-04 | Asset audit (unused assets, oversized textures, uncompressed audio) | AssetDatabase.GetAllAssetPaths + dependency walk, TextureImporter size checks, AudioImporter format checks |
| PERF-05 | Build pipeline automation with size report | BuildPipeline.BuildPlayer + BuildReport parsing, PackedAssets size analysis, JSON output |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastMCP | 3.0+ | MCP server framework | Already used; all servers built on this |
| Python f-string templates | N/A | C# code generation | Established pattern in all existing template files |
| `_write_to_unity()` | N/A | File writing to Unity project | Existing helper with path traversal protection |
| `_sanitize_cs_string` / `_sanitize_cs_identifier` | N/A | Security for C# interpolation | Established pattern from scene_templates.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | existing | Template output verification | All new template functions get assertion tests |
| Unity NavMeshAgent API | Unity 2022+ | AI navigation in generated C# | Mob controller patrol/chase pathfinding |
| Unity ProfilerRecorder API | Unity 2020.2+ | Performance metrics in generated C# | Scene profiler draw calls/batches/memory |
| Unity Lightmapping API | Unity 2022+ | Lightmap baking in generated C# | PERF-03 async bake with progress |
| Unity BuildPipeline API | Unity 2022+ | Build automation in generated C# | PERF-05 build + size report |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Enum-based FSM | Full behavior tree for all mobs | FSM is simpler, BT scaffolding provided separately via MOB-05 |
| ProfilerRecorder API | UnityStats class | ProfilerRecorder works in Release builds; UnityStats is editor-only |
| Manual LODGroup setup | AutoLOD package | AutoLOD requires package install; manual LODGroup.SetLODs is zero-dependency |

## Architecture Patterns

### New Files Required
```
Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/
    gameplay_templates.py       # MOB-01 through MOB-07 template generators
    performance_templates.py    # PERF-01 through PERF-05 template generators

Tools/mcp-toolkit/tests/
    test_gameplay_templates.py     # Unit tests for gameplay C# template output
    test_performance_templates.py  # Unit tests for performance C# template output
```

### Modified Files
```
Tools/mcp-toolkit/src/veilbreakers_mcp/
    unity_server.py            # Add imports + unity_gameplay + unity_performance compound tools
```

### Pattern 1: Compound Tool with Literal Actions (Established)
**What:** Single `@mcp.tool()` function with `action: Literal[...]` parameter dispatching to private handler functions
**When to use:** Always -- ARCH-01 requires max 26 tool definitions across all servers
**Example (from existing code):**
```python
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
    ],
    ...
) -> str:
```

### Pattern 2: C# Template Generator Function (Established)
**What:** Python function returning complete C# source string via f-string interpolation
**When to use:** Every template generator
**Key conventions:**
- Function name: `generate_{feature}_script(params) -> str`
- C# class name: `VeilBreakers_{FeatureName}`
- MenuItem path: `[MenuItem("VeilBreakers/Gameplay/...")] ` or `[MenuItem("VeilBreakers/Performance/...")]`
- Result file: `File.WriteAllText("Temp/vb_result.json", json)`
- Error handling: try/catch wrapping all logic, writing error to vb_result.json
- User inputs sanitized: `_sanitize_cs_string()` for string values, `_sanitize_cs_identifier()` for identifiers

### Pattern 3: Pure-Logic Extraction for Testing (Established)
**What:** Extract validation/computation logic into standalone Python functions testable without Unity
**When to use:** Threshold analysis, recommendation generation, parameter validation
**Examples for this phase:**
- `_validate_mob_params()` -- check detection_range > attack_range, speeds positive
- `_analyze_profile_thresholds()` -- compare profiler data against budgets, generate recommendations
- `_classify_asset_issues()` -- categorize oversized textures, uncompressed audio
- `_validate_lod_screen_percentages()` -- ensure descending order

### Pattern 4: Runtime vs Editor Scripts (New for this phase)
**What:** Some generated C# scripts are runtime MonoBehaviours (mob AI, spawn systems), others are Editor-only
**When to use:**
- **Runtime scripts** (Assets/Scripts/Runtime/): MobController, SpawnManager, CombatAbility, Projectile, BehaviorTree nodes
- **Editor scripts** (Assets/Editor/Generated/): SceneProfiler, LODSetup, LightmapBaker, AssetAuditor, BuildAutomation
**Key difference:** Runtime scripts use `using UnityEngine;` + MonoBehaviour/ScriptableObject. Editor scripts additionally use `using UnityEditor;` + `[MenuItem(...)]`.

### Anti-Patterns to Avoid
- **Monolithic mob controller:** Do NOT put all AI logic in one giant script. Separate the state machine controller from patrol waypoint data, aggro system, and combat abilities.
- **Hardcoded thresholds in profiler:** Do NOT embed performance budgets as constants. Make them configurable parameters so users can set their own targets.
- **String concatenation for JSON in C#:** The existing templates use escaped JSON string building (`"{{\\"status\\": \\"success\\", ...}}"`). Continue this pattern for consistency.
- **Editor-only API in runtime scripts:** Do NOT use `AssetDatabase`, `EditorUtility`, or `MenuItem` in runtime MonoBehaviours. These only compile in the Editor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AI pathfinding | Custom A* or navigation | NavMeshAgent.SetDestination | Unity NavMesh handles obstacles, slopes, agents natively |
| Sphere overlap detection | Manual distance checks | Physics.OverlapSphere | GPU-accelerated, handles layers, filters |
| LOD mesh simplification | Custom decimation | LODGroup.SetLODs with existing mesh LODs | Phase already has pipeline_generate_lods in Blender |
| Build report parsing | Custom file size counting | BuildReport.packedAssets from BuildPipeline | Official API provides per-asset size breakdown |
| Lightmap progress tracking | Custom timer polling | Lightmapping.isRunning + bakeCompleted callback | Built-in API handles all edge cases |
| Projectile physics | Custom euler integration | Rigidbody.AddForce for arc, transform.Translate for straight | Physics engine handles collisions natively |

**Key insight:** The generated C# templates should leverage Unity's built-in systems (NavMesh, Physics, LODGroup, Lightmapping, BuildPipeline) rather than implementing custom alternatives. Our job is to generate well-configured scripts that wire these systems together.

## Common Pitfalls

### Pitfall 1: NavMeshAgent vs Transform Movement Conflict
**What goes wrong:** Setting transform.position directly while NavMeshAgent is active causes jittering or teleporting
**Why it happens:** NavMeshAgent controls the transform; manual position changes conflict
**How to avoid:** Always use `agent.SetDestination()` or `agent.Move()`, never `transform.position = ...` while agent is enabled. Disable agent before teleporting.
**Warning signs:** Mob jitters between two positions, or NavMesh warnings in console

### Pitfall 2: OverlapSphere in Update Creates Garbage
**What goes wrong:** Calling `Physics.OverlapSphere()` every frame allocates arrays, causing GC spikes
**Why it happens:** OverlapSphere returns new Collider[] each call
**How to avoid:** Use `Physics.OverlapSphereNonAlloc()` with a pre-allocated buffer, or check on a timer (every 0.2s) instead of every frame
**Warning signs:** GC.Alloc spikes in profiler correlated with mob count

### Pitfall 3: Editor Script API in Runtime Context
**What goes wrong:** Scripts using `AssetDatabase`, `EditorUtility`, `MenuItem`, or `using UnityEditor` fail to compile in builds
**Why it happens:** UnityEditor namespace is stripped from non-Editor builds
**How to avoid:** Runtime scripts (MobController, SpawnManager, etc.) must NEVER reference UnityEditor. Use `#if UNITY_EDITOR` guards if absolutely needed, but prefer clean separation.
**Warning signs:** Build errors referencing UnityEditor types

### Pitfall 4: Lightmapping.BakeAsync Requires OnDemand Mode
**What goes wrong:** BakeAsync returns false and prints warning
**Why it happens:** BakeAsync only works when `Lightmapping.giWorkflowMode == GIWorkflowMode.OnDemand`
**How to avoid:** Set `Lightmapping.giWorkflowMode = Lightmapping.GIWorkflowMode.OnDemand` before calling BakeAsync
**Warning signs:** BakeAsync returns false, no bake starts

### Pitfall 5: LODGroup Screen Percentages Must Descend
**What goes wrong:** LODs display incorrectly or Unity throws errors
**Why it happens:** LOD[0] must have the highest screen percentage, descending to LOD[n]
**How to avoid:** Validate percentages in Python pure-logic function before generating C#. Typical defaults: LOD0=60%, LOD1=30%, LOD2=15%, Culled=1%.
**Warning signs:** Objects pop between LODs at wrong distances

### Pitfall 6: Build Report Null Reference
**What goes wrong:** Accessing BuildReport properties after a failed build throws NullReferenceException
**Why it happens:** BuildPipeline.BuildPlayer returns a report even on failure, but some sub-objects may be null
**How to avoid:** Check `report.summary.result == BuildResult.Succeeded` before accessing packedAssets
**Warning signs:** NullReferenceException when build fails

## Code Examples

### Mob Controller State Machine (MOB-01) -- Template Output Pattern
```csharp
// Generated by generate_mob_controller_script()
using UnityEngine;
using UnityEngine.AI;

public class VeilBreakers_MobController_{name} : MonoBehaviour
{
    public enum MobState { Patrol, Aggro, Chase, Attack, Flee, ReturnToPatrol }

    [Header("Detection")]
    public float detectionRange = {detection_range}f;
    public float attackRange = {attack_range}f;
    public float leashDistance = {leash_distance}f;

    [Header("Movement")]
    public float patrolSpeed = {patrol_speed}f;
    public float chaseSpeed = {chase_speed}f;

    [Header("Combat")]
    public float fleeHealthPercent = {flee_health_pct}f;

    private NavMeshAgent agent;
    private MobState currentState = MobState.Patrol;
    private Transform playerTransform;
    private Vector3 spawnPosition;
    // ... state machine Update() with switch(currentState)
}
```

### Scene Profiler (PERF-01) -- Template Output Pattern
```csharp
// Generated by generate_scene_profiler_script()
using UnityEngine;
using UnityEditor;
using Unity.Profiling;
using System.IO;

public static class VeilBreakers_SceneProfiler
{
    [MenuItem("VeilBreakers/Performance/Profile Scene")]
    public static void Execute()
    {
        // Collect metrics
        var stats = new {
            frameTime = Time.unscaledDeltaTime * 1000f,
            drawCalls = UnityStats.drawCalls,
            batches = UnityStats.batches,
            triangles = UnityStats.triangles,
            vertices = UnityStats.vertices,
            usedTextureMemory = UnityStats.usedTextureMemorySize,
            renderTextureCount = UnityStats.renderTextureCount,
            totalMemoryMB = UnityEngine.Profiling.Profiler.GetTotalAllocatedMemoryLong() / (1024f * 1024f),
        };
        // Write to Temp/vb_result.json with recommendations
    }
}
```

### LODGroup Auto-Setup (PERF-02) -- Template Output Pattern
```csharp
// Generated by generate_lod_setup_script()
using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_LODSetup
{
    [MenuItem("VeilBreakers/Performance/Setup LODGroups")]
    public static void Execute()
    {
        var meshRenderers = FindObjectsOfType<MeshRenderer>();
        int configured = 0;
        foreach (var renderer in meshRenderers)
        {
            var go = renderer.gameObject;
            if (go.GetComponent<LODGroup>() != null) continue;

            var lodGroup = go.AddComponent<LODGroup>();
            var lods = new LOD[{lod_count}];
            lods[0] = new LOD({screen_pct_0}f, new Renderer[] { renderer });
            // Additional LOD levels reference LOD meshes if available
            lodGroup.SetLODs(lods);
            lodGroup.RecalculateBounds();
            configured++;
        }
        // Write result JSON
    }
}
```

### Spawn System (MOB-04) -- Runtime Script Pattern
```csharp
// Generated by generate_spawn_system_script()
using UnityEngine;
using System.Collections;
using System.Collections.Generic;

public class VeilBreakers_SpawnManager : MonoBehaviour
{
    [System.Serializable]
    public class SpawnWave
    {
        public GameObject[] prefabs;
        public int count;
        public float delayBetweenSpawns = 0.5f;
    }

    public SpawnWave[] waves;
    public float waveCooldown = {wave_cooldown}f;
    public int maxAlive = {max_count};
    public float respawnTimer = {respawn_timer}f;
    public float spawnRadius = {spawn_radius}f;

    private List<GameObject> aliveInstances = new List<GameObject>();
    private int currentWave = 0;
    // ... wave spawning coroutine logic
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UnityStats.drawCalls (editor-only) | ProfilerRecorder API | Unity 2020.2+ | Works in Release builds, more metrics available |
| Lightmapping.Bake (synchronous) | Lightmapping.BakeAsync + isRunning | Unity 2020+ | Non-blocking bake with progress monitoring |
| Manual LOD mesh creation | LODGroup.SetLODs programmatic setup | Stable since Unity 2017 | Standard API, no packages needed |
| Physics.OverlapSphere (allocating) | Physics.OverlapSphereNonAlloc | Unity 2017+ | Zero-allocation for per-frame detection |
| BuildReport manual file parsing | BuildReport from BuildPipeline.BuildPlayer | Unity 2018.1+ | Structured API with PackedAssets breakdown |

**Deprecated/outdated:**
- `UnityStats` class: Still works in Editor but prefer ProfilerRecorder for cross-platform consistency
- `Lightmapping.Bake()` synchronous: Still functional but blocks the editor; use BakeAsync for better UX

## Open Questions

1. **UnityStats vs ProfilerRecorder for Editor Scripts**
   - What we know: ProfilerRecorder is the modern API. UnityStats works only in Editor but is simpler for MenuItem scripts.
   - What's unclear: Whether the profiler script needs to work in play mode or editor-only.
   - Recommendation: Use UnityStats for the editor MenuItem profiler (PERF-01 is editor-only by nature). Add a comment noting ProfilerRecorder alternative for runtime use.

2. **LOD Mesh References for PERF-02**
   - What we know: LODGroup.SetLODs needs Renderer references for each LOD level.
   - What's unclear: Whether LOD meshes will already exist from Blender pipeline_generate_lods, or if the script should create simplified meshes in Unity.
   - Recommendation: Generate the LODGroup setup script assuming LOD meshes exist as sibling GameObjects with _LOD0/_LOD1/_LOD2 naming convention (matching Blender pipeline output). If not found, assign only LOD0 with the original renderer.

3. **Occlusion Culling Setup**
   - What we know: CONTEXT.md mentions occlusion culling setup in auto-optimization.
   - What's unclear: Whether this needs a dedicated action or is part of an existing action.
   - Recommendation: Include occlusion culling as part of the scene profiler recommendations, and add `StaticEditorFlags.OccludeeStatic` / `OccluderStatic` tagging to the LOD setup script. No separate action needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | Tools/mcp-toolkit/pyproject.toml |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_gameplay_templates.py tests/test_performance_templates.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOB-01 | Mob controller C# has NavMeshAgent, enum states, configurable params | unit | `pytest tests/test_gameplay_templates.py::TestMobController -x` | Wave 0 |
| MOB-02 | Aggro system C# has OverlapSphere, threat decay, leash logic | unit | `pytest tests/test_gameplay_templates.py::TestAggroSystem -x` | Wave 0 |
| MOB-03 | Patrol route C# has Transform[] waypoints, dwell times, random offset | unit | `pytest tests/test_gameplay_templates.py::TestPatrolRoute -x` | Wave 0 |
| MOB-04 | Spawn system C# has wave config, max count, respawn timer, area bounds | unit | `pytest tests/test_gameplay_templates.py::TestSpawnSystem -x` | Wave 0 |
| MOB-05 | Behavior tree C# has ScriptableObject base, Sequence/Selector/Leaf | unit | `pytest tests/test_gameplay_templates.py::TestBehaviorTree -x` | Wave 0 |
| MOB-06 | Combat ability C# has animation trigger, VFX, hitbox, damage, sound | unit | `pytest tests/test_gameplay_templates.py::TestCombatAbility -x` | Wave 0 |
| MOB-07 | Projectile C# has trajectory enum, trail, impact, velocity config | unit | `pytest tests/test_gameplay_templates.py::TestProjectileSystem -x` | Wave 0 |
| PERF-01 | Profiler C# has UnityStats/ProfilerRecorder, frame time, JSON report | unit | `pytest tests/test_performance_templates.py::TestSceneProfiler -x` | Wave 0 |
| PERF-02 | LOD setup C# has LODGroup.SetLODs, screen percentages, MeshRenderer | unit | `pytest tests/test_performance_templates.py::TestLODSetup -x` | Wave 0 |
| PERF-03 | Lightmap C# has BakeAsync, isRunning, quality settings | unit | `pytest tests/test_performance_templates.py::TestLightmapBaker -x` | Wave 0 |
| PERF-04 | Asset audit C# has AssetDatabase scan, TextureImporter, AudioImporter | unit | `pytest tests/test_performance_templates.py::TestAssetAudit -x` | Wave 0 |
| PERF-05 | Build C# has BuildPipeline.BuildPlayer, BuildReport, size analysis | unit | `pytest tests/test_performance_templates.py::TestBuildAutomation -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_gameplay_templates.py tests/test_performance_templates.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_gameplay_templates.py` -- covers MOB-01 through MOB-07
- [ ] `tests/test_performance_templates.py` -- covers PERF-01 through PERF-05

## Tool Budget Analysis

### Current Unity Server Tool Count
| Tool | Actions | Requirements |
|------|---------|-------------|
| unity_editor | 6 | ARCH series |
| unity_vfx | 10 | VFX-01 through VFX-10 |
| unity_audio | 10 | AUD-01 through AUD-10 |
| unity_ui | 5 | UI-02, UI-03, UI-05, UI-06, UI-07 |
| unity_scene | 7 | SCENE-01 through SCENE-07 |
| **unity_gameplay** (new) | **7** | **MOB-01 through MOB-07** |
| **unity_performance** (new) | **5** | **PERF-01 through PERF-05** |

### Post-Phase 8 Totals
- Unity server: 7 compound tools (was 5)
- Blender server: 15 tools (unchanged)
- Total across all servers: 22 tools -- well within ARCH-01 max of 26

## Template File Structure

### gameplay_templates.py Functions
```python
# Pure-logic helpers (testable without Unity)
_validate_mob_params(detection_range, attack_range, leash_distance, ...) -> bool
_validate_spawn_params(max_count, respawn_timer, spawn_radius, ...) -> bool
_validate_ability_params(cooldown, damage, ...) -> bool
_validate_projectile_params(velocity, trajectory_type, ...) -> bool

# C# template generators
generate_mob_controller_script(name, detection_range, attack_range, ...) -> str     # MOB-01
generate_aggro_system_script(name, detection_range, decay_rate, ...) -> str          # MOB-02
generate_patrol_route_script(name, waypoint_count, dwell_time, ...) -> str           # MOB-03
generate_spawn_system_script(name, max_count, respawn_timer, ...) -> str             # MOB-04
generate_behavior_tree_script(name, node_types) -> str                               # MOB-05
generate_combat_ability_script(name, damage, cooldown, ...) -> str                   # MOB-06
generate_projectile_script(name, velocity, trajectory, ...) -> str                   # MOB-07
```

### performance_templates.py Functions
```python
# Pure-logic helpers (testable without Unity)
_analyze_profile_thresholds(data, budgets) -> list[dict]    # recommendation engine
_classify_asset_issues(assets) -> dict                      # categorize audit findings
_validate_lod_screen_percentages(percentages) -> bool       # ensure descending order

# C# template generators
generate_scene_profiler_script(budgets) -> str                                       # PERF-01
generate_lod_setup_script(lod_count, screen_percentages) -> str                      # PERF-02
generate_lightmap_bake_script(quality, bounces, ...) -> str                          # PERF-03
generate_asset_audit_script(max_texture_size, ...) -> str                            # PERF-04
generate_build_automation_script(target, scenes, ...) -> str                         # PERF-05
```

## Runtime vs Editor Script Routing

| Requirement | Script Type | Output Path | Reason |
|-------------|-------------|-------------|--------|
| MOB-01 | Runtime MonoBehaviour | Assets/Scripts/Runtime/AI/ | Runs during gameplay |
| MOB-02 | Runtime MonoBehaviour | Assets/Scripts/Runtime/AI/ | Runs during gameplay |
| MOB-03 | Runtime MonoBehaviour | Assets/Scripts/Runtime/AI/ | Runs during gameplay |
| MOB-04 | Runtime MonoBehaviour | Assets/Scripts/Runtime/Spawning/ | Runs during gameplay |
| MOB-05 | ScriptableObject + Runtime | Assets/Scripts/Runtime/BehaviorTree/ | Data + runtime execution |
| MOB-06 | ScriptableObject + Runtime | Assets/Scripts/Runtime/Combat/ | Data + runtime execution |
| MOB-07 | Runtime MonoBehaviour | Assets/Scripts/Runtime/Combat/ | Runs during gameplay |
| PERF-01 | Editor MenuItem | Assets/Editor/Generated/Performance/ | Editor-only profiling |
| PERF-02 | Editor MenuItem | Assets/Editor/Generated/Performance/ | Editor-only LOD setup |
| PERF-03 | Editor MenuItem | Assets/Editor/Generated/Performance/ | Editor-only baking |
| PERF-04 | Editor MenuItem | Assets/Editor/Generated/Performance/ | Editor-only audit |
| PERF-05 | Editor MenuItem | Assets/Editor/Generated/Performance/ | Editor-only build |

**Important:** Runtime scripts (MOB-*) do NOT get `[MenuItem]` attributes. They are written to Assets/Scripts/Runtime/ and are meant to be attached to GameObjects. The MCP tool response should include `next_steps` instructions for attaching the component.

## Sources

### Primary (HIGH confidence)
- Unity NavMeshAgent API: https://docs.unity3d.com/ScriptReference/AI.NavMeshAgent.html
- Unity LODGroup.SetLODs: https://docs.unity3d.com/ScriptReference/LODGroup.SetLODs.html
- Unity Lightmapping.BakeAsync: https://docs.unity3d.com/ScriptReference/Lightmapping.BakeAsync.html
- Unity BuildPipeline.BuildPlayer: https://docs.unity3d.com/ScriptReference/BuildPipeline.BuildPlayer.html
- Unity BuildReport: https://docs.unity3d.com/ScriptReference/Build.Reporting.BuildReport.html
- Unity ProfilerRecorder: https://docs.unity3d.com/ScriptReference/Unity.Profiling.ProfilerRecorder.html
- Unity FrameTimingManager: https://docs.unity3d.com/ScriptReference/FrameTimingManager.html
- Existing codebase: scene_templates.py, vfx_templates.py, audio_templates.py patterns

### Secondary (MEDIUM confidence)
- Unity AI FSM patterns: https://www.toptal.com/unity/unity-ai-development-finite-state-machine-tutorial
- Unity Build Report Inspector: https://github.com/Unity-Technologies/BuildReportInspector
- Unity AutoLOD: https://github.com/Unity-Technologies/AutoLOD

### Tertiary (LOW confidence)
- None -- all findings verified against official Unity documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Same architecture as Phases 1-7, no new dependencies
- Architecture: HIGH - Follows established compound tool + template generator pattern exactly
- Pitfalls: HIGH - Based on official Unity API documentation and known NavMesh/Physics/Lightmapping gotchas
- C# API coverage: MEDIUM - Template output patterns verified against Unity docs but not compiled against a live Unity project

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable -- Unity APIs and project patterns are well-established)
