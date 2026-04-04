# Phase 47: Unity Integration & Regression - Research

**Researched:** 2026-04-04
**Domain:** Unity Editor TCP bridge, MCP tool integration testing, regression verification
**Confidence:** HIGH

## Summary

Phase 47 addresses three distinct concerns: (1) expanding the Unity Editor TCP bridge from 10 real-time commands to 26+ by adding 16 missing handlers for GameObject CRUD, component read/write, scene queries, and utility operations; (2) verifying all 37 MCP tools (16 Blender + 22 Unity, ~350 actions) function correctly through live integration testing; and (3) confirming that v8.0 fixes (camera, checkpoints, pipeline, materials, architecture, interiors, animation, export) remain intact after subsequent v9.0/v10.0 changes.

The codebase already has a mature, proven bridge architecture: the Blender addon runs a TCP server on port 9876 with a `COMMAND_HANDLERS` dict mapping command strings to handler functions, and the Unity bridge mirrors this exactly on port 9877 via `VBBridgeServer.cs` (TcpListener + ConcurrentQueue + EditorApplication.update) and `VBBridgeCommands.cs` (HANDLERS dict + Dispatch method). Both are generated from Python template functions in `qa_templates.py`. The Python client (`UnityConnection` in `shared/unity_client.py`) uses the same 4-byte big-endian length-prefixed JSON protocol as the Blender client. This means adding new bridge handlers is well-understood: add a C# handler method to the generated `VBBridgeCommands.cs` template, register it in the HANDLERS dict, then call it from a new or existing MCP tool via `_try_bridge()` or `conn.send_command()`.

**Primary recommendation:** Add 16 new handlers to the `generate_bridge_commands_script()` function in `qa_templates.py`, create a new `unity_gameobject` compound MCP tool for real-time operations, write comprehensive tests, then run the full 37-tool verification matrix.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BRIDGE-01 | Add 16 missing Unity bridge handlers for real-time GameObject/component/scene ops | Architecture Patterns section: all 16 handlers mapped with C# implementation patterns, template generation approach documented |
| BRIDGE-02 | Live Blender integration testing -- verify all 37 MCP tools function correctly | Tool Verification Matrix section: 16 Blender + 22 Unity tools catalogued, test approach for each documented |
| BRIDGE-03 | Verify v8.0 fixes still working (camera, checkpoints, pipeline, materials, architecture, interiors, animation, export) | v8.0 Regression Checklist section: all 10 fix categories with specific test assertions |
| TEST-02 | New tests for all fixed generators and wired systems | Validation Architecture section: test map for all new bridge handlers and regression checks |
| TEST-04 | Opus verification scan after every phase | Standard workflow: scan-fix-rescan until clean |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastMCP | (project dependency) | MCP server framework for Python tool hosting | Already used for both vb-blender and vb-unity servers |
| Pydantic | (project dependency) | UnityCommand/UnityResponse model serialization | Already used for all bridge protocol models |
| pytest | (project dependency) | Test framework for 19,920+ existing tests | Project standard, all tests use pytest |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| UnityConnection (shared.unity_client) | internal | TCP client for Unity bridge on port 9877 | Every real-time bridge call |
| qa_templates.py | internal | C# template generation for VBBridgeServer/Commands | Adding new bridge handlers |
| editor.py `_try_bridge()` | internal | Bridge-with-fallback pattern | New MCP tool handlers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TCP bridge handlers | Generated C# scripts (current fallback) | Scripts require recompile+execute cycle; bridge handlers execute instantly |
| New `unity_gameobject` tool | Adding to `unity_editor` | Editor tool already has 9 actions; new tool provides clean namespace |

## Architecture Patterns

### Current Bridge Architecture
```
Python MCP Server (port varies)
    |
    v
UnityConnection (shared/unity_client.py) --- TCP port 9877 --->  VBBridgeServer.cs (Unity Editor)
    |                                                                    |
    v                                                                    v
unity_tools/*.py                                              VBBridgeCommands.cs
(22 compound MCP tools)                                       HANDLERS dict -> HandleXxx() methods
```

