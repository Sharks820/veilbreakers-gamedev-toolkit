# Phase 37: Pipeline Integration - Research

**Researched:** 2026-03-31
**Domain:** End-to-end map generation pipeline, state persistence, Unity Addressables, runtime occlusion
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MESH-16 | Clean commit workflow -- atomic commits after every bug/error scan, state tracked in STATE.md | Covered by Task 1: pipeline orchestration + state JSON persistence |
| PIPE-01 | AAA technique research documented: CGA grammars, WFC, L-systems, hydraulic erosion, Poisson disk, straight skeleton roofs, domain warping | Covered by Task 5: dedicated AAA technique research document |

</phase_requirements>

---

## Summary

Phase 37 wires every procedural system built in Phases 30-36 into a single callable pipeline. The goal is resumable map generation (state persisted to JSON between steps), Unity Addressables streaming group configuration per district, occlusion zone geometry at interior/exterior boundaries, and an exportable package format that Unity can load in one shot.

The existing `asset_pipeline action=compose_map` (blender_server.py lines 2412-2714) is a 9-step sequential pipeline covering terrain, water, roads, locations, biome paint, vegetation, props, and interiors. It already has error isolation per step (`steps_completed`/`steps_failed`) but writes no JSON checkpoint and cannot resume mid-run. The Unity side has `generate_addressables_config_script()` in `build_templates.py` that creates Blender-to-Unity Addressable groups, but it is not wired to map output -- groups are defined manually, not derived from compose_map location data.

**Primary recommendation:** Extend compose_map with a checkpoint/resume layer (JSON written to disk between steps), add a `generate_map_package` action that exports FBX + PBR + LOD + scene hierarchy JSON from completed Blender state, add a Unity-side `setup_map_streaming` action that reads the scene hierarchy JSON and auto-creates Addressable groups per district, and add occlusion portal geometry in the existing `world_generate_linked_interior` handler.

---

## Standard Stack

### Core (already in codebase, no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `json` | stdlib | State persistence (checkpoint files) | Zero dependency, Blender-safe |
| Python `pathlib` | stdlib | Cross-platform path management | Already used throughout codebase |
| `bpy.ops.export_scene.fbx` | Blender 4.x built-in | FBX export with Unity-optimised axis | Used in export.py already |
| `bpy.ops.export_scene.gltf` | Blender 4.x built-in | GLB export alternative | Used in export.py already |
| `UnityEditor.AddressableAssets` | via Unity Addressables package | Addressable group setup | Already in build_templates.py |
| `UnityEditor.StaticOcclusionCulling` | Unity 6 built-in | Bake static occlusion | Available in Unity 6 / URP 17.3 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `blender_addon.handlers.lod_pipeline` | existing | LOD chain generation per exported mesh | Needed before FBX export |
| `blender_addon.handlers.export` | existing | `handle_export_fbx`, `handle_export_gltf` | Used as export back-end |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON checkpoint file | SQLite / shelve | JSON simpler, human-readable, no extra deps, sufficient for single-map state |
| Static Unity occlusion bake | Umbra / custom portal renderer | Static bake is free, zero runtime cost; custom renderer adds runtime overhead without sufficient benefit at this stage |
| Per-district Addressable group | Single "Map" group | Per-district enables streaming by zone -- required by success criterion 2 |

---

## Architecture Patterns

### Recommended Project Structure

New files this phase touches:

```
blender_addon/handlers/
  pipeline_state.py        # checkpoint read/write, step registry, resume logic
blender_server.py          # new actions: generate_map_package, resume_map
unity_server.py            # new action: setup_map_streaming
shared/unity_templates/
  world_streaming_templates.py   # Addressable group generator per district, occlusion setup
tests/
  test_pipeline_state.py         # checkpoint persistence tests
  test_world_streaming_templates.py  # Addressable + occlusion template tests
```

### Pattern 1: Checkpoint / Resume

**What:** After each compose_map step completes, write a JSON file to a caller-specified `checkpoint_dir`. On a subsequent call with `resume=True`, load the checkpoint, skip already-completed steps, and continue from the first failed or missing step.

**When to use:** Any multi-step Blender operation that may fail mid-way due to Tripo timeouts, Blender crashes, or budget limits.

