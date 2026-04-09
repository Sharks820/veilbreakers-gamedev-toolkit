# Terrain Tool Bug Audit

Date: 2026-04-07
Scope: Concrete bugs, broken contracts, and high-impact gaps in the terrain toolchain

This audit focuses on real tool failures, not just architecture wishes.

## Findings

### 1. Registered world-terrain command is still exposed even though it always hard-fails

Severity: Critical

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py:970`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:1174`

Details:

- `env_generate_world_terrain` is still registered in the public command map.
- The handler behind it immediately raises `NotImplementedError`.

Impact:

- The tool advertises a supported multi-tile world-generation command that cannot run.
- Any automation or agent path still targeting the documented world-terrain workflow will fail at runtime.

Recommended fix:

- Either remove the registration now, or replace the handler with a compatibility wrapper that drives `env_generate_terrain_tile` for each tile.

### 2. Tiled cliff overlays are created in the wrong transform space

Severity: High

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:784`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:817`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:825`
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py:613`

Details:

- `detect_cliff_edges()` returns cliff positions centered around the local terrain mesh.
- `_create_terrain_mesh_from_heightmap()` creates the terrain object at `object_location`, but creates each cliff object at the raw local-space coordinates before parenting it to the terrain.
- Parenting preserves the cliff object's world transform instead of turning those local coordinates into tile-local offsets.

Impact:

- On offset terrain tiles, cliff overlays can remain near the origin instead of following the tile.
- This directly breaks tiled-world cliff visuals and makes seam continuity impossible.

Recommended fix:

- Create cliff objects in the terrain object's local space after parenting, or set `cliff_obj.parent = obj` first and then assign local transforms.

### 3. Cliff overlay height calculation mixes vertical range with horizontal terrain size

Severity: High

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py:631`
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py:637`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:821`

Details:

- `detect_cliff_edges()` computes:
  - `height_range = max(height) - min(height)` over the cluster
  - `cliff_height = max(height_range * max(terrain_width, terrain_height) * 0.1, 2.0)`
- That multiplies a vertical value by the terrain width/height.
- `_create_terrain_mesh_from_heightmap()` then also scales the cliff object Z position by `height_scale`.

Impact:

- Cliff mesh height becomes detached from the actual terrain feature size.
- On larger terrains or world-space heightmaps, this can produce absurdly tall overlays or heavily exaggerated cliff pieces.
- The result is one likely cause of “fake cliffs” and broken silhouette reads.

Recommended fix:

- Compute cliff height strictly from vertical relief in the source height domain, then convert once to mesh scale.
- Do not multiply vertical relief by horizontal terrain extent.

### 4. Terrain editing helpers still clamp world-space terrain back to `[0, 1]`

Severity: High

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py:793`
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py:896`
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py:1483`
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py:1530`

Details:

- `compute_erosion_brush()` returns `np.clip(result, 0.0, 1.0)`.
- `flatten_terrain_zone()` also returns `np.clip(result, 0.0, 1.0)`.
- The terrain branch has already moved important paths toward world-space height values, but these helpers still assume normalized terrain.

Impact:

- Any world-unit terrain edited through these helpers can be silently crushed into a normalized range.
- This breaks foundations, erosion paint, and any follow-up passes that expect consistent terrain units.

Recommended fix:

- Remove hard clipping from these pure helpers.
- If normalized editing is required for a specific path, make it an explicit wrapper with normalize/de-normalize steps.

### 5. The visual gate can report success with zero screenshots

Severity: High

Files:

- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_validation.py:136`

Repro:

- Running `aaa_verify_map([], min_score=60)` currently returns:
  - `{'passed': True, 'total_score': 0.0, 'per_angle': [], 'failed_angles': []}`

Details:

- `aaa_verify_map()` never checks for an empty screenshot list.
- It returns success when no images were analyzed.

Impact:

- A terrain generation pass can pass “AAA verification” without any visual evidence.
- This undermines the whole screenshot-validation workflow and makes autonomous passes unsafe.

Recommended fix:

- Treat an empty screenshot set as a hard failure.
- Also require a minimum angle count instead of accepting any non-empty subset.

### 6. Multi-channel seam validation is broken for semantic tiles and splatmaps

Severity: High

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py:353`
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py:405`
- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py:1662`

Repro:

- Calling `validate_tile_seams()` with 3D tile data such as shape `(H, W, 4)` raises:
  - `TypeError: float() argument must be a string or a real number, not 'list'`

Details:

- The seam validator assumes scalar height values and casts edge elements through `float(...)`.
- The public `env_validate_tile_seams` command is therefore not usable for splatmaps, wetness masks, or other semantic tile payloads.

Impact:

- The tool cannot validate the very multi-channel exports the AAA terrain workflow needs.
- This blocks semantic seam validation for masks and chunk metadata.

Recommended fix:

- Extend the validator to support N-dimensional arrays by comparing all trailing channels.
- Return per-channel max/mean deltas when the input is multi-channel.

### 7. Water-network foundation exists but is effectively dead code in the terrain pipeline

Severity: Medium

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/_water_network.py:437`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:994`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:1174`

