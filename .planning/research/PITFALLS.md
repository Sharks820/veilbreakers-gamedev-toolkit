# Domain Pitfalls: AAA Procedural 3D Architecture

**Domain:** Procedural 3D generation for AAA dark fantasy RPG (Blender + Unity pipeline)
**Researched:** 2026-03-30
**Confidence:** HIGH (verified against existing project research, gap analysis, AAA benchmarks, and production post-mortems)

---

## Critical Pitfalls

Mistakes that cause rewrites, user-visible quality failures, or project abandonment.

---

### Pitfall 1: Placeholder Primitives Masquerading as AAA Assets

**What goes wrong:**
Procedural generators produce scaled cubes for furniture (tables are 1.2x1.2x0.75 boxes), cones for trees, icospheres for bushes, and cylinders for pillars. These read as placeholder blocking, not game geometry. The v3.0 gap analysis identified this as the single largest systemic issue: placement systems output geometric primitives while the scatter engine, interior layout, and dungeon BSP are AAA-grade. The gap analysis found 67 gaps with furniture/props at 20% coverage and environmental detail at 25% coverage -- precisely because all placed objects are primitives.

**Why it happens:**
Procedural placement is architecturally easier than procedural mesh generation. Placing a cube at coordinates (x, y, z) is trivial. Generating a table with four turned legs, a beveled top, and wood grain surface detail is substantially harder. Developers build the placement system first (it shows results immediately), then never circle back to replace the placeholder geometry with actual meshes.

**How to avoid:**
1. Build the procedural mesh generation library FIRST, before any placement or scattering system. If you cannot generate a table mesh, you cannot test whether the placement system works.
2. Define mesh generators by parametric blueprints: a table generator takes `leg_style`, `top_thickness`, `surface_detail` and produces a real mesh with topology grading.
3. Enforce a "no primitives in production" rule: every `bpy.ops.mesh.primitive_cube_add` in generator code that is not a collision mesh must be replaced with a proper mesh generator.
4. The Skin Modifier approach (from CHARACTER_MESH_QUALITY_TECHNIQUES.md) can produce organic continuous meshes for characters, vegetation, and natural forms. Use it instead of primitive assembly.

**Warning signs:**
- Generated scenes contain objects named "Cube", "Cone", "Sphere" instead of descriptive names
- Mesh analysis reports "8 faces" for a "table" object
- Screenshots show blocky, Minecraft-like geometry instead of detailed dark fantasy props
- Contact sheet reviews show identical silhouette across all props of a category

**Phase to address:**
Phase 1 (Procedural Mesh Foundation) -- build the mesh generation library before any other content work.

---

### Pitfall 2: Uniform Roughness Makes Everything Look Like Plastic

**What goes wrong:**
All generated materials have flat roughness values (e.g., roughness=0.5 everywhere). Stone looks like gray plastic. Metal looks like shiny plastic. Wood looks like brown plastic. This is the single most common visual quality killer in procedural generation -- the AAA research explicitly identifies it: "roughness variation is king" and "flat uniform roughness is the #1 differentiator between cheap and professional PBR."

**Why it happens:**
Procedural material generators assign a single roughness value per material. But real-world materials have roughness variation within a single surface: edges are smoother (worn by contact), crevices are rougher (dust accumulation), flat surfaces have subtle variation (fingerprints, use patterns). Without this variation, Principled BSDF with uniform roughness produces the "plastic look" regardless of how good the geometry is.

**How to avoid:**
1. Never assign a single roughness float. Always use a roughness texture map with procedural noise.
2. For every material, add a Curvature-based wear map (the toolkit already has `handle_generate_wear_map`). Edges get lower roughness (polished), crevices get higher roughness (dirt).
3. Use the Blender node approach: Noise Texture (scale 50-200) + color ramp to add micro-roughness variation on top of the base roughness value.
4. Implement material presets with roughness ranges, not single values: Stone roughness 0.6-0.9, Polished metal 0.1-0.3, Leather 0.5-0.8, Fabric 0.7-1.0.
5. Add AO darkening to crevices (10-30%, not black halos).

**Warning signs:**
- All materials in a scene have the same specular highlight behavior
- Stone walls reflect light uniformly across the entire surface
- Metal objects look like molded plastic, not forged iron
- validate_palette passes but the scene still looks "off"

