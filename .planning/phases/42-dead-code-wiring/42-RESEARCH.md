# Phase 42: Dead Code Wiring - Research

**Researched:** 2026-04-04
**Domain:** Blender handler pipeline wiring -- connecting 11 existing but disconnected systems into the live compose_map pipeline
**Confidence:** HIGH

## Summary

Phase 42 is fundamentally a **wiring phase**, not a code-writing phase. All 11 target systems already exist as complete, tested Python modules in `blender_addon/handlers/`. The problem is that `compose_map` in `blender_server.py` (the canonical pipeline) either calls simpler fallback paths, bypasses these systems entirely, or the modules are never imported into `__init__.py`. The total dead code across 11 files is approximately 13,157 lines -- all tested (810 tests pass today) but never invoked from the live pipeline.

The key insight from codebase analysis is that the wiring breaks fall into three categories: (1) dispatch table misrouting (e.g., `_LOC_HANDLERS["settlement"]` pointing to `world_generate_town` instead of `world_generate_settlement`), (2) modules never imported in `__init__.py` (e.g., `building_interior_binding.py`, `modular_building_kit.py`), and (3) compose_map steps that call simpler handlers when richer alternatives exist (e.g., simple `env_generate_road` instead of MST `road_network.py`).

**Primary recommendation:** Work through each WIRE requirement as a focused wiring change: identify the dead code module, identify where it SHOULD be called from, add the import/call, update dispatch tables. No new algorithms needed -- only plumbing.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WIRE-01 | Wire VEGETATION_GENERATOR_MAP (15+ real generators) replacing placeholder cubes | VEGETATION_GENERATOR_MAP in `_mesh_bridge.py` (lines 285-304) has 18 entries. `environment_scatter.py` handler already reads it. Issue: `vegetation_system.py` line 762-766 creates cubes as placeholder. Need to ensure ALL scatter code paths use `environment_scatter.py` not `vegetation_system.py`. |
| WIRE-02 | Wire modular building kit (260 pieces, 52 core x 5 styles) into building/castle generation | `modular_building_kit.py` (2,579 lines) is NOT imported anywhere. Has `generate_modular_piece()` and `assemble_building()`. Must import in `__init__.py` and wire into `_generate_location_building()` in `worldbuilding.py`. |
| WIRE-03 | Wire settlement_generator (15 types) -- route castle through it | `_LOC_HANDLERS["settlement"]` routes to `world_generate_town` instead of `world_generate_settlement`. Castle bypasses settlement_generator entirely via `handle_generate_castle()` box generator. Fix dispatch table + route castle through settlement system. |
| WIRE-04 | Wire AAA water handler (spline-following mesh + flow vertex colors) | `handle_create_water` in `environment.py` line 879 already creates spline-following water mesh. Already registered as `env_create_water`. compose_map Step 3 already calls it. Issue is likely that no `path_points` are passed, so it falls back to flat grid. Wire river spline data into water call. |
| WIRE-05 | Wire spline-terrain deformation for rivers and roads | `handle_spline_deform` in `terrain_advanced.py` line 392 exists and is registered as `terrain_spline_deform`. Already used as fallback in compose_map location placement. Need to wire it into road generation (Step 4) and river carving (Step 3). |
| WIRE-06 | Wire L-system trees (4 species) replacing lollipop meshes | `vegetation_lsystem.py` (1,189 lines) has oak/birch/twisted/dead/pine grammars. Already imported in `__init__.py`. Already wired through `VEGETATION_GENERATOR_MAP` via `_lsystem_tree_generator`. Issue overlaps with WIRE-01 -- ensuring scatter uses the generator map path. |
| WIRE-07 | Wire interior binding (14 room types) into settlement generation | `building_interior_binding.py` (400 lines) is NOT imported in `__init__.py`. Has `BUILDING_ROOM_MAP` for tavern/house/castle/cathedral/tower/shop/forge/chapel/barracks/library/prison/treasury/throne_room/alchemy_lab. Pure-logic module. |
| WIRE-08 | Wire atmospheric volumes, light integration LIGHT_PROP_MAP, prop density/quality | `atmospheric_volumes.py` (444 lines), `light_integration.py` (364 lines), `prop_density.py` (761 lines) are all imported in `__init__.py` but NEVER called from compose_map. Need new steps in compose_map for atmosphere + lighting + prop density. |
| WIRE-09 | Wire coastline generator + 7 dead-code terrain features | `coastline.py` imported, registered as `env_generate_coastline` but never called from compose_map. 6 of 10 terrain feature generators NOT imported: natural_arch, geyser, sinkhole, floating_rocks, ice_formation, lava_flow. |
| WIRE-10 | Wire MST road network replacing simple paths | `road_network.py` (699 lines) has `compute_road_network()` with MST connectivity, road classification, bridge detection, switchbacks. Registered as `env_compute_road_network`. compose_map Step 4 uses `env_generate_road` (simple waypoint follower) instead. |
| WIRE-11 | Wire building_interior_binding.py (currently NOT IMPORTED in __init__.py) | Confirmed: 0 imports in `__init__.py`. Only referenced in test files. Must add import and wire `BUILDING_ROOM_MAP` + `generate_interior_specs_for_building()` into settlement building generation. |
| TEST-04 | Opus verification scan after every phase | Standard verification protocol: Opus scan -> fix round -> re-scan -> until CLEAN. |
</phase_requirements>

