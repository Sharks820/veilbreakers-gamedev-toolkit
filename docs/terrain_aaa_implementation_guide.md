# Terrain AAA Overhaul Implementation Guide

Date: 2026-04-07
Scope: Terrain branch architecture, feature quality, visual validation, and authoring workflow

## Purpose

This guide reviews the proposed "AAA Terrain Branch Overhaul Spec" against the current codebase and turns the valid parts into a concrete implementation plan.

It is not a blind acceptance of the external spec.

The current terrain branch already has meaningful world-space, tiled-world, flow, splatmap, scatter, and visual-QA groundwork. The real problem is that these systems are disconnected. Terrain generation still behaves like a set of local tools instead of a staged terrain authoring pipeline with semantic intent, pass-level validation, and visual gates.

## Current Reality

### Already present and worth keeping

- `_terrain_world.py` already provides canonical world-space sampling, world-heightmap generation, tile extraction, seam validation, and whole-region erosion helpers.
- `environment.py` already supports terrain generation, tile generation, splatmap export, cliff overlays, biome presets, and tiled height export.
- `_water_network.py` already has a real world-level water graph with river widths, lakes, waterfall detection, tile edge contracts, and per-tile feature queries.
- `terrain_materials.py` already has world splatmap computation and layered terrain materials.
- `terrain_advanced.py` already has flow accumulation and drainage basin analysis.
- `blender_server.py` already has pipeline checkpoints, anchor planning, contact sheets, screenshots, and an AAA verification entrypoint.

### Blender tooling that should be treated as the authoring surface

These are the Blender-side control layers that matter for terrain/world work:

- `blender_scene`: inspect scene state, configure render units, save the current `.blend`, and verify that the save exists on disk.
- `blender_environment`: terrain generation, tile generation, paint/sculpt, river carving, water creation, heightmap export, and multi-biome terrain entrypoints.
- `blender_mesh`: local geometry edits, sculpt tools, booleans, retopo, multires, and `mesh_checkpoint` for object-local rollback before risky mesh edits.
- `blender_viewport`: screenshots, contact sheets, orthographic review, and deterministic angle renders for visual QA.
- `asset_pipeline`: `compose_map`, terrain/world orchestration, and external toolchain inspection/configuration routing.
- `toolchain_inspect_external` / `toolchain_configure_external`: runtime understanding of installed Blender add-ons and extensions.

The external add-on inventory is already formalized in `addon_toolchain.py`. Categories already tracked include:

- terrain
- architecture / interiors
- scatter / foliage
- UV / baking
- modeling helpers / non-destructive primitives
- surface detail / decals
- asset management
- layout variation
- LOD

This means the missing problem is not "we do not know about Blender tools." The missing problem is that the terrain workflow has not been forcing a consistent ladder for when to inspect them, when to prefer in-place edits, and when to persist the full `.blend`.

### What is actually failing

- Terrain shape is still too noise-led. Macro, meso, structural, and micro decisions are not separated.
- Cliffs are detected after the terrain exists and then decorated with overlays. They are not authored as systems.
- Waterfalls are detected or meshed, but not authored as a source -> lip -> drop -> pool -> outflow chain.
- Cave entrances are generated as local assets, not as context-aware geological archetypes.
- Material zoning is mostly slope/height based. It is not driven by reusable semantic masks.
- Asset scatter is contextual in places, but not role-tagged, camera-aware, or hero-feature aware.
- Validation exists for screenshots and seams, but not for terrain feature correctness.
- Checkpointing exists at compose-map level, but not as terrain-pass rollback.
- Visual review exists, but it is not a required gate for terrain passes and it is too image-stat-driven to catch terrain-read problems reliably.
- The repo previously had compose-map JSON checkpoints and mesh-local checkpoints, but not a first-class `.blend` project save/verify layer.

## Blender Save And Edit Layer

### Non-destructive edit rule

Do not default to deleting and regenerating the entire terrain/world root.

Preferred escalation order:

1. inspect scene state and external add-on/tool availability
2. lock anchors / identify the exact terrain scope
3. create a local mesh checkpoint before destructive object-level edits
4. run the smallest terrain or mesh edit that can solve the problem
5. capture contact sheet / required review angles
6. save the `.blend`
7. verify the save before continuing

Use full regeneration only when:

- the semantic source state is wrong
- the current pass failed before producing a stable reviewable artifact
- local fixes would create more state drift than restarting the pass

### Project save layer

The Blender scene tool should be treated as the project persistence authority:

- `blender_scene action=inspect`
  use this before editing to see current file path and dirty state
- `blender_scene action=save_project`
  use this to persist the active `.blend`
- `blender_scene action=verify_project_save`
  use this to confirm the file exists, has a non-zero size, and optionally matches the current open file

Suggested save cadence:

- save before any risky terrain pass
- save immediately after a visually approved pass
- save before export milestones
- save before switching from procedural generation to manual corrective edits
- save after any manual fix that would be expensive to reconstruct

Recommended mode choices:

- normal save for continuing the same working file
- incremental save when branching into a risky visual or sculpt iteration
- copy save only for backups, not as the main working path

Verification requirements:

- file exists on disk
- file size is non-zero
- current Blender file path matches the target path for non-copy saves
- optional SHA-256 hash capture for milestone saves

## Verdict On The External Spec

### Valid and should be implemented

- Terrain semantics as a required pre-edit state
- Reusable terrain mask generation
- Structural cliff authoring
- Hydrologic waterfall authoring
- Cave entrance archetypes
- Mask-driven materials
- Semantic asset placement
- Hard terrain validators
- Pass-level checkpoints and rollback
- Quality profiles and locked presets
- Protected zones and named anchors
- Scoped corrections that only touch failed features

### Valid goal, but the proposed file ownership should change

- Do not turn `_terrain_world.py` into the main orchestrator.
  Keep it as the world-field authority. Add a new orchestrator such as `terrain_pipeline.py` or `terrain_authoring.py`.
- Do not replace `terrain_materials.py` with a new material module.
  Extend the existing file and use helper submodules only if it becomes too large.
- Do not discard `_water_network.py`.
  Build the waterfall and river authoring system on top of it.
- Do not treat `visual_validation.py` as sufficient AAA validation.
  Keep it, but add terrain-aware visual and semantic gates above it.

### Overstated in the external spec

- Water support is not missing; it is incomplete.
  `_water_network.py` is already a solid base.
- Tiled-world terrain is not missing; it is partially implemented.
  `_terrain_world.py`, `environment.py`, and `terrain_chunking.py` already cover part of the world/tile contract.
- The branch is not just `noise -> erosion -> mesh -> decorate`.
  It already contains world-space sampling, tile exports, flow analysis, splatmaps, and scatter filters. The real issue is that these pieces are not coordinated by intent and validation.

## The Real Root Causes Of The Visual Problems

### Grainy terrain quality

This is not primarily a UV problem.

The main causes are:

- terrain silhouette is still too dependent on a single blended heightfield
- cliff structure is coming from slope thresholds and overlays instead of authored landform decisions
- noise bands are not exposed as separate outputs
- there is no explicit macro composition layer
- materials do not have a strong macro breakup pass

UV and projection issues matter on cliffs and some water surfaces, but they are secondary.

### Glitchy water and expensive waterfall iteration

The main causes are:

- waterfall generation is split across local mesh builders and water-network detection
- there is no waterfall contract object that must pass validation
- pool carving, outflow solving, foam placement, mist zones, and wet-rock zones are not a single authored pass
- water visuals are being built without enough terrain-semantic context

### Straight-cut rivers, canyons, cliffs, and terrain cutouts

The main causes are:

- cliff faces are discovered late from slope rather than placed early from structure masks
- river carving and canyon shaping do not use enough asymmetry, bank logic, deposition, or cliff interaction
- cave and waterfall systems do not force framing, debris, talus, and receiving geometry

