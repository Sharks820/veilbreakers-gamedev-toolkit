# Terrain Branch Master Plan For Claude

Date: 2026-04-07
Branch: `feature/terrain-world-foundation`
Repo: `Sharks820/veilbreakers-gamedev-toolkit`
Audience: Claude / implementation agent
Scope: Full terrain branch overhaul to AAA terrain authoring quality, including branch-validated defects, architecture, visual workflow, Blender practices, and terrain AI understanding requirements

This document is the consolidated handoff.

It includes:

- the original Codex AAA terrain quality direction
- the branch-grounded implementation plan
- the validated bug audit
- the follow-up Gemini validation
- the must-fix visual/AI workflow requirements

This is not a “prompt tuning” task.
This is a terrain tool architecture and execution quality task.

## 1. Mission

Turn the current terrain branch from a good procedural base into an AAA-grade terrain authoring system that can produce:

- believable macro composition
- real cliff systems
- hydrologically valid rivers and waterfalls
- authored cave entrances
- believable first-pass materials
- intelligent Tripo and terrain-asset placement
- checkpointed and reversible edits
- repeatable profiles and presets
- scene-aware, low-iteration AI direction
- visually grounded user-to-AI editing

Do not treat this as “make terrain prettier.”
Treat this as “replace a disconnected procedural terrain workflow with a semantic, validated, visual-first terrain authoring pipeline.”

## 2. What Is Already Good In This Branch

The branch already has real foundations. Do not throw them away.

Keep and build on:

- canonical world-space terrain sampling in [_terrain_world.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_terrain_world.py)
- theoretical global normalization in [_terrain_noise.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py)
- pure hydraulic and thermal erosion primitives in [_terrain_erosion.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py)
- vectorized world-consistent noise generation in [_terrain_noise.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py)
- tile extraction and seam helpers in [_terrain_world.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_terrain_world.py)
- flow and drainage groundwork in [terrain_advanced.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py)
- strong water-graph foundation in [_water_network.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_water_network.py)
- chunk/LOD groundwork in [terrain_chunking.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py)
- terrain export path in [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)
- viewport capture and review infrastructure in [viewport.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/viewport.py) and [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)
- terrain editing protocol in [TERRAIN_EDITING_PROTOCOL.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md)

The real problem is not that the branch lacks every ingredient.
The real problem is that the ingredients are disconnected, semantically weak, and not enforced through a visual validation loop.

## 3. Validated Current Branch State

The following branch conditions were validated:

- current branch is `feature/terrain-world-foundation`
- current commit is `71e6451e95c049a04b34284c0d0dd5e83765054e`
- canonical world sampling exists
- centered-terrain offset fixes exist in active code paths
- dangerous legacy terrain fallbacks were removed in related tooling
- critical vegetation aliases were integrated into `_mesh_bridge.py`
- the C# tiled terrain `.GetComponent<Terrain>()` fix is present
- explicit world anchors are clamped in `blender_server.py`

Important working-tree note:

- `_terrain_erosion.py` currently contains an uncommitted fix for the droplet speed scaling bug
- that fix passed `18` erosion tests locally
- do not lose that change

## 4. Current Branch Diagnosis

### 4.1 Why the branch is still not AAA

The branch still behaves too much like:

- noise
- erosion
- mesh
- decorate

AAA terrain tools behave more like:

- composition
- semantic scene read
- structural masks
- hero feature solving
- erosion refinement
- material zoning
- asset logic
- validation
- checkpoint
- scoped corrections

That difference is why the current branch still produces:

- blanket terrain
- cliffs that read like steep slopes
- waterfalls that read like placed geometry
- cave mouths that read like cuts/booleans
- weak first-pass material zoning
- context-light asset placement
- too much iteration
- low trust in autonomous edits

### 4.2 Biggest visual failure causes

The biggest visual problems are:

- no enforced terrain semantics before edits
- visual QA is weaker than advertised
- water logic is split across incompatible systems
- cliffs are handled too late and too locally
- cave entrances are not authored as entrance systems
- materials still consume weak masks
- asset logic is not semantic enough
- AI is not required to ground edits in the user’s actual view and locked anchors

## 5. Must-Fix Branch Defects

Treat every item below as must-fix.
Do not rank them down to “later.”

### 5.1 Fake multi-angle visual verification

Problem:

- `aaa_verify` requests `render_angle`
- `render_angle` is currently aliased to normal viewport screenshot capture
- yaw/pitch are ignored

Files:

- [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)
- [__init__.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/__init__.py)
- [viewport.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/viewport.py)

Required fix:

- implement a real `render_angle` handler
- use a deterministic review camera
- support target object, target anchor, or terrain focal region
- render true macro, hero, side-profile, top, and ground-level review angles

### 5.2 Visual gate false-passes on zero screenshots

Problem:

- `aaa_verify_map([])` currently returns success

File:

- [visual_validation.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_validation.py)

Required fix:

- zero screenshots must hard-fail
- underspecified angle count must hard-fail
- missing-angle reporting must be explicit
- update tests that currently encode the broken success-on-empty behavior

### 5.3 Public waterfall path bypasses real water logic

Problem:

- public waterfall route still points to standalone mesh generation
- `_water_network.py` is not the active terrain-water authority

Files:

- [__init__.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/__init__.py)
- [terrain_features.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py)
- [_water_network.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_water_network.py)

Required fix:

- retire the standalone waterfall path as the public workflow
- integrate `_water_network.py` into the terrain pipeline
- drive waterfalls from river semantics

### 5.4 Dead public world-generation route is still exposed

Problem:

- `env_generate_world_terrain` is still publicly registered
- the handler immediately raises `NotImplementedError`

Files:

- [__init__.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/__init__.py)
- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)

Required fix:

- remove the public route now, or replace it with a compatibility wrapper over the tile/pipeline workflow
- do not leave dead commands advertised to agents

### 5.5 Terrain editing protocol is doc-only

Problem:

- the terrain editing protocol exists, but is not enforced in runtime terrain workflows

File:

- [TERRAIN_EDITING_PROTOCOL.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md)

Required fix:

- turn protocol helpers into runtime utilities
- require them for terrain mutation near existing geometry
- fail unsafe edits lacking view sync, anchors, or surface classification

### 5.6 Per-tile erosion overlap is not seam-exact

Problem:

- current `erosion_margin` overlap path reduces mismatch
- it does not guarantee exact adjacent seam agreement after independent erosion

File:

- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)

Required fix:

- support scalable distributed erosion with halos and seam blending
- preserve whole-world erode-then-split for smaller worlds and exact mode
- add validation for independently eroded adjacent tiles

### 5.7 Large-world precision strategy is missing

Problem:

- branch relies on world-space floats without a floating-origin or local-tile precision strategy

Required fix:

- adopt large-world coordinate strategy
- keep generation in stable high-precision coordinate space
- support camera/tile-relative rendering and export contracts

### 5.8 Splatmap border padding is missing

Problem:

- splatmaps export as exact raw dimensions
- Unity import path reads exact terrain alphamap size
- there is no padded-border path to prevent GPU edge bleed

Files:

- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)
- [scene_templates.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/scene_templates.py)

Required fix:

- support padded alphamap export
- support padded alphamap import
- support neighbor-border duplication or tile-border bleed copying

### 5.9 Tile metadata contract is still ambiguous

Problem:

- tile generation returns both `object_location` and `position`
- `object_location` is the terrain object center transform
- `position` is the tile min-corner world location
- both are returned without a hard consumer contract

File:

- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)

Required fix:

- define one canonical transform contract for downstream consumers
- if both center and bounds are returned, name them explicitly and document which systems must use which
- do not leave terrain, water, scatter, and export consumers guessing

### 5.10 Public seam validation is still scalar-only

Problem:

- the public `terrain_chunking.validate_tile_seams()` path still assumes scalar samples
- it cannot validate multi-channel semantic tiles such as splatmaps, wetness masks, or flow masks

File:

- [terrain_chunking.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py)

Required fix:

- support `(H, W, C)` seam validation
- return per-channel max/mean seam error
- validate semantic continuity, not just height continuity

### 5.11 Semantic masks are still too shallow

Problem:

- cliffs, water, caves, materials, and assets still do not consume a rich enough mask stack

Required fix:

- build a proper semantic terrain mask layer

### 5.12 Material zoning is still too slope-driven

Problem:

- current material weighting is still mostly slope plus coarse height percent plus optional moisture

Required fix:

- move material zoning to semantic masks
- add triplanar cliff material logic
- add macro breakup and wetness variation

### 5.13 Asset placement is still not terrain-semantic enough

Problem:

- terrain assets are not yet driven by cliff, riverbank, waterfall-base, cave-mouth, and quiet-zone semantics

Required fix:

- build semantic placement zones and role-based asset logic

### 5.14 Current tests encode some broken behavior and missing cases

Problem:

- current tests explicitly assert that `aaa_verify_map([])` passes
- current terrain tiling tests verify whole-world erode-then-split seams, but do not verify independently generated adjacent tiles with erosion margins

Files:

- [test_aaa_visual_verification.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_aaa_visual_verification.py)
- [test_terrain_tiling.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_terrain_tiling.py)

Required fix:

- rewrite tests to enforce the desired terrain-validation behavior, not current broken behavior
- add independent-adjacent-tile erosion seam tests
- add padded alphamap border tests
- add real multi-angle render verification tests

### 5.15 Performance validation is still fake

Problem:

- `performance_check` is exposed in `blender_server.py`
- the addon-side `performance_budget_check` handler is still a stub returning `{"status": "ok", "budget": "not_implemented"}`
- the server then interprets missing totals as `0` triangles and `0` draw calls, which can false-pass the summary
- there are currently no tests covering this path

Files:

- [__init__.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/__init__.py)
- [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)

Required fix:

- replace the stub with a real scene-wide performance collector
- count terrain, water, foliage, rock, and cliff mesh budgets separately
- report actual triangle counts, instance counts, material counts, and draw-call proxies
- hard-fail or return `not_available` when the measurement is not implemented
- add tests so a stub cannot silently report success

### 5.16 `terrain_advanced.apply_stamp_to_heightmap()` still uses a stale terrain-origin contract

Problem:

- `handle_terrain_stamp()` passes `terrain_origin=(obj.location.x, obj.location.y)`
- the rest of the branch treats terrain object location as the terrain center
- `apply_stamp_to_heightmap()` still converts with `(position - origin) / terrain_size`
- that math interprets `terrain_origin` like a min corner instead of a centered terrain transform

Files:

- [terrain_advanced.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py)
- [test_terrain_advanced.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_terrain_advanced.py)

Required fix:

- make stamp placement use the same centered-terrain world contract as the rest of the branch
- update runtime stamping and pure-logic helpers together
- rewrite the tests so they validate the centered contract, not the old corner-origin assumption

### 5.17 River and road terrain handlers still use a broken world-height adapter

Problem:

- `handle_carve_river()` and `handle_generate_road()` extract mesh heights
- both convert to `heightmap = heights / heights.max()`
- the pure path functions are tested as normalized `[0,1]` consumers
- world terrains with negative minima or shared world ranges do not fit that contract

Files:

- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)
- [_terrain_noise.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py)
- [test_terrain_noise.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_terrain_noise.py)

Required fix:

- define an explicit adapter between world-unit terrain and normalized path solvers
- use shared min/max or a world-height transform object, not `heights.max()` alone
- preserve signed world elevation and reconstruct correctly after carving or grading
- add tests for terrains with negative elevations and asymmetric world ranges

### 5.18 Scatter and biome/material consumers still assume terrain minimum elevation is zero

Problem:

- `environment_scatter.py` converts terrain heights with `heights / heights.max()`
- `paint_terrain_biomes` computes `altitude = center.z / height_scale` and clamps to `[0,1]`
- negative lowlands collapse to `0`, and slope/biome decisions drift when world terrains are not zero-based

Files:

- [environment_scatter.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py)
- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)

Required fix:

- remove zero-based altitude assumptions from scatter, slope, and biome/material assignment
- use shared world elevation contracts or explicit terrain-range adapters
- ensure vegetation, debris, and material zoning remain correct on terrains with negative valleys, basins, or waterlines

### 5.19 Tests still protect dead or legacy terrain workflows

Problem:

- tests still assert the presence of `env_generate_world_terrain`
- tests still exercise and wire the standalone `env_generate_waterfall` route as if it is the intended public system
- these tests lock in legacy workflows the branch is supposed to retire

Files:

- [test_functional_blender_tools.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_functional_blender_tools.py)
- [test_road_coastline_terrain_features.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_road_coastline_terrain_features.py)
- [test_wiring_integration.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_wiring_integration.py)

Required fix:

- delete or rewrite tests that encode dead public terrain routes
- replace legacy waterfall wiring tests with water-network-driven terrain tests
- make the test suite enforce the new pass-based terrain pipeline instead of backward-compatible terrain shortcuts

### 5.20 Standalone terrain actions still bypass checkpoint and rollback control

Problem:

- `compose_map` has checkpoint/resume support
- the standalone `blender_environment` terrain actions (`generate_terrain`, `carve_river`, `generate_road`, `create_water`, `sculpt_terrain`, and others) still call Blender handlers directly
- the terrain actions most likely to be used interactively by agents are therefore outside the checkpoint/rollback contract

Files:

- [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)

Required fix:

- route standalone terrain mutations through the same pass/checkpoint framework
- autosave after successful terrain passes
- require rollback on failed terrain validation
- do not leave checkpointing as a compose-map-only feature

### 5.21 Map-point normalization is still using a lossy heuristic

Problem:

- `_normalize_map_point()` tries to guess whether user coordinates are in `0..size` space or centered `[-half,+half]` space
- the current rule only shifts when both coordinates are in `[0, size]` and at least one exceeds `60%` of terrain size
- valid unsigned-space inputs like `(50, 50)` on a `100`-unit terrain are treated as already centered
- that maps the point to the far edge instead of the terrain center