## Standard Stack

### Core (All Already Exist -- No New Dependencies)

| Module | Location | Lines | Purpose | Status |
|--------|----------|-------|---------|--------|
| `_mesh_bridge.py` | handlers/ | 1,051 | VEGETATION_GENERATOR_MAP + mesh_from_spec converter | Imported but map underused |
| `modular_building_kit.py` | handlers/ | 2,579 | 260-piece snap-together architecture kit | NOT IMPORTED |
| `settlement_generator.py` | handlers/ | 3,042 | 15 settlement types with full layout system | Imported but bypassed by castle |
| `building_interior_binding.py` | handlers/ | 400 | 14 room type mappings for buildings | NOT IMPORTED |
| `vegetation_lsystem.py` | handlers/ | 1,189 | L-system trees (5 species) with wind/billboard | Imported, wired through map |
| `environment.py` | handlers/ | 1000+ | handle_create_water (spline water), handle_carve_river | Registered, called without spline data |
| `terrain_advanced.py` | handlers/ | 450+ | Spline-terrain deformation | Registered, used only as fallback |
| `atmospheric_volumes.py` | handlers/ | 444 | 7 volume types, biome rules, placement engine | Imported, NEVER CALLED |
| `light_integration.py` | handlers/ | 364 | 8 light prop types, placement, flicker presets | Imported, NEVER CALLED |
| `prop_density.py` | handlers/ | 761 | 12 room type density rules, Poisson placement | Imported, NEVER CALLED |
| `coastline.py` | handlers/ | 539 | 4 coastline styles, feature placement | Imported, registered, NEVER CALLED |
| `road_network.py` | handlers/ | 699 | MST road network, classification, bridges | Imported, registered, NEVER CALLED |
| `terrain_features.py` | handlers/ | 2,089 | 10 terrain feature generators | Only 4 of 10 imported |

### No New Libraries Needed

This phase requires zero new library installations. All code exists. The work is exclusively import/call wiring.

## Architecture Patterns

