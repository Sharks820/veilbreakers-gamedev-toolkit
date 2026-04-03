# Terrain & Environment Overhaul -- Critical Gap Analysis

**Date:** 2026-04-02
**Scope:** 16-stream terrain/environment design synthesis
**Method:** Full codebase audit against proposed design
**Verdict:** 34 gaps identified, 11 critical, 14 high, 9 medium

---

## 1. MISSING SYSTEMS

### GAP-01 [CRITICAL]: No NavMesh Generation Pipeline
The design covers terrain geometry, materials, vegetation, buildings, water -- but never mentions NavMesh. Unity's AI Navigation system needs baked NavMesh surfaces that account for terrain slope limits, water as non-walkable, building interiors as separate NavMesh surfaces, and dynamic obstacles (destructibles, vegetation). The codebase has encounter_spaces.py with spawn points and trigger volumes, but zero NavMesh integration. Without this, no NPC or enemy can pathfind.

**Impact:** All AI-driven gameplay is blocked.
**Fix:** Add NavMesh bake step to terrain pipeline. Define walkable slope angle per biome. Mark water/cliff/void as non-walkable. Generate NavMeshLink bridges for gaps. Handle interior-to-exterior NavMesh connections.

### GAP-02 [HIGH]: No Collision Mesh Strategy for Kitbash Buildings
The design specifies Tripo GLB kitbashing with grid-based alignment, but never addresses collision meshes. Tripo models are high-poly with internal geometry. Using them as-is for collision is a performance disaster. The pipeline removes internal faces but doesn't generate simplified convex decomposition colliders.

**Impact:** Players clip through buildings or physics framerate tanks.
**Fix:** Add convex decomposition step (V-HACD or similar) after internal face removal. Generate box/capsule primitives for regular shapes. Export collision meshes separately from visual meshes.

### GAP-03 [HIGH]: No Audio Zone / Reverb Zone Integration
The design covers lighting atmosphere (fog, tonemapping) per biome but has zero mention of spatial audio. The game project has a spatial audio system with occlusion (per STATE.md), but the terrain pipeline doesn't generate audio zone boundaries, reverb zones for interiors/caves, ambient sound trigger volumes, or water proximity audio regions.

**Impact:** Silent world or manually placed audio after the fact.
**Fix:** Generate AudioReverbZone components from building/cave enclosures. Define ambient audio profiles per biome. Create water proximity triggers. Export as part of terrain chunk metadata.

### GAP-04 [HIGH]: No Occlusion Culling Data Generation
The design mentions HLOD for distant objects but says nothing about occlusion culling. For a dark fantasy world with dense buildings, walls, and terrain features, occlusion culling is essential. Unity's built-in occlusion system needs bake data, and the design doesn't account for occluder/occludee marking on buildings or terrain features.

**Impact:** GPU renders objects behind walls/terrain, killing framerate.
**Fix:** Mark large opaque meshes (buildings, walls, terrain chunks) as Static Occluders. Mark smaller props as Occludees. Include occlusion bake step in pipeline.

### GAP-05 [MEDIUM]: No Minimap / World Map Data Export
The terrain pipeline generates heightmaps, biome data, road networks, and building placements -- but none of this feeds into a minimap or world map system. The game will need top-down renders or simplified map data.

**Impact:** No in-game navigation UI.
**Fix:** Export top-down orthographic render pass. Generate simplified 2D map from terrain + road + building data.

### GAP-06 [MEDIUM]: No Weather Particle Interaction with Terrain
The design covers atmosphere (fog, tonemapping) but not weather particle systems. Rain needs to interact with terrain (splash on surfaces, run off slopes), snow needs accumulation on horizontal surfaces, and wind should affect vegetation and particles consistently.

**Impact:** Weather feels disconnected from the world.
**Fix:** Define weather particle collision layers. Generate rain splash zones from terrain normals. Add snow accumulation mask from slope data.

---

## 2. INTEGRATION GAPS

### GAP-07 [CRITICAL]: Splatmap Transfer -- Blender Vertex Colors to Unity Alphamaps
The Blender side computes splatmap weights as vertex colors (RGBA per vertex in `terrain_materials.py`). The Unity side (`scene_templates.py`) expects `TerrainLayer` textures and `SetAlphamaps()` calls. There is NO converter between these formats. The vertex color splatmap data computed in Blender is never exported as a texture image or alphamap array. The Unity terrain setup just sets layer 0 to 1.0 everywhere (line 121-123 in scene_templates.py: "alphamaps[ay, ax, 0] = 1f").