## Mandatory New Architecture

Add a terrain pass orchestrator:

- `terrain_pipeline.py`

This module should own the terrain authoring pass graph and nothing else.

Suggested pass order:

1. `read_scene_intent`
2. `generate_macro_world`
3. `build_structural_masks`
4. `author_cliffs`
5. `author_water_system`
6. `author_caves`
7. `run_erosion`
8. `assign_materials`
9. `populate_assets`
10. `run_visual_and_semantic_validation`
11. `export_chunk_metadata`

Each pass must support:

- deterministic seed isolation
- checkpoint before mutation
- pass-local failure reporting
- rollback on validator failure
- named outputs stored in a shared terrain state object

## Mandatory New Modules

### `terrain_semantics.py`

Purpose: source of truth for what the terrain is supposed to mean

Suggested dataclasses:

- `TerrainIntentState`
- `TerrainSceneRead`
- `HeroFeatureSpec`
- `WaterSystemSpec`
- `CaveSystemSpec`
- `ProtectedZoneSpec`
- `TerrainAnchor`
- `TerrainSuccessCriteria`

Responsibilities:

- read current landform families
- infer or store focal region
- resolve named anchors
- define protected zones
- describe required hero features
- define success criteria for each pass

No terrain edit should run without a populated `TerrainIntentState`.

### `terrain_masks.py`

Purpose: reusable named mask generation and caching

Required masks:

- slope
- curvature
- concavity
- convexity
- ridge strength
- basin membership
- erosion
- deposition
- flow accumulation
- drainage
- wetness
- talus
- cliff candidates
- waterfall lip candidates
- cave candidates
- hero feature candidates
- asset zones
- quiet zones

This module should centralize logic currently scattered across:

- `_terrain_noise.py`
- `_terrain_depth.py`
- `terrain_advanced.py`
- `_water_network.py`

### `terrain_cliffs.py`

Purpose: structural cliff authoring

Required functions:

- `build_cliff_candidate_mask(state, masks)`
- `carve_cliff_system(state, masks, heightfield)`
- `add_cliff_ledges(state, masks, heightfield)`
- `build_talus_field(state, masks, heightfield)`
- `insert_hero_cliff_meshes(state, scene)`
- `validate_cliff_readability(state, masks, scene)`

Implementation rules:

- cliffs happen before final erosion and before final water dressing
- cliff system must explicitly create lip, face, ledges, and base
- hero cliff meshes should only reinforce silhouette where the heightfield cannot
- triplanar cliff material assignment must happen here or in the material pass via a cliff mask

### `terrain_waterfalls.py`

Purpose: waterfall authoring as a hydrologic chain

Required dataclass:

- `WaterfallFeature`

Required fields:

- source
- lip
- drop_path
- pool
- outflow
- width
- mist_zone
- foam_zone
- wet_rock_zone

Required functions:

- `detect_waterfall_lip_candidates(state, masks, water_network)`
- `solve_waterfall_from_river(state, waterfall_spec, water_network, heightfield)`
- `carve_impact_pool(heightfield, waterfall_feature)`
- `build_outflow_channel(heightfield, waterfall_feature)`
- `generate_mist_zone(waterfall_feature)`
- `generate_foam_mask(waterfall_feature)`
- `validate_waterfall_system(waterfall_feature, masks, anchors)`

Important note:

This module should extend `_water_network.py`, not replace it.

### `terrain_caves.py`

Purpose: cave entrance authoring by archetype

Required archetypes:

- fissure
- collapsed arch
- undercut shelf
- sinkhole
- tunnel

Required functions:

- `pick_cave_archetype(state, masks, context)`
- `generate_cave_path(archetype, context)`
- `carve_cave_volume(heightfield, path, archetype)`
- `build_cave_entrance_frame(archetype, entrance_data)`
- `scatter_collapse_debris(entrance_data)`
- `generate_damp_mask(entrance_data, water_context)`
- `validate_cave_entrance(entrance_data, anchors)`

