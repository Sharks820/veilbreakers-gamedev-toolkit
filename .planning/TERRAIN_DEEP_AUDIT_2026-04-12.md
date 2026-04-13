# Terrain Deep Audit Report — 2026-04-12

**Methodology**: 8 parallel Opus agents — 4 codebase scanners + 4 AAA industry researchers
**Scope**: All terrain_*.py, handlers/, tests/, contracts, quality infrastructure + World Machine/Gaea/Houdini/UE5/6 AAA game pipelines

---

## EXECUTIVE SUMMARY

The terrain system has **excellent analytical infrastructure** (40+ mask-stack channels, ecotone graphs, waterfall hydrology, stratigraphic erosion, 4-layer vegetation) but suffers from a fundamental **analysis-to-geometry gap**: the pipeline detects and classifies terrain features extensively but rarely converts those analyses into actual 3D mesh geometry in Blender.

**By the numbers:**
- 4 CRITICAL code bugs (runtime errors, dead validation, non-functional wind erosion)
- 8 HIGH code bugs (flat water, river [0,1] clip, BFS perf, stub cliff meshes)
- 16 MEDIUM code bugs (unit mismatches, hardcoded thresholds, missing UVs, thread safety)
- 9 LOW code bugs (performance, cosmetic, documentation)
- 3 CRITICAL architectural gaps vs AAA (no particle erosion, no cliff geometry, no water mesh)
- 9 major contract/spec gaps (no river spec, no volumetric water req, no performance budgets)
- 13 CODEX barrier test classes never implemented
- 7 handler files with zero test coverage

---

## SECTION 1: CRITICAL CODE BUGS (Fix Immediately)

### BUG-001: `list_layers` variable shadowing — NameError at runtime
- **File**: `blender_addon/handlers/terrain_advanced.py:779-781`
- **Bug**: List comprehension iterates with `for L in layers` but body references `layer` (from prior code path). Will raise `NameError` if `list_layers` is called without prior `modify_layer` in same invocation, or silently return duplicate data for the last layer.
- **Fix**: Change `for L in layers` to `for layer in layers`

### BUG-002: `check_focal_composition` compares radians against 30.0 — always false
- **File**: `blender_addon/handlers/terrain_validation.py:701`
- **Bug**: `slope_arr > 30.0` but slope channel is in radians (0 to pi/2 ~= 1.57). The check `> 30.0` is NEVER true. Validation always reports "only 0.0% of terrain is steep" regardless of actual terrain.
- **Fix**: `np.degrees(slope_arr) > 30.0` or compare against `math.radians(30.0)` (~0.524)

### BUG-003: Wind erosion `np.roll` causes edge wrap-around contamination
- **File**: `blender_addon/handlers/terrain_wind_erosion.py:56-57`
- **Bug**: `np.roll` wraps array edges — left edge receives right edge heights and vice versa. Creates visible seam artifacts: sudden cliffs/valleys at tile boundaries from opposite edge elevations.
- **Fix**: Use `np.pad(mode="edge")` + manual slicing instead of `np.roll`, or zero out delta at edge cells

### BUG-004: `pass_wind_erosion` computes delta but never applies to height
- **File**: `blender_addon/handlers/terrain_wind_erosion.py:141-194`
- **Bug**: Computes `total_delta`, stores as `"wind_erosion_delta"` channel, but never modifies `stack.height`. Docstring says "Produces: height (mutated)" but height is untouched. Wind erosion has ZERO effect on terrain geometry.
- **Fix**: Add `stack.set("height", np.asarray(stack.height, dtype=np.float64) + total_delta, "wind_erosion")` before return

---

## SECTION 2: HIGH CODE BUGS

### BUG-005: Water bodies are flat single-sided planes — not volumetric
- **File**: `blender_addon/handlers/environment.py:2919`
- **Severity**: HIGH
- **Bug**: `handle_create_water()` generates a surface mesh where all ring vertices share the same Z. No bottom geometry, no Volume Absorption/Scatter shader nodes. The waterfall system mandates volumetric prisms but general water bodies don't implement it.
- **Fix**: Add bottom face layer offset by depth parameter. Add Volume Absorption node to water material. Implement varying depth across cross-section (deeper center, shallower banks).

