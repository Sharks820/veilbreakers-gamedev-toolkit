# Terrain Fix Execution Plan — All Findings

**Created:** 2026-04-12
**Orchestration:** GSD (context isolation + atomic commits) + Superpowers (TDD + systematic debugging + verification)
**Total scope:** ~780 findings + 84 AAA gaps + 18 plan conflicts + 36 research techniques + 6 Codex R16 research rounds
**Task count:** 554 tasks across 11 phases (0-10), ALL research-aligned, ALL findings mapped, quality testing infrastructure included
**Quality layers:** L0-L6 (existing) + L7 Geometry Gate + L8 Visual Regression + L9 Statistical Shape + L10 Agent Protocol

---

## Execution discipline (every phase)

```
FOR EACH PHASE:
  1. RESEARCH  — Context7 + episodic memory search for prior art/decisions
  2. PLAN      — GSD planner: task breakdown, dependencies, acceptance criteria
  3. TDD       — Superpowers: write failing tests FIRST (red), then implement (green), then refactor
  4. EXECUTE   — GSD executor: fresh context per task, atomic commits
  5. VERIFY    — GSD verifier: goal-backward check + Superpowers verification-before-completion
  6. REVIEW    — VB code reviewer (PYTHONPATH=src python src/veilbreakers_mcp/vb_code_reviewer.py <path>)
  7. SCAN      — python scripts/quality_lint.py + pytest + test_substance_lint.py
  8. COMMIT    — atomic commit with descriptive message
  9. PUSH      — git push to feature/terrain-world-foundation
  10. MEMORY   — save episodic memory of decisions + lessons learned
```

---

## Multi-Agent Parallelism Protocol

### Guardrails: File-level ownership isolation

Each parallel agent gets **exclusive file ownership** — no two agents may edit the same file.
The orchestrator assigns file sets BEFORE dispatching agents.

```
PARALLEL DISPATCH RULES:
  1. PARTITION  — Split phase tasks into non-overlapping file sets
  2. ASSIGN     — Each agent gets exactly one file set (read-many, write-only-owned)
  3. CONTEXT    — Each agent gets: its file set, the PLAN.md, CLAUDE.md, and READ-ONLY access to all other files
  4. WORKTREE   — Use isolation: "worktree" for agents that touch overlapping import chains
  5. NO CROSS-WRITE — Agent MUST NOT edit files outside its assigned set. If it needs a change in another file, it reports a DEPENDENCY and the orchestrator routes it.
  6. COMMIT     — Each agent commits ONLY its owned files
```

### Verification gate: merge + conflict check

After ALL parallel agents complete, a **verification agent** runs BEFORE any push:

```
VERIFICATION GATE:
  1. MERGE CHECK  — Are there any git merge conflicts between agent commits?
  2. IMPORT CHECK — python -c "import blender_addon.handlers" succeeds?
  3. FULL SUITE   — python -m pytest tests/ -q --timeout=300 passes?
  4. LINT CHECK   — quality_lint.py + test_substance_lint.py clean?
  5. OVERLAP SCAN — Grep all agent commits for changes to the same function/class (even in different files)
  6. REGRESSION   — Compare test count vs baseline (must be >= previous phase baseline)
  7. APPROVE/REJECT — If any check fails, identify which agent's changes caused it, reject that agent's commit, re-run
```

### Phase parallelism map

| Phase | Parallel agents | File ownership split | Sequential dependency |
|---|---|---|---|
| 49 | 2 waves (sequential) | Wave 1: conftest+fake_bpy+substance_lint. Wave 2: terrain.yaml+baseline | Wave 2 depends on Wave 1 |
| 50 | 3 parallel | A: terrain_erosion_filter.py (new). B: ErosionConfig+ridgeMap dataclass. C: unit tests + gradient fallback | All merge into pass_erosion wiring (sequential after) |
| 51 | 3 parallel | A: integrator pass (new file). B: waterfall produces_channels fix. C: cave produces_channels fix + stratigraphy wiring | Integrator must exist before B/C test it |
| 52 | 4 parallel | A: pass_coastline. B: pass_karst. C: pass_wind_erosion. D: pass_glacial | Each owns exactly one pass file. AST lint rule is sequential after |
| 53 | 2 waves | Wave 1: BakedTerrain dataclass + DAG output. Wave 2 (3 parallel): compose_terrain_node, compose_map, legacy removal | Wave 2 consumes Wave 1's contract |
| 54 | 3 parallel | A: seam_guard fix + blend_weight (blender_server.py seam section). B: TerrainNodeRegistry (new file). C: cross-tile validator + edge tests | A owns blender_server seam lines, B owns new file, C owns test files |
| 55 | **5 sub-phases in parallel** | **6A** (Scatter): 6.1-6.2, 6.5-6.7, 6.20-6.27, 6.49-6.58, 6.127-6.137. **6B** (Rivers/Water): 6.3, 6.8-6.9, 6.59-6.76. **6C** (Roads/Cliffs/Morphology): 6.77-6.88, 6.107-6.118, 6.125-6.126. **6D** (Handler bugs+Socket+Wiring): 6.28-6.48, 6.90-6.106. **6E** (Caves deep-dive): 6.119-6.124 | Each sub-phase owns distinct files; 6D is independent of terrain pipeline |
| 56 | 2 parallel | A: Blender material pipeline (terrain_materials*.py). B: Unity shader (shader_templates.py + scene_templates.py) | **Unity shader (Agent B) can START after Phase 4** — does not depend on Phases 5-6 |
| 57 | 3 parallel | A: AdvancedTerrainErosion UPM + erosion tool. B: terrain LOD+holes+collision. C: trees+NavMesh+mask export | **Tasks 8.1-8.4 can START after Phase 4** — basic Unity integration independent of Blender pipeline |
| 58 | 5 parallel | Each agent gets ~5 independent fixes with non-overlapping files + generator upgrade tasks split into groups of 5 templates | Maximum parallelism, minimal risk |
| 59 | 1 (sequential) | Verification agent runs all checks | Final gate |

### Optimized Execution Order (critical path: 8 phases, not 11)

```
MAIN PIPELINE (critical path):
  Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6A/6B/6C → Phase 7 (Blender materials) → Phase 10

PARALLEL UNITY STREAM (starts after Phase 4):
  Phase 4 done → Unity Stream A (tasks 7.4-7.12 shader + 8.1-8.4 basic integration)
                  → Unity Stream B (tasks 8.5-8.18, after Phase 6 completes)

PARALLEL CLEANUP STREAM (starts after Phase 0):
  Phase 0 done → Phase 0.5 (tasks 9.1-9.5, 9.10, 9.14 — independent code quality fixes)
                  → runs in parallel with Phases 1-6

PARALLEL HANDLER BUG STREAM (starts after Phase 0):
  Phase 0 done → Phase 6D (tasks 6.28-6.48 handler bugs + 6.90-6.106 wiring)
                  → runs in parallel with Phases 1-5

PHASE 9 GENERATOR UPGRADES (after Phase 6):
  Phase 6 done → tasks 9.15-9.26 (generator upgrades, AAA quality)
                  → runs in parallel with Phase 7
```

### Cross-phase dependencies (explicit)

```
Task 6.5  depends on 4.1  (BakedTerrain dataclass)
Task 6.82 depends on 2.5  (stratigraphy) + 5.25 (Poisson blending)
Task 8.16 depends on 6.111 (dual-layer heightmap)
Task 7.1  depends on 6.5  (scatter reads gradient for material assignment)
```

### Agent naming convention

```
Phase-XX-Agent-Y  (e.g., Phase-52-Agent-A = coastline delta conversion)
```

Each agent's prompt includes:
- YOUR FILES (exclusive write access): [list]
- READ-ONLY FILES (do not modify): [everything else]
- DEPENDENCY PROTOCOL: If you need a change in a file you don't own, emit "DEPENDENCY: <file> needs <change>" and STOP that subtask

---

## COMPLETE MAPPING: See FINDINGS_PHASE_MAP.md for the full finding→phase mapping (520+ items, 100% coverage).

---

## Phase 0: Foundation Setup (= Roadmap Phase 49)
**Findings addressed:** CONFLICT-006, CONFLICT-010, CONFLICT-016, CONFLICT-018, F130-F133, F400-F447, F450-F482, F560-F592, F461, F840-F845
**Goal:** Merge master, replace MagicMock conftest, regenerate terrain contract

### Tasks:
- 0.1: Merge master (commit 2877ed5) into feature branch — resolves unmerged fixes
- 0.2: Replace global MagicMock conftest with real fake_bpy module (F461, F840, F841)
  - fake_bpy must error loudly on unimplemented attrs
  - Every existing test that touches bpy must still pass OR be identified as hiding a bug
- 0.3: Regenerate terrain.yaml from current registrar state (CONFLICT-010)
- 0.4: Fix test_substance_lint np.testing.assert_* blind spot (F842)
- 0.5: Run full test suite — establish baseline pass count

### Acceptance:
- [ ] Master merged, no conflicts
- [ ] conftest.py has real fake_bpy, not MagicMock
- [ ] terrain.yaml matches actual registrar (14 bundles, not 18)
- [ ] test_substance_lint recognizes np.testing assertions
- [ ] All tests pass (document any that now FAIL — those are real bugs exposed)

---

## Phase 1: Analytical Erosion Filter (11 tasks)
**Findings addressed:** F277-F300, F801-F805, F860-F864, CONFLICT-003, CONFLICT-008
**Goal:** Port runevision analytical erosion to numpy, replace broken droplet sim, fix ALL noise/erosion math bugs

### Tasks:
- 1.1: Fix gravity sign bug at _terrain_noise.py:1137 (F277) — one-line safety net (line 928 is header, bug at 1137)
- 1.2: Create terrain_erosion_filter.py — port PhacelleNoise + ErosionFilter from lpmitchell C#
  - Pure numpy, no bpy dependency
  - Outputs: height_delta, ridge_map, analytical gradient
  - World-space (x, z, seed, config) evaluation
  - Per-pixel parameter overrides for biome blending
  - AssumedSlope for flat terrain
  - Rounding/Onset vec4 controls
- 1.3: Add ErosionConfig dataclass matching lpmitchell struct (12 fields)
- 1.4: Add ridgeMap field to ErosionMasks or create AnalyticalErosionResult (F860)
- 1.5: Add finite-difference gradient fallback for imported heightmaps (CONFLICT-003)
- 1.6: Delete dead duplicate hydraulic_erosion in _terrain_noise.py:928-1150 (F863)
- 1.7: Wire pass_erosion to use analytical filter instead of droplet sim
- 1.8: Fix OpenSimplex scalar vs array noise mismatch (F805)
- 1.9: Unit tests against known gradients (pure numpy, no bpy needed)
- 1.10: Add per-biome ErosionConfig to terrain.yaml contract — each biome gets own erosion_strength, gully_weight, detail, rounding, onset, assumed_slope. Lerp between adjacent biome configs at boundaries.
- 1.11: Add exit slope threshold (default 0.0075) to analytical erosion filter — particles terminate when local slope drops below threshold. Prevents over-erosion in valleys.

**Amendments to Task 1.2:** Include normalization parameter (~0.4 default) in PhacelleNoise port. Include FadeTarget derivation (configurable amplitude factor, default 0.6, producing flat-bottom valleys and sharp peaks). Document IEEE 754 gradient dead zone around zero.

### Acceptance:
- [ ] terrain_erosion_filter.py passes unit tests with known gradient inputs
- [ ] Two adjacent tiles evaluating same (x,z) produce bit-identical results
- [ ] Ridge map output is -1 on creases, +1 on ridges
- [ ] Existing pipeline tests still pass with new erosion
- [ ] quality_lint.py <= 16 findings on handlers/
- [ ] Perlin noise hash optimization applied (Miles Oetzel technique)

---

## Phase 2: Dead Delta Integration
**Findings addressed:** F820, F821, F822, F824, F825, F001, F002, stratigraphy F-P1
**Goal:** Create integrator pass, wire all orphan deltas to stack.height

### Tasks:
- 2.1: Create pass_integrate_deltas — reads waterfall_pool_delta, cave_height_delta, applies to height
- 2.2: Register integrator pass between waterfalls and materials in pipeline
- 2.3: Fix waterfall produces_channels to include waterfall_pool_delta (F824)
- 2.4: Fix cave produces_channels to include cave_height_delta (F825)
- 2.5: Wire terrain_stratigraphy.apply_differential_erosion() into pass pipeline (R7 P1)
- 2.6: Delete bug-ratifying waterfall test (test_terrain_waterfalls.py:335 pattern)
- 2.7: Write real tests that FAIL if deltas aren't applied (inverse of bug-ratifying)
- 2.8: Implement multi-material thermal erosion in pass_thermal — maintain separate sediment and bedrock height channels. Erosion depletes sediment buffer first; only erodes bedrock when sediment exhausted. Deposition adds to sediment buffer. Creates realistic stratigraphy.

