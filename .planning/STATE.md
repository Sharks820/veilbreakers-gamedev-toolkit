---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Complete Unity Game Development Coverage
status: executing
stopped_at: Completed 13-02-PLAN.md
last_updated: "2026-03-20T15:43:29Z"
last_activity: 2026-03-20 -- Completed 13-02-PLAN.md (equipment handlers + 105 tests, 4098 total)
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 16
  completed_plans: 16
---

# Project State: VeilBreakers GameDev Toolkit

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Every tool returns structured validation data and visual proof so Claude never works blind
**Current focus:** v2.0 Phase 13 in progress

## Current Position

Phase: 13 of 17 (Content & Progression Systems)
Plan: 2 of N in current phase (13-01, 13-02 complete)
Status: Executing Phase 13
Last activity: 2026-03-20 -- Completed 13-02-PLAN.md (equipment handlers + 105 tests, 4098 total)

```
Phase Progress: [████████████████████████████████████░░░░] 76% overall (13/17 phases in progress)
v2.0 Progress:  [████████████████] 16/16 plans complete
```

## Performance Metrics

| Metric | Value |
|--------|-------|
| v1.0 phases complete | 8/8 |
| v1.0 tests passing | 2,740 |
| v1.0 MCP tools | 22 (15 Blender + 7 Unity) |
| v1.0 handlers | 86 Blender handlers |
| v1.0 bugs fixed | 55 total across 4 scan rounds |
| v2.0 requirements | 76 across 11 categories |
| v2.0 phases planned | 9 (phases 9-17) |
| v2.0 plans completed | 16 (09-01, 09-02, 09-03, 10-01, 10-02, 10-03, 10-04, 11-01, 11-02, 11-03, 11-04, 12-01, 12-02, 12-03, 13-01, 13-02) |
| v2.0 tests added | 1,516 (118 prefab + 78 settings + 96 assets + 49 code-gen + 43 shader-v2 + 47 test+arch + 260 tool-wiring + 72 pipeline + 64 quality + 105 tool-wiring-p11 + 93 core-game + 87 vb-combat + 98 tool-wiring-p12 + 105 equipment + 201 content) |
| v2.0 total tests passing | 4,299 |
| v2.0 MCP tools | 31 (15 Blender + 16 Unity) |
| 09-01 duration | 16 min |
| 09-02 duration | 13 min |
| 09-03 duration | 11 min |
| 10-01 duration | 7 min |
| 10-02 duration | 9 min |
| 10-03 duration | 9 min |
| 10-04 duration | 18 min |
| 11-02 duration | 8 min |
| 11-03 duration | 15 min |
| 11-04 duration | 12 min |
| 12-01 duration | 13 min |
| 12-02 duration | 11 min |
| 12-03 duration | 11 min |
| 13-01 duration | 17 min |
| 13-02 duration | 11 min |

## Accumulated Context