**Phase to address:**
Phase 1 (Procedural Mesh Foundation) -- material presets must be defined alongside mesh generators, not added later.

---

### Pitfall 3: Heightmap Terrain Cannot Represent Vertical Geometry

**What goes wrong:**
Terrain is generated as a heightmap grid (one height value per XY position). This fundamentally cannot represent vertical cliffs, overhangs, cave mouths, or arch formations. When the game requires dramatic cliff walls or cave entrances (a dark fantasy staple), the terrain system silently produces sloped ramps instead of vertical faces. The gap analysis identified cliff face generation and cave entrance geometry as CRITICAL gaps.

**Why it happens:**
Heightmap terrain is the standard approach in both Blender and Unity. It is computationally efficient and well-supported. The limitation only becomes apparent when the design calls for features that require 2+ height values at the same XY position (cliff overhangs, cave tunnels, natural arches). By the time this is discovered, the entire terrain pipeline is built around heightmap assumptions.

**How to avoid:**
1. Accept the heightmap limitation for the base terrain surface. Do not fight it.
2. Implement a separate mesh object layer for vertical features: cliff face meshes, overhang geometry, cave entrance transition pieces. These are placed on top of the heightmap, not carved into it.
3. Use modular kit pieces for cliff faces (straight, corner, curved sections) that snap to terrain edges.
4. Create transition meshes where vertical cliff meets terrain surface (blended vertex colors + terrain material matching).
5. In the Unity terrain shader, add height-based blending that matches the cliff mesh material at the seam.

**Warning signs:**
- Mountain slopes look like smooth ramps instead of dramatic cliff faces
- Cave entrances are just dark spots on a hillside, not actual openings
- Rivers carve V-shaped valleys instead of the steep-walled canyons dark fantasy requires
- Terrain cross-sections show smooth curves everywhere, no verticality

**Phase to address:**
Phase 2 (Terrain and Environment) -- cliff/overhang mesh generation must be part of the terrain system, not bolted on after.

---

### Pitfall 4: Per-Object Budget Passes But Scene Budget Fails

**What goes wrong:**
Every individual prop passes `game_check` (under its poly budget, valid UVs, correct material). But a furnished room contains 50 props, each at their individual limit, totaling 100K+ triangles plus 50 draw calls. A town with 20 buildings, each under budget, plus vegetation scatter produces 2M+ triangles. The scene crawls at 15 FPS despite every individual asset being "optimized." The gap analysis identified cross-asset polycount budgeting as a HIGH gap.

**Why it happens:**
Quality validation checks operate on individual objects (`game_check` validates per-object poly budgets). No tool sums visible objects in a scene and validates against a frame budget. Developers check each asset in isolation and assume the total will be fine.

**How to avoid:**
1. Define scene-level budgets alongside per-object budgets:
   - Visible scene at 60 FPS PC: 2-6M triangles, 500-2000 draw calls, 4GB VRAM
   - Single room interior: 50K-150K triangles total (all furniture + walls + props)
   - Town block (10 buildings + roads + scatter): 200K-500K triangles total
2. Build a scene budget auditor that sums all visible objects and compares against frame budgets.
3. Use LOD aggressively: LOD2 at 15% screen space, LOD3 at 5%, cull below 2%.
4. Use GPU instancing for repeated props (barrels, crates, vegetation). One draw call for all barrels, not one per barrel.
5. Implement a per-room prop budget: each room type gets a maximum triangle count, and the furnishing generator must stay under it.

**Warning signs:**
- Frame rate drops significantly in furnished rooms vs. empty rooms
- Draw call count exceeds 1000 in town scenes
- GPU profiler shows triangle count well under per-object budgets but total scene is over frame budget
- Vegetation scatter with 1000+ instances causes visible stuttering

**Phase to address:**
Phase 2 (Terrain and Environment) -- scene budgets must be defined before populating environments.

---

### Pitfall 5: Cookie-Cutter Buildings From Identical Modules

**What goes wrong:**
Modular kit buildings use the same 5-10 wall/floor/roof pieces in the same combinations. Every building in the town looks like the same structure with slightly different dimensions. The player cannot tell the tavern from the blacksmith from the guard barracks by silhouette alone. This is the "procgen sameness" problem -- technically correct but visually boring.

**Why it happens:**
Modular kit design constrains the part vocabulary to a small set of snap-together pieces. Without variation systems (damage states, material swaps, trim overlays, narrative props), every assembly from the same kit produces buildings with identical character. The building grammar produces structural variation but not visual variation.

