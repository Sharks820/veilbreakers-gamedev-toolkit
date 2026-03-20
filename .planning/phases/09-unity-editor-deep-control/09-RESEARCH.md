# Phase 9: Unity Editor Deep Control - Research

**Researched:** 2026-03-20
**Domain:** Unity Editor scripting -- programmatic prefab, component, hierarchy, import pipeline, project settings, and package management
**Confidence:** HIGH

## Summary

Phase 9 adds deep Unity Editor control to the MCP toolkit: creating/modifying prefabs (including variants and nesting), configuring components via SerializedObject/SerializedProperty, manipulating scene hierarchies, managing project settings (Player/Build/Quality/Physics/Time/Graphics), installing packages via PackageManager.Client and manifest.json editing, configuring asset import (ModelImporter, TextureImporter, material remapping), performing GUID-safe asset operations (move/rename/delete via AssetDatabase), creating Assembly Definitions, and generating Unity Presets.

All of this follows the existing v1.0 pattern: Python generates complete C# editor scripts, writes them to `Assets/Editor/Generated/`, and returns `next_steps` for recompile + execute via mcp-unity. The key difference from v1.0 is that Phase 9 scripts heavily use `PrefabUtility`, `SerializedObject`, `AssetDatabase`, `PlayerSettings`, `QualitySettings`, and `PackageManager.Client` -- APIs that are editor-only and require `Undo` registration for safe operation.

**Primary recommendation:** Add 3 new compound tools (`unity_prefab`, `unity_settings`, `unity_assets`) with corresponding template files, following the exact handler + template pattern established in v1.0. Every generated C# script must use `Undo.RecordObject`/`Undo.RegisterCreatedObjectUndo` and write enhanced result JSON with `changed_assets`, `warnings`, and `validation_status` fields.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Full auto-wire via versioned profiles**: When creating prefabs, toolkit auto-adds components based on prefab type (hero, monster, prop, UI) matching VeilBreakers component patterns (e.g. monster prefab gets Combatant, NavMeshAgent, CapsuleCollider, Animator). Auto-wire rules stored as versioned JSON profiles (not hardcoded) so game architecture can evolve without toolkit rewrites
- **Ghost prefab scaffolding**: Since no 3D models exist yet, support creating "scaffold" prefabs with correct components + placeholder visuals (transparent capsule with brand icon) for gameplay testing before Blender pipeline finishes
- **Deterministic selector schema**: Primary lookup by name, fallback to full hierarchy path, with GUID-based and regex/query selectors for disambiguation. Must handle duplicated names, nested prefabs, and variant chains safely
- **Scene vs Prefab Mode context**: Explicit "target context" parameter -- modifying a specific scene instance vs editing the master prefab asset uses different PrefabUtility API calls
- **Prefab variants are first-class**: Support base prefab + variants with overrides. Critical for corruption tiers (5 levels) and brand variants (10 brands)
- **Variant-matrix generator**: Generate corruption tier 1-5 x brand 1-10 x archetype variants from a single base prefab/profile automatically
- **Full nested prefab support**: Rooms contain furniture prefabs, buildings contain rooms, towns contain buildings. No depth limits but with override chain guardrails
- **Custom + built-in components via SerializedObject API**: Configure any serialized field on any component using SerializedObject API -- custom MonoBehaviours (Combatant, AudioConfig, HeroDisplayConfig), ScriptableObject references, and all Unity built-in components
- **Reflect component action**: `reflect_component` returns all serialized field names, types, and current values for a given script so Claude doesn't have to guess field names
- **Batch operations**: Apply component configurations to multiple objects at once using tag, layer, or name pattern matching
- **Full physics configuration**: Create PhysicsMaterials, assign to colliders, configure layer collision matrix
- **All joint types supported**: HingeJoint, SpringJoint, ConfigurableJoint, CharacterJoint, FixedJoint
- **Type-based presets for import**: Define import presets per asset type (hero, monster, weapon, prop, environment) with correct scale, compression, animation type, normals
- **Atomic import sequence**: Enforce correct order -- 1. Textures, 2. Material creation, 3. FBX import, 4. Material remapping
- **Auto-generate materials + remap option**: Auto-create PBR materials from imported textures by default. Option to remap to existing project materials
- **Import pipeline precedence**: asset-type presets, folder-level rules, .preset files, existing AssetPostprocessors, Unity defaults
- **Platform-aware texture compression**: Auto-set compression format per platform (ASTC for mobile, DXT5 for PC) + max texture size by asset type
- **Generate Unity Presets (.preset files)**: Create .preset files alongside import configuration (PIPE-09)
- **Auto-sync tags/layers from code**: Read Constants.cs tag/layer definitions and ensure Unity TagManager matches
- **Multi-source package management**: Install from Unity registry, OpenUPM scoped registries, and git URLs. Handle manifest.json + scopedRegistries entries
- **Full Player Settings**: Company/product name, icon, splash, scripting backend (IL2CPP/Mono), API compatibility, color space, resolution defaults (EDIT-05)
- **Full Assembly Definition management**: Create .asmdef files, add/remove assembly references, set scripting defines, configure platform targets (EDIT-15)
- **Undo protocol mandatory**: Every generated C# script must use Undo.RegisterCreatedObjectUndo / Undo.RecordObject
- **Batch scripting**: Support generating one large C# "Job" script that performs multiple operations in one compilation cycle
- **Dependency-aware asset operations**: Reference scanning before delete/move/rename. GUID preservation + warn on live dependencies + safe-delete mode
- **Enhanced result JSON**: Every tool returns changed_assets, warnings, conflicts, reimport_required, validation_status
- **Post-operation validation**: After mutations, verify prefab opens cleanly, required components present, import settings applied correctly
- **validate_project_integrity action**: Scan all prefabs and report missing components, broken script references, missing materials, tag/layer mismatches
- **Tag/layer drift detection**: Source-of-truth is Constants.cs -- detect and warn when layers are edited manually

