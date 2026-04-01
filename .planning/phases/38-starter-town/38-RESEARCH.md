# Phase 38: Starter Town (Hearthvale) - Research

**Researched:** 2026-03-31
**Domain:** Settlement generation, building grammar, interior system, Tripo AI pipeline, Unity export
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Town Identity**
- D-01: Hearthvale is a fortified castle-town — the last free safe haven. Massive castle walls and battlements are the reason this place survives. Not a quaint village — a proper castle keep with an outer market district.
- D-02: Veil pressure 0.0-0.15 — pristine, unaffected by corruption. Props and buildings in excellent condition. No corruption tinting.
- D-03: Atmosphere: bustling market life, warm tavern glow, cobblestone streets alive with commerce. Refugees from outer lands huddle in corners — the contrast is the tone.
- D-04: This town must look amazing — AAA quality visuals are non-negotiable.

**Building Roster (14 buildings)**
- D-05: Exact roster: 1 Tavern ("The Ember Hearth"), 1 Blacksmith, 1 Temple, 1 Town Hall, 2 Shops (general store + apothecary), 1 Bakery, 5 Houses, 1 Guard Barracks
- D-06: Every building gets full interior density — spatial graphs, activity zones, 10-15 clutter items per room, 2+ light sources per room

**Fortifications**
- D-07: Imposing fortress walls — tall gray stone (5-6m), angular guard towers with arrow slits, heavy iron portcullis, battlements with walkways
- D-08: 2+ guard towers minimum, main gate with portcullis geometry
- D-09: Secret entrance: sewer grate by the river, leading under the walls

**Market Area**
- D-10: Central market square with 5+ stalls (Tripo-generated), central well or fountain, cobblestone ground, dense street-level props
- D-11: Market stalls and props via Tripo AI with "dark fantasy medieval, pristine, hand-crafted, PBR-ready" prompts — no corruption variants

**Performance + Export**
- D-12: Quality first, optimize after — full quality generation first, then LOD pass + texture atlas optimization
- D-13: Target: <5s load time on PC, 60fps at 1080p. Profile via unity_performance action=profile_scene
- D-14: Export as Addressables-ready package for Unity

### Claude's Discretion
- River placement and terrain features around the town
- Specific Tripo prompt templates for each prop and stall type
- LOD distances and optimization passes
- Vegetation around town exterior (orchards, farmland for outskirts lots)
- Guard tower interior detail level
- Town hall interior layout

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MESH-13 | Starter town: 10-15 buildings with furnished interiors, market area, fortifications, road network, vegetation, terrain integration. Exports to Unity as Addressables-ready package, maintains 60fps at 1080p | generate_settlement() with "town" type covers building placement + roads + interiors + walls. Gap: 14 specific named buildings require custom roster override. Tripo pipeline covers market stalls. blender_export + unity_build addressables covers export. unity_performance covers profiling. |
</phase_requirements>

---

## Summary

Phase 38 generates Hearthvale, the quality benchmark that proves the entire v7.0 procedural pipeline works end-to-end. The existing `generate_settlement()` function provides the structural backbone — it supports towns with walls, roads, interior furnishing, and perimeter generation. However, Hearthvale's exact 14-building roster (with named buildings like "The Ember Hearth" tavern, apothecary, bakery, etc.) does not map directly to the current `SETTLEMENT_TYPES["town"]` configuration, which uses generic types like `abandoned_house`, `forge`, and `shrine_major`. Phase 38 must define a custom "hearthvale" settlement profile that overrides the building roster with the exact 14 buildings specified in D-05.

The fortification system (`_generate_perimeter`) already handles walls, gates, and corner towers for settlement types with `has_walls: True`, but it generates 3m-height walls by default. Hearthvale requires 5-6m stone fortress walls with battlements and an iron portcullis (named type "gate_large" or "portcullis"). The secret sewer entrance (D-09) is not currently modeled — it will need to be added as an additional perimeter element with a specific type. Wall height is currently a parameter of `generate_settlement(wall_height=3.0)` — passing `wall_height=5.5` will produce the required scale.

The Tripo AI pipeline from Phase 35 is fully operational with PBR texture extraction and the delight pipeline. Five+ market stalls and dense street props can be generated via `asset_pipeline action=generate_3d`. The market square itself is handled by the existing district-based `generate_city_districts()` path when the "market_quarter" district type is active. For Phase 38, using `settlement_type="town"` with a hearthvale-specific `layout_brief` will invoke the organic/radial road layout matching Phase 36 decisions.