**How to avoid:**
1. Each kit style needs 25-40 module pieces minimum (per AAA_BEST_PRACTICES_COMPREHENSIVE.md), including 4-6 damage/variation pieces.
2. Implement a narrative dressing layer: `add_storytelling_props` places context-specific clutter (horseshoes at the blacksmith, tankards at the tavern, weapons at the guard barracks). These break the visual monotony.
3. Use vertex color randomization per-instance: slight hue shifts on walls, different weathering patterns on each building.
4. Create variant sub-kits: a "dark_fantasy" building kit needs pristine, weathered, damaged, corrupted, and ruined sub-variants.
5. Implement silhouette variation through roof shape (peaked, flat, domed, spired), wall height, and building footprint asymmetry -- not just width/depth scaling.
6. Add the overrun_variant system to existing buildings (WORLD-09) to create corrupted versions with different visual character.

**Warning signs:**
- Screenshots of different buildings could be swapped and nobody would notice
- All buildings in a town have the same roof angle and wall texture
- The only visual difference between a tavern and a temple is the sign text
- Silhouette_test returns similar silhouette scores for all building types

**Phase to address:**
Phase 3 (Building and Architecture) -- kit variation must be designed into the module set, not applied as post-processing.

---

### Pitfall 6: Terrain-Building Seam Gaps and Z-Fighting

**What goes wrong:**
Buildings placed on procedural terrain either float above the terrain surface (visible gap underneath) or intersect it (walls clipping through terrain, doors blocked by ground mesh). When building floors and terrain heightmaps occupy the same Y coordinate, z-fighting produces flickering artifacts. This is the terrain/building mesh integration problem (MESH-05) and it is one of the most visible quality failures -- players walk through a town and see buildings hovering or partially buried.

**Why it happens:**
Terrain heightmaps have limited resolution (typically 512x512 or 1024x1024 grid). A building footprint is a rectangle that rarely aligns to the heightmap grid. The terrain height at the building corner might be 12.3m while the building floor is at 12.0m (designed for "flat ground"). The heightmap cannot represent a flat building pad within a sloped terrain without flattening the entire area.

**How to avoid:**
1. Terrain flattening at building sites: when placing a building, flatten the terrain heightmap under the building footprint to the building's floor height. Use cosine-blended falloff at the edges (from MAP_BUILDING_TECHNIQUES.md, Unreal Landscape Spline approach).
2. Foundation meshes: every building gets a foundation mesh that extends below the floor height by 0.3-0.5m. This hides the terrain-building seam.
3. Height probing: before placing a building, sample the terrain height at all four corners. If the height difference exceeds a threshold (0.3m), either reject the placement or adjust the building floor height.
4. Terrain skirt meshes: create transition geometry between building walls and terrain -- stone foundations, dirt berms, stepped terracing for hillside buildings.
5. In Unity, use terrain decals at building perimeters to blend the transition visually.

**Warning signs:**
- Buildings visible floating above terrain from certain camera angles
- Terrain clipping through building floors
- Z-fighting flicker at building bases
- Doors that cannot be entered because terrain blocks the threshold

**Phase to address:**
Phase 2 (Terrain and Environment) -- terrain-building integration must be solved before town/city generation.

---

### Pitfall 7: Tripo Pipeline Quality Does Not Match Procedural Quality

**What goes wrong:**
AI-generated models from Tripo3D have different topology, texture style, and proportions than procedurally generated Blender meshes. When mixed in the same scene (e.g., Tripo-generated hero character standing next to procedural buildings), the style clash is jarring. Tripo models have dense triangle soup (200K-2M tris) while procedural models have clean topology. Tripo textures are photo-realistic while procedural textures use node-based PBR. The combination looks like two different art directors worked on the same scene.

**Why it happens:**
The Tripo pipeline and the procedural pipeline are separate workflows with separate quality standards. Tripo output goes through: generate -> cleanup -> retopo -> UV -> texture. Procedural output goes through: mesh generation -> material presets. These pipelines produce fundamentally different aesthetic results even when targeting the same art style.