### Claude's Discretion
- NavMesh Areas and Off-Mesh Links configuration approach (PHYS-02)
- Bone socket attachment system implementation details (EQUIP-02)
- Quality Settings tier configuration (shadow distance, texture quality, AA, VSync, LOD bias)
- Build Settings scene list and platform switching approach
- Time settings (fixed timestep) and Graphics settings (render pipeline asset) configuration
- Tool structure: recommended 3 new tools (unity_prefab, unity_settings, unity_assets) but implementation may adjust based on action count balance

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EDIT-01 | Create, modify, delete Prefabs (nested + variants) | PrefabUtility.SaveAsPrefabAsset, InstantiatePrefab, variant creation via prefab-instance-save pattern |
| EDIT-02 | Add, remove, configure any Component | SerializedObject/SerializedProperty API, Undo.AddComponent, ObjectFactory.AddComponent |
| EDIT-03 | Manipulate scene hierarchy (create empties, rename, reparent, enable/disable, set layer/tag) | GameObject API, Transform.SetParent, Undo.RegisterCreatedObjectUndo |
| EDIT-04 | Configure physics layers, layer collision matrix, physics materials | Physics.IgnoreLayerCollision, PhysicsMaterial creation, SerializedObject on TagManager |
| EDIT-05 | Manage Player Settings | PlayerSettings static properties + SerializedObject("ProjectSettings/ProjectSettings.asset") |
| EDIT-06 | Manage Build Settings | EditorBuildSettings.scenes, EditorUserBuildSettings |
| EDIT-07 | Configure Quality Settings | QualitySettings + SerializedObject("ProjectSettings/QualitySettings.asset") |
| EDIT-08 | Install/remove/update Unity packages | PackageManager.Client.Add/Remove/List + manifest.json editing for scoped registries |
| EDIT-09 | Create/manage custom Tags, Sorting Layers, Physics Layers | SerializedObject on TagManager.asset |
| EDIT-10 | Asset operations (move, rename, delete, duplicate, create folders) with GUID preservation | AssetDatabase.MoveAsset, RenameAsset, DeleteAsset, CopyAsset, CreateFolder |
| EDIT-11 | Configure Time, Graphics, Editor preferences | Time.fixedDeltaTime via SerializedObject, GraphicsSettings, EditorPrefs |
| EDIT-12 | Configure FBX ModelImporter settings | ModelImporter API (meshCompression, animationType, scale, normals) |
| EDIT-13 | Configure TextureImporter settings | TextureImporter + SetPlatformTextureSettings for per-platform compression |
| EDIT-14 | Material remapping on FBX import | ModelImporter.SearchAndRemapMaterials, material extraction, custom remapping |
| EDIT-15 | Assembly Definition management | JSON file creation (.asmdef format), CompilationPipeline for validation |
| IMP-01 | Manage .meta files and GUIDs when moving/renaming assets | AssetDatabase.MoveAsset auto-preserves GUID; never use File.Move |
| IMP-02 | Configure material remapping on FBX import | Same as EDIT-14 -- ModelImporter material system |
| PHYS-01 | Configure physics Joints (Hinge, Spring, Configurable, Character, Fixed) | AddComponent<JointType>, SerializedObject for joint property config |
| PHYS-02 | NavMeshObstacle, Off-Mesh Links, NavMesh Areas with cost configuration | NavMeshSurface, NavMeshModifier, NavMeshLink (com.unity.ai.navigation 2.0.9) |
| PIPE-09 | Generate Unity Presets for reusable import/component configuration | Preset class (new Preset(source), AssetDatabase.CreateAsset for .preset files) |
| EQUIP-02 | Bone socket attachment system (10 standard sockets) | Transform.Find on bone hierarchy, empty GameObject parenting to bone transforms |
</phase_requirements>

## Standard Stack

### Core Unity APIs (Editor-Only)

| API | Namespace | Purpose | Why Standard |
|-----|-----------|---------|--------------|
| PrefabUtility | UnityEditor | Prefab creation, variant creation, override management, nested prefab support | Only API for programmatic prefab operations; SaveAsPrefabAsset + InstantiatePrefab pattern |
| SerializedObject / SerializedProperty | UnityEditor | Generic property access on any Unity Object -- read/write any serialized field | Required for component configuration, project settings access, undo-safe field modification |
| AssetDatabase | UnityEditor | Asset CRUD operations, import, reimport, path management, GUID queries | Only safe way to move/rename/delete assets while preserving .meta file integrity |
| PlayerSettings | UnityEditor | Company, product, scripting backend, API compat, color space, icons | Direct static properties for most settings; SerializedObject for advanced |
| EditorBuildSettings | UnityEditor | Scene list management, platform switching | EditorBuildSettings.scenes array for build scene configuration |
| QualitySettings | UnityEngine | Shadow distance, texture quality, AA, VSync, LOD bias | Runtime-accessible class; SerializedObject for editor-time multi-tier configuration |
| PackageManager.Client | UnityEditor.PackageManager | Package install/remove/list/search | Client.Add returns async AddRequest; required for programmatic package management |
| ModelImporter | UnityEditor | FBX import settings (scale, compression, animation, rig type) | Accessed via AssetImporter.GetAtPath for import configuration |
| TextureImporter | UnityEditor | Texture import settings (max size, compression, sRGB, platform overrides) | SetPlatformTextureSettings for per-platform texture compression |
| Preset | UnityEditor.Presets | Reusable settings templates (.preset files) | new Preset(source) captures all serialized properties; ApplyTo for application |
| Undo | UnityEditor | Undo registration for all mutations | Mandatory for all destructive operations; RecordObject + RegisterCreatedObjectUndo |

### Navigation APIs (for PHYS-02)