**Checkpoint schema:**
```python
{
    "map_name": "Thornveil_Region",
    "seed": 42,
    "spec": {...},          # original map_spec for replay
    "steps_completed": ["scene_cleared", "terrain_generated", "water_plane", "road_0"],
    "steps_failed": [],
    "objects_created": ["Thornveil_Terrain", "Thornveil_Water"],
    "locations": [...],     # location_results from completed placement steps
    "interiors": [...],
    "last_updated": "2026-03-31T12:00:00Z"
}
```

**Resume logic (pure Python, testable without Blender):**
```python
# Source: codebase pattern from map_composer.py + settlement_generator.py
def load_checkpoint(checkpoint_dir: str, map_name: str) -> dict | None:
    path = Path(checkpoint_dir) / f"{map_name}_checkpoint.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)

def save_checkpoint(checkpoint_dir: str, state: dict) -> None:
    path = Path(checkpoint_dir) / f"{state['map_name']}_checkpoint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
```

### Pattern 2: Scene Hierarchy JSON

**What:** After all Blender objects are created and named, traverse bpy.data.objects and emit a hierarchy JSON describing each object's name, type (terrain/building/interior/prop/road), parent, world position/rotation/scale, and the Addressable group it belongs to.

**When to use:** End of `generate_map_package` action, consumed by Unity `setup_map_streaming`.

**Schema (per object entry):**
```json
{
    "name": "Village_TavernExterior",
    "type": "building",
    "district": "market",
    "addressable_group": "Map_District_Market",
    "world_position": [12.5, 0.0, -8.3],
    "world_rotation_euler": [0.0, 0.0, 1.57],
    "world_scale": [1.0, 1.0, 1.0],
    "fbx_path": "Assets/Maps/Thornveil/Buildings/Village_TavernExterior.fbx",
    "lod_variants": ["_LOD0", "_LOD1", "_LOD2"],
    "has_interior": true,
    "interior_name": "Village_TavernInterior"
}
```

### Pattern 3: Per-District Addressable Groups

**What:** Map each location returned by compose_map to an Addressable group named `Map_{MapName}_District_{DistrictName}`. Terrain tiles use distance-based grouping (`Map_{MapName}_Terrain_Near` / `_Mid` / `_Far`). Each building with an interior is its own sub-group.

**When to use:** Called from new Unity action `setup_map_streaming` after scene hierarchy JSON is available.

**Group naming convention:**
```
Map_Thornveil_Terrain_Near      (within 80m of player start)
Map_Thornveil_Terrain_Mid       (80-200m)
Map_Thornveil_Terrain_Far       (200m+, low-res)
Map_Thornveil_District_Market   (town center buildings + roads)
Map_Thornveil_District_Civic
Map_Thornveil_District_Residential
Map_Thornveil_District_Industrial
Map_Thornveil_Building_Tavern   (building + interior as one group)
Map_Thornveil_Building_Blacksmith
```

The existing `generate_addressables_config_script()` in `build_templates.py` already generates BundledAssetGroupSchema groups -- the new code calls it with a group list derived from compose_map output.

### Pattern 4: Occlusion Portal Geometry

**What:** At every interior doorway, generate a thin quad mesh (0.1m depth) that covers the door opening exactly, named `{building}_Portal_{door_idx}`. This mesh is the Unity Occlusion Portal trigger geometry. Also generate `{building}_OcclusionZone` (a slightly inset convex box matching the room bounds) as a static occluder.

**When to use:** During `compose_interior` step, after room shells are placed and doors are defined in `planned_doors`.

**Blender handler pattern:**
```python
# Added to worldbuilding_layout.py or building_interior_binding.py
def _create_occlusion_portal(door: dict, room_a: dict, room_b: dict, seed: int) -> dict:
    """Create portal quad at door opening for Unity streaming boundary."""
    # door has: position (x,y,z), width, height, orientation
    # Returns: {"name": str, "type": "occlusion_portal", "bounds": [...]}
```

### Anti-Patterns to Avoid