### Existing 10 Bridge Commands (VBBridgeCommands.cs)
```
ping, recompile, execute_menu_item, enter_play_mode,
exit_play_mode, screenshot, console_logs, read_result,
get_game_objects, check_compile_status
```

### 16 New Bridge Handlers (BRIDGE-01)

**Priority 1 -- GameObject CRUD (7 handlers):**
| Handler | C# API | Parameters |
|---------|--------|------------|
| `create_gameobject` | `new GameObject(name)` + optional primitive mesh | name, primitive_type?, parent_path?, position?, rotation?, scale? |
| `delete_gameobject` | `DestroyImmediate(go)` | path (hierarchy path) or instance_id |
| `duplicate_gameobject` | `Instantiate(go)` | path or instance_id |
| `reparent_gameobject` | `go.transform.SetParent(parent)` | path, new_parent_path (null = root) |
| `set_transform` | `go.transform.position/rotation/localScale` | path, position?, rotation?, scale?, local? |
| `update_gameobject` | `go.name/tag/layer/SetActive` | path, name?, tag?, layer?, active? |
| `find_gameobjects` | `FindObjectsByType` + filter | name_contains?, tag?, layer?, component_type?, include_inactive? |

**Priority 2 -- Component Operations (3 handlers):**
| Handler | C# API | Parameters |
|---------|--------|------------|
| `get_components` | `go.GetComponents<Component>()` + reflection | path, component_type? |
| `add_component` | `go.AddComponent(Type.GetType(typeName))` | path, component_type |
| `remove_component` | `DestroyImmediate(component)` | path, component_type, index? |

**Priority 3 -- Scene Queries (3 handlers):**
| Handler | C# API | Parameters |
|---------|--------|------------|
| `get_hierarchy` | recursive traverse from scene roots | max_depth?, include_components? |
| `get_scene_info` | `SceneManager.GetActiveScene()` properties | (none) |
| `save_scene` | `EditorSceneManager.SaveScene()` | path? |

**Priority 4 -- Utility (3 handlers):**
| Handler | C# API | Parameters |
|---------|--------|------------|
| `undo` | `Undo.PerformUndo()` | (none) |
| `redo` | `Undo.PerformRedo()` | (none) |
| `instantiate_prefab` | `PrefabUtility.InstantiatePrefab()` | prefab_path, parent_path?, position?, rotation? |

### Implementation Pattern: Adding a Bridge Handler

All handlers follow the same pattern in `generate_bridge_commands_script()` (`qa_templates.py`):

```python
# In the HANDLERS dict initialization (line ~318):
'        ["create_gameobject"] = HandleCreateGameObject,',

# Handler method:
"    static Dictionary<string, object> HandleCreateGameObject(Dictionary<string, object> p)",
"    {",
"        string name = p.ContainsKey(\"name\") ? p[\"name\"].ToString() : \"GameObject\";",
"        var go = new GameObject(name);",
"        Undo.RegisterCreatedObjectUndo(go, \"Create \" + name);",
"        // ... set transform, parent, etc.",
"        return new Dictionary<string, object> { [\"instance_id\"] = go.GetInstanceID(), [\"name\"] = go.name };",
"    }",
```

### Implementation Pattern: New MCP Compound Tool

Create `unity_tools/gameobject.py` following existing patterns:

```python
@mcp.tool()
async def unity_gameobject(
    action: Literal[
        "create", "delete", "duplicate", "reparent",
        "set_transform", "update", "find",
        "get_components", "add_component", "remove_component",
        "get_hierarchy", "get_scene_info", "save_scene",
        "undo", "redo", "instantiate_prefab",
    ],
    # ... params ...
) -> str:
    # Try bridge first, no script fallback needed for these
    result = await _try_bridge(f"cmd_name", params)
    if result is None:
        return json.dumps({"status": "error", "message": "VBBridge not connected"})
    return json.dumps({"status": "success", **result})
```

