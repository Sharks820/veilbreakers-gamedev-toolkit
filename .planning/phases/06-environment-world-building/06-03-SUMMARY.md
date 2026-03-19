---
phase: 06-environment-world-building
plan: 03
status: complete
completed: 2026-03-19
tests_before: 914
tests_after: 998
tests_added: 84
handler_count_before: 59
handler_count_after: 64
---

## What was done

Built the complete building/structure generation pipeline: pure-logic grammar rules, specialized structure templates, ruins damage system, interior furniture layout, and modular architecture kit.

### Files created
- `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` -- Pure-logic module (zero bpy imports) with:
  - `STYLE_CONFIGS`: 5 architectural presets (medieval, gothic, rustic, fortress, organic)
  - `BuildingSpec` dataclass for geometry operation lists
  - `evaluate_building_grammar()`: grammar-rule evaluation (foundation -> walls -> floors -> roof -> windows -> door -> details)
  - `generate_castle_spec()`: curtain walls, corner towers, keep, gatehouse
  - `generate_tower_spec()`: cylindrical body, spiral stairs placeholder, battlement ring
  - `generate_bridge_spec()`: semicircular arches, road deck, railings, abutments
  - `generate_fortress_spec()`: outer walls, corner towers, central keep, courtyard, gatehouse
  - `apply_ruins_damage()`: priority-based operation removal with debris and vegetation
  - `generate_interior_layout()`: collision-avoiding furniture placement for 8 room types
  - `MODULAR_CATALOG` + `generate_modular_pieces()`: grid-aligned architecture kit (8 piece types)

- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` -- 5 Blender handlers:
  - `handle_generate_building`: grammar -> bmesh geometry
  - `handle_generate_castle`: castle template -> joined mesh
  - `handle_generate_ruins`: damage spec -> structure + debris
  - `handle_generate_interior`: furniture layout -> parented placeholder objects
  - `handle_generate_modular_kit`: piece catalog -> grid-aligned mesh objects with custom properties
  - Pure-logic helpers: `_building_ops_to_mesh_spec()` and result builders for testability

- `Tools/mcp-toolkit/tests/test_building_grammar.py` -- 67 tests covering:
  - Style config validation (10 tests)
  - Grammar evaluation (15 tests)
  - Specialized templates: castle, tower, bridge, fortress (17 tests)
  - Ruins damage scaling and determinism (7 tests)
  - Interior furniture placement and collision avoidance (9 tests)
  - Modular kit dimensions and scaling (9 tests)

- `Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py` -- 17 tests covering:
  - Mesh spec conversion: box (8 verts, 6 faces), cylinder vertex counts, opening flags (4 tests)
  - Handler return shape validation for all 5 handlers (10 tests)
  - Geometry correctness: box vertex positions, cylinder circle formation (3 tests)

### Files modified
- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py` -- Added worldbuilding imports and 5 COMMAND_HANDLERS entries (59 -> 64 handlers)

## Key decisions
- Direct bmesh face construction for window/door openings (no boolean subtract) per research recommendation
- Ruins damage uses priority ordering: details/roof removed first, foundation last
- Interior collision avoidance uses AABB overlap checking with 50-attempt retry
- Modular kit dimensions stored as integer cell multiples, scaled at generation time to avoid float drift
- All generation functions accept `seed` parameter for full determinism

## Requirements covered
- ENV-08: Building generation from grammar rules (5 style presets)
- ENV-09: Castle/tower/bridge/fortress specialized templates
- ENV-10: Ruins generation with damage_level parameter
- ENV-13: Interior furniture placement (8 room types, collision avoidance)
- ENV-14: Modular architecture kit (8 piece types, grid-aligned)