**Impact:** All computed biome texturing is thrown away on Unity import.
**Fix:** Add splatmap-to-PNG export in Blender (render vertex colors to texture). OR compute alphamap arrays in Unity from the same slope/height rules. OR export splatmap data as a raw binary alongside the heightmap.

### GAP-08 [CRITICAL]: No Terrain Chunk Boundary Stitching
The `terrain_chunking.py` computes neighbor references (line 6: "computes neighbor references for edge stitching") but this is metadata only. There is NO actual edge-matching implementation. When two terrain chunks meet, their heightmap edges must be identical. The current bilinear LOD downsample doesn't guarantee edge consistency between neighboring chunks at different LOD levels.

**Impact:** Visible seams between terrain tiles, T-junctions, water flowing uphill at boundaries.
**Fix:** Implement shared-edge constraint: neighboring chunks must share identical edge vertices. LOD transitions need skirt meshes or geomorphing. Add seam validation test.

### GAP-09 [CRITICAL]: Blender LOD to Unity LOD Group Mapping
The Blender codebase has `lod_pipeline.py` with 7 LOD presets, but there's no mechanism to export LOD levels as separate meshes that Unity can consume as LODGroup components. The Tripo pipeline specifies "LOD chain" but doesn't define how LOD0-LOD3 meshes get packaged into a single prefab with LODGroup, transition distances, and screen-relative heights.

**Impact:** All assets ship as single-LOD, devastating performance.
**Fix:** Define LOD export format (multiple FBX/GLB per asset with naming convention). Generate Unity LODGroup setup script that reads LOD meshes and assigns transition distances.

### GAP-10 [HIGH]: Road Network Not Deforming Terrain
`road_network.py` generates road segments with MST connectivity, but roads are placed ON terrain without deforming the terrain underneath. Real roads need flattened terrain, embankments, drainage ditches, and smooth transitions to surrounding terrain.

**Impact:** Roads float above or cut through terrain surface.
**Fix:** Apply road-aware terrain deformation: flatten terrain under road segments, taper to natural elevation at road edges. Run road deformation BEFORE final erosion pass.

### GAP-11 [HIGH]: Building Placement Not Terracing Terrain
Buildings in the settlement generator create "plot markers" (per STATE.md: "Town generator creates plot markers but doesn't place buildings"). Even if buildings ARE placed, the terrain underneath is not flattened. Buildings on slopes will have floating corners or buried foundations.

**Impact:** Buildings look wrong on anything but flat terrain.
**Fix:** Generate terrain flattening zones around building plots. Create foundation geometry that bridges building base to terrain slope. Run building terracing after road deformation, before erosion.

### GAP-12 [HIGH]: Vegetation Scatter Ignores Building/Road Exclusion Zones
`vegetation_system.py` does Poisson disk placement with slope/height filtering, but has no awareness of buildings, roads, or other placed structures. Trees will grow through buildings and grass will cover road surfaces.

**Impact:** Vegetation clips through structures.
**Fix:** Generate exclusion masks from building footprints, road segments, and water bodies. Pass exclusion mask to vegetation scatter.

### GAP-13 [HIGH]: Water Body to Terrain Integration
The design mentions river meander simulation and flood-fill lake generation, but the existing `environment.py` handler only exports heightmaps. There's no mechanism to: carve river channels into terrain, set water level planes at correct heights, blend water edge materials with terrain, or handle the waterfall case where rivers drop over cliffs.

**Impact:** Water floats or sinks relative to terrain. River banks are hard edges.
**Fix:** Carve river channels into heightmap before export. Export water plane heights per river segment. Blend wet materials at water edges using moisture map.

### GAP-14 [MEDIUM]: Interior Streaming Connection Points
The design mentions building assembly but doesn't specify how exterior building meshes connect to interior streaming scenes. The codebase has `building_interior_binding.py` and `world_templates.py` with interior streaming, but there's no automated connection between: the kitbash building exterior -> door trigger placement -> interior scene name -> interior streaming load distance.