### Anti-Patterns to Avoid
- **Script fallback for CRUD ops:** Unlike editor actions (recompile, screenshot), GameObject CRUD should NOT fall back to script generation. These are real-time operations that lose all value if they require a recompile cycle. Return a clear error if bridge is unavailable.
- **Missing Undo registration:** Every handler that mutates the scene MUST call `Undo.RegisterCreatedObjectUndo()` or `Undo.RecordObject()`. Without this, Ctrl+Z breaks and users lose work.
- **Blocking the main thread:** Heavy operations (hierarchy traversal of 10K+ objects) must be careful about frame time. Add depth limits and object count caps.
- **Hardcoded paths:** Use `Transform.Find()` relative to scene roots or `FindObjectsByType`, never hardcoded hierarchy assumptions.

### Recommended Project Structure for New Files
```
Tools/mcp-toolkit/
  src/veilbreakers_mcp/
    unity_tools/
      gameobject.py           # NEW: unity_gameobject compound tool (16 actions)
    shared/
      unity_templates/
        qa_templates.py        # MODIFIED: add 16 handlers to generate_bridge_commands_script()
  tests/
    test_unity_gameobject.py   # NEW: tests for all 16 bridge handlers
    test_bridge_regression.py  # NEW: v8.0 regression tests
    test_mcp_tool_matrix.py    # NEW: 37-tool import/action verification
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON serialization in C# | Custom serializer | MiniJSON already embedded in VBBridgeCommands.cs | Handles Dictionary<string, object> which JsonUtility cannot |
| TCP protocol | New protocol | Existing 4-byte length-prefixed JSON (shared with Blender) | Proven, tested, handles edge cases |
| Bridge lifecycle | Manual Start/Stop | Existing `[InitializeOnLoad]` + `AssemblyReloadEvents` pattern | Handles domain reload, editor restart, assembly reload |
| Component reflection | Per-type handlers | Generic C# reflection (`GetType`, `GetFields`, `GetProperties`) | Handles any Unity component without enumerating types |
| Hierarchy traversal | Recursive string building | `SerializeGameObject()` already exists in VBBridgeCommands | Reuse and extend the existing recursive serializer |

## Common Pitfalls

### Pitfall 1: Unity Thread Safety
**What goes wrong:** Bridge handlers execute on the main thread via EditorApplication.update, but heavy operations (find all objects, serialize full hierarchy) can stutter the editor.
**Why it happens:** VBBridgeServer queues commands and processes them one per update tick on the main thread.
**How to avoid:** Add object count limits (max 1000 results from find), depth limits on hierarchy traversal (max 10 levels), and truncate large string fields.
**Warning signs:** Editor freezes or slow response when bridge command is sent.

### Pitfall 2: Assembly Reload Kills Bridge State
**What goes wrong:** Adding new C# handlers triggers a domain reload, which destroys the bridge server state.
**Why it happens:** Unity's assembly reload destroys all static state. The `[InitializeOnLoad]` static constructor re-runs, but any queued commands are lost.
**How to avoid:** The existing pattern already handles this via `AssemblyReloadEvents.beforeAssemblyReload += Stop` and auto-restart in static constructor. Just don't add persistent state to handlers.
**Warning signs:** Bridge connection drops during recompile, recovers after.

### Pitfall 3: Undo Stack Corruption
**What goes wrong:** Operations that skip `Undo.RegisterCreatedObjectUndo()` or `Undo.RecordObject()` create scene state that cannot be undone, potentially corrupting the undo stack.
**Why it happens:** Forgetting to register with Unity's Undo system before modifying objects.
**How to avoid:** EVERY handler that creates or modifies GameObjects/Components MUST register with Undo first.
**Warning signs:** Ctrl+Z doesn't revert a bridge operation.

### Pitfall 4: Type.GetType Fails for Unity Types
**What goes wrong:** `Type.GetType("Rigidbody")` returns null because Unity types need assembly-qualified names.
**Why it happens:** C# `Type.GetType()` only searches `mscorlib` and the calling assembly by default.
**How to avoid:** Search all loaded assemblies: `AppDomain.CurrentDomain.GetAssemblies().SelectMany(a => a.GetTypes()).FirstOrDefault(t => t.Name == typeName)`.
**Warning signs:** `add_component` fails with "type not found" for standard Unity components.

### Pitfall 5: Test Isolation Without Live Unity
**What goes wrong:** Tests try to connect to Unity bridge and fail because Unity isn't running.
**Why it happens:** Test code imports bridge client without mocking the connection.
**How to avoid:** All bridge tests must mock `UnityConnection.send_command()`. Template tests verify C# string output only, not execution. Follow existing pattern in `test_unity_client.py` and `test_functional_unity_tools.py`.
**Warning signs:** Tests pass locally with Unity open, fail in CI.

## v8.0 Regression Checklist (BRIDGE-03)

The following v8.0 fixes must be verified as still working:

| Category | v8.0 Fix | Test Assertion |
|----------|----------|----------------|
| **Camera** | auto-frame screenshots, interior/ortho/preview modes, dark fantasy lighting | `handle_auto_frame_camera` returns valid camera params; `handle_interior_camera_shot` generates correct code |
| **Checkpoints** | Atomic writes via temp+rename, interior_results guard | `interior_results = []` inside checkpoint guard, `os.replace()` used for atomic writes |
| **Pipeline** | terrain flatten params, material_ids, LOD pipeline, _LOC_HANDLERS | `_LOC_HANDLERS["settlement"]` routes to `world_generate_settlement` (not `world_generate_town`), `mesh_from_spec` creates material slots |
| **Materials** | All metallic values binary (0.0 or 1.0), 7 new MATERIAL_LIBRARY entries, dark fantasy palette | MATERIAL_LIBRARY has expected entries, metallic values are 0.0 or 1.0 |
| **Architecture** | Rafters angled, timber 4 sides, flying buttress, foundations, flatten_terrain_zone | Building quality functions produce expected geometry metrics |
| **Interiors** | 180-degree rotation bug fixed (R = atan2(px-tx, py-ty)) | Furniture rotation formula correct in placement code |
| **Animation** | Bone existence filter, bird/floating/insect anims | Animation handlers check `hasattr` / bone existence before assignment |
| **Export** | Roughness-to-smoothness inversion, LODGroup, collision meshes | Export template generates `1.0f - roughness` conversion, `_COL` prefix handling |

## Tool Verification Matrix (BRIDGE-02)

### Blender Tools (16 total, TCP port 9876)
| Tool | Actions | Test Approach |
|------|---------|---------------|
| blender_object | create/modify/delete/duplicate | Verify handler imports, parameter validation |
| blender_mesh | analyze/repair/game_check/sculpt/boolean/retopo | Verify handler registration in COMMAND_HANDLERS |
| blender_uv | unwrap/pack/lightmap/equalize | Template output validation |
| blender_texture | create_pbr/bake/validate/wear | Template generation tests |
| blender_material | create/assign/modify/list | Handler function signatures |
| blender_rig | apply_template/auto_weight/validate | Template correctness |
| blender_animation | generate_walk/attack/idle/batch_export | Handler import verification |
| blender_quality | 32 AAA generators | Generator function existence + signature |
| blender_worldbuilding | dungeons/caves/towns/castles/ruins | Handler routing correctness |
| blender_environment | terrain/rivers/roads/water/scatter | Handler registration |
| blender_viewport | screenshot/contact_sheet | Handler correctness |
| blender_export | fbx/gltf | Export function signatures |
| blender_execute | execute_code | Direct code execution handler |
| blender_scene | get_scene_info/clear/configure/list_objects | Scene handler tests |
| asset_pipeline | compose_map/compose_interior/generate_3d | Pipeline routing tests |
| concept_art | generate/extract_palette/silhouette_test | Template generation |

### Unity Tools (22 total, script generation + TCP bridge)
| Tool | Key Actions | Test Approach |
|------|-------------|---------------|
| unity_editor | recompile/screenshot/console_logs/load_scene | Bridge + fallback script tests |
| unity_vfx | 19 brand VFX + shader actions | Template C# output validation |
| unity_audio | 20 audio actions | Template generation tests |
| unity_ui | 14 UI actions | UXML/USS template validation |
| unity_scene | terrain/lighting/animators | C# template correctness |
| unity_gameplay | mob/spawn/behavior_tree | Template output tests |
| unity_game | save/health/abilities/synergy | Template validation |
| unity_content | inventory/dialogue/quests/loot | Template generation |
| unity_world | scenes/weather/day_night/WFC | Template correctness |
| unity_camera | Cinemachine/shake/cutscenes | Template validation |
| unity_code | generate_class/state_machine | Code generation tests |
| unity_shader | HLSL/renderer features | Shader template tests |
| unity_qa | bridge/tests/profiling/code_review | Bridge setup + template tests |
| unity_prefab | create/variants/batch | Template validation |
| unity_performance | profile/LOD/lightmap | Template generation |
| unity_assets | import/configure/audit | Template tests |
| unity_data | data layer templates | Template validation |
| unity_settings | project/packages/physics | Template tests |
| unity_build | platform/addressables/CI | Template validation |
| unity_quality | aaa_audit/consistency | Template tests |
| unity_pipeline | orchestration/steps | Template validation |
| unity_ux | UX patterns | Template tests |

## Code Examples

### Adding a Handler to VBBridgeCommands.cs Template

Source: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/qa_templates.py`

