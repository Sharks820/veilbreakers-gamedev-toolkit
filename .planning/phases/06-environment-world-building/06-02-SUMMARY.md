---
phase: 06-environment-world-building
plan: 02
status: complete
completed: 2026-03-19
tests_passed: 57  # 33 dungeon_gen + 24 worldbuilding_layout_handlers
tests_total: 57
regressions: 0
full_suite: 998 passed
---

# Phase 06 Plan 02 Summary: Dungeon/Cave/Town Layout Generation

## What was built

### Pure-logic module: `_dungeon_gen.py`
- **BSP dungeon generator** (`generate_bsp_dungeon`): Recursive binary space partition creates rooms with corridors, doors, spawn/loot points. Connectivity guaranteed via flood-fill verification with forced corridor fallback.
- **Cellular automata cave generator** (`generate_cave_map`): 4-5 rule automata with configurable fill probability. Produces single connected region by pruning disconnected floor areas.
- **Town layout generator** (`generate_town_layout`): Voronoi-based district assignment with typed districts (civic, residential, commercial, industrial), road network along district boundaries, building plot subdivision, and landmark placement.
- All algorithms are seed-deterministic. Zero bpy/bmesh imports.

### Blender handlers: `worldbuilding_layout.py`
- `handle_generate_dungeon` -- BSP rooms to bmesh geometry (floors, walls, corridors, doors)
- `handle_generate_cave` -- Cellular automata to bmesh (floor quads + boundary wall columns)
- `handle_generate_town` -- Voronoi districts to bmesh (roads, plot markers, landmark markers)
- Pure-logic conversion functions (`_dungeon_to_geometry_ops`, `_cave_to_geometry_ops`, `_town_to_geometry_ops`) fully testable without Blender.

### Handler registration
- 3 new entries in `COMMAND_HANDLERS`: `world_generate_dungeon`, `world_generate_cave`, `world_generate_town`

## Files created/modified

| File | Action |
|------|--------|
| `Tools/mcp-toolkit/blender_addon/handlers/_dungeon_gen.py` | Created -- pure-logic BSP/cave/town algorithms |
| `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py` | Created -- 3 Blender handlers + geometry ops converters |
| `Tools/mcp-toolkit/blender_addon/handlers/__init__.py` | Modified -- import + register 3 new handlers |
| `Tools/mcp-toolkit/tests/test_dungeon_gen.py` | Created -- 33 tests (BSP, cave, town) |
| `Tools/mcp-toolkit/tests/test_worldbuilding_layout_handlers.py` | Created -- 24 tests (geometry ops + handler metadata) |

## Requirements satisfied

| Req | Description | Evidence |
|-----|-------------|----------|
| ENV-03 | Cave/dungeon system generation | BSP dungeon + cellular automata caves, connectivity verified |
| ENV-11 | Town/settlement layout | Voronoi districts, roads, building plots, landmarks |
| ENV-12 | Dungeon layout generation | BSP rooms, corridors, doors, spawn/loot points |

## Key properties verified by tests

- BSP dungeon: all rooms reachable (flood-fill), no overlapping rooms, min size respected, room types assigned, grid values in {0,1,2,3}, spawn points on floor cells
- Cave: single connected region, border cells are walls, floor ratio 10-70%, fill_probability 0.3 more open than 0.6
- Town: districts cover full area, roads form connected network (>90%), building plots within district boundaries, district types include civic + residential, landmarks near roads
- All algorithms: deterministic with same seed, different seeds produce different outputs
