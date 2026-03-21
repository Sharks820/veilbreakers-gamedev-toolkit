---
phase: 18-procedural-mesh-integration-terrain-depth
plan: 03
subsystem: blender-handlers
tags: [procedural-mesh, handler-integration, worldbuilding, scatter, dungeon, castle]

requires:
  - phase: 18-01
    provides: "_mesh_bridge.py with 4 mapping dicts, mesh_from_spec, resolve_generator"
  - phase: 18-02
    provides: "_terrain_depth.py with 5 terrain generators"
provides:
  - "Interior handler dispatches 28+ furniture types through FURNITURE_GENERATOR_MAP with cube fallback"
  - "Castle handler places gate, rampart, drawbridge, fountain from CASTLE_ELEMENT_MAP"
  - "Vegetation scatter uses real tree/rock/mushroom/bush/root templates from VEGETATION_GENERATOR_MAP"
  - "generate_dungeon_prop_placements: pure-logic dungeon prop placement engine"
  - "Dungeon handler creates props from DUNGEON_PROP_MAP (torches, altars, pillars, chests, archways)"
  - "14 integration tests covering all 4 mapping tables and placement rules"
affects: [blender-worldbuilding, blender-environment, dungeon-gen]

tech-stack:
  added: []
  patterns:
    - "Generator dispatch: look up item type in mapping dict, call generator, feed to mesh_from_spec"
    - "Cube fallback: unmapped types gracefully degrade to primitive cube geometry"
    - "Pure-logic prop placement: generate_dungeon_prop_placements returns placement dicts, handler creates geometry"
    - "Scatter template optimization: lower segment counts for instanced vegetation templates"

key-files:
  created:
    - "Tools/mcp-toolkit/tests/test_mesh_integration.py"
  modified:
    - "Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py"
    - "Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py"
    - "Tools/mcp-toolkit/blender_addon/handlers/_dungeon_gen.py"
    - "Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py"

decisions:
  - "Cube fallback for 25 unmapped furniture types (armor_stand, bed, throne, etc.) -- generators can be added later"
  - "'chains' alias added to FURNITURE_GENERATOR_MAP for _ROOM_CONFIGS compatibility"
  - "Grass stays as flat plane in vegetation scatter (billboard grass is standard game technique)"
  - "Dungeon prop placement is pure-logic to enable testing without bpy"
  - "Lower segment counts for scatter templates (6 for trees, 8 for rocks) to prevent viewport slowdown"

metrics:
  duration: "16m 26s"
  completed: "2026-03-21T09:13:27Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 14
  tests_total_passing: 71
  files_modified: 5
  files_created: 1
---

# Phase 18 Plan 03: Handler Integration Summary

Wire procedural mesh generators into worldbuilding, scatter, dungeon, and castle handlers -- replacing primitive cubes/cones with real geometry from 127-generator library.

## One-Liner

Interior/castle/scatter/dungeon handlers now dispatch furniture, vegetation, castle elements, and dungeon props through 4 mapping tables to procedural mesh generators with graceful cube fallback.

## Task Results

### Task 1: Interior and Castle Handlers (54bb1aa)

Modified `worldbuilding.py` to use procedural meshes:

**Interior handler (handle_generate_interior):**
- Looks up each furniture item type in FURNITURE_GENERATOR_MAP
- 28+ types dispatched to procedural generators (table, chair, shelf, chest, barrel, bookshelf, altar, pillar, brazier, chandelier, candelabra, crate, rug, banner, anvil, forge, workbench, cauldron, sarcophagus, chain/chains, desk, large_table, long_table, serving_table, locked_chest, carpet, cage, shelf_with_bottles, wall_tomb)
- 25 unmapped types fall back to cube creation (armor_stand, bed, throne, wardrobe, etc.)
- Result dict includes `procedural_mesh_count` for tracking

**Castle handler (handle_generate_castle):**
- After main structure via _spec_to_bmesh, adds procedural detail elements
- Gate mesh at front center (gatehouse position)
- Rampart meshes along 4 wall tops, spaced every 4m
- Drawbridge mesh at gate position extending outward
- Fountain mesh at courtyard center
- All parented to castle object under CastleDetails collection

### Task 2: Scatter and Dungeon Handlers (b5ebc03)

**Vegetation scatter (environment_scatter.py):**
- `_create_vegetation_template` uses VEGETATION_GENERATOR_MAP for tree, bush, rock, mushroom, root
- Lower segment counts for scatter templates (instanced 1000s of times)
- Grass stays as flat plane (correct billboard technique for games)
- Material assignment preserved after template creation

**Dungeon prop placement (_dungeon_gen.py):**
- New pure-logic function `generate_dungeon_prop_placements(layout, seed)`
- Boss rooms: altar at center + pillar at 4 corners
- Treasure rooms: chest at center + torch_sconce at 4 corners
- Generic/entrance rooms: 1-2 random props (crate, barrel, skull_pile)
- Corridors: torch_sconce every 4-6 cells, alternating sides
- Doorways: 30% chance of archway
- Returns placement dicts (type, position, rotation, room_type)

**Dungeon handler (worldbuilding.py):**
- Consumes prop placements via generate_dungeon_prop_placements()
- Creates geometry for each prop through DUNGEON_PROP_MAP + mesh_from_spec
- Per-floor prop collections for organization
- Result includes procedural_mesh_count

**Integration tests (test_mesh_integration.py):**
14 tests across 4 test classes:
- TestInteriorFurnitureMapping (3): coverage verification, generator validation, mapped count
- TestVegetationMapping (2): type coverage, generator validation
- TestDungeonPropPlacement (7): valid types, required keys, torch spacing, boss altar, treasure chest, boss pillars, determinism
- TestCastleElementMapping (2): element coverage, generator validation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added 'chains' alias in FURNITURE_GENERATOR_MAP**
- **Found during:** Task 1
- **Issue:** _ROOM_CONFIGS uses "chains" but FURNITURE_GENERATOR_MAP had only "chain"
- **Fix:** Added "chains": (generate_chain_mesh, {}) alias
- **Files modified:** _mesh_bridge.py
- **Commit:** 54bb1aa

## Verification

```
cd Tools/mcp-toolkit && python -m pytest tests/test_worldbuilding_handlers.py tests/test_environment_scatter_handlers.py tests/test_mesh_integration.py tests/test_dungeon_gen.py -x -q
71 passed in 2.71s

# Full suite (excluding 2 pre-existing API key failures)
python -m pytest tests/ -q --ignore=tests/test_elevenlabs_client.py --ignore=tests/test_gemini_client.py
7345 passed, 38 skipped in 30.35s
```

## Known Stubs

None -- all mapped types produce real procedural geometry. Unmapped furniture types (25) are intentional cube fallbacks and documented in test_mesh_integration.py._UNMAPPED_FURNITURE_TYPES.

## Self-Check: PASSED

All 5 created/modified files exist. Both task commits (54bb1aa, b5ebc03) verified in git log.