- **Monolithic export:** Do not try to export the entire map as one FBX. Export per-object or per-group so Addressables can bundle them separately.
- **Baking Addressables at pipeline time:** The Blender side produces a group config script; Unity side runs `AddressableAssetSettings.BuildPlayerContent()` only at Unity build time, not during map generation.
- **Skipping game_check before export:** The existing `blender_mesh action=game_check` rule from CLAUDE.md is mandatory before any FBX export. The `generate_map_package` action must call game_check on all created objects before exporting.
- **Hard-coding district names:** District names come from map_spec locations, not a fixed enum. The Addressable group generator must accept arbitrary district strings.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Addressable group creation | Custom Unity asset database code | `generate_addressables_config_script()` in `build_templates.py` | Already verified against UnityEditor.AddressableAssets API |
| FBX export settings | Custom FBX writer | `handle_export_fbx()` in `export.py` | Unity-optimised axis, scale, and bone settings already correct |
| LOD generation | Per-export LOD logic | `blender_addon.handlers.lod_pipeline` | Phase 30 LOD pipeline with silhouette preservation exists |
| Step isolation / error resilience | Custom try/except scaffolding | Existing `steps_completed`/`steps_failed` pattern from compose_map | Already battle-tested across 9 compose_map steps |
| Game-readiness validation | Custom mesh checkers | `blender_mesh action=game_check` | Phase 30 validator: poly count, UVs, normals |

**Key insight:** The hard infrastructure already exists. This phase is integration glue -- state persistence, group derivation from map data, and portal geometry generation. No new algorithms required.

---

## Common Pitfalls

### Pitfall 1: Checkpoint Stale After Spec Change
**What goes wrong:** User re-runs pipeline with a different map_spec but same map_name and same checkpoint_dir. Resume logic skips already-completed steps but applies new spec from the current call -- mismatch between checkpoint's cached `locations` and the new spec's locations.
**Why it happens:** Resume logic reads checkpoint `steps_completed` but not the original spec.
**How to avoid:** On resume, compare spec seed + location count from checkpoint vs current call. If mismatch, warn and require `force_restart=True` to clear checkpoint.
**Warning signs:** `locations` list in checkpoint has different length than `spec.locations` in current call.

### Pitfall 2: Blender Object Name Drift
**What goes wrong:** Scene hierarchy JSON captures object names at export time. Unity imports FBX with auto-renamed objects (trailing `.001` suffix for duplicates). Addressable group membership breaks.
**Why it happens:** Blender auto-deduplicates object names when objects are created without unique names.
**How to avoid:** Enforce unique naming in compose_map: `f"{map_name}_{loc_type}_{i}"`. Validate all object names before scene hierarchy JSON is emitted. Assert no `.` in exported object names.
**Warning signs:** FBX import log in Unity shows renamed meshes.

### Pitfall 3: Per-Object FBX Export Is Slow
**What goes wrong:** Exporting 50+ buildings as individual FBXs takes minutes in Blender due to repeated selection/export cycles.
**Why it happens:** `bpy.ops.export_scene.fbx(use_selection=True)` selects/deselects each object in a loop.
**How to avoid:** Group objects by Addressable group first, then export each group as one FBX (one FBX per group, not per object). Interior and exterior of same building go into the same FBX file with consistent pivot.
**Warning signs:** Export step taking >60 seconds per location.

### Pitfall 4: Unity Occlusion Bake Requires Static Flag
**What goes wrong:** Unity's StaticOcclusionCulling.Compute() only considers objects marked as Static. Procedurally placed buildings imported via Addressables are not static by default.
**Why it happens:** Addressable-loaded objects instantiate at runtime without the Static flag.
**How to avoid:** The `setup_map_streaming` Unity C# script must set `GameObjectUtility.SetStaticEditorFlags` on all imported building objects before baking occlusion in-editor. Include this in the generated script.
**Warning signs:** Occlusion bake window shows 0 occluders.

### Pitfall 5: Interior/Exterior Z-fighting at Portal Boundary
**What goes wrong:** The exterior building wall and interior room floor/wall occupy the same world-space plane, causing Z-fighting visible through portals.
**Why it happens:** Interior room shells generated by `compose_interior` are positioned at building world origin without wall thickness offset.
**How to avoid:** Interior shells use a 0.1m inset on all bounding faces. Document this as a placement rule in `pipeline_state.py` portal geometry function.
**Warning signs:** Visual glitching at door thresholds in Blender viewport.

---

## Code Examples

### Checkpoint Save/Load