Details:

- `_water_network.py` contains a strong world-level river/lake/waterfall model.
- There are no active callers to `WaterNetwork.from_heightmap()` in the terrain generation path.
- The old multi-tile world handler that could have owned this integration is deprecated.

Impact:

- The best current foundation for hydrologic waterfalls and tile-edge water continuity is not participating in terrain generation.
- Waterfall quality is limited by disconnected local mesh builders and ad hoc water creation.

Recommended fix:

- Integrate `WaterNetwork.from_heightmap()` into the new terrain pass orchestrator and make water features first-class pass outputs.

### 8. Current visual verification is image-stat based, not terrain-read based

Severity: Medium

Files:

- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_validation.py:14`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_validation.py:166`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py:3405`

Details:

- The visual gate scores brightness, contrast, edges, entropy, color spread, and a few heuristic flags.
- It does not validate the terrain-specific things that actually matter:
  - cliff silhouette readability
  - waterfall chain placement
  - cave entrance framing
  - quiet-vs-detail balance
  - focal composition

Impact:

- Bad terrain can still pass as long as the image is visually “busy” enough.
- This explains why the branch can satisfy technical gates while still looking wrong.

Recommended fix:

- Keep the current screenshot stats as a low-level sanity filter.
- Add terrain-specific visual review on top, anchored to semantic features and camera priorities.

### 9. The tile-generation path returns metadata that does not describe the actual Blender object transform

Severity: Medium

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:1005`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:1008`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:1148`
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py:1152`

Details:

- The terrain object is created at `object_location = (world_origin_x + terrain_size/2, world_origin_y + terrain_size/2, 0)`.
- The returned metadata also includes:
  - `object_location`
  - `position = [world_origin_x, 0.0, world_origin_y]`
- These two values describe different coordinate contracts.

Impact:

- Downstream tools can easily consume the wrong transform contract.
- This kind of ambiguity is exactly how terrain, water, scatter, and export systems drift apart.

Recommended fix:

- Return one explicit transform contract and name it clearly:
  - either object origin / center transform
  - or tile min-corner world bounds
- Do not return both without defining which consumers should use which.

### 10. World splatmap generation is still a Python double loop on full terrain regions

Severity: Medium

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py:2172`

Details:

- `compute_world_splatmap_weights()` loops cell-by-cell in Python.
- That is already expensive on larger tiles and becomes a real bottleneck on multi-tile worlds.

Impact:

- Slow splat generation increases iteration cost and discourages frequent validation.
- It directly fights the goal of low-iteration autonomous terrain authoring.

Recommended fix:

- Rewrite the function as vectorized NumPy operations before scaling up world-region passes.

### 11. The advertised multi-angle AAA verifier does not actually change camera angle

Severity: High

Files:

- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py:3406`
- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py:1701`
- `Tools/mcp-toolkit/blender_addon/handlers/viewport.py:969`

Details:

- `blender_server.py` loops over yaw/pitch pairs and sends `render_angle`.
- In the addon registry, `render_angle` is currently just an alias to `handle_get_viewport_screenshot`.
- `handle_get_viewport_screenshot()` does not read `yaw` or `pitch`; it simply captures the current viewport.

Impact:

- The "10-angle" AAA verification pass can degrade into repeated screenshots from the same view.
- Composition, cliff silhouette, waterfall placement, and cave-read problems can all be missed because they are never inspected from distinct angles.

Recommended fix:

- Implement a real `render_angle` handler that positions a temporary review camera around a target or terrain anchor and renders each requested angle deterministically.
- Fail verification when fewer than the required angles were actually captured.

### 12. The terrain editing protocol exists only as documentation and is not enforced by the active toolchain

Severity: High

Files:

- `.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md`
- `.claude/skills/vb-mcp-tools/SKILL.md`

Details:

- The protocol defines mandatory live-view sync, locked reference empties, surface classification, distance diagnostics, and boolean preflight.
- Branch code searches show these helpers and requirements exist only in the documentation path, not in the active terrain handlers or server routing.

Impact:

- The branch has no hard guarantee that terrain edits are grounded in the user's live view or in anchored, reusable reference points.
- This explains recurring failures like floating waterfalls, buried cave mouths, and visually wrong "fixes" that pass local math checks.

Recommended fix:

- Promote the protocol into callable terrain-edit utilities and require them in all terrain mutation passes that place or cut geometry near existing surfaces.
- Add validation failures when edits are attempted without view sync, anchors, or surface classification where required.

### 13. The exposed waterfall generator bypasses the branch's actual water-logic foundation