### Key Decisions (from v1.0+)
| Decision | Rationale | Phase |
|----------|-----------|-------|
| C# template code generation (not live RPC) | VFX/Shader/AudioMixer have no creation APIs | 7 |
| _sanitize_cs_string for all user input | Prevents code injection in C# templates | 7 |
| Path traversal protection in _write_to_unity | resolve() + startswith() check | 7 |
| Local _sanitize copies per template module | Avoids circular imports, consistent with existing pattern | 9 |
| OpenUPM installs edit manifest.json directly | Client.Add only handles standard UPM, not scoped registries | 9 |
| Tag/layer sync with bidirectional drift detection | Catches both missing-in-TagManager and missing-in-Constants.cs | 9 |
| Selector helper as reusable C# snippet generator | All component/hierarchy/joint/navmesh operations use selector pattern | 9 |
| Auto-wire profiles as external JSON files | Easy extension without code changes | 9 |
| Job script batches with StartAssetEditing + atomic Undo | Efficient multi-op single compile cycle | 9 |
| Asset-type presets as dicts for FBX/texture import | Easy defaults per asset category (hero/monster/weapon/prop/env) | 9 |
| Asmdef generation returns JSON not C# | .asmdef files are plain JSON, no editor script needed | 9 |
| Safe delete scans dependencies before deletion | Prevents broken references from careless asset removal | 9 |
| Atomic import enforces textures->materials->FBX->remap order | Prevents pink materials from out-of-order imports | 9 |
| IMGUI (OnGUI) default for EditorWindow generation | Matches existing VeilBreakers editor tools, simpler template gen | 10 |
| Private fields auto-prefixed with underscore | VeilBreakers _camelCase convention enforced in code gen | 10 |
| Reserved word identifiers get @ prefix | More permissive than rejection, valid C# syntax | 10 |
| ScriptableObject auto-adds CreateAssetMenu | Consistent with Unity best practices for SO assets | 10 |
| Renderer feature uses RenderGraph API (RecordRenderGraph) not legacy Execute() | URP 17 / Unity 6 modern API, Execute() is obsolete | 10 |
| Property-to-HLSL type mapping centralised in helper | Consistent CBUFFER generation across all shader configs | 10 |
| SO event channels use VeilBreakers.Events.Channels namespace | Distinct from existing VeilBreakers.Core.EventBus to prevent collisions | 10 |
| TestRunnerApi with runSynchronously, not CLI batch mode | Maintains two-step editor script pattern for MCP integration | 10 |
| Architecture patterns in VeilBreakers.Patterns namespace | Consistent namespace for service locator, object pool, state machine | 10 |
| unity_code consolidates 12 code-gen actions in single compound tool | Matches established compound pattern (unity_vfx, unity_audio, etc.) | 10 |
| modify_script creates .cs.bak backup before modification | Safety rollback for non-destructive script editing | 10 |
| SpriteAtlas V1 API (.spriteatlas) for programmatic creation | V2 has native crash issues; V1 API is stable and well-documented | 11 |
| Normal map bake generates Blender Python not C# | Executed via blender_execute, must use only allowed imports (bpy, mathutils) | 11 |
| AssetPostprocessor uses OnPreprocess exclusively | OnPostprocess triggers infinite reimport loops; OnPreprocess is safe | 11 |
| .asset files excluded from Git LFS | Unity Force Text serialization stores .asset as YAML text | 11 |
| Setting maps use (property, formatter) tuples | Clean code generation from Python dicts to C# property assignments | 11 |
| Line-based string concatenation for C# templates | Avoids f-string/brace escaping issues in deeply nested C# code | 11 |
| URP Lit material properties not Shader Graph | Simpler template generation, matches research recommendation | 11 |
| ITU-R BT.601 luminance for de-lighting | Industry standard weights, consistent with Blender | 11 |
| ASSET_TYPE_BUDGETS as canonical budget source | Single source of truth for poly budgets across Python and C# | 11 |
| C# interpolation vars whitelisted in f-string leak detector | added/skipped/failed/sprites.Length are legitimate C# $"..." interpolation, not Python f-string leaks | 11 |
| VB delegation pattern: generated MonoBehaviours call existing static utility classes | Generated C# references BrandSystem/SynergySystem/CorruptionSystem by name, never reimplements | 12 |
| Actual VeilBreakers API signatures over plan interfaces | Plan had simplified signatures; actual source uses Path enum, 10 brands, nested SynergyTier | 12 |
| Extended damage types cover all 10 brands | BrandSystem has 10 brands (not 5 combat), damage type system matches full set | 12 |
| Cinemachine 3.x API exclusively (CinemachineCamera + OrbitalFollow + RotationComposer) | Legacy FreeLook is Cinemachine 2.x, new API is cleaner and Unity 6 native | 12 |
| Multi-file generators return tuples | Input config returns (JSON, C#), settings returns (C#, UXML, USS) for related artifacts | 12 |
| HTTP client uses UNITY_6000_0_OR_NEWER guard | Awaitable async for Unity 6, coroutine fallback for earlier versions | 12 |
| Save system key derivation from Application.identifier | AES-CBC key derived via SHA256(identifier + salt), matching SaveFileHandler pattern | 12 |
| ns_kwargs dict pattern for optional namespace passthrough | Only passes namespace when non-empty, letting generators use defaults | 12 |
| Extended f-string whitelist for HTTP client interpolation | 'method' and 'url' are legitimate C# $"" interpolation beyond 50-char lookback | 12 |
| Synchronous handler signatures for equipment handlers | Existing codebase uses def (not async def); plan corrected to match | 13 |
| Pure-logic validation/computation helpers for testability | Separated _validate_* and _compute_* from bpy-dependent code | 13 |
| Weapon generator dispatch table (_WEAPON_GENERATORS) | Clean extensibility for adding new weapon types | 13 |
| Convex hull for collision mesh approximation | bmesh.ops.convex_hull for simplified weapon collision shapes | 13 |
| Tuple return for multi-file content generators | (SO_cs, system_cs, uxml, uss) for UI-heavy systems, (SO_cs, system_cs) for code-only | 13 |
| VB_ItemData matches items.json schema exactly | ItemType 0-5, ItemRarity 0-4, stat_buffs, corruptionChange, pathChange | 13 |
| Brand loot affinity delegates, never reimplements | BrandSystem.GetEffectiveness with 1.5x weight boost on match | 13 |
| Quest reward distribution via typed EventBus events | OnXPGained/OnCurrencyGained/OnItemReward for cross-system rewards | 13 |
| Editor balancing tools use IMGUI OnGUI | Consistent with existing VeilBreakers editor window pattern | 13 |

### Architecture Notes
- v2.0 extends the existing unity_server.py with deeper Editor control
- v1.0 code generation pattern (write C# to disk, recompile) continues as foundation
- Phase 9 (EDIT) adds prefab/component/hierarchy manipulation beyond code gen
- Phase 10 (CODE) generalizes C# generation beyond domain-specific templates
- IMP-01/02 grouped with EDIT (asset operations are editor-level concerns)
- BUILD-06 (sprite atlasing) grouped with DATA (asset preparation, not build pipeline)

### Blockers
None currently.

## Session Continuity

Last session: 2026-03-20T15:49:29Z
Stopped at: Completed 13-01-PLAN.md (content templates + 201 tests, 4,299 total)
Next action: Continue Phase 13 (13-03 remaining)

---
*State initialized: 2026-03-18*
*Last updated: 2026-03-20 -- Completed 13-01-PLAN.md (content templates + 201 tests, 4,299 total)*