| API | Package | Purpose | Version |
|-----|---------|---------|---------|
| NavMeshSurface | com.unity.ai.navigation | NavMesh building for specific agent types | 2.0.9 (installed) |
| NavMeshModifier | com.unity.ai.navigation | Per-object area type and NavMesh inclusion control | 2.0.9 |
| NavMeshLink | com.unity.ai.navigation | Connects NavMesh surfaces (replaces OffMeshLink) | 2.0.9 |
| NavMeshObstacle | UnityEngine.AI | Runtime obstacle carving | Built-in |

### Python-Side (MCP Toolkit)

| Library | Purpose | Already Installed |
|---------|---------|-------------------|
| FastMCP | MCP server framework | Yes (v1.0) |
| pydantic-settings | Settings with env vars | Yes (v1.0) |
| pytest | Test framework | Yes (v1.0) |

No new Python dependencies required. Phase 9 is pure extension of the existing `unity_server.py` architecture with new handlers and template files.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SerializedObject for settings | Direct reflection on settings objects | SerializedObject handles undo, prefab overrides, multi-editing -- reflection does not |
| manifest.json editing for packages | PackageManager.Client.Add for all packages | Client.Add does not support scopedRegistries addition; manifest.json needed for OpenUPM |
| JSON profiles for auto-wire | Hardcoded C# dictionaries | JSON profiles are user-editable and version-independent; dictionaries would require toolkit code changes when game architecture evolves |

## Architecture Patterns

### Recommended Project Structure (New Files)

```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  unity_server.py                          # Extended with 3 new tool functions
  shared/
    unity_templates/
      prefab_templates.py                  # NEW: prefab, component, hierarchy C# generators
      settings_templates.py                # NEW: project settings, packages, tags/layers C# generators
      asset_templates.py                   # NEW: import pipeline, asset ops, presets C# generators
    auto_wire_profiles/                    # NEW: JSON prefab type profiles
      monster.json
      hero.json
      prop.json
      ui.json
tests/
  test_prefab_templates.py                # NEW
  test_settings_templates.py              # NEW
  test_asset_templates.py                 # NEW
```

### Pattern 1: Compound Tool with Handler Dispatch (Existing, Extend)

**What:** Each compound tool declares a `Literal` action type, dispatches to `_handle_*` functions.
**When to use:** Every new tool follows this pattern exactly.
**Example:**
```python
# Source: existing unity_server.py pattern (verified in codebase)
@mcp.tool()
async def unity_prefab(
    action: Literal[
        "create",           # EDIT-01: Create prefab from scene objects
        "create_variant",   # EDIT-01: Create prefab variant
        "modify",           # EDIT-01: Modify existing prefab asset
        "delete",           # EDIT-01: Delete prefab asset
        "create_scaffold",  # Ghost scaffolding
        "add_component",    # EDIT-02: Add component
        "remove_component", # EDIT-02: Remove component
        "configure",        # EDIT-02: Configure component properties
        "reflect_component",# EDIT-02: Introspect component fields
        "hierarchy",        # EDIT-03: Hierarchy operations
        "batch_configure",  # Batch operations
        "generate_variants",# Variant matrix generator
        "setup_joints",     # PHYS-01: Physics joints
        "setup_bone_sockets", # EQUIP-02: Bone socket attachment
    ],
    ...
) -> str:
    try:
        if action == "create":
            return await _handle_prefab_create(...)
        # ... dispatch pattern continues
    except Exception as exc:
        logger.exception("unity_prefab action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})
```

### Pattern 2: C# Template with Undo Registration (New Requirement)

**What:** Every generated C# editor script must register undo operations.
**When to use:** All Phase 9 templates -- every mutation must be undoable.
**Example:**
```csharp
// Source: Unity API docs - Undo class
// https://docs.unity3d.com/ScriptReference/Undo.html
[MenuItem("VeilBreakers/Prefab/Create Prefab")]
public static void Execute()
{
    try
    {
        // For new objects
        var go = new GameObject("MyPrefab");
        Undo.RegisterCreatedObjectUndo(go, "VB Create Prefab");

        // For modifying existing objects
        Undo.RecordObject(existingObject, "VB Modify Component");
        existingObject.someProperty = newValue;

        // For adding components
        var comp = Undo.AddComponent<Rigidbody>(go);

        // Save prefab
        bool success;
        PrefabUtility.SaveAsPrefabAsset(go, assetPath, out success);

        // Clean up scene instance
        Undo.DestroyObjectImmediate(go);

        // Write enhanced result JSON
        var result = new {
            status = "success",
            action = "create",
            changed_assets = new[] { assetPath },
            warnings = new string[0],
            validation_status = "valid"
        };
        File.WriteAllText("Temp/vb_result.json", JsonUtility.ToJson(result));
    }
    catch (Exception ex) { /* error handling */ }
}
```

### Pattern 3: Prefab Variant Creation via Instance-Save

**What:** Creating a prefab variant requires: load base -> instantiate -> modify -> SaveAsPrefabAsset (which detects the instance connection and creates a variant).
**When to use:** EDIT-01 variant creation, variant-matrix generator.
**Example:**
```csharp
// Source: PrefabUtility.SaveAsPrefabAsset docs
// https://docs.unity3d.com/ScriptReference/PrefabUtility.SaveAsPrefabAsset.html
// Key insight: "If the input is a Prefab instance root, the result becomes a Prefab Variant"
var basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(basePrefabPath);
var instance = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);

// Modify the instance (overrides become variant overrides)
var combatant = instance.GetComponent<Combatant>();
if (combatant != null)
{
    var so = new SerializedObject(combatant);
    so.FindProperty("_corruption").floatValue = corruptionLevel;
    so.ApplyModifiedProperties();
}

// Save as variant -- Unity auto-detects the prefab connection
bool success;
PrefabUtility.SaveAsPrefabAsset(instance, variantPath, out success);

// Clean up scene instance
Object.DestroyImmediate(instance);
```

### Pattern 4: SerializedObject for Generic Property Access

