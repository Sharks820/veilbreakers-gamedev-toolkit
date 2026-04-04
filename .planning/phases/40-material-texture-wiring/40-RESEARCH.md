# Phase 40: Material & Texture Wiring - Research

**Researched:** 2026-04-04
**Domain:** Blender procedural material pipeline, PBR node graphs, terrain splatmap materials
**Confidence:** HIGH

## Summary

Phase 40 addresses the most visible quality gap in the entire toolkit: 90%+ of generated assets render as default white/grey because the material library (52 materials + 6 procedural generators) exists but is never called after mesh generation. The code path for auto-assignment exists in `_mesh_bridge.py:mesh_from_spec()` via `CATEGORY_MATERIAL_MAP`, but it silently catches all exceptions, and many worldbuilding generators bypass `mesh_from_spec` entirely. Additionally, the HeightBlend node group uses deprecated Blender 4.0+ API (`group.inputs.new()`), 14 biome palettes exist but only the V2 splatmap version is actively wired, castle roughness textures bake as ALL BLACK, and curvature-driven wear/weathering exists in `weathering.py` but is never called post-generation.

The material infrastructure is excellent -- the hardest code is already written. This phase is almost entirely **wiring**, not new code. The primary work is: (1) ensure every generator path ends with material assignment, (2) fix the HeightBlend deprecated API, (3) create the missing wet rock material, (4) add curvature wear and micro-detail normal injection as post-processing steps, (5) enforce dark fantasy palette validation, and (6) fix material duplication on repeated terrain runs.

**Primary recommendation:** Wire `_assign_procedural_material()` or `create_procedural_material()` at every exit point where meshes are created, then fix HeightBlend API and create wet rock material. Do NOT build new material systems -- everything needed already exists.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MAT-01 | Wire material library into ALL generators post-mesh | CATEGORY_MATERIAL_MAP + mesh_from_spec auto-assign exists but silently fails; worldbuilding generators have `_assign_procedural_material()` but many paths skip it |
| MAT-02 | Fix 6 material creation sites that never set Base Color | 3 of 6 were fixed in v8.0; remaining sites in environment_scatter.py line 882 (grass mat), and any new material created via `bpy.data.materials.new()` without color |
| MAT-03 | Wire HeightBlend node group into biome terrain materials | `_create_height_blend_group()` at terrain_materials.py:1520 uses deprecated `group.inputs.new()` API (Blender 4.0+ crash); `height_blend()` pure logic at line 1480 works; node group never called from `create_biome_terrain_material()` |
| MAT-04 | Wire 14 biome palettes (BIOME_PALETTES_V2) into terrain generation | `BIOME_PALETTES_V2` defined at terrain_materials.py:1813 with all 14 biomes; `create_biome_terrain_material()` at line 2055 consumes them; compose_map Step 6 calls `terrain_create_biome_material` but only when biome param is set |
| MAT-05 | Fix castle roughness textures (ALL BLACK) | V9 finding: texture bake step generates blank black images; the material roughness values are correct in code but the bake output overrides them |
| MAT-06 | Create wet rock material | Referenced as material zone in terrain_features.py (lines 118-119, 299-300) and coastline.py (line 37) but never created as actual procedural material in MATERIAL_LIBRARY |
| MAT-07 | Add curvature-driven wear to all materials | `weathering.py` has `apply_edge_wear()` (convex), `apply_dirt_accumulation()` (concave), `apply_moss_growth()`, `apply_rain_staining()` -- all exist but never called post-generation |
| MAT-08 | Add micro-detail normal maps | `_build_normal_chain()` at procedural_materials.py:910 already builds 3-layer micro/meso/macro normal chain; material library entries already have `micro_normal_strength`, `meso_normal_strength`, `macro_normal_strength` params -- need to verify all builders call it |
| MAT-09 | Enforce dark fantasy palette (Saturation <40%, Value 10-50%) | Palette constants defined in procedural_materials.py:36-53; test_procedural_materials.py has HSV validation; need runtime enforcement on all color inputs |
| MAT-10 | Fix terrain material duplication on repeated runs | `create_biome_terrain_material()` always creates new `bpy.data.materials.new()` at line 2071; no dedup check like `bpy.data.materials.get()` before creation |
| TEST-04 | Opus verification scan after phase | Standard protocol: scan, fix, rescan until CLEAN |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