Severity: High

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py:1114`
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py:254`
- `Tools/mcp-toolkit/blender_addon/handlers/_water_network.py:437`

Details:

- `env_generate_waterfall` is wired to `terrain_features.generate_waterfall()`.
- That generator produces a standalone fixed-axis mesh concept, not a river-derived waterfall system.
- There are no active callers to `WaterNetwork.from_heightmap()` in the terrain path.

Impact:

- The branch currently exposes two incompatible waterfall stories:
  - a world-level hydrology model that is not used
  - a visible waterfall mesh generator that does not understand terrain logic
- This is a direct reason waterfall work remains slow, brittle, and visually disconnected from rivers and cliffs.

Recommended fix:

- Replace `env_generate_waterfall` with a waterfall-authoring pass driven by `_water_network.py` and terrain semantics.
- Keep the standalone mesh generator only as a low-level geometry helper, not as the public terrain-water workflow.

### 14. The current standalone waterfall generator is terrain-agnostic and hard-coded to a single orientation

Severity: High

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py:254`

Details:

- The generator explicitly assumes the waterfall faces `-Y`.
- The cliff face is built at `Y=0`, the pool is pushed into `-Y`, and the optional cave is placed behind the waterfall at a fixed positive-Y location.
- None of these placements are derived from terrain normals, river vectors, basin shape, or actual surface intersection.

Impact:

- The generated waterfall can only ever be "correct" in an isolated demo setup.
- As soon as it is applied to real terrain, it tends to read as a cutout or kit piece rather than terrain-authored water.

Recommended fix:

- Refactor this into reusable sub-generators for sheet, foam, pool, mist, and cave framing, but derive transform and dimensions from terrain semantics plus surface/anchor validation.

### 15. Material zoning is still driven by slope and coarse height percent, not semantic terrain masks

Severity: Medium

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py:2172`
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py:2260`

Details:

- `compute_world_splatmap_weights()` only uses slope, coarse height percent, and optional moisture.
- The material graph is built from the `VB_TerrainSplatmap` vertex-color channels rather than a richer semantic mask stack.
- There is no triplanar cliff path, no curvature-driven breakup, and no dedicated erosion/deposition/wetness material logic.

Impact:

- First-pass terrain materials will continue to look blanket-like even if the base geometry improves.
- "Grainy terrain" is not primarily a UV problem in this path; it is mainly weak structural zoning plus procedural noise doing too much of the visual work.

Recommended fix:

- Introduce semantic masks for cliff, wetness, erosion, deposition, curvature, quiet zones, and cave dampness.
- Add dedicated cliff triplanar material logic and macro color breakup driven by those masks.

### 16. Scatter placement is still context-aware around buildings, not terrain-aware around landforms

Severity: Medium

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/_scatter_engine.py:318`
- `Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py:1688`

Details:

- `context_scatter()` picks props by nearest building affinity inside a square area.
- Terrain-aware vegetation placement exists, but the prop-scatter logic still does not consume cliff zones, riverbanks, waterfall bases, cave entrances, or hero-feature masks.

Impact:

- Asset placement can look random or biome-generic even when the terrain underneath is trying to communicate a specific feature.
- This is one of the main reasons scenes still read as procedural rather than authored.

Recommended fix:

- Add terrain-semantic asset zones and role tags, then place hero/support/filler assets through those masks instead of building affinity alone.

### 17. Terrain flow analysis is still too shallow for AAA water, materials, and validation

Severity: Medium

Files:

- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py:986`
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_world.py:268`
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py:1`

Details:

- `compute_flow_map()` is a D8 flow-direction and accumulation pass.
- `erode_world_heightmap()` only returns the eroded heightfield plus that flow map.
- The branch does not yet emit derived masks such as erosion amount, deposition, bank instability, talus zones, wetness proxy, or pool candidates.

Impact:

- Water, materials, cliffs, and asset rules are all forced to infer terrain meaning from too little data.
- The result is straight-cut channels, weak riverbank behavior, and material passes that cannot react intelligently to real landform logic.

Recommended fix:

- Expand the terrain-analysis layer so erosion and flow produce reusable semantic outputs, not just prettier heights.

## Highest-Value Fix Order

1. Remove or replace the dead `env_generate_world_terrain` command.
2. Fix fake multi-angle QA by implementing a real `render_angle` path.
3. Make `aaa_verify_map()` fail on empty or underspecified screenshot sets.
4. Fix tiled cliff overlay transforms and cliff height scaling.
5. Remove `[0, 1]` clipping from world-space terrain editing helpers.
6. Extend seam validation to multi-channel terrain data.
7. Replace public waterfall generation with a `_water_network.py`-driven pass.
8. Turn the terrain editing protocol into enforced runtime utilities.
9. Replace image-stat-only visual QA with terrain-aware review.