**How to avoid:**
1. Define a unified art style validation pass that both pipelines must pass. Use `validate_art_style` (PROD-04) with dark fantasy palette enforcement.
2. Apply a consistent material override: regardless of source (Tripo or procedural), all assets in a scene use the same master material library (20-40 materials from AAA_QUALITY_ASSETS.md Section 2.1).
3. Run the de-lighting pass (`texture_ops.py handle_delight`) on ALL textures, Tripo and procedural alike, to normalize lighting information.
4. Use the same texel density standard (10.24 px/cm baseline) enforced by `uv_equalize_density` for both pipelines.
5. Create a style transfer step for Tripo textures: adjust hue/saturation/value to match the dark fantasy palette before compositing into the scene.

**Warning signs:**
- Tripo characters look photorealistic while buildings look stylized (or vice versa)
- Texture resolution differs visibly between AI and procedural assets
- Material response to lighting is noticeably different between sources
- Color temperature shifts between Tripo and procedural objects in the same scene

**Phase to address:**
Phase 4 (Pipeline Integration) -- style normalization must be part of the pipeline, not a manual review step.

---

### Pitfall 8: LOD Decimation Destroys Silhouette Readability

**What goes wrong:**
Automatic LOD generation (decimate modifier at 50%, 25%, 10%) produces LOD meshes that lose the distinctive silhouette of the original. A sword with an ornate cross-guard becomes a plain stick at LOD2. A building with a peaked roof becomes a blob at LOD3. At distance, all objects collapse into similar-looking low-poly shapes, destroying the visual identity that the player uses for navigation and recognition.

**Why it happens:**
Decimate modifier operates uniformly across the mesh. It reduces polygon count without understanding which features are structurally important (silhouette-defining edges) versus which are surface detail (engravings, bevels). The most distinctive features (guard shape, roofline, spire) are often the first to be simplified because they have the highest local curvature.

**How to avoid:**
1. Use per-asset-type LOD presets, not uniform decimation ratios:
   - Weapons: preserve silhouette profile, simplify surface detail first
   - Buildings: preserve roofline and wall outlines, simplify interior detail
   - Characters: preserve face detail at LOD2, simplify body aggressively
   - Props: preserve bounding shape, simplify all surface detail
2. Implement silhouette-preserving decimation: weight edge collapse cost by silhouette importance. Edges on the mesh silhouette (perpendicular to view) have higher cost than interior edges.
3. For LOD3, consider billboard/impostor approach instead of further decimation. A sprite captured from the original looks better than 50 triangles of blob.
4. Validate each LOD level with silhouette_test at the expected viewing distance for that LOD level.
5. Use the region-weighted vertex importance system (from v3.0) to guide LOD reduction on characters.

**Warning signs:**
- Distant objects all look like featureless blobs
- Players cannot identify building types from distance
- LOD transitions cause visible shape change (not just detail change)
- Weapon outlines change shape between LOD1 and LOD2

**Phase to address:**
Phase 1 (Procedural Mesh Foundation) -- LOD presets must be defined alongside mesh generators.

---

### Pitfall 9: Boolean Operations Produce Dirty Geometry

**What goes wrong:**
Using boolean operations (DIFFERENCE, UNION, INTERSECT) for procedural mesh construction (carving windows, adding detail, cutting doorways) produces non-manifold edges, degenerate faces, T-junctions, and micro-patches. These artifacts cause rendering errors (shadow acne, light leaking), physics collision problems, and UV unwrap failures. The gap analysis identified mesh boolean cleanup as a systemic cross-cutting gap.

**Why it happens:**
Boolean operations on arbitrary meshes are numerically imprecise. When a cutter mesh intersects a target mesh at angles or positions that create near-coincident vertices, the boolean algorithm produces floating point approximation artifacts. These are invisible at creation time but cause cascading failures in downstream operations (UV unwrap, normal calculation, physics mesh generation).

**How to avoid:**
1. Run mandatory post-boolean cleanup after every boolean operation:
   - Remove doubles (merge_distance=0.001)
   - Recalculate normals
   - Delete loose geometry
   - Fill holes (max_hole_sides=4)
   - Check for non-manifold edges
2. Prefer non-boolean construction methods where possible: extrude faces instead of boolean-cut holes, inset instead of boolean-add detail, mirror instead of boolean-union symmetric halves.
3. When booleans are unavoidable, use clean input meshes: no n-gons, no non-manifold geometry, no overlapping faces. Run `mesh analyze` on both inputs before the boolean.
4. After boolean + cleanup, validate the result with `game_check` before proceeding.

