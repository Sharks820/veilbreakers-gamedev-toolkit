# Phase 39: Pipeline & Systemic Fixes - Research

**Researched:** 2026-04-04
**Domain:** Blender addon pipeline architecture, Python API compatibility, coordinate systems, terrain math
**Confidence:** HIGH

## Summary

Phase 39 eliminates every systemic pipeline bug that downstream phases depend on. The codebase has 147+ documented bug instances across 9 categories, with exact file:line locations from the V9 53-agent audit. The work divides into 8 clear workstreams: (1) pipeline dispatch routing fixes, (2) Z=0 hardcoded placements replaced with terrain-height sampling, (3) deprecated Blender API calls, (4) Y-axis vertical bugs, (5) smart planner wiring, (6) smoothstep shared utility, (7) square-terrain assumption fixes, and (8) rectangular terrain geometry bugs.

The CRITICAL user directive is to consolidate TWO pipeline paths into ONE. Research confirms `compose_map` in `blender_server.py` is the canonical pipeline (10+ steps, checkpoint resume, full orchestration). `compose_world_map` in `map_composer.py` has superior placement logic (biome-aware, slope-respecting, MST road generation) that `compose_map` lacks. The correct action is: merge `compose_world_map`'s placement intelligence INTO `compose_map` Step 5, then deprecate `handle_compose_world_map` as a standalone entry point.

All bug locations are precisely documented in V9_MASTER_FINDINGS.md with file:line references. No exploratory research needed -- this is surgical fix work.

**Primary recommendation:** Fix dispatch bugs first (they block everything), then Z=0/smoothstep utilities (they enable bulk fixes), then apply bulk fixes across all 9+ files, then wire smart planner, then fix rectangular terrain assumptions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicitly locked -- all implementation choices at Claude's discretion.

### Claude's Discretion
All implementation choices are at Claude's discretion -- pure infrastructure phase. Use V9_MASTER_FINDINGS.md (sections 1-2, 16.10, 19.1) as the authoritative source for every bug location and fix specification. Follow ROADMAP phase goal, success criteria, and codebase conventions.

Key references for exact line numbers and fix details:
- V9_MASTER_FINDINGS.md Section 1: Pipeline Architecture (dispatch bugs, smart planner)
- V9_MASTER_FINDINGS.md Section 2: Codebase-Wide Systemic Bugs (147+ instances with file:line)
- V9_MASTER_FINDINGS.md Section 16.10: Additional Code Bugs
- V9_MASTER_FINDINGS.md Section 19.1: Foundational Rules (smootherstep, safe_place_object utilities)

### Deferred Ideas (OUT OF SCOPE)
None -- infrastructure phase, all items are in scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Fix 3 pipeline dispatch bugs (asset_pipeline COMMAND_HANDLERS, _LOC_HANDLERS settlement routing, param shape mismatches) | Exact locations confirmed: `__init__.py:1461-1465`, `blender_server.py:2932`, handler param analysis complete |
| PIPE-02 | Fix 42 Z=0 hardcoded placements across 9 files with safe_place_object() utility | All 42 instances catalogued with file:line in V9 Section 2 Pattern 1. `_sample_scene_height()` already exists at `worldbuilding.py:2595` |
| PIPE-03 | Fix 6 deprecated Blender 5.0 API calls | 3 categories confirmed: `group.inputs/outputs.new()` at `terrain_materials.py:1560-1578`, `ShaderNodeTexMusgrave` at `geometry_nodes.py:156`, `cap_fill` (invalid param name) at `worldbuilding.py:3200,3544,6983` |
| PIPE-04 | Fix Y-axis vertical bugs (full codebase grep, terrain_features cliff outcrop) | V9 Pattern 7 documents cliff outcrop Y-axis stacking. Full grep required during execution |
| PIPE-05 | Wire compose_world_map smart planner into compose_map Step 5 | Pipeline analysis complete: `compose_map` is canonical, `compose_world_map` has superior biome/slope/MST logic. Merge plan documented |
| PIPE-06 | Create smoothstep() shared utility, replace 35 linear interpolation sites | All 35 sites documented in V9 Section 2 Pattern 2 with exact file:line references |
| PIPE-07 | Fix all square-terrain assumptions (6+ files: chunking, scatter, road, export, sculpt, layers) | 6+ files confirmed with specific bugs: `terrain_chunking.py:174`, `environment_scatter.py:286`, heightmap export, terrain_layers, terrain_sculpt |
| PIPE-08 | Fix rectangular terrain bugs (heightmap export squash, road warp, scatter drift) | Exact bugs documented in V9 Section 16.19 with file references |
| TEST-01 | All existing tests pass (19,850+ baseline) | 19,863 tests currently collected. Pytest configured in `pyproject.toml` |
| TEST-04 | Opus verification scan after every phase | Protocol documented in STATE.md verification section |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- **Always verify visually** after Blender mutations.
- **Blender is Z-up** -- Y-up conversion happens at EXPORT time only.
- **Use seeds** for reproducible generation.
- **Batch when possible**.
- **Tool architecture**: compound pattern (one tool name, `action` param selects operation).
- Tests run via `pytest tests/` in `Tools/mcp-toolkit/`.