**Impact:** Buildings are visual shells with no gameplay access.
**Fix:** Define door anchor points in kitbash recipe. Auto-generate DoorTrigger components linked to interior scene names. Wire into InteriorStreamingManager.

---

## 3. PIPELINE GAPS

### GAP-15 [CRITICAL]: scipy / Numba Not Available in Blender's Bundled Python
The design proposes scipy `gaussian_filter` and Numba JIT. Blender ships its own Python with numpy but NOT scipy or numba. The codebase grep confirms: scipy appears only in the code reviewer's "forbidden external dependency" lists. Installing pip packages into Blender's Python is fragile and version-dependent.

**Impact:** Core erosion improvements are unimplementable as designed.
**Fix:** Replace scipy gaussian_filter with pure numpy convolution (np.convolve or manual kernel). Replace Numba JIT with numpy vectorization (the design already mentions numpy vectorized for grid-based erosion). If scipy is truly needed, implement manual Gaussian kernel.

### GAP-16 [CRITICAL]: No Automated End-to-End Pipeline Test
The pipeline is: noise -> erosion -> materials -> chunking -> export RAW -> Unity import -> splatmaps -> vegetation -> buildings. But there's no integration test that runs the full chain. Individual handlers have unit tests, but nothing validates that the output of one step is valid input for the next.

**Impact:** Pipeline breaks silently at integration boundaries.
**Fix:** Create end-to-end pipeline test: generate 257x257 terrain -> erode -> compute splatmap -> chunk -> export RAW -> validate Unity import dimensions. Test can run without Blender or Unity using pure-logic functions.

### GAP-17 [HIGH]: Tripo Model Interior Hollowing Not Addressed
Buildings from Tripo are solid meshes. The design says "remove internal faces" but Tripo buildings are often manifold solids. The pipeline needs: boolean subtraction to create interior void, wall thickness enforcement, window/door cutouts, and floor plane generation. None of this exists.

**Impact:** Buildings are solid blocks with no gameplay interior.
**Fix:** For kitbash buildings, use modular pieces (walls, floors, roofs) that are inherently hollow. For Tripo hero buildings, add boolean interior carving step. Accept that most Tripo buildings are exterior-only and pair with procedural interiors.

### GAP-18 [HIGH]: Texture Tiling Artifacts at Close Range
The design specifies texture tiling for splatmap layers but doesn't address close-range tiling repetition. At 15m tiling (default in scene_templates.py), walking on terrain reveals obvious pattern repeats. No detail texture, triplanar mapping, or stochastic tiling is mentioned.

**Impact:** Ground looks artificial when camera is near.
**Fix:** Add detail normal maps for close-range viewing. Implement triplanar mapping for cliff faces (prevents UV stretching). Consider stochastic tiling or noise-based UV offset for ground layers.

### GAP-19 [MEDIUM]: No Texture Compression / Format Strategy
The design mentions "compress textures" in the Tripo pipeline but doesn't specify formats. Unity needs: BC7 for albedo/normal on PC, ASTC for mobile, ETC2 as fallback. Blender exports raw PNG/EXR. The conversion step is missing.

**Impact:** Either huge texture memory or manual compression after pipeline.
**Fix:** Add texture import settings per platform in Unity asset pipeline. Use unity_assets tool with proper compression format per texture type.

### GAP-20 [MEDIUM]: Assembly Recipe Format Undefined
The design mentions "assembly recipes" for kitbash buildings but doesn't define the recipe format. What does a recipe look like? JSON? What fields? How do pieces reference each other? How are snapping points defined? The existing `_building_grammar.py` has building grammar rules, but the new kitbash system needs a different format for Tripo pieces.

**Impact:** Can't implement assembly without a format.
**Fix:** Define recipe schema: list of {piece_id, position, rotation, snap_point, material_override}. Define snap point format: {anchor_position, anchor_normal, compatible_tags}. Create recipe validator.

---

## 4. DEPENDENCY RISKS

### GAP-21 [HIGH]: GPU Resident Drawer Is Unity 6 Experimental
The design claims 99.7% draw call reduction from GPU Resident Drawer. This feature is relatively new in Unity 6 and has known limitations: doesn't work with all shader types, requires SRP Batcher compatibility, may have issues with dynamic batching, and doesn't support all material property blocks. The codebase has zero references to Forward+ or GPU Resident Drawer.

