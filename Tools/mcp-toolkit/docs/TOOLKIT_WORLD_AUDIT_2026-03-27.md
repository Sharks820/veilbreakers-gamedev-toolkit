# VeilBreakers Toolkit World Audit

Date: 2026-03-27

## Target Envelope

- CPU: AMD Ryzen 7 5700, 8 cores / 16 threads
- GPU: NVIDIA GeForce RTX 4060 Ti
- RAM: 32 GB
- Practical iteration target:
  - terrain authoring at 256-384 height resolution for active passes
  - vegetation scatter capped in the low thousands during iteration
  - visible scene triangle budget near the existing Unity profiler default of 2M triangles
  - draw calls kept near the existing Unity profiler default of 2000

This machine is good enough for strong-looking authored regions and medium-scale procedural passes. It is not a license to generate unbounded city meshes, full-resolution terrain, heavy foliage, dense interiors, and hero materials in one shot.

## Changes Landed In This Pass

- Building openings now segment walls deterministically instead of relying on brittle booleans, so windows and doors cut real holes.
- Compose planners now:
  - keep map anchors from collapsing onto each other
  - derive room bounds and door markers for interiors
  - preserve `layout_brief` into settlement generation
- `compose_map` now preserves richer location intent and applies a generation budget:
  - passes `layout_brief`, `site_profile`, style, preset, and weathering hints where applicable
  - caps terrain resolution, vegetation density, and prop density according to a practical map budget

## Main Diagnosis

The toolkit is not mainly failing because the model is weak.

It is failing because the top-level world path still has three structural problems:

1. Intent loss
   - High-level prompts collapse into coarse handler defaults before they reach the geometry systems.
   - Result: different briefs converge to similar towns, similar buildings, and similar map density.

2. Shallow art grammar
   - The architecture system still has a thin style vocabulary and a thin façade vocabulary.
   - Result: geometry is more correct than before, but still reads procedural and repetitive instead of authored.

3. Missing composition contracts
   - Terrain, architecture, interiors, texturing, validation, and runtime export exist as separate tools, but are not enforced as one authoring pipeline.
   - Result: “feature exists” in the repo does not equal “feature participates in final output.”

## Current Gaps By System

### 1. Architecture And Building Quality

What exists:
- `blender_addon/handlers/_building_grammar.py`
- `blender_addon/handlers/building_quality.py`
- `blender_addon/handlers/modular_building_kit.py`
- `blender_addon/handlers/worldbuilding.py`

What is missing:
- The building grammar is still too small. It does not express district identity, façade hierarchy, annex logic, roofline rhythm, utility/service additions, or landmark silhouettes.
- The modular kit is structurally useful but visually thin. Most pieces are still panel-grade primitives with light style dressing.
- The castle generator is still massing-first, not authored-set-piece-first.
- The town generator still starts from plot markers and upgrades them, instead of being district-grammar-first from the start.

Why that matters:
- “AAA architecture” is not one good wall mesh. It is massing, hierarchy, silhouette, material breakup, and brief-specific asymmetry working together.

Required next layer:
- façade bays
- plinths
- pilasters / buttresses
- cornices / parapets / eaves
- dormers / chimneys / service stacks
- stair towers / bridges / annexes
- damage states and repair states

### 2. Terrain And Architecture Fitment

What exists:
- `blender_addon/handlers/environment.py`
- `blender_addon/handlers/terrain_advanced.py`
- `blender_addon/handlers/terrain_chunking.py`

What is missing:
- no proper cut/fill solver
- no stepped foundations
- no retaining walls
- no graded road apron generation
- no cliff anchoring / overhang support for large structures
- no rule that a district, castle, or academy must reshape itself around slope, ridge, or water edge

Why that matters:
- Without a foundation solver, buildings look dropped on terrain instead of constructed into it.
- This is one of the biggest reasons the output does not read “AAA.”

### 3. Layout Variety And Intelligent Mapping

What exists:
- `blender_addon/handlers/settlement_generator.py`
- `blender_addon/handlers/worldbuilding_layout.py`
- `src/veilbreakers_mcp/blender_server.py`

Recent improvement:
- settlement generation now reacts to `layout_brief`
- district/city layouts can vary by axial, radial, terraced, waterfront-edge, and organic patterns

What is still missing:
- no true prompt-to-layout compiler for region scale
- no land-use solver for district adjacency
- no vista-aware landmark placement
- no road hierarchy solver
- no history / culture layer that changes parcel shapes, plot sizes, or street widths
- no guarantee that different prompts with the same seed produce clearly different macro identities across a full map

What to add:
- settlement signature system:
  - water edge
  - spine axis
  - fortification logic
  - district adjacency rules
  - landmark class
  - road hierarchy
  - terrain adaptation mode

### 4. Interiors And Furnishing

What exists:
- linked interior shells
- room graph planning
- furnishing placement primitives

What is missing:
- room program generation by building role
- circulation and clearance constraints
- sightline logic for doors and stairs
- floor-to-floor stacking logic for real buildings
- furnishing categories tied to Tripo asset classes
- placement validation against collision, exits, and traversal width

Current failure mode:
- interiors are still shell-first and room-list-first, not gameplay-use-first.

### 5. Materials, UVs, And High-Level Texture Quality

What exists:
- strong texture/material helper surface in `texture_quality.py`
- UV, bake, wear, and trim-sheet handlers exposed by the Blender addon

What is missing:
- those material and UV systems are not automatically part of the world-generation path
- smart materials are mostly parameter/code generation, not a guaranteed applied pass after building generation
- no mandatory trim-sheet assignment for architectural kits
- no material consolidation pass for runtime draw-call sanity
- no final “hero surface treatment” pass that reacts to biome, weather, corruption, or narrative tone