### Acceptance:
- [ ] Waterfall pools depress terrain heightmap
- [ ] Cave carves modify terrain surface
- [ ] Stratigraphic differential erosion is applied
- [ ] No bug-ratifying tests remain
- [ ] Integrator pass registered and running in default pipeline

---

## Phase 3: Bundle I Delta Conversion
**Findings addressed:** CONFLICT-002, F862, F007
**Goal:** Convert height-overwriter passes to delta-returning passes

### Tasks:
- 3.1: Convert pass_coastline from height writer to mask + delta producer
- 3.2: Convert pass_karst from height writer to delta producer
- 3.3: Convert pass_wind_erosion from height writer to delta producer
- 3.4: Convert pass_glacial from height writer to delta producer
- 3.5: Extend integrator pass to compose all deltas (additive, not last-writer-wins)
- 3.6: Add AST lint rule to quality_lint.py: detect stack.set("height",...) outside integrator

### Acceptance:
- [ ] No pass writes directly to stack.height except integrator
- [ ] quality_lint catches any new height-overwriter
- [ ] All Bundle I passes produce deltas
- [ ] Pipeline output is equivalent (integration test)

---

## Phase 4: BakedTerrain Contract + Path Unification + Geological Generators
**Findings addressed:** CONFLICT-004, F105, F107, F108, F145, F204-F213, F823,
F139-F153 (Round 3 legacy path bugs), F117, F119, F123, F124 (geological generators),
GAP-002, GAP-008, GAP-010, GAP-012, GAP-013, GAP-016 (geological gaps)
**Goal:** All 5 authoring paths consume BakedTerrain artifact; independent legacy bugs fixed; geological generators implemented

### Tasks — BakedTerrain core:
- 4.1: Define BakedTerrain dataclass (height grid, ridge map, material masks, metadata, gradient)
- 4.2: Pass DAG produces BakedTerrain as final output
- 4.3: compose_terrain_node consumes BakedTerrain (not re-calling env_generate_terrain with erosion=none)
- 4.4: compose_map consumes BakedTerrain (not bypassing DAG) (F823)
- 4.5: Remove legacy cliff overlay path from _create_terrain_mesh_from_heightmap (F145)
- 4.6: Deprecate cowork_bridge/rebuild_riftpass_01.py (document migration path) (F204-F209)
- 4.7: Fix compose_map LOD dispatch — use pipeline_generate_lods not asset_pipeline (R7 P0)

### Tasks — F139-F153 independent fixes (Round 3 legacy path bugs):
- 4.8: Fix `handle_run_terrain_pass` no cleanup on exception — add try/finally to delete leaked bpy meshes/objects (F150, P0)
- 4.9: Fix `bool("false")=True` inversion in `composition_hints.get("unity_export_opt_out")` — parse string booleans correctly (F152, P0)
- 4.10: Fix erosion iteration escalation `max(150000, resolution²/2)` — make caller-controllable (F140, P0)
- 4.11: Fix `flatten_zones` running BEFORE moisture map — reorder so drainage signal preserved (F143, P0)
- 4.12: Fix `shared_height_range` fallback estimation diverging from real channel data (F153, P0)
- 4.13: Fix double-erosion when `erosion="both"` runs hydraulic + thermal non-exclusively (F148, P0)
- 4.14: Fix biome preset merge dropping seed — preserve reproducible seed (F146, P1)
- 4.15: Fix erosion silently disabled when caller supplies heightmap (F147, P0)
- 4.16: Fix `erosion_margin` cropping — flatten_zones applied in padded space, not inner-tile grid space (F149, P1)
- 4.17: Fix `register_all_terrain_passes(strict=False)` return value discarded — surface missing bundle attribution (F151, P1)
- 4.18: Fix hardcoded `warp_strength=0.4`, `warp_scale=0.5` — make configurable (F141, P1)
- 4.19: Fix `terrain_size = scale` — separate world-size param from noise scale (F142, P1)
- 4.20: Fix moisture map only computed when `erosion_applied=True` — compute unconditionally (F144, P1)
- 4.21: Fix cliff overlay trigger at `cliff_threshold=60°` that bypasses `terrain_cliffs.py` — eliminated by BakedTerrain unification (F145, subsumed)

### Tasks — Geological generators (F117, F119, F123, F124):
- 4.22: [CROSS-REF] Waterfall volumetric 3D mesh spec defined here (F117); implementation in Phase 6 tasks 6.4 + 6.74 + 6.15
- 4.23: Implement curvature-weighted wetness for material assignment — use BakedTerrain curvature output (F119)
- 4.24: Implement debris cone / talus field geometry generator (F123)
- 4.25: Implement natural arch standalone generator (F124)

### Tasks — Geological gaps (GAP-002, GAP-008, GAP-010, GAP-012, GAP-013, GAP-016):
- 4.26: Implement volcanic system: caldera, columnar basalt, pyroclastic flow geometry (GAP-002)
- 4.27: Implement sediment deposition: alluvial fans, deltas, floodplains (GAP-008)
- 4.28: Implement cirque/arete/horn alpine glacial landforms (GAP-010)
- 4.29: Implement stratigraphy visible in cliff faces — exposed rock layers at cliff cross-sections (GAP-012)
- 4.30: Implement columnar basalt joints — hexagonal column geometry for volcanic cliffs (GAP-013)
- 4.31: [MERGED into 2.8] Multi-material thermal erosion mechanism built in Phase 2 task 2.8; this task verifies per-rock-type differential rate integration with stratigraphy (GAP-016)

### Acceptance:
- [ ] Only 1 path to terrain mesh: BakedTerrain → mesh builder
- [ ] compose_map runs full pass DAG
- [ ] compose_terrain_node does NOT call env_generate_terrain with erosion=none
- [ ] LODs actually generate in compose_map
- [ ] Legacy cliff overlay code deleted
- [ ] `handle_run_terrain_pass` cleans up on exception (F150)
- [ ] `bool("false")` no longer inverts intent (F152)
- [ ] Erosion iterations are caller-controllable, not silently escalated (F140)
- [ ] flatten_zones runs AFTER moisture map (F143)
- [ ] Volcanic caldera, columnar basalt, debris cones, natural arches generate real geometry
- [ ] Stratigraphy layers visible in cliff cross-sections
- [ ] Multi-material thermal erosion varies by rock type
- [ ] All 15 F139-F153 items resolved (independent fixes or subsumed by unification)

---

## Phase 5: Seam System + Node Merging
**Findings addressed:** F800, F806, F807, F810-F818, F841,
F164-F169 (stitch bugs), F813, F814, F818 (previously missing from task list),
F115, F116 (geological structure absorbed), GAP-001 (tectonic), GAP-017 (fault displacement),
CONFLICT-005 (smoothstep vs Poisson)
**Goal:** Seam guards work, nodes plug together like puzzle pieces, all stitch bugs fixed

### Tasks — Seam guard + registry core:
- 5.1: Fix seam guard zones — add forbidden_mutations for erosion/waterfalls/materials (F800)
- 5.2: Add hero blend-weight layer: smoothstep(dist_from_edge / guard_width) (F812, CONFLICT-005)
- 5.3: Create TerrainNodeRegistry (config consistency, neighbor tracking) (F810)
- 5.4: Add cross-tile boundary validator (load neighbor edge, compare heights) (F811)
- 5.5: Fix smooth post-process box blur tile-edge wrapping (F806)
- 5.6: Fix crater/volcanic preset tile-local center (F807)
- 5.7: Fix erosion np.pad edge mode — use neighbor data or zero-gradient (F817)

### Tasks — F164-F169 stitch bugs:
- 5.8: Fix `handle_stitch_terrain_edges` non-idempotent — averages Z at seam, running twice drifts toward avg-of-avgs. Make idempotent (F164, P0)
- 5.9: Fix `_edge_vertices` tolerance=1e-4 on raw coords — at world_origin_x=500000 rounds to ~0 matches. Use relative tolerance or local-space comparison (F165, P0)
- 5.10: Fix `handle_paint_terrain` leaking materials — creates new materials every call with no cleanup. Add `bpy.data.materials.remove` on replace (F166, P0)
- 5.11: Fix `handle_carve_river` and `handle_generate_road` height_scale fallback — sub-sea-level flats get 100x inflation from divide-by-near-zero (F167, P0)
- 5.12: Fix `handle_export_heightmap` garbled output on non-rectangular sculpted grids — add `rows*cols == len(heights)` assertion (F168, P0)
- 5.13: Fix Unity compat resize using nearest-neighbor only — downsampling 2049->1025 loses hero detail. Use bilinear/bicubic (F169, P0)

### Tasks — F813, F814, F818 (previously missing from task list):
- 5.14: Fix protected zone enforcement permissive — partial intersection explicitly allowed. Add per-cell zone checking to erosion/waterfalls/materials_v2 passes (F813, P1)
- 5.15: Fix seam validation verify-only with no repair — wire `handle_stitch_terrain_edges` into compose_terrain_node post-pass, add re-erosion/edge blending on validation failure (F814, P1)
- 5.16: Fix triplanar flag with no cross-tile UV continuity — pass_materials must compute world-space-continuous triplanar projection, not per-tile-independent (F818, P2)

### Tasks — Stitch coordinate/topology fixes:
- 5.17: Fix stitch function local-space coordinates — tiles with different obj.location offsets produce wrong matches. Convert to world-space before matching (F815, P1)
- 5.18: Fix stitch hard-fail on vertex count mismatch — add interpolation or nearest-vertex fallback for topology changes from subdivision/remesh (F816, P1)

### Tasks — Geological structure (absorbed from deferred):
- 5.19: Wire rock_hardness from stratigraphy to differential erosion — enable banded erosion patterns (F115)
- 5.20: Implement fault line displacement system — normal/reverse/strike-slip faults for non-noise-shaped mountains (F116, GAP-001, GAP-017)

### Tasks — Advanced merging + hero-node refinement:
- 5.24: Implement optional pipe-model hydraulic erosion refinement for hero terrain nodes (Mei/Decaudin). After analytical base layer, run pipe-model iterations on overlapping regions for local pooling, undercut banks, alluvial fans. Include flux scaling limiter K=min(1, d*dx²/(sum(f)*dt)), water-height gating C=Kc*sin(a)*|v|*clamp(d,0,1), semi-Lagrangian advection, flux-derived velocity, implicit Euler, bulk momentum averaging. Only runs on hero nodes, not base tiles.
- 5.25: Implement Poisson blending (Laplace equation solver) as alternative to smoothstep for merging hero geometry into base terrain. Preserves interior gradients while matching boundary conditions. A/B test vs smoothstep blend-weight — use whichever produces fewer visible seams.

### Tasks — Tests:
- 5.21: Write edge-matching integration tests proving puzzle-piece tiling (F841)
- 5.22: Write stitch idempotency test — stitch twice, verify heights unchanged on second pass
- 5.23: Write protected zone enforcement test — verify erosion/waterfall mutations blocked in guard band

### Acceptance:
- [ ] Two adjacent tiles have identical height at shared boundary (atol=1e-12)
- [ ] Hero deltas fade to zero at tile edges via blend weight
- [ ] Seam guard zones actually block erosion/waterfalls/materials in guard band
- [ ] Node registry tracks populated tiles and validates config consistency
- [ ] Stitch is idempotent — running twice produces same result (F164)
- [ ] Edge vertex matching works at large world offsets (F165)
- [ ] No material leaks on repaint (F166)
- [ ] River/road height_scale never divides by near-zero (F167)
- [ ] Heightmap export validates grid rectangularity (F168)
- [ ] Unity resize uses bilinear, not nearest-neighbor (F169)
- [ ] Protected zones enforce per-cell blocking for all mutation passes (F813)
- [ ] Seam validation triggers repair, not just warning string (F814)
- [ ] Triplanar projection is world-space continuous across tiles (F818)
- [ ] Fault lines produce visible tectonic displacement in terrain (F116)
- [ ] Integration tests prove puzzle-piece tiling

---

## Phase 6: Scatter + Rivers + Water
**Findings addressed:** F830-F838, F064-F067 (Tripo/scatter), F154-F163 (hero builder bugs),
F241-F269 (29 non-terrain handler bugs affecting scatter/settlement/worldbuilding/socket),
F854, CONFLICT-007,
NEW-R8-01 through NEW-R8-18, CODEX-R14-01 through CODEX-R14-04,
F113, F114, F118, F122, F125, F126, F127 (absorbed from deferred),
GAP-003, GAP-009, GAP-023, GAP-024, GAP-027 (absorbed from deferred),
R15J wiring gaps (32 functions with zero production callers)
**Goal:** Scatter reads slope/ridge, rivers have visible water, waterfalls have mesh, all handler bugs fixed, dead functions wired in

