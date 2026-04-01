# Phase 38: Starter Town - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate "Hearthvale" — a complete, playable fortified castle-town that serves as the quality benchmark proving the entire procedural pipeline works end-to-end. This is the last great bastion, furthest from the Veil, where life carries on almost normally behind imposing walls — but refugees from the outer lands bring whispers of the horrors beyond.

</domain>

<decisions>
## Implementation Decisions

### Town Identity
- **D-01:** Hearthvale is a **fortified castle-town** — the last free safe haven, furthest from the Veil. Massive castle walls and battlements are the reason this place survives. Not a quaint village — a proper castle keep with an outer market district.
- **D-02:** Veil pressure 0.0-0.15 — pristine, unaffected by corruption. Props and buildings are in excellent condition. No corruption tinting.
- **D-03:** Atmosphere: bustling market life, warm tavern glow, cobblestone streets alive with commerce. But there's an undercurrent — refugees from outer lands huddle in corners, haunted by what they've seen. The contrast between "everything is fine" and "the world is ending out there" is the tone.
- **D-04:** This town must look **amazing** — it's the showpiece proving the entire pipeline. AAA quality visuals are non-negotiable.

### Building Roster (14 buildings)
- **D-05:** Exact roster:
  - 1 Tavern ("The Ember Hearth") — bar with stools, dining tables with plates/mugs, rooms upstairs
  - 1 Blacksmith — forge, anvils, weapon racks, tool storage
  - 1 Temple — altar, prayer benches, candelabras, stained glass effect
  - 1 Town Hall — meeting hall, official chambers
  - 2 Shops (general store + apothecary) — shelves, counters, displayed wares
  - 1 Bakery — ovens, flour bags, bread displays
  - 5 Houses — varied sizes, residential furnishing
  - 1 Guard Barracks — bunks, weapon racks, training equipment
- **D-06:** Every building gets **full interior density** — Phase 33 system at max: spatial graphs, activity zones, 10-15 clutter items per room, 2+ light sources per room. This is the quality benchmark.

### Fortifications
- **D-07:** Imposing fortress walls — tall gray stone walls (5-6m), angular guard towers with arrow slits, heavy iron portcullis, battlements with walkways. These walls are WHY this place survives.
- **D-08:** 2+ guard towers minimum, main gate with portcullis geometry
- **D-09:** Secret entrance: sewer grate by the river, leading under the walls. Hidden but discoverable.

### Market Area
- **D-10:** Central market square with 5+ stalls (Tripo-generated), central well or fountain, cobblestone ground, and dense street-level props (crates, barrels, hanging signs, lanterns, flower boxes).
- **D-11:** Market stalls and props generated via Tripo AI with prompts: "dark fantasy medieval, pristine, hand-crafted, PBR-ready" — no corruption variants needed for this town.

### Performance + Export
- **D-12:** Quality first, optimize after — generate at full quality (AAA textures, full interiors, all props), then run LOD pass + texture atlas optimization. Visual benchmark matters more than hitting exact fps on first try.
- **D-13:** Target: <5s load time on PC, 60fps at 1080p with all buildings and terrain visible. Profile via unity_performance action=profile_scene.
- **D-14:** Export as Addressables-ready package for Unity.

### Claude's Discretion
- River placement and terrain features around the town
- Specific Tripo prompt templates for each prop and stall type
- LOD distances and optimization passes
- Vegetation around town exterior (orchards, farmland for outskirts lots)
- Guard tower interior detail level
- Town hall interior layout

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline Systems (all preceding phases)
- `Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py` — generate_settlement(), enhanced in Phase 36
- `Tools/mcp-toolkit/blender_addon/handlers/road_network.py` — road generation
- `Tools/mcp-toolkit/blender_addon/handlers/map_composer.py` — compose_world_map(), Veil pressure
- `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` — Phase 32+33: buildings + interiors
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_grammar.py` — Phase 31+34: terrain + biomes
- `Tools/mcp-toolkit/blender_addon/handlers/asset_pipeline.py` — Phase 35: Tripo pipeline
- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py` — layout helpers
- `Tools/mcp-toolkit/blender_addon/handlers/export.py` — FBX/glTF export

### Phase 36 Context (World Composer decisions)
- `.planning/phases/36-world-composer/36-CONTEXT.md` — road style, district zoning, lot subdivision, prop density decisions

### Game Context
- VeilBreakers 10 brands: IRON/SAVAGE/SURGE/VENOM/DREAD/LEECH/GRACE/MEND/RUIN/VOID
- Hearthvale is brand-neutral — furthest from the Veil, no brand corruption

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 36 World Composer: road networks, district zoning, lot subdivision, street props — this phase CALLS all of it
- Phase 37 Pipeline Integration: compose_map end-to-end pipeline — this phase validates it
- Phase 33 Interior System: spatial graphs, clutter, lighting — used for every building interior
- Phase 35 Tripo Pipeline: texture extraction, delight, validation — used for all street props

### Established Patterns
- `generate_settlement()` is the main entry point — Phase 38 calls this with Hearthvale-specific parameters
- `compose_world_map()` orchestrates the full pipeline
- Seed-based deterministic generation — Hearthvale should have a fixed seed for reproducibility

### Integration Points
- `blender_worldbuilding action=generate_settlement` — the MCP action that triggers everything
- `asset_pipeline action=compose_map` — full pipeline composition
- `blender_viewport action=contact_sheet` — visual QA validation
- `unity_performance action=profile_scene` — performance validation after Unity import

</code_context>

<specifics>
## Specific Ideas

- Hearthvale should feel like the one place in VeilBreakers where you can breathe — warm stone, lantern light, the smell of bread from the bakery. But the refugees remind you it won't last.
- The imposing walls should be the first thing you see approaching — they dominate the skyline. Inside, the market square is the heart of the town.
- Visual QA: contact sheet must show overhead + 4 ground-level angles. No floating objects, no z-fighting, no missing faces.
- This is the quality benchmark — if Hearthvale doesn't look amazing, the whole pipeline fails its proof.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 38-starter-town*
*Context gathered: 2026-03-31*