### From CLAUDE.md
- **Always verify visually** after Blender mutations -- use `blender_viewport action=contact_sheet`
- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export (materials are part of texture step)
- **Game readiness**: Run `blender_mesh action=game_check` before export
- **Batch when possible**: Use batch processing for bulk material assignment
- **Context7 first** for library/framework questions
- **Episodic Memory** before starting non-trivial tasks
- **Bug scan rounds until CLEAN** -- never stop after one round

### From V9 Decisions
- All future work goes through compose_map (no new orchestration paths)
- v10.0: PIPE must go first (Phase 39 prerequisite for Phase 40)
- After EVERY phase: Opus scan -> fix -> rescan -> repeat until CLEAN

## Standard Stack

### Core (Already Present)
| Library | Location | Purpose | Status |
|---------|----------|---------|--------|
| `procedural_materials.py` | `handlers/procedural_materials.py` (1837 lines) | 52 named materials + 6 procedural generators (stone/wood/metal/organic/terrain/fabric) | EXISTS, not wired to most generators |
| `terrain_materials.py` | `handlers/terrain_materials.py` (2202 lines) | 14 biome palettes, HeightBlend, splatmap vertex colors, biome terrain materials | EXISTS, HeightBlend is dead code |
| `_mesh_bridge.py` | `handlers/_mesh_bridge.py` | CATEGORY_MATERIAL_MAP + mesh_from_spec auto-assign | EXISTS, silently catches errors |
| `weathering.py` | `handlers/weathering.py` | Edge wear, dirt, moss, rain staining, corruption veins | EXISTS, never called post-generation |
| `materials.py` | `handlers/materials.py` (99 lines) | Simple material CRUD handlers | EXISTS |
| `_build_normal_chain()` | `procedural_materials.py:910` | 3-layer micro/meso/macro normal chain | EXISTS, used by all 6 builders |

### No New Dependencies Required
This phase uses only existing Blender Python API (`bpy`, `bmesh`, `mathutils`). No pip installs needed.

## Architecture Patterns

### Material System Architecture (Current)
```
MATERIAL_LIBRARY (52 entries)          BIOME_PALETTES_V2 (14 biomes)
    |                                       |
    v                                       v
GENERATORS dict (6 builders)          create_biome_terrain_material()
    |                                       |
    v                                       v
create_procedural_material()          auto_assign_terrain_layers()
    |                                       |
    v                                       v
bpy.data.materials.new() + node graph  Vertex color splatmap + MixShader
```

### Generator -> Material Pipeline (Pattern 1: mesh_from_spec)
```
Pure-logic generator (weapon_quality, procedural_meshes, armor_meshes, etc.)
    |-- returns MeshSpec dict with metadata.category
    v
mesh_from_spec() in _mesh_bridge.py
    |-- reads spec.metadata.category
    |-- looks up CATEGORY_MATERIAL_MAP[category]
    |-- calls create_procedural_material(name, material_key)
    |-- assigns to obj.data.materials
    v
Blender object with procedural material
```
**Used by:** `_build_quality_object()` for weapons/armor/props, and worldbuilding.py for some items.

### Generator -> Material Pipeline (Pattern 2: Direct worldbuilding)
```
Worldbuilding handler (building, castle, dungeon, encounter, etc.)
    |-- creates Blender objects directly (not via MeshSpec)
    |-- may or may not call _assign_procedural_material()
    v
_assign_procedural_material(obj, material_key)
    |-- reuses or creates procedural material
    |-- assigns to obj.data.materials[0]
    v
Blender object with procedural material
```
**Used by:** `handle_generate_building()`, `handle_generate_castle()`.