Files:

- [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)
- [test_compose_planners.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_compose_planners.py)
- [test_compose_map_integration.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/tests/test_compose_map_integration.py)

Required fix:

- remove the heuristic guess path
- require an explicit coordinate-space contract, or explicit conversion mode
- add tests for center, quarter, and offset points in both coordinate systems
- ensure roads, rivers, anchors, and explicit placements all use the same map-space contract

### 5.22 `compose_map` terrain location is not honored by actual terrain generation

Problem:

- `compose_map` reads `terrain.location`
- anchor planning and point-to-cell conversion use that location
- the actual `env_generate_terrain` call does not pass any terrain location
- `handle_generate_terrain()` still creates the terrain object at `(0, 0, 0)`

Files:

- [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)
- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)

Required fix:

- make terrain generation accept an explicit terrain object location / world origin
- propagate `terrain.location` through compose-map terrain generation
- add integration tests that verify non-origin terrain placement is honored end-to-end

### 5.23 World-tile artifact export is still incomplete

Problem:

- `_export_world_tile_artifacts()` currently writes only heightmap and optional alphamap
- `handle_generate_terrain_tile()` computes flow accumulation and a moisture proxy, but does not export flow, wetness, cliff, or other semantic masks
- the downstream tile pipeline still lacks the semantic artifact set required for AAA terrain continuity

Files:

- [environment.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/environment.py)

Required fix:

- export named terrain semantic artifacts per tile
- at minimum add flow, wetness, cliff, and hero-feature candidate outputs
- make exported artifact paths part of the tile result contract
- add continuity validation for those exported masks

### 5.24 Chunk metadata export is still geometry-centric only

Problem:

- `terrain_chunking.export_chunks_metadata()` exports bounds, LOD info, and neighbor references
- it does not export semantic mask channels, continuity manifests, hero-feature continuity, or water continuity metadata
- the metadata format is still too thin for a real streamable terrain meaning layer

Files:

- [terrain_chunking.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py)

Required fix:

- extend metadata export to include semantic artifact manifests
- export continuity metadata for rivers, waterfalls, masks, and hero features
- keep metadata lean, but not geometry-only

### 5.25 Terrain-preparation failures can still be swallowed during location placement

Problem:

- `compose_map` tries `terrain_flatten_zone`
- if that fails, it falls back to `terrain_spline_deform`
- if both fail, placement still continues
- this allows location generation to proceed even when terrain prep failed, which can still produce floating, buried, or slope-clipped structures

Files:

- [blender_server.py](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py)

Required fix:

- do not swallow terrain-prep failure for location placement
- treat failed terrain flattening as a failed pass unless the location is explicitly allowed to use a custom foundation strategy
- surface the exact terrain-prep failure in validation output and checkpoint state

## 6. Gemini Follow-Up Validation

Gemini’s analysis was mostly valid.

Validated:

- erosion speed scaling bug was real
- large-world precision gap is real
- splatmap filtering seam gap is real

Partial agreement:

- Gemini’s memory/scalability critique is directionally correct
- but the branch is not purely “erode whole world then split”
- it already has `erosion_margin` overlap support
- that overlap support is not the same thing as true AAA tiled erosion with halo blending

Do not discard the current overlap work.
Extend it into a real scalable erosion strategy.

## 7. Non-Negotiable Design Change

Replace direct scene mutation with staged terrain authoring.

Current bad behavior:

- user request
- AI guesses
- scene changes

Required behavior:

- user request
- scene understanding
- anchor resolution
- structured plan
- scoped execution
- pass validation
- visual review
- checkpoint save or rollback

If this architecture is not implemented, the branch will keep wasting tokens and visual iteration time.

## 8. Core Architecture

### 8.1 Keep `_terrain_world.py` pure

Do not turn `_terrain_world.py` into the orchestration layer.

It should remain responsible for:

- deterministic world-space sampling
- world-region generation
- tile extraction
- seam helpers
- whole-region erosion wrapper

### 8.2 Add `terrain_pipeline.py`