This replaces generic hole logic with framed, readable entrances.

### `terrain_validation.py`

Purpose: hard terrain pass/fail rules

Required validators:

- cliff presence and readability
- hero feature count and spacing
- waterfall chain validity
- pool existence and outflow continuity
- cave entrance readability
- material zoning completeness
- asset overlap and density sanity
- protected-zone violation detection
- quiet-zone preservation
- chunk seam continuity for masks and water, not just height

This module should also expose structured failure output:

- `ValidationFailure`
- `ValidationReport`

### `terrain_checkpoints.py`

Purpose: pass-level save, rollback, preset persistence

Required functions:

- `save_checkpoint(pass_name)`
- `rollback_last_checkpoint()`
- `autosave_after_pass(pass_name)`
- `autosave_every_n_actions(n)`
- `save_preset(profile_name)`
- `restore_preset(profile_name)`

Important note:

`blender_server.py` already has compose-map checkpoint support. Reuse the storage approach and patterns, but add terrain-pass granularity.

### `terrain_quality_profiles.py`

Purpose: repeatable quality modes

Profiles:

- `preview`
- `production`
- `hero_shot`
- `aaa_open_world`

Each profile should control:

- heightfield resolution
- erosion iterations
- cliff mesh density
- water detail
- asset density
- validation strictness
- screenshot cadence
- checkpoint cadence

## Required Changes To Existing Files

### `_terrain_world.py`

Keep this file pure and authoritative.

Do not make it the pass orchestrator.

Valid upgrades:

- add pass-seed helpers
- add support for multi-channel field extraction
- add typed world-region bundles for height + masks + water metadata
- add shared export range helpers for tile packs

### `_terrain_noise.py`

Current state:

- good world-space sampling
- domain warping exists
- ridged noise exists
- no explicit macro/meso/structural band outputs

Required upgrades:

- add separate outputs for continental, macro, ridges, meso breakup, strata, and micro
- expose domain warp bands independently
- add directional warping
- add strata banding
- add anisotropic breakup
- add anti-grain smoothing
- output a `TerrainNoiseStack` object instead of only a final soup heightmap

Rule:

micro detail can perturb surfaces and materials, but must never define the major terrain read.

### `_terrain_erosion.py`

Current state:

- hydraulic and thermal erosion exist
- only returns a modified heightmap

Required upgrades:

- return erosion, deposition, bank instability, talus, wetness proxy, and drainage maps
- support channel-aware hydraulic behavior
- support base-of-cliff deposition and talus buildup
- support pool deepening around waterfall impacts

Important follow-up:

remove normalized-height assumptions in dependent editing helpers from `terrain_advanced.py`.

### `terrain_advanced.py`

Current state:

- useful flow analysis exists
- editing helpers still clip back to `[0, 1]`

Required upgrades:

- stop clipping flatten/erosion helpers to normalized height unless explicitly wrapped
- either convert helpers to world-unit terrain math or add a documented normalize/de-normalize wrapper
- expose basin, ridge, and drainage utilities through `terrain_masks.py`

### `_terrain_depth.py`

Current state:

- contains cliff detection
- contains local cliff, cave, waterfall, bridge mesh builders
- is mixing analysis and generation

Required upgrades:

- keep reusable geometry builders
- move analysis logic into `terrain_masks.py` and `terrain_semantics.py`
- move cliff/waterfall/cave orchestration into their dedicated feature modules

### `_water_network.py`

Current state:

- strongest existing foundation after `_terrain_world.py`

Required upgrades:

- support meander shaping rules
- bank asymmetry metadata
- basin fill and outflow solving
- waterfall lip classification from network context
- wetness adjacency masks
- foam and mist influence masks
- continuity validation across tile borders for both river paths and waterfall chains

### `terrain_materials.py`

Current state:

- layered materials exist
- world splatmap exists
- still largely slope/height driven

Required upgrades:

- drive layer assignment from semantic masks rather than only thresholds
- add wetness variation and spray-zone variation
- add macro color breakup independent from detail noise
- add cliff triplanar material path
- add scree/sediment and damp cave material zones
- vectorize `compute_world_splatmap_weights()` before pushing world-size passes harder

### `environment_scatter.py` and `vegetation_system.py`

Current state:

- contextual scatter and exclusions exist
- no asset-role semantics
- no hero/support/filler distinction

Required upgrades:

- add asset metadata tags
- add zone-aware asset rules
- add clustering strategies for cliff bases, waterfall bases, cave entrances, river bends, and quiet terrain
- add overlap and density validation
- add camera-priority weighting
- add water-proximity rock logic and wet-rock assignment

### `environment.py`

Current state:

- handler-based tool entrypoint
- single-tile path exists
- world-terrain handler is deprecated

Required upgrades:

- stop treating this as the terrain authoring brain
- delegate to `terrain_pipeline.py`
- expose pass execution hooks:
  - `run_pass("macro")`
  - `run_pass("cliffs")`
  - `run_pass("water")`
  - `run_pass("caves")`
  - `run_pass("materials")`
  - `run_pass("assets")`
  - `run_pass("validation")`
- enforce rollback on validation failure
- enforce checkpoint save on pass success

### `terrain_chunking.py`

Current state:

- height chunking and seam checks exist

Required upgrades:

- chunk and export semantic data, not just heights
- add support for splat, wetness, cliff, flow, and asset masks
- export hero-feature continuity data
- validate seam continuity for:
  - height
  - splat weights
  - wetness
  - water path continuity
  - waterfall continuity

## Missing Gaps Not Covered Well Enough By The External Spec

### 1. Add a terrain visual review layer

Create:

- `terrain_visual_review.py`

Why:

The project already has `visual_validation.py`, contact-sheet capture, and `aaa_verify`, but the current visual gate is too generic. It can detect brightness, contrast, and missing textures, but it cannot tell whether:

- the cliff reads as a slope from the hero camera
- the waterfall lip is misplaced
- the cave entrance lacks framing
- terrain detail is globally noisy instead of locally authored

Required behavior:

- capture contact sheets at named anchors and focal cameras after major passes
- compare against pass-specific expectations from `TerrainIntentState`
- require human-readable failure messages tied to actual anchors and features

### 1.1 Add taste-completion and visual acceptance testing

The branch still has no meaningful notion of "this terrain is visually complete" beyond generic image sanity checks.

That is a separate gap from basic screenshot validation.

Missing capabilities:

- no terrain-aware taste rubric for cliffs, caves, waterfalls, crossings, quiet terrain, and hero landforms
- no required camera set per feature type
- no visual completion criteria tied to silhouette quality, focal hierarchy, traversal readability, and dark-fantasy tone
- no regression snapshots for known-good terrain scenes
- no correction-loop testing that proves a fix improved the target view without damaging validated views

Required behavior:

- define required semantic cameras per terrain feature:
  - hero cliff view
  - waterfall side/profile view
  - cave approach view
  - traversal corridor view
  - top-down readability view
- score each capture against a terrain-specific rubric instead of only generic image statistics
- emit failure reasons in terrain language:
  - cliff reads as slope
  - waterfall lip is off-anchor
  - cave mouth is buried
  - scene lacks quiet ground against focal density
  - bridge or crossing does not ground into terrain
- store known-good contact-sheet baselines for regression comparison
- require correction passes to preserve already-approved views

Implementation note:

- `visual_validation.py` should remain the low-level image sanity layer
- taste-completion checks should live above it in the terrain review system and operate on anchors, semantics, and feature-specific expectations

### 2. Add camera saliency and focal composition helpers

The external spec mentions camera-priority generation mode, but the codebase needs an explicit implementation path.

Add to semantics/masks:

- focal valley center
- skyline silhouette score
- foreground/midground/background occupancy checks
- hero-feature spacing checks from primary view

### 3. Add quiet-terrain budgeting