### BUG-006: River carving clips world-space heights to [0,1]
- **File**: `blender_addon/handlers/_terrain_noise.py:839`
- **Severity**: HIGH
- **Bug**: `np.clip(result, 0.0, 1.0)` after carving. World-space heights (0-500m) get normalized/denormalized in a round-trip that introduces quantization error. Rivers cannot carve below the heightmap floor.
- **Fix**: Operate in world-space units directly. Remove [0,1] clip. Use actual min/max heights for depth scaling.

### BUG-007: `insert_hero_cliff_meshes` is a stub — records intent only
- **File**: `blender_addon/handlers/terrain_cliffs.py:454-475`
- **Severity**: HIGH
- **Bug**: "Real bmesh geometry generation ships in a later Bundle B extension." Only appends strings to `state.side_effects`. No actual cliff geometry is ever created despite extensive cliff analysis (lip polyline, face mask, ledges, talus).
- **Fix**: Wire `carve_cliff_system()` output to `generate_cliff_face_mesh()` from `_terrain_depth.py` to produce actual cliff overlay meshes.

### BUG-008: `_label_connected_components` BFS has unchecked appends
- **File**: `blender_addon/handlers/terrain_cliffs.py:147-180`
- **Severity**: HIGH
- **Bug**: BFS appends all 8 neighbors unconditionally — bounds/visited checks happen after pop, not before append. On 512x512 mostly-True mask, stack grows to millions of entries. Massive memory usage and slow performance.
- **Fix**: Check bounds and visited BEFORE appending to `stack_bfs`

### BUG-009: Erosion mass conservation check allows "both zero" as soft
- **File**: `blender_addon/handlers/terrain_validation.py:348-390`
- **Severity**: HIGH
- **Bug**: Reports "erosion + deposition are both ~0" as soft, silently allowing the erosion pass to be a complete no-op with no warning.
- **Fix**: Should be "hard" when erosion pass claims to have run

### BUG-010: `_erode_brush` may produce negative `erosion_amount` from float precision
- **File**: `blender_addon/handlers/_terrain_erosion.py:274-280`
- **Severity**: HIGH
- **Bug**: Double-negation pattern with brush edge weights can produce fractional negative values. Docstring claims values are ">= 0".
- **Fix**: Add `erosion_amount = np.maximum(erosion_amount, 0.0)` before returning

### BUG-011: Chunking overlap creates asymmetric border widths at chunk (0,0)
- **File**: `blender_addon/handlers/terrain_chunking.py:197-206`
- **Severity**: HIGH
- **Bug**: `r_start = gy * chunk_size - overlap` goes negative for gy=0, clamped to 0. First row/column chunks get fewer overlap samples on north/west edges, creating asymmetric geometry at LOD transitions.
- **Fix**: Pad source heightmap with `overlap` samples on all sides before chunking

### BUG-012: Waterfall hydrology chain has no mesh builder
- **File**: `blender_addon/handlers/terrain_waterfalls.py:1-200`
- **Severity**: HIGH
- **Bug**: Excellent hydrologic analysis (lip detection, plunge path, impact pool, WaterfallChain dataclass) but no function builds the 7 WaterfallFunctionalObjects as actual geometry. `terrain_waterfalls_volumetric.py` validates profiles but doesn't build meshes.
- **Fix**: Implement `build_waterfall_chain_geometry()` that takes WaterfallChain + WaterfallVolumetricProfile and generates thick tapered prism with rounded front face.

---

## SECTION 3: MEDIUM CODE BUGS

### BUG-013: `compute_slope_map` vs `compute_slope` return different units
- **Files**: `_terrain_noise.py:598` (degrees), `terrain_masks.py:27` (radians)
- Both used throughout codebase. Scatter engine expects degrees, TerrainMaskStack stores radians, validation inconsistently treats as both.
- **Fix**: Standardize on one unit or rename to `compute_slope_rad`/`compute_slope_deg`