**Impact:** Performance pillar may not deliver as promised.
**Fix:** Implement performance system with GPU Resident Drawer as optional enhancement, not requirement. Test with actual scene complexity. Have fallback rendering path using standard SRP Batcher + GPU Instancing.

### GAP-22 [HIGH]: Adaptive Probe Volumes Require Careful Configuration
The design specifies APV for GI, but the Unity templates only generate legacy LightProbeGroup grids (see world_templates.py). APV is a different system that requires: volume configuration, probe density settings, baking workflow, and streaming support for large worlds. None of this exists in the Unity template system.

**Impact:** GI system uses old probes, not APV as designed.
**Fix:** Add APV configuration template to Unity world tools. Define probe density per area type (dense for interiors, sparse for open terrain). Plan for bake time in production schedule.

### GAP-23 [MEDIUM]: Tripo API Rate Limits and Credit Costs at Scale
The design mentions "face_limit in Tripo API calls" but doesn't address the cost of generating 100+ unique building pieces, vegetation assets, and props. At $0.10-0.50 per model, a full world could cost $50-200+ in API credits. Rate limits may throttle generation.

**Impact:** Budget overrun or generation bottleneck.
**Fix:** Define asset reuse strategy: X unique base pieces with Y material/scale variants. Generate hero pieces with Tripo, use procedural variants for fill. Cache all Tripo results aggressively.

### GAP-24 [MEDIUM]: 1025x1025 Heightmap Per Tile Memory
9 tiles (3x3 grid) at 1025x1025 uint16 = ~19MB raw heightmap data. With terrain mesh, splatmaps (4 layers per tile = 4 textures per tile), vegetation instance data, and building data, a single loaded area could exceed 2GB easily. The "Low 2GB VRAM" tier may not support even the 3x3 streaming window.

**Impact:** Low-end target may be unachievable.
**Fix:** Reduce heightmap to 513x513 for Low tier. Reduce splatmap resolution. Reduce vegetation density. Actually profile memory usage before committing to tier targets.

---

## 5. SCALE CONCERNS

### GAP-25 [HIGH]: Generation Time for Full World
No estimates are given for how long it takes to: generate a 1025x1025 heightmap with multi-pass erosion, compute splatmaps for 9 tiles, scatter vegetation across 9km^2, and place/generate all buildings. If each operation takes 30-60 seconds in Blender (via TCP), a full world could take hours of serial generation.

**Impact:** Iteration time too slow for development.
**Fix:** Profile each step. Parallelize where possible (vegetation and buildings can scatter in parallel). Pre-compute and cache erosion results. Consider generating at lower resolution and upsampling.

### GAP-26 [MEDIUM]: Vegetation Instance Counts
At densities listed in vegetation_system.py (trees 0.16 density, ground cover 0.36 density), a 1km^2 tile with Poisson disk placement could generate 50K-200K vegetation instances. Across 9 tiles, that's potentially 1.8M instances. Even with GPU instancing and DrawMeshInstancedIndirect, this needs careful LOD and distance culling.

**Impact:** GPU overload on mid-range hardware.
**Fix:** Define maximum instance counts per tile per quality tier. Implement distance-based density falloff (full density within 100m, 50% at 200m, billboard at 400m, cull beyond 600m).

---

## 6. VISUAL QUALITY GAPS

### GAP-27 [HIGH]: Terrain-to-Building Ground Seam
Where buildings meet terrain, there's always a visible seam. The design doesn't address: grounding buildings with decal "skirts" that blend into terrain, dirt/rubble accumulation at building bases, or foundation geometry that overlaps terrain edge.

**Impact:** Buildings look pasted onto the ground.
**Fix:** Generate ground decal rings around building footprints. Add dirt/debris mesh at building perimeter. Use vertex-blended material at building-terrain intersection.

### GAP-28 [HIGH]: LOD Pop-In on Vegetation
The design specifies GPU instancing for vegetation but doesn't define: LOD transition distances, crossfade dithering between LODs, or billboard distances for trees. Abrupt LOD switches are extremely noticeable on trees and large vegetation.

**Impact:** Distracting visual popping across the landscape.
**Fix:** Use screen-space dithered crossfade (SpeedTree-style) for tree LOD transitions. Define minimum 3 LODs per tree (full, reduced, billboard). Set crossfade band to at least 10% of transition distance.