```python
# Inside generate_bridge_commands_script(), add to HANDLERS dict:
'        ["create_gameobject"] = HandleCreateGameObject,',

# Add handler method after existing handlers:
"    static Dictionary<string, object> HandleCreateGameObject(Dictionary<string, object> p)",
"    {",
"        string name = p.ContainsKey(\"name\") ? p[\"name\"].ToString() : \"New GameObject\";",
"        string primitiveType = p.ContainsKey(\"primitive_type\") ? p[\"primitive_type\"].ToString() : \"\";",
"        var go = string.IsNullOrEmpty(primitiveType)",
"            ? new GameObject(name)",
"            : GameObject.CreatePrimitive((PrimitiveType)Enum.Parse(typeof(PrimitiveType), primitiveType));",
"        if (!string.IsNullOrEmpty(primitiveType)) go.name = name;",
"        Undo.RegisterCreatedObjectUndo(go, \"Create \" + name);",
"        // Set transform from params...",
"        return new Dictionary<string, object> {",
"            [\"instance_id\"] = go.GetInstanceID(),",
"            [\"name\"] = go.name,",
"            [\"path\"] = GetHierarchyPath(go.transform)",
"        };",
"    }",
```

### New MCP Tool Pattern (unity_gameobject.py)

Source: Follows pattern of `unity_tools/editor.py`