**Primary recommendation:** Register a custom "hearthvale" entry in `SETTLEMENT_TYPES`, call `generate_settlement("hearthvale", seed=3810, ...)` with `wall_height=5.5`, then generate Tripo market stalls and props separately, run visual QA via contact sheet, profile performance, and export to Unity with Addressables packaging.

---

## Standard Stack

### Core
| Library / System | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| settlement_generator.py | Phase 36 | Town layout, building placement, roads, interior furnishing, walls | Single source of truth for settlement logic |
| _building_grammar.py | Phase 32+33 | Building specs, interior spatial graphs, clutter, lighting | AAA interior density with activity zones |
| asset_pipeline.generate_3d | Phase 35 | Tripo AI prop and stall generation with PBR extraction | Required for D-10/D-11 market stalls |
| map_composer.py | Phase 36 | Veil pressure, biome integration, full pipeline orchestration | Hearthvale placed in safehold pressure band |
| blender_export (FBX) | Phase 17 | Scene export for Unity import | Standard game export format |
| unity_build (Addressables) | Phase 17 | Streaming package generation | D-14 requirement |
| unity_performance.profile_scene | Phase 8 | 60fps / <5s load validation | D-13 requirement |

### Supporting
| Library / System | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| blender_viewport contact_sheet | All phases | Multi-angle visual QA | After every generation step |
| blender_mesh game_check | Phase 2 | Topology validation before export | Before blender_export |
| blender_mesh repair | Phase 2 | Non-manifold / doubles cleanup | After Tripo prop import |
| blender_uv | Phase 2 | UV atlas generation for Unity | Before export if UV issues detected |
| blender_worldbuilding generate_castle | Phase 6 | Fortification keep geometry if needed | If perimeter system insufficient for portcullis |

---

## Architecture Patterns

### Recommended Hearthvale Generation Structure

```
Phase 38 execution order:
1. Register SETTLEMENT_TYPES["hearthvale"] with 14-building roster
2. generate_settlement("hearthvale", seed=3810, radius=65, wall_height=5.5,
      layout_brief="fortified castle-town, winding cobblestone streets, market square")
3. Tripo stall generation: 5+ stalls via asset_pipeline generate_3d
4. Visual QA: blender_viewport contact_sheet (overhead + 4 ground-level)
5. Issue fixes: blender_mesh repair on any Tripo imports
6. blender_mesh game_check across all buildings
7. blender_export FBX → Unity
8. unity_build addressables grouping
9. unity_performance profile_scene
```

### Pattern 1: Custom "hearthvale" Settlement Profile

The settlement system is data-driven via `SETTLEMENT_TYPES`. Define a new entry matching Hearthvale's exact requirements:

```python
# settlement_generator.py addition
SETTLEMENT_TYPES["hearthvale"] = {
    "building_count": (14, 14),           # Exact count — no randomization
    "has_walls": True,
    "has_market": True,
    "has_shrine": True,
    "road_style": "cobblestone",
    "building_types": [
        "tavern",          # The Ember Hearth — bar, dining, rooms upstairs
        "blacksmith",      # Forge, anvils, weapon racks
        "temple",          # Altar, prayer benches, candelabras
        "town_hall",       # Meeting hall, official chambers
        "general_store",   # Shelves, counters, displayed wares
        "apothecary",      # Shelves, counters, displayed wares
        "bakery",          # Ovens, flour bags, bread displays
        "house",           # Varied sizes, residential furnishing
        "house",
        "house",
        "house",
        "house",
        "guard_barracks",  # Bunks, weapon racks, training equipment
    ],
    "prop_density": 0.7,                  # Dense — pristine Skyrim density
    "perimeter_props": ["wall_segment", "gate_portcullis", "corner_tower"],
    "layout_pattern": "organic",          # Winding medieval, Phase 36 D-01
}
```

The building type strings also need entries in `_BUILDING_ROOMS`, `_BUILDING_FOOTPRINTS`, and `ROOM_FURNISHINGS` for the new types (tavern, blacksmith, temple, town_hall, general_store, apothecary, bakery, guard_barracks are partially defined; house is an alias for abandoned_house).