**Warning signs:**
- Mesh analyze reports non-manifold edges after boolean operations
- UV unwrap produces islands with zero area
- Shadow artifacts appear on boolean-cut surfaces
- Physics collision mesh has holes or spikes

**Phase to address:**
Phase 1 (Procedural Mesh Foundation) -- boolean cleanup must be part of every mesh generator that uses booleans.

---

### Pitfall 10: Context Window Bloat During Generation Sessions

**What goes wrong:**
Generating a complete town with 20 buildings, furnishing interiors, scattering vegetation, and validating quality consumes enormous LLM context. Each tool call returns structured data (vertex counts, material assignments, validation results). After generating 10 buildings, the context window is 60-70% full. After furnishing interiors, it hits 80%. The auto-compact threshold fires and the LLM loses track of what it has already generated, leading to duplicate objects, inconsistent naming, and broken references.

**Why it happens:**
Each procedural generation step produces structured output (JSON responses with metrics, coordinates, validation data). The compound tool pattern reduces token overhead per tool call, but the cumulative output from 50+ sequential operations fills the context. The LLM cannot "forget" intermediate results selectively -- compaction removes the oldest content, which is often the architectural decisions and constraints from the beginning of the session.

**How to avoid:**
1. Implement state persistence: write generation state (building list, prop placements, validation results) to files on disk, not in the conversation context. Reference files by name, not by content.
2. Use the auto-compact workflow at 80% (MESH-14). Design generators to be stateless -- each generator reads its input from files, not from conversation history.
3. Batch generation calls: instead of "generate one building" repeated 20 times, use "generate town" as a single operation that produces all buildings. One tool call, one response.
4. Compress validation output: instead of full `game_check` reports, return pass/fail with a single-line summary. Log full details to a file.
5. Use the GLM memory persistence (MESH-15) to save learnings between sessions rather than re-deriving them from context.

**Warning signs:**
- LLM generates duplicate buildings that already exist in the scene
- Object naming becomes inconsistent (Building_01, building_2, BUILDING-03)
- Validation results from earlier objects are referenced incorrectly
- Context compaction causes the LLM to "forget" the art style constraints

**Phase to address:**
Phase 1 (Procedural Mesh Foundation) -- state persistence and batch operations must be designed into the generator architecture.

---

## Technical Debt Patterns

Shortcuts that seem reasonable during procedural generation but create long-term quality problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Cube placeholders for props | Quick scene blocking, validates placement logic | Must replace every placeholder with actual mesh later; double work | Initial prototyping only, NEVER in production |
| Single roughness value per material | Simple material system, fewer texture maps | Everything looks like plastic; must regenerate all materials | Never |
| Uniform decimation for LOD | One line of code for all LOD levels | Silhouette destruction; must create per-type LOD presets | Prototyping only |
| Heightmap-only terrain | Well-supported, fast rendering | No cliffs, caves, or overhangs; must add mesh overlay system | Base terrain only; vertical features must be separate meshes |
| Boolean for all detail | Fast way to cut windows, doors, notches | Dirty geometry cascading into UV/normal/shadow failures | Only with mandatory post-boolean cleanup |
| One texture per material | Simpler pipeline, fewer draw calls | No PBR variation, no micro-detail, plastic look | Never for visible surfaces |
| Global random seed only | Reproducible scenes from one seed | Cannot regenerate individual elements; must regenerate entire scene | Acceptable if elements also support local seeds |

## Integration Gotchas

Common mistakes when connecting procedural generation to external systems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Tripo3D output -> Blender cleanup | Assume cleanup fixes all AI defects | Cleanup handles topology normals/holes. Must also: de-light textures, validate UV seam placement, enforce texel density, check scale |
| Blender export -> Unity import | Assume FBX "just works" | Must: apply modifiers, set correct Forward/Up axes, embed materials, validate scale (Blender 1m = Unity 1m but FBX importer applies 0.01x), use glTF when possible |
| Procedural material -> Unity URP | Export Cycles shader nodes | Cycles nodes do not convert to URP. Export texture maps (albedo/normal/MRAO), apply URP Lit shader in Unity |
| Terrain heightmap -> Unity terrain | Export raw heightmap at arbitrary resolution | Unity terrain expects specific resolution (513x513 for 512x512 terrain). Must export with correct bit depth (16-bit) and correct byte order |
| Scatter instances -> Unity | Export as individual mesh objects | Must export as collection instances or convert to GPU instancing. Individual objects = massive draw call count |
| Modular kit pieces -> Unity snapping | Assume Unity uses same grid as Blender | Unity transform snapping uses different defaults. Export kit pieces with pivot at bottom-left-back, document grid size in metadata |
| AI character mesh -> Rigify rig | Auto-weight after retopo | Retopo'd mesh has no vertex groups. Must: retopo -> mark sharp edges -> define UV seams -> THEN auto-weight. Skipping steps produces garbage weights |

