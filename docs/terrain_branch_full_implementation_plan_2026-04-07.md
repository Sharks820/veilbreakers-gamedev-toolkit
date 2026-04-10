# Terrain Branch Full Coverage Implementation Plan

Date: 2026-04-07
Branch: `feature/terrain-world-foundation`
Scope: Branch-only terrain toolchain, visual QA loop, Blender editing workflow, and AI terrain-understanding pathway

This plan is not a generic wishlist. It is based on the current branch code, the existing terrain-editing protocol, and the confirmed breakpoints in the active terrain path.

## Executive Summary

The branch already has useful foundations:

- deterministic world-space terrain sampling in `_terrain_world.py`
- vectorized noise generation in `_terrain_noise.py`
- pure erosion primitives in `_terrain_erosion.py`
- a real water-graph foundation in `_water_network.py`
- tile/chunk groundwork in `terrain_chunking.py`
- viewport capture and image-stat QA in `viewport.py`, `blender_server.py`, and `visual_validation.py`

The branch still fails visually for a small set of concrete reasons:

1. the tool does not enforce terrain semantics before mutation
2. visual verification is weaker than advertised
3. the strongest water logic is disconnected from the exposed waterfall workflow
4. cliffs and caves are still treated too much like local geometry events instead of structural terrain systems
5. material and asset passes consume weak masks
6. the AI workflow is not forced to observe the user's actual view, lock anchors, or make scoped corrections

If you fix only prompts, the branch will keep burning time on the same visual failures.

## Blender Authoring Ladder

The terrain branch needs one explicit Blender working contract:

1. inspect current scene state and current `.blend` path
2. inspect external Blender add-on/tool availability
3. identify edit scope and lock anchors
4. create object-local mesh checkpoints before destructive geometry edits
5. mutate in place whenever the terrain intent is still valid
6. run viewport/contact-sheet review
7. save the `.blend`
8. verify the save

Use the Blender surfaces in these roles:

- `blender_scene`: scene state, `.blend` save, save verification
- `blender_environment`: terrain generation and terrain mutation
- `blender_mesh`: local geometry repair and checkpointable mesh edits
- `blender_viewport`: mandatory visual QA
- `asset_pipeline`: orchestration and external-toolchain routing
- `toolchain_inspect_external`: discover installed/enabled Blender add-ons before choosing a path

Mesh checkpoints are not enough on their own. They are in-memory object snapshots only. They do not replace project saves because they do not preserve whole-scene state or survive restart.

## A. Confirmed Branch Defects That Must Be Fixed First

These are the current "stop the bleeding" items. Do these before any larger AAA refactor.

### A1. Remove fake capability and dead routing

- Remove or replace `env_generate_world_terrain` in `Tools/mcp-toolkit/blender_addon/handlers/__init__.py`.
- Replace it with a compatibility wrapper that drives the tile workflow, or remove it until the new pass controller exists.

### A2. Fix fake multi-angle visual verification

- `blender_server.py` sends `render_angle` requests for AAA verification.
- `__init__.py` currently maps `render_angle` to `handle_get_viewport_screenshot`.
- `handle_get_viewport_screenshot()` ignores yaw and pitch.

Required fix:

- add a real `render_angle` handler in `viewport.py`
- orbit a temporary review camera around a target object, feature anchor, or world focus
- render deterministic angle sets for:
  - macro composition
  - hero feature read
  - ground-level traversal read
  - waterfall side profile
  - cave-mouth framing

### A3. Make visual validation fail honestly

In `visual_validation.py`:

- fail on zero screenshots
- fail when fewer than the required angle count were captured
- report missing angles explicitly
- treat missing screenshots as a failed capture, not a skipped angle

### A4. Fix cliff overlay placement and scaling bugs

In `environment.py` and `_terrain_depth.py`:

- parent cliff objects before assigning local transform, or assign matrix in parent space
- compute cliff height from actual local relief only
- never multiply vertical relief by horizontal terrain extent

### A5. Remove world-height corruption in edit helpers

In `terrain_advanced.py`:

- remove unconditional `[0, 1]` clipping from world-space edit helpers
- keep normalized edit wrappers separate from world-unit helpers

### A6. Fix seam validation for semantic data

In `terrain_chunking.py`:

- extend seam validation to support `(H, W, C)` data
- return per-channel max/mean deltas
- validate height, wetness, cliff, splat, flow, and hero-feature channels separately

### A7. Retire the public standalone waterfall path

Current public route:

- `env_generate_waterfall` -> `terrain_features.generate_waterfall()`

Required fix:

- keep `terrain_features.generate_waterfall()` only as a geometry helper if needed
- remove it as the public terrain authoring path
- replace it with a pass that starts from terrain semantics and `_water_network.py`

### A8. Enforce project-save verification around terrain work

The branch now needs a real `.blend` persistence contract in addition to JSON pipeline checkpoints and mesh-local checkpoints.

Required workflow:

- inspect current file path and dirty state before mutation
- save before risky terrain passes
- save after accepted terrain passes
- use incremental saves for risky forks
- verify file existence and current-file match after save