### Pattern 3: Terrain Materials
```
compose_map Step 6
    |-- sends "terrain_create_biome_material" command
    v
handle_create_biome_terrain(params)
    |-- calls create_biome_terrain_material(biome_name, object_name)
    |-- builds 4-layer MixShader graph (ground/slope/cliff/special)
    |-- paints vertex color splatmap
    v
Terrain mesh with splatmap-blended material
```

### Anti-Patterns to Avoid
- **Silent exception swallowing:** `_mesh_bridge.py:1041` catches ALL exceptions with `pass`. Log the error at minimum.
- **Creating materials without dedup:** `create_biome_terrain_material()` always creates new materials. Must check `bpy.data.materials.get()` first.
- **Using `group.inputs.new()` API:** Removed in Blender 4.0. Must use `group.interface.new_socket()`.
- **Hardcoding colors without palette validation:** All colors must pass saturation <40%, value 10-50% check.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Procedural PBR materials | New material creation functions | `create_procedural_material(name, key)` from procedural_materials.py | 52 presets + 6 builders already handle all cases |
| Material assignment to objects | Direct `bpy.data.materials.new()` | `_assign_procedural_material(obj, key)` from worldbuilding.py | Handles dedup, error recovery, mat slot management |
| Terrain material blending | Custom shader blending | `create_biome_terrain_material(biome, obj_name)` from terrain_materials.py | 4-layer splatmap with vertex colors already built |
| Edge wear/weathering | Custom vertex color painting | `handle_apply_weathering()` from weathering.py | Full pipeline: edge wear + dirt + moss + rain + corruption |
| Normal detail chains | Manual bump node creation | `_build_normal_chain()` from procedural_materials.py | 3-layer micro/meso/macro already parameterized |
| Category->material mapping | New lookup tables | `CATEGORY_MATERIAL_MAP` from _mesh_bridge.py | 35+ categories already mapped |
| Color validation | Manual RGB checks | `_rgb_to_hsv()` from test_procedural_materials.py | Verified HSV conversion for sat/value checking |

**Key insight:** 95% of this phase is calling existing functions from the right places, not writing new material code.

## Common Pitfalls

### Pitfall 1: Silent Exception Swallowing in mesh_from_spec
**What goes wrong:** Material assignment fails silently due to bare `except Exception: pass` at `_mesh_bridge.py:1041`.
**Why it happens:** Original code prioritized "never crash" over "always material".
**How to avoid:** Change to `except Exception as e: logger.warning(...)` and add a fallback flat-color material assignment if procedural fails.
**Warning signs:** Objects render white in viewport despite having `metadata.category` set.

### Pitfall 2: HeightBlend Deprecated API Crash
**What goes wrong:** `_create_height_blend_group()` at terrain_materials.py:1560-1578 uses `group.inputs.new("NodeSocketFloat", "Height_A")` and `group.outputs.new(...)` which crash in Blender 4.0+.
**Why it happens:** Code was written for Blender 3.x API. In 4.0+, node group sockets use `group.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocketFloat')`.
**How to avoid:** Replace all 5 occurrences (4 inputs + 1 output) with `group.interface.new_socket()`. Also update `group.inputs[name].default_value` to `group.interface.items_tree[name].default_value`.
**Warning signs:** `AttributeError: 'ShaderNodeTree' has no attribute 'inputs'` when node group creation is attempted.

### Pitfall 3: Material Duplication on Repeated Runs
**What goes wrong:** Running compose_map twice creates duplicate materials (e.g., "VB_Terrain_thornwood_forest", "VB_Terrain_thornwood_forest.001").
**Why it happens:** `create_biome_terrain_material()` at line 2071 always calls `bpy.data.materials.new()` without checking for existing material.
**How to avoid:** Add `existing = bpy.data.materials.get(mat_name); if existing: return existing` check before creation. Also add to `_assign_procedural_material()`.
**Warning signs:** Growing material count in `.blend` file on repeated pipeline runs.

