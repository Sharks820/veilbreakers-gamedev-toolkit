# Phase 9: Unity Editor Deep Control - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Programmatic control over Unity Editor operations: prefab creation/variants/nesting, component add/remove/configure, hierarchy manipulation, physics layers/materials/joints, project settings (Player/Build/Quality/Time/Graphics), package management (Unity/OpenUPM/git), import configuration (FBX ModelImporter, TextureImporter, material remapping), asset operations (move/rename/delete with GUID preservation), Assembly Definition management, and Unity Presets.

Requirements: EDIT-01 through EDIT-15, IMP-01, IMP-02, PHYS-01, PHYS-02, PIPE-09, EQUIP-02.

</domain>

<decisions>
## Implementation Decisions

### Prefab & Hierarchy Operations
- **Full auto-wire via versioned profiles**: When creating prefabs, toolkit auto-adds components based on prefab type (hero, monster, prop, UI) matching VeilBreakers component patterns (e.g. monster prefab gets Combatant, NavMeshAgent, CapsuleCollider, Animator). Auto-wire rules stored as versioned JSON profiles (not hardcoded) so game architecture can evolve without toolkit rewrites
- **Ghost prefab scaffolding**: Since no 3D models exist yet, support creating "scaffold" prefabs with correct components + placeholder visuals (transparent capsule with brand icon) for gameplay testing before Blender pipeline finishes
- **Deterministic selector schema**: Primary lookup by name, fallback to full hierarchy path, with GUID-based and regex/query selectors for disambiguation. Must handle duplicated names, nested prefabs, and variant chains safely
- **Scene vs Prefab Mode context**: Explicit "target context" parameter — modifying a specific scene instance vs editing the master prefab asset uses different PrefabUtility API calls
- **Prefab variants are first-class**: Support base prefab + variants with overrides. Critical for corruption tiers (5 levels) and brand variants (10 brands) — one base monster, many visual/stat variants
- **Variant-matrix generator**: Generate corruption tier 1-5 × brand 1-10 × archetype variants from a single base prefab/profile automatically
- **Full nested prefab support**: Rooms contain furniture prefabs, buildings contain rooms, towns contain buildings. No depth limits but with override chain guardrails

### Component Configuration
- **Custom + built-in components**: Configure any serialized field on any component using SerializedObject API — custom MonoBehaviours (Combatant, AudioConfig, HeroDisplayConfig), ScriptableObject references, and all Unity built-in components
- **Reflect component action**: `reflect_component` returns all serialized field names, types, and current values for a given script so Claude doesn't have to guess field names
- **Batch operations**: Apply component configurations to multiple objects at once using tag, layer, or name pattern matching (e.g. "add CapsuleCollider + Rigidbody + NavMeshAgent to all objects tagged Monster")
- **Full physics configuration**: Create PhysicsMaterials (friction, bounciness), assign to colliders, configure layer collision matrix for player/enemy/projectile/environment separation
- **All joint types supported**: HingeJoint, SpringJoint, ConfigurableJoint, CharacterJoint, FixedJoint — covers breakable props, ragdoll physics, chains, bridges, doors (PHYS-01)

### Import Pipeline
- **Type-based presets**: Define import presets per asset type (hero, monster, weapon, prop, environment) with correct scale, compression, animation type, normals. Auto-applies based on asset type matching AAA-02 poly budgets
- **Atomic import sequence**: Enforce correct order — 1. Textures → 2. Material creation → 3. FBX import → 4. Material remapping. Prevents pink/default materials from out-of-order imports
- **Auto-generate materials + remap option**: Auto-create PBR materials from imported textures by default. Option to remap to existing project materials when they exist. Handles both fresh Tripo3D imports and Blender exports
- **Import pipeline precedence**: Clear layering — asset-type presets → folder-level rules → .preset files → existing AssetPostprocessors → Unity defaults. Presets are one layer, not the whole solution
- **Platform-aware texture compression**: Auto-set compression format per platform (ASTC for mobile, DXT5 for PC) + max texture size by asset type (hero: 2048, monster: 1024, prop: 512, UI: 1024). Auto-detect sRGB/linear based on texture channel
- **Generate Unity Presets (.preset files)**: Create .preset files alongside import configuration so rules are visible and editable in Unity Inspector even without MCP (PIPE-09)

### Project Settings & Packages
- **Auto-sync tags/layers from code**: Read Constants.cs tag/layer definitions and ensure Unity TagManager matches. Prevents code-to-settings desync bugs
- **Multi-source package management**: Install from Unity registry, OpenUPM scoped registries, and git URLs. Handle manifest.json + scopedRegistries entries
- **Full Player Settings**: Company/product name, icon, splash, scripting backend (IL2CPP/Mono), API compatibility, color space, resolution defaults (EDIT-05)
- **Full Assembly Definition management**: Create .asmdef files, add/remove assembly references, set scripting defines, configure platform targets (EDIT-15)

### Execution & Safety Model
- **Undo protocol mandatory**: Every generated C# script must use `Undo.RegisterCreatedObjectUndo` / `Undo.RecordObject`. One bad command should never force a Git revert
- **Batch scripting**: Support generating one large C# "Job" script that performs multiple operations in one compilation cycle — avoids 10 recompile cycles (3-5s each) for 10 sequential actions
- **Dependency-aware asset operations**: Reference scanning before delete/move/rename. GUID preservation is necessary but not sufficient — warn on live dependencies, support safe-delete mode
- **Enhanced result JSON**: Every tool returns `changed_assets`, `warnings`, `conflicts`, `reimport_required`, `validation_status` in addition to existing `status`/`action` fields
- **Post-operation validation**: After mutations, verify prefab opens cleanly, required components present, import settings applied correctly. Machine-readable validation failures