Do not treat compose-map JSON checkpoints as project persistence. They are resumable pipeline metadata, not Blender project state.

## B. Real Root Causes Of The Visual Problems

### B1. "Grainy terrain" is not mainly a UV problem

The active branch terrain material path is dominated by:

- one splatmap built from slope plus coarse height percent
- vertex-color blending
- generic noise-based bump breakup

That means the visual graininess is mainly caused by:

- weak landform structure
- micro noise carrying too much visual burden
- no semantic cliff/wetness/erosion zoning
- no triplanar cliff read
- insufficient macro color breakup

UVs matter for some assets and hero meshes. They are not the main explanation for the terrain branch looking noisy or cheap.

### B2. Water is split across incompatible systems

Right now the branch contains:

- a real water graph and waterfall detection model in `_water_network.py`
- a standalone visible waterfall generator in `terrain_features.py`
- separate terrain mesh logic that does not require water-system authorship

This is why waterfalls take too long:

- placement logic is not the same as rendering logic
- terrain carving, water pathing, pool carving, and visual review are not one pipeline

### B3. The AI is allowed to mutate before it proves scene understanding

This is the biggest workflow issue.

The branch has a terrain-editing protocol in `.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md`, but the active terrain path does not enforce:

- live viewport sync
- locked reference empties
- surface classification before placement
- distance diagnostics before cave/waterfall edits
- minimal-diff correction passes

So the AI can still do technically legal but visually wrong edits.

### B4. Terrain semantics are still too implicit

The active pipeline still behaves roughly like:

- generate heightfield
- erode it
- mesh it
- assign materials
- scatter things

AAA terrain tools instead need:

- semantic scene read
- structural masks
- hero feature solving
- erosion/material/asset passes driven by meaning
- pass validation and rollback

## C. Target Architecture

Do not overload `_terrain_world.py` with orchestration.

### Keep `_terrain_world.py` as the pure world-field authority

Responsibilities:

- deterministic world-space height sampling
- region extraction
- world erosion wrapper
- tile seam helpers

### Add a new `terrain_pipeline.py` orchestrator