### Tasks — Scatter core fixes (F830-F838):
- 6.1: Fix prop scatter object name lookup (F830) — use terrain object, not area_name
- 6.2: Add slope filtering to prop scatter (F831) — dot(normal, up) threshold
- 6.3: Wire terrain pipeline to generate spline/ribbon river mesh from flow accumulation network. Width/depth derived from flow_accumulation values. Resample river paths into splines, generate cross-section profiles, carve banks into terrain, triangulate lake shore polygons. Pass mesh specs to handle_create_water (F832 corrected)
- 6.4: Build waterfall volumetric mesh from WaterfallVolumetricProfile spec (F833)
- 6.5: Wire scatter to read analytical gradient + ridge_map from BakedTerrain (F834)
- 6.6: Fix slope alignment gradient normalization (F835)
- 6.7: Wire Tripo manifest to scatter as fallback generator (F836)
- 6.8: Fix river carving negative height destruction (F837)
- 6.9: Add water surface mesh consumer for Bundle O water_surface channel (F838)

### Tasks — Hero builder bugs (F154-F163):
- 6.10: Fix `handle_build_cliff_face` hardcoded params (width=20, height=15, seed=42) — read pass_cliffs output instead (F154, P0)
- 6.11: Fix `generate_cliff_face` paper-thin single-surface — add thickness, back face, sides for volumetric cliff (F155, P0)
- 6.12: Fix ledge path 2-vert-wide flat ribbon — make walkable wedge geometry (F156, P0)
- 6.13: Fix `handle_build_cave_entrance` hardcoded dimensions — caves float if terrain not at Z=0 (F157, P0)
- 6.14: Fix `handle_build_waterfall` legacy_geometry_fallback — every hero waterfall goes through legacy path because heightmap never supplied (F158, P0)
- 6.15: Fix `generate_waterfall` NOT volumetric — violates `feedback_waterfall_must_have_volume.md`. Add water-sheet mesh, volumetric ledges, real splash geometry (F159, P0)
- 6.16: Fix orphan material slot — `materials` list has 5 entries, "moss" never referenced (F160, P0)
- 6.17: Fix waterfall `facing_direction` param — handler never passes it, waterfalls always face legacy -Y instead of river direction (F161, P1)
- 6.18: Wire `terrain_waterfalls_volumetric.py` — currently validator-only, never imported by any handler. Enforce volumetric contract in pipeline (F162, P0)
- 6.19: Fix `legacy["warning"]` string in return dict — callers that don't inspect treat as success. Raise or log properly (F163, P0)

### Tasks — F241-F269 non-terrain handler bugs (29 items):
- 6.20: Fix `_scatter_pass` hardcoded `_BIOME_DENSITY.get(biome, 0.5)` — unknown biome silently defaults. Add warning (F241, P0)
- 6.21: Fix slope/height thresholds `sl > 30.0 or h < 0.1 or h > 0.7` hardcoded — make biome-configurable. Alpine can't place trees above h=0.7 (F242, P0)
- 6.22: Fix grid dim detection fallback `side = int(sqrt(vert_count))` — silently corrupts non-square terrains (F243, P0)
- 6.23: Fix building footprint detection iterating ALL `bpy.data.objects` — any empty with children treated as exclusion zone (F244, P0)
- 6.24: Fix road detection `"road" in _obj.name.lower()` — "Broadsword" falsely excluded (F245, P0)
- 6.25: Fix `bpy.data.objects.new()` per instance with no cleanup — re-running produces .001, .002 ever-growing (F246, P0)
- 6.26: Fix `slope_roll = math.atan2(dzdx, 1.0)` — the 1.0 is wrong, slope roll artificially damped. Same at slope_pitch (F247, P0)
- 6.27: Fix `handle_scatter_props` passes scatter-collection name as terrain_name — `bpy.data.objects.get(area_name)` is None, every prop at Z=0 (F248, P0)
- 6.28: Fix `_sample_heightmap` called 4x per building corner, 200 buildings = 800 raycasts — add caching (F249, P0)
- 6.29: Fix `platform_elevation = max_elevation` on terraced terrain — all pads match highest corner (F250, P1)
- 6.30: Fix `_place_buildings` runs BEFORE heightmap-aware computation — nothing rejects placement requiring 10m foundation (F251, P0)
- 6.31: Fix `_generate_alleys` + `_scatter_settlement_props` never receive heightmap — alleys planar, props at Z=0 (F252, P0)
- 6.32: Fix `_sample_scene_height` hardcoded 10km ceiling — terrains >10km high silently return fallback (F253, P0)
- 6.33: Fix castle mesh generation swallowing — one battlement fails, ALL subsequent skipped (F254, P0)
- 6.34: Fix GLB import swallow — Tripo prop import failures logged but settlement proceeds without prop (F255, P0)
- 6.35: Fix terrain alignment on prop placement swallowed — props float/sink (F256, P0)
- 6.36: Fix `env_generate_world_terrain` commented DEPRECATED but still registered — old callers hit monolithic path (F257, P0)
- 6.37: Fix ~25 terrain-adjacent handlers registered as inline lambdas with no error handling (F258, P0)
- 6.38: Fix duplicate `terrain_validate_tile_seams` / `env_validate_tile_seams` pointing to same function (F259, P1)
- 6.39: Fix equipment weapon type 6-way if/elif — unknown weapon silently generates sword (F260, P1)
- 6.40: Fix addon reload orphaned timer — two servers fight for port 9876 (F261, P0)
- 6.41: Fix `unregister` not stopping in-flight `_handle_client` threads — reload orphans daemon threads (F262, P1)
- 6.42: Fix `result_event.wait(timeout=300)` race — slow command N's result overwrites fast command N+1 (F263, P0)
- 6.43: Fix `_process_commands` pops ONE command per 10ms tick — 100 cmd/sec throughput ceiling (F264, P0)
- 6.44: Fix handler returning `{"status":"partial"}` bypassing wrapper — downstream treats as error (F265, P0)
- 6.45: Fix no outbound size cap — 100MB dict crashes sendall (F266, P0)
- 6.46: Fix unbounded `command_queue.put()` — 1000 queued commands = memory explosion (F267, P0)
- 6.47: Fix `_handle_client` background thread reading bpy objects — Blender API violation, random crash (F268, P0)
- 6.48: Fix `bpy.app.timers.register(persistent=True)` — survives file-load, crashes on scene reload (F269, P1)

### Tasks — Best-practice additions (from research alignment):
- 6.107: Refactor _terrain_height_sampler to accept Callable[[float,float],float] from BakedTerrain.sample_height instead of bpy.data.objects.get with silent Z=0 fallback. Raise ValueError if no height source.
- 6.108: Implement discharge-dependent erosion with power-law exponent (discharge^0.4) in river carving. Larger streams erode proportionally less per unit discharge than small tributaries.
- 6.109: Implement accumulation curvature — curvature weighted by flow accumulation. Feed to material assignment and scatter rules.
- 6.110: Add geological stratification to cliff mesh builder — quantize cliff height into layers with different erosion resistance, producing visible ledge-and-face patterns (bedding planes, hoodoos, mesas).
- 6.111: Implement dual-layer heightmap for overhangs/arches — BakedTerrain gets optional ceiling_height grid. Mesh builder generates floor + ceiling geometry. Unity punches terrain holes where ceiling exists.
- 6.112: Implement depression filling and breach handling in flow accumulation pipeline — fill pits below min volume (become lakes), breach saddles blocking drainage. Complete drainage network, no orphan basins.
- 6.113: Implement terrain-flatten pass under building footprints — flatten with soft falloff (cosine blend over 2-5m border). Apply as height delta through integrator, not direct write.
- 6.114: Replace MST-based road routing with slope-weighted A* — cost = base_cost + slope²*penalty. Roads follow contours, avoid steep grades, find passes. MST determines connectivity, A* determines routes.
- 6.115: Upgrade cave path generation from random heading + sine to stress/water-driven branching — follow fault lines, water flow from ridge map, bedrock weakness. Add chamber reveals, roof-fall debris, surface connection via terrain holes.
- 6.116: Upgrade generate_swamp_terrain from flat noise + radial hummocks to drainage-derived micro-basins. Organic drainage channels, root heave bumps, peat shelf edges. Standing water fills micro-basins.
- 6.117: Compute Strahler stream order from ridge map skeleton — skeletonize ridge map, count pixel neighbors at junctions to assign stream order. Feed to river width/depth computation (F121)
- 6.118: Implement fractal coastline subdivision — replace noise-based coastline shape with fractal midpoint displacement for natural cove/peninsula/headland geometry (BEST_PRACTICES section 8.4)