**Partial coverage audit (what exists vs what's needed):**

| Required Building | Existing Type | Gap |
|-------------------|---------------|-----|
| Tavern | "tavern" in ROOM_FURNISHINGS but NOT in _BUILDING_ROOMS | Add to _BUILDING_ROOMS with rooms: ["tavern", "bedroom", "bedroom"] |
| Blacksmith | "forge" in all maps | Rename alias or use "forge" |
| Temple | "shrine_major" in all maps | Alias or add "temple" with rooms: ["shrine_room", "shrine_room", "storage"] |
| Town Hall | NOT in _BUILDING_ROOMS | Add with rooms: ["great_hall", "study", "storage"] |
| General Store | NOT specifically | Add alias to market_stall_cluster or add "general_store" |
| Apothecary | NOT in _BUILDING_ROOMS | Add with rooms: ["study", "storage"] |
| Bakery | NOT in _BUILDING_ROOMS | Add with rooms: ["kitchen", "storage"] |
| House | "abandoned_house" | Add "house" alias |
| Guard Barracks | "barracks" fully defined | Use directly |

### Pattern 2: Wall Height and Portcullis Geometry

`generate_settlement()` accepts `wall_height` but this controls floor height, not wall perimeter height. The `_generate_perimeter()` function places wall segment objects with type strings — the Blender handler receiving "gate_portcullis" will need to generate actual portcullis geometry.

The fortress style config in `_building_grammar.py` has `"door": {"style": "iron_gate", ...}` — this is the correct style to apply to gate geometry. The wall segments should use the "fortress" style with `stone_fortified` material.

Hearthvale wall spec:
- Height: 5.5m (pass `wall_height=5.5` to generate_settlement)
- Material: stone_heavy / stone_fortified
- Details: battlement, arrow_slit windows
- Gate type: "gate_portcullis" — needs a dedicated handler that generates iron portcullis geometry via `blender_quality` or `blender_execute`

### Pattern 3: Secret Sewer Entrance

The current `_generate_perimeter()` generates wall segments and gates but has no concept of a secret entrance. This needs to be added as a post-generation step:

```python
# Post-generation: add sewer secret entrance
# Place a "sewer_entrance" prop near the river edge of the perimeter
# Type: "sewer_entrance" — prompt template already exists in blender_server.py:
# "dark fantasy sewer entrance, heavy iron grate set in cobblestone,
#  fetid water drainage, rat carvings on archway, corroded metal bars,
#  descending stone steps"
# Generate via asset_pipeline action=generate_3d with this prompt
# Position: wall perimeter, river-facing side
```

The sewer entrance prompt is already defined in `blender_server.py` (line 2278): `"sewer_entrance": "dark fantasy sewer entrance, heavy iron grate set in cobblestone..."`. Use this directly.

### Pattern 4: Market Square + Tripo Props

The market area uses district-based generation. For the 5+ Tripo-generated stalls:

```python
# Tripo stall prompts — one call per stall type for variety
stall_prompts = {
    "produce_stall": "dark fantasy medieval market stall, fresh produce display, wooden frame with canvas awning, pristine condition, PBR-ready, hand-crafted",
    "blacksmith_stall": "dark fantasy medieval weapon display stall, weapons hanging on frame, armor on mannequins, pristine, PBR-ready",
    "herbalist_stall": "dark fantasy medieval herbalist stall, hanging dried herbs bundles, clay jars, wooden shelves, pristine, PBR-ready",
    "fabric_stall": "dark fantasy medieval fabric merchant stall, rolled bolts of cloth, colorful banners, pristine, PBR-ready",
    "food_vendor": "dark fantasy medieval food vendor cart, cauldron over fire, wooden bowls stacked, ladle, pristine, PBR-ready",
}
# Central feature — fountain or well:
fountain_prompt = "dark fantasy medieval stone fountain, ornate carved basin, central column with flowing water effect, pristine gray stone, PBR-ready"
```

### Pattern 5: Layout Brief for Hearthvale Organic Layout

The `_derive_settlement_profile()` function parses `layout_brief` text to determine road pattern. For Hearthvale:

```python
layout_brief = "fortified castle-town, winding cobblestone, market square at center, radial streets from square"
# This triggers:
# - "organic" or "radial_spokes" pattern (market + radial keywords)
# - main_axis randomized
# - "market_quarter" district gets +score from market/square keywords
# - "military_quarter" gets +score from fortified keyword
```

### Anti-Patterns to Avoid
- **Using settlement_type="town" directly:** Building types are generic (`abandoned_house`, `forge`). Hearthvale needs exact named buildings. Override with a custom type entry.
- **Relying on random building_count:** D-05 mandates exactly 14 buildings. Use `(14, 14)` for count range.
- **Skipping wall_height override:** Default is 3.0m. Hearthvale needs 5.5m fortress walls. Always pass `wall_height=5.5`.
- **Generating all props at once with batch_process:** Tripo generation is credits-intensive. Generate and validate each unique stall type individually. Cache results for reuse.
- **Exporting before game_check:** The pipeline REQUIRES `blender_mesh action=game_check` before `blender_export`. Do not skip.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Town layout with buildings + roads | Custom placement loop | `generate_settlement()` | Already has MST roads, collision avoidance, multi-floor interiors, perimeter walls |
| Interior furnishing | Custom furniture placer | `_furnish_interior()` in settlement_generator | Activity zones, Poisson disk scatter, wall vs center placement already implemented |
| Interior lighting | Custom light placer | `_place_interior_lights()` | Per-room type light presets already calibrated |
| Market stall 3D models | Procedural geometry | `asset_pipeline action=generate_3d` with Tripo | AAA quality, PBR textures, delight pipeline |
| PBR texture extraction | Custom GLB parser | Phase 35 GLB texture extractor (already in asset_pipeline cleanup) | pygltflib + struct fallback, handles all PBR channels |
| Unity Addressables groups | Custom C# | `unity_build action=create_addressables_groups` | Pre-built with per-district streaming groups |
| Performance profiling | Manual Unity | `unity_performance action=profile_scene` | Automated FPS, draw call, VRAM measurement |
| LOD generation | Manual LOD baking | `asset_pipeline action=generate_lods` | lod_pipeline.py with silhouette preservation >85% |

**Key insight:** The entire settlement → interior → export → addressables → profiling pipeline is fully wired. Phase 38 is primarily a configuration and execution phase, not a new-system phase.

---

## Common Pitfalls

### Pitfall 1: Building Types Not Registered
**What goes wrong:** `generate_settlement("hearthvale")` raises `ValueError: Unknown settlement type 'hearthvale'` because the new type isn't in `SETTLEMENT_TYPES` when the handler runs.
**Why it happens:** `SETTLEMENT_TYPES` dict is defined at module load. New entries must be added before calling `generate_settlement`.
**How to avoid:** In the Blender handler (`worldbuilding_layout.py` or a new `hearthvale.py`), extend `SETTLEMENT_TYPES` before calling the function, or pass config directly through a new `generate_hearthvale()` entry point.
**Warning signs:** ValueError immediately when calling generate_settlement.

### Pitfall 2: Missing Building Type Mappings
**What goes wrong:** "tavern", "bakery", "apothecary", "town_hall", "general_store", "house" are not in `_BUILDING_ROOMS` or `_BUILDING_FOOTPRINTS` in settlement_generator.py. These buildings will get empty interiors (`room_functions: ["storage"]` fallback).
**Why it happens:** The settlement generator was built with fantasy camp/dungeon types. Hearthvale needs civilian building types.
**How to avoid:** Task 1 must add all 8 missing building type entries to `_BUILDING_ROOMS`, `_BUILDING_FOOTPRINTS`, `ROOM_FURNISHINGS`, and `_BUILDING_FLOORS`. This is non-negotiable before generation.
**Warning signs:** Buildings generate but interiors show only storage rooms. Furniture count is very low.

### Pitfall 3: Wall Height vs Floor Height Parameter
**What goes wrong:** Passing `wall_height=5.5` controls floor storey height, NOT perimeter wall height. The perimeter wall visual height depends on the Blender handler that instantiates wall segments — the `wall_height` parameter in `generate_settlement` feeds floor heights, not wall geometry.
**Why it happens:** `wall_height` parameter names are reused for different purposes.
**How to avoid:** The Blender handler for wall_segment pieces must be explicitly told the wall height. Pass `height=5.5` as a parameter in the perimeter element dict, or use a dedicated `hearthvale_wall_height` config key.
**Warning signs:** Walls appear at 3m height despite wall_height=5.5.

### Pitfall 4: Tripo Props Not Anchored to Terrain
**What goes wrong:** Tripo-generated market stalls float or clip into the ground because their Z position is set to 0 but the terrain is not flat.
**Why it happens:** Tripo import sets object origin to 0,0,0. Terrain around the market square must be flat (or props must be terrain-snapped).
**How to avoid:** In Task 2, ensure the market square area uses flat terrain (heightmap returns consistent Z in the center region). Alternatively, use `blender_execute` to snap props to terrain surface after import.
**Warning signs:** Contact sheet shows stalls floating or clipping.

### Pitfall 5: Portcullis Geometry Not Implemented
**What goes wrong:** The "gate_portcullis" type string in perimeter elements has no corresponding Blender handler. The handler will fall back to a generic box or produce an error.
**Why it happens:** gate types in `_generate_perimeter()` are strings that need matching Blender-side handlers. "gate_portcullis" is new.
**How to avoid:** Task 1 must implement portcullis geometry (iron bar grid) either via `blender_quality` or `blender_execute` with custom Python. This is a new handler, not a reuse.
**Warning signs:** Main gate appears as a flat box instead of an iron portcullis.

### Pitfall 6: Addressables Groups Too Coarse
**What goes wrong:** Exporting the entire town as one Addressable group means the full 14-building town loads at once. <5s load target fails.
**Why it happens:** Default export bundles everything together.
**How to avoid:** Use per-district Addressable groups per Phase 37 design: market district, civic buildings, residential buildings, fortifications as separate groups. Interior assets load only when entering a building (streaming group per building).
**Warning signs:** unity_performance shows >5s initial load time.

---

## Code Examples

### Registering the Hearthvale Settlement Type

```python
# Source: settlement_generator.py additions (Task 1)
SETTLEMENT_TYPES["hearthvale"] = {
    "building_count": (14, 14),
    "has_walls": True,
    "has_market": True,
    "has_shrine": True,
    "road_style": "cobblestone",
    "building_types": [
        "tavern", "blacksmith", "temple", "town_hall",
        "general_store", "apothecary", "bakery",
        "house", "house", "house", "house", "house",
        "guard_barracks",
    ],
    "prop_density": 0.7,
    "perimeter_props": ["wall_segment", "portcullis_gate", "corner_tower"],
    "layout_pattern": "organic",
}

# New _BUILDING_ROOMS entries required:
_BUILDING_ROOMS["tavern"] = ["tavern", "tavern", "bedroom", "bedroom", "storage"]
_BUILDING_ROOMS["blacksmith"] = ["smithy", "smithy", "storage"]
_BUILDING_ROOMS["temple"] = ["shrine_room", "shrine_room", "storage"]
_BUILDING_ROOMS["town_hall"] = ["great_hall", "great_hall", "study", "storage"]
_BUILDING_ROOMS["general_store"] = ["market", "storage", "storage"]
_BUILDING_ROOMS["apothecary"] = ["study", "storage"]
_BUILDING_ROOMS["bakery"] = ["kitchen", "kitchen", "storage"]
_BUILDING_ROOMS["house"] = ["bedroom", "kitchen", "storage"]
_BUILDING_ROOMS["guard_barracks"] = ["barracks", "barracks", "guard_post", "storage"]

# New _BUILDING_FOOTPRINTS entries:
_BUILDING_FOOTPRINTS["tavern"] = (12.0, 10.0)   # Large tavern
_BUILDING_FOOTPRINTS["blacksmith"] = (10.0, 8.0)
_BUILDING_FOOTPRINTS["temple"] = (14.0, 12.0)   # Imposing temple
_BUILDING_FOOTPRINTS["town_hall"] = (16.0, 12.0) # Town hall is largest civic building
_BUILDING_FOOTPRINTS["general_store"] = (9.0, 7.0)
_BUILDING_FOOTPRINTS["apothecary"] = (8.0, 7.0)
_BUILDING_FOOTPRINTS["bakery"] = (8.0, 7.0)
_BUILDING_FOOTPRINTS["house"] = (8.0, 6.0)
_BUILDING_FOOTPRINTS["guard_barracks"] = (14.0, 10.0)
```

### Generating the Settlement

```python
# Source: Blender handler / blender_worldbuilding action=generate_town
result = generate_settlement(
    settlement_type="hearthvale",
    seed=3810,                    # Fixed seed for reproducibility
    center=(0.0, 0.0),
    radius=65.0,                  # Large enough for 14 buildings + market + walls
    wall_height=3.5,              # Floor storey height
    layout_brief="fortified castle-town, winding cobblestone, market square at center, radial streets, military quarter, commerce district",
)
# result contains: buildings (14), roads, props, perimeter, interiors, lights
```

### Tripo Market Stall Generation

```python
# Source: blender_server.py asset_pipeline generate_3d pattern
# Call for each unique stall type (5 types minimum)
stall_prompts = [
    "dark fantasy medieval produce market stall, wooden frame, canvas awning, fresh vegetables and fruit display, pristine condition, PBR-ready, hand-crafted medieval",
    "dark fantasy medieval weapon merchant stall, iron weapons hanging, shield display, pristine, PBR-ready",
    "dark fantasy medieval herbalist and potion stall, hanging dried herbs, colored glass bottles, clay jars, pristine, PBR-ready",
    "dark fantasy medieval fabric merchant stall, rolled cloth bolts, colorful dyed fabrics, pristine, PBR-ready",
    "dark fantasy medieval hot food vendor cart, iron cauldron, wooden serving bowls, steaming soup, pristine, PBR-ready",
]
# Central fountain:
fountain_prompt = "dark fantasy medieval stone fountain, ornate carved stone basin, central column with lion-head water spouts, pristine gray stone, PBR-ready"
```

### Contact Sheet QA Sequence

```python
# Source: CLAUDE.md / blender_viewport tool
# Run after each generation step:
# 1. After generate_settlement: overhead + 4 cardinal ground-level angles
# 2. After Tripo prop placement: market square close-up
# 3. After wall/gate generation: exterior approach angle
# 4. Final QA: full town overhead + main gate approach + market interior + tavern interior
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Plot marker boxes only | Actual buildings placed on plots via handle_generate_town | Phase 32 | Buildings now appear in town, not empty boxes |
| Generic building types only | Phase 36 World Composer: district zoning, organic roads | Phase 36 | Market quarters, civic zones, correct building placement |
| Tripo blank textures | GLB texture extraction + delight pipeline | Phase 35 | Tripo props now have real PBR textures |
| Global RNG | Seed-based per-generator RNG | Phase 30 | Reproducible towns with fixed seeds |
| 3m flat walls | Fortress style config with battlements, arrow slits | Phase 32 | Visually distinct fortress architecture |

**Deprecated/outdated:**
- `world_generate_settlement` action: Not exposed as an MCP action. Use `blender_worldbuilding action=generate_town` which calls `handle_generate_town()` which calls `generate_settlement()` internally.
- settlement_type "abandoned_house" for residential buildings: Use new "house" alias for Hearthvale residential buildings.

---

## Open Questions

1. **Portcullis geometry implementation**
   - What we know: The "gate_portcullis" type string needs a Blender handler. blender_quality has door/chain generators. `blender_execute` can generate custom mesh.
   - What's unclear: Whether `blender_quality action=generate_prop type=door` with "iron_gate" style produces portcullis-quality geometry, or whether we need `blender_execute` with custom Python.
   - Recommendation: In Task 1, implement portcullis as a grid of vertical iron bars using `blender_execute` with bpy. This is straightforward and gives exact visual control.

2. **handle_generate_town vs generate_settlement call path**
   - What we know: `blender_worldbuilding action=generate_town` calls `handle_generate_town()` in worldbuilding_layout.py, which calls `generate_town_layout()` (a different function), NOT `generate_settlement()`.
   - What's unclear: Whether the two generation paths (generate_town_layout vs generate_settlement) are redundant or complementary. generate_settlement is more featureful (perimeter, interiors, lights).
   - Recommendation: For Hearthvale, call `generate_settlement()` directly from a new `handle_generate_hearthvale()` handler, bypassing the older generate_town_layout path. Register it as `world_generate_hearthvale` in `__init__.py`.

3. **Unity export — FBX vs glTF for town scale**
   - What we know: `blender_export` supports both. FBX is standard for Unity. A 14-building town with interiors may produce large FBX files.
   - What's unclear: Whether Unity's FBX importer handles the full hierarchy cleanly at this scale.
   - Recommendation: Export by district group (market, civic, residential, fortifications) as separate FBX files. Matches Addressables grouping and avoids monolithic export.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Blender (TCP bridge) | All generation | Assumed | 4.x | None — required |
| Tripo AI API | Market stall generation (D-10/D-11) | Yes (Phase 35) | v2 web API | Skip Tripo stalls, use procedural geometry |
| Unity (VeilBreakers3DCurrent) | Addressables + profiling | Assumed | 6.x URP | None for profiling step |
| settlement_generator.py | Town layout | Yes (Phase 36) | Current | N/A |
| _building_grammar.py | Interior system | Yes (Phase 33) | Current | N/A |
| pytest | Test validation | Yes | Current | N/A |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | Tools/mcp-toolkit/tests/ (conftest.py provides bpy stubs) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_settlement_generator.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH-13 | "hearthvale" settlement type registered and generates 14 buildings | unit | `pytest tests/test_settlement_generator.py::TestHearthvale -x` | Wave 0 |
| MESH-13 | Hearthvale perimeter has walls + portcullis gate + 2+ towers | unit | `pytest tests/test_settlement_generator.py::TestHearthvale::test_hearthvale_perimeter -x` | Wave 0 |
| MESH-13 | All 14 buildings have non-empty interiors (>= 5 furniture pieces each) | unit | `pytest tests/test_settlement_generator.py::TestHearthvale::test_hearthvale_interior_density -x` | Wave 0 |
| MESH-13 | New building types all have entries in _BUILDING_ROOMS, _BUILDING_FOOTPRINTS | unit | `pytest tests/test_settlement_generator.py::TestHearthvale::test_hearthvale_building_types -x` | Wave 0 |
| MESH-13 | Fixed seed 3810 produces identical output on repeated calls | unit | `pytest tests/test_settlement_generator.py::TestHearthvale::test_hearthvale_determinism -x` | Wave 0 |
| MESH-13 | Visual QA: contact sheet reviewed with no floating objects | manual | Review contact_sheet output images | N/A — manual |
| MESH-13 | Unity: <5s load, 60fps at 1080p | integration | unity_performance profile_scene | N/A — requires Unity |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_settlement_generator.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_settlement_generator.py::TestHearthvale` class — covers all MESH-13 unit tests (new test class, file exists)
- [ ] Hearthvale settlement type registration in settlement_generator.py — must exist before tests pass

---

## Project Constraints (from CLAUDE.md)

- Tool architecture: compound pattern, one tool name per domain, `action` param selects operation
- Always verify visually after Blender mutations — contact_sheet for thorough review (MANDATORY)
- Pipeline order: repair → UV → texture → rig → animate → export. Do not skip steps.
- Unity two-step: tool writes script, must recompile + execute. Follow `next_steps`.
- Game readiness: `blender_mesh action=game_check` before export
- `unity_performance action=profile_scene` after Unity setup
- Use seeds for reproducible generation (fixed seed=3810 for Hearthvale)
- Pure-logic grammars in `_*_grammar.py` files — no bpy dependency — for testability
- Blender handlers wire grammar output to scene objects

---

## Sources

### Primary (HIGH confidence)
- `settlement_generator.py` (2,386 lines) — direct code inspection: generate_settlement(), _generate_perimeter(), _place_buildings(), _furnish_interior(), SETTLEMENT_TYPES
- `_building_grammar.py` — direct code inspection: STYLE_CONFIGS, FACADE_STYLE_RULES, BuildingSpec, ROOM_SPATIAL_GRAPHS
- `blender_server.py` — direct code inspection: blender_worldbuilding generate_town action, asset_pipeline compose_map, sewer_entrance prompt templates
- `worldbuilding_layout.py` — direct code inspection: handle_generate_town(), district-to-building mapping
- `38-CONTEXT.md` — locked user decisions
- `36-CONTEXT.md` — road style, district zoning decisions

### Secondary (MEDIUM confidence)
- `STATE.md` — Phase 35 completion status, known gaps (building grammar boxes for gargoyles, building_quality.py disconnected)
- `ROADMAP.md` — Phase 38 success criteria
- `REQUIREMENTS.md` — MESH-13 specification

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — direct code inspection of all pipeline systems
- Architecture: HIGH — based on actual function signatures and data structures
- Pitfalls: HIGH — identified from actual code gaps (missing building type maps, wall_height semantics)
- Open questions: MEDIUM — portcullis and path routing need implementation decisions

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable codebase, month window)