Practical conclusion:
- the repo has material intelligence, but not a material pipeline for architecture/world output

### 6. Modeling, Topology, And Mesh Safety

What exists:
- topology analysis
- retopo tools
- UV tools
- LOD generation

What is missing:
- no end-to-end contract that every generated building or imported furnishing must pass topology, UV, and LOD validation before export
- no automatic split between hero meshes and repeatable kit meshes
- no mesh repair quarantine path for bad world assets comparable to the safer character path

This is one reason assets still “break models”:
- the toolkit can generate or import geometry
- it does not consistently enforce mesh correctness before downstream steps continue

### 7. Rigging And Editable Interactive Props

What exists:
- `riggable_objects.py`
- broad rigging tool surface in the Blender MCP

What is missing:
- no consistent pipeline for taking generated/imported world props through:
  - articulation tagging
  - rig template selection
  - deformation test
  - export validation
- no special path for common gameplay architecture props:
  - doors
  - gates
  - shutters
  - portcullises
  - chandeliers
  - bridge segments

### 8. Runtime Export And Unity Integration

What exists:
- Unity helpers for terrain blend, lighting, navmesh, LOD groups, interior streaming, and performance profiling

What is missing:
- world composition does not automatically produce a runtime-ready Unity package
- no guaranteed handoff from Blender chunking/district metadata to Unity additive scenes / Addressables
- no mandatory navmesh or occlusion step tied to export
- no automatic performance audit after world import

This is another orchestration gap:
- the Unity side has useful helpers, but the top-level world pipeline still returns too early

## Comparable Tools And What To Steal

### Dungeon Architect

Useful pattern:
- flow graph grammar that rewrites room-to-room structure into richer module chains
- modular snap generation instead of loose marker placement

What to steal:
- graph rewrite passes before geometry
- explicit room/module categories
- path criticality and gating in layout generation

Reference:
- https://docs.dungeonarchitect.dev/unity/snap-flow/snapflow-design-graph/

### ArcGIS CityEngine

Useful pattern:
- rule-based modeling from shape grammar
- footprint-to-building transformation with authored rule files

What to steal:
- district and façade rule files instead of hardcoding all style choices in Python
- “brief -> rule set -> building family” instead of “brief -> direct primitive generation”

Reference:
- https://doc.arcgis.com/en/cityengine/2023.1/get-started/get-started-rule-based-modeling.htm

### Houdini Engine

Useful pattern:
- reusable smart assets with exposed procedural parameters
- host-app editing and batch processing

What to steal:
- treat major VeilBreakers generators like HDAs:
  - stable parameters
  - viewport handles
  - reusable instances
  - batch-safe processing
- procedural controls must remain editable after placement

References:
- https://www.sidefx.com/products/houdini-engine/
- https://www.sidefx.com/faq/question/houdini-engine/

### World Creator

Useful pattern:
- terrain sync that carries height, color, texture, splat, and object data together
- bridge-level control over subdivision, reduction, and culling

What to steal:
- terrain import/export should be one coherent packet:
  - heightmap
  - splat layers
  - object scatter data
  - reduction controls
- large-scene culling defaults should exist to avoid editor crashes

References:
- https://docs.world-creator.com/reference/export/bridge-tools
- https://docs.world-creator.com/reference/export/bridge-tools/blender-bridge

### Gaia

Useful pattern:
- all-in-one terrain/world system with multi-tile focus and location variation

What to steal:
- explicit multi-tile world thinking
- biome-driven location variation and terrain dressing as a first-class system

Reference:
- https://www.procedural-worlds.com/products/indie/gaia/

## Recommended Implementation Order

### P0: Stop Losing Intent

- Continue pushing `layout_brief`, site, style, and role hints through every map/world entrypoint
- Add a map brief compiler that outputs:
  - region spine
  - district plan
  - landmark set
  - road hierarchy
  - terrain adaptation mode

### P0: Terrain-Foundation Solver

- Add:
  - stepped plinths
  - retaining walls
  - terrain cut/fill
  - road connection aprons
  - cliff anchors and terraces

### P0: Replace Primitive Façade Assembly With Real Architecture Kits

- Build a true façade grammar from modular families
- Separate hero landmark kit from repeatable district kit
- Add district-specific style packs:
  - fortress
  - port
  - slum
  - noble
  - sorcery academy
  - shrine / monastery

### P1: Furnishing Pipeline

- Add room program generation
- Add clearance validation
- Add Tripo category mapping for furniture classes
- Add “furnish by story role” not just room type

### P1: Mandatory Surface Pipeline

- After building generation, automatically run:
  - UV sanity
  - trim-sheet assignment
  - smart material pass
  - wear/biome overlay pass
  - LOD generation
  - export validation

### P1: Runtime Packaging

- Export districts/chunks with metadata for:
  - additive scenes
  - Addressables
  - navmesh zones
  - occlusion cells
  - streaming entrances for interiors

## Direct Answer To “Why Can’t The Model Figure It Out?”

Because the toolkit is still asking the model to improvise too much:

- the façade vocabulary is too thin
- the terrain fitment contract is incomplete
- the furnishing contract is incomplete
- the material pipeline is optional
- the runtime export path is not enforced

A stronger prompt cannot compensate for missing production contracts.

## Bottom Line

The toolkit is no longer failing only at “doors do not cut walls.”

The remaining bottleneck is now the next layer up:

- authored architectural grammar
- terrain-aware construction logic
- room-program-driven interiors
- mandatory material/UV/LOD validation
- runtime-safe packaging

That is the gap between “procedural tool demo” and “AAA-feeling world pipeline.”