**What:** Access any serialized field on any component without knowing the type at compile time.
**When to use:** EDIT-02 configure action, reflect_component, batch_configure.
**Example:**
```csharp
// Source: SerializedObject docs
// https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SerializedObject.html
var component = targetObject.GetComponent(componentTypeName);
var so = new SerializedObject(component);
so.Update();

// Iterate all properties (for reflect_component)
var prop = so.GetIterator();
while (prop.NextVisible(true))
{
    // prop.name, prop.type, prop.propertyType, current value
}

// Set specific property (for configure)
var targetProp = so.FindProperty(propertyName);
switch (targetProp.propertyType)
{
    case SerializedPropertyType.Float:
        targetProp.floatValue = floatVal;
        break;
    case SerializedPropertyType.Integer:
        targetProp.intValue = intVal;
        break;
    case SerializedPropertyType.String:
        targetProp.stringValue = strVal;
        break;
    case SerializedPropertyType.Boolean:
        targetProp.boolValue = boolVal;
        break;
    case SerializedPropertyType.ObjectReference:
        targetProp.objectReferenceValue = AssetDatabase.LoadAssetAtPath<Object>(refPath);
        break;
    // ... Color, Vector2, Vector3, Enum, etc.
}
so.ApplyModifiedProperties();
```

### Pattern 5: TagManager Serialized Access for Tags/Layers

**What:** Tags and layers are stored in ProjectSettings/TagManager.asset, accessed via SerializedObject.
**When to use:** EDIT-09, auto-sync from Constants.cs.
**Example:**
```csharp
// Source: Unity TagManager documentation + community solutions
// https://docs.unity3d.com/Manual/class-TagManager.html
var tagManager = new SerializedObject(
    AssetDatabase.LoadMainAssetAtPath("ProjectSettings/TagManager.asset")
);

// Add tag
var tags = tagManager.FindProperty("tags");
for (int i = 0; i < tags.arraySize; i++)
{
    if (tags.GetArrayElementAtIndex(i).stringValue == tagName) return; // already exists
}
tags.InsertArrayElementAtIndex(tags.arraySize);
tags.GetArrayElementAtIndex(tags.arraySize - 1).stringValue = tagName;

// Add layer (layers 8-31 are user-configurable)
var layers = tagManager.FindProperty("layers");
for (int i = 8; i < 32; i++)
{
    var layerProp = layers.GetArrayElementAtIndex(i);
    if (string.IsNullOrEmpty(layerProp.stringValue))
    {
        layerProp.stringValue = layerName;
        break;
    }
}
tagManager.ApplyModifiedProperties();
```

### Pattern 6: Package Management (Multi-Source)

**What:** Install packages from UPM registry (Client.Add), OpenUPM scoped registries (manifest.json editing), and git URLs (Client.Add with URL).
**When to use:** EDIT-08 package management.
**Example:**
```csharp
// UPM registry package
var request = Client.Add("com.unity.cinemachine@3.1.0");

// Git URL package
var request = Client.Add("https://github.com/user/repo.git#v1.0.0");

// OpenUPM: Must edit manifest.json directly for scopedRegistries
// Then Client.Add for the actual package
string manifestPath = Path.Combine(Application.dataPath, "..", "Packages/manifest.json");
string json = File.ReadAllText(manifestPath);
// Parse, add scopedRegistry entry, add dependency, write back
```

### Anti-Patterns to Avoid

- **File.Move/File.Copy for asset operations:** Always use AssetDatabase.MoveAsset/CopyAsset. File system operations bypass GUID tracking and break all references.
- **Direct field assignment without SerializedObject:** Bypasses undo, doesn't trigger prefab override tracking, doesn't mark dirty.
- **Forgetting to call AssetDatabase.Refresh after file writes:** Generated C# scripts need a refresh cycle to be recognized.
- **Calling AssetDatabase.Refresh inside OnPostprocessAllAssets:** Causes infinite reimport loops (the existing BlenderFBXImportPostprocessor already has a comment warning about this).
- **Using Object.Instantiate instead of PrefabUtility.InstantiatePrefab:** Object.Instantiate breaks the prefab connection; PrefabUtility.InstantiatePrefab preserves it (critical for variant creation).
- **Hardcoding component type expectations:** Use the reflect_component pattern to discover fields dynamically rather than assuming field names.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GUID preservation on asset move | Manual .meta file copying | AssetDatabase.MoveAsset | Handles .meta atomically; manual copy can corrupt GUID references |
| Prefab variant creation | Manual prefab file manipulation | PrefabUtility.InstantiatePrefab + SaveAsPrefabAsset | Unity auto-detects instance connection and creates proper variant chain |
| Component property iteration | Reflection (System.Reflection) | SerializedObject.GetIterator | SerializedObject respects Unity serialization rules, handles undo, multi-edit |
| Tag/layer creation | Direct YAML editing of TagManager.asset | SerializedObject on TagManager.asset | Direct YAML editing can corrupt the file and miss format changes between Unity versions |
| Package installation | Direct manifest.json editing alone | PackageManager.Client.Add (UPM) + manifest.json (scoped registries only) | Client.Add handles resolution, dependency chains, and compilation triggers |
| Undo for created objects | Manual tracking | Undo.RegisterCreatedObjectUndo | Unity's undo system is integrated with prefab overrides, scene dirty state, and history |

**Key insight:** Unity's editor APIs are designed as a cohesive system -- SerializedObject, PrefabUtility, AssetDatabase, and Undo all interoperate. Using any of these partially (e.g., SerializedObject without Undo) breaks the contract and causes subtle bugs.

## Common Pitfalls

### Pitfall 1: Prefab Variant vs Independent Prefab Confusion
**What goes wrong:** Calling SaveAsPrefabAsset on a prefab instance creates a variant instead of an independent prefab. Calling it on an unpacked object creates an independent prefab instead of a variant.
**Why it happens:** SaveAsPrefabAsset auto-detects the prefab connection on the input GameObject.
**How to avoid:** For variants: use `PrefabUtility.InstantiatePrefab(base)` then save. For independent: `PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction)` before saving.
**Warning signs:** Variant overrides not showing in Inspector; changes to base prefab not propagating.