### GAP-29 [MEDIUM]: Prop Repetition / Uniqueness
The design specifies modular pieces and Tripo generation but doesn't address how to avoid repetitive-looking environments. If you have 5 unique rock types scattered 1000 times each, the pattern becomes obvious. No mention of per-instance variation (color tint, scale jitter, rotation randomness, material weathering variation).

**Impact:** World looks procedurally generated (bad).
**Fix:** Define per-instance variation parameters: random scale 0.8-1.2, random Y rotation, random color tint shift within biome palette, random weathering intensity. Apply via GPU instancing material property overrides.

---

## 7. TESTING GAPS

### GAP-30 [HIGH]: No In-Engine Visual Validation Pipeline
Many visual quality issues (LOD pop-in, texture tiling, seams, lighting) are only detectable in-engine with the camera at specific positions. The design has no automated screenshot comparison, no reference frame validation, and no visual regression testing.

**Impact:** Visual bugs ship undetected.
**Fix:** Define camera path waypoints for automated visual testing. Capture screenshots at key positions. Compare against reference images. Flag significant pixel differences. Use unity_performance action=profile_scene after each major change.

### GAP-31 [MEDIUM]: Erosion Quality is Subjective
The design proposes specific erosion parameters (domain warping 0.4-0.7, bilateral filtering, etc.) but there's no quantitative metric for "good" terrain. How do you know if the erosion result looks right without visual inspection?

**Impact:** Parameters may need manual tuning per terrain type.
**Fix:** Define terrain quality metrics: height variance, drainage density, slope distribution histogram. Compare against reference terrain heightmaps from real geographic data.

---

## 8. DARK FANTASY SPECIFIC GAPS

### GAP-32 [CRITICAL]: No Veil Effect / Corruption Zone Terrain Modification
The game is called VeilBreakers. The Veil is presumably the central gameplay mechanic. The design mentions "corruption tint overlay" in terrain_materials.py and biome-specific vegetation (corrupted_swamp, veil_crack_zone), but there's no system for: dynamic corruption spread across terrain, Veil boundary visual effects (distortion, color shift, particle emission), terrain deformation from Veil influence (twisted ground, reality tears), or gameplay-affecting terrain changes in corruption zones.

**Impact:** The defining visual/gameplay feature of the game has no terrain integration.
**Fix:** Define Veil zone system: corruption intensity map (0-1) per terrain vertex. Blend corruption materials via additional splatmap channel. Add vertex displacement in corruption zones. Generate Veil boundary VFX trigger volumes. Make corruption zones dynamically expandable at runtime.

### GAP-33 [HIGH]: Boss Arena Terrain Requirements
The design mentions encounter_spaces.py with boss arena templates (arena_circle with 12m radius), but boss arenas in Soulsborne games need: custom terrain sculpting (elevated platforms, pits, obstacles), unique ground materials (bloodstained stone, ritual circles), controlled sightlines (pillars that block/reveal), and phase-specific terrain changes (floor breaking, arena expanding). The encounter system generates flat abstract layouts, not terrain-integrated arenas.

**Impact:** Boss fights feel generic.
**Fix:** Create boss arena terrain stamps: pre-sculpted heightmap patches that blend into surrounding terrain. Define arena material overlays. Generate cover geometry from terrain features, not just placed boxes.

### GAP-34 [HIGH]: No Destructible Environment Terrain Integration
`destruction_system.py` handles mesh damage states (pristine -> worn -> damaged -> destroyed) but this is isolated from terrain. When a building is destroyed, the terrain should show: rubble scatter, scorch marks, crater deformation. None of this exists.

**Impact:** Destruction feels disconnected from the world.
**Fix:** Define terrain modification events for destruction: crater stamp, debris scatter radius, material overlay (scorched earth, rubble). Apply at runtime or pre-bake for static destruction.

---

## 9. PLAYER EXPERIENCE GAPS

### GAP-35 [HIGH]: No Interaction Point / Loot Placement System
The terrain pipeline generates a world but doesn't define where players can: interact with objects (doors, levers, chests), find loot, discover crafting materials, or trigger story events. The encounter system has spawn points but no interaction points.