One of the user-visible failures is over-detailed terrain with no rest areas.

Add a quiet-zone budget:

- some percentage of terrain must remain low-frequency and low-scatter
- detail density must fall off outside focal regions and hero features

### 4. Add correction contracts for agents

Before any terrain edit, the agent should produce:

- major landforms
- focal point
- hero terrain features
- waterfall source/lip/pool/outflow if applicable
- cave candidates

### 5. Add terrain contract integrity checks

The branch still has several terrain-contract failures that are not feature passes, but will keep breaking the pipeline until they are explicitly validated.

Missing checks:

- performance validation can still return a success-shaped result from stubbed metrics
- terrain consumers do not yet share one enforced world-height contract
- map-space conversion is still heuristic in compose flows
- terrain planning can respect `terrain.location` while actual terrain generation still ignores it
- terrain flattening can fail silently inside placement flow
- standalone terrain actions still bypass terrain-pass checkpoint rules

Required behavior:

- fail or mark unknown when terrain performance metrics are stubbed or missing
- enforce one terrain height contract across carving, scatter, paint, sampling, and export
- replace heuristic map-point normalization with an explicit coordinate-space contract
- make generated terrain placement honor the same location contract used by planning
- surface terrain-flatten prep failures as pass failures, not silent fallbacks
- require checkpoint hooks for interactive terrain mutation paths
- target edit scope
- protected zones
- success criteria

If the scene read is missing or contradictory, do not edit.

When correcting, the agent should emit only:

- failures
- targeted fixes
- protected zones to preserve

### 5. Add data-level feature IDs

Every hero feature should have a stable ID so passes can update the same thing instead of re-inventing it:

- `CLIFF_HERO_A`
- `WF_LIP_TARGET`
- `WF_POOL_TARGET`
- `CAVE_ENTRANCE_A`
- `FOCAL_VALLEY_CENTER`

This is necessary for autonomous iteration without scene drift.

## Recommended Execution Order

### Phase 1: Semantics, validation, and terrain-pass checkpoints

Implement first:

- `terrain_semantics.py`
- `terrain_validation.py`
- `terrain_checkpoints.py`
- `terrain_pipeline.py`

Without these, feature work will continue to generate token churn and scene breakage.

### Phase 2: Terrain masks and world-noise decomposition

Implement next:

- `terrain_masks.py`
- `_terrain_noise.py` band outputs
- `_terrain_erosion.py` derived maps
- `terrain_advanced.py` world-unit cleanup

This creates the inputs that cliffs, water, caves, materials, and assets should all share.

### Phase 3: Structural cliffs

Implement next:

- `terrain_cliffs.py`
- `_terrain_depth.py` cleanup
- `terrain_materials.py` cliff triplanar path
- `environment_scatter.py` talus/cliff clustering

This fixes one of the main silhouette failures first.

### Phase 4: Waterfalls and water context

Implement next:

- extend `_water_network.py`
- add `terrain_waterfalls.py`
- add water-adjacent rock and wetness logic
- add waterfall validation and camera-anchor review

This directly addresses the current waterfall pain and glitchy water behavior.

### Phase 5: Cave archetypes

Implement next:

- `terrain_caves.py`
- cave dampness and debris material zones
- entrance framing validators

### Phase 6: Material zoning overhaul

Implement next:

- mask-driven layer assignment
- macro breakup
- wet/damp/spray-zone material rules
- scree and sediment zones

### Phase 7: Semantic asset placement

Implement next:

- `terrain_assets.py`
- hero/support/filler rules
- water/cliff/cave clustering
- density and overlap validators

### Phase 8: Chunk meaning export and seam validation

Implement next:

- semantic chunk exports
- multi-mask seam checks
- river and waterfall continuity checks
- padded splatmap border compatibility

### Phase 9: Profiles and presets

Implement last:

- `terrain_quality_profiles.py`
- terrain preset JSON schema
- preset locking and restore flow

## Definition Of Done For This Branch