### Pitfall 4: Worldbuilding Generators Bypassing mesh_from_spec
**What goes wrong:** Many worldbuilding generators create Blender objects directly (via bmesh or primitives) and never call material assignment.
**Why it happens:** Building/castle/dungeon generators predate the mesh_from_spec pattern. They construct geometry inline with bmesh.
**How to avoid:** Add `_assign_procedural_material(obj, material_key)` calls after EVERY object creation in worldbuilding handlers. Use the existing `_assign_procedural_material_recursive()` for parent objects with children.
**Warning signs:** Generated buildings/castles/dungeons appear all-white in viewport.

### Pitfall 5: Castle Roughness ALL BLACK
**What goes wrong:** Castle roughness textures are all black (value 0.0 = perfect mirror surface).
**Why it happens:** Per V9 findings: "the TEXTURE CREATION step generates blank black images, not that materials aren't assigned". The bake pipeline produces black roughness maps.
**How to avoid:** This is likely in the texture baking code. The fix is to either: (a) skip roughness bake and use procedural roughness from the material node graph, or (b) fix the bake setup to use correct roughness pass. Since we're wiring procedural materials, the roughness comes from the node graph -- the bake step is a downstream concern (Phase 46).
**Warning signs:** Objects appear mirror-like despite high roughness values in material definition.

### Pitfall 6: Biome Parameter Name Mismatch
**What goes wrong:** Multi-biome terrain handler passes `name` but the handler reads `object_name`.
**Why it happens:** V9 finding: "the live multi-biome call passes `name` while the handler reads `object_name`".
**How to avoid:** Ensure compose_map Step 6 passes `object_name` (not `name`) to `terrain_create_biome_material` command. Current code at blender_server.py:3073 looks correct (`"object_name": terrain_name`), but verify the Blender addon handler side too.
**Warning signs:** Material created successfully but never assigned to terrain object.

## Code Examples

### Example 1: Correct Material Assignment via _assign_procedural_material
```python
# Source: worldbuilding.py:174-190
def _assign_procedural_material(obj, material_key):
    """Assign a procedural material from MATERIAL_LIBRARY to a Blender object."""
    try:
        mat_name = f"{obj.name}_{material_key}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = create_procedural_material(mat_name, material_key)
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        return True
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug("Material assignment failed for %s (%s): %s",
                      getattr(obj, "name", "<unnamed>"), material_key, exc)
        return False
```

### Example 2: Correct HeightBlend Node Group (Blender 4.0+ API)
```python
# FIX: Replace group.inputs.new() with group.interface.new_socket()
# BEFORE (Blender 3.x, crashes in 4.0+):
group.inputs.new("NodeSocketFloat", "Height_A")
group.inputs["Height_A"].default_value = 0.5

# AFTER (Blender 4.0+):
group.interface.new_socket(
    name="Height_A",
    in_out='INPUT',
    socket_type='NodeSocketFloat',
)
# Access default via items_tree
for item in group.interface.items_tree:
    if item.name == "Height_A" and item.in_out == 'INPUT':
        item.default_value = 0.5
```

### Example 3: Material Deduplication Pattern
```python
# Source: Pattern from environment.py:598 (correct approach)
mat_name = f"VB_Terrain_{biome_name}"
mat = bpy.data.materials.get(mat_name)
if mat is None:
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    # ... build node graph ...
# Always reuse existing material
```

### Example 4: Adding Wet Rock Material to MATERIAL_LIBRARY
```python
# Add to MATERIAL_LIBRARY in procedural_materials.py
# Uses Lagarde wet-rock PBR formulas (referenced in V9 water research)
"wet_rock": {
    "base_color": (0.08, 0.07, 0.06, 1.0),   # Darker when wet
    "roughness": 0.15,                           # Very smooth when wet
    "roughness_variation": 0.08,
    "metallic": 0.0,
    "normal_strength": 1.6,
    "detail_scale": 6.0,
    "wear_intensity": 0.3,
    "node_recipe": "stone",
    "micro_normal_strength": 0.3,
    "meso_normal_strength": 0.8,
    "macro_normal_strength": 1.2,
},
```