## Performance Traps

Patterns that work at small scale but fail as scene complexity grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-prop unique materials | Draw calls spike to 500+ in furnished room | Material atlas per room/kit; share materials across props | >10 props with unique materials in view |
| No LOD on scatter instances | Frame drop when looking at forest | LOD Groups on scatter templates; billboard at distance | >50 instanced trees in view |
| Heightmap resolution too high | Terrain mesh has 1M+ faces; slow to export and import | Use 512x512 or 1024x1024 max; quadtree LOD in Unity | >1024x1024 heightmap grid |
| Furnishing without prop budget | Room with 50 props = 100K+ triangles | Define per-room triangle budget; prioritize and cut | >20 props in a single room |
| Physics mesh per-prop | Unity physics engine overwhelmed | Use simplified collision meshes (box/capsule), share across instances | >30 physics-enabled props in scene |
| No texture atlasing for kit pieces | Each modular wall segment = 1 draw call | One shared material per kit; trim sheet atlas for all pieces | >15 kit pieces in view |
| Real-time boolean computation | Frame drops during generation, not runtime | Pre-compute all booleans; bake results to static meshes | Any real-time boolean in game loop |
| Uncompressed textures in generation | Memory spikes during batch texture operations | Use compressed formats (BCn/DXT) for intermediate textures when possible | >10 textures at 2048x2048 simultaneously |

## "Looks Done But Isn't" Checklist

Things that appear complete during generation but are missing critical pieces.

- [ ] **Procedural building:** Often missing interior geometry -- verify walls have thickness (not paper-thin planes), floors have undersides, windows have frames (not holes)
- [ ] **Furnished room:** Often missing collision meshes -- verify every prop has a simplified collision shape for player interaction
- [ ] **Terrain vegetation scatter:** Often missing LOD -- verify scattered objects have LOD groups set up, not just the base mesh
- [ ] **Material assignment:** Often missing PBR maps -- verify not just albedo but also normal, roughness, metallic, AO maps are generated and assigned
- [ ] **UV unwrap:** Often missing texel density validation -- verify UV density matches the scene standard (10.24 px/cm), not just that UVs exist
- [ ] **Export validation:** Often missing scale check -- verify exported mesh matches expected world-space dimensions in Unity (1 Blender unit = 1 Unity meter)
- [ ] **Scene composition:** Often missing lighting setup -- verify scene has proper light sources (sun, ambient, point lights for interiors), not just geometry
- [ ] **Kit piece snapping:** Often missing gap check -- verify pieces snap without visible seams (gap < 0.5mm), not just that they align to grid
- [ ] **Tripo cleanup pipeline:** Often missing de-lighting -- verify albedo has no baked-in shadows/ambient occlusion from the AI generator
- [ ] **LOD chain:** Often missing silhouette validation -- verify LOD3 is still recognizable as the same object, not just that it has fewer polygons

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Placeholder primitives in production | HIGH | Replace every primitive with parametric mesh generator. Requires building mesh library retroactively. Worst case: regenerate entire scene. |
| Plastic-looking materials | MEDIUM | Add roughness variation maps to all materials. Can be done post-hoc with procedural node graph updates. Does not require regenerating geometry. |
| No vertical terrain features | HIGH | Add cliff/overhang mesh overlay system. Requires new generator code and re-placement on existing terrain. Cannot fix existing heightmap. |
| Scene budget exceeded | MEDIUM | Audit scene, identify over-budget objects, reduce LOD levels, merge instances, remove unnecessary props. Can be done without regenerating assets. |
| Cookie-cutter buildings | MEDIUM | Add variation overlays (vertex color randomization, narrative props, damage states). Does not require regenerating structural mesh. |
| Terrain-building seam gaps | MEDIUM | Add foundation meshes and terrain flattening. Can be retrofitted to existing buildings. |
| Style mismatch between pipelines | MEDIUM | Apply style transfer / color grading pass to normalize. Can be automated as a pipeline step. |
| LOD silhouette destruction | LOW | Re-generate LOD chain with silhouette-preserving weights. Does not affect LOD0. |
| Boolean dirty geometry | MEDIUM | Run post-boolean cleanup on affected meshes. May require re-unwrapping UVs and re-baking textures. |
| Context window bloat | LOW | Implement state persistence, compact and reload from files. Existing generation is not lost, just context. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Placeholder primitives | Phase 1: Mesh Foundation | Generate 10 props, run mesh_analyze -- all must pass A/B topology grade |
| Plastic materials | Phase 1: Mesh Foundation | Apply material to test object, render in MATERIAL shading, verify non-uniform specular highlights |
| No vertical terrain | Phase 2: Terrain and Environment | Generate terrain with cliff feature, verify vertical faces exist and cave entrance transitions work |
| Scene budget overflow | Phase 2: Terrain and Environment | Furnish 5 rooms, run scene profiler, verify total under room budget |
| Cookie-cutter buildings | Phase 3: Building and Architecture | Generate town of 20 buildings, run silhouette_test comparison -- all must be distinguishable |
| Terrain-building gaps | Phase 2: Terrain and Environment | Place building on sloped terrain, screenshot from below -- verify no gap visible |
| Pipeline style mismatch | Phase 4: Pipeline Integration | Place Tripo character next to procedural building, run validate_art_style -- both pass |
| LOD silhouette destruction | Phase 1: Mesh Foundation | Generate LOD chain for 5 asset types, verify LOD2 silhouette score within 15% of LOD0 |
| Boolean dirty geometry | Phase 1: Mesh Foundation | Run boolean test suite, verify 0 non-manifold edges on all results |
| Context window bloat | Phase 1: Mesh Foundation | Generate 20 objects in sequence, verify state persisted to disk and retrievable |