```python
from veilbreakers_mcp.unity_tools._common import mcp, logger
from veilbreakers_mcp.unity_tools.editor import _try_bridge

@mcp.tool()
async def unity_gameobject(
    action: Literal[
        "create", "delete", "duplicate", "reparent",
        "set_transform", "update", "find",
        "get_components", "add_component", "remove_component",
        "get_hierarchy", "get_scene_info", "save_scene",
        "undo", "redo", "instantiate_prefab",
    ],
    name: str = "",
    path: str = "",
    # ... other params
) -> str:
    """Real-time Unity GameObject/component operations via VBBridge TCP."""
    if action == "create":
        result = await _try_bridge("create_gameobject", {
            "name": name or "New GameObject",
            "primitive_type": primitive_type,
            "parent_path": parent_path,
            "position": position,
            "rotation": rotation,
            "scale": scale,
        })
        if result is None:
            return json.dumps({
                "status": "error",
                "message": "VBBridge not connected. Start Unity and run unity_qa action=setup_bridge first.",
            })
        return json.dumps({"status": "success", "action": "create", **result})
```

### Test Pattern for Bridge Handlers

Source: Follows `test_functional_unity_tools.py` and `test_unity_client.py` patterns

```python
class TestBridgeCommandsTemplate:
    """Verify generated C# contains all 26 handlers."""

    def test_all_handlers_registered(self):
        from veilbreakers_mcp.shared.unity_templates.qa_templates import (
            generate_bridge_commands_script,
        )
        cs = generate_bridge_commands_script()
        # Original 10
        for cmd in ["ping", "recompile", "execute_menu_item", "enter_play_mode",
                     "exit_play_mode", "screenshot", "console_logs", "read_result",
                     "get_game_objects", "check_compile_status"]:
            assert f'["{cmd}"]' in cs, f"Missing handler: {cmd}"
        # New 16
        for cmd in ["create_gameobject", "delete_gameobject", "duplicate_gameobject",
                     "reparent_gameobject", "set_transform", "update_gameobject",
                     "find_gameobjects", "get_components", "add_component",
                     "remove_component", "get_hierarchy", "get_scene_info",
                     "save_scene", "undo", "redo", "instantiate_prefab"]:
            assert f'["{cmd}"]' in cs, f"Missing new handler: {cmd}"

    def test_undo_registration_present(self):
        cs = generate_bridge_commands_script()
        assert "Undo.RegisterCreatedObjectUndo" in cs
        assert "Undo.RecordObject" in cs
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Script generation for everything | TCP bridge for editor ops, scripts for complex generation | v4.0 (Phase 16) | Instant editor control without recompile |
| 10 bridge commands | 26+ bridge commands (after this phase) | Phase 47 | Full real-time CRUD parity with community packages |
| Manual Unity testing | Auto-recompile + screenshot + console_logs | v4.0 (Phase 7) | Claude can test without human clicking |

**Community comparison:**
- CoderGamester/mcp-unity (5,800+ stars): All operations real-time
- CoplayDev/unity-mcp (147+ tools): Full component read/write
- VeilBreakers: 350+ game dev actions BUT only 10 real-time. This phase closes the gap.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (latest) |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_unity_gameobject.py tests/test_bridge_regression.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRIDGE-01 | 16 new bridge handlers generate correct C# | unit | `pytest tests/test_unity_gameobject.py -x` | Wave 0 |
| BRIDGE-01 | New unity_gameobject MCP tool imports and has all 16 actions | unit | `pytest tests/test_unity_gameobject.py::TestUnityGameObjectTool -x` | Wave 0 |
| BRIDGE-02 | All 37 MCP tools importable with correct action counts | unit | `pytest tests/test_mcp_tool_matrix.py -x` | Wave 0 |
| BRIDGE-02 | All Blender handlers registered in COMMAND_HANDLERS | unit | `pytest tests/test_mcp_tool_matrix.py::TestBlenderToolMatrix -x` | Wave 0 |
| BRIDGE-03 | v8.0 camera/checkpoint/pipeline/material/architecture/interior/animation/export fixes intact | unit | `pytest tests/test_bridge_regression.py -x` | Wave 0 |
| TEST-02 | New tests cover all new handlers and regression checks | unit | `pytest tests/test_unity_gameobject.py tests/test_bridge_regression.py tests/test_mcp_tool_matrix.py --co -q` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_unity_gameobject.py tests/test_bridge_regression.py tests/test_mcp_tool_matrix.py -x`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x`
- **Phase gate:** Full suite green (19,920+ tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_unity_gameobject.py` -- covers BRIDGE-01 (16 handlers + MCP tool)
- [ ] `tests/test_bridge_regression.py` -- covers BRIDGE-03 (v8.0 fix verification)
- [ ] `tests/test_mcp_tool_matrix.py` -- covers BRIDGE-02 (37-tool verification)