### Example 5: Curvature Wear Post-Processing Call
```python
# Source: weathering.py provides the pure-logic compute functions
# This is the pattern for calling weathering after object creation:
from .weathering import handle_apply_weathering

handle_apply_weathering({
    "object_name": obj.name,
    "preset": "medium",       # or "light", "heavy", "ancient", "corrupted"
    "edge_wear": 0.5,
    "dirt": 0.3,
    "moss": 0.2,
    "rain": 0.15,
})
```

## Key Files Map

| File | Lines | Role in Phase 40 |
|------|-------|-------------------|
| `handlers/procedural_materials.py` | 1837 | MATERIAL_LIBRARY (52 entries), GENERATORS (6 builders), create_procedural_material(), _build_normal_chain() |
| `handlers/terrain_materials.py` | 2202 | BIOME_PALETTES_V2 (14 biomes), _create_height_blend_group() (DEAD CODE), create_biome_terrain_material(), auto_assign_terrain_layers() |
| `handlers/_mesh_bridge.py` | 1052 | CATEGORY_MATERIAL_MAP (35+ categories), mesh_from_spec() with auto-material |
| `handlers/worldbuilding.py` | ~8000 | _assign_procedural_material(), _assign_procedural_material_recursive(), 15+ generator handlers |
| `handlers/weathering.py` | ~400 | apply_edge_wear(), apply_dirt_accumulation(), apply_moss_growth(), apply_rain_staining() |
| `handlers/environment.py` | ~1100 | handle_paint_terrain(), handle_create_road(), handle_create_water() |
| `handlers/environment_scatter.py` | ~1700 | Vegetation/prop scatter with material presets |
| `handlers/materials.py` | 99 | Simple material CRUD (handle_material_create/assign/modify/list) |
| `handlers/weapon_quality.py` | 3090 | Pure-logic weapon generators (6 types), all set category="weapon" |
| `handlers/armor_meshes.py` | ~1900 | Pure-logic armor generators (10 types), all set category="armor" |
| `handlers/building_quality.py` | ~1500 | Pure-logic building generators (9 types), set material_ids for multi-material |
| `handlers/riggable_objects.py` | ~1200 | Pure-logic prop generators (door/chain/flag/chest/drawbridge) |
| `handlers/clothing_system.py` | ~1300 | Clothing generators with material_regions metadata |
| `handlers/creature_anatomy.py` | ~800 | Creature generators (need category verification) |
| `handlers/__init__.py` | ~1500 | Handler dispatch, _build_quality_object(), COMMAND_HANDLERS dict |
| `src/veilbreakers_mcp/blender_server.py` | 5482 | compose_map pipeline (Step 6 = biome paint), MCP tool dispatch |

## Detailed Findings Per Requirement

### MAT-01: Wire Material Library into ALL Generators

**Current state:** CATEGORY_MATERIAL_MAP has 35+ category->material mappings. mesh_from_spec auto-assigns if category is set. BUT:

1. **Generators that DO set category and go through mesh_from_spec:** weapon_quality (6 types), armor_meshes (10 types), procedural_meshes (60+ types) -- these SHOULD work but the silent exception catch may hide failures
2. **Generators that create objects directly (bypass mesh_from_spec):** worldbuilding.py building/castle/dungeon generators -- these need explicit `_assign_procedural_material()` calls
3. **Generators missing category metadata:** riggable_objects.py (no `"category"` key found in grep), creature_anatomy.py (no category found)

**Action required:**
- Audit every generator handler in __init__.py COMMAND_HANDLERS
- For mesh_from_spec path: fix silent exception to log + add fallback
- For direct creation path: add `_assign_procedural_material()` calls
- For missing categories: add `category` to metadata in pure-logic generators