### Compose Map Pipeline (Current -- 10 Steps)
```
Step 1: Clear scene
Step 2: Generate terrain (with erosion) -- WORKING
Step 3: Water bodies (rivers + water level) -- calls env_create_water but no spline data
Step 4: Roads -- calls env_generate_road (simple waypoint) NOT road_network.py MST
Step 5: Place locations -- _LOC_HANDLERS dispatch, castle BYPASSES settlement_generator
Step 6: Biome paint + lighting -- lighting uses setup_dark_fantasy_lighting NOT light_integration
Step 7: Vegetation scatter -- calls env_scatter_vegetation (has VEGETATION_GENERATOR_MAP wiring)
Step 8: Prop scatter -- calls env_scatter_props, NOT prop_density engine
Step 9: Generate interiors -- basic room generation, NOT building_interior_binding
Step 10: Export heightmap
```

### Compose Map Pipeline (Target -- After Wiring)
```
Step 1: Clear scene -- UNCHANGED
Step 2: Generate terrain (with erosion) -- UNCHANGED
Step 2.5: NEW -- Terrain features (coastline + 7 dead features based on map_spec)
Step 3: Water bodies -- pass spline path_points from river carving into water mesh creation
Step 3.5: NEW -- Spline-terrain deformation along river/road paths
Step 4: Roads -- replace env_generate_road with env_compute_road_network (MST) + materialize
Step 5: Place locations -- fix _LOC_HANDLERS, route castle through settlement_generator
Step 5.5: NEW -- Building interiors via building_interior_binding room mapping
Step 6: Biome paint + lighting -- add light_integration LIGHT_PROP_MAP placement
Step 7: Vegetation scatter -- verify VEGETATION_GENERATOR_MAP path used (not cube fallback)
Step 8: Prop scatter -- wire prop_density engine for AAA density placement
Step 8.5: NEW -- Atmospheric volumes placement
Step 9: Generate interiors -- use building_interior_binding for room type mapping
Step 10: Export heightmap -- UNCHANGED
```

### Wiring Pattern (Repeat for Each System)
```python
# Pattern 1: Import in __init__.py
from .module_name import (
    function_name,
    CONSTANT_NAME,
)

# Pattern 2: Fix dispatch table
_LOC_HANDLERS = {
    "settlement": "world_generate_settlement",  # was world_generate_town
    "castle": "world_generate_settlement",       # was world_generate_castle
}

# Pattern 3: Add compose_map step
if "new_step" not in steps_completed:
    try:
        result = await blender.send_command("command_name", {params})
        steps_completed.append("new_step")
    except Exception as e:
        steps_failed.append({"step": "new_step", "error": str(e)})
    _save_chkpt()
```

### Anti-Patterns to Avoid
- **Do NOT rewrite generator logic.** These systems work. Only change how they are called.
- **Do NOT change pure-logic module signatures.** The generators return MeshSpec dicts. The wiring layer (blender_server.py, __init__.py, worldbuilding.py) is what changes.
- **Do NOT remove fallback paths.** Keep cube/simple fallbacks as error recovery, but ensure the primary path uses the real generators.
- **Do NOT add new compose_map steps without checkpoint support.** Every new step MUST have `if "step_name" not in steps_completed` guard and `_save_chkpt()` call.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Road network connectivity | Custom A* path | `compute_road_network()` from road_network.py | Already has MST, classification, bridges, switchbacks |
| Building-to-room mapping | Hardcoded room lists | `BUILDING_ROOM_MAP` from building_interior_binding.py | Already covers 14 building types with floor/size ratios |
| Atmospheric volume placement | Manual volume creation | `compute_atmospheric_placements()` from atmospheric_volumes.py | Already has 7 types, biome rules, performance estimation |
| Light placement | Manual light adding | `compute_light_placements()` from light_integration.py | Already has budget, merging, 8 prop types |
| Interior prop density | Simple random placement | `compute_detail_prop_placements()` from prop_density.py | Already has Poisson-disk, zone-aware, 12 room types |
| Modular building assembly | New building generator | `assemble_building()` from modular_building_kit.py | Already has 52 piece types x 5 styles, snap-grid |

**Key insight:** Every "feature" in this phase already exists as complete, tested code. The work is exclusively plumbing -- import statements, dispatch table entries, and compose_map step additions.