### Project Validation
- **`validate_project_integrity` action**: Scan all prefabs and report missing components, broken script references, missing materials, tag/layer mismatches
- **Tag/layer drift detection**: Source-of-truth is Constants.cs — detect and warn when layers are edited manually in Unity or by packages

### Claude's Discretion
- NavMesh Areas and Off-Mesh Links configuration approach (PHYS-02)
- Bone socket attachment system implementation details (EQUIP-02)
- Quality Settings tier configuration (shadow distance, texture quality, AA, VSync, LOD bias)
- Build Settings scene list and platform switching approach
- Time settings (fixed timestep) and Graphics settings (render pipeline asset) configuration
- Tool structure: recommended 3 new tools (unity_hierarchy, unity_assets, unity_pipeline) but implementation may adjust based on action count balance

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### VeilBreakers Game Project (target project for this toolkit)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/Constants.cs` — Tag/layer definitions that must sync with TagManager
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/GameBootstrap.cs` — 13-phase singleton initialization sequence
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Combat/Combatant.cs` — Component that auto-wire should add to combat prefabs
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Editor/BlenderFBXImportPostprocessor.cs` — Existing FBX import configuration (extend, don't conflict)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Packages/manifest.json` — Current package state (Addressables, PrimeTween, Input System, etc.)

### Toolkit Implementation (existing patterns to follow)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Existing Unity tool architecture (compound pattern, handlers, _write_to_unity, _sanitize_cs_string)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/` — Template generator pattern for C# code generation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/config.py` — Settings including UNITY_PROJECT_PATH

### Requirements
- `.planning/REQUIREMENTS.md` — EDIT-01 through EDIT-15, IMP-01, IMP-02, PHYS-01, PHYS-02, PIPE-09, EQUIP-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_write_to_unity()`: Path-validated file writer for C# scripts — all Phase 9 handlers must use this
- `_sanitize_cs_string()`: String escaping for C# template injection prevention — mandatory for all user input
- `_sanitize_cs_identifier()`: Identifier sanitization for class/method/field names
- `_read_unity_result()`: Result JSON reader from Temp/vb_result.json

### Established Patterns
- **Compound tool pattern**: One tool name, `action` param selects operation, 5-10 actions per tool
- **Handler pattern**: `async def _handle_[action]()` dispatched from main tool function
- **Template pattern**: Separate `shared/unity_templates/[category]_templates.py` files generate complete C# source
- **MenuItem registration**: All editor scripts register `[MenuItem("VeilBreakers/[Category]/[Action]")]`
- **Result JSON**: Every script writes `{"status": "success/error", "action": "...", ...}` to `Temp/vb_result.json`
- **next_steps array**: All success responses include next_steps telling Claude what mcp-unity commands to run

### Integration Points
- Unity server has 7 existing tools (unity_editor, unity_vfx, unity_audio, unity_ui, unity_scene, unity_gameplay, unity_performance)
- Phase 9 should add 2-3 new compound tools (suggested: unity_hierarchy, unity_settings, unity_assets) or extend unity_editor
- Generated scripts go to `Assets/Editor/Generated/[Category]/`
- Runtime scripts (prefab behaviors) go to `Assets/Scripts/Runtime/`

### Game Project Structure
- Empty Prefabs/ directory (Characters/, Monsters/, UI/, VFX/ — all .gitkeep only) — #1 gap
- 128 C# scripts across 15 subsystems with established namespace conventions (VeilBreakers.[Category])
- 4 Assembly Definitions: VeilBreakers.Runtime, VeilBreakers.Editor, VeilBreakers.Tests.PlayMode, VeilBreakers.Tests.EditMode
- Unity 6000.3.6f1, URP 17.3.0, UI Toolkit (no legacy UGUI)
- No 3D character models in engine yet — placeholder capsules for heroes

</code_context>

<specifics>
## Specific Ideas

- Auto-wire should match VeilBreakers component architecture: monsters get Combatant + NavMeshAgent + CapsuleCollider + Animator; heroes get the same plus additional controllers
- Tag/layer sync from Constants.cs is specifically to prevent the bug where code references tags that Unity's TagManager doesn't know about
- Prefab variants are critical for the corruption system (5 tiers with increasing visual corruption) and brand system (10 combat brands with distinct visual identity)
- The game's BlenderFBXImportPostprocessor already handles some import settings — toolkit should extend this, not conflict with it
- PrimeTween is installed via OpenUPM scoped registry — package management must handle scopedRegistries in manifest.json, not just standard packages
- Ghost scaffolding is critical since the game has NO models yet — gameplay testing needs prefabs with correct scripts even without art
- Batch scripting to avoid recompile loops — Gemini flagged 10 sequential actions = 30-50s of waiting
- Variant-matrix generator enables systematic content creation: 60+ monsters × 5 corruption tiers × visual variants from minimal base prefabs

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-unity-editor-deep-control*
*Context gathered: 2026-03-20*