### Pitfall 2: SerializedProperty Type Mismatch
**What goes wrong:** Setting `floatValue` on an `int` property silently fails or corrupts data.
**Why it happens:** SerializedProperty has separate value accessors per type (floatValue, intValue, stringValue, etc.).
**How to avoid:** Always check `property.propertyType` before setting values. Build a switch/map in the template that handles all SerializedPropertyType enum values.
**Warning signs:** Properties silently not updating; values reverting on play.

### Pitfall 3: Recompile Cascade on Batch Operations
**What goes wrong:** 10 sequential tool calls each generate a C# script, causing 10 recompile cycles (3-5s each = 30-50s wasted).
**Why it happens:** Each new .cs file triggers Unity's compilation pipeline.
**How to avoid:** Support a "batch job" mode that generates one large C# script with multiple operations, wrapped in `AssetDatabase.StartAssetEditing()` / `StopAssetEditing()`. The user decision explicitly requires this.
**Warning signs:** Long waits between sequential operations; Unity Editor becoming unresponsive.

### Pitfall 4: AssetDatabase Refresh Timing
**What goes wrong:** Generated C# script exists on disk but Unity hasn't compiled it yet. Executing menu item fails.
**Why it happens:** Unity's asset pipeline is asynchronous; file writes don't immediately register.
**How to avoid:** The existing pattern (write script, return next_steps telling user to recompile first) is correct. For batch operations, use `AssetDatabase.StartAssetEditing()` at the beginning and `AssetDatabase.StopAssetEditing()` + `AssetDatabase.Refresh()` at the end.
**Warning signs:** "Menu item not found" errors; scripts appearing in project but not compiling.

### Pitfall 5: TagManager Layer Slot Exhaustion
**What goes wrong:** Unity has only 32 layers (0-31), with 0-7 reserved. Attempting to add a 25th user layer silently fails.
**Why it happens:** No error from the API -- the loop just doesn't find an empty slot.
**How to avoid:** Count existing layers before adding. Return warning in result JSON when approaching capacity. VeilBreakers currently defines layers 8 (Player) and 9 (Enemy) in Constants.cs, so 22 slots remain.
**Warning signs:** Layer assignments not taking effect; objects not interacting with physics correctly.

### Pitfall 6: Nested Prefab Override Chain Depth
**What goes wrong:** Deep nesting (town > building > room > furniture > sub-component) creates long override chains that become hard to debug and slow to resolve.
**Why it happens:** Each nesting level adds an override resolution step.
**How to avoid:** Implement a configurable max depth check (recommended: 4 levels). Warn when exceeding threshold but don't block.
**Warning signs:** Slow prefab loading; confusing override indicators in Inspector.

### Pitfall 7: Material Remapping Before Textures Import
**What goes wrong:** FBX imports before its textures are in the project, getting default pink materials.
**Why it happens:** Out-of-order import -- FBX processed before texture assets exist.
**How to avoid:** The atomic import sequence (user decision): 1. Import textures, 2. Create materials, 3. Import FBX, 4. Remap materials. The toolkit must enforce this ordering.
**Warning signs:** Pink/magenta materials on imported models; broken material references.

### Pitfall 8: Existing BlenderFBXImportPostprocessor Conflict
**What goes wrong:** Phase 9 import configuration conflicts with the existing `BlenderFBXImportPostprocessor` (order 100).
**Why it happens:** Two AssetPostprocessors both trying to set the same ModelImporter properties.
**How to avoid:** Phase 9 import presets should work at a different level (Preset files + explicit toolkit-triggered reimport), not as another AssetPostprocessor. When explicit import configuration is requested, it should use `AssetImporter.GetAtPath` + direct property setting rather than competing with the existing postprocessor. For folder-based auto-rules, use a higher postprocess order (200+) and only set properties that the existing postprocessor doesn't touch.
**Warning signs:** Import settings toggling between values; FBX reimporting multiple times.

## Code Examples

### Creating a Prefab with Auto-Wire Components
```csharp
// Source: PrefabUtility docs + VeilBreakers Combatant.cs pattern
[MenuItem("VeilBreakers/Prefab/Create Monster Prefab")]
public static void Execute()
{
    string prefabName = "{PREFAB_NAME}";
    string savePath = "Assets/Prefabs/Monsters/" + prefabName + ".prefab";

    // Create scaffold GameObject
    var go = new GameObject(prefabName);
    Undo.RegisterCreatedObjectUndo(go, "VB Create Monster Prefab");

    // Add placeholder visual (ghost scaffolding)
    var capsule = GameObject.CreatePrimitive(PrimitiveType.Capsule);
    capsule.transform.SetParent(go.transform);
    capsule.transform.localPosition = Vector3.zero;
    var renderer = capsule.GetComponent<MeshRenderer>();
    // Set transparent material for ghost effect

    // Auto-wire monster components (from profile)
    Undo.AddComponent<CapsuleCollider>(go);
    var agent = Undo.AddComponent<NavMeshAgent>(go);
    var animator = Undo.AddComponent<Animator>(go);
    // Combatant is a custom MonoBehaviour
    var combatant = Undo.AddComponent<VeilBreakers.Combat.Combatant>(go);

    // Configure via SerializedObject
    var so = new SerializedObject(combatant);
    so.FindProperty("_brand").enumValueIndex = {BRAND_INDEX};
    so.FindProperty("_displayName").stringValue = prefabName;
    so.ApplyModifiedProperties();

    // Save as prefab
    Directory.CreateDirectory(Path.GetDirectoryName(savePath));
    bool success;
    var prefabAsset = PrefabUtility.SaveAsPrefabAsset(go, savePath, out success);

    // Clean up scene
    Undo.DestroyObjectImmediate(go);

    // Write result
    // ... enhanced JSON with changed_assets, validation_status
}
```