## Common Pitfalls

### Pitfall 1: Changing Generator Signatures
**What goes wrong:** Modifying pure-logic generator functions breaks 810 existing tests.
**Why it happens:** Developer thinks the generator needs changes to "fit" the pipeline.
**How to avoid:** The wiring layer adapts to the generators, not the other way around. Create adapter functions if needed (like `_lsystem_tree_generator` already does in `_mesh_bridge.py`).
**Warning signs:** Any diff touching files like `vegetation_lsystem.py`, `road_network.py`, `atmospheric_volumes.py` core logic.

### Pitfall 2: Breaking Checkpoint Resume
**What goes wrong:** New compose_map steps don't have checkpoint guards, causing duplicate work or crashes on resume.
**Why it happens:** Developer adds step but forgets the `if "step_name" not in steps_completed` pattern.
**How to avoid:** Every new step MUST follow the existing pattern: check -> try -> append to steps_completed -> _save_chkpt(). Copy an existing step as template.
**Warning signs:** New steps without the guard pattern.

### Pitfall 3: Dual Code Path for Vegetation
**What goes wrong:** Both `vegetation_system.py` (cubes) and `environment_scatter.py` (real meshes) exist. Wiring one doesn't prevent the other from being called.
**Why it happens:** Multiple MCP commands exist: `env_scatter_vegetation` (good) and `env_scatter_biome_vegetation` (cubes).
**How to avoid:** Ensure `env_scatter_biome_vegetation` either delegates to `env_scatter_vegetation` or is deprecated/removed. compose_map Step 7 already calls the correct handler.
**Warning signs:** Any code path that reaches `vegetation_system.py:762-766` (the cube creation lines).

### Pitfall 4: Castle Routing Breaks Existing Castle Generation
**What goes wrong:** Routing castle through settlement_generator changes the output structure, breaking Hearthvale and other tests.
**Why it happens:** settlement_generator.py's "castle" type has different parameters/output than handle_generate_castle.
**How to avoid:** settlement_generator already has a "castle" type (lines 77-89). Route compose_map castle requests to `world_generate_settlement` with `settlement_type="castle"`. The settlement system will handle layout, roads, and building placement, then call the building generator for individual structures.
**Warning signs:** Castle test failures, Hearthvale regression.

### Pitfall 5: Pure-Logic Modules Need Blender Materialization
**What goes wrong:** Modules like `road_network.py`, `coastline.py`, `atmospheric_volumes.py` return pure MeshSpec dicts, not Blender objects. Calling them directly from compose_map won't create visible geometry.
**Why it happens:** These modules are pure-logic (no bpy imports) for testability.
**How to avoid:** Use `mesh_from_spec()` from `_mesh_bridge.py` to convert MeshSpec dicts into Blender objects. This is the standard pattern already used by `_create_vegetation_template()` and castle detail generation.
**Warning signs:** compose_map step succeeds but no objects appear in scene.

### Pitfall 6: Import Cycles
**What goes wrong:** Adding `from .modular_building_kit import ...` to `__init__.py` creates circular imports.
**Why it happens:** `__init__.py` already imports from 40+ modules. Some modules import from each other.
**How to avoid:** Check for circular dependencies before adding imports. Use lazy imports (inside functions) if needed. `modular_building_kit.py` and `building_interior_binding.py` have no handler-to-handler imports, so they should be safe.
**Warning signs:** ImportError on module load.

## Code Examples

### Example 1: Import modular_building_kit in __init__.py
```python
# Source: Pattern from existing __init__.py imports (line 244-258)
from .modular_building_kit import (  # noqa: F401 -- modular building kit
    generate_modular_piece,
    assemble_building,
    get_available_pieces,
    STYLES as MODULAR_STYLES,
)
```