**Impact:** World exists but has no gameplay affordances.
**Fix:** Define interaction point types (loot, door, lever, NPC, crafting station). Generate placement rules per building type and biome. Export as tagged GameObjects with appropriate collider triggers.

### GAP-36 [MEDIUM]: No Player Traversal Aids
Dark fantasy games often have: ladders, ropes, ziplines, climbable walls, mantling points, and dodge-roll-safe zones. The terrain pipeline generates terrain and roads but no traversal infrastructure for verticality or shortcuts.

**Impact:** Player movement limited to walking on roads and terrain slopes.
**Fix:** Generate traversal point metadata: climbable cliff faces (based on slope + height), ladder anchor points on buildings, bridge connection points between elevated areas.

---

## 10. WHAT 16 RESEARCH AGENTS MISSED

### GAP-37 [CRITICAL]: No Terrain Streaming Scene Architecture
The design says "3x3 additive scene loading" but the architecture for this is undefined. How does each terrain tile become a Unity scene? What triggers load/unload? How do tile-local objects (vegetation, buildings, props) get assigned to the correct scene? The Unity template system (`world_templates.py`) has generic async scene loading but nothing terrain-grid-aware. The `terrain_chunking.py` exports JSON metadata for Unity but there's no Unity consumer for that metadata.

**Impact:** The streaming system is designed in Blender terms but has no Unity implementation.
**Fix:** Define terrain streaming architecture: TerrainStreamingManager that reads chunk metadata JSON, manages 3x3 active window, triggers async load/unload based on player position. Each tile is one additive scene containing: terrain, vegetation, buildings, props, triggers. Generate the scene setup scripts via unity_world tool.

### GAP-38 [HIGH]: Cross-Chunk Entity Awareness
When an enemy or NPC is near a chunk boundary, it needs to be aware of the adjacent chunk's navmesh and objects. The streaming system must handle: entities that span chunk boundaries, AI pathfinding across loaded chunks, physics interactions across chunk boundaries, and render distance extending beyond the current chunk.

**Impact:** AI and physics break at chunk edges.
**Fix:** Use a buffer zone (50-100m overlap) where chunks share entity awareness. Keep NavMesh baked across chunk boundaries. Use a global entity manager that's chunk-agnostic.

### GAP-39 [HIGH]: No Heightmap Resolution Validation
The design says 1025x1025 per 1km tile, but Unity Terrain requires heightmap resolution to be (2^n + 1). If the noise generator or erosion system produces a different resolution, the Unity import will fail silently or distort the terrain. There's no validation step ensuring the exported RAW file matches the expected resolution.

**Impact:** Corrupted terrain import.
**Fix:** Add resolution validation assertion at export time. Ensure all terrain operations preserve the (2^n + 1) resolution. Add a test that round-trips a heightmap through export/import and verifies height accuracy.

### GAP-40 [MEDIUM]: No Fallback for Failed Tripo Generations
The pipeline assumes Tripo generates valid models. In practice, AI 3D generation has a ~10-30% failure rate (degenerate meshes, missing parts, wrong scale). The design has no retry logic, quality scoring gate, or fallback to procedural alternatives.

**Impact:** Pipeline stalls or ships broken assets.
**Fix:** Add quality gate after Tripo download: check vertex count, check bounding box dimensions, check manifold status. On failure: retry with different seed (max 3 attempts), then fall back to procedural mesh from existing 267 generators.

---

## Summary Table