### Configuring Import Settings on FBX
```csharp
// Source: ModelImporter API docs
// https://docs.unity3d.com/ScriptReference/ModelImporter.html
[MenuItem("VeilBreakers/Assets/Configure FBX Import")]
public static void Execute()
{
    string assetPath = "{ASSET_PATH}";
    var importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
    if (importer == null) { /* error */ return; }

    Undo.RecordObject(importer, "VB Configure FBX Import");

    // Geometry
    importer.globalScale = {SCALE}f;
    importer.meshCompression = ModelImporterMeshCompression.{COMPRESSION};
    importer.isReadable = {IS_READABLE};
    importer.optimizeMeshPolygons = true;
    importer.optimizeMeshVertices = true;

    // Animation
    importer.animationType = ModelImporterAnimationType.{ANIM_TYPE};
    importer.importAnimation = {IMPORT_ANIM};

    // Material
    importer.materialImportMode = ModelImporterMaterialImportMode.{MATERIAL_MODE};

    // Apply and reimport
    importer.SaveAndReimport();
}
```

### Platform-Aware Texture Compression
```csharp
// Source: TextureImporter.SetPlatformTextureSettings docs
// https://docs.unity3d.com/ScriptReference/TextureImporter.GetPlatformTextureSettings.html
[MenuItem("VeilBreakers/Assets/Configure Texture Import")]
public static void Execute()
{
    string assetPath = "{ASSET_PATH}";
    var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
    if (importer == null) return;

    Undo.RecordObject(importer, "VB Configure Texture Import");

    importer.maxTextureSize = {MAX_SIZE};  // 2048 for hero, 1024 for mob, 512 for prop
    importer.sRGBTexture = {IS_SRGB};     // true for albedo, false for normal/roughness
    importer.mipmapEnabled = true;

    // PC: DXT5
    var pcSettings = importer.GetPlatformTextureSettings("Standalone");
    pcSettings.overridden = true;
    pcSettings.maxTextureSize = {MAX_SIZE};
    pcSettings.format = TextureImporterFormat.DXT5;
    importer.SetPlatformTextureSettings(pcSettings);

    // Android: ASTC
    var androidSettings = importer.GetPlatformTextureSettings("Android");
    androidSettings.overridden = true;
    androidSettings.maxTextureSize = {MAX_SIZE};
    androidSettings.format = TextureImporterFormat.ASTC_6x6;
    importer.SetPlatformTextureSettings(androidSettings);

    importer.SaveAndReimport();
}
```

### Project Settings Configuration
```csharp
// Source: PlayerSettings API docs
// https://docs.unity3d.com/ScriptReference/PlayerSettings.html
[MenuItem("VeilBreakers/Settings/Configure Player Settings")]
public static void Execute()
{
    PlayerSettings.companyName = "{COMPANY}";
    PlayerSettings.productName = "{PRODUCT}";
    PlayerSettings.colorSpace = ColorSpace.{COLOR_SPACE};
    PlayerSettings.SetScriptingBackend(
        BuildTargetGroup.Standalone,
        ScriptingImplementation.{BACKEND}  // IL2CPP or Mono2x
    );
    PlayerSettings.SetApiCompatibilityLevel(
        BuildTargetGroup.Standalone,
        ApiCompatibilityLevel.{API_LEVEL}  // NET_Standard or NET_Unity_4_8
    );

    // Quality Settings via SerializedObject for multi-tier config
    var qualitySettings = new SerializedObject(
        AssetDatabase.LoadMainAssetAtPath("ProjectSettings/QualitySettings.asset")
    );
    // Access quality level array and configure each tier
    // ...
    qualitySettings.ApplyModifiedProperties();
}
```

### Assembly Definition Creation
```csharp
// Source: Unity .asmdef documentation
// https://docs.unity3d.com/6000.3/Documentation/Manual/cus-asmdef.html
// .asmdef files are JSON -- generate and write directly
string asmdefContent = @"{
    ""name"": ""{ASSEMBLY_NAME}"",
    ""rootNamespace"": ""{NAMESPACE}"",
    ""references"": [{REFERENCES}],
    ""includePlatforms"": [{PLATFORMS}],
    ""excludePlatforms"": [],
    ""allowUnsafeCode"": false,
    ""overrideReferences"": false,
    ""precompiledReferences"": [],
    ""autoReferenced"": true,
    ""defineConstraints"": [],
    ""versionDefines"": [],
    ""noEngineReferences"": false
}";
File.WriteAllText(asmdefPath, asmdefContent);
AssetDatabase.Refresh();
```

