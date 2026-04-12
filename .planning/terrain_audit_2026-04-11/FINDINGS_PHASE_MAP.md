# Complete Findings → Phase Mapping

**Every finding must have a phase. No exceptions.**

## RETRACTED (no action needed — document only)
F003, F077, F134, F135, F138, F527

## Phase 49 (Foundation): Test infrastructure + contract + baseline
F130-F133, F400-F447 (contract YAML drift), F450-F480, F482 (bug-ratifying tests + MagicMock),
F560-F592 (git history/informational), F461, F840-F844, F842, F845
CONFLICT-006, CONFLICT-010, CONFLICT-016, CONFLICT-018

## Phase 50 (Analytical Erosion): Filter + noise + gradient
F277-F300 (terrain math: erosion, stamps, bridges, structural masks, seeds, fallbacks),
F801-F805, F860-F864, F805 (opensimplex mismatch), F863 (dead duplicate erosion)
CONFLICT-003, CONFLICT-008

## Phase 51 (Dead Delta Integration): Integrator + orphan channels
F001, F002, F004-F006, F008-F018 (channel clobber including F008 roughness_variation 4 writers, F009 wetness 3 writers), F082-F087 (stack.set bypass),
F820-F825, F822

## Phase 52 (Bundle I Delta Conversion): Height-overwriter → delta
F007, F862, plus the specific pass files:
F650-F660 (grid dim fallback, checkpoint drift, RNG protocol, flatten resize),
F-karst multi-writer, F-glacial multi-writer, F-framing new height writer
CONFLICT-002 (height-overwriter → delta migration plan)

## Phase 53 (BakedTerrain + Path Unification): All 5 paths → 1
F105-F112 (integration divergent paths), F145, F204-F213 (cowork bridge),
F139-F153 (Round 3 legacy path bugs: erosion escalation, flatten_zones ordering,
double-erosion, erosion_margin offset, bool("false")=True inversion, biome seed drop,
cliff overlay trigger, moisture-only-if-erosion, handle_run_terrain_pass no cleanup,
register strict=False discarded, shared_height_range estimation — most eliminated by
BakedTerrain unification, F150 no-cleanup and F152 bool-inversion are independent fixes),
F823, F823 compose_map bypass
CONFLICT-004

## Phase 54 (Seam System + Node Merging)
F164-F169 (stitch bugs), F800, F806-F818
CONFLICT-005 (smoothstep vs Poisson — adopt smoothstep now)

## Phase 55 (Scatter + Rivers + Water)
F064-F067 (Tripo/scatter), F154-F163 (hero builder bugs: cliff params, waterfall, cave entrance),
F241-F269 (non-terrain handler bugs affecting scatter: biome density, slope thresholds, grid corruption,
building footprint, scatter wrong arg, raycasts, building/alleys no heightmap, terrain alignment),
F830-F838, F854
CONFLICT-007 (path network A* prerequisite for stairs-as-intersection)
NEW-R8-01 (P0) terrain_water_variants.py:734 — get_swamp_specs crashes: Wetland has no radius_m
NEW-R8-02 (P0) terrain_water_variants.py:740 — get_swamp_specs crashes: Wetland has no world_pos
NEW-R8-03 (P0) terrain_water_variants.py:693 — detect_hot_springs wrong arity, always returns []
NEW-R8-04 (P1) terrain_water_variants.py:579-661 — 6 water detectors dead, never called from pass
NEW-R8-05 (P1) terrain_bundle_o.py:1-34 — water feature spec generators unscheduled in pipeline
NEW-R8-06 (P2) road_network.py:1-700 — road mesh_specs computed but never sent to Blender handler
NEW-R8-07 (P1) environment.py:333-415 — Tripo asset manifest orphaned, never auto-consumed
NEW-R8-08 (P2) terrain_morphology.py:63-100 — no saddle/col/pass template in 30-template catalog
NEW-R8-09 (P2) _terrain_noise.py:715-787 — A* pathfinding unwired from pass detection
NEW-R8-10 (P1) _terrain_noise.py:764 — A* uses abs(height_diff): uphill=downhill cost. Rivers route UPHILL. Root cause of "straight line horrible cuts"
NEW-R8-11 (P1) terrain_features.py:157-198 — Canyon walls widen toward top (inverted trapezoid). Real canyons have vertical/inward walls
NEW-R8-12 (P1) environment.py:1056-1067 — moisture_map computed via distance transform then silently discarded every call
NEW-R8-13 (P0) terrain_features.py:254-490 — generate_waterfall has NO water curtain mesh. "Waterfall" is cliff rock with no falling water
NEW-R8-14 (P1) environment.py:2386 — flow_dir_z vertex color encodes horizontal tangent, not vertical. Shader reads wrong data
NEW-R8-15 (P1) terrain_waterfalls.py:681 — RNG constructed from derived seed then immediately discarded (assigned to _)
NEW-R8-16 (P1) terrain_waterfalls.py:166 — D8 angle north-south mirrored. Waterfall lips/pools placed on wrong side of slopes
NEW-R8-17 (P2) terrain_morphology.py:149-203 — All 30 templates are smooth Gaussians, no vertical walls/scarps/discontinuities. Canyons are rounded slots
NEW-R8-18 (P2) terrain_cliffs.py:pass_cliffs — cliff_candidate mask written but no downstream consumer creates geometry
CODEX-R14-01 (P1) terrain_cliffs.py:212-217,582-587 — region scoping clips components at boundaries instead of filtering whole components by center. Same cliff gets split into multiple smaller cliffs across region runs
CODEX-R14-02 (P1) terrain_cliffs.py:494-519,621-623 — hard validation failures mapped to status="warning" not "failed". Structurally broken cliffs continue through pipeline as non-fatal warnings
CODEX-R14-03 (P1) terrain_cliffs.py:282-313 — _extract_lip_polyline returns scanline order (row,col sort) not contour order. Downstream extrusion/alignment produces zig-zagged cliff rims
CODEX-R14-04 (P2) terrain_cliffs.py:399-445 — talus angle_of_repose_deg stored in dataclass but never influences the mask. apron_cells forced through max(1,...) so 0 still produces apron. Talus cannot be physically tuned or disabled