## Architecture Patterns

### Pipeline Consolidation Strategy

**CRITICAL USER DIRECTIVE: ONE active pipeline.**

The codebase has TWO pipeline paths:

| Pipeline | Location | Capabilities | Weakness |
|----------|----------|-------------|----------|
| `compose_map` | `blender_server.py:2732-3200+` | Full 10-step orchestration, checkpoint resume, terrain+water+roads+locations+vegetation+props+atmosphere+interiors | Uses simple ring-based anchor placement (`_plan_map_location_anchors`) -- no biome/slope awareness |
| `compose_world_map` | `map_composer.py:1002-1120+` | Biome-aware placement, slope-respecting, MST road generation, Veil pressure bands, 21 biome types, 14 POI types | Roads/POIs only -- no terrain gen, no water, no vegetation, no checkpoints |

**Winner: `compose_map`** -- it is the full pipeline with checkpoint resume and all generation steps.

**Merge strategy:**
1. Extract `compose_world_map`'s placement logic into a reusable function
2. Replace `_plan_map_location_anchors` (simple ring placement) with `compose_world_map`'s biome/slope/MST placement when a heightmap is available
3. Replace compose_map Step 4 (simple waypoint roads) with MST-generated roads from `compose_world_map`
4. Keep `handle_compose_world_map` registered in COMMAND_HANDLERS but have it delegate to compose_map (backward compat) or mark deprecated
5. The pure-logic `compose_world_map()` function in `map_composer.py` stays as a testable utility -- it has NO bpy imports and is fully testable

### Dispatch Architecture

```
MCP Server (blender_server.py)
  --> TCP to Blender addon (socket_server.py)
    --> COMMAND_HANDLERS dict (handlers/__init__.py:683-1480)
      --> Individual handler functions in handlers/*.py
```

Key dispatch maps:
- `COMMAND_HANDLERS` in `handlers/__init__.py:683` -- 100+ command-to-function mappings
- `_LOC_HANDLERS` in `blender_server.py:2924` -- location type to worldbuilding command routing
- `asset_pipeline` entry at `__init__.py:1461-1465` -- currently only handles `generate_lods`

### Shared Utilities Location

New shared utilities should go in a dedicated module:

```
blender_addon/handlers/
  _shared_utils.py  (NEW)  -- smoothstep(), safe_place_object()
```

This follows the existing underscore-prefix convention for internal modules (`_terrain_noise.py`, `_terrain_erosion.py`, `_terrain_depth.py`, `_mesh_bridge.py`, etc.).

### Recommended Fix Order (dependency-aware)