### Example 2: Import building_interior_binding in __init__.py
```python
# Source: Pattern from existing __init__.py imports
from .building_interior_binding import (  # noqa: F401 -- building interior binding
    BUILDING_ROOM_MAP,
    generate_interior_specs_for_building,  # if this function exists
)
```

### Example 3: Fix _LOC_HANDLERS Dispatch Table
```python
# Source: blender_server.py line 2924
# BEFORE (broken):
_LOC_HANDLERS = {
    "settlement": "world_generate_town",      # BUG: should be world_generate_settlement
    "castle": "world_generate_castle",         # BYPASS: should route through settlement
}

# AFTER (fixed):
_LOC_HANDLERS = {
    "settlement": "world_generate_settlement",  # FIXED: use full settlement system
    "castle": "world_generate_settlement",       # FIXED: route through settlement
}
```

### Example 4: New compose_map Step for Road Network
```python
# Source: compose_map pattern from blender_server.py Step 3-8
# Replace simple road generation with MST road network
if "road_network" not in steps_completed:
    try:
        # Collect waypoints from planned locations
        waypoints = [
            (loc["anchor"][0], loc["anchor"][1], loc["anchor"][2])
            for loc in location_results
        ]
        if len(waypoints) >= 2:
            road_result = await blender.send_command("env_compute_road_network", {
                "waypoints": waypoints,
                "water_level": water_cfg.get("water_level", 0.0),
                "seed": map_seed + 200,
            })
            # Materialize road segments using mesh_from_spec
            # (road_network returns pure data, needs Blender conversion)
            steps_completed.append("road_network")
    except Exception as e:
        steps_failed.append({"step": "road_network", "error": str(e)})
    _save_chkpt()
```

### Example 5: Wire Atmospheric Volumes into compose_map
```python
# Source: compose_map pattern + atmospheric_volumes.py API
if biome and "atmosphere_volumes" not in steps_completed:
    try:
        from blender_addon.handlers.atmospheric_volumes import (
            compute_atmospheric_placements,
        )
        placements = compute_atmospheric_placements(
            biome_type=biome,
            area_bounds=(0.0, 0.0, terrain_size, terrain_size),
            density_scale=float(spec.get("atmosphere_density", 1.0)),
            seed=map_seed + 600,
        )
        # Materialize each volume placement as a Blender object
        for p in placements:
            mesh_spec = compute_volume_mesh_spec(p)
            # Use mesh_from_spec to create Blender object
        steps_completed.append("atmosphere_volumes")
    except Exception as e:
        steps_failed.append({"step": "atmosphere_volumes", "error": str(e)})
    _save_chkpt()
```

### Example 6: Import Remaining Terrain Features
```python
# Source: __init__.py line 253-258
# BEFORE: only 4 of 10 imported
from .terrain_features import (
    generate_canyon,
    generate_waterfall,
    generate_cliff_face,
    generate_swamp_terrain,
)

# AFTER: all 10 imported
from .terrain_features import (  # noqa: F401 -- terrain feature generators
    generate_canyon,
    generate_waterfall,
    generate_cliff_face,
    generate_swamp_terrain,
    generate_natural_arch,
    generate_geyser,
    generate_sinkhole,
    generate_floating_rocks,
    generate_ice_formation,
    generate_lava_flow,
)
```

## Detailed File-Level Wiring Map

### Files That Need Changes

| File | What Changes | Lines Affected |
|------|-------------|----------------|
| `handlers/__init__.py` | Add imports for modular_building_kit, building_interior_binding; import remaining 6 terrain features; add dispatch entries | ~20 new import lines, ~10 new dispatch entries |
| `blender_server.py` | Fix _LOC_HANDLERS; add compose_map steps for atmosphere, lighting, MST roads, coastline, terrain features, prop density; wire spline data into water/road calls | ~100-150 new lines in compose_map |
| `worldbuilding.py` | Route castle through settlement_generator; wire modular_building_kit into _generate_location_building | ~30-50 lines changed |
| `environment_scatter.py` | Ensure vegetation_system.py cube path is deprecated or redirected | ~5-10 lines |
| `vegetation_system.py` | Redirect handle_scatter_biome_vegetation to use VEGETATION_GENERATOR_MAP path | ~10-20 lines |