## Phase 56 (Material Pipeline + Shaders)
F034-F049 (materials: no textures, splatmap ordering, hardcoded color, triplanar dead, no UV,
no displacement, no wetness, PBR builder dead),
F270-F276 (material split-brain: legacy vs V2, splatmap mismatch),
F600-F621 (materials deep: PBR dead, snow unreachable, dark-brown fallback, no displacement,
metallic pinned, node_recipe dead),
F826-F828
CONFLICT-011 (PBR texture generation prerequisite for triplanar)
Rendering gaps (RGAP prefix to disambiguate from Unity gaps):
RGAP-001 triplanar, RGAP-002 macro-variation, RGAP-003 detail normals,
RGAP-004 POM/tessellation, RGAP-005 height-blend preview, RGAP-006 wetness/puddle,
RGAP-007 splatmap layers (4→16), RGAP-008 stochastic tiling, RGAP-009 per-layer AO,
RGAP-010 virtual texturing, RGAP-011 terrain holes shader, RGAP-012 terrain LOD shader,
RGAP-013 atmospheric fog, RGAP-014 snow SSS, RGAP-015 GBuffer pass, RGAP-016 mip bias,
RGAP-017 terrain AO, RGAP-018 LOD stitching, RGAP-019 wind animation shader,
RGAP-020 billboard impostor shader, RGAP-021 density falloff, RGAP-022 shadow-receiving ground,
RGAP-023 vegetation interaction, RGAP-024 per-instance color, RGAP-025 seasonal vegetation,
RGAP-026 GPU instancing shader, RGAP-027 water-terrain intersection, RGAP-028 decal projection,
RGAP-029 runtime deformation, RGAP-030 per-region color grading, RGAP-031 minimap,
RGAP-032 terrain SSS, RGAP-033 cloud shadow

## Phase 57 (Unity Integration)
F050-F063 (Unity export: Z-up, endianness, resolution, FBX, LOD, seam, channels),
F188-F203 (Unity Round 3: C# endianness, asset path, alphamap, validator lies, TreePrototype,
navmesh, splatmap),
F360-F381 (Unity compound tools: 11 dead actions, schema mismatches, orchestrator theater,
terrain blend axis, streaming, quality audit, LOD),
F850-F852
CONFLICT-015 (Unity erosion package)
GAP-001 through GAP-021 (runtime gaps)

## Phase 58 (Cleanup — Silent Swallows + Stubs + Non-terrain)
F019-F030 (silent exception swallowing),
F031-F033 (workflow presets),
F068-F079 (stubs: dirty tracking, 12-step, dead detectors, honesty_lint),
F080-F081 (Bundle H phantom),
F088-F089 (dead side-effect passes: god_ray, stochastic),
F090-F097 (addon lifecycle: hot reload, register, Bundle N, checkpoints, runtime),
F098-F104 (TCP/protocol: numpy encoder, traceback, outbound cap, timer, created_objects, ProtocolGate),
F170-F187 (frozen-mutable + state bugs),
F214-F224 (dead code/wiring: enforce_budget, differential_erosion, performance_report,
roughness_driver, multiscale_breakup, test_caves stub),
F225-F240 (MCP layer bugs: hero failures counted as success, fire-and-forget, protected_zones dropped,
compose_map error semantics, seam validation traffic),
F320-F331 (blender_server: generate_prop, map_package, aaa_verify, performance_check stub,
LOD chain fake, compose_interior resume, checkpoint/rollback nonfunctional),
F520-F549 minus F527 (non-terrain generators: sandbox, geometry_nodes, modifier_apply,
building grammar blanket except = F540 "buildings are boxes", road/dungeon/settlement terrain-blindness,
datablock leaks),
F661-F767 (remaining terrain files: natural arch, geyser, sinkhole, floating rocks, ice formation,
lava flow kink, checkpoint id reuse, chunking drops rows, DAG merge bypass, pipeline overwrites,
double-defined breakup, roughness driver nonexistent channels, wind field seed, cliff hero placeholder),
F845, F853-F857, F864
R7 findings: terrain_features global mutable, terrain_banded_advanced dead module,
stratigraphy differential_erosion dead, compose_map LOD dispatch P0, compose_interior checkpoint,
settlement radius, fallback radial search, fog toroidal wrapping, quality_lint edge cases

