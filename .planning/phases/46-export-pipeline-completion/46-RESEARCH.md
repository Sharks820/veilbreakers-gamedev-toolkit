# Phase 46: Export Pipeline Completion - Research

**Researched:** 2026-04-04
**Domain:** Blender-to-Unity export pipeline (FBX, LOD, bake, collision, vegetation, splatmap, QA)
**Confidence:** HIGH

## Summary

Phase 46 addresses nine requirements (EXPORT-01 through EXPORT-09) plus TEST-04 covering the final mile of the Blender-to-Unity asset pipeline. The codebase already has robust individual components -- FBX export with Unity-specific material tagging (export.py), silhouette-preserving LOD generation (pipeline_lod.py), multi-channel texture baking (texture.py), collision mesh UCX_ renaming (export.py), game_check validation (mesh.py), and vertex-color splatmap computation (terrain_materials.py). The gap is that these systems are not wired into the `compose_map` pipeline and several have integration bugs.

The three bug-fix requirements (EXPORT-08 and EXPORT-09) are well-characterized: `aaa_verify` sends `render_angle` which aliases to `handle_get_viewport_screenshot` (ignores yaw/pitch/output_path params, reuses stale temp PNGs), and `generate_map_package` calls `derive_addressable_groups()` which emits empty terrain/interiors groups while `export_fbx` ignores the `object_names` parameter entirely.

**Primary recommendation:** Wire existing handlers into compose_map as new checkpoint-backed steps (Steps 11-15), fix the two aliased handlers to accept their documented parameters, and add a splatmap-to-PNG exporter plus a vegetation instance JSON serializer as new pure-logic functions.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXPORT-01 | Add FBX export step to compose_map for all non-terrain objects | compose_map ends at Step 10 (heightmap). Add Step 11 calling `export_fbx` per addressable group. Fix `export_fbx` to accept `object_names` filter. |
| EXPORT-02 | Add texture bake step to pipeline (diffuse, normal, AO, curvature) | `handle_bake_procedural_to_images` exists in texture.py (lines 1186+). Wire into compose_map as Step 12 before FBX export. |
| EXPORT-03 | Add LOD generation step with silhouette-preserving decimation | `handle_generate_lods` exists in pipeline_lod.py. Wire into compose_map as Step 13. LOD0/1/2/3 ratios [1.0, 0.5, 0.25, 0.1] already default. |
| EXPORT-04 | Add game_check validation step before export | `handle_check_game_ready` exists in mesh.py (line 1224). Wire into compose_map as Step 11a (before FBX). Already used by generate_map_package. |
| EXPORT-05 | Add collision mesh generation (UCX_ prefix) | UCX_ rename exists in export.py. Collision mesh generation (convex hull via bmesh) exists in equipment.py (line 1837). Extract to shared utility and wire into compose_map. |
| EXPORT-06 | Vegetation instance serialization (Blender scatter -> Unity TreeInstance) | No code exists. Build new pure-logic serializer that reads vegetation collection objects and outputs JSON: `{position, rotation, scale, prototypeIndex, widthScale, heightScale}` matching Unity's `TreeInstance` struct. |
| EXPORT-07 | Splatmap-to-image export for Unity Terrain alphamap | Vertex-color splatmap data exists (terrain_materials.py, `auto_assign_terrain_layers`). No image export. Build exporter: read RGBA vertex colors from `VB_TerrainSplatmap` layer, rasterize to image, save as PNG. Unity expects float[,,] alphamaps -- 4 channels per RGBA. |
| EXPORT-08 | Fix aaa_verify stale screenshot bug (yaw/pitch ignored, old PNGs reused) | Root cause: `render_angle` aliased to `handle_get_viewport_screenshot` which ignores yaw/pitch. Also reads `filepath` not `output_path`. Fix: implement real `handle_render_angle` that positions camera. |
| EXPORT-09 | Fix generate_map_package broken group export | Two bugs: (1) `derive_addressable_groups` emits empty terrain/interiors groups; (2) `export_fbx` ignores `object_names`. Fix both. |
| TEST-04 | Opus verification scan after every phase | Standard follow-up rounds until CLEAN. |
</phase_requirements>