### BUG-014: Biome rules use hardcoded [0,1] altitude thresholds
- **File**: `_terrain_noise.py:262-354`
- BIOME_RULES use `min_alt: 0.7` etc. but pipeline uses world-unit heights (meters) via `normalize=False`. Assignment fails on non-normalized heightmaps.
- **Fix**: Normalize heights internally in `compute_biome_assignments()` or accept world-unit thresholds

### BUG-015: Canyon/waterfall/cliff generators produce mesh with no UVs or normals
- **File**: `blender_addon/handlers/terrain_features.py` (throughout)
- Returns only vertices+faces+material_indices. No UV coordinates, no vertex normals, no vertex colors.
- **Fix**: Add basic triplanar UV generation to each feature generator

### BUG-016: Two `validate_tile_seams` functions with different signatures
- **Files**: `_terrain_world.py:173` (dict of tiles), `terrain_chunking.py:355` (two tiles + direction)
- Import confusion likely. Different return structures.
- **Fix**: Rename one to `validate_tile_pair_seam`

### BUG-017: Two `apply_thermal_erosion` with incompatible parameter semantics
- **Files**: `terrain_advanced.py:1120` (raw height diff, default 0.5), `_terrain_erosion.py` (angle in degrees, default 40.0)
- Same name, completely different semantics for `talus_angle`.
- **Fix**: Rename or deprecate legacy version

### BUG-018: `compute_erosion_brush` terrain_origin is center, not min corner
- **File**: `blender_addon/handlers/terrain_advanced.py:836-839`
- Brush position offset missing the `- tw * 0.5` that `apply_layer_operation` correctly applies.
- **Fix**: Apply same `min_x = ox - tw * 0.5` offset

### BUG-019: Scatter engine ignores explicit biome assignment map
- **File**: `blender_addon/handlers/_scatter_engine.py:131-264`
- Filters by altitude/slope ranges per rule but doesn't consume `compute_biome_assignments()` output. Biomes with overlapping ranges bleed into each other.
- **Fix**: Add `biome_map` parameter that filters by per-cell biome index

### BUG-020: `_features_gen` global cache not thread-safe
- **File**: `blender_addon/handlers/terrain_features.py:33-46`
- Module-level globals shared without locking. Concurrent calls silently replace generator.
- **Fix**: Use thread-local or pass generator as parameter

### BUG-021: `_OpenSimplexWrapper` imports but never uses opensimplex
- **File**: `_terrain_noise.py:164-183`
- Imports opensimplex but evaluation is from `_PermTableNoise`. Library installed but makes zero difference.
- **Fix**: Either use opensimplex for evaluation or remove dependency

### BUG-022: `generate_dunes` hardcoded wavelength/amplitude
- **File**: `terrain_wind_erosion.py:104,131`
- `wavelength=10.0`, `amplitude=2.0` regardless of terrain scale. Wrong for different cell sizes.
- **Fix**: Scale relative to `stack.cell_size`

### BUG-023: `carve_u_valley` O(N*M) brute-force distance
- **File**: `terrain_glacial.py:95-111`
- Computes distance to ALL dense path points per cell. ~50M operations for 512x512.
- **Fix**: Use KD-tree or rasterize path into distance field

### BUG-024: `detect_lakes` iterates all cells in pure Python
- **File**: `_water_network.py:200`
- ~1M iterations in pure Python for 1024x1024. Takes 10-30 seconds.
- **Fix**: Vectorize with `scipy.ndimage.minimum_filter`

### BUG-025: Basin detection pure-Python BFS (terrain_masks.py)
- **File**: `terrain_masks.py:145-237`
- 262K cells with 8-neighbor BFS in Python. Bottleneck for large terrains.
- **Fix**: Use `scipy.ndimage.label` or vectorized union-find

---

## SECTION 4: CRITICAL WIRING DISCONNECTS

These are features where the analysis code exists and works, but the pass/pipeline never calls it:

| ID | Pass | What's Disconnected | Impact |
|----|------|---------------------|--------|
| P0-004 | `pass_waterfalls` | `carve_impact_pool` and `build_outflow_channel` return deltas but pass never applies to `stack.height` | Waterfall pools/outflows don't affect terrain |
| P0-008 | `pass_caves` | `carve_cave_volume` returns delta but pass discards it | Cave carving has no effect |
| P0-009 | `pass_scatter_intelligent` | `environment_scatter.py` is a separate unreferenced code path | Two scatter systems, pipeline uses neither fully |
| P0-021 | `pass_water_variants` | Ignores ALL 8 variant detectors (braided, estuary, karst springs, perched lakes, hot springs, wetlands, seasonal, tidal) | Only does generic inverse-depth wetness |
| P0-022 | `pass_vegetation_depth` | Calls only `compute_vegetation_layers` (1 of 7 helpers) | Disturbance patches, clearings, fallen logs, edge effects, cultivated zones, allelopathic exclusion all dead code |
| N/A | `compose_map` | Bypasses entire Bundles A-O pass pipeline | Quality infrastructure (validation, contracts, lint) unused for main entry point |
| N/A | `compose_terrain_node` | Documented but ZERO implementation | Cannot compose terrain nodes |

---

## SECTION 5: CRITICAL ARCHITECTURAL GAPS VS AAA

### GAP-1: No Particle-Based Hydraulic Erosion (CRITICAL)
**Current**: Analytical erosion filter evaluates each point in isolation. No water droplets, no sediment transport loops, no flow accumulation feedback.
**AAA Standard**: World Machine/Gaea/Houdini all use particle-based or grid-based shallow water simulation. 200K droplets for visible erosion in 10-20 seconds. Outputs wear/deposit/flow maps that drive ALL downstream systems (cliff placement, material assignment, vegetation).
**Algorithm**: Per particle: compute surface normal -> accelerate -> move -> compute equilibrium sediment capacity from slope*speed*volume -> deposit or erode -> evaporate. ~20 lines of core math.
**References**: github.com/weigert/SimpleHydrology, nickmcd.me/2020/04/10/simple-particle-based-hydraulic-erosion/

### GAP-2: No 3D Cliff/Overhang Geometry (CRITICAL)
**Current**: Heightfield-only. Cliff analysis (lip polyline, face mask, ledges, talus) is excellent but outputs masks only. `insert_hero_cliff_meshes` is a stub.
**AAA Standard**: Far Cry 5 GPU cliff mesh pipeline, UE5 Landscape Mesh Extraction, marching cubes for caves/overhangs (GPU Gems 3).
**Recommended Architecture**: Hybrid heightmap + sparse SDF volumes. Heightmap everywhere, allocate 32x32x32 SDF chunks only where slope > 60 degrees. Compose SDF from heightmap + warped noise overhangs + cave subtraction. Marching cubes on active chunks only. Transvoxel for LOD seam stitching.
**References**: developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-1, transvoxel.org

### GAP-3: No Water Surface Mesh Generation (CRITICAL)
**Current**: Masks only (foam, mist, wet_rock, water_surface as 2D height layer). Never creates actual water geometry in Blender.
**AAA Standard**: All AAA games generate water surface+volume meshes. Rivers get spline-following geometry with cross-section profiles. Lakes get flood-filled surface planes with bathymetry underneath. Waterfalls get volumetric sheet geometry.
**What Exists Already**: `handle_create_water()` in environment.py DOES create water mesh but it's flat single-sided. WaterfallFunctionalObjects defines 7 geometry types but none are built.

### GAP-4: No Height-Based Texture Blending (HIGH)
**Current**: Linear weight blending in splatmap. Sand and rock blend 50/50 in transition zones producing muddy results.
**AAA Standard**: Per-texture height maps. Sand height texture is low, rock height texture is high. Blending uses `max(height_A * weight_A, height_B * weight_B)` so sand naturally fills cracks between stones. Sharp, natural-looking transitions.