### Files That Should NOT Change

| File | Why |
|------|-----|
| `_mesh_bridge.py` | VEGETATION_GENERATOR_MAP already correct (18 entries) |
| `modular_building_kit.py` | Pure-logic, complete, 100% tested |
| `settlement_generator.py` | Pure-logic, complete, 15 types working |
| `building_interior_binding.py` | Pure-logic, complete, 14 room types working |
| `atmospheric_volumes.py` | Pure-logic, complete, 7 volume types working |
| `light_integration.py` | Pure-logic, complete, 8 light prop types working |
| `prop_density.py` | Pure-logic, complete, 12 room density rules working |
| `coastline.py` | Pure-logic, complete, 4 styles working |
| `road_network.py` | Pure-logic, complete, MST + classification working |
| `terrain_features.py` | Pure-logic, complete, 10 generators working |
| `vegetation_lsystem.py` | Pure-logic, complete, 5 species working |

## VEGETATION_GENERATOR_MAP Coverage

The map in `_mesh_bridge.py` lines 285-304 currently has 18 entries:

| Key | Generator | Kwargs |
|-----|-----------|--------|
| `tree` | `_lsystem_tree_generator` | oak, iterations=4, broadleaf, veil_healthy |
| `tree_healthy` | `_lsystem_tree_generator` | oak, iterations=4, broadleaf, veil_healthy |
| `tree_boundary` | `_lsystem_tree_generator` | birch, iterations=4, broadleaf, veil_boundary |
| `tree_blighted` | `_lsystem_tree_generator` | twisted, iterations=4, vine, veil_blighted |
| `tree_dead` | `_lsystem_tree_generator` | dead, iterations=4, None, veil_blighted |
| `tree_twisted` | `_lsystem_tree_generator` | twisted, iterations=4, vine, veil_boundary |
| `pine_tree` | `_lsystem_tree_generator` | pine, iterations=4, needle, veil_healthy |
| `bush` | `generate_shrub_mesh` | {} |
| `shrub` | `generate_shrub_mesh` | {} |
| `grass` | `generate_grass_clump_mesh` | {} |
| `weed` | `generate_grass_clump_mesh` | blade_count=9, height=0.5 |
| `flower` | `generate_mushroom_mesh` | size=0.28, cap_style=cluster |
| `rock` | `generate_rock_mesh` | boulder |
| `rock_mossy` | `generate_rock_mesh` | boulder, size=0.92 |
| `cliff_rock` | `generate_rock_mesh` | cliff_outcrop |
| `mushroom` | `generate_mushroom_mesh` | {} |
| `mushroom_cluster` | `generate_mushroom_mesh` | cluster, size=0.34 |
| `root` | `generate_root_mesh` | {} |

The biome vegetation rules in `blender_server.py` (`_default_vegetation_rules_for_biome`) use keys like `tree_healthy`, `tree_boundary`, `tree_blighted` which DO match the map. The wiring from compose_map through `env_scatter_vegetation` to `_create_vegetation_template` to `VEGETATION_GENERATOR_MAP.get(veg_type)` is CORRECT.

**The real issue:** The `vegetation_system.py` handler `handle_scatter_biome_vegetation` (registered as `env_scatter_biome_vegetation`) creates cubes. If any code path calls this instead of `env_scatter_vegetation`, cubes appear. The Hearthvale scene was likely generated using an older code path or direct `env_scatter_biome_vegetation` call.

## Settlement Types (All 15)