### MAT-02: Fix Sites Never Setting Base Color

**v8.0 fix history (from memory):** 3 of 6 original sites were fixed:
1. FIXED: `_terrain_noise.py BIOME_RULES` -- added base_color
2. FIXED: `environment.py handle_paint_terrain` -- reads base_color from rules
3. FIXED: `environment_scatter.py` breakable props -- pull from presets

**Remaining sites to audit:**
- `environment_scatter.py:882` -- grass material creation (verified: does set Base Color at line 887)
- `worldbuilding.py:7897` -- corruption material (verified: does set Base Color at line 7902)
- Any NEW material created via plain `bpy.data.materials.new()` + `use_nodes = True` without explicit Base Color

**Action:** Full grep audit of `bpy.data.materials.new()` across all handlers, verify each sets Base Color.

### MAT-03: Wire HeightBlend Node Group

**Location:** `terrain_materials.py:1520-1631`
**Bug:** Lines 1560-1563 use `group.inputs.new("NodeSocketFloat", ...)` which crashes Blender 4.0+
**Fix:** Replace with `group.interface.new_socket(name=..., in_out='INPUT', socket_type='NodeSocketFloat')`
**Integration:** HeightBlend is never called from `create_biome_terrain_material()`. Need to insert HeightBlend node group between each layer's shader and the MixShader nodes, using noise texture height output as the blend height inputs.

### MAT-04: Wire BIOME_PALETTES_V2

**Location:** `terrain_materials.py:1813-1898`
**Status:** 14 biomes defined with 4 layers each (ground/slope/cliff/special)
**Current wiring:** compose_map Step 6 (blender_server.py:3073) calls `terrain_create_biome_material` with biome_name -- this IS wired
**Gap:** Only called when `spec.get("biome")` is set. Some generation paths may not pass biome name. Need to ensure default biome fallback.

### MAT-05: Castle Roughness ALL BLACK

**Root cause per V9:** "the TEXTURE CREATION step generates blank black images, not that materials aren't assigned"
**Analysis:** If we wire procedural materials from MATERIAL_LIBRARY, the roughness comes from the node graph (e.g., `build_stone_material()` creates roughness noise variation). The ALL BLACK issue is in the texture BAKE step, not the material definition.
**Fix approach:** (a) Ensure castle objects get procedural materials (which have correct roughness in node graph), (b) the bake fix is Phase 46 scope, but we should validate castle material roughness values are non-zero after assignment.

### MAT-06: Create Wet Rock Material

**Current state:** Referenced as material zone string in:
- `terrain_features.py:118-119` (canyon_floor, canyon_wall, **wet_rock**, canyon_ledge)
- `terrain_features.py:299-300` (cliff_rock, **wet_rock**, pool_bottom, ledge_stone, moss)
- `coastline.py:37` (rock, **wet_rock**, gravel, water_edge)

But "wet_rock" does NOT exist in MATERIAL_LIBRARY or TERRAIN_MATERIALS.

**Implementation:** Add to MATERIAL_LIBRARY with Lagarde wet-rock PBR formula: darken base color 30%, reduce roughness by 60%, increase normal strength. Based on dry `cliff_rock` material as starting point.

### MAT-07: Curvature-Driven Wear

**Current state:** `weathering.py` has full pipeline:
- `apply_edge_wear()` -- convex edge wear mask
- `apply_dirt_accumulation()` -- concave crevice dirt
- `apply_moss_growth()` -- upward-facing moss
- `apply_rain_staining()` -- vertical rain streaks
- WEATHERING_PRESETS: "light", "medium", "heavy", "ancient", "corrupted"

**Gap:** `handle_apply_weathering()` exists but is never called from any generator pipeline.

**Fix:** Add weathering call after material assignment in compose_map pipeline. Could be a new Step 6.5 between biome paint and vegetation scatter.

### MAT-08: Micro-Detail Normal Maps

