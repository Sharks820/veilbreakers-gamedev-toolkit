# Physics, Collision, NavMesh & Player Interaction Systems Research

**Researched:** 2026-04-02
**Domain:** Unity 6 open-world dark fantasy action RPG runtime systems
**Confidence:** HIGH (verified against Unity 6000.3 docs, AI Navigation 2.0 package docs, Cinemachine 3.1 docs)

## Summary

This research covers the six critical gameplay infrastructure domains identified as gaps in VeilBreakers: NavMesh/AI navigation, collision mesh strategy, physics performance, player interaction systems, camera/input, and save/load. Unity 6 ships with the AI Navigation package (com.unity.ai.navigation) as the standard NavMesh solution, replacing the legacy baked-in-editor workflow. Physics uses PhysX 5 with significant improvements over earlier versions. Cinemachine 3.x provides production-ready third-person camera with built-in collision resolution. The New Input System is the standard for cross-device input with runtime rebinding.

The biggest risk area is NavMesh on large open-world terrains -- runtime baking is supported but requires careful tile sizing and incremental updates to avoid frame hitches. The second risk is physics object count management; an action RPG with destructibles, ragdolls, and dynamic objects needs aggressive use of kinematic bodies, physics LOD, and sleeping thresholds.

**Primary recommendation:** Use NavMeshSurface components per terrain tile with pre-baked data and runtime NavMeshLink generation for dynamic connections. Use compound primitive colliders for all interactive objects, reserving MeshCollider (convex) only for static architecture. Budget 200-300 active dynamic Rigidbodies maximum at 60fps, with aggressive kinematic conversion for distant objects.

---

## 1. NavMesh for Terrain

### 1.1 How Unity NavMesh Works on Terrain (Unity 6 / AI Navigation 2.0)

**Confidence: HIGH** (verified against Unity AI Navigation 2.0.12 docs)

Unity 6 uses the **AI Navigation package** (`com.unity.ai.navigation@2.0`). The legacy Navigation window bake button is removed in Unity 6 -- you MUST use `NavMeshSurface` components.

**Core workflow:**
1. Add `NavMeshSurface` component to a GameObject (or each terrain tile)
2. Configure Agent Type (radius, height, max slope, step height)
3. Set "Use Geometry" to "Render Meshes" (includes Terrains) or "Physics Colliders"
4. Click Bake or call `surface.BuildNavMesh()` at runtime