## Architecture Patterns

### Compose_map Pipeline Extension
The compose_map pipeline (blender_server.py lines 2737-3229) uses a checkpoint-resume pattern with named steps. Currently Steps 1-10:
1. scene_cleared
2. terrain_generated
3. water (rivers + plane)
4. roads
5. locations
6. biome_painted + lighting_ready
7. vegetation_scattered
8. props_scattered
9. interiors_generated
10. heightmap_exported

New steps to add (Steps 11-15):
11. **game_check_validated** -- run `mesh_check_game_ready` on all created_objects
12. **textures_baked** -- run `bake_procedural_to_images` on non-terrain meshes
13. **lods_generated** -- run `pipeline_generate_lods` on non-terrain meshes
14. **collisions_generated** -- generate convex hull collision meshes (UCX_ prefix)
15. **fbx_exported** -- run `export_fbx` per addressable group with `object_names` filter

Each step follows the pattern:
```python
if "step_name" not in steps_completed:
    try:
        # do work
        steps_completed.append("step_name")
        _save_chkpt()
    except Exception as e:
        steps_failed.append({"step": "step_name", "error": str(e)})
```

### Recommended New Files
```
blender_addon/handlers/
  export.py                      # MODIFY: add object_names filter to handle_export_fbx
  viewport.py                    # MODIFY: add handle_render_angle (real camera positioning)
  collision_generator.py         # NEW: shared collision mesh generation utility
  vegetation_serializer.py       # NEW: vegetation -> Unity TreeInstance JSON
  splatmap_exporter.py           # NEW: vertex color splatmap -> PNG image
  pipeline_lod.py                # EXISTS: already complete
  pipeline_state.py              # MODIFY: fix derive_addressable_groups

src/veilbreakers_mcp/
  blender_server.py              # MODIFY: compose_map Steps 11-15, fix aaa_verify

tests/
  test_export_pipeline.py        # NEW: integration tests for new steps
  test_collision_generator.py    # NEW: convex hull tests
  test_vegetation_serializer.py  # NEW: TreeInstance format tests
  test_splatmap_exporter.py      # NEW: splatmap rasterization tests
  test_render_angle.py           # NEW: render_angle handler tests
```

### Anti-Patterns to Avoid
- **Silently swallowing exceptions in pipeline steps:** Each step must log failures with context. The current pattern of `except Exception: pass` in generate_map_package (line 3300, 3322) loses critical debugging information.
- **Aliasing handlers instead of implementing them:** `render_angle -> handle_get_viewport_screenshot` was a shortcut that created the aaa_verify stale screenshot bug. Always implement the actual handler when parameter semantics differ.
- **Global scene export when per-group is needed:** `export_fbx` must support `object_names` filtering by selecting objects before export with `selected_only=True`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LOD generation | Custom mesh simplification | `handle_generate_lods` in pipeline_lod.py | Already has silhouette-preserving decimation with 14-view analysis, symmetry detection |
| Texture baking | Manual render-to-texture | `handle_bake_procedural_to_images` in texture.py | Already supports diffuse/normal/AO/metallic/roughness with Cycles, metallic-via-emission trick |
| Convex hull collision | Manual vertex computation | `bmesh.ops.convex_hull()` (Blender API) | Already used in equipment.py, handles edge cases |
| UCX_ prefix rename | String replacement | `_rename_collision_meshes_for_unity()` in export.py | Already handles name collisions, tags custom properties |
| UV2 lightmap layer | Manual UV management | `_ensure_uv2_lightmap_layer()` in export.py | Already handles slot ordering, tagging |
| Material tagging | Custom property writing | `_tag_materials_for_unity()` in export.py | Roughness inversion, texture type classification |

## Common Pitfalls