## Open Questions

1. **`_try_bridge` import sharing**
   - What we know: `_try_bridge` is defined in `editor.py` as a module-level function
   - What's unclear: Whether to import it from editor.py into gameobject.py, or extract to _common.py
   - Recommendation: Move `_try_bridge` to `_common.py` so all tools can use it cleanly. It's already a shared utility pattern.

2. **Component field serialization depth**
   - What we know: `get_components` needs to serialize component field values via C# reflection
   - What's unclear: How deep to serialize (nested objects? references? arrays of components?)
   - Recommendation: Serialize one level deep. For object references, return instanceId + name. For arrays, serialize up to 100 elements. Mark truncation.

3. **Existing `get_game_objects` vs new `get_hierarchy`**
   - What we know: `get_game_objects` already exists and serializes root GameObjects recursively
   - What's unclear: Whether to enhance existing or add separate handler
   - Recommendation: Keep existing `get_game_objects` for backwards compatibility. New `get_hierarchy` adds depth limit, component inclusion toggle, and instance IDs.

## Project Constraints (from CLAUDE.md)

- **Unity two-step workflow:** Tool writes script, then recompile + execute. New bridge handlers bypass this for real-time ops.
- **Always verify visually:** Use `blender_viewport action=contact_sheet` for Blender; `unity_editor action=screenshot` for Unity.
- **Pipeline order:** repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- **Game readiness:** Run `blender_mesh action=game_check` before export. Run `unity_performance action=profile_scene` after setup.
- **Batch when possible:** Use batch processing actions where available.
- **Tool documentation:** Provided via MCP server system-reminder -- do not duplicate in generated scripts.
- **Bug scan rounds:** Run follow-up rounds until CLEAN -- never stop after one round if bugs found.
- **No security sandbox tightening:** BLOCKED_FUNCTIONS stays minimal.