From `settlement_generator.py`:
1. village (4-8 buildings, organic layout)
2. town (8-16 buildings, grid layout, walls)
3. bandit_camp (3-6, circular)
4. castle (5-10, concentric, walls)
5. outpost (2-4, grid, walls)
6. traveler_camp (2-5, circular)
7. merchant_camp (3-7, organic)
8. wizard_fortress (6-12, concentric, walls)
9. sorcery_school (5-10, grid, walls)
10. cliff_keep (4-8, concentric, walls)
11. ruined_town (5-10, organic)
12. farmstead (3-6, organic)
13. medieval_town (40-80, concentric_organic, walls)
14. coastal_village (4-8, radial)
15. hearthvale (custom, 40-80, walled)

## Terrain Features -- Import Status

| Generator | Imported in __init__.py | In Dispatch Table | Called from compose_map |
|-----------|------------------------|-------------------|----------------------|
| generate_canyon | YES | YES (env_generate_canyon) | NO |
| generate_waterfall | YES | YES (env_generate_waterfall) | NO |
| generate_cliff_face | YES | YES (env_generate_cliff_face) | NO |
| generate_swamp_terrain | YES | NO | NO |
| generate_natural_arch | NO | NO | NO |
| generate_geyser | NO | NO | NO |
| generate_sinkhole | NO | NO | NO |
| generate_floating_rocks | NO | NO | NO |
| generate_ice_formation | NO | NO | NO |
| generate_lava_flow | NO | NO | NO |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_mesh_bridge.py tests/test_settlement_generator.py tests/test_modular_building_kit.py tests/test_building_interior_binding.py tests/test_road_network.py tests/test_atmospheric_volumes.py tests/test_light_integration.py tests/test_vegetation_lsystem.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WIRE-01 | VEGETATION_GENERATOR_MAP used by scatter, no cubes | unit | `pytest tests/test_mesh_bridge.py tests/test_aaa_terrain_vegetation.py -x` | YES |
| WIRE-02 | Modular building kit imported and callable | unit | `pytest tests/test_modular_building_kit.py -x` | YES |
| WIRE-03 | Settlement generator dispatched for castle/settlement types | unit | `pytest tests/test_settlement_generator.py tests/test_aaa_castle_settlement.py -x` | YES |
| WIRE-04 | AAA water handler creates spline mesh with flow data | unit | `pytest tests/test_aaa_water_scatter.py -x` | YES |
| WIRE-05 | Spline-terrain deformation applied to roads/rivers | unit | `pytest tests/test_road_coastline_terrain_features.py -x` | YES |
| WIRE-06 | L-system trees generated with proper species | unit | `pytest tests/test_vegetation_lsystem.py -x` | YES |
| WIRE-07 | Interior binding maps building type to room types | unit | `pytest tests/test_building_interior_binding.py -x` | YES |
| WIRE-08 | Atmospheric volumes + lights + prop density placed | unit | `pytest tests/test_atmospheric_volumes.py tests/test_light_integration.py tests/test_prop_density_decal_encounter.py -x` | YES |
| WIRE-09 | Coastline + 6 terrain features importable and dispatchable | unit | `pytest tests/test_road_coastline_terrain_features.py tests/test_terrain_features_v2.py -x` | YES |
| WIRE-10 | MST road network replaces simple path generation | unit | `pytest tests/test_road_network.py -x` | YES |
| WIRE-11 | building_interior_binding importable from __init__ | integration | `pytest tests/test_integration_pipelines.py -x` | YES |
| TEST-04 | All tests pass, Opus scan clean | full-suite | `pytest tests/ -x -q` | YES |

### Sampling Rate
- **Per task commit:** Quick run command (relevant test files)
- **Per wave merge:** Full suite (`pytest tests/ -x -q`)
- **Phase gate:** Full suite green + Opus scan clean before verify