Do not call the terrain branch AAA until all of these are true:

- landforms read as intentional families from hero cameras
- cliffs have lip, face, ledges, base, and material separation
- waterfalls always validate as source -> lip -> pool -> outflow
- cave entrances read as authored geological structures
- materials look believable before hand-polish
- assets react to semantic zones instead of random density fields
- terrain passes are checkpointed and reversible
- failed features can be corrected without scene-wide collateral damage
- quiet terrain exists and is intentionally preserved
- visual review is required, not optional, after major terrain passes

## Short Implementation Summary

The external feedback is mostly right about the destination and partly wrong about the starting point.

The shortest valid path is:

1. add terrain semantics
2. add terrain validators
3. add terrain-pass checkpoints
4. centralize terrain masks
5. rebuild cliffs first
6. rebuild waterfall authoring on top of `_water_network.py`
7. add cave archetypes
8. convert materials to semantic mask inputs
9. add semantic asset placement
10. make visual review a hard gate

That path fixes the actual visual failures without throwing away the world-space and tile foundations that already exist.

## Consolidated Verified Gap Index

Use this as the pointer map for the verified terrain-gap inventory.

### Structural code defects and broken contracts

See:

- `terrain_tool_bug_audit_2026-04-07.md`
- `terrain_branch_full_implementation_plan_2026-04-07.md` section `L`
- `terrain_claude_master_plan_2026-04-07.md` sections `25` and `28`

Covers:

- cliff transform-space bugs
- cliff height math bugs
- world-height clipping bugs
- weak visual-verification contracts
- tile metadata contract drift
- weak waterfall compatibility routing
- thin chunk/export artifact contracts
- four-layer terrain export/import ceiling
- Unity terrain import fallback paths that hide missing terrain artifacts
- Unity terrain import not validating RAW artifact byte counts
- tiled terrain import not validating grid occupancy, dimension consistency, or physical continuity
- Unity-compat heightmap export distorting non-square terrains
- silent multibiome material/vegetation failure paths
- fake performance validation
- map-space normalization drift
- terrain-location drift
- flatten-failure swallowing

### Missing terrain systems and integrations

See:

- `terrain_branch_full_implementation_plan_2026-04-07.md` section `K1`
- `terrain_claude_master_plan_2026-04-07.md` section `27.1`

Covers:

- NavMesh integration
- terrain-audio metadata
- occlusion integration
- weather-state terrain data
- advanced water integration
- road/building deformation
- terrain-side interior connectors
- terrain end-to-end integration testing
- texture anti-repetition/compression policy
- padded splatmap/alphamap border policy
- world splatmap generation scalability
- non-divisible world chunk coverage
- clear water continuation between nodes and tiles
- world-consistent hydrology for tile wetness, splatmaps, and waterfall detection
- Unity terrain holes / opening-mask pipeline
- Unity-native terrain detail and tree-data pipeline
- Unity TerrainLayer material-fidelity pipeline
- micro-undulation and ground detail
- bridge approaches
- cave entrance framing
- waterfall environment authoring
- fords and shallow crossings
- structural biome transitions
- terrain streaming semantics
- terrain corruption logic
- boss-arena terrain sculpting
- destructible terrain integration
- special terrain-type depth

### Deferred terrain items that still belong to the branch

See:

- `terrain_branch_full_implementation_plan_2026-04-07.md` section `K2`
- `terrain_claude_master_plan_2026-04-07.md` section `27.2`

### Visual taste-completion and acceptance testing

See:

- this guide section `1`
- this guide section `1.1`

### Terrain contract integrity and safety model

See:

- this guide section `5`
- `terrain_branch_full_implementation_plan_2026-04-07.md` section `M`
- `terrain_claude_master_plan_2026-04-07.md` section `28`

### Missing regression coverage

See:

- `terrain_branch_full_implementation_plan_2026-04-07.md` sections `L2` and `M2`
- `terrain_claude_master_plan_2026-04-07.md` section `28.2`