| ID | Severity | Category | Gap |
|----|----------|----------|-----|
| GAP-01 | CRITICAL | Missing System | No NavMesh generation pipeline |
| GAP-07 | CRITICAL | Integration | Splatmap data never transfers Blender->Unity |
| GAP-08 | CRITICAL | Integration | Terrain chunk boundary stitching is metadata-only |
| GAP-09 | CRITICAL | Integration | Blender LOD meshes don't map to Unity LODGroups |
| GAP-15 | CRITICAL | Dependency | scipy/Numba not in Blender Python |
| GAP-16 | CRITICAL | Testing | No end-to-end pipeline integration test |
| GAP-32 | CRITICAL | Dark Fantasy | Veil/corruption has no terrain integration |
| GAP-37 | CRITICAL | Architecture | Terrain streaming has no Unity-side implementation |
| GAP-02 | HIGH | Missing System | No collision mesh strategy for buildings |
| GAP-03 | HIGH | Missing System | No audio zone / reverb integration |
| GAP-04 | HIGH | Missing System | No occlusion culling data generation |
| GAP-10 | HIGH | Integration | Roads don't deform terrain |
| GAP-11 | HIGH | Integration | Buildings don't terrace terrain |
| GAP-12 | HIGH | Integration | Vegetation ignores building/road exclusion |
| GAP-13 | HIGH | Integration | Water body not integrated with terrain |
| GAP-17 | HIGH | Pipeline | Building interiors from Tripo not addressed |
| GAP-18 | HIGH | Pipeline | Texture tiling visible at close range |
| GAP-21 | HIGH | Dependency | GPU Resident Drawer is experimental |
| GAP-22 | HIGH | Dependency | APV templates don't exist in Unity tools |
| GAP-25 | HIGH | Scale | Generation time for full world unestimated |
| GAP-27 | HIGH | Visual | Terrain-to-building seam |
| GAP-28 | HIGH | Visual | LOD pop-in on vegetation |
| GAP-30 | HIGH | Testing | No in-engine visual validation |
| GAP-33 | HIGH | Dark Fantasy | Boss arenas lack terrain sculpting |
| GAP-34 | HIGH | Dark Fantasy | Destruction doesn't affect terrain |
| GAP-35 | HIGH | Player Experience | No interaction / loot point placement |
| GAP-38 | HIGH | Architecture | Cross-chunk entity awareness |
| GAP-39 | HIGH | Pipeline | No heightmap resolution validation |
| GAP-05 | MEDIUM | Missing System | No minimap / world map data export |
| GAP-06 | MEDIUM | Missing System | Weather particle interaction with terrain |
| GAP-14 | MEDIUM | Integration | Interior streaming connection undefined |
| GAP-19 | MEDIUM | Pipeline | No texture compression strategy |
| GAP-20 | MEDIUM | Pipeline | Assembly recipe format undefined |
| GAP-23 | MEDIUM | Dependency | Tripo credit costs at scale |
| GAP-24 | MEDIUM | Dependency | Low-tier VRAM target may be unachievable |
| GAP-26 | MEDIUM | Scale | Vegetation instance count management |
| GAP-29 | MEDIUM | Visual | Prop repetition / uniqueness |
| GAP-31 | MEDIUM | Testing | Erosion quality is subjective |
| GAP-36 | MEDIUM | Player Experience | No traversal aids (ladders, climbing) |
| GAP-40 | MEDIUM | Pipeline | No fallback for failed Tripo generations |

---

## Priority Execution Order

**Must fix before implementation begins:**
1. GAP-15: Replace scipy/Numba with numpy equivalents (blocks all erosion work)
2. GAP-07: Define splatmap export format (blocks material pipeline)
3. GAP-08: Implement chunk edge stitching (blocks streaming)
4. GAP-09: Define LOD export -> LODGroup pipeline (blocks asset pipeline)
5. GAP-37: Design terrain streaming Unity architecture (blocks all Unity integration)

**Must fix during implementation:**
6. GAP-01: NavMesh integration
7. GAP-32: Veil/corruption terrain system
8. GAP-16: End-to-end pipeline test
9. GAP-10/11/12/13: Terrain deformation for roads, buildings, water, vegetation exclusion
10. GAP-02: Collision mesh strategy

**Should fix before shipping:**
11. GAP-27/28: Visual seams and LOD pop-in
12. GAP-33/34: Boss arenas and destructible terrain
13. GAP-35: Interaction points
14. GAP-03/04: Audio zones and occlusion culling
15. Everything else

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|-----------|-------|
| Integration gaps (7-14) | HIGH | Directly verified by reading source code on both sides of each boundary |
| Dependency risks (15, 21-24) | HIGH | Verified scipy/numba absence via grep, Forward+/APV absence confirmed |
| Missing systems (1-6) | HIGH | Searched entire codebase for NavMesh, audio zone, occlusion terms |
| Dark fantasy gaps (32-34) | MEDIUM | Based on codebase audit + genre knowledge; actual game design may cover these elsewhere |
| Scale concerns (25-26) | MEDIUM | Theoretical; needs profiling to confirm |
| Visual quality (27-29) | MEDIUM | Common issues in terrain systems; actual impact depends on art style |