**Current state:** `_build_normal_chain()` at procedural_materials.py:910 ALREADY implements 3-layer normals:
- Micro (scale 40-80): fine pores/scratches
- Meso (scale 10-20): cracks/veins
- Macro (scale 2-5): large undulation

All 6 builders (stone/wood/metal/organic/terrain/fabric) call `_build_normal_chain()`.
All 52 MATERIAL_LIBRARY entries have `micro_normal_strength`, `meso_normal_strength`, `macro_normal_strength` params.

**Gap:** The normal chain is built INSIDE the procedural material -- so if a generator doesn't get a procedural material, it has no normals. This is the same wiring issue as MAT-01.

**Additional enhancement:** Consider adding a Geometry Pointiness node (Blender's built-in curvature approximation) as a 4th micro-detail layer for extra surface realism.

### MAT-09: Dark Fantasy Palette Enforcement

**Current state:** Constants defined in procedural_materials.py:
- Saturation NEVER exceeds 40%
- Value range 10-50%
- Existing tests in `test_procedural_materials.py` validate this for MATERIAL_LIBRARY entries

**Gap:** No runtime enforcement when generators create materials outside MATERIAL_LIBRARY. Need a validation function that clamps/warns on out-of-range colors.

**Implementation:** Add `validate_dark_fantasy_color(r, g, b) -> (r, g, b)` utility that clamps saturation and value to acceptable range. Call from `create_procedural_material()` and `_assign_procedural_material()`.

### MAT-10: Material Duplication Fix

**Bug location:** `create_biome_terrain_material()` at terrain_materials.py:2071:
```python
mat = bpy.data.materials.new(name=f"VB_Terrain_{biome_name}")  # Always creates new!
```

**Also in:** `_assign_procedural_material()` at worldbuilding.py:179-182 -- DOES check `bpy.data.materials.get(mat_name)` first (correct pattern).

**Fix:** Add dedup check to `create_biome_terrain_material()`:
```python
mat_name = f"VB_Terrain_{biome_name}"
existing = bpy.data.materials.get(mat_name)
if existing is not None:
    # Optionally update vertex colors on object
    if object_name:
        # ... assign existing mat and repaint splatmap ...
    return existing
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `group.inputs.new()` | `group.interface.new_socket()` | Blender 4.0 (2023-11) | HeightBlend node group crashes |
| `mat.node_tree.nodes["Principled BSDF"]` | Same (still valid) | Blender 4.0+ | No change needed |
| `mesh.vertex_colors` | `mesh.color_attributes` | Blender 3.4+ | Code already updated |
| Musgrave Texture node | Noise Texture node | Blender 4.1+ | Code already updated |
| `calc_normals_split()` | `calc_normals()` | Blender 4.1+ | Code has compat check |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && uv run pytest tests/test_procedural_materials.py tests/test_terrain_materials.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAT-01 | Every CATEGORY_MATERIAL_MAP key has matching MATERIAL_LIBRARY entry | unit | `uv run pytest tests/test_procedural_materials.py -x -q` | Yes |
| MAT-01 | Every generator sets metadata.category | unit | `uv run pytest tests/test_aaa_materials.py -x -q` | Yes (partial) |
| MAT-02 | All material creation sites set Base Color | unit | `uv run pytest tests/test_procedural_materials.py::test_all_entries_have_base_color -x` | Yes (partial) |
| MAT-03 | HeightBlend node group uses 4.0+ API | unit | New test needed | No -- Wave 0 |
| MAT-04 | All 14 biomes have valid palettes | unit | `uv run pytest tests/test_terrain_materials.py -x -q` | Yes |
| MAT-05 | Castle roughness > 0 after material assignment | unit | New test needed | No -- Wave 0 |
| MAT-06 | wet_rock exists in MATERIAL_LIBRARY | unit | `uv run pytest tests/test_procedural_materials.py::test_library_minimum_count -x` | Implicit |
| MAT-07 | Weathering functions produce valid vertex masks | unit | New test needed for integration | Partial in test_procedural_materials |
| MAT-08 | All builders call _build_normal_chain | unit | `uv run pytest tests/test_procedural_materials.py -x -q` | Implicit |
| MAT-09 | All MATERIAL_LIBRARY colors pass dark fantasy validation | unit | `uv run pytest tests/test_procedural_materials.py::test_dark_fantasy_palette_compliance -x` | Yes |
| MAT-10 | Repeated biome material creation reuses existing | unit | New test needed | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && uv run pytest tests/test_procedural_materials.py tests/test_terrain_materials.py tests/test_aaa_materials.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_height_blend_api.py` -- covers MAT-03 (HeightBlend uses interface.new_socket)
- [ ] `tests/test_material_dedup.py` -- covers MAT-10 (terrain material not duplicated)
- [ ] `tests/test_castle_roughness.py` -- covers MAT-05 (roughness values non-zero)
- [ ] `tests/test_wet_rock_material.py` -- covers MAT-06 (wet_rock in MATERIAL_LIBRARY)
- [ ] `tests/test_weathering_integration.py` -- covers MAT-07 (weathering called post-generation)

## Open Questions

1. **Castle roughness root cause**
   - What we know: Roughness values in code are correct (0.6-0.85 range), but baked textures are all black
   - What's unclear: Whether this is a bake setup bug, wrong bake pass type, or missing UV issue
   - Recommendation: For Phase 40, wire procedural materials (which have correct roughness in node graph). The bake fix is Phase 46 EXPORT scope. Validate that procedural material roughness is visually correct.

2. **Which generators still create white objects after mesh_from_spec fix?**
   - What we know: mesh_from_spec has auto-assign but silently catches errors
   - What's unclear: Exact failure mode -- is it import error, missing category, or material creation crash?
   - Recommendation: Fix the silent catch to log errors, then run full generator suite and collect failure list.

3. **Should weathering be opt-in or automatic?**
   - What we know: handle_apply_weathering() exists with presets
   - What's unclear: Performance impact on large scenes, user preference
   - Recommendation: Make it automatic with "medium" preset in compose_map pipeline, add override param to skip.

## Sources

### Primary (HIGH confidence)
- `handlers/procedural_materials.py` -- MATERIAL_LIBRARY (52 entries), 6 builder functions, create_procedural_material()
- `handlers/terrain_materials.py` -- BIOME_PALETTES_V2 (14 biomes), HeightBlend dead code, create_biome_terrain_material()
- `handlers/_mesh_bridge.py` -- CATEGORY_MATERIAL_MAP (35+ mappings), mesh_from_spec auto-assign
- `handlers/worldbuilding.py` -- _assign_procedural_material(), _assign_procedural_material_recursive()
- `handlers/weathering.py` -- Edge wear/dirt/moss/rain/corruption pipeline
- `.planning/V9_MASTER_FINDINGS.md` -- Section 10 (Materials), Section 17.10 (Universal failures), Section 18.1 (Wiring readiness)
- `memory/project_material_color_bug.md` -- v8.0 Base Color fix history

### Secondary (MEDIUM confidence)
- Blender 4.0 release notes (node group interface API change) -- geometry_nodes.py in codebase uses the new API, confirming pattern
- V9 finding: "TEXTURE CREATION step generates blank black images" for castle roughness

### Tertiary (LOW confidence)
- Exact count of generators that bypass mesh_from_spec -- estimated ~15 in worldbuilding.py, needs runtime verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all code examined directly in codebase
- Architecture: HIGH - complete material pipeline traced from library definition to assignment
- Pitfalls: HIGH - all issues verified against actual code and V9 findings
- HeightBlend API fix: HIGH - Blender 4.0+ API confirmed by geometry_nodes.py usage
- Castle roughness: MEDIUM - root cause documented in V9 but not verified against bake code

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- Blender API changes only at major versions)
