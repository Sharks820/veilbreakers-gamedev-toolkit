# Phase 33: Interior System -- Research

**Date:** 2026-03-31
**Status:** Complete
**Sources:** Codebase audit (building_interior_binding.py, _building_grammar.py, worldbuilding.py, _mesh_bridge.py), Phase 30 Research, procedural interior generation literature

---

## 1. Current Codebase State

### 1.1 Interior Layout Engine (`_building_grammar.py :: generate_interior_layout`)

**What exists:**
- 22 room type configs in `_ROOM_CONFIGS` (tavern, smithy, storage, barracks, guard_post, throne_room, dungeon_cell, bedroom, kitchen, library, study, great_hall, armory, chapel, shrine_room, blacksmith, guard_barracks, treasury, war_room, alchemy_lab, torture_chamber, crypt, dining_hall)
- Each config is a list of (type, placement_rule, base_size_xy, height) tuples
- Three placement rules: "wall", "center", "corner"
- Collision avoidance via AABB overlap check (50 retry attempts)
- Seed-based RNG for reproducibility

**Critical gaps:**
1. **No spatial relationships** -- chairs don't face tables, beds don't have nightstands beside them, stools don't surround bar counters
2. **No wall-alignment enforcement** -- wall items pick random walls, no preference for back/side walls, no spacing enforcement
3. **No clutter/prop scattering** -- rooms have only furniture, no dishes on tables, books on shelves, tools near workbenches
4. **No lighting placement** -- no torch sconces at doorways, no candles on tables, no fireplace emissive, no point light data
5. **No path clearance enforcement** -- door-to-center path not guaranteed clear, furniture can block doorways
6. **No activity zone concept** -- kitchen has no work triangle, tavern has no bar service zone vs seating zone

### 1.2 Building-Interior Binding (`building_interior_binding.py`)

**What exists:**
- `BUILDING_ROOM_MAP`: 14 building types -> room configs (tavern, house, castle, cathedral, tower, shop, forge, ruin, gate, bridge, wall_section, dungeon_entrance, shrine, abandoned_house)
- `STYLE_MATERIAL_MAP`: 7 styles -> 5-key material palettes (dark_fantasy, gothic, medieval, elven, dwarven, corrupted, fortress)
- `align_rooms_to_building()`: Strip-packing rooms into building footprint by floor
- `generate_door_metadata()`: World-space door positions with scene linking
- `generate_interior_spec_from_building()`: Main bridge function returning compose_interior-compatible spec

**Status:** Pure-logic, well-tested (26 tests), returns specs but NO spatial awareness in furniture placement.

### 1.3 Worldbuilding Interior Handler (`worldbuilding.py :: handle_generate_interior`)

**What exists:**
- Creates room parent empty with `vb_room_type` metadata
- Calls `_create_interior_shell()` for floor/ceiling/walls with procedural materials
- Iterates `generate_interior_layout()` output, creates meshes via `FURNITURE_GENERATOR_MAP` or cube fallback
- 44 furniture type entries in `FURNITURE_GENERATOR_MAP` (bed, table, chair, shelf, chest, barrel, candelabra, bookshelf, wardrobe, cabinet, altar, pillar, brazier, chandelier, crate, rug, banner, anvil, forge, workbench, cauldron, sarcophagus, chain, staircase, tent, lookout_post, bar_counter, fireplace, cooking_fire, pew, map_display, holy_symbol, prayer_mat, nightstand, tool_rack, bellows, large_table, long_table, serving_table, desk, locked_chest, carpet, cage, shelf_with_bottles, wall_tomb)

**Gap:** No items lack generators, but furniture placement has zero spatial intelligence.

### 1.4 FURNITURE_SCALE_REFERENCE

Exists with real-world dimensions for validation:
- door: 1.0-1.2m wide, 2.0-2.2m tall
- table: 0.72-0.78m high, 0.8-1.8m wide
- chair: seat height 0.45-0.50m
- bed: 0.9-2.1m wide, 1.4-2.1m long
- shelf: 1.5-2.6m tall
- barrel: 0.4-0.6m diameter
- torch_sconce: 1.5-1.8m height, 0.15-0.25m protrusion

### 1.5 compose_interior Pipeline (blender_server.py)

Steps: linked_interior -> room geometry -> mesh_enhance -> storytelling_props -> tripo queue
- `storytelling_density` parameter exists but calls `env_add_storytelling_props` which is the ONLY "clutter" path
- No lighting step in the pipeline
- No constraint satisfaction step

---

## 2. Technique Research

### 2.1 Constraint-Based Furniture Placement (Make It Home, Yu et al. 2011)

**Core algorithm:** Simulated annealing with multi-term cost function:
1. **Clearance cost** -- min 0.3m from walls, 0.5m between large furniture
2. **Alignment cost** -- items parallel to nearest wall, desks facing windows
3. **Focal point cost** -- seating oriented toward fireplace/altar/bar/stage
4. **Conversation distance** -- chairs 1.5-3.0m from paired table center
5. **Path accessibility** -- Dijkstra from door to room center, min 1.0m corridor width
6. **Visual balance** -- distribute furniture mass evenly across room quadrants