```
Wave 1: Foundation (no dependencies)
  1a. Create _shared_utils.py with smoothstep() and safe_place_object()
  1b. Fix dispatch bugs (PIPE-01)
  1c. Fix deprecated Blender API (PIPE-03)
  
Wave 2: Bulk application (depends on Wave 1 utilities)
  2a. Replace 42 Z=0 hardcodings with safe_place_object() (PIPE-02)
  2b. Replace 35 linear interpolations with smoothstep() (PIPE-06)
  2c. Fix Y-axis bugs (PIPE-04)
  
Wave 3: Architecture (depends on Wave 1 dispatch fixes)
  3a. Wire compose_world_map smart planner into compose_map (PIPE-05)
  3b. Fix square-terrain assumptions (PIPE-07)
  3c. Fix rectangular terrain bugs (PIPE-08)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terrain height sampling | Custom raycasting per call site | `_sample_scene_height()` at `worldbuilding.py:2595` | Already handles ARCH-028 (terrain-only hits), multi-ray fallback, error handling |
| Smooth interpolation | Inline `t*t*(3-2*t)` at each site | `smoothstep(t)` shared utility | 35 sites need it; central utility ensures consistency and enables future upgrade to quintic |
| Object terrain placement | Manual Z calculation per handler | `safe_place_object(x, y, terrain_name)` wrapper | Combines height sampling + water exclusion + bounds check in one call |
| Grid dimension detection | `int(math.sqrt(vert_count))` | `_detect_grid_dims(bm)` at `environment.py:51` | Already handles non-square terrains via coordinate set counting |
| MST road network | Manual waypoint specification | `_generate_world_roads()` from `map_composer.py:525` | Prim's MST + terrain-cost weighting + shortcut edges already implemented |

## Detailed Bug Catalog

### PIPE-01: Pipeline Dispatch Bugs (3 bugs)

**Bug 1: asset_pipeline COMMAND_HANDLERS only handles generate_lods**
- Location: `handlers/__init__.py:1461-1465`
- Current code: Lambda that checks `action == "generate_lods"` and returns error for everything else
- Impact: 25+ asset_pipeline actions fail if routed through the addon handler
- Fix: Add routing for all asset_pipeline actions or remove the stub handler and let the MCP server handle routing (since compose_map goes through `blender_server.py` not through this handler)

**Bug 2: _LOC_HANDLERS["settlement"] routes to wrong handler**
- Location: `blender_server.py:2932`
- Current: `"settlement": "world_generate_town"` 
- Should be: `"settlement": "world_generate_settlement"`
- Impact: Full settlement system (15 types in `settlement_generator.py`) bypassed; always falls back to basic town generation
- Verified: `world_generate_settlement` IS registered in COMMAND_HANDLERS at `__init__.py:846`

**Bug 3: Parameter shape mismatches**
- Multiple locations where the same handler is called from different MCP tools with different parameter key names (e.g., `name` vs `object_name`, `terrain_name` inconsistencies)
- Fix: Audit all handler call sites for param key consistency

### PIPE-02: Z=0 Hardcoding (42 instances across 9 files)

**Affected files with line numbers (from V9 Section 2):**

| File | Lines | Count |
|------|-------|-------|
| `worldbuilding_layout.py` | 67, 73, 79, 86, 125, 132, 154, 164, 174, 492, 515, 674, 677, 680, 688, 691, 701, 704 | 18 |
| `worldbuilding.py` | 3366, 3380, 6000, 6188, 6214, 6229, 6273, 6373, 7052, 7416, 7645 | 11 |
| `coastline.py` | 268, 277, 286, 335, 351, 367 | 6 |
| `terrain_features.py` | 705, 729 | 2 |
| `environment_scatter.py` | 156, 203, 289, 412 | 4 |
| `vegetation_scatter.py` | 98, 156 | 2 |
| `rock_scatter.py` | 67 | 1 |
| `mesh.py` | 487 | 1 |
| `water.py` | 234 | 1 |

**Existing utility:** `_sample_scene_height(x, y, terrain_name)` at `worldbuilding.py:2595`
- Raycasts from (x, y, 10000) downward
- Filters for terrain-only hits when terrain_name provided (ARCH-028)
- Falls back to 0.0 on failure

**New utility needed:** `safe_place_object(x, y, terrain_name, water_level=None)` wrapper that:
1. Calls `_sample_scene_height(x, y, terrain_name)` for Z
2. Checks `z < water_level` for water exclusion
3. Checks bounds (within terrain extents)
4. Returns `(x, y, z)` or `None` if placement is invalid

### PIPE-03: Deprecated Blender API (6 instances)

**Category 1: Node group interface API (Blender 4.0+)**
- `terrain_materials.py:1560-1563` -- `group.inputs.new("NodeSocketFloat", "Height_A")` etc.
- `terrain_materials.py:1578` -- `group.outputs.new("NodeSocketFloat", "Result")`
- Fix: `group.interface.new_socket(name="Height_A", in_out='INPUT', socket_type='NodeSocketFloat')`
- Confidence: HIGH -- verified via Blender 4.0 release notes and official API docs

**Category 2: ShaderNodeTexMusgrave (Blender 4.1+)**
- `geometry_nodes.py:156` -- Listed in VALID_GN_NODES whitelist
- Fix: Replace with `ShaderNodeTexNoise` (Musgrave was merged into Noise Texture node in Blender 4.1)
- Confidence: HIGH -- documented Blender 4.1 change

**Category 3: `cap_fill` invalid parameter name**
- `worldbuilding.py:3200` -- `bmesh.ops.create_circle(bm, cap_fill=True, segments=24, radius=radius)`
- `worldbuilding.py:3544` -- `cap_fill=True`
- `worldbuilding.py:6983` -- `bmesh.ops.create_circle(bm, cap_fill=True, segments=32, radius=diameter / 2)`
- Fix: Change `cap_fill=True` to `cap_ends=True` (correct bmesh parameter name)
- Note: `environment_scatter.py:1610` already uses correct `cap_ends=True, cap_tris=True`
- Confidence: HIGH -- verified against bmesh.ops documentation; `cap_fill` never existed as a parameter name

### PIPE-04: Y-Axis Vertical Bugs

**Known instance:** `terrain_features.py` cliff outcrop -- layers stack along Y instead of Z
- Blender uses Z-up coordinate system
- Y-axis should only be used for depth/forward direction
- Full codebase grep required during execution to find all instances

**Grep patterns to execute:**
```
# Find Y used for vertical stacking
grep -n "\.y\s*[+\-]=" handlers/*.py | grep -i "height\|stack\|layer\|vert\|up"
# Find hardcoded Y-up assumptions
grep -n "Vector.*0.*1.*0\|up.*=.*y\|vertical.*y" handlers/*.py
```

### PIPE-05: Smart Planner Wiring

**Current state:**
- `compose_map` Step 5 uses `_plan_map_location_anchors()` at `blender_server.py:208` -- simple ring-based placement
- `compose_world_map()` at `map_composer.py:1002` has:
  - Biome-aware placement via `POI_PLACEMENT_RULES` (14 POI types with slope/elevation/biome preferences)
  - Slope-respecting placement via heightmap sampling
  - MST road generation via Prim's algorithm (`_generate_world_roads` at line 525)
  - Veil pressure band system (4 bands: safehold/frontier/contested/veil_belt)
  - Min-distance enforcement between POIs
  - 21 biome types

**Wiring plan:**
1. In `compose_map` between Step 2 (terrain) and Step 5 (locations), call `compose_world_map()` with the generated terrain's heightmap
2. Use returned POI positions as anchors instead of `_plan_map_location_anchors()` ring placement
3. Use returned roads instead of manual `spec.get("roads", [])` waypoints
4. Keep `_plan_map_location_anchors` as fallback when no heightmap available
5. `compose_world_map()` is pure-logic (no bpy imports) -- safe to call from async MCP server code

### PIPE-06: Smoothstep Shared Utility

**Formula:** `t * t * (3.0 - 2.0 * t)` (Hermite smoothstep)

Note: V9_MASTER_FINDINGS calls this "smootherstep" but the formula `t*t*(3-2*t)` is technically "smoothstep" (Hermite). True smootherstep/quintic is `6t^5 - 15t^4 + 10t^3` (Ken Perlin). The `_terrain_noise.py:101` already uses the quintic version for Perlin noise. For animation and terrain transitions, the Hermite version is standard and correct.

**35 sites to replace (from V9 Section 2 Pattern 2):**

| File | Lines |
|------|-------|
| `animation_gaits.py` | 1375, 1522, 1524, 1661, 1663 |
| `animation_combat.py` | 563, 576, 651, 652 |
| `animation_monster.py` | 89, 91, 208, 216 |
| `animation_environment.py` | 143, 163, 186, 208, 229, 410, 437 |
| `animation_locomotion.py` | 292, 297, 311, 316, 342, 371, 541, 542 |

**Pattern to find:** `start_val + (end_val - start_val) * t` where t is unsmoothed
**Replace with:** `start_val + (end_val - start_val) * smoothstep(t)`

**Utility design:**
```python
def smoothstep(t: float) -> float:
    """Hermite smoothstep: S-curve interpolation in [0, 1].
    
    Replaces linear ``t`` with smooth ease-in-ease-out.
    Formula: 3t^2 - 2t^3
    """
    t = max(0.0, min(1.0, t))  # clamp
    return t * t * (3.0 - 2.0 * t)
```

### PIPE-07 / PIPE-08: Square-Terrain Assumptions & Rectangular Bugs

**Files with square assumptions:**

| File | Line | Bug | Fix |
|------|------|-----|-----|
| `terrain_chunking.py` | 174 | `grid_cols = total_cols // chunk_size` drops remainder | Use `math.ceil()` or pad remainder into final chunk |
| `environment_scatter.py` | 286 | `terrain_size = max(dims.x, dims.y)` uses single value for both axes | Use `size_x = dims.x; size_y = dims.y` separately |
| `environment_scatter.py` | 290-291 | `_sample()` uses `half_size` (single value) for both U and V mapping | Use separate `half_x` and `half_y` |
| `terrain_advanced.py` | 53 | `_detect_grid_dims` fallback assumes square (`side, side`) | Already has robust path; ensure all callers use it |
| `terrain_advanced.py` | 712 | `res = int(math.sqrt(len(mesh.vertices)))` | Use `_detect_grid_dims` or equivalent |
| `vegetation_system.py` | 346 | `grid_res = int(math.sqrt(len(terrain_vertices)))` | Use separate row/col detection |
| `environment.py` | 71 | `side = max(2, int(math.sqrt(len(bm.verts))))` -- fallback in `_detect_grid_dims` | This IS the fallback -- keep but prefer coordinate-detection path |
| `terrain_advanced.py` (layers) | Multiple | Layer sizing uses `sqrt(vertex_count)` | Use `_detect_grid_dims` |
| Heightmap export | 1175-1181 | `unity_compat=True` resizes to square `target x target` | Compute `target_rows` and `target_cols` independently |
| Road generation | Multiple | Uses X extent for both axes in coordinate conversion | Use `dims.x` for X and `dims.y` for Y separately |

**The `_detect_grid_dims` function (environment.py:51)** already handles non-square terrains correctly via coordinate-set counting. The fix pattern is: ensure all terrain code paths use this function (or equivalent) instead of `sqrt(vert_count)`.

## Common Pitfalls

### Pitfall 1: Breaking `_sample_scene_height` Signature
**What goes wrong:** Changing the function signature or behavior breaks 20+ existing call sites that already use it correctly.
**Why it happens:** Temptation to modify the existing function instead of wrapping it.
**How to avoid:** Create `safe_place_object()` as a NEW wrapper around the EXISTING `_sample_scene_height()`. Do not modify the existing function.
**Warning signs:** Test failures in worldbuilding handlers that currently work.

### Pitfall 2: Animation Smoothstep Breaks Timing
**What goes wrong:** Applying smoothstep to animation `t` values changes the visual timing of all animations.
**Why it happens:** Linear-to-smooth transition changes the rate of change at start/end of animations.
**How to avoid:** This is the INTENDED behavior -- smoothstep creates ease-in-ease-out. But test that animations still look correct (no overshooting, no stalling).
**Warning signs:** Animation keyframe values at t=0 and t=1 must remain unchanged (smoothstep(0)=0, smoothstep(1)=1).

### Pitfall 3: Circular Import When Adding Shared Utils
**What goes wrong:** Creating `_shared_utils.py` that imports from modules that already import from each other.
**Why it happens:** The handlers directory has complex import chains.
**How to avoid:** `_shared_utils.py` must ONLY import from: `bpy`, `bmesh`, `mathutils`, `math`, `logging`, and standard library. It must NOT import from other handler modules. For `_sample_scene_height` access, either move it to `_shared_utils.py` or have `safe_place_object` accept a height-sampling callback.
**Warning signs:** ImportError at addon load time.

### Pitfall 4: Partial Migration Leaves Mixed State
**What goes wrong:** Some files use `safe_place_object()` while others still use `Z=0`. Future developers don't know which pattern is correct.
**Why it happens:** Large number of sites (42+) across 9 files makes it tempting to do partial fixes.
**How to avoid:** Track every instance from the V9 catalog. Mark each as done. Do not leave any Z=0 hardcodings.
**Warning signs:** Any `= 0.0` or `= 0` near placement code that isn't inside a conditional fallback.

### Pitfall 5: `compose_world_map` Pure-Logic Assumption
**What goes wrong:** Calling `compose_world_map()` from async MCP server code and it unexpectedly needs `bpy`.
**Why it happens:** Future modifications might add `bpy` imports to `map_composer.py`.
**How to avoid:** `map_composer.py` header says "NO bpy/bmesh imports. Fully testable without Blender." -- preserve this. The function returns placement data; Blender operations happen in compose_map.
**Warning signs:** Import errors when calling from `blender_server.py` async context.

### Pitfall 6: cap_fill Silently Ignored vs Raising Error
**What goes wrong:** `bmesh.ops.create_circle(bm, cap_fill=True, ...)` may silently ignore the unknown kwarg in some Blender versions rather than raising an error.
**Why it happens:** bmesh.ops may use **kwargs and ignore unknown keys.
**How to avoid:** Always use the documented parameter names: `cap_ends=True` for filled circles, `cap_tris=True` for triangle fills.
**Warning signs:** Circle/cone operations that produce open (unfilled) geometry when they should be capped.

## Code Examples

### Smoothstep Utility
```python
# Source: V9_MASTER_FINDINGS.md Section 19.1 + standard Hermite interpolation
def smoothstep(t: float) -> float:
    """Hermite smoothstep for S-curve interpolation.
    
    Returns 0 for t<=0, 1 for t>=1, smooth transition between.
    Use instead of linear ``t`` for all terrain transitions and animation blending.
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def inverse_smoothstep(t: float) -> float:
    """Inverse of smoothstep -- useful for converting back."""
    t = max(0.0, min(1.0, t))
    return 0.5 - math.sin(math.asin(1.0 - 2.0 * t) / 3.0)
```

### safe_place_object Utility
```python
# Source: V9_MASTER_FINDINGS.md Section 19.1
def safe_place_object(
    x: float,
    y: float,
    terrain_name: str | None,
    water_level: float | None = None,
    bounds: tuple[float, float, float, float] | None = None,
    offset_z: float = 0.02,
) -> tuple[float, float, float] | None:
    """Sample terrain height and validate placement.
    
    Returns (x, y, z) if placement is valid, None if rejected.
    Rejection reasons: below water, outside bounds, no terrain hit.
    """
    z = _sample_scene_height(x, y, terrain_name)
    
    if water_level is not None and z < water_level:
        return None
    
    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        if not (min_x <= x <= max_x and min_y <= y <= max_y):
            return None
    
    return (x, y, z + offset_z)
```

### Blender 4.0+ Node Group Interface
```python
# Source: Blender 4.0 Python API release notes
# OLD (removed in Blender 4.0):
# group.inputs.new("NodeSocketFloat", "Height_A")
# group.outputs.new("NodeSocketFloat", "Result")

# NEW (Blender 4.0+):
group.interface.new_socket(
    name="Height_A",
    in_out='INPUT',
    socket_type='NodeSocketFloat'
)
group.interface.new_socket(
    name="Result",
    in_out='OUTPUT',
    socket_type='NodeSocketFloat'
)
```

### Non-Square Terrain Handling
```python
# Source: environment.py:51 _detect_grid_dims pattern
# WRONG: assumes square
side = int(math.sqrt(len(bm.verts)))
rows, cols = side, side

# RIGHT: detect actual dimensions
xs = set(round(v.co.x, 3) for v in bm.verts)
ys = set(round(v.co.y, 3) for v in bm.verts)
cols, rows = len(xs), len(ys)
if cols * rows != len(bm.verts):
    # Fallback to square only if coordinate detection fails
    side = max(2, int(math.sqrt(len(bm.verts))))
    rows, cols = side, side
```

### Terrain Chunking Remainder Fix
```python
# WRONG: drops remainder rows/cols
grid_cols = max(1, total_cols // chunk_size)
grid_rows = max(1, total_rows // chunk_size)

# RIGHT: include remainder as partial final chunk
grid_cols = max(1, math.ceil(total_cols / chunk_size))
grid_rows = max(1, math.ceil(total_rows / chunk_size))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `group.inputs.new()` | `group.interface.new_socket()` | Blender 4.0 (Nov 2023) | Node group creation crashes on Blender 4.0+ |
| `ShaderNodeTexMusgrave` | `ShaderNodeTexNoise` (merged) | Blender 4.1 (Mar 2024) | Musgrave node type not found error |
| `cap_fill=True` | `cap_ends=True` | Never valid (was always wrong param name) | Circle/cone creation may not fill caps |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pyproject.toml) |
| Config file | `Tools/mcp-toolkit/pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_integration_pipelines.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | _LOC_HANDLERS routes settlement to world_generate_settlement | unit | `pytest tests/test_integration_pipelines.py::TestLocHandlerCoverage -x` | Yes (existing tests check this) |
| PIPE-01 | asset_pipeline handler routes all actions | unit | `pytest tests/test_integration_pipelines.py -x -k "asset_pipeline"` | Partial |
| PIPE-02 | No Z=0 hardcodings remain in handler files | static analysis | `grep -rn "= 0\.0\|= 0$" handlers/ \| grep -v test \| grep -v "#"` | Wave 0 |
| PIPE-03 | No deprecated Blender API calls | static analysis | `grep -rn "group.inputs.new\|group.outputs.new\|ShaderNodeTexMusgrave\|cap_fill" blender_addon/` | Wave 0 |
| PIPE-04 | No Y-axis vertical bugs | static analysis + unit | `grep -rn "\.y.*height\|\.y.*vertical\|\.y.*stack" handlers/` | Wave 0 |
| PIPE-05 | compose_world_map placement used in compose_map | integration | `pytest tests/test_integration_pipelines.py -x -k "compose"` | Wave 0 |
| PIPE-06 | smoothstep utility exists and is used | unit | `pytest tests/ -x -k "smoothstep"` | Wave 0 |
| PIPE-07 | No sqrt(vert_count) for grid dims | static analysis | `grep -rn "sqrt.*vert\|sqrt.*len" handlers/ \| grep -v _detect_grid` | Wave 0 |
| PIPE-08 | Heightmap export preserves rectangular aspect | unit | Wave 0 | Wave 0 |
| TEST-01 | All existing 19,863 tests pass | full suite | `python -m pytest tests/ -x -q` | Yes |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q --tb=short`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_shared_utils.py` -- covers smoothstep(), safe_place_object() utility
- [ ] `tests/test_pipeline_dispatch.py` -- covers PIPE-01 asset_pipeline routing for all actions
- [ ] `tests/test_rectangular_terrain.py` -- covers PIPE-07/PIPE-08 non-square terrain handling
- [ ] Static analysis grep scripts for Z=0, deprecated API, Y-axis bugs

## Key File Inventory

| File | Lines | Role | Changes Needed |
|------|-------|------|---------------|
| `blender_server.py` | 5,482 | MCP server, compose_map pipeline | Fix _LOC_HANDLERS, wire smart planner |
| `handlers/__init__.py` | 1,480 | COMMAND_HANDLERS dispatch | Fix asset_pipeline routing |
| `handlers/worldbuilding.py` | ~7,700 | Settlement/town/castle generation | Fix 11 Z=0 bugs, 3 cap_fill bugs |
| `handlers/worldbuilding_layout.py` | ~700 | Location layout | Fix 18 Z=0 bugs |
| `handlers/map_composer.py` | 1,380 | Smart planner (compose_world_map) | Source of placement logic to merge |
| `handlers/terrain_materials.py` | ~1,600 | Terrain material creation | Fix 5 deprecated API calls |
| `handlers/geometry_nodes.py` | ~200 | GN node type whitelist | Remove ShaderNodeTexMusgrave |
| `handlers/coastline.py` | ~400 | Coastline generation | Fix 6 Z=0 bugs |
| `handlers/terrain_features.py` | ~1,200 | Terrain feature generators | Fix 2 Z=0 bugs, Y-axis bug |
| `handlers/environment_scatter.py` | ~1,600 | Vegetation/prop scatter | Fix 4 Z=0 bugs, square terrain assumption |
| `handlers/vegetation_scatter.py` | ~200 | Vegetation scatter | Fix 2 Z=0 bugs |
| `handlers/rock_scatter.py` | ~100 | Rock scatter | Fix 1 Z=0 bug |
| `handlers/environment.py` | ~1,200 | Terrain generation, heightmap export | Fix heightmap squash bug |
| `handlers/terrain_chunking.py` | ~350 | Terrain chunk splitting | Fix remainder row/col truncation |
| `handlers/terrain_advanced.py` | ~1,700 | Terrain layers, sculpt, advanced ops | Fix square assumptions |
| `handlers/vegetation_system.py` | ~800 | Vegetation system | Fix sqrt grid assumption |
| `handlers/animation_*.py` | Various | Animation keyframing | Replace 35 linear interpolations |
| `handlers/_shared_utils.py` | NEW | Shared utilities | Create smoothstep(), safe_place_object() |

## Open Questions

1. **Parameter shape mismatch audit scope**
   - What we know: V9 documents this as a bug pattern but doesn't enumerate every instance
   - What's unclear: Exact number and locations of all param mismatches
   - Recommendation: During PIPE-01 execution, grep for common param name variations (`name` vs `object_name`, `terrain_name` vs `terrain`) and fix systematically

2. **cap_fill behavior in current Blender**
   - What we know: `cap_fill` is not a documented bmesh.ops parameter; `cap_ends` is correct
   - What's unclear: Whether current Blender silently ignores `cap_fill` or raises an error
   - Recommendation: Fix to `cap_ends=True` regardless -- it's the correct API

3. **Smoothstep vs Smootherstep naming**
   - What we know: V9 calls it "smootherstep" but specifies `t*t*(3-2*t)` which is Hermite smoothstep
   - What's unclear: Whether the project intended the quintic version
   - Recommendation: Use Hermite smoothstep (`3t^2 - 2t^3`) as specified in V9. Name the function `smoothstep()` to match standard terminology. The quintic version (`6t^5 - 15t^4 + 10t^3`) is already used in `_terrain_noise.py` for Perlin fade curves.

## Sources

### Primary (HIGH confidence)
- V9_MASTER_FINDINGS.md Sections 1, 2, 15, 16.10, 16.19, 19.1 -- exact bug locations with file:line
- Codebase analysis -- direct reading of all affected files
- Blender 4.0 Python API release notes -- node group interface change verified
- bmesh.ops documentation -- cap_ends/cap_fill parameter verification

### Secondary (MEDIUM confidence)
- [Blender 4.0 Python API changes](https://developer.blender.org/docs/release_notes/4.0/python_api/) -- group.inputs.new deprecated
- [NodeTreeInterface docs](https://docs.blender.org/api/current/bpy.types.NodeTreeInterface.html) -- new_socket API
- [Creating inputs for node groups in Blender 4.0](https://b3d.interplanety.org/en/creating-inputs-and-outputs-for-node-groups-in-blender-4-0-using-the-python-api/) -- migration guide

### Tertiary (LOW confidence)
- ShaderNodeTexMusgrave deprecation in Blender 4.1 -- based on training data, not verified against release notes

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all changes are to existing codebase, no new dependencies
- Architecture: HIGH -- pipeline structure fully analyzed, both paths read in detail
- Pitfalls: HIGH -- based on actual codebase patterns and import chains
- Bug locations: HIGH -- V9 53-agent audit provides exact file:line references, cross-verified by direct codebase reading

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- internal codebase changes only, no external dependencies)