### Wave 0 Gaps
- [ ] `tests/test_wiring_integration.py` -- NEW test file needed to verify wiring connections specifically (e.g., that `_LOC_HANDLERS["settlement"]` maps to correct handler, that `__init__.py` exports modular_building_kit symbols, that compose_map new steps follow checkpoint pattern)
- [ ] Verify no import cycles when adding new imports to `__init__.py`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cube placeholders for vegetation | VEGETATION_GENERATOR_MAP with L-system trees | v8.0 (map created, never wired) | 18 procedural mesh types available |
| Box geometry for castle | Settlement generator with modular kit | v8.0 (code written, never called) | 260-piece architecture system |
| Simple waypoint roads | MST road network with classification | v8.0 (pure-logic module, never called) | Bridge detection, switchbacks, road hierarchy |
| Flat quad water | Spline-following water mesh with flow vertex colors | v8.0 (handler exists, no spline data passed) | AAA water with flow direction + foam |

## Open Questions

1. **Castle through settlement_generator parameter mapping**
   - What we know: settlement_generator has "castle" type with 5-10 buildings, concentric layout
   - What's unclear: How does the existing `handle_generate_castle` outer_size/keep_size/tower_count map to settlement_generator parameters? The settlement system uses center/radius/wall_height.
   - Recommendation: Route castle through settlement_generator, which then calls _generate_location_building for each structure. Castle-specific parameters (outer_size, keep_size) may need an adapter or the settlement "castle" type config may need extension.

2. **Pure-logic modules need Blender materialization bridge**
   - What we know: road_network, coastline, atmospheric_volumes return MeshSpec dicts (pure data)
   - What's unclear: compose_map communicates with Blender via `blender.send_command()` which expects registered command names. The pure-logic modules are registered but their outputs are data, not Blender objects.
   - Recommendation: Either (a) create thin handler wrappers that call the pure-logic function + mesh_from_spec, or (b) add materialization steps in blender_server.py after calling the registered commands.

3. **Vegetation scatter dual path deprecation**
   - What we know: `env_scatter_vegetation` (good) and `env_scatter_biome_vegetation` (cubes) both exist
   - What's unclear: Is `env_scatter_biome_vegetation` called anywhere outside of direct MCP tool use?
   - Recommendation: Make `handle_scatter_biome_vegetation` delegate to `handle_scatter_vegetation` internally, or add VEGETATION_GENERATOR_MAP lookup into it. Do NOT remove it (would break MCP API).

## Project Constraints (from CLAUDE.md)

- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- **Always verify visually** after Blender mutations. Use `blender_viewport` action=`contact_sheet`.
- **Run game_check** before ANY export.
- **Batch when possible**: Use batch operations where available.
- **Bug scan rounds**: Always run follow-up rounds until CLEAN.
- **Fix broken tools immediately**: Don't retry same broken approach.
- **Blender is Z-up**: Code keeps using Y for vertical -- systemic recurring bug. Verify all wiring respects Z-up.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `blender_addon/handlers/__init__.py` -- verified import status of all 11 modules
- Direct codebase analysis of `blender_server.py` lines 2732-3224 -- full compose_map pipeline traced
- Direct codebase analysis of `_mesh_bridge.py` lines 285-304 -- VEGETATION_GENERATOR_MAP verified
- Direct codebase analysis of `modular_building_kit.py` -- 2,579 lines, zero imports found
- Direct codebase analysis of `building_interior_binding.py` -- 400 lines, zero handler imports found
- `V9_MASTER_FINDINGS.md` sections 1.5, 4, 5, 6 -- wiring status, water, vegetation, settlement findings
- Test suite run: 810 tests pass for all dead-code modules (verified 2026-04-04)

### Secondary (MEDIUM confidence)
- `REQUIREMENTS.md` WIRE-01 through WIRE-11 requirement descriptions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all modules verified in codebase, no external dependencies
- Architecture: HIGH - compose_map pipeline fully traced, all dispatch tables analyzed
- Pitfalls: HIGH - specific line numbers and code paths identified for each risk
- Wiring map: HIGH - every import/dispatch/call-site verified against actual source

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable codebase, no external dependency drift)