**Implementation approach for our codebase:**
- Keep `_ROOM_CONFIGS` as item manifest (WHAT goes in each room)
- Add `ROOM_SPATIAL_GRAPHS` defining spatial RELATIONSHIPS (WHERE items go relative to each other)
- Implement constraint solver as post-processing on `generate_interior_layout` output
- Use simulated annealing with temperature schedule: T=100, cooling=0.98, iterations=500

### 2.2 Activity Zones

**Tavern zones:**
- Bar service zone: bar_counter along back wall, stools in 0.5m arc, kegs behind
- Seating zone: tables clustered with 2-4 chairs each, 0.6m clearance between groups
- Hearth zone: fireplace + seating arc (2 chairs/benches within 2.5m facing fire)

**Kitchen work triangle:**
- Stove/fire, prep surface (table), storage (shelf/barrel) forming triangle with 1.2-2.5m legs

**Bedroom clusters:**
- Bed against wall, nightstand within 0.5m of bed head, wardrobe on adjacent wall, desk facing window (opposite wall from bed)

**Blacksmith workflow:**
- Forge against exterior wall (needs chimney), anvil 1.5m from forge, workbench adjacent, tool rack within arm's reach of workbench

### 2.3 Poisson Disk Clutter Scatter (Bridson's Algorithm)

**For surface-bounded scatter (books on shelves, dishes on tables, tools on workbenches):**
- Define scatter surfaces from furniture bounding boxes
- Sample points using Poisson disk with min distance 0.15-0.3m
- Select clutter items from room-type-specific prop pools
- Vary scale +/-15% for natural look
- Density: 5-15 items per room (storytelling_density multiplier)

**Clutter pools per room type:**
- Tavern: mugs, plates, bottles, candle stubs, coins, food scraps
- Bedroom: books, candle, mirror, clothing pile, rug fringe
- Kitchen: pots, ladles, cutting board, vegetables, flour bag
- Blacksmith: hammer, tongs, horseshoe, metal ingot, grinding stone
- Library: open books, quill/ink, scroll, globe, magnifying glass

### 2.4 Lighting Placement Rules

**Per-room-type lighting schema:**
- All rooms: min 2 light sources (2700-3500K warm light)
- Doorways: torch sconce at 1.6m height, both sides of door
- Tables: candle or candelabra per table surface
- Fireplaces: emissive material + point light (2700K, warm orange)
- Chandeliers: hanging from ceiling center, radius coverage of room
- Work areas: focused light source near workbench/desk

**Light source types:**
- torch_sconce: warm (2800K), 4m radius, wall-mounted
- candle: warm (3000K), 2m radius, surface-placed
- fireplace: warm (2700K), 5m radius, emissive + point light
- chandelier: warm (3200K), 8m radius, ceiling-hung
- brazier: warm (3000K), 3m radius, floor-standing

---

## 3. Gap Analysis: What Must Be Built

| Component | Status | Action |
|---|---|---|
| Spatial relationship graphs | MISSING | Create ROOM_SPATIAL_GRAPHS with focal points, clusters, zones |
| Constraint satisfaction solver | MISSING | Implement simulated annealing post-processor |
| Wall clearance 0.3m | PARTIAL (0.15m currently) | Increase wall_margin to 0.3m, enforce door clearance 1.0m |
| Chair-faces-table constraint | MISSING | Add relationship edges in spatial graph |
| Path-to-door clearance | MISSING | Add Dijkstra/bresenham path check from door to center |
| Clutter scatter | MISSING | Implement Poisson disk scatter on furniture surfaces |
| Clutter prop pools | MISSING | Define per-room-type clutter item lists |
| Lighting placement | MISSING | Add light source placement with temperature/radius |
| Lighting data in layout output | MISSING | Extend generate_interior_layout return format |
| Activity zone definitions | MISSING | Define zones per room type |

---

## 4. Implementation Strategy

**Plan: 4 tasks, all in `_building_grammar.py` (pure logic) + tests**

1. **Room Spatial Graphs + Constraint Solver** -- ROOM_SPATIAL_GRAPHS dict, simulated annealing refiner, wall clearance 0.3m, path-to-door check
2. **Activity Zone Templates** -- Zone definitions per room type, focal points, clustering rules, relationship edges (chairs face tables)
3. **Clutter Scatter System** -- Poisson disk sampling on furniture surfaces, per-room clutter pools, 5-15 items per room
4. **Lighting Placement Engine** -- Per-room-type light schemas, doorway torches, surface candles, fireplace emissive, min 2 sources per room

All implementations are pure-logic (no bpy) in `_building_grammar.py` for testability.
The `handle_generate_interior` in `worldbuilding.py` will consume the enhanced layout data.

---

*Research compiled from: codebase audit (2026-03-31), Make It Home (Yu et al., SIGGRAPH 2011), Bridson's Poisson disk algorithm, game interior lighting reference (Skyrim/Fable cell design)*