### GAP-5: River Paths Lack Natural Curvature (HIGH)
**Current**: D8 flow traces produce grid-aligned stair-step paths. `carve_river_path` displaces heightmap vertices downward — no topology cutting, no bank geometry, no cross-section profile.
**AAA Standard**: Centripetal Catmull-Rom splines through subsampled path points. U-shape/V-shape cross-section profiles via vertex displacement. Bank slopes vary (steeper outer bank in meanders). Width scales with sqrt(flow_accumulation).
**References**: Horizon Zero Dawn river tool (80.lv article), Paris et al. 2023 SIGGRAPH Asia meandering rivers (github.com/aparis69/Meandering-rivers)

### GAP-6: No Displacement Map Generation (HIGH)
**Current**: No micro-detail displacement for cliff faces or terrain surfaces.
**AAA Standard**: RDR2 Parallax Occlusion Mapping, UE5 Nanite displacement, rock face detail via Worley noise striations + scrape deformation.

---

## SECTION 6: TEST COVERAGE GAPS

### Feature Coverage Matrix

| Feature | Rating | Key Gap |
|---------|--------|---------|
| Cliff generation | COVERED | No bmesh geometry verification (mask-only tests) |
| Water bodies | PARTIAL | P0-021: pass ignores all 8 variant detectors |
| River cutout carving | PARTIAL | 2D heightmap only. No mesh cutout, no bank geometry |
| Seamless tiling (height) | COVERED | Exact edge matching at atol=1e-12. Strongest area. |
| Cross-tile water/material | MISSING | Height continuity verified. Water/material/biome channels NOT tested |
| Erosion (hydraulic/thermal/wind) | COVERED | 50K droplet stress test, real quality tests |
| Scatter/vegetation | COVERED | But P0-022: pass uses 1/7 helpers |
| Heightmap import | MISSING | DEM import broken (P0-014: only .npy). Tests only cover synthetic fallback |
| Heightmap export | COVERED | uint16 quantization with metadata |
| Terrain LOD | PARTIAL | Heightmap downsampling only. No mesh LOD, no LOD stitching |
| Splatmap blending | COVERED | Weight normalization, slope/altitude triggers, 5-channel |
| Biome transitions | COVERED | But no cross-tile transition tests |

### Missing Test Infrastructure
- **Zero 3D mesh geometry verification** anywhere in entire test suite (all tests operate on 2D numpy arrays)
- **All 13 CODEX barrier test classes never implemented** (no-stub-pass, delta-applied, frozen-dataclass-hashable, validator-no-self-rollback, registrar-completeness, mcp-tool-roundtrip, validation-full-runs, manifest-schema-roundtrip, axis-convention-on-export, advertised-detector-wired, honesty-roundtrip, generator-not-stub, builder-bsdf-wired)
- **Integration test uses strict=False** — only exercises Bundles A+D. Bundles B, C, E-O untested.
- **7 handler files have zero tests**: terrain_framing.py, terrain_morphology.py, terrain_hierarchy.py, terrain_rhythm.py, terrain_negative_space.py, terrain_sculpt.py, terrain_protocol.py

---

## SECTION 7: CONTRACT AND QUALITY INFRASTRUCTURE GAPS

### terrain.yaml Contract Missing:
1. No cliff geometry specification (angle thresholds, poly budget, material requirements)
2. No water body volumetric requirement
3. No river pass or river curvature specification AT ALL
4. No mesh export format specification (FBX/glTF)
5. No performance budgets (poly count, draw calls, frame time)
6. No splatmap export format specification
7. No LOD chain specification
8. No UV generation requirements
9. Cliff pass only produces mask — no geometry spec, no plan to close gap

### quality_lint.py Missing:
1. No L2-07 REGISTRAR-INCOMPLETE (replaced by HEIGHT-WRITER)
2. No L2-08 WRONG-ARITY-CALL (never implemented)
3. No hardcoded magic number detection
4. No coordinate system error detection (Z-up vs Y-up)
5. No missing UV generation detection
6. Multi-statement stubs not caught

### honesty_lint.py Missing:
1. Cannot parse YAML status fields — only markdown checkboxes
2. No channel contract verification (produces vs actual writes)
3. No is_stub field cross-check
4. No known_bugs verification