## Sources

### Project Research (HIGH confidence -- verified against codebase and prior analysis)
- `.planning/research/3d-modeling-gap-analysis.md` -- 67 gaps identified, primitives-as-placeholders is systemic issue
- `.planning/research/AAA_QUALITY_ASSETS.md` -- PBR quality standards, roughness variation, polygon budgets, texture resolutions
- `.planning/research/AAA_BEST_PRACTICES_COMPREHENSIVE.md` -- Modular kit design, terrain blending, LOD strategy, draw call budgets
- `.planning/research/MAP_BUILDING_TECHNIQUES.md` -- Terrain splatmaps, spline carving, level streaming, cliff face approaches
- `.planning/research/CHARACTER_MESH_QUALITY_TECHNIQUES.md` -- Primitive assembly vs continuous field, Skin Modifier approach
- `.planning/research/TEXTURING_ENVIRONMENTS_RESEARCH.md` -- Splatmap blending, anti-tiling, weathering systems
- `.planning/research/AI_MESH_GENERATION_TECHNIQUES.md` -- SDF-based mesh extraction, topology quality from AI vs procedural

### Memory Files (MEDIUM confidence -- point-in-time observations, verified against project state)
- `project_visual_quality_crisis.md` -- "Generated 3D is primitive boxes with flat colors"
- `project_v5_gap_analysis.md` -- 192 gaps: 63 equipment, 83 world, 46 visual
- `project_template_quality_audit.md` -- 293 generators at 72% AAA readiness

### Industry References (HIGH confidence -- cross-referenced)
- Polycount Wiki -- Triangle budgets, LOD strategy, modular kit design
- Google Filament PBR documentation -- Roughness variation importance
- DOOM 2016 Graphics Study (Adrian Courreges) -- Scene budget management
- GDC 2011 Fast SSS approximation -- Character rendering quality
- Bethesda/FromSoftware modular design -- Kit-based construction at 25-40 pieces per kit
- Unreal Engine Landscape system -- Spline terrain carving, height-blend splatmaps
- Unity URP documentation -- SRP Batcher, LOD Groups, GPU instancing

---
*Pitfalls research for: AAA Procedural 3D Architecture (Blender + Unity pipeline)*
*Researched: 2026-03-30*
*Confidence: HIGH -- critical pitfalls verified against existing project research, gap analysis, and AAA benchmarks*