### Pitfall 1: export_fbx object_names Filter
**What goes wrong:** `generate_map_package` passes `object_names` to `export_fbx`, but `handle_export_fbx` has no such parameter -- it exports the entire scene.
**Why it happens:** The server-level code assumes the handler supports per-object filtering, but the handler was written for scene/selection export only.
**How to avoid:** Implement `object_names` in `handle_export_fbx`: select specified objects in Blender, then export with `selected_only=True`.
**Warning signs:** All group FBX files contain the same full-scene geometry.

### Pitfall 2: derive_addressable_groups Empty Groups
**What goes wrong:** `derive_addressable_groups()` emits terrain group with empty `objects` list and interiors group with empty `objects` list. The terrain group never gets terrain object names; the interiors group is always hardcoded empty.
**Why it happens:** Terrain object names are not passed into the function (only location_results). The interiors group is appended unconditionally with empty objects.
**How to avoid:** Pass terrain object names into the function. Populate interiors group from interior_results. Skip groups with zero objects in the export loop.

### Pitfall 3: aaa_verify Stale Screenshots
**What goes wrong:** `aaa_verify` captures screenshots at 10 camera angles but all screenshots are identical (same viewport angle) and old PNGs persist across runs.
**Why it happens:** Three bugs: (1) `render_angle` is aliased to `handle_get_viewport_screenshot` which ignores `yaw`/`pitch` params; (2) handler reads `filepath` not `output_path`; (3) stable named subdir (`vb_aaa_verify/`) reuses old files.
**How to avoid:** Implement real `handle_render_angle` that positions a camera at specified yaw/pitch. Use `output_path` param. Delete old screenshots before capture.

### Pitfall 4: Splatmap Resolution Mismatch
**What goes wrong:** Blender terrain has per-vertex splatmap data (one RGBA tuple per vertex). Unity terrain alphamaps have separate resolution (typically 512x512 or 1024x1024).
**Why it happens:** Vertex data is irregular -- terrain mesh vertex count depends on resolution parameter, not a nice grid.
**How to avoid:** Rasterize vertex colors onto a regular grid at the target alphamap resolution. Use terrain grid dimensions (`_detect_grid_dims`) for correct mapping.

### Pitfall 5: Vegetation Instance Coordinate System
**What goes wrong:** Blender uses Z-up, Unity uses Y-up. Vegetation positions from Blender scatter are in world coordinates with Z as vertical.
**Why it happens:** Systemic Blender/Unity axis mismatch (documented in feedback_blender_z_up.md).
**How to avoid:** In the vegetation serializer, swap Y/Z coordinates and normalize positions to [0,1] range relative to terrain bounds (Unity TreeInstance uses normalized positions).

### Pitfall 6: Collision Mesh Too Detailed
**What goes wrong:** Running convex hull on high-poly objects produces collision meshes with too many faces, wasting physics CPU budget.
**Why it happens:** bmesh.ops.convex_hull preserves all hull vertices regardless of count.
**How to avoid:** After convex hull generation, apply a simple decimation pass (target ~64-128 faces). Unity's MeshCollider with convex=true has internal triangle limits.

## Code Examples

### Example 1: Adding object_names Filter to export_fbx

```python
# In export.py handle_export_fbx, after line 223:
object_names = params.get("object_names")

# Before export (before line 244 override = get_3d_context_override()):
if object_names:
    # Deselect all, then select only specified objects
    bpy.ops.object.select_all(action='DESELECT')
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
    # Force selected_only for filtered export
    selected_only = True
```

### Example 2: Vegetation Instance Serialization Format

```python
# Unity TreeInstance JSON format
{
    "terrain_name": "Map_Terrain",
    "tree_prototypes": [
        {"prefab_name": "Oak_Tree", "prototype_index": 0},
        {"prefab_name": "Bush_Medium", "prototype_index": 1}
    ],
    "instances": [
        {
            "position": [0.45, 0.0, 0.62],  # normalized [0,1] on terrain XZ
            "rotation": 1.57,                 # radians
            "width_scale": 1.0,
            "height_scale": 1.2,
            "prototype_index": 0
        }
    ]
}
```