Create:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_pipeline.py`

Responsibilities:

- accept terrain intent, anchors, quality profile, and edit scope
- run passes in a deterministic order
- isolate seeds by pass
- collect outputs and validations
- manage checkpoints and rollback

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

## 9. Mandatory New Modules

### 9.1 `terrain_semantics.py`

Purpose:

- central terrain scene understanding

Add:

- `TerrainIntentState`
- `TerrainSceneRead`
- `HeroFeatureSpec`
- `WaterSystemSpec`
- `CaveSystemSpec`
- `ProtectedZoneSpec`
- `CameraPrioritySpec`

This module must answer:

- what are the major landforms
- what is the focal point
- which hero features exist or are missing
- where waterfalls should source, lip, pool, and outflow
- where cave candidates exist
- what regions are protected

No terrain edit should happen without this state.

### 9.2 `terrain_masks.py`

Purpose:

- reusable semantic terrain attributes

Generate:

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
- cliff candidates
- cave candidates
- waterfall candidates
- riverbank zones
- quiet zones
- hero-feature zones
- Tripo placement zones

Masks must be:

- cached
- exportable
- usable by logic, materials, chunking, and Geometry Nodes

### 9.3 `terrain_cliffs.py`

Purpose:

- structural cliff authoring

Add:

- `build_cliff_candidate_mask()`
- `carve_cliff_system()`
- `add_cliff_ledges()`
- `build_talus_field()`
- `insert_hero_cliff_meshes()`
- `validate_cliff_readability()`

AAA cliff rule:

- a cliff is not just “steep terrain”
- it must have lip, face, ledges, base/talus, and material separation

### 9.4 `terrain_waterfalls.py`

Purpose:

- real waterfall system authoring

Add:

- `detect_waterfall_lip_candidates()`
- `solve_waterfall_from_river()`
- `carve_impact_pool()`
- `build_outflow_channel()`
- `generate_mist_zone()`
- `generate_foam_mask()`
- `generate_wet_rock_mask()`
- `validate_waterfall_system()`

Represent each waterfall as:

- source
- lip
- drop
- pool
- outflow

If any link is missing, the waterfall must fail generation.

### 9.5 `terrain_caves.py`

Purpose:

- authored cave entrance systems

Add cave archetypes:

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

### 9.6 `terrain_validation.py`

Purpose:

- hard pass/fail terrain validation

Add validators for:

- cliff presence and readability
- hero feature count and spacing
- waterfall hydrology chain completeness
- pool existence and outflow
- cave entrance quality
- material zoning completeness
- Tripo collision sanity
- excessive global detail
- protected-zone violations
- large-world precision policy compliance
- splatmap border padding compliance
- real multi-angle capture completeness

### 9.7 `terrain_checkpoints.py`

Purpose:

- save and rollback

Add:

- `save_checkpoint(pass_name)`
- `rollback_last_checkpoint()`
- `save_preset(profile_name)`
- `restore_preset(profile_name)`
- `autosave_after_pass(pass_name)`
- `autosave_every_n_actions(n)`

### 9.8 Blender project save layer

The terrain workflow must distinguish among three different safety layers:

- mesh-local checkpoints for object edits
- pipeline JSON checkpoints for compose-map resume
- full `.blend` project saves for actual scene persistence

Required operating rule:

- inspect current file path and dirty state before terrain mutation
- inspect external add-on/tool availability before choosing a Blender workflow
- prefer scoped in-place edits over delete-and-regenerate when the terrain semantic state is still valid
- save before risky passes
- save after accepted passes
- verify each non-copy save on disk

Save verification should check:

- file exists
- file size is non-zero
- current Blender file matches the saved path for active working saves
- optional hash capture for milestone saves

### 9.8 `terrain_quality_profiles.py`

Purpose:

- predictable quality modes

Profiles:

- `preview`
- `production`
- `hero_shot`
- `aaa_open_world`

Each profile must control:

- resolution
- erosion iterations
- mesh density
- scatter density
- water mesh detail
- review angle count
- validation strictness
- checkpoint frequency

## 10. Required Changes To Existing Files

### 10.1 `_terrain_world.py`

Keep pure.

Use it for:

- deterministic world-space height authority
- tile extraction
- seam validation
- exact whole-region erosion mode

Do not make this the procedural god-object.

### 10.2 `_terrain_noise.py`

Add separate output bands:

- continental / macro forms
- ridgelines
- meso breakup
- strata / shelf field
- micro detail
- domain warp field

Add:

- directional warping
- ridged multifractal support
- strata banding
- anisotropic breakup
- anti-grain smoothing

Rule:

- micro detail must never define terrain silhouette

### 10.3 `_terrain_erosion.py`

Preserve the current pure erosion core and the droplet speed fix.

Extend outputs to include:

- erosion amount
- deposition amount
- wetness proxy
- bank instability
- talus zones
- pool deepening candidates

Also support:

- exact whole-region erosion mode
- tiled erosion with halos and seam blending mode

### 10.4 `_terrain_depth.py`

Make this the terrain-analysis brain.

Add:

- slope extraction
- curvature extraction
- basin detection
- ridge extraction
- cliff-lip detection
- waterfall-candidate detection
- cave-candidate detection
- camera saliency helpers
- line-of-sight helpers

Keep low-level mesh utilities here if useful, but not public authoring workflows.

### 10.5 `_water_network.py`

This becomes the water authority.

Add or expose:

- river class logic
- variable width
- meander logic
- bank asymmetry
- waterfall insertion
- lake pooling / basin fill
- outflow solving
- foam / mist adjacency masks
- wetness adjacency

No public waterfall generation path should bypass this model.

### 10.6 `terrain_materials.py`

Move from slope-led material assignment to semantic material zoning.

Add:

- `build_terrain_material_stack()`
- `assign_material_zones()`
- `generate_wetness_variation()`
- `generate_macro_color_breakup()`
- `apply_triplanar_on_cliffs()`

Required terrain material stack minimum:

- soil / grass
- exposed rock
- stratified cliff rock
- sediment / scree
- wet rock
- moss / damp variation

### 10.7 `environment_scatter.py` and `_scatter_engine.py`

Upgrade to semantic asset placement.

Add:

- `classify_asset_role(hero/support/filler)`
- `build_asset_context_rules()`
- `place_assets_by_zone()`
- `cluster_rocks_for_cliffs()`
- `cluster_rocks_for_waterfalls()`
- `scatter_debris_for_caves()`
- `validate_asset_density_and_overlap()`

Placement logic must understand:

- cliffs
- riverbanks
- waterfall bases
- cave entrances
- plateaus
- flat open terrain
- quiet zones
- focal areas

### 10.8 `terrain_chunking.py`

Extend beyond geometry.

Chunk and export:

- height
- splat / biome weights
- cliff masks
- wetness masks
- flow maps
- asset masks
- hero-feature continuity data

Add seam validation for:

- border height delta
- border mask continuity
- river / waterfall continuity
- splatmap border compatibility

### 10.9 `environment.py`

Reduce toward strict pass control and tile compatibility wrappers.

Add:

- `run_pass("macro")`
- `run_pass("cliffs")`
- `run_pass("water")`
- `run_pass("caves")`
- `run_pass("materials")`
- `run_pass("assets")`
- `run_pass("validation")`

Do not keep broad ad hoc terrain mutation logic here long term.

Also:

- remove or replace the dead `handle_generate_world_terrain()` route
- resolve the `object_location` vs `position` contract ambiguity

### 10.10 `viewport.py` and `blender_server.py`

Must become trustworthy terrain review tools.

Add:

- real `render_angle`
- macro review angle sets
- hero feature review angle sets
- traversal review angle sets
- anchor-target review cameras
- verification of screenshot completeness

Also:

- update any tests or call paths that currently rely on empty-path success
- ensure `aaa_verify` fails if requested angles were not actually captured

## 11. The Real Cliff Fix

Cliffs must be generated before fine detail and before final water.

Required cliff pipeline:

1. generate macro terrain
2. build cliff candidate mask from:
   - slope
   - curvature
   - concavity / convexity
   - ridge adjacency
3. carve local cliff structures
4. add ledge interruptions
5. build talus at the base
6. insert hero cliff meshes only where silhouette needs help
7. assign cliff-specific materials
8. scatter cliff-context assets
9. validate cliff readability from key review cameras

Blender best practice:

- use terrain mesh for continuity
- use separate hero cliff meshes for silhouette authority
- use triplanar materials on cliff faces
- use debris/talus meshes at the base
- preserve the clean cliff lip silhouette from main camera

## 12. The Real Waterfall Fix

A waterfall must be authored from a river network.

Required waterfall pipeline:

1. solve river path
2. detect cliff crossing / lip candidate
3. establish lip position and width
4. carve receiving pool
5. create outflow channel
6. generate waterfall geometry components
7. generate foam only at impact / turbulence
8. generate mist volume
9. generate wet rock mask nearby
10. validate source / lip / pool / outflow chain

Validation rules:

- source Z > lip Z
- lip Z > pool Z
- pool radius above minimum
- outflow exists
- waterfall stays in target screen-space region if anchor exists

Blender best practice:

- split into river surface, waterfall sheet/volume, impact pool, foam layer, mist volume, wet rock zone
- do not try to sell the entire system with one noisy UV material

## 13. The Real Cave Fix

Cave openings must be authored entrances, not generic holes.

Required cave pipeline:

1. pick archetype from terrain context
2. define path / chamber
3. carve or volume-build cave
4. remesh / smooth
5. re-break with geological rock pattern
6. build entrance lip and side framing
7. add collapse debris
8. add damp mask and darkening
9. add occlusion shelf / shadow pocket
10. validate entrance readability

Blender best practice:

- use sculpt or volume workflow for hero entrances
- add separate entrance rock pieces
- use shadow shelves and debris to hide transitions
- use wetness / dirt to sell age and geology

## 14. The Real Material Fix

Current first-pass terrain texturing is still too weak because it is not semantic enough.

Required mask stack for materials:

- slope
- height
- curvature
- flow
- wetness
- erosion
- deposition
- biome
- cliff
- cave dampness
- quiet zones

AAA best practices:

- triplanar on cliffs
- macro breakup separate from micro detail
- micro normals separate from displacement
- roughness variation aggressively used
- preserve silhouette in geometry, not shader tricks

Important:

- “grainy terrain” in this branch is not mainly a UV issue
- the larger issue is structural zoning weakness and noise doing too much visual work

## 15. The Real Tripo / Asset Intelligence Fix

Every terrain asset needs semantic context and role.

Required metadata tags:

- cliff
- riverbank
- waterfall_base
- cave_entrance
- plateau
- forest_floor
- hero
- support
- filler
- large
- medium
- small

Required placement logic:

- cliffs: angular rock clusters, sparse scrub
- waterfall base: boulders, shattered slabs, mist rocks
- riverbanks: rounded stones, debris, low vegetation
- cave entrances: collapse rubble, framing rocks, damp debris
- flat open terrain: biome vegetation, lower rock clutter

Blender best practice:

- use Geometry Nodes scatter with zone masks, density curves, exclusion zones, clustering behavior, and camera-priority weighting
- random scatter is not acceptable

## 16. User -> AI Understanding And Visual Workflow

This is the highest-value workflow fix in the whole plan.

### 16.1 Required scene read before edit

Before any terrain mutation, the AI must output:

- current major landforms
- focal point
- hero terrain features
- waterfall source / lip / pool / outflow if relevant
- cave candidates
- target edit scope
- protected zones
- success criteria

If this scene read is wrong or low-confidence:

- no edit

### 16.2 Named anchors

Support empties like:

- `WF_LIP_TARGET`
- `WF_POOL_TARGET`
- `WF_OUTFLOW_TARGET`
- `CLIFF_HERO_A`
- `CAVE_ENTRANCE_A`
- `FOCAL_VALLEY_CENTER`
- `PROTECTED_RIDGE_A`

AI must prefer anchors over visual guessing.

### 16.3 Runtime enforcement of terrain editing protocol

The current protocol in [TERRAIN_EDITING_PROTOCOL.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md) must become runtime terrain-edit logic.

Mandatory runtime behaviors:

- observe before calculate
- sync to the user’s viewport
- lock reference empties
- classify surface vs inside vs floating vs in-front
- use smallest possible diff
- verify placement before cutting or placing geometry

### 16.4 Scoped corrections

When something fails, corrections must be narrow:

Failures:

1. waterfall lip too far left
2. cliff face still reads as slope
3. cave mouth lacks framing

Correction rule:

- fix only those
- do not alter unrelated terrain
- preserve validated passes and protected zones

### 16.5 Visual review requirements

Each major pass must support:

- live viewport screenshot
- deterministic contact sheet
- semantic overlay review where useful

Review modes:

- `macro_review`
- `hero_feature_review`
- `traversal_review`

## 17. Checkpoints, Presets, And Profiles

Add checkpoint saves after every successful pass.

Examples:

- `terrain_01_macro.blend`
- `terrain_02_cliffs.blend`
- `terrain_03_water.blend`
- `terrain_04_caves.blend`
- `terrain_05_materials.blend`
- `terrain_06_assets.blend`

Add preset files under:

- `presets/terrain/aaa_open_world.json`
- `presets/terrain/hero_waterfall.json`
- `presets/terrain/cave_basin.json`

Preset contents:

- seeds
- biome config
- erosion config
- cliff rules
- water rules
- asset rules
- material rules
- quality profile
- large-world policy
- splatmap padding policy

## 18. Large-World Policy

The current branch needs an explicit large-world strategy.

Required:

- high-precision generation coordinates
- tile-relative local transforms for mesh/object work where needed
- stable export/import contracts
- support for future floating-origin or origin-rebasing workflows

Do not rely on raw 32-bit world floats as the long-term only policy.

## 19. Tiled Erosion Policy

Support two modes:

### Exact mode

- erode the full world region, then split
- use for smaller worlds, hero shots, and correctness-focused generation

### Scalable tiled mode

- per-tile erosion with halos / overlap margins
- seam blending or reconciliation pass
- validation against adjacent tile seams

Current overlap-margin path is not enough by itself.

## 20. Splatmap Padding Policy

Support padded splatmaps for tiled export.

Required:

- export padded alphamaps with neighbor-compatible border pixels
- import padded alphamaps into Unity terrain pipeline
- reconcile internal terrain alphamap resolution vs external export dimension

The current exact-size RAW export is not enough for tiled AAA terrain texturing.

## 21. Definition Of AAA Done

Do not call the branch AAA until these are all true:

- terrain reads as 3 to 5 clear landform families from camera
- cliffs have real structure and silhouette authority
- waterfalls always have source / lip / pool / outflow logic
- cave entrances look authored, not booleaned
- first-pass materials already look believable
- Tripo placement is context-aware
- edits are checkpointed and reversible
- the AI can make targeted corrections without re-breaking validated terrain
- quiet terrain exists alongside detail
- visual review is real, not fake
- large-world precision policy exists
- tiled splatmap seam policy exists
- tiled erosion policy exists

## 22. Implementation Order

Do this in this order:

1. preserve and commit the `_terrain_erosion.py` speed fix
2. implement real `render_angle`
3. make `aaa_verify_map()` fail honestly
4. replace dead/broken public terrain routes
5. add `terrain_semantics.py`
6. add `terrain_validation.py`
7. add `terrain_checkpoints.py`
8. add `terrain_pipeline.py`
9. add `terrain_masks.py`
10. expand `_terrain_depth.py`
11. expand `_terrain_erosion.py` outputs
12. rebuild cliffs
13. integrate `_water_network.py` as the real water authority
14. rebuild waterfall authoring
15. rebuild cave archetypes
16. overhaul material zoning
17. overhaul asset placement
18. add large-world coordinate policy
19. add tiled erosion halo/blend policy
20. add padded splatmap export/import policy
21. resolve tile metadata contract ambiguity
22. extend chunk semantics and continuity validation
23. update tests that encode broken visual-validation behavior or miss tiled-edge cases
24. add profiles and presets
25. replace fake `performance_budget_check` with real measurement
26. fix stamp-space world-contract drift in `terrain_advanced.py`
27. fix world-height adapters for river/road/scatter/material consumers
28. remove or rewrite tests that protect dead terrain routes and legacy waterfall wiring
29. route standalone terrain actions through checkpointed pass control
30. replace heuristic map-point normalization with an explicit coordinate-space contract
31. propagate terrain location through actual terrain generation
32. export semantic tile artifacts and semantic chunk metadata
33. stop swallowing terrain-preparation failures during location placement

## 23. Direct Instruction To Claude

Use this instruction block directly:

Your task is to turn the `feature/terrain-world-foundation` branch into an AAA-grade terrain authoring system, not just a procedural generator.

You must preserve the branch’s good foundations:

- canonical world-space terrain sampling
- deterministic noise generation
- pure erosion primitives
- water-network groundwork
- tile/chunk groundwork

You must fix all remaining must-fix issues:

1. fake multi-angle visual verification
2. empty screenshot false-pass in AAA validation
3. public waterfall generation bypassing the water graph
4. terrain editing protocol existing only in docs
5. non-exact independent tiled erosion seams
6. lack of large-world precision strategy
7. lack of splatmap border padding strategy
8. weak semantic terrain masks
9. weak material zoning
10. weak semantic asset placement
11. fake performance budget validation
12. stale stamp-space world coordinate math
13. broken world-height adapters in river and road handlers
14. zero-based altitude assumptions in scatter and biome/material consumers
15. tests that still enforce dead world-generation and standalone waterfall workflows
16. standalone terrain actions bypassing checkpoints
17. lossy coordinate-space heuristics in map-point normalization
18. `compose_map` terrain location not reaching terrain generation
19. incomplete semantic tile/chunk export contracts
20. swallowed terrain-preparation failures during placement

You must prioritize:

1. terrain semantics
2. validation
3. checkpoints
4. real visual review
5. structural cliffs
6. real waterfall systems
7. cave entrance archetypes
8. mask-driven materials
9. semantic asset placement
10. large-world and tiled-world correctness

Do not propose vague improvements.
Produce concrete file-level changes, new modules, function signatures, pass architecture, validation rules, export rules, Blender-specific implementation details, and verification requirements.

Do not treat cliffs as overlays.
Do not treat waterfalls as freeform meshes.
Do not treat cave openings as simple booleans.
Do not treat first-pass texturing as optional polish.
Do not allow edits without checkpoints and validation.
Do not trust visual QA until `render_angle` is real and screenshot validation can fail honestly.
Do not ignore large-world precision or tiled splatmap filtering seams.

Target quality benchmark:
AAA studio-style terrain authoring workflow with visual-first AI editing.

## 24. Supporting Documents

These documents also exist and can be consulted:

- [terrain_aaa_implementation_guide.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/docs/terrain_aaa_implementation_guide.md)
- [terrain_tool_bug_audit_2026-04-07.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/docs/terrain_tool_bug_audit_2026-04-07.md)
- [terrain_branch_full_implementation_plan_2026-04-07.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/docs/terrain_branch_full_implementation_plan_2026-04-07.md)
- [terrain_pipeline_handoff_for_claude.md](C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit/docs/terrain_pipeline_handoff_for_claude.md)

This master plan is the authoritative combined version.

## 25. Additional Round Findings From This Audit

These were validated after the earlier master-plan draft and must be treated as part of the same authoritative handoff.

### 25.1 Fake performance validation creates false confidence

- addon registration still defines `performance_budget_check` as a stub returning `not_implemented`
- `blender_server.py` still wraps that result into a success-shaped performance report
- because missing metrics default to `0`, this path can falsely report that the scene is under budget

### 25.2 A legacy terrain-origin contract remains in the stamp path

- most of the terrain branch now uses centered terrain transforms
- `apply_stamp_to_heightmap()` still behaves like `terrain_origin` is the min corner
- `handle_terrain_stamp()` passes the terrain object location directly, so stamp placement will drift on offset centered terrains

### 25.3 World-height adapters are inconsistent across terrain consumers

- river and road carving currently adapt mesh heights using only `heights.max()`
- scatter slope extraction does the same
- legacy biome/material painting assumes negative terrain heights should clamp to altitude `0`
- this is a branch-wide contract drift problem, not an isolated river bug

### 25.4 The test suite still locks in legacy terrain APIs

- the suite still checks for `env_generate_world_terrain`
- the suite still treats standalone waterfall generation as a supported public workflow
- these tests will fight the AAA pipeline refactor unless they are rewritten with the implementation

### 25.5 Standalone terrain actions still skip the checkpoint system

- `compose_map` persists and reloads pipeline checkpoints
- `blender_environment` terrain actions still mutate terrain directly without checkpoint savepoints or rollback hooks
- the most common interactive terrain path is therefore still outside the intended safety model

### 25.6 Map-space conversion is still heuristic and can mis-map valid points

- `_normalize_map_point()` only shifts unsigned-space inputs when at least one axis exceeds `60%` of terrain size
- points like `(50, 50)` on a `100`-unit terrain remain unshifted and map to the far edge
- this affects river, road, and placement routing in compose workflows

### 25.7 `terrain.location` exists in planning but not in generated terrain placement

- compose planning uses `terrain.location`
- actual terrain generation still creates the terrain mesh at the origin
- any non-origin terrain spec can therefore drift out of sync with later placement logic

### 25.8 Tile exports still do not stream terrain meaning

- world tile export currently writes heightmap plus optional alphamap only
- flow, wetness, cliff, and other semantic outputs are still not part of the artifact contract
- chunk metadata remains geometry-centric instead of meaning-centric

### 25.9 Terrain flattening failures can still disappear inside placement flow

- `compose_map` attempts heightmap-aware flattening, then spline-deform fallback
- if both fail, placement still proceeds
- this makes terrain-prep failure look like a later visual problem instead of a pass failure

## 26. AAA / Open-World Reference Practices To Match

The branch should not just imitate generic “AAA vibes.”
It should close specific gaps against real open-world terrain and environment tool practices documented by Epic, Guerrilla, and Ubisoft.

### 26.1 Large worlds use streaming cells, not monolithic scene mutation

Epic’s World Partition material explicitly frames large-world production around automatic world grids, streaming cells, and HLOD-driven memory control rather than one giant always-live world file.

Implication for this branch:

- terrain passes must operate on scoped regions and streamable semantic chunks
- validation and export must be cell-aware
- checkpointing should align with pass scopes and tile/cell scopes

Sources:

- Epic, *World Partition / streaming guidance*: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5.0-release-notes?application_version=5.0
- Epic, *Level Streaming in Unreal Engine*: https://dev.epicgames.com/documentation/en-us/unreal-engine/level-streaming-in-unreal-engine
- Epic, *Streaming and HLODs in UEFN*: https://dev.epicgames.com/documentation/uefn/streaming-and-hlods-in-unreal-editor-for-fortnite

### 26.2 Large worlds use translated or high-precision world space, not raw float-only world coordinates everywhere

Epic’s Large World Coordinates documentation explicitly recommends translated world space or camera-relative world space for precision and performance.

Implication for this branch:

- semantic generation can stay in stable high precision space
- Blender object work, camera work, and exported tile transforms should use local translated frames where appropriate
- “all raw world-space floats, all the time” is not a real large-world strategy

Sources:

- Epic, *Large World Coordinates Rendering in Unreal Engine 5*: https://dev.epicgames.com/documentation/en-us/unreal-engine/large-world-coordinates-rendering-in-unreal-engine-5
- Epic, *Unreal Engine 5.0 Release Notes* (LWC introduction): https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5.0-release-notes?application_version=5.0

### 26.3 AAA terrain editing is non-destructive and layered

Epic’s Landscape Edit Layers documentation describes a non-destructive stack for heightmap, weightmap, spline, and patch edits rather than destructive one-pass mutation.

Implication for this branch:

- terrain pipeline passes should behave like edit layers
- macro terrain, cliff carving, water deformation, patches, splines, paint, and visibility data should remain separable
- checkpoint/rollback should operate on semantic passes, not only whole-file saves

Sources:

- Epic, *Landscape Edit Layers in Unreal Engine*: https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-edit-layers-in-unreal-engine
- Epic, *Unreal Engine 5.6 Release Notes* (landscape edit-layer improvements): https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-6-release-notes

### 26.4 Open-world procedural placement is artist-directed and partition-aware

Guerrilla describes Horizon Zero Dawn’s environment system as GPU-based procedural placement driven from artist-authored graph rules. Epic’s PCG with World Partition docs describe Data Layer and HLOD-aware partitioning rather than random scatter.

Implication for this branch:

- asset placement must be graph/rule driven by semantics and masks
- outputs must be partitionable by terrain zone, data layer, or hero/pass class
- “scatter points on slopes” is not enough

Sources:

- Guerrilla, *GPU-Based Procedural Placement in Horizon Zero Dawn*: https://www.guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn
- Epic, *Using PCG with World Partition in Unreal Engine*: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-pcg-with-world-partition-in-unreal-engine

### 26.5 AAA toolchains split responsibilities into dedicated tools with explicit inputs

Ubisoft’s Ghost Recon Wildlands terrain/tools presentation emphasizes dedicated tools instead of one giant multipurpose tool, with explicit and implicit placement inputs for vegetation and environment layers. Guerrilla’s Horizon Zero Dawn tools-pipeline talk reinforces the same production lesson: open-world quality required a rebuilt tools framework so multiple generation and editing systems could interoperate cleanly.

Implication for this branch:

- cliffs, waterfalls, caves, masks, materials, and assets should stay as dedicated modules and passes
- input contracts should be explicit: anchors, protected zones, semantic masks, river graphs, cliff candidates
- broad “generate final terrain” tools are the wrong direction

Source:

- Ubisoft / GDC Vault, *Ghost Recon Wildlands terrain technology tools*: https://media.gdcvault.com/gdc2017/Presentations/WERLE_MARTINEZ_GRWterrainTechnologyTools.pdf
- Guerrilla, *Creating a Tools Pipeline for Horizon Zero Dawn*: https://www.guerrilla-games.com/read/creating-a-tools-pipeline-for-horizon-zero-dawn

### 26.6 Hero meshes and virtualized detail are layered on top of terrain, not expected from the base heightfield alone

Epic’s Nanite guidance emphasizes using high-detail geometry where appropriate, automatic streaming/LOD, and not expecting card-based or purely shader-based cheats to carry the scene by themselves.

Implication for this branch:

- terrain heightfields should provide continuity and broad landforms
- hero cliffs, debris, cave framing, and selective rock structures should provide close-read silhouette authority
- materials should not be asked to rescue weak geometry

Sources:

- Epic, *Nanite Virtualized Geometry in Unreal Engine*: https://dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine
- Epic, *Using Nanite with Landscapes in Unreal Engine*: https://dev.epicgames.com/documentation/en-us/unreal-engine/using-nanite-with-landscapes-in-unreal-engine?application_version=5.7

### 26.7 Source-control-friendly world editing matters in real production

Epic’s OFPA guidance is directly relevant to autonomous terrain editing because it reduces cross-user contention by moving actor data into external files.

Implication for this branch:

- pass outputs and checkpoints should be split and inspectable
- automated terrain edits should not funnel through one giant opaque artifact when more granular outputs are possible
- this also supports safer rollback and narrower agent diffs

Source:

- Epic, *One File Per Actor in Unreal Engine*: https://dev.epicgames.com/documentation/en-us/unreal-engine/one-file-per-actor-in-unreal-engine

### 26.8 Visibility and traversal are first-class terrain concerns, not afterthoughts

Guerrilla’s Decima visibility presentation describes Horizon’s open world as a large dense environment where visibility queries had to become a dedicated system. Their traversal talk also frames the world as complex and organic from the player’s movement perspective.

Implication for this branch:

- terrain semantics should include camera saliency, silhouette authority, traversal corridors, and readable hero-feature exposure
- validation should not stop at hydrology or seam correctness; it must also confirm that cliffs, waterfalls, caves, and quiet spaces read from the important viewpoints
- the AI workflow must prefer anchored, screen-aware corrections over blind world-space mutation

Sources:

- Guerrilla, *Decima Engine: Visibility in Horizon Zero Dawn*: https://www.guerrilla-games.com/read/decima-engine-visibility-in-horizon-zero-dawn
- Guerrilla, *Player Traversal Mechanics in the Vast World of Horizon Zero Dawn*: https://www.guerrilla-games.com/read/player-traversal-mechanics-in-the-vast-world-of-horizon-zero-dawn

## 27. Verified Additional Terrain Gaps From Secondary Audit

This section de-duplicates the secondary-agent findings against the actual terrain branch.

### 27.1 Active terrain gaps

- NavMesh generation pipeline is still missing from the terrain workflow itself.
- Terrain does not export terrain-audio metadata: surface tags, water proximity zones, cave/interior reverb zones, or ambient crossfade regions.
- Terrain/building/cliff export is not yet integrated with occlusion-ready metadata or bake handoff.
- Terrain does not export weather-state products such as wetness, snow, fog response, or wind-reactive masks.
- Water is still not a full semantic terrain pass: carve, shoreline blend, depth context, foam, wet-edge, and continuity metadata are missing.
- clear water continuation between nodes and tiles is still missing from the downstream contract even though `_water_network.py` already computes stable IDs and tile edge contracts.
- tile splatmaps and wetness are still derived from local tile hydrology instead of one world hydrology solve.
- Road and building terrain deformation remains shallow: no terracing, graded approaches, abutments, retaining logic, or ditch systems.
- Exterior terrain does not export terrain-side interior streaming connectors, door anchors, or transition metadata.
- Unity terrain holes export/import is still missing, so terrain openings for cave mouths, sinkholes, and terrain-under-terrain transitions cannot be represented through the TerrainData pipeline itself.
- Unity-native terrain detail layers and tree-instance export is still missing from the terrain branch contract.
- Unity TerrainLayer import still only carries diffuse texture + tiling, not full terrain-layer material fidelity.
- There is still no terrain integration test that verifies generation -> erosion -> terrain materials -> chunking -> export -> Unity terrain setup.
- Terrain texture anti-repetition and compression/export policy remain undefined at branch level.
- Micro-undulation and close-read ground-detail breakup still need a dedicated pass.
- Cave mouths and dungeon entrances still lack consistent terrain framing.
- Waterfall environments still lack plunge-pool shaping, outflow carving, mist zones, and spray-fed terrain logic.
- Ford and shallow-crossing authoring are still absent.
- Biome transitions still need structural ecotone logic rather than only material blends.
- Chunk export still lacks rich terrain streaming semantics for hero features, continuity zones, occlusion hints, and cross-chunk awareness.
- World splatmap generation still scales poorly because `compute_world_splatmap_weights()` evaluates full terrain regions with Python row/column loops.
- Terrain-specific corruption logic still lacks a dedicated intensity map, warped terrain behavior, fissures, and terrain masks.
- Boss-arena terrain sculpting still needs encounter-space landform logic.
- Destructible terrain/environment integration is still missing.
- Special terrain-type depth is still missing for frozen lakes, fog valleys, wetlands, multi-biome islands, lava corridors, arches, tunnels, crater stamps, and underwater-adjacent terrain.

### 27.2 Defer until the semantic pipeline refactor

- Terrain-aware building collision strategy should be integrated after terrain/building export contracts are stabilized.
- Additional terrain presets should be added after semantics, masks, and terrain materials are refactored so presets map to real terrain behavior.
- Richer water behavior such as meanders, tributary-merge treatment, shoreline classes, and lake-edge logic belongs in the semantic water pass.
- Richer terrain-audio behavior should wait until terrain surface semantics and zone exports exist.
- Environmental storytelling overlays should land after semantic masks and targeted correction loops exist.
- Weather-specific wet/dry/snow/fog terrain-state products should wait for the terrain-material refactor.
- Terrain-side LODGroup packaging should be attached to the chunk export/streaming refactor.
- Full waterfall polish systems should be completed inside the dedicated waterfall pass rebuild.
- Ecotone kits should be built on semantic biome adjacency data rather than direct scatter rules.
- Weather-driven vegetation and surface response should wait for terrain-weather metadata.

### 27.3 Secondary-audit claims that were excluded

- splatmap transfer is not missing anymore
- vegetation exclusion zones already exist
- minimap/world-map support exists elsewhere in the toolkit
- Unity-side NavMesh, occlusion, weather, interior streaming, door, audio, and LOD systems already exist, but the terrain branch still fails to integrate with them cleanly
- the public waterfall routing bug was corrected, but the branch still lacks the real semantic waterfall authoring system

## 28. Additional Terrain Contract Gaps From Reconciliation Scan

These were found while reconciling the branch plan, implementation guide, tests, and master-plan round findings.

### 28.1 Active terrain contract gaps

- `performance_budget_check` is still a stub, while `blender_server.py` still turns missing metrics into a success-shaped performance result.
- stamp placement still needs an explicit centered-terrain contract check through the handler path.
- terrain consumers still do not share one enforced world-height contract.
- tests still preserve deprecated terrain public APIs that should not define the future branch contract.
- standalone interactive terrain actions still bypass terrain-pass checkpoints.
- `_normalize_map_point()` still uses a heuristic coordinate-space conversion that can mis-map valid positions.
- compose planning can respect `terrain.location` while actual terrain generation still creates terrain at origin.
- terrain flatten failures can still disappear inside placement flow instead of failing the terrain-prep pass.
- terrain layer export/import is still hard-capped at exactly four layers because the RAW alphamap path is RGBA-only and the Unity import templates require exactly four terrain layers.
- Unity terrain import still hides missing alphamap failures by warning and falling back to default layer coverage.
- Unity terrain import still hides missing heightmap failures by warning and creating a flat terrain.
- Unity terrain import still accepts corrupted RAW artifact sizes because the generated import scripts do not validate exact byte counts for heightmaps or alphamaps.
- multibiome terrain generation can still swallow biome material and vegetation authoring failures instead of surfacing them as terrain-generation failures.
- chunking can still drop trailing world edges when world sample dimensions are not exact multiples of `chunk_size`.
- Unity compatibility heightmap export can still distort non-square terrains by forcing a square power-of-two-plus-one resize from the column dimension.
- tile water feature queries still drop stable network/segment identity for rivers and streams, so downstream tools cannot express explicit water continuation between nodes and neighboring tiles.
- computed water edge contracts are still not consumed by the active terrain-tile generation/export path.
- tile texturing can still drift on heuristic per-tile height ranges when no explicit shared range is supplied.
- the public waterfall compatibility path still detects waterfalls from a tile-local water solve instead of from shared world hydrology context.
- Unity terrain import still has no hole-mask contract for authored terrain openings.
- Unity terrain setup still has no contract for importing terrain-native detail layers or tree-instance populations.
- Unity terrain detail painting still exists only as a generic fill path, not as a consumer of exported terrain semantics.
- tiled Unity terrain import does not reject duplicate tile-grid occupancy.
- tiled Unity terrain import still allows neighbor-linked tiles to use incompatible sizes or resolutions.
- tiled Unity terrain import still allows custom tile positions that break physical continuity while neighbor links remain wired.

### 28.2 Missing regression coverage

- no regression test for stubbed performance metrics returning a false pass
- no regression test for centered-terrain stamp placement through the handler workflow
- no branch-level regression test proving consistent world-height interpretation across terrain consumers
- no regression test requiring interactive terrain actions to participate in checkpoint safety
- no full edge-case regression coverage for heuristic map-space normalization
- no regression test proving `terrain.location` affects actual terrain generation
- no regression test requiring flatten-prep failure to surface as a hard terrain failure
- no regression test for more-than-four terrain-layer export/import behavior
- no regression test requiring Unity terrain import to fail when terrain heightmap or alphamap artifacts are missing
- no regression test requiring Unity terrain import to reject RAW files with incorrect byte counts
- no regression test requiring multibiome terrain generation to surface biome-material or vegetation failures
- no regression test proving chunking preserves full world coverage for non-divisible world dimensions
- no regression test protecting non-square terrain exports from square-resize distortion in Unity-compat mode
- no regression test requiring tile water feature queries to preserve stable network/segment continuity identifiers
- no regression test proving computed water edge contracts are consumed by terrain-tile generation or export
- no regression test requiring wetness and splatmap products to remain world-consistent across neighboring tiles
- no regression test requiring a shared world height-range contract for tile texturing when explicit ranges are omitted
- no regression test proving the public waterfall compatibility path uses world-consistent hydrology context
- no regression test requiring Unity terrain hole masks to be exported, imported, and aligned with authored terrain openings
- no regression test requiring Unity-native terrain detail and tree data to round-trip through terrain export/import
- no regression test requiring Unity TerrainLayer imports to preserve normal/mask/material fidelity inputs
- no regression test requiring Unity terrain detail painting to follow exported terrain semantics instead of uniform fill
- no regression test requiring tiled terrain manifests to reject duplicate grid occupancy
- no regression test requiring neighbor-linked tiles to share compatible size and resolution
- no regression test requiring tiled-terrain world positions to remain grid-contiguous