```python
# Source: codebase pattern (pure Python, no bpy dependency)
import json
from pathlib import Path

CHECKPOINT_FILENAME = "{map_name}_checkpoint.json"

def save_pipeline_checkpoint(checkpoint_dir: str, state: dict) -> str:
    """Persist pipeline state to disk. Returns file path."""
    path = Path(checkpoint_dir) / CHECKPOINT_FILENAME.format(map_name=state["map_name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return str(path)

def load_pipeline_checkpoint(checkpoint_dir: str, map_name: str) -> dict | None:
    """Load checkpoint if it exists, else return None."""
    path = Path(checkpoint_dir) / CHECKPOINT_FILENAME.format(map_name=map_name)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

### Deriving Addressable Groups from compose_map Output

```python
# Source: derived from compose_map result schema (blender_server.py lines 1143-1160)
def derive_addressable_groups(map_name: str, locations: list[dict]) -> list[dict]:
    """Convert compose_map location results to Addressable group dicts."""
    groups = []
    for loc in locations:
        district = loc.get("type", "unknown").capitalize()
        group_name = f"Map_{map_name}_District_{district}"
        groups.append({
            "name": group_name,
            "packing": "PackTogether",
            "local": True,
        })
    # Terrain distance groups
    for tier in ("Near", "Mid", "Far"):
        groups.append({
            "name": f"Map_{map_name}_Terrain_{tier}",
            "packing": "PackSeparately",
            "local": True,
        })
    return groups
```

### Scene Hierarchy JSON Emitter (Blender-side)

```python
# Source: bpy.data.objects traversal pattern used in blender_server.py
import bpy
import json

def emit_scene_hierarchy(map_name: str, location_results: list[dict]) -> dict:
    """Traverse Blender scene and emit per-object hierarchy for Unity."""
    objects = []
    loc_lookup = {loc["name"]: loc for loc in location_results}
    for obj in bpy.data.objects:
        if obj.type not in ("MESH", "EMPTY"):
            continue
        pos = list(obj.matrix_world.to_translation())
        rot = list(obj.matrix_world.to_euler())
        scl = list(obj.matrix_world.to_scale())
        loc_match = loc_lookup.get(obj.name, {})
        objects.append({
            "name": obj.name,
            "type": _classify_object(obj.name, loc_results=location_results),
            "district": loc_match.get("type", "world"),
            "world_position": [round(v, 4) for v in pos],
            "world_rotation_euler": [round(v, 4) for v in rot],
            "world_scale": [round(v, 4) for v in scl],
        })
    return {"map_name": map_name, "objects": objects}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual FBX drag-drop into Unity | Addressables per-group streaming | Unity 2019+ | Districts load/unload independently; no single-frame spike |
| Unity static occlusion culling (manual bake) | Portal-based streaming + static occlusion combined | Unity 2021+ | Portals cull interior geometry at doorways before static bake fires |
| Monolithic world scene | Additive scene loading per zone | Unity 2018+ | Memory pressure reduced; only active zones resident |

**Deprecated/outdated:**
- Manual LOD placement in Unity (replaced by LOD Group component auto-configured by the import script -- already in asset_templates.py)
- Unity Occlusion Areas (manual box placement) -- replaced by portal quad geometry placed at doorways during pipeline export

---

## Open Questions

1. **Phase 36 completion status**
   - What we know: Phase 36 (World Composer) is listed as MESH-08 pending; the 36-CONTEXT.md exists with design decisions but no 36-PLAN.md or implementation confirmed.
   - What's unclear: Whether compose_map already calls the Phase 36 road mesh + district zoning code, or whether Phase 37 will run against placeholder locations.
   - Recommendation: Phase 37 implementation should treat `location_results` from compose_map as an opaque list of `{name, type, anchor, radius}` dicts and not depend on district-level data that Phase 36 may not yet expose. The Addressable group derivation can fall back to location type if district data is absent.

2. **Export path convention for Unity**
   - What we know: `handle_export_fbx()` takes a filepath param. Unity Addressables expect assets under `Assets/` in the Unity project.
   - What's unclear: The Unity project path is not stored in compose_map state. The `generate_map_package` action needs a `unity_assets_path` param.
   - Recommendation: Add `unity_assets_path` as an optional param to `generate_map_package` with a sensible default (`~/VeilBreakers3DCurrent/Assets/Maps/`).