### Tasks — Cave deep-dive (BEST_PRACTICES Section 14):
- 6.119: Implement Perlin worm cave path generation + marching cubes mesh — use 3D Perlin worm (simplex noise gradient following) to carve cave skeleton, then expand chambers with cellular automata, generate mesh via marching cubes for volumetric cave geometry with ceiling/walls/floor as independent surfaces (BEST_PRACTICES #14.1)
- 6.120: Implement stalactite/stalagmite L-system generation — iterative drip-line growth following Cui & Chow paper. Stalactites hang from ceiling at water ingress points, stalagmites grow from floor below drip lines. Variable thickness, clustering, occasional column merges (BEST_PRACTICES #14.2 item 2)
- 6.121: Implement cave water pool insertion at floor minima — detect local minima in cave floor mesh, insert flat reflective water surface with caustics material. Pool depth proportional to chamber volume. Wet-zone material transition around pool edges (BEST_PRACTICES #14.2 item 4)
- 6.122: Implement cave lighting metadata export — detect ceiling crack positions for god-ray light shafts, mark bioluminescent zones (mushroom/lichen clusters on damp walls), export as metadata channels for Unity volumetric lighting setup (BEST_PRACTICES #14.2 item 3)
- 6.123: Implement portal-based streaming at cave entrances — define portal geometry at cave mouth, export portal bounds + connected interior cell IDs for Unity additive scene loading. Interior geometry in separate scene, loaded when player approaches portal (BEST_PRACTICES #14.1, Elden Ring reference)
- 6.124: Implement cave entrance asymmetry — cave mouths must NOT be perfect arches. Add irregular lip geometry: one side higher, rubble pile partially blocking, vegetation overhang, erosion-worn edges. Randomize entrance profile per seed (BEST_PRACTICES #14.2)

### Tasks — Cliff deep-dive (BEST_PRACTICES Section 14):
- 6.125: Add rock type classification to cliff mesh builder — BASALT (hexagonal columnar joints), SANDSTONE (rounded strata, wind-worn curves), GRANITE (large irregular angular blocks). Rock type influences fracture pattern, strata thickness, weathering profile, and talus debris shape. Selectable per-biome or per-cliff-instance (BEST_PRACTICES #14.4 item 6)
- 6.126: Implement cliff-terrain transition geometry — skirt mesh (curved transition from cliff base to terrain surface) + shader blending (cliff mesh samples terrain texture at contact zone via depth mask, MicroSplat approach). Extend cliff bottom 1-2m into terrain to ensure overlap, not gap (BEST_PRACTICES #14.5)

### Tasks — Scatter feature tasks:
- 6.49: Implement slope-threshold instancing (4-bucket: sheer_rock/stairs/small_rock/grass)
- 6.50: Fix scatter 2D->3D positions — `_scatter_pass` stores (wx,wy) with no Z, causing Z=0 placement (Opus scatter scan P0)
- 6.51: Add slope alignment to vegetation — trees on steep slopes must rotate perpendicular to surface (Opus scatter scan P0)
- 6.52: Add Tripo asset cache — download GLBs once, cache locally, reuse across scatter (F066)
- 6.53: Wire GPU instancing export to disk — write JSON + actually export (Opus scatter P1, F126)
- 6.54: Fix altitude normalization — use actual mesh Z range, not height_scale param (Opus env.py P1)
- 6.55: Fix multi_biome_world crash when biomes=None (Opus env.py P0)
- 6.56: Wire Tripo environmental prop pipeline — manifest -> scatter (F127, NEW-R8-07)
- 6.57: Add per-instance color variation to scatter (GAP-024)
- 6.58: Add vegetation interaction system — trampling, bending on collision (GAP-023)

### Tasks — Vegetation scatter deep-dive (BEST_PRACTICES Section 15):
- 6.127: Implement Voronoi clumping for vegetation scatter — assign scatter points to Voronoi cells, points within same cell share clump properties (lean direction, density multiplier, species bias). Produces natural tree groves and shrub clusters instead of uniform distribution (BEST_PRACTICES #15.5 item 3, Ghost of Tsushima reference)
- 6.128: Implement variable-density Poisson disk sampling — density map (from moisture, slope, altitude, biome) modulates min_distance parameter. Dense forest = small min_distance, sparse alpine = large min_distance. Replaces fixed-radius Poisson disk (BEST_PRACTICES #15.5)
- 6.129: Implement flow accumulation moisture map feeding into scatter — derive moisture from ridge_map flow accumulation (high accumulation = wet valley, low = dry ridge). Moisture drives species selection, density, and ground cover type. Wire to scatter pass as input channel (BEST_PRACTICES #15.1, Witcher 3 reference)
- 6.130: Implement species compatibility matrix at biome transitions — prevent ecologically nonsensical combinations (e.g., cactus next to fern). Matrix defines allowed co-occurrence per biome pair. At biome boundary, only species valid in BOTH biomes may spawn in transition zone (BEST_PRACTICES #15.6)
- 6.131: Implement dark fantasy corruption zone rings — 4 concentric zones from corruption epicenter: (1) bare twisted rock + corruption tendrils, (2) dead trees + bioluminescent mushrooms, (3) blighted vegetation (desaturated, wilted), (4) normal with occasional blight patches. Zone radii configurable per corruption source. Wire to scatter pass as corruption_mask input (BEST_PRACTICES #15.6)
- 6.132: Implement bioluminescent mushroom scatter species — emission_color (0.1, 0.4, 0.3), emission_strength 0.8. Cluster on damp walls, cave floors, corruption zone ring 2. Export emission data for Unity point light or emissive material (BEST_PRACTICES #15.6)
- 6.133: Implement twisted tree trunk sine-wave displacement — 2-4 sine cycles along trunk height, 10-20% amplitude relative to trunk radius. Apply as mesh deformation during tree generation. Corruption intensity modulates cycle count and amplitude (BEST_PRACTICES #15.6)
- 6.134: Implement altitudinal zonation for vegetation — 6 altitude bands (valley floor/lowland/montane/subalpine/alpine/nival) with species lists, density curves, and undergrowth rules per band. Normalize altitude relative to terrain height range, not absolute meters (BEST_PRACTICES #15.3)
- 6.135: Implement forest structure layers — canopy (15-30m, density 0.15-0.25), understory (5-15m, shade-tolerant, inverse canopy density), shrub (1-5m, edge effect boost), ground cover (0-1m, moisture-driven). Dense canopy suppresses understory by 60%. Multi-pass scatter with layer interaction (BEST_PRACTICES #15.4)
- 6.136: Implement multi-pass exclusion zones for scatter — buildings, roads, cliff faces, water bodies each define exclusion polygons. Scatter skips points inside any exclusion zone. Edge softening: density ramps from 0 to full over 2-5m from exclusion boundary (BEST_PRACTICES #15.5)
- 6.137: Implement per-instance color variation for vegetation — hue shift +/-10 degrees, brightness +/-15%, scale 0.7-1.3x, rotation 0-360. Variation seeded by instance position hash for determinism. Prevents "clone army" appearance (BEST_PRACTICES #15.5 item 4)

### Tasks — River + water fixes:
- 6.59: FIX A* cost function — remove abs(height_diff) at _terrain_noise.py:764 so downhill is cheap, uphill expensive (NEW-R8-10, ROOT CAUSE of straight-line rivers)
- 6.60: Implement path network (A* on heightfield) for stairs-as-intersection (CONFLICT-007)
- 6.61: Lake mesh generation — wire detect_lakes() output to handle_create_water for flat lake surface mesh (F118, GAP-027)
- 6.62: Ocean water plane — for open ocean/sea, use multi-cascade FFT wave simulation (or prepare FFT-compatible normal/displacement maps for Unity shader). For rivers/small lakes, keep spline/flowmap-driven. Blender preview uses simplified displacement; Unity uses full FFT shader.
- 6.63: Shoreline treatment using signed distance field from water boundaries — shore foam intensity = SDF * flow_speed. Separate 'wet edge' mask for rock darkening + soft alpha fade. Wet sand transition zone. Wave-edge blending. Export SDF + foam mask as additional texture channel.
- 6.64: Fix perched lake detection inversion — currently finds hilltops, not basins (Opus road/water P2)
- 6.65: Replace fixed sine-wave meander with discharge-driven curvature. Outer banks erode faster (proportional to discharge*momentum), inner banks deposit sediment. River width, bend radius, bank asymmetry derived from drainage strength, not arbitrary sine params. Variable wavelength from discharge variation (F122, GAP-009)
- 6.66: Fix Wetland dataclass — add radius_m and world_pos attributes (NEW-R8-01, NEW-R8-02)
- 6.67: Fix detect_hot_springs call signature — pass volcanic_activity_mask (NEW-R8-03)
- 6.68: Wire 6 dead water detectors into pass_water_variants body (NEW-R8-04)
- 6.69: Wire water feature spec generators from terrain_bundle_o into pipeline schedule (NEW-R8-05)
- 6.70: Fix moisture_map computed via distance transform then silently discarded every call (NEW-R8-12)
- 6.71: Fix flow_dir_z vertex color encodes horizontal tangent not vertical — shader reads wrong data (NEW-R8-14)
- 6.72: Fix RNG constructed from derived seed then immediately discarded (assigned to _) in terrain_waterfalls.py:681 (NEW-R8-15)
- 6.73: Fix D8 angle north-south mirrored — waterfall lips/pools placed on wrong side of slopes (NEW-R8-16)
- 6.74: Add water curtain mesh to generate_waterfall with: plunge-pool erosion depression (height delta fed to integrator), splash shelves at lip and pool edge, mist-wet material darkening zone (radius proportional to waterfall height). Currently cliff rock with zero falling water geometry (NEW-R8-13)
- 6.75: Implement river 3D geometry — spline mesh + flowmap bake, Arnklit Waterways pattern (F114, GAP-003)
- 6.76: Implement natural arch geometry at cliff-river intersections (F125)

### Tasks — Road + terrain features:
- 6.77: Wire road_network mesh_specs to Blender handler — create actual road mesh objects (NEW-R8-06)
- 6.78: Fix road terrain height sampling — roads must sample terrain Z along segments (Opus road scan P1)
- 6.79: Road-terrain material blending — road edges blend into terrain material
- 6.80: Add saddle/col/mountain pass template to terrain_morphology.py catalog (NEW-R8-08)
- 6.81: Wire A* to carve mountain passes through ridgelines + generate trail mesh (NEW-R8-09)
- 6.82: Implement real cliff mesh builder from cliff_candidate mask — replace stub with bmesh geometry including: stratified overhang meshes (from stratigraphy), fracture shelves with directional weathering, contact debris at cliff base. Hero insertion uses Poisson or smoothstep blending at boundaries (F854, NEW-R8-18)
- 6.83: Fix canyon wall profile — reverse inverted trapezoid so walls vertical/inward. Add heightfield remap for near-vertical cliffs + terracing pass for ledge-and-face walls. Use hydrology-based incision depth (proportional to discharge) instead of uniform noise. Canyon cross-section varies along length based on upstream discharge (NEW-R8-11)
- 6.84: Add vertical wall/scarp capability to morphology template system — enable discontinuities in height profiles so templates CAN produce non-smooth shapes (NEW-R8-17). Full template-by-template geology upgrade deferred to Phase 9 task 9.16.

### Tasks — CODEX-R14 cliff pipeline bugs:
- 6.85: Fix region scoping clips components at boundaries instead of filtering by center — same cliff split into multiple smaller cliffs (CODEX-R14-01, P1)
- 6.86: Fix hard validation failures mapped to status="warning" not "failed" — broken cliffs continue as non-fatal (CODEX-R14-02, P1)
- 6.87: Fix `_extract_lip_polyline` returns scanline order not contour order — downstream extrusion produces zig-zagged rims (CODEX-R14-03, P1)
- 6.88: Fix talus `angle_of_repose_deg` stored but never influences mask — `apron_cells` forced through max(1,...), talus cannot be tuned or disabled (CODEX-R14-04, P2)

### Tasks — Pipe-model erosion (absorbed from deferred):
- 6.89: [MOVED to 5.24] Pipe-model erosion for hero nodes now lives in Phase 5 task 5.24 (F113)

### Tasks — R15J wiring gaps (32 functions with zero production callers):
- 6.90: Wire `generate_biome_transition_mesh` into pipeline — call from pass or compose_* when biome boundary detected
- 6.91: Wire `generate_waterfall_mesh` into pipeline — call from compose_terrain_node waterfall stage
- 6.92: Wire `generate_terrain_bridge_mesh` into pipeline — call when path network crosses river/canyon
- 6.93: [DUPLICATE of 2.5] apply_differential_erosion wiring handled in Phase 2 task 2.5
- 6.94: Wire `generate_braided_channels` into pass_water_variants body
- 6.95: Wire `detect_estuary` into pass_water_variants body
- 6.96: Wire `detect_karst_springs` into pass_water_variants body
- 6.97: Wire `detect_perched_lakes` into pass_water_variants body
- 6.98: Wire `apply_seasonal_water_state` into pass_water_variants body
- 6.99: Wire `apply_morphology_template` (30 templates) into compose_terrain_node or pass pipeline
- 6.100: Wire `compute_height_blended_weights` into pass_materials
- 6.101: Wire `detect_destructibility_patches` into pipeline for gameplay layer export
- 6.102: Wire `compute_footprint_surface_data` into settlement/building placement
- 6.103: Wire `apply_edit` from terrain_live_preview into Blender handler for real-time editing
- 6.104: Wire `generate_weathering_timeline` + `apply_weathering_event` into pipeline
- 6.105: Wire `generate_diff_overlay` into pipeline for visual diff tooling
- 6.106: Wire remaining ~15 R15J zero-caller functions (audit full R15J list, wire each with 1-line call site in appropriate pass/compose)

### Acceptance:
- [ ] Props placed at correct Z height on terrain (F248, F250-F252 fixed)
- [ ] No props on vertical cliffs (F242 biome-configurable thresholds)
- [ ] Rivers have visible water surface mesh in Blender with natural meander
- [ ] Lakes have visible water surface mesh
- [ ] Ocean plane exists with shore foam
- [ ] Waterfalls have 3D volumetric mesh WITH water curtain (F159, NEW-R8-13)
- [ ] Roads are actual Blender mesh objects conforming to terrain (NEW-R8-06)
- [ ] Mountain passes have saddle templates and carved trail geometry (NEW-R8-08/09)
- [ ] Cliff faces are real bmesh geometry, not a placeholder stub (NEW-R8-18)
- [ ] Canyon walls are vertical/inward, not inverted trapezoid (NEW-R8-11)
- [ ] Scatter uses analytical gradient, not finite-diff (F834)
- [ ] Path network exists, stairs emerge at steep+path intersection (CONFLICT-007)
- [ ] A* routes rivers downhill, not uphill=downhill (NEW-R8-10)
- [ ] All 29 F241-F269 handler bugs fixed
- [ ] All 10 F154-F163 hero builder bugs fixed
- [ ] All 4 CODEX-R14 cliff pipeline bugs fixed
- [ ] All 6 NEW-R8 water variant fixes applied (01-05, 12-17)
- [ ] Socket server race conditions eliminated (F263-F268)
- [ ] All 32 R15J zero-caller functions have at least one production call site
- [ ] D8 angle direction correct for waterfall placement (NEW-R8-16)
- [ ] Moisture map not silently discarded (NEW-R8-12)
- [ ] Morphology templates include discontinuities, not just smooth Gaussians (NEW-R8-17)
- [ ] Caves use Perlin worm paths + marching cubes mesh, not random heading + sine (6.119)
- [ ] Stalactites/stalagmites generated via L-system in caves (6.120)
- [ ] Cave water pools at floor minima with reflective surface (6.121)
- [ ] Cave lighting metadata exported (crack positions, bioluminescent zones) (6.122)
- [ ] Portal-based streaming defined at cave entrances (6.123)
- [ ] Cave entrances are asymmetric, not perfect arches (6.124)
- [ ] Cliff rock type classification (basalt/sandstone/granite) drives geometry (6.125)
- [ ] Cliff-terrain transition has skirt mesh or shader blending (6.126)
- [ ] Voronoi clumping produces natural tree groves (6.127)
- [ ] Variable-density Poisson disk modulated by moisture/slope/altitude (6.128)
- [ ] Flow accumulation moisture map feeds scatter species selection (6.129)
- [ ] Species compatibility matrix prevents nonsensical biome-boundary combos (6.130)
- [ ] Dark fantasy corruption zones produce 4 concentric rings (6.131)
- [ ] Bioluminescent mushrooms emit light in caves and corruption zones (6.132)
- [ ] Twisted trees have sine-wave trunk displacement (6.133)
- [ ] Altitudinal zonation produces 6 distinct vegetation bands (6.134)
- [ ] Forest structure has canopy/understory/shrub/ground layers (6.135)
- [ ] Multi-pass exclusion zones prevent scatter in buildings/roads/cliffs/water (6.136)
- [ ] Per-instance color/scale/rotation variation eliminates clone appearance (6.137)

---


## Phase 7: Material Pipeline + Shaders (= Roadmap Phase 56)
**Findings addressed:** F034-F049 (16 material bugs), F270-F276 (material split-brain), F600-F621 (materials deep),
F826-F828, CONFLICT-011, F120, F121, F128, F129,
RGAP-001 through RGAP-033 (33 rendering gaps)
**Goal:** One unified material system in Blender with real PBR textures + triplanar + displacement. AAA shader node graph.

### Cluster A: Kill split-brain — unify legacy vs V2 material systems (F270-F276, F603)
- 7.A1: Delete legacy `BIOME_PALETTES` zone schema (`ground/slopes/cliffs/water_edges`) and migrate all callers to V2 schema (`ground/slope/cliff/special`) (F270)
- 7.A2: Unify splatmap attribute name to single `VB_TerrainSplatmap` — remove `TerrainSplatmap_<biome>` legacy path (F271)
- 7.A3: Delete V2 `alpha` / `blend_method` fields that no shader reads — or implement real transparency for water_edges (F272)
- 7.A4: Wire `roughness_variation`, `wear_intensity`, `node_recipe` V2 layer keys to actual shader differentiation — or delete them (F273)
- 7.A5: Fix ProtocolGate theater — either enforce protocol rules or remove the gate entirely (F274)
- 7.A6: Fix `mesh_from_spec()` to apply per-face `material_ids` from hero builders instead of ignoring them (F275)
- 7.A7: Fix cave entrance axis contract confusion (Y vs Z depth direction) (F276)
- 7.A8: Unify three disjoint rule schemas (legacy BIOME_PALETTES, V2 palettes, MaterialRuleSet) into single vocabulary (F603)

### Cluster B: Real PBR textures — fix the "no textures ever bound" class (F034-F049, F600-F621)
- 7.B1: Generate procedural PBR texture set (albedo, normal, roughness, AO, height) for all terrain layer types using Blender Musgrave Hetero Terrain + Hybrid Multifractal + Ridged Multifractal noise nodes, remapped through color ramps (CONFLICT-011, F612)
- 7.B2: Wire `texture.py` PBR builder (`handle_create_pbr_material` / `handle_load_extracted_textures`) into terrain material creation path — replace hardcoded base_color tuples (F034, F036, F049, F601)
- 7.B3: Fix material bind ordering — create `VB_TerrainSplatmap` vertex color attribute BEFORE material assignment (F035)
- 7.B4: Replace `ShaderNodeBump` on `ShaderNodeTexNoise` with `ShaderNodeNormalMap` using real normal textures (F037)
- 7.B5: Add `ShaderNodeTexCoord` + `ShaderNodeMapping` for explicit UV/world-space coordinate control (F041)
- 7.B6: Fix material `slot_offset` miscalculation for pre-existing slots (F039)
- 7.B7: Add UV unwrap pass — procedural UV via Geometry Nodes UV Unwrap node (Blender 3.3+) for terrain meshes, cliff meshes, debris, modular structures (F040, BEST_PRACTICES #34)
- 7.B8: Fix material `nodes.clear()` race — use unique material names per tile or guard against parallel rebuilds (F045)
- 7.B9: Fix material double-append (F046)
- 7.B10: Fix HeightBlend to use actual heightmap samples, not noise `Fac` (F047)
- 7.B11: Add `mesh.update()` after `color_attributes` write in biome terrain material (F048)
- 7.B12: Fix snow altitude threshold — make relative to terrain height_scale, not absolute 250m (F604)
- 7.B13: Fix multi-biome vertex-color fallback — wire V2 biome names to palette lookup so 16-biome worlds don't paint uniform dark-brown (F605)
- 7.B14: Fix metallic values for crystal_cavern/mountain_pass layers — currently all pinned 0.0 despite descriptions saying "high metallic" (F616)
- 7.B15: Wire `node_recipe` (terrain/stone/organic) to differentiated shader sub-graphs (F617)
- 7.B16: Wire `emission_color/strength/subsurface_weight` from V2 palette slots to actual shader nodes (F619)
- 7.B17: Implement Blender procedural terrain material stack — Geometry Nodes for terrain-aware material assignment combining noise nodes with color ramps

### Cluster C: Wire DAG splatmap to Blender mesh (F826-F828)
- 7.C1: Wire pass_materials `splatmap_weights_layer` to Blender mesh vertex colors (F826)
- 7.C2: Fix material auto-assign to read DAG splatmap data instead of recomputing from local vertex positions (F827)
- 7.C3: Add world-space material continuity across tiles — sample world-space noise at shared coordinates (F828)
- 7.C4: Wire `compute_height_blended_weights` (currently zero callers) into material assignment (BEST_PRACTICES #10.6)

### Cluster D: Triplanar + displacement + POM (RGAP-001, RGAP-004, F038, F042, F610, F615)
- 7.D1: Implement real triplanar shader node group — GPU triplanar sampling (XY/YZ/XZ blend by normal^2). Selective: only on cliffs/steep slopes/UV-less meshes, not everywhere (F615, F038, RGAP-001, BEST_PRACTICES #4)
- 7.D2: Add `ShaderNodeDisplacement` wiring — connect height texture to displacement output with `displacement_method='BOTH'` (F042, F610, RGAP-004)
- 7.D3: Add persistent world-space cliff detail noise via 3D simplex triplanar sample — survives heightmap edits, seamless across streamed chunks (BEST_PRACTICES #6.4)
- 7.D4: Add POM (Parallax Occlusion Mapping) node group for close-up terrain depth (RGAP-004)

### Cluster E: Macro variation + detail normals + weathering (RGAP-002, RGAP-003, RGAP-009, F043, F044, F120)
- 7.E1: Add macro-variation sampler — large-scale color/roughness noise to break tiling repetition (RGAP-002)
- 7.E2: Implement macro + detail normal blending via Reoriented Normal Mapping from analytical erosion gradient. Bake terrain normal map at 2x-4x heightmap resolution. Export as additional texture channel for Unity (F043, F120, RGAP-003)
- 7.E3: Add per-layer ambient occlusion bake/approximation (RGAP-009)
- 7.E4: Implement wetness as overlay/modifier layer — Fresnel/curvature-driven wetness modulates roughness/darkening, moss mask, snow dot-product accumulation. Paintable wetness separate from base materials (F044, RGAP-006)
- 7.E5: Add Strahler stream order derived from ridge map for river width/depth material zones (F121)

### Cluster F: Stochastic tiling + splatmap expansion (RGAP-007, RGAP-008, RGAP-016)
- 7.F1: Implement stochastic/random tiling to suppress texture repetition — port UnityLabs procedural-stochastic-texturing or TilingRandomization, handle normal-map edge artifacts (RGAP-008)
- 7.F2: Expand splatmap from 4 channels to 8-16 layers — height-based blending using Mask Map B channel, keep critical materials in first 4 layers for stock URP Terrain Lit, custom shader fallback for >4 (RGAP-007)
- 7.F3: Add mip bias control for terrain texture sampling (RGAP-016)

### Cluster G: Height-blend preview + terrain holes + LOD shader (RGAP-005, RGAP-011, RGAP-012, RGAP-018)
- 7.G1: Add height-blend preview mode in Blender viewport (RGAP-005)
- 7.G2: Add terrain holes / alpha clip to shader for cave entrances and overhangs (RGAP-011)
- 7.G3: Add terrain LOD shader transitions — smooth cross-fade between material detail levels (RGAP-012)
- 7.G4: Add LOD stitching shader to prevent cracks at LOD boundaries (RGAP-018)

### Cluster H: Atmospheric + environmental shading (RGAP-013, RGAP-014, RGAP-015, RGAP-017, RGAP-022, RGAP-032, RGAP-033)
- 7.H1: Add atmospheric fog shader integration — height-based + distance-based fog (RGAP-013)
- 7.H2: Add snow subsurface scattering (SSS) shader — Y-dot-normal projection + SSS for snow layers (F128, RGAP-014, RGAP-032)
- 7.H3: Add GBuffer terrain pass for deferred rendering compatibility (RGAP-015)
- 7.H4: Add terrain ambient occlusion from heightmap-derived cavity map (RGAP-017)
- 7.H5: Add shadow-receiving ground plane shader (RGAP-022)
- 7.H6: Add cloud shadow projection texture — animated noise shadow mask (RGAP-033, F129)
- 7.H7: Add per-region color grading via world-space lookup (RGAP-030)

### Cluster I: Vegetation + scatter shaders (RGAP-019, RGAP-020, RGAP-021, RGAP-023, RGAP-024, RGAP-025, RGAP-026)
- 7.I1: Add wind animation vertex shader for vegetation — world-space phase, per-vertex weight (RGAP-019)
- 7.I2: Add billboard impostor shader for distant trees/bushes (RGAP-020)
- 7.I3: Add density falloff shader for vegetation fade-out at distance (RGAP-021)
- 7.I4: Add vegetation interaction shader — player-pushes-grass displacement (RGAP-023)
- 7.I5: Add per-instance color variation via instance ID hash (RGAP-024)
- 7.I6: Add seasonal vegetation color/density shader controls (F128, RGAP-025)
- 7.I7: Add GPU instancing shader variant for terrain scatter objects (RGAP-026)

### Cluster J: Water-terrain + decal shaders (RGAP-027, RGAP-028, RGAP-029)
- 7.J1: Add water-terrain intersection foam/darkening shader at shorelines (RGAP-027)
- 7.J2: Add decal projection shader for roads/paths/scorch marks on terrain — Unity: URP Decal Projector, Blender: preview geometry above surface (RGAP-028)
- 7.J3: Add runtime terrain deformation shader — footprints/impacts via displacement (RGAP-029)

### Cluster K: Minimap (RGAP-031)
- 7.K1: Add terrain minimap render shader — top-down material-aware render (RGAP-031)

### Acceptance:
- [ ] Single unified material system — no legacy vs V2 split (F270-F276 resolved)
- [ ] All terrain materials have real PBR textures (albedo, normal, roughness, AO, height) (F034, F036, F612)
- [ ] Triplanar shader node group works selectively on cliff faces (F615, RGAP-001)
- [ ] Displacement/POM visible on close-up terrain (F042, F610, RGAP-004)
- [ ] Splatmap weights from DAG appear on Blender mesh (F826)
- [ ] Materials match at tile boundaries (F828)
- [ ] Snow/wetness/moss masks driven by slope/altitude/curvature (F044, F604)
- [ ] Stochastic tiling eliminates visible repetition (RGAP-008)
- [ ] 8+ splatmap layers with height-based blending (RGAP-007)
- [ ] Macro + detail normals combined via RNM at 2x+ heightmap resolution (F120, RGAP-003)
- [ ] Vegetation has wind animation, LOD billboards, per-instance color (RGAP-019-026)
- [ ] Water-terrain intersection has foam/darkening (RGAP-027)
- [ ] Cloud shadow projection visible (RGAP-033)
- [ ] Terrain holes work for cave entrances (RGAP-011)
- [ ] Procedural UV on cliff meshes via Geometry Nodes (F040)
- [ ] Wetness overlay darkens/smooths without duplicating materials (RGAP-006)
- [ ] Zero F034-F049 material bugs remain
- [ ] Zero F600-F621 deep material bugs remain
- [ ] All 33 RGAP items addressed

---

## Phase 8: Unity Integration (= Roadmap Phase 57)
**Findings addressed:** F050-F063 (14 Unity export bugs), F188-F203 (16 Unity R3 bugs), F360-F381 (22 Unity compound tool bugs),
F850-F852, CONFLICT-015, GAP-001 through GAP-021 (runtime),
GAP-028 (terrain decals), GAP-029 (runtime deformation), GAP-031 (minimap)
**Goal:** Complete Blender-to-Unity terrain pipeline: export works, C# consumers exist, runtime features functional

### Cluster A: Fix Blender-side export fundamentals (F050-F063)
- 8.A1: Add Z-up to Y-up axis swap in terrain_unity_export.py (F050)
- 8.A2: Force little-endian encoding for heightmap NPY export (F051)
- 8.A3: Add resolution validation — reject non-(2^n+1) heightmap sizes with clear error (F052)
- 8.A4: Wire compose_terrain_node/compose_map to invoke Unity terrain setup bridge (F053)
- 8.A5: Write vegetation/prop placement manifest JSON from scatter pass for Unity consumption (F054)
- 8.A6: Add FBX terrain mesh export + TerrainData .asset generation C# script (F055)
- 8.A7: Add tile stitching verification — validate border heights match before export (F056)
- 8.A8: Add LOD FBX chain export for terrain meshes (F057)
- 8.A9: Expand splatmap exporter beyond 4-channel RGBA — support 6-8 layers via multiple textures (F058)
- 8.A10: Remove hardcoded `len(splatmap_layers) != 4` check in scene_templates.py (F059)
- 8.A11: Unify two incompatible export schemas (compose_map .raw vs compose_terrain_node manifest) into single export contract with run-ID and cleanup (F060)
- 8.A12: Remove hidden `stack.set("heightmap_raw_u16")` side-effect from export function (F061)
- 8.A13: Fix determinism_hash to compute BEFORE stack mutation (F062)
- 8.A14: Add heightmap/splatmap/manifest awareness to handle_export_fbx/gltf (F063)

### Cluster B: Fix Unity-side C# consumers (F188-F203)
- 8.B1: Fix C# heightmap reader endianness — add explicit LE/BE handling with validation (F188)
- 8.B2: Add file size validation in C# reader — reject resolution mismatches instead of truncating (F189)
- 8.B3: Fix hardcoded TerrainData asset path — use run-ID or caller-supplied path (F190)
- 8.B4: Fix JSON construction — use proper serializer instead of string concatenation, handle Windows paths (F191)
- 8.B5: Fix missing heightmap fallback — error instead of silent flat terrain (F192)
- 8.B6: Fix terrain_size to read from producer manifest instead of hardcoded defaults (F193)
- 8.B7: Add manifest_path parameter to _handle_scene_setup_terrain — consume world_origin, coordinate_system, bit_depth, cell_size, tile_x/y (F194)
- 8.B8: Fix alphamap weight normalization — log warnings for NaN/negative instead of silent fix (F195)
- 8.B9: Add flip_vertical assertion for tiled terrain neighbor wiring (F196)
- 8.B10: Fix production pipeline param mismatches — terrain_import `terrain_size` vs handler `heightmap_path` (F197)
- 8.B11: Fix scatter_objects param mismatch — `prefabs` vs `prefab_paths` (F198)
- 8.B12: Create C# NumPy reader or convert NPY to raw binary on export side (F199)
- 8.B13: Add TreePrototype + DetailPrototype wiring — consume tree_instance_points from Blender export (F200, GAP-004)
- 8.B14: Wire navmesh consumer — call terrain_navmesh_export from pipeline, create NavMeshSurface on Unity side (F201, GAP-009)
- 8.B15: Add position parameter to setup_terrain — place at world_origin, not always (0,0,0) (F202)
- 8.B16: Unify two splatmap formats (PNG vs RAW) — standardize on one format with clear extension contract (F203)

### Cluster C: Fix Unity compound tool bugs (F360-F381)
- 8.C1: Fix 11 dead/misnamed action references in production_templates.py (F360-F369)
  - Fix `unity_assets.fbx_import` to real action name (F360, F362)
  - Fix `unity_prefab.create` param `type` to `prefab_type` (F361, F365)
  - Fix `unity_assets.material_auto_generate` to real action (F363)
  - Fix `unity_camera.virtual_camera` to `create_virtual_camera` (F364)
  - Fix `unity_content.loot_table` to `create_loot_table` with correct params (F366)
  - Fix `unity_qa.test_runner` to `run_tests` (F367)
  - Fix `unity_build.build_multi_platform` param `build_target` to `platforms` (F368)
  - Fix `unity_qa.play_session` to real action (F369)
- 8.C2: Replace pipeline orchestrator theater with real MCP tool invocations (F370)
- 8.C3: Fix dolly camera CinemachineSplineDolly — require spline/path assignment (F371)
- 8.C4: Fix audio zone reverb placement — derive bounds from cave/interior/terrain data (F372)
- 8.C5: Add terrain/splatmap/heightmap inputs to environmental VFX actions (F373)
- 8.C6: Fix paint_terrain_detail to use slope/height/biome/splat instead of constant density (F374)
- 8.C7: Fix create_terrain_blend depression radius for non-square terrains (F375)
- 8.C8: Fix setup_occlusion to include Unity Terrain components as occluders/occludees (F376)
- 8.C9: Standardize world script status to `"success"` (not `"ok"`) (F377)
- 8.C10: Fix setup_map_streaming to include terrain tiles and TerrainData in streaming groups (F378)
- 8.C11: Fix AAA quality audit to include TerrainData/TerrainLayer in quality gates (F379)
- 8.C12: Fix setup_lod_groups to handle Unity Terrain LOD/streaming (not just MeshRenderer) (F380)
- 8.C13: Fix save schema to include player transform, terrain tile, and streamed-world state (F381)

### Cluster D: Unity erosion + terrain tools (F850-F852, CONFLICT-015)
- 8.D1: Add AdvancedTerrainErosion UPM package dependency (F850, CONFLICT-015)
- 8.D2: Create unity_terrain tool action for erosion config + evaluation via Burst
- 8.D3: Fix Blender-Unity terrain size bridging — read manifest metrics (F851)
- 8.D4: Fix resolution mismatch validation between producer and consumer (F852)

### Cluster E: Runtime terrain features (GAP-001 through GAP-021)
- 8.E1: Add terrain LOD control tool — heightmapPixelError, basemapDistance, detailObjectDistance (GAP-001)
- 8.E2: Add terrain holes tool — SetHoles API for cave entrances and overhangs (GAP-003)
- 8.E3: Add terrain collision configuration — layer-based collision, physics material (GAP-005)
- 8.E4: Export Blender mask channels (wetness, ridge, wind, macro) as additional textures for Unity shader (GAP-014)
- 8.E5: Add per-layer PBR properties to TerrainLayer setup — normal scale, metallic, smoothness (GAP-019)
- 8.E6: Implement LayerProcGen-style chunked terrain streaming — tiles evaluate analytically on demand per camera frustum, Addressables LoadSceneAsync for background loading (GAP-002)
- 8.E7: Add terrain brush tool — runtime terrain painting from editor scripts (GAP-006)
- 8.E8: Add grass/detail wind configuration (GAP-007)
- 8.E9: Add terrain material instancing — per-terrain material property blocks (GAP-008)
- 8.E10: Add terrain layer blending configuration — smooth vs sharp transitions (GAP-010)
- 8.E11: Add terrain shadow configuration — cascade shadow maps for terrain (GAP-011)
- 8.E12: Implement quadtree/CDLOD terrain LOD — distance-based detail selection with smooth transitions, geometry clipmap nested grids, drawInstanced for GPU instancing (GAP-012)
- 8.E13: Add terrain fog integration — height fog, distance fog, volumetric (GAP-013)
- 8.E14: Implement virtual texturing setup — splatmap resolution 2x-4x heightmap, texture streaming by camera distance (GAP-015)
- 8.E15: Add terrain vegetation density control — distance-based LOD for grass/details (GAP-016)
- 8.E16: Add terrain weather effects integration — rain puddles, snow accumulation (GAP-017)
- 8.E17: Add terrain reflection probe placement — auto-place based on terrain features (GAP-018)
- 8.E18: Add terrain audio zone auto-generation from biome data (GAP-020)
- 8.E19: Add terrain particle effects — dust, sand, snow particles from terrain type (GAP-021)

### Cluster F: Runtime advanced features (GAP-028, GAP-029, GAP-031)
- 8.F1: Add terrain decal system — roads, paths, scorch marks as projected decals (GAP-028)
- 8.F2: Implement runtime terrain deformation — SetHeightsDelayLOD + CopyActiveRenderTextureToHeightmap for footprints/impacts, DirtyHeightmapRegion for partial updates, PhysX heightfield collision auto-updates (GAP-029)
- 8.F3: Add terrain minimap renderer — top-down camera with terrain material awareness (GAP-031)

### Cluster G: Export pipeline extensions (from research alignment)
- 8.G1: Export baked flowmap textures — pack RG=flow direction, B=foam intensity from analytical gradient + flow accumulation. Reference: Arnklit/Waterways
- 8.G2: Implement terrain hole workflow for caves — Paint Holes API punches through heightfield, rock meshes hide aliased edges, NavMesh respects holes, dual-layer heightmap drives automatic hole placement
- 8.G3: Add terrain collision optimization — PhysX heightfield collider with resolution matching physics needs (lower than render), separate collision mesh for dynamic vs static

### Acceptance:
- [ ] Blender heightmap exports with correct axis swap, endianness, and resolution validation (F050-F052)
- [ ] C# reader correctly imports heightmaps at any valid 2^n+1 resolution (F189)
- [ ] Manifest contract consumed on Unity side — correct world_origin, size, coordinate system (F194)
- [ ] All 11 dead action references in production_templates.py fixed and tested (F360-F369)
- [ ] Orchestrator invokes real MCP tools (not theater) (F370)
- [ ] AdvancedTerrainErosion evaluates terrain in Unity editor (F850)
- [ ] Terrain holes work for cave entrances (GAP-003)
- [ ] Trees placed via TreePrototype with billboard LOD (F200, GAP-004)
- [ ] NavMeshSurface generated from terrain data (F201, GAP-009)
- [ ] Mask channels exported and consumed by Unity shader (GAP-014)
- [ ] Splatmap supports 6-8+ layers (F058, F059)
- [ ] Terrain tiles stream in/out based on camera position (GAP-002)
- [ ] Flowmap texture drives animated water shader (8.G1)
- [ ] Footprints/impacts deform terrain at runtime (GAP-029)
- [ ] Terrain holes auto-placed where ceiling heightmap exists (8.G2)
- [ ] LOD transitions smooth with no popping (GAP-012)
- [ ] Terrain decals, runtime deformation, and minimap functional (GAP-028, GAP-029, GAP-031)
- [ ] Save system includes terrain-aware state (F381)
- [ ] Zero F050-F063 export bugs remain
- [ ] Zero F188-F203 C# consumer bugs remain
- [ ] Zero F360-F381 compound tool bugs remain

---

## Phase 9: Cleanup — Silent Swallows + Stubs + Non-terrain Fixes (= Roadmap Phase 58)
**Findings addressed:** F019-F030 (silent swallows), F031-F033 (workflow presets), F068-F079 (stubs),
F080-F081 (Bundle H phantom), F088-F089 (dead side-effect passes), F090-F097 (addon lifecycle),
F098-F104 (TCP/protocol), F170-F187 (frozen-mutable + state), F214-F224 (dead code/wiring),
F225-F240 (MCP layer bugs), F320-F331 (blender_server stubs), F520-F549 (non-terrain generators),
F661-F767 (remaining terrain files), F845, F853-F857, F864,
R7 findings, GAP-018 through GAP-024, GAP-026
**Goal:** No silent exception swallowing, no dead stubs, no broken non-terrain generators, clean codebase

### Cluster A: Silent exception swallowing — replace bare except with logging (F019-F030, F856-F857)
- 9.A1: Fix `_safe_import_registrar` — log bundle name + traceback on import failure, return error info to caller (F019, F856)
- 9.A2: Fix `terrain_checkpoints.py:352` bare except with wrong arity on autosave chain (F020)
- 9.A3: Fix `terrain_waterfalls.py:699` "defensive" bare except — log and re-raise or handle specifically (F021)
- 9.A4: Fix 3 bare excepts in terrain_region_exec.py (region execution, checkpoint save, rollback) (F022)
- 9.A5: Fix 2 nested `pass` swallows on banded_cache in terrain_banded.py (F023)
- 9.A6: Add try/except to `terrain_pipeline` MCP action — surface errors as structured JSON, not raw TCP (F024)
- 9.A7: Fix 3 swallows in terrain_addon_health.py — health check must not lie about health (F025)
- 9.A8: Fix terrain_hot_reload.py reload failures — distinguish from missing modules (F026)
- 9.A9: Fix snapshot diffing swallow in terrain_golden_snapshots.py (F027)
- 9.A10: Fix sidecar write swallow in terrain_checkpoints_ext.py (F028)
- 9.A11: Fix pass_validation_full rollback failure — mark `triggered_rollback=True` even on rollback error (F029)
- 9.A12: Fix 3 `pass` swallows in environment.py material/vegetation paths (F030)
- 9.A13: Replace all 15+ bare `except Exception: pass` in compose_map export pipeline with structured logging and error propagation (F857)

### Cluster B: Workflow presets (F031-F033)
- 9.B1: Expand `terrain_unity_ready_free` preset to include cliffs, caves, waterfalls, water_variants, materials_v2, scatter_intelligent (F031)
- 9.B2: Verify `pass_prepare_heightmap_raw_u16` registration via Bundle J (F032 — already exists, confirm wiring)
- 9.B3: Create `terrain_unity_ready_aaa` and `terrain_unity_ready_full` presets with all passes (F033)

### Cluster C: Stubs — implement or delete (F068-F079, F855)
- 9.C1: Implement `terrain_dirty_tracking.coalesce` — merge overlapping dirty regions (F068)
- 9.C2: Implement 5 twelve-step orchestrator stubs: `_apply_flatten_zones_stub`, `_apply_canyon_river_carves_stub`, `_detect_cliff_edges_stub`, `_detect_cave_candidates_stub`, `_detect_waterfall_lips_stub` (F069-F072, F855)
- 9.C3: Wire `detect_wetlands` in terrain_water_variants.py or mark as deferred with comment (F073)
- 9.C4: Wire `apply_quixel_to_layer` to Blender shader consumer or delete dead JSON-only path (F074)
- 9.C5: Implement `_coerce_bbox` in terrain_scene_read.py (F075)
- 9.C6: Implement `_safe_asarray` in terrain_validation.py (F076)
- 9.C7: Delete or implement `_load_records` in terrain_telemetry_dashboard.py (F077 — RETRACTED but stub remains)
- 9.C8: Implement `_coerce_location` in terrain_review_ingest.py (F078)
- 9.C9: Fix honesty_lint.py symbol extractor — use AST-based extraction instead of 5-LOC heuristic (F079, F224)

### Cluster D: Bundle H phantom modules (F080-F081, F853)
- 9.D1: Add `register_*_pass` functions to terrain_morphology.py, terrain_hierarchy.py, terrain_rhythm.py, terrain_negative_space.py — OR delete the 899 LOC of orphan code (F080, F081, F853)
- 9.D2: Fix registrar docstring to match actual registered bundles (F080)

### Cluster E: Dead side-effect passes (F088-F089)
- 9.E1: Wire god_ray_hints to stack or export — store hints array, not just `len(hints)` in metrics (F088, F214)
- 9.E2: Wire stochastic shader UV direction to exporter or delete direction computation (F089)

### Cluster F: Addon lifecycle + hot reload (F090-F097, F864)
- 9.F1: Expand hot_reload module list beyond 4 modules — or document which modules need Blender restart (F090)
- 9.F2: Wire hot_reload to an actual caller — currently defined but never invoked (F091)
- 9.F3: Fix importlib.reload cascade — reload dependencies in correct order (F092)
- 9.F4: Fix PassDAG.execute_parallel — either implement real parallelism or rename to execute_serial (F093)
- 9.F5: Make register_pass idempotent — skip or update on duplicate instead of raising ValueError (F094, F726)
- 9.F6: Delete Bundle N no-op registration or implement real passes (F095)
- 9.F7: Add mid-batch checkpoint save to batch_process (F096)
- 9.F8: Add `bpy.app.version` runtime checks for 4.2-4.6 API compatibility (F097)
- 9.F9: Fix PASS_REGISTRY class-level mutable shared state for parallel safety (F864)

### Cluster G: TCP/protocol bugs (F098-F104)
- 9.G1: Add numpy JSON encoder (`default=` handler for np.float32/int64/ndarray) to socket_server.py (F098)
- 9.G2: Include full traceback in error responses, not just `str(e)` (F099)
- 9.G3: Add outbound message size cap or chunked transfer to socket_server.py (F100)
- 9.G4: Fix timer queue — handle concurrent clients without 300s queue buildup (F101)
- 9.G5: Include `created_objects` list in handle_run_terrain_pass return dict (F102)
- 9.G6: Fix empty-dict scene_read — treat `{}` same as None to avoid phantom pipeline inserts (F103)
- 9.G7: Fix ProtocolGate — either wire `enforce_protocol=True` or delete the dead gate (F104, F274)

### Cluster H: Frozen-mutable + state bugs (F170-F187, F845)
- 9.H1: Fix `HeroFeatureSpec(frozen=True)` with mutable Dict — use `MappingProxyType` or unfrozen (F170, F845)
- 9.H2: Fix `TerrainIntentState(frozen=True)` with mutable Dict (F171, F845)
- 9.H3: Fix `compute_hash` NaN bytes vs `__eq__` NaN contract violation (F172)
- 9.H4: Add `detail_density` to `compute_hash` _ARRAY_CHANNELS or iterate all dict channels (F173)
- 9.H5: Fix `to_npz` to persist `detail_density`, `wildlife_affinity`, `decal_density` (F174)
- 9.H6: Fix `from_npz` — validate meta dict completeness, don't lie about provenance (F175)
- 9.H7: Fix `populated_by_pass` provenance tracking — update on mutation, not just init (F176)
- 9.H8: Wire or delete orphan channels: `physics_collider_mask`, `lightmap_uv_chart_id`, `lod_bias`, `tree_instance_points`, `ambient_occlusion_bake` (F177)
- 9.H9: Convert f64 allocations to f32 where precision is not needed — save ~60MB/tile (F178)
- 9.H10: Fix upcast-then-copy double allocation in terrain_advanced.py erosion iterations (F179)
- 9.H11: Fix circular import chain terrain_pipeline <-> everything — break with lazy imports or interface module (F180)
- 9.H12: Fix terrain_features.py module-level globals `_features_gen`, `_features_seed` — make instance-scoped or pass as params (F181)
- 9.H13: Fix terrain_checkpoints.py module-level dicts keyed by `id(controller)` — use weakref or controller registry (F182, F710)
- 9.H14: Fix terrain_validation.py `_ACTIVE_CONTROLLER` global — concurrent pipeline safety (F183)
- 9.H15: Register missing Bundle M or document why it's skipped (F184)
- 9.H16: Fix registrar partial registration — add rollback on partial failure (F185)
- 9.H17: Fix error string membership test in registrar — `"F" in loaded` misses `"SKIPPED"` (F186)
- 9.H18: Guard Bundle O child imports — handle terrain_vegetation_depth/terrain_water_variants import failures (F187)

### Cluster I: Dead code + unwired functions (F214-F224)
- 9.I1: Wire `enforce_budget` to pipeline or compose_* orchestrators (F215)
- 9.I2: Wire `apply_differential_erosion` from terrain_stratigraphy.py into pass pipeline (F216)
- 9.I3: Wire `collect_performance_report` to compose_* orchestrators (F217)
- 9.I4: Fix pass_decals `produces_channels` — declare `decal_density` so DAG orders correctly (F218)
- 9.I5: Reconcile framing height writer (F219/F754) with delta integration architecture
- 9.I6: Fix roughness_driver — produce `erosion_amount`/`deposition_amount` from erosion pass or delete dead reads (F220, F745)
- 9.I7: Fix multiscale_breakup idempotency — track if breakup already applied, don't add additively (F221)
- 9.I8: Fix test_terrain_caves.py to assert on stack.height deltas and mesh, not just dataclass fields (F222)
- 9.I9: Fix test_bundle_r.py — remove hero builder mocks, test real integration (F223)
- 9.I10: Fix honesty_lint.py to use AST-based analysis instead of LOC heuristic (F224)
- 9.I11: [VERIFICATION] Verify all 32 R15J zero-caller functions have production callers after Phase 6 wiring. Any still-unwired function gets wired here as catchall — generate_biome_transition_mesh, generate_terrain_bridge_mesh, detect_estuary, detect_karst_springs, apply_seasonal_water_state, detect_destructibility_patches, compute_footprint_surface_data, generate_weathering_timeline, apply_weathering_event, generate_diff_overlay, etc.

### Cluster J: MCP layer bugs — compose_terrain_node + compose_map (F225-F240)
- 9.J1: Fix hero builder success tracking — check `.get("status")` before recording as built (F225)
- 9.J2: Remove or reconcile compose_terrain_node water/river override path that fights DAG water_variants + hero waterfalls (F226)
- 9.J3: Fix fire-and-forget calls — check return status of env_paint_terrain, terrain_create_biome_material, env_scatter_vegetation (F227)
- 9.J4: Fix env_export_heightmap — check `.get("ok")`/`.get("status")` on return (F228)
- 9.J5: Add `"error"` state to compose_terrain_node — don't collapse all post-pipeline failures to "success"/"partial" (F229)
- 9.J6: Merge caller-supplied `spec.protected_zones` with `seam_protected_zones` (F230)
- 9.J7: Align compose_terrain_node default pipeline with terrain_unity_ready_free preset (F231)
- 9.J8: Add try/except to compose_terrain_node body — handle TCP disconnects/timeouts/JSON errors (F232)
- 9.J9: Reconcile compose_terrain_node (no try/except) vs compose_map (swallows everything) error semantics (F233)
- 9.J10: Coordinate three cliff systems — pass_cliffs, legacy cliff overlay, hero cliff builder — into single path (F234)
- 9.J11: Add error check to clear_scene call — don't silently wipe scene (F235)
- 9.J12: Add seam verification caching — don't run 5x full preview pipelines per call (F236)
- 9.J13: Fix blender_environment position parameter — add `position` to function signature (F237)
- 9.J14: Update asset_pipeline docstring to include all 29 actions (F238)
- 9.J15: Add checkpoint support to compose_terrain_node (F239)
- 9.J16: Audit previously-unread compose_terrain_node lines 3283-3568 and compose_map lines 4224-4541 (F240)

### Cluster K: blender_server compound tool stubs (F320-F331)
- 9.K1: Fix generate_prop fallback — invoke actual procedural generator when Tripo absent (F320)
- 9.K2: Fix generate_map_package — fail on per-object game-check/LOD/FBX errors instead of suppressing (F321)
- 9.K3: Fix aaa_verify angle label reconstruction after mid-sequence capture failure (F322)
- 9.K4: Implement real performance_check handler — replace stub that returns fake data (F323)
- 9.K5: Fix generate_lod_chain — fail when source object missing, don't return synthetic LOD spec (F324)
- 9.K6: Fix compose_interior checkpoint resume — cover linked interior, geometry enhancement, storytelling-prop passes (F325)
- 9.K7: Fix compose_interior prop quality gate — inspect generated props, not room shell (F326)
- 9.K8: Fix batch_process selection state leak between items — select target before export (F327)
- 9.K9: Fix import_model/import_and_process object discovery — use actual imported mesh names, not filename stem fallback (F328)
- 9.K10: Fix terrain_pipeline list_passes/list_bundles — return actual registry data, not empty wrappers (F329)
- 9.K11: Fix terrain_pipeline list_checkpoints and rollback — persist controller across MCP calls (F330)
- 9.K12: Fix inspect_external_toolchain to include `selection` and `disabled_but_installed` fields in agent_contract (F331)

### Cluster L: Non-terrain generator chain fixes (F520-F549 minus F527)
- 9.L1: Fix execute.py sandbox: add stdout truncation, wall-clock timeout, stderr capture, ImportError handling, execution logging (F520-F526)
- 9.L2: Sanitize generated Geometry Nodes names — strip dots/spaces from target_name (F528)
- 9.L3: Add node_groups reuse guard — `.get()` before `.new()` to prevent .001/.002 leaks (F529)
- 9.L4: Fix modifier_apply context override for Blender 4.x compatibility (F530)
- 9.L5: Fix curvature-to-roughness wiring — don't report `"applied": True` on exception (F532)
- 9.L6: Fix auto_generate_lod_chain datablock leak — reuse existing LOD_group (F533)
- 9.L7: Fix road_network heightmap indexing — use clamp not modulo for world-to-grid mapping (F536)
- 9.L8: Fix road segment mesh to sample terrain height along path, not linear interpolate (F537)
- 9.L9: Add terrain_heightmap required parameter to compute_road_network — error on None (F538)
- 9.L10: Fix _building_grammar.py blanket except — narrow exception handling so rich detail mesh errors are visible, not silently producing boxes (F540)
- 9.L11: Add terrain_heightmap reference to _building_grammar.py — building Z from terrain (F541)
- 9.L12: Add terrain awareness to _settlement_grammar.py — 3D grid placement (F542)
- 9.L13: Add heightmap input to _dungeon_gen.py — dungeon entrances at correct Z (F543)
- 9.L14: Couple _biome_grammar.py to heightmap-derived biome hints (F544)
- 9.L15: Fix _mesh_bridge.py datablock leak + silent material-assignment failure (F545-F547)
- 9.L16: Create shared `sample_terrain_height(x, y)` helper for the entire non-terrain generator chain (F548)
- 9.L17: Create shared `ensure_datablock(collection, name, create_fn)` helper to prevent datablock leaks across all handlers (F549)

### Cluster M: Remaining terrain file bugs + generator AAA upgrades (F661-F767)
- 9.M1: Fix `generate_natural_arch` ground interface — add pillar-to-ground mesh transition + asymmetry, notch erosion, partial collapse, contact rubble (F680)
- 9.M2: Fix `generate_geyser` dead RNG variable — actually use `rng` for randomization + add downhill-biased terracing, overflow asymmetry, heat damage staining (F685)
- 9.M3: Fix `generate_sinkhole` global state coupling — use only local RNG + add broken rim segments, shelf failures, seep paths (F689)
- 9.M4: Fix `generate_floating_rocks` ring topology — fix modulo index for duplicate/skipped triangles (F693-F695)
- 9.M5: Fix `generate_ice_formation` stale `kt` variable — use per-face kt for material zoning + add drip-line clustering, fracture patterns, thickness-driven material (F697)
- 9.M6: Fix `generate_lava_flow` tangent kink at final vertex + add slope response, branching lobes, pressure ridges, cooled rafts (F700)
- 9.M7: Fix `flatten_layers` resize — use bilinear interpolation, not nearest-neighbor (F664)
- 9.M8: Fix snap origin raycast offset for Z-shifted terrain (F676)
- 9.M9: Fix terrain_chunking grid_cols silently dropping non-multiple-of-chunk_size rows — use ceil division (F716)
- 9.M10: Fix _merge_pass_outputs setattr bypass + hash bugs (F721)
- 9.M11: Fix _producers dict last-wins non-determinism — error or merge on duplicate channel producers (F722)
- 9.M12: Delete duplicate `compute_anisotropic_breakup` — remove terrain_banded_advanced.py dead module (F734, R7-dead-module)
- 9.M13: Fix `apply_anti_grain_smoothing` scipy/numpy non-determinism — pick one backend (F735)
- 9.M14: Fix wind_field seed — consult `intent.seed` (F747)
- 9.M15: Wire `scatter_moraines` output to actual geometry creation (F766)
- 9.M16: Upgrade `apply_morphology_template` from Gaussian blob profiles to drainage/lithology/tectonic controls — all 30 templates (BEST_PRACTICES #10.5)
- 9.M17: Add bulkify post-process pass — detect ridges/features thinner than minimum width threshold and widen (BEST_PRACTICES #19)

### Cluster N: R7 remaining findings
- 9.N1: Fix compose_interior checkpoint auto-resume without resume flag (R7 P1)
- 9.N2: Fix settlement radius underestimation in _estimate_location_radius (R7 P1)
- 9.N3: Fix fallback radial search centered at (0,0) instead of query location (R7 P1)
- 9.N4: Fix fog mask toroidal wrapping at tile edges (R7 P2)
- 9.N5: Vectorize compute_flow_map D8 direction for performance (R7 P2)
- 9.N6: Fix compose_terrain_node vegetation skip when no rules list (R7 P2)
- 9.N7: Fix viewport max_size inconsistency (R7 P2)
- 9.N8: Fix compose_map LOD dispatch — use pipeline_generate_lods not asset_pipeline (R7 P0)

### Cluster O: Cleanup-phase AAA geology/rendering gaps (GAP-018 through GAP-024, GAP-026)
- 9.O1: Add periglacial terrain features — patterned ground, pingos, solifluction lobes (GAP-018)
- 9.O2: Add desert pavement / ventifact terrain features (GAP-019)
- 9.O3: Add spring/seep lines at stratigraphy boundaries (GAP-020)
- 9.O4: Add landslide/mass wasting terrain features — rockfall, debris flow, creep (GAP-021)
- 9.O5: Add hot spring mineral terrace generation (GAP-022)
- 9.O6: Add reef/biogenic landform generation (GAP-023)
- 9.O7: Add spheroidal weathering / tafoni texture patterns (GAP-024)
- 9.O8: Add fold/anticline/syncline visible in cliff faces (GAP-026)

### Cluster P: AAA tool parity + production quality (from research alignment)
- 9.P1: Implement non-destructive procedural authoring — every pass re-runnable with same seed producing identical output, add determinism test
- 9.P2: Implement multiscale erosion — low-res macro drainage first, upsample and re-erode at high-res for detail (Houdini HeightField Erode 3.0 pattern)
- 9.P3: Rich auxiliary output validation — verify pipeline exports all masks (wetness, ridge, wind, macro, sediment, debris, flow), add export manifest listing all channels
- 9.P4: Performance at production resolutions — profile pipeline at 4K and 8K heightmap resolution, identify bottlenecks, add numpy vectorization or chunked processing. Target: 8K terrain in <60s

### Acceptance:
- [ ] Zero bare `except Exception: pass` in terrain code paths (F019-F030)
- [ ] Zero bare `except Exception: pass` in compose_map pipeline (F857)
- [ ] No dead stubs — all twelve-step orchestrator steps functional (F069-F072, F855)
- [ ] Bundle H modules either registered with real passes or deleted (F080-F081, F853)
- [ ] All frozen-mutable dataclass issues fixed (F170-F187, F845)
- [ ] TCP protocol handles numpy types, includes tracebacks, caps outbound (F098-F104)
- [ ] Non-terrain generators (buildings, roads, dungeons, settlements) place at correct terrain Z (F540-F548)
- [ ] `sample_terrain_height()` shared helper used by all generators (F548)
- [ ] `ensure_datablock()` shared helper prevents all datablock leaks (F549)
- [ ] compose_terrain_node has try/except, error states, checkpoint support (F225-F240)
- [ ] compose_map error semantics aligned with compose_terrain_node (F233)
- [ ] All hero builder return statuses checked (F225)
- [ ] hot_reload wired and working for all terrain modules (F090-F092)
- [ ] All 15+ remaining terrain file bugs (F661-F767) fixed
- [ ] All R7 findings resolved
- [ ] All GAP-018 through GAP-024 + GAP-026 implemented
- [ ] All 30 morphology templates upgraded with geology controls (9.M16)
- [ ] Generator visual quality: natural arch, geyser, sinkhole, lava, ice all upgraded (9.M1-M6)
- [ ] All 12+ dead functions wired with production callers (9.I11)
- [ ] Pipeline deterministic — same seed = same output (9.P1)
- [ ] 8K terrain generates in <60s (9.P4)
- [ ] quality_lint.py <= 0 findings on handlers/
- [ ] All tests pass
---

## Phase 10: Final Verification + Quality Testing Infrastructure
**Goal:** Full suite green, code reviewer clean, visual verification ready, NEW quality test categories

### Tasks — Verification:
- 10.1: Run full pytest suite — must pass
- 10.2: Run quality_lint.py on all handlers/ — must be 0 findings
- 10.3: Run test_substance_lint.py — real_ratio >= 0.50
- 10.4: Run honesty_lint.py — verify plan claims match code
- 10.5: Run VB code reviewer on all changed files
- 10.6: GSD verifier: goal-backward check against all 780 findings
- 10.7: Update FINDINGS.md with resolution status for each finding
- 10.8: Update episodic memory with lessons learned

### Tasks — Geometric Quality Tests (CRITICAL gap — zero geometry validation exists):
- 10.9: Add `validate_mesh_geometric_quality()` — manifold check (BMEdge.is_manifold), normal consistency (face_normal dot centroid>0), degenerate faces (calc_area<epsilon), aspect ratio bounds. Uses bmesh API
- 10.10: Wire geometric validation into ALL terrain feature generators in test_terrain_features_v2.py + test_terrain_depth.py
- 10.11: Add `test_normals_consistent()` for every generated terrain mesh

### Tasks — Statistical Terrain Quality Tests (CRITICAL gap):
- 10.12: Add `test_height_distribution_shape()` — mountains=right-skewed, plains=Gaussian, canyon=bimodal. scipy.stats.skewtest
- 10.13: Add `test_slope_distribution_realistic()` — slope fits log-normal R²>0.8. Reference: TRI (Riley) classes 0-80 level through >959 extremely rugged
- 10.14: Add `test_fractal_dimension_range()` — box-counting dim in [2.1, 2.5]. <2.05=too smooth, >2.5=noise
- 10.15: Add `test_terrain_spectral_power()` — 1/f^β spectrum β in [1.0, 2.0]
- 10.16: Add `test_hypsometric_integral()` — HI>0.6 youthful, 0.35-0.6 mature, <0.35 old. Validate per terrain type
- 10.17: Add `test_hack_law_exponent()` — drainage Hack's law h in [0.4, 0.7] (global fit 0.54)

### Tasks — Physical Plausibility Tests (CRITICAL gap):
- 10.18: Add `test_river_flows_downhill()` — every step height <= previous. MUST FAIL on current A* bug
- 10.19: Add `test_drainage_acyclic()` — D8 flow direction graph has no cycles
- 10.20: Add `test_erosion_v_shaped_channels()` — cross-section concavity check at river locations
- 10.21: Add `test_thermal_erosion_talus_angle()` — post-erosion max slope <= talus angle parameter

### Tasks — Cross-Feature + LOD + Export Tests:
- 10.22: Add `test_waterfall_at_cliff_edge()` — lip candidates only at cliff edges
- 10.23: Add `test_cave_entrance_on_cliff_face()` — cave entrance within cliff bounds
- 10.24: Add `test_road_preserves_cliff_integrity()` — road grading doesn't flatten cliffs
- 10.25: Add `test_lod_max_height_error()` + `test_lod_seam_continuity()`
- 10.26: Add `test_uint16_quantization_error()` + `test_splatmap_normalization_post_export()`

### Tasks — Visual Regression Infrastructure:
- 10.27: Create `terrain_visual_qa.py` — renders 5 QA views (height colormap, slope heatmap, normal map, wireframe, drainage overlay) via numpy+PIL (no bpy needed for 4 of 5). Pure numpy deterministic renders
- 10.28: Create `terrain_image_compare.py` — SSIM + pHash comparison. Thresholds: >0.92 pass, 0.80-0.92 warn, <0.80 fail
- 10.29: Create `terrain_anomaly_detector.py` — 7 rule-based detectors: smooth_blob (fractal_dim<2.05), flat_terrain (height_std<0.5m), inverted_terrain (ridges lower than valleys), cliff_absence (cliff_fraction<5%), drainage_disconnect, material_monotony, noise_garbage (fractal_dim>2.5). Terrain-type-specific thresholds via TERRAIN_PROFILES dict
- 10.30: Create `terrain_statistics.py` — compute TerrainStatistics dataclass (height/slope/drainage/roughness/fractal_dim/curvature/material coverage) from TerrainMaskStack. Pure numpy
- 10.31: Create `terrain_qa_report.py` — generates HTML report with thumbnails, statistics, anomaly findings, golden comparison diffs. Self-contained single file
- 10.32: Register `pass_visual_qa` in TerrainPassController + add `visual_qa` action to terrain_pipeline MCP tool
- 10.33: Generate golden reference images for 10 canonical seeds stored in `.planning/terrain_qa_golden/`

### Tasks — Quality Lint + Protocol:
- 10.34: Extend quality_lint.py: detect hardcoded-dict returns, np.zeros_like as result, missing seed propagation, Y-up/Z-up coord bugs
- 10.35: Extend test_substance_lint.py: STRUCTURAL classification for range-only assertions
- 10.36: Verify AGENT_QUALITY_PROTOCOL.md exists and CLAUDE.md references it
- 10.37: Add pre-commit hook: quality_lint + test_substance_lint on changed terrain files
- 10.38: Add PTRM realism scoring — geomorphon classification (10 landform types), score >0.6 acceptable, >0.8 good
- 10.39: Add property-based testing with Hypothesis — terrain invariants as properties ("for any seed, no holes", "slope < X at walkable areas")
- 10.40: Add automated daily world validation scan (AC Origins pattern) — scheduled script runs full terrain pipeline on 10 canonical seeds, compares against golden references, generates visual report with regressions flagged. Integrates with CI or GSD scheduled task. Catches regressions automatically without manual QA (BEST_PRACTICES #13.1)

### Acceptance:
- [ ] All tests pass, all lints clean, code reviewer 0 P0/P1
- [ ] FINDINGS.md resolution status for every finding
- [ ] Geometric quality tests pass for all feature generators (10.9-10.11)
- [ ] Statistical terrain tests validate realistic distributions (10.12-10.17)
- [ ] Rivers flow downhill test catches A* bug before fix, passes after (10.18)
- [ ] Drainage network acyclic (10.19), erosion V-shaped (10.20)
- [ ] Golden references exist for 10 seeds (10.33)
- [ ] Visual QA SSIM >0.92 against golden (10.28)
- [ ] Anomaly detector catches smooth blobs + flat terrain + noise garbage (10.29)
- [ ] quality_lint.py has 10+ patterns (10.34)
- [ ] AGENT_QUALITY_PROTOCOL.md referenced in CLAUDE.md (10.36)
- [ ] Pre-commit hook blocks quality regressions (10.37)
- [ ] PTRM realism score >0.6 for all terrain types (10.38)
- [ ] Hypothesis finds zero invariant violations across 100 random seeds (10.39)
- [ ] Daily automated validation scan configured and producing reports (10.40)