### brief_agent.py Missing:
1. `orphan_deltas` always returns empty list
2. Dead code exporters not surfaced
3. Unwired library warnings (899 LOC real code) not surfaced
4. Cross-cutting bugs not extracted
5. Custom YAML parser fragile for complex structures

---

## SECTION 8: AAA INDUSTRY TECHNIQUES TO ADOPT

### Tier 1 — Transformative (would fundamentally improve quality)

| Technique | Source | Implementation Effort |
|-----------|--------|----------------------|
| Particle-based hydraulic erosion | SimpleHydrology, SoilMachine | MEDIUM — ~200 LOC core, need numpy vectorization |
| Hybrid heightmap + sparse SDF for cliffs | GPU Gems 3, Transvoxel | HIGH — new data structure, marching cubes mesher |
| Catmull-Rom river spline smoothing | Procedural Riverscapes (HAL 2019) | LOW — fit spline to existing D8 path points |
| Cross-section river carving (U/V profiles) | Industry standard | LOW — vertex displacement with profile function |
| Height-based texture blending | UE5/Unity standard | LOW — add per-texture height channel to splatmap |
| Volumetric water geometry | All AAA games | MEDIUM — extend handle_create_water with bottom faces + Volume Absorption |

### Tier 2 — Significant Quality Improvement

| Technique | Source | Implementation Effort |
|-----------|--------|----------------------|
| Wear/deposit/flow masks from erosion | Gaea, World Machine | LOW — output as channels during particle erosion |
| Meandering rivers via momentum | Nick McDonald 2023 | MEDIUM — extend particle erosion with momentum maps |
| Poisson disk scatter with hierarchy | Houdini HeightField Scatter | MEDIUM — replace grid-based scatter |
| Priority-Flood depression filling | Barnes 2014 (richdem) | LOW — prerequisite for proper D8 flow |
| Strahler stream ordering | Hydrology standard | LOW — label river hierarchy from confluence graph |
| Hjulstrom curve river bed material | Geomorphology standard | LOW — flow velocity -> material assignment |

### Tier 3 — Polish and Completeness

| Technique | Source | Implementation Effort |
|-----------|--------|----------------------|
| Displacement maps for rock detail | RDR2, UE5 Nanite | MEDIUM |
| Wang tiles for scatter variation | Academic | MEDIUM |
| Geomorphing between LOD levels | Witcher 3 clipmaps | HIGH |
| Columnar basalt generation | Voronoi + extrusion | MEDIUM |
| Sea cliff wave-cut notch | NEWTS1.0 model | MEDIUM |
| Natural arch/bridge SDF | Inigo Quilez SDF ops | MEDIUM |

---

## SECTION 9: PRIORITIZED ACTION PLAN

### Phase A — Critical Bug Fixes (1-2 days)
1. Fix BUG-001 through BUG-004 (4 CRITICAL bugs)
2. Fix BUG-005 through BUG-012 (8 HIGH bugs)
3. Wire P0-004 (waterfall deltas), P0-008 (cave deltas), P0-021 (water variants), P0-022 (vegetation depth)

### Phase B — Foundation Architecture (3-5 days)
1. Implement particle-based hydraulic erosion (GAP-1) — ~200 LOC core
2. Apply wind erosion delta to height (BUG-004 fix enables this)
3. Add Catmull-Rom spline smoothing to river paths (GAP-5)
4. Add U/V cross-section profiles for river carving
5. Make water bodies volumetric (GAP-3) — bottom faces + Volume Absorption shader
6. Build waterfall chain geometry from WaterfallFunctionalObjects spec

### Phase C — Cliff Geometry System (5-7 days)
1. Design sparse SDF volume data structure for cliff regions
2. Implement SDF composition: heightmap + warped noise overhangs
3. Implement marching cubes mesh extraction
4. Wire cliff analysis output to SDF volume allocation
5. Add Transvoxel LOD transition cells
6. Generate rock face detail (scrape deformation + Worley striations)