3. **MESH-16 scope ambiguity**
   - What we know: MESH-16 is described as "Clean commit workflow -- atomic commits after every bug/error scan, state tracked in STATE.md". This sounds like a process requirement, not a code feature.
   - What's unclear: Whether MESH-16 requires a code change (e.g., a CI hook or a STATE.md auto-updater), or just adherence to process during this phase.
   - Recommendation: Treat MESH-16 as a process requirement satisfied by: (a) the phase includes atomic commits after each task, (b) STATE.md is updated at phase completion. No new code needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `json` / `pathlib` | Checkpoint persistence | Built-in | stdlib | -- |
| Blender FBX exporter | generate_map_package | Built-in | Blender 4.x | glTF export |
| Unity Addressables package | setup_map_streaming | Confirmed in VB3DCurrent | Latest for Unity 6 | -- |
| Unity StaticOcclusionCulling | occlusion bake step | Built-in Unity 6 | Unity 6.x | Manual bake instruction |

No missing blocking dependencies.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `Tools/mcp-toolkit/pytest.ini` (inferred from existing test suite) |
| Quick run command | `pytest Tools/mcp-toolkit/tests/test_pipeline_state.py Tools/mcp-toolkit/tests/test_world_streaming_templates.py -x` |
| Full suite command | `pytest Tools/mcp-toolkit/tests/ -x --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | AAA technique research document present and has required sections | smoke | `pytest Tools/mcp-toolkit/tests/test_pipeline_state.py::test_pipe01_research_document_exists -x` | Wave 0 |
| MESH-16 | STATE.md updated + atomic commits per scan | manual | manual review | -- |
| SC-1 | `save_pipeline_checkpoint` writes JSON; `load_pipeline_checkpoint` reads it back | unit | `pytest tests/test_pipeline_state.py::TestCheckpoint -x` | Wave 0 |
| SC-1 | Resume skips completed steps | unit | `pytest tests/test_pipeline_state.py::TestResume -x` | Wave 0 |
| SC-2 | `derive_addressable_groups` produces one group per location type + 3 terrain tiers | unit | `pytest tests/test_world_streaming_templates.py::TestAddressableGroups -x` | Wave 0 |
| SC-3 | `generate_occlusion_portal_geometry` produces quad mesh spec at door bounds | unit | `pytest tests/test_world_streaming_templates.py::TestPortalGeometry -x` | Wave 0 |
| SC-4 | Scene hierarchy JSON contains all expected fields per object entry | unit | `pytest tests/test_pipeline_state.py::TestSceneHierarchy -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest Tools/mcp-toolkit/tests/test_pipeline_state.py Tools/mcp-toolkit/tests/test_world_streaming_templates.py -x`
- **Per wave merge:** `pytest Tools/mcp-toolkit/tests/ -x --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `Tools/mcp-toolkit/tests/test_pipeline_state.py` -- checkpoint R/W, resume logic, scene hierarchy
- [ ] `Tools/mcp-toolkit/tests/test_world_streaming_templates.py` -- Addressable group derivation, portal geometry spec

---

## Sources

### Primary (HIGH confidence)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` lines 2412-2714 -- full compose_map implementation read directly
- `Tools/mcp-toolkit/blender_addon/handlers/map_composer.py` lines 1002-1160 -- `compose_world_map()` signature and return schema
- `Tools/mcp-toolkit/blender_addon/handlers/export.py` -- FBX/glTF export handlers
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/build_templates.py` lines 279-397 -- `generate_addressables_config_script()` full implementation
- `.planning/phases/36-world-composer/36-CONTEXT.md` -- Phase 36 decisions and canonical refs
- `.planning/REQUIREMENTS.md` -- MESH-16, PIPE-01 requirement text

### Secondary (MEDIUM confidence)
- Memory `project_vb3d_codebase_map.md` -- VeilBreakers3DCurrent uses Unity 6.x URP 17.3, Addressables already in project
- Memory `project_v7_execution_progress.md` -- Phase 35 complete, Phase 36 partially planned

### Tertiary (LOW confidence)
- None -- all key decisions grounded in direct code reads

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- direct code inspection, no training assumptions
- Architecture: HIGH -- derives from existing compose_map + build_templates patterns
- Pitfalls: HIGH -- derived from actual code behaviour (object naming, FBX export loop)

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable infrastructure, no fast-moving APIs)