### Example 3: Splatmap Rasterization to PNG

```python
import numpy as np
from PIL import Image

def export_splatmap_to_png(
    vertices: list,
    vertex_colors: list[tuple[float,float,float,float]],
    grid_rows: int,
    grid_cols: int,
    output_path: str,
    target_resolution: int = 512,
) -> str:
    """Rasterize per-vertex RGBA splatmap to image.
    
    Unity Terrain expects alphamap as float[height, width, layers].
    Each pixel RGBA maps to 4 terrain layers.
    """
    # Reshape vertex colors to grid
    splatmap = np.array(vertex_colors, dtype=np.float32).reshape(grid_rows, grid_cols, 4)
    
    # Resize to target resolution
    img = Image.fromarray((splatmap * 255).astype(np.uint8), mode='RGBA')
    img = img.resize((target_resolution, target_resolution), Image.BILINEAR)
    img.save(output_path)
    return output_path
```

### Example 4: handle_render_angle Implementation

```python
def handle_render_angle(params: dict) -> dict:
    """Render viewport screenshot from a specific camera angle.
    
    Params:
        yaw (float): Horizontal angle in degrees.
        pitch (float): Vertical angle in degrees.
        output_path (str): File path for the screenshot.
        distance (float): Camera distance from scene center.
    """
    yaw = math.radians(params.get("yaw", 0.0))
    pitch = math.radians(params.get("pitch", 30.0))
    output_path = params.get("output_path") or params.get("filepath") or _unique_temp_path("vb_render")
    distance = params.get("distance", 10.0)
    
    # Compute camera position from spherical coordinates
    cam_x = distance * math.cos(pitch) * math.sin(yaw)
    cam_y = distance * math.cos(pitch) * math.cos(yaw)
    cam_z = distance * math.sin(pitch)
    
    # Create/reuse camera, set position, look at origin
    cam = bpy.data.objects.get("VB_RenderAngle_Camera")
    if not cam:
        cam_data = bpy.data.cameras.new("VB_RenderAngle_Camera")
        cam = bpy.data.objects.new("VB_RenderAngle_Camera", cam_data)
        bpy.context.scene.collection.objects.link(cam)
    
    cam.location = (cam_x, cam_y, cam_z)
    direction = mathutils.Vector((0, 0, 0)) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    
    bpy.context.scene.camera = cam
    # ... render to output_path ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Scene-wide FBX export | Per-group Addressable export | Required now | Enables Unity Addressables streaming |
| No texture bake in pipeline | Auto-bake procedural to images | texture.py already built | Necessary for FBX export (FBX can't embed procedural nodes) |
| render_angle alias | Real camera-positioned render | Must fix in Phase 46 | Enables multi-angle AAA verification |
| Manual LOD creation | Auto silhouette-preserving LOD | pipeline_lod.py already built | 4-tier LOD chain for all assets |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | Tools/mcp-toolkit/pyproject.toml |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_export_pipeline.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x --timeout=120` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXPORT-01 | FBX export step in compose_map | unit | `pytest tests/test_export_pipeline.py::test_fbx_export_step -x` | Wave 0 |
| EXPORT-02 | Texture bake step in pipeline | unit | `pytest tests/test_export_pipeline.py::test_texture_bake_step -x` | Wave 0 |
| EXPORT-03 | LOD generation step | unit | `pytest tests/test_lod_pipeline.py -x` | Exists |
| EXPORT-04 | game_check validation step | unit | `pytest tests/test_export_pipeline.py::test_game_check_step -x` | Wave 0 |
| EXPORT-05 | Collision mesh generation | unit | `pytest tests/test_collision_generator.py -x` | Wave 0 |
| EXPORT-06 | Vegetation instance serialization | unit | `pytest tests/test_vegetation_serializer.py -x` | Wave 0 |
| EXPORT-07 | Splatmap-to-image export | unit | `pytest tests/test_splatmap_exporter.py -x` | Wave 0 |
| EXPORT-08 | aaa_verify stale screenshot fix | unit | `pytest tests/test_render_angle.py -x` | Wave 0 |
| EXPORT-09 | generate_map_package group export fix | unit | `pytest tests/test_pipeline_state.py -x` | Exists (needs extension) |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_export_pipeline.py tests/test_pipeline_state.py -x --timeout=60`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x --timeout=120`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_export_pipeline.py` -- covers EXPORT-01, EXPORT-02, EXPORT-04
- [ ] `tests/test_collision_generator.py` -- covers EXPORT-05
- [ ] `tests/test_vegetation_serializer.py` -- covers EXPORT-06
- [ ] `tests/test_splatmap_exporter.py` -- covers EXPORT-07
- [ ] `tests/test_render_angle.py` -- covers EXPORT-08
- [ ] Extend `tests/test_pipeline_state.py` -- covers EXPORT-09

## Detailed Bug Analysis

### EXPORT-08: aaa_verify Stale Screenshots

**Location:** blender_server.py lines 3348-3410, __init__.py lines 1505-1510

**Root causes (3 independent bugs):**
1. `render_angle` registered as alias to `handle_get_viewport_screenshot` (\_\_init\_\_.py line 1505). The screenshot handler ignores yaw/pitch params entirely -- it just captures whatever is currently in the viewport.
2. `handle_get_viewport_screenshot` reads `filepath` param (line 985) but `aaa_verify` passes `output_path` (line 3380). The handler generates a unique temp path instead.
3. Stable temp directory `vb_aaa_verify/` (line 3370) means old PNGs from previous runs persist. New renders may fail silently, and the code picks up old files.

**Fix plan:**
1. Create `handle_render_angle` function in viewport.py that accepts yaw/pitch/output_path, positions a temporary camera, renders, and cleans up.
2. Register as `"render_angle": handle_render_angle` in \_\_init\_\_.py (replacing the alias).
3. In aaa_verify (blender_server.py), clear the temp directory before starting captures.
4. Read output_path correctly (handler should accept both `filepath` and `output_path`).

### EXPORT-09: generate_map_package Broken Group Export

**Location:** blender_server.py lines 3231-3346, pipeline_state.py lines 204-260

**Root causes (2 independent bugs):**
1. `derive_addressable_groups()` creates terrain group with `"objects": []` (line 229) and interiors group with `"objects": []` (line 257). Terrain objects are never added because the function only receives `location_results`, not terrain names. Interiors are hardcoded empty.
2. `handle_export_fbx()` in export.py has no `object_names` parameter. When generate_map_package calls `export_fbx` with `object_names` (line 3318), the handler ignores it and exports the entire scene.

**Fix plan:**
1. Add `terrain_objects` and `interior_results` parameters to `derive_addressable_groups()`.
2. Populate terrain group objects from terrain_objects list.
3. Populate interiors group objects from interior_results.
4. Add `object_names` support to `handle_export_fbx()` via Blender selection filtering.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of export.py, pipeline_lod.py, texture.py, mesh.py, environment.py, terrain_materials.py, environment_scatter.py, viewport.py, blender_server.py, pipeline_state.py, __init__.py
- V9_MASTER_FINDINGS.md Section 11 (Export Pipeline) and Section 16.19 (deep scan findings)
- REQUIREMENTS.md (EXPORT-01 through EXPORT-09)

### Secondary (MEDIUM confidence)
- Unity TerrainData.SetAlphamaps API format from scene_templates.py (C# templates in codebase)
- Unity TreeInstance struct format from training data (standard Unity API, stable for years)

### Tertiary (LOW confidence)
- None -- all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all components exist in codebase, just need wiring
- Architecture: HIGH - compose_map checkpoint pattern is well-established, extensions follow same pattern
- Pitfalls: HIGH - bugs verified by reading exact source lines
- Bug fixes: HIGH - root causes traced to specific code lines with clear fix paths

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- internal codebase, no external dependency changes expected)