Create:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_pipeline.py`

Main responsibilities:

- accept scene intent, anchors, quality profile, and edit scope
- run ordered passes
- isolate seeds by pass
- save checkpoints
- collect validation outputs
- stop and rollback on failure

Required pass order:

1. `read_scene_intent`
2. `generate_macro_world`
3. `generate_structural_masks`
4. `solve_cliffs`
5. `solve_water`
6. `solve_caves`
7. `run_erosion_refinement`
8. `apply_material_zoning`
9. `populate_assets`
10. `run_validation`
11. `capture_visual_review`
12. `checkpoint_success`

## D. New Modules To Add

### D1. `terrain_semantics.py`

Create a hard state object. No edit happens without it.

Add:

- `TerrainIntentState`
- `TerrainSceneRead`
- `HeroFeatureSpec`
- `WaterSystemSpec`
- `CaveSystemSpec`
- `ProtectedZoneSpec`
- `CameraPrioritySpec`

Required outputs:

- major landforms
- focal region
- intended traversal corridors
- hero terrain features present and missing
- waterfall source/lip/drop/pool/outflow candidates
- cave candidate types and anchor regions
- protected zones
- requested edit scope
- success criteria

### D2. `terrain_masks.py`

This is the central data-product layer.

Generate and cache:

- slope
- curvature
- convexity / concavity
- ridge
- basin
- flow accumulation
- drainage
- wetness proxy
- erosion
- deposition
- talus
- cliff candidate
- cave candidate
- quiet zone
- hero-feature zone
- waterfall candidate
- riverbank zone
- Tripo placement zones

Export masks as:

- numpy arrays for logic
- named attributes for Geometry Nodes
- optional textures for material baking/preview

### D3. `terrain_cliffs.py`

Cliffs must become structural terrain events.

Add:

- `build_cliff_candidate_mask()`
- `carve_cliff_system()`
- `add_cliff_ledges()`
- `build_talus_field()`
- `insert_hero_cliff_meshes()`
- `validate_cliff_readability()`

Required cliff model:

- lip
- face
- ledges
- base/talus
- cliff-specific material zone
- cliff-context asset support

### D4. `terrain_waterfalls.py`

All waterfalls must come from the water system, not visible mesh requests.

Add:

- `detect_waterfall_lip_candidates()`
- `solve_waterfall_from_river()`
- `carve_impact_pool()`
- `build_outflow_channel()`
- `generate_mist_zone()`
- `generate_foam_mask()`
- `generate_wet_rock_mask()`
- `validate_waterfall_system()`

Waterfall data contract:

- source
- lip
- drop
- pool
- outflow
- screen-space target if anchor exists

### D5. `terrain_caves.py`

Replace generic cuts and standalone cave-mouth logic.

Add archetypes:

- fissure cave
- collapsed arch cave
- undercut shelf cave
- sinkhole cave
- tunnel cave

Add:

- `pick_cave_archetype()`
- `generate_cave_path()`
- `carve_cave_volume()`
- `build_cave_entrance_frame()`
- `scatter_collapse_debris()`
- `generate_damp_mask()`
- `validate_cave_entrance()`

### D6. `terrain_validation.py`

This is the pass/fail authority.

Add validators for:

- cliff presence and readability
- hero-feature count and spacing
- waterfall hydrology chain completeness
- pool existence and outflow
- cave entrance quality
- material zoning completeness
- asset density and overlap
- protected-zone violations
- quiet-zone preservation
- chunk seam continuity
- capture completeness for visual review

### D7. `terrain_checkpoints.py`

Add:

- `save_checkpoint(pass_name)`
- `rollback_last_checkpoint()`
- `save_preset(profile_name)`
- `restore_preset(profile_name)`
- `autosave_after_pass(pass_name)`
- `autosave_every_n_actions(n)`

### D8. `terrain_quality_profiles.py`

Profiles:

- `preview`
- `production`
- `hero_shot`
- `aaa_open_world`

Each must control:

- heightfield resolution
- erosion iterations
- mesh density
- review angle count
- asset density
- validation strictness
- checkpoint frequency
- screenshot requirements

## E. Existing File Changes

### E1. `_terrain_noise.py`

Stop returning one visual soup.

Add separated outputs:

- macro continental form
- ridge field
- meso breakup
- strata/shelf field
- micro detail field
- domain warp field

Required practices:

- micro detail must never define terrain silhouette
- strata should be a separate control field
- directional warping should be available for sedimentary/cliff regions
- anti-grain smoothing should suppress noisy peppering on broad forms

### E2. `_terrain_erosion.py`

Keep the existing erosion core but expand outputs.

Return:

- eroded heightfield
- erosion amount
- deposition amount
- wetness proxy
- talus zones
- pool candidates
- bank instability

Required note:

- the current pure hydraulic/thermal core is a good base
- the missing part is derived data products, not a total rewrite

### E3. `_terrain_depth.py`

Turn it into the terrain-analysis brain, not a detached feature helper module.

Add:

- ridge extraction
- basin detection
- cliff-lip detection
- waterfall candidate detection
- cave candidate detection
- camera saliency helpers
- line-of-sight helpers for main composition cameras

Keep mesh helper functions here only if they are low-level reusable geometry utilities, not public authoring entrypoints.

### E4. `_water_network.py`

This becomes the water authority.

Upgrade and consume it in the pipeline:

- river class logic
- width variation
- bank asymmetry
- basin fill / lake pooling
- waterfall insertion
- outflow solving
- tile continuity contracts
- foam/mist/wetness adjacency outputs

Do not allow separate waterfall authoring outside this model.

### E5. `terrain_materials.py`

Move from slope-only material mixing to semantic material zoning.

Add:

- `build_terrain_material_stack()`
- `assign_material_zones()`
- `generate_macro_color_breakup()`
- `generate_wetness_variation()`
- `apply_triplanar_on_cliffs()`

Material zones should consume:

- cliff mask
- wetness
- erosion
- deposition
- curvature
- quiet zones
- cave dampness

### E6. `environment_scatter.py` and `_scatter_engine.py`

Current scatter is decent for vegetation and weak for semantic terrain assets.

Replace or extend with:

- hero/support/filler role tags
- zone-based placement
- riverbank rules
- waterfall-base rules
- cliff rules
- cave-entrance rules
- plateau/open-field rules
- focal-area density falloff
- protected-zone exclusion

### E7. `terrain_chunking.py`

Chunk more than heights.

Export:

- height
- cliff masks
- wetness masks
- splat weights
- flow maps
- hero-feature continuity metadata
- asset masks
- water continuity contracts

Validate:

- height seams
- mask seams
- river continuity
- waterfall continuity
- hero-feature continuity

### E8. `environment.py`

Reduce it to compatibility wrappers plus strict pass-control helpers.

Add:

- `run_pass("macro")`
- `run_pass("cliffs")`
- `run_pass("water")`
- `run_pass("caves")`
- `run_pass("materials")`
- `run_pass("assets")`
- `run_pass("validation")`

Do not leave broad ad hoc terrain mutation logic here long term.

## F. User -> AI Understanding And Visual Workflow

This is the highest-value workflow change in the entire plan.

### F1. Required pre-edit scene read

Before any terrain edit, the AI must emit a structured scene read:

- current major landforms
- focal point
- existing hero features
- missing hero features
- waterfall source/lip/pool/outflow if relevant
- cave candidates
- intended edit scope
- protected zones
- exact success criteria

If this scene read is missing or confidence is low:

- no terrain mutation
- request more visual context or use more screenshots

### F2. Required visual inputs

For terrain generation or major correction:

- 1 user live viewport screenshot
- 1 contact sheet from deterministic review angles
- 1 semantic overlay pass when available:
  - cliff candidates
  - water paths
  - hero feature masks

Do not rely on a single beauty screenshot.

### F3. Named anchors

Support empties such as:

- `WF_LIP_TARGET`
- `WF_POOL_TARGET`
- `WF_OUTFLOW_TARGET`
- `CLIFF_HERO_A`
- `CAVE_ENTRANCE_A`
- `FOCAL_VALLEY_CENTER`
- `PROTECTED_RIDGE_A`

Anchor rules:

- AI must prefer anchors over visual guesses
- anchors must store local metadata where needed
- anchors must survive correction passes

### F4. Mandatory view-sync and placement protocol

The runtime toolchain must adopt the protocol currently living only in docs:

- get active viewport info before screenshot interpretation
- classify placement points against terrain surfaces
- run distance diagnostics when geometry relation is unclear
- create locked reference empties before multi-step edits

This is non-negotiable for:

- waterfalls
- cave entrances
- cliff hero pieces
- boolean or volume cave cuts

### F5. Scoped correction format

When something fails, corrections must be narrow:

Failures:

1. waterfall lip too far left
2. cliff face reads as slope from main camera
3. cave mouth lacks side framing

Correction rule:

- fix only the failed items
- do not regenerate unrelated terrain
- preserve protected zones and validated passes

### F6. Visual review modes

Add three review modes:

- `macro_review`
  - world composition
  - landform families
  - quiet vs detail balance
- `hero_feature_review`
  - cliff silhouette
  - waterfall chain readability
  - cave entrance readability
- `traversal_review`
  - riverbank logic
  - valley/canyon corridor readability
  - player-scale entrance and exit reads

## G. Blender-Specific AAA Practices To Enforce

### G1. Terrain

- use hybrid terrain: base terrain mesh plus hero meshes plus procedural masks
- keep macro, meso, and micro separated
- preserve silhouettes in geometry, not shader cheats
- use 16-bit or 32-bit map outputs for baked masks where needed

### G2. Cliffs

- use terrain carving for continuity
- use hero cliff meshes only to strengthen silhouette and local rock authority
- use triplanar materials on cliff faces
- add talus and broken ledges at the base

### G3. Water

- split water by function:
  - river surface
  - waterfall sheet/volume
  - impact pool
  - foam layer
  - mist volume
  - wetness mask or decal
- keep foam at energy points only
- do not sell the whole system with animated UV distortion alone

### G4. Caves

- use archetypes and volume workflows for hero entrances
- frame entrances with dedicated rock masses
- add shadow shelves and damp debris
- hide transitions with geometry and occlusion, not just noise

### G5. Materials

- macro color breakup must be separate from micro detail
- micro normals must be separate from displacement
- roughness variation matters as much as albedo
- texel density should be coherent across hero meshes and terrain

### G6. Assets

- place by role and context, not random scatter
- cluster around terrain logic
- use camera-priority weighting for hero assets
- preserve quiet areas

## H. Implementation Phases

### Phase 0. Stop The Bleeding

Fix now:

1. dead world command
2. fake `render_angle`
3. empty screenshot pass
4. cliff transform/height bugs
5. world-height clipping
6. multi-channel seam validation

### Phase 1. Semantics + Pass Controller

Build:

- `terrain_pipeline.py`
- `terrain_semantics.py`
- `terrain_validation.py`
- `terrain_checkpoints.py`

Goal:

- no mutation without scene understanding
- no pass without validation
- no failure without rollback

### Phase 2. Terrain Analysis And Mask Products

Build:

- `terrain_masks.py`
- expanded `_terrain_depth.py`
- expanded `_terrain_erosion.py`

Goal:

- terrain meaning becomes explicit and reusable

### Phase 3. Cliffs

Build `terrain_cliffs.py` and integrate before final water and materials.

Goal:

- cliffs stop reading like steep slopes

### Phase 4. Water And Waterfalls

Promote `_water_network.py` into the main pipeline and add `terrain_waterfalls.py`.

Goal:

- source/lip/pool/outflow chain becomes mandatory

### Phase 5. Caves

Add `terrain_caves.py`.

Goal:

- authored cave entrances with framing, dampness, and readability

### Phase 6. Materials

Refactor `terrain_materials.py`.

Goal:

- believable first-pass look before hero polish

### Phase 7. Assets

Upgrade scatter and asset logic.

Goal:

- Tripo and rocks feel terrain-aware, not random

### Phase 8. Chunk Semantics And Open-World Continuity

Upgrade `terrain_chunking.py`.

Goal:

- stream meaning, not just heights

### Phase 9. Presets, Profiles, And Correction Loops

Add:

- quality profiles
- preset JSONs
- targeted correction workflow

Goal:

- low-iteration, repeatable authoring

## I. Definition Of Done For This Branch

Do not call the branch AAA until these are true:

- terrain reads as 3 to 5 clear landform families from camera
- cliffs have lip, face, ledges, and talus
- waterfalls always satisfy source/lip/pool/outflow validation
- cave entrances look framed and grounded
- first-pass materials already look believable
- assets obey terrain context
- passes are checkpointed and reversible
- visual review uses real multi-angle capture
- the AI can make targeted corrections without re-breaking validated terrain
- quiet terrain exists alongside detail

## J. Recommended Build Order

This is the shortest path to visible improvement with the least wasted effort:

1. fix `render_angle`, screenshot failure rules, and dead/broken public routes
2. fix cliff transform and world-height corruption bugs
3. build semantics, validation, checkpoints, and pass orchestration
4. build mask products and expand terrain analysis outputs
5. rebuild cliffs
6. rebuild waterfalls on `_water_network.py`
7. add cave archetypes
8. overhaul material zoning
9. add semantic asset placement
10. export chunk semantics and profiles/presets

If you try to do materials or asset polish before steps 1 through 6, the branch will continue to look procedural for structural reasons, not polish reasons.

## K. Additional Legitimate Terrain Gaps Verified After Secondary Audit

These items were re-checked against the current terrain branch and adjacent toolkit systems.

Rule for this list:

- include only legitimate terrain-side gaps
- include deferred items if they still belong to terrain
- do not list systems that already exist elsewhere unless the terrain branch still fails to integrate with them

### K1. Active Terrain Gaps

- `NavMesh generation pipeline`
  Terrain export does not yet drive Unity NavMesh surfaces, non-walkable water masking, or exterior/interior nav handoff as one terrain workflow.
- `Audio zones and terrain-audio metadata`
  Terrain tiles do not export surface tags for footsteps, water proximity zones, cave/interior reverb zones, or ambient crossfade regions.
- `Occlusion-culling integration`
  Terrain/building/cliff outputs are not marked and handed off as occluder-ready data in the terrain pipeline.
- `Weather interaction and weather-variant terrain data`
  The terrain branch does not export wetness, snow accumulation, fog response, wind-reactive vegetation masks, or wet/dry material-state metadata.
- `Advanced water integration`
  Rivers and pools are still not treated as a semantic terrain pass that carves the heightfield, blends shorelines, exports water-depth context, and supports foam or wet-edge behavior.
- `Clear water continuation between nodes and tiles`
  `_water_network.py` tracks `network_id`, `segment_id`, node IDs, and tile edge contracts, but `get_tile_water_features()` reduces rivers and streams to anonymous waypoint runs. Downstream terrain/tile workflows therefore do not get a stable continuation contract for reconnecting the same water body across nodes, tile borders, and exported artifacts.
- `Tile splatmaps and wetness are still solved from local tile hydrology`
  `handle_generate_terrain_tile()` computes `moisture_map` from `compute_flow_map(heightmap)` after the tile has been cropped back out of the erosion margin. That means wetness-driven splatmaps are still derived from tile-local flow instead of one world hydrology solve, so water-adjacent material behavior can drift at tile borders.
- `Road and building terrain deformation`
  Current flattening support is not enough for terracing, foundation grading, ditches, bridge approaches, retaining walls, or structurally grounded placement.
- `Interior streaming terrain connectors`
  Exterior terrain/building outputs do not yet define door anchors, terrain-side transition zones, or export metadata needed to connect interiors cleanly.
- `Unity terrain holes export/import`
  The branch exports heightmaps and alphamaps, but not Unity terrain holes data. Cave mouths, sinkholes, and terrain-under-terrain transitions therefore cannot be represented through the Unity Terrain pipeline itself and must fall back to disconnected mesh-only workarounds.
- `Unity-native terrain detail and tree data export`
  The branch does not export Unity Terrain detail layers, detail prototypes, or tree-instance data from terrain semantics. Vegetation therefore remains disconnected from the TerrainData pipeline instead of being represented as Unity-native terrain grass/detail/tree products where appropriate.
- `Unity TerrainLayer material fidelity is still under-specified`
  The terrain setup templates only assign `diffuseTexture` and `tileSize` on each `TerrainLayer`. Normal maps, mask maps, and other terrain-layer material inputs are not imported through the terrain contract, so Unity terrain shading still loses important surface fidelity even when splat layers are present.
- `End-to-end terrain pipeline test`
  There is still no single terrain integration test that verifies generation -> erosion -> terrain materials -> chunking -> export -> Unity terrain setup as a continuous path.
- `Texture tiling and terrain-compression strategy`
  Terrain close-range breakup, anti-repetition, and unified texture-compression/export policy are still underspecified and not enforced by the branch.
- `Micro-undulation and close-read ground detail`
  The branch still lacks a dedicated pass for subtle ground breakup, small relief noise layering, clutter-ready masks, and anti-flatness treatment.
- `Bridge approaches and structural terrain transitions`
  Bridge placement lacks graded ramps, abutments, retaining geometry, and terrain shaping that visually and physically ties structures into the landform.
- `Cave entrance terrain framing`
  Cave mouths and dungeon entrances still need hillside cuts, rubble aprons, drainage shaping, and terrain framing as a consistent authoring pass.
- `Waterfall environment authoring`
  Beyond the public routing fix, the branch still lacks plunge-pool shaping, outflow carving, mist zones, spray-fed vegetation masks, and full source/lip/pool/outflow environment treatment.
- `Ford and shallow-crossing generation`
  There is no terrain-aware generator for shallow crossings, stepping stones, approach ramps, or broad low-flow traversal points.
- `Biome transition structure`
  Terrain transitions are still mostly material-driven and need structural transition logic such as scrub bands, hedgerows, wet margins, edge-tree lean zones, and shoreline transition kits.
- `Terrain-side streaming semantics`
  Chunk metadata exists, but the terrain branch still does not export rich streaming semantics for hero features, continuity zones, occlusion hints, and cross-chunk awareness.
- `Padded splatmap border policy`
  The branch still lacks padded alphamap/splatmap export and import policy for tiled terrain, so border compatibility and GPU edge-bleed prevention are not yet part of the terrain contract.
- `World splatmap generation scalability`
  `compute_world_splatmap_weights()` still processes large terrain regions with Python row/column loops, which becomes a real bottleneck for larger worlds and batch tile authoring.
- `Veil corruption as terrain logic`
  Corruption exists broadly in the toolkit, but the terrain branch does not yet provide a dedicated corruption intensity map, warped terrain behavior, fissure generation, or terrain-side corruption masks.
- `Boss-arena terrain sculpting depth`
  Boss spaces may exist elsewhere, but terrain-specific arena sculpting still lacks authored pits, raised pads, cover landforms, terrain hazards, and readable encounter-space shaping.
- `Destructible terrain/environment integration`
  The branch does not yet allow destruction outcomes such as craters, scorched patches, debris fields, or collapse marks to modify terrain outputs and terrain metadata.
- `Special terrain-type authoring depth`
  The branch still lacks a coherent terrain-side implementation path for frozen lakes, fog valleys, wetlands, multi-biome islands, lava corridors, arches, tunnels, crater stamps, and underwater-adjacent terrain.

### K2. Defer Until Pipeline Refactor

These are legitimate terrain items, but they should wait until the semantic pass pipeline exists because otherwise they will be bolted onto the wrong architecture.

- `Collision mesh strategy for buildings`
  Generic collision generation exists, but terrain-aware building collider strategy should be integrated alongside terrain/building placement and export contracts, not as an isolated patch.
- `Missing terrain presets at branch level`
  The branch has only a narrow set of base noise presets. More biome presets should be added after terrain semantics, masks, and material zoning are refactored so presets map to real terrain behavior instead of just noise parameters.
- `Advanced water behavior beyond routing`
  Meanders, tributary merge treatment, shoreline classes, lake-edge logic, and depth-driven water styling belong in the semantic water pass, not as one-off feature hacks.
- `Terrain audio system richness`
  Footstep variation by movement state, armor weight, ambient crossfading, and richer audio export should land after surface semantics and zone products exist.
- `Environmental storytelling overlays`
  Battle aftermath, camps, ruins, corruption scars, and other storytelling terrain overlays should come after semantics and correction loops can protect hero areas and preserve continuity.
- `Weather-specific terrain material variants`
  Wet/dry/snow/fog terrain-state products should wait until terrain materials are reworked around semantic masks and pass outputs.
- `LOD mapping from Blender terrain outputs to Unity`
  Generic LOD systems exist, but terrain-side LODGroup packaging should be attached to the chunk export/streaming refactor rather than patched into the current ad hoc flow.
- `Waterfall polish systems`
  Mist volumes, foam masks, plunge pools, wet rock zones, and downstream shaping should be completed as part of the dedicated `terrain_waterfalls.py` rebuild.
- `Farmland-to-forest and other ecotone kits`
  These should be implemented on top of semantic biome adjacency data and terrain masks, not direct post-scatter rules.
- `Weather-driven vegetation and surface response`
  Rain splash zones, snow loading, and wind-response masks belong after terrain-weather metadata exists.

### K3. Notes On Excluded Secondary-Audit Claims

These were not added as branch gaps because they are already implemented elsewhere, already fixed, or were overstated:

- splatmap transfer is no longer a missing branch feature
- vegetation exclusion zones already exist
- minimap/world-map support exists elsewhere in the toolkit
- Unity-side NavMesh, occlusion, weather, interior streaming, door, audio, and LOD tooling exist, but their terrain-branch integration remains a gap and is tracked above
- the earlier public waterfall routing issue has already been corrected, but the full semantic waterfall authoring system is still missing and remains tracked above

## L. Additional Deep-Dive Findings After Follow-Up Code Audit

These are still-open terrain bugs or terrain-side integration failures confirmed after the secondary-audit cleanup.

### L1. Still-open code defects

- `Cliff overlay parenting is still wrong for offset tiles`
  In `environment.py`, cliff overlays are positioned in world space and then parented to the terrain object without reconciling local transform. This will still misplace cliffs once chunks are offset from origin.
- `Cliff height math is still dimensionally wrong`
  In `_terrain_depth.py`, cliff height is still derived from normalized relief multiplied by horizontal terrain extent. That mixes vertical and horizontal units and can overstate cliff size.
- `World-height editing helpers still clip into normalized [0, 1]`
  `compute_erosion_brush()` and `flatten_terrain_zone()` in `terrain_advanced.py` still return `np.clip(..., 0.0, 1.0)`, which conflicts with the branch’s world-height direction.
- `Tile metadata still exposes conflicting transform contracts`
  `object_location` is the terrain-object center, while `position` still reports `[world_origin_x, 0.0, world_origin_y]`. That ambiguity remains unresolved.
- `Waterfall compatibility handler still overstates what it does`
  The new `handle_generate_waterfall()` can derive a candidate from `_water_network.py`, but it still feeds the selected feature into the legacy visible mesh generator and returns the first candidate only. This is a better public contract than before, but not a real terrain-aware waterfall authoring pass.
- `Chunk metadata export is still too thin for terrain streaming`
  `export_chunks_metadata()` exports bounds, LOD summaries, and neighbors, but not artifact paths, semantic masks, hero-feature channels, continuity contracts, or terrain-side streaming hints.
- `Tile artifact export is still limited to heightmap + optional alphamap`
  `_export_world_tile_artifacts()` still writes only RAW heightmap and optional alphamap. Water, semantics, masks, occlusion hints, audio zones, and continuity products are still absent.
- `Terrain layer export/import is still capped at exactly four layers`
  `_export_splatmap_raw()` only writes RGBA data and silently drops anything beyond four channels, while the Unity terrain setup templates still require exactly four `splatmap_layers`. That blocks richer terrain layer sets before the semantic export refactor.
- `Unity terrain import still hides missing alphamap failures`
  The Unity terrain setup templates only warn when an alphamap file is missing and then fall back to default terrain-layer coverage. Broken terrain texturing can therefore look like a successful terrain import.
- `Unity terrain import still hides missing heightmap failures`
  The same Unity terrain setup templates only warn when a RAW heightmap is missing and then create a flat terrain. That converts a hard terrain artifact failure into a misleading success path.
- `Unity terrain import still accepts corrupted RAW artifact sizes`
  The Unity terrain setup templates do not validate exact byte counts for heightmaps or alphamaps. Short files silently leave zeros/default coverage in place, and oversized files are effectively ignored past the consumed range, which hides broken terrain artifact dimensions instead of failing fast.
- `Multibiome terrain generation still swallows biome presentation failures`
  `handle_generate_multibiome_terrain()` treats biome material assignment as best-effort and skips biome vegetation-scatter failures silently, so terrain generation can report success even when biome presentation and grounding failed.
- `Chunking can still drop non-divisible world edges`
  `compute_terrain_chunks()` uses floor division for `grid_cols` and `grid_rows`, so world regions whose sample dimensions are not exact multiples of `chunk_size` can lose the trailing edge instead of emitting a final partial chunk or failing the contract.
- `Unity compatibility heightmap export can still distort non-square terrains`
  `handle_export_heightmap()` resizes to a power-of-two-plus-one target using the column count as the reference dimension, then applies the same square target to both axes with nearest-neighbor sampling. Non-square terrains can therefore be silently squashed into a square export.
- `Tile water feature extraction still drops stable water identity`
  `get_tile_water_features()` returns anonymous `river_paths` and `streams` waypoint lists even though the underlying water network has stable segment/node/network IDs and tile edge contracts. This prevents downstream terrain generation and export from expressing explicit water continuation between nodes and neighboring tiles.
- `Computed water edge contracts are still unused by the terrain pipeline`
  `_water_network.py` computes per-tile `WaterEdgeContract` data, but the active terrain-tile generation/export flow does not consume those contracts. The branch therefore computes water continuation metadata without actually enforcing or exporting it where terrain tiles are built.
- `Tile terrain texturing can still drift on heuristic height ranges`
  When explicit `height_range` values are not provided, `handle_generate_terrain_tile()` falls back to `_estimate_tile_height_range(...)` instead of a shared solved world range. Terrain layer zoning can therefore vary tile-to-tile even when neighboring tiles are part of the same world landform.
- `Waterfall detection is still tile-local in the public compatibility path`
  `handle_generate_waterfall()` builds a fresh `WaterNetwork` from the supplied tile heightmap instead of from a persisted world network or shared world region. Waterfall candidate detection in that path therefore lacks upstream/downstream world context and cannot guarantee cross-tile hydrologic continuity.
- `Unity terrain import still has no hole-mask contract`
  The Unity terrain setup templates create TerrainData from heightmaps and optional alphamaps only; there is no path for importing terrain hole masks or validating that terrain openings match authored cave/sinkhole entrances.
- `Unity terrain setup still ignores native detail/tree population`
  The Unity terrain setup path builds TerrainData from heightmaps and alphamaps only. It does not import detail layers, tree prototypes, or terrain-native vegetation placement from exported terrain semantics.
- `Unity terrain detail painting is still generic, not terrain-semantic`
  The available Unity detail-paint path fills density maps uniformly per prototype instead of consuming exported terrain semantics such as wetness, biome zones, exclusion masks, or traversal corridors. Even where Unity-native detail layers exist, they are not grounded in the terrain branch’s authored terrain meaning.
- `Tiled Unity terrain import does not validate unique grid occupancy`
  The tiled Unity setup script inserts tiles into `terrainMap["grid_x,grid_y"]` without checking for duplicate grid coordinates. Later duplicates silently overwrite earlier tiles in the neighbor map, which can hide broken tile manifests.
- `Tiled Unity terrain import does not validate tile-size or resolution consistency`
  The Unity tiled terrain setup path allows every tile to specify its own `size` and `resolution`, then wires neighbors anyway. That means adjacent tiles can be treated as neighbors even when their dimensions are incompatible for seamless terrain stitching.
- `Tiled Unity terrain import does not validate world-position continuity`
  Default positions are derived from `grid_x * size.x` and `grid_y * size.z`, but custom `position` overrides are accepted without any continuity checks. The branch can therefore report a successful tiled import even when neighbor-linked tiles are physically gapped or overlapped in world space.

### L2. Missing regression coverage

- There is still no regression test for cliff overlay placement on non-origin tiles.
- There is still no regression test protecting world-height terrain edits from normalized clipping.
- Current flatten and erosion-brush tests still explicitly encode clipped `[0, 1]` output, so the suite currently protects the old behavior rather than the branch direction.
- There is still no meaningful regression test for water-network-derived waterfall authoring beyond command registration/basic invocation.
- There is still no regression test for reconciling `object_location` vs `position` tile metadata contracts.
- Chunk export tests still validate lightweight JSON shape, not whether the export is sufficient for semantic terrain streaming or Unity-side terrain assembly.
- There is still no regression test for more-than-four terrain-layer export/import behavior.
- There is still no regression test requiring Unity terrain import to hard-fail when heightmap or alphamap artifacts are missing.
- There is still no regression test requiring Unity terrain import to reject RAW files with incorrect byte counts.
- There is still no regression test requiring multibiome terrain generation to surface biome-material or vegetation authoring failures.
- There is still no regression test proving chunking preserves full world coverage when world dimensions are not exact multiples of `chunk_size`.
- There is still no regression test protecting non-square terrain exports from square-resize distortion in `unity_compat` mode.
- There is still no regression test requiring tile water feature queries to preserve stable network/segment continuity identifiers.
- There is still no regression test proving computed `WaterEdgeContract` data is consumed by terrain-tile generation or export.
- There is still no regression test requiring wetness/splatmap products to remain world-consistent across neighboring tiles.
- There is still no regression test requiring a shared world height-range contract for tile texturing when explicit ranges are omitted.
- There is still no regression test proving the public waterfall compatibility path uses world-consistent, not tile-local, hydrology context.
- There is still no regression test requiring Unity terrain hole masks to be exported, imported, and aligned with authored terrain openings.
- There is still no regression test requiring Unity-native terrain detail layers and tree-instance data to round-trip from terrain export into TerrainData.
- There is still no regression test requiring Unity TerrainLayer imports to preserve normal/mask/material fidelity inputs.
- There is still no regression test requiring Unity-native terrain detail painting to follow exported terrain semantics instead of uniform fill.
- There is still no regression test requiring tiled terrain manifests to reject duplicate `(grid_x, grid_y)` occupancy.
- There is still no regression test requiring neighbor-linked tiles to share compatible `size` and `resolution`.
- There is still no regression test requiring tiled terrain world positions to remain contiguous with the declared grid.

## M. Additional Terrain Contract Gaps Found During Reconciliation Scan

These were surfaced while reconciling the earlier master-plan round findings against the branch execution plan.

### M1. Active terrain-side contract and workflow gaps

- `Fake performance validation`
  `performance_budget_check` is still a stub, but `blender_server.py` still wraps it into a success-shaped report with zero-default metrics. This can falsely claim terrain scenes are within budget.
- `Legacy terrain-origin drift in stamp workflow`
  The stamp path still carries older terrain-origin assumptions and needs explicit verification against centered terrain contracts.
- `World-height adapter inconsistency across terrain consumers`
  Some terrain consumers still normalize or infer altitude from `heights.max()` or clamp negative-space terrain meaning away, which keeps the branch contract inconsistent.
- `Legacy terrain APIs still protected by tests`
  Parts of the suite still preserve deprecated public terrain workflows and will resist the intended AAA refactor unless rewritten.
- `Standalone terrain actions skip checkpointing`
  Interactive terrain actions still operate outside the pass-checkpoint safety model used by `compose_map`.
- `Heuristic map-space conversion`
  `_normalize_map_point()` still uses a heuristic threshold that can mis-map valid unsigned positions on centered terrains.
- `Planned terrain location vs generated terrain placement drift`
  `compose_map` respects `terrain.location` during planning and routing, but terrain generation still creates the terrain object at origin, so non-origin plans can drift from actual generated terrain.
- `Flattening failures can disappear inside placement flow`
  `compose_map` tries heightmap flattening, then spline-deform fallback, and still proceeds if both fail. That hides terrain-prep failure as a later placement-quality problem.

### M2. Missing regression coverage for these contract gaps

- There is no regression test ensuring the performance budget path hard-fails or reports unknown when metrics are stubbed/missing.
- There is no focused regression test for centered-terrain stamp placement through the handler path.
- There is no branch-level regression test proving all major terrain consumers use the same world-height contract.
- There is no regression test requiring interactive terrain actions to create terrain checkpoints or rollback hooks.
- Existing compose-map planner tests do not fully guard the heuristic edge cases in `_normalize_map_point()`.
- There is no regression test proving `terrain.location` is honored by actual terrain generation, not only by planning helpers.
- There is no regression test requiring terrain flatten failure to surface as a hard terrain-prep failure instead of being silently swallowed.