### Bone Socket Setup (EQUIP-02)
```csharp
// Source: SkinnedMeshRenderer.bones, Transform hierarchy
// https://docs.unity3d.com/ScriptReference/SkinnedMeshRenderer-bones.html
[MenuItem("VeilBreakers/Prefab/Setup Bone Sockets")]
public static void Execute()
{
    string prefabPath = "{PREFAB_PATH}";
    var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
    var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);

    string[] socketNames = {
        "weapon_hand_R", "weapon_hand_L", "shield_hand_L",
        "back_weapon", "hip_L", "hip_R",
        "head", "chest", "spell_hand_R", "spell_hand_L"
    };

    // Standard bone name mappings (Humanoid rig)
    var boneMap = new Dictionary<string, string> {
        {"weapon_hand_R", "RightHand"},
        {"weapon_hand_L", "LeftHand"},
        {"shield_hand_L", "LeftHand"},
        {"back_weapon", "Spine2"},  // Upper back
        {"hip_L", "LeftUpLeg"},
        {"hip_R", "RightUpLeg"},
        {"head", "Head"},
        {"chest", "Spine1"},
        {"spell_hand_R", "RightHand"},
        {"spell_hand_L", "LeftHand"},
    };

    var animator = instance.GetComponent<Animator>();
    foreach (var socket in socketNames)
    {
        // Find bone transform via Animator (for Humanoid rigs)
        // or via Transform.Find for Generic rigs
        Transform bone = null;
        if (animator != null && animator.isHuman)
        {
            // Map socket name to HumanBodyBones enum
            bone = animator.GetBoneTransform(/* mapped HumanBodyBones */);
        }

        if (bone == null)
            bone = instance.transform.FindRecursive(boneMap[socket]);

        if (bone != null)
        {
            var socketObj = new GameObject("Socket_" + socket);
            Undo.RegisterCreatedObjectUndo(socketObj, "VB Add Socket");
            socketObj.transform.SetParent(bone);
            socketObj.transform.localPosition = Vector3.zero;
            socketObj.transform.localRotation = Quaternion.identity;
        }
    }

    // Save back to prefab
    PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
    Object.DestroyImmediate(instance);
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PrefabUtility.CreatePrefab | PrefabUtility.SaveAsPrefabAsset | Unity 2018.3+ | CreatePrefab is obsolete; SaveAsPrefabAsset is the only supported method |
| OffMeshLink component | NavMeshLink (AI Navigation package) | com.unity.ai.navigation 1.0+ | NavMeshLink is more flexible, less overhead; OffMeshLink still works but NavMeshLink preferred |
| Manual quality level arrays | QualitySettings via SerializedObject | Unity 2020+ | SerializedObject approach allows programmatic multi-tier configuration |
| Separate EditorSettings for each platform | PlayerSettings per BuildTargetGroup | Ongoing | Use SetScriptingBackend/SetApiCompatibilityLevel per BuildTargetGroup |

**Deprecated/outdated:**
- `PrefabUtility.CreatePrefab`: Removed. Use `SaveAsPrefabAsset`.
- `PrefabUtility.ReplacePrefab`: Removed. Use `SaveAsPrefabAsset` (overwrites) or `SavePrefabAsset` (in-place save).
- Direct YAML editing of ProjectSettings files: Fragile, version-dependent. Use SerializedObject.

## Open Questions

1. **Auto-wire profile JSON schema**
   - What we know: Profiles map prefab type to component list with default property values
   - What's unclear: Exact schema for property value types (how to represent ObjectReference, Enum, nested structs in JSON)
   - Recommendation: Start with a simple schema supporting primitives + asset paths for references. Iterate based on real usage patterns.

2. **Batch job script generation limits**
   - What we know: One large C# script avoids recompile cascading
   - What's unclear: Maximum practical script size before Unity's compiler slows down or OOMs
   - Recommendation: Cap at 50 operations per batch. Profile with representative workloads during testing.

3. **Constants.cs parsing robustness**
   - What we know: Need to read tag/layer constants from Constants.cs for auto-sync
   - What's unclear: Whether to use regex parsing or proper Roslyn analysis
   - Recommendation: Use targeted regex (the constants follow a strict `public const string TAG_X = "Y"` pattern). Roslyn is overkill for this specific file.

4. **Variant-matrix generator scale**
   - What we know: Need corruption 1-5 x brand 1-10 x archetype = 50+ variants per base prefab
   - What's unclear: Whether 50+ prefab variants in one operation causes Editor performance issues
   - Recommendation: Generate in batches wrapped in `AssetDatabase.StartAssetEditing()` / `StopAssetEditing()`. Test with 10, 50, 100 variants.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already installed, used for 2,740 existing tests) |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_prefab_templates.py tests/test_settings_templates.py tests/test_asset_templates.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDIT-01 | Prefab create/variant/nested/delete C# generation | unit | `pytest tests/test_prefab_templates.py::TestPrefabCreate -x` | Wave 0 |
| EDIT-02 | Component add/remove/configure/reflect C# generation | unit | `pytest tests/test_prefab_templates.py::TestComponentOps -x` | Wave 0 |
| EDIT-03 | Hierarchy manipulation C# generation | unit | `pytest tests/test_prefab_templates.py::TestHierarchy -x` | Wave 0 |
| EDIT-04 | Physics layers/collision matrix/materials C# generation | unit | `pytest tests/test_prefab_templates.py::TestPhysicsConfig -x` | Wave 0 |
| EDIT-05 | PlayerSettings C# generation | unit | `pytest tests/test_settings_templates.py::TestPlayerSettings -x` | Wave 0 |
| EDIT-06 | BuildSettings C# generation | unit | `pytest tests/test_settings_templates.py::TestBuildSettings -x` | Wave 0 |
| EDIT-07 | QualitySettings C# generation | unit | `pytest tests/test_settings_templates.py::TestQualitySettings -x` | Wave 0 |
| EDIT-08 | Package management C# generation + manifest editing | unit | `pytest tests/test_settings_templates.py::TestPackageManagement -x` | Wave 0 |
| EDIT-09 | Tag/layer creation C# generation | unit | `pytest tests/test_settings_templates.py::TestTagsLayers -x` | Wave 0 |
| EDIT-10 | Asset operations C# generation | unit | `pytest tests/test_asset_templates.py::TestAssetOps -x` | Wave 0 |
| EDIT-11 | Time/Graphics settings C# generation | unit | `pytest tests/test_settings_templates.py::TestTimeGraphics -x` | Wave 0 |
| EDIT-12 | FBX ModelImporter config C# generation | unit | `pytest tests/test_asset_templates.py::TestModelImporter -x` | Wave 0 |
| EDIT-13 | TextureImporter config C# generation | unit | `pytest tests/test_asset_templates.py::TestTextureImporter -x` | Wave 0 |
| EDIT-14 | Material remapping C# generation | unit | `pytest tests/test_asset_templates.py::TestMaterialRemap -x` | Wave 0 |
| EDIT-15 | Assembly Definition generation | unit | `pytest tests/test_asset_templates.py::TestAssemblyDef -x` | Wave 0 |
| IMP-01 | GUID-safe asset move/rename C# generation | unit | `pytest tests/test_asset_templates.py::TestAssetOps -x` | Wave 0 |
| IMP-02 | Material remapping (same as EDIT-14) | unit | `pytest tests/test_asset_templates.py::TestMaterialRemap -x` | Wave 0 |
| PHYS-01 | Joint configuration C# generation | unit | `pytest tests/test_prefab_templates.py::TestJointSetup -x` | Wave 0 |
| PHYS-02 | NavMesh areas/links configuration C# generation | unit | `pytest tests/test_prefab_templates.py::TestNavMeshConfig -x` | Wave 0 |
| PIPE-09 | Preset creation C# generation | unit | `pytest tests/test_asset_templates.py::TestPresetCreation -x` | Wave 0 |
| EQUIP-02 | Bone socket setup C# generation | unit | `pytest tests/test_prefab_templates.py::TestBoneSockets -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_prefab_templates.py tests/test_settings_templates.py tests/test_asset_templates.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_prefab_templates.py` -- covers EDIT-01, EDIT-02, EDIT-03, EDIT-04, PHYS-01, PHYS-02, EQUIP-02
- [ ] `tests/test_settings_templates.py` -- covers EDIT-05, EDIT-06, EDIT-07, EDIT-08, EDIT-09, EDIT-11
- [ ] `tests/test_asset_templates.py` -- covers EDIT-10, EDIT-12, EDIT-13, EDIT-14, EDIT-15, IMP-01, IMP-02, PIPE-09

## Sources

### Primary (HIGH confidence)
- [PrefabUtility API](https://docs.unity3d.com/ScriptReference/PrefabUtility.html) -- All prefab creation methods, variant pattern, override management
- [PrefabUtility.SaveAsPrefabAsset](https://docs.unity3d.com/ScriptReference/PrefabUtility.SaveAsPrefabAsset.html) -- Variant auto-detection behavior, parameter details
- [SerializedObject API (Unity 6)](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SerializedObject.html) -- Generic property access, Update/ApplyModifiedProperties pattern
- [AssetDatabase.MoveAsset](https://docs.unity3d.com/ScriptReference/AssetDatabase.MoveAsset.html) -- GUID-preserving asset move
- [PlayerSettings API](https://docs.unity3d.com/ScriptReference/PlayerSettings.html) -- All configurable project settings
- [PackageManager.Client.Add](https://docs.unity3d.com/ScriptReference/PackageManager.Client.Add.html) -- Package installation API
- [TextureImporter.GetPlatformTextureSettings](https://docs.unity3d.com/ScriptReference/TextureImporter.GetPlatformTextureSettings.html) -- Per-platform texture compression
- [Preset API](https://docs.unity3d.com/ScriptReference/Presets.Preset.html) -- Preset creation and application
- [AI Navigation Manual (Unity 6)](https://docs.unity3d.com/6000.3/Documentation/Manual/com.unity.ai.navigation.html) -- NavMeshSurface, NavMeshLink, NavMeshModifier
- [NavMeshSurface Component (2.0.11)](https://docs.unity3d.com/Packages/com.unity.ai.navigation@2.0/manual/NavMeshSurface.html) -- Component configuration details
- [Unity .asmdef Documentation (Unity 6)](https://docs.unity3d.com/6000.3/Documentation/Manual/cus-asmdef.html) -- Assembly Definition JSON format
- [TagManager Documentation](https://docs.unity3d.com/Manual/class-TagManager.html) -- Tag and layer management
- Existing codebase: `unity_server.py` (2912 lines), `editor_templates.py`, `gameplay_templates.py` -- Established patterns
- Existing codebase: `BlenderFBXImportPostprocessor.cs` -- Import postprocessor to avoid conflicting with
- Existing codebase: `Constants.cs` -- Tag/layer definitions (TAG_PLAYER, TAG_ENEMY, TAG_INTERACTABLE, TAG_PROJECTILE; LAYER_PLAYER=8, LAYER_ENEMY=9)
- Existing codebase: `Combatant.cs` -- Component fields for auto-wire reference (Brand, corruption, stats, etc.)
- Existing codebase: `manifest.json` -- Current packages (AI Navigation 2.0.9, PrimeTween via OpenUPM scoped registry)

### Secondary (MEDIUM confidence)
- [Unity Support: Modifying Project Settings via scripting](https://support.unity.com/hc/en-us/articles/115000177803-How-can-I-modify-Project-Settings-via-scripting) -- SerializedObject approach for project settings
- [Community: Creating Prefab Variant from Editor script](https://discussions.unity.com/t/creating-a-prefab-variant-from-within-an-editor-script/950076) -- Confirms InstantiatePrefab + SaveAsPrefabAsset pattern for variants
- [Unity Learn: Assembly Definitions](https://learn.unity.com/tutorial/working-with-assembly-definitions) -- .asmdef best practices
- [Community: Adding Tags/Layers by script](https://discussions.unity.com/t/create-tags-and-layers-in-the-editor-using-script-both-edit-and-runtime-modes/755400) -- SerializedObject on TagManager.asset approach

### Tertiary (LOW confidence)
- None -- all critical claims verified against official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all APIs verified against Unity 6 official documentation
- Architecture: HIGH -- directly extends proven v1.0 compound tool + template pattern
- Pitfalls: HIGH -- documented from official API docs, community discussions, and existing codebase analysis (BlenderFBXImportPostprocessor conflict identified from actual code)
- Navigation (PHYS-02): HIGH -- com.unity.ai.navigation 2.0.9 already installed in project
- Bone sockets (EQUIP-02): MEDIUM -- standard pattern verified from docs but exact HumanBodyBones mapping needs runtime validation
- Variant matrix scale: MEDIUM -- pattern is sound but performance at 50+ variants untested

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable APIs, Unity 6 LTS)