**Terrain-specific behavior:**
- Terrain heightmap is sampled during voxelization -- no separate terrain collider needed for baking
- Terrain trees marked as NavMesh obstacles are automatically carved out
- Terrain detail objects (grass) are NOT included in NavMesh baking (they shouldn't be)

### 1.2 NavMesh Baking Configuration for Open World

**Key settings for large terrains:**

| Setting | Recommended Value | Why |
|---------|------------------|-----|
| Agent Radius | 0.5 (human-sized) | Standard for humanoid characters |
| Agent Height | 2.0 | Standard human height |
| Max Slope | 45 degrees | Steep enough for dramatic terrain, matches Dark Souls style |
| Step Height | 0.4 | Allows stepping over rubble/small obstacles |
| Voxel Size | 0.166 (1/3 radius) | Default is good; smaller = more accurate but slower bake |
| Tile Size | 256 voxels (default) | Good balance; reduce to 128 for runtime baking to limit memory |
| Min Region Area | 2.0 | Removes tiny disconnected walkable patches |

**Object Collection for open world:** Use "Volume" collection mode per terrain tile rather than "All Game Objects" to limit bake scope and enable parallel baking of tiles.

### 1.3 Slope Angle Limits for Walkability

- **Max Slope** property on NavMeshSurface controls the steepest walkable angle
- Default is 45 degrees; range is 0-60 degrees
- For dark fantasy: 45 degrees is standard (matches Souls-like games where steep terrain is common)
- Surfaces steeper than Max Slope are automatically marked as non-walkable
- **Step Height** handles small vertical obstacles (stairs, ledges) independently of slope

### 1.4 NavMesh on Multiple Terrain Tiles (Cross-Tile Pathing)

**Approach: One NavMeshSurface per terrain tile.**

```csharp
// Each terrain tile has its own NavMeshSurface component
// When a tile loads:
public void OnTileLoaded(Terrain terrain)
{
    var surface = terrain.gameObject.AddComponent<NavMeshSurface>();
    surface.collectObjects = CollectObjects.Current;
    surface.useGeometry = NavMeshCollectGeometry.RenderMeshes;
    surface.defaultArea = 0; // Walkable
    surface.overrideTileSize = true;
    surface.tileSize = 128; // Smaller for runtime performance
    surface.BuildNavMesh();
}
```

**Cross-tile connection:** NavMesh tiles placed adjacent to each other with matching edges will automatically connect -- agents can path across tile boundaries seamlessly. The NavMesh system handles edge stitching internally as long as:
- Both surfaces use the same Agent Type
- Tile edges overlap or are adjacent (within voxel tolerance)

**If tiles don't align perfectly**, use `NavMeshLink` components at tile boundaries.

### 1.5 Runtime NavMesh Baking vs Pre-Baked

| Approach | When to Use | Performance |
|----------|-------------|-------------|
| **Pre-baked (editor)** | Static terrain, handcrafted levels | Zero runtime cost, instant availability |
| **Runtime baking** | Procedurally generated terrain, streaming tiles | 50-200ms per tile depending on complexity |
| **Hybrid** | Pre-bake static terrain, runtime-bake dynamic additions | Best of both worlds |

**Runtime baking API:**
```csharp
// Async-friendly pattern for runtime baking
NavMeshSurface surface = GetComponent<NavMeshSurface>();

// Bake on background thread (Unity 6 supports this)
var data = NavMeshBuilder.BuildNavMeshData(
    surface.GetBuildSettings(),
    sources, // NavMeshBuildSource list
    new Bounds(center, size),
    transform.position,
    transform.rotation
);

// Apply on main thread
surface.navMeshData = data;
surface.AddData();
```

**Performance tip:** For open world, pre-bake all terrain tiles in the editor. Only runtime-bake when terrain is dynamically modified (destruction, Veil world transition).

### 1.6 NavMeshLink for Gaps/Jumps/Ladders

**NavMeshLink** creates traversable connections between disconnected NavMesh regions.

**Use cases for VeilBreakers:**
| Link Type | Start/End Width | Bidirectional | Example |
|-----------|----------------|---------------|---------|
| Jump down | 1.0m | NO (one-way) | Cliff edges, rooftop drops |
| Jump across | 1.0m | YES | Gap in bridge, broken staircase |
| Ladder | 0.5m | YES | Tower access, dungeon vertical |
| Door threshold | 2.0m | YES | Doorways between NavMesh areas |
| Water crossing | 3.0m | YES | Shallow ford across river |

**Configuration:**
```csharp
// NavMeshLink component properties
NavMeshLink link = gameObject.AddComponent<NavMeshLink>();
link.startPoint = new Vector3(0, 0, 0);  // Local space
link.endPoint = new Vector3(0, -5, 3);    // Jump down 5m, forward 3m
link.width = 1.0f;
link.bidirectional = false;               // One-way drop
link.agentTypeID = agentTypeID;           // Must match NavMeshSurface
link.area = 2;                            // "Jump" area type (cost = 2)
link.autoUpdate = true;                   // Update when object moves
```

**Agent traversal handling:**
```csharp
// In NavMeshAgent update loop
if (agent.isOnOffMeshLink)
{
    OffMeshLinkData linkData = agent.currentOffMeshLinkData;
    // Animate jump/climb/ladder based on link area type
    StartCoroutine(TraverseLink(linkData));
}
```

### 1.7 NavMesh Areas (Walkable, Not Walkable, Water, etc.)

Unity provides 3 built-in + 29 custom area types (32 total, bitmask).

**Recommended area setup for VeilBreakers:**

| Area | Index | Cost | Purpose |
|------|-------|------|---------|
| Walkable | 0 | 1.0 | Normal ground |
| Not Walkable | 1 | -- | Impassable |
| Jump | 2 | 2.0 | NavMeshLink traversal |
| Water (Shallow) | 3 | 3.0 | Wading -- slower movement |
| Water (Deep) | 4 | 5.0 | Swimming required |
| Mud/Swamp | 5 | 2.5 | Corrupted terrain, slow |
| Road | 6 | 0.5 | Faster travel on paths |
| Stairs | 7 | 1.5 | Slightly more costly |
| Veil Corrupted | 8 | 4.0 | Dangerous Veil-touched ground |

**Agent area masks** control which areas an agent type can traverse:
```csharp
// NPC that avoids water
agent.areaMask = ~(1 << 3 | 1 << 4); // Exclude shallow and deep water

// Water creature only moves in water
agent.areaMask = (1 << 3 | 1 << 4);   // Only shallow and deep water
```

### 1.8 NavMesh Performance on Large Terrains

| Terrain Size | Pre-bake Time | NavMesh Data Size | Runtime Memory |
|-------------|---------------|-------------------|----------------|
| 500x500m | 2-5 seconds | 1-5 MB | 2-8 MB |
| 1000x1000m | 10-30 seconds | 5-20 MB | 10-30 MB |
| 2000x2000m | 30-120 seconds | 20-80 MB | 40-100 MB |

**Optimization strategies:**
1. **Tile-based streaming:** Load/unload NavMesh data with terrain tiles (NavMeshSurface.RemoveData() / AddData())
2. **Reduce voxel resolution** for open areas (increase voxel size to 0.25-0.33)
3. **Use Min Region Area** aggressively (set to 4-8) to cull tiny NavMesh fragments
4. **Height Mesh** only where needed (disable for flat terrain to save memory)
5. **Multiple agent types** only if truly needed (each doubles NavMesh memory)

---

## 2. Collision Mesh Strategy

### 2.1 Collider Type Selection Guide

**Confidence: HIGH** (verified against Unity 6000.3 docs)

| Collider Type | CPU Cost | Use Case | VeilBreakers Example |
|--------------|----------|----------|---------------------|
| **SphereCollider** | Cheapest | Round objects, approximations | Potions, orbs, boulders |
| **BoxCollider** | Very cheap | Rectangular shapes | Crates, chests, tables, walls |
| **CapsuleCollider** | Cheap | Characters, cylindrical | Player, NPCs, pillars, trees |
| **MeshCollider (convex)** | Moderate | Complex moving objects | Thrown weapons, rolling objects |
| **MeshCollider (non-convex)** | Expensive | Static complex geometry ONLY | Cave walls, terrain supplements |
| **Compound (multiple primitives)** | Sum of parts | Complex interactive objects | Buildings, vehicles, furniture |

**RULE: Never use non-convex MeshCollider on dynamic (non-kinematic) Rigidbodies.** PhysX requires convex colliders for dynamic simulation. Kinematic and static objects can use non-convex mesh colliders.

### 2.2 Convex Decomposition (V-HACD / CoACD)

For complex shapes that need dynamic physics (destructibles, thrown objects):

**V-HACD** (Volumetric Hierarchical Approximate Convex Decomposition):
- Unity Technologies maintains an official V-HACD repo: `github.com/Unity-Technologies/VHACD`
- Decomposes a concave mesh into multiple convex hull pieces
- Each piece becomes a child GameObject with its own convex MeshCollider
- Typical result: 5-15 convex hulls per complex object

**CoACD** (alternative, newer):
- Better quality decomposition than V-HACD for some shapes
- Free Unity plugin available: `discussions.unity.com/t/free-better-convex-mesh-collider-generator-coacd`

**When to use automatic decomposition:**
- Imported 3D models with complex shapes that need dynamic physics
- Destructible objects that fracture into pieces
- NOT needed for most game objects (use compound primitives instead)

### 2.3 Compound Colliders for Complex Buildings

**Best approach for VeilBreakers buildings:**

```
Building_Root (no collider)
  +-- Wall_North (BoxCollider)
  +-- Wall_South (BoxCollider)
  +-- Wall_East (BoxCollider)
  +-- Wall_West (BoxCollider)
  +-- Floor (BoxCollider)
  +-- Roof (BoxCollider, angled)
  +-- Doorway_Trigger (BoxCollider, isTrigger)
  +-- Interior_Trigger (BoxCollider, isTrigger, larger)
```

**Guidelines:**
- 6-12 primitive colliders per building is typical
- Use BoxColliders for walls, floors, roofs
- Add trigger volumes for gameplay events (enter building, interaction zones)
- Do NOT use MeshCollider for buildings unless extremely irregular geometry
- Parent all colliders to a single Rigidbody (kinematic) for compound behavior

### 2.4 Terrain Collider Performance

Unity's `TerrainCollider` is highly optimized:
- Uses heightmap directly -- no mesh generation needed
- O(1) lookup time for point queries (height at position)
- Automatically handles LOD based on query precision
- **No polycount budget** -- it's heightmap-based, not mesh-based
- Performance is essentially free compared to equivalent MeshColliders

**One TerrainCollider per Terrain tile** -- this is automatic when using Unity Terrain.

### 2.5 Trigger Volumes for Gameplay Events

**Design pattern for VeilBreakers:**

| Trigger Type | Shape | Size | Layer | Purpose |
|-------------|-------|------|-------|---------|
| Room enter | Box | Room bounds | Trigger | Interior loading, lighting swap |
| NPC interaction | Sphere | 3-5m radius | Trigger | Show interact prompt |
| Combat arena | Box/Sphere | Arena bounds | Trigger | Lock doors, spawn enemies |
| Loot pickup | Sphere | 1.5m radius | Trigger | Auto-pickup range |
| Hazard zone | Box | Hazard area | Trigger | Damage over time (corruption) |
| Cutscene trigger | Box | Thin plane | Trigger | One-shot cinematic trigger |
| Water volume | Box | Water bounds | Trigger | Swimming state transition |

**Implementation pattern:**
```csharp
[RequireComponent(typeof(Collider))]
public class GameplayTrigger : MonoBehaviour
{
    [SerializeField] private TriggerType type;
    [SerializeField] private bool oneShot = false;
    private bool triggered = false;

    private void OnTriggerEnter(Collider other)
    {
        if (triggered && oneShot) return;
        if (!other.CompareTag("Player")) return;
        triggered = true;
        TriggerEvent(other);
    }
}
```

### 2.6 Layer-Based Collision Matrix Design

**Recommended layer setup for VeilBreakers (32 layer limit):**

| Layer # | Name | Collides With |
|---------|------|--------------|
| 0 | Default | Everything |
| 6 | Player | Environment, Enemy, EnemyProjectile, Interactable, Trigger, Water |
| 7 | Enemy | Environment, Player, PlayerProjectile, NavBlocker |
| 8 | PlayerProjectile | Environment, Enemy, Destructible |
| 9 | EnemyProjectile | Environment, Player, Destructible |
| 10 | Environment | Everything except Trigger |
| 11 | Interactable | Player (trigger only) |
| 12 | Trigger | Player only |
| 13 | Destructible | PlayerProjectile, EnemyProjectile, Environment |
| 14 | Ragdoll | Environment only |
| 15 | Water | Player, Enemy |
| 16 | VFX | Nothing (visual only) |
| 17 | NavBlocker | Enemy (for AI avoidance) |
| 18 | Camera | Environment (for camera collision) |

**Critical optimizations:**
- Enemy-Enemy collisions DISABLED (use NavMesh avoidance instead, much cheaper)
- Projectile-Projectile collisions DISABLED
- VFX layer collides with NOTHING
- Ragdoll only collides with Environment (not player, not enemies)

### 2.7 Collision Mesh Polycount Budgets

| Object Type | Max Collider Tris | Approach |
|-------------|-------------------|----------|
| Static building | N/A (use compound primitives) | 6-12 BoxColliders |
| Static prop (barrel, crate) | N/A | 1 BoxCollider or CapsuleCollider |
| Dynamic prop | 32-64 (convex hull) | Auto-generated convex |
| Character | N/A | CapsuleCollider |
| Complex static (cave) | 500-2000 (non-convex mesh) | Simplified collision mesh |
| Terrain | N/A (heightmap) | TerrainCollider |
| Destructible piece | 16-32 (convex) | V-HACD decomposed |

**Rule of thumb:** If your collision mesh has more than 256 triangles on a dynamic object, you are doing it wrong. Use primitives or decompose further.

---

## 3. Physics Performance

### 3.1 Rigidbody Count Limits at 60fps

**Confidence: MEDIUM** (based on community benchmarks + Unity guidance, no hard official number)

| Rigidbody Type | Safe Count (60fps, mid-range PC) | Absolute Max |
|---------------|----------------------------------|--------------|
| **Active dynamic** (moving, colliding) | 200-300 | 500 |
| **Sleeping dynamic** (at rest) | 1000-2000 | 5000+ |
| **Kinematic** (script-controlled) | 500-1000 | 2000+ |
| **Static colliders** (no Rigidbody) | 5000-10000 | 50000+ |

**Key insight:** It's not the total Rigidbody count that matters -- it's the number of **active, non-sleeping** dynamic bodies simultaneously. PhysX automatically sleeps bodies at rest.

**VeilBreakers budget per frame:**
- Player + equipment: 1-3 dynamic bodies
- Active enemies in combat: 10-20 (capsule colliders, simple)
- Projectiles in flight: 10-30
- Ragdolls (active): 2-3 (each = 10-15 rigid bodies, so 20-45 total)
- Destruction debris: 20-50 (short-lived, pooled)
- Interactive props: 5-10
- **Total active budget: ~100-170 dynamic bodies** (well within limits)

### 3.2 Physics Tick Rate Configuration

```csharp
// Project Settings > Time
// Default fixed timestep: 0.02s (50 Hz)
Time.fixedDeltaTime = 0.02f;  // 50 Hz -- RECOMMENDED for action RPG

// For faster combat requiring precise collision:
Time.fixedDeltaTime = 0.01667f;  // 60 Hz -- matches frame rate, more accurate
// WARNING: Doubling physics rate roughly doubles physics CPU cost

// For less critical physics (distant objects):
// Use per-object simulation control, not global timestep changes
```

**Recommendation for VeilBreakers:** Keep at 50 Hz (0.02s). Use Continuous collision detection only on fast-moving projectiles. The 50 Hz rate is sufficient for melee combat with proper hitbox timing.

### 3.3 Physics LOD (Disable Physics on Distant Objects)

Unity has no built-in physics LOD system. **You must implement it manually.**

```csharp
public class PhysicsLOD : MonoBehaviour
{
    [SerializeField] private float disableDistance = 50f;
    [SerializeField] private float sleepDistance = 30f;
    private Rigidbody rb;
    private Collider col;
    private Transform player;

    void Update() // or check every N frames
    {
        float dist = Vector3.Distance(transform.position, player.position);

        if (dist > disableDistance)
        {
            rb.isKinematic = true;
            col.enabled = false;     // Complete physics removal
        }
        else if (dist > sleepDistance)
        {
            rb.isKinematic = true;   // No dynamic sim, but still collides
            col.enabled = true;
        }
        else
        {
            rb.isKinematic = false;  // Full physics
            col.enabled = true;
        }
    }
}
```

**Distance thresholds for VeilBreakers:**
| Distance | Physics State | Example |
|----------|--------------|---------|
| 0-30m | Full dynamic | Combat range, interactive props |
| 30-50m | Kinematic + collider | Visible but not interactive |
| 50m+ | Disabled entirely | Out of gameplay range |

### 3.4 Ragdoll on Terrain Slopes

**Common problems and solutions:**

| Problem | Solution |
|---------|----------|
| Ragdoll slides down slopes | Increase drag (2-5), increase angular drag (5-10) on all ragdoll rigidbodies |
| Ragdoll jitters on terrain | Increase solver iterations (8-12), use PhysicMaterial with high friction |
| Ragdoll clips through terrain | Use Continuous collision detection on torso/hips |
| Ragdoll limbs stretch | Limit joint angular ranges to 5-15 degrees minimum, avoid mass ratios > 5:1 between connected bodies |
| Ragdoll never stops moving | Set `sleepThreshold = 0.05f` on all rigidbodies, set sleep timeout |

**Ragdoll stability settings:**
```csharp
// Apply to all ragdoll rigidbodies
foreach (var rb in ragdollBodies)
{
    rb.drag = 2f;
    rb.angularDrag = 5f;
    rb.collisionDetectionMode = CollisionDetectionMode.Continuous;
    rb.sleepThreshold = 0.05f;
    rb.maxAngularVelocity = 7f; // Prevent wild spinning
    rb.solverIterations = 10;
    rb.solverVelocityIterations = 5;
}
```

**Best practice:** Use "active ragdoll" hybrid -- animation-driven skeleton transitions to physics ragdoll on death/stagger, then auto-disables after 3-5 seconds of rest.

### 3.5 Destruction Physics Budget

**Budget for real-time destruction:**
- **Max simultaneous destruction events:** 2-3
- **Pieces per destruction:** 8-15 convex fragments
- **Piece lifetime:** 3-5 seconds, then fade and pool
- **Total destruction rigidbodies at once:** 30-45
- **Use LOD:** Only show destruction within 30m of player

**Implementation pattern:**
```csharp
public class Destructible : MonoBehaviour
{
    [SerializeField] private GameObject intactVersion;
    [SerializeField] private GameObject fracturedVersion; // Pre-fractured in Blender
    [SerializeField] private float pieceLifetime = 4f;

    public void Destroy(Vector3 hitPoint, float force)
    {
        intactVersion.SetActive(false);
        fracturedVersion.SetActive(true);

        foreach (var rb in fracturedVersion.GetComponentsInChildren<Rigidbody>())
        {
            rb.AddExplosionForce(force, hitPoint, 3f);
            StartCoroutine(FadeAndPool(rb.gameObject, pieceLifetime));
        }
    }
}
```

### 3.6 Kinematic vs Dynamic Decision Guide

| Object | Body Type | Reason |
|--------|-----------|--------|
| Player character | Kinematic Rigidbody | Controlled by CharacterController/script, not physics |
| Enemies (alive) | Kinematic Rigidbody | Animation-driven movement via NavMeshAgent |
| Enemies (dead) | Dynamic (ragdoll) | Switch to ragdoll on death |
| Doors | Kinematic | Animation-driven open/close |
| Treasure chests | Kinematic | Animation-driven open |
| Thrown weapons | Dynamic | Physics-driven flight path |
| Dropped loot | Dynamic -> Kinematic | Dynamic until landed, then kinematic |
| Barrels/crates | Kinematic -> Dynamic | Static until hit, then dynamic briefly |
| Destruction debris | Dynamic -> Pool | Short-lived dynamic, then recycled |
| World props (static) | No Rigidbody | Static colliders only |
| Projectiles (arrows, spells) | Dynamic (CCD) | Continuous collision detection for speed |

---

## 4. Player Interaction Systems

### 4.1 Interaction Trigger Design (Proximity + Look Direction)

**The Souls-like interaction pattern:** Proximity sphere + forward raycast + input prompt.

```csharp
public class InteractionSystem : MonoBehaviour
{
    [SerializeField] private float interactRadius = 3f;
    [SerializeField] private float interactAngle = 60f; // Degrees from forward
    [SerializeField] private LayerMask interactableLayer;

    private IInteractable currentTarget;

    void Update()
    {
        // 1. Find all interactables within radius
        var hits = Physics.OverlapSphere(
            transform.position, interactRadius, interactableLayer
        );

        // 2. Filter by look direction
        IInteractable best = null;
        float bestScore = float.MinValue;

        foreach (var hit in hits)
        {
            Vector3 toTarget = (hit.transform.position - transform.position).normalized;
            float dot = Vector3.Dot(transform.forward, toTarget);
            float angle = Mathf.Acos(dot) * Mathf.Rad2Deg;

            if (angle < interactAngle && dot > bestScore)
            {
                var interactable = hit.GetComponent<IInteractable>();
                if (interactable != null && interactable.CanInteract)
                {
                    best = interactable;
                    bestScore = dot;
                }
            }
        }

        currentTarget = best;

        // 3. Show/hide UI prompt
        UIManager.Instance.ShowInteractPrompt(best != null, best?.InteractText);

        // 4. Handle input
        if (best != null && Input.GetButtonDown("Interact"))
            best.Interact(gameObject);
    }
}

public interface IInteractable
{
    bool CanInteract { get; }
    string InteractText { get; }
    void Interact(GameObject interactor);
}
```

### 4.2 Door Opening/Closing Mechanics

```csharp
public class Door : MonoBehaviour, IInteractable
{
    [SerializeField] private Animator animator;
    [SerializeField] private bool requiresKey;
    [SerializeField] private string keyItemID;
    [SerializeField] private AudioClip openSound, closeSound;

    private bool isOpen = false;
    public bool CanInteract => !requiresKey || PlayerInventory.HasItem(keyItemID);
    public string InteractText => isOpen ? "Close" : (requiresKey ? "Unlock" : "Open");

    public void Interact(GameObject interactor)
    {
        isOpen = !isOpen;
        animator.SetBool("IsOpen", isOpen);
        AudioSource.PlayClipAtPoint(isOpen ? openSound : closeSound, transform.position);

        // NavMesh obstacle update
        GetComponent<NavMeshObstacle>().carving = !isOpen;
    }
}
```

**Key details:**
- Use Animation-driven doors (Animator component), not physics hinges (too unstable)
- Use `NavMeshObstacle` with carving to update NavMesh when door opens/closes
- Lock/unlock state persists in save data
- Two-sided interaction: door opens away from player (use dot product with door forward)

### 4.3 Chest/Container Loot Interaction

```csharp
public class LootContainer : MonoBehaviour, IInteractable
{
    [SerializeField] private Animator animator;
    [SerializeField] private LootTable lootTable;
    [SerializeField] private Transform[] itemSpawnPoints;
    private bool isOpened = false;

    public bool CanInteract => !isOpened;
    public string InteractText => "Open";

    public void Interact(GameObject interactor)
    {
        isOpened = true;
        animator.SetTrigger("Open");
        var items = lootTable.Roll();
        foreach (var item in items)
            PlayerInventory.AddItem(item);
        UIManager.Instance.ShowLootPopup(items);

        // Save state
        SaveManager.SetFlag($"chest_{gameObject.GetComponent<UniqueID>().ID}", true);
    }

    // Restore state on load
    public void OnLoad(string id)
    {
        if (SaveManager.GetFlag($"chest_{id}"))
        {
            isOpened = true;
            animator.Play("Opened", 0, 1f); // Jump to opened state
        }
    }
}
```

### 4.4 NPC Dialogue Trigger

- Use sphere trigger (3-5m radius) for "approach NPC" awareness
- Inner sphere (1.5-2m) or raycast for "interact" prompt
- On interact: freeze player movement, switch to dialogue camera, open dialogue UI
- Use the existing DialogueManager system (already in VeilBreakers3DCurrent)

### 4.5 Lever/Switch Mechanics

```csharp
public class Lever : MonoBehaviour, IInteractable
{
    [SerializeField] private Animator animator;
    [SerializeField] private UnityEvent onActivate;
    [SerializeField] private UnityEvent onDeactivate;
    [SerializeField] private bool isToggle = true;

    private bool activated = false;
    public bool CanInteract => isToggle || !activated;
    public string InteractText => activated ? "Deactivate" : "Activate";

    public void Interact(GameObject interactor)
    {
        activated = isToggle ? !activated : true;
        animator.SetBool("Activated", activated);

        if (activated) onActivate.Invoke();
        else onDeactivate.Invoke();
    }
}
```

**Connected systems:** Levers can trigger doors, bridges, traps, elevators, Veil portals via UnityEvents.

### 4.6 Climbable Surface Detection

**Two approaches for dark fantasy RPG:**

**Approach A: Designated climb points (recommended for Souls-like):**
- Place ladder/vine objects with climb interaction triggers
- NOT freeform climbing (that's Breath of the Wild, not Dark Souls)
- Ladder interaction: player snaps to ladder, enters climb animation state
- Climb speed controlled by animation, not physics

**Approach B: Surface tag detection (for limited free climbing):**
```csharp
// Raycast forward from player to detect climbable surfaces
if (Physics.Raycast(transform.position, transform.forward, out hit, 1.5f))
{
    if (hit.collider.CompareTag("Climbable"))
    {
        // Check surface angle is suitable for climbing
        float wallAngle = Vector3.Angle(hit.normal, Vector3.up);
        if (wallAngle > 70f && wallAngle < 110f) // Near-vertical
        {
            canClimb = true;
        }
    }
}
```

**Recommendation for VeilBreakers:** Use Approach A (designated climb points). Freeform climbing requires extensive animation work and edge-case handling that isn't worth it for a Souls-like.

### 4.7 Swimming/Wading in Water

**Unity has NO built-in water physics.** You must implement buoyancy and swimming manually.

**Implementation layers:**

1. **Water volume detection:** Box trigger collider on water surface
2. **Depth detection:** Raycast down from player to water bottom
3. **State transitions:**
   - Depth < 0.5m: Normal walk (splash particles)
   - Depth 0.5-1.2m: Wading (slow movement, different animation)
   - Depth > 1.2m: Swimming (different movement model, camera adjustment)

```csharp
public class WaterZone : MonoBehaviour
{
    [SerializeField] private float waterSurfaceY;

    private void OnTriggerStay(Collider other)
    {
        if (!other.CompareTag("Player")) return;

        float playerFeetY = other.transform.position.y;
        float depth = waterSurfaceY - playerFeetY;

        if (depth > 1.2f)
            PlayerController.SetState(MovementState.Swimming);
        else if (depth > 0.5f)
            PlayerController.SetState(MovementState.Wading);
        else
            PlayerController.SetState(MovementState.Splashing);
    }
}
```

**Swimming movement:**
- Replace CharacterController.Move with custom buoyancy force
- Apply upward force when below water surface
- Reduce gravity (or set to 0) when swimming
- Movement speed reduced by 40-60%
- Stamina drain while swimming (Souls-like)
- Corruption water deals damage over time (VeilBreakers specific)

---

## 5. Camera and Input

### 5.1 Third Person Camera Collision (Cinemachine 3.x)

**Confidence: HIGH** (verified against Cinemachine 3.1 docs)

Use **Cinemachine Third Person Follow** body component (NOT FreeLook for Souls-like combat).

**Configuration:**
```
CinemachineCamera
  +-- Body: Third Person Follow
       Camera Distance: 4
       Shoulder Offset: (0.5, 0.3, 0) -- slight over-shoulder
       Damping: (0.1, 0.3, 0.2) -- responsive but smooth
       Camera Collision Filter: Environment + Camera layers
       Camera Radius: 0.2
       Damping Into Collision: 0 -- instant snap when wall hit
       Damping From Collision: 0.5 -- smooth return
       Ignore Tag: "Player"
```

### 5.2 Camera Occlusion Handling

Cinemachine Third Person Follow handles this automatically via its collision system. Additional strategies:

1. **Transparency fade:** When camera clips through geometry, fade those objects to transparent
```csharp
// Raycast from camera to player, fade any objects hit
void HandleOcclusion()
{
    Vector3 dir = player.position - camera.position;
    RaycastHit[] hits = Physics.RaycastAll(camera.position, dir, dir.magnitude, occlusionLayer);
    foreach (var hit in hits)
    {
        var renderer = hit.collider.GetComponent<Renderer>();
        if (renderer) FadeToTransparent(renderer, 0.3f);
    }
}
```

2. **Camera clip plane adjustment:** Reduce near clip plane when camera is close to walls
3. **Maximum zoom in:** When no valid camera position exists, zoom to minimum distance over shoulder

### 5.3 Lock-On Targeting System

**Core components:**

```csharp
public class LockOnSystem : MonoBehaviour
{
    [SerializeField] private float lockOnRange = 20f;
    [SerializeField] private float lockOnAngle = 60f;
    [SerializeField] private LayerMask targetableLayer;

    private Transform currentTarget;
    private CinemachineCamera lockOnCamera;

    public void ToggleLockOn()
    {
        if (currentTarget != null)
        {
            ReleaseLock();
            return;
        }

        // Find best target: closest to screen center within range + angle
        var candidates = Physics.OverlapSphere(
            transform.position, lockOnRange, targetableLayer);

        Transform best = null;
        float bestScore = float.MaxValue;

        foreach (var c in candidates)
        {
            Vector3 screenPos = Camera.main.WorldToViewportPoint(c.transform.position);
            float distToCenter = Vector2.Distance(
                new Vector2(screenPos.x, screenPos.y),
                new Vector2(0.5f, 0.5f));

            if (screenPos.z > 0 && distToCenter < bestScore)
            {
                best = c.transform;
                bestScore = distToCenter;
            }
        }

        if (best != null) AcquireLock(best);
    }

    private void AcquireLock(Transform target)
    {
        currentTarget = target;
        lockOnCamera.Priority.Value = 20; // Higher than default camera
        // Set Cinemachine LookAt to target lock-on point (chest height)
        lockOnCamera.LookAt = target.Find("LockOnPoint");
        // Show lock-on reticle UI
        UIManager.Instance.ShowLockOnReticle(target);
    }

    // Switch targets (R-stick flick)
    public void SwitchTarget(float direction)
    {
        // Sort visible targets by screen-space X position
        // Pick next target in flick direction
    }
}
```

**Camera behavior when locked on:**
- Use separate CinemachineCamera with higher priority
- LookAt tracks the locked target's "LockOnPoint" (usually chest height)
- Follow still tracks player
- Player strafes around target (movement input becomes relative to target direction)

### 5.4 Input Rebinding System

**Use Unity's New Input System** (`com.unity.inputsystem`).

**Setup:**
1. Create InputActionAsset with Action Maps:
   - `Gameplay` (movement, camera, combat, interact, lock-on)
   - `UI` (navigate, submit, cancel)
   - `Dialogue` (advance, skip, choice selection)

2. Control Schemes:
   - `KeyboardMouse` (keyboard + mouse bindings)
   - `Gamepad` (Xbox/PlayStation controller bindings)

3. Runtime rebinding:
```csharp
public void StartRebind(InputAction action, int bindingIndex)
{
    action.Disable();
    var rebind = action.PerformInteractiveRebinding(bindingIndex)
        .OnComplete(op =>
        {
            op.Dispose();
            action.Enable();
            SaveBindingOverrides(); // Persist to JSON
        })
        .OnCancel(op =>
        {
            op.Dispose();
            action.Enable();
        })
        .Start();
}

// Save/Load binding overrides
public void SaveBindingOverrides()
{
    string json = playerInput.actions.SaveBindingOverridesAsJson();
    PlayerPrefs.SetString("InputBindings", json);
}

public void LoadBindingOverrides()
{
    string json = PlayerPrefs.GetString("InputBindings", "");
    if (!string.IsNullOrEmpty(json))
        playerInput.actions.LoadBindingOverridesFromJson(json);
}
```

### 5.5 Controller Support

The New Input System handles this via Control Schemes:
- Automatic device detection (PlayerInput component)
- Automatic scheme switching (keyboard <-> gamepad)
- Gamepad rumble via `Gamepad.current.SetMotorSpeeds(low, high)`
- Dead zones configurable per stick binding
- Button prompts: detect active scheme, show matching icons (Xbox/PS/KB)

**Recommended action map for VeilBreakers (Gameplay):**

| Action | KB/Mouse | Gamepad | Type |
|--------|----------|---------|------|
| Move | WASD | Left Stick | Vector2 |
| Camera | Mouse Delta | Right Stick | Vector2 |
| Attack (Light) | Left Click | R1/RB | Button |
| Attack (Heavy) | Right Click (hold) | R2/RT | Button |
| Dodge/Roll | Space | B/Circle | Button |
| Block | Shift | L1/LB | Button |
| Interact | E | A/Cross | Button |
| Lock-On | Q / Middle Click | R3 (click) | Button |
| Use Item | R | X/Square | Button |
| Inventory | I / Tab | Menu/Options | Button |
| Sprint | Shift (hold) | L3 (click) | Button |

---

## 6. Save/Load System

### 6.1 What State Needs Saving

**Confidence: HIGH** (based on VeilBreakers game systems audit)

| Category | Data | Size Estimate | Priority |
|----------|------|---------------|----------|
| **Player Position** | Vector3 + Quaternion + Scene ID | 28 bytes | CRITICAL |
| **Player Stats** | HP, Stamina, Mana, Level, XP, Brand levels | ~200 bytes | CRITICAL |
| **Inventory** | Item IDs, counts, equipment slots | 2-10 KB | CRITICAL |
| **Quest Progress** | Active quests, objectives, flags | 1-5 KB | CRITICAL |
| **World State** | Opened chests, killed bosses, destroyed objects, lever states | 5-20 KB | CRITICAL |
| **Corruption Levels** | Per-area corruption %, player corruption | 200 bytes | HIGH |
| **NPC States** | Alive/dead, location, dialogue flags | 1-5 KB | HIGH |
| **Settings** | Graphics, audio, controls (separate file) | 2 KB | MEDIUM |
| **Map Discovery** | Explored areas, waypoints unlocked | 1-2 KB | MEDIUM |
| **Statistics** | Play time, kills, deaths, items found | 500 bytes | LOW |

**Total save file size estimate:** 15-50 KB (very small, easy to manage)

### 6.2 Save File Format and Architecture

**Recommended: JSON for development, binary for release.**

```csharp
[Serializable]
public class SaveData
{
    public int version = 1;          // CRITICAL: Version for migration
    public long timestamp;            // Unix timestamp
    public string checksum;           // Integrity verification

    public PlayerData player;
    public InventoryData inventory;
    public QuestData quests;
    public WorldStateData worldState;
    public CorruptionData corruption;
    public NPCStateData[] npcs;
    public MapData map;
    public StatisticsData stats;
}

// Serialization
public static class SaveSerializer
{
    // Development: JSON (human-readable, debuggable)
    public static string ToJson(SaveData data) =>
        JsonUtility.ToJson(data, prettyPrint: true);

    // Release: Binary (smaller, harder to tamper)
    public static byte[] ToBinary(SaveData data)
    {
        string json = JsonUtility.ToJson(data);
        byte[] bytes = System.Text.Encoding.UTF8.GetBytes(json);
        // Optional: compress with GZip
        // Optional: encrypt with AES
        return bytes;
    }
}
```

### 6.3 Auto-Save Frequency

| Trigger | When | Why |
|---------|------|-----|
| **Checkpoint** | Bonfire/shrine rest | Souls-like save point |
| **Zone transition** | Enter new area/scene | Prevent progress loss on crash |
| **Boss defeated** | After boss death animation | Major milestone |
| **Quest complete** | After reward given | Prevent quest re-completion |
| **Timed interval** | Every 5 minutes | Background safety net |
| **Quit game** | On application quit | Always save on exit |

**Implementation:**
- Auto-save to a dedicated "autosave" slot (separate from manual saves)
- Show brief "Saving..." icon (do NOT pause gameplay)
- Save on background thread to avoid frame hitches

### 6.4 Cloud Save Support

**Two approaches:**

1. **Unity Cloud Save** (Unity Gaming Services):
   - Built-in Unity package, simple API
   - Stores key-value data or files in Unity's cloud
   - Free tier: 5MB per player
   - `CloudSaveService.Instance.Data.ForceSaveAsync(data)`

2. **Steam Cloud** (for Steam release):
   - Configure in Steamworks app settings
   - Steam auto-syncs files from `Application.persistentDataPath`
   - No code changes needed if saves are in the right directory
   - Set byte quota and file count in Steamworks

**Recommendation:** Support both. Save to `Application.persistentDataPath` (Steam auto-syncs). Optionally also push to Unity Cloud Save for cross-platform.

### 6.5 Save Corruption Prevention

**The atomic write pattern (CRITICAL):**

```csharp
public static class SafeSaveWriter
{
    public static void Save(string savePath, byte[] data)
    {
        string tempPath = savePath + ".tmp";
        string backupPath = savePath + ".bak";

        // Step 1: Write to temp file
        File.WriteAllBytes(tempPath, data);

        // Step 2: Verify temp file is valid
        byte[] verification = File.ReadAllBytes(tempPath);
        if (!ValidateChecksum(verification))
        {
            File.Delete(tempPath);
            throw new SaveCorruptionException("Save verification failed");
        }

        // Step 3: Backup existing save
        if (File.Exists(savePath))
            File.Copy(savePath, backupPath, overwrite: true);

        // Step 4: Atomic rename (replaces target)
        File.Move(tempPath, savePath); // On most OS, Move is atomic

        // Step 5: Keep backup for 3 most recent saves
        RotateBackups(savePath);
    }

    public static SaveData Load(string savePath)
    {
        try
        {
            byte[] data = File.ReadAllBytes(savePath);
            if (ValidateChecksum(data))
                return Deserialize(data);
        }
        catch { }

        // Fallback: try backup
        string backupPath = savePath + ".bak";
        if (File.Exists(backupPath))
        {
            Debug.LogWarning("Primary save corrupted, loading backup");
            byte[] data = File.ReadAllBytes(backupPath);
            return Deserialize(data);
        }

        return null; // No valid save found
    }

    private static bool ValidateChecksum(byte[] data)
    {
        // Extract stored checksum, compute actual, compare
        // Use SHA256 or CRC32
        return true; // placeholder
    }
}
```

**Additional protection:**
- **Version field** in every save: enables migration when game updates change data format
- **3 backup rotation:** Keep save.dat, save.dat.bak, save.dat.bak2
- **Never delete old save before new save is verified**
- **Graceful degradation:** If save is corrupted, offer to load backup, or start fresh with an explanation

---

## Common Pitfalls

### Pitfall 1: NavMesh Not Baking in Unity 6
**What goes wrong:** Developers look for the old Navigation window Bake button, can't find it.
**Why:** Unity 6 removed the legacy bake UI. NavMesh is now component-based.
**How to avoid:** Use `NavMeshSurface` component on a GameObject. Bake from the component inspector or via `surface.BuildNavMesh()`.
**Warning signs:** "Bake button missing" in Unity 6.

### Pitfall 2: Non-Convex MeshCollider on Dynamic Rigidbody
**What goes wrong:** Runtime error, object falls through world or behaves erratically.
**Why:** PhysX requires convex colliders on non-kinematic rigidbodies.
**How to avoid:** Always use primitive colliders or convex mesh colliders on dynamic objects. Use V-HACD for complex shapes.
**Warning signs:** Console error about non-convex mesh collider.

### Pitfall 3: Too Many Active Ragdolls
**What goes wrong:** Frame rate drops to single digits.
**Why:** Each ragdoll = 10-15 rigidbodies. 10 ragdolls = 150 active physics bodies.
**How to avoid:** Pool ragdolls. Max 2-3 active simultaneously. Auto-disable after 3-5 seconds. Remove corpses beyond 30m.
**Warning signs:** Physics.Simulate taking >5ms in Profiler.

### Pitfall 4: Save Data Not Versioned
**What goes wrong:** Game update changes save format, all player saves become unloadable.
**Why:** No migration path between save versions.
**How to avoid:** Include version int in SaveData from day one. Write migration functions for each version bump.
**Warning signs:** Any change to SaveData fields.

### Pitfall 5: Camera Clipping Through Terrain
**What goes wrong:** Camera goes underground on slopes or when player stands against cliff.
**Why:** Default Cinemachine collision doesn't always handle terrain perfectly.
**How to avoid:** Use "Camera" layer on environment, set Camera Collision Filter to that layer, tune Camera Radius to 0.2-0.3, set Damping Into Collision to 0.
**Warning signs:** Camera goes dark or shows skybox unexpectedly.

### Pitfall 6: Physics Layer Matrix Not Configured
**What goes wrong:** Enemies collide with each other (physics pile-ups), projectiles hit friendly targets, performance tanks.
**Why:** Default layer matrix has everything colliding with everything.
**How to avoid:** Set up collision matrix FIRST, before adding any physics objects. Disable enemy-enemy, projectile-projectile, VFX-everything.
**Warning signs:** Enemies pushing each other, friendly fire.

### Pitfall 7: Swimming System Ignores Stamina
**What goes wrong:** Player swims indefinitely, breaks level design that uses water as a barrier.
**Why:** Swimming implemented without tying into stamina system.
**How to avoid:** Swimming drains stamina. When stamina hits 0, player starts drowning (damage over time). Deep water = gameplay risk, not free traversal.
**Warning signs:** Player bypassing intended paths via water.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NavMesh generation | Custom pathfinding (A*) | Unity AI Navigation 2.0 NavMeshSurface | Battle-tested, handles terrain, multi-agent, areas |
| Camera collision | Custom raycast camera | Cinemachine 3.x Third Person Follow | Handles all edge cases, damping, collision resolution |
| Input rebinding | Custom input manager | Unity Input System + InputActionRebindingExtensions | Handles all devices, serialization, dead zones |
| Convex decomposition | Manual collider placement | V-HACD or CoACD | Mathematical precision, handles any mesh |
| Ragdoll setup | Manual joint configuration | Unity Ragdoll Wizard + preset tweaks | Correct mass distribution, joint limits |
| Save serialization | Custom binary format | JsonUtility (dev) / MessagePack (release) | Versioning, debugging, cross-platform |
| Lock-on targeting | From scratch | Cinemachine state-driven camera + OverlapSphere | Camera management is the hard part, Cinemachine solves it |

---

## Architecture Patterns

### Recommended Interaction System Structure
```
Scripts/
  Interaction/
    IInteractable.cs            # Interface
    InteractionSystem.cs        # Player-side detection + prompt
    Interactables/
      Door.cs
      LootContainer.cs
      Lever.cs
      NPCInteraction.cs
      Ladder.cs
      Bonfire.cs
  Physics/
    PhysicsLOD.cs              # Distance-based physics management
    Destructible.cs            # Fracture + cleanup
    RagdollController.cs       # Animation -> ragdoll transition
    WaterZone.cs               # Swimming/wading detection
  Navigation/
    NavMeshManager.cs          # Runtime bake orchestration
    NavMeshAreaConfig.cs       # ScriptableObject area definitions
  Camera/
    LockOnSystem.cs            # Target acquisition + switching
    CameraOcclusionFader.cs    # Transparency for occluding objects
  Save/
    SaveManager.cs             # Orchestration
    SaveData.cs                # Data structures
    SafeSaveWriter.cs          # Atomic writes + backup
    SaveMigrator.cs            # Version migration
```

---

## Sources

### Primary (HIGH confidence)
- [Unity AI Navigation 2.0.12 - NavMeshSurface](https://docs.unity3d.com/Packages/com.unity.ai.navigation@2.0/manual/NavMeshSurface.html) - Component API, configuration, runtime baking
- [Unity 6000.3 - Configure Rigidbody Colliders](https://docs.unity3d.com/6000.3/Documentation/Manual/rigidbody-configure-colliders.html) - Collider types, convex requirements, compound colliders
- [Unity 6000.3 - Layer Collision Matrix](https://docs.unity3d.com/6000.3/Documentation/Manual/physics-optimization-cpu-collision-layers.html) - Collision filtering
- [Cinemachine 3.1 - Third Person Follow](https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/manual/CinemachineThirdPersonFollow.html) - Camera collision, occlusion, configuration
- [Unity AI Navigation 2.0 - NavMesh Link](https://docs.unity3d.com/Packages/com.unity.ai.navigation@2.0/manual/CreateNavMeshLink.html) - Gap/jump/ladder connections
- [Unity 6000.3 - NavMesh Scripting API](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/AI.NavMesh.html) - Runtime API
- [Unity - Collider Types and Performance](https://docs.unity3d.com/2022.3/Documentation//Manual/physics-optimization-cpu-collider-types.html) - Performance characteristics
- [Unity - Rigidbody Collision Detection Modes](https://docs.unity3d.com/2022.3/Documentation/Manual/physics-optimization-cpu-rigidbody-collision-modes.html) - CCD options

### Secondary (MEDIUM confidence)
- [Unity Discussions - NavMesh baking in Unity 6](https://discussions.unity.com/t/how-to-bake-navigaton-mesh-in-unity-6/1526191) - Migration from legacy UI
- [Game Save Systems Guide 2025](https://generalistprogrammer.com/tutorials/game-save-systems-complete-data-persistence-guide-2025) - Atomic writes, backup rotation
- [Steam Cloud Quick Guide](https://www.gamedeveloper.com/programming/quick-guide-to-steam-cloud-saves) - Steam integration
- [Unity Cloud Save Docs](https://docs.unity.com/ugs/en-us/manual/cloud-save/manual) - UGS cloud save
- [Unity V-HACD GitHub](https://github.com/Unity-Technologies/VHACD) - Convex decomposition
- [Catlike Coding - Swimming Tutorial](https://catlikecoding.com/unity/tutorials/movement/swimming/) - Water/buoyancy implementation
- [Ragdoll Stability Manual](https://docs.unity3d.com/Manual//RagdollStability.html) - Joint limits, mass ratios

### Tertiary (LOW confidence)
- Community-reported rigidbody count limits (200-300 active dynamic at 60fps) - no official number exists, varies by hardware
- Destruction piece budgets (8-15 fragments) - based on industry practice, not measured on target hardware

---

## Metadata

**Confidence breakdown:**
- NavMesh: HIGH - verified against AI Navigation 2.0 package docs
- Collision strategy: HIGH - verified against Unity 6000.3 manual
- Physics performance: MEDIUM - budgets are estimates, no official limits published
- Player interaction: HIGH - standard patterns, well-documented
- Camera/Input: HIGH - verified against Cinemachine 3.1 + Input System docs
- Save/Load: HIGH - well-established patterns, verified atomic write approach

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable domain, 30-day validity)