### Phase D — Quality Infrastructure Completion (2-3 days)
1. Implement 13 barrier test classes from CODEX spec
2. Switch integration test to strict=True
3. Add integration tests for Bundles B, C, E-O
4. Add 3D mesh geometry verification tests
5. Add cross-tile water/material continuity tests
6. Update contract YAML with missing specs (rivers, volumetric water, performance budgets)

### Phase E — Polish and AAA Quality Push (3-5 days)
1. Height-based texture blending (GAP-4)
2. Wear/deposit/flow masks from erosion output
3. Priority-Flood depression filling for proper D8 flow
4. Hjulstrom curve river bed material assignment
5. Meandering rivers via momentum (if time permits)
6. Displacement map generation for cliff faces

---

## APPENDIX A: KEY REFERENCES

### Papers
- Barnes et al. 2014 — Priority-Flood depression filling, O(n)
- Genevaux et al. 2013 — Terrain from Hydrology (SIGGRAPH 2013)
- Paris et al. 2023 — Meandering Rivers (SIGGRAPH Asia 2023)
- Cordonnier et al. 2023 — Glacial Erosion (SIGGRAPH 2023)
- Emilien et al. 2015 — Interactive Waterfall Scenes (CGF)
- GPU Gems 3 Ch.1 — SDF terrain with caves/overhangs
- Transvoxel — LOD-seam-free marching cubes

### Open Source
- github.com/weigert/SimpleHydrology — Particle hydrology (rivers+lakes+waterfalls)
- github.com/weigert/SoilMachine — Multi-layer 3D erosion
- github.com/r-barnes/richdem — High-performance terrain hydrology
- github.com/aparis69/Meandering-rivers — SIGGRAPH Asia 2023
- github.com/dandrino/terrain-erosion-3-ways — Three erosion approaches
- github.com/Erkaman/gl-rock — Procedural rock mesh
- gitlab.inria.fr/landscapes/glacial-erosion — SIGGRAPH 2023

### GDC/SIGGRAPH Talks
- Far Cry 5 procedural terrain pipeline (Houdini Engine, overnight rebuilds)
- Horizon Zero Dawn river tool + world data maps
- Ghost of Tsushima grass/scatter system (GPU compute, per-blade Bezier)
- Witcher 3 terrain clipmaps (5 levels, tessellation factor 8-16)
- RDR2 terrain LOD + Parallax Occlusion Mapping

### Blog Posts
- nickmcd.me — Particle erosion, wind erosion, meandering rivers, SoilMachine
- iquilezles.org/articles/distfunctions — SDF primitive library
- redblobgames.com/x/1723-procedural-river-growing — Drainage basin generation

### Tiling, LOD, Scatter
- Losasso & Hoppe (SIGGRAPH 2004) — Geometry Clipmaps
- Strugar (2010) — CDLOD: Continuous Distance-Dependent LOD (github.com/fstrugar/CDLOD)
- Bridson (SIGGRAPH 2007) — Fast Poisson Disk Sampling O(n)
- AutoBiomes (CGI 2020, University of Bremen) — Multi-biome with climate sim
- Wangscape — Wang tile terrain (github.com/Wangscape/Wangscape)

---

## APPENDIX B: CURRENT STRENGTHS (Do Not Regress)

These systems are well-implemented and should be preserved:
- **Seamless tiling**: Edge vertex matching at atol=1e-12, post-erosion seam validation
- **PBR materials**: Full Principled BSDF with proper linear-space colors, 80+ materials
- **Stratigraphic erosion**: Layered rock with differential erosion (rare in commercial tools)
- **Karst hydrology**: Sinkholes, cenotes, poljes (more features than most pro tools)
- **4-layer vegetation**: Canopy/understory/shrub/ground_cover with allelopathic exclusion
- **Ecotone graph**: Per-biome-pair transition curves (smoothstep/sigmoid/linear)
- **Water variant detectors**: 8 specialized detectors (just need to wire them into the pass)
- **TerrainMaskStack**: 40+ channels with provenance tracking and intent hashing
- **Deterministic pipeline**: Seeded with full checkpoint/rollback capability
- **Unity export**: Comprehensive (heightmap, splatmap, normals, navmesh, auxiliary channels)