## Phase 59 (Verification)
CONFLICT-009 (update retracted citation), CONFLICT-016 (consolidate ~30-40 duplicates)
All 84 AAA gaps verified
All findings marked resolved or deferred with justification
F136-F137 (git history informational)

## NOTHING DEFERRED — All items are active.

### Previously-deferred AAA features → now assigned to phases:

**Phase 55 (Scatter + Rivers + Water) — absorbs water/river/lake features:**
- F113: pipe-model erosion for hero-node refinement (Mei/Decaudin)
- F114: river 3D geometry (spline mesh + flowmap bake, Arnklit Waterways pattern)
- F118: priority-flood lake detection + lake surface mesh
- F122: meander/oxbow river system (sinuosity, cutbank/point bar)
- F125: natural arch geometry at cliff-river intersections
- GAP-003 (river geometry), GAP-009 (meander), GAP-027 (lake mesh)

**Phase 54 (Seam System + Node Merging) — absorbs geological structure:**
- F115: rock_hardness wiring to differential erosion (stratigraphy→erosion coupling)
- F116: fault line displacement system (normal/reverse/strike-slip faults)
- GAP-001 (tectonic), GAP-017 (fault displacement)

**Phase 56 (Material Pipeline) — absorbs visual quality features:**
- F120: macro + detail normal blending (Reoriented Normal Mapping)
- F121: Strahler stream order → river width/depth from ridge map
- F128: seasonal/snow accumulation shader (Y-dot-normal projection + SSS)
- F129: lighting probes + occlusion for terrain
- GAP-014 (snow SSS), GAP-025 (seasonal vegetation), GAP-030 (per-region color grading)
- GAP-032 (terrain SSS), GAP-033 (cloud shadow projection)

**Phase 55 (Scatter) — absorbs vegetation + prop features:**
- F126: GPU scatter / indirect instancing
- F127: Tripo environmental prop pipeline (wire manifest → scatter)
- GAP-024 (per-instance color variation), GAP-023 (vegetation interaction)
- GAP-025 (seasonal vegetation runtime)

**Phase 53 (BakedTerrain) — absorbs geological generators:**
- F117: waterfall volumetric 3D mesh from WaterfallVolumetricProfile
- F119: curvature-weighted wetness for material assignment
- F123: debris cone / talus field geometry
- F124: natural arch standalone generator
- GAP-002 (volcanic system: caldera, columnar basalt, pyroclastic)
- GAP-008 (sediment deposition: alluvial fans, deltas, floodplains)
- GAP-010 (cirque/arete/horn alpine)
- GAP-012 (stratigraphy visible in cliff faces)
- GAP-013 (columnar basalt joints)
- GAP-016 (multi-material thermal erosion)

**Phase 57 (Unity Integration) — absorbs runtime features:**
- GAP-028 (terrain decals: roads, paths, scorch marks)
- GAP-029 (runtime terrain deformation: footprints, impacts)
- GAP-031 (terrain minimap renderer)

**Phase 58 (Cleanup) — absorbs remaining geology/rendering LOW items:**
- GAP-018 (periglacial: patterned ground, pingos, solifluction)
- GAP-019 (desert pavement / ventifacts)
- GAP-020 (spring/seep lines at stratigraphy boundaries)
- GAP-021 (landslide/mass wasting: rockfall, debris flow, creep)
- GAP-022 (hot spring mineral terraces)
- GAP-023 (reef/biogenic landforms)
- GAP-024 (spheroidal weathering / tafoni)
- GAP-026 (fold/anticline/syncline in cliff faces)

## Totals

| Category | Count |
|---|---|
| Explicitly mapped to Phase 49-58 | **~560** |
| Retracted (no action) | 6 |
| Deferred | **0** |
| **Total accounted** | **~566** |
| Cross-round duplicates (consolidated under primary ID) | ~30-40 |
| **Grand total unique findings** | **~560** |

The ~780 headline number includes: ~560 unique items + 84 AAA gaps (now integrated into phases) + 18 plan conflicts (integrated) + ~30-40 duplicates + R7 findings.
After dedup and retraction: **~560 actionable unique items, ALL mapped to phases, NOTHING deferred.**