## Sources

### Primary (HIGH confidence)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/qa_templates.py` -- VBBridgeServer + VBBridgeCommands C# templates, current 10 handlers
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_client.py` -- UnityConnection TCP client, protocol details
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/editor.py` -- `_try_bridge()` pattern, existing bridge usage
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/_common.py` -- `_bridge_recompile_and_execute()`, `_write_to_unity()`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/__init__.py` -- 22 Unity tool modules registered
- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py` -- Blender COMMAND_HANDLERS (100+ handlers, reference implementation)
- `Tools/mcp-toolkit/blender_addon/handlers/objects.py` -- Blender object CRUD pattern (reference for Unity CRUD)
- `Tools/mcp-toolkit/tests/test_unity_client.py` -- Existing Unity client tests (model + connection)
- `Tools/mcp-toolkit/tests/test_functional_unity_tools.py` -- Existing functional tests (282 tests)

### Secondary (MEDIUM confidence)
- `.planning/V9_MASTER_FINDINGS.md` Section 19.3 -- Integration gap analysis identifying 16 missing handlers
- `.claude/.../memory/project_unity_bridge_gaps.md` -- Gap analysis vs CoderGamester/mcp-unity and CoplayDev/unity-mcp
- `.claude/.../memory/project_v8_execution_complete.md` -- v8.0 fix list for regression testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already in project, no new packages needed
- Architecture: HIGH -- proven bridge pattern exists, just adding handlers to established template
- Pitfalls: HIGH -- derived from actual codebase analysis (thread safety, undo, assembly reload all observed in existing code)
- v8.0 regression: MEDIUM -- fix list documented in memory but some specifics need verification against current code

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- internal architecture unlikely to change)
